# laos 上线前技术评审（2026-10-07）

> **评审对象**：laos v0.19.0（主库 691 项测试实跑通过，`-m unittest discover -s tests -q` = "Ran 691 tests / OK (skipped=5)"，2026-10-07 实跑核对；页脚总数 1041 = 主库 691 + 隔离区 AlwaysOnRec-ZCode 279 + 复现区 Repro-ZCode 71，两区计数亦当日实跑核对）。
> **定位重申（叙事红线）**：基座是 Linux 内核，Agent 是内核之上的新负载（与进程同类）；laos 是内核治理在用户态的延伸——laosd 是架在 Linux kernel 之上的薄内核（语义层），所有特权操作最终仍由 Linux 执行，laosd 只负责"允许不允许、记不记"。
> **数字口径**：本文全部数字取自仓库既有实测（计划事实基线 + README/CHANGELOG/PROJECT_OVERVIEW + 引用调研文档）或本评审当日实跑（§5 逐模块测试数为 `python -m unittest tests.test_X` 实跑 "Ran N tests"）；未实测维度一律明写"未实测"，不引入外部宣称值。
> **本文角色**：与《需求评审》（docs/review/2026-10-07-requirements-review.md）交叉一致（场景完成度口径对齐其 §2）；**§4 风险与债务表编号冻结（R1…R11）**，是《埋点设计》（Task 3）发射点覆盖面的技术源头。

---

## §1 架构盘点（五层表）

> 模块清单实取自 `ls laos/`（机械口径：主包 36 个 .py 文件 = 35 个功能模块 + 包 `__init__.py`；`enforcement/` 子包另 5 个 .py = 4 个后端文件 base/linux/android/stub + 子包 `__init__.py`）与各模块 docstring 首行（2026-10-07 实取），非凭记忆罗列。完成度口径与 T1 §2.2 能力分解交叉一致。

| 层 | 一句话职责 | 核心模块（laos/，docstring 首行实取） | 驱动/入口载体 | 完成度 |
|---|---|---|---|---|
| **① 内核语义层** | 架在 Linux kernel 之上的用户态薄内核：进程表、syscall 闸门链、驱动路由、审计、上下文配额 | `kernel.py`（laosd 内核）、`agent.py`（Agent=进程）、`brain.py`（CPU）、`context.py`（内存管理单元）、`memory.py`（episodic memory）、`skills.py`（技能沉淀）、`branch.py`/`cow.py`（fork-COW 分支原语）、`scheduler.py`（多 Agent 公平复用 LLM）、`mcp.py`（MCP 最小实现=驱动总线，含 Tasks/Elicitation）、`validate.py`（schema 校验+路径围栏）、`locks.py`（unique_lock 语义）、`agentprof.py`（审计→语义 span）、`profiling.py`（eBPF 内核真值） | `bin/laosd.py`（init）、`bin/laosctl.py`、`bin/laosweb.py`；治理类驱动（fs/proc/sys/screen/apps/comms/notify/battery/events/genie） | **✅ 完整**（T1 S3 场景 ✅；审计+内核真值+语义剖析三层齐备） |
| **② 强制层** | 把 Linux 内核已有强制原语包装成 laos 的"保护环"，OSAL 换平台=换一个文件 | `sandbox.py`（Sandbox/PathJail）、`seccomp.py`（ctypes 经典 BPF，34 条危险 syscall）、`risk.py`（FleetLedger 不可逆风险账本）、`enforcement/`：`base.py`（后端契约）+ `linux.py`（unshare+seccomp+cgroup v2 真隔离）+ `android.py`（Termux 矩阵）+ `stub.py`（非 Linux 降级） | `scripts/termux_matrix.py`（Android 降级矩阵一键实测） | **✅ 完整**（Linux 真隔离 + 非 Linux 自动降级"仅能力表"，矩阵实测入档） |
| **③ 听觉栈** | 四段漏斗（VAD 常驻检测→触发捕获→即时蒸馏→原音频即焚）+ 三通道 ASR + 评测与空间音频研究件 | `vad.py`（零依赖 VAD，流式/批式一致）、`vadmetrics.py`（FA/FR/F1+BG-FAR 防装死闸）、`wer.py`（WER/CER 纯标准库）、`refiner.py`（AgenticSR 规则版 Refiner）、`loudness.py`（BS.1770-4）、`binaural.py`（ILD/IPD）、`foa.py`（一阶 Ambisonics）、`micgeom.py`（阵列几何/MPE）、`duplex.py`（双工时序度量） | 听觉驱动：`drv_ear.py`（ASR 三通道）、`drv_mic.py`（显式录音+VAD 分段，event:"mic" 双路径）、`drv_rec.py`（VAD 触发式录音+rec_gc 即焚）、`drv_audio.py`（FLASepformer 分离+JAEC AEC）、`drv_npu.py`（QNN 后端+真机传输）；入口 `bin/journal.py`/`diary.py`/`mood_report.py` | **◐ 部分**：VAD/ASR/refiner/评测 ✅（实测）；**KWS ◐**（模型+词表已拿到，真音频触发未跑）；空间音频件（binaural/foa/micgeom/loudness）为研究资产向组件，非生产链路（T1 S1 ✅ 不受影响） |
| **④ 对话控制面** | v0.17.0 语义复现波次五件：唤醒会话机、对话调度核、知识短路、TTS 适配、轮转策略 | `wakegate.py`（四态会话机，唤醒只由端侧音频触发、文本永不唤醒）、`dialogsched.py`（generation 版本化打断+投机 prefill 窗+latest-only 队列+MicrophoneGate+TtsRouter）、`knowledge.py`（bigram 廉价短路层，阈值 0.58）、`speechchunk.py`（LLM 流→TTS 友好文本三段适配）、`turnpolicy.py`（speak/hold/stop 三态）、`turnbuf.py`（打断即作废+水位内 commit）、`confgate.py`（置信度三段闸）、`judge.py`（System-One 判断器） | `tests/test_dialog_e2e.py` 五件闭环（9 例）；消费方=未来语音问答管线（T1 S2 ◐） | **◐ 部分**：五件控制面语义 ✅（72 例测试）；**TTS 合成能力面 ○**（TtsRouter 只有路由/降级语义，无合成后端）；turnpolicy×GenerationGate 未组合（→R1） |
| **⑤ 研究资产层** | 调研语料、评测基准、隔离/复现区——支撑"来源诚实"纪律的可复验资产 | 主库侧：`corpus/venue_expansion/`（38 venue 全量语料+精炼工作集）、`scripts/`（crawl_*/query_corpus/eval_whistle 等采集检索工具链）、`docs/research/`（76 份调研报告，INDEX 机械计数口径，v0.19.0 时点） | 隔离区 `AlwaysOnRec-ZCode/`（前沿增量独立可跑，279 项测试实跑核对）；复现区 `Repro-ZCode/`（六来源复现：BS.1770/FxLms ANC/头部朝向/PhaseCoder/Pipecat 帧管道/unique_lock，71 项 pytest 实跑核对）；AASR-Bench 917 例 refiner 评测 | **✅ 完整**（T1 S4 ✅；38 venue / 120,234 行全量落库 + 934 行强命中工作集） |

**盘点结论**：五层中 ①②⑤ 完整，③④ 各有一个明确缺口（KWS 真音频触发 / TTS 合成后端）——两个缺口都不在 laos 语义层内部，而在驱动与外部能力面；这正是"内核语义层零依赖、重依赖只进驱动子进程"分层（ADR-1）的预期代价形态：缺口以"语义已备、引擎待接"的方式存在。

---

## §2 接口契约审计

> 契约实取自源码：`drivers/drv_ear.py` 文件头与通道实现、`laos/dialogsched.py`/`laos/wakegate.py` 构造签名、`laos/kernel.py` AuditLog。稳定性三档：**稳**（有测试钉住+文档化，改动需过测试）/ **演化中**（已实现但预期会变）/ **未冻结**（无版本化承诺，下游引用需自担）。

### 2.1 三通道 ASR env 契约（drivers/drv_ear.py）

| 契约 | 内容 | 稳定性 |
|---|---|---|
| `LAOS_ASR_CHANNEL` | 通道选择：`funasr`（默认，本机 SenseVoiceSmall+fsmn-vad，需 conda python+模型）/ `server`（HTTP）/ `whistle`（cactus CLI 子进程）；未知值报 `EINVAL`（drv_ear.py `ValueError(f"EINVAL: unknown LAOS_ASR_CHANNEL …")`） | **演化中**（funasr/server 已文档化进 README §九并被测试消费；whistle 通道 2026-10-06 新入，出错语义刚定型） |
| `LAOS_SENSEVOICE_MODEL` / `LAOS_SENSEVOICE_VAD` | funasr 通道模型路径（README §九） | **稳** |
| `LAOS_ASR_SERVER` | server 通道端点，默认 `http://127.0.0.1:8000`，POST `/v1/transcribe`（stdlib urllib 手拼 multipart）——零依赖兜底，任何解释器可跑 | **稳**（端点+协议双默认值钉住） |
| `LAOS_WHISTLE_BIN` / `LAOS_WHISTLE_MODEL` / `LAOS_WHISTLE_CMD` | whistle 通道 needle 引擎与命令模板（默认 `cactus transcribe Cactus-Compute/whistle --file {wav} --language {lang}`）；引擎缺失只在该通道真用到时报 `ENOENT`（which 探测，不预加载） | **演化中**（引擎探测语义已测，命令模板允许自定义=接口面仍开放） |
| `LAOS_EAR_PYTHON` | 听觉双驱动（drv_ear/drv_mic）解释器；未设置时自动探测本机 conda python，再退回主解释器（此时仅 server 通道/status 可用） | **稳**（README §九文档化；探测失败路径有报错指引） |
| **统一出口** | `ear.transcribe` → 统一 JSON `{"text","language","emotions","source","latency_ms"}`；`ear.status` → 通道/模型路径/服务可达性/加载状态；重依赖（funasr/torch/soundfile/needle）全部惰性导入，裸解释器必须能 import 并回答 status | **稳**（三通道同构出口是下游消费的唯一契约；test_ear_mic 12 例+test_ear_whistle 10 例+test_ear_refine 4 例钉住） |

### 2.2 对话控制面注入点契约（laos/dialogsched.py / laos/wakegate.py）

| 契约 | 内容 | 稳定性 |
|---|---|---|
| 可注入时钟 | `PauseWindow(clock=…)`、`DialogQueue(…, clock=…)`、`MicrophoneGate(…, clock=…)`（dialogsched.py）与 `WakeGate(clock=…)`（wakegate.py）全部接受 `Clock=time.monotonic` 注入——单线程决策核，I/O 由调用方驱动（上游 C++ 线程+条件变量的语义等价改写） | **稳**（全部超时/窗口类测试都依赖注入时钟；这是测试密度的结构前提） |
| `GenerationGate(on_interrupt=…)` 回调 | 构造时可注入打断回调；`interrupt()` 递增代数+触发回调，流式回调逐块核对代数，过期代宁可丢不可播 | **演化中**（回调位单一；与 turnpolicy 的接线（→R1）会扩展消费面） |
| `TtsBackendP` Protocol | TtsRouter 双后端（offline/online）以 Protocol 类型约束；降级规则=在线失败且一句未发才降级、句中不换声线 | **稳**（Protocol 形态稳定；注意这是路由契约，不是合成能力契约——合成后端 ○ →R3） |
| `MicrophoneGate` 半双工参数 | `post_tts_guard_ms: float = 400.0`（dialogsched.py 默认参数）——无 AEC 时播报期间+guard 锁麦克风 | **稳**（设计值有测试钉住；AEC 接入后语义将扩展为"就绪后放行 barge-in"，属未来演化） |
| `KnowledgeRetriever` JSONL 格式 | 兼容上游 knowledge JSONL 格式；UTF-8 符号 bigram、0.7/0.3 双向覆盖、子串=1.0、交集≥2 下限、阈值 0.58 | **稳**（上游真数据 fixture 前 6 条入测试，公式精查） |

### 2.3 审计事件流契约（laos/kernel.py AuditLog）

| 契约 | 内容 | 稳定性 |
|---|---|---|
| 写入机制 | `AuditLog.write()`：追加式 JSONL，逐条 `seq` 单调序号在 append 前盖章（==records 下标，防前端去重漂移），逐条 flush | **稳**（test_laos 31 例覆盖内核行为） |
| `event:"mic"` 双路径 | 每次 `mic.*`/录音 syscall 在审计里落一条 event:"mic"——**放行（kernel.py syscall 派发尾部）与被拒（`_deny` 路径）都写**；`LAOS_REC=0` 时返回 EACCES 仍留痕 | **稳**（隐私红线级契约，测试钉住；T3 埋点必须复用此通道语义，不开新后门） |
| `event:"jev"` 双路径 | 判断层同构红线：放行与拒绝双路径（kernel.py，仿 event:"mic"） | **稳** |
| 事件 schema 本体 | 行内字段无版本号、无统一 schema 声明（`{"t","event",…}` 自由字典） | **未冻结**（T3 埋点事件将挂在同一 JSONL 流上并引入分类学字段——schema 演化是本波既定动作，下游解析方需按"未知字段宽容"处理） |
| `audit_mode` | 默认 `'w'`（每次 laosd 启动重写，便于 demo 复现），生产应传 `'a'` 累积 | **演化中**（语义已文档化在构造 docstring；生产/演示双模式的默认值取向值得后续审视 →R10） |

**审计小结**：laos 对外的三类接口面里，**听觉 env 契约与审计红线契约已可用"引用方"标准依赖**（稳/演化中）；**审计事件 schema 未冻结**是诚实的现状——T3 埋点设计正是在这个未冻结面上做第一次系统性定型。

---

## §3 强项（带证据）

### 3.1 对话控制面语义复现的测试密度

- **单波次 72 例**：v0.17.0 voicenpu 复现波次新增 wakegate 12 + dialogsched 23 + knowledge 11 + speechchunk 17 + dialog_e2e 9 = **72 例**（各数 2026-10-07 逐模块实跑核对：`Ran 12/23/11/17/9 tests`；注：docs/research/2026-10-06-voicenpu-adoption.md §四记 speechchunk 为 16 例，系报告时点笔误，以实跑 17 为准）。
- **密度曲线**：501→573（v0.17.0，+72）→634（v0.18.0 venue 扩展，+61）→**691**（v0.19.0 语料复用，+57）——三波连增，全部"新增功能带新增测试"（CHANGELOG 各版段可查）。
- **占位**：控制面五件 72 例占主库 691 的 **10.4%**；其中 dialogsched 23 例覆盖打断代数/合并/窗口延长 200ms/latest-only/半双工/降级不换声线全语义面。
- **结构前提**：全部时间语义经可注入时钟测试（§2.2），无 sleep 依赖——测试 0.001s 级跑完（dialogsched 23 例 0.001s，实跑计时）。

### 3.2 Refiner 实测增益

AASR-Bench 917 例错误率 0.4571→0.3875（**-15.2%**）；端到端（TTS 口吃语音→funasr→refiner）CER 1.563→0.042。证据：docs/research/2026-10-06-agenticasr-adoption.md（含分动作消融表）+ tests/test_refiner.py 21 例（实跑核对）。

### 3.3 三通道 footprint 梯度

| 通道 | 依赖足迹 | 实测精度/性能 | 定位 |
|---|---|---|---|
| funasr/SenseVoice | 本机模型+conda 解释器（重） | en WER 2.7% / zh CER 0.0%（zh 主力） | 精度主力 |
| whistle via needle3 | 模型 16.9MB + 引擎 1.56MB（轻） | en WER 10.8%，ttft 651ms，~300 tok/s | 多语轻备（7 语，无中文） |
| server | 0（HTTP 客户端，纯 stdlib） | 取决于服务端 | 零依赖兜底（任何解释器） |

footprint 从"本机大模型"到"17MB 端侧"到"零依赖网络"形成完整梯度——单一环境故障（模型缺失/解释器不可用）不会同时打死三条通道（ADR-4）。

### 3.4 研究资产规模

- 语料：38 venue / **120,234 行**全量落库 + laos 三主线过滤命中 2,103 行 + **934 行强命中工作集**（audio-speech 771 / agent-os 49 / spatial-privacy 114）——docs/research/2026-10-06-venue-expansion-survey.md + 2026-10-07 波次 CHANGELOG。
- 调研库：docs/research/ 76 份报告（INDEX 机械计数，v0.19.0 时点；主报告 33 份）。
- 评测资产：AASR-Bench 917 例；隔离区 279 项（实跑 OK skipped=8）+ 复现区 71 项（pytest 实跑 71 passed）独立可跑。

### 3.5 治理红线的工程化落地（不是口号，是代码）

- `event:"mic"` 放行+被拒双路径写审计（kernel.py 两处 write 点）；
- `LAOS_REC=0` 全局禁录返回 EACCES 且留痕；
- 审计 `seq` 单调盖章防前端去重漂移（AuditLog.write 注释即设计依据）；
- 强制层 OSAL 三后端（linux/android/stub）+ Termux 降级矩阵一键实测脚本。

---

## §4 风险与债务表（编号冻结：R1–R11）

> 本表是 Task 3《埋点设计》发射点覆盖面的技术源头：每条风险对应的故障面应在埋点事件中有观测位（直接发射或预留）。后续新增条目顺延 R12+，不得复用已冻结编号。与 T1 §6 问题域（P01–P15）的关联在"影响面"列标注。

| 编号 | 风险 | 证据指针（仓库内） | 影响面 | 缓解建议 |
|---|---|---|---|---|
| **R1** | **turnpolicy 与 GenerationGate 未组合**：turnpolicy 决定"何时打断"（speak/hold/stop 三态），GenerationGate 保证"打断后陈旧产出不外泄"——两者正交但无组合测试与接线，P05 打断失效的候选成因之一 | docs/research/2026-10-06-voicenpu-adoption.md §五（"两者正交可组合"结论本身即承认未组合）；tests/test_turnpolicy.py（15 例）与 tests/test_dialogsched.py（23 例）各自独立，test_dialog_e2e.py 9 例未引入 turnpolicy | 对话控制面；P05 | 增加 turnpolicy→`GenerationGate.on_interrupt` 接线 + 组合集成测试；埋点在打断路径记录代数与发起方 |
| **R2** | **KWS 未实测**：sherpa-onnx zipformer 3.3M 模型与"小乐"拼音词表（`x iǎo l è @小乐`）已从上游拿到，但驱动子进程模式未跑——真音频唤醒链路（语音问答第一环）无实测 | docs/research/2026-10-06-voicenpu-adoption.md §六#1；tests/test_wakegate.py 12 例全部走注入 `wake()`（无音频路径） | 听觉栈+对话控制面；P01/P02 | 驱动子进程接 sherpa-onnx（Windows 官方库）；负样本生成器接入前先落误唤醒计数埋点 |
| **R3** | **TTS 能力面缺失**：laos 无合成后端，TtsRouter 只有路由/降级语义；豆包协议帧编解码（帧头 0x11141000 事件码族）已记录但无 API key 未实测——S2 语音问答只能降级形态（文字输出）上线 | docs/research/2026-10-06-voicenpu-adoption.md §三（复现分层裁决）/§六#2；laos/dialogsched.py TtsRouter（Protocol 无实现）；T1 §5 G6 NO-GO | S2 场景闭环；P07 | 豆包协议驱动（待 key）或系统 TTS 通道先行；降级路径埋点先落（P07 观测位与合成能力解耦） |
| **R4** | **AEC 未接入对话链路致半双工**：上游 barge-in 仅 AEC ready 后启用（AEC3 收敛门槛=100 活跃渲染帧+50 稳定捕获帧）；laos 对话链路按无 AEC 设计——MicrophoneGate `post_tts_guard_ms=400.0` 播报期间锁麦。注意：drv_audio 有组件级 JAEC AEC（GPU 基准实测），缺的是与对话控制面的链路级接线 | laos/dialogsched.py:263（`post_tts_guard_ms: float = 400.0`）；docs/research/2026-10-06-voicenpu-adoption.md §二（音频合同 16k 采/48k 放/40ms 参考延迟）；drv_audio.py（JAEC AEC 存在但独立于对话调度） | 抢话体验与全双工代差；P05 | 把 drv_audio AEC 就绪信号接入 MicrophoneGate（收敛门槛语义照上游）；埋点记录 guard 触发/释放与 AEC 就绪态 |
| **R5** | **refiner 子句级替换局限**：规则版 refiner 只做子句级替换型纠正（"发邮件给张三，不对，我是说李四"），对非替换型错误无能为力——线上若误期"通用纠错"会产生错误信任 | docs/research/2026-10-06-agenticasr-adoption.md（"已知局限（即论文卖点）：子句级替换型"+分动作消融表 replace 类仅 2 例） | 听觉栈输出质量预期；P03 | 埋点记录 refine 前后文本哈希与替换命中计数（内容脱敏），使线上替换率可观测；LLM 版 refiner 后置 |
| **R6** | **QNN 真机链路未复测**：真机 QNN LPAI 推理（LAOS_NPU_ENDPOINT 经 adb forward 指向真机 App InferenceServer）2026-09 曾闭环，此后无回归复测；当前测试只覆盖 laos 侧传输层（本地 HTTP stub），真机设备位无 CI 可达用例 | drivers/drv_npu.py 文件头（路线 A 语义）；tests/test_npu_driver.py（10 例，TestDeviceTransport 用 127.0.0.1 本地桩）；docs/research/qnn-real-device-runbook.md | NPU 能力宣称与实际链路可能漂移；P08 | 真机 runbook 复跑一次并记录 SDK/设备版本；埋点在 npu.infer 记录端点可达性与延迟分位 |
| **R7** | **Crossref/DBLP 外源依赖**：语料增量更新依赖 Anthology bib dump+Crossref ISSN 模糊召回双主通道（36/38 venue）；DBLP/OpenReview 实测 JS 反爬、PMLR 无 DOI；TUN 断窗需退避+断点续抓——采集链路对外源可用性敏感 | docs/research/2026-10-06-venue-expansion-survey.md（数据源结构性结论节）；scripts/crawl_icassp_crossref.py 等；tests/test_fetch_crossref.py 25 例为离线 fixture（不防外源漂移） | 研究资产层可复现性（非运行时风险）；语料增量断供 | 采集结果带源+时间戳版本化入档；断窗重试脚本已有（var/ 侧），增加采集成功/失败事件记录 |
| **R8** | **三棵树同步漂移**：版本同步靠 scripts/release.py `VERSION_FILES`（主库 + AlwaysOnRec-ZCode + AlwaysOnRec-Trae 三处 `__version__`）+ 文档锚点自动改写；手工改动任一处或 release.py 失跑即漂移——文档宣称与实际行为不符会放大一切问题报告的不可信（T1 A2） | scripts/release.py:37-41（VERSION_FILES）；AGENTS.md 发版纪律节（"漏掉任何一步都算发版事故"——纪律的存在本身即风险曾发生的证据） | 全仓口径可信度；发版事故面 | 保持 release.py --apply 硬闸（不绿拒绝发版）；发版后加一步三树版本 diff 断言 |
| **R9** | **测试口径双轨（本评审实跑新发现）**：主库 4 个测试文件为 pytest 风格模块级函数——test_locks（7 函数）/test_loudness（10）/test_micgeom（6）/test_turnbuf（8）共 **31 个测试**，`python -m unittest tests.test_X` 报 "Ran 0 tests / NO TESTS RAN"，**不在 691 口径内**（pytest 下 31 passed，2026-10-07 实跑）；复现区 Repro-ZCode 71 例同为 pytest-only（unittest discover 0）。README"691 实跑"口径成立，但总测试资产实际 >1041 未在页脚体现，且只跑 unittest 的 CI 会静默漏跑 31 例 | 本评审 §5 实跑记录（逐模块 Ran 行）；tests/test_locks.py 文件头（`import pytest`+裸函数）；AGENTS.md 测试口径节（README 写实跑数的纪律） | 测试资产错账；locks/loudness/micgeom/turnbuf 四模块对 unittest 口径"不可见" | 二选一：将 4 文件包成 unittest.TestCase（并入 691 口径，页脚随之+31），或 README 显式声明双 runner 口径；复现区在页脚注明 pytest |
| **R10** | **长时运行无界增长**：审计与记忆 JSONL 追加式无界（AuditLog 默认 mode='w' 每次启动重写、生产 'a' 累积；memory.jsonl 无 TTL/水位治理）；无 RSS 采样——常开 7×24 场景（T1 A3）的慢泄漏直到用户侧爆发才可见 | laos/kernel.py AuditLog（mode 语义+records 全量驻留内存）；laos/memory.py（JSONL 存储）；T1 §6 P10/P11 | 常开形态稳定性；P10/P11 | 埋点先落 RSS 采样与 JSONL 行数/字节水位事件（T3 P 类）；治理策略（轮转/上限）后置 |
| **R11** | **听觉重依赖解释器探测链脆弱**：drv_ear/drv_mic 依赖"自动探测本机 conda python"（LAOS_EAR_PYTHON 可覆盖），探测失败时静默降级为"仅 server 通道/status 可用"——机器环境变化（conda 迁移/多环境）会以能力悄悄变窄的形式表现，而非显式报错 | drivers/drv_ear.py:112 附近（"set LAOS_ASR_CHANNEL=server or run drv_ear under conda python"指引）；README §九 LAOS_EAR_PYTHON 行 | 听觉栈可用性；P08 | 埋点在驱动加载时记录解释器探测结果与通道可用集（T3 L 类 driver.load）；探测失败升格为面板可见状态 |

**风险表小结**：11 条中 R1–R5 属对话/听觉能力面（语义已备、引擎或接线待补），R6–R7 属外部依赖面，R8–R9 属仓库工程纪律面，R10–R11 属运行可观测面。**除 R9 为本评审新发现外，其余与 T1 §7 风险清单交叉印证**；R9/R10/R11 三条直接构成 Task 3 埋点（L/P 类事件、RSS 采样、driver.load 事件）的技术动因。

---

## §5 测试覆盖评估

### 5.1 主库逐模块测试数表（2026-10-07 逐文件实跑，`python -m unittest tests.test_X` 取 "Ran N tests"）

| 测试模块 | N | 测试模块 | N | 测试模块 | N |
|---|---|---|---|---|---|
| test_laos（内核） | 31 | test_fetch_crossref | 25 | test_ear_mic | 12¹ |
| test_dialogsched | 23 | test_wer | 22 | test_vadmetrics | 12 |
| test_curate_strong_hits | 37 | test_laosweb | 20 | test_ear_whistle | 10 |
| test_multivenue | 30 | test_memory | 20 | test_npu_driver | 10 |
| test_query_corpus | 20 | test_screen | 18 | test_ipc | 13 |
| test_judge | 17 | test_calibrate_judge | 16 | test_binaural | 8 |
| test_release | 17 | test_risk | 16 | test_foa | 9 |
| test_refiner | 21 | test_filter_laos_relevant | 16 | test_seccomp | 9² |
| test_speechchunk | 17 | test_turnpolicy | 15 | test_dialog_e2e | 9 |
| test_fetch_anthology | 14 | test_jev_skills | 8 | test_enforcement | 6 |
| test_stale | 10 | test_scope | 8 | test_agentprof | 6 |
| test_apps | 7 | test_diary | 7 | test_validate | 6 |
| test_duplex | 11 | test_vad | 7 | test_venue_registry | 6 |
| test_knowledge | 11 | test_mcp2 | 7 | test_jev_mem_ctx | 6 |
| test_wakegate | 12 | test_confgate | 12 | test_skills | 6 |
| test_battery / test_cow / test_genie / test_notify / test_profiling³ / test_jev_gate / test_relbudget / test_scheduler / test_rec / test_mood / test_journal / test_events / test_context / test_capability / test_ear_refine / test_audio_driver / test_irreversibility / test_sandbox | 各5/4/3/2 | | | | |
| test_locks / test_loudness / test_micgeom / test_turnbuf | **0**⁴ | | | | |

¹ skipped=2；² skipped=2；³ skipped=1（全套 skipped=5 与 discover 一致）；⁴ pytest 风格 31 函数在 pytest 下全过（→R9）。

**合计 691**：表列全 67 个测试文件（含 4 个 unittest 口径 0 例文件，→R9 双轨口径：691 为 unittest 正口径，31 例 pytest 风格不在其内），逐模块求和=discover 实跑 "Ran 691 tests in 75.1s / OK (skipped=5)"，两口径互证。分区：AlwaysOnRec-ZCode 隔离区 discover 实跑 **279**（OK skipped=8）；Repro-ZCode 复现区 pytest 实跑 **71 passed**——页脚 1041 口径成立（R9 的 31 例除外）。

### 5.2 盲区清单（按"测不到的路径"归类）

| 盲区 | 现状 | 关联 |
|---|---|---|
| **drivers 真机链路** | KWS 音频触发未跑（R2）；QNN 真机设备位只有本地 HTTP 桩（R6）；ALSA/USB 自愈语义（上游 ENODEV close+200ms 重开、EPIPE recover）仅入档未实现更未测；drv_audio 分离/AEC 有 GPU 基准但无对话链路级用例（R4） | P01/P08/P09 |
| **并发路径** | dialogsched/wakegate 是可注入时钟的单线程决策核（设计选择，I/O 由调用方驱动）——**调用方并发驱动决策核的竞态无测试**；AuditLog 的 "GIL 下 len+append 足够原子"是注释论证非测试论证；多 Agent 并发 syscall 派发靠 asyncio.Lock（kernel.py），压力路径无测试 | P10/P15 |
| **长时运行** | 无 soak/耐久测试：JSONL 无界增长（R10）、内存驻留（AuditLog.records 全量在内存）、时钟漂移对窗口判定的影响——全部零覆盖；上游对照常驻 1951MB，laos 侧常驻内存未实测 | P10/P11 |
| **跨模块组合** | turnpolicy×GenerationGate（R1）；speechchunk×TTSRouter 只有 e2e 9 例的组合面；refiner×whistle 通道组合（whistle 无中文，实际仅 funasr 组合被测） | P03/P05 |
| **测试口径双轨** | 31 个 pytest 函数在 unittest 口径不可见（R9，本评审新发现） | R9 |

### 5.3 覆盖评估结论

主库覆盖呈"**内核与控制面语义密、驱动真机与运行时稀**"的形态——这与分层设计一致（语义层零依赖可测、重依赖在驱动子进程难测），但盲区清单即上线后故障的高发区：**§5.2 五类盲区与 §4 风险表、T1 §6 问题域三者高度重叠，共同指向观测面缺位**（→§8 可观测性评分、→Task 3）。

---

## §6 性能数据汇总

### 6.1 已实测数字（全部可溯源）

| 维度 | 数字 | 来源 |
|---|---|---|
| ASR funasr 精度 | en WER 2.7% / zh CER 0.0%（zh 主力） | 事实基线（计划文档）；docs/research 耳-记忆波次实测 |
| ASR whistle 精度 | en WER 10.8% | docs/research/2026-10-06-cactus-whistle-adoption.md（实测） |
| ASR whistle 流式 | ttft 651ms，~300 tok/s；模型 16.9MB+引擎 1.56MB | 同上 |
| Refiner 精度 | AASR-Bench 917 例错误率 0.4571→0.3875（-15.2%）；e2e（TTS 口吃语音）CER 1.563→0.042 | docs/research/2026-10-06-agenticasr-adoption.md |
| 判断层 | edgejev 端侧 median **157.5ms**（README 宣称 15.6ms 被实测否证） | scripts/bench_jev_local.py 实测（来源诚实纪律案例） |
| 语音增强 GPU | FLASepformer RTX 4060 CPU vs GPU 6.4x→9.3x（30s 音频 1.99s，验证线性复杂度） | scripts/flasep_gpu_bench.py；PROJECT_OVERVIEW 实测亮点 |
| SenseVoice 吞吐 | GPU RTF≈0.01 | PROJECT_OVERVIEW 五大能力版图④（实测口径） |
| 上游对照锚点 | voicenpu RK3576：端到端首音 1.44s / 常驻 1951MB / ASR 端点→终稿 ~88ms / metrics 22 字段 | docs/research/2026-10-06-voicenpu-adoption.md §二（对照用，非 laos 数字） |
| 测试吞吐 | 主库全套 691 例 75.1s（discover 实跑，2026-10-07） | 本评审 §5 实跑 |

### 6.2 未实测维度清单（如实声明，禁止引用宣称值充数）

- 端到端首音（对照上游 1.44s）——laos 侧全线未实测；
- ASR 端点→终稿延迟（对照上游 ~88ms）；funasr 通道 ttft（非流式）；
- KWS 唤醒触发延迟与漏/误唤醒率（R2：链路本身未跑）；
- refiner 修正延迟（现有口径只有精度）；知识库检索 retrieval_ms；
- LLM 首 token（laos 无常驻 LLM 通道）；TTS 首音（能力面缺失 R3）；
- laos 进程常驻内存（对照上游 1951MB）；长时运行 RSS 曲线（R10）；
- laos 侧功耗（仅有业界阶梯的定性结论：通用 Linux 设备空闲即 400–1000 mW，docs/research/always-on-recording/hardware-power.md）。

**结论**：laos 的实测集中在**精度与离线基准**（WER/CER/refiner/GPU 加速比），**在线分段延迟与资源占用几乎全空**——§6.2 每一行都对应 T3 埋点的一个必采字段族（延迟分位/内存采样），这是埋点设计性能面的直接需求清单。

---

## §7 技术决策记录（ADR ×5）

**ADR-1 零依赖：laos/ 核心纯 stdlib**
- **决策**：`laos/` 包零第三方依赖；重依赖（funasr/torch/sounddevice/needle/numpy）只进 drivers/ 子进程，惰性导入，裸解释器必须能 import 并回答 status。
- **动因**：①可移植——Windows/macOS 自动降级仍可跑语义层与 server 通道；②审计面最小化——治理内核自身不引入供应链面；③测试秒级（dialogsched 23 例 0.001s）；④conda 红线（重依赖不污染主解释器环境）。
- **代价**：性能上限受纯 Python 约束（VAD 的 audioop 兜底即为此设计）；numpy 级计算只能放驱动或隔离区。
- **状态**：有效；AGENTS.md 红线级纪律。

**ADR-2 规则版 refiner 先行**
- **决策**：refiner 首版用规则（子句级替换），不做 LLM 纠错。
- **动因**：①零依赖红线下唯一可进主库的形态；②可解释可离线评测（AASR-Bench 917 例直接量化：-15.2%）；③生效路径确定（无幻觉放大风险——规则错也是可枚举的错）。
- **代价**：覆盖面窄（仅替换型，R5）。
- **状态**：有效；LLM 版 refiner 作为后续选项（需 LLM 通道，laos 当前无常驻通道）。

**ADR-3 语义复现不拷贝（voicenpu AGPL 隔离）**
- **决策**：对 AGPL-3.0 上游 voicenpu_engine 做语义级独立实现——读源码理解算法与协议语义后用 Python 重写，零代码拷贝；测试 fixture 摘录上游数据前 6 条并注明来源。
- **动因**：①许可合规（AGPL 传染性）；②适配 laos 架构——上游 C++ 线程+条件变量改为可注入时钟的单线程决策核（语义等价、I/O 调用方驱动），直接获得可测性（§3.1 的 72 例密度是此决策的直接回报）。
- **代价**：复现成本高于移植；语义等价性靠测试钉（12+23+11+17+9 例）。
- **状态**：有效；同样模式适用于后续上游采纳（jev/whistle 等波次已沿用）。

**ADR-4 三通道 ASR**
- **决策**：funasr（zh 精度主力）+ server（HTTP 零依赖兜底）+ whistle（16.9MB 多语轻备）三通道并存，`LAOS_ASR_CHANNEL` 切换，统一 JSON 出口。
- **动因**：①单通道锁死风险——模型文件缺失/解释器不可用/语言覆盖三种故障形态不同（footprint 梯度 §3.3）；②server 通道保证裸解释器形态（Windows/macOS 降级）听力不全瘫；③上游 RKNN 通道不可复现（aarch64 NPU-only），三通道是替身策略。
- **代价**：三份通道维护面；通道误切本身成为新故障模式（→P03，埋点需记 per-channel 观测）。
- **状态**：有效。

**ADR-5 KWS 延后**
- **决策**：v0.17.0 只复现 WakeGate 会话语义（可注入测试），KWS 引擎（sherpa-onnx 子进程）延后到驱动波次；模型与词表先取档。
- **动因**：①分层解耦——控制面语义不依赖具体 KWS 引擎（引擎是驱动层可替换件）；②隐私红线先行——"唤醒只由端侧音频触发、文本永不唤醒"是语义约束，先钉进状态机测试（12 例）比先跑通引擎更关键；③KWS 实测需要驱动子进程基础设施（LAOS_EAR_PYTHON 探测链）成熟。
- **代价**：真音频唤醒链路空窗（R2，P01/P02）；隔离区 DTW 模板私有唤醒词作为研究资产先行。
- **状态**：有效；Should 项 S1（T1 §3）为到期信号。

---

## §8 评审结论（分维度就绪度）

> 就绪度评分（5 分制，判据=语义完备度×测试证据×实测覆盖×线上观测面四要素）；与 T1 §5 Go/No-Go 交叉一致，沿用其 NO-GO 限定口径。

| 维度 | 评分 | 判据摘要 |
|---|---|---|
| **对话控制面** | **4.0 / 5** | 五件语义完备（wakegate/dialogsched/knowledge/speechchunk/e2e 共 72 例，§3.1）；扣分：turnpolicy×GenerationGate 未组合（R1）、TTS 路由无合成后端可路由（R3）、无真音频端到端 |
| **听觉栈** | **3.5 / 5** | 三通道+VAD+refiner 均实测（§3.2/3.3，funasr zh CER 0.0% / refiner -15.2%）；扣分：KWS 未实测（R2）、AEC 未接对话链路致半双工（R4）、refiner 覆盖面窄（R5） |
| **治理层** | **4.0 / 5** | 审计/强制/预算/分支语义齐备（test_laos 31+enforcement 6+seccomp 9+risk 16…），eBPF 内核真值+OTLP span；扣分：审计 schema 未冻结（§2.3）、JSONL 无界增长（R10） |
| **可观测性** | **1.5 / 5**（四维度最低） | 仅有 syscall 审计 JSONL（event:"mic"/"jev" 红线双路径是亮点）+ laosweb 面板；**无分段延迟、无降级/故障事件、无 RSS 采样、无 overrun/自愈计数**——§6.2 未实测清单与 §5.2 盲区清单的共同根因 |

**结论**：

1. **沿用 T1 判定口径**：以开发者自部署研究平台形态（S1/S3/S4），技术面满足上线；语音问答（S2）按降级形态上线（R2/R3 到位前不承诺完整体验）。
2. **可观测性是唯一系统性短板（对应 T1 G8 NO-GO 的技术侧论证）**：三个高分区（控制面/听觉/治理）的已测证据都是**离线测试与离线基准**，上线后从"测试绿"到"用户报告的问题可定位"之间没有任何观测面衔接——P01–P15 大半无数据可答。**§4 风险表（R1–R11）与 §6.2 未实测清单共同构成 Task 3 埋点设计的覆盖面需求**：埋点是当前架构下把三块长板（语义+测试+审计流）转化为线上诊断能力的最短路径。
3. **本评审新增的工程动作项**（不阻塞本波文档交付）：R9 测试口径统一（31 例并入或显式声明）、R8 三树版本 diff 断言、R10 JSONL 水位观测——三项均可与 laos/telemetry.py 实现波次合并落地。

---

### 附：本文引用来源

- 计划事实基线：docs/superpowers/plans/2026-10-07-review-instrumentation.md（数字唯一允许来源）
- T1 成品（交叉一致源）：docs/review/2026-10-07-requirements-review.md（§2 场景完成度、§5 Go/No-Go、§6 问题域 P01–P15）
- 源码实取：`ls laos/` + 各模块 docstring 首行；drivers/drv_ear.py、drivers/drv_mic.py、drivers/drv_npu.py 文件头；laos/kernel.py（AuditLog/event:"mic"）；laos/dialogsched.py（MicrophoneGate/TtsRouter/注入点）；laos/wakegate.py
- 实跑记录（2026-10-07）：主库逐模块 `-m unittest tests.test_X`（合计 691，skipped=5）；discover 全套 "Ran 691 tests in 75.1s"；AlwaysOnRec-ZCode discover 279（skipped=8）；Repro-ZCode pytest 71 passed；4 个 pytest 风格文件 pytest 31 passed
- README.md（§九 环境变量、目录速览、版本与发布）、docs/PROJECT_OVERVIEW.md（目录总览、五大能力版图、实测亮点）、CHANGELOG.md（v0.17.0/v0.18.0/v0.19.0 各波次测试增量）
- docs/research/2026-10-06-voicenpu-adoption.md（§二 上游全景、§五 对照、§六 后续建议）；2026-10-06-agenticasr-adoption.md（refiner 消融）；2026-10-06-cactus-whistle-adoption.md（whistle 实测）；2026-10-06-venue-expansion-survey.md（语料外源结论）；qnn-real-device-runbook.md
- scripts/release.py（VERSION_FILES 三棵树）；AGENTS.md（发版纪律/conda 红线/零依赖/测试口径四条持久纪律）
