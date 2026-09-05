# tests/test_risk.py
"""Irreversibility Budget 2.0 —— 车队级风险记账（加权、两级账本、准入控制）。

    python -m unittest tests.test_risk -v
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
from laos.risk import FleetLedger  # noqa: E402


def _spec(name: str = "proc.exec", cost: int = 3, risk: str = "low") -> ToolSpec:
    return ToolSpec(name, "desc",
                    {"type": "object", "properties": {"x": {"type": "string"}}},
                    reversible=False, risk=risk, irreversibility_cost=cost)


class TestFleetLedger(unittest.TestCase):
    def test_remaining_and_admission(self):
        led = FleetLedger(budget=5, reserve=1)
        self.assertEqual(led.remaining, 5)
        self.assertTrue(led.can_admit())
        led.charge(pid=1, tool="proc.exec", cost=3)
        self.assertEqual(led.remaining, 2)
        self.assertEqual(led.spent, 3)
        self.assertEqual(led.per_agent, {1: 3})
        self.assertEqual(led.per_tool, {"proc.exec": 3})
        led.charge(pid=2, tool="proc.exec", cost=2)
        self.assertFalse(led.can_admit())  # remaining=0 <= reserve=1

    def test_charge_accumulates(self):
        led = FleetLedger(budget=10)
        led.charge(1, "t1", 1)
        led.charge(1, "t2", 2)
        led.charge(2, "t1", 3)
        self.assertEqual(led.spent, 6)
        self.assertEqual(led.per_agent, {1: 3, 2: 3})
        self.assertEqual(led.per_tool, {"t1": 4, "t2": 2})


class TestWeightedGate(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: True)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()

    def _mount(self, spec: ToolSpec):
        self.k.syscall_table[spec.name] = ("proc", spec)
        self.k.procs[1] = PCB(pid=1, name="a", caps=CapabilitySet(["proc.*"]),
                              budget=None)

    def test_default_cost_is_one(self):
        self.assertEqual(ToolSpec("x", "d", {}).irreversibility_cost, 1)
        self.assertEqual(ToolSpec("x", "d", {}, irreversibility_cost=3).irreversibility_cost, 3)

    def test_weighted_charge(self):
        self._mount(_spec(cost=3))
        asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        self.assertEqual(self.k.risk.spent, 3)          # 按标注价记账，不是 1
        self.assertEqual(self.k.risk.per_tool["proc.exec"], 3)
        self.assertEqual(self.k.procs[1].stats["risk"], 3)

    def test_fleet_exhaustion_denies(self):
        self.k.risk.budget = 2
        self._mount(_spec(cost=3))
        res = asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("fleet risk budget exhausted", res.error)
        self.assertEqual(self.k.risk.spent, 0)          # 拒绝不计费

    def test_risk_spend_audit_event(self):
        self._mount(_spec(cost=3))
        asyncio.run(self.k.syscall(1, "proc.exec", {"x": "y"}))
        events = [r for r in self.k.audit.records if r.get("event") == "risk_spend"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["cost"], 3)
        self.assertEqual(events[0]["fleet_spent"], 3)
        self.assertEqual(events[0]["agent_spent"], 3)

    def test_legacy_budget_property_roundtrip(self):
        # 兼容契约：test_irreversibility.py 通过该属性置零预算
        self.k.irreversibility_budget = 0
        self.assertEqual(self.k.risk.budget, 0)
        self.assertEqual(self.k.irreversibility_budget, 0)


class TestAgentRiskCap(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: True)
        self.k.syscall_table["proc.exec"] = ("proc", _spec(cost=2))
        # 车队默认预算 3 会抢先触发 fleet 闸门；本类只测 agent 帽，调大隔离干扰
        self.k.risk.budget = 100
        self.td2 = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()
        self.td2.cleanup()

    def _spawn(self, risk_cap):
        return self.k.spawn(name="a", caps=["proc.*"], ctx=object(),
                            risk_cap=risk_cap)

    def test_cap_exceeded_denies_before_confirm(self):
        pcb = self._spawn(risk_cap=1)  # 帽 1 < cost 2
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertFalse(res.ok)
        self.assertIn("agent risk cap exceeded", res.error)
        self.assertEqual(self.k.risk.spent, 0)

    def test_cap_boundary_allows(self):
        pcb = self._spawn(risk_cap=2)  # 帽 == cost，恰好放行
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertNotIn("EACCES", res.error)   # 无真驱动，落到 EIO
        self.assertIn("EIO", res.error)
        self.assertEqual(pcb.stats["risk"], 2)

    def test_cumulative_spend_hits_cap(self):
        pcb = self._spawn(risk_cap=3)
        asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "1"}))   # 0+2 <= 3，计 2
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "2"}))
        self.assertIn("agent risk cap exceeded", res.error)  # 2+2 > 3
        self.assertEqual(self.k.risk.per_agent[pcb.pid], 2)

    def test_no_cap_is_unlimited(self):
        pcb = self._spawn(risk_cap=None)
        res = asyncio.run(self.k.syscall(pcb.pid, "proc.exec", {"x": "y"}))
        self.assertNotIn("EACCES", res.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
