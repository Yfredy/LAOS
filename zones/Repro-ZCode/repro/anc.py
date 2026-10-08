"""FxLMS 主动降噪复现（来源③：车载 ANC 厂商集锦）。

车载 ANC 机制光谱：EOC（发动机阶次，RPM/CAN 参考，确定性前馈）→
RNC（路噪，加速度计参考，宽带前馈）→ ESS/AVES（声浪合成）。
共同算法底座是 FxLMS（filtered-x LMS）：

    d(n) = (P ∗ x)(n)                      初级通路（噪声源→误差麦克风）
    y(n) = (W ∗ x)(n)，u 经 S 传播          次级通路（扬声器→误差麦克风）
    e(n) = d(n) + (S ∗ y)(n)                误差麦克风（反相叠加）
    W(n+1) = W(n) - mu · e(n) · (Ŝ ∗ x)(n)  过滤后参考更新（负号=反相抵消）

符号约定：本实现"反相声波"由更新式的负号承载，y 本身不取反。
多通道版为 2 参考×2 误差点矩阵形态（车厂多扬声器布局的最小情形）。
"""
from __future__ import annotations

import numpy as np


def engine_harmonics(rpm: float, orders: list[float], fs: float, dur_s: float,
                     amp: float, rng: np.random.Generator) -> np.ndarray:
    """发动机阶次信号：f_k = rpm/60 × order，幅度按 1/order 滚降（EOC 参考信号）。"""
    f0 = rpm / 60.0
    n = int(fs * dur_s)
    t = np.arange(n) / fs
    x = np.zeros(n)
    for order in orders:
        ph = rng.uniform(0, 2 * np.pi)
        x += (amp / order) * np.sin(2 * np.pi * f0 * order * t + ph)
    return x


def fir_apply(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """FIR 滤波（full 卷积截到 len(x)）。"""
    return np.convolve(x, h)[: len(x)]


def _delay_line_matrix(x: np.ndarray, L: int) -> np.ndarray:
    """(N, L) 矩阵：第 n 行 = [x(n), x(n-1), ..., x(n-L+1)]（不足补零）。"""
    N = len(x)
    X = np.zeros((N, L))
    for k in range(L):
        X[k:, k] = x[: N - k]
    return X


def _recent_dot(y_hist_k: np.ndarray, s: np.ndarray, n: int) -> float:
    """(s ∗ y_k)(n) = Σ_j s[j]·y(n-j)：最近样本倒序后与 s 点积。"""
    ns = len(s)
    lo = max(0, n - ns + 1)
    seg_rev = y_hist_k[lo : n + 1][::-1]         # [y(n), y(n-1), ...]
    return float(np.dot(seg_rev, s[: len(seg_rev)]))


def fxlms(x: np.ndarray, p_ir: np.ndarray, s_ir: np.ndarray,
          mu: float, L: int, s_hat: np.ndarray | None = None,
          w0: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """单通道 FxLMS。返回 (e, w)。

    p_ir: 初级通路 FIR；s_ir: 真实次级通路；s_hat: 次级通路估计（默认=s_ir）。
    """
    if s_hat is None:
        s_hat = s_ir
    N = len(x)
    w = np.zeros(L) if w0 is None else w0.astype(float).copy()
    Xd = _delay_line_matrix(x, L)                # 参考延迟线
    xf = fir_apply(x, s_hat)                     # 过滤后参考 Ŝ∗x
    XF = _delay_line_matrix(xf, L)
    d = fir_apply(x, p_ir)                       # 初级噪声
    # 扬声器输出 y(n) = w(n)·x_delay(n)，经 s_ir 到误差点
    y_full = np.zeros(N + len(s_ir) - 1)
    e = np.zeros(N)
    for n in range(N):
        y = float(w @ Xd[n])
        y_full[n : n + len(s_ir)] += y * s_ir
        e[n] = d[n] + y_full[n]
        w = w - mu * e[n] * XF[n]
    return e, w


def identify_path(probe: np.ndarray, y: np.ndarray, L: int) -> np.ndarray:
    """最小二乘 FIR 辨识：y ≈ probe ∗ h → h = (XᵀX)⁻¹Xᵀy（次级通路估计 Ŝ）。"""
    X = _delay_line_matrix(probe, L)
    h, *_ = np.linalg.lstsq(X, y, rcond=None)
    return h


def fxlms_mc(x: np.ndarray, P_ir: np.ndarray, S_ir: np.ndarray,
             mu: float, L: int, s_hat: np.ndarray | None = None
             ) -> tuple[np.ndarray, np.ndarray]:
    """2×2 多通道 FxLMS：单参考 x、K=2 扬声器、M=2 误差点。

    P_ir: (M, len_p) 初级通路；S_ir: (M, K, len_s) 误差m←扬声k 通路。
    标准耦合形式：e_m(n) = d_m(n) + Σ_k (s_mk ∗ y_k)(n)；
    更新 w_k ← w_k - mu·Σ_m e_m(n)·(ŝ_mk ∗ x)(n-delayline)。
    返回 (E(M,N), W(K,L))。
    """
    if s_hat is None:
        s_hat = S_ir
    M, K = S_ir.shape[0], S_ir.shape[1]
    N = len(x)
    ns = S_ir.shape[2]
    W = np.zeros((K, L))
    Xd = _delay_line_matrix(x, L)
    # XF[m][k]: 误差 m、扬声 k 的过滤后参考延迟线 (N, L)
    XF = [[_delay_line_matrix(fir_apply(x, s_hat[m, k]), L) for k in range(K)]
          for m in range(M)]
    D = np.stack([fir_apply(x, p) for p in P_ir])
    E = np.zeros((M, N))
    y_hist = np.zeros((K, N))                    # 各扬声器输出历史
    for n in range(N):
        # 扬声器输出与到各误差点的传播
        yk = np.array([float(W[k] @ Xd[n]) for k in range(K)])
        for m in range(M):
            acc = D[m][n]
            for k in range(K):
                # s_mk ∗ y_k 在 n 处的值：需要 y_k 的最近 ns 个样本
                acc += _recent_dot(y_hist[k], S_ir[m, k], n)
            E[m, n] = acc
        y_hist[:, n] = yk
        for k in range(K):
            grad = np.zeros(L)
            for m in range(M):
                grad += E[m, n] * XF[m][k][n]
            W[k] = W[k] - mu * grad
    return E, W
