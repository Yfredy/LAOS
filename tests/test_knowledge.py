# tests/test_knowledge.py
"""KnowledgeRetriever 测试：上游真数据 fixture + 打分公式精查。

fixture（tests/data/voicenpu_knowledge.jsonl）摘自 voicenpu_engine
knowledge/company_knowledge.jsonl 前 6 条（Gitee bravexyz，AGPL-3.0）。

    python -m unittest tests.test_knowledge -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from laos.knowledge import KnowledgeRetriever, _features

FIXTURE = Path(__file__).resolve().parent / "data" / "voicenpu_knowledge.jsonl"


class FeatureTests(unittest.TestCase):
    def test_ascii_fold_and_cjk_symbols(self):
        norm, terms = _features("Hello 世界")
        self.assertEqual(norm, "hello世界")
        self.assertIn("hello世", terms)                      # ASCII 词 + 汉字 bigram

    def test_punctuation_ignored(self):
        norm, terms = _features("你是谁？")
        self.assertEqual(norm, "你是谁")
        self.assertIn("你是", terms)

    def test_single_symbol_unigram(self):
        _, terms = _features("好")
        self.assertEqual(terms, {"好"})


class KnowledgeRetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kr = KnowledgeRetriever()
        assert cls.kr.load(FIXTURE)

    def test_load_real_fixture(self):
        self.assertEqual(self.kr.size(), 6)

    def test_exact_question_substring_hit(self):
        # fixture 里 "你是谁呀" 挂在 daily-001（自我介绍）下
        match = self.kr.search("你是谁", min_score=0.58)
        self.assertIsNotNone(match)
        self.assertEqual(match.id, "daily-001")
        self.assertIn("乐乐", match.answer)
        self.assertEqual(match.score, 1.0)                    # 子串双向 → 1.0

    def test_paraphrase_with_prefix_hit(self):
        match = self.kr.search("乐乐你来自哪里呀", min_score=0.58)
        self.assertIsNotNone(match)
        self.assertEqual(match.id, "daily-003")

    def test_miss_falls_through(self):
        self.assertIsNone(self.kr.search("今天股市行情怎么样", min_score=0.58))
        self.assertIsNone(self.kr.search("", min_score=0.58))

    def test_score_formula(self):
        # 自建库精查 0.7/0.3 双向覆盖：query 乙丙丁戊(3 词项) vs 问句 甲乙丙丁(3 词项)
        # 交集 {乙丙,丙丁}=2，非子串 → 0.7*2/3 + 0.3*2/3 = 0.666…
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kb.jsonl"
            path.write_text(json.dumps({
                "id": "t1", "answer": "答",
                "questions": ["甲乙丙丁"]}, ensure_ascii=False) + "\n",
                encoding="utf-8")
            kr = KnowledgeRetriever()
            self.assertTrue(kr.load(path))
            match = kr.search("乙丙丁戊", min_score=0.58)
            self.assertIsNotNone(match)
            self.assertAlmostEqual(match.score, 0.7 * 2 / 3 + 0.3 * 2 / 3,
                                   places=6)
            self.assertIsNone(kr.search("乙丙丁戊", min_score=0.7))   # 阈值闸

    def test_intersection_floor(self):
        # 交集 <2 一票否决：只共享一个 bigram 的高字面相似也不命中
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kb.jsonl"
            path.write_text(json.dumps({
                "id": "t2", "answer": "答",
                "questions": ["你是谁呀"]}, ensure_ascii=False) + "\n",
                encoding="utf-8")
            kr = KnowledgeRetriever()
            self.assertTrue(kr.load(path))
            # "到底是谁啊" 与 "你是谁呀" 仅共享 bigram "是谁"
            self.assertIsNone(kr.search("到底是谁啊", min_score=0.0))

    def test_load_failures(self):
        kr = KnowledgeRetriever()
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.jsonl"
            empty.write_text("", encoding="utf-8")
            self.assertFalse(kr.load(empty))
            bad = Path(tmp) / "bad.jsonl"
            bad.write_text("not json\n", encoding="utf-8")
            self.assertFalse(kr.load(bad))
            missing_field = Path(tmp) / "missing.jsonl"
            missing_field.write_text(json.dumps({"id": "x"}) + "\n",
                                     encoding="utf-8")
            self.assertFalse(kr.load(missing_field))
            self.assertFalse(kr.load(Path(tmp) / "nonexistent.jsonl"))

    def test_max_query_bytes(self):
        self.assertIsNone(self.kr.search("啊" * 600, min_score=0.0))  # >1024B


if __name__ == "__main__":
    unittest.main()
