# 录音回放（Audio Replay）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全天候录音加"录音回放"：一键取当前时间点前 15–60 秒（默认 20s）音频，重听 + 简单 ASR 转写成文字——辅助没听清/听障场景；为后期"摘要回顾模型"留结构化扩展位。

**Architecture:** 三层组装。① `laos/ringbuf.py`（纯 stdlib）内存环形缓冲：drv_mic 监听线程持续喂入，只留最近 N 秒（默认 60s，上限 300s），不落盘、进程即逝。② 驱动层 `mic.replay`（drv_mic 新工具）：显式 syscall 才把环冲快照写成 WAV（stdlib wave，即焚目录只留 20 份）。③ 内核内建 `rec.replay`（阻塞型，to_thread 派发）：同步串调 mic/ear 两个驱动客户端（MCPClient._rpc 全程持 threading.Lock，跨线程安全，绕开事件循环 driver 锁），合并音频快照+ear 三通道转写为一份 JSON，并按隐私红线补 `event:"mic"` 审计（只记元数据）。laosweb `/api/replay` + 「录音回放」卡片收尾（音频 base64 回传重听 + 文字展示）。摘要钩子=响应结构已含转写全文与时长，未来加 `summarize` 步骤的位置在 `_impl_rec_replay` 转写块之后（见 §扩展位，本期不实现）。

**Tech Stack:** Python 3 纯 stdlib（wave/threading/asyncio/json/base64）；零新依赖；测试 unittest（miniconda python）。

**Spec:** 用户需求原文（2026-10-09）："我需要针对全天候录音加一个特殊的功能。它的名字叫录音回放。目标是针对全天候录音，一直在录入的音频，帮我这个时间点的前 15 秒到 20 秒的音频进行一个回放功能。帮助别人没有听清，或者说对于那些有听觉障碍的人，起到很大的帮助作用。先做一个基本的功能，就是用 ASR 简单的 ASR 模型来对这些文本进行一个识别。等到后期留一个摘要模型的东西来做对 15 秒到 20 秒的音频，或者说更长时间的音频，做一个摘要的回顾。" 本计划即该 spec 的实施分解；仓库红线（AGENTS.md）随行。

## Global Constraints

- 零依赖红线：`laos/` 核心纯 stdlib；`laos/ringbuf.py` 只准 import 标准库。
- conda 红线：测试只用 `C:/Users/yaoyue/miniconda3/python.exe`；禁止 pip install。
- 隐私红线：录音只由显式 syscall 触发（环冲由既有 `mic.listen_start` 拉起后才有数据）；`LAOS_REC=0` 时 `mic.replay`/`rec.replay` 一律 EACCES；音频快照只在显式回放 syscall 内落盘（var/ear/replay/，只留最近 20 份）；审计只记元数据（秒数/成败/耗时），**转写文本与音频字节永不入审计**。
- `rec.replay` 读隐私源 → sentinel `private_tools` 置污（与 `mic.segments` 同级待遇）。
- 每次全量测试以实跑数为准：`cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`，记 "Ran N tests"。
- 提交信息用 conventional commits；发版（Task 6）走 AGENTS.md 发版纪律全清单。

---

### Task 1: AudioRingBuffer 核心模块（laos/ringbuf.py）

**Files:**
- Create: `laos/ringbuf.py`
- Test: `tests/test_ringbuf.py`

**Interfaces:**
- Consumes: 无（纯新模块）。
- Produces: `AudioRingBuffer(sample_rate: int = 16000, max_seconds: float = 60.0)`，方法 `feed(pcm16_bytes: bytes) -> None`、`snapshot(seconds: float) -> bytes`（PCM16 LE 字节，不足给全部）、`available_seconds() -> float`、`wav_bytes(seconds: float) -> bytes`（44 字节 WAV 头+PCM16 单声道）。线程安全。Task 2 依赖这些名字与签名。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ringbuf.py`：

```python
"""AudioRingBuffer —— 回放环形缓冲（纯 stdlib，内存即焚）。

    python -m unittest tests.test_ringbuf -v
"""
from __future__ import annotations

import io
import sys
import threading
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.ringbuf import AudioRingBuffer  # noqa: E402


class TestAudioRingBuffer(unittest.TestCase):
    def test_feed_and_snapshot_returns_recent_bytes(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=2)
        ring.feed(b"\x01\x00" * 1000)          # 1s 的 0x0001 样本
        ring.feed(b"\x02\x00" * 1000)          # 1s 的 0x0002 样本
        self.assertEqual(ring.snapshot(1.0), b"\x02\x00" * 1000)

    def test_ring_trims_to_max_seconds(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=1)
        ring.feed(b"\x01\x00" * 1000)          # 1s
        ring.feed(b"\x02\x00" * 500)           # 再 0.5s → 超容裁旧
        self.assertAlmostEqual(ring.available_seconds(), 1.0, delta=0.01)
        self.assertNotIn(b"\x01\x00", ring.snapshot(0.2))

    def test_snapshot_more_than_available_returns_all(self):
        ring = AudioRingBuffer(sample_rate=1000, max_seconds=5)
        pcm = b"\x03\x00" * 500                # 0.5s
        ring.feed(pcm)
        self.assertEqual(ring.snapshot(20.0), pcm)
        self.assertAlmostEqual(ring.available_seconds(), 0.5, delta=0.01)

    def test_snapshot_empty_ring_returns_empty(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=60)
        self.assertEqual(ring.snapshot(15.0), b"")
        self.assertEqual(ring.available_seconds(), 0.0)

    def test_wav_bytes_header_is_playable_pcm16(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=10)
        pcm = bytes(range(256)) * 100          # 25600 B = 12800 样本 = 0.8s
        ring.feed(pcm)
        wav = ring.wav_bytes(0.8)
        with wave.open(io.BytesIO(wav), "rb") as w:
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getframerate(), 16000)
            self.assertEqual(w.getnframes(), 12800)
            self.assertEqual(w.readframes(w.getnframes()), pcm)

    def test_concurrent_feed_and_snapshot_is_safe(self):
        ring = AudioRingBuffer(sample_rate=16000, max_seconds=30)
        errors: list[Exception] = []

        def feeder():
            try:
                for _ in range(200):
                    ring.feed(b"\x00\x01" * 1600)   # 每块 0.1s
            except Exception as exc:               # pragma: no cover
                errors.append(exc)

        th = threading.Thread(target=feeder)
        th.start()
        for _ in range(50):
            snap = ring.snapshot(5.0)
            self.assertLessEqual(len(snap), 5 * 16000 * 2)
        th.join()
        self.assertFalse(errors)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_ringbuf -v 2>&1 | tail -5`
Expected: FAIL/ERROR `ModuleNotFoundError: No module named 'laos.ringbuf'`

- [ ] **Step 3: 最小实现**

创建 `laos/ringbuf.py`：

```python
"""AudioRingBuffer —— 回放用音频环形缓冲（纯 stdlib，内存即焚）。

录音回放（rec.replay / mic.replay）的底座：监听线程把每个音频块 feed 进来，
缓冲只保留最近 max_seconds 秒 PCM16 字节（约 32KB/s @16kHz 单声道），超龄
即弃——不落盘、不进审计、进程退出即消失。音频落盘只发生在显式回放
syscall（mic.replay）内部（隐私红线，见 drivers/drv_mic.py 头注）。
"""

from __future__ import annotations

import io
import threading
import wave


class AudioRingBuffer:
    """线程安全的 PCM16 单声道环形缓冲。"""

    def __init__(self, sample_rate: int = 16000, max_seconds: float = 60.0):
        self.sample_rate = int(sample_rate)
        self.max_bytes = int(self.sample_rate * 2 * float(max_seconds))
        self._buf = bytearray()
        self._lock = threading.Lock()

    def feed(self, pcm16_bytes: bytes) -> None:
        """追加一个音频块；超出容量按整样本裁掉最旧数据。"""
        with self._lock:
            self._buf += pcm16_bytes
            if len(self._buf) > self.max_bytes:
                cut = len(self._buf) - self.max_bytes
                cut += cut % 2  # 不劈开 int16 样本
                del self._buf[:cut]

    def snapshot(self, seconds: float) -> bytes:
        """取最近 seconds 秒（不足则全部）PCM16 字节副本。"""
        want = int(float(seconds) * self.sample_rate * 2)
        with self._lock:
            want = min(want, len(self._buf))
            want -= want % 2
            return bytes(self._buf[-want:]) if want else b""

    def available_seconds(self) -> float:
        with self._lock:
            return len(self._buf) / (self.sample_rate * 2)

    def wav_bytes(self, seconds: float) -> bytes:
        """快照 + 44 字节 WAV 头（PCM16 单声道），可直接落盘/播放。"""
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(self.snapshot(seconds))
        return out.getvalue()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_ringbuf -v 2>&1 | tail -3`
Expected: `Ran 6 tests ... OK`

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add laos/ringbuf.py tests/test_ringbuf.py
git commit -m "feat(ringbuf): AudioRingBuffer——回放用内存环形缓冲（纯 stdlib，线程安全，即焚）"
```

---

### Task 2: drv_mic 接入环冲 + mic.replay 工具

**Files:**
- Modify: `drivers/drv_mic.py`（模块头注、imports、模块态、`mic_listen_start`、`_listen_loop`、`mic_status`，新增 `mic_replay`/`_prune_replay_dir`）
- Test: `tests/test_replay.py`（本文件本 Task 创建，Task 3/4 续用）

**Interfaces:**
- Consumes: Task 1 的 `AudioRingBuffer`（构造 `AudioRingBuffer(SAMPLE_RATE, max_seconds)`；方法 `feed/available_seconds/wav_bytes`）。
- Produces: 驱动工具 `mic.replay(seconds: float = 20.0) -> str`——返回 JSON 字符串 `{"ok": true, "wav": "<相对路径>", "seconds": <实际回放秒>, "ring_seconds": <环冲可用秒>, "sample_rate": 16000}`；`LAOS_REC=0` 抛 `PermissionError`（EACCES）；未监听/环冲空抛 `RuntimeError`（ENOENT 文案）。模块态 `drv_mic._ring: AudioRingBuffer | None`（测试注入位）。Task 3 的内核内建按这些名字消费。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_replay.py`：

```python
"""录音回放（rec.replay / mic.replay）——驱动工具 + 内核内建 + laosweb 端点。

    python -m unittest tests.test_replay -v

三层都在本文件：驱动工具直调（注入 _ring，无需声卡/conda）；内核内建用
_FakeDriver 替身注入 kernel.drivers；laosweb 端点测试在 tests/test_laosweb.py
（TestReplayApi，见 Task 4）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_mic  # noqa: E402
from laos.mcp import CallResult  # noqa: E402
from laos.ringbuf import AudioRingBuffer  # noqa: E402


class TestMicReplayTool(unittest.TestCase):
    """mic.replay 驱动工具（直调函数，注入 _ring；无需声卡）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._td.name)  # var/ear/replay 写进临时目录
        drv_mic._ring = AudioRingBuffer(16000, 60)
        drv_mic._ring.feed(b"\x11\x22" * 16000)  # 1s 样本

    def tearDown(self):
        os.chdir(self._cwd)
        drv_mic._ring = None
        self._td.cleanup()

    def test_replay_writes_wav_and_json(self):
        out = json.loads(drv_mic.mic_replay(0.5))
        self.assertTrue(out["ok"])
        self.assertTrue(Path(out["wav"]).exists())
        self.assertEqual(out["sample_rate"], 16000)
        with wave.open(out["wav"], "rb") as w:
            self.assertEqual(w.getframerate(), 16000)
            self.assertEqual(w.getnframes(), 8000)  # 0.5s @16kHz

    def test_replay_more_than_ring_returns_available(self):
        out = json.loads(drv_mic.mic_replay(30))
        self.assertLessEqual(out["seconds"], 1.01)
        self.assertGreaterEqual(out["ring_seconds"], 0.99)

    def test_replay_disabled_under_laos_rec_0(self):
        os.environ["LAOS_REC"] = "0"
        try:
            with self.assertRaises(PermissionError):
                drv_mic.mic_replay()
        finally:
            del os.environ["LAOS_REC"]

    def test_replay_without_ring_raises_enoent(self):
        drv_mic._ring = None
        with self.assertRaises(RuntimeError):
            drv_mic.mic_replay()

    def test_prune_keeps_last_20_snapshots(self):
        for _ in range(23):
            drv_mic.mic_replay(0.1)
        files = sorted(Path("var", "ear", "replay").glob("replay-*.wav"))
        self.assertEqual(len(files), 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_replay -v 2>&1 | tail -5`
Expected: 6 ERROR——`mic_replay` 不存在（`AttributeError: module 'drv_mic' has no attribute 'mic_replay'` 或同类）

- [ ] **Step 3: 实现 drv_mic 改动**

对 `drivers/drv_mic.py` 做六处修改：

（a）模块头注工具清单（docstring 第 6-10 行区域）在 `mic.status` 行前插入一行：

```
    mic.replay      回放最近 N 秒（监听环冲快照落 var/ear/replay/，只留 20 份）
```

并在头注"隐私红线"清单末尾追加一条：

```
  - mic.replay 只读监听会话的内存环冲（laos.ringbuf）；快照落盘只发生在
    本显式 syscall 内，目录只留最近 20 份；LAOS_REC=0 同闸门 EACCES
```

（b）imports 区（`import math` 起）加两行——`import json` 按字母序放在 `import math` 之前；ringbuf import 放 `from laos.mcp import MCPServer` 之后：

```python
import json
```

```python
from laos.ringbuf import AudioRingBuffer  # noqa: E402
```

（c）模块态：在 `_recording = False  # mic.record 同步录音进行中` 之后追加：

```python
# 回放环形缓冲（laos.ringbuf）：仅监听会话期间供给，内存即焚——
# listen_start 每次新建（回放窗口=本次监听会话），stop 保留到进程退出
_ring: AudioRingBuffer | None = None
_ring_seq = 0  # 回放快照命名单调递增：裁旧后文件名也不会被复用
```

（d）`mic_listen_start`：函数首行 `global _listen_thread, _listen_error` 改为 `global _listen_thread, _listen_error, _ring`；锁内 `_listen_error = ""` 之后插入：

```python
        try:
            _ring_s = float(os.environ.get("LAOS_REPLAY_RING_S", "60"))
        except ValueError:
            _ring_s = 60.0
        _ring = AudioRingBuffer(SAMPLE_RATE,
                                max(5.0, min(300.0, _ring_s)))
```

（e）`_listen_loop` 读块处（`data, _frames = stream.read(chunk)` 与 `buffer.extend` 之间）插入：

```python
            if _ring is not None:  # 回放环冲：监听会话期间持续供给
                _ring.feed(data[:, 0].tobytes())
```

（f）新增工具与裁旧函数（放在 `mic_segments` 之后、`mic_status` 之前）：

```python
@drv.tool(
    "mic.replay",
    "回放最近 N 秒音频：监听会话内存环冲的快照，落 var/ear/replay/（只留"
    "最近 20 份）；LAOS_REC=0 时 EACCES；未监听/环冲空时报 ENOENT",
    {"type": "object",
     "properties": {"seconds": {"type": "number",
                                "description": "回放秒数（默认 20）"}},
     "required": []},
)
def mic_replay(seconds: float = 20.0) -> str:
    global _ring_seq
    if os.environ.get("LAOS_REC", "1") == "0":  # 全局禁录闸门（同 mic_record）
        raise PermissionError("EACCES: recording disabled (LAOS_REC=0)")
    ring = _ring
    if ring is None or ring.available_seconds() < 0.1:
        raise RuntimeError(
            "ENOENT: replay ring empty (call mic.listen_start first)")
    seconds = max(0.5, min(float(seconds), 300.0))
    out_dir = Path("var") / "ear" / "replay"
    out_dir.mkdir(parents=True, exist_ok=True)
    _ring_seq += 1
    out = out_dir / f"replay-{_ring_seq:04d}-{int(time.time())}.wav"
    out.write_bytes(ring.wav_bytes(seconds))  # stdlib wave，无需 soundfile
    _prune_replay_dir(out_dir, keep=20)
    return json.dumps(
        {"ok": True, "wav": str(out),
         "seconds": min(seconds, ring.available_seconds()),
         "ring_seconds": round(ring.available_seconds(), 2),
         "sample_rate": SAMPLE_RATE}, ensure_ascii=False)


def _prune_replay_dir(out_dir: Path, keep: int = 20) -> None:
    """回放快照即焚位：目录内只留最近 keep 份（写后清，防长期堆积）。"""
    files = sorted(out_dir.glob("replay-*.wav"))
    for old in (files[:-keep] if len(files) > keep else []):
        old.unlink(missing_ok=True)
```

（g）`mic_status`：`line = (...)` 之前插入一行、`f"segments={n_seg} device={device}")` 改为带 ring：

```python
    ring_s = round(_ring.available_seconds(), 1) if _ring is not None else 0.0
```

```python
    line = (f"recording={_recording} listening={listening} "
            f"segments={n_seg} ring={ring_s}s device={device}")
```

- [ ] **Step 4: 跑测试确认通过（含既有 drv_mic 回归）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_replay tests.test_ear_mic -v 2>&1 | tail -4`
Expected: test_replay `Ran 6 tests ... OK`；test_ear_mic 全绿（status 子串断言不受 `ring=` 追加影响；若出现精确相等断言失败，把该断言改为子串断言再继续）

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add drivers/drv_mic.py tests/test_replay.py
git commit -m "feat(mic): mic.replay 回放工具——监听环冲快照落盘（即焚目录 20 份）+ LAOS_REC=0 闸门"
```

---

### Task 3: 内核内建 rec.replay（跨驱动组装 + 隐私审计 + sentinel 置污）

**Files:**
- Modify: `laos/kernel.py`（`_BLOCKING_BUILTINS`、`_builtin_specs`、`_builtin_impls`、新增 `_impl_rec_replay`）
- Modify: `laos/sentinel.py:49`（`private_tools` 元组追加 `"rec.replay"`）
- Test: `tests/test_replay.py`（追加 TestRecReplayBuiltin 组）

**Interfaces:**
- Consumes: Task 2 的 `mic.replay` JSON（`wav/seconds/ring_seconds/sample_rate`）；既有 `ear.transcribe` JSON（`text/language/emotions/source`）；`self.drivers["mic"|"ear"].call_tool(name, args) -> CallResult`（阻塞同步，线程安全）。
- Produces: 内建 syscall `rec.replay(seconds: float = 20, transcribe: bool = True, language: str = "auto") -> CallResult`，成功 payload JSON：`{"ok","wav","seconds","ring_seconds","sample_rate","text","language","emotions","source","transcribe_ms","ms"}`（transcribe=false 时 `text=""`、`source="none"`、`transcribe_ms=0`）。Task 4 的 laosweb 处理器按这些键消费。

- [ ] **Step 1: 写失败测试**

在 `tests/test_replay.py` 的 `if __name__ == "__main__":` 之前追加：

```python
class _FakeDriver:
    """MCPClient 替身：按工具名回放预制 CallResult（或 callable(args)）。"""

    def __init__(self, tools, results):
        self.tools = {t: None for t in tools}
        self._results = results

    def call_tool(self, name, args):
        r = self._results[name]
        return r(args) if callable(r) else r


class TestRecReplayBuiltin(unittest.TestCase):
    """内核内建 rec.replay：mic+ear 组装 / caps / 审计 / 降级路径。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        from laos.kernel import AgentKernel
        self.kernel = AgentKernel(Path(self._td.name) / "var")
        wav = Path(self._td.name) / "replay-0001-0.wav"
        wav.write_bytes(b"RIFF--fake-wav--bytes")
        snap = CallResult.ok_text(json.dumps(
            {"ok": True, "wav": str(wav), "seconds": 20,
             "ring_seconds": 25, "sample_rate": 16000}))
        tr = CallResult.ok_text(json.dumps(
            {"text": "刚刚没听清的那句话", "language": "zh", "emotions": [],
             "source": "funasr", "latency_ms": 100}))
        self.kernel.drivers["mic"] = _FakeDriver(["mic.replay"],
                                                  {"mic.replay": snap})
        self.kernel.drivers["ear"] = _FakeDriver(["ear.transcribe"],
                                                  {"ear.transcribe": tr})
        self.pid = self.kernel.spawn(name="replayer",
                                     caps=["rec.replay"]).pid

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_replay_combines_mic_and_ear(self):
        result = asyncio.run(self.kernel.syscall(
            self.pid, "rec.replay", {"seconds": 20}))
        self.assertTrue(result.ok, result.text)
        payload = json.loads(result.text)
        self.assertEqual(payload["text"], "刚刚没听清的那句话")
        self.assertEqual(payload["source"], "funasr")
        self.assertEqual(payload["seconds"], 20)

    def test_replay_transcribe_false_skips_ear(self):
        result = asyncio.run(self.kernel.syscall(
            self.pid, "rec.replay", {"seconds": 20, "transcribe": False}))
        payload = json.loads(result.text)
        self.assertEqual(payload["text"], "")
        self.assertEqual(payload["source"], "none")
        self.assertEqual(payload["transcribe_ms"], 0)

    def test_replay_writes_mic_privacy_audit_metadata_only(self):
        asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        recs = [r for r in self.kernel.audit.records
                if r.get("event") == "mic" and r.get("tool") == "rec.replay"]
        self.assertEqual(len(recs), 1)
        self.assertNotIn("text", recs[0])  # 只记元数据，转写文本永不入审计
        self.assertIn("seconds", recs[0])

    def test_replay_denied_without_cap(self):
        pid2 = self.kernel.spawn(name="noright", caps=["msg.*"]).pid
        result = asyncio.run(self.kernel.syscall(pid2, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("EPERM", result.text)

    def test_replay_missing_mic_driver_fails_enoent(self):
        del self.kernel.drivers["mic"]
        result = asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertFalse(result.ok)
        self.assertIn("ENOENT", result.text)

    def test_replay_private_tools_marks_taint(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="auto"))
        asyncio.run(self.kernel.syscall(self.pid, "rec.replay", {}))
        self.assertTrue(self.kernel.sentinel.is_tainted(self.pid))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_replay.TestRecReplayBuiltin -v 2>&1 | tail -5`
Expected: 6 FAIL——`rec.replay` 尚非 syscall（`ENOSYS: no such syscall` 类失败文案）

- [ ] **Step 3: 实现内核改动**

对 `laos/kernel.py` 做四处修改：

（a）`_BLOCKING_BUILTINS = frozenset({"evolve.run"})` 改为：

```python
_BLOCKING_BUILTINS = frozenset({"evolve.run", "rec.replay"})
```

（b）`_builtin_specs` 里 `"evolve.run"` 条目的 `reversible=True, risk="medium"),` 之后追加：

```python
            "rec.replay": ToolSpec(
                "rec.replay",
                "录音回放：取监听会话最近 N 秒音频快照（mic.replay），可选"
                "ear 三通道转写。读隐私源（置污）；LAOS_REC=0 时驱动侧拒绝",
                {"type": "object",
                 "properties": {"seconds": {"type": "number", "minimum": 1,
                                            "maximum": 300},
                                "transcribe": {"type": "boolean"},
                                "language": {"type": "string"}},
                 "required": []},
                reversible=True, risk="low"),
```

（c）`_builtin_impls` 里 `"evolve.run": self._impl_evolve_run,` 之后追加：

```python
            "rec.replay": self._impl_rec_replay,
```

（d）`_impl_evolve_run` 方法定义之后新增方法：

```python
    def _impl_rec_replay(self, pcb: PCB, args: dict) -> "CallResult":
        """录音回放组装（阻塞型内建，to_thread 派发）：mic.replay 取快照
        → ear.transcribe 转写 → 合并 JSON。直接同步 call_tool——MCPClient
        ._rpc 全程持 threading.Lock，跨线程安全；不经事件循环 driver 锁，
        HTTP 线程 asyncio.run 内调用也不会劈锁（laosweb /api/replay 路径）。
        """
        from .mcp import CallResult
        mic = self.drivers.get("mic")
        if mic is None or "mic.replay" not in mic.tools:
            return CallResult.fail("ENOENT: mic driver not loaded")
        seconds = float(args.get("seconds", 20))
        language = str(args.get("language") or "auto")
        transcribe = bool(args.get("transcribe", True))
        t0 = time.perf_counter()
        snap = mic.call_tool("mic.replay", {"seconds": seconds})
        if not snap.ok:
            return CallResult.fail(snap.text)
        try:
            payload = json.loads(snap.text)
        except json.JSONDecodeError:
            return CallResult.fail(
                f"EIO: mic.replay bad payload: {snap.text[:120]}")
        payload.update({"text": "", "language": "", "emotions": [],
                        "source": "none", "transcribe_ms": 0})
        if transcribe:
            ear = self.drivers.get("ear")
            if ear is None or "ear.transcribe" not in ear.tools:
                return CallResult.fail("ENOENT: ear driver not loaded")
            t1 = time.perf_counter()
            tr = ear.call_tool("ear.transcribe",
                               {"wav": payload["wav"], "language": language})
            payload["transcribe_ms"] = round((time.perf_counter() - t1) * 1000)
            if not tr.ok:
                return CallResult.fail(tr.text)
            try:
                item = json.loads(tr.text)
            except json.JSONDecodeError:
                return CallResult.fail("EIO: ear.transcribe bad payload")
            payload.update({"text": item.get("text", ""),
                            "language": item.get("language", ""),
                            "emotions": item.get("emotions", []),
                            "source": item.get("source", "")})
        # 隐私红线：rec.replay 暴露拾音内容，按 mic.* 同口径补 event:"mic"
        # 审计——只记元数据（秒数/是否转写），文本与音频永不入审计
        self.audit.write({"t": time.time(), "event": "mic", "pid": pcb.pid,
                          "tool": "rec.replay", "ok": True, "denied": False,
                          "seconds": payload.get("seconds"),
                          "transcribe": transcribe})
        payload["ms"] = round((time.perf_counter() - t0) * 1000)
        return CallResult.ok_text(json.dumps(payload, ensure_ascii=False))
```

对 `laos/sentinel.py` 一处修改（第 49 行）：

```python
    private_tools: tuple = ("mem.recall", "mem.curate", "mic.segments",
                            "rec.replay")
```

- [ ] **Step 4: 跑测试确认通过（含 sentinel 全回归）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_replay tests.test_sentinel -v 2>&1 | tail -4`
Expected: test_replay `Ran 12 tests ... OK`；test_sentinel 全绿（既有用例自建 config 不钉默认元组）

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add laos/kernel.py laos/sentinel.py tests/test_replay.py
git commit -m "feat(kernel): 内建 rec.replay——mic/ear 跨驱动组装+event:mic 隐私审计+sentinel 置污（阻塞型内建）"
```

---

### Task 4: laosweb /api/replay + 前端「录音回放」卡

**Files:**
- Modify: `bin/laosweb.py`（`_spawn_operator` caps；新增 `_handle_replay`；`_POST_ROUTES` 注册；前端 HTML 卡片 + JS）
- Test: `tests/test_laosweb.py`（追加 TestReplayApi 组）

**Interfaces:**
- Consumes: Task 3 的内建 `rec.replay` payload 键（`wav/seconds/ring_seconds/text/language/emotions/source/transcribe_ms/ms`）；`kernel.syscall(pid, tool, args)`（async）；模块态 `get_kernel()/_operator_pid/REPO`；前端帮手 `$(sel)`/`post(path, body)`。
- Produces: HTTP 端点 `POST /api/replay {"seconds"?,"transcribe"?,"language"?}` → 200 `{"ok":true,"wav_b64","seconds","ring_seconds","text","language","emotions","source","transcribe_ms","ms"}`（`wav` 键删除、`wav_b64` 取代）；503 kernel/operator 缺席；400 seconds 非数；502 内核/驱动失败（error 带内核文案）。前端卡片：`#btn-replay`/`#replay-sec`/`#replay-out`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_laosweb.py` 末尾（`if __name__` 块之前）追加。注意本文件需要独立的替身与导入——不依赖 tests/test_replay.py 的任何定义：

```python
class TestReplayApi(unittest.TestCase):
    """POST /api/replay：operator caps + 内建 rec.replay + wav base64 回传。"""

    def setUp(self):
        self._prev_kernel = laosweb.get_kernel()
        self._prev_pid = laosweb._operator_pid
        self._td = tempfile.TemporaryDirectory()
        from laos.kernel import AgentKernel
        from laos.mcp import CallResult
        self._CallResult = CallResult
        self.kernel = AgentKernel(Path(self._td.name) / "var")

        class _FakeDriver:
            def __init__(self, tools, results):
                self.tools = {t: None for t in tools}
                self._results = results

            def call_tool(self, name, args):
                r = self._results[name]
                return r(args) if callable(r) else r

        wav = Path(self._td.name) / "replay-0001-0.wav"
        wav.write_bytes(b"RIFF--fake-wav--bytes")
        self.kernel.drivers["mic"] = _FakeDriver(
            ["mic.replay"],
            {"mic.replay": CallResult.ok_text(json.dumps(
                {"ok": True, "wav": str(wav), "seconds": 20,
                 "ring_seconds": 20, "sample_rate": 16000}))})
        laosweb.set_kernel(self.kernel)
        laosweb._operator_pid = self.kernel.spawn(
            name="operator", caps=["msg.*", "rec.replay"]).pid

    def tearDown(self):
        laosweb.set_kernel(self._prev_kernel)
        laosweb._operator_pid = self._prev_pid
        self.kernel.shutdown()
        self._td.cleanup()

    def test_replay_returns_b64_and_text(self):
        code, body = laosweb._handle_replay({"seconds": 20})
        self.assertEqual(code, 200, body)
        self.assertTrue(body["ok"])
        self.assertIn("wav_b64", body)
        self.assertNotIn("wav", body)          # 路径不外泄，只给 b64
        import base64
        self.assertEqual(base64.b64decode(body["wav_b64"]),
                         b"RIFF--fake-wav--bytes")

    def test_replay_no_kernel_503(self):
        laosweb.set_kernel(None)
        code, _ = laosweb._handle_replay({})
        self.assertEqual(code, 503)

    def test_replay_driver_fail_502_with_reason(self):
        CR = self._CallResult
        self.kernel.drivers["mic"]._results[
            "mic.replay"] = CR.fail("ENOENT: replay ring empty "
                                    "(call mic.listen_start first)")
        code, body = laosweb._handle_replay({})
        self.assertEqual(code, 502)
        self.assertIn("ring empty", body["error"])

    def test_replay_bad_seconds_400(self):
        code, _ = laosweb._handle_replay({"seconds": "abc"})
        self.assertEqual(code, 400)
```

同时检查 `tests/test_laosweb.py` 头部导入：若还没有 `import json` / `import tempfile` / `from pathlib import Path` 则补齐（`laosweb` 已在该文件导入）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_laosweb.TestReplayApi -v 2>&1 | tail -5`
Expected: 4 ERROR——`AttributeError: module 'laosweb' has no attribute '_handle_replay'`

- [ ] **Step 3: 实现 laosweb 改动**

对 `bin/laosweb.py` 做四处修改：

（a）`_spawn_operator` 内 `pid = kernel.spawn(name="operator", caps=["msg.*"],` 改为：

```python
    pid = kernel.spawn(name="operator", caps=["msg.*", "rec.replay"],
```

（b）`_audit_voice` 函数之后新增处理函数：

```python
def _handle_replay(body: dict) -> tuple[int, dict]:
    """POST /api/replay {"seconds"?,"transcribe"?,"language"?}：录音回放。

    内核内建 rec.replay（阻塞型，to_thread 派发，HTTP 线程 asyncio.run 安全）
    → 最近 N 秒监听音频 + ear 三通道转写；wav 以 base64 回传供 <audio> 重听。
    需要 mic.listen_start 会话在跑（未监听 → 502 带内核原因）。审计走内核
    syscall 记录 + 内建补的 event:"mic"（本端点不另记）。摘要扩展位：未来
    summarize 步骤插在内核 _impl_rec_replay 转写块之后，本端点形状不变。
    """
    import base64

    kernel = get_kernel()
    if kernel is None or _operator_pid is None:
        return 503, {"error": "kernel/operator not available"}
    try:
        seconds = float(body.get("seconds", 20))
    except (TypeError, ValueError):
        return 400, {"error": "seconds must be a number"}
    seconds = max(1.0, min(seconds, 60.0))  # web 面板上限 60s（b64 体量）
    language = str(body.get("language") or "auto")
    transcribe = bool(body.get("transcribe", True))
    result = asyncio.run(kernel.syscall(
        _operator_pid, "rec.replay",
        {"seconds": seconds, "transcribe": transcribe,
         "language": language}))
    if not result.ok:
        return 502, {"error": result.text}
    try:
        payload = json.loads(result.text)
    except json.JSONDecodeError:
        return 502, {"error": "bad replay payload"}
    wav_path = Path(str(payload.get("wav", "")))
    if not wav_path.is_absolute():
        wav_path = REPO / wav_path
    try:
        wav_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")
    except OSError:
        return 502, {"error": f"replay wav unreadable: {wav_path.name}"}
    payload.pop("wav", None)  # 路径不外泄，前端只用 b64
    payload["wav_b64"] = wav_b64
    return 200, payload
```

（c）`_POST_ROUTES = {` 字典里 `"/api/voice": _handle_voice,` 之后追加一行：

```python
    "/api/replay": _handle_replay,
```

（d）前端两处。HTML：在对话卡的 `<div class="muted" id="llm-msg"></div>\n      </div>` 之后插入新卡（「operator 信箱」卡之前）：

```html
      <div class="card"><b>录音回放</b>
        <div class="row">
          <select id="replay-sec" title="回放秒数">
            <option value="15">15s</option>
            <option value="20" selected>20s</option>
            <option value="30">30s</option>
            <option value="60">60s</option>
          </select>
          <button class="act primary" id="btn-replay">⟲ 回放</button>
        </div>
        <div id="replay-out" class="muted">重听最近一段音频并转写成文字（需常听会话在跑）</div>
      </div>
```

JS：在 `voiceSend` 函数定义之后追加：

```javascript
/* ---- 录音回放：最近 N 秒重听 + ASR 文字（听障/没听清辅助） ---- */
$("#btn-replay").onclick = async () => {
  const out = $("#replay-out");
  out.classList.remove("muted");
  out.textContent = "回放中…（转写可能要几秒）";
  const r = await post("/api/replay",
                       { seconds: +$("#replay-sec").value, transcribe: true });
  if (!r.ok || !r.data || r.data.ok === undefined) {
    out.textContent = (r.data && r.data.error) || `回放失败（HTTP ${r.status}）`;
    return;
  }
  out.textContent = "";
  const audio = document.createElement("audio");
  audio.controls = true;
  audio.src = "data:audio/wav;base64," + r.data.wav_b64;
  const text = document.createElement("div");
  text.textContent = r.data.text || "(无转写文本)";
  const meta = document.createElement("div");
  meta.className = "muted";
  meta.textContent = `${r.data.seconds}s / 环冲 ${r.data.ring_seconds}s · ` +
    `${r.data.source} · 转写 ${r.data.transcribe_ms}ms · 共 ${r.data.ms}ms`;
  out.append(audio, text, meta);
};
```

- [ ] **Step 4: 跑测试确认通过（laosweb 全回归）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_laosweb -v 2>&1 | tail -4`
Expected: 全绿（既有组 + TestReplayApi 4 例）

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add bin/laosweb.py tests/test_laosweb.py
git commit -m "feat(laosweb): /api/replay + 录音回放卡——b64 重听 + ASR 文字（operator 授 rec.replay）"
```

---

### Task 5: 全量回归 + 功能地图登记

**Files:**
- Modify: `docs/guide/laos-features-map.md`（A 组追加 A10 行）
- Modify: `README.md`（功能地图节 AI 行 9 项→10 项，追加短语）

**Interfaces:**
- Consumes: Task 1–4 全部落地后的实跑测试数。
- Produces: 功能地图两处登记（A10 + README AI 行）；全量绿基线（Task 6 发版门禁依赖）。

- [ ] **Step 1: 全量测试**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `OK`。记下实跑数 N（以本次 discover 输出为准——并行波次可能已推高基线，勿用任何预估值）。若有失败：先修再进本 Task 其余步骤（不许带红往下走）。

- [ ] **Step 2: 功能地图登记（docs/guide/laos-features-map.md）**

在 A9 行（`| A9 | **Linux AgentOS demo** …`）之后追加：

```markdown
| A10 | **录音回放** `rec.replay` | 常听会话最近 15–60s 音频快照+ASR 转写（听障/没听清辅助；内存环冲即焚，LAOS_REC=0 禁） | laosweb「录音回放」卡；内核 syscall `rec.replay` |
```

（该文件 A 组小节头 `## 1. 第一层：AI / Agent 能力（有模型参与的）` 无计数文案，无需再改。）

- [ ] **Step 3: README 功能地图行**

README.md 功能地图节 `| 🤖 **AI / Agent 能力**（9 项，全 opt-in） | …` 行：`（9 项` 改 `（10 项`，行尾 ` · AgentOS demo` 之后追加 ` · 录音回放（15–60s 快照+转写）`。

- [ ] **Step 4: 交接门禁（改码后必跑）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/check_onboarding.py`
Expected: 绿（本波未改 ONBOARDING.md，其基线数字不含本波新增测试数；若因 README 变动报红，按脚本输出把漂移项改齐再跑绿）。

- [ ] **Step 5: 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add docs/guide/laos-features-map.md README.md
git commit -m "docs: 功能地图登记 A10 录音回放（README AI 行 10 项）"
```

---

### Task 6: 发版 v0.36.0（AGENTS.md 发版纪律全清单）

**Files:**
- Modify: 三棵树 `__version__`、CHANGELOG.md、全部介绍文件锚点（release.py 自动）

**Interfaces:**
- Consumes: Task 5 的全量绿基线与实跑测试数。
- Produces: v0.36.0 tag + GitHub Release 页 + 全部介绍文件版本/测试数同步。

- [ ] **Step 1: dry-run 核对**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/release.py --dry-run`
Expected: 测试真跑全绿；报告显示下一版本 v0.36.0（feat 波次）、三树同步与五类锚点改动清单。核对无异常再进 Step 2。

- [ ] **Step 2: apply**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe scripts/release.py --apply`
Expected: 三树 `__version__` 与介绍文件锚点落盘（README/PROJECT_OVERVIEW/PPT 组/页脚测试计数，页脚总数含隔离区+复现区）。

- [ ] **Step 3: CHANGELOG 人工段落**

在 `CHANGELOG.md` 的 `[Unreleased]` 之下插入 v0.36.0 段（日期 2026-10-09）：

```markdown
## [0.36.0] - 2026-10-09

### Added
- **录音回放 `rec.replay`**：全天候录音新能力——一键取当前时间点前 15–60 秒
  （默认 20s）音频快照重听 + ASR 转写文字，辅助没听清/听障场景。
  - `laos/ringbuf.py`：内存环形缓冲（纯 stdlib，即焚，默认 60s 上限 300s，
    `LAOS_REPLAY_RING_S` 可调）
  - `mic.replay` 驱动工具：快照落 var/ear/replay/（只留 20 份）；
    `LAOS_REC=0` 同闸门 EACCES
  - 内核内建 `rec.replay`：mic/ear 跨驱动组装（阻塞型 to_thread 派发），
    隐私审计 event:"mic" 只记元数据，sentinel private_tools 置污
  - laosweb `/api/replay` + 「录音回放」卡：音频 b64 重听 + 文字展示
  - 摘要模型扩展位：`_impl_rec_replay` 转写块后（本期未实现，见计划 §扩展位）
```

- [ ] **Step 4: release commit + tag + push**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
git add -A
git commit -m "chore(release): v0.36.0 — 录音回放（环冲+mic.replay+内核组装+laosweb 卡）"
git tag -a v0.36.0 -m "录音回放：15–60s 快照+ASR 转写（听障/没听清辅助）"
git push origin master --tags
```

- [ ] **Step 5: GitHub Release 页**

按既有 json 文件法建 Release（token 经 `git credential fill`，不回显）：title `v0.36.0 — 录音回放`，notes 用 Step 3 的 CHANGELOG 段正文。验证 `gh release view v0.36.0` 或 API 200。

---

## 扩展位（本期不实现，禁止顺手实现）

**摘要回顾模型**（spec 后半句）：插入点是 `laos/kernel.py` `_impl_rec_replay` 的转写块之后、审计写入之前——届时给 `rec.replay` 的 ToolSpec 加 `"summarize": {"type": "boolean"}` 参数，true 时把 `payload["text"]` 送 `laos/llm.py` LLMClient（或 JitMem 摘要内建）产出 `payload["summary"]`；laosweb 前端在 `#replay-out` 追加一个 summary 节点即可，API 形状向后兼容。环冲上限已放宽到 300s（`LAOS_REPLAY_RING_S`），"更长时间的音频"无需改缓冲层。触发条件：用户明确提出下一波。

## 现状锚点（写计划时核实过的代码事实）

- `drivers/drv_mic.py:116-118` 监听循环 `stream.read(chunk)` + `buffer.extend`（ring feed 插入点）；`mic.listen_start` 仅显式拉起（隐私红线）；`mic_status` 输出 `recording=/listening=/segments=/device=`。
- `laos/kernel.py`：`_BLOCKING_BUILTINS = frozenset({"evolve.run"})`（:252 附近）；内建查表 miss 才 ENOSYS（:566 附近，`syscall_table` 先查、`_builtin_specs` 后查）；内建与 MCP 共享闸门链（caps→task_scope→validate→EDQUOT→风险闸→sentinel）；`mic.*` 派发尾部补 event:"mic" 审计——内建不走该分支，故 `_impl_rec_replay` 自补。
- `laos/mcp.py:61-77`：`CallResult.ok_text(text)` / `CallResult.fail(error)`；`MCPClient._rpc` 全程持 `threading.Lock`（:385 附近，UniqueLock 全程持锁事实）。
- `laos/sentinel.py:49`：`private_tools: tuple = ("mem.recall", "mem.curate", "mic.segments")`；无测试钉死默认元组（tests/test_sentinel.py:245 自建 config）。
- `bin/laosweb.py`：`$`(:448)/`post`(:460) 前端帮手；`_spawn_operator` caps=["msg.*"]；`_POST_ROUTES`(:1351 附近)；`_handle_msg` 头注明言 HTTP 线程"绝不在此跑 MCP 路径"——本设计以阻塞型内建 + to_thread 遵守该约束；REPO 常量(:35)。
- `bin/laosd.py:169-170`：mic/ear 驱动由 conda python 拉起、boot 即载——`rec.replay` 无需改 boot。
- 功能地图：`docs/guide/laos-features-map.md` A 组尾 A9、E 组尾 E14；README.md:63 AI 行 9 项。
