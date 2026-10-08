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


class TestKernelSentinelWiring(unittest.TestCase):
    """kernel opt-in 接线：sentinel=None 字节级不变；装上后六步进闸门链。

    对 task-3-brief 的两处落地修正（行为语义不变，详见 task-3-report.md）：
      1. brief 的 msg.send to_pid=1 是笔误——_next_pid 从 1000 起自增，
         全新内核没有 pid 1，ESRCH 会让 assertTrue(res.ok) 必挂；改发往
         同驻 buddy 进程（与 tests/test_ipc.py 的既有模式一致）；
      2. tearDown 先 kernel.shutdown() 再清临时目录——Windows 上审计
         句柄不关会 WinError 32（与 IPCBase 等既有内核测试同款）。
    """

    def setUp(self):
        import asyncio
        import tempfile

        from laos.context import ContextManager
        from laos.kernel import AgentKernel
        self._asyncio = asyncio
        self._td = tempfile.TemporaryDirectory()
        self._kernel_cls = AgentKernel
        self._ctx_cls = ContextManager
        self._k = None

    def tearDown(self):
        if self._k is not None:
            self._k.shutdown()
        self._td.cleanup()

    def _boot(self, sentinel=None, confirm=lambda op: True):
        k = self._kernel_cls(Path(self._td.name) / "var", confirm=confirm,
                             sentinel=sentinel)
        k.branches.create_root("main")
        pcb = k.spawn(name="a", caps=["mem.*", "msg.*"],
                      ctx=self._ctx_cls(system_prompt="t", max_tokens=2000),
                      branch="main")
        buddy = k.spawn(name="b", caps=[],
                        ctx=self._ctx_cls(system_prompt="t", max_tokens=2000),
                        branch="main")
        self._k = k
        return k, pcb, buddy

    def _call(self, k, pcb, tool, args):
        return self._asyncio.run(k.syscall(pcb.pid, tool, args))

    def test_default_none_is_byte_compatible(self):
        k, pcb, buddy = self._boot()            # 不装 sentinel
        res = self._call(k, pcb, "msg.send", {"to_pid": buddy.pid, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertFalse([r for r in k.audit.records
                          if r.get("event") == "sentinel"])

    def test_ask_flow_via_confirm_and_audit(self):
        s = Sentinel(SentinelConfig(mode="ask"))  # msg.send 出站 → risk-mode ask
        confirms = []
        k, pcb, buddy = self._boot(sentinel=s, confirm=lambda op:
                                   (confirms.append(op) or True))
        res = self._call(k, pcb, "msg.send", {"to_pid": buddy.pid, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(confirms), 1)
        self.assertEqual(confirms[0]["sentinel"], "risk-mode")
        rows = [r for r in k.audit.records if r.get("event") == "sentinel"]
        self.assertEqual([(r["tool"], r["decision"]) for r in rows],
                         [("msg.send", "ask")])

    def test_confirm_denied_blocks(self):
        s = Sentinel(SentinelConfig(mode="ask"))
        k, pcb, buddy = self._boot(sentinel=s, confirm=lambda op: False)
        res = self._call(k, pcb, "msg.send", {"to_pid": buddy.pid, "text": "hi"})
        self.assertFalse(res.ok)
        self.assertIn("sentinel", res.error)

    def test_session_grant_skips_confirm(self):
        s = Sentinel(SentinelConfig(mode="ask"))
        s.grants.add("msg.send", scope="session")
        confirms = []
        k, pcb, buddy = self._boot(sentinel=s, confirm=lambda op:
                                   (confirms.append(op) or True))
        res = self._call(k, pcb, "msg.send", {"to_pid": buddy.pid, "text": "hi"})
        self.assertTrue(res.ok, res.error)
        self.assertEqual(confirms, [])            # grant 覆盖，不再问人
        rows = [r for r in k.audit.records if r.get("event") == "sentinel"]
        self.assertIsNotNone(rows[-1]["grant"])   # 审计带 grant gid（见 Step 3）

    def test_private_read_taints_then_egress_asks_even_auto(self):
        s = Sentinel(SentinelConfig(mode="auto"))
        confirms = []
        k, pcb, buddy = self._boot(sentinel=s, confirm=lambda op:
                                   (confirms.append(op) or True))
        self._call(k, pcb, "mem.remember",
                   {"kind": "fact", "text": "用户偏好中文", "tags": ["偏好"]})
        res = self._call(k, pcb, "mem.recall", {"query": "偏好", "k": 3})
        self.assertTrue(res.ok)
        self.assertTrue(s.is_tainted(pcb.pid))    # 隐私读 → 污点
        self._call(k, pcb, "msg.send", {"to_pid": buddy.pid, "text": "hi"})
        self.assertEqual(confirms[-1]["sentinel"], "taint-egress")  # auto 也问

    def test_kill_untaints(self):
        s = Sentinel(SentinelConfig(mode="auto"))
        k, pcb, buddy = self._boot(sentinel=s)
        self._call(k, pcb, "mem.recall", {"query": "x"})
        self.assertTrue(s.is_tainted(pcb.pid))
        k.kill(pcb.pid)
        self.assertFalse(s.is_tainted(pcb.pid))


if __name__ == "__main__":
    unittest.main()
