# -*- coding: utf-8 -*-
"""组装 guizang 瑞士风 laos 介绍 deck：注入 12 页 sections + SPEAKER_NOTES。"""
import re
from pathlib import Path

SRC = Path(r"C:\Users\yaoyue\.agents\skills\guizang-ppt-skill\assets\template-swiss.html")
DST = Path(r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\ppt\laos-intro-guizang.html")

CHROME = ('<header class="chrome-min"><div class="l">laos · Linux AgentOS · Field Note 01</div>'
          '<div class="r">SS · 26.10.05 · {n:02d} / 12</div></header>')

SECTIONS = []

# ---------- P1/S01 封面 ----------
SECTIONS.append(f'''
<section class="slide accent" data-animate="hero" data-layout="SWISS-COVER-ASCII" data-slide-id="cover">
  <div class="canvas-card">
    <canvas class="ascii-bg" aria-hidden="true"></canvas>
    {CHROME.format(n=1)}
    <div style="flex:1;padding:0;display:grid;grid-template-rows:auto 1fr auto;gap:2.6vh">
      <div data-anim="kicker" class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em">LINUX AGENTOS · FIELD NOTE 01</div>
      <h1 data-anim="title" style="align-self:center;font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(8.4vw,15vh);line-height:.96;letter-spacing:-.025em;color:#fff">给 AI Agent<br/>一座<span style="font-style:italic;font-weight:300">操作系统</span></h1>
      <div data-anim="bottom" style="display:grid;grid-template-rows:auto auto;gap:1.6vh;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh">
        <div data-anim="lead" class="lead" style="max-width:52ch;color:rgba(255,255,255,.86);font-weight:300">laos · Linux AgentOS v0.9.0 —— 用内核强制原语给 Agent 划出能力边界，而不是靠提示词恳求。主库 353 + 隔离区 350 = 703 项测试全绿。</div>
        <div style="display:flex;justify-content:space-between;align-items:end">
          <div class="t-meta" style="color:rgba(255,255,255,.6)">GitHub · Yfredy/LAOS · 2026-10</div>
          <div class="t-meta" style="color:rgba(255,255,255,.6)">→ swipe / arrow keys</div>
        </div>
      </div>
    </div>
  </div>
</section>''')

# ---------- P10/S10 问题 ----------
SECTIONS.append(f'''
<section class="slide" data-animate="matrix-statement" data-layout="S10" data-slide-id="problem">
  <div class="canvas-card">
    {CHROME.format(n=2)}
    <span class="ring-mat" style="left:5vw;bottom:5vh;width:18vw;height:18vw"></span>
    <h1 class="h-statement" style="font-size:min(6vw,10.5vh)">Agent 拿着 root 裸奔。<br/>提示词是<span style="font-style:italic;font-weight:300">恳求</span>，<br/>不是强制。</h1>
    <p style="font-family:var(--sans),var(--sans-zh);font-size:max(18px,1.1vw);line-height:1.7;color:var(--text-secondary);max-width:56ch;margin-top:3vh;font-weight:300">一条 rm -rf 就能删光家目录；一个恶意 MCP 工具就能把剪贴板与通知发出去。缺的不是更聪明的模型，是操作系统：能力、调度、审计、记账、隔离。</p>
    <span class="stmt-anchor">— The Problem · 02</span>
  </div>
</section>''')

# ---------- P12/S12 命题 ----------
SECTIONS.append(f'''
<section class="slide" data-animate="manifesto" data-layout="S12" data-slide-id="thesis">
  <div class="canvas-card">
    {CHROME.format(n=3)}
    <div class="manifesto-top" style="display:grid;grid-template-columns:1.2fr .8fr;gap:4vw;flex:1;align-items:start;padding-top:2vh">
      <div>
        <span class="t-cat">The Thesis</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(5.2vw,9.2vh);line-height:1.02;letter-spacing:-.03em;margin-top:1.6vh">Linux kernel<br/>+ Agent + MCP<br/>= <span style="color:var(--accent)">Linux AgentOS</span></h2>
      </div>
      <div style="align-items:flex-start;padding-top:1.2vw">
        <p style="font-family:var(--sans),var(--sans-zh);font-size:max(18px,1.05vw);line-height:1.75;color:var(--text-secondary);font-weight:300">不改内核一行代码：复用 namespace（隔离视图）、cgroup（资源上限）、seccomp BPF（系统调用白名单）、Landlock（路径沙箱）。laosd 是薄内核，只做语义层。</p>
        <ul class="meta-list" style="margin-top:2.4vh">
          <li>0 KERNEL PATCHES</li><li>4 MANDATORY PRIMITIVES</li><li>1 THIN KERNEL</li>
        </ul>
      </div>
    </div>
    <div class="ink-banner-full" style="margin:4vh -5vw -4.4vh;background:var(--ink);padding:3.6vh 5vw;display:flex;align-items:center;justify-content:space-between;gap:2vw">
      <div style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(3vw,5.4vh);letter-spacing:-.02em;color:#fff">能力边界写在<span style="font-style:italic;font-weight:300">内核</span>里，不写在提示词里。</div>
      <div style="display:flex;gap:2vw;color:rgba(255,255,255,.72)">
        <i data-lucide="shield-check" style="width:2.4vw;height:2.4vw"></i>
        <i data-lucide="lock" style="width:2.4vw;height:2.4vw"></i>
        <i data-lucide="cpu" style="width:2.4vw;height:2.4vw"></i>
        <i data-lucide="file-lock-2" style="width:2.4vw;height:2.4vw"></i>
      </div>
    </div>
  </div>
</section>''')

# ---------- P8/S08 类比 ----------
SECTIONS.append(f'''
<section class="slide" data-animate="duo-mirror" data-layout="S08" data-slide-id="analogy">
  <div class="canvas-card">
    {CHROME.format(n=4)}
    <div style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">One Mapping</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">Linux 的词表，<br/>Agent 的语义。</h2>
    </div>
    <div class="duo-compare" style="flex:1;margin-top:2vh">
      <div class="duo-half">
        <span class="t-cat">Linux</span>
        <div style="display:flex;flex-direction:column;gap:1.8vh;margin-top:2vh">
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">进程</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">PID · 调度 · 生命周期</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">系统调用</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">open / read / fork …</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">设备驱动</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">声卡 · 屏幕 · 传感器</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">insmod</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">按需装载内核模块</p></div>
        </div>
      </div>
      <span class="vrule"></span>
      <div class="duo-half">
        <span class="t-cat" style="color:var(--accent)">laos</span>
        <div style="display:flex;flex-direction:column;gap:1.8vh;margin-top:2vh">
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">Agent</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">PCB · 能力集 · 预算</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">MCP tool call</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">JSON-RPC，每次过闸</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">MCP Server</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">drv_mic · drv_ear · drv_screen …</p></div>
          <div><h3 style="font-weight:400;font-size:max(19px,1.5vw)">load_driver</h3><p style="font-size:max(16px,.95vw);color:var(--text-secondary)">外挂任意 MCP 服务器为驱动</p></div>
        </div>
      </div>
    </div>
  </div>
</section>''')

# ---------- P11/S11 闸门链 ----------
GATES = [("01","能力表"),("02","task_scope"),("03","schema"),("04","预算·记账"),
         ("05","Jev 预审"),("06","确认横幅"),("07","审计·派发")]
nodes = "".join(
    f'<div class="tl-h-node"><span class="num">{n}</span><span class="dot"></span><span class="lbl">{l}</span></div>'
    for n, l in GATES)
SECTIONS.append(f'''
<section class="slide" data-animate="timeline-walk" data-layout="S11" data-slide-id="gates">
  <div class="canvas-card">
    {CHROME.format(n=5)}
    <div style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">The Syscall Gate Chain</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">每一次工具调用<br/>都过七道闸。</h2>
      <p style="font-size:max(18px,1.05vw);color:var(--text-secondary);max-width:58ch;line-height:1.7;font-weight:300">task_scope 收窄到路径前缀、pkg: 应用白名单与 time: 时间窗；EDQUOT 预算与 FleetLedger 给不可逆操作计价；事后可完整回放「谁在何时用掉了什么权限」。</p>
    </div>
    <div class="timeline-h" style="margin-top:auto;margin-bottom:6vh">
      <span class="tl-h-axis"></span>
      {nodes}
    </div>
  </div>
</section>''')

# ---------- P13/S13 强制层 ----------
SECTIONS.append(f'''
<section class="slide" data-animate="three-forces" data-layout="S13" data-slide-id="enforcement">
  <div class="canvas-card">
    {CHROME.format(n=6)}
    <div class="three-forces" style="display:grid;grid-template-columns:5fr 11fr;gap:3vw;flex:1;align-items:stretch;padding-top:1vh">
      <div class="hero-ink-col" style="background:var(--ink);padding:3.6vh 2.4vw;position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between">
        <span class="dot-mat" style="right:-6vw;bottom:-6vh;width:20vw;height:20vw;opacity:.5"></span>
        <div style="position:relative;z-index:1">
          <span class="t-cat" style="color:rgba(255,255,255,.72)">Enforcement</span>
          <h2 style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1.04;letter-spacing:-.02em;color:#fff;margin-top:1.4vh">不改内核，<br/>复用 Linux。</h2>
        </div>
        <div class="t-meta" style="color:rgba(255,255,255,.6);position:relative;z-index:1">强制原语 × 3</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:2vh;justify-content:center">
        <article class="card-fill sub-card" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;align-items:center;padding:2.4vh 2vw">
          <span class="force-num" style="font-weight:200;font-size:5.2vw;color:var(--accent);line-height:.9">01</span>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">seccomp BPF</h4><p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">进程级系统调用白名单——真拦截，不是君子协定。</p></div>
        </article>
        <article class="card-fill sub-card" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;align-items:center;padding:2.4vh 2vw">
          <span class="force-num" style="font-weight:200;font-size:5.2vw;color:var(--accent);line-height:.9">02</span>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">cgroup v2</h4><p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">驱动子进程 CPU / 内存上限——驱动失控不拖垮宿主。</p></div>
        </article>
        <article class="card-fill sub-card" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;align-items:center;padding:2.4vh 2vw">
          <span class="force-num" style="font-weight:200;font-size:5.2vw;color:var(--accent);line-height:.9">03</span>
          <div><h4 style="font-weight:500;font-size:max(18px,1.3vw)">eBPF profiler + CoW</h4><p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.6">行为画像与执行隔离，给 Agent 建「档案」。</p></div>
        </article>
      </div>
    </div>
  </div>
</section>''')

# ---------- P4/S04 驱动 ----------
DRIVERS = [
    ("mic", "01", "drv_mic", "麦克风 · 录音只由显式 syscall 触发"),
    ("ear", "02", "drv_ear", "本地 ASR + 发音韵律评估"),
    ("monitor-smartphone", "03", "drv_screen", "adb 屏幕操控 · pkg: 应用白名单"),
    ("bell", "04", "drv_notify / comms", "通知与短信 · 敏感数据可信闸"),
    ("cpu", "05", "drv_npu / events", "端侧感知事件环形缓冲"),
    ("plug", "06", "load_driver", "一行把任意 MCP 服务器 insmod 成驱动"),
]
cells = "".join(
    f'<div class="cell"><i data-lucide="{ico}"></i><span class="cell-num">{n}</span><h4>{t}</h4><p>{d}</p></div>'
    for ico, n, t, d in DRIVERS)
SECTIONS.append(f'''
<section class="slide" data-animate="six-cells" data-layout="S04" data-slide-id="drivers">
  <div class="canvas-card">
    {CHROME.format(n=7)}
    <div style="display:flex;flex-direction:column;gap:1.2vh;padding-top:1vh">
      <span class="t-cat">Drivers as Devices</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">MCP Server 就是设备驱动。</h2>
    </div>
    <div class="cell-6" style="flex:1;margin-top:3vh">
      {cells}
    </div>
  </div>
</section>''')

# ---------- P2/S02 四段漏斗 ----------
FUNNEL = [
    ("Stage 01", "µW", "常驻检测 —— PCEN/VAD 低功耗常开，功耗预算 µW 级"),
    ("Stage 02", "15s", "触发捕获 —— 环形缓冲 + 私有唤醒词 DTW 模板（纯 JSON 非声纹）"),
    ("Stage 03", "0云", "即时蒸馏 —— SenseVoice 全本地 ASR + 情感，零上云"),
    ("Stage 04", "6h", "即焚 —— 默认 6 小时留存，LAOS_REC=0 全局禁录"),
]
fnodes = "".join(
    f'''<div class="tl-node"><div class="tl-axis"><span class="dot"></span></div>
      <div class="tl-body"><span class="yr">{s}</span><span class="multi">{m}<small></small></span><p class="desc">{d}</p></div></div>'''
    for s, m, d in FUNNEL)
SECTIONS.append(f'''
<section class="slide" data-animate="timeline-vertical" data-layout="S02" data-slide-id="funnel">
  <div class="canvas-card">
    {CHROME.format(n=8)}
    <div style="display:flex;flex-direction:column;gap:1vh;padding-top:.6vh">
      <span class="t-cat">Always-On Hearing · Four Stages</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:1;letter-spacing:-.03em">听觉管线：常开但克制。</h2>
    </div>
    <div class="timeline-v" style="flex:1;margin-top:2vh">
      {fnodes}
    </div>
  </div>
</section>''')

# ---------- P18/S18 Jev ----------
SECTIONS.append(f'''
<section class="slide" data-animate="why-now" data-layout="S18" data-slide-id="jev">
  <div class="canvas-card">
    {CHROME.format(n=9)}
    <div style="display:flex;flex-direction:column;gap:1vh;padding-top:.6vh">
      <span class="t-cat">Jev Judgment Layer</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">快问快答判断层，校准先行。</h2>
    </div>
    <div class="why-now-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:2.6vw;flex:1;margin-top:3vh;align-content:stretch">
      <div class="why-col" style="display:flex;flex-direction:column;gap:1.4vh">
        <span class="t-cat">三判型</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw)">Noul · Choice · Score</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">是非二判 / 2-255 选项 / 2-10 级打分——把决策压成结构化快问快答。</p>
        <span class="why-num-bottom" style="font-weight:200;font-size:7vw;line-height:.9;margin-top:auto">3<span style="font-size:max(16px,1vw);font-weight:500"> 型</span></span>
      </div>
      <div class="why-col" style="display:flex;flex-direction:column;gap:1.4vh">
        <span class="t-cat">四闸门</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw)">预审 · 记忆 · 压缩 · 技能</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">高危操作预审、记忆入库存过滤、上下文压缩选择、技能质量闸——全部可插拔后端。</p>
        <span class="why-num-bottom" style="font-weight:200;font-size:7vw;line-height:.9;margin-top:auto">4<span style="font-size:max(16px,1vw);font-weight:500"> 门</span></span>
      </div>
      <div class="why-col" style="display:flex;flex-direction:column;gap:1.4vh">
        <span class="t-cat">校准教训</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw)">rule 后端不够准</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">标注集实测 accuracy 0.519、高置信桶错误率 33%——AUTOGATE 禁配 rule 后端，自动化前先跑校准。</p>
        <span class="why-num-bottom" style="font-weight:200;font-size:7vw;line-height:.9;margin-top:auto;color:var(--accent)">0.519</span>
      </div>
    </div>
  </div>
</section>''')

# ---------- P6/S06 语料 KPI ----------
TOWERS = [
    ("book-open", "19,792", "双会议全量论文（Interspeech 5,507 + ICASSP 14,285）", "36vh"),
    ("layout-grid", "9,908", "多顶会主题切片（35 venue · 29 有产出）", "18vh"),
    ("github", "3,724", "GitHub 音频×AI×Agent 仓库普查", "7vh"),
    ("list-checks", "76", "采纳总纲映射（落地33 / 推荐23 / 不做20）", "6vh"),
]
towers = "".join(
    f'''<div class="tower-col" style="display:flex;flex-direction:column;align-items:center;gap:1vh;justify-content:flex-end">
      <i data-lucide="{ico}"></i><span class="num-mega">{num}</span><span class="lbl">{lbl}</span>
      <div class="bar-tower" style="--h:{h}"></div></div>'''
    for ico, num, lbl, h in TOWERS)
SECTIONS.append(f'''
<section class="slide" data-animate="tower-grow" data-layout="S06" data-slide-id="corpus">
  <div class="canvas-card">
    {CHROME.format(n=10)}
    <div style="display:flex;justify-content:space-between;align-items:end;padding-top:1vh">
      <div style="display:flex;flex-direction:column;gap:1vh">
        <span class="t-cat">Evidence-Based Design</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">设计不拍脑袋。</h2>
      </div>
      <p style="font-size:max(16px,.92vw);color:var(--text-helper);max-width:30ch;text-align:right">每个模块背后是可溯源的<br/>论文与开源证据链</p>
    </div>
    <div class="kpi-tower-row" style="display:grid;grid-template-columns:repeat(4,1fr);gap:2vw;flex:1;margin-top:2vh;align-items:end">
      {towers}
    </div>
  </div>
</section>''')

# ---------- P16/S16 复现区 ----------
REPRO = [
    ("BS.1770-4 响度计量", "R128 校准点 −23.00 LUFS ±0.1", False),
    ("FxLMS 主动降噪", "发动机阶次收敛后 >20dB", False),
    ("头部朝向论文全管线", "ISM+STFT 相位+BiGRU，冒烟 56.5°", False),
    ("PhaseCoder 麦位编码", "与官方 JAX 源码逐行对齐", False),
    ("Pipecat 帧管道", "打断作废排队帧，系统帧穿管", True),
    ("unique_lock 语义", "RAII · defer · try_lock 七测试", False),
]
briefs = "".join(
    f'''<div class="brief-card{' is-accent' if acc else ''}" style="display:flex;flex-direction:column;justify-content:space-between;padding:2.2vh 1.6vw;min-height:16vh">
      <div style="font-weight:500;font-size:max(18px,1.25vw);letter-spacing:-.01em">{t}</div>
      <div style="font-family:var(--mono);font-size:max(14px,.85vw);opacity:.75;text-align:right">{d}</div></div>'''
    for t, d, acc in REPRO)
SECTIONS.append(f'''
<section class="slide" data-animate="field-notes" data-layout="S16" data-slide-id="repro">
  <div class="canvas-card">
    {CHROME.format(n=11)}
    <div style="display:flex;flex-direction:column;gap:1vh;padding-top:1vh">
      <span class="t-cat">Repro Zone · Six Sources</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">能复现的，全部复现。</h2>
      <p style="font-size:max(18px,1.05vw);color:var(--text-secondary);max-width:60ch;line-height:1.7;font-weight:300">六来源隔离复现区 71 项测试：TDD、零新依赖、论文数字不作断言、偏差全部记档。</p>
    </div>
    <div class="brief-grid" style="display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:1.6vw;flex:1;margin-top:2.4vh">
      {briefs}
    </div>
  </div>
</section>''')

# ---------- P9/S09 收尾 ----------
SECTIONS.append('''
<section class="slide split" data-animate="split-statement" data-layout="SWISS-CLOSING-ASCII" data-slide-id="closing">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half b-accent" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between;position:relative;overflow:hidden">
        <canvas class="ascii-bg" aria-hidden="true"></canvas>
        <div class="chrome-min" style="margin-bottom:0;position:relative;z-index:1">
          <div class="l">12 / 12</div><div class="r">CLOSING</div>
        </div>
        <div data-anim="manifesto" style="display:flex;flex-direction:column;gap:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em;margin-bottom:1.6vh">MANIFESTO</div>
          <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(7vw,12.5vh);line-height:.96;letter-spacing:-.025em;font-weight:200;color:#fff">v0.1 → v0.9，<br/>每一步都<span style="font-style:italic;font-weight:300">可追溯</span>。</h2>
          <div style="font-family:var(--sans),var(--sans-zh);font-size:max(14px,1vw);line-height:1.6;color:rgba(255,255,255,.82);font-weight:400;max-width:36ch;margin-top:1.4vh">语义化版本 + Keep a Changelog + GitHub Release 页——一个完整需求波次 = 一次 MINOR。</div>
        </div>
        <div data-anim="signature" style="display:flex;justify-content:space-between;align-items:end;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.62)">Yfredy/LAOS</div>
          <div class="t-meta" style="color:rgba(255,255,255,.62)">26.10.05</div>
        </div>
      </div>
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min"><div class="l">NEXT</div><div class="r">03 ITEMS</div></div>
        <div data-anim="rules" style="display:flex;flex-direction:column;gap:0">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">01</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1vh">drv_screen 多轮真机验收</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">手机五层能力的第三层：通知 / 短信 / 传感器全链用例。</p></div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">02</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1vh">外挂驱动 PoC</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">load_driver 把 mobile-mcp 直接 insmod 成内核驱动（遥测必关）。</p></div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle);border-bottom:2px solid var(--accent)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--accent)">03</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1vh">bs1770 响度合入主库</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">录音留档的 LUFS 口径 + Pipecat 帧管道进入 laos 语音路径。</p></div>
          </div>
        </div>
        <div class="t-meta" style="color:var(--text-helper);text-align:right">→ 完 · END OF FIELD NOTE</div>
      </div>
    </div>
  </div>
</section>''')

NOTES = [
    dict(id="cover", title="给 AI Agent 一座操作系统", section="开场", minutes=0.5,
         purpose="建立反差：Agent 很强但没有操作系统",
         talk=["一条 rm -rf 的例子开场", "提示词是恳求不是强制", "预告：闸门链 / 驱动 / 证据链"]),
    dict(id="problem", title="Agent 拿着 root 裸奔", section="问题", minutes=0.8,
         purpose="把风险说具体",
         talk=["删库与隐私外发两个场景", "缺的是 OS 五件套：能力/调度/审计/记账/隔离"]),
    dict(id="thesis", title="Linux AgentOS 命题", section="命题", minutes=1.0,
         purpose="给出公式与不动内核的立场",
         talk=["kernel + Agent + MCP", "四个强制原语点名", "laosd 只做薄内核语义层"]),
    dict(id="analogy", title="Linux ↔ laos 词表", section="架构", minutes=1.0,
         purpose="用熟悉概念映射新概念",
         talk=["进程→Agent，syscall→tool call", "驱动→MCP Server", "insmod→load_driver"]),
    dict(id="gates", title="syscall 七道闸", section="核心", minutes=1.5,
         purpose="全项目最核心的一页",
         talk=["按 01-07 顺序走一遍", "pkg:/time: 收窄到最小权限", "审计可回放"]),
    dict(id="enforcement", title="强制层三件套", section="架构", minutes=1.0,
         purpose="证明'强制'是真拦截",
         talk=["seccomp/cgroup/eBPF 各一句", "不改内核是卖点"]),
    dict(id="drivers", title="驱动即设备", section="架构", minutes=1.0,
         purpose="展示设备面与外挂路线",
         talk=["六个内建驱动快速过", "load_driver 外挂任意 MCP"]),
    dict(id="funnel", title="听觉四段漏斗", section="听觉", minutes=1.2,
         purpose="展示最激进的常开能力如何克制",
         talk=["µW→15s→0云→6h 四个锚点数", "红线三件套"]),
    dict(id="jev", title="Jev 判断层", section="判断", minutes=1.0,
         purpose="展示语义闸门与诚实校准",
         talk=["三判型四闸门", "0.519 的教训：校准先于自动化"]),
    dict(id="corpus", title="证据链", section="研究", minutes=0.8,
         purpose="设计不是拍脑袋",
         talk=["四个数字念一遍", "全部可溯源到 corpus/"]),
    dict(id="repro", title="复现区", section="研究", minutes=0.8,
         purpose="展示工程纪律",
         talk=["六来源 71 测试", "论文数字不作断言"]),
    dict(id="closing", title="版本治理与路线", section="收尾", minutes=0.6,
         purpose="给出可信的收束与下一步",
         talk=["v0.1→v0.9 可追溯", "三个 Next 项目"]),
]

src = SRC.read_text(encoding="utf-8")

# 1) 替换插入区：SLIDES_HERE 注释起到最后一个示例 section 结束
start = src.index("<!-- SLIDES_HERE")
end_marker = "<!-- 演讲备注：替换示例页时同步替换"
end = src.index(end_marker)
new_sections = "<!-- laos · Linux AgentOS · 12 sections (Swiss locked mode S01-S22) -->\n" + "\n".join(SECTIONS) + "\n\n"
src = src[:start] + new_sections + src[end:]

# 2) 替换 SPEAKER_NOTES
notes_js = "const SPEAKER_NOTES = [\n" + ",\n".join(
    "  {{ id: {id!r}, title: {title!r}, section: {section!r}, minutes: {minutes}, purpose: {purpose!r}, talk: {talk!r} }}".format(**n)
    for n in NOTES) + "\n];"
src = re.sub(r"const SPEAKER_NOTES = \[.*?\];", notes_js, src, count=1, flags=re.S)

# 3) 标题
src = re.sub(r"<title>.*?</title>", "<title>laos · Linux AgentOS — Field Note 01</title>", src, count=1)

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(src, encoding="utf-8")
print("written:", DST, len(src), "chars; sections:", len(SECTIONS))
