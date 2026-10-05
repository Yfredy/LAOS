"""laos.binaural —— 双耳空间线索：逐频点 ILD / IPD（纯 stdlib）。

来源：SAIL（arXiv 2609.34347）用双耳相位差作为与声学流（mel）解耦的**空间
流**特征，证明保持声学-空间结构是多声源理解的关键。本模块是其最小内核版：
Goertzel 算法（Wolfgang Goertzel, 1958）在指定频点上求 DFT 系数，由此得
强度差与相位差——不需要 FFT、不需要 numpy。

符号约定：
- ILD = 20·log10(|L(f)|/|R(f)|)，正值 = 左耳更响（声源偏左）；
- IPD = angle(L(f)) − angle(R(f))，wrap 到 (−π, π]，正值 = 左耳超前。

与 laos.micgeom 的分工：micgeom 是**阵列几何先验**（声源在哪，坐标编码），
binaural 是**信号侧线索**（双通道录音里实际测到的差分）——SAIL 的两流对应
这两类输入。输入为 PCM16 整数序列（与 laos.vad 同约定；比值/相位差对
整数缩放不敏感）。

脏数据策略：某频点两通道皆近零（无声）→ ILD 记 0.0 不记 NaN；单边有声 →
±120 dB 封顶。Goertzel 终值公式：X = e^{−iω(N−1)}·(s[N−1] − e^{−iω}·s[N−2])
（返回**精确** DFT 系数 Σx[n]e^{−iωn}，与直接求和一致；经典整数 bin 公式
只是相位旋转了 ω(N−1)，跨通道求差时两者等价）。
"""
from __future__ import annotations

import cmath
import math
from typing import Sequence

__all__ = ["goertzel", "ild_db", "ipd_rad", "binaural_features"]

# 默认频点：语音频带五点倍频程（与 SAIL 空间流的低频相位差用途对齐）
DEFAULT_FREQS = (250.0, 500.0, 1000.0, 2000.0, 4000.0)

_EPS = 1e-9      # |X| 低于此视为该频点无声
_CAP_DB = 120.0  # 单边有声时的 ILD 封顶


def goertzel(samples: Sequence[int], sr: int, f0: float) -> complex:
    """单频点 DFT 系数 Σ x[n]·e^{−iωn}，ω = 2πf0/sr（任意非整数 bin 亦可）。

    纯 Python 两系数递推，48k 采样 10ms 窗（480 点）单频点 <0.5ms；
    五频点 × 100ms 帧的实时预算充裕。
    """
    w = 2.0 * math.pi * f0 / sr
    coeff = 2.0 * math.cos(w)
    s1 = 0.0
    s2 = 0.0
    for x in samples:
        s1, s2 = float(x) + coeff * s1 - s2, s1
    if not samples:
        return 0j
    rot = cmath.exp(-1j * w * (len(samples) - 1))
    return rot * (s1 - cmath.exp(-1j * w) * s2)


def ild_db(left: Sequence[int], right: Sequence[int], sr: int,
           freqs: Sequence[float] = DEFAULT_FREQS) -> list[float]:
    """逐频点双耳强度差（dB，正 = 左响）。两通道皆无声 → 0.0。"""
    out: list[float] = []
    for f in freqs:
        gl = abs(goertzel(left, sr, f))
        gr = abs(goertzel(right, sr, f))
        if gl < _EPS and gr < _EPS:
            out.append(0.0)
        elif gr < _EPS:
            out.append(_CAP_DB)
        elif gl < _EPS:
            out.append(-_CAP_DB)
        else:
            out.append(20.0 * math.log10(gl / gr))
    return out


def ipd_rad(left: Sequence[int], right: Sequence[int], sr: int,
            freqs: Sequence[float] = DEFAULT_FREQS) -> list[float]:
    """逐频点双耳相位差（rad ∈ (−π, π]，正 = 左超前）。"""
    out: list[float] = []
    for f in freqs:
        gl = goertzel(left, sr, f)
        gr = goertzel(right, sr, f)
        diff = cmath.phase(gl) - cmath.phase(gr)
        out.append(math.atan2(math.sin(diff), math.cos(diff)))  # wrap 到 (−π, π]
    return out


def binaural_features(left: Sequence[int], right: Sequence[int], sr: int,
                      freqs: Sequence[float] = DEFAULT_FREQS) -> dict:
    """SAIL 空间流的最小特征包：{"ild_db": [...], "ipd_rad": [...]}。"""
    return {"ild_db": ild_db(left, right, sr, freqs),
            "ipd_rad": ipd_rad(left, right, sr, freqs)}
