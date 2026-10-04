"""STFT 相位特征测试（来源① §2：Feature Extraction）。

论文：Hann 窗 4ms/步 2ms、相位取 sin/cos、堆叠 2C×T×F（F=128）。
16kHz 下 4ms=64 样本窗、2ms=32 步、nfft=256 零填充 → 129 bin 丢 DC 取 128
（论文 F=128 的工程决定，docstring 记档）。
"""
import numpy as np

from repro.sho.features import stft_phase_features, angular_mae

FS = 16000


def test_feature_shape_2CxTxF128():
    x = np.random.default_rng(0).standard_normal((6, 16000)) * 0.1
    f = stft_phase_features(x, FS)
    assert f.shape[0] == 12 and f.shape[2] == 128
    assert f.shape[1] == (16000 - 64) // 32 + 1
    assert np.all(np.isfinite(f))


def test_known_delay_linear_phase():
    n = np.arange(16000) / FS
    base = np.sin(2 * np.pi * 500 * n)
    delayed = np.concatenate([np.zeros(4), base[:-4]])
    x = np.stack([base, delayed])
    f = stft_phase_features(x, FS)
    k = np.arange(1, 129)                       # 丢 DC 后 bin 1..128（nfft=256）
    expected = -2 * np.pi * k * 4 / 256
    dphi = (np.arctan2(f[2, 100], f[3, 100])
            - np.arctan2(f[0, 100], f[1, 100]))
    sig = 7                                     # 500Hz=原 bin 8；特征数组下标=bin-1
    err = np.abs(np.angle(np.exp(1j * (dphi[sig - 1:sig + 2]
                                       - expected[sig - 1:sig + 2]))))
    assert np.mean(err) < 0.1                   # 信号 bin 及泄漏邻 bin 遵循延迟律


def test_sin_cos_unit_norm():
    x = np.random.default_rng(2).standard_normal((2, 4096)) * 0.2
    f = stft_phase_features(x, FS)
    # 同通道 sin/cos 成对：sin²+cos²=1
    norms = f[0] ** 2 + f[1] ** 2
    assert np.allclose(norms, 1.0, atol=1e-9)


def test_angular_mae_wraparound():
    assert angular_mae([359.0], [1.0]) == 2.0
    assert angular_mae([90.0], [90.0]) == 0.0
    t = np.full(2000, 0.0)
    p = np.random.default_rng(1).uniform(0, 360, 2000)
    assert 80 < angular_mae(t, p) < 100         # 随机预测 ≈ 90°
