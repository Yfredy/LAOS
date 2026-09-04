"""多 Agent 公平复用 Brain（LLM 是最贵资源）。

受 AIOS Scheduler 启发：把全局锁升级为带 priority 的时间片轮转 + 每 agent token 预算。

    python -m unittest tests.test_scheduler -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.scheduler import AgentScheduler  # noqa: E402


class TestAgentScheduler(unittest.TestCase):
    def test_fair_round_robin(self):
        s = AgentScheduler()
        s.register(1, priority=0)
        s.register(2, priority=0)
        order = []
        for _ in range(4):
            for pid in (1, 2):
                if s.acquire(pid):
                    order.append(pid)
                    s.release(pid)
        # 严格交替，无饥饿
        self.assertEqual(order, [1, 2, 1, 2, 1, 2, 1, 2])

    def test_token_budget_suspends(self):
        s = AgentScheduler()
        s.register(7, priority=0, token_budget=10)
        self.assertTrue(s.acquire(7))
        s.note_tokens(7, 10)  # 用尽预算
        s.release(7)
        self.assertFalse(s.acquire(7))  # 超额挂起，不让思考

    def test_priority_preempts(self):
        s = AgentScheduler()
        s.register(1, priority=0)
        s.register(2, priority=1)  # 高优先级
        self.assertTrue(s.acquire(2))
        s.release(2)
        self.assertEqual(s.next_pid(), 2)  # 高优先级优先


if __name__ == "__main__":
    unittest.main()
