# tests/test_dialog_e2e.py
"""voicenpu 控制面复现件闭环集成测试（无音频，确定性脚本驱动）。

把五个复现模块串成完整对话控制流，对照上游 voicenpu_engine 的
单轮链路：KWS 唤醒 → ASR 终稿过 WakeGate → 声控指令短路（parse_mode_
request）或知识库短路（KnowledgeRetriever）→ 否则 LLM 流式生成按
speech_chunk_end 切句、clean_for_speech 清洗 → TtsRouter 合成（在线
失败降级离线）→ generation 打断丢弃过期代 → WakeGate.finish_turn +
MicrophoneGate 半双工保护。全程按上游 dialog_metrics.jsonl 字段口径
记录指标行。

    python -m unittest tests.test_dialog_e2e -v
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Callable, Iterator, List, Optional

from laos.dialogsched import (DialogQueue, GenerationGate, MicrophoneGate,
                              PauseWindow, TtsRouter, parse_mode_request)
from laos.knowledge import KnowledgeRetriever
from laos.speechchunk import clean_for_speech, speech_chunk_end
from laos.wakegate import WakeConfig, WakeGate, WakeState

FIXTURE = Path(__file__).resolve().parent / "data" / "voicenpu_knowledge.jsonl"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, sec):
        self.now += sec


class FakeTts:
    """按 clean 文本逐块发 16k 采样音频的假后端。"""

    def __init__(self, name: str, rate: int = 44100, fail: bool = False):
        self._name, self._rate, self.fail = name, rate, fail
        self.spoken: List[str] = []

    def ready(self):
        return True

    def sample_rate(self):
        return self._rate

    def name(self):
        return self._name

    def cancel(self):
        pass

    def synthesize_stream(self, text: str, sink: Callable[[List[float]], bool]) -> bool:
        if self.fail:
            return False
        self.spoken.append(text)
        return sink([0.0] * 16000)                            # 1s 假音频


def fake_llm_stream() -> Iterator[str]:
    """模拟 RKLLM 流式 token 输出（含思考链与模型自称，检验清洗）。"""
    yield "<think>用户在问身份</think>乐乐：我是Qwen3-VL，1.很高兴认识你。"
    yield "我会尽力帮忙；有疑问随时问我。"


class VoicenpuControlLoop:
    """把复现件组装成上游 DialogController 的同构控制面。"""

    def __init__(self, clock: FakeClock):
        self.clock = clock
        self.gate = GenerationGate()
        self.pause = PauseWindow(clock)
        self.queue = DialogQueue(self.pause, self.gate, clock)
        self.wake = WakeGate(clock)
        self.wake.configure(WakeConfig(
            enabled=True, wake_words=["小乐"], sleep_words=["小乐休息"],
            follow_up_timeout_sec=12.0, max_session_sec=120.0, max_turns=6))
        self.knowledge = KnowledgeRetriever()
        self.offline_tts = FakeTts("offline")
        self.online_tts = FakeTts("online", fail=True)
        self.router = TtsRouter(self.offline_tts, self.online_tts)
        self.router.select("online")
        self.mic = MicrophoneGate(sample_rate=16000, post_tts_guard_ms=400,
                                  clock=clock)
        self.metrics: List[dict] = []

    def on_kws(self, keyword: str) -> bool:
        return self.wake.wake()

    def on_asr_final(self, text: str) -> None:
        verdict = self.wake.process(text)
        if verdict.slept or not verdict.answer:
            return
        mode = parse_mode_request(verdict.text)
        if mode is not None:
            self._speak_direct("已切换到在线模式。" if mode == "online"
                               else "已切换到离线模式。")
            return
        match = self.knowledge.search(verdict.text, min_score=0.58)
        if match is not None:
            self._run_dialog(verdict.text, iter([match.answer]), "knowledge")
            return
        self._run_dialog(verdict.text, fake_llm_stream(), "llm")

    def _speak_direct(self, text: str) -> None:
        self._run_dialog(text, iter([text]), "tts")

    def _run_dialog(self, request: str, chunks: Iterator[str], route: str) -> None:
        job = self.queue.enqueue(True, request)
        played: List[str] = []
        pending = ""
        first_audio_ms: Optional[float] = None
        for chunk in chunks:
            if not self.gate.is_current(job.generation):
                break                                          # 迟到的回答不播
            pending += chunk
            cut = speech_chunk_end(pending)
            while cut:
                sentence = clean_for_speech(pending[:cut])
                pending = pending[cut:]
                cut = speech_chunk_end(pending)
                if not sentence:
                    continue
                ok = self.router.synthesize_stream(
                    sentence, lambda audio: self.gate.is_current(job.generation))
                if not ok:
                    break
                if first_audio_ms is None:
                    first_audio_ms = self.clock.now * 1000.0
                self.mic.emit_audio(16000)
                played.append(sentence)
        if pending and self.gate.is_current(job.generation):
            tail = clean_for_speech(pending)
            if tail and self.router.synthesize_stream(
                    tail, lambda audio: self.gate.is_current(job.generation)):
                played.append(tail)
        self.mic.extend_guard()
        self.wake.finish_turn()
        self.metrics.append({
            "request": request, "route": route,
            "response": "".join(played), "played_sentences": len(played),
            "first_audio_ms": first_audio_ms or 0.0,
            "speculative_cancelled": self.pause.take_cancelled(job.id),
        })


class ControlLoopE2E(unittest.TestCase):
    def build(self):
        clock = FakeClock()
        loop = VoicenpuControlLoop(clock)
        self.assertTrue(loop.knowledge.load(FIXTURE))
        return clock, loop

    def test_wake_then_knowledge_shortcut(self):
        _, loop = self.build()
        self.assertFalse(loop.wake.state() == WakeState.LISTENING)
        self.assertTrue(loop.on_kws("小乐"))
        loop.on_asr_final("你是谁")
        self.assertEqual(len(loop.metrics), 1)
        row = loop.metrics[0]
        self.assertEqual(row["route"], "knowledge")            # 命中绕过 LLM
        self.assertIn("乐乐", row["response"])
        # 长答案被流式切成多句，逐句进 TTS；拼回与 response 一致
        self.assertGreaterEqual(row["played_sentences"], 2)
        self.assertEqual("".join(loop.offline_tts.spoken), row["response"])
        self.assertTrue(loop.offline_tts.spoken[0].startswith("你好"))

    def test_llm_stream_chunked_and_cleaned(self):
        clock, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("讲讲你能做什么")
        row = loop.metrics[0]
        self.assertEqual(row["route"], "llm")
        self.assertNotIn("<think>", row["response"])           # 思考链剔除
        self.assertNotIn("Qwen", row["response"])              # 自称本地化
        self.assertNotIn("1.", row["response"])                # 序号残片剔除
        self.assertIn("，或者", row["response"])                # 分号口语化
        self.assertGreaterEqual(row["played_sentences"], 2)    # 流式多句

    def test_online_degrades_to_offline(self):
        _, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("你是谁")
        self.assertTrue(loop.router.take_fell_back())          # 在线失败→离线兜底
        self.assertTrue(loop.offline_tts.spoken)

    def test_mode_command_shortcuts_llm(self):
        _, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("小乐，切换到离线模式")
        self.assertEqual(loop.metrics[0]["route"], "tts")
        self.assertIn("离线", loop.metrics[0]["response"])

    def test_sleep_word_closes_session(self):
        _, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("小乐休息")
        self.assertEqual(loop.metrics, [])                     # 不进对话
        self.assertEqual(loop.wake.state(), WakeState.SLEEPING)

    def test_asleep_utterances_ignored(self):
        _, loop = self.build()
        loop.on_asr_final("今天天气怎么样")                     # 未唤醒
        self.assertEqual(loop.metrics, [])

    def test_interrupted_generation_never_plays(self):
        clock, loop = self.build()
        loop.on_kws("小乐")
        gen_before = loop.gate.current()
        loop.on_asr_final("你是谁")                             # 5 句完整播报
        self.assertEqual(loop.metrics[0]["played_sentences"],
                         len(loop.offline_tts.spoken))
        # 新话语入队即 interrupt：代数前进，上一代的一切产出被拒
        loop.on_asr_final("你来自哪里")
        self.assertGreater(loop.gate.current(), gen_before + 1)
        self.assertEqual(len(loop.metrics), 2)
        self.assertFalse(loop.gate.is_current(gen_before + 1))

    def test_mic_guard_half_duplex(self):
        clock, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("你是谁")                             # 5 句 × 1s 播报
        # 控制环已按句 emit_audio（5s）并追加 post_tts_guard 400ms
        self.assertFalse(loop.mic.allow(aec_ready=False, barge_in_enabled=True))
        clock.advance(5.3)
        self.assertFalse(loop.mic.allow(False, True))          # guard 尾沿
        clock.advance(0.2)
        self.assertTrue(loop.mic.allow(False, True))

    def test_metrics_rows_are_json_serializable(self):
        _, loop = self.build()
        loop.on_kws("小乐")
        loop.on_asr_final("你是谁")
        for row in loop.metrics:
            json.dumps(row, ensure_ascii=False)                # 上传 jsonl 口径


if __name__ == "__main__":
    unittest.main()
