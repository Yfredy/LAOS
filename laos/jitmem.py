"""jitmem —— Just-in-Time Memory：记忆在使用时再被理解（read-time curation）。

方法论源自 JitMem 论文（*Just-in-Time Memory: Learning to Curate
Task-Adaptive Memory for LLM Agents*，arXiv:2609.27334，2026-09-23）：
不做 write-time 压缩——固定摘要在未来任务未现形时就被迫决定丢弃哪些细节，
"再强的检索也只能找回已经缺失细节的摘要"；改为长期保留原始记忆，任务
到来时检索并即时整理（curate）成面向当前任务的紧凑上下文 payload。

论文四步循环 → laos 转译落地（零依赖红线下的诚实降级）：

    ① 检索   BM25 top-k 原始轨迹(k=3)   → MemoryStore.recall（字符
             bigram Jaccard 房型检索器；零相关预过滤同样由 recall 承担）
    ② 整理   LLM Curator 合成 payload    → 规则 Curator：自适应加权评分
             （论文实证 untrained curator 已打平/超过 write-time 基线，
              WebShop 61.0 vs 41.0 SR）+ 近重复去重 + 字符预算整条取舍
             （**绝不截断条目原文**——原文细节即"操作约束"所在）
    ③ 执行   Executor 带 payload 解题    → laos 调用方（agent/对话管线）
    ④ 回填   成功轨迹 LLM-judge 入库     → mem.outcome(payload_id, success)：
             reward=即时任务成败、时间隔为零（论文原话）。论文用 GRPO
             （8×H200 21–27h）训练 Curator；laos 降级为首条优势归因的
             指数 bandit——以 payload 首条（最高分入选者）相对候选池
             均值的分量差为归因信号，成功上调、失败下调，乘性更新后
             归一化。启发式，非 RL；诚实标注。

与 write-time Jev 入库预审（memory.remember 的 judge 闸）不冲突：那道闸
拦的是隐私/临时过程（治理决策），本模块不压缩任何已入库记忆——存储侧
MemoryStore 本就是"一个文件 + 追加写"的原始记忆库，天然满足论文
"store raw, interpret when needed"的存储取向。

payload 文本供直接前置进任务提示（论文 payload ≈1.9K tokens vs
write-time 法 10–13K；laos 以 budget_chars≈1200 中文字符对齐同一量级）。
"""

from __future__ import annotations

import math
import threading
import time

from .memory import (
    RECENCY_HALF_LIFE_DAYS,
    SECONDS_PER_DAY,
    MemoryStore,
    bigram_jaccard,
)

# 三分量权重与 MemoryStore.recall 的 0.7/0.2/0.1 同源；Curator 的差异在于
# 它们会随 mem.outcome 即时成败自适应（recall 的固定权重不动——两条路径
# 各自独立，互不绑架）
TEXT_W, TAG_W, RECENCY_W = 0, 1, 2
DEFAULT_WEIGHTS = (0.7, 0.2, 0.1)


class Curator:
    """read-time 记忆整理器：检索→加权评分→去重→预算→分组 briefing。

    线程安全：payload 登记与权重更新共用一把锁（kernel 多线程 syscall
    并发 curate/outcome）；检索与评分只读 store 与权重快照，锁外执行。
    """

    # 每条计入预算的元数据开销（"- #id ... (score 0.00)" 行前缀的近似值）
    PAYLOAD_OVERHEAD_CHARS = 24

    def __init__(self, store: MemoryStore, k: int = 8, budget_chars: int = 1200,
                 dup_threshold: float = 0.6, weights: tuple = DEFAULT_WEIGHTS,
                 learn_rate: float = 0.1, payload_cap: int = 128):
        self.store = store
        self.k = max(1, int(k))
        self.budget_chars = max(1, int(budget_chars))
        self.dup_threshold = float(dup_threshold)
        self._w = [float(x) for x in weights]
        self._lr = float(learn_rate)
        # kernel 常驻防无界增长：登记表封顶，最老 payload 出队
        # （其后的 mem.outcome 得 ENOSTR 语义，与"任务早已翻篇"相称）
        self._payload_cap = max(1, int(payload_cap))
        self._lock = threading.Lock()
        self._payloads: dict[int, tuple | None] = {}  # id -> 归因信号
        self._next_id = 1
        self._n_payloads = 0
        self._n_outcomes = 0
        self._n_successes = 0

    # -- 评分分量（与 MemoryStore.recall 同式，供自适应权重复用）----------
    def _components(self, task: str, rec: dict, now: float) -> tuple[float, float, float]:
        j = bigram_jaccard(task, str(rec.get("text", "")))
        tags = rec.get("tags") or []
        hits = sum(1 for tg in tags if tg and str(tg) in task)
        tag_ratio = hits / len(tags) if tags else 0.0
        age_days = max(0.0, (now - rec.get("ts", now)) / SECONDS_PER_DAY)
        recency = 0.3 ** (age_days / RECENCY_HALF_LIFE_DAYS)
        return j, tag_ratio, recency

    # -- ①② 检索 + 整理 ---------------------------------------------------
    def curate(self, task: str, k: int | None = None) -> dict:
        task = str(task)
        kk = max(1, int(k)) if k else self.k
        now = time.time()
        # 零相关预过滤（文本、标签双零不参与评分）由 recall 承担
        cands = self.store.recall(task, k=kk)
        w = tuple(self._w)  # 快照：本次整理全程用同一组权重
        scored = []
        for idx, rec in enumerate(cands):
            j, tg, rc = self._components(task, rec, now)
            score = w[TEXT_W] * j + w[TAG_W] * tg + w[RECENCY_W] * rc
            scored.append({"rec": rec, "comp": (j, tg, rc),
                           "score": score, "idx": idx})
        scored.sort(key=lambda s: (-s["score"], s["idx"]))

        # 去重：与已保留条目文本 bigram jaccard 达阈值即近重复，整条丢弃
        kept: list[dict] = []
        dedup_dropped = 0
        for s in scored:
            dup = any(bigram_jaccard(str(s["rec"].get("text", "")),
                                     str(k2["rec"].get("text", "")))
                      >= self.dup_threshold for k2 in kept)
            if dup:
                dedup_dropped += 1
            else:
                kept.append(s)

        # 预算：按分降序整条收纳（后到的小条可回填余量）；超预算整条丢弃，
        # 绝不截断原文；首条豁免（退化守卫：预算再小也保 top-1）
        used, entries, budget_dropped = 0, [], 0
        for s in kept:
            cost = len(str(s["rec"].get("text", ""))) + self.PAYLOAD_OVERHEAD_CHARS
            if entries and used + cost > self.budget_chars:
                budget_dropped += 1
                continue
            entries.append(s)
            used += cost

        # 分组：section 按 section 内最佳分排序（相关领域在前），
        # section 内按时间升序（经验/轨迹的因果连贯）
        sections: dict[str, list[dict]] = {}
        for s in entries:
            sections.setdefault(str(s["rec"].get("kind", "?")), []).append(s)
        sec_order = sorted(sections,
                           key=lambda kind: -max(x["score"] for x in sections[kind]))

        # 登记payload：归因信号 = 首条分量 - 候选池分量均值（首条凭什么
        # 脱颖而出——全池同质的分量如新鲜度差≈0，不参与归因，避免无信息漂移）
        lead = entries[0]["comp"] if entries else None
        if scored:
            n = len(scored)
            means = tuple(sum(s["comp"][i] for s in scored) / n for i in range(3))
        else:
            means = (0.0, 0.0, 0.0)
        with self._lock:
            pid = self._next_id
            self._next_id += 1
            while len(self._payloads) >= self._payload_cap:
                self._payloads.pop(min(self._payloads))
            self._payloads[pid] = None if lead is None else (
                tuple(a - b for a, b in zip(lead, means)), means)
            self._n_payloads += 1

        lines = [f"payload #{pid} task: {task}"]
        for kind in sec_order:
            lines.append(f"## {kind}")
            for s in sorted(sections[kind],
                            key=lambda x: x["rec"].get("ts", 0)):
                r = s["rec"]
                lines.append(f"- #{r.get('id', '?')} {r.get('text', '')}"
                             f" (score {s['score']:.2f})")
        if not entries:
            lines.append("(no relevant memories)")
        text = "\n".join(lines)

        out_entries = []
        for s in entries:
            row = dict(s["rec"])
            row["score"] = round(s["score"], 4)
            out_entries.append(row)
        return {
            "id": pid,
            "task": task,
            "entries": out_entries,
            "text": text,
            "stats": {
                "candidates": len(scored),
                "dedup_dropped": dedup_dropped,
                "budget_dropped": budget_dropped,
                "over_budget": used > self.budget_chars,
            },
        }

    # -- ④ 回填：即时成败 → 权重 bandit 微调 --------------------------------
    def note_outcome(self, payload_id: int, success: bool) -> bool:
        with self._lock:
            signal = self._payloads.get(int(payload_id))
            if signal is None and int(payload_id) not in self._payloads:
                return False  # ENOSTR 语义：未知/已逐出的 payload
            self._n_outcomes += 1
            if success:
                self._n_successes += 1
            if signal is None:
                return True  # 空 payload（无候选）：记账，权重不动
            adv, _means = signal
            direction = 1.0 if success else -1.0
            raw = [self._w[i] * math.exp(direction * self._lr * adv[i])
                   for i in range(3)]
            total = sum(raw)
            self._w = [x / total for x in raw]
        return True

    # -- 观测 --------------------------------------------------------------
    def weights(self) -> tuple[float, float, float]:
        with self._lock:
            return tuple(self._w)  # type: ignore[return-value]

    def stats(self) -> dict:
        with self._lock:
            return {"payloads": self._n_payloads,
                    "outcomes": self._n_outcomes,
                    "successes": self._n_successes,
                    "weights": [round(x, 4) for x in self._w]}
