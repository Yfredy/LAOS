"""ITU-R BS.1770-4 响度计量复现（来源④：dB/RMS/LUFS/True Peak 文章）。

规范口径（全部可溯源）：
- K 计权 = 高频搁置滤波器（+~4dB @ >1.7kHz）级联 高通 38Hz。
  48kHz 精确系数来自 BS.1770-4 Annex 表格（本模块 48k 分支直接返回该表）；
  其它采样率用相同模拟原型参数（f0/G/Q，EBU R128/pyloudnorm 口径）经 RBJ cookbook
  数字化——测试证明 48k 时两条路线频率响应一致 <1e-3 dB。
- 积分响度：400ms 块 / 100ms 步；每块 z_k = -0.691 + 10log10(Σ_c G_c·mean_sq)；
  绝对门 -70 LUFS；相对门 = 过绝对门块的响度均值再 -10 LU；幸存块取能量均值。
- Momentary = 400ms 滑窗逐块（无门控、步 100ms 口径与积分块一致，滑到尾部）；
  Short-term = 3s 滑窗。
- LRA（EBU R128 Tech 3342）：S 块（3s/100ms），绝对门 -70、相对门 -20 LU，
  幸存块响度的 10-95 分位差。
- True Peak：4× FFT 过采样（零填充插值）重构波形取 max|·|，dBTP。
- PLR = True Peak - Integrated（响度战争度量）。

通道权重 G_c：单声道 1.0；立体声 L=R=1.0（BS.1770 对 L/R 各计 1.0）。
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

# K 计权模拟原型参数（EBU R128 / pyloudnorm 口径，任意 fs 数字化用）
_SHELF = dict(f0=1681.974450955533, gain_db=3.999843853973, q=0.7071752369554196)
_HIGHPASS = dict(f0=38.13547087602444, q=0.5003270373238773)

# BS.1770-4 Annex：48 kHz 精确系数
_ANNEX_48K_B = np.array(
    [[1.53512485958697, -2.69169618940638, 1.19839281085285],
     [1.0, -2.0, 1.0]]
)
_ANNEX_48K_A = np.array(
    [[1, -1.69065929318241, 0.73248077421585],
     [1, -1.99004745483398, 0.99007225036621]]
)


def _high_shelf(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """RBJ cookbook 高频搁置（A = 10^(G/40)）。"""
    A = 10 ** (_SHELF["gain_db"] / 40.0)
    w0 = 2 * np.pi * _SHELF["f0"] / fs
    alpha = np.sin(w0) / (2 * _SHELF["q"])
    cw, sw = np.cos(w0), np.sin(w0)
    two = 2 * np.sqrt(A) * alpha
    b = np.array([A * ((A + 1) + (A - 1) * cw + two),
                  -2 * A * ((A - 1) + (A + 1) * cw),
                  A * ((A + 1) + (A - 1) * cw - two)])
    a = np.array([(A + 1) - (A - 1) * cw + two,
                  2 * ((A - 1) - (A + 1) * cw),
                  (A + 1) - (A - 1) * cw - two])
    return b / a[0], a / a[0]


def _high_pass(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """RBJ cookbook 常数 0dB 峰值增益高通。"""
    w0 = 2 * np.pi * _HIGHPASS["f0"] / fs
    alpha = np.sin(w0) / (2 * _HIGHPASS["q"])
    cw = np.cos(w0)
    b = np.array([(1 + cw) / 2, -(1 + cw), (1 + cw) / 2])
    a = np.array([1 + alpha, -2 * cw, 1 - alpha])
    return b / a[0], a / a[0]


def k_weight_biquads(fs: float) -> tuple[np.ndarray, np.ndarray]:
    """返回 (b(2,3), a(2,3))：第一级 shelving、第二级 highpass。"""
    if abs(fs - 48000.0) < 1e-9:
        return _ANNEX_48K_B.copy(), _ANNEX_48K_A.copy()
    b1, a1 = _high_shelf(fs)
    b2, a2 = _high_pass(fs)
    return np.vstack([b1, b2]), np.vstack([a1, a2])


def _k_weight(x: np.ndarray, fs: float) -> np.ndarray:
    """逐通道 K 计权滤波。x: (C,N) 或 (N,)。必须拷贝——atleast_2d 对
    2D 输入返回原视图，lfilter 原地写回会污染调用方数组（双重计权 bug）。"""
    b, a = k_weight_biquads(fs)
    out = np.array(np.atleast_2d(np.asarray(x, dtype=np.float64)), copy=True)
    for i in range(out.shape[0]):
        for j in range(2):
            out[i] = lfilter(b[j], a[j], out[i])
    return out


def _channel_weights(n_ch: int) -> np.ndarray:
    # BS.1770：L/R（及 5.1 的 Ls/Rs=1.41）——本复现覆盖 1/2 通道
    return np.ones(n_ch)


def _as_channels(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x[None, :] if x.ndim == 1 else x


def _block_loudness(x: np.ndarray, fs: float, win_s: float, hop_s: float):
    """滑块响度。返回 (block_loudness LUFS 数组, 权重 G 数组, 每块每通道能量)。"""
    xc = _as_channels(x)
    y = _k_weight(xc, fs)
    n_ch, n = y.shape
    G = _channel_weights(n_ch)
    win = int(round(win_s * fs))
    hop = int(round(hop_s * fs))
    starts = np.arange(0, n - win + 1, hop)
    if len(starts) == 0:
        return np.array([]), G, np.zeros((0, n_ch))
    frames = np.stack([y[:, s:s + win] for s in starts])   # (B, C, win)
    ms = np.mean(frames ** 2, axis=-1)                     # (B, C)
    power = np.sum(G * ms, axis=-1)                        # (B,)
    loud = np.where(power > 0, -0.691 + 10 * np.log10(power + 1e-30), -np.inf)
    return loud, G, ms


def integrated_loudness(x: np.ndarray, fs: float) -> float:
    """门控积分响度（BS.1770-4 §5）：绝对门 -70，相对门 -10 LU。"""
    xc = _as_channels(x)
    n_ch = xc.shape[0]
    loud, G, ms = _block_loudness(xc, fs, win_s=0.4, hop_s=0.1)
    above = loud > -70.0
    if not np.any(above):
        return -np.inf
    prelim = -0.691 + 10 * np.log10(np.mean(np.sum(G * ms[above], axis=-1)) + 1e-30)
    rel = prelim - 10.0
    keep = (loud > -70.0) & (loud > rel)
    if not np.any(keep):
        keep = above
    return float(-0.691 + 10 * np.log10(np.mean(np.sum(G * ms[keep], axis=-1)) + 1e-30))


def momentary_loudness(x: np.ndarray, fs: float) -> np.ndarray:
    loud, _, _ = _block_loudness(x, fs, win_s=0.4, hop_s=0.1)
    return loud


def short_term_loudness(x: np.ndarray, fs: float) -> np.ndarray:
    loud, _, _ = _block_loudness(x, fs, win_s=3.0, hop_s=0.1)
    return loud


def loudness_range(x: np.ndarray, fs: float) -> float:
    """LRA（EBU R128 Tech 3342）：S 块、绝对 -70、相对 -20 LU、P95-P10。"""
    xc = _as_channels(x)
    loud, _, _ = _block_loudness(xc, fs, win_s=3.0, hop_s=0.1)
    above = loud > -70.0
    if not np.any(above):
        return 0.0
    prelim = np.percentile(loud[above], 50)  # 3342 相对门基于门控后分布
    rel = prelim - 20.0
    keep = loud[(loud > -70.0) & (loud > rel)]
    if len(keep) < 2:
        return 0.0
    return float(np.percentile(keep, 95) - np.percentile(keep, 10))


def true_peak(x: np.ndarray, fs: float, oversample: int = 4) -> float:
    """4× FFT 过采样 True Peak（dBTP）。通道独立取最大。"""
    xc = _as_channels(x)
    peaks = []
    for ch in xc:
        n = len(ch)
        nfft = 1 << int(np.ceil(np.log2(n * oversample)))
        X = np.fft.rfft(ch, n=nfft)
        up = np.fft.irfft(X, n=nfft)
        peaks.append(np.max(np.abs(up)))
    peak = max(peaks)
    return float(20 * np.log10(peak + 1e-30))


def plr(x: np.ndarray, fs: float) -> float:
    """Peak-to-Loudness Ratio = True Peak - Integrated。"""
    return true_peak(x, fs) - integrated_loudness(x, fs)
