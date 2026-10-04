"""Pipecat 帧管道架构复现（来源⑤：微信文章"连 LiveKit 都只是它的传输层"）。

复现 Pipecat（github.com/pipecat-ai/pipecat，BSD-2）的架构内核，纯 asyncio：
不装框架（conda 红线），只复现文章讲透的设计决策——

1. 帧两分法：
   - SystemFrame（StartFrame/EndFrame/InterruptionFrame/MetricsFrame…）：
     立即处理、**打断不清空**（打断信号本身、指标、控制必须穿管到底）
   - DataFrame（音频/转写/LLM 文本/TTS 音频…）：进队列、**打断即作废**
     （用户一开口，还在排队的半句话 TTS 音频直接丢弃）
2. InterruptionFrame：打断风暴的核心——沿途清空每个处理器的数据队列。
3. 全程流式：处理器逐帧 push，不等上游"完成"（LLM 第一句 → TTS 即起）。
4. 聚合器放 output 之后：assistant 上下文只记**实际播出**的内容，
   被打断的尾巴不进记忆（与 laos mem.* 闸门语义天然契合）。
5. 自定义处理器（HandoffGuard 模式）：吞帧 + 直接注入播报帧。

与 laos 的映射：Frame≈事件/审计事件；Pipeline≈drv_mic→drv_ear→brain 链；
InterruptionFrame≈四段漏斗第②层"用户接管即作废"；聚合器位置≈mem.remember
只该记实际发生的交互。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


# ---------------------------------------------------------------- 帧类型
class Frame:
    """基帧。"""


class SystemFrame(Frame):
    """系统帧：立即处理，打断不清空。"""


class StartFrame(SystemFrame):
    pass


class EndFrame(SystemFrame):
    pass


class InterruptionFrame(SystemFrame):
    """用户打断：沿途作废所有排队的数据帧。"""


class MetricsFrame(SystemFrame):
    def __init__(self, data: dict):
        self.data = data


class DataFrame(Frame):
    """数据帧：排队流转，打断即作废。"""


@dataclass
class InputAudioRawFrame(DataFrame):
    audio: bytes = b""


@dataclass
class TranscriptionFrame(DataFrame):
    text: str = ""
    user: str = "user"


@dataclass
class LLMTextFrame(DataFrame):
    text: str = ""


@dataclass
class TTSAudioFrame(DataFrame):
    text: str = ""      # 复现口径：以文本代替音频字节


@dataclass
class TTSSpeakFrame(DataFrame):
    text: str = ""      # 直接注入的播报（垫话/兜底）


DOWNSTREAM = "downstream"
UPSTREAM = "upstream"


# ---------------------------------------------------------------- 处理器
class FrameProcessor:
    """管道节点：收帧 → 处理 → 转发（默认透传）。

    子类在 process_frame 里用 self.push(...) 注入新帧（Pipecat 同款风格：
    push 到链上下家，而不是直接调用对方）。
    """

    def __init__(self):
        self._next: FrameProcessor | None = None
        self._prev: FrameProcessor | None = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def process_frame(self, frame: Frame, direction: str):
        return frame

    async def push(self, frame: Frame, direction: str = DOWNSTREAM):
        """处理器内部注入帧（模拟 Pipecat source.push / queue_frame）。"""
        if direction == DOWNSTREAM and self._next is not None:
            await self._next._enqueue(frame, direction)
        elif direction == UPSTREAM and self._prev is not None:
            await self._prev._enqueue(frame, direction)

    async def _enqueue(self, frame: Frame, direction: str):
        if isinstance(frame, InterruptionFrame):
            # 打断帧：作废本节点排队的数据帧，保留系统帧，然后入队
            drained = []
            while not self._queue.empty():
                try:
                    drained.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            keep_sys = [f for f in drained if isinstance(f, SystemFrame)]
            for f in [frame] + keep_sys:       # 数据帧在此作废
                self._queue.put_nowait(f)
            return
        # 其余帧（含 Start/End/Metrics 系统帧）按 FIFO——顺序语义不可颠倒
        self._queue.put_nowait(frame)

    async def _run(self):
        while True:
            frame = await self._queue.get()
            await self._handle(frame, DOWNSTREAM)
            if isinstance(frame, EndFrame):
                return                # 终帧处理后本节点退出（已向下游转发）

    async def _handle(self, frame: Frame, direction: str):
        if isinstance(frame, InterruptionFrame):
            # 打断语义：作废排队数据帧，保留系统帧（End/Metrics 不能丢）
            drained = []
            while not self._queue.empty():
                try:
                    drained.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            for f in drained:
                if isinstance(f, SystemFrame):
                    self._queue.put_nowait(f)
        out = await self.process_frame(frame, direction)
        if out is not None:
            await self.push(out, direction)

    def link(self, prev: "FrameProcessor | None", next_: "FrameProcessor | None"):
        self._prev, self._next = prev, next_


class SourceProcessor(FrameProcessor):
    """管道源头：外部用 await src.push(frame) 注入。"""

    async def push(self, frame: Frame, direction: str = DOWNSTREAM):
        if direction == DOWNSTREAM and self._next is not None:
            await self._next._enqueue(frame, direction)


class SinkCollector(FrameProcessor):
    """管道末端：只收不转发。"""

    def __init__(self):
        super().__init__()
        self.frames: list[Frame] = []

    async def process_frame(self, frame, direction):
        self.frames.append(frame)
        return None


# ---------------------------------------------------------------- 组合件
class AggregatorProcessor(FrameProcessor):
    """聚合器（放 output 之后）：只拼接实际穿过本节点的数据帧。"""

    def __init__(self):
        super().__init__()
        self.transcript = ""

    async def process_frame(self, frame, direction):
        if isinstance(frame, (LLMTextFrame, TTSAudioFrame)):
            self.transcript += frame.text
        return frame


class HandoffGuard(FrameProcessor):
    """兜底守卫：命中关键词的用户帧吞掉，注入播报帧（文章 Handoff 模式）。"""

    def __init__(self, keywords: list[str], speak_text: str = "这个我处理不了，已转人工。"):
        super().__init__()
        self.keywords = keywords
        self.speak_text = speak_text

    async def process_frame(self, frame, direction):
        if isinstance(frame, TranscriptionFrame):
            if any(k in frame.text for k in self.keywords):
                await self.push(TTSSpeakFrame(self.speak_text), direction)
                return None          # 吞帧：LLM 不该看到
        return frame


class Pipeline:
    """把处理器连成链，各起一个消费任务；src.push(...) 即入链。"""

    def __init__(self, processors: list[FrameProcessor]):
        self.processors = processors
        for i, p in enumerate(processors):
            prev = processors[i - 1] if i > 0 else None
            nxt = processors[i + 1] if i < len(processors) - 1 else None
            p.link(prev, nxt)

    async def run(self):
        # 首个处理器是源（无输入队列消费），其余各起一个消费任务；
        # EndFrame 沿链转发，每个节点处理完自然退出。
        tasks = [asyncio.create_task(p._run()) for p in self.processors[1:]]
        await asyncio.gather(*tasks)
