# laos 需求评审（2026-10-18）

> **评审对象**：laos v0.39.0（主库 1180 项测试实跑通过，`unittest discover` = "Ran 1180 tests / OK (skipped=5)"，2026-10-18 当日实跑核对；另隔离区 AlwaysOnRec-ZCode 279 项 / 复现区 Repro-ZCode 94 项 / 对照树 AlwaysOnRec-Trae 276 项，均当日实跑核对）。
> **定位重申（叙事红线）**：基座是 Linux 内核，Agent 是内核之上的新负载（与进程同类）；laos 是内核治理在用户态的延伸，不是"给 AI Agent 装上操作系统"。laosd 是架在 Linux kernel 之上的薄内核（语义层），所有特权操作最终仍由 Linux 执行，laosd 只负责"允许不允许、记不记"。
> **数字口径**：本文全部数字取自 2026-10-18 当日实跑（测试计数、模块数、驱动数）或仓库既有实测记录（CHANGELOG 各版段、调研报告、复现区记录）；未实测维度一律明写"未实测"，不引入外部宣称值。
> **本文角色**：对《需求评审 v0.19.0》（docs/review/2026-10-07-requirements-review.md）的现行版刷新——该文是 v0.19.0 时点的上线前评审快照（编号 P01–P15 自其时冻结），本文沿用其编号体系并逐条更新状态，作为飞书文档评审会议的需求侧依据。

---

## §1 评审范围与三条产品线

### 1.1 laos 的三类目标形态（现状刷新）

| # | 形态 | 内容 | 服务对象 | 当前状态 |
|---|---|---|---|---|
| 1 | **Linux AgentOS 治理内核**（第一形态） | 用户态薄内核：进程表 / 能力表 / 九级 syscall 闸门链 / Sentinel 动作闸 / 不可逆预算 / 审计流，把 Agent 当新负载管起来 | 引用 laos 内核库的开发者 | **✅ 主体已成**（51 模块、17 驱动、1180 测试；对外品牌 nanoLAOS） |
| 2 | **端侧常开听觉研究平台**（听觉链路） | 四段漏斗（VAD 常驻检测 → 触发捕获 → 即时蒸馏 → 原音频即焚）+ 三通道 ASR + 生活日志双记忆（声景/节律）+ 录音回放 | 开发者本人 | **✅ 完整**（S1 场景四段全落地；KWS 真音频触发仍缺位，见 §3） |
| 3 | **对话控制面组件库** | wakegate / dialogsched / turnpolicy / knowledge / speechchunk / turnbuf / confgate / evroute / dialogflow 可复用组件（v0.17.0–v0.30.0 语义复现波次） | 组装语音对话系统的开发者 | **◐ 部分**：控制面语义 ✅（含 ARVIS 话轮路由三件）；**TTS 合成后端仍缺位**，端到端语音闭环未成 |

### 1.2 本评审口径下的"上线"定义

**第一场景 = 开发者自部署上线**：开发者在自己的机器（Linux 为完整形态；Windows/macOS 自动降级为"仅能力表 + server ASR 通道"）克隆仓库、跑通 1180 项测试、按 README 启动 `laosd` / `laosweb` / `journal` 管线并日常使用。

**明确非目标（不承诺）**：

- 无对外 SaaS 承诺：laos 不提供托管服务、无 SLA、不做云端默认上传（ASR 全本地是红线，见 §4.3）；
- 不做多租户（Won't，见 §3）；
- 不做面向终端消费者的合规认证——隐私按仓库既有红线纪律执行；
- 不修改 Linux 内核（用户态延伸，非新内核）。

---

## §2 用户画像与核心场景

**用户画像**：P1 自部署开发者（第一场景用户：在自己的机器上跑 laos 并日常使用治理/听觉/对话能力）；P2 Agent 治理研究者（引用能力表/审计/预算语义做多 Agent 实验）；P3 语音/语料研究者（消费调研语料与评测工具链）。

### 2.1 核心场景表（用户动作 → 系统行为 → 完成度）

| 场景 | 用户动作 → 系统行为 | 完成度 |
|---|---|---|
| **S1 常开录音日记** | 开发者显式触发录音 syscall → StreamingVAD 门控（仅"有没有人声"一比特，静音不落盘）→ 捕获有人声片段 → funasr/SenseVoice 转写+情感 → journal 入库（mem.remember）→ 声景/节律特征（v0.37.0）→ diary/mood_report 聚合 → rec_gc 6 小时即焚原音频 | **✅ 完整**（漏斗四段全落地，真录音/真 ASR 用例实测；说话人分离缺位为增强项，不阻塞） |
| **S2 语音问答**（唤醒→识别→知识库/LLM→TTS） | 说唤醒词 → WakeGate 四态会话（文本永不唤醒）→ 三通道 ASR 识别 → knowledge bigram 短路（阈值 0.58）或 LLM 流式（v0.31.0 llm.py + laosweb 对话面）→ speechchunk 切句清洗 → 前端浏览器 speechSynthesis 朗读（v0.33.0）或 TtsRouter 降级；抢话时 generation 版本化打断，播报中附和词吞掉/真打断让位（v0.30.0 ARVIS 三件） | **◐ 部分**：会话机 ✅、三通道 ASR ✅、知识库短路 ✅、LLM 通道 ✅、打断+话轮路由 ✅、**KWS 真音频触发 ○**（WakeGate 模块级测试全走注入）、**laos 侧 TTS 合成后端 ○**（仅前端浏览器 speechSynthesis 与路由降级语义）——端到端闭环未成 |
| **S3 Agent 治理审计** | 起 Agent 干活 → 每次 tool call = 一条带 errno 的 syscall 审计（含被拒路径）→ laosctl ps/trace/denied/budget/spans/traceviz 回放；eBPF 内核真值 + AgentProf 语义 span + telemetry 23 事件埋点（v0.21.0） | **✅ 完整**（审计流 + 内核真值 + 语义剖析 + 埋点四层齐备） |
| **S4 语料研究** | 检索/评测 → 19,792 篇双会议论文 + 3,724 OSS 仓库普查 + 38 venue 120,234 行语料（934 行强命中工作集）+ 116 份调研文档（capstone 采纳总账）+ AASR-Bench 917 例 refiner 评测 + WER 工具链 | **✅ 完整**（语料资产 + 评测管线可用） |
| **S5 治理面板人审**（新增，v0.28.0–v0.29.0） | laosweb v3 mobile-first 面板：审批卡四钮（拒绝/一次/本会话/总是）+ 污点 pids + grants 逐条撤销 + mode 三选一；60s 未审批按拒绝 | **✅ 完整**（Sentinel 六级闸 + GrantStore + TaintTracker + 前端投影全链） |

### 2.2 场景支撑能力完成度分解（与仓库实际一致）

| 能力 | 完成度 | 依据 |
|---|---|---|
| 九级 syscall 闸门链 | ✅ | `laos/kernel.py:514` syscall()；能力表/task_scope/pkg 作用域/预算/Sentinel/不可逆/派发审计 |
| Sentinel 动作闸 + 污点跟踪 | ✅ | `laos/sentinel.py` 六级有序判定 + GrantStore（once/session/always）+ TaintTracker（唯一清除=进程退出）；26 例测试（v0.28.0） |
| 三通道 ASR | ✅ | funasr/SenseVoice（en WER 2.7% / zh CER 0.0%，zh 主力）；whistle via needle3（en WER 10.8%，ttft 651ms）；server（HTTP，零依赖兜底） |
| Refiner | ✅ | AASR-Bench 917 例错误率 0.4571→0.3875（-15.2%）；端到端 CER 1.563→0.042；已知局限=子句级替换型 |
| 唤醒会话机（WakeGate） | ✅ 模块级 | `laos/wakegate.py` 四态（follow-up 12s / 会话 120s / 6 轮）+ 附和词白名单（v0.30.0）；**无 KWS 真音频触发** |
| 打断与话轮路由 | ✅ | dialogsched generation 版本化 + turnpolicy speak/hold/stop + ARVIS 附和吞掉/语义路由/播报时窗（27 例，v0.30.0） |
| LLM 通道 | ✅ | `laos/llm.py` OpenAI 兼容最小封装（纯 stdlib urllib 非流式；缺省优雅降级）+ laosweb 对话面 + 记忆注入（v0.31.0/v0.32.0） |
| TTS 合成能力面 | ○ | laos 侧仍无合成后端；前端 speechSynthesis 朗读开关（v0.33.0，本地不出网）+ TtsRouter 降级语义（句中不换声线）已备 |
| 录音回放 | ✅ | `rec.replay` 内建 syscall（跨驱动同步组装）+ 环形缓冲（30s 默认，clamp 5..120s）+ laosweb 回放卡 + 摘要扩展位（v0.36.0/v0.38.0） |
| 生活日志双记忆 | ✅ | `laos/soundscape.py` 频域声景 + `laos/rhythm.py` 时域节律（v0.37.0）；零新增常驻内存 |
| 埋点可观测 | ✅ | `laos/telemetry.py` 23 事件注册表（脱敏四级、5s 节流、64MB 轮转、LAOS_REC=0 联动静默）——v0.20.0 评审时 G8 NO-GO 项已补齐 |
| 审计与禁录 | ✅ | 每次 syscall 带 errno 审计；录音成功**与被拒**均写 `event:"mic"`；`LAOS_REC=0` 全局禁录返回 EACCES |
| 语音桥（安卓壳） | ✅ | 原生 VoiceBridge.kt（PCM16 内存即焚）+ PWA 兜底（v0.33.0） |

---

## §3 功能需求清单（MoSCoW）

### Must（第一场景上线即必须有；缺任一则"开发者自部署"不成立）

| # | 需求 | 现状 |
|---|---|---|
| M1 | 三通道 ASR（funasr zh 主力 / server 零依赖兜底 / whistle 轻量多语备） | ✅ 已达标 |
| M2 | 唤醒会话（WakeGate 四态 + 附和词白名单；唤醒只由端侧音频触发，文本永不唤醒） | ✅ 已达标（模块级） |
| M3 | 打断与话轮路由（generation 版本化；附和吞掉/真打断让位；播报时窗） | ✅ 已达标 |
| M4 | 审计（每次 tool call = 带 errno 的 syscall 审计；录音事件 `event:"mic"` 双路径） | ✅ 已达标 |
| M5 | 禁录开关（`LAOS_REC=0` 全局禁录，返回 EACCES） | ✅ 已达标 |
| M6 | 治理面板人审（Sentinel 六级闸 + 审批卡 + scoped grants + 污点跟踪） | ✅ 已达标（v0.28.0–v0.29.0 落地） |
| M7 | 埋点可观测（23 事件、脱敏四级、轮转与静默联动） | ✅ 已达标（v0.21.0 落地，v0.22.0 终审修复） |

### Should（上线后近期应补；不阻塞第一场景，但决定语音问答体验完整性）

| # | 需求 | 现状 |
|---|---|---|
| S1 | KWS 实测落地（模型与词表已拿到，驱动子进程模式待跑） | ◐ |
| S2 | TTS 能力面（laos 侧合成后端；当前仅前端 speechSynthesis + 路由降级语义） | ◐（前端朗读已可用，合成后端未接） |
| S3 | 说话人分离（journal 现分不清"我说的/别人说的"——听觉链路最后一块明显缺口；PIPL 约束下用会话内到达顺序聚类替代声纹路线） | ○ |

### Could（竞争力增强，非门槛）

| # | 需求 | 说明 |
|---|---|---|
| C1 | AEC 全双工 | 现为半双工保护：播报期间 +400ms guard 锁麦克风（MicrophoneGate）；drv_audio 有组件级 JAEC AEC，缺对话链路级接线 |
| C2 | NPU SER 真机 | 语音情感模型调研已备（docs/research/2026-09-11-ser-model-landscape.md） |
| C3 | drv_screen 多轮真机验收 | 手机操控驱动（tap/text/dump/key 等）已有测试，长时真机跑机待排 |

### Won't（明确不做；本轮上线不承诺）

| # | 需求 | 理由 |
|---|---|---|
| W1 | 云端默认上传 | 隐私红线：ASR 全本地，录音只由显式 syscall 触发；任何上云仅显式 opt-in 且永不默认 |
| W2 | 多租户 / SaaS 化 | laos 无对外托管承诺（§1.2） |
| W3 | 修改 Linux 内核 | 定位红线：laos 是内核治理在用户态的延伸，强制力复用既有内核原语 |
| W4 | 声纹识别（speaker embedding） | PIPL：声纹=敏感个人信息，需单独同意；已否决，改会话内到达顺序聚类 |

---

## §4 非功能需求

### 4.1 延迟预算表（对照 voicenpu 上游 RK3576 实测；laos 未实测处如实标注）

| 链路段 | 上游 voicenpu（RK3576 实测，对照锚点） | laos v0.39.0 现状 |
|---|---|---|
| 唤醒触发（KWS→会话开） | sherpa-onnx zipformer 3.3M 在链路内 | **未实测**（KWS 模型/词表已拿到，真音频触发未跑，○） |
| ASR 端点→终稿 | ~88ms | **未实测** |
| ASR 流式首字 ttft | （流式 Zipformer RKNN，未单列） | whistle 通道 **651ms 实测**（~300 tok/s）；funasr 通道非流式 |
| ASR 精度（参考口径） | wenetspeech 3.3M transducer | funasr en WER 2.7% / zh CER 0.0%；whistle en WER 10.8%（实测） |
| Refiner 修正延迟 | — | **未实测**（现有口径为精度：错误率 -15.2%、e2e CER 1.563→0.042） |
| 知识库检索 | retrieval_ms 记入指标 | **未实测**（本地 JSONL bigram 检索） |
| LLM 首 token | RKLLM Qwen3-VL-2B w4a16 | **未实测**（llm.py 走 OpenAI 兼容端点，非流式） |
| TTS 首音 | 在线豆包 / 离线 MeloTTS | **laos 侧无此段**（前端 speechSynthesis 可用；合成后端 ○） |
| 端到端首音 | **1.44s** | **未实测** |
| 抢话保护 | AEC ready 后启用 barge-in；无 AEC 时播报期间+400ms 锁麦 | MicrophoneGate guard **400ms**（设计值）+ 附和词白名单离线路由（v0.30.0） |
| 判断层 | — | edgejev 端侧 **median 157.5ms 实测**（README 宣称 15.6ms 已被实测否证）；clef-flash WSL 实测 noul 33.8s / choice 32.8s / score 62.9s（18.1GB 权重，CPU 推理，非端侧候选） |
| 常驻内存 | 1951MB | **未实测** |

**结论**（沿用 v0.19.0 评审判定，至今仍成立）：laos 只有片段级实测（whistle ttft、jev median、WER/CER 精度、refiner 精度），**端到端延迟全线未实测**——"为什么慢/是否劣化"目前无数据可答。缓解面已从 v0.21.0 的 23 事件埋点部分覆盖（分段延迟/降级/故障事件有观测位），但真实数据要靠上线运行积累。

### 4.2 功耗预算（引 always-on-recording 调研口径）

"常开"是跨 4 个数量级的功耗阶梯（docs/research/always-on-recording/hardware-power.md）：

| 阶梯 | 量级 | 例证 |
|---|---|---|
| 定制 ASIC | 亚 µW（0.047–1 µW） | VAD ASIC 47 nW；AAD 门控 KWS 0.36–0.8 µW |
| 专用音频 NPU | 百 µW | Syntiant NDP120 always-on 140 µW |
| 手机传感中枢 / aDSP | 数 mW | 高通官方口径 Sensing Hub 全部处理 <1 mA；laos 真机目标 ADSP LPAI **<5 mW（≈0.62%/天）** |
| 通用 AP 常醒 | 数百 mW–瓦 | 跑通用 Linux 的机器**空闲即 400–1000 mW** |

**对第一场景的判定**（不变）：

1. **工程准入线**：常开能力 ≤25 mW（≈3%/天）；进入 100 mW 量级即一天吃掉 1/4 电，用户会立刻关掉。
2. **落盘比"听"贵 1–2 个数量级**（听 ≤25 mW vs 写 SD 17–70 mW）——四段漏斗"只存有声段"同时是最大的省电措施，不只是隐私设计。
3. **桌面/proot 形态的移动常开不成立**（Python 进程醒着就在数百 mW 量级）：第一场景的常开形态定位为**台式供电的研究平台**；移动常开走原生 App + ADSP 路线，不在本评审门槛内。

### 4.3 隐私合规（红线逐条）

| # | 红线 | 落法 |
|---|---|---|
| 1 | 录音只由显式 syscall 触发 | `drv_rec.rec_start` / App `/rec/*`；无后台静默录音路径 |
| 2 | `LAOS_REC=0` 全局禁录 | 返回 EACCES，一键关闭；telemetry `a.*` 同步静默、`f.rec.bypass` 永不静默 |
| 3 | ASR 全本地 | funasr/whistle 本机推理；server 通道默认 127.0.0.1 端点；上行音频只转写不落盘（/api/voice，v0.33.0） |
| 4 | 录音成功**与被拒**都写审计 | `event:"mic"`（放行/拒绝两路径） |
| 5 | 原音频即焚 | `rec_gc(keep_hours=6)`——即使前环被滥用，原始音频最多活 6 小时 |
| 6 | 标识信息脱敏 | `LAOS_PRIVACY_MASK=1`（主机名等） |
| 7 | 转写与摘要文本不入审计 | rec.replay 音频与转写永不入任何审计记录；摘要为衍生文本同样不入（v0.36.0/v0.38.0 测试钉死） |
| 8 | LLM/埋点内容脱敏 | event:'llm' 只记模型/耗时/成败/长度；telemetry 内容类只许 len/sha256 前 8 位/时长/语言码，禁止级字段拒发整条 |

---

## §5 上线门槛（Go/No-Go 清单）

| # | 门槛 | 现状态 | 判定 | 差距 |
|---|---|---|---|---|
| G1 | 主库测试全绿 | 1180 项实跑 OK（skipped=5）；另隔离区 279 / 复现区 94 / 对照树 276 | **GO** | — |
| G2 | 零依赖承诺 | `laos/` 核心纯 stdlib；重依赖只进驱动子进程惰性导入 | **GO** | — |
| G3 | 三通道 ASR 可用 | funasr zh 主力 + server 零依赖兜底 + whistle 轻备，均有实测 | **GO** | — |
| G4 | 唤醒会话语义 | WakeGate 四态 + 附和词白名单 + 全迁移路径测试 | **GO**（模块级） | 真音频唤醒链路未实测（KWS ○，Should S1） |
| G5 | 打断与话轮路由 | generation 版本化 + ARVIS 三件（27 例）+ dialog_e2e 闭环 | **GO** | — |
| G6 | TTS 能力面 | laos 侧 ○；前端 speechSynthesis 朗读可用 | **◐ PARTIAL** | laos 侧合成后端未接（Should S2）——语音问答按"文字+浏览器朗读"形态上线 |
| G7 | 审计与禁录 | `event:"mic"` + `LAOS_REC=0`，红线逐条满足（§4.3） | **GO** | — |
| G8 | 可观测性 | telemetry 23 事件 + laosweb 面板已落地（v0.21.0–v0.29.0） | **GO**（v0.19.0 时的 NO-GO 已消除） | 分段延迟真实数据待运行积累 |
| G9 | 治理面板人审 | Sentinel 六级闸 + 审批卡 + grants + 污点（v0.28.0–v0.29.0） | **GO** | — |
| G10 | 文档与发版流程 | README/PROJECT_OVERVIEW/release.py 全量自动同步（含 dated 排除，2026-10-18 加固）+ 交接门禁实跑对账 | **GO** | deck 正文旧锚点待下次重建（PPT 底稿已刷新） |

**综合判定**：以**开发者自部署研究平台 + Agent 治理内核**双形态（S1/S3/S4/S5 场景），laos **满足上线门槛，十项全 GO（G6 为限定口径 PARTIAL）**。**语音问答（S2）按"文字 + 浏览器朗读"形态上线**：KWS 实测与 laos 侧 TTS 合成到位前不承诺完整体验。对照 v0.19.0 评审：当期唯一系统性 NO-GO（G8 可观测性）与 G6 均已实质推进，剩余缺口集中在**驱动真机链路**（KWS/TTS/屏幕多轮验收），不在内核语义层内部。

---

## §6 上线后问题域清单（编号沿用冻结 P01–P15，状态更新）

> 编号自 v0.19.0 评审冻结，不得复用；状态列为 2026-10-18 核对。新增问题顺延 P16+（本版无新增冻结）。

| 编号 | 问题域 | 用户视角症状 | 2026-10-18 状态 |
|---|---|---|---|
| **P01** | 唤醒不灵 | 喊唤醒词没反应，会话开不起来 | **开放**（KWS 未实测治本；埋点 d.wake.state_change 已有观测位） |
| **P02** | 误唤醒 | 没叫它却自己醒（电视/他人对话触发） | **开放**（负样本生成器已备未接入；无事件记录误触发计数） |
| **P03** | ASR 误识别劣化 | 转写越来越错（专名错、方言错、CER 上升） | **部分缓解**（refiner 已落地 -15.2%；per-channel 精度靠埋点可观测；换版本回退仍靠纪律） |
| **P04** | 端到端延迟劣化 | 对话越来越卡、首音变慢 | **部分缓解**（埋点有分段观测位；真实曲线待运行积累；基线仍空） |
| **P05** | 打断失效（过期代播放） | 已经抢话了，它还在播旧回答 | **已关闭**（ARVIS 三件落地：附和/真打断路由 + generation 代数核对；27 例测试 + 事件可观测） |
| **P06** | 会话异常（超时/轮数提前睡） | 还在聊着呢它突然睡了 | **已关闭**（WakeGate 边界测试全覆盖 + d.wake.state_change 六迁移事件） |
| **P07** | TTS 降级频繁 | 声线突变/播报失败/降级到不说话 | **开放**（laos 侧合成未落地；前端 speechSynthesis 不受此限） |
| **P08** | 模型加载失败 | 启动报错或某通道静默不可用 | **部分缓解**（驱动 status 工具可查；LAOS_EAR_PYTHON 探测失败仍为静默降级） |
| **P09** | 音频设备断连 | 麦克风/声卡拔掉后链路死掉 | **开放**（上游自愈语义入档未实现） |
| **P10** | 内存增长 | 跑几天越来越胖直至 OOM | **部分缓解**（telemetry 64MB 轮转 + RSS 无采样；memory.jsonl 仍无 TTL/水位治理） |
| **P11** | 崩溃后恢复 | laosd/驱动子进程 crash 后状态不一致 | **部分缓解**（审计 gzip 轮转 + epoch/seq 跨代续写；无崩溃/恢复事件） |
| **P12** | 审计缺失 | 某次调用/录音查不到记录（红线级） | **已关闭**（AuditLog seq 单调盖章 + rotate() 异常保底 + mode='a' 跨 boot 代续） |
| **P13** | `LAOS_REC=0` 旁路 | 禁录开关下仍有录音行为（红线级） | **已关闭**（drv_mic 两条录音路径均加闸（v0.20.0）+ `f.rec.bypass` 哨兵事件） |
| **P14** | 投机取消风暴 | 回答变慢且 token 消耗异常 spike | **开放**（投机窗语义有测试；laos 未接 LLM 流式，指标未实现） |
| **P15** | 音频队列 overrun 风暴 | 识别断续、丢字 | **开放**（无 overrun 计数事件） |

**统计**：15 条中已关闭 4 条（P05/P06/P12/P13）、部分缓解 5 条、开放 6 条——开放项集中在**真机驱动链路与长时运行**两个域，与 §5 差距列一致。

---

## §7 需求评审结论

### 7.1 TOP5 风险（2026-10-18 版）

| # | 风险 | 依据 |
|---|---|---|
| R1 | **KWS 唤醒链路未实测**——语音问答第一环仍是断的 | §2.2：WakeGate 模块级 ✅ 但真音频触发未跑（→P01/P02） |
| R2 | **laos 侧 TTS 合成后端缺失**——语音问答闭环缺最后一环 | §2.2：TTS ○，S2 只能"文字+浏览器朗读"形态（→P07） |
| R3 | **端到端延迟基线全线未实测**——上线后无法回答"为什么慢/是否劣化" | §4.1：对照上游 1.44s 首音锚点，laos 侧无任何端到端数字（→P04，缓解面已从 v0.19.0 的"无观测位"改善为"有观测位无数据"） |
| R4 | **长时运行无界增长只缓解未治本**——memory.jsonl 无 TTL/水位；RSS 无采样 | §6 P10；telemetry 只封了埋点自己的轮转 |
| R5 | **真机驱动链路无回归**——KWS/QNN/音频设备断连三类真机路径零覆盖 | §6 P08/P09；测试全部在仿真层 |

### 7.2 TOP3 放大器（让风险变贵的机制）

| # | 放大器 | 作用机制 |
|---|---|---|
| A1 | **测试口径双轨** | 主库 4 个 pytest 风格测试文件（locks/loudness/micgeom/turnbuf）在 unittest discover 口径不可见——只跑 unittest 的 CI 会静默漏跑（v0.19.0 技术评审 R9，至今未决） |
| A2 | **三棵树同步漂移** | 版本或计数漂移→文档宣称与实际行为不符→问题报告不可信（release.py --apply 硬闸 + 2026-10-18 dated 排除已收口，但手工改文档仍会引入漂移） |
| A3 | **长时运行无巡检** | 常开场景 7×24 无人值守，慢泄漏/慢劣化（P10/P04）无人发现，直到用户侧爆发 |

### 7.3 结论

以**开发者自部署研究平台 + Agent 治理内核**双形态，laos **满足上线门槛**（§5 十项 GO）；**语音问答（S2）按"文字 + 浏览器朗读"形态上线**（KWS 实测与 laos 侧 TTS 合成到位前不承诺完整体验）。对照 v0.19.0 评审，需求侧两大 NO-GO（可观测性 G8、TTS G6）均已实质推进，本轮需求面的工作重心应从"补功能"转向**驱动真机链路验收**（KWS / TTS / 屏幕多轮）与**长时运行数据积累**——前者是 Should 项，后者靠上线运行自然产生。

---

### 附：本文引用来源

- 前版评审（编号冻结源）：docs/review/2026-10-07-requirements-review.md（P01–P15 冻结、Go/No-Go 判定口径）
- CHANGELOG.md v0.19.0–v0.39.0 各版段（能力落地与测试增量记录）
- docs/design/2026-10-08-architecture-current-state.md（架构现状快照：模块地图/驱动/zones/环境变量）
- 2026-10-18 实跑记录：主库 discover "Ran 1180 tests / OK (skipped=5)"（当日多次全套 255–291s；1180 = v0.39.0 发版时点 1158 + 1 dated 排除回归 + 6 锚点同步回归 + 15 当日并行 SDD 批次的综述校验器回归，构成归属详见《技术评审 2026-10-18》页眉口径段）；AlwaysOnRec-ZCode 279（skipped=8）；Repro-ZCode pytest 94 collected；AlwaysOnRec-Trae 276（skipped=8）
- docs/research/2026-10-06-voicenpu-adoption.md（上游对照锚点 1.44s/1951MB/88ms）；docs/research/always-on-recording/hardware-power.md（功耗阶梯与准入线）
- docs/ppt/2026-10-18-ppt-audit.md（介绍面锚点审计与 §6 执行记录）
- README.md / docs/PROJECT_OVERVIEW.md / AGENTS.md（能力总览、发版纪律、红线纪律）
