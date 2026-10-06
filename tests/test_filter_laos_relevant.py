# tests/test_filter_laos_relevant.py
"""laos 相关性过滤（Task 5）：三主线正则词表 / is_relevant 契约 / 跨文件去重。

brief Step 1 正反例逐条断言（"LLM agent operating system constraints"→agent-os；
"always-on audio wake word"→audio-speech；"binaural localization"→spatial-privacy；
"image style transfer diffusion"→False），三主线各 2 正例 + 1 反例；外加契约：
TOPICS 词表照 brief 逐字抄录、is_relevant 返回 (bool, topic|None)、多命中取
TOPICS 迭代序首个、空摘要只匹标题、casefold、标题+摘要拼串跨字段命中、
跨文件同 doi（casefold）或同 title（casefold）去重只留首现、CLI --stats。
纯离线，不触网。
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

VE = Path(__file__).resolve().parents[1] / "corpus/venue_expansion"
sys.path.insert(0, str(VE))

import filter_laos_relevant as flr  # noqa: E402
from filter_laos_relevant import TOPICS, is_relevant, run_filter  # noqa: E402


def entry(title, abstract=None, **kw):
    e = {"title": title, "year": 2026, "venue": "Test Venue",
         "authors": ["Doe, Jane"], "url": "https://x/1",
         "doi": "10.1/t.1", "abstract": abstract}
    e.update(kw)
    return e


def write(path, entries):
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                            for e in entries), encoding="utf-8")


class TopicsVerbatim(unittest.TestCase):
    def test_wordlists_copied_from_brief(self):
        """三主线键齐全，正则逐字等于 brief 词表（防手改漂移）。"""
        self.assertEqual(set(TOPICS), {"agent-os", "audio-speech",
                                       "spatial-privacy"})
        self.assertEqual(
            TOPICS["agent-os"],
            r"(agent).{0,40}(operating system|sandbox|syscall|kernel|"
            r"governan|resource|quota|isolation)|(llm|language model)"
            r".{0,30}(agent)")
        self.assertEqual(
            TOPICS["audio-speech"],
            r"(wake[- ]?word|keyword spotting|vad|voice activity|"
            r"always[- ]?on|speech recognition|asr|tts|diariz|far[- ]?field|"
            r"echo cancell)")
        self.assertEqual(
            TOPICS["spatial-privacy"],
            r"(binaural|spatial audio|beamform|acoustic camera|"
            r"speech privacy|audio watermark)")


class IsRelevant(unittest.TestCase):
    """brief Step 1：三主线各 2 正例 + 1 反例，及 is_relevant 契约。"""

    def test_agent_os_positives(self):
        self.assertEqual(is_relevant(
            entry("LLM agent operating system constraints")), (True, "agent-os"))
        self.assertEqual(is_relevant(
            entry("Sandboxing LLM Agents via Syscall Interception")),
            (True, "agent-os"))

    def test_agent_os_negative(self):
        self.assertEqual(is_relevant(
            entry("Neural Machine Translation with Limited Parallel Data")),
            (False, None))

    def test_audio_speech_positives(self):
        self.assertEqual(is_relevant(
            entry("Always-On Audio Wake Word Detection")),
            (True, "audio-speech"))
        self.assertEqual(is_relevant(
            entry("Far-Field Keyword Spotting with Voice Activity Detection")),
            (True, "audio-speech"))

    def test_audio_speech_negative(self):
        self.assertEqual(is_relevant(
            entry("Singing Melody Extraction from Polyphonic Music")),
            (False, None))

    def test_spatial_privacy_positives(self):
        self.assertEqual(is_relevant(entry("Binaural Localization of Sound")),
                         (True, "spatial-privacy"))
        self.assertEqual(is_relevant(
            entry("Speech Privacy Preservation via Audio Watermarking")),
            (True, "spatial-privacy"))

    def test_brief_negative(self):
        self.assertEqual(is_relevant(
            entry("Image Style Transfer with Diffusion Models")), (False, None))

    def test_return_contract_types(self):
        ok, topic = is_relevant(entry("Wake Word"))
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(topic, str)
        self.assertIn(topic, TOPICS)
        ok2, topic2 = is_relevant(entry("Quantum Error Correction"))
        self.assertIs(ok2, False)
        self.assertIsNone(topic2)

    def test_multi_hit_takes_first_topic_in_topics_order(self):
        # 同时命中三主线：取 TOPICS 迭代序首个
        self.assertEqual(is_relevant(
            entry("LLM agent always-on wake word binaural beamforming")),
            (True, "agent-os"))
        # audio-speech 在 spatial-privacy 之前
        self.assertEqual(is_relevant(
            entry("always-on wake word plus binaural beamforming")),
            (True, "audio-speech"))

    def test_none_abstract_matches_title_only(self):
        self.assertEqual(
            is_relevant(entry("Wake Word Detection", abstract=None)),
            (True, "audio-speech"))
        self.assertEqual(
            is_relevant(entry("Graph Neural Networks", abstract=None)),
            (False, None))

    def test_abstract_used_when_present_and_spans_join(self):
        # 标题中性、摘要命中
        self.assertEqual(is_relevant(
            entry("A Survey of Something", abstract="we evaluate asr systems")),
            (True, "audio-speech"))
        # 标题尾 + 摘要头跨字段拼接仍可命中
        self.assertEqual(is_relevant(
            entry("Modular Agent", abstract="Sandbox Execution Environments")),
            (True, "agent-os"))

    def test_casefold_matching(self):
        self.assertEqual(is_relevant(entry("BINAURAL LOCALIZATION")),
                         (True, "spatial-privacy"))


class RunFilterIO(unittest.TestCase):
    """跨文件去重（同 doi casefold 或同 title casefold 只留首现）+ 行保序。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        d = self.dir = Path(self.td.name)
        write(d / "venue_a.jsonl", [
            entry("LLM agent operating system constraints", doi="10.1/a"),
            entry("Cat Photo Classification", doi="10.1/b"),   # 未命中
            entry("Always-On Wake Word", doi="10.1/c"),
        ])
        write(d / "venue_b.jsonl", [
            entry("Agent Resource Governance", doi="10.1/A"),  # 同 doi（大小写不同）
            entry("always-on wake word", doi=None),            # 同 title casefold
            entry("Binaural Localization", doi="10.1/d"),      # 新命中
        ])
        self.out = d / "laos_relevant.jsonl"
        self.stats = run_filter([d / "venue_a.jsonl", d / "venue_b.jsonl"],
                                self.out)

    def tearDown(self):
        self.td.cleanup()

    def test_counts_and_cross_table(self):
        self.assertEqual(self.stats["total_in"], 6)
        self.assertEqual(self.stats["hits"], 5)
        self.assertEqual(self.stats["dup_hits"], 2)
        self.assertEqual(self.stats["written"], 3)
        self.assertEqual(self.stats["per_topic"],
                         {"agent-os": 1, "audio-speech": 1,
                          "spatial-privacy": 1})
        # venue 键 = 源文件 stem（0 行文件天然不出现）
        self.assertEqual(self.stats["cross"],
                         {"venue_a": {"agent-os": 1, "audio-speech": 1},
                          "venue_b": {"spatial-privacy": 1}})

    def test_output_rows_ordered_with_laos_topic(self):
        rows = [json.loads(l)
                for l in self.out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["title"] for r in rows],
                         ["LLM agent operating system constraints",
                          "Always-On Wake Word", "Binaural Localization"])
        self.assertEqual([r["laos_topic"] for r in rows],
                         ["agent-os", "audio-speech", "spatial-privacy"])
        # 原行全部字段原样保留
        self.assertEqual(rows[0]["doi"], "10.1/a")
        self.assertEqual(rows[0]["authors"], ["Doe, Jane"])
        self.assertEqual(rows[0]["venue"], "Test Venue")


class Cli(unittest.TestCase):
    def test_main_writes_output_and_prints_stats_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            write(d / "venue_x.jsonl",
                  [entry("Always-On Wake Word", doi="10.1/x"),
                   entry("Cat Photo Classification", doi="10.1/y")])
            out = d / "relevant.jsonl"
            for _ in range(2):  # 第二轮：输出文件已存在，不得被当输入
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = flr.main(["--ve-dir", str(d), "--out", str(out),
                                   "--stats"])
                self.assertEqual(rc, 0)
                self.assertEqual(
                    len(out.read_text(encoding="utf-8").splitlines()), 1)
                text = buf.getvalue()
                self.assertIn("audio-speech", text)
                self.assertIn("venue_x", text)
                self.assertIn("命中 1", text)

    def test_main_no_inputs_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            buf, err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                rc = flr.main(["--ve-dir", td, "--out",
                               str(Path(td) / "r.jsonl")])
            self.assertEqual(rc, 1)
            self.assertTrue(err.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
