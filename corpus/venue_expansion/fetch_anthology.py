#!/usr/bin/env python
"""corpus/venue_expansion/fetch_anthology.py — ACL Anthology NLP 族抓取（Task 2）.

数据源与路径决策：
  1. 首选全库 bib dump：https://aclanthology.org/anthology+abstracts.bib.gz
     先 HEAD 定大小；>500MB 或下载重试耗尽 -> 转分卷路径。
  2. 分卷路径（保险）：按 registry years 窗口逐年枚举候选卷号，逐卷抓
     https://aclanthology.org/volumes/<volume-id>.bib（404 记缺口后继续）。
     老卷号（P/D/N/Q/C + W 系列 CoNLL）只能 best-effort 枚举，缺口如实上报。

所有 HTTP 均带指数退避重试（1s→2s→…→60s，共 8 次；404 不重试）。
dump 缓存于 corpus/venue_expansion/_cache/（gitignore），解压一次反复用。

过滤口径：entry 的 venue 取 booktitle（inproceedings）或 journal（article），
casefold 子串匹配 VENUE_PATTERNS[prefix]，再卡 years 窗口。NAACL 真实
booktitle 写作 "North American Chapter of the Association for Computational
Linguistics"，故用语义短语而非裸缩写；acl 只认 "Annual Meeting…"（避免把
NAACL/COLING 的 "…of the Association for Computational Linguistics" 误收）。
各会议的 Findings 卷按 anthology 归属计入对应 venue。

零第三方依赖（urllib.request/gzip/json/re/time，纯 stdlib）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://aclanthology.org"
DUMP_URL = BASE + "/anthology+abstracts.bib.gz"
DUMP_MAX_BYTES = 500 * 1024 * 1024  # 超过则走分卷路径
RETRY_DELAYS = [1, 2, 4, 8, 16, 32, 60, 60]  # 1s→2s→…→60s ×8
UA = "laos-venue-expansion/0.1 (research corpus; github.com/yaoyue/laos)"
HTTP_TIMEOUT = 300  # 秒（单次 socket 空闲超时，非总时长）

SCHEMA_ORDER = ("title", "year", "venue", "authors", "url", "doi", "abstract")
SCHEMA_KEYS = frozenset(SCHEMA_ORDER)

# 只解析这两类条目（@proceedings/@string/@comment 等一律跳过）
ENTRY_TYPES = {"inproceedings", "article"}

# registry anthology_prefix -> booktitle/journal 的 casefold 子串模式。
# 裸缩写（naacl/coling/conll/tacl）兼容旧式 "Proceedings of NAACL" 写法并
# 顺带覆盖 Findings 卷（"…: EMNLP 2024"）；acl 特殊：禁用裸缩写防误收，
# 另用 "Proceedings of the ACL <year> …" 前缀模式收旧短文/演示/SRW 卷。
VENUE_PATTERNS = {
    "acl": [
        "annual meeting of the association for computational linguistics",
        "findings of the association for computational linguistics: acl",
        "proceedings of the acl",
        "proceedings of acl",
    ],
    "emnlp": ["empirical methods in natural language processing", "emnlp"],
    "naacl": ["north american chapter", "nations of the americas chapter",
              "naacl"],
    "coling": ["international conference on computational linguistics", "coling"],
    "conll": ["computational natural language learning", "conll"],
    "tacl": ["transactions of the association for computational linguistics",
             "tacl"],
}

# prefix -> (排除子串, 豁免子串)：命中排除串则否决，除非命中豁免串。
# acl 的前缀模式会扫到 "Proceedings of the ACL 2012 Joint Workshop on …"
# 这类同场专题 workshop（有独立卷号）；emnlp/naacl/coling 的裸缩写子串会扫到
# "… Workshop on X (at EMNLP/NAACL)" / "… (LREC-COLING 2024)" 同场 workshop。
# 一律排除；SRW 属主会卷族（P10-3、2024.acl-srw 等），豁免。conll 例外：
# CoNLL 1997-2015 本身就叫 "Workshop on Computational Natural Language
# Learning"，不能排除（其实测噪音为 0，未登记）。
VENUE_EXCLUDES = {
    "acl": (["workshop"], ["student research workshop"]),
    "emnlp": (["workshop"], ["student research workshop"]),
    "naacl": (["workshop"], ["student research workshop"]),
    "coling": (["workshop"], ["student research workshop"]),
}


def _log(msg: str) -> None:
    print(f"[fetch_anthology] {msg}", flush=True)


# ---------------------------------------------------------------- 解析（纯函数）

_TYPE_RE = re.compile(r"@([A-Za-z]+)\s*\{")
_FIELD_RE = re.compile(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*")
_WS_RE = re.compile(r"\s+")


def _scan_braced(text: str, start: int) -> int:
    """text[start] == '{'：返回配对 '}' 下标；未闭合返回 -1（find 级扫描）。"""
    depth = 0
    i, n = start, len(text)
    while i < n:
        b = text.find("{", i)
        c = text.find("}", i)
        if c < 0:
            return -1
        if b >= 0 and b < c:
            depth += 1
            i = b + 1
        else:
            depth -= 1
            if depth == 0:
                return c
            i = c + 1
    return -1


def _clean_val(raw: str) -> str:
    return _WS_RE.sub(" ", raw).strip()


def _parse_fields(body: str) -> dict:
    """解析条目体（已剥掉外层大括号与 key），返回已知字段的裸值。"""
    fields: dict[str, str] = {}
    i, n = 0, len(body)
    known = {"title", "author", "booktitle", "journal", "year", "url", "doi",
             "abstract"}
    while i < n:
        while i < n and body[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        m = _FIELD_RE.match(body, i)
        if not m:
            break  # 无法识别的残余——放弃该条剩余部分
        key = m.group(1).casefold()
        i = m.end()
        if i < n and body[i] == "{":
            j = _scan_braced(body, i)
            if j < 0:
                break
            val, i = body[i + 1:j], j + 1
        elif i < n and body[i] == '"':
            j = body.find('"', i + 1)
            if j < 0:
                break
            val, i = body[i + 1:j], j + 1
        else:  # 裸 token（month = jun 等）
            j = i
            while j < n and body[j] not in ",\n":
                j += 1
            val, i = body[i:j], j
        if key in known:
            fields[key] = _clean_val(val)
    return fields


def _make_record(f: dict) -> dict:
    raw_year = f.get("year")
    year = int(raw_year) if raw_year and raw_year.isdigit() else (raw_year or None)
    venue = f.get("booktitle") or f.get("journal") or ""
    author = f.get("author") or ""
    authors = ([a.strip() for a in re.split(r"\s+and\s+", author,
                                            flags=re.IGNORECASE) if a.strip()]
               if author else [])
    return {
        "title": f.get("title") or "",
        "year": year,
        "venue": venue,
        "authors": authors,
        "url": f.get("url") or None,
        "doi": f.get("doi") or None,
        "abstract": f.get("abstract") or None,
    }


def parse_bib_entries(text: str) -> list:
    """bib 全文 -> 条目列表。状态机：@type{ 起，平衡大括号止；噪音跳过。"""
    entries = []
    i, n = 0, len(text)
    while i < n:
        at = text.find("@", i)
        if at < 0:
            break
        m = _TYPE_RE.match(text, at)
        if not m:  # 散文里的 @、email 等
            i = at + 1
            continue
        open_b = m.end() - 1
        close = _scan_braced(text, open_b)
        if close < 0:  # EOF 残缺条目
            break
        if m.group(1).casefold() in ENTRY_TYPES:
            body = text[m.end():close]
            comma = body.find(",")  # 剥 entry key
            fields = _parse_fields(body[comma + 1:]) if comma >= 0 else {}
            entries.append(_make_record(fields))
        i = close + 1
    return entries


def entry_matches(entry: dict, prefix: str, year_lo: int, year_hi: int) -> bool:
    """registry 的 anthology_prefix + years 窗口过滤。

    匹配前剥掉大小写保护花括号（真实 dump 里旧卷 booktitle 写作
    "North {A}merican Chapter" / "Empirical {M}ethods ..."），只影响
    匹配，不改动存储的 venue 原文。"""
    y = entry.get("year")
    if not isinstance(y, int) or not (year_lo <= y <= year_hi):
        return False
    patterns = VENUE_PATTERNS.get(prefix)
    if not patterns:
        return False
    hay = re.sub(r"[{}]", "", entry.get("venue") or "").casefold()
    if not any(p in hay for p in patterns):
        return False
    excludes, exempts = VENUE_EXCLUDES.get(prefix, ([], []))
    if any(x in hay for x in excludes) and not any(x in hay for x in exempts):
        return False
    return True


def write_jsonl(path, entries: list) -> int:
    """逐条 json.dumps(ensure_ascii=False) 写行，返回条数。

    原子落盘（final-review 必修 1）：先写同目录 <name>.part，写完
    os.replace 原子顶替——中途被杀（TUN 断窗实测发生 2 次）只会留下
    .part 残件被下轮覆盖，不会把半截产物固化成"已存在即跳过"的正式
    文件污染断点续抓；Python 层异常时 .part 即时清理，旧正式产物原样。
    追加转义 U+2028/U+2029/U+0085：json.dumps(ensure_ascii=False) 会把这
    三个 Unicode 行分隔符原样留在串里（JSON 合法，ASCII 控制符则会被 dumps
    转义），但读方 str.splitlines() 会在此断行，逐行 json.loads 即崩
    （Task 4 fix round 1：crossref_conf_ijcai 的 ScaleFormer 条目实测内嵌
    原始 U+2028）。转义成 \\u2028 既保 JSON 值不变又免断行。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    part = p.with_name(p.name + ".part")
    count = 0
    try:
        with part.open("w", encoding="utf-8", newline="\n") as fh:
            for e in entries:
                s = json.dumps(e, ensure_ascii=False)
                s = (s.replace("\u2028", "\\u2028")
                      .replace("\u2029", "\\u2029")
                      .replace("\x85", "\\u0085"))
                fh.write(s + "\n")
                count += 1
        part.replace(p)  # = os.replace：同目录原子顶替
    except BaseException:
        part.unlink(missing_ok=True)  # 半截 .part 不留，正式产物未被触碰
        raise
    return count


# ---------------------------------------------------------------- 网络（带退避）

class DumpUnavailable(Exception):
    """全库 dump 拿不到（超限/下载重试耗尽）——调用方转分卷路径。"""


def _open(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=HTTP_TIMEOUT)


def http_get_bytes(url: str) -> bytes:
    """GET 全量读回；指数退避重试 RETRY_DELAYS 次；404/403 不重试。"""
    last = None
    for attempt in range(len(RETRY_DELAYS) + 1):  # 首试 + 8 重试
        try:
            with _open(url) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                raise  # 永久失败，重试无意义
            last = exc
        except Exception as exc:  # TUN 断窗 / 超时 / reset
            last = exc
        if attempt >= len(RETRY_DELAYS):
            break
        delay = RETRY_DELAYS[attempt]
        _log(f"GET {url} 第 {attempt + 1} 次失败（{last!r}），{delay}s 后重试")
        time.sleep(delay)
    raise RuntimeError(f"GET {url} 重试耗尽: {last!r}")


def http_head_length(url: str):
    """HEAD Content-Length；拿不到（405/无头字段）返回 None，不致命。"""
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            with _open(url, method="HEAD") as resp:
                return int(resp.headers.get("Content-Length") or 0) or None
        except Exception as exc:
            if attempt >= len(RETRY_DELAYS):
                _log(f"HEAD {url} 失败（{exc!r}），跳过大小检查直接试下载")
                return None
            time.sleep(RETRY_DELAYS[attempt])
    return None


def ensure_dump(cache_dir: Path) -> Path:
    """确保本地有解压后的全库 bib，返回其路径。失败抛 DumpUnavailable。"""
    gz = cache_dir / "anthology+abstracts.bib.gz"
    bib = cache_dir / "anthology+abstracts.bib"
    if bib.exists() and bib.stat().st_size > 0:
        return bib
    cache_dir.mkdir(parents=True, exist_ok=True)
    if not (gz.exists() and gz.stat().st_size > 0):
        size = http_head_length(DUMP_URL)
        if size is not None:
            _log(f"dump HEAD Content-Length: {size / 1e6:.1f} MB")
            if size > DUMP_MAX_BYTES:
                raise DumpUnavailable(f"dump {size / 1e6:.0f}MB > 500MB")
        try:
            data = http_get_bytes(DUMP_URL)
        except RuntimeError as exc:
            raise DumpUnavailable(str(exc))
        gz.write_bytes(data)
        _log(f"dump 下载完成: {len(data) / 1e6:.1f} MB -> {gz.name}")
    part = bib.with_suffix(".bib.part")
    with gzip.open(gz, "rb") as src, open(part, "wb") as dst:
        shutil.copyfileobj(src, dst, 1 << 22)  # 4MB 块，内存有界
    part.replace(bib)
    _log(f"dump 解压完成: {bib.stat().st_size / 1e6:.1f} MB -> {bib.name}")
    return bib


# ---------------------------------------------------------------- 分卷路径（保险）

def _volume_ids(prefix: str, year: int) -> list:
    """(prefix, year) 的候选卷号（best-effort 枚举，404 由调用方容忍）。"""
    yy = f"{year % 100:02d}"
    newschool = year >= 2020
    if prefix == "acl":
        return ([f"{year}.acl-main", f"{year}.acl-short", f"{year}.findings-acl"]
                if newschool else [f"P{yy}-{k}" for k in (1, 2, 3)])
    if prefix == "emnlp":
        return ([f"{year}.emnlp-main", f"{year}.findings-emnlp"]
                if newschool else [f"D{yy}-{k}" for k in (1, 2)])
    if prefix == "naacl":
        # 2020 无 NAACL；2016-2019 为 N16.. 形式
        return ([f"{year}.naacl-1", f"{year}.findings-naacl"]
                if year >= 2021 else [f"N{yy}-{k}" for k in (1, 2, 3)])
    if prefix == "coling":
        return ([f"{year}.coling-1"] if year in (2018, 2022, 2023, 2024, 2025)
                else ([f"C{yy}-1"] if year == 2016 else []))
    if prefix == "conll":
        # 2018 前卷号在 W 系列（slug 不可枚举）——只试新式
        return [f"{year}.conll-1", f"{year}.conll-sharedtask"] if year >= 2018 else []
    if prefix == "tacl":
        return [f"{year}.tacl-1"] + ([f"Q{yy}-1"] if year < 2017 else [])
    return []


def fetch_venue_volumes(prefix: str, year_lo: int, year_hi: int) -> tuple:
    """分卷抓取：返回 (entries, 缺口说明列表)。404 记缺口继续。"""
    entries, gaps = [], []
    for year in range(year_lo, year_hi + 1):
        ids = _volume_ids(prefix, year)
        if not ids:
            gaps.append(f"{prefix}@{year}: 无候选卷号（老 W 系列不可枚举）")
            continue
        got_any = False
        for vid in ids:
            url = f"{BASE}/volumes/{vid}.bib"
            try:
                text = http_get_bytes(url).decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                gaps.append(f"{vid}: HTTP {exc.code}")
                continue
            except RuntimeError as exc:
                gaps.append(f"{vid}: {exc}")
                continue
            parsed = parse_bib_entries(text)
            keep = [e for e in parsed if entry_matches(e, prefix, year_lo, year_hi)]
            entries.extend(keep)
            got_any = True
            _log(f"  卷 {vid}: {len(keep)} 条")
        if not got_any and not any(g.startswith(f"{prefix}@{year}") for g in gaps):
            gaps.append(f"{prefix}@{year}: 全部候选卷 404")
    return entries, gaps


# ---------------------------------------------------------------- CLI 主流程

def parse_years(spec: str) -> tuple:
    """"2010-2025" / "2027" -> (lo, hi)。"""
    spec = spec.strip()
    m = re.fullmatch(r"(\d{4})(?:-(\d{4}))?", spec)
    if not m:
        raise ValueError(f"bad years spec: {spec!r}")
    lo = int(m.group(1))
    return lo, int(m.group(2) or lo)


def _year_stats(entries: list) -> str:
    years = [e["year"] for e in entries if isinstance(e.get("year"), int)]
    if not years:
        return "无年份"
    per = {}
    for y in years:
        per[y] = per.get(y, 0) + 1
    span = f"{min(years)}..{max(years)}"
    top = ", ".join(f"{y}:{per[y]}" for y in sorted(per))
    return f"year {span} ({top})"


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="ACL Anthology NLP 族抓取（registry source=anthology 行）")
    ap.add_argument("--venue", action="append",
                    help="registry venue 名（可重复；缺省=全部 6 行）")
    ap.add_argument("--limit", type=int, default=0,
                    help="每 venue 最多条数（冒烟用；0=全量）")
    ap.add_argument("--registry", default=str(HERE / "venues.csv"))
    ap.add_argument("--out-dir", default=str(HERE))
    ap.add_argument("--force", action="store_true",
                    help="输出已存在也重抓（缺省跳过=断点续抓）")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(HERE))
    from make_registry import load_registry
    rows = [r for r in load_registry(args.registry) if r["source"] == "anthology"]
    if args.venue:
        want = {v.casefold() for v in args.venue}
        rows = [r for r in rows if r["venue"].casefold() in want]
        missing = want - {r["venue"].casefold() for r in rows}
        if missing:
            _log(f"registry 无此 venue: {sorted(missing)}")
            return 2
    if not rows:
        _log("registry 无 anthology 行")
        return 2

    out_dir = Path(args.out_dir)
    todo = [r for r in rows
            if args.force or not (out_dir / f"anthology_{r['venue']}.jsonl").exists()]
    for r in rows:
        if r not in todo:
            _log(f"{r['venue']}: 已存在 anthology_{r['venue']}.jsonl，跳过（断点续抓）")
    if not todo:
        _log("全部输出文件均已存在，无事可做")
        return 0

    cache = out_dir / "_cache"
    dump_path, all_entries = None, []
    try:
        dump_path = ensure_dump(cache)
    except DumpUnavailable as exc:
        _log(f"全库 dump 不可用（{exc}）-> 分卷路径")
    if dump_path is not None:
        _log(f"解析全库 dump（一次性，多 venue 复用）…")
        all_entries = parse_bib_entries(
            dump_path.read_text(encoding="utf-8", errors="replace"))
        _log(f"全库共 {len(all_entries)} 条 inproceedings/article")

    summary, failures = [], []
    for r in todo:
        venue = r["venue"]
        prefix = r["anthology_prefix"].strip()
        lo, hi = parse_years(r["years"])
        out = out_dir / f"anthology_{venue}.jsonl"
        if dump_path is not None:
            entries = [e for e in all_entries
                       if entry_matches(e, prefix, lo, hi)]
            src, gaps = "dump", []
        else:
            entries, gaps = fetch_venue_volumes(prefix, lo, hi)
            src = "分卷"
        if args.limit:
            entries = entries[:args.limit]
        try:
            count = write_jsonl(out, entries)
        except OSError as exc:
            failures.append(f"{venue}: 写出失败 {exc!r}")
            continue
        _log(f"{venue}: {count} 行 [{src}] {_year_stats(entries)}")
        summary.append((venue, count, src))
        for g in gaps:
            _log(f"{venue} 分卷缺口: {g}")

    _log("--- 汇总 ---")
    for venue, count, src in summary:
        _log(f"  anthology_{venue}.jsonl: {count} 行 [{src}]")
    if failures:
        _log("失败清单:")
        for f in failures:
            _log(f"  {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
