"""drv_npu —— NPU/加速器驱动测试（路线 C 桌面原型）。

    python -m unittest tests.test_npu_driver -v
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402


class NpuDriverCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        # 钉大风险预算：npu.infer 每次计 2，别让默认车队预算（3）抢先拒
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=20)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver("npu", [sys.executable, str(REPO / "drivers" / "drv_npu.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def _call(self, pid, tool, args):
        return asyncio.run(self.kernel.syscall(pid, tool, args))


class TestNpuDriver(NpuDriverCase):
    def test_devices_registered_in_syscall_table(self):
        self.assertIn("npu.devices", self.kernel.syscalls())
        self.assertIn("npu.infer", self.kernel.syscalls())

    def test_devices_lists_stub_and_qnn(self):
        pcb = self._spawn(["npu.*"])
        res = self._call(pcb.pid, "npu.devices", {})
        self.assertTrue(res.ok, res.error)
        self.assertIn("stub", res.text)
        # 本机 QAIRT SDK 存在时 qnn-cpu 可用；否则报告不可用——两种都是合法输出
        self.assertTrue("qnn-cpu" in res.text)

    def test_infer_stub_returns_seven_classes(self):
        pcb = self._spawn(["npu.*"])
        # 显式钉 stub：装有 QAIRT 的机器上 auto 会选 qnn-cpu（ENOSYS，见路线 A）
        res = self._call(pcb.pid, "npu.infer",
                         {"model": "timnet", "input": "audio-feature-26x479",
                          "backend": "stub"})
        self.assertTrue(res.ok, res.error)
        self.assertIn("backend=stub", res.text)
        self.assertIn("top1=", res.text)
        # 确定性：同输入同输出
        res2 = self._call(pcb.pid, "npu.infer",
                          {"model": "timnet", "input": "audio-feature-26x479",
                           "backend": "stub"})
        self.assertEqual(res.text, res2.text)

    def test_infer_charges_risk_ledger(self):
        pcb = self._spawn(["npu.*"])
        before = self.kernel.risk.spent
        # 尝试定价：计费发生在内核闸门（授权即计费），驱动层结果不影响账单
        self._call(pcb.pid, "npu.infer", {"model": "timnet", "input": "x",
                                          "backend": "stub"})
        self.assertEqual(self.kernel.risk.spent, before + 2)  # 功耗定价 cost=2
        self.assertEqual(pcb.stats["risk"], 2)

    def test_infer_denied_without_caps(self):
        pcb = self._spawn(["sys.*"])
        res = self._call(pcb.pid, "npu.infer", {"model": "t", "input": "x"})
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)

    def test_qnn_cpu_backend_reports_enosys(self):
        pcb = self._spawn(["npu.*"])
        res = self._call(pcb.pid, "npu.infer",
                         {"model": "timnet", "input": "x", "backend": "qnn-cpu"})
        # 本机装了 QAIRT：库能加载但图级绑定未实现 → ENOSYS；
        # 未装 QAIRT：EIO load failed。两者都不是成功。
        self.assertFalse(res.ok)
        self.assertTrue("ENOSYS" in res.text or "EIO" in res.text, res.text)

    def test_unknown_backend_rejected(self):
        pcb = self._spawn(["npu.*"])
        res = self._call(pcb.pid, "npu.infer",
                         {"model": "t", "input": "x", "backend": "gpu-quantum"})
        self.assertFalse(res.ok)
        self.assertIn("EINVAL", res.text)


class TestDeviceTransport(unittest.TestCase):
    """真机闭环的 laos 侧：LAOS_NPU_ENDPOINT 指向 HTTP 端点时走真机推理。

    用 stdlib 起一个模拟"App InferenceServer"的端点，验证驱动的 HTTP 传输
    与计费；真实设备端点由 App 的 InferenceServer.kt 提供（同一 JSON 协议）。
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=20)
        self.endpoint_calls: list[bytes] = []

        import http.server
        import threading

        drv_root = REPO / "drivers"
        self._drv = None

        class MockDevice(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/health":
                    body = json.dumps({"status": "ok", "model": "timnet-lpai",
                                       "initialized": True}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                self_server = self
                self_server.server.endpoint_calls.append(body)
                probs = [0.4, 0.1, 0.05, 0.05, 0.3, 0.05, 0.05]
                out = json.dumps({
                    "probs": probs,
                    "labels": ["Anger", "Boredom", "Disgust", "Fear",
                               "Happiness", "Neutral", "Sadness"],
                    "latency_ms": 6.1, "top1": "Happiness",
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MockDevice)
        self.server.endpoint_calls = self.endpoint_calls
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        port = self.server.server_address[1]

        self._prev_endpoint = os.environ.get("LAOS_NPU_ENDPOINT")
        os.environ["LAOS_NPU_ENDPOINT"] = f"http://127.0.0.1:{port}"

        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_NPU_ENDPOINT": f"http://127.0.0.1:{port}"}
        self.kernel.load_driver("npu", [sys.executable, str(drv_root / "drv_npu.py")],
                                env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self.server.shutdown(); self.server.server_close()
        if self._prev_endpoint is None:
            os.environ.pop("LAOS_NPU_ENDPOINT", None)
        else:
            os.environ["LAOS_NPU_ENDPOINT"] = self._prev_endpoint
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def test_devices_reports_healthy_device(self):
        pcb = self._spawn(["npu.*"])
        res = asyncio.run(self.kernel.syscall(pcb.pid, "npu.devices", {}))
        self.assertIn("device-timnet", res.text)
        self.assertIn("initialized=True", res.text)

    def test_infer_over_device_transport(self):
        import base64
        pcb = self._spawn(["npu.*"])
        pcm = (b"\x00\x01" * 160)  # 160 帧 PCM16 假音频
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "npu.infer",
            {"model": "timnet", "input": base64.b64encode(pcm).decode(),
             "backend": "device"}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("backend=device-timnet", res.text)
        self.assertIn("latency=", res.text)
        self.assertIn("top1=Happiness", res.text)
        # 真机端点确实收到了 base64 PCM（闭环证据）
        self.assertEqual(len(self.endpoint_calls), 1)
        self.assertIn("samples_b64", self.endpoint_calls[0])
        # 计费：真机推理同样消耗功耗预算
        self.assertEqual(pcb.stats["risk"], 2)

    def test_device_unreachable_fails_clean(self):
        # 驱动在 import 时读端点——用不可达端点单独起一个驱动实例来测降级
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_NPU_ENDPOINT": "http://127.0.0.1:9"}  # discard 端口，不可达
        self.kernel.load_driver("npu-dead", [sys.executable, str(REPO / "drivers" / "drv_npu.py")],
                                env=env)
        pcb = self._spawn(["npu.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "npu.infer",
            {"model": "timnet", "input": base64.b64encode(b"\x00\x01").decode(),
             "backend": "device"}))
        self.assertFalse(res.ok)
        self.assertIn("E", res.text[:12])  # errno 前缀（EIO/ECONNREFUSED/URLError 家族）


if __name__ == "__main__":
    unittest.main(verbosity=2)
