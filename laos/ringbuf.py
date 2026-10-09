"""AudioRingBuffer —— 回放用音频环形缓冲（纯 stdlib，内存即焚）。

录音回放（rec.replay / mic.replay）的底座：监听线程把每个音频块 feed 进来，
缓冲只保留最近 max_seconds 秒 PCM16 字节（约 32KB/s @16kHz 单声道，
默认 30s≈960KB——手机内存预算内的小镜像，权威时域存储在 ADSP），超龄
即弃——不落盘、不进审计、进程退出即消失。音频落盘只发生在显式回放
syscall（mic.replay）内部（隐私红线，见 drivers/drv_mic.py 头注）。
"""

from __future__ import annotations

import io
import threading
import wave


class AudioRingBuffer:
    """线程安全的 PCM16 单声道环形缓冲。"""

    def __init__(self, sample_rate: int = 16000, max_seconds: float = 30.0):
        self.sample_rate = int(sample_rate)
        self.max_bytes = int(self.sample_rate * 2 * float(max_seconds))
        self._buf = bytearray()
        self._lock = threading.Lock()

    def feed(self, pcm16_bytes: bytes) -> None:
        """追加一个音频块；超出容量按整样本裁掉最旧数据。"""
        with self._lock:
            self._buf += pcm16_bytes
            if len(self._buf) > self.max_bytes:
                cut = len(self._buf) - self.max_bytes
                cut += cut % 2  # 不劈开 int16 样本
                del self._buf[:cut]

    def snapshot(self, seconds: float) -> bytes:
        """取最近 seconds 秒（不足则全部）PCM16 字节副本。"""
        want = int(float(seconds) * self.sample_rate * 2)
        with self._lock:
            want = min(want, len(self._buf))
            want -= want % 2
            return bytes(self._buf[-want:]) if want else b""

    def available_seconds(self) -> float:
        with self._lock:
            return len(self._buf) / (self.sample_rate * 2)

    def wav_bytes(self, seconds: float) -> bytes:
        """快照 + 44 字节 WAV 头（PCM16 单声道），可直接落盘/播放。"""
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(self.snapshot(seconds))
        return out.getvalue()
