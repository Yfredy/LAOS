# tests/test_mic_caps.py
"""内核 mic 四级能力阶梯 + 审计红线扩展（Task 1）。

    python -m unittest tests.test_mic_caps -v

阶梯语义（调研 §8.4 / Global Constraint 4）：mic.listen ⊂ mic.record ⊂
mic.transcribe ⊂ mic.always_on，高层含低层、每级独立授权、默认收紧；
审计红线从 mic.* 扩展到 mic.* + rec.*（ear.transcribe 是转写非录音，不入审计）。

不需要真声卡、零重依赖：stub 驱动直插 syscall_table，只测内核闸门本身。
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.kernel import AgentKernel  # noqa: E402
from laos.mcp import CallResult, ToolSpec  # noqa: E402


class StubDriver:
    """假 MCP 客户端：任何工具调用都返回 OK（闸门语义测试用不到真驱动）。"""

    def call_tool(self, tool, args):
        return CallResult.ok_text("OK")

    def close(self):
        pass


# 直插 syscall_table 的录音类工具集合（schema 全空对象，参数校验必过；
# ear.transcribe 挂在 ear 驱动名下，其余挂 mic）
_STUB_TOOLS = (
    "mic.listen_start", "mic.listen_stop", "mic.segments", "mic.status",
    "mic.record",
    "mic.always_on_start", "mic.always_on_stop", "mic.rewind",
    "rec.start", "rec.stop", "rec.status", "rec.segments", "rec.gc",
    "ear.transcribe",
)


class MicCapsLadderTest(unittest.TestCase):
    """四级能力阶梯：spawn 不同能力集的 agent，断言放行/拒绝与审计。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var",
                                  confirm=lambda op: True)
        # 直插 stub 驱动：不经 load_driver（零子进程），只注册闸门要查的表
        self.kernel.drivers["mic"] = StubDriver()
        self.kernel.drivers["ear"] = StubDriver()
        for tool in _STUB_TOOLS:
            driver = "ear" if tool.startswith("ear.") else "mic"
            self.kernel.syscall_table[tool] = (
                driver, ToolSpec(tool, "stub tool",
                                 {"type": "object", "properties": {}}))

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps):
        return self.kernel.spawn(name="a", caps=caps, ctx=object())

    def _call(self, pid, tool, args=None):
        return asyncio.run(self.kernel.syscall(pid, tool, args or {}))

    # 1) 无任何 mic 能力 → mic.listen_start 被阶梯拒绝（EACCES + 级别名）
    def test_no_caps_listen_start_denied_with_ladder_message(self):
        pcb = self._spawn([])
        res = self._call(pcb.pid, "mic.listen_start")
        self.assertFalse(res.ok)
        self.assertIn("EACCES", res.error)
        self.assertIn("mic capability level", res.error)
        self.assertIn("mic.listen", res.error)

    # 2) 仅有 mic.listen：listen 放行；record / transcribe 越级被拒
    def test_listen_only(self):
        pcb = self._spawn(["mic.listen"])
        self.assertTrue(self._call(pcb.pid, "mic.listen_start").ok)
        res = self._call(pcb.pid, "mic.record")
        self.assertFalse(res.ok)
        self.assertIn("mic capability level mic.record", res.error)
        res = self._call(pcb.pid, "ear.transcribe")
        self.assertFalse(res.ok)
        self.assertIn("mic capability level mic.transcribe", res.error)

    # 3) 仅有 mic.record：record 成功、listen_start 成功（高层含低层）
    def test_record_implies_listen(self):
        pcb = self._spawn(["mic.record"])
        self.assertTrue(self._call(pcb.pid, "mic.record").ok)
        self.assertTrue(self._call(pcb.pid, "mic.listen_start").ok)

    # 4) 仅有 mic.transcribe：ear.transcribe 成功；listen_start 成功
    #    （高层含低层：transcribe ⊇ record ⊇ listen。计划原文此处写
    #    "mic.listen_start 被拒"，与其自身 _mic_ladder_ok 实现（从所需级
    #    向上 any 放行）及 Global Constraint 4"高层级包含低层级"矛盾，
    #    按阶梯语义断言成功——偏离已在 task-1-report 记录）
    def test_transcribe_implies_listen(self):
        pcb = self._spawn(["mic.transcribe"])
        self.assertTrue(self._call(pcb.pid, "ear.transcribe").ok)
        self.assertTrue(self._call(pcb.pid, "mic.listen_start").ok)

    # 5) 仅有 mic.always_on：最高级，三级工具全放行（高层含低层）
    def test_always_on_implies_lower(self):
        pcb = self._spawn(["mic.always_on"])
        self.assertTrue(self._call(pcb.pid, "mic.always_on_start").ok)
        self.assertTrue(self._call(pcb.pid, "mic.rewind").ok)
        self.assertTrue(self._call(pcb.pid, "mic.listen_start").ok)

    # 6) 被拒的 rec.start 也在审计里留下 event:"mic" denied:true
    #    （审计红线扩展：rec.* 与 mic.* 同等待遇，无论成败可追责）
    def test_denied_rec_start_audited_as_mic_event(self):
        pcb = self._spawn([])
        res = self._call(pcb.pid, "rec.start")
        self.assertFalse(res.ok)
        self.assertIn("mic capability level", res.error)
        mic_recs = [r for r in self.kernel.audit.records
                    if r.get("event") == "mic" and r.get("tool") == "rec.start"]
        self.assertEqual(len(mic_recs), 1)
        self.assertTrue(mic_recs[0]["denied"])
        self.assertIn("mic capability level", mic_recs[0]["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
