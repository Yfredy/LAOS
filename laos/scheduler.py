"""多 Agent 公平复用 Brain（LLM 是最贵资源）。

受 AIOS Scheduler 启发：AIOS 用 FIFO/RR 给 LLM 推理请求排队，RR 的 p90 等待更低。
这里把"全局锁"升级为带 priority 的时间片轮转 + 每 agent token 预算，超额自动挂起。
"""
from __future__ import annotations


class AgentScheduler:
    def __init__(self) -> None:
        self._prio: dict[int, int] = {}
        self._budget: dict[int, int | None] = {}
        self._used: dict[int, int] = {}
        self._suspended: set[int] = set()
        self._last_served: dict[int, int] = {}
        self._serve_tick = 1  # 从未服务的 agent 默认 last=0，故 tick 从 1 起以区分"更老"

    def register(self, pid: int, priority: int = 0, token_budget: int | None = None) -> None:
        self._prio[pid] = priority
        self._budget[pid] = token_budget
        self._used[pid] = 0

    def next_pid(self) -> int | None:
        alive = [p for p in self._prio if p not in self._suspended]
        if not alive:
            return None
        # 优先级高者优先；平级时上次服务时间最老者优先（轮转，避免饥饿）
        return max(alive, key=lambda p: (self._prio[p], -self._last_served.get(p, 0)))

    def acquire(self, pid: int) -> bool:
        if pid in self._suspended:
            return False
        b = self._budget.get(pid)
        if b is not None and self._used.get(pid, 0) >= b:
            self._suspended.add(pid)
            return False
        if self.next_pid() != pid:
            return False
        self._last_served[pid] = self._serve_tick
        self._serve_tick += 1
        return True

    def release(self, pid: int) -> None:
        # 轮转状态由 _last_served 维护，release 无需动作；保留接口以对齐 Agent 调用
        _ = pid

    def retire(self, pid: int) -> None:
        """进程退出即注销：否则轮转指针会停在已结束的 pid 上，饿死其余 agent。"""
        self._prio.pop(pid, None)
        self._budget.pop(pid, None)
        self._used.pop(pid, None)
        self._suspended.discard(pid)
        self._last_served.pop(pid, None)

    def note_tokens(self, pid: int, n: int) -> None:
        self._used[pid] = self._used.get(pid, 0) + n
        b = self._budget.get(pid)
        if b is not None and self._used[pid] >= b:
            self._suspended.add(pid)
