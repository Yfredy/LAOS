#!/usr/bin/env python3
"""drv_mic —— 麦克风"声卡驱动"（MCP Server，重依赖惰性导入）。

把录音设备封装成 syscall：

    mic.record        同步录 seconds 秒 → var/ear/rec-<unix>.wav（16kHz 单声道 PCM16）
    mic.listen_start  拉起后台监听线程（能量阈值 VAD 分段）
    mic.listen_stop   停止监听，把最后一段未闭合有声区落盘
    mic.segments      取出未消费分段（读后即清，同 msg.recv 语义）
    mic.replay      回放最近 N 秒（监听环冲快照落 var/ear/replay/，只留 20 份）
    mic.status        recording / listening / segments / device

依赖策略：sounddevice/soundfile/numpy 只在真正录音的函数内惰性导入——
本驱动必须能在裸解释器下 import 并回答 status（降级语义与 drv_audio 一致），
真正录音时缺依赖才报 ENOENT。生产加载方（bin/laosd.py）用 conda python
拉起本驱动（LAOS_EAR_PYTHON 可覆盖）。

隐私红线（设计约束，不可违反）：
  - 驱动模块加载时绝不启动任何录音线程；监听线程只能被 mic.listen_start
    显式拉起，mic.listen_stop / 进程退出即终止；
  - LAOS_REC=0 全局禁录：mic.record / mic.listen_start 一律 EACCES 拒绝
    （与 drv_rec.rec_start 同语义同闸门）；
  - 每一次 mic.* syscall 在内核审计里额外落一条 event:"mic" 记录
    （见 laos/kernel.py syscall 派发尾部与 _deny 拒绝路径——无论成败）；
  - mic.replay 只读监听会话的内存环冲（laos.ringbuf）；快照落盘只发生在
    本显式 syscall 内，目录只留最近 20 份；LAOS_REC=0 同闸门 EACCES

分段算法 split_on_silence 是模块级纯函数（能量 dBFS 阈值 + 最短静音），
测试可直接合成样本验证，无需声卡。
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from laos.ringbuf import AudioRingBuffer  # noqa: E402

drv = MCPServer("drv_mic", version="0.1.0")

#: 录音参数：16kHz 单声道 PCM16（SenseVoice 的原生输入格式）
SAMPLE_RATE = 16000
CHANNELS = 1

#: int16 满量程（dBFS 参考电平）
FULL_SCALE = 32768.0

# -- 监听状态（仅 mic.listen_start 显式调用后才存在线程——隐私红线）----------
_listen_lock = threading.Lock()
_listen_thread: threading.Thread | None = None
_listen_stop = threading.Event()
_listen_error: str = ""
_segments: list[str] = []  # 未消费分段 wav 路径（segments 消费后清空）
_seg_seq = 0  # 分段命名单调递增：消费（清空）后文件名也不会被复用
_recording = False  # mic.record 同步录音进行中

# 回放环形缓冲（laos.ringbuf）：仅监听会话期间供给，内存即焚——
# listen_start 每次新建（回放窗口=本次监听会话），stop 保留到进程退出。
# 内存预算（手机）：默认 30s=960KB、clamp 5..120s，权威时域存储在 ADSP
_ring: AudioRingBuffer | None = None
_ring_seq = 0  # 回放快照命名单调递增：裁旧后文件名也不会被复用


def _ring_seconds_from_env() -> float:
    """环冲容量（秒）：LAOS_REPLAY_RING_S 覆盖，clamp 5..120（预算红线）。"""
    try:
        v = float(os.environ.get("LAOS_REPLAY_RING_S", "30"))
    except ValueError:
        v = 30.0
    return max(5.0, min(120.0, v))


# --------------------------------------------------------------------------
# 纯函数：静音分段 —— 委托 laos.vad（统一实现，批式/流式一致）
# --------------------------------------------------------------------------
def split_on_silence(samples: list[int], sr: int, threshold_db: float = -40,
                     min_silence_ms: int = 300) -> list[tuple[int, int]]:
    """按能量分段（drv_mic 兼容签名）：无声段边界由连续 min_silence_ms 静音决定。

    语义与 laos.vad.split_segments 一致——本函数是它的薄包装：
    pad=0、min_speech=0（本驱动不分段时长过滤，由调用方决定）。
    """
    from laos.vad import split_segments
    return split_segments(samples, sr,
                          threshold_dbfs=threshold_db,
                          min_speech_ms=1,
                          min_silence_ms=min_silence_ms,
                          pad_ms=0)


# --------------------------------------------------------------------------
# 监听线程体（sounddevice/numpy/soundfile 全部惰性导入）
# --------------------------------------------------------------------------
def _write_segment(seg_dir: Path, buffer: list[int], s: int, e: int,
                   sf, np) -> None:
    global _seg_seq
    with _listen_lock:  # 命名 + 登记 + 计数在同一临界区，杜绝覆盖
        out = seg_dir / f"seg-{_seg_seq}.wav"
        _seg_seq += 1
        _segments.append(str(out))
    sf.write(str(out), np.array(buffer[s:e], dtype="int16"),
             SAMPLE_RATE, subtype="PCM_16")


def _listen_loop(threshold_db: float, min_silence_ms: int) -> None:
    """后台监听线程：100ms 块读取 → 累积缓冲 → split_on_silence 复算 →
    新完成的段落盘。原型不裁剪缓冲（长时监听内存随时长增长，见驱动 docstring）。"""
    global _listen_error
    try:
        import numpy as np
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        _listen_error = f"ENOENT: missing audio stack: {exc}"
        return
    seg_dir = Path("var") / "ear" / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    chunk = SAMPLE_RATE // 10
    buffer: list[int] = []
    emitted = 0
    stream = None
    try:
        # 设备打开也在 try 里：麦克风被占用/拔出时 InputStream() 构造即抛，
        # 不能让监听线程带崩得无声无息——要落到 _listen_error 供 status 如实上报
        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                                dtype="int16")
        stream.start()
        while not _listen_stop.is_set():
            data, _frames = stream.read(chunk)
            if _ring is not None:  # 回放环冲：监听会话期间持续供给
                _ring.feed(data[:, 0].tobytes())
            buffer.extend(int(v) for v in data[:, 0])
            segs = split_on_silence(buffer, SAMPLE_RATE, threshold_db,
                                    min_silence_ms)
            while emitted < len(segs):
                s, e = segs[emitted]
                emitted += 1
                _write_segment(seg_dir, buffer, s, e, sf, np)
    except Exception as exc:  # 设备拔出等：如实上报到 status
        _listen_error = f"EIO: listen stream failed: {exc}"
    finally:
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if buffer:  # 收尾：最后一段未闭合有声区也落盘
            try:
                segs = split_on_silence(buffer, SAMPLE_RATE, threshold_db,
                                        min_silence_ms)
                while emitted < len(segs):
                    s, e = segs[emitted]
                    emitted += 1
                    _write_segment(seg_dir, buffer, s, e, sf, np)
            except Exception as exc:
                _listen_error = f"EIO: final flush failed: {exc}"


# --------------------------------------------------------------------------
# syscalls
# --------------------------------------------------------------------------
@drv.tool(
    "mic.record",
    "从默认麦克风同步录 seconds 秒（16kHz 单声道 PCM16），写 var/ear/rec-<unix>.wav"
    "（LAOS_REC=0 全局禁录：EACCES）",
    {"type": "object",
     "properties": {"seconds": {"type": "integer",
                                "description": "录音秒数（默认 5）"}}},
)
def mic_record(seconds: int = 5) -> str:
    global _recording
    if os.environ.get("LAOS_REC", "1") == "0":  # 全局禁录闸门（同 drv_rec.rec_start）
        raise PermissionError("EACCES: recording disabled (LAOS_REC=0)")
    import sounddevice as sd  # 惰性：只有真录音才需要声卡栈
    import soundfile as sf
    seconds = max(1, int(seconds))
    n_frames = SAMPLE_RATE * seconds
    _recording = True
    try:
        audio = sd.rec(n_frames, samplerate=SAMPLE_RATE, channels=CHANNELS,
                       dtype="int16")
        sd.wait()
    finally:
        _recording = False
    out_dir = Path("var") / "ear"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"rec-{int(time.time())}.wav"
    sf.write(str(out), audio, SAMPLE_RATE, subtype="PCM_16")
    return f"OK recorded {out} ({len(audio)} samples)"


@drv.tool(
    "mic.listen_start",
    "显式拉起后台监听线程（能量阈值 VAD 分段），分段落 var/ear/segments/seg-<n>.wav。"
    "隐私红线：除本调用外驱动绝不自行启动录音；LAOS_REC=0 全局禁录（EACCES）。",
    {"type": "object",
     "properties": {"threshold_db": {"type": "number",
                                     "description": "dBFS 能量阈值（默认 -40）"},
                    "min_silence_ms": {"type": "integer",
                                       "description": "最短静音切段时长（默认 300）"}}},
)
def mic_listen_start(threshold_db: float = -40.0,
                     min_silence_ms: int = 300) -> str:
    global _listen_thread, _listen_error, _ring
    if os.environ.get("LAOS_REC", "1") == "0":  # 全局禁录闸门（同 drv_rec.rec_start）
        raise PermissionError("EACCES: recording disabled (LAOS_REC=0)")
    with _listen_lock:
        if _listen_thread is not None and _listen_thread.is_alive():
            return "OK already listening"
        _listen_stop.clear()
        _listen_error = ""
        _ring = AudioRingBuffer(SAMPLE_RATE, _ring_seconds_from_env())
        th = threading.Thread(target=_listen_loop,
                              args=(float(threshold_db), int(min_silence_ms)),
                              daemon=True, name="mic-listen")
        _listen_thread = th
        th.start()
    return (f"OK listening started (threshold_db={threshold_db} "
            f"min_silence_ms={min_silence_ms})")


@drv.tool("mic.listen_stop", "停止监听线程并把最后一段未闭合有声区落盘",
          {"type": "object", "properties": {}})
def mic_listen_stop() -> str:
    global _listen_thread
    with _listen_lock:
        th = _listen_thread
    if th is None or not th.is_alive():
        return "OK not listening"
    _listen_stop.set()
    th.join(timeout=5.0)
    with _listen_lock:
        _listen_thread = None
        n = len(_segments)
    return f"OK listening stopped (pending segments={n})"


@drv.tool("mic.segments", "取出未消费的语音分段 wav 路径（读后即清空）",
          {"type": "object", "properties": {}})
def mic_segments() -> str:
    with _listen_lock:
        segs = list(_segments)
        _segments.clear()
    if not segs:
        return "(no pending segments)"
    return "\n".join(segs)


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
    seconds = max(0.5, min(float(seconds), 120.0))
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


@drv.tool("mic.status", "麦克风状态：recording/listening/segments/device",
          {"type": "object", "properties": {}})
def mic_status() -> str:
    device = "unavailable"
    try:
        import sounddevice as sd
        idx = sd.default.device[0]  # 输入设备
        if idx >= 0:
            device = str(sd.query_devices(idx)["name"])
    except Exception:
        pass
    with _listen_lock:
        listening = _listen_thread is not None and _listen_thread.is_alive()
        n_seg = len(_segments)
    ring_s = round(_ring.available_seconds(), 1) if _ring is not None else 0.0
    line = (f"recording={_recording} listening={listening} "
            f"segments={n_seg} ring={ring_s}s device={device}")
    if _listen_error:
        line += f" error={_listen_error}"
    return line


if __name__ == "__main__":
    drv.serve_forever()
