# laos 采纳总纲（Capstone）：全部调研资产 × laos 架构映射

> 定位：[INDEX.md](INDEX.md) 所列 59 份调研资产的**采纳总账**——每条映射回答四问：来源｜可取之处｜laos 落点｜状态。
> 状态记法：**●已落地**（代码落地，附 git commit，查证命令见附录）/ **●已消化**（资产入库或口径写入文档，无代码落点）/ **◐推荐 P0–P3** / **○不做**（附理由）。
> 三树布局：根 `laos/` 为主树；`AlwaysOnRec-ZCode/` 为隔离实现区（Apple 增量与 speech-frontier 批次，README §10.2）；`AlwaysOnRec-Trae/` 为并行会话工作区（能力阶梯/Opus 配额/环形缓冲批次）。涉及三树的落点均带路径前缀，commit 归属经 `git show --stat` 逐条核实（命令见附录）。
> 纪律：量化结论全部抄自源文档原句（不造新数）；外部 URL 均出自源文档；本报告自身只做映射与裁决。

---

## §A 总览矩阵（laos 模块 × 来源域）

| laos 模块 | 论文/学术 | OSS 生态 | 产品/业界 | 教训/合规 | 状态汇总 |
|---|---|---|---|---|---|
| `laos/vad.py` StreamingVAD（根树）＋PCEN（ZCode 树） | EdgeSpot/FusionVAD | Silero VAD 对照 | — | — | ●（7ffe672, bbf5f5e）｜◐外接 ONNX |
| `AlwaysOnRec-ZCode/laos/kws.py` 私有唤醒词 | EdgeSpot/LLM-Synth4KWS | openWakeWord 管线 | — | — | ●（bbf5f5e） |
| `drv_rec`（②捕获＋Opus＋配额＋即焚；Opus 档在 Trae 树） | AudioMoth 占空比 | Opus (RFC 6716) | Apple S12 环形缓冲 | UCB 自动删除实证 | ●（06ba582, 029a01a）｜◐duty 档 |
| `AlwaysOnRec-ZCode/laos/audiostore.py` 留存档 | Mimi/SNAC 低码率 codec | SNAC (MIT) | — | 即焚前最小留存 | ●（bbf5f5e） |
| `drv_ear`（③蒸馏 ASR+情感） | SenseVoice/TIM-Net | SenseVoice/FunASR/sherpa-onnx | Apple S12 端侧蒸馏 | PIPL 声纹红线 | ●（fa47b39）｜◐diarization |
| `bin/journal.py`＋`diary`/`mood_report`（④消费） | emotion2vec/EmoBox | LocalRecorder 分层摘要 | Apple 三段式 schema | 情感只做纵向差分 | ●（5fa34d2, 677616b）｜◐9 类精化 |
| `laos/kernel.py` 能力阶梯（Trae 树）＋task_scope（根树） | Agent libOS 权威上限 | — | — | NameTag 教训 | ●（885391c, 962d956） |
| `laos/risk.py` FleetLedger | Irreversibility Budget (MPI-SWS) | — | — | — | ●（9285448 等 4 commits） |
| `laos/branch.py`+`cow.py` BranchContext | Fork-Explore-Commit (2602.08199) | BranchFS 对照 | — | — | ●（06edb3c, 713568b）｜○FUSE 远期 |
| `laos/context.py` 窗口/摘要/观察簿 | Stale Context (HKU)/MemGPT | fast-jev-compaction 模式 | — | — | ●（06edb3c, ba74910） |
| `laos/judge.py` Jev 判断层 | Jev System-One 三判型 | NanoJev/simple-jev/校准台方法论 | — | rule 后端 0.519 警示 | ●（509189a→477af8c） |
| `laos/agentprof.py` 语义剖析 | AgentProf (SOSP'26 线) | — | — | — | ●（e88fb24, 9a94834） |
| `laos/seccomp.py`+`enforcement/` | 阿里云 AgentSecCore 对照 | gVisor/E2B（远期） | — | — | ●（088e63e→4794580）｜◐白名单模式 |
| `drv_npu` QNN/ADSP 真机闭环 | TIM-Net ADSP 部署 | QNN LPAI | — | 功耗阶梯分界 | ●（89b37ef, dd753f7） |
| `drv_screen`/`drv_genie`/IPC/MCP | MCP 2026-07-28 | agentOS MsgBus 对照 | — | — | ●（7874c3b, 17fcb5f） |
| ADSP 白名单事件（`/events` 升级） | DCASE'25 蒸馏冠军 | YAMNet | Apple Sound Recognition | 先滤人声留事件 | ◐P1（缺口） |
| 真机可见指示（前台通知） | MeMic N=168 | — | Meta LED 防篡改/Apple Recap 无声争议 | 合规硬要求 | ◐P0（缺口） |

**一句话裁决**：内核语义层与四段漏斗主干已全部落地（●占多数）；剩余推荐集中在三处——ADSP 事件白名单、说话人弱标签、真机可见指示；拒绝清单收敛于"伪装采集/摄像头/云常开/闭源云/情绪识别执法红线"五族。

---

## §B 四段漏斗映射（主线）

### B-① 常驻检测（nW–mW 级）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| Silero VAD（MIT，[GitHub](https://github.com/snakers4/silero-vad)） | 模型 ~2MB、30ms chunk <1ms CPU、24/7 事实标准 | 自研零依赖 StreamingVAD 保持兜底（批量/流式 parity） | ●已落地（7ffe672）；外接 ONNX 通道 ◐P3 |
| EdgeSpot（ICASSP 2026，[arXiv:2601.16316](https://arxiv.org/abs/2601.16316)） | 可训练 PCEN 前端（逐通道能量归一化，几十行） | `AlwaysOnRec-ZCode/laos/vad.py` `use_pcen=True`：低 28dB 语音与正常音量分段一致 | ●已落地（bbf5f5e） |
| FusionVAD（IS25，[arXiv:2506.01365](https://arxiv.org/abs/2506.01365)） | MFCC+SSL 特征**简单相加**即超交叉注意力 | PCEN 之外的噪声鲁棒第二台阶 | ◐推荐 P2 |
| openWakeWord 管线＋LLM-Synth4KWS（[arXiv:2505.22995](https://arxiv.org/abs/2505.22995)） | 合成数据+易混词对比学习压误唤醒（AUC +3.7%、易混词 c-AUC +11.3%） | `AlwaysOnRec-ZCode/laos/kws.py` 包络 DTW（模板=纯 JSON 非声纹）+`AlwaysOnRec-ZCode/scripts/kws_confusables.py` 声母/韵母替换 | ●已落地（bbf5f5e） |
| TIM-Net（ICASSP 2023，[GitHub](https://github.com/Jiaxin-Ye/TIM-Net_SER)） | ~0.1–0.5M 参数小型档精度之王；真机 34,671 参数/0.4MB，LPI <5mW 常驻 | App 内 ADSP LPAI 情感差分 → `/events` → `drv_events` | ●已落地（89b37ef 推理；drv_events 15c3186；闭环 dd753f7） |
| 34.7µW KWS 专用 IC（MDPI Electronics 2023） | 待机 1.65µW / KWS 平均 34.7µW 功耗标尺 | 纯能量 VAD 应压个位数 µW 的预算口径（不实现硬件） | ○不做（硬件实现；仅作标尺参照，[hardware-power](always-on-recording/hardware-power.md)） |

### B-② 触发捕获（存储档）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| Apple Watch S12 音频智能（[支持文档](https://support.apple.com/en-us/148354)） | 15s 环形缓冲=②触发捕获、7 天删=④即焚的消费者级验证 | journal 标题 schema + `time:` 调度窗（ZCode 树）+ 6h 即焚（根树） | ●已落地（5fa34d2；即焚 3911790） |
| mic 能力阶梯（laos 原创，业界无第二家） | `mic.listen→record→transcribe→always_on` 高层含低层、默认收紧 | `AlwaysOnRec-Trae/laos/kernel.py` 四级能力表 | ●已落地（885391c） |
| Opus（RFC 6716，[xiph/opus](https://github.com/xiph/opus)） | 16 kbps = 7.2 MB/h 宽带近透明；帧长 2.5–60ms | `AlwaysOnRec-Trae/drivers/drv_rec.py` opus 编码（回退链）+ 存储配额 | ●已落地（06ba582） |
| AudioMoth（[Open Acoustic Devices](https://www.openacousticdevices.info/)） | SD 写入 17–70 mW、睡眠 80 µW 的占空比调度范本（9% 占空→续航 ~12×） | 环形缓冲+rewind 已落；duty-cycle 档位待做 | ◐推荐 P2（`029a01a` 已落 `AlwaysOnRec-Trae/drivers/drv_mic.py` always_on 环形缓冲与回放） |
| Mimi/SNAC（[arXiv:2410.00037](https://arxiv.org/abs/2410.00037) / [arXiv:2410.14411](https://arxiv.org/abs/2410.14411)） | 1.1/0.98 kbps ≈ **0.5MB/小时**（PCM 115MB/h 的 1/233）；留存格式=模型表示合一 | `AlwaysOnRec-ZCode/laos/audiostore.py` µ-law 档（默认关）+ SNAC 可选依赖；0.5MB/h×6h≈3MB/天 | ●已落地（bbf5f5e；µ-law ~0.5× 档 ≈57MB/h（115MB/h×0.5 折算）已落地，0.5MB/h 为 SNAC 可选依赖目标） |

### B-③ 蒸馏（百 mW–W 级）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| SenseVoice-Small（[HF](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)） | **234M**、10s 音频 ~70ms；ASR+情感+事件一次推理 | `drv_ear` 本机/HTTP 双通道（`LAOS_ASR_CHANNEL`） | ●已落地（fa47b39） |
| Streaming Sortformer（IS25，[arXiv:2507.18446](https://arxiv.org/abs/2507.18446)） | 到达序说话人身份（AOSC），**不建长期声纹库**，PIPL 对齐 | "谁的日记"弱标签（4 说话人上限；跨天身份=开放课题） | ◐推荐 P1 |
| DCASE'25 Task1 冠军（[结果页](https://dcase.community/challenge2025/task-low-complexity-acoustic-scene-classification-with-device-information-results)） | **61.47% @ 122,296 参数 / 29.4 MMACs**（约束 128K/30MMACs）；大教师→小学生蒸馏范式 | ADSP 白名单事件（哭声/警报/门铃→`/events`）；"环境理解"入口 | ◐推荐 P1 |
| URGENT Challenge（[arXiv:2505.23212](https://arxiv.org/abs/2505.23212)） | 7 类失真统一评测；2024 冠军 Multistage USE（MOS 3.52） | journal"先增强再转写"的内部评测蓝图（SE 后 WER 必回归，配 [2501.02452](https://arxiv.org/abs/2501.02452) 桥接结论） | ◐推荐 P1 |
| whisper_streaming LocalAgreement（[GitHub](https://github.com/ufal/whisper_streaming)，arXiv:2307.14743） | 自适应分片/延迟的流式 ASR | `ear.stream` 通道（现状仅批量转写） | ◐推荐 P1 |
| GTCRN（ICASSP 2024，[GitHub](https://github.com/Xiaobin-Rong/gtcrn)） | 仓库实测 48.2K 参数 / 33.0 MMACs/s，PESQ 2.87——MCU/ADSP 可常驻的算力锚点 | 常驻 ML 门槛判据；journal 批处理前置可选 | ◐推荐 P2（锚点＋DPDFNet 落地选项，ONNX 已被 sherpa 收录） |
| SE-AGCNet（IS26，[arXiv:2606.25959](https://arxiv.org/abs/2606.25959)） | 端到端联合 SE+LUFS 响度控制；"AGC 的 ML 化刚起步" | journal 前置响度归一的复现 baseline | ◐推荐 P2（先做纯 Python RMS-AGC ~20 行） |
| TRILLsson（IS22，见 [双会议遍历](2026-09-13-icassp-interspeech-full-survey.md)） | 以 **<4% 体积在情感任务反超 wav2vec2.0** | 端侧情感兜底参照（零依赖哲学同款：蒸馏小底座+轻头） | ◐推荐 P2 |
| emotion2vec_plus_large（[HF](https://huggingface.co/emotion2vec/emotion2vec_plus_large)） | ~300M、9 类细粒度、13 数据集 10 语言 | mood_report 9 类聚合可选通道（EMOTION_GLYPHS 扩表） | ◐推荐 P3 |
| GOPT+speechocean762（[arXiv:2205.03432](https://arxiv.org/abs/2205.03432)） | 四维（准确/流利/完整/韵律）发音评分全开源基线 | `AlwaysOnRec-ZCode/laos/pronunciation.py` 流利度/节奏两维 + `ear.assess`（GOPT 后端插桩，ZCode 树） | ●已落地（bbf5f5e） |
| Kokoro-82M（[HF](https://huggingface.co/hexgrad/Kokoro-82M)） | 82M 仅解码器 TTS，端侧性价比之王（中文需 v1.1-zh） | 语音回复+AudioSeal 水印（[arXiv:2401.17264](https://arxiv.org/abs/2401.17264)） | ◐推荐 P2（laos 现只听不说，回复属新增面） |

### B-④ 留存与消费（合规成本集中段）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| UCB 隐私控制实证（[EECS-2022-249](https://digicoll.lib.berkeley.edu/record/273841/files/EECS-2022-249.pdf)） | 用户期待自动删除 vs 行业默认永久存储的认知错位 | `rec_gc(keep_hours=6)` 原始音频即焚 | ●已落地（3911790） |
| Apple Siri Recap 三段式 | 标题+摘要+要点 schema；按时间/地点计划 | journal `# 标题` 首行 + diary 渲染 + `time:HH:MM-HH:MM` 窗（mic.* 专用、fail-closed） | ●已落地（5fa34d2） |
| LocalRecorder 分层摘要 | hour→day→week | diary 五章节（日级）+ mood_report（周级） | ●已落地（9891fb9, 677616b） |
| mem0（Apache-2.0，[GitHub](https://github.com/mem0ai/mem0)） | user/session/agent 三级记忆 | MemoryStore 单层 JSONL 的冷热分层（明文层/摘要层） | ◐推荐 P1 |
| StreamVoiceAnon+（[arXiv:2603.06079](https://arxiv.org/abs/2603.06079)） | 首批流式匿名化，帧级蒸馏保情感（攻击者 EER 49.0%） | 日记对外分享先匿名化（VoicePrivacy 协议） | ◐推荐 P3 |
| MeMic（CHI EA '24，N=168）+ Meta LED 防篡改 | 可见指示是合规硬要求；Apple Recap 无声无灯=争议焦点（laos 差异化高地） | Android 前台常驻通知+用户可见开关 | ◐推荐 P0（真机合规缺口，README 中期 5） |

---

## §C 内核语义层映射

### C-1 AIOS / AgenticOS'26 论文族 → 内核件

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| Irreversibility Budget（MPI-SWS，[SOSP'26 AgenticOS](2026-09-05-agentos-next-steps.md)） | 车队级风险记账与准入——`rm -rf` 与 `ls` 不能同价 | `laos/risk.py` FleetLedger：加权/两级记账 + per-agent 风险帽 + spawn 准入保留水位 + `laosctl budget` 回放 | ●已落地（9285448, 6c5fd62, 63128df, 6fdd71a） |
| Fork-Explore-Commit（[arXiv:2602.08199](https://arxiv.org/abs/2602.08199)） | branch context：COW 隔离 + first-commit-wins + 可嵌套 | `laos/branch.py`（基线即含）→ `laos/cow.py` hardlink COW（fork 只复制目录项、写路径 temp+replace 断链）+ inode 快路径 diff | ●已落地（06edb3c, 352ce4a, 713568b, ac1d417） |
| Stale Context（HKU *When Agent Context Goes Stale*） | 上下文与实际环境不一致的检测与通告 | `context.py` 观察簿：fs.read 观察 / fs.write/append 失效他人 / branch commit 批量失效 → 内核通告注入 agent 窗口 | ●已落地（ba74910, fd51845, 54b2ad3） |
| AgentProf（UCSC+阿里云+HKUST） | Agent 语义剖析（重复浪费/拒绝率/单工具依赖） | `laos/agentprof.py`：审计流→per-agent span+启发式→OTLP/JSON 导出（`var/traces/`）+ `laosctl spans` | ●已落地（e88fb24, 9a94834） |
| token=内存管理共识（MemGPT/AIOS Context Manager，[agentos-landscape](agentos-landscape-2026-08.md) §G） | 上下文=新内存：窗口/分页/swap | `context.py` ContextManager 窗口+摘要压缩+swap | ●已落地（06edb3c 基线；Jev 化压缩 c685f32） |
| Agent libOS Task Authority ceiling（[arXiv:2606.03895](https://arxiv.org/abs/2606.03895)） | 权限上限只能收紧不能放宽；信息流标签传播 | `task_scope` 意图收窄（能力说"能读"、任务说"读哪些"，越界 EACCES、血统继承） | ●已落地（962d956）；信息流标签 ◐P2；sys.delegate 委托 ●（7874c3b 同批 IPC） |
| 阿里云 AgentSecCore（[ANOLISA](https://github.com/alibaba/ANOLISA)，L4） | seccomp+bubblewrap 进程级沙箱、Skill 签名 | `LAOS_SECCOMP=block-dangerous`（纯 Python BPF 组装、bootstrap shim 注入、fork 继承）+ namespace/cgroup 接驱动 spawn | ●已落地（088e63e, 79302d3, 320b6b6, 28d1a3e）；seccomp 白名单模式 ◐P2 |
| CherryUSB OSAL 模式（[cherry-embed 学习](2026-09-10-cherry-embed-learning.md)） | 一套抽象层适配多种 RTOS | `laos/enforcement/` linux/android/stub 三后端 + `LAOS_ENFORCEMENT` 选择器 + Termux 探测 | ●已落地（fa9b5e9, c08bdfe, 4794580） |
| MCP 2026-07-28（Tasks/Elicitation） | 异步任务+人类在环统一入口 | `syscall(..., task=True)` 轮询 + elicitation 路由内核 confirm | ●已落地（17fcb5f, 03b9ae8） |
| FUSE BranchFS（arXiv:2602.08199 实现，非 root，创建 <350µs） | 真 O(1) inode 级 COW + 原子 rename | 硬链接 COW 已覆盖当前规模 | ○不做（远期项：README §七-9；引入 FUSE 的复杂度在 demo 阶段不划算） |
| gVisor 可插拔沙箱 | seccomp 之后下一档隔离强度 | enforcement 第四后端 | ○不做（远期项：README §七-10） |
| seL4 agentOS（L5） | 能力不可提升+形式化验证 | — | ○不做（放弃 Linux 生态；laos 定位=L2 语义写扎实+L4 强制接满，[agentos-landscape](agentos-landscape-2026-08.md) §1） |
| Composite FL（KTH，ICASSP 2024 最佳论文） | 联邦学习异构数据 | — | ○不做（非 laos 主域，[ICASSP 报告](2026-09-13-icassp-2022-2026-report.md)） |

### C-2 Jev 判断层（TypeSafe System-One）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| Jev 三判型契约（[Jev 生态报告](2026-09-18-jev-landscape.md) §1） | noul/choice/score 类型化决策+校准概率，零生成零幻觉 | `laos/judge.py` 四后端（none/rule/cloud/local）+ SafeJudge fail-open 装配 | ●已落地（509189a） |
| 四闸门消费点（landscape §4 论证） | prejudge/mem 入库/compact/skill 沉淀各配判型 | kernel 高危预审（`LAOS_JEV_AUTOGATE`/`PREVIEW`）+ `LAOS_JEV_MEM/COMPACT/SKILL`，全路径 `event:"jev"` 审计 | ●已落地（a65932a, c685f32, 3a1564b, 7dae105） |
| 校准台方法论（[jarvis 评估](2026-09-18-jev-chat-jarvis-assessment.md) §4.1，MIT+NOTICE 署名） | 52 例标注集→混淆矩阵+置信分桶+gates 退出码 | `scripts/calibrate_judge.py`；**rule 后端 accuracy 0.519、0.9-1.0 桶误判 33%** → autogate 禁配 rule | ●已落地（703d73c；警示写入 README，477af8c） |
| criteria 式问句（jarvis §4.2） | instructions+判据双层、档位情景化、题目正交、反例前置 | 四问句常量两段式升级 + `kernel.py PREJUDGE_JUDGE_QUESTION` 模板 | ●已落地（c6f6509） |
| 自检模式（jarvis §4.3 KbSelfCheck） | 真库冒烟+scratch 配置+finally 清理 | `bin/laosctl.py selfcheck`（JSONL 完整性+归一化+recall sanity） | ●已落地（c72e85d；修复 80be49b） |
| A-B 实验纪律（jarvis §4.4） | 单一变量+基线格+全格记录 | laos 既有做法（流式/批量 VAD parity 即 A-B 同构），吸收其验收文档形态 | ●已落地（7ffe672 parity；评估报告留痕） |
| 端侧复现谱系（NanoJev/simple-jev/edgejev，[实测](jev/04-ondevice-benchmark.md)） | edgejev ONNX int8 324.5MB、3 题批量 median **157.5ms**、峰值 RSS 495MB（README 15.6ms 被否证） | `LAOS_JEV_ENDPOINT` local 后端即接；**常驻每帧调用 0.5–1.5W 否决，离线档 4.6mW 可接受** | ●已落地（509189a local 后端）；端侧常驻 ○不做 |
| 校准不对称警告（landscape §1.3） | Choice/Score 过信、Boolean 欠信；排序在分布外不可盲信（GoSail 重排反例） | 阈值按判型分调 + 中文 state 校准存疑待实测 | ◐推荐 P2（local/cloud 后端上线前跑校准台） |

---

## §D AgentOS 广域映射（产品与 OSS 参照）

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| screenpipe（⚠ source-available，YC S26） | 24/7 屏幕+音频、本地 SQLite+OCR+Whisper——laos `drivers/rec`+记忆层最接近的参照 | schema 参照（`audio_transcriptions(timestamp,speaker,text,offset)` 字段级对齐）；**MIT→source-available 许可警示已写进 README 10.3** | ◐参照不引入（商用需重读许可；修正 2626ccc 批次） |
| Omi（BasedHardware，开源含硬件） | 24h+ 连续录音 BLE 流式到手机、可自托管 | 硬件+固件+后端全栈参照 | ◐参照 P3（硬件形态远期） |
| pipecat ★15.5k / agenticSeek ★27.2k（[OSS 普查](2026-09-14-papers-oss-full-survey.md) §3） | voice agent 运行时/全本地 agent 的编排层 | **不直接用：无能力管控/审计层**（laos 差异化=内核闸门+审计+即焚，开源世界无第二家） | ○不做（编排层非漏斗组件） |
| Meetily / Vexa（[增补篇](always-on-recording/2026-09-11-verticals-apple-articles.md) §4） | bot-free 桌面抓音（不进会议）；"音频永不离开设备" | 会议赛道 schema/UX 参照（与 laos 本机驱动架构同构） | ◐参照 P3 |
| mem0 三级记忆 | user/session/agent 分层与事实抽取 | 记忆分层对照（§B-④） | ◐推荐 P1 |
| OpenVoiceOS（[GitHub](https://github.com/OpenVoiceOS/ovos-core)） | mic→VAD→wakeword→STT→intent→TTS 全链插件化 | laos 驱动已 MCP 化（更强的强制力层），插件化注册表可参照 | ○参照（不引入整栈） |
| Abridge（Epic 首个 Pal，200+ 医疗系统）/ Dragon Copilot | B 端合规姿势：会话级可撤回同意+领域结构化产物（SOAP） | laos 对等物=diary 五章节/journal 情绪标签；确认横幅+常驻通知覆盖"每次会话级同意" | ○参照（不进医疗域） |
| OSS 普查 3724 条（[景观报告](2026-09-14-audio-ai-agent-oss-landscape.md)） | core 132（3.5%）；漏斗落点 ①42/②25/③117/**④0** | ④即焚是策略而非第三方组件——laos 独有；许可缺失 75.2% 须逐条核 SPDX | ●已消化（073a3c5，语料+报告+审计脚本入库；无代码落点） |
| 双会议 19,792 篇语料（[全量普查](2026-09-14-papers-oss-full-survey.md)） | ICASSP 14,285 + Interspeech 5,507；edge/llm/health 主题增长 | `papers_unified.jsonl` 选型底座 | ●已消化（073a3c5 报告 + ba2d649 统一语料与校验器入库） |

---

## §E 端侧与真机

| 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|
| QNN/ADSP LPAI（[真机集成研究](2026-09-09-qnn-real-os-integration.md)） | TIM-Net Active <50mW / LPI <5mW；7 分类 | `npu.infer` syscall → adb → ADSP 推理 → 结果回审计流并"风险账本扣 2 分" | ●已落地（1bf173a, 89b37ef, dd753f7；[运行手册](qnn-real-device-runbook.md)） |
| GTCRN 33.0 MMACs/s | MCU/ADSP 可常驻的现实预算上界 | 常驻候选模型的第一道筛选 | ◐锚点（§B-③） |
| 34.7µW KWS IC | 功耗标尺：纯能量 VAD 应压个位数 µW | `vad.py` 零依赖设计的目标口径 | ○不做硬件（§B-①） |
| Termux 五项矩阵（mount ns/cgroup v2/driver_pid/swapon/bpftrace） | proot 架构边界的实测证明 | `termux_matrix.py` 探测脚本已写；真机五项未跑全 | ◐推荐 P1（脚本 4794580；README 中期 6） |
| 功耗阶梯（[hardware-power](always-on-recording/hardware-power.md)） | ASIC 0.047–1µW → 音频 NPU 140µW → 传感枢纽 <1mA → AP 数百 mW（电池 19.25 Wh） | "proot 里 `mic.always_on` 不成立，必须原生 App 走 aDSP"的架构分界已写进 README §六 | ●已消化（口径入 README §六业界对标段；数字出处即本行源文档 hardware-power 功耗阶梯表，无代码落点） |
| Android 14 后台 mic FGS 限制 | 后台起 mic FGS 直接 SecurityException | 原生 App + 前台服务通知路线的依据 | ◐推荐 P0（与 §B-④ 可见指示同一项） |
| sherpa-onnx ★14.7k（Apache-2.0） | ONNX 推理在 proot aarch64 上更稳、体积更小；一站式 ASR+VAD+diarization+降噪 | `LAOS_ASR_CHANNEL` 之外的可选第三通道 | ◐推荐 P2（diarization 落地时的运行时首选） |

---

## §F 已拒绝清单汇总（一表收口）

| 拒绝对象 | 一句理由 | 出处 |
|---|---|---|
| jev-chat-jarvis 采集链路七文件（SelectToSpeakService/config_disguised/KeepAliveService/ChatAppAdapter/ChatCaptureService/ScreenCapture/OverlayController） | 伪装系统服务绕过反读取+无弹框截屏+对聊天对方零可见的画像外发——五条红线踩四条，**整体拒绝、零代码采纳**（方法论四件已另落地，见 §C-2） | [jarvis 评估](2026-09-18-jev-chat-jarvis-assessment.md) §5 |
| 多模态视频系（HumanOmni / AVSE / Emotion-LLaMA / AVVP） | laos 纯听觉、无摄像头是隐私红线——"默认永久不做，不是条件性暂缓" | [SER landscape](2026-09-11-ser-model-landscape.md) §2.5、[AED/AGC](2026-09-11-aed-agc-model-landscape.md) §2.5 |
| 云常开系（Rewind→Limitless→Meta、Humane AI Pin） | 死因=云依赖+低使用价值+高隐私成本；"零云"须写进内核约束而非文档承诺 | [收敛版](always-on-recording/2026-09-landscape.md) §8 |
| 职场/教育场景情绪识别 | EU AI Act 2025-02-02 起直接禁止（罚款至全球营业额 7%） | [frontiers](2026-09-12-speech-model-frontiers.md) §5.6 |
| GPT-4o-audio / Gemini 音频档 | 闭源云，违反 laos 零云约束 | SER landscape §2.4 |
| 应用层常驻实时降噪 | ADSP 固件 TX-path 已覆盖；再叠 ML 是双倍功耗（收益只剩"再降 3dB 底噪"） | AED/AGC §4 |
| 生成式修复（UNIVERSE/Miipher/扩散系） | 分钟级批处理、非因果，与常驻链路无交集 | AED/AGC §3.4 |
| 高星 TTS/音乐生成系（GPT-SoVITS ★61.8k、coqui-TTS ★46k 等） | laos 只听不说，范围外（Kokoro 回复属显式新增面，另行评估） | OSS 景观 §5 |
| 声纹库/长期说话人画像 | 中国法下声纹=敏感个人信息（PIPL 28/29 条，需单独同意）；diarization 只做到达序弱标签 | 收敛版 §7、frontiers §2 |
| 隐蔽采集四黑名单（秘密录音/看护无同意常录/声纹画像/永久云存默认） | 合规黑名单，主动放弃 | 收敛版 §7 |
| Jev 端侧常驻调用 | 常驻每帧 0.5–1.5W 附加（否决）；仅离线/二级确认档（4.6mW 量级）可用 | [jev 落点](jev/05-laos-placement.md) |

---

## §G 优先级路线图 v2（历史 P0–P3 合并去重）

> 合并来源：[收敛版 §9.4](always-on-recording/2026-09-landscape.md)、[frontiers §6](2026-09-12-speech-model-frontiers.md)、[增补篇 §6](always-on-recording/2026-09-11-verticals-apple-articles.md)、README §七、SER §3–4、AED/AGC §4–5。
> 已被消化项（本报告口径=已落地）单列于表尾。列：依据来源数 / 预计工作量（S/M/L）/ 依赖。

| # | 事项 | 优先级 | 来源数 | 工作量 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| 1 | Android 前台常驻通知+用户可见开关（真机可见指示） | **P0** | 3（收敛版 §9.4/增补篇 §3/README 中期5） | M | App | 未做 |
| 2 | ADSP 白名单事件分类器（DCASE 蒸馏/YAMNet 裁剪→`/events`） | P1 | 4（AED §4-5/收敛版 §9.3/增补篇 Sound Recognition/frontiers P2） | M | ADSP 第二 LPAI 岛调研 | 未做 |
| 3 | 说话人弱标签（Streaming Sortformer 到达序，不建声纹库） | P1 | 3（frontiers P1/收敛版 §9.3/README 近期1） | L | PC 批处理；sherpa-onnx 通道 | 未做 |
| 4 | `ear.stream` 流式 ASR（LocalAgreement） | P1 | 2（收敛版 §9.2/OSS core） | M | — | 未做 |
| 5 | 记忆冷热分层（mem0/MemOS 式：热明文+冷摘要） | P1 | 2（README 近期2/§D mem0） | M | — | 未做 |
| 6 | journal 前置增强+响度归一（URGENT 蓝图 + RMS-AGC 纯 Python ~20 行，SE 后 WER 必回归） | P1 | 3（AED §4-5/§8.5/SER §6.2） | M | .venv-audio | 未做 |
| 7 | MCP Tasks/Elicitation 硬化（旧客户端挂起超时/task 线程运行时守卫/task 记录 GC） | P1 | 1（README 近期4） | S | — | 未做 |
| 8 | Termux 五项真机矩阵跑通 | P1 | 2（README 中期6/hardware-power §7） | M | 真机 | 脚本已落（4794580） |
| 9 | 技能库精化（SkillStore 参数相似度聚类，减误命中） | P2 | 1（README 近期3） | S | — | 未做 |
| 10 | 占空比 duty 档（AudioMoth 范本，9% 占空→续航 ~12×） | P2 | 2（收敛版 §9.4/hardware-power） | S | App（029a01a 环形缓冲已落，Trae 树） | 部分落地 |
| 11 | seccomp 白名单模式（按驱动画像） | P2 | 2（README §七 强制隔离行/ANOLISA） | M | — | 未做 |
| 12 | 信息流控制标签（Agent libOS 标签传播+Sink 注册） | P2 | 1（[agentos-landscape](agentos-landscape-2026-08.md) §5 信息流控制行） | L | — | 未做 |
| 13 | drv_screen 多轮真机验收（通知/短信/传感器/技能编排用例） | P2 | 1（README 中期8） | M | 真机 | 未做 |
| 14 | `fs.write /main` commit 时结算（延迟定价） | P2 | 1（README 中期7） | S | — | 未做 |
| 15 | 认知/压力纵向差分（TAUKADIAL 口径，只做"与自己比"） | P3 | 2（frontiers P3/academic §5） | L | 纵向数据积累 | 远期 |
| — | **本会话已消化**：journal 标题 schema+`time:` 窗（5fa34d2，ZCode 树）、PCEN/KWS/audiostore/pronunciation（bbf5f5e，ZCode 树）、能力阶梯（885391c）/Opus+配额（06ba582）/环形缓冲（029a01a）（Trae 树）、FleetLedger（9285448 等）、观察簿（ba74910 等）、AgentProf（e88fb24 等）、Jev 四闸门+校准台（509189a→477af8c）、README 业界对照（2626ccc） | — | — | — | — | ●已落地 |

> **与 README §七 对账**：近期 4 项全收录（diarization→#3、记忆分层→#5、技能库精化→#9、MCP 硬化→#7）；中期 4 项全收录（前台通知→#1、Termux→#8、延迟定价→#14、drv_screen→#13）；远期 2 项（FUSE BranchFS/gVisor）已在 §C-1 缺口行裁决，不重复列表。原表 TTS 回复（Kokoro+AudioSeal）与 emotion2vec 9 类精化两行移出——单来源、非架构级，仅保留 §B 映射条目；RMS-AGC 并入 #6。
> **优先级裁决（ADSP 事件，#2）**：§G 原标 P0 与 §A/§B 的 P1 不一致，现统一为 **P1**——任务书样例与 AED 篇 §4"优先级"节均定 P1，且其前置依赖（ADSP 能否暴露第二个通用 SED LPAI 岛，AED §5-3）未经真机验证，不满足 P0"无依赖立即可做"的标准；P0 仅保留真机可见通知。

---

## 附录：commit 查证命令（"已落地"全部经 git log 核对）

```bash
# 已知锚点核对
git log --oneline -1 bbf5f5e   # AlwaysOnRec-ZCode 批次（PCEN/KWS/audiostore/pronunciation）
git log --oneline -1 477af8c   # Jev 判断层收尾（autogate/rule 警示）
git log --oneline -1 7dae105   # JevGatedMemory 收敛 + live E2E
git log --oneline -1 80be49b   # selfcheck 修复
# 内核件
git log --oneline --all | grep -iE "FleetLedger|risk"        # 9285448/6c5fd62/63128df/6fdd71a
git log --oneline --all | grep -iE "observation|stale"       # ba74910/fd51845/54b2ad3
git log --oneline --all | grep -i "AgentProf"                # e88fb24/9a94834
git log --oneline --all -- laos/branch.py                    # 06edb3c（基线）/713568b
# 漏斗与驱动
git log --oneline --all | grep -iE "AlwaysOnRec|journal|vad" # 5fa34d2/bbf5f5e/029a01a/06ba582/885391c/7ffe672
git log --oneline --all | grep -iE "drv_npu|qnn|device transport" # 89b37ef/dd753f7
git log --oneline --all | grep -iE "judge|jev"                # 509189a/a65932a/c685f32/3a1564b/703d73c/c6f6509/c72e85d
# 三树归属核实（路径前缀的依据）
git show --stat --oneline 885391c | head -3    # 能力阶梯 → AlwaysOnRec-Trae/laos/kernel.py
git show --stat --oneline 06ba582 | head -3    # Opus+配额 → AlwaysOnRec-Trae/drivers/drv_rec.py
git show --stat --oneline 029a01a | head -3    # 环形缓冲 → AlwaysOnRec-Trae/drivers/drv_mic.py
git show --stat --oneline 5fa34d2 | head -3    # 标题 schema+time: 窗 → AlwaysOnRec-ZCode/
git show --stat --oneline bbf5f5e | head -3    # PCEN/KWS/audiostore/pronunciation → AlwaysOnRec-ZCode/laos/*
git log --oneline -1 073a3c5                   # ●已消化锚：普查终版入库
git log --oneline -1 ba2d649                   # ●已消化锚：19,792 篇统一语料+校验器
```
