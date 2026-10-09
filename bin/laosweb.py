#!/usr/bin/env python3
"""laosweb —— Linux AgentOS 内核状态实时面板 + 交互操控台。

不重复造轮子：内核引导 / 种子分支 / demo 全部复用 laosd，
本模块做三件事——
  1. build_state(kernel)：把内核可观测面聚合成一个可 JSON 化的 dict
  2. http.server 起一个单页面板 + /api/state（2s 轮询，零依赖；
     v3 四视图 mobile-first + 底部 tab + 暗亮主题 + PWA 四件套：
     会话=审批卡+进程/信箱/运维、审计=chips 流、记忆=provenance、治理=sentinel）
  3. POST /api/* 交互端点：确认裁决 / 重启 / kill / operator 信箱 / 生成日记

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
import re
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包：注入以便 import diary

import laosd  # noqa: E402  复用引导器：boot_kernel / seed_main_branch / demo / WORKDIR
import diary as diary_mod  # noqa: E402  每日日记生成（build_diary）
from laos.context import ContextManager  # noqa: E402  operator 进程的上下文
from laos.llm import LLMClient, LLMError  # noqa: E402  个人 agent 云端大脑（LAOS_LLM_*）

PORT = int(os.environ.get("LAOS_WEB_PORT", "8800"))

# 模块级持有者：Handler 与测试共享当前内核（main() 里装配）
_kernel = None
# demo 线程结束后置 True，面板据此前置"运行中/已结束"徽标
_demo_done = False
# 个人 agent 对话面（LAOS_LLM_* 云端大脑；main() 装配，测试可直接注入）
_llm = None
_chat_log: list[dict] = []        # [{"role": "user"|"assistant", "text"}]
_chat_lock = threading.Lock()
CHAT_LOG_CAP = 60                 # 30 轮；state 投影再截尾 20 条

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
    # reason = sentinel 决策因（op["sentinel"]，如 "risk-mode"/"taint-egress"）：
    # 审批卡据此向人类解释"为什么问你"（nanoMuse 审批三字段语义，spec §4）
    entry = {"id": cid, "op": op, "event": threading.Event(), "answer": None,
             "reason": op.get("sentinel")}
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
MEM_RECENT_N = 10   # 记忆面板展示的最近记忆条数
DIARY_LATEST_N = 3  # 日记面板展示的最近篇数


def _memories_view(kernel) -> dict:
    """记忆库视图：stats + 最近 N 条（读 MemoryStore 的 JSONL，走公开 .path）。"""
    view: dict = {"stats": kernel.memory.stats(), "recent": []}
    try:
        lines = kernel.memory.path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return view
    recent: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            recent.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 崩溃残迹（半行）跳过
        if len(recent) >= MEM_RECENT_N:
            break
    view["recent"] = recent
    return view


def _diary_view(kernel) -> list[dict]:
    """最近几篇日记：文件名 + 首个标题行（文件名即日期，倒序 = 最新在先）。"""
    diary_dir = kernel.memory.path.parent / "diary"
    if not diary_dir.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(diary_dir.glob("*.md"), key=lambda p: p.name,
                    reverse=True)[:DIARY_LATEST_N]:
        title = ""
        try:
            with p.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("#"):
                        title = line
                        break
        except OSError:
            continue
        out.append({"name": p.name, "title": title})
    return out


# ---- Task 4 渲染数据整形（纯函数：PAGE JS 的 Python 侧镜像，可单测）------
def _chips_rows(state: dict, limit: int = 40) -> list[dict]:
    """审计流 → chips 行：tool 名为 chip、ok 着色、时间与 pid 为辅文。

    键名以 build_state 实际为准（audit = 末 60 条浅拷贝列表，取最后
    limit 条）。非 syscall 事件（spawn/kill/admission/…）无 tool/ok 键：
    chip 退化用事件名、ok 按中性 True（中性事件不误报 err）。err 取
    result 前 80 字符（失败辅文）。
    """
    rows: list[dict] = []
    for r in state.get("audit", [])[-limit:]:
        ok = bool(r.get("ok")) if r.get("event") == "syscall" else True
        rows.append({"tool": r.get("tool") or r.get("event") or "?",
                     "ok": ok, "pid": r.get("pid"), "t": r.get("t"),
                     "err": None if ok else str(r.get("result", ""))[:80]})
    return rows


def _memory_rows(state: dict) -> list[dict]:
    """记忆行 + provenance 徽标（origin=user 亮显——人写行胜模型行）。

    memories 键以 build_state 实际为准：{"stats":…, "recent":[…]}——行取
    recent。origin 缺省 agent（老库行无 origin 字段时同视为模型行）。
    """
    out: list[dict] = []
    for m in (state.get("memories") or {}).get("recent", []):
        origin = m.get("origin", "agent")
        out.append({"id": m.get("id"), "text": m.get("text"), "kind": m.get("kind"),
                    "origin": origin, "user": origin == "user"})
    return out


def _sentinel_view(kernel) -> dict:
    """治理面投影：sentinel 未装配优雅降级（enabled:false + 空列表）。"""
    s = getattr(kernel, "sentinel", None)
    if s is None:
        return {"enabled": False, "mode": None, "private_tools": [],
                "egress_tools": [], "grants": [], "tainted_pids": []}
    return {"enabled": True, "mode": s.cfg.mode,
            "private_tools": list(s.cfg.private_tools),
            "egress_tools": list(s.cfg.egress_tools),
            "grants": s.grants.list_grants(),
            "tainted_pids": sorted(s._tainted)}


def _sentinel_post(kernel, body: dict) -> dict:
    """治理面写入：grant/revoke/set_mode。未知 action 以 KeyError 抛出，
    由 Handler 层转 400（与 _handle_confirm 的错误风格一致）。"""
    s = getattr(kernel, "sentinel", None)
    if s is None:
        raise KeyError("sentinel not assembled")
    action = body["action"]
    if action == "grant":
        gid = s.grants.add(str(body["tool_glob"]), body.get("target"),
                           str(body.get("scope", "once")))
        return {"ok": True, "gid": gid}
    if action == "revoke":
        return {"ok": s.grants.revoke(int(body["gid"]))}
    if action == "set_mode":
        s.cfg.mode = str(body["mode"])
        return {"ok": True}
    raise KeyError(f"unknown action {action!r}")


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
             "message": e["op"].get("message", ""), "reason": e.get("reason")}
            for e in list(_pending.values())
        ],
        "operator_pid": _operator_pid,
        # 记忆与日记（episodic memory 的可观测面）
        "memories": _memories_view(kernel),
        "diary": _diary_view(kernel),
        # 治理面（sentinel 的可观测投影；未装配时优雅降级）
        "sentinel": _sentinel_view(kernel),
        # 个人 agent 对话面（LAOS_LLM_* 未配置时 configured=False 优雅降级）
        "chat": {"configured": _llm is not None,
                 "model": _llm.model if _llm is not None else "",
                 "log": _chat_view()},
    }


# ---- v3 四视图（mobile-first + 底部 tab + 暗亮主题 + PWA）------------------
# DOM 契约：nav#tabs 四个 data-view 按钮 × main 四个 <section data-view>
# 容器（内含 #v-chat/#v-audit/#v-memory/#v-gov 锚点 div）；
# XSS 地基：动态内容一律 createElement/textContent 构造，PAGE 全程不做
# HTML 字符串拼接；审计流 epoch|seq 复合键去重（设计 §6.2）+ 只追加不重建；
# 交互五 POST（confirm/kill/msg/recv/diary/restart）全部回归于 chat 视图。
PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b0f14">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="laos">
<link rel="manifest" href="/manifest.webmanifest">
<title>laos — 控制台</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1a2027;--muted:#6b7684;--accent:#0f6f5c;
      --danger:#b3372f;--ok:#2c7a4b;--line:#e3e7ec}
[data-theme=dark]{--bg:#0b0f14;--panel:#121821;--ink:#e8edf2;--muted:#8b96a3;
      --accent:#3fc3a6;--danger:#e06a62;--ok:#5cbf85;--line:#1f2937}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.5 system-ui,"Segoe UI","Microsoft YaHei",sans-serif;
  padding-bottom:calc(56px + env(safe-area-inset-bottom))}
main{max-width:720px;margin:0 auto;padding:12px}
main section{display:none} main section.on{display:block}
nav#tabs{position:fixed;bottom:0;left:0;right:0;display:flex;justify-content:space-around;
  background:var(--panel);border-top:1px solid var(--line);
  padding-bottom:env(safe-area-inset-bottom);z-index:9}
nav#tabs button{flex:1;padding:10px 0 8px;border:0;background:none;color:var(--muted);
  font-size:12px;cursor:pointer}
nav#tabs button.on{color:var(--accent);font-weight:600}
@media(min-width:900px){ /* 桌面：侧栏恒显（参照 nanoMuse desktop.ts 语义） */
  body{padding-bottom:0;padding-left:200px}
  nav#tabs{flex-direction:column;justify-content:flex-start;top:0;bottom:0;left:0;
    width:200px;border-top:0;border-right:1px solid var(--line)}
  nav#tabs button{text-align:left;padding:12px 18px;font-size:14px}
  main{max-width:860px;padding:20px 28px}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;
  padding:12px;margin:10px 0}
.chip{display:inline-block;background:color-mix(in srgb,var(--accent) 12%,transparent);
  color:var(--accent);border-radius:999px;padding:1px 10px;font-size:12px;margin:2px}
.chip.ok{background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok)}
.chip.err{background:color-mix(in srgb,var(--danger) 14%,transparent);color:var(--danger)}
.muted{color:var(--muted)} .danger{color:var(--danger)}
.badge{border:1px solid currentColor;border-radius:4px;padding:0 5px;font-size:11px;
  margin:0 2px;white-space:nowrap}
button.act{border:1px solid var(--line);background:var(--panel);color:var(--ink);
  border-radius:8px;padding:6px 12px;cursor:pointer}
button.act.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.act.danger{color:var(--danger);border-color:var(--danger)}
button.act.kill{padding:2px 8px;font-size:12px;color:var(--danger);
  border-color:var(--danger)}
button.act:disabled{opacity:.45;cursor:not-allowed}
select,input{border:1px solid var(--line);background:var(--bg);color:var(--ink);
  border-radius:8px;padding:6px 8px;font:inherit}
input[type=number]{width:72px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.row input[type=text]{flex:1;min-width:150px}
#chat-pending .card{border-color:var(--danger)}
#llm-log{max-height:42vh;overflow-y:auto;display:flex;flex-direction:column;gap:6px;margin:8px 0}
.llm-u,.llm-a{padding:8px 10px;border-radius:10px;max-width:88%;white-space:pre-wrap;word-break:break-word}
.llm-u{align-self:flex-end;background:#0f6f5c;color:#fff}
.llm-a{align-self:flex-start;background:#161b22;border:1px solid #30363d}
.arow{padding:3px 0;border-bottom:1px dashed var(--line);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.rrow{margin-right:12px;white-space:nowrap}
table.tbl{width:100%;border-collapse:collapse}
.tbl th,.tbl td{text-align:left;padding:3px 6px;border-bottom:1px solid var(--line);
  white-space:nowrap}
.tbl th{color:var(--muted);font-weight:500}
#v-memory h3{margin:14px 0 4px;font-size:13px;color:var(--muted)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;
  background:var(--ok);animation:pulse 1.2s ease-in-out infinite;vertical-align:middle}
.dot.off{background:var(--muted);animation:none}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
</style>
</head>
<body>
<nav id="tabs">
  <button data-view="chat" class="on">会话</button>
  <button data-view="audit">审计</button>
  <button data-view="memory">记忆</button>
  <button data-view="gov">治理</button>
</nav>
<main>
  <section data-view="chat" class="on">
    <h2>会话</h2>
    <div id="v-chat">
      <div id="chat-status"></div>
      <div id="chat-pending"></div>
      <div class="card"><b id="llm-title">对话（未配置）</b>
        <div id="llm-log"></div>
        <div class="row">
          <input id="llm-in" type="text" placeholder="问你的 agent…">
          <button class="act primary" id="btn-llm-send">发送</button>
          <button class="act" id="btn-llm-new" title="清空会话">↺</button>
        </div>
        <div class="muted" id="llm-msg"></div>
      </div>
      <div class="card"><b>operator 信箱</b>
        <div class="row">
          <select id="msg-to"></select>
          <input id="msg-text" type="text" placeholder="以 operator 身份发给 agent…">
          <button class="act primary" id="btn-msg-send">发送</button>
        </div>
        <div class="muted" id="msg-out">（发送 / 收取结果显示在这里）</div>
        <div id="chat-recv"></div>
      </div>
      <div class="card"><b>进程表</b><div id="chat-procs"></div></div>
      <div class="card"><b>运维</b>
        <div class="row">
          <select id="restart-confirm">
            <option value="no">横幅裁决</option>
            <option value="auto-yes">自动放行</option>
          </select>
          <input id="restart-budget" type="number" min="2" step="1" value="3"
                 title="必须 > reserve(1)：低于会连 operator 都 spawn 不进">
          <button class="act" id="btn-restart">↻ 重跑</button>
          <span class="muted" id="restart-msg"></span>
        </div>
        <div class="row">
          <button class="act" id="btn-diary">生成今日日记</button>
          <span class="muted" id="diary-msg"></span>
        </div>
      </div>
    </div>
  </section>
  <section data-view="audit"><h2>审计</h2><div id="v-audit"></div></section>
  <section data-view="memory"><h2>记忆</h2><div id="v-memory"></div></section>
  <section data-view="gov">
    <h2>治理</h2>
    <div id="v-gov">
      <div id="gov-gate"></div>
      <div class="card"><b>风险模式</b>
        <div class="row" id="gov-modes">
          <button class="act" data-mode="ask">ask 询问</button>
          <button class="act" data-mode="auto">auto 放行</button>
          <button class="act" data-mode="strict">strict 严拒</button>
        </div>
        <span class="muted" id="gov-msg"></span>
      </div>
      <div class="card"><b>授权（grants）——逐条可撤销</b><div id="gov-grants"></div></div>
      <div class="card"><b>污点进程（读后即污点）</b><div id="gov-taints"></div></div>
      <div class="card"><b>工具面（只读）</b><div id="gov-tools"></div></div>
    </div>
  </section>
</main>
<script type="module">
const $ = s => document.querySelector(s);
const api = (p, o) => fetch(p, o).then(r => r.json());

// XSS 地基：动态内容（进程名/审计结果/记忆文本/工具名）一律 DOM API +
// textContent 构造节点，全页不做 HTML 字符串拼接。
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = String(text);
  return n;
}
function chip(text, cls) { return el("span", cls ? "chip " + cls : "chip", text); }
async function post(path, body) {
  try {
    const resp = await fetch(path, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) });
    return { ok: resp.ok, status: resp.status,
             data: await resp.json().catch(() => ({})) };
  } catch (e) { return { ok: false, status: 0, data: {} }; }
}
function refreshNow() {  // POST 后立即拉一次（不并入 2s 自排程循环，避免双循环）
  api("/api/state").then(render).catch(() => {});
}
function fmtT(t) {
  if (t == null) return "";
  const d = new Date(Number(t) * 1000);
  const p = (n, w) => String(n).padStart(w || 2, "0");
  return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
}

// ---- tab 切换 + 主题跟随（系统暗色偏好）----
for (const b of document.querySelectorAll("nav#tabs button"))
  b.onclick = () => {
    for (const x of document.querySelectorAll("nav#tabs button, main section"))
      x.classList.toggle("on", x === b || x.dataset.view === b.dataset.view);
  };
if (matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.dataset.theme = "dark";

// ---- chat：状态 chips + 审批卡 + 进程表（kill）+ 信箱（msg.send/recv）----
function renderStatus(s) {
  const box = $("#chat-status");
  box.replaceChildren();
  const st = s.status || {};
  box.append(chip("uptime " + (st.uptime_s ?? "-") + "s"),
             chip("进程 " + (st.processes ?? "-")),
             chip("驱动 " + (st.drivers ?? "-")),
             chip("审计 " + (s.audit || []).length + " 条"));
  const demo = chip(s.demo_done ? "demo 已结束" : "demo 运行中");
  demo.prepend(el("span", s.demo_done ? "dot off" : "dot"));
  box.append(demo);
}

// 审批卡四钮：拒绝 / 允许一次（不带 scope）/ 本会话 / 总是（后两者落 grant）。
// 前端一律新键（cid/approved）且始终显式带 tool——不给服务端 "*" 兜底留门。
const DECISIONS = [
  { label: "拒绝", approved: false, cls: "danger" },
  { label: "允许一次", approved: true, cls: "primary" },
  { label: "本会话", approved: true, scope: "session" },
  { label: "总是", approved: true, scope: "always" },
];
function renderPending(s) {
  const box = $("#chat-pending");
  box.replaceChildren();
  for (const p of (s.pending_confirm || [])) {
    const card = el("div", "card");
    const head = el("div", "row");
    head.append(chip(p.tool || "?"));
    // reason 徽标 = sentinel 决策因（如 risk-mode/taint-egress）：为什么问你
    if (p.reason) head.append(el("span", "badge danger", p.reason));
    card.append(head);
    if (p.message) card.append(el("div", "muted", p.message));
    const acts = el("div", "row");
    for (const d of DECISIONS) {
      const b = el("button", "act " + (d.cls || ""), d.label);
      b.onclick = async () => {
        const body = { cid: p.id, approved: d.approved, tool: p.tool || "" };
        if (d.scope) body.scope = d.scope;  // once 不带 scope
        await post("/api/confirm", body);
        refreshNow();
      };
      acts.append(b);
    }
    card.append(acts);
    box.append(card);
  }
}

function renderProcs(s) {
  const box = $("#chat-procs");
  box.replaceChildren();
  const tbl = el("table", "tbl");
  const hr = el("tr");
  for (const h of ["pid", "name", "state", "caps", "sys", "deny", "risk", "✕"])
    hr.append(el("th", null, h));
  tbl.append(hr);
  for (const p of (s.procs || [])) {
    const dead = p.state === "zombie" || p.state === "killed";
    const tr = el("tr");
    const put = (v, cls) => tr.append(el("td", cls, v));
    put(p.pid); put(p.name);
    put(p.state, dead ? "danger" : "muted");
    put((p.caps || []).join(" ") || "-");
    put(p.stats ? p.stats.syscalls : 0);
    put(p.stats ? p.stats.denied : 0);
    put(p.stats ? p.stats.risk : 0);
    const td = el("td");
    if (!dead && p.pid !== s.operator_pid) {  // 人不可杀；已死进程无按钮
      const b = el("button", "act kill", "✕");
      b.onclick = async () => {
        await post("/api/kill", { pid: p.pid });
        refreshNow();
      };
      td.append(b);
    }
    tr.append(td);
    tbl.append(tr);
  }
  box.append(tbl);
}

function renderMsgs(s) {
  const sel = $("#msg-to");  // 下拉刷新但保选择；输入框/按钮不重建（不丢草稿/焦点）
  const prev = sel.value;
  sel.replaceChildren();
  const live = (s.procs || []).filter(p =>
    p.pid !== s.operator_pid && p.state !== "zombie" && p.state !== "killed");
  for (const p of live) {
    const o = el("option", null, p.pid + " " + p.name);
    o.value = String(p.pid);
    sel.append(o);
  }
  if (prev && live.some(p => String(p.pid) === prev)) sel.value = prev;
  const box = $("#chat-recv");
  box.replaceChildren();
  for (const p of (s.procs || []).filter(p =>
      p.state !== "zombie" && p.state !== "killed")) {
    const row = el("span", "rrow");
    row.append(el("b", null, p.pid), " " + p.name + " ");
    const b = el("button", "act", "收取");
    b.onclick = async () => {
      const r = await post("/api/recv", { pid: p.pid });
      $("#msg-out").textContent = r.ok
        ? "pid=" + p.pid + " 信箱 → " + (r.data.text || "(empty)")
        : "收取失败: " + (r.data.error || "HTTP " + r.status);
      refreshNow();
    };
    row.append(b);
    box.append(row);
  }
}

// ---- audit：chips 流（复合键去重，最新在上，只追加不重建）----
const auditSeen = new Map();  // key -> 已见（插入序 = 时间序：旧 -> 新）
const AUDIT_MAX = 200;
function renderAudit(s) {
  const body = $("#v-audit");  // 固定容器：只 prepend 新行，绝不整版重建
  for (const r of (s.audit || [])) {
    // 去重键 = (轮转代 epoch, 单调序号 seq, t, tool) 复合键——seq 轮转换代
    // 后复位归零（设计 §6.2），裸 seq 键会把新代同 seq 事件误判重复而丢弃
    const key = r.epoch + "|" + r.seq + "|" + r.t + "|" + (r.tool || r.event || "");
    if (auditSeen.has(key)) continue;
    auditSeen.set(key, true);
    body.prepend(auditRow(r));
  }
  while (body.children.length > AUDIT_MAX) body.removeChild(body.lastChild);
  while (auditSeen.size > AUDIT_MAX) auditSeen.delete(auditSeen.keys().next().value);
}
function auditRow(r) {
  const isSys = r.event === "syscall";
  const ok = isSys ? !!r.ok : true;  // 非 syscall 事件中性着色（不误报 err）
  const row = el("div", "arow");
  row.append(el("span", "muted", fmtT(r.t)), " ");
  row.append(chip(r.tool || r.event || "?", ok ? "ok" : "err"));
  if (r.pid != null) row.append(" ", el("span", "muted", "pid " + r.pid));
  if (!ok && r.result != null && String(r.result) !== "")
    row.append(" ", el("span", "danger", "→ " + String(r.result).slice(0, 80)));
  return row;
}
function resetAuditStream() {  // restart：新内核 (epoch,seq) 重计——账本必须清空
  auditSeen.clear();
  $("#v-audit").replaceChildren();
}

// ---- memory：provenance 徽标（人写亮显）+ 日记列表 ----
function renderMemory(s) {
  const box = $("#v-memory");
  box.replaceChildren();
  const m = s.memories || {};
  const st = m.stats || {};
  const head = el("div");
  head.append(el("span", "muted", "total "), el("b", null, st.total || 0), " ");
  for (const [k, v] of Object.entries(st.by_kind || {})) head.append(chip(k + " " + v));
  box.append(head);
  const rows = m.recent || [];
  if (!rows.length) box.append(el("div", "muted", "（记忆库还是空的）"));
  for (const r of rows) {
    const origin = r.origin || "agent";
    const row = el("div", "arow");
    if (r.kind) row.append(el("span", "badge muted", r.kind), " ");
    // origin=user 亮显（人写行胜模型行）；agent 行灰徽标
    row.append(origin === "user" ? chip("人写") : el("span", "badge muted", origin));
    row.append(" #" + r.id + " ", el("span", null, String(r.text ?? "").slice(0, 60)));
    if (r.tags && r.tags.length)
      row.append(" ", el("span", "muted", "[" + r.tags.join(",") + "]"));
    box.append(row);
  }
  box.append(el("h3", null, "日记"));
  const diary = s.diary || [];
  if (!diary.length)
    box.append(el("div", "muted", "（还没有日记——会话页点「生成今日日记」）"));
  for (const d of diary) {
    const row = el("div", "arow");
    row.append(el("b", null, d.name), " ", el("span", "muted", d.title || ""));
    box.append(row);
  }
}

// ---- gov：enabled 门控 + mode 三选一 + grants 逐条撤销 + 污点 chips ----
function renderGov(s) {
  const sen = s.sentinel || {};
  const on = !!sen.enabled;
  const gate = $("#gov-gate");
  gate.replaceChildren();
  if (!on) {
    const c = el("div", "card");
    c.textContent = "sentinel 未装配——治理面只读（装配后可设模式 / 撤销授权）";
    gate.append(c);
  } else {
    gate.append(el("div", "muted", "sentinel 已装配 · mode=" + sen.mode));
  }
  for (const b of document.querySelectorAll("#gov-modes button")) {
    b.disabled = !on;  // 未装配禁写
    b.classList.toggle("primary", on && b.dataset.mode === sen.mode);
  }
  const gbox = $("#gov-grants");
  gbox.replaceChildren();
  const grants = sen.grants || [];
  if (!grants.length) gbox.append(el("span", "muted", "（无授权）"));
  else {
    const tbl = el("table", "tbl");
    const hr = el("tr");
    for (const h of ["gid", "tool_glob", "target", "scope", ""])
      hr.append(el("th", null, h));
    tbl.append(hr);
    for (const g of grants) {
      const tr = el("tr");
      tr.append(el("td", null, g.gid), el("td", null, g.tool_glob),
                el("td", "muted", g.target ?? "-"), el("td", null, g.scope));
      const td = el("td");
      const b = el("button", "act danger", "撤销");
      b.disabled = !on;
      b.onclick = async () => {
        await post("/api/sentinel", { action: "revoke", gid: g.gid });
        refreshNow();
      };
      td.append(b);
      tr.append(td);
      tbl.append(tr);
    }
    gbox.append(tbl);
  }
  const tbox = $("#gov-taints");
  tbox.replaceChildren();
  const taints = sen.tainted_pids || [];
  if (!taints.length) tbox.append(el("span", "muted", "（无污点进程）"));
  for (const pid of taints) tbox.append(chip("pid " + pid, "err"));
  const tools = $("#gov-tools");
  tools.replaceChildren();
  tools.append(el("div", "muted", "隐私读（读后即污点）"));
  for (const t of (sen.private_tools || [])) tools.append(chip(t));
  tools.append(el("div", "muted", "外发面"));
  for (const t of (sen.egress_tools || [])) tools.append(chip(t, "err"));
}

function renderLlm(c) {
  if (!c) return;
  $("#llm-title").textContent = "对话" + (c.configured ? "（" + (c.model || "?") + "）" : "（未配置）");
  $("#llm-in").disabled = !c.configured;
  $("#btn-llm-send").disabled = !c.configured;
  const log = $("#llm-log");
  log.textContent = "";
  for (const m of (c.log || [])) {
    const b = document.createElement("div");
    b.className = m.role === "user" ? "llm-u" : "llm-a";
    b.textContent = m.text;               // XSS 纪律：textContent，永不拼 HTML
    log.append(b);
  }
  log.scrollTop = log.scrollHeight;
}
function render(s) {
  renderStatus(s);
  renderLlm(s.chat);
  renderPending(s);
  renderProcs(s);
  renderMsgs(s);
  renderAudit(s);
  renderMemory(s);
  renderGov(s);
}

// ---- 交互接线：msg.send / restart / diary / set_mode --------------------
async function sendMsg() {
  const to = Number($("#msg-to").value);
  const text = $("#msg-text").value.trim();
  if (!to || !text) return;
  const r = await post("/api/msg", { to_pid: to, text: text });
  const out = $("#msg-out");
  if (!r.ok) out.textContent = "发送失败: " + (r.data.error || "HTTP " + r.status);
  else if (r.data.ok) { out.textContent = "已发送 → pid=" + to; $("#msg-text").value = ""; }
  else out.textContent = "内核拒绝: " + (r.data.text || "");
  refreshNow();
}
async function restartDemo() {
  const body = { confirm: $("#restart-confirm").value,
                 risk_budget: Number($("#restart-budget").value || 3) };
  $("#restart-msg").textContent = "重启中…";
  const r = await post("/api/restart", body);
  if (!r.ok) {
    $("#restart-msg").textContent = "失败: " + (r.data.error || "HTTP " + r.status);
    return;
  }
  $("#restart-msg").textContent = "已重启，审计流从头滚动";
  resetAuditStream();
  refreshNow();
}
async function genDiary() {
  $("#diary-msg").textContent = "生成中…";
  const r = await post("/api/diary", {});
  $("#diary-msg").textContent = (r.ok && r.data.ok)
    ? "已写入 " + (r.data.path || "")
    : "失败: " + (r.data.error || "HTTP " + r.status);
  refreshNow();
}
async function sendChat() {
  const inp = $("#llm-in");
  const text = inp.value.trim();
  if (!text) return;
  $("#llm-msg").textContent = "思考中…";
  inp.value = ""; inp.disabled = true;
  const r = await post("/api/chat", { text: text });
  inp.disabled = $("#btn-llm-send").disabled;
  $("#llm-msg").textContent = (!r.ok || !r.data.ok)
    ? "失败: " + ((r.data && r.data.error) || "HTTP " + r.status)
    : (r.data.ms + "ms");
  refreshNow();
}
$("#btn-msg-send").onclick = sendMsg;
$("#btn-llm-send").onclick = sendChat;
$("#btn-llm-new").onclick = async () => {
  await post("/api/chat", { reset: true });
  $("#llm-msg").textContent = "";
  refreshNow();
};
$("#llm-in").addEventListener("keydown", e => {
  if (e.key === "Enter") sendChat();
});
$("#btn-restart").onclick = restartDemo;
$("#btn-diary").onclick = genDiary;
for (const b of document.querySelectorAll("#gov-modes button"))
  b.onclick = async () => {
    const r = await post("/api/sentinel",
                         { action: "set_mode", mode: b.dataset.mode });
    $("#gov-msg").textContent = r.ok
      ? "" : "失败: " + (r.data.error || "HTTP " + r.status);
    refreshNow();
  };

// 2s 轮询：失败也排下一轮——fetch/渲染任一故障都不得杀死面板循环
async function tick() {
  try {
    render(await api("/api/state"));
  } catch (e) { /* 暂不可达/渲染故障：吞掉，下一轮再试 */ }
  setTimeout(tick, 2000);
}
tick();
</script>
</body></html>
"""

# ---- PWA 四件套：manifest + 内联 SVG 图标（零二进制资产，全内联生成）------
MANIFEST = (
    '{"name":"laos 控制台","short_name":"laos","start_url":"/",'
    '"display":"standalone","background_color":"#0b0f14",'
    '"theme_color":"#0f6f5c",'
    '"icons":[{"src":"/icon.svg","sizes":"any","type":"image/svg+xml"}]}'
)
ICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<circle cx="12" cy="12" r="10" fill="#0f6f5c"/>'
            '<text x="12" y="16" font-size="12" text-anchor="middle" '
            'fill="#fff">L</text></svg>')


class Handler(http.server.BaseHTTPRequestHandler):
    """GET / -> PAGE；GET /api/state -> 内核状态 JSON；
    GET /manifest.webmanifest + /icon.svg -> PWA 四件套（内联生成）；
    其余 404。HEAD 同路由只回响应头（curl -sI 探活用）。"""

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/manifest.webmanifest":
            self._send(200, MANIFEST.encode("utf-8"),
                       "application/manifest+json; charset=utf-8")
        elif path == "/icon.svg":
            self._send(200, ICON_SVG.encode("utf-8"),
                       "image/svg+xml; charset=utf-8")
        elif path == "/api/state":
            try:
                payload = json.dumps(build_state(_kernel), ensure_ascii=False)
            except Exception:
                self._send(503, b'{"error": "kernel state unavailable"}',
                           "application/json; charset=utf-8")
                return
            self._send(200, payload.encode("utf-8"),
                       "application/json; charset=utf-8")
        elif path == "/api/sentinel":
            # 治理面投影：sentinel 未装配也 200（enabled:false 优雅降级）
            self._send(200,
                       json.dumps(_sentinel_view(get_kernel()),
                                  ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_HEAD(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8",
                       head_only=True)
        elif path == "/manifest.webmanifest":
            self._send(200, MANIFEST.encode("utf-8"),
                       "application/manifest+json; charset=utf-8", head_only=True)
        elif path == "/icon.svg":
            self._send(200, ICON_SVG.encode("utf-8"),
                       "image/svg+xml; charset=utf-8", head_only=True)
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
    """POST /api/confirm {"cid", "approved", "scope"?, "tool"?}：应答待裁决项。

    nanoMuse 审批三字段语义的 laos 化（spec §4）：approved 且 scope ∈
    {session, always} 且 sentinel 已装配 → 先经 _sentinel_post 落 grant 再
    放行（tool 取 body.tool，缺省回退 pending 条目的 op.tool）；deny /
    scope=once 不落 grant。旧键名（id/allow）在新审批卡切换前保持兼容。
    """
    cid = str(body.get("cid") or body.get("id") or "")
    entry = _pending.get(cid)
    if entry is None:
        return 404, {"ok": False, "error": f"no pending confirm {cid!r}"}
    approved = bool(body.get("approved", body.get("allow")))
    scope = body.get("scope")
    if approved and scope in ("session", "always"):
        kernel = get_kernel()
        if kernel is not None and getattr(kernel, "sentinel", None) is not None:
            _sentinel_post(kernel, {
                "action": "grant",
                "tool_glob": str(body.get("tool") or entry["op"].get("tool", "*")),
                "target": None, "scope": scope})
    entry["answer"] = approved
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


def _handle_diary(body: dict) -> tuple[int, dict]:
    """POST /api/diary {"date"?}：聚合当天审计 + 记忆库，生成每日日记。

    build_diary 是纯同步文件 I/O（读内存中的 audit.records、写 var/diary、
    向 MemoryStore 追加一行）——不经 MCP 驱动、无 driver 锁、无 asyncio，
    与 msg.* 同级，HTTP 线程直接调用安全。LLM 摘要在 build_diary 内部
    try/except 兜底：失败自动回落抽取式模板，端点永不 500 于 LLM 故障。
    """
    kernel = get_kernel()
    if kernel is None:
        return 503, {"error": "kernel not available"}
    date = str(body.get("date") or time.strftime("%Y-%m-%d")).strip()
    # 日期白名单：只放行 YYYY-MM-DD——../ 之类的路径串不得借 date 逃出 var/diary/
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return 400, {"error": "date must be YYYY-MM-DD"}
    result = diary_mod.build_diary(date, kernel.audit.records, kernel.memory)
    return 200, {"ok": True, "path": result["path"], "date": result["date"],
                 "summary": result["summary"]}


def _handle_sentinel(body: dict) -> tuple[int, dict]:
    """POST /api/sentinel {"action": "grant"|"revoke"|"set_mode", ...}。

    纯同步内存读写（GrantStore 自带锁），无 MCP 驱动、无 asyncio，HTTP
    线程直调安全。未知 action / sentinel 未装配（KeyError）、坏参数
    （ValueError）均转 400——与 _handle_confirm 的错误风格一致。
    """
    kernel = get_kernel()
    if kernel is None:
        return 503, {"error": "kernel not available"}
    try:
        return 200, _sentinel_post(kernel, body)
    except (KeyError, ValueError) as exc:
        return 400, {"ok": False, "error": str(exc)}


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


def _chat_view(tail: int = 20) -> list[dict]:
    with _chat_lock:
        return [dict(m) for m in list(_chat_log)[-tail:]]


def _audit_llm(model: str, started: float, ok: bool,
               out_len: int = 0, err: str = "") -> None:
    """LLM 调用审计：只记 模型/耗时/成败/长度——内容永不入审计（隐私红线）。"""
    k = get_kernel()
    if k is None:
        return
    rec = {"t": time.time(), "pid": 0, "op": "llm.chat", "event": "llm",
           "ok": ok, "model": model,
           "ms": int((time.monotonic() - started) * 1000), "out_len": out_len}
    if err:
        rec["err"] = err[:120]
    try:
        k.audit.write(rec)
    except Exception:
        pass  # 审计失败不阻断对话链路


def _handle_chat(body: dict) -> tuple[int, dict]:
    """POST /api/chat {"text"} / {"reset": true}：个人 agent 对话。

    未配置 LAOS_LLM_* → 503（能力缺席不假装存在，与 sentinel 未装配同
    哲学）；调用失败 → 502（LLMError 带原因）；成功追加双向气泡进会话
    历史（内存态，重启即清——持久化对话记忆留给后续波接 MemoryStore）。
    """
    if body.get("reset"):
        with _chat_lock:
            _chat_log.clear()
        return 200, {"ok": True, "log": []}
    text = str(body.get("text") or "").strip()
    if not text:
        return 400, {"error": "text required"}
    client = _llm
    if client is None:
        return 503, {"error": "LLM 未配置：设 LAOS_LLM_BASE_URL 与 "
                              "LAOS_LLM_MODEL（可选 LAOS_LLM_KEY）后重启 laosweb"}
    messages = [{"role": "system", "content": client.system}]
    messages += [{"role": m["role"], "content": m["text"]} for m in _chat_view(CHAT_LOG_CAP)]
    messages.append({"role": "user", "content": text})
    started = time.monotonic()
    try:
        reply = client.chat(messages)
    except LLMError as exc:
        _audit_llm(client.model, started, ok=False, err=str(exc))
        return 502, {"error": f"LLM 调用失败: {exc}"}
    ms = int((time.monotonic() - started) * 1000)
    with _chat_lock:
        _chat_log.append({"role": "user", "text": text})
        _chat_log.append({"role": "assistant", "text": reply})
        del _chat_log[:-CHAT_LOG_CAP]
    _audit_llm(client.model, started, ok=True, out_len=len(reply))
    return 200, {"ok": True, "reply": reply, "model": client.model,
                 "ms": ms, "log": _chat_view()}


_POST_ROUTES = {
    "/api/confirm": _handle_confirm,
    "/api/kill": _handle_kill,
    "/api/msg": _handle_msg,
    "/api/recv": _handle_recv,
    "/api/restart": _handle_restart,
    "/api/diary": _handle_diary,
    "/api/sentinel": _handle_sentinel,
    "/api/chat": _handle_chat,
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
    global _llm
    _llm = LLMClient.from_env()
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
