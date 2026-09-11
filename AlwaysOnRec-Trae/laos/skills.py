"""skills —— 技能库：成功任务序列沉淀为可复用技能（"越用越聪明"）。

一个"技能" = 一次成功任务的（工具调用序列签名 + 任务描述），存入
MemoryStore（kind="skill"）。新任务到来时按任务文本检索相似技能，
以 [skill-hint] 注入 Agent 上下文——过去解决过的问题，下次直接给出
历史解法提示。

设计原则：本模块只做**提取与匹配**，存储复用 MemoryStore（零新存储层、
零依赖）；learn 有严格门控（失败/被拒/单步任务不学——噪声不是经验）。
"""

from __future__ import annotations


def digest_trace(trace: list[dict]) -> str:
    """工具调用序列签名：`tool1(arg键集)→tool2(arg键集)`，跳过非 syscall 条目。"""
    parts = []
    for entry in trace or []:
        if "syscall" not in entry:
            continue
        keys = ",".join(sorted((entry.get("args") or {}).keys()))
        parts.append(f"{entry['syscall']}({keys})")
    return "→".join(parts)


class SkillStore:
    """技能的提取、门控与检索（存储委托 MemoryStore，kind="skill"）。"""

    def __init__(self, memory):
        self.memory = memory

    def learn_from_result(self, result, task: str) -> dict | None:
        """成功任务 → 沉淀为技能；失败/被拒/单步任务不学（噪声不是经验）。"""
        if not getattr(result, "ok", False):
            return None
        if getattr(result, "denied", 0):
            return None
        if getattr(result, "syscalls", 0) < 2:
            return None  # 单步调用没有"序列"可言
        signature = digest_trace(result.trace)
        answer = (getattr(result, "answer", "") or "")[:100]
        return self.memory.remember(
            kind="skill",
            text=f"{task} ⇒ {answer}",
            tags=[signature],
        )

    def match(self, query: str, k: int = 3) -> list[dict]:
        """按任务文本检索相似技能（只返回 kind=="skill"）。"""
        return [m for m in self.memory.recall(query, k=k) if m.get("kind") == "skill"]
