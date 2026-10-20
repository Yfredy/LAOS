"""speaker_qnn：SM8845/HTP V81 的 QNN 构建与真机诊断工具链。

Task 1 只固化故障基线与真机执行契约（元数据门禁、结果分类、ADB 运行器），
不做修复。后续任务在同一 schema 上追加 build/probe/benchmark。

    python -m unittest tests.test_speaker_qnn_contracts tests.test_speaker_qnn_device -v
    python -m scripts.speaker_qnn.device smoke --serial <serial>
"""
from __future__ import annotations

from .contracts import (
    CAMPLUS_INPUT_SHAPE,
    CAMPLUS_OUTPUT_SHAPE,
    HTP_V81_DSP_ARCH,
    SCHEMA_VERSION,
    SM8845_SOC_MODEL,
    ContextMetadata,
    DeviceRunResult,
    DeviceRunStatus,
    classify_device_run,
    load_context_metadata,
    parse_profile_timings,
    validate_sm8845_context,
    write_json_atomic,
)

__all__ = [
    "CAMPLUS_INPUT_SHAPE",
    "CAMPLUS_OUTPUT_SHAPE",
    "HTP_V81_DSP_ARCH",
    "SCHEMA_VERSION",
    "SM8845_SOC_MODEL",
    "ContextMetadata",
    "DeviceRunResult",
    "DeviceRunStatus",
    "classify_device_run",
    "load_context_metadata",
    "parse_profile_timings",
    "validate_sm8845_context",
    "write_json_atomic",
]
