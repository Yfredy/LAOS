"""各向同性扩散场噪声测试（来源① §3.1 噪声增广）。

论文：WHAM 单声道 → 相位随机化不相关副本 → 混合到各向同性扩散场目标
相干（[31,32]）。扩散场双麦相干模型：Γ(f) = sinc(2πf·d/c)。
"""
import numpy as np

from repro.sho.noise import diffuse_noise, measure_coherence
from repro.sho.ism import circular_array

FS = 16000


def test_shape_and_finite():
    mics = circular_array(6, 0.045)
    x = diffuse_noise(4 * FS, mics, FS, np.random.default_rng(3))
    assert x.shape == (6, 4 * FS)
    assert np.all(np.isfinite(x))


def test_seedable():
    mics = circular_array(4, 0.045)
    a = diffuse_noise(2 * FS, mics, FS, np.random.default_rng(5))
    b = diffuse_noise(2 * FS, mics, FS, np.random.default_rng(5))
    assert np.array_equal(a, b)


def test_coherence_matches_sinc():
    mics = circular_array(6, 0.045)
    x = diffuse_noise(8 * FS, mics, FS, np.random.default_rng(3))
    C = measure_coherence(x)
    f = np.fft.rfftfreq(1024, 1 / FS)
    d01 = float(np.linalg.norm(mics[0] - mics[1]))
    c = 343.0
    idx = (f > 200) & (f < 3000)                # sinc 模型有效的中频带
    est = np.abs(C[0, 1, idx])
    tgt = np.abs(np.sinc(2 * f[idx] * d01 / c))
    assert np.mean(np.abs(est - tgt)) < 0.15


def test_coherence_unity_at_dc_and_falling():
    mics = circular_array(2, 0.045)
    x = diffuse_noise(8 * FS, mics, FS, np.random.default_rng(4))
    C = measure_coherence(x)
    f = np.fft.rfftfreq(1024, 1 / FS)
    assert C[0, 1, 0] > 0.95
    assert C[0, 1, np.argmin(np.abs(f - 4000))] < C[0, 1, np.argmin(np.abs(f - 500))]


def test_spectral_shape_option():
    mics = circular_array(2, 0.045)
    shape = np.exp(-np.linspace(0, 4, 257))     # 低频加重包络（257=生成器 nfft 512）
    x = diffuse_noise(4 * FS, mics, FS, np.random.default_rng(6),
                      spectral_shape=shape)
    a = np.abs(np.fft.rfft(x[0]))
    half = len(a) // 2
    assert np.mean(a[:half]) > np.mean(a[half:])
