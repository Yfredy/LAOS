"""laosd —— Linux AgentOS 的内核（用户态实现）。

它不替代 Linux kernel，而是**架在 Linux kernel 之上的薄内核**：

    真 Linux kernel   : 线程调度、内存、namespace / cgroup / seccomp 强制隔离
    laosd（本文件）   : Agent 进程表、能力检查、MCP 驱动路由、审计、上下文配额

因此所有特权操作最终仍由 Linux 执行，laosd 只负责"允许不允许、记不记、
怎么路由"。这也是"Linux AgentOS = Linux kernel + Agent + MCP"里最务实的
一段：语义层自己写，强制层交给内核。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .branch import BranchTable
from .mcp import MCPClient, ToolSpec
from .risk import FleetLedger
from .sandbox import IsolationReport, Sandbox
from .scheduler import AgentScheduler

# --------------------------------------------------------------------------
# 能力（capability）—— 点分命名 + 通配，等价于 Linux 的 CAP_* 位图
# --------------------------------------------------------------------------


class CapabilitySet:
    """支持 `*`（全部）、`fs.*`（整个驱动）、`fs.read`（单条调用）三级粒度。"""

    def __init__(self, patterns: list[str] | None = None):
        self.patterns = set(patterns or [])

    def allows(self, tool: str) -> bool:
        if "*" in self.patterns:
            return True
        if tool in self.patterns:
            return True
        driver = tool.split(".", 1)[0]
        return f"{driver}.*" in self.patterns

    def __repr__(self) -> str:
        return f"CapabilitySet({sorted(self.patterns)})"

    def delegate(self, subset: list[str]) -> "CapabilitySet":
        """委派子集：结果必须 ⊆ 自身能力，越权即 ValueError（可委派不可提升）。"""
        cand = CapabilitySet(subset)
        for pat in cand.patterns:
            # 该模式必须能被 self 覆盖：要么 self 含 '*'，要么 self 含该模式，
            # 要么 self 含其驱动通配（如委派 fs.read 需 self 有 fs.* 或 fs.read）
            if "*" in self.patterns:
                continue
            if pat in self.patterns:
                continue
            driver = pat.split(".", 1)[0]
            if f"{driver}.*" in self.patterns:
                continue
            raise ValueError(f"cannot delegate {pat!r}: not granted to parent")
        return cand


# --------------------------------------------------------------------------
# PCB —— Agent 进程控制块
# --------------------------------------------------------------------------
@dataclass
class PCB:
    pid: int
    name: str
    caps: CapabilitySet
    state: str = "ready"  # ready | running | blocked | zombie | killed
    parent: int = 0
    created_at: float = field(default_factory=time.time)
    ctx: Any = None  # ContextManager
    stats: dict = field(default_factory=lambda: {"syscalls": 0, "denied": 0, "tokens": 0, "risk": 0})
    branch: str | None = None
    budget: int | None = None  # 最大 syscall 次数，None = 无限
    risk_cap: int | None = None  # 本 agent 的风险帽（Irreversibility Budget）

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("ctx", None)
        d["caps"] = sorted(self.caps.patterns)
        return d


# --------------------------------------------------------------------------
# 审计 —— 相当于 strace + auditd 的合体
# --------------------------------------------------------------------------
class AuditLog:
    def __init__(self, path: Path, mode: str = "w"):
        """mode='w' 表示每次 laosd 启动重写一次审计轨迹，便于 demo 复现；
        生产环境应传 'a' 做累积审计。"""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open(mode, encoding="utf-8")
        self.records: list[dict] = []

    def write(self, record: dict) -> None:
        self.records.append(record)
        self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# --------------------------------------------------------------------------
# 内核
# --------------------------------------------------------------------------
class AgentKernel:
    def __init__(
        self,
        workdir: Path,
        isolation: IsolationReport | None = None,
        audit_mode: str = "w",
        irreversibility_budget: int | None = None,
        confirm=None,
    ):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.drivers: dict[str, MCPClient] = {}
        self.syscall_table: dict[str, tuple[str, ToolSpec]] = {}  # tool -> (driver, spec)
        self.procs: dict[int, PCB] = {}
        self.audit = AuditLog(self.workdir / "audit.jsonl", mode=audit_mode)
        self.branches = BranchTable(self.workdir / "branches")
        self.sandbox = Sandbox(self.workdir)
        self.isolation = isolation or self.sandbox.report
        self._next_pid = 1000
        self._sched_lock = asyncio.Lock()
        self.scheduler = AgentScheduler()
        # driver 是单工 stdio 会话，同一 driver 的 RPC 必须串行（并发写会挂死）
        self._driver_locks: dict[str, asyncio.Lock] = {}
        self._agent_token_budget = int(os.environ.get("LAOS_AGENT_TOKENS", "0")) or None
        risk_budget = (
            irreversibility_budget
            if irreversibility_budget is not None
            else int(os.environ.get("LAOS_RISK_BUDGET")
                     or os.environ.get("LAOS_IRREV_BUDGET")
                     or "3")
        )
        self.risk = FleetLedger(
            budget=risk_budget,
            reserve=int(os.environ.get("LAOS_RISK_RESERVE", "1")),
        )
        self.confirm = confirm or self._cli_confirm
        # MCP Tasks（2026-07-28）：task 路径轮询 tasks/result 的总超时
        self.task_timeout = float(os.environ.get("LAOS_TASK_TIMEOUT", "30"))
        self.boot_at = time.time()
        # -- 内建 syscall 层（内核直供，不经 MCP 驱动）------------------------
        self._builtin_specs: dict[str, ToolSpec] = {
            "msg.send": ToolSpec(
                "msg.send", "向另一个 agent 的信箱投递消息",
                {"type": "object",
                 "properties": {"to_pid": {"type": "integer"},
                                "text": {"type": "string"}},
                 "required": ["to_pid", "text"]}),
            "msg.recv": ToolSpec("msg.recv", "收取并清空自己的信箱",
                                 {"type": "object", "properties": {}}),
            "msg.list": ToolSpec("msg.list", "列出所有信箱的积压情况",
                                 {"type": "object", "properties": {}}),
            "sys.delegate": ToolSpec(
                "sys.delegate", "把自身能力子集授予另一个 agent（TTL 按调用次数）",
                {"type": "object",
                 "properties": {"to_pid": {"type": "integer"},
                                "caps_subset": {"type": "array",
                                                "items": {"type": "string"}},
                                "ttl_calls": {"type": "integer", "minimum": 1}},
                 "required": ["to_pid", "caps_subset", "ttl_calls"]}),
        }
        self._builtin_impls: dict[str, Callable] = {
            "msg.send": self._impl_msg_send,
            "msg.recv": self._impl_msg_recv,
            "msg.list": self._impl_msg_list,
            "sys.delegate": self._impl_sys_delegate,
        }
        self._mailboxes: dict[int, list[dict]] = {}
        # 运行时能力委托：pid -> [{"caps": CapabilitySet, "remaining": int,
        #   "by": int}]；_effective_allows 每次经委托使用扣 1（TTL 按调用次数），
        # 委托者 kill 即全部撤销（_drop_delegations_by）
        self._delegations: dict[int, list[dict]] = {}

    # -- 兼容层：旧接口 irreversibility_budget 读写映射到车队账本 -----------
    # 注意 setter 改的是 risk.budget，因此同时影响 spawn 准入控制：
    # remaining <= reserve 时新 agent 一律拒绝进场
    @property
    def irreversibility_budget(self) -> int:
        return self.risk.remaining

    @irreversibility_budget.setter
    def irreversibility_budget(self, v: int) -> None:
        self.risk.budget = v

    # -- 驱动管理（insmod / rmmod）---------------------------------------
    def load_driver(self, name: str, argv: list[str], env: dict | None = None) -> MCPClient:
        # 驱动子进程经 sandbox 包装启动（Linux 上 unshare 隔离 + seccomp shim，
        # 跨平台降级原样）
        client = MCPClient(name, self.sandbox.wrap(argv), env=env)
        # server→client 请求（elicitation/create）走内核 confirm 路由：
        # 必须在 start()（initialize 握手）之前装好
        client.on_server_request = self._on_elicit
        client.start()
        # cgroup v2 资源上限：仅 root + cgroupfs 可写时生效，否则 None（降级）。
        # attach 目标是真实驱动进程（unshare --fork 的直接子进程），
        # cgroup 按进程树继承，其子孙（proc.exec 等）一并受限
        cgroup = self.sandbox.make_cgroup(f"drv-{name}")
        Sandbox.attach(cgroup, client.driver_pid)
        self.drivers[name] = client
        for tool in client.tools.values():
            self.syscall_table[tool.name] = (name, tool)
        self.audit.write(
            {
                "t": time.time(),
                "event": "driver_load",
                "driver": name,
                "tools": len(client.tools),
                "cgroup": str(cgroup) if cgroup else None,
                "driver_pid": client.driver_pid,
            }
        )
        return client

    def unload_driver(self, name: str) -> None:
        client = self.drivers.pop(name, None)
        if client:
            client.close()
            for tool in [t for t, (d, _) in self.syscall_table.items() if d == name]:
                self.syscall_table.pop(tool, None)
        self.audit.write({"t": time.time(), "event": "driver_unload", "driver": name})

    def close_all_drivers(self) -> None:
        for name in list(self.drivers):
            self.unload_driver(name)

    # -- 进程管理（fork / kill / ps）--------------------------------------
    def spawn(
        self,
        name: str,
        caps: list[str],
        ctx: Any,
        branch: str | None = None,
        parent: int = 0,
        budget: int | None = None,
        risk_cap: int | None = None,
    ) -> PCB:
        # 准入控制：车队风险剩余低于保留水位时拒绝新 agent 进场
        if not self.risk.can_admit():
            self.audit.write(
                {"t": time.time(), "event": "admission", "name": name,
                 "decision": "deny", "fleet_remaining": self.risk.remaining}
            )
            raise PermissionError(
                f"EACCES: fleet risk reserve not met "
                f"(remaining={self.risk.remaining}, reserve={self.risk.reserve})"
            )
        self._next_pid += 1
        pcb = PCB(
            pid=self._next_pid,
            name=name,
            caps=CapabilitySet(caps),
            ctx=ctx,
            branch=branch,
            parent=parent,
            budget=budget,
            risk_cap=risk_cap,
        )
        self.procs[pcb.pid] = pcb
        self.scheduler.register(pcb.pid, token_budget=self._agent_token_budget)
        self.audit.write(
            {"t": time.time(), "event": "spawn", "pid": pcb.pid, "name": name,
             "caps": caps, "risk_cap": risk_cap,
             "fleet_remaining": self.risk.remaining}
        )
        return pcb

    def kill(self, pid: int, sig: str = "SIGTERM") -> bool:
        pcb = self.procs.get(pid)
        if not pcb or pcb.state in ("zombie", "killed"):
            return False
        pcb.state = "killed"
        self.scheduler.retire(pid)
        # 委托者死亡即撤销其授出的一切委托（可委派不可提升，亦不可遗赠）
        self._drop_delegations_by(pid)
        self.audit.write({"t": time.time(), "event": "kill", "pid": pid, "sig": sig})
        return True

    def _drop_delegations_by(self, pid: int) -> None:
        """委托者死亡即撤销其授出的一切委托（可委派不可提升，亦不可遗赠）。"""
        for to_pid, lst in list(self._delegations.items()):
            kept = [d for d in lst if d["by"] != pid]
            if len(kept) != len(lst):
                self._delegations[to_pid] = kept
                self.audit.write({"t": time.time(), "event": "delegate_revoke",
                                  "by": pid, "to": to_pid})

    def ps(self) -> list[dict]:
        return [p.to_dict() for p in self.procs.values()]

    # -- 系统调用网关 -----------------------------------------------------
    async def syscall(self, pid: int, tool: str, args: dict | None = None,
                      task: bool = False) -> Any:
        """AgentOS 的核心入口，等价于 glibc 里的 syscall()。

        流程：解析 -> 查表 -> 进程状态检查 -> 能力检查 -> 预算检查
              -> 驱动调用 -> 审计 -> 返回

        task=True（MCP Tasks 2026-07-28）：驱动声明了 tasks capability 时走
        call_tool_task + task_result 异步路径，否则降级为同步路径（不是错误）。
        """
        from .mcp import CallResult
        from .validate import ValidationError, validate_args

        args = args or {}
        started = time.perf_counter()
        pcb = self.procs.get(pid)
        if pcb is None:
            return CallResult.fail("ESRCH: no such process")
        if pcb.state == "killed":
            return CallResult.fail("EACCES: process killed")

        # 查表：先 MCP 驱动表，miss 再查内核内建表（msg.* 等）；
        # 两处都 miss 才是 ENOSYS
        entry = self.syscall_table.get(tool)
        builtin_spec = self._builtin_specs.get(tool)
        if entry is None and builtin_spec is None:
            return self._deny(pcb, tool, args, started, "ENOSYS: no such syscall")
        driver_name = entry[0] if entry else None
        spec = entry[1] if entry else builtin_spec

        # 有效能力：自身 caps ∪ 未过期委托（MCP 与内建统一语义）；
        # consume=True 时扣减首个匹配委托的剩余额度
        if not self._effective_allows(pcb, tool, consume=True):
            return self._deny(pcb, tool, args, started, "EPERM: capability not granted")

        # 参数校验：dispatch 前由内核强制（堵 AIOS Tool Manager 无校验的洞）
        try:
            validate_args(spec.input_schema, args)
        except ValidationError as ve:
            return self._deny(pcb, tool, args, started, str(ve))

        # syscall 次数预算先于不可逆闸门：注定因 EDQUOT 被拒的调用
        # 不允许消耗车队风险预算（attempt-based pricing 见 risk.py 模块注释）
        if pcb.budget is not None and pcb.stats["syscalls"] >= pcb.budget:
            return self._deny(pcb, tool, args, started, "EDQUOT: syscall budget exhausted")

        # 不可逆闸门 2.0：车队级风险记账 + 每 agent 风险帽（Irreversibility Budget）
        if not spec.reversible:
            cost = max(1, spec.irreversibility_cost)
            if self.risk.remaining < cost:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: fleet risk budget exhausted")
            if pcb.risk_cap is not None and pcb.stats["risk"] + cost > pcb.risk_cap:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: agent risk cap exceeded")
            if spec.risk == "high" and not self.confirm(
                {"tool": tool, "args": args, "risk": spec.risk}
            ):
                return self._deny(pcb, tool, args, started,
                                  "EACCES: irreversible operation requires confirmation")
            self.risk.charge(pcb.pid, tool, cost)
            pcb.stats["risk"] += cost
            self.audit.write(
                {"t": time.time(), "event": "risk_spend", "pid": pcb.pid,
                 "tool": tool, "cost": cost,
                 "agent_spent": pcb.stats["risk"], "fleet_spent": self.risk.spent}
            )

        # 内建分支：内核直供的 syscall（msg.*），不经 MCP 驱动、无 driver 锁。
        # 与 MCP 路径共享同一道闸门链（caps -> validate -> EDQUOT -> 风险闸门）。
        if entry is None:
            result = self._builtin_impls[tool](pcb, args)
            elapsed_ms = (time.perf_counter() - started) * 1000
            pcb.stats["syscalls"] += 1
            self.audit.write(
                {"t": time.time(), "event": "syscall", "pid": pid, "agent": pcb.name,
                 "tool": tool, "args": args, "ok": result.ok,
                 "ms": round(elapsed_ms, 2), "result": result.text[:500],
                 "builtin": True}
            )
            return result

        # 驱动调用放进线程：stdio RPC 是阻塞的，不能卡住事件循环。
        # 同一 driver 的调用按设备互斥（单工 stdio 会话），不同 driver 可并行。
        # task 路径同样包在同一把 driver 锁里：call_tool_task 发起 + task_result
        # 轮询必须独占单工会话，与同步路径互斥。
        pcb.state = "running"
        try:
            async with self._driver_locks.setdefault(driver_name, asyncio.Lock()):
                client = self.drivers[driver_name]
                if task and client.capabilities.get("tasks"):
                    def _run_task():
                        task_id = client.call_tool_task(tool, args)
                        return client.task_result(task_id, timeout_s=self.task_timeout)
                    result = await asyncio.to_thread(_run_task)
                else:
                    result = await asyncio.to_thread(client.call_tool, tool, args)
        except Exception as exc:
            result = CallResult.fail(f"EIO: driver {driver_name} failed: {exc}")
        finally:
            pcb.state = "ready" if pcb.state != "killed" else "killed"

        # Stale Context：fs.read 记录观察；fs.write/append 失效其他 agent 的观察
        if result.ok and hasattr(pcb.ctx, "observe"):
            if tool == "fs.read" and "path" in args:
                pcb.ctx.observe(args["path"], self._digest(result.text))
            elif tool in ("fs.write", "fs.append") and "path" in args:
                for other in self.procs.values():
                    if other.pid != pcb.pid and hasattr(other.ctx, "invalidate"):
                        other.ctx.invalidate(args["path"])

        elapsed_ms = (time.perf_counter() - started) * 1000
        pcb.stats["syscalls"] += 1
        self.audit.write(
            {
                "t": time.time(),
                "event": "syscall",
                "pid": pid,
                "agent": pcb.name,
                "tool": tool,
                "driver": driver_name,
                "args": args,
                "ok": result.ok,
                "ms": round(elapsed_ms, 2),
                "result": result.text[:500],
            }
        )
        return result

    # -- 有效能力：自身 caps + 未过期委托（consume=True 时扣 TTL 额度）------
    def _effective_allows(self, pcb: PCB, tool: str, consume: bool = False) -> bool:
        if pcb.caps.allows(tool):
            return True
        for d in self._delegations.get(pcb.pid, []):
            if d["remaining"] > 0 and d["caps"].allows(tool):
                if consume:
                    d["remaining"] -= 1
                return True
        return False

    # -- 内建实现（内核直供，不经 MCP 驱动）--------------------------------
    MAILBOX_MAX = 16
    MSG_MAX_CHARS = 4096

    def _impl_msg_send(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        to_pid = int(args["to_pid"])
        text = str(args["text"])
        if to_pid not in self.procs:
            return CallResult.fail(f"ESRCH: no such process {to_pid}")
        if len(text) > self.MSG_MAX_CHARS:
            return CallResult.fail(f"EMSGSIZE: {len(text)} > {self.MSG_MAX_CHARS}")
        box = self._mailboxes.setdefault(to_pid, [])
        if len(box) >= self.MAILBOX_MAX:
            return CallResult.fail(f"ENOBUFS: mailbox full for {to_pid}")
        box.append({"from": pcb.pid, "text": text, "t": time.time()})
        self.audit.write({"t": time.time(), "event": "msg", "from": pcb.pid,
                          "to": to_pid, "bytes": len(text)})
        return CallResult.ok_text(f"OK sent to pid={to_pid}")

    def _impl_msg_recv(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        box = self._mailboxes.get(pcb.pid, [])
        self._mailboxes[pcb.pid] = []
        if not box:
            return CallResult.ok_text("(empty)")
        lines = [f"from={m['from']}: {m['text']}" for m in box]
        return CallResult.ok_text("\n".join(lines))

    def _impl_msg_list(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        rows = [f"pid={pid}: {len(box)} pending"
                for pid, box in self._mailboxes.items() if box]
        return CallResult.ok_text("\n".join(rows) or "(no pending messages)")

    def _impl_sys_delegate(self, pcb: PCB, args: dict) -> "CallResult":
        # CapabilitySet 就定义在本模块，直接引用，无循环导入
        from .mcp import CallResult
        to_pid = int(args["to_pid"])
        subset = list(args["caps_subset"])
        ttl = int(args["ttl_calls"])
        if to_pid not in self.procs:
            return CallResult.fail(f"ESRCH: no such process {to_pid}")
        if ttl < 1:
            return CallResult.fail("EINVAL: ttl_calls must be >= 1")
        try:
            delegated = pcb.caps.delegate(subset)
        except ValueError as exc:
            return CallResult.fail(f"EPERM: {exc}")
        self._delegations.setdefault(to_pid, []).append(
            {"caps": delegated, "remaining": ttl, "by": pcb.pid})
        self.audit.write({"t": time.time(), "event": "delegate", "from": pcb.pid,
                          "to": to_pid, "caps": sorted(delegated.patterns), "ttl": ttl})
        return CallResult.ok_text(
            f"OK delegated {len(delegated.patterns)} caps to pid={to_pid} (ttl={ttl} calls)")

    def _deny(self, pcb: PCB, tool: str, args: dict, started: float, err: str):
        from .mcp import CallResult

        pcb.stats["denied"] += 1
        self.audit.write(
            {
                "t": time.time(),
                "event": "syscall",
                "pid": pcb.pid,
                "agent": pcb.name,
                "tool": tool,
                "args": args,
                "ok": False,
                "ms": round((time.perf_counter() - started) * 1000, 2),
                "result": err,
            }
        )
        return CallResult.fail(err)

    def _on_elicit(self, method: str, params: dict) -> dict:
        """驱动 elicitation/create → 内核 confirm（人类在环，协议内机制）。"""
        if method != "elicitation/create":
            raise RuntimeError(f"ENOSYS: client does not support {method}")
        ok = self.confirm({"tool": "elicitation",
                           "message": params.get("message", ""),
                           "risk": "high"})
        return {"action": "accept" if ok else "decline", "value": ""}

    @staticmethod
    def _cli_confirm(op: dict) -> bool:
        # 默认准入回调：CLI 交互确认；非交互环境（EOF）默认拒绝
        try:
            return input(f"allow {op['tool']}? [y/N] ").lower() == "y"
        except EOFError:
            return False

    @staticmethod
    def _digest(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    # -- Stale Context：branch commit 批量失效 -----------------------------
    def on_branch_committed(self, branch: str, paths: list[str]) -> None:
        """分支提交改变了父分支内容：所有观察过这些路径的上下文失效。

        commit 的 paths 是分支内相对路径（如 workspace/hosts），虚拟化为
        /{branch}/{path} —— 观察簿的 key 正是虚拟路径，而 invalidate 对
        未观察过的路径是无操作，因此直接按完整虚拟路径全量广播即可。
        """
        for virt in (f"/{branch}/{p}".replace("\\", "/") for p in paths):
            for pcb in self.procs.values():
                if hasattr(pcb.ctx, "invalidate"):
                    pcb.ctx.invalidate(virt)
        self.audit.write(
            {"t": time.time(), "event": "stale_broadcast", "branch": branch,
             "paths": len(paths)}
        )

    # -- 调度器：LLM 是最贵的资源，也要有时间片 ---------------------------
    def scheduler_ctx(self) -> "AgentScheduler":
        # 保留兼容接口；实际调度由 self.scheduler 在 agent._do_syscall 中驱动
        return self.scheduler

    # -- 观测 -------------------------------------------------------------
    def lsmod(self) -> list[dict]:
        return [
            {
                "driver": name,
                "pid": c.pid,
                "driver_pid": c.driver_pid,
                "tools": [t.name for t in c.tools.values()],
            }
            for name, c in self.drivers.items()
        ]

    def syscalls(self) -> list[str]:
        return sorted(self.syscall_table)

    def status(self) -> dict:
        return {
            "uptime_s": round(time.time() - self.boot_at, 2),
            "isolation": str(self.isolation),
            "drivers": len(self.drivers),
            "syscalls": len(self.syscall_table),
            "processes": len(self.procs),
            "branches": self.branches.list(),
            "audit_records": len(self.audit.records),
        }

    def shutdown(self) -> None:
        self.close_all_drivers()
        self.audit.write({"t": time.time(), "event": "shutdown"})
        self.audit.close()
