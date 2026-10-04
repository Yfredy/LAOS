"""BS.1770-4 响度计量复现测试（来源④：dB/RMS/LUFS/True Peak 文章）。

校准锚点：997 Hz 正弦 @ -23 dBFS 立体声 → -23.0 LUFS（EBU R128 校准点）。
48k Annex 精确系数来自 ITU-R BS.1770-4 原文表格。
"""
import numpy as np
import pytest

from repro.bs1770 import (
    k_weight_biquads,
    integrated_loudness,
    momentary_loudness,
    short_term_loudness,
    loudness_range,
    true_peak,
    plr,
)


def _sine(f, fs, dur, amp):
    t = np.arange(int(fs * dur)) / fs
    return amp * np.sin(2 * np.pi * f * t)


def test_calibration_stereo_sine_minus23():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 10.0, 10 ** (-23 / 20))] * 2)
    assert abs(integrated_loudness(x, fs) - (-23.0)) < 0.1


def test_mono_is_3lu_below_dual_mono():
    """BS.1770：单通道 G=1.0 只计一次 → 比 dual-mono 立体声低 3.01 LU。
    -23 dBFS 峰值正弦单声道 ≈ -26.0 LUFS。"""
    fs = 48000
    x = _sine(997.0, fs, 10.0, 10 ** (-23 / 20))
    assert abs(integrated_loudness(x, fs) - (-26.0)) < 0.1
    # 幂等性：同一数组重复测量结果不变（防原地污染回归）
    assert abs(integrated_loudness(x, fs) - (-26.0)) < 0.1


def test_stereo_identical_plus3_over_mono():
    fs = 48000
    s = _sine(997.0, fs, 10.0, 10 ** (-23 / 20))
    m = integrated_loudness(s, fs)
    st = integrated_loudness(np.stack([s, s]), fs)
    assert abs((st - m) - 3.01) < 0.1


def test_gating_drops_quiet_tail():
    fs = 48000
    loud = _sine(997.0, fs, 2.0, 0.5)
    quiet = _sine(997.0, fs, 2.0, 10 ** (-80 / 20))
    x = np.stack([np.concatenate([loud, quiet])] * 2)
    ref = integrated_loudness(np.stack([_sine(997.0, fs, 4.0, 0.5)] * 2), fs)
    assert abs(integrated_loudness(x, fs) - ref) < 0.5


def test_parametric_biquads_match_annex_at_48k():
    fs = 48000
    b, a = k_weight_biquads(fs)
    annex_b = np.array(
        [[1.53512485958697, -2.69169618940638, 1.19839281085285],
         [1.0, -2.0, 1.0]]
    )
    annex_a = np.array(
        [[1, -1.69065929318241, 0.73248077421585],
         [1, -1.99004745483398, 0.99007225036621]]
    )
    w = np.linspace(1, 24000, 2000)
    z = np.exp(1j * 2 * np.pi * w / fs)
    for i in range(2):
        H_new = np.polyval(b[i], 1 / z) / np.polyval(a[i], 1 / z)
        H_ref = np.polyval(annex_b[i], 1 / z) / np.polyval(annex_a[i], 1 / z)
        d = (20 * np.log10(np.abs(H_new) + 1e-30)
             - 20 * np.log10(np.abs(H_ref) + 1e-30))
        assert np.max(np.abs(d)) < 1e-3


def test_biquads_work_at_other_fs():
    b, a = k_weight_biquads(16000)
    assert b.shape == (2, 3) and a.shape == (2, 3)
    assert np.all(np.isfinite(b)) and np.all(np.isfinite(a))


def test_momentary_short_term_shapes_and_values():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 8.0, 0.5)] * 2)
    m, s = momentary_loudness(x, fs), short_term_loudness(x, fs)
    assert len(m) > len(s) > 0
    # 0.5 幅度正弦：K(997)≈+0.691 与 -0.691 抵消，双通道功率 2×(a²/2)=a² → M0 ≈ 20log10(0.5)
    assert abs(m[0] - (-6.0)) < 0.3
    assert abs(s[0] - m[0]) < 0.2


def test_lra_constant_signal_near_zero():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 20.0, 0.3)] * 2)
    assert loudness_range(x, fs) < 1.0


def test_lra_two_level_signal():
    fs = 48000
    loud = _sine(997.0, fs, 10.0, 0.5)
    soft = _sine(997.0, fs, 10.0, 0.05)  # 差 ~20 dB
    x = np.stack([np.concatenate([loud, soft])] * 2)
    lra = loudness_range(x, fs)
    assert 5.0 < lra < 25.0


def test_true_peak_sine_and_plr():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 5.0, 0.5)] * 2)
    tp = true_peak(x, fs)
    assert abs(tp - (-6.02)) < 0.15
    assert abs(plr(x, fs) - (tp - integrated_loudness(x, fs))) < 1e-9


def test_true_peak_catches_intersample_peak():
    fs = 48000
    # 半采样偏相正弦：样本峰低估真实峰
    t = np.arange(int(fs * 2)) / fs
    x = 0.99 * np.sin(2 * np.pi * 997.0 * t + np.pi / 3)
    tp = true_peak(x, fs)
    sp = 20 * np.log10(np.max(np.abs(x)) + 1e-30)
    assert tp >= sp - 0.01  # 过采样峰值 ≥ 样本峰值
