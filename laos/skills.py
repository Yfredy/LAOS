"""skills —— 技能库：成功任务序列沉淀为可复用技能（"越用越聪明"）。

一个"技能" = 一次成功任务的（工具调用序列签名 + 任务描述），存入
MemoryStore（kind="skill"）。新任务到来时按任务文本检索相似技能，
以 [skill-hint] 注入 Agent 上下文——过去解决过的问题，下次直接给出
历史解法提示。

设计原则：本模块只做**提取与匹配**，存储复用 MemoryStore（零新存储层、
零依赖）；learn 有严格门控（失败/被拒/单步任务不学——噪声不是经验）。
"""

from __future__ import annotations

from typing import Any

# Jev 沉淀预审（Task 5，opt-in）：record(judge=...) 传入判断后端时先问
# 一句——deny（= 轨迹没达成目标，成功只是"模型自称"）拒绝沉淀返回 None；
# 审计留在调用方（skills 层只管收与拒，不写审计）。
# Task 3 升级为 criteria 式两段问句（指示段 + 判据段，方法论源自
# jev-chat-jarvis questions.py，MIT；题面按 laos 语义重写）：题首保留原
# 问句不变，判据段钉住 deny 方向 = 不沉淀。判据文本刻意避开
# judge.DENY_WORDS——RuleBackend 只扫问句关键词，问句自带 deny 词会让
# 规则后端对该 gate 无差别全拒
SKILL_JUDGE_QUESTION = (
    "此任务轨迹确实达成了目标吗？依据任务描述与轨迹证据判断：工具调用"
    "是否真的完成了任务目标，而非仅凭模型自称成功。\n"
    "判“是”（allow，可沉淀为技能）当：轨迹有可核验的完成证据（结果 ok、"
    "产出物已写入、验证性调用通过），且解法对同类任务可复用；"
    "判“否”（deny，不沉淀）当：目标未达成、成功只是模型断言而无证据、"
    "调用被拒或中途放弃、或属无复用价值的一次性操作，任一命中即否。"
)


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

    def record(self, result, task: str,
               judge: Any | None = None) -> dict | None:
        """沉淀入口（Task 5 Produces 名）：带 Jev 质量闸的 learn_from_result。"""
        return self.learn_from_result(result, task, judge=judge)

    def learn_from_result(self, result, task: str,
                          judge: Any | None = None) -> dict | None:
        """成功任务 → 沉淀为技能；失败/被拒/单步任务不学（噪声不是经验）。

        judge 非 None 时（Task 5，opt-in）在既有门控之后、落库之前先问
        noul(task, SKILL_JUDGE_QUESTION)：deny（= 轨迹没达成目标，成功只是
        "模型自称"）→ 不沉淀返回 None；不传 judge（默认）时此分支不存在，
        行为与现状一致。judge 放便宜门控之后——云端后端可能慢，不白问。
        """
        if not getattr(result, "ok", False):
            return None
        if getattr(result, "denied", 0):
            return None
        if getattr(result, "syscalls", 0) < 2:
            return None  # 单步调用没有"序列"可言
        if judge is not None:
            if judge.noul(str(task), SKILL_JUDGE_QUESTION).verdict == "deny":
                return None
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
