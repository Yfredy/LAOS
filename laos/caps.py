"""caps —— Agent 工具能力注册表：caller 分级 / 权限位 / 生命周期 / LLM 可见域。

    叙事     Agent 调工具 = 进程调 syscall；能力表 = syscall 表的权限位治理。
             laos 是内核治理在用户态的延伸，本模块是工具面的那一层。
    来源     espressif/esp-claw claw_cap.h 取长补短（2026-10-08 复现波次，
             docs/research/2026-10-08-espclaw-vs-muse-agent-core.md §五）。
             esp-claw 在 MCU 上独立长出了与内核权限位同构的形态：caller
             分级（SYSTEM/AGENT/CONSOLE/ROOT_AGENT/SUB_AGENT）、权限位
             （CALLABLE_BY_LLM/EMITS_EVENTS/RESTRICTED/ROOT_AGENT_ONLY）、
             能力状态机（REGISTERED→STARTED→DISABLED，DRAINING 排空）与
             per-session 工具可见域。laos 侧收敛为纯 stdlib 同构件。

    Caller   SYSTEM=内核/装配面；AGENT=root agent；SUB_AGENT=派生代理；
             CONSOLE=人机命令行。ROOT_AGENT 不单列——AGENT 即 root。
    状态机   REGISTERED（不可调）→ enable → STARTED（可调）→ disable →
             DISABLED；drain() 先 DRAINING 等 in-flight 排空再 DISABLED
             （对应 claw 的 DRAINING/UNLOADING 语义的同步简化）。
    可见域   tools_for(caller, session) 生成该调用方可调且 LLM 可见的
             工具目录；set_llm_visible(families, session_id) 支持全局与
             按 session 覆盖（最小暴露面原则）。
    审计     registry(audit=fn)：每次 call 追加 {cap, caller, ok}——
             挂 telemetry/audit 流的口径见 CalCap。

零依赖：纯 stdlib（enum/dataclasses/threading）。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from typing import Any, Callable


class CapKind(Enum):
    """能力种类：可调用 / 事件源 / 混合（claw_cap_kind_t 同构）。"""

    CALLABLE = auto()
    EVENT_SOURCE = auto()
    HYBRID = auto()


class Caller(Enum):
    """调用方分级（claw_cap_caller_t 同构；ROOT_AGENT=AGENT 不单列）。"""

    SYSTEM = auto()
    AGENT = auto()
    CONSOLE = auto()
    SUB_AGENT = auto()


class CapFlag(Flag):
    """权限位（claw_cap_flags_t 取 LLM 治理相关的四位）。"""

    CALLABLE_BY_LLM = auto()
    EMITS_EVENTS = auto()
    RESTRICTED = auto()
    ROOT_AGENT_ONLY = auto()


class CapState(Enum):
    """能力状态机（claw_cap_state_t 同步简化：无 UNLOADING 半态）。"""

    REGISTERED = auto()
    STARTED = auto()
    DISABLED = auto()
    DRAINING = auto()


@dataclass(frozen=True)
class CapabilityDescriptor:
    """能力描述子。execute(payload, ctx) -> output；ctx 见 CallContext。"""

    id: str
    name: str
    family: str
    kind: CapKind
    flags: CapFlag
    description: str = ""
    input_schema: dict | None = None
    execute: Callable[[dict, "CallContext"], Any] | None = None


@dataclass
class CallContext:
    """call() 时构造的调用上下文（血统链 + in-flight 计数，claw 同构）。"""

    caller: Caller
    session_id: str | None = None
    agent_id: str | None = None
    parent_agent_id: str | None = None
    active_calls: int = 0


@dataclass
class _Entry:
    descriptor: CapabilityDescriptor
    state: CapState = CapState.REGISTERED
    active_calls: int = 0
    zero: threading.Condition = field(default_factory=threading.Condition)


class CapRegistry:
    """能力注册表：登记 / 状态机 / caller 闸 / 可见域 / 审计。"""

    def __init__(self, audit: Callable[[dict], None] | None = None):
        self._caps: dict[str, _Entry] = {}
        self._audit = audit
        self._llm_visible: dict[str | None, list[str] | None] = {}
        self._lock = threading.RLock()

    # -- 登记/状态机 ------------------------------------------------------

    def register(self, descriptor: CapabilityDescriptor) -> None:
        with self._lock:
            if descriptor.id in self._caps:
                raise ValueError(
                    f"EEXIST: capability already registered: {descriptor.id}")
            self._caps[descriptor.id] = _Entry(descriptor)

    def unregister(self, cap_id: str) -> None:
        with self._lock:
            entry = self._require(cap_id)
            if entry.active_calls:
                raise RuntimeError(
                    f"EBUSY: capability has in-flight calls, drain first: "
                    f"{cap_id} ({entry.active_calls})")
            del self._caps[cap_id]

    def enable(self, cap_id: str) -> None:
        with self._lock:
            self._require(cap_id).state = CapState.STARTED

    def disable(self, cap_id: str) -> None:
        with self._lock:
            self._require(cap_id).state = CapState.DISABLED

    def drain(self, cap_id: str, timeout: float | None = None) -> bool:
        """DRAINING → 等 in-flight 排空 → DISABLED。超时返回 False（状态
        仍推进到 DISABLED，剩余 in-flight 自然结束后不再受理新调用）。"""
        with self._lock:
            entry = self._require(cap_id)
            entry.state = CapState.DRAINING
        with entry.zero:
            while entry.active_calls and (timeout is None or timeout > 0):
                step = 0.05 if timeout is None else min(0.05, timeout)
                entry.zero.wait(step)
                if timeout is not None:
                    timeout -= step
        with self._lock:
            entry.state = CapState.DISABLED
        return entry.active_calls == 0

    def state(self, cap_id: str) -> CapState:
        with self._lock:
            return self._require(cap_id).state

    # -- 调用 -------------------------------------------------------------

    def call(self, cap_id: str, payload: dict, *, caller: Caller,
             session_id: str | None = None, agent_id: str | None = None,
             parent_agent_id: str | None = None) -> Any:
        # execute() 在注册表锁外跑（否则全部能力调用被串行化，drain 拿不到
        # 锁、并发调用互相阻塞）；锁内只做查表/闸门/in-flight 计数。
        entered = False
        ok = False
        try:
            with self._lock:
                entry = self._require(cap_id)
                if entry.state is not CapState.STARTED:
                    raise RuntimeError(
                        f"EACCES: capability not started "
                        f"({entry.state.name}): {cap_id}")
                self._gate(entry.descriptor, caller, cap_id)
                if entry.descriptor.kind is CapKind.EVENT_SOURCE:
                    raise ValueError(
                        f"EINVAL: event-source capability is not callable: "
                        f"{cap_id}")
                if entry.descriptor.execute is None:
                    raise ValueError(
                        f"ENOSYS: capability has no execute: {cap_id}")
                with entry.zero:
                    entry.active_calls += 1
                entered = True
                ctx = CallContext(caller=caller, session_id=session_id,
                                  agent_id=agent_id,
                                  parent_agent_id=parent_agent_id,
                                  active_calls=entry.active_calls)
            result = entry.descriptor.execute(dict(payload), ctx)
            ok = True
            return result
        finally:
            if entered:
                with entry.zero:
                    entry.active_calls = max(0, entry.active_calls - 1)
                    if entry.active_calls == 0:
                        entry.zero.notify_all()
            if self._audit is not None:
                self._audit({"cap": cap_id, "caller": caller.name,
                             "ok": ok, "session_id": session_id})

    @staticmethod
    def _gate(descriptor: CapabilityDescriptor, caller: Caller,
              cap_id: str) -> None:
        if CapFlag.RESTRICTED in descriptor.flags and caller is not Caller.SYSTEM:
            raise PermissionError(
                f"EPERM: RESTRICTED capability requires SYSTEM caller: "
                f"{cap_id} (got {caller.name})")
        if (CapFlag.ROOT_AGENT_ONLY in descriptor.flags
                and caller not in (Caller.SYSTEM, Caller.AGENT)):
            raise PermissionError(
                f"EPERM: ROOT_AGENT_ONLY capability requires AGENT/SYSTEM: "
                f"{cap_id} (got {caller.name})")

    # -- 可见域 / 目录 ----------------------------------------------------

    def set_llm_visible(self, families: list[str] | None,
                        session_id: str | None = None) -> None:
        """LLM 可见 family 域；None=恢复默认全集，[]=全隐藏。session 覆盖
        优先于全局（未设置的 session 走全局）。"""
        with self._lock:
            self._llm_visible[session_id] = families

    def tools_for(self, *, caller: Caller,
                  session_id: str | None = None) -> list[CapabilityDescriptor]:
        with self._lock:
            families = self._llm_visible.get(
                session_id, self._llm_visible.get(None))
            out = []
            for entry in self._caps.values():
                d = entry.descriptor
                if CapFlag.CALLABLE_BY_LLM not in d.flags:
                    continue
                if CapFlag.RESTRICTED in d.flags:
                    continue
                if (CapFlag.ROOT_AGENT_ONLY in d.flags
                        and caller is Caller.SUB_AGENT):
                    continue
                if families is not None and d.family not in families:
                    continue
                out.append(d)
            out.sort(key=lambda d: d.id)
            return out

    def catalog(self) -> list[dict]:
        """运维目录（全部能力 + 状态 + 治理位；不区分 caller）。"""
        with self._lock:
            return [{
                "id": e.descriptor.id, "name": e.descriptor.name,
                "family": e.descriptor.family,
                "kind": e.descriptor.kind.name,
                "state": e.state.name,
                "restricted": CapFlag.RESTRICTED in e.descriptor.flags,
                "root_agent_only":
                    CapFlag.ROOT_AGENT_ONLY in e.descriptor.flags,
                "active_calls": e.active_calls,
            } for e in sorted(self._caps.values(),
                              key=lambda e: e.descriptor.id)]

    def _require(self, cap_id: str) -> _Entry:
        try:
            return self._caps[cap_id]
        except KeyError:
            raise KeyError(f"ENOENT: capability not registered: {cap_id}") \
                from None


class CalCap:
    """审计钩子 → telemetry 事件流的适配（a.* 口径对齐 v0.21.0 埋点）。

    CapRegistry(audit=CalCap(emit=emitter)) 时每次 call 转发一条
    {"event": "cap.call", ...}——字段名与 telemetry 事件纪律一致
    （计数优先于内容：不携带 payload）。
    """

    def __init__(self, registry: CapRegistry | None, emit):
        self._registry = registry
        self._emit = emit

    def __call__(self, record: dict) -> None:
        self.record(**record)

    def record(self, cap: str, caller: str, ok: bool,
               session_id: str | None = None) -> None:
        self._emit({"event": "cap.call", "cap": cap, "caller": caller,
                    "ok": ok, "session_id": session_id})
