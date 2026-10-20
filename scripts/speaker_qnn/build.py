"""SM8845/HTP V81 的受限 QNN 构建矩阵。

设计口径（与 2026-10-20 故障基线绑定）：

- 每个候选 QAIRT 树先建一个 `y=x+1` smoke context，只有元数据实测为
  `socModel=87`、`dspArch=81` 才算合格；2.47 之类的静默回退
  （实测 `socModel=0`、`dspArch=81`）只作为被拒绝的反例，绝不进入 CAM++ 构建；
- 转换固定 W8A16（`--weights_bitwidth 8`、`--act_bitwidth 16`）并使用
  40 条真实语音校准列表；每次构建记录 converter / model-lib / context
  三条完整命令与产物 SHA-256；
- context 必须恰好一个 graph，且 graph 名与 build variant 一致；不满足即
  `metadata_rejected`，不推送设备；
- 完整图变体总数硬上限 10，Stage B 只在 Stage A 没有通过时展开。

    python -m scripts.speaker_qnn.build inventory
    python -m scripts.speaker_qnn.build matrix --stage toolchain
    python -m scripts.speaker_qnn.build matrix --stage compiler
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

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

DEFAULT_QAIRT_ROOTS: tuple[Path, ...] = (
    QNN_ROOT / "sdk/qairt/2.47.0.260601",
    QNN_ROOT / "sdk-2.51/qairt/2.51.1.261002",
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
}
SHELL_COMPONENTS = frozenset({"converter"})  # Python 脚本无内嵌 build ID

BUILD_READY = "ready"
BUILD_METADATA_REJECTED = "metadata_rejected"
BUILD_ERROR = "build_error"
# 只有这些状态算失败；device_unavailable 是"未验证"，不构成升级 VTCM 的理由。
FAILURE_STATUSES = frozenset(
    {"build_error", "metadata_rejected", "load_error", "timeout", "ssr"}
)


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "status": self.status,
            "context_path": self.context_path,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "sha256": dict(self.sha256),
            "commands": list(self.commands),
            "error": self.error,
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command(argv: list[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in argv])


def _tail(text: str, lines: int = 20) -> str:
    return "\n".join((text or "").strip().splitlines()[-lines:])


def require_toolchain_files(toolchain: ToolchainSpec) -> None:
    """同一 build 的全部必需文件必须在位，缺一即拒绝构建。"""
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
    }
    missing = [
        f"{label}: {path}"
        for label, path in paths.items()
        if not Path(path).is_file()
    ]
    if missing:
        raise FileNotFoundError("QAIRT 文件缺失：\n  " + "\n  ".join(missing))


def discover_toolchains(
    roots: tuple[Path, ...] = DEFAULT_QAIRT_ROOTS,
) -> tuple[ToolchainSpec, ...]:
    """枚举本地 QAIRT 树；只收同 build 且组件齐全的候选。"""
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


def build_converter_command(
    model: Path,
    calibration_list: Path,
    variant: BuildVariant,
    model_dir: Path | None = None,
) -> str:
    """W8A16 转换命令；per-tensor 量化 + 真实语音校准列表。"""
    output_path = (
        (Path(model_dir) / f"{variant.graph_name}.cpp").resolve()
        if model_dir is not None
        else Path(f"{variant.graph_name}.cpp")
    )
    return _command(
        [
            QAIRT_PYTHON,
            variant.toolchain.converter,
            "--input_network",
            model,
            "--input_list",
            calibration_list,
            "--weights_bitwidth",
            "8",
            "--act_bitwidth",
            "16",
            "--output_path",
            output_path,
        ]
    )


def build_model_lib_command(
    cpp: Path, binary: Path, variant: BuildVariant, lib_dir: Path
) -> str:
    return _command(
        [
            QAIRT_PYTHON,
            variant.toolchain.model_lib_generator,
            "-c",
            cpp,
            "-b",
            binary,
            "-t",
            "windows-x86_64",
            "-l",
            variant.graph_name,
            "-o",
            lib_dir,
            "--clean_up",
        ]
    )


def build_context_command(
    model_lib: Path, context_dir: Path, config_file: Path, variant: BuildVariant
) -> str:
    return _command(
        [
            variant.toolchain.context_generator,
            "--backend",
            variant.toolchain.backend_host,
            "--model",
            model_lib,
            "--binary_file",
            f"{variant.graph_name}.bin",
            "--output_dir",
            context_dir,
            "--config_file",
            config_file,
            "--htp_socs",
            "sm8845",
            "--optimization_level_override",
            str(variant.optimization_level),
            "--dlbc_override",
            "true" if variant.dlbc else "false",
        ]
    )


def _context_utility_command(
    context_binary: Path, info_json: Path, toolchain: ToolchainSpec
) -> str:
    return _command(
        [
            toolchain.context_utility,
            "--context_binary",
            context_binary,
            "--json_file",
            info_json,
            "--unified_qairt_format",
        ]
    )


def read_context_metadata(
    info_json: Path,
    *,
    graph_name: str | None = None,
    expected_input_shape: tuple[int, ...] | None = CAMPLUS_INPUT_SHAPE,
    expected_output_shape: tuple[int, ...] | None = CAMPLUS_OUTPUT_SHAPE,
) -> tuple[ContextMetadata | None, str | None]:
    """读取并门禁 context 元数据；不合格返回 (None, 原因)。"""
    try:
        metadata = load_context_metadata(info_json)
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
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    log_path.write_text(output.strip() + "\n", encoding="utf-8", errors="replace")
    return completed.returncode


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
) -> BuildArtifact:
    """转换 + model DLL + SM8845 context，并做元数据门禁。

    任何一步失败都写 `artifact.json`（`build_error`）并返回，不保留 context；
    元数据回退/图形不符写 `metadata_rejected`。
    """
    model = Path(model)
    calibration_list = Path(calibration_list)
    output_dir = Path(output_dir)
    model_dir = output_dir / "model"
    lib_dir = output_dir / "lib"
    context_dir = output_dir / "context"
    for directory in (model_dir, lib_dir, context_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    (output_dir / "artifact.json").unlink(missing_ok=True)

    if not model.is_file():
        return _failure(variant, output_dir, BUILD_ERROR, f"ONNX 模型不存在：{model}")
    if not calibration_list.is_file():
        return _failure(
            variant, output_dir, BUILD_ERROR, f"校准列表不存在：{calibration_list}"
        )
    try:
        require_toolchain_files(variant.toolchain)
    except FileNotFoundError as exc:
        return _failure(variant, output_dir, BUILD_ERROR, str(exc))

    base_sha = {
        "model": _sha256(model),
        "calibration_list": _sha256(calibration_list),
    }
    try:
        graph_config, wrapper = write_backend_configs(context_dir, variant)
    except FileNotFoundError as exc:
        return _failure(variant, output_dir, BUILD_ERROR, str(exc), sha256=base_sha)
    assert graph_config.is_file() and wrapper.is_file()

    converter_command = build_converter_command(
        model, calibration_list, variant, model_dir
    )
    commands = [converter_command]
    code = _run_step(
        [
            str(QAIRT_PYTHON),
            str(variant.toolchain.converter),
            "--input_network", str(model),
            "--input_list", str(calibration_list),
            "--weights_bitwidth", "8",
            "--act_bitwidth", "16",
            "--output_path", str((model_dir / f"{variant.graph_name}.cpp").resolve()),
        ],
        model_dir / "converter.log",
        env=_converter_env(variant.toolchain),
        timeout=1800,
        cwd=model_dir,
    )
    if code != 0:
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"converter 失败（exit {code}）：\n"
            + _tail((model_dir / "converter.log").read_text(encoding="utf-8", errors="replace")),
            sha256=base_sha, commands=tuple(commands),
        )
    cpp = model_dir / f"{variant.graph_name}.cpp"
    binary = model_dir / f"{variant.graph_name}.bin"
    if not cpp.is_file() or not binary.is_file():
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"converter 未产出 {cpp.name}/{binary.name}", sha256=base_sha,
            commands=tuple(commands),
        )
    sha = dict(base_sha)
    sha.update({"cpp": _sha256(cpp), "bin": _sha256(binary)})

    model_lib_command = build_model_lib_command(
        cpp.resolve(), binary.resolve(), variant, lib_dir.resolve()
    )
    commands.append(model_lib_command)
    code = _run_step(
        [
            str(QAIRT_PYTHON),
            str(variant.toolchain.model_lib_generator),
            "-c", str(cpp.resolve()),
            "-b", str(binary.resolve()),
            "-t", "windows-x86_64",
            "-l", variant.graph_name,
            "-o", str(lib_dir.resolve()),
            "--clean_up",
        ],
        output_dir / "model-lib.log",
        env=_model_lib_env(),
        timeout=1800,
    )
    libraries = sorted(lib_dir.rglob(f"{variant.graph_name}.dll"))
    if code != 0 or not libraries:
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"model lib 失败（exit {code}）：\n"
            + _tail((output_dir / "model-lib.log").read_text(encoding="utf-8", errors="replace")),
            sha256=sha, commands=tuple(commands),
        )
    model_lib = libraries[0]
    sha["model_lib"] = _sha256(model_lib)

    context_command = build_context_command(
        model_lib.resolve(), context_dir.resolve(), wrapper.resolve(), variant
    )
    commands.append(context_command)
    code = _run_step(
        [
            str(variant.toolchain.context_generator),
            "--backend", str(variant.toolchain.backend_host),
            "--model", str(model_lib.resolve()),
            "--binary_file", f"{variant.graph_name}.bin",
            "--output_dir", str(context_dir.resolve()),
            "--config_file", str(wrapper.resolve()),
            "--htp_socs", "sm8845",
            "--optimization_level_override", str(variant.optimization_level),
            "--dlbc_override", "true" if variant.dlbc else "false",
        ],
        context_dir / "context-generator.log",
        env=None,
        timeout=3600,
    )
    contexts = sorted(context_dir.glob("*.bin"))
    if code != 0 or not contexts:
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"context 生成失败（exit {code}）：\n"
            + _tail((context_dir / "context-generator.log").read_text(
                encoding="utf-8", errors="replace")),
            sha256=sha, commands=tuple(commands),
        )
    context_binary = contexts[0]
    sha["context"] = _sha256(context_binary)

    info_json = context_dir / "info.json"
    utility_command = _context_utility_command(
        context_binary.resolve(), info_json.resolve(), variant.toolchain
    )
    commands.append(utility_command)
    code = _run_step(
        [
            str(variant.toolchain.context_utility),
            "--context_binary", str(context_binary.resolve()),
            "--json_file", str(info_json.resolve()),
            "--unified_qairt_format",
        ],
        context_dir / "context-utility.log",
        env=None,
        timeout=600,
    )
    if code != 0 or not info_json.is_file():
        return _failure(
            variant, output_dir, BUILD_ERROR,
            f"context utility 失败（exit {code}）", sha256=sha, commands=tuple(commands),
        )

    metadata, error = read_context_metadata(
        info_json,
        graph_name=variant.graph_name,
        expected_input_shape=expected_input_shape,
        expected_output_shape=expected_output_shape,
    )
    if metadata is None:
        return _failure(
            variant, output_dir, BUILD_METADATA_REJECTED, error or "metadata rejected",
            sha256=sha, commands=tuple(commands),
        )

    return _write_artifact(
        output_dir,
        BuildArtifact(
            variant_id=variant.variant_id,
            status=BUILD_READY,
            context_path=str(context_binary),
            metadata=metadata,
            sha256=sha,
            commands=tuple(commands),
            error=None,
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
    from .device import run_context  # 延迟导入：仅真机路径需要 numpy

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
        row["status"] = "pass" if stability.status == "pass" else stability.status
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
        "device_run": None,
        "stability_run": None,
    }


def run_matrix(
    stage: str,
    *,
    model: Path = DEFAULT_MODEL,
    calibration_list: Path = DEFAULT_CALIBRATION,
    output_root: Path = DEBUG_ROOT,
    serial: str | None = None,
    num_inferences: int = 30,
    roots: tuple[Path, ...] = DEFAULT_QAIRT_ROOTS,
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
        if smoke_artifact.status == BUILD_READY:
            eligible.append(spec)

    def build_full(variant: BuildVariant, *, allow_device: bool) -> dict[str, Any]:
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
        row = _row("compiler" if variant.optimization_level != 2 or variant.vtcm_mb != 4
                   else "toolchain", "full", artifact)
        if artifact.status == BUILD_READY and allow_device:
            row.update(_device_row(serial, artifact, num_inferences))
        elif artifact.status == BUILD_READY:
            row.update({
                "status": "device_unavailable",
                "reason": "未请求真机执行",
                "device_run": None,
                "stability_run": None,
            })
        return row

    if stage in ("toolchain", "all"):
        for spec in eligible:
            row = build_full(BuildVariant(spec, 2, 4, False, GRAPH_NAME), allow_device=True)
            rows.append(row)
            if row["status"] == "pass":
                break

    stage_a_passed = any(row["status"] == "pass" for row in rows)
    run_compiler = stage == "compiler" or (stage == "all" and not stage_a_passed)
    if run_compiler and eligible:
        newest = eligible[-1]
        attempted: list[tuple[BuildVariant, dict[str, Any]]] = []
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
            row = build_full(variant, allow_device=True)
            rows.append(row)
            attempted.append((variant, row))
        # brief Step 5：只有 4 MB 档全部失败，才为进度最多的变体升级 VTCM 8 MB。
        if attempted and all(row["status"] in FAILURE_STATUSES for _, row in attempted):
            best, _ = max(
                attempted,
                key=lambda pair: (len(pair[1]["sha256"]), -pair[0].optimization_level),
            )
            rows.append(
                build_full(
                    BuildVariant(newest, best.optimization_level, 8, False, GRAPH_NAME),
                    allow_device=True,
                )
            )

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
    for row in rows:
        merged[row["variant_id"]] = row
    if stage not in stages:
        stages.append(stage)
    stages = list(dict.fromkeys(stages))

    merged_rows = sorted(merged.values(), key=lambda row: row["variant_id"])
    statuses: dict[str, int] = {}
    for row in merged_rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
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
        "toolchains": [
            {"build_id": spec.build_id, "root": str(spec.root)} for spec in toolchains
        ],
        "variants": merged_rows,
        "summary": {
            "full_graph_variants": sum(
                1 for row in merged_rows if row["kind"] == "full"
            ),
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
