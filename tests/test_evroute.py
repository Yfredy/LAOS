# tests/test_evroute.py
"""evroute —— 事件规则表（esp-claw claw_event_router 的 laos 转译，P2 兑现）。

源构件：esp-claw components/claw_modules/claw_event_router（Apache-2.0，
espressif/esp-claw，结构级判读自 var/repro 抢救源码）——JSON 规则热载 +
六动作 + consume_on_match + per-action fail_open。laos 转译（零依赖红线）：

    动作映射：CALL_CAP→call_cap（回调注入，装配层接 laos/caps.py）
              DROP→drop（事件防火墙）  EMIT_EVENT→emit（派生事件回注）
              RUN_AGENT/RUN_SCRIPT/SEND_MESSAGE→kernel/驱动域，核心版不做

    语义保留：consume_on_match（首条命中消费）、fail_open（动作异常时
    放行继续 vs 保守中止）、无规则命中=事件默认放行（passthrough）、
    结果对象带 matched/matched_rules/action_count/failed_actions/
    first_rule_id（esp-claw claw_event_router_result_t 同构）。

    python -m unittest tests.test_evroute -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.evroute import EventRouter  # noqa: E402


def cap_rule(rid="r1", **kw):
    rule = {"id": rid, "enabled": True, "consume_on_match": False,
            "match": {"type": "asr.final"},
            "actions": [{"kind": "call_cap", "cap": "x",
                         "input": {"a": 1}, "caller": "SYSTEM",
                         "fail_open": True}]}
    rule.update(kw)
    return rule


class TestMatchAndFlow(unittest.TestCase):
    def test_no_rules_passthrough(self):
        r = EventRouter()
        res = r.handle({"type": "asr.final", "text": "你好"})
        self.assertFalse(res.matched)
        self.assertFalse(res.dropped)
        self.assertEqual(res.action_count, 0)

    def test_type_match_executes_action(self):
        calls = []
        def cap(name, payload, caller):
            calls.append((name, payload, caller))
            return "cap-out"
        r = EventRouter(rules=[cap_rule()], call_cap=cap)
        res = r.handle({"type": "asr.final", "text": "你好"})
        self.assertTrue(res.matched)
        self.assertEqual(res.action_count, 1)
        self.assertEqual(res.failed_actions, 0)
        self.assertEqual(calls, [("x", {"a": 1}, "SYSTEM")])
        self.assertEqual(res.first_rule_id, "r1")
        self.assertEqual(res.cap_outputs.get("x"), "cap-out")

    def test_type_mismatch_no_match(self):
        calls = []
        r = EventRouter(rules=[cap_rule()],
                        call_cap=lambda *a: calls.append(a))
        res = r.handle({"type": "d.wake.state_change"})
        self.assertFalse(res.matched)
        self.assertEqual(calls, [])

    def test_consume_on_match_stops_rule_chain(self):
        seen = []
        mk = lambda rid, consume: {  # noqa: E731
            "id": rid, "enabled": True, "consume_on_match": consume,
            "match": {"type": "asr.final"},
            "actions": [{"kind": "call_cap", "cap": rid, "input": {},
                         "caller": "SYSTEM", "fail_open": True}]}
        r = EventRouter(rules=[mk("r1", True), mk("r2", False)],
                        call_cap=lambda name, *_: seen.append(name))
        res = r.handle({"type": "asr.final"})
        self.assertEqual(res.matched_rules, 1)
        self.assertEqual(seen, ["r1"])

    def test_without_consume_both_rules_match(self):
        seen = []
        mk = lambda rid: {  # noqa: E731
            "id": rid, "enabled": True, "consume_on_match": False,
            "match": {"type": "asr.final"},
            "actions": [{"kind": "call_cap", "cap": rid, "input": {},
                         "caller": "SYSTEM", "fail_open": True}]}
        r = EventRouter(rules=[mk("r1"), mk("r2")],
                        call_cap=lambda name, *_: seen.append(name))
        res = r.handle({"type": "asr.final"})
        self.assertEqual(res.matched_rules, 2)
        self.assertEqual(seen, ["r1", "r2"])

    def test_disabled_rule_skipped(self):
        calls = []
        r = EventRouter(rules=[cap_rule(enabled=False)],
                        call_cap=lambda *a: calls.append(a))
        self.assertFalse(r.handle({"type": "asr.final"}).matched)
        self.assertEqual(calls, [])

    def test_text_exact_and_prefix(self):
        base = {"id": "t", "enabled": True, "consume_on_match": False,
                "match": {"type": "asr.final"},
                "actions": [{"kind": "drop"}]}
        exact = dict(base, id="e", match={"type": "asr.final",
                                          "text": "停", "text_match": "exact"})
        prefix = dict(base, id="p", match={"type": "asr.final",
                                           "text": "打开", "text_match": "prefix"})
        r = EventRouter(rules=[exact, prefix])
        self.assertTrue(r.handle({"type": "asr.final", "text": "停"}).matched)
        self.assertFalse(r.handle({"type": "asr.final", "text": "停止"}).matched)
        self.assertTrue(r.handle({"type": "asr.final", "text": "打开灯"}).matched)

    def test_source_exact_and_wildcard(self):
        rule = {"id": "s", "enabled": True, "consume_on_match": False,
                "match": {"type": "ev", "source": "drv_mic"},
                "actions": [{"kind": "drop"}]}
        r = EventRouter(rules=[rule])
        self.assertTrue(r.handle({"type": "ev", "source": "drv_mic"}).matched)
        self.assertFalse(r.handle({"type": "ev", "source": "drv_ear"}).matched)


class TestActions(unittest.TestCase):
    def test_drop_action_sets_dropped(self):
        rule = {"id": "d", "enabled": True, "consume_on_match": False,
                "match": {"type": "asr.final"}, "actions": [{"kind": "drop"}]}
        res = EventRouter(rules=[rule]).handle({"type": "asr.final", "text": "x"})
        self.assertTrue(res.matched)
        self.assertTrue(res.dropped)

    def test_call_cap_exception_fail_open_continues(self):
        acts = [
            {"kind": "call_cap", "cap": "boom", "input": {},
             "caller": "SYSTEM", "fail_open": True},
            {"kind": "drop"},
        ]
        rule = cap_rule()
        rule["actions"] = acts
        def boom(name, payload, caller):
            if name == "boom":
                raise RuntimeError("cap exploded")
            return "ok"
        res = EventRouter(rules=[rule], call_cap=boom).handle({"type": "asr.final"})
        self.assertEqual(res.failed_actions, 1)
        self.assertTrue(res.dropped)      # fail_open=True：后续动作照跑

    def test_call_cap_exception_fail_closed_aborts_rule(self):
        acts = [
            {"kind": "call_cap", "cap": "boom", "input": {},
             "caller": "SYSTEM", "fail_open": False},
            {"kind": "drop"},
        ]
        rule = cap_rule()
        rule["actions"] = acts
        def boom(name, payload, caller):
            raise RuntimeError("cap exploded")
        res = EventRouter(rules=[rule], call_cap=boom).handle({"type": "asr.final"})
        self.assertEqual(res.failed_actions, 1)
        self.assertFalse(res.dropped)     # fail_closed：drop 没跑，事件放行

    def test_emit_action_sends_derived_event_with_copy(self):
        got = []
        rule = {"id": "e", "enabled": True, "consume_on_match": False,
                "match": {"type": "asr.final"},
                "actions": [{"kind": "emit",
                             "event": {"type": "asr.routed", "mark": 1},
                             "copy": ["text"]}]}
        r = EventRouter(rules=[rule], sink=got.append)
        res = r.handle({"type": "asr.final", "text": "你好"})
        self.assertEqual(res.emitted, [{"type": "asr.routed", "mark": 1,
                                        "text": "你好"}])
        self.assertEqual(got, res.emitted)


class TestCrudAndReload(unittest.TestCase):
    def test_add_delete_rule_and_duplicate_id_rejected(self):
        r = EventRouter()
        r.add_rule(cap_rule("a"))
        self.assertEqual(r.list_rules()[0]["id"], "a")
        with self.assertRaises(ValueError):
            r.add_rule(cap_rule("a"))
        self.assertTrue(r.delete_rule("a"))
        self.assertFalse(r.delete_rule("a"))
        self.assertEqual(r.list_rules(), [])

    def test_invalid_rule_rejected(self):
        r = EventRouter()
        bad_kind = cap_rule()
        bad_kind["actions"] = [{"kind": "run_agent"}]  # 核心版不做的动作
        with self.assertRaises(ValueError):
            r.add_rule(bad_kind)
        with self.assertRaises(ValueError):
            r.add_rule(cap_rule("x", match={"text": "t", "text_match": "regex"}))

    def test_load_file_and_hot_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rules.json"
            path.write_text(json.dumps([cap_rule("one")]), encoding="utf-8")
            calls = []
            r = EventRouter(call_cap=lambda *a: calls.append(a))
            r.load_file(path)
            self.assertTrue(r.handle({"type": "asr.final"}).matched)
            path.write_text(json.dumps([]), encoding="utf-8")
            r.reload()                       # 热载：规则清空后事件放行
            self.assertFalse(r.handle({"type": "asr.final"}).matched)

    def test_audit_hook_called_with_summary(self):
        audits = []
        r = EventRouter(rules=[cap_rule()],
                        call_cap=lambda *a: "ok",
                        on_audit=lambda row: audits.append(row))
        r.handle({"type": "asr.final"})
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["first_rule_id"], "r1")
        self.assertEqual(audits[0]["action_count"], 1)


if __name__ == "__main__":
    unittest.main()
