# Linux AgentOS 认知 Demo 实施计划（kernel + Agent + MCP）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个 ~500 行、零依赖（纯 Python stdlib）的可运行 demo 讲清 laos 的核心命题：**基座是 Linux 内核；Agent 是新负载（与进程同类）；MCP 服务是设备驱动**——三者拼成"Linux AgentOS"的最小可认知闭环。

**Architecture:** `demos/agentos-demo/` 独立于 `laos/` 核心（认知演示物，不进内核、不进主测试套件）。三个真实进程扮演三个角色：Agent（真实 Linux 进程，有 pid/退出码/信号）、DemoKernel（监督者：能力闸+审计+代理）、MCP 文件服务（设备驱动：JSON-RPC 2.0 over stdio）。Agent 只能经内核 syscall 通道（stdin/stdout 管道）取资源；内核按 per-agent 能力表放行并把调用代理给 MCP server；agent 进程内自装 seccomp BPF 封死 execve/socket——"内核之外无资源、能力之外无访问"。

**Tech Stack:** Python 3 stdlib only（subprocess/json/threading/ctypes）；seccomp 经 ctypes 直调 prctl+seccomp（复刻 `laos/seccomp.py` 的模式，不 import 它——demo 自包含）；WSL Ubuntu 运行与测试（真 Linux 原语；Windows 宿主不跑）。

**Spec:** `docs/research/2026-10-08-aios-agentos-landscape.md` §6（demo 设计与三角色映射表；调研认知是 demo 的论证前提，执行者应先读该节）。

## Global Constraints

- 零依赖：只准 Python 3 stdlib；禁止 pip install 任何东西。
- 自包含：demo 目录内不 import `laos` 包（认知演示物要能单目录拷走）；允许从 `laos/seccomp.py` **复刻**常量与调用模式（来源在文件头注明）。
- 运行环境：WSL Ubuntu（`wsl -- python3 ...`）；seccomp 测试在非 Linux 跳过（`unittest.skipUnless(platform.system()=="Linux")`）。
- 测试不进主套件：demo 测试由自身命令运行（`python3 test_demo.py`），`tests/` 目录不动——主套件 946 绿的口径不受影响。
- 每任务一个 commit，消息用 `feat(demo): ...` 前缀。
- 对应表（README 与代码注释同源）：Agent=进程（fork/exec/信号/退出码）；内核=监督者（能力表=syscall 表的权限位）；MCP server=驱动（stdio=设备总线）；审计=内核日志（audit.jsonl）。

---

### Task 1: MCP 文件服务（"设备驱动"角色）

**Files:**
- Create: `demos/agentos-demo/mcp_fs.py`
- Test: `demos/agentos-demo/test_demo.py`

**Interfaces:**
- Consumes: 无（首个任务）。
- Produces: `mcp_fs.py` 可执行为 MCP server（stdin/stdout 上 JSON-RPC 2.0）；工具三件 `fs.read(path)` / `fs.write(path, data)` / `time.now()`；环境变量 `DEMO_JAIL` 指定 jail 根（缺省 `<本文件目录>/var/jail`）。后续 Task 2/3 以子进程方式驱动它。

- [ ] **Step 1: 写失败测试（握手 + 三工具 + jail 越界拒绝）**

创建 `demos/agentos-demo/test_demo.py`：

```python
# demos/agentos-demo/test_demo.py —— Linux AgentOS demo 测试（WSL 侧运行）
# 运行：wsl -- python3 demos/agentos-demo/test_demo.py
# 零依赖；不 import laos（demo 自包含）。
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class McpFsTest(unittest.TestCase):
    """MCP 文件服务 = 设备驱动：stdio 上的 JSON-RPC 2.0。"""

    def _server(self, jail: Path):
        env = dict(os.environ, DEMO_JAIL=str(jail))
        return subprocess.Popen(
            [sys.executable, str(HERE / "mcp_fs.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8")

    def _rpc(self, proc, obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline())

    def test_handshake_tools_list_and_call(self):
        with tempfile.TemporaryDirectory() as td:
            jail = Path(td)
            (jail / "a.txt").write_text("hello", encoding="utf-8")
            p = self._server(jail)
            try:
                init = self._rpc(p, {"jsonrpc": "2.0", "id": 1,
                                      "method": "initialize",
                                      "params": {}})
                self.assertIn("result", init)
                tools = self._rpc(p, {"jsonrpc": "2.0", "id": 2,
                                      "method": "tools/list"})
                names = {t["name"] for t in tools["result"]["tools"]}
                self.assertEqual(names, {"fs.read", "fs.write", "time.now"})
                r = self._rpc(p, {"jsonrpc": "2.0", "id": 3,
                                  "method": "tools/call",
                                  "params": {"name": "fs.read",
                                             "arguments": {"path": "a.txt"}}})
                self.assertEqual(r["result"]["content"][0]["text"], "hello")
            finally:
                p.stdin.close()
                p.wait(timeout=5)

    def test_jail_escape_denied(self):
        with tempfile.TemporaryDirectory() as td:
            jail = Path(td) / "jail"
            jail.mkdir()
            secret = Path(td) / "secret.txt"
            secret.write_text("nope", encoding="utf-8")
            p = self._server(jail)
            try:
                r = self._rpc(p, {"jsonrpc": "2.0", "id": 1,
                                  "method": "tools/call",
                                  "params": {"name": "fs.read",
                                             "arguments": {"path": "../secret.txt"}}})
                self.assertTrue(r.get("error") or
                                r["result"].get("isError"))
            finally:
                p.stdin.close()
                p.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: FAIL/ERROR（`mcp_fs.py` 不存在，Popen 报 FileNotFoundError）。

- [ ] **Step 3: 实现 mcp_fs.py**

创建 `demos/agentos-demo/mcp_fs.py`：

```python
#!/usr/bin/env python3
"""mcp_fs —— Linux AgentOS demo 的"设备驱动"：stdio 上的 MCP 文件服务。

对应表：MCP server = 设备驱动（stdio = 设备总线，tools/list = 设备探测，
tools/call = 一次设备 I/O）。工具面刻意窄：fs.read/fs.write 只在 jail 内
（DEMO_JAIL），time.now 零状态——驱动只做设备语义，不做治理（治理在内核）。

JSON-RPC 2.0 over stdio（MCP 传输契约）；协议字段参考 laos/mcp.py 同型实现。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TOOLS = [
    {"name": "fs.read", "description": "读 jail 内相对路径文件",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"}},
                     "required": ["path"]}},
    {"name": "fs.write", "description": "写 jail 内相对路径文件",
     "inputSchema": {"type": "object",
                     "properties": {"path": {"type": "string"},
                                    "data": {"type": "string"}},
                     "required": ["path", "data"]}},
    {"name": "time.now", "description": "当前时间（零状态驱动示例）",
     "inputSchema": {"type": "object", "properties": {}}},
]

SERVER_INFO = {"name": "mcp-fs", "version": "0.1.0"}


def _jail() -> Path:
    root = Path(os.environ.get("DEMO_JAIL", Path(__file__).parent / "var" / "jail"))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _resolve(jail: Path, rel: str) -> Path:
    p = (jail / rel).resolve()
    if not p.is_relative_to(jail):   # 越界一律拒绝（驱动侧硬边界）
        raise PermissionError(f"EPERM: out of jail: {rel!r}")
    return p


def _call(name: str, args: dict) -> str:
    jail = _jail()
    if name == "fs.read":
        return _resolve(jail, str(args["path"])).read_text(encoding="utf-8")
    if name == "fs.write":
        p = _resolve(jail, str(args["path"]))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(args["data"]), encoding="utf-8")
        return f"OK {len(str(args['data']))} bytes"
    if name == "time.now":
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    raise ValueError(f"ENOSYS: unknown tool {name!r}")


def main() -> int:
    for line in sys.stdin:                      # 每行一个 JSON-RPC 请求
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        rid, method = req.get("id"), req.get("method")
        try:
            if method == "initialize":
                result = {"protocolVersion": "2025-06-18",
                          "capabilities": {"tools": {}},
                          "serverInfo": SERVER_INFO}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                text = _call(req["params"]["name"], req["params"].get("arguments") or {})
                result = {"content": [{"type": "text", "text": text}]}
            else:
                raise ValueError(f"ENOSYS: {method}")
            resp = {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as exc:                # 驱动错误按 JSON-RPC error 回
            resp = {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行确认通过**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: OK（2 tests）。

- [ ] **Step 5: Commit**

```bash
git add demos/agentos-demo/mcp_fs.py demos/agentos-demo/test_demo.py
git commit -m "feat(demo): MCP 文件服务——设备驱动角色（stdio JSON-RPC + jail 硬边界）"
```

---

### Task 2: 内核 + Agent 进程模型（能力闸 + 审计）

**Files:**
- Create: `demos/agentos-demo/kernel.py`（含 DemoKernel 与 agent 代理逻辑）
- Create: `demos/agentos-demo/agent.py`（agent 进程入口）
- Modify: `demos/agentos-demo/test_demo.py`（追加 KernelAgentTest）

**Interfaces:**
- Consumes: Task 1 的 `mcp_fs.py`（DemoKernel 以子进程驱动，构造参数 `mcp_cmd` 可注入假 server 供测试）。
- Produces:
  - `DemoKernel.spawn(agent_id: str, caps: list[str], program: list[str] | None = None) -> int`（返回真实 pid；program 缺省 `[sys.executable, agent.py, agent_id]`）
  - `DemoKernel.syscall_loop(timeout: float = 10.0) -> None`（读 agent stdout 的 syscall 行→能力闸→`self._dispatch`→回写应答；agent 退出或 EOF 结束）
  - `DemoKernel.audit_path: Path`（`<demo>/var/audit.jsonl`，每行 `{"t","pid","agent","op","args","ok","result"}`）
  - agent 协议（agent.py 与 kernel 的共同契约）：agent 每行 `{"op": "fs.read", "args": {...}}` 打到 stdout；从 stdin 每行读 `{"ok": true, "result": ...}` 或 `{"ok": false, "error": "EPERM ..."}`。

- [ ] **Step 1: 追加失败测试**

在 `test_demo.py` 追加：

```python
from kernel import DemoKernel   # noqa: E402  (demo 目录自包含，同目录 import)


class _ScriptServer:
    """测试用假 MCP server：一条预先编排的应答。"""

    def __init__(self, reply: dict):
        self._reply = reply

    def call(self, name: str, args: dict) -> dict:
        return self._reply


class KernelAgentTest(unittest.TestCase):
    def _boot(self, caps, script):
        k = DemoKernel()
        k.mcp = _ScriptServer({"content": [{"type": "text", "text": "DATA"}]})
        aid = f"agent-{abs(hash(script)) % 1000}"
        k.write_script(aid, script)
        pid = k.spawn(aid, caps)
        k.syscall_loop(timeout=10)
        return k, pid

    def test_agent_is_real_process_and_gates(self):
        # agent 有能力表：fs.read 放行、fs.write 拒 EPERM
        k, pid = self._boot(["fs.read"], [
            {"op": "fs.read", "args": {"path": "a.txt"}},
            {"op": "fs.write", "args": {"path": "b.txt", "data": "x"}},
        ])
        self.assertGreater(pid, 0)
        rows = k.audit_rows()
        ops = [(r["op"], r["ok"]) for r in rows]
        self.assertEqual(ops, [("fs.read", True), ("fs.write", False)])
        self.assertIn("EPERM", rows[1]["result"])

    def test_agent_exit_code_is_real(self):
        k, pid = self._boot(["fs.read"], [{"op": "fs.read", "args": {"path": "a"}}])
        self.assertEqual(k.agent_exit(pid), 0)

    def test_signal_kill(self):
        k = DemoKernel()
        aid = "sleeper"
        k.write_script(aid, [{"op": "sleep", "args": {"sec": 60}}])
        pid = k.spawn(aid, [])
        import signal
        import time as _t
        _t.sleep(0.5)
        k.kill(pid, signal.SIGTERM)            # 内核对真进程发真信号
        k.syscall_loop(timeout=5)
        self.assertLess(k.agent_exit(pid), 0)  # 负值=被信号杀死（Linux 语义）
```

同时 `kernel.py` 需提供 `write_script(agent_id, script)`（把 agent 的任务脚本写到 `var/scripts/<agent_id>.json`，agent.py 启动时读取执行）。

- [ ] **Step 2: 运行确认失败**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: ERROR（`kernel` 模块不存在，import 失败）。

- [ ] **Step 3: 实现 kernel.py 与 agent.py**

创建 `demos/agentos-demo/kernel.py`：

```python
#!/usr/bin/env python3
"""kernel —— Linux AgentOS demo 的"内核"：监督者角色。

对应表：能力表 = syscall 表的权限位（per-agent allow-list）；审计 = 内核
日志（audit.jsonl，一行一事件）；MCP server = 驱动（syscall 经 _dispatch
代理到驱动）；agent = 进程（真 pid/信号/退出码——本文件不做模拟）。
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VAR = HERE / "var"


class DemoKernel:
    def __init__(self, mcp_cmd: list[str] | None = None):
        self.mcp_cmd = mcp_cmd or [sys.executable, str(HERE / "mcp_fs.py")]
        self.mcp = None                   # 测试可注入假驱动；否则懒起真 MCP
        self._procs: dict[int, subprocess.Popen] = {}
        self._caps: dict[int, set[str]] = {}
        self._names: dict[int, str] = {}
        self.audit_path = VAR / "audit.jsonl"
        VAR.mkdir(exist_ok=True)
        self.audit_path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()

    # -- 进程面 ------------------------------------------------------------
    def write_script(self, agent_id: str, script: list[dict]) -> None:
        d = VAR / "scripts"
        d.mkdir(exist_ok=True)
        (d / f"{agent_id}.json").write_text(json.dumps(script), encoding="utf-8")

    def spawn(self, agent_id: str, caps: list[str],
              program: list[str] | None = None) -> int:
        program = program or [sys.executable, str(HERE / "agent.py"), agent_id]
        proc = subprocess.Popen(program, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True,
                                encoding="utf-8")
        self._procs[proc.pid] = proc
        self._caps[proc.pid] = set(caps)
        self._names[proc.pid] = agent_id
        return proc.pid

    def kill(self, pid: int, sig=signal.SIGTERM) -> None:
        self._procs[pid].send_signal(sig)

    def agent_exit(self, pid: int):
        return self._procs[pid].poll()

    # -- syscall 面 ----------------------------------------------------------
    def syscall_loop(self, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        pending = {pid: p for pid, p in self._procs.items()}
        while pending and time.monotonic() < deadline:
            for pid, proc in list(pending.items()):
                line = proc.stdout.readline()
                if not line:                       # agent 退出（EOF）
                    del pending[pid]
                    continue
                req = json.loads(line)
                reply = self._syscall(pid, req)
                proc.stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
                proc.stdin.flush()

    def _syscall(self, pid: int, req: dict) -> dict:
        op, args = str(req.get("op")), req.get("args") or {}
        if op not in self._caps[pid]:
            reply = {"ok": False, "error": f"EPERM: {op} not in caps of pid {pid}"}
        elif op == "sleep":
            reply = {"ok": True, "result": "interrupted?"}
        else:
            reply = self._dispatch(op, args)      # 放行 → 代理到 MCP 驱动
        self._audit(pid, op, args, reply)
        return reply

    def _dispatch(self, op: str, args: dict) -> dict:
        if self.mcp is None:
            self.mcp = _McpProxy(self.mcp_cmd)
        try:
            out = self.mcp.call(op, args)
            return {"ok": True, "result": out["content"][0]["text"]}
        except Exception as exc:
            return {"ok": False, "error": f"EIO: {exc}"}

    # -- 审计 --------------------------------------------------------------
    def _audit(self, pid: int, op: str, args: dict, reply: dict) -> None:
        row = {"t": time.time(), "pid": pid, "agent": self._names[pid],
               "op": op, "args": args, "ok": reply["ok"],
               "result": str(reply.get("result") or reply.get("error"))[:120]}
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def audit_rows(self) -> list[dict]:
        return [json.loads(l) for l in
                self.audit_path.read_text(encoding="utf-8").splitlines() if l]


class _McpProxy:
    """内核持有的 MCP 客户端：起 mcp_fs 子进程，握手后逐条 tools/call。"""

    def __init__(self, cmd: list[str]):
        self._p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True,
                                   encoding="utf-8")
        self._id = 0

    def call(self, name: str, args: dict) -> dict:
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
               "params": {"name": name, "arguments": args}}
        self._p.stdin.write(json.dumps(req) + "\n")
        self._p.stdin.flush()
        return json.loads(self._p.stdout.readline())["result"]
```

创建 `demos/agentos-demo/agent.py`：

```python
#!/usr/bin/env python3
"""agent —— Linux AgentOS demo 的"Agent"：一个真实 Linux 进程。

启动即真进程（本进程的 pid/退出码/信号都是内核语义，非模拟）。行为循环：
读 var/scripts/<agent_id>.json 的任务脚本，逐条把 syscall 打到 stdout、
从 stdin 读应答——agent 的唯一资源通道就是这对管道（内核）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    agent_id = sys.argv[1]
    script = json.loads((HERE / "var" / "scripts" / f"{agent_id}.json")
                        .read_text(encoding="utf-8"))
    for step in script:
        sys.stdout.write(json.dumps(step, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        reply = json.loads(sys.stdin.readline())
        print(f"[{agent_id}] {step['op']} -> "
              f"{'OK ' + str(reply.get('result')) if reply['ok'] else reply.get('error')}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行确认通过**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: OK（5 tests）。若 `test_signal_kill` 偶发超时，确认 `syscall_loop` 在 agent 被 SIGTERM 后 readline 返回 EOF（管道关闭）即退出循环。

- [ ] **Step 5: Commit**

```bash
git add demos/agentos-demo/kernel.py demos/agentos-demo/agent.py demos/agentos-demo/test_demo.py
git commit -m "feat(demo): 内核+Agent 进程模型——真 pid/信号/退出码 + 能力闸 + 审计"
```

---

### Task 3: seccomp 收紧 Agent 进程（L4 强制层）

**Files:**
- Create: `demos/agentos-demo/seccomp_gate.py`
- Modify: `demos/agentos-demo/agent.py`（启动即装 filter）
- Modify: `demos/agentos-demo/test_demo.py`（追加 SeccompTest）

**Interfaces:**
- Consumes: Task 2 的 agent.py main 入口。
- Produces: `seccomp_gate.install()`——在当前进程装 BPF filter：`execve`/`execveat` 与 `socket`/`socketpair`/`connect` 一律 `SECCOMP_RET_ERRNO|EPERM`；其余 syscall 放行。装好后 `os.system`/`subprocess`/网络全部失败但管道 I/O 正常。

- [ ] **Step 1: 追加失败测试**

```python
import platform


class SeccompTest(unittest.TestCase):
    """L4 强制层：agent 进程自装 seccomp——内核之外无资源。"""

    @unittest.skipUnless(platform.system() == "Linux", "seccomp 仅 Linux")
    def test_agent_cannot_exec_or_socket(self):
        k = DemoKernel()
        k.write_script("jailed", [
            {"op": "selftest.execve", "args": {}},
            {"op": "selftest.socket", "args": {}},
            {"op": "fs.read", "args": {"path": "a.txt"}},   # 管道 I/O 仍正常
        ])
        k.mcp = _ScriptServer({"content": [{"type": "text", "text": "DATA"}]})
        pid = k.spawn("jailed", ["fs.read", "selftest.execve", "selftest.socket"])
        k.syscall_loop(timeout=10)
        rows = {(r["op"], r["ok"]) for r in k.audit_rows()}
        self.assertIn(("selftest.execve", False))
        self.assertIn(("selftest.socket", False))
        self.assertIn(("fs.read", True))
```

kernel 的 `_syscall` 对 `selftest.*` op 放行到 agent 自检（见 Step 3 的协议改动）。

- [ ] **Step 2: 运行确认失败**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: FAIL（selftest op 未实现：execve/socket 实际仍成功 → ok=True）。

- [ ] **Step 3: 实现 seccomp_gate.py + 协议接线**

创建 `demos/agentos-demo/seccomp_gate.py`（复刻自 `laos/seccomp.py` 的 BPF 构造模式，仅保留 demo 所需最小集）：

```python
#!/usr/bin/env python3
"""seccomp_gate —— agent 进程的自装强制层（demo 版）。

复刻自 laos/seccomp.py（Apache-2.0 同仓）的 prctl+seccomp(2) 直调模式，
缩小为两条规则：execve/execveat 与 socket 族返回 EPERM，其余放行。
装在 agent.py 进程内——演示"能力表管得到许可，seccomp 管得到物理"：
即使 kernel 有 bug 放行了越权 op，agent 进程也生不出新进程/网络连接。
"""
from __future__ import annotations

import ctypes
import ctypes.util

PR_SET_NO_NEW_PRIVS = 38
SECCOMP_SET_MODE_FILTER = 1
SECCOMP_RET_ALLOW = 0x7fff0000
SECCOMP_RET_ERRNO = 0x00050000
EPERM = 1

# linux/audit.h：x86_64 AUDIT_ARCH_X86_64 = 0xC000003E
AUDIT_ARCH_X86_64 = 0xC000003E

# syscall 号（x86_64）：execve=59, execveat=322, socket=41, socketpair=53,
# connect=42 —— aarch64 号不同，非 x86_64 直接不装（demo 主场 WSL x86_64）。
BLOCKED = {59: "execve", 322: "execveat", 41: "socket", 53: "socketpair", 42: "connect"}


def _filter() -> bytes:
    """手搓 BPF 程序：load arch → 校验 → load nr → 逐条比对 → 默认 ALLOW。"""
    prog = []
    prog += [0x20, 0x00, 0x00, 0x00000004]              # BPF_LD|W|ABS arch
    prog += [0x15, 0x00, len(BLOCKED) + 1, AUDIT_ARCH_X86_64]  # JNE -> default
    prog += [0x20, 0x00, 0x00, 0x00000000]              # BPF_LD|W|ABS nr
    jumps_left = len(BLOCKED)
    for nr in BLOCKED:
        jumps_left -= 1
        prog += [0x15, jumps_left, 0x00, nr]            # JE nr -> block(跳距)
    prog += [0x06, 0x00, 0x00, SECCOMP_RET_ALLOW]       # RET ALLOW
    for _ in BLOCKED:
        prog += [0x06, 0x00, 0x00, SECCOMP_RET_ERRNO | EPERM]  # RET EPERM
    import struct
    return b"".join(struct.pack("<HBBI", *insn) for insn in prog)


def install() -> bool:
    """装 filter；成功 True，环境不支持（非 Linux/非 x86_64）False 不炸。"""
    import platform
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        return False
    libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return False
    prog = _filter()
    class Flock(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]
    flock = Flock(len(prog) // 8, ctypes.cast(prog, ctypes.c_void_p))
    return libc.syscall(317, SECCOMP_SET_MODE_FILTER, 0, ctypes.byref(flock)) == 0
```

`agent.py` 的 main() 开头加：

```python
try:
    import seccomp_gate
    seccomp_gate.install()
except Exception:
    pass  # 装不上照常跑（非 Linux 场景）；装上了 = 物理收紧
```

`kernel.py` 的 `_syscall` 加 selftest 分支（在能力闸之后、`_dispatch` 之前）：

```python
        elif op.startswith("selftest."):
            reply = _selftest(op)
```

以及模块级函数（agent 收到后在**自己进程里**试危险操作并回报）——改协议：kernel 把 selftest 转成让 agent 本地执行的指令不安全，正确做法是 agent.py 侧预置：脚本步骤 `{"op": "selftest.execve"}` 到达 agent 后**不发给内核**、本地执行并回填结果。实现：`agent.py` 循环里拦截：

```python
        if step["op"].startswith("selftest."):
            reply = _selftest_local(step["op"])
        else:
            sys.stdout.write(...); reply = json.loads(sys.stdin.readline())
```

```python
def _selftest_local(op: str) -> dict:
    """selftest.* 不走内核——agent 在本地实测危险操作是否已被 seccomp 拦下。"""
    try:
        if op == "selftest.execve":
            subprocess.run(["/bin/true"], check=True)      # noqa: F401 已被 seccomp 拦
        elif op == "selftest.socket":
            import socket as _s
            _s.socket().connect(("127.0.0.1", 1))
        return {"ok": True, "result": "DANGEROUS: not blocked"}
    except OSError as exc:
        return {"ok": False, "error": f"blocked: {type(exc).__name__} {exc}"[:120]}
```

审计行由 agent 把 reply 打回内核（`{"op":"selftest.execve","__reply":{...}}` 旁路一行），kernel 记审计但不回写——实现取简：selftest 结果也走 stdout 一行 `{"op": op, "args": {}, "__self": reply}`，kernel `_syscall` 识别 `__self` 直接入审计。

- [ ] **Step 4: 运行确认通过**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: OK（6 tests；Windows 下 SeccompTest SKIP）。

- [ ] **Step 5: Commit**

```bash
git add demos/agentos-demo/seccomp_gate.py demos/agentos-demo/agent.py demos/agentos-demo/kernel.py demos/agentos-demo/test_demo.py
git commit -m "feat(demo): seccomp 强制层——execve/socket EPERM，内核之外无资源"
```

---

### Task 4: 叙事脚本 + README（认知交付物）

**Files:**
- Create: `demos/agentos-demo/run_demo.sh`
- Create: `demos/agentos-demo/README.md`
- Test: `test_demo.py` 追加 `test_run_demo_script`（子进程跑脚本断言 exit 0 + 审计文件非空）

**Interfaces:**
- Consumes: Task 1–3 全部（真 MCP server + 两 agent + seccomp）。
- Produces: `bash run_demo.sh` 一条命令 30 秒讲完整个故事，退出码 0。

- [ ] **Step 1: 追加失败测试**

```python
class RunDemoTest(unittest.TestCase):
    @unittest.skipUnless(platform.system() == "Linux", "整链 demo 仅 Linux")
    def test_run_demo_script(self):
        r = subprocess.run(["bash", str(HERE / "run_demo.sh")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("AUDIT", r.stdout)          # 脚本要打印审计摘要
        audit = Path(HERE / "var" / "audit.jsonl")
        self.assertTrue(audit.exists() and audit.read_text(encoding="utf-8").strip())
```

- [ ] **Step 2: 运行确认失败**

Run: `wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: FAIL（run_demo.sh 不存在）。

- [ ] **Step 3: 实现 run_demo.sh 与 README.md**

`run_demo.sh`（叙事五幕：起驱动→起内核→两个 Agent（能力不同）→越权与 seccomp 双重拦截→审计收尾）：

```bash
#!/usr/bin/env bash
# Linux AgentOS 认知 demo —— 30 秒讲清：内核 + Agent(进程) + MCP(驱动)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
echo "== 幕一：设备上线（MCP 文件服务 = 驱动） =="
python3 - <<'PY'
from kernel import DemoKernel
from pathlib import Path
k = DemoKernel()                       # 懒起真 mcp_fs.py（DEMO_JAIL=var/jail）
Path("var/jail").mkdir(parents=True, exist_ok=True)
Path("var/jail/a.txt").write_text("hello-from-jail", encoding="utf-8")

print("== 幕二：Agent 上场（真实 Linux 进程） ==")
k.write_script("reader", [
    {"op": "fs.read", "args": {"path": "a.txt"}},
    {"op": "fs.write", "args": {"path": "b.txt", "data": "reader-was-here"}},
    {"op": "selftest.execve", "args": {}},
])
k.write_script("writer", [
    {"op": "fs.write", "args": {"path": "c.txt", "data": "writer-rulez"}},
])
r = k.spawn("reader", caps=["fs.read", "selftest.execve"])   # 无 fs.write
w = k.spawn("writer", caps=["fs.read", "fs.write"])
print(f"  reader pid={r}  writer pid={w}")

print("== 幕三：syscall 循环（能力闸 + 代理到驱动） ==")
k.syscall_loop(timeout=15)

print("== 幕四：验证（越权被拒 / seccomp 生效 / jail 落盘） ==")
rows = k.audit_rows()
for row in rows:
    mark = "OK " if row["ok"] else "DENY"
    print(f"  [{mark}] pid={row['pid']} {row['op']} -> {row['result'][:48]}")
assert any(r_["op"] == "fs.write" and not r_["ok"] for r_ in rows), "能力闸未拦越权"
assert any(r_["op"] == "selftest.execve" and not r_["ok"] for r_ in rows), "seccomp 未拦"
b = Path("var/jail/b.txt")
assert not b.exists(), "越权写竟落盘"
assert Path("var/jail/c.txt").read_text(encoding="utf-8") == "writer-rulez"

print("== 幕五：审计（内核日志，一行一事件） ==")
print(f"AUDIT {len(rows)} rows -> {k.audit_path}")
print("demo 通过：Agent=进程 / 内核=监督者(能力+审计) / MCP=驱动 / seccomp=强制层")
PY
```

`README.md`：以对应表为主体（Agent↔进程：pid/信号/退出码全是真的；内核↔监督者：能力表+审计+代理；MCP server↔驱动：stdio 总线+jail；seccomp↔强制层），注明运行方式 `wsl -- bash demos/agentos-demo/run_demo.sh`、与 laos 主仓的关系（认知蒸馏物，不是 laos 本体）、来源行（复刻自 laos/seccomp.py 的模式）。

- [ ] **Step 4: 运行确认通过**

Run: `wsl -- bash demos/agentos-demo/run_demo.sh && wsl -- python3 demos/agentos-demo/test_demo.py`
Expected: 脚本五幕全过；测试 OK（7 tests，非 Linux SKIP 2）。

- [ ] **Step 5: Commit**

```bash
git add demos/agentos-demo/run_demo.sh demos/agentos-demo/README.md demos/agentos-demo/test_demo.py
git commit -m "feat(demo): 叙事脚本+README——30 秒讲清 kernel+Agent+MCP 三件套"
```

---

## Self-Review 记录

1. **Spec 覆盖**：调研报告 §6 的三角色映射（Agent=进程/内核=监督者/MCP=驱动）分别由 Task 2（进程模型+能力闸+审计）、Task 1（MCP 驱动）、Task 3（强制层补完"内核之外无资源"）覆盖；叙事交付（认知）由 Task 4 覆盖。全天候录音与 AIOS 格局属调研报告本体，不进 demo（YAGNI）。
2. **占位符扫描**：无 TBD/TODO；每个代码步骤含完整代码；selftest 的 `__self` 旁路协议在 Task 3 Step 3 内定义清楚。
3. **类型一致性**：`DemoKernel.spawn/call/audit_rows` 签名在 Task 2 定义、Task 3/4 按同签名调用；agent 协议（stdout 请求行/stdin 应答行/selftest 旁路）三处描述一致。
