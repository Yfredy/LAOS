# laos 个人伴侣增量：听觉输入 + 记忆库 + 每日日记 实施计划

> 状态：已实施（feat/ear-memory-diary 分支）。本文件为该轮计划的设计记录。

**Goal:** 把 laos 从"演示内核"推进为"会听、会记、会写日记"的系统，三个增量。隐私红线：录音只由显式 syscall 触发；ASR 双通道可切换。

**Architecture:** ① 听觉：`drivers/drv_mic.py`（录音，conda python，sounddevice）+ `drivers/drv_ear.py`（ASR 双通道：funasr GPU 直调 / SenseVoice server HTTP，LAOS_ASR_CHANNEL 切换，统一 JSON 返回）。② 记忆：`laos/memory.py` MemoryStore（JSONL + 字符二元组 Jaccard×0.7 + tags×0.2 + 时间衰减×0.1）注册为内核内建 syscall `mem.remember/recall/forget/stats`。③ 日记：`bin/diary.py` 聚合 audit + mem.recall → 四章节 markdown（LLM 可选，模板兜底）→ `mem.remember(kind="diary")` 入库；laosweb 增记忆/日记面板。

**前置探索结论：** SenseVoice 环境就绪（miniconda3 torch 2.6.0+cu124 + funasr 1.4.0 + sounddevice 0.5.6；模型缓存 D:/ldf/sensevoice_asr/models；server.py FastAPI 端口 8000；AutoModel 直调实测 RTF≈0.01）。

**隐私红线：** 录音只由显式 syscall 触发；每条录音写审计 `event:"mic"`；无显式调用无录音。

**Tasks:** T1 记忆库 + mem.*（commit 37cc6ea）→ T2 drv_mic + drv_ear（commit fa47b39）→ T3 日记 + 面板（commit 9891fb9）。

**明确不做（后续轮次）：** 技能库（越用越聪明）、手机端全天候事件接入、全天候低功耗实测。
