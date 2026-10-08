"""kws —— 零依赖私有唤醒词：归一化包络 + DTW 模板匹配。

用户用 drv_mic 念几遍自家唤醒词 → enroll 存归一化能量包络模板；
之后任何一段录音用 match/best 比对，DTW 距离小于阈值即命中。
增益不变（包络按峰值归一）、时移/语速微变由 DTW 对齐吸收——
"enrollment + 模板匹配"是 EdgeSpot/LLM-Synth4KWS 之外最轻的零训练路线，
且模板只在本地内存/文件，不构成"声纹库"（不含可重建语音的信息）。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence


def envelope(samples: Sequence[int], sr: int, *, frame_ms: int = 10) -> list[float]:
    """PCM16 → 峰值归一化能量包络（0..1）。静音 clip → 全 0。"""
    frame = max(1, sr * frame_ms // 1000)
    env: list[float] = []
    for i in range(0, len(samples), frame):
        chunk = samples[i:i + frame]
        acc = 0
        for v in chunk:
            acc += v * v
        env.append(math.sqrt(acc / len(chunk)))
    peak = max(env, default=0.0)
    if peak <= 0.0:
        return [0.0] * len(env)
    env = [min(1.0, e / peak) for e in env]
    return _trim(env)


def _trim(env: list[float], floor: float = 0.1) -> list[float]:
    """剪掉首尾的近静音帧（对齐敏感度从"起始位置"转给 DTW 内部）。"""
    lo = 0
    while lo < len(env) and env[lo] < floor:
        lo += 1
    hi = len(env)
    while hi > lo and env[hi - 1] < floor:
        hi -= 1
    return env[lo:hi]


def count_peaks(env: list[float], *, height: float = 0.4,
                min_gap: int = 12) -> int:
    """数能量峰（音节近似）：>height 的连续段算一峰，峰间至少隔 min_gap 帧。"""
    peaks = 0
    run = False
    since = min_gap
    for v in env:
        if v >= height:
            if not run and since >= min_gap:
                peaks += 1
                since = 0
            run = True
        else:
            run = False
        since += 1
    return peaks


def dtw_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """经典 DTW，距离按对齐路径长度归一（不同时长可比）。"""
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 1.0
    INF = float("inf")
    prev = [INF] * (m + 1)
    prev[0] = 0.0
    for i in range(1, n + 1):
        cur = [INF] * (m + 1)
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = abs(ai - b[j - 1])
            cur[j] = cost + min(prev[j], cur[j - 1], prev[j - 1])
        prev = cur
    # 脉冲数差异惩罚：DTW 会用"拉伸"廉价吃掉多出来的峰，须单独罚
    return prev[m] / (n + m) + 0.5 * abs(count_peaks(list(a)) - count_peaks(list(b)))


class KeywordSpotter:
    """模板唤醒词：enroll 若干遍 → match(单模板)/best(全部模板取最优)。"""

    DEFAULT_MAX_DIST = 0.35  # 归一化 DTW 距离阈值（0=完全一致）

    def __init__(self, *, max_dist: float = DEFAULT_MAX_DIST):
        self.max_dist = max_dist
        self._templates: dict[str, list[list[float]]] = {}

    def enroll(self, name: str, samples: Sequence[int], sr: int) -> None:
        env = envelope(samples, sr)
        if max(env, default=0.0) <= 0.0:
            raise ValueError("enroll clip is silent")
        self._templates.setdefault(name, []).append(env)

    def match(self, samples: Sequence[int], sr: int, name: str) -> bool:
        """整段 clip 与指定词的所有模板比，任一低于阈值即命中。"""
        env = envelope(samples, sr)
        for tpl in self._templates.get(name, ()):
            if dtw_distance(env, tpl) <= self.max_dist:
                return True
        return False

    def best(self, samples: Sequence[int], sr: int) -> tuple[str | None, float]:
        """返回 (命中词, 距离)；无一命中时词为 None。"""
        env = envelope(samples, sr)
        best_name, best_d = None, self.max_dist
        for name, tpls in self._templates.items():
            for tpl in tpls:
                d = dtw_distance(env, tpl)
                if d <= best_d:
                    best_name, best_d = name, d
        return best_name, best_d

    def save(self, path: Path) -> None:
        """模板落盘（纯 JSON，不含音频，可随日记一起备份/删除）。"""
        import json
        Path(path).write_text(
            json.dumps({"max_dist": self.max_dist,
                        "templates": self._templates}, ensure_ascii=False),
            encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "KeywordSpotter":
        import json
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        s = cls(max_dist=data.get("max_dist", cls.DEFAULT_MAX_DIST))
        s._templates = {k: [list(t) for t in v]
                        for k, v in data.get("templates", {}).items()}
        return s
