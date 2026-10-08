"""Pipecat 帧管道架构复现测试（来源⑤：连 LiveKit 都只是它的传输层）。

复现的是 Pipecat 的架构内核（不装框架本身——conda 红线不装包）：
- 帧分类：SystemFrame 立即处理、打断不清空；DataFrame 排队、打断时清空
- InterruptionFrame 穿管作废：用户一开口，排队中的 TTS/LLM 帧全部作废
- 全程流式：LLM 第一句出来 TTS 就开始，不等全文
- assistant 聚合器放 output 之后：只有实际播出的内容进上下文
- HandoffGuard：自定义处理器吞帧+直接注入播报（"这个我处理不了，转人工"）
"""
import asyncio

import pytest

from repro.framepipe import (
    FrameProcessor,
    Pipeline,
    SourceProcessor,
    SinkCollector,
    InterruptionFrame,
    MetricsFrame,
    TranscriptionFrame,
    LLMTextFrame,
    TTSAudioFrame,
    TTSSpeakFrame,
    StartFrame,
    EndFrame,
    AggregatorProcessor,
    HandoffGuard,
)


def _run(coro):
    return asyncio.run(coro)


def test_pipeline_passthrough_order():
    """STT→LLM 文本帧按序到达 Sink。"""

    class LLMStub(FrameProcessor):
        pass

    async def main():
        src = SourceProcessor()
        sink = SinkCollector()
        pipe = Pipeline([src, sink])
        run_task = asyncio.create_task(pipe.run())
        for i in range(3):
            await src.push(LLMTextFrame(f"chunk{i}"))
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)
        texts = [f.text for f in sink.frames if isinstance(f, LLMTextFrame)]
        assert texts == ["chunk0", "chunk1", "chunk2"]

    _run(main())


def test_interruption_clears_queued_data_but_system_passes():
    """打断：排队的 DataFrame 作废，SystemFrame（Metrics）照常穿管。"""

    class SlowProc(FrameProcessor):
        """模拟慢 TTS：每个数据帧 sleep，制造排队积压。"""

        async def process_frame(self, frame, direction):
            if isinstance(frame, LLMTextFrame):
                await asyncio.sleep(0.05)
            return frame

    async def main():
        src = SourceProcessor()
        slow = SlowProc()
        sink = SinkCollector()
        pipe = Pipeline([src, slow, sink])
        run_task = asyncio.create_task(pipe.run())
        for i in range(8):
            await src.push(LLMTextFrame(f"t{i}"))
        await asyncio.sleep(0.12)          # 部分帧还在排队
        await src.push(InterruptionFrame())  # 用户打断
        await src.push(MetricsFrame({"latency_ms": 42}))  # 系统帧
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)
        got_texts = [f.text for f in sink.frames if isinstance(f, LLMTextFrame)]
        assert len(got_texts) < 8          # 打断后排队帧被作废
        assert any(isinstance(f, MetricsFrame) for f in sink.frames)  # 系统帧穿管
        assert any(isinstance(f, InterruptionFrame) for f in sink.frames)

    _run(main())


def test_streaming_first_output_before_llm_done():
    """流式：LLM 还没生成完，Sink 已收到前几段输出。"""

    class StreamingLLM(FrameProcessor):
        def __init__(self):
            super().__init__()
            self.generated = 0

        async def process_frame(self, frame, direction):
            if isinstance(frame, TranscriptionFrame):
                # 逐句流出，句间有延迟（模拟 token 流）
                for i in range(4):
                    await asyncio.sleep(0.03)
                    self.generated += 1
                    await self.push(LLMTextFrame(f"sentence{i}"), direction)
            return frame

    async def main():
        src = SourceProcessor()
        llm = StreamingLLM()
        sink = SinkCollector()
        pipe = Pipeline([src, llm, sink])
        run_task = asyncio.create_task(pipe.run())
        await src.push(TranscriptionFrame("讲个长一点的故事"))
        # LLM 还在生成（4 句需要 ~0.12s）时，第一句应已到达 Sink
        await asyncio.sleep(0.08)
        early = [f for f in sink.frames if isinstance(f, LLMTextFrame)]
        assert any(f.text == "sentence0" for f in early)
        assert llm.generated < 4          # 尚未生成完
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)

    _run(main())


def test_aggregator_after_output_only_played_content():
    """聚合器在 output 之后：被打断没播出的半句不进上下文。"""

    class StreamingLLM(FrameProcessor):
        async def process_frame(self, frame, direction):
            if isinstance(frame, TranscriptionFrame):
                for i in range(10):
                    await asyncio.sleep(0.02)
                    await self.push(LLMTextFrame(f"w{i}"), direction)
            return frame

    async def main():
        src = SourceProcessor()
        llm = StreamingLLM()
        agg = AggregatorProcessor()
        sink = SinkCollector()
        pipe = Pipeline([src, llm, agg, sink])   # 聚合器在"output"位置之后
        run_task = asyncio.create_task(pipe.run())
        await src.push(TranscriptionFrame("hi"))
        await asyncio.sleep(0.09)               # 只播出一部分
        await src.push(InterruptionFrame())     # 打断
        await asyncio.sleep(0.05)               # 等清空传播
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)
        played = [f for f in sink.frames if isinstance(f, LLMTextFrame)]
        # 聚合记录 == 实际穿过 output 的内容，且被打断的尾句不在
        assert agg.transcript == "".join(f.text for f in played)
        assert 0 < len(agg.transcript) < 10 * 2

    _run(main())


def test_handoff_guard_swallows_and_injects():
    """HandoffGuard：命中关键词 → 吞掉用户帧、注入播报帧，LLM 收不到原帧。"""

    class LLMRecorder(FrameProcessor):
        def __init__(self):
            super().__init__()
            self.got = []

        async def process_frame(self, frame, direction):
            if isinstance(frame, TranscriptionFrame):
                self.got.append(frame.text)
            return frame

    async def main():
        src = SourceProcessor()
        guard = HandoffGuard(keywords=["转账"])
        llm = LLMRecorder()
        sink = SinkCollector()
        pipe = Pipeline([src, guard, llm, sink])
        run_task = asyncio.create_task(pipe.run())
        await src.push(TranscriptionFrame("帮我转账一万块"))
        await src.push(TranscriptionFrame("今天天气怎么样"))
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)
        assert llm.got == ["今天天气怎么样"]      # 转账帧被吞
        speaks = [f for f in sink.frames if isinstance(f, TTSSpeakFrame)]
        assert len(speaks) == 1 and "人工" in speaks[0].text  # 注入了兜底播报

    _run(main())


def test_start_end_system_frames_reach_sink():
    async def main():
        src = SourceProcessor()
        sink = SinkCollector()
        pipe = Pipeline([src, sink])
        run_task = asyncio.create_task(pipe.run())
        await src.push(StartFrame())
        await src.push(EndFrame())
        await asyncio.wait_for(run_task, 3)
        assert any(isinstance(f, StartFrame) for f in sink.frames)

    _run(main())
