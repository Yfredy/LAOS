"""decide —— Clef 兼容决策层：三判型 schema + 类型化输出 + 规则后端。

docs/research/2026-10-07-cloudflare-clef.md §二 的接口化：决策步接收
state（dict），按 DecisionSchema（noul/choice/score 三判型，与 laos 判断层
调研的三判型原语同名同义）返回带概率的类型化 Decision，供代码路由 /
升级 / 转人工。Clef 的延迟优势来自 prefill-only 非自回归——本模块是它的
零依赖规则后端版（纯 stdlib，judge.py 同款哲学）。

三判型语义：

    noul   二值判断：answer "yes"|"no"，probabilities {"yes":p,"no":1-p}
    choice 选项集：answer 为所选选项文本，probabilities 覆盖全部选项、和=1
    score  连续值：answer 按 threshold 阈值化，probabilities {"score":0..1}

类型化输出纪律（Decision 构造即校验，fail-loud）：
    - 概率越界（<0 或 >1）→ ValueError；
    - 多键概率之和显著偏离 1（容差 1e-6）→ ValueError；单键豁免（score
      的单键即分数本身，不是分布）。

后端插拔表（register_backend/get_backend，Task 3 clef 后端挂点）：
    "rule" 预登记（本模块 RuleBackend 实例，可直接调用）；未登记名
    KeyError，不静默兜底——显式选择尊重显式失败，与 enforcement 的
    未知值兜底不同（这里是开发者装配面，不是运行时配置面）。

RuleBackend 打分规则（确定性，保证默认链路可测）：
    noul   按 state 布尔字段（yes/decision/verdict/answer/flag/ok，查找
           序在前者优先）→ p_yes∈{0,1}；否则按数值字段（confidence/
           probability/prob/score/value）透传为 p_yes；无命中均匀 0.5/0.5
           并在 source 标注 uniform。
    choice 把 state 全部字符串值拼成文本，各选项分词（无空白的中日文整串
           作一个关键词）计包含次数为强度，归一化为概率；总强度 0 → 均匀
           1/N（source 标注 uniform），answer 取第一最大。
    score  按数值字段（score/value/confidence/probability/prob/rating）
           钳制到 [0,1] 透传（规则后端兜底不炸链路），answer = 分数
           >= threshold ? "yes" : "no"；无命中中点 0.5（标注 uniform）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = [
    "DECISION_TYPES",
    "SUM_TOLERANCE",
    "Decision",
    "DecisionSchema",
    "RuleBackend",
    "get_backend",
    "register_backend",
]

#: 三判型词表（与 Clef schema 同名同义）
DECISION_TYPES = ("noul", "choice", "score")

#: 多键概率之和偏离 1 的容差（浮点归一化余差在此内算"和=1"）
SUM_TOLERANCE = 1e-6

# RuleBackend 的 state 字段查找序（在前者优先）
NOUL_BOOL_KEYS = ("yes", "decision", "verdict", "answer", "flag", "ok")
NOUL_PROB_KEYS = ("confidence", "probability", "prob", "score", "value")
SCORE_KEYS = ("score", "value", "confidence", "probability", "prob", "rating")


def _clamp01(value: float) -> float:
    """钳制到 [0,1]（规则后端对越界 state 的兜底）。"""
    return min(max(float(value), 0.0), 1.0)


def _is_number(value: object) -> bool:
    """数值判定：int/float 且排除 bool（True 是 int 的子类）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class DecisionSchema:
    """决策步的输入契约（Clef 三判型）。

    type      "noul" | "choice" | "score"
    options   仅 choice 用：非空、不重复的选项列表（重复会让
              probabilities 的 dict 键坍缩，构造即拒）
    threshold 阈值（默认 0.5）：noul 作用于 p(yes)，score 作用于分数，
              answer 统一取 >= 语义（含等号）
    """

    type: str
    options: list[str] | None = None
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if self.type not in DECISION_TYPES:
            raise ValueError(
                f"type 必须是 {DECISION_TYPES} 之一，实测 {self.type!r}")
        if self.type == "choice":
            if not isinstance(self.options, (list, tuple)) or not self.options:
                raise ValueError("choice 判型必须提供非空 options")
            options = list(self.options)
            for option in options:
                if not isinstance(option, str) or not option.strip():
                    raise ValueError(f"选项必须是非空字符串：{option!r}")
            if len(set(options)) != len(options):
                raise ValueError(f"选项重复（probabilities 键会坍缩）：{options}")
            object.__setattr__(self, "options", options)
        elif self.options is not None:
            raise ValueError("options 仅 choice 判型可用")
        if not _is_number(self.threshold) or not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"threshold 必须是 [0,1] 内数值，实测 {self.threshold!r}")


@dataclass(frozen=True)
class Decision:
    """决策步的类型化输出：结论 + 概率分布 + 来源 + 校准标记。

    校验（构造即拒，ValueError）：
      - 每个概率都必须在 [0,1]（越界即拒）；
      - 多键时概率之和 ≈ 1（|sum-1| <= SUM_TOLERANCE）；单键豁免。
    calibrated 留给 Task 3 的 clef 后端：Brier/RLCD 校准过的概率才置
    True——决策不只对答案负责，还要对概率负责。
    """

    answer: str
    probabilities: dict[str, float]
    source: str
    calibrated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.probabilities, dict):
            raise ValueError(
                f"probabilities 必须是 dict，实测 {type(self.probabilities)!r}")
        for key, value in self.probabilities.items():
            if not _is_number(value):
                raise ValueError(f"概率 {key!r} 不是数值：{value!r}")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"概率越界 [0,1]：{key}={value!r}")
        if len(self.probabilities) > 1:
            total = sum(float(v) for v in self.probabilities.values())
            if abs(total - 1.0) > SUM_TOLERANCE:
                raise ValueError(
                    f"多键概率之和应≈1（容差 {SUM_TOLERANCE}），实测 {total:.6f}")


class RuleBackend:
    """零依赖规则后端：确定性打分，保证默认链路可测。

    打分规则见模块 docstring。可调用实例（__call__ → decide），因此可直接
    登记进后端插拔表。
    """

    name = "rule"

    def decide(self, state: dict, schema: DecisionSchema) -> Decision:
        """按 schema 判型路由到对应规则打分。"""
        if schema.type == "noul":
            return self._decide_noul(state, schema)
        if schema.type == "choice":
            return self._decide_choice(state, schema)
        return self._decide_score(state, schema)

    def __call__(self, state: dict, schema: DecisionSchema) -> Decision:
        return self.decide(state, schema)

    # ---------------------------------------------------------------- noul

    def _decide_noul(self, state: dict, schema: DecisionSchema) -> Decision:
        for key in NOUL_BOOL_KEYS:
            value = state.get(key)
            if isinstance(value, bool):
                p_yes = 1.0 if value else 0.0
                return self._noul_result(p_yes, schema, self.name)
        for key in NOUL_PROB_KEYS:
            value = state.get(key)
            if _is_number(value):
                return self._noul_result(_clamp01(value), schema, self.name)
        return self._noul_result(0.5, schema, f"{self.name}:uniform")

    @staticmethod
    def _noul_result(p_yes: float, schema: DecisionSchema,
                     source: str) -> Decision:
        answer = "yes" if p_yes >= schema.threshold else "no"
        return Decision(answer, {"yes": p_yes, "no": 1.0 - p_yes}, source)

    # -------------------------------------------------------------- choice

    def _decide_choice(self, state: dict,
                       schema: DecisionSchema) -> Decision:
        text = " ".join(
            str(v) for v in state.values() if isinstance(v, str)).lower()
        strengths = []
        for option in schema.options or []:
            tokens = [t for t in option.lower().split() if t]
            if not tokens:  # 无空白语（中文等）：整串作一个关键词
                tokens = [option.lower()]
            strengths.append(sum(text.count(token) for token in tokens))
        total = sum(strengths)
        if total <= 0:
            count = len(schema.options or [])
            probabilities = {option: 1.0 / count for option in schema.options}
            return Decision(schema.options[0], probabilities,
                            f"{self.name}:uniform")
        probabilities = {option: strength / total
                         for option, strength in zip(schema.options, strengths)}
        best = max(range(len(strengths)), key=strengths.__getitem__)  # 并列取第一
        return Decision(schema.options[best], probabilities, self.name)

    # --------------------------------------------------------------- score

    def _decide_score(self, state: dict,
                      schema: DecisionSchema) -> Decision:
        for key in SCORE_KEYS:
            value = state.get(key)
            if _is_number(value):
                score = _clamp01(value)
                answer = "yes" if score >= schema.threshold else "no"
                return Decision(answer, {"score": score}, self.name)
        answer = "yes" if 0.5 >= schema.threshold else "no"
        return Decision(answer, {"score": 0.5}, f"{self.name}:uniform")


# ---------------------------------------------------------------- 插拔表

#: 后端契约：fn(state, schema) -> Decision（RuleBackend 实例可直接调用）
BackendFn = Callable[[dict, DecisionSchema], Decision]

_BACKENDS: dict[str, BackendFn] = {}


def register_backend(name: str, fn: BackendFn) -> BackendFn:
    """登记决策后端（同名覆盖，支持热替换）。返回 fn 以便作装饰器。"""
    _BACKENDS[name] = fn
    return fn


def get_backend(name: str) -> BackendFn:
    """按名取后端；未登记 → KeyError（装配面 fail-loud，不静默兜底）。"""
    return _BACKENDS[name]


# 默认后端预登记：clef 后端由 Task 3 在此挂点（register_backend("clef", ...)）
register_backend("rule", RuleBackend())
