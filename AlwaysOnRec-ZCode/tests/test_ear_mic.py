"""drv_mic（录音）+ drv_ear（ASR 双通道）—— 听觉驱动测试。

    python -m unittest tests.test_ear_mic -v

解释器约定（与 Task 全局约束一致）：
  - 本测试文件用裸 uv python 跑（无 sounddevice/funasr）——验证两个驱动
    惰性导入、缺重依赖时优雅降级；
  - 真录音 / 真 ASR 用 conda python 子进程（sounddevice/funasr 所在），
    skipUnless 守卫，模型/解释器缺席时跳过而非失败。

隐私红线：mic.* 每一次 syscall 都在内核审计里留 event:"mic" 记录；
监听线程只能被 mic.listen_start 显式拉起，驱动无自启动线程。
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import sys
import tempfile
import threading
import time
import unittest
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_ear  # noqa: E402
import drv_mic  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

#: 重依赖所在的 conda python（sounddevice/funasr 栈）与 SenseVoice 模型缓存
CONDA_PY = Path("C:/Users/yaoyue/miniconda3/python.exe")
SV_MODEL = Path(
    "D:/ldf/sensevoice_asr/models/models/iic--SenseVoiceSmall/snapshots/master")
SV_VAD = Path(
    "D:/ldf/sensevoice_asr/models/models/"
    "iic--speech_fsmn_vad_zh-cn-16k-common-pytorch/snapshots/master")
HAS_MIC_ENV = CONDA_PY.exists()          # 录音：conda python（sounddevice）
HAS_ASR_ENV = HAS_MIC_ENV and SV_MODEL.exists() and SV_VAD.exists()  # 真 ASR


def _write_wav(path: Path, seconds: float = 1.0, sr: int = 16000,
               amp: float = 0.0) -> Path:
    """stdlib wave 合成 wav（测试进程零依赖）：amp=0 即静音。"""
    n = int(sr * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for i in range(n):
            v = amp * math.sin(2 * math.pi * 440 * i / sr)
            frames += int(v * 32767).to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))
    return path


# --------------------------------------------------------------------------
# 1) split_on_silence 纯函数（无 sounddevice 依赖，直测模块级函数）
# --------------------------------------------------------------------------
class TestSplitOnSilence(unittest.TestCase):
    SR = 8000

    def _synth_v_s_v(self) -> list[int]:
        """[响 0.3s][静 0.5s][响 0.3s] @8kHz int16 —— 正弦 440Hz 幅 8000。"""
        voiced = [int(8000 * math.sin(2 * math.pi * 440 * i / self.SR))
                  for i in range(int(0.3 * self.SR))]
        silence = [0] * int(0.5 * self.SR)
        return voiced + silence + voiced

    def test_two_voiced_segments(self):
        samples = self._synth_v_s_v()
        segs = drv_mic.split_on_silence(samples, self.SR,
                                        threshold_db=-40, min_silence_ms=300)
        self.assertEqual(len(segs), 2, segs)
        # 段 1 覆盖前 0.3s 有声区；段 2 从后半有声区开始直到采样末尾
        self.assertEqual(segs[0][0], 0)
        self.assertLessEqual(segs[0][1], int(0.32 * self.SR))
        self.assertGreaterEqual(segs[1][0], int(0.75 * self.SR))
        self.assertEqual(segs[1][1], len(samples))

    def test_all_silence_no_segments(self):
        segs = drv_mic.split_on_silence([0] * self.SR, self.SR,
                                        threshold_db=-40, min_silence_ms=300)
        self.assertEqual(segs, [])


# --------------------------------------------------------------------------
# 2) ear server 通道：stdlib mock HTTP（模仿 SenseVoice server 响应）
# --------------------------------------------------------------------------
class _MockSenseVoice(BaseHTTPRequestHandler):
    """模仿 D:/ldf/sensevoice_asr/server.py 的 /v1/transcribe 响应形状。"""

    def do_GET(self):  # /health 探活
        payload = b'{"status": "ok", "model": "SenseVoiceSmall"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        m = re.search(rb'name="language"\r\n\r\n([^\r]*)', body)
        lang = m.group(1).decode("utf-8", "replace") if m else "auto"
        out = {
            "text": "今天天气怎么样",
            "language": "zh" if lang in ("auto", "") else lang,
            "emotions": ["NEUTRAL"],
            "inference_time_ms": 12.3,
        }
        payload = json.dumps(out).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # 安静
        pass


class EarServerChannelTest(unittest.TestCase):
    """server 通道全链路：裸 uv python 子进程（零依赖）+ 本地 mock 服务。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _MockSenseVoice)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_ASR_CHANNEL": "server",
            "LAOS_ASR_SERVER": f"http://127.0.0.1:{self.port}",
        }
        self.kernel.load_driver("ear", [sys.executable,
                                        str(REPO / "drivers" / "drv_ear.py")],
                                env=env)
        self.kernel.branches.create_root("main")
        self.wav = _write_wav(self.workdir / "uttr.wav", seconds=1.0)

    def tearDown(self):
        self.kernel.shutdown()
        self.httpd.shutdown()
        self.httpd.server_close()
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def _call(self, pid, tool, args):
        return asyncio.run(self.kernel.syscall(pid, tool, args))

    def test_transcribe_unified_json_shape(self):
        pcb = self._spawn(["ear.*"])
        res = self._call(pcb.pid, "ear.transcribe", {"wav": str(self.wav)})
        self.assertTrue(res.ok, res.error)
        out = json.loads(res.text)
        self.assertIn("text", out)
        self.assertEqual(out["source"], "server")
        self.assertIn("latency_ms", out)
        self.assertIsInstance(out["emotions"], list)
        self.assertIn("language", out)

    def test_status_server_channel(self):
        pcb = self._spawn(["ear.*"])
        res = self._call(pcb.pid, "ear.status", {})
        self.assertTrue(res.ok, res.error)
        self.assertIn("channel=server", res.text)
        self.assertIn("server_reachable=True", res.text)
        self.assertIn("loaded=False", res.text)


class EarStatusFunasrChannelTest(unittest.TestCase):
    """funasr 通道 status（裸 python 也必须可答——不 import funasr）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_ASR_CHANNEL": "funasr",
        }
        self.kernel.load_driver("ear", [sys.executable,
                                        str(REPO / "drivers" / "drv_ear.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_status_reports_channel_and_model_path(self):
        pcb = self.kernel.spawn(name="a", caps=["ear.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "ear.status", {}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("channel=funasr", res.text)
        self.assertIn("loaded=False", res.text)
        # 模型缓存存在与否如实上报（本机为 True；缓存被清的机器上跳过该断言）
        if SV_MODEL.exists():
            self.assertIn("model_path=True", res.text)


# --------------------------------------------------------------------------
# 3) ear funasr 真实通道：conda python + 本机 SenseVoice 缓存
# --------------------------------------------------------------------------
@unittest.skipUnless(HAS_ASR_ENV, "需要 conda python（funasr）与 SenseVoice 模型缓存")
class TestFunasrReal(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_ASR_CHANNEL": "funasr",
        }
        self.kernel.load_driver("ear", [str(CONDA_PY),
                                        str(REPO / "drivers" / "drv_ear.py")],
                                env=env)
        self.kernel.branches.create_root("main")
        self.wav = _write_wav(self.workdir / "silence.wav", seconds=1.0)

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_transcribe_silence_ok_with_text_key(self):
        pcb = self.kernel.spawn(name="a", caps=["ear.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "ear.transcribe",
                                              {"wav": str(self.wav)}))
        self.assertTrue(res.ok, res.error or res.text)
        out = json.loads(res.text)
        self.assertIn("text", out)  # 静音允许空文本
        self.assertEqual(out["source"], "funasr")
        self.assertIn("latency_ms", out)
        self.assertIsInstance(out["emotions"], list)


# --------------------------------------------------------------------------
# 4+5) mic.record 真录音（conda python 子进程保证 sounddevice）+ 隐私审计
# --------------------------------------------------------------------------
@unittest.skipUnless(HAS_MIC_ENV, "需要 conda python（sounddevice）")
class TestMicReal(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver("mic", [str(CONDA_PY),
                                        str(REPO / "drivers" / "drv_mic.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self):
        return self.kernel.spawn(name="a", caps=["mic.*"],
                                 ctx=ContextManager(system_prompt="t"))

    def _record(self, seconds: int = 1):
        pcb = self._spawn()
        return asyncio.run(self.kernel.syscall(
            pcb.pid, "mic.record", {"seconds": seconds}))

    def test_record_real_16k_wav(self):
        res = self._record(seconds=1)
        self.assertTrue(res.ok, res.error or res.text)
        m = re.match(r"OK recorded (\S+) \((\d+) samples\)", res.text)
        self.assertIsNotNone(m, res.text)
        path = Path(m.group(1))
        if not path.is_absolute():
            path = Path.cwd() / path
        self.assertTrue(path.exists(), str(path))
        with wave.open(str(path), "rb") as w:  # 标准库 wave 验证（测试进程零依赖）
            self.assertEqual(w.getframerate(), 16000)
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertAlmostEqual(w.getnframes() / w.getframerate(), 1.0, delta=0.2)

    def test_record_audited_as_mic_event(self):
        before = len([r for r in self.kernel.audit.records
                      if r.get("event") == "mic"])
        res = self._record(seconds=1)
        self.assertTrue(res.ok, res.error or res.text)
        mic_events = [r for r in self.kernel.audit.records
                      if r.get("event") == "mic"]
        self.assertEqual(len(mic_events), before + 1)
        self.assertEqual(mic_events[-1]["tool"], "mic.record")

    def test_listen_start_stop_segments(self):
        pcb = self._spawn()
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mic.listen_start", {"threshold_db": -40}))
        self.assertTrue(res.ok, res.error or res.text)
        # 监听线程异步拉起：status 轮询至 listening=True
        deadline = time.time() + 3
        listening = False
        while time.time() < deadline:
            st = asyncio.run(self.kernel.syscall(pcb.pid, "mic.status", {}))
            if "listening=True" in st.text:
                listening = True
                break
            time.sleep(0.2)
        self.assertTrue(listening, st.text)
        time.sleep(2.0)  # 安静房间：2s 静音 → 0 或 1 段（宽松断言，不崩即可）
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mic.listen_stop", {}))
        self.assertTrue(res.ok, res.error or res.text)
        st = asyncio.run(self.kernel.syscall(pcb.pid, "mic.status", {}))
        self.assertIn("listening=False", st.text)
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mic.segments", {}))
        self.assertTrue(res.ok, res.error or res.text)  # 内容 0/1 段皆可


class TestMicDeniedStillAudited(unittest.TestCase):
    """隐私红线补口子：被内核 _deny 的 mic.* 调用（EPERM 等）同样要留
    event:"mic" 审计（denied:true）——录音意图无论成败都可追责、可计数。
    不需要声卡：驱动加载（惰性导入）+ 能力表拒绝，全程零重依赖。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver("mic", [sys.executable,
                                        str(REPO / "drivers" / "drv_mic.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_denied_mic_record_writes_both_records(self):
        pcb = self.kernel.spawn(name="a", caps=["sys.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mic.record",
                                              {"seconds": 1}))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)
        sys_recs = [r for r in self.kernel.audit.records
                    if r.get("event") == "syscall"
                    and r.get("tool") == "mic.record"]
        mic_recs = [r for r in self.kernel.audit.records
                    if r.get("event") == "mic"]
        self.assertEqual(len(sys_recs), 1)      # 拒绝本身有 syscall 记录
        self.assertFalse(sys_recs[0]["ok"])
        self.assertEqual(len(mic_recs), 1)      # 且有 mic 审计事件
        self.assertTrue(mic_recs[0]["denied"])
        self.assertIn("EPERM", mic_recs[0]["reason"])


class TestMicGracefulNoSounddevice(unittest.TestCase):
    """裸 uv python（无 sounddevice）：驱动可加载、status 可答、record 报错不崩。"""

    def setUp(self):
        if HAS_MIC_ENV and Path(sys.executable).resolve() == CONDA_PY.resolve():
            self.skipTest("当前解释器即 conda python（含 sounddevice），无法测降级")
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver("mic", [sys.executable,
                                        str(REPO / "drivers" / "drv_mic.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_status_without_sounddevice(self):
        pcb = self.kernel.spawn(name="a", caps=["mic.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mic.status", {}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("listening=False", res.text)
        self.assertIn("device=unavailable", res.text)

    def test_record_reports_missing_dep(self):
        pcb = self.kernel.spawn(name="a", caps=["mic.*"],
                                ctx=ContextManager(system_prompt="t"))
        res = asyncio.run(self.kernel.syscall(pcb.pid, "mic.record",
                                              {"seconds": 1}))
        self.assertFalse(res.ok)
        self.assertIn("No module named", res.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
