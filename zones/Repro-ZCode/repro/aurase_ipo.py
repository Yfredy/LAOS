"""AuraSE-IPO 决策面规则版复现（arXiv 2610.06632v1，§Inference Policy Optimization）。

复现的是 IPO 的**决策与治理逻辑**，不是神经训练（MMDiT 27 块 + 8×A100 级
GPU-hours 违反本区纪律，诚实偏差见模块地图登记）。逐条对应论文原文：

- Eq.13 多目标奖励 R(·) = Σ_q w_q r_q，权重 OVRL:WER:SIM:SBS = 4:2:2:2
  （"The normalized reward weights ... by 4:2:2:2"，质量 40% + 保真 60%，
  "mitigating single-metric reward hacking"）。
- 偏好对构造："We enumerate pairs with a positive reward gap and sample one
  per utterance with probability proportional to that gap"——正差对枚举 +
  差距比例采样（不总塌缩到 best-worst）。
- Fig.2c 边际过滤：margin δ（论文 δ=0.20 平均 5.7 对/话语，8 候选）。
- 有界缓冲复用："after T_r bounded-reuse optimization steps, we replace the
  buffer B with fresh candidates from the updated model and re-sync the
  anchor to it"——锚点随模型前移（on-policy），对拍 offline DPO 的冻结锚。
- Eq.14-15 目标：L = −log σ(β[Δ(x+) − Δ(x−)])，Δ(x) = E_θold(x) − E_θ(x)，
  能量 E ∝ −log π（FM-DPO 速度误差代理）。本文件 E 为线性打分器 θ·f，
  解析梯度 SGD——验证"锚点相对边际"的更新方向语义。
- Table 2 诊断统计：reward spread = mean per-utterance best−worst gap；
  Fig.2b：per-policy 胜率分布（uniform = 1/M）。

诚实偏差（相对论文）：
1. 归一化细节在 supplementary（v1 未含），本实现用 utterance 内 min-max
   （保序：utterance 内单指标排序不变，权重交互后语义完好）；
2. WER 为 lower-better，取 1−norm 后并入加权和（论文同义）；
3. 候选特征/能量全是合成数据，论文 Table 3/6 的数值一概不断言；
4. 锚点刷新 vs 冻结的对比只做构造性演示（方向性），不复现训练曲线。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

METRICS = ("OVRL", "WER", "SIM", "SBS")
REWARD_WEIGHTS = {"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0}
LOWER_BETTER = frozenset({"WER"})
DEPLOYMENT_POLICY = (0, 1.0, 10)  # (CFG, temp, steps)——论文 §Main Results 尾注


def normalize_candidates(values: list[float],
                         lower_better: bool = False) -> list[float]:
    """utterance 内 min-max 归一到 [0,1]；lower-better 翻转（WER 越低越好）。"""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)  # 无区分度：全部中性满分（保序恒等）
    norm = [(v - lo) / (hi - lo) for v in values]
    return [1.0 - n for n in norm] if lower_better else norm


def reward(candidates: list[dict[str, float]],
           weights: dict[str, float] | None = None) -> list[float]:
    """Eq.13：逐指标 utterance 内归一 → 加权和。candidates 同一话语的 M 个候选。"""
    weights = weights or REWARD_WEIGHTS
    if not candidates:
        return []
    per_metric = {m: normalize_candidates([c[m] for c in candidates],
                                          m in LOWER_BETTER)
                  for m in METRICS}
    total_w = sum(weights[m] for m in METRICS)
    return [sum(weights[m] * per_metric[m][i] for m in METRICS) / total_w
            for i in range(len(candidates))]


@dataclass(frozen=True)
class Pair:
    chosen: int      # 候选下标（奖励高者）
    rejected: int
    gap: float       # R(chosen) − R(rejected)，恒 > margin


def enumerate_pairs(rewards: list[float],
                    margin: float = 0.0) -> list[Pair]:
    """正差对全集（i,j 有序：r_i − r_j > margin）。Fig.2c 的 δ 即 margin。"""
    return [Pair(i, j, rewards[i] - rewards[j])
            for i in range(len(rewards))
            for j in range(len(rewards))
            if rewards[i] - rewards[j] > margin]


def sample_pair(pairs: list[Pair],
                rng: random.Random) -> Pair | None:
    """差距比例采样：P(pair) ∝ gap（论文原句）。空表 → None。"""
    if not pairs:
        return None
    total = sum(p.gap for p in pairs)
    pick = rng.random() * total
    acc = 0.0
    for p in pairs:
        acc += p.gap
        if pick <= acc:
            return p
    return pairs[-1]  # 浮点边界兜底


def reward_spread(rewards_matrix: list[list[float]]) -> float:
    """Table 2 的 reward spread：mean per-utterance (best − worst)。"""
    if not rewards_matrix:
        return 0.0
    return sum(max(row) - min(row) for row in rewards_matrix) / len(rewards_matrix)


def winner_distribution(rewards_matrix: list[list[float]]) -> list[float]:
    """Fig.2b：每策略胜率（per-utterance argmax 计数 / 话语数；平分计 1/M）。"""
    if not rewards_matrix:
        return []
    m = len(rewards_matrix[0])
    wins = [0.0] * m
    for row in rewards_matrix:
        best = max(row)
        winners = [i for i, r in enumerate(row) if r == best]
        for i in winners:
            wins[i] += 1.0 / len(winners)
    n = len(rewards_matrix)
    return [w / n for w in wins]


@dataclass
class PreferenceBuffer:
    """有界复用缓冲：take 计数扣减，耗尽即 stale；refresh 换血并前移锚点版本。"""
    max_reuse: int                          # 论文的 T_r
    pairs: list[Pair] = field(default_factory=list)
    reuse_left: int = 0
    anchor_version: int = 0

    def load(self, pairs: list[Pair]) -> None:
        self.pairs = list(pairs)
        self.reuse_left = self.max_reuse
        self.anchor_version += 1

    def take(self) -> Pair | None:
        if self.reuse_left <= 0 or not self.pairs:
            return None
        self.reuse_left -= 1
        return self.pairs[self.reuse_left % len(self.pairs)]

    @property
    def stale(self) -> bool:
        return self.reuse_left <= 0


def energy(theta: list[float], feats: list[float]) -> float:
    """E_θ(x) = θ·f（论文中是 FM 速度误差代理；本处线性打分器，见诚实偏差#3）。"""
    return sum(t * f for t, f in zip(theta, feats))


def ipo_loss(theta: list[float], anchor: list[float],
             feats_plus: list[float], feats_minus: list[float],
             beta: float = 0.1) -> float:
    """Eq.14-15：−log σ(β[Δ(x+) − Δ(x−)])，Δ(x) = E_θold(x) − E_θ(x)。"""
    delta_plus = energy(anchor, feats_plus) - energy(theta, feats_plus)
    delta_minus = energy(anchor, feats_minus) - energy(theta, feats_minus)
    z = beta * (delta_plus - delta_minus)
    # log σ(z) 数值稳定式
    return -(-math.log1p(math.exp(-z)) if z >= 0 else z - math.log1p(math.exp(z)))


def apply_pair_update(theta: list[float], anchor: list[float],
                      feats_plus: list[float], feats_minus: list[float],
                      beta: float = 0.1, lr: float = 0.05) -> list[float]:
    """单对 SGD：L 对 θ 的解析梯度 dL/dθ = (1−σ(z))·β·(f+ − f−)。

    m = β[(E_a(x+)−E_a(x−)) − θ·(f+ − f−)]，增大 m ⇔ 压低 E(x+) 相对 E(x−)
    ——即"chosen 更受青睐"的锚点相对边际方向（推导与数值锚点见测试）。
    """
    delta_plus = energy(anchor, feats_plus) - energy(theta, feats_plus)
    delta_minus = energy(anchor, feats_minus) - energy(theta, feats_minus)
    z = beta * (delta_plus - delta_minus)
    sigma = 1.0 / (1.0 + math.exp(-z))
    coef = lr * (1.0 - sigma) * beta
    return [t - coef * (fp - fm) for t, fp, fm
            in zip(theta, feats_plus, feats_minus)]


def run_policy_loop(candidates_by_round: list[list[dict[str, float]]],
                    feats_by_round: list[list[list[float]]],
                    max_reuse: int = 4, beta: float = 0.1, lr: float = 0.05,
                    refresh_anchor: bool = True, seed: int = 7
                    ) -> tuple[list[float], list[float]]:
    """IPO 闭环玩具驱动（脚本用）：rounds × (奖励→对采样→缓冲→T_r 步更新)。

    refresh_anchor=True 即 IPO（每轮锚点随模型前移）；False 即 offline DPO
    语义（锚点冻结在初始模型）。返回 (最终θ, 每轮平均奖励轨迹)。
    """
    rng = random.Random(seed)
    dim = len(feats_by_round[0][0])
    theta = [0.0] * dim
    anchor = list(theta)
    buf = PreferenceBuffer(max_reuse=max_reuse)
    trajectory: list[float] = []

    for cand, feats in zip(candidates_by_round, feats_by_round):
        pairs = enumerate_pairs(reward(cand))
        buf.load(pairs)
        if refresh_anchor:
            anchor = list(theta)  # 生成本轮候选的模型即本轮锚点（on-policy）
        taken = 0
        while not buf.stale and taken < max_reuse:
            pair = buf.take()
            if pair is None:
                break
            theta = apply_pair_update(theta, anchor,
                                      feats[pair.chosen],
                                      feats[pair.rejected],
                                      beta=beta, lr=lr)
            taken += 1
        trajectory.append(sum(reward(cand)) / len(cand))
    return theta, trajectory
