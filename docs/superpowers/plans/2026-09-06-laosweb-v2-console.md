# laosweb v2 —— 交互式操控（从看板到驾驶舱）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 laosweb 从只读看板升级为可操控驾驶舱：① 高危操作弹出**确认横幅**（允许/拒绝按钮，60s 超时自动拒）——human-in-the-loop 走进面板；② **重跑按钮**（带 confirm 模式/风险预算参数，重启内核+demo）；③ **operator 进程**——人以 `msg.send` 给任意 agent 发消息；④ 进程表每行 **kill 按钮**。

**Architecture:** 全部交互走 `POST /api/*`（JSON body），复用现有 `ThreadingHTTPServer`（每个请求本就是独立线程）。线程安全设计：① confirm 挂起队列 `self._pending: dict[cid, {op, event, answer}]`——`web_confirm` 压队 + `Event.wait(60)`（demo 线程的事件循环在等待期间冻结，这是诚实的"系统等你裁决"；HTTP 线程不受影响）；② kill 用 `kernel.kill(pid)`（同步、无 await，HTTP 线程安全）；③ restart = 旧 kernel.shutdown() → os.environ 更新 → 重新 boot（boot_kernel 读 env）→ 新 demo 线程；④ operator 是 boot 后 `kernel.spawn(name="operator", caps=["msg.*"])` 的常驻进程——人也是系统里的一个进程；手动发消息经 `asyncio.run(kernel.syscall(operator_pid, "msg.send", ...))` 在 HTTP 线程跑（内建 syscall 无驱动锁，且是独立事件循环——不触碰 demo 循环的 `_driver_locks`）。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖，前端 vanilla JS。

**Spec:** 用户需求（面板要可交互）；交互设计对照 `docs/guide-panel.md`。

## Global Constraints

- 零第三方依赖；不破坏执行时基线（以实测为准，当前 142）；测试并入 `tests/test_laosweb.py`。
- 解释器 `$PY`（同前）；每 task 一个 commit。
- **线程红线**：HTTP 线程只允许 ① 读状态 ② 同步内核调用（kill/confirm-queue 操作）③ `asyncio.run` 跑**内建** syscall（msg.*/sys.delegate——绝不跑 MCP 路径，避免跨事件循环的驱动锁）；demo 循环挂起等待确认时冻结是设计行为。
- confirm 队列语义：等待上限 60s，超时自动拒绝；answered 后队列项移除。

## 现状关键事实

- `bin/laosweb.py`：`build_state(kernel)`（GET /api/state）、`Handler`（do_GET/do_HEAD/do 404/503）、`main()`（boot_kernel → seed → 确认不读终端的 confirm 覆盖 → demo 守护线程 → serve_forever）。`_kernel` 模块级持有。
- `laos/kernel.py`：`kernel.kill(pid)`（同步）；`kernel.confirm` 可整体替换（laosweb 已替换为不读 stdin 的 lambda）；内建 syscall 经 `syscall(pid, tool, args)`（async）。
- `kernel.spawn(name, caps, ctx, ...)` 需要 ctx（ContextManager）。
- 前端：`PAGE` 单页，`tick()` 每秒 fetch /api/state 后 `render(state)` 更新固定 id 面板。

---

### Task 1: 后端交互端点（confirm 队列 / restart / kill / operator msg）

**Files:**
- Modify: `bin/laosweb.py`
- Test: `tests/test_laosweb.py`（追加）

**Interfaces:**
- Produces:
  - 模块级：`_pending: dict[str, dict]`（cid → {op, event: threading.Event, answer: bool|None}）、`_operator_pid: int | None`。
  - `web_confirm(op: dict) -> bool`：压队（cid = f"c{seq}"）→ `event.wait(60)` → 返回 answer（超时/未答 = False）。
  - `build_state` 增键 `"pending_confirm": [{"id", "tool", "message"}...]`（从 _pending 投影）与 `"operator_pid"`。
  - POST 端点（JSON body，返回 JSON）：
    - `POST /api/confirm` `{"id": cid, "allow": bool}` → 置 answer + set event → `{"ok": true}`
    - `POST /api/restart` `{"confirm": "yes"|"no", "risk_budget": int}` → 旧 kernel.shutdown() → os.environ 写 LAOS_CONFIRM/LAOS_RISK_BUDGET → 重 boot（含 seed、confirm 覆盖、operator spawn、新 demo 线程、_demo_done=False）→ `{"ok": true}`
    - `POST /api/kill` `{"pid": int}` → kernel.kill → `{"ok": true}` / 404
    - `POST /api/msg` `{"to_pid": int, "text": str}` → `asyncio.run(kernel.syscall(_operator_pid, "msg.send", {...}))` → `{"ok": result.ok, "text": result.text}`
  - `main()` boot 后 spawn operator：`_operator_pid = kernel.spawn(name="operator", caps=["msg.*"], ctx=ContextManager(system_prompt="human operator")).pid`；`kernel.confirm = web_confirm`（替换现在的 lambda）。
  - demo 线程包装 try/except：restart 时旧线程若还活着，其驱动调用会因 shutdown 抛错——捕获后静默置 `_demo_done=True`（旧线程是 daemon，不阻塞退出）。
- Handler `do_POST`：路由上述端点；body 用 `Content-Length` 读取 + `json.loads`；错误 → 400/404；成功 → 200 JSON。

- [ ] **Step 1: 追加失败测试（tests/test_laosweb.py）**

```python
class TestInteractivity(unittest.TestCase):
    def setUp(self):
        # 沿用 TestBuildState 的 kernel 引导（抽成模块级 helper 复用）
        self.kernel = _make_kernel()   # 真驱动 + main 分支 + 两个 agent + operator
        binmod.set_kernel(self.kernel)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), binmod.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.kernel.shutdown()

    def _post(self, path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    def test_confirm_roundtrip(self):
        import threading as th
        answers = []
        def ask():
            answers.append(binmod.web_confirm({"tool": "proc.exec", "message": "x"}))
        t = th.Thread(target=ask, daemon=True).start()
        import time; time.sleep(0.2)
        state = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{self.port}/api/state").read())
        self.assertEqual(len(state["pending_confirm"]), 1)
        cid = state["pending_confirm"][0]["id"]
        self._post("/api/confirm", {"id": cid, "allow": True})
        time.sleep(0.3)
        self.assertEqual(answers, [True])

    def test_confirm_timeout_denies(self):
        import time
        res = binmod.web_confirm({"tool": "x"})  # 无 pending 投放（直接测函数需短超时）
        # 注：直测超时需要 60s——改为测压队后答 False 的路径
```

（实现者注意：`web_confirm` 的 60s 等待不能直接测——把等待时长提为模块常量 `CONFIRM_TIMEOUT_S = 60`，测试里 monkeypatch 成 0.5；`test_confirm_timeout_denies` 压队后不开答，0.8s 后断言返回 False 且队列清空。）

    def test_kill_agent(self):
        victim = <spawn 一个一次性 agent>
        res = self._post("/api/kill", {"pid": victim.pid})
        self.assertTrue(res["ok"])
        self.assertEqual(self.kernel.procs[victim.pid].state, "killed")

    def test_operator_msg_send(self):
        target = <spawn>
        res = self._post("/api/msg", {"to_pid": target.pid, "text": "hi"})
        self.assertTrue(res["ok"])
        recv = asyncio.run(self.kernel.syscall(target.pid, "msg.recv", {}))
        self.assertIn("hi", recv.text)

    def test_restart_rebuilds_kernel(self):
        old_pid = next(iter(self.kernel.procs))
        res = self._post("/api/restart", {"confirm": "yes", "risk_budget": 9})
        self.assertTrue(res["ok"])
        self.assertIsNot(binmod.get_kernel(), self.kernel)  # 新内核对象
        self.assertEqual(os.environ.get("LAOS_RISK_BUDGET"), "9")
```

（restart 测试会换掉全局 _kernel——tearDown 恢复或随后 shutdown 新内核；实现者保证测试隔离。）

- [ ] **Step 2: 跑测试确认失败** —— `404`（无 do_POST）

- [ ] **Step 3: 实现**（按 Interfaces；restart 里 `os.environ["LAOS_RISK_BUDGET"] = str(risk_budget)` 与 `os.environ["LAOS_CONFIRM"] = confirm` 在 boot 之前写入）

- [ ] **Step 4: 全量回归**（全绿 = 基线 + ~6）

- [ ] **Step 5: Commit** — `feat(laos): laosweb interactive endpoints (confirm queue/restart/kill/operator msg)`

---

### Task 2: 前端操控 + README

**Files:**
- Modify: `bin/laosweb.py`（PAGE）、`README.md`

**UI 设计：**
1. **确认横幅**（页面顶部，红色 `#dc2626` 底）：`render` 时若 `state.pending_confirm` 非空则显示：`⚠ 内核等待裁决：{message} [✓ 允许] [✗ 拒绝]`，按钮 `fetch('/api/confirm', {id, allow})`；多个待确认排成列表。横幅存在时加闪烁边框。
2. **重启控制台**（顶部右侧小面板）：confirm 下拉（no=拒绝高危 / yes=放行计费）、风险预算数字输入（默认 3）、[↻ 重跑 demo] 按钮 → POST /api/restart → 立即 tick()。重启后 audit 清空重新滚动（前端 seen-set 需在 restart 成功后 reset）。
3. **进程表 kill 列**：每行末尾 `✕`（zombie/killed 行不显示）→ `POST /api/kill` → tick()。
4. **发消息面板**（新增第 7 面板）：to_pid 下拉（从 procs 取活进程，排除 operator 自己）、text 输入框、[发送] → POST /api/msg → 显示结果行；发送后目标 agent 的 msg.recv 由用户点面板按钮或让 demo 的 brain 消费——面板直接附一个 [帮忙 recv] 小按钮对该 pid 调 `msg.recv`（走 operator msg 面板同款 POST？recv 需要目标 pid 自己调——增加 `POST /api/recv` `{"pid"}`：`asyncio.run(kernel.syscall(pid, "msg.recv", {}))` 返回文本显示在面板上）。

- [ ] **Step 1: 实现上述四块 UI**（render 更新固定节点；按钮 onclick 走 fetch POST 后立即 tick()；restart 后清空 audit seen-set）
- [ ] **Step 2: README**：guide-panel.md（docs/）加「交互功能」节（确认横幅/重跑/发消息/kill 的用法与实验建议）；README §7 laosweb 行改为「实时面板 + 交互操控」
- [ ] **Step 3: 全量回归 + 手工验收**——起服务，浏览器过一遍：触发 confirm（需 LAOS_CONFIRM 走 web_confirm——注意 restart 设 confirm=yes/no 走的是 lambda 自动答；**让横幅出现的路径**：restart 不设 confirm=yes 时（默认 no），把 web_confirm 接进闸门而非 lambda——即 restart 的 confirm 参数只控制 LAOS_CONFIRM env 的默认 lambda？简化：**web_confirm 始终接管**（横幅必弹），restart 的 confirm 参数改为控制「自动答 yes」开关：`confirm: "auto-yes"` 时 confirm=lambda True 跳横幅，否则横幅。验收：demo 跑到 proc.exec 时横幅出现 → 点允许 → 审计流绿、风险账本 spent=3 → 再重跑点拒绝 → EACCES 不计费）

- [ ] **Step 4: Commit** — `feat(laos): laosweb control console (confirm banner/restart/kill/operator msg)`

## 验收清单

- [ ] 全量测试全绿（基线 + ~6）
- [ ] 浏览器实测：横幅弹出→允许→计费；横幅弹出→拒绝→不计费；重跑按钮换预算生效；kill 后进程表 state=killed；operator 发消息 agent 能收
- [ ] 本计划恰 2-3 个 commit
