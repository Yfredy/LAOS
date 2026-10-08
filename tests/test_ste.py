# tests/test_ste.py
"""ste —— 约束语言 lint（ASD-STE100 原则的 check-only 可测子集）。

方法论源自 Karpathy 2026-10-02 帖（x.com/karpathy/status/2105819303471976479）：
让 LLM 用 ASD-STE100 写——航空航天维修文档约束语言（~900 批准词、one
word one meaning），输出"a lot more readable"。官方词表再分发受限（ASD
许可），本模块只取原则不收词表（同 github.com/danyuchn/asd-ste100-skill
的取舍，MIT）；且**只检查不改写**——简化是有损变换，问题报告必须带
原文摘录，原始文本永远权威（与 jitmem"绝不截断原文"同一原则族）。

    python -m unittest tests.test_ste -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import os

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.ste import lint  # noqa: E402

CLEAN = (
    "用户偏好中文回复。\n"
    "mem.remember 把事实写入记忆库。\n"
    "每次调用都留审计记录。"
)


class TestSteLint(unittest.TestCase):
    def test_clean_text_passes(self):
        self.assertEqual(lint(CLEAN), [])

    def test_empty_text_passes(self):
        self.assertEqual(lint(""), [])
        self.assertEqual(lint("\n\n"), [])

    def test_r1_long_sentence_detected(self):
        long = "这是一句" + "很" * 80 + "长的句子。"
        problems = lint(long)
        self.assertTrue(problems)
        p = problems[0]
        self.assertIn("R1", p["rule"])
        self.assertIn("句长", p["rule"])
        self.assertTrue(p["detail"])       # 带"X 字 > 上限"式明细
        self.assertTrue(p["excerpt"])      # 带原文摘录（不改写原则）

    def test_r1_boundary_at_limit(self):
        ok = "好" * 60 + "。"
        self.assertEqual([p for p in lint(ok) if "R1" in p["rule"]], [])
        over = "好" * 61 + "。"
        self.assertTrue([p for p in lint(over) if "R1" in p["rule"]])

    def test_sentence_splitting_covers_punctuations(self):
        # 。！？!? 与换行都是句界；每句独立检查
        text = "好" * 70 + "！短句。" + "好" * 70 + "？"
        r1 = [p for p in lint(text) if "R1" in p["rule"]]
        self.assertEqual(len(r1), 2)

    def test_r2_synonym_rotation(self):
        # Karpathy 原痛点：agent/worker/executor 混用
        text = "The agent calls memory. The executor writes audit. The worker exits."
        problems = lint(text)
        r2 = [p for p in problems if "R2" in p["rule"]]
        self.assertEqual(len(r2), 1)
        self.assertIn("agent", r2[0]["detail"])
        self.assertIn("executor", r2[0]["detail"])

    def test_r2_single_form_no_problem(self):
        text = "The agent calls memory. The agent writes audit."
        self.assertEqual([p for p in lint(text) if "R2" in p["rule"]], [])

    def test_r2_custom_groups_and_disable(self):
        text = "先调用 foo，再调用 bar。"
        custom = lint(text, term_groups=[("foo", "bar")])
        self.assertTrue([p for p in custom if "R2" in p["rule"]])
        none = lint(text, term_groups=[])
        self.assertEqual([p for p in none if "R2" in p["rule"]], [])
        disabled = lint(text, term_groups=[("foo", "bar")], rules=("R1",))
        self.assertEqual(disabled, [])

    def test_r3_multi_clause_sentence(self):
        four = "先取数据，再清洗，然后入库，最后汇报。"
        problems = lint(four)
        self.assertTrue([p for p in problems if "R3" in p["rule"]])
        three = "先取数据，再清洗，然后入库。"
        self.assertEqual([p for p in lint(three) if "R3" in p["rule"]], [])

    def test_r4_hedge_stack(self):
        stacked = "这个方案可能大概是可行的。"
        problems = lint(stacked)
        self.assertTrue([p for p in problems if "R4" in p["rule"]])
        single = "这个方案可能是可行的。"
        self.assertEqual([p for p in lint(single) if "R4" in p["rule"]], [])
        # hedge 不跨句叠加
        spread = "这可能是对的。那大概也是对的。"
        self.assertEqual([p for p in lint(spread) if "R4" in p["rule"]], [])

    def test_r5_semicolon_flagged(self):
        problems = lint("先做甲；再做乙。")
        r5 = [p for p in problems if "R5" in p["rule"]]
        self.assertEqual(len(r5), 1)
        # 半角分号同样报；一句多分号逐个报
        self.assertEqual(len([p for p in lint("甲；乙；丙。") if "R5" in p["rule"]]), 2)

    def test_deterministic_order_by_position(self):
        text = "好" * 70 + "；好" + "。也许可能也许可能这样吧。"
        ps = lint(text)
        self.assertEqual([p["pos"] for p in ps], sorted(p["pos"] for p in ps))
        self.assertEqual(ps[0]["rule"][:2], "R1")  # 位置 0 的句长问题在最前
        # R2 文档级检查（pos=-1）永远在最前
        self.assertEqual(
            lint("agent 与 worker 并存\n" + "好" * 70 + "。")[0]["rule"][:2], "R2")

    def test_max_sentence_chars_configurable(self):
        text = "好" * 40 + "。"
        self.assertEqual([p for p in lint(text) if "R1" in p["rule"]], [])
        tight = lint(text, max_sentence_chars=20)
        self.assertTrue([p for p in tight if "R1" in p["rule"]])


class TestSteCli(unittest.TestCase):
    def _run(self, content: str) -> subprocess.CompletedProcess:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(content)
            path = fh.name
        try:
            return subprocess.run(
                [sys.executable, "-m", "laos.ste", path],
                capture_output=True, text=True, cwd=str(REPO))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_cli_clean_exit_zero(self):
        r = self._run(CLEAN)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("通过", r.stdout)

    def test_cli_problems_exit_one_with_rule_lines(self):
        r = self._run("好" * 80 + "。")
        self.assertEqual(r.returncode, 1)
        self.assertIn("R1", r.stdout)


class TestKernelSteHook(unittest.TestCase):
    """LAOS_STE_LINT=1 时 mem.curate 的 briefing 过 ste lint，问题数入审计。

    只检查不改写：payload 文本原样返回给 agent，审计只多一个计数字段。
    """

    def setUp(self):
        import asyncio

        from laos.context import ContextManager
        from laos.kernel import AgentKernel
        self._asyncio = asyncio
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var",
                                  confirm=lambda op: True)
        self.kernel.branches.create_root("main")
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        self.pcb = self.kernel.spawn(name="a", caps=["mem.*"], ctx=ctx,
                                     branch="main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _curate_row(self):
        asyncio = self._asyncio
        res = asyncio.run(self.kernel.syscall(
            self.pcb.pid, "mem.remember",
            {"kind": "fact", "text": "好" * 80, "tags": ["甲"]}))
        self.assertTrue(res.ok, res.error)
        res = asyncio.run(self.kernel.syscall(
            self.pcb.pid, "mem.curate", {"task": "甲事"}))
        self.assertTrue(res.ok, res.error)
        rows = [r for r in self.kernel.audit.records
                if r.get("event") == "memory" and r.get("op") == "curate"]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_enabled_records_problem_count(self):
        with mock.patch.dict(os.environ, {"LAOS_STE_LINT": "1"}):
            row = self._curate_row()
        self.assertGreaterEqual(row.get("ste_problems", 0), 1)  # 80 字长句必中 R1

    def test_disabled_by_default_no_field(self):
        row = self._curate_row()
        self.assertNotIn("ste_problems", row)


if __name__ == "__main__":
    unittest.main()
