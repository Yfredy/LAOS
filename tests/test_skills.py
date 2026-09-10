# tests/test_skills.py
"""技能库 —— 成功任务序列沉淀为可复用技能（越用越聪明）。

    python -m unittest tests.test_skills -v
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
from laos.skills import SkillStore, digest_trace  # noqa: E402

DRIVERS = REPO / "drivers"


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


class TestDigestTrace(unittest.TestCase):
    def test_deterministic_and_shaped(self):
        trace = [
            {"step": 1, "syscall": "fs.read", "args": {"path": "/f"}},
            {"step": 2, "syscall": "fs.append", "args": {"path": "/f"}},
        ]
        self.assertEqual(digest_trace(trace), "fs.read(path)→fs.append(path)")
        self.assertEqual(digest_trace(trace), digest_trace(trace))

    def test_skips_non_syscall_entries(self):
        trace = [
            {"step": 1, "say": "thinking..."},
            {"step": 2, "syscall": "sys.info", "args": {}},
        ]
        self.assertEqual(digest_trace(trace), "sys.info()")


class TestSkillStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        from laos.memory import MemoryStore
        self.memory = MemoryStore(Path(self._td.name) / "memory.jsonl")
        self.store = SkillStore(self.memory)

    def tearDown(self):
        self._td.cleanup()

    def test_learn_gates(self):
        self.assertIsNone(self.store.learn_from_result(_result(ok=False), "任务"))
        self.assertIsNone(self.store.learn_from_result(_result(denied=1), "任务"))
        self.assertIsNone(self.store.learn_from_result(_result(syscalls=1), "任务"))
        rec = self.store.learn_from_result(_result(), "确保 hosts 里有记录")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["kind"], "skill")

    def test_learn_includes_signature_in_tags(self):
        rec = self.store.learn_from_result(_result(), "任务")
        self.assertTrue(rec["tags"][0].startswith("fs.read"))

    def test_match_filters_skill_kind(self):
        self.store.learn_from_result(_result(), "确保 hosts 里有 myapp.local 记录")
        self.memory.remember("fact", "用户偏好中文回复")
        got = self.store.match("hosts 里的 myapp 记录", k=3)
        self.assertGreaterEqual(len(got), 1)
        self.assertTrue(all(m["kind"] == "skill" for m in got))


class TestAgentSkillIntegration(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(self.workdir / "branches")}
        self.kernel.load_driver("fs", [sys.executable, str(DRIVERS / "drv_fs.py")], env=env)
        self.kernel.branches.create_root("main")
        ws = self.main_workspace = self.kernel.branches.get("main").workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name):
        from laos.brain import ScriptedBrain
        ctx = ContextManager(system_prompt="t", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name=name, caps=["fs.*"], ctx=ctx, branch="main")
        from laos.agent import Agent
        return Agent(self.kernel, pcb, ScriptedBrain(branch="main"))

    def test_second_run_gets_skill_hint(self):
        agent1 = self._spawn("a1")
        res1 = asyncio.run(agent1.run("确保 hosts 里有 myapp.local 记录"))
        self.assertTrue(res1.ok, res1.answer)
        # 成功任务已沉淀为技能
        skills = self.kernel.memory.stats()["by_kind"].get("skill", 0)
        self.assertGreaterEqual(skills, 1)
        # 第二次 run 的上下文里应出现 [skill-hint]
        agent2 = self._spawn("a2")
        res2 = asyncio.run(agent2.run("确保 hosts 里有 myapp.local 记录"))
        self.assertTrue(res2.ok, res2.answer)
        hints = [m for m in agent2.pcb.ctx.messages
                 if m["role"] == "user" and str(m.get("content", "")).startswith("[skill-hint]")]
        self.assertGreaterEqual(len(hints), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
