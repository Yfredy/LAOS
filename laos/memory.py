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
from typing import Any

SECONDS_PER_DAY = 86400
RECENCY_HALF_LIFE_DAYS = 14.0  # 0.3 ** (days / 14)

# Jev 入库预审（Task 4，opt-in）：remember(judge=...) 传入判断后端时先问
# 一句——deny（不值得长期记住或涉隐私）拒绝入库返回 None；审计留在调用方
# （memory 层只管收与拒，不写审计）。
# Task 3 升级为 criteria 式两段问句（指示段 + 判据段，方法论源自
# jev-chat-jarvis questions.py，MIT；题面按 laos 语义重写）：题首保留原
# 问句不变，判据段钉住 deny 方向 = 不入库。注意判据文本刻意避开
# judge.DENY_WORDS（"危险/泄露隐私"等）——RuleBackend 只扫问句关键词，
# 问句自带 deny 词会让规则后端对该 gate 无差别全拒
REMEMBER_JUDGE_QUESTION = (
    "值得长期记住且无隐私风险吗？只依据待记文本本身判断：它是跨会话"
    "仍成立的稳定信息还是本轮临时过程，以及其中是否含个人敏感数据。\n"
    "判“是”（allow，可入库）当：文本表达长期有效的用户偏好、事实结论"
    "或经验教训（如“用户偏好中文回复”“该仓库用 unittest 跑测试”），"
    "且不含任何个人敏感数据；判“否”（deny，不入库）当：文本只是临时"
    "过程细节（中间步骤、试错记录、一次性待办），或含个人敏感数据"
    "（密钥、token、身份证号、住址、私钥内容、聊天记录原文），"
    "任一命中即否。"
)


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
    def remember(self, kind: str, text: str, tags: list[str] | None = None,
                 judge: Any | None = None) -> dict | None:
        if judge is not None:
            # Jev 入库预审：deny = 不可入库。判断放锁外（云端后端可能慢，
            # 不占写锁）；不传 judge（默认）时此分支整体不存在，行为不变
            if judge.noul(str(text), REMEMBER_JUDGE_QUESTION).verdict == "deny":
                return None
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

    # -- 自检（Task 4）------------------------------------------------------
    # 模式参考 jev-chat-jarvis KbSelfCheck.kt（MIT，
    # github.com/jev-chat/jev-chat-jarvis）：自检打真库——写临时条目→验证
    # 容易悄悄坏掉的路径→finally 删光；不是对既有数据的扫描（①②的检测
    # 能力靠注入坏行验证，抓不到坏行的检查是绿泡泡）。
    # laosctl selfcheck 在 tempfile scratch store 上跑（不碰用户
    # var/memory.jsonl）；对既有 store 直接跑亦安全，但注意自检会短暂注入
    # 坏行、结束时走 forget 的原子重写（坏行随之被丢弃——与 _load 静默
    # 跳过半行的既定语义一致）。

    def _scan_jsonl(self) -> list[str]:
        """直接重读磁盘文件（绕开 _load 的静默跳过），报告完整性问题：
        ① 行不可解析 / 非 JSON 对象 / 缺必含字段 id/kind/text/ts
        ② 重复 id。内存 _records 看不到坏行（_load 已跳过），唯一现形处
        就是这里。"""
        problems: list[str] = []
        seen: dict[Any, int] = {}
        if not self.path.exists():
            return problems
        with self.path.open("r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    problems.append(f"① 第 {lineno} 行不可解析为 JSON（崩溃残迹/半行）")
                    continue
                if not isinstance(rec, dict):
                    problems.append(f"① 第 {lineno} 行不是 JSON 对象")
                    continue
                missing = [f for f in ("id", "kind", "text", "ts") if f not in rec]
                if missing:
                    problems.append(f"① 第 {lineno} 行缺必含字段 {'/'.join(missing)}")
                if "id" in rec:
                    if rec["id"] in seen:
                        problems.append(
                            f"② 第 {lineno} 行与第 {seen[rec['id']]} 行 id 重复: {rec['id']!r}")
                    else:
                        seen[rec["id"]] = lineno
        return problems

    def self_check(self) -> list[str]:
        """自检流程检查，返回失败项清单（空 = 全过）。五项：

        ① JSONL 每行可解析且必含 id/kind/text/ts（检测能力靠注入坏行验证）
        ② 重复 id 检测（同上，注入重复行验证抓得到）
        ③ 全/半角括号归一化健壮性：记 "测试群(12)" 与 "测试群（12）" 后
           两种 query 都能同时命中——bigram 检索天然容错（共享 bigram
           重叠，实测 Jaccard 3/9 > 0），此处钉住该事实，刻意不加归一化
           层（YAGNI）
        ④ recall 空 query 不炸且不捞出零相关条目
        ⑤ 自检写入的临时条目用后即删（finally forget，内存与磁盘都复原）

        模式参考 jev-chat-jarvis KbSelfCheck.kt（MIT，
        github.com/jev-chat/jev-chat-jarvis）。
        """
        failures: list[str] = []
        with self._lock:
            base = self._scan_jsonl()  # 自检前既有的坏行先记下（含则报失败）
        if base:
            failures.append("①② 自检前文件已有完整性问题: " + "; ".join(base))
        before = len(self._records)
        a = self.remember("selfcheck", "测试群(12)")
        b = self.remember("selfcheck", "测试群（12）")
        try:
            # ①② 检测能力：注入 截断半行/缺字段行/重复 id 行，必须全抓到，
            # 随后用 _rewrite（写回 _records）撤回注入的裸行
            with self._lock:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write('{"id": 999, "kind": "selfcheck", "text"\n')
                    fh.write(json.dumps(
                        {"id": 1000, "kind": "selfcheck", "ts": 0.0},
                        ensure_ascii=False) + "\n")
                    fh.write(json.dumps(
                        {"id": a["id"], "kind": "selfcheck", "text": "dup", "ts": 0.0},
                        ensure_ascii=False) + "\n")
                caught = [p for p in self._scan_jsonl() if p not in base]
                self._rewrite()  # 撤回注入（原子重写）
            if not any("不可解析" in p for p in caught):
                failures.append(f"① 未检出不可解析行: {caught}")
            if not any("缺必含字段" in p for p in caught):
                failures.append(f"① 未检出缺字段行: {caught}")
            if not any("id 重复" in p for p in caught):
                failures.append(f"② 未检出重复 id 行: {caught}")
            with self._lock:
                residue = self._scan_jsonl()
            if residue:
                failures.append(f"①② 注入撤回后文件仍有完整性问题: {residue}")

            # ③ 全/半角括号：两种 query 都得同时命中两条（bigram 天然容错）
            want = {"测试群(12)", "测试群（12）"}
            for query in ("测试群(12)", "测试群（12）"):
                got = {r["text"] for r in self.recall(query, k=10)}
                if not want <= got:
                    failures.append(
                        f"③ 全/半角括号 recall 未同时命中 query={query!r}: {sorted(got)}")

            # ④ 空 query：不炸、零相关不捞（recency 不得单独构成召回）
            try:
                leaked = self.recall("", k=5)
            except Exception as exc:
                failures.append(f"④ recall 空 query 抛异常: {exc!r}")
            else:
                if leaked:
                    failures.append(f"④ recall 空 query 应返回空列表: {leaked}")
        finally:
            # ⑤ 无论如何清理（KbSelfCheck 的 finally 删光模式），并核验复原
            forgot = (self.forget(a["id"]), self.forget(b["id"]))
            if not all(forgot):
                failures.append(f"⑤ forget 自检临时条目失败: {forgot}")
            if len(self._records) != before:
                failures.append(
                    f"⑤ 自检后内存条目数未复原: {before} -> {len(self._records)}")
            on_disk = MemoryStore(self.path).stats()["total"]
            if on_disk != before:
                failures.append(f"⑤ 自检后磁盘条目数未复原: {before} -> {on_disk}")
        return failures
