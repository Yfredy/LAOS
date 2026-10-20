"""SM8845/HTP V81 真机执行契约：ADB 部署、同 build 校验、运行与归类。

设计口径（与 2026-10-20 故障基线绑定）：

- 每次运行创建唯一远端目录，runner / libQnnHtp.so / V81 stub / V81 skel /
  libQnnSystem.so / context 全部来自同一个 QAIRT build，并在推送后逐文件
  校验远端 SHA-256；
- 绝不写 `vendor.fastrpc.process.rpctimeout`，也不向 qnn-net-run 传
  `--timeout`——10 秒看门狗是安全边界，CAM++ 的 timeout 就是要留下的证据；
- 本地 stdout/logcat/profile/output/result.json 统一落到调用方给的 run 目录，
  由 `classify_device_run` 判定 `pass/timeout/ssr/...`；`pass` 之外都不是
  速度值。

    python -m scripts.speaker_qnn.device smoke --serial 327366100004
    python -m scripts.speaker_qnn.device run --artifact <dir> --serial ... --num-inferences 1
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .contracts import (
    CAMPLUS_INPUT_SHAPE,
    CAMPLUS_OUTPUT_SHAPE,
    DeviceRunResult,
    classify_device_run,
    load_context_metadata,
    parse_profile_timings,
    validate_sm8845_context,
    write_json_atomic,
)

try:  # 主库 discover 环境没有 numpy；只有真机运行时才需要
    import numpy as np
except ImportError:  # pragma: no cover - 由 read_output 给出明确错误
    np = None  # type: ignore[assignment]

REPO = Path(__file__).resolve().parents[2]
DEBUG_ROOT = REPO / "var/speaker-benchmark/qnn/campplus-htp-debug"
DEFAULT_TOOLCHAIN = REPO / "var/speaker-benchmark/qnn/sdk-2.51/qairt/2.51.1.261002"
SMOKE_ARTIFACT = REPO / "var/speaker-benchmark/qnn/htp-smoke/context-valid"
REMOTE_ROOT = "/data/local/tmp/nanolaos-qnn"

# adsprpc 在 `<进程名>.farf` 里读 DSP 侧 FARF 日志掩码；缺省只开 ERROR
# （mask 8），DSP 的 `gpe_execute_novalidate` 与 FastRPC "Intentional crash
# ... timeout: 10000" 都不会进 logcat；0x1F = DEBUG..FATAL。
FARF_CONFIG_NAME = "qnn-net-run.farf"
FARF_CONFIG_MASK = "0x1F"
# 真实搜索串（logcat `log_config.c:449`）：
# `at ;/vendor/lib64/rfs/dsp;/vendor/lib/rfsa/adsp;/vendor/lib/rfsa/dsp;/vendor/dsp;`
# 首项空串即进程 cwd；/vendor 只读，所以唯一可写落点是运行目录本身，并把
# 该目录显式并入 ADSP_LIBRARY_PATH 的复合搜索路径。
ADSP_SEARCH_ROOTS: tuple[str, ...] = (
    "/vendor/lib64/rfs/dsp",
    "/vendor/lib/rfsa/adsp",
    "/vendor/lib/rfsa/dsp",
    "/vendor/dsp",
)

# (相对 QAIRT root, 远端文件名)；顺序即推送顺序。
TOOLCHAIN_LAYOUT: tuple[tuple[str, str], ...] = (
    ("bin/aarch64-android/qnn-net-run", "qnn-net-run"),
    ("lib/aarch64-android/libQnnHtp.so", "libQnnHtp.so"),
    ("lib/aarch64-android/libQnnHtpV81Stub.so", "libQnnHtpV81Stub.so"),
    ("lib/aarch64-android/libQnnSystem.so", "libQnnSystem.so"),
    ("lib/hexagon-v81/unsigned/libQnnHtpV81Skel.so", "libQnnHtpV81Skel.so"),
)
# libQnnSystem.so 不内嵌版本串（2.51.1 实测），只能靠"同一 QAIRT root 内"
# 约束；其余四件必须逐字节版本一致。
TOOLCHAIN_VERSIONED = frozenset(
    {"qnn-net-run", "libQnnHtp.so", "libQnnHtpV81Stub.so", "libQnnHtpV81Skel.so"}
)

_BUILD_ID_RE = re.compile(rb"v\d+\.\d+\.\d+\.\d{6,}")
_SHA256_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+)$")


@dataclass(frozen=True)
class QairtToolchain:
    """一套同 build 的 QAIRT 设备侧文件。"""

    root: Path
    build_id: str

    def paths(self) -> tuple[tuple[Path, str], ...]:
        return tuple((self.root / relative, name) for relative, name in TOOLCHAIN_LAYOUT)


def detect_build_id(path: Path) -> str:
    """从二进制内嵌的版本串读出 QAIRT build ID（无需在设备上执行）。"""
    path = Path(path)
    matches = _BUILD_ID_RE.findall(path.read_bytes())
    if not matches:
        raise ValueError(f"无法从 {path} 读取 QAIRT build ID")
    return max(matches, key=len).decode("ascii")


def require_same_build_id(expected: str, actual_by_name: dict[str, str]) -> None:
    """同一运行的所有组件必须共享 build ID；混合版本直接拒绝。"""
    mismatched = {
        name: build_id
        for name, build_id in actual_by_name.items()
        if build_id != expected
    }
    if mismatched:
        detail = ", ".join(f"{name}={build_id}" for name, build_id in sorted(mismatched.items()))
        raise ValueError(f"QAIRT build ID 不一致：期望 {expected}，实际 {detail}")


def discover_toolchain(root: Path | None = None) -> QairtToolchain:
    """定位本地 QAIRT 树；`LAOS_QAIRT_ROOT` 可覆盖默认路径。"""
    candidate = Path(root or os.environ.get("LAOS_QAIRT_ROOT") or DEFAULT_TOOLCHAIN)
    missing = [str(candidate / relative) for relative, _ in TOOLCHAIN_LAYOUT
               if not (candidate / relative).is_file()]
    if missing:
        raise FileNotFoundError(
            "QAIRT 设备文件缺失：\n  " + "\n  ".join(missing)
        )
    toolchain = QairtToolchain(root=candidate.resolve(), build_id="")
    build_id = detect_build_id(toolchain.paths()[0][0])
    return QairtToolchain(root=toolchain.root, build_id=build_id)


def verify_toolchain(toolchain: QairtToolchain, context_build_id: str) -> None:
    """context + runner + backend/stub/skel 必须同一 build。"""
    detected = {"context": context_build_id}
    for path, name in toolchain.paths():
        if name in TOOLCHAIN_VERSIONED:
            detected[name] = detect_build_id(path)
    require_same_build_id(toolchain.build_id, detected)


def find_context_files(artifact_dir: Path) -> tuple[Path, Path]:
    """在 artifact 目录里定位唯一一份 info.json + context .bin。"""
    artifact_dir = Path(artifact_dir)
    info = artifact_dir / "info.json"
    if not info.is_file():
        infos = sorted(artifact_dir.rglob("info.json"))
        if len(infos) != 1:
            raise FileNotFoundError(
                f"{artifact_dir} 下应有且仅有一份 info.json，实际 {len(infos)} 份"
            )
        info = infos[0]
    contexts = sorted(info.parent.glob("*.bin"))
    if len(contexts) != 1:
        raise FileNotFoundError(
            f"{info.parent} 下应有且仅有一个 context .bin，实际 {len(contexts)} 个"
        )
    return info, contexts[0]


def parse_input_list(path: Path) -> list[tuple[str, Path]]:
    """解析 `tensor:=path`；相对路径按 input list 所在目录解析。"""
    path = Path(path)
    entries: list[tuple[str, Path]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, raw = line.partition(":=")
        if not separator or not name.strip() or not raw.strip():
            raise ValueError(f"{path}:{lineno} 不是合法的 `tensor:=path`：{line!r}")
        raw_path = Path(raw.strip())
        if not raw_path.is_absolute():
            raw_path = (path.parent / raw_path).resolve()
        entries.append((name.strip(), raw_path))
    if not entries:
        raise ValueError(f"input list 为空：{path}")
    return entries


def stability_inputs(
    entries: list[tuple[str, Path]], num_inferences: int
) -> list[tuple[str, Path]]:
    """稳定性门禁是"同一输入连续 N 次"，不是 N 条不同输入。

    取 input list 第一条真实语音重复 `num_inferences` 次；每次推理都由
    `qnn-net-run --num_inferences` 独立执行一遍，输出必须逐次有限。
    """
    if num_inferences < 1:
        raise ValueError("num_inferences 必须 >= 1")
    if not entries:
        raise ValueError("input list 为空，无法构造稳定性序列")
    return [entries[0]] * num_inferences


def write_farf_config(directory: Path) -> Path:
    """写 `<进程名>.farf`；运行目录（cwd）是搜索串第一项，/vendor 只读。"""
    path = Path(directory) / FARF_CONFIG_NAME
    path.write_text(FARF_CONFIG_MASK + "\n", encoding="ascii")
    return path


def farf_remote_path(remote_dir: str) -> str:
    """farf 必须落在 cwd（搜索串空串项），即远端运行目录。"""
    return f"{remote_dir}/{FARF_CONFIG_NAME}"


def build_adsp_library_path(remote_dir: str) -> str:
    """复合 ADSP 搜索路径：cwd + 运行目录 + 设备真实 /vendor 搜索根。"""
    return ";".join((".", remote_dir, *ADSP_SEARCH_ROOTS))


def build_remote_command(
    remote_dir: str,
    num_inferences: int,
    profiling_level: str,
    perf_profile: str,
) -> str:
    """构造设备侧命令；故意不出现 --timeout / rpctimeout。"""
    arguments = [
        "./qnn-net-run",
        "--backend", "./libQnnHtp.so",
        "--retrieve_context", "./context.bin",
        "--input_list", "./input-list.txt",
        "--output_dir", "./output",
        "--num_inferences", str(num_inferences),
        "--profiling_level", profiling_level,
        "--perf_profile", perf_profile,
        # verbose 才带出 DSP 侧 gpe_execute_novalidate 与 FastRPC
        # "Intentional crash ... timeout: 10000" 证据链。
        "--log_level", "verbose",
    ]
    # 该厂商 FastRPC 的 ADSP_LIBRARY_PATH 以 ';' 分隔（2.51.1 实测：
    # ':' 会被当成单个目录名，skel 落到 /vendor/lib/rfsa/adsp 的旧版本）。
    environment = (
        "LD_LIBRARY_PATH=. "
        f'ADSP_LIBRARY_PATH="{build_adsp_library_path(remote_dir)}"'
    )
    return f"cd {remote_dir} && {environment} " + " ".join(arguments)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_adb(serial: str, *arguments: str, timeout: float = 180.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb", "-s", serial, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _adb_failure(process: subprocess.CompletedProcess) -> str | None:
    text = f"{process.stdout or ''}\n{process.stderr or ''}"
    for marker in ("adb: device", "device offline", "no devices", "error: closed"):
        if marker in text:
            return text.strip()
    return None


def _parse_sha256sum(text: str) -> dict[str, str]:
    """把 `sha256sum` 输出解析成 basename → hash。"""
    hashes: dict[str, str] = {}
    for line in text.splitlines():
        match = _SHA256_LINE_RE.match(line.strip())
        if match is None:
            continue
        hashes[Path(match.group(2)).name] = match.group(1).lower()
    return hashes


_LOGCAT_PID_RE = re.compile(
    r"^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s+(\d+)\s+\d+\s+[VDIWEFA]\s"
)
_QNN_PID_RE = re.compile(r"qnn-net-run pid:(\d+)")


def qnn_run_pid(stdout: str) -> int | None:
    """从 runner 自报的 `qnn-net-run pid:N` 取本次运行 PID。"""
    match = _QNN_PID_RE.search(stdout)
    return int(match.group(1)) if match else None


def filter_logcat_for_pid(logcat: str, pid: int | None) -> str:
    """只留本次 qnn-net-run 的 logcat 行，避免外部进程污染分类。

    DSP 侧崩溃报告来自 cdsprpcd，但正文用 `fr/<pid>/` 标注应用进程，
    因此同时按 token 匹配。
    """
    if pid is None:
        return logcat
    token = re.compile(rf"(?<!\d){pid}(?!\d)")
    kept: list[str] = []
    for line in logcat.splitlines():
        match = _LOGCAT_PID_RE.match(line)
        if (match is not None and match.group(1) == str(pid)) or token.search(line):
            kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def input_list_candidates(artifact: Path, *, smoke: bool) -> tuple[Path, ...]:
    """brief Step 5 的裸命令没有 --input-list，需按候选位置回退。"""
    artifact = Path(artifact)
    if smoke:
        return (artifact.parent / "input-list-host.txt", artifact / "input_list.txt")
    return (
        artifact / "input_list.txt",
        artifact / "input-list-host.txt",
        DEBUG_ROOT / "inputs/campplus-input-list-host.txt",
    )


def resolve_input_list(artifact: Path, explicit: str | None, *, smoke: bool) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise FileNotFoundError(f"input list 不存在：{path}")
        return path
    candidates = input_list_candidates(artifact, smoke=smoke)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "找不到 input list，已尝试：\n  "
        + "\n  ".join(str(path) for path in candidates)
    )


def read_output(path: Path) -> "np.ndarray":
    """qnn-net-run 默认按 float32 写输出（未加 --use_native_output_files）。"""
    if np is None:
        raise RuntimeError("读取 QNN 输出需要 numpy：请用 var/speaker-benchmark/.venv 运行")
    return np.fromfile(Path(path), dtype="<f4")


def _failure(
    output_dir: Path,
    message: str,
    *,
    stdout: str = "",
    logcat: str = "",
    exit_code: int = -1,
) -> DeviceRunResult:
    stdout_path = output_dir / "stdout.log"
    logcat_path = output_dir / "logcat.txt"
    text = message.strip() + "\n"
    if stdout:
        text = stdout.rstrip() + "\n" + text
    stdout_path.write_text(text, encoding="utf-8", errors="replace")
    evidence = [stdout_path]
    if logcat:
        logcat_path.write_text(logcat, encoding="utf-8", errors="replace")
        evidence.append(logcat_path)
    result = DeviceRunResult(
        status="tool_error",
        exit_code=exit_code,
        output_path=None,
        output_count=0,
        finite=False,
        context_load_us=None,
        graph_execute_us=None,
        timeout_ms=None,
        evidence_paths=tuple(str(path) for path in evidence),
    )
    payload = result.to_dict()
    payload["error"] = message.strip()
    write_json_atomic(output_dir / "result.json", payload)
    return result


def run_context(
    serial: str,
    artifact_dir: Path,
    input_list: Path,
    output_dir: Path,
    num_inferences: int = 1,
    profiling_level: str = "basic",
    perf_profile: str = "default",
    *,
    toolchain: QairtToolchain | None = None,
    expected_input_shape: tuple[int, ...] = CAMPLUS_INPUT_SHAPE,
    expected_output_shape: tuple[int, ...] = CAMPLUS_OUTPUT_SHAPE,
    run_timeout_s: float = 240.0,
) -> DeviceRunResult:
    """部署同一 build 的 context 并在真机上运行，产出 `result.json`。

    超出 FastRPC 10 秒看门狗的运行会以 `timeout` 返回——这是预期证据，
    不是需要重试或绕过的问题。
    """
    artifact_dir = Path(artifact_dir)
    input_list = Path(input_list)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if num_inferences < 1:
        raise ValueError("num_inferences 必须 >= 1")

    info, context_bin = find_context_files(artifact_dir)
    metadata = load_context_metadata(info)
    validate_sm8845_context(
        metadata,
        expected_input_shape=tuple(expected_input_shape),
        expected_output_shape=tuple(expected_output_shape),
    )
    selected = toolchain or discover_toolchain()
    verify_toolchain(selected, metadata.build_id)

    try:
        entries = parse_input_list(input_list)
    except (OSError, ValueError) as exc:
        return _failure(output_dir, f"input list 不可用：{exc}")
    needed = stability_inputs(entries, num_inferences)

    run_name = (
        f"{time.strftime('%Y%m%d-%H%M%S')}-{artifact_dir.name}-{uuid.uuid4().hex[:8]}"
    )
    remote_dir = f"{REMOTE_ROOT}/{run_name}"

    made = _run_adb(serial, "shell", f"mkdir -p {remote_dir}/inputs {remote_dir}/output",
                    timeout=60)
    if made.returncode != 0:
        return _failure(output_dir, f"远端目录创建失败：{made.stderr or made.stdout}",
                        exit_code=made.returncode)

    pushed: list[tuple[Path, str, str]] = []  # (local, remote, 期望 hash)
    try:
        for host, name in selected.paths():
            remote = f"{remote_dir}/{name}"
            process = _run_adb(serial, "push", str(host), remote, timeout=600)
            if process.returncode != 0:
                reason = _adb_failure(process) or process.stderr or process.stdout
                return _failure(output_dir, f"推送 {name} 失败：{reason}",
                                exit_code=process.returncode)
            pushed.append((host, remote, _sha256(host)))

        remote_context = f"{remote_dir}/context.bin"
        process = _run_adb(serial, "push", str(context_bin), remote_context, timeout=600)
        if process.returncode != 0:
            reason = _adb_failure(process) or process.stderr or process.stdout
            return _failure(output_dir, f"推送 context 失败：{reason}",
                            exit_code=process.returncode)
        pushed.append((context_bin, remote_context, _sha256(context_bin)))

        remote_inputs: dict[Path, str] = {}
        remote_list_lines: list[str] = []
        for tensor, host in needed:
            remote_input = remote_inputs.get(host)
            if remote_input is None:
                # 同一输入重复 N 次只推一次，list 里重复引用同一远端文件。
                remote_input = f"{remote_dir}/inputs/{host.name}"
                process = _run_adb(serial, "push", str(host), remote_input, timeout=600)
                if process.returncode != 0:
                    reason = _adb_failure(process) or process.stderr or process.stdout
                    return _failure(output_dir, f"推送输入 {host.name} 失败：{reason}",
                                    exit_code=process.returncode)
                pushed.append((host, remote_input, _sha256(host)))
                remote_inputs[host] = remote_input
            remote_list_lines.append(f"{tensor}:={remote_input}")

        local_list = output_dir / "input-list-device.txt"
        local_list.write_text("\n".join(remote_list_lines) + "\n", encoding="ascii")
        remote_list = f"{remote_dir}/input-list.txt"
        process = _run_adb(serial, "push", str(local_list), remote_list, timeout=60)
        if process.returncode != 0:
            reason = _adb_failure(process) or process.stderr or process.stdout
            return _failure(output_dir, f"推送 input list 失败：{reason}",
                            exit_code=process.returncode)
        pushed.append((local_list, remote_list, _sha256(local_list)))

        farf = write_farf_config(output_dir)
        remote_farf = farf_remote_path(remote_dir)
        process = _run_adb(serial, "push", str(farf), remote_farf, timeout=60)
        if process.returncode != 0:
            reason = _adb_failure(process) or process.stderr or process.stdout
            return _failure(output_dir, f"推送 FARF 日志配置失败：{reason}",
                            exit_code=process.returncode)
        pushed.append((farf, remote_farf, _sha256(farf)))

        checksum = _run_adb(
            serial, "shell",
            "sha256sum " + " ".join(shlex.quote(remote) for _, remote, _ in pushed),
            timeout=120,
        )
        remote_hashes = _parse_sha256sum(checksum.stdout or "")
        for _, remote, expected_hash in pushed:
            actual = remote_hashes.get(Path(remote).name)
            if actual != expected_hash:
                return _failure(
                    output_dir,
                    f"远端 SHA-256 校验失败：{remote} 期望 {expected_hash} 实际 {actual}",
                    stdout=checksum.stdout or "",
                    logcat=checksum.stderr or "",
                )

        _run_adb(serial, "logcat", "-c", timeout=30)
        executable = _run_adb(serial, "shell", f"chmod 755 {remote_dir}/qnn-net-run",
                              timeout=30)
        if executable.returncode != 0:
            return _failure(
                output_dir,
                f"runner 赋权失败：{executable.stderr or executable.stdout}",
                exit_code=executable.returncode,
            )
        logcat_path = output_dir / "logcat.txt"
        with logcat_path.open("w", encoding="utf-8", errors="replace") as logcat_stream:
            logcat = subprocess.Popen(
                ["adb", "-s", serial, "logcat", "-v", "threadtime"],
                stdout=logcat_stream,
                stderr=subprocess.STDOUT,
            )
            try:
                completed = _run_adb(
                    serial, "shell",
                    build_remote_command(
                        remote_dir, num_inferences, profiling_level, perf_profile
                    ),
                    timeout=run_timeout_s,
                )
            except subprocess.TimeoutExpired as exc:
                logcat.terminate()
                logcat.wait(timeout=10)
                return _failure(output_dir, f"主机侧等待超时（{exc.timeout}s）：{exc}")
            finally:
                time.sleep(1.0)
                logcat.terminate()
                try:
                    logcat.wait(timeout=10)
                except subprocess.TimeoutExpired:  # pragma: no cover - 防御
                    logcat.kill()
                    logcat.wait(timeout=5)
    except FileNotFoundError as exc:
        return _failure(output_dir, f"adb/QAIRT 不可用：{exc}")

    stdout_text = f"{completed.stdout or ''}\n{completed.stderr or ''}".strip()
    (output_dir / "stdout.log").write_text(stdout_text + "\n", encoding="utf-8")

    if _adb_failure(completed):
        return _failure(
            output_dir,
            f"adb shell 失败：{_adb_failure(completed)}",
            stdout=stdout_text,
            logcat=logcat_path.read_text(encoding="utf-8", errors="replace"),
            exit_code=completed.returncode,
        )

    output_pull = _run_adb(serial, "pull", f"{remote_dir}/output",
                           str(output_dir / "output"), timeout=300)
    if output_pull.returncode != 0:
        return _failure(
            output_dir,
            f"拉取 output 失败：{_adb_failure(output_pull) or output_pull.stderr or output_pull.stdout}",
            stdout=stdout_text,
            logcat=logcat_path.read_text(encoding="utf-8", errors="replace"),
            exit_code=completed.returncode,
        )

    profile_text = ""
    profile_path = output_dir / "profile.log"
    profile_pull = _run_adb(serial, "pull", f"{remote_dir}/qnn-profiling-data.log",
                            str(profile_path), timeout=120)
    if profile_pull.returncode == 0 and profile_path.is_file():
        profile_text = profile_path.read_text(encoding="utf-8", errors="replace")
    elif profile_path.exists():
        profile_path.unlink()

    output_files = sorted((output_dir / "output").rglob("*.raw"))
    output_path = output_files[0] if output_files else None
    output_array = read_output(output_path) if output_path is not None else None

    logcat_text = logcat_path.read_text(encoding="utf-8", errors="replace")
    # 全量 logcat 是设备全局的（混有 thermalextservice 等外部进程的 SSR/
    # `Failed to load` 行），分类只看本次 qnn-net-run 的 PID；logcat.txt
    # 仍保留全量作为证据。
    run_logcat = filter_logcat_for_pid(logcat_text, qnn_run_pid(stdout_text))
    result = classify_device_run(
        stdout_text,
        run_logcat,
        output_array,
        expected_output_shape=tuple(metadata.output_shape),
        exit_code=completed.returncode,
        profile_text=profile_text,
    )
    evidence = [output_dir / "stdout.log", logcat_path]
    if profile_path.is_file():
        evidence.append(profile_path)
    if output_path is not None:
        evidence.append(output_path)
    result = dataclasses.replace(
        result,
        output_path=str(output_path) if output_path is not None else None,
        evidence_paths=tuple(str(path) for path in evidence),
    )
    write_json_atomic(output_dir / "result.json", result.to_dict())
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    smoke = subcommands.add_parser("smoke", help="跑 y=x+1 smoke context（预期 pass）")
    smoke.add_argument("--serial", required=True)
    smoke.add_argument("--artifact", default=str(SMOKE_ARTIFACT))
    smoke.add_argument("--input-list")
    smoke.add_argument("--num-inferences", type=int, default=1)
    smoke.add_argument("--output-dir")
    smoke.add_argument("--profiling-level", default="basic")
    smoke.add_argument("--perf-profile", default="default")

    run = subcommands.add_parser("run", help="跑一个 CAM++ artifact（超时是预期证据）")
    run.add_argument("--serial", required=True)
    run.add_argument("--artifact", required=True)
    run.add_argument("--input-list")
    run.add_argument("--num-inferences", type=int, default=1)
    run.add_argument("--output-dir")
    run.add_argument("--profiling-level", default="basic")
    run.add_argument("--perf-profile", default="default")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    artifact = Path(arguments.artifact)
    try:
        input_list = resolve_input_list(
            artifact, arguments.input_list, smoke=arguments.command == "smoke"
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if arguments.command == "smoke":
        expected_shapes = ((1, 16), (1, 16))
        label = "smoke"
    else:
        expected_shapes = (CAMPLUS_INPUT_SHAPE, CAMPLUS_OUTPUT_SHAPE)
        label = artifact.name

    output_dir = (
        Path(arguments.output_dir)
        if arguments.output_dir
        else DEBUG_ROOT / "device-runs" / f"{time.strftime('%Y%m%d-%H%M%S')}-{label}"
    )
    result = run_context(
        arguments.serial,
        artifact,
        input_list,
        output_dir,
        arguments.num_inferences,
        arguments.profiling_level,
        arguments.perf_profile,
        expected_input_shape=expected_shapes[0],
        expected_output_shape=expected_shapes[1],
    )
    print(result.to_json())
    return 0 if result.status == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
