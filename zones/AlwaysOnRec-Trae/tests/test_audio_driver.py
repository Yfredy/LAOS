"""drv_audio —— 语音增强驱动测试（ModelScope 重依赖在驱动子进程内）。

    python -m unittest tests.test_audio_driver -v

真实推理用 .venv-audio 的 python 跑（本机已部署并缓存模型）；优雅降级用
当前解释器（无 modelscope）验证"缺依赖时报错不崩"。
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

VENV_PY = REPO / ".venv-audio" / "Scripts" / "python.exe"
HAS_VENV = VENV_PY.exists()


@unittest.skipUnless(HAS_VENV, "需要 .venv-audio（modelscope/torch 音频栈）")
class TestAudioDriverReal(unittest.TestCase):
    """真实推理（venv python 子进程，模型已缓存）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=20)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver(
            "audio", [str(VENV_PY), str(REPO / "drivers" / "drv_audio.py")], env=env)
        self.kernel.branches.create_root("main")
        # 8kHz 双音混合输入（标准库 wave 合成：确定性、无网络、无依赖）
        import math
        import wave
        wav_path = self.workdir / "mix.wav"
        self.workdir.mkdir(parents=True, exist_ok=True)
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            frames = bytearray()
            for i in range(16000):  # 2.0s @ 8kHz
                v = 0.5 * math.sin(2 * math.pi * 300 * i / 8000) \
                    + 0.5 * math.sin(2 * math.pi * 800 * i / 8000)
                frames += int(v * 26000).to_bytes(2, "little", signed=True)
            w.writeframes(bytes(frames))
        self.mix_wav = str(wav_path)

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def _call(self, pid, tool, args):
        return asyncio.run(self.kernel.syscall(pid, tool, args))

    def test_models_listed(self):
        pcb = self._spawn(["audio.*"])
        res = self._call(pcb.pid, "audio.models", {})
        self.assertTrue(res.ok, res.error)
        self.assertIn("separate", res.text)
        self.assertIn("aec", res.text)

    def test_real_separation_through_kernel(self):
        pcb = self._spawn(["audio.*"])
        res = self._call(pcb.pid, "audio.separate", {"wav": self.mix_wav})
        self.assertTrue(res.ok, res.error)
        self.assertIn("OK separated", res.text)
        self.assertIn("_spk1.wav", res.text)
        # 分离产物真实存在且为 8kHz（标准库 wave 验证，测试进程零依赖）
        out1 = Path(res.text.split("-> ")[1].split(",")[0].strip())
        self.assertTrue(out1.exists())
        import wave
        with wave.open(str(out1), "rb") as w:
            self.assertEqual(w.getframerate(), 8000)
            self.assertEqual(w.getnframes(), 16000)  # 2.0s @ 8kHz

    def test_denied_without_caps(self):
        pcb = self._spawn(["sys.*"])
        res = self._call(pcb.pid, "audio.separate", {"wav": self.mix_wav})
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)


class TestGracefulNoModelscope(unittest.TestCase):
    """裸解释器（无 modelscope）下驱动可加载、models 列表可答、推理报错不崩。"""

    def setUp(self):
        if HAS_VENV and VENV_PY == Path(sys.executable):
            self.skipTest("当前解释器即 venv（含 modelscope），无法测降级")
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver(
            "audio", [sys.executable, str(REPO / "drivers" / "drv_audio.py")], env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_models_without_modelscope(self):
        pcb = self.kernel.spawn(name="a", caps=["audio.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "audio.models", {}))
        self.assertTrue(res.ok, res.error)  # 列表不需要重依赖

    def test_separate_reports_missing_dep(self):
        pcb = self.kernel.spawn(name="a", caps=["audio.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "audio.separate",
                                              {"wav": "nonexistent.wav"}))
        self.assertFalse(res.ok)
        self.assertTrue("No module named" in res.text or "ENOENT" in res.text,
                        res.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
