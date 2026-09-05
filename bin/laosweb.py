#!/usr/bin/env python3
"""laosweb —— Linux AgentOS 内核状态实时面板 + 交互操控台。

不重复造轮子：内核引导 / 种子分支 / demo 全部复用 laosd，
本模块做三件事——
  1. build_state(kernel)：把内核可观测面聚合成一个可 JSON 化的 dict
  2. http.server 起一个单页面板 + /api/state（1s 轮询，零依赖）
  3. POST /api/* 交互端点：确认裁决 / 重启 / kill / operator 信箱

线程红线：HTTP 线程只允许 ① 读状态 ② 同步内核调用（kernel.kill /
确认队列操作）③ asyncio.run 跑**内建** syscall（msg.*——不经 MCP 驱动、
无 driver 锁，绝不触碰 demo 循环的驱动互斥量）。

用法：
    python bin/laosweb.py                # 内核 + demo + 面板 (http://127.0.0.1:8800)
    LAOS_WEB_PORT=9000 python bin/laosweb.py
    LAOS_CONFIRM=auto-yes python bin/laosweb.py   # 高危操作自动放行（照常计费）
"""

from __future__ import annotations

import asyncio
import http.server
import itertools
import json
import os
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import laosd  # noqa: E402  复用引导器：boot_kernel / seed_main_branch / demo / WORKDIR
from laos.context import ContextManager  # noqa: E402  operator 进程的上下文

PORT = int(os.environ.get("LAOS_WEB_PORT", "8800"))

# 模块级持有者：Handler 与测试共享当前内核（main() 里装配）
_kernel = None
# demo 线程结束后置 True，面板据此前置"运行中/已结束"徽标
_demo_done = False

# ---- 交互状态（确认队列 / operator / demo 代数）--------------------------
# 确认队列：cid -> {id, op, event, answer}；web_confirm 压队并阻塞等待，
# /api/confirm 应答。demo 线程的事件循环在等待期间冻结——诚实的
# "系统等你裁决"；HTTP 线程不受影响（每个请求本就是独立线程）。
CONFIRM_TIMEOUT_S = 60  # 等待裁决上限（秒）；超时按拒绝处理
_confirm_seq = itertools.count(1)
_pending: dict[str, dict] = {}
_auto_yes = False             # confirm=auto-yes 时秒答 True（跳过横幅，照常计费）
_operator_pid: int | None = None  # 人也是进程：operator 的 pid（信箱入口）
_demo_gen = 0                 # demo 代数：restart 后旧线程不得置结束徽标
_restart_lock = threading.Lock()  # 防并发 restart（双击/浏览器重试）把面板搞坏


def set_kernel(kernel) -> None:
    """写入模块级内核持有者（Handler 与测试共用）。"""
    global _kernel
    _kernel = kernel


def get_kernel():
    """读取模块级内核持有者。"""
    return _kernel


def web_confirm(op: dict) -> bool:
    """kernel.confirm 的面板实现：压入待裁决队列并阻塞等待人类裁决。

    裁决经 POST /api/confirm 写 answer + 点亮 event；60s 超时按拒绝。
    _auto_yes（restart 带 confirm=auto-yes）时不排队直接放行。
    """
    if _auto_yes:
        return True
    cid = f"c{next(_confirm_seq)}"
    entry = {"id": cid, "op": op, "event": threading.Event(), "answer": None}
    _pending[cid] = entry
    try:
        # CONFIRM_TIMEOUT_S 在调用点取值：测试可 monkeypatch 成短超时
        if not entry["event"].wait(CONFIRM_TIMEOUT_S):
            return False  # 超时：默认拒绝
        return bool(entry["answer"])
    finally:
        _pending.pop(cid, None)  # 已裁决/超时后移除队列项


def _deny_all_pending() -> None:
    """restart 时清空确认队列：挂起的裁决一律按拒绝，等待线程立即苏醒。"""
    for entry in list(_pending.values()):
        entry["answer"] = False
        entry["event"].set()
    _pending.clear()


# --------------------------------------------------------------------------
def build_state(kernel) -> dict:
    """聚合内核可观测面为单个 dict（纯函数，可直接单测 / JSON 序列化）。"""
    # snapshot 在 agent 全部 retire 后为空，回退到内核留存的末次派发视图
    scheduler = kernel.scheduler.snapshot() or list(kernel.sched_view.values())
    return {
        "status": kernel.status(),
        "procs": kernel.ps(),
        "branches": kernel.branches.list(),
        "scheduler": scheduler,
        "risk": {
            "spent": kernel.risk.spent,
            "remaining": kernel.risk.remaining,
            "budget": kernel.risk.budget,
            "per_tool": dict(kernel.risk.per_tool),
        },
        "isolation": str(kernel.isolation),
        "lsmod": kernel.lsmod(),
        "syscalls": kernel.syscalls(),
        "audit": [dict(r) for r in kernel.audit.records[-60:]],
        "demo_done": bool(_demo_done),
        # 待裁决队列投影（从模块级 _pending 取——确认关属于面板而非单个内核）
        "pending_confirm": [
            {"id": e["id"], "tool": e["op"].get("tool", ""),
             "message": e["op"].get("message", "")}
            for e in list(_pending.values())
        ],
        "operator_pid": _operator_pid,
    }


# --------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>laos —— Linux AgentOS 面板</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --line:#334155; --fg:#e2e8f0; --dim:#94a3b8;
          --ok:#4ade80; --err:#f87171; --blue:#60a5fa; --gray:#64748b; }
  * { box-sizing: border-box; }
  body { background: var(--bg); color: var(--fg); margin: 0; padding: 16px 20px;
         font: 13px/1.5 ui-monospace, Consolas, "Courier New", monospace; }
  h1 { font-size: 20px; margin: 0 0 10px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
  .chip { background: var(--card); border: 1px solid var(--line); border-radius: 999px;
          padding: 3px 10px; color: var(--dim); white-space: nowrap; }
  .chip b { color: var(--fg); font-weight: 600; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
         margin-right: 6px; background: var(--ok); animation: pulse 1.2s ease-in-out infinite; }
  .dot.off { background: var(--gray); animation: none; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .25; } }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
           padding: 12px; min-width: 0; }
  .panel h2 { font-size: 13px; margin: 0 0 8px; color: var(--blue); letter-spacing: 1px; }
  .wide { grid-column: 1 / -1; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 3px 6px; border-bottom: 1px solid var(--line);
           white-space: nowrap; }
  th { color: var(--dim); font-weight: 500; }
  .ok { color: var(--ok); } .err { color: var(--err); } .dim { color: var(--gray); }
  .st-exploring { color: var(--blue); } .st-committed { color: var(--ok); }
  .st-invalidated { color: var(--gray); } .st-aborted { color: var(--gray); }
  .big { font-size: 26px; font-weight: 700; }
  .nums { display: flex; gap: 28px; margin-bottom: 10px; }
  .lbl { color: var(--dim); font-size: 11px; }
  .bar-row { display: grid; grid-template-columns: 110px 1fr 40px; gap: 8px;
             align-items: center; margin: 4px 0; }
  .bar { height: 10px; border-radius: 5px; background: #334155; overflow: hidden; }
  .bar > div { height: 100%; background: var(--ok); }
  .sus { color: var(--err); }
  .arow { padding: 1px 0; border-bottom: 1px dashed #1f2937; white-space: nowrap;
          overflow: hidden; text-overflow: ellipsis; }
  .at { color: var(--gray); } .apid { color: var(--blue); }
  .badge { border: 1px solid currentColor; border-radius: 4px; padding: 0 4px;
           margin-right: 4px; font-size: 11px; }
  .ares { color: var(--dim); }
  footer { margin-top: 14px; color: var(--gray); font-size: 11px; }
  /* ---- 交互操控：确认横幅 / 重启控制台 / kill / 消息面板 ---- */
  button { background: #334155; color: var(--fg); border: 1px solid var(--line);
           border-radius: 4px; padding: 2px 10px; cursor: pointer; font: inherit; }
  button:hover { background: #475569; }
  select, input { background: #0f172a; color: var(--fg); border: 1px solid var(--line);
                  border-radius: 4px; padding: 2px 6px; font: inherit; }
  #confirm-banner { display: none; position: fixed; top: 0; left: 0; right: 0; z-index: 50;
                    background: #dc2626; color: #fff; padding: 10px 20px; font-weight: 600;
                    box-shadow: 0 2px 14px rgba(0,0,0,.55);
                    animation: alert 0.9s ease-in-out infinite; }
  @keyframes alert { 0%,100% { outline: 3px solid #fecaca; outline-offset: -3px; }
                     50% { outline: 3px solid #7f1d1d; outline-offset: -3px; } }
  #confirm-banner .allow { background: #16a34a; border-color: #16a34a; margin-left: 12px; }
  #confirm-banner .deny { background: #7f1d1d; border-color: #fca5a5; margin-left: 6px; }
  #restart-console { display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
                     margin: 0 0 12px; background: var(--card);
                     border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; }
  .mrow { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
  .rrow { padding: 1px 0; }
  .rrow button { margin: 0 10px 0 6px; padding: 0 6px; font-size: 11px; }
  .kill { color: var(--err); padding: 0 6px; font-size: 11px; }
</style>
</head>
<body>
<div id="confirm-banner"></div>
<header>
  <h1>laos —— Linux AgentOS 面板</h1>
  <div class="chips" id="chips"></div>
</header>
<div id="restart-console">
  <span class="lbl">重启控制台</span>
  <select id="restart-confirm">
    <option value="no">横幅裁决</option>
    <option value="auto-yes">自动放行</option>
  </select>
  <span class="lbl">风险预算</span>
  <input id="restart-budget" type="number" min="2" step="1" value="3" style="width:64px"
         title="必须 > reserve(1)：低于会连 operator 都 spawn 不进">
  <button onclick="restartDemo()">↻ 重跑</button>
  <span id="restart-msg" class="dim"></span>
</div>
<div class="grid">
  <section class="panel"><h2>进程表</h2><div id="procs-body"></div></section>
  <section class="panel"><h2>分支树</h2><div id="branches-body"></div></section>
  <section class="panel"><h2>风险账本</h2><div id="risk-body"></div></section>
  <section class="panel"><h2>调度快照</h2><div id="sched-body"></div></section>
  <section class="panel wide"><h2>审计流（最新在上）</h2><div id="audit-body"></div></section>
  <section class="panel wide"><h2>系统调用表</h2><div id="syscalls-body"></div></section>
  <section class="panel wide"><h2>消息面板（operator 信箱）</h2><div id="msgs-body">
    <div class="mrow">
      <span class="lbl">to_pid</span>
      <select id="msg-to"></select>
      <input id="msg-text" type="text" placeholder="以 operator 身份发给 agent…"
             style="flex:1; min-width:160px">
      <button onclick="sendMsg()">发送</button>
    </div>
    <div id="msg-out" class="dim">（发送 / 收取结果显示在这里）</div>
    <div id="recv-list" style="margin-top:8px"></div>
  </div></section>
</div>
<footer>laosweb v0.2 —— 纯标准库实现，1s 轮询 /api/state + POST /api/* 交互操控</footer>
<script>
const $ = id => document.getElementById(id);

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function hms(t) {
  const d = new Date(Number(t) * 1000);
  const p = (n, w) => String(n).padStart(w || 2, '0');
  return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' +
         p(d.getSeconds()) + '.' + p(d.getMilliseconds(), 3);
}

function renderChips(s) {
  const st = s.status || {};
  const isoRaw = String(st.isolation || '');
  const cut = isoRaw.indexOf('):');
  const isoShort = cut >= 0 ? isoRaw.slice(0, cut + 1) : isoRaw.split(':')[0];
  const demo = s.demo_done
    ? '<span class="chip"><span class="dot off"></span>demo 已结束</span>'
    : '<span class="chip"><span class="dot"></span>demo 运行中</span>';
  $('chips').innerHTML =
    '<span class="chip">uptime <b>' + esc(st.uptime_s) + 's</b></span>' +
    '<span class="chip">隔离 <b>' + esc(isoShort) + '</b></span>' +
    '<span class="chip">驱动 <b>' + esc(st.drivers) + '</b></span>' +
    '<span class="chip">审计 <b>' + esc(st.audit_records) + '</b> 条</span>' + demo;
}

function renderProcs(s) {
  const op = s.operator_pid;
  const rows = (s.procs || []).map(p => {
    const dead = p.state === 'zombie' || p.state === 'killed';
    // kill 列：活进程可杀；operator（人）与已死进程不显示按钮
    const killCell = (!dead && p.pid !== op)
      ? '<td><button class="kill" onclick="killProc(' + esc(p.pid) + ')">✕</button></td>'
      : '<td></td>';
    return '<tr><td>' + esc(p.pid) + '</td><td>' + esc(p.name) + '</td><td>' + esc(p.state) +
    '</td><td>' + esc((p.caps || []).join(' ')) + '</td><td>' +
    esc(p.task_scope ? p.task_scope.join(' ') : '-') + '</td><td>' + esc(p.branch || '-') +
    '</td><td>' + esc(p.stats ? p.stats.syscalls : 0) + '</td><td>' +
    esc(p.stats ? p.stats.denied : 0) + '</td><td>' +
    esc(p.stats ? p.stats.risk : 0) + '</td>' + killCell + '</tr>';
  }).join('');
  $('procs-body').innerHTML =
    '<table><tr><th>pid</th><th>name</th><th>state</th><th>caps</th><th>scope</th>' +
    '<th>branch</th><th>sys</th><th>deny</th><th>risk</th><th>✕</th></tr>' + rows + '</table>';
}

function renderBranches(s) {
  const rows = (s.branches || []).map(b =>
    '<div class="st-' + esc(b.state) + '">' + esc(b.name) + ' [' + esc(b.state) +
    '] changes=' + esc(b.changes) +
    (b.parent ? ' <span class="dim">(← ' + esc(b.parent) + ')</span>' : '') + '</div>').join('');
  $('branches-body').innerHTML = rows || '<span class="dim">（无分支）</span>';
}

function renderRisk(s) {
  const r = s.risk || {};
  let html = '<div class="nums">' +
    '<div><div class="lbl">spent 已花费</div><div class="big err">' + esc(r.spent) + '</div></div>' +
    '<div><div class="lbl">remaining 剩余</div><div class="big ok">' + esc(r.remaining) + '</div></div>' +
    '<div><div class="lbl">budget 总预算</div><div class="big">' + esc(r.budget) + '</div></div></div>';
  const pt = r.per_tool || {};
  const keys = Object.keys(pt);
  const max = Math.max(1, ...keys.map(k => pt[k]));
  html += keys.map(k =>
    '<div class="bar-row"><span>' + esc(k) + '</span><div class="bar"><div style="width:' +
    Math.max(2, Math.round(100 * pt[k] / max)) + '%"></div></div><span>' + esc(pt[k]) +
    '</span></div>').join('') || '<span class="dim">（尚无开销）</span>';
  $('risk-body').innerHTML = html;
}

function renderSched(s) {
  const rows = (s.scheduler || []).map(r =>
    '<div' + (r.suspended ? ' class="sus"' : '') + '>pid=' + esc(r.pid) +
    ' err=' + esc(r.err_used) + '/' + (r.err_budget == null ? '∞' : esc(r.err_budget)) +
    ' tokens=' + esc(r.token_used) +
    (r.suspended ? ' [挂起: ' + esc(r.reason || '') + ']' : '') + '</div>').join('');
  $('sched-body').innerHTML = rows || '<span class="dim">（暂无调度快照）</span>';
}

function renderSys(s) {
  $('syscalls-body').innerHTML = (s.syscalls || []).map(t =>
    '<span class="chip" style="margin:2px">' + esc(t) + '</span>').join('');
}

const BADGE_COLOR = {
  admission: '#a78bfa', delegate: '#facc15', stale_broadcast: '#fb923c',
  builtin: '#22d3ee', msg: '#60a5fa', driver_load: '#94a3b8',
};

function eventDesc(r) {
  if (r.event === 'syscall') return r.result || '';
  if (r.event === 'admission')
    return r.name + ' ' + r.decision + ' (fleet_remaining=' + r.fleet_remaining + ')';
  if (r.event === 'delegate')
    return r.from + ' -> ' + r.to + ' caps=[' + (r.caps || []).join(',') + '] ttl=' + r.ttl;
  if (r.event === 'stale_broadcast') return 'branch=' + r.branch + ' paths=' + r.paths;
  if (r.event === 'msg') return 'from=' + r.from + ' to=' + r.to + ' bytes=' + r.bytes;
  if (r.event === 'driver_load') return r.driver + ' tools=' + r.tools;
  if (r.event === 'driver_unload') return r.driver;
  if (r.event === 'spawn')
    return r.name + ' caps=[' + (r.caps || []).join(',') + '] scope=' + (r.task_scope || '-');
  if (r.event === 'kill') return 'pid=' + r.pid + ' ' + (r.sig || '');
  return r.backend || r.branch || '';
}

const auditRows = new Map();  // key -> 已见标记（插入序 = 时间序：旧 -> 新）
const AUDIT_MAX = 200;        // 客户端保留行数上限

function auditRowHtml(r) {
  const pid = r.pid != null ? r.pid : (r.from != null ? r.from : (r.to != null ? r.to : '-'));
  const label = r.event === 'syscall' ? r.tool : r.event;
  let color = '#64748b';
  if (r.event === 'syscall') color = r.builtin ? BADGE_COLOR.builtin : '#94a3b8';
  else if (BADGE_COLOR[r.event]) color = BADGE_COLOR[r.event];
  const cls = r.event === 'syscall' ? (r.ok ? 'ok' : 'err') : '';
  return '<div class="arow ' + cls + '"><span class="at">' + hms(r.t) + '</span> ' +
    '<span class="apid">' + esc(pid) + '</span> ' +
    '<span class="badge" style="color:' + color + '">' + esc(label) + '</span>' +
    '<span class="ares">→ ' + esc(String(eventDesc(r)).slice(0, 80)) + '</span></div>';
}

function renderAudit(s) {
  const body = $('audit-body');            // 固定容器：只追加新行，绝不重建面板
  const recs = s.audit || [];
  const n = recs.length;
  for (let i = 0; i < n; i++) {
    const r = recs[i];
    // 去重键 = 内核审计单调序号 seq（AuditLog.write 在 append 前盖章）：
    // 不由"总数-窗口+下标"反推 —— 采样 status 与切片 audit 之间若混入
    // 新记录，反推序号会漂移，导致同一批记录下一 tick 被重复插入；
    // 与 t + tool 联合去重（同秒同工具多次调用靠序号区分）
    const key = r.seq + '|' + r.t + '|' + r.tool;
    if (auditRows.has(key)) continue;
    auditRows.set(key, true);
    body.insertAdjacentHTML('afterbegin', auditRowHtml(r));  // 逐条插到最上 = 最新在上
  }
  // 上限 200：顶部最新、底部最旧，超限从底部裁
  while (body.children.length > AUDIT_MAX) body.removeChild(body.lastChild);
  // 去重账本同步截尾（窗口内的键必属最新的 200 个，不会被误删重插）
  while (auditRows.size > AUDIT_MAX) auditRows.delete(auditRows.keys().next().value);
}

function render(s) {
  renderChips(s);
  renderBanner(s);
  renderProcs(s);
  renderBranches(s);
  renderRisk(s);
  renderSched(s);
  renderSys(s);
  renderMsgs(s);
  renderAudit(s);
}

// ---- 交互操控：POST 助手 + 确认横幅 + 重启控制台 + kill + 消息面板 ------
async function post(path, body) {
  try {
    const resp = await fetch(path, { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body) });
    const data = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, data: data || {} };
  } catch (e) { return { ok: false, status: 0, data: {} }; }
}

function renderBanner(s) {
  const el = $('confirm-banner');       // 固定节点：只改内容，不重建横幅本体
  const rows = s.pending_confirm || [];
  if (!rows.length) { el.style.display = 'none'; el.innerHTML = ''; return; }
  el.style.display = 'block';
  el.innerHTML = rows.map(r =>
    '<div class="crow">⚠ 内核等待裁决：' + esc(r.message || r.tool) +
    '<button class="allow" onclick="decide(\'' + esc(r.id) + '\',true)">✓ 允许</button>' +
    '<button class="deny" onclick="decide(\'' + esc(r.id) + '\',false)">✗ 拒绝</button></div>'
  ).join('');
}

async function decide(id, allow) {
  await post('/api/confirm', { id: id, allow: allow });
  tick();  // 任何 POST 后立即刷新
}

async function restartDemo() {
  const body = { confirm: $('restart-confirm').value,
                 risk_budget: Number($('restart-budget').value || 3) };
  $('restart-msg').textContent = '重启中…';
  const r = await post('/api/restart', body);
  if (!r.ok) {
    $('restart-msg').textContent = '失败: ' + (r.data.error || 'HTTP ' + r.status);
    return;
  }
  $('restart-msg').textContent = '已重启，审计流从头滚动';
  auditRows.clear();  // 新内核审计 seq 从 0 重新计数：去重账本必须清空
  $('audit-body').innerHTML = '';
  tick();
}

async function killProc(pid) {
  await post('/api/kill', { pid: pid });
  tick();
}

// 消息面板：输入框所在面板绝不整体重建（会丢焦点/草稿），只刷新下拉与收取列表
function renderMsgs(s) {
  const sel = $('msg-to');
  const prev = sel.value;
  const live = (s.procs || []).filter(p =>
    p.pid !== s.operator_pid && p.state !== 'zombie' && p.state !== 'killed');
  sel.innerHTML = live.map(p =>
    '<option value="' + esc(p.pid) + '">' + esc(p.pid + ' ' + p.name) + '</option>').join('');
  if (prev && live.some(p => String(p.pid) === prev)) sel.value = prev;
  $('recv-list').innerHTML = (s.procs || []).filter(p =>
    p.state !== 'zombie' && p.state !== 'killed').map(p =>
    '<span class="rrow"><span class="apid">' + esc(p.pid) + '</span> ' + esc(p.name) +
    '<button onclick="recvMsg(' + esc(p.pid) + ')">收取</button></span>').join('');
}

async function sendMsg() {
  const to = Number($('msg-to').value);
  const text = $('msg-text').value.trim();
  if (!to || !text) return;
  const r = await post('/api/msg', { to_pid: to, text: text });
  if (!r.ok) $('msg-out').textContent = '发送失败: ' + (r.data.error || 'HTTP ' + r.status);
  else if (r.data.ok) { $('msg-out').textContent = '已发送 → pid=' + to; $('msg-text').value = ''; }
  else $('msg-out').textContent = '内核拒绝: ' + (r.data.text || '');
  tick();
}

async function recvMsg(pid) {
  const r = await post('/api/recv', { pid: pid });
  if (!r.ok) $('msg-out').textContent = '收取失败: ' + (r.data.error || 'HTTP ' + r.status);
  else $('msg-out').textContent = 'pid=' + pid + ' 信箱 → ' + (r.data.text || '(empty)');
  tick();
}

async function tick() {
  try {
    const resp = await fetch('/api/state');
    if (resp.ok) render(await resp.json());
  } catch (e) { /* 服务暂不可达，下一轮再试 */ }
}
setInterval(tick, 1000);
tick();
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    """GET / -> PAGE；GET /api/state -> 内核状态 JSON；其余 404。
    HEAD 同路由只回响应头（curl -sI 探活用）。"""

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            try:
                payload = json.dumps(build_state(_kernel), ensure_ascii=False)
            except Exception:
                self._send(503, b'{"error": "kernel state unavailable"}',
                           "application/json; charset=utf-8")
                return
            self._send(200, payload.encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_HEAD(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8",
                       head_only=True)
        elif path == "/api/state":
            try:
                body = json.dumps(build_state(_kernel), ensure_ascii=False).encode("utf-8")
            except Exception:
                body = b'{"error": "kernel state unavailable"}'
                self._send(503, body, "application/json; charset=utf-8", head_only=True)
                return
            self._send(200, body, "application/json; charset=utf-8", head_only=True)
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8", head_only=True)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        handler = _POST_ROUTES.get(path)
        if handler is None:
            self._send(404, b'{"error": "not found"}',
                       "application/json; charset=utf-8")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except ValueError:
            self._send(400, b'{"error": "invalid JSON body"}',
                       "application/json; charset=utf-8")
            return
        if not isinstance(body, dict):
            self._send(400, b'{"error": "JSON object body required"}',
                       "application/json; charset=utf-8")
            return
        try:
            code, payload = handler(body)
        except Exception as exc:  # 单请求故障不炸服务器线程
            code, payload = 500, {"ok": False, "error": f"internal error: {exc}"}
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _send(self, code: int, body: bytes, ctype: str, head_only: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass  # 静默访问日志，避免刷屏


# ---- POST 交互端点（HTTP 线程红线：读状态 / 同步 kill / 内建 syscall）----
def _handle_confirm(body: dict) -> tuple[int, dict]:
    """POST /api/confirm {"id", "allow"}：应答待裁决项（web_confirm 苏醒）。"""
    cid = str(body.get("id", ""))
    entry = _pending.get(cid)
    if entry is None:
        return 404, {"ok": False, "error": f"no pending confirm {cid!r}"}
    entry["answer"] = bool(body.get("allow"))
    entry["event"].set()
    return 200, {"ok": True}


def _handle_kill(body: dict) -> tuple[int, dict]:
    """POST /api/kill {"pid"}：同步 kill，HTTP 线程安全（无 await）。"""
    try:
        pid = int(body.get("pid"))
    except (TypeError, ValueError):
        return 400, {"error": "pid must be an integer"}
    kernel = get_kernel()
    if kernel is None:
        return 503, {"error": "kernel not available"}
    if pid == _operator_pid:
        # 人也是进程，但人是不可杀的常驻进程（UI 已隐藏按钮，API 再兜底）
        return 400, {"ok": False, "error": "cannot kill operator"}
    if not kernel.kill(pid):
        return 404, {"ok": False, "error": f"no such process {pid}"}
    return 200, {"ok": True}


def _handle_msg(body: dict) -> tuple[int, dict]:
    """POST /api/msg {"to_pid", "text"}：以 operator 身份 msg.send。

    msg.* 是内核内建 syscall——不经 MCP 驱动、无 driver 锁，HTTP 线程用
    独立事件循环（asyncio.run）执行安全；绝不在此跑 MCP 路径。
    """
    kernel = get_kernel()
    if kernel is None or _operator_pid is None:
        return 503, {"error": "kernel/operator not available"}
    try:
        to_pid = int(body.get("to_pid"))
    except (TypeError, ValueError):
        return 400, {"error": "to_pid must be an integer"}
    text = str(body.get("text", ""))
    result = asyncio.run(kernel.syscall(
        _operator_pid, "msg.send", {"to_pid": to_pid, "text": text}))
    return 200, {"ok": result.ok, "text": result.text}


def _handle_recv(body: dict) -> tuple[int, dict]:
    """POST /api/recv {"pid"}：以该 pid 自己的身份收取信箱（内建 syscall）。

    设计选择：localhost-only 面板，无鉴权，任何浏览器用户可读任意进程信箱。
    """
    kernel = get_kernel()
    if kernel is None:
        return 503, {"error": "kernel not available"}
    try:
        pid = int(body.get("pid"))
    except (TypeError, ValueError):
        return 400, {"error": "pid must be an integer"}
    result = asyncio.run(kernel.syscall(pid, "msg.recv", {}))
    return 200, {"ok": result.ok, "text": result.text}


def _handle_restart(body: dict) -> tuple[int, dict]:
    """POST /api/restart {"confirm", "risk_budget"}：换参数重 boot 内核。

    confirm: "no"=横幅裁决（默认）| "auto-yes"=自动放行（跳横幅，照常计费）。
    fail-safe 语义：先校验参数（risk_budget 必须 > reserve，否则新内核连
    第一个进程都 spawn 不进），再 boot 新栈；boot 全程旧内核继续服务，
    新栈完全就绪（cutover）后才 shutdown 旧内核——boot 半途失败时面板
    永不 503。env 先写再 boot（boot_kernel 从环境读 LAOS_RISK_BUDGET）。
    """
    if not _restart_lock.acquire(blocking=False):
        return 409, {"error": "restart already in progress"}
    try:
        return _do_restart(body)
    finally:
        _restart_lock.release()


def _do_restart(body: dict) -> tuple[int, dict]:
    """restart 的真正实现（由 _restart_lock 串行化）。"""
    confirm = body.get("confirm", "no")
    if confirm not in ("no", "auto-yes"):
        return 400, {"error": "confirm must be 'no' or 'auto-yes'"}
    try:
        risk_budget = int(body.get("risk_budget", 3))
    except (TypeError, ValueError):
        return 400, {"error": "risk_budget must be an integer"}
    old = get_kernel()
    reserve = old.risk.reserve if old is not None \
        else int(os.environ.get("LAOS_RISK_RESERVE", "1"))
    if risk_budget <= reserve:
        # 新内核的第一个 spawn（operator）就要过准入：remaining=budget 必须
        # 严格高于 reserve（can_admit）。先校验后动手，避免 boot 半途炸掉。
        return 400, {"ok": False,
                     "error": f"risk_budget must be > reserve ({reserve})"}
    try:
        _boot_stack(confirm, risk_budget)  # 内部完成 cutover（持有者 + demo）
    except Exception as exc:
        # 新栈已自行回收（_boot_stack 内 shutdown+re-raise）；旧内核原封不动
        return 500, {"ok": False, "error": f"restart boot failed: {exc}"}
    # cutover 已完成，此刻才退役旧内核：其 demo 线程的下次内核调用即失败，
    # 线程自行吞掉退场（先 shutdown 再清队列，被唤醒的旧线程死在下一个
    # 内核调用上，不会重新往确认队列里压队）
    if old is not None:
        old.shutdown()
    _deny_all_pending()  # 冻结在确认关的旧 demo 线程按拒绝苏醒并随即退场
    return 200, {"ok": True}


_POST_ROUTES = {
    "/api/confirm": _handle_confirm,
    "/api/kill": _handle_kill,
    "/api/msg": _handle_msg,
    "/api/recv": _handle_recv,
    "/api/restart": _handle_restart,
}


# --------------------------------------------------------------------------
def _start_demo(kernel) -> None:
    """起 demo 守护线程（首启与 restart 共用）。

    restart 后旧线程若还活着，其驱动/审计调用会因旧内核 shutdown 而抛错
    ——捕获后静默退场（旧线程是 daemon，不阻塞退出）。只有"当代"线程
    允许置 _demo_done：旧线程晚死不得抢走新 demo 的"运行中"徽标。
    """
    global _demo_done, _demo_gen
    _demo_gen += 1
    gen = _demo_gen

    def _run():
        global _demo_done
        try:
            asyncio.run(laosd.demo(kernel, use_real=False, task=None))
        except Exception:
            pass  # 旧内核已 shutdown：句柄全失效，异常即退场信号
        finally:
            if gen == _demo_gen:
                _demo_done = True

    threading.Thread(target=_run, daemon=True).start()


def _spawn_operator(kernel) -> int:
    """人也是进程：spawn 常驻 operator（pid 进程表可见），是人类发消息的身份。

    spawn 后立即从调度器注销：operator 没有脑循环、永远不 acquire 时间片，
    若留在轮转队列里，它会以 (priority, last_served) 平局的首位（dict 插入
    序最先）永久霸占 next_pid()，把所有真 agent 饿死在 acquire() 的自旋上。
    """
    pid = kernel.spawn(name="operator", caps=["msg.*"],
                       ctx=ContextManager(system_prompt="human operator")).pid
    kernel.scheduler.retire(pid)
    return pid


def _boot_stack(confirm_mode: str, risk_budget: int):
    """boot 一整套：内核 + 种子分支 + operator 进程 + confirm 接线 + demo 线程。

    main() 首启与 POST /api/restart 共用。confirm_mode：no=横幅裁决（默认）、
    auto-yes=自动放行。boot_kernel 从环境读 LAOS_RISK_BUDGET——必须先写
    env 再 boot。fail-safe：boot 半途（seed/接线/spawn 准入）任何一步失败，
    先 shutdown 半启动的新内核（回收驱动子进程与审计句柄）再上抛——持有者
    未被触碰，restart 端点得以让旧内核继续服务。持有者移交 + demo 线程是
    不可回退的 cutover 点，放在最后一步。
    """
    global _auto_yes, _operator_pid, _demo_done
    os.environ["LAOS_CONFIRM"] = confirm_mode
    os.environ["LAOS_RISK_BUDGET"] = str(risk_budget)
    kernel = laosd.boot_kernel(laosd.WORKDIR)
    try:
        laosd.seed_main_branch(kernel)
        # 横幅永远接管确认关：web_confirm 不读终端（读终端会阻塞 demo 线程）；
        # auto-yes 模式在 web_confirm 顶部秒答 True——跳过横幅、照常计费。
        kernel.confirm = web_confirm
        _operator_pid = _spawn_operator(kernel)
    except Exception:
        kernel.shutdown()  # 半启动的内核就地回收，绝不泄漏驱动子进程
        raise
    # ---- cutover：新栈完全就绪才接管持有者并起 demo（此后不可回退）----
    _auto_yes = confirm_mode == "auto-yes"
    _demo_done = False
    set_kernel(kernel)
    _start_demo(kernel)
    return kernel


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    mode = ("auto-yes" if os.environ.get("LAOS_CONFIRM", "no").lower()
            in ("1", "yes", "y", "true", "auto-yes") else "no")
    budget = int(os.environ.get("LAOS_RISK_BUDGET") or 3)
    _boot_stack(mode, budget)

    # 先绑定再播报：端口被占（如 Windows 保留端口段）时立即报错退出，
    # 而不是带着一个已被 finally 关掉内核的僵尸 demo 线程继续跑
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"laosweb 面板: http://127.0.0.1:{PORT}/  (Ctrl-C 退出)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # 关当前内核（restart 可能已换过持有者）
        k = get_kernel()
        if k is not None:
            k.shutdown()
        print("laosweb 已关闭")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
