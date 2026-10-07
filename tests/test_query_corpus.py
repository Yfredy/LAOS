# tests/test_query_corpus.py
"""语料查询 CLI（Task 2）：过滤链语义 / query(opts) 契约 / CLI 输出。

brief Step 1 断言逐条覆盖：--topic 按 laos_topic 字段过滤、--strong-only
只取 strong==true（缺省/False 均剔除）、--year 2023-2025 区间含两端、
--grep 对 title+abstract 大小写不敏感、--limit 截断（0=不限）、空结果返回
[]；外加契约：fixture 用 tempfile 注入（不触真实语料）、query(opts) 可
import 复用且返回 list[dict]、--venue 按 venue 字段内容 casefold 包含匹配、
--json 每行一个 JSON（stdout 无杂质）、默认人读表格每行截 80 列、
parse_year 拒绝非法区间、--grep 非法正则走 argparse error（exit 2）、
跨多文件保序合并。纯离线，不触网，不写真实语料目录。
"""
import io
import json
import re
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import query_corpus as qc  # noqa: E402
from query_corpus import parse_year, query  # noqa: E402


def entry(title, abstract=None, **kw):
    e = {"title": title, "year": 2024, "venue": "Interspeech",
         "authors": ["Doe, Jane"], "url": "https://x/1",
         "doi": "10.1/t.1", "abstract": abstract}
    e.update(kw)
    return e


def write(path, entries):
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                            for e in entries), encoding="utf-8")


def opts(**kw):
    """CLI 等价 Namespace；缺省与 argparse 默认一致。"""
    base = dict(topic=None, strong_only=False, venue=None, year=None,
                grep=None, limit=50)
    base.update(kw)
    return Namespace(**base)


def make_corpus(tmp):
    """两个 jsonl、6 行：覆盖 topic/strong/year/grep/limit 全部分支。

    行序即期望保序：a1..a4 在 alpha.jsonl，b1..b2 在 beta.jsonl
    （sorted glob 下 alpha 先读）。
    """
    rows_a = [
        entry("Barge-In Robust Wake Word Detection",   # audio 强，2023
              "full-duplex spoken dialogue with barge-in handling",
              year=2023, laos_topic="audio-speech", strong=True,
              strong_terms=["wake word"]),
        entry("Agent OS Kernel Sandbox",               # agent 弱命中但 strong=False
              "syscall governance for LLM agents",
              year=2025, laos_topic="agent-os", strong=False),
        entry("Binaural Beamforming Privacy",          # spatial，无 strong 字段
              None, year=2024, laos_topic="spatial-privacy"),
        entry("Untopical Paper",                       # 无 topic，年份区间外
              "image style transfer", year=2022),
    ]
    rows_b = [
        entry("Sandboxed Agents Via Syscall Interception",  # agent 强，2025
              "kernel-level quota and isolation",
              year=2025, laos_topic="agent-os", strong=True,
              strong_terms=["kernel sandbox"]),
        entry("VAD For Always-On Audio",               # audio 强，2023
              "voice activity detection", year=2023,
              laos_topic="audio-speech", strong=True),
    ]
    write(Path(tmp) / "alpha.jsonl", rows_a)
    write(Path(tmp) / "beta.jsonl", rows_b)
    return rows_a + rows_b


class QueryFilters(unittest.TestCase):
    """brief Step 1：六个过滤语义逐条断言。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.rows = make_corpus(self._tmp.name)
        self.root = self._tmp.name

    def test_topic_filters_laos_topic_field(self):
        got = query(opts(topic="agent-os"), root=self.root)
        self.assertEqual([r["title"] for r in got],
                         ["Agent OS Kernel Sandbox",
                          "Sandboxed Agents Via Syscall Interception"])

    def test_strong_only_keeps_strong_true(self):
        got = query(opts(strong_only=True), root=self.root)
        # strong=False 与缺省 strong 字段均剔除
        self.assertEqual([r["title"] for r in got],
                         ["Barge-In Robust Wake Word Detection",
                          "Sandboxed Agents Via Syscall Interception",
                          "VAD For Always-On Audio"])

    def test_year_range_inclusive(self):
        got = query(opts(year="2023-2025"), root=self.root)
        # 2022 的 Untopical Paper 剔除，2023 与 2025 端点均保留
        self.assertEqual([r["year"] for r in got], [2023, 2025, 2024, 2025, 2023])

    def test_year_single_value(self):
        got = query(opts(year="2023"), root=self.root)
        self.assertEqual([r["year"] for r in got], [2023, 2023])

    def test_grep_case_insensitive_over_title_and_abstract(self):
        # 小写 pattern 命中大写标题；title+abstract 拼串都算
        got = query(opts(grep="barge-in"), root=self.root)
        self.assertEqual([r["title"] for r in got],
                         ["Barge-In Robust Wake Word Detection"])
        got = query(opts(grep="FULL-DUPLEX"), root=self.root)  # 大写 pattern 命中小写摘要
        self.assertEqual([r["title"] for r in got],
                         ["Barge-In Robust Wake Word Detection"])

    def test_limit_truncates_and_zero_means_all(self):
        got = query(opts(limit=2), root=self.root)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["title"], self.rows[0]["title"])
        got_all = query(opts(limit=0), root=self.root)
        self.assertEqual(len(got_all), 6)

    def test_default_limit_is_50(self):
        got = query(opts(), root=self.root)
        self.assertEqual(len(got), 6)  # 6 < 50 全保留，证明默认不是 0

    def test_empty_result_is_empty_list(self):
        self.assertEqual(query(opts(topic="spatial-privacy", strong_only=True,
                                    grep="quantum"), root=self.root), [])

    def test_venue_substring_casefold(self):
        got = query(opts(venue="interspeech"), root=self.root)
        self.assertEqual(len(got), 6)  # 所有 fixture venue 均含 Interspeech
        got = query(opts(venue="no-such-venue"), root=self.root)
        self.assertEqual(got, [])

    def test_filter_chain_combines(self):
        got = query(opts(topic="audio-speech", strong_only=True,
                         year="2023-2024", grep="wake"), root=self.root)
        self.assertEqual([r["title"] for r in got],
                         ["Barge-In Robust Wake Word Detection"])

    def test_query_returns_list_of_dicts_and_is_importable(self):
        got = query(opts(limit=3), root=self.root)
        self.assertIsInstance(got, list)
        for r in got:
            self.assertIsInstance(r, dict)


class ParseYear(unittest.TestCase):
    def test_single_and_range(self):
        self.assertEqual(parse_year("2023"), (2023, 2023))
        self.assertEqual(parse_year("2023-2025"), (2023, 2025))

    def test_invalid_specs_raise(self):
        for bad in ("202", "20235", "a-b", "2023-2022", "2023-", "2023-2024-2025"):
            with self.assertRaises(ValueError, msg=bad):
                parse_year(bad)


class Cli(unittest.TestCase):
    """main(argv)：--json 每行一个 JSON、人读表格 80 列、exit code。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        make_corpus(self._tmp.name)
        self.root = self._tmp.name

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = qc.main(argv, root=self.root)
        return code, out.getvalue(), err.getvalue()

    def test_json_mode_one_json_per_line(self):
        code, out, err = self.run_cli(["--topic", "agent-os", "--json"])
        self.assertEqual(code, 0)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        for ln in lines:
            row = json.loads(ln)
            self.assertEqual(row["laos_topic"], "agent-os")

    def test_json_mode_empty_result_no_stdout_rows(self):
        code, out, err = self.run_cli(["--topic", "agent-os", "--grep",
                                       "quantum", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_human_table_lines_capped_at_80(self):
        long_title = "Very Long Title " + "x" * 120
        write(Path(self.root) / "gamma.jsonl",
              [entry(long_title, laos_topic="agent-os")])
        code, out, err = self.run_cli(["--topic", "agent-os"])
        self.assertEqual(code, 0)
        body = [ln for ln in out.splitlines() if ln.strip()]
        self.assertGreaterEqual(len(body), 1)
        for ln in body:
            self.assertLessEqual(len(ln), 80)

    def test_bad_year_spec_exits_2(self):
        code, out, err = self.run_cli(["--year", "20-23"])
        self.assertEqual(code, 2)

    def test_bad_grep_regex_exits_2(self):
        code, out, err = self.run_cli(["--grep", "([unclosed"])
        self.assertEqual(code, 2)

    def test_bad_topic_choice_exits_2(self):
        code, out, err = self.run_cli(["--topic", "quantum-os"])
        self.assertEqual(code, 2)

    def test_limit_zero_cli(self):
        code, out, err = self.run_cli(["--limit", "0", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len([ln for ln in out.splitlines() if ln.strip()]), 6)


if __name__ == "__main__":
    unittest.main()
