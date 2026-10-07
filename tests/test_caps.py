# tests/test_caps.py
"""caps —— Agent 工具能力注册表：caller 分级 / 权限位 / 生命周期 / LLM 可见域。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_caps -v

来源：espressif/esp-claw claw_cap.h 取长补短（2026-10-08 复现波次，
docs/research/2026-10-08-espclaw-vs-muse-agent-core.md §五）：
caller 五级（SYSTEM/AGENT/CONSOLE/SUB_AGENT）、权限位（RESTRICTED/
ROOT_AGENT_ONLY/CALLABLE_BY_LLM）、能力状态机（REGISTERED→STARTED→
DISABLED，DRAINING 排空）、per-session LLM 可见域。laos 叙事：Agent
调工具 = 进程调 syscall，能力表 = syscall 表的权限位治理。
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos import caps  # noqa: E402
from laos.caps import (  # noqa: E402
    CalCap, Caller, CapFlag, CapKind, CapState, CapabilityDescriptor,
)


def _descriptor(cid="cap.files.read", *, kind=CapKind.CALLABLE,
                flags=CapFlag.CALLABLE_BY_LLM, execute=None, family="files"):
    return CapabilityDescriptor(
        id=cid, name=cid.split(".")[-1], family=family, kind=kind, flags=flags,
        description="test cap", input_schema={"type": "object"},
        execute=execute or (lambda payload, ctx: {"ok": True, "in": payload}))


class TestRegisterAndStates(unittest.TestCase):
    def test_register_defaults_to_registered(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        self.assertEqual(reg.state("cap.files.read"), CapState.REGISTERED)

    def test_duplicate_id_rejected(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        with self.assertRaisesRegex(ValueError, "EEXIST"):
            reg.register(_descriptor())

    def test_enable_disable_state_machine(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        reg.enable("cap.files.read")
        self.assertEqual(reg.state("cap.files.read"), CapState.STARTED)
        reg.disable("cap.files.read")
        self.assertEqual(reg.state("cap.files.read"), CapState.DISABLED)

    def test_enable_unknown_key_error(self):
        reg = caps.CapRegistry()
        with self.assertRaises(KeyError):
            reg.enable("nope")

    def test_unregister_removes(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        reg.unregister("cap.files.read")
        with self.assertRaises(KeyError):
            reg.state("cap.files.read")


class TestCallSemantics(unittest.TestCase):
    def _started(self, desc=None):
        reg = caps.CapRegistry()
        reg.register(desc or _descriptor())
        reg.enable((desc or _descriptor()).id)
        return reg

    def test_call_executes_with_context(self):
        reg = self._started()
        out = reg.call("cap.files.read", {"path": "a.txt"},
                       caller=Caller.AGENT, session_id="s1")
        self.assertEqual(out, {"ok": True, "in": {"path": "a.txt"}})

    def test_call_unknown_key_error(self):
        with self.assertRaises(KeyError):
            caps.CapRegistry().call("nope", {}, caller=Caller.SYSTEM)

    def test_call_not_started_rejected(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        with self.assertRaisesRegex(RuntimeError, "EACCES|state"):
            reg.call("cap.files.read", {}, caller=Caller.SYSTEM)

    def test_event_source_not_callable(self):
        reg = self._started(
            _descriptor("cap.btn.press", kind=CapKind.EVENT_SOURCE,
                        flags=CapFlag.EMITS_EVENTS))
        with self.assertRaisesRegex(ValueError, "EINVAL"):
            reg.call("cap.btn.press", {}, caller=Caller.SYSTEM)

    def test_hybrid_is_callable(self):
        reg = self._started(_descriptor("cap.mic", kind=CapKind.HYBRID,
                                        flags=CapFlag.CALLABLE_BY_LLM | CapFlag.EMITS_EVENTS))
        self.assertTrue(reg.call("cap.mic", {}, caller=Caller.AGENT)["ok"])

    def test_active_calls_counted_during_execution(self):
        seen = []
        evt = threading.Event()

        def slow(payload, ctx):
            seen.append(ctx.active_calls)
            evt.set()
            return {}

        reg = self._started(_descriptor("cap.slow", execute=slow))
        t = threading.Thread(
            target=lambda: reg.call("cap.slow", {}, caller=Caller.SYSTEM))
        t.start()
        evt.wait(2)
        t.join(2)
        self.assertEqual(seen, [1])  # 执行中可见 in-flight 计数


class TestCallerGate(unittest.TestCase):
    def _started(self, **kw):
        reg = caps.CapRegistry()
        reg.register(_descriptor(**kw))
        reg.enable(kw.get("cid", "cap.files.read"))
        return reg

    def test_restricted_blocks_agent_allows_system(self):
        reg = self._started(flags=CapFlag.RESTRICTED)
        with self.assertRaisesRegex(PermissionError, "EPERM"):
            reg.call("cap.files.read", {}, caller=Caller.AGENT)
        self.assertTrue(reg.call("cap.files.read", {}, caller=Caller.SYSTEM)["ok"])

    def test_root_agent_only_blocks_sub_agent_and_console(self):
        reg = self._started(flags=CapFlag.ROOT_AGENT_ONLY | CapFlag.CALLABLE_BY_LLM)
        with self.assertRaisesRegex(PermissionError, "EPERM"):
            reg.call("cap.files.read", {}, caller=Caller.SUB_AGENT)
        with self.assertRaisesRegex(PermissionError, "EPERM"):
            reg.call("cap.files.read", {}, caller=Caller.CONSOLE)
        self.assertTrue(reg.call("cap.files.read", {}, caller=Caller.AGENT)["ok"])


class TestDrain(unittest.TestCase):
    def test_drain_waits_for_inflight_then_disables(self):
        inside = threading.Event()
        release = threading.Event()

        def slow(payload, ctx):
            inside.set()
            release.wait(3)
            return {}

        reg = caps.CapRegistry()
        reg.register(_descriptor("cap.slow", execute=slow))
        reg.enable("cap.slow")
        t = threading.Thread(
            target=lambda: reg.call("cap.slow", {}, caller=Caller.SYSTEM))
        t.start()
        self.assertTrue(inside.wait(2))
        drained = []
        dt = threading.Thread(
            target=lambda: drained.append(
                reg.drain("cap.slow", timeout=5)))
        dt.start()
        import time
        time.sleep(0.2)
        self.assertEqual(reg.state("cap.slow"), CapState.DRAINING)
        release.set()
        t.join(2)
        dt.join(2)
        self.assertEqual(drained, [True])
        self.assertEqual(reg.state("cap.slow"), CapState.DISABLED)

    def test_drain_immediate_when_idle(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor())
        reg.enable("cap.files.read")
        self.assertTrue(reg.drain("cap.files.read", timeout=1))
        self.assertEqual(reg.state("cap.files.read"), CapState.DISABLED)


class TestLlmVisibility(unittest.TestCase):
    def _reg(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor("cap.files.read", family="files"))
        reg.register(_descriptor("cap.mic.record", family="mic",
                                 flags=CapFlag.RESTRICTED))
        reg.enable("cap.files.read")
        reg.enable("cap.mic.record")
        return reg

    def test_tools_for_filters_restricted_and_non_llm(self):
        reg = self._reg()
        tools = reg.tools_for(caller=Caller.AGENT)
        self.assertEqual([t.id for t in tools], ["cap.files.read"])

    def test_llm_visible_scoping_global_and_session(self):
        reg = self._reg()
        reg.set_llm_visible([])
        self.assertEqual(reg.tools_for(caller=Caller.AGENT), [])
        reg.set_llm_visible(["files"], session_id="s1")
        self.assertEqual([t.id for t in reg.tools_for(caller=Caller.AGENT,
                                                      session_id="s1")],
                         ["cap.files.read"])
        # s2 无 session 覆盖 → 走全局 []（全隐藏）
        self.assertEqual(reg.tools_for(caller=Caller.AGENT, session_id="s2"),
                         [])

    def test_sub_agent_excludes_root_only(self):
        reg = caps.CapRegistry()
        reg.register(_descriptor("cap.root.only",
                                 flags=CapFlag.ROOT_AGENT_ONLY | CapFlag.CALLABLE_BY_LLM))
        reg.enable("cap.root.only")
        self.assertEqual(reg.tools_for(caller=Caller.SUB_AGENT), [])
        self.assertEqual([t.id for t in reg.tools_for(caller=Caller.AGENT)],
                         ["cap.root.only"])

    def test_catalog_records_flags_and_family(self):
        reg = self._reg()
        cat = reg.catalog()
        self.assertEqual({c["id"] for c in cat},
                         {"cap.files.read", "cap.mic.record"})
        mic = next(c for c in cat if c["id"] == "cap.mic.record")
        self.assertTrue(mic["restricted"])


class TestAuditHook(unittest.TestCase):
    def test_audit_hook_sees_calls(self):
        log = []
        reg = caps.CapRegistry(audit=log.append)
        reg.register(_descriptor())
        reg.register(_descriptor("cap.secret", flags=CapFlag.RESTRICTED))
        reg.enable("cap.files.read")
        reg.enable("cap.secret")
        reg.call("cap.files.read", {}, caller=Caller.AGENT)
        with self.assertRaises(PermissionError):
            reg.call("cap.secret", {}, caller=Caller.CONSOLE)  # RESTRICTED 拒非 SYSTEM
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0]["cap"], "cap.files.read")
        self.assertTrue(log[0]["ok"])
        self.assertEqual(log[1]["cap"], "cap.secret")
        self.assertFalse(log[1]["ok"])


class TestCalCap(unittest.TestCase):
    """CalCap 便捷构造：audit 元组 → 事件流（telemetry a.* 对接口径）。"""

    def test_cal_cap_emits_event(self):
        events = []

        def emit(event):
            events.append(event)

        cap = CalCap(registry=None, emit=emit)
        cap.record("cap.files.read", caller=Caller.AGENT, ok=True)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "cap.call")
        self.assertEqual(events[0]["cap"], "cap.files.read")
        self.assertTrue(events[0]["ok"])


if __name__ == "__main__":
    unittest.main()
