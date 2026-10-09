# tests/test_evolve.py
"""evolve —— 受治理进化作业面离线测试：gate 路径政策 / job-result 契约 /
ENODEV 装配面 / payload round-trip。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v

来源：docs/research/2026-10-09-rsi-landscape.md §8 裁决 #2（自改写防线）；
装配面哲学同 laos/decide.py（drv_clef 先例）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.evolve import (EvolveGate, EvolveJob, EvolveResult,  # noqa: E402
                         RewardSpec, aggregate, register_executor, run_job)
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

    def test_optional_reward_fields_roundtrip(self):
        p = self._payload()
        p["reward_version"] = "aurase-4222"
        p["reward_detail"] = {"OVRL": 3.367, "WER": 8.22, "weights": "4:2:2:2"}
        r = EvolveResult.from_payload(p)
        self.assertEqual(r.reward_version, "aurase-4222")
        self.assertEqual(r.reward_detail["WER"], 8.22)

    def test_legacy_payload_without_reward_still_constructs(self):
        r = EvolveResult.from_payload(self._payload())  # 旧六字段
        self.assertEqual(r.reward_version, "")
        self.assertIsNone(r.reward_detail)

    def test_null_reward_version_becomes_empty(self):
        p = self._payload()
        p["reward_version"] = None
        r = EvolveResult.from_payload(p)
        self.assertEqual(r.reward_version, "")


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
        import laos.evolve as _ev
        _ev._executors.clear()  # 顺序无关护栏（同 TestRunJob）
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

    def test_oserror_from_executor_is_eio(self):
        # 终审 I3：驱动没转换的裸 OSError（WinError 5 拒绝访问 / 路径
        # 超长）不得击穿 syscall 网关——内核兜成 EIO（MCP 路径 blanket
        # except → EIO 同款口径）
        def boom(job):
            raise PermissionError(5, "WinError 5 拒绝访问")

        register_executor(boom)
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertFalse(res.ok)
        self.assertIn("EIO", res.error)
        self.assertIn("OSError", res.error)

    def test_audit_records_reward_version_when_present(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d",
            reward_version="aurase-4222"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertEqual(events[-1].get("reward_version"), "aurase-4222")

    def test_audit_omits_reward_version_when_absent(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertNotIn("reward_version", events[-1])


class TestEvolveRunYieldsLoop(unittest.TestCase):
    """终审 C1：evolve.run 是首个阻塞型内建——派发须让出事件循环。

    作业在飞（执行器卡在 threading.Event 上）时，同 kernel 的快 syscall
    （mem.stats）必须先行返回；随后放行作业、双结果与审计行完好。
    """

    def setUp(self):
        import laos.evolve as _ev
        _ev._executors.clear()  # 顺序无关护栏（同 TestEvolveSyscall）
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: False)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()
        import laos.evolve as ev
        ev._executors.clear()

    def test_evolve_run_does_not_freeze_loop(self):
        entered = threading.Event()
        release = threading.Event()

        def blocking(job):
            entered.set()              # 已进 worker 线程，"作业"开跑
            release.wait(timeout=3.0)  # 3s：若派发没让出循环，失败点在
                                       # 顺序断言而非无限挂死
            return EvolveResult(0.5, "var/rsi/jobs/d/out.py", "ab" * 32,
                                job.iterations, 1.0, "var/rsi/jobs/d")

        register_executor(blocking)
        self.k.procs[1] = PCB(pid=1, name="evo",
                              caps=CapabilitySet(["evolve.*", "mem.*"]))
        args = {"target": "var/rsi/jobs/d/i.py",
                "evaluator": "var/rsi/jobs/d/e.py", "iterations": 5}

        async def scenario():
            evolve_task = asyncio.create_task(
                self.k.syscall(1, "evolve.run", args))
            for _ in range(1000):  # 等 worker 真正进入执行器（≤10s 硬上限）
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(entered.is_set(), "阻塞执行器未被进入：派发没上路")
            # 关键断言：evolve 仍在飞（release 未置位），快 syscall 先回
            quick = await asyncio.wait_for(self.k.syscall(1, "mem.stats"),
                                           timeout=5.0)
            self.assertFalse(evolve_task.done(),
                             "mem.stats 不应被 evolve.run 押后")
            release.set()
            return quick, await evolve_task

        quick, evolve_res = asyncio.run(scenario())
        self.assertTrue(quick.ok, getattr(quick, "error", quick))
        self.assertIn("total=", quick.text)
        self.assertTrue(evolve_res.ok, getattr(evolve_res, "error", evolve_res))
        # 审计完好：每行皆整 JSON、seq 连续无重号（写锁钉住的不变式）、
        # 两条 syscall 行都在、evolve 行字段齐全、快行先落账
        lines = [ln for ln in
                 self.k.audit.path.read_text(encoding="utf-8").splitlines()
                 if ln]
        rows = [json.loads(ln) for ln in lines]  # 逐行可解析 = 行完整性
        self.assertEqual([r["seq"] for r in rows], list(range(len(rows))))
        tools = [(i, r["tool"]) for i, r in enumerate(rows)
                 if r.get("event") == "syscall" and r.get("ok")]
        tool_names = [t for _, t in tools]
        self.assertIn("mem.stats", tool_names)
        self.assertIn("evolve.run", tool_names)
        ms = next(i for i, t in tools if t == "mem.stats")
        er = next(i for i, t in tools if t == "evolve.run")
        self.assertLess(ms, er)  # 快 syscall 先落账
        ev_rows = [r for r in rows if r.get("event") == "evolve"]
        self.assertTrue(ev_rows and ev_rows[-1]["sha256"] == "ab" * 32)


class TestRewardSpec(unittest.TestCase):
    def test_valid_spec(self):
        s = RewardSpec({"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0},
                       frozenset({"WER"}), version="aurase-4222")
        self.assertEqual(s.version, "aurase-4222")

    def test_empty_or_nonpositive_weights_rejected(self):
        for bad in ({}, {"OVRL": 0.0}, {"OVRL": -1.0}):
            with self.assertRaises(ValueError) as cm:
                RewardSpec(bad)
            self.assertIn("EINVAL", str(cm.exception))

    def test_lower_better_must_be_subset(self):
        with self.assertRaises(ValueError):
            RewardSpec({"OVRL": 1.0}, frozenset({"WER"}))

    def test_blank_version_rejected(self):
        with self.assertRaises(ValueError):
            RewardSpec({"OVRL": 1.0}, version="")

    def test_nan_and_inf_weights_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError) as cm:
                RewardSpec({"OVRL": bad})
            self.assertIn("EINVAL", str(cm.exception))


class TestAggregate(unittest.TestCase):
    # 调研文档 §3 手算例的独立复算（与复现区测试各自独立，不共享代码）：
    # OVRL [3.0,3.2,3.4]→[0,.5,1]；WER(lower) [.10,.08,.12]→[.5,1,0]；
    # SIM [.70,.75,.75]→[0,1,1]；SBS [.90,.90,.88]→[1,1,0]；
    # 4:2:2:2（和 10）→ cand0=0.3 / cand1=0.8 / cand2=0.6
    CANDS = {
        "c0": {"OVRL": 3.0, "WER": 0.10, "SIM": 0.70, "SBS": 0.90},
        "c1": {"OVRL": 3.2, "WER": 0.08, "SIM": 0.75, "SBS": 0.90},
        "c2": {"OVRL": 3.4, "WER": 0.12, "SIM": 0.75, "SBS": 0.88},
    }
    SPEC = RewardSpec({"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0},
                      frozenset({"WER"}), version="aurase-4222")

    def test_hand_computed_4222(self):
        r = aggregate(self.CANDS, self.SPEC)
        self.assertEqual(
            [round(r["c0"], 10), round(r["c1"], 10), round(r["c2"], 10)],
            [0.3, 0.8, 0.6])

    def test_winner_not_ovrl_best(self):
        # 4:2:2:2 下总分王 c1 不是 OVRL 最高的 c2——保真 60% 拉回内容
        r = aggregate(self.CANDS, self.SPEC)
        self.assertEqual(max(r, key=r.get), "c1")

    def test_constant_metric_is_neutral_full(self):
        # brief 笔误修正：b 的 F 原为 0.9（与"双指标无区分度"矛盾，
        # 0.9≠0.5 有区分度会得 {'a': 0.5, 'b': 1.0}）；按测试名/注释/
        # 断言三处一致意图 + 复现区 test_constant_is_neutral_full
        # （[5.0, 5.0]）口径，改为常量 0.5
        cands = {"a": {"Q": 1.0, "F": 0.5}, "b": {"Q": 1.0, "F": 0.5}}
        spec = RewardSpec({"Q": 1.0, "F": 1.0}, version="t")
        self.assertEqual(aggregate(cands, spec),
                         {"a": 1.0, "b": 1.0})  # 双指标无区分度 → 中性满分

    def test_rewards_within_unit(self):
        r = aggregate(self.CANDS, self.SPEC)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in r.values()))
        # 全指标垫底的候选恰好得 0.0（值域闭端）
        worst = {"w": {m: (max(c[m] for c in self.CANDS.values())
                           if m == "WER" else
                           min(c[m] for c in self.CANDS.values()))
                       for m in self.SPEC.weights}}
        merged = dict(self.CANDS, **worst)
        self.assertEqual(aggregate(merged, self.SPEC)["w"], 0.0)


if __name__ == "__main__":
    unittest.main()
