# tests/test_speechchunk.py
"""LLM→TTS 适配层测试：流式分句（字节级语义）/ 播报清洗 / 数字归一化。

语义对照上游 voicenpu_engine rkllm_qwen.cpp / melo_tts.cpp（AGPL-3.0，
语义复现非拷贝）。

    python -m unittest tests.test_speechchunk -v
"""
from __future__ import annotations

import unittest

from laos.speechchunk import (clean_for_speech, normalize_digits_for_speech,
                              speech_chunk_end)


class SpeechChunkEndTests(unittest.TestCase):
    def test_sentence_punctuation_cuts_immediately(self):
        self.assertEqual(speech_chunk_end("三，四五。"), 5)     # 整句含句号
        self.assertEqual(speech_chunk_end("好！吗？"), 2)      # 最早句末标点
        self.assertEqual(speech_chunk_end("走吗；继续"), 3)

    def test_early_comma_not_eligible(self):
        # 逗号在第 15 字节之前不可切，攒到句号
        self.assertEqual(speech_chunk_end("三，四五。"), 5)
        self.assertEqual(speech_chunk_end("好，继续说吧怎么样了"), 0)

    def test_comma_after_15_bytes_cuts(self):
        # 5 个汉字（15 字节）后的逗号可切
        self.assertEqual(speech_chunk_end("甲乙丙丁戊，后面的话"), 6)

    def test_list_separator_after_15_bytes(self):
        self.assertEqual(speech_chunk_end("甲乙丙丁戊、乙和丙"), 6)

    def test_fallback_14_characters(self):
        self.assertEqual(speech_chunk_end("一二三四五六七八九十一二三四五"), 14)
        self.assertEqual(speech_chunk_end("短句"), 0)

    def test_mixed_ascii_byte_semantics(self):
        # 12 字节 ASCII 前缀 + 你好。（句号在字节 18）→ 按字节切
        self.assertEqual(speech_chunk_end("hello world 你好。"), 15)


class CleanForSpeechTests(unittest.TestCase):
    def test_prefix_strip(self):
        self.assertEqual(clean_for_speech("  乐乐：你好"), "你好")
        self.assertEqual(clean_for_speech("助手:在的"), "在的")

    def test_leading_index_number(self):
        self.assertEqual(clean_for_speech("1. 第一条"), "第一条")
        self.assertEqual(clean_for_speech("12、内容"), "内容")

    def test_think_block_removed(self):
        self.assertEqual(clean_for_speech("<think>推理</think>回答"), "回答")

    def test_model_name_localized(self):
        self.assertEqual(clean_for_speech("我是Qwen3-VL"), "我是本地语音助手")
        self.assertEqual(clean_for_speech("Qwen说的"), "本地语音助手说的")

    def test_enumeration_residue_removed(self):
        self.assertEqual(clean_for_speech("选项1.继续"), "选项继续")
        self.assertEqual(clean_for_speech("3、甲"), "甲")

    def test_semicolon_becomes_connector(self):
        self.assertEqual(clean_for_speech("第一；第二"), "第一，或者第二")

    def test_markdown_and_whitespace_stripped(self):
        self.assertEqual(clean_for_speech("#标题*强调*"), "标题强调")
        self.assertEqual(clean_for_speech("你\n好\t世 界"), "你好世界")


class NormalizeDigitsTests(unittest.TestCase):
    def test_clock_time(self):
        self.assertEqual(normalize_digits_for_speech("3:30"), "三点三零")
        self.assertEqual(normalize_digits_for_speech("3.14"), "三点一四")

    def test_plain_digits(self):
        self.assertEqual(normalize_digits_for_speech("2026年"), "二零二六年")

    def test_full_width_digits(self):
        self.assertEqual(normalize_digits_for_speech("５点"), "五点")

    def test_dot_not_between_digits_untouched(self):
        self.assertEqual(normalize_digits_for_speech("a.b"), "a.b")


if __name__ == "__main__":
    unittest.main()
