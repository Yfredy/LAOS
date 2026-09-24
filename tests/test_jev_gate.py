# tests/test_jev_gate.py
"""内核确认横幅的 Jev 机器预审闸（Task 3，opt-in）。

LAOS_JEV_BACKEND=none（默认）时零改动——不构造判断后端、无 jev 审计、
confirm 流程逐字节不变（用例③钉住）；显式启用后，risk=high 的确认横幅
先经机器预审（judge.noul）：

- deny          → EDENIED: denied by jev prejudge（机器终审，不打扰人类）
- allow+高置信  → LAOS_JEV_AUTOGATE=1 时跳过人类 confirm 直接放行
- 其余          → 回落人类 confirm（低置信 / 仅预览模式）
- 每次预审写一条 event:"jev" 审计（放行与拒绝双路径，仿 event:"mic"）

    python -m unittest tests.test_jev_gate -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.judge import JudgeResult  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402


class FakeJudge:
    """注入 kernel.judge 的桩后端：返回预置 JudgeResult 并记录调用。"""

    def __init__(self, verdict: str, confidence: float):
        self.result = JudgeResult(verdict, confidence)
        self.calls: list[tuple[str, str]] = []

    def noul(self, context: str, question: str) -> JudgeResult:
        self.calls.append((context, question))
        return self.result


class TestJevGate(unittest.TestCase):
    def setUp(self):
        # 环境隔离：本套用例无论外部环境如何，都从"默认 none"出发
        self._env = mock.patch.dict(os.environ)
        self._env.start()
        for key in ("LAOS_JEV_BACKEND", "LAOS_JEV_AUTOGATE",
                    "LAOS_JEV_PREVIEW", "LAOS_JEV_AUTOGATE_MIN"):
            os.environ.pop(key, None)
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.confirm_calls: list[dict] = []

        def _confirm(op: dict) -> bool:
            self.confirm_calls.append(op)
            return False  # 人类一律拒绝：闸门走向在断言里现形

        self.kernel = AgentKernel(self.workdir, confirm=_confirm,
                                  irreversibility_budget=100)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8",
               "LAOS_FS_ROOT": str(self.workdir / "branches")}
        self.kernel.load_driver(
            "proc", [sys.executable, str(REPO / "drivers" / "drv_proc.py")],
            env=env)
        self.kernel.branches.create_root("main")
        self.pcb = self.kernel.spawn(name="jev", caps=["proc.*"],
                                     ctx=object(), branch="main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()
        self._env.stop()

    def _jev_records(self):
        return [r for r in self.kernel.audit.records
                if r.get("event") == "jev"]

    def _exec(self, cmdline: str):
        return asyncio.run(self.kernel.syscall(
            self.pcb.pid, "proc.exec", {"cmdline": cmdline}))

    def test_autogate_high_confidence_bypasses_confirm(self):
        # ① AUTOGATE=1 + 高置信 allow → 不经人类 confirm 直接放行，
        #    且审计含 event:"jev"（verdict/confidence/autogate 齐全）
        os.environ["LAOS_JEV_AUTOGATE"] = "1"
        fake = FakeJudge("allow", 0.97)
        self.kernel.judge = fake
        res = self._exec("echo jev-ok")
        self.assertTrue(res.ok, res.error or res.text)
        self.assertEqual(self.confirm_calls, [], "不得惊动人类 confirm")
        self.assertEqual(len(fake.calls), 1, "预审恰好一次")
        # 预审问句钉关键词不钉全文（criteria 式两段，全文由
        # test_calibrate_judge 的 import 契约与 test_judge 的结构例钉）：
        # 固定 context + 工具/参数/agent 注入 + 判据结构 + deny 方向
        pctx, pquestion = fake.calls[0]
        self.assertEqual(pctx, "内核高风险 syscall 确认横幅预审")
        self.assertTrue(pquestion.startswith("允许执行 proc.exec"))
        self.assertIn("'cmdline'", pquestion)
        self.assertIn("agent=jev", pquestion)
        self.assertIn("；判“否”", pquestion)
        self.assertIn("deny，拒绝执行", pquestion)
        jev = self._jev_records()
        self.assertEqual(len(jev), 1)
        self.assertEqual(jev[0]["pid"], self.pcb.pid)
        self.assertEqual(jev[0]["tool"], "proc.exec")
        self.assertEqual(jev[0]["verdict"], "allow")
        self.assertEqual(jev[0]["confidence"], 0.97)
        self.assertTrue(jev[0]["autogate"])

    def test_low_confidence_falls_back_to_confirm(self):
        # ② 低置信(0.6)：即使 AUTOGATE=1 也要人类 confirm 拍板
        os.environ["LAOS_JEV_AUTOGATE"] = "1"
        fake = FakeJudge("allow", 0.6)
        self.kernel.judge = fake
        res = self._exec("echo jev-low")
        self.assertFalse(res.ok)  # confirm 返回 False → 人类拒绝
        self.assertIn("EACCES", res.error)
        self.assertEqual(len(self.confirm_calls), 1, "仍走人类 confirm")
        jev = self._jev_records()
        self.assertEqual(len(jev), 1)
        self.assertEqual(jev[0]["verdict"], "allow")
        self.assertEqual(jev[0]["confidence"], 0.6)

    def test_default_backend_none_keeps_legacy_behavior(self):
        # ③ 默认 LAOS_JEV_BACKEND=none：无 jev 审计、confirm 照旧、
        #    不构造任何判断后端——默认行为逐字节不变
        self.assertIsNone(self.kernel.judge)
        res = self._exec("echo legacy")
        self.assertFalse(res.ok)  # confirm=False → 与现状一致的拒绝
        self.assertIn("EACCES", res.error)
        self.assertEqual(len(self.confirm_calls), 1, "人类 confirm 照常询问")
        self.assertEqual(self._jev_records(), [], "不得新增 jev 审计")

    def test_deny_rejects_without_confirm(self):
        # ④ 机器 deny → 直接 EDENIED（reason 带 jev prejudge），
        #    不经人类 confirm；预览模式下照样强制（deny 是终审）
        os.environ["LAOS_JEV_PREVIEW"] = "1"
        fake = FakeJudge("deny", 0.99)
        self.kernel.judge = fake
        res = self._exec("echo jev-deny")
        self.assertFalse(res.ok)
        self.assertIn("EDENIED", res.error)
        self.assertIn("jev prejudge", res.error)
        self.assertEqual(self.confirm_calls, [], "机器终审不得再问人类")
        jev = self._jev_records()
        self.assertEqual(len(jev), 1)
        self.assertEqual(jev[0]["verdict"], "deny")
        self.assertFalse(jev[0]["autogate"])

    def test_autogate_zero_string_does_not_bypass(self):
        # ⑤ 遗留 A：LAOS_JEV_AUTOGATE="0" 必须解析为关——旧
        #    bool(os.environ.get(...)) 是"存在即真"，设 0 反而开启。
        #    PREVIEW=1 让预审照跑，但高置信 allow 也不得机器代拍
        os.environ["LAOS_JEV_PREVIEW"] = "1"
        os.environ["LAOS_JEV_AUTOGATE"] = "0"
        fake = FakeJudge("allow", 0.97)
        self.kernel.judge = fake
        res = self._exec("echo jev-zero")
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertEqual(len(self.confirm_calls), 1,
                         "=0 时不许机器代拍，必须回落人类 confirm")
        self.assertEqual(len(fake.calls), 1, "预览模式预审照常执行")
        jev = self._jev_records()
        self.assertEqual(len(jev), 1)
        self.assertFalse(jev[0]["autogate"], "审计里 autogate 必须为 False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
