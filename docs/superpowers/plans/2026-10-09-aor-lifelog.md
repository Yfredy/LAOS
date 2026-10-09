# 全天候生活日志（Lifelog）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全天候录音升级为生活日志：①每天自动生成一篇生活日记（在小记/审计五章之上新增节律+声景章）；②时域节律记忆 + 频域声景记忆双入库（用途见 §双记忆的五个落地用途）；③零新增常驻内存（手机预算红线，与回放计划 §内存预算分工，见 §与回放计划的衔接）；④交付一份全天候录音功能版图（§功能版图，基于本仓既有 24 份调研的诚实盘点）。

**Architecture:** 数据全部来自 journal 漏斗已落盘的 VAD 分段（var/ear/journal/rec-*.wav），在原音频即焚（rec.gc）**之前**离线提取特征——不碰回放环冲、不新增任何常驻内存。三层：`laos/soundscape.py` 频域特征（Goertzel 分带能量纯 stdlib + 复用 `laos/loudness.py` 的 LUFS/True Peak/PLR）→ `bin/journal.py` 管线接线（既有转写不动，新增：每段 describe → 按小时聚合 → `kind="soundscape"` 文本记忆；`--diary` 收尾一键生成当日日记）→ `bin/diary.py` 第六章「今天的节律与声景」（`laos/rhythm.py` 从 journal 记忆派生小时画像渲染，并固化一条 `kind="rhythm"` 快照记忆）。时域与频域的记忆都是**文本**（无音频字节），日增量 ≈ 3.5KB。

**Tech Stack:** Python 3 纯 stdlib（Goertzel/wave/array/math/collections）；零新依赖；测试 unittest（miniconda python）。

**Spec:** 用户需求原文（2026-10-09，四点）："①每天的全天候录音都会生成一篇日记类型的东西，方便我们对每个人的生活进行记录。②时序记忆功能，就记录每个时间段的记忆情况，是时域上的记忆。然后时域的话肯定有频域，所以还要记录一下频域上的记忆。至于这两个记忆点是怎么用，等你自己来发掘。③确保我的这个全天候录音产生的 buffer 空间一定不能太大，因为我的手机内存是有限的。我是在 ADSP 里面去进行时域信息音频的存储。④你自己去收集考量一些全天候录音的功能……比如说语音情感识别、环境场景识别、音量自动增益的识别等各个功能。" ③由回放计划承接（已改：环冲默认 30s=960KB、clamp 5..120s），本计划遵守"零新增常驻内存"；④交付为本文 §功能版图；①②为本计划 Task 1–4。

## Global Constraints

- 零依赖红线：`laos/soundscape.py`、`laos/rhythm.py` 纯 stdlib。
- conda 红线：测试只用 `C:/Users/yaoyue/miniconda3/python.exe`。
- **内存预算红线（需求③）**：本波零新增常驻内存——特征是 journal 批处理的读盘离线计算；声景/节律记忆是文本行（soundscape ≈ 每天每小时 1 行 ≈ 2KB + rhythm 每天 1 行 ≈ 0.2KB）；AP 侧音频常驻只有回放环冲（30s=960KB，见回放计划 Global Constraints）；权威时域音频存储在 ADSP（用户部署形态），本波所有模块对 ADSP 透明（只消费落盘分段）。
- **特征必须先于即焚**：describe() 在主循环转写成功后立刻算（wav 还在盘上），rec.gc 之后不再读音频。
- 隐私红线：特征与统计只来自"只录自己"的 journal 分段；日记/记忆不含音频字节；"对每个人的生活进行记录"=每人一台设备各自生成各自日记（laos 无多人声纹分离，也不做——红线只录自己）。
- `SECTION_TITLES` 5→6 章是**显式契约变更**：`tests/test_diary.py` 的 `SECTION_TITLES_EXPECTED` 必须同步（Task 4 内完成，不许留红）。
- 实跑测试口径：`cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`，以 "Ran N tests" 实数为准（勿用预估值——并行波与回放波可能已推高基线）。
- 提交信息 conventional commits；发版（Task 6）走 AGENTS.md 发版纪律全清单。

---

### Task 1: laos/soundscape.py —— 频域声景特征（Goertzel + 复用 loudness）

**Files:**
- Create: `laos/soundscape.py`
- Test: `tests/test_soundscape.py`

**Interfaces:**
- Consumes: `laos.loudness.integrated_loudness(x, fs) / true_peak(x, fs) / plr(x, fs)`（x=通道列表，fs=采样率；drv_ear.ear_lufs 同款用法）。
- Produces: `BANDS = (125, 250, 500, 1000, 2000, 4000, 6000)`；`band_energies_db(pcm16: bytes, sr: int = 16000) -> dict[int, float]`（各带 dB，floor −120.0）；`describe(pcm16: bytes, sr: int = 16000) -> dict`（键 `lufs/true_peak_dbtp/plr/bands_db/flatness/peak_band`）；`aggregate(feats: list[dict]) -> dict`（多段均值，形状同 describe 去掉 peak_band 重算）；`render(feats: dict, hour: str, n_segments: int) -> str`（单行记忆文本）。Task 3 按这些名字消费。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_soundscape.py`：

```python
"""soundscape —— 频域声景特征（Goertzel 分带 + LUFS 复用，纯 stdlib）。

    python -m unittest tests.test_soundscape -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.soundscape import BANDS, aggregate, describe, render  # noqa: E402


def _sine_pcm(seconds: float, freq: float, sr: int = 16000,
              amp: float = 0.5) -> bytes:
    import array
    n = int(seconds * sr)
    a = array.array("h",
                    (int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr))
                     for i in range(n)))
    return a.tobytes()


class TestSoundscape(unittest.TestCase):
    # 信号一律 0.5s：响度计 400ms 窗/100ms hop 至少出两块（0.3s 会走
    # -inf→floor 路径，正弦 LUFS 断言会失真）
    def test_sine_peaks_at_its_band(self):
        feats = describe(_sine_pcm(0.5, 1000))
        self.assertEqual(feats["peak_band"], 1000)
        others = [v for b, v in feats["bands_db"].items() if b != 1000]
        self.assertGreater(feats["bands_db"][1000], max(others) + 6.0)

    def test_flatness_within_unit_range(self):
        for pcm in (_sine_pcm(0.5, 500), _sine_pcm(0.5, 2000)):
            self.assertGreaterEqual(describe(pcm)["flatness"], 0.0)
            self.assertLessEqual(describe(pcm)["flatness"], 1.0)

    def test_silence_floors_without_raising(self):
        feats = describe(b"\x00\x00" * 8000)  # 0.5s 全零 → 全程 <-70dB 门下
        self.assertEqual(feats["lufs"], -120.0)
        self.assertEqual(feats["plr"], 0.0)
        for v in feats["bands_db"].values():
            self.assertLessEqual(v, -100.0)

    def test_short_signal_floors_not_inf(self):
        # <0.4s 信号：integrated_loudness 返回 -inf，describe 必须钳到 floor
        feats = describe(_sine_pcm(0.2, 1000))
        self.assertGreater(feats["lufs"], -120.0 + 1e-9)  # 有信号不该走 floor
        self.assertTrue(feats["lufs"] != float("-inf"))

    def test_empty_pcm_safe(self):
        feats = describe(b"")
        self.assertEqual(set(feats), {"lufs", "true_peak_dbtp", "plr",
                                      "bands_db", "flatness", "peak_band"})
        self.assertEqual(feats["bands_db"], {b: -120.0 for b in BANDS})

    def test_aggregate_averages(self):
        f1 = describe(_sine_pcm(0.5, 500))
        f2 = describe(_sine_pcm(0.5, 2000))
        agg = aggregate([f1, f2])
        self.assertAlmostEqual(agg["lufs"], (f1["lufs"] + f2["lufs"]) / 2,
                               delta=0.15)
        self.assertAlmostEqual(
            agg["bands_db"][500],
            (f1["bands_db"][500] + f2["bands_db"][500]) / 2, delta=0.15)

    def test_render_compact_line(self):
        feats = describe(_sine_pcm(0.5, 1000))
        line = render(feats, "14", 3)
        self.assertIn("14时", line)
        self.assertIn("3段", line)
        self.assertIn("LUFS", line)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_soundscape -v 2>&1 | tail -5`
Expected: ERROR `ModuleNotFoundError: No module named 'laos.soundscape'`

- [ ] **Step 3: 最小实现**

创建 `laos/soundscape.py`：

```python
"""soundscape —— 频域声景特征（纯 stdlib：Goertzel 分带能量 + 复用 loudness）。

全天候录音的"频域记忆"数据源：journal 管线在原音频即焚（rec.gc）之前对
每段提取特征，按小时聚合成一条 kind="soundscape" 文本记忆——不存任何
音频字节。用途（见 plans/2026-10-09-aor-lifelog.md §双记忆的五个落地
用途）：场景指纹（带谱+flatness 相似度）、噪声暴露健康档案（LUFS 日
剂量）、未来 AGC 预判数据底座、麦克风自检（带谱异常=遮挡/故障）。

成本：Goertzel 每带一次全窗扫描——10s@16kHz 段约 7×160k 次乘加（纯
Python 亚秒级），journal 离线批处理可接受；不做流式。
"""

from __future__ import annotations

import array
import math

from laos.loudness import integrated_loudness, true_peak

#: 倍频程近似分带（Hz）——16kHz 采样上限 8kHz，6000 是有意义的最高带
BANDS = (125, 250, 500, 1000, 2000, 4000, 6000)
FLOOR_DB = -120.0


def _samples(pcm16: bytes) -> array.array:
    """PCM16 LE 字节 → 归一化 float 样本（奇数字节尾巴丢弃）。"""
    usable = len(pcm16) - len(pcm16) % 2
    a = array.array("h")
    a.frombytes(pcm16[:usable])
    return array.array("d", (s / 32768.0 for s in a))


def _goertzel_power(x: array.array, sr: int, freq: float) -> float:
    """单频点功率（Goertzel）：相对量纲，供分带间 dB 比较。"""
    if not x:
        return 0.0
    k = 2.0 * math.cos(2.0 * math.pi * freq / sr)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + k * s1 - s2
        s2, s1 = s1, s0
    return (s1 * s1 + s2 * s2 - k * s1 * s2) / (len(x) * len(x))


def band_energies_db(pcm16: bytes, sr: int = 16000) -> dict[int, float]:
    x = _samples(pcm16)
    if not x:
        return {b: FLOOR_DB for b in BANDS}
    out: dict[int, float] = {}
    for b in BANDS:
        p = _goertzel_power(x, sr, float(b))
        out[b] = FLOOR_DB if p <= 1e-12 else round(10.0 * math.log10(p), 1)
    return out


def describe(pcm16: bytes, sr: int = 16000) -> dict:
    """一段 PCM16 的完整声景特征（响度三件套复用 loudness.py）。

    floor 防护：integrated_loudness 对 <0.4s 信号或全静音返回 -inf
    （loudness.py:128 `if not loud: return -inf`）——一律钳到 FLOOR_DB，
    PLR 由两 floor 值推导（避免 -inf-(-inf)=nan）。"""
    x = _samples(pcm16)
    if not x:
        return {"lufs": FLOOR_DB, "true_peak_dbtp": FLOOR_DB, "plr": 0.0,
                "bands_db": {b: FLOOR_DB for b in BANDS},
                "flatness": 0.0, "peak_band": 0}
    bands = band_energies_db(pcm16, sr)
    lin = [10.0 ** (v / 10.0) for v in bands.values()]
    geo = math.exp(sum(math.log(max(p, 1e-12)) for p in lin) / len(lin))
    lufs = max(FLOOR_DB, round(integrated_loudness([x], sr), 1))
    tp = max(FLOOR_DB, round(true_peak([x], sr), 1))
    plr_v = round(tp - lufs, 1) if (tp > FLOOR_DB and lufs > FLOOR_DB) else 0.0
    return {"lufs": lufs, "true_peak_dbtp": tp, "plr": plr_v,
            "bands_db": bands,
            "flatness": round(geo / (sum(lin) / len(lin)), 3),
            "peak_band": max(bands, key=bands.get)}


def aggregate(feats: list[dict]) -> dict:
    """多段均值聚合：数值键逐个平均，bands_db 逐带平均，peak_band 重算。"""
    if not feats:
        raise ValueError("EINVAL: aggregate of empty list")
    n = len(feats)

    def mean(key: str) -> float:
        return round(sum(f[key] for f in feats) / n, 1)

    bands = {b: round(sum(f["bands_db"][b] for f in feats) / n, 1)
             for b in BANDS}
    return {"lufs": mean("lufs"), "true_peak_dbtp": mean("true_peak_dbtp"),
            "plr": mean("plr"), "bands_db": bands,
            "flatness": round(sum(f["flatness"] for f in feats) / n, 3),
            "peak_band": max(bands, key=bands.get)}


def render(feats: dict, hour: str, n_segments: int) -> str:
    """单行记忆文本：'14时 3段：LUFS -23.4 PLR 9.8 峰值带 1000Hz(-30.1dB)
    flatness 0.012'——供 kind="soundscape" 记忆与日记第六章直拼。"""
    pk = feats["peak_band"]
    return (f"{hour}时 {n_segments}段：LUFS {feats['lufs']} "
            f"PLR {feats['plr']} 峰值带 {pk}Hz({feats['bands_db'][pk]}dB) "
            f"flatness {feats['flatness']}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_soundscape -v 2>&1 | tail -3`
Expected: `Ran 7 tests ... OK`

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add laos/soundscape.py tests/test_soundscape.py
git commit -m "feat(soundscape): 频域声景特征——Goertzel 分带+LUFS/PLR 复用（纯 stdlib，即焚前离线）"
```

---

### Task 2: laos/rhythm.py —— 时域节律档案

**Files:**
- Create: `laos/rhythm.py`
- Test: `tests/test_rhythm.py`

**Interfaces:**
- Consumes: journal 记忆 dict（`ts: float`、`tags: list[str]`，情感=首个大写 tag，与 bin/diary.py 第五章同规则）。
- Produces: `hour_profile(records: list[dict]) -> dict[str, dict]`（本地时区 `"HH"` → `{"segments": int, "emotions": dict[str, int]}`）；`busiest(profile: dict) -> str | None`（段数最多的小时，空 profile 返回 None）；`dominant_emotion(profile: dict) -> str | None`（全 profile 情感计数冠军）；`render(profile: dict) -> str`（`"09时 2段(NEUTRAL:2) · 14时 3段(HAPPY:1,NEUTRAL:2)"`，小时升序；空 profile 返回 `""`）。Task 4 按这些名字消费。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_rhythm.py`：

```python
"""rhythm —— 时域节律档案（journal 记忆 → 小时画像，纯派生）。

    python -m unittest tests.test_rhythm -v
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.rhythm import busiest, dominant_emotion, hour_profile, render  # noqa: E402


def _journal_rec(ts: float, emotion: str) -> dict:
    return {"id": 1, "ts": ts, "kind": "journal", "text": "x",
            "tags": [emotion], "origin": "journal"}


def _at_today(hour: int, minute: int = 0) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday,
                        hour, minute, 0, 0, 0, -1))


class TestRhythm(unittest.TestCase):
    def test_groups_by_local_hour(self):
        p = hour_profile([_journal_rec(_at_today(9), "NEUTRAL"),
                          _journal_rec(_at_today(9, 30), "HAPPY"),
                          _journal_rec(_at_today(14), "ANGRY")])
        self.assertEqual(p["09"]["segments"], 2)
        self.assertEqual(p["14"]["segments"], 1)

    def test_emotion_falls_back_to_neutral(self):
        p = hour_profile([{"ts": _at_today(8), "tags": ["chat"]}])
        self.assertEqual(p["08"]["emotions"], {"NEUTRAL": 1})

    def test_busiest_and_dominant(self):
        recs = ([_journal_rec(_at_today(9), "NEUTRAL")]
                + [_journal_rec(_at_today(14), f) for f in ("HAPPY", "SAD")])
        p = hour_profile(recs)
        self.assertEqual(busiest(p), "14")
        self.assertEqual(dominant_emotion(p), "NEUTRAL")  # 三情绪并列 1 票，Counter 取首遇（插入序）

    def test_empty_profile(self):
        self.assertEqual(hour_profile([]), {})
        self.assertIsNone(busiest({}))
        self.assertIsNone(dominant_emotion({}))
        self.assertEqual(render({}), "")

    def test_render_sorted_compact(self):
        p = hour_profile([_journal_rec(_at_today(14), "HAPPY"),
                          _journal_rec(_at_today(9), "NEUTRAL")])
        line = render(p)
        self.assertIn("09时 1段(NEUTRAL:1)", line)
        self.assertIn("14时 1段(HAPPY:1)", line)
        self.assertLess(line.index("09时"), line.index("14时"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_rhythm -v 2>&1 | tail -5`
Expected: ERROR `ModuleNotFoundError: No module named 'laos.rhythm'`

- [ ] **Step 3: 最小实现**

创建 `laos/rhythm.py`：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_rhythm -v 2>&1 | tail -3`
Expected: `Ran 5 tests ... OK`

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add laos/rhythm.py tests/test_rhythm.py
git commit -m "feat(rhythm): 时域节律档案——journal 记忆按小时画像（纯派生，busiest/主导情绪/紧凑渲染）"
```

---

### Task 3: bin/journal.py —— 特征接线 + 小时声景记忆 + --diary

**Files:**
- Modify: `bin/journal.py`（docstring、`run_pipeline` 签名与主循环、`main` 增 `--diary`）
- Test: `tests/test_journal.py`（追加 3 例）

**Interfaces:**
- Consumes: Task 1 的 `describe/aggregate/render`；既有 `MemoryStore.remember(kind, text, tags)`；`bin/diary.py` 的 `build_diary/_load_audit/DEFAULT_AUDIT`（仅 `--diary` 路径 import，保持 journal 主体零耦合）。
- Produces: `run_pipeline(journal_dir, memory, *, transcribe=None, gc_keep_hours=None, spectral: bool = True) -> dict`——返回 dict 在既有 `ok/errors` 之上新增 `"soundscape_hours": list[str]`（生成了声景记忆的小时列表，按小时升序）；每个有声段的小时聚合成一条 `kind="soundscape"` 记忆（`tags=[<该段日期 YYYY-MM-DD>, "soundscape"]`，text=`render(aggregate([...]), hour, n)`）。`main()` 新增 `--diary` 开关：管线跑完后对当天调用 `diary.build_diary`。既有调用（test_journal 旧 3 例、bin/journal.py 无参 CLI）行为不变。

- [ ] **Step 1: 写失败测试**

在 `tests/test_journal.py` 的 `TestJournalPipeline` 类内（`test_empty_dir_friendly` 之后）追加：

```python
    def test_soundscape_memories_per_hour(self):
        import os
        # 两段分属不同小时（mtime 相差 1h）：小时聚合键不同 → 两条声景记忆
        os.utime(self.journal_dir / "rec-0001-1.wav",
                 (1759957200.0, 1759957200.0))
        os.utime(self.journal_dir / "rec-0002-2.wav",
                 (1759960800.0, 1759960800.0))
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe,
                              gc_keep_hours=None)
        self.assertEqual(len(result["soundscape_hours"]), 2)
        sc = [m for m in self.memory.recall("LUFS", k=10)
              if m.get("kind") == "soundscape"]
        self.assertGreaterEqual(len(sc), 2)
        self.assertTrue(all("LUFS" in m["text"] for m in sc))
        # 既有 journal 记忆不受影响
        self.assertEqual(self.memory.stats()["by_kind"].get("journal"), 2)

    def test_spectral_false_opts_out(self):
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe,
                              spectral=False, gc_keep_hours=None)
        self.assertEqual(result["soundscape_hours"], [])
        self.assertIsNone(self.memory.stats()["by_kind"].get("soundscape"))

    def test_features_survive_gc_zero(self):
        from journal import run_pipeline
        result = run_pipeline(self.journal_dir, self.memory,
                              transcribe=self._transcribe, gc_keep_hours=0)
        # 音频全焚后声景记忆仍在（特征先于 GC 提取）
        self.assertEqual(len(list(self.journal_dir.glob("*.wav"))), 0)
        self.assertEqual(len(result["soundscape_hours"]), 1)
```

同时 `setUp` 末尾（`self.calls = calls` 之后）追加一行，把 mock 存到实例（上面三例都引用它）：

```python
        self._transcribe = drv_ear.transcribe
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_journal -v 2>&1 | tail -5`
Expected: 新 3 例 FAIL/ERROR（`run_pipeline() got an unexpected keyword argument 'spectral'` / `KeyError: 'soundscape_hours'`）；旧 3 例仍绿

- [ ] **Step 3: 实现 journal.py 改动**

对 `bin/journal.py` 做三处修改：

（a）docstring 流程行更新（在"→ mem.remember(kind="journal"…"行后补一句）：

```
→ 每段声景特征（laos.soundscape.describe，即焚前提取）按小时聚合为
  kind="soundscape" 记忆（spectral=True 默认开；--diary 收尾生成当日日记）
```

（b）`run_pipeline` 签名与实现：

```python
def run_pipeline(journal_dir: Path, memory, *, transcribe=None,
                 gc_keep_hours: float | None = None,
                 spectral: bool = True) -> dict:
    """转写目录内所有分段并入记忆库。返回 {"ok": [...], "errors": [...],
    "soundscape_hours": [...]}。

    语义：转写成功的段落 mem.remember(kind="journal", tags=[emotion])；
    失败段记录错误继续（不中断批次）；gc_keep_hours 非 None 时按
    mtime 清理（0 = 立即即焚——"转写成功为前提"的默认策略由调用方控制）。
    spectral=True 时每段在即焚前提取声景特征（describe），按 (日期,小时)
    聚合，循环后逐小时 mem.remember(kind="soundscape", tags=[日期,
    "soundscape"])——特征先于 GC，音频焚毁不影响记忆。
    """
    if transcribe is None:
        import drv_ear
        transcribe = drv_ear.transcribe

    import time as _time

    from laos.soundscape import aggregate, describe, render as sc_render

    ok, errors = [], []
    _sc_feats: dict[tuple[str, str], list[dict]] = {}  # (date, hour) -> feats
    _sc_counts: dict[tuple[str, str], int] = {}
    for wav in sorted(Path(journal_dir).glob("rec-*.wav")):
        try:
            raw = transcribe(str(wav))
            item = json.loads(raw) if isinstance(raw, str) else raw
        except Exception as exc:
            errors.append({"wav": wav.name, "error": str(exc)[:120]})
            continue
        emotion = (item.get("emotions") or [""])[0] or "NEUTRAL"
        hour_min = datetime.fromtimestamp(wav.stat().st_mtime).strftime("%H:%M")
        memory.remember(kind="journal",
                        text=f"[{hour_min}] {item.get('text', '')}",
                        tags=[emotion])
        if spectral:
            try:  # 特征失败不拖垮转写批次（坏音频已被上面 try 拦，此处防御性）
                mtime = wav.stat().st_mtime
                lt = _time.localtime(mtime)
                key = (_time.strftime("%Y-%m-%d", lt),
                       _time.strftime("%H", lt))
                _sc_feats.setdefault(key, []).append(
                    describe(wav.read_bytes()))
                _sc_counts[key] = _sc_counts.get(key, 0) + 1
            except Exception:
                pass
        ok.append({"wav": wav.name, "text": item.get("text", ""),
                   "emotions": item.get("emotions", [])})

    soundscape_hours: list[str] = []
    for (date, hour) in sorted(_sc_feats):
        text = sc_render(aggregate(_sc_feats[(date, hour)]), hour,
                         _sc_counts[(date, hour)])
        memory.remember(kind="soundscape", text=text,
                        tags=[date, "soundscape"], origin="journal")
        soundscape_hours.append(hour)

    if gc_keep_hours is not None:
        cutoff_age = gc_keep_hours
        import time
        for wav in Path(journal_dir).glob("rec-*.wav"):
            if wav.stat().st_mtime < time.time() - cutoff_age * 3600:
                wav.unlink(missing_ok=True)

    return {"ok": ok, "errors": errors,
            "soundscape_hours": soundscape_hours}
```

（c）`main()` 增开关（`--dry-run` 参数行之后加一行、`args = ap.parse_args()` 之后管线调用之后加 --diary 分支）：

```python
    ap.add_argument("--diary", action="store_true",
                    help="管线跑完后生成当天日记（bin/diary.py build_diary）")
```

`result = run_pipeline(...)` 之后、`return 0` 之前插入：

```python
    if args.diary:
        from diary import DEFAULT_AUDIT, _load_audit, build_diary
        today = time.strftime("%Y-%m-%d")
        build_diary(today, _load_audit(Path(DEFAULT_AUDIT)), memory)
        print(f"[journal] 已生成当日日记（diary/{today}.md）", file=sys.stderr)
```

（`time`/`sys` 已在 journal.py 顶部 import；`memory` 变量为 main 里既有 MemoryStore 实例。"每天自动生成"的自动化由部署侧定时器承担——cron/Tasker 每晚调 `python bin/journal.py --diary`，laos 侧只保证这一键原子可用。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_journal -v 2>&1 | tail -3`
Expected: `Ran 6 tests ... OK`（旧 3 + 新 3）

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add bin/journal.py tests/test_journal.py
git commit -m "feat(journal): 声景特征接线——即焚前 describe 按小时聚合 kind=soundscape 记忆 + --diary 一键日记（spectral 可关）"
```

---

### Task 4: bin/diary.py —— 第六章「今天的节律与声景」+ rhythm 快照入库

**Files:**
- Modify: `bin/diary.py`（`SECTION_TITLES` 6 元组、`build_diary` 第六章块、rhythm 快照 remember）
- Modify: `tests/test_diary.py`（`SECTION_TITLES_EXPECTED` 6 元组 + 新 2 例）

**Interfaces:**
- Consumes: Task 2 的 `hour_profile/busiest/dominant_emotion/render`；第五章既有的 `heard`（journal 记忆当日过滤）；`memory_store._records`（第五章同款内部访问先例）。
- Produces: `SECTION_TITLES` = 既有 5 章 + `"六、今天的节律与声景"`；`build_diary` 返回 sections 增第六键（既有键全部不动、五章内容不动）；heard 非空时额外 `memory_store.remember(kind="rhythm", text=render(hour_profile(heard)), tags=[date], origin="diary")`。第六章文本规则：节律行（render + "——最活跃 {busiest} 时，主导情绪 {dominant}"）、声景行（当日 soundscape 记忆 text 逐行拼）、两者皆空 → "（今天没有节律/声景记录——journal 管线跑过才有）"。

- [ ] **Step 1: 写失败测试（含契约变更同步）**

`tests/test_diary.py` 两处修改：

（a）第 23 行契约常量改为 6 元组：

```python
SECTION_TITLES_EXPECTED = ("一、今天做了什么", "二、新记住的事", "三、被拒绝与原因", "四、明天可以试试", "五、今天听到的", "六、今天的节律与声景")
```

（b）`TestBuildDiary` 类内追加两例（`import time` 已有；需要 `from laos.rhythm import hour_profile` 不必——黑盒走 build_diary）：

```python
    def test_sixth_section_renders_rhythm_and_soundscape(self):
        # 当天 14 时两条 journal 记忆 + 一条当日 soundscape 记忆
        day_start = datetime.strptime(self.date, "%Y-%m-%d").timestamp()
        h14 = day_start + 14 * 3600
        self.store.remember("journal", "[14:02] 说了句什么", tags=["HAPPY"])
        self.store._records[-1]["ts"] = h14  # 直接钉时间戳（绕开 now 偶然）
        self.store.remember("journal", "[14:40] 又说了句", tags=["NEUTRAL"])
        self.store._records[-1]["ts"] = h14 + 2380
        self.store.remember("soundscape",
                            "14时 2段：LUFS -23.4 PLR 9.8 峰值带 1000Hz"
                            "(-30.1dB) flatness 0.012",
                            tags=[self.date, "soundscape"])
        self.store._records[-1]["ts"] = h14
        result = build_diary(self.date, self.records, self.store)
        sixth = result["六、今天的节律与声景"]
        self.assertIn("14时 2段", sixth)
        self.assertIn("LUFS -23.4", sixth)
        self.assertIn("最活跃 14 时", sixth)
        # rhythm 快照入库：kind=rhythm，tags 含日期
        rhythms = [m for m in self.store._records if m.get("kind") == "rhythm"]
        self.assertEqual(len(rhythms), 1)
        self.assertIn(self.date, rhythms[0]["tags"])
        self.assertIn("14时", rhythms[0]["text"])

    def test_sixth_section_empty_placeholder(self):
        result = build_diary(self.date, self.records, self.store)
        self.assertIn("没有节律/声景记录", result["六、今天的节律与声景"])
        self.assertFalse([m for m in self.store._records
                          if m.get("kind") == "rhythm"])
```

（`from datetime import datetime` 在 tests/test_diary.py 头部**缺失**——写计划时已核实（其导入区只有 os/sys/tempfile/time/unittest/pathlib/mock），在 `from pathlib import Path` 之后补一行 `from datetime import datetime`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_diary -v 2>&1 | tail -5`
Expected: 新 2 例 FAIL（result 无 "六、今天的节律与声景" 键）；`test_section_titles_constant` FAIL（5≠6）；其余既有例 FAIL 于标题循环——契约变更的预期红

- [ ] **Step 3: 实现 diary.py 改动**

对 `bin/diary.py` 做三处修改：

（a）`SECTION_TITLES` 元组追加第六章：

```python
SECTION_TITLES = (
    "一、今天做了什么",
    "二、新记住的事",
    "三、被拒绝与原因",
    "四、明天可以试试",
    "五、今天听到的",
    "六、今天的节律与声景",
)
```

（b）`build_diary` 内第五章 `heard_txt` 块之后追加第六章构建（插在 `sections = dict(zip(SECTION_TITLES, ...))` 之前）：

```python
    # ---- 第六章：今天的节律与声景（时域节律 + 频域声景双记忆）----------
    from laos.rhythm import busiest, dominant_emotion, hour_profile, render
    lines6 = []
    if heard:
        profile = hour_profile(heard)
        lines6.append(
            f"- 节律：{render(profile)}"
            f"——最活跃 {busiest(profile)} 时，"
            f"主导情绪 {dominant_emotion(profile) or 'NEUTRAL'}")
        memory_store.remember(
            kind="rhythm", text=render(profile), tags=[date],
            origin="diary")  # 时序记忆快照：日后可 mem.recall("<日期> 14时")
        sc = [r for r in memory_store._records
              if r.get("kind") == "soundscape" and date in r.get("tags", [])]
        for r in sc:
            lines6.append(f"- 声景：{r['text']}")
    rhythm_txt = ("\n".join(lines6)
                  if lines6
                  else "（今天没有节律/声景记录——journal 管线跑过才有）")
```

（c）`sections = dict(zip(SECTION_TITLES, (did, memories, denied_txt, tomorrow, heard_txt)))` 改为六元组：

```python
    sections = dict(zip(SECTION_TITLES,
                        (did, memories, denied_txt, tomorrow, heard_txt,
                         rhythm_txt)))
```

- [ ] **Step 4: 跑测试确认通过（diary 全回归）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_diary -v 2>&1 | tail -3`
Expected: 全绿（既有全部 + 新 2 例）

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add bin/diary.py tests/test_diary.py
git commit -m "feat(diary): 第六章「今天的节律与声景」——rhythm 小时画像+当日 soundscape 拼装+rhythm 快照入库（SECTION_TITLES 5→6 契约变更）"
```

---

### Task 5: 全量回归 + 功能地图登记（A11）+ README

**Files:**
- Modify: `docs/guide/laos-features-map.md`（A 组追加 A11 行）
- Modify: `README.md`（功能地图节 AI 行计数 +1、追加短语）

**Interfaces:**
- Consumes: Task 1–4 落地后的实跑测试数。
- Produces: A11 登记 + README 对齐；全量绿基线（Task 6 依赖）。

- [ ] **Step 1: 全量测试**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `OK`。记实跑数（勿用预估值——回放波 v0.36.0 是否已并入以 git log 为准）。失败先修再走下步。

- [ ] **Step 2: 功能地图登记**

`docs/guide/laos-features-map.md` 在 A10 行（录音回放，回放波登记）之后追加：

```markdown
| A11 | **生活日志双记忆** soundscape/rhythm | 频域声景（Goertzel 分带+LUFS，即焚前提取）+时域节律（小时画像）双记忆，日记六章自动生成 | `python bin/journal.py --diary`；laosweb「生成今日日记」 |
```

若回放波（A10）尚未执行：A11 行仍按上表插入，A10 行由回放波自己的 Task 5 补插（两波登记互不阻塞，序号已预留）。

- [ ] **Step 3: README 功能地图行**

README 功能地图节 AI 行：计数 +1（回放波已执行则 11→12；未执行则 10→11——**以执行时 README 实数 +1 为准**），行尾追加 ` · 生活日志（节律+声景双记忆/日记六章）`。

- [ ] **Step 4: 交接门禁**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/check_onboarding.py`
Expected: 绿（本波未改 ONBOARDING.md；报红则按脚本输出改齐再跑绿）。

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add docs/guide/laos-features-map.md README.md
git commit -m "docs: 功能地图登记 A11 生活日志双记忆（README AI 行 +1）"
```

---

### Task 6: 发版 v0.37.0（AGENTS.md 发版纪律全清单）

**Files:**
- Modify: 三棵树 `__version__`、CHANGELOG.md、全部介绍文件锚点（release.py 自动）

**Interfaces:**
- Consumes: Task 5 的全量绿基线与实跑测试数。
- Produces: v0.37.0 tag + GitHub Release 页 + 介绍文件同步。

- [ ] **Step 1: dry-run 核对**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/release.py --dry-run`
Expected: 全绿；下一版本 **v0.37.0**（若回放波 v0.36.0 尚未发版，先执行回放波 Task 6 再回来——版本号严格递增）。

- [ ] **Step 2: apply**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/release.py --apply`

- [ ] **Step 3: CHANGELOG 人工段落**

在 `CHANGELOG.md` 的 `[Unreleased]` 之下插入（日期以实际发版日为准）：

```markdown
## [0.37.0] - 2026-10-09

### Added
- **生活日志双记忆**：全天候录音从"转写留档"升级为"生活记录"。
  - `laos/soundscape.py`：频域声景特征（Goertzel 七分带 + 复用 LUFS/
    True Peak/PLR，纯 stdlib）——journal 即焚前提取，零新增常驻内存
  - `laos/rhythm.py`：时域节律档案（journal 记忆按小时画像，纯派生）
  - `bin/journal.py`：每段特征按 (日期,小时) 聚合成 `kind="soundscape"`
    记忆；`--diary` 一键收尾生成当日日记；`spectral=False` 可关
  - `bin/diary.py`：新增第六章「今天的节律与声景」（节律行+声景行），
    并固化当日 `kind="rhythm"` 快照（时间检索锚点）
  - 记忆增量 ≈ 3.5KB/天（文本）；功能版图见
    docs/superpowers/plans/2026-10-09-aor-lifelog.md §功能版图
```

- [ ] **Step 4: release commit + tag + push**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add -A
git commit -m "chore(release): v0.37.0 — 生活日志双记忆（声景+节律）与日记六章"
git tag -a v0.37.0 -m "生活日志：频域声景+时域节律双记忆，每日日记六章"
git push origin master --tags
```

- [ ] **Step 5: GitHub Release 页**

按既有 json 文件法建 Release（token 经 `git credential fill`，不回显）：title `v0.37.0 — 生活日志双记忆`，notes 用 Step 3 段正文。验证 API 200 / `gh release view v0.37.0`。

---

## §双记忆的五个落地用途（需求②"怎么用等你自己来发掘"的回答）

| # | 用途 | 数据 | 状态 |
|---|---|---|---|
| 1 | **日记第六章**：生活记录的日常呈现（节律+声景+情感） | rhythm + soundscape | ● 本波 Task 4 |
| 2 | **时间检索**：`mem.recall("2026-10-09 14时")` 命中 rhythm 快照与该时 journal 行——"上周三下午我在说什么"成为可查询问题 | rhythm 快照 | ● 本波 Task 4（能力就位，检索走既有 bigram 召回） |
| 3 | **作息画像与异常**：跨天 rhythm 对比（早鸟/夜猫漂移、独居安全"连续 3 小时无人声"提醒） | rhythm 日累积 | ◐ 未来波（需跨周数据积累，触发条件：用户点名） |
| 4 | **噪声暴露健康档案**：每日 LUFS 剂量曲线（职业卫生 80dB/8h 参考线）；带谱异常=麦克风遮挡/故障自检 | soundscape 日累积 | ◐ 未来波（数据本波开始积累） |
| 5 | **AGC/ASC 数据底座**：带谱历史 → 未来增益预判（调音先例可循）；带谱+flatness 相似度 → 场景指纹（"这段像办公室"） | soundscape | ◐ 未来波（与功能版图 ASC/AGC 触发条件挂钩） |

## §与回放计划的衔接（内存预算分工，需求③）

| 存储 | 位置 | 预算 | 生命周期 |
|---|---|---|---|
| 权威时域音频 | **ADSP**（用户部署形态） | 设备侧自理 | laos 不可见 |
| 回放环冲（AP） | drv_mic 进程内存 | 默认 30s=960KB，clamp ≤120s | 进程即逝（回放计划已按此收紧） |
| journal 分段 | var/ear/journal/（盘） | LAOS_JOURNAL_KEEP_H=6h | 转写+特征提取后即焚 |
| 双记忆 | memory.jsonl（盘） | ≈3.5KB/天文本 | 长期（文本，无音频字节） |

本波**零新增常驻内存**：soundscape/rhythm 都是 journal 批处理的离线读盘计算 + 文本行追加。

## §功能版图（需求④的交付——基于本仓既有调研的诚实盘点，非新调研）

> 用户点名：语音情感识别、环境场景识别、音量自动增益。以下每行状态均有既有文档背书；"本波动作"只做零依赖/低依赖项，模型级升级按触发条件排队。

| 能力 | laos 现状 | 本波动作 | 模型级升级的触发条件（出处） |
|---|---|---|---|
| 语音情感识别 SER | ● 已在链路：drv_ear funasr 通道富文本标签 → journal tags → 日记第五章情感分布 | 无需动作（数据已被第六章复用） | HY4 sherpa 通道已并行可用（speech-emotion/06-adoption） |
| 环境场景识别 ASC | 空白 | ◐ **本波奠基**：soundscape 带谱+flatness=特征层积木 | 模型版与 AED 同条件：A 档真机 或 中文场景微调（audio-events/2026-09-landscape §2 中文空白） |
| 音频事件识别 AED | ○ 暂不引入：B 档维持 VAD 能量门 | 无 | ①走出 proot 拿 A 档 ②事件类别固定或中文微调 ③事件标签只改蒸馏不改留存（audio-events/07-adoption §3） |
| 音量自动增益 AGC | ○ 模型版不加（分层裁决：闭环增益是 DSP 已有） | ◐ **本波奠基**：LUFS 日档案=未来增益预判数据底座 | 判断层流量≥千次/周 或 B 档解除（auto-gain/07-adoption） |
| 唤醒词 KWS | ● sherpa zipformer 3.3M int8 实测（解码中位 7.56ms） | 无 | 已达标 |
| 打断/全双工 | ● duplex/turnpolicy/wakegate（ARVIS R1-R3，v0.30.0） | 无 | AEC3 回声消除走驱动子进程波（R5 排队） |
| 录音回放 | 回放计划整波（v0.36.0） | 无（本计划 §衔接） | — |
| 摘要回顾（长音频） | 回放计划 §扩展位（预留） | 无 | 用户点名下一波 |
| 说话人验证/多人 | ○ 红线只录自己，无多人需求 | 无 | EoW 唤醒词注册音范式 ◐ 远线（docs/research/2026-10-09-interspeech2026-se-trends.md D1） |
| 听觉健康/噪声暴露 | 空白 | ◐ **本波奠基**：LUFS 日剂量数据开始积累 | 用途 4 未来波 |
| 空间音频/定位 | ● 资产在库（binaural/foa/micgeom），非全天候场景 | 无 | 用户点名 |

## 现状锚点（写计划时核实过的代码事实）

- `bin/diary.py`：五章 SECTION_TITLES（:43-49）；第五章 heard 过滤 `kind=="journal"` + 情感 Counter（:259-273）；`build_diary(date, audit_records, memory_store, brain=None)` 返回 sections/markdown/stats；写 var/diary/<date>.md 并 remember(kind="diary", tags=[date], origin="diary")（:279-287）。
- `tests/test_diary.py:23`：`SECTION_TITLES_EXPECTED` 五元组钉死标题（`test_section_titles_constant` 精确相等）——第六章必须同步改。
- `bin/journal.py`：`run_pipeline(journal_dir, memory, *, transcribe=None, gc_keep_hours=None)`；转写成功 → `mem.remember(kind="journal", text="[HH:MM] ...", tags=[emotion])`；gc 在循环后（:54-84）。`tests/test_journal.py` 钉：`by_kind.get("journal")==2`、gc_keep_hours=0 全焚、坏 wav 报错继续——spectral 记忆用不同 kind 不破坏这些断言；特征必须在 gc 前提取。
- `laos/loudness.py`：`integrated_loudness(x, fs)/true_peak(x, fs)/plr(x, fs)`，x=通道列表（drv_ear.ear_lufs 的 `array.array("d")` 通道同款用法 :346-349）。
- `laos/memory.py:124-138`：remember 记录形状 `{id, ts, kind, text, tags, origin, origin_pid}`；recall 是 bigram Jaccard（时间检索用途 2 依赖文本里含 "14时" 等词）。
- 功能地图：A 组尾 A9（回放波预留 A10）；README 功能地图节 AI 行计数 9 项（两波各 +1）。
