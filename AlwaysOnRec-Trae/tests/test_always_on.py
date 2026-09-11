# tests/test_always_on.py
"""drv_mic 常开模式 —— 环形缓冲 + VAD 门控落盘 + rewind（注入式，无真机）。

    python -m unittest tests.test_always_on -v

解释器约定（与 test_rec.py 同款注入模式）：
  - 本测试文件用裸 uv python 跑（无 sounddevice/numpy/soundfile）——常开路径
    分段落盘走 laos.vad.wav_bytes（纯 stdlib），环形缓冲是纯字节操作，
    注入 fake input factory 即可端到端验证，全程零重依赖；
  - 真声卡路径由 test_ear_mic.py 的 conda 用例覆盖（skipUnless 守卫）。

线程时序（防 flaky）：注入 factory 的流在 start 后由喂块线程异步推块，
每块回调同步完成"进环形缓冲 + VAD 消费"，喂完置 feed_done 事件——测试等
feed_done 即代表全部块已处理完（回调内同步落盘），无需轮询猜测；
mic.always_on_stop 会在流 stop 时 join 喂块线程再 flush，同样无竞态。

隐私红线：常开线程只能被 mic.always_on_start 显式拉起（模块加载零线程）；
LAOS_REC=0 时 always_on_start 抛 PermissionError；环形缓冲读写持 _ring_lock。
"""
from __future__ import annotations

import math
import os
import re
import sys
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_mic  # noqa: E402

SR = drv_mic.SAMPLE_RATE
BLOCK = SR // 10 * 2  # 100ms 块的 PCM16LE 字节数（1600 样本 × 2）


def synth_pcm(spec: list[tuple[str, int]]) -> bytes:
    """按 [(kind, ms), ...] 合成 PCM16LE；kind "v"=440Hz 正弦（响），"s"=数字静音。"""
    out = bytearray()
    for kind, ms in spec:
        n = SR * ms // 1000
        if kind == "v":
            for i in range(n):
                v = int(0.5 * 26000 * math.sin(2 * math.pi * 440 * i / SR))
                out += v.to_bytes(2, "little", signed=True)
        else:
            out += b"\x00\x00" * n
    return bytes(out)


#: 计划钉的三段式音频：[有声 0.4s][静 0.6s][有声 0.4s]（共 1.4s，恰 14 块）
THREE_PHASE: list[tuple[str, int]] = [("v", 400), ("s", 600), ("v", 400)]


class FakeInputStream:
    """start 后由喂块线程异步推块的假输入流；喂完置 done，stop 会 join 喂块线程。"""

    def __init__(self, callback, blocks: list[bytes], done: threading.Event):
        self._cb = callback
        self._blocks = blocks
        self._done = done
        self.stopped = False
        self._feeder: threading.Thread | None = None

    def start(self):
        def feed():
            for b in self._blocks:
                if self.stopped:
                    break
                self._cb(b, None, None, None)  # 回调内同步：进 ring + VAD 消费
            self._done.set()
        self._feeder = threading.Thread(target=feed, daemon=True, name="ao-feeder")
        self._feeder.start()

    def stop(self):
        self.stopped = True
        if self._feeder is not None:
            self._feeder.join(timeout=2.0)  # 喂块线程停了才放手，flush 无竞态

    def close(self):
        pass


class AlwaysOnCase(unittest.TestCase):
    """mic.always_on_start / mic.rewind / mic.always_on_stop 全流程。"""

    def setUp(self):
        self._td = Path(__file__).parent / "_ao_tmp"
        self._td.mkdir(exist_ok=True)
        drv_mic.set_output_dir(self._td)
        drv_mic._reset()

    def tearDown(self):
        drv_mic._reset()
        drv_mic.set_output_dir(None)
        import shutil
        shutil.rmtree(self._td, ignore_errors=True)

    def _start_with(self, audio: bytes, **kwargs) -> tuple[str, threading.Event]:
        """注入 factory（异步喂块）并拉起常开线程，返回 (start 返回文本, feed_done)。"""
        blocks = [audio[i:i + BLOCK] for i in range(0, len(audio), BLOCK)]
        done = threading.Event()

        def factory(samplerate, blocksize, dtype, callback):
            return FakeInputStream(callback, blocks, done)

        drv_mic.set_input_factory(factory)
        return drv_mic.mic_always_on_start(**kwargs), done

    def _wait_fed(self, done: threading.Event) -> None:
        """等全部块喂完并处理完（回调内同步落盘，feed_done 即终态）。"""
        self.assertTrue(done.wait(timeout=5.0), "fake stream 未在 5s 内喂完块")

    def test_always_on_writes_vad_gated_segments(self):
        # 三段式音频 → 常开 → VAD 门控落盘 2 个语音段（静音区零存储）
        out, done = self._start_with(synth_pcm(THREE_PHASE))
        self.assertIn("OK", out, out)
        self._wait_fed(done)
        st = drv_mic.mic_status()
        self.assertIn("always_on=True", st)
        self.assertIn("ring_seconds=120", st)  # 默认容量
        wavs = sorted(self._td.glob("seg-*.wav"))
        self.assertEqual(len(wavs), 2, [p.name for p in wavs])
        for w in wavs:  # 每段都是可解析的 16kHz 单声道 PCM16 WAV
            with wave.open(str(w)) as f:
                self.assertEqual(f.getframerate(), SR)
                self.assertEqual(f.getnchannels(), 1)
                self.assertEqual(f.getsampwidth(), 2)
                self.assertGreaterEqual(f.getnframes(), SR // 10)  # ≥1 块

    def test_rewind_returns_recent_audio_wav(self):
        # rewind(15)：环形缓冲全部 1.4s 都在 15s 内 → 帧数 ≈ 喂入总时长
        out, done = self._start_with(synth_pcm(THREE_PHASE))
        self._wait_fed(done)
        res = drv_mic.mic_rewind(seconds=15)
        m = re.match(r"OK rewound (\S+) \((\d+) samples\)", res)
        self.assertIsNotNone(m, res)
        path = Path(m.group(1))
        self.assertTrue(path.exists(), str(path))
        self.assertIn("rewind-", path.name)
        with wave.open(str(path)) as f:
            self.assertEqual(f.getframerate(), SR)
            self.assertAlmostEqual(f.getnframes() / SR, 1.4, delta=0.1)
        # rewind(1)：只取最近 1s 环形缓冲尾部
        res1 = drv_mic.mic_rewind(seconds=1)
        m1 = re.match(r"OK rewound (\S+) \((\d+) samples\)", res1)
        self.assertIsNotNone(m1, res1)
        with wave.open(str(m1.group(1))) as f:
            self.assertAlmostEqual(f.getnframes() / SR, 1.0, delta=0.05)

    def test_rewind_without_start_reports_enotactive(self):
        res = drv_mic.mic_rewind(seconds=15)
        self.assertIn("ENOTACTIVE", res)
        self.assertIn("always_on not running", res)

    def test_disabled_by_env_permission_error(self):
        # 隐私红线：LAOS_REC=0 全局禁录（EACCES）
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            with self.assertRaises(PermissionError):
                drv_mic.mic_always_on_start()

    def test_stop_flush_and_status_off(self):
        out, done = self._start_with(synth_pcm(THREE_PHASE))
        self._wait_fed(done)
        before = sorted(p.name for p in self._td.glob("seg-*.wav"))
        self.assertEqual(len(before), 2)
        stop = drv_mic.mic_always_on_stop()
        self.assertIn("OK", stop, stop)
        st = drv_mic.mic_status()
        self.assertIn("always_on=False", st)
        self.assertIn("ring_seconds=0", st)
        # 收尾 flush 复用 _listen_loop 语义：已落盘段不丢、不崩
        after = sorted(p.name for p in self._td.glob("seg-*.wav"))
        self.assertEqual(after, before)
        # 环形缓冲已清空 + 线程已停 → rewind 报 ENOTACTIVE
        self.assertIn("ENOTACTIVE", drv_mic.mic_rewind(seconds=15))

    def test_restart_after_stop_uses_new_thread(self):
        # 停止后重入 always_on_start 可再次启动（线程不复用，段序号不回绕）
        out1, done1 = self._start_with(synth_pcm(THREE_PHASE))
        self._wait_fed(done1)
        first_th = drv_mic._always_on_thread
        self.assertIsNotNone(first_th)
        self.assertTrue(first_th.is_alive())
        drv_mic.mic_always_on_stop()
        out2, done2 = self._start_with(synth_pcm([("v", 300), ("s", 400)]))
        self.assertIn("OK", out2, out2)
        self._wait_fed(done2)
        second_th = drv_mic._always_on_thread
        self.assertIsNotNone(second_th)
        self.assertIsNot(first_th, second_th)  # 全新线程，非复用
        wavs = sorted(self._td.glob("seg-*.wav"))
        self.assertEqual(len(wavs), 3, [p.name for p in wavs])  # 2 + 新会话 1
        drv_mic.mic_always_on_stop()

    def test_ring_seconds_capped_at_600(self):
        # 内存上限红线：ring_seconds ≤ 600
        blocks: list[bytes] = []
        done = threading.Event()

        def factory(samplerate, blocksize, dtype, callback):
            return FakeInputStream(callback, blocks, done)

        drv_mic.set_input_factory(factory)
        out = drv_mic.mic_always_on_start(ring_seconds=99999)
        self.assertIn("ring_seconds=600", out, out)
        self.assertIn("ring_seconds=600", drv_mic.mic_status())
        drv_mic.mic_always_on_stop()

    def test_status_reports_always_on_fields(self):
        # 闲置态也要如实上报（字段常在，值为关闭态）
        st = drv_mic.mic_status()
        self.assertIn("always_on=False", st)
        self.assertIn("ring_seconds=0", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
