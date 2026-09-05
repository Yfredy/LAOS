# laos/risk.py
"""FleetLedger —— 车队级不可逆风险账本。

对应《The Irreversibility Budget: Fleet-Level Risk Accounting and Admission
Control for Agent Operating Systems》（AgenticOS @ SOSP 2026, MPI-SWS）：
不可逆操作按工具定价，agent/车队两级记账，spawn 时做准入控制
（剩余预算必须高于保留水位，留给已准入 agent 应急）。

记账语义：kill/abort **不退款** —— 不可逆操作的定义就是"无法通过
终止进程撤销"；退款只属于显式回滚机制（分支 abort 只回滚分支内
可逆写，而那些写在写时就没有计费）。注意这条边界的适用范围：
未计费的 fs.write / fs.append 只有在写入探索分支工作区时才谈得上
"可回滚"——写进 /main（或 commit 之后的状态）是持久的、未计费的、
且在闸门之外；把这段持久写纳入定价是已知下一步（README §6
future-work 列的"探索期免计费、commit 时结算"）。

计价语义：**按尝试计费**（attempt-based pricing）——闸门一旦放行
（车队余量、agent 风险帽、人工确认三关全过），这笔账即落定；即便
驱动随后拒绝（EDENIED）或失败（EIO）也不退，账本记录的是"授权
决定"本身，而非驱动的执行结果。syscall 次数预算（EDQUOT）在闸门
**之前**检查：因预算耗尽被拒的调用永远不会计费。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FleetLedger:
    """车队总预算 + 保留水位 + 两级（pid / tool）支出直方图。"""

    budget: int
    reserve: int = 1
    spent: int = 0
    per_agent: dict[int, int] = field(default_factory=dict)
    per_tool: dict[str, int] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return self.budget - self.spent

    def can_admit(self) -> bool:
        """准入控制：剩余预算必须严格高于保留水位。"""
        return self.remaining > self.reserve

    def charge(self, pid: int, tool: str, cost: int) -> None:
        self.spent += cost
        self.per_agent[pid] = self.per_agent.get(pid, 0) + cost
        self.per_tool[tool] = self.per_tool.get(tool, 0) + cost
