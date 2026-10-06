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
    crossref_to_entry,
    fetch_container,
    fetch_journal,
    journal_family,
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


if __name__ == "__main__":
    unittest.main()
