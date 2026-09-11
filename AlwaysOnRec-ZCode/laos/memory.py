"""memory —— laos 的个人记忆库（episodic memory）。

内核直供的 mem.* syscall 背后的存储层：一个 JSONL 追加日志。
设计取向与内核一致——能靠"一个文件 + 追加写"解决的不上数据库：

    remember  = 追加一行 JSON（O(1)；崩溃最坏丢最后一行）
    forget    = 全量重写文件（"个人"量级的记忆，O(N) 可接受）
    recall    = 内存全量扫描 + 字符 bigram Jaccard 相关度（零依赖的模糊
                检索，以字符为单元，中英文一视同仁，不需要分词器）

recall 评分（三分量，权重可调）：

    score = bigram_jaccard(query, text) * 0.7   # 文本相关度
          + tags 命中比例           * 0.2       # 标签召回
          + recency                 * 0.1       # 时间加成
    recency = 0.3 ** (距今天数 / 14)             # 两周衰减到 0.3

零相关（文本、标签双零）的条目不参与评分：recency 不单独构成召回，
否则"完全不相关的查询"也会把整库按新旧顺序捞出来。

CLI（bin/diary.py）与常驻内核共享同一 memory.jsonl 时，假定不同时写入
（单写者约定）；并发写请走内核 mem.* syscall。
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

SECONDS_PER_DAY = 86400
RECENCY_HALF_LIFE_DAYS = 14.0  # 0.3 ** (days / 14)


def bigram_jaccard(a: str, b: str) -> float:
    """字符二元组（bigram）集合的 Jaccard 相似度；任一串不足两字符 → 0.0。"""
    sa = {a[i:i + 2] for i in range(len(a) - 1)}
    sb = {b[i:i + 2] for i in range(len(b) - 1)}
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    if not inter:
        return 0.0
    return inter / len(sa | sb)


class MemoryStore:
    """JSONL 持久化的个人记忆库：读时全量进内存，remember 追加写。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._records: list[dict] = []
        # remember 是"算 _next_id + 追加"的读改写，forget 是"过滤 + 全量重写"
        # ——laosweb HTTP 线程与 demo 线程会同时调 remember，无锁会铸出重复 id
        self._lock = threading.Lock()
        self._load()

    # -- 持久化 ------------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    self._records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # 崩溃残迹（半行）跳过

    def _append(self, rec: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _rewrite(self) -> None:
        # 全量重写走 temp + os.replace（与 cow.py 同一套原子目录项替换）：
        # 旧实现先 truncate 原文件，重写中途崩溃 = 整个记忆库被毁；
        # 原子替换下崩溃最坏留一个 .tmp 残迹，原文件完好
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(
            f".{self.path.name}.rewrite-{os.getpid()}-{threading.get_ident()}.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                for rec in self._records:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise

    @property
    def _next_id(self) -> int:
        return max((r["id"] for r in self._records), default=0) + 1

    # -- 记忆操作 ----------------------------------------------------------
    def remember(self, kind: str, text: str, tags: list[str] | None = None) -> dict:
        with self._lock:  # id 的读改写必须原子，否则并发 remember 铸重复 id
            rec = {"id": self._next_id, "ts": time.time(), "kind": str(kind),
                   "text": str(text), "tags": [str(t) for t in (tags or [])]}
            self._records.append(rec)
            self._append(rec)
            return dict(rec)

    def recall(self, query: str, k: int = 5) -> list[dict]:
        now = time.time()
        with self._lock:  # 评分全程对 _records 只读快照，避免与 remember/forget 交错
            scored: list[tuple[float, dict]] = []
            for rec in self._records:
                j = bigram_jaccard(str(query), str(rec.get("text", "")))
                tags = rec.get("tags") or []
                hits = sum(1 for tg in tags if tg and str(tg) in str(query))
                tag_ratio = hits / len(tags) if tags else 0.0
                if j <= 0.0 and tag_ratio <= 0.0:
                    continue  # 零相关：时间项不得单独构成召回
                age_days = max(0.0, (now - rec.get("ts", now)) / SECONDS_PER_DAY)
                recency = 0.3 ** (age_days / RECENCY_HALF_LIFE_DAYS)
                score = j * 0.7 + tag_ratio * 0.2 + recency * 0.1
                if score <= 0.0:
                    continue
                scored.append((score, rec))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        out: list[dict] = []
        for score, rec in scored[:max(0, int(k))]:
            row = dict(rec)
            row["score"] = round(score, 4)
            out.append(row)
        return out

    def forget(self, mid: int) -> bool:
        with self._lock:  # 与 remember 互斥：避免"过滤 + 重写"与追加交错
            before = len(self._records)
            self._records = [r for r in self._records if r.get("id") != mid]
            if len(self._records) == before:
                return False
            self._rewrite()
            return True

    def stats(self) -> dict:
        by_kind: dict[str, int] = {}
        for rec in self._records:
            kind = rec.get("kind", "?")
            by_kind[kind] = by_kind.get(kind, 0) + 1
        return {"total": len(self._records), "by_kind": by_kind}
