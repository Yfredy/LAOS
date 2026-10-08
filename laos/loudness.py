"""laos.loudness —— ITU-R BS.1770-4 响度计量（纯 stdlib 采纳版）。

来源：采纳书 A 项（docs/research/2026-10-05-repro-adoption.md）。
numpy 版验证在 zones/Repro-ZCode/repro/bs1770.py（同锚点）；本模块守住 laos 核心
零依赖承诺——双二阶节手写转置直接 II，分块能量逐样本累加。

规范口径：
- K 计权 = 高频搁置（+4dB@>1.7kHz）级联 高通 38Hz；48k 用 Annex 精确系数，
  其它采样率用同模拟原型（f0/G/Q）经 RBJ cookbook 数字化。
- 积分响度：400ms 块 / 100ms 步；z = -0.691 + 10log10(Σ G_c·mean_sq)；
  绝对门 -70 LUFS、相对门（均值 -10 LU）。
- Momentary 400ms / Short-term 3s 滑窗；LRA（EBU 3342）：S 块 -70/-20 门，
  P95-P10。
- True Peak：局部峰值 sinc 重构近似（只在样本峰邻域做带限插值，避免全域
  4× FFT）——与 4× FFT 口径差 ±0.2dB 级，记档为近似。

输入：list[list[float]] 或 list[float]（单声道按 G=1.0 计一次）。
"""
from __future__ import annotations

import array
import math

_SHELF = dict(f0=1681.974450955533, gain_db=3.999843853973, q=0.7071752369554196)
_HIGHPASS = dict(f0=38.13547087602444, q=0.5003270373238773)

_ANNEX_48K_B = ((1.53512485958697, -2.69169618940638, 1.19839281085285),
                (1.0, -2.0, 1.0))
_ANNEX_48K_A = ((1.0, -1.69065929318241, 0.73248077421585),
                (1.0, -1.99004745483398, 0.99007225036621))


def _high_shelf(fs: float):
    A = 10 ** (_SHELF["gain_db"] / 40.0)
    w0 = 2 * math.pi * _SHELF["f0"] / fs
    alpha = math.sin(w0) / (2 * _SHELF["q"])
    cw, sw = math.cos(w0), math.sin(w0)
    two = 2 * math.sqrt(A) * alpha
    b = (A * ((A + 1) + (A - 1) * cw + two),
         -2 * A * ((A - 1) + (A + 1) * cw),
         A * ((A + 1) + (A - 1) * cw - two))
    a = ((A + 1) - (A - 1) * cw + two,
         2 * ((A - 1) - (A + 1) * cw),
         (A + 1) - (A - 1) * cw - two)
    return b, a


def _high_pass(fs: float):
    w0 = 2 * math.pi * _HIGHPASS["f0"] / fs
    alpha = math.sin(w0) / (2 * _HIGHPASS["q"])
    cw = math.cos(w0)
    b = ((1 + cw) / 2, -(1 + cw), (1 + cw) / 2)
    a = (1 + alpha, -2 * cw, 1 - alpha)
    return b, a


def k_weight_biquads(fs: float):
    """返回 ((b1,b2),(b1,b2) 两级, (a1,a2) 两级) 的系数元组数组口径。"""
    if abs(fs - 48000.0) < 1e-9:
        return _ANNEX_48K_B, _ANNEX_48K_A
    b1, a1 = _high_shelf(fs)
    b2, a2 = _high_pass(fs)
    return (b1, b2), (a1, a2)


class _Biquad:
    """转置直接 II，逐样本 float。"""

    __slots__ = ("b0", "b1", "b2", "a1", "a2", "z1", "z2")

    def __init__(self, b, a):
        a0 = a[0]
        self.b0, self.b1, self.b2 = b[0] / a0, b[1] / a0, b[2] / a0
        self.a1, self.a2 = a[1] / a0, a[2] / a0
        self.z1 = self.z2 = 0.0

    def __call__(self, x: float) -> float:
        y = self.b0 * x + self.z1
        self.z1 = self.b1 * x - self.a1 * y + self.z2
        self.z2 = self.b2 * x - self.a2 * y
        return y


def _as_channels(x) -> list[array.array]:
    if x and isinstance(x[0], (list, tuple, array.array)):
        chans = [array.array("d", ch) for ch in x]
    else:
        chans = [array.array("d", x)]
    return chans


def _k_weighted(chans: list[array.array], fs: float) -> list[array.array]:
    (b1, b2), (a1, a2) = k_weight_biquads(fs)
    out = []
    for ch in chans:
        f1 = _Biquad(b1, a1)
        f2 = _Biquad(b2, a2)
        out.append(array.array("d", (f2(f1(v)) for v in ch)))
    return out


def _block_loudness(chans: list[array.array], fs: float, win_s: float, hop_s: float):
    """返回 (每块 LUFS 列表, 每块 Σ G·mean_sq 列表)。"""
    n_ch = len(chans)
    n = len(chans[0])
    win = int(round(win_s * fs))
    hop = int(round(hop_s * fs))
    if n < win:
        return [], []
    loud, power = [], []
    for start in range(0, n - win + 1, hop):
        acc = 0.0
        for ch in chans:
            s = 0.0
            for i in range(start, start + win):
                v = ch[i]
                s += v * v
            acc += s / win
        power.append(acc)
        loud.append(-0.691 + 10 * math.log10(acc + 1e-300))
    return loud, power


def integrated_loudness(x, fs: float) -> float:
    chans = _k_weighted(_as_channels(x), fs)
    loud, power = _block_loudness(chans, fs, 0.4, 0.1)
    if not loud:
        return float("-inf")
    above = [p for p, l in zip(power, loud) if l > -70.0]
    if not above:
        return float("-inf")
    prelim = -0.691 + 10 * math.log10(sum(above) / len(above) + 1e-300)
    rel = prelim - 10.0
    keep = [p for p, l in zip(power, loud) if l > -70.0 and l > rel]
    if not keep:
        keep = above
    return -0.691 + 10 * math.log10(sum(keep) / len(keep) + 1e-300)


def momentary_loudness(x, fs: float) -> list[float]:
    loud, _ = _block_loudness(_k_weighted(_as_channels(x), fs), fs, 0.4, 0.1)
    return loud


def short_term_loudness(x, fs: float) -> list[float]:
    loud, _ = _block_loudness(_k_weighted(_as_channels(x), fs), fs, 3.0, 0.1)
    return loud


def loudness_range(x, fs: float) -> float:
    loud, _ = _block_loudness(_k_weighted(_as_channels(x), fs), fs, 3.0, 0.1)
    above = [l for l in loud if l > -70.0]
    if len(above) < 2:
        return 0.0
    above.sort()
    rel = above[len(above) // 2] - 20.0
    keep = [l for l in above if l > rel]
    if len(keep) < 2:
        return 0.0
    keep.sort()

    def pct(seq, q):
        k = (len(seq) - 1) * q
        lo, hi = int(k), min(int(k) + 1, len(seq) - 1)
        return seq[lo] + (seq[hi] - seq[lo]) * (k - lo)

    return pct(keep, 0.95) - pct(keep, 0.10)


def _sinc(x: float) -> float:
    if abs(x) < 1e-12:
        return 1.0
    return math.sin(math.pi * x) / (math.pi * x)


def true_peak(x, fs: float) -> float:
    """局部峰值 sinc 重构 True Peak（dBTP，近似口径 ±0.2dB）。

    只在与 |x| 局部最大值相邻 ±3 样本处以 4× 网格做带限插值——
    带限信号在峰邻域的重构与全域 4× 采样等价，计算量 O(峰数×小常数)。
    """
    chans = _as_channels(x)
    best = 0.0
    for ch in chans:
        n = len(ch)
        for i in range(1, n - 1):
            a0, a1, a2 = abs(ch[i - 1]), abs(ch[i]), abs(ch[i + 1])
            if a1 >= a0 and a1 >= a2 and a1 > 0:
                for k in (-3, -2, -1, 1, 2, 3):
                    t = k / 4.0
                    acc = 0.0
                    for j in range(i - 8, i + 9):
                        if 0 <= j < n:
                            acc += ch[j] * _sinc(t - (j - i))
                    if abs(acc) > best:
                        best = abs(acc)
    return 20 * math.log10(best + 1e-300)


def plr(x, fs: float) -> float:
    return true_peak(x, fs) - integrated_loudness(x, fs)
