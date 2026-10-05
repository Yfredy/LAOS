# laos 采纳总纲（Capstone 映射报告）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把全部已学资产（19,792 篇双会议论文 / 3,724 个 OSS 仓库 / Jev 生态 / jev-chat-jarvis 评估 / Apple·DCASE·挑战赛结论）按 laos 架构逐项映射为"可取之处 → 落点 → 状态"，产出终版总入口报告 `docs/research/2026-09-19-laos-adoption-capstone.md` + 调研索引 `docs/research/INDEX.md`，并接入 README。

**Architecture:** 纯文档交付（不改代码，不新建沙箱——用户提出的"多开几个项目文件夹"记为后续代码增量的惯例：每个主题一个 `<Topic>-ZCode/`，本计划无需）。报告**按 laos 架构组织而非按来源组织**：四段漏斗为主线，内核语义层/端侧真机/AgentOS 广域为支线；每条映射固定四字段（来源｜可取之处｜laos 落点｜状态），状态 ∈ {已落地(带 commit)、推荐 P0-P3、不做(带理由)}。

**Tech Stack:** Markdown；引用既有 11+ 份调研文档的相对链接；数字一律引用来源文档（不新算）。

**Spec:** 本计划 §Task 2 的骨架与样例条目即规格。来源资产清单（Task 1 产出为准）。

## Global Constraints

- 每条映射必须有可点的证据链接（既有文档相对路径或外部 URL）；无链接的条目不收
- 状态为"已落地"的条目必须带 commit hash（从 git log 查证）；"不做"必须一句话理由
- 不新造数字：所有量化结论引用来源文档原句/原数
- 报告 ≤400 行（总纲是索引与裁决，不是内容搬运；细节留在各源文档）
- README 只加两行（§10.1 头部总入口 + 目录速览不改）

---

### Task 1: 资产盘点（来源清单）

**Files:**
- Create: `docs/research/INDEX.md`（索引文件，Task 3 完成内容）

**Interfaces:**
- Produces: `docs/research/` 下全部 .md 的权威清单（含一句话定位），供 Task 2 引用

- [ ] **Step 1:** `ls docs/research/*.md docs/research/always-on-recording/*.md docs/research/jev/*.md` + 逐份 head -5 确认定位
- [ ] **Step 2:** 生成清单（预期 ≥16 份：业界 6、模型地图 4、双会议普查 2、ICASSP 五年 1、OSS 景观 1、Jev 2、jarvis 评估 1、capstone 本身）；每份一行：文件名｜一句话｜关键数字

### Task 2: 终版映射报告（核心交付物）

**Files:**
- Create: `docs/research/2026-09-19-laos-adoption-capstone.md`

**Interfaces:** 无代码接口；README 接入靠 Task 3。

骨架（§A-§G 逐节写实，每节为映射表 + 3-5 行裁决叙述）：

**§A 总览矩阵**（laos 架构 × 来源域，一张 15-20 行表：行=laos 模块，列=论文/OSS/产品/教训，格=状态色 ●已落地 ◐推荐 ○不做）

**§B 四段漏斗映射**（主线）。样例条目（四字段格式，执行时照此密度全写）：
- Apple Watch S12 音频智能｜15s 环形缓冲=②触发捕获、7 天删=④即焚的消费者级验证｜journal 标题 schema + time: 窗 + 6h 即焚｜已落地（AlwaysOnRec-ZCode，bbf5f5e）
- Streaming Sortformer (IS25)｜到达序说话人身份，不建长期声纹库｜"谁的日记"标注，PIPL 对齐｜推荐 P1
- DCASE'25 Task1 冠军 61.5%@122K/29MMACs｜大教师→小学生蒸馏范式｜ADSP 白名单事件（哭声/警报/门铃→/events）｜推荐 P1
- Mimi/SNAC 1.1/0.98 kbps｜留存格式=模型表示合一｜audiostore 已落地 µ-law 档，SNAC 为可选依赖｜已落地（80be49b 前序 bbf5f5e）
- TRILLsson (IS22)｜<4% 体积情感任务反超 wav2vec2｜端侧情感兜底参照｜推荐 P2
- URGENT Challenge (IS24/25)｜7 类失真统一评测｜journal"先增强再转写"的内部评测蓝图（SE 后 WER 必回归）｜推荐 P1（配 2501.02452 桥接结论）

**§C 内核语义层映射**：AIOS/AgenticOS'26 论文族（Irreversibility Budget→FleetLedger 已落地；Fork-Explore-Commit→BranchContext 已落地；stale context→观察簿已落地；AgentProf→span 导出已落地——各带 commit）；Jev 判断层（四闸门已落地 7dae105 + 校准台 0.519 警示）；Context Manager（token=内存管理已落地）；**缺口行**：FUSE BranchFS/gVisor/Federated composite（KTH 最佳论文）→ 不做/远期带理由

**§D AgentOS 广域映射**：screenpipe（参照+source-available 许可警示）、Omi（自托管）、pipecat ★15.5k/agenticSeek ★27.2k（voice agent 运行时参照——laos 为何不直接用：无能力管控/审计层）、Meetily/Vexa（bot-free 会议参照）、mem0（三级记忆对照）、OpenVoiceOS 插件化、Abridge/Dragon（B 端合规姿势参照）

**§E 端侧与真机**：QNN ADSP LPAI <5mW（已落地真机闭环）、GTCRN 33MMACs 锚点、34.7µW KWS IC 功耗标尺、Termux 矩阵、EdgeSpot PCEN（已落地）

**§F 已拒绝清单汇总**（一表收口）：jev-chat-jarvis 伪装采集七文件、多模态视频系（HumanOmni/AVSE）、云常开系（Rewind/Limitless 死因）、职场教育情绪识别（AI Act）、GPT-4o-audio（零云约束）——各一句理由 + 出处

**§G 优先级路线图 v2**：合并所有历史 P0-P3 去重成一张 12-15 行表（行=事项，列=依据来源数/预计工作量/依赖），标注哪些已被本会话消化

- [ ] **Step 1:** 按 §A-§G 骨架写全文（执行者需先读 INDEX.md 清单 + git log 查证"已落地"commit）
- [ ] **Step 2:** 自查四约束（链接全/commit 真/不造数/≤400 行）
- [ ] **Step 3:** `git commit -m "docs(research): laos adoption capstone — 全资产按架构映射的总纲（来源→可取之处→落点→状态）"`

### Task 3: 索引与 README 接入

**Files:**
- Modify: `docs/research/INDEX.md`（Task 1 的清单扩为含 capstone 的导航：按"想了解 X → 读 Y"组织）
- Modify: `README.md`（§10.1 标题下加一行：`> 📌 **总入口**：[laos 采纳总纲](docs/research/2026-09-19-laos-adoption-capstone.md)——全部调研按 laos 架构的逐项映射与裁决。`）

- [ ] **Step 1:** INDEX.md 按问题导航重排（"想做全天候录音→读哪三份""想选模型→读哪四份""想做 Agent 治理层→读哪两份"…）
- [ ] **Step 2:** README 加总入口行（仅此一行，不动其他）
- [ ] **Step 3:** `git commit -m "docs: research INDEX navigation + README capstone entry"`

### Task 4: 收尾

- [ ] Step 1: 全量测试不涉及（纯文档）；`git push origin master`（失败 60s×3 重试）
- [ ] Step 2: 交付说明：报告路径、映射条目总数、三个状态的数量分布（已落地/推荐/不做）

## Self-Review

- 覆盖：论文（§B/§C）✓ OSS（§D）✓ 产品/教训（§B/§F）✓ AgentOS/AIOS 广域（§C/§D）✓ 音视频限定（全篇听觉主线+视频系归入拒绝）✓ 用户"多开项目权限"诉求（Architecture 段记为后续惯例）✓
- 占位符：§B 样例六条已写实四字段密度，§C-§G 各节有具体条目来源 ✓
- 一致性：状态三值与 §G 路线图列名一致；commit hash 由执行者 git log 查证而非凭记忆 ✓
