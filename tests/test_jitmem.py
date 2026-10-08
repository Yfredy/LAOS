# tests/test_jitmem.py
"""jitmem —— Just-in-Time Memory：记忆在使用时再被理解（read-time curation）。

方法论源自 JitMem 论文（Just-in-Time Memory: Learning to Curate
Task-Adaptive Memory for LLM Agents, arXiv:2609.27334, 2026-09-23，
Salesforce 系团队）：不做 write-time 压缩，任务到来时检索原始记忆并即时
整理成紧凑 payload。laos 落地为转译复现——规则 Curator（论文实证
untrained curator 已打平/超过 write-time 基线）+ 即时成败的 bandit 权重
微调（论文用 GRPO 8×H200 训练，零依赖红线下降级为启发式）。

    python -m unittest tests.test_jitmem -v
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import ContextManager  # noqa: E402
from laos.jitmem import Curator  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402
from laos.memory import MemoryStore  # noqa: E402

COFFEE_TASK = "意式浓缩咖啡的配方比例"
# 与任务共享 bigram（咖啡/啡的）但无标签：j≈0.11，靠文本相关度召回
TEXT_MATCH = "手冲咖啡的研磨粗细参数"
# 与任务零 bigram 重叠、仅靠标签"配方"召回：j=0, tag_ratio=1.0
TAG_MATCH = "牛奶打发温度控制"
IRRELEVANT = "量子纠错码的距离下界证明"


def fresh_store(td: str) -> MemoryStore:
    """写三条可控记忆：文本命中 / 标签命中 / 零相关（recall 预过滤应丢弃）。"""
    store = MemoryStore(Path(td) / "memory.jsonl")
    store.remember("skill", TEXT_MATCH, tags=["冲煮"])
    store.remember("fact", TAG_MATCH, tags=["配方"])
    store.remember("paper", IRRELEVANT, tags=["量子"])
    return store


class TestCuratorPipeline(unittest.TestCase):
    """curate 管线：检索→自适应评分→去重→预算（整条取舍）→分组→briefing。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = fresh_store(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_curate_selects_relevant_and_drops_zero_relevance(self):
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        texts = [e["text"] for e in p["entries"]]
        self.assertIn(TEXT_MATCH, texts)   # 文本命中入选
        self.assertIn(TAG_MATCH, texts)    # 标签命中入选
        self.assertNotIn(IRRELEVANT, texts)  # 零相关不入 payload
        self.assertEqual(p["task"], COFFEE_TASK)
        self.assertEqual(p["stats"]["candidates"], 2)

    def test_empty_store_returns_empty_payload(self):
        cur = Curator(MemoryStore(Path(self._td.name) / "empty.jsonl"))
        p = cur.curate("任何任务")
        self.assertEqual(p["entries"], [])
        self.assertIn("no relevant memories", p["text"])
        self.assertEqual(p["stats"]["candidates"], 0)

    def test_raw_text_never_truncated(self):
        # JitMem 核心主张：摘要丢操作约束——预算只整条取舍，绝不截断原文
        cur = Curator(self.store, budget_chars=30)
        p = cur.curate(COFFEE_TASK)
        for e in p["entries"]:
            self.assertIn(e["text"], p["text"])

    def test_budget_drops_whole_entries(self):
        cur = Curator(self.store, budget_chars=1)
        p = cur.curate(COFFEE_TASK)
        # 预算再小也保 top-1（退化守卫），其余整条丢弃
        self.assertEqual(len(p["entries"]), 1)
        self.assertGreater(p["stats"]["budget_dropped"], 0)
        self.assertTrue(p["stats"]["over_budget"])
        # 反向：预算充裕时两条全收、零丢弃
        p2 = Curator(self.store, budget_chars=10000).curate(COFFEE_TASK)
        self.assertEqual(len(p2["entries"]), 2)
        self.assertEqual(p2["stats"]["budget_dropped"], 0)

    def test_near_duplicates_deduped_keep_higher_score(self):
        # 同文异标签：文本 jaccard=1.0 ≥ dup_threshold，去重保留分高者（带标签那条）
        self.store.remember("fact", TEXT_MATCH, tags=["配方", "冲煮"])
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        same = [e for e in p["entries"] if e["text"] == TEXT_MATCH]
        self.assertEqual(len(same), 1)
        self.assertEqual(p["stats"]["dedup_dropped"], 1)
        self.assertEqual(same[0]["tags"], ["配方", "冲煮"])

    def test_distinct_texts_not_deduped(self):
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        self.assertEqual(p["stats"]["dedup_dropped"], 0)
        self.assertEqual(len(p["entries"]), 2)

    def test_sections_by_kind_chronological_within(self):
        # 显式 ts 的 JSONL：同 kind 两条旧→新（文本互不相似，避开去重），
        # 另一 kind 一条；时序体现在 briefing 文本里（section 内时间升序）
        path = Path(self._td.name) / "ordered.jsonl"
        rows = [
            {"id": 1, "ts": 100.0, "kind": "episode", "text": "咖啡研磨刻度调节", "tags": ["咖啡"]},
            {"id": 2, "ts": 200.0, "kind": "episode", "text": "浓缩萃取时间控制", "tags": ["咖啡"]},
            {"id": 3, "ts": 300.0, "kind": "fact", "text": "咖啡豆烘焙程度", "tags": ["咖啡"]},
        ]
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        cur = Curator(MemoryStore(path))
        p = cur.curate("咖啡冲煮要点")
        self.assertEqual({e["id"] for e in p["entries"]}, {1, 2, 3})
        # 同 section 内按时间升序（轨迹因果连贯），跨 section 按 section 最佳分排序
        self.assertIn("## episode", p["text"])
        self.assertIn("## fact", p["text"])
        self.assertLess(p["text"].index("- #1 "), p["text"].index("- #2 "))

    def test_payload_text_header_carries_task_and_id(self):
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        self.assertIn("payload #1", p["text"])
        self.assertIn(COFFEE_TASK, p["text"])

    def test_curate_respects_k(self):
        cur = Curator(self.store, k=1)
        p = cur.curate(COFFEE_TASK)
        self.assertEqual(p["stats"]["candidates"], 1)
        self.assertLessEqual(len(p["entries"]), 1)

    def test_deterministic_without_outcomes(self):
        cur = Curator(self.store)
        p1, p2 = cur.curate(COFFEE_TASK), cur.curate(COFFEE_TASK)
        self.assertEqual([(e["id"], e["score"]) for e in p1["entries"]],
                         [(e["id"], e["score"]) for e in p2["entries"]])

    def test_curate_is_readonly_on_store(self):
        before = self.store.stats()["total"]
        Curator(self.store).curate(COFFEE_TASK)
        self.assertEqual(self.store.stats()["total"], before)


class TestCuratorAdaptiveWeights(unittest.TestCase):
    """note_outcome：即时任务成败 → 三分量权重 bandit 微调（首条归因）。

    论文 reward=冻结 Executor 的即时任务成功（时间隔为零）；laos 零依赖
    版降级为首条归因的指数 bandit——诚实标注：启发式，非 GRPO。
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = fresh_store(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_success_on_tag_driven_payload_raises_tag_weight(self):
        cur = Curator(self.store)
        w0 = cur.weights()
        p = cur.curate(COFFEE_TASK)
        # 标签命中条（tag_ratio=1, j=0）分数 0.3 > 文本命中条 ≈0.18，为首条
        self.assertEqual(p["entries"][0]["text"], TAG_MATCH)
        self.assertTrue(cur.note_outcome(p["id"], True))
        w1 = cur.weights()
        self.assertGreater(w1[1], w0[1])   # w_tags 上升
        self.assertLess(w1[0], w0[0])      # w_text（归因 0）被归一化压低
        self.assertAlmostEqual(sum(w1), 1.0, places=6)

    def test_failure_lowers_attributed_weight(self):
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        w0 = cur.weights()
        self.assertTrue(cur.note_outcome(p["id"], False))
        w1 = cur.weights()
        self.assertLess(w1[1], w0[1])      # 首条归因 tag → 失败下调
        self.assertAlmostEqual(sum(w1), 1.0, places=6)

    def test_outcome_changes_subsequent_ranking(self):
        cur = Curator(self.store)
        p0 = cur.curate(COFFEE_TASK)
        gap0 = (p0["entries"][0]["score"] - p0["entries"][1]["score"])
        cur.note_outcome(p0["id"], True)   # 成功 → 更信标签通道
        p1 = cur.curate(COFFEE_TASK)
        by = {e["text"]: e["score"] for e in p1["entries"]}
        gap1 = by[TAG_MATCH] - by[TEXT_MATCH]
        self.assertGreater(gap1, gap0)     # 标签条相对优势扩大

    def test_outcome_unknown_payload_id_false(self):
        cur = Curator(self.store)
        self.assertFalse(cur.note_outcome(999, True))

    def test_weights_bounded_after_many_outcomes(self):
        cur = Curator(self.store)
        for i in range(20):
            p = cur.curate(COFFEE_TASK)
            cur.note_outcome(p["id"], i % 2 == 0)
        w = cur.weights()
        self.assertAlmostEqual(sum(w), 1.0, places=6)
        for wi in w:
            self.assertGreater(wi, 0.0)
            self.assertLess(wi, 1.0)

    def test_stats_reports_payloads_and_outcomes(self):
        cur = Curator(self.store)
        p = cur.curate(COFFEE_TASK)
        cur.note_outcome(p["id"], True)
        st = cur.stats()
        self.assertEqual(st["payloads"], 1)
        self.assertEqual(st["outcomes"], 1)
        self.assertEqual(st["successes"], 1)

    def test_payload_registry_cap_evicts_oldest(self):
        cur = Curator(self.store, payload_cap=2)
        ids = [cur.curate(COFFEE_TASK)["id"] for _ in range(3)]
        self.assertTrue(cur.note_outcome(ids[2], True))
        self.assertFalse(cur.note_outcome(ids[0], True))  # 已被逐出


class TestJitmemSyscalls(unittest.TestCase):
    """mem.curate / mem.outcome 内建 syscall：任务到来→整理→执行→回填成败。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.kernel = AgentKernel(Path(self._td.name) / "var",
                                  confirm=lambda op: True)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, caps):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=caps, ctx=ctx, branch="main")

    def test_curate_then_outcome_roundtrip(self):
        pcb = self._spawn(["mem.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.remember",
            {"kind": "fact", "text": TAG_MATCH, "tags": ["配方"]}))
        self.assertTrue(res.ok, res.error)
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.curate", {"task": COFFEE_TASK}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("payload #1", res.text)
        self.assertIn(TAG_MATCH, res.text)
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.outcome", {"payload_id": 1, "success": True}))
        self.assertTrue(res.ok, res.error)
        # 成败回填后权重已变、下一轮 curate 仍可用（id 递增）
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.curate", {"task": COFFEE_TASK}))
        self.assertIn("payload #2", res.text)

    def test_curate_on_empty_memory(self):
        pcb = self._spawn(["mem.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.curate", {"task": "任何任务"}))
        self.assertTrue(res.ok, res.error)
        self.assertIn("no relevant memories", res.text)

    def test_outcome_unknown_id_enostr(self):
        pcb = self._spawn(["mem.*"])
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.outcome", {"payload_id": 999, "success": True}))
        self.assertFalse(res.ok)
        self.assertIn("ENOSTR", res.error)

    def test_curate_and_outcome_audited_as_memory_events(self):
        pcb = self._spawn(["mem.*"])
        asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.curate", {"task": COFFEE_TASK}))
        asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.outcome", {"payload_id": 1, "success": False}))
        ops = [(r.get("op"), r.get("success"))
               for r in self.kernel.audit.records
               if r.get("event") == "memory"]
        self.assertIn(("curate", None), ops)
        self.assertIn(("outcome", False), ops)

    def test_curate_readonly_on_memory_store(self):
        pcb = self._spawn(["mem.*"])
        asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.remember",
            {"kind": "fact", "text": TEXT_MATCH, "tags": ["冲煮"]}))
        before = self.kernel.memory.stats()["total"]
        asyncio.run(self.kernel.syscall(
            pcb.pid, "mem.curate", {"task": COFFEE_TASK}))
        self.assertEqual(self.kernel.memory.stats()["total"], before)


if __name__ == "__main__":
    unittest.main()
