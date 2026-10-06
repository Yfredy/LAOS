# laos/knowledge.py
"""本地知识检索（KnowledgeRetriever）——LLM 前置的廉价短路层。

语义复现自 voicenpu_engine（Gitee bravexyz，AGPL-3.0）的
src/llm/knowledge_retriever.cpp：独立实现，非代码拷贝。上游设计：
命中本地知识库的问句直接绕过 LLM（回答零延迟、零算力），未命中才
落入 Qwen——"先查表、再推理"的两级路由。

打分语义（与上游逐条对齐）：
1. 符号化：ASCII 字母数字折叠成词（小写），非 ASCII 按码点切成单符号
   （CJK 一字一符）；中文标点从忽略表中剔除（，。！？；：、（）《》""''）；
2. 词项 = 相邻符号 bigram（单符号句只有 unigram）；
3. 候选要求交集 ≥ 2 个词项；
4. score = 0.7 * |交|/|query 词项| + 0.3 * |交|/|question 词项|；
5. 任一方向整句子串命中 → score = 1.0；
6. 最高分 < min_score（上游默认 0.58）→ 未命中。

数据格式与上游 company_knowledge.jsonl 兼容：
    {"id": ..., "answer": ..., "questions": [...], ...}
纯 stdlib（json 替代上游 yaml-cpp 解析同一 JSONL 行格式）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# 上游 ignored_punctuation 的码点展开（，。！？；：、（）《》“”‘’）
_IGNORED = set("，。！？；：、（）《》“”‘’")


def _symbols(text: str) -> List[str]:
    """符号化：ASCII 词折叠 + CJK 单字；忽略中文标点。"""
    out: List[str] = []
    ascii_run: List[str] = []
    for ch in text:
        if ch.isascii():
            if ch.isalnum():
                ascii_run.append(ch.lower())
                continue
            if ascii_run:
                out.append("".join(ascii_run))
                ascii_run = []
            continue
        if ascii_run:
            out.append("".join(ascii_run))
            ascii_run = []
        if ch not in _IGNORED:
            out.append(ch)
    if ascii_run:
        out.append("".join(ascii_run))
    return out


def _features(text: str) -> Tuple[str, frozenset]:
    """（归一化串，bigram 词项集）。"""
    syms = _symbols(text)
    normalized = "".join(syms)
    terms = set()
    if len(syms) == 1:
        terms.add(syms[0])
    for a, b in zip(syms, syms[1:]):
        terms.add(a + b)
    return normalized, frozenset(terms)


@dataclass
class KnowledgeMatch:
    id: str
    answer: str
    score: float
    elapsed_ms: float


class KnowledgeRetriever:
    """JSONL 知识库加载 + bigram 覆盖率检索。"""

    MAX_QUERY_BYTES = 1024  # 超长问句直接判未命中（上游同款防滥用闸）

    def __init__(self) -> None:
        self._entries: List[Tuple[str, str, List[Tuple[str, frozenset]]]] = []

    def load(self, path: str | Path) -> bool:
        """逐行加载 JSONL；任一行缺 id/answer/questions 或整库为空 → False。"""
        loaded = []
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    node = json.loads(line)
                    if ("id" not in node or "answer" not in node or
                            not isinstance(node.get("questions"), list)):
                        return False
                    questions = []
                    for q in node["questions"]:
                        norm, terms = _features(str(q))
                        if terms:
                            questions.append((norm, terms))
                    if not questions:
                        return False
                    loaded.append((str(node["id"]), str(node["answer"]), questions))
        except (OSError, json.JSONDecodeError):
            return False
        if not loaded:
            return False
        self._entries = loaded
        return True

    def size(self) -> int:
        return len(self._entries)

    def search(self, text: str, min_score: float = 0.58,
               clock: Callable[[], float] = time.perf_counter) -> Optional[KnowledgeMatch]:
        """最佳命中或 None。打分语义见模块 docstring。"""
        start = clock()
        if not text or len(text.encode("utf-8")) > self.MAX_QUERY_BYTES:
            return None
        q_norm, q_terms = _features(text)
        if not q_terms:
            return None
        best: Optional[Tuple[float, str, str]] = None
        for entry_id, answer, questions in self._entries:
            for c_norm, c_terms in questions:
                inter = len(q_terms & c_terms)
                if inter < 2:
                    continue
                score = 0.7 * inter / len(q_terms) + 0.3 * inter / len(c_terms)
                if c_norm in q_norm or q_norm in c_norm:
                    score = 1.0
                if best is None or score > best[0]:
                    best = (score, entry_id, answer)
        if best is None or best[0] < min_score:
            return None
        return KnowledgeMatch(best[1], best[2], best[0],
                              (clock() - start) * 1000.0)
