#!/usr/bin/env python3
"""按版本拆 CHANGELOG → docs/releases/vX.Y.Z.md（发版内容归档，本地权威源）。

用法：python scripts/gen_release_notes.py
规则：
  - 每版一文件：docs/releases/<tag>.md，头部元信息（日期/对比链/Release 页链）+ 正文
  - v0.36.0 / v0.37.0 正文用 var/release-notes-v0360/0370.md 加长版（Release 页同文）
  - 其余版本正文 = CHANGELOG 该版段落
  - docs/releases/README.md 生成索引（版本倒序，一句定位取正文首个标题行）
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CL = REPO / "CHANGELOG.md"
OUT = REPO / "docs" / "releases"
EXTENDED = {  # Release 页加长版正文（本地留档）
    "v0.36.0": REPO / "docs" / "releases" / "extended" / "v0.36.0.md",
    "v0.37.0": REPO / "docs" / "releases" / "extended" / "v0.37.0.md",
}

VER_RE = re.compile(r"^## \[(v[0-9]+\.[0-9]+\.[0-9]+)\] - (\d{4}-\d{2}-\d{2})\s*$")


def parse_sections(text: str):
    secs, cur = [], None
    for line in text.splitlines():
        m = VER_RE.match(line)
        if m:
            if cur:
                secs.append(cur)
            cur = {"tag": m.group(1), "date": m.group(2), "lines": []}
        elif cur is not None and not line.startswith("## [Unreleased]"):
            cur["lines"].append(line)
    if cur:
        secs.append(cur)
    return secs


SECTION_WORDS = {"added", "changed", "fixed", "removed", "deprecated", "security"}


def first_summary(lines: list[str]) -> str:
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        body = s.lstrip("#").strip()
        if body.lower().rstrip(":：") in SECTION_WORDS:
            continue  # 小节标题（### Added 等）不是定位句
        s = body.lstrip("- ").strip()
        s = re.sub(r"^(?:feat|fix|docs|chore|refactor|test|perf|ci|build)"
                   r"(?:\([^)]*\))?\s*[:：]?\s*", "", s)
        # 取首个粗体锚或冒号前的主语段
        m = re.match(r"\*\*(.+?)\*\*", s) or re.match(r"^(.+?)[：:]", s)
        text = (m.group(1) if m else s).strip().strip("*")
        if text:
            return text[:60]
    return ""


def sort_key(tag: str):
    return tuple(int(x) for x in tag[1:].split("."))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    secs = parse_sections(CL.read_text(encoding="utf-8"))
    tags = sorted((s["tag"] for s in secs), key=sort_key)
    rows = []
    for i, sec in enumerate(sorted(secs, key=lambda s: sort_key(s["tag"]))):
        tag, date = sec["tag"], sec["date"]
        prev = tags[i - 1] if i > 0 else None
        body = EXTENDED[tag].read_text(encoding="utf-8") if tag in EXTENDED \
            else "\n".join(sec["lines"]).strip()
        header = [
            f"# {tag} 发版内容",
            "",
            f"- **版本**：{tag}（{date}）",
            f"- **对比**：[{'v' + prev[1:] if prev else tag}...{tag}]"
            f"(https://github.com/Yfredy/LAOS/compare/{prev + '...' + tag if prev else tag})"
            if prev else f"- **对比**：起点版本",
            f"- **Release 页**：https://github.com/Yfredy/LAOS/releases/tag/{tag}",
            f"- **正文来源**：{'Release 页加长版（docs/releases/extended/ 留档）' if tag in EXTENDED else 'CHANGELOG.md 该版段落'}",
            "",
            "---",
            "",
        ]
        (OUT / f"{tag}.md").write_text("\n".join(header) + body + "\n",
                                       encoding="utf-8")
        rows.append((tag, date, first_summary(sec["lines"])))

    idx = ["# 发版内容归档（docs/releases/）", "",
           "> 每版一文件（`vX.Y.Z.md`）：头部元信息（日期/对比链/Release 页链）+ 详细正文。",
           "> 生成：`python scripts/gen_release_notes.py`（正文源：CHANGELOG.md；加长版正文存 docs/releases/extended/）。",
           "> 本目录随每次发版重新生成对齐（发版纪律扩展：新版本发完即跑本脚本并提交）。",
           "", "| 版本 | 日期 | 一句定位 |", "|---|---|---|"]
    for tag, date, summary in sorted(rows, key=lambda r: sort_key(r[0]), reverse=True):
        idx.append(f"| [{tag}]({tag}.md) | {date} | {summary} |")
    (OUT / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"OK: {len(secs)} versions -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
