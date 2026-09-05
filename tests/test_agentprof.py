# tests/test_agentprof.py
"""AgentProf —— 审计流 → 语义 span + OTLP/JSON 导出（零依赖）。

    python -m unittest tests.test_agentprof -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agentprof import build_spans, score, export_otlp  # noqa: E402


def _recs():
    return [
        {"t": 1.0, "event": "spawn", "pid": 1001, "name": "ops", "caps": ["fs.*"]},
        {"t": 1.1, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.read",
         "args": {"path": "/main/f"}, "ok": True, "ms": 5.0, "result": "data", "driver": "fs"},
        {"t": 1.2, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.read",
         "args": {"path": "/main/f"}, "ok": True, "ms": 4.0, "result": "data", "driver": "fs"},
        {"t": 1.3, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "fs.write",
         "args": {"path": "/main/f"}, "ok": True, "ms": 6.0, "result": "OK", "driver": "fs"},
        {"t": 1.4, "event": "syscall", "pid": 1001, "agent": "ops", "tool": "proc.exec",
         "args": {"cmdline": "ls"}, "ok": False, "ms": 1.0, "result": "[error] EACCES: x"},
        {"t": 2.0, "event": "syscall", "pid": 9999, "agent": "ghost", "tool": "fs.read",
         "args": {}, "ok": True, "ms": 1.0, "result": ""},
    ]


class TestBuildSpans(unittest.TestCase):
    def test_groups_by_pid_and_ignores_orphans(self):
        spans = build_spans(_recs())
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].pid, 1001)
        self.assertEqual(spans[0].name, "ops")
        self.assertEqual(len(spans[0].calls), 4)
        self.assertEqual(spans[0].denied, 1)
        self.assertAlmostEqual(spans[0].total_ms, 16.0)

    def test_repeat_detection(self):
        spans = build_spans(_recs())
        reps = spans[0].repeats
        self.assertEqual(len(reps), 1)
        self.assertEqual(reps[0]["tool"], "fs.read")
        self.assertEqual(reps[0]["count"], 2)

    def test_score_flags(self):
        spans = build_spans(_recs())
        flags = score(spans[0])
        self.assertTrue(any("wasteful repeat: fs.read x2" in f for f in flags))
        self.assertTrue(any("tool monoculture" not in f for f in flags))  # 3/4 未到 0.8


if __name__ == "__main__":
    unittest.main(verbosity=2)
