"""laos.telemetry —— 埋点核心（设计 docs/design/2026-10-07-instrumentation-design.md）.

实现规格：v0.20.0 埋点设计的 §1 五原则 / §3 统一 schema / §6 保留与采样。
本模块是独立 JSONL 落盘发射器（装配层后续接线到 kernel.audit / 各驱动尾部；
裸解释器 import 零副作用——无 IO、无环境读取，构造 Emitter 才开文件）。

四条硬约束（红线落法）：

1. **零依赖**：纯 stdlib（json/os/threading/time/hashlib）。
2. **计数优先于内容**（设计 §1.2）：字段级允许表逐字段标
   明文(plain)/计数(count)/脱敏(redacted)三档；禁止级（request/response
   明文、音频字节、转写/refine 文本、唤醒词原文）**拒发整条事件**并落
   warn 行；内容类只允许 len / sha256 前 8 位 / 时长 / 语言码四种形态。
3. **节流必设**（设计 §1.4）：同 (event, module, session) 键 5s 窗口内
   首条即发、后续静默计数（take_throttled 取走）；窗口后首条携带
   `throttled: N`（被压制条数，设计 §3.1 节流元字段）。豁免：level=error、
   f.rec.bypass、l.sys.init、l.crash.recover(phase=detect)。
4. **LAOS_REC=0 联动**（设计 §1.5，读取口径同 drivers/drv_rec.py:91）：
   `a.*` 音频链路事件整体静默；s.asr.result / s.refine.delta 仅
   source=capture 时剥内容派生字段（*_sha8/*_len/duration_sec），
   source=file 照发（ASR 全本地与禁录两条红线互不扩大）；f.rec.bypass
   永不静默（它就是禁录态哨兵）。

写盘语义：追加流 + 原子换新。逐条 emit 落入 `<path>.part` 中转文件并
逐条 flush（崩溃不丢已发射事件——数据总在 .part，参照
corpus/venue_expansion/fetch_anthology.py write_jsonl 的 .part 先例，但
telemetry 是追加流：正式 path 只在 flush() 时整批并入完整行，轮转归档
（path → path.1，覆盖旧 .1）用 os.replace 原子换新文件。主文件永不出现
半截行；进程被杀只留 .part 残件，下次 flush 自动并入。

事件注册表：设计 §3 的 23 事件全量登记（L4/A4/S2/D5/P3/F5），逐字段
脱敏级别照抄 §3.2–3.7 字段表。注册表外事件只允许信封 + 空 fields
（防字段走私）。

信封（六键，独立落盘口径；接到 AuditLog.write() 时由审计流补 t/seq，
设计 §3.1）::

    {"ts": <monotonic ms>, "event": ..., "level": ...,
     "module": ..., "session": ..., "fields": {...}}
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable, Iterable

__all__ = [
    "TelemetryEmitter",
    "RedactionPolicy",
    "EVENT_FIELDS",
    "EVENT_FORBIDDEN",
    "GLOBAL_FORBIDDEN_FIELDS",
    "NEVER_THROTTLE_EVENTS",
    "sha8",
]

# ---------------------------------------------------------------------------
# 脱敏分级（设计 §1.2 四级；前三级允许，禁止级拒发）
# ---------------------------------------------------------------------------

LEVEL_PLAIN = "plain"        # 明文：标识符/计数/时延/配置值，无隐私面
LEVEL_COUNT = "count"        # 计数：只记次数/数量，不记内容
LEVEL_REDACTED = "redacted"  # 脱敏：len / sha256 前 8 位 / 时长 / 语言码
LEVEL_FORBIDDEN = "forbidden"  # 禁止：红线，永不入事件（拒发整条）


def sha8(text: str) -> str:
    """内容脱敏形态之一：sha256 前 8 位（设计 §1.2，记作 *_sha8 字段）。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# 事件注册表（设计 §3.2–3.7 逐字段表全量转录；23 事件 = L4+A4+S2+D5+P3+F5）
# ---------------------------------------------------------------------------

_PLAIN, _COUNT, _REDACTED = LEVEL_PLAIN, LEVEL_COUNT, LEVEL_REDACTED

EVENT_FIELDS: dict[str, dict[str, str]] = {
    # ---- L 生命周期（§3.2）----
    "l.sys.init": {
        "version": _PLAIN, "py_exec": _REDACTED, "platform_masked": _REDACTED,
        "drivers": _COUNT, "rec_enabled": _PLAIN, "asr_channel": _PLAIN,
        "ear_python_source": _PLAIN, "boot_count": _COUNT,
    },
    "l.driver.load": {
        "driver": _PLAIN, "tools": _COUNT, "ok": _PLAIN, "err": _PLAIN,
        "interpreter_source": _PLAIN, "channels_available": _PLAIN,
        "driver_pid": _PLAIN,
    },
    "l.driver.unload": {"driver": _PLAIN, "reason": _PLAIN},
    "l.crash.recover": {
        "driver": _PLAIN, "phase": _PLAIN, "err": _PLAIN,
        "uptime_s": _COUNT, "restarts": _COUNT,
    },
    # ---- A 音频链路（§3.3）----
    "a.mic.frame_overrun": {
        "queue": _PLAIN, "overruns": _COUNT, "dropped_frames": _COUNT,
        "recovered": _PLAIN,
    },
    "a.device.reopen": {
        "device": _REDACTED, "attempt": _COUNT, "backoff_ms": _COUNT,
        "err": _PLAIN, "ok": _PLAIN,
    },
    "a.vad.endpoint": {
        "duration_ms": _REDACTED, "start_ms": _REDACTED,
        "threshold_dbfs": _PLAIN, "sr": _PLAIN, "source": _PLAIN,
    },
    "a.mic.stream_error": {
        "err": _PLAIN, "phase": _PLAIN, "device_hint": _REDACTED,
    },
    # ---- S 语音服务（§3.4）----
    "s.asr.result": {
        "channel": _PLAIN, "ok": _PLAIN, "lang": _REDACTED,
        "latency_ms": _COUNT, "duration_sec": _REDACTED,
        "audio_sha8": _REDACTED, "text_len": _COUNT, "text_sha8": _REDACTED,
        "emotions_n": _COUNT, "endpoint_to_final_ms": _COUNT,
        "source": _PLAIN, "req_lang": _PLAIN,
    },
    "s.refine.delta": {
        "in_len": _COUNT, "out_len": _COUNT, "in_sha8": _REDACTED,
        "out_sha8": _REDACTED, "hits_filler": _COUNT, "hits_stutter": _COUNT,
        "hits_correction": _COUNT, "changed": _PLAIN,
    },
    # ---- D 对话调度（§3.5）----
    "d.dialog.turn": {
        "turn_id": _PLAIN, "route": _PLAIN, "knowledge_id": _PLAIN,
        "knowledge_score": _PLAIN, "retrieval_ms": _COUNT, "ok": _PLAIN,
        "interrupted": _PLAIN, "generation": _COUNT, "first_text_ms": _COUNT,
        "first_audio_ms": _COUNT, "prefill_ms": _COUNT, "generate_ms": _COUNT,
        "tokens": _COUNT, "total_ms": _COUNT, "pause_observation_ms": _COUNT,
        "speculative": _PLAIN, "speculative_cancelled": _PLAIN,
        "merged_segments": _COUNT, "speculative_tokens_wasted": _COUNT,
        "dropped_latest_only": _COUNT, "utter_len": _COUNT,
        "utter_sha8": _REDACTED, "chunks_out": _COUNT,
    },
    "d.wake.state_change": {
        "from": _PLAIN, "to": _PLAIN, "reason": _PLAIN, "turns": _COUNT,
        "session_ms": _COUNT,
    },
    "d.barge_in": {"generation": _COUNT, "source": _PLAIN, "state": _PLAIN},
    "d.mic.guard": {
        "action": _PLAIN, "blocked_ms": _COUNT, "aec_ready": _PLAIN,
        "post_tts_guard_ms": _PLAIN,
    },
    "d.speculative.cancel": {
        "dialog_id": _PLAIN, "reason": _PLAIN, "merged": _PLAIN,
        "tokens_wasted_est": _COUNT,
    },
    # ---- P 性能（§3.6）----
    "p.rtf": {"channel": _PLAIN, "n": _COUNT, "p50": _COUNT, "p95": _COUNT,
              "max": _COUNT},
    "p.memory": {"rss_kb": _COUNT, "vms_kb": _COUNT, "audit_records": _COUNT,
                 "uptime_s": _COUNT},
    "p.jsonl.water": {"file": _PLAIN, "lines": _COUNT, "bytes": _COUNT,
                      "watermark_hit": _PLAIN},
    # ---- F 降级与故障（§3.7）----
    "f.tts.fallback": {
        "backend": _PLAIN, "stage": _PLAIN, "sentence_emitted": _PLAIN,
        "route": _PLAIN,
    },
    "f.asr.channel_fail": {"channel": _PLAIN, "err": _PLAIN,
                           "requested_lang": _PLAIN},
    "f.model.load_fail": {
        "model": _REDACTED, "kind": _PLAIN, "err": _PLAIN,
        "interpreter_source": _PLAIN,
    },
    "f.rec.bypass": {"tool": _PLAIN, "pid": _PLAIN, "detail": _PLAIN},
    "f.audit.gap": {"expected": _COUNT, "seen": _COUNT, "gap": _COUNT,
                    "window_ms": _COUNT},
}

# 逐事件禁止对照行（设计 §3 各内容接触点表尾"禁止对照"）：
# 命中即拒发整条事件 + warn 落盘——不是静默丢弃，是留证据的拒绝。
EVENT_FORBIDDEN: dict[str, frozenset[str]] = {
    "a.vad.endpoint": frozenset({"wav", "audio", "pcm"}),
    "s.asr.result": frozenset({"text", "emotions", "wav", "audio", "pcm",
                                "audio_bytes"}),
    "s.refine.delta": frozenset({"text", "in_text", "out_text"}),
    "d.dialog.turn": frozenset({"request", "response", "utterance", "answer",
                                 "text"}),
    "d.wake.state_change": frozenset({"text", "wake_word", "sleep_word"}),
}

# 全局禁止名单（红线内容形态；无论事件是否注册，命中即拒发）。
# 第一道防线是允许表本身（不在表内的字段一律剥除），本名单是第二道：
# 已知内容走私名给"拒发 + warn"的显式拒绝，供代码评审与面板直读。
GLOBAL_FORBIDDEN_FIELDS = frozenset({
    "text", "wav", "audio", "audio_bytes", "pcm", "request", "response",
    "emotions", "transcript", "asr_text", "in_text", "out_text",
    "wake_word", "sleep_word", "utterance", "answer",
})

# 永不节流事件（设计 §1.4 豁免清单；level=error 与
# l.crash.recover(phase=detect) 在 Emitter 里按条件判）
NEVER_THROTTLE_EVENTS = frozenset({"f.rec.bypass", "l.sys.init"})

# REC=0 时整体静默的事件前缀（设计 §1.5 表：a.vad.endpoint / a.mic.*）
_REC_SILENCE_PREFIX = "a."
# REC=0 且 source=capture 时剥内容派生字段的事件（设计 §1.5 表）
_REC_STRIP_CAPTURE_EVENTS = frozenset({"s.asr.result", "s.refine.delta"})
# 内容派生字段形态（§1.5 原文：audio_sha8/text_sha8/*_len/duration_sec）
def _is_content_derived(name: str) -> bool:
    return name.endswith("_sha8") or name.endswith("_len") or name == "duration_sec"


# ---------------------------------------------------------------------------
# RedactionPolicy —— 事件 → 字段允许表（三档允许 + 禁止级拒发）
# ---------------------------------------------------------------------------

class RedactionPolicy:
    """按注册表逐事件校验 fields：允许的过、未列出的剥、禁止级的拒。

    类属性四级脱敏级别即模块级常量（设计 §1.2）：
    LEVEL_PLAIN / LEVEL_COUNT / LEVEL_REDACTED / LEVEL_FORBIDDEN。

    - `check(event, fields)` → (clean_fields, rejected_forbidden_names)
      * 字段在事件允许表内 → 保留（三档级别只是标注，不做值形态改写；
        len/sha8 的派生由发射点调用 sha8()/len() 完成——设计 §3 来源函数列）
      * 字段不在表内 → 剥除（防走私：未登记字段永不落盘）
      * 字段命中禁止级（逐事件禁止表或全局名单）→ 列入 rejected，
        调用方（Emitter）拒发整条事件并写 warn 行
      * 事件未注册 → clean 恒为 {}（信封 + 空 fields），但命中全局禁止
        名单的字段仍列入 rejected
    """

    LEVEL_PLAIN = LEVEL_PLAIN
    LEVEL_COUNT = LEVEL_COUNT
    LEVEL_REDACTED = LEVEL_REDACTED
    LEVEL_FORBIDDEN = LEVEL_FORBIDDEN

    def __init__(
        self,
        event_fields: dict[str, dict[str, str]] | None = None,
        event_forbidden: dict[str, Iterable[str]] | None = None,
        global_forbidden: Iterable[str] = GLOBAL_FORBIDDEN_FIELDS,
    ):
        self.event_fields = event_fields if event_fields is not None else EVENT_FIELDS
        self.event_forbidden = {
            k: frozenset(v) for k, v in (event_forbidden or EVENT_FORBIDDEN).items()
        }
        self.global_forbidden = frozenset(global_forbidden)

    def is_registered(self, event: str) -> bool:
        return event in self.event_fields

    def field_level(self, event: str, field: str) -> str | None:
        """字段脱敏级别；未注册事件或未列出字段 → None。"""
        return self.event_fields.get(event, {}).get(field)

    def forbidden_fields(self, event: str) -> frozenset[str]:
        """事件的有效禁止集 = 逐事件禁止表 ∪ 全局名单。"""
        return self.event_forbidden.get(event, frozenset()) | self.global_forbidden

    def check(self, event: str, fields: dict | None) -> tuple[dict, list[str]]:
        fields = fields or {}
        if not isinstance(fields, dict):
            raise TypeError(f"fields must be dict, got {type(fields).__name__}")
        forbidden = self.forbidden_fields(event)
        rejected = sorted(n for n in fields if n in forbidden)
        if not self.is_registered(event):
            # 注册表外事件：只允许信封 + 空 fields（防字段走私）
            return {}, rejected
        allow = self.event_fields[event]
        clean = {n: v for n, v in fields.items()
                 if n not in forbidden and n in allow}
        return clean, rejected


# ---------------------------------------------------------------------------
# TelemetryEmitter —— JSONL 追加流发射器（节流/脱敏/轮转/REC 联动）
# ---------------------------------------------------------------------------

class TelemetryEmitter:
    """埋点事件发射器。用法::

        em = TelemetryEmitter(workdir / "telemetry.jsonl")
        em.emit("d.wake.state_change", module="wakegate", session=sid,
                fields={"from": "sleeping", "to": "listening", ...})
        em.flush()

    线程安全（粗粒度锁）；emit 返回 bool：True=已受理落盘（在 .part），
    False=被节流/REC 静默/禁止级拒发（拒发时另落 telemetry.reject warn 行）。
    """

    def __init__(
        self,
        path,
        max_bytes: int = 64 * 1024 * 1024,
        throttle_sec: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
        policy: RedactionPolicy | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_bytes)
        self.throttle_sec = float(throttle_sec)
        self._clock = clock
        self.policy = policy if policy is not None else RedactionPolicy()
        self._lock = threading.Lock()
        self._part = self.path.with_name(self.path.name + ".part")
        self._fh = self._part.open("a", encoding="utf-8", newline="\n")
        # 崩溃残件语义：构造时收养已存在的 .part（下次 flush 并入主文件）
        self._part_size = os.fstat(self._fh.fileno()).st_size
        self._base_size = (self.path.stat().st_size
                           if self.path.exists() else 0)
        # 节流状态：key=(event, module, session) → (上次发射时刻, 窗口内被压制数)
        self._throttle_state: dict[tuple, tuple[float | None, int]] = {}
        self._throttled_total = 0
        self._closed = False

    # -- 公开接口 ----------------------------------------------------------

    def emit(self, event: str, level: str = "info", module: str = "",
             session: str = "", fields: dict | None = None) -> bool:
        """发射一条埋点事件；返回是否受理（False=节流/静默/拒发）。"""
        if level not in ("info", "warn", "error"):
            raise ValueError(f"invalid level {level!r}: info|warn|error")
        if not event or not isinstance(event, str):
            raise ValueError("event must be a non-empty string")
        raw_fields = fields or {}

        # -- LAOS_REC=0 联动（设计 §1.5；读取口径同 drv_rec.py:91）--
        rec_off = os.environ.get("LAOS_REC", "1") == "0"
        if rec_off and event.startswith(_REC_SILENCE_PREFIX):
            return False  # a.* 音频链路事件整体静默（f.* 哨兵不受影响）

        # -- 脱敏强制（设计 §1.2）：禁止级拒发整条 + warn 落盘 --
        clean, rejected = self.policy.check(event, raw_fields)
        if rejected:
            with self._lock:
                self._write_reject_warn(event, rejected)
            return False

        # -- REC=0 内容派生字段剥离（仅 source=capture；file 照发）--
        if (rec_off and event in _REC_STRIP_CAPTURE_EVENTS
                and raw_fields.get("source") == "capture"):
            clean = {n: v for n, v in clean.items()
                     if not _is_content_derived(n)}

        # -- 节流（设计 §1.4）--
        suppressed, release_count = self._throttle_check(
            event, level, module, session, raw_fields)
        if suppressed:
            return False

        envelope = {
            "ts": round(self._clock() * 1000, 3),  # monotonic 毫秒（§3.1）
            "event": event,
            "level": level,
            "module": module,
            "session": session,
            "fields": clean,
        }
        if release_count > 0:
            envelope["throttled"] = release_count  # 节流元字段（§3.1）
        with self._lock:
            self._write_line(envelope)
        return True

    def flush(self) -> None:
        """把 .part 中转的完整行整批并入正式文件（逐行 parse 保证）。"""
        with self._lock:
            self._merge_part()

    def take_throttled(self) -> int:
        """取走（并清零）累计被节流压制的事件数。"""
        with self._lock:
            n = self._throttled_total
            self._throttled_total = 0
            return n

    def close(self) -> None:
        """flush 后关闭句柄；之后再 emit 抛 RuntimeError。"""
        with self._lock:
            if not self._closed:
                self._merge_part()
                self._fh.close()
                self._closed = True

    def __enter__(self) -> "TelemetryEmitter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- 节流（设计 §1.4：5s 窗口 + 豁免清单）------------------------------

    def _throttle_check(self, event: str, level: str, module: str,
                        session: str, raw_fields: dict) -> tuple[bool, int]:
        """返回 (是否压制, 窗口释放携带的被压制数)。"""
        exempt = (
            level == "error"
            or event in NEVER_THROTTLE_EVENTS
            or (event == "l.crash.recover"
                and raw_fields.get("phase") == "detect")
        )
        with self._lock:
            now = self._clock()
            key = (event, module, session)
            last, suppressed = self._throttle_state.get(key, (None, 0))
            if exempt:
                # 豁免事件不查窗，但照常刷新窗口时钟（供同键非豁免路径用）
                self._throttle_state[key] = (now, suppressed)
                return False, 0
            if last is not None and (now - last) < self.throttle_sec:
                self._throttle_state[key] = (last, suppressed + 1)
                self._throttled_total += 1
                return True, 0
            release = suppressed
            self._throttle_state[key] = (now, 0)
            return False, release

    # -- 写盘（.part 中转 + os.replace 轮转换新）---------------------------

    def _write_reject_warn(self, event: str, rejected: list[str]) -> None:
        """禁止级拒发的 warn 行（落盘留证据，设计 §1.2；不经策略/节流）。"""
        self._write_line({
            "ts": round(self._clock() * 1000, 3),
            "event": "telemetry.reject",
            "level": "warn",
            "module": "telemetry",
            "session": "",
            "fields": {
                "reason": "forbidden_field",
                "event": event,
                "rejected": rejected,
            },
        })

    def _write_line(self, envelope: dict) -> None:
        if self._closed:
            raise RuntimeError("emitter closed")
        line = json.dumps(envelope, ensure_ascii=False)
        # U+2028/U+2029/U+0085 是 JSON 合法但会被 splitlines 断行的字符，
        # 转义成 \\u2028 序列——值不变、逐行 parse 不崩（write_jsonl 先例）
        line = (line.replace("\u2028", "\\u2028")
                    .replace("\u2029", "\\u2029")
                    .replace("\x85", "\\u0085"))
        payload = (line + "\n").encode("utf-8")
        if (self._base_size + self._part_size + len(payload)
                > self.max_bytes):
            self._rotate()  # 单文件达 max_bytes：先归档再写（§6.2 容量口径）
        self._fh.write(line + "\n")
        self._fh.flush()  # 逐条 flush 进 .part（§6.4：崩溃不丢已发射事件）
        self._part_size += len(payload)

    def _rotate(self) -> None:
        """归档当前代：.part 并入 path → path 原子改名 path.1（覆盖旧 .1）。"""
        self._merge_part()
        if self.path.exists():
            os.replace(self.path, self.path.with_name(self.path.name + ".1"))
        self._base_size = 0

    def _merge_part(self) -> None:
        """把 .part 完整行整批并入正式文件（主文件永不出现半截行）。"""
        self._fh.flush()
        if self._part_size == 0:
            return
        with open(self._part, "rb") as src, open(self.path, "ab") as out:
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        self._base_size += self._part_size
        self._fh.close()
        self._fh = self._part.open("w", encoding="utf-8", newline="\n")
        self._part_size = 0
