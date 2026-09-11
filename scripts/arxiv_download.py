"""Download arXiv PDFs into docs/research/papers/ and extend papers_index.md.

Usage:
    python scripts/arxiv_download.py --ids 2504.02624,2110.07058
    python scripts/arxiv_download.py --from-file docs/research/always-on-recording/academic-papers.md

The --from-file mode parses every `arXiv:<id>` bullet under a heading that
contains "建议归档的论文" (or falls back to the whole file).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, "docs", "research", "papers")
INDEX = os.path.join(ROOT, "docs", "research", "papers_index.md")
UA = {"User-Agent": "laos-research/1.0 (paper archiving)"}

SECTION_HEAD = "建议归档的论文"
ID_RE = re.compile(r"(\d{4}\.\d{4,5})")


def ids_from_file(path: str) -> list[str]:
    text = open(path, encoding="utf-8").read()
    m = re.search(rf"^#+\s*.*{SECTION_HEAD}.*$", text, re.M)
    scope = text[m.end():] if m else text
    out: list[str] = []
    for line in scope.splitlines():
        for aid in ID_RE.findall(line):
            if aid not in out:
                out.append(aid)
    return out


def latest_versions(ids: list[str]) -> dict[str, tuple[str, str]]:
    """id -> (versioned id like '2504.02624v2', title)."""
    meta: dict[str, tuple[str, str]] = {}
    for i in range(0, len(ids), 8):
        batch = ids[i : i + 8]
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"id_list": ",".join(batch), "max_results": len(batch)}
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                    raw = r.read().decode("utf-8", "replace")
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  meta batch {i} attempt {attempt}: {exc}", file=sys.stderr)
                time.sleep(8)
        else:
            continue
        for block in raw.split("<entry>")[1:]:
            block = block.split("</entry>")[0]

            def tag(t: str) -> str:
                m = re.search(rf"<{t}>(.*?)</{t}>", block, re.S)
                return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

            ver = tag("id").rsplit("/", 1)[-1]           # 2504.02624v2
            base = re.sub(r"v\d+$", "", ver)
            meta[base] = (ver, tag("title"))
        time.sleep(4)
    return meta


def download(ver: str) -> bool:
    dest = os.path.join(PAPERS, f"{ver}.pdf")
    if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
        print(f"  skip (exists) {ver}")
        return True
    url = f"https://arxiv.org/pdf/{ver}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            data = r.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAIL {ver}: {exc}", file=sys.stderr)
        return False
    if not data.startswith(b"%PDF"):
        print(f"  FAIL {ver}: not a PDF ({data[:20]!r})", file=sys.stderr)
        return False
    with open(dest, "wb") as fh:
        fh.write(data)
    print(f"  ok {ver} ({len(data) // 1024} KB)")
    return True


def extend_index(rows: list[tuple[str, str, str]]) -> None:
    """rows: (versioned id, title, date-ish)."""
    if not os.path.exists(INDEX):
        return
    text = open(INDEX, encoding="utf-8").read()
    marker = "## Always-on recording（全天候录音）"
    if marker in text:
        text = text.split(marker)[0]
    lines = [
        "",
        marker,
        "",
        f"> {time.strftime('%Y-%m-%d')} 由 `scripts/arxiv_download.py` 归档，共 {len(rows)} 篇。",
        "",
        "| arXiv | 标题 |",
        "|---|---|",
    ]
    for ver, title, _ in rows:
        base = re.sub(r"v\d+$", "", ver)
        lines.append(f"| [{ver}](https://arxiv.org/abs/{base}) | {title} |")
    open(INDEX, "w", encoding="utf-8").write(text.rstrip() + "\n" + "\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--from-file", default="")
    args = ap.parse_args()

    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    if args.from_file:
        ids += ids_from_file(os.path.join(ROOT, args.from_file) if not os.path.isabs(args.from_file) else args.from_file)
    ids = list(dict.fromkeys(ids))
    if not ids:
        print("no ids", file=sys.stderr)
        return 1

    print(f"resolving {len(ids)} ids ...", file=sys.stderr)
    meta = latest_versions(ids)
    missing = [i for i in ids if i not in meta]
    if missing:
        print(f"  metadata missing for: {missing}", file=sys.stderr)

    print("downloading ...", file=sys.stderr)
    rows = []
    for base in ids:
        if base not in meta:
            continue
        ver, title = meta[base]
        if download(ver):
            rows.append((ver, title, ""))
        time.sleep(3)

    extend_index(rows)
    print(f"archived {len(rows)} papers; index updated", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
