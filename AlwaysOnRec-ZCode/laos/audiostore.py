"""audiostore —— 录音留存档（漏斗②的存储升级，默认关闭）。

四段漏斗的红线是"原音频即焚"（rec_gc / journal gc）。本模块只做一件事：
在即焚前把已经转写成功的段压缩进留存档（可选），让 6 小时窗口内的磁盘占用
从 115MB/h（PCM16）降到 ~57MB/h（µ-law）甚至 ~0.5MB/h（SNAC 神经编解码）。

隐私语义不变：
  * 默认不构造 AudioStore → journal 行为与旧版完全一致（即焚=删除）；
  * 留存档内容仍是可重建的原始音频 —— 它受与原音频相同的 gc/红线管辖，
    开启留存档的用户须自行设定档期清理（这与"重要片段高保真留存"是同一责任模型）；
  * µ-law 用 stdlib audioop（≤3.12）/纯 Python 兜底，零第三方依赖；
    SNAC 为可选依赖（lazy import，缺失即 CodecUnavailable），测试用假 codec 注入。
"""

from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

try:  # Python ≤3.12
    import audioop  # type: ignore
    _HAVE_AUDIOOP = True
except ImportError:  # 3.13+
    _HAVE_AUDIOOP = False

_BIAS = 0x84
_CLIP = 32635


def _lin2ulaw_one(sample: int) -> int:
    """PCM16 单样本 → µ-law 字节（经典 G.711 算法，纯 Python 兜底）。"""
    sign = (sample >> 8) & 0x80
    if sign:
        sample = -sample
    if sample > _CLIP:
        sample = _CLIP
    sample += _BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def _ulaw2lin_one(u: int) -> int:
    u = ~u & 0xFF
    sign = u & 0x80
    exponent = (u >> 4) & 0x07
    mantissa = u & 0x0F
    sample = ((mantissa << 3) + _BIAS) << exponent
    sample -= _BIAS
    return sample if not sign else -sample


def _lin2ulaw(pcm: bytes) -> bytes:
    if _HAVE_AUDIOOP:
        return audioop.lin2ulaw(pcm, 2)
    n = len(pcm) // 2
    vals = struct.unpack(f"<{n}h", pcm)
    return bytes(_lin2ulaw_one(v) for v in vals)


def _ulaw2lin(data: bytes) -> bytes:
    if _HAVE_AUDIOOP:
        return audioop.ulaw2lin(data, 2)
    n = len(data)
    return struct.pack(f"<{n}h", *(_ulaw2lin_one(b) for b in data))


class CodecUnavailable(RuntimeError):
    """可选编解码后端缺失（如 SNAC 未安装）。"""


class AudioStore:
    """留存档：store(wav 字节) → 压缩文件；load() → 重建 WAV 字节。

    codec: "ulaw"（零依赖，~0.5×）| "wav"（原样）| "snac"（可选，~0.005×，
    需 pip install snac + torch；仅存 token 时体积最小但重建需模型）。
    """

    def __init__(self, dir_path: Path, *, codec: str = "ulaw", sr: int = 16000):
        if codec not in ("ulaw", "wav", "snac"):
            raise ValueError(f"unknown codec: {codec}")
        self.dir = Path(dir_path)
        self.codec = codec
        self.sr = sr
        self.dir.mkdir(parents=True, exist_ok=True)

    def store(self, name: str, wav_bytes: bytes) -> Path:
        stem = Path(name).stem
        if self.codec == "wav":
            out = self.dir / f"{stem}.wav"
            out.write_bytes(wav_bytes)
            return out
        samples = self._wav_to_samples(wav_bytes)
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        if self.codec == "ulaw":
            out = self.dir / f"{stem}.ulaw"
            out.write_bytes(_lin2ulaw(pcm))
            return out
        # snac：可选后端，缺失时给出可操作的错误
        try:
            import snac  # noqa: F401
            import torch  # noqa: F401
        except ImportError as exc:
            raise CodecUnavailable(
                "snac codec requires `pip install snac torch`") from exc
        raise CodecUnavailable("snac token export wiring is experimental")

    def load(self, path: Path) -> bytes:
        """压缩文件 → 重建 WAV 字节（snac 档不支持离线重建）。"""
        path = Path(path)
        if path.suffix == ".wav":
            return path.read_bytes()
        if path.suffix == ".ulaw":
            return self._samples_to_wav(list(struct.unpack(
                f"<{path.stat().st_size}h", _ulaw2lin(path.read_bytes()))))
        raise CodecUnavailable(f"cannot rebuild {path.suffix} without model")

    def stats(self) -> dict:
        files = list(self.dir.glob("*"))
        return {"files": len(files), "bytes": sum(f.stat().st_size for f in files),
                "codec": self.codec}

    # -- WAV 拆装 -----------------------------------------------------------
    @staticmethod
    def _wav_to_samples(wav_bytes: bytes) -> list[int]:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            raw = w.readframes(w.getnframes())
        n = len(raw) // 2
        return list(struct.unpack(f"<{n}h", raw))

    def _samples_to_wav(self, samples: list[int]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        return buf.getvalue()

