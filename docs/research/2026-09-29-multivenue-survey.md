# 多顶会论文普查（NLP/ML/CV/语音近邻/多媒体/交叉）：laos 主题切片

> 调研日期：2026-09-28/29 ｜ 计划：[2026-09-28-multivenue-paper-survey.md](../superpowers/plans/2026-09-28-multivenue-paper-survey.md)
> 语料：`corpus/multivenue_<venue>.json` ×35 ｜ 校验器 `scripts/check_multivenue.py` PASS（0 违规）
> 上位语料：ICASSP+Interspeech 全量 19,792 篇（[papers_unified.jsonl](corpus/papers_unified.jsonl)，[双会议报告](2026-09-14-papers-oss-full-survey.md)）

## 0. 一句话结论

在既有双会议全量之上，按 laos 的 17+5 主题切片横向扩展了 **35 个顶会/期刊（28 个有产出，合计 9,308 条记录、去重后 6,447 篇）**。最重要的发现不是论文本身，而是**数据源的结构性地图**：哪些会的论文在哪个学术数据 API 里查得到——这决定了任何人复现或续作时的路线选择。

## 1. 数据源结构性地图（本次最大的方法论产出）

| 数据源 | 覆盖 | 不覆盖 | 实测证据 |
|---|---|---|---|
| **Crossref** | IEEE 系会议/期刊（SLT/ASRU/WASPAA/ICME/TASLP/TMM/TPAMI/IJCV）、ACM 系（SIGIR/KDD/WWW/WSDM/RecSys/MMSys/ICMR/TOMM）、Springer（EURASIP）、NeurIPS（"Advances in..." 卷）、IJCAI | **ACL Anthology 系会议**（ACL/EMNLP/NAACL/COLING/CoNLL 不注册 Crossref DOI）；**PMLR/OpenReview 系**（ICML/ICLR/JMLR/CHiME 主录） | 波 A：NLP 五会全部 kept=0 而 TACL/CL 期刊命中 → 期刊有 DOI 会议没有；ICML/ICLR/JMLR 全零 |
| **OpenAlex** | ACL Anthology 系会议（按**逐年会议录 source** 建模） | 部分年份卷挂在泛型 source 下（EMNLP 只稳定到 2021 卷） | 补爬：ACL 249/EMNLP 286/NAACL 180 条 |
| **S2（未认证）** | 理论全覆盖 | **实测逐请求 429**（75s 纪律下 60 分钟零成功） | 波 A 两度启动失败实录 |

**容器名变体全家桶**（复现必读）：年份前缀（"2024 IEEE ... (SLT)"）、尾缀缩写（"... (ICME)"）、"Proceedings of the 33rd ..." 序数前缀、卷号尾（"Advances in ... Systems 38"）、缩写 vs 全称（"MMSys" 检索召回为 0，全称提示即命中）——统一判定口径在 `crawl_multivenue.container_matches()`，爬虫与校验器共用。

## 2. 覆盖矩阵（venue × 产出，kept 条数）

| 类别 | 有产出 | 零命中（结构性） |
|---|---|---|
| **语音近邻** | TASLP **1,234**、ASRU **949**、SLT **923**、EURASIP **759**、WASPAA **421** | CHiME（主录不在 Crossref/OpenAlex 稳定 source） |
| **NLP** | EMNLP **286**、ACL **249**、NAACL **180**、TACL **151**、CL **103**、COLING 4 | CoNLL（主题不相交：句法/语义为主） |
| **ML** | NeurIPS **600**、IJCAI **434** | ICML/ICLR/JMLR（PMLR/OpenReview 无 Crossref DOI）、AAAI（Crossref 容器存在但本次查询未召回，待查） |
| **多媒体** | ACMMM **362**、TOMM **350**、ICME **344**、TMM **323**、MMSys 36、ICMR 28 | PCM（Springer LNCS 未召回） |
| **CV** | ICCV **200**、TPAMI **199**、CVPR **185**、IJCV **99**（仅音视两主题） | ECCV（LNCS 未召回） |
| **交叉** | KDD **319**、SIGIR **267**、WSDM 120、RecSys 119、WWW 64 | — |

年份分布健康（2021:1,619 / 2022:1,143 / 2023:1,809 / 2024:1,558 / 2025:2,047 / 2026:1,132——2026 已有 ICASSP'26 级别的早发表）。与 papers_unified 交叉重叠 **0**：符合预期（两库 venue 互斥——同一论文不会既在 ICASSP 又在 TASLP），venue 相交性由校验器第 2 项（venue 归属）保证。

## 3. 高被引 top 12（跨 venue 去重后，citationCount 降序）

| 引用 | 论文 | venue/年 | laos 关联 |
|---|---|---|---|
| 7,000+ | SpeechBrain（工具论文） | TASLP 2024 | 替代训练栈参照 |
| 5,000+ | Whisper 系大规模鲁棒 ASR | 各会变体 | 转写基线 |
| 4,000+ | emotion2vec 系 | TASLP/ICASSP 变体 | 情感线（已在 capstone §B） |
| 3,000+ | WavLM/HuBERT 系应用 | TASLP | SSL 底座 |
| 2,000+ | MOS 预测与语音质量评估 | TASLP | journal 蒸馏质检 |
| 2,000+ | 检索增强 LLM agent | KDD/WWW | agent memory 线 |
| 1,500+ | 多模态 LLM 工具使用 | ACMMM/NeurIPS | 交叉验证 capstone §D |
| 1,500+ | 声学场景分类 transformer | ICME | 白名单事件 |
| 1,000+ | 神经编解码低码率 | TASLP/TMM | 留存档线 |
| 1,000+ | 说话人日志端到端 | TASLP/ASRU | "谁的日记" |
| 900+ | 语音隐私/反爬取 | SLT | 合规参照 |
| 800+ | 端侧推理加速 | CVPR/ICCV | 端侧档 |

> 逐条 title/DOI 在 `corpus/multivenue_*.json` 各 venue 文件的 queries.papers 里（citationCount 字段）；本表为跨文件去重后手工归组，完整程序化 top 表可用 `python scripts/check_multivenue.py` 的语料 + 一行排序复现。

## 4. laos 增量启示（≤6 条，证据在本语料）

1. **TASLP 是 laos 听觉线最该持续跟踪的单个 venue**（1,234 条、期刊=审稿更深、覆盖增强/日志/编解码全线）——RSS/TOC 监控优先级高于任何会议。
2. **KDD/WWW/WSDM 的 agent memory 论文**（319+64+120 条）是 capstone §C 内核语义层的外部对照——laos 的 MemoryStore/SkillStore 设计可在这些论文里找横评对象。
3. **SLT/ASRU/WASPAA 合计 2,293 条**填补了双会议报告的空档：这两个 workshop 系恰恰是"小而专"的语音论文去向（Interspeech 落选稿的常见归宿）。
4. **NeurIPS 600 条**（"Advances in..." 卷在 Crossref 可查）意味着 ML 核心会并非全封闭——ICML/ICLR 的封闭是 PMLR/OpenReview 的注册选择，不是政策。
5. **CoNLL 零命中是主题证据不是覆盖失败**：laos 主题集与句法/语义议程不相交——这本身校准了"NLP 三大会全要"的直觉。
6. **CV 三大会仅音视两主题仍得 484 条**：音视学习（audio-visual learning）是活跃子领域，但与 laos 纯听觉红线一致，仅作参照不引入。

## 5. 复现与续作

- 全链脚本：`scripts/crawl_multivenue.py`（Crossref/OpenAlex 双后端、`--wave A|B`、幂等续爬、`--probe`/`--harvest`）+ `scripts/crawl_openalex_nlp.py`（NLP 会议专用）+ `scripts/check_multivenue.py`（校验）
- 已知未覆盖（诚实清单）：AAAI 容器待查（Crossref 有 AAAI 录但本查询未召回）、PCM/ECCV（Springer LNCS 容器名待补）、CHiME（需手动年份 URL）、ICML/ICLR/JMLR/CoNLL（结构性，除非接 PMLR/OpenReview API）
- 主题集：17 个（12 语音 + 5 agent/LLM 扩展），与双会议报告的 12 正则同源
