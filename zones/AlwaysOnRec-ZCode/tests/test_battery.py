# tests/test_battery.py
"""动态功耗定价 —— 电池状态驱动风险成本乘数 + 电池驱动。

    python -m unittest tests.test_battery -v
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


class BatteryKernelCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=["npu.*"], ctx=ctx, branch="main")


class TestDynamicPricing(BatteryKernelCase):
    def setUp(self):
        super().setUp()
        # 手动注册一个 cost=2 的规格（不加载驱动子进程——计费发生在内核风险闸门，
        # 派发失败不影响账单，这本身就是"尝试定价"语义的一部分）
        from laos.mcp import ToolSpec
        self.kernel.syscall_table["npu.infer"] = (
            "npu", ToolSpec("npu.infer", "推理", {"type": "object",
                            "properties": {"x": {"type": "string"}}},
                            reversible=False, risk="medium",
                            irreversibility_cost=2))
        self.pcb = self.kernel.spawn(name="a", caps=["npu.*"],
                                     ctx=ContextManager(system_prompt="t",
                                                        max_tokens=2000),
                                     branch="main")

    def test_default_multiplier_is_one(self):
        self.assertEqual(self.kernel.risk.multiplier, 1.0)
        before = self.kernel.risk.spent
        asyncio.run(self.kernel.syscall(self.pcb.pid, "npu.infer", {"x": "y"}))
        self.assertEqual(self.kernel.risk.spent - before, 2)

    def test_low_battery_multiplier_triples_cost(self):
        self.kernel.set_pricing_multiplier(3.0)
        before = self.kernel.risk.spent
        asyncio.run(self.kernel.syscall(self.pcb.pid, "npu.infer", {"x": "y"}))
        self.assertEqual(self.kernel.risk.spent - before, 6)  # 2 × 3.0

    def test_pricing_change_audited(self):
        self.kernel.set_pricing_multiplier(3.0)
        events = [r for r in self.kernel.audit.records
                  if r.get("event") == "pricing"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["multiplier"], 3.0)


class TestBatteryDriverParse(unittest.TestCase):
    def test_parse_termux_output(self):
        from drivers.drv_battery import parse_termux_battery
        out = '{"percentage": 37, "status": "DISCHARGING"}'
        self.assertEqual(parse_termux_battery(out),
                         {"percent": 37, "charging": False})

    def test_parse_app_json(self):
        from drivers.drv_battery import parse_app_battery
        self.assertEqual(parse_app_battery('{"percent": 80, "charging": true}'),
                         {"percent": 80, "charging": True})


if __name__ == "__main__":
    unittest.main(verbosity=2)
