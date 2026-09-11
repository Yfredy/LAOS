# 低功耗全天候录音管线（听觉日志）——用途分析与实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 laos 加"听觉日志管线"：低功耗常驻拾音 → 只捕获有声段 → 本地 ASR → 结构化入记忆库 → 日记/情绪曲线消费。回答两个问题：全天候录音**有什么真实用途**（Part A，用已验证的商业产品与研究背书），以及 laos **怎么以正确的架构实现**（Part C，五个 task）。

**Architecture:** 关键认知——**"全天候录音"不是"录 24 小时音频"，而是一条四段漏斗**：常驻低功耗检测（DSP/毫瓦级）→ VAD 触发式捕获（只存有声段）→ 即时蒸馏（本地 ASR 转文字+情感）→ **原音频即焚**（默认数小时后删）。全存原始音频 = 每天 2.7GB + 电池灾难 + 隐私雷区；漏斗之后留下的是几天几 MB 的结构化记忆——这才是"越用越聪明"的燃料。laos 侧：`laos/vad.py`（零依赖流式 VAD，取代 drv_mic 里的简化版）+ `drv_rec`（录音会话驱动，conda python）+ `ear.journal` 批量转写（复用 drv_ear 双通道）+ 日记/情绪周报消费。

**Tech Stack:** 核心零依赖（vad.py 纯 numpy-free：stdlib `audioop`/`math`；Python 3.13 移除了 audioop——用纯 Python RMS 兜底）；录音用 conda 环境的 sounddevice；ASR 复用 SenseVoice（GPU RTF≈0.01，情感标签现成）。

**Spec:** 用户需求（全天候录音 + 用途）；既有关联：QNN/ADSP LPAI 常驻情感识别（`docs/research/2026-09-09-qnn-real-os-integration.md`）、drv_ear 情感标签解析、mem.*/diary。

---

## Part A：全天候录音的真实用途（不是功能清单，是有人付钱的场景）

> 你说"只能想到功能想不到实际用途"——原因是功能思维停在"录了什么"，用途思维要问"**谁来查它、查的时候在找什么、现在他们为此付多少钱**"。以下每个场景都有已上市产品或严肃研究背书。

### A1. 会议/课堂自动笔记（最大众，商业验证最充分）
**场景**：你一天开了三个会，谁说了什么、待办是什么——人脑记不全，笔记跟不上。
**谁在做**：Limitless Pendant（$199 吊坠，全天候录音+转写+摘要）、Plaud Note（录音卡片）、Otter.ai（会议转写，独角兽）、Google Pixel 的 Recorder。
**laos 形态**：`rec.start` 进会场 → 分段捕获 → ASR → `mem.remember(kind="meeting")` → 日记里"今天三个会，要点如下"。**你的差异化：全程本地 ASR，会议内容不出设备**（Limitless 们做不到的隐私卖点）。

### A2. 记忆外挂（医疗与生活，研究最热）
**场景**："上周医生说我那个指标要注意什么来着？""那天认识的同事叫什么？"
**谁在做**：Limitless 的定位就是"记忆外挂"；Microsoft Recall（全屏截图版，争议极大——因为**截图**比**录音**隐私雷区更大）；学术界叫"记忆假体"（memory prosthesis），用于轻度认知障碍/早期阿尔茨海默患者。
**laos 形态**：听觉日志 + `mem.recall` 天然就是这个——"上周三"这类时间查询正是 mem.recall 的时间衰减检索设计所服务的。

### A3. 情绪健康追踪（你的 SER 模型的主场，最独特）
**场景**：连续 30 天的"说话情绪曲线"——你自己感觉"最近状态不好"之前，数据已经显示了（语气更平、话更少、负面词更多）。抑郁/焦虑的语音标志物是活跃研究方向（vocal biomarkers）。
**谁在做**：Corama、Ellipsis Health（语音生物标记物诊断辅助）、大量数字疗法研究。
**laos 形态**：drv_ear 已经解析 SenseVoice 情感标签（NEUTRAL/HAPPY/SAD/ANGRY）——每段转写自带情感 → 日记的情感曲线 → 周报。**再加上 ADSP 上常驻的 TIM-Net（<5mW，不上传音频只上报情感事件）——这是别的产品没有的"零隐私泄露情绪追踪"**（你的 QNN 项目就是为此设计的）。

### A4. 看护与安全（社会价值最高）
**场景**：独居老人——跌倒声/呼救声/长时间异常安静（是好事还是出事了？）；婴儿房——哭声即时通知；抑郁症患者——深夜频繁叹气/哭声。
**谁在做**：Amazon Alexa Care Hub、Apple Watch 跌倒检测（声音版）、学术界的 acoustic monitoring for elderly care。
**laos 形态**：VAD + 声学事件分类（呼救/哭声/跌倒是音频分类模型，可作为 SER 之外的第二个小模型上 ADSP）→ `mem.remember(kind="alert")` + 通知驱动。**注意合规**：看护录音需被看护人知情同意。

### A5. 语言学习与表达习惯（个人成长）
**场景**：学外语——今天说了多少英语、卡壳在哪；演讲训练—— filler words（"嗯""那个"）频率；程序员——每天说多少无效会议。
**laos 形态**：SenseVoice 的 language 标签直接统计每日语言占比；文本里数 filler words。

### A6. 不要做的场景（诚实边界）
- **秘密录音他人**：多数司法辖区违法（中国：民法典1033条；两卡条例）——laos 的审计 + 本地处理是防护，但法律边界靠你
- **上传云端做训练**：与"本地 ASR"卖点自相矛盾
- **无限期保留原音频**：默认即焚（见 Task 5 的 KEEP 策略）

**A 部结论**：这条管线做完 = laos 拥有 Limitless 的核心功能 + 你独有的零云隐私架构 + SER 情绪追踪。这是能写进简历/面试的完整故事：**"从 DSP 模型部署到 Agent 操作系统的端侧 AI 全栈"**。

---

## Part B：架构——四段漏斗（核心设计文档）

```
[第1段 常驻检测]  麦克风 → 分块流(100ms) → StreamingVAD(能量+滞回)
                  ◇ 无声：丢弃（0 存储）
[第2段 触发捕获]  检测到语音 → 环形缓冲补 padding → 有声段成段(≥200ms)
                  → var/ear/journal/<ts>.wav（仅有声段，日均 <30MB）
[第3段 即时蒸馏]  ear.journal：SenseVoice 转写 + 情感标签
                  → mem.remember(kind="journal", tags=[日期,情感])
                  ◇ 默认策略：转写成功后原 wav 定时即焚（LAOS_JOURNAL_KEEP_H=6）
[第4段 消费]      mem.recall → 日记「今天听到的」→ 情绪周报 → mem 技能匹配
```

**功耗真话（桌面 vs 真机）**：
- 桌面/插电：sounddevice 流式录音常驻无压力
- 手机 Termux：**不能**用 sounddevice 常驻（AP 常醒 = 电池灾难）——正确路径是 App 侧 VAD 服务（前台服务，AudioRecord）或 ADSP 常驻检测（你的 LPAI 模型路线）；Termux:API 的 `termux-microphone-record` 只支持启停不支持流。所以真机路径 = App 扩展（Task 5 runbook），Termux 路径只做"手动触发录音"
- 这就是为什么 Part C 全部先在桌面实现：架构语义与平台解耦

---

## Part C：实施任务

### Task 1: `laos/vad.py` —— 流式 VAD（纯函数 + 流式类，零依赖）

**Files:**
- Create: `laos/vad.py`
- Modify: `drivers/drv_mic.py`（`split_on_silence` 委托 `laos.vad`，消除重复实现）
- Test: `tests/test_vad.py`（新建）

**Interfaces:**
```python
def rms_dbfs(samples: Sequence[int]) -> float:
    """RMS → dBFS（满幅正弦≈0，静音≈-∞；全零返回 -120.0）"""

def split_segments(samples, sr, *, threshold_dbfs=-35.0,
                   min_speech_ms=200, min_silence_ms=400, pad_ms=100
                  ) -> list[tuple[int, int]]:
    """批式分段：返回有声区间 [(start, end)]（样本索引，含 pad）。"""

class StreamingVAD:
    """流式版：feed(chunk: bytes#PCM16LE) → 每次返回「新完成的有声段」列表
    （(start_ts_ms, wav_bytes)，内部攒帧、滞回判停、pad 补边）。
    与批式 split_segments 在同一音频上分段结果一致（一致性测试钉住）。"""

def wav_bytes(segment_samples, sr) -> bytes:  # PCM16LE → WAV 字节（stdlib wave+io）
```

- [ ] **Step 1: 失败测试**（tests/test_vad.py）：合成音频三件套（正弦有声 0.3s / 静 0.5s / 有声 0.3s）→ 批式 2 段；流式按 100ms 分块喂 → 分段与批式一致（起止差 ≤1 帧）；全静音 → 0 段；纯音全有声 → 1 段；rms_dbfs 满幅/全零两端；drv_mic 的 split_on_silence 委托后既有测试（test_ear_mic）仍绿
- [ ] **Step 2: 确认失败 → Step 3: 实现**（stdlib `audioop.rms`，`ImportError` 时纯 Python 兜底）**→ Step 4: 回归（+~6）**
- [ ] **Step 5: Commit** — `feat(laos): streaming VAD (laos/vad.py, zero-dep)`

### Task 2: `drivers/drv_rec.py` —— 录音会话驱动（触发式捕获）

**Files:**
- Create: `drivers/drv_rec.py`
- Modify: `bin/laosd.py`（boot：conda python 存在且 sounddevice 可导入 → 加载 drv_rec）
- Test: `tests/test_rec.py`（新建）

**Interfaces:**
- 跑在 **conda python**（sounddevice 0.5.6 已装）；`import sounddevice` 惰性
- `rec.start(threshold_dbfs=-35)`：开 InputStream（100ms 块）→ 内部 StreamingVAD → 有声段写 `var/ear/journal/rec-<seq>-<ts>.wav` → 返回 `OK recording`
- `rec.stop` → `OK stopped, N segments`；`rec.segments(since_ts=0)` → 新分段列表（路径+时长）；`rec.status` → `recording=<bool> segments=<n> keep_hours=<h>`
- **隐私与策略**：`LAOS_REC=0` 时 start 返回 `EACCES: recording disabled (LAOS_REC)`（总开关，默认开但显式触发才录）；每段写审计 `event:"rec"`；`LAOS_JOURNAL_KEEP_H=6`——`rec.gc()` 删除超龄原音频（默认在 journal 转写成功后由调用方触发 gc）
- **内核联动**：laosd boot 后 `kernel.set_pricing_multiplier` 不动，但 `rec.segments` 结果供 4.7 之后的新 act 展示

- [ ] **Step 1: 失败测试**（FakeSoundDevice 注入 InputStream 假流——喂合成三段音频，断言：只产 2 个有声 wav、文件可被 stdlib wave 解析、stop 后 status 归零、LAOS_REC=0 → EACCES、gc 删超龄保留未超龄）
- [ ] **Step 2: 确认失败 → Step 3: 实现 → Step 4: 回归（+~7）**
- [ ] **Step 5: Commit** — `feat(laos): drv_rec VAD-gated recording sessions (explicit trigger)`

### Task 3: `ear.journal` —— 分段批量转写 + 入记忆

**Files:**
- Modify: `drivers/drv_ear.py`（新增 `ear.journal`：批量转写 var/ear/journal/*.wav → text+emotions → 返回 JSONL 行；不写记忆——记忆由调用方 mem.remember 完成，保持"驱动只做设备"分层）
- Create: `bin/journal.py`（CLI：`ear.journal` 拉转写 → `mem.remember(kind="journal", tags=[date, emotion])` → `rec.gc()` 即焚 → 打印时间线）
- Test: `tests/test_journal.py`

**Interfaces:**
- `ear.journal(wav_dir, since_ts=0)` → `{"items": [{"wav", "text", "emotions", "language", "latency_ms"}]}`（逐段调 ear.transcribe 已有逻辑，失败段标 error 继续）
- `bin/journal.py` 流程：找 var/ear/journal 新分段 → ear.journal → 每条 `mem.remember("journal", text=f"[{时刻}] {text}", tags=[emotion])` → `rec.gc()` → 打印「时间线 + 情感统计」

- [ ] **Step 1: 失败测试**（mock ear 通道 + 3 个假 wav：2 转写成功 1 失败 → 时间线 2 条、失败 1 条标注、记忆 +2、gc 后 wav 清空）
- [ ] **Step 2: 实现 → Step 3: 回归（+~4）**
- [ ] **Step 4: Commit** — `feat(laos): journal pipeline (batch ASR segments into memory, auto-gc)`

### Task 4: 日记与情绪曲线消费

**Files:**
- Modify: `bin/diary.py`（build_diary 增「今天听到的」章节：kind="journal" 的记忆按时间排列 + 情感标签统计条形图（纯字符））
- Create: `bin/mood_report.py`（`--days 7`：journal 记忆的情感标签按日统计 → 字符堆叠条形图 + 趋势一句；纯 stdlib）
- Test: `tests/test_diary.py` 追加 + `tests/test_mood.py`（新建）

- [ ] **Step 1: 失败测试**（diary 含「今天听到的」章节与情感统计；mood 按日聚合正确；7 天空数据 → 友好空态）
- [ ] **Step 2: 实现 → Step 3: 回归（+~5）**
- [ ] **Step 4: Commit** — `feat(laos): diary audio section and weekly mood report`

### Task 5: 真机路径 runbook（App VAD 录音服务）+ 文档收尾

**Files:**
- Modify: TimnetLpaiApp `InferenceServer.kt`（`POST /rec/start`、`POST /rec/stop`、`GET /segments`——App 内 AudioRecord + 能量 VAD 分段落 App 私有存储；前台服务通知遵 Android 规范）、`MainActivity.kt`（按钮接线）
- Modify: `docs/research/qnn-real-device-runbook.md`（真机录音闭环章节：`adb forward` → drv_ear device 通道转写 → journal 入库）
- Modify: `README.md`（驱动清单 + 听觉日志管线图 + 测试数）、`docs/guide-panel.md`（「听觉日志」节）

- [ ] **Step 1: Kotlin 实现 → Step 2: 构建通过（`gradlew assembleDebug`）→ Step 3: runbook（真机步骤 + 合规提示：知情同意）→ Step 4: 回归**
- [ ] **Step 5: Commit** — `feat(laos): on-device VAD recording service and runbook`

---

## 隐私与合规设计（贯穿红线）

1. **显式触发**：`rec.start` 是 syscall；`LAOS_REC=0` 全局禁录；每段写审计
2. **本地蒸馏**：ASR 用本机 SenseVoice（模型本地缓存）——音频与文本都不出设备
3. **原音频即焚**：`rec.gc()` 默认保留 6 小时（转写成功为前提），`LAOS_JOURNAL_KEEP_H` 可调
4. **他人声音**：现实约束——多人环境会录到他人；缓解：仅会议/独处场景开启 + 本地说话人识别（future：复用 SER-Distill 思路训练 speaker embedding）
5. **法律提示写入 runbook**：中国民法典1033条——录制他人需知情同意；本管线默认仅拾取使用者本人环境音

## 验收清单（全部完成后）

- [ ] 全量测试全绿（基线 203 + ~22）
- [ ] 桌面端到端：`rec.start` → 说话 → `rec.stop` → `python bin/journal.py` → mem 里有转写 → 日记「今天听到的」有内容 → wav 已 gc
- [ ] 情绪周报：连续多日数据后 `python bin/mood_report.py` 出字符图
- [ ] 隐私：`LAOS_REC=0` 时全链路拒绝；审计完整
- [ ] 5 个 commit（每 task 一个）+ 真机 APK 构建
