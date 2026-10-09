"""asr —— laos 的转写客户端（OpenAI 兼容 /audio/transcriptions，纯 stdlib）。

opt-in：`LAOS_ASR_URL`（如 https://api.groq.com/openai/v1，自动拼
/audio/transcriptions；已含 /transcriptions 的完整 URL 原样用）+
可选 `LAOS_ASR_KEY` / `LAOS_ASR_MODEL`（部分端点必填，如 whisper-large-v3-turbo）。
未配置 → from_env() 返回 None，调用方降级（laosweb /api/voice 返回 503）。

隐私红线（与 drv_ear 同源）：上行音频**只做转写不落盘**；审计只记
字节数/耗时/成败，内容与音频本身永不入审计。零依赖：multipart 手拼
（OpenAI 转写契约：file 字段 + 可选 model 字段）。
"""
from __future__ import annotations

import os
import json
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Optional

__all__ = ["AsrError", "TranscribeClient"]


class AsrError(RuntimeError):
    """转写失败（网络/HTTP/响应形状）。调用方降级，不崩链路。"""


def _multipart(fields: dict[str, str], file_field: str, filename: str,
               content_type: str, audio: bytes, boundary: str) -> bytes:
    """手拼 multipart/form-data（stdlib 无现成 multipart 编码器）。"""
    out = bytearray()
    for name, value in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; "
                f'name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
    out += (f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n").encode("utf-8")
    out += audio + b"\r\n"
    out += f"--{boundary}--\r\n".encode("ascii")
    return bytes(out)


@dataclass(frozen=True)
class TranscribeClient:
    """一个 OpenAI 兼容转写端点的最小封装。无状态、线程安全。"""

    url: str
    api_key: str = ""
    model: str = ""
    timeout_s: float = 60.0

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> Optional["TranscribeClient"]:
        env = os.environ if env is None else env

        def _num(name: str, default: float) -> float:
            try:
                return float(env.get(name, "") or default)
            except ValueError:
                return default

        url = str(env.get("LAOS_ASR_URL", "")).strip().rstrip("/")
        if not url:
            return None
        return cls(url=url,
                   api_key=str(env.get("LAOS_ASR_KEY", "")).strip(),
                   model=str(env.get("LAOS_ASR_MODEL", "")).strip(),
                   timeout_s=_num("LAOS_ASR_TIMEOUT_S", 60.0))

    def transcribe(self, audio: bytes, content_type: str = "audio/wav",
                   filename: str = "audio.wav") -> str:
        """音频字节 → 文本。OpenAI 兼容端点返回 {"text": "..."}。"""
        endpoint = (self.url if self.url.endswith("/audio/transcriptions")
                    else self.url + "/audio/transcriptions")
        boundary = "laos-" + uuid.uuid4().hex
        fields = {k: v for k, v in (("model", self.model),) if v}
        body = _multipart(fields, "file", filename, content_type, audio, boundary)
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(endpoint, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise AsrError(f"{type(exc).__name__}: {exc}") from exc
        text = data.get("text") if isinstance(data, dict) else None
        if not isinstance(text, str):
            raise AsrError(f"unexpected response shape: {list(data)[:5] if isinstance(data, dict) else type(data).__name__}")
        return text
