"""dialogflow —— 对话管线装配：事件防火墙 → 唤醒闸 → 对话队列 → JIT 记忆。

把既有的单件决策核装成一条可驱动的对话管线（单线程决策核，I/O 由
调用方驱动——与 dialogsched 同哲学）：

    asr/barge_in/wake 入口 ──▶ EventRouter（evroute，esp-claw 事件规则表
                                转译：声明式路由+DROP 防火墙）
                            └─▶ WakeGate（唤醒会话闸门，voicenpu 语义）
                                  └─▶ DialogQueue（latest-only，v0.21.0
                                      起 d.dialog.turn phase="queued"）
    turn_done ──▶ phase="done" 补发（v0.21.0 明言"完成态归装配层"的债）
              ──▶ JitMem outcome 回填（v0.24.0 四步循环的第④步）

JIT 记忆接线（JitMem 会话级化）：会话首个放行 turn 时 `curate` 一次，
payload 缓存供全会话复用（对话的一轮≈论文的一步，全会话≈论文的一个
任务）；每轮 `turn_done(ok)` 都把即时成败 `note_outcome` 回填——reward
时间隔为零的论文语义原样保留。

env 覆盖（接线波）：LAOS_DIALOG_OBS_MS / LAOS_DIALOG_RESUME_MS →
PauseWindow.configure（configure_from_env）；LAOS_WAKE_* →
WakeConfig.from_env（wakegate.py）。
"""

from __future__ import annotations

import os
import time
from typing import Callable, Optional

from .dialogsched import DialogJob, DialogQueue, GenerationGate, PauseWindow, safe_emit
from .evroute import EventRouter
from .jitmem import Curator
from .wakegate import WakeGate

Clock = Callable[[], float]
OnEvent = Callable[[str, dict], None]


class DialogPipeline:
    """装配层：组合件全部可注入，缺省自建对话核；router/curator 可为
    None（无路由=事件直通，无记忆=纯对话）。"""

    def __init__(self, wake_gate: WakeGate,
                 router: Optional[EventRouter] = None,
                 curator: Optional[Curator] = None,
                 on_event: Optional[OnEvent] = None,
                 clock: Clock = time.monotonic):
        self.wake_gate = wake_gate
        self.router = router
        self.curator = curator
        self._on_event = on_event
        self.gate = GenerationGate()
        self.pause = PauseWindow(clock=clock)
        # 队列埋点与装配层埋点走同一 sink：queued/done 两种 phase 同流
        self.queue = DialogQueue(self.pause, self.gate, clock=clock,
                                 on_event=on_event)
        self._payload_id: Optional[int] = None   # 会话级 JIT payload
        self._last_job: Optional[DialogJob] = None

    # -- 入口（先过防火墙，再进对话核）--------------------------------------
    def wake(self) -> bool:
        if self._dropped({"type": "wake.word"}):
            return False
        woke = self.wake_gate.wake()
        if woke:
            self._payload_id = None   # 新会话：JIT payload 重新整理
        return woke

    def asr_final(self, text: str) -> Optional[DialogJob]:
        """一句 ASR 终稿：防火墙 → 唤醒闸 → （会话首 turn）curate → 入队。"""
        if self._dropped({"type": "asr.final", "text": text}):
            return None
        result = self.wake_gate.process(text)
        if not result.answer:
            return None
        if self.curator is not None and self._payload_id is None:
            payload = self.curator.curate(result.text)
            self._payload_id = payload["id"]
        job = self.queue.enqueue(use_llm=True, text=result.text)
        self._last_job = job
        return job

    def barge_in(self) -> bool:
        if self._dropped({"type": "user.barge_in"}):
            return False
        return self.wake_gate.barge_in()

    def speech_started(self) -> None:
        if self._dropped({"type": "vad.speech_start"}):
            return
        self.wake_gate.speech_started()

    # -- 出口 ----------------------------------------------------------------
    def turn_done(self, ok: bool, tts_remaining_sec: float = 0.0) -> None:
        """一轮回答结束：JIT outcome 回填 + FollowUp 窗 + phase="done" 补发。"""
        if self.curator is not None and self._payload_id is not None:
            self.curator.note_outcome(self._payload_id, bool(ok))
        self.wake_gate.finish_turn(tts_remaining_sec)
        if self._last_job is not None:
            safe_emit(self._on_event, "d.dialog.turn", {
                "turn_id": self._last_job.id,
                "generation": self._last_job.generation,
                "phase": "done", "ok": bool(ok)})

    # -- 周期与观测 ----------------------------------------------------------
    def tick(self) -> bool:
        return self.wake_gate.tick()

    def wake_state(self) -> str:
        return self.wake_gate.state_name()

    def configure_from_env(self, env: Optional[dict] = None) -> None:
        """LAOS_DIALOG_OBS_MS / LAOS_DIALOG_RESUME_MS → PauseWindow 参数
        （投机 prefill 观察窗/续说判定窗）。未设项保持现值；坏值回退现值。"""
        env = os.environ if env is None else env

        def _int(name: str, cur: int) -> int:
            raw = env.get(name)
            if raw is None:
                return cur
            try:
                return max(0, int(str(raw).strip()))
            except ValueError:
                return cur  # 坏值不炸：env 是用户输入，回退现值
        self.pause.configure(_int("LAOS_DIALOG_OBS_MS", self.pause.observation_ms),
                             _int("LAOS_DIALOG_RESUME_MS",
                                  self.pause.resume_min_samples // 16))

    # -- 内部 ----------------------------------------------------------------
    def _dropped(self, event: dict) -> bool:
        if self.router is None:
            return False
        return self.router.handle(event).dropped
