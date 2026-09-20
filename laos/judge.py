"""judge —— System-One 判断器（可插拔后端 + 零依赖兜底）。

Brain 的快问快答通道：给定 (context, question)，按三种判断型（noul /
choice / score）返回 JudgeResult(verdict, confidence, raw)。后端可插拔
（Kconfig 思想，与 laos/enforcement.select 同款哲学），由环境变量
LAOS_JEV_BACKEND 选择：

    none(默认)|rule → RuleBackend   零依赖关键词兜底，保证默认链路可测
    cloud           → CloudBackend  TypeSafe System-One API（LAOS_JEV_API_KEY）
    local           → LocalBackend  OpenAI 兼容本地端点（LAOS_JEV_ENDPOINT）

HTTP 一律走 curl 子进程（不经 urllib，代理/沙箱策略友好，stdlib 之外零依赖）。
请求体契约（供 Task 5 装配引用，Cloud/Local 共用同一 {"context","question",
"mode","options","levels"} 语义）：

    Cloud: POST {LAOS_JEV_BASE_URL 默认 https://api.typesafe.ai/v1}/systemone
           头 Authorization: Bearer {LAOS_JEV_API_KEY}
           体 {"mode":"noul|choice|score","context":...,"question":...,
               "options":[...],"levels":N}
    Local: POST {LAOS_JEV_ENDPOINT}/v1/chat/completions（OpenAI 兼容）
           体 {"messages":[{"role":"user","content": JSON.stringify(
               {context,question,mode,options,levels})}]}
           响应 choices[0].message.content 解析为 JSON
           {"verdict":...,"confidence":...}

verdict 词表："allow" | "deny" | "level_0".."level_9" | 选项文本。
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field

__all__ = [
    "CloudBackend",
    "DENY_WORDS",
    "JudgeBackend",
    "JudgeError",
    "JudgeResult",
    "LocalBackend",
    "RuleBackend",
    "select",
]

DEFAULT_CLOUD_BASE_URL = "https://api.typesafe.ai/v1"
DEFAULT_TIMEOUT = 10.0
DENY_CONFIDENCE = 0.99
DENY_WORDS: tuple[str, ...] = ("危险", "删除全部", "格式化", "rm -rf", "泄露隐私")


class JudgeError(RuntimeError):
    """判断后端请求/解析失败（网络、端点缺失、响应不合契约）。"""


@dataclass
class JudgeResult:
    """一次判断的结果：结论 + 置信度 + 后端原始返回（审计用）。"""

    verdict: str      # "allow" | "deny" | "level_0".."level_9" | 选项文本
    confidence: float # 0..1
    raw: dict = field(default_factory=dict)


class JudgeBackend:
    """判断后端契约：三种判断型，各返回一个 JudgeResult。"""

    name = "base"

    def noul(self, context: str, question: str) -> JudgeResult:
        """是非判断：可行/不可行 → "allow" | "deny"。"""
        raise NotImplementedError

    def choice(self, context: str, question: str,
               options: list[str]) -> JudgeResult:
        """多选一判断：verdict 为所选选项文本。"""
        raise NotImplementedError

    def score(self, context: str, question: str, levels: int = 5) -> JudgeResult:
        """分级判断：verdict 为 "level_0".."level_{levels-1}"。"""
        raise NotImplementedError


# ---------------------------------------------------------------- 后端实现


class RuleBackend(JudgeBackend):
    """零依赖兜底：确定性关键词规则，保证默认链路可测。

    noul：question 内含 deny 词表任一词（不区分大小写）→ deny 0.99，
    否则 allow 0.5；choice：均匀打分（等概率）→ 第一项，置信度 1/N，
    空选项 fail-safe 拒绝；score：均匀打分 → 中位 level，置信度 1/levels。
    """

    name = "rule"

    def noul(self, context: str, question: str) -> JudgeResult:
        q = (question or "").lower()
        for word in DENY_WORDS:
            if word.lower() in q:
                return JudgeResult("deny", DENY_CONFIDENCE,
                                   {"backend": self.name, "mode": "noul",
                                    "matched": word})
        return JudgeResult("allow", 0.5,
                           {"backend": self.name, "mode": "noul",
                            "matched": None})

    def choice(self, context: str, question: str,
               options: list[str]) -> JudgeResult:
        if not options:
            return JudgeResult("deny", 0.0,
                               {"backend": self.name, "mode": "choice",
                                "reason": "options 为空，兜底拒绝"})
        return JudgeResult(str(options[0]), 1.0 / len(options),
                           {"backend": self.name, "mode": "choice",
                            "uniform": True})

    def score(self, context: str, question: str,
              levels: int = 5) -> JudgeResult:
        n = max(int(levels), 1)
        return JudgeResult(f"level_{n // 2}", 1.0 / n,
                           {"backend": self.name, "mode": "score",
                            "levels": n, "uniform": True})


def _clamp01(value: object) -> float:
    """置信度钳制到 0..1（后端返回越界/缺型时兜 0.0）。"""
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return min(max(f, 0.0), 1.0)


def _verdict_from_payload(payload: dict) -> tuple[str, float]:
    """从响应 JSON 提取 (verdict, confidence)。

    两种形态：顶层 {"verdict","confidence"}（Cloud 直返式）；或 OpenAI
    兼容 choices[0].message.content 内嵌 JSON（Local 式）。
    """
    if "verdict" in payload:
        return str(payload.get("verdict")), _clamp01(payload.get("confidence", 0.0))
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        try:
            inner = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise JudgeError(
                f"choices[0].message.content 不是合法 JSON：{content[:120]!r}") from exc
        if not isinstance(inner, dict) or "verdict" not in inner:
            raise JudgeError("content JSON 缺少 verdict 字段")
        return str(inner.get("verdict")), _clamp01(inner.get("confidence", 0.0))
    raise JudgeError("响应中既无 verdict 也无 choices，无法判断")


def _post_curl(url: str, body: dict, headers: dict[str, str],
               timeout: float = DEFAULT_TIMEOUT) -> dict:
    """curl 子进程发一次 POST JSON，返回解析后的响应 dict。

    请求体以 UTF-8 原文发送（ensure_ascii=False，中文不做 ASCII 转义）；
    curl 非零退出或响应非 JSON → JudgeError。
    """
    cmd = ["curl", "-sS", "--max-time", f"{timeout:g}", "-X", "POST", url,
           "-H", "Content-Type: application/json"]
    for key, value in headers.items():
        cmd += ["-H", f"{key}: {value}"]
    cmd += ["--data-binary", json.dumps(body, ensure_ascii=False)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout + 5.0)
    except subprocess.TimeoutExpired as exc:
        raise JudgeError(f"curl 超时：{url}") from exc
    except OSError as exc:
        raise JudgeError(f"curl 不可用：{exc}") from exc
    if proc.returncode != 0:
        raise JudgeError(
            f"curl 退出码 {proc.returncode}：{(proc.stderr or '').strip() or url}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"响应不是合法 JSON：{proc.stdout[:200]!r}") from exc


class CloudBackend(JudgeBackend):
    """TypeSafe System-One API（LAOS_JEV_API_KEY / LAOS_JEV_BASE_URL）。

    请求契约见模块 docstring。缺 key 时构造不报错，调用时 fail-loud
    （尊重显式选择，与 enforcement 同款哲学）。
    """

    name = "cloud"

    def __init__(self, api_key: str | None = None,
                 base_url: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(
            "LAOS_JEV_API_KEY", "")
        base = base_url if base_url is not None else os.environ.get(
            "LAOS_JEV_BASE_URL", DEFAULT_CLOUD_BASE_URL)
        self.base_url = base.rstrip("/")
        self.timeout = timeout

    def _judge(self, mode: str, context: str, question: str,
               options: list[str], levels: int) -> JudgeResult:
        if not self.api_key:
            raise JudgeError("缺少 TypeSafe API key：请设置 LAOS_JEV_API_KEY")
        url = f"{self.base_url}/systemone"
        body = {"mode": mode, "context": context, "question": question,
                "options": options, "levels": levels}
        payload = _post_curl(url, body,
                             {"Authorization": f"Bearer {self.api_key}"},
                             self.timeout)
        verdict, confidence = _verdict_from_payload(payload)
        return JudgeResult(verdict, confidence, payload)

    def noul(self, context: str, question: str) -> JudgeResult:
        return self._judge("noul", context, question, [], 0)

    def choice(self, context: str, question: str,
               options: list[str]) -> JudgeResult:
        return self._judge("choice", context, question, list(options), 0)

    def score(self, context: str, question: str,
              levels: int = 5) -> JudgeResult:
        return self._judge("score", context, question, [], int(levels))


class LocalBackend(JudgeBackend):
    """OpenAI 兼容本地端点（LAOS_JEV_ENDPOINT，如 NanoJev/simple-jev）。

    请求契约见模块 docstring：判断载荷整体 JSON.stringify 后作为单条
    user 消息 content；响应 choices[0].message.content 解析为
    {"verdict":...,"confidence":...}。缺端点时调用时 fail-loud。
    """

    name = "local"

    def __init__(self, endpoint: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        endpoint = endpoint if endpoint is not None else os.environ.get(
            "LAOS_JEV_ENDPOINT", "")
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def _judge(self, mode: str, context: str, question: str,
               options: list[str], levels: int) -> JudgeResult:
        if not self.endpoint:
            raise JudgeError("缺少本地判断端点：请设置 LAOS_JEV_ENDPOINT")
        url = f"{self.endpoint}/v1/chat/completions"
        inner = {"context": context, "question": question, "mode": mode,
                 "options": options, "levels": levels}
        body = {"messages": [{"role": "user",
                              "content": json.dumps(inner, ensure_ascii=False)}]}
        payload = _post_curl(url, body, {}, self.timeout)
        verdict, confidence = _verdict_from_payload(payload)
        return JudgeResult(verdict, confidence, payload)

    def noul(self, context: str, question: str) -> JudgeResult:
        return self._judge("noul", context, question, [], 0)

    def choice(self, context: str, question: str,
               options: list[str]) -> JudgeResult:
        return self._judge("choice", context, question, list(options), 0)

    def score(self, context: str, question: str,
              levels: int = 5) -> JudgeResult:
        return self._judge("score", context, question, [], int(levels))


# ---------------------------------------------------------------- 工厂


def select() -> JudgeBackend:
    """按 LAOS_JEV_BACKEND 选择判断后端：none(默认)|rule|cloud|local。

    未知值不炸链路：兜底 RuleBackend（与 enforcement.select 同款哲学）。
    """
    want = os.environ.get("LAOS_JEV_BACKEND", "none").strip().lower()
    if want == "cloud":
        return CloudBackend()
    if want == "local":
        return LocalBackend()
    return RuleBackend()  # none | rule | 未知值 → 零依赖兜底
