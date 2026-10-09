# tests/test_evolve.py
"""evolve —— 受治理进化作业面离线测试：gate 路径政策 / job-result 契约 /
ENODEV 装配面 / payload round-trip。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v

来源：docs/research/2026-10-09-rsi-landscape.md §8 裁决 #2（自改写防线）；
装配面哲学同 laos/decide.py（drv_clef 先例）。
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.evolve import (EvolveGate, EvolveJob, EvolveResult,  # noqa: E402
                         register_executor, run_job)
from laos.kernel import AgentKernel, CapabilitySet, PCB  # noqa: E402


def _job(**kw):
    base = dict(target="var/rsi/jobs/demo/initial_program.py",
                evaluator="var/rsi/jobs/demo/evaluator.py", iterations=10)
    base.update(kw)
    return EvolveJob(**base)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.gate = EvolveGate(roots=("var/rsi/jobs",))

    def test_inside_root_passes(self):
        self.gate.check(_job())  # 不抛即过

    def test_outside_root_is_eperm(self):
        with self.assertRaises(ValueError) as cm:
            self.gate.check(_job(target="laos/kernel.py"))
        self.assertIn("EPERM", str(cm.exception))

    def test_dotdot_escape_is_eperm(self):
        with self.assertRaises(ValueError):
            self.gate.check(_job(target="var/rsi/jobs/../../laos/kernel.py"))

    def test_separator_edge_no_false_prefix(self):
        with self.assertRaises(ValueError):  # jobs2 不得借道 jobs 前缀
            self.gate.check(_job(target="var/rsi/jobs2/x.py"))

    def test_iterations_bounds_are_einval(self):
        for bad in (0, -1, 501):
            with self.assertRaises(ValueError) as cm:
                self.gate.check(_job(iterations=bad))
            self.assertIn("EINVAL", str(cm.exception))


class TestRunJob(unittest.TestCase):
    def setUp(self):
        # 全量发现按字母序先跑 test_drv_evolve（import 即全局登记执行器），
        # 这里 setUp 也清一次，保证 ENODEV 用例不受污染
        import laos.evolve as ev
        ev._executors.clear()

    def tearDown(self):
        # 清掉本类注册的执行器，避免污染其他测试
        import laos.evolve as ev
        ev._executors.clear()

    def test_enODEV_without_driver(self):
        with self.assertRaises(RuntimeError) as cm:
            run_job(_job())
        self.assertIn("ENODEV", str(cm.exception))

    def test_registered_executor_roundtrip(self):
        seen = {}

        def fake(job):
            seen["job"] = job
            return EvolveResult(0.87, "var/rsi/jobs/demo/out.py",
                                "ab" * 32, 10, 1.5, "var/rsi/jobs/demo")

        register_executor(fake)
        result = run_job(_job())
        self.assertEqual(result.best_score, 0.87)
        self.assertEqual(seen["job"].iterations, 10)


class TestPayload(unittest.TestCase):
    def _payload(self):
        return {"best_score": 0.5, "best_program_path": "var/rsi/jobs/d/o.py",
                "best_program_sha256": "cd" * 32, "iterations_completed": 9,
                "elapsed_s": 2.0, "artifacts_dir": "var/rsi/jobs/d"}

    def test_roundtrip(self):
        r = EvolveResult.from_payload(self._payload())
        self.assertEqual(r.best_program_sha256, "cd" * 32)

    def test_bad_types_fail_loud(self):
        bad = self._payload()
        bad["best_score"] = "high"
        with self.assertRaises(ValueError):
            EvolveResult.from_payload(bad)
        bad2 = self._payload()
        bad2["iterations_completed"] = -1
        with self.assertRaises(ValueError):
            EvolveResult.from_payload(bad2)


class TestEnvRoots(unittest.TestCase):
    """env 红线：LAOS_EVOLVE_ROOTS 只能扩非禁区根，禁区永不可经 env 放行。"""

    def test_env_expands_allow_roots(self):
        with mock.patch.dict(os.environ, {"LAOS_EVOLVE_ROOTS": "var/custom"},
                             clear=False):
            EvolveGate().check(_job(target="var/custom/prog.py",
                                    evaluator="var/custom/eval.py"))  # 不抛即过

    def test_forbidden_root_still_rejected_under_env(self):
        with mock.patch.dict(os.environ, {"LAOS_EVOLVE_ROOTS": "laos"},
                             clear=False):
            with self.assertRaises(ValueError) as cm:
                EvolveGate().check(_job(target="laos/kernel.py"))
        self.assertIn("EPERM", str(cm.exception))
        self.assertIn("禁区", str(cm.exception))

    def test_deep_dotdot_escape_is_eperm(self):
        with self.assertRaises(ValueError) as cm:
            EvolveGate().check(
                _job(target="var/rsi/jobs/../../../../laos/kernel.py"))
        self.assertIn("EPERM", str(cm.exception))


class TestEvolveSyscall(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: False)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()
        import laos.evolve as ev
        ev._executors.clear()

    def _pcb(self, caps):
        pcb = PCB(pid=1, name="evo", caps=CapabilitySet(caps), budget=None)
        self.k.procs[1] = pcb
        return pcb

    def _args(self):
        return {"target": "var/rsi/jobs/d/initial_program.py",
                "evaluator": "var/rsi/jobs/d/evaluator.py", "iterations": 5}

    def test_eperm_without_cap(self):
        self._pcb([])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)

    def test_enODEV_without_driver(self):
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertFalse(res.ok)
        self.assertIn("ENODEV", res.error)

    def test_ok_with_fake_executor_and_audit(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        import json as _json
        payload = _json.loads(res.text)
        self.assertEqual(payload["best_score"], 0.9)
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertTrue(events and events[-1]["sha256"] == "ab" * 32)

    def test_gate_violation_fails_not_crashes(self):
        self._pcb(["evolve.*"])
        bad = self._args()
        bad["target"] = "laos/kernel.py"
        res = asyncio.run(self.k.syscall(1, "evolve.run", bad))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)


if __name__ == "__main__":
    unittest.main()
