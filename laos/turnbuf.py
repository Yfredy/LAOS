"""laos.turnbuf —— 交互轮次缓冲（Pipecat 两课的内核语义层，采纳书 B 项）。

来源：Pipecat 帧管道复现（zones/Repro-ZCode/repro/framepipe.py）的两条设计课：
  课 1（打断即作废）：用户一开口，排队未送达的内容全部丢弃；
  课 2（聚合器放 output 之后）：上下文/记忆只记**实际送达**的内容。

映射到 laos：append = Agent 生成的数据帧；deliver_more = 传输层实际送出的
水位；interrupt = 用户接管；commit = mem.remember 只写已送达水位（与记忆
闸门语义同构——记实际发生的交互，不记想象的交互）。线程安全（一把锁，
生命周期用 laos.locks.UniqueLock 显式化——采纳书 C 项）。
"""
from __future__ import annotations

import threading

from .locks import UniqueLock


class TurnBuffer:
    """一轮交互的"生成-送达-打断-入记忆"缓冲。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._delivered: list[str] = []              # 已送达水位（拼接即文本）
        self._pending: list[str] = []                # 生成未送达（数据帧队列）
        self._interrupted = False

    # -- 生成侧（数据帧） ------------------------------------------------
    def append(self, text: str) -> None:
        """Agent 生成一段文本（未送达）。"""
        if not text:
            return
        with UniqueLock(self._lock):
            self._pending.append(text)

    def interject(self, text: str) -> None:
        """插队帧：外部结果插到待送达队列**头部**，下一次送达先送它。

        语义来源（docs/research/2026-10-05-speech-weekly-spatial-duplex.md）：
        SALMONN-duo——慢系统返回期间系统 1 保持说话，结果回来无缝织入当前轮；
        Context Spanning——检索到的原文不经压缩直接注入。interrupt() 之后仍可
        用（清场后新起一轮播报）。与 commit 的"只记已送达"正交：插队帧同样
        只在实际送达后才进记忆。
        """
        if not text:
            return
        with UniqueLock(self._lock):
            self._pending.insert(0, text)

    # -- 传输侧（推进送达水位） ------------------------------------------
    def deliver_more(self, delta: str) -> None:
        """增量标记已实际送出的内容：从待送达队列头部消费 delta 字符。"""
        if not delta:
            return
        with UniqueLock(self._lock):
            rest = delta
            while rest and self._pending:
                head = self._pending[0]
                if len(head) <= len(rest):
                    self._delivered.append(head)
                    rest = rest[len(head):]
                    self._pending.pop(0)
                else:
                    self._delivered.append(head[: len(rest)])
                    self._pending[0] = head[len(rest):]
                    rest = ""

    # -- 打断（课 1） -----------------------------------------------------
    def interrupt(self) -> None:
        """用户接管：未送达尾部立即作废。"""
        with UniqueLock(self._lock):
            self._pending = []
            self._interrupted = True

    # -- 读侧 --------------------------------------------------------------
    @property
    def delivered_text(self) -> str:
        with UniqueLock(self._lock):
            return "".join(self._delivered)

    @property
    def pending_text(self) -> str:
        with UniqueLock(self._lock):
            return "".join(self._pending)

    @property
    def interrupted(self) -> bool:
        with UniqueLock(self._lock):
            return self._interrupted

    # -- 入记忆（课 2） ----------------------------------------------------
    def commit(self, memory, kind: str, tags: list[str] | None = None,
               judge=None) -> dict | None:
        """把**已送达水位内**的文本写入记忆（透传 Jev judge）。"""
        text = self.delivered_text
        if not text:
            return None
        return memory.remember(kind, text, tags=tags, judge=judge)

    def reset(self) -> None:
        """开始下一轮。"""
        with UniqueLock(self._lock):
            self._delivered = []
            self._pending = []
            self._interrupted = False
