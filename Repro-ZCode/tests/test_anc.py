"""FxLMS 主动降噪复现测试（来源③：车载 ANC 厂商集锦）。

机制：参考信号 x（发动机阶次/RNC 加速度计）经自适应 FIR W 产生反相声波，
经次级通路 S（扬声器→误差麦克风）叠加到初级噪声 d（P∗x）上；
LMS 更新用"过滤后"的参考 Ŝ∗x（FxLMS 核心思想，补偿 S 的相位滞后）。
厂商数字（Bose 3-6dB/歌尔 11.2dB(A) 等）是营销口径，只作锚点，不作断言。
"""
import numpy as np

from repro.anc import (
    engine_harmonics,
    fir_apply,
    fxlms,
    identify_path,
    fxlms_mc,
)


def _att_db(e, d):
    return 10 * np.log10(np.mean(d ** 2) / np.mean(e ** 2) + 1e-30)


def test_engine_harmonics_orders_and_f0():
    rng = np.random.default_rng(7)
    fs, rpm = 8000, 2400.0                      # f0 = 40 Hz
    x = engine_harmonics(rpm, [2, 3], fs, 2.0, 1.0, rng)
    X = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    for k in (80.0, 120.0):                     # 阶次 2/3 → 80/120 Hz
        assert X[np.argmin(np.abs(f - k))] > 0.5 * np.max(X)


def test_engine_harmonics_seedable():
    a = engine_harmonics(1800.0, [2], 8000, 1.0, 1.0, np.random.default_rng(3))
    b = engine_harmonics(1800.0, [2], 8000, 1.0, 1.0, np.random.default_rng(3))
    assert np.array_equal(a, b)


def test_fir_apply_delay_shape():
    x = np.array([1.0, 0, 0, 0])
    assert np.allclose(fir_apply(x, np.array([0.5, 0.25])), np.array([0.5, 0.25, 0, 0]))


def test_fxlms_tonal_attenuation_gt20db():
    rng = np.random.default_rng(3)
    fs = 8000
    x = engine_harmonics(2400.0, [2], fs, 3.0, 1.0, rng)
    p_ir, s_ir = np.array([0.05, 0.9, 0.15]), np.array([0.6, 0.35, 0.08])
    d = fir_apply(x, p_ir)
    e, w = fxlms(x, p_ir, s_ir, mu=0.03, L=24, s_hat=s_ir)
    tail = slice(int(1.5 * fs), None)             # 收敛后
    assert _att_db(e[tail], d[tail]) > 20.0
    assert len(w) == 24


def test_fxlms_broadband_rnc_style_attenuates():
    """RNC 形态：宽带参考（加速度计信号近似）。"""
    rng = np.random.default_rng(21)
    fs = 8000
    x = rng.standard_normal(int(3 * fs)) * 0.5
    x = np.convolve(x, np.array([1.0, 0.6, 0.3]), "same")   # 带点色
    p_ir, s_ir = np.array([0.1, 0.85, 0.2]), np.array([0.55, 0.3, 0.12])
    d = fir_apply(x, p_ir)
    e, _ = fxlms(x, p_ir, s_ir, mu=0.005, L=32, s_hat=s_ir)
    assert _att_db(e[int(2 * fs):], d[int(2 * fs):]) > 6.0


def test_secondary_path_mismatch_still_converges():
    rng = np.random.default_rng(5)
    fs = 8000
    x = engine_harmonics(1800.0, [2, 4], fs, 3.0, 1.0, rng)
    p_ir, s_ir = np.array([0.1, 0.8, 0.2]), np.array([0.5, 0.4, 0.1])
    s_hat = np.array([0.45, 0.4, 0.12])           # 估计有偏
    d = fir_apply(x, p_ir)
    e, _ = fxlms(x, p_ir, s_ir, mu=0.02, L=32, s_hat=s_hat)
    assert _att_db(e[int(2 * fs):], d[int(2 * fs):]) > 10.0


def test_identify_path_recovers_fir():
    rng = np.random.default_rng(11)
    fs = 8000
    probe = rng.standard_normal(4000) * 0.1
    s_ir = np.array([0.5, 0.35, 0.1, 0.05])
    y = fir_apply(probe, s_ir)
    est = identify_path(probe, y, L=4)
    assert np.allclose(est, s_ir, atol=1e-6)


def test_fxlms_mc_2x2_both_error_mics():
    rng = np.random.default_rng(13)
    fs = 8000
    x = engine_harmonics(2400.0, [2], fs, 3.0, 1.0, rng)
    P = np.array([[0.05, 0.9, 0.15], [0.1, 0.8, 0.2]])      # 2 初级通路
    S = np.array([[[0.6, 0.35, 0.08], [0.3, 0.5, 0.1]],     # S[m][k]: 误差m←扬声k
                  [[0.4, 0.3, 0.2], [0.55, 0.3, 0.05]]])
    E, W = fxlms_mc(x, P, S, mu=0.002, L=16)
    D = np.stack([fir_apply(x, p) for p in P])
    for m in range(2):
        assert _att_db(E[m][int(1.5 * fs):], D[m][int(1.5 * fs):]) > 10.0
    assert W.shape == (2, 16)
