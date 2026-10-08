# tests/test_traceviz.py
"""traceviz —— 审计日志 → mermaid 时序图（"架构、调用链一张图看懂"）。

方法论源自 Karpathy 2026-10-02 帖第二阶梯：向模型要图表而不是文字——
"a lot easier to process, parse, and understand"。laos 的对应物：内核
审计是权威调用链记录，traceviz 把它转成 mermaid sequenceDiagram 的
**只读派生视图**——不改写审计、审计永远是权威源（派生物与原始的双层
结构，见 docs/research/2026-10-08-readable-output.md）。

    python -m unittest tests.test_traceviz -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.traceviz import to_mermaid  # noqa: E402


def syscall_event(pid=1, agent="a", tool="mem.remember", ok=True,
                  err=None, t=1000.0, **extra):
    ev = {"t": t, "event": "syscall", "pid": pid, "agent": agent,
          "tool": tool, "ok": ok}
    if err:
        ev["result"] = err
    ev.update(extra)
    return ev


class TestToMermaid(unittest.TestCase):
    def test_empty_records_minimal_diagram(self):
        out = to_mermaid([])
        self.assertTrue(out.startswith("sequenceDiagram"))

    def test_single_ok_syscall(self):
        out = to_mermaid([syscall_event()])
        self.assertIn("sequenceDiagram", out)
        self.assertIn("participant K as kernel", out)
        self.assertIn("P1", out)
        self.assertIn("P1->>K: mem.remember", out)
        self.assertIn("K-->>P1: ok", out)

    def test_failed_syscall_cross_arrow_with_error(self):
        out = to_mermaid([syscall_event(ok=False, err="EPERM: no cap")])
        self.assertIn("K--xP1: EPERM", out)

    def test_multiple_agents_distinct_participants(self):
        recs = [syscall_event(pid=1, agent="ear", tool="mic.open", t=1.0),
                syscall_event(pid=2, agent="web", tool="msg.send", t=2.0)]
        out = to_mermaid(recs)
        self.assertIn("participant P1 as ear(1)", out)
        self.assertIn("participant P2 as web(2)", out)

    def test_agent_name_sanitized_for_mermaid(self):
        # 名字里的 : ; \n 会破坏 mermaid 语法，必须清洗
        out = to_mermaid([syscall_event(agent="bad:name;\nnext")])
        self.assertIn("participant P1 as bad", out)
        self.assertNotIn(":", out.split("participant P1 as bad")[1].split("\n")[0])

    def test_tail_caps_recent_window(self):
        recs = [syscall_event(pid=1, tool=f"tool{i}", t=float(i))
                for i in range(5)]
        out = to_mermaid(recs, tail=3)
        self.assertIn("tool2", out)
        self.assertIn("tool4", out)
        self.assertNotIn("tool0", out)
        self.assertNotIn("tool1", out)

    def test_non_syscall_events_ignored(self):
        recs = [syscall_event(),
                {"t": 1.0, "event": "memory", "op": "remember", "pid": 1},
                {"t": 2.0, "event": "spawn", "pid": 3}]
        out = to_mermaid(recs)
        self.assertEqual(out.count("->>K:"), 1)

    def test_pid_without_agent_falls_back(self):
        out = to_mermaid([{"t": 1.0, "event": "syscall", "pid": 7,
                           "tool": "mem.stats", "ok": True}])
        self.assertIn("participant P7 as ?(7)", out)


class TestCli(unittest.TestCase):
    def test_module_main_prints_diagram(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            fh.write('{"t":1,"event":"syscall","pid":1,"agent":"a",'
                     '"tool":"mem.remember","ok":true}\n')
            path = fh.name
        try:
            r = subprocess.run(
                [sys.executable, "-m", "laos.traceviz", path],
                capture_output=True, text=True, cwd=str(REPO))
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sequenceDiagram", r.stdout)
        self.assertIn("mem.remember", r.stdout)

    def test_laosctl_subcommand(self):
        with tempfile.TemporaryDirectory() as td:
            audit = Path(td) / "audit.jsonl"
            audit.write_text(
                '{"t":1,"event":"syscall","pid":1,"agent":"a",'
                '"tool":"mem.curate","ok":true}\n', encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(REPO / "bin" / "laosctl.py"),
                 "traceviz", "--file", str(audit)],
                capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sequenceDiagram", r.stdout)
        self.assertIn("mem.curate", r.stdout)


if __name__ == "__main__":
    unittest.main()
