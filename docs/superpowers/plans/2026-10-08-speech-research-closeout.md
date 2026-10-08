# 语音三域调研收尾（SER / AED / AGC）实施计划

> **生成于 4332b1c 时刻快照**：文中"主库 980 项测试"等基线数字系当时实跑（v0.28.1）；v0.29.0（laosweb v3 波）后主库计数已变，执行时以实跑为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把三条停在 Task 1（只定了口径）的语音域调研线收尾 —— **SER**（Task 2–7 已完成，只剩落地 Task 8）、**AED**（完成 1/8，剩 Task 2–8）、**AGC**（完成 1/9，剩 Task 2–9）—— 交付三份 landscape + HTML 全景 + 三份落地篇，并让跨仓库 `AlwaysOnRec-HY4` 的采纳结论落到真实代码分支或"明确不引入"的书面论证。

**Architecture:** 调研型计划，不是代码型计划。每条线沿用已定稿的骨架：`00` 口径 → 分档文件 → 两个跨切轴（端侧 / 多模态）→ landscape 收敛 → 落地。"测试"不是 pytest，而是三个机器校验器（`check_ser_table.py` / `check_aed_table.py` / `check_agc_table.py`），以及跨仓库 HY4 的 147 项 unittest。三条线互不依赖，可并行；唯一的共同前置是 Task 0（HY4 测试门禁）。

**Tech Stack:** Python 3 stdlib（校验器与语料 CLI）、WebSearch / WebFetch、arXiv API、`docs/` 下零依赖单文件深色 HTML。

**Spec:** 本计划是**收尾计划**，逐 Task 的内容规格来自下列三份源计划（执行者必须同时读本文件与对应源计划的任务段落，本文件给出序号映射与收尾期新增约束）：
- `docs/superpowers/plans/2026-09-11-speech-emotion-models.md` → 本计划 Task 1 = 其 Task 8（L320-372）
- `docs/superpowers/plans/2026-09-11-audio-event-models.md` → 本计划 Task 2–8 = 其 Task 2–8（L181-490）
- `docs/superpowers/plans/2026-09-11-auto-gain-models.md` → 本计划 Task 9–16 = 其 Task 2–9（L167-512）
- 现状基线：`docs/design/2026-10-08-architecture-current-state.md`（主库 980 测试、conda 解释器、目录纪律）

---

## Global Constraints

1. **解释器锁死 `C:/Users/yaoyue/miniconda3/python.exe`（3.12.4）。** 一切 python 命令用该绝对路径。主库 `laos/` 若误用 3.11.9 会因 PEP 701 f-string 直接崩（`bin/laosd.py:395`）。
2. **跨仓库路径固定为 `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4`。** 任何落地类 Task 在动手前与收尾时都必须跑 `python -m unittest discover -s tests -t .`，**147 项全绿**才算完成。
3. **校验器的"静默跳过"是真实风险，必须显式核对。** `scripts/table_lint.py`（L17/30/44/110）只认**首列为"模型"**的表格，首列不同的表会被静默跳过、报 0 违规。因此每次跑校验器时，必须核对它打印的**表数与记录数**与文件里实际表格数一致；不一致等于没校验。
4. **每条记录必须可核验。** `来源` 列必须有 arXiv ID / HF repo / GitHub / 官方文档链接之一；查不到就**删除该条**，不留 `待补` / `TBD`（校验器会拦）。
5. **不改动 `scripts/check_ser_table.py`；不改动 `laos/` 主代码。** 本计划是调研线，主库 980 项测试必须全程保持全绿（若某 Task 需要动主库，先停下来向用户确认）。
6. **既有速览版不删除。** `docs/research/2026-09-11-aed-agc-model-landscape.md` 保留为素材，只在头部加一行指向新目录的指针。
7. **检索优先用本地语料再补网络。** 起点命令：`python scripts/query_corpus.py --topic audio-speech --strong-only --limit 200`（实测 771 条强命中）；命中的标题必须回溯原文核实数字，不得照抄语料摘要。
8. **指标不许写裸数字。** 必须带基准名与任务类型，如 `mAP 0.502 (AudioSet AS-2M full, tagging)`；跨任务类型（mAP ≠ PSDS ≠ 准确率）与跨数据规模（AS-20K ≠ AS-2M full）**不得直接比较**，必须比时正文明说"不可直接比较"。
9. **HTML 全景零第三方依赖**：单文件、深色、内联 SVG/JS/CSS，不引 CDN。
10. **每个 Task 一个 commit**（laos 仓库），跨仓库改动单独一个 commit。
11. **落地点不得凭空命名**：必须读完 HY4 对应代码后，由调研结论决定改哪个文件、新增哪个通道名。

---

### Task 0: 前置门禁 —— HY4 147 项回到全绿

**Files:**
- Test: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\tests\test_rec.py:167`
- Modify（二选一，由 Step 2 判定决定）: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\aor\drivers\rec.py`（L44/77/174-240/286）或 `tests\test_rec.py`

**Interfaces:**
- Consumes: HY4 现有 `rec.status` 输出、模块级全局 `_encoding`。
- Produces: 147 全绿的 HY4，供 Task 1 / 8 / 16 的落地步骤使用。

- [ ] **Step 1: 复现失败**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .`
Expected: `Ran 147 tests` + `FAIL: test_status_reports_encoding_and_quota`，断言 `encoding=wav` 未命中，实际串为 `... encoding=opus evicted=0 ttl_hours=6.0 quota_bytes=268435456 quota_segments=10000`。

- [ ] **Step 2: 判因（必须读完代码再动）**

读 `aor/drivers/rec.py` 的 L44（`_encoding = "auto"`）、L63/77（`global` 声明与重置点）、L174-177（`_effective_encoding()`）、L222-240（`rec_start` 的赋值分支）、L286（status 打印）。判定下列三种情形之一并写进 commit message：
- **A 测试污染**：`_encoding` 是模块级全局，前一个用例以 `opus` 结束后未复位 → 修测试（用例首尾显式复位）；
- **B 默认值语义变更**：`auto` 解析优先 opus 且 `rec_start` 的显式 `wav` 未落到全局 → 修代码（显式值必须覆盖 auto 解析）；
- **C 断言过期**：编码策略已改为默认 opus（对应"留存档"能力），断言应改为 `encoding=opus` → 修测试并在注释里写明变更来源。

- [ ] **Step 3: 修复并复跑**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .`
Expected: `Ran 147 tests ... OK`。

- [ ] **Step 4: Commit（HY4 仓库）**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add aor/drivers/rec.py tests/test_rec.py
git commit -m "fix(rec): status encoding assertion — <A|B|C 判定一句话>"
```

---

### Task 1: SER 落地 —— 06-adoption.md + HY4 ear 通道

**Files:**
- Create: `docs/research/speech-emotion/06-adoption.md`
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\aor\drivers\ear.py`（新增通道分支）
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\README.md`（补选型理由）
- Test: HY4 `python -m unittest discover -s tests -t .`（147 全绿）

**Interfaces:**
- Consumes: `docs/research/speech-emotion/2026-09-landscape.md`（Task 7 已产出的选型结论）、`AOR_ASR_CHANNEL`（`stub`/`funasr`/`server`，定义于 `aor/drivers/ear.py` 的 `channel()`）、`classify_mood(dbfs, dur_ms)`。
- Produces: 一条新的情绪通道，或一份"暂不引入"的论证（二者必居其一）。

- [ ] **Step 1: 先读 HY4 的 ear 通道现状**

读 `aor/drivers/ear.py`，确认三件事并写入 `06-adoption.md`：（a）`channel()` 的三值分支与 `DEFAULT_CHANNEL` 取值来源；（b）`classify_mood(dbfs, dur_ms)` 的输入从哪来、`emotions` 字段当前由谁填；（c）新增通道是**替换** `classify_mood` 还是**补充** `emotions` 字段来源（推荐后者，理由写进文档：粗粒度唤醒度零成本且已有测试覆盖）。

- [ ] **Step 2: 写落地建议**

`06-adoption.md` 必须回答：
1. proot Ubuntu 现状下哪几款模型**当下真能跑**（给出名字与环境要求，依据 `04-edge-deployment.md` 的 A/B 档结论）；
2. 新通道与 `classify_mood()` 的职责边界；
3. **不做什么**三条，逐条给理由：不引入说话人识别（声纹红线）· 不输出临床结论 · 多模态的**视觉模态不进 HY4**（隐私成本，见 `05-multimodal.md`）。

- [ ] **Step 3: 改 ear.py 加分支（条件执行）**

若结论为引入，在 `channel()` 三值之外新增分支（名字由 Step 1–2 的结论决定），保持惰性导入与缺依赖静默降级到 `stub` 的既有行为：

```python
def channel() -> str:
    return os.environ.get("AOR_ASR_CHANNEL") or os.environ.get("LAOS_ASR_CHANNEL") \
        or DEFAULT_CHANNEL
```

若结论为"暂不引入"，**不改代码**，只在 `06-adoption.md` 写明触发条件。

- [ ] **Step 4: 跑 HY4 全量测试**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .`
Expected: `Ran 147 tests ... OK`。

- [ ] **Step 5: Commit（两个仓库）**

```bash
git add docs/research/speech-emotion/06-adoption.md
git commit -m "docs(speech-emotion): adoption plan for AlwaysOnRec-HY4 ear channel"

cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add aor/drivers/ear.py README.md
git commit -m "feat(ear): <channel-name> emotion channel behind AOR_ASR_CHANNEL"
```

---

### Task 2: AED 小型模型（< 30M）

**Files:**
- Create: `docs/research/audio-events/01-small-models.md`
- Test: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py docs/research/audio-events/01-small-models.md`

**Interfaces:**
- Consumes: `docs/research/audio-events/00-taxonomy-and-metrics.md` 的 12 列 schema 与任务类型映射表。
- Produces: 小型档表格，供 Task 6（端侧）与 Task 8（收敛）读取。

- [ ] **Step 1: 检索**

起点：`python scripts/query_corpus.py --topic audio-speech --strong-only --grep "scene|event|tagging|DCASE" --limit 200`。补检索：`low-complexity acoustic scene classification`、`DCASE2025 task1`、`tiny audio event detection MCU`、`sub-100k parameter audio tagging`、`MMACs audio tagging`。

- [ ] **Step 2: 建表（不少于 12 条）**

每条必须含：参数量、**MMACs 或等效计算量**（有则必填）、任务类型、基准（AudioSet 必须标 AS-20K / AS-2M full）、指标、许可、来源链接。DCASE Low-Complexity ASC 系列**必须收录**——它是唯一带硬约束（128K 参数 / 30 MMACs）的公开赛道，是端侧档的事实标准。

- [ ] **Step 3: 写"128K 参数约束下能做什么"小节**

必须回答：该约束下 ASC 准确率逐年变化；约束内模型能否迁移到 tagging/SED（ASC 独占单类 vs tagging 多标签，不能直接套）；**参数量与 MMACs 哪个才是真瓶颈**（引用或自推，推导要写明假设）。

- [ ] **Step 4: 跑校验器（并按 Global Constraint 3 核对表数）**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py docs/research/audio-events/01-small-models.md`
Expected: 0 违规，且打印的记录数 ≥ 12；查不到来源的条目删掉重跑。

- [ ] **Step 5: Commit**

```bash
git add docs/research/audio-events/01-small-models.md
git commit -m "docs(audio-events): small AED models under the 128K/30-MMACs constraint"
```

---

### Task 3: AED 中型模型（30M–500M）

**Files:**
- Create: `docs/research/audio-events/02-medium-models.md`
- Test: `scripts/check_aed_table.py docs/research/audio-events/02-medium-models.md`

**Interfaces:**
- Consumes: `00` schema 与校验器。
- Produces: 中型档表格，供 Task 6 / 8 引用。

- [ ] **Step 1: 检索**

补检索：`AudioSet AS-2M full mAP state of the art`、`audio tagging transformer benchmark`、`BEATs CED SSLAM comparison`、`PANNs vs AST vs PaSST mAP`。待核实起点线索（**每条都要找到原始出处，找不到就删**）：SSLAM 88M ≈ 50.2 mAP、CED 86M ≈ 50.0 mAP、SPEARs+a XLarge ≈ 50.0 mAP、BEATs iter3+ ≈ 48.6 mAP。

- [ ] **Step 2: 建表（不少于 12 条）**

必须区分 AS-20K 与 AS-2M full；同一模型两处都有报告时主表记 full、20K 值进备注。

- [ ] **Step 3: 写"中型档是 AED 的精度甜点"小节**

给出中型档在 AS-2M full 上的 mAP 区间，与 Task 2 小型档做**同基准同任务**对比（如 YAMNet 0.306 vs 0.45–0.50，均须核实），并说明代价（参数量/MMACs 涨多少、能否实时）。

- [ ] **Step 4: 跑校验器 + Step 5: Commit**

```bash
git add docs/research/audio-events/02-medium-models.md
git commit -m "docs(audio-events): medium AED models on AudioSet AS-2M full"
```

---

### Task 4: AED 大型模型（> 500M，含音频大模型路线）

**Files:**
- Create: `docs/research/audio-events/03-large-models.md`
- Test: `scripts/check_aed_table.py docs/research/audio-events/03-large-models.md`

**Interfaces:**
- Consumes: `00` schema 与开放词表裁定。
- Produces: 大型档表格，供 Task 7（多模态）与 Task 8 引用。

- [ ] **Step 1: 检索**

补检索：`audio LLM audio tagging benchmark`、`audio language model vs specialized audio encoder`、`open-vocabulary sound event detection LLM`、`zero-shot SED CLAP DESED PSDS`、`DASM open-vocabulary SED`。

- [ ] **Step 2: 建表（不少于 10 条）**

`版本/权重` 列必须区分三种结构：编码器+标签头（纯判别）· 端到端音频大模型（音频编码器直连 LLM）· 两段式（ASR/caption + LLM 判定）。API-only 商业模型 `许可` 列写 `proprietary API`。

- [ ] **Step 3: 写"大型档在 AED 上换了什么"小节（本 Task 的判定点）**

必须给出结论并附数字/引用：（a）大型档的真正增量是不是**开放词表**——DESED 零样本 PSDS1 相对监督 CRNN 是多少（初始线索 ≈0.422，须核实），并写明是"audio LLM 不做 tagging"还是"做了但做不好"（两者架构含义完全不同）；（b）7B 级模型处理 10 秒音频的耗时/显存量级；（c）**失败模式**——开放词表模型对"不在提示集里的真实事件"是静默漏检还是误报（直接决定它能否做常驻检测）。

- [ ] **Step 4: 跑校验器 + Step 5: Commit**

```bash
git add docs/research/audio-events/03-large-models.md
git commit -m "docs(audio-events): large AED models and the open-vocabulary tradeoff"
```

---

### Task 5: AED 跨切轴一 —— 端侧部署

**Files:**
- Create: `docs/research/audio-events/05-edge-deployment.md`
- Modify: `docs/research/audio-events/01-small-models.md`、`02-medium-models.md`（回填 `edge` 列）

**Interfaces:**
- Consumes: Task 2/3 表格、`docs/research/speech-emotion/04-edge-deployment.md` 的功耗阶梯（**引用，不重算**）、`docs/research/qnn-real-device-runbook.md`。
- Produces: 端侧可行性结论，供 Task 8/9 使用。

- [ ] **Step 1: 检索 runtime 与量化证据**

覆盖 TFLite / TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、**QNN**。重点核实：DCASE Low-Complexity 获奖系统是否有公开的量化/部署产物（多数只有 PyTorch 权重——这是端侧档的真实缺口）。

- [ ] **Step 2: 写端侧预算表**

RTF（常驻检测要求流式 ≤ 0.1）、峰值内存、模型体积、功耗 mW、MMACs/秒；**功耗数字直接引用 SER 04 与 `docs/research/always-on-recording/` 的量级阶梯**，不另起一套。

- [ ] **Step 3: 写"proot 现状"（本 Task 的判定点）**

沿用 A/B 两档：A 档·真端侧（原生 App / aDSP / Sensing Hub / 手机 NPU，mW 档）vs B 档·proot 内（CPU 推理，通用 Linux 空闲 400–1000 mW，拿不到 aDSP）。必须回答 **AED 专属问题**：常驻 AED 在 B 档是否可接受——持续 CPU 跑几 M 参数 tagging 模型的实测或估算功耗是多少，相对"常驻 VAD 能量门"增量多大。给不出实测就给估算并写明假设，**不许含糊带过**（直接决定 Task 9 落地结论）。

- [ ] **Step 4: 回填 edge 列**（`yes: <runtime+量化>` / `no` / `unknown(未找到公开转换案例)`，按 A/B 档标注）+ **Step 5: 跑校验器**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py docs/research/audio-events/01-small-models.md 02-medium-models.md`
Expected: 0 违规（`unknown(未找到公开转换案例)` 是合法值）。

- [ ] **Step 6: Commit**

```bash
git add docs/research/audio-events/05-edge-deployment.md 01-small-models.md 02-medium-models.md
git commit -m "docs(audio-events): edge deployment axis with proot reality check"
```

---

### Task 6: AED 跨切轴二 —— 多模态

**Files:**
- Create: `docs/research/audio-events/06-multimodal.md`
- Modify: `docs/research/audio-events/03-large-models.md`（回填 `模态` 列精确组合）

**Interfaces:**
- Consumes: Task 4 大型表、`00` 的开放词表裁定。
- Produces: 多模态结论，供 Task 8 交叉分析。

- [ ] **Step 1: 检索模态组合**

`A+V`（audio-visual event localization、VGGSound、LLP、AVE）、`A+T`（开放词表/检索式 SED，CLAP）、`A+T+V`。

- [ ] **Step 2: 建数据集表（不少于 8 条）**

每条含语言、模态组合、规模、标签粒度、**许可**；至少含 VGGSound、AVE、LLP、AudioSet（含视频模态但常用纯音频）、AudioCaps、Clotho、DESED、DCASE Task3（SELD）。

- [ ] **Step 3: 写"多模态换来了什么"小节**

必须回答且有可引用数字：（a）`A+V` 相对纯 `A` 在**事件定位**（不只是分类）上提升多少——定位才是视觉的真正增量；（b）`A+T` 开放词表在未见类别上的表现与代价；（c）**隐私代价**：视觉模态在中国法下的合规成本（个保法 §26 公共场所图像用途限制、§28–30 人脸属敏感个人信息需单独同意、国务院令 799 号 §17 视频保存 ≥30 日）与 laos「原音频即焚」架构**直接互斥**。
延续 SER 05 的立场（视觉不进 HY4），但在 AED 语境下**独立复核**（SER 用视觉看表情，AED 用视觉做定位），写出一致或推翻的理由。

- [ ] **Step 4: 跑校验器 + Step 5: Commit**

```bash
git add docs/research/audio-events/06-multimodal.md 03-large-models.md
git commit -m "docs(audio-events): multimodal axis — visual adds localization, not classification"
```

---

### Task 7: AED 收敛 —— landscape + 交叉表 + HTML 全景

**Files:**
- Create: `docs/research/audio-events/2026-09-landscape.md`
- Create: `docs/audio-event-models.html`

**Interfaces:**
- Consumes: Task 2–6 全部表格。
- Produces: 选型输入，供 Task 8 使用。

- [ ] **Step 1: 写交叉表**

核心是 **规模档 × {edge, multimodal}**，每格给：模型数量、代表模型、典型 mAP/PSDS 区间、典型 MMACs 与延迟。另补「任务类型 × 规模档」推荐表与「按场景推荐」表（常驻低功耗 / 近实时 / 事后批量）。

- [ ] **Step 2: 写"中文场景空白"一节（AED 特有，必须写）**

检索并记录：中文/中文环境音频事件数据集是否存在；若无，写明后果——AudioSet 本体来自英文 YouTube，中文家庭环境（电动车报警器、麻将、广场舞、燃气灶报警器等）分布不同，直接用会产生哪些具体失效；给出缓解手段（自采小样本微调 / 只做粗粒度事件 / 用开放词表绕过固定词表）。**不得用英文基准结论冒充中文可用性。**

- [ ] **Step 3: 写"常驻检测升级"决策**

直接回答：漏斗第一段从 VAD 能量门升级为事件级检测，收益（减少无效唤醒、事件级触发更准）、代价（常驻功耗、误触发、误报的隐私含义）、什么条件下值得做；给出明确的**做 / 不做 / 有条件做**与判定阈值。

- [ ] **Step 4: 写选型决策树**

输入部署约束（能否出端、有无 NPU、是否实时、能否联网、事件类别是否固定），输出推荐档位与具体模型；每步写清判据。

- [ ] **Step 5: 生成 HTML 全景**

`docs/audio-event-models.html`：深色单文件、零外部依赖、sticky 导航。至少含 3×2 交叉矩阵图、任务类型×指标映射图、三档参数量/MMACs 对比表、AudioSet AS-2M full 榜单、多模态数据集表、端侧 runtime 对比表。

- [ ] **Step 6: 跑全量校验器**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py docs/research/audio-events/*.md`
Expected: 0 违规，总记录数 ≥ 40。

- [ ] **Step 7: Commit**

```bash
git add docs/research/audio-events/2026-09-landscape.md docs/audio-event-models.html
git commit -m "docs(audio-events): landscape synthesis and HTML panorama"
```

---

### Task 8: AED 落地 —— 接回 AlwaysOnRec-HY4

**Files:**
- Create: `docs/research/audio-events/07-adoption.md`
- Modify: HY4 下由 Task 7 结论指定的文件（**不得凭空指定**；若结论为"暂不引入"则只改文档）
- Modify: `C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4\README.md`
- Test: HY4 `python -m unittest discover -s tests -t .`（147 全绿）

**Interfaces:**
- Consumes: Task 7 决策、Task 5 的 A/B 档结论、HY4 现有捕获链路代码。
- Produces: 一条 AED 通道，或一份"暂不引入"的论证。

- [ ] **Step 1: 先读 HY4 现状再动笔**

读 `aor/drivers/ear.py` 与捕获链路相关文件，确认并写入 `07-adoption.md`：（a）第一段常驻检测当前的实现位置与判据（VAD 能量门参数）；（b）AED 若接入是**替换**能量门还是**在其后作二次确认**（推荐后者，理由写进文中：能量门零成本，AED 只处理被能量门放过的可疑片段，功耗可降一个量级）；（c）`AOR_ASR_CHANNEL` 三值是否受影响，新增分支如何命名（由结论决定）。

- [ ] **Step 2: 写落地建议**

必须回答：1. 在 proot Ubuntu 现状下（B 档）哪几款模型**当下真能跑**，给出名字与环境要求；2. AED 输出与既有"粗粒度唤醒度"标签的职责边界——事件标签进记忆哪一层、保留多久；3. **不做什么**三条：不做全 521 类常驻输出（长期事件序列聚合可推断家庭结构与作息，属超范围画像）· 不引入视觉模态（合规成本 + 与即焚互斥）· **不让 AED 结果单独触发留存**（事件标签只能改变"是否蒸馏"，不能改变"是否留存原始音频"，否则即焚被绕过）。

- [ ] **Step 3: 改 HY4 代码（条件执行）**

按 Task 7 结论执行；保持惰性导入与缺依赖静默降级到 `stub` 的既有行为。

- [ ] **Step 4: 跑 HY4 全量测试（跨仓库）**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .`
Expected: `Ran 147 tests ... OK`。

- [ ] **Step 5: 给速览版加指针（不删除）**

在 `docs/research/2026-09-11-aed-agc-model-landscape.md` 头部插入一行，指向 `docs/research/audio-events/` 并说明 AED 部分已被取代（AGC 部分另见 Task 9–16）。**保留原文**（其 §7 文献跟踪仍有独立价值）。

- [ ] **Step 6: 分别 Commit（两个仓库）**

```bash
git add docs/research/audio-events/07-adoption.md docs/research/2026-09-11-aed-agc-model-landscape.md
git commit -m "docs(audio-events): adoption plan and pointer from superseded landscape"

cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add <Task 7 指定的文件> README.md
git commit -m "feat: AED channel per audio-events landscape decision"
```

---

### Task 9: AGC 经典 DSP 档（主力，必须先做）

**Files:**
- Create: `docs/research/auto-gain/01-classical-dsp.md`
- Test: `scripts/check_agc_table.py docs/research/auto-gain/01-classical-dsp.md`

**Interfaces:**
- Consumes: `00` schema 与编号化自测口径。
- Produces: 经典 DSP 档表格 + **二次增益结论**（决定后面所有 AGC Task 的走向）。

- [ ] **Step 1: 先回答"二次增益"（本 Task 的核心）**

检索三层并明确写出结论：（a）Android AudioSource / HAL 是否默认施加 AGC（`VOICE_COMMUNICATION` vs `MIC` vs `UNPROCESSED` 的区别是线索）；（b）走 `UNPROCESSED` 能否绕过；（c）proot Ubuntu 经 Termux 录音走哪条路径。
结论三选一，如实写：已过 AGC（用户态再加即二次增益 → 削波与增益泵浦，直接决定 Task 16 是"不加"或"只做响度归一"）/ 可绕过（写条件与代价）/ 不确定（写"需真机验证"并给出方法：录已知电平的扫频/白噪，看输出是否随输入线性）。**不许含糊带过。**

- [ ] **Step 2: 建表（不少于 8 条）**

每条含作用点、控制对象（数字/模拟/响度）、许可、来源（官方仓库或 RFC/标准）、**是否可得**（厂商固件写 `no`）。WebRTC AGC2 必须收录并写清两段结构（模拟段改采集音量、数字段做响度闭环）与内置噪声门。

- [ ] **Step 3: 写"经典 DSP 为什么仍是主力"小节**

CPU 占用（MCPS 量级）、内存（状态变量字节量级）、延迟（帧长与 lookahead）、以及在收敛时间/稳态误差这类闭环指标上神经方案是否有公开证据能赢。

- [ ] **Step 4: 写"标准与合规"小节**

核实后列出 ITU-R BS.1770-4、EBU R128、ATSC A/85、中国对应标准（检索 GY/T 系列）：标准号（核实后再写，不许编）、目标响度值、适用范围。

- [ ] **Step 5: 跑校验器**（`n/a(非神经)` 与 `自测口径 N` 是合法写法）+ **Step 6: Commit**

```bash
git add docs/research/auto-gain/01-classical-dsp.md
git commit -m "docs(auto-gain): classical DSP stage and the double-gain question"
```

---

### Task 10: AGC 小型神经网络（< 30M）

**Files:**
- Create: `docs/research/auto-gain/02-small-models.md`
- Test: `scripts/check_agc_table.py docs/research/auto-gain/02-small-models.md`

**Interfaces:**
- Consumes: `00` schema 与自测口径、Task 9 的二次增益结论。
- Produces: 小型档表格，供 Task 12/15/16 使用。

- [ ] **Step 1: 检索**

补检索：`neural AGC`、`learned gain control speech`、`SE-AGCNet`、`RNNoise MCU deployment`、`DeepFilterNet RTF`、`lightweight speech enhancement DNS challenge`、`GTCRN parameters`。重点核实 **SE-AGCNet**（arXiv 2606.25959）：唯一明确把"语音增强 + LUFS 响度控制"端到端联合的工作，参数量/许可/权重可得性/指标都要找到出处。

- [ ] **Step 2: 建表（不少于 10 条）**

每条含参数量、作用点、控制对象（多数是 `降噪掩码` 或 `联合(SE+AGC)`，**降噪不等于增益控制，不得混记**）、许可、来源。

- [ ] **Step 3: 写"神经网络在这里换来了什么"小节（本计划的判决定性点）**

（a）相对经典 DSP 在**噪声场景**下的增益（PESQ / STOI / SI-SDR / DNSMOS）；（b）在**纯电平调整**（无噪声、只是说话声小）这一 AGC 本职任务上，神经方案是否有证据优于经典反馈环——**若没有证据就写"没有证据"，不许用噪声场景的数字替代**；（c）代价：RTF、内存、模型体积、常驻功耗。

- [ ] **Step 4: 跑校验器 + Step 5: Commit**

```bash
git add docs/research/auto-gain/02-small-models.md
git commit -m "docs(auto-gain): small neural gain/enhancement models (<30M)"
```

---

### Task 11: AGC 中型神经网络（30M–500M，预期稀疏）

**Files:**
- Create: `docs/research/auto-gain/03-medium-models.md`
- Test: `scripts/check_agc_table.py docs/research/auto-gain/03-medium-models.md`

**Interfaces:**
- Consumes: `00` schema。
- Produces: 中型档表格与"该档稀疏"的判定。

- [ ] **Step 1: 检索并判定是否稀疏**

补检索：`speech enhancement model parameters 30M 100M`、`MossFormer2 parameters`、`TF-GridNet RTF`。**明确规则**：若核实后不足 6 条，**不得为凑数灌水**（不许把声码器、TTS 前端塞进来充数），改为显式写「该档稀疏」并给出原因（增益/增强是低层信号处理，几十 M 内已饱和，实时性约束先于精度触顶）。

- [ ] **Step 2: 建表（下限 4 条）**

每条含参数量、RTF（有则必填）、作用点、控制对象（相邻领域的写 `非AGC(相邻：…)` 并注明收录理由）、许可、来源。

- [ ] **Step 3: 写"中型档稀疏说明"小节**

给出条目数、代表模型、为什么没有更多；若结论与预期相反（该档其实丰富），同样如实写，并回过头在 `00` 的口径裁定节记录对预期假设的推翻。

- [ ] **Step 4: 跑校验器 + Commit**

```bash
git add docs/research/auto-gain/03-medium-models.md
git commit -m "docs(auto-gain): medium neural models and the sparsity finding"
```

---

### Task 12: AGC 大型与生成式（> 500M）

**Files:**
- Create: `docs/research/auto-gain/04-large-models.md`
- Test: `scripts/check_agc_table.py docs/research/auto-gain/04-large-models.md`

**Interfaces:**
- Consumes: `00` schema（含"参数量对扩散失效"约束）。
- Produces: 大型档表格，供 Task 15/16 使用。

- [ ] **Step 1: 检索**

补检索：`diffusion speech enhancement NFE`、`audio super resolution model size`、`generative audio restoration real time`。

- [ ] **Step 2: 建表（不少于 6 条）**

每条**必须**同时给出参数量与 NFE（扩散/流匹配步数）或 RTF，缺一不可入表。`控制对象` 列几乎全部写 `非AGC(相邻：修复·超分)` 并注明收录理由——本档存在的意义是回答"用生成式做增益/修复值不值"，不是选型池。

- [ ] **Step 3: 写"生成式在这里的边界"小节**

（a）相对经典 DSP 在**极低质量输入**（严重削波、带限、强噪）上提升多少；（b）RTF 与 NFE 量级 + 是否可能实时的明确判断；（c）**幻觉风险**——生成式会"补出"输入中不存在的语音内容，在"原音频即焚 + 只留文本"架构下意味着无来源的记忆进入转写与情绪判定。此条必须在 Task 16 落地篇被引用。

- [ ] **Step 4: 跑校验器 + Commit**

```bash
git add docs/research/auto-gain/04-large-models.md
git commit -m "docs(auto-gain): large/generative restoration and the hallucination boundary"
```

---

### Task 13: AGC 跨切轴一 —— 端侧部署

**Files:**
- Create: `docs/research/auto-gain/05-edge-deployment.md`
- Modify: `docs/research/auto-gain/01-classical-dsp.md`、`02-small-models.md`（回填 `edge` 列）

**Interfaces:**
- Consumes: Task 9/10 表格、Task 9 的二次增益结论、SER 04 已建立的功耗阶梯（**引用，不重算**）。
- Produces: 端侧结论，供 Task 15/16 使用。

- [ ] **Step 1: 写"三处作用点的端侧可得性"表（AGC 独有）**

| 作用点 | 第三方 App 能否实现 | 功耗档 | 备注 |
|---|---|---|---|
| 采集前（aDSP / TX-path） | 通常**不能**（SER 04 结论：普通第三方 App 能用 Hexagon HTP，但不能用 aDSP 的 SEE/LPAI，内核 fastrpc 对未授信进程 attach audioPD 返回 -EACCES） | mW 档 | 拿不到 |
| 采集后（AP 用户态 / proot） | 能 | 常驻跑模型数十至数百 mW；跑经典 DSP < 5 MCPS | 唯一可选层 |
| 离线 | 能 | 一次性 | 与即焚架构兼容性另论 |

沿用 A/B 两档：A 档·真端侧 vs B 档·proot 内（CPU 推理，通用 Linux 空闲 400–1000 mW）。

- [ ] **Step 2: 检索 runtime 与量化证据**

覆盖 TFLite Micro、ONNX Runtime Mobile、CoreML、NCNN、MNN、RKNN、QNN、CMSIS-NN / Ethos-U（MCU 侧）。重点核实 **RNNoise 一类超小模型在 MCU 上的公开部署案例**（AGC 领域唯一有大量端侧实测证据的分支）。

- [ ] **Step 3: 写"常驻增益控制的功耗账"**

经典 DSP（WebRTC AGC2 一类）的 MCPS 与 mW 量级；小型神经网络（RNNoise / DTLN / GTCRN 一类）常驻的 RTF 与 mW 量级；两者相对"什么都不做"的增量。**功耗引用 SER 04 与 `docs/research/always-on-recording/` 已建立的量级阶梯**，不另起一套。

- [ ] **Step 4: 回填 edge 列**（经典 DSP 通常可写 `yes: 任意 CPU（C 定点实现）`，但备注说明仍需跑在 AP 上）

- [ ] **Step 5: 跑校验器 + Commit**

```bash
git add docs/research/auto-gain/05-edge-deployment.md 01-classical-dsp.md 02-small-models.md
git commit -m "docs(auto-gain): edge deployment axis — aDSP unreachable, AP is the only layer"
```

---

### Task 14: AGC 跨切轴二 —— 多模态（预期为空）

**Files:**
- Create: `docs/research/auto-gain/06-multimodal.md`

**Interfaces:**
- Consumes: `00` 的多模态候选池、Task 10/12 表格。
- Produces: 多模态象限的**空/非空判定与论证**，供 Task 15 使用。

- [ ] **Step 1: 检索（检索词逐条记录进文件）**

至少覆盖：`audio-visual gain control`、`visual-assisted automatic gain control`、`multimodal loudness normalization`、`audio-visual speech enhancement`、`speaker distance estimation visual gain`、`video conferencing audio video joint normalization`、`跨模态 响度 归一`。

- [ ] **Step 2: 记录检索证据**

每个检索词、命中工作（无则写 `无命中`）、以及命中项为何**不算**多模态 AGC（例如 audio-visual speech enhancement 是增强不是增益控制，控制对象是掩码不是增益）。

- [ ] **Step 3: 写"这个象限为什么是空的"小节**

给出物理解释而不只是"没找到"：增益是**瞬时电平闭环**问题，决策所需信息全在音频信号本身（当前电平、目标电平、噪声底），视觉与文本不提供额外的瞬时电平信息；唯一有物理意义的多模态输入是**说话人距离/朝向**，但声学方法更直接省电、视觉方案要开摄像头（合规与功耗高一个量级）。此论证要由检索证据支撑，允许推翻。

- [ ] **Step 4: 若证伪则建表**

若确实找到 ≥ 3 条真实的多模态 AGC 工作，按 schema 建表并跑 `check_agc_table.py`，同时在 `00` 口径裁定节记录对预期假设的推翻。

- [ ] **Step 5: Commit**

```bash
git add docs/research/auto-gain/06-multimodal.md
git commit -m "docs(auto-gain): multimodal axis — empty quadrant with evidence"
```

---

### Task 15: AGC 收敛 —— landscape + 交叉表 + HTML 全景

**Files:**
- Create: `docs/research/auto-gain/2026-09-landscape.md`
- Create: `docs/auto-gain-models.html`

**Interfaces:**
- Consumes: Task 9–14 全部表格与结论。
- Produces: 选型输入，供 Task 16 使用。

- [ ] **Step 1: 写交叉表**

**档位（经典 DSP / 小 / 中 / 大）× {edge, multimodal}**，每格给：条目数、代表实现、典型指标（PESQ/STOI 或收敛时间/稳态误差，视控制对象而定）、典型 RTF/MCPS。多模态列若全空就写"全空（见 06）"，**不填占位符**。

- [ ] **Step 2: 写"AGC 到底是不是模型问题"（本计划的结论锚点）**

用 Task 9–12 的证据给出明确判断，形态为下列之一并给理由：**主要是 DSP 问题 / 主要是模型问题 / 分层（闭环增益是 DSP，噪声场景是模型）**。无论哪种都要引用具体数字，**不许骑墙**。

- [ ] **Step 3: 写"加在哪一层"决策表**

输入：是否已过 TX-path AGC（Task 9 结论）、能否拿 aDSP（不能，见 Task 13）、是否常驻、是否允许联网、目标是 ASR/情绪蒸馏质量还是听感。输出：加 / 不加 / 加在哪层 / 用什么。**必须包含"什么都不加"这一行及其触发条件。**

- [ ] **Step 4: 写"与即焚架构的兼容性"小节**

增益只作用于**送入推理的那份副本**，不作用于留存副本；增益参数可随原始音频一并焚毁；生成式修复因会补出输入中不存在的内容（Task 12 幻觉风险），**不得**用于会产生记忆的链路。

- [ ] **Step 5: 生成 HTML 全景**

`docs/auto-gain-models.html`：深色单文件、零外部依赖、sticky 导航。至少含：三处作用点示意图（内联 SVG）、档位 × edge 矩阵、经典 DSP 与小型神经网络的功耗/RTF 对比表、响度标准表、多模态空象限说明。

- [ ] **Step 6: 跑全量校验器**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py docs/research/auto-gain/*.md`
Expected: 0 违规，总记录 ≥ 28（领域主力为非神经 DSP，条目数天然少于 AED/SER，属正常）。

- [ ] **Step 7: Commit**

```bash
git add docs/research/auto-gain/2026-09-landscape.md docs/auto-gain-models.html
git commit -m "docs(auto-gain): landscape synthesis and HTML panorama"
```

---

### Task 16: AGC 落地 —— 接回 AlwaysOnRec-HY4

**Files:**
- Create: `docs/research/auto-gain/07-adoption.md`
- Modify: HY4 下由 Task 15 结论指定的文件（**不得凭空指定**；若结论为"不加"，则只改文档）
- Test: HY4 `python -m unittest discover -s tests -t .`（147 全绿）

**Interfaces:**
- Consumes: Task 15 决策表、Task 9 的二次增益结论、Task 13 的作用点可得性。
- Produces: 一个明确的落地动作，或一份"什么都不做"的论证。

- [ ] **Step 1: 先读 HY4 捕获链路再动笔**

读 `aor/drivers/ear.py` 及捕获相关代码，确认并写入 `07-adoption.md`：（a）当前录音源与是否已存在增益/归一化处理；（b）`classify_mood(dbfs, dur_ms)` 的 `dbfs` 怎么算——**若 AGC 施加在它之前，电平被归一化后 dbfs 就失去"这个人说话多大声"的信息**，这是真实副作用，必须写明；（c）若加 AGC，是在录音写入前（影响留存）还是只在送推理前（不影响留存）。

- [ ] **Step 2: 写落地建议**

必须回答：1. 按 Task 15 决策表，本仓库的具体动作（加 / 不加 / 只做响度归一）；2. 若加：用哪个实现、加在哪层、如何避免二次增益、如何保留 dbfs 的原始电平语义；3. **不做什么**三条：不在采集前层做（第三方 App 拿不到 aDSP 的 SEE/LPAI）· 不引入生成式修复（补出不存在的内容，污染转写与情绪记忆）· 不让增益作用于留存副本。

- [ ] **Step 3: 改 HY4 代码（条件执行）**

若 Task 15 结论为"加"，在 Step 1 确认的位置加分支，保持惰性导入与缺依赖静默降级；若为"不加"，**不改代码**，只写明触发条件（例如"若未来切换到 `AudioSource.UNPROCESSED` 或原生 App 拿到未处理 PCM，则重新评估"）。

- [ ] **Step 4: 跑 HY4 全量测试**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4 && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .`
Expected: `Ran 147 tests ... OK`。

- [ ] **Step 5: 给速览版加指针（不删除）**

在 `docs/research/2026-09-11-aed-agc-model-landscape.md` 头部插入一行，指向 `docs/research/auto-gain/` 并说明 AGC 部分已被取代。**保留原文**（其 §8 文献跟踪仍有独立价值）。

- [ ] **Step 6: 分别 Commit（两个仓库）**

```bash
git add docs/research/auto-gain/07-adoption.md docs/research/2026-09-11-aed-agc-model-landscape.md
git commit -m "docs(auto-gain): adoption plan and pointer from superseded landscape"

cd C:\Users\yaoyue\CodeBuddy\Claw\AlwaysOnRec-HY4
git add <Task 15 指定的文件>
git commit -m "feat: gain handling per auto-gain landscape decision"
```

---

## 验收清单（全部完成后）

- [ ] Task 0：HY4 `Ran 147 tests ... OK`（当前 1 个失败已判因并修复）
- [ ] `scripts/check_ser_table.py docs/research/speech-emotion/*.md` 零违规，SER 总记录 ≥ 42（增量只来自 06-adoption，不改既有表）
- [ ] `scripts/check_agc_table.py docs/research/auto-gain/*.md` 零违规，AGC 总记录 ≥ 28
- [ ] `scripts/check_aed_table.py docs/research/audio-events/*.md` 零违规，AED 总记录 ≥ 40
- [ ] 三个校验器每次运行时**表数与记录数已与文件实际表格数核对**（防 table_lint 静默跳过）
- [ ] 三份 landscape + 三份 HTML 全景产出，HTML 零外部依赖
- [ ] AED「中文场景空白」一节已写，且未用英文基准冒充中文可用性
- [ ] AGC「二次增益」有明确结论（已过 AGC / 可绕过 / 需真机验证），未含糊带过
- [ ] AGC「到底是不是模型问题」给出单一明确判断，未骑墙
- [ ] 所有 AudioSet 数字标注了 AS-20K 还是 AS-2M full；跨任务类型数字未被互相比较
- [ ] 三条落地篇都显式写了"不做什么"三条
- [ ] 主库 `laos/` 全程未改，980 项测试保持全绿
- [ ] 速览版 `2026-09-11-aed-agc-model-landscape.md` 保留且头部有指针（AED 与 AGC 各一行）
- [ ] 每个 Task 一个 commit（laos 仓库 16 个 + HY4 仓库至多 4 个）
- [ ] `docs/research/INDEX.md` 与 `docs/research/2026-09-19-laos-adoption-capstone.md` 补登记三条线的收尾成果

## 自检记录（写完即核）

- **Spec 覆盖**：三条源计划的剩余 Task 全部映射进本计划（SER T8→Task 1；AED T2–T8→Task 2–8；AGC T2–9→Task 9–16），并新增 Task 0 作为共同前置门禁（源计划写于 HY4 全绿时期，未料到当前 1 个失败）。
- **占位符扫描**：无 `TBD` / `待补` / `TODO` / "Similar to Task N"。所有"[待核实]起点线索"均附带"找不到就删"的处置规则（沿用源计划口径，校验器会拦占位词）。
- **类型/命名一致**：三个校验器命令在全文逐字一致；文件编号沿用源计划（`01-small-models.md` 等在 AED/AGC 两域各自独立，不交叉）；`AOR_ASR_CHANNEL`、`channel()`、`classify_mood()` 与 HY4 现有代码逐字一致；解释器一律 `C:/Users/yaoyue/miniconda3/python.exe`。
- **既有接口不破坏**：`check_ser_table.py` 只读不写；`laos/` 主代码不动；`channel()` 新增分支带默认值，`stub`/`funasr`/`server` 行为不变；HY4 既有 147 测试保持通过。
- **与现状文档的咬合**：`docs/design/2026-10-08-architecture-current-state.md` §11 列出的 6 项硬伤中，第 6 项（HY4 失败测试）由 Task 0 处理；第 5 项（table_lint 首列硬编码）不修代码，改为 Global Constraint 3 的**核对表数**要求来规避静默跳过——两条线互不冲突。

---

## Execution Handoff

Plan 已写完并保存。执行方式二选一：

**1. Subagent-Driven（推荐）** —— 每个 Task 派一个子代理，两轮审查（先符合 spec、再质量），Task 间快速迭代。三条线（SER / AED / AGC）互不依赖，可并行派发；Task 0 必须先于 Task 1 / 8 / 16 完成。

**2. Inline Execution** —— 在当前会话按序执行，带检查点。

选哪种？
