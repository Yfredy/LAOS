"""dialogflow —— 对话管线装配：事件防火墙 → 唤醒闸 → 对话队列 → JIT 记忆。

把既有的单件决策核装成一条可驱动的对话管线（单线程决策核，I/O 由
调用方驱动——与 dialogsched 同哲学）：

    asr/barge_in/wake 入口 ──▶ EventRouter（evroute，esp-claw 事件规则表
                                转译：声明式路由+DROP 防火墙）
                            └─▶ WakeGate（唤醒会话闸门，voicenpu 语义；
                                R1：播报中的终稿先过话轮路由——附和吞掉、
                                真打断让位）
                                  └─▶ DialogQueue（latest-only，v0.21.0
                                      起 d.dialog.turn phase="queued"）
    turn_done ──▶ phase="done" 补发（v0.21.0 明言"完成态归装配层"的债）
              ──▶ JitMem outcome 回填（v0.24.0 四步循环的第④步）

R2 语义话轮路由（2026-10-08 ARVIS 波，opt-in）：turn_judge 注入
（turnpolicy.TimedTurnJudge 兼容——decide(assistant_tail, user_text) →
(decision, source)）时，播报中的终稿先问判断层：continue=吞（播报
继续）/ yield·wait=让位进 turn / fallback=落回关键词档；每次裁决发
d.dialog.turn_route 事件（无文本，脱敏级）。助手侧上下文由调用方
note_answer() 喂入（滚动尾串）。

R3 播报时窗（ARVIS AnnouncementWindow 语义）：announce(text) 把后台
任务的播报压进窗口——用户说话中 / 话轮未落地 / TTS 音频未走完三条件
全空才放行；阻塞的挂起（FIFO），窗口打开（speech_ended / turn_done
后音频走完 / tick）自动冲刷。放行队列由调用方 take_announcements()
取走播报——不走 DialogQueue（latest-only 会互相清队），也不过唤醒闸
（agent 主动发声，治理在内核侧）。

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
from .turnpolicy import classify_barge_in
from .wakegate import WakeGate

Clock = Callable[[], float]
OnEvent = Callable[[str, dict], None]

ANSWER_TAIL_CHARS = 2000   # 语义路由的助手侧滚动上下文（ARVIS 用 4000，个人记忆库场景减半）


class DialogPipeline:
    """装配层：组合件全部可注入，缺省自建对话核；router/curator 可为
    None（无路由=事件直通，无记忆=纯对话）；turn_judge 可为 None
    （无判断层=关键词档话轮路由，R1 仍生效）。"""

    def __init__(self, wake_gate: WakeGate,
                 router: Optional[EventRouter] = None,
                 curator: Optional[Curator] = None,
                 on_event: Optional[OnEvent] = None,
                 clock: Clock = time.monotonic,
                 turn_judge=None):
        self.wake_gate = wake_gate
        self.router = router
        self.curator = curator
        self.turn_judge = turn_judge
        self._on_event = on_event
        self._clock = clock
        self.gate = GenerationGate()
        self.pause = PauseWindow(clock=clock)
        # 队列埋点与装配层埋点走同一 sink：queued/done 两种 phase 同流
        self.queue = DialogQueue(self.pause, self.gate, clock=clock,
                                 on_event=on_event)
        self._payload_id: Optional[int] = None   # 会话级 JIT payload
        self._last_job: Optional[DialogJob] = None
        # R2 语义路由状态
        self._answer_tail = ""
        self._last_route: Optional[dict] = None
        if turn_judge is not None:
            self.wake_gate.set_barge_classifier(self._route_barge)
        # R3 播报时窗状态
        self._user_speaking = False
        self._turn_pending = False
        self._audio_until = 0.0
        self._ann_pending: list[str] = []   # 窗口阻塞中
        self._ann_ready: list[str] = []     # 已放行待取

    # -- 入口（先过防火墙，再进对话核）--------------------------------------
    def wake(self) -> bool:
        if self._dropped({"type": "wake.word"}):
            return False
        woke = self.wake_gate.wake()
        if woke:
            self._payload_id = None   # 新会话：JIT payload 重新整理
        return woke

    def asr_final(self, text: str) -> Optional[DialogJob]:
        """一句 ASR 终稿：防火墙 → 唤醒闸（播报中先过话轮路由）→
        （会话首 turn）curate → 入队。附和/continue 吞掉返回 None。"""
        if self._dropped({"type": "asr.final", "text": text}):
            return None
        self._user_speaking = False          # 终稿落地：用户这句说完
        self._last_route = None
        result = self.wake_gate.process(text)
        if self._last_route is not None:
            # 路由裁决进审计：吞（continue/附和）与让位（yield/wait）两态
            # 都发——被吞的话轮也是一次治理决策，不可只记放行
            safe_emit(self._on_event, "d.dialog.turn_route",
                      dict(self._last_route))
            self._last_route = None
        if not result.answer:
            return None
        if self.curator is not None and self._payload_id is None:
            payload = self.curator.curate(result.text)
            self._payload_id = payload["id"]
        job = self.queue.enqueue(use_llm=True, text=result.text)
        if job is not None:
            self._last_job = job
            self._turn_pending = True
        return job

    def barge_in(self) -> bool:
        if self._dropped({"type": "user.barge_in"}):
            return False
        return self.wake_gate.barge_in()

    def speech_started(self) -> None:
        if self._dropped({"type": "vad.speech_start"}):
            return
        self._user_speaking = True
        self.wake_gate.speech_started()

    def speech_ended(self) -> None:
        """VAD 语音终点：用户这句说完——播报时窗解阻 + 冲刷挂起播报。
        （VAD 终点不改变唤醒态，仅驱动 R3 窗口。）"""
        self._user_speaking = False
        self._try_flush_announcements()

    def note_answer(self, text: str) -> None:
        """喂助手侧播报文本（R2 语义路由的 assistant_tail 上下文，
        滚动保留尾串）。调用方在 TTS 播报时逐段喂入即可。"""
        if text:
            self._answer_tail = (self._answer_tail + str(text))[-ANSWER_TAIL_CHARS:]

    # -- R3 播报时窗 ---------------------------------------------------------
    def announce(self, text: str) -> bool:
        """后台播报：窗口开=立即放行（True），阻塞=挂起 FIFO（False）。

        窗口三条件（ARVIS AnnouncementWindow 语义）：用户说话中 /
        话轮未落地（asr_final→turn_done 之间）/ TTS 音频未走完
        （turn_done 的 tts_remaining_sec 计的截止线）。放行/挂起均发
        d.dialog.announce 事件（accepted/pending，无文本——脱敏级）。
        """
        text = str(text)
        if not text:
            return False
        if self._ann_window_blocked():
            self._ann_pending.append(text)
            safe_emit(self._on_event, "d.dialog.announce",
                      {"accepted": False, "pending": len(self._ann_pending)})
            return False
        self._ann_ready.append(text)
        safe_emit(self._on_event, "d.dialog.announce",
                  {"accepted": True, "pending": len(self._ann_pending)})
        return True

    def take_announcements(self) -> list[str]:
        """取走已放行的播报（FIFO，取走即清）。调用方负责实际发声。"""
        out, self._ann_ready = self._ann_ready, []
        return out

    def _ann_window_blocked(self) -> bool:
        return (self._user_speaking or self._turn_pending
                or self._clock() < self._audio_until)

    def _try_flush_announcements(self) -> None:
        if self._ann_pending and not self._ann_window_blocked():
            self._ann_ready.extend(self._ann_pending)
            self._ann_pending = []
            safe_emit(self._on_event, "d.dialog.announce",
                      {"accepted": True, "pending": 0,
                       "flushed": len(self._ann_ready)})

    # -- 出口 ----------------------------------------------------------------
    def turn_done(self, ok: bool, tts_remaining_sec: float = 0.0) -> None:
        """一轮回答结束：JIT outcome 回填 + FollowUp 窗 + phase="done" 补发
        + 播报时窗记 TTS 截止线（R3）。"""
        if self.curator is not None and self._payload_id is not None:
            self.curator.note_outcome(self._payload_id, bool(ok))
        self.wake_gate.finish_turn(tts_remaining_sec)
        if self._last_job is not None:
            safe_emit(self._on_event, "d.dialog.turn", {
                "turn_id": self._last_job.id,
                "generation": self._last_job.generation,
                "phase": "done", "ok": bool(ok)})
        self._turn_pending = False
        self._audio_until = self._clock() + max(0.0, tts_remaining_sec)
        self._try_flush_announcements()

    # -- 周期与观测 ----------------------------------------------------------
    def tick(self) -> bool:
        changed = self.wake_gate.tick()
        self._try_flush_announcements()   # TTS 截止线过了就冲刷（R3）
        return changed

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
    def _route_barge(self, text: str) -> bool:
        """R2 语义路由（wakegate 话轮分类注入）：True=吞。

        continue=吞（播报继续）；yield/wait=让位进 turn（wait 的澄清
        语义归执行方，裁决经 d.dialog.turn_route 可观测）；fallback=
        落回关键词档（附和白名单离线仍生效）。在 wakegate 锁内执行——
        判断后端须自兜超时（TimedTurnJudge 已限时）。
        """
        decision, source = self.turn_judge.decide(self._answer_tail, text)
        self._last_route = {"decision": decision, "source": source}
        if decision == "continue":
            return True
        if decision == "fallback":
            return classify_barge_in(text, self.wake_gate.backchannel_words)
        return False

    def _dropped(self, event: dict) -> bool:
        if self.router is None:
            return False
        return self.router.handle(event).dropped
