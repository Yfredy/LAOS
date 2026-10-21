"""SM8845/HTP V81 的受限 QNN 构建矩阵。

设计口径（与 2026-10-20 故障基线绑定）：

- 每个候选 QAIRT 树先建一个 `y=x+1` smoke context，只有元数据实测为
  `socModel=87`、`dspArch=81` 才算合格；2.47 之类的静默回退
  （实测 `socModel=0`、`dspArch=81`）只作为被拒绝的反例，绝不进入 CAM++ 构建；
- 转换固定 W8A16（`--weights_bitwidth 8`、`--act_bitwidth 16`）并使用
  40 条真实语音校准列表；真执行与展示共用同一 argv 构造器，每次构建记录
  converter / model-lib / context generator / context utility 四条完整命令
  与产物 SHA-256；
- context 必须恰好一个 graph、build ID 与本候选树一致、graph 名与 build
  variant 一致；元数据不满足即 `metadata_rejected`；
- context generator exit 0 但日志出现 `unexpected GraphHtpSettings option`
  时记 `config_warning`：产物保留但不上机，且 vtcm 在等价性证明前不算独立
  变量；
- 失败的构建（`build_error` / `metadata_rejected`）不留下任何 context
  产物：全部中间物先落 `artifacts.tmp/`，只有成功才原子提升；
- 完整图变体总数硬上限 10（按不同 context 二进制计数），Stage B 只在
  Stage A 没有通过时展开；VTCM 8 MB 只在 4 MB 档全部失败后升级；
- QPM 库存查询结果必须显式写入矩阵 JSON，查不到就写 `unavailable` 及原因。

    python -m scripts.speaker_qnn.build inventory
    python -m scripts.speaker_qnn.build matrix --stage toolchain
    python -m scripts.speaker_qnn.build matrix --stage compiler
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import (
    CAMPLUS_INPUT_SHAPE,
    CAMPLUS_OUTPUT_SHAPE,
    SCHEMA_VERSION,
    ContextMetadata,
    load_context_metadata,
    validate_sm8845_context,
    write_json_atomic,
)
from .device import detect_build_id

REPO = Path(__file__).resolve().parents[2]
QNN_ROOT = REPO / "var/speaker-benchmark/qnn"
DEBUG_ROOT = QNN_ROOT / "campplus-htp-debug"
DEFAULT_MODEL = (
    QNN_ROOT / "campplus-w8a16-v2/campplus-3s-fp32-static-stats.onnx"
)
DEFAULT_CALIBRATION = QNN_ROOT / "campplus-w8a16/input_list.txt"
SMOKE_MODEL = QNN_ROOT / "htp-smoke/smoke.onnx"
SMOKE_CALIBRATION = QNN_ROOT / "htp-smoke/input-list-host.txt"

GRAPH_NAME = "campplus_w8a16_static_stats"
SMOKE_GRAPH_NAME = "smoke_w8a16"
SMOKE_INPUT_SHAPE = (1, 16)
SMOKE_OUTPUT_SHAPE = (1, 16)
MAX_FULL_GRAPH_VARIANTS = 10

QPM_PRODUCT = "qualcomm_ai_runtime_community"
CONFIG_WARNING_MARKER = "unexpected GraphHtpSettings"

DEFAULT_QAIRT_ROOTS: tuple[Path, ...] = (
    QNN_ROOT / "sdk/qairt/2.47.0.260601",
    QNN_ROOT / "sdk-2.51/qairt/2.51.1.261002",
    QNN_ROOT / "sdk-2.51.40/qairt/2.51.40.260930",
)
QAIRT_PYTHON = Path(
    os.environ.get("LAOS_QAIRT_PYTHON", QNN_ROOT / ".venv310/Scripts/python.exe")
)
CMAKE_BIN = Path(
    os.environ.get(
        "LAOS_CMAKE_BIN",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
        r"\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin",
    )
)

# inventory 组件 → QAIRT root 内相对路径。
COMPONENT_PATHS: dict[str, str] = {
    "runner": "bin/aarch64-android/qnn-net-run",
    "backend_host": "lib/x86_64-windows-msvc/QnnHtp.dll",
    "backend_android": "lib/aarch64-android/libQnnHtp.so",
    "stub": "lib/aarch64-android/libQnnHtpV81Stub.so",
    "skel": "lib/hexagon-v81/unsigned/libQnnHtpV81Skel.so",
    "converter": "bin/x86_64-windows-msvc/qnn-onnx-converter",
    "context_generator": "bin/x86_64-windows-msvc/qnn-context-binary-generator.exe",
    "profile_viewer": "bin/x86_64-windows-msvc/qnn-profile-viewer.exe",
}
SHELL_COMPONENTS = frozenset({"converter"})  # Python 脚本无内嵌 build ID

BUILD_READY = "ready"
BUILD_CONFIG_WARNING = "config_warning"
BUILD_METADATA_REJECTED = "metadata_rejected"
BUILD_ERROR = "build_error"
BUILD_CALIBRATION_REJECTED = "calibration_rejected"
# 只有这些状态算失败；device_unavailable / config_warning 是"未验证"，
# 不构成升级 VTCM 的理由。
FAILURE_STATUSES = frozenset(
    {
        "build_error",
        "metadata_rejected",
        "calibration_rejected",
        "load_error",
        "timeout",
        "ssr",
        "execute_error",
    }
)

STEP_TIMEOUT = 124  # 与 GNU coreutils 的超时退出码对齐

# 校准清单：40 条真实语音、20 个说话人，评估集说话人必须完全排除。
CALIBRATION_MANIFEST_NAME = "calibration_manifest.json"
CALIBRATION_SUMS_NAME = "SHA256SUMS.txt"
CALIBRATION_RECORDS = 40
CALIBRATION_SPEAKERS = 20


@dataclass(frozen=True)
class ToolchainSpec:
    """一套同 build 的 QAIRT 树（设备侧 + host 侧工具）。"""

    build_id: str
    root: Path
    runner: Path
    backend_host: Path
    backend_android: Path
    stub: Path
    skel: Path
    converter: Path
    context_generator: Path
    profile_viewer: Path

    @classmethod
    def from_inventory(cls, inventory: Mapping[str, Any]) -> "ToolchainSpec":
        build_id = str(inventory.get("build_id") or "")
        components = inventory.get("components") or {}
        missing = sorted(set(COMPONENT_PATHS) - set(components))
        if not build_id or missing:
            raise ValueError(
                "QAIRT inventory 不完整："
                f"build_id={build_id!r}, 缺少组件={missing}"
            )
        mismatched = {
            name: str(components[name].get("build_id"))
            for name in COMPONENT_PATHS
            if str(components[name].get("build_id")) != build_id
        }
        if mismatched:
            detail = ", ".join(f"{name}={value}" for name, value in sorted(mismatched.items()))
            raise ValueError(f"mixed QAIRT build: 期望 {build_id}，实际 {detail}")
        return cls(
            build_id=build_id,
            root=Path(inventory["root"]),
            **{
                name: Path(components[name]["path"])
                for name in COMPONENT_PATHS
            },
        )

    @property
    def short_version(self) -> str:
        parts = self.build_id.lstrip("v").split(".")
        return ".".join(parts[:3])

    @property
    def model_lib_generator(self) -> Path:
        return self.root / "bin/x86_64-windows-msvc/qnn-model-lib-generator"

    @property
    def context_utility(self) -> Path:
        return self.root / "bin/x86_64-windows-msvc/qnn-context-binary-utility.exe"

    @property
    def net_run_extensions(self) -> Path:
        return self.root / "lib/x86_64-windows-msvc/QnnHtpNetRunExtensions.dll"

    def inventory(self) -> dict[str, Any]:
        return {
            "build_id": self.build_id,
            "root": str(self.root),
            "components": {
                name: {"path": str(getattr(self, name)), "build_id": self.build_id}
                for name in COMPONENT_PATHS
            },
        }


@dataclass(frozen=True)
class BuildVariant:
    """一个完整图/子图的编译配置（Stage A/B 的矩阵单元）。"""

    toolchain: ToolchainSpec
    optimization_level: int
    vtcm_mb: int
    dlbc: bool
    graph_name: str

    def __post_init__(self) -> None:
        if self.optimization_level not in (0, 1, 2, 3):
            raise ValueError(f"optimization_level 必须在 0..3：{self.optimization_level}")
        if self.vtcm_mb not in (4, 8):
            raise ValueError(f"vtcm_mb 只允许 4/8：{self.vtcm_mb}")
        if not self.graph_name:
            raise ValueError("graph_name 不能为空")

    @property
    def variant_id(self) -> str:
        return (
            f"{self.toolchain.short_version}-opt{self.optimization_level}"
            f"-vtcm{self.vtcm_mb}-dlbc{int(self.dlbc)}-{self.graph_name}"
        )


@dataclass(frozen=True)
class BuildArtifact:
    """一次构建的可审计结果；失败也落盘，绝不留下半成品 context。"""

    variant_id: str
    status: str
    context_path: str | None
    metadata: ContextMetadata | None
    sha256: dict[str, str]
    commands: tuple[str, ...]
    error: str | None
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "status": self.status,
            "context_path": self.context_path,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "sha256": dict(self.sha256),
            "commands": list(self.commands),
            "error": self.error,
            "warning": self.warning,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command(argv: Sequence[object]) -> str:
    return subprocess.list2cmdline([str(part) for part in argv])


def _tail(text: str, lines: int = 20) -> str:
    return "\n".join((text or "").strip().splitlines()[-lines:])


def _log_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def require_toolchain_files(toolchain: ToolchainSpec) -> None:
    """十一件必需文件必须全部在位，缺一即拒绝构建。

    build ID 同号只覆盖 `discover_toolchains` 的 8 个 inventory 组件（其中
    converter 无内嵌版本串、沿用首个探测值）；model-lib generator、
    context utility、backend extension 不内嵌 build ID，这里只校验文件存在，
    不能声称十一件全部同号。
    """
    paths = {
        "runner": toolchain.runner,
        "backend host": toolchain.backend_host,
        "backend android": toolchain.backend_android,
        "V81 stub": toolchain.stub,
        "V81 skel": toolchain.skel,
        "converter": toolchain.converter,
        "context generator": toolchain.context_generator,
        "model lib generator": toolchain.model_lib_generator,
        "context utility": toolchain.context_utility,
        "backend extension": toolchain.net_run_extensions,
        "profile viewer": toolchain.profile_viewer,
    }
    missing = [
        f"{label}: {path}"
        for label, path in paths.items()
        if not Path(path).is_file()
    ]
    if missing:
        raise FileNotFoundError("QAIRT 文件缺失：\n  " + "\n  ".join(missing))


_CALIBRATION_SHA_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+)$")


def validate_calibration(calibration_list: Path) -> dict[str, Any]:
    """校准清单门禁：40 条真实语音、20 个说话人、评估集完全排除。

    除 manifest 自身的计数/排他约束外，逐条重算 raw 的 SHA-256，并把
    `SHA256SUMS.txt` 里列出的每个文件也重算一遍；任何不一致都拒绝构建
    （返回 `calibration_rejected`，不进入转换）。
    """
    base = Path(calibration_list).parent
    manifest_path = base / CALIBRATION_MANIFEST_NAME
    sums_path = base / CALIBRATION_SUMS_NAME
    if not manifest_path.is_file():
        raise ValueError(f"校准清单缺失：{manifest_path}")
    if not sums_path.is_file():
        raise ValueError(f"校准校验文件缺失：{sums_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"校准清单不可读：{manifest_path}: {exc}") from exc
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != CALIBRATION_RECORDS:
        raise ValueError(
            f"校准清单记录数不符：期望 {CALIBRATION_RECORDS}，"
            f"实际 {len(records) if isinstance(records, list) else '缺失'}"
        )
    speakers = {
        str(record.get("speaker"))
        for record in records
        if isinstance(record, Mapping) and record.get("speaker") is not None
    }
    if len(speakers) != CALIBRATION_SPEAKERS:
        raise ValueError(
            f"校准清单说话人数不符：期望 {CALIBRATION_SPEAKERS}，实际 {len(speakers)}"
        )
    excluded = {
        str(value)
        for value in manifest.get("evaluation_speakers_excluded") or ()
    }
    overlap = sorted(speakers & excluded)
    if overlap:
        raise ValueError(
            f"校准清单与评估集说话人重叠：{', '.join(overlap)}；校准必须完全排除评估集"
        )
    manifest_hashes: dict[Path, str] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("校准清单 records 每条必须是对象")
        raw_value = record.get("raw")
        expected = record.get("raw_sha256")
        if not isinstance(raw_value, str) or not raw_value:
            raise ValueError(f"校准清单记录缺少 raw：{record!r}")
        if not isinstance(expected, str) or not expected:
            raise ValueError(f"校准清单记录缺少 raw_sha256：{raw_value}")
        raw_path = Path(raw_value)
        if not raw_path.is_absolute():
            raw_path = (base / raw_path).resolve()
        if not raw_path.is_file():
            raise ValueError(f"校准 raw 不存在：{raw_path}")
        actual = _sha256(raw_path)
        if actual != expected.lower():
            raise ValueError(
                f"校准 raw SHA-256 不符：{raw_path} 期望 {expected} 实际 {actual}"
            )
        manifest_hashes[raw_path.resolve()] = actual

    sums_entries: dict[Path, str] = {}
    sums_labels: dict[Path, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        match = _CALIBRATION_SHA_LINE_RE.match(line.strip())
        if match is None:
            continue
        label = match.group(2).strip()
        item = Path(label)
        if not item.is_absolute():
            item = base / item
        item = item.resolve()
        sums_entries[item] = match.group(1).lower()
        sums_labels[item] = label
    if not sums_entries:
        raise ValueError(f"SHA256 校验文件为空：{sums_path}")
    for item, expected in sums_entries.items():
        if not item.is_file():
            raise ValueError(
                f"SHA256SUMS.txt 列出的文件不存在：{sums_labels[item]}"
            )
        actual = _sha256(item)
        if actual != expected:
            raise ValueError(
                f"SHA256SUMS.txt 校验失败：{sums_labels[item]} "
                f"期望 {expected} 实际 {actual}"
            )
    # 必须按解析后的完整路径对账，不能只比 basename：同名但不同目录的
    # 文件不能替代 manifest 里登记的那一条。
    for raw_path, actual in manifest_hashes.items():
        recorded = sums_entries.get(raw_path)
        if recorded is None:
            raise ValueError(
                f"manifest 的 raw 未列入 SHA256SUMS.txt：{raw_path}"
            )
        if recorded != actual:
            raise ValueError(
                f"manifest 与 SHA256SUMS.txt 的 raw 哈希不一致：{raw_path}"
            )
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "sums": str(sums_path),
        "sums_sha256": _sha256(sums_path),
        "records": len(records),
        "speakers": len(speakers),
    }


def discover_toolchains(
    roots: tuple[Path, ...] = DEFAULT_QAIRT_ROOTS,
) -> tuple[ToolchainSpec, ...]:
    """枚举本地 QAIRT 树；只收可探测组件同 build 且齐全的候选。

    可探测组件是 `COMPONENT_PATHS` 的 8 项（converter 是 Python 脚本，
    无内嵌版本串，沿用首个探测到的 build ID）；roots 来自
    `DEFAULT_QAIRT_ROOTS` 或显式传入，**不读 `LAOS_QAIRT_ROOT`**——该环境
    变量只由 `device.py` 的设备侧工具链发现使用。
    """
    discovered: list[ToolchainSpec] = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        build_id = ""
        inventory: dict[str, Any] = {"root": str(root.resolve()), "components": {}}
        try:
            for name, relative in COMPONENT_PATHS.items():
                path = root / relative
                if not path.is_file():
                    raise FileNotFoundError(path)
                detected = (
                    build_id if name in SHELL_COMPONENTS and build_id else detect_build_id(path)
                )
                build_id = build_id or detected
                inventory["components"][name] = {
                    "path": str(path.resolve()),
                    "build_id": detected,
                }
        except (FileNotFoundError, ValueError):
            continue
        inventory["build_id"] = build_id
        try:
            discovered.append(ToolchainSpec.from_inventory(inventory))
        except ValueError:
            continue
    return tuple(sorted(discovered, key=lambda spec: spec.build_id))


_QPM_VERSION_RE = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s*$")


def _parse_qpm_versions(output: str) -> list[str]:
    versions: list[str] = []
    in_list = False
    for line in (output or "").splitlines():
        if "Available version" in line:
            in_list = True
            tail = line.split(":", 1)[1] if ":" in line else ""
            candidate = tail.strip()
            if _QPM_VERSION_RE.match(candidate):
                versions.append(candidate)
            continue
        if not in_list:
            continue
        match = _QPM_VERSION_RE.match(line)
        if match is None:
            if line.strip():
                break
            continue
        versions.append(match.group(1))
    return versions


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def probe_qpm_candidates(
    *, product: str = QPM_PRODUCT, timeout: float = 120.0,
    runner: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """查询 QPM 库存；任何失败都显式返回 `unavailable` 与原因，不省略。"""
    command = shutil.which("qpm-cli") or shutil.which("qpm")
    if command is None:
        return {
            "status": "unavailable",
            "reason": "未找到 qpm-cli/qpm 可执行文件",
            "product": product,
        }

    def default_runner(executable: str) -> str:
        completed = subprocess.run(
            [executable, "--info", product],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise subprocess.SubprocessError(
                f"qpm --info {product} exit {completed.returncode}: "
                f"{_tail((completed.stdout or '') + (completed.stderr or ''), 5)}"
            )
        return (completed.stdout or "") + (completed.stderr or "")

    try:
        output = (runner or default_runner)(command)
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "status": "unavailable",
            "reason": f"QPM 查询失败：{exc}",
            "product": product,
            "command": command,
        }
    versions = _parse_qpm_versions(output)
    if not versions:
        return {
            "status": "unavailable",
            "reason": "QPM 输出里没有可解析的版本列表",
            "product": product,
            "command": command,
            "stdout_tail": _tail(output, 10),
        }
    return {
        "status": "available",
        "product": product,
        "command": command,
        "available_versions": versions,
    }


def write_backend_configs(
    directory: Path, variant: BuildVariant
) -> tuple[Path, Path]:
    """写 graph 级 htp 配置与外层 backend_extensions 包装。"""
    extensions = variant.toolchain.net_run_extensions
    if not extensions.is_file():
        raise FileNotFoundError(
            f"HTP backend extension 缺失（QnnHtpNetRunExtensions.dll）：{extensions}"
        )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    graph_path = directory / "htp-graph-config.json"
    wrapper_path = directory / "backend-extensions.json"
    write_json_atomic(
        graph_path,
        {
            "graphs": [
                {
                    "vtcm_mb": variant.vtcm_mb,
                    "graph_names": [variant.graph_name],
                }
            ]
        },
    )
    write_json_atomic(
        wrapper_path,
        {
            "backend_extensions": {
                "shared_library_path": str(extensions),
                "config_file_path": str(graph_path),
            }
        },
    )
    return graph_path, wrapper_path


def build_converter_argv(
    model: Path,
    calibration_list: Path,
    variant: BuildVariant,
    model_dir: Path | None = None,
) -> list[str]:
    """W8A16 转换的真实 argv（真执行与展示共用这一份）。"""
    output_path = (
        (Path(model_dir) / f"{variant.graph_name}.cpp").resolve()
        if model_dir is not None
        else Path(f"{variant.graph_name}.cpp")
    )
    return [
        str(QAIRT_PYTHON),
        str(variant.toolchain.converter),
        "--input_network",
        str(model),
        "--input_list",
        str(calibration_list),
        "--weights_bitwidth",
        "8",
        "--act_bitwidth",
        "16",
        "--output_path",
        str(output_path),
    ]


def build_converter_command(
    model: Path,
    calibration_list: Path,
    variant: BuildVariant,
    model_dir: Path | None = None,
) -> str:
    """W8A16 转换命令的可读形式；唯一真源是 `build_converter_argv`。"""
    return _command(build_converter_argv(model, calibration_list, variant, model_dir))


def build_model_lib_argv(
    cpp: Path, binary: Path, variant: BuildVariant, lib_dir: Path
) -> list[str]:
    return [
        str(QAIRT_PYTHON),
        str(variant.toolchain.model_lib_generator),
        "-c",
        str(cpp),
        "-b",
        str(binary),
        "-t",
        "windows-x86_64",
        "-l",
        variant.graph_name,
        "-o",
        str(lib_dir),
        "--clean_up",
    ]


def build_model_lib_command(
    cpp: Path, binary: Path, variant: BuildVariant, lib_dir: Path
) -> str:
    return _command(build_model_lib_argv(cpp, binary, variant, lib_dir))


def build_context_argv(
    model_lib: Path, context_dir: Path, config_file: Path, variant: BuildVariant
) -> list[str]:
    return [
        str(variant.toolchain.context_generator),
        "--backend",
        str(variant.toolchain.backend_host),
        "--model",
        str(model_lib),
        "--binary_file",
        f"{variant.graph_name}.bin",
        "--output_dir",
        str(context_dir),
        "--config_file",
        str(config_file),
        "--htp_socs",
        "sm8845",
        "--optimization_level_override",
        str(variant.optimization_level),
        "--dlbc_override",
        "true" if variant.dlbc else "false",
    ]


def build_context_command(
    model_lib: Path, context_dir: Path, config_file: Path, variant: BuildVariant
) -> str:
    return _command(build_context_argv(model_lib, context_dir, config_file, variant))


def context_utility_argv(
    context_binary: Path, info_json: Path, toolchain: ToolchainSpec
) -> list[str]:
    return [
        str(toolchain.context_utility),
        "--context_binary",
        str(context_binary),
        "--json_file",
        str(info_json),
        "--unified_qairt_format",
    ]


def read_context_metadata(
    info_json: Path,
    *,
    graph_name: str | None = None,
    expected_build_id: str | None = None,
    expected_input_shape: tuple[int, ...] | None = CAMPLUS_INPUT_SHAPE,
    expected_output_shape: tuple[int, ...] | None = CAMPLUS_OUTPUT_SHAPE,
) -> tuple[ContextMetadata | None, str | None]:
    """读取并门禁 context 元数据；不合格返回 (None, 原因)。"""
    try:
        metadata = load_context_metadata(info_json)
        if expected_build_id is not None and metadata.build_id != expected_build_id:
            raise ValueError(
                "context build ID 与候选 QAIRT 树不一致："
                f"期望 {expected_build_id!r}，实际 {metadata.build_id!r}"
            )
        if graph_name is not None and metadata.graph_name != graph_name:
            raise ValueError(
                f"context graph name 与编译配置不一致："
                f"期望 {graph_name!r}，实际 {metadata.graph_name!r}"
            )
        validate_sm8845_context(
            metadata,
            expected_input_shape=(
                tuple(expected_input_shape)
                if expected_input_shape is not None
                else tuple(metadata.input_shape)
            ),
            expected_output_shape=(
                tuple(expected_output_shape)
                if expected_output_shape is not None
                else tuple(metadata.output_shape)
            ),
        )
    except ValueError as exc:
        return None, f"metadata rejected: {exc}"
    return metadata, None


def config_warning(log_path: Path) -> str | None:
    """context generator exit 0 但配置项未被识别时返回原文行。"""
    path = Path(log_path)
    if not path.is_file():
        return None
    for line in _log_text(path).splitlines():
        if CONFIG_WARNING_MARKER in line:
            return line.strip()
    return None


def _converter_env(toolchain: ToolchainSpec) -> dict[str, str]:
    env = os.environ.copy()
    python_path = str(toolchain.root / "lib/python")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = python_path + (os.pathsep + existing if existing else "")
    return env


def _model_lib_env() -> dict[str, str]:
    env = os.environ.copy()
    if CMAKE_BIN.is_dir():
        env["PATH"] = str(CMAKE_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _run_step(argv: list[str], log_path: Path, *, env: dict[str, str] | None,
              timeout: float, cwd: Path | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            [str(part) for part in argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=env,
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.TimeoutExpired as exc:
        output = f"主机侧等待超时（{exc.timeout}s）：{_command(argv)}"
        log_path.write_text(output + "\n", encoding="utf-8", errors="replace")
        return STEP_TIMEOUT
    except OSError as exc:
        log_path.write_text(f"无法执行：{exc}\n", encoding="utf-8", errors="replace")
        return 1
    except ValueError as exc:
        log_path.write_text(f"命令参数无效：{exc}\n", encoding="utf-8", errors="replace")
        return 1
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    log_path.write_text(output.strip() + "\n", encoding="utf-8", errors="replace")
    return completed.returncode


def _discard_workdir(work_dir: Path) -> None:
    shutil.rmtree(work_dir, ignore_errors=True)


def _promote_artifacts(work_dir: Path, output_dir: Path) -> None:
    """只在构建成功时把中间物原子搬进最终目录。"""
    for name in ("model", "lib", "context"):
        source = work_dir / name
        if not source.exists():
            continue
        target = output_dir / name
        if target.exists():
            shutil.rmtree(target)
        source.replace(target)
    shutil.rmtree(work_dir, ignore_errors=True)


def _write_artifact(output_dir: Path, artifact: BuildArtifact) -> BuildArtifact:
    write_json_atomic(output_dir / "artifact.json", artifact.to_dict())
    return artifact


def _failure(
    variant: BuildVariant,
    output_dir: Path,
    status: str,
    error: str,
    *,
    sha256: Mapping[str, str] | None = None,
    commands: tuple[str, ...] = (),
    warning: str | None = None,
) -> BuildArtifact:
    return _write_artifact(
        output_dir,
        BuildArtifact(
            variant_id=variant.variant_id,
            status=status,
            context_path=None,
            metadata=None,
            sha256=dict(sha256 or {}),
            commands=commands,
            error=error,
            warning=warning,
        ),
    )


def build_w8a16_context(
    model: Path,
    calibration_list: Path,
    variant: BuildVariant,
    output_dir: Path,
    *,
    expected_input_shape: tuple[int, ...] = CAMPLUS_INPUT_SHAPE,
    expected_output_shape: tuple[int, ...] = CAMPLUS_OUTPUT_SHAPE,
    calibration_evidence: Path | None = None,
) -> BuildArtifact:
    """转换 + model DLL + SM8845 context，并做元数据/配置门禁。

    中间物先落 `output_dir/artifacts.tmp/`；只有元数据通过（`ready` 或
    `config_warning`）才原子提升到 `model/lib/context`，失败一律丢弃，
    目录里只剩 `artifact.json`。

    `calibration_evidence` 用于派生输入清单（probe 前缀是真实校准清单的
    副本、后缀是同一批 40 条语音的中间张量）：转换仍读 `calibration_list`，
    但校准门禁校验其来源清单。默认两者相同。
    """
    model = Path(model)
    calibration_list = Path(calibration_list)
    evidence = (
        Path(calibration_evidence) if calibration_evidence is not None else calibration_list
    )
    output_dir = Path(output_dir)
    work_dir = output_dir / "artifacts.tmp"
    model_dir = work_dir / "model"
    lib_dir = work_dir / "lib"
    context_dir = work_dir / "context"
    for stale in (model_dir, lib_dir, context_dir):
        if stale.exists():
            shutil.rmtree(stale)
    for promoted in (output_dir / "model", output_dir / "lib", output_dir / "context"):
        if promoted.exists():
            shutil.rmtree(promoted)
    (output_dir / "artifact.json").unlink(missing_ok=True)
    # 旧版本曾把步骤日志写在变体目录根层，重建时一并清掉。
    (output_dir / "model-lib.log").unlink(missing_ok=True)
    for directory in (model_dir, lib_dir, context_dir):
        directory.mkdir(parents=True)

    if not model.is_file():
        _discard_workdir(work_dir)
        return _failure(variant, output_dir, BUILD_ERROR, f"ONNX 模型不存在：{model}")
    if not calibration_list.is_file():
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR, f"校准列表不存在：{calibration_list}"
        )
    if not evidence.is_file():
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR, f"校准证据清单不存在：{evidence}"
        )
    try:
        require_toolchain_files(variant.toolchain)
    except FileNotFoundError as exc:
        _discard_workdir(work_dir)
        return _failure(variant, output_dir, BUILD_ERROR, str(exc))
    try:
        calibration_summary = validate_calibration(evidence)
    except ValueError as exc:
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_CALIBRATION_REJECTED,
            f"校准清单被拒绝：{exc}",
        )

    base_sha = {
        "model": _sha256(model),
        "calibration_list": _sha256(calibration_list),
        # 校准证据自身也必须进 artifact provenance：清单与校验文件任一
        # 变动都要让 artifact 的 sha256 绑定失效。
        "calibration_manifest": calibration_summary["manifest_sha256"],
        "calibration_sums": calibration_summary["sums_sha256"],
    }
    try:
        graph_config, wrapper = write_backend_configs(context_dir, variant)
    except FileNotFoundError as exc:
        _discard_workdir(work_dir)
        return _failure(variant, output_dir, BUILD_ERROR, str(exc), sha256=base_sha)
    assert graph_config.is_file() and wrapper.is_file()

    converter_argv = build_converter_argv(model, calibration_list, variant, model_dir)
    commands = [_command(converter_argv)]
    code = _run_step(
        converter_argv,
        model_dir / "converter.log",
        env=_converter_env(variant.toolchain),
        timeout=1800,
        cwd=model_dir,
    )
    if code != 0:
        error = (
            f"converter 失败（exit {code}）：\n"
            + _tail(_log_text(model_dir / "converter.log"))
        )
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR, error,
            sha256=base_sha, commands=tuple(commands),
        )
    cpp = model_dir / f"{variant.graph_name}.cpp"
    binary = model_dir / f"{variant.graph_name}.bin"
    if not cpp.is_file() or not binary.is_file():
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"converter 未产出 {cpp.name}/{binary.name}", sha256=base_sha,
            commands=tuple(commands),
        )
    sha = dict(base_sha)
    sha.update({"cpp": _sha256(cpp), "bin": _sha256(binary)})

    model_lib_argv = build_model_lib_argv(
        cpp.resolve(), binary.resolve(), variant, lib_dir.resolve()
    )
    commands.append(_command(model_lib_argv))
    code = _run_step(
        model_lib_argv,
        work_dir / "model-lib.log",
        env=_model_lib_env(),
        timeout=1800,
    )
    libraries = sorted(lib_dir.rglob(f"{variant.graph_name}.dll"))
    if code != 0 or not libraries:
        error = (
            f"model lib 失败（exit {code}）：\n"
            + _tail(_log_text(work_dir / "model-lib.log"))
        )
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR, error,
            sha256=sha, commands=tuple(commands),
        )
    model_lib = libraries[0]
    sha["model_lib"] = _sha256(model_lib)

    context_argv = build_context_argv(
        model_lib.resolve(), context_dir.resolve(), wrapper.resolve(), variant
    )
    commands.append(_command(context_argv))
    code = _run_step(
        context_argv,
        context_dir / "context-generator.log",
        env=None,
        timeout=3600,
    )
    contexts = sorted(context_dir.glob("*.bin"))
    if code != 0 or not contexts:
        error = (
            f"context 生成失败（exit {code}）：\n"
            + _tail(_log_text(context_dir / "context-generator.log"))
        )
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR, error,
            sha256=sha, commands=tuple(commands),
        )
    context_binary = contexts[0]
    sha["context"] = _sha256(context_binary)
    warning = config_warning(context_dir / "context-generator.log")

    info_json = context_dir / "info.json"
    utility_argv = context_utility_argv(
        context_binary.resolve(), info_json.resolve(), variant.toolchain
    )
    commands.append(_command(utility_argv))
    code = _run_step(
        utility_argv,
        context_dir / "context-utility.log",
        env=None,
        timeout=600,
    )
    if code != 0 or not info_json.is_file():
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"context utility 失败（exit {code}）",
            sha256=sha, commands=tuple(commands), warning=warning,
        )

    metadata, metadata_error = read_context_metadata(
        info_json,
        graph_name=variant.graph_name,
        expected_build_id=variant.toolchain.build_id,
        expected_input_shape=expected_input_shape,
        expected_output_shape=expected_output_shape,
    )
    if metadata is None:
        _discard_workdir(work_dir)
        return _failure(
            variant, output_dir, BUILD_METADATA_REJECTED,
            metadata_error or "metadata rejected",
            sha256=sha, commands=tuple(commands), warning=warning,
        )

    _promote_artifacts(work_dir, output_dir)
    promoted_context = output_dir / "context" / context_binary.name
    return _write_artifact(
        output_dir,
        BuildArtifact(
            variant_id=variant.variant_id,
            status=BUILD_CONFIG_WARNING if warning else BUILD_READY,
            context_path=str(promoted_context),
            metadata=metadata,
            sha256=sha,
            commands=tuple(commands),
            error=None,
            warning=warning,
        ),
    )


def compiler_variants(toolchain: ToolchainSpec) -> tuple[BuildVariant, ...]:
    """Stage B 第一档：opt 0..3 × VTCM 4 MB，DLBC 显式关闭。

    VTCM 8 MB 只在 4 MB 档全部失败后作为升级项单独构建（brief Step 5）。
    """
    return tuple(
        BuildVariant(toolchain, level, 4, False, GRAPH_NAME)
        for level in (0, 1, 2, 3)
    )


def compare_contexts(
    reference: BuildArtifact, candidate: BuildArtifact
) -> dict[str, Any]:
    """4 MB vs 8 MB 的 host 侧等价性证明（context sha256 + 元数据回读）。"""
    ref_sha = reference.sha256.get("context")
    cand_sha = candidate.sha256.get("context")
    if not ref_sha or not cand_sha:
        return {
            "status": "unavailable",
            "reason": "缺少一侧 context 哈希，无法判定等价",
            "variants": [reference.variant_id, candidate.variant_id],
        }
    equivalent = ref_sha == cand_sha
    return {
        "status": "equivalent" if equivalent else "distinct",
        "variants": [reference.variant_id, candidate.variant_id],
        "sha256": {reference.variant_id: ref_sha, candidate.variant_id: cand_sha},
        "metadata": {
            reference.variant_id: reference.metadata.to_dict()
            if reference.metadata else None,
            candidate.variant_id: candidate.metadata.to_dict()
            if candidate.metadata else None,
        },
        "reason": (
            "context 二进制逐字节相同 → vtcm_mb 未改变产物，不是独立变量"
            if equivalent
            else "context 二进制不同 → vtcm_mb 可能是独立变量，但仍受配置告警约束"
        ),
    }


def _artifact_from_row(row: Mapping[str, Any]) -> BuildArtifact:
    metadata = row.get("metadata")
    return BuildArtifact(
        variant_id=str(row["variant_id"]),
        status=str(row["status"]),
        context_path=row.get("context"),
        metadata=(
            ContextMetadata.from_dict(metadata) if metadata else None
        ),
        sha256=dict(row.get("sha256") or {}),
        commands=tuple(row.get("commands") or ()),
        error=row.get("error"),
        warning=row.get("warning"),
    )


def _adb_serial_available(serial: str) -> bool:
    try:
        completed = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == serial and parts[1] == "device":
            return True
    return False


def _device_row(serial: str | None, artifact: BuildArtifact,
                num_inferences: int) -> dict[str, Any]:
    """设备不可用时只记录 `device_unavailable`，绝不伪造 DeviceRunResult。"""
    if not serial or not _adb_serial_available(serial):
        return {
            "status": "device_unavailable",
            "reason": "adb 无该序列号的在线设备",
            "device_run": None,
            "stability_run": None,
        }
    from .device import run_context, stability_verdict  # 延迟导入：仅真机路径需要 numpy

    artifact_dir = Path(artifact.context_path or "").parent
    run_dir = artifact_dir.parent / "device-runs"
    result = run_context(
        serial,
        artifact_dir,
        Path(os.environ.get("LAOS_INPUT_LIST", DEFAULT_CALIBRATION)),
        run_dir / "single",
        num_inferences=1,
    )
    row: dict[str, Any] = {
        "status": result.status,
        "device_run": result.to_dict(),
        "stability_run": None,
    }
    if result.status == "pass":
        stability = run_context(
            serial,
            artifact_dir,
            Path(os.environ.get("LAOS_INPUT_LIST", DEFAULT_CALIBRATION)),
            run_dir / "stability",
            num_inferences=num_inferences,
        )
        row["stability_run"] = stability.to_dict()
        row["status"] = stability_verdict(stability, num_inferences)
    return row


def _row(stage: str, kind: str, artifact: BuildArtifact) -> dict[str, Any]:
    return {
        "stage": stage,
        "kind": kind,
        "variant_id": artifact.variant_id,
        "status": artifact.status,
        "context": artifact.context_path,
        "metadata": artifact.metadata.to_dict() if artifact.metadata else None,
        "sha256": dict(artifact.sha256),
        "commands": list(artifact.commands),
        "error": artifact.error,
        "warning": artifact.warning,
        "device_run": None,
        "stability_run": None,
    }


def _qpm_record(
    roots: tuple[Path, ...], toolchains: tuple[ToolchainSpec, ...],
    probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """把 QPM 库存与本地树对齐；没有可用更新树就显式 `unavailable`。"""
    record = dict(probe) if probe is not None else probe_qpm_candidates()
    local = [spec.build_id.lstrip("v") for spec in toolchains]
    record["local_build_ids"] = [spec.build_id for spec in toolchains]
    record["local_roots"] = [str(root) for root in roots]
    versions = list(record.get("available_versions") or [])
    installed = [
        version for version in versions
        if any(spec.build_id.startswith("v" + version) for spec in toolchains)
    ]
    if installed:
        record["installed_versions"] = installed
    if versions and local:
        newest_local = max(_version_key(version) for version in local)
        newer = sorted(
            (version for version in versions
             if _version_key(version) > newest_local and version not in installed),
            key=_version_key,
            reverse=True,
        )
        record["newer_than_local"] = newer
    else:
        record.setdefault("newer_than_local", [])
    if record.get("status") != "unavailable":
        newer = record.get("newer_than_local") or []
        if newer:
            record["status"] = "unavailable"
            record["reason"] = (
                "QPM 有更新的 QAIRT（"
                + ", ".join(newer)
                + "），但未下载安装（需 license 与重资产下载），"
                "Stage A 无可用更新树"
            )
        elif installed:
            record["status"] = "installed"
            record["reason"] = (
                "QPM 列表中的 QAIRT 已下载并纳入本地矩阵："
                + ", ".join(installed)
            )
        else:
            record["status"] = "unavailable"
            record["reason"] = "QPM 库存里没有比本地更新的 QAIRT 版本"
    return record


def run_matrix(
    stage: str,
    *,
    model: Path = DEFAULT_MODEL,
    calibration_list: Path = DEFAULT_CALIBRATION,
    output_root: Path = DEBUG_ROOT,
    serial: str | None = None,
    num_inferences: int = 30,
    roots: tuple[Path, ...] = DEFAULT_QAIRT_ROOTS,
    qpm_probe: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """执行 Stage A（版本）或 Stage B（编译配置）；完整图变体上限 10。"""
    if stage not in ("toolchain", "compiler", "all"):
        raise ValueError(f"未知 stage：{stage}")
    output_root = Path(output_root)
    builds = output_root / "builds"
    toolchains = discover_toolchains(roots)
    for spec in toolchains:
        inventory_path = output_root / "toolchains" / spec.build_id / "inventory.json"
        write_json_atomic(inventory_path, spec.inventory())

    rows: list[dict[str, Any]] = []
    built: set[str] = set()
    device_available = bool(serial and _adb_serial_available(serial))
    full_variant_ids: set[str] = set()
    recorded: dict[str, dict[str, Any]] = {}
    existing_matrix = output_root / "matrix.json"
    if existing_matrix.is_file():
        try:
            previous_matrix = json.loads(existing_matrix.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_matrix = {}
        recorded = {
            row["variant_id"]: row for row in previous_matrix.get("variants", [])
        }
        full_variant_ids.update(
            variant_id
            for variant_id, row in recorded.items()
            if row.get("kind") == "full"
        )

    # 版本资格：tiny smoke context 的元数据是唯一可信证据。
    eligible: list[ToolchainSpec] = []
    for spec in toolchains:
        smoke_variant = BuildVariant(spec, 2, 4, False, SMOKE_GRAPH_NAME)
        smoke_artifact = build_w8a16_context(
            SMOKE_MODEL,
            SMOKE_CALIBRATION,
            smoke_variant,
            builds / f"{smoke_variant.variant_id}",
            expected_input_shape=SMOKE_INPUT_SHAPE,
            expected_output_shape=SMOKE_OUTPUT_SHAPE,
        )
        rows.append(_row("eligibility", "smoke", smoke_artifact))
        if smoke_artifact.status in (BUILD_READY, BUILD_CONFIG_WARNING):
            eligible.append(spec)

    def build_full(
        variant: BuildVariant, *, allow_device: bool, stage_label: str
    ) -> dict[str, Any]:
        if variant.variant_id not in full_variant_ids:
            if len(full_variant_ids) >= MAX_FULL_GRAPH_VARIANTS:
                raise ValueError(
                    f"完整图变体超过上限 {MAX_FULL_GRAPH_VARIANTS}，拒绝继续扩展"
                )
            full_variant_ids.add(variant.variant_id)
        built.add(variant.variant_id)
        artifact = build_w8a16_context(
            model, calibration_list, variant, builds / variant.variant_id
        )
        row = _row(stage_label, "full", artifact)
        if artifact.status == BUILD_READY and allow_device:
            row.update(_device_row(serial, artifact, num_inferences))
        elif artifact.status == BUILD_READY:
            row.update({
                "status": "device_unavailable",
                "reason": "未请求真机执行",
                "device_run": None,
                "stability_run": None,
            })
        elif artifact.status == BUILD_CONFIG_WARNING:
            row.update({
                "status": BUILD_CONFIG_WARNING,
                "reason": (
                    "context 配置告警未闭环，未上机："
                    f"{artifact.warning or CONFIG_WARNING_MARKER}"
                ),
                "device_run": None,
                "stability_run": None,
            })
        return row

    if stage in ("toolchain", "all"):
        for spec in eligible:
            row = build_full(
                BuildVariant(spec, 2, 4, False, GRAPH_NAME),
                allow_device=True,
                stage_label="toolchain",
            )
            rows.append(row)
            if row["status"] == "pass":
                break

    stage_a_passed = any(row["status"] == "pass" for row in rows)
    run_compiler = stage == "compiler" or (stage == "all" and not stage_a_passed)
    reference = recorded.get(
        f"{eligible[-1].short_version}-opt2-vtcm4-dlbc0-{GRAPH_NAME}"
    ) if eligible else None
    attempted: list[tuple[BuildVariant, dict[str, Any]]] = []
    if run_compiler and eligible:
        newest = eligible[-1]
        for variant in compiler_variants(newest):
            previous = recorded.get(variant.variant_id)
            # 已记录的变体不重复构建；但设备回来后要补跑 device_unavailable 的行。
            stale_pending = (
                previous is not None
                and previous.get("status") == "device_unavailable"
                and device_available
            )
            if variant.variant_id in built or (
                previous is not None
                and previous.get("status") != BUILD_ERROR
                and not stale_pending
            ):
                continue
            row = build_full(variant, allow_device=True, stage_label="compiler")
            rows.append(row)
            attempted.append((variant, row))
        if reference is None:
            reference = next(
                (
                    row for _, row in attempted
                    if row["variant_id"].endswith(f"opt2-vtcm4-dlbc0-{GRAPH_NAME}")
                ),
                None,
            )

    # host 侧等价性证明：4 MB 参考变体 vs 同 opt 的 8 MB 变体。必须先于
    # 升级判定：VTCM 未证明会改变 context 二进制前，它不是独立变量。
    vtcm_equivalence: dict[str, Any] = {
        "status": "not_probed",
        "reason": "缺少 4 MB 参考 context，无法做等价性证明",
    }
    if run_compiler and eligible and reference is not None:
        probe_variant = BuildVariant(eligible[-1], 2, 8, False, GRAPH_NAME)
        probe_dir = output_root / "probes" / f"vtcm-equivalence-{probe_variant.variant_id}"
        recorded_probe = probe_dir / "artifact.json"
        if recorded_probe.is_file():
            try:
                probe_artifact = _artifact_from_row(
                    json.loads(recorded_probe.read_text(encoding="utf-8"))
                )
            except (OSError, json.JSONDecodeError, KeyError):
                probe_artifact = build_w8a16_context(
                    model, calibration_list, probe_variant, probe_dir
                )
        else:
            probe_artifact = build_w8a16_context(
                model, calibration_list, probe_variant, probe_dir
            )
        vtcm_equivalence = compare_contexts(
            _artifact_from_row(reference), probe_artifact
        )
        vtcm_equivalence["probe_dir"] = str(probe_dir)
        vtcm_equivalence["probe_warning"] = probe_artifact.warning
        vtcm_equivalence["probe_status"] = probe_artifact.status

    # VTCM 升级判定：4 MB 档"全部失败"且等价性证明为 distinct 才升级。
    baseline_ids = (
        {variant.variant_id for variant in compiler_variants(eligible[-1])}
        if eligible else set()
    )
    baseline_rows = [row for row in rows if row["variant_id"] in baseline_ids]
    known_failures = [
        recorded.get(variant_id) for variant_id in baseline_ids - built
    ]
    known_failures = [row for row in known_failures if row is not None]
    evaluated = baseline_rows + known_failures
    four_mb_failed = bool(evaluated) and all(
        row["status"] in FAILURE_STATUSES for row in evaluated
    ) and len(evaluated) >= len(baseline_ids)
    vtcm_escalation: dict[str, Any] = {
        "status": "skipped",
        "reason": "4 MB 档尚未取得全部失败证据（含 device_unavailable / config_warning）",
    }
    if run_compiler and eligible and four_mb_failed:
        escalation = BuildVariant(eligible[-1], 2, 8, False, GRAPH_NAME)
        if vtcm_equivalence.get("status") != "distinct":
            vtcm_escalation = {
                "status": "skipped",
                "reason": (
                    "4 MB→8 MB 未证明会改变 context 二进制（等价性 "
                    f"{vtcm_equivalence.get('status')}），VTCM 不是独立变量"
                ),
            }
        elif escalation.variant_id in built:
            vtcm_escalation = {
                "status": "already_recorded",
                "variant_id": escalation.variant_id,
            }
        else:
            rows.append(build_full(escalation, allow_device=True, stage_label="compiler"))
            vtcm_escalation = {
                "status": "built",
                "variant_id": escalation.variant_id,
            }
    elif not run_compiler:
        vtcm_escalation = {"status": "skipped", "reason": "未进入编译配置矩阵"}

    merge_path = output_root / "matrix.json"
    merged: dict[str, dict[str, Any]] = {}
    stages: list[str] = []
    if merge_path.is_file():
        try:
            previous = json.loads(merge_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        merged.update(
            {row["variant_id"]: row for row in previous.get("variants", [])}
        )
        stages.extend(previous.get("stages") or [])
        if previous.get("stage"):
            stages.append(previous["stage"])
    merged.update({row["variant_id"]: row for row in rows})
    if stage not in stages:
        stages.append(stage)
    stages = list(dict.fromkeys(stages))

    merged_rows = sorted(merged.values(), key=lambda row: row["variant_id"])
    # 同一 context 二进制只算一个独立变体：后出现的标 equivalent_to。
    canonical: dict[str, str] = {}
    for row in merged_rows:
        if row.get("kind") != "full":
            continue
        digest = (row.get("sha256") or {}).get("context")
        row.pop("equivalent_to", None)
        if not digest:
            continue
        if digest in canonical:
            row["equivalent_to"] = canonical[digest]
        else:
            canonical[digest] = row["variant_id"]

    statuses: dict[str, int] = {}
    for row in merged_rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    full_rows = [row for row in merged_rows if row["kind"] == "full"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stage": stage,
        "stages": stages,
        "model": {"path": str(model), "sha256": _sha256(Path(model))}
        if Path(model).is_file() else {"path": str(model), "sha256": None},
        "calibration_list": {
            "path": str(calibration_list),
            "sha256": _sha256(Path(calibration_list))
            if Path(calibration_list).is_file() else None,
            "entries": sum(
                1
                for line in Path(calibration_list).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            ) if Path(calibration_list).is_file() else 0,
        },
        "device": {"serial": serial, "available": device_available},
        "qpm": _qpm_record(roots, toolchains, qpm_probe),
        "toolchains": [
            {"build_id": spec.build_id, "root": str(spec.root)} for spec in toolchains
        ],
        "vtcm_equivalence": vtcm_equivalence,
        "vtcm_escalation": vtcm_escalation,
        "variants": merged_rows,
        "summary": {
            "full_graph_variants": len(canonical),
            "full_graph_rows": len(full_rows),
            "max_full_graph_variants": MAX_FULL_GRAPH_VARIANTS,
            "statuses": statuses,
            "stage_a_passed": any(
                row["status"] == "pass" and row["kind"] == "full"
                for row in merged_rows
            ),
        },
    }
    write_json_atomic(merge_path, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("inventory", help="列出同 build 的 QAIRT 候选")

    matrix = subcommands.add_parser("matrix", help="执行受限构建矩阵")
    matrix.add_argument("--stage", choices=("toolchain", "compiler", "all"),
                        required=True)
    matrix.add_argument("--model", default=str(DEFAULT_MODEL))
    matrix.add_argument("--calibration-list", default=str(DEFAULT_CALIBRATION))
    matrix.add_argument("--output-root", default=str(DEBUG_ROOT))
    matrix.add_argument("--serial")
    matrix.add_argument("--num-inferences", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "inventory":
        for spec in discover_toolchains():
            print(
                f"{spec.build_id}  root={spec.root}  "
                f"net-run-extensions={spec.net_run_extensions.is_file()}"
            )
        print(json.dumps(probe_qpm_candidates(), ensure_ascii=False, sort_keys=True))
        return 0
    payload = run_matrix(
        arguments.stage,
        model=Path(arguments.model),
        calibration_list=Path(arguments.calibration_list),
        output_root=Path(arguments.output_root),
        serial=arguments.serial,
        num_inferences=arguments.num_inferences,
    )
    for row in payload["variants"]:
        print(f"{row['status']:>18}  {row['kind']:>4}  {row['variant_id']}")
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    print(json.dumps(payload["qpm"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
