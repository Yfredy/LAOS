"""各向同性扩散场噪声（来源① §3.1 噪声增广的复现）。

论文做法（[31,32]）：单声道噪声 → STFT 域相位随机化的不相关副本 →
混合到各向同性扩散场的目标相干。扩散场双麦复相干（经典结果）：

    Γ_ij(f) = sinc(2π f d_ij / c)     （sinc = sin(x)/x，d_ij 麦间距）

实现：STFT 域逐频率 bin 生成 C 路独立复高斯，用 Γ(f) 矩阵的 Cholesky
下三角 L 混合 → ISTFT。这样得到的正是目标相干结构的多通道扩散噪声
（数学上与"相位随机化副本混合"等价：两者都合成 Γ 相干的高斯场）。
spectral_shape 可选谱包络（如伪语音谱），模拟 WHAM 的语音带能量分布。
"""
from __future__ import annotations

import numpy as np

C_SOUND = 343.0


def _stft(x: np.ndarray, nfft: int, hop: int) -> np.ndarray:
    from numpy.lib.stride_tricks import sliding_window_view
    frames = sliding_window_view(x, nfft)[::hop] * np.hanning(nfft + 1)[:nfft]
    return np.fft.rfft(frames, axis=-1)


def _istft(X: np.ndarray, n_samples: int, nfft: int, hop: int) -> np.ndarray:
    frames = np.fft.irfft(X, n=nfft, axis=-1)
    win = np.hanning(nfft + 1)[:nfft]
    out = np.zeros(n_samples + nfft)
    wsum = np.zeros(n_samples + nfft)
    inv = np.sum(win) / hop
    for t, fr in enumerate(frames):
        s = t * hop
        out[s : s + nfft] += fr * win * inv
        wsum[s : s + nfft] += win ** 2 * inv
    out = out[:n_samples]
    wsum = wsum[:n_samples]
    return out / np.maximum(wsum, 1e-9)


def diffuse_noise(n_samples: int, mic_positions: np.ndarray, fs: int,
                  rng: np.random.Generator,
                  spectral_shape: np.ndarray | None = None) -> np.ndarray:
    """Γ(f)=sinc 相干的多通道扩散噪声。返回 (C, n_samples)。"""
    M = mic_positions.shape[0]
    nfft = 512
    hop = nfft // 2
    n_frames = n_samples // hop + 1
    n_bins = nfft // 2 + 1

    d = np.linalg.norm(mic_positions[:, None, :] - mic_positions[None, :, :], axis=-1)
    freqs = np.fft.rfftfreq(nfft, 1 / fs)
    # 目标相干矩阵逐 bin（sinc 可能出负值——用实 Cholesky 需 PSD：
    # 负相干以 |Γ| 幅度近似，高频段差异记档；窗域混合后近似保持）
    gamma = np.zeros((n_bins, M, M))
    for k in range(n_bins):
        g = np.sinc(2 * freqs[k] * d / C_SOUND)
        g = np.clip(g, -0.99, 0.99)
        np.fill_diagonal(g, 1.0)
        try:
            gamma[k] = np.linalg.cholesky(g)
        except np.linalg.LinAlgError:
            # 数值边缘：对角加载
            gamma[k] = np.linalg.cholesky(g + 1e-6 * np.eye(M))

    out = np.zeros((M, n_samples))
    # 逐通道独立生成再逐 bin 混合：直接生成白 STFT 场 (M, T, F)
    white = (rng.standard_normal((M, n_frames, n_bins))
             + 1j * rng.standard_normal((M, n_frames, n_bins))) / np.sqrt(2)
    if spectral_shape is not None:
        shape = np.asarray(spectral_shape)
        assert len(shape) == n_bins, f"spectral_shape 需 {n_bins} bin"
        white = white * shape[None, None, :]
    mixed = np.einsum("fij,jtf->itf", gamma, white)   # 逐 bin：L(f)·白场
    for m in range(M):
        out[m] = _istft(mixed[m], n_samples, nfft, hop)
    # 补齐余量样本
    if out.shape[1] < n_samples:
        out = np.pad(out, ((0, 0), (0, n_samples - out.shape[1])))
    return out


def measure_coherence(x: np.ndarray, nfft: int = 1024) -> np.ndarray:
    """测量多通道 STFT 相干矩阵 (C, C, F)（验证用）。"""
    C = x.shape[0]
    X = np.stack([_stft(x[m], nfft, nfft // 2) for m in range(C)])   # (C, T, F)
    P = np.einsum("ctf,dtf->cdtf", X, np.conj(X))
    pxx = np.real(np.diagonal(P, axis1=0, axis2=1))                  # (C, C, F) 取对角
    auto = np.stack([np.real(np.mean(np.abs(X[m]) ** 2, axis=0)) for m in range(C)])
    coh = np.zeros((C, C, X.shape[2]))
    for i in range(C):
        for j in range(C):
            cross = np.mean(P[i, j], axis=0)
            coh[i, j] = np.abs(cross) / np.sqrt(auto[i] * auto[j] + 1e-30)
    return coh
