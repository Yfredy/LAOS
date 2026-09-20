# 05 · laos 判定点映射与落点清单（Task 5）

> 本文件是 Part 2 的设计产出：把 laos 现有的「魔法数字 / 朴素相似度」判定点逐一映射到
> Jev 的三原语（Choice / Score / Noul），给出收益、代价（**全部挂 Task 4 实测数字**）与排除理由。
>
> **判据来源（唯一）**：`04-ondevice-benchmark.md` 的 `yzfly/edgejev` 本机实测——
> 首次加载 **2144 ms**、3 题批量 median **157.5 ms** / p95 **233.1 ms**、峰值 RSS **494.8 MB**、
> 模型目录 **358.9 MB**；README 宣称的 15.6 ms 被否证（本机无 VNNI，慢约 **10×**）。
> 外推 aarch64 无可靠换算系数，仅量级估计：常驻每帧调用 → 持续 **0.5–1.5 W** 附加（否决）；
> 离线/二级确认档 → 常摊 **4.6 mW** 量级（可接受）。**不沿用任何 README 宣称值。**

---

## Step 1 · laos 现有的「魔法数字」判定点（逐个核对源码，行号以实际为准）

下表为起点表（计划第 343–355 行）按**实际源码核对**后的结果。相较起点表有 **2 处偏差**（已在表末注明）：

| # | 位置（实际行号） | 当前判定 | 类型 |
|---|---|---|---|
| 1 | `laos/vad.py:43` `split_segments(threshold_dbfs=-35.0)`；`laos/vad.py:107` `StreamingVAD.__init__(threshold_dbfs=-35.0)` | 固定能量阈值 | 硬阈值 |
| 2 | `drivers/drv_mic.py:61` `split_on_silence(threshold_db=-40)`；`drivers/drv_mic.py:183` `mic_listen_start(threshold_db=-40.0)` | 固定能量阈值 | 硬阈值 |
| 3 | `laos/memory.py:43` `bigram_jaccard(a,b)`；`laos/memory.py:120` `MemoryStore.recall(query,k=5)`（含权重 `0.7/0.2/0.1` `memory.py:13,133`） | bigram Jaccard 相似度 + 固定权重 | 朴素相似度 |
| 4 | `laos/memory.py:35` `RECENCY_HALF_LIFE_DAYS = 14.0` | 固定半衰期 | 硬阈值 |
| 5 | `laos/skills.py:48` `SkillStore.match(query,k=3)`（走 `memory.recall`） | 同上（文本 Jaccard） | 朴素相似度 |
| 6 | `laos/risk.py:48` `FleetLedger.can_admit()` → `remaining > reserve` | 布尔硬规则 | 硬阈值 |
| 7 | `laos/risk.py:40` `FleetLedger.multiplier` | 外部输入，无判断 | 空缺 |
| 8 | `laos/context.py:127` `_compact_if_needed()` / `:162` `_swap_out(victims)` / `:174` `_default_summarizer`（按 token 窗口换出 + 160 字截断摘要） | 按 token 窗口换出 | 硬阈值 |
| 9 | `laos/brain.py:220` `make_brain(**kwargs)` / `Brain.think`（key 存在→OpenAIChatBrain，否则 ScriptedBrain，`brain.py:222`） | 单一 brain，无路由 | 空缺 |
| 10 | `drivers/drv_ear.py:191` `ear_transcribe`（funasr SenseVoiceSmall，`LAOS_ASR_CHANNEL`=`funasr`/`server`） | 固定 ASR 通道 | 固定 |
| 11 | `laos/scheduler.py:41` `next_pid()` / `:86` `note_outcome(pid, ok)`（优先级 + token 预算 + err 预算） | 规则调度 | 规则调度 |

**与起点表的偏差（实测源码后确认）：**

- **偏差 A（新增，非魔法数字）**：`laos/memory.py:106-112` 的 `remember(judge=...)` 与
  `laos/context.py:131-156` 的 `_compact_if_needed(judge=...)` **已由 Task 4 预埋 opt-in 的
  `judge.noul(...).verdict == "deny"` 钩子**（`REMEMBER_JUDGE_QUESTION` `memory.py:40`、
  `COMPACT_JUDGE_QUESTION` `context.py:32`）。即「记忆入库预审」「上下文压缩预审」两条
  Noul 落点**骨架已存在**，仅缺真实 edgejev 后端与阈值调参。这意味着 Step 2 的候选 8 已部分落地。
- **偏差 B（细化）**：起点表把 `MemoryStore.recall` 的相似度描述为单点，实际其内部评分是
  `bigram_jaccard*0.7 + tag_ratio*0.2 + recency*0.1`（`memory.py:13,133`）三个**硬权重**叠加，
  权重本身也是魔法数字，一并计入判定点 3。

> 说明：本表为「判定点映射表」，列数 ≠ 12，按口径文件裁定 `check_jev_table.py` 自动跳过、不误伤。

---

## Step 2 · 逐点映射到 Choice / Score / Noul

> 代价数字一律来自 Task 4：`edgejev` 单次调用 = 3 题齐发一次 forward pass，**median 157.5 ms /
> p95 233.1 ms**（x86 无 VNNI，onnxruntime CPU int8）；aarch64 估计 **100–400 ms/批**（同量级，
> 无可靠系数）。常驻 session 占用 **RSS ~495 MB**，首次加载 **2144 ms**。

### 候选 1 · 漏斗① 触发判定（`StreamingVAD` / `mic_listen_start`）→ **Noul**
- **原语**：`Noul("这段是人声且值得记录")`，替代/叠加纯能量门。
- **state**：`{waveform_rms, segment_wav, env_noise_profile}`。
- **预期收益**：能量门把「有声 vs 无声」误判为「值得记 vs 不记」（电视声、键盘声、邻居说话都会过门）。
  Jev 能区分「主人的行为意图」，减少无效蒸馏与即焚写盘。
- **代价（最大风险）**：若在**每帧实时路径**无条件调用 → 按 Task 4 外推，**1 次/秒持续附加
  0.5–1.5 W**（§4 高档，否决）；且常驻 495 MB RSS 长期占用。
- **裁定**：**纯每帧调用不可行（否决）**。改为**两级结构**——能量门先过（0 代价），Jev 仅在
  边界有声段做二次确认（中档：N≈1000–5000/天 → 0.5–2 J/天，常摊 **0.1–0.2 mW**，可接受）。
  两级结构可行，但属实时触发路径，留待实测足够后再上（见 P4+）。

### 候选 2 · 漏斗③ 蒸馏后的重要度（`memory.remember` 前）→ **Score**
- **原语**：`Score("这段内容对主人的长期价值", legend=[无用,低,中,高,关键])`。
- **state**：`{transcript, emotions, kind, speaker}`。
- **预期收益**：当前 `remember` 全量入长期记忆（或靠 `judge.noul` 二值拒绝），无连续价值分档；
  Score 可驱动「高价值→长期记忆 / 低价值→即焚」的连续分流，替代固定 `RECENCY_HALF_LIFE_DAYS`。
- **代价**：每次蒸馏触发 1 次 Jev（157.5 ms/批）；属于**非实时触发路径**（不在每帧循环），
  每天数百–数千次 → 常摊 4.6 mW 量级（§4 低档，可忽略）。失效模式：legnend 标定不当会把
  高情绪但低价值内容误判——需以 `confidence` 兜底（低置信转人工复核）。

### 候选 3 · 漏斗③ 记忆类别路由 → **Choice**
- **原语**：`Choice(kind)`，options = `[billing, technical, personal, scheduling, ...]`（≤255）。
- **state**：`{transcript, emotions, tags}`。
- **预期收益**：现状 `kind` 由调用方自己传（`skills.learn_from_result` 硬编码 `kind="skill"`，
  `memory.remember` 调用方指定），分类口径不统一。Jev 统一路由，且 `confidence` 来自分布形状
  （官方示例 billing 0.84 但 confidence 仅 0.596），可三档处置。
- **代价**：与候选 2 同一批次内齐发（加题几乎不增延迟，口径 §3），无额外延迟；离线触发路径。

### 候选 4 · 记忆召回（`MemoryStore.recall`）→ **Score（两级：Jaccard 召回 + Jev 精排）**
- **原语**：`Score("这条记忆与当前查询的相关度", legend=[无关,弱,中,强])` 替代 `bigram_jaccard*0.7`。
- **state**：`{query, recalled_text, tags, kind}`。
- **预期收益**：bigram Jaccard 对语义近义、改写、跨语言召回差（中英混合场景尤甚）；Jev 语义精排
  提升 top-k 质量。保留 Jaccard 做粗召回（O(1) 本地、零代价）避免全量过模型。
- **代价**：仅对粗召回 top-N 精排，调用量 = 召回量（非全库），离线路径；157.5 ms/批可承受。
  失效模式：Jev 误排压过低相关真值 → 保留原 `j<=0 and tag_ratio<=0` 零相关短路（`memory.py:129`）。

### 候选 5 · 记忆半衰期（`RECENCY_HALF_LIFE_DAYS`）→ 由 **Score** 分档
- **原语**：复用候选 2 的价值 `Score`，半衰期按分值分档（高价值 → 半衰期拉长至 60–90 天，
  低价值 → 缩至 3–7 天），**取代固定 14 天**。
- **state**：同候选 2 的 `value` score。
- **预期收益**：高价值记忆不再被 14 天一刀切衰减；低价值更快即焚，省存储与召回噪声。
- **代价**：与候选 2 同一批次，零额外延迟；**但半衰期动态化会改变 `recall` 的 `recency` 项**
  （`memory.py:132`），需重构为每记录存 `score` 而非全局常量——中改动量。

### 候选 6 · 不可逆操作闸门（`FleetLedger.can_admit`）→ **Score + confidence 三档（最高价值）**
- **原语**：`Score("这次调用有多不可逆", legend=[可逆,低,中,高,致命])` + `confidence` 三档处置。
- **state**：`{tool, args, caller_pid, current_budget, multiplier}`。
- **预期收益**：现状 `can_admit` 仅 `remaining > reserve`（`risk.py:50`）布尔硬规则，不衡量操作
  **不可逆程度**。`charge` 按**尝试计费**且 **kill 不退款**（`risk.py:9-21`）——低置信放行会
  **直接烧预算**。Jev 用 `confidence` 三档：高=放行 / 中=记录待复核 / 低=要求确认，把「不可逆性」
  显式化。
- **代价**：触发路径（spawn 时），非每帧；157.5 ms/批可承受。失效模式最危险：**低置信误放行
  = 真金白银损失**（`risk.py` 明确 charge 不退）→ 阈值必须按错判代价缩放，低档强制确认，
  不得自动执行。这是全表**唯一涉及预算燃烧**的落点，优先级高但需严调阈值。

### 候选 7 · 技能路由（`SkillStore.match`）→ **Choice**
- **原语**：`Choice(skill_id)`，options = 候选技能签名集合（≤255）。
- **state**：`{task_text, candidate_signatures}`。
- **预期收益**：现走 `memory.recall` 的文本 Jaccard（`skills.py:50`），语义近义技能捞不准；
  Jev 选最匹配技能注入 `[skill-hint]`。
- **代价**：与候选 4 同属召回路径，可共享 Jev session；离线。

### 候选 8 · 上下文压缩（`_swap_out` / `_default_summarizer`）→ **Noul（已 opt-in 预埋，见偏差 A）**
- **原语**：`Noul("这条换出后会丢失关键信息")`，对标 `tamaratran/fast-jev-compaction`(4868★)。
- **state**：`{message_content, role, prior_summary}`。
- **预期收益**：现状按 token 窗口机械换出最老 1/3（`context.py:129`），可能丢关键约束；
  Jev 把「不可丢」消息保留在窗口内（`context.py:138-143` 骨架已写）。
- **代价**：压缩发生在 `append` 时（非每帧实时），频率低；157.5 ms/批可承受。**骨架已由 Task 4
  预埋**（`judge.noul` 分支），只需接真实 edgejev 后端并调 `COMPACT_JUDGE_QUESTION` 阈值 →
  **落地成本最低、风险最小，列 P0**。

### 候选 9 · Brain 路由（`make_brain`）→ **Choice**
- **原语**：`Choice(brain_id)`，options = `[scripted, openai, local_llm, ...]`。
- **state**：`{task_complexity, latency_budget, api_available}`。
- **预期收益**：现状 `make_brain` 仅按「有无 API key」二选一（`brain.py:222`），无复杂度感知；
  Jev 可做模型路由，对标 `kerpopule/hermes-jev-skills`(195★)。
- **代价**：改动最大（涉及 Brain 抽象与多后端生命周期）；且 Jev 自身是**决策**模型不是生成模型，
  路由目标仍是 LLM——收益边际。列 P4，最后做。

### 映射分布小结
- **Choice ×3**：候选 3（类别路由）、7（技能路由）、9（Brain 路由）。
- **Score ×4**：候选 2（重要度）、4（召回精排）、5（半衰期）、6（不可逆闸门）。
- **Noul ×2**：候选 1（触发）、8（压缩）。
- **已 opt-in 预埋**：候选 8 与「记忆入库预审」（`remember` 的 `judge.noul`）骨架已存在，证实
  Noul 在 laos 的接口形态可行，降低后续落地风险。

---

## Step 3 · 「不值得做」的部分及理由

1. **官方云端 API 进运行时**：违反 Global Constraints 2/7——闭源无权重、无自托管、未向中国大陆
   开放、laos 要求本地优先。只能作参考基线，不得成运行时依赖。
2. **为 laos 自训练一个决策头**：成本（训练数据/算力/校准）与收益不匹配。Task 4 已证明 `edgejev`
   可跑通，现有复现够用；除非全部复现不可用才考虑（现状非此）。
3. **用 Jev 替代 ASR 或情绪模型**：Jev **不生成文本**（`00-taxonomy-and-metrics.md` §1），
   不是生成模型的替代品；`drv_ear` 的 SenseVoice 负责 ASR+情绪，Jev 只在其后做决策。
4. **漏斗① 每帧路径无条件调用 Jev**：功耗否决——Task 4 §4 高档，1 次/秒 → 持续 0.5–1.5 W 附加，
   手机不可承受。必须两级结构（候选 1 已裁定）。
5. **（本执行者补充）为每个判定点独立加载/启停 edgejev 实例**：Task 4 实测首次加载 **2144 ms**、
   峰值 RSS **494.8 MB** → 模型**不能按需启停**（每次冷启 2.1 s 不可接受延迟），且常驻即占
   **~495 MB**。推论：所有落地点的 Jev 必须以**单一常驻 session** 服务（多个 Noul/Score/Choice
   题可一次 `system_one` 齐发，加题几乎不增延迟，口径 §3）；**不值得为每个模块各起一个 edgejev
   进程/会话**——那会线性放大 RAM 占用（N×495 MB），在手机上直接 OOM。这条是前面所有落点的
   **架构前提**：离线/二级确认落点共享同一 session，漏斗① 若上也必须复用该 session 而非新建。

---

## Step 4 · 落地顺序（P0–P4，按收益 ÷ 风险）

> 排序原则（计划第 381 行）：**P0 必须是离线/非实时路径**，常驻实时路径留到实测足够之后。

| 优先级 | 落点（候选） | 原语 | 理由（挂 Task 4 数字） |
|---|---|---|---|
| **P0** | 上下文压缩（8，已 opt-in）+ 记忆召回精排（4） | Noul / Score | 均**离线非实时**，不碰常驻每帧路径；157.5 ms/批、每天数百次 → 常摊 **4.6 mW** 量级（§4 低档，可忽略）；压缩钩子骨架已由 Task 4 预埋，落地成本最低、风险最小。 |
| P1 | 蒸馏重要度（2）+ 记忆类别路由（3） | Score / Choice | 漏斗③ 蒸馏后触发（非实时每帧）；与 P0 共享同一常驻 Jev session，加题不增延迟；直接提升记忆质量与即焚判定。 |
| P2 | 不可逆操作闸门（6） | Score + confidence | 离线触发、价值最高（防烧预算），但 `charge` 不退 → 阈值须严调，故列 P1 之后谨慎落地。 |
| P3 | 记忆半衰期分档（5）+ 技能路由（7） | Score / Choice | 离线；半衰期需重构 `recall` 的 `recency` 项（中改动），技能路由复用召回 session。 |
| P4 | Brain 路由（9） | Choice | 改动最大、收益边际，最后做。 |
| 否决/观察 | 漏斗① 常驻（1） | Noul（两级） | 纯每帧调用**不可行**（0.5–1.5 W 附加）；两级结构（能量门先过 + 边界段二次确认）可行但属实时触发路径，须先在 proot aarch64 实测功耗后评估，**不进当前落地**。 |

**P0 定义与理由**：P0 = **上下文压缩（Noul）+ 记忆召回精排（Score）**。二者都满足「离线/非实时、
复用单一常驻 Jev session、单批 157.5 ms 在每天数百次调用下常摊仅 4.6 mW、且不触碰常驻每帧实时
路径」四条，且压缩钩子已由 Task 4 预埋、几乎零新增架构风险——是 Task 4 实测结论下唯一「收益高、
代价可承受、落地快」的起点。

---

## 附：口径裁定记录（Task 5 新增）

### 裁定 J5：判定点映射表列数 ≠ 12，`check_jev_table.py` 自动跳过
本文件 Step 1/Step 2 的表为「判定点 → 原语」映射，列名非 12 列 schema，按口径文件第 7 节裁定
校验器不触发、不误伤。本文件不引入 12 列表，故不跑逐表校验（已确认无 12 列表即 0 违规，见校验记录）。

### 裁定 J6：Noul 落点不得补 confidence
候选 1（触发）、候选 8（压缩）用 `Noul`，按口径 §2 **只有 `noul` 概率、无 `confidence`**；
其「不可行/边界」判定只能靠 `noul` 阈值，不得自行补 confidence 字段（与 `memory.py` /
`context.py` 现有 `judge.noul(...).verdict` 抽象一致——该抽象把 `noul` 概率映射为 deny/allow，
不引入 confidence）。

### 裁定 J7：所有延迟/功耗引用必须带 Task 4 出处，禁用 README 15.6 ms
凡本文件延迟/内存/功耗数字，一律来自 `04-ondevice-benchmark.md` 实测（median 157.5 ms、RSS 495 MB、
首载 2144 ms、常驻每帧 0.5–1.5 W 否决）。README 宣称 15.6 ms 已否证（慢 10×），不得在落点代价中引用。
