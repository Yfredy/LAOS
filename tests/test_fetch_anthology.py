# tests/test_fetch_anthology.py
"""ACL Anthology NLP 族抓取（Task 2）：bib 状态机解析 / venue 过滤 / jsonl 写出。

fixture 覆盖 brief Step 1 三类样例：普通条目 / 含 abstract 条目 / 噪音行
（% 注释、条目间散文里的 @、@string、EOF 残缺条目）。纯离线，不触网。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

VE = Path(__file__).resolve().parents[1] / "corpus/venue_expansion"
sys.path.insert(0, str(VE))

from fetch_anthology import (  # noqa: E402
    SCHEMA_KEYS,
    VENUE_PATTERNS,
    _volume_ids,
    entry_matches,
    parse_bib_entries,
    write_jsonl,
)
from make_registry import load_registry  # noqa: E402

REG = VE / "venues.csv"

# 混合定界风格：首条目双引号值（brief fixture 原样），次条目花括号值
BIB = '''% ACL Anthology dump fragment (fixture)
@inproceedings{naacl-2024-fake,
  title = "Agent Sandbox Study",
  author = "Zhang, Wei and Li, Ming",
  booktitle = "Proceedings of NAACL",
  year = "2024",
  url = "https://aclanthology.org/2024.naacl-1.1/"
}
noise between entries -- contact @example.com for questions
@string{acl-abbrev = "Association for Computational Linguistics"}
@article{tacl-fake,
  title = {Always-On Listening},
  abstract = {We study privacy.},
  journal = "TACL",
  volume = "12",
  year = "2024"
}
@inproceedings{broken-no-close,
  title = {dangling'''


class ParseBibEntries(unittest.TestCase):
    def setUp(self):
        self.entries = parse_bib_entries(BIB)

    def test_basic_and_abstract(self):
        """brief Step 1 核心断言（外加作者/年份/URL 细节）。"""
        self.assertEqual(len(self.entries), 2)
        e0, e1 = self.entries
        self.assertEqual(e0["venue"], "Proceedings of NAACL")
        self.assertEqual(e0["title"], "Agent Sandbox Study")
        self.assertEqual(e0["year"], 2024)
        self.assertEqual(e0["authors"], ["Zhang, Wei", "Li, Ming"])
        self.assertEqual(e0["url"], "https://aclanthology.org/2024.naacl-1.1/")
        self.assertIsNone(e0["doi"])
        self.assertIsNone(e0["abstract"])
        self.assertTrue(e1["abstract"].startswith("We study"))
        self.assertEqual(e1["venue"], "TACL")
        self.assertEqual(e1["year"], 2024)
        self.assertEqual(e1["authors"], [])

    def test_schema_keys_exact(self):
        for e in self.entries:
            self.assertEqual(set(e), SCHEMA_KEYS)

    def test_noise_skipped(self):
        """% 注释 / 散文 @ / @string / EOF 残缺条目都不产生条目。"""
        self.assertEqual([e["title"] for e in self.entries],
                         ["Agent Sandbox Study", "Always-On Listening"])

    def test_nested_braces_and_doi(self):
        bib = ('@inproceedings{k-2013,\n'
               '  title = {On the {NAACL}/{{EMNLP}} Split},\n'
               '  doi = {10.18653/v1/k},\n'
               '  booktitle = {Proceedings of NAACL},\n'
               '  year = {2013}\n'
               '}\n')
        e = parse_bib_entries(bib)[0]
        # 剥最外层定界，内层花括号原样保留（含双花括号字面量）
        self.assertEqual(e["title"], "On the {NAACL}/{{EMNLP}} Split")
        self.assertEqual(e["doi"], "10.18653/v1/k")
        self.assertEqual(e["year"], 2013)

    def test_multiline_value_collapsed(self):
        bib = ('@article{m,\n  abstract = {Line one\n  line two.},\n  year = {2020}\n}\n')
        e = parse_bib_entries(bib)[0]
        self.assertEqual(e["abstract"], "Line one line two.")


class VenueFilter(unittest.TestCase):
    NAACL24 = ("Proceedings of the 2024 Conference of the North American Chapter "
               "of the Association for Computational Linguistics (Volume 1: Long Papers)")
    ACL62 = ("Proceedings of the 62nd Annual Meeting of the Association for "
             "Computational Linguistics (Volume 1: Long Papers)")
    EMNLP24 = "Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing"
    FINDINGS_EMNLP = "Findings of the Association for Computational Linguistics: EMNLP 2024"
    FINDINGS_ACL = "Findings of the Association for Computational Linguistics: ACL 2024"
    COLING = "Proceedings of the 31st International Conference on Computational Linguistics"
    CONLL = "Proceedings of the 28th Conference on Computational Natural Language Learning (CoNLL)"
    TACL = "Transactions of the Association for Computational Linguistics"

    def e(self, venue, year):
        return {"title": "x", "year": year, "venue": venue, "authors": [],
                "url": None, "doi": None, "abstract": None}

    def test_nacl_window_and_edges(self):
        self.assertTrue(entry_matches(self.e(self.NAACL24, 2024), "naacl", 2010, 2025))
        self.assertTrue(entry_matches(self.e(self.NAACL24, 2010), "naacl", 2010, 2025))
        self.assertTrue(entry_matches(self.e(self.NAACL24, 2025), "naacl", 2010, 2025))
        self.assertFalse(entry_matches(self.e(self.NAACL24, 2009), "naacl", 2010, 2025))
        self.assertFalse(entry_matches(self.e(self.NAACL24, 2026), "naacl", 2010, 2025))
        # 年份非 int（解析失败的原始串/缺失）一律不匹配
        self.assertFalse(entry_matches(self.e(self.NAACL24, "2024"), "naacl", 2010, 2025))
        self.assertFalse(entry_matches(self.e(self.NAACL24, None), "naacl", 2010, 2025))

    def test_each_prefix_matches_its_real_booktitle(self):
        cases = [
            ("acl", self.ACL62, 2024),
            ("emnlp", self.EMNLP24, 2023),
            ("emnlp", self.FINDINGS_EMNLP, 2024),
            ("acl", self.FINDINGS_ACL, 2024),
            ("naacl", self.NAACL24, 2024),
            ("coling", self.COLING, 2025),
            ("conll", self.CONLL, 2024),
            ("tacl", self.TACL, 2013),
        ]
        for prefix, venue, year in cases:
            self.assertTrue(entry_matches(self.e(venue, year), prefix, 2010, 2025),
                            f"{prefix} 应匹配 {venue!r}")

    def test_brace_protected_booktitles(self):
        """真实 dump 用大小写保护花括号（"North {A}merican Chapter"），
        匹配前必须剥掉，否则 2015/2018/2019 等旧卷全部漏配（回归）。"""
        braced = [
            ("naacl", "Proceedings of the 2015 Conference of the North {A}merican "
                      "Chapter of the Association for Computational Linguistics: "
                      "Human Language Technologies"),
            ("naacl", "Human Language Technologies: The 2010 Annual Conference of "
                      "the North {A}merican Chapter of the {A}ssociation for "
                      "Computational Linguistics"),
            ("naacl", "Proceedings of the 2025 Conference of the Nations of the "
                      "Americas Chapter of the Association for Computational "
                      "Linguistics"),  # 2025 改名 Nations of the Americas
            ("emnlp", "Proceedings of the 2013 Conference on Empirical {M}ethods in "
                      "{N}atural {L}anguage {P}rocessing"),
            ("tacl", "Transactions of the {A}ssociation for Computational "
                     "{L}inguistics"),
        ]
        for prefix, venue in braced:
            self.assertTrue(entry_matches(self.e(venue, 2014), prefix, 2010, 2025),
                            f"{prefix} 应匹配（剥保护括号后）{venue[:60]!r}")
        # ACL 主模式同样要过保护括号（51st {A}nnual {M}eeting …）
        self.assertTrue(entry_matches(
            self.e("Proceedings of the 51st Annual Meeting of the Association for "
                   "Computational {L}inguistics (Volume 1: Long Papers)", 2013),
            "acl", 2010, 2025))

    def test_acl_short_demos_srw_in_but_topic_workshops_out(self):
        """acl 前缀模式收旧短文/演示/SRW 卷，排除同场专题 workshop。"""
        short = self.e("Proceedings of the ACL 2010 Conference Short Papers", 2010)
        demos = self.e("Proceedings of ACL 2017, System Demonstrations", 2017)
        srw = self.e("Proceedings of ACL 2018, Student Research Workshop", 2018)
        self.assertTrue(entry_matches(short, "acl", 2010, 2025))
        self.assertTrue(entry_matches(demos, "acl", 2010, 2025))
        self.assertTrue(entry_matches(srw, "acl", 2010, 2025))
        ws = self.e("Proceedings of the ACL 2012 Joint Workshop on Statistical "
                    "Parsing and Semantic Processing of Morphologically Rich "
                    "Languages", 2012)
        self.assertFalse(entry_matches(ws, "acl", 2010, 2025))

    def test_colocated_workshops_out_but_conll_workshop_series_in(self):
        """裸缩写子串会扫到同场专题 workshop（emnlp/naacl/coling），排除；
        但 CoNLL 老卷本身就叫 "Workshop on Computational Natural Language
        Learning"，必须保留。"""
        ws_emnlp = self.e("Proceedings of the 2018 EMNLP Workshop BlackboxNLP: "
                          "Analyzing and Interpreting Neural Networks for NLP", 2018)
        ws_naacl = self.e("Proceedings of the NAACL HLT 2010 Workshop on Creating "
                          "Speech and Language Data with Amazon's Mechanical Turk",
                          2010)
        ws_coling = self.e("Proceedings of the Third Workshop on Language "
                           "Technologies for Historical and Ancient Languages "
                           "at LREC-COLING 2024", 2024)
        for prefix, e in (("emnlp", ws_emnlp), ("naacl", ws_naacl),
                          ("coling", ws_coling)):
            self.assertFalse(entry_matches(e, prefix, 2010, 2025))
        conll_ws = self.e("Proceedings of the 2007 Joint Conference on Empirical "
                          "Methods in Natural Language Processing and "
                          "Computational Natural Language Learning (EMNLP-CoNLL "
                          "2007)", 2007)
        # 联合卷两属（EMNLP+CoNLL），双方都收；conll 窗口从 2010 起故 2007 不收
        self.assertFalse(entry_matches(conll_ws, "conll", 2010, 2025))
        conll_core = self.e("Proceedings of the Fifteenth Conference on "
                            "Computational Natural Language Learning", 2011)
        self.assertTrue(entry_matches(conll_core, "conll", 2010, 2025))

    def test_no_cross_match(self):
        # 北美章/COLING 的 booktitle 都含 "Association for Computational
        # Linguistics"，不得因此误入 acl；COLING 也不得误入 acl
        for venue in (self.NAACL24, self.COLING, self.EMNLP24, self.CONLL, self.TACL,
                      self.FINDINGS_EMNLP):
            self.assertFalse(entry_matches(self.e(venue, 2024), "acl", 2010, 2025),
                             f"acl 不得匹配 {venue!r}")
        self.assertFalse(entry_matches(self.e(self.ACL62, 2024), "naacl", 2010, 2025))
        self.assertFalse(entry_matches(self.e(self.ACL62, 2024), "coling", 2010, 2025))

    def test_patterns_cover_registry(self):
        rows = [r for r in load_registry(REG) if r["source"] == "anthology"]
        self.assertEqual(len(rows), 6)
        prefixes = {r["anthology_prefix"].strip() for r in rows}
        self.assertLessEqual(prefixes, set(VENUE_PATTERNS), "registry 新增 prefix 需配齐模式")


class JsonlAndVolumes(unittest.TestCase):
    def test_write_jsonl_roundtrip(self):
        entries = parse_bib_entries(BIB)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.jsonl"
            n = write_jsonl(p, entries)
            self.assertEqual(n, 2)
            lines = p.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            for ln, e in zip(lines, entries):
                rec = json.loads(ln)
                self.assertEqual(rec, e)  # None -> null；无换行（值已折叠）
            self.assertNotIn("\r", p.read_text(encoding="utf-8"))

    def test_volume_ids_best_effort_nonempty(self):
        # 分卷路径（保险用）：每个 registry prefix 在 anthology 确有卷的样本年
        # 都有候选卷号（COLING 2010-2014 与老 CoNLL 不在 anthology，无卷可枚举）
        samples = {"acl": (2012, 2024), "emnlp": (2012, 2024), "naacl": (2012, 2024),
                   "coling": (2016, 2024), "conll": (2019, 2024), "tacl": (2014, 2024)}
        for prefix, years in samples.items():
            for year in years:
                self.assertTrue(_volume_ids(prefix, year),
                                f"{prefix}@{year} 无候选卷号")


if __name__ == "__main__":
    unittest.main()
