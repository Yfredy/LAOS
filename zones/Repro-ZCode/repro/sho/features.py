"""STFT 相位特征 + 环形 MAE（来源① §2）。

论文 Feature Extraction：Hann 窗 4 ms、步 2 ms，取相位并以 sin/cos 表示
（避 ±π 断续），按通道维堆叠成 2C×T×F，F=128。
工程决定：fs=16k 时 4ms=64 样本、nfft=256 零填充 → 129 个 rfft bin，
丢 DC bin 后取 128（论文口径 F=128 的对齐方式）。
通道交错顺序：[ch0_sin, ch0_cos, ch1_sin, ch1_cos, ...]。
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

WIN = 64          # 4 ms @16k
HOP = 32          # 2 ms @16k
NFFT = 256        # 零填充 → 129 bin → 丢 DC → F=128


def stft_phase_features(x: np.ndarray, fs: int) -> np.ndarray:
    """多通道音频 → (2C, T, 128) sin/cos 相位特征。

    仅按论文参数（4ms/2ms/Hann）实现；fs 非 16k 时按比例取整窗口。
    """
    x = np.atleast_2d(np.asarray(x, dtype=np.float64))
    C, N = x.shape
    win = int(0.004 * fs)
    hop = max(1, int(0.002 * fs))
    nfft = 4 * win
    win_f = np.hanning(win + 1)[:win]

    frames = sliding_window_view(x, win, axis=1)[:, ::hop]      # (C, T, win)
    frames = frames * win_f[None, None, :]
    spec = np.fft.rfft(frames, n=nfft, axis=-1)                  # (C, T, nfft/2+1)
    phase = np.angle(spec[:, :, 1:nfft // 2 + 1])                # 丢 DC → 128 bin
    s = np.sin(phase)
    c = np.cos(phase)
    feats = np.empty((2 * C, phase.shape[1], phase.shape[2]))
    feats[0::2] = s
    feats[1::2] = c
    return feats


def angular_mae(theta_true_deg, theta_pred_deg) -> float:
    """环形平均角误差（论文 §3 公式）：min(|Δ|, 360-|Δ|) 的均值。"""
    t = np.asarray(theta_true_deg, dtype=float)
    p = np.asarray(theta_pred_deg, dtype=float)
    d = np.abs(t - p) % 360.0
    return float(np.mean(np.minimum(d, 360.0 - d)))
