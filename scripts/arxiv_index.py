"""Fetch arXiv metadata (title/summary) for every PDF in docs/research/papers.

Writes docs/research/papers_index.md with an id -> title/date table, and prints
which entries look audio / always-on-recording related.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPERS = os.path.join(ROOT, "docs", "research", "papers")

AUDIO_KEYWORDS = [
    "audio", "speech", "voice", "acoustic", "microphone", "microphones",
    "sound", "asr", "whisper", "speaker", "diarization", "wake",
    "listening", "conversation", "wearable", "egocentric", "lifelog",
    "hearing", "noise", "sonic", "vocal", "prosod", "emotion",
]


def arxiv_ids() -> list[str]:
    out = []
    for name in sorted(os.listdir(PAPERS)):
        m = re.match(r"^(\d{4}\.\d{4,5})v\d+\.pdf$", name)
        if m:
            out.append(m.group(1))
    return out


def fetch_batch(ids: list[str]) -> dict[str, dict]:
    url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"id_list": ",".join(ids), "max_results": len(ids)}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "laos-research/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", "replace")

    entries: dict[str, dict] = {}
    for block in raw.split("<entry>")[1:]:
        block = block.split("</entry>")[0]

        def tag(t: str) -> str:
            m = re.search(rf"<{t}>(.*?)</{t}>", block, re.S)
            return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

        aid = tag("id")
        short = aid.rsplit("/", 1)[-1]
        short = re.sub(r"v\d+$", "", short)
        entries[short] = {
            "title": tag("title"),
            "published": tag("published")[:10],
            "summary": tag("summary")[:400],
        }
    return entries


def main() -> int:
    ids = arxiv_ids()
    print(f"found {len(ids)} arXiv ids", file=sys.stderr)
    meta: dict[str, dict] = {}
    for i in range(0, len(ids), 8):
        batch = ids[i : i + 8]
        for attempt in range(3):
            try:
                meta.update(fetch_batch(batch))
                break
            except Exception as exc:  # noqa: BLE001
                print(f"batch {i} attempt {attempt} failed: {exc}", file=sys.stderr)
                time.sleep(8)
        time.sleep(4)

    lines = ["# docs/research/papers 索引\n", f"> 自动生成，共 {len(ids)} 篇。\n"]
    lines.append("| arXiv | 日期 | 标题 |")
    lines.append("|---|---|---|")
    for aid in ids:
        m = meta.get(aid)
        if not m:
            lines.append(f"| {aid} | ? | (元数据获取失败) |")
            continue
        lines.append(f"| [{aid}](https://arxiv.org/abs/{aid}) | {m['published']} | {m['title']} |")

    with open(os.path.join(ROOT, "docs", "research", "papers_index.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n=== AUDIO-RELATED ===")
    for aid in ids:
        m = meta.get(aid)
        if not m:
            continue
        blob = (m["title"] + " " + m["summary"]).lower()
        hits = [k for k in AUDIO_KEYWORDS if re.search(rf"\b{k}", blob)]
        if hits:
            print(f"{aid} [{','.join(hits[:4])}] {m['title']}")

    with open(os.path.join(ROOT, "docs", "research", "papers_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
