#!/usr/bin/env python3
"""drv_mic —— 麦克风"声卡驱动"（MCP Server，重依赖惰性导入）。

把录音设备封装成 syscall：

    mic.record        同步录 seconds 秒 → var/ear/rec-<unix>.wav（16kHz 单声道 PCM16）
    mic.listen_start  拉起后台监听线程（能量阈值 VAD 分段）
    mic.listen_stop   停止监听，把最后一段未闭合有声区落盘
    mic.segments      取出未消费分段（读后即清，同 msg.recv 语义）
    mic.status        recording / listening / segments / device

依赖策略：sounddevice/soundfile/numpy 只在真正录音的函数内惰性导入——
本驱动必须能在裸解释器下 import 并回答 status（降级语义与 drv_audio 一致），
真正录音时缺依赖才报 ENOENT。生产加载方（bin/laosd.py）用 conda python
拉起本驱动（LAOS_EAR_PYTHON 可覆盖）。

隐私红线（设计约束，不可违反）：
  - 驱动模块加载时绝不启动任何录音线程；监听线程只能被 mic.listen_start
    显式拉起，mic.listen_stop / 进程退出即终止；
  - 每一次 mic.* syscall 在内核审计里额外落一条 event:"mic" 记录
    （见 laos/kernel.py syscall 派发尾部）。

分段算法 split_on_silence 是模块级纯函数（能量 dBFS 阈值 + 最短静音），
测试可直接合成样本验证，无需声卡。
"""

from __future__ import annotations

import math
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

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


# --------------------------------------------------------------------------
# 纯函数：静音分段（无任何设备/重依赖，测试直测）
# --------------------------------------------------------------------------
def split_on_silence(samples: list[int], sr: int, threshold_db: float = -40,
                     min_silence_ms: int = 300) -> list[tuple[int, int]]:
    """按能量分段：dBFS 低于 threshold_db 连续 >= min_silence_ms 即边界。

    返回有声区间 [(start, end), ...]（采样下标，end 不含）。10ms 帧算
    RMS → dBFS；首尾有声区也各自成段（尾部段延伸到 len(samples)）。
    """
    n = len(samples)
    if n == 0:
        return []
    win = max(1, sr // 100)  # 10ms 分析帧
    min_silence = max(1, sr * min_silence_ms // 1000)

    segments: list[tuple[int, int]] = []
    start: int | None = None        # 当前有声段起点
    silence_at: int | None = None   # 连续静音起点（None = 不在静音中）
    for pos in range(0, n - win + 1, win):
        chunk = samples[pos:pos + win]
        acc = 0
        for v in chunk:
            acc += v * v
        rms = math.sqrt(acc / len(chunk))
        db = 20.0 * math.log10(rms / FULL_SCALE) if rms > 0 else -999.0
        if db >= threshold_db:  # 有声
            if start is None:
                start = pos
            silence_at = None
        elif start is not None:  # 有声段中的静音
            if silence_at is None:
                silence_at = pos
            if pos + win - silence_at >= min_silence:
                segments.append((start, silence_at))
                start = None
                silence_at = None
    if start is not None:  # 尾部未闭合的有声区
        segments.append((start, n))
    return segments


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
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype="int16")
    try:
        stream.start()
        while not _listen_stop.is_set():
            data, _frames = stream.read(chunk)
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
    "从默认麦克风同步录 seconds 秒（16kHz 单声道 PCM16），写 var/ear/rec-<unix>.wav",
    {"type": "object",
     "properties": {"seconds": {"type": "integer",
                                "description": "录音秒数（默认 5）"}}},
)
def mic_record(seconds: int = 5) -> str:
    global _recording
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
    "隐私红线：除本调用外驱动绝不自行启动录音。",
    {"type": "object",
     "properties": {"threshold_db": {"type": "number",
                                     "description": "dBFS 能量阈值（默认 -40）"},
                    "min_silence_ms": {"type": "integer",
                                       "description": "最短静音切段时长（默认 300）"}}},
)
def mic_listen_start(threshold_db: float = -40.0,
                     min_silence_ms: int = 300) -> str:
    global _listen_thread, _listen_error
    with _listen_lock:
        if _listen_thread is not None and _listen_thread.is_alive():
            return "OK already listening"
        _listen_stop.clear()
        _listen_error = ""
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
    line = (f"recording={_recording} listening={listening} "
            f"segments={n_seg} device={device}")
    if _listen_error:
        line += f" error={_listen_error}"
    return line


if __name__ == "__main__":
    drv.serve_forever()
