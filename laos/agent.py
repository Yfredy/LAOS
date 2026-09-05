"""Agent —— AgentOS 里的“进程”。

一个 Agent = PCB + 上下文（虚拟地址空间）+ Brain（CPU）+ 能力集（保护环）。
它唯一能做副作用的方式是发起系统调用（MCP tool call），并且只能看到
自己被授权的那部分 syscall —— 这一步由内核过滤后交给 Brain。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .brain import Brain, Thought
from .context import ContextManager
from .kernel import AgentKernel, PCB

# 调度等待上界：200 轮 x 10ms ≈ 2s。挂起（token/err 预算耗尽）的 agent
# 等满上界即收到调度拒绝，而不是永久自旋占住事件循环（R307）。
_SCHED_WAIT_ROUNDS = 200


@dataclass
class AgentResult:
    pid: int
    ok: bool
    answer: str = ""
    steps: int = 0
    syscalls: int = 0
    denied: int = 0
    tokens: int = 0
    trace: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"pid={self.pid} ok={self.ok} steps={self.steps} "
            f"syscalls={self.syscalls} denied={self.denied} tokens={self.tokens}"
        )


class Agent:
    def __init__(
        self,
        kernel: AgentKernel,
        pcb: PCB,
        brain: Brain,
        max_steps: int = 12,
    ):
        self.kernel = kernel
        self.pcb = pcb
        self.brain = brain
        self.max_steps = max_steps

    @property
    def visible_tools(self) -> list[dict]:
        """内核按能力集裁剪 syscall 表后，才交给 LLM 看到。

        MCP 驱动表与内核内建表（msg.* 等）合并裁剪：统一走
        kernel._effective_allows（自身 caps ∪ 未过期委托，不 consume）。
        """
        specs = {tool: spec for tool, (_driver, spec) in self.kernel.syscall_table.items()}
        for tool, spec in self.kernel._builtin_specs.items():
            specs.setdefault(tool, spec)
        out = []
        for tool, spec in sorted(specs.items()):
            if self.kernel._effective_allows(self.pcb, tool):
                out.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "inputSchema": spec.input_schema,
                    }
                )
        return out

    def fork_child(self, name: str, caps_subset: list[str], branch: str, child_brain) -> "Agent":
        """派生子进程：只能委派自身能力的子集（kernel.spawn(parent=...)）。

        风险帽同预算一样随父进程继承：委派可以收窄、不可以提升风险特权。
        任务边界（task_scope）随血统继承，不因分支放宽。
        """
        child_caps = self.pcb.caps.delegate(caps_subset)
        ctx = ContextManager(
            system_prompt=self.pcb.ctx._system.content,
            max_tokens=self.pcb.ctx.max_tokens,
            swap_dir=self.kernel.workdir / "swap",
        )
        child_pcb = self.kernel.spawn(
            name=name, caps=sorted(child_caps.patterns), ctx=ctx,
            branch=branch, parent=self.pcb.pid, budget=self.pcb.budget,
            risk_cap=self.pcb.risk_cap, task_scope=self.pcb.task_scope,
        )
        return Agent(self.kernel, child_pcb, child_brain, max_steps=self.max_steps)

    async def _do_syscall(self, call) -> str:
        # LLM 是最贵的共享资源：所有 Agent 经 AgentScheduler 公平抢时间片；
        # 挂起（token/err 预算耗尽）的 agent 在有界等待后收到调度拒绝，
        # 而不是永久自旋（Patient Bytes 语义：预算耗尽 = 让出）。
        sched = self.kernel.scheduler
        waited = 0
        while not sched.acquire(self.pcb.pid):
            waited += 1
            if waited > _SCHED_WAIT_ROUNDS:
                return "ESRCH: scheduler suspended pid (token/err budget exhausted)"
            await asyncio.sleep(0.01)
        try:
            res = await self.kernel.syscall(self.pcb.pid, call.name, call.arguments)
            sched.note_tokens(self.pcb.pid, self.pcb.ctx.stats.total_tokens)
            return res.text
        finally:
            sched.release(self.pcb.pid)

    async def run(self, task: str) -> AgentResult:
        ctx = self.pcb.ctx
        ctx.append("user", task)
        result = AgentResult(pid=self.pcb.pid, ok=False)
        try:
            for step in range(1, self.max_steps + 1):
                # Stale Context：内核通告注入（HKU: 当上下文与现实不符时强制重读）
                if hasattr(self.pcb.ctx, "drain_notices"):
                    for stale_path in self.pcb.ctx.drain_notices():
                        self.pcb.ctx.notice(
                            f"STALE: {stale_path} 已被外部修改，之前的读取结果不可信，请重新 fs.read"
                        )
                tools = self.visible_tools
                thought: Thought = await asyncio.to_thread(self.brain.think, ctx.messages, tools)
                result.steps = step

                if thought.text:
                    ctx.append("assistant", thought.text)
                    result.trace.append({"step": step, "say": thought.text})

                if not thought.tool_calls:
                    result.answer = thought.text
                    # 被内核拒过的 Agent 不算成功完成
                    result.ok = thought.finish and self.pcb.stats["denied"] == 0
                    if thought.finish:
                        break
                    continue  # 纯思考步，未结束则继续下一轮

                for call in thought.tool_calls:
                    out = await self._do_syscall(call)
                    ctx.append("tool", out, name=call.name)
                    result.trace.append(
                        {"step": step, "syscall": call.name, "args": call.arguments, "ret": out[:300]}
                    )

                if thought.finish:
                    result.answer = thought.text
                    result.ok = True
                    break
            else:
                result.answer = f"达到最大步数 {self.max_steps}，任务未完成。"
                result.ok = False
        finally:
            # 进程退出即从调度器注销：否则轮转指针停在已结束的 pid 上，饿死其余 agent
            self.kernel.scheduler.retire(self.pcb.pid)

        result.syscalls = self.pcb.stats["syscalls"]
        result.denied = self.pcb.stats["denied"]
        result.tokens = ctx.stats.total_tokens
        # 生命周期收尾不得覆盖 kill：被处决的进程必须停在 killed 上
        # （否则 run 迟一步返回，/api/state 会看到 killed 又变回 zombie/ready）
        if self.pcb.state != "killed":
            self.pcb.state = "zombie" if result.ok else "ready"
        return result


async def run_agents(kernel: AgentKernel, agents: list[Agent], tasks: list[str]) -> list[AgentResult]:
    """并发跑多个 Agent —— 内核调度器负责给它们分 LLM 时间片。"""
    return list(await asyncio.gather(*(a.run(t) for a, t in zip(agents, tasks))))
