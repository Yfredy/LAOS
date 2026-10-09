# docs/research 调研资产清单（INDEX）

> laos 调研资产权威清单：每份文档一句话定位 + 关键数字（均抄自各文档自身原文，未凭文件名推断）。
> 盘点日期：2026-10-06（2026-10-07 增补 4 份调研 + 3 份评审与设计；2026-10-08 持续增补：arvis/muse-gadget-sdk 报告 + 语音三域收尾 16 份；2026-10-09 增补：小红书「AI音频研究」134 篇逐图全量调研 1 份 + RSI 方向全景 1 份 + Qwen Audio Agent Runtime 单篇 1 份；再增补：Interspeech 2026 语音增强风向 1 份）。共 107 份 .md（不含本文件；2026-10-09 复核基数 108 = 106 份资产 + capstone + 本文件，二次增补后 109 = 107 份资产 + capstone + 本文件，三次增补后 110 = 108 份资产 + capstone + 本文件）。此前头部写的分项口径（66+2+17+3=88）与实数漂移，分项归属核对归属"INDEX 预存计数漂移归属波"排队项，此处只对准总数。

## 导航：按问题找文档

> 本节只给「最短阅读路径」；下面一～七节的清单表才是全量数据，按目录逐份查。

**【总入口｜先读这份】全部调研到底采纳了什么、落到 laos 哪里？**

- [2026-09-19-laos-adoption-capstone.md](2026-09-19-laos-adoption-capstone.md) — 59 份资产的采纳总账：每条回答「来源｜可取之处｜laos 落点｜状态（●已落地/●已消化/◐P0–P3/○不做）」。读完它再按指引下钻本清单，不必通读。

**想做全天候录音（产品形态、功耗、合规怎么定）？**

- [always-on-recording/2026-09-landscape.md](always-on-recording/2026-09-landscape.md) — 五条调研线（产品/学术/硬件/接受度/垂直）的收敛结论：常开被动产品全灭、端侧克制常开是唯一活路，四段漏斗的起点。
- [always-on-recording/2026-09-11-verticals-apple-articles.md](always-on-recording/2026-09-11-verticals-apple-articles.md) — B 端四条垂直赛道 + Apple Watch S12「端侧克制常开」范式逐项对照（环形缓冲/端侧蒸馏/7 天即焚）。
- [always-on-recording-industry-2026-09.md](always-on-recording-industry-2026-09.md) — 业界全景：形态×处理位置×触发方式×开源闭源图谱 + 法条清单 + 开源可抄管道（Silero VAD→sherpa-onnx→Opus→SQLite）。

**想选听觉模型（SER / AED / AGC / 其余语音能力）？**

- [speech-emotion/2026-09-landscape.md](speech-emotion/2026-09-landscape.md) — **SER 收敛终篇（2026-10-08 收尾波）**：46 条记录交叉 + 选型决策树（Q6 一体化 → SenseVoice-Small via sherpa-onnx）+ 落地见 06-adoption。
- [audio-events/2026-09-landscape.md](audio-events/2026-09-landscape.md) — **AED 收敛终篇（2026-10-08 收尾波）**：交叉表 + 中文场景空白 + 常驻升级判定（"不做常驻；有条件做事件驱动"）+ 落地见 07-adoption（暂不引入）。
- [auto-gain/2026-09-landscape.md](auto-gain/2026-09-landscape.md) — **AGC 收敛终篇（2026-10-08 收尾波）**："分层判定（闭环增益是 DSP，噪声场景是模型）" + 加在哪层决策表 + 落地见 07-adoption（不加）。
- [2026-09-11-ser-model-landscape.md](2026-09-11-ser-model-landscape.md) — SER 选型地图：端侧/小/中/大/多模态五类全景，含参数量与延迟硬数字。
- [2026-09-11-aed-agc-model-landscape.md](2026-09-11-aed-agc-model-landscape.md) — 听觉链路另两个能力的选型地图：AED 的 DCASE 低复杂度硬约束与 AGC 的 ML 化现状。
- [2026-09-12-speech-model-frontiers.md](2026-09-12-speech-model-frontiers.md) — SER/AED/AGC 之外的六大语音领域（说话人/前端触发/编解码生成/副语言健康）51 篇逐篇跟踪。
- [2026-10-09-interspeech2026-se-trends.md](2026-10-09-interspeech2026-se-trends.md) — Interspeech 2026 语音增强 115 篇风向（一步生成式/幻觉记账/延迟旋钮/Enroll-on-Wakeup/后门攻击）：EoW 唤醒段当注册音 ◐ 远线，生成式幻觉红线获学界印证 ●。
- [speech-emotion/2026-09-landscape.md](speech-emotion/2026-09-landscape.md) — SER 侧的交叉收敛篇：46 条记录只交叉不新增，选型前的最后一道核对。

**想做 Agent 治理层（laosd 薄内核）/ 判断层？**

- [agentos-landscape-2026-08.md](agentos-landscape-2026-08.md) — 「AgentOS」八种含义与 L0–L3 强制力光谱，内核语义层设计的坐标系。
- [2026-09-21-jev-decision-model-survey.md](2026-09-21-jev-decision-model-survey.md) — 判断层选型：Jev 三判型技术实质 + laos 11 处硬阈值映射 + 端侧实测真数字（不用 README 宣称值）。
- [aios-deep-dive-2026-08.md](aios-deep-dive-2026-08.md) — AIOS 逐机制拆解与 laos 直接对比，内核该抄什么、缺什么。
- [jev/05-laos-placement.md](jev/05-laos-placement.md) — 判断层落地清单：常驻每帧调用否决、离线档 4.6 mW 可接受等收益/代价逐条裁决。

**想查某篇论文 / 某个开源项目的原始数据？**

- [papers_index.md](papers_index.md) — `papers/` 论文 PDF 库自动索引（115 篇，arXiv 号+日期+标题表）。
- [2026-09-14-papers-oss-full-survey.md](2026-09-14-papers-oss-full-survey.md) — 统一语料 19,792 篇的程序化总账（ICASSP+Interspeech 全量），每个数字可溯源。
- [2026-09-14-audio-ai-agent-oss-landscape.md](2026-09-14-audio-ai-agent-oss-landscape.md) — 3,724 条 OSS 仓库的四段漏斗裁决表（core 132 / ref 2864 / unrelated 728），查项目适配结论看这份。
- [corpus/（见第六节清单）](#六corpus-与数据语料数据文件只列规模) — 语料与爬虫本体：`papers_unified.jsonl`、各抓取脚本与 README 快照，回溯任何报告数字的最终出处。

**想了解 RSI / Agent 自我改进（论文浪潮与治理含义）？**

- [2026-10-09-rsi-landscape.md](2026-10-09-rsi-landscape.md) — 2026-09/10 RSI 论文浪潮全景（RSIGym 环境 / AIDE² 自改写 / RRSI 正则化 / Last AI 路线图 + ICLR 26 Workshop 110 篇 + 开源生态 + 产业动态）与 laos「进化循环外裁判席」裁决。

## 一、主报告（根目录，36 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [agentos-landscape-2026-08.md](agentos-landscape-2026-08.md) | AgentOS / AIOS 现状调研与变体分类学：回答「Linux AgentOS = Linux kernel + Agent + MCP」命题在当下坐标系里的位置 | "「AgentOS」现在至少指 **8 种不同的东西**"；分类坐标轴为强制力光谱 L0（约定层）→L3（libOS 层） |
| [aios-deep-dive-2026-08.md](aios-deep-dive-2026-08.md) | AIOS（Rutgers）逐机制深度拆解，与 laos 直接对比：「它验证了什么、它缺了什么」 | arXiv:2403.16971v5（2025-08-12）；仓库 v0.2.2、859 commits；核心结论"AIOS 与 laos 是互补关系，不是竞争关系" |
| [2026-09-05-agentos-next-steps.md](2026-09-05-agentos-next-steps.md) | 对照最新论文与开源生态的 laos 下一步机会清单，按优先级排序 | 三个外部信号：MCP 2026-07-28 规范（Tasks/Elicitation/MRTR）、AgenticOS @ SOSP 2026 论文名单（Irreversibility Budget / Patient Bytes / Stale Context / AgentProf 等） |
| [2026-09-09-qnn-real-os-integration.md](2026-09-09-qnn-real-os-integration.md) | QNN/ADSP 语音情感真机部署工程的学习总结与 laos 结合路线（AP 侧 Android/Linux 结合点） | TIM-Net **34,671 参数 / 0.4MB**、LIGHT-SERNET ~460K 参数；Active < 50mW / LPI < 5mW；7 分类 |
| [2026-09-10-cherry-embed-learning.md](2026-09-10-cherry-embed-learning.md) | CherryUSB + CherryAVP 学习分析：嵌入式「小而美」两堂架构课（OSAL 抽象层 / 零抽象热路径） | OSAL 六种 RTOS 适配；产出已落地 `laos/enforcement/` 包（linux/android/stub 三后端 + `LAOS_ENFORCEMENT` 选择器） |
| [qnn-real-device-runbook.md](qnn-real-device-runbook.md) | 真机闭环运行手册：laos `npu.infer` syscall 经 adb 到骁龙 ADSP QNN LPAI 推理并回审计流 | 链路 `adb forward tcp:8900`；结果回审计流并"风险账本扣 2 分" |
| [papers_index.md](papers_index.md) | `docs/research/papers/` 论文 PDF 库的自动生成索引（arXiv 号 + 日期 + 标题表） | "自动生成，共 115 篇"（PDF 库实际 147 个 PDF，含同文多版本，另有 MANIFEST.txt） |
| [2026-09-11-ser-model-landscape.md](2026-09-11-ser-model-landscape.md) | 语音情感识别（SER）模型选型地图：端侧 / 小 / 中 / 大 / 多模态五类全景 | SenseVoice-Small **234M**、10s 音频 ~70ms；emotion2vec_plus_base ~90M；TIM-Net ADSP LPAI 岛 <5mW 常驻 |
| [2026-09-11-aed-agc-model-landscape.md](2026-09-11-aed-agc-model-landscape.md) | 音频事件识别（AED）与自动增益（AGC）模型全景：laos 听觉链路另两个模型能力的选型地图 | DCASE Low-Complexity 硬约束 **128K 参数 / 30 MMACs**，2025 冠军 61.47% @ 122,296 参数；GTCRN 实测 48.2K 参数 / 33.0 MMACs/s |
| [2026-09-12-speech-model-frontiers.md](2026-09-12-speech-model-frontiers.md) | SER/AED/AGC 之外六大语音信号领域（说话人/前端触发/编解码与生成/副语言学与健康声学）逐篇文献跟踪 | "共 **51 篇**逐篇条目"；Mimi 1.1kbps ≈ **0.5MB/小时**；Sortformer 第三方基准 DER 11.1% |
| [2026-09-13-icassp-2022-2026-report.md](2026-09-13-icassp-2022-2026-report.md) | ICASSP 近五年（2022–2026）结构化抽样报告：获奖名单 + 规模统计 + 代表论文摘要（抽样版，被终版取代但保留为伴侣篇） | ""近五年所有 ICASSP 论文" ≈ **10,000+ 篇**录用论文"；历年录用率 ~45%；2023 投稿 6,127 / 录用 2,765 |
| [2026-09-13-icassp-interspeech-full-survey.md](2026-09-13-icassp-interspeech-full-survey.md) | 双会议真实遍历报告（终版前置）：Interspeech 全量 + ICASSP 主题切片 + 深读，每个数字可溯源到 corpus/ | Interspeech 2021–2025 **5,507 篇 = 全量 100%**；ICASSP 切片 enhancement 5,257 / emotion 1,838 / codec 2,388 / VAD 183；32 篇深读 |
| [2026-09-14-audio-ai-agent-oss-landscape.md](2026-09-14-audio-ai-agent-oss-landscape.md) | 音频/AI/Agent 开源项目星标全景：laos 四段漏斗选型最终报告（Task 4） | "**3724 条**干净仓库（去噪 2153 + 引号短语补抓 1571）"；laos 适配 core 132 ｜ ref 2864 ｜ unrelated 728；许可字段缺失 2801/3724（75.2%） |
| [2026-09-29-multivenue-survey.md](2026-09-29-multivenue-survey.md) | 多顶会主题切片普查：35 个 NLP/ML/CV/语音近邻/多媒体/交叉 venue（9,908 条，29 有产出）+ 数据源结构性地图 | TASLP 1,234 / ASRU 949 / SLT 923；Crossref↔ACL Anthology↔PMLR 覆盖边界；AAAI 解锁=ISSN 2159-5399 精确过滤 |
| [2026-09-29-mobile-mcp-assessment.md](2026-09-29-mobile-mcp-assessment.md) | Mobile MCP（7k+★ 手机操控 MCP）评估：30 工具对照 laos 五层手机能力 + 采纳决策表 | 无治理驱动对照组：`kernel.load_driver()` 可直接外挂（`MOBILEMCP_DISABLE_TELEMETRY=1` 必设）；双击/长按/按键/应用管理=drv_screen 缺口；GPS 伪装/裸批处理/云真机=不做 |
| [2026-10-05-four-article-repro.md](2026-10-05-four-article-repro.md) | 六来源复现报告：头部朝向论文（arXiv 2607.02129v1）/PhaseCoder/车载 ANC/LUFS/Pipecat 帧管道/C++ unique_lock——能复现的全部落进 `Repro-ZCode/`（71 测试） | "R128 校准点 I=−23.00 LUFS ±0.1"；FxLMS 音调 >20dB、2×2 ~15dB；PhaseCoder MPE 与官方 JAX 源码逐行对齐（α=7/β=4）；冒烟 120 语句×400 步 holdout 56.5°；Pipecat 打断作废排队帧而系统帧穿管 |
| [2026-10-05-repro-adoption.md](2026-10-05-repro-adoption.md) | 复现批次采纳执行书：六来源+五 PPT skill 对 laos 的帮助裁决（●执行 3 / ◐文档 2 / ○不做 2）与落地 | "A 响度纯 stdlib 进主库 + ear.lufs；B TurnBuffer 打断即作废/只记已送达；C UniqueLock+`_rpc` 全程持锁的协议事实" |
| [2026-10-05-speech-weekly-spatial-duplex.md](2026-10-05-speech-weekly-spatial-duplex.md) | 本周语音 AI 论文周报（8 篇：空间音频×4 + 全双工×4）学习与采纳评估——小红书登录墙后按"当周+双主题"从 arXiv 重构清单（诚实声明在文内） | Duplex-MPE 四能力分解（发起/准确/沉默/停止，MiniCPM-o 4.5 三项领先，Gemini 显隐式差 64.3pp）；SAIL 双耳相位差空间流；SALMONN-duo 快慢双系统；裁决 ●duplex/turnpolicy+binaural ◐foa |
| [2026-10-06-four-wechat-articles.md](2026-10-06-four-wechat-articles.md) | 四篇微信文章学习与采纳：EdgeAI-KWS 双 MCU 端侧部署 / Foreground VAD（arXiv 2609.19856）/ kernel-internals.org / GitHub 2026-09 趋势榜 | 置信度三段分流 ">= 0.9 本地执行 / >= 0.7 云端校验 / 其余丢弃"→`laos/confgate.py`；"BG-FAR 单独看会被装死模型刷满，必须配 Foreground F1 闸门"→`laos/vadmetrics.py`；趋势榜十强过半为 Agent 基础设施且两个 MCP 原生 |
| [2026-10-06-qnn-workspace-study.md](2026-10-06-qnn-workspace-study.md) | QNN 工作区（C:\Users\yaoyue\Downloads\QNN，22GB）通读学习：Explore 测绘 + 五份关键文件精读——固件层的"内核优先"同款动作（基座不动，SER 注册成 SEE 虚拟传感器常驻 SLPI） | 模型 rodata 符号级实测 **86,241B**；"AP 深睡时推理照常进行"；InferenceServer.kt 绑 127.0.0.1:8900 供 "laos AgentOS over adb forward"——npu.infer 的设备端对端；裁决 ●×1 ◐×4 ○×1 |
| [2026-10-06-transformer-efficiency-timeline.md](2026-10-06-transformer-efficiency-timeline.md) | 小红书视频《55秒看完Transformer效率演进时间线》整理（视频五路取件全失败，按既有预案从可验证来源重构，诚实声明在文内） | 三大脉络"少算/少搬/少存"：FA-2/3 IO 感知、GQA "KV 缩至 1/8 几乎无损"、MLA 93.3%、PagedAttention=OS 分页思想反哺模型层；与 laos 关系全为 ○/◐（模型层治理与进程外配额分而治之） |
| [2026-10-06-cactus-whistle-adoption.md](2026-10-06-cactus-whistle-adoption.md) | 小红书《16.9MB跑完端侧语音识别》复现与接入：Cactus Whistle——needle3 引擎（Windows 单文件 1.56MB）本机原生跑通，三通道 ASR 定局（zh 主力 funasr / 多语轻备 whistle / HTTP server） | **whistle en WER 10.8% vs SenseVoice 2.7%/zh CER 0%**；zh 实测英语幻觉（7 语无中文）；ttft 651ms/~300 tok/s；价值面=极小足迹（模型 16.9MB+引擎 1.56MB，全平台含 WASM/Android）非精度；WSL2+qemu aarch64 虚拟手机全程留档 |
| [2026-10-06-agenticasr-adoption.md](2026-10-06-agenticasr-adoption.md) | 小红书《AgenticASR》复现与运用：arXiv 2607.28175（ASR→Refiner 解耦，Qwen3-4B+LoRA 微调打赢 560B 零样本 19.7 vs 25.8）——laos 规则版 AgenticSR Refiner + ear.refine/refine=True 落地 | **官方 AASR-Bench 917 例全集（ModelScope）：错误率 0.4571→0.3875（-15.2%），18 场景 17 改善/持平，passthrough 零误伤**；端到端（TTS 口吃语音→funasr→refiner）CER 1.563→0.042；重述型纠错天然容错 ASR 噪声；官方仓库核对：全参微调/template cpm4/917+6637 rubric/onnx-int4 变体 |
| [2026-10-06-xhs-cuzz-audio-projects.md](2026-10-06-xhs-cuzz-audio-projects.md) | 小红书 up主 cuzz（语音学/音频工具向）音频项目清单 × laos 适配裁决：首屏采样 17 个音频项目（强制对齐 12 + 声学/语料 4 + ASR 1），诚实声明在文内（含 token 态不一致附注、TIFA/citationtone_hub 未核实） | 裁决 "**CrisperWhisper ●**（verbatim+词级时间戳→refiner 输入层与听觉记忆时间轴）/ **Qwen3-ASR ●**（zh 通道下一代候选，wer 框架可立即实测）/ charsiu ◐（zh 侧对齐）/ voicesauce ◐（副语言 DSP）"；其余对齐工具群 ○ 选型储备 |
| [2026-10-09-xhs-ai-audio-research-full.md](2026-10-09-xhs-ai-audio-research-full.md) | 小红书 up主「AI音频研究」全量调研：134 篇音频笔记 **逐图视觉转写**（1706 图 CDN 直读+幻觉裁决重读），A-K 十一组：Interspeech 2026 前端/ASR 五代演进+论文 15 篇/实践与语料/降噪 8 家横评/VAD 三家/DSP 13 篇/TTS 六代演进 15 篇+论文 11 篇/评测 9 篇/杂项与 DL 教学 36 篇；每篇含 laos 契合点，附录二为裁决总章（A 立即适用 6 条/B 近线 drivers 3 条/C 远线雷达 4 条/D 教学资产 3 条+红线重申） | 裁决 "**ASR 三通道/VAD 三档/时间戳三路线第三方四重佐证 ●**/SHEET MOS+合成退化元评测 ◐（评测扩容）/**DFN3+RNNoise 降噪双轨 ◐（drivers 层）**/TTS 商用安全区清单 ○（远线雷达）"；非音频 8 篇（LangChain 五部曲等）附录登记 |
| [2026-10-06-voicenpu-adoption.md](2026-10-06-voicenpu-adoption.md) | 小红书《RK3576语音系统》复现与采纳：Gitee bravexyz/voicenpu_engine（AGPL-3.0，13 cpp 全源码通读）——RK3576 端侧全双工对话引擎，控制面五件语义复现进 laos（WakeGate 四态会话机/generation 打断+投机 prefill 窗口/bigram 知识库短路/LLM→TTS 切句清洗/双后端降级路由），72 例新增测试 + 9 例闭环 e2e | 上游硬数字：首音 1.44s/常驻 1951MB/ASR 端点→终稿 ~88ms/投机窗口 500ms+96ms 恢复下限+200ms 延长；裁决=纯逻辑 ● 已落地 / KWS·VAD·豆包协议 ◐ 驱动待实测 / RKNN·ALSA·AEC3 ○ 需真机（laos 有 funasr/whistle 替身）；TimsFM_FDformer 私有不可克隆 |
| [2026-10-06-venue-expansion-survey.md](2026-10-06-venue-expansion-survey.md) | 顶会语料扩展普查（38 venue 整卷全量落库）：ACL Anthology bib dump + Crossref 期刊/会议双主通道 + DBLP/OpenReview 反爬实测证据 + laos 三主线交叉计数与覆盖缺口清单 | 合计 "**120,234 行**"= Anthology 42,939 + 期刊 19,860 + 会议 57,435；laos 命中 2,103（agent-os 880 / audio-speech 1,109 / spatial-privacy 114），"**窄治理分支仅 44 篇才是 laos 头条数**"；audio-speech 42% 为裸子串弱命中 |
| [2026-09-14-papers-oss-full-survey.md](2026-09-14-papers-oss-full-survey.md) | 论文 × 开源项目全量普查终版：数字全部由 `corpus/gen_final_report.py` 程序化读出 | "**统一语料 19,792 篇**"= ICASSP 2022-2026 共 14,285 + Interspeech 2021-2025 共 5,507；1,315 篇带摘要（Interspeech 摘要回填 89.1%） |
| [2026-09-18-jev-landscape.md](2026-09-18-jev-landscape.md) | Jev System-One 生态研究报告：TypeSafe AI 决策模型语义、三判型、定价与开源生态 | 语料"从 30 条扩到 **68 条**，全部实抓 GitHub API 元数据"；Noul/Choice/Score 三判型；$0.042/MTok（output 免费）、36kr 折算 0.44s / $0.00035 每次 |
| [2026-09-21-jev-decision-model-survey.md](2026-09-21-jev-decision-model-survey.md) | Jev 决策模型调研：技术实质、开源生态与 laos 落点（11 处硬阈值映射） | "GitHub Search API 全量抓取（1443 条原始 → 去噪 778 条）"；laos 11 处硬阈值/朴素相似度；edgejev 实测 3 题批量 median **157.5 ms**（README 宣称 15.6 ms 被否证，慢约 10×） |
| [2026-09-18-jev-chat-jarvis-assessment.md](2026-09-18-jev-chat-jarvis-assessment.md) | jev-chat-jarvis（Jev 聊天助手 Android 版）评估裁决：拒绝其采集链路、采纳校准台与问句方法论 | 产品 v1.4（CHANGELOG 2026-09-23）；"采集链路……踩 laos 五条合规红线中的四条，整体拒绝" |
| [always-on-recording-industry-2026-09.md](always-on-recording-industry-2026-09.md) | 全天候录音业界调研：产品、开源与技术机制（形态×处理位置×触发方式×开源闭源图谱） | "纯常开（always-on passive）阵营几乎全部倒下或被平台收购（Rewind→Limitless→Meta、Humane AI Pin→HP；Bee 2025-07 被 Amazon 收编）"；开源可抄管道 Silero VAD → sherpa-onnx/FunASR → Opus → SQLite+向量库 |
| [2026-10-07-agentos-governance-literature.md](2026-10-07-agentos-governance-literature.md) | venue-expansion 语料 agent-os 窄分支 49 篇逐篇对照（四组×capstone 四列裁决）＋八分类校验：无第九种"层"含义、两个含义级新强调 | "实测 **49 篇**（计划书按旧语料估 44，本批为实测数）"；状态汇总 "●已落地 1（#3）· ●已消化 9（#1/7/9/13/14/19/21/22/33）· ◐推荐 10（P2×4：#2/4/6/12；P3×6：#8/10/20/34/38/39）· ○不做 29" |
| [2026-10-07-dialog-spatial-retrieval.md](2026-10-07-dialog-spatial-retrieval.md) | 934 行强命中工作集的对话听觉四子题定向检索＋spatial-privacy 全量 114 行四小类归桶，逐线裁决 | §一 四子题计数 "barge/interrupt/full-duplex/turn-taking **4** · wake[- ]?word\|keyword spotting **27** · voice activity\|endpoint\|end-point **24** · diariz\|speaker separation **44**"；§二 "spatial-privacy 主题 114 行 = binaural/spatial/beamform/acoustic-camera 类 **105** + audio watermark 类 **9** + speech privacy 类 **0** + 其他 **0**（105+9+0+0=114，分类完备）" |
| [2026-10-07-slvdev-mcu-genai.md](2026-10-07-slvdev-mcu-genai.md) | 小红书《单片机上跑起生成式模型》复现与采纳：slvDev 三项目（esp32-ai 已克隆复现；stm32-diffusion·stm32-voice **2026-10-08 复核定性：仓库现不存在**——带凭据 404+34 仓清单无此名+全局搜索无果）——28.9M PLE TinyLM 在 Windows 宿主跑通，附嵌入式导航三层解答 | 复现实态 "staging_verify **PASS（0 失败）**…贪心生成 **481 tok/s** host-x86（ESP32 板端 9.88 同一份 llm.h）"；"OSFY『2.89 亿参数』系 **28.9M 十进制误读**（仓库实测证实）；'transcription/dictation' 宣称全仓零实现"；模型 14.91MB / Vin=32768 / L=6 / PLE 维 128 / group=128 |
| [2026-10-07-cloudflare-clef.md](2026-10-07-cloudflare-clef.md) | 小红书《38.8毫秒返回分类答案》学习与 laos 判断层对照：Cloudflare Clef/Clef-flash 决策模型（2026-10-01，Birthday Week 2026）——笔记四条声称逐条核实（38.8ms 真实=决策延迟非首 token；llama.cpp-SURGE/✨Spark/定价曲线三条 46 公告与原文均无，转译链讹变不采信） | "Clef-flash 中位 **38.8ms**/p95 122.4（vs Jev 524.1）——非自回归 prefill-only+schema 选项并行打分"；Qwen3.5-9B 基座+rank-256 LoRA+routing head，**Apache 2.0**（HF Cloudflare/clef-flash）；schema=noul/choice/score 与 laos 三判型同源；裁决=Clef-flash 本地实测 ◐P2/非自回归架构 ●已消化/校准 Brier+RLCD ◐P3/云端 ○ |
| [2026-10-08-espclaw-vs-muse-agent-core.md](2026-10-08-espclaw-vs-muse-agent-core.md) | 小红书《Agent本体能力对比，ESP-Claw vs Muse-Gad》复现与采纳：双仓溯源证实（espressif/esp-claw MCU 闭环框架 + facebookincubator/muse-gadget-sdk=Meta Muse Gadgets 2026-10-02 开源）——架构对照七构件表，claw_cap 能力框架落地为 laos/caps.py | muse Linux SDK 测试套件双环境实跑："Windows **142 passed / 1 failed / 1 skipped**（唯一失败=test_identity_persists 的 Unix 0o600 断言，Windows st_mode 恒 0o666，环境差异非 bug）；**WSL 原生 167 passed / 1 skipped in 9.43s**"；esp-claw 构建烧录 BLOCKED（无板无 ESP-IDF）；笔记数字声称 ○未证实×2（拓展坞 8GB/128GB vs 4GB/64GB、RESTful 16 Agent 上限）；caps 落地 30c15f7 全套 **861 绿** |

| [2026-10-08-jitmem.md](2026-10-08-jitmem.md) | 小红书《JitMem：让记忆在使用时再被理解》复现与采纳：论文 arXiv:2609.27334（Salesforce 系，GRPO 训 Curator，ALFWorld/WebShop/τ²-bench +16.2/+16.3/+3.9）——read-time curation 四步循环转译落地为 laos/jitmem.py + mem.curate/mem.outcome 内建 syscall | 论文一手事实全部 ●证实（笔记 4 帧转译零讹变）；**untrained curator 已打平 write-time 基线**是规则版 v1 立论支点；GRPO 8×H200 BLOCKED-by-design（零依赖红线），降级为首条优势归因 bandit（即时成败 reward 原样保留）；主库 **884 绿**（861+23），原文永不截断（论文核心主张：摘要丢操作约束） |

| [2026-10-08-readable-output.md](2026-10-08-readable-output.md) | 小红书《如何让 AI 输出更容易理解》复现与采纳：溯源 Karpathy 原帖 2026-10-02（四阶梯 ASD-STE100/图表/交互页/解释视频）——约束语言落地为 laos/ste.py check-only lint、调用链落地为 laos/traceviz.py（audit→mermaid）+ laosctl traceviz | 四阶梯×裁决表：①②●落地 ③◐P2（laosweb）④○不做（双红线）；**笔记"格式越好懂错误藏得越深"未见于原帖，系转译层增补**，采纳为双层结构治理原则（派生物必须能回到原始记录）；ASD 官方 ~900 词表再分发受限不收录（与 asd-ste100-skill 同取舍）；kernel LAOS_STE_LINT=1 钩子 lint JitMem briefing 记审计；主库 **911 绿**（884+27） |

| [2026-10-08-dialogflow-assembly.md](2026-10-08-dialogflow-assembly.md) | 排队波次兑现（非笔记复现）：esp-claw 事件规则表 P2 兑现（laos/evroute.py：JSON 热载+CRUD+consume_on_match/fail_open+三动作映射）+ 对话管线装配（laos/dialogflow.py：入口防火墙→WakeGate→队列→JitMem curate/outcome 闭合）+ 三件债清账 | v0.21.0 债：phase=done 补发（同 turn_id 配对）、LAOS_WAKE_*/LAOS_DIALOG_* env 覆盖、diary 跨代聚合（gz 归档按数字代序+活文件拼接）；64MB 水位核对已实装（telemetry max_bytes+写前归档）；P3 两项对照收档（phase 语义域不同不硬搬/双分区播种对个人记忆库不适用）；sink 两参协议坑记录（safe_emit 按设计吞 TypeError）；主库 **942 绿**（911+31）；排队清底补记：**sherpa-onnx KWS 实测完成**（zipformer 3.3M int8，唤醒词检出零误报，解码中位 7.56ms/p95 8.47ms@Windows CPU，SAPI 离线合成测试音）、豆包 TTS BLOCKED（无 key） |解码中位 7.56ms/p95 8.47ms@Windows CPU，SAPI 离线合成测试音）、豆包 TTS BLOCKED（无 key） |

| [2026-10-08-aios-agentos-landscape.md](2026-10-08-aios-agentos-landscape.md) | 三轨全景调研（AIOS/AgentOS 格局 + Linux 原生路线 + 全天候录音增量）：四派分层判定（framework/沙箱VM/**OS 内核派空位**/端侧）+ 真内核碎片清单（sched_ext-SchedCP/AgentSight/Landlock-nono/Anthropic srt/systemd-mcp）+ 苹果 Audio Intelligence 入场分析 + Linux AgentOS demo 设计（=plans/2026-10-08-agentos-demo.md 的 spec） | **源码级铁证：AIOS 调度器=threading.Thread（用户态模拟）**；三个空白点（几百行 agent-OS 教学 demo 不存在/socket-activated MCP 无案例/agent-cgroup 无项目）；商用大厂零 OS 隐喻（Anthropic containment 博客：93% 批准率/钓鱼 24/25 外泄仅靠 egress 拦）；全天候七因清单（社会许可>技术）+ Plaud 公式（按钮显式+会议场景，100 万台）；laos 红线与苹果 2026-09 范式逐条同频（不留音频/只录自己/本地优先空位） |

| [2026-10-08-nanomuse.md](2026-10-08-nanomuse.md) | nanoMuse 学习（论文 arXiv:2610.08699+源码 33 次 API 直读）：Meta Muse 开源对照物的 Sentinel 动作闸/taint/scoped grants/记忆双线全拆解——laos 采纳落地 laos/sentinel.py + provenance | Sentinel 六级判定序+taint 永不回退+warnings 仅 once 档（20 例测试）；自认“policy 边界非特权边界”=laos caps+seccomp 的差异化定位；Muse 复刻段（seccomp+kernel taint+Sentinel 唯一权限权威）为 laos 叙事商业印证；GPL 红线=只学设计零代码拷贝 |

| [2026-10-08-nanomuse-ui-xdevice-reference.md](2026-10-08-nanomuse-ui-xdevice-reference.md) | nanoMuse/Muse 全参照清单（功能 16 屏/界面十决策/全端兼容架构）：一套 Web UI+每端薄桥（Android WebView 14 方法桥含 7 厂商保活矩阵/Electron 桥/PWA 四件套）——laos 取经手册 | 审批 API 三字段（approved/scope/reason）与 laos GrantStore 同构直抄；React 技术栈不抄（零依赖纪律，抄设计语言）；采纳 #1-#5 → [laosweb v3 计划](../superpowers/plans/2026-10-08-laosweb-v3.md)；Android 保活厂商矩阵收录为 AlwaysOnRec 端侧化波必引知识；§7 目录组织学=仓库卫生波 spec |

| [2026-10-08-arvis.md](2026-10-08-arvis.md) | ARVIS 学习（XHS 笔记 404 → GitHub 溯源 GHJ20001017/Full-Duplex-Model，Apache-2.0，HF speech-to-speech 修改版）：级联式全双工工程解法全拆解——AEC3 回声消除/双档打断路由（keyword 保守门 13 词 backchannel 白名单 + jev 协议 0.6B 语义路由 wait-continue-yield）/话轮 revision 化投机重开/播报时窗/保留信封守卫 | 语义路由 **120ms 超时失败保守** + 首句豁免 + WAIT 反问锁 tool_choice；TurnController：9 显式打断短语/13 附和词/280ms 最短语音/3 字符阈值；**语义路由请求体=jev 协议原文（与 laos 判断层同方言）**；CancelScope 与 laos GenerationGate 同构互证、sherpa-onnx KWS 双边同款；**R1/R2/R3 已落地 v0.30.0**（c51a46a，1016 绿）；AEC3 走驱动子进程参照（MicrophoneGate aec_ready 预留位吻合）、e2e 训练侧不采纳 |

| [2026-10-08-muse-gadget-sdk.md](2026-10-08-muse-gadget-sdk.md) | Muse Gadget SDK 学习（XHS 404 → 仓库直读；Muse 本体 2026-09-23 Meta Connect 发布、SDK 2026-10-02 开源）：官方端云治理链全拆解——agent 在租用 VM/能力在端/凭据与执行分账户；executor 治理四招 + Noise XX 链路 + 43 技能 Markdown-only 五段式 | **run_as 非特权账户执行（服务账户持凭据永不执行）**修正姊妹篇"全账号直授"表述；输出预算 **json.dumps escape 感知收缩**（96KiB 循环缩 3/4）；file.write 分块+sha256+原子替换与 laos cow.py 同构互证；技能五段式 Identify/Prerequisites/Workflow/**Verify the Result**/**Limits**；裁决 A1 五段式惯例/A2 裁剪设计参考采纳、Noise/租用 VM 不采纳（云依赖红线） |

| [2026-10-09-rsi-landscape.md](2026-10-09-rsi-landscape.md) | RSI（递归自我改进）方向全景：小红书《RSIGym》笔记登录墙后按预案从一手来源重构（诚实声明在文内）——2026-09/10 论文浪潮九篇 + ICLR 26 RSI Workshop 110 篇 + 开源生态盘点 + 产业动态（智谱/小米/阿里/Anthropic）+ laos「进化循环外裁判席」裁决 | RSIGym（arXiv 2610.10310）Opus 5 **RSI-Index 0.4809**（SWE-bench 17.67→50.33%、AIME 31.67→97.78%、$500/基准）；AIDE² 8 天 7 改进但 **reward hacking 仍 32%**；Weng 七瓶颈之五"**评估器与权限须在进化循环之外**"= laos 定位行业级佐证；PostTrainBench 自动化后训练 23.2% vs 人类 51.1%；裁决 ●叙事×2 / ◐对照×5 / ○复现×1（重依赖全线违反零依赖红线） |
| [2026-10-09-xhs-qwen-audio-agent-runtime.md](2026-10-09-xhs-qwen-audio-agent-runtime.md) | 小红书《Voice Agent 的真正壁垒可能不是语音模型》单篇学习（jimmy_cat，1 篇 2 图逐图转写）→ QwenAudio/qwen-audio-agent v2.0.0 + arXiv:2609.25195 三链核实**零讹变**——Frontend/Backend Agent + Orchestration Runtime，两个解耦（打断≠取消、完成≠交付）上升为 runtime 法定职责，"Voice Model ≠ Voice Agent" | 座舱基准 "134 cases…mixed execution achieves a task success rate of **91.04%**, compared with **72.39% and 80.60%**"、"reduces mean task execution latency by **26.73% and 30.91%**"（摘要原文）；裁决 ●叙事/互证×3（两解耦=OS 信号语义、mixed execution=调度策略证据）+ ◐ACP/A2A 对照 + ○不引 Node.js 本体（零依赖红线）；"完成≠交付"半边为 laos 后台任务语音化第一缺口 |
| [2026-10-09-interspeech2026-se-trends.md](2026-10-09-interspeech2026-se-trends.md) | 微信公众号《Interspeech 2026 语音增强技术风向》（声息实验室）学习与溯源：115 篇（67 SE+29 TSE/分离+10 ANC/声区/丢包+9 评测）六风向——一步生成式（SBM arXiv:2510.16834 ●）/幻觉记账（StuPASE/UniSE/ETH 多指标奖励）/延迟旋钮/Enroll-on-Wakeup（arXiv:2602.15519 ●，唤醒词段免费注册音）/Ouroboros 前端后门 | 裁决 D1–D8：EoW 说话人自适应 ◐ 远线（触发=A 档真机∧多说话人 CER 实测劣化，与 AEC3 同波）；"生成式修复不入记忆链路"红线（auto-gain/04:24）**获学界正面印证 ●**；Ouroboros=治理前置第四条印证链（Anthropic/Muse/dots 之后）；ASR-as-judge 盲区→评测裁判须与被测通道异源；延迟旋钮与 dialogsched 预算家族同构互证；纯学习波代码零改动 |
## 二、全天候录音调研组（always-on-recording/，5 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [always-on-recording/2026-09-landscape.md](always-on-recording/2026-09-landscape.md) | 五条调研线的收敛结论与索引（产品/学术/硬件/接受度/垂直应用的入口） | "16 个产品里 `always_on=常开被动` 的只有 **2 个**（Rewind、Limitless），且**两个都死了**" |
| [always-on-recording/2026-09-11-verticals-apple-articles.md](always-on-recording/2026-09-11-verticals-apple-articles.md) | 增量补充篇：B 端垂直赛道（会议/医疗/销售/无障碍）+ Apple Watch S12「音频智能」专题 + 文章语料 | "云常开 = 已死，端侧克制常开 = 刚被苹果转正"（Apple Watch Series 12 Siri Recap，2026-09-10 发布，环形缓冲 + 端侧蒸馏 + 7 天自动删除） |
| [always-on-recording/academic-papers.md](always-on-recording/academic-papers.md) | 学术论文线：可穿戴长期录音 / 事件检测 / 说话人日志 / 纵向健康追踪等六方向逐篇表格 | "47 nW 的 VAD、988 nW 的 KWS 均已流片验证"；ESC-50 97%+；DIHARD III 真实场景 DER 中位数 35–45%；Ego4D 3,670 h / 931 人 |
| [always-on-recording/hardware-power.md](always-on-recording/hardware-power.md) | 端侧硬件与功耗：把「常开」换算成 laos 能用的预算数字，并钉死 proot/Termux 架构下哪些做不到 | 功耗阶梯跨 4 个数量级："定制 ASIC 上亚微瓦（0.047–1 µW）→ 专用音频 NPU 上百微瓦（140 µW）→ 手机传感中枢/aDSP 上数毫瓦 → 应用处理器上数百毫瓦到数瓦"；电池基准 5000 mAh × 3.85 V = 19.25 Wh |
| [always-on-recording/social-acceptance.md](always-on-recording/social-acceptance.md) | 社会接受度实证研究 + 2024–2026 争议事件时间线（不含法条，法条在业界篇 §7） | MeMic（CHI EA '24）在线对照 **N=168**：只录自己显著提升接受度；CHI'26 **N=525**：场景主效应 F=56.440, p<.001；旁观者"只有 6.1% 认为单靠 LED 就够" |

## 三、模型地图支撑卷宗（speech-emotion/ 8 份、audio-events/ 8 份、auto-gain/ 8 份；2026-10-08 语音三域收尾波补齐 16 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [speech-emotion/00-taxonomy-and-metrics.md](speech-emotion/00-taxonomy-and-metrics.md) | SER 组唯一口径来源：为什么是「3 档 × 2 标记」分档法 + 12 列记录 schema | 分档"小型 `[0, 30M)`、中型 `[30M, 500M)`、大型 `[500M, +∞)`"；校验器 `scripts/check_ser_table.py` |
| [speech-emotion/01-small-models.md](speech-emotion/01-small-models.md) | SER 小型档（<30M）检索与核实数据表（只记录、不推荐） | YAMNet 3.7M（Acc 56.1, IEMOCAP 4 类）；openSMILE ComParE_2016 6,373 维特征（Acc 62.1, IEMOCAP） |
| [speech-emotion/02-medium-models.md](speech-emotion/02-medium-models.md) | SER 中型档（30M–500M）数据表 | wav2vec 2.0 base 95.04M（IEMOCAP UA 58.27）；30M 归本档、500M 归大型档 |
| [speech-emotion/03-large-models.md](speech-emotion/03-large-models.md) | SER 大型档（>500M）数据表，区分纯音频大模型与「ASR + LLM 两段式」两条路线 | 参数量"按口径写**两段之和**"；大型档"几乎被语音大模型 / LLM 路线占满" |
| [speech-emotion/04-edge-deployment.md](speech-emotion/04-edge-deployment.md) | 端侧部署轴：在 laos（Android + proot Ubuntu + Termux）语境下「端侧可部署」到底是什么意思 | "「端侧可行」在 laos 语境下不是一个布尔值，而是两个互斥的档位"（功耗阶梯只引用不重算） |
| [speech-emotion/05-multimodal.md](speech-emotion/05-multimodal.md) | 多模态轴：laos（纯音频 → 触发后 ASR 蒸馏）要不要为情感识别加视觉通道 | 结论"**不引入。且是「默认永久不做」，不是「条件性暂缓」**" |
| [speech-emotion/2026-09-landscape.md](speech-emotion/2026-09-landscape.md) | SER landscape 交叉与收敛篇：只做交叉不新增记录 | 数据基础"17 条 + 18 条 + 11 条 = **46 条记录**，全部通过 `scripts/check_ser_table.py` 校验" |
| [speech-emotion/06-adoption.md](speech-emotion/06-adoption.md) | SER 落地篇（收尾 Task 1）：HY4 ear 通道采纳——引入 opt-in 通道 **sherpa**（一次前向同出文本+情感），classify_mood 保留零成本兜底（补充不替换） | "ONNX INT8 228–229 MB；10 s ≈70 ms（RTF≈7×10⁻³）"；不做什么三条（不声纹/非临床/视觉不进 HY4）；HY4 落地 e76e0b4（AOR_ASR_CHANNEL=sherpa + AOR_SHERPA_DIR，**152 全绿** 147+5） |
| [audio-events/00-taxonomy-and-metrics.md](audio-events/00-taxonomy-and-metrics.md) | AED 组唯一口径来源：任务类型 / 规模分档 / 指标 / 记录 schema（沿用 SER 12 列骨架 + AudioSet 划分口径） | 校验器 `scripts/check_aed_table.py`（复用 `scripts/table_lint.py` 通用核心） |
| [audio-events/01-small-models.md](audio-events/01-small-models.md) | AED 小型档（<30M）：DCASE Low-Complexity 硬约束赛道是端侧事实标准（19 条） | "128 KiB/30 MMACs 约束下的最高准确率一直在 **60.8% → 62.7% → 62.1% → 61.5%** 的窄带里，**没有趋势性提升**"；YAMNet mAP 0.306 (AudioSet AS-2M full, tagging)、edge "yes: TFLite Micro" 全档唯一 |
| [audio-events/02-medium-models.md](audio-events/02-medium-models.md) | AED 中型档（30M–500M）：精度甜点（28 条；AS-20K 与 AS-2M full 全档区分，同模型双报主表记 full） | AST **0.459** / PaSST-S **0.471** (AudioSet AS-2M full, tagging, 单模型；集成 0.485/0.496)；"中型档是 AED 的精度甜点" |
| [audio-events/03-large-models.md](audio-events/03-large-models.md) | AED 大型档（>500M）：开放词表代价（11 条；区分纯判别/端到端音频大模型/两段式三结构） | "DASM 的 **42.2 是 PSDS1**"（DESED 零样本，初始线索 0.422 核实成立）；"53.7 是 X-Ares 片段级准确率…**两者不可比**" |
| [audio-events/05-edge-deployment.md](audio-events/05-edge-deployment.md) | AED 端侧轴：runtime/量化证据 + proot 现实核对（判定点：常驻 AED 在 B 档是否可接受） | 结论**不可接受**：B 档 400–1000 mW 常驻税 vs ≤25 mW 预算；DCASE 获奖系统"多数只有 PyTorch 权重"是端侧档真实缺口 |
| [audio-events/06-multimodal.md](audio-events/06-multimodal.md) | AED 多模态轴：A+V 的真正增量是事件**定位**而非分类；数据集表含许可列 | 视觉不进 HY4（SER 05 立场在 AED 语境独立复核后**维持**：合规成本 + 与即焚互斥） |
| [audio-events/2026-09-landscape.md](audio-events/2026-09-landscape.md) | AED 收敛篇：交叉表 + 中文场景空白（特有必写节）+ 常驻升级判定 + 选型决策树 + HTML 全景（docs/audio-event-models.html） | 记录 01(19)+02(28)+03(11)=**58 条**；判定"**不做'常驻事件级检测'；有条件做 = 事件驱动**"；中文空白"不得用英文基准结论冒充中文可用性" |
| [audio-events/07-adoption.md](audio-events/07-adoption.md) | AED 落地篇（收尾 Task 8）：**暂不引入**——B 档维持 VAD 能量门（StreamingVAD，rec.py:233，−35 dBFS）；含对 landscape §4 推荐分支的推翻记录 | "只要 ① 不成立（当前 B 档）且 ② 未做中文微调，结论维持「暂不引入」"；不做什么三条（不全 521 类常驻/不视觉/不让 AED 单独触发留存）；HY4 不改代码 |
| [auto-gain/00-taxonomy-and-metrics.md](auto-gain/00-taxonomy-and-metrics.md) | AGC 组唯一口径来源：作用点 / 控制对象 / 规模分档 / 自测口径 / 记录 schema | 分档"「经典 DSP 档 + 3 档 × 2 标记」"；校验器 `scripts/check_agc_table.py` |
| [auto-gain/01-classical-dsp.md](auto-gain/01-classical-dsp.md) | AGC 经典 DSP 档（实际主力）+ **二次增益判定点**：Android AudioSource 是否默认施加 AGC 三层检索 | "结论（三选一，不许含糊）：**不确定 —— 需真机验证**"（给出扫频/白噪线性检验法）；WebRTC AGC2 两段结构（模拟段+数字段+内置噪声门）必收 |
| [auto-gain/02-small-models.md](auto-gain/02-small-models.md) | AGC 小型神经档（<30M，10 条）：绝大多数只做降噪掩码**不做增益控制**（降噪≠增益，不得混记） | "唯一的真·联合 SE+AGC 工作是 SE-AGCNet…不进 schema 表（GC 4：查不到参数量就不入表）"；纯电平调整上神经方案"没有证据"（不许用噪声场景数字替代） |
| [auto-gain/03-medium-models.md](auto-gain/03-medium-models.md) | AGC 中型档（30M–500M，4 条）：**该档稀疏**——无以增益控制为主业的模型，4 条全是相邻（语音分离） | "印证了 00 的预期假设（中型档稀疏，不得为凑数灌水），**未推翻**它"；QDPN 按来源规则剔除 |
| [auto-gain/04-large-models.md](auto-gain/04-large-models.md) | AGC 大型/生成式档（6 条）：不是选型池，回答"生成式做增益/修复值不值"；参数量+NFE/RTF 双必填 | 幻觉风险：生成式会"补出"输入中不存在的语音内容 → 在"原音频即焚+只留文本"架构下=无来源记忆进转写（Task 16 引用为否决依据） |
| [auto-gain/05-edge-deployment.md](auto-gain/05-edge-deployment.md) | AGC 端侧轴：三处作用点可得性表（aDSP 不可达/离线）+ 常驻增益功耗账 | "采集前（A 档）物理可达但 laos 工程不可达；采集后（B 档）是 laos 唯一能落的点，但被 400–1000 mW 常驻税笼罩" |
| [auto-gain/06-multimodal.md](auto-gain/06-multimodal.md) | AGC 多模态象限判定：**非空——"AGC 多模态预期为空"被证伪**（≥3 条真实工作，检索词逐条留档） | "判定：非空"；物理直觉（增益是瞬时电平闭环，视觉不提供瞬时电平信息）被真实工作推翻，如实回写 |
| [auto-gain/2026-09-landscape.md](auto-gain/2026-09-landscape.md) | AGC 收敛篇：交叉表 + "AGC 到底是不是模型问题"结论锚点 + 加在哪层决策表（含"什么都不加"行）+ 即焚兼容性 + HTML 全景（docs/auto-gain-models.html） | **"结论：分层 —— 闭环增益是 DSP 问题，噪声 + 音量不平衡场景是模型问题。不许骑墙。"**；增益只作用于送推理的副本，生成式不得用于产生记忆的链路 |
| [auto-gain/07-adoption.md](auto-gain/07-adoption.md) | AGC 落地篇（收尾 Task 16）：**不加**——HY4 捕获链不动（二次增益不确定 + dbfs 原始电平语义必须保留） | 触发条件留档（"若未来切到 UNPROCESSED 或原生拿到未处理 PCM，重新评估"）；不做什么三条（不在采集前层做/不生成式/不作用于留存副本） |

## 四、OSS 普查支撑（oss/，3 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [oss/oss_fetch_summary.md](oss/oss_fetch_summary.md) | OSS 抓取摘要（去噪 + 引号短语补抓后） | "合并后总数：**3724 条**（去噪保留 2153 + 补抓新增 1571）"；补抓泄漏复核 1850/1850 命中音频域判据 |
| [oss/oss_audit.md](oss/oss_audit.md) | OSS 语料审计与去噪报告（可解释相关性判据） | "总仓库数（去重）：3529"；剔除噪声共 1376 条（audio-llm/voice-agent 裸词切片） |
| [oss/classification_system.md](oss/classification_system.md) | Task 3 分类体系与 laos 适配映射（规则可复现） | "分类体系（13 类，可多标签）"；源数据 `repos_raw.jsonl` 3724 条（注：终版报告分类数为 15 类，两处不一致时以终版报告 15 为准） |

## 五、Jev 调研支撑卷宗（jev/，8 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [jev/00-taxonomy-and-metrics.md](jev/00-taxonomy-and-metrics.md) | Jev 组唯一口径来源：决策模型实质 / 三原语 / 12 列 schema / 校验器；防编造纪律 | 校验器 `scripts/check_jev_table.py`；"凡查不到的字段一律记 `未知`……**不许编造 star 数、延迟或许可**" |
| [jev/01-official-and-clients.md](jev/01-official-and-clients.md) | Jev 官方与客户端（SDK / MCP / Agent Skill）清单 | 官方/客户端封装 TypeSafe 云端 API、中国大陆未开放 →"laos_fit 一律 unrelated"；browser-use/jev-ultrafast 11101 星 |
| [jev/02-oss-reproductions.md](jev/02-oss-reproductions.md) | Jev 开源复现清单（"本次调研核心文档"），区分真复现与单 token 打分 | 命门："「复现」与「复现(单token打分)」必须区分（口径 J9）"；TheoLeeCJ/SemIf 2286 星、TianyuCodings/NanoJev 1309 星 |
| [jev/03-oss-applications.md](jev/03-oss-applications.md) | Jev 开源应用与生态（browser / voice / android / guard / 清单 / 评测 / 工具） | 语音+常驻先例线：moritzkremb/jev-voice-browser 147 星；多数仍走官方云端 API，laos_fit 多标 ref |
| [jev/04-ondevice-benchmark.md](jev/04-ondevice-benchmark.md) | 端侧候选本机实测（Task 4 唯一交付：Windows x86 CPU 真数字 + 外推 Android） | edgejev：ONNX int8 模型 **324.5 MB**、3 题批量 median **157.5 ms**、峰值 RSS **495 MB**、首次加载 **2.1 s**；"README 宣称的「单题 15.6 ms」是在 Xeon AVX512-VNNI 上的硬件特例" |
| [jev/05-laos-placement.md](jev/05-laos-placement.md) | laos 判定点映射与落点清单（Task 5 设计产出）：魔法数字 → Jev 三原语，收益/代价/排除理由 | "常驻每帧调用 → 持续 **0.5–1.5 W** 附加（否决）；离线/二级确认档 → 常摊 **4.6 mW** 量级（可接受）"；"不沿用任何 README 宣称值" |
| [jev/06-clef-mapping.md](jev/06-clef-mapping.md) | Clef 落地对照（v0.22.0）：三路线选型表（rules ~0ms 实测 / edgejev 157.5ms 实测 / clef-flash 38.8ms 边缘 GPU 引用）＋非自回归架构定论＋Brier/RLCD 校准方法库映射 | "38.8ms 是**引用**：Cloudflare 边缘 GPU 实测……laos 不复现该口径的硬件前不进默认链"；qemu chroot 加载实测 **19.4s**、单发未取得（内存压力 c10 崩溃，GFLOPS 外推 ≈85min/次）；引用与本地实测"**永不混写**" |
| [jev/fetch_summary.md](jev/fetch_summary.md) | Jev GitHub 全景抓取摘要（Task 2） | "原始抓取（去重后，含噪声）：**1443** 条……精度判据保留 / 交付（repos_raw.jsonl）：**778** 条"；剔除噪声 665 条 |

## 六、corpus/ 与数据语料（数据文件，只列规模）

**论文/OSS/Jev 统一语料（corpus/）**：

| 文件 | 规模 |
|---|---|
| `corpus/papers_unified.jsonl` | **19,792 行**（实测 `wc -l`；= ICASSP 14,285 + Interspeech 5,507，报告口径同） |
| `corpus/icassp2022_papers.json` … `icassp2026_papers.json` | 1863 / 2720 / 2699 / 3163 / 3840 篇（`icassp_census_summary.md` 口径），单文件 544K–1.2M |
| `corpus/interspeech_corpus.json` | 3.5MB，Interspeech 2021–2025 全量 5,507 条（`.bak` 旧版 2.1M） |
| `corpus/icassp_corpus_2022_2023.json` | 1.4MB（2022–2023 合并语料） |
| `corpus/icassp_s2_raw.json` / `icassp_s2_round2.json` / `icassp_s2_round3.json` | Semantic Scholar 主题切片 84K / 416K / 635K |
| `corpus/oss_corpus.json` | 1.6MB 原始 OSS 抓取（另有 `oss_top30_summary.json` 13K） |
| `corpus/jev_repos.json` / `jev_repos_curated.json` | 160K 原始 / 20K 精选（报告口径 68 条） |
| `corpus/*.py`（6 个） | 抓取与生成脚本：`crawl_icassp.py`、`crawl_icassp_openalex.py`、`crawl_icassp_s2.py`、`crawl_icassp_s2_round3.py`、`crawl_github_oss.py`、`gen_final_report.py` |

**corpus/ 下 .md 语料快照（17 份 = 直属 7 份 + `oss_top30_readmes/` 10 份，非作者撰写综述）**：

| 文件 | 内容 / 规模 |
|---|---|
| `corpus/appendix_interspeech_lists.md` | 自动生成的 Interspeech 相关论文全列表：codec 109 / kws_vad 113 / event 67 / emotion 321（截前 120）/ diariz 227 篇，647 行 |
| `corpus/icassp_census_summary.md` | ICASSP 2022-2026 普查覆盖率表：96.0%–104.4%，0 异常 |
| `corpus/is2026_status.md` | Interspeech 2026 上线探测：ISCA 存档 HTTP 404，"Interspeech 上限只能到 2025" |
| `corpus/jev_readme_*.md`（4 份） | NanoJev / simple-jev / jevlike / awesome-jev 的 README 快照（132–381 行） |
| `corpus/oss_top30_readmes/*.md`（10 份） | Top30 OSS 项目 README 快照（FunASR、Speech-AI-Forge、UltraEval-Audio 等，167–2003 行） |

**兄弟数据目录**：`papers/`（论文 PDF 全文库，147 个 PDF + MANIFEST.txt，索引见 `papers_index.md`）；`oss/repos_raw.jsonl` 3724 行 / `repos_classified.jsonl` 3724 行 / `repos_fetched.jsonl` 1850 行 / `noise_dropped.jsonl` 1376 行。

## 七、计划文档（docs/superpowers/plans/，调研执行相关）

| 文件 | 一句话定位 |
|---|---|
| `plans/2026-09-11-always-on-recording-research.md` | 全天候录音行业调研（文章 + 开源项目）实施计划（六维度全景报告） |
| `plans/2026-09-11-always-on-recording-landscape.md` | 全天候录音业界全景调研实施计划（五条线 → 带分类学的全景文档 → 反向映射四段漏斗） |
| `plans/2026-09-11-always-on-recording-capabilities.md` | laos 全天候录音能力补齐实施计划（四级 mic 阶梯 + Opus 配额 + 常开模式 + 流式 ASR） |
| `plans/2026-09-11-speech-emotion-models.md` | SER 模型调研实施计划（规模分档 × edge/multimodal 双标签） |
| `plans/2026-09-11-audio-event-models.md` | AED 模型调研实施计划（回答「常驻检测能否从 VAD 能量门升级为事件级检测」） |
| `plans/2026-09-11-auto-gain-models.md` | AGC 模型调研实施计划（先回答「它到底是不是一个模型问题」） |
| `plans/2026-09-14-icassp-interspeech-census.md` | 双会议五年论文普查实施计划（Crossref + ISCA 双源，取代抽样版） |
| `plans/2026-09-13-full-traversal-papers-and-oss.md` | ICASSP 全量枚举 + 音频/AI/Agent 开源全量搜索实施计划（数据程序化生成报告） |
| `plans/2026-09-14-audio-ai-agent-oss-landscape.md` | 开源项目星标调研实施计划（GitHub Search API → 四段漏斗适配结论） |
| `plans/2026-09-18-jev-system-one-layer.md` | Jev「System One」判断层学习/普查/落地实施计划（`laos/judge.py` 三判型） |
| `plans/2026-09-21-jev-decision-model-survey.md` | Jev 决策模型调研与 laos 落点实施计划（实测端侧 + 判定点映射） |
| `plans/2026-09-18-jev-chat-jarvis-assessment.md` | jev-chat-jarvis 评估与选择性采纳实施计划（拒绝伪装机制、采纳三项工程实践） |
| `plans/2026-09-19-laos-adoption-capstone.md` | 本 capstone 总纲：全部调研资产按 laos 架构逐项映射为「可取之处 → 落点 → 状态」并产出本 INDEX |

## 八、评审与设计（docs/review/ · docs/design/，2026-10-07 上线前评审波次）

> 不在 docs/research/ 树内（../review/ 与 ../design/），但同属 INDEX 资产口径（头部 +3 的来源）；交叉核对（2026-10-07，Task 4）：需求 §6 的 P01–P15（15 类）== 设计 §5 矩阵 15 行；技术 §4 的 R1–R11（11 条）在设计 §4 发射点/预留位逐条有着落（R7/R8/R9 明记"不在埋点面"）。

| 文件 | 一句话定位 | 关键数字 / 规模 |
|---|---|---|
| [../review/2026-10-07-requirements-review.md](../review/2026-10-07-requirements-review.md) | 上线前需求评审：三形态定位 / 四场景完成度 / MoSCoW / Go-NoGo 九门槛（"可观测性（G8）是唯一系统性 NO-GO"）——埋点设计的需求源头 | §6 上线后问题域清单"**编号冻结：P01–P15**"= **15 类**；§4.3 隐私红线 7 条（第 7 条为埋点预立约束） |
| [../review/2026-10-07-technical-review.md](../review/2026-10-07-technical-review.md) | 上线前技术评审：五层架构盘点 / 接口契约审计（稳·演化中·未冻结三档）/ ADR×5 / 测试覆盖盲区清单——埋点发射点覆盖面的技术源头 | §4 风险与债务表"**编号冻结（R1…R11）**"= **11 条**（R9 测试口径双轨为本评审新发现）；主库逐模块实跑合计 691 与 discover 互证 |
| [../design/2026-10-07-instrumentation-design.md](../design/2026-10-07-instrumentation-design.md) | 埋点设计（`laos/telemetry.py` 实现规格）：六类事件分类学 / 统一 schema 逐字段脱敏四级 / 发射点清单 / 问题→埋点诊断矩阵——消费两评审的冻结编号 | **23 事件 / 138 字段**（§2"六类，23 事件"；138 = 130 事件数据字段 + 信封 7 + 节流元字段 1，机械计数，含 dialog.turn `phase`）；矩阵 15 行全覆盖；voicenpu metrics 25 字段→采纳 22（§7 对照，"22 个可观测指标字段"）；**2026-10-07 已实现核心**（`laos/telemetry.py` + 10 钩子 + laosweb 复合键） |
