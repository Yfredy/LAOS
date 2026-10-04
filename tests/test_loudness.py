"""laos/loudness.py 测试 —— BS.1770-4 纯 stdlib 采纳（来源④，采纳书 A 项）。

锚点与 Repro-ZCode/repro/bs1770.py 相同（那里已验证过的物理事实），
本测试证明纯 stdlib 版在同一锚点上成立。
"""
import array
import json
import math
import wave

import pytest
from pathlib import Path

from laos.loudness import (
    k_weight_biquads,
    integrated_loudness,
    momentary_loudness,
    short_term_loudness,
    loudness_range,
    true_peak,
    plr,
)


def _sine(f, fs, dur, amp, phase=0.0):
    n = int(fs * dur)
    return [amp * math.sin(2 * math.pi * f * i / fs + phase) for i in range(n)]


def test_calibration_stereo_sine_minus23():
    fs = 48000
    s = _sine(997.0, fs, 8.0, 10 ** (-23 / 20))
    x = [s, s]
    assert abs(integrated_loudness(x, fs) - (-23.0)) < 0.1


def test_mono_is_3lu_below_dual_mono():
    fs = 48000
    s = _sine(997.0, fs, 8.0, 10 ** (-23 / 20))
    m = integrated_loudness([s], fs)
    st = integrated_loudness([s, s], fs)
    assert abs(m - (-26.0)) < 0.1
    assert abs((st - m) - 3.01) < 0.1


def test_idempotent_no_input_mutation():
    # 同一输入两次测量结果一致（无内部状态泄漏）
    fs = 48000
    s = _sine(997.0, fs, 4.0, 0.5)
    a = integrated_loudness([s, s], fs)
    b = integrated_loudness([s, s], fs)
    assert abs(a - b) < 1e-9


def test_gating_drops_quiet_tail():
    fs = 48000
    loud = _sine(997.0, fs, 2.0, 0.5)
    quiet = _sine(997.0, fs, 2.0, 10 ** (-80 / 20))
    x = [loud + quiet, loud + quiet]
    ref = integrated_loudness([_sine(997.0, fs, 4.0, 0.5)] * 2, fs)
    assert abs(integrated_loudness(x, fs) - ref) < 0.5


def test_momentary_short_term():
    fs = 48000
    x = [_sine(997.0, fs, 8.0, 0.5)] * 2
    m = momentary_loudness(x, fs)
    s = short_term_loudness(x, fs)
    assert len(m) > len(s) > 0
    assert abs(m[0] - (-6.0)) < 0.4      # 0.5 幅度：K(997)≈+0.69 与 -0.691 抵消


def test_lra_constant_near_zero():
    fs = 48000
    x = [_sine(997.0, fs, 20.0, 0.3)] * 2
    assert loudness_range(x, fs) < 1.0


def test_true_peak_sine():
    fs = 48000
    x = [_sine(997.0, fs, 3.0, 0.5)] * 2
    tp = true_peak(x, fs)
    assert abs(tp - (-6.02)) < 0.2       # sinc 局部重构近似（记档口径）


def test_plr_definition():
    fs = 48000
    x = [_sine(997.0, fs, 3.0, 0.5)] * 2
    assert abs(plr(x, fs) - (true_peak(x, fs) - integrated_loudness(x, fs))) < 1e-9


def test_parametric_biquads_finite_other_fs():
    b, a = k_weight_biquads(16000)
    assert len(b) == 2 and len(b[0]) == 3 and len(a) == 2 and len(a[0]) == 3


def _write_wav(path, chans, fs):
    import wave as W
    n = len(chans[0])
    with W.open(str(path), "wb") as w:
        w.setnchannels(len(chans)); w.setsampwidth(2); w.setframerate(fs)
        inter = [0] * (n * len(chans))
        for c, ch in enumerate(chans):
            for i, v in enumerate(ch):
                inter[i * len(chans) + c] = int(max(-1, min(1, v)) * 32767)
        w.writeframes(array.array("h", inter).tobytes())


def test_ear_lufs_tool_contract(tmp_path):
    import importlib.util
    import subprocess
    import sys as _sys
    fs = 48000
    s = _sine(997.0, fs, 4.0, 10 ** (-23 / 20))
    wav = tmp_path / "calib.wav"
    _write_wav(wav, [s, s], fs)
    spec = importlib.util.spec_from_file_location(
        "drv_ear_lufs", str(Path(__file__).resolve().parents[1] / "drivers" / "drv_ear.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = json.loads(mod.ear_lufs(str(wav)))
    assert abs(out["lufs"] - (-23.0)) < 0.15
    assert out["channels"] == 2 and out["sample_rate"] == fs
    assert abs(out["plr"] - (out["true_peak_dbtp"] - out["lufs"])) < 0.02
