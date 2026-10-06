# tests/test_wer.py
"""laos.wer —— ASR 评测：词错率 WER / 字错率 CER（编辑距离，纯标准库）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_wer -v

来源：docs/research/2026-10-06-cactus-whistle-adoption.md——端侧 ASR 通道接入前
必须先量化效果（用户裁决：最主要的是先测模型效果到底怎么样）。中文用 CER
（字级），英文用 WER（词级）；归一化统一处理大小写/标点/全半角/空白。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.wer import cer, edit_distance, normalize, wer  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_lowercase_and_strip_punct(self):
        self.assertEqual(normalize("Hello, World!"), "hello world")

    def test_fullwidth_to_halfwidth(self):
        self.assertEqual(normalize("Ｈｅｌｌｏ"), "hello")

    def test_cjk_punct_removed(self):
        self.assertEqual(normalize("今天天气怎么样？"), "今天天气怎么样")

    def test_collapse_whitespace(self):
        self.assertEqual(normalize("a   b\t c"), "a b c")

    def test_chinese_text_untouched(self):
        self.assertEqual(normalize("打开厨房的灯。"), "打开厨房的灯")


class TestEditDistance(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(edit_distance("abc", "abc"), 0)

    def test_empty(self):
        self.assertEqual(edit_distance("", "abc"), 3)
        self.assertEqual(edit_distance("abc", ""), 3)
        self.assertEqual(edit_distance("", ""), 0)

    def test_substitution(self):
        self.assertEqual(edit_distance("cat", "cut"), 1)

    def test_insertion_deletion(self):
        self.assertEqual(edit_distance("cat", "cart"), 1)   # 插入 r
        self.assertEqual(edit_distance("cart", "cat"), 1)   # 删除 r

    def test_lists(self):
        self.assertEqual(edit_distance(["a", "b"], ["a", "c", "b"]), 1)

    def test_known_distance(self):
        # kitten -> sitting 经典例：3
        self.assertEqual(edit_distance("kitten", "sitting"), 3)


class TestWer(unittest.TestCase):
    def test_perfect(self):
        self.assertEqual(wer("hello world", "hello world"), 0.0)

    def test_one_word_wrong_of_two(self):
        self.assertEqual(wer("hello world", "hello there"), 0.5)

    def test_all_wrong(self):
        self.assertEqual(wer("one two three", "four five six"), 1.0)

    def test_insertion_counts(self):
        # ref 2 词，hyp 3 词（多插 1 词）→ 1/2
        self.assertEqual(wer("hello world", "hello big world"), 0.5)

    def test_punctuation_and_case_ignored(self):
        self.assertEqual(wer("Hello, World!", "hello world"), 0.0)

    def test_empty_ref_raises(self):
        with self.assertRaises(ValueError):
            wer("", "something")

    def test_empty_hyp_full_error(self):
        self.assertEqual(wer("hello world", ""), 1.0)


class TestCer(unittest.TestCase):
    def test_chinese_perfect(self):
        self.assertEqual(cer("打开厨房的灯。", "打开厨房的灯"), 0.0)

    def test_one_char_wrong(self):
        # 打开厨房的灯 (6字) vs 打开客厅的灯：厨→客、房→厅 2 处替换 → 2/6
        self.assertAlmostEqual(cer("打开厨房的灯", "打开客厅的灯"), 2 / 6)

    def test_chinese_missing_sentence(self):
        # 参照 16 字，假设识别成 0 字 → 1.0
        self.assertEqual(cer("人工智能正在改变我们与计算机交互的方式", ""), 1.0)

    def test_spaces_ignored_in_cer(self):
        self.assertEqual(cer("a b c", "abc"), 0.0)


if __name__ == "__main__":
    unittest.main()
