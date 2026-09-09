"""drv_npu —— NPU/加速器驱动测试（路线 C 桌面原型）。

    python -m unittest tests.test_npu_driver -v
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
