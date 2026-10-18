# Brain 可靠性与重复动作防护实施计划（第一波）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉 laos 两个现存洞——LLM tool_call 参数非法 JSON 直接崩 `brain.think`、agent 主循环对重复无效 syscall 无检测——并引入 esp32-iphone-agent 同款的三档温度重试阶梯（0 → 0.4 → 0.8）。

**Architecture:** `laos/brain.py` 的 `Thought` 增加 `retryable` 标志，`OpenAIChatBrain.think` 接受 `temperature` 并把「任一 tool_call 参数解析失败」的轮次整体转为可重试 Thought（不抛异常）；`laos/agent.py` 主循环维护连续重试计数驱动温度阶梯（超限放弃），并新增重复 syscall 检测器——同 `tool` + 同规范化参数第 3 次原样发起时，经既有 `ctx.notice` 通知面注入「强制换策略」通告。不动 kernel、不动驱动、零新依赖。

**Tech Stack:** Python 3.10+ 纯 stdlib（`dataclasses` / `json` / `asyncio` / `unittest` / `unittest.mock`）；测试全程 mock `laos.brain.urllib.request.urlopen`，不打真网络。

**Spec:** `docs/research/2026-10-15-esp32-iphone-agent-borrowing.md` §「laos 现存两个代码洞」+ §借鉴清单 #2

## Global Constraints

- **核心零依赖**：`laos/` 纯 stdlib，禁止 import 任何第三方包（既有红线，AGENTS.md）。
- **fail-loud**：解析失败必须显式转为可重试状态，禁止把异常吞成 `finish=True`，禁止静默兜底。
- **测试口径**：每个 Task 完成时 `python -m unittest discover -s tests` 必须全绿；`urlopen` 全程 mock，测试不触网。
- **既有行为保持**：`ScriptedBrain` 确定性行为不变（忽略 temperature）；正常路径请求体仅新增 `temperature` 字段（默认 0——这是有意的行为明确化：首轮从「服务器默认 1.0」变为显式确定性，commit message 必须写明）；`AgentResult` 字段语义不变。
- **温度阶梯三档与 esp32 同款**：首轮 `0`，第 1 次重试 `0.4`，第 2 次重试 `0.8`，超过 2 次重试放弃；参数为 `float`。
- **乱序阅读禁令**（本仓库计划纪律）：跨 Task 引用一律原文重复代码块，禁止「类似 Task N」；邻 Task 签名只经 Interfaces 的 Produces 块传递。
- **checkbox 纪律**：计划正文 checkbox 执行时不勾选，完成度看 commit 与落点。

---

### Task 1: `Thought.retryable` 标志 + `brain.think` 接受 `temperature`

**Files:**
- Modify: `laos/brain.py`（`Thought` dataclass 21-28 行；`Brain.think` 抽象方法 39-40 行；`ScriptedBrain.think` 93 行；`OpenAIChatBrain.think` 183-217 行）
- Test: `tests/test_brain.py`（新建）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `Thought` 新增字段 `retryable: bool = False`（默认 False，既有构造点全部兼容）。语义：`retryable=True` 表示本轮输出不可用（tool_call 参数解析失败），调用方应升温重试，不得当作结束。
  - `Brain.think(self, messages: list[dict], tools: list[dict], temperature: float = 0) -> Thought`。`ScriptedBrain.think` 接受并忽略 `temperature`（确定性后端）；`OpenAIChatBrain.think` 将其透传进请求体 `payload["temperature"]`（`float`）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_brain.py`：

```python
# tests/test_brain.py
"""Brain 可靠性与温度阶梯（第一波：brain-reliability-repeat-guard）。

    python -m unittest tests.test_brain -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.brain import OpenAIChatBrain, ScriptedBrain, Thought  # noqa: E402


def _ok_response(content: str = "hi"):
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    resp = mock.Mock()
    resp.read.return_value = body
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


class TestThoughtRetryable(unittest.TestCase):
    def test_retryable_defaults_false(self):
        t = Thought(text="x")
        self.assertFalse(t.retryable)
        self.assertEqual(t.tool_calls, [])
        self.assertFalse(t.finish)


class TestThinkTemperature(unittest.TestCase):
    def test_scripted_brain_accepts_temperature(self):
        brain = ScriptedBrain(branch="main")
        thought = brain.think([{"role": "user", "content": "task"}],
                              [{"name": "sys.info"}], temperature=0.7)
        self.assertFalse(thought.retryable)
        self.assertTrue(thought.tool_calls or thought.text)

    def test_openai_payload_includes_temperature(self):
        brain = OpenAIChatBrain(api_key="sk-test",
                                base_url="https://x.test/v1")
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            brain.think([{"role": "user", "content": "hi"}], [], temperature=0.4)
        payload = json.loads(up.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0.4)

    def test_openai_default_temperature_zero(self):
        brain = OpenAIChatBrain(api_key="sk-test",
                                base_url="https://x.test/v1")
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            brain.think([{"role": "user", "content": "hi"}], [])
        payload = json.loads(up.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_brain -v`
Expected: FAIL——`TypeError: think() got an unexpected keyword argument 'temperature'`（3 个温度测试红）；`TestThoughtRetryable` 已绿（字段未加时 `Thought(text="x")` 不报错但无 retryable 属性 → `AttributeError`，同样红）。

- [ ] **Step 3: 最小实现**

`laos/brain.py` 的 `Thought`（21-28 行）加字段：

```python
@dataclass
class Thought:
    """一次 think() 的产物：要么说话，要么发起若干系统调用。"""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish: bool = False
    #: 本轮输出不可用（tool_call 参数解析失败等）：调用方应升温重试，
    #: 不得当作结束。默认 False——既有全部构造点行为不变。
    retryable: bool = False
```

`Brain.think` 抽象方法（39-40 行）改签名：

```python
    def think(self, messages: list[dict], tools: list[dict],
              temperature: float = 0) -> Thought:
        raise NotImplementedError
```

`ScriptedBrain.think`（93 行）改签名（忽略 temperature，保持确定性）：

```python
    def think(self, messages: list[dict], tools: list[dict],
              temperature: float = 0) -> Thought:
```

`OpenAIChatBrain.think`（183-187 行）改签名并透传 temperature：

```python
    def think(self, messages: list[dict], tools: list[dict],
              temperature: float = 0) -> Thought:
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
                                   "temperature": float(temperature)}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_brain -v`
Expected: PASS（4 绿）

- [ ] **Step 5: Commit**

```bash
git add laos/brain.py tests/test_brain.py
git commit -m "feat(brain): Thought 增加 retryable 标志，think 接受 temperature（首波 brain 可靠性，spec: research/2026-10-15-esp32-iphone-agent-borrowing）"
```

---

### Task 2: `OpenAIChatBrain` tool_call 解析失败整体转可重试 Thought

**Files:**
- Modify: `laos/brain.py`（`OpenAIChatBrain.think` 内 tool_calls 解析段，203-217 行）
- Test: `tests/test_brain.py`（追加两个测试类方法）

**Interfaces:**
- Consumes: Task 1 的 `Thought.retryable` 与 `think(messages, tools, temperature)` 签名。
- Produces: `OpenAIChatBrain.think` 的失败语义——**任一** tool_call 的 `function.arguments` 不是合法 JSON 时，返回 `Thought(text="tool_call 参数解析失败（call_id=<id>）：arguments 不是合法 JSON，请严格按 inputSchema 重新生成", tool_calls=[], finish=False, retryable=True)`（整轮作废，不执行其中合法的调用）；全部合法时照常返回 `tool_calls`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_brain.py` 末尾（`if __name__` 之前）追加：

```python
def _toolcall_response(arguments: str, call_id: str = "c1"):
    body = json.dumps({"choices": [{"message": {"content": "",
        "tool_calls": [{"id": call_id,
                        "function": {"name": "sys.info",
                                     "arguments": arguments}}]}}]}).encode()
    resp = mock.Mock()
    resp.read.return_value = body
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


class TestParseFailure(unittest.TestCase):
    def _brain(self):
        return OpenAIChatBrain(api_key="sk-test", base_url="https://x.test/v1")

    def test_bad_arguments_becomes_retryable(self):
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_toolcall_response('{"x": ')):
            thought = self._brain().think([{"role": "user", "content": "t"}],
                                          [{"name": "sys.info"}])
        self.assertTrue(thought.retryable)
        self.assertEqual(thought.tool_calls, [])
        self.assertFalse(thought.finish)
        self.assertIn("解析失败", thought.text)
        self.assertIn("c1", thought.text)

    def test_valid_arguments_still_parses(self):
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_toolcall_response('{"path": "/p"}')):
            thought = self._brain().think([{"role": "user", "content": "t"}],
                                          [{"name": "fs.read"}])
        self.assertFalse(thought.retryable)
        self.assertEqual(len(thought.tool_calls), 1)
        self.assertEqual(thought.tool_calls[0].arguments, {"path": "/p"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_brain.TestParseFailure -v`
Expected: FAIL——`json.loads` 抛 `JSONDecodeError` 从 `think()` 逃逸（当前 211 行行为），测试以 Error 而非断言失败收场。

- [ ] **Step 3: 最小实现**

`laos/brain.py` `OpenAIChatBrain.think` 的 tool_calls 解析段（203-217 行）整体替换为：

```python
        choice = body["choices"][0]["message"]
        calls = choice.get("tool_calls") or []
        parsed: list[ToolCall] = []
        for c in calls:
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except (json.JSONDecodeError, TypeError, AttributeError) as exc:
                # 整轮作废：一个坏 call 不放过、也不单独执行好 call——
                # 半套工具调用比没有调用更危险（esp32 同款纪律）
                return Thought(
                    text=(f"tool_call 参数解析失败（call_id={c.get('id', '')}）："
                          f"arguments 不是合法 JSON（{exc}），"
                          f"请严格按 inputSchema 重新生成"),
                    tool_calls=[], finish=False, retryable=True)
            parsed.append(ToolCall(
                c["function"]["name"], args, c.get("id", "")))
        if parsed:
            return Thought(text=choice.get("content") or "", tool_calls=parsed)
        return Thought(text=choice.get("content") or "", finish=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_brain -v`
Expected: PASS（6 绿）

- [ ] **Step 5: Commit**

```bash
git add laos/brain.py tests/test_brain.py
git commit -m "fix(brain): tool_call 参数非法 JSON 不再崩 think()——整轮转 retryable Thought（修现存洞：一次模型输出抖动报废整个任务）"
```

---

### Task 3: `Agent.run` 温度阶梯与重试上限

**Files:**
- Modify: `laos/agent.py`（import 区 11-16 行加 `json`；模块常量 17-19 行后追加两个常量；`run` 方法 112-179 行）
- Test: `tests/test_agent_reliability.py`（新建）

**Interfaces:**
- Consumes: Task 1/2 的 `Thought.retryable` 与 `think(messages, tools, temperature)`。
- Produces:
  - 模块常量 `_RETRY_TEMPERATURE_LADDER: tuple[float, float] = (0.4, 0.8)` 与 `_MAX_RETRYABLE_RETRIES: int = 2`（`laos/agent.py` 模块级）。
  - `Agent.run` 行为：连续 `retryable` 轮依次以 `0 → 0.4 → 0.8` 调 `brain.think`；第 3 次仍 `retryable` 时以 `result.ok=False`、`result.answer="模型连续 3 轮输出不可用（tool_call 参数解析失败），任务中止。"` 终止，不再调用 `think`；任何非 retryable 轮重置计数。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_agent_reliability.py`（kernel 装配沿用 `tests/test_laos.py` 的 `KernelTestCase` 模式，自包含以便乱序阅读）：

```python
# tests/test_agent_reliability.py
"""Agent 主循环可靠性：温度阶梯 / 重试上限 / 重复 syscall 检测（第一波）。

    python -m unittest tests.test_agent_reliability -v
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agent import Agent  # noqa: E402
from laos.brain import Brain, Thought, ToolCall  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

DRIVERS = REPO / "drivers"


class _RecordingBrain(Brain):
    """记录每次 think 收到的 temperature，按脚本返回 Thought。"""

    name = "recording"

    def __init__(self, script):
        self.script = script
        self.temperatures: list[float] = []
        self.calls = 0

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        self.temperatures.append(temperature)
        idx = min(self.calls, len(self.script) - 1)
        self.calls += 1
        item = self.script[idx]
        if callable(item):
            return item()
        return item


class ReliabilityTestCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        for name in ("fs", "proc", "sys"):
            self.kernel.load_driver(
                name, [sys.executable, str(DRIVERS / f"drv_{name}.py")], env=env)
        self.main = self.kernel.branches.create_root("main")
        ws = self.main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def spawn(self, brain, caps=("sys.*",)):
        ctx = ContextManager(system_prompt="test", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        pcb = self.kernel.spawn(name="t", caps=list(caps), ctx=ctx, branch="main")
        return Agent(self.kernel, pcb, brain)


class TestRetryLadder(ReliabilityTestCase):
    def test_ladder_then_success(self):
        bad = Thought(text="参数坏了", retryable=True)
        good = Thought(text="", tool_calls=[ToolCall("sys.info", {}, "c1")])
        done = Thought(text="完成", finish=True)
        brain = _RecordingBrain([bad, bad, good, done])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查一下环境"))
        self.assertEqual(brain.temperatures, [0, 0.4, 0.8])
        self.assertTrue(res.ok)
        self.assertGreaterEqual(res.syscalls, 1)

    def test_gives_up_after_two_retries(self):
        brain = _RecordingBrain([Thought(text="还是坏", retryable=True)])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查一下环境"))
        self.assertEqual(brain.calls, 3)
        self.assertEqual(brain.temperatures, [0, 0.4, 0.8])
        self.assertFalse(res.ok)
        self.assertIn("连续 3 轮", res.answer)
        self.assertEqual(res.syscalls, 0)

    def test_success_resets_retry_count(self):
        bad = Thought(text="坏", retryable=True)
        good = Thought(text="", tool_calls=[ToolCall("sys.info", {}, "c1")])
        done = Thought(text="完成", finish=True)
        brain = _RecordingBrain([bad, good, bad, good, done])
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("查两轮环境"))
        self.assertTrue(res.ok)
        # 两段各一次重试：0 → 0.4 →（成功重置）→ 0 → 0.4
        self.assertEqual(brain.temperatures, [0, 0.4, 0, 0.4])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_agent_reliability -v`
Expected: FAIL——`TypeError: think() got an unexpected keyword argument 'temperature'`（Task 1 已修签名时此处应已能调；若按序执行到本任务则失败点为：`_RecordingBrain` 脚本第一轮返回 retryable 时 `Agent.run` 将其当纯思考步 `continue`，重试计数不递增 → `test_gives_up_after_two_retries` 断言 `brain.calls == 3` 实测为 12，`test_ladder_then_success` 的 temperatures 断言失败）。

- [ ] **Step 3: 最小实现**

`laos/agent.py` import 区（11-16 行）加 `json`：

```python
import asyncio
import json
from dataclasses import dataclass, field
```

模块常量区（`_SCHED_WAIT_ROUNDS = 200` 之后）追加：

```python
# 温度重试阶梯（esp32-iphone-agent 同款三档）：首轮 0（确定性），
# 第 1/2 次重试 0.4/0.8；超过 _MAX_RETRYABLE_RETRIES 次仍不可用即放弃。
_RETRY_TEMPERATURE_LADDER: tuple[float, float] = (0.4, 0.8)
_MAX_RETRYABLE_RETRIES: int = 2
```

`Agent.run` 主循环（124-145 行区间）改为：

```python
        result = AgentResult(pid=self.pcb.pid, ok=False)
        retryable_seen = 0
        try:
            for step in range(1, self.max_steps + 1):
                # Stale Context：内核通告注入（HKU: 当上下文与现实不符时强制重读）
                if hasattr(self.pcb.ctx, "drain_notices"):
                    for stale_path in self.pcb.ctx.drain_notices():
                        self.pcb.ctx.notice(
                            f"STALE: {stale_path} 已被外部修改，之前的读取结果不可信，请重新 fs.read"
                        )
                tools = self.visible_tools
                if retryable_seen:
                    temperature = _RETRY_TEMPERATURE_LADDER[
                        min(retryable_seen, len(_RETRY_TEMPERATURE_LADDER)) - 1]
                else:
                    temperature = 0
                thought: Thought = await asyncio.to_thread(
                    self.brain.think, ctx.messages, tools, temperature=temperature)
                result.steps = step

                if thought.text:
                    ctx.append("assistant", thought.text)
                    result.trace.append({"step": step, "say": thought.text})

                if thought.retryable:
                    # 本轮输出不可用（tool_call 参数解析失败）：升温重试，
                    # 超限放弃——绝不把异常吞成 finish，也不空转烧预算
                    retryable_seen += 1
                    if retryable_seen > _MAX_RETRYABLE_RETRIES:
                        result.answer = (
                            f"模型连续 {retryable_seen} 轮输出不可用"
                            f"（tool_call 参数解析失败），任务中止。")
                        result.ok = False
                        break
                    continue
                retryable_seen = 0

                if not thought.tool_calls:
                    result.answer = thought.text
                    # 被内核拒过的 Agent 不算成功完成
                    result.ok = thought.finish and self.pcb.stats["denied"] == 0
                    if thought.finish:
                        break
                    continue  # 纯思考步，未结束则继续下一轮
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_agent_reliability -v`
Expected: PASS（3 绿）

- [ ] **Step 5: 全量回归 + Commit**

Run: `python -m unittest discover -s tests`
Expected: 全绿（既有 1146 + 新增，数量以实跑 "Ran N tests" 为准）

```bash
git add laos/agent.py tests/test_agent_reliability.py
git commit -m "feat(agent): think 增加温度重试阶梯 0→0.4→0.8 与重试上限（esp32 同款容错，修 brain 解析失败无止损面）"
```

---

### Task 4: 重复 syscall 检测器 + `ctx.notice` 强制换策略

**Files:**
- Modify: `laos/agent.py`（`Agent.run` 的 tool_calls 执行段，147-152 行区间）
- Test: `tests/test_agent_reliability.py`（追加 `TestRepeatGuard` 类与两个专用 Brain）

**Interfaces:**
- Consumes: Task 3 的 `Agent.run` 主循环结构；`ContextManager.notice(content: str) -> Message`（`laos/context.py:258`，以 user 角色注入 `[kernel-notice] ` 前缀）。
- Produces: `Agent.run` 内行为——以 `f"{call.name}|{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"` 为键计数；同一键第 3 次出现时（且仅第 3 次）经 `self.pcb.ctx.notice(...)` 注入一次通告，文案固定包含 `重复动作警告`、该 syscall 名与参数、`必须更换策略`、`禁止原样重试`。不同参数或不同工具不共享计数。

- [ ] **Step 1: 写失败测试**

在 `tests/test_agent_reliability.py` 末尾（`if __name__` 之前）追加：

```python
class _FixedCallBrain(Brain):
    """永远发起同一个 syscall，绝不 finish（用于重复检测）。"""

    name = "fixed"

    def __init__(self, name="sys.info", arguments=None):
        self._name = name
        self._args = arguments or {}

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        return Thought(text="再试一次",
                       tool_calls=[ToolCall(self._name, dict(self._args), "c1")])


class _AlternatingArgsBrain(Brain):
    """同一工具但参数交替变化（不构成"原样重复"）。"""

    name = "alternating"

    def __init__(self):
        self._n = 0

    def think(self, messages, tools, temperature: float = 0) -> Thought:
        self._n += 1
        return Thought(text="",
                       tool_calls=[ToolCall("sys.info",
                                            {"n": self._n}, f"c{self._n}")])


class TestRepeatGuard(ReliabilityTestCase):
    def _notices(self, ctx):
        return [m for m in ctx.messages
                if m.get("role") == "user"
                and str(m.get("content", "")).startswith("[kernel-notice]")]

    def test_third_identical_call_triggers_notice(self):
        brain = _FixedCallBrain()
        agent = self.spawn(brain)
        asyncio.run(agent.run("反复查询环境"))
        notices = self._notices(agent.pcb.ctx)
        self.assertEqual(len(notices), 1)
        self.assertIn("重复动作警告", notices[0]["content"])
        self.assertIn("sys.info", notices[0]["content"])
        self.assertIn("必须更换策略", notices[0]["content"])
        self.assertIn("禁止原样重试", notices[0]["content"])

    def test_varying_args_never_triggers(self):
        brain = _AlternatingArgsBrain()
        agent = self.spawn(brain)
        asyncio.run(agent.run("每轮不同参数"))
        self.assertEqual(self._notices(agent.pcb.ctx), [])

    def test_notice_fires_once_not_every_step(self):
        brain = _FixedCallBrain()
        agent = self.spawn(brain)
        res = asyncio.run(agent.run("反复查询环境"))
        # max_steps=12 默认：同一 call 发 12 次，通告只在第 3 次出现一次
        self.assertEqual(res.steps, 12)
        self.assertEqual(len(self._notices(agent.pcb.ctx)), 1)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m unittest tests.test_agent_reliability.TestRepeatGuard -v`
Expected: FAIL——三个测试的 notice 断言实测为空列表（当前 `agent.py` 无重复检测）。

- [ ] **Step 3: 最小实现**

`laos/agent.py` `Agent.run` 的 tool_calls 执行段（147-152 行区间）替换为：

```python
                repeat_counts: dict[str, int] = {}
                for call in thought.tool_calls:
                    key = (f"{call.name}|"
                           f"{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}")
                    repeat_counts[key] = repeat_counts.get(key, 0) + 1
                    if repeat_counts[key] == 3:
                        # 同 tool + 同参数第 3 次原样发起：强制换策略
                        # （esp32 _repeating 同款；每个 key 只通告一次）
                        self.pcb.ctx.notice(
                            f"重复动作警告：{call.name}("
                            f"{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
                            f") 已第 3 次原样发起。必须更换策略——换工具、换参数"
                            f"或换路径；禁止原样重试。")
                    out = await self._do_syscall(call)
                    ctx.append("tool", out, name=call.name)
                    result.trace.append(
                        {"step": step, "syscall": call.name, "args": call.arguments, "ret": out[:300]}
                    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m unittest tests.test_agent_reliability -v`
Expected: PASS（6 绿）

- [ ] **Step 5: 全量回归 + Commit**

Run: `python -m unittest discover -s tests`
Expected: 全绿（含既有 `tests/test_laos.py::TestAgent`——ScriptedBrain 流程中 `fs.read` 同参仅 2 次，不得误触发通告）

```bash
git add laos/agent.py tests/test_agent_reliability.py
git commit -m "feat(agent): 重复 syscall 检测器——同 tool+同参数第 3 次触发强制换策略 notice（esp32 _repeating 同款，治 max_steps 硬截断前的死循环烧预算）"
```

---

## Self-Review 记录（写完三查，2026-10-15）

1. **spec 覆盖**：spec（research/2026-10-15 §两个现存洞 + 借鉴清单 #2）两项需求均有落点——洞 1（brain.py:211 解析崩）→ Task 1/2；洞 2（死循环无检测）→ Task 3（温度阶梯止损）+ Task 4（重复检测 notice）。借鉴清单 #2 中的「重复无效动作检测 + 解析失败容错阶梯」完整覆盖；#2 中依赖 verify 证据的分支（changed=False 才计数）属第二波范围，本计划不涉及，无缺口。
2. **占位符扫描**：无 TBD / 无「加适当错误处理」式空转步骤；所有代码步骤均带可运行代码块；跨 Task 引用均为原文重复（`_ok_response` 助手、kernel 装配、notice 断言助手在两处照抄，未用「类似 Task N」）。
3. **类型一致性**：`Thought.retryable: bool`（Task 1 定义）→ Task 2/3 消费同名同型；`think(messages, tools, temperature: float = 0)` 签名在 Task 1 定义后，Task 2/3 与全部测试 Brain（`_RecordingBrain` / `_FixedCallBrain` / `_AlternatingArgsBrain`）逐字符一致；`_RETRY_TEMPERATURE_LADDER`/`_MAX_RETRYABLE_RETRIES` 仅 Task 3 定义、无跨 Task 消费；重复键格式 `name|json` 在 Task 4 实现与通告文案中一致。
