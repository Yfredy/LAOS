# docs/research 调研资产清单（INDEX）

> laos 调研资产权威清单：每份文档一句话定位 + 关键数字（均抄自各文档自身原文，未凭文件名推断）。
> 盘点日期：2026-09-27。共 59 份 .md（不含本文件，find 会数出 60）= 作者撰写的调研文档 42 份 + corpus/ 语料快照 17 份。

## 一、主报告（根目录，18 份）

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
| [2026-09-14-papers-oss-full-survey.md](2026-09-14-papers-oss-full-survey.md) | 论文 × 开源项目全量普查终版：数字全部由 `corpus/gen_final_report.py` 程序化读出 | "**统一语料 19,792 篇**"= ICASSP 2022-2026 共 14,285 + Interspeech 2021-2025 共 5,507；1,315 篇带摘要（Interspeech 摘要回填 89.1%） |
| [2026-09-18-jev-landscape.md](2026-09-18-jev-landscape.md) | Jev System-One 生态研究报告：TypeSafe AI 决策模型语义、三判型、定价与开源生态 | 语料"从 30 条扩到 **68 条**，全部实抓 GitHub API 元数据"；Noul/Choice/Score 三判型；$0.042/MTok（output 免费）、36kr 折算 0.44s / $0.00035 每次 |
| [2026-09-21-jev-decision-model-survey.md](2026-09-21-jev-decision-model-survey.md) | Jev 决策模型调研：技术实质、开源生态与 laos 落点（11 处硬阈值映射） | "GitHub Search API 全量抓取（1443 条原始 → 去噪 778 条）"；laos 11 处硬阈值/朴素相似度；edgejev 实测 3 题批量 median **157.5 ms**（README 宣称 15.6 ms 被否证，慢约 10×） |
| [2026-09-18-jev-chat-jarvis-assessment.md](2026-09-18-jev-chat-jarvis-assessment.md) | jev-chat-jarvis（Jev 聊天助手 Android 版）评估裁决：拒绝其采集链路、采纳校准台与问句方法论 | 产品 v1.4（CHANGELOG 2026-09-23）；"采集链路……踩 laos 五条合规红线中的四条，整体拒绝" |
| [always-on-recording-industry-2026-09.md](always-on-recording-industry-2026-09.md) | 全天候录音业界调研：产品、开源与技术机制（形态×处理位置×触发方式×开源闭源图谱） | "纯常开（always-on passive）阵营几乎全部倒下或被平台收购（Rewind→Limitless→Meta、Humane AI Pin→HP；Bee 2025-07 被 Amazon 收编）"；开源可抄管道 Silero VAD → sherpa-onnx/FunASR → Opus → SQLite+向量库 |

## 二、全天候录音调研组（always-on-recording/，5 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [always-on-recording/2026-09-landscape.md](always-on-recording/2026-09-landscape.md) | 五条调研线的收敛结论与索引（产品/学术/硬件/接受度/垂直应用的入口） | "16 个产品里 `always_on=常开被动` 的只有 **2 个**（Rewind、Limitless），且**两个都死了**" |
| [always-on-recording/2026-09-11-verticals-apple-articles.md](always-on-recording/2026-09-11-verticals-apple-articles.md) | 增量补充篇：B 端垂直赛道（会议/医疗/销售/无障碍）+ Apple Watch S12「音频智能」专题 + 文章语料 | "云常开 = 已死，端侧克制常开 = 刚被苹果转正"（Apple Watch Series 12 Siri Recap，2026-09-10 发布，环形缓冲 + 端侧蒸馏 + 7 天自动删除） |
| [always-on-recording/academic-papers.md](always-on-recording/academic-papers.md) | 学术论文线：可穿戴长期录音 / 事件检测 / 说话人日志 / 纵向健康追踪等六方向逐篇表格 | "47 nW 的 VAD、988 nW 的 KWS 均已流片验证"；ESC-50 97%+；DIHARD III 真实场景 DER 中位数 35–45%；Ego4D 3,670 h / 931 人 |
| [always-on-recording/hardware-power.md](always-on-recording/hardware-power.md) | 端侧硬件与功耗：把「常开」换算成 laos 能用的预算数字，并钉死 proot/Termux 架构下哪些做不到 | 功耗阶梯跨 4 个数量级："定制 ASIC 上亚微瓦（0.047–1 µW）→ 专用音频 NPU 上百微瓦（140 µW）→ 手机传感中枢/aDSP 上数毫瓦 → 应用处理器上数百毫瓦到数瓦"；电池基准 5000 mAh × 3.85 V = 19.25 Wh |
| [always-on-recording/social-acceptance.md](always-on-recording/social-acceptance.md) | 社会接受度实证研究 + 2024–2026 争议事件时间线（不含法条，法条在业界篇 §7） | MeMic（CHI EA '24）在线对照 **N=168**：只录自己显著提升接受度；CHI'26 **N=525**：场景主效应 F=56.440, p<.001；旁观者"只有 6.1% 认为单靠 LED 就够" |

## 三、模型地图支撑卷宗（speech-emotion/ 7 份、audio-events/ 1 份、auto-gain/ 1 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [speech-emotion/00-taxonomy-and-metrics.md](speech-emotion/00-taxonomy-and-metrics.md) | SER 组唯一口径来源：为什么是「3 档 × 2 标记」分档法 + 12 列记录 schema | 分档"小型 `[0, 30M)`、中型 `[30M, 500M)`、大型 `[500M, +∞)`"；校验器 `scripts/check_ser_table.py` |
| [speech-emotion/01-small-models.md](speech-emotion/01-small-models.md) | SER 小型档（<30M）检索与核实数据表（只记录、不推荐） | YAMNet 3.7M（Acc 56.1, IEMOCAP 4 类）；openSMILE ComParE_2016 6,373 维特征（Acc 62.1, IEMOCAP） |
| [speech-emotion/02-medium-models.md](speech-emotion/02-medium-models.md) | SER 中型档（30M–500M）数据表 | wav2vec 2.0 base 95.04M（IEMOCAP UA 58.27）；30M 归本档、500M 归大型档 |
| [speech-emotion/03-large-models.md](speech-emotion/03-large-models.md) | SER 大型档（>500M）数据表，区分纯音频大模型与「ASR + LLM 两段式」两条路线 | 参数量"按口径写**两段之和**"；大型档"几乎被语音大模型 / LLM 路线占满" |
| [speech-emotion/04-edge-deployment.md](speech-emotion/04-edge-deployment.md) | 端侧部署轴：在 laos（Android + proot Ubuntu + Termux）语境下「端侧可部署」到底是什么意思 | "「端侧可行」在 laos 语境下不是一个布尔值，而是两个互斥的档位"（功耗阶梯只引用不重算） |
| [speech-emotion/05-multimodal.md](speech-emotion/05-multimodal.md) | 多模态轴：laos（纯音频 → 触发后 ASR 蒸馏）要不要为情感识别加视觉通道 | 结论"**不引入。且是「默认永久不做」，不是「条件性暂缓」**" |
| [speech-emotion/2026-09-landscape.md](speech-emotion/2026-09-landscape.md) | SER landscape 交叉与收敛篇：只做交叉不新增记录 | 数据基础"17 条 + 18 条 + 11 条 = **46 条记录**，全部通过 `scripts/check_ser_table.py` 校验" |
| [audio-events/00-taxonomy-and-metrics.md](audio-events/00-taxonomy-and-metrics.md) | AED 组唯一口径来源：任务类型 / 规模分档 / 指标 / 记录 schema（沿用 SER 12 列骨架 + AudioSet 划分口径） | 校验器 `scripts/check_aed_table.py`（复用 `scripts/table_lint.py` 通用核心） |
| [auto-gain/00-taxonomy-and-metrics.md](auto-gain/00-taxonomy-and-metrics.md) | AGC 组唯一口径来源：作用点 / 控制对象 / 规模分档 / 自测口径 / 记录 schema | 分档"「经典 DSP 档 + 3 档 × 2 标记」"；校验器 `scripts/check_agc_table.py` |

## 四、OSS 普查支撑（oss/，3 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [oss/oss_fetch_summary.md](oss/oss_fetch_summary.md) | OSS 抓取摘要（去噪 + 引号短语补抓后） | "合并后总数：**3724 条**（去噪保留 2153 + 补抓新增 1571）"；补抓泄漏复核 1850/1850 命中音频域判据 |
| [oss/oss_audit.md](oss/oss_audit.md) | OSS 语料审计与去噪报告（可解释相关性判据） | "总仓库数（去重）：3529"；剔除噪声共 1376 条（audio-llm/voice-agent 裸词切片） |
| [oss/classification_system.md](oss/classification_system.md) | Task 3 分类体系与 laos 适配映射（规则可复现） | "分类体系（13 类，可多标签）"；源数据 `repos_raw.jsonl` 3724 条（注：终版报告分类数为 15 类） |

## 五、Jev 调研支撑卷宗（jev/，7 份）

| 文件 | 一句话定位 | 关键数字 / 规模（抄原句） |
|---|---|---|
| [jev/00-taxonomy-and-metrics.md](jev/00-taxonomy-and-metrics.md) | Jev 组唯一口径来源：决策模型实质 / 三原语 / 12 列 schema / 校验器；防编造纪律 | 校验器 `scripts/check_jev_table.py`；"凡查不到的字段一律记 `未知`……**不许编造 star 数、延迟或许可**" |
| [jev/01-official-and-clients.md](jev/01-official-and-clients.md) | Jev 官方与客户端（SDK / MCP / Agent Skill）清单 | 官方/客户端封装 TypeSafe 云端 API、中国大陆未开放 →"laos_fit 一律 unrelated"；browser-use/jev-ultrafast 11101 星 |
| [jev/02-oss-reproductions.md](jev/02-oss-reproductions.md) | Jev 开源复现清单（"本次调研核心文档"），区分真复现与单 token 打分 | 命门："「复现」与「复现(单token打分)」必须区分（口径 J9）"；TheoLeeCJ/SemIf 2286 星、TianyuCodings/NanoJev 1309 星 |
| [jev/03-oss-applications.md](jev/03-oss-applications.md) | Jev 开源应用与生态（browser / voice / android / guard / 清单 / 评测 / 工具） | 语音+常驻先例线：moritzkremb/jev-voice-browser 147 星；多数仍走官方云端 API，laos_fit 多标 ref |
| [jev/04-ondevice-benchmark.md](jev/04-ondevice-benchmark.md) | 端侧候选本机实测（Task 4 唯一交付：Windows x86 CPU 真数字 + 外推 Android） | edgejev：ONNX int8 模型 **324.5 MB**、3 题批量 median **157.5 ms**、峰值 RSS **495 MB**、首次加载 **2.1 s**；"README 宣称的「单题 15.6 ms」是在 Xeon AVX512-VNNI 上的硬件特例" |
| [jev/05-laos-placement.md](jev/05-laos-placement.md) | laos 判定点映射与落点清单（Task 5 设计产出）：魔法数字 → Jev 三原语，收益/代价/排除理由 | "常驻每帧调用 → 持续 **0.5–1.5 W** 附加（否决）；离线/二级确认档 → 常摊 **4.6 mW** 量级（可接受）"；"不沿用任何 README 宣称值" |
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
