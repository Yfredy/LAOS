# -*- coding: utf-8 -*-
"""生成 laos-intro 12 页 pptx 源 SVG（ppt-master quick-generate 契约）。

画布 ppt169 (1280×720)；平铺页 + 根 data-pptx-page-role；lang="zh-CN"。
设计系统：纸白/墨黑/克莱因蓝，与 HTML 系 deck 同源的品牌视觉。
仅用基础图元（rect/line/circle/text），无合并形状（skia-pathops 规避）。
"""
from pathlib import Path

OUT = Path(r"C:\Users\yaoyue\.agents\projects\laos-intro-master_20261005\svg_output")

INK = "#17171A"; SUB = "#55555E"; MUTE = "#8A8A93"; ACC = "#1F3BD8"
ACCSOFT = "#E8EDFB"; LINE = "#E3E3E8"; GOLD = "#C89B3C"; PAPER = "#FFFFFF"
F = "Microsoft YaHei"

def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def head(n, tag):
    return (f'<text x="72" y="50" font-family="{F}" font-size="12" letter-spacing="3" fill="{MUTE}">LAOS · LINUX AGENTOS</text>'
            f'<text x="1208" y="50" font-family="{F}" font-size="12" letter-spacing="2" fill="{MUTE}" text-anchor="end">{n:02d} / 12 · {esc(tag)}</text>'
            f'<line x1="72" y1="66" x2="1208" y2="66" stroke="{LINE}" stroke-width="1"/>')

def foot():
    return (f'<line x1="72" y1="668" x2="1208" y2="668" stroke="{LINE}" stroke-width="1"/>'
            f'<text x="72" y="692" font-family="{F}" font-size="11" fill="{MUTE}">github.com/Yfredy/LAOS · v0.9.0</text>'
            f'<text x="1208" y="692" font-family="{F}" font-size="11" fill="{MUTE}" text-anchor="end">FIELD NOTE 01 · 26.10.05</text>')

def page(fname, role, n, tag, body):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
           f'lang="zh-CN" data-pptx-page-role="{role}">\n'
           f'<rect x="0" y="0" width="1280" height="720" fill="{PAPER}"/>\n'
           + head(n, tag) + "\n" + body + "\n" + foot() + "\n</svg>\n")
    (OUT / fname).write_text(svg, encoding="utf-8")
    return fname

def title(x, y, text, size=44, color=INK, weight=700):
    return f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" font-weight="{weight}" fill="{color}">{esc(text)}</text>'

def body_t(x, y, text, size=20, color=SUB, weight=400, spacing=None):
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    return f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" font-weight="{weight}" fill="{color}"{ls}>{esc(text)}</text>'

def kicker(x, y, text, color=ACC):
    return f'<text x="{x}" y="{y}" font-family="{F}" font-size="13" letter-spacing="4" fill="{color}">{esc(text)}</text>'

PAGES = []

# ---- 01 cover ----
body = (
    f'<rect x="72" y="120" width="240" height="8" fill="{ACC}"/>'
    + kicker(72, 168, "LINUX AGENTOS · FIELD NOTE 01")
    + title(72, 268, "给 AI Agent 一座操作系统", 60)
    + body_t(72, 330, "内核强制的能力边界，而不是提示词恳求", 26, INK, 400)
    + body_t(72, 376, "Linux kernel + Agent + MCP —— 不改内核一行代码", 20)
    + f'<rect x="72" y="430" width="440" height="86" fill="{ACCSOFT}"/>'
    + body_t(96, 466, "703 项测试全绿", 22, ACC, 700)
    + body_t(96, 496, "主库 353 · AlwaysOnRec 279 · Repro 71", 15, SUB)
    + body_t(72, 585, "GitHub · Yfredy/LAOS", 16, SUB)
    + body_t(72, 612, "2026-10-05 · v0.9.0", 15, MUTE)
    + f'<circle cx="1150" cy="300" r="150" fill="none" stroke="{ACC}" stroke-width="2"/>'
    + f'<circle cx="1150" cy="300" r="104" fill="none" stroke="{LINE}" stroke-width="1"/>'
    + f'<circle cx="1150" cy="300" r="58" fill="none" stroke="{LINE}" stroke-width="1"/>'
    + f'<circle cx="1150" cy="300" r="10" fill="{ACC}"/>'
    + f'<text x="1150" y="326" font-family="{F}" font-size="15" fill="{SUB}" text-anchor="middle">laosd</text>'
    + f'<circle cx="1246" cy="300" r="6" fill="{GOLD}"/>'
    + f'<circle cx="1150" cy="204" r="6" fill="{GOLD}"/>'
)
PAGES.append(page("01_cover.svg", "cover", 1, "COVER", body))

# ---- 02 problem ----
rows = [
    ("R-01", "一条 rm -rf 删光家目录", "\u201c请小心\u201d写在提示词里——恳求不是强制，模型没有义务听。"),
    ("R-02", "恶意 MCP 工具直通隐私", "剪贴板、通知、短信：装一个工具等于开一扇没有锁的门。"),
    ("R-03", "不可逆操作无计价", "卸载、发送、删除与读取同权；没有记账，就没有回放与追责。"),
]
y = 190
parts = [kicker(72, 130, "SHEET 02 · 风险台账"), title(72, 190, "Agent 拿着 root 裸奔。")]
y = 260
for no, h, d in rows:
    parts.append(f'<rect x="72" y="{y}" width="1136" height="86" fill="#F7F8FA"/>')
    parts.append(body_t(96, y + 38, no, 20, ACC, 700))
    parts.append(body_t(170, y + 34, h, 21, INK, 700))
    parts.append(body_t(170, y + 64, d, 16, SUB))
    y += 106
parts.append(body_t(72, y + 26, "缺的不是更聪明的模型，是操作系统：能力 · 调度 · 审计 · 记账 · 隔离。", 21, INK, 700))
PAGES.append(page("02_problem.svg", "content", 2, "PROBLEM", "".join(parts)))

# ---- 03 thesis ----
parts = [kicker(72, 130, "SHEET 03 · 设计命题"),
         title(72, 190, "Linux kernel + Agent + MCP", 40),
         title(72, 246, "= Linux AgentOS", 40, ACC)]
prim = [("namespace", "隔离视图 —— mount / pid / net 各自独立"),
        ("cgroup v2", "资源上限 —— 失控的驱动只死自己"),
        ("seccomp BPF", "系统调用白名单 —— 真拦截，非君子协定"),
        ("Landlock", "路径沙箱 —— 未授权目录不可见")]
y = 300
for name, desc in prim:
    parts.append(f'<line x1="72" y1="{y}" x2="1208" y2="{y}" stroke="{LINE}"/>')
    parts.append(body_t(72, y + 34, name, 19, ACC, 700))
    parts.append(body_t(260, y + 34, desc, 17, SUB))
    y += 62
parts.append(f'<rect x="72" y="{y + 10}" width="300" height="52" fill="{INK}"/>')
parts.append(body_t(96, y + 43, "laosd = 薄内核 · 0 补丁", 18, PAPER, 700))
parts.append(body_t(400, y + 43, "只做语义层：能力表 / 审计 / 记账 / 确认；设备交给 MCP 驱动", 16, SUB))
PAGES.append(page("03_thesis.svg", "content", 3, "THESIS", "".join(parts)))

# ---- 04 mapping ----
parts = [kicker(72, 130, "SHEET 04 · 词表映射"), title(72, 190, "Linux 的词表，Agent 的语义。")]
rows = [("进程", "Agent", "PCB · 能力集 · 预算"),
        ("系统调用", "MCP tool call", "JSON-RPC，每次过闸"),
        ("设备驱动", "MCP Server", "drv_mic / drv_ear / drv_screen …"),
        ("内核", "laosd 薄内核", "只做语义层"),
        ("insmod", "load_driver", "外挂任意 MCP 服务器")]
y = 246
parts.append(body_t(72, y - 12, "LINUX", 12, MUTE, 400, 3))
parts.append(body_t(320, y - 12, "LAOS", 12, MUTE, 400, 3))
parts.append(body_t(620, y - 12, "语义", 12, MUTE, 400, 3))
y += 10
for k, v, d in rows:
    parts.append(f'<line x1="72" y1="{y}" x2="1208" y2="{y}" stroke="{LINE}"/>')
    parts.append(body_t(72, y + 36, k, 21, INK, 700))
    parts.append(body_t(320, y + 36, v, 21, ACC, 700))
    parts.append(body_t(620, y + 36, d, 17, SUB))
    y += 64
PAGES.append(page("04_mapping.svg", "content", 4, "MAPPING", "".join(parts)))

# ---- 05 gates ----
parts = [kicker(72, 130, "SHEET 05 · 过闸台账"), title(72, 190, "每一次工具调用，过七道闸。")]
gates = ["能力表", "task_scope", "schema", "EDQUOT", "FleetLedger", "Jev 预审", "确认横幅", "审计"]
x = 72
w = 122
for i, g in enumerate(gates):
    parts.append(f'<rect x="{x}" y="270" width="{w}" height="64" fill="{ACC if i in (1, 7) else ACCSOFT}"/>')
    fill = PAPER if i in (1, 7) else ACC
    parts.append(f'<text x="{x + w / 2}" y="309" font-family="{F}" font-size="15" font-weight="700" fill="{fill}" text-anchor="middle">{esc(g)}</text>')
    if i < len(gates) - 1:
        parts.append(f'<text x="{x + w + 6}" y="309" font-family="{F}" font-size="15" fill="{MUTE}">→</text>')
    x += w + 14
cards = [("task_scope 三种收窄", "路径前缀 · pkg: 应用白名单 · time: 时间窗，权限收到最小。"),
         ("预算与计价", "EDQUOT 见底即拒；FleetLedger 给不可逆操作记账，超出弹确认。"),
         ("可回放", "事后完整回答：谁、何时、用掉了什么权限。")]
x = 72
for h, d in cards:
    parts.append(f'<rect x="{x}" y="396" width="360" height="150" fill="#F7F8FA"/>')
    parts.append(body_t(x + 24, 436, h, 19, INK, 700))
    parts.append(f'<rect x="{x + 24}" y="452" width="44" height="3" fill="{ACC}"/>')
    parts.append(body_t(x + 24, 492, d, 15, SUB))
    x += 388
parts.append(body_t(72, 610, "事后可完整回放：谁在何时用掉了什么权限。", 19, INK, 700))
PAGES.append(page("05_gates.svg", "content", 5, "GATES", "".join(parts)))

# ---- 06 enforcement ----
parts = [kicker(72, 130, "SHEET 06 · 强制规格"),
         title(72, 190, "强制发生在内核，不在上下文窗口。")]
cards = [("SPEC-01", "seccomp BPF", "进程级系统调用白名单。拦截是真实的，不依赖模型自觉。"),
         ("SPEC-02", "cgroup v2", "驱动子进程 CPU / 内存上限；驱动失控不拖垮宿主。"),
         ("SPEC-03", "eBPF + CoW", "行为画像与执行隔离，给每个 Agent 建立档案。")]
x = 72
for tag, h, d in cards:
    parts.append(f'<rect x="{x}" y="260" width="360" height="220" fill="{PAPER}" stroke="{LINE}"/>')
    parts.append(f'<rect x="{x}" y="260" width="360" height="6" fill="{ACC}"/>')
    parts.append(body_t(x + 24, 306, tag, 12, MUTE, 400, 3))
    parts.append(body_t(x + 24, 348, h, 24, INK, 700))
    parts.append(body_t(x + 24, 396, d, 16, SUB))
    x += 388
parts.append(body_t(72, 556, "不发明新机制，只做 Linux 三十年强制原语的正确组合。", 20, INK, 700))
PAGES.append(page("06_enforcement.svg", "content", 6, "ENFORCEMENT", "".join(parts)))

# ---- 07 drivers ----
parts = [kicker(72, 130, "SHEET 07 · 设备清单"), title(72, 190, "MCP Server 就是设备驱动。")]
cells = [("drv_mic / drv_ear", "录音只由显式 syscall 触发；本地 ASR + 韵律评估"),
         ("drv_screen", "adb 屏幕操控 · pkg: 应用白名单收窄"),
         ("drv_notify / comms", "通知与短信——敏感数据走可信闸"),
         ("drv_npu / events", "端侧感知事件环形缓冲"),
         ("drv_battery 等", "手机五层能力的传感面"),
         ("load_driver 外挂", "一行把 mobile-mcp 等任意 MCP 服务器装成驱动·遥测必关")]
for i, (h, d) in enumerate(cells):
    cx = 72 + (i % 3) * 388
    cy = 250 + (i // 3) * 190
    acc = i == 5
    parts.append(f'<rect x="{cx}" y="{cy}" width="360" height="166" fill="{ACCSOFT if acc else "#F7F8FA"}"/>')
    parts.append(body_t(cx + 24, cy + 44, h, 19, ACC if acc else INK, 700))
    parts.append(f'<rect x="{cx + 24}" y="{cy + 60}" width="44" height="3" fill="{ACC}"/>')
    parts.append(body_t(cx + 24, cy + 100, d, 15, SUB))
PAGES.append(page("07_drivers.svg", "content", 7, "DRIVERS", "".join(parts)))

# ---- 08 funnel ----
parts = [kicker(72, 130, "SHEET 08 · 听觉台账"), title(72, 190, "常开，但克制。")]
stages = [("S-01", "常驻检测", "µW 级", "PCEN/VAD 低功耗常开——功耗预算决定一切。"),
          ("S-02", "触发捕获", "15s", "环形缓冲 + 私有唤醒词 DTW（纯 JSON 非声纹）。"),
          ("S-03", "即时蒸馏", "零上云", "SenseVoice 全本地 ASR + 情感。"),
          ("S-04", "即焚", "6h", "默认六小时留存；LAOS_REC=0 全局禁录。")]
y = 246
for no, h, k, d in stages:
    parts.append(f'<line x1="72" y1="{y}" x2="1208" y2="{y}" stroke="{LINE}"/>')
    parts.append(body_t(72, y + 36, no, 18, ACC, 700))
    parts.append(body_t(170, y + 36, h, 21, INK, 700))
    parts.append(body_t(360, y + 36, k, 21, GOLD, 700))
    parts.append(body_t(520, y + 36, d, 16, SUB))
    y += 64
parts.append(f'<rect x="72" y="{y + 14}" width="700" height="48" fill="{INK}"/>')
parts.append(body_t(96, y + 45, "红线：录音只由显式 syscall 触发 · 每次调用审计 · ASR 全本地", 16, PAPER, 700))
PAGES.append(page("08_funnel.svg", "content", 8, "HEARING", "".join(parts)))

# ---- 09 jev ----
parts = [kicker(72, 130, "SHEET 09 · 判断台账"), title(72, 190, "快问快答判断层，校准先行。")]
cards = [("TYPES", "三判型", "Noul 是非 · Choice 2-255 选项 · Score 2-10 级。"),
         ("GATES", "四闸门", "高危预审 · 记忆过滤 · 压缩选择 · 技能质量。"),
         ("CALIBRATION", "校准教训", "rule 后端 accuracy 0.519")]
x = 72
for tag, h, d in cards:
    parts.append(f'<rect x="{x}" y="260" width="360" height="210" fill="#F7F8FA"/>')
    parts.append(body_t(x + 24, 304, tag, 12, MUTE, 400, 3))
    parts.append(body_t(x + 24, 346, h, 23, INK, 700))
    parts.append(body_t(x + 24, 394, d, 16, SUB))
    x += 388
parts.append(body_t(896, 424, "高置信桶错误率 33% → AUTOGATE 禁配 rule", 16, SUB))
parts.append(body_t(72, 546, "判断后端可插拔（none / rule / cloud / local）——校准数据说了算。", 20, INK, 700))
PAGES.append(page("09_jev.svg", "content", 9, "JUDGMENT", "".join(parts)))

# ---- 10 corpus ----
parts = [kicker(72, 130, "SHEET 10 · 证据台账"), title(72, 190, "设计不拍脑袋。")]
stats = [("19,792", "双会议全量论文遍历", 460), ("9,908", "多顶会主题切片 · 35 venue", 230),
         ("3,724", "开源仓库普查", 90), ("76", "采纳总纲映射", 36)]
x = 72
for num, label, bar in stats:
    parts.append(f'<text x="{x}" y="330" font-family="{F}" font-size="52" font-weight="700" fill="{ACC}">{num}</text>')
    parts.append(f'<rect x="{x + 8}" y="{652 - bar}" width="46" height="{bar}" fill="{ACCSOFT}"/>')
    parts.append(body_t(x, 370, label, 15, SUB))
    x += 292
parts.append(f'<line x1="72" y1="652" x2="1208" y2="652" stroke="{INK}"/>')
parts.append(body_t(72, 460, "每个模块背后是可溯源的论文与开源证据链 —— corpus/ 全量公开。", 19, INK, 700))
parts.append(body_t(72, 492, "Interspeech 5,507 + ICASSP 14,285；落地 33 / 推荐 23 / 不做 20。", 15, SUB))
PAGES.append(page("10_corpus.svg", "content", 10, "EVIDENCE", "".join(parts)))

# ---- 11 repro ----
parts = [kicker(72, 130, "SHEET 11 · 复现台账"), title(72, 190, "能复现的，全部复现。")]
rows = [("F-01", "BS.1770-4 响度计量", "R128 校准点 −23.00 LUFS ±0.1 · True Peak 4×"),
        ("F-02", "FxLMS 主动降噪", "发动机阶次收敛 >20dB · 2×2 多通道 ~15dB"),
        ("F-03", "头部朝向论文全管线", "镜像源法 + STFT 相位 + BiGRU-MHSA · 冒烟 56.5°"),
        ("F-04", "PhaseCoder 麦位编码", "与官方 JAX 源码逐行对齐（α=7 · β=4）"),
        ("F-05", "Pipecat 帧管道 + unique_lock", "打断作废排队帧而系统帧穿管 · RAII/defer/try_lock")]
y = 250
for no, h, d in rows:
    parts.append(f'<line x1="72" y1="{y}" x2="1208" y2="{y}" stroke="{LINE}"/>')
    parts.append(body_t(72, y + 36, no, 18, ACC, 700))
    parts.append(body_t(160, y + 36, h, 20, INK, 700))
    parts.append(body_t(560, y + 36, d, 16, SUB))
    y += 62
parts.append(f'<rect x="72" y="{y + 8}" width="260" height="52" fill="{ACC}"/>')
parts.append(body_t(96, y + 42, "71 项测试全绿", 19, PAPER, 700))
parts.append(body_t(360, y + 42, "TDD · 零新依赖 · 论文数字不作断言 · 偏差全记档", 16, SUB))
PAGES.append(page("11_repro.svg", "content", 11, "REPRO", "".join(parts)))

# ---- 12 ending ----
body = (
    kicker(72, 168, "SHEET 12 · 竣工与下一步")
    + title(72, 280, "能力边界写在内核里，", 52)
    + title(72, 348, "不写在提示词里。", 52, ACC)
    + f'<line x1="72" y1="400" x2="500" y2="400" stroke="{GOLD}" stroke-width="3"/>'
    + body_t(72, 448, "v0.1 → v0.9 语义化版本 · Keep a Changelog · GitHub Release 页", 19, INK, 700)
    + body_t(72, 480, "一个完整需求波次 = 一次 MINOR；合规红线前置（EU AI Act / PIPL / 拒绝伪装采集）。", 16, SUB)
    + body_t(72, 548, "NEXT", 13, MUTE, 400, 4)
    + body_t(72, 584, "drv_screen 真机验收 → 外挂驱动 PoC（mobile-mcp）→ bs1770 响度合入主库", 18, ACC, 700)
    + body_t(72, 632, "github.com/Yfredy/LAOS · 26.10.05", 15, MUTE)
)
PAGES.append(page("12_ending.svg", "ending", 12, "AS-BUILT", body))

print("written:", len(PAGES), "pages →", OUT)
