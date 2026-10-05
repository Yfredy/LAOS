"""laos.duplex —— 双工时序度量：事件时间线 → 客观时序指标。

来源：Duplex-MPE（arXiv 2609.31948）把全双工能力拆成 发起 / 准确 / 沉默 /
停止 四项评分；其中 发起（响应延迟）、沉默（抢话计数）、停止（打断响应延迟）
是纯时序量，OS 层可客观计量，不需要内容语义（"准确"归 ASR/Jev 层）。

本模块消费与内核审计日志同构的 (t_seconds, kind) 事件序列，不产生事件、
无副作用。kind ∈ {"user_start","user_end","agent_start","agent_end",
"barge_in"}。

脏数据策略（宁缺毋滥）：
- 未闭合的 start（到时间线末尾仍无对应 end）→ 该区间**丢弃**，不入时长；
- 重复 start（上一段未闭合又来一个）→ 上一段作废，重新起算；
- 超出 horizon 未配对到的请求/打断 → 不计（防单条脏日志拖垮中位数）。

响应延迟配对规则：user_end 之后**第一个**合法 agent_start（该时刻用户不在
说话、且中间没有新的 user_start）——取最近一个未答的 user_end，更早的
未答 user_end 视为漏应答，丢弃。抢话（agent_start 落在用户开口区间内）
计入 premature_responses，不参与响应延迟。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = ["DuplexMetrics", "analyze", "summarize"]


@dataclass
class DuplexMetrics:
    """一次分析产出的全部时序指标（单位：秒 / 次数）。"""

    response_latencies: list[float] = field(default_factory=list)
    barge_in_latencies: list[float] = field(default_factory=list)
    overlap_durations: list[float] = field(default_factory=list)
    total_user_speech: float = 0.0
    total_agent_speech: float = 0.0
    premature_responses: int = 0
    interrupts: int = 0

    @property
    def overlap_ratio(self) -> float:
        """重叠时长 / 双方说话总时长；总时长为 0 → 0.0。"""
        denom = self.total_user_speech + self.total_agent_speech
        if denom <= 0.0:
            return 0.0
        return sum(self.overlap_durations) / denom


def _intersect(a: list[tuple[float, float]],
               b: list[tuple[float, float]]) -> list[float]:
    """两组闭开区间的逐段交时长（双方均按 start 升序）。"""
    out: list[float] = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            out.append(hi - lo)
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return out


def analyze(events: list[tuple[float, str]], *,
            horizon: float = 10.0) -> DuplexMetrics:
    """单遍扫描配对。events 无需有序（内部先排序）。"""
    m = DuplexMetrics()
    evs = sorted(((float(t), str(k)) for t, k in events), key=lambda e: e[0])

    user_iv: list[tuple[float, float]] = []
    agent_iv: list[tuple[float, float]] = []
    open_user: float | None = None
    open_agent: float | None = None
    pending_user_end: float | None = None   # 最近一个未答的 user_end
    pending_barge: float | None = None      # 最近一个未落地的 barge_in

    for t, kind in evs:
        if kind == "user_start":
            open_user = t                 # 重复 start：上一段未闭合即作废
        elif kind == "user_end":
            if open_user is not None:
                user_iv.append((open_user, t))
                m.total_user_speech += t - open_user
                open_user = None
            pending_user_end = t
        elif kind == "agent_start":
            open_agent = t                  # 代理开口即起区间（抢话也占线）
            if open_user is not None:
                m.premature_responses += 1  # 抢话：不算响应延迟
            else:
                if pending_user_end is not None and t - pending_user_end <= horizon:
                    m.response_latencies.append(t - pending_user_end)
                pending_user_end = None     # 更早未答的 user_end 一并放弃
        elif kind == "agent_end":
            if open_agent is not None:
                agent_iv.append((open_agent, t))
                m.total_agent_speech += t - open_agent
                open_agent = None
            if pending_barge is not None and t - pending_barge <= horizon:
                m.barge_in_latencies.append(t - pending_barge)
            pending_barge = None
        elif kind == "barge_in":
            m.interrupts += 1
            pending_barge = t
        else:
            raise ValueError(f"unknown event kind: {kind!r}")

    m.overlap_durations = _intersect(user_iv, agent_iv)
    return m


def _stats(xs: list[float]) -> dict:
    """median / p90（最近邻秩）/ max / n；空列表 → 统计位 None。"""
    if not xs:
        return {"median": None, "p90": None, "max": None, "n": 0}
    s = sorted(xs)
    n = len(s)
    p90 = s[max(0, math.ceil(0.9 * n) - 1)]
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {"median": med, "p90": p90, "max": s[-1], "n": n}


def summarize(m: DuplexMetrics) -> dict:
    """JSON 友好摘要（可直接进审计/日报）。"""
    return {
        "response_latency": _stats(m.response_latencies),
        "barge_in_latency": _stats(m.barge_in_latencies),
        "overlap_ratio": m.overlap_ratio,
        "overlap_total_s": sum(m.overlap_durations),
        "total_user_speech_s": m.total_user_speech,
        "total_agent_speech_s": m.total_agent_speech,
        "premature_responses": m.premature_responses,
        "interrupts": m.interrupts,
    }
