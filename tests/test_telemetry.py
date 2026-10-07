# tests/test_telemetry.py
"""laos.telemetry —— 埋点核心（设计 docs/design/2026-10-07-instrumentation-design.md）.

覆盖 task-1 brief Step 1 清单：
  - schema 信封六键（ts/event/level/module/session/fields）
  - 禁止级字段拒发 + warn 落盘
  - 节流 5s 同类丢弃 + take_throttled 计数（豁免：error 级/f.rec.bypass/
    l.sys.init/l.crash.recover phase=detect）
  - 轮转：单文件达 max_bytes → path.1 后缀归档（覆盖旧 .1）
  - 原子写：.part 中转，flush 前主文件不出现半截内容
  - LAOS_REC=0 时 a.* 音频类事件整体静默；s.asr.result/s.refine.delta
    仅 source=capture 时剥内容派生字段（source=file 照发）
  - flush 后文件完整可逐行 parse（含 U+2028 断行转义）
  - error 级事件 stderr 镜像一行（§6.4；静默事件不镜像）
  - clock 注入（ts=monotonic ms + 节流窗口共用同一时钟）

    python -m unittest tests.test_telemetry -v
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos import telemetry as tel
from laos.telemetry import TelemetryEmitter


class FakeClock:
    """可手动推进的单调时钟（clock 注入用）。"""

    def __init__(self, start: float = 0.0):
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


class TelemetryBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "telemetry.jsonl"
        self.part = self.dir / "telemetry.jsonl.part"
        self.clock = FakeClock(100.0)
        self.em = TelemetryEmitter(
            self.path, max_bytes=64 * 1024 * 1024,
            throttle_sec=5.0, clock=self.clock,
        )
        self.addCleanup(self.em.close)  # Windows：句柄不关，临时目录删不掉

    def _emitter(self, path=None, clock=None, **kw):
        em = TelemetryEmitter(path or self.path, clock=clock or self.clock,
                              **kw)
        self.addCleanup(em.close)
        return em

    def read_lines(self, p=None):
        p = Path(p) if p is not None else self.path
        if not p.exists():
            return []
        rows = []
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                rows.append(json.loads(ln))
        return rows


class TestEnvelope(TelemetryBase):
    def test_envelope_has_exactly_six_keys(self):
        ok = self.em.emit(
            "d.wake.state_change", module="wakegate", session="a3f9c1d2",
            fields={"from": "sleeping", "to": "listening", "reason": "wake",
                    "turns": 0, "session_ms": 0},
        )
        self.assertTrue(ok)
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            set(rows[0].keys()),
            {"ts", "event", "level", "module", "session", "fields"},
        )
        self.assertEqual(rows[0]["event"], "d.wake.state_change")
        self.assertEqual(rows[0]["level"], "info")
        self.assertEqual(rows[0]["module"], "wakegate")
        self.assertEqual(rows[0]["session"], "a3f9c1d2")
        self.assertEqual(rows[0]["fields"]["from"], "sleeping")

    def test_ts_is_monotonic_ms_from_injected_clock(self):
        clock = FakeClock(1.5)
        em = self._emitter(path=self.dir / "clock.jsonl", clock=clock)
        self.assertTrue(em.emit("l.sys.init", module="kernel",
                                fields={"version": "0.20.0"}))
        clock.advance(0.25)
        self.assertTrue(em.emit("l.driver.unload", module="kernel",
                                fields={"driver": "ear", "reason": "shutdown"}))
        em.flush()
        rows = self.read_lines(self.dir / "clock.jsonl")
        self.assertEqual(rows[0]["ts"], 1500.0)
        self.assertEqual(rows[1]["ts"], 1750.0)

    def test_level_must_be_info_warn_error(self):
        with self.assertRaises(ValueError):
            self.em.emit("l.sys.init", level="debug")
        with self.assertRaises(ValueError):
            self.em.emit("", level="info")

    def test_error_level_mirrors_to_stderr(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertTrue(self.em.emit(  # error 级 → stderr 镜像一行
                "f.asr.channel_fail", level="error", module="drv_ear",
                fields={"channel": "funasr", "err": "RuntimeError: boom",
                        "requested_lang": "zh"}))
            self.assertTrue(self.em.emit(  # warn 级 → 不镜像
                "f.model.load_fail", level="warn", module="drv_ear",
                fields={"model": "m", "kind": "sensevoice", "err": "e",
                        "interpreter_source": "env"}))
        mirrored = [ln for ln in buf.getvalue().splitlines() if ln.strip()]
        self.assertEqual(len(mirrored), 1)
        row = json.loads(mirrored[0])  # 镜像行是可 parse 的完整事件 JSON
        self.assertEqual(row["event"], "f.asr.channel_fail")
        self.assertEqual(row["level"], "error")
        self.assertEqual(row["fields"]["channel"], "funasr")
        # 镜像不替代落盘：两条都仍在文件里
        self.em.flush()
        self.assertEqual([r["event"] for r in self.read_lines()],
                         ["f.asr.channel_fail", "f.model.load_fail"])

    def test_silenced_event_does_not_mirror_to_stderr(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), \
                mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            self.assertFalse(self.em.emit(  # a.* 静默 → 也不镜像
                "a.mic.stream_error", level="error", module="drv_mic",
                fields={"err": "EIO", "phase": "read", "device_hint": "m"}))
        self.assertEqual(buf.getvalue(), "")


class TestRedaction(TelemetryBase):
    def test_forbidden_field_rejects_and_writes_warn(self):
        ok = self.em.emit(
            "s.asr.result", module="drv_ear",
            fields={"channel": "funasr", "ok": True, "text": "你好世界"},
        )
        self.assertFalse(ok)  # 拒发
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 1)
        warn = rows[0]
        self.assertEqual(warn["event"], "telemetry.reject")
        self.assertEqual(warn["level"], "warn")
        self.assertEqual(warn["fields"]["event"], "s.asr.result")
        self.assertIn("text", warn["fields"]["rejected"])
        # 红线：明文内容永不出现在落盘行里
        raw = self.path.read_text(encoding="utf-8")
        self.assertNotIn("你好世界", raw)

    def test_unregistered_event_envelope_only_empty_fields(self):
        ok = self.em.emit("x.custom.ping", fields={"foo": 1, "bar": "baz"})
        self.assertTrue(ok)
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "x.custom.ping")
        self.assertEqual(rows[0]["fields"], {})

    def test_unregistered_event_with_forbidden_name_rejected(self):
        ok = self.em.emit("x.custom.ping", fields={"text": "hi"})
        self.assertFalse(ok)
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(rows[0]["event"], "telemetry.reject")
        self.assertIn("text", rows[0]["fields"]["rejected"])

    def test_unlisted_field_stripped_but_allowed_kept(self):
        ok = self.em.emit(
            "s.asr.result", module="drv_ear",
            fields={"channel": "funasr", "ok": True, "secret_metric": 42},
        )
        self.assertTrue(ok)
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(rows[0]["fields"], {"channel": "funasr", "ok": True})

    def test_policy_check_api(self):
        pol = tel.RedactionPolicy()
        clean, rejected = pol.check(
            "d.dialog.turn",
            {"turn_id": 1, "route": "tts", "request": "明文", "response": "答案"},
        )
        self.assertEqual(clean, {"turn_id": 1, "route": "tts"})
        self.assertEqual(sorted(rejected), ["request", "response"])
        clean2, rejected2 = pol.check("x.unknown", {"a": 1})
        self.assertEqual(clean2, {})
        self.assertEqual(rejected2, [])
        self.assertEqual(pol.field_level("s.asr.result", "text_sha8"),
                         tel.RedactionPolicy.LEVEL_REDACTED)
        self.assertIsNone(pol.field_level("s.asr.result", "nope"))
        self.assertFalse(pol.is_registered("x.unknown"))

    def test_registry_covers_23_events_and_core_field_sets(self):
        self.assertEqual(len(tel.EVENT_FIELDS), 23)
        core = {
            "d.wake.state_change": {"from", "to", "reason", "turns", "session_ms"},
            "d.dialog.turn": {"turn_id", "route", "utter_len", "utter_sha8",
                              "interrupted", "generation", "tokens", "total_ms"},
            "s.asr.result": {"channel", "ok", "lang", "latency_ms",
                             "duration_sec", "audio_sha8", "text_len",
                             "text_sha8", "source"},
            "s.refine.delta": {"in_len", "out_len", "in_sha8", "out_sha8",
                               "hits_filler", "hits_stutter",
                               "hits_correction", "changed"},
            "a.mic.frame_overrun": {"queue", "overruns", "dropped_frames",
                                    "recovered"},
            "f.tts.fallback": {"backend", "stage", "sentence_emitted", "route"},
        }
        for ev, want in core.items():
            self.assertLessEqual(want, set(tel.EVENT_FIELDS[ev]), ev)
        # 禁止对照行已入注册表（设计 §3 禁止对照）
        for ev in ("s.asr.result", "d.dialog.turn", "s.refine.delta",
                   "d.wake.state_change", "a.vad.endpoint"):
            self.assertIn(ev, tel.EVENT_FORBIDDEN, ev)

    def test_sha8_helper(self):
        self.assertEqual(
            tel.sha8("abc"),
            hashlib.sha256(b"abc").hexdigest()[:8],
        )


class TestThrottle(TelemetryBase):
    VAD = {"duration_ms": 1200, "start_ms": 300, "threshold_dbfs": -35.0,
           "sr": 16000, "source": "rec"}

    def _vad(self, **kw):
        return self.em.emit("a.vad.endpoint", **kw)

    def test_same_key_drops_within_window_and_counts(self):
        self.assertTrue(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.assertFalse(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.assertFalse(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.assertEqual(self.em.take_throttled(), 2)
        self.assertEqual(self.em.take_throttled(), 0)  # 取走即清零
        self.em.flush()
        self.assertEqual(len(self.read_lines()), 1)

    def test_release_after_window_carries_suppressed_count(self):
        self.assertTrue(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.assertFalse(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.assertFalse(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.clock.advance(5.0)  # 恰达窗口边界 → 放行
        self.assertTrue(self._vad(module="drv_rec", session="s1", fields=self.VAD))
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 2)
        self.assertNotIn("throttled", rows[0])
        self.assertEqual(rows[1].get("throttled"), 2)

    def test_throttle_key_is_event_module_session(self):
        self.assertTrue(self._vad(module="drv_rec", session="a", fields=self.VAD))
        self.assertTrue(self._vad(module="drv_rec", session="b", fields=self.VAD))
        self.assertTrue(self._vad(module="wakegate", session="a", fields=self.VAD))
        self.assertTrue(self.em.emit("a.mic.stream_error", module="drv_rec",
                                     session="a",
                                     fields={"err": "EIO", "phase": "read",
                                             "device_hint": "mask"}))
        self.assertEqual(self.em.take_throttled(), 0)

    def test_exemptions_never_throttled(self):
        for _ in range(3):  # error 级永不节流
            self.assertTrue(self.em.emit(
                "f.asr.channel_fail", level="error", module="drv_ear",
                fields={"channel": "funasr", "err": "RuntimeError",
                        "requested_lang": "zh"}))
        self.assertTrue(self.em.emit(  # f.rec.bypass 永不节流
            "f.rec.bypass", module="telemetry",
            fields={"tool": "mic.record", "pid": 1042, "detail": "seq=7"}))
        self.assertTrue(self.em.emit(
            "f.rec.bypass", module="telemetry",
            fields={"tool": "mic.record", "pid": 1042, "detail": "seq=8"}))
        self.assertTrue(self.em.emit(  # l.sys.init 永不节流
            "l.sys.init", module="kernel",
            fields={"version": "0.20.0", "drivers": 3, "rec_enabled": True}))
        self.assertTrue(self.em.emit(
            "l.sys.init", module="kernel",
            fields={"version": "0.20.0", "drivers": 3, "rec_enabled": True}))
        self.assertEqual(self.em.take_throttled(), 0)

    def test_crash_recover_detect_exempt_recovered_not(self):
        det = {"driver": "ear", "phase": "detect", "err": "EIO",
               "uptime_s": 12.0, "restarts": 0}
        self.assertTrue(self.em.emit("l.crash.recover", module="kernel", fields=det))
        self.assertTrue(self.em.emit("l.crash.recover", module="kernel", fields=det))
        rec = dict(det, phase="recovered")
        self.assertFalse(self.em.emit("l.crash.recover", module="kernel", fields=rec))
        self.assertEqual(self.em.take_throttled(), 1)


class TestRotationAndAtomicWrite(TelemetryBase):
    def _small_emitter(self):
        return self._emitter(max_bytes=1, throttle_sec=5.0)

    def test_rotation_archives_to_dot1_overwriting_old(self):
        em = self._small_emitter()
        f1 = {"version": "0.20.0", "drivers": 3, "rec_enabled": True}
        f2 = {"version": "0.20.0", "drivers": 4, "rec_enabled": False}
        f3 = {"version": "0.20.0", "drivers": 5, "rec_enabled": True}
        self.assertTrue(em.emit("l.sys.init", module="kernel", fields=f1))
        self.assertTrue(em.emit("l.sys.init", module="kernel", fields=f2))  # 触发轮转
        self.assertTrue(em.emit("l.sys.init", module="kernel", fields=f3))  # 再轮转，.1 被覆盖
        em.flush()
        main_rows = self.read_lines(self.path)
        arch_rows = self.read_lines(str(self.path) + ".1")
        self.assertEqual(len(main_rows), 1)
        self.assertEqual(main_rows[0]["fields"]["drivers"], 5)
        self.assertEqual(len(arch_rows), 1)  # 单槽 .1：旧归档被覆盖
        self.assertEqual(arch_rows[0]["fields"]["drivers"], 4)

    def test_atomic_part_transit_before_flush(self):
        self.assertTrue(self.em.emit(
            "d.wake.state_change", module="wakegate", session="boot1",
            fields={"from": "sleeping", "to": "listening", "reason": "wake",
                    "turns": 0, "session_ms": 0}))
        self.assertTrue(self.em.emit(
            "d.wake.state_change", module="wakegate", session="boot2",
            fields={"from": "listening", "to": "processing", "reason": "speech",
                    "turns": 1, "session_ms": 800}))
        # flush 前：主文件不存在（无半截内容），.part 已逐条落盘
        self.assertFalse(self.path.exists())
        part_text = self.part.read_text(encoding="utf-8")
        self.assertEqual(part_text.count("\n"), 2)
        # flush 后：主文件完整可逐行 parse，.part 清空
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["fields"]["turns"], 1)
        self.assertEqual(self.part.read_text(encoding="utf-8").strip(), "")

    def test_part_crash_residue_recovered_on_next_flush(self):
        residue = {"ts": 1.0, "event": "l.sys.init", "level": "info",
                   "module": "kernel", "session": "", "fields": {}}
        self.part.write_text(json.dumps(residue) + "\n", encoding="utf-8")
        em = self._emitter()
        self.assertTrue(em.emit("l.driver.unload", module="kernel",
                                fields={"driver": "ear", "reason": "shutdown"}))
        em.flush()
        rows = self.read_lines()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["event"], "l.sys.init")
        self.assertEqual(rows[1]["event"], "l.driver.unload")

    def test_flush_yields_parseable_lines_with_unicode_breaks(self):
        for i in range(5):
            self.clock.advance(5.0)  # 避开同键节流（l.driver.load 非豁免）
            self.assertTrue(self.em.emit(
                "l.driver.load", module="kernel",
                fields={"driver": f"d{i}", "tools": 3, "ok": True,
                        "err": "x\u2028y\u2029z", "interpreter_source": "env",
                        "channels_available": ["funasr", "server"],
                        "driver_pid": 1000 + i}))
        self.em.flush()
        text = self.path.read_text(encoding="utf-8")
        raw_lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertEqual(len(raw_lines), 5)  # U+2028/2029 已转义，不产生断行
        for ln in raw_lines:
            row = json.loads(ln)
            self.assertEqual(row["fields"]["err"], "x\u2028y\u2029z")


class TestRecGate(TelemetryBase):
    def test_rec0_silences_audio_events_not_others(self):
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            self.assertFalse(self.em.emit(
                "a.vad.endpoint", module="drv_rec",
                fields={"duration_ms": 900, "start_ms": 0,
                        "threshold_dbfs": -35.0, "sr": 16000, "source": "rec"}))
            self.assertFalse(self.em.emit(
                "a.mic.stream_error", module="drv_mic",
                fields={"err": "EIO", "phase": "read", "device_hint": "m"}))
            self.assertTrue(self.em.emit(
                "d.wake.state_change", module="wakegate",
                fields={"from": "sleeping", "to": "listening", "reason": "wake",
                        "turns": 0, "session_ms": 0}))
            # f.rec.bypass 是禁录态哨兵：永不静默
            self.assertTrue(self.em.emit(
                "f.rec.bypass", level="error", module="telemetry",
                fields={"tool": "mic.record", "pid": 7, "detail": "seq=3"}))
        self.em.flush()
        rows = self.read_lines()
        self.assertEqual([r["event"] for r in rows],
                         ["d.wake.state_change", "f.rec.bypass"])

    def test_rec0_strips_capture_content_fields_for_asr(self):
        fields = {"channel": "funasr", "ok": True, "latency_ms": 650.0,
                  "audio_sha8": "abcd1234", "text_len": 42,
                  "text_sha8": "ffff0000", "duration_sec": 3.2,
                  "source": "capture", "req_lang": "zh"}
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            self.assertTrue(self.em.emit("s.asr.result", module="drv_ear",
                                         fields=fields))
        self.em.flush()
        got = self.read_lines()[0]["fields"]
        for gone in ("audio_sha8", "text_sha8", "text_len", "duration_sec"):
            self.assertNotIn(gone, got)
        for keep in ("channel", "ok", "latency_ms", "source", "req_lang"):
            self.assertIn(keep, got)

    def test_rec0_file_source_asr_fields_pass_through(self):
        fields = {"channel": "funasr", "ok": True, "latency_ms": 650.0,
                  "audio_sha8": "abcd1234", "text_len": 42,
                  "text_sha8": "ffff0000", "duration_sec": 3.2,
                  "source": "file", "req_lang": "zh"}
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            self.assertTrue(self.em.emit("s.asr.result", module="drv_ear",
                                         fields=fields))
        self.em.flush()
        got = self.read_lines()[0]["fields"]
        self.assertEqual(got["audio_sha8"], "abcd1234")
        self.assertEqual(got["duration_sec"], 3.2)

    def test_rec0_strips_capture_content_fields_for_refine(self):
        fields = {"in_len": 10, "out_len": 8, "in_sha8": "11111111",
                  "out_sha8": "22222222", "hits_filler": 2, "hits_stutter": 0,
                  "hits_correction": 1, "changed": True, "source": "capture"}
        with mock.patch.dict(os.environ, {"LAOS_REC": "0"}):
            self.assertTrue(self.em.emit("s.refine.delta", module="refiner",
                                         fields=dict(fields)))
        self.em.flush()
        got = self.read_lines()[0]["fields"]
        for gone in ("in_len", "out_len", "in_sha8", "out_sha8"):
            self.assertNotIn(gone, got)
        self.assertEqual(got["hits_filler"], 2)
        self.assertEqual(got["changed"], True)


if __name__ == "__main__":
    unittest.main()
