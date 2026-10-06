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

Task 4（会议族，2026-10-06 probe1-9 实测口径）：
  1. 出版社逐年缴存容器名（年份前缀 "2023 IEEE …"、届次 "Proceedings of the
     30th ACM SIGKDD …"、卷号 "…Systems 37"、甚至 V.1/V.2 分卷），registry
     官方名几乎从不逐字出现——所以 variant 不是"首个命中即停"的替换拼写，而是
     "可接受容器名集合"的并集（跨遍历按 DOI 去重）。
  2. query.container-title 多词查询是 OR 语义：查询词混入年份/proceedings/
     conference 等常见词，召回暴涨到几十万（"Interspeech 2025"→447k vs
     "Interspeech"→1.2k）。召回查询词必须用缩写/特征词（SIGKDD/ICME/ASRU），
     再用 filter=prefix:<DOI前缀>（无逗号，与 container-title filter 无关）
     按出版社压噪声；通用词会议（acmmm/www/mmsys/slt/wsdm/recsys）逐年
     分窗遍历压页数。
  3. DOI 前缀过滤值必须逐字精确：Curran（NeurIPS）=10.52202，SciTePress
     =10.5220——差一位过滤到另一家，看起来像"带 prefix 反漏真条目"。
     保险起见 prefix 变体 0 行时自动去 prefix 重试一轮。
  3b. query 端点 cursor=* 深分页是 scan 序（无相关度排序但遍历完整）；
     带 sort=relevance 虽保聚簇序，实测页界跳漏（iccv 全量 6491 → 5991），
     故取 scan 序 + prefix 压噪 + 客户端精确归并。
  4. Crossref 字段里 "&" 以 XML 转义 "&amp;" 缴存（KDD 2021 实测），
     norm_title_tokens 先 html.unescape 再切词。
  5. IJCAI 2022+ 的 10.24963 DOI 存在但 container-title 为空串——名字通道
     抓不到，登记覆盖缺口。Interspeech 2026+ 走 /prefixes/10.21437/works
     兜底（DOI 前缀 ∧ 容器名词元交集，防 Speech Prosody/Odyssey 误收）。
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
MAX_CONTAINER_PAGES = 50  # 模糊召回的硬页上限（防失控；召回须靠 prefix/特征词压进 50 页内）

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


def _works_url(lo: int, hi: int, rows: int, cursor: str,
               issn: str = "", container: str = "", prefix: str = "",
               ptype: bool = False) -> str:
    """拼 /journals/<issn>/works 或 /works?query.container-title=… 的完整 URL。

    container 模式可叠加 type:proceedings-article（brief Step 3 口径）与
    prefix:<DOI前缀>（出版社过滤，值无逗号不触 400）。query 端点两个实测坑：
    (1) sort=relevance 虽保聚簇序，但深翻页会页界跳漏（iccv 6491→5991），
    故走 cursor=* 的 scan 序（无序但完整，配合 prefix 压噪 + 客户端精确
    归并）；(2) DOI 前缀须逐字精确：Curran=10.52202，SciTePress=10.5220
    ——差一位就是另一家。
    """
    path = f"{API}/journals/{issn}/works" if issn else f"{API}/works"
    flt = f"from-pub-date:{lo}-01-01,until-pub-date:{hi}-12-31"
    if ptype:
        flt += ",type:proceedings-article"
    if prefix:
        flt += f",prefix:{prefix}"
    q = {"rows": str(rows), "cursor": cursor, "select": SELECT,
         "filter": flt, "mailto": MAILTO}
    if container:
        q = {"query.container-title": container, **q}
    return path + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def _prefix_works_url(lo: int, hi: int, rows: int, cursor: str,
                      doi_prefix: str) -> str:
    """/prefixes/<p>/works（DOI 前缀全量，无模糊查询，召回小，不加 type 过滤）。"""
    q = {"rows": str(rows), "cursor": cursor, "select": SELECT,
         "filter": f"from-pub-date:{lo}-01-01,until-pub-date:{hi}-12-31",
         "mailto": MAILTO}
    if cursor is None:
        q.pop("cursor")
    return (f"{API}/prefixes/{doi_prefix}/works?"
            + urllib.parse.urlencode(q, quote_via=urllib.parse.quote))


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
    """cursor 深分页循环：页满续翻 next-cursor，不满即停；limit 截断。

    keep 模式（模糊召回）只有硬页上限 50 一道闸——不加"连续空页软停"：
    scan 序（cursor=*）里真条目可能整段滞后（acmmm 实测前 10 页全噪、
    真条目在其后，软停直接误判缺口 0 行）。召回靠 prefix/特征词压到 50
    页内，翻到自然不满页为止即完整。翻页中 cursor 失效（404/410，大召回
    集换页常见）保留已收行提前收束，首页 404 仍然抛（真 not-found 分诊）。
    """
    entries, cursor, pages = [], "*", 0  # cursor=* 起（scan 序：无序但完整）
    while True:
        try:
            data = http_get_json(url_of(lo, hi, rows, cursor))
        except urllib.error.HTTPError as exc:
            if cursor != "*" and exc.code in (404, 410):
                _log(f"翻页 cursor 失效（HTTP {exc.code}），保留已收 "
                     f"{len(entries)} 行提前收束")
                return entries
            raise
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
    """刊名/容器名规范化 token 元组（剥 XML 转义 + 去 IEEE/ACM 冠名与虚词）。

    Crossref 的 "&amp;" 实测存在于 container-title（KDD 2021），先 html.unescape
    再切词，否则 "&" 形与 "and" 形永远不相等。保留重复词元（sorted 元组），
    "ICASSP 2026 - 2026 IEEE…" 与 "2026 IEEE…" 因此可区分。
    """
    toks = re.findall(r"[a-z0-9]+", html.unescape(title or "").casefold())
    return tuple(sorted(t for t in toks if t not in _TITLE_STOP))


def fetch_container(name: str, years, limit: int = 0, rows: int = ROWS,
                    query: str = "", prefix: str = "",
                    accepted: frozenset = None) -> list:
    """按 container-title 抓 /works（Task 4 会议论文集）。

    filter=container-title 带逗号必 400（实测），故走 query.container-title
    模糊召回 + 客户端规范化精确过滤；召回页数有硬上限。query 用缩写/特征词
    压 OR 召回（缺省=容器名全文）；accepted 是可接受容器名 token 元组集合
    （缺省=容器名本体），跨年变体由调用方并入。
    """
    lo, hi = parse_years(years) if isinstance(years, str) else years
    if accepted is None:
        accepted = {norm_title_tokens(name)}
    return _cursor_paged(
        lambda l, h, r, c: _works_url(l, h, r, c, container=query or name,
                                      prefix=prefix, ptype=True),
        lo, hi, rows, limit,
        keep=lambda e: norm_title_tokens(e["venue"]) in accepted)


def fetch_doi_prefix(doi_prefix: str, years, keep_tokens: frozenset = None,
                     limit: int = 0, rows: int = ROWS) -> list:
    """/prefixes/<p>/works 兜底（Interspeech：10.21437 全是 ISCA 系事件）。

    keep 规则：DOI 前缀匹配 ∧（若给 keep_tokens）容器名与官方名共享至少一个
    词元——挡住同前缀的 Speech Prosody/Odyssey/JEP 等姊妹会议。
    """
    lo, hi = parse_years(years) if isinstance(years, str) else years

    def _keep(e):
        if not (e["doi"] or "").casefold().startswith(doi_prefix.casefold()):
            return False
        if keep_tokens is not None and not (
                set(norm_title_tokens(e["venue"])) & set(keep_tokens)):
            return False
        return True

    return _cursor_paged(
        lambda l, h, r, c: _prefix_works_url(l, h, r, c, doi_prefix),
        lo, hi, rows, limit, keep=_keep)


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


# ---------------------------------------------------------------- 会议族（Task 4）

_PREFIX_ACM, _PREFIX_IEEE, _PREFIX_ISCA = "10.1145", "10.1109", "10.21437"


def _ord_lo(n):
    """序数词英文写法（WSDM/RecSys/IJCAI 的官方容器名用英文届次，实测）。"""
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


VENUE_CONF = {
    # query=召回特征词（压 OR 噪声）；prefix=filter:prefix 出版社过滤（neurips
    # 实测反漏，置空）；split=逐年分窗遍历（通用词会议召回大）；variants=可
    # 接受容器名（probe1-9 观测到的官方缴存书写，逐年前缀/届次/分卷差异）；
    # doi_prefix=全零时的 /prefixes 兜底。全部为 2026-10-06 实测观测形式。
    "neurips": {
        # Curran 前缀 = 10.52202（逐字精确；10.5220 是 SciTePress）。
        # 实测逐年存量：v35=2022 3022 / v36=2023 4062 / v37=2024 4938 /
        # v38=2025 6225；v34(2021) 与 v39(2026) 未缴存 → 缺口
        "query": "Advances in Neural Information Processing Systems",
        "prefix": "10.52202", "split": True,
        "variants": [f"Advances in Neural Information Processing Systems {v}"
                     for v in range(34, 40)],  # v34=2021 … v39=2026
    },
    "ijcai": {
        # 2024 卷官方缴存名有排版笔误 "Thirty-ThirdInternational"（缺空格，
        # 实测 999 行全是这形），按逐字变体收录；其余届次书写正常
        "query": "International Joint Conference on Artificial Intelligence",
        "prefix": "10.24963", "split": False,
        "variants": ["Proceedings of the " + w + " International Joint "
                     "Conference on Artificial Intelligence"
                     for w in ("Thirtieth", "Thirty-First", "Thirty-Second",
                               "Thirty-Third", "Thirty-Fourth", "Thirty-Fifth")]
                    + ["Proceedings of the Thirty-ThirdInternational Joint "
                       "Conference on Artificial Intelligence"],
    },
    "iccv": {
        "query": "ICCV", "prefix": _PREFIX_IEEE, "split": False,
        "variants": [f"{y} IEEE/CVF International Conference on Computer Vision "
                     f"(ICCV)" for y in (2021, 2023, 2025)],
    },
    "icassp": {
        "query": "ICASSP", "prefix": _PREFIX_IEEE, "split": False,
        # 2024-2026 实测形 "ICASSP 2026 - 2026 IEEE …(ICASSP)"；窗口 2027-2028
        "variants": [f"ICASSP {y} - {y} IEEE International Conference on "
                     f"Acoustics, Speech and Signal Processing (ICASSP)"
                     for y in (2027, 2028)]
                    + [f"{y} IEEE International Conference on Acoustics, Speech "
                       f"and Signal Processing (ICASSP)" for y in (2027, 2028)],
    },
    "interspeech": {
        # 2026-2027：Interspeech 2026 未缴存（10.21437 前缀 2026 窗口只有
        # Speech Prosody/Odyssey/JEP/CHiME 等 ISCA 姊妹事件）——prefix 兜底
        # 同前缀但容器名需含 "interspeech" 词元，防误收
        "query": "Interspeech", "prefix": _PREFIX_ISCA, "split": False,
        "doi_prefix": _PREFIX_ISCA,
        "variants": ["Interspeech 2026", "Interspeech 2027"],
    },
    "asru": {
        "query": "ASRU", "prefix": _PREFIX_IEEE, "split": False,
        # 2025 实测形无 "Workshop on" 前缀且届词序不同；窗口 2026-2027
        "variants": ["IEEE Automatic Speech Recognition and Understanding "
                     "Workshop (ASRU)"]
                    + [f"{y} IEEE Automatic Speech Recognition and Understanding "
                       f"Workshop (ASRU)" for y in (2026, 2027)],
    },
    "slt": {
        "query": "Spoken Language Technology", "prefix": _PREFIX_IEEE,
        "split": True,
        "variants": [f"{y} IEEE Spoken Language Technology Workshop (SLT)"
                     for y in (2026, 2027)],
    },
    "waspaa": {
        "query": "WASPAA", "prefix": _PREFIX_IEEE, "split": False,
        "variants": [f"{y} IEEE Workshop on Applications of Signal Processing "
                     f"to Audio and Acoustics (WASPAA)"
                     for y in (2021, 2023, 2025)],
    },
    "chime": {
        "query": "CHiME", "prefix": _PREFIX_ISCA, "split": False,
        # 系列更名：CHiME-7 起 "Speech Processing in Everyday Environments"，
        # CHiME-9 是 challenge 名（probe2 前缀路由实测 14 行）
        "variants": [
            f"{o} International Workshop on Speech Processing in Everyday "
            f"Environments (CHiME {y})"
            for o, y in (("7th", 2023), ("8th", 2024))]
            + ["9th CHiME Speech Separation and Recognition Challenge "
               "(CHiME 2026)"],
    },
    "acmmm": {
        "query": "International Conference on Multimedia",
        "prefix": _PREFIX_ACM, "split": True,
        "variants": [f"Proceedings of the {_ord_lo(n)} ACM International "
                     f"Conference on Multimedia" for n in range(29, 35)],
    },
    "icme": {
        "query": "ICME", "prefix": _PREFIX_IEEE, "split": False,
        "variants": [f"{y} IEEE International Conference on Multimedia and "
                     f"Expo (ICME)" for y in range(2021, 2027)],
    },
    "icmr": {
        "query": "Multimedia Retrieval", "prefix": _PREFIX_ACM, "split": False,
        # 2023 实测带 ACM 冠名、其余年份不带；norm 剥 ACM 冠名后两者同形，
        # 单形式即可全收
        "variants": [f"Proceedings of the {y} International Conference on "
                     f"Multimedia Retrieval" for y in range(2021, 2027)],
    },
    "mmsys": {
        "query": "Multimedia Systems Conference", "prefix": _PREFIX_ACM,
        "split": True,
        # 2021-2023/2025 届次形；2024 卷缴存名带 ACM DL 占位后缀
        # "…Conference 2024 on ZZZ"（实测），2026 年份后缀形
        "variants": [f"Proceedings of the {_ord_lo(n)} ACM Multimedia Systems "
                     f"Conference" for n in (12, 13, 14, 16)]
                    + ["Proceedings of the ACM Multimedia Systems Conference "
                       f"{y}" for y in (2026,)]
                    + ["Proceedings of the ACM Multimedia Systems Conference "
                       "2024 on ZZZ"],
    },
    "pcm": {
        # Springer LNCS/CCIS 卷在 Crossref 无此容器名（probe3 bibliographic
        # 全噪声）——官方名 + 连字符变体，0 行即覆盖缺口（registry 预告 sparse）
        "query": "Pacific-Rim Conference on Multimedia", "prefix": "",
        "split": False, "variants": ["Pacific Rim Conference on Multimedia"],
    },
    "icip": {
        "query": "ICIP", "prefix": _PREFIX_IEEE, "split": False,
        "variants": [f"{y} IEEE International Conference on Image Processing "
                     f"(ICIP)" for y in range(2021, 2027)],
    },
    "sigir": {
        "query": "SIGIR", "prefix": _PREFIX_ACM, "split": False,
        "variants": [f"Proceedings of the {_ord_lo(n)} International ACM SIGIR "
                     f"Conference on Research and Development in Information "
                     f"Retrieval" for n in range(44, 50)],
    },
    "kdd": {
        "query": "SIGKDD", "prefix": _PREFIX_ACM, "split": False,
        # 2021 "&" 形（&amp; 缴存，norm 已剥转义），2022-2024 "and" 形，
        # 2025+ V.1/V.2 分卷形 + 平形并存（probe1/3 实测）
        "variants": (
            ["Proceedings of the 27th ACM SIGKDD Conference on Knowledge "
             "Discovery & Data Mining"]
            + [f"Proceedings of the {_ord_lo(n)} ACM SIGKDD Conference on "
               f"Knowledge Discovery and Data Mining" for n in range(28, 33)]
            + [f"Proceedings of the {_ord_lo(n)} ACM SIGKDD Conference on "
               f"Knowledge Discovery and Data Mining V.{v}"
               for n in (31, 32) for v in (1, 2)]),
    },
    "www": {
        "query": "Web Conference", "prefix": _PREFIX_ACM, "split": True,
        # 2021 旧名 "Web Conference"（无 ACM）；2025 起改 "ACM on Web
        # Conference"（PACM 系命名，probe3 实测）
        "variants": ["Proceedings of the Web Conference 2021"]
                    + [f"Proceedings of the ACM Web Conference {y}"
                       for y in (2022, 2023, 2024, 2026)]
                    + ["Proceedings of the ACM on Web Conference 2025"],
    },
    "wsdm": {
        "query": "Web Search and Data Mining", "prefix": _PREFIX_ACM,
        "split": False,
        # 数字/英文届次混用（probe1 实测），逐年形式按观测固定
        "variants": ["Proceedings of the " + w + " ACM International Conference "
                     "on Web Search and Data Mining"
                     for w in ("14th", "Fifteenth", "Sixteenth", "17th",
                               "Eighteenth", "Nineteenth")],
    },
    "recsys": {
        "query": "Recommender Systems", "prefix": _PREFIX_ACM, "split": False,
        "variants": [
            "Fifteenth ACM Conference on Recommender Systems",        # 2021
            "Proceedings of the 16th ACM Conference on Recommender Systems",
            "Proceedings of the 17th ACM Conference on Recommender Systems",
            "18th ACM Conference on Recommender Systems",             # 2024
            "Proceedings of the Nineteenth ACM Conference on Recommender Systems",
            "Proceedings of the 20th ACM Conference on Recommender Systems"],
    },
    "globalsip": {
        "query": "GlobalSIP", "prefix": _PREFIX_IEEE, "split": False,
        "variants": [f"{y} IEEE Global Conference on Signal and Information "
                     f"Processing (GlobalSIP)" for y in range(2013, 2020)],
    },
}


def container_family(name, years, variants=(), query="", prefix="",
                     split_years=False, doi_prefix="", query_by_year=None,
                     limit: int = 0):
    """registry 会议行抓取，返回 (entries, note, contributions)。

    归并：item 容器名 token 元组 ∈ {官方名} ∪ variants（probe 实测出版社逐年
    变体，官方名几乎从不逐字出现，故取并集而非首个命中即停），跨遍历按 DOI
    去重。split_years=True 逐年分窗（通用词会议召回大，压页数）；query_by_year
    允许逐年换召回查询词。prefix 过滤 0 行时自动去 prefix 重试（前缀值逐字
    精确，差一位即错家——防御性回退）。仍 0 行且配了 doi_prefix，走
    /prefixes/<p>/works 兜底（前缀 ∧ 词元交集）；最终 0 行则 note 记"覆盖
    缺口"。contributions = [(变体名, 行数)]。
    """
    lo, hi = parse_years(years) if isinstance(years, str) else years
    label_of = {}
    for cand in (name, *variants):
        label_of.setdefault(norm_title_tokens(cand), cand)
    q = query or name
    qmap = query_by_year or {}
    windows = ([(y, y) for y in range(lo, hi + 1)] if split_years
               else [(lo, hi)])

    def _run(pfx):
        got, contrib = {}, {}
        for wlo, whi in windows:
            for e in fetch_container(name, (wlo, whi),
                                     query=qmap.get(wlo) or q, prefix=pfx,
                                     accepted=set(label_of)):
                key = e["doi"] or f"{e['title']}\x00{e['year']}"
                if key in got:
                    continue
                got[key] = e
                lab = label_of.get(norm_title_tokens(e["venue"]), "（无名形）")
                contrib[lab] = contrib.get(lab, 0) + 1
        return list(got.values()), contrib

    entries, contrib, note = [], {}, ""
    for pfx in ([prefix, ""] if prefix else [""]):
        entries, contrib = _run(pfx)
        if entries:
            if pfx != prefix:
                note = f"prefix={prefix} 召回 0 行，去 prefix 重试命中"
            break
    if not entries and doi_prefix:
        fb = fetch_doi_prefix(doi_prefix, (lo, hi),
                              keep_tokens=norm_title_tokens(name))
        if fb:
            uniq = {}
            for e in fb:
                uniq.setdefault(e["doi"] or f"{e['title']}\x00{e['year']}", e)
            entries, contrib = list(uniq.values()), {
                f"DOI 前缀 {doi_prefix} 兜底": len(uniq)}
            note = (f"容器名及变体窗口 0 行，DOI 前缀 {doi_prefix} 兜底承接 "
                    f"{len(entries)} 行")
    if not entries:
        note = (note or f"官方名及 {len(variants)} 个变体窗口均 0 行"
                f"（覆盖缺口）")
    if limit:
        entries = entries[:limit]
    return entries, note, sorted(contrib.items(), key=lambda kv: -kv[1])


# ---------------------------------------------------------------- CLI 主流程

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:40] or "venue"


def _conf_for_direct(name: str, venue: str, registry: str) -> dict:
    """direct 容器模式自动接 VENUE_CONF（--venue 命中或容器名与 registry 全等）。"""
    if venue in VENUE_CONF:
        return VENUE_CONF[venue]
    from make_registry import load_registry
    want = (name or "").strip().casefold()
    for r in load_registry(registry):
        if r["source"] == "crossref_container" \
                and r["crossref_container"].strip().casefold() == want:
            return VENUE_CONF.get(r["venue"], {})
    return {}


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Crossref 期刊/会议族抓取（registry crossref_journal / "
                    "crossref_container 行）")
    ap.add_argument("--mode", choices=["journal", "container"],
                    help="direct 模式：journal 用 --issn，container 用 --name")
    ap.add_argument("--issn", help="journal 模式 ISSN（如 2329-9290）")
    ap.add_argument("--name", help="container 模式 container-title 全名")
    ap.add_argument("--variant", action="append", default=[],
                    help="container 模式可接受容器名变体（可重复；缺省取 "
                         "--venue 对应 VENUE_CONF）")
    ap.add_argument("--query", help="container 模式召回查询词（缺省=容器名）")
    ap.add_argument("--prefix-filter", dest="prefix_filter", default="",
                    help="filter=prefix:<DOI前缀> 出版社过滤")
    ap.add_argument("--doi-prefix", dest="doi_prefix", default="",
                    help="container 模式全零时 /prefixes/<p>/works 兜底")
    ap.add_argument("--split-years", action="store_true", dest="split_years",
                    help="container 模式逐年分窗遍历")
    ap.add_argument("--years", help='"2026-2027"（direct 模式必填）')
    ap.add_argument("--venue", help="输出文件名 tag（缺省=issn/name slug）")
    ap.add_argument("--limit", type=int, default=0, help="最多条数（冒烟用；0=全量）")
    ap.add_argument("--registry-run", action="store_true",
                    help="按 registry 跑某一族（断点续抓；--family 选族）")
    ap.add_argument("--family", choices=["journal", "container"], default="journal",
                    help="--registry-run 的族（缺省 journal）")
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
            out = out_dir / f"{prefix}_{tag}.jsonl"
            count = write_jsonl(out, entries)
            _log(f"{tag}: {count} 行 -> {out.name} {_year_stats(entries)}")
            if note:
                _log(f"{tag}: {note}")
            return 0 if count or not note else 1
        conf = _conf_for_direct(args.name, args.venue or "", args.registry)
        entries, note, contrib = container_family(
            args.name, args.years,
            variants=(args.variant or conf.get("variants", ())),
            query=args.query or conf.get("query", ""),
            prefix=args.prefix_filter or conf.get("prefix", ""),
            split_years=args.split_years or conf.get("split", False),
            doi_prefix=args.doi_prefix or conf.get("doi_prefix", ""),
            query_by_year=conf.get("query_by_year") or None,
            limit=args.limit)
        tag = args.venue or _slug(args.name)
        out = out_dir / f"crossref_conf_{tag}.jsonl"
        count = write_jsonl(out, entries)
        _log(f"{tag}: {count} 行 -> {out.name} {_year_stats(entries)}")
        for lab, n in contrib[:6]:
            _log(f"{tag}:   {n:6d} <- {lab[:70]}")
        if note:
            _log(f"{tag}: {note}")
        return 0 if count else 1

    from make_registry import load_registry
    src = f"crossref_{args.family}"
    rows = [r for r in load_registry(args.registry) if r["source"] == src]
    if not rows:
        _log(f"registry 无 {src} 行")
        return 2
    ext = "journal" if args.family == "journal" else "conf"
    todo = [r for r in rows
            if args.force or not (out_dir / f"crossref_{ext}_{r['venue']}.jsonl").exists()]
    for r in rows:
        if r not in todo:
            _log(f"{r['venue']}: 已存在 crossref_{ext}_{r['venue']}.jsonl，"
                 f"跳过（断点续抓）")
    summary, failures = [], []
    t0 = time.time()
    for r in todo:
        venue, t1 = r["venue"], time.time()
        try:
            if args.family == "journal":
                entries, used, note = journal_family(
                    r["crossref_issn"], r["years"], limit=args.limit)
                contrib = []
            else:
                conf = VENUE_CONF.get(venue, {})
                entries, note, contrib = container_family(
                    r["crossref_container"], r["years"],
                    variants=conf.get("variants", ()),
                    query=conf.get("query", ""),
                    prefix=conf.get("prefix", ""),
                    split_years=conf.get("split", False),
                    doi_prefix=conf.get("doi_prefix", ""),
                    query_by_year=conf.get("query_by_year") or None,
                    limit=args.limit)
                used = "+".join(lab[:40] for lab, _ in contrib[:2]) or "—"
        except Exception as exc:  # 单 venue 失败不卡死
            failures.append((venue, repr(exc)))
            _log(f"{venue}: 抓取异常 {exc!r}")
            continue
        dt = time.time() - t1
        if not entries:
            failures.append((venue, note or "0 行"))
            _log(f"{venue}: 0 行（{dt:.0f}s）—— {note}")
            continue
        out = out_dir / f"crossref_{ext}_{venue}.jsonl"
        count = write_jsonl(out, entries)
        _log(f"{venue}: {count} 行（{dt:.0f}s）{_year_stats(entries)}")
        for lab, n in contrib:
            _log(f"{venue}:   {n:6d} <- {lab[:70]}")
        if note:
            _log(f"{venue}: {note}")
        summary.append((venue, count, used))
    _log(f"--- 汇总（{len(summary)}/{len(todo)} venues，{time.time() - t0:.0f}s）---")
    for venue, count, used in summary:
        _log(f"  crossref_{ext}_{venue}.jsonl: {count} 行")
    if failures:
        _log("失败/覆盖缺口清单:")
        for venue, why in failures:
            _log(f"  {venue}: {why}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
