# tests/test_jev_skills.py
"""技能沉淀质量闸（Task 5，opt-in）+ laosd 装配代理。

judge= 不传（默认）时 learn_from_result 行为与现状一致（用例③钉住）；
显式传入判断后端后，record(...) 先问一句
noul(task, 题首"此任务轨迹确实达成了目标吗？"+判据段，criteria 式)
——deny（= 轨迹没达成目标）不沉淀返回 None，技能库不新增。

装配层（bin/laosd.py）：JevGatedMemory 代理把 judge 按条目类型接到
存储边界（kind=="skill" 走 LAOS_JEV_SKILL 的沉淀闸，其余 kind 走
LAOS_JEV_MEM 的入库闸），agent.py / kernel mem.* 零改动；kernel 的
mem.remember 对"judge 拒绝 → remember 返回 None"必须 None-safe（EDENIED
而不是 TypeError）。

    python -m unittest tests.test_jev_skills -v
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
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包，路径注入以便 import laosd

from laos.judge import JudgeResult, SafeJudge, env_flag  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402
from laos.memory import MemoryStore  # noqa: E402
from laos.skills import SKILL_JUDGE_QUESTION, SkillStore  # noqa: E402


def _result(ok=True, denied=0, syscalls=2, trace=None, answer="done", pid=1):
    """构造最小 AgentResult 形状（duck typing，避免循环导入）。"""

    class _R:
        pass

    r = _R()
    r.ok = ok
    r.denied = denied
    r.syscalls = syscalls
    r.trace = trace if trace is not None else [
        {"step": 1, "syscall": "fs.read", "args": {"path": "/f"}, "ret": "x"},
        {"step": 2, "syscall": "fs.append", "args": {"path": "/f"}, "ret": "OK"},
    ]
    r.answer = answer
    r.pid = pid
    return r


class FakeJudge:
    """注入消费点的桩后端：返回预置 JudgeResult 并记录调用。"""

    def __init__(self, verdict: str):
        self.verdict = verdict
        self.calls: list[tuple[str, str]] = []

    def noul(self, context: str, question: str) -> JudgeResult:
        self.calls.append((context, question))
        return JudgeResult(self.verdict, 0.9)


class TestSkillJevGate(unittest.TestCase):
    """record(...) 的三用例：deny 不沉淀 / allow 新增 / 无 judge 现状一致。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(Path(self._td.name) / "memory.jsonl")
        self.store = SkillStore(self.memory)

    def tearDown(self):
        self._td.cleanup()

    def test_judge_deny_skips_distillation(self):
        # ① deny（轨迹没达成目标）→ 不沉淀：返回 None、技能库零新增、零落盘
        fake = FakeJudge("deny")
        rec = self.store.learn_from_result(_result(), "确保 hosts 有记录",
                                           judge=fake)
        self.assertIsNone(rec)
        self.assertEqual(self.memory.stats()["total"], 0)
        self.assertFalse(self.memory.path.exists(), "deny 时不得落盘")
        # 问句钉关键词不钉全文（全文由 test_calibrate_judge 的 import
        # 契约钉）：context 精确 + 题首 10 字 + 判据结构 + deny 方向
        context, question = fake.calls[0]
        self.assertEqual(context, "确保 hosts 有记录")
        self.assertTrue(question.startswith(SKILL_JUDGE_QUESTION[:10]))
        self.assertIn("；判“否”", question)
        self.assertIn("deny，不沉淀", question)

    def test_judge_allow_distills(self):
        # ② allow → 新增一条 skill（record 与 learn_from_result 同一入口语义）
        fake = FakeJudge("allow")
        rec = self.store.record(_result(), "确保 hosts 里有 myapp.local 记录",
                                judge=fake)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["kind"], "skill")
        self.assertEqual(self.memory.stats()["total"], 1)
        context, question = fake.calls[0]
        self.assertEqual(context, "确保 hosts 里有 myapp.local 记录")
        self.assertTrue(question.startswith(SKILL_JUDGE_QUESTION[:10]))
        self.assertIn("deny，不沉淀", question)

    def test_without_judge_unchanged(self):
        # ③ 不传 judge → 与现状一致：既有门控照旧、无条件入库返回 dict
        rec = self.store.learn_from_result(_result(), "确保 hosts 有记录")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["kind"], "skill")
        self.assertEqual(self.memory.stats()["total"], 1)


class TestLaosdWiring(unittest.TestCase):
    """bin/laosd.py 装配层：JevGatedMemory 代理 + wire_judge + kernel None-safe。"""

    def setUp(self):
        import laosd  # bin/ 非包，模块头已做路径注入
        self.laosd = laosd
        self._env = mock.patch.dict(os.environ)
        self._env.start()
        for key in ("LAOS_JEV_BACKEND", "LAOS_JEV_AUTOGATE",
                    "LAOS_JEV_PREVIEW", "LAOS_JEV_MEM", "LAOS_JEV_COMPACT",
                    "LAOS_JEV_SKILL"):
            os.environ.pop(key, None)
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: False)
        self.kernel.branches.create_root("main")
        self.pcb = self.kernel.spawn(name="wire", caps=["mem.*"],
                                     ctx=object(), branch="main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()
        self._env.stop()

    def test_env_flag_truthy_values_only(self):
        # 存在即真曾是 bug（遗留 A）：只有 1/true/yes（大小写不敏感）为真
        for value in ("1", "true", "TRUE", "Yes", " yes "):
            with mock.patch.dict(os.environ, {"LAOS_JEV_X": value}):
                self.assertTrue(env_flag("LAOS_JEV_X"), value)
        for value in ("0", "false", "no", "off", "", "  "):
            with mock.patch.dict(os.environ, {"LAOS_JEV_X": value}):
                self.assertFalse(env_flag("LAOS_JEV_X"), value)
        self.assertFalse(env_flag("LAOS_JEV_UNSET_KEY"))

    def test_wire_judge_none_is_noop(self):
        # BACKEND=none（默认）：不构造后端、不包代理，kernel 属性原样
        judge_before = self.kernel.judge
        self.assertIsNone(self.laosd.wire_judge(self.kernel))
        self.assertIs(self.kernel.judge, judge_before)
        self.assertIsInstance(self.kernel.memory, MemoryStore)

    def test_wire_judge_wraps_safe_and_gates_memory(self):
        # BACKEND=rule + MEM=1 → kernel.judge 换成 SafeJudge、memory 换成代理
        os.environ["LAOS_JEV_BACKEND"] = "rule"
        os.environ["LAOS_JEV_MEM"] = "1"
        safe = self.laosd.wire_judge(self.kernel)
        self.assertIsInstance(safe, SafeJudge)
        self.assertIs(self.kernel.judge, safe)
        self.assertIsInstance(self.kernel.memory, self.laosd.JevGatedMemory)
        proxy = self.kernel.memory
        self.assertIsNone(proxy.skill_judge, "未开 LAOS_JEV_SKILL 不拦沉淀")
        self.assertIs(proxy.mem_judge, safe)
        # 后端是 rule（无 deny 词）→ fact 入库放行，行为与无 judge 一致
        rec = self.kernel.memory.remember("fact", "用户偏好中文回复")
        self.assertIsNotNone(rec)

    def test_proxy_splits_mem_and_skill_gates(self):
        # 代理按条目类型分流：skill 闸 deny 只拦 kind=="skill"，fact 照常
        store = MemoryStore(self.workdir / "m-proxy.jsonl")
        fake = FakeJudge("deny")
        proxy = self.laosd.JevGatedMemory(store, skill_judge=fake)
        self.assertIsNone(proxy.remember("skill", "任务 ⇒ done"))
        self.assertIsNotNone(proxy.remember("fact", "普通事实"))
        self.assertEqual(store.stats()["by_kind"], {"fact": 1})
        context, question = fake.calls[0]
        self.assertEqual(context, "任务 ⇒ done")
        self.assertTrue(question.startswith(SKILL_JUDGE_QUESTION[:10]))
        self.assertIn("deny，不沉淀", question)
        # recall/stats 透传
        self.assertEqual(proxy.stats()["total"], 1)

    def test_kernel_mem_remember_none_safe(self):
        # judge 拒绝 → 代理返回 None：mem.remember syscall 必须 EDENIED
        # 而不是在 rec["id"] 上炸 TypeError
        self.kernel.memory = self.laosd.JevGatedMemory(
            MemoryStore(self.workdir / "m-deny.jsonl"),
            mem_judge=FakeJudge("deny"))
        res = asyncio.run(self.kernel.syscall(
            self.pcb.pid, "mem.remember", {"kind": "fact", "text": "x"}))
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.error)
        self.assertEqual(self.kernel.memory.stats()["total"], 0)
        denied = [r for r in self.kernel.audit.records
                  if r.get("event") == "memory" and r.get("denied")]
        self.assertEqual(len(denied), 1, "拒绝路径必须留审计")


if __name__ == "__main__":
    unittest.main(verbosity=2)
