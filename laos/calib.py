"""calib —— 概率校准度量：Brier 分数 / 期望校准误差 ECE / 可靠性曲线。

来源：docs/research/2026-10-07-cloudflare-clef.md §二/§三——Clef 训练用
label-smoothed CE + **Brier loss 概率校准**，RLCD（校准决策强化学习）二级
优化；§四采纳件 P3（"Brier/RLCD 校准 → laos 校准台方法库条目"）。核心
命题（§三.3）：**决策模型不只对答案，还要对概率负责**——laos 四闸门的
阈值本质也是概率门，这三个函数就是概率门的评判尺：Clef 用 Brier loss
训练校准，laos 校准台用它们评测校准。

度量表（均为"越低越好"，完美校准 = 0）：

    brier_score   均方误差 mean((p-o)^2)：同时惩罚过度自信与不自信，也
                  惩罚答错；对 0/1 结果，过度自信的代价是 (1-p)^2 量级。
    ece           期望校准误差：分桶 |桶内平均置信 - 桶内实际频率| 按桶
                  样本数加权求和；只看置信与频率的偏差，不管答案对错。
    reliability   可靠性曲线原始数据 [(bucket_lower, avg_p, freq, n), ...]
                  （只含有样本的桶）——ECE 的可解释形态，逐桶画图即校准
                  台视图。ece() 直接由它加权重算，两函数永远一致。

分桶纪律（ece/reliability 共用）：左闭右开 [i/bins, (i+1)/bins)，最后一桶
闭（p=1.0 归入末桶）。浮点边界表示误差（0.3*10=2.9999999999999996）按
BIN_EPSILON 索引容差归位。

输入校验（三函数共用，fail-loud 与 decide.py 同款，全部 ValueError）：
    空序列 / probs 非数值或越界 [0,1] / outcomes 非 0/1（bool 是二元真值
    的自然表示，接受并归一为 0/1）/ 长度不齐；ece/reliability 另有 bins
    必须是 >=1 的整数（bool 不算）。

纯函数零依赖（stdlib only），无状态可并行。
"""
from __future__ import annotations

from typing import Sequence

__all__ = ["brier_score", "ece", "reliability"]

#: 分桶索引的浮点容差：0.3*10=2.9999999999999996 这类表示误差在此内归位
BIN_EPSILON = 1e-9


def _check_bins(bins: int) -> None:
    """bins 必须是 >=1 的整数（bool 是 int 子类，显式排除）。"""
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 1:
        raise ValueError(f"bins 必须是 >=1 的整数，实测 {bins!r}")


def _validated_pairs(probs: Sequence[float],
                     outcomes: Sequence[float]) -> list[tuple[float, float]]:
    """公共校验：等长、非空、probs∈[0,1]、outcomes∈{0,1}；返回 (p, o) 对。"""
    n = len(probs)
    if n == 0:
        raise ValueError("probs/outcomes 不能为空序列")
    if len(outcomes) != n:
        raise ValueError(f"probs/outcomes 长度不齐：{n} vs {len(outcomes)}")
    pairs: list[tuple[float, float]] = []
    for p, o in zip(probs, outcomes):
        if isinstance(p, bool) or not isinstance(p, (int, float)):
            raise ValueError(f"probs 每项必须是数值，实测 {p!r}")
        p = float(p)
        if not 0.0 <= p <= 1.0:  # nan/inf 的比较恒 False，一并在此拦截
            raise ValueError(f"probs 越界 [0,1]：{p!r}")
        if isinstance(o, bool):
            o = int(o)
        elif not isinstance(o, (int, float)):
            raise ValueError(f"outcomes 每项必须是 0/1，实测 {o!r}")
        o = float(o)
        if o not in (0.0, 1.0):
            raise ValueError(f"outcomes 每项必须是 0/1，实测 {o!r}")
        pairs.append((p, o))
    return pairs


def _bucket_index(p: float, bins: int) -> int:
    """p 的桶下标：左闭右开，最后一桶闭（p=1.0 钳回末桶）。"""
    return min(int(p * bins + BIN_EPSILON), bins - 1)


def brier_score(probs: Sequence[float],
                outcomes: Sequence[float]) -> float:
    """Brier 分数：mean((p_i - o_i)^2)。完美校准 = 0，全错自信 = 1。

    Clef 训练目标（Brier loss 概率校准）的度量面：训练时最小化它，校准
    台评测时也看它。手算锚点：probs=[1,0,1] vs outcomes=[1,0,0] → 1/3。
    """
    pairs = _validated_pairs(probs, outcomes)
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def reliability(probs: Sequence[float], outcomes: Sequence[float],
                bins: int = 10) -> list[tuple[float, float, float, int]]:
    """可靠性曲线数据：[(bucket_lower, avg_p, empirical_freq, n), ...]。

    只返回有样本的桶（空桶不占行）；bucket_lower 是桶左端点 i/bins，
    avg_p 桶内平均预测概率，empirical_freq 桶内 0/1 实际频率，n 样本数。
    """
    _check_bins(bins)
    pairs = _validated_pairs(probs, outcomes)
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for p, o in pairs:
        buckets[_bucket_index(p, bins)].append((p, o))
    curve: list[tuple[float, float, float, int]] = []
    for idx, members in enumerate(buckets):
        if not members:
            continue
        n = len(members)
        curve.append((
            idx / bins,
            sum(p for p, _ in members) / n,
            sum(o for _, o in members) / n,
            n,
        ))
    return curve


def ece(probs: Sequence[float], outcomes: Sequence[float],
        bins: int = 10) -> float:
    """期望校准误差：sum_b (n_b / N) * |avg_p_b - freq_b|。

    由 reliability() 输出直接加权重算——ECE 与可靠性曲线永远一致（评测
    口径单一来源）。手算锚点：[0.05,0.15,0.95,1.0] vs [0,1,1,1]，bins=10
    → 0.25*0.05 + 0.25*0.85 + 0.5*0.025 = 0.2375。
    """
    curve = reliability(probs, outcomes, bins=bins)
    total = sum(n for *_, n in curve)  # 空桶已滤，总样本数不变
    return sum(n / total * abs(avg_p - freq)
               for _, avg_p, freq, n in curve)
