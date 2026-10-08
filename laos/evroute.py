"""evroute —— 事件规则表：VAD/唤醒/打断的声明式路由（"事件防火墙"）。

转译自 esp-claw components/claw_modules/claw_event_router（Apache-2.0，
espressif/esp-claw；结构级判读自 var/repro 抢救源码，非代码拷贝）。
espclaw 报告（docs/research/2026-10-08-espclaw-vs-muse-agent-core.md §五
裁决 #2，◐P2 承诺）的兑现件，对话管线装配波次（dialogflow.py）的规则面。

esp-claw 构件 → laos 转译对照：

    claw_event_router_rule_t{enabled/consume_on_match/id/description/
    match{event_type/event_key/source_cap/.../text/text_match}/actions}
      → 本模块同构子集：match{type/source/text/text_match(exact|prefix)}
        （未承载的 match 字段：channel/chat_id/content_type——laos 事件
        无信道语义，按需再扩）

    六动作 CALL_CAP/RUN_AGENT/RUN_SCRIPT/SEND_MESSAGE/EMIT_EVENT/DROP
      → 核心版三动作 + 映射说明：
        call_cap —— 能力调用经**回调注入**（装配层接 laos/caps.py 的
                    CapRegistry.call；核心版不 import caps，解耦）
        drop     —— 事件防火墙：命中即吞，调用方据 result.dropped 不走默认路径
        emit     —— 派生事件回注 sink（可 copy 原事件字段）
        run_agent/run_script/send_message → kernel 信箱/驱动子进程域，
        不进零依赖核心（装配层可用 call_cap 回调自行动作化）

    claw_event_router_result_t{matched/matched_rules/action_count/
    failed_actions/first_rule_id}  → RouteResult 同构 + dropped/emitted

语义（与 esp-claw 一致，两处显式化）：

- **无规则命中 = 事件放行**（passthrough，matched=False）——路由器是
  过滤器不是必经闸；
- **consume_on_match**：规则命中后是否继续匹配后续规则（首条消费）；
  与 drop 正交（consume 管规则链，drop 管事件去向）；
- **fail_open（per-action，默认 False=保守）**：动作执行异常时 True=
  记失败但继续该规则剩余动作（放行心），False=中止该规则剩余动作
  （fail-closed）。异常永不冒泡出 handle()——路由层先吞后记。

规则来源：构造入参 / load_file(JSON) + reload() 热载 / CRUD
（add_rule 校验拒绝重复 id 与未支持动作，fail-loud）。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

CallCap = Callable[[str, dict, str], Any]   # (cap_name, input, caller) -> result
Sink = Callable[[dict], None]
AuditHook = Callable[[dict], None]

SUPPORTED_ACTIONS = ("call_cap", "drop", "emit")
SUPPORTED_TEXT_MATCH = ("exact", "prefix")


@dataclass
class RouteResult:
    matched: bool = False
    matched_rules: int = 0
    action_count: int = 0
    failed_actions: int = 0
    dropped: bool = False
    first_rule_id: Optional[str] = None
    cap_outputs: dict = field(default_factory=dict)
    emitted: list = field(default_factory=list)


def _validate(rule: dict) -> dict:
    rid = rule.get("id")
    if not isinstance(rid, str) or not rid:
        raise ValueError(f"rule id 必须是非空字符串: {rule!r}")
    match = rule.get("match") or {}
    tm = match.get("text_match", "exact")
    if tm not in SUPPORTED_TEXT_MATCH:
        raise ValueError(
            f"rule {rid}: text_match 仅支持 {SUPPORTED_TEXT_MATCH}, got {tm!r}")
    for action in rule.get("actions") or []:
        kind = action.get("kind")
        if kind not in SUPPORTED_ACTIONS:
            raise ValueError(
                f"rule {rid}: 动作 {kind!r} 不在核心版支持集 "
                f"{SUPPORTED_ACTIONS}（run_agent/run_script/send_message "
                f"属 kernel/驱动域，经 call_cap 回调动作化）")
    return rule


class EventRouter:
    """声明式事件路由器。线程安全（规则表读写一把锁；handle 期间规则
    快照，热载不撕裂正在进行的匹配）。"""

    def __init__(self, rules: Optional[list[dict]] = None,
                 call_cap: Optional[CallCap] = None,
                 sink: Optional[Sink] = None,
                 on_audit: Optional[AuditHook] = None):
        self._call_cap = call_cap
        self._sink = sink
        self._on_audit = on_audit
        self._lock = threading.Lock()
        self._rules: dict[str, dict] = {}
        self._path: Optional[Path] = None
        for rule in rules or []:
            self.add_rule(rule)

    # -- 规则面 --------------------------------------------------------------
    def add_rule(self, rule: dict) -> None:
        rule = _validate(rule)
        with self._lock:
            if rule["id"] in self._rules:
                raise ValueError(f"rule id 重复: {rule['id']!r}")
            self._rules[rule["id"]] = rule

    def delete_rule(self, rid: str) -> bool:
        with self._lock:
            return self._rules.pop(rid, None) is not None

    def list_rules(self) -> list[dict]:
        with self._lock:
            return [dict(r, actions=[dict(a) for a in r.get("actions", [])])
                    for r in self._rules.values()]

    def load_file(self, path: Path | str) -> None:
        """从 JSON 文件载入规则（数组），并记住路径供 reload() 热载。"""
        path = Path(path)
        rules = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rules, list):
            raise ValueError(f"规则文件必须是 JSON 数组: {path}")
        with self._lock:
            self._rules = {}
            for rule in rules:
                _validate(rule)
                if rule["id"] in self._rules:
                    raise ValueError(f"rule id 重复: {rule['id']!r}")
                self._rules[rule["id"]] = rule
            self._path = path

    def reload(self) -> None:
        """热载：重读 load_file 记住的路径（esp-claw claw_event_router_reload）。"""
        if self._path is None:
            raise RuntimeError("reload 前须先 load_file")
        self.load_file(self._path)

    # -- 匹配与执行 ----------------------------------------------------------
    def handle(self, event: dict) -> RouteResult:
        with self._lock:
            rules = list(self._rules.values())  # 快照：匹配期免撕裂
        result = RouteResult()
        for rule in rules:
            if not rule.get("enabled", True):
                continue
            if not self._match(rule.get("match") or {}, event):
                continue
            if not result.matched:
                result.first_rule_id = rule["id"]
            result.matched = True
            result.matched_rules += 1
            abort = self._run_actions(rule.get("actions") or [], event, result)
            if rule.get("consume_on_match", False) or abort:
                break
        if self._on_audit is not None:
            try:
                self._on_audit({"matched": result.matched,
                                "matched_rules": result.matched_rules,
                                "action_count": result.action_count,
                                "failed_actions": result.failed_actions,
                                "dropped": result.dropped,
                                "first_rule_id": result.first_rule_id})
            except Exception:
                pass  # 审计钩子异常不伤路由主链路
        return result

    def _match(self, match: dict, event: dict) -> bool:
        want_type = match.get("type")
        if want_type and event.get("type") != want_type:
            return False
        want_source = match.get("source")
        if want_source not in (None, "", "*") and event.get("source") != want_source:
            return False
        want_text = match.get("text")
        if want_text is not None:
            text = event.get("text")
            if not isinstance(text, str):
                return False
            if match.get("text_match", "exact") == "prefix":
                if not text.startswith(want_text):
                    return False
            elif text != want_text:
                return False
        return True

    def _run_actions(self, actions: list[dict], event: dict,
                     result: RouteResult) -> bool:
        """执行规则动作序列。返回 True=中止该规则剩余动作（fail-closed）。"""
        for action in actions:
            kind = action.get("kind")
            result.action_count += 1
            try:
                if kind == "drop":
                    result.dropped = True
                elif kind == "call_cap":
                    if self._call_cap is None:
                        raise RuntimeError("call_cap 未注入（装配层接线缺失）")
                    out = self._call_cap(action.get("cap", ""),
                                         dict(action.get("input") or {}),
                                         action.get("caller", "SYSTEM"))
                    result.cap_outputs[action.get("cap", "")] = out
                elif kind == "emit":
                    derived = dict(action.get("event") or {})
                    for f in action.get("copy") or []:
                        if f in event:
                            derived[f] = event[f]
                    result.emitted.append(derived)
                    if self._sink is not None:
                        self._sink(derived)
            except Exception:
                result.failed_actions += 1
                if not action.get("fail_open", False):
                    return True  # fail-closed：中止该规则剩余动作
        return False
