"""伪语音 + cardioid 指向性声源测试（来源① §3.1 的替代实现）。

论文用 22 条实测 VDP + VCTK；本复现用 cardioid 族 a+b·cosθ + 自造伪语音
（f0 轮廓 + 谐波 + 共振峰 + 音节包络）——偏差记入复现报告。
"""
import numpy as np

from repro.sho.speech import synth_speech, directivity_gain, oriented_room_dict

FS = 16000


def test_speech_seedable_and_shape():
    s1 = synth_speech(2.0, FS, np.random.default_rng(9))
    s2 = synth_speech(2.0, FS, np.random.default_rng(9))
    assert s1.shape == (32000,) and np.array_equal(s1, s2)


def test_speech_peak_normalized():
    s = synth_speech(2.0, FS, np.random.default_rng(1))
    assert np.max(np.abs(s)) <= 10 ** (-6 / 20) + 1e-9
    assert np.max(np.abs(s)) > 0.2  # 不是近静音


def test_speech_has_harmonic_structure():
    s = synth_speech(3.0, FS, np.random.default_rng(2))
    S = np.abs(np.fft.rfft(s))
    f = np.fft.rfftfreq(len(s), 1 / FS)
    centroid = np.sum(f * S) / np.sum(S)
    assert centroid < FS / 4                      # 能量集中低频（谐波结构）
    # f0 带内能量显著高于 4-8kHz 带内
    lo = S[(f > 100) & (f < 800)].mean()
    hi = S[(f > 4000) & (f < 8000)].mean()
    assert lo > 5 * hi


def test_directivity_front_stronger_than_back():
    assert directivity_gain(0.0, 0.5, 0.5) == 1.0
    assert directivity_gain(np.pi, 0.5, 0.5) == 0.0
    assert directivity_gain(np.pi, 0.7, 0.3) < directivity_gain(2.5, 0.7, 0.3)


def test_oriented_room_dict_has_vdp():
    rd = oriented_room_dict(np.random.default_rng(2))
    assert {"a", "b"} <= set(rd["directivity"].keys())
    assert 0.3 <= rd["directivity"]["a"] <= 0.7
    assert rd["directivity"]["a"] + rd["directivity"]["b"] == 1.0
