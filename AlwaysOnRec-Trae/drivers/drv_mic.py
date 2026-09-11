#!/usr/bin/env python3
"""drv_mic —— 麦克风"声卡驱动"（MCP Server，重依赖惰性导入）。

把录音设备封装成 syscall：

    mic.record          同步录 seconds 秒 → var/ear/rec-<unix>.wav（16kHz 单声道 PCM16）
    mic.listen_start    拉起后台监听线程（能量阈值 VAD 分段）
    mic.listen_stop     停止监听，把最后一段未闭合有声区落盘
    mic.always_on_start 拉起常开线程：100ms 块进环形缓冲（rewind 回溯用）+ VAD 门控落盘
    mic.rewind          取最近 seconds 秒环形缓冲拼成 WAV → var/ear/segments/rewind-<ts>.wav
    mic.always_on_stop  停止常开线程：flush 最后一段未闭合有声区并清空环形缓冲
    mic.segments        取出未消费分段（读后即清，同 msg.recv 语义）
    mic.status          recording / listening / segments / device / always_on / ring_seconds

依赖策略：sounddevice/soundfile/numpy 只在真正录音的函数内惰性导入——
本驱动必须能在裸解释器下 import 并回答 status（降级语义与 drv_audio 一致），
真正录音时缺依赖才报 ENOENT。生产加载方（bin/laosd.py）用 conda python
拉起本驱动（LAOS_EAR_PYTHON 可覆盖）。

隐私红线（设计约束，不可违反）：
  - 驱动模块加载时绝不启动任何录音线程；监听/常开线程只能被 mic.listen_start
    / mic.always_on_start 显式拉起，*_stop / 进程退出即终止；
  - 常开模式尊重 LAOS_REC=0 全局禁录（EACCES）；环形缓冲内存上限 600s；
  - 每一次 mic.* syscall 在内核审计里额外落一条 event:"mic" 记录
    （见 laos/kernel.py syscall 派发尾部与 _deny 拒绝路径——无论成败）。

分段算法 split_on_silence 是模块级纯函数（能量 dBFS 阈值 + 最短静音），
测试可直接合成样本验证，无需声卡。分段落盘走 laos.vad.wav_bytes（纯
stdlib）——常开模式在裸解释器下注入 fake input factory 即可端到端验证。
"""

from __future__ import annotations

import io
import math
import os
import sys
import threading
import time
import wave
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from laos.vad import wav_bytes  # noqa: E402  纯 stdlib WAV 封装：落盘零重依赖

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

# -- 常开状态（仅 mic.always_on_start 显式调用后才存在线程——隐私红线）--------
_always_on_lock = threading.Lock()
_always_on_thread: threading.Thread | None = None
_always_on_stop = threading.Event()
_always_on_error: str = ""
_ring: deque = deque()          # 环形缓冲：100ms PCM16LE 字节块（mic.rewind 回溯用）
_ring_lock = threading.Lock()   # 红线：_ring 的读写必须持 _ring_lock
_ring_seconds = 0               # 当前环形缓冲容量（秒）；0 = 未运行
_input_factory = None           # 测试注入：callable(samplerate, blocksize, dtype, callback) -> stream
_output_dir: Path | None = None  # 测试注入：分段/rewind 输出目录；None = var/ear/segments


def set_input_factory(factory) -> None:
    """测试注入假输入流工厂；None 恢复真实 sounddevice（与 drv_rec 同款注入点）。"""
    global _input_factory
    _input_factory = factory


def set_output_dir(path: Path | None) -> None:
    """测试注入输出目录；None 恢复默认 var/ear/segments。"""
    global _output_dir
    _output_dir = Path(path) if path else None


def _segments_dir() -> Path:
    d = _output_dir or (Path("var") / "ear" / "segments")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _real_factory(samplerate, blocksize, dtype, callback):
    import sounddevice as sd  # 惰性：只有真录音（无注入）才需要声卡栈
    return sd.InputStream(samplerate=samplerate, blocksize=blocksize,
                          dtype=dtype, callback=callback)


def _reset() -> None:
    """测试隔离：停掉监听/常开线程并清空全部模块态（仅供测试调用）。"""
    global _listen_thread, _always_on_thread, _ring, _ring_seconds
    global _listen_error, _always_on_error, _input_factory, _seg_seq
    _listen_stop.set()
    _always_on_stop.set()
    for th in (_listen_thread, _always_on_thread):
        if th is not None and th.is_alive():
            th.join(timeout=3.0)
    _listen_stop.clear()
    _always_on_stop.clear()
    with _listen_lock:
        _listen_thread = None
        _segments.clear()
        _seg_seq = 0
        _listen_error = ""
    with _always_on_lock:
        _always_on_thread = None
        _ring_seconds = 0
        _always_on_error = ""
    with _ring_lock:
        _ring = deque()
    _input_factory = None


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
# 线程体（sounddevice 等重依赖惰性导入；落盘走 laos.vad.wav_bytes 零重依赖）
# --------------------------------------------------------------------------
def _write_segment(seg_dir: Path, buffer: list[int], s: int, e: int) -> None:
    global _seg_seq
    with _listen_lock:  # 命名 + 登记 + 计数在同一临界区，杜绝覆盖
        out = seg_dir / f"seg-{_seg_seq}.wav"
        _seg_seq += 1
        _segments.append(str(out))
    out.write_bytes(wav_bytes(buffer[s:e], SAMPLE_RATE))


def _consume_voice(buffer: list[int], emitted: int, *, threshold_db: float,
                   min_silence_ms: int, seg_dir: Path) -> int:
    """共享纯函数（split_on_silence 薄消费）：把累积缓冲切分，把新出现的有声段
    落盘，返回已消费段数。_listen_loop 与 _always_on_loop 共用，避免逻辑漂移。"""
    segs = split_on_silence(buffer, SAMPLE_RATE, threshold_db, min_silence_ms)
    while emitted < len(segs):
        s, e = segs[emitted]
        emitted += 1
        _write_segment(seg_dir, buffer, s, e)
    return emitted


def _listen_loop(threshold_db: float, min_silence_ms: int) -> None:
    """后台监听线程：100ms 块读取 → 累积缓冲 → _consume_voice 消费新完成段。
    原型不裁剪缓冲（长时监听内存随时长增长，见驱动 docstring）。"""
    global _listen_error
    try:
        import sounddevice as sd
    except ImportError as exc:
        _listen_error = f"ENOENT: missing audio stack: {exc}"
        return
    seg_dir = _segments_dir()
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
            buffer.extend(int(v) for v in data[:, 0])
            emitted = _consume_voice(buffer, emitted, threshold_db=threshold_db,
                                     min_silence_ms=min_silence_ms,
                                     seg_dir=seg_dir)
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
                _consume_voice(buffer, emitted, threshold_db=threshold_db,
                               min_silence_ms=min_silence_ms, seg_dir=seg_dir)
            except Exception as exc:
                _listen_error = f"EIO: final flush failed: {exc}"


def _always_on_loop(ring_seconds: int, threshold_db: float,
                    min_silence_ms: int) -> None:
    """常开线程体：与 _listen_loop 同构（100ms 块 → 累积缓冲 → _consume_voice），
    差异是每块先推入环形缓冲 _ring（供 mic.rewind 回溯最近音频）。
    音频走回调模型（与 drv_rec 注入工厂同签名）；无块到达时挂起等停止信号。"""
    global _always_on_error
    seg_dir = _segments_dir()
    chunk = SAMPLE_RATE // 10  # 100ms 块
    buffer: list[int] = []
    emitted = 0

    def on_audio(data, frames, t, status) -> None:
        nonlocal emitted
        try:
            pcm = bytes(data)  # PCM16LE 字节
            with _ring_lock:  # 红线：环形缓冲读写必须持 _ring_lock
                _ring.append(pcm)
            buffer.extend(int.from_bytes(pcm[i:i + 2], "little", signed=True)
                          for i in range(0, len(pcm) - 1, 2))
            emitted = _consume_voice(buffer, emitted,
                                     threshold_db=threshold_db,
                                     min_silence_ms=min_silence_ms,
                                     seg_dir=seg_dir)
        except Exception as exc:  # 回调线程崩了无人收尸 → 落 _always_on_error 如实上报
            _always_on_error = f"EIO: always-on consume failed: {exc}"

    stream = None
    try:
        factory = _input_factory or _real_factory
        stream = factory(SAMPLE_RATE, chunk, "int16", on_audio)
        stream.start()
        while not _always_on_stop.wait(timeout=0.2):
            pass  # 块经回调异步到达；这里只等 mic.always_on_stop 的停止信号
    except ImportError as exc:  # 真声卡栈缺失（注入模式下不会走到）
        _always_on_error = f"ENOENT: missing audio stack: {exc}"
    except Exception as exc:  # 设备占用/拔出等：如实上报到 status
        _always_on_error = f"EIO: always-on stream failed: {exc}"
    finally:
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if buffer:  # 收尾（复用 _listen_loop 语义）：最后一段未闭合有声区也落盘
            try:
                _consume_voice(buffer, emitted, threshold_db=threshold_db,
                               min_silence_ms=min_silence_ms, seg_dir=seg_dir)
            except Exception as exc:
                _always_on_error = f"EIO: final flush failed: {exc}"


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


# --------------------------------------------------------------------------
# 常开模式 syscalls（环形缓冲 + rewind；线程只能被 always_on_start 显式拉起）
# --------------------------------------------------------------------------
@drv.tool(
    "mic.always_on_start",
    "拉起常开线程：持续读 100ms 块，先推入环形缓冲（供 mic.rewind 回溯），"
    "再同监听一样 VAD 门控落盘 var/ear/segments/。隐私：LAOS_REC=0 时 EACCES；"
    "环形缓冲内存上限 600s；除本调用外驱动绝不自行启动录音线程。",
    {"type": "object",
     "properties": {"ring_seconds": {"type": "integer",
                                     "description": "环形缓冲时长上限秒（默认 120，≤600）"},
                    "threshold_db": {"type": "number",
                                     "description": "dBFS 能量阈值（默认 -40）"},
                    "min_silence_ms": {"type": "integer",
                                       "description": "最短静音切段时长（默认 300）"}}},
)
def mic_always_on_start(ring_seconds: int = 120, threshold_db: float = -40.0,
                        min_silence_ms: int = 300) -> str:
    global _always_on_thread, _always_on_error, _ring, _ring_seconds
    if os.environ.get("LAOS_REC", "1") == "0":
        raise PermissionError("EACCES: recording disabled (LAOS_REC=0)")
    with _always_on_lock:
        if _always_on_thread is not None and _always_on_thread.is_alive():
            return "OK always-on already running"
        rs = min(600, max(1, int(ring_seconds)))  # 内存上限红线：≤600s
        _ring_seconds = rs
        with _ring_lock:
            _ring = deque(maxlen=rs * 10)  # 元素为 100ms PCM16LE 字节块
        _always_on_stop.clear()
        _always_on_error = ""
        th = threading.Thread(target=_always_on_loop,
                              args=(rs, float(threshold_db), int(min_silence_ms)),
                              daemon=True, name="mic-always-on")
        _always_on_thread = th
        th.start()
    return (f"OK always-on started (ring_seconds={rs} "
            f"threshold_db={threshold_db} min_silence_ms={min_silence_ms})")


@drv.tool(
    "mic.rewind",
    "回溯最近 seconds 秒：把环形缓冲尾部拼成 WAV 落 var/ear/segments/rewind-<ts>.wav。"
    "常开模式未运行时报 ENOTACTIVE。",
    {"type": "object",
     "properties": {"seconds": {"type": "integer",
                                "description": "回溯秒数（默认 15）"}}},
)
def mic_rewind(seconds: int = 15) -> str:
    with _always_on_lock:
        running = _always_on_thread is not None and _always_on_thread.is_alive()
    if not running:
        return "ENOTACTIVE: always_on not running"
    seconds = max(1, int(seconds))
    with _ring_lock:  # 红线：环形缓冲读取持 _ring_lock
        pcm = b"".join(_ring)[-seconds * SAMPLE_RATE * 2:]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    out = _segments_dir() / f"rewind-{int(time.time())}.wav"
    out.write_bytes(buf.getvalue())
    return f"OK rewound {out} ({len(pcm) // 2} samples)"


@drv.tool("mic.always_on_stop", "停止常开线程：flush 最后一段未闭合有声区并清空环形缓冲",
          {"type": "object", "properties": {}})
def mic_always_on_stop() -> str:
    global _always_on_thread, _ring_seconds
    with _always_on_lock:
        th = _always_on_thread
    if th is None or not th.is_alive():
        return "OK always-on not running"
    _always_on_stop.set()
    th.join(timeout=5.0)
    with _always_on_lock:
        _always_on_thread = None
        _ring_seconds = 0
    with _ring_lock:
        _ring.clear()  # 停止即清空：不留音频残留（隐私）
    return "OK always-on stopped"


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
    with _always_on_lock:
        always_on = _always_on_thread is not None and _always_on_thread.is_alive()
        ring_seconds = _ring_seconds
    line = (f"recording={_recording} listening={listening} "
            f"segments={n_seg} device={device}")
    if _listen_error:
        line += f" error={_listen_error}"
    line += f" always_on={always_on} ring_seconds={ring_seconds}"
    if _always_on_error:
        line += f" ao_error={_always_on_error}"
    return line


if __name__ == "__main__":
    drv.serve_forever()
