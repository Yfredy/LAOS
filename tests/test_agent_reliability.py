# tests/test_agent_reliability.py
"""Agent 主循环可靠性：温度阶梯 / 重试上限 / 重复 syscall 检测（第一波）。

    python -m unittest tests.test_agent_reliability -v
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agent import Agent  # noqa: E402
from laos.brain import Brain, Thought, ToolCall  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

DRIVERS = REPO / "drivers"


class _RecordingBrain(Brain):
    """记录每次 think 收到的 temperature，按脚本返回 Thought。"""

    name = "recording"

    def __init__(self, script):
        self.script = script
        self.temperatures: list[float] = []
        self.calls = 0

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        self.temperatures.append(temperature)
        idx = min(self.calls, len(self.script) - 1)
        self.calls += 1
        item = self.script[idx]
        if callable(item):
            return item()
        return item


class ReliabilityTestCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        for name in ("fs", "proc", "sys"):
            self.kernel.load_driver(
                name, [sys.executable, str(DRIVERS / f"drv_{name}.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        ws = self.main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def spawn(self, brain, caps=("sys.*",)):
        ctx = ContextManager(system_prompt="test", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name="t", caps=list(caps), ctx=ctx, branch="main")
        return Agent(self.kernel, pcb, brain)


class TestRetryLadder(ReliabilityTestCase):
    def test_ladder_then_success(self):
        bad = Thought(text="参数坏了", retryable=True)
        good = Thought(text="", tool_calls=[ToolCall("sys.info", {}, "c1")])
        done = Thought(text="完成", finish=True)
        brain = _RecordingBrain([bad, bad, good, done])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查一下环境"))
        # 三轮重试阶梯 + 收尾 done 轮（0）：共 4 次 think
        self.assertEqual(brain.temperatures, [0, 0.4, 0.8, 0])
        self.assertTrue(res.ok)
        self.assertGreaterEqual(res.syscalls, 1)

    def test_gives_up_after_two_retries(self):
        brain = _RecordingBrain([Thought(text="还是坏", retryable=True)])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查一下环境"))
        self.assertEqual(brain.calls, 3)
        self.assertEqual(brain.temperatures, [0, 0.4, 0.8])
        self.assertFalse(res.ok)
        self.assertIn("连续 3 轮", res.answer)
        self.assertEqual(res.syscalls, 0)

    def test_success_resets_retry_count(self):
        bad = Thought(text="坏", retryable=True)
        good = Thought(text="", tool_calls=[ToolCall("sys.info", {}, "c1")])
        done = Thought(text="完成", finish=True)
        brain = _RecordingBrain([bad, good, bad, good, done])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查两轮环境"))
        self.assertTrue(res.ok)
        # 两段各一次重试：0 → 0.4 →（成功重置）→ 0 → 0.4，
        # 收尾 done 轮再记一个 0
        self.assertEqual(brain.temperatures, [0, 0.4, 0, 0.4, 0])


class _FixedCallBrain(Brain):
    """永远发起同一个 syscall，绝不 finish（用于重复检测）。"""

    name = "fixed"

    def __init__(self, name="sys.info", arguments=None):
        self._name = name
        self._args = arguments or {}

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        return Thought(text="再试一次",
                       tool_calls=[ToolCall(self._name, dict(self._args), "c1")])


class _AlternatingArgsBrain(Brain):
    """同一工具但参数交替变化（不构成"原样重复"）。"""

    name = "alternating"

    def __init__(self):
        self._n = 0

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        self._n += 1
        return Thought(text="",
                       tool_calls=[ToolCall("sys.info",
                                            {"n": self._n}, f"c{self._n}")])


class TestRepeatGuard(ReliabilityTestCase):
    def _notices(self, ctx):
        return [m for m in ctx.messages
                if m.get("role") == "user"
                and str(m.get("content", "")).startswith("[kernel-notice]")]

    def test_third_identical_call_triggers_notice(self):
        brain = _FixedCallBrain()
        agent = self.spawn(brain)
        asyncio.run(agent.run("反复查询环境"))
        notices = self._notices(agent.pcb.ctx)
        self.assertEqual(len(notices), 1)
        self.assertIn("重复动作警告", notices[0]["content"])
        self.assertIn("sys.info", notices[0]["content"])
        self.assertIn("必须更换策略", notices[0]["content"])
        self.assertIn("禁止原样重试", notices[0]["content"])

    def test_varying_args_never_triggers(self):
        brain = _AlternatingArgsBrain()
        agent = self.spawn(brain)
        asyncio.run(agent.run("每轮不同参数"))
        self.assertEqual(self._notices(agent.pcb.ctx), [])

    def test_notice_fires_once_not_every_step(self):
        brain = _FixedCallBrain()
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("反复查询环境"))
        # max_steps=12 默认：同一 call 发 12 次，通告只在第 3 次出现一次
        self.assertEqual(res.steps, 12)
        self.assertEqual(len(self._notices(agent.pcb.ctx)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
