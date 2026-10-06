#!/usr/bin/env python
"""corpus/venue_expansion/fetch_crossref.py — Crossref 期刊族抓取（Task 3）。

路线：GET https://api.crossref.org/journals/<issn>/works
      ?rows=1000&cursor=<c>&select=…&filter=from-pub-date:<lo>-01-01,
      until-pub-date:<hi>-12-31&mailto=laos@example.com
cursor 初值 "*"，翻页取 message.next-cursor（须 URL 编码），返回条数 < rows 停。
polite pool：全部请求带 mailto=laos@example.com 参数 + 同地址 UA。
退避重试 1s→2s→…→60s ×8（复用 Task 2 语义；404/403 不重试直接抛）。

2026-10-06 实测口径（写死进代码前的三次探测结论）：
  1. TASLP 的 IEEE/ACM 刊记录（issn 2329-9290/2329-9304）Crossref 存量停在
     issued=2024（395 行），2025+ 论文改挂在继任刊记录 "IEEE Transactions on
     Audio Speech and Language Processing"（issn 2998-4173，DOI 前缀 taslpro，
     2025:381 / 2026:360 行）。故 journal_family 做三级零行回退：同刊备用
     ISSN -> 刊名检索同名列继任刊，仍 0 行才记失败清单。
  2. /works?filter=container-title:<名> 的值里带逗号必 400（filter 以逗号
     分隔），所以 fetch_container 走 query.container-title 模糊召回 + 客户端
     按 container-title 规范化精确过滤（Task 4 复用时注意此约束）。
  3. select 支持 URL 字段（https://doi.org/…），abstract 仅部分出版社缴存，
     缺失置 None；author given/family 拼接或取机构 name。

零第三方依赖（urllib/json/re/html/time，纯 stdlib）。断点续抓：输出 jsonl
已存在即跳过（--force 重抓）；单刊失败不卡死，记清单退出码 1。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fetch_anthology import parse_years, write_jsonl, _year_stats  # noqa: E402

API = "https://api.crossref.org"
MAILTO = "laos@example.com"
UA = "laos-venue-expansion/0.1 (research corpus; mailto:laos@example.com)"
HTTP_TIMEOUT = 300
RETRY_DELAYS = [1, 2, 4, 8, 16, 32, 60, 60]  # 1s→2s→…→60s ×8
ROWS = 1000
SELECT = "DOI,title,issued,container-title,ISSN,author,abstract,URL"
MAX_TITLE_CANDIDATES = 5  # 零行回退最多尝试的同名列刊记录数
MAX_CONTAINER_PAGES = 50  # query.container-title 模糊召回的硬页上限（防失控）

SCHEMA_ORDER = ("title", "year", "venue", "authors", "url", "doi", "abstract")
SCHEMA_KEYS = frozenset(SCHEMA_ORDER)


def _log(msg: str) -> None:
    print(f"[fetch_crossref] {msg}", flush=True)


# ---------------------------------------------------------------- 网络（带退避，可注入）

_urlopen = urllib.request.urlopen  # 测试注入点（fake urlopen）


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return _urlopen(req, timeout=HTTP_TIMEOUT)


def http_get_json(url: str) -> dict:
    """GET -> json；指数退避重试 ×8；404/403 不重试直接抛（调用方分诊）。"""
    last = None
    for attempt in range(len(RETRY_DELAYS) + 1):  # 首试 + 8 重试
        try:
            with _open(url) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except AssertionError:  # 测试 fake 路由失配：立刻暴露，不进退避睡眠
            raise
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise
            last = exc
        except Exception as exc:  # TUN 断窗 / 超时 / reset
            last = exc
        if attempt >= len(RETRY_DELAYS):
            break
        delay = RETRY_DELAYS[attempt]
        _log(f"GET {url} 第 {attempt + 1} 次失败（{last!r}），{delay}s 后重试")
        time.sleep(delay)
    raise RuntimeError(f"GET {url} 重试耗尽: {last!r}")


def _works_url(lo: int, hi: int, rows: int, cursor: str, issn: str = "",
               container: str = "") -> str:
    """拼 /journals/<issn>/works 或 /works?query.container-title=… 的完整 URL。"""
    path = f"{API}/journals/{issn}/works" if issn else f"{API}/works"
    q = {"rows": str(rows), "cursor": cursor, "select": SELECT,
         "filter": f"from-pub-date:{lo}-01-01,until-pub-date:{hi}-12-31",
         "mailto": MAILTO}
    if container:
        q = {"query.container-title": container, **q}
    return path + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


# ---------------------------------------------------------------- 解析（纯函数）

_TAG_RE = re.compile(r"<[^>]+>")  # JATS（jats:p/jats:italic/…）一律剥
_WS_RE = re.compile(r"\s+")


def strip_jats(raw):
    """JATS abstract -> 纯文本（剥标签 + 反转义实体 + 折叠空白）；空入 None。"""
    if not raw:
        return None
    txt = html.unescape(_TAG_RE.sub(" ", raw))
    return _WS_RE.sub(" ", txt).strip() or None


def crossref_to_entry(item: dict) -> dict:
    """Crossref message.items[i] -> anthology 同 schema 条目。

    year 取 issued.date-parts[0][0]；title/container-title 取首元素；
    缺 abstract/URL 置 None；author 拼接 "Family, Given"（机构作者取 name）。
    """
    parts = (item.get("issued") or {}).get("date-parts") or []
    year = None
    if parts and parts[0]:
        y = parts[0][0]
        if isinstance(y, int) or (isinstance(y, str) and y.isdigit()):
            year = int(y)
    authors = []
    for a in item.get("author") or []:
        fam, giv = a.get("family"), a.get("given")
        if fam and giv:
            authors.append(f"{fam}, {giv}")
        elif fam or giv:
            authors.append(fam or giv)
        elif a.get("name"):
            authors.append(a["name"])
    return {
        "title": (item.get("title") or [""])[0],
        "year": year,
        "venue": (item.get("container-title") or [""])[0],
        "authors": authors,
        "url": item.get("URL") or None,
        "doi": item.get("DOI") or None,
        "abstract": strip_jats(item.get("abstract")),
    }


# ---------------------------------------------------------------- 抓取（cursor 循环）

def _cursor_paged(url_of, lo: int, hi: int, rows: int, limit: int,
                  keep=None) -> list:
    """cursor 深分页循环：页满续翻 next-cursor，不满即停；limit 截断。"""
    entries, cursor, pages = [], "*", 0
    while True:
        data = http_get_json(url_of(lo, hi, rows, cursor))
        msg = data.get("message") or {}
        items = msg.get("items") or []
        batch = [crossref_to_entry(it) for it in items]
        if keep is not None:
            batch = [e for e in batch if keep(e)]
        entries.extend(batch)
        if limit and len(entries) >= limit:
            return entries[:limit]
        if len(items) < rows:
            return entries
        cursor = msg.get("next-cursor")
        pages += 1
        if not cursor:
            return entries  # 页满但无 next-cursor：宁停不循环
        if keep is not None and pages >= MAX_CONTAINER_PAGES:
            _log(f"模糊召回路径已达硬页上限 {MAX_CONTAINER_PAGES}，提前收束")
            return entries


def fetch_journal(issn: str, years, limit: int = 0, rows: int = ROWS) -> list:
    """/journals/<issn>/works 全量（years 窗口内），cursor 分页。"""
    lo, hi = parse_years(years) if isinstance(years, str) else years
    return _cursor_paged(lambda l, h, r, c: _works_url(l, h, r, c, issn=issn),
                         lo, hi, rows, limit)


_TITLE_STOP = {"ieee", "acm", "the", "of", "on", "in", "and", "for"}


def norm_title_tokens(title: str) -> tuple:
    """刊名规范化 token 集（去 IEEE/ACM 冠名与虚词），用于精确匹配。"""
    toks = re.findall(r"[a-z0-9]+", (title or "").casefold())
    return tuple(sorted(t for t in toks if t not in _TITLE_STOP))


def fetch_container(name: str, years, limit: int = 0, rows: int = ROWS) -> list:
    """按 container-title 抓 /works（Task 4 会议论文集复用）。

    filter=container-title 带逗号必 400（实测），故走 query.container-title
    模糊召回 + 客户端规范化精确过滤；召回页数有硬上限。
    """
    lo, hi = parse_years(years) if isinstance(years, str) else years
    want = norm_title_tokens(name)
    return _cursor_paged(
        lambda l, h, r, c: _works_url(l, h, r, c, container=name),
        lo, hi, rows, limit,
        keep=lambda e: norm_title_tokens(e["venue"]) == want)


# ---------------------------------------------------------------- 零行回退（期刊族）

def _journal_record(issn: str) -> dict:
    """/journals/<issn> 刊记录（title + ISSN 列表）；404 返回空 dict。"""
    try:
        return http_get_json(
            f"{API}/journals/{issn}?mailto={MAILTO}").get("message") or {}
    except urllib.error.HTTPError:
        return {}


def journal_family(issn: str, years, limit: int = 0):
    """registry 单行期刊抓取 + 零行回退，返回 (entries, used_issn, note)。

    回退链（每次只借一个事实来源，全部落日志）：
      1. registry ISSN 直抓（0 行才继续；404 直接记清单，ISSN 本身无效）；
      2. 刊记录里的备用 ISSN 各试一次；
      3. 刊名检索的同名列刊记录（去 IEEE/ACM 冠名后 token 集相等）——
         承接 TASLP 这类换记录主体的继任刊，最多试 MAX_TITLE_CANDIDATES 个。
    """
    tried = {issn}
    try:
        entries = fetch_journal(issn, years, limit=limit)
    except urllib.error.HTTPError as exc:
        return [], issn, f"journal {issn} HTTP {exc.code}（ISSN 无效或未注册）"
    if entries:
        return entries, issn, ""
    rec = _journal_record(issn)
    title = rec.get("title") or ""
    for alt in [i for i in rec.get("ISSN") or [] if i not in tried]:
        tried.add(alt)
        entries = fetch_journal(alt, years, limit=limit)
        if entries:
            return entries, alt, f"{issn} 窗口 0 行，改用同刊备用 ISSN {alt}"
    if not title:
        return [], issn, f"{issn} 窗口 0 行且无刊记录可回退"
    cands = []
    if title:
        # 检索词去掉 IEEE/ACM 等冠名与虚词：带冠名全名查刊名索引只会召回
        # 原记录本身，去冠名 token 查询才能召回同名列继任刊（TASLP 实测）。
        query_txt = " ".join(t for t in re.findall(r"[a-z0-9]+", title.casefold())
                             if t not in _TITLE_STOP) or title
        try:
            found = http_get_json(
                f"{API}/journals?rows=20&query="
                + urllib.parse.quote(query_txt) + f"&mailto={MAILTO}")
            want = norm_title_tokens(title)
            cands = [j for j in (found.get("message") or {}).get("items") or []
                     if norm_title_tokens(j.get("title") or "") == want
                     and any(i not in tried for i in j.get("ISSN") or [])]
        except (urllib.error.HTTPError, RuntimeError) as exc:
            _log(f"刊名检索失败（{exc!r}），跳过继任刊回退")
    for j in cands[:MAX_TITLE_CANDIDATES]:
        cand_issn = next((i for i in j.get("ISSN") or [] if i not in tried), None)
        if not cand_issn:
            continue
        tried.add(cand_issn)
        _log(f"  继任刊候选: {cand_issn} ({j.get('title')})")
        entries = fetch_journal(cand_issn, years, limit=limit)
        if entries:
            return entries, cand_issn, (
                f"{issn} 窗口 0 行（存量止于旧卷），同名列继任刊 {cand_issn}"
                f"（{j.get('title')}）承接增量")
    return [], issn, f"{issn} 及其同刊/同名列 ISSN 窗口均 0 行"


# ---------------------------------------------------------------- CLI 主流程

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:40] or "venue"


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Crossref 期刊族抓取（registry source=crossref_journal 行）")
    ap.add_argument("--mode", choices=["journal", "container"],
                    help="direct 模式：journal 用 --issn，container 用 --name")
    ap.add_argument("--issn", help="journal 模式 ISSN（如 2329-9290）")
    ap.add_argument("--name", help="container 模式 container-title 全名")
    ap.add_argument("--years", help='"2026-2027"（direct 模式必填）')
    ap.add_argument("--venue", help="输出文件名 tag（缺省=issn/name slug）")
    ap.add_argument("--limit", type=int, default=0, help="最多条数（冒烟用；0=全量）")
    ap.add_argument("--registry-run", action="store_true",
                    help="按 registry 跑全部 crossref_journal 行（断点续抓）")
    ap.add_argument("--registry", default=str(HERE / "venues.csv"))
    ap.add_argument("--out-dir", default=str(HERE))
    ap.add_argument("--force", action="store_true",
                    help="输出已存在也重抓（缺省跳过=断点续抓）")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.registry_run:
        if not args.mode or args.mode == "journal" and not args.issn \
                or args.mode == "container" and not args.name or not args.years:
            ap.error("--registry-run 或（--mode + --issn/--name + --years）必选其一")
        if args.mode == "journal":
            entries, used, note = journal_family(args.issn, args.years,
                                                 limit=args.limit)
            tag = args.venue or args.issn
            prefix = "crossref_journal"
        else:
            entries, note = fetch_container(args.name, args.years,
                                            limit=args.limit), ""
            tag = args.venue or _slug(args.name)
            prefix = "crossref_container"
        out = out_dir / f"{prefix}_{tag}.jsonl"
        count = write_jsonl(out, entries)
        _log(f"{tag}: {count} 行 -> {out.name} {_year_stats(entries)}")
        if note:
            _log(f"{tag}: {note}")
        return 0 if count or not note else 1

    from make_registry import load_registry
    rows = [r for r in load_registry(args.registry)
            if r["source"] == "crossref_journal"]
    if not rows:
        _log("registry 无 crossref_journal 行")
        return 2
    todo = [r for r in rows
            if args.force or not (out_dir / f"crossref_journal_{r['venue']}.jsonl").exists()]
    for r in rows:
        if r not in todo:
            _log(f"{r['venue']}: 已存在 crossref_journal_{r['venue']}.jsonl，"
                 f"跳过（断点续抓）")
    summary, failures = [], []
    t0 = time.time()
    for r in todo:
        venue, t1 = r["venue"], time.time()
        try:
            entries, used, note = journal_family(r["crossref_issn"], r["years"],
                                                 limit=args.limit)
        except Exception as exc:  # 单刊失败不卡死
            failures.append((venue, repr(exc)))
            _log(f"{venue}: 抓取异常 {exc!r}")
            continue
        dt = time.time() - t1
        if not entries:
            failures.append((venue, note or "0 行"))
            _log(f"{venue}: 0 行（{dt:.0f}s）—— {note}")
            continue
        out = out_dir / f"crossref_journal_{venue}.jsonl"
        count = write_jsonl(out, entries)
        _log(f"{venue}: {count} 行 [{used}]（{dt:.0f}s）{_year_stats(entries)}")
        if note:
            _log(f"{venue}: {note}")
        summary.append((venue, count, used))
    _log(f"--- 汇总（{len(summary)}/{len(todo)} 刊，{time.time() - t0:.0f}s）---")
    for venue, count, used in summary:
        _log(f"  crossref_journal_{venue}.jsonl: {count} 行 [{used}]")
    if failures:
        _log("失败清单:")
        for venue, why in failures:
            _log(f"  {venue}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
