"""vad —— 零依赖 VAD（语音活动检测）：能量阈值 + 滞回 + 补边。

全天候听觉日志的第一段漏斗（docs/superpowers/plans/2026-09-10-always-on-audio-journal.md
Part B）：常驻检测只判"有没有人声"，无声块即弃（零存储）；有声段成段落盘
交给后续转写。流式与批式在同一音频上的分段结果一致（一致性由测试钉住）。

零依赖策略：RMS 优先用 stdlib audioop（Python ≤3.12）；3.13 移除了 audioop，
兜底为纯 Python 实现（速度足够 100ms 块的实时处理）。
"""

from __future__ import annotations

import io
import math
import struct
import wave
from typing import Sequence

try:  # Python ≤3.12
    import audioop  # type: ignore
    _HAVE_AUDIOOP = True
except ImportError:  # 3.13+
    _HAVE_AUDIOOP = False


def rms_dbfs(samples: Sequence[int]) -> float:
    """RMS → dBFS（32768 满幅）。全零/空 → -120.0。"""
    if not samples:
        return -120.0
    if _HAVE_AUDIOOP:
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        rms = audioop.rms(pcm, 2)
    else:
        acc = 0
        for v in samples:
            acc += v * v
        rms = int(math.sqrt(acc / len(samples)))
    if rms == 0:
        return -120.0
    return 20.0 * math.log10(rms / 32768.0)


def rms_lin(samples: Sequence[int]) -> float:
    """RMS 线性幅度（PCEN 在线性域做归一化，不走对数）。"""
    if not samples:
        return 0.0
    if _HAVE_AUDIOOP:
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        return float(audioop.rms(pcm, 2))
    acc = 0
    for v in samples:
        acc += v * v
    return math.sqrt(acc / len(samples))


class _Pcen:
    """流式 PCEN（Per-Channel Energy Normalization, Wang et al. 2017 简化版）。

    快 EMA 跟能量 E、慢 EMA 跟底噪参考 M，输出 P=(E/(eps+M))^alpha - beta（整流）。
    性质：稳态音 P→1-beta（与绝对电平无关），突发/起始 P>>1，静音 P→0 ——
    这正是"大小声同一门限"的来源（EdgeSpot/FusionVAD 结论的零依赖落地）。
    M 用首帧能量初始化，避免冷启动虚报。
    """

    def __init__(self, *, s: float = 0.125, sm: float = 0.005,
                 alpha: float = 1.0, beta: float = 0.4, eps: float = 1e-6):
        self.s, self.sm, self.alpha, self.beta, self.eps = s, sm, alpha, beta, eps
        self._e: float | None = None
        self._m: float | None = None

    def step(self, amp: float) -> float:
        if self._e is None:  # 首帧：E=M=amp，稳态即 1-beta
            self._e = self._m = amp
        else:
            self._e = (1 - self.s) * self._e + self.s * amp
            self._m = (1 - self.sm) * self._m + self.sm * self._e
        p = (self._e / (self.eps + self._m)) ** self.alpha - self.beta
        return p if p > 0.0 else 0.0


def pcen_voiced_frames(samples: Sequence[int], sr: int, *, threshold: float = 0.5,
                       **pcen_kw) -> list[bool]:
    """批式 PCEN 有声帧判定（10ms 粒度，与能量法同粒度便于互换）。"""
    frame = max(1, sr // 100)
    pcen = _Pcen(**pcen_kw)
    return [pcen.step(rms_lin(samples[i:i + frame])) >= threshold
            for i in range(0, len(samples), frame)]


def split_segments(samples: Sequence[int], sr: int, *, threshold_dbfs: float = -35.0,
                   min_speech_ms: int = 200, min_silence_ms: int = 400,
                   pad_ms: int = 100, use_pcen: bool = False,
                   pcen_threshold: float = 0.5) -> list[tuple[int, int]]:
    """批式分段：返回有声区间 [(start, end)]（含 pad 的样本索引闭开区间）。

    滞回：能量 ≥ threshold 判有声进入；连续 < threshold 达 min_silence_ms 判结束。
    有声时长 < min_speech_ms 的段丢弃（咔哒/环境脉冲噪声）。
    use_pcen=True 时改用 PCEN 归一化能量（电平不变：大小声同一门限），
    此时 threshold_dbfs 被忽略、由 pcen_threshold 判定。
    """
    frame = max(1, sr // 100)  # 10ms 粒度
    n = len(samples)
    if use_pcen:
        voiced_frames = pcen_voiced_frames(samples, sr, threshold=pcen_threshold)
    else:
        voiced_frames = []
        for i in range(0, n, frame):
            chunk = samples[i:i + frame]
            voiced_frames.append(rms_dbfs(chunk) >= threshold_dbfs)

    min_sil_frames = max(1, min_silence_ms // 10)
    segments: list[tuple[int, int]] = []
    start = None
    silence_run = 0
    for idx, voiced in enumerate(voiced_frames):
        if voiced:
            silence_run = 0
            if start is None:
                start = idx
        else:
            if start is not None:
                silence_run += 1
                if silence_run >= min_sil_frames:
                    end = idx - silence_run + 1  # 静音起点
                    segments.append((start, end))
                    start = None
                    silence_run = 0
    if start is not None:
        segments.append((start, len(voiced_frames)))

    pad = sr * pad_ms // 1000
    out: list[tuple[int, int]] = []
    min_speech = sr * min_speech_ms // 1000
    for s, e in segments:
        s_samples = max(0, s * frame - pad)
        e_samples = min(n, e * frame + pad)
        if e_samples - s_samples >= min_speech:
            out.append((s_samples, e_samples))
    return out


def wav_bytes(segment_samples: Sequence[int], sr: int) -> bytes:
    """PCM16 样本 → WAV 字节（mono/16bit，stdlib wave）。"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f"<{len(segment_samples)}h", *segment_samples))
    return buf.getvalue()


class StreamingVAD:
    """流式 VAD：feed(PCM16LE 字节块) → 每次返回新完成的有声段列表。

    返回元素为 (start_ts_ms, wav_bytes)。内部按 10ms 帧计能量，滞回判停，
    段首/段尾各补 pad——分段语义与 split_segments 一致。
    """

    def __init__(self, sr: int, *, threshold_dbfs: float = -35.0,
                 min_speech_ms: int = 200, min_silence_ms: int = 400,
                 pad_ms: int = 100, use_pcen: bool = False,
                 pcen_threshold: float = 0.5):
        self.sr = sr
        self.threshold = threshold_dbfs
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.pad_ms = pad_ms
        self.use_pcen = use_pcen
        self._pcen = _Pcen() if use_pcen else None
        self._pcen_threshold = pcen_threshold
        self._frame = max(1, sr // 100)
        self._in_speech = False
        self._silence_run = 0
        self._seg_start_frame: int | None = None
        self._frame_idx = 0
        self._seg_buf: list[bytes] = []
        self._pad_frames = max(1, pad_ms // 10)
        self._pad_buf: list[bytes] = []  # 滚动保留 pad 窗口，段首补边用
        self._seg_frame_count = 0

    def feed(self, pcm16le: bytes) -> list[tuple[int, bytes]]:
        """喂一块 PCM16LE；返回本块内完成的有声段 [(start_ms, wav_bytes)]。"""
        completed: list[tuple[int, bytes]] = []
        step = self._frame * 2
        for i in range(0, len(pcm16le) - step + 1, step):
            frame_bytes = pcm16le[i:i + step]
            samples = struct.unpack(f"<{self._frame}h", frame_bytes)
            if self.use_pcen:
                voiced = self._pcen.step(rms_lin(samples)) >= self._pcen_threshold
            else:
                voiced = rms_dbfs(samples) >= self.threshold

            if not self._in_speech:
                self._pad_buf.append(frame_bytes)
                if len(self._pad_buf) > self._pad_frames:
                    self._pad_buf.pop(0)
                if voiced:
                    self._in_speech = True
                    # 起点回扣 pad 历史（与批式的 s*frame-pad 对齐）
                    self._seg_start_frame = max(0, self._frame_idx - len(self._pad_buf))
                    self._seg_buf = list(self._pad_buf)
                    self._seg_frame_count = 0
                    self._silence_run = 0
            else:
                self._seg_buf.append(frame_bytes)
                if voiced:
                    self._silence_run = 0
                    self._seg_frame_count += 1
                else:
                    self._silence_run += 1
                    if self._silence_run >= max(1, self.min_silence_ms // 10):
                        if self._seg_frame_count * 10 >= self.min_speech_ms:
                            start_ms = self._seg_start_frame * 10  # type: ignore[operator]
                            completed.append(
                                (start_ms, self._frames_to_wav(self._seg_buf)))
                        self._in_speech = False
                        self._seg_buf = []
                        # pad_buf 不清零：保留滚动静音历史，紧接的再触发
                        # 才能回扣完整 pad（与批式 s*frame-pad 严格对齐）
            self._frame_idx += 1
        return completed

    def _frames_to_wav(self, frames: list[bytes]) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sr)
            w.writeframes(b"".join(frames))
        return buf.getvalue()

    def flush(self) -> list[tuple[int, bytes]]:
        """收尾：若还有未闭合的有声段，按当前缓冲出段。"""
        if self._in_speech and self._seg_frame_count * 10 >= self.min_speech_ms:
            start_ms = self._seg_start_frame * 10  # type: ignore[operator]
            out = [(start_ms, self._frames_to_wav(self._seg_buf))]
            self._in_speech = False
            self._seg_buf = []
            return out
        return []
