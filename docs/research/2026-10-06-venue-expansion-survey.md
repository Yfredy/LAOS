# 顶会语料扩展普查（venue expansion survey）：38 个 venue 全量落库

> 调研日期：2026-10-06/07 ｜ 计划：[2026-10-06-venue-expansion-survey.md](../superpowers/plans/2026-10-06-venue-expansion-survey.md)（SDD 六任务，账本 [.superpowers/sdd/2026-10-06-venue-expansion-survey/progress.md](../../.superpowers/sdd/2026-10-06-venue-expansion-survey/progress.md)）
> 语料：`corpus/venue_expansion/*.jsonl` ×35（6 anthology + 8 journal + 21 conference，其中 5 个 0 行占位）｜ 注册表 `corpus/venue_expansion/venues.csv`（38 venue）
> 上位语料：ICASSP+Interspeech 全量 19,792 篇（[papers_unified.jsonl](../../corpus/papers_unified.jsonl)）+ 35-venue 主题切片 9,908 条（[multivenue 报告](2026-09-29-multivenue-survey.md)）

## 0. 一句话结论

在既有双会议与 35-venue 切片之上，把 **38 个 venue（NLP 六会全量 / 9 刊 / 21 会 + 2 deferred）按"整卷全量"标准落库**：合计 **120,234 行**，laos 三主线正则过滤命中 **2,103 行**（agent-os 880 / audio-speech 1,109 / spatial-privacy 114，跨文件去重剔 13）——其中真正的"agent 操作系统治理"窄分支只有 **44 篇**，这是 laos 议题的直接外部对照集；其余 agent-os 命中是泛 LLM-agent 论文（宽分支 836），audio-speech 有 42% 是裸 `asr`/`tts`/`vad` 子串弱命中。数据源侧的结构性结论延续并加深了 multivenue 报告的地图：**ACL Anthology（官方 bib dump）与 Crossref（journal ISSN + container-title 模糊召回）双主通道可覆盖 38 venue 中的 36 个；DBLP/OpenReview 实测 JS 反爬、PMLR 无 DOI，是仅剩的两个换源缺口。**

## 1. 方法与数据源

### 1.1 双主通道

| 通道 | venue 数 | 实现与口径 | 实测教训 |
|---|---|---|---|
| **ACL Anthology**（`fetch_anthology.py`） | 6（acl/emnlp/naacl/coling/conll/tacl） | 官方 `anthology+abstracts.bib.gz` 全库 dump（42.5MB，2026-10-05 快照）一次性下载缓存，本地状态机解析 BibTeX：booktitle/journal 剥大小写保护花括号后 casefold 子串匹配 + 年窗过滤；只收 inproceedings/article | 不剥 `{A}` 保护花括号会漏 2015/2018/2019 等旧卷（已修+回归测试）；双向 ground-truth 审计（按 URL 卷族反查漏配）= 0 |
| **Crossref 期刊**（`fetch_crossref.py --mode journal`） | 9（taslp/aaai/tpami/ijcv/tmm/tomm/jmlr/cl/eurasip-jasmp） | ISSN 精确过滤 + cursor 深分页；零行三级回退（备用 ISSN → 刊名检索去 IEEE/ACM 冠名 token 的同名列继任刊 → 仍 0 记失败清单） | TASLP 继任刊靠回退链自动接到；JMLR 两个 ISSN 均 0 行=真实缺口（见 §4） |
| **Crossref 会议**（`fetch_crossref.py --mode container`） | 21 | `query.container-title` 模糊召回（**不能**用 `filter=container-title`：带逗号必 HTTP 400，实测）+ `filter=prefix:<DOI前缀>` 压噪 + 客户端规范化精确归并；变体是**可接受集合的并集**（按 DOI 去重），不是首个命中即停 | 容器名逐年变形是常态（届次/年份前缀/分卷 V.1/V.2/排版笔误/冠名更替，§2 备注）；`sort=relevance` 深翻页页界跳漏（iccv 6491→5991 实测），必须走 cursor=* scan 序全遍历到不满页 |

统一 schema：`{title, year, venue, authors, url, doi, abstract}`（jsonl；abstract 可 None——出版社未向 Crossref 缴存时如实置 None，是口径不是 bug）。写出纪律：U+2028/U+2029/U+0085 转义成 `\u2028` 形（ijcai 曾有一行 title 内嵌 U+2028 会炸 `splitlines()` 读法，已修+回归测试）。HTTP 全带指数退避 1s→60s×8、polite pool mailto；输出文件已存在即跳过=断点续抓，`--force` 重抓。

### 1.2 实测反爬证据（换源决策的依据）

| 数据源 | 实测现象 | 处置 |
|---|---|---|
| **DBLP** | 批量列表页 JS 反爬，程序化抓取被拦 | ICML/PCM 等缺口 venue 的换源通道记为"DBLP/Springer"但本轮未强攻（见 §4） |
| **OpenReview** | 反爬阻断 bulk fetch | ICLR 标 `deferred`，靠 35-venue 存量（到 2024）兜底 |
| **S2（未认证）** | （multivenue 报告实录）逐请求 429，60 分钟零成功 | 不再作为主通道 |

### 1.3 网络环境（TUN 断窗）

抓取窗口恰逢 TUN 断网窗（Anthology dump 42.5MB 曾以 ~30KB/s 蠕动 ~40 分钟；Task 4 后台任务两次被环境杀掉）。兜底=指数退避 + 断点续抓（已存在文件跳过、0 行缺口落空文件承接），两次被杀均无损续跑。**断窗没有损失任何数据，只拉长了墙钟时间。**

## 2. 每 venue 计数总表（38 行，实抓 `wc -l` 口径）

CCF 列照注册表 `venues.csv` 的 ccf 列（CCF 2022 目录**人工近似值，未逐一复核**；iclr/tacl/waspaa/chime/eurasip-jasmp/globalsip 目录未收录留空）。“年窗”是 registry 的抓取窗（T2/T3/T4 据此过滤），“实抓年分布”是落库数据的真实跨度。

### 2.1 ACL Anthology 族（6 venue，42,939 行）

| venue | CCF | 年窗 | 实抓行数 | 实抓年分布与备注 |
|---|---|---|---:|---|
| acl | A | 2010-2025 | 14,599 | 2010-2025 无缺口；含短文/演示/SRW/Findings；EACL 2022=ACL-62 自然计入；abstract ~80% |
| emnlp | B | 2010-2025 | 15,349 | 2010-2025 无缺口；含 demos/industry/Findings；EMNLP+CoNLL 联合卷两属；abstract ~90% |
| naacl | B | 2010-2025 | 5,480 | 2011/2014/2017/2020/2023 无会属实无卷；2025 改名 "Nations of the Americas Chapter" 已适配；abstract ~74%（Task 2 实测 82.1%） |
| coling | B | 2010-2025 | 5,676 | 双年份系列；2024 为 LREC-COLING 联合会自然计入；abstract ~82% |
| conll | C | 2010-2025 | 1,040 | 核心 CoNLL+联合 shared task；老卷在 W 系列卷号下靠 booktitle 匹配收；abstract ~52%（老卷上游无摘要） |
| tacl | — | 2013-2025 | 795 | 期刊全文镜像于 Anthology；2013 年 Q 卷上游只有 35 条；2026 卷 105 条按年窗排除；abstract 100% |

### 2.2 Crossref 期刊族（9 venue，19,860 行）

| venue | CCF | 年窗 | 实抓行数 | 实抓年分布与备注 |
|---|---|---|---:|---|
| tpami | A | 2015-2025 | 5,323 | 248→822 篇/年；abstract 0%（IEEE 不向 Crossref 缴存） |
| tmm | B | 2015-2025 | 4,850 | 276→879 篇/年；abstract 0%（IEEE 同上） |
| aaai | A | 2026-2027（增量） | 4,920 | 2026 全年；ISSN 2159-5399 已解锁（multivenue 报告遗留缺口关闭）；abstract 100% |
| tomm | B | 2015-2025 | 1,851 | abstract ~95%（ACM 缴存） |
| ijcv | A | 2015-2025 | 1,799 | abstract 15.5%（Springer 缴存稀疏） |
| cl | B | 2015-2025 | 365 | 33..41 篇/年；abstract 82.5% |
| eurasip-jasmp | — | 2015-2025 | 392 | abstract 58.4% |
| taslp | B | 2026-2027（增量） | 360 | **实抓走继任刊 ISSN 2998-4173**（IEEE 改版，原 2329-9290 存量停在 2024）；abstract 0%（IEEE） |
| jmlr | A | 2015-2025 | **0** | **Crossref 真实缺口**：1533-7928 HTTP 404；1532-4435 是 "Unmaintained records" stub，works=0——JMLR 论文不向 Crossref 缴存 DOI（§4） |

### 2.3 Crossref 会议族（21 venue，57,435 行）

| venue | CCF | 年窗 | 实抓行数 | 实抓年分布与备注 |
|---|---|---|---:|---|
| neurips | A | 2021-2026 | 16,691 | v35:2834 / v36:3540 / v37:4494 / v38:5823；**v34(2021) 未逐篇缴存、v39(2026) 12 月开会**（DOI 前缀 10.52202 逐年验证） |
| iccv | A | 2021-2026 | 6,491 | 双年制：2021:1561 / 2023:2163 / 2025:2709（= 召回全集，精确） |
| acmmm | A | 2021-2026（增量） | 5,383 | 29th:684 → 33rd:1620；**2026（34th，10 月末）未缴存** |
| ijcai | A | 2021-2026 | 5,964 | 六届全收；2024 官方缴存名缺空格笔误（"Thirty-ThirdInternational"）按逐字变体收录无缺；全族带 abstract |
| kdd | A | 2021-2026 | 4,536 | 2025/2026 ACM 改 V.1/V.2 分卷缴存，两种形式均并收 |
| icip | C | 2021-2026 | 4,129 | 797/874/730/602/491/635，逐年健康 |
| icme | B | 2021-2026 | 2,931 | 2026 未缴存 |
| sigir | A | 2021-2026 | 2,906 | 44th:382 → 49th:686 |
| www | A | 2021-2026 | 2,731 | 2025 冠名改 "ACM on Web Conference" 已入变体表；2026:723 |
| globalsip | — | 2013-2019（存档窗） | 1,673 | 2019 后停办，抓存档窗；2014-2019 全量精确收齐；首届 2013 不在 Crossref |
| recsys | B | 2021-2026 | 1,203 | Fifteenth→20th，部分年份无 "Proceedings" 前缀，均在变体表 |
| wsdm | B | 2021-2026 | 1,093 | 序数词与数字混用（"Fifteenth"/"17th"），均并收 |
| icmr | C | 2021-2026 | 1,055 | 96→343 逐年增长 |
| waspaa | — | 2021-2026 | 272 | 双年制：2021/2023/2025 = 84/87/101（召回全集，精确） |
| mmsys | C | 2021-2026 | 330 | 2024 缴存名带 ACM DL 占位后缀 "on ZZZ"，按逐字变体收 |
| chime | — | 2021-2026 | 47 | 2023/2024/2026 三届 17/16/14（challenge workshop，缴存本就 sparse） |
| icassp | B | 2027-2028（增量） | **0** | 2027-05 开会、论文集未缴存（存量到 2026 已在 papers_unified）；10.1109 前缀 2027-2028 窗口独立探测 0 行 |
| interspeech | C | 2026-2027（增量） | **0** | "Interspeech" 容器 + DOI 前缀 10.21437 兜底双路探测：前缀 2026-2027 共 371 行全是 ISCA 姊妹事件（Speech Prosody/JEP/Odyssey/CHiME/DC/WOCHAT），Interspeech 2026 论文集未缴存 |
| asru | C | 2026-2027（增量） | **0** | 双年制，下届 2027-12；2026-2027 窗口 0 行 |
| slt | C | 2026-2027（增量） | **0** | SLT 2026（年末）未缴存；逐年全遍历（19.7k/年召回）0 命中 |
| pcm | C | 2021-2026 | **0** | **系统性缺口**：Springer LNCS/CCIS 的 PCM 卷在 Crossref 无可检索容器名（container-title 与 query.bibliographic 双路全噪声）；需 DBLP/Springer 换源（§4） |

### 2.4 deferred（2 venue，registry 在册、本轮不抓）

| venue | CCF | 年窗 | 状态 | 缺口原因 |
|---|---|---|---|---|
| iclr | — | 2025-2026（增量） | deferred | OpenReview 反爬阻断 bulk fetch；靠 35-venue 存量（到 2024）兜底 |
| icml | A | 2021-2026 | deferred | PMLR proceedings 无 DOI；DBLP/OpenReview 反爬；后续换源再攻 |

**合计：42,939 + 19,860 + 57,435 = 120,234 行**（5 个 0 行占位文件与 jmlr 空缺均已在 registry 登记为缺口，不重复计数）。

## 3. laos 相关性交叉计数（2,103 命中）

过滤口径：`filter_laos_relevant.py` 三主线正则词表，标题+摘要（若有）拼串 casefold 匹配；跨文件联合卷重复按 DOI+title casefold 去重（剔 13）。输入 35 文件 120,234 行 → 命中 2,116 → 写出 **2,103**。

### 3.1 venue × topic 交叉表（去重后写出行为准）

| venue | agent-os | audio-speech | spatial-privacy | total |
|---|---:|---:|---:|---:|
| anthology_emnlp | 248 | 240 | 2 | 490 |
| anthology_acl | 198 | 227 | 2 | 427 |
| crossref_journal_aaai | 127 | 74 | 6 | 207 |
| anthology_naacl | 69 | 104 | . | 173 |
| anthology_coling | 22 | 129 | . | 151 |
| crossref_conf_ijcai | 59 | 53 | 2 | 114 |
| crossref_journal_eurasip-jasmp | . | 75 | 31 | 106 |
| crossref_conf_neurips | 70 | 22 | 5 | 97 |
| crossref_journal_taslp | 3 | 31 | 17 | 51 |
| crossref_conf_kdd | 43 | 5 | . | 48 |
| crossref_conf_globalsip | . | 9 | 19 | 28 |
| crossref_conf_acmmm | 2 | 21 | 3 | 26 |
| crossref_conf_icme | . | 21 | 2 | 23 |
| crossref_conf_waspaa | . | 6 | 15 | 21 |
| crossref_journal_tomm | 1 | 14 | 2 | 17 |
| crossref_conf_sigir | 12 | 3 | . | 15 |
| crossref_conf_www | 10 | 5 | . | 15 |
| crossref_journal_tmm | . | 10 | 3 | 13 |
| anthology_tacl | 1 | 10 | . | 11 |
| crossref_conf_recsys | 5 | 5 | . | 10 |
| crossref_conf_chime | . | 9 | . | 9 |
| crossref_conf_iccv | 1 | 7 | 1 | 9 |
| anthology_conll | 1 | 7 | . | 8 |
| crossref_journal_tpami | . | 6 | 1 | 7 |
| crossref_conf_icip | 3 | 3 | . | 6 |
| crossref_conf_mmsys | 1 | 2 | 3 | 6 |
| crossref_conf_wsdm | 3 | 3 | . | 6 |
| crossref_journal_cl | . | 6 | . | 6 |
| crossref_journal_ijcv | . | 2 | . | 2 |
| crossref_conf_icmr | 1 | . | . | 1 |
| **TOTAL** | **880** | **1,109** | **114** | **2,103** |

（venue 键 = 源文件 stem；5 个 0 行占位文件天然不出现。）

### 3.2 三主线精度注记（引用任何数字前必读）

1. **agent-os 880 中，宽分支 836 = 泛 LLM-agent 论文**：命中 `(llm|language model).{0,30}(agent)` 的论文语义≈"任何 LLM agent 论文"，**不是**"agent 操作系统治理"。**窄治理分支（agent×operating system/sandbox/syscall/kernel/governan/resource/quota/isolation）仅 44 篇，这才是 laos 头条数**——引用时用 44，不用 880。
2. **audio-speech 1,109 中 42%（463 行）是裸子串弱命中**：仅靠 `asr`/`tts`/`vad` 三个裸词命中、无任何强音频关键词——LLM 安全论文的 "attack success rate (asr)" 大量误标（如 "Defensive Prompt Patch…against Jailbreaking" 被 asr 误收；全库此类误标约 68 篇集中在 attack-success-rate 语义）。强关键词驱动分布：speech recognition 457 / asr 284 / tts 141 / vad 132 / diariz 33 / keyword spotting 19 / voice activity 18 / echo cancell 9 / far-field 8 / wake word 4 / always-on 4。
3. **spatial-privacy 114 精度较好**：集中在 eurasip-jasmp(31)/globalsip(19)/taslp(17)/waspaa(15) 等音频 venue，抽检样例均为真双耳/波束/水印主题。

### 3.3 每主线强命中代表论文（各 5 篇，年份倒序；从 title 含主线词组的强命中里实挑，避开弱命中）

**agent-os（窄治理分支 44 篇之代表）**：

1. **TuneAgent: Agentic Operating System Kernel Tuning with Reinforcement Learning**（KDD 2026）——标题级 "agentic operating system kernel"，与 laos "Agent 是新负载、内核治理延伸" 叙事同轴的内核调优工作。
2. **PolicySim: An LLM-Based Agent Social Simulation Sandbox for Proactive Policy Optimization**（WWW 2026）——agent 沙箱内政策仿真，治理语义直连。
3. **{AXIS}: Efficient Human-Agent-Computer Interaction with {API}-First {LLM}-Based Agents**（ACL 2025）——人-代理-计算机交互的 API-first 路线。
4. **Emergent Risk Awareness in Rational Agents under Resource Constraints**（NeurIPS 2025 / v38）——资源约束下的 agent 风险感知，配额治理的对面镜像。
5. **Fairness and Optimization in Dynamic Multiagent Allocation Problems**（IJCAI 2024）——共享资源池的动态公平分配（同线：IJCAI 2021 "Dominant Resource Fairness with Meta-Types" 即内核 DRF 谱系）。

**audio-speech（强关键词命中之代表）**：

1. **Effective User-Defined Keyword Spotting With Dual-Stage Matching, Multi-Modal Enrollment, and Continual Adaptation**（IEEE TASLP 2026）——用户自定义 KWS，laos 唤醒词线。
2. **Cueing Without Gapping: Cuer-Independent Cued Speech Recognition Powered by Cross-Cuer Invariant Modeling**（AAAI 2026）——可见言语识别的说话人无关建模。
3. **Conversation Clustering by Mutual Gaze Estimation and AV-ASR by Dual Model Output Fusion**（CHiME 2026, 9th Challenge）——多源挑战赛式 AV-ASR。
4. **Calliope: A TTS-based Narrated E-book Creator Ensuring Exact Synchronization, Privacy, and Layout Fidelity**（MMSys 2026）——TTS 应用系统，含隐私约束。
5. **Far-End Reconstruction-Guided Separation-Based Acoustic Echo Cancellation With Flow Matching**（IEEE TASLP 2026）——AEC 与分离联合建模，全双工对话的地基。

**spatial-privacy（title 强命中之代表）**：

1. **Array-Aware Ambisonics and HRTF Encoding for Binaural Reproduction With Wearable Arrays**（IEEE TASLP 2026）——可穿戴阵列→双耳重放，与 laos binaural.py/foa.py 直接同域。
2. **SpatialV2A: Visual-Guided High-fidelity Spatial Audio Generation**（IJCAI 2026）——视觉引导空间音频生成。
3. **Yours or Mine? Overwriting Attacks Against Neural Audio Watermarking**（AAAI 2026）——音频水印攻击面，laos 留存档/溯源线的威胁模型。
4. **Beamforming with Interaural Time-To-Level Difference Conversion for Hearing Loss Compensation**（WASPAA 2025）——双耳时域-声级差转换波束，助听语义。
5. **CCStereo: Audio-Visual Contextual and Contrastive Learning for Binaural Audio Generation**（ACM MM 2025）——视听对比学习双耳生成。

## 4. 覆盖缺口与后续（来源诚实，逐条）

| # | 缺口 | 证据（独立探测，非仅本次 0 行） | 后续动作 |
|---|---|---|---|
| 1 | **jmlr = 0 行** | `/journals/1533-7928` HTTP 404（e-ISSN 未注册）；刊名检索仅得 "Unmaintained records" stub（ISSN 1532-4435，works=0 全年份）——JMLR 论文不向 Crossref 缴存 DOI | 换源：jmlr.org 官网 paper 页（doi/url 字段换源口径）或 DBLP（若反爬可破） |
| 2 | **pcm = 0 行（系统性）** | Springer LNCS/CCIS 的 PCM 卷在 Crossref 无可检索容器名：container-title 与 query.bibliographic 双路全噪声（召回 CLEO-PR/护理学刊等） | 换源：DBLP 或 Springer 直接抓（LNCS 卷号可枚举） |
| 3 | **icassp/interspeech/asru/slt = 2026-27 未来窗** | 四会均为增量窗（存量已在 papers_unified/35-venue 覆盖到 2025/2026）；独立探测：ICASSP 2027 未缴存、Interspeech 前缀 10.21437 的 2026-27 共 371 行全是 ISCA 姊妹事件、ASRU 下届 2027-12、SLT 2026 年末 | **会议论文集缴存后 `--force` 重跑即接**（断点续抓机制已就位；interspeech 前缀兜底自动承接） |
| 4 | **ICML = deferred** | PMLR proceedings 无 DOI；DBLP/OpenReview 批量列表 JS 反爬（实测） | 换源三选：PMLR 官网卷页直接抓（无 DOI，url 口径）/ DBLP / OpenReview API 单卷试探 |
| 5 | **ICLR = deferred（存量兜底）** | OpenReview 反爬；35-venue 切片库存量到 2024 | 增量（2025+）待 OpenReview 可编程通道 |
| 6 | **TASLP 后继刊口径** | IEEE 改版：IEEE/ACM TASLP（2329-9290）存量停在 issued=2024，2025+ 挂继任刊 "IEEE Transactions on Audio Speech and Language Processing"（ISSN 2998-4173，DOI 前缀 taslpro） | registry 的 issn 列后续更新为 2998-4173（本轮抓取已由回退链兜住，数据是对的，registry 未改只在此声明） |
| 7 | **IEEE 三刊 abstract 不缴存** | taslp/tmm/tpami 的 Crossref 记录无 abstract 字段（实测口径；ACM/tomm 95%、aaai 100%、cl 82.5%、eurasip 58.4%、ijcv 15.5% 对比） | abstract 置 None 是口径不是 bug；需要摘要时走 IEEE Xplore 单页补抓（代价高，未做） |
| 8 | **部分年份缺口（有行但某年缺）** | neurips v34(2021) 未逐篇缴存/v39(2026) 未开；acmmm 2026、icme 2026 未缴存；iccv 偶数年无会；globalsip 2013 首届不在 Crossref；kdd 2025/26 分卷已并收无缺 | 各会缴存后 `--force` 重跑 |
| 9 | **网络环境（TUN 断窗）** | Anthology dump 以 ~30KB/s 蠕动 40 分钟；Task 4 后台任务两次被环境杀掉 | 退避+断点续抓兜底（两次被杀均无损续跑）；若再遇断窗，重跑同一命令即可续 |

## 5. CCF 口径说明

第 2 节各表 CCF 列照 `venues.csv` 的 ccf 列逐字誊写。该列为**人工填写的 CCF 2022 目录近似值，未逐一复核**（T1 报告疑虑 3 原文移交）：iclr/tacl/waspaa/chime/eurasip-jasmp/globalsip 目录未收录留空；tomm(B)/slt(C) 是最没把握的两格。CCF 列仅供报告分档参考，不参与抓取分派与任何测试断言。

## 6. 与既有语料的关系（去重口径）

- 35-venue 切片（9,908 条，主题切片非全量）与 papers_unified（19,792 篇）是**主题/会议维度的不同切法**；本语料是**整卷全量**维度，三库并存。
- acl/emnlp/naacl（存量有 ACL/EMNLP 主题切片）、acmmm、taslp/asru/slt/aaai/iclr（增量行）与既有语料的重叠由 T5 的跨文件 DOI+title casefold 去重承接（本次剔 13 行）；联合卷（EMNLP+CoNLL、LREC-COLING、EACL=ACL-62）在 anthology 族两属属预期非 bug。
- 后续增量：各会新论文集缴存后 `--force` 重跑对应 venue（断点续抓保证只补新）；窗口扩宽只需改 `venues.csv` 的 years 列（Anthology dump 缓存可复用）。

---

*数字口径：全部计数为 `wc -l` 实测（jsonl 行数=论文数）；laos_relevant 计数为过滤脚本 `--stats` 实跑；年分布为 T2-T4 任务报告实测。本报告不改写任何上游数字。*
