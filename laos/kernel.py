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
import gzip
import hashlib
import json
import os
import posixpath
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from . import judge
from .branch import BranchTable
from .jitmem import Curator
from .mcp import MCPClient, ToolSpec
from .memory import MemoryStore
from .risk import FleetLedger
from .sandbox import IsolationReport, Sandbox
from .scheduler import AgentScheduler

# --------------------------------------------------------------------------
# Jev 机器预审问句（Task 3：criteria 式两段——指示段 + 判据段）-----------
#
# 模板占位 {tool}/{args}/{agent} 与 _jev_prejudge 实参一一对应（.format
# 渲染；判据文本不得引入额外花括号）。判据段钉住 deny 方向 = 拒绝执行。
# 校准台 scripts/calibrate_judge.py import 本常量复刻同一问句（此前是
# 按源码逐字复刻，提常量后改字面自动跟随）。方法论源自 jev-chat-jarvis
# questions.py（MIT），题面按 laos 语义重写；判据文本刻意避开
# judge.DENY_WORDS（"危险/泄露隐私"等）——RuleBackend 只扫问句关键词，
# 问句自带 deny 词会让规则后端对预审无差别全拒
PREJUDGE_JUDGE_QUESTION = (
    "允许执行 {tool} {args} 吗？agent={agent}。只依据工具名、参数与 "
    "agent 身份判断：操作是否落在该 agent 的任务域内、破坏面是否可逆、"
    "是否外发敏感数据。\n"
    "判“是”（allow，放行）当：操作在该 agent 的任务域内，且影响可逆或"
    "已隔离（jail 内、临时目录、构建产物），不外发敏感数据；"
    "判“否”（deny，拒绝执行）当：破坏面不可逆（覆写系统盘、清空根目录、"
    "改分区表）、越出任务域（动与任务无关的系统路径或他人数据）、或把"
    "凭据/隐私发往外部，任一命中即否。"
)

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
    task_scope: list[str] | None = None  # 意图驱动的虚拟路径前缀白名单（空/None = 不限）

    def to_dict(self) -> dict:
        # asdict 会深拷贝全部字段，而 ctx 是"活的" ContextManager（demo 线程
        # 还在往窗口追加消息）：深拷贝既慢（1s 轮询 × 每 agent）又可能撞上
        # RuntimeError。用 replace 把 ctx 置空让 asdict 根本不触碰它，
        # 输出形状不变（无 ctx 键，caps 为排序列表）。
        d = asdict(replace(self, ctx=None))
        d.pop("ctx", None)
        d["caps"] = sorted(self.caps.patterns)
        return d


# --------------------------------------------------------------------------
# 审计 —— 相当于 strace + auditd 的合体
# --------------------------------------------------------------------------
class AuditLog:
    # 归档段命名：audit-<UTC日期>-<轮转代 n>.jsonl.gz（设计 §6.2）——n 单调
    # 递增即轮转代，开机扫描续代，跨 boot 不重复。
    _ARCHIVE_RE = re.compile(r"^audit-\d{8}-(\d+)\.jsonl\.gz$")

    def __init__(self, path: Path, mode: str = "w"):
        """mode='w' 表示每次 laosd 启动重写一次审计轨迹，便于 demo 复现；
        生产环境应传 'a' 做累积审计。"""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open(mode, encoding="utf-8")
        self.records: list[dict] = []
        # 写锁（终审 C1）：阻塞型内建（evolve.run）在 worker 线程里落
        # event:"evolve" 行，与循环线程的 syscall 记账并发写——盖章/入列/
        # 落盘三步必须整体互斥，seq==下标 不变式与整行完整性由此钉死，
        # 也为后续一切阻塞型内建兜底
        self._wlock = threading.Lock()
        # 轮转代数（file_epoch，设计 §6.2）：换代时 records 清零、seq 复位
        # 归零，epoch +1——消费方（laosweb 前端）必须以 (epoch, seq) 复合键
        # 去重，轮转后同 seq 的新事件才不会被误判重复。开机扫已有归档段
        # 从 max 代 +1 续起：重启换内核后新代的键也不会与旧归档碰撞。
        self.epoch = 0
        for p in self.path.parent.glob("audit-*.jsonl.gz"):
            m = self._ARCHIVE_RE.match(p.name)
            if m:
                self.epoch = max(self.epoch, int(m.group(1)) + 1)
        # mode='a' 跨 boot 键语义（终审 T3-2）：开机时当前文件已有未轮转
        # 内容 → 那是上一 boot 的代（epoch 已盖在行内），本 boot 换新代
        # 续写，同文件不再出现重复 (epoch, seq) 键。取文件尾行已盖 epoch
        # +1（mode='w' 开机即截断、size=0 天然不触发；尾行读不出 epoch 的
        # 非空文件按"至少被 0 号代之后的某代占用"保守 bump 到 1）。
        if self.path.stat().st_size > 0:
            tail = self._tail_epoch()
            self.epoch = max(self.epoch,
                             tail + 1 if tail is not None else 1)

    def _tail_epoch(self) -> int | None:
        """有界 tail 读：末 64KB 内最后一条可解析行的 epoch 戳（无 → None）。"""
        with self.path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            tail = fh.read().decode("utf-8", errors="replace")
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec.get("epoch"), int):
                return rec["epoch"]
        return None

    def write(self, record: dict) -> None:
        # 单调序号在 append 前盖章：seq == 记录在 self.records 里的下标，
        # 审计消费者（laosweb 前端去重键）不必再从"总数-窗口"反推全局序号
        # —— 观测线程采样 status 与切片 audit 之间若混入新记录，反推值会
        # 漂移导致前端重复插入。epoch 与 seq 同点盖章：轮转后 records 清零、
        # seq 复位，前端以 (epoch, seq) 复合键去重才不把新代同 seq 事件
        # 误判重复（§6.2）。线程安全（终审 C1）：evolve.run 走 worker 线程
        # 后"GIL 下 len+append 足够原子"的假设作废，锁内完成三步。
        with self._wlock:
            record["epoch"] = self.epoch
            record["seq"] = len(self.records)
            self.records.append(record)
            self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._fh.flush()

    def rotate(self) -> None:
        """轮转原语（设计 §6.2）：当前文件 gzip 归档 → 重开空文件继续追加。

        归档名 audit-<UTC日期>-<epoch>.jsonl.gz 内嵌单调轮转代 n；records
        清零即 seq 复位归零、epoch +1——消费方（laosweb 前端）以
        (epoch, seq) 复合键去重，轮转后同 seq 的新事件不会被误判重复。
        64MB 水位触发与归档保留策略（7 天 / 256MB）由后续轮转接线波次
        挂上；本方法只钉死"轮转发生时"的代数与 seq 语义。

        异常恢复（终审 T3-1，try/finally 语义保底 reopen）：归档/重开任
        一步抛错时，以追加模式重开原文件后原样上抛——数据未丢、代数未
        变、下次可重试；半途归档残件清掉（防开机扫档误续代）。审计断流
        是比轮转失败更大的错，句柄必须始终可用。
        """
        self._fh.flush()
        self._fh.close()
        archive = None
        try:
            stamp = time.strftime("%Y%m%d", time.gmtime())
            archive = self.path.with_name(f"audit-{stamp}-{self.epoch}.jsonl.gz")
            if self.path.exists():
                with self.path.open("rb") as src, open(archive, "wb") as raw:
                    with gzip.GzipFile(fileobj=raw, mode="wb") as out:
                        shutil.copyfileobj(src, out)
                    raw.flush()
                    os.fsync(raw.fileno())
                self.path.unlink()
            new_fh = self.path.open("w", encoding="utf-8")
        except Exception:
            if archive is not None and archive.exists():
                try:
                    archive.unlink()
                except OSError:
                    pass  # 残件清理是尽力而为；主目标是指柄可用
            self._fh = self.path.open("a", encoding="utf-8")
            raise
        self._fh = new_fh
        self.records.clear()
        self.epoch += 1

    def close(self) -> None:
        self._fh.close()


# --------------------------------------------------------------------------
# 内核
# --------------------------------------------------------------------------
# 阻塞型内建 syscall（终审 C1）：impl 内是阻塞子进程调用（evolve.run 默认
# 1800s），内联派发等于把整个事件循环——其余 agent 的 syscall、调度器、
# confirm 回调——押给一次作业。此集合内的派发走 asyncio.to_thread 让出
# 循环（MCP 驱动路径同款）；msg.*/mem.* 纯内存，保持内联不付线程切换。
# 前置闸门全部留在循环线程，事后记账（stats/audit）两条路径同形。
_BLOCKING_BUILTINS = frozenset({"evolve.run"})


class AgentKernel:
    def __init__(
        self,
        workdir: Path,
        isolation: IsolationReport | None = None,
        audit_mode: str = "w",
        irreversibility_budget: int | None = None,
        confirm=None,
        sentinel: "Sentinel | None" = None,      # 动作闸 opt-in（nanoMuse 采纳，
                                                 # None=字节级不变；见 laos/sentinel.py）
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
        # 可靠性预算（Patient Bytes）：per-agent 派发后失败次数上限，耗尽即挂起；
        # "0" 表示不限（or None）。内核层 _deny（EPERM/EDQUOT 等）不算失败。
        self._agent_err_budget = int(os.environ.get("LAOS_AGENT_ERR_BUDGET", "3")) or None
        # 调度观测缓存：agent 退出即被 retire 出调度器（防饿死其余 agent），
        # 这里留存每个 pid 末次派发后的调度视图行，供运行报告在进程退出后仍可观测。
        self.sched_view: dict[int, dict] = {}
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
        self.sentinel = sentinel
        # Jev 机器预审（System-One 快问快答，opt-in）：LAOS_JEV_BACKEND=
        # none（默认）时不构造任何后端、self.judge=None，确认横幅行为
        # 逐字节不变；显式选择 rule/cloud/local 才接 Task 2 的判断器
        if os.environ.get("LAOS_JEV_BACKEND", "none").strip().lower() != "none":
            self.judge = judge.select()
        else:
            self.judge = None
        # MCP Tasks（2026-07-28）：task 路径轮询 tasks/result 的总超时
        self.task_timeout = float(os.environ.get("LAOS_TASK_TIMEOUT", "30"))
        self.boot_at = time.time()
        # 个人记忆库（episodic memory）：mem.* 内建 syscall 的存储层，
        # JSONL 追加日志放 workdir，与审计/分支同一套"一切皆文件"取向
        self.memory = MemoryStore(self.workdir / "memory.jsonl")
        # Just-in-Time 记忆整理器（read-time curation，arXiv:2609.27334
        # 转译落地）：任务到来时 mem.curate 即时整理，任务成败经 mem.outcome
        # 回填驱动检索权重自适应；只读 memory，不压缩不删除任何已入库记忆
        self.mem_curator = Curator(self.memory)
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
            "mem.remember": ToolSpec(
                "mem.remember", "把一条事实/事件写入个人记忆库",
                {"type": "object",
                 "properties": {"kind": {"type": "string"},
                                "text": {"type": "string"},
                                "tags": {"type": "array",
                                         "items": {"type": "string"}}},
                 "required": ["kind", "text"]},
                reversible=True, risk="low"),
            "mem.recall": ToolSpec(
                "mem.recall", "按相关度检索个人记忆库（bigram Jaccard + 标签 + 时间）",
                {"type": "object",
                 "properties": {"query": {"type": "string"},
                                "k": {"type": "integer", "minimum": 1}},
                 "required": ["query"]},
                reversible=True, risk="low"),
            "mem.forget": ToolSpec(
                "mem.forget", "按 id 从个人记忆库删除一条记忆",
                {"type": "object",
                 "properties": {"id": {"type": "integer"}},
                 "required": ["id"]},
                reversible=True, risk="low"),
            "mem.stats": ToolSpec(
                "mem.stats", "个人记忆库统计（总数 / 按 kind 分布）",
                {"type": "object", "properties": {}},
                reversible=True, risk="low"),
            "mem.curate": ToolSpec(
                "mem.curate",
                "Just-in-Time 记忆整理：任务到来时按当前任务检索并即时整理"
                "相关记忆为紧凑上下文（read-time curation，不压缩库内原文）",
                {"type": "object",
                 "properties": {"task": {"type": "string"},
                                "k": {"type": "integer", "minimum": 1}},
                 "required": ["task"]},
                reversible=True, risk="low"),
            "mem.outcome": ToolSpec(
                "mem.outcome",
                "回填任务成败（配合 mem.curate 的 payload_id），驱动 JIT "
                "记忆检索权重自适应（即时 reward，时间隔为零）",
                {"type": "object",
                 "properties": {"payload_id": {"type": "integer"},
                                "success": {"type": "boolean"}},
                 "required": ["payload_id", "success"]},
                reversible=True, risk="low"),
            "evolve.run": ToolSpec(
                "evolve.run",
                "受治理的进化优化作业（OpenEvolve 后端，重依赖 venv 子进程隔离；"
                "target/evaluator 须在 var/rsi/jobs/ 允许根内）",
                {"type": "object",
                 "properties": {"target": {"type": "string"},
                                "evaluator": {"type": "string"},
                                "iterations": {"type": "integer",
                                               "minimum": 1}},
                 "required": ["target", "evaluator", "iterations"]},
                reversible=True, risk="medium"),
        }
        self._builtin_impls: dict[str, Callable] = {
            "msg.send": self._impl_msg_send,
            "msg.recv": self._impl_msg_recv,
            "msg.list": self._impl_msg_list,
            "sys.delegate": self._impl_sys_delegate,
            "mem.remember": self._impl_mem_remember,
            "mem.recall": self._impl_mem_recall,
            "mem.forget": self._impl_mem_forget,
            "mem.stats": self._impl_mem_stats,
            "mem.curate": self._impl_mem_curate,
            "mem.outcome": self._impl_mem_outcome,
            "evolve.run": self._impl_evolve_run,
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
        task_scope: list[str] | None = None,
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
            task_scope=list(task_scope) if task_scope else None,
        )
        self.procs[pcb.pid] = pcb
        self.scheduler.register(pcb.pid, token_budget=self._agent_token_budget,
                                err_budget=self._agent_err_budget)
        # 观测缓存以 spawn 时的初始行打底：从未成功派发过的 agent（每次都被
        # 内核 _deny）也要能出现在调度快照里
        self.sched_view[pcb.pid] = next(
            r for r in self.scheduler.snapshot() if r["pid"] == pcb.pid)
        self.audit.write(
            {"t": time.time(), "event": "spawn", "pid": pcb.pid, "name": name,
             "caps": caps, "risk_cap": risk_cap, "task_scope": task_scope,
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
        # Sentinel 污点随进程退出清除（污点的唯一清除通道；opt-in 零改动）
        if self.sentinel is not None:
            self.sentinel.untaint(pid)
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
        # 先快照再迭代：HTTP 观测线程读 ps() 的同时 demo 线程可能 spawn
        # （往 self.procs 插入），直接迭代 dict 视图会
        # RuntimeError: dictionary changed size during iteration
        return [p.to_dict() for p in list(self.procs.values())]

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

        # 意图收窄（task_scope）：能力说"能读文件"，任务说"读哪些文件"。
        # 仅当 PCB 声明了白名单且本次调用带 path 参数时强制：虚拟路径必须
        # 先归一化再与白名单前缀做分隔符收边匹配，否则 EACCES —— Oracle Labs
        # 思想：能力随任务意图收窄，而非静态授权一刀切。
        if pcb.task_scope and "path" in args:
            # 先归一化再匹配：.. / 重复斜杠不得借道越过任务边界（虚拟路径
            # 是 jail 相对路径且无符号链接，normpath 归一化安全）；
            # 前缀必须以分隔符收边（/workspace/host 不得准入 /workspace/hosts）
            norm = posixpath.normpath(str(args["path"]))
            allowed = any(
                norm == p or norm.startswith(p if p.endswith("/") else p + "/")
                for p in pcb.task_scope
            )
            if not allowed:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: outside task scope")

        # pkg 作用域：屏幕操控与应用管理限制在白名单 App（task_scope 的
        # pkg:<package> 条目）——apps.*（launch/close）与 screen.* 同闸
        pkg_scopes = [s[4:] for s in (pcb.task_scope or []) if s.startswith("pkg:")]
        if pkg_scopes and tool.startswith(("screen.", "apps.")) and "pkg" in args:
            pkg = str(args["pkg"])
            if not any(pkg == p or pkg.startswith(p + ".") for p in pkg_scopes):
                return self._deny(pcb, tool, args, started,
                                  "EACCES: outside task scope")

        # 参数校验：dispatch 前由内核强制（堵 AIOS Tool Manager 无校验的洞）
        try:
            validate_args(spec.input_schema, args)
        except ValidationError as ve:
            return self._deny(pcb, tool, args, started, str(ve))

        # syscall 次数预算先于不可逆闸门：注定因 EDQUOT 被拒的调用
        # 不允许消耗车队风险预算（attempt-based pricing 见 risk.py 模块注释）
        if pcb.budget is not None and pcb.stats["syscalls"] >= pcb.budget:
            return self._deny(pcb, tool, args, started, "EDQUOT: syscall budget exhausted")

        # Sentinel 动作闸（opt-in）：六级判定在既有闸门之后、不可逆闸之前；
        # ask=走既有 confirm 回调（grants 先查，覆盖则免问）；deny=EDENIED。
        # 出站工具按不可逆评估（信息离 pid 域不可收回——brief 测试锚点
        # "msg.send 不可逆 → risk-mode ask"）；spec.reversible 本身不动，
        # 既有风险记账口径零变化。sentinel=None 时整段零执行零审计。
        if self.sentinel is not None:
            from .sentinel import Assessment
            egress = tool in self.sentinel.cfg.egress_tools
            assessment = Assessment(
                tool=tool, risk=getattr(spec, "risk", "low"),
                reversible=getattr(spec, "reversible", True) and not egress,
                reads_private=tool in self.sentinel.cfg.private_tools,
                egress=egress)
            decision = self.sentinel.decide(
                assessment, tainted=self.sentinel.is_tainted(pid))
            grant_gid = None
            if decision.action == "deny":
                return self._deny(pcb, tool, args, started,
                                  f"EDENIED: sentinel {decision.reason}")
            if decision.action == "ask":
                # grants 只对普通 ask 生效；终审警告（grant_scopes 仅含 once
                # 档）恒走人类 confirm——nanoMuse "warnings 永不被 grant 覆盖"
                grant_gid = None
                if set(decision.grant_scopes) & {"session", "always"}:
                    grant_gid = self.sentinel.grants.covers(tool)
                if grant_gid is None and not self.confirm(
                        {"tool": tool, "args": args,
                         "sentinel": decision.reason}):
                    return self._deny(pcb, tool, args, started,
                                      "EACCES: sentinel requires confirmation")
            self.audit.write({"t": time.time(), "event": "sentinel",
                              "pid": pid, "tool": tool,
                              "decision": decision.action,
                              "reason": decision.reason, "grant": grant_gid})
            # 闸门通用置污（F1）：放行即置——reads_private 由 private_tools
            # 单点派生，不再散在 impl 内（读面清单与实现脱节会漏 taint，
            # 如 mic.segments 曾因幽灵名 mic.read 而读后不置污）
            if assessment.reads_private:
                self.sentinel.mark_private_read(pid)

        # 不可逆闸门 2.0：车队级风险记账 + 每 agent 风险帽（Irreversibility Budget）
        if not spec.reversible:
            cost = max(1, spec.irreversibility_cost)
            if self.risk.remaining < cost:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: fleet risk budget exhausted")
            if pcb.risk_cap is not None and pcb.stats["risk"] + cost > pcb.risk_cap:
                return self._deny(pcb, tool, args, started,
                                  "EACCES: agent risk cap exceeded")
            if spec.risk == "high":
                # Jev 机器预审（opt-in）：人类确认横幅先给判断器看一眼。
                # none/未启用时返回 "ask"，confirm 流程逐字节不变
                prejudge = self._jev_prejudge(pcb, tool, args, started)
                if prejudge == "deny":
                    return self._deny(pcb, tool, args, started,
                                      "EDENIED: denied by jev prejudge")
                if prejudge != "bypass" and not self.confirm(
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
        # 与 MCP 路径共享同一道闸门链（caps -> task_scope -> validate -> EDQUOT -> 风险闸门），
        # 并与 MCP 路径共用函数尾部统一的可靠性记账（见下方单一收口）。
        if entry is None:
            impl = self._builtin_impls[tool]
            # 阻塞型内建走线程（终审 C1）：evolve.run 的子进程默认 1800s，
            # 内联派发会冻死事件循环；集合外的 msg.*/mem.* 纯内存保持
            # 内联。闸门链在前、记账在后，两条路径行为完全一致。
            if tool in _BLOCKING_BUILTINS:
                result = await asyncio.to_thread(impl, pcb, args)
            else:
                result = impl(pcb, args)
            elapsed_ms = (time.perf_counter() - started) * 1000
            pcb.stats["syscalls"] += 1
            self.audit.write(
                {"t": time.time(), "event": "syscall", "pid": pid, "agent": pcb.name,
                 "tool": tool, "args": args, "ok": result.ok,
                 "ms": round(elapsed_ms, 2), "result": result.text[:500],
                 "builtin": True}
            )
        else:
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

            # 隐私红线：成功派发到驱动的每一次 mic.* syscall 都额外落一条
            # event:"mic" 审计记录（被内核 _deny 拒绝的调用由 _deny 补记，
            # denied:true）——录音行为无论成败都必须可追责、可计数
            if tool.startswith("mic."):
                self.audit.write({"t": time.time(), "event": "mic",
                                  "pid": pid, "tool": tool, "ok": result.ok,
                                  "denied": False})

        # 可靠性记账（Patient Bytes）——builtin 与 MCP 两条派发路径的唯一收口：
        # 审计写入之后、返回之前。_deny 的内核裁决（EPERM/EDQUOT/EACCES）不经此处；
        # 驱动返回的 isError=True（如 EDENIED）属于 agent 的失败尝试，照记。
        self.scheduler.note_outcome(pid, result.ok)
        # 顺手刷新调度观测缓存（agent 退出 retire 后 snapshot 不可见，见 sched_view）
        self.sched_view.update({r["pid"]: r for r in self.scheduler.snapshot()})
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

    # -- Jev 机器预审：确认横幅的 System-One 快问快答（opt-in）-------------
    JEV_AUTOGATE_MIN_DEFAULT = 0.95

    def _jev_prejudge(self, pcb: PCB, tool: str, args: dict,
                      started: float) -> str:
        """risk=high 确认横幅的机器预审：先问判断器，再决定问不问人。

        仅当显式选择后端（self.judge 非 None，即 LAOS_JEV_BACKEND != none）
        且设置了 LAOS_JEV_AUTOGATE 或 LAOS_JEV_PREVIEW 时介入；每次预审
        写一条 event:"jev" 审计（放行与拒绝双路径，仿 event:"mic" 红线）。
        返回三态：

            "deny"    机器否决 → 调用方 _deny（EDENIED），不再惊动人类
            "bypass"  allow 且置信 ≥ LAOS_JEV_AUTOGATE_MIN 且 AUTOGATE=1
                      → 跳过人类 confirm 直接放行（风险记账照常）
            "ask"     回落人类确认（低置信 / 仅预览 / 后端故障 fail-safe）
        """
        autogate = judge.env_flag("LAOS_JEV_AUTOGATE")
        if self.judge is None or not (autogate
                                      or judge.env_flag("LAOS_JEV_PREVIEW")):
            return "ask"
        try:
            result = self.judge.noul(
                "内核高风险 syscall 确认横幅预审",
                PREJUDGE_JUDGE_QUESTION.format(tool=tool, args=args,
                                               agent=pcb.name),
            )
        except Exception:
            # fail-safe：判断后端故障（网络/缺 key 等）不炸内核链路，
            # 回落人类确认；审计仍留痕（verdict="error"）
            self.audit.write(
                {"t": time.time(), "event": "jev", "pid": pcb.pid,
                 "tool": tool, "verdict": "error", "confidence": 0.0,
                 "autogate": autogate}
            )
            return "ask"
        self.audit.write(
            {"t": time.time(), "event": "jev", "pid": pcb.pid, "tool": tool,
             "verdict": result.verdict,
             "confidence": round(result.confidence, 3),
             "autogate": autogate}
        )
        if result.verdict == "deny":
            return "deny"
        min_conf = float(os.environ.get(
            "LAOS_JEV_AUTOGATE_MIN", self.JEV_AUTOGATE_MIN_DEFAULT))
        if (autogate and result.verdict == "allow"
                and result.confidence >= min_conf):
            return "bypass"
        return "ask"

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

    # -- mem.* 内建实现：个人记忆库（episodic memory）----------------------
    MEM_RECALL_DEFAULT_K = 5

    def _impl_mem_remember(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        rec = self.memory.remember(
            str(args["kind"]), str(args["text"]),
            tags=[str(t) for t in args.get("tags", [])],
            origin="agent", origin_pid=pcb.pid)
        if rec is None:
            # Jev 入库预审拒绝（装配层给 memory 注入 judge 时可能返回
            # None，Task 5 装配代理 JevGatedMemory）：对 agent 诚实回
            # EDENIED 并留审计，而不是在 rec["id"] 上炸 TypeError
            self.audit.write({"t": time.time(), "event": "memory",
                              "op": "remember", "pid": pcb.pid,
                              "kind": str(args["kind"]), "denied": True})
            return CallResult.fail(
                "EDENIED: memory intake denied by jev prejudge")
        self.audit.write({"t": time.time(), "event": "memory", "op": "remember",
                          "pid": pcb.pid, "id": rec["id"], "kind": rec["kind"]})
        return CallResult.ok_text(f"OK remembered #{rec['id']}")

    def _impl_mem_recall(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        hits = self.memory.recall(
            str(args["query"]), int(args.get("k", self.MEM_RECALL_DEFAULT_K)))
        # 隐私读污点已改闸门通用置（sentinel 判定放行处，F1）——此处不再置
        if not hits:
            return CallResult.ok_text("(no matching memories)")
        lines = [f"#{h['id']} [{h['kind']}] {h['text']} (score={h['score']:.2f})"
                 for h in hits]
        return CallResult.ok_text("\n".join(lines))

    def _impl_mem_forget(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        mid = int(args["id"])
        if not self.memory.forget(mid):
            return CallResult.fail(f"ENOSTR: no such memory #{mid}")
        self.audit.write({"t": time.time(), "event": "memory", "op": "forget",
                          "pid": pcb.pid, "id": mid})
        return CallResult.ok_text(f"OK forgot #{mid}")

    def _impl_mem_stats(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        st = self.memory.stats()
        kinds = " ".join(f"{k}={n}" for k, n in sorted(st["by_kind"].items()))
        return CallResult.ok_text(f"total={st['total']}" + (f" {kinds}" if kinds else ""))

    def _impl_mem_curate(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        payload = self.mem_curator.curate(str(args["task"]),
                                          k=args.get("k"))
        # 隐私读污点已改闸门通用置（sentinel 判定放行处，F1）——此处不再置
        audit_row = {"t": time.time(), "event": "memory",
                     "op": "curate", "pid": pcb.pid,
                     "payload": payload["id"], "stats": payload["stats"]}
        # 约束语言 lint（opt-in，LAOS_STE_LINT=1，Karpathy ASD-STE100 阶梯）：
        # 只检查不改写——问题数入审计供观测，payload 文本保持原样（原文权威）
        if os.environ.get("LAOS_STE_LINT", "").strip() == "1":
            from .ste import lint
            audit_row["ste_problems"] = len(lint(payload["text"]))
        self.audit.write(audit_row)
        # 返回 briefing 文本（含 payload #id 头）供前置进任务提示；
        # id 即 mem.outcome 的回填句柄
        return CallResult.ok_text(payload["text"])

    def _impl_mem_outcome(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult
        pid = int(args["payload_id"])
        success = bool(args["success"])
        if not self.mem_curator.note_outcome(pid, success):
            return CallResult.fail(f"ENOSTR: no such payload #{pid}")
        self.audit.write({"t": time.time(), "event": "memory",
                          "op": "outcome", "pid": pcb.pid,
                          "payload": pid, "success": success})
        return CallResult.ok_text(f"OK outcome #{pid}")

    def _impl_evolve_run(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult

        from .evolve import EvolveJob, run_job
        try:
            job = EvolveJob(target=str(args["target"]),
                            evaluator=str(args["evaluator"]),
                            iterations=int(args["iterations"]))
            result = run_job(job)
        except (ValueError, RuntimeError, TypeError) as exc:
            # gate 的 EPERM/EINVAL、装配面 ENODEV：fail-loud 冒泡为 CallResult
            return CallResult.fail(str(exc))
        except OSError as exc:
            # 终审 I3：驱动只转换了 FileNotFoundError，subprocess 仍会抛裸
            # OSError（WinError 5 拒绝访问 / 路径超长）——兜成 EIO 不击穿
            # syscall 网关（MCP 路径 blanket except → EIO 同款口径）
            return CallResult.fail(f"EIO: evolve 驱动 OSError：{exc}")
        self.audit.write({"t": time.time(), "event": "evolve", "op": "run",
                          "pid": pcb.pid, "target": job.target,
                          "iterations": result.iterations_completed,
                          "best_score": result.best_score,
                          "sha256": result.best_program_sha256})
        return CallResult.ok_text(json.dumps(asdict(result),
                                             ensure_ascii=False, sort_keys=True))

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
        # 隐私红线补口子：mic.* 被内核拒绝（EPERM/EDQUOT/EACCES 等）同样要
        # 留下 event:"mic" 审计——录音意图无论成败都可追责、可计数
        if tool.startswith("mic."):
            self.audit.write({"t": time.time(), "event": "mic",
                              "pid": pcb.pid, "tool": tool,
                              "denied": True, "reason": err})
        return CallResult.fail(err)

    def _on_elicit(self, method: str, params: dict) -> dict:
        """驱动 elicitation/create → 内核 confirm（人类在环，协议内机制）。"""
        if method != "elicitation/create":
            raise RuntimeError(f"ENOSYS: client does not support {method}")
        ok = self.confirm({"tool": "elicitation",
                           "message": params.get("message", ""),
                           "risk": "high"})
        return {"action": "accept" if ok else "decline", "value": ""}

    # -- 动态功耗定价：电池/温控状态驱动的风险乘数 -------------------------
    def set_pricing_multiplier(self, m: float) -> None:
        """调整风险定价乘数（写审计 event:"pricing"）。

        语义：乘数作用于所有不可逆操作的基础定价——低电量/高温时上调，
        让 Agent 自动收敛不可逆操作；恢复后回落。"""
        self.risk.multiplier = float(m)
        self.audit.write({"t": time.time(), "event": "pricing",
                          "multiplier": self.risk.multiplier,
                          "fleet_remaining": self.risk.remaining})

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
