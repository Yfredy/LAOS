# -*- coding: utf-8 -*-
"""把综述 Markdown 正文转为单文件 HTML 阅读版（纯 stdlib，无外链）。

只处理本综述实际用到的语法：
  - `#` / `##` / `###` / `####` 标题（生成 id 锚点与 TOC）
  - 段落（连续非空行合并）
  - `- ` 无序列表 / `N. ` 有序列表（支持缩进续行）
  - 管道表格（首行为表头，第二行为分隔行）
  - `> ` 引用块
  - `---` 分隔线
  - 行内：`**粗体**`、`` `代码` ``、`[文字](链接)`、`[Sxx]` 文献编号
脱离本文件未覆盖的语法一律按纯文本转义输出，绝不静默丢弃内容。

用法：
    python scripts/md2html_survey.py <input.md> <output.html> [--title 标题]
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

CSS = """
  :root{
    --bg:#0e1117; --panel:#161b22; --panel2:#1c2230; --border:#30363d;
    --text:#c9d1d9; --muted:#8b949e; --accent:#58a6ff; --accent2:#3fb950;
    --warn:#f0883e; --bad:#f85149; --good:#3fb950; --chip:#21262d;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;
    line-height:1.75;font-size:15px}
  .wrap{max-width:1180px;margin:0 auto;padding:0 20px 80px}
  header{padding:30px 0 20px;border-bottom:1px solid var(--border);margin-bottom:8px}
  header h1{margin:0 0 8px;font-size:24px;color:#fff;line-height:1.4}
  header .meta{color:var(--muted);font-size:13px}
  nav.toc{background:var(--panel);border:1px solid var(--border);border-radius:8px;
    padding:14px 18px;margin:22px 0 30px}
  nav.toc strong{display:block;color:#fff;margin-bottom:8px;font-size:14px}
  nav.toc ol{margin:0;padding-left:22px}
  nav.toc li{margin:3px 0}
  nav.toc a{color:var(--accent);text-decoration:none}
  nav.toc a:hover{text-decoration:underline}
  h2{font-size:20px;color:#fff;margin:38px 0 14px;padding-bottom:8px;
    border-bottom:1px solid var(--border)}
  h3{font-size:16.5px;color:#e6edf3;margin:26px 0 10px}
  h4{font-size:15px;color:var(--accent2);margin:20px 0 8px}
  p{margin:10px 0}
  ul,ol{margin:10px 0;padding-left:26px}
  li{margin:5px 0}
  blockquote{margin:14px 0;padding:10px 16px;background:var(--panel2);
    border-left:3px solid var(--accent);color:var(--muted);border-radius:0 6px 6px 0}
  blockquote p{margin:4px 0}
  hr{border:0;border-top:1px solid var(--border);margin:30px 0}
  code{background:var(--chip);padding:1px 6px;border-radius:4px;
    font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;font-size:13px;
    color:#ffd580}
  strong{color:#fff}
  a{color:var(--accent)}
  .cite{display:inline-block;background:var(--chip);color:var(--accent);
    border:1px solid var(--border);border-radius:4px;padding:0 5px;
    font-size:12px;line-height:1.6;white-space:nowrap}
  .tblwrap{overflow-x:auto;margin:16px 0;border:1px solid var(--border);border-radius:8px}
  table{border-collapse:collapse;width:100%;font-size:13.5px;background:var(--panel)}
  th,td{border:1px solid var(--border);padding:8px 11px;text-align:left;vertical-align:top}
  th{background:var(--panel2);color:#fff;font-weight:600;position:sticky;top:0}
  tbody tr:nth-child(even){background:#131922}
  footer{margin-top:50px;padding-top:16px;border-top:1px solid var(--border);
    color:var(--muted);font-size:12.5px}
  @media print{body{background:#fff;color:#000}nav.toc{display:none}}
"""

CITE_RE = re.compile(r"\[S\d{1,3}\]")


def slugify(text: str, used: set[str]) -> str:
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.strip()).strip("-").lower()
    base = base or "sec"
    sid = base
    n = 2
    while sid in used:
        sid = f"{base}-{n}"
        n += 1
    used.add(sid)
    return sid


def inline(text: str) -> str:
    """行内语法。先转义，再按 code → bold → link 顺序还原（code 优先，避免嵌套替换）。"""
    out = html.escape(text, quote=False)
    # 行内代码先占位，防止其内部内容被后续规则改写
    codes: list[str] = []

    def _code(m: re.Match[str]) -> str:
        codes.append(m.group(1))
        return f"\x00CODE{len(codes) - 1}\x00"

    out = re.sub(r"`([^`]+)`", _code, out)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
                 r'<a href="\2" target="_blank" rel="noopener">\1</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = CITE_RE.sub(lambda m: f'<span class="cite">{m.group(0)}</span>', out)
    for i, c in enumerate(codes):
        out = out.replace(f"\x00CODE{i}\x00", f"<code>{c}</code>")
    return out


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_table_sep(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and bool(re.fullmatch(r"\|[\s:|-]+\|", s))


def render_table(rows: list[list[str]]) -> str:
    head, body = rows[0], rows[1:]
    th = "".join(f"<th>{inline(c)}</th>" for c in head)
    trs = []
    for r in body:
        tds = "".join(f"<td>{inline(c)}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return ('<div class="tblwrap"><table><thead><tr>'
            f"{th}</tr></thead><tbody>{''.join(trs)}</tbody></table></div>")


def convert(md_text: str, title: str) -> tuple[str, list[tuple[str, str, int]]]:
    lines = md_text.splitlines()
    used: set[str] = set()
    toc: list[tuple[str, str, int]] = []  # (id, text, level)
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        s = line.strip()

        if not s:
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"-{3,}", s):
            out.append("<hr>")
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            text = m.group(2).strip()
            sid = slugify(text, used)
            toc.append((sid, text, lvl))
            out.append(f'<h{lvl} id="{sid}">{inline(text)}</h{lvl}>')
            i += 1
            continue

        # 引用块
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            inner = "".join(f"<p>{inline(t)}</p>" for t in buf if t)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # 表格
        if s.startswith("|") and i + 1 < n and is_table_sep(lines[i + 1]):
            rows = [split_row(s)]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(rows))
            continue

        # 列表
        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
            ordered = bool(re.match(r"^\d+\.\s+", s))
            items: list[str] = []
            while i < n:
                cur = lines[i].strip()
                mo = re.match(r"^\d+\.\s+(.*)$", cur)
                mu = re.match(r"^[-*]\s+(.*)$", cur)
                if mo and ordered:
                    items.append(mo.group(1))
                    i += 1
                elif mu and not ordered:
                    items.append(mu.group(1))
                    i += 1
                elif cur and not re.match(r"^[-*]\s+", cur) and not re.match(r"^\d+\.\s+", cur) \
                        and items and lines[i].startswith((" ", "\t")):
                    # 缩进续行：并入上一项
                    items[-1] += " " + cur
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            body = "".join(f"<li>{inline(it)}</li>" for it in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        # 段落（连续非空、非以上语法的行）
        buf = []
        while i < n:
            cur = lines[i].strip()
            if not cur:
                break
            if re.fullmatch(r"-{3,}", cur) or cur.startswith("|") or cur.startswith(">") \
                    or re.match(r"^#{1,4}\s+", cur) \
                    or re.match(r"^[-*]\s+", cur) or re.match(r"^\d+\.\s+", cur):
                break
            buf.append(cur)
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")

    toc_html = []
    for sid, text, lvl in toc:
        if lvl == 2:
            toc_html.append(f'<li><a href="#{sid}">{html.escape(text)}</a></li>')
    body = "\n".join(out)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>{html.escape(title)}</h1>
  <div class="meta">nanoLAOS · laos 音频智能体技术综述 v2（2026-10-18）· 91 篇文献 S01–S91</div>
</header>
<nav class="toc"><strong>目录</strong><ol>
{chr(10).join(toc_html)}
</ol></nav>
<main>
{body}
</main>
<footer>
  由 <code>scripts/md2html_survey.py</code> 从 <code>docs/research/2026-10-18-audio-agentos-survey.md</code>
  生成；单文件、内联样式、无外链依赖。证据附录见同目录
  <code>2026-10-18-audio-agentos-survey-evidence.md</code>。
</footer>
</div>
</body>
</html>
"""
    return doc, toc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="综述 Markdown → 单文件 HTML")
    ap.add_argument("src", type=pathlib.Path)
    ap.add_argument("dst", type=pathlib.Path)
    ap.add_argument("--title", default="音频智能体技术综述 v2")
    args = ap.parse_args(argv)

    text = args.src.read_text(encoding="utf-8")
    doc, toc = convert(text, args.title)
    args.dst.write_text(doc, encoding="utf-8")
    print(f"ok  {args.dst}  ({len(doc)} bytes, {len(toc)} headings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
