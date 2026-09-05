# laosweb —— 内核状态实时可视化面板实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 laos 做一个零依赖的实时 Web 面板：启动即引导内核并后台运行完整 demo（fork/explore、ReAct、IPC、委托、提交——demo 本身就是全部内核机制的活体测试），浏览器打开 `http://127.0.0.1:8800` 即可实时看到进程表、能力拒绝（按防御层分类）、分支树、风险账本、调度快照和审计流。

**Architecture:** `bin/laosweb.py`（stdlib `http.server` + 内嵌单页 HTML）：复用 `laosd.py` 的 `boot_kernel`/`seed_main_branch`/`demo`（不复制内核引导逻辑）；demo 在守护线程里 `asyncio.run` 跑，HTTP 线程只读内核状态（浅拷贝，异常回 503）。`GET /api/state` 返回 JSON（status/ps/branches/scheduler/risk/audit 尾部 60 条/lsmod/syscalls/demo_done）；`GET /` 返回内嵌中文暗色面板，vanilla JS 每秒 fetch 刷新。可测性：`build_state(kernel)` 与 `PAGE` 独立成纯函数/常量，handler 只做委托。

**Tech Stack:** Python 3.10+ 标准库（http.server / urllib / threading / asyncio），零第三方依赖，无外部静态资源。

**Spec:** 用户需求（可视化展示内核运行效果）；机制对照见 `docs/research/2026-09-05-agentos-next-steps.md`。

## Global Constraints

- 零第三方依赖（**禁止** flask/fastapi/opentelemetry 等一切 pip 包）；stdlib only。
- 不破坏执行时基线测试（以实测为准，当前 133）；新增测试放独立文件 `tests/test_laosweb.py`。
- 解释器 `/c/Users/yaoyue/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe`（记 `$PY`）。
- 线程模型红线：HTTP handler 线程只读状态（浅拷贝切片），绝不 mutate 内核；任何读异常回 503 而非崩掉 server。
- demo 的 `_cli_confirm` 在管道 stdin 下 EOF 拒绝（已验证不阻塞）——不要加输入处理。
- 端口 `LAOS_WEB_PORT` 默认 8800，绑定 127.0.0.1。
- 每task一个 commit；测试数改 README 时用实测值。

## 现状关键事实

- `bin/laosd.py:48-60` `boot_kernel(workdir)`：加载 fs/proc/sys 三驱动（sandbox.wrap 包装）；`seed_main_branch(kernel)`；`async def demo(kernel, use_real, task)` 跑完整七幕并打印。
- `laos/kernel.py` 可读状态：`status()`（uptime/isolation/drivers/syscalls/processes/branches/audit_records）、`ps()`、`branches.list()`、`scheduler.snapshot()`（agent 退出后为空 → 用 `sched_view`（plan #6 遗产，dict[pid]->row）兜底）、`risk`（spent/remaining/budget/per_tool）、`lsmod()`、`syscalls()`、`audit.records`（内存 list，含 syscall/admission/stale_broadcast/delegate/risk_spend/msg/driver_load 事件）。
- `bin/laosd.py:26-27` 的 `sys.path.insert(0, REPO)` 惯例——laosweb 照做后可 `import laosd`。
- 审计事件里 `syscall` 记录有 `ok/tool/result/pid/agent`；`admission`/`delegate_revoke`/`stale_broadcast`/`delegate`/`msg` 是分类标记来源。

---

### Task 1: build_state + HTTP 骨架 + 测试

**Files:**
- Create: `bin/laosweb.py`
- Test: `tests/test_laosweb.py`（新建）

**Interfaces:**
- Produces:
  - `PAGE: str`（占位即可，Task 2 替换为完整面板；须含标记子串 `laosweb`）
  - `build_state(kernel) -> dict`：键 `status/procs/branches/scheduler/risk/isolation/lsmod/syscalls/audit/demo_done`；`audit` 为最后 60 条的浅拷贝切片；`scheduler = snapshot() or sched_view兜底`；`demo_done` 从线程状态读取。
  - `class Handler(http.server.BaseHTTPRequestHandler)`：`GET /` → 200 `PAGE`（text/html; charset=utf-8）；`GET /api/state` → 200 JSON；其他路径 404；`build_state` 抛异常 → 503。`log_message` 静默（避免刷屏）。
  - `main()`：boot → seed → demo 守护线程 → `ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()`；`KeyboardInterrupt`/`finally` → `kernel.shutdown()`。PORT = `int(env LAOS_WEB_PORT 默认 8800)`。
- Test（`tests/test_laosweb.py`）：
  - `build_state` 直测：tempdir kernel（复用 test_laos.py 的 KernelTestCase 模式：真驱动 + spawn 两个 agent + 一次成功 syscall + 一次 denied）→ 断言键齐全、`procs` 2 条、`audit` 非空且 ≤60、risk 字段在。
  - HTTP 直测：`ThreadingHTTPServer(("127.0.0.1", 0), laosweb.Handler)` 起线程（kernel 用类属性共享）→ `urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state")` JSON 解析含 `status`；`GET /` 200 且含 `laosweb`；`GET /nope` 404。teardown `server.shutdown()` + `kernel.shutdown()`。

- [ ] **Step 1: 写失败测试**（tests/test_laosweb.py，按上述 Interfaces；import laosweb 需 `sys.path.insert(0, str(REPO / "bin"))`——沿用 test_risk.py 的 bin 注入先例，且必须放 import 区最前避免顺序问题）

- [ ] **Step 2: 跑测试确认失败**——`$PY -m unittest tests.test_laosweb -v` → `ModuleNotFoundError: No module named 'laosweb'`

- [ ] **Step 3: 实现 bin/laosweb.py**（骨架：`build_state` 完整实现；`PAGE` 先用含 `laosweb` 标记的最小 HTML；Handler/main 完整实现）

- [ ] **Step 4: 跑全量测试**——`$PY -m unittest discover -s tests 2>&1 | tail -3`（全绿 = 实测基线 + 4 左右，以实测为准）

- [ ] **Step 5: Commit** — `feat(laos): laosweb state API and http skeleton`

---

### Task 2: demo 集成 + 完整面板 + README

**Files:**
- Modify: `bin/laosweb.py`（PAGE 换成完整面板）、`README.md`

**Interfaces:**
- `PAGE` 替换为完整单页（设计要点）：
  - 暗色（#0f172a 底、#e2e8f0 字、等宽字体），顶部 `<h1>laos —— Linux AgentOS 面板</h1>` + 状态 chips（uptime、isolation、drivers、audit_records、demo 状态：运行中/已结束）。
  - CSS grid 两列面板卡（圆角、细边框）：进程表（表格：pid/name/state/caps/scope/branch/syscalls/denied/risk）、分支树（name[state] changes，committed 绿 / invalidated 灰 / exploring 蓝）、风险账本（大数字 spent/remaining + per_tool 直方条）、调度快照（pid/err_used/err_budget/tokens/suspended，挂起红标）、审计流（`<pre>` 追加式列表，最新在上：每行 `hh:mm:ss.mmm pid tool → result截断80字`，ok 绿 `#4ade80`、error 红 `#f87171`，事件类型徽标：admission 紫、delegate 黄、stale_broadcast 橙、builtin 青）、系统调用表 chips。
  - JS：`setInterval(fetch('/api/state').then(r=>r.json()).then(render), 1000)`；render 各面板 innerHTML/textContent；audit 用 Map 以 `t+tool+pid` 去重追加，超过 200 条截尾。
- `demo_done` 徽标：运行中 = 呼吸动画点；结束 = 灰。

- [ ] **Step 1: 实现 PAGE 完整版**（纯前端，无测试面变化）
- [ ] **Step 2: README**：§7 bin/ 段加 `laosweb.py  内核状态实时 Web 面板（http.server，零依赖）`；顶部用法块加 `python bin/laosweb.py   # 启动内核 + Web 面板 (http://127.0.0.1:8800)`；测试数改实测
- [ ] **Step 3: 全量回归 + 手工验收**——`$PY bin/laosweb.py` 后台起，`curl -s http://127.0.0.1:8800/api/state` demo 运行中与结束后各取一次（audit 流应有 tick），`curl -sI http://127.0.0.1:8800/` 200；报告贴 JSON 片段
- [ ] **Step 4: Commit** — `feat(laos): laosweb live dashboard page and docs`

## 验收清单

- [ ] 全量测试全绿（基线 + ~4）
- [ ] `$PY bin/laosweb.py` 后浏览器打开 `http://127.0.0.1:8800` 能看到：demo 运行中徽标 → 结束徽标、进程表 2 行、审计流实时滚动、风险账本 spent=0 remaining=3
- [ ] `laosctl`/既有行为零回归
- [ ] 本计划恰 2 个 commit
