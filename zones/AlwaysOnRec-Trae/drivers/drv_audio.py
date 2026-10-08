#!/usr/bin/env python3
"""drv_audio —— 语音增强"设备驱动"（MCP Server）。

把 ModelScope 的两个 Qwen Audio 语音增强模型封装成 syscall
（模型出处见 docs/research/2026-09-09-qnn-real-os-integration.md 的姊妹篇：
Qwen Audio 团队 2026-09-10 开源）：

    audio.separate  FLASepformer：8kHz 单声道双说话人分离 → 两路独立语音
    audio.aec       JAEC：16kHz 实时回声消除（神经网络时延估计 + 线性处理）

**运行环境**：本驱动需要 modelscope/torch/soundfile（仓库外依赖），因此必须用
专用 venv 的 python 启动（见 LAOS_AUDIO_PYTHON / laosd 的加载守卫）。laos 核心
保持零依赖的承诺不破坏——重依赖只存在于驱动子进程里。

定价语义：CPU 上可重跑的计算，标注 reversible=True（区别于 drv_npu 的
功耗不可逆定价）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_audio", version="0.1.0")

_pipelines: dict[str, object] = {}


def _get_pipeline(kind: str):
    """惰性加载模型（首次调用才下载/初始化，加载结果缓存）。"""
    if kind in _pipelines:
        return _pipelines[kind]
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks

    if kind == "separate":
        p = pipeline(Tasks.speech_separation,
                     model="iic/speech_flatsepreformer_separation_temporal_8k_base_libri2mix100",
                     trust_remote_code=True)
    elif kind == "aec":
        p = pipeline(Tasks.acoustic_echo_cancellation,
                     model="iic/speech_jaec_aec_16k", device="cpu",
                     trust_native_code=True)
    else:
        raise ValueError(f"EINVAL: unknown model kind {kind!r}")
    _pipelines[kind] = p
    return p


@drv.tool(
    "audio.separate",
    "FLASepformer 双说话人分离：8kHz 单声道 wav → 两路独立语音 wav",
    {
        "type": "object",
        "properties": {"wav": {"type": "string", "description": "混合语音 wav 路径（8000Hz 单声道）"}},
        "required": ["wav"],
    },
)
def audio_separate(wav: str) -> str:
    import numpy as np
    import soundfile as sf
    from modelscope.outputs import OutputKeys

    p = Path(wav)
    if not p.exists():
        raise FileNotFoundError(f"ENOENT: {wav}")
    t0 = time.perf_counter()
    result = _get_pipeline("separate")(wav)
    elapsed = time.perf_counter() - t0
    out_paths = []
    for i, signal in enumerate(result[OutputKeys.OUTPUT_PCM_LIST]):
        out = str(p.with_name(f"{p.stem}_spk{i + 1}.wav"))
        sf.write(out, np.frombuffer(signal, dtype=np.int16), 8000)
        out_paths.append(out)
    return f"OK separated in {elapsed:.1f}s -> {', '.join(out_paths)}"


@drv.tool(
    "audio.aec",
    "JAEC 回声消除：16kHz 等长 mic/farend wav 对 → 消回声后的 wav（22ms 固定延迟）",
    {
        "type": "object",
        "properties": {
            "nearend_mic": {"type": "string", "description": "麦克风信号 wav 路径"},
            "farend_speech": {"type": "string", "description": "远端参考 wav 路径"},
        },
        "required": ["nearend_mic", "farend_speech"],
    },
)
def audio_aec(nearend_mic: str, farend_speech: str) -> str:
    import numpy as np
    import soundfile as sf
    from modelscope.outputs import OutputKeys

    for p in (nearend_mic, farend_speech):
        if not Path(p).exists():
            raise FileNotFoundError(f"ENOENT: {p}")
    t0 = time.perf_counter()
    result = _get_pipeline("aec")({"nearend_mic": nearend_mic,
                                   "farend_speech": farend_speech})
    elapsed = time.perf_counter() - t0
    out = str(Path(nearend_mic).with_name(f"{Path(nearend_mic).stem}_aec.wav"))
    pcm = result[OutputKeys.OUTPUT_PCM]
    sf.write(out, np.frombuffer(pcm, dtype=np.int16), 16000)
    return f"OK aec in {elapsed:.1f}s -> {out}"


@drv.tool("audio.models", "列出本驱动已集成的语音增强模型与加载状态",
          {"type": "object", "properties": {}})
def audio_models() -> str:
    lines = [
        "[OK ] separate  FLASepformer (iic/speech_flatsepreformer_separation_temporal_8k_base_libri2mix100)",
        "[OK ] aec       JAEC (iic/speech_jaec_aec_16k, jaec_x86.dll)",
    ]
    lines.append(f"loaded: {', '.join(sorted(_pipelines)) or '(none yet, lazy on first call)'}")
    return "\n".join(lines)


if __name__ == "__main__":
    drv.serve_forever()
