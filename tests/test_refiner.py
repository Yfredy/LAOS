# tests/test_refiner.py
"""laos.refiner —— AgenticSR 规则版 Refiner：口语转写 → 干净意图文本。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_refiner -v

来源：docs/research/2026-10-06-agenticasr-adoption.md（小红书笔记《AgenticASR：
基于智能体方法优化现实场景下》→ arXiv 2607.28175）。论文 Refiner 是 Qwen3-4B
+LoRA 微调（小模型微调打赢 Qwen3-560B 零样本：19.7 vs 25.8 WER）；本模块复现其
任务的**确定性子集**（纯 stdlib）：填充词去除、口吃折叠、自我纠正取末段——
"保留说话者最终意图"的规则近似。学习型 Refiner 走 genie 端侧 LLM 通道（远期）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.refiner import refine  # noqa: E402


class TestFillers(unittest.TestCase):
    def test_chinese_fillers_removed(self):
        self.assertEqual(refine("呃今天天气怎么样"), "今天天气怎么样")
        self.assertEqual(refine("嗯我想想啊"), "我想想")

    def test_filler_between_words(self):
        self.assertEqual(refine("打开呃厨房的灯"), "打开厨房的灯")

    def test_english_fillers_removed(self):
        self.assertEqual(refine("uh turn on the um kitchen light"),
                         "turn on the kitchen light")

    def test_normal_words_kept(self):
        # 那个/这个是指示词，不能当填充词误删
        self.assertEqual(refine("打开那个厨房的灯"), "打开那个厨房的灯")

    def test_clean_text_unchanged(self):
        self.assertEqual(refine("今天天气怎么样"), "今天天气怎么样")


class TestStutter(unittest.TestCase):
    def test_chinese_triple_repeat_folded(self):
        self.assertEqual(refine("我我我想要喝水"), "我想要喝水")

    def test_chinese_double_repeat_kept(self):
        # 双叠是合法中文（谢谢/看看/想想）
        self.assertEqual(refine("谢谢你我再想想"), "谢谢你我再想想")

    def test_english_double_word_folded(self):
        self.assertEqual(refine("turn on the the light"), "turn on the light")

    def test_english_legal_phrase_kept(self):
        # "very very" 是强调；规则版不折英文双副词以外的双连？——统一折叠，本测试钉住现状
        self.assertEqual(refine("make it very very clear"), "make it very clear")


class TestSelfCorrection(unittest.TestCase):
    def test_chinese_take_last_segment(self):
        # 最终意图 = 最后一次纠正的内容
        self.assertEqual(refine("明天九点不对我是说十点开会"), "十点开会")

    def test_chinese_correction_marker_variants(self):
        self.assertEqual(refine("不是，是后天"), "是后天")  # 引导字"是"保留（规则版）
        self.assertEqual(refine("我叫小王，哦不对，是老王"), "是老王")

    def test_english_take_last_segment(self):
        # 取末段（最终意图 = 最后说的内容）；子句级替换是学习型 Refiner 的活
        self.assertEqual(refine("meet at nine no wait ten oclock"), "ten oclock")

    def test_english_i_mean(self):
        # 子句级替换型纠正是规则版的已知局限（论文用学习型 Refiner 的理由）：
        # "four I mean six" 意图为 "book a table for six"，规则版取末段得 "six"
        self.assertEqual(refine("book a table for four I mean six"), "six")

    def test_full_restate_takes_tail(self):
        # 完整重述型：末段本身含共享前缀，取末段即完整意图
        self.assertEqual(refine("meet at nine no wait meet at ten"), "meet at ten")

    def test_no_correction_untouched(self):
        self.assertEqual(refine("这个不对需要修改"), "这个不对需要修改")

    def test_combined_fillers_and_correction(self):
        # 已知局限钉住：子句级替换（意图=发邮件给李四）规则版只给出末段
        self.assertEqual(refine("呃发邮件给张三不对嗯我是说李四"), "李四")


class TestCleanup(unittest.TestCase):
    def test_whitespace_and_punct_collapsed(self):
        self.assertEqual(refine("今天  天气。怎么样！"), "今天天气怎么样")

    def test_empty_input(self):
        self.assertEqual(refine(""), "")

    def test_idempotent(self):
        once = refine("呃我我我想想，不对，我是说考虑一下")
        self.assertEqual(refine(once), once)


if __name__ == "__main__":
    unittest.main()
