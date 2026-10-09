"""rhythm —— 时域节律档案：journal 记忆 → 按小时的生活节律画像。

纯派生（不落盘）：输入 journal kind 记忆（ts + 情感 tag），输出小时
分布。两条消费路径：① diary 第六章渲染；② 日记生成时固化一条
kind="rhythm" 快照记忆（可日后 mem.recall("上周三 14时") 时间检索）。
情感判定与 bin/diary.py 第五章同规则：首个全大写 tag，无则 NEUTRAL。
"""

from __future__ import annotations

import time
from collections import Counter


def _emotion_of(rec: dict) -> str:
    return next((t for t in rec.get("tags", []) if t.isupper()), "NEUTRAL")


def hour_profile(records: list[dict]) -> dict[str, dict]:
    """journal 记忆列表 → {"HH": {"segments": n, "emotions": {E: n}}}。"""
    out: dict[str, dict] = {}
    for rec in records:
        hour = time.strftime("%H", time.localtime(float(rec.get("ts", 0))))
        slot = out.setdefault(hour, {"segments": 0, "emotions": {}})
        slot["segments"] += 1
        emo = _emotion_of(rec)
        slot["emotions"][emo] = slot["emotions"].get(emo, 0) + 1
    return out


def busiest(profile: dict[str, dict]) -> str | None:
    if not profile:
        return None
    return max(profile, key=lambda h: profile[h]["segments"])


def dominant_emotion(profile: dict[str, dict]) -> str | None:
    counter: Counter = Counter()
    for slot in profile.values():
        counter.update(slot["emotions"])
    return counter.most_common(1)[0][0] if counter else None


def render(profile: dict[str, dict]) -> str:
    """紧凑单行/多行文本（小时升序）；空 profile 返回空串（调用方自管文案）。"""
    parts = []
    for hour in sorted(profile):
        slot = profile[hour]
        emo = ",".join(f"{e}:{n}" for e, n in sorted(
            slot["emotions"].items(), key=lambda kv: -kv[1]))
        parts.append(f"{hour}时 {slot['segments']}段({emo})")
    return " · ".join(parts)
