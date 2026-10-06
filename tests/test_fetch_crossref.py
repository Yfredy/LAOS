# tests/test_fetch_crossref.py
"""Crossref 期刊族抓取（Task 3）：item 解析 / JATS 剥离 / cursor 分页 / 零行回退。

fixture 覆盖 brief Step 1 两条：真实形态 Crossref item 的 crossref_to_entry
（year 取 issued.date-parts[0][0]、title 首元素、缺 abstract 置 None），以及
注入 fake urlopen 的 cursor 两页拼接。纯离线，不触网。
"""
import json
import sys
import unittest
import urllib.error
from pathlib import Path

VE = Path(__file__).resolve().parents[1] / "corpus/venue_expansion"
sys.path.insert(0, str(VE))

import fetch_crossref  # noqa: E402
from fetch_crossref import (  # noqa: E402
    SCHEMA_KEYS,
    VENUE_CONF,
    container_family,
    crossref_to_entry,
    fetch_container,
    fetch_journal,
    journal_family,
    norm_title_tokens,
    strip_jats,
)
from make_registry import load_registry  # noqa: E402

REG = VE / "venues.csv"

# 真实形态 item（2026-10-06 实测 api.crossref.org /journals/2998-4173/works 裁剪）
ITEM = {
    "DOI": "10.1109/taslpro.2026.3671637",
    "title": ["RPG-MoGe: Relation Prompt-Guided Multi-Order Generation"],
    "issued": {"date-parts": [[2026]]},
    "container-title": ["IEEE Transactions on Audio Speech and Language Processing"],
    "ISSN": ["2998-4173"],
    "URL": "https://doi.org/10.1109/taslpro.2026.3671637",
    "author": [
        {"given": "Jinzhong", "family": "Ning", "sequence": "first"},
        {"given": "Gyeong-Su", "family": "Kim", "sequence": "additional"},
        {"name": "IEEE Speech Group"},  # 机构作者：无 given/family 只有 name
    ],
}


def item(n, year=2026, **kw):
    d = {
        "DOI": f"10.1109/taslpro.2026.36716{n}",
        "title": [f"Paper {n}"],
        "issued": {"date-parts": [[year]]},
        "container-title": ["IEEE Transactions on Audio Speech and Language Processing"],
        "ISSN": ["2998-4173"],
        "URL": f"https://doi.org/10.1109/taslpro.2026.36716{n}",
    }
    d.update(kw)
    return d


class CrossrefToEntry(unittest.TestCase):
    def test_real_shape_item(self):
        """brief Step 1 核心断言：year/title/venue/doi/url/authors/abstract。"""
        e = crossref_to_entry(ITEM)
        self.assertEqual(e["year"], 2026)  # issued.date-parts[0][0]
        self.assertEqual(e["title"], "RPG-MoGe: Relation Prompt-Guided "
                                     "Multi-Order Generation")  # 首元素
        self.assertEqual(e["venue"], ITEM["container-title"][0])
        self.assertEqual(e["doi"], "10.1109/taslpro.2026.3671637")
        self.assertEqual(e["url"], "https://doi.org/10.1109/taslpro.2026.3671637")
        self.assertEqual(e["authors"], ["Ning, Jinzhong", "Kim, Gyeong-Su",
                                        "IEEE Speech Group"])
        self.assertIsNone(e["abstract"])  # 缺 abstract 字段 -> None
        self.assertEqual(set(e), SCHEMA_KEYS)

    def test_missing_optional_fields(self):
        e = crossref_to_entry({"DOI": "10.1/x", "title": ["T"],
                               "issued": {"date-parts": [[2025, 3]]}})
        self.assertEqual(e["year"], 2025)
        self.assertEqual(e["venue"], "")
        self.assertEqual(e["authors"], [])
        self.assertIsNone(e["abstract"])
        self.assertIsNone(e["url"])

    def test_strip_jats(self):
        raw = ("<jats:p>We study <jats:italic>privacy</jats:italic> "
               "&amp; <jats:sub>x</jats:sub> in agents.</jats:p>")
        self.assertEqual(strip_jats(raw), "We study privacy & x in agents.")
        self.assertIsNone(strip_jats(None))
        # 多段落：标签边界折叠成单空格
        self.assertEqual(strip_jats("<jats:p>One.</jats:p><jats:p>Two.</jats:p>"),
                         "One. Two.")


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def page(items, next_cursor=None):
    msg = {"items": items, "total-results": 10}
    if next_cursor is not None:
        msg["next-cursor"] = next_cursor
    return {"status": "ok", "message-type": "work-list", "message": msg}


class PatchUropenMixin:
    """把模块级 _urlopen 换成按 URL 分发的 fake；记录每次请求 URL。"""

    def setUp(self):
        self.calls = []
        self.routes = []  # [(substr, payload)]，首个命中生效
        self._orig = fetch_crossref._urlopen

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            self.calls.append(url)
            for i, (substr, payload) in enumerate(self.routes):
                if substr in url:
                    self.routes.pop(i)  # 一次性路由，天然模拟翻页序列
                    return FakeResp(payload)
            raise AssertionError(f"fake urlopen: no route for {url}")

        fetch_crossref._urlopen = fake_urlopen

    def tearDown(self):
        fetch_crossref._urlopen = self._orig


class CursorPaging(PatchUropenMixin, unittest.TestCase):
    def test_two_pages_joined_and_cursor_encoded(self):
        """cursor 循环：页满(rows)续翻 next-cursor（须 URL 编码），不满停。"""
        self.routes = [
            ("/works?", page([item(1), item(2), item(3)], next_cursor="C+R/2=")),
            ("/works?", page([item(4), item(5)])),
        ]
        entries = fetch_journal("2998-4173", (2026, 2027), rows=3)
        self.assertEqual([e["title"] for e in entries],
                         ["Paper 1", "Paper 2", "Paper 3", "Paper 4", "Paper 5"])
        self.assertEqual(len(self.calls), 2)
        # 首页带 cursor=*（journal 路由无 query，无 sort；container 路由
        # 的 sort=relevance 断言见 ContainerFamily）
        self.assertIn("cursor=%2A", self.calls[0])
        # 第二页请求必须带正确严格编码后的 cursor（urlencode safe=''：+//%3D）
        self.assertIn("cursor=C%2BR%2F2%3D", self.calls[1])
        # polite pool 参数与年份窗口过滤（urlencode 后 @/: 为 %40/%3A）
        self.assertIn("mailto=laos%40example.com", self.calls[1])
        self.assertIn("from-pub-date%3A2026-01-01", self.calls[1])
        self.assertIn("until-pub-date%3A2027-12-31", self.calls[1])
        self.assertIn("rows=3", self.calls[0])

    def test_limit_truncates(self):
        self.routes = [("/works?", page([item(1), item(2), item(3)],
                                        next_cursor="X")),
                       ("/works?", page([item(4), item(5)]))]
        entries = fetch_journal("2998-4173", (2026, 2027), rows=3, limit=4)
        self.assertEqual(len(entries), 4)

    def test_next_cursor_missing_stops(self):
        """页满但无 next-cursor：宁停不循环（防死循环）。"""
        self.routes = [("/works?", page([item(1), item(2), item(3)]))]
        entries = fetch_journal("2998-4173", (2026, 2027), rows=3)
        self.assertEqual(len(entries), 3)
        self.assertEqual(len(self.calls), 1)

    def test_scan_mode_no_soft_stop_before_exhaustion(self):
        """scan 序无软停：前几页全噪也必须翻到不满页（acmmm 实测真条目
        整段滞后，软停曾把 5252 行的会议误判成 0 行缺口）。"""
        from fetch_crossref import _cursor_paged, _works_url
        noise = dict(item(9))
        noise["title"] = ["Noise Paper"]
        noise["DOI"] = "10.1/noise"
        real = item(1)
        self.routes = (
            [("/works?", page([dict(noise), dict(noise)], next_cursor=f"c{i}"))
             for i in range(1, 6)]            # 5 个满页全噪声
            + [("/works?", page([real]))])    # 末页不满：真条目才出现
        entries = _cursor_paged(
            lambda l, h, r, c: _works_url(l, h, r, c, container="X"),
            2022, 2022, 2, 0, keep=lambda e: e["title"] == "Paper 1")
        self.assertEqual([e["title"] for e in entries], ["Paper 1"])
        self.assertEqual(len(self.calls), 6)

    def test_cursor_404_mid_page_keeps_entries(self):
        """深页 cursor 失效（HTTP 404）保留已收行收束；首页 404 仍抛。"""
        from fetch_crossref import _cursor_paged, _works_url

        def boom_404(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        # 首页 404：真 not-found，向上抛
        fetch_crossref._urlopen = boom_404
        with self.assertRaises(urllib.error.HTTPError):
            _cursor_paged(lambda l, h, r, c: _works_url(l, h, r, c, container="X"),
                          2022, 2022, 2, 0, keep=lambda e: True)

    def test_cursor_404_after_first_page_keeps_kept_entries(self):
        """第 2 页起 404（大召回集 cursor 过期实测形态）：保留已收行返回。"""
        from fetch_crossref import _cursor_paged, _works_url
        real = item(1)
        noise = dict(real)
        noise["title"] = ["Noise Paper"]
        noise["DOI"] = "10.1/noise"
        self.routes = [("/works?", page([real, noise], next_cursor="c2"))]
        orig, seen = fetch_crossref._urlopen, []

        def half_404(req, timeout=None):
            if not seen:
                seen.append(1)
                return orig(req, timeout=timeout)
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        fetch_crossref._urlopen = half_404
        entries = _cursor_paged(
            lambda l, h, r, c: _works_url(l, h, r, c, container="X"),
            2022, 2022, 2, 0, keep=lambda e: e["title"] == "Paper 1")
        self.assertEqual([e["title"] for e in entries], ["Paper 1"])


class ContainerMode(PatchUropenMixin, unittest.TestCase):
    def test_container_exact_match_client_side(self):
        """query.container-title 模糊召回，客户端按 container-title 精确过滤。"""
        noise = item(9, container_title=None)
        noise.pop("container-title")
        noise["container-title"] = ["Transactions on Nonexistent Things"]
        self.routes = [("/works?", page([item(1), noise, item(2)]))]
        entries = fetch_container(
            "IEEE Transactions on Audio Speech and Language Processing",
            (2026, 2027), rows=3)
        self.assertEqual([e["title"] for e in entries], ["Paper 1", "Paper 2"])
        self.assertIn("query.container-title=", self.calls[0])  # 值已 URL 编码

    def test_norm_title_tokens_unescapes_xml_entities(self):
        """Crossref 字段含 XML 转义（KDD 2021 实测 '&amp;'）——规范化前先反转义。"""
        self.assertEqual(
            norm_title_tokens("Proceedings of the 27th ACM SIGKDD Conference on "
                              "Knowledge Discovery &amp; Data Mining"),
            norm_title_tokens("Proceedings of the 27th ACM SIGKDD Conference on "
                              "Knowledge Discovery & Data Mining"))


class ContainerFamily(PatchUropenMixin, unittest.TestCase):
    """Task 4：会议族抓取（variant 并集归并 + prefix 过滤 + DOI 前缀兜底）。

    实测口径（2026-10-06 probe1-9）：出版社逐年缴存容器名（年份前缀/届次后缀），
    官方名几乎从不逐字出现，故 variant 是"可接受容器名集合"的并集（按 DOI 去重），
    而非首个命中即停；query.container-title 多词查询是 OR 语义，查询词须用
    缩写/特征词 + 可选 prefix:<DOI前缀> 过滤压召回。
    """

    PRIMARY = "Proceedings of the ACM SIGKDD International Conference on " \
              "Knowledge Discovery and Data Mining (KDD)"
    VAR_2021 = "Proceedings of the 27th ACM SIGKDD Conference on Knowledge " \
               "Discovery & Data Mining"
    VAR_2022 = "Proceedings of the 28th ACM SIGKDD Conference on Knowledge " \
               "Discovery and Data Mining"

    def kdd_item(self, n, container, year=2022, doi=None):
        d = item(n, year=year,
                 DOI=doi or f"10.1145/3534678.{n:04d}",
                 URL=f"https://doi.org/10.1145/3534678.{n:04d}")
        d["container-title"] = [container]
        return d

    def test_union_of_primary_and_variants_with_dedup(self):
        """两条真变体 + 噪声并收；跨遍历（split_years）同 DOI 只记一次。"""
        y21 = self.kdd_item(1, self.VAR_2021, year=2021)
        y22 = self.kdd_item(2, self.VAR_2022, year=2022)
        noise = self.kdd_item(9, "ACM Transactions on Knowledge Discovery from Data",
                              year=2022)
        dup = dict(self.kdd_item(2, self.VAR_2022, year=2022))
        dup["title"] = ["Paper 2 (dup)"]
        self.routes = [
            ("/works?", page([y21, noise])),          # 2021 遍历
            ("/works?", page([y22, dup])),            # 2022 遍历：同 DOI
        ]
        entries, note, contrib = container_family(
            self.PRIMARY, (2021, 2022),
            variants=[self.VAR_2021, self.VAR_2022], split_years=True)
        self.assertEqual(sorted(e["title"] for e in entries),
                         ["Paper 1", "Paper 2"])  # dup 按 DOI 去重，噪声不收
        by_form = {name: n for name, n in contrib}
        self.assertEqual(by_form[self.VAR_2021], 1)
        self.assertEqual(by_form[self.VAR_2022], 1)
        self.assertNotIn(self.PRIMARY, by_form)  # 官方名本体窗口内未缴存
        # split_years：两次遍历各自带整年窗口
        self.assertIn("from-pub-date%3A2021-01-01", self.calls[0])
        self.assertIn("until-pub-date%3A2021-12-31", self.calls[0])
        self.assertIn("until-pub-date%3A2022-12-31", self.calls[1])

    def test_url_carries_type_and_prefix_filters(self):
        # prefix 遍历 0 行后还会去 prefix 重试一轮，两轮路由都备空页
        self.routes = [("/works?", page([])), ("/works?", page([]))]
        container_family(self.PRIMARY, (2021, 2022), query="SIGKDD",
                         prefix="10.1145")
        self.assertIn("query.container-title=SIGKDD", self.calls[0])
        self.assertIn("type%3Aproceedings-article", self.calls[0])
        self.assertIn("prefix%3A10.1145", self.calls[0])
        # scan 序（不带 sort）：sort=relevance 实测页界跳漏（iccv 6491→5991）
        self.assertNotIn("sort=", self.calls[0])
        self.assertIn("cursor=%2A", self.calls[0])

    def test_prefix_zero_rows_retry_without_prefix(self):
        """10.5220 实测：带 prefix 反而漏真条目——0 行时去 prefix 重试。"""
        noise = self.kdd_item(9, "ACM Transactions on Knowledge Discovery from Data")
        real = self.kdd_item(1, self.VAR_2022)
        self.routes = [
            ("prefix%3A10.1145", page([noise])),  # 带 prefix 遍历：全噪声
            ("/works?", page([real])),            # 去 prefix 重试：命中
        ]
        entries, note, _ = container_family(self.PRIMARY, (2022, 2022),
                                            variants=[self.VAR_2022],
                                            prefix="10.1145")
        self.assertEqual([e["title"] for e in entries], ["Paper 1"])
        self.assertIn("去 prefix", note)

    def test_doi_prefix_fallback_after_all_zero(self):
        """interspeech 兜底：/prefixes/<p>/works + DOI 前缀 ∧ 容器名词元交集。"""
        noise = item(9, container_title=None)
        noise.pop("container-title")
        noise["container-title"] = ["Speech Prosody 2026"]  # 同前缀但非本 venue
        noise["DOI"] = "10.21437/speechprosody.2026"
        good = item(1, container_title=None)
        good.pop("container-title")
        good["container-title"] = ["Interspeech 2026"]      # 容器名变体
        good["DOI"] = "10.21437/interspeech.2026.1"
        wrongdoi = item(2, container_title=None)
        wrongdoi.pop("container-title")
        wrongdoi["container-title"] = ["Interspeech 2026"]  # 容器对但非本前缀
        wrongdoi["DOI"] = "10.9999/not-isca.1"
        self.routes = [
            ("/works?", page([noise])),                            # 容器查询（带 prefix）
            ("/works?", page([noise])),                            # 去 prefix 重试
            ("prefixes/10.21437/works", page([noise, good, wrongdoi])),
        ]
        entries, note, _ = container_family(
            "Interspeech", (2026, 2027), variants=["Interspeech 2026"],
            query="Interspeech", prefix="10.21437", doi_prefix="10.21437")
        self.assertEqual([e["doi"] for e in entries],
                         ["10.21437/interspeech.2026.1"])
        self.assertIn("兜底", note)

    def test_query_by_year_overrides_recall_query(self):
        """neurips：逐年换召回查询词（卷号查询才聚簇），归并集合不变。"""
        real = self.kdd_item(1, self.VAR_2021, year=2021)
        self.routes = [("/works?", page([real])), ("/works?", page([]))]
        container_family(self.PRIMARY, (2021, 2022),
                         variants=[self.VAR_2021, self.VAR_2022],
                         split_years=True,
                         query_by_year={2021: "Systems 34", 2022: "Systems 35"})
        self.assertIn("query.container-title=Systems%2034", self.calls[0])
        self.assertIn("query.container-title=Systems%2035", self.calls[1])
        self.assertIn("until-pub-date%3A2021-12-31", self.calls[0])

    def test_all_zero_registers_gap(self):
        self.routes = [("/works?", page([])), ("/works?", page([]))]
        entries, note, contrib = container_family(
            self.PRIMARY, (2021, 2022), variants=[self.VAR_2021],
            prefix="10.1145")
        self.assertEqual(entries, [])
        self.assertEqual(contrib, [])
        self.assertIn("覆盖缺口", note)


class CliDirectContainer(PatchUropenMixin, unittest.TestCase):
    def test_container_mode_writes_crossref_conf_file(self):
        import tempfile
        real = item(1, container_title=None)
        real.pop("container-title")
        real["container-title"] = ["2022 IEEE/CVF International Conference on "
                                   "Computer Vision (ICCV)"]
        self.routes = [("/works?", page([real]))]
        with tempfile.TemporaryDirectory() as td:
            rc = fetch_crossref.run([
                "--mode", "container", "--venue", "iccv",
                "--name", "IEEE/CVF International Conference on Computer Vision",
                "--variant", "2022 IEEE/CVF International Conference on Computer "
                             "Vision (ICCV)",
                "--years", "2021-2026", "--limit", "10", "--out-dir", td])
            out = (Path(td) / "crossref_conf_iccv.jsonl")
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            lines = [json.loads(l) for l in
                     out.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(set(lines[0]), SCHEMA_KEYS)


class ZeroRowFallback(PatchUropenMixin, unittest.TestCase):
    """TASLP 实况：registry ISSN 只到 2024，2025+ 在同名继任刊记录下。"""

    def test_successor_journal_record_found(self):
        self.routes = [
            # 1) registry ISSN：合法刊但窗口内 0 行
            ("/journals/2329-9290/works", page([])),
            # 2) 刊内备用 ISSN（2329-9304）仍 0 行
            ("/journals/2329-9290", {"message": {
                "title": "IEEE/ACM Transactions on Audio Speech and Language "
                         "Processing",
                "ISSN": ["2329-9290", "2329-9304"]}}),
            ("/journals/2329-9304/works", page([])),
            # 3) 刊名检索：命中继任刊记录（去 IEEE/ACM 词缀后同名列）
            ("/journals?rows=20", {"message": {"items": [
                {"title": "IEEE Transactions on Audio Speech and Language "
                          "Processing", "ISSN": ["2998-4173"]},
                {"title": "Journal of Unrelated Things", "ISSN": ["0000-0001"]},
            ]}}),
            # 4) 继任刊 ISSN 抓到行
            ("/journals/2998-4173/works", page([item(1), item(2)])),
        ]
        entries, used, note = journal_family("2329-9290", (2026, 2027))
        self.assertEqual([e["title"] for e in entries], ["Paper 1", "Paper 2"])
        self.assertEqual(used, "2998-4173")
        self.assertIn("2998-4173", note)
        # 刊名检索词须去 IEEE/ACM 冠名（全名只召回原记录，TASLP 实测）
        search_url = next(u for u in self.calls if "/journals?rows=20" in u)
        qval = search_url.rsplit("query=", 1)[1].split("&")[0].casefold()
        self.assertNotIn("acm", qval.replace("%20", " ").split())
        self.assertNotIn("ieee", qval.replace("%20", " ").split())

    def test_all_zero_returns_empty_with_note(self):
        self.routes = [
            ("/journals/2329-9290/works", page([])),
            ("/journals/2329-9290", {"message": {
                "title": "IEEE/ACM Transactions on Audio Speech and Language "
                         "Processing",
                "ISSN": ["2329-9290", "2329-9304"]}}),
            ("/journals/2329-9304/works", page([])),
            ("/journals?rows=20", {"message": {"items": []}}),
        ]
        entries, used, note = journal_family("2329-9290", (2026, 2027))
        self.assertEqual(entries, [])
        self.assertEqual(used, "2329-9290")
        self.assertIn("0 行", note)

    def test_journal_not_found_404_goes_to_ledger(self):
        def boom(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        fetch_crossref._urlopen = boom
        entries, used, note = journal_family("0000-0000", (2026, 2027))
        self.assertEqual(entries, [])
        self.assertIn("404", note)


class RegistryContract(unittest.TestCase):
    def test_nine_journal_rows_all_have_issn(self):
        rows = [r for r in load_registry(REG) if r["source"] == "crossref_journal"]
        self.assertEqual(len(rows), 9)
        for r in rows:
            self.assertRegex(r["crossref_issn"], r"^\d{4}-\d{3}[\dXx]$",
                             f"{r['venue']} 缺合法 ISSN")

    def test_21_container_rows_covered_by_venue_conf(self):
        """21 行 crossref_container：容器名非空，且每行都有抓取配置。"""
        rows = [r for r in load_registry(REG)
                if r["source"] == "crossref_container"]
        self.assertEqual(len(rows), 21)
        for r in rows:
            self.assertTrue(r["crossref_container"].strip(),
                            f"{r['venue']} 缺容器名")
            self.assertIn(r["venue"], VENUE_CONF,
                          f"{r['venue']} 缺 VENUE_CONF 抓取配置")
            conf = VENUE_CONF[r["venue"]]
            self.assertIn("query", conf)
            self.assertTrue(conf["variants"], f"{r['venue']} 无变体表")
            # 变体名规范化后必须互相可区分（否则并集归并失真）
            toksets = [norm_title_tokens(v) for v in conf["variants"]]
            self.assertEqual(len(set(toksets)), len(toksets),
                             f"{r['venue']} 存在规范化后撞车的变体")
        self.assertEqual(set(VENUE_CONF), {r["venue"] for r in rows})


if __name__ == "__main__":
    unittest.main()
