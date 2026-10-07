#!/usr/bin/env python
"""scripts/query_corpus.py — venue_expansion 语料通用查询（Task 2 复用基础设施）。

对 corpus/venue_expansion/*.jsonl 全部（35 个 venue 抓取产物（注册表 38
venue 的落库文件，其中 5 个 0 行占位）+ laos_relevant[_strong].jsonl
2 个派生，行 schema {title,year,venue,authors,url,doi,abstract,
laos_topic?,strong?,strong_terms?}）做只读过滤检索，供 Task 3/4 窄分支
对照与定向检索复用。不写任何文件（--json 输出到 stdout）。

用法：
  python scripts/query_corpus.py --topic agent-os --strong-only
  python scripts/query_corpus.py --grep "barge|interrupt" --strong-only --json
  python scripts/query_corpus.py --venue interspeech --year 2023-2025 --limit 0

语义：
  --topic       过滤 laos_topic 字段（agent-os|audio-speech|spatial-privacy）
  --strong-only 只保留 strong==true 行（raw 文件与 laos_relevant.jsonl 无
                strong 字段，故实际等价于在 laos_relevant_strong 上检索）
  --venue       按 venue 字段内容 casefold 包含匹配（--venue NAACL 命中
                "Findings of ...: NAACL 2024"，文件名前缀如
                crossref_conf_neurips 不参与匹配）
  --year        A 或 A-B，区间含两端
  --grep        对 title+abstract 正则、大小写不敏感
  --limit       截断条数，默认 50，0=不限
  --json        每行一个 JSON（默认人读表格：year/venue/title 截 80 列，
                行情数摘要走 stderr，保证 stdout 可安全管道）

query(opts) 可 import 复用（返回 list[dict]，行序 = sorted 文件名 × 行序，
不做跨文件去重——注意 raw 文件与 laos_relevant*.jsonl 有子集关系，不带
--strong-only 时同一条可能命中多次）。写行沿用 fetch_anthology.write_jsonl
纪律：U+2028/U+2029/U+0085 转义成 \\u2028 形（值不变，splitlines 读者不断行）。
零第三方依赖（argparse/json/re/sys/pathlib，纯 stdlib）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "corpus" / "venue_expansion"

TOPICS = ("agent-os", "audio-speech", "spatial-privacy")
DEFAULT_LIMIT = 50
TABLE_WIDTH = 80

# write_jsonl 纪律：这三个 Unicode 行分隔符在 json.dumps(ensure_ascii=False)
# 下会原样留在串里，读者 str.splitlines() 会断行——输出前转义成 \u2028 形。
_LS_SEP = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\u0085": "\\u0085"}


def _escape_line_seps(text: str) -> str:
    for ch, esc in _LS_SEP.items():
        text = text.replace(ch, esc)
    return text


def parse_year(spec: str) -> tuple[int, int]:
    """"A" -> (A, A)；"A-B" -> (A, B)。区间含端点；非法即 ValueError。"""
    m = re.fullmatch(r"(\d{4})(?:-(\d{4}))?", spec.strip())
    if not m:
        raise ValueError(f"bad --year spec: {spec!r} (want A or A-B, 4-digit)")
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:
        raise ValueError(f"bad --year spec: {spec!r} (upper < lower)")
    return lo, hi


def iter_rows(root: Path):
    """sorted(glob *.jsonl) × 行序逐条 yield dict；空行跳过。"""
    for path in sorted(root.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def query(opts, root: Path | str | None = None) -> list[dict]:
    """过滤链 topic → strong → venue → year → grep → limit，返回 list[dict]。

    opts 只需携带 topic/strong_only/venue/year/grep/limit 属性
    （argparse.Namespace 即可）；root 缺省真实语料目录，测试注入 tmp 目录。
    """
    if root is None:
        root = CORPUS_DIR
    rows = iter_rows(Path(root))

    topic = getattr(opts, "topic", None)
    if topic:
        rows = (r for r in rows if r.get("laos_topic") == topic)

    if getattr(opts, "strong_only", False):
        rows = (r for r in rows if r.get("strong") is True)

    venue = getattr(opts, "venue", None)
    if venue:
        needle = venue.casefold()
        rows = (r for r in rows if needle in (r.get("venue") or "").casefold())

    year_spec = getattr(opts, "year", None)
    if year_spec:
        lo, hi = parse_year(year_spec)
        rows = (r for r in rows
                if isinstance(r.get("year"), int) and lo <= r["year"] <= hi)

    grep = getattr(opts, "grep", None)
    if grep:
        rx = re.compile(grep, re.IGNORECASE)
        rows = (r for r in rows
                if rx.search((r.get("title") or "")
                             + " " + (r.get("abstract") or "")))

    rows = list(rows)

    limit = getattr(opts, "limit", DEFAULT_LIMIT)
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def render_row(r: dict) -> str:
    """人读一行：year(4) + venue(32) + title，整行截 80 列。"""
    year = str(r.get("year") or "?")
    venue = (r.get("venue") or "?").strip() or "?"
    title = (r.get("title") or "?").strip() or "?"
    line = f"{year:<4} {venue:<32.32} {title}"
    if len(line) > TABLE_WIDTH:
        line = line[: TABLE_WIDTH - 1] + "…"
    return line


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="只读查询 corpus/venue_expansion/*.jsonl（--json 每行一个 JSON）")
    p.add_argument("--topic", choices=TOPICS,
                   help="过滤 laos_topic 字段")
    p.add_argument("--strong-only", action="store_true", dest="strong_only",
                   help="只保留 strong==true 行")
    p.add_argument("--venue", metavar="PREFIX",
                   help="venue 字段内容 casefold 包含匹配（如 --venue NAACL）")
    p.add_argument("--year", metavar="A[-B]",
                   help="年份过滤，A 或区间 A-B（含端点）")
    p.add_argument("--grep", metavar="PATTERN",
                   help="对 title+abstract 正则匹配，大小写不敏感")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, metavar="N",
                   help=f"截断条数（默认 {DEFAULT_LIMIT}，0=不限）")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="每行一个 JSON（默认人读表格）")
    return p


def main(argv=None, root: Path | str | None = None) -> int:
    parser = build_parser()
    try:
        ns = parser.parse_args(argv)

        if ns.limit < 0:
            parser.error(f"--limit must be >= 0 (got {ns.limit})")
        if ns.year:
            try:
                parse_year(ns.year)
            except ValueError as e:
                parser.error(str(e))
        if ns.grep:
            try:
                re.compile(ns.grep)
            except re.error as e:
                parser.error(f"invalid --grep pattern: {e}")
    except SystemExit as e:  # argparse 用法错误 -> exit code（脚本态等价 sys.exit(2)）
        return int(e.code or 0)

    rows = query(ns, root=root)

    if ns.as_json:
        for r in rows:
            print(_escape_line_seps(json.dumps(r, ensure_ascii=False)))
    else:
        for r in rows:
            print(render_row(r))
    print(f"[query_corpus] {len(rows)} hit(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
