#!/usr/bin/env python3
"""drv_ear —— 听觉驱动：ASR 双通道（MCP Server，重依赖惰性导入）。

    ear.transcribe  wav → 统一 JSON：{"text","language","emotions","source","latency_ms"}
    ear.status      通道 / 模型路径 / 服务可达性 / 模型加载状态

双通道（LAOS_ASR_CHANNEL，默认 funasr）：

    funasr  本机直推：funasr AutoModel(SenseVoiceSmall + fsmn-vad)。
            模型路径 env LAOS_SENSEVOICE_MODEL / LAOS_SENSEVOICE_VAD；
            device = cuda:0（torch.cuda 可用时）否则 cpu；
            富文本标签 <|zh|><|NEUTRAL|>... 解析出 language 与 emotions，
            rich_transcription_postprocess 剥标签得纯文本。
            重依赖（funasr/torch/soundfile）只在首次 transcribe 时惰性导入。

    server  HTTP 服务：stdlib urllib 手拼 multipart POST 到
            {LAOS_ASR_SERVER:http://127.0.0.1:8000}/v1/transcribe
            （field: file=wav 字节, language）→ 解析 JSON 响应。
            零第三方依赖——任何解释器都能跑这一通道。

依赖策略与 drv_audio/drv_mic 一致：裸解释器必须能 import 本驱动并回答
status（find_spec 探测，不真正 import funasr）；缺依赖只在真用到该通道时
报 ENOENT。
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import threading
import wave
import struct
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_ear", version="0.1.0")


def _install_protocol_guard() -> None:
    """stdio 协议保护（仅 serve_forever 前安装，import 本模块零副作用）。

    funasr/torch 加载与推理时会往 stdout 打日志（模型加载信息、进度条），
    会污染 MCP 的 JSON-RPC 行协议（内核读到的就是 "Expecting value" 解析
    错误）。做法：复制出"真 stdout"专用于协议写出，再把 sys.stdout 指到
    stderr——第三方库的一切打印都退化为驱动日志（stderr，内核 DEVNULL
    丢弃），协议行永远干净。
    """
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w",
                         encoding="utf-8", buffering=1)

    def _protocol_write(obj: dict) -> None:
        protocol.write(json.dumps(obj, ensure_ascii=False) + "\n")
        protocol.flush()

    drv._write = _protocol_write  # 实例属性遮蔽：serve_forever / elicit 都走这里
    sys.stdout = sys.stderr

#: SenseVoice 模型缓存默认路径（本机；LAOS_SENSEVOICE_MODEL/VAD 可覆盖）
DEFAULT_MODEL = "D:/ldf/sensevoice_asr/models/models/iic--SenseVoiceSmall/snapshots/master"
DEFAULT_VAD = (
    "D:/ldf/sensevoice_asr/models/models/"
    "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch/snapshots/master"
)

#: SenseVoice 富文本标签里的情感 / 语言 token
EMOTION_TAGS = {"NEUTRAL", "HAPPY", "SAD", "ANGRY", "FEARFUL",
                "DISGUSTED", "SURPRISED"}
LANGUAGE_TAGS = {"zh", "en", "yue", "ja", "ko", "de", "es", "fr", "auto"}

#: 惰性加载的 funasr AutoModel（None = 未加载）+ 加载/推理互斥锁
_model_lock = threading.Lock()
_model = None
_model_device: str = "-"


def _funasr_available() -> bool:
    """find_spec 探测（不真正 import，裸解释器也能秒答）。"""
    return importlib.util.find_spec("funasr") is not None


def _get_model():
    """惰性加载 SenseVoice AutoModel（进程内只加载一次）。"""
    global _model, _model_device
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            try:
                from funasr import AutoModel  # 重依赖：仅 funasr 通道真实推理时
            except ImportError as exc:
                raise RuntimeError(
                    f"ENOENT: funasr not installed in this interpreter ({exc}); "
                    f"set LAOS_ASR_CHANNEL=server or run drv_ear under conda python"
                ) from exc
            import torch
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            model_path = os.environ.get("LAOS_SENSEVOICE_MODEL", DEFAULT_MODEL)
            vad_path = os.environ.get("LAOS_SENSEVOICE_VAD", DEFAULT_VAD)
            _model = AutoModel(
                model=model_path, vad_model=vad_path,
                vad_kwargs={"max_single_segment_time": 30000},
                trust_remote_code=True, device=device,
                disable_update=True, ncpu=4)
            _model_device = device
    return _model


def _parse_tags(raw: str) -> tuple[str, list[str]]:
    """从富文本标签解析 (language, emotions)：语言取首个语言标签。"""
    tags = re.findall(r"<\|([^|]+)\|>", raw)
    emotions = [t for t in tags if t.upper() in EMOTION_TAGS]
    language = next((t for t in tags if t.lower() in LANGUAGE_TAGS
                     and t.lower() != "auto"), "")
    return language, emotions


def _transcribe_funasr(path: Path, language: str) -> dict:
    model = _get_model()
    import soundfile as sf  # funasr 栈内必有
    audio, _sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    with _model_lock:  # AutoModel 非并发安全
        res = model.generate(input=audio, cache={}, language=language,
                             use_itn=True, batch_size_s=60,
                             merge_vad=True, merge_length_s=15)
    raw = str(res[0]["text"])
    lang, emotions = _parse_tags(raw)
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    text = rich_transcription_postprocess(raw)
    return {"text": text,
            "language": lang or (language if language != "auto" else "unknown"),
            "emotions": emotions}


def _transcribe_server(path: Path, language: str) -> dict:
    server = os.environ.get("LAOS_ASR_SERVER", "http://127.0.0.1:8000").rstrip("/")
    boundary = "----laosdrv_ear" + uuid.uuid4().hex
    body = (
        (f"--{boundary}\r\n"
         f'Content-Disposition: form-data; name="file"; '
         f'filename="{path.name}"\r\n'
         f"Content-Type: audio/wav\r\n\r\n").encode("utf-8")
        + path.read_bytes() + b"\r\n"
        + (f"--{boundary}\r\n"
           f'Content-Disposition: form-data; name="language"\r\n\r\n'
           f"{language}\r\n").encode("utf-8")
        + f"--{boundary}--\r\n".encode("utf-8")
    )
    req = urllib.request.Request(
        f"{server}/v1/transcribe", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return {"text": str(payload.get("text", "")),
            "language": str(payload.get("language", "unknown")),
            "emotions": [str(e) for e in (payload.get("emotions") or [])]}


def _server_reachable(server: str) -> bool:
    """/health 探活；任何 HTTP 响应（含 404）都算服务在。"""
    for suffix in ("/health", "/"):
        try:
            with urllib.request.urlopen(server + suffix, timeout=1.5):
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            continue
    return False


@drv.tool(
    "ear.assess",
    "发音韵律评估（零依赖档：流利度/节奏两维；音素准确度需 GOPT 后端）",
    {"type": "object",
     "properties": {"wav": {"type": "string", "description": "WAV 文件路径"},
                    "expected_text": {"type": "string"}},
     "required": ["wav"]},
)
def ear_assess(wav: str, expected_text: str = "") -> str:
    import json as _json
    from laos.pronunciation import assess
    path = Path(wav)
    if not path.exists():
        return _json.dumps({"error": f"ENOENT: {wav}"}, ensure_ascii=False)
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    n = len(raw) // 2
    samples = list(struct.unpack(f"<{n}h", raw))
    result = assess(samples, sr,
                    expected_text=expected_text or None)
    return _json.dumps(result, ensure_ascii=False)


@drv.tool(
    "ear.transcribe",
    "语音识别（wav 路径）→ 统一 JSON：text/language/emotions/source/latency_ms。"
    "通道由 LAOS_ASR_CHANNEL 选（funasr=本机 SenseVoice / server=HTTP 服务）",
    {"type": "object",
     "properties": {"wav": {"type": "string", "description": "wav 文件路径"},
                    "language": {"type": "string",
                                 "description": "语言（默认 auto）"}},
     "required": ["wav"]},
)
def ear_transcribe(wav: str, language: str = "auto") -> str:
    t0 = time.perf_counter()
    path = Path(wav)
    if not path.exists():
        raise FileNotFoundError(f"ENOENT: no such wav: {wav}")
    channel = os.environ.get("LAOS_ASR_CHANNEL", "funasr")
    if channel == "server":
        out, source = _transcribe_server(path, language), "server"
    elif channel == "funasr":
        out, source = _transcribe_funasr(path, language), "funasr"
    else:
        raise ValueError(f"EINVAL: unknown LAOS_ASR_CHANNEL {channel!r} "
                         f"(funasr|server)")
    out["source"] = source
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return json.dumps(out, ensure_ascii=False)


@drv.tool(
    "ear.status",
    "听觉驱动状态：通道 / 模型路径存在性 / ASR 服务可达性 / 模型加载状态",
    {"type": "object", "properties": {}},
)
def ear_status() -> str:
    channel = os.environ.get("LAOS_ASR_CHANNEL", "funasr")
    model_path = os.environ.get("LAOS_SENSEVOICE_MODEL", DEFAULT_MODEL)
    vad_path = os.environ.get("LAOS_SENSEVOICE_VAD", DEFAULT_VAD)
    server = os.environ.get("LAOS_ASR_SERVER", "http://127.0.0.1:8000").rstrip("/")
    return (f"channel={channel} "
            f"model_path={Path(model_path).exists()} "
            f"vad_path={Path(vad_path).exists()} "
            f"server_reachable={_server_reachable(server)} "
            f"funasr={'available' if _funasr_available() else 'unavailable'} "
            f"loaded={_model is not None} device={_model_device}")


if __name__ == "__main__":
    _install_protocol_guard()
    drv.serve_forever()
