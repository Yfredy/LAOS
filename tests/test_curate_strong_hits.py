# tests/test_curate_strong_hits.py
"""强命中精炼器（Task 1）：is_strong 契约 / 三主线强命中规则 / 产出 IO 与 CLI。

brief Step 1 四条核心断言逐字照抄（attack success rate 裸 asr 判弱 / wake
word 短语判强 / asr+音频语境同现判强 / kernel sandbox 判强+tool use 宽分支
判弱 / spatial 全保），外加契约：audio 短语表与 bare+±60 字符语境窗、
agent-os 窄分支双向同现（治理词在前也算，brief 正例 Kernel-level
sandboxing of LLM agents）与 40 字符跨度上限、宽分支判弱、spatial 词表
短语级全保；strong_terms 记录命中的强词组标签（去重保序）；run_curate
只写强命中行（原字段 + strong:true + strong_terms，行保序）并回报
topic×强/弱 计数；CLI --stats；--out 与输入同路径拒绝。纯离线，不触网。
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus.venue_expansion.curate_strong_hits import (  # noqa: E402
    AGENT_GOV_TERMS, AUDIO_PHRASES, AUDIO_BARE_WORDS, CONTEXT_WINDOW,
    SPATIAL_PHRASES, is_strong, run_curate, strong_terms,
)
import corpus.venue_expansion.curate_strong_hits as csh  # noqa: E402


def entry(title, abstract=None, **kw):
    e = {"title": title, "year": 2026, "venue": "Test Venue",
         "authors": ["Doe, Jane"], "url": "https://x/1",
         "doi": "10.1/t.1", "abstract": abstract}
    e.update(kw)
    return e


def write(path, entries):
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                            for e in entries), encoding="utf-8")


class BriefCore(unittest.TestCase):
    """task-1 brief Step 1 四条核心断言，逐字照抄。"""

    def test_audio_speech_bare_substring_is_weak(self):
        # 裸 asr/tts/vad 子串 = 弱（attack success rate 的 asr）
        self.assertFalse(is_strong({"title": "Boosting attack success rate (asr) of jailbreaks",
                                    "abstract": None, "laos_topic": "audio-speech"}))

    def test_audio_speech_phrase_is_strong(self):
        self.assertTrue(is_strong({"title": "Streaming wake word detection on device",
                                   "abstract": None, "laos_topic": "audio-speech"}))
        self.assertTrue(is_strong({"title": "Noise-robust asr front-end",  # asr 邻接音频词
                                   "abstract": "speech recognition pipeline", "laos_topic": "audio-speech"}))

    def test_agent_os_narrow_only(self):
        self.assertTrue(is_strong({"title": "Kernel-level sandboxing of LLM agents",
                                   "abstract": None, "laos_topic": "agent-os"}))
        self.assertFalse(is_strong({"title": "A survey of llm agent tool use",  # 宽分支
                                    "abstract": None, "laos_topic": "agent-os"}))

    def test_spatial_privacy_kept(self):
        self.assertTrue(is_strong({"title": "Binaural localization with beamforming",
                                   "abstract": None, "laos_topic": "spatial-privacy"}))


class Wordlists(unittest.TestCase):
    """词表防漂移：audio 短语表/bare 词、agent 治理词、spatial 短语表照 brief。"""

    def test_audio_phrase_list_from_brief(self):
        self.assertEqual([lab for lab, _ in AUDIO_PHRASES], [
            "wake word", "keyword spotting", "speech recognition",
            "voice activity", "echo cancellation", "far-field",
            "text-to-speech", "speech translation", "spoken dialogue",
            "voice agent", "audio-visual speech", "diarization"])

    def test_audio_bare_and_window(self):
        self.assertEqual(AUDIO_BARE_WORDS, ("asr", "tts", "vad"))
        self.assertEqual(CONTEXT_WINDOW, 60)

    def test_agent_gov_terms_from_filter_narrow_branch(self):
        # 与 filter_laos_relevant 窄分支治理词逐字一致（含 quota）
        self.assertEqual(AGENT_GOV_TERMS, ("operating system", "sandbox",
                                           "syscall", "kernel", "governan",
                                           "resource", "quota", "isolation"))

    def test_spatial_phrase_list_from_filter_vocab(self):
        self.assertEqual([lab for lab, _ in SPATIAL_PHRASES], [
            "binaural", "spatial audio", "beamforming", "acoustic camera",
            "speech privacy", "audio watermark"])


class AudioSpeechRules(unittest.TestCase):
    """bare 词须词边界 + ±60 字符音频语境窗；always-on 不在强短语表。"""

    def test_bare_word_without_audio_context_is_weak(self):
        self.assertFalse(is_strong(entry("The asr metric revisited",
                                         laos_topic="audio-speech")))

    def test_bare_word_with_context_after_within_window(self):
        # asr 之后 43 字符处出现语境词 voice -> 强
        self.assertTrue(is_strong(entry("improving asr", "x" * 40 + " voice",
                                        laos_topic="audio-speech")))

    def test_bare_word_with_context_beyond_window_is_weak(self):
        # asr 之后 200+ 字符处才有 voice -> 窗外 -> 弱
        self.assertFalse(is_strong(entry("improving asr", "x" * 200 + " voice",
                                         laos_topic="audio-speech")))

    def test_bare_word_with_context_before_within_window(self):
        self.assertTrue(is_strong(entry("speech models", "evaluated asr benchmarks",
                                        laos_topic="audio-speech")))

    def test_bare_word_requires_word_boundary(self):
        # asr 嵌在长词里（asrbench）不算裸词命中，即便语境词在场
        self.assertFalse(is_strong(entry("asrbench evaluation with speech audio",
                                         laos_topic="audio-speech")))

    def test_always_on_alone_is_weak(self):
        self.assertFalse(is_strong(entry("Always-on connectivity in cellular networks",
                                         laos_topic="audio-speech")))

    def test_diarization_stem_is_strong(self):
        e = entry("Speaker diarization in meetings", laos_topic="audio-speech")
        self.assertTrue(is_strong(e))
        self.assertEqual(strong_terms(e), ["diarization"])

    def test_unhyphenated_text_to_speech_is_strong(self):
        self.assertTrue(is_strong(entry("Neural text to speech synthesis",
                                        laos_topic="audio-speech")))

    def test_tts_bare_with_context_strong_without_weak(self):
        self.assertTrue(is_strong(entry("streaming tts", "with natural voice",
                                        laos_topic="audio-speech")))
        self.assertFalse(is_strong(entry("streaming tts for chatbots",
                                         laos_topic="audio-speech")))


class AgentOsRules(unittest.TestCase):
    """窄分支双向同现（agent…gov 或 gov…agent，40 字符跨度）；宽分支弱。"""

    def test_gov_word_before_agent_is_strong(self):
        self.assertTrue(is_strong(entry("Sandbox execution for tool agents",
                                        laos_topic="agent-os")))

    def test_span_over_40_chars_is_weak(self):
        # agent 与 sandbox 相隔 > 40 字符 -> 弱
        self.assertFalse(is_strong(entry("agent " + "filler " * 20 + "sandbox policy",
                                         laos_topic="agent-os")))

    def test_resource_within_span_strong(self):
        e = entry("Resource quota enforcement for autonomous agents",
                  laos_topic="agent-os")
        self.assertTrue(is_strong(e))
        self.assertIn("agent+resource", strong_terms(e))

    def test_wide_branch_only_is_weak(self):
        self.assertFalse(is_strong(entry("language model agents for reasoning",
                                         laos_topic="agent-os")))
        self.assertFalse(is_strong(entry("llm agent frameworks a survey",
                                         laos_topic="agent-os")))

    def test_kernel_sandbox_terms_pair_labels(self):
        e = entry("Kernel-level sandboxing of LLM agents", laos_topic="agent-os")
        self.assertEqual(set(strong_terms(e)), {"agent+sandbox", "agent+kernel"})

    def test_no_agent_no_strong(self):
        # 只有治理词、没有 agent -> 窄分支不成立 -> 弱
        self.assertFalse(is_strong(entry("kernel bypass via speculative execution",
                                         laos_topic="agent-os")))


class SpatialRules(unittest.TestCase):
    """词表本身即短语级，全保。"""

    def test_each_vocab_phrase_is_strong(self):
        for title in ("Binaural localization", "spatial audio reproduction",
                      "adaptive beamforming array", "acoustic camera imaging",
                      "speech privacy protection", "audio watermark detection"):
            e = entry(title, laos_topic="spatial-privacy")
            self.assertTrue(is_strong(e), title)

    def test_terms_labels(self):
        e = entry("Binaural localization with beamforming",
                  laos_topic="spatial-privacy")
        self.assertEqual(strong_terms(e), ["binaural", "beamforming"])


class StrongTermsContract(unittest.TestCase):
    """strong_terms 去重保序（短语标签在前、bare 词在后）；未知 topic 判弱。"""

    def test_phrase_order_and_dedup(self):
        e = entry("Wake word and keyword spotting, wake word again",
                  laos_topic="audio-speech")
        self.assertEqual(strong_terms(e), ["wake word", "keyword spotting"])

    def test_bare_label_after_phrases(self):
        e = entry("Noise-robust asr front-end",
                  abstract="speech recognition pipeline",
                  laos_topic="audio-speech")
        self.assertEqual(strong_terms(e), ["speech recognition", "asr"])

    def test_is_strong_returns_bool(self):
        self.assertIsInstance(is_strong(entry("Wake word", laos_topic="audio-speech")), bool)
        self.assertIsInstance(is_strong(entry("cat photos", laos_topic="audio-speech")), bool)

    def test_unknown_topic_is_weak(self):
        self.assertFalse(is_strong({"title": "Wake word everywhere",
                                    "abstract": None, "laos_topic": "other"}))
        self.assertFalse(is_strong({"title": "Wake word everywhere",
                                    "abstract": None}))

    def test_none_abstract_matches_title_only(self):
        self.assertTrue(is_strong(entry("voice agent orchestration", abstract=None,
                                        laos_topic="audio-speech")))


class RunCurateIO(unittest.TestCase):
    """只写强命中行：原字段 + strong:true + strong_terms，行保序，弱行计数。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        d = self.dir = Path(self.td.name)
        self.inp = d / "laos_relevant.jsonl"
        write(self.inp, [
            entry("Streaming wake word detection", doi="10.1/a",
                  laos_topic="audio-speech"),                        # audio 强
            entry("Boosting attack success rate (asr) of jailbreaks",
                  doi="10.1/b", laos_topic="audio-speech"),          # audio 弱
            entry("Kernel-level sandboxing of LLM agents",
                  doi="10.1/c", laos_topic="agent-os"),              # agent 强
            entry("A survey of llm agent tool use", doi="10.1/d",
                  laos_topic="agent-os"),                            # agent 弱
            entry("Binaural localization with beamforming",
                  doi="10.1/e", laos_topic="spatial-privacy"),       # spatial 强
        ])
        self.out = d / "laos_relevant_strong.jsonl"
        self.stats = run_curate(self.inp, self.out)

    def tearDown(self):
        self.td.cleanup()

    def test_counts(self):
        self.assertEqual(self.stats["total_in"], 5)
        self.assertEqual(self.stats["strong"], 3)
        self.assertEqual(self.stats["weak"], 2)
        self.assertEqual(self.stats["written"], 3)
        self.assertEqual(self.stats["per_topic"], {
            "agent-os": {"strong": 1, "weak": 1},
            "audio-speech": {"strong": 1, "weak": 1},
            "spatial-privacy": {"strong": 1, "weak": 0}})

    def test_output_rows_ordered_with_new_fields(self):
        rows = [json.loads(l)
                for l in self.out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["title"] for r in rows],
                         ["Streaming wake word detection",
                          "Kernel-level sandboxing of LLM agents",
                          "Binaural localization with beamforming"])
        self.assertEqual([r["laos_topic"] for r in rows],
                         ["audio-speech", "agent-os", "spatial-privacy"])
        self.assertTrue(all(r["strong"] is True for r in rows))
        self.assertEqual(rows[0]["strong_terms"], ["wake word"])
        self.assertEqual(set(rows[1]["strong_terms"]), {"agent+sandbox", "agent+kernel"})
        self.assertEqual(rows[2]["strong_terms"], ["binaural", "beamforming"])
        # 原字段原样保留
        self.assertEqual([r["doi"] for r in rows], ["10.1/a", "10.1/c", "10.1/e"])
        self.assertEqual(rows[0]["authors"], ["Doe, Jane"])
        self.assertEqual(rows[0]["venue"], "Test Venue")

    def test_weak_row_not_written(self):
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn("attack success", text)
        self.assertNotIn("survey of llm agent", text)

    def test_input_file_untouched(self):
        rows = [json.loads(l)
                for l in self.inp.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 5)
        self.assertFalse(any("strong" in r for r in rows))


class Cli(unittest.TestCase):
    def test_main_writes_output_and_prints_stats(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            inp = d / "relevant.jsonl"
            write(inp, [dict(entry("Always-on wake word", doi="10.1/a"),
                             laos_topic="audio-speech"),
                        dict(entry("llm agent reasoning survey", doi="10.1/b"),
                             laos_topic="agent-os")])
            out = d / "strong.jsonl"
            for _ in range(2):  # 第二轮：输出已存在，覆盖语义，不续写
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = csh.main(["--in", str(inp), "--out", str(out),
                                   "--stats"])
                self.assertEqual(rc, 0)
                self.assertEqual(
                    len(out.read_text(encoding="utf-8").splitlines()), 1)
                text = buf.getvalue()
                self.assertIn("audio-speech", text)
                self.assertIn("agent-os", text)
                self.assertIn("spatial-privacy", text)
                self.assertIn("强", text)
                self.assertIn("弱", text)
                self.assertIn("写出 1 行", text)

    def test_main_rejects_out_equal_to_input(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            inp = d / "relevant.jsonl"
            write(inp, [dict(entry("Always-on wake word"),
                             laos_topic="audio-speech")])
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                rc = csh.main(["--in", str(inp), "--out", str(inp)])
            self.assertEqual(rc, 1)
            self.assertTrue(err.getvalue().strip())
            # 输入未被破坏
            self.assertEqual(
                len(json.loads(inp.read_text(encoding="utf-8").splitlines()[0])),
                8)  # entry 七字段 + laos_topic，无 strong/strong_terms

    def test_main_missing_input_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                rc = csh.main(["--in", str(d / "nope.jsonl"),
                               "--out", str(d / "o.jsonl")])
            self.assertEqual(rc, 1)
            self.assertTrue(err.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
