# tests/test_aurase_ipo.py —— AuraSE-IPO 决策面规则版的手算锚点测试。
# 来源：arXiv 2610.06632v1 §Inference Policy Optimization（Eq.13-15、Fig.2、Table 2）。
# 所有期望值手算推导，不引用论文模型数值（诚实偏差见模块 docstring）。
from __future__ import annotations

import math
import random

import pytest

from repro.aurase_ipo import (PreferenceBuffer, Pair, apply_pair_update,
                              enumerate_pairs, energy, ipo_loss, reward,
                              reward_spread, run_policy_loop, sample_pair,
                              winner_distribution, normalize_candidates)


class TestNormalize:
    def test_minmax_higher_better(self):
        assert normalize_candidates([1.0, 2.0, 3.0]) == [0.0, 0.5, 1.0]

    def test_minmax_lower_better_flips(self):
        # WER：越低越好 → 最小值得 1.0
        assert normalize_candidates([1.0, 2.0, 3.0], lower_better=True) == \
            [1.0, 0.5, 0.0]

    def test_constant_is_neutral_full(self):
        # 无区分度 → 中性满分（保序恒等，不产生假对比）
        assert normalize_candidates([5.0, 5.0]) == [1.0, 1.0]


class TestReward:
    CANDS = [
        {"OVRL": 3.0, "WER": 0.10, "SIM": 0.70, "SBS": 0.90},
        {"OVRL": 3.2, "WER": 0.08, "SIM": 0.75, "SBS": 0.90},
        {"OVRL": 3.4, "WER": 0.12, "SIM": 0.75, "SBS": 0.88},
    ]

    def test_hand_computed_4222(self):
        # 手算：OVRL norm [0,.5,1]；WER(lower) [.5,1,0]；SIM [0,1,1]；SBS [1,1,0]
        # cand0=(0+1+0+2)/10=0.3  cand1=(2+2+2+2)/10=0.8  cand2=(4+0+2+0)/10=0.6
        assert reward(self.CANDS) == pytest.approx([0.3, 0.8, 0.6])

    def test_winner_is_not_ovrl_best(self):
        # 4:2:2:2 下总分王（cand1）不是 OVRL 最高的 cand2——保真 60% 拉回内容
        r = reward(self.CANDS)
        assert r.index(max(r)) == 1

    def test_empty(self):
        assert reward([]) == []


class TestPairs:
    def test_positive_gap_enumeration(self):
        pairs = enumerate_pairs([0.3, 0.8, 0.6])
        assert [(p.chosen, p.rejected) for p in pairs] == [(1, 0), (1, 2), (2, 0)]

    def test_margin_filters(self):
        # Fig.2c 的 δ：margin 0.25 后只剩 gap>0.25 的两对
        pairs = enumerate_pairs([0.3, 0.8, 0.6], margin=0.25)
        assert [(p.chosen, p.rejected) for p in pairs] == [(1, 0), (2, 0)]

    def test_gap_proportional_frequencies(self):
        pairs = enumerate_pairs([0.3, 0.8, 0.6])  # gaps 0.5/0.2/0.3，和=1.0
        rng = random.Random(11)
        counts = {(1, 0): 0, (1, 2): 0, (2, 0): 0}
        n = 20000
        for _ in range(n):
            p = sample_pair(pairs, rng)
            counts[(p.chosen, p.rejected)] += 1
        assert counts[(1, 0)] / n == pytest.approx(0.5, abs=0.02)
        assert counts[(1, 2)] / n == pytest.approx(0.2, abs=0.02)
        assert counts[(2, 0)] / n == pytest.approx(0.3, abs=0.02)

    def test_seed_determinism(self):
        pairs = enumerate_pairs([0.3, 0.8, 0.6])
        a = sample_pair(pairs, random.Random(42))
        b = sample_pair(pairs, random.Random(42))
        assert (a.chosen, a.rejected) == (b.chosen, b.rejected)

    def test_empty_returns_none(self):
        assert sample_pair([], random.Random(0)) is None


class TestDiagnostics:
    def test_reward_spread_definition(self):
        # Table 2 口径：mean per-utterance best−worst
        assert reward_spread([[0.3, 0.8, 0.6], [0.9, 0.1, 0.5]]) == \
            pytest.approx((0.5 + 0.8) / 2)

    def test_winner_distribution(self):
        dist = winner_distribution([[0.3, 0.8, 0.6], [0.9, 0.1, 0.5]])
        assert dist == pytest.approx([0.5, 0.5, 0.0])

    def test_winner_distribution_tie_splits(self):
        assert winner_distribution([[0.5, 0.5]]) == pytest.approx([0.5, 0.5])


class TestBuffer:
    def test_bounded_reuse_and_refresh(self):
        buf = PreferenceBuffer(max_reuse=3)
        buf.load([Pair(1, 0, 0.5), Pair(2, 0, 0.3)])
        assert buf.anchor_version == 1 and not buf.stale
        taken = [buf.take() for _ in range(3)]
        assert all(t is not None for t in taken)
        assert buf.stale and buf.take() is None
        buf.load([Pair(0, 2, 0.1)])
        assert buf.anchor_version == 2 and buf.reuse_left == 3

    def test_take_cycles_pairs(self):
        buf = PreferenceBuffer(max_reuse=4)
        buf.load([Pair(1, 0, 0.5), Pair(2, 0, 0.3)])
        seq = [buf.take() for _ in range(4)]
        # 取用序循环覆盖全部对（不总重复同一对——best-worst 塌缩的反面）
        assert {(p.chosen, p.rejected) for p in seq} == {(1, 0), (2, 0)}


class TestObjective:
    def test_loss_at_anchor_is_log2(self):
        # θ == 锚点 → Δ=0 → z=0 → L=−log σ(0)=log 2
        theta = anchor = [0.3, -0.2, 0.1]
        assert ipo_loss(theta, anchor, [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == \
            pytest.approx(math.log(2.0))

    def test_update_direction_hand_computed(self):
        # θ=[0,0], 锚=[0,0], f+=[1,0], f−=[0,1], β=0.1, lr=0.05:
        # z=0 → σ=0.5 → coef=0.0025 → θ_new = θ − 0.0025(f+−f−) = [−0.0025, +0.0025]
        theta = apply_pair_update([0.0, 0.0], [0.0, 0.0],
                                  [1.0, 0.0], [0.0, 1.0],
                                  beta=0.1, lr=0.05)
        assert theta == pytest.approx([-0.0025, 0.0025])

    def test_update_lowers_chosen_energy_margin(self):
        feats_p, feats_m = [1.0, 0.3], [0.2, 0.9]
        anchor = [0.1, -0.1]
        before = energy(anchor, feats_m) - energy(anchor, feats_p)
        theta = list(anchor)
        for _ in range(20):
            theta = apply_pair_update(theta, anchor, feats_p, feats_m)
        after = energy(theta, feats_m) - energy(theta, feats_p)
        assert after > before  # chosen 相对 rejected 的能量边际扩大

    def test_loss_decreases_along_updates(self):
        feats_p, feats_m = [0.8, 0.1], [0.1, 0.7]
        anchor = [0.2, 0.0]
        theta = list(anchor)
        losses = [ipo_loss(theta, anchor, feats_p, feats_m)]
        for _ in range(30):
            theta = apply_pair_update(theta, anchor, feats_p, feats_m)
            losses.append(ipo_loss(theta, anchor, feats_p, feats_m))
        assert losses[-1] < losses[0]


class TestPolicyLoop:
    @staticmethod
    def _rounds(drift: float):
        """8 策略合成候选：每策略各占一个指标角（无单一策略占优），
        每轮整体加漂移（模拟模型演化后候选分布移动）。"""
        cands, feats = [], []
        for r in range(4):
            row = []
            for j in range(8):
                o = 0.6 + 0.2 * ((j + r) % 8 == 0) + drift * r
                w = 0.10 + 0.02 * ((j + r) % 8 == 1)
                s = 0.7 + 0.05 * ((j + r) % 8 == 2)
                b = 0.88 + 0.04 * ((j + r) % 8 == 3)
                row.append({"OVRL": o, "WER": w, "SIM": s, "SBS": b})
            cands.append(row)
            feats.append([[1.0 if ((j + rr) % 8) < 4 else 0.0,
                           float((j + rr) % 8)] for rr in range(1)
                          for j in range(8)])
        return cands, feats

    def test_refresh_anchor_tracks_drift_better(self):
        """构造性演示（方向性，非论文数值）：候选分布逐轮漂移时，
        IPO 的锚点前移比 offline DPO 的冻结锚更贴合当前轮。"""
        cands, feats = self._rounds(drift=0.05)
        theta_ipo, _ = run_policy_loop(cands, feats, refresh_anchor=True)
        theta_dpo, _ = run_policy_loop(cands, feats, refresh_anchor=False)
        # 以末轮奖励为基准：学到的能量应与末轮奖励排序正相关（Spearman 手验）
        import statistics
        final_r = reward(cands[-1])
        rank = sorted(range(8), key=lambda i: final_r[i])

        def corr(theta):
            e = [energy(theta, f) for f in feats[-1]]
            erank = sorted(range(8), key=lambda i: e[i])
            # 能量低=优：两个"优序"的位置向量 Spearman
            pos_r = {idx: k for k, idx in enumerate(rank)}
            pos_e = {idx: k for k, idx in enumerate(erank)}
            n = 8
            d2 = sum((pos_r[i] - pos_e[i]) ** 2 for i in range(n))
            return 1 - 6 * d2 / (n * (n * n - 1))

        assert corr(theta_ipo) >= corr(theta_dpo)

    def test_deterministic_with_seed(self):
        cands, feats = self._rounds(drift=0.03)
        a = run_policy_loop(cands, feats, seed=9)
        b = run_policy_loop(cands, feats, seed=9)
        assert a == b

    def test_trajectory_length_matches_rounds(self):
        cands, feats = self._rounds(drift=0.0)
        _, traj = run_policy_loop(cands, feats)
        assert len(traj) == 4
        assert all(statistics_ok(t) for t in traj)


def statistics_ok(x: float) -> bool:
    return 0.0 <= x <= 1.0
