"""Brain —— AgentOS 的“CPU”。

传统 OS 里 CPU 是可替换的硬件；AgentOS 里 LLM 是可替换的后端。
这里定义统一接口，并提供两个实现：

  * ScriptedBrain  —— 确定性策略机，无 API key 也能完整跑通 demo
  * OpenAIChatBrain —— 兼容 OpenAI /v1/chat/completions 的真实后端（零依赖，走 urllib）
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)
    call_id: str = ""


@dataclass
class Thought:
    """一次 think() 的产物：要么说话，要么发起若干系统调用。"""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish: bool = False


class Brain:
    name = "abstract"

    def think(self, messages: list[dict], tools: list[dict]) -> Thought:
        raise NotImplementedError


# --------------------------------------------------------------------------
# 确定性后端：把“意图”翻译成确定的 syscall 序列
# --------------------------------------------------------------------------
class ScriptedBrain(Brain):
    """不联网、不花钱、可复现。用于验证内核本身是否正确。

    它按固定的运维 SOP 行动（一个最小的 ReAct 状态机）：

        sys.info -> fs.read -> [缺失则 fs.append] -> fs.read 校验
                 -> proc.exec('rm -rf /') 越权探测 -> 收尾汇报

    最后一步是故意的：用来演示内核能力表如何返回 EPERM。
    """

    name = "scripted"

    def __init__(
        self,
        branch: str = "main",
        target: str = "workspace/hosts",
        record: str = "myapp.local",
        entry: str = "127.0.0.1 myapp.local",
        deny_probe: str | None = None,
        deny_args: dict | None = None,
    ):
        self.virt_path = f"/{branch}/{target.lstrip('/')}"
        self.record = record
        self.entry = entry
        self._step = 0
        # 故意发起一次越权 syscall，用于验证内核能力表是否真的拦得住
        self.deny_probe = deny_probe
        self.deny_args = deny_args or {}

    # -- 工具 ------------------------------------------------------------
    @staticmethod
    def _last_tool_output(messages: list[dict], tool_name: str | None = None) -> str:
        for m in reversed(messages):
            if m.get("role") == "tool":
                if tool_name is None or m.get("name") == tool_name:
                    return str(m.get("content", ""))
        return ""

    def _act(self, step: int, name: str, say: str, args: dict) -> Thought:
        return Thought(text=say, tool_calls=[ToolCall(name, args, f"c{step}")])

    # -- 主循环 ----------------------------------------------------------
    def think(self, messages: list[dict], tools: list[dict]) -> Thought:
        available = {t["name"] for t in tools}
        self._step += 1
        step = self._step

        # 越权探测：明知没有权限也要调，验证内核会不会真拦
        if self.deny_probe:
            probe, self.deny_probe = self.deny_probe, None
            return self._act(
                step, probe, f"能力探测：尝试调用未授权的 {probe}。", dict(self.deny_args)
            )

        if step == 1:
            if "sys.info" not in available:
                return Thought(text="sys 驱动未授权，跳过环境采集。")
            return self._act(step, "sys.info", "先采集宿主信息，确认运行环境。", {})

        if step == 2:
            if "fs.read" not in available:
                return Thought(text="fs 驱动未授权，无法读取目标文件。", finish=True)
            return self._act(step, "fs.read", f"读取 {self.virt_path}", {"path": self.virt_path})

        if step == 3:
            content = self._last_tool_output(messages, "fs.read")
            if self.record in content:
                return Thought(text="目标记录已存在，无需修改，进入校验。")
            if "fs.append" not in available:
                return Thought(text="fs.append 未授权，无法写入。", finish=True)
            return self._act(
                step,
                "fs.append",
                "记录缺失，追加一条 hosts 记录。",
                {"path": self.virt_path, "content": self.entry + "\n"},
            )

        if step == 4:
            return self._act(step, "fs.read", "回读校验写入结果。", {"path": self.virt_path})

        if step == 5:
            if "proc.exec" not in available:
                return Thought(text="proc 驱动未出现在可见 syscall 表中，跳过越权探测。")
            return self._act(
                step,
                "proc.exec",
                "尝试执行一条高危命令，验证内核的能力边界。",
                {"cmdline": "rm -rf /"},
            )

        content = self._last_tool_output(messages, "fs.read")
        verdict = "已生效" if self.record in content else "未生效，需要人工介入"
        return Thought(text=f"任务完成。目标记录 {self.record} {verdict}。", finish=True)


# --------------------------------------------------------------------------
# 真实后端
# --------------------------------------------------------------------------
class OpenAIChatBrain(Brain):
    """兼容 OpenAI 协议的真实 LLM 后端。设置 OPENAI_API_KEY 后自动可用。"""

    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 60,
    ):
        self.model = model or os.environ.get("LAOS_LLM_MODEL", "gpt-4o-mini")
        self.base_url = (
            base_url or os.environ.get("LAOS_LLM_BASE_URL") or "https://api.openai.com/v1"
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _tools_payload(self, tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    def think(self, messages: list[dict], tools: list[dict]) -> Thought:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = self._tools_payload(tools)
            payload["tool_choice"] = "auto"

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return Thought(text=f"LLM 调用失败: HTTP {exc.code} {exc.read()[:300]!r}", finish=True)
        except Exception as exc:
            return Thought(text=f"LLM 调用失败: {exc}", finish=True)

        choice = body["choices"][0]["message"]
        calls = choice.get("tool_calls") or []
        if calls:
            return Thought(
                text=choice.get("content") or "",
                tool_calls=[
                    ToolCall(
                        c["function"]["name"],
                        json.loads(c["function"]["arguments"] or "{}"),
                        c.get("id", ""),
                    )
                    for c in calls
                ],
            )
        return Thought(text=choice.get("content") or "", finish=True)


def make_brain(**kwargs) -> Brain:
    """有 key 用真的，没 key 用脚本的。"""
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("LAOS_LLM_BASE_URL"):
        return OpenAIChatBrain(
            **{k: v for k, v in kwargs.items() if k in ("model", "base_url", "api_key", "timeout")}
        )
    return ScriptedBrain(
        **{
            k: v
            for k, v in kwargs.items()
            if k in ("branch", "target", "record", "entry", "deny_probe", "deny_args")
        }
    )
