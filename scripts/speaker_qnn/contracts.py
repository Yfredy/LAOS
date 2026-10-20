"""SM8845/V81 QNN 契约：context 元数据门禁、真机结果分类与 JSON 序列化。

故障基线（2026-10-20 实录，nubia P0310 / SM8845 / HTP V81）：

- QAIRT 2.51.1 context 元数据为 `socModel=87`、`dspArch=81`，CAM++ W8A16
  context 输入 `U16[1,80,298]`、输出 `U16[1,192]`；
- CAM++ 在 `gpe_execute_novalidate` 后恰好 10.001 s 被 FastRPC 看门狗
  主动终止，QNN 返回 `err 1003` 并触发 CDSP SSR，没有 embedding 输出；
- 同机 y=x+1 smoke graph 正常，说明设备/HTP 通路本身可用；
- QAIRT 2.47 对 SM8845 曾静默回退到 `socModel=0`、`dspArch=68`。

因此契约层做两件事：上机前拒绝任何元数据回退的 context；下机后只把
"退出码 0 + 有限输出 + 无看门狗/SSR 证据"判为 `pass`，绝不把看门狗
超时报告成延迟。10 秒看门狗是安全边界，本模块不修改也不绕过它。
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # 主库 discover 环境没有 numpy，运行时按需导入
    import numpy as np

SCHEMA_VERSION = 1

SM8845_SOC_MODEL = 87
HTP_V81_DSP_ARCH = 81
# info.json 记录的是 QNN context 物理布局；语义布局 [1,298,80] 由转换器
# 内部转置，转换记录见 campplus-w8a16 的 calibration_manifest.json。
CAMPLUS_INPUT_SHAPE = (1, 80, 298)
CAMPLUS_OUTPUT_SHAPE = (1, 192)

DeviceRunStatus = Literal[
    "pass",
    "timeout",
    "ssr",
    "load_error",
    "execute_error",
    "tool_error",
]


@dataclass(frozen=True)
class ContextMetadata:
    """一个 context 的单一 graph 元数据（build/arch/形状）。"""

    build_id: str
    soc_model: int
    dsp_arch: int
    graph_name: str
    input_shape: tuple[int, ...]
    output_shape: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_shape"] = list(self.input_shape)
        payload["output_shape"] = list(self.output_shape)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


@dataclass(frozen=True)
class DeviceRunResult:
    """一次真机执行的判定结果；`pass` 之外都不是速度值。"""

    status: DeviceRunStatus
    exit_code: int
    output_path: str | None
    output_count: int
    finite: bool
    context_load_us: int | None
    graph_execute_us: int | None
    timeout_ms: int | None
    evidence_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_paths"] = list(self.evidence_paths)
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def load_context_metadata(info_json: Path) -> ContextMetadata:
    """读取 `qnn-context-binary-utility` 导出的 info.json。

    只接受恰好一个 graph、一个 input、一个 output 的 context；多图/空图
    直接拒绝，避免把错误 context 推上真机。
    """
    info_json = Path(info_json)
    try:
        payload = json.loads(info_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 context info.json: {info_json}: {exc}") from exc

    graphs = payload.get("graphs") or []
    num_graphs = payload.get("numGraphs", len(graphs))
    if num_graphs != 1 or len(graphs) != 1:
        raise ValueError(
            f"context 必须恰好一个 graph（numGraphs={num_graphs}），"
            f"实际 {len(graphs)} 个：{info_json}"
        )
    graph = graphs[0]
    inputs = graph.get("graphInputs") or []
    outputs = graph.get("graphOutputs") or []
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError(
            f"context 必须恰好一个 input/output，实际 {len(inputs)}/{len(outputs)}："
            f"{info_json}"
        )

    build_id = payload.get("buildId")
    if not isinstance(build_id, str) or not build_id:
        raise ValueError(f"context 缺少 buildId：{info_json}")
    soc_model = payload.get("socModel")
    dsp_arch = (payload.get("contextMetadata") or {}).get("dspArch")
    if not isinstance(soc_model, int) or not isinstance(dsp_arch, int):
        raise ValueError(
            "SM8845/V81 元数据缺失："
            f"socModel={soc_model!r}, dspArch={dsp_arch!r}（{info_json}）"
        )

    return ContextMetadata(
        build_id=build_id,
        soc_model=soc_model,
        dsp_arch=dsp_arch,
        graph_name=str(graph.get("graphName", "")),
        input_shape=tuple(int(v) for v in inputs[0].get("dimensions") or ()),
        output_shape=tuple(int(v) for v in outputs[0].get("dimensions") or ()),
    )


def validate_sm8845_context(
    metadata: ContextMetadata,
    *,
    expected_input_shape: tuple[int, ...] = CAMPLUS_INPUT_SHAPE,
    expected_output_shape: tuple[int, ...] = CAMPLUS_OUTPUT_SHAPE,
) -> None:
    """SM8845/V81 上机门禁：拒绝 arch 回退与形状不符的 context。"""
    if metadata.soc_model != SM8845_SOC_MODEL or metadata.dsp_arch != HTP_V81_DSP_ARCH:
        raise ValueError(
            "SM8845/V81 元数据不匹配："
            f"socModel={metadata.soc_model}, dspArch={metadata.dsp_arch}；"
            f"要求 socModel={SM8845_SOC_MODEL}, dspArch={HTP_V81_DSP_ARCH}"
        )
    actual_input = tuple(metadata.input_shape)
    actual_output = tuple(metadata.output_shape)
    if actual_input != tuple(expected_input_shape) or actual_output != tuple(
        expected_output_shape
    ):
        raise ValueError(
            "SM8845/V81 context 形状不匹配："
            f"input={actual_input} output={actual_output}；"
            f"期望 input={tuple(expected_input_shape)} "
            f"output={tuple(expected_output_shape)}"
        )


# 看门狗证据有两种真实形态：客户端主动终止
# （`... remote session control ... timeout: 10000`）与 CDSP 崩溃报告
# （`crashed in thread "fr/<pid>/..." ... timeout: 10000`）。
_TIMEOUT_RE = re.compile(
    r"(?:remote session control[^\n]*?|crashed in thread[^\n]*?)\btimeout\s*:\s*(\d+)",
    re.I,
)
_INTENTIONAL_CRASH_RE = re.compile(r"intentional crash triggered", re.I)
_SSR_RE = re.compile(
    r"SSR detected|SSR in progress|Single-Core SSR|SSR successfully recovered",
    re.I,
)
_LOAD_ERROR_RE = re.compile(
    r"failed to load|unable to load|could not load|context create failed|"
    r"load context(?: binary)? failed|QnnContext_create.*fail",
    re.I,
)
_EXEC_ERROR_RE = re.compile(
    r"graph execution failure|failed in execution|err\s+1003|"
    r"execution finished with result [1-9]",
    re.I,
)

_TIMING_UNIT_US = {"us": 1, "µs": 1, "ms": 1000, "s": 1_000_000}
_LOAD_TIME_RE = re.compile(
    r"load(?: binary)?\)?\s*time\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(us|µs|ms|s)\b",
    re.I,
)
_EXEC_TIME_RE = re.compile(
    r"(?:graph\s+)?execut(?:e|ion)(?:\s+excluding\s+wait)?\)?\s*time\s*[:=]\s*"
    r"([0-9]+(?:\.[0-9]+)?)\s*(us|µs|ms|s)\b",
    re.I,
)


def _flat_values(output: Any) -> list[float]:
    """把 numpy 数组/嵌套 list 归一成有限性检查用的扁平 float 列表。"""
    if output is None:
        return []
    tolist = getattr(output, "tolist", None)
    if callable(tolist):
        output = tolist()
    values: list[float] = []
    pending = [output]
    while pending:
        item = pending.pop(0)
        if isinstance(item, (list, tuple)):
            pending[:0] = list(item)
        else:
            values.append(float(item))
    return values


def _parse_timing(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text or "")
    if match is None:
        return None
    value = float(match.group(1)) * _TIMING_UNIT_US[match.group(2).lower()]
    return int(round(value))


def parse_profile_timings(text: str) -> tuple[int | None, int | None]:
    """从 qnn-profile-viewer 文本里取 (context load, graph execute) 微秒。"""
    return _parse_timing(_LOAD_TIME_RE, text), _parse_timing(_EXEC_TIME_RE, text)


def classify_device_run(
    stdout: str,
    logcat: str,
    output: "np.ndarray | None",
    *,
    expected_output_shape: tuple[int, ...] = CAMPLUS_OUTPUT_SHAPE,
    exit_code: int = 0,
    profile_text: str = "",
) -> DeviceRunResult:
    """按证据强弱判定一次真机运行。

    优先级：看门狗 timeout > SSR > context 加载失败 > 通用执行失败 >
    输出缺失/元素数不符/非有限。看门狗证据是根因，SSR 是它的下游后果
    ——真实 CAM++ logcat 两者同时出现，必须判 `timeout`。
    """
    combined = "\n".join((stdout or "", logcat or ""))
    timeout_match = _TIMEOUT_RE.search(combined)
    timeout_ms = int(timeout_match.group(1)) if timeout_match else None

    if timeout_match or _INTENTIONAL_CRASH_RE.search(combined):
        status: DeviceRunStatus = "timeout"
    elif _SSR_RE.search(combined):
        status = "ssr"
    elif _LOAD_ERROR_RE.search(combined):
        status = "load_error"
    elif _EXEC_ERROR_RE.search(combined) or exit_code != 0:
        status = "execute_error"
    elif output is None:
        status = "execute_error"
    else:
        status = "pass"

    values = _flat_values(output)
    expected_count = math.prod(expected_output_shape)
    finite = bool(values) and all(math.isfinite(value) for value in values)
    if status == "pass" and (len(values) != expected_count or not finite):
        status = "execute_error"

    load_us, execute_us = parse_profile_timings(profile_text)
    return DeviceRunResult(
        status=status,
        exit_code=exit_code,
        output_path=None,
        output_count=len(values),
        finite=finite,
        context_load_us=load_us,
        graph_execute_us=execute_us,
        timeout_ms=timeout_ms,
        evidence_paths=(),
    )


def write_json_atomic(path: Path, payload: Any) -> None:
    """原子写 JSON（同目录临时文件 + os.replace）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
