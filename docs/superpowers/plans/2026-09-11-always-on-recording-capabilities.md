# laos 全天候录音能力补齐（Always-On Recording Capabilities）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 laos 的听觉子系统从"VAD 门控会话录音"升级为业界验证过的**克制版全天候录音**：四级 mic 能力阶梯（内核强制）+ Opus 存储配额 + 常开模式（环形缓冲/rewind/buffer-and-burst）+ 分层摘要 + 录音状态指示 + 流式 ASR 通道，全部落在既有架构（内核闸门链 / MCP 驱动 / journal 管线）上。

**Architecture:** 业界 2024–2026 的结论（调研文档 `docs/research/always-on-recording-industry-2026-09.md` §8）：纯常开被动录音几乎全部倒下，活路是 **VAD 门控 + 本地低码率录音 + 事后批量转写（buffer-and-burst）+ 录音做成受能力表强制管控的系统资源**。laos 已有四段漏斗（`vad.py` → `drv_rec` → `ear.journal` → `journal.py`），本计划补齐五块空档：① 内核层把 mic 做成四级能力阶梯（`mic.listen → mic.record → mic.transcribe → mic.always_on`，高层含低层、默认收紧）；② `drv_rec` 存 Opus（可降级 WAV）+ 字节/段数配额 + TTL；③ `drv_mic` 新增常开模式（环形缓冲 + VAD 门控落盘 + `rewind` 回溯 + 充电时批量转写入口）；④ journal 分层摘要（hour→day→week 入记忆）；⑤ 内核 `mic_state` 状态事件 + `laosctl mic` 控制面；⑥ `ear.stream` 流式转写通道（抄 whisper_streaming 的 LocalAgreement 思路，确定性启发式可测）。所有内核改动保持零第三方依赖；驱动改动只在 conda 音频环境（`LAOS_EAR_PYTHON`）里用已装依赖，缺 Opus 写支持时静默降级 WAV。

**Tech Stack:** 内核层纯 stdlib（与现状一致）；驱动层 sounddevice / soundfile / numpy（conda 环境已有）；ASR 复用 drv_ear 双通道（funasr=SenseVoice 本机 / server=HTTP）；测试 `unittest`（253 项基线之上新增 ~30）。

**Spec:** 调研文档 `docs/research/always-on-recording-industry-2026-09.md`（§8 五条启示为 Global Constraints 的来源）+ 既有实现计划 `docs/superpowers/plans/2026-09-10-always-on-audio-journal.md`（四段漏斗已落地：`laos/vad.py`、`drivers/drv_rec.py`、`bin/journal.py`、`bin/diary.py`、`bin/mood_report.py`）。

## Global Constraints

以下约束全文生效，任何 Task 不得违反（措辞来自调研 §8 与既有隐私红线，逐条照抄）：

1. **供电预算**：不假设"全程流式上云"可行。`drivers/mic` 默认 Opus 低码率（16kbps 量级）存本地环形缓冲，不做实时 ASR；流式 ASR 仅在 VAD 语音段 + 策略要求实时时激活；高精度异步通道在充电/连 WiFi 时批量处理（buffer-and-burst）。
2. **VAD 门控 = 正确的"常开"**：麦克风硬件层常开，但软件层只在检测到语音时才编码/转写/存储——静音帧直接丢弃（零存储零后续算力）。
3. **存储三级压缩**：PCM 115MB/h → Opus 10.8MB/h → 转写文本 ~0.05MB/h → 向量 <0.1MB/h。`drivers/rec` 不存 PCM 原始音频；原始音频设 TTL（7 天上限），转写文本+向量长期保留。
4. **隐私能力模型**：四级能力 `mic.listen`(VAD能量) → `mic.record`(VAD门控录音) → `mic.transcribe`(ASR) → `mic.always_on`(24/7)，高层级包含低层级，每级独立授权、默认收紧，最高级需人类一次性释放（走内核确认闸门）。
5. **录音状态指示**：任何 agent 启动录音时内核必须发出可感知的状态信号（audit `mic_state` 事件 + `laosctl mic` 查询）。
6. **审计红线（现有，扩展）**：每一次 mic./rec. syscall——无论成败——额外落一条 `event:"mic"` 审计记录（`laos/kernel.py` `_deny` 与派发尾部已实现，扩展到 `rec.*`）。
7. **隐私红线（现有，贯穿）**：驱动模块加载时绝不启动任何录音线程；录音线程只能被显式 syscall 拉起；`LAOS_REC=0` 全局禁录（`EACCES`）。
8. **端侧优先**：默认纯端侧处理；上云转写需单独授权（现状：仅 `ear.transcribe` 走 server 通道时是云，保持原样）。
9. **零依赖**：`laos/` 内核目录禁止新增第三方 import；驱动目录允许惰性导入 conda 环境依赖，缺依赖必须可降级（`ENOENT` 或 fallback，不得崩模块导入）。
10. **不存声纹**：不新增任何说话人声纹注册/比对能力（中国法下声纹=敏感个人信息）。
11. 命名与提交：新代码中文注释；commit message 用仓库既有风格 `feat(laos): ...`；每个 Task 一个 commit，步骤用 `- [ ]` 跟踪。
12. 平台：桌面（Windows 降级 / Linux 全隔离）为主战场；真机 App 路径不在本计划范围（见 09-10 计划 Task 5，已另有 runbook）。

---

## File Structure（本计划新建/修改文件总览）

| 文件 | 动作 | 职责 |
|---|---|---|
| `laos/kernel.py` | 修改 | 新增 `MIC_CAP_LEVELS`/`MIC_LEVEL_ORDER`/`_mic_required`/`_mic_ladder_ok`/`_emit_mic_state`；审计红线扩展到 `rec.*` |
| `drivers/drv_rec.py` | 修改 | Opus 编码（自动降级 WAV）+ 字节/段数配额 FIFO 淘汰 + 扩展 `rec.start(encoding=)` / `rec.status` |
| `drivers/drv_mic.py` | 修改 | 新增 `set_input_factory` 注入点 + `mic.always_on_start/rewind/always_on_stop` 常开模式（环形缓冲 + VAD 落盘） |
| `bin/journal.py` | 修改 | 分层摘要（hour→day→week）+ 兼容 .opus 段转写 + `--summary` 开关 |
| `bin/laosctl.py` | 修改 | 新增 `mic` 子命令（录音状态/用量/拒绝回放） |
| `bin/laosd.py` | 修改 | boot 加载 `drv_rec`（此前漏加载）+ demo 听觉 agent 能力表更新 |
| `drivers/drv_ear.py` | 修改 | 新增 `ear.stream` 流式转写（LocalAgreement 启发式，chunk 自适应延长） |
| `tests/test_mic_caps.py` | 新建 | Task 1：四级能力阶梯 + 审计扩展 |
| `tests/test_rec.py` | 修改 | Task 2：编码降级/配额/状态 |
| `tests/test_always_on.py` | 新建 | Task 3：环形缓冲/rewind/stop flush |
| `tests/test_journal.py` | 修改 | Task 4：分层摘要 |
| `tests/test_laosctl.py` | 新建 | Task 5：`laosctl mic` 回放 |
| `tests/test_stream.py` | 新建 | Task 6：`ear.stream` 分片策略 |
| `README.md` / `docs/PROJECT_OVERVIEW.md` | 修改 | Task 7：能力阶梯/新工具/环境变量/测试数 |

---

### Task 1: 内核 mic 能力阶梯（四级门控 + 审计扩展）

**Files:**
- Modify: `laos/kernel.py`
- Test: `tests/test_mic_caps.py`（新建）

**Interfaces:**
- 新增模块级常量与门控（放在 `CapabilitySet` 之后）：
```python
# 录音管线四级能力阶梯（调研 §8.4：高层含低层、默认收紧、人类一次性释放）。
# 顺序即包含关系：mic.listen ⊂ mic.record ⊂ mic.transcribe ⊂ mic.always_on
MIC_LEVEL_ORDER = ["mic.listen", "mic.record", "mic.transcribe", "mic.always_on"]
MIC_CAP_LEVELS = {
    "mic.listen":     {"mic.listen_start", "mic.listen_stop", "mic.segments",
                       "mic.status", "rec.status", "rec.segments"},
    "mic.record":     {"mic.record", "rec.start", "rec.stop", "rec.gc"},
    "mic.transcribe": {"ear.transcribe"},
    "mic.always_on":  {"mic.always_on_start", "mic.always_on_stop", "mic.rewind"},
}
# 录音类 syscall 前缀：审计红线覆盖 mic.* 与 rec.*（ear.transcribe 是转写非录音）
MIC_AUDIT_PREFIXES = ("mic.", "rec.")
```
- 新增内核方法（挂在 `AgentKernel` 上）：
```python
def _mic_required(self, tool: str) -> str | None:
    """tool 所属的最低能力级；非录音工具返回 None（不强制）。"""
    for cap, tools in MIC_CAP_LEVELS.items():
        if tool in tools:
            return cap
    return None

def _mic_ladder_ok(self, pcb: "PCB", tool: str) -> bool:
    """能力阶梯检查：持有所需级或更高级即放行（高层含低层）。"""
    req = self._mic_required(tool)
    if req is None:
        return True
    idx = MIC_LEVEL_ORDER.index(req)
    return any(pcb.caps.allows(c) for c in MIC_LEVEL_ORDER[idx:])
```
- 在 `syscall()` 闸门链中插入（紧接 `_effective_allows` 检查之后、task_scope 之前）：
```python
if not self._mic_ladder_ok(pcb, tool):
    return self._deny(pcb, tool, args, started,
                      f"EACCES: mic capability level "
                      f"{self._mic_required(tool)} not granted")
```
- 审计红线扩展：`syscall()` 派发尾部与 `_deny()` 里 `tool.startswith("mic.")` 改为 `tool.startswith(MIC_AUDIT_PREFIXES)`。

- [ ] **Step 1: 写失败测试** `tests/test_mic_caps.py`：直插 stub 驱动（`self.syscall_table[tool] = ("mic", spec)`、`self.drivers["mic"] = StubDriver`，`StubDriver.call_tool` 返回 `CallResult.ok_text("OK")`），spawn 不同能力集的 agent 断言：
  - 无任何 mic 能力 → `mic.listen_start` 返回 `EACCES`（含 `mic capability level` 字样）
  - 仅有 `mic.listen` → `mic.listen_start` 成功、`mic.record` 被拒、`ear.transcribe` 被拒
  - 仅有 `mic.record` → `mic.record` 成功、`mic.listen_start` 成功（高层含低层）
  - 仅有 `mic.transcribe` → `ear.transcribe` 成功、`mic.listen_start` 被拒
  - 仅有 `mic.always_on` → `mic.always_on_start` 成功、`mic.rewind` 成功、`mic.listen_start` 成功
  - 被拒的 `rec.start` 也在审计里留下 `event:"mic", denied:true`（审计红线扩展）
- [ ] **Step 2: 运行确认失败** — `python -m unittest tests.test_mic_caps -v`，预期全部 FAIL（`EACCES`/门控未实现）
- [ ] **Step 3: 实现**（按上述 Interfaces 改 `laos/kernel.py`）
- [ ] **Step 4: 回归** — `python -m unittest discover -s tests`，预期 253 + ~7 全绿（既有 `test_laos.py`/`test_rec.py` 使用 mic 工具的地方若未带能力会被新闸门拦下——如失败，在对应测试的 spawn caps 里补 `mic.listen`/`mic.record`）
- [ ] **Step 5: Commit** — `feat(laos): kernel mic capability ladder (listen/record/transcribe/always_on)`

---

### Task 2: drv_rec 存储层——Opus 编码（自动降级）+ 配额 FIFO

**Files:**
- Modify: `drivers/drv_rec.py`
- Test: `tests/test_rec.py`（追加）

**Interfaces:**
```python
# 模块级纯函数：WAV PCM 段 → 目标编码字节 + 实际编码名（"wav" | "opus"）
def encode_segment(wav_bytes: bytes, encoding: str = "auto") -> tuple[bytes, str]:
    """encoding: "wav" | "opus" | "auto"。
    opus 用 soundfile 写 OGG/OPUS；libsndfile 不支持 OPUS 或依赖缺失时
    静默降级 wav（绝不抛错——存储层降级优于丢段）。auto=opus 优先。"""

def _segment_ext(enc: str) -> str:  # "wav" → ".wav"，"opus" → ".opus"

# 配额环境变量（模块顶部读一次，syscall 内每次读——测试可 mock.patch.dict）
#   LAOS_REC_MAX_BYTES    默认 268435456 (256MB ≈ Opus 24h)
#   LAOS_REC_MAX_SEGMENTS 默认 10000
```
- `rec.start(threshold_dbfs=-35.0, encoding="auto")`：新增参数；`_save_segment` 改为 `_save_segment(start_ms, wav)` 内部调 `encode_segment`，文件名 `rec-<seq:04d>-<ts>.<ext>`；写完后 `_enforce_quota()`
- `_enforce_quota()`：按 mtime 升序删除最旧段，直到 `size <= MAX_BYTES` 且 `count <= MAX_SEGMENTS`；返回本次淘汰数（写进 `rec.status` 的 `evicted` 计数，模块级 `_evicted_total` 累计）
- `rec.segments` / `rec.gc` 的 glob 从 `rec-*.wav` 改为 `rec-*.*`
- `rec.status` 追加 `encoding=<opus|wav> evicted=<n> bytes=<dir 内总字节>`

- [ ] **Step 1: 追加失败测试**（沿用 FakeInputStream 注入；`synth_pcm` 已有）：
  - `encode_segment(wav, "wav")` 返回原字节；`encode_segment(wav, "opus")` 在 `drv_rec._SF_OK=False`（monkeypatch 模拟无 soundfile/无 OPUS）时返回 `("wav", 原字节)`；真环境有 OPUS 时返回 `("opus", 非空字节)`（用 `skipUnless` 保护）
  - 配额：`LAOS_REC_MAX_SEGMENTS=2` 时喂 3 段 → 只留 2 个文件、`rec.status` 里 `evicted>=1`、最旧段已删
  - 配额字节：`LAOS_REC_MAX_BYTES` 设极小（如 4096）→ 写完即淘汰直到低于阈值
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（改 `drivers/drv_rec.py`；`_save_segment` 内先 `bytes, enc = encode_segment(...)` 再按 `_segment_ext(enc)` 命名）
- [ ] **Step 4: 回归** — `tests/test_rec.py` 全绿 + 全量
- [ ] **Step 5: Commit** — `feat(laos): drv_rec opus encoding with fallback and storage quota`

---

### Task 3: drv_mic 常开模式——环形缓冲 + VAD 门控落盘 + rewind

**Files:**
- Modify: `drivers/drv_mic.py`
- Test: `tests/test_always_on.py`（新建）

**Interfaces:**
```python
# 测试注入（与 drv_rec.set_input_factory 同款，放模块级）
def set_input_factory(factory) -> None: ...   # callable(samplerate, blocksize, dtype, callback) -> stream
def set_output_dir(path: Path | None) -> None: ...

# 新 syscall（内核能力阶梯把这三个工具挂在 mic.always_on 级）
mic.always_on_start(ring_seconds=120, threshold_db=-40.0, min_silence_ms=300)
    # 拉起常开线程：持续读 100ms 块；块进环形缓冲（collections.deque(maxlen=ring_seconds*10)）；
    # 同 listen 一样跑 split_on_silence → 新完成的有声段落盘 var/ear/segments/
    # 隐私：尊重 LAOS_REC=0（EACCES）；线程只能本调用显式拉起；内存上限 ring_seconds<=600
mic.rewind(seconds=15)
    # 返回 var/ear/segments/rewind-<ts>.wav（最近 seconds 秒环形缓冲拼成的 WAV）
    # 未在常开模式 → 返回 "ENOTACTIVE: always_on not running"
mic.always_on_stop()
    # 停线程 + flush 最后一段未闭合有声区（复用 _listen_loop 收尾语义）
```
- 实现提示：`_always_on_loop` 与 `_listen_loop` 结构相同，差异是每块先推入 `_ring`（`deque`，元素为 100ms PCM16LE 字节块），`_write_segment` 前把 ring 内字节与 buffer 合并用于 rewind（rewind 直接取 `b"".join(_ring)[-seconds*SR*2:]` 包 WAV）。`_ring_lock` 保护读写。
- `mic.status` 追加 `always_on=<bool> ring_seconds=<n>`。

- [ ] **Step 1: 写失败测试** `tests/test_always_on.py`：
  - `set_input_factory` 注入三段式音频（有声 0.4s / 静 0.6s / 有声 0.4s）→ `always_on_start` → 断言 `var/ear/segments/` 出现 2 个语音段文件（VAD 门控落盘）
  - `rewind(seconds=15)` 返回存在的 wav，`wave` 解析帧数 ≈ 喂入总时长（≤15s 部分）
  - `rewind` 在未启动时报 `ENOTACTIVE`
  - `LAOS_REC=0` 时 `always_on_start` 抛 `PermissionError`
  - `always_on_stop` 后 `mic.status` 里 `always_on=False`、最后未闭合段已 flush
  - 停止后重入 `always_on_start` 可再次启动（线程不复用）
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（`drivers/drv_mic.py`；`_listen_loop` 与 `_always_on_loop` 共享一个 `_consume_voice(buffer, emitted)` 纯函数避免逻辑漂移——已有 `split_on_silence` 薄包装）
- [ ] **Step 4: 回归** — 全量
- [ ] **Step 5: Commit** — `feat(laos): mic always-on mode with ring buffer and rewind`

---

### Task 4: journal 分层摘要（hour→day→week）+ .opus 段兼容

**Files:**
- Modify: `bin/journal.py`
- Test: `tests/test_journal.py`（追加）

**Interfaces:**
```python
def build_summaries(items: list[dict], buckets=("hour", "day", "week")) -> list[dict]:
    """items = run_pipeline()["ok"]（含 wav 名 + text + emotions）。
    按 wav mtime 分桶（hour=同一小时 / day=同日 / week=同 ISO 周），
    每桶产出 kind="journal_summary" 记忆：
      text = f"[{bucket_label}] {extractive_summary}"
      tags = [bucket_label, "summary"]
    extractive_summary（零依赖）：桶内文本拼接，取前 400 字符 + 尾部 100 字符
    （"掐头去尾"式抽取摘要；不做 LLM——genie 通道留作 future 增强）。"""
```
- `run_pipeline` 保持转写+记忆主流程不变；新增 `--summary` 开关：转写后调 `build_summaries`，把摘要逐条 `memory.remember(...)`，打印摘要行
- `.opus` 兼容：`Path(journal_dir).glob("rec-*")`（不再限定 .wav）；转写前若 `suffix != ".wav"` 且走 server 通道，先经 soundfile 读→写临时 .wav（conda 环境有 soundfile；funasr 通道直接读 .opus 即可）

- [ ] **Step 1: 追加失败测试**：构造 3 个不同 mtime 的假 wav（同小时 2 个、次日 1 个）+ mock transcribe → `build_summaries` 产出 2 条（hour 桶 2 个合并 + day 桶跨小时合并），text 含掐头去尾摘要、tags 含 `summary`；`--summary` 模式记忆库新增对应 kind；空 items → `[]`
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 回归** — 全量
- [ ] **Step 5: Commit** — `feat(laos): journal hierarchical summaries (hour/day/week)`

---

### Task 5: 录音状态指示——内核 `mic_state` 事件 + `laosctl mic`

**Files:**
- Modify: `laos/kernel.py`
- Modify: `bin/laosctl.py`
- Test: `tests/test_laosctl.py`（新建）

**Interfaces:**
```python
# 内核：录音会话起止工具（成功派发后发状态事件）
MIC_SESSION_TOOLS = {
    "mic.listen_start": "on", "mic.listen_stop": "off",
    "mic.record": "on", "rec.start": "on", "rec.stop": "off",
    "mic.always_on_start": "on", "mic.always_on_stop": "off",
}
# syscall() 派发尾部（审计 event:"mic" 之后追加）：
#   state = MIC_SESSION_TOOLS.get(tool)
#   if state and result.ok:
#       self.audit.write({"t": time.time(), "event": "mic_state",
#                         "pid": pid, "tool": tool, "state": state})
```
- `laosctl mic`（新子命令）：回放审计日志——
  - 每 pid 当前录音状态（按 `mic_state` 最后一条 state 推断）
  - mic 工具调用统计（`event:"mic"` 计数，按 tool + ok/denied 分组）
  - 每次 `rec.start/always_on_start` 至今的持续时长
- `main()` 的 `choices` 加入 `"mic"`。

- [ ] **Step 1: 写失败测试** `tests/test_laosctl.py`：手写一段合成审计 JSONL（含 `mic_state` on/off、`event:"mic"` 若干、spawn 记录）→ `load()` + `cmd_mic` 重定向 stdout，断言：pid 状态推断正确（最后是 off → 未录音）、调用统计计数正确、无记录时友好空态
- [ ] **Step 2: 运行确认失败**（`mic` 不在 choices → argparse 报错）
- [ ] **Step 3: 实现**（kernel `MIC_SESSION_TOOLS` + 派发尾部；laosctl `cmd_mic`）
- [ ] **Step 4: 回归** — 全量
- [ ] **Step 5: Commit** — `feat(laos): mic_state kernel event and laosctl mic command`

---

### Task 6: ear.stream 流式转写通道（LocalAgreement 启发式）

**Files:**
- Modify: `drivers/drv_ear.py`
- Test: `tests/test_stream.py`（新建）

**Interfaces:**
```python
ear.stream(wav, chunk_ms=1000, extend_ms=500, max_extend_ms=3000, strategy="local_agreement")
    # 返回 JSON 行（每行一条）：
    #   {"start_ms": int, "text": str, "final": bool, "strategy": str}
    # 语义：长 wav 按 chunk 顺序转写；strategy:
    #   "greedy"         固定 chunk_ms，不延长
    #   "local_agreement" 该 chunk 转写文本末尾非句末标点 且 块尾 300ms RMS 高于
    #                     阈值（仍在说话）→ 延长 extend_ms 重转写；累计延长超
    #                     max_extend_ms 强制 final（防无限伸长）
    # 转写后端复用 ear.transcribe 逻辑（funasr 或 server 通道，按 LAOS_ASR_CHANNEL）
    # 块尾 RMS 用 laos.vad.rms_dbfs（零依赖，与 VAD 同源）
```
- 新增模块级纯函数（可测）：
```python
def _needs_extension(text: str, tail_voiced: bool, extended_ms: int,
                     max_extend_ms: int) -> bool:
    """text 末字符非句末标点（。！？.!?）且 tail_voiced 且未超 max → True。"""
def _split_chunks(path: Path, chunk_ms: int) -> list[tuple[int, bytes]]:
    """wav → [(start_ms, pcm16le_bytes)]（stdlib wave 读）。"""
```

- [ ] **Step 1: 写失败测试** `tests/test_stream.py`：
  - `_needs_extension` 三态：句末标点结尾 → False；无标点 + tail 有声 → True；无标点 + tail 静音 → False；超 max_extend → False
  - 合成"两词夹 600ms 静音"的 wav（词长 800ms，chunk=1000ms）→ greedy 出 2 条 final；local_agreement 在第 1 块尾因句内切分延长后合并成更少 final 段（用注入的 fake transcribe 返回可预期文本）
  - `ear.stream` 对不存在的 wav 返回 `ENOENT` 错误
- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**（`drivers/drv_ear.py`；`ear.stream` 内部 `chunk → _transcribe_xxx` 复用现有函数；尾部 RMS 由 chunk 末尾 300ms 样本算）
- [ ] **Step 4: 回归** — 全量
- [ ] **Step 5: Commit** — `feat(laos): ear.stream adaptive streaming transcription (local agreement)`

---

### Task 7: 引导集成 + 文档收尾

**Files:**
- Modify: `bin/laosd.py`
- Modify: `README.md`
- Modify: `docs/PROJECT_OVERVIEW.md`

**Interfaces / 内容：**
- `bin/laosd.py`：在 `ear`/`mic` 加载后追加（drv_rec 此前**未加载**，属遗漏修复）：
```python
kernel.load_driver("rec", [ear_py, str(DRIVERS / "drv_rec.py")], env=env)
```
- demo 听觉 agent 的 spawn caps 更新为 `["mic.listen", "mic.record", "mic.transcribe"]`（**不给** `mic.always_on`——默认收紧，需人类显式授予）
- `README.md`：驱动清单补 `drv_rec`；新增"全天候录音能力阶梯"小节（四级表 + `LAOS_REC_MAX_BYTES`/`LAOS_REC_MAX_SEGMENTS`/`LAOS_REC=0` 环境变量 + `mic.always_on` 用法 + `laosctl mic`）；测试数更新
- `docs/PROJECT_OVERVIEW.md`：听觉链路段补能力阶梯一句 + 计划链接

- [ ] **Step 1: 改 `bin/laosd.py` 并冒烟** — `python bin/laosd.py` 跑完 demo 无异常、`lsmod` 含 rec；`python -m unittest tests.test_laos -v` 绿
- [ ] **Step 2: 更新 README / PROJECT_OVERVIEW**
- [ ] **Step 3: 全量回归** — `python -m unittest discover -s tests`，记录最终测试数
- [ ] **Step 4: 端到端验收**（桌面）：
  ```
  python bin/laosd.py            # boot 含 rec 驱动
  # 面板/CLI：给听觉 agent 授 mic.listen+mic.record+mic.transcribe →
  #   rec.start → 说话 → rec.stop → python bin/journal.py --summary
  #   断言：mem 有 kind="journal" 与 "journal_summary"；laosctl mic 显示状态；wav 已 gc
  python bin/laosctl.py mic      # 录音状态/用量回放
  ```
- [ ] **Step 5: Commit** — `feat(laos): boot rec driver, docs for always-on recording`

---

## 验收清单（全部完成后）

- [ ] 全量测试全绿（基线 253 + 本计划 ~30）
- [ ] 四级能力阶梯：无 mic 能力 agent 对 `rec.start`/`mic.listen_start`/`ear.transcribe` 全部 EACCES；仅授 `mic.record` 的 agent 能用 `mic.listen_start` 但不能 `ear.transcribe`（高层含低层语义正确）
- [ ] `rec.start(encoding="opus")` 在无 OPUS 环境自动降级 WAV 不崩；配额超限 FIFO 淘汰并记 `evicted`
- [ ] `mic.always_on_start` → 说话 → `mic.rewind(15)` 能取回最近 15s；`LAOS_REC=0` 拒绝；`mic_state` 审计 on/off 成对
- [ ] `journal.py --summary` 产出 hour/day/week 摘要记忆；.opus 段可转写
- [ ] `laosctl mic` 正确回放录音状态与用量
- [ ] `ear.stream` greedy 与 local_agreement 两种策略结果可预期（测试钉住）
- [ ] `bin/laosd.py` 加载 rec 驱动；README/PROJECT_OVERVIEW 已更新
- [ ] 每个 Task 一个 commit（共 7 个）

## 自检记录（写完即核）

- **Spec 覆盖**：调研 §8 五条启示 → Task 1（能力模型/状态指示）Task 2（存储配额/Opus）Task 3（供电预算/环形缓冲/rewind）Task 4（分层摘要）Task 6（流式 ASR 选型）；Global Constraints 每条有对应 Task。
- **占位符扫描**：无 `TBD`/`待补`/`类似 Task N`；每个代码步都有真实代码。
- **类型/命名一致**：`MIC_CAP_LEVELS`/`MIC_LEVEL_ORDER`/`_mic_required`/`_mic_ladder_ok`/`encode_segment`/`_enforce_quota`/`mic.always_on_start`/`mic.rewind`/`mic.always_on_stop`/`build_summaries`/`MIC_SESSION_TOOLS`/`ear.stream`/`_needs_extension`/`_split_chunks` 在定义处与调用处逐字一致；`laosctl` 新子命令与 `main()` choices 同步。
- **既有接口不破坏**：`rec.start` 新增参数带默认值；`mic.*` 既有工具行为不变（仅新增能力闸门与状态事件）；journal 主流程向后兼容（`--summary` 为新增开关）。
