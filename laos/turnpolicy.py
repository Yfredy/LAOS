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

话轮路由（2026-10-08 ARVIS 波，R1/R2）：播报期间用户开口不再"开口即
让位"，分类后再定——附和（backchannel，"嗯嗯/对/好的"整句命中白名单）
装作没听见播报继续，其余按真打断让位（终稿权威）。语义来源：ARVIS
Full-Duplex-Model turn_controller.py / semantic_turn_router.py
（Apache-2.0）——学设计零拷贝，规则集按 laos 语义重写；语义档
（TimedTurnJudge）包一个 continue/yield/wait 三值判断后端，预算外一律
落回关键词档（离线保守），与 laos 判断层（jev 协议方言）同源。
"""
from __future__ import annotations

import threading

__all__ = ["TurnPolicy", "classify_barge_in", "normalize_utterance",
           "TimedTurnJudge", "DEFAULT_BACKCHANNEL_WORDS"]

_EVENT_KINDS = ("user_start", "user_end", "agent_start", "agent_end", "barge_in")

# ARVIS TurnController._backchannels 同位词表（Apache-2.0，学设计零拷贝），
# 补"是的"两词——中文附和最高频。整句精确命中才算（"嗯，但是…"不是附和）。
DEFAULT_BACKCHANNEL_WORDS = ("嗯", "嗯嗯", "啊", "哦", "噢", "对", "好的", "好",
                             "知道了", "继续", "是的", "yes", "yeah", "ok", "okay")

_BACKCHANNEL_STRIP = " \t\r\n，。！？、,.!?；;：:‘’“”\"'（）()[]【】"


def normalize_utterance(text: str) -> str:
    """剥空白与全/半角标点并 casefold——附和白名单匹配前的归一化。"""
    return "".join(ch for ch in str(text)
                   if ch not in _BACKCHANNEL_STRIP).casefold()


def classify_barge_in(text: str, backchannel_words) -> bool:
    """播报期间一句 ASR 终稿是否为附和（True=吞掉，播报继续不打断）。

    只有整句（归一化后）精确命中白名单才算附和；其余一切——显式打断
    短语、疑问句、半句话——都按真打断处理：终稿权威原则（ARVIS 关键词
    路由对 final 的裁决：非 backchannel 即 cancel；partial 级的 WAIT/
    最短时长闸属未来的 asr_partial 接缝，此处不预留）。
    """
    norm = normalize_utterance(text)
    return bool(norm) and norm in frozenset(backchannel_words)


class TimedTurnJudge:
    """语义话轮路由的限时包装（R2）。

    包一个 decide(assistant_tail, user_text) -> "continue" | "yield" |
    "wait" 的判断后端（laos 判断层 jev 协议方言，本地小模型或子进程皆
    可），返回 (decision, source)：成功 → ("continue"/"yield"/"wait",
    "semantic")；超时/异常/废值 → ("fallback", "timeout"/"error"/
    "invalid")，由调用方落回关键词档——失败方向与 ARVIS 不同：ARVIS
    失败保播报（宁不打断），laos 落回关键词档（附和白名单离线仍生效，
    真打断照常让位），不引入"判断服务挂了就装聋"的静默失效面。

    实现：工作线程 + join(timeout)。超时后线程仍在跑（daemon）——判断
    后端必须自兜网络层超时；这里的预算只保证决策核不被拖死。
    """

    DECISIONS = ("continue", "yield", "wait")

    def __init__(self, decide_fn, timeout_s: float = 0.12):
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._decide_fn = decide_fn
        self.timeout_s = timeout_s

    def decide(self, assistant_tail: str, user_text: str) -> tuple[str, str]:
        box: list = []

        def _run() -> None:
            try:
                box.append(("ok", self._decide_fn(assistant_tail, user_text)))
            except Exception as exc:  # 判断后端任何异常都不得带崩决策核
                box.append(("error", exc))

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(self.timeout_s)
        if not box:
            return ("fallback", "timeout")
        kind, payload = box[0]
        if kind == "error":
            return ("fallback", "error")
        if payload not in self.DECISIONS:
            return ("fallback", "invalid")
        return (payload, "semantic")


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
