# -*- coding: utf-8 -*-
"""组装 guizang 瑞士风 laos 创新融资 deck：注入 15 页 sections + SPEAKER_NOTES。
版式映射（Swiss locked mode S01-S22 + 两个 ASCII 特殊页）：
  P1  SWISS-COVER-ASCII   封面
  P2  S03  Split Statement 一页看懂（statement 白名单）
  P3  S13  Three Forces    痛点三柱
  P4  S18  Why Now         为什么是现在（三浪）
  P5  S05  Three Layers    产品架构三层
  P6  S11  Horizontal Timeline 8 环闸门链
  P7  S04  Six Cells       端侧听觉栈六层
  P8  S12  Manifesto       合规先发（ink banner）
  P9  S15  Matrix + Hero   竞争四象限
  P10 S20  Stacked Ledger  里程碑大数字
  P11 S19  Four Cards      商业模式三线+定价哲学
  P12 S17  System Diagram  TAM/SAM/SOM 同心圆（示例标注）
  P13 S02  Vertical Timeline 路线图 Q1-Q4
  P14 S06  KPI Tower       融资用途拆分（示例标注；lbl 无 center）
  P15 SWISS-CLOSING-ASCII  团队与风险收尾
"""
import re
from pathlib import Path

SRC = Path(r"C:\Users\yaoyue\.agents\skills\guizang-ppt-skill\assets\template-swiss.html")
DST = Path(r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\ppt\funding\laos-funding-guizang.html")

N = 15
CHROME = ('<header class="chrome-min"><div class="l">laos · Linux AgentOS · 创新融资项目介绍</div>'
          '<div class="r">SS · 26.10.05 · {n:02d} / ' + str(N) + '</div></header>')

SECTIONS = []

# ---------- P1 封面 ----------
SECTIONS.append(f'''
<section class="slide accent" data-animate="hero" data-layout="SWISS-COVER-ASCII" data-slide-id="cover">
  <div class="canvas-card">
    <canvas class="ascii-bg" aria-hidden="true"></canvas>
    {CHROME.format(n=1)}
    <div style="flex:1;padding:0;display:grid;grid-template-rows:auto 1fr auto;gap:2.6vh">
      <div data-anim="kicker" class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em">LAOS · LINUX AGENTOS · FUNDING DECK</div>
      <h1 data-anim="title" style="align-self:center;font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(7.6vw,13.5vh);line-height:.98;letter-spacing:-.025em;color:#fff">给 AI Agent<br/>装上<span style="font-style:italic;font-weight:300">治理内核</span></h1>
      <div data-anim="bottom" style="display:grid;grid-template-rows:auto auto;gap:1.6vh;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh">
        <div data-anim="lead" class="lead" style="max-width:54ch;color:rgba(255,255,255,.86);font-weight:300">laos v0.12.0 —— 8 环 syscall 闸门链 + 15 个设备驱动 + 全自研端侧听觉栈：模型负责想，laos 负责说「不」。</div>
        <div style="display:flex;justify-content:space-between;align-items:end">
          <div class="t-meta" style="color:rgba(255,255,255,.6)">创新融资 · 项目介绍 · 2026-10</div>
          <div class="t-meta" style="color:rgba(255,255,255,.6)">v0.12.0 · 30 天 12 版本 · 765 测试</div>
        </div>
      </div>
    </div>
  </div>
</section>''')

# ---------- P2 一页看懂（S03 statement，白名单内） ----------
SECTIONS.append(f'''
<section class="slide split" data-animate="statement" data-layout="S03" data-slide-id="one-slide">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min" style="margin-bottom:0"><div class="l">02 / {N} · ONE SLIDE</div><div class="r">IF THEY REMEMBER</div></div>
        <div>
          <div class="t-meta" style="margin-bottom:2.4vh">IF THEY REMEMBER ONE SLIDE</div>
          <h1 style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(5.2vw,9.2vh);line-height:1.06;letter-spacing:-.03em;color:var(--text-primary)">模型负责想，<br/>laos 负责说<span style="font-style:italic;font-weight:300;color:var(--accent)">「不」</span>。</h1>
        </div>
        <div class="t-meta" style="color:var(--text-helper)">— laos · Linux AgentOS · v0.12.0</div>
      </div>
      <div class="half b-grey" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min" style="margin-bottom:0"><div class="l">AT A GLANCE</div><div class="r">03 BLOCKS</div></div>
        <div style="display:flex;flex-direction:column;gap:2.6vh">
          <div>
            <span class="t-cat">问题</span>
            <p style="font-size:max(18px,1.05vw);line-height:1.65;color:var(--text-secondary);margin-top:.8vh">Agent 直接拿工具，没有「系统调用」层——<strong style="font-weight:600;color:var(--text-primary)">无预算、无审计、无回滚、无合规</strong>。</p>
          </div>
          <div>
            <span class="t-cat" style="color:var(--accent)">方案</span>
            <p style="font-size:max(18px,1.05vw);line-height:1.65;color:var(--text-secondary);margin-top:.8vh">laos = 用户态 Agent 内核：8 环 syscall 闸门链（能力→范围→校验→预算→计价→预审→确认→审计）。</p>
          </div>
          <div>
            <span class="t-cat">进展</span>
            <p style="font-size:max(18px,1.05vw);line-height:1.65;color:var(--text-secondary);margin-top:.8vh">开源 v0.12.0 · 15 个设备驱动 · 端侧听觉栈全自研纯 stdlib · 19,792 篇论文语料。</p>
          </div>
        </div>
        <div class="t-meta" style="color:var(--text-helper)">一句话：模型负责想，laos 负责说「不」</div>
      </div>
    </div>
  </div>
</section>''')

# ---------- P3 痛点三柱（S13） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="three-forces" data-layout="S13" data-slide-id="problem">
  <div class="canvas-card">
    {CHROME.format(n=3)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">The Problem · Three Pillars</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">三条断层，<br/>挡住企业上 Agent。</h2>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(12,1fr);gap:2.6vw;flex:1;margin-top:2.6vh;align-items:stretch">
      <div class="span-5" style="background:var(--ink);padding:3.4vh 2.2vw;position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between">
        <span class="dot-mat" style="right:-5vw;bottom:-5vh;width:18vw;height:18vw;opacity:.5"></span>
        <div style="position:relative;z-index:1">
          <span class="t-cat on-dark">No Syscall Layer</span>
          <h2 style="font-weight:200;font-size:min(3.4vw,6.2vh);line-height:1.1;letter-spacing:-.02em;color:#fff;margin-top:1.4vh">无预算 · 无审计<br/>无回滚 · 无合规</h2>
        </div>
        <div class="t-meta" style="color:rgba(255,255,255,.62);position:relative;z-index:1">一次 tool call = 一次不可逆操作</div>
      </div>
      <div class="span-7" style="display:flex;flex-direction:column;gap:1.8vh;justify-content:center">
        <article class="card-fill" style="display:grid;grid-template-columns:auto 1fr;gap:1.4vw;align-items:center;padding:2.2vh 1.8vw">
          <div style="font-weight:200;font-size:4.6vw;color:var(--accent);line-height:.9">01</div>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">失控成本</h4>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">误删文件、超额扣费、并发写坏状态——LangChain / MCP host 在应用层 try-catch，挡不住。</p></div>
        </article>
        <article class="card-fill" style="display:grid;grid-template-columns:auto 1fr;gap:1.4vw;align-items:center;padding:2.2vh 1.8vw">
          <div style="font-weight:200;font-size:4.6vw;color:var(--accent);line-height:.9">02</div>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">合规黑洞</h4>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">EU AI Act 已生效、PIPL 把声纹列为敏感个人信息——企业上 Agent 缺一层可审计的证据链。</p></div>
        </article>
        <article class="card-fill" style="display:grid;grid-template-columns:auto 1fr;gap:1.4vw;align-items:center;padding:2.2vh 1.8vw">
          <div style="font-weight:200;font-size:4.6vw;color:var(--accent);line-height:.9">03</div>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">端侧碎片</h4>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">麦克风 / 屏幕 / 通知 / NPU 各自为 SDK，Agent 接入每件设备都要重写一遍，且没有统一隐私闸。</p></div>
        </article>
      </div>
    </div>
  </div>
</section>''')

# ---------- P4 为什么是现在（S18 三浪） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="why-now" data-layout="S18" data-slide-id="why-now">
  <div class="canvas-card">
    {CHROME.format(n=4)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Why Now · Three Waves</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">三浪叠加，<br/>治理层窗口正打开。</h2>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(3,1fr);gap:2.6vw;flex:1;margin-top:2.8vh;align-content:stretch">
      <div style="display:flex;flex-direction:column;gap:1.2vh;min-height:0">
        <div style="display:flex;flex-direction:column;gap:1.2vh">
          <span class="t-cat">浪 01</span>
          <h3 style="font-weight:400;font-size:max(18px,1.35vw)">MCP 成为事实标准</h3>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">2026-07-28 规范更新：Tasks / Elicitation / MRTR——工具调用接口统一，治理层有了统一切入点。</p>
        </div>
        <span style="font-weight:200;font-size:6.6vw;line-height:.9;margin-top:auto">01</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.2vh;min-height:0">
        <div style="display:flex;flex-direction:column;gap:1.2vh">
          <span class="t-cat">浪 02</span>
          <h3 style="font-weight:400;font-size:max(18px,1.35vw)">Agent 从聊天走向执行</h3>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">企业开始让 Agent 动真实系统——「能干活」到「敢让它干活」之间，差的正是 OS 层。</p>
        </div>
        <span style="font-weight:200;font-size:6.6vw;line-height:.9;margin-top:auto">02</span>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.2vh;min-height:0">
        <div style="display:flex;flex-direction:column;gap:1.2vh">
          <span class="t-cat" style="color:var(--accent)">浪 03</span>
          <h3 style="font-weight:400;font-size:max(18px,1.35vw)">监管落地窗口</h3>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">EU AI Act 分阶段生效 · 国内生成式算法备案——合规是预算充足的用户。</p>
        </div>
        <span style="font-weight:200;font-size:6.6vw;line-height:.9;margin-top:auto;color:var(--accent)">03</span>
      </div>
    </div>
  </div>
</section>''')

# ---------- P5 产品架构（S05 三层） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="stack-build" data-layout="S05" data-slide-id="product">
  <div class="canvas-card">
    {CHROME.format(n=5)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">The Product · Architecture</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">三层结构：<br/>用户态 Agent 内核。</h2>
    </div>
    <div class="stack-row" style="margin-top:3vh">
      <div class="stack-block b-grey">
        <span class="layer-nb">LAYER 01</span>
        <span class="layer-icon"><i data-lucide="bot"></i></span>
        <div class="layer-ttl">Agent / 模型</div>
        <p class="layer-desc">负责想：规划、推理、决策——不直接触碰工具。</p>
        <span class="layer-tag">PLANNER</span>
      </div>
      <div class="stack-block b-accent">
        <span class="layer-nb">LAYER 02</span>
        <span class="layer-icon"><i data-lucide="cpu"></i></span>
        <div class="layer-ttl">laos 内核</div>
        <p class="layer-desc">闸门链 + 调度 + 分支 + 记忆。三件内核语义：tool call = 系统调用 · MCP Server = 设备驱动 · 能力表 = 权限位。</p>
        <span class="layer-tag">0 第三方依赖 · PURE STDLIB</span>
      </div>
      <div class="stack-block b-ink">
        <span class="layer-nb">LAYER 03</span>
        <span class="layer-icon"><i data-lucide="plug-zap"></i></span>
        <div class="layer-ttl">15 个驱动子进程</div>
        <p class="layer-desc">drv_mic · drv_ear · drv_screen … ↔ Linux / MCP / 外设——每个驱动都是隔离子进程。</p>
        <span class="layer-tag">15 DRIVERS</span>
      </div>
    </div>
    <div class="t-meta" style="margin-top:2vh;color:var(--text-helper)">零依赖承诺：内核纯 Python stdlib——可进任何低端安卓 / 边缘盒子的 Python 环境</div>
  </div>
</section>''')

# ---------- P6 八环闸门链（S11） ----------
GATES = [("01", "能力表", "up", False), ("02", "task_scope", "down", False),
         ("03", "schema", "up", False), ("04", "EDQUOT 预算", "down", False),
         ("05", "FleetLedger 计价", "up", True), ("06", "Jev 预审", "down", False),
         ("07", "确认横幅", "up", False), ("08", "审计", "down", False)]
nodes = "".join(
    f'''<div class="th-node{' accent' if acc else ''} {pos}"><span class="dot"></span>'''
    f'''<span class="label" style="width:9.5vw"><span class="yr">{num}</span><span class="name">{name}</span></span></div>'''
    for num, name, pos, acc in GATES)
SECTIONS.append(f'''
<section class="slide" data-animate="timeline-walk" data-layout="S11" data-slide-id="gates">
  <div class="canvas-card">
    {CHROME.format(n=6)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Moat 01 · Syscall Gate Chain × 8</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">八环闸门：<br/>越界在第二环即拒。</h2>
      <p style="font-size:max(18px,1.05vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300">先扣账后派发——FleetLedger 不可逆计价，操作前风险已定价，事后不可抵赖；每一次调用都可完整回放「谁在何时用掉了什么权限」。</p>
    </div>
    <div class="timeline-h" style="margin:0 0 4vh">
      <span class="tl-h-axis"></span>
      <div class="tl-row" style="display:grid;grid-template-columns:repeat(8,1fr);align-items:center;width:100%">
        {nodes}
      </div>
    </div>
    <div class="t-meta" style="color:var(--text-helper)">对照：应用层 guardrail / 策略文件 = 「建议」 · laos = 「强制」——第 2 环即拒，驱动根本不被触达</div>
  </div>
</section>''')

# ---------- P7 端侧听觉栈（S04 六格） ----------
LAYERS = [
    ("activity", "01", "VAD 常驻检测", "低功耗常开的语音活动检测"),
    ("gauge", "02", "BS.1770-4 响度", "校准锚点 −23.00 LUFS ±0.1"),
    ("audio-lines", "03", "Goertzel 双耳 ILD·IPD", "双耳时差与相位差定位线索"),
    ("mic", "04", "麦克风几何 MPE", "麦克风阵列参数估计"),
    ("box", "05", "FOA 编解码", "一阶 Ambisonics 空间音频"),
    ("radio", "06", "ShoNet 声源定位复现", "论文级复现，与官方实现对齐"),
]
cells = "".join(
    f'<div class="sub-card"><i data-lucide="{ico}"></i><span class="nb-corner">{n}</span><div class="ttl">{t}</div><p class="desc">{d}</p></div>'
    for ico, n, t, d in LAYERS)
SECTIONS.append(f'''
<section class="slide" data-animate="grid-reveal" data-layout="S04" data-slide-id="hearing">
  <div class="canvas-card">
    {CHROME.format(n=7)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Moat 02 · On-Device Hearing Stack</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">全自研、纯 stdlib 的<br/>端侧听觉栈。</h2>
      <p style="font-size:max(18px,1.05vw);color:var(--text-secondary);max-width:64ch;line-height:1.7;font-weight:300">全双工三件套：时序度量 · speak-hold-stop 轮转 · 打断即作废轮缓冲。语音是 Agent 最自然的入口，端侧 = 隐私合规的唯一安全区——而市面方案全部依赖云端大模型。</p>
    </div>
    <div class="sub-grid-3-2">
      {cells}
    </div>
  </div>
</section>''')

# ---------- P8 合规先发（S12 宣言 + ink 通栏） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="manifesto" data-layout="S12" data-slide-id="compliance">
  <div class="canvas-card">
    {CHROME.format(n=8)}
    <div style="display:grid;grid-template-columns:repeat(12,1fr);gap:2.6vw;flex:1;align-items:start;padding-top:1vh">
      <div class="span-7">
        <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh">
          <span class="t-cat">Moat 03 · Compliance First</span>
          <div><h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">可审计，<br/>是入场券。</h2></div>
        </div>
        <ul style="list-style:none;display:flex;flex-direction:column;gap:1.2vh;margin-top:2.4vh">
          <li style="font-family:var(--mono);font-size:max(14px,.85vw);letter-spacing:.14em;color:var(--text-secondary)">EU AI ACT 禁令清单 · 已完成法条功课</li>
          <li style="font-family:var(--mono);font-size:max(14px,.85vw);letter-spacing:.14em;color:var(--text-secondary)">PIPL 声纹 = 敏感个人信息 · 单独同意</li>
          <li style="font-family:var(--mono);font-size:max(14px,.85vw);letter-spacing:.14em;color:var(--text-secondary)">录音四红线：显式 syscall · LAOS_REC=0 · 全量审计 · ASR 本地</li>
        </ul>
      </div>
      <div class="span-5" style="padding-top:1.2vw">
        <span class="t-cat">拒绝清单实证</span>
        <p style="font-size:max(18px,1.05vw);line-height:1.7;color:var(--text-secondary);font-weight:300;margin-top:1.4vh">对标开源产品的七个越界文件逐行分析后，<strong style="font-weight:600;color:var(--text-primary)">一行不抄</strong>——红线不是口号，是提交记录可查的工程事实。</p>
      </div>
    </div>
    <div class="ink-banner-full" data-anim="up" style="margin:3vh -5vw -4.4vh;background:var(--ink);padding:3.4vh 5vw;display:flex;align-items:center;justify-content:space-between;gap:2vw">
      <div style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(2.6vw,4.6vh);letter-spacing:-.02em;color:#fff">法条功课做在前面，<span style="font-style:italic;font-weight:300">红线写进内核</span>。</div>
      <div style="display:flex;gap:2vw;color:rgba(255,255,255,.72)">
        <i data-lucide="scale" style="width:2.2vw;height:2.2vw"></i>
        <i data-lucide="shield-check" style="width:2.2vw;height:2.2vw"></i>
        <i data-lucide="file-search" style="width:2.2vw;height:2.2vw"></i>
      </div>
    </div>
  </div>
</section>''')

# ---------- P9 竞争四象限（S15） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="matrix-fill" data-layout="S15" data-slide-id="landscape">
  <div class="canvas-card">
    {CHROME.format(n=9)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Competitive Landscape</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">四象限里，<br/>只有一个空位。</h2>
    </div>
    <div style="display:flex;justify-content:space-between;gap:2vw;margin-top:1.8vh">
      <span class="t-meta">X · L0 框架/壳 → L3 libOS</span>
      <span class="t-meta">Y · 建议性 → 执行路径强制</span>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(2,1fr);grid-template-rows:1fr 1fr;gap:1.2vw;flex:1;margin-top:1.2vh;min-height:0">
      <div class="card-fill" style="padding:2.2vh 1.6vw;display:flex;flex-direction:column;justify-content:space-between;min-height:0">
        <div><span class="t-cat">端侧派</span>
        <h3 style="font-weight:400;font-size:max(18px,1.4vw);margin-top:.8vh">各家设备 SDK</h3></div>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.55">麦克风 / 屏幕 / NPU 各自为政——无 OS 语义，无统一隐私闸。</p>
        <span class="t-meta" style="color:var(--text-helper)">L1 · 端侧 · 无强制</span>
      </div>
      <div class="card-accent" style="padding:2.2vh 1.6vw;display:flex;flex-direction:column;justify-content:space-between;min-height:0">
        <div><span class="t-cat">laos</span>
        <h3 style="font-weight:400;font-size:max(18px,1.4vw);margin-top:.8vh">强制 × 端侧 × 账本</h3></div>
        <p style="font-size:max(16px,.95vw);line-height:1.55;color:rgba(255,255,255,.9)">唯一同时落在执行路径强制层、端侧驱动与审计账本三轴上的占位。</p>
        <span class="t-meta">L2 · 用户态强制层</span>
      </div>
      <div class="card-fill" style="padding:2.2vh 1.6vw;display:flex;flex-direction:column;justify-content:space-between;min-height:0">
        <div><span class="t-cat">框架派</span>
        <h3 style="font-weight:400;font-size:max(18px,1.4vw);margin-top:.8vh">LangGraph 等</h3></div>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.55">应用层 guardrail 是「建议」，越权照样放行。</p>
        <span class="t-meta" style="color:var(--text-helper)">L0-L1 · 建议性</span>
      </div>
      <div class="card-fill" style="padding:2.2vh 1.6vw;display:flex;flex-direction:column;justify-content:space-between;min-height:0">
        <div><span class="t-cat">治理派</span>
        <h3 style="font-weight:400;font-size:max(18px,1.4vw);margin-top:.8vh">策略引擎</h3></div>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.55">策略在旁路执行，不在工具调用路径上。</p>
        <span class="t-meta" style="color:var(--text-helper)">旁路 · 不在执行路径</span>
      </div>
    </div>
    <div data-anim="up" style="margin-top:2vh">
      <div style="display:grid;grid-template-columns:auto 1fr;gap:2.4vw;align-items:center">
        <div>
          <p style="font-size:max(16px,.98vw);color:var(--text-secondary);line-height:1.6">坐标系里的空位已被占住。学术对照：Rutgers AIOS 调度优先，与 laos <strong style="font-weight:600;color:var(--text-primary)">互补不互竞</strong>（调研结论）。</p>
          <span class="t-meta" style="color:var(--text-helper)">COMPETITOR MAP · 2026-10</span>
        </div>
        <div style="font-weight:200;font-size:min(6.4vw,11vh);line-height:.9;letter-spacing:-.04em;color:var(--accent);justify-self:end">L2</div>
      </div>
    </div>
  </div>
</section>''')

# ---------- P10 里程碑大数字（S20 账单） ----------
LEDGER = [
    ("12", "MINOR VERSIONS / 30 天", "v0.1.0 → v0.12.0，每版本有 tag + Release + CHANGELOG", "git-tag"),
    ("765", "TESTS GREEN", "主库 415 · 隔离区 279 · 复现区 71，TDD 先红后绿", "check-check"),
    ("19,792", "PAPER CORPUS", "双会议全量论文语料，设计全部可溯源", "book-open"),
    ("3,724", "REPO SURVEY", "OSS 星标库分级 + 47 份调研文档", "github"),
    ("4", "PAPER-LEVEL REPRO", "响度 · ANC · DOA · MPE，与官方实现逐行对齐", "flask-conical"),
]
rows = "".join(
    f'''<div class="ledger-row" style="display:grid;grid-template-columns:13vw 1fr auto;gap:2vw;align-items:center;padding:1.6vh 0;border-bottom:1px solid var(--border-subtle)">
      <div class="ledger-num" style="font-weight:200;font-size:min(4.4vw,8vh);line-height:.95;letter-spacing:-.035em;font-feature-settings:'tnum'">{num}</div>
      <div class="ledger-label"><div style="font-weight:500;font-size:max(16px,1.05vw);letter-spacing:.02em">{lbl}</div>
      <p style="font-size:max(16px,.92vw);color:var(--text-secondary);line-height:1.5;margin-top:.4vh">{desc}</p></div>
      <span class="ledger-icon" style="display:flex"><i data-lucide="{ico}" style="width:1.8vw;height:1.8vw;stroke-width:1.5;color:var(--accent)"></i></span>
    </div>'''
    for num, lbl, desc, ico in LEDGER)
SECTIONS.append(f'''
<section class="slide" data-animate="stacked-ledger" data-layout="S20" data-slide-id="traction">
  <div class="canvas-card">
    {CHROME.format(n=10)}
    <div style="display:flex;flex-direction:column;gap:1vh;padding-top:.6vh">
      <span class="t-cat">Traction · 全部真实</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">30 天，12 个版本，<br/>765 项测试全绿。</h2>
    </div>
    <div data-anim="ledger" style="display:flex;flex-direction:column;flex:1;justify-content:center;margin-top:.6vh">
      {rows}
    </div>
    <div style="display:flex;justify-content:space-between;align-items:end;gap:2vw;margin-top:1.4vh">
      <span class="t-meta" style="color:var(--text-helper)">开源一个月 · 社区冷启动期（诚实呈现：尚无外部贡献者，增长看 issue / PR 转化）</span>
      <span class="t-meta" style="color:var(--text-helper)">ALL NUMBERS AUDITABLE</span>
    </div>
  </div>
</section>''')

# ---------- P11 商业模式（S19 四卡） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="four-cards" data-layout="S19" data-slide-id="business">
  <div class="canvas-card">
    {CHROME.format(n=11)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:2vh;padding-top:1vh">
      <div style="width:80px;height:2px;background:var(--accent)"></div>
      <div style="display:flex;flex-direction:column;gap:1.2vh">
        <span class="t-cat">Business Model · 三条收入线</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">先开源建标准，<br/>卖的是「敢用」。</h2>
      </div>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(4,1fr);gap:1.8vw;flex:1;margin-top:3vh;align-content:stretch">
      <div style="display:flex;flex-direction:column;gap:1.2vh;border-top:1px solid var(--border-subtle);padding-top:1.8vh;min-height:0">
        <span class="t-meta">LINE 01</span>
        <h3 style="font-weight:400;font-size:max(18px,1.45vw);line-height:1.15">治理中间件</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">企业私有化 Agent 治理：闸门链 + FleetLedger 账本打包进企业 MCP 网关。License + SLA。</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.2vh;border-top:1px solid var(--border-subtle);padding-top:1.8vh;min-height:0">
        <span class="t-meta">LINE 02</span>
        <h3 style="font-weight:400;font-size:max(18px,1.45vw);line-height:1.15">审计报表 SaaS</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">FleetLedger 数据 → 合规证据链导出。按 Agent 数量订阅。</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.2vh;border-top:1px solid var(--border-subtle);padding-top:1.8vh;min-height:0">
        <span class="t-meta">LINE 03</span>
        <h3 style="font-weight:400;font-size:max(18px,1.45vw);line-height:1.15">端侧语音 SDK</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">零依赖听觉栈 + 全双工轮转。OEM / 设备厂按量授权。</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.2vh;border-top:2px solid var(--accent);padding-top:1.7vh;min-height:0">
        <span class="t-meta" style="color:var(--accent)">PRICING</span>
        <h3 style="font-weight:400;font-size:max(18px,1.45vw);line-height:1.15">定价哲学</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">开源内核建标准——付费点是强制层与证据链：「敢用」本身。</p>
      </div>
    </div>
  </div>
</section>''')

# ---------- P12 市场空间（S17 同心圆 · 示例标注） ----------
SECTIONS.append(f'''
<section class="slide" data-animate="system-diagram" data-layout="S17" data-slide-id="market">
  <div class="canvas-card">
    {CHROME.format(n=12)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Market · 结构示意（示例口径）</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">TAM / SAM / SOM，<br/>三层嵌套。</h2>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(12,1fr);gap:2.6vw;flex:1;align-items:center;margin-top:1vh;min-height:0">
      <div class="span-6" style="display:flex;align-items:center;justify-content:center;min-height:0">
        <svg viewBox="0 0 400 400" style="width:min(34vw,52vh);height:auto;overflow:visible" aria-hidden="true">
          <circle cx="200" cy="200" r="180" fill="none" stroke="var(--grey-2)" stroke-width="1.4"></circle>
          <circle cx="200" cy="200" r="124" fill="none" stroke="var(--grey-3)" stroke-width="1.4"></circle>
          <circle cx="200" cy="200" r="68" style="fill:var(--accent);stroke:none"></circle>
        </svg>
      </div>
      <div class="span-6" style="display:flex;flex-direction:column;gap:1.8vh">
        <div>
          <span class="t-cat">TAM（示例口径）</span>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6;margin-top:.6vh">Agent 基础设施软件——需替换为可辩护测算。</p>
        </div>
        <div>
          <span class="t-cat">SAM（示例口径）</span>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6;margin-top:.6vh">企业 Agent 治理与审计：MCP 网关 / 策略执行细分。</p>
        </div>
        <div>
          <span class="t-cat" style="color:var(--accent)">SOM（示例口径）</span>
          <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6;margin-top:.6vh">3 年可触达：私有化 + 报表 + SDK 三线合计。</p>
        </div>
      </div>
    </div>
    <div class="t-meta" style="margin-top:1.4vh;color:var(--text-helper)">本页为结构示意 · 数字待替换 · 正式投资人版将附测算模型</div>
  </div>
</section>''')

# ---------- P13 路线图（S02 纵向时间轴） ----------
ROADMAP = [
    ("Q1", "v1.0", "内核稳定：多 Agent 并发调度 + 首个企业试点（治理中间件 POC）", False),
    ("Q2", "SaaS", "审计报表 SaaS 内测 + 驱动市场：第三方 MCP 治理接入协议", False),
    ("Q3", "1-2", "端侧语音 SDK 在 1-2 款设备落地：Bin2Ambi / 空间音频进产品", False),
    ("Q4", "A 轮", "可复制的「治理 + 听觉」打包案例——A 轮叙事节点", True),
]
rnodes = "".join(
    f'''<div class="tl-node{' accent' if acc else ''}" style="padding:1.7vh 0">
      <div class="tl-axis" style="display:flex;justify-content:center;align-items:center"><span class="dot"></span></div>
      <span class="yr">{q}</span>
      <span class="multi">{m}</span>
      <p class="desc">{d}</p>
    </div>'''
    for q, m, d, acc in ROADMAP)
SECTIONS.append(f'''
<section class="slide" data-animate="progression" data-layout="S02" data-slide-id="roadmap">
  <div class="canvas-card">
    {CHROME.format(n=13)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1vh;padding-top:.6vh">
      <span class="t-cat">Roadmap · 12 Months</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:1;letter-spacing:-.03em">四季四步，走到 A 轮叙事节点。</h2>
    </div>
    <div class="timeline-v" style="margin-top:1.6vh">
      {rnodes}
    </div>
    <div class="kpi-row-4">
      <div class="kpi-cell"><div class="lbl">TEAM · NOW</div><div class="nb">1</div><div class="note">独立开发者 + AI 协作流水线</div></div>
      <div class="kpi-cell"><div class="lbl">HIRE · H1</div><div class="nb">+2</div><div class="note">内核 / 端侧</div></div>
      <div class="kpi-cell"><div class="lbl">HIRE · H2</div><div class="nb">+2</div><div class="note">合规 / BD</div></div>
      <div class="kpi-cell"><div class="lbl">TARGET · 12M</div><div class="nb">5<span class="unit">人</span></div><div class="note">招人计划与融资用途绑定</div></div>
    </div>
  </div>
</section>''')

# ---------- P14 融资方案（S06 KPI 塔 · 示例标注） ----------
USES = [
    ("cpu", "USE 01 · 端侧真机验证", "40", "设备矩阵 · 声学实验室 · 真机验收", "30vh", True),
    ("share-2", "USE 02 · 生态适配", "30", "MCP 生态 · 驱动市场", "23vh", False),
    ("shield-check", "USE 03 · 合规认证与试点", "20", "认证投入 · 首个企业试点", "16.5vh", False),
    ("life-buoy", "USE 04 · 运营", "10", "基础运营与合规开销", "12.5vh", False),
]
towers = "".join(
    f'''<div class="bar-tower">
      <div class="cap"><i data-lucide="{ico}"></i></div>
      <div class="body-block{' b-accent' if acc else ''}" style="min-height:{h};padding:1.4vh 1.2vw">
        <div class="lbl">{lbl}</div>
        <div class="nb" style="font-size:max(20px,2.4vw)">{num}<span class="unit">%</span></div>
        <div class="sub">{sub}</div>
      </div>
    </div>'''
    for ico, lbl, num, sub, h, acc in USES)
SECTIONS.append(f'''
<section class="slide" data-animate="measure-up" data-layout="S06" data-slide-id="the-ask">
  <div class="canvas-card">
    {CHROME.format(n=14)}
    <div style="display:flex;justify-content:space-between;align-items:end;gap:3vw;padding-top:1vh">
      <div data-anim="line" style="display:flex;flex-direction:column;gap:1vh">
        <span class="t-cat">The Ask · 天使轮（示例）</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">四成，押在端侧真机。</h2>
      </div>
      <div style="border:1px solid var(--border-subtle);padding:1.6vh 1.4vw;max-width:30ch">
        <div style="font-weight:300;font-size:max(18px,1.35vw);letter-spacing:-.01em">¥500 万 / 出让 10%<span style="font-size:.6em;color:var(--text-helper)">（示例，可调）</span></div>
        <p style="font-size:max(16px,.9vw);color:var(--text-secondary);line-height:1.55;margin-top:.6vh">里程碑对赌：12 个月内 v1.0 + 首个付费试点</p>
      </div>
    </div>
    <div class="bar-towers" style="margin-top:2vh">
      {towers}
    </div>
    <div class="t-meta" style="margin-top:1.6vh;color:var(--text-helper)">示例结构：金额与比例按正式 BP 测算更新 · 用途拆分合计 100%</div>
  </div>
</section>''')

# ---------- P15 团队与风险（收尾） ----------
SECTIONS.append(f'''
<section class="slide split" data-animate="split-statement" data-layout="SWISS-CLOSING-ASCII" data-slide-id="closing">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half b-accent" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between;position:relative;overflow:hidden">
        <canvas class="ascii-bg" aria-hidden="true"></canvas>
        <div class="chrome-min" style="margin-bottom:0;position:relative;z-index:1">
          <div class="l">{N:02d} / {N}</div><div class="r">CLOSING</div>
        </div>
        <div data-anim="manifesto" style="display:flex;flex-direction:column;gap:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em;margin-bottom:1.6vh">MANIFESTO</div>
          <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(5.4vw,9.6vh);line-height:.98;letter-spacing:-.025em;font-weight:200;color:#fff">模型负责想，<br/>laos 负责<br/>说<span style="font-style:italic;font-weight:300">「不」</span>。</h2>
          <div style="font-family:var(--sans),var(--sans-zh);font-size:max(14px,1vw);line-height:1.6;color:rgba(255,255,255,.82);font-weight:400;max-width:36ch;margin-top:1.4vh">创新融资 · 项目介绍 · v0.12.0 · 765 测试全绿</div>
        </div>
        <div data-anim="signature" style="display:flex;justify-content:space-between;align-items:end;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.62)">github.com/Yfredy/LAOS</div>
          <div class="t-meta" style="color:rgba(255,255,255,.62)">26.10.05</div>
        </div>
      </div>
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min"><div class="l">TEAM &amp; RISKS</div><div class="r">03 RULES</div></div>
        <ul class="takeaway-list" style="list-style:none;display:flex;flex-direction:column;gap:0;margin:0;padding:0">
          <li style="display:grid;grid-template-columns:auto 1fr;gap:1.8vw;align-items:start;padding:2.4vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4vw,7.2vh);line-height:.9;color:var(--text-primary)">01</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.7vw);line-height:1.2;letter-spacing:-.015em;color:var(--text-primary);margin-bottom:1vh">团队（真实呈现）</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">独立开发者：30 天 12 版本 / 765 测试 / 47 份调研的 AI 协作流水线，本身就是产品方法论证明。招人计划见路线图。</p></div>
          </li>
          <li style="display:grid;grid-template-columns:auto 1fr;gap:1.8vw;align-items:start;padding:2.4vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4vw,7.2vh);line-height:.9;color:var(--text-primary)">02</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.7vw);line-height:1.2;letter-spacing:-.015em;color:var(--text-primary);margin-bottom:1vh">风险与对策</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">标准竞争 → 深耕强制层与账本、标准中立；单人风险 → 首要融资用途即团队；长销售周期 → 先开发者后企业（开源漏斗）。</p></div>
          </li>
          <li style="display:grid;grid-template-columns:auto 1fr;gap:1.8vw;align-items:start;padding:2.4vh 0;border-top:1px solid var(--border-subtle);border-bottom:2px solid var(--accent)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4vw,7.2vh);line-height:.9;color:var(--accent)">03</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.7vw);line-height:1.2;letter-spacing:-.015em;color:var(--accent);margin-bottom:1vh">开源可尽调</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">github.com/Yfredy/LAOS —— 版本、测试、调研、拒绝清单，全部公开可查。</p></div>
          </li>
        </ul>
        <div class="t-meta" style="color:var(--text-helper);text-align:right">→ 完 · END OF FUNDING DECK</div>
      </div>
    </div>
  </div>
</section>''')

NOTES = [
    dict(id="cover", title="给 AI Agent 装上治理内核", section="开场", minutes=0.5,
         purpose="定调：laos 是治理内核，融资版开场",
         talk=["一句话定位：模型负责想，laos 负责说不", "角标数字先立信任：v0.12.0 / 30 天 12 版本 / 765 测试", "预告三道壁垒与融资用途"],
         transition="从定位直接进入「只记一页」的总览"),
    dict(id="one-slide", title="一页看懂", section="开场", minutes=1.0,
         purpose="如果只记住一页：问题-方案-进展",
         talk=["无 syscall 层的 tool call 四无：预算/审计/回滚/合规", "8 环闸门链一句话带过，细节在第 6 页", "进展锚点：15 驱动 / 纯 stdlib / 19,792 语料"],
         transition="总览抛出问题，下一页把问题拆成三根柱子"),
    dict(id="problem", title="痛点三柱", section="问题", minutes=1.2,
         purpose="把三条断层说具体，每柱一个场景",
         talk=["失控成本：一次 tool call 一次不可逆操作", "合规黑洞：EU AI Act / PIPL 声纹", "端侧碎片：每台设备重写一遍、无统一隐私闸", "强调应用层 try-catch 挡不住"],
         transition="痛已经在场，下一页回答为什么是现在"),
    dict(id="why-now", title="为什么是现在", section="时机", minutes=1.0,
         purpose="三浪叠加证明窗口期",
         talk=["MCP 事实标准给了统一切入点", "Agent 从聊天走向执行，差的是敢用", "监管落地：合规是预算充足的用户"],
         transition="窗口已开，下一页看产品怎么接住"),
    dict(id="product", title="产品：三层结构", section="产品", minutes=1.0,
         purpose="说清 laos 是什么、不是什么",
         talk=["三层各司其职：Agent 想 / 内核管 / 驱动动设备", "三件内核语义：syscall / 设备驱动 / 权限位", "零依赖承诺：纯 stdlib 进低端设备"],
         transition="架构里最值钱的是中间层，下一页展开第一道壁垒"),
    dict(id="gates", title="壁垒一：8 环闸门链", section="壁垒", minutes=1.5,
         purpose="全项目最核心的一页：强制 vs 建议",
         talk=["按 01-08 顺序走一遍八环", "FleetLedger 先扣账后派发，不可抵赖", "第 2 环即拒，驱动根本不被触达", "对照：guardrail 是建议，laos 是强制"],
         transition="第一道壁垒管调用，第二道管声音入口"),
    dict(id="hearing", title="壁垒二：端侧听觉栈", section="壁垒", minutes=1.0,
         purpose="六层全自研 + 端侧=隐私唯一安全区",
         talk=["六层从 VAD 到 ShoNet 复现", "全双工三件套一句话", "市面方案全依赖云端大模型", "响度校准锚点 −23.00 LUFS ±0.1 体现精度"],
         transition="第二道壁垒是能力，第三道是法条功课"),
    dict(id="compliance", title="壁垒三：合规先发", section="壁垒", minutes=1.0,
         purpose="法条功课 + 拒绝清单实证",
         talk=["EU AI Act / PIPL 声纹 / 录音四红线", "七个越界文件逐行分析一行不抄", "可审计是入场券不是加分项"],
         transition="三道壁垒合起来决定竞争位置，下一页看坐标系"),
    dict(id="landscape", title="竞争四象限", section="竞争", minutes=1.2,
         purpose="证明 L2 空位只有 laos",
         talk=["坐标系：L0-L3 × 建议-强制", "框架派/治理派/端侧派各缺什么", "Rutgers AIOS 互补不互竞", "结论：强制 × 端侧 × 账本三轴只在 laos 相交"],
         transition="位置唯一，接下来用真实数字证明执行力"),
    dict(id="traction", title="里程碑与进展", section="进展", minutes=1.2,
         purpose="全部真实数字建立工程信任",
         talk=["12 版本 / 765 测试 / 19,792 语料 / 3,724 仓库 / 4 项复现", "每版本 tag+Release+CHANGELOG 可查", "诚实呈现社区冷启动期", "数字全部可尽调"],
         transition="执行力有据，下一页讲怎么收钱"),
    dict(id="business", title="商业模式", section="商业", minutes=1.0,
         purpose="三条收入线 + 定价哲学",
         talk=["中间件 License / SaaS 订阅 / SDK 按量", "先开源建标准，卖的是敢用", "付费点是强制层与证据链"],
         transition="收入结构定了，下一页给市场空间的结构"),
    dict(id="market", title="市场空间（示例）", section="商业", minutes=0.8,
         purpose="给结构不给假数字",
         talk=["TAM/SAM/SOM 三层嵌套结构", "明确说明：示例口径，正式版附测算模型", "三线合计构成 SOM"],
         transition="空间讲完，转到 12 个月怎么走"),
    dict(id="roadmap", title="路线图 12 个月", section="财务", minutes=1.0,
         purpose="四季四步到 A 轮叙事",
         talk=["Q1 v1.0+试点 / Q2 SaaS+驱动市场 / Q3 设备落地 / Q4 打包案例", "团队 1→3→5 与融资用途绑定", "每季都有可验证交付物"],
         transition="路线讲完，最后把融资本身摆上桌"),
    dict(id="the-ask", title="融资方案（示例）", section="财务", minutes=1.2,
         purpose="用途拆分与对赌",
         talk=["天使轮示例：500 万 / 10%", "40% 端侧真机是最大头", "对赌：12 个月 v1.0 + 首个付费试点", "强调示例口径，以正式 BP 为准"],
         transition="金额之后，用团队与风险页收束"),
    dict(id="closing", title="团队与风险", section="收尾", minutes=0.8,
         purpose="真实呈现团队，风险给对策，留 repo",
         talk=["单人 + AI 流水线即方法论证明", "三大风险三大对策", "github.com/Yfredy/LAOS 欢迎尽调", "回扣开场：模型负责想，laos 负责说不"],
         transition="结束演讲，进入提问"),
]

src = SRC.read_text(encoding="utf-8")

# 1) 替换插入区
start = src.index("<!-- SLIDES_HERE")
end_marker = "<!-- 演讲备注：替换示例页时同步替换"
end = src.index(end_marker)
new_sections = ("<!-- laos · 创新融资 · 15 sections (Swiss locked mode S01-S22 + ASCII cover/closing) -->\n"
                + "\n".join(SECTIONS) + "\n\n")
src = src[:start] + new_sections + src[end:]

# 2) 替换 SPEAKER_NOTES
notes_js = "const SPEAKER_NOTES = [\n" + ",\n".join(
    "  {{ id: {id!r}, title: {title!r}, section: {section!r}, minutes: {minutes}, purpose: {purpose!r}, talk: {talk!r}, transition: {transition!r} }}".format(**n)
    for n in NOTES) + "\n];"
src = re.sub(r"const SPEAKER_NOTES = \[.*?\];", notes_js, src, count=1, flags=re.S)

# 3) 标题
src = re.sub(r"<title>.*?</title>", "<title>laos · Linux AgentOS — 创新融资项目介绍 · Funding Deck</title>", src, count=1)

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(src, encoding="utf-8")
print("written:", DST, len(src), "chars; sections:", len(SECTIONS))
