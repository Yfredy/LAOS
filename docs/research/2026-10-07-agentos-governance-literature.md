# AgentOS 窄分支治理文献对照（venue-expansion 语料强命中 49 篇）

> 日期：2026-10-07
> 来源：venue-expansion 语料（38 venue 注册切片，[多场地普查](2026-10-06-venue-expansion-survey.md)）中 `--topic agent-os --strong-only` 的强命中窄分支，**实测 49 篇**（计划书按旧语料估 44，本批为实测数）。
> 底账：全清单导出 [agent_os_narrow.tsv](../../corpus/venue_expansion/agent_os_narrow.tsv)（title/year/venue/doi 四列 49 行，与本文表格同序）。
> 纪律：DOI/年份/venue 一律抄自语料 json（`var/agent_os_strong.json`）；无摘要篇标【仅标题】，按标题+领域常识谨慎裁决，不编摘要；量化数字只引论文原句。

---

## §方法

- **取材**：`query_corpus.py --topic agent-os --strong-only --limit 0 --json` → 49 行 JSONL。强命中=agent-os 主题词在标题/摘要强命中（Task 2 口径），非人工筛选。
- **摘要可得性**：**有摘要 42 篇 / 仅标题 7 篇**。仅标题 7 篇全部落在非 anthology 来源——NeurIPS 2025 ×2（Cambridge DOI）、KDD 2026 ×4、WebConf 2026 ×1（crossref 会议记录无摘要字段）；anthology 系（ACL/EMNLP/NAACL/Findings 含 industry）、IJCAI、AAAI、ACM TOMM 全部有摘要。
- **裁决方法**：每篇按 capstone 四列（来源｜可取之处｜laos 落点｜状态）逐篇裁决；落点对照 laos 当前能力面——syscall 闸门链 / seccomp+CoW+eBPF 强制层 / FleetLedger 风险账本 / MCP Tasks / 信箱 IPC / laosweb / 判断层（Jev 四闸门）/ audit 审计流 / 听觉栈三通道 / wakegate+dialogsched（v0.17.0 引入，现 v0.18.0）。找不到落点的写 ○ 并给一句理由。
- **venue×year 分布**：ACL 系 14（2020×1/2023×2/2024×2/2025×9）· IJCAI 16（2021×4/2022×1/2023×1/2024×1/2025×2/2026×7）· AAAI-26 11 · KDD-26 4 · NeurIPS-25 2 · WebConf-26 1 · ACM TOMM 1（2016）；按年：2016×1/2020×1/2021×4/2022×1/2023×3/2024×3/2025×13/**2026×23**——近半是 2026 新文，治理议题正在加速。
- **构成判读（诚实声明）**：强命中词表把"agent+resource/allocation"类多智能体分配/公平/审计理论（§C 16 篇＋B/D 组同族 #12/19/20/42/44/45/47，共 23 篇）大量带入；真正 OS 层治理文献约 1/4。这不是噪声——分配/公平/审计理论正是 FleetLedger 与配额语义的学科根基，但本文按"是否对 laos 能力面有落点"如实分级，多数理论篇裁决为 ○。

---

## §对照表（四组分表，全局连续编号 1–49）

> 状态记法同 capstone：**●已落地**（代码在库，附 commit）/ **●已消化**（论据或口径入库，无新代码）/ **◐推荐 P0–P3** / **○不做**（附理由）。落点找不到的写 ○。

### A. OS 治理与工具链（11 篇）

| # | 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|---|
| 1 | 2025·EMNLP·Tool Preferences Unreliable | 对 MCP 工具描述做细微措辞编辑，即可让竞争场景下某工具被调用量**放大 10 倍以上**（GPT-4.1/Qwen 实测）——工具选择完全不可靠 | 这正是"visibility ≠ permission"的实证：laos syscall 闸门链+task_scope 意图收窄（962d956）让"被诱导选中"≠"被允许执行"；反推工具/技能注册表的描述文本需防篡改审计（skills.py + Jev SKILL 闸门 3a1564b 的描述字段） | ●已消化（闸门必要性实证论据）＋◐P2（注册表描述防篡改审计） |
| 2 | 2026·AAAI·ToolSmith | 自动生成的工具必须经"NL 测试→**安全沙箱执行**→状态变更查 API 确认"闭环验证后才允许注册 | skills.py 技能沉淀 + seccomp 沙箱（088e63e）两件已有，"生成→沙箱验证→再注册"的闭环缺口 | ◐推荐 P2（技能注册前沙箱验证回路） |
| 3 | 2026·IJCAI·TraceBrain | 开源 agentic trace 管理基础设施——框架无关 OTLP delta schema，把 trace 从被动日志升格为**主动治理与 agent 适配**的资产 | audit 审计流 + agentprof.py 已导 OTLP/JSON（e88fb24, 9a94834）；缺的是"trace 反哺"回路（审计→风险参数/技能/记忆） | ●已落地（OTLP 底座）＋◐P2（审计反哺治理回路） |
| 4 | 2025·NeurIPS·DRIFT【仅标题】 | 动态规则防御+注入隔离（injection isolation）守护 LLM Agent | 提示注入是 laos 明确未覆盖面（闸门管"能不能调"，不管"话里被塞了什么"；Agent libOS 也自认不防）；判断层 prejudge 高危预审可挂注入特征检查作缓解 | ◐推荐 P2（prejudge 注入特征规则，仅标题级谨慎评估） |
| 5 | 2025·Findings-ACL·SMART | 元认知自省让 agent"能用参数知识就不调工具"，压 Tool Overuse 的算力浪费 | laos 治理哲学相反：靠内核强制（EDQUOT 次数预算+FleetLedger 风险加权，"rm -rf 与 ls 不同价"）而非 agent 自觉——留作路线对照论据 | ○不做（自觉路线与闸门路线互斥，laos 选闸门） |
| 6 | 2026·KDD·Memory Systems Diagnosis【仅标题】 | 自主 AI 研究代理的记忆系统**系统性诊断与基准**（低资源框架） | memory.py 单层 JSONL；冷热分层已列 P1（capstone §G#5）；诊断/基准框架应随分层落地后引入 | ◐推荐 P2（记忆质量基准，排在分层 P1 之后） |
| 7 | 2025·ACL·AXIS | API 优先于 UI 动作：任务时长与可靠性双收益，UI 仅兜底；API 可经自动探索持续扩充 | 与 laos 架构同构——驱动全 MCP 化（API 总线），drv_screen 只作通知/短信读取兜底；论据入库支撑"MCP=驱动总线"定位 | ●已消化 |
| 8 | 2025·EMNLP·EnterpriseBench | 企业环境 500 任务沙箱；核心难点=数据碎片+**细粒度访问控制**下的评测 | task_scope（能力说"能读"、任务说"读哪些"，越界 EACCES）正是该问题的单机版；企业域非当前场景，只取验收场景构造思路 | ◐参照 P3 |
| 9 | 2026·AAAI·EcoAgent | 端云协作多 agent 手机自动化，关键隐私决策=**验证所需截图不上云**（截图留端侧） | 零云约束的行业同向论据：laos 截屏仅本机（drv_screen）、云判断层默认关、ASR 全本地 | ●已消化 |
| 10 | 2025·Findings-EMNLP·GUI Localization Biases | GUI agent 定位幻觉的四类失败模式刻画 + PSS（Peak Sharpness Score）不确定度指标 | drv_screen 现为读取型；若未来扩展操控面，PSS 式动作置信度可挂判断层 score 判型做高危闸门 | ◐推荐 P3（操控面扩展的前置项） |
| 11 | 2026·KDD·TuneAgent【仅标题】 | 用 RL 让 Agent **调优操作系统内核**（agentic kernel tuning） | 属 [agentos-landscape](agentos-landscape-2026-08.md) §H（SchedCP 族"系统为 Agent 让路"线）；laos 是用户态薄内核，不改内核 | ○不做（内核调优域外，与 SchedCP 同裁决） |

### B. 审计·判断·会话（9 篇）

| # | 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|---|
| 12 | 2026·AAAI·Optimally Auditing Adversarial Agents | 审计策略化：委托方承诺审计策略、代理方选均衡——**审谁/何时审/如何罚**是最优机制设计问题 | audit 现为全量 JSONL（每 syscall 一行）；规模上升后"选择性审计+惩罚策略"是自然演进 | ◐推荐 P2（审计采样与升级策略） |
| 13 | 2026·IJCAI·Rule-Bottleneck RL | 高风险场景（孕产妇医疗资源序贯分配）中深度 RL 因不可解释不被采纳——LLM agent+规则瓶颈带出**可解释决策** | 判断层同构论据：criteria 式判据+决策留痕（jev 全路径 `event:"jev"` 审计，a65932a 系） | ●已消化 |
| 14 | 2025·EMNLP-industry·STREAQ | 分层选择性路由：大模型贵而准（稀有 AoI）、小模型廉而误报多——按风险分层选 tier | Jev 四后端（none/rule/cloud/local）分层路由同构；且印证校准警示（rule 后端 0.519 不得配 autogate，477af8c） | ●已消化 |
| 15 | 2025·NeurIPS·Emergent Risk Awareness【仅标题】 | 资源约束下理性 agent 涌现风险意识 | 对照论据：laos 把"风险意识"外部制度化（FleetLedger 记账在内核不在 agent），不赌涌现 | ○不做（仅标题；外部强制路线的对照项） |
| 16 | 2020·ACL·Blend Skills | 会话 agent"多技能融合"评测——孤立技能好≠融合流畅 | skills.py 技能库已有；对话内容质量评测非治理域 | ○不做（非内核治理面） |
| 17 | 2023·ACL·CLV persona | 稀疏属性+稠密文本+历史三源人设建模 | 用户画像踩隐私红线（laos 只做纵向差分，不建画像） | ○不做（画像红线） |
| 18 | 2023·ACL·ArgSciChat | 科学论文论辩对话数据集（41 篇 NLP 论文） | 无对话内容产品面（wakegate/dialogsched 是会话调度状态机，不产对话内容） | ○不做（数据集域外） |
| 19 | 2026·IJCAI·Credit Fairness | 共享资源池在线分配引入"信用公平"：不仅每轮 max-min，**累计获得差异**也要有界 | FleetLedger 两级记账+per-agent 风险帽已含累计维度；信用=跨会话累计公平的论据 | ●已消化 |
| 20 | 2026·AAAI·ARDE | 双层演化治理：外层监管 agent 按系统诊断信号（策略熵/Gini/完成率）生成治理规则，内层个体学习 | "监管 agent 看指标调规则"=FleetLedger 风险参数（现为静态阈值）的远期演进方向 | ◐推荐 P3（风险参数自适应，远期） |

### C. 多 Agent 资源治理理论（16 篇，IJCAI/AAAI/KDD 分配理论块）

> 判读：这一块是强命中词表带入的相邻学科——多智能体资源分配/公平/机制设计。laos 的对应物是 FleetLedger 风险账本与 syscall/存储配额（多 Agent 同机竞争预算与 ADSP/存储资源）。语义同源者标 ●已消化，纯理论无单机落点者 ○。

| # | 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|---|
| 21 | 2021·IJCAI·DRF with Meta-Types | 主资源公平（DRF）+元类型约束（位置/替代效应）——多资源配额公平的经典推广 | risk.py 加权记账+EDQUOT 配额=DRF 思想的单机风险版（"多资源不同价"同构） | ●已消化 |
| 22 | 2026·AAAI·Fairness and Stability | 共享资源分配在单调效用两类下的公平+**稳定性**刻画 | 多 agent 配额稳定性论据（FleetLedger per-agent 风险帽的语义正当性） | ●已消化 |
| 23 | 2025·IJCAI·Online Resource Sharing | 非货币在线共享机制的 1/2 鲁棒界及其随机化策略改进 | 配额机制设计理论背景；EDQUOT 已足当前规模 | ○不做（机制理论，不落代码） |
| 24 | 2026·AAAI·Fair Societies | 房屋/不可分资源公平匹配的两个可 tractable 算法 | 匹配市场域外（laos 资源=预算/存储/调用次数，非一次性匹配） | ○不做 |
| 25 | 2026·IJCAI·Fairly Dividing Random Items | 非同质随机物品公平+高效分配的存在性与快速算法 | 组合分配理论域外 | ○不做 |
| 26 | 2026·IJCAI·Every Bit Helps | 每 agent λ 个基数查询即达 O(n^(1/λ)) 最优 distortion | 社会选择理论域外 | ○不做 |
| 27 | 2024·IJCAI·Fairness in Dynamic Allocation（综述） | 动态多 agent 分配的公平与优化研究地图 | 背景综述；FleetLedger 已有参照系（Irreversibility Budget） | ○不做（背景参照） |
| 28 | 2023·IJCAI·Homophilic Agents | 异质 agent 同质偏好下的战略资源选择博弈 | 博弈域外 | ○不做 |
| 29 | 2026·IJCAI·Phi-Actor-Critic | 把一般和博弈导向帕累托有效**相关均衡**（而非任一 Nash） | MARL 协调理论域外；spawn 准入不做均衡求解 | ○不做 |
| 30 | 2021·IJCAI·AV Fleets | 车队去中心化资源分配（V2V，无中央派单） | "车队级"治理语义已由 FleetLedger 落地（spawn 准入保留水位，9285448 系）；车辆调度本身域外 | ○不做 |
| 31 | 2022·IJCAI·OTIMAPP | 调度无关的多 agent 路径规划——无论运行时怎么调度都互不阻塞 | 路径规划域外；locks.py 驱动并发无此需求 | ○不做 |
| 32 | 2026·IJCAI·EVA-Gen | 感知模块应从**价值**学习（重构价值对齐），而非均匀最小化重建误差 | MARL 感知域外 | ○不做 |
| 33 | 2025·IJCAI·CFC-Agent | LLM agent 在公共资源困境中会**过早耗竭**共享资源；"考虑未来后果"（CFC）框架缓解 | laos 设计的直接实证支撑：agent 自觉不可靠→未来后果须由内核外部记账（EDQUOT+FleetLedger） | ●已消化 |
| 34 | 2021·IJCAI·Institutions in Socio-Ecosystems | 多制度多规范的机构化 MAS 模型（规范的时空表达） | 能力阶梯+task_scope=单租户制度的形式化；多制度/多租户规范层是远期形态 | ◐推荐 P3（多租户规范层，远期） |
| 35 | 2021·IJCAI·Abstract Argumentation | 部分攻击知识下的多 agent 论辩框架（含二阶/公共知识建模） | 判断层判型契约已定（noul/choice/score），论辩语义域外 | ○不做 |
| 36 | 2026·KDD·PG-DyRA【仅标题】 | 势博弈引导的多 agent 动态城市资源分配 | 城市调度域外 | ○不做 |

### D. LLM Agent 应用·模拟·教育（13 篇）

| # | 来源 | 可取之处 | laos 落点 | 状态 |
|---|---|---|---|---|
| 37 | 2025·NAACL·EvoAgent | 进化算法自动把专才 agent 扩展成多 agent 系统 | 与权限哲学冲突：laos spawn 走 FleetLedger 准入+能力只收不放（task_scope 血统继承），不放开自动繁殖 | ○不做（自动繁殖 agent 与权限收窄互斥） |
| 38 | 2025·ACL·Beyond Frameworks | 多 agent 协作四维机制的受控实证：治理/参与控制/交互动态/**对话历史管理** | 后两维对应信箱 IPC（7874c3b）+context 管理两件已有；实证结论可指导信箱协议演进 | ◐推荐 P3（信箱协议演进参照） |
| 39 | 2026·AAAI·VIL2C | 信息价值（VoI）感知的 agent 间低延迟通信——按信息价值调延迟分布 | 信箱 IPC 现无消息优先级；VoI 式分级是可借鉴机制 | ◐推荐 P3 |
| 40 | 2026·AAAI·StoryBox | 多 agent 沙箱自底向上长篇故事生成 | 创作域外 | ○不做 |
| 41 | 2026·AAAI·KDR-Agent | 低资源多域 NER 的知识检索/消歧/反思多 agent 框架 | NLP 任务域外 | ○不做 |
| 42 | 2026·AAAI·AgentSwift | 价值引导分层搜索自动设计 agent（压评测成本） | agent.py 固定代理+spawn 准入；agent 自动设计域外 | ○不做 |
| 43 | 2026·AAAI·Hackathon for High Schoolers | 高中生 AI agent 入门的 hackathon 教学框架 | 教育域外 | ○不做 |
| 44 | 2026·KDD·MALLES【仅标题】 | 多 agent LLM 经济沙箱+消费者偏好对齐 | 经济模拟域外 | ○不做 |
| 45 | 2026·WebConf·PolicySim【仅标题】 | LLM agent 社会模拟沙箱做前瞻政策优化 | 政策模拟域外 | ○不做 |
| 46 | 2024·Findings-ACL·STSS | 行为层（沙箱模拟目标达成）客观评测语言 agent 社交智能 | laos 验收=unittest 实跑口径；社交基准域外 | ○不做 |
| 47 | 2024·Findings-EMNLP·SRAP-Agent | LLM 经济模拟公共住房稀缺分配政策（破完全信息/完全理性假设） | 政策模拟域外 | ○不做 |
| 48 | 2025·Findings-EMNLP·INDOORWORLD | 物理+社会紧耦合的异构多 agent 环境 | 虚拟环境层非 laos 组件（laos 环境即真实 OS） | ○不做 |
| 49 | 2016·ACM TOMM·Thunder Crystal | 众包带宽租赁的内容分发平台——按贡献计价的资源租赁市场（实测部署） | 市场计价与风险加权记账思想同构（贡献=风险不同价）；CDN 域外 | ○不做 |

> 状态汇总：●已落地 1（#3）· ●已消化 9（#1/7/9/13/14/19/21/22/33）· ◐推荐 10（P2×4：#2/4/6/12；P3×6：#8/10/20/34/38/39）· ○不做 29；另 #1/#3 两行为 ●＋◐ 双标（主状态已入前计数，◐ 事项见各行）。
> **49/49 全覆盖，来源计数=49**（四组为分组重排，编号全局连续；与 [agent_os_narrow.tsv](../../corpus/venue_expansion/agent_os_narrow.tsv) 的 49 行经 year+题名关键词双射核对，无遗漏无重复）。

---

## §八分类校验（对照 [agentos-landscape-2026-08](agentos-landscape-2026-08.md) 八含义与 L0–L5 强制力光谱）

### 新形态

**没有出现第九种"层"含义**——49 篇无一落在 L0–L5 之外的新抽象层。但有两个**含义级新强调**值得点名：

1. **"AgentOS = 多 Agent 资源公平治理器"**（本批 IJCAI/AAAI/KDD 分配族 23 篇的合流含义）：OS 语义不只是调度与隔离，还有**配额公平、累计信用、对抗性审计**。这不是新层（仍在 L2 语义层内，AIOS Scheduler 的延伸），但把 landscape §5 缺口表里"FleetLedger 风险记账"一条的学科根基显式化了——laos 已提前落在这条线上。
2. **"trace 管理层"**（#3 TraceBrain）：把可观测性从工具（AgentProf）升格为**治理回路基础设施**（trace 驱动 agent 适配与治理决策）。仍属 L2 语义层组件，不构成新层，但提出了 landscape 未明说的"审计反哺"命题（见修正节）。

### 确认

- **L0–L2 的 "visibility ≠ permission" 被 #1（Tool Preferences Unreliable）实证强化**：MCP 只解决"能看到"，工具描述甚至能被操纵放大 10 倍调用——权限必须内核闸门强制，laos 路线的正当性新增一篇 EMNLP 证据。
- **§F 沙箱线被 #2（ToolSmith 生成工具须沙箱闭环验证）与 #4（DRIFT 注入隔离）双确认**：隔离不只用于"跑不可信代码"，也用于"验证自产工具"与"隔离注入内容"。
- **§H 内核侧适配被 #11（TuneAgent）确认并外推**（仅标题级）：从 sched_ext 调度器扩展到"RL 调内核"的一般形态，"系统为 Agent 让路"议题面在变宽。
- **§G 记忆线被 #6（记忆系统诊断基准）确认**（仅标题级）：记忆系统可靠性已成为独立研究对象。
- **零云/端侧隐私约束被 #9（EcoAgent 截图不上云）确认为行业共识**而非 laos 独有偏好。
- **L2 定位再确认**：本批无一篇做 L4/L5 强制力——强制层议题仍在系统会议（SOSP 系），NLP/ML 会议贡献的是语义层与治理理论。

### 修正

- **审计的定位需从"可观测"升格为"治理回路"**：landscape §5 把审计放在 P2 可观测档（AgentProf）；TraceBrain 表明 trace 应参与治理与适配决策（审计→风险参数→闸门收紧）。属对 §5 缺口表的小修正，不动八分类框架。
- **多 Agent IPC（P2）的参照系换血**：landscape §5 该行对标 agentOS MsgBus/A2A（协议层）；本批 #38/#39（协作机制实证/VoI 通信）提供了**机制层**参照——信箱协议演进应同时看协议与调度机制两侧。优先级不变。
- **八分类框架本身无需修正**：49 篇全部可归入既有含义（A 用户态中间件语义件 / F 沙箱 / G 记忆 / H 内核侧适配 + 分配理论作为 L2 治理语义的学科根基），无一溢出。

---

## §对 laos 的三句话结论

1. **#1 的 10 倍操纵证据把"闸门必要性"钉死了**：工具描述可控调用率意味着 agent 的工具选择完全不可信——laos "visibility ≠ permission"（syscall 闸门+task_scope）不是保守设计而是唯一安全设计；顺带暴露一个 P2 实缺口：技能/工具注册表描述文本的防篡改审计。
2. **#3 TraceBrain 指出审计的下一跳是"反哺"**：laos audit+agentprof 的 OTLP 底座已落地（●），但 trace 还只是被动证据；把审计流策略化回灌风险参数与技能沉淀（审计→治理回路）是最值得吸收的架构思想（P2）。
3. **IJCAI/AAAI 分配块（DRF 元类型/信用公平/最优审计）是 FleetLedger 的免费理论背书**：多资源不同价、累计获得有界、审计策略化三个概念 laos 已各自落地或半落地，剩余可吸收点是**选择性审计策略**（P2）与**跨会话信用维度**的显式化。

---

## 附：复核命令

```bash
# 底账生成（与本文同源）
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --topic agent-os --strong-only --limit 0 --json > var/agent_os_strong.json
# 行数与摘要可得性核对（应得 49 / 42+7）
C:/Users/yaoyue/miniconda3/python.exe -c "import json;rows=[json.loads(l) for l in open('var/agent_os_strong.json',encoding='utf-8') if l.strip()];print(len(rows),sum(1 for r in rows if (r.get('abstract') or '').strip()))"
# TSV 行数核对（应得 49）
wc -l corpus/venue_expansion/agent_os_narrow.tsv
```
