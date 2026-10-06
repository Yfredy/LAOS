# tests/test_venue_registry.py
"""venue 注册表校验：schema/去重/年窗/来源分派。"""
import csv, re, unittest
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "corpus/venue_expansion/venues.csv"
HAVE = {"icassp", "interspeech", "taslp", "asru", "slt", "aaai", "iclr"}  # 已有语料 venue（小写）

class Registry(unittest.TestCase):
    def setUp(self):
        with open(REG, encoding="utf-8") as fh:
            self.rows = list(csv.DictReader(fh))

    def test_schema_and_nonempty(self):
        need = {"venue", "ccf", "source", "years"}
        for r in self.rows:
            self.assertTrue(need <= set(r), r)
            self.assertTrue(r["venue"] and r["source"] in
                            {"anthology", "crossref_journal", "crossref_container", "deferred"}, r)

    def test_venue_unique_casefold(self):
        names = [r["venue"].casefold() for r in self.rows]
        self.assertEqual(len(names), len(set(names)))

    def test_existing_corpus_incremental_only(self):
        # 已有语料 venue 只允许增量年份：notes 须注明 incremental 且声明
        # 已覆盖终点（"…through YYYY"），years 起点须严格晚于该终点
        for r in self.rows:
            if r["venue"].casefold() in HAVE:
                hay = (r["years"] + " " + r["notes"]).casefold()
                self.assertIn("incremental", hay, r["venue"])
                m = re.search(r"through (\d{4})", r["notes"])
                self.assertTrue(
                    m, f'{r["venue"]}: notes 未声明已覆盖终点')
                start = int(r["years"][:4])
                self.assertGreater(
                    start, int(m.group(1)),
                    f'{r["venue"]}: years 起点 {start} 未晚于已覆盖终点 '
                    f"{m.group(1)}")

    def test_user_list_covered(self):
        want = {"naacl", "coling", "conll", "tacl", "neurips", "icml", "ijcai",
                "iccv", "tpami", "ijcv", "waspaa", "chime", "eurasip-jasmp",
                "icmr", "mmsys", "icme", "pcm", "tmm", "tomm", "sigir", "kdd",
                "www", "wsdm", "recsys", "icip", "globalsip"}
        got = {r["venue"].casefold() for r in self.rows}
        self.assertEqual(want - got, set(), f"缺: {want - got}")


class LoadRegistry(unittest.TestCase):
    """load_registry 接口（T2-T4 抓取任务按 source 列消费此表）。"""

    def test_load_registry_returns_validated_rows(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus/venue_expansion"))
        from make_registry import load_registry
        rows = load_registry(REG)
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)
        by = {r["venue"].casefold(): r for r in rows}
        # 分派列齐备：anthology 行有 anthology_prefix；crossref_journal 行有 issn；
        # crossref_container 行有 container；deferred 行只说明缺口
        for r in rows:
            if r["source"] == "anthology":
                self.assertTrue(r["anthology_prefix"], r["venue"])
            elif r["source"] == "crossref_journal":
                self.assertTrue(r["crossref_issn"], r["venue"])
            elif r["source"] == "crossref_container":
                self.assertTrue(r["crossref_container"], r["venue"])

    def test_load_registry_rejects_duplicates(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "corpus/venue_expansion"))
        from make_registry import load_registry
        bad = REG.parent / "_tmp_bad_registry.csv"
        bad.write_text(
            "venue,ccf,dblp_stream,crossref_issn,crossref_container,anthology_prefix,years,source,notes\n"
            "naacl,B,conf/naacl,,,naacl,2010-2025,anthology,x\n"
            "NAACL,B,conf/naacl,,,naacl,2010-2025,anthology,dup\n",
            encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                load_registry(bad)
        finally:
            bad.unlink()


if __name__ == "__main__":
    unittest.main()
