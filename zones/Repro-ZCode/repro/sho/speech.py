"""伪语音合成 + cardioid 族指向性（来源① §3.1 的自包含替代）。

论文：22 条实测 VDP（[24,25,26]）× VCTK 44k 录音。
本复现（环境红线：不下载语料）：
- 伪语音 = f0 轮廓（120-220Hz 随机游走）+ 15 次谐波（1/k 滚降）
  + 3 个共振峰带通（scipy）+ 2-5Hz 音节包络 + 静音段
- 指向性 = cardioid 族 D(θ) = a + b·cos(θ)，(a,b) 每语句采样、a+b=1
  （前向无衰减、后向 a；实测 VDP 的简化替代，偏差记档）
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, lfilter

from repro.sho.ism import sample_room


def synth_speech(dur_s: float, fs: int, rng: np.random.Generator) -> np.ndarray:
    """自包含伪语音。"""
    n = int(fs * dur_s)
    t = np.arange(n) / fs
    # f0 随机游走 120-220 Hz
    steps = rng.normal(0, 8.0, n)
    f0 = 170.0 + np.cumsum(steps)
    f0 = np.clip(f0, 120.0, 220.0)
    phase = 2 * np.pi * np.cumsum(f0) / fs
    # 谐波源
    src = np.zeros(n)
    for k in range(1, 16):
        src += (1.0 / k) * np.sin(k * phase + rng.uniform(0, 2 * np.pi))
    # 共振峰：三个带通（F1~500、F2~1500、F3~2500 附近随机）
    out = np.zeros(n)
    for fc in (rng.uniform(400, 700), rng.uniform(1200, 1800),
               rng.uniform(2200, 2800)):
        b, a = butter(2, [max(fc - 250, 50) / (fs / 2), min(fc + 250, fs / 2 - 1) / (fs / 2)],
                      btype="band")
        out += lfilter(b, a, src)
    # 音节包络 2-5Hz + 语句级静音段
    syll = 0.5 * (1 + np.sin(2 * np.pi * rng.uniform(2, 5) * t
                             + rng.uniform(0, 2 * np.pi)))
    gate = np.ones(n)
    n_pause = int(rng.uniform(0.1, 0.25) * n)
    gate[:n_pause] = 0                          # 句首静音（VAD 裁剪对象）
    x = out * syll * gate
    peak = np.max(np.abs(x))
    if peak > 0:
        x = x / peak * 10 ** (-6 / 20)          # 峰值 -6 dBFS
    return x.astype(np.float64)


def directivity_gain(theta_rad: float, a: float, b: float) -> float:
    """cardioid 族指向性增益：θ=朝向偏角，D = a + b·cos(θ)。"""
    return a + b * np.cos(theta_rad)


def oriented_room_dict(rng: np.random.Generator) -> dict:
    """sample_room + cardioid VDP 参数（替代论文 22 条实测 VDP）。"""
    rd = sample_room(rng)
    a = rng.uniform(0.3, 0.7)
    rd["directivity"] = {"a": a, "b": 1.0 - a}
    return rd
