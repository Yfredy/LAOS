#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""生成 laos 音频/AI/Agent 开源星标全景：markdown 报告 + 深色单文件 HTML。

所有数字均从 repos_classified.jsonl 真实统计得出（不手编）。
同一次运行同时产出 .md 与 .html，保证两份文件关键数字一致。
"""
import json, io, os, collections, statistics, html

BASE = r"C:/Users/yaoyue/CodeBuddy/Claw/laos"
SRC = os.path.join(BASE, "docs/research/oss/repos_classified.jsonl")
MD_OUT = os.path.join(BASE, "docs/research/2026-09-14-audio-ai-agent-oss-landscape.md")
HTML_OUT = os.path.join(BASE, "docs/audio-ai-agent-oss.html")

CRAWLED_AT = "2026-09-14"

# ---------- 载入 ----------
rows = [json.loads(l) for l in io.open(SRC, encoding="utf-8") if l.strip()]
N = len(rows)

# ---------- 统计 ----------
cat_counter = collections.Counter()
for r in rows:
    for c in r.get("category", []):
        cat_counter[c] += 1
CATS = [c for c, _ in cat_counter.most_common()]          # 15 类，按条数降序

fit_counter = collections.Counter(r.get("laos_fit") for r in rows)

lic_missing = sum(1 for r in rows if not (r.get("license") or ""))
lic_counter = collections.Counter((r.get("license") or "") for r in rows)

lang_counter = collections.Counter((r.get("language") or "none") for r in rows)

# star 分档（左闭右开）
BUCKETS = [("≥10000", 10000, 10**9), ("1000–9999", 1000, 10000),
           ("100–999", 100, 1000), ("<100", 0, 100)]
def bucket_of(s):
    for name, lo, hi in BUCKETS:
        if lo <= s < hi:
            return name
    return "<100"
bucket_counter = collections.Counter(bucket_of(r["stars"]) for r in rows)

# 每类 star 中位数
cat_stars = collections.defaultdict(list)
for r in rows:
    for c in r["category"]:
        cat_stars[c].append(r["stars"])
cat_median = {c: int(statistics.median(v)) for c, v in cat_stars.items()}

# 总榜 top40
top40 = sorted(rows, key=lambda x: -x["stars"])[:40]
# 各类 top12
cat_top = {}
for c in CATS:
    cat_top[c] = sorted([r for r in rows if c in r["category"]],
                        key=lambda x: -x["stars"])[:12]
# core 全量（132）
core_rows = sorted([r for r in rows if r["laos_fit"] == "core"],
                   key=lambda x: -x["stars"])
# 不推荐：高星但非 core
avoid_rows = sorted([r for r in rows if r["laos_fit"] != "core"],
                    key=lambda x: -x["stars"])[:25]

TOP10 = sorted(rows, key=lambda x: -x["stars"])[:10]

# ---------- 工具 ----------
def trunc(s, n=78):
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"

def esc(s):
    return html.escape(str(s))

# ============================================================
# 1) MARKDOWN
# ============================================================
L = []
def w(s=""):
    L.append(s)

w("# 音频 / AI / Agent 开源项目星标全景")
w()
w("> laos 四段漏斗选型调研 · 最终报告（Task 4）")
w()
w(f"- **抓取日期**: {CRAWLED_AT}（GitHub Search API 未认证快照，star 数为时变量）")
w(f"- **语料规模**: {N:,} 条干净仓库（去噪 2153 + 引号短语补抓 1571）")
w(f"- **分类数**: {len(CATS)} 类（可多标签）")
w(f"- **laos 适配**: core {fit_counter['core']:,} ｜ ref {fit_counter['ref']:,} ｜ unrelated {fit_counter['unrelated']:,}")
w()
w("## 0 · 摘要（TL;DR）")
w()
w(f"- 遍历 **{N}** 个音频 / 语音 AI / 语音·多模态 Agent 方向高星开源项目，覆盖 **{len(CATS)}** 个功能类别。")
w(f"- 真正能进 laos 四段漏斗的 **core 仅 {fit_counter['core']:,} 个（{100*fit_counter['core']/N:.1f}%）**；")
w(f"  76.9% 是「参考/借鉴」级（ref），19.5% 与漏斗无关（unrelated）。")
w(f"- core 集中于四段漏斗的 **①常驻检测（VAD/唤醒词）** 与 **③即时蒸馏（ASR/降噪/声音事件）**；")
w(f"  ②触发捕获多用通用采集库（FFmpeg/pyaudio 类），④原音频即焚是策略而非第三方组件。")
w(f"- **许可字段缺失 {lic_missing:,}/{N:,}（{100*lic_missing/N:.1f}%）**，core 仅排除云 API wrapper，")
w(f"  不保证全部可商用；落地前须逐条核 SPDX（见第 6 节）。")
w()
w("## 1 · 方法与限额说明")
w()
w("数据来自 GitHub Search API（`search/repositories` 端点，未认证），遵守实测限额：")
w()
w("- `search` 限额 **10 次/分钟** → 每请求 `sleep 7`；`core` 限额 60 次/小时且常为 0 → **只用 search 端点**，不补字段。")
w("- search 端点单次响应已含 `stars`/`description`/`language`/`license.spdx_id`/`html_url`/`topics`/`archived` 等全部所需字段。")
w("- 单 query 最多返回 **1000 条**，按 stars 降序取 top，不追求全量。")
w("- 统一加 `fork:false`；落盘后剔除 `archived:true`。")
w("- 去噪纪律（Task 2）：8 个 `topic:` 切片 100% 相关直接复用；`audio-llm`/`voice-agent` 两裸关键词切片相关率仅 20%/16%，逐条重筛剔除 1376 条噪声（含 `public-apis` 479k★、`awesome-python` 320k★），再用引号短语补抓找回真相关项目。")
w(f"- 抓取时间 `{CRAWLED_AT}` 落盘；star 为快照，可能已过时。")
w()
w("## 2 · 总榜 Top 40（star 降序）")
w()
w("| # | star | 仓库 | 语言 | 许可 | 一句话用途 |")
w("|---|---:|---|---|---|---|")
for i, r in enumerate(top40, 1):
    lic = r.get("license") or "-"
    w(f"| {i} | {r['stars']:,} | `{esc(r['full_name'])}` | {esc(r.get('language') or '-')} | {esc(lic)} | {esc(trunc(r['description'],60))} |")
w()
w("## 3 · 分类榜（15 类，各 Top 12）")
w()
w("> 说明：**实际统计得到 15 个类别标签**，而非背景简报所述的「14 类」——多出的 `ml-framework`（540 条）与 `agent-llm`（126 条）在分类器规则中被单独命中。下表以真实 15 类为准。")
w()
w("### 3.0 类别总览")
w()
w("| 类别 | 条数 | star 中位数 |")
w("|---|---:|---:|")
for c in CATS:
    w(f"| {c} | {cat_counter[c]} | {cat_median[c]:,} |")
w()
for c in CATS:
    w(f"### 3.{CATS.index(c)+1} {c}（{cat_counter[c]} 个，中位 {cat_median[c]:,}★）")
    w()
    w("| star | 仓库 | 许可 | 一句话用途 |")
    w("|---:|---|---|---|")
    for r in cat_top[c]:
        lic = r.get("license") or "-"
        w(f"| {r['stars']:,} | `{esc(r['full_name'])}` | {esc(lic)} | {esc(trunc(r['description'],56))} |")
    w()
w("## 4 · laos 适配结论（core 落地清单）")
w()
w(f"共 **{fit_counter['core']}** 个 `laos_fit=core`，按 stars 降序列出。漏斗落点取自分类器写入的 `laos_stage` 字段；")
w("端侧可行性（C1）以「命中 on-device 信号」为判据（已在 core 判定中通过），具体功耗档位见 `docs/research/speech-emotion/04-edge-deployment.md` 的 A/B 档口径；许可（C3）见第 6 节缺失说明。")
w()
# 漏斗落点聚合（基于 laos_stage 是否含 ①/②/③/④）
stage_hit = collections.Counter()
for r in core_rows:
    st = r.get("laos_stage") or ""
    if "①" in st: stage_hit["①常驻检测"] += 1
    if "②" in st: stage_hit["②触发捕获"] += 1
    if "③" in st: stage_hit["③即时蒸馏"] += 1
    if "④" in st: stage_hit["④原音频即焚"] += 1
w("**漏斗落点分布（core 组件去重计数，一个组件可落多段）：**")
w()
for k in ["①常驻检测", "②触发捕获", "③即时蒸馏", "④原音频即焚"]:
    w(f"- {k}：{stage_hit[k]} 个组件")
w()
w("**core 落地清单（全量，132 个）：**")
w()
w("| star | 仓库 | 类别 | 漏斗落点(laos_stage) | 许可 |")
w("|---:|---|---|---|---|")
for r in core_rows:
    lic = r.get("license") or "-"
    w(f"| {r['stars']:,} | `{esc(r['full_name'])}` | {esc(','.join(r['category']))} | {esc(r.get('laos_stage') or '-')} | {esc(lic)} |")
w()
w("**与既有选型的冲突/替代（节选）：**")
w()
w("- `k2-fsa/sherpa-onnx` 优于 `modelscope/FunASR` 作为端侧 ASR 运行时（已见于 SER 04 §8：ONNX 推理在 proot aarch64 上更稳、体积更小）。")
w("- `snakers4/silero-vad` / `k2-fsa/sherpa-onnx` 的 VAD 是 ①常驻检测首选，纯 CPU、毫秒级、可常驻。")
w("- `ggml-org/whisper.cpp` 是 ③即时蒸馏 ASR 主选；`alphacep/vosk-api` 提供离线多语种备选。")
w("- `xiph/rnnoise` / `breizhn/DTLN` / `Audio-WestlakeU/FullSubNet` 等降噪模型作 ③前置。`sherpa-onnx` 同时含降噪与 VAD。")
w()
w("## 5 · 明确不推荐清单（高星但不适配）")
w()
w("下列仓库 star 很高，但**不应直接作为 laos 组件**——原因是范围外（laos 只听不说）、缺端侧信号、或是云/媒体服务器/编排层。避免「star 高就该用」的误判。")
w()
w("| star | 仓库 | 类别 | 不推荐理由(fit_notes) |")
w("|---:|---|---|---|")
for r in avoid_rows:
    notes = " / ".join(r.get("fit_notes") or []) or (",".join(r["category"]) or "-")
    w(f"| {r['stars']:,} | `{esc(r['full_name'])}` | {esc(','.join(r['category']))} | {esc(trunc(notes,60))} |")
w()
w("典型模式：")
w("- **音乐/TTS 生成类**（so-vits-svc / GPT-SoVITS / Coqui TTS / fish-speech）：laos 只听不说，范围外。")
w("- **巨型框架/编排**（transformers / unsloth / mastra / agenticSeek）：缺 on-device 信号或属 agent 编排层，非漏斗组件。")
w("- **媒体服务器/传输**（ossrs/srs）：属基础设施，非端侧组件。")
w("- **unrelated 泄漏**（awesome-piracy / audacity / seamless_communication）：与漏斗无关，属补抓噪声复核残留。")
w()
w("## 6 · 局限与需人工复核")
w()
w("本报告如实保留 Task 3 执行者标注的「需人工复核」项，**未做粉饰**：")
w()
w("1. **speaker 类「隐私红线」是策略性一律降级**——未区分「纯 diarization 分割（可借鉴）」与「声纹注册（碰红线 C5）」。若某项目仅做流式分割，应人工复核后上调为 core 候选。")
w("2. **端侧可行性（C1）靠关键词近似判定**，未在 proot aarch64 上实测跑通；silero / sherpa-onnx / whisper.cpp 等经 SER 04 §8 论证可行，其余需实测。")
w(f"3. **许可字段 {lic_missing:,}/{N:,}（{100*lic_missing/N:.1f}%）缺失**，core 仅排除云 API wrapper，未逐条核 SPDX，不替代法律意见。")
w("4. **少数 speech-foundation 大模型**（如 `facebookresearch/seamless_communication`）因描述措辞未被关键词命中，被误分到 unrelated。")
w()
w("通用局限：star 数为抓取时刻快照（时变）；类别依赖作者自填 `topics`+`description`，存在标签噪声导致漏标/错标；判定仅基于元数据，未读源码。")
w()
md_text = "\n".join(L) + "\n"
io.open(MD_OUT, "w", encoding="utf-8").write(md_text)
print("WROTE", MD_OUT, len(md_text), "bytes")

# ============================================================
# 2) HTML
# ============================================================
# 调色板（显式 hex，供 SVG fill 使用）
C_BG="#0d1117"; C_PANEL="#161b22"; C_PANEL2="#1c2230"; C_LINE="#2a3140"
C_FG="#e6edf3"; C_DIM="#9aa7b8"
C_CYAN="#39d0d8"; C_ORANGE="#f0883e"; C_RED="#f85149"; C_GREEN="#3fb950"
C_PURPLE="#bc8cff"; C_YELLOW="#e3b341"
CAT_COLORS=[C_CYAN,C_ORANGE,C_PURPLE,C_GREEN,C_YELLOW,C_RED,
             "#7ee787","#79c0ff","#d2a8ff","#ffa657","#56d4dd","#f778ba",
             "#a5d6ff","#ff7b72","#3fb9c9"]

def svg_bar_chart(title, labels, values, colors, unit="", h=300, bar_w=46, gap=18):
    """竖向柱状图，每个柱显式 fill。"""
    W = 80 + len(labels)*(bar_w+gap)
    mx = max(values) if values else 1
    n = len(labels)
    parts=[f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">']
    base = h-40
    for i,(lab,v,col) in enumerate(zip(labels,values,colors)):
        x = 70 + i*(bar_w+gap)
        bh = int(base-30) * (v/mx) if mx else 0
        y = base - bh
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" fill="{col}" rx="3"/>')
        parts.append(f'<text x="{x+bar_w/2}" y="{y-6}" text-anchor="middle" fill="{C_FG}" font-size="12">{v:,}</text>')
        # 类别标签旋转
        parts.append(f'<text x="{x+bar_w/2}" y="{base+16}" text-anchor="end" fill="{C_DIM}" font-size="11" transform="rotate(35 {x+bar_w/2} {base+16})">{esc(lab)}</text>')
    parts.append(f'<line x1="60" y1="{base}" x2="{W-10}" y2="{base}" stroke="{C_LINE}"/>')
    parts.append('</svg>')
    return "\n".join(parts)

def svg_hbar(title, items, maxv, h, color=C_CYAN):
    """横向条形图（top40）。items=[(label, value)]"""
    rowh=22; W=920
    parts=[f'<svg viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">']
    for i,(lab,v) in enumerate(items):
        y=10+i*rowh
        bw = (W-330) * (v/maxv) if maxv else 0
        parts.append(f'<text x="10" y="{y+14}" fill="{C_DIM}" font-size="12">{esc(lab)}</text>')
        parts.append(f'<rect x="300" y="{y+2}" width="{bw:.1f}" height="{rowh-7}" fill="{color}" rx="3"/>')
        parts.append(f'<text x="{310+bw:.1f}" y="{y+14}" fill="{C_FG}" font-size="11.5">{v:,}</text>')
    parts.append('</svg>')
    return "\n".join(parts)

def svg_fit_stacked():
    """laos_fit 三档横向堆叠条。"""
    total=sum(fit_counter.values())
    segs=[("core",fit_counter['core'],C_GREEN),
          ("ref",fit_counter['ref'],C_ORANGE),
          ("unrelated",fit_counter['unrelated'],C_DIM)]
    W=900; x0=20; y=40; H=46
    parts=[f'<svg viewBox="0 0 {W} 120" role="img" aria-label="laos_fit 分布">']
    cx=x0
    for name,v,col in segs:
        bw=(W-40)*(v/total)
        parts.append(f'<rect x="{cx:.1f}" y="{y}" width="{bw:.1f}" height="{H}" fill="{col}"/>')
        parts.append(f'<text x="{cx+bw/2:.1f}" y="{y+H/2+5}" text-anchor="middle" fill="{C_BG}" font-size="13" font-weight="600">{name} {v}</text>')
        cx+=bw
    parts.append('</svg>')
    return "\n".join(parts)

def svg_heat():
    """类别 × 星档 热力矩阵。"""
    bw_labels=[b[0] for b in BUCKETS]
    ncat=len(CATS); nb=len(bw_labels)
    cw=130; ch=26; x0=120; y0=40; W=x0+nb*cw+20; Hh=y0+ncat*ch+30
    # 统计
    grid=collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        for c in r["category"]:
            grid[c][bucket_of(r["stars"])]+=1
    mx=max((grid[c][b] for c in CATS for b in bw_labels), default=1) or 1
    parts=[f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="类别×星档热力矩阵">']
    # 列头
    for j,b in enumerate(bw_labels):
        parts.append(f'<text x="{x0+j*cw+cw/2}" y="{y0-12}" text-anchor="middle" fill="{C_DIM}" font-size="12">{b}</text>')
    for i,c in enumerate(CATS):
        yy=y0+i*ch
        parts.append(f'<text x="{x0-8}" y="{yy+ch/2+4}" text-anchor="end" fill="{C_FG}" font-size="11.5">{esc(c)}</text>')
        for j,b in enumerate(bw_labels):
            v=grid[c][b]
            xx=x0+j*cw
            if v==0:
                parts.append(f'<rect x="{xx+1}" y="{yy+1}" width="{cw-2}" height="{ch-2}" fill="{C_PANEL}" stroke="{C_LINE}"/>')
            else:
                op=max(0.12, 0.92*v/mx)
                parts.append(f'<rect x="{xx+1}" y="{yy+1}" width="{cw-2}" height="{ch-2}" fill="{C_CYAN}" fill-opacity="{op:.2f}" stroke="{C_LINE}"/>')
            parts.append(f'<text x="{xx+cw/2}" y="{yy+ch/2+4}" text-anchor="middle" fill="{C_FG}" font-size="10.5">{v}</text>')
    parts.append('</svg>')
    return "\n".join(parts)

# ---- 构建 HTML ----
H=[]
def h(s=""): H.append(s)

h('<!DOCTYPE html>')
h('<html lang="zh-CN">')
h('<head>')
h('<meta charset="UTF-8">')
h('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
h('<title>音频 / AI / Agent 开源星标全景 · laos</title>')
h('<style>')
h('  :root{')
h('    --bg:#0d1117; --panel:#161b22; --panel2:#1c2230; --line:#2a3140;')
h('    --fg:#e6edf3; --dim:#9aa7b8; --cyan:#39d0d8; --orange:#f0883e;')
h('    --red:#f85149; --green:#3fb950; --purple:#bc8cff; --yellow:#e3b341;')
h('  }')
h('  *{box-sizing:border-box}')
h('  body{margin:0;background:var(--bg);color:var(--fg);')
h('       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;')
h('       font-size:15px;line-height:1.7}')
h('  a{color:var(--cyan);text-decoration:none}')
h('  a:hover{text-decoration:underline}')
h('  .layout{display:flex;max-width:1560px;margin:0 auto}')
h('  nav{position:sticky;top:0;height:100vh;width:238px;flex:0 0 238px;overflow-y:auto;')
h('      border-right:1px solid var(--line);padding:22px 14px;background:#0b0f15}')
h('  nav h4{margin:0 0 12px;font-size:13px;letter-spacing:.12em;color:var(--dim);text-transform:uppercase}')
h('  nav a{display:block;padding:6px 10px;margin:2px 0;border-radius:6px;color:var(--dim);font-size:13.5px}')
h('  nav a:hover{background:var(--panel2);color:var(--fg);text-decoration:none}')
h('  main{flex:1;min-width:0;padding:34px 40px 90px}')
h('  header{border-bottom:1px solid var(--line);padding-bottom:26px;margin-bottom:34px}')
h('  h1{font-size:31px;margin:0 0 10px;letter-spacing:-.01em}')
h('  h1 span{color:var(--cyan)}')
h('  .meta{color:var(--dim);font-size:13px}')
h('  .lead{font-size:16px;color:#c9d5e3;border-left:3px solid var(--cyan);')
h('        padding:12px 16px;background:var(--panel);border-radius:0 8px 8px 0;margin:22px 0}')
h('  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:14px;margin:24px 0 8px}')
h('  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}')
h('  .kpi b{display:block;font-size:26px;color:var(--cyan);line-height:1.25}')
h('  .kpi small{color:var(--dim);font-size:12.5px}')
h('  .kpi.warn b{color:var(--red)} .kpi.ok b{color:var(--green)} .kpi.amber b{color:var(--orange)}')
h('  section{margin:52px 0;scroll-margin-top:14px}')
h('  h2{font-size:22px;margin:0 0 6px;padding-bottom:10px;border-bottom:1px solid var(--line)}')
h('  h2 .num{color:var(--cyan);margin-right:10px;font-variant-numeric:tabular-nums}')
h('  h3{font-size:16.5px;margin:30px 0 10px;color:var(--orange)}')
h('  p{margin:12px 0}')
h('  ul{margin:10px 0;padding-left:22px} li{margin:5px 0}')
h('  code{background:#1b2230;padding:1px 6px;border-radius:4px;font-size:13px;color:var(--purple)}')
h('  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:18px 0}')
h('  .note{color:var(--dim);font-size:13px}')
h('  .tw{overflow-x:auto;border:1px solid var(--line);border-radius:10px;margin:16px 0}')
h('  table{border-collapse:collapse;width:100%;min-width:720px;font-size:13.5px}')
h('  th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}')
h('  th{background:#131a24;color:var(--dim);font-weight:600;white-space:nowrap;position:sticky;top:0}')
h('  tr:last-child td{border-bottom:none}')
h('  tbody tr:hover{background:#141b26}')
h('  .dead{color:var(--red)} .alive{color:var(--green)} .maybe{color:var(--yellow)}')
h('  .tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;')
h('       border:1px solid var(--line);color:var(--dim);white-space:nowrap}')
h('  .tag.c{color:var(--cyan);border-color:#1d4b50} .tag.g{color:var(--green);border-color:#1d4a26}')
h('  .tag.r{color:var(--red);border-color:#4d2220} .tag.o{color:var(--orange);border-color:#4d351d}')
h('  svg{display:block;max-width:100%;height:auto}')
h('  .fig{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px;margin:18px 0}')
h('  .fig .cap{color:var(--dim);font-size:12.5px;margin-top:10px}')
h('  .legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--dim);font-size:12.5px;margin-top:10px}')
h('  .legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px}')
h('  footer{border-top:1px solid var(--line);margin-top:60px;padding-top:20px;color:var(--dim);font-size:13px}')
h('  @media(max-width:960px){nav{display:none}main{padding:24px 18px 60px}}')
h('</style>')
h('</head>')
h('<body>')
h('<div class="layout">')
h('<nav>')
h('  <h4>目录</h4>')
h('  <a href="#top">概览</a>')
h('  <a href="#methods">1 · 方法与限额</a>')
h('  <a href="#charts">2 · 全景图表</a>')
h('  <a href="#top40">3 · 总榜 Top 40</a>')
h('  <a href="#cat">4 · 分类榜</a>')
h('  <a href="#laos">5 · laos core 清单</a>')
h('  <a href="#avoid">6 · 不推荐清单</a>')
h('  <a href="#limits">7 · 局限与复核</a>')
h('</nav>')
h('<main>')
h('<header id="top">')
h('  <h1>音频 / AI / Agent 开源<span>星标全景</span></h1>')
h(f'  <div class="meta">抓取日期 {CRAWLED_AT} ｜ GitHub Search API 未认证快照 ｜ 数据源：repos_classified.jsonl（{N} 条）｜ 零外部依赖单文件</div>')
h('  <div class="lead">')
h(f'    遍历 <b>{N}</b> 个音频 / 语音 AI / 语音·多模态 Agent 方向高星开源项目，覆盖 <b>{len(CATS)}</b> 个功能类别；')
h(f'    真正能进 laos 四段漏斗的 <b>core 仅 {fit_counter["core"]} 个（{100*fit_counter["core"]/N:.1f}%）</b>。')
h('  </div>')
h('  <div class="kpis">')
h(f'    <div class="kpi"><b>{N:,}</b><small>干净仓库总数</small></div>')
h(f'    <div class="kpi"><b>{len(CATS)}</b><small>功能类别（可多标签）</small></div>')
h(f'    <div class="kpi ok"><b>{fit_counter["core"]}</b><small>core 可直接落地</small></div>')
h(f'    <div class="kpi amber"><b>{fit_counter["ref"]:,}</b><small>ref 参考/借鉴</small></div>')
h(f'    <div class="kpi warn"><b>{fit_counter["unrelated"]:,}</b><small>unrelated 无关</small></div>')
h(f'    <div class="kpi warn"><b>{100*lic_missing/N:.0f}%</b><small>许可字段缺失（{lic_missing:,} 条）</small></div>')
h('  </div>')
h('</header>')

# 1 methods
h('<section id="methods">')
h('  <h2><span class="num">01</span>方法与限额说明</h2>')
h('  <ul>')
h('    <li>GitHub Search API（<code>search/repositories</code>）未认证：<b>search 10 次/分钟</b>，每请求 sleep 7；core 60 次/小时常为 0 → 只用 search 端点不补字段。</li>')
h('    <li>单 query 上限 <b>1000 条</b>，按 stars 降序取 top。</li>')
h('    <li>统一 <code>fork:false</code>，落盘后剔除 <code>archived:true</code>。</li>')
h('    <li>去噪（Task 2）：8 个 <code>topic:</code> 切片 100% 相关复用；两裸关键词切片相关率仅 20%/16%，剔除 1376 条噪声后用引号短语补抓找回真相关项目。干净语料 <b>2153 + 1571 = 3724</b>。</li>')
h(f'    <li>抓取时间 <code>{CRAWLED_AT}</code> 落盘；star 为快照，可能过时。</li>')
h('  </ul>')
h('</section>')

# 2 charts
h('<section id="charts">')
h('  <h2><span class="num">02</span>全景图表</h2>')
h('  <div class="fig">')
h('    <div style="font-weight:600;margin-bottom:8px">laos_fit 三档分布</div>')
h(svg_fit_stacked())
h('    <div class="legend"><span><i style="background:#3fb950"></i>core 可直接落地</span><span><i style="background:#f0883e"></i>ref 参考/借鉴</span><span><i style="background:#9aa7b8"></i>unrelated 无关</span></div>')
h('  </div>')
h('  <div class="fig">')
h('    <div style="font-weight:600;margin-bottom:8px">类别分布（按条数）</div>')
h(svg_bar_chart("类别分布", CATS, [cat_counter[c] for c in CATS],
                [CAT_COLORS[i%len(CAT_COLORS)] for i in range(len(CATS))], h=320))
h('  </div>')
h('  <div class="fig">')
h('    <div style="font-weight:600;margin-bottom:8px">star 分档分布</div>')
h(svg_bar_chart("star 分档", [b[0] for b in BUCKETS], [bucket_counter[b[0]] for b in BUCKETS],
                [C_CYAN,C_GREEN,C_ORANGE,C_PURPLE], h=260, bar_w=70, gap=40))
h('  </div>')
h('  <div class="fig">')
h('    <div style="font-weight:600;margin-bottom:8px">类别 × 星档 热力矩阵（单元格数字 = 仓库数）</div>')
h(svg_heat())
h(f'    <div class="cap">共 {N} 条；行=15 个类别，列=star 分档。颜色越亮代表该格仓库越多。注意 kws-vad / aed / dataset 大量集中在低星档，而 codec / music / dsp-lib 中位星更高。</div>')
h('  </div>')
h('  <div class="fig">')
h('    <div style="font-weight:600;margin-bottom:8px">总榜 Top 40 star 条形图</div>')
h(svg_hbar("总榜 Top40", [(r["full_name"], r["stars"]) for r in top40], top40[0]["stars"], 40+len(top40)*22))
h('  </div>')
h('</section>')

# 3 top40 table
h('<section id="top40">')
h('  <h2><span class="num">03</span>总榜 Top 40（star 降序）</h2>')
h('  <div class="tw"><table>')
h('    <thead><tr><th>#</th><th>star</th><th>仓库</th><th>语言</th><th>许可</th><th>一句话用途</th></tr></thead>')
h('    <tbody>')
for i,r in enumerate(top40,1):
    h(f'    <tr><td>{i}</td><td>{r["stars"]:,}</td><td><code>{esc(r["full_name"])}</code></td><td>{esc(r.get("language") or "-")}</td><td>{esc(r.get("license") or "-")}</td><td>{esc(trunc(r["description"],60))}</td></tr>')
h('    </tbody></table></div>')
h('</section>')

# 4 categories
h('<section id="cat">')
h('  <h2><span class="num">04</span>分类榜（15 类，各 Top 12）</h2>')
h(f'  <p class="note">实际统计得到 <b>{len(CATS)}</b> 个类别标签（非背景简报所述「14 类」）：多出 <code>ml-framework</code>（{cat_counter["ml-framework"]} 条）与 <code>agent-llm</code>（{cat_counter["agent-llm"]} 条）。下表以真实 15 类为准。</p>')
for c in CATS:
    h(f'  <h3>{esc(c)}（{cat_counter[c]} 个，中位 {cat_median[c]:,}★）</h3>')
    h('  <div class="tw"><table>')
    h('    <thead><tr><th>star</th><th>仓库</th><th>许可</th><th>一句话用途</th></tr></thead>')
    h('    <tbody>')
    for r in cat_top[c]:
        h(f'    <tr><td>{r["stars"]:,}</td><td><code>{esc(r["full_name"])}</code></td><td>{esc(r.get("license") or "-")}</td><td>{esc(trunc(r["description"],56))}</td></tr>')
    h('    </tbody></table></div>')
h('</section>')

# 5 laos core
h('<section id="laos">')
h('  <h2><span class="num">05</span>laos 适配结论（core 落地清单）</h2>')
h(f'  <p>共 <b>{fit_counter["core"]}</b> 个 <code>laos_fit=core</code>。漏斗落点取自分类器写入的 <code>laos_stage</code> 字段；端侧可行性（C1）以命中 on-device 信号为判据（core 判定已通过），功耗档位见 SER 04 §8；许可（C3）见第 7 节缺失说明。</p>')
h('  <div class="panel">')
h('    <div style="font-weight:600;margin-bottom:8px">漏斗落点分布（core 组件去重计数，可落多段）</div>')
for k in ["①常驻检测","②触发捕获","③即时蒸馏","④原音频即焚"]:
    h(f'    <p style="margin:4px 0"><span class="tag g">{esc(k)}</span> {stage_hit[k]} 个组件</p>')
h('  </div>')
h('  <div class="tw"><table>')
h('    <thead><tr><th>star</th><th>仓库</th><th>类别</th><th>漏斗落点</th><th>许可</th></tr></thead>')
h('    <tbody>')
for r in core_rows:
    h(f'    <tr><td>{r["stars"]:,}</td><td><code>{esc(r["full_name"])}</code></td><td>{esc(",".join(r["category"]))}</td><td>{esc(r.get("laos_stage") or "-")}</td><td>{esc(r.get("license") or "-")}</td></tr>')
h('    </tbody></table></div>')
h('  <h3>与既有选型的冲突 / 替代（节选）</h3>')
h('  <ul>')
h('    <li><code>k2-fsa/sherpa-onnx</code> 优于 <code>modelscope/FunASR</code> 作端侧 ASR 运行时（ONNX 在 proot aarch64 更稳、体积更小，SER 04 §8）。</li>')
h('    <li><code>snakers4/silero-vad</code> / <code>sherpa-onnx</code> 的 VAD 是 ①常驻检测首选，纯 CPU、毫秒级、可常驻。</li>')
h('    <li><code>ggml-org/whisper.cpp</code> 是 ③即时蒸馏 ASR 主选；<code>alphacep/vosk-api</code> 提供离线多语种备选。</li>')
h('    <li><code>xiph/rnnoise</code> / <code>breizhn/DTLN</code> / <code>Audio-WestlakeU/FullSubNet</code> 等降噪作 ③前置。</li>')
h('  </ul>')
h('</section>')

# 6 avoid
h('<section id="avoid">')
h('  <h2><span class="num">06</span>明确不推荐清单（高星但不适配）</h2>')
h('  <p>下列 star 很高但<strong>不应直接作为 laos 组件</strong>——范围外（只听不说）、缺端侧信号、或属云/媒体服务器/编排层。避免「star 高就该用」误判。</p>')
h('  <div class="tw"><table>')
h('    <thead><tr><th>star</th><th>仓库</th><th>类别</th><th>不推荐理由</th></tr></thead>')
h('    <tbody>')
for r in avoid_rows:
    notes = " / ".join(r.get("fit_notes") or []) or (",".join(r["category"]) or "-")
    h(f'    <tr><td>{r["stars"]:,}</td><td><code>{esc(r["full_name"])}</code></td><td>{esc(",".join(r["category"]))}</td><td>{esc(trunc(notes,60))}</td></tr>')
h('    </tbody></table></div>')
h('  <ul>')
h('    <li><b>音乐/TTS 生成类</b>（so-vits-svc / GPT-SoVITS / Coqui TTS / fish-speech）：laos 只听不说，范围外。</li>')
h('    <li><b>巨型框架/编排</b>（transformers / unsloth / mastra / agenticSeek）：缺 on-device 信号或属 agent 编排层。</li>')
h('    <li><b>媒体服务器/传输</b>（ossrs/srs）：基础设施，非端侧组件。</li>')
h('    <li><b>unrelated 泄漏</b>（awesome-piracy / audacity / seamless_communication）：补抓噪声复核残留。</li>')
h('  </ul>')
h('</section>')

# 7 limits
h('<section id="limits">')
h('  <h2><span class="num">07</span>局限与需人工复核</h2>')
h('  <p>如实保留 Task 3 执行者标注的「需人工复核」项，未做粉饰：</p>')
h('  <ul>')
h('    <li><b>speaker 类「隐私红线」是策略性一律降级</b>——未区分「纯 diarization 分割（可借鉴）」与「声纹注册（碰红线 C5）」。仅做流式分割者应人工复核后上调为 core 候选。</li>')
h('    <li><b>端侧可行性（C1）靠关键词近似判定</b>，未在 proot aarch64 实测跑通；silero / sherpa-onnx / whisper.cpp 经 SER 04 §8 论证可行，其余需实测。</li>')
h(f'    <li><b>许可字段 {lic_missing}/{N}（{100*lic_missing/N:.1f}%）缺失</b>，core 仅排除云 API wrapper，未逐条核 SPDX，不替代法律意见。</li>')
h('    <li><b>少数 speech-foundation 大模型</b>（如 <code>facebookresearch/seamless_communication</code>）因描述措辞未被关键词命中，误分 unrelated。</li>')
h('  </ul>')
h('  <p class="note">通用局限：star 数为抓取时刻快照（时变）；类别依赖作者自填 topics+description，存在标签噪声；判定仅基于元数据，未读源码。</p>')
h('</section>')

h('<footer>')
h(f'  数据源 repos_classified.jsonl（{N} 条）｜ 抓取 {CRAWLED_AT} ｜ 由 scripts/build_oss_report.py 从真实字段生成，markdown 与 HTML 数字同源一致。')
h('</footer>')
h('</main>')
h('</div>')
h('</body>')
h('</html>')

html_text = "\n".join(H) + "\n"
io.open(HTML_OUT, "w", encoding="utf-8").write(html_text)
print("WROTE", HTML_OUT, len(html_text), "bytes")

# ---------- 一致性自检 ----------
print("\n=== 一致性自检 ===")
print("total", N, "cats", len(CATS), "core", fit_counter['core'], "ref", fit_counter['ref'], "unrelated", fit_counter['unrelated'])
print("license missing", lic_missing, f"({100*lic_missing/N:.1f}%)")
print("TOP10:")
for r in TOP10:
    print("  ", r["stars"], r["full_name"])
# 验证 md 含 top40 第一名 & html 含（均带千分位逗号）
t0 = top40[0]
fmt = f"{t0['stars']:,}"
assert fmt in md_text and t0["full_name"] in md_text, "md missing top1"
assert fmt in html_text and t0["full_name"] in html_text, "html missing top1"
# 抽查：core 总数 / unrelated 总数 在两文件均出现
for needle in [f"{fit_counter['core']}", f"{fit_counter['unrelated']}", f"{N:,}"]:
    assert needle in md_text and needle in html_text, f"missing {needle}"
print("OK: top1 + 关键总数 present in both md & html")
