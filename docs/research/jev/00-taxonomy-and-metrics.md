# Jev 口径：决策模型实质 / 三原语 / 12 列 schema / 校验器

> 本文件是 `docs/research/jev/` 下所有文件的**唯一口径来源**。
> 表格 schema 由 `scripts/check_jev_table.py` 机器校验，改动前先跑
> `python scripts/check_jev_table.py --selftest`。
>
> 本文件所列技术事实，除特别标注出处者外，均为**执行前人工实测核实（2026-09-21）**。
> Jev 是两周内出现的新词，网上信息少且混杂厂商宣传；裸词检索会混入
> `jevil` / `Jevons` / `JEVAN-BINDU-ANDROID` 等噪声。凡查不到的字段一律记 `未知`
> 并在「验证状态」标 `未核实`，**不许编造 star 数、延迟或许可**。

---

## 1. Jev 是什么 / 不是什么

**Jev** 是 TypeSafe AI 的 **System One** 决策模型——对标 Kahneman 的「快慢分工」里的
System 1（快、直觉、自动化），把「决策」本身做成模型的一等公民。

| 维度 | Jev（是） | 不是什么 |
|---|---|---|
| 输出形态 | **类型化、带校准（calibrated）的决策** | 不生成文本 |
| 架构 | transformer-based，但**非自回归 + 并行采样器** | 不是「小 LLM」 |
| 训练 | RLCD（Reinforcement Learning for Calibrated Decisions，对标 RLHF） | 不是单纯 SFT |
| 与「小 LLM」本质区别 | **输出空间在推理前就被定义**（由 typed questions 约束） | 不是参数量更小 |

**最关键的区分：Jev 与「小 LLM」的区别是输出空间的约束方式，不是参数量大小。**
小 LLM 仍要「生成」token、仍可能输出非法结构；Jev 的返回形状由请求里的
typed questions 在推理前就锁定，因此「结构化输出错误」由 schema 保证（见 §6），
但这不等于「答案正确」——**答案仍可能错，只是格式不会错**。

---

## 2. 三原语（返回形状照抄官方口径，不得改写）

三个原语在一次请求内可**并行且隔离**求值，加题几乎不增延迟。

| 原语 | 问什么 | 返回什么 | 典型用途 |
|---|---|---|---|
| `Choice` | 从至多 **255** 个选项里选一个 | `choice` + `probabilities` + `confidence` | 分类、路由、动作选择 |
| `Score` | 在连续量表上打分 | `score` + `legend` + `probabilities` + `confidence` | 重要度、风险、价值评级（**可落在两个等级之间**） |
| `Noul` | 二元/概率判断 | `noul`（0–1 概率） | 是否相关、是否值得记录（**无独立 confidence**） |

- `Choice` 的 `probabilities` 是各选项的概率分布；`confidence` 来自该分布的**形状**
  （见 §5），不是胜出选项的概率。
- `Score` 的 `legend` 定义量表等级；`score` 是连续值，**允许落在两个等级之间**
  （这是与 `Choice` 最直观的区别）。
- `Noul` **只有 `noul` 一个 0–1 概率，没有 `confidence`**——这是最容易写错的一点，
  落表/落代码时不得给它补一个 confidence。

---

## 3. state + typed questions 请求形状（完整示例）

请求携带 `state`（上下文）、`model`、`questions`（typed questions 列表）。
一次请求内并行求值，下面是「对一段转录做分类 + 价值评分 + 相关性判断」三题齐发：

```json
{
  "state": {
    "transcript": "帮我记一下，周五和张总开会讨论 Q3 预算",
    "speaker": "owner"
  },
  "model": "system-one",
  "questions": [
    {"type": "choice", "id": "category",
     "question": "这段属于哪类记忆？",
     "options": ["billing", "technical", "personal", "scheduling"]},
    {"type": "score", "id": "value",
     "question": "这段对主人的长期价值？",
     "legend": ["无用", "低", "中", "高", "关键"]},
    {"type": "noul", "id": "relevant",
     "question": "这段值得被常驻采集记录吗？"}
  ]
}
```

```json
{
  "answers": [
    {"id": "category", "choice": "billing",
     "probabilities": {"billing": 0.84, "technical": 0.159, "personal": 0.001, "scheduling": 0.0},
     "confidence": 0.596},
    {"id": "value", "score": 0.84,
     "legend": ["无用", "低", "中", "高", "关键"],
     "probabilities": {"无用": 0.0, "低": 0.0, "中": 0.16, "高": 0.84, "关键": 0.0},
     "confidence": 0.596},
    {"id": "relevant", "noul": 0.92}
  ]
}
```

注意：`relevant` 这个 `Noul` 回答**没有 `confidence` 字段**，只有 `noul`。
`category` 与 `value` 的 `confidence` 相同（0.596），因为二者共享同一份分布形状判据。

---

## 4. confidence 的语义与三档处置

**confidence 来自概率分布的「形状」，不是胜出选项的概率。**

上例里 `billing` 拿到 0.84（很高的胜出概率），但 `confidence` 只有 **0.596**——
因为 `technical` 仍占 0.159，分布并不「尖锐」。如果 `billing` 0.99、`technical` 0.01，
`confidence` 就会高得多。一句话：**confidence 衡量「模型有多确定」，不是「赢家有多强」**。

官方建议按错判代价缩放阈值，做三档处置：

| 档 | confidence 区间（示意，阈值按错判代价缩放） | 处置 |
|---|---|---|
| 高 | 分布尖锐（如 > 0.9 量级） | 自动执行 |
| 中 | 分布有次峰 | 入复核队列 |
| 低 | 分布平、多峰 | 转人工 |

**laos 特别提醒**：`FleetLedger.can_admit` 这类「不可逆操作闸门」若改由 Jev 驱动，
低置信度放行会**直接烧预算**（`charge` 按尝试计费、kill 不退款），因此低档必须要求确认，
中档必须记录待复核——这条在 Task 5 落点设计里写死。

---

## 5. 官方数字的可信度分级表

**诚信底线：任何引用官方数字处必须标注「官方自测」。**

| 数字 | 数值 | 标注 | 出处 / 口径说明 |
|---|---|---|---|
| 端到端延迟 | 70–500 ms | **官方自测** | TypeSafe workflow evals，参照系 GPT-6 Astra 与 Fable 5.1 平均 |
| 定价 | $0.042 / 1M input tokens（output 免费） | **官方自测** | TypeSafe 官方定价页 |
| 速度优势 | 193.6× 更快 | **官方自测** | 同上，参照系 GPT-6 Astra + Fable 5.1 平均 |
| 成本优势 | 444.6× 更便宜 | **官方自测** | 同上 |
| 第三方复现实测提升 | 20–24% | **第三方** | AGI Hunt 汇总（与官方自测量级差异巨大） |
| 结构化输出错误率 | 0% | **口径说明：schema 保证，非经验实测** | 由 typed questions 约束返回形状，**答案仍可能错**，只是格式不会错 |

**结论**：官方数字与第三方实测之间差一个数量级（193.6× vs 20–24%）。本调研在
引用任何官方数字时一律带「官方自测」标签，不允许把厂商自测当作实测结论写进落点判断。

---

## 6. 为什么官方 API 不能作为 laos 运行时依赖

四条，逐条给出处：

| # | 理由 | 出处 |
|---|---|---|
| 1 | **闭源，无权重**——架构、参数量、权重均未公开，无法自托管或审计 | Global Constraints 1（执行前核实） |
| 2 | **无自托管选项**——只有早期访问 waitlist 的云端 API | 同上 |
| 3 | **未向中国大陆开放**——央广网 2026-09-20 报道 APUS 复现时明确提及；laos 用户多在中国大陆 | 央广网 2026-09-20 |
| 4 | **laos 架构要求本地优先**——Android + proot Ubuntu，隐私红线（不存声纹、情绪非临床）、`mic.*` syscall 审计 | laos/kernel.py、Global Constraints 6–7 |

**推论**：官方 API 在本调研里**只能作参考基线**，不得进入任何运行时依赖。端侧可行性
必须由实测（Task 4）而非 README 宣称决定。任何「云端 API wrapper」即使 star 很高，
在 laos 落点标签里也标 `unrelated`。

---

## 7. 12 列 schema 与各列填写规则

列名**逐字照抄**，Task 2/3/4/5/6 全部按名消费：

```
["项目", "类别", "星数", "语言", "许可", "运行时依赖",
 "端侧可跑", "原语", "报告延迟", "laos 落点", "验证状态", "来源"]
```

| 列 | 取值 / 规则 |
|---|---|
| 项目 | 仓库全名 `owner/repo` 或产品名 |
| 类别 | 见 §8 裁定：{官方 / 客户端 / 复现 / 复现(单token打分) / 应用 / 清单 / 评测 / 工具}（子串匹配，`复现(单token打分)` 凭「复现」通过） |
| 星数 | 整数；查不到写 `未知` |
| 语言 | 实现语言，如 Python / Rust / TypeScript；查不到写 `未知` |
| 许可 | 必须非空；查不到写 `未知` |
| 运行时依赖 | **只接受 `torch` / `onnx` / `rust` / `llama.cpp` / `云端API` / `未知`**，不许写「轻量」之类模糊词 |
| 端侧可跑 | `yes` / `no` / `unknown(未实测)` |
| 原语 | 该项目用到的原语：Choice / Score / Noul / 组合；不适用写 `-` |
| 报告延迟 | 数字必须带单位（`ms` / `s` / `µs`）**且**标数据源：`官方自测` / `第三方` / `未实测` |
| laos 落点 | 四段漏斗里的落点，如 漏斗①触发 / 漏斗③蒸馏 / 记忆召回 / 上下文压缩 / 不值得 |
| 验证状态 | `已实测` / `已读代码` / `仅 README` / `未核实` |
| 来源 | 必须含 `github.com` / `arxiv.org` / `huggingface.co` 之一 |

四条 Jev 专属校验规则（代码见 `scripts/check_jev_table.py`）：

- **g `rule_category`**：类别必须落在枚举内，杜绝自由发挥。
- **h `rule_runtime_dep`**：运行时依赖必须点名上述关键字，不许写「轻量」。
- **i `rule_edge_conflict`**：`端侧可跑=yes` 时依赖不得含 `云端API`（本调研最易犯的错）。
- **j `rule_latency`**：延迟数字必须带单位且标数据源。

---

## 8. 候选池（起点线索，逐条核实后方可入表）

以下为执行前人工实测（2026-09-21）抓到的仓库，**星数为实测值，但许可 / 依赖 / 延迟
一律 `[待核实]`**。按六条线列示；其中「单 token 打分」类（借用现成 LM 首 token logits）
已在条目后用 `（单token打分）` 标出，对应 §9 裁定。

**官方与客户端**
- `browser-use/jev-ultrafast`(11069★) `[待核实]`
- `typesafe-ai/skills` `[待核实]`
- `jkudish/jev-mcp`(147★) `[待核实]`
- `jkudish/jev-browser`(179★) `[待核实]`
- `itsmostafa/typesafe-mcp`(131★) `[待核实]`
- `dabit3/jev-experiments`(328★) `[待核实]`
- `dbreunig/building-with-jev-skill`(124★) `[待核实]`

**开源复现（端侧候选，最关键的一条线）**
- `yzfly/edgejev`(2★，**README 称 CPU 单题 15.6 ms、模型 324 MB、运行时不依赖 torch**) `[待核实]`
- `wfzyx/von`(116★，Apache-2.0，称 sub-15ms 非自回归) `[待核实]`
- `Heman10x-NGU/openJev-verdict-2.0`(151★，ModernBERT 151M，称 77.10% acc / Brier 0.0636) `[待核实]`
- `Heman10x-NGU/Verdict-open-jev`(33★) `[待核实]`
- `receptron/laya`(8★) `[待核实]`
- `aovestdipaperino/laya-rust`(1★，**纯 Rust 推理**) `[待核实]`
- `jaredpalmer/kev`(800★，Apache-2.0，Qwen2.5-0.5B 可自训练) `[待核实]`
- `TianyuCodings/NanoJev`(1303★，MIT) `[待核实]`
- `Yinsongxu/LLM2Jev`(60★，Apache-2.0) `（单token打分）` `[待核实]`
- `zhihz/openjev`(19★，双语) `[待核实]`
- `kshetrajna12/reflex`(84★，MIT，Qwen3.5) `[待核实]`
- `logan-markewich/jeff`(155★，自托管 drop-in) `[待核实]`
- `featherless-ai/simple-jev`(371★) `（单token打分）` `[待核实]`
- `Argos1111/jev_local`(16★) `[待核实]`
- `intikhab49/open-jev-typed-decision-engine`(5★) `[待核实]`
- `mkeco/Cerebellum-2B` `[待核实]`
- `TheoLeeCJ/SemIf`(2281★) `[待核实]`

**语音 / 音频 + Jev（与 laos 最贴近的先例）**
- `moritzkremb/jev-voice-browser`(146★) `[待核实]`
- `kevinbadi/jev-voice`(37★，**local whisper.cpp + one Jev call**) `[待核实]`
- `chasemc67/Jevis`(1★，**Jev-filtered always-on speech input: mic → STT → Jev → text**) `[待核实]`
- `sgaabdu4/capture`(2★，Private Mac voice diary: 本地 Parakeet 转写 + Jev 分类) `[待核实]`
- `nikotaronosuke/jev-voice-decision`(0★) `[待核实]`
- `santos-sanz/jev-audio-beeper`(1★) `[待核实]`
- `winter-loo/jev-voice-browser`(0★) `[待核实]`

**Android / 移动端**
- `droidrun/mobile-jev`（官方引用，真机驱动 Uber：9 动作约 21 s，**未完成下单**）`[待核实]`
- `ufec/jev-block-android-ad`(3★，JevNoiseGate 过滤通知/短信) `[待核实]`
- `antiyro/jevdroid`(3★，ADB + typed Python) `[待核实]`
- `Friedjof/jev-mobile`(2★) `[待核实]`
- `dougsong/jev-android`(1★，**Kotlin Android SDK**) `[待核实]`

**清单与评测**
- `yibie/awesome-jev`(539★) `[待核实]`
- `Anil-matcha/awesome-jev-by-typesafe`(680★) `[待核实]`
- `v-modal/awesome-jev-tools`(510★) `[待核实]`
- `cobanov/awesome-jev`(247★) `[待核实]`
- `AbdelStark/awesome-typesafe`(380★) `[待核实]`
- `fstandhartinger/jevbench`(18★) `[待核实]`
- `AbdelStark/jev-benchmarks`(12★) `[待核实]`
- `wondertwins/jev-benchmark` `[待核实]`

**其他应用**
- `kerpopule/hermes-jev-skills`(195★，**Jev 驱动的 model routing / memory / compaction / skill selection**) `[待核实]`
- `tamaratran/fast-jev-compaction`(4868★) `[待核实]`
- `leepokai/jev-guard`（deny/ask/allow）`[待核实]`
- `realZachi/pg-jev`(236★) `[待核实]`
- `superagents-lab/jev-search`(284★) `[待核实]`
- `devagrawal09/jev-review`(396★) `[待核实]`
- `thruwire/foreman`(422★) `[待核实]`
- `APUS-AI-Lab/fast-browser-use`(15★，MIT，Qwen3.5-9B 本地) `（单token打分）` `[待核实]`
- `ChetasLua/jevmeter` `[待核实]`
- `AboveColin/HA-Jev` `[待核实]`
- `jarrodwatts/jev-trader`(1453★) `[待核实]`

---

## 9. 「端到端复现 vs 借用范式」口径裁定（最关键的一条）

Jev 生态里混着**两类完全不同的东西**，在「是否需要训练」「延迟构成」「校准性」上
截然不同。**不区分会得出「端侧跑 Jev 只要 15 ms」的错结论。**

| 类 | 是什么 | 代表 | 是否需要训练 | 延迟构成 | 校准性 |
|---|---|---|---|---|---|
| (a) **真复现** | 自己重新训练出**非自回归决策头** | `wfzyx/von`、`Heman10x-NGU/openJev-verdict-2.0`、`jaredpalmer/kev` | 是（需自训/提供权重） | 推理一次 | 有（分布形状可校准） |
| (b) **借用范式** | 只把现有 LM 的**首个 token logits** 拿来当打分 | `APUS-AI-Lab/fast-browser-use`、`featherless-ai/simple-jev`、`Yinsongxu/LLM2Jev` | 否（依赖现成 LM） | LM 前向 + 取首 token | 弱（受基座 LM 校准影响） |

**落表规则**：表格「类别」列必须区分——前者记 `复现`，后者记 `复现(单token打分)`。
「15 ms」通常来自 (b) 类（现成 LM 单 token 前向），**不能外推到 (a) 类端侧复现的
真实延迟**；Task 4 实测会以 (a) 类为核心，避免被 README 宣称误导。

---

## 10. 口径裁定记录（执行过程中产生）

### 裁定 J1：`table_lint.check_text` 表头触发列硬编码「模型」，Jev 表需触发列可变副本
`scripts/table_lint.py` 第 110 行将 schema 表的识别条件写成 `cells[0] == "模型"`，
而本调研 12 列 schema 以「项目」开头。若直接调 `table_lint.run_cli` / `check_text`，
**整张 Jev 表会被跳过、零校验**（静默失效，比报错更危险）。
裁定：`scripts/check_jev_table.py` 复用 `table_lint` 的 `Violation` / `split_row` /
`is_separator` / `PLACEHOLDERS` / `SOURCE_HOSTS`，但维护一份触发列可变的 `check_text`
副本；**不修改 `table_lint.py`**。

### 裁定 J2：通用规则 params / metric 在 Jev schema 下天然 inert
`table_lint` 的通用规则 b(params)、e(metric) 依赖「参数量(M)」「指标」两列，Jev 12 列
里没有，因此不会触发。Jev 可触发的通用规则为 `cols` / `source` / `license` /
`placeholder` 四类 + 4 条 Jev 专属规则；再加 `schema` 表头错配，selftest 共覆盖
**9 类**违规，与计划「九类反例各命中」对齐。params / metric 两类不适用，不强行断言。

### 裁定 J3：`rule_category` 用子串匹配容纳「复现(单token打分)」
类别合法枚举为 {官方 / 客户端 / 复现 / 应用 / 清单 / 评测 / 工具}，不含
「复现(单token打分)」。裁定：规则用 `any(k in v for k in OK)` 子串匹配，使
"复现(单token打分)" 凭 "复现" 通过——既允许真复现、也允许单 token 打分两类都合法，
同时杜绝枚举外的自由发挥。

### 裁定 J4：`Violation` 实际签名是四参，计划骨架为笔误
计划 Task 1 Step 1 的 `Violation(lineno, "rule", "detail")` 是三参，但
`table_lint.Violation.__init__(path, line, rule, detail)` 是四参。裁定：按真实签名
修正为 `Violation("<jev>", lineno, "rule", "detail")`，第一参占位串由 `check_text`
统一覆写为真实文件名，保证 `file:line` 可直接跳转。**不修改 `table_lint.py`**。

---

> 交叉校验语料（非本文件结论来源，供后续 Task 复核）：
> `docs/research/corpus/jev_repos_curated.json`（30 条精选）、
> `docs/research/corpus/jev_repos.json`。
