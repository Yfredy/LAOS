"""laos.turnpolicy —— 轮转三态策略：speak / hold / stop。

来源：Duplex-MPE（arXiv 2609.31948）把全双工助手能力拆成 发起/准确/沉默/停
止四项评分；其中三个是纯时序决策——何时发起回复（speak）、何时保持沉默
（hold，含"别人聊别人的不插嘴"）、何时停止说话（stop，barge-in 让位）。
本模块是这三个决策的**策略位**：纯函数状态机、无副作用，同一输入永远同一
输出；音频证据（VAD/ASR）由调用方转成事件时间线后喂入。

与 laos.duplex 的关系：duplex 度量"发生了什么"（响应延迟/抢话/重叠），
turnpolicy 决定"接下来该做什么"。两者共用事件词表但**互不 import**——
少量区间逻辑重复换取模块独立（各自可单独进驱动子进程）。

防过早响应（LateIntent 思想，同周 LateIntent-Bench arXiv 2610.00272 的
"过早响应率"）：min_hold_ms 意图保持闸——用户停止发声后至少再等这么久，
防住"说了半句就被接话"。
"""
from __future__ import annotations

__all__ = ["TurnPolicy"]

_EVENT_KINDS = ("user_start", "user_end", "agent_start", "agent_end", "barge_in")


class TurnPolicy:
    """时序轮转策略。所有阈值单位毫秒。"""

    def __init__(self, *, tail_silence_ms: int = 500, min_speech_ms: int = 200,
                 min_hold_ms: int = 250) -> None:
        for name, v in (("tail_silence_ms", tail_silence_ms),
                        ("min_speech_ms", min_speech_ms),
                        ("min_hold_ms", min_hold_ms)):
            if v <= 0:
                raise ValueError(f"{name} must be positive, got {v}")
        self.tail_silence_ms = tail_silence_ms
        self.min_speech_ms = min_speech_ms
        self.min_hold_ms = min_hold_ms

    def decide(self, events: list[tuple[int, str]], now_ms: int) -> str:
        """对 (t_ms, kind) 时间线在 now_ms 时刻做三态裁决。

        返回：
        "stop"  代理正在说 + 用户已开口（barge-in：让位，TurnBuffer.interrupt
                的策略入口）；
        "speak" 用户话轮完成：有声 ≥ min_speech_ms、尾部静默 ≥ tail_silence_ms、
                意图保持 ≥ min_hold_ms、代理未在说话、且该话轮尚未被应答过；
        "hold"  其余一切（用户在说 / 静默未达阈值 / 已答过 / 双方都沉默）。

        优先级 stop > speak > hold。只统计 t ≤ now_ms 的事件（未来事件忽略）。
        """
        evs = sorted(((int(t), str(k)) for t, k in events), key=lambda e: e[0])

        open_user: int | None = None
        agent_speaking = False
        last_iv: tuple[int, int] | None = None    # 最近一个闭合的用户话轮
        last_user_activity: int | None = None     # 最近一次用户事件时刻
        answered = False                          # 当前话轮是否已被 agent 接过

        for t, kind in evs:
            if t > now_ms:
                break
            if kind == "user_start":
                open_user = t
                last_user_activity = t
            elif kind == "user_end":
                if open_user is not None:
                    last_iv = (open_user, t)
                open_user = None
                last_user_activity = t
                answered = False
            elif kind == "agent_start":
                agent_speaking = True
                if open_user is None:
                    answered = True               # 不是抢话：视为已应答当前话轮
            elif kind == "agent_end":
                agent_speaking = False
            # "barge_in" 由调用方在生成事件时已处理（interrupt 语义），此处不另判

        if open_user is not None and agent_speaking:
            return "stop"

        if (open_user is None and not agent_speaking
                and last_iv is not None and not answered
                and last_iv[1] - last_iv[0] >= self.min_speech_ms
                and now_ms - last_iv[1] >= self.tail_silence_ms
                and last_user_activity is not None
                and now_ms - last_user_activity >= self.min_hold_ms):
            return "speak"

        return "hold"
