# tests/test_ear_refine.py
"""drv_ear AgenticSR 接入：ear.refine 工具 + ear.transcribe(refine=True)。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_ear_refine -v

来源：docs/research/2026-10-06-agenticasr-adoption.md（arXiv 2607.28175，
小红书笔记《AgenticASR：基于智能体方法优化现实场景下》→ 复现并运用）。
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from drivers import drv_ear  # noqa: E402


class TestEarRefineTool(unittest.TestCase):
    def test_refine_tool_returns_raw_and_refined(self):
        out = json.loads(drv_ear.ear_refine("呃我我我想喝水"))
        self.assertEqual(out["raw"], "呃我我我想喝水")
        self.assertEqual(out["refined"], "我想喝水")

    def test_refine_tool_clean_text_passthrough(self):
        out = json.loads(drv_ear.ear_refine("今天天气怎么样"))
        self.assertEqual(out["refined"], "今天天气怎么样")


class TestTranscribeRefineParam(unittest.TestCase):
    def setUp(self):
        self.wav = REPO / "var" / "asr_eval" / "en_a.wav"
        if not self.wav.exists():
            import wave
            self.wav = REPO / "var" / "asr_eval" / "_tmp_silence.wav"
            self.wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.wav), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(b"\x00\x00" * 1600)

    def test_refine_true_applies_refiner(self):
        with mock.patch.dict(os.environ, {"LAOS_ASR_CHANNEL": "funasr"}, clear=False), \
             mock.patch.object(drv_ear, "_transcribe_funasr",
                               return_value={"text": "明天九点不对我是说十点开会",
                                             "language": "zh", "emotions": []}):
            out = json.loads(drv_ear.ear_transcribe(str(self.wav), refine=True))
        self.assertEqual(out["text"], "十点开会")
        self.assertEqual(out["source"], "funasr")

    def test_refine_default_false_keeps_raw(self):
        with mock.patch.dict(os.environ, {"LAOS_ASR_CHANNEL": "funasr"}, clear=False), \
             mock.patch.object(drv_ear, "_transcribe_funasr",
                               return_value={"text": "呃今天天气怎么样",
                                             "language": "zh", "emotions": []}):
            out = json.loads(drv_ear.ear_transcribe(str(self.wav)))
        self.assertEqual(out["text"], "呃今天天气怎么样")


if __name__ == "__main__":
    unittest.main()
