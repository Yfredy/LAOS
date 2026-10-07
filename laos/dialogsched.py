# laos/dialogsched.py
"""对话调度核心——打断版本化 + 投机 prefill 窗口 + latest-only 队列。

语义复现自 voicenpu_engine（Gitee bravexyz，AGPL-3.0）的
src/scheduler/voice_scheduler.cpp / dialog_controller.cpp /
include/tts/tts_backend.h：独立实现，非代码拷贝。上游是 C++ 线程 +
条件变量；这里改为可注入时钟的单线程决策核（语义等价，I/O 由调用方
驱动），laos 审计/驱动层可直接复用。

三个关键机制（上游的精华）：

1. **generation 版本化打断**：interrupt() 递增全局代数并回调外部中止
   （LLM abort / TTS cancel）。所有流式回调在产出每一块前核对代数，
   过期代数的任何音频都不得进入播放——"迟到的回答宁可丢，不可播"。

2. **投机 prefill + PAUSE 续说合并**：用户句中停顿（VAD 静默 ≥ 观察
   窗）时，ASR 终稿被当作"投机话语"提前启动 LLM prefill，但 TTS 提交
   要等 commit 窗口；若窗口内语音恢复且累计 ≥ resume_min_samples
   （96ms × 16 sample/ms），投机轮取消（浪费的 token 数仍记指标），
   新句与旧句以"，"合并成一句重新入队。

3. **latest-only 队列**：新话语入队时清空全部排队任务（人只关心最新
   一句），被清任务的投机取消记录一并回收。

附带上游 dialog_controller 的三件纯逻辑：
- MicrophoneGate：无 AEC 时播报期间锁麦克风（半双工自保护）；
- parse_mode_request：松散口径的"切换到在线/离线模式"声控指令；
- TtsRouter：在线/离线双后端，在线失败且一句未发时降级离线（句中
  不换声音），降级一次后对外可查询。

纯 stdlib；clock/sleep 可注入。
"""
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Protocol, Set

Clock = Callable[[], float]

ONLINE_WORDS = ("在线", "联网", "云端")
OFFLINE_WORDS = ("离线", "脱机", "断网", "本地")
SWITCH_VERBS = ("模式", "切换", "切到", "切成", "改成", "换成", "变成", "转到",
                "开启", "启用", "进入")
MAX_COMMAND_BYTES = 60

# ---------------------------------------------------------------- 埋点发射
# 可选 on_event 回调（装配层接线，生产核不 import telemetry）：
# 默认 None 零行为变化；回调异常吞掉——埋点永不影响主链路。


def safe_emit(on_event: Optional[Callable[[str, dict], None]],
              event: str, fields: dict) -> None:
    """发射埋点事件；on_event=None 或回调抛错均零影响主链路。"""
    if on_event is None:
        return
    try:
        on_event(event, fields)
    except Exception:
        pass


def _sha8(text: str) -> str:
    """话语脱敏指纹（设计 §3.5 禁止对照行）：明文禁入事件，仅 sha256 前 8 位。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- 打断版本化

class GenerationGate:
    """全局代数：interrupt() 作废一切在途流，is_current() 是每块产出的
    准入检查。on_interrupt 回调（可为 None）用于外部 abort LLM/TTS。"""

    def __init__(self, on_interrupt: Optional[Callable[[], None]] = None):
        self._generation = 0
        self._on_interrupt = on_interrupt
        self._lock = threading.Lock()

    def interrupt(self) -> int:
        with self._lock:
            self._generation += 1
            current = self._generation
        if self._on_interrupt:
            self._on_interrupt()
        return current

    def is_current(self, generation: int) -> bool:
        with self._lock:
            return self._generation == generation

    def current(self) -> int:
        with self._lock:
            return self._generation


# ------------------------------------------------------- 投机 prefill / 合并

@dataclass
class PauseCandidate:
    text: str
    commit_deadline: float
    merged_segments: int = 1


class PauseWindow:
    """句中停顿的投机窗口状态机（上游 VoiceScheduler 的 pause_* 成员）。

    on_event 可选埋点回调（默认 None 零行为变化）：投机轮取消时收
    ("d.speculative.cancel", {...})，计数脱敏级（设计 §3.5）；回调异常
    吞掉，埋点永不影响主链路。
    """

    def __init__(self, clock: Clock = time.monotonic,
                 on_event: Optional[Callable[[str, dict], None]] = None):
        self._clock = clock
        self._on_event = on_event
        self._lock = threading.Lock()
        self.observation_ms = 500
        self.resume_min_samples = 96 * 16      # 96ms × 16 sample/ms
        self._pending_text = ""
        self._merge_count = 0
        self._merge_pending = False
        self._speculative_id = 0
        self._cancelled: Set[int] = set()
        self._committed_id = 0
        self._commit_deadline = 0.0
        self._resume_candidate = False
        self._resume_samples = 0

    def configure(self, observation_ms: int, resume_min_ms: int) -> None:
        with self._lock:
            self.observation_ms = max(0, observation_ms)
            self.resume_min_samples = max(0, resume_min_ms) * 16

    def prepare_candidate(self, text: str) -> PauseCandidate:
        """投机话语候选：若上一投机轮被续说取消，与残留文本以"，"合并。"""
        with self._lock:
            merged = text
            count = 1
            if self._merge_pending and self._pending_text:
                merged = self._pending_text + "，" + text
                count = self._merge_count + 1
            self._pending_text = merged
            self._merge_count = count
            self._merge_pending = False
            return PauseCandidate(merged,
                                  self._clock() + self.observation_ms / 1000.0,
                                  count)

    def register_dialog(self, dialog_id: int, speculative: bool,
                        commit_deadline: float) -> None:
        """新对话轮注册：非投机轮立即作废挂着的投机轮。"""
        with self._lock:
            if not speculative:
                if self._speculative_id:
                    self._cancelled.add(self._speculative_id)
                self._speculative_id = 0
                self._pending_text = ""
                self._merge_count = 0
                self._merge_pending = False
                return
            if self._speculative_id:
                self._cancelled.add(self._speculative_id)
            self._speculative_id = dialog_id
            self._commit_deadline = commit_deadline

    def handle_speech_activity(self, speech_started: bool, speech_active: bool,
                               sample_count: int) -> bool:
        """每个音频块调用。窗口内语音恢复且累计达 resume_min_samples →
        取消投机轮并置合并标志。返回是否发生了取消（调用方应 interrupt）。"""
        with self._lock:
            if (speech_started and self._speculative_id
                    and self._clock() < self._commit_deadline):
                self._resume_candidate = True
                self._resume_samples = 0
            if not self._resume_candidate:
                return False
            if not speech_active:
                self._resume_candidate = False
                self._resume_samples = 0
                return False
            self._resume_samples += sample_count
            if self._resume_samples < self.resume_min_samples:
                return False
            self._cancelled.add(self._speculative_id)
            safe_emit(self._on_event, "d.speculative.cancel", {
                "dialog_id": self._speculative_id, "reason": "resume_cancel",
                "merged": True, "tokens_wasted_est": 0,
                "resume_samples": self._resume_samples})
            self._speculative_id = 0
            self._committed_id = 0
            self._merge_pending = True
            self._resume_candidate = False
            self._resume_samples = 0
            return True

    def commit_decision(self, dialog_id: int, now: float) -> str:
        """投机轮 TTS 提交判定：'commit' | 'wait' | 'cancel'。"""
        with self._lock:
            if dialog_id in self._cancelled:
                return "cancel"
            if self._committed_id == dialog_id:
                return "commit"
            if self._speculative_id not in (0, dialog_id):
                return "cancel"
            resume_deadline = self._commit_deadline + 0.2   # 上游 +200ms
            if now >= resume_deadline and self._resume_candidate:
                self._resume_candidate = False
                self._resume_samples = 0
            if now >= self._commit_deadline and not self._resume_candidate:
                self._committed_id = dialog_id
                if self._speculative_id == dialog_id:
                    self._speculative_id = 0
                self._pending_text = ""
                self._merge_count = 0
                self._merge_pending = False
                return "commit"
            return "wait"

    def take_cancelled(self, dialog_id: int) -> bool:
        with self._lock:
            if dialog_id in self._cancelled:
                self._cancelled.discard(dialog_id)
                return True
            return False

    def reset(self) -> None:
        with self._lock:
            self._pending_text = ""
            self._merge_count = 0
            self._merge_pending = False
            self._speculative_id = 0
            self._cancelled.clear()
            self._committed_id = 0
            self._resume_candidate = False
            self._resume_samples = 0


# ----------------------------------------------------------- latest-only 队列

@dataclass
class DialogJob:
    id: int
    generation: int
    use_llm: bool
    text: str
    speculative: bool = False
    commit_deadline: float = 0.0
    merged_segments: int = 1


class DialogQueue:
    """新任务入队即清空排队（latest-only）；被清任务的投机取消记录回收。

    on_event 可选埋点回调（默认 None 零行为变化）：成功入队后收
    ("d.dialog.turn", {...})——最小发射点，无明文 text（sha8 脱敏，
    设计 §3.5）；回调异常吞掉，埋点永不影响主链路。
    """

    def __init__(self, pause: PauseWindow, gate: GenerationGate,
                 clock: Clock = time.monotonic,
                 on_event: Optional[Callable[[str, dict], None]] = None):
        self._pause = pause
        self._gate = gate
        self._clock = clock
        self._on_event = on_event
        self._lock = threading.Lock()
        self._jobs: List[DialogJob] = []
        self._next_id = 0
        self.dropped: int = 0

    def enqueue(self, use_llm: bool, text: str, speculative: bool = False,
                commit_deadline: float = 0.0, merged_segments: int = 1) -> Optional[DialogJob]:
        if not text:
            return None
        generation = self._gate.interrupt()
        with self._lock:
            self._next_id += 1
            job_id = self._next_id
            self.dropped += len(self._jobs)
            for stale in self._jobs:
                self._pause.take_cancelled(stale.id)   # 不会再到 writeMetrics
            self._jobs = [DialogJob(job_id, generation, use_llm, text,
                                    speculative, commit_deadline, merged_segments)]
        self._pause.register_dialog(job_id, speculative, commit_deadline)
        safe_emit(self._on_event, "d.dialog.turn", {
            "turn_id": job_id, "generation": generation, "use_llm": use_llm,
            "speculative": speculative, "merged_segments": merged_segments,
            "utter_len": len(text), "utter_sha8": _sha8(text)})
        return self._jobs[0]

    def pop(self) -> Optional[DialogJob]:
        with self._lock:
            return self._jobs.pop(0) if self._jobs else None


# ------------------------------------------------------------- 半双工麦克风闸

class MicrophoneGate:
    """无 AEC（或 AEC 未就绪）时：播报期间及其后 post_tts_guard_ms 内
    麦克风输入视为自回声，直接抑制。barge_in + aec_ready 时恒放行。"""

    def __init__(self, sample_rate: int = 16000,
                 post_tts_guard_ms: float = 400.0,
                 clock: Clock = time.monotonic):
        self.sample_rate = sample_rate
        self.post_tts_guard_ms = post_tts_guard_ms
        self._clock = clock
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    def allow(self, aec_ready: bool, barge_in_enabled: bool) -> bool:
        if barge_in_enabled and aec_ready:
            return True
        with self._lock:
            return self._clock() >= self._blocked_until

    def emit_audio(self, sample_count: int) -> None:
        duration = sample_count / self.sample_rate
        with self._lock:
            now = self._clock()
            self._blocked_until = max(now, self._blocked_until) + duration

    def extend_guard(self) -> None:
        """一轮回答结束：若仍在播报，追加 guard 窗口。"""
        with self._lock:
            now = self._clock()
            if self._blocked_until > now:
                self._blocked_until += self.post_tts_guard_ms / 1000.0


# --------------------------------------------------------------- 声控模式切换

def parse_mode_request(text: str) -> Optional[str]:
    """'切换到在线模式'/'改成离线吧' → 'online'/'offline'；非指令 → None。

    松散口径（上游同款）：≤60 字节；在线词与离线词互斥出现；且带一个
    切换类动词（或裸"…模式"）。"""
    if len(text.encode("utf-8")) > MAX_COMMAND_BYTES:
        return None
    online = any(w in text for w in ONLINE_WORDS)
    offline = any(w in text for w in OFFLINE_WORDS)
    if online == offline:
        return None
    if not any(v in text for v in SWITCH_VERBS):
        return None
    return "online" if online else "offline"


# --------------------------------------------------------------- TTS 双后端

class TtsBackendP(Protocol):
    def ready(self) -> bool: ...
    def synthesize_stream(self, text: str,
                          sink: Callable[[List[float]], bool]) -> bool: ...
    def cancel(self) -> None: ...
    def sample_rate(self) -> int: ...
    def name(self) -> str: ...


class TtsRouter:
    """在线/离线路由：select 校验就绪与采样率一致；在线失败且本轮一句
    未发时降级离线；同一轮回答已发出在线音频则句中不换声音。"""

    def __init__(self, offline: TtsBackendP, online: TtsBackendP,
                 fallback: bool = True):
        self._offline = offline
        self._online = online
        self._fallback = fallback
        self._active: TtsBackendP = offline
        self._online_emitted = False
        self._fell_back = False
        self._lock = threading.Lock()

    def select(self, backend: str) -> bool:
        target = (self._offline if backend == "offline" else
                  self._online if backend == "online" else None)
        if (target is None or not target.ready() or
                target.sample_rate() != self._offline.sample_rate()):
            return False
        with self._lock:
            self._active = target
        return True

    def synthesize_stream(self, text: str,
                          sink: Callable[[List[float]], bool]) -> bool:
        backend = self._active
        emitted = False

        def guarded(chunk: List[float]) -> bool:
            nonlocal emitted
            emitted = True
            if backend is self._online:
                self._online_emitted = True
            return sink(chunk)

        if backend.synthesize_stream(text, guarded):
            return True
        with self._lock:
            if (backend is not self._online or not self._fallback or emitted
                    or self._online_emitted):
                return False
        if not self._offline.synthesize_stream(text, sink):
            return False
        with self._lock:
            self._fell_back = True
        return True

    def take_fell_back(self) -> bool:
        with self._lock:
            value = self._fell_back
            self._fell_back = False
            return value

    def cancel(self) -> None:
        self._active.cancel()
        with self._lock:
            self._online_emitted = False

    def sample_rate(self) -> int:
        return self._active.sample_rate()

    def name(self) -> str:
        return self._active.name()
