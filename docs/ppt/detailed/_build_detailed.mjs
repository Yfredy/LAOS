// 组装 guizang 瑞士风 laos 详细技术深潜 deck：19 页 sections + SPEAKER_NOTES。
// 内容唯一来源：docs/ppt/laos-detailed-outline.md（v0.12.0 · 2026-10-05），不虚构数字。
// 版式：Swiss locked mode S01-S22 + SWISS-COVER-ASCII / SWISS-CLOSING-ASCII。
import { readFileSync, writeFileSync } from 'node:fs';

const SRC = 'C:/Users/yaoyue/.agents/skills/guizang-ppt-skill/assets/template-swiss.html';
const DST = 'C:/Users/yaoyue/CodeBuddy/Claw/laos/docs/ppt/detailed/laos-detailed-guizang.html';

const N_TOTAL = 19;
const chrome = (n) =>
  `<header class="chrome-min"><div class="l">laos · Linux AgentOS · 详细技术深潜</div>` +
  `<div class="r">SS · 26.10.05 · ${String(n).padStart(2, '0')} / ${N_TOTAL}</div></header>`;

const S = [];

// ============ P1 · A1 封面 · SWISS-COVER-ASCII ============
S.push(`
<section class="slide accent" data-animate="hero" data-layout="SWISS-COVER-ASCII" data-slide-id="cover">
  <div class="canvas-card">
    <canvas class="ascii-bg" aria-hidden="true"></canvas>
    ${chrome(1)}
    <div style="flex:1;padding:0;display:grid;grid-template-rows:auto 1fr auto;gap:2.6vh">
      <div data-anim="kicker" class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em">LINUX AGENTOS · TECHNICAL DEEP DIVE</div>
      <h1 data-anim="title" style="align-self:center;font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(7.4vw,13.4vh);line-height:.98;letter-spacing:-.025em;color:#fff">把 Linux 变成<br/>Agent 的<span style="font-style:italic;font-weight:300">操作系统</span></h1>
      <div data-anim="bottom" style="display:grid;grid-template-rows:auto auto;gap:1.6vh;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh">
        <div data-anim="lead" class="lead" style="max-width:58ch;color:rgba(255,255,255,.86);font-weight:300">详细技术深潜——Linux AgentOS = Linux kernel + Agent + MCP。面向 AI Agent 的用户态操作系统：15 个驱动 · 8 环 syscall 闸门 · 765 项测试全绿。</div>
        <div style="display:flex;justify-content:space-between;align-items:end">
          <div class="t-meta" style="color:rgba(255,255,255,.6)">v0.12.0 · 2026-10-05 · github.com/Yfredy/LAOS</div>
          <div class="t-meta" style="color:rgba(255,255,255,.6)">→ swipe / arrow keys</div>
        </div>
      </div>
    </div>
  </div>
</section>`);

// ============ P2 · A2 命题 · S12 ============
const PRIMS = [
  ['01', 'namespace', '隔离'],
  ['02', 'cgroup', '配额'],
  ['03', 'seccomp-BPF', '系统调用过滤'],
  ['04', 'landlock', '文件沙箱'],
];
const primRows = PRIMS.map(([n, name, d]) =>
  `<div style="display:grid;grid-template-columns:2.4em 1fr auto;gap:1vw;align-items:baseline;padding:1.3vh 0;border-top:1px solid var(--border-subtle)">
      <span class="t-meta">${n}</span>
      <span style="font-family:var(--mono);font-weight:500;font-size:max(16px,1.05vw);letter-spacing:-.01em">${name}</span>
      <span style="font-size:max(15px,.95vw);color:var(--text-secondary)">${d}</span></div>`).join('');
S.push(`
<section class="slide" data-animate="manifesto" data-layout="S12" data-slide-id="thesis">
  <div class="canvas-card">
    ${chrome(2)}
    <div class="manifesto-top" style="display:grid;grid-template-columns:1.15fr .85fr;gap:4vw;flex:1;align-items:start;padding-top:2vh;min-height:0">
      <div>
        <span class="t-cat">The Thesis · 命题</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(5vw,9vh);line-height:1.04;letter-spacing:-.03em;margin-top:1.8vh">Linux kernel<br/>+ Agent + MCP<br/>= <span style="color:var(--accent)">Linux AgentOS</span></h2>
        <p style="font-size:max(16px,1vw);color:var(--text-helper);margin-top:3.6vh;font-weight:400">不改一行内核代码，把 Linux 变成 Agent 的操作系统。</p>
      </div>
      <div style="padding-top:1.2vw">
        <span class="t-cat">四件内核遗产 · Reused As-Is</span>
        <div style="display:flex;flex-direction:column;margin-top:1.6vh;border-bottom:1px solid var(--border-subtle)">${primRows}</div>
      </div>
    </div>
    <div class="ink-banner-full" style="margin:4vh -5vw -4.4vh;background:var(--ink);padding:3.4vh 5vw;display:flex;align-items:center;justify-content:space-between;gap:3vw">
      <div style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(2.5vw,4.4vh);line-height:1.3;letter-spacing:-.02em;color:#fff">Agent 时代的「内核」不是重写调度器，<br/>是给工具调用装上 <span style="font-style:italic;font-weight:300">syscall 语义</span>。</div>
      <div style="display:flex;gap:2vw;color:rgba(255,255,255,.72)">
        <i data-lucide="shield-check" style="width:2.2vw;height:2.2vw"></i>
        <i data-lucide="lock" style="width:2.2vw;height:2.2vw"></i>
        <i data-lucide="cpu" style="width:2.2vw;height:2.2vw"></i>
        <i data-lucide="file-lock-2" style="width:2.2vw;height:2.2vw"></i>
      </div>
    </div>
  </div>
</section>`);

// ============ P3 · A2 映射表 · S08 ============
const duoRows = (items) => items.map(([n, term]) =>
  `<div style="display:grid;grid-template-columns:2.2em 1fr;gap:1vw;align-items:baseline;padding:2.9vh 0;border-top:1px solid var(--border-subtle)">
              <span class="t-meta">${n}</span>
              <span style="font-weight:300;font-size:max(22px,1.9vw);letter-spacing:-.015em;line-height:1.1">${term}</span></div>`).join('');
S.push(`
<section class="slide" data-animate="duo-mirror" data-layout="S08" data-slide-id="mapping">
  <div class="canvas-card">
    ${chrome(3)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:.6vh">
      <span class="t-cat">One Mapping · 词表映射</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(5vw,8.8vh);line-height:1;letter-spacing:-.03em">Linux 的词表，<br/>Agent 的语义。</h2>
    </div>
    <div class="duo-compare" style="flex:1;margin-top:4.8vh;margin-bottom:2.6vh" data-anim="up">
      <div class="col">
        <span class="col-tag"><span class="num">LX</span>LINUX</span>
        <div style="display:flex;flex-direction:column;margin-top:2vh;border-bottom:1px solid var(--border-subtle)">${duoRows([['01', '设备驱动'], ['02', '系统调用'], ['03', '内核'], ['04', '权限位']])}</div>
      </div>
      <span class="vrule"></span>
      <div class="col accent">
        <span class="col-tag"><span class="num">LA</span>LAOS</span>
        <div style="display:flex;flex-direction:column;margin-top:2vh;border-bottom:1px solid var(--border-subtle)">${duoRows([['01', 'MCP Server'], ['02', 'tool call'], ['03', 'laosd · 薄内核'], ['04', '能力表 · caps']])}</div>
      </div>
    </div>
  </div>
</section>`);

// ============ P4 · A3 坐标 · S09 ============
S.push(`
<section class="slide" data-animate="statement" data-layout="S09" data-slide-id="landscape">
  <div class="canvas-card">
    ${chrome(4)}
    <span class="dot-mat" style="position:absolute;right:0;top:0;width:30vw;height:30vw"></span>
    <div style="flex:1;padding:0 0 2.6vh;display:grid;grid-template-rows:1fr auto auto;gap:3vh;min-height:0;position:relative;z-index:1">
      <div data-anim="line" style="display:flex;flex-direction:column;gap:2.4vh;justify-content:center">
        <span class="t-cat">Landscape · 定位坐标</span>
        <h1 style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(5vw,8.8vh);line-height:1.06;letter-spacing:-.03em">同一句「AgentOS」，<br/>市面上至少 <span style="color:var(--accent)">8</span> 种东西。</h1>
        <p style="font-size:max(18px,1.05vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:1.6vh">多数是框架 / 壳；laos 是治理内核——能力 · 预算 · 审计 · 判断，四件事在派发之前完成。<span style="color:var(--text-helper)">来源：docs/research/agentos-landscape-2026-08.md</span></p>
      </div>
      <div data-anim="up" style="display:grid;grid-template-columns:repeat(4,1fr);gap:1.2vw">
        <div style="border-top:1px solid var(--border-subtle);padding-top:1.6vh;display:flex;flex-direction:column;gap:.8vh">
          <span style="font-family:var(--mono);font-weight:200;font-size:min(3vw,5.4vh);line-height:1">L0</span>
          <span style="font-size:max(16px,1vw);font-weight:400">约定层</span>
        </div>
        <div style="border-top:1px solid var(--border-subtle);padding-top:1.6vh;display:flex;flex-direction:column;gap:.8vh">
          <span style="font-family:var(--mono);font-weight:200;font-size:min(3vw,5.4vh);line-height:1;color:var(--text-helper)">L1</span>
          <span style="font-size:max(16px,1vw);font-weight:400;color:var(--text-helper)">·</span>
        </div>
        <div style="border-top:2px solid var(--accent);padding-top:1.6vh;display:flex;flex-direction:column;gap:.8vh">
          <span style="font-family:var(--mono);font-weight:200;font-size:min(3vw,5.4vh);line-height:1;color:var(--accent)">L2</span>
          <span style="font-size:max(16px,1vw);font-weight:500">用户态强制层 · laos</span>
        </div>
        <div style="border-top:1px solid var(--border-subtle);padding-top:1.6vh;display:flex;flex-direction:column;gap:.8vh">
          <span style="font-family:var(--mono);font-weight:200;font-size:min(3vw,5.4vh);line-height:1">L3</span>
          <span style="font-size:max(16px,1vw);font-weight:400">libOS 层</span>
        </div>
      </div>
      <div class="t-meta">SPECTRUM · 强制力 L0 → L3 · LAOS 落位 L2</div>
    </div>
  </div>
</section>`);

// ============ P5 · B1 架构 · S17 ============
S.push(`
<section class="slide" data-animate="system-diagram" data-layout="S17" data-slide-id="arch">
  <div class="canvas-card">
    ${chrome(5)}
    <div style="flex:1;padding:0 0 2.6vh;display:grid;grid-template-columns:5fr 6fr;gap:4vw;min-height:0">
      <div data-anim="line" style="display:flex;flex-direction:column;gap:2vh">
        <span class="t-cat">Architecture · 总体架构</span>
        <h2 class="h-xl" style="font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1;letter-spacing:-.03em">三层架构，<br/>零依赖内核。</h2>
        <p style="font-size:max(18px,1vw);color:var(--text-secondary);line-height:1.7;font-weight:300;max-width:44ch;margin-top:2vh">自上而下：Agent（brain / agent）→ laos 内核（kernel.py 调度 + syscall 闸门链）→ 驱动子进程（15 个 drv_*，重依赖隔离）→ Linux / MCP / 外设。</p>
        <div style="display:flex;flex-direction:column;margin-top:.6vh;border-bottom:1px solid var(--border-subtle)">
          <div style="display:grid;grid-template-columns:2.4em 1fr;gap:1vw;padding:1.4vh 0;border-top:1px solid var(--border-subtle)">
            <span class="t-meta">01</span>
            <div><span style="font-weight:500;font-size:max(16px,1.05vw)">laos 主库</span>
            <p style="font-size:max(15px,.92vw);color:var(--text-secondary);line-height:1.5">零第三方依赖（纯 stdlib）——重依赖只活在驱动子进程</p></div>
          </div>
          <div style="display:grid;grid-template-columns:2.4em 1fr;gap:1vw;padding:1.4vh 0;border-top:1px solid var(--border-subtle)">
            <span class="t-meta">02</span>
            <div><span style="font-weight:500;font-size:max(16px,1.05vw)">AlwaysOnRec 隔离区</span>
            <p style="font-size:max(15px,.92vw);color:var(--text-secondary);line-height:1.5">常开录音的沙箱边界</p></div>
          </div>
          <div style="display:grid;grid-template-columns:2.4em 1fr;gap:1vw;padding:1.4vh 0;border-top:1px solid var(--border-subtle)">
            <span class="t-meta">03</span>
            <div><span style="font-weight:500;font-size:max(16px,1.05vw)">Repro 复现区</span>
            <p style="font-size:max(15px,.92vw);color:var(--text-secondary);line-height:1.5">论文复现的隔离地带</p></div>
          </div>
        </div>
      </div>
      <div data-anim="up" style="display:flex;flex-direction:column;gap:1.6vh;min-width:0;min-height:0">
        <div class="t-meta" style="text-align:right">AGENT（BRAIN / AGENT）↓ 调用</div>
        <div style="flex:1;min-height:0">
          <svg viewBox="0 0 400 400" style="width:100%;height:100%;display:block" aria-hidden="true">
            <circle cx="200" cy="200" r="188" fill="none" stroke="var(--grey-2)" stroke-width="1"/>
            <circle cx="200" cy="200" r="130" fill="none" stroke="var(--ink)" stroke-width="1"/>
            <circle cx="200" cy="200" r="70" fill="var(--accent)"/>
          </svg>
        </div>
        <div style="display:flex;flex-direction:column">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:1.2vw;align-items:baseline;padding:1.2vh 0;border-top:1px solid var(--border-subtle)">
            <span style="width:10px;height:10px;background:var(--accent)"></span>
            <span style="font-size:max(16px,1vw)"><span style="font-weight:500">laos 内核</span> · kernel.py 调度 + syscall 闸门链</span>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:1.2vw;align-items:baseline;padding:1.2vh 0;border-top:1px solid var(--border-subtle)">
            <span style="width:10px;height:10px;border:1px solid var(--ink)"></span>
            <span style="font-size:max(16px,1vw)"><span style="font-weight:500">驱动子进程</span> · 15 × drv_*，重依赖隔离</span>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:1.2vw;align-items:baseline;padding:1.2vh 0;border-top:1px solid var(--border-subtle);border-bottom:1px solid var(--border-subtle)">
            <span style="width:10px;height:10px;background:var(--grey-2)"></span>
            <span style="font-size:max(16px,1vw)"><span style="font-weight:500">Linux · MCP · 外设</span> · 真实世界</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>`);

// ============ P6 · B2 闸门链 · S11 ============
const GATES = [
  ['01', '能力表 caps', '如 screen.*', 'up'],
  ['02', 'task_scope', '路径 / pkg: / time:', 'down'],
  ['03', 'schema 校验', '参数非法即拒 · EINVAL', 'up'],
  ['04', 'EDQUOT 预算', '配额耗尽即拒', 'down'],
  ['05', 'FleetLedger', '先扣账后派发 · 不可逆计价', 'up'],
  ['06', 'Jev 预审', '值不值得做 · opt-in', 'down'],
  ['07', '确认横幅', '高危操作人审', 'up'],
  ['08', '派发 · 审计', '每笔 tool call 留痕', 'down'],
];
const gateNodes = GATES.map(([n, name, desc, pos]) =>
  `<div class="th-node${n === '02' ? ' accent' : ''} ${pos}"><span class="label" style="width:10.5vw"><span class="yr">${n}</span><span class="name">${name}</span><span class="desc">${desc}</span></span><span class="dot"></span></div>`).join('');
S.push(`
<section class="slide" data-animate="timeline-walk" data-layout="S11" data-slide-id="gates">
  <div class="canvas-card">
    ${chrome(6)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:.6vh">
      <span class="t-cat">The Syscall Gate Chain · 全片核心</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.8vw,8.4vh);line-height:1;letter-spacing:-.03em">每一次工具调用，<br/>都过八道闸。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:64ch;line-height:1.7;font-weight:300;margin-top:2.6vh">静态约束 → 动态计价 → 判断与审计，逐环收窄。例：screen.tap 越过 pkg: 应用白名单，第 2 环即拒——不触 adb。</p>
    </div>
    <div class="timeline-h" style="flex:1">
      <div class="tl-row" style="grid-template-columns:repeat(8,1fr)">${gateNodes}</div>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:baseline;border-top:1px solid var(--border-subtle);padding-top:1.6vh;margin-bottom:3vh">
      <span class="t-meta">STATIC → ECONOMIC → JUDGMENT → AUDIT</span>
      <span class="t-meta">8 GATES · ALL BEFORE DISPATCH</span>
    </div>
  </div>
</section>`);

// ============ P7 · B3 分支与内存 · S19 ============
const FCARDS = [
  ['01', 'BRANCH', 'branch.py', '分支树：Agent 在分支上试错，合并回主线——类似 git 语义的 Agent 上下文管理。'],
  ['02', 'COW', 'cow.py', '写时复制上下文：分支共享基底，改动才落新页。'],
  ['03', 'MEMORY', 'memory.py', 'MemoryStore + 记忆闸门：只记实际发生的交互。'],
  ['04', 'DIARY', 'diary / journal', '日记层：沉淀实际发生的交互轨迹。'],
];
const fcards = FCARDS.map(([n, tag, term, desc]) =>
  `<div style="border-top:1px solid var(--border-subtle);padding-top:2vh;display:flex;flex-direction:column;gap:1.2vh">
      <span class="t-meta">— ${n} / ${tag}</span>
      <div style="font-family:var(--mono);font-weight:300;font-size:max(22px,1.8vw);letter-spacing:-.02em;line-height:1">${term}</div>
      <p style="font-size:max(15px,.94vw);color:var(--text-secondary);line-height:1.6">${desc}</p></div>`).join('');
S.push(`
<section class="slide" data-animate="four-cards" data-layout="S19" data-slide-id="branch">
  <div class="canvas-card">
    ${chrome(7)}
    <div style="flex:1;padding:0 0 2.6vh;display:grid;grid-template-rows:auto 1fr;gap:4.8vh;min-height:0">
      <div data-anim="line" style="display:flex;flex-direction:column;gap:2.2vh">
        <div style="height:4px;width:80px;background:var(--accent)"></div>
        <div style="display:flex;flex-direction:column;gap:1.2vh">
          <span class="t-cat">Branch &amp; Memory · 分支与内存模型</span>
          <h2 class="h-xl" style="font-weight:200;font-size:min(4.8vw,8.4vh);line-height:1;letter-spacing:-.03em">在分支上试错，<br/>合并回主线。</h2>
        </div>
      </div>
      <div data-anim="up" style="display:grid;grid-template-columns:repeat(4,1fr);gap:1.6vw">${fcards}</div>
    </div>
  </div>
</section>`);

// ============ P8 · B4 Jev · S18 ============
S.push(`
<section class="slide" data-animate="why-now" data-layout="S18" data-slide-id="jev">
  <div class="canvas-card">
    ${chrome(8)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.2vh;padding-top:.6vh">
      <span class="t-cat">Jev · 判断层</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.8vw,8.4vh);line-height:1;letter-spacing:-.03em">四闸门决策，<br/>校准先行。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:2.6vh">判断层可透传挂载：TurnBuffer.commit 与 memory.remember 都能挂 judge。</p>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(3,1fr);gap:2.6vw;flex:1;margin-top:3.8vh;align-content:stretch;padding-bottom:2.6vh">
      <div style="display:flex;flex-direction:column;gap:1.6vh">
        <span class="t-cat">三判型</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw);line-height:1.2">Noul · Choice · Score</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">把决策压成结构化快问快答——三种判断形态覆盖 laos 的决策点。</p>
        <span style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:.9;margin-top:auto">3<span style="font-size:max(16px,1vw);font-weight:500"> 型</span></span>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.6vh">
        <span class="t-cat">硬阈值映射</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw);line-height:1.2">四闸门决策模型</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">laos 11 处硬阈值映射到 Jev 四闸门决策模型，判断先于派发。</p>
        <span style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:.9;margin-top:auto">11<span style="font-size:max(16px,1vw);font-weight:500"> 处</span></span>
      </div>
      <div style="display:flex;flex-direction:column;gap:1.6vh">
        <span class="t-cat">诚实数字</span>
        <h3 style="font-weight:400;font-size:max(18px,1.35vw);line-height:1.2">实测否证宣称</h3>
        <p style="font-size:max(16px,.95vw);color:var(--text-secondary);line-height:1.65">端侧实测 median 157.5ms：README 宣称 15.6ms 被实测否证，慢 10×——如实记录。</p>
        <span style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:.9;margin-top:auto;color:var(--accent)">157.5<span style="font-size:max(16px,1vw);font-weight:500">ms</span></span>
      </div>
    </div>
  </div>
</section>`);

// ============ P9 · C1 驱动全景 · S15（重点表格页） ============
const DRV_CELLS = [
  ['HEARING · 听觉', 'drv_mic', '录音 · 只由显式 syscall 触发'],
  ['HEARING · 听觉', 'drv_ear', '转写 + LUFS'],
  ['HEARING · 听觉', 'drv_rec', ''],
  ['GOVERN · 治理', null, 'kernel.load_driver() 外挂需过闸；apps.* / screen.* 均受 pkg: 作用域'],
  ['PHONE · 手机', 'drv_screen', 'tap · text · dump · key · longpress · doubletap · devices'],
  ['PHONE · 手机', 'drv_apps', 'list · launch · close'],
  ['PHONE · 手机', 'drv_notify', ''],
  ['PHONE · 手机', 'drv_battery', ''],
  ['PHONE · 手机', 'drv_comms', ''],
  ['PHONE · 手机', 'drv_events', ''],
  ['SYSTEM · 系统', 'drv_fs', ''],
  ['SYSTEM · 系统', 'drv_proc', ''],
  ['SYSTEM · 系统', 'drv_npu', 'QNN 真机'],
  ['SYSTEM · 系统', 'drv_audio', ''],
  ['SYSTEM · 系统', 'drv_genie', ''],
  ['SYSTEM · 系统', 'drv_sys', ''],
];
const drvCells = DRV_CELLS.map(([tag, name, desc]) => {
  if (name === null) {
    return `<div class="card-accent" style="padding:1.3vh 1vw;display:flex;flex-direction:column;gap:.6vh;min-width:0;overflow:hidden">
            <span class="t-meta" style="color:var(--accent-on);opacity:.85">${tag}</span>
            <p style="font-size:max(15px,.92vw);line-height:1.5;font-weight:400">${desc}</p></div>`;
  }
  const body = desc
    ? `<p style="font-family:var(--mono);font-size:max(13px,.82vw);line-height:1.45;color:var(--text-secondary)">${desc}</p>`
    : '';
  return `<div class="card-fill" style="padding:1.3vh 1vw;display:flex;flex-direction:column;gap:.5vh;min-width:0;overflow:hidden">
            <span class="t-meta" style="font-size:max(11px,.68vw)">${tag}</span>
            <div style="font-family:var(--mono);font-weight:500;font-size:max(15px,1.02vw);letter-spacing:-.01em">${name}</div>${body}</div>`;
}).join('');
S.push(`
<section class="slide" data-animate="matrix-fill" data-layout="S15" data-slide-id="drivers">
  <div class="canvas-card">
    ${chrome(9)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.1vh;padding-top:.4vh">
      <span class="t-cat">Driver Panorama · 驱动全景</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:1;letter-spacing:-.03em">驱动全景：15 个设备。</h2>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(4,1fr);gap:1.1vh 1.1vw;flex:1;min-height:0;margin-top:4.8vh">${drvCells}</div>
    <div style="display:flex;justify-content:space-between;align-items:end;margin-top:2vh;padding-bottom:2.8vh">
      <span class="num-mega" style="font-size:min(5vw,8.8vh)">15</span>
      <span class="t-meta">BUILT-IN DRIVERS · 听觉 3 · 手机 6 · 系统 6</span>
    </div>
  </div>
</section>`);

// ============ P10 · C2 听觉栈 · S16 ============
const briefCard = (name, desc, metric, acc) =>
  `<div class="${acc ? 'card-accent' : 'card-fill'}" style="display:flex;flex-direction:column;justify-content:space-between;padding:2vh 1.5vw;min-height:15vh;gap:1.2vh">
      <div style="display:flex;flex-direction:column;gap:.8vh">
        <div style="font-weight:500;font-size:max(17px,1.2vw);letter-spacing:-.01em">${name}</div>
        <p style="font-size:max(15px,.92vw);line-height:1.55;opacity:.85">${desc}</p>
      </div>
      <div style="font-family:var(--mono);font-size:max(14px,.85vw);font-weight:500;opacity:.8;text-align:right">${metric}</div></div>`;

const HEAR = [
  ['vad.py', '能量 + 滞回 VAD：10ms 帧，无声即弃、零存储。', '10MS · 零存储', false],
  ['loudness.py', 'BS.1770-4 全套——K 计权（48k Annex 精确系数）/ 门控积分 / LRA / True Peak（sinc 重构）/ PLR。', '−23.00 LUFS ±0.1', false],
  ['binaural.py', 'Goertzel 逐频点双耳线索——ILD / IPD（250 / 500 / 1k / 2k / 4k Hz）。', '250–4K HZ · ILD/IPD', false],
  ['micgeom.py', '麦克风几何 MPE——与官方 JAX 源码逐行对齐，跨实现 diff 0.0。', 'DIFF 0.0', false],
  ['foa.py', '一阶 Ambisonics 编解码——SN3D / N3D + ACN。', 'SN3D/N3D · ACN', false],
  ['ShoNet DOA', '复现于 Repro 区——STFT 相位特征 → CNN + BiGRU + MHSA。', '冒烟 HOLDOUT 56.5°', true],
];
S.push(`
<section class="slide" data-animate="field-notes" data-layout="S16" data-slide-id="hearing">
  <div class="canvas-card">
    ${chrome(10)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.1vh;padding-top:.4vh">
      <span class="t-cat">On-Device Hearing Stack · 端侧听觉栈</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">六层听觉，全部本地。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:2.6vh">从 VAD 到空间音频整条栈跑在端侧——校准锚点 −23.00 LUFS ±0.1。</p>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:1.4vh 1.4vw;flex:1;min-height:0;margin-top:3vh;padding-bottom:2.6vh">${HEAR.map(h => briefCard(...h)).join('')}</div>
  </div>
</section>`);

// ============ P11 · C3 全双工 · S13 ============
const forceCard = (n, name, desc, mono) =>
  `<article class="card-fill" style="display:grid;grid-template-columns:auto 1fr;gap:1.6vw;align-items:center;padding:2.2vh 1.8vw">
      <span style="font-weight:200;font-size:4vw;color:var(--accent);line-height:.9">${n}</span>
      <div><h4 style="${mono ? 'font-family:var(--mono);' : ''}font-weight:500;font-size:max(17px,1.2vw);margin-bottom:.8vh">${name}</h4>
      <p style="font-size:max(15px,.94vw);color:var(--text-secondary);line-height:1.6">${desc}</p></div></article>`;

const DUPLEX = [
  ['01', 'duplex.py', '事件时间线 → 响应延迟 / 打断响应 / 重叠率 / 抢话计数——Duplex-MPE 四能力分解。'],
  ['02', 'turnpolicy.py', 'speak / hold / stop 三态；min-speech 200ms · tail-silence 500ms · min-hold 250ms 三闸，防过早响应。'],
  ['03', 'turnbuf.py', '打断即作废（未送达丢弃）；只记已送达——记忆不写想象；interject 插队帧，慢系统结果无缝织入。'],
];
S.push(`
<section class="slide" data-animate="three-forces" data-layout="S13" data-slide-id="duplex">
  <div class="canvas-card">
    ${chrome(11)}
    <div class="three-forces" data-anim="up" style="display:grid;grid-template-columns:5fr 11fr;gap:3vw;flex:1;align-items:stretch;padding-top:1vh;min-height:0;padding-bottom:2.6vh">
      <div class="hero-ink-col" style="background:var(--ink);padding:3.4vh 2.2vw;position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between">
        <span class="dot-mat" style="position:absolute;right:-6vw;bottom:-6vh;width:18vw;height:18vw;opacity:.5"></span>
        <div style="position:relative;z-index:1">
          <span class="t-cat on-dark">Full-Duplex · 全双工轮转</span>
          <h2 style="font-weight:200;font-size:min(3.8vw,6.8vh);line-height:1.06;letter-spacing:-.02em;color:#fff;margin-top:1.6vh">听得见，<br/>也插得上话。</h2>
        </div>
        <div class="t-meta" style="color:rgba(255,255,255,.6);position:relative;z-index:1">DUPLEX-MPE · SALMONN-DUO · CONTEXT SPANNING — 2026-09 周报波</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:2vh;justify-content:center">${DUPLEX.map(d => forceCard(d[0], d[1], d[2], true)).join('')}</div>
    </div>
  </div>
</section>`);

// ============ P12 · C4 双沙箱 · S02 ============
const FUNNEL4 = [
  ['STAGE 01', '10ms', 'VAD 常开：能量 + 滞回，无声即弃、零存储', false],
  ['STAGE 02', '成段', '段落成段——环形缓冲截取有效语音段', false],
  ['STAGE 03', '本地', '本地转写：端侧蒸馏，ASR 全本地', false],
  ['STAGE 04', '7天', '事件入记忆；7 天即焚', true],
];
const fnodes = FUNNEL4.map(([s, m, d, acc]) =>
  `<div class="tl-node${acc ? ' accent' : ''}" style="padding:1.7vh 0"><span class="dot"></span><span class="yr">${s}</span><span class="multi">${m}</span><p class="desc">${d}</p></div>`).join('');
const REDLINES = [
  ['REDLINE 01 · 显式触发', '录音只由显式 syscall 触发'],
  ['REDLINE 02 · 全局禁录', 'LAOS_REC=0 一票否决'],
  ['REDLINE 03 · 全程审计', '每次调用审计 event:「mic」'],
  ['REDLINE 04 · 不出端', 'ASR 全本地'],
];
const redCells = REDLINES.map(([lbl, note]) =>
  `<div class="kpi-cell"><span class="lbl">${lbl}</span><p class="note">${note}</p></div>`).join('');
S.push(`
<section class="slide" data-animate="progression" data-layout="S02" data-slide-id="sandbox">
  <div class="canvas-card">
    ${chrome(12)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1vh;padding-top:.4vh">
      <span class="t-cat">AlwaysOnRec · 双沙箱</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">常开，而克制。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:2.6vh">隔离区 279 项测试；环形缓冲 + 端侧蒸馏 + 7 天即焚——Apple Watch S12 范式对照。</p>
    </div>
    <div class="timeline-v" style="flex:1;margin-top:2vh;min-height:0">${fnodes}</div>
    <div class="kpi-row-4" style="margin-top:2vh;margin-bottom:3vh">${redCells}</div>
  </div>
</section>`);

// ============ P13 · D1 测试与质量 · S20 ============
const LEDGER = [
  ['765', '测试全绿', '主库 415 + AlwaysOnRec 279 + Repro 71', 'check-circle-2', true],
  ['415', 'laos 主库', '纯 stdlib，零第三方依赖', 'layout-grid', false],
  ['279', 'AlwaysOnRec 隔离区', '常开录音沙箱的专属测试', 'shield', false],
  ['71', 'Repro 复现区', '论文复现全部隔离', 'flask-conical', false],
  ['12', 'MINOR · 30 天', 'v0.1.0（09-04）→ v0.12.0（10-05）', 'git-tag', false],
];
const ledgerRows = LEDGER.map(([num, lbl, desc, ico, acc]) =>
  `<div class="ledger-row" style="display:grid;grid-template-columns:auto 1fr auto;gap:2vw;align-items:center;padding:1.5vh 0;border-bottom:1px solid var(--border-subtle)">
      <span class="ledger-num" style="font-weight:200;font-size:min(4vw,7vh);line-height:.95;letter-spacing:-.03em;font-feature-settings:'tnum';${acc ? 'color:var(--accent)' : ''}">${num}</span>
      <div class="ledger-label"><div style="font-weight:500;font-size:max(17px,1.2vw);margin-bottom:.4vh">${lbl}</div>
      <p style="font-size:max(15px,.92vw);color:var(--text-secondary)">${desc}</p></div>
      <i data-lucide="${ico}" style="width:1.8vw;height:1.8vw;stroke-width:1.4;color:var(--text-helper)"></i></div>`).join('');
S.push(`
<section class="slide" data-animate="stacked-ledger" data-layout="S20" data-slide-id="quality">
  <div class="canvas-card">
    ${chrome(13)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1vh;padding-top:.4vh">
      <span class="t-cat">Quality · 测试与质量</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">765 项测试，全绿。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:64ch;line-height:1.7;font-weight:300;margin-top:2.6vh">TDD 纪律——先红后绿，每任务一 commit；版本纪律——SemVer + conventional commits。</p>
    </div>
    <div data-anim="ledger" style="flex:1;margin-top:2.4vh;padding-bottom:2.6vh;min-height:0">${ledgerRows}</div>
  </div>
</section>`);

// ============ P14 · D2 版本史 · S15（重点表格页） ============
const HIST = [
  ['v0.1.0', '09-04', 'baseline：149 文件', false],
  ['v0.2.0', '09-05', '强制层：seccomp + CoW + eBPF + FleetLedger', false],
  ['v0.3.0', '09-09', 'AgentProf + MCP Tasks + 信箱 + laosweb + drv_npu', false],
  ['v0.4.0', '09-11', '听觉 + 记忆 + 日记', false],
  ['v0.5.0', '09-11', '五层手机能力 + 双沙箱', false],
  ['v0.6.0', '09-18', '语料库：19,792 论文 + 3,724 OSS', false],
  ['v0.7.0', '09-28', 'Jev 四闸门', false],
  ['v0.8.0–0.10.0', '10-05', '复现采纳三连：SHO / PhaseCoder / ANC / LUFS / Pipecat / unique_lock→loudness / turnbuf / locks + 五套 PPT', false],
  ['v0.11.0', '10-05', '手机操控四件套 + drv_apps + micgeom', false],
  ['v0.12.0', '10-05', '双工时序 + 轮转策略 + 双耳线索 + FOA', true],
  ['30 天', '09-04 → 10-05', '从 baseline 到双工时序的完整冲刺', false],
  ['纪律', 'SEMVER', '语义化版本 + conventional commits', false],
];
const histCells = HIST.map(([v, d, desc, acc]) =>
  `<div class="${acc ? 'card-accent' : 'card-fill'}" style="padding:1.3vh 1vw;display:flex;flex-direction:column;gap:.7vh;min-width:0;overflow:hidden">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:.6vw;flex-wrap:wrap">
        <span style="font-family:var(--mono);font-weight:500;font-size:max(14px,1vw);letter-spacing:-.01em">${v}</span>
        <span class="t-meta" style="font-size:max(11px,.7vw)">${d}</span></div>
      <p style="font-size:max(14px,.88vw);line-height:1.5;${acc ? 'color:var(--accent-on);opacity:.92' : 'color:var(--text-secondary)'}">${desc}</p></div>`).join('');
S.push(`
<section class="slide" data-animate="matrix-fill" data-layout="S15" data-slide-id="history">
  <div class="canvas-card">
    ${chrome(14)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.1vh;padding-top:.4vh">
      <span class="t-cat">Release History · 版本史</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.2vw,7.4vh);line-height:1;letter-spacing:-.03em">30 天，12 个 MINOR。</h2>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(3,1fr);gap:1.1vh 1.1vw;flex:1;min-height:0;margin-top:4.8vh">${histCells}</div>
    <div style="display:flex;justify-content:space-between;align-items:end;margin-top:2vh;padding-bottom:2.8vh">
      <span class="num-mega" style="font-size:min(5vw,8.8vh)">12</span>
      <span class="t-meta">MINOR RELEASES · V0.1.0 → V0.12.0 · 30 DAYS</span>
    </div>
  </div>
</section>`);

// ============ P15 · D3 复现文化 · S16 ============
const REPRO = [
  ['BS.1770-4 响度计量', '校准锚点 −23.00 LUFS ±0.1，跨实现可复核。', '−23.00 LUFS ±0.1', false],
  ['FxLMS 主动降噪', '发动机阶次收敛后降噪量 >20dB。', '>20DB', false],
  ['ShoNet DOA', '冒烟 holdout 误差 56.5°。', '56.5°', false],
  ['PhaseCoder MPE', '与官方实现逐行对齐。', '逐行对齐', false],
  ['诚实清单', '跑不动的等比缩距——40,295 样本 → 百样本冒烟，偏差全部写明。', '40,295 → 百样本', true],
  ['采纳漏斗', '复现 → 裁决（● 执行 / ◐ 基础件 / ○ 不做）→ 主库落地 → 文档执行注记。', '● ◐ ○', false],
];
S.push(`
<section class="slide" data-animate="field-notes" data-layout="S16" data-slide-id="repro">
  <div class="canvas-card">
    ${chrome(15)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.1vh;padding-top:.4vh">
      <span class="t-cat">Repro Culture · 复现文化</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">能复现的，全部复现。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:2.6vh">71 项测试的隔离复现区——论文数字不作断言，跑不动就等比缩距并写明偏差。</p>
    </div>
    <div data-anim="up" style="display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:1fr 1fr;gap:1.4vh 1.4vw;flex:1;min-height:0;margin-top:3vh;padding-bottom:2.6vh">${REPRO.map(r => briefCard(...r)).join('')}</div>
  </div>
</section>`);

// ============ P16 · D4 语料库 · S06 ============
const TOWERS = [
  ['book-open', 'PAPERS · 双会议全量', '19,792', 'ICASSP 2022-2026 14,285 + Interspeech 2021-2025 5,507 · 全量 100%', '34vh', true],
  ['library', 'INTERSPEECH', '5,507', '2021-2025 五届全量', '13vh', false],
  ['github', 'OSS · 星标仓库', '3,724', '去噪：core 132 / ref 2,864 / unrelated 728', '10vh', false],
  ['file-search', 'DOCS · 调研文档', '47', 'capstone 采纳总账：来源 / 可取之处 / 落点 / 状态', '9vh', false],
];
const towers = TOWERS.map(([ico, lbl, num, sub, h, acc]) =>
  `<div class="bar-tower">
      <div class="cap"><i data-lucide="${ico}"></i></div>
      <div class="body-block${acc ? ' b-accent' : ''}" style="min-height:${h}">
        <span class="lbl">${lbl}</span><span class="nb">${num}</span><p class="sub">${sub}</p></div></div>`).join('');
S.push(`
<section class="slide" data-animate="measure-up" data-layout="S06" data-slide-id="corpus">
  <div class="canvas-card">
    ${chrome(16)}
    <div data-anim="line" style="display:flex;flex-direction:column;gap:1.1vh;padding-top:.4vh">
      <span class="t-cat">Evidence Corpus · 调研语料库</span>
      <h2 class="h-xl" style="font-weight:200;font-size:min(4.4vw,7.8vh);line-height:1;letter-spacing:-.03em">设计，不拍脑袋。</h2>
      <p style="font-size:max(18px,1vw);color:var(--text-secondary);max-width:62ch;line-height:1.7;font-weight:300;margin-top:2.6vh">47 份调研文档 + capstone 采纳总账，每个模块背后是可溯源的证据链。</p>
    </div>
    <div class="bar-towers" data-anim="up" style="padding-bottom:2.6vh">${towers}</div>
  </div>
</section>`);

// ============ P17 · E1 红线 · S03 ============
const JARVIS = ['伪装配置', '聊天截获', '屏幕捕获', '常驻保活'];
const jarvisRows = JARVIS.map(item =>
  `<div style="display:grid;grid-template-columns:auto 1fr;gap:1vw;align-items:center;padding:1.1vh 0;border-top:1px solid var(--border-subtle)">
      <i data-lucide="x" style="width:1.4vw;height:1.4vw;stroke-width:2;color:var(--accent)"></i>
      <span style="font-size:max(16px,1vw);font-weight:400">${item}</span></div>`).join('');
S.push(`
<section class="slide split" data-animate="statement" data-layout="S03" data-slide-id="redline">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min" style="margin-bottom:0"><div class="l">17 / 19</div><div class="r">RED LINES</div></div>
        <div style="display:flex;flex-direction:column;gap:2.6vh">
          <span class="t-cat">Principle · 原则</span>
          <h1 style="font-family:var(--sans),var(--sans-zh);font-weight:200;font-size:min(4.6vw,8.2vh);line-height:1.08;letter-spacing:-.03em">能力可以有，<br/>红线内的能力，<br/><span style="font-style:italic;font-weight:300">永远不做</span>。</h1>
        </div>
        <div class="t-meta">— 非协商项 · NON-NEGOTIABLE</div>
      </div>
      <div class="half b-grey" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min" style="margin-bottom:0"><div class="l">EVIDENCE</div><div class="r">JARVIS · EU · PIPL</div></div>
        <div style="display:flex;flex-direction:column;gap:1.4vh">
          <span class="t-cat">拒绝清单实证 · jarvis</span>
          <p style="font-size:max(15px,.95vw);color:var(--text-secondary)">七文件一行不碰——</p>
          <div style="border-bottom:1px solid var(--border-subtle)">${jarvisRows}</div>
          <span class="t-cat" style="margin-top:1.4vh">法条跟踪</span>
          <div style="display:flex;flex-direction:column">
            <div style="padding:1.1vh 0;border-top:1px solid var(--border-subtle)">
              <span style="font-family:var(--mono);font-weight:500;font-size:max(14px,.9vw)">EU AI ACT</span>
              <p style="font-size:max(15px,.92vw);color:var(--text-secondary)">职场 / 教育情绪识别禁令</p></div>
            <div style="padding:1.1vh 0;border-top:1px solid var(--border-subtle);border-bottom:1px solid var(--border-subtle)">
              <span style="font-family:var(--mono);font-weight:500;font-size:max(14px,.9vw)">PIPL</span>
              <p style="font-size:max(15px,.92vw);color:var(--text-secondary)">声纹 = 敏感个人信息，单独同意</p></div>
          </div>
        </div>
        <div class="t-meta" style="text-align:right">TRACKING · 2026-10</div>
      </div>
    </div>
  </div>
</section>`);

// ============ P18 · E2 路线图 · S13 ============
const ROADMAP = [
  ['01', '近期 · v0.13+', 'FDGym 式模拟用户回归；Bin2Ambi 驱动；FOA 评测钩子接 RMS-AQA。'],
  ['02', '中期 · v1.0', '多 Agent 并发调度；驱动市场——第三方 MCP 治理接入。'],
  ['03', '远期', '端侧完整语音 Agent 参考机：laosd + 听觉栈 + 全双工闭环。'],
];
S.push(`
<section class="slide" data-animate="three-forces" data-layout="S13" data-slide-id="roadmap">
  <div class="canvas-card">
    ${chrome(18)}
    <div class="three-forces" data-anim="up" style="display:grid;grid-template-columns:5fr 11fr;gap:3vw;flex:1;align-items:stretch;padding-top:1vh;min-height:0;padding-bottom:2.6vh">
      <div class="hero-ink-col" style="background:var(--ink);padding:3.4vh 2.2vw;position:relative;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between">
        <span class="ring-mat" style="position:absolute;right:-5vw;top:-5vh;width:16vw;height:16vw;opacity:.4"></span>
        <div style="position:relative;z-index:1">
          <span class="t-cat on-dark">Roadmap · 路线图</span>
          <h2 style="font-weight:200;font-size:min(3.8vw,6.8vh);line-height:1.06;letter-spacing:-.02em;color:#fff;margin-top:1.6vh">从强制内核，<br/>到端侧参考机。</h2>
        </div>
        <div class="t-meta" style="color:rgba(255,255,255,.6);position:relative;z-index:1">V0.13+ → V1.0 → REFERENCE DEVICE</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:2vh;justify-content:center">${ROADMAP.map(r => forceCard(r[0], r[1], r[2], false)).join('')}</div>
    </div>
  </div>
</section>`);

// ============ P19 · E3 收尾 · SWISS-CLOSING-ASCII ============
S.push(`
<section class="slide split" data-animate="split-statement" data-layout="SWISS-CLOSING-ASCII" data-slide-id="closing">
  <div class="canvas-card">
    <div class="split-half">
      <div class="half b-accent" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between;position:relative;overflow:hidden">
        <canvas class="ascii-bg" aria-hidden="true"></canvas>
        <div class="chrome-min" style="margin-bottom:0;position:relative;z-index:1">
          <div class="l">19 / 19</div><div class="r">CLOSING</div>
        </div>
        <div data-anim="manifesto" style="display:flex;flex-direction:column;gap:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.78);letter-spacing:.22em;margin-bottom:1.6vh">MANIFESTO</div>
          <h2 style="font-family:var(--sans),var(--sans-zh);font-size:min(5.2vw,9.2vh);line-height:1.06;letter-spacing:-.025em;font-weight:200;color:#fff">Agent 需要的不是<br/>更强的模型，是一个<br/>会说<span style="font-style:italic;font-weight:300">「不」</span>的内核。</h2>
          <div style="font-family:var(--sans),var(--sans-zh);font-size:max(14px,1vw);line-height:1.6;color:rgba(255,255,255,.82);font-weight:400;max-width:36ch;margin-top:1.8vh">能力 · 预算 · 审计 · 判断——全部在派发之前完成。</div>
        </div>
        <div data-anim="signature" style="display:flex;justify-content:space-between;align-items:end;border-top:1px solid rgba(255,255,255,.22);padding-top:2vh;position:relative;z-index:1">
          <div class="t-meta" style="color:rgba(255,255,255,.62)">Yfredy/LAOS</div>
          <div class="t-meta" style="color:rgba(255,255,255,.62)">26.10.05</div>
        </div>
      </div>
      <div class="half" style="padding:5.6vh 3.6vw 4.4vh;justify-content:space-between">
        <div class="chrome-min"><div class="l">TAKEAWAYS</div><div class="r">03 RULES</div></div>
        <div data-anim="rules" style="display:flex;flex-direction:column;gap:0">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">01</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1.6vh">命题</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">Linux kernel + Agent + MCP——不改一行内核代码的四件遗产复用。</p></div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--text-primary)">02</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1.6vh">深潜</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">8 环 syscall 闸门 · 15 驱动 · 端侧听觉栈 · 全双工轮转 · 765 项测试全绿。</p></div>
          </div>
          <div style="display:grid;grid-template-columns:auto 1fr;gap:2vw;align-items:start;padding:2.6vh 0;border-top:1px solid var(--border-subtle);border-bottom:2px solid var(--accent)">
            <div style="font-family:var(--sans);font-weight:200;font-size:min(4.4vw,7.8vh);line-height:.9;color:var(--accent)">03</div>
            <div><h3 style="font-weight:400;font-size:max(18px,1.8vw);margin-bottom:1.6vh;color:var(--accent)">仓库</h3>
            <p style="font-size:max(16px,.94vw);line-height:1.6;color:var(--text-secondary)">github.com/Yfredy/LAOS · v0.12.0 · 2026-10-05。</p></div>
          </div>
        </div>
        <div class="t-meta" style="color:var(--text-helper);text-align:right">→ 完 · END OF DEEP DIVE</div>
      </div>
    </div>
  </div>
</section>`);

// ============ SPEAKER_NOTES ============
const NOTES = [
  { id: 'cover', title: '把 Linux 变成 Agent 的操作系统', section: '开场', minutes: 0.5,
    purpose: '定调详细版：这是上一波 12 页概览的机制层下钻',
    talk: ['封面公式先立住：kernel + Agent + MCP', '预告三个硬数字：15 驱动 / 8 环闸门 / 765 测试', '声明版本基准：v0.12.0 · 2026-10-05'],
    transition: '从公式直接进命题' },
  { id: 'thesis', title: '命题与四件内核遗产', section: '命题', minutes: 1.2,
    purpose: '给出公式与不动内核的立场',
    talk: ['namespace / cgroup / seccomp-BPF / landlock 各自的角色', '四件遗产全部复用、零内核补丁', 'ink 条那句是全片题眼：syscall 语义'],
    transition: '词表映射让抽象命题落地' },
  { id: 'mapping', title: 'Linux 与 laos 词表映射', section: '命题', minutes: 0.8,
    purpose: '用熟悉概念映射新概念',
    talk: ['四组词一一对应：驱动 / 系统调用 / 薄内核 / 权限位', '观众记住映射就记住了架构', 'tool call 每次过闸 = 系统调用语义的落点'],
    transition: '先说市面上别人怎么做 AgentOS' },
  { id: 'landscape', title: 'AgentOS 八种含义与 L2 落位', section: '定位', minutes: 1.0,
    purpose: '建立差异化坐标',
    talk: ['调研结论：同一个词至少 8 种所指', '强制力光谱 L0 到 L3，laos 在 L2 用户态强制层', '多数是框架/壳，laos 是治理内核：四件事在派发前完成'],
    transition: '坐标定了，下钻第一层：总体架构' },
  { id: 'arch', title: '三层架构与三棵树', section: '内核', minutes: 1.2,
    purpose: '建立全局结构图',
    talk: ['自上而下四层走一遍', '核心承诺：laos 目录零第三方依赖', '三棵树：主库 / AlwaysOnRec / Repro'],
    transition: '架构的中心是闸门链' },
  { id: 'gates', title: 'syscall 八环闸门链（全片核心）', section: '内核', minutes: 1.8,
    purpose: '把强制讲到机制层',
    talk: ['按 01-08 顺序走：能力 / 作用域 / schema / 预算 / 计价 / 预审 / 人审 / 审计', '举例 screen.tap 越过 pkg 白名单第 2 环即拒，不触 adb', '这一页多停留，是全片核心'],
    transition: '闸门之外还有分支与记忆模型' },
  { id: 'branch', title: '分支与内存模型', section: '内核', minutes: 1.0,
    purpose: '展示 Agent 上下文管理的 git 语义',
    talk: ['branch.py 分支树加 cow.py 写时复制', '类似 git 语义：试错在分支、结论回主线', 'memory.py 记忆闸门：只记实际发生的交互'],
    transition: '第四个内核组件是判断层 Jev' },
  { id: 'jev', title: '判断层 Jev 与诚实数字', section: '内核', minutes: 1.2,
    purpose: '展示判断层与诚实的校准文化',
    talk: ['三判型 Noul/Choice/Score，11 处硬阈值映射', 'judge 可透传：commit 与 remember 都能挂', '157.5ms 否证 15.6ms——慢 10 倍也如实写'],
    transition: '内核讲完，转向驱动生态' },
  { id: 'drivers', title: '驱动全景 15 个设备（重点表格页）', section: '驱动', minutes: 1.6,
    purpose: '展示完整设备面与治理事实',
    talk: ['按听觉 3 / 手机 6 / 系统 6 三组走', '蓝格是治理事实：load_driver 外挂需过闸', 'drv_screen 的七种操作都在 pkg 作用域内'],
    transition: '挑最深的一条栈下钻：听觉' },
  { id: 'hearing', title: '端侧听觉栈六层', section: '驱动', minutes: 1.6,
    purpose: '展示最深的端侧工程链',
    talk: ['vad 到 ShoNet 六层走一遍', '两个锚点：-23.00 LUFS 正负 0.1 与 diff 0.0', 'ShoNet 是 Repro 区的复现成果'],
    transition: '听觉之上是全双工轮转' },
  { id: 'duplex', title: '全双工轮转三件套', section: '驱动', minutes: 1.2,
    purpose: '展示对话时序的机制层',
    talk: ['duplex 四能力分解 / turnpolicy 三态三闸 / turnbuf 打断即作废', '三闸数字：200ms / 500ms / 250ms', '来源：2026-09 周报波三篇'],
    transition: '常开能力如何被沙箱约束' },
  { id: 'sandbox', title: 'AlwaysOnRec 双沙箱', section: '驱动', minutes: 1.2,
    purpose: '展示最激进能力的克制设计',
    talk: ['四段漏斗走一遍，279 项测试兜底', '四条红线一条都不能破', 'Apple Watch S12 范式对照'],
    transition: '机制讲完，看质量与节奏' },
  { id: 'quality', title: '765 测试与版本纪律', section: '质量', minutes: 0.8,
    purpose: '用账单式数据建立工程信任',
    talk: ['415 加 279 加 71 三个隔离区', 'TDD 先红后绿，每任务一 commit', 'SemVer + conventional commits 的版本纪律'],
    transition: '账单的纵轴就是版本史' },
  { id: 'history', title: '30 天 12 个 MINOR（重点表格页）', section: '质量', minutes: 1.2,
    purpose: '展示版本演化的密度与轨迹',
    talk: ['从 v0.1.0 baseline 149 文件走到 v0.12.0 双工时序', 'v0.8 到 v0.10 复现采纳三连是转折点', '蓝格是当前版本'],
    transition: '版本史里最硬的是复现文化' },
  { id: 'repro', title: '复现文化与采纳漏斗', section: '质量', minutes: 1.0,
    purpose: '展示论文级诚实',
    talk: ['四个复现各有硬指标', '诚实清单：40,295 缩到百样本，偏差写明', '采纳漏斗：复现 / 裁决 / 落地 / 注记'],
    transition: '复现的证据来自语料库' },
  { id: 'corpus', title: '调研语料库', section: '质量', minutes: 0.8,
    purpose: '证明设计有证据链',
    talk: ['19,792 / 5,507 / 3,724 / 47 四个数字', '全量 100%，不做抽样', '每条采纳总账：来源 / 可取之处 / 落点 / 状态'],
    transition: '能力之外还有不做的事' },
  { id: 'redline', title: '安全与合规红线', section: '收尾', minutes: 1.0,
    purpose: '立原则：红线内永远不做',
    talk: ['jarvis 七文件一行不碰的实证', 'EU AI Act 与 PIPL 两条法条跟踪', '原则一句话：能力可以有，红线永远不做'],
    transition: '最后看路线图' },
  { id: 'roadmap', title: '路线图三段', section: '收尾', minutes: 0.8,
    purpose: '给出可信的下一步',
    talk: ['近期 v0.13 三件事', '中期 v1.0 多 Agent 与驱动市场', '远期端侧参考机'],
    transition: '收束到一句宣言' },
  { id: 'closing', title: '会说「不」的内核', section: '收尾', minutes: 0.5,
    purpose: '一句话收束全场',
    talk: ['不是更强的模型，是会说「不」的内核', '能力 · 预算 · 审计 · 判断全部在派发前完成', '报出仓库与版本号'],
    transition: '结束，进问答' },
];

// ============ 组装 ============
let src = readFileSync(SRC, 'utf8');

const start = src.indexOf('<!-- SLIDES_HERE');
const endMarker = '<!-- 演讲备注：替换示例页时同步替换';
const end = src.indexOf(endMarker);
const newSections = '<!-- laos · Linux AgentOS · 详细技术深潜 · 19 sections ' +
  '(Swiss locked mode S01-S22 + ASCII cover/closing) -->\n' + S.join('\n') + '\n\n';
src = src.slice(0, start) + newSections + src.slice(end);

const notesJs = 'const SPEAKER_NOTES = [\n' + NOTES.map(n =>
  `  { id: ${JSON.stringify(n.id)}, title: ${JSON.stringify(n.title)}, section: ${JSON.stringify(n.section)}, minutes: ${n.minutes}, purpose: ${JSON.stringify(n.purpose)}, talk: ${JSON.stringify(n.talk)}, transition: ${JSON.stringify(n.transition)} }`
).join(',\n') + '\n];';
src = src.replace(/const SPEAKER_NOTES = \[[\s\S]*?\];/, notesJs);

src = src.replace(/<title>.*?<\/title>/, '<title>laos · Linux AgentOS — 详细技术深潜 · Deep Dive</title>');

writeFileSync(DST, src, 'utf8');
console.log('written:', DST, src.length, 'chars; sections:', S.length, '; notes:', NOTES.length);
