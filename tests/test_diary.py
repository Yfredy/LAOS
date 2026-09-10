# tests/test_diary.py
"""diary —— 每日日记（审计流 + 记忆库聚合）的回归测试。

    python -m unittest tests.test_diary -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包，路径注入以便 import diary

from laos.memory import MemoryStore  # noqa: E402
from diary import SECTION_TITLES, build_diary  # noqa: E402

FOUR_TITLES = ("一、今天做了什么", "二、新记住的事", "三、被拒绝与原因", "四、明天可以试试")


class TestBuildDiary(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")
        self.store.remember("fact", "我喜欢的编程语言是 Python", tags=["编程"])
        self.store.remember("episodic", "今天下午开了产品评审会", tags=["会议"])
        self.now = time.time()
        self.date = time.strftime("%Y-%m-%d", time.localtime(self.now))
        # 伪造当天审计：2 成功 + 1 被拒（形状与内核 audit.jsonl 的 syscall 行一致）
        self.records = [
            {"t": self.now, "event": "syscall", "pid": 1001, "agent": "ops-agent",
             "tool": "fs.read", "args": {"path": "/main/workspace/hosts"},
             "ok": True, "ms": 1.2, "result": "127.0.0.1 localhost"},
            {"t": self.now, "event": "syscall", "pid": 1001, "agent": "ops-agent",
             "tool": "fs.write", "args": {"path": "/exp-A/workspace/hosts"},
             "ok": True, "ms": 0.8, "result": "OK wrote 3 lines"},
            {"t": self.now, "event": "syscall", "pid": 1002, "agent": "guest-agent",
             "tool": "fs.read", "args": {"path": "/main/workspace/hosts"},
             "ok": False, "ms": 0.1,
             "result": "EPERM: fs.read not in caps (allowed: sys.*, msg.*)"},
        ]

    def tearDown(self):
        self._td.cleanup()

    def _build(self, records):
        # 测试环境强制走模板路径：OPENAI_API_KEY 一律视为未设置
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            return build_diary(self.date, records, self.store)

    def test_four_sections_and_file_written(self):
        result = self._build(self.records)
        for title in FOUR_TITLES:
            self.assertIn(title, result)          # 返回 dict 含四章关键字
            self.assertTrue(result[title].strip())  # 且每章都有内容
        # md 文件写出：标题 + 四个 ## 章节齐全
        md = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn(f"# laos 日记 {self.date}", md)
        for title in FOUR_TITLES:
            self.assertIn(f"## {title}", md)
        # 聚合数字正确：3 次 syscall（2 成功 1 被拒），TOP 工具 fs.read
        self.assertIn("3", result["一、今天做了什么"])
        self.assertIn("fs.read", result["一、今天做了什么"])
        self.assertIn("EPERM", result["三、被拒绝与原因"])

    def test_memory_consolidation_appends_diary(self):
        before = self.store.stats()["total"]
        result = self._build(self.records)
        self.assertTrue(result["summary"])        # 第一段摘要非空
        st = self.store.stats()
        self.assertEqual(st["total"], before + 1)  # 记忆库 total +1
        self.assertEqual(st["by_kind"].get("diary"), 1)  # 新增条目 kind=diary
        diaries = [r for r in self.store.recall(self.date, k=5)
                   if r["kind"] == "diary"]
        self.assertTrue(diaries)                  # 按 date 标签能召回日记
        self.assertEqual(diaries[0]["tags"], [self.date])

    def test_empty_audit_still_has_all_sections(self):
        result = self._build([])
        for title in FOUR_TITLES:
            self.assertIn(title, result)
        self.assertIn("今天没有 syscall 记录", result["一、今天做了什么"])
        md = Path(result["path"]).read_text(encoding="utf-8")
        for title in FOUR_TITLES:
            self.assertIn(f"## {title}", md)

    def test_records_of_other_days_are_excluded(self):
        yesterday = time.strftime(
            "%Y-%m-%d", time.localtime(self.now - 86400))
        old = [dict(r, t=self.now - 86400) for r in self.records]
        env = dict(os.environ)
        env.pop("OPENAI_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            result = build_diary(self.date, old, self.store)
        self.assertIn("今天没有 syscall 记录", result["一、今天做了什么"])
        # 昨天的记录不会被算进今天的日记
        self.assertNotIn("fs.write", result["一、今天做了什么"])
        self.assertEqual(yesterday, time.strftime(
            "%Y-%m-%d", time.localtime(self.now - 86400)))  # sanity

    def test_section_titles_constant(self):
        self.assertEqual(tuple(SECTION_TITLES), FOUR_TITLES)


class _FakeBrain:
    def __init__(self, text: str):
        self.name = "fake"
        self._text = text

    def think(self, messages, tools):
        from laos.brain import Thought
        return Thought(text=self._text, finish=True)


class TestLlmPath(unittest.TestCase):
    """LLM 摘要路径：成功用 LLM 文案；失败（含 brain.py 的"LLM 调用失败"
    错误包装）一律回落抽取式模板——日记生成永不因 LLM 故障而失败。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")
        self.now = time.time()
        self.date = time.strftime("%Y-%m-%d", time.localtime(self.now))

    def tearDown(self):
        self._td.cleanup()

    def test_llm_summary_used_when_brain_succeeds(self):
        result = build_diary(self.date, [], self.store,
                             brain=_FakeBrain("今天内核安睡，无事发生。"))
        self.assertEqual(result["summary"], "今天内核安睡，无事发生。")
        md = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("今天内核安睡，无事发生。", md)
        self.assertNotIn("今天没有 syscall 记录，内核安静地待了一天。", md)

    def test_llm_failure_marker_falls_back_to_template(self):
        # 复刻真实事故：无效 OPENAI_API_KEY → brain.think 不抛异常，
        # 返回 "LLM 调用失败: HTTP 401 ..." 的 Thought——必须回落模板，
        # 且错误文案不得被写成日记/存进记忆库
        result = build_diary(self.date, [], self.store,
                             brain=_FakeBrain(
                                 "LLM 调用失败: HTTP 401 b'incorrect api key'"))
        self.assertIn("今天没有 syscall 记录", result["summary"])
        self.assertNotIn("LLM 调用失败", result["summary"])
        md = Path(result["path"]).read_text(encoding="utf-8")
        self.assertNotIn("LLM 调用失败", md)
        diary_rows = [r for r in self.store.recall(self.date, k=5)
                      if r["kind"] == "diary"]
        self.assertTrue(diary_rows)
        self.assertNotIn("LLM 调用失败", diary_rows[0]["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
