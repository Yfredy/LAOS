"""laos.vadmetrics —— VAD 成对指标：FA/FR/F1 + BG-FAR 防装死闸门。

来源：docs/research/2026-10-06-four-wechat-articles.md 采纳件 B
（Foreground VAD, arXiv 2609.19856 的指标配对原则）：

- 常规指标按"前景语音帧"算：precision / recall / F1、fa_rate（前景静音帧
  被误报为语音的比例）、fr_rate（漏检率 = 1 - recall）；
- **BG-FAR**：在"前景静音 ∧ 背景有声"帧上的误报率——餐厅隔壁桌说话导致
  的误报，正是一般 fa_rate 里最伤全双工体验的那部分；
- **防装死闸门**：BG-FAR 单独看会被"永远输出 0"的装死模型刷满，所以
  bg_far_valid = (f1 >= f1_floor)——F1 不过闸，BG-FAR 一律视为无效。

background 掩码未提供时 bg_far / bg_far_valid 为 None（未定义而非 0）。
纯函数零依赖；输入为逐帧布尔序列（10ms 粒度由调用方约定，本模块不关心）。
"""
from __future__ import annotations

from typing import Sequence

__all__ = ["evaluate_vad"]


def _ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


def evaluate_vad(pred: Sequence[bool], ref: Sequence[bool],
                 background: Sequence[bool] | None = None, *,
                 f1_floor: float = 0.5) -> dict:
    """对逐帧 VAD 预测算成对指标。

    pred：预测语音帧；ref：前景语音真值；background：背景有声真值（可选，
    用于 BG-FAR 分母"前景静音∧背景有声"）。三者等长，否则 ValueError。

    返回 dict：frames / tp / fp / fn / precision / recall / f1 /
    fa_rate / fr_rate / bg_far / bg_far_valid / f1_floor。
    """
    n = len(pred)
    if n == 0:
        raise ValueError("empty input")
    if len(ref) != n or (background is not None and len(background) != n):
        raise ValueError("pred/ref/background length mismatch")

    tp = fp = fn = tn = 0
    for p, r in zip(pred, ref):
        if p and r:
            tp += 1
        elif p and not r:
            fp += 1
        elif not p and r:
            fn += 1
        else:
            tn += 1

    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    bg_far: float | None = None
    bg_far_valid: bool | None = None
    if background is not None:
        bg_frames = [i for i in range(n) if not ref[i] and background[i]]
        if bg_frames:
            bg_far = sum(1 for i in bg_frames if pred[i]) / len(bg_frames)
            bg_far_valid = f1 >= f1_floor  # 装死闸门：F1 不过闸，BG-FAR 无效

    return {
        "frames": n,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1,
        "fa_rate": _ratio(fp, fp + tn),
        "fr_rate": _ratio(fn, fn + tp),
        "bg_far": bg_far,
        "bg_far_valid": bg_far_valid,
        "f1_floor": f1_floor,
    }
