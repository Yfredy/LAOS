"""Context Manager —— AgentOS 的“内存管理单元”。

传统 OS 管的是页框：分配、换出、回收。
AgentOS 管的是 token：窗口内保留什么、什么压缩成摘要、什么 swap 到磁盘。

这里实现一个够用的版本：
  * 定长滑动窗口（物理内存）
  * 超限后把最老的若干轮压缩成一条 summary（换页）
  * summary 可持久化到磁盘（swap）
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


def approx_tokens(text: str) -> int:
    """粗估 token 数：中文按 1.5 char/token，英文按 4 char/token 的折中。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    return int(cjk / 1.5 + (len(text) - cjk) / 4) + 1


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str
    ts: float = field(default_factory=time.time)
    tokens: int = 0
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.tokens:
            self.tokens = approx_tokens(self.content)

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.meta:
            d.update(self.meta)
        return d


@dataclass
class ContextStats:
    window_tokens: int = 0
    total_tokens: int = 0
    turns: int = 0
    compactions: int = 0
    swapped_bytes: int = 0
    stale_marks: int = 0


class ContextManager:
    """一个 Agent 进程独占的上下文（等价于进程的虚拟地址空间）。"""

    def __init__(
        self,
        system_prompt: str = "",
        max_tokens: int = 4000,
        swap_dir: Path | None = None,
        summarizer: Callable[[list[Message]], str] | None = None,
    ):
        self.max_tokens = max_tokens
        self.swap_dir = swap_dir
        self.summarizer = summarizer or self._default_summarizer
        self.stats = ContextStats()
        self._summary: str = ""
        self._window: list[Message] = []
        # 观察簿：path -> 读时内容摘要（Stale Context 检测，HKU/AgenticOS'26）
        self._observations: dict[str, str] = {}
        self._stale: set[str] = set()
        if system_prompt:
            self._system = Message("system", system_prompt)
        else:
            self._system = Message("system", "")

    # -- 基本读写 ---------------------------------------------------------
    def append(self, role: str, content: str, **meta) -> Message:
        msg = Message(role, content, meta=meta)
        if role == "system":
            self._system = msg
            return msg
        self._window.append(msg)
        self.stats.turns += 1
        self.stats.total_tokens += msg.tokens
        self._compact_if_needed()
        return msg

    @property
    def messages(self) -> list[dict]:
        out: list[dict] = []
        if self._system.content:
            out.append(self._system.to_dict())
        if self._summary:
            out.append(
                {
                    "role": "system",
                    "content": f"<summary of earlier context>\n{self._summary}",
                }
            )
        out.extend(m.to_dict() for m in self._window)
        return out

    @property
    def window_tokens(self) -> int:
        return self._system.tokens + approx_tokens(self._summary) + sum(
            m.tokens for m in self._window
        )

    # -- 换页 -------------------------------------------------------------
    def _compact_if_needed(self) -> None:
        while self.window_tokens > self.max_tokens and len(self._window) > 2:
            victim_count = max(1, len(self._window) // 3)
            victims, self._window = self._window[:victim_count], self._window[victim_count:]
            self._swap_out(victims)
            self._summary = self.summarizer(victims + [Message("system", self._summary)])
            self.stats.compactions += 1
        self.stats.window_tokens = self.window_tokens

    def _swap_out(self, victims: list[Message]) -> None:
        """把被压缩掉的消息写到磁盘，等价于 swap。"""
        if not self.swap_dir:
            return
        self.swap_dir.mkdir(parents=True, exist_ok=True)
        path = self.swap_dir / f"swap-{int(time.time() * 1000)}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for m in victims:
                f.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        self.stats.swapped_bytes += path.stat().st_size

    @staticmethod
    def _default_summarizer(victims: list[Message]) -> str:
        lines = []
        for m in victims[:-1]:
            snippet = m.content.replace("\n", " ").strip()
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."
            lines.append(f"- [{m.role}] {snippet}")
        return "\n".join(lines)

    # -- 观测 -------------------------------------------------------------
    def dump(self) -> dict[str, Any]:
        return {
            "window_tokens": self.window_tokens,
            "max_tokens": self.max_tokens,
            "messages_in_window": len(self._window),
            "turns": self.stats.turns,
            "total_tokens": self.stats.total_tokens,
            "compactions": self.stats.compactions,
            "swapped_bytes": self.stats.swapped_bytes,
        }

    # -- 抢占快照（受 AIOS Context Manager 启发，但作用于 Agent 上下文窗口）----
    def save_snapshot(self) -> Path:
        """把当前完整上下文序列化到 swap_dir，等价于进程挂起时的寄存器/内存落盘。"""
        if not self.swap_dir:
            raise RuntimeError("save_snapshot requires swap_dir")
        self.swap_dir.mkdir(parents=True, exist_ok=True)
        path = self.swap_dir / f"snap-{int(time.time() * 1000)}.json"
        payload = {
            "system": self._system.content,
            "summary": self._summary,
            "window": [m.to_dict() for m in self._window],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def load_snapshot(self, path: Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self._system = Message("system", data.get("system", ""))
        self._summary = data.get("summary", "")
        self._window = [Message(m["role"], m["content"], meta=m) for m in data.get("window", [])]
        self.stats.window_tokens = self.window_tokens

    @property
    def suspended(self) -> bool:
        return getattr(self, "_suspended", False)

    def suspend(self) -> None:
        self._suspended = True

    def resume(self) -> None:
        self._suspended = False

    # -- Stale Context：观察簿 --------------------------------------------
    def observe(self, path: str, digest: str) -> None:
        """记录一次 fs.read 观察：读到的内容摘要。重读即愈合。"""
        self._observations[path] = digest
        self._stale.discard(path)

    def invalidate(self, path: str) -> None:
        """该路径被外部修改：观察过它的上下文从此陈旧。"""
        if path in self._observations and path not in self._stale:
            self._stale.add(path)
            self.stats.stale_marks += 1

    def drain_notices(self) -> list[str]:
        """取走当前陈旧路径列表（一次性，取走即清）。"""
        out = sorted(self._stale)
        self._stale.clear()
        return out

    def notice(self, content: str) -> Message:
        """内核通告：以 user 角色注入（append('system') 会替换系统提示，勿用）。"""
        return self.append("user", f"[kernel-notice] {content}")
