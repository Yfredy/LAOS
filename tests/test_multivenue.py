"""scripts/crawl_multivenue.py 单元测试 —— venue 精确匹配/合并去重/URL 构造/六类覆盖。

    python -m unittest tests.test_multivenue -v

全部用例为纯函数测试，不发任何真实 HTTP 请求。
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import crawl_multivenue  # noqa: E402
from crawl_multivenue import (  # noqa: E402
    FIELDS,
    VENUES,
    VENUE_NAMES,
    harvest_suggestions,
    merge,
    slice_query,
    venue_of,
    venue_of_fuzzy,
)


class TestVenueOf(unittest.TestCase):
    """① venue_of 精确匹配 + 别名。"""

    def test_exact_match_known_strings(self):
        self.assertEqual(venue_of({"venue": "ACL"}), "ACL")
        self.assertEqual(venue_of({"venue": "EMNLP"}), "EMNLP")
        self.assertEqual(
            venue_of({"venue": "IEEE/ACM Transactions on Audio, Speech, and Language Processing"}),
            "IEEE/ACM Transactions on Audio, Speech, and Language Processing",
        )
        self.assertEqual(
            venue_of({"venue": "EURASIP Journal on Audio, Speech, and Music Processing"}),
            "EURASIP Journal on Audio, Speech, and Music Processing",
        )

    def test_alias_variants_in_expanded_set(self):
        # 同一 venue 的候选别名都在展开集内（含 NeurIPS 的长名/短名双形态）
        for v in [
            "NeurIPS",
            "Annual Conference of the Neural Information Processing Systems",
            "Transactions of the Association for Computational Linguistics",
            "Computational Linguistics",
            "Journal of Machine Learning Research",
            "IEEE Transactions on Pattern Analysis and Machine Intelligence",
            "International Journal of Computer Vision",
            "IEEE Transactions on Multimedia",
            "ACM Transactions on Multimedia Computing, Communications, and Applications",
        ]:
            self.assertEqual(venue_of({"venue": v}), v, v)

    def test_non_target_rejected(self):
        self.assertIsNone(venue_of({"venue": "ICASSP"}))
        self.assertIsNone(venue_of({"venue": "Interspeech"}))
        self.assertIsNone(venue_of({"venue": "arXiv (cs.CL)"}))

    def test_exact_means_case_and_whitespace_sensitive(self):
        # S2 venue 字段客户端精确匹配：大小写/空白不同不算命中
        self.assertIsNone(venue_of({"venue": "acl"}))
        self.assertIsNone(venue_of({"venue": " ACL"}))
        self.assertIsNone(venue_of({"venue": ""}))
        self.assertIsNone(venue_of({"venue": None}))
        self.assertIsNone(venue_of({}))
        self.assertIsNone(venue_of({"title": "no venue field"}))


class TestMerge(unittest.TestCase):
    """② merge 去重 by (title.lower(), year)，同 title 不同 venue 各计一次 venue 命中。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _write(path: Path, obj) -> str:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False))
        return str(path)

    def test_dedup_same_title_year_across_venues(self):
        p_slt = {"title": "Deep Noise Suppression", "year": 2022,
                 "venue": "SLT", "citationCount": 3}
        p_asru = {"title": "DEEP NOISE SUPPRESSION", "year": 2022,
                  "venue": "ASRU", "citationCount": 9}  # 大小写不同 → 去重合并
        f1 = self._write(self.dir / "a.json",
                         {"queries": {"speech enhancement": {"total": 1, "papers": [p_slt]}}})
        f2 = self._write(self.dir / "b.json", {"papers": [p_asru]})
        out = merge([f1, f2])
        self.assertEqual(out["unique_papers"], 1)
        self.assertEqual(out["total_records"], 2)
        self.assertEqual(out["duplicates"], 1)
        # 同 title 不同 venue：各计一次 venue 命中
        self.assertEqual(out["venue_counts"], {"SLT": 1, "ASRU": 1})
        paper = out["papers"][0]
        self.assertEqual(sorted(paper["venues"]), ["ASRU", "SLT"])
        self.assertEqual(paper["venue_hits"], 2)
        self.assertEqual(paper["citationCount"], 9)  # 保留跨副本最高被引

    def test_same_title_different_year_not_merged(self):
        p1 = {"title": "Deep Noise Suppression", "year": 2022, "venue": "SLT", "citationCount": 1}
        p2 = {"title": "Deep Noise Suppression", "year": 2023, "venue": "SLT", "citationCount": 2}
        f = self._write(self.dir / "c.json", [p1, p2])
        out = merge([f])
        self.assertEqual(out["unique_papers"], 2)
        self.assertEqual(out["venue_counts"], {"SLT": 2})

    def test_within_file_duplicate_counts_once_per_venue(self):
        p = {"title": "Codec Paper", "year": 2021, "venue": "TASLP", "citationCount": 0}
        f = self._write(self.dir / "d.json", {"papers": [dict(p), dict(p)]})
        out = merge([f])
        self.assertEqual(out["unique_papers"], 1)
        self.assertEqual(out["venue_counts"], {"TASLP": 1})


class TestSliceQuery(unittest.TestCase):
    """③ slice_query URL 含 venue + year + fields + limit 要素。"""

    def test_url_shape(self):
        url = slice_query("IEEE Spoken Language Technology Workshop", "agent memory")
        self.assertIn("api.semanticscholar.org/graph/v1/paper/search", url)
        self.assertIn("query=agent%20memory", url)
        self.assertIn("venue=IEEE%20Spoken%20Language%20Technology%20Workshop", url)
        self.assertIn("year=2021-2026", url)
        self.assertIn(f"fields={FIELDS}", url)
        self.assertIn("limit=100", url)

    def test_fields_cover_required_schema(self):
        url = slice_query("ACL", "emotion recognition")
        for field in ["title", "year", "venue", "citationCount", "externalIds", "abstract"]:
            self.assertIn(field, url)


class TestVenuesCatalog(unittest.TestCase):
    """④ VENUES 覆盖 Spec 六类（断言类别键集与各类 venue 名单）。"""

    def test_six_category_keys_exactly(self):
        self.assertEqual(
            set(VENUES),
            {"nlp", "ml", "cv", "speech_adj", "multimedia", "cross"},
        )

    def test_all_categories_nonempty(self):
        for cat, strings in VENUES.items():
            self.assertTrue(strings, f"{cat} 不应为空")
            self.assertTrue(all(isinstance(s, str) and s for s in strings), cat)

    def test_spec_venue_names_per_category(self):
        self.assertEqual(
            set(VENUE_NAMES["speech_adj"]),
            {"SLT", "ASRU", "WASPAA", "CHiME", "TASLP", "EURASIP"},
        )
        self.assertEqual(
            set(VENUE_NAMES["nlp"]),
            {"ACL", "EMNLP", "NAACL", "COLING", "CoNLL", "TACL", "CL"},
        )
        self.assertEqual(
            set(VENUE_NAMES["ml"]),
            {"ICLR", "NeurIPS", "ICML", "AAAI", "IJCAI", "JMLR"},
        )
        self.assertEqual(
            set(VENUE_NAMES["cv"]),
            {"CVPR", "ECCV", "ICCV", "TPAMI", "IJCV"},
        )
        self.assertEqual(
            set(VENUE_NAMES["multimedia"]),
            {"ACMMM", "ICMR", "MMSys", "ICME", "PCM", "TMM", "TOMM"},
        )
        self.assertEqual(
            set(VENUE_NAMES["cross"]),
            {"SIGIR", "KDD", "WWW", "WSDM", "RecSys"},
        )
        # Spec 共 ~36 个 venue，全部有候选串
        total = sum(len(v) for v in VENUE_NAMES.values())
        self.assertGreaterEqual(total, 30)

class TestVenueOfFuzzy(unittest.TestCase):
    """⑤ venue_of_fuzzy：casefold + 去标点 + 双向子串（别名表 resolved+tried 并集参与）。

    "NeurIPS" 串能匹配 "Neural Information Processing Systems"；
    "EMNLP" 不含 "Conference on Empirical Methods..." 子串，靠别名表命中。
    """

    def test_emnlp_variants_hit_nlp(self):
        for v in [
            "EMNLP",
            "Conference on Empirical Methods in Natural Language Processing",
            "Empirical Methods in Natural Language Processing",
            "Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing",
        ]:
            self.assertEqual(venue_of_fuzzy({"venue": v}), "nlp", v)

    def test_iclr_icml_variants_hit_ml(self):
        for v in [
            "ICLR",
            "International Conference on Learning Representations",
            "3rd International Conference on Learning Representations",
            "ICML",
            "International Conference on Machine Learning",
            "40th International Conference on Machine Learning",
        ]:
            self.assertEqual(venue_of_fuzzy({"venue": v}), "ml", v)

    def test_slt_variants_hit_speech_adj(self):
        for v in [
            "SLT",
            "IEEE Spoken Language Technology Workshop",
            "IEEE Spoken Language Technology Workshop (SLT)",
            "Spoken Language Technology Workshop",
            "2022 IEEE Spoken Language Technology Workshop (SLT)",
        ]:
            self.assertEqual(venue_of_fuzzy({"venue": v}), "speech_adj", v)

    def test_case_and_punctuation_insensitive(self):
        self.assertEqual(
            venue_of_fuzzy({"venue": "ieee spoken language technology workshop (slt)"}),
            "speech_adj",
        )
        self.assertEqual(
            venue_of_fuzzy({"venue": "PACIFIC-RIM CONFERENCE ON MULTIMEDIA"}),
            "multimedia",
        )
        self.assertEqual(
            venue_of_fuzzy({"venue": "neural information processing systems"}),
            "ml",
        )

    def test_short_alias_does_not_hijack_acronym(self):
        # 别名 "CL"（2 字符）不得把 "ICLR"/"ICML" 劫持到 nlp：等值/最长别名优先
        self.assertEqual(venue_of_fuzzy({"venue": "ICLR"}), "ml")
        self.assertEqual(venue_of_fuzzy({"venue": "ICML"}), "ml")
        self.assertEqual(venue_of_fuzzy({"venue": "ACL"}), "nlp")
        self.assertEqual(venue_of_fuzzy({"venue": "CL"}), "nlp")

    def test_non_target_rejected(self):
        self.assertIsNone(venue_of_fuzzy({"venue": "ICASSP"}))
        self.assertIsNone(venue_of_fuzzy({"venue": "Interspeech"}))
        self.assertIsNone(venue_of_fuzzy({"venue": "arXiv (cs.CL)"}))
        self.assertIsNone(venue_of_fuzzy({"venue": "Transactions on Speech"}))
        self.assertIsNone(venue_of_fuzzy({"venue": ""}))
        self.assertIsNone(venue_of_fuzzy({"venue": None}))
        self.assertIsNone(venue_of_fuzzy({}))
        self.assertIsNone(venue_of_fuzzy({"title": "no venue field"}))


class TestHarvest(unittest.TestCase):
    """⑥ 机会式采集：observed 计数 -> 建议新增规范串（计数>=3 且未精确收录）。"""

    def test_harvest_suggestions_filter_and_sort(self):
        observed = {
            "ICASSP": 9,                                        # 未收录 & >=3 -> 建议
            "INTERSPEECH": 4,                                   # 未收录 & >=3 -> 建议
            "ACL": 12,                                          # 已精确收录 -> 不建议
            "Conference on Empirical Methods in Natural Language Processing": 7,  # 已收录（别名）-> 不建议
            "ISCA Speaker Odyssey": 2,                          # <3 -> 不建议
        }
        self.assertEqual(
            harvest_suggestions(observed=observed),
            [
                {"venue": "ICASSP", "count": 9},
                {"venue": "INTERSPEECH", "count": 4},
            ],
        )

    def test_harvest_default_reads_observed_file(self):
        # 注入 observed 样例文件（临时目录），_load_observed 默认路径读取后过滤
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "multivenue_observed.json"
            obs_path.write_text(
                json.dumps({
                    "updated_at": "2026-09-28 23:00:00",
                    "observed": {"ICASSP": 5, "EMNLP": 6},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(crawl_multivenue, "OBSERVED_PATH", obs_path):
                got = harvest_suggestions()
        self.assertEqual(got, [{"venue": "ICASSP", "count": 5}])  # EMNLP 已收录被滤掉

    def test_run_wave_records_observed_venue_strings(self):
        # mock s2_fetch：wave 返回的 paper venue 串（含被 venue_of 拒绝的邻居串）计入 observed.json
        payload = [
            {"title": "Kept Paper", "year": 2023,
             "venue": "Annual Meeting of the Association for Computational Linguistics"},
            {"title": "Neighbor One", "year": 2023, "venue": "Some Neighbor Venue"},
            {"title": "Neighbor Two", "year": 2024, "venue": "Some Neighbor Venue"},
        ]

        def fake_fetch(url, counters):
            counters["attempts"] += 1
            return {"data": [dict(p) for p in payload], "total": len(payload)}

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with mock.patch.object(crawl_multivenue, "CORPUS_DIR", tmpdir), \
                 mock.patch.object(crawl_multivenue, "OBSERVED_PATH",
                                   tmpdir / "multivenue_observed.json"), \
                 mock.patch.object(crawl_multivenue, "s2_fetch", fake_fetch), \
                 mock.patch.object(crawl_multivenue, "Pacer"):
                rc = crawl_multivenue.run_wave("A", None, limit_requests=1,
                                               dry_run=False, wall_s=600)
                self.assertEqual(rc, 0)
                observed = crawl_multivenue._load_observed()
        self.assertEqual(observed.get("Some Neighbor Venue"), 2)
        self.assertEqual(
            observed.get("Annual Meeting of the Association for Computational Linguistics"), 1,
        )

    def test_cli_harvest_flag_prints_suggestions(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "multivenue_observed.json"
            obs_path.write_text(
                json.dumps({"observed": {"ICASSP": 9, "EMNLP": 3}}, ensure_ascii=False),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with mock.patch.object(crawl_multivenue, "OBSERVED_PATH", obs_path), \
                 contextlib.redirect_stdout(buf):
                rc = crawl_multivenue.main(["--harvest"])
        self.assertEqual(rc, 0)
        self.assertIn("ICASSP", buf.getvalue())
        self.assertNotIn("EMNLP\n", buf.getvalue())  # 已收录串不出现在建议清单


if __name__ == "__main__":
    unittest.main()
