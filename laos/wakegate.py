# laos/wakegate.py
"""唤醒会话闸门（WakeGate）——语音对话的会话生命周期状态机。

语义复现自 voicenpu_engine（Gitee bravexyz，AGPL-3.0）的
include/scheduler/wake_gate.h：独立实现，非代码拷贝。上游把唤醒词当
"电源键"——唤醒只由专用 KWS 模型从音频线程触发（wake()），ASR 文本
永不用于唤醒；会话内每句话都进入对话，直到休眠词或超时回睡。

四态机：
    Sleeping ──wake()──▶ Listening ──process(text)──▶ Processing
       ▲                   │   ▲                          │
       └──休眠词/轮数/会话超时─┘   └──speechStarted()──────┘
                              FollowUp ◀──finishTurn()──┘
    （FollowUp 在 follow_up_timeout 内有新语音则回 Listening）

设计要点（与上游一致）：
- 唤醒后 session 计时开始，max_session_sec 到期强制回睡；
- 每轮 process() 前检查休眠词（子串匹配，去空白归一化后）；
- max_turns 轮数上限，超出静默回睡（不告警）；
- barge_in() 只在 Processing 态有效（用户打断正在播报的回答）；
- finishTurn(delay_sec) 把 TTS 播报时长并入 FollowUp 窗口，避免
  "回答刚说完就超时"。

纯 stdlib；时间源可注入（默认 time.monotonic），便于测试。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


class WakeState(Enum):
    SLEEPING = "sleeping"
    LISTENING = "listening"
    PROCESSING = "processing"
    FOLLOW_UP = "follow_up"


@dataclass
class WakeConfig:
    enabled: bool = False
    wake_words: List[str] = field(default_factory=list)
    sleep_words: List[str] = field(default_factory=list)
    follow_up_timeout_sec: float = 12.0
    max_session_sec: float = 120.0
    max_turns: int = 6


@dataclass
class WakeResult:
    answer: bool          # 这句话是否进入对话
    text: str = ""        # 归一化后的有效文本（answer=True 时非空）
    slept: bool = False   # 这句话命中了休眠词


class WakeGate:
    """唤醒会话闸门。所有方法线程安全（一把锁）。

    on_event 可选埋点回调（默认 None 零行为变化，装配层接线，本核不
    import telemetry）：状态迁移时收 ("d.wake.state_change", {...})，
    字段计数脱敏级（设计 §3.5）；回调异常吞掉，埋点永不影响主链路。
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 on_event: Optional[Callable[[str, dict], None]] = None):
        self._clock = clock
        self._on_event = on_event
        self._config = WakeConfig()
        self._state = WakeState.SLEEPING
        self._turns = 0
        self._session_started = 0.0
        self._follow_up_deadline = 0.0
        import threading
        self._lock = threading.Lock()

    def configure(self, config: WakeConfig) -> None:
        with self._lock:
            self._config = config
            self._state = (WakeState.SLEEPING if config.enabled
                           else WakeState.LISTENING)
            self._turns = 0

    def wake(self) -> bool:
        """KWS 命中唤醒词时调用。只在 Sleeping 态生效，返回是否发生迁移。"""
        with self._lock:
            if not self._config.enabled:
                return False
            now = self._clock()
            self._expire(now)
            if self._state != WakeState.SLEEPING:
                return False
            self._session_started = now
            self._turns = 0
            self._transition(WakeState.LISTENING, "wake")
            return True

    def process(self, asr_text: str) -> WakeResult:
        """一句 ASR 终稿过闸：休眠词→睡；空文本→丢；轮数满→睡；否则放行。"""
        with self._lock:
            norm = _normalize(asr_text)
            if not self._config.enabled:
                return WakeResult(True, norm, False)
            now = self._clock()
            self._expire(now)
            if self._state in (WakeState.SLEEPING, WakeState.PROCESSING):
                return WakeResult(False)
            if _contains_any(norm, self._config.sleep_words):
                self._sleep("sleep_word")
                return WakeResult(False, slept=True)
            if not norm:
                return WakeResult(False)
            if 0 < self._config.max_turns <= self._turns:
                self._sleep("max_turns")
                return WakeResult(False)
            self._transition(WakeState.PROCESSING, "turn")
            self._turns += 1
            return WakeResult(True, norm, False)

    def speech_started(self) -> None:
        """VAD 检测到新语音起点。FollowUp/Processing 回 Listening（继续听）。"""
        with self._lock:
            self._expire(self._clock())
            if self._state in (WakeState.FOLLOW_UP, WakeState.PROCESSING):
                self._state = WakeState.LISTENING

    def barge_in(self) -> bool:
        """用户在系统播报中开口。仅 Processing 态有效（打断播报）。"""
        with self._lock:
            if self._state != WakeState.PROCESSING:
                return False
            self._state = WakeState.LISTENING
            return True

    def finish_turn(self, delay_sec: float = 0.0) -> None:
        """一轮回答结束（delay_sec=TTS 剩余播报时长，并入 FollowUp 窗口）。"""
        with self._lock:
            if self._state != WakeState.PROCESSING:
                return
            self._state = WakeState.FOLLOW_UP
            wait = max(0.0, delay_sec) + self._config.follow_up_timeout_sec
            self._follow_up_deadline = self._clock() + wait

    def tick(self) -> bool:
        """周期调用：推进超时。返回状态是否发生变化。"""
        with self._lock:
            before = self._state
            self._expire(self._clock())
            return before != self._state

    def state(self) -> WakeState:
        with self._lock:
            self._expire(self._clock())
            return self._state

    def state_name(self) -> str:
        return self.state().value

    # ---- 内部（须持锁） ----

    def _expire(self, now: float) -> None:
        cfg = self._config
        if not cfg.enabled or self._state == WakeState.SLEEPING:
            return
        if (0.0 < cfg.max_session_sec and
                now - self._session_started >= cfg.max_session_sec):
            self._sleep("session_timeout")
            return
        if (self._state == WakeState.FOLLOW_UP and
                0.0 < cfg.follow_up_timeout_sec and now >= self._follow_up_deadline):
            self._sleep("followup_timeout")

    def _sleep(self, reason: str) -> None:
        self._transition(WakeState.SLEEPING, reason)
        self._turns = 0

    def _transition(self, to_state: WakeState, reason: str) -> None:
        """统一迁移出口（须持锁）：置新态并发射 d.wake.state_change 埋点
        事件（§3.5 字段：from/to/reason/turns/session_ms，计数脱敏级，
        文本永不入事件；on_event=None 或回调异常均零影响主链路）。"""
        old = self._state
        self._state = to_state
        if self._on_event is None:
            return
        try:
            self._on_event("d.wake.state_change", {
                "from": old.value, "to": to_state.value, "reason": reason,
                "turns": self._turns,
                "session_ms": int((self._clock() - self._session_started) * 1000),
            })
        except Exception:
            pass


def _normalize(text: str) -> str:
    return "".join(ch for ch in text if ch not in " \t\r\n")


def _contains_any(haystack: str, words: List[str]) -> bool:
    return any(w and w in haystack for w in words)
