# 全天候录音 · 业界应用补充调研：垂直赛道、Apple 音频智能、文章语料

> 调研时间：2026-09-11 ｜ 本文是 [2026-09-landscape.md](2026-09-landscape.md) 的**增量补充篇**，
> 补齐三条此前缺失的线：① B 端垂直应用（会议智能 / 医疗环境文档 / 销售收入智能 / 无障碍）；
> ② Apple Watch Series 12「音频智能」专题（2026-09-10 发布，业界最新变量）；
> ③ 文章 / 深度报道语料库。开源项目增补（Vexa / Meetily / Amurex / screenpipe 许可证变更）一并收录。
>
> 记法沿用姊妹篇：✅ 官方源已查证 ｜ 🔶 第三方/媒体声称 ｜ `未证实` 查不到可核验来源。

---

## 1. 一句话结论（本篇对收敛版结论的修正）

1. **"常开被动录音 = 已死"需要修正为"云常开 = 已死，端侧克制常开 = 刚被苹果转正"。**
   2026-09-10 发布的 Apple Watch Series 12「音频智能」（Siri Recap）就是**常开被动 + 环形缓冲 + 端侧蒸馏 + 7 天自动删除**，
   与 laos 四段漏斗逐项同构（见 §3 对照表）。此前全景表里"16 个产品只有 2 个常开被动且都死了"的判断，
   在消费级巨头入场后不再成立——死的死因是云依赖与留存政策，不是"常开"本身。
2. **全天候录音最大的商业应用根本不在消费硬件，而在 B 端垂直赛道**：
   医疗环境文档（Abridge 成为 Epic 首个 "Pal" 伙伴，200+ 医疗系统）与销售收入智能（Gong 单席位 $1,300+/年）才是钱所在，
   它们用真金白银回答了"业界如何应用全天候录音"——**应用形态全部是"会议/就诊/通话四段漏斗"，无一例外**。
3. ** consenting 争议从"偷不偷听"转向"旁观者知情"**：Apple 的 Siri Recap 全天聆听却**没有任何提示音/指示灯**
   （Live Rewind 有 chime，Recap 无声），Wired/PCMag 已用 "mass surveillance" 框架报道。
   这正是 laos「真机常驻通知」路线图项的差异化价值——**连苹果都还没做到的事**。

---

## 2. B 端垂直应用全景（业界"怎么用"的另一半答案）

> 此前调研全部集中在消费硬件与开源工具；本节补齐"谁在用、用来干什么、怎么处理同意与留存"。
> 每个赛道按收敛版的三判据（`always_on` / `processing` / `retention`）描述。

### 2.1 医疗环境文档（Ambient Clinical Documentation）——体量最大的常听场景

**应用方式**：诊室里手机/麦克风常听医患对话 → 自动生成结构化病历草稿（SOAP 格式）→ 医生审签入 EHR。
这不是"录音笔"而是"环境文档 Agent"：③段蒸馏直接产出**领域结构化产物**（主诉/现病史/评估/计划 + 计费编码）。

| 平台 | 2026 现状 | `always_on` | `processing` | `retention` | 来源 |
|---|---|---|---|---|---|
| Microsoft Dragon Copilot（Nuance DAX 合并） | 桌面+移动助手，已向护士扩展；宣称每诊节省 ~7 分钟 | 诊中常听，手动开停 | 云（Azure 健康云） | 云，HIPAA 合规 | [官方](https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot) 🔶（节省分钟数厂商口径） |
| Abridge | **200+ 美国医疗系统**；**Epic 首个 "Pal" 级伙伴**（"Abridge Inside" 从 Haiku 到 Hyperdrive 全嵌入）；从文档扩展到医嘱与决策支持 | 诊中常听 | 云 | 云 | [官方新闻稿](https://www.abridge.com/press-release/abridge-becomes-epics-first-pal-bringing-generative-ai-to-more-providers-and-patients) ✅ |
| Suki | $55M C 轮（估值 ~$4 亿）+ Zoom 战略投资；小诊所到企业；含计费编码建议 | 诊中常听 | 云 | 云 | [官方](https://www.suki.ai/press-releases/suki-announces-investment-from-zoom-ventures/) ✅ 🔶（估值媒体口径） |
| Ambience Healthcare | 与 Abridge 并列的卫生系统玩家 | 诊中常听 | 云 | 云 | [行业综述](https://getlimeai.com/ambient-clinical-documentation-companies/) 🔶 |

**同意与合规（对 laos 最有借鉴价值的一段）**：

- **The Lancet** 已发表 "the consent gap in ambient clinical AI"：采用速度远超患者同意实践，试验证明省时减负，但同意流程普遍落后。[原文](https://www.thelancet.com/journals/landig/article/PIIS2589-7500(26)00078-6/fulltext) ✅
- **HIPAA 不管，州窃听法管**：治疗目的记录 HIPAA 无特殊同意要求，但**全员同意州（如加州）的窃听法适用**——患者和医生都必须同意，泛隐私通知不够；2026 年已有针对厂商的诉讼出现。[两党同意州指南](https://www.scribing.io/blog/one-party-vs-two-party-consent-states-ai-scribing) 🔶
- 正面样本：Penn Medicine 向患者公开 FAQ，明确"经你同意"+HIPAA 合规。[官方 FAQ](https://www.pennmedicine.org/patient-resources/information-for-patients/ambient-documentation-faqs) ✅
- **ABA（美国律师协会）**：环境录音"与既有隐私法和同意框架存在张力"。[ABA Health Law](https://www.americanbar.org/groups/health_law/news/2026/ambient-ai-scribes-privacy-cybersecurity/) ✅

**对 laos 的启示**：
1. laos 的**显式触发 + 每次审计 + 即焚**正是医疗赛道被诉讼倒逼出来的合规姿势——消费产品可以靠用户协议糊弄，B 端不能。
2. 蒸馏产物应该是**领域结构化模板**（医疗是 SOAP，laos 的对等物是 diary 五章节 / journal 情绪标签），不是裸转写文本。
3. "同意"必须是**每次会话级、可撤回、双方可见**——laos 的确认横幅机制与真机常驻通知恰好覆盖。

### 2.2 会议智能（Meeting Intelligence）——竞争最红海、laos 用户最熟悉的赛道

**应用方式**：bot 入会或桌面端抓音 → 实时转写 → 摘要/行动项/话术分析。两条技术路线：**bot 入会**（Otter/Fireflies，
机器人以参会者身份加入并宣告）vs **bot-free 桌面抓音**（Granola/Meetily，听系统音频，不进会议）。

| 产品 | 2026 定位 | 路线 | 留存 | 来源 |
|---|---|---|---|---|
| Otter.ai | 转写准确率口碑第一（93–95%，好条件）🔶 | bot | 云，免费档有分钟帽 | [对比文](https://www.itsconvo.com/blog/otter-vs-fireflies-vs-fathom) |
| Fireflies | 销售团队向，集成最广 | bot | 云 | [排名文](https://meetingnotes.com/blog/best-ai-note-takers) |
| Fathom | 免费档最慷慨（无限录制 + 30 秒摘要），G2 评分最高 🔶 | bot | 云 | [评测](https://get-alfred.ai/blog/best-ai-meeting-notetakers) |
| Granola | 本地抓音 + 人工笔记混合，bot-free 派代表 | bot-free | 本地为主 | [bot-free 评测](https://get-alfred.ai/blog/best-ai-meeting-notetakers) |

**对 laos 的启示**：bot-free 路线（不进会议、抓本机音频）与 laos 的"本机驱动"架构同构；
laos 的差异点仍是**零云 + 能力管控**——这一档在会议赛道是空白（最接近的 Meetily 见 §4）。

### 2.3 销售收入智能（Revenue Intelligence）——"录音即资产"的商业化极致

**应用方式**：全部客户通话常录 → 转写 → 话术/竞品提及/异议处理/交易风险分析 → 教练反馈与预测。

- **Gong**：自品牌 "Revenue AI OS"，多模态收入信号处理 + 专职 AI Agent； Foundations 约 **$1,300–1,600/席/年**，50 人团队约 **$130K/年** 🔶。[官网](https://www.gong.io/) ✅ ｜ [定价分析](https://www.getmaxiq.com/blog/gong-ai-pricing) 🔶
- 批评点：关键词式 Smart Trackers 缺少生成式推理，CRO 流失声音出现（[Oliv AI 分析](https://www.oliv.ai/blog/gong-limitations-challenges) 🔶）。
- 竞品分野：Gong 强会话智能与教练，Clari 强预测与管道检视（[对比](https://www.sybill.ai/blogs/gong-vs-clari) 🔶）。

**对 laos 的启示**：键词匹配 → LLM 推理的迁移已经在 B 端发生；laos 记忆层检索（bigram）未来接入 LLM 重排是同一条路。
另外这是"录音同意"最成熟的场景——电话录音报信（"此通话将被录音"）是**可见指示的工业化形态**，与 laos 常驻通知同构。

### 2.4 无障碍（Accessibility）——全天候转写的"正当性天花板"

**应用方式**：实时字幕眼镜/App 供聋人与听障者使用，全天候开启的**正当性最高、反对声音最小**的场景。

- **XRAI Glass**：2.0 已全球发布——iOS + Android 双端（**无需眼镜也能跑在手机/平板上**）、支持新 AR 眼镜、75+ 语言翻译、ChatGPT 助手。[官方](https://xrai.glass/blog/2nd-edition-launches-globally/) ✅ ｜ [企业版](https://xrai.glass/enterprise/) ✅
- 社区实况：r/deaf 上 TranscribeGlass vs XRAI AR 的真实使用对比（助听器为主、字幕为辅是典型用法）。[Reddit](https://www.reddit.com/r/deaf/comments/1nc1nzp/experiences_with_transcribeglass_vs_xrai_ar/) 🔶
- 横评：五款 AR 实时字幕眼镜（[Hearing Tracker](https://www.hearingtracker.com/hearing-glasses/hear-with-your-eyes-five-ar-live-captioning-glasses) 🔶）；Even Realities 的无障碍字幕指南（[官方](https://www.evenrealities.com/blogs/buyers-guide/ai-glasses-for-accessibility) ✅）。

**对 laos 的启示**：无障碍是"常开"最有说服力的产品故事——laos 看护/老人场景的对外叙事应向它靠拢
（"听觉辅助"而非"监控"），与社会接受度篇的措辞结论一致。

---

## 3. 专题：Apple Watch Series 12「音频智能」（2026-09-10 发布）

> 来源：用户提供的中文分析 [iphoneplay 文章](https://www.iphoneplay.cn/2026/09/10/apple-watch-series-12-audio-intelligence-health/) 🔶，
> 官方口径经 [Apple 支持文档](https://support.apple.com/en-us/148354) ✅ 与 Apple Newsroom 交叉查证 ✅。

### 3.1 功能与机制

| 功能 | 机制 | 触发 | 留存 |
|---|---|---|---|
| **Live Rewind**（实时回放） | 双击表冠 → 转写**最近 15 秒**对话 | 手动，每次触发有提示音（chime） | 文本片段存 Siri App |
| **Siri Recap**（谈话纪要） | 全天环境聆听 → 按对话自动生成**标题 + 摘要 + 要点** | opt-in；可按**时间/地点**计划；控制中心随时关 | **7 天不保存自动删除**；可随时查看/编辑/删除；iCloud 端到端加密同步 |
| **Sound Recognition**（声音识别） | 警报器/门铃/婴儿啼哭等 → 通知 | 常开检测 | 仅事件通知 |
| **音乐识别** | Shazam 加速版 | 手动 | — |

硬件要求：Series 12 / Ultra 4（S11 芯片划出**安全隔离区**做临时音频处理——原始音频"完全不可访问，连 Apple 也不行"）；
**明确不识别说话人身份**；每项功能需单独 opt-in，用户决定 Siri Recap 在**何地何时**工作。

### 3.2 争议（与 Meta 眼镜同一条线）

- Live Rewind 有提示音，但 **Siri Recap 全天聆听完全无声**——旁观者无从知情。Wired/PCMag/Business Insider 以
  "mass surveillance" 框架报道；中文舆论直接以"全天候偷听"为题（[iphoneplay](https://www.iphoneplay.cn/2026/09/10/apple-watch-series-12-audio-intelligence-health/) 🔶）。
- Apple 的辩护：opt-in + 端侧处理 + E2E 加密 + Live Rewind 提示音。✅官方回应口径 🔶（辩护有效性为媒体评判）

### 3.3 与 laos 四段漏斗逐项对照（本专题核心）

| 漏斗环节 | Apple Watch S12 | laos | 判断 |
|---|---|---|---|
| ① 常驻检测 | 环境聆听，产出"高阶笔记"而非全录 | StreamingVAD / ADSP LPAI | **同构**：双方都拒绝"全录 24 小时" |
| ② 触发捕获 | **15 秒环形缓冲**（Live Rewind） | 环形缓冲补 pad 成段 | **同构**——消费级巨头验证了 laos 的环形缓冲方案 |
| ③ 蒸馏 | S11 安全隔离区**端侧**处理 → 标题+摘要+要点 | SenseVoice 本地 GPU / 端侧 | **同构**；Apple 的三段式 schema 值得抄（见 §6 计划 Task 1） |
| ④ 留存 | 摘要 **7 天自动删**（可手动保存），原始音频从不落盘 | 原始音频 **6 小时即焚**，文本长留 | laos 更激进：即焚对象是原始音频；Apple 干脆不让原始音频存在——殊途同归 |
| 说话人 | **明确不识别身份** | diarization 为规划中的缺口 | Apple 替 laos 的"不建声纹库"合规立场背书；laos 做 diarization 应只做**弱标签**（收敛版 §9.3 结论再获支撑） |
| 旁观者可见性 | Recap **无声无灯**（争议焦点） | 真机常驻通知（路线图项） | **laos 的差异化机会**：连苹果都没做，laos 把"正在录音"做成系统级可见状态 |
| 调度粒度 | 按**时间/地点**计划 + 控制中心一键关 | `LAOS_REC=0` 全局开关 + 能力表，**无时间维度** | 可抄：mic 能力加时间窗（见 §6 计划 Task 2） |

**一句话**：Apple 用一款手表把"克制版常开"从开源极客实践（screenpipe/laos）升格为消费级默认路线，
四段漏斗的每个环节都被独立验证；同时它在旁观者可见性上的妥协，恰好是 laos 下一步要拿下的高地。

---

## 4. 开源项目增补（收敛版表格之外）

| 项目 | 许可证 | 定位 | laos 可复用性 | 来源 |
|---|---|---|---|---|
| **Vexa** | 开源 | 会议转写 **API**：bot 入会（Meet/Teams/Zoom）或桌面抓音（vexa-desktop），Docker 自托管 ~1 小时，"开源 Fireflies 替代" | 中（bot-free 桌面抓音的工程参照） | [GitHub](https://github.com/vexa-ai/vexa) ✅ |
| **Meetily** | 开源 | "隐私优先会议助手"：**无 bot、 invisibly 本地抓音、本地 LLM 摘要**，"音频永不离开设备"——会议赛道里与 laos 哲学最接近的产品 | 中高（自托管会议纪要的 schema 与 UX 参照） | [官网](https://meetily.ai/) ✅ |
| **Amurex** | 开源 | 隐身会议 copilot：静默录制 + 会后转写 + **记忆层**；自托管永久免费 | 中（"会议记忆层"与 laos journal 定位重叠，可对比 schema） | [HN 讨论](https://news.ycombinator.com/item?id=42779378) 🔶 |
| **screenpipe** | ⚠️ **许可证已变**：MIT → **source-available**（另：YC S26 批次） | 24/7 屏幕+音频本地捕获事实标准 | 仍极高，但**商用需重读许可条款** | [官网博客](https://screenpipe.com/blog/open-source-ai-screen-recorder) ✅ |

> ⚠️ 修正收敛版全景表：screenpipe 标注为 MIT，现已是 source-available——引用其"开源标杆"地位时需注明。

**新品补充（中文生态）**：字节 **Ola Friend**（$169/6.6g 开放式 AI 耳机，接豆包；一代豆包眼镜因差异化不足已内部砍掉）[Yicai](https://www.yicaiglobal.com/news/tiktok-owner-bytedance-launches-usd169-ai-earbuds-in-china) ✅ ｜ **Rokid Glasses**（2026-01 主打"比雷朋更轻、录音更长"）[官方](https://www.rokid.com/) ✅ ｜ IFA 2026 主旋律 = "context + voice + agent"（[综述](https://dymesty.com/blogs/articles/ifa-2026-wearable-ai) 🔶）。

---

## 5. 文章语料库（按用途分类，全部经 2026-09-11 检索核验）

**对比评测类**（选型/竞品分析用）：
[Otter vs Fireflies vs Fathom 2026](https://www.itsconvo.com/blog/otter-vs-fireflies-vs-fathom) ｜
[Best AI Note Takers 2026 (meetingnotes)](https://meetingnotes.com/blog/best-ai-note-takers) ｜
[Bot-Free Notetakers (get-alfred)](https://get-alfred.ai/blog/best-ai-meeting-notetakers) ｜
[Best AI Meeting Notes (zackproser)](https://zackproser.com/blog/best-ai-meeting-notes-2026) ｜
[Self-Hosted Notetakers (anarlog)](https://anarlog.so/blog/selfhosted-ai-notetakers/) ｜
[AR 字幕眼镜五连评 (Hearing Tracker)](https://www.hearingtracker.com/hearing-glasses/hear-with-your-eyes-five-ar-live-captioning-glasses)

**医疗合规类**（同意框架/诉讼风险）：
[The Lancet: consent gap](https://www.thelancet.com/journals/landig/article/PIIS2589-7500(26)00078-6/fulltext) ｜
[两党同意州 × AI scribe 指南](https://www.scribing.io/blog/one-party-vs-two-party-consent-states-ai-scribing) ｜
[ABA: ambient scribes 与隐私法张力](https://www.americanbar.org/groups/health_law/news/2026/ambient-ai-scribes-privacy-cybersecurity/) ｜
[Penn Medicine 患者 FAQ（正面样本）](https://www.pennmedicine.org/patient-resources/information-for-patients/ambient-documentation-faqs) ｜
[环境文档厂商全景 (getlimeai)](https://getlimeai.com/ambient-clinical-documentation-companies/) ｜
[Suki vs DAX vs Abridge vs Freed](https://intuitionlabs.ai/articles/suki-vs-nuance-dax-vs-abridge-vs-freed)

**事件与趋势类**（叙事/风险案例）：
[Apple Watch S12 音频智能中文深度分析](https://www.iphoneplay.cn/2026/09/10/apple-watch-series-12-audio-intelligence-health/) ｜
[Apple 官方支持文档 148354](https://support.apple.com/en-us/148354) ｜
[IFA 2026 可穿戴 AI 综述](https://dymesty.com/blogs/articles/ifa-2026-wearable-ai) ｜
[Gong 局限性 2026](https://www.oliv.ai/blog/gong-limitations-challenges) ｜
[screenpipe 开源屏幕录制博文](https://screenpipe.com/blog/open-source-ai-screen-recorder)

---

## 6. 对 laos 的落地增量计划（写作计划格式）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把本篇调研的三条增量（Apple 三段式 journal schema、mic 能力时间窗、业界对照写入 README）落进 laos 代码与文档。

**Architecture:** 全部改动走 laos 既有模式：journal schema 扩展走 MemoryStore 兼容字段（老记录缺字段自动降级）；时间窗走 task_scope 新前缀 `time:`，与 `pkg:` 同级解析；README 增补"业界对照"小节引用本调研。

**Tech Stack:** 纯 Python 标准库（零依赖约束不变），253 项既有测试为回归底线。

**Spec:** 本文（§2/§3/§4）即规格说明。

### Global Constraints

- 零第三方依赖（标准库 only）
- 隐私红线不动：录音必须显式 syscall 触发、`LAOS_REC=0` 全局禁录、每次调用审计 `event:"mic"`
- 新增字段必须向后兼容（旧 memory.jsonl 无新字段时可读）
- 全量测试基线：253 项，改动后必须全绿且只增不减

---

### Task 1: journal 记忆条目升级为 Apple 式三段 schema（title 字段）

**Files:**
- Modify: `bin/journal.py`（run_pipeline 中 remember 调用）
- Modify: `bin/diary.py`（"五、今天听到的"渲染消费 title）
- Test: `tests/test_journal.py`、`tests/test_diary.py`

**Interfaces:**
- Consumes: `MemoryStore.remember(kind, text, tags)`（现有签名不变）；`bin/diary.py` 中"五、今天听到的"章节的渲染代码（以实际函数名为准）
- Produces: journal 条目 text 首行变为 `# <标题>`；"今天听到的"章节优先显示标题行；`mood_report` 不受影响

- [ ] **Step 1: 写失败测试**——`tests/test_journal.py` 增加：转写文本 ≥2 句时，remember 的 text 首行为 `# ` 开头的短标题（≤20 字，取首句前 20 字符）；`tests/test_diary.py` 增加："今天听到的"章节渲染包含该标题行
- [ ] **Step 2: 运行确认失败**：`python -m unittest tests.test_journal tests.test_diary -v` → 新断言 FAIL
- [ ] **Step 3: 实现**——`journal.py` 中 `run_pipeline` 生成 `title = text.split("。")[0][:20]`，`mem.remember(kind="journal", text=f"# {title}\n{text}", tags=[emotion])`；`diary.py` 渲染时 `lines.append(entry["text"].splitlines()[0].lstrip("# "))`
- [ ] **Step 4: 全量测试通过**：`python -m unittest discover -s tests` → 253+ 全绿
- [ ] **Step 5: Commit**：`feat(journal): Apple-style title+summary schema for audio memories`

### Task 2: mic.* 能力时间窗（task_scope 新前缀 `time:`）

**Files:**
- Modify: `laos/kernel.py`（task_scope 解析处，`pkg:` 同级增加 `time:` 分支）
- Test: `tests/test_scope.py`

**Interfaces:**
- Consumes: PCB.task_scope（list[str]）；现有 `pkg:` 前缀解析代码位置
- Produces: `time:HH:MM-HH:MM` 前缀——超出时间窗的 `mic.*` 调用返回 `EACCES: outside task scope (time window)`；无 `time:` 前缀时行为完全不变

- [ ] **Step 1: 写失败测试**——spawn 带 `task_scope=["time:09:00-18:00"]` 的 agent：窗口内 `mic.status` 放行、窗口外返回 EACCES 且审计 `reason` 含 `time window`（用注入时钟或 monkeypatch `kernel._now_hhmm`）
- [ ] **Step 2: 运行确认失败**：`python -m unittest tests.test_scope -v` → FAIL
- [ ] **Step 3: 实现**——kernel.py task_scope 门新增 `time:` 分支：解析 `HH:MM-HH:MM` 与 `_now_hhmm()` 比较（跨零点区间按 `start<=now or now<=end`）；仅约束 `mic.*` 前缀调用，其余 syscall 不受影响
- [ ] **Step 4: 全量测试通过**
- [ ] **Step 5: Commit**：`feat(kernel): time: window scope for mic syscalls (Apple Siri-Recap-style scheduling)`

### Task 3: README 增补"业界对照"一节（引用本调研）

**Files:**
- Modify: `README.md`（第六节"重点能力"末尾）
- Create: 无（链接到本文）

**Interfaces:** 无代码接口，纯文档。

- [ ] **Step 1:** README 第六节末尾追加小节"业界对照"：三行结论（云常开已死/Apple S12 端侧克制常开逐项同构/laos 差异化=零云+能力管控+旁观者可见），附 `[完整调研](docs/research/always-on-recording/2026-09-11-verticals-apple-articles.md)` 链接
- [ ] **Step 2: Commit**：`docs(readme): industry benchmark section (Apple S12 audio intelligence, B2B verticals)`

---

## 7. 参考来源

全部链接已内嵌正文各表；本篇新增核验的核心官方源：
[Apple 支持文档（Audio Intelligence 隐私与 7 天删除）](https://support.apple.com/en-us/148354) ｜
[Abridge × Epic 新闻稿](https://www.abridge.com/press-release/abridge-becomes-epics-first-pal-bringing-generative-ai-to-more-providers-and-patients) ｜
[Microsoft Dragon Copilot](https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot) ｜
[Suki 融资公告](https://www.suki.ai/press-releases/suki-announces-investment-from-zoom-ventures/) ｜
[Gong 官网](https://www.gong.io/) ｜
[XRAI Glass 2.0](https://xrai.glass/blog/2nd-edition-launches-globally/) ｜
[Vexa GitHub](https://github.com/vexa-ai/vexa) ｜
[Meetily 官网](https://meetily.ai/) ｜
[Rokid 官网](https://www.rokid.com/) ｜
[Ola Friend 报道（Yicai）](https://www.yicaiglobal.com/news/tiktok-owner-bytedance-launches-usd169-ai-earbuds-in-china)
