# tests/test_sentinel.py —— nanoMuse Sentinel 的 laos 转译（六级有序判定+taint+grants）。
# 设计来源：docs/research/2026-10-08-nanomuse.md §3.1（只学设计，无代码拷贝，GPL 隔离）。
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.sentinel import (  # noqa: E402
    Assessment,
    Decision,
    GrantStore,
    Sentinel,
    SentinelConfig,
)


def sent(**kw) -> Sentinel:
    return Sentinel(SentinelConfig(**kw))


class TestDecideOrder(unittest.TestCase):
    """六级判定序：deny→规则→always 列表→风险×模式→taint→不可覆盖警告。"""

    def test_deny_tools_wins_first(self):
        d = sent(deny_tools=("shell",)).decide(Assessment("shell", risk="high"))
        self.assertEqual((d.action, d.reason), ("deny", "deny-tools"))

    def test_explicit_rule_beats_lists(self):
        d = sent(rules=({"tool_glob": "msg.*", "action": "allow"},),
                 always_ask=("msg.send",)).decide(Assessment("msg.send"))
        self.assertEqual((d.action, d.reason), ("allow", "rule"))

    def test_always_allow_and_always_ask(self):
        self.assertEqual(sent(always_allow=("time.now",)).decide(
            Assessment("time.now")).action, "allow")
        self.assertEqual(sent(always_ask=("fs.write",)).decide(
            Assessment("fs.write")).action, "ask")

    def test_risk_times_mode_matrix(self):
        a = Assessment("x.tools", risk="high", reversible=False)
        self.assertEqual(sent(mode="auto").decide(a).action, "allow")
        self.assertEqual(sent(mode="ask").decide(a).action, "ask")
        self.assertEqual(sent(mode="strict").decide(
            Assessment("y.tools", risk="low")).action, "allow")     # strict 只问非 low
        self.assertEqual(sent(mode="strict").decide(
            Assessment("z.tools", risk="medium")).action, "ask")

    def test_taint_escalates_egress_even_in_auto(self):
        # 读过隐私后出站变 ask，永不回退——auto 模式同样生效（nanoMuse 语义）
        d = sent(mode="auto").decide(Assessment("msg.send", egress=True), tainted=True)
        self.assertEqual((d.action, d.reason), ("ask", "taint-egress"))

    def test_taint_only_hits_egress_tools(self):
        d = sent(mode="auto").decide(Assessment("mem.remember"), tainted=True)
        self.assertEqual(d.action, "allow")

    def test_taint_egress_grant_scopes_once_only(self):
        # 污点出站永不回退：不给 session/always 免疫，仅 once 档可 grant
        # （唯一豁免=显式 allow 规则，见 test_explicit_allow_rule_beats_taint）
        d = sent(mode="ask").decide(Assessment("msg.send", egress=True), tainted=True)
        self.assertEqual((d.action, d.reason), ("ask", "taint-egress"))
        self.assertEqual(d.grant_scopes, ("once",))

    def test_explicit_allow_rule_beats_taint(self):
        # egress allowlist 的 laos 化：显式规则可放行污点出站
        d = sent(mode="auto", rules=({"tool_glob": "msg.send", "action": "allow"},)
                 ).decide(Assessment("msg.send", egress=True), tainted=True)
        self.assertEqual(d.action, "allow")

    def test_warning_terminal_only_once_grantable(self):
        # 不可逆+高风险=不可覆盖警告：普通 grant 压不住，只有 once 档
        d = sent(mode="ask").decide(Assessment("pay.transfer", risk="high",
                                               reversible=False))
        self.assertEqual((d.action, d.reason, d.grant_scopes),
                         ("ask", "warning-terminal", ("once",)))

    def test_reversible_low_default_allows(self):
        self.assertEqual(sent().decide(Assessment("mem.stats")).action, "allow")

    def test_decision_default_scopes(self):
        d = sent().decide(Assessment("fs.write", reversible=False))
        self.assertEqual(d.grant_scopes, ("once", "session", "always"))


class TestGrantStore(unittest.TestCase):
    """scoped grants：once 命中即耗 / session 可重复 / target 绑定 + glob。"""

    def test_once_consumed_session_persists(self):
        g = GrantStore()
        gid = g.add("msg.send", scope="once")
        self.assertEqual(g.covers("msg.send"), gid)      # 首次命中并消费
        self.assertIsNone(g.covers("msg.send"))          # once 已耗
        s = g.add("fs.*", scope="session")
        self.assertEqual(g.covers("fs.write"), s)
        self.assertEqual(g.covers("fs.write"), s)        # session 可重复

    def test_target_binding_and_glob(self):
        g = GrantStore()
        gid = g.add("msg.send", target="pid:7", scope="always")
        self.assertIsNone(g.covers("msg.send", target="pid:8"))  # target 不符
        self.assertEqual(g.covers("msg.send", target="pid:7"), gid)
        self.assertEqual(g.covers("msg.send"), gid)      # 查询不带 target 视为通配命中

    def test_revoke_and_list(self):
        g = GrantStore()
        gid = g.add("shell", scope="always")
        rows = g.list_grants()
        self.assertEqual([(r["gid"], r["tool_glob"], r["scope"]) for r in rows],
                         [(gid, "shell", "always")])
        self.assertTrue(g.revoke(gid))
        self.assertFalse(g.revoke(gid))
        self.assertIsNone(g.covers("shell"))

    def test_bad_scope_rejected(self):
        with self.assertRaises(ValueError):
            GrantStore().add("x", scope="forever")


class TestTaintTracker(unittest.TestCase):
    """污点只涨不清，唯一清除通道=进程退出（untaint）。"""

    def test_taint_never_auto_clears(self):
        s = Sentinel()
        self.assertFalse(s.is_tainted(7))
        s.mark_private_read(7)
        self.assertTrue(s.is_tainted(7))       # 只涨不清（nanoMuse：永不回退）
        s.untaint(7)                            # 唯一清除通道=进程退出
        self.assertFalse(s.is_tainted(7))

    def test_taint_per_pid(self):
        s = Sentinel()
        s.mark_private_read(1)
        self.assertFalse(s.is_tainted(2))


if __name__ == "__main__":
    unittest.main()
