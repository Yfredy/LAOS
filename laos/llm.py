"""llm —— laos 的云端大脑（OpenAI 兼容 chat.completions，纯 stdlib）。

opt-in：`LAOS_LLM_BASE_URL` + `LAOS_LLM_MODEL` 两值齐（`LAOS_LLM_KEY` 可空
——本地推理服务 llama.cpp / ollama 的 OpenAI 兼容端点无需鉴权）才启用；
未配置时 `LLMClient.from_env()` 返回 None，调用方优雅降级（laosweb
/api/chat 返回 503 提示——与 sentinel 未装配同款哲学：能力缺席不假装存在）。

零依赖红线：urllib.request 直连；首版**非流式**（回复完整返回——手机
WebView 轮询模型下非流式反而省事，流式留给后续波）。

隐私红线：审计只记 谁调/模型/耗时/成败与长度，**内容永不进审计**
（与 d.wake 事件同款脱敏级）；本模块无状态，对话历史由调用方持有。
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional, Sequence

__all__ = ["LLMClient", "LLMError", "DEFAULT_SYSTEM"]

DEFAULT_SYSTEM = (
    "你是 nanoLAOS（laos · Linux AgentOS）上的个人 agent——laos 是 Linux "
    "内核治理在用户态的延伸，你是被治理的负载之一。用中文回复，简洁直接；"
    "不确定就说不确定，不编造。用户的数据只属于用户。"
)


class LLMError(RuntimeError):
    """云端调用失败（网络/HTTP/响应形状）。调用方降级，不崩链路。"""


@dataclass(frozen=True)
class LLMClient:
    """一个 OpenAI 兼容端点的最小封装。无状态、线程安全（纯函数式调用）。"""

    base_url: str
    model: str
    api_key: str = ""
    timeout_s: float = 60.0
    system: str = DEFAULT_SYSTEM

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> Optional["LLMClient"]:
        """三值 env 装配；缺 BASE_URL 或 MODEL → None（调用方降级）。"""
        env = os.environ if env is None else env

        def _num(name: str, default: float) -> float:
            try:
                return float(env.get(name, "") or default)
            except ValueError:
                return default

        base = str(env.get("LAOS_LLM_BASE_URL", "")).strip().rstrip("/")
        model = str(env.get("LAOS_LLM_MODEL", "")).strip()
        if not base or not model:
            return None
        return cls(
            base_url=base,
            model=model,
            api_key=str(env.get("LAOS_LLM_KEY", "")).strip(),
            timeout_s=_num("LAOS_LLM_TIMEOUT_S", 60.0),
            system=str(env.get("LAOS_LLM_SYSTEM", "")).strip() or DEFAULT_SYSTEM,
        )

    def chat(self, messages: Sequence[dict]) -> str:
        """一轮对话。messages=[{"role","content"},...]（调用方组好 system）。

        返回首个 choice 的 content 文本；网络/HTTP/形状异常统一 LLMError
        （fail 方向：抛错给调用方降级，不返回半真半假的内容）。
        """
        url = (self.base_url if self.base_url.endswith("/chat/completions")
               else self.base_url + "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps({"model": self.model, "messages": list(messages)},
                            ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # urllib.error/超时/坏 JSON 一律归一
            raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected response shape: {exc}") from exc
