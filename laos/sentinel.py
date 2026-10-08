"""sentinel —— 动作闸：六级有序判定 + taint 追踪 + scoped grants。

设计转译自 nanoMuse（github.com/nano-muse/nanoMuse, GPL-3.0）的
nanomuse/sentinel/{gate,policy,grants}.py——只学判定序与语义，零代码拷贝
（GPL 传染红线；锚点见 docs/research/2026-10-08-nanomuse.md §3.1）。

判定序（与 nanoMuse policy.py:72-143 同构，laos 化语义）：
    ① deny_tools 硬拒
    ② 显式规则（tool_glob，action=allow/ask/deny）——唯一能放行污点出站
       与终审警告的通道（= nanoMuse 的 egress allowlist 语义）
    ③ always_allow / always_ask 列表
    ④ 风险×模式：auto 全放 / strict 非 low 问 / ask（默认）不可逆或高风险问
    ⑤ taint 升级：污点 pid 的出站工具强制 ask（auto 也生效，永不回退；
       仅 once 档 grant——不给 session/always 免疫）
    ⑥ 终审警告：不可逆且高风险 → ask 且仅 once 档 grant 可用（auto 除外）
      （= nanoMuse "warnings 永不被 grant 覆盖"的 laos 化）
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Assessment:
    tool: str
    risk: str = "low"           # 对齐 ToolSpec.risk 口径（low/medium/high）
    reversible: bool = True     # 对齐 ToolSpec.reversible
    reads_private: bool = False  # 本调用是否读隐私源（供调用方事后 taint）
    egress: bool = False         # 本调用是否出站（信息离开本机/pid 域）


@dataclass(frozen=True)
class Decision:
    action: str                  # "allow" | "ask" | "deny"
    reason: str
    grant_scopes: tuple = ("once", "session", "always")


@dataclass
class SentinelConfig:
    deny_tools: tuple = ()
    rules: tuple = ()            # ({"tool_glob": str, "action": str}, ...)
    always_allow: tuple = ()
    always_ask: tuple = ()
    mode: str = "ask"            # "ask" | "auto" | "strict"
    private_tools: tuple = ("mem.recall", "mem.curate", "mic.read")
    egress_tools: tuple = ("msg.send",)


class GrantStore:
    """scoped grants：授权即能力（tool_glob+target 绑定+寿命档）。

    laos 化三档（nanoMuse 五档 once/conversation/session/24h/always 的子集，
    YAGNI）：once=单次消费、session=内核生命周期、always=同 session 但显式
    最高档（持久化留接线波）。线程安全（kernel 多线程 syscall 并发 covers）。
    """
    _SCOPES = ("once", "session", "always")

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._next = 1
        self._grants: dict[int, dict] = {}

    def add(self, tool_glob: str, target: str | None = None,
            scope: str = "once") -> int:
        import fnmatch
        if scope not in self._SCOPES:
            raise ValueError(f"scope must be one of {self._SCOPES}, got {scope!r}")
        fnmatch.fnmatch("", tool_glob)  # 早验 glob 合法性
        with self._lock:
            gid = self._next
            self._next += 1
            self._grants[gid] = {"gid": gid, "tool_glob": tool_glob,
                                 "target": target, "scope": scope}
            return gid

    def covers(self, tool: str, target: str | None = None) -> int | None:
        import fnmatch
        with self._lock:
            for gid, g in list(self._grants.items()):
                if fnmatch.fnmatch(tool, g["tool_glob"]):
                    if g["target"] is not None and target is not None \
                            and g["target"] != target:
                        continue
                    if g["scope"] == "once":
                        del self._grants[gid]
                    return gid
        return None

    def revoke(self, gid: int) -> bool:
        with self._lock:
            return self._grants.pop(gid, None) is not None

    def list_grants(self) -> list[dict]:
        with self._lock:
            return [dict(g) for g in self._grants.values()]


class Sentinel:
    """纯决策核：无 I/O；taint/grants 状态由本类持有
    （线程安全：kernel 多线程 syscall 并发 decide/covers/mark）。
    """

    def __init__(self, config: SentinelConfig | None = None,
                 grants: GrantStore | None = None):
        self.cfg = config or SentinelConfig()
        self.grants = grants if grants is not None else GrantStore()
        import threading
        self._taint_lock = threading.Lock()
        self._tainted: set[int] = set()

    def mark_private_read(self, pid: int) -> None:
        with self._taint_lock:
            self._tainted.add(pid)

    def is_tainted(self, pid: int) -> bool:
        with self._taint_lock:
            return pid in self._tainted

    def untaint(self, pid: int) -> None:
        """进程退出时的唯一清除通道（kernel kill 路径调用）。"""
        with self._taint_lock:
            self._tainted.discard(pid)

    def decide(self, a: Assessment, tainted: bool = False) -> Decision:
        import fnmatch
        cfg = self.cfg
        if a.tool in cfg.deny_tools:
            return Decision("deny", "deny-tools")
        for rule in cfg.rules:
            if fnmatch.fnmatch(a.tool, rule.get("tool_glob", "")):
                act = rule.get("action", "ask")
                if act == "deny":
                    return Decision("deny", "rule")
                if act == "allow":
                    return Decision("allow", "rule")
                return Decision("ask", "rule")
        if a.tool in cfg.always_allow:
            return Decision("allow", "always-allow")
        if a.tool in cfg.always_ask:
            return Decision("ask", "always-ask")
        # ④ 风险×模式：auto 全放 / strict 非 low 问 / ask（默认）不可逆或高风险问。
        #    终审案例（不可逆且高风险）不在本级定级——延后到 ⑥ 升级为仅 once 档。
        terminal = (not a.reversible) and a.risk == "high"
        if cfg.mode == "auto":
            pass  # auto 不在此级产生 ask（taint 升级仍生效，见 ⑤）
        elif cfg.mode == "strict":
            if a.risk != "low" and not terminal:
                return Decision("ask", "risk-mode")
        else:  # ask（默认）：不可逆或高风险才问（与 kernel 既有 confirm 口径对齐）
            if not terminal and (not a.reversible or a.risk == "high"):
                return Decision("ask", "risk-mode")
        # ⑤ taint 升级：污点 pid 的出站工具强制 ask（auto 也生效，永不回退）。
        #    仅 once 档 grant——污点出站不给 session/always 免疫（唯一豁免=② 显式 allow）。
        if tainted and a.egress:
            return Decision("ask", "taint-egress", ("once",))
        # ⑥ 终审警告：不可逆且高风险 → ask 且仅 once 档 grant 可用。
        #    auto 依 ④ "全放"约定不触发——唯一穿透 auto 的升级是 ⑤ taint-egress。
        if terminal and cfg.mode != "auto":
            return Decision("ask", "warning-terminal", ("once",))
        return Decision("allow", "default")
