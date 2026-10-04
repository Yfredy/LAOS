"""laos.turnbuf 测试 —— Pipecat 两课进内核语义层（采纳书 B 项）。

课 1（打断即作废）：interrupt() 丢弃未送达尾部。
课 2（聚合器放 output 之后）：commit() 只把已送达水位内的文本写入记忆——
被打断没说出口的半句话永远不进 mem.*。
"""
import threading

import pytest

from laos.memory import MemoryStore
from laos.turnbuf import TurnBuffer


class _MemSpy(MemoryStore):
    """记录 remember 调用的探针。"""

    def __init__(self, tmp_path):
        super().__init__(tmp_path / "mem.jsonl")
        self.calls = []

    def remember(self, kind, text, tags=None, judge=None, **kw):
        self.calls.append((kind, text, tags))
        return super().remember(kind, text, tags=tags, judge=judge, **kw)


def test_append_and_deliver_waterline():
    tb = TurnBuffer()
    tb.append("你好")
    tb.append("，我在")
    assert tb.delivered_text == "" and tb.pending_text == "你好，我在"
    tb.deliver_more("你好")
    assert tb.delivered_text == "你好" and tb.pending_text == "，我在"
    tb.deliver_more("，我在")
    assert tb.pending_text == ""


def test_interrupt_drops_undelivered():
    tb = TurnBuffer()
    tb.append("这句话说完了")
    tb.append("，这句被打断")
    tb.deliver_more("这句话说完了")
    tb.interrupt()
    assert tb.delivered_text == "这句话说完了"
    assert tb.pending_text == ""            # 未送达尾部作废（Pipecat 课 1）
    assert tb.interrupted


def test_commit_only_delivered_content(tmp_path):
    mem = _MemSpy(tmp_path)
    tb = TurnBuffer()
    tb.append("实际播出的内容")
    tb.append(" 没播出的后半句")
    tb.deliver_more("实际播出的内容")
    tb.interrupt()
    tb.commit(mem, kind="dialog")
    assert len(mem.calls) == 1
    kind, text, _ = mem.calls[0]
    assert kind == "dialog" and text == "实际播出的内容"   # 聚合器在 output 之后


def test_commit_without_interrupt_commits_all_delivered(tmp_path):
    mem = _MemSpy(tmp_path)
    tb = TurnBuffer()
    tb.append("全部送达")
    tb.deliver_more("全部送达")
    tb.commit(mem, kind="dialog", tags=["t"])
    kind, text, tags = mem.calls[0]
    assert text == "全部送达" and tags == ["t"]


def test_commit_nothing_when_nothing_delivered(tmp_path):
    mem = _MemSpy(tmp_path)
    tb = TurnBuffer()
    tb.append("全都没送达")
    tb.interrupt()
    tb.commit(mem, kind="dialog")
    assert mem.calls == []                  # 零落盘（记忆闸门同构）


def test_judge_passthrough(tmp_path):
    """commit 透传 judge：deny 则记忆层零落盘。"""
    from laos.judge import JudgeResult, RuleBackend

    class _DenyAll(RuleBackend):
        def noul(self, context, question):
            return JudgeResult("deny", 1.0, {})

    mem = _MemSpy(tmp_path)
    tb = TurnBuffer()
    tb.append("敏感内容")
    tb.deliver_more("敏感内容")
    tb.commit(mem, kind="dialog", judge=_DenyAll())
    # 尝试发生（spy 记录）但 deny → 零落盘（持久层为空）
    assert len(mem.calls) == 1
    assert mem.recall("敏感") == []


def test_thread_safety_basic():
    tb = TurnBuffer()
    errs = []

    def producer():
        try:
            for i in range(200):
                tb.append(f"块{i}")
                tb.deliver_more(f"块{i}")
        except Exception as e:
            errs.append(e)

    t = threading.Thread(target=producer)
    t.start(); t.join()
    assert not errs
    assert tb.delivered_text.endswith("块199")


def test_reset_for_next_turn():
    tb = TurnBuffer()
    tb.append("第一轮")
    tb.deliver_more("第一轮")
    tb.reset()
    assert tb.delivered_text == "" and tb.pending_text == ""
    assert not tb.interrupted
