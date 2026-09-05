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

    def test_score_high_denial_rate_positive(self):
        # 规则② 正例：n=5、拒绝 3 次（0.6 > 0.5）-> high denial rate: 3/5
        recs = [{"t": 1.0, "event": "spawn", "pid": 2001, "name": "sloppy"}]
        for i, ok in enumerate([False, False, False, True, True]):
            recs.append({"t": 1.1 + i * 0.1, "event": "syscall", "pid": 2001,
                         "agent": "sloppy", "tool": "fs.read",
                         "args": {"path": f"/p{i}"}, "ok": ok, "ms": 1.0,
                         "result": "ok" if ok else "[error] EACCES: x"})
        flags = score(build_spans(recs)[0])
        self.assertTrue(any("high denial rate: 3/5" in f for f in flags))

    def test_score_tool_monoculture_positive(self):
        # 规则④ 正例：n=6、fs.read 5 次（5/6 > 0.8）-> tool monoculture: fs.read (5/6)
        recs = [{"t": 2.0, "event": "spawn", "pid": 2002, "name": "reader"}]
        for i in range(5):
            recs.append({"t": 2.1 + i * 0.1, "event": "syscall", "pid": 2002,
                         "agent": "reader", "tool": "fs.read",
                         "args": {"path": f"/p{i}"}, "ok": True, "ms": 1.0,
                         "result": "ok"})
        recs.append({"t": 2.7, "event": "syscall", "pid": 2002, "agent": "reader",
                     "tool": "fs.stat", "args": {"path": "/p0"}, "ok": True,
                     "ms": 1.0, "result": "ok"})
        flags = score(build_spans(recs)[0])
        self.assertTrue(any("tool monoculture: fs.read (5/6)" in f for f in flags))


class TestOtlpExport(unittest.TestCase):
    def test_export_shape(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            spans = build_spans(_recs())
            paths = export_otlp(spans, Path(td) / "traces")
            self.assertEqual(len(paths), 1)
            doc = json.loads(paths[0].read_text(encoding="utf-8"))
            rs = doc["resourceSpans"][0]
            attrs = {a["key"]: a["value"] for a in rs["resource"]["attributes"]}
            self.assertEqual(attrs["laos.pid"]["intValue"], 1001)
            spans_list = rs["scopeSpans"][0]["spans"]
            self.assertEqual(len(spans_list), 4)
            first = spans_list[0]
            self.assertEqual(len(first["traceId"]), 32)
            self.assertEqual(len(first["spanId"]), 16)
            self.assertIn(first["status"]["code"],
                          ("STATUS_CODE_OK", "STATUS_CODE_ERROR"))
            denied = [s for s in spans_list if s["status"]["code"] == "STATUS_CODE_ERROR"]
            self.assertEqual(len(denied), 1)
            self.assertEqual(denied[0]["name"], "proc.exec")
            # R206：审计 t 是 time.time() 亚秒浮点，每个 syscall 有自己的时刻——
            # 起点必须随调用严格递增（_recs() 的 t 两两不同），终点 >= 起点。
            starts = [int(s["startTimeUnixNano"]) for s in spans_list]
            for a, b in zip(starts, starts[1:]):
                self.assertLess(a, b, f"startNs 未严格递增: {starts}")
            for s in spans_list:
                self.assertGreaterEqual(int(s["endTimeUnixNano"]),
                                        int(s["startTimeUnixNano"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
