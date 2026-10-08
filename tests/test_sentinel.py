# tests/test_sentinel.py —— nanoMuse Sentinel 的 laos 转译（六级有序判定+taint+grants）。
# 设计来源：docs/research/2026-10-08-nanomuse.md §3.1（只学设计，无代码拷贝，GPL 隔离）。
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.sentinel import Assessment, Decision, Sentinel, SentinelConfig  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
