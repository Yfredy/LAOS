# 听觉治理波（Auditory Governance Wave）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有四段漏斗（全天候听觉）之上新增四个内核治理能力——A 说话人分离（到达顺序）、B 听觉缺页召回、C 声景驱动调度、D 即焚销毁回执——把"记什么"升级为"谁在说 / 没了还能不能召回 / 该不该录 / 删了能不能证明"。

**Architecture:** 四段独立子系统共享同一套"内核侧纯 stdlib 计算 + 驱动挂钩消费"的姿势。A 在 `laos/speaker.py` 用 7 带谱质心做会话内贪心聚类（到达顺序=身份，绝不存原始声纹向量），`bin/journal.py` 转写后贴 `[S1]` 标签；B 在 `laos/audiodream.py` 给即焚后的 journal 记忆做"缺页语义"——`recall` 命中已焚段返回 `audio_status="burned"` 软降级而非报错；C 在 `laos/duty.py` 用聚合声景特征反推 VAD 阈值偏移，`drivers/drv_rec.py` 下一捕获段 `rec_start` 消费；D 在 `laos/burnt.py` 让 `rec_gc`/journal 删除前算 sha256 销毁回执（内容哈希算完即弃、只留哈希+元数据），新增 `burn.verify` 只读核验。

**Tech Stack:** Python 3 纯 stdlib（hashlib/array/math/wave/json/threading）；零新依赖；测试 unittest（`C:/Users/yaoyue/miniconda3/python.exe`）；驱动侧挂钩不新增第三方库。

**Spec:** 用户指令（2026-10-12）："针对本项目音视频功能，全天候录音 + AgentOS 内核，还能做什么创新"——四方向 A/B/C/D 全部采纳，落地形态锁定"内核侧纯 stdlib + 驱动挂钩"。红线随行（AGENTS.md）。

## Global Constraints

- 零依赖红线：`laos/` 新增四模块（speaker/audiodream/duty/burnt）只准 import 标准库；`drivers/` 侧改动同样不得新增顶层依赖（重依赖仍只进驱动子进程 .venv-audio）。
- conda 红线：只用 `C:/Users/yaoyue/miniconda3/python.exe`；禁止 `pip install` 进主环境；测试命令一律用该解释器绝对路径。
- **体量红线（内核/常驻语境新增，2026-10-12）**：laos 是内核治理 + 手机端常驻 lifelog（`ringbuf` 30s≈960KB"小镜像"、"权威时域存储在 ADSP"即此纪律），任何进**常驻/内核热路径**的模型后端**权重体量上限设 ~50MB 级**（含分带推理内存，非仅磁盘大小）；超限模型**只能走离线/桌面批处理后处理**（journal `--diar` 阶段），**不得进手机常驻链路、不得进 `laos/` 核心**。选型必须并列报"磁盘 MB + 峰值 RAM + CPU/GPU"三项，缺任一项不得进产品链路。
- 隐私红线（本波最高优先，四段各自强化）：
  - **A**：聚类只产"会话内序号标签"（S1/S2…），质心向量、原始声纹、任何可跨会话识别个体的特征**一律不落盘、不进记忆、不进审计**；跨会话身份关联明确列为不实现（open problem，见 §A 设计说明）。
  - **B**：缺页召回**永不复活音频字节**——只对既有文本记忆做语义标注，音频即焚后不可逆。
  - **C**：调度只调"灵敏度阈值"，不改变"录音只由显式 syscall 触发、`LAOS_REC=0` 全局禁录"这条既有红线。
  - **D**：回执只存 sha256（单向，不可反推内容）+ 文件名 + 字节数 + 时长 + 时刻；**原始字节哈希算完即弃**；回执文件不含任何音频内容或转写文本。
- 叙事红线：禁止"给 AI Agent 装上操作系统"类主客反转；四段一律表述为"内核治理语义在听觉链路上的延伸"。
- 契约兼容：`bin/journal.py run_pipeline` 现签名 `(journal_dir, memory, *, transcribe=None, gc_keep_hours=None, spectral=True)` 保持向后兼容——新参数一律带默认值追加在末尾；`bin/diary.py` SECTION_TITLES=6 不回退。
- 测试口径：README 写 unittest discover 实跑 "Ran N" 数，不是静态 `def test_` 计数；每段任务收尾必跑全量并记实际数字。
- 提交：conventional commits；每 Task 一 commit；四段各自收尾可独立发版（Section 末含 release 提示）。
- 全量测试命令（每条 Step 复用，勿改写）：
  ```bash
  cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
  ```

---

## Section A — 说话人分离（到达顺序 · 不建声纹库）

**缺口出处**：README §下一步 #1；调研 `docs/research/2026-09-12-speech-model-frontiers.md` §2（Streaming Sortformer 到达顺序 AOSC / USEF-TP personal VAD，P1 行"谁的日记"）。**设计说明**：PIPL 把声纹列为敏感个人信息需单独同意，故本波不建任何可跨会话识别个体的声纹库——只在一次 journal 批处理内，用 7 带谱质心做贪心聚类，把同一批音频切成"第 1 个说话人 / 第 2 个说话人"的会话内标签。跨天"同一人=同一主人"是调研明确列出的 open problem，本波**不实现**，Task 边界不为其预留磁盘结构。

### Task A1: 谱质心与到达顺序贪心聚类（laos/speaker.py）

**Files:**
- Create: `laos/speaker.py`
- Test: `tests/test_speaker.py`

**Interfaces:**
- Consumes: `laos/soundscape.BANDS`（`(125,250,500,1000,2000,4000,6000)`，soundscape.py:21）与 `laos/soundscape.describe(pcm16) -> dict`（返回含 `bands_db: dict[int,float]`）。
- Produces:
  - `bands_of(pcm16: bytes) -> dict[int, float]` —— 转发 `describe(pcm16)["bands_db"]`。
  - `to_centroid(bands_db: dict[int, float]) -> dict[int, float]` —— 归一化为每个质心分量 ∈ [0,1]（softmax，温度 1.0，按 dB 值）。
  - `centroid_distance(a: dict[int, float], b: dict[int, float]) -> float` —— 同带键欧氏距离，缺带按 0.0 计。
  - `label_speakers(segments: list[dict], threshold: float = 0.15) -> list[str]` —— `segments[i]` 必含 `"bands_db"`；返回与输入等长的标签列表 `["S1","S1","S2",...]`（到达顺序，贪心匹配已有质心，距离 > threshold 则新建）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_speaker.py`：

```python
"""speaker —— 到达顺序说话人聚类（7 带谱质心，纯 stdlib，不建声纹库）。

    python -m unittest tests.test_speaker -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.speaker import (bands_of, centroid_distance, label_speakers,
                          to_centroid)  # noqa: E402


def _sine_pcm(seconds: float, freq: float, sr: int = 16000,
              amp: float = 0.5) -> bytes:
    import array
    n = int(seconds * sr)
    a = array.array("h",
                    (int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr))
                     for i in range(n)))
    return a.tobytes()


class TestSpeaker(unittest.TestCase):
    def test_centroid_components_in_unit_range(self):
        c = to_centroid(bands_of(_sine_pcm(0.5, 1000)))
        self.assertEqual(len(c), 7)
        for v in c.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_same_source_distance_zero(self):
        c = to_centroid(bands_of(_sine_pcm(0.5, 1000)))
        self.assertAlmostEqual(centroid_distance(c, dict(c)), 0.0, places=9)

    def test_low_and_high_bands_are_far(self):
        low = to_centroid(bands_of(_sine_pcm(0.5, 200)))
        high = to_centroid(bands_of(_sine_pcm(0.5, 5000)))
        self.assertGreater(centroid_distance(low, high), 0.5)

    def test_label_speakers_splits_two_regimes(self):
        segs = [
            {"bands_db": bands_of(_sine_pcm(0.5, 200))},
            {"bands_db": bands_of(_sine_pcm(0.5, 250))},
            {"bands_db": bands_of(_sine_pcm(0.5, 5000))},
            {"bands_db": bands_of(_sine_pcm(0.5, 6000))},
        ]
        labels = label_speakers(segs, threshold=0.15)
        self.assertEqual(len(labels), 4)
        self.assertEqual(labels[0], "S1")
        self.assertEqual(labels[1], "S1")   # 低频两人同一簇
        self.assertEqual(labels[2], "S2")   # 高频新建簇
        self.assertEqual(labels[3], "S2")

    def test_label_speakers_is_arrival_order_first_is_S1(self):
        # 到达顺序=身份：第一个出现的簇恒为 S1（无外部随机种子、可复现）
        segs = [{"bands_db": bands_of(_sine_pcm(0.5, f))}
                for f in (5000, 200, 5500, 250)]
        self.assertEqual(label_speakers(segs)[0], "S1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laos.speaker'`

- [ ] **Step 3: 写最小实现**

创建 `laos/speaker.py`：

```python
"""speaker —— 到达顺序说话人聚类（纯 stdlib，不建声纹库）。

journal 现在分不清"我说的/别人说的"（README 缺口 #1）。这里只做一次
批处理内的会话级切分：拿 soundscape 的 7 带谱质心当"声纹的粗代理"，
贪心按到达顺序聚类——同一批音频里谱形近的归同一人，标签 S1/S2… 是
序号而非身份，函数结束质心即弃，绝不落盘（PIPL 声纹=敏感个人信息）。

跨天"同一人=同一日记主人"是调研 §2 明确列出的开放问题，本模块不实现、
不预留持久结构。方法论对标 Streaming Sortformer 的 AOSC（到达顺序=身份）。
"""

from __future__ import annotations

import math

from laos.soundscape import BANDS, describe


def bands_of(pcm16: bytes) -> dict[int, float]:
    return describe(pcm16)["bands_db"]


def to_centroid(bands_db: dict[int, float]) -> dict[int, float]:
    """dB 带谱 → softmax 归一化质心（分量 ∈ [0,1]，跨响度可比）。"""
    vals = [bands_db.get(b, -120.0) for b in BANDS]
    m = max(vals)
    exps = [math.exp((v - m)) for v in vals]
    s = sum(exps) or 1.0
    return {b: e / s for b, e in zip(BANDS, exps)}


def centroid_distance(a: dict[int, float], b: dict[int, float]) -> float:
    acc = 0.0
    for band in BANDS:
        d = a.get(band, 0.0) - b.get(band, 0.0)
        acc += d * d
    return math.sqrt(acc)


def label_speakers(segments: list[dict],
                   threshold: float = 0.15) -> list[str]:
    """到达顺序贪心聚类：segments[i] 含 "bands_db"；返回等长标签 ["S1",...]。"""
    centroids: list[dict[int, float]] = []
    out: list[str] = []
    for seg in segments:
        c = to_centroid(seg["bands_db"])
        best, best_d = -1, float("inf")
        for idx, existing in enumerate(centroids):
            d = centroid_distance(c, existing)
            if d < best_d:
                best, best_d = idx, d
        if best >= 0 and best_d <= threshold:
            out.append(f"S{best + 1}")
        else:
            centroids.append(c)
            out.append(f"S{len(centroids)}")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker -v`
Expected: PASS（5 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/speaker.py tests/test_speaker.py
git commit -m "feat(speaker): 到达顺序谱质心贪心聚类（纯 stdlib，不建声纹库）——A1"
```

### Task A2: journal 管线贴说话人标签（bin/journal.py）

**Files:**
- Modify: `bin/journal.py:29-95`（`run_pipeline` 主体）
- Test: `tests/test_journal.py`（追加用例，勿删既有）

**Interfaces:**
- Consumes: `laos.speaker.bands_of`、`laos.speaker.label_speakers`（A1 Produces）。
- Produces: `run_pipeline(..., speaker: bool = False)` 追加末位关键字参数，默认关闭保持既有行为字节不变；开启时 journal 记忆文本变为 `[HH:MM][S1] {transcript}`。

- [ ] **Step 1: 写失败测试（追加到 tests/test_journal.py 的 TestJournal 类内）**

```python
    def test_speaker_off_by_default_text_unchanged(self):
        # 现有断言的文本形如 "[HH:MM] ..."；speaker 默认 False 时不得掺入 [S]
        from pathlib import Path as _P
        import tempfile
        from laos.memory import MemoryStore
        from journal import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            wd = _P(d) / "rec-x.wav"
            self._write_sine_wav(wd, 1000)  # 既有测试若缺此辅助则一并补，见 Step 1b
            mem = MemoryStore(_P(d) / "mem.jsonl")
            res = run_pipeline(_P(d), mem, transcribe=lambda p: {"text": "你好", "emotions": ["NEUTRAL"]},
                               gc_keep_hours=None, spectral=False)
            rec = [r for r in mem.recall("你好", k=3) if r["kind"] == "journal"][0]
            self.assertNotIn("[S", rec["text"])
            self.assertTrue(rec["text"].startswith("["))

    def test_speaker_on_tags_arrival_order(self):
        from pathlib import Path as _P
        import tempfile
        from laos.memory import MemoryStore
        from journal import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            self._write_sine_wav(_P(d) / "rec-1.wav", 200)
            self._write_sine_wav(_P(d) / "rec-2.wav", 5000)
            mem = MemoryStore(_P(d) / "mem.jsonl")
            run_pipeline(_P(d), mem,
                         transcribe=lambda p: {"text": "喂", "emotions": ["NEUTRAL"]},
                         gc_keep_hours=None, spectral=False, speaker=True)
            texts = [r["text"] for r in mem.recall("喂", k=5) if r["kind"] == "journal"]
            joined = "".join(texts)
            self.assertIn("[S1]", joined)
            self.assertIn("[S2]", joined)
```

Step 1b：若 `tests/test_journal.py` 尚无写正弦 wav 的辅助，在测试类内补：

```python
    @staticmethod
    def _write_sine_wav(path, freq, seconds=0.6, sr=16000):
        import array, math, wave
        n = int(seconds * sr)
        a = array.array("h", (int(0.4 * 32767 * math.sin(2 * math.pi * freq * i / sr))
                               for i in range(n)))
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(a.tobytes())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_journal.TestJournal.test_speaker_on_tags_arrival_order -v`
Expected: FAIL — `TypeError: run_pipeline() got an unexpected keyword argument 'speaker'`

- [ ] **Step 3: 改实现**

在 `bin/journal.py` 的 `run_pipeline` 签名（当前 journal.py:29-31）末尾加 `speaker: bool = False`。把逐段循环改为"先收集、后统一贴标"：在循环前初始化 `_pending: list[tuple[Path, dict, str]] = []`，循环内（journal.py:53-77 现逐段 remember 处）当 `speaker=False` 保持原逻辑逐段 `memory.remember(kind="journal", text=f"[{hour_min}] {item.get('text','')}")`；当 `speaker=True` 时改为把 `(wav, item, hour_min)` 追加进 `_pending` 不立即入库。循环结束后：

```python
    if speaker and _pending:
        from laos.speaker import bands_of, label_speakers
        segs = [{"bands_db": bands_of(wav.read_bytes())} for wav, _item, _hm in _pending]
        labels = label_speakers(segs)
        for (wav, item, hour_min), lab in zip(_pending, labels):
            memory.remember(kind="journal",
                            text=f"[{hour_min}][{lab}] {item.get('text', '')}",
                            tags=[(item.get("emotions") or ["NEUTRAL"])[0] or "NEUTRAL",
                                  f"speaker:{lab}"])
```

`main()`（journal.py:98-134）加 argparse：`ap.add_argument("--speaker", action="store_true", help="按到达顺序贴说话人标签（会话内，不建声纹库）")`，并把 `run_pipeline(...)` 调用改为 `run_pipeline(..., speaker=args.speaker)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_journal -v`
Expected: PASS（含既有全部 + 2 新用例；既有 speaker 无关断言不受影响因默认 False）

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add bin/journal.py tests/test_journal.py
git commit -m "feat(journal): --speaker 到达顺序贴 [S1]/[S2] 标签（默认关，行为兼容）——A2"
```

### Task A3: 日记第六章按说话人聚合 + 文档同步（bin/diary.py + README）

**Files:**
- Modify: `bin/diary.py`（第六章渲染函数；先读现有 `build_diary` 定位 rhythm/soundscape 段）
- Modify: `README.md:311`（缺口 #1 状态从"未做"改为"会话内已做，跨会话列为 open problem"）
- Test: `tests/test_diary.py`（若无则建）

**Interfaces:**
- Consumes: A2 写入的 `tags` 含 `speaker:S1`；记忆文本含 `[S1]`。
- Produces: `build_diary` 输出的"今天听到的人"小节，统计各 `speaker:S*` 标签计数（仅会话内序号，无跨会话身份）。

- [ ] **Step 1: 先读现有 diary 第六章实现再动手**

Run: `C:/Users/yaoyue/miniconda3/python.exe -X utf8 -c "import sys;sys.stdout.reconfigure(encoding='utf-8');print(open(r'bin/diary.py',encoding='utf-8').read())" | grep -n "第六\|节律\|声景\|SECTION_TITLES\|def build_diary\|speaker"`
Expected: 定位到 `build_diary` 第六章段落与 `SECTION_TITLES`，确认追加小节不破坏 6 章契约。

- [ ] **Step 2: 写失败测试**

创建/追加 `tests/test_diary.py`：

```python
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "bin"))
from laos.memory import MemoryStore  # noqa: E402
from diary import build_diary  # noqa: E402


class TestDiarySpeaker(unittest.TestCase):
    def test_diary_counts_speakers(self):
        with tempfile.TemporaryDirectory() as d:
            mem = MemoryStore(Path(d) / "mem.jsonl")
            mem.remember("journal", "[09:00][S1] 早", tags=["NEUTRAL", "speaker:S1"])
            mem.remember("journal", "[09:05][S1] 好", tags=["NEUTRAL", "speaker:S1"])
            mem.remember("journal", "[10:00][S2] 嗨", tags=["NEUTRAL", "speaker:S2"])
            md = build_diary("1970-01-01", [], mem, diary_dir=Path(d))
            text = (Path(d) / "diary" / "1970-01-01.md").read_text(encoding="utf-8") \
                if (Path(d) / "diary" / "1970-01-01.md").exists() else md
            self.assertIn("S1", str(text))
            self.assertIn("2", str(text))  # S1 出现 2 次
```

- [ ] **Step 3: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_diary -v`
Expected: FAIL（第六章尚无 speaker 统计，断言 `assertIn("S1", ...)` 不成立）

- [ ] **Step 4: 改实现**

在 `build_diary` 第六章末尾追加"今天听到的人"小节：遍历 `mem` 当日 `kind=="journal"` 记录，从 `tags` 里取 `speaker:S*` 计数，渲染 `S1×2 · S2×1`。若 `build_diary` 无 `diary_dir` 参数则按 Step 1 读到的实际签名调整测试调用以匹配（**不新增 diary→speaker 的磁盘身份**，只做当日聚合）。

- [ ] **Step 5: 跑测试确认通过 + 改 README 缺口行**

`README.md:311` 缺口 #1 文本改为：`**说话人分离（diarization）**——journal 已支持会话内到达顺序标签（--speaker，S1/S2…，不建声纹库）；跨会话"同一人"关联是调研 §2 开放问题，仍未解`

- [ ] **Step 6: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add bin/diary.py tests/test_diary.py README.md
git commit -m "feat(diary): 第六章按 speaker 标签聚合+README 缺口#1 状态更新——A3"
```

> **Section A 说话人标签 · 外部模型评估（两则附录 + 一个内核接缝 Task）**：以下附录记录用户点名评估外部模型的两轮结论——评估一（分离，不并入）、评估二（diarization，作驱动侧可选后端 + 交付 Task A4 内核归一接缝）。

### 附录 A·评估一 —— 外部模型 `iic/FLASepformer-JAEC` 能否并入 Task A（2026-10-12）

**用户点名评估的意图**：Task A 目前是纯 stdlib 的"谱质心到达顺序贪心聚类"，用户希望用更强的专用模型替代或增强。经查证 ModelScope 集合 `iic/FLASepformer-JAEC` 与其论文（arXiv:2508.19528，Interspeech 2025）。

**结论（先说裁决）**：**不并入 Task A**——它解的是另一个问题，且撞四条本仓红线。正确归位是把它记为一个**许可证门槛未过、只能 opt-in 的驱动侧前置能力**（驱动本体已存在且带 venv 门控测试，缺的是默认链路接线与许可证放行，见下"归位"），而非改写 Task A1–A3。

**事实核对（模型到底做什么）**：
- FLASepformer 是**单声道语音分离（speech separation / 鸡尾酒会解混）**：输入 8kHz 两人重叠混音，输出**两路分离后波形**；**不产出任何说话人身份/序号标签**。这与 Task A 的需求（"谁在说"的会话内 S1/S2 标签，即 diarization 语义）是两个任务——分离给 ASR 喂干净单说话人音频，diarization 给文本贴"哪段属于谁"。
- 集合里的 JAEC 是**声学回声消除（AEC）前端**（16kHz，实时通话用），面向双端有远端参考信号的场景；全天候 lifelog 采集没有远端参考可消，与本漏斗正交，同样不服务于 Task A。
- 跑法：ModelScope/PyTorch pipeline 或 ONNX；论文口径 GPU 推理，ModelScope 卡另标 CPU/ONNX 可跑；**长音频支持但非流式**（non-streaming）。

**模型身份与论文级指标（2026-10-12 复核补全）**：
- **FLASepformer**（论文 arXiv:2508.19528，Interspeech 2025）：把 SepReformer / TF-Locoformer 的全局注意力换成门控聚焦线性注意力（Gated FLA），复杂度 O(N²)→O(N)；A800 上 30s 混音推理比 SepReformer 基线快 1.49–2.29×，显存占用降至基线 15.8%–31.9%。本仓驱动实际加载的 checkpoint 是 `iic/speech_flatsepreformer_separation_temporal_8k_base_libri2mix100`（FLA-SepReformer-B，14.2M 参数，Libri2Mix train-100 约 29h 训练，8kHz full-overlap min 干净混音）：Libri2Mix-100 测试 **SI-SNRi 20.3 dB / SDRi 20.7 dB**（同权重换 WSJ0-2Mix 基准为 23.5/23.7 dB）。另有第二个真实 checkpoint `damo/speech_flatflocoformer_separation_timefrequency_8k_middle_libri2mix360`（FLA-TFLocoformer-M，15.1M，Libri2Mix-360：22.2/22.4 dB）——同为 CC BY-NC 4.0，**换 checkpoint 不换许可证**。
- **JAEC**（`iic/speech_jaec_aec_16k`）：16kHz，需**等长**单声道 PCM16 的 nearend_mic/farend_speech 对；每次调用处理 160 采样点（10ms），输出相对 mic 输入带**固定 352 采样点（22ms）算法延迟**；两段式结构（神经时延估计 TDE + 线性滤波 LP），**不含非线性抑制级**（喇叭破音类非线性失真不处理）；权重仅一个 105,216 字节的 `tde_lp.bin`，配原生库 `jaec_arm.so` / `jaec_x86.so` / `jaec_x86.dll`（`trust_native_code=True`）；要求 ModelScope > 1.39.1（本机 `.venv-audio` 为 2.0.0+main，满足）；CPU 实时率 RTF 0.0020–0.0039（Apple M4 / Intel Xeon / Core Ultra 9 185H，10 次中位数）——**CPU 即可实时，无需 GPU**。
- **许可证不对称（同一个集合，两种商用资格）**：FLASepformer 模型卡明示 **CC BY-NC 4.0**，且原文写"本模型仅限非商业学术研究用途，严禁商用"；JAEC 据第三方拆解转述模型卡为 **Apache-2.0**（单一来源，拉取权重时须二次确认）。即：分离模型带商用禁区，回声模型不带——但 JAEC 要 farend 参考，lifelog 常驻采集场景没有，**商用资格与本漏斗无关**。

**本仓落地现状（本次复核的关键增量：两模型早已是 syscall，不是"将来可选"）**：
- `drivers/drv_audio.py` 已把二者封装为 `audio.separate`（FLASepformer：8kHz 单声道混音 → `_spk1.wav`/`_spk2.wav` 两路）与 `audio.aec`（JAEC：等长 mic/farend → `_aec.wav`），另有 `audio.models` 报告加载状态；模型**惰性加载**（首次调用才下载/初始化），laos 核心零依赖承诺不破坏。
- `bin/laosd.py:161` 加载该驱动；`bin/laosd.py:340` 演示段（§4.7）合成 8kHz 双音混音实调 `audio.separate`；`tests/test_audio_driver.py` 有真实推理用例（`@unittest.skipUnless(.venv-audio 存在)` 门控，缺 venv 时走"报错不崩"的优雅降级用例）——本机 `.venv-audio` 已部署（modelscope 2.0.0+main / torch 2.14.0+cpu），真实推理测试可跑。zone 树 AlwaysOnRec-Trae / ZCode 各有同构副本。
- **边界澄清（驱动存在 ≠ 可进产品默认链路）**：CC BY-NC 4.0 的禁区管"进入商用产品链路"。故本附录结论精确化为：Task A1–A3 不动（纯 stdlib 默认路径）；`audio.separate`/`audio.aec` 维持 opt-in syscall 现状——**不进 journal 默认漏斗、不进常驻检测流、不进任何默认开启的链路**；若要进默认链路，前置条件是换宽松许可权重或拿到商用授权。原"挂载点拟名 drv_sep"草记据此作废（见下归位）。

**四条硬约束冲突（逐条给证据）**：
1. **零依赖红线**：分离模型是 PyTorch/asteroid 级重依赖，按 AGENTS.md「`laos/` 核心纯 stdlib」「重依赖只进驱动子进程」——它**进不了 `laos/speaker.py`**，只能在驱动子进程侧。故它天生不是 Task A1（内核侧纯函数）的实现物。
2. **conda 红线**：禁止 `pip install` 进 `miniconda3` 主环境；模型权重与 torch 只能落 `.venv-audio` 驱动 venv——再次印证它属驱动侧，不属内核 Task A。
3. **采样率/流式不匹配**：模型 8kHz 非流式，而本漏斗是 16kHz 流式 VAD（`laos/vad.py`）+ SenseVoice 16k ASR。并入需在驱动侧做 16k→8k 重采样、且只能**批处理**（journal 离线阶段），不能进常驻检测流。
4. **许可证（最硬）**：ModelScope 卡标 **CC BY-NC 4.0（仅非商用）**。本仓有 funding deck / 开源对外定位（README/PROJECT_OVERVIEW/docs/ppt/funding），商用叙事与该许可证直接冲突。**在未换成宽松许可权重前，任何进产品链路的用法都不成立**——这也是本附录不把它写成带 commit 的编号 TDD Task 的原因（写进去即违反 writing-plans「无占位符/不写装不上也测不了的外部依赖 Task」纪律）。

**归位（若将来要用，正确的挂载点）**：把它记成**可选、默认关、批处理、驱动侧**的"重叠语音分离前置级"，作用是**提升重叠段的 ASR 转写质量**（把两人混音拆成两路各送 drv_ear），**不是**获得说话人身份。契约草记（默认链路门槛未过故不接线；驱动侧已存在的 `audio.separate` 及其 venv 门控测试维持原状，本波不新写其 TDD Task）：

```
# 仅在满足全部前置后，才升级为编号 Task（届时按 TDD 补失败测试）：
#   前置①：找到与 CC BY-NC 4.0 兼容商用 或 换宽松许可的分离权重
#   前置②：权重/推理代码只进 drivers/.venv-audio，主套件 import 不触它
#   前置③：默认 LAOS_SEP=0 关闭；开启仅在 journal 离线批处理阶段生效
#   前置④：隐私沿用 A 红线——分离只出音频流，绝不落"可跨会话识别个体"的声纹
# 挂载点：已存在——drivers/drv_audio.py 的 audio.separate（2026-10-12 复核确认），无需新建 drv_sep
#   待接线部分：16k→8k 重采样进、分离、8k→16k 出，两路分别转写再按到达顺序合标 S1/S2
#   （audio.separate 输出为 8k wav，drv_ear/SenseVoice 为 16k 链路，需驱动侧重采样桥接）
#   与 Task A 的关系：A 的聚类负责"贴标签"，本层负责"让每路更干净好转写"——正交互补，不互相替代
```

**与 Task A 的最终关系（一句话）**：Task A1–A3 维持纯 stdlib 不动；FLASepformer-JAEC 是"重叠语音分离"这条**独立、滞后、许可证门槛**的能力，驱动本体（`audio.separate`/`audio.aec`）已存在且维持 opt-in 现状，归驱动侧 ASR 增强，**不解决也不改变** diarization 的会话内标签语义与不建声纹库红线。

---

### 附录 A·评估二 —— Diarization 专用模型能否升级 Task A（2026-10-12）

**定位纠偏（与评估一相对）**：评估一的 FLASepformer 解"分离"（把重叠混音拆成两路干净波形，**不出标签**）；本评估一对齐 Task A 真正需求——**diarization（谁在何时说）**。查证三个主流开源 diarization 候选，**结论：diarization 家族确实对口，可作为 Task A 的"驱动侧可选增强后端"，但 `laos/speaker.py` 的纯 stdlib 聚类必须保留为零依赖默认/兜底——模型只进驱动子进程 `.venv-audio`，绝不进核心（AGENTS.md 零依赖/conda 红线）。**

**三候选横评（对照本仓红线）**：

| 维度 | NeMo **Streaming Sortformer** `4spk-v2` | 阿里 **3D-Speaker / CAM++**（ModelScope/FunASR） | **pyannote.audio 3.1** |
|---|---|---|---|
| 任务匹配 | **端到端直接出帧级说话人标签**（无需自建聚类） | VAD+声纹嵌入+谱聚类（需自己排到达顺序） | segmentation+嵌入+聚类流水线 |
| 到达顺序=身份 | **原生 AOSC 机制**（论文核心卖点即"arrival-time ordering"）——**正是 Task A1 docstring 已点名对标的方法论**（`laos/speaker.py:144`） | 需后处理按首现重排 | 需后处理按首现重排 |
| 许可证（商用兼容） | 代码 Apache-2.0；权重 **NVIDIA Open Model License**（可商用、无营收门槛——2026-10-12 复核纠正：原记"CC-BY-4.0"有误，那只是第三方 CoreML 转换仓的自选许可；NVIDIA 模型卡明示 governed by the NVIDIA Open Model License Agreement）✅ | **Apache-2.0**（最干净，可商用）✅ | 代码 MIT；**3.1 权重 gated**（须接受用户条款 + HF token，接入有摩擦）；新 Community-1 更开放 |
| 流式/采样率 | **流式**、16kHz——契合漏斗常驻检测语义 ✅ | 批处理、16kHz（journal 离线阶段可用） | 批处理、16kHz |
| 算力 | NeMo 口径 **GPU 为主**；社区已有 ExecuTorch/xnnpack **CPU** 移植（附 AMI DER 实测）与 CoreML ANE 移植——CPU 可跑，但体量仍超标 | CAM++ 轻量，**CPU 友好** | GPU/CPU 皆可（VRAM 6–8GB 参考） |
| 隐私红线适配 | **不建跨会话声纹库天然达成**（会话内标签，不产持久向量）✅ | 需保证嵌入用完即弃、不落盘（本波已如此约束） | 同 CAM++ |
| **体量（本波新增硬判据）** | **117M 参数**（4spk-v2.1 口径，三源证实）：gguf F32 **471MB** / F16 **237MB** / Q8_0 **139MB**（transcribe.cpp 实测口径），CoreML fp16 ~230MB——**全部 >100MB，超 ~50MB 上限** ❌ | CAM++ 编码 **7.2M 参数**（D-TDNN+上下文掩码，arXiv:2303.00332 系，三源证实 7.18–7.2M）：fp32 ≈29MB（参数推衍；ModelScope 卡 JS 渲染未取到实测值，拉取时实测补报），int8 ONNX 更小——**体量达标** ✅ | segmentation-3.0（1.5M，PyanNet SincNet+BiLSTM）+ 嵌入 WeSpeaker ResNet34 **6.6M / ONNX 28MB（fp16 tflite 13.4MB）**，合计数十 MB——**大体达标**（嵌入 fp16 后仅 13.4MB） |
| 依赖体量 | NeMo+PyTorch，**重** | 中（可 ONNX 化） | 中（pyannote.audio 3.x） |

**裁决（推荐排序 · 已按体量红线重排）**：体量是内核/手机端常驻链路的硬约束，故按"进哪条路径"分两档，而非单一首选：
1. **常驻/热路径可选后端首选 = 3D-Speaker / CAM++**：**体量达标（7.2M 参数，fp32 ≈29MB 参数推衍、int8 更小，拉取时实测补报）+ Apache-2.0（最干净）+ CPU 友好 + 国产 ModelScope 原生**——四项同时满足本波体量红线与许可要求，是唯一可考虑挂进常驻/近常驻链路的候选。代价：需补"按首现重排标签"一步（Task A4 即把该重排收敛成内核纯函数）。
2. **离线/桌面后处理档 = Streaming Sortformer**：概念最贴合（AOSC=到达顺序=身份，正是 `speaker.py:144` 对标方法论）、流式、权重 NVIDIA Open Model License 可商用，但 **117M 参数 / fp32 ~471MB · fp16 ~237MB · Q8_0 ~139MB（transcribe.cpp 实测口径）/ GPU 为主 → 触体量红线，禁入手机常驻链路**；只作 journal `--diar` 的**桌面批处理后处理**可选档（拉取时须实测磁盘 MB + 峰值 RAM 再决定）。
3. **不推荐进产品链路 = pyannote 3.1**：3.1 权重 gated + 需 HF token 接受条款，接入摩擦与可复现性差；Community-1 若许可稳定可复议。
- **许可证与体量一律在拉取权重时二次确认**（卡片口径随版本变；MB 以实测为准，不用宣称值）。

**正确的升级姿势（不改红线、不改核心零依赖承诺）**：内核 `laos/speaker.py` 继续做**默认**（无模型/离线兜底）；diarization 模型作为 `drivers/drv_ear.py` 侧（或新 `drv_diar.py`）的**可选后端**，产出会话内到达顺序标签后，经下面 Task A4 的归一化函数回灌 journal，标签契约与 A1 完全一致（仍是 `S1/S2…`，不建声纹库）。Task A4 提供这个跨后端归一的**内核侧纯 stdlib 函数**（零依赖、可单测），是模型并入的唯一合法接缝。

### Task A4: diarization 后端标签归一（laos/speaker.py 扩展 · 模型接入的唯一内核接缝）

**Files:**
- Modify: `laos/speaker.py`（追加 `normalize_arrival_labels`）
- Test: `tests/test_speaker.py`（追加用例）

**Interfaces:**
- Consumes: 驱动侧 diarization 后端产出的、随段落顺序排列的**原始说话人 id 序列** `raw_ids: list[str]`（同一物理说话人在整段内必须给同一 raw id；后端可以是 Sortformer 帧标签投票后的段级 id、CAM++ 聚类簇号、或 A1 的 `label_speakers` 自身输出）。
- Produces: `normalize_arrival_labels(raw_ids: list[str]) -> list[str]` —— 按**首次出现顺序**把任意 raw id 重映射为 `S1/S2…`（到达顺序=身份），与 `label_speakers` 输出同型同义；空输入 → `[]`。**这是内核侧唯一被模型消费的入口**，模型侧改动不触碰 `laos/` 其余部分。

- [ ] **Step 1: 追加失败测试**

在 `tests/test_speaker.py` 的 `class TestSpeaker` 内追加：

```python
    def test_normalize_arrival_labels_maps_by_first_seen(self):
        # 模拟 CAM++ 簇号乱序/任意命名：按首次出现重排为 S1/S2/S3
        self.assertEqual(
            normalize_arrival_labels(["spk_7", "a", "spk_7", "z", "a", "spk_7"]),
            ["S1", "S2", "S1", "S3", "S2", "S1"])

    def test_normalize_arrival_labels_empty(self):
        self.assertEqual(normalize_arrival_labels([]), [])

    def test_normalize_arrival_labels_matches_label_speakers_shape(self):
        # 与 A1 贪心聚类输出同型：等长、首元素恒 S1、只用 S<n>
        raw = ["x", "y", "x", "y"]
        out = normalize_arrival_labels(raw)
        self.assertEqual(out, ["S1", "S2", "S1", "S2"])
        self.assertEqual(out[0], "S1")
```

并在文件顶部 import 行补 `normalize_arrival_labels`：

```python
from laos.speaker import (bands_of, centroid_distance, label_speakers,
                          normalize_arrival_labels, to_centroid)  # noqa: E402
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker -v`
Expected: FAIL — `ImportError: cannot import name 'normalize_arrival_labels'`

- [ ] **Step 3: 写最小实现**

在 `laos/speaker.py` 末尾追加（纯 stdlib，无新 import）：

```python
def normalize_arrival_labels(raw_ids: list[str]) -> list[str]:
    """把任意 diarization 后端的段级说话人 id 按到达顺序重映射为 S1/S2…。

    内核侧唯一被模型消费的接缝：模型（Sortformer/CAM++）或 A1 贪心聚类产出
    的原始 id 序列，在此统一成会话内序号标签——不建声纹库、不落盘，与
    label_speakers 同型同义。空输入返回 []。
    """
    remap: dict[str, int] = {}
    out: list[str] = []
    for rid in raw_ids:
        if rid not in remap:
            remap[rid] = len(remap) + 1
        out.append(f"S{remap[rid]}")
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker -v`
Expected: PASS（含 A1 原 5 例 + 本 Task 3 例 = 8 tests）

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add laos/speaker.py tests/test_speaker.py
git commit -m "feat(speaker): normalize_arrival_labels 到达顺序归一——diarization 后端唯一内核接缝（A4）"
```

> **模型接入边界（务必遵守，勿在本波越界）**：Sortformer/CAM++ 的权重下载、torch/NeMo 安装、GPU 探测**全部只发生在驱动子进程 `.venv-audio`**（如新 `drivers/drv_diar.py` 或 drv_ear 的可选工具），产出的段级 raw id 序列经 `normalize_arrival_labels` 回灌 `bin/journal.py`。**主测试套件不 import 任何模型依赖**；`laos/` 核心保持零依赖；`speaker.py` 的 `label_speakers` 仍是无模型时的默认路径。**体量闸门（本波新增）**：驱动后端挂载前必须实测并报"磁盘 MB + 峰值 RAM + CPU/GPU"三项——**≤ ~50MB 者才可评估进常驻/近常驻链路（CAM++ 档）**；**> 100MB / GPU 级（Sortformer 117M）只准挂 journal `--diar` 离线后处理，禁入手机常驻链路**。驱动侧模型的挂载（权重拉取/推理/降级/体量实测）属独立后续波，本波只交付这个可单测的内核归一接缝 + 评估裁决。

> **Section A 收尾**：可独立发版（走 AGENTS.md 发版纪律 `python scripts/release.py --apply`）。测试数以实跑为准记录。A4 属零依赖内核接缝，与 A1–A3 同波可交付；模型后端本身（drv_diar/Sortformer/CAM++）留下一波，不在本波发版口径内。

---

## Section B — 听觉缺页召回（laos/audiodream.py · 内核侧，零驱动改动）

**内核同构**：教训④"上下文是新的内存"（README §五）+ branch.py `first-commit-wins` 的软降级语义。音频即焚后，文本记忆仍在——`recall` 命中一条音频已焚的 journal 记忆时，不是报错而是"缺页→用文本摘要满足"，并在结果里标注 `audio_status="burned"`（音频页不在物理框）。**绝不复活字节**。

### Task B1: 缺页语义纯函数（laos/audiodream.py）

**Files:**
- Create: `laos/audiodream.py`
- Test: `tests/test_audiodream.py`

**Interfaces:**
- Consumes: journal 记忆 dict（含 `kind`/`text`/`ts`）；`laos.burnt`（Section D）若存在则读回执，否则回退到 `has_audio` 字段——本波 B/D 松耦合，audiodream **不强依赖 burnt**（无 burnt 时 `has_audio` 缺省视为 True）。
- Produces:
  - `is_burned(rec: dict) -> bool` —— `rec.get("has_audio", True) is False`。
  - `dream_recall(results: list[dict]) -> list[dict]` —— 给每条加 `audio_status`（`"live"` / `"burned"`）；burned 条目把 `text` 置空串（文本摘要由调用方从 `rec["text"]` 另取），返回浅拷贝列表。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_audiodream.py`：

```python
"""audiodream —— 即焚后记忆的缺页召回语义（纯 stdlib，不复活字节）。

    python -m unittest tests.test_audiodream -v
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from laos.audiodream import dream_recall, is_burned  # noqa: E402


class TestAudiodream(unittest.TestCase):
    def test_default_has_audio_is_live(self):
        self.assertFalse(is_burned({"kind": "journal", "text": "x", "ts": 0.0}))

    def test_explicit_burned(self):
        self.assertTrue(is_burned({"has_audio": False, "text": "x"}))

    def test_dream_recall_marks_status(self):
        out = dream_recall([
            {"kind": "journal", "text": "你好", "ts": 1.0},
            {"kind": "journal", "text": "再见", "ts": 2.0, "has_audio": False},
        ])
        self.assertEqual(out[0]["audio_status"], "live")
        self.assertEqual(out[1]["audio_status"], "burned")
        self.assertEqual(out[1]["text"], "")       # 字节不复活
        self.assertEqual(out[1]["dream_text"], "再见")  # 文本另存供摘要

    def test_dream_recall_non_journal_untouched(self):
        out = dream_recall([{"kind": "soundscape", "text": "14时", "ts": 1.0}])
        self.assertNotIn("audio_status", out[0])

    def test_dream_recall_is_shallow_copy_input_mutated_no(self):
        src = [{"kind": "journal", "text": "x", "ts": 1.0, "has_audio": False}]
        dream_recall(src)
        self.assertEqual(src[0]["text"], "x")       # 原列表不被就地改写


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_audiodream -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laos.audiodream'`

- [ ] **Step 3: 写最小实现**

创建 `laos/audiodream.py`：

```python
"""audiodream —— 即焚后听觉记忆的缺页召回语义（纯 stdlib）。

上下文是新的内存（README 教训④）：音频段即焚后，物理"页"（wav 字节）已
换出且不可逆回收，但文本记忆这条"页表项"还在。recall 命中已焚段时，
不报 ENOENT，而是用文本满足——标 audio_status="burned"，字节绝不复活。
对标 branch.py first-commit-wins：请求落空时软降级而非硬失败。
"""

from __future__ import annotations

_JOURNAL_KINDS = frozenset({"journal"})


def is_burned(rec: dict) -> bool:
    """has_audio 缺省视为 True（Section D 回执缺席时的安全默认）。"""
    return rec.get("has_audio", True) is False


def dream_recall(results: list[dict]) -> list[dict]:
    out: list[dict] = []
    for rec in results:
        if rec.get("kind") not in _JOURNAL_KINDS:
            out.append(rec)
            continue
        row = dict(rec)
        if is_burned(rec):
            row["audio_status"] = "burned"
            row["dream_text"] = rec.get("text", "")
            row["text"] = ""
        else:
            row["audio_status"] = "live"
        out.append(row)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_audiodream -v`
Expected: PASS（5 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/audiodream.py tests/test_audiodream.py
git commit -m "feat(audiodream): 即焚后记忆缺页召回纯函数（live/burned 软降级）——B1"
```

### Task B2: journal 记忆落 has_audio + 内核 mem.recall 接 dream_recall

**Files:**
- Modify: `bin/journal.py:62-77`（remember 处传入 `has_audio`）与 `main()`（gc 后回填 False）
- Modify: `laos/kernel.py:413`（`mem.recall` 内建对结果套 `dream_recall`）
- Test: `tests/test_audiodream.py`（追加集成用例）+ `tests/test_kernel_mem.py`（若存在则追加，否则并入 audiodream 集成）

**Interfaces:**
- Consumes: `laos.audiodream.dream_recall`（B1 Produces）。
- Produces: journal 记忆在 gc 删除音频后，其 `has_audio` 被置 `False`；`mem.recall` 返回条目携带 `audio_status`。

- [ ] **Step 1: 写失败集成测试（追加到 tests/test_audiodream.py）**

```python
class TestJournalBurned(unittest.TestCase):
    def test_journal_remembers_with_has_audio(self):
        import tempfile
        from pathlib import Path as _P
        from laos.memory import MemoryStore
        from journal import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            wd = _P(d) / "rec-a.wav"
            import array, math, wave
            n = int(0.6 * 16000)
            a = array.array("h", (int(0.4 * 32767 * math.sin(2*math.pi*1000*i/16000)) for i in range(n)))
            with wave.open(str(wd), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(a.tobytes())
            mem = MemoryStore(_P(d) / "mem.jsonl")
            run_pipeline(_P(d), mem, transcribe=lambda p: {"text": "喂", "emotions": ["NEUTRAL"]},
                         gc_keep_hours=0, spectral=False)  # 立即即焚
            rec = [r for r in mem.recall("喂", k=3) if r["kind"] == "journal"][0]
            self.assertFalse(rec.get("has_audio", True))  # 焚后置 False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_audiodream.TestJournalBurned -v`
Expected: FAIL — 断言不成立（现 remember 无 has_audio，默认 True）

- [ ] **Step 3: 改实现（journal gc 回填 has_audio）**

在 `bin/journal.py` gc 块（当前 journal.py:87-92）里，删除每个 wav 前，先把对应该段的 journal 记忆 `has_audio` 置 False。因 MemoryStore 无按字段更新接口，采用"记住本批入库的 id 列表 + gc 命中时 forget 旧行并 remember 同文本+has_audio=False 新行"过重；**改用轻量方案**：remember 时不写 has_audio（默认 live），gc 删除 wav 后，收集被删 wav 的 `[HH:MM]` 时刻集合，`memory` 侧提供一个新增最小接口。为守 DRY 与本波范围，采用最小可行：在 `run_pipeline` 内维护 `id_by_wav: dict[str, int]`（remember 返回 rec 的 id），gc 删除后调用 `memory.mark_burned(id)`。

先在 `laos/memory.py` 增 `mark_burned`（**注意**：这是对 memory.py 的唯一新增，追加在 `forget` 之后）：

```python
    def mark_burned(self, mid: int) -> bool:
        """把某条记忆音频标记为已焚（缺页召回用）；不改文本，仅追加 has_audio=False。"""
        with self._lock:
            for rec in self._records:
                if rec.get("id") == mid:
                    rec["has_audio"] = False
                    self._rewrite()
                    return True
            return False
```

`bin/journal.py`：remember 返回的 rec 存 `id_by_wav[wav.name] = rec["id"]`（A2 已把 remember 结果可用；对 speaker on/off 两条分支都要记 id）；gc 循环（journal.py:90-92）删除时 `if wav.name in id_by_wav: memory.mark_burned(id_by_wav[wav.name])`。

内核 `laos/kernel.py` 的 `mem.recall` 内建（`_impl_mem_recall`，注册于 kernel.py:413）：在返回前对结果列表套 `from .audiodream import dream_recall; rows = dream_recall(rows)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_audiodream tests.test_journal -v`
Expected: PASS

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add laos/memory.py laos/kernel.py bin/journal.py tests/test_audiodream.py
git commit -m "feat(memory): mark_burned + mem.recall 接缺页召回（has_audio 即焚回填）——B2"
```

> **Section B 收尾**：与 D 松耦合，可独立发版。

---

## Section C — 声景驱动调度（laos/duty.py 内核侧 + drv_rec 挂钩）

**内核同构**：进程按负载调度 CPU，听觉链路按**声景负载**调度捕获灵敏度。安静时段提高 VAD 阈值（更少误启、省电），嘈杂/活跃时段降低阈值（不漏人声）。输入是聚合声景特征（LUFS），输出是**下一捕获段** `rec_start(threshold_dbfs=...)` 的偏移。只调灵敏度，不改"显式 syscall 才录"红线。

### Task C1: 声景→阈值偏移策略（laos/duty.py）

**Files:**
- Create: `laos/duty.py`
- Test: `tests/test_duty.py`

**Interfaces:**
- Consumes: `laos.soundscape.aggregate(feats) -> dict`（含 `lufs`，soundscape.py:79）；即 `describe`/`aggregate` 产出的 dict。
- Produces:
  - `BASE_THRESHOLD_DBFS = -35.0`（与 drv_rec.rec_start 默认一致，drv_rec.py:89）
  - `threshold_offset(lufs: float, *, quiet_dbfs: float = -30.0, loud_dbfs: float = -15.0) -> float` —— 很安静（lufs < quiet）返回正偏移（提阈值少录），很吵（lufs > loud）返回负偏移（降阈值多录），中间 0.0。
  - `compute_duty(aggregate_feats: dict, base_threshold: float = BASE_THRESHOLD_DBFS) -> dict` —— 返回 `{"threshold_dbfs": float, "mode": "quiet"|"normal"|"loud", "lufs": float}`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_duty.py`：

```python
"""duty —— 声景负载 → VAD 捕获阈值调度（纯 stdlib）。

    python -m unittest tests.test_duty -v
"""
from __future__ import annotations
import sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from laos.duty import BASE_THRESHOLD_DBFS, compute_duty, threshold_offset  # noqa: E402


class TestDuty(unittest.TestCase):
    def test_quiet_raises_threshold(self):
        self.assertGreater(threshold_offset(-45.0), 0.0)
        self.assertGreater(compute_duty({"lufs": -45.0})["threshold_dbfs"],
                           BASE_THRESHOLD_DBFS)

    def test_loud_lowers_threshold(self):
        self.assertLess(threshold_offset(-5.0), 0.0)
        self.assertLess(compute_duty({"lufs": -5.0})["threshold_dbfs"],
                        BASE_THRESHOLD_DBFS)

    def test_normal_band_is_base_and_zero_offset(self):
        self.assertEqual(threshold_offset(-20.0), 0.0)
        d = compute_duty({"lufs": -20.0})
        self.assertEqual(d["threshold_dbfs"], BASE_THRESHOLD_DBFS)
        self.assertEqual(d["mode"], "normal")

    def test_mode_labels(self):
        self.assertEqual(compute_duty({"lufs": -50.0})["mode"], "quiet")
        self.assertEqual(compute_duty({"lufs": -3.0})["mode"], "loud")

    def test_offset_is_capped(self):
        # 极端安静不得把阈值推到正数（封顶 +5 dB）
        self.assertLessEqual(threshold_offset(-120.0), 5.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_duty -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laos.duty'`

- [ ] **Step 3: 写最小实现**

创建 `laos/duty.py`：

```python
"""duty —— 声景负载驱动的捕获调度（纯 stdlib，内核侧策略）。

进程按 CPU 负载调度，听觉链路按"声景负载"调度捕获灵敏度（README 缺口
#2 记忆分层的近邻：把被动声景记忆反过来用作调控信号）。安静→提阈值少误启
（省电），嘈杂→降阈值不漏人声。只调 StreamingVAD 的 threshold，绝不改变
"录音只由显式 syscall 触发、LAOS_REC=0 全局禁录"红线（隐私红线优先）。
"""

from __future__ import annotations

BASE_THRESHOLD_DBFS = -35.0
_MAX_OFFSET_DBFS = 5.0


def threshold_offset(lufs: float, *, quiet_dbfs: float = -30.0,
                     loud_dbfs: float = -15.0) -> float:
    if lufs >= loud_dbfs:          # 吵：降阈值（负偏移）
        return max(-_MAX_OFFSET_DBFS, round((loud_dbfs - lufs) / 3.0, 1))
    if lufs <= quiet_dbfs:         # 静：提阈值（正偏移）
        return min(_MAX_OFFSET_DBFS, round((quiet_dbfs - lufs) / 3.0, 1))
    return 0.0                      # 中间带：不动


def compute_duty(aggregate_feats: dict,
                 base_threshold: float = BASE_THRESHOLD_DBFS) -> dict:
    lufs = float(aggregate_feats.get("lufs", BASE_THRESHOLD_DBFS))
    off = threshold_offset(lufs)
    mode = ("quiet" if lufs <= -30.0 else
            "loud" if lufs >= -15.0 else "normal")
    return {"threshold_dbfs": round(base_threshold + off, 1),
            "mode": mode, "lufs": lufs}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_duty -v`
Expected: PASS（5 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/duty.py tests/test_duty.py
git commit -m "feat(duty): 声景 LUFS → VAD 阈值偏移调度策略（纯 stdlib）——C1"
```

### Task C2: drv_rec 消费调度（挂钩 + 环境变量门控）

**Files:**
- Modify: `drivers/drv_rec.py:89-98`（`rec_start`）
- Test: `tests/test_rec.py`（追加）

**Interfaces:**
- Consumes: `laos.duty.compute_duty`（C1 Produces）。
- Produces: `rec_start` 新增可选关键字 `auto_duty: bool = False`；为 True 且 `LAOS_REC=1` 时读取最近一次声景聚合（由 journal 落盘的 `var/ear/duty.json`）套用调度阈值。

- [ ] **Step 1: 写失败测试（追加到 tests/test_rec.py）**

```python
    def test_auto_duty_reads_duty_json(self):
        import json, tempfile
        from pathlib import Path as _P
        import drv_rec
        with tempfile.TemporaryDirectory() as d:
            p = _P(d) / "duty.json"
            p.write_text(json.dumps({"threshold_dbfs": -38.0, "mode": "quiet"}),
                         encoding="utf-8")
            got = drv_rec._resolve_duty_threshold(p, default=-35.0)
            self.assertEqual(got, -38.0)

    def test_missing_duty_json_returns_default(self):
        import tempfile
        from pathlib import Path as _P
        import drv_rec
        with tempfile.TemporaryDirectory() as d:
            got = drv_rec._resolve_duty_threshold(_P(d) / "nope.json", default=-35.0)
            self.assertEqual(got, -35.0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_rec -v`
Expected: FAIL — `AttributeError: module 'drv_rec' has no attribute '_resolve_duty_threshold'`

- [ ] **Step 3: 改实现（drv_rec 挂钩）**

在 `drivers/drv_rec.py` 增纯函数（不触发录音，只解析 JSON）：

```python
def _resolve_duty_threshold(duty_path, default: float = -35.0) -> float:
    """读声景调度落盘的 duty.json 取 threshold_dbfs；缺文件/坏值回退 default。"""
    import json
    try:
        data = json.loads(_Path(duty_path).read_text(encoding="utf-8"))
        v = float(data["threshold_dbfs"])
        return v
    except (OSError, ValueError, KeyError):
        return default
```

（`_Path` = drv_rec.py 现有 `from pathlib import Path`；若无则用 `Path`。）`rec_start`（drv_rec.py:89）签名加 `auto_duty: bool = False`，函数体首行：`if auto_duty: threshold_dbfs = _resolve_duty_threshold(_journal_dir().parent / "duty.json", threshold_dbfs)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_rec -v`
Expected: PASS

- [ ] **Step 5: journal 落 duty.json + 全量回归 + 提交**

`bin/journal.py` 声景聚合段（journal.py:80-85）后，把 `compute_duty(aggregate(...))` 结果写 `var/ear/duty.json`（`spectral and auto_duty_json` 门控，默认写；供 C2 读）。测试补一条：跑 pipeline 后 `duty.json` 存在且含 `threshold_dbfs`。

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add drivers/drv_rec.py bin/journal.py tests/test_rec.py
git commit -m "feat(drv_rec): rec_start auto_duty 读声景调度阈值+journal 落 duty.json——C2"
```

> **Section C 收尾**：真机省电收益需 §七 中期项"termux 真机矩阵"验证；本波只交付策略与挂钩（可单测、可回退 `auto_duty=False`）。

---

## Section D — 即焚销毁回执（laos/burnt.py + rec.gc/journal 挂钩 + burn.verify）

**内核同构**：审计要能回答 PIPL/EU AI Act 的"你能证明删了吗"。`rec_gc`/journal 现用裸 `p.unlink()`（drv_rec.py:164、journal.py:92）不留痕。改为删除前算 sha256（哈希算完即弃、只留哈希+元数据），落一份**销毁账** `var/ear/burnt.jsonl`；新增 `burn.verify(path)` 只读核验"该文件确实不存在且销毁账有对应记录"。回执**永不含音频内容或转写文本**。

### Task D1: 销毁回执核心模块（laos/burnt.py）

**Files:**
- Create: `laos/burnt.py`
- Test: `tests/test_burnt.py`

**Interfaces:**
- Produces:
  - `content_hash(data: bytes) -> str` —— sha256 hexdigest。
  - `record_burn(path: Path, data: bytes, *, keep: Path | None = None) -> dict` —— 算哈希、追加一行回执到 `burnt.jsonl`（keep 缺省用 `path.parent`），返回回执 dict `{sha256, file, bytes, t}`。
  - `load_receipts(burnt_path: Path) -> list[dict]`。
  - `verify_deletion(receipt: dict, search_dirs: list[Path]) -> bool` —— 该 `file` 在所有 search_dirs 下都不存在 **且** sha256 匹配回执 → True。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_burnt.py`：

```python
"""burnt —— 即焚销毁回执（sha256 单向，可审计"删了且删对"）。

    python -m unittest tests.test_burnt -v
"""
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from laos.burnt import (content_hash, load_receipts, record_burn,  # noqa: E402
                        verify_deletion)


class TestBurnt(unittest.TestCase):
    def test_hash_is_sha256_hex64(self):
        h = content_hash(b"audio-bytes")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_receipt_has_no_content(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec-1.wav"
            wav.write_bytes(b"secret-audio")
            rec = record_burn(wav, wav.read_bytes(), keep=Path(d))
            self.assertNotIn("secret-audio", str(rec))
            self.assertEqual(rec["file"], "rec-1.wav")
            self.assertEqual(rec["bytes"], len(b"secret-audio"))

    def test_verify_true_after_delete(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec-1.wav"
            wav.write_bytes(b"aaa")
            rec = record_burn(wav, wav.read_bytes(), keep=Path(d))
            wav.unlink()
            self.assertTrue(verify_deletion(rec, [Path(d)]))

    def test_verify_false_if_file_remains(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec-1.wav"
            wav.write_bytes(b"aaa")
            rec = record_burn(wav, wav.read_bytes(), keep=Path(d))
            self.assertFalse(verify_deletion(rec, [Path(d)]))

    def test_load_receipts_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "rec-1.wav"; wav.write_bytes(b"x")
            record_burn(wav, wav.read_bytes(), keep=Path(d))
            rows = load_receipts(Path(d) / "burnt.jsonl")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["file"], "rec-1.wav")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_burnt -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laos.burnt'`

- [ ] **Step 3: 写最小实现**

创建 `laos/burnt.py`：

```python
"""burnt —— 即焚销毁回执（纯 stdlib，隐私可审计化）。

rec_gc/journal 删原音频时不留痕，无法回应"你能证明删了吗"（PIPL/EU AI
Act）。删除前算一次 sha256（哈希算完即弃、不落原始字节），只把
{哈希, 文件名, 字节数, 时刻}追加进 burnt.jsonl 作销毁证。回执不含任何
音频内容或转写文本（哈希单向不可反推）。verify 核验"文件确已消失且账上有
对应哈希"。对标 OS unlink 记账 + 硬件 trustzone 的度量式证明。
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

RECEIPT_NAME = "burnt.jsonl"


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_burn(path: Path, data: bytes, *, keep: Path | None = None) -> dict:
    """算哈希→写回执→返回 dict；调用方随后 unlink path（哈希即弃不留原字节）。"""
    path = Path(path)
    base = Path(keep) if keep is not None else path.parent
    rec = {"sha256": content_hash(data), "file": path.name,
           "bytes": len(data), "t": time.time()}
    out = base / RECEIPT_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_receipts(burnt_path: Path) -> list[dict]:
    out: list[dict] = []
    p = Path(burnt_path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def verify_deletion(receipt: dict, search_dirs: list[Path]) -> bool:
    """回执所指文件在所有目录都不存在，且哈希字段完整 → 销毁可证明。"""
    name = receipt.get("file")
    if not name or not receipt.get("sha256"):
        return False
    for d in search_dirs:
        if (Path(d) / name).exists():
            return False
    return True
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_burnt -v`
Expected: PASS（6 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/burnt.py tests/test_burnt.py
git commit -m "feat(burnt): sha256 即焚销毁回执+verify_deletion（单向不含内容）——D1"
```

### Task D2: rec.gc / journal 删除前落回执 + 内核 burn.verify 只读内建

**Files:**
- Modify: `drivers/drv_rec.py:156-166`（`rec_gc`）
- Modify: `bin/journal.py:87-92`（gc 块）
- Modify: `laos/kernel.py`（`_builtin_impls` 注册 `burn.verify` + ToolSpec）
- Test: `tests/test_rec.py`（追加）+ `tests/test_burnt.py`（追加集成）

**Interfaces:**
- Consumes: `laos.burnt.record_burn`、`laos.burnt.verify_deletion`、`laos.burnt.load_receipts`（D1 Produces）。
- Produces: `rec_gc` 删除每段前 `record_burn`；内核内建 `burn.verify(file) -> {"deleted": bool, "receipt": dict|None}`。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_burnt.py`：

```python
class TestGcWritesReceipt(unittest.TestCase):
    def test_rec_gc_records_before_delete(self):
        import os, tempfile
        from pathlib import Path as _P
        os.environ["LAOS_JOURNAL_KEEP_H"] = "0"  # 立即即焚
        import drv_rec
        with tempfile.TemporaryDirectory() as d:
            drv_rec.set_output_dir(_P(d))
            wav = _P(d) / "rec-1.wav"; wav.write_bytes(b"audio")
            drv_rec.rec_gc(keep_hours=0)
            self.assertFalse(wav.exists())
            rows = load_receipts(_P(d) / "burnt.jsonl")
            self.assertTrue(any(r["file"] == "rec-1.wav" for r in rows))
            self.assertTrue(verify_deletion(rows[-1], [_P(d)]))
            drv_rec.set_output_dir(None)
        os.environ.pop("LAOS_JOURNAL_KEEP_H", None)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_burnt.TestGcWritesReceipt -v`
Expected: FAIL — burnt.jsonl 不存在（rec_gc 现裸 unlink）

- [ ] **Step 3: 改实现（rec_gc + journal gc 落回执）**

`drivers/drv_rec.py` `rec_gc`（drv_rec.py:156-166）循环体内，把 `p.unlink(missing_ok=True)` 改为先读字节算回执再删：

```python
    from laos.burnt import record_burn
    for p in _journal_dir().glob("rec-*.wav"):
        if p.stat().st_mtime < cutoff:
            try:
                record_burn(p, p.read_bytes(), keep=_journal_dir())
            except OSError:
                pass
            p.unlink(missing_ok=True)
            removed += 1
```

`bin/journal.py` gc 块（journal.py:90-92）同样在 `wav.unlink()` 前 `record_burn(wav, wav.read_bytes(), keep=Path(journal_dir))`（顶部 `from laos.burnt import record_burn` 局部导入）。

内核 `laos/kernel.py`：`_specs` 加 `"burn.verify": ToolSpec("burn.verify", "核验某已焚音频文件确实消失且销毁账有对应哈希（只读，无内容）", {"type":"object","properties":{"file":{"type":"string"}},"required":["file"]}, reversible=True, risk="low")`；`_builtin_impls` 加 `"burn.verify": self._impl_burn_verify`；实现：

```python
    def _impl_burn_verify(self, pcb, args):
        from .mcp import CallResult
        from .burnt import RECEIPT_NAME, load_receipts, verify_deletion
        import os
        journal_dir = Path(os.environ.get("LAOS_JOURNAL_DIR",
                          str(REPO / "var" / "ear" / "journal")))
        receipts = load_receipts(journal_dir / RECEIPT_NAME)
        want = args.get("file", "")
        rec = next((r for r in receipts if r.get("file") == want), None)
        deleted = bool(rec) and verify_deletion(rec, [journal_dir])
        return CallResult.ok_text(json.dumps(
            {"deleted": deleted, "receipt": rec}, ensure_ascii=False))
```

（`REPO`/`Path`/`json` 用 kernel.py 现有导入；确认顶部有 `from pathlib import Path` 与 `import json`。）

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_burnt tests.test_rec -v`
Expected: PASS

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add drivers/drv_rec.py bin/journal.py laos/kernel.py tests/test_burnt.py
git commit -m "feat(rec.gc): 即焚前落 sha256 销毁回执+内核 burn.verify 只读核验——D2"
```

> **Section D 收尾**：burnt.jsonl 是隐私合规审计物，纳入 `docs/releases/` 说明；与 B 的 `has_audio` 呼应（B2 的 gc 回填可后续迭代改为读 D 回执，本波保持松耦合不引入循环依赖）。

---

## 跨段集成校验（全部四段落地后，一次性）

- [ ] **Step 1: 全量实跑记录测试数**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `Ran N tests` + `OK (skipped=5)`（N = 基线 1146 + 本波新增，实跑为准）

- [ ] **Step 2: 零依赖自检**

Run: `C:/Users/yaoyue/miniconda3/python.exe -X utf8 -c "import ast,sys; [ast.parse(open(f,encoding='utf-8').read()) for f in ['laos/speaker.py','laos/audiodream.py','laos/duty.py','laos/burnt.py']]; print('AST ok')"`
Expected: `AST ok`；人工核四模块 import 仅 stdlib + 既有 laos 模块（无新第三方）。

- [ ] **Step 3: 隐私红线抽查**

`burnt.jsonl` 与 journal 记忆文本不得含音频字节/转写全文；`speaker` 标签不落质心向量。人工 grep `burnt.jsonl` 确认只有 sha256/file/bytes/t 四字段。

- [ ] **Step 4: 计划状态登记**

在 `docs/superpowers/plans/README.md` 表内登记本计划为 `待执行`（落点：laos/speaker·audiodream·duty·burnt + 挂钩），三查（spec 覆盖/占位符/类型一致）通过后保存。

## Self-Review 结论（作者自查）

- **spec 覆盖**：A→缺口#1+调研P1；B→教训④缺页语义；C→声景反向调度（被动记忆升级闭环）；D→PIPL"证明删了"审计。四方向全部有 Task 落地，无悬空需求。**追加需求（2026-10-12 用户点名外部模型评估）也已覆盖**：评估一（FLASepformer-JAEC，分离）裁决不并入并记驱动侧 ASR 可选前置级；评估二（Sortformer/3D-Speaker/pyannote，diarization）裁决作驱动侧可选后端，并交付**Task A4 `normalize_arrival_labels`** 作为模型接入的唯一内核接缝（纯 stdlib、可单测）。**追加体量红线（2026-10-12 用户指令：内核/手机端须控模型大小）**：Global Constraints 新增体量闸门（常驻链路 ≤ ~50MB），评估二排序按此重排——**CAM++（~30MB/Apache/CPU）升常驻首选，Sortformer（117M/数百 MB/GPU）降为 journal 离线后处理档**。**两则评估均于 2026-10-12 当日复核补全事实链**：FLASepformer = arXiv:2508.19528（Libri2Mix-100 SI-SNRi 20.3 dB，CC BY-NC 4.0 禁商用）；JAEC = 10ms 帧 / 22ms 固定延迟 / CPU RTF ≤0.0039（许可证转述 Apache-2.0，单一来源待确认）；**两模型早已落地为 `drivers/drv_audio.py` 的 `audio.separate`/`audio.aec`**（laosd 加载 + venv 门控测试，本机 `.venv-audio` 可跑真实推理）——挂载点已存在，缺的是默认链路接线与许可证放行，结论（不并入 Task A、维持 opt-in）不变。
- **占位符扫描**：无 "TBD/加适当处理/为上述写测试"；每个改 kernel/memory 的步骤都给了目标代码块；diary/`_Path`/kernel 顶部导入处标注"先读现有实现再对齐"，因这些是**读现场确认动作**而非占位（Step 明确给出确认命令）。模型侧（drv_diar/Sortformer/CAM++ 权重下载与推理）**刻意不写成 TDD Task**——它进不了主套件（重依赖只在 `.venv-audio`，AGENTS.md 红线）且需 GPU，故只给"归一接缝 A4 + 裁决 + 挂载边界注记"，非占位而是明确划出后续波边界。
- **类型一致**：`bands_of/to_centroid/centroid_distance/label_speakers`（A1）在 A2 消费名一致；**`normalize_arrival_labels(raw_ids: list[str]) -> list[str]`（A4 新增）在 A4 测试/实现/挂载注记三处签名一致，且与 `label_speakers` 同型同义（list[str]，S1/S2… 到达顺序）**；`compute_duty/threshold_offset/BASE_THRESHOLD_DBFS`（C1）在 C2 一致；`record_burn/load_receipts/verify_deletion/RECEIPT_NAME/content_hash`（D1）在 D2 一致；`dream_recall/is_burned`（B1）在 B2 一致；`mark_burned`（B2 新增 memory.py 方法）签名单一来源。
- **已知松耦合点（非 bug，刻意）**：B2 的 `has_audio` 回填与 D 的销毁回执本期各自独立（B 默认 live、gc 置 False；D 只写 burnt.jsonl），避免 B↔D 循环依赖；未来迭代可让 B 读 D 回执统一。已在 Section D 收尾注明。
- **Scope 提醒**：本计划含四个独立子系统，建议按 Section 拆成可并行子任务或四份执行；每 Section 独立可测、可 commit、可发版。若执行者一次吞全四段风险高，优先 A（缺口#1、价值最直接）→ D（合规刚需、纯内核零驱动风险最低）→ B → C（C 需真机验证收益）。
