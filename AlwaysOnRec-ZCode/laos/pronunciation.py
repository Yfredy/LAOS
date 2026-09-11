"""pronunciation —— 发音评估（零依赖韵律档 + 可插拔 GOPT 后端）。

调研依据（docs/research/2026-09-12-speech-model-frontiers.md §5.1）：
发音评估的四维口径（准确/流利/完整/韵律，GOPT + speechocean762）是语言学习
功能的行业标准。本模块零依赖档只覆盖**韵律两维**（流利度/节奏）——它们从
能量包络即可算；音素"准确度/完整度"必须对照期望文本，需 GOPT 类后端
（LAOS_PRON_BACKEND 可插拔），缺失时如实返回 None 而不是编一个分数。

红线：分数只用于"与自己比"的纵向差分（练习曲线），不做绝对水平判定。
"""

from __future__ import annotations

from typing import Callable, Sequence

from .kws import envelope
from .vad import split_segments

Backend = Callable[[Sequence[int], int, str | None], dict]


def _burst_peaks(env: list[float], *, height: float = 0.4, min_gap_ms: int = 120,
                 frame_ms: int = 10) -> list[int]:
    """包络峰（音节近似）的帧索引。"""
    peaks: list[int] = []
    last = -min_gap_ms // frame_ms - 1
    for i, v in enumerate(env):
        if v >= height and i - last >= min_gap_ms // frame_ms:
            peaks.append(i)
            last = i
    return peaks


def prosodic_features(samples: Sequence[int], sr: int) -> dict:
    """零依赖韵律特征：语速（音节近似/秒）、语音占比、停顿数、时长。"""
    total = len(samples)
    if total == 0:
        return {"duration_s": 0.0, "speech_ratio": 0.0, "pauses": 0,
                "syllables_per_sec": 0.0}
    segs = split_segments(samples, sr, use_pcen=True)
    voiced = sum(e - s for s, e in segs)
    # 停顿 = 有声段之间的间隙 ≥ 200ms
    pauses = sum(1 for a, b in zip(segs, segs[1:]) if b[0] - a[1] >= sr * 0.2)
    env = envelope(samples, sr)
    peaks = _burst_peaks(env)
    duration = total / sr
    return {
        "duration_s": round(duration, 3),
        "speech_ratio": round(voiced / total, 3),
        "pauses": pauses,
        "syllables_per_sec": round(len(peaks) / duration, 2) if duration else 0.0,
    }


def _score_fluency(feat: dict) -> int:
    """流利度 0-100：语音占比高、停顿少 → 高分（线性映射，够纵向差分用）。"""
    ratio = feat["speech_ratio"]
    pause_penalty = min(30, feat["pauses"] * 10)
    return int(max(0, min(100, ratio * 100 - pause_penalty)))


def assess(samples: Sequence[int], sr: int, *, expected_text: str | None = None,
           backend: Backend | None = None) -> dict:
    """发音评估。零依赖档返回 fluency/rhythm（韵律维）+ accuracy/completeness=None；
    提供 backend（GOPT 类）时合并其结果，backend 键如实标注来源。"""
    feat = prosodic_features(samples, sr)
    env = envelope(samples, sr)
    peaks = _burst_peaks(env)
    # 节奏：相邻峰间隔的变异系数（CV）→ 0.2 以下算规整
    gaps = [b - a for a, b in zip(peaks, peaks[1:])]
    if len(gaps) >= 2:
        mean = sum(gaps) / len(gaps)
        var = sum((g - mean) ** 2 for g in gaps) / len(gaps)
        cv = (var ** 0.5) / mean if mean else 1.0
        rhythm = int(max(0, min(100, 100 - cv * 100)))
    else:
        rhythm = 50  # 样本不足以评节奏：中性分
    result: dict = {
        "fluency": _score_fluency(feat),
        "rhythm": rhythm,
        "accuracy": None,
        "completeness": None,
        "prosody": feat,
        "backend": "none",
    }
    if backend is not None:
        merged = backend(samples, sr, expected_text)
        result.update({k: v for k, v in merged.items() if v is not None})
        result["backend"] = "custom"
    return result
