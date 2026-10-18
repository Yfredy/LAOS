# writing-plans 技能学习：计划工程学与 Skill 工作流（2026-10-18）

> 学习对象：`~/.workbuddy/skills/writing-plans/SKILL.md`（7,053 B）+ 配套
> `plan-document-reviewer-prompt.md`（1,713 B）；配套技能 `executing-plans` /
> `subagent-driven-development` / `finishing-a-development-branch`。
> 关联来源：微信公众号「AI前沿速递」《WorkBuddy + 综述Skill，20分钟写出一篇投稿级综述》
> （2026-10-18）——该文已于同日沉淀为 `docs/research/2026-10-18-litreview-skill-workflow.md`，
> **本文不重复其综述 SOP，只取它与 writing-plans 的同构部分**（§7）。
> 记法：✅ 技能明文 ｜ 🔶 本仓既有约定 ｜ ⚠️ 本文独立判断。

---

## 1. 一句话论点

**计划不是记录，是"写给零上下文执行者的可执行契约"。** writing-plans 的每一条苛刻要求
（无占位符、2–5 分钟一步、跨 Task 签名逐字一致）都不是文档洁癖，而是对冲同一个风险：
**执行者（人或子代理）不看你的脑子，只看纸面**。纸面缺一寸，执行就偏一尺。

⚠️ 而 Skill 本身——无论是 writing-plans 还是 LitReview——是同一范式的另一半：
**把流程、交付物定义与禁止事项在动手前写死，让模型无法用更便宜的产物交差。**
文章里那句「不能只给一份目录或几张表格就算完成」，和 writing-plans 的
「TBD / 加适当错误处理 = 计划失败」，是同一条规则在两个领域的投影。

---

## 2. 技能原文拆解（十条硬要求）

| # | 条文（✅ 明文） | 一句话意图 |
|---|---|---|
| 1 | Overview：假设工程师对代码库**零上下文**、且判断力可疑；DRY/YAGNI/TDD/频繁提交 | 计划的读者是"聪明的陌生人"，不是未来的自己 |
| 2 | Scope Check：spec 覆盖多个独立子系统 → **拆成多个计划**，每个都能独立产出可测试软件 | 一份计划只解决一个可验收的切面 |
| 3 | File Structure：先定文件与职责，再定 Task；小文件优先；一起改的文件放一起；按职责而非技术层切分 | 分解决策在写代码前锁定 |
| 4 | Task Right-Sizing：Task = 携带自己测试周期、值得单独过评审门的**最小单元**；setup/配置/脚手架/文档折进需要它的 Task | 切分点是"评审者可能否决这个而批准相邻那个" |
| 5 | Bite-Sized：每步 2–5 分钟、一个动作（写失败测试 / 跑它确认红 / 最小实现 / 跑绿 / 提交） | 粒度小到不可能走神 |
| 6 | Plan Header：Goal / Architecture / Tech Stack / **Spec（路径）** + Global Constraints + 执行子技能声明 | spec 随计划同行，计划从 spec 立论 |
| 7 | Task Structure：Files（Create/Modify `path:123-145`/Test）+ **Interfaces（Consumes / Produces 精确签名）** + checkbox 步骤（代码块必给） | 执行者只见自己那一段，靠 Interfaces 学邻段名字 |
| 8 | No Placeholders：禁 TBD/「加适当错误处理」/「为上述写测试」/「类似 Task N」/ 无代码块的描述性步骤 | 占位符 = 计划失败，不是待办 |
| 9 | Self-Review（自查非派发）：① spec 覆盖 ② 占位符扫描 ③ 类型一致性 | 三查是发布闸门 |
| 10 | Execution Handoff：保存后给用户二选一（Subagent-Driven 推荐 / Inline Execution），各自绑定 REQUIRED SUB-SKILL | 计划写完不是终点，交接才是 |

配套 `plan-document-reviewer-prompt.md` 给出**派发式评审**的四个维度
（Completeness / Spec Alignment / Task Decomposition / Buildability）与一条校准线：
**只在"会导致实现期真问题"时才提 issue，否则放行**——避免评审员用文风偏好阻塞交付。

---

## 3. 设计意图：每条在防哪个失效模式

| 失效模式 | 症状 | 被哪条挡住 |
|---|---|---|
| **F1 上下文缺失** | 执行者不知道仓库约定，凭直觉写 | #1 零上下文假设 + #6 Global Constraints 逐字照抄数值 |
| **F2 占位符糊弄** | "处理边界情况"→ 实现时随手糊 | #8 明令 + #9 ② 扫描 |
| **F3 类型漂移** | Task 3 叫 `clearLayers()`，Task 7 变 `clearFullLayers()` | #7 Produces 块 + #9 ③ 一致性 |
| **F4 乱序阅读** | 子代理并行只看到自己那一段 | #7 Interfaces + 🔶 本仓"原文重复，禁参见" |
| **F5 一步太大** | 一次改三个文件，红绿分不清 | #5 2–5 分钟一步 |
| **F6 交付降级** | 拿目录/表格冒充成品 | #6 Spec + 🔶 交付物清单（LitReview 同构） |
| **F7 计划与 spec 脱节** | 计划自己发明需求 | #6 Spec 字段 + #9 ① 覆盖检查 |
| **F8 无粒度提交** | 一堆改动一个 commit，回滚困难 | #5 每 Task 一 commit + 🔶 落点可用 `git log` 证明 |

**本仓实证（2026-10-18，brain 可靠性波）**：即使严格按体例写的计划，实现期仍抓到三个坑——
① 断言漏记收尾 done 轮的 temperature（测试 double 每次 think 都记账，断言要算全序列）；
② `repeat_counts` 初始化写在步循环内 → 按步清零、跨步永远到不了阈值 3（**计数器生命周期必须与语义辖域一致**）；
③ abstract 签名一变（think 加参），全仓 `def think(` 的旧签名 test double 秒崩 TypeError。
⚠️ 教训：**计划自身的测试代码也会错；裁决原则是以 Produces 语义 + 测试意图为准，偏差写进 commit body。**

---

## 4. 与 laos 既有纪律的对照（增量在哪里）

本仓 `docs/superpowers/plans/README.md` 已于 2026-10-09 把该技能内化为三条增量纪律。对照如下：

| 维度 | writing-plans 原文 | laos 增量（🔶） | 为什么加 |
|---|---|---|---|
| 三查 | #9 自查三项 | 同三项，但明确**保存前必跑、不派发子代理** | 派发会把"写计划"变成"等评审"，拖慢节奏 |
| Task 尺寸 | #4 自带测试周期的最小单元 | 追加：步骤 2–5 分钟，但 **Task 不是步骤的机械聚合** | 防止把 40 步拆成 40 个 Task |
| 跨 Task 引用 | #7 Interfaces | 追加硬禁令：**禁"类似 Task N"，代码块照抄** | zones/ 并行执行是常态，执行者乱序读 |
| 完成度判据 | checkbox 勾选 | **checkbox 执行时不勾选**；判据 = 交付物在 `git log --all -- <path>` 可证 + 验收清单 | 勾选是自证，git 历史是他证 |
| 状态登记 | 无 | `plans/README.md` 状态表三值（已执行/部分执行/待执行）+ 落点摘要 | 50 份计划需要单一状态入口 |
| 数值纪律 | #6 Global Constraints 逐字照抄 | 追加：分档**左闭右开**、数字写实跑值 | 跨文档引用同一阈值时口径必须唯一 |

⚠️ 结论：**writing-plans 管"计划怎么写"，本仓纪律管"计划怎么被证伪"。** 后者是补上了原技能的空白——
原技能假设执行完就结束，本仓要求三个月后还能用 git 证明做过什么。

---

## 5. 端到端工作流（想法 → 落地）

| 阶段 | 技能 | 输入 | 产出 | 关键动作 |
|---|---|---|---|---|
| P0 理清需求 | `brainstorming` | 模糊想法 | 设计 spec | 多方案取舍写进 spec，不写进计划 |
| P1 隔离工作区 | `using-git-worktrees` | spec | 独立 worktree | 不在 master 上直接实施 |
| P2 写计划 | **writing-plans** | spec | `docs/superpowers/plans/YYYY-MM-DD-<name>.md` | 四段头 + Global Constraints + File Structure + Task×N |
| P3 三查 | （自查） | 计划 + spec | 修正后的计划 | 覆盖 / 占位符 / 类型一致性 |
| P4 执行 | `subagent-driven-development`（推荐）或 `executing-plans` | 计划 | 代码 + 测试 + 逐 Task commit | 每 Task 一子代理 + 两阶段评审；阻塞即停，不猜 |
| P5 可选评审 | `plan-document-reviewer-prompt` | 计划 + spec | Approved / Issues | 只在会导致实现期真问题时提 issue |
| P6 收尾 | `finishing-a-development-branch` | 全绿分支 | 合并/PR | 验证测试、给选项、执行选择 |
| P7 发版 | 🔶 `scripts/release.py --apply` | 主库绿 | 版本/文档锚点同步 + tag + Release | 测试不绿直接拒发版（本仓最高优先级） |

**本仓实例（2026-10-18 当天跑通）**：`2026-10-18-audio-agentos-litreview-survey.md`——
Spec 指向 `2026-10-18-litreview-skill-workflow.md`；Global Constraints 11 条逐字锁定数值
（规模分档 `[0,30M)/[30M,500M)/[500M,+∞)` 左闭右开、AudioSet 必须标 `AS-20K/AS-2M/full`、
证据等级四值 `全文/表格核实/摘要/二手`、`--strict` 参考文献 ≥60 篇）；9 个 Task，
Task 1 的 Produces 直接给出 `run_checks(survey_path, survey_text, evidence_path, evidence_text, strict=False) -> list[Violation]`
与 36 个规则名，后续 Task 全部按规则名与退出码验收。⚠️ 这是"跨 Task 靠 Produces 学名字"的标准样本。

---

## 6. 可复用计划骨架（本仓体例，可直接抄）

````markdown
# <功能名> Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一句话说明构建什么
**Architecture:** 2–3 句说明路径与取舍
**Tech Stack:** 关键技术/库（含版本与依赖边界）
**Spec:** `<spec 路径>` —— 计划从 spec 立论，执行者两份都读

## Global Constraints
- 每条一行，数值**逐字照抄 spec**，正文不得改写
- 依赖红线 / 目录纪律 / 既有校验器必须常绿 / 发版锚点不动 …（本仓特有）

## File Structure
| 路径 | 职责 |（新增文件在此登记，临时物只进 var/）

### Task N: <组件名>
**Files:** Create / Modify `path:行号` / Test
**Interfaces:**
- Consumes: 前序 Task 提供的精确签名
- Produces: 后续 Task 依赖的精确签名与返回类型（逐字符一致）
- [ ] Step 1: 写失败测试（**给完整测试代码**）
- [ ] Step 2: 跑，确认红（给命令 + 期望报错原文）
- [ ] Step 3: 最小实现（给代码，禁止占位符）
- [ ] Step 4: 跑，确认绿
- [ ] Step 5: commit（给 `git add` 与 commit message）
````

**写完必跑（保存前，非派发）**：spec 覆盖 → 占位符扫描 → 类型一致性。
**写完必登记**：`docs/superpowers/plans/README.md` 状态表加一行（落点摘要 + 状态）。

---

## 7. Skill 工程学：writing-plans 与 LitReview 的五处同构

文章把 Skill 定义为「一份给 AI 的任务说明」。把两个技能放在一起看，**有效的 Skill 都有同样的五要素**：

| 要素 | writing-plans | lit-review（据文章） | 作用 |
|---|---|---|---|
| ① 触发条件 | "有 spec、写代码前" | "要写综述时" | 防止在不该用的时候被调用 |
| ② 流程前置规定 | 四段头 → File Structure → Task 分解 → 步骤 | 定范围 → 查筛读 → 比较 → 成文 | **不允许模型自己发明顺序** |
| ③ 交付物定义 | 完整计划（含代码块的步骤） | 完整综述 + 参考文献 | 定义质量下限 |
| ④ 反降级硬边界 | 禁 TBD / 禁"适当处理" / 禁"类似 Task N" | 禁只给目录或表格 | 堵住最便宜的交差方式 |
| ⑤ 自审与门禁 | Self-Review 三查 | 未核实内容必须标注 | 让模型自己先过一遍 |

⚠️ 推论（可用于以后写任何 Skill）：**流程与交付物定义决定上限，反降级边界决定下限。**
只写流程不写禁止事项的 Skill，模型会用最小代价满足流程——那正是文章里"目录 + 几张表格"的结局。

---

## 8. 计划写作验收清单（写完逐项勾）

**写之前**
- [ ] 有 spec 且路径写进了 Header；spec 覆盖多个独立子系统 → 已拆成多份计划
- [ ] worktree/隔离区已就绪（不在 master 上实施）

**写之中**
- [ ] File Structure 先于 Task 定稿；一起改的文件放一起
- [ ] 每个 Task 自带测试周期；setup/文档已折进需要它的 Task
- [ ] 每步 2–5 分钟、一个动作、代码块完整（测试步骤必给测试代码）
- [ ] Global Constraints 数值逐字照抄 spec（含左闭右开这类边界写法）
- [ ] Interfaces 的 Produces 与后续 Task 的 Consumes 逐字符一致

**写之后（三查 + 登记 + 交付）**
- [ ] spec 每个需求都能指到某个 Task
- [ ] 全文无 TBD / "加适当错误处理" / "为上述写测试" / "类似 Task N"
- [ ] 跨 Task 的函数名、参数、字段名、规则名无漂移
- [ ] 已登记进 `plans/README.md` 状态表
- [ ] 已向用户给出执行方式二选一并绑定子技能
- [ ] 每 Task 一 commit，落点可用 `git log --oneline --all -- <path>` 证明
- [ ] checkbox 保持未勾选（完成度看 git，不看勾）

---

## 9. 边界与诚实声明

- **适用边界**：writing-plans 面向**代码实施**。调研/综述类任务沿用其骨架时，必须额外加
  「证据等级」与「来源诚实」两栏（本仓做法：核验层级四值 + 未核实清单隔离，见综述计划），
  否则计划会产出"看起来完整、实际无法溯源"的产物。
- **不声称**：本文未对 writing-plans 做任何修改，也未生成新计划；§6 骨架是本仓体例的复述，不是新规。
- **引用边界**：微信文章的经验已完整沉淀在 `2026-10-18-litreview-skill-workflow.md`，本文只在 §7 取其与
  计划技能的同构关系，不重复其 S0–S8 SOP 与验收清单。
- **待用户裁决项**：`plan-document-reviewer-prompt` 的派发式评审在本仓从未使用（一直用自查三查）。
  是否在 20+ Task 的大计划上启用一次，属于流程选择题，本文不代为决定。
