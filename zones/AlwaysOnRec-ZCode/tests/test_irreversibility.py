"""不可逆操作预算 + 人类确认准入（升级 AIOS ask_permission 的提示性确认）。

AIOS 的 ask_permission 弹窗不自动拒绝；laos 内核强制：
- 每条 tool 标 reversible/risk
- 不可逆操作消耗 irreversibility budget，预算是硬上限（耗尽直接 EACCES）
- risk=high 还需人类一次性确认（confirm 注入，测试用 mock）

    python -m unittest tests.test_irreversibility -v
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.kernel import AgentKernel, CapabilitySet, PCB  # noqa: E402
from laos.mcp import ToolSpec  # noqa: E402


class TestIrreversibility(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             irreversibility_budget=1, confirm=lambda op: False)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()

    def _proc_pcb(self):
        self.k.syscall_table["proc.exec"] = ("proc",
            ToolSpec("proc.exec", "exec", {"type": "object",
                     "properties": {"cmdline": {"type": "string"}}, "required": ["cmdline"]},
                     reversible=False, risk="high"))
        pcb = PCB(pid=1, name="a", caps=CapabilitySet(["proc.*"]), budget=None)
        self.k.procs[1] = pcb
        return pcb

    def test_high_risk_blocked_without_confirm(self):
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "rm -rf /"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)

    def test_confirm_true_allows(self):
        self.k.confirm = lambda op: True
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "echo hi"}))
        # 只有 spec 没有真驱动，会走到 EIO，但确认分支应通过（不返回 EACCES）
        self.assertNotIn("EACCES", res.error)

    def test_budget_depletes(self):
        self.k.confirm = lambda op: True
        self.k.irreversibility_budget = 0  # 预算耗尽：硬上限，确认也不放行
        self._proc_pcb()
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"cmdline": "echo hi"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)


if __name__ == "__main__":
    unittest.main()
