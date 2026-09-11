#!/usr/bin/env python3
"""drv_rec —— VAD 触发式录音会话驱动（MCP Server，听觉日志第 2 段）。

全天候听觉日志管线（docs/superpowers/plans/2026-09-10-always-on-audio-journal.md）：
常驻拾音流喂给 laos.vad.StreamingVAD——**只有有声段落盘**（无声即弃，
零存储零后续算力），落 var/ear/journal/ 供 ear.journal 批量转写。

隐私（贯穿红线）：
  - 显式触发：rec.start 是 syscall；LAOS_REC=0 全局禁录（EACCES）
  - 每段写审计（内核侧 event:"mic" 已有；本驱动返回文本含段信息）
  - 原音频即焚：rec.gc(keep_hours) 删超龄段（默认 LAOS_JOURNAL_KEEP_H=6h，
    由 journal 转写成功后触发）

运行环境：conda python（sounddevice）；测试注入 fake input factory。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from laos.vad import StreamingVAD  # noqa: E402

drv = MCPServer("drv_rec", version="0.1.0")

SAMPLE_RATE = 16000
_input_factory = None       # 测试注入：callable(samplerate, blocksize, dtype, callback) -> stream
_output_dir: Path | None = None
_stream = None
_vad: StreamingVAD | None = None
_recording = False
_lock = threading.Lock()
_seg_seq = 0
_earliest_keep = time.time()


def set_input_factory(factory) -> None:
    """测试注入假输入流工厂；None 恢复真实 sounddevice。"""
    global _input_factory
    _input_factory = factory


def set_output_dir(path: Path | None) -> None:
    """测试注入输出目录；None 恢复默认 var/ear/journal。"""
    global _output_dir
    _output_dir = Path(path) if path else None


def _reset() -> None:
    """测试隔离：停流清态。"""
    global _stream, _vad, _recording, _seg_seq
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
    _stream = None
    _vad = None
    _recording = False
    _seg_seq = 0


def _journal_dir() -> Path:
    d = _output_dir or (Path("var") / "ear" / "journal")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _real_factory(samplerate, blocksize, dtype, callback):
    import sounddevice as sd
    return sd.InputStream(samplerate=samplerate, blocksize=blocksize,
                          dtype=dtype, callback=callback)


@drv.tool(
    "rec.start",
    "开始 VAD 触发式录音（只有有声段落盘；LAOS_REC=0 时禁录）",
    {"type": "object",
     "properties": {"threshold_dbfs": {"type": "number", "default": -35.0}},
     "required": []},
)
def rec_start(threshold_dbfs: float = -35.0) -> str:
    global _stream, _vad, _recording
    if os.environ.get("LAOS_REC", "1") == "0":
        raise PermissionError("EACCES: recording disabled (LAOS_REC=0)")
    with _lock:
        if _recording:
            return "OK already recording"
        _vad = StreamingVAD(SAMPLE_RATE, threshold_dbfs=threshold_dbfs)
        factory = _input_factory or _real_factory

        def on_audio(data, frames, t, status):
            for start_ms, wav in _vad.feed(bytes(data)):  # type: ignore[union-attr]
                _save_segment(start_ms, wav)

        _stream = factory(SAMPLE_RATE, SAMPLE_RATE // 10, "int16", on_audio)
        _stream.start()
        _recording = True
    return "OK recording (VAD-gated)"


def _save_segment(start_ms: int, wav: bytes) -> Path:
    global _seg_seq
    _seg_seq += 1
    path = _journal_dir() / f"rec-{_seg_seq:04d}-{int(time.time())}.wav"
    path.write_bytes(wav)
    return path


@drv.tool("rec.stop", "停止录音会话，返回段数",
          {"type": "object", "properties": {}})
def rec_stop() -> str:
    global _recording
    n = 0
    with _lock:
        if _stream is not None:
            if _vad is not None:
                for start_ms, wav in _vad.flush():
                    _save_segment(start_ms, wav)
            try:
                _stream.stop()
                _stream.close()
            except Exception:
                pass
        n = _seg_seq
        _reset()
        _recording = False
    return f"OK stopped, {n} segments"


@drv.tool(
    "rec.segments",
    "列出已捕获的听觉日志分段",
    {"type": "object", "properties": {"since_ts": {"type": "number"}}, "required": []},
)
def rec_segments(since_ts: float = 0) -> str:
    rows = []
    for p in sorted(_journal_dir().glob("rec-*.wav")):
        if p.stat().st_mtime > since_ts:
            rows.append(f"{p.name} {p.stat().st_size}B")
    return "\n".join(rows) or "(no segments)"


@drv.tool(
    "rec.gc",
    "删除超龄原音频（默认保留 LAOS_JOURNAL_KEEP_H 小时）",
    {"type": "object", "properties": {"keep_hours": {"type": "number"}}, "required": []},
)
def rec_gc(keep_hours: float | None = None) -> str:
    if keep_hours is None:
        keep_hours = float(os.environ.get("LAOS_JOURNAL_KEEP_H", "6"))
    h = float(keep_hours)
    cutoff = time.time() - h * 3600
    removed = 0
    for p in _journal_dir().glob("rec-*.wav"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)
            removed += 1
    return f"OK gc removed {removed} (keep {h}h)"


@drv.tool("rec.status", "录音会话状态", {"type": "object", "properties": {}})
def rec_status() -> str:
    keep = os.environ.get("LAOS_JOURNAL_KEEP_H", "6")
    segs = len(list(_journal_dir().glob("rec-*.wav"))) if not _output_dir else \
        len(list(_journal_dir().glob("rec-*.wav")))
    return f"recording={_recording} segments={segs} keep_hours={keep}"


if __name__ == "__main__":
    drv.serve_forever()
