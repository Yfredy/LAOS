# tests/test_jev_mem_ctx.py
"""记忆入库过滤 + 上下文压缩判断（Task 4，opt-in）。

judge= 不传（默认）时行为与现状一致（用例③⑤钉住）；显式传入判断后端后：

- MemoryStore.remember(judge=)：noul("值得长期记住且无隐私风险吗？") 为
  deny → 拒绝入库返回 None（审计留在调用方）
- ContextManager(judge=)：压缩时对候选 victims（最老 1/3）逐条
  noul("此消息可安全丢弃（信息已概括或属临时过程）吗？")——deny（=不可丢）
  的消息移出 victims 保留在窗口内；候选全被保则跳过本轮压缩，连续两轮
  全跳过后强制按原逻辑压缩一次（防死循环）

    python -m unittest tests.test_jev_mem_ctx -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import COMPACT_JUDGE_QUESTION, ContextManager  # noqa: E402
from laos.judge import JudgeResult  # noqa: E402
from laos.memory import REMEMBER_JUDGE_QUESTION, MemoryStore  # noqa: E402


class FakeJudge:
    """可编程桩后端：按 context 字典精确匹配 verdict，未命中走默认值；记录调用。"""

    def __init__(self, verdict: str = "allow",
                 by_context: dict[str, str] | None = None):
        self.default_verdict = verdict
        self.by_context = dict(by_context or {})
        self.calls: list[tuple[str, str]] = []

    def noul(self, context: str, question: str) -> JudgeResult:
        self.calls.append((context, question))
        return JudgeResult(self.by_context.get(context, self.default_verdict), 0.9)


def _blob(tag: str) -> str:
    """定长消息体：400 字符 ASCII → approx_tokens = 400/4 + 1 = 101。

    尺寸经过核算：6 条 606 tok > 550 触发一轮压缩（最老 1/3 = 2 条），
    压完 491 tok（judge 案 549 tok）≤ 550——恰好一轮收场，断言无歧义。
    """
    return tag + "-" + "x" * (400 - len(tag) - 1)


class TestMemoryJevFilter(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self._td.name) / "memory.jsonl")

    def tearDown(self):
        self._td.cleanup()

    def test_remember_judge_deny_rejects(self):
        # ① deny → 拒绝入库：total 不变、返回 None、文件零写入
        fake = FakeJudge(verdict="deny")
        res = self.store.remember("fact", "用户的身份证号", judge=fake)
        self.assertIsNone(res)
        self.assertEqual(self.store.stats()["total"], 0)
        self.assertFalse(self.store.path.exists(), "deny 时不得落盘")
        self.assertEqual(fake.calls,
                         [("用户的身份证号", REMEMBER_JUDGE_QUESTION)])

    def test_remember_judge_allow_stores(self):
        # ② allow → 正常入库：返回 rec、total+1、持久化照常
        fake = FakeJudge(verdict="allow")
        rec = self.store.remember("fact", "喜欢 Python", tags=["pref"],
                                  judge=fake)
        self.assertIsInstance(rec, dict)
        self.assertEqual(rec["id"], 1)
        self.assertEqual(self.store.stats()["total"], 1)
        self.assertEqual(MemoryStore(self.store.path).stats()["total"], 1)

    def test_remember_without_judge_unchanged(self):
        # ③ 不传 judge → 与现状一致：无条件入库、返回 dict
        rec = self.store.remember("diary", "今天开了评审会")
        self.assertIsInstance(rec, dict)
        self.assertEqual(rec["id"], 1)
        self.assertEqual(rec["text"], "今天开了评审会")
        self.assertEqual(self.store.stats()["total"], 1)


class TestContextJevCompaction(unittest.TestCase):
    MAX_TOKENS = 550

    def test_compaction_with_judge_keeps_denied_head(self):
        # ④ judge 判首条"不可丢"：首条保留在窗口，其余候选照常压缩
        fake = FakeJudge(by_context={_blob("m-1"): "deny"})
        ctx = ContextManager(max_tokens=self.MAX_TOKENS, judge=fake)
        for i in range(1, 7):
            ctx.append("user", _blob(f"m-{i}"))
        # 6 × 101 = 606 > 550 → 候选 victims = 最老 1/3 = [m-1, m-2]；
        # m-1 deny → 移出 victims 留在窗口；m-2 allow → 照常压缩进摘要
        contents = [m.content for m in ctx._window]
        self.assertEqual(contents, [_blob(f"m-{i}") for i in (1, 3, 4, 5, 6)])
        self.assertEqual(ctx.stats.compactions, 1)
        self.assertIn(_blob("m-2")[:160], ctx._summary)  # 摘要截断到 160 字符
        self.assertEqual(fake.calls,
                         [(_blob("m-1"), COMPACT_JUDGE_QUESTION),
                          (_blob("m-2"), COMPACT_JUDGE_QUESTION)])

    def test_compaction_without_judge_oldest_third(self):
        # ⑤ 默认无 judge → 压缩仍按最老 1/3（既有行为钉住）
        ctx = ContextManager(max_tokens=self.MAX_TOKENS)
        for i in range(1, 7):
            ctx.append("user", _blob(f"m-{i}"))
        contents = [m.content for m in ctx._window]
        self.assertEqual(contents, [_blob(f"m-{i}") for i in (3, 4, 5, 6)])
        self.assertIn(_blob("m-1")[:160], ctx._summary)
        self.assertIn(_blob("m-2")[:160], ctx._summary)
        self.assertEqual(ctx.stats.compactions, 1)
        self.assertIsNone(ctx.judge)

    def test_compaction_guard_forces_after_two_skips(self):
        # ⑥ 防死循环（设计裁决）：候选全"不可丢"连跳两轮后，第三轮强制
        #    按原逻辑压缩一次——宁可丢受保护消息也不让窗口无限涨爆
        fake = FakeJudge(verdict="deny")
        ctx = ContextManager(max_tokens=self.MAX_TOKENS, judge=fake)
        for i in range(1, 9):
            ctx.append("user", _blob(f"m-{i}"))
        # m-6/m-7 两轮候选 [m-1,m-2] 全 deny → 跳过；m-8 一轮强制压缩
        self.assertEqual(ctx.stats.compactions, 1)
        self.assertEqual(ctx._window[0].content, _blob("m-3"))
        self.assertIn(_blob("m-1")[:160], ctx._summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
