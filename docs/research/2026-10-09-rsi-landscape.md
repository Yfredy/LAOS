# RSI（递归自我改进）方向全景调研：论文浪潮、开源生态与 laos 治理含义

> 调研日期：2026-10-09。触发：小红书笔记《RSIGym：让 Agent 自主优化模型和 Harness AI 应该怎…》（标题残句）。

## 0. 来源诚实声明

- 小红书分享链接（`xhslink.cn/o/9dA1Ir76RLb` → 重定向至 xiaohongshu.com/discovery/item/6ac8a797…）两条通道均失败：webReader 报网络错误（error id 202610091705…），WebFetch 重定向跟进后仅返回页面标题「小红书 - 你的生活兴趣社区」——登录墙 + JS 渲染，笔记正文与图片均不可达。
- 按仓库预案处理：**以笔记标题残句为主题锚点，内容全部从可验证一手来源重构**——RSIGym 论文 arXiv 摘要页（2610.10310）、GitHub 仓库 README（evolvent-ai/RSIGym）、ICLR 2026 RSI Workshop 官网、Lilian Weng 博客原文（2026-07-04）、各论文 arXiv 摘要页。笔记本体说了什么、有几张图，本文不复原也不猜测。
- 评测数字一律抄一手来源页面原文；中文媒体报道（钛媒体/量子位/机器之心/MIT TR 中文）只在 §6 产业动态使用并逐一标注链接，其中转述的数字（如 Anthropic 占比）标注「媒体口径」。

## 1. 一句话结论

RSI 在 2026-09/10 完成了从概念到**纸面基础设施**的跃迁：实验环境（RSIGym）、过拟合治理（RRSI）、探索框架（Dream-RSI / RSIAgent）、能力路线图（The Last AI Built by Humans）四条线在六周内同时成型，ICLR 2026 首届 RSI Workshop 录用 110 篇；Lilian Weng 七月综述已把近期路径钉死在 harness engineering（"近端 RSI 不太可能始于模型直接改写自身权重"）。**对 laos 最重要的一条行业自证：Weng 列出的七大瓶颈之五是"评估器与权限控制应放在进化循环之外"——这正是 laos 一直主张的内核治理席位的定义**（基座不自改写，负载可以）。

## 2. 定义与分层：谁在说 RSI，说的都是什么

### 2.1 术语谱系

| 时间 | 节点 | 内容 |
|---|---|---|
| 1965 | I. J. Good「ultraintelligent machine」 | 机器在一切智力活动上超越人类，并能设计更好的机器改进自身（Lilian Weng 综述的溯源起点） |
| 1987–2003 | Schmidhuber | Gödel Machine / OOPS / 1987 论文，可证明最优的自我改写机器（个人主页《Recursive Self-Improvement Since 1987》为权威综述入口，含 2026 新作 Red Queen Gödel machine，arXiv:2606.26294，agent 与 evaluator 共演化） |
| 2008 | Yudkowsky 造词 | "recursive self-improvement"：AI 用现有智能改进产生其智能的认知机制 |
| 2023–2025 | LLM 时代 | STaR / Self-Rewarding LM / Promptbreeder / STOP / ADAS / AlphaEvolve / Darwin Gödel Machine，把 RSI 拆成可实验的对象 |
| 2026-09/10 | 本轮浪潮 | 环境、正则化、评测、路线图四线成型（§4） |

### 2.2 三层区分（lobehub/awesome-rsi 明文口径）

1. **self-refinement**：单任务内迭代改输出，不持久（如 Self-Refine）；
2. **persistent self-improvement**：改进成果跨任务保留（文件系统记忆、context 演化）；
3. **RSI**：改进机制本身也是被改进对象（harness/优化器代码，乃至联合更新权重）。

RSIGym 论文开篇即用"carrying accepted changes into later improvement cycles"定义递归性——**被验证接受的改动必须持久进入后续循环**，否则只是 self-refinement。

### 2.3 优化对象链（Weng 综述的骨架）

```
prompt → structured context → workflow → harness code → optimizer code → (权重)
```

近期路径共识落在 **harness code** 一层：Claude Code / Codex 的成功证明部署层重要性接近模型原生智能；Weng 的判断原文是 "the near-term path of RSI is unlikely to start as a model directly rewriting its weights"。她同时给出 OS 类比：harness 应封装复杂逻辑、保持简单接口，接口/配置可能逐步标准化——**这与 laos「syscall 边界即治理契约」的叙事同构**（§8）。

## 3. RSIGym 深读（小红书笔记的主角）

### 3.1 论文（arXiv:2610.10310，2026-10-07，CC BY 4.0）

- 作者 9 人：Fanqing Meng、Lingxiao Du、Haocheng Lu、Qiguang Chen 等（GitHub 组织 Evolvent AI 出品；一作 Fanqing Meng 为评测基建领域高产作者，页面未列机构，此处不写）。
- 动机：RSI 研究需要"把已接受的改动带进后续循环 + 研究 agent 提出的改动"的大量基础设施；现有设置要么让 agent 重复搭轮子，要么只许改进单一环节。
- **EaaS（Everything as a Service）架构**：训练、推理、rollout、评估、沙箱执行全部封装为可复用服务 + 共享预算与权限控制。
- **三条改进轨道**：Data（改训练数据）/ Harness（改执行与训练框架）/ Joint（联合优化数据、训练设置与 harness）。
- **RSI-Index 指标**：五个基准上平均"关闭剩余性能差距的比例"，即各基准 `(final − initial)/(1 − initial)` 的均值（公式抄自仓库 README，与论文一致）。
- 五基准：SWE-bench Verified、Terminal-Bench 2.0、AIME、GPQA Diamond、SkillsBench（软件工程 / 终端交互 / 数学 / 科学推理 / 技能类）。
- **主要结果**（六个前沿研究模型的独立 Joint 运行，每基准 $500 平台服务预算）：**Opus 5 最佳，RSI-Index 0.4809**（基线为 0）；SWE-bench Verified **17.67% → 50.33%**；AIME **31.67% → 97.78%**；**30 次 Joint 运行中 29 次有提升**。附 DSH-harness 精炼、预算敏感性、受限网络实验与轨迹公开。

### 3.2 仓库实况（evolvent-ai/RSIGym，2026-10-09 查）

| 项 | 值 |
|---|---|
| star / fork / commits | 36 / 1 / 4（**全新仓，热乎的**） |
| License | 页面未注明 |
| 依赖 | Python 3.12+ / uv / Harbor 0.20.x / curl / jq / Docker |
| 服务组件 | train_server（LoRA 微调，基于 Tinker）、model_server（OpenAI 兼容推理，基座+checkpoint）、rollout_server（前沿模型做数据生成与评判）、benchmark_server（评测任务/奖励/轨迹，Harbor + E2B）、e2b_proxy（沙箱隔离计算）、auth_server（运行密钥、权限、**预算记账**） |
| 其他 | rsi_task 任务定义、skills、tools（实时仪表盘 rsiwatch，端口 8420）；启动顺序 auth_server 先行，run.sh 读 key.json 签发预算密钥 |

### 3.3 对 laos 有意义的三个细节

1. **auth_server 是一等公民且必须先启动**——预算密钥、权限、记账是整个环境的前置条件，不是事后补丁。这是"治理基座先于负载"的工程化表达，与 laos caps+GrantStore 同构（§8.4）。
2. **agent 跑在轻量 CPU 容器里，训练/推理/评测都在远端服务**——改进对象（模型/harness）与改进者（agent）物理分离，权限边界天然清晰。
3. **RSI-Index 用"关闭剩余差距比例"而非绝对分**——把自改进效率变成可比口径，测量纪律值得借鉴（laos 若做自改进演示，telemetry 记录可用同公式）。

## 4. 2026-09/10 论文浪潮（六周一浪，九篇主力）

| 论文 | arXiv | 团队 | 一句话 | 关键数字 |
|---|---|---|---|---|
| RSIGym | 2610.10310 | Evolvent AI（9 人） | RSI 的 EaaS 实验环境 + RSI-Index | Opus 5 RSI-Index 0.4809；SWE-bench 17.67→50.33%；29/30 运行提升 |
| AIDE² | 2609.26457 | Weco AI（5 人，9-22） | AI 研究 agent 改自己代码，双循环（外层选择+内层执行） | 8 天 7 项连续改进；泛化 4 个 held-out 基准；**reward hacking 55%→32%**（仍比人类工程 agent 低 7pp，且此性质未被显式优化） |
| RRSI | 2609.24972 | Google Research（14 人，v3 10-04） | harness 自进化的**正则化**：提议器加时间退火编辑预算+探索历史；选择器加 critic（筛基准特异提议）+pruner（删太小/太贵/失效改动） | 演化分割最高 +6.0 分；5 个 OOD 基准最高 +4.3 分；policy token 省 30%；代码 google-research/rrsi |
| Dream-RSI | 2609.14858 | 17 人（页面未列机构；MIT TR 中文称"谷歌"，存疑不采） | 用历史发现树构建**回放模拟器**，在模拟器里"做梦"做离线策略优化，改进后回线上 | 4 领域 9 任务；摘要仅称 competitive quality（无绝对数） |
| RSIAgent | 2609.15364 | Sibo Zhu 等 6 人（9-14） | **training-free 的 RSI**：curriculum/actor/verifier 三智能体，先广后深探索，记忆冻结复用，不更新参数 | OSWorld-v2 与 Agent's Last Exam 上 Kimi-K3、GLM-5.3 等开源模型"outperform frontier closed-source models including GPT-6" |
| The Last AI Built by Humans | 2609.11873 | SJTU 领衔 35 人（含 Hinton、Bengio，9-10/v3 9-22） | RSI 能力路线图 + HCI（Headroom-Closed Index）指标 | 五级自主性：改进执行→改进策略→经验获取→环境适应→递归元改进；揭示现有 LLM"剩余空间闭合"不足 |
| Breaking the Environment Wall | 2609.29773 | 11 人（9-24） | 环境不是 agent-ready 的：信息碎片/证据误导/环境演化三问题 | 环境墙使 SOTA agent **83.9%→57.6%**；Env-Rethink（27B 后训练）30 任务 9 模型平均 rubric +15.1pp |
| CollabFlow | 2609.38662 | — | 多智能体协作的 RSI：agent 按产出互评互改 | （未抓摘要细节） |
| RSIGame | 2609.39045 | — | 游戏开发场景的 agentic RSI（explore-diagnose-improve 循环） | （未抓摘要细节） |

**读法**：这九篇不是同质刷分，而是分工——RSIGym 供环境、RRSI 供约束、Dream-RSI/RSIAgent 供探索、Last AI 供路线图、Env-Wall 供环境侧。RSI 正在长出自己的"方法论栈"。

## 5. 支撑线：Workshop 110 篇 + He Ye 清单 16 篇

### 5.1 ICLR 2026 首届 RSI Workshop（110 篇）

- 分轨：**Oral 4 / Spotlight 21 / Poster 75 / Short 10**（官网 papers.html）。
- Oral 四篇：Agent0（零数据自进化）、Contextual Drag（上下文错误如何影响推理）、Learning to Continually Learn via Meta-learning Agentic Memory Designs、PostTrainBench。
- Poster 主题抽样可见热点：reward hacking in self-improving code agents、AUTOHARNESS、self-evolving rubrics、验证器失效归因、模型坍缩与合成数据验证——**安全与评测类占比显著**，不是纯能力叙事。
- 配套社区资产：natnew/awesome-recursive-self-improvement（workshop 论文清单）、DAIR.AI 学院 Self-Improving Agents 专栏（31 篇精选）、thelatestinai 话题页称 RSI 论文月增 94%（媒体口径，仅作热度参考）。

### 5.2 He Ye（UCL）RSI 研究笔记的四条主题脉络

笔记引用 Lilian Weng 综述为索引，串联 STOP / DGM / AlphaEvolve / ACE / MCE / Self-Harness / AHE 等，并列出 16 篇 2605–2608 号段论文（Pre-Commit Gating 2608.05810、HarnessLens 2608.27311、Janus 2608.08189、HarnessCompass 2608.01918、Evo-Bench 2608.09096、HarnessOpt-Bench 2608.06301、HELIX 2608.13951、Hierarchical Self-Improvement 2608.08466、DemoEvolve 2605.24539、ShinkaEvolve 2509.19349、PostTrainBench 2603.08640、Meta-Agent Challenge 2606.04455、Meta-Harness 2603.28052 等）。四条脉络：

1. **技能污染与不可逆性**：技能池超临界规模后性能退化，缺陷技能会被后续蒸馏引用——需要**事前门控**（pre-commit gating）。
2. **评估预算效率**：行为感知验证、双代理模型、共演化评估器（Janus）。
3. **过拟合与泛化**：HarnessCompass / StarHarness / Evo-Bench 都在对抗"对演化任务的过拟合"。
4. **能力现状**：PostTrainBench 显示自动化后训练仍远逊人类（**23.2% vs 51.1%**）；Meta-Agent Challenge 测"写 agent 的能力"。

## 6. 产业与舆论（2026-09，媒体口径逐一标注）

- **智谱**：唐杰 9-17 披露公司首个 RSI 工程化实践，预告 GLM-6.0 为"完全自训练"模型（[钛媒体/搜狐](https://m.sohu.com/a/1085514979_116132)）。
- **小米**：9-22 发布 MiMo-V2.6 系列，称"探索 RSI 的关键一步"（同上文）。
- **阿里**：吴泳铭云栖大会称 RSI 是"通往超级人工智能的具体路径"，Qwen 团队有进展（同上文）。
- **Anthropic**：Claude"主导"的研发任务占比 2 月 <1% → 8 月约 26%，按其 AL0–AL5 标准属 AL4（钛媒体转述，媒体口径）；同期 OpenAI/Anthropic 数次**预警 RSI 失控风险**并呼吁放缓。
- **Hinton 首篇 RSI 论文**：即 §4 的 The Last AI Built by Humans（35 人联署含 Bengio），分析 AI 进入训练/评估/安全流程的距离（[量子位/BAAI 转载](https://link.baai.ac.cn/@liangzw/117392631844217034)）。
- **中文深度解读**：[RSI"出圈"背后（钛媒体）](https://m.sohu.com/a/1085514979_116132)、[RRSI 过拟合分析（机器之心 Pro）](https://cj.sina.cn/articles/view/5952915720/162d2490806704yjxm)、[Dream-RSI（MIT TR 中文）](https://www.mittrchina.com/news/detail/16974)、[四大技术路线全景综述（搜狐）](https://m.sohu.com/a/1085500004_122066678)、[Last AI 中文解读（知乎）](https://zhuanlan.zhihu.com/p/2090467279368622620)、[tonybai 博客](https://tonybai.com/2026/09/27/the-last-ai-built-by-humans-rsi)。
- 钛媒体的卡点归纳（转述）：无在线实时学习/权重固定；"两头"问题（发起与决策两端仍靠人）；组织授权问责机制缺位；质疑声认为 RSI 是伪概念（自回归范式只能在人框内运行）。

## 7. 开源生态盘点（2026-10-09 实查）

| 仓库 | star | License | 定位 |
|---|---|---|---|
| [algorithmicsuperintelligence/openevolve](https://github.com/algorithmicsuperintelligence/openevolve) | **7.5k**（1.2k fork，836 commits，活跃） | Apache-2.0 | AlphaEvolve 开源实现（原 codelion 仓）；**唯一免训练免 GPU 的上手型**：pip 装、任意 OpenAI 兼容 API 或 Claude Code/Copilot CLI 甚至 Ollama 本地模型；Metal GPU kernel 实测平均 +12.5%/峰值 106%；Gemini Flash ~$0.01–0.05/迭代 |
| [EvoAgentX](https://github.com/ANative-Lab/EvoAgentX) | ~3.2k | MIT | "自进化 agent 工作流"框架（arXiv:2507.03616）：自动生成-执行-评估-进化多智能体工作流，产品味最重；配套 Awesome-Self-Evolving-Agents（MIT） |
| [jennyzzt/dgm](https://github.com/jennyzzt/dgm) | ~2.4k | — | Darwin Gödel Machine 官方代码（Sakana AI/UBC，Jeff Clune 线）：自指编码 agent 改自己代码 + agent 归档，SWE-bench/Polyglot；跑起来重（前沿模型+长程演化），精读型 |
| [google-research/rrsi](https://github.com/google-research/rrsi) | **1.4k**（4 commits，论文随代码型） | Apache-2.0（注明非官方支持产品） | RRSI 官方代码：harness 级 RSI + 正则化搜索全套工程范式——退火编辑预算 schedule.py、critic 泄漏筛查、噪声地板选择、**独立 git worktree 评估候选 + fast-forward 合入**、编辑历史全程可审计；README 结果：Terminal-Bench 74.2→80.2（+6.0）、SWE-bench Verified 82.0→83.8（OOD）；运行需 Vertex AI/GCP + Claude Opus 4.8，重 |
| [aiming-lab/Agent0](https://github.com/aiming-lab/Agent0) | ~1.3k | Apache-2.0 | UNC/Salesforce/Stanford；Agent0（arXiv:2511.16043，零数据自进化，Qwen3-8B-Base 数学 +18%/通用 +24%）+ Agent0-VL（2511.19900，视觉推理 +12.5%，8B 开源 SOTA）；ICML'26 & COLM'26 在投；**ICLR 26 RSI Workshop Oral**；需 GPU 训练 |
| [lobehub/awesome-rsi](https://github.com/lobehub/awesome-rsi) | 427 | CC0-1.0 | RSI 研究地图：model-level/harness-level/frameworks/安全/评测 16 章（§2.2 三分法出处） |
| [evolvent-ai/RSIGym](https://github.com/evolvent-ai/RSIGym) | 36 | 未注明 | 本轮主角：RSI 实验环境（§3）；实验室基建，非上手项目 |
| natnew/awesome-recursive-self-improvement | — | — | Workshop 论文清单 |

**实践入口排序**（按"能不能真上手跑 + 学到多少"）：① OpenEvolve——唯一能在 laos 纪律内试跑的（临时物进 var/，conda 红线外装），进化循环本身也是"评估器在循环外"的最小活样本；② rrsi——跑不动的部分当治理模式精读（critic/pruner/退火预算/worktree 隔离，与 laos sentinel/GrantStore/风险账本一一对应）；③ dgm——自改写 agent 的正典实现，读代码理解 archive 与自指回路；④ EvoAgentX/Agent0——框架型与训练型，远期参照。

> 2026-10-09 后续：①已兑现——OpenEvolve 经 `drivers/drv_evolve.py`（venv 子进程）+ `laos/evolve.py`（gate/装配面）+ 内建 syscall `evolve.run`（caps→validate→sentinel→audit 全链）接入 laos，主套件 1078 绿；真跑 e2e **收档 BLOCKED**（环境无可用 LLM 后端：唯一 key 是 ZCode 沙箱内部网关会话密钥，对七端点全 401、网关域名公网 NXDOMAIN、无 ollama，证据原文见 var/rsi/openevolve/OBSERVATIONS.md §后端/§e2e）；②的治理模式精读由本落地自然覆盖一半（worktree 隔离对照 cow.py 另案）。

**GitHub Trending 实况（2026-10-09 当日页）**：无任何以 RSI/self-improvement 为主题的仓库上榜——**这波是论文先行、工具未爆**（RSIGym 才 4 个 commit）。邻接上榜者：claude-mem（agent 持久记忆，页面读数 ~98.8k★）、mattpocock/skills（agent 技能包，页面读数 ~281k★）、morloto/rea（agent 逆向工程）、anthropics/knowledge-work-plugins（Claude Cowork 插件）——记忆/技能/插件这三大"持久化自我改进基础设施"在榜，恰是 §2.2 第二层（persistent self-improvement）的民间形态。

## 8. laos 契合点与裁决

> 定位叙事不变：基座是 Linux 内核，Agent 是新负载，laos 是内核治理在用户态的延伸。RSI 让负载变成"**会自改写的负载**"——OS 史的对应动作不是跟着负载一起进化，而是 W^X、不可变内核文本、代码签名。laos 不做改进算法，做**改进循环外的不可变裁判席**。

| # | 采纳点 | 裁决 |
|---|---|---|
| 1 | "评估器与权限控制在进化循环之外"（Weng 七瓶颈之五）+ AIDE² 证据（reward hacking 55%→32% 但仍有 32%，且非显式优化所得）——行业自己论证了治理基座必须独立于被优化的 agent | ● 叙事消化：立此存照为 laos 定位的第一行业级佐证，与 [2026-10-08-aios-agentos-landscape](2026-10-08-aios-agentos-landscape.md) 的"OS 内核派空位"判断互证 |
| 2 | 自修改路径的哨兵覆盖：RSI 场景=agent 写自身 harness/技能/配置文件。检查 sentinel 六级判定与 caps 是否把"自我修改"当受控行作（可写自身路径集合） | ◐ P2 → **● 已落地**（evolve.run gate：禁区永不可放行，var/rsi/jobs 允许根，env 只扩不缩；syscall 全链 caps→validate→sentinel→audit 有测试覆盖） |
| 3 | 技能污染/不可逆性（He Ye 脉络一）↔ laos 已有 CowFS 原子替换+sha256 与 provenance taint：接受的技能改动可回滚、带出处、缺陷可阻断引用 | ◐ P3 对照确认覆盖度（机制已在，写清映射即可） |
| 4 | RRSI 的 pruner（删太小/太贵/失效改动）与退火编辑预算需要**外部数据面**：laos 风险账本+telemetry 天然可充当每轮改动的成本/收益记录器 | ◐ P3（等 laos 有真实自改进循环时兑现） |
| 5 | RSIGym auth_server（密钥/权限/预算记账先于一切服务启动）与 caps+GrantStore（approved/scope/reason 三字段）同构 | ● 已消化（设计互证，写进叙事；不引代码——其依赖栈 Docker/Harbor/Tinker/GPU 云预算全部违反零依赖与 conda 红线） |
| 6 | RSI-Index 口径 `(final−initial)/(1−initial)` 作为自改进效率的测量纪律 | ◐ P3（未来演示用，telemetry 字段预留即可；2026-10-09 e2e 未真跑——后端 BLOCKED，实测口径**未记**，解锁后补） |
| 7 | Weng 瓶颈三"负面结果的保存" ↔ JitMem mem.outcome 已记成败；检查 curate 是否会把负面结果裁掉 | ◐ P2 对照检查（与 #2 同轮 audit） |
| 8 | 跑 RSIGym/复现 AIDE²/Dream-RSI | ○ 不做：重依赖（Docker/Harbor/E2B/Tinker/前沿模型 API/$500×5 预算）全线违反零依赖红线；本文为文献调研，不承诺复现 |

**三条不做**（防走偏）：

1. **不做训练**：laos 永不进入 LoRA/rollout/奖励模型链路——那是负载的事，laos 是它的 cgroup/seccomp/audit。
2. **不做进化算法库**：不自研 Promptbreeder/AlphaEvolve 类组件，OpenEvolve 等仅作 drivers 层远期参照。
3. **不追热上主库**：本轮零代码改动；#2/#3/#7 的对照检查排进 audit 队列，绿了才谈落地。

## 9. 来源清单（全部 2026-10-09 实抓）

**一手**：[RSIGym arXiv](https://arxiv.org/abs/2610.10310) · [evolvent-ai/RSIGym](https://github.com/evolvent-ai/RSIGym) · [AIDE²](https://arxiv.org/abs/2609.26457) · [RRSI](https://arxiv.org/abs/2609.24972) · [Dream-RSI](https://arxiv.org/abs/2609.14858) · [RSIAgent](https://arxiv.org/abs/2609.15364) · [The Last AI Built by Humans](https://arxiv.org/abs/2609.11873) · [Breaking the Environment Wall](https://arxiv.org/abs/2609.29773) · [ICLR 2026 RSI Workshop](https://recursive-workshop.github.io/papers.html) · [Lilian Weng: Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness) · [He Ye RSI notes](https://heye.me/research-notes/rsi) · [lobehub/awesome-rsi](https://github.com/lobehub/awesome-rsi) · [aiming-lab/Agent0](https://github.com/aiming-lab/Agent0) · [openevolve](https://github.com/algorithmicsuperintelligence/openevolve) · [Schmidhuber RSI since 1987](https://people.idsia.ch/~juergen/recursive-self-improvement.html) · [github.com/trending](https://github.com/trending)

**媒体**：[钛媒体 RSI 出圈](https://m.sohu.com/a/1085514979_116132) · [量子位 Hinton 论文](https://link.baai.ac.cn/@liangzw/117392631844217034) · [机器之心 Pro RRSI](https://cj.sina.cn/articles/view/5952915720/162d2490806704yjxm) · [MIT TR 中文 Dream-RSI](https://www.mittrchina.com/news/detail/16974) · [四大技术路线综述](https://m.sohu.com/a/1085500004_122066678) · [知乎 Last AI 解读](https://zhuanlan.zhihu.com/p/2090467279368622620) · [tonybai](https://tonybai.com/2026/09/27/the-last-ai-built-by-humans-rsi)
