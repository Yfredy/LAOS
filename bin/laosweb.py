#!/usr/bin/env python3
"""laosweb —— Linux AgentOS 内核状态实时面板。

不重复造轮子：内核引导 / 种子分支 / demo 全部复用 laosd，
本模块只做两件事——
  1. build_state(kernel)：把内核可观测面聚合成一个可 JSON 化的 dict
  2. http.server 起一个单页面板 + /api/state（1s 轮询，零依赖）

用法：
    python bin/laosweb.py                # 内核 + demo + 面板 (http://127.0.0.1:8800)
    LAOS_WEB_PORT=9000 python bin/laosweb.py
"""

from __future__ import annotations

import asyncio
import http.server
import json
import os
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import laosd  # noqa: E402  复用引导器：boot_kernel / seed_main_branch / demo / WORKDIR

PORT = int(os.environ.get("LAOS_WEB_PORT", "8800"))

# 模块级持有者：Handler 与测试共享当前内核（main() 里装配）
_kernel = None
# demo 线程结束后置 True，面板据此前置"运行中/已结束"徽标
_demo_done = False


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
</style>
</head>
<body>
<header>
  <h1>laos —— Linux AgentOS 面板</h1>
  <div class="chips" id="chips"></div>
</header>
<div class="grid">
  <section class="panel"><h2>进程表</h2><div id="procs-body"></div></section>
  <section class="panel"><h2>分支树</h2><div id="branches-body"></div></section>
  <section class="panel"><h2>风险账本</h2><div id="risk-body"></div></section>
  <section class="panel"><h2>调度快照</h2><div id="sched-body"></div></section>
  <section class="panel wide"><h2>审计流（最新在上）</h2><div id="audit-body"></div></section>
  <section class="panel wide"><h2>系统调用表</h2><div id="syscalls-body"></div></section>
</div>
<footer>laosweb v0.1 —— 纯标准库实现，1s 轮询 /api/state</footer>
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
  const rows = (s.procs || []).map(p =>
    '<tr><td>' + esc(p.pid) + '</td><td>' + esc(p.name) + '</td><td>' + esc(p.state) +
    '</td><td>' + esc((p.caps || []).join(' ')) + '</td><td>' +
    esc(p.task_scope ? p.task_scope.join(' ') : '-') + '</td><td>' + esc(p.branch || '-') +
    '</td><td>' + esc(p.stats ? p.stats.syscalls : 0) + '</td><td>' +
    esc(p.stats ? p.stats.denied : 0) + '</td><td>' +
    esc(p.stats ? p.stats.risk : 0) + '</td></tr>').join('');
  $('procs-body').innerHTML =
    '<table><tr><th>pid</th><th>name</th><th>state</th><th>caps</th><th>scope</th>' +
    '<th>branch</th><th>sys</th><th>deny</th><th>risk</th></tr>' + rows + '</table>';
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
  renderProcs(s);
  renderBranches(s);
  renderRisk(s);
  renderSched(s);
  renderSys(s);
  renderAudit(s);
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

    def _send(self, code: int, body: bytes, ctype: str, head_only: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass  # 静默访问日志，避免刷屏


# --------------------------------------------------------------------------
def main() -> int:
    global _kernel
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    kernel = laosd.boot_kernel(laosd.WORKDIR)
    laosd.seed_main_branch(kernel)
    _kernel = kernel

    def _run_demo():
        global _demo_done
        try:
            asyncio.run(laosd.demo(kernel, use_real=False, task=None))
        finally:
            _demo_done = True

    threading.Thread(target=_run_demo, daemon=True).start()

    # 先绑定再播报：端口被占（如 Windows 保留端口段）时立即报错退出，
    # 而不是带着一个已被 finally 关掉内核的僵尸 demo 线程继续跑
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"laosweb 面板: http://127.0.0.1:{PORT}/  (Ctrl-C 退出)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        kernel.shutdown()
        print("laosweb 已关闭")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
