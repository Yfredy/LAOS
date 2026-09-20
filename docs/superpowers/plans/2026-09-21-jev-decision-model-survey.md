# Jev 决策模型调研与 laos 落点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 摸清 TypeSafe Jev（System One 类型化决策模型）的技术实质与开源生态全景，并判定它有哪些部分值得在 laos 常驻音频 Agent 的四段漏斗里落地——产出可复核的项目清单与带判据的落点设计，而不是一份印象式综述。

**Architecture:** 分两个 Part。Part 1（Task 1–4）建口径、抓 GitHub 全景、分类、**实测端侧候选的真实可跑性**；Part 2（Task 5–6）把 laos 现有的判定点逐个映射到 Jev 的三个原语（Choice / Score / Noul），给出成本-收益表与排除理由，最后出报告与 HTML。两条判断贯穿全程：**官方云端 API 不可作为 laos 运行时依赖**（闭源、无权重、中国大陆未开放、laos 要求本地优先），因此端侧可行性必须由实测而非 README 宣称决定。

**Tech Stack:** Python 3.11（`C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe`）、GitHub Search API（限额 10 次/分钟，单 query 上限 1000 条）、既有 `scripts/crawl_oss_repos.py`（14 字段 schema，支持引号短语检索）、既有 `scripts/table_lint.py`（共享校验核心）、Git。

**Spec:** 本计划自带全部实测事实，无需外部 spec。相关联的既有调研：`docs/research/speech-emotion/`（SER，46 条，已定「3 档 × 2 标记」口径）、`docs/research/audio-events/`（AED）、`docs/research/auto-gain/`（AGC）。

## Global Constraints

1. **Jev 官方是闭源云端 API**：`POST https://api.typesafe.ai/v1/systemone`，早期访问 waitlist，**未公开架构、参数量、权重，无自托管选项**。定价 $0.042/1M input tokens，output 免费；官方称端到端 70–500 ms。
2. **Jev 服务未向中国大陆开放**（央广网 2026-09-20 报道 APUS 复现时明确提及）。laos 用户在中国境内 → **官方 API 只能作参考基线，不得成为运行时依赖**。
3. **三个原语的返回形状**（照抄官方口径，不得改写）：`Choice` → `choice` + `probabilities` + `confidence`（最多 255 选项）；`Score` → `score` + `legend` + `probabilities` + `confidence`（可落在两个等级之间）；`Noul` → `noul`（0–1 概率，**无独立 confidence**）。三个原语可在一次请求内**并行且隔离**求值，加题几乎不增延迟。
4. **confidence 来自概率分布形状**，不是胜出选项的概率。官方示例：billing 0.84 但 confidence 仅 0.596（technical 仍占 0.159）。官方建议三档处置：高置信自动执行 / 中等入复核 / 低置信转人工，阈值按错判代价缩放。
5. **官方性能数字是厂商自测**：193.6× 更快 / 444.6× 更便宜来自 TypeSafe 自己的 workflow evals（参照系是 GPT-6 Astra 与 Fable 5.1 的平均）。第三方复现实测只有 **20–24%** 提升（AGI Hunt 汇总）。**任何引用官方数字处必须标注 `官方自测`。**
6. **laos 部署环境**：Android + proot Ubuntu（完整 glibc aarch64，manylinux wheel 可直接装），**拿不到 NPU**，只能 CPU 推理，空闲功耗 400–1000 mW 量级；裸 Termux 是 Bionic libc，torch 缺 `libgomp.so.1`。
7. **laos 隐私红线**：不存声纹；情绪标签非临床用途；`mic.*` syscall 在 `laos/kernel.py` 内被强制审计。
8. **GitHub API 限额**：search 端点约 10 次/分钟，单 query 上限 1000 条；`core` 端点配额极易耗尽，**只用 search**。
9. **环境坑（Windows Git Bash）**：`dirname` / `cd` / `ls` / `head` / `tail` 全部 command not found；反引号被当命令替换；`-c` 内联时双引号嵌套会破坏传参（复杂脚本先写临时文件再跑）。一律绝对路径调 python 并加 `-u`；文件读写一律 UTF-8。
10. **不得修改** `docs/research/speech-emotion/`、`audio-events/`、`auto-gain/`、`docs/research/oss/` 下任何既有文件，也不得修改 `scripts/table_lint.py` 或 `scripts/crawl_oss_repos.py`。
11. **不许编造 star 数、延迟或许可**。查不到就写 `未知` 并在「验证状态」列标 `未核实`。

---

## Part 1 · 知识与生态普查

### Task 1: Jev 口径文件与校验器

**Files:**
- Create: `docs/research/jev/00-taxonomy-and-metrics.md`
- Create: `scripts/check_jev_table.py`
- Reference（只读，不得修改）: `scripts/table_lint.py`、`scripts/check_ser_table.py`

**Interfaces:**
- Consumes: `table_lint.check_text(text, columns, source, extra_rules)` / `table_lint.run_cli(...)`
- Produces: 12 列 schema `COLUMNS`（见下），供 Task 2/3/5 全部表格消费；`scripts/check_jev_table.py` 供 Task 3/5 验证

- [ ] **Step 1: 写 12 列 schema 的失败测试**

先读 `scripts/table_lint.py` 确认接口，再在 `scripts/check_jev_table.py` 里内置 `--selftest`。测试用反例必须覆盖 6 类违规：`params` / `source` / `license` / `metric` / `placeholder`（通用五条）+ 4 条 Jev 专属规则：

```python
# scripts/check_jev_table.py
COLUMNS = ["项目", "类别", "星数", "语言", "许可", "运行时依赖",
           "端侧可跑", "原语", "报告延迟", "laos 落点", "验证状态", "来源"]

def rule_category(row, lineno):
    """规则 g：类别必须落在枚举内，杜绝自由发挥。"""
    v = row.get("类别", "")
    OK = ("官方", "客户端", "复现", "应用", "清单", "评测", "工具")
    if not any(k in v for k in OK):
        return [Violation(lineno, "category", "类别必须含 %s 之一，当前=%r" % ("/".join(OK), v))]
    return []

def rule_runtime_dep(row, lineno):
    """规则 h：运行时依赖不许写模糊词，必须点名。"""
    v = row.get("运行时依赖", "")
    OK = ("torch", "onnx", "rust", "云端API", "llama.cpp", "未知")
    if not any(k in v for k in OK):
        return [Violation(lineno, "runtime-dep",
                          "运行时依赖必须点名 %s 之一（不许写'轻量'），当前=%r" % ("/".join(OK), v))]
    return []

def rule_edge_conflict(row, lineno):
    """规则 i：端侧可跑=yes 时，运行时依赖不得含云端API（本调研最易犯的错）。"""
    if row.get("端侧可跑", "").strip() == "yes" and "云端API" in row.get("运行时依赖", ""):
        return [Violation(lineno, "edge-conflict", "端侧可跑=yes 但依赖云端API，矛盾")]
    return []

def rule_latency(row, lineno):
    """规则 j：延迟数字必须带单位 + 必须标数据源（官方自测/第三方/未实测）。"""
    import re
    v = row.get("报告延迟", "")
    if re.search(r"\d", v):
        if not re.search(r"\d+\s*(ms|s|µs)", v):
            return [Violation(lineno, "latency", "延迟缺单位：%r" % v)]
        if not any(k in v for k in ("官方自测", "第三方", "未实测")):
            return [Violation(lineno, "latency", "延迟未标数据源（官方自测/第三方/未实测）：%r" % v)]
    return []
```

- [ ] **Step 2: 跑 selftest 确认失败**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\check_jev_table.py --selftest`
Expected: FAIL，九类反例各命中一次；同时确认非目标表（列数 < 10 的对照表）不误伤。

- [ ] **Step 3: 实现 CLI**

用 `run_cli(COLUMNS, extra_rules=[rule_category, rule_runtime_dep, rule_edge_conflict, rule_latency])` 组装，参考 `check_ser_table.py` 的骨架但**不复制其 SELFTEST 文本**。

- [ ] **Step 4: 跑 selftest 确认通过**

Expected: 输出 PASS。若 `table_lint` 缺 `Violation` 导出，改为从 `table_lint` 实际导出名导入（先 `import table_lint; print(dir(table_lint))` 确认），**不要修改 `table_lint.py`**。

- [ ] **Step 5: 写 `00-taxonomy-and-metrics.md`**

必须包含：

1. 文件头：本文件是 `docs/research/jev/` 下所有文件的唯一口径来源，schema 由 `check_jev_table.py` 机器校验。
2. **Jev 是什么 / 不是什么**：System One（Kahneman 快慢分工）决策模型；transformer-based 但**不生成文本**；非自回归 + 并行采样器；训练方法 RLCD（Reinforcement Learning for Calibrated Decisions，对标 RLHF）。与「小 LLM」的区别是**输出空间在推理前就被定义**，不是参数量差别。
3. **三原语表**：Choice / Score / Noul，各列「问什么 / 返回什么 / 典型用途」。写明 Noul 无独立 confidence。
4. **state + typed questions 的请求形状**：给一个完整 JSON 请求/响应示例（state + model + questions，answers 含 probabilities 与 confidence）。
5. **confidence 的语义与三档处置**（高/中/低，阈值按错判代价缩放），并解释示例里 0.84 vs 0.596 的由来。
6. **官方数字的可信度分级表**：延迟 70–500 ms、$0.042/1M、193.6×/444.6×、0% 结构化输出错误 → 逐条标注 `官方自测` / `第三方` / `口径说明`。特别写明「0% 结构化错误」是 schema 保证而非经验实测，**答案仍可能错**。
7. **为什么官方 API 不能作为 laos 运行时依赖**：闭源 / 无自托管 / 中国大陆未开放 / laos 本地优先四条，逐条给出处。
8. **12 列 schema 与各列填写规则**。关键列定义：
   - `运行时依赖`：只接受 `torch` / `onnx` / `rust` / `llama.cpp` / `云端API` / `未知`，**不许写「轻量」**。
   - `端侧可跑`：`yes` / `no` / `unknown(未实测)`。
   - `报告延迟`：数字必须带单位并标 `官方自测` / `第三方` / `未实测`。
   - `验证状态`：`已实测` / `已读代码` / `仅 README` / `未核实`。
9. **候选池（起点线索，逐条核实后方可入表）**：把下面这些已由我在 2026-09-21 实测到的仓库按四条线列出，**每条后跟 `[待核实]`**（星数为实测值，但许可/依赖/延迟一律待核实）：

   - 官方与客户端：`browser-use/jev-ultrafast`(11069★)、`typesafe-ai/skills`、`jkudish/jev-mcp`(147★)、`jkudish/jev-browser`(179★)、`itsmostafa/typesafe-mcp`(131★)、`dabit3/jev-experiments`(328★)、`dbreunig/building-with-jev-skill`(124★)
   - 开源复现（端侧候选，最关键的一条线）：`yzfly/edgejev`(2★，**README 称 CPU 单题 15.6 ms、模型 324 MB、运行时不依赖 torch**)、`wfzyx/von`(116★，Apache-2.0，称 sub-15ms 非自回归)、`Heman10x-NGU/openJev-verdict-2.0`(151★，ModernBERT 151M，称 77.10% acc / Brier 0.0636)、`Heman10x-NGU/Verdict-open-jev`(33★)、`receptron/laya`(8★)、`aovestdipaperino/laya-rust`(1★，**纯 Rust 推理**)、`jaredpalmer/kev`(800★，Apache-2.0，Qwen2.5-0.5B 可自训练)、`TianyuCodings/NanoJev`(1303★，MIT)、`Yinsongxu/LLM2Jev`(60★，Apache-2.0)、`zhihz/openjev`(19★，双语)、`kshetrajna12/reflex`(84★，MIT，Qwen3.5)、`logan-markewich/jeff`(155★，自托管 drop-in)、`featherless-ai/simple-jev`(371★)、`Argos1111/jev_local`(16★)、`intikhab49/open-jev-typed-decision-engine`(5★)、`mkeco/Cerebellum-2B`、`TheoLeeCJ/SemIf`(2281★)
   - 语音/音频 + Jev（与 laos 最贴近的先例）：`moritzkremb/jev-voice-browser`(146★)、`kevinbadi/jev-voice`(37★，**local whisper.cpp + one Jev call**)、`chasemc67/Jevis`(1★，**Jev-filtered always-on speech input harness: mic → STT → Jev → text**)、`sgaabdu4/capture`(2★，Private Mac voice diary: 本地 Parakeet 转写 + Jev 分类)、`nikotaronosuke/jev-voice-decision`(0★)、`santos-sanz/jev-audio-beeper`(1★)、`winter-loo/jev-voice-browser`(0★)
   - Android / 移动端：`droidrun/mobile-jev`（官方引用，真机驱动 Uber：9 动作约 21 s，**未完成下单**）、`ufec/jev-block-android-ad`(3★，JevNoiseGate 过滤通知/短信)、`antiyro/jevdroid`(3★，ADB + typed Python)、`Friedjof/jev-mobile`(2★)、`dougsong/jev-android`(1★，**Kotlin Android SDK**)
   - 清单与评测：`yibie/awesome-jev`(539★)、`Anil-matcha/awesome-jev-by-typesafe`(680★)、`v-modal/awesome-jev-tools`(510★)、`cobanov/awesome-jev`(247★)、`AbdelStark/awesome-typesafe`(380★)、`fstandhartinger/jevbench`(18★)、`AbdelStark/jev-benchmarks`(12★)、`wondertwins/jev-benchmark`
   - 其他应用：`kerpopule/hermes-jev-skills`(195★，**Jev 驱动的 model routing / memory / compaction / skill selection**)、`tamaratran/fast-jev-compaction`(4868★)、`leepokai/jev-guard`（deny/ask/allow）、`realZachi/pg-jev`(236★)、`superagents-lab/jev-search`(284★)、`devagrawal09/jev-review`(396★)、`thruwire/foreman`(422★)、`APUS-AI-Lab/fast-browser-use`(15★，MIT，Qwen3.5-9B 本地)、`ChetasLua/jevmeter`、`AboveColin/HA-Jev`、`jarrodwatts/jev-trader`(1453★)

10. **「端到端复现 vs 借用范式」的口径裁定**：Jev 生态里有两类东西——(a) 真正重新训练出非自回归决策头的（如 `von` / `openJev-verdict` / `kev`）；(b) 只是把现有 LM 的**首个 token logits** 拿来当打分的（如 `fast-browser-use` / `simple-jev` / `LLM2Jev`）。二者在「是否需要训练」「延迟构成」「校准性」上完全不同，**必须在表格里用 `类别` 列区分**（前者记 `复现`，后者记 `复现(单token打分)`），不区分会得出「端侧跑 Jev 只要 15 ms」的错结论。

- [ ] **Step 6: Commit**

```bash
git add docs/research/jev/00-taxonomy-and-metrics.md scripts/check_jev_table.py
git commit -m "docs(jev): System One taxonomy, 12-col schema and validator"
```

---

### Task 2: GitHub 全景抓取与去噪

**Files:**
- Create: `docs/research/jev/repos_raw.jsonl`
- Create: `docs/research/jev/fetch_summary.md`
- Consume（只读调用，不得修改）: `scripts/crawl_oss_repos.py`

**Interfaces:**
- Consumes: `crawl_oss_repos.search(query, pages)` / `crawl_oss_repos.parse_repo(item)`（14 字段；**先读该文件确认真实签名再调用**，若签名不同以实际为准）
- Produces: `repos_raw.jsonl`，每行一个 repo JSON，供 Task 3 分类消费

- [ ] **Step 1: 确认抓取器接口**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u -c "import sys; sys.path.insert(0, r'C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts'); import crawl_oss_repos as m; print([n for n in dir(m) if not n.startswith('_')])"`
Expected: 打印出 `search` / `parse_repo` 等函数名。**若实际签名与本计划假设不符，以实际为准并在汇报中说明。**

- [ ] **Step 2: 用引号短语 query 批量抓取**

Jev 是新兴词，裸词检索会混入 `jevil` / `Jevons` / `jevent` 等噪声（已在探测中观察到 `vs-jevil-android-port`、`JEVAN-BINDU-ANDROID` 这类误命中）。**必须用引号短语 + topic 限定**。query 清单：

```python
QUERIES = [
    'jev in:name',
    '"jev" in:description',
    '"typesafe" in:name,description',
    '"system one" decision model',
    '"decision model" in:description',
    'topic:jev',
    'topic:typesafe',
    '"typed decisions"',
    '"non-autoregressive" decision',
    'jev-ultrafast',
]
```

每个 query 取 3 页（300 条），间隔 ≥7 秒（10 次/分钟限额）。10 query × 3 页 ≈ 30 请求 ≈ 4 分钟，**后台运行**。

- [ ] **Step 3: 去重与去噪**

按 `full_name` 去重。去噪判据（**写进 `fetch_summary.md`，不许主观挑**）：
- 保留：name / description / topics 任一命中 `jev`、`typesafe`、`system one`、`system-1`、`typed decision`、`decision model` 之一（大小写不敏感）。
- 剔除：仅姓氏/人名/无关词命中（如 `jevons`、`jevil`、`jevent`、`Jevgenija`），且 topics 与 description 均无上述词。
- 单独记录被剔除条目到 `docs/research/jev/noise_dropped.jsonl`，便于复核。

- [ ] **Step 4: 生成抓取摘要**

统计并写入 `fetch_summary.md`：总条数、star 分布（≥10000 / 1000–9999 / 100–999 / <100）、语言 top10、许可 top10、star Top20 榜单（带 description）。

- [ ] **Step 5: 抽查 5 条真实性**

任取 Top20 中 5 条，用浏览器打开 `html_url` 核对 star 数与描述。**若某条 star 数差异 >10%，说明抓取时间或去重有问题**，回 Step 2 排查。

- [ ] **Step 6: Commit**

```bash
git add docs/research/jev/repos_raw.jsonl docs/research/jev/fetch_summary.md docs/research/jev/noise_dropped.jsonl
git commit -m "docs(jev): GitHub census of jev/typesafe/decision-model repos with denoise log"
```

---

### Task 3: 分类、入表与端侧初筛

**Files:**
- Create: `scripts/classify_jev.py`
- Create: `docs/research/jev/repos_classified.jsonl`
- Create: `docs/research/jev/01-official-and-clients.md`
- Create: `docs/research/jev/02-oss-reproductions.md`
- Create: `docs/research/jev/03-oss-applications.md`

**Interfaces:**
- Consumes: `repos_raw.jsonl`（Task 2）
- Produces: `repos_classified.jsonl`（追加 `category` / `laos_fit` / `fit_notes` / `verify_state` 四字段），供 Task 5 消费

- [ ] **Step 1: 写分类脚本**

`classify()` 规则必须可解释、可复现（读 `topics` / `description` / `full_name`），输出 `category` ∈ {`官方`, `客户端`, `复现`, `复现(单token打分)`, `应用`, `清单`, `评测`, `工具`}。判据示例：

```python
def classify(r):
    n = (r.get("full_name") or "").lower()
    d = (r.get("description") or "").lower()
    t = " ".join(r.get("topics") or []).lower()
    blob = n + " " + d + " " + t
    if "awesome" in n or "curated" in d or "list of" in d:
        return "清单"
    if any(k in blob for k in ("benchmark", "eval", "brier", "calibration")):
        return "评测"
    # 复现：自己训了决策头 / 非自回归 / 可自托管
    if any(k in blob for k in ("non-autoregressive", "replica", "reproduc", "drop-in",
                               "open-source system one", "open alternative", "re-creation",
                               "train and run", "alternative to")):
        return "复现"
    # 复现(单token打分)：借用现成 LM 的首 token logits
    if any(k in blob for k in ("single-token", "logits", "turn any open model",
                               "adapt local", "first token", "reflex")):
        return "复现(单token打分)"
    if any(k in blob for k in ("mcp", "sdk", "client", "skill")):
        return "客户端"
    if any(k in blob for k in ("browser", "voice", "android", "guard", "triage",
                               "routing", "compaction", "agent")):
        return "应用"
    return "工具"
```

- [ ] **Step 2: 打 laos 落点标签**

`laos_fit` ∈ {`core`（可直接落地）/ `ref`（有参考价值）/ `unrelated`}。判据落到 laos 的硬约束：能否端侧 CPU 跑、是否依赖云端 API、许可是否允许自托管、是否与音频/常驻场景相关。**宁可严格不要灌水**——云端 API wrapper 即使 star 很高也标 `unrelated` 并在 `fit_notes` 写明理由。

- [ ] **Step 3: 写三份分档文档**

每份含一张 12 列表（列名逐字照抄 Task 1 的 schema）：
- `01-official-and-clients.md`：TypeSafe 官方、SDK、MCP、agent skill
- `02-oss-reproductions.md`：**本次调研的核心文档**。每条复现必须回答四个问题：是否真非自回归 / 基座模型与参数量 / 是否需要自训练 / 许可。区分 `复现` 与 `复现(单token打分)`。
- `03-oss-applications.md`：browser / voice / android / guard / routing / compaction 等应用，重点标出**语音 + 常驻**类先例（`chasemc67/Jevis`、`sgaabdu4/capture`、`kevinbadi/jev-voice`）。

- [ ] **Step 4: 跑校验器**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\check_jev_table.py C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\jev\01-official-and-clients.md C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\jev\02-oss-reproductions.md C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\jev\03-oss-applications.md`
Expected: 0 违规。若报违规，**修表不改规则**（除非能证明规则误伤真实内容，此时按 Task 1 的方式记录裁定）。

- [ ] **Step 5: Commit**

```bash
git add scripts/classify_jev.py docs/research/jev/repos_classified.jsonl docs/research/jev/01-official-and-clients.md docs/research/jev/02-oss-reproductions.md docs/research/jev/03-oss-applications.md
git commit -m "docs(jev): classify ecosystem into official/reproduction/application with laos fit"
```

---

### Task 4: 端侧候选实测（决定是否值得用的关键）

**Files:**
- Create: `scripts/bench_jev_local.py`
- Create: `docs/research/jev/04-ondevice-benchmark.md`

**Interfaces:**
- Consumes: `02-oss-reproductions.md` 的候选清单（Task 3）
- Produces: 实测延迟/内存数字，供 Task 5 的落点可行性判据使用

- [ ] **Step 1: 静态可行性预筛（不下载模型）**

对 Task 3 的每个 `复现` / `复现(单token打分)` 候选，读 README 回答：基座模型与参数量、是否需要自训练、运行时依赖（`torch` / `onnx` / `rust` / `llama.cpp`）、模型体积、是否提供权重。把「**不需要 torch**」的候选（`yzfly/edgejev`、`aovestdipaperino/laya-rust`）单列——它们对 proot 环境风险最低。

- [ ] **Step 2: 在本机 Windows CPU 上实测（不是 proot，写明外推假设）**

挑 **2–3 个**可跑的候选（优先 `yzfly/edgejev`，其次 `wfzyx/von`，第三 `Heman10x-NGU/Verdict-open-jev`）。脚本骨架：

```python
# scripts/bench_jev_local.py
import json, subprocess, sys, time, os, statistics

CANDIDATES = [
    {"repo": "yzfly/edgejev", "clone": "https://github.com/yzfly/edgejev.git"},
    {"repo": "wfzyx/von",     "clone": "https://github.com/wfzyx/von.git"},
]

def bench(fn, n=30):
    """跑 n 次取中位与 p95，返回 ms。首次调用不计入（含懒加载/权重初始化）。"""
    fn()                      # warmup
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t0) * 1000.0)
    xs.sort()
    return {"median_ms": round(statistics.median(xs), 2),
            "p95_ms": round(xs[int(0.95 * len(xs)) - 1], 2),
            "n": n}
```

**若某个候选装不上或跑不通，如实记录失败原因，不要跳过也不要伪造数字。** 这一步的真实结果比任何 README 宣称都重要。

- [ ] **Step 3: 外推到 proot aarch64（必须写明假设，不许含糊）**

给出三档估算并标明公式与假设来源：
- 常驻额外功耗：按「每天 N 次判断 × 单次能耗」估算，与 laos 既有的功耗阶梯对照（定制 ASIC 0.047–1 µW / 专用音频 NPU 140 µW / aDSP·Sensing Hub <1 mA / 通用 MCU·AP 26–50 mW / **通用 Linux 空闲 400–1000 mW** / 手机 NPU 持续 1–4 W）。
- 明确写：x86 Windows CPU 实测值 → aarch64 proot 的换算**没有可靠系数**，只是量级估计。

- [ ] **Step 4: 写 `04-ondevice-benchmark.md`**

含：候选对比表（12 列 schema）、实测原始数字、失败记录、外推估算与假设、**结论一句话**（端侧现在能不能跑、跑得起跑不起）。

- [ ] **Step 5: Commit**

```bash
git add scripts/bench_jev_local.py docs/research/jev/04-ondevice-benchmark.md
git commit -m "docs(jev): on-device feasibility benchmark of open reproductions"
```

---

## Part 2 · laos 落点设计

### Task 5: laos 判定点映射与落点清单

**Files:**
- Create: `docs/research/jev/05-laos-placement.md`
- Reference（只读）: `laos/vad.py`、`laos/memory.py`、`laos/risk.py`、`laos/skills.py`、`laos/context.py`、`laos/brain.py`、`laos/scheduler.py`、`drivers/drv_ear.py`、`drivers/drv_mic.py`

**Interfaces:**
- Consumes: Task 3 的分类结论 + Task 4 的实测数字
- Produces: 落点清单，供 Task 6 报告消费

- [ ] **Step 1: 列出 laos 现有的「魔法数字」判定点**

逐个打开上述文件，把**当前用硬阈值或朴素相似度代替判断**的地方列成表。已确认的起点（行号以实际文件为准）：

| 位置 | 当前判定 | 类型 |
|---|---|---|
| `laos/vad.py` `split_segments(threshold_dbfs=-35.0)` / `StreamingVAD.__init__` | 固定能量阈值 | 硬阈值 |
| `drivers/drv_mic.py` `mic_listen_start(threshold_db=-40.0)`、`split_on_silence(threshold_db=-40)` | 固定能量阈值 | 硬阈值 |
| `laos/memory.py` `bigram_jaccard(a,b)`、`MemoryStore.recall(query,k=5)` | bigram Jaccard 相似度 | 朴素相似度 |
| `laos/memory.py` `RECENCY_HALF_LIFE_DAYS = 14.0` | 固定半衰期 | 硬阈值 |
| `laos/skills.py` `SkillStore.match(query,k=3)`（走 `memory.recall`） | 同上 | 朴素相似度 |
| `laos/risk.py` `FleetLedger.can_admit()` → `remaining > reserve` | 布尔硬规则 | 硬阈值 |
| `laos/risk.py` `FleetLedger.multiplier`（由电池/温控外部给定） | 外部输入，无判断 | 空缺 |
| `laos/context.py` `_compact_if_needed()` / `_swap_out(victims)` / `_default_summarizer` | 按 token 窗口换出 | 硬阈值 |
| `laos/brain.py` `make_brain(**kwargs)` / `Brain.think` | 单一 brain，无路由 | 空缺 |
| `drivers/drv_ear.py` `ear_transcribe` (funasr SenseVoiceSmall) | 固定 ASR 通道 | 固定 |
| `laos/scheduler.py` `next_pid()` / `note_outcome(pid, ok)` | 优先级 + token 预算 | 规则调度 |

- [ ] **Step 2: 逐个映射到 Choice / Score / Noul**

每个判定点给出：换用哪个原语、state 里放什么、预期收益、**以及代价**（延迟、依赖、失效模式）。重点候选：

1. **漏斗① 触发判定**（`StreamingVAD` / `mic_listen_start`）：`Noul("这段是人声且值得记录")`，替代/叠加纯能量门。代价：常驻路径上每帧都要调模型 → **这是功耗风险最大的一条**，必须用 Task 4 的实测数字说明能不能承受，承受不了就改为「能量门先过，Jev 只在边界段二次确认」的两级结构。
2. **漏斗③ 蒸馏后的重要度**（`memory.remember` 之前）：`Score("这段内容对主人的长期价值", legend=[...])`，决定是否进长期记忆 vs 即焚。
3. **漏斗③ 记忆类别路由**：`Choice(kind)`，替代现在靠调用方自己传 `kind`。
4. **记忆召回**（`MemoryStore.recall`）：`Score` 替代 `bigram_jaccard`，或两级（Jaccard 召回 + Jev 精排）。
5. **记忆半衰期**（`RECENCY_HALF_LIFE_DAYS`）：由固定 14 天改为按 `Score` 分档。
6. **不可逆操作闸门**（`FleetLedger.can_admit`）：`Score("这次调用有多不可逆")` + confidence 三档处置（高=放行 / 中=记录待复核 / 低=要求确认）。**注意：`charge` 是按尝试计费且 kill 不退款，低置信度放行会直接烧预算**，这条必须写清。
7. **技能路由**（`SkillStore.match`）：`Choice` 替代文本相似。
8. **上下文压缩**（`_swap_out` / `_default_summarizer`）：`Noul("这条换出后会丢失关键信息")`，对标 `tamaratran/fast-jev-compaction`。
9. **Brain 路由**（`make_brain`）：`Choice` 选 brain，对标 `kerpopule/hermes-jev-skills`。

- [ ] **Step 3: 明确写出「不值得做」的部分及理由**

至少覆盖：
- 官方云端 API 进运行时（违反 Global Constraints 2/7）
- 为 laos 自训练一个决策头（成本与收益不匹配，除非 Task 4 证明现有复现全都不可用）
- 用 Jev 替代 ASR 或情绪模型本身（Jev 不生成文本，不是生成模型的替代品）
- 在漏斗①的每帧路径上无条件调用（功耗）

- [ ] **Step 4: 给出落地顺序（P0–P4）**

按「收益 ÷ 风险」排序，**P0 必须是离线/非实时路径上的**（例如记忆整理、压缩路由），把常驻实时路径留到实测数据足够之后。

- [ ] **Step 5: Commit**

```bash
git add docs/research/jev/05-laos-placement.md
git commit -m "docs(jev): map laos decision points to Choice/Score/Noul with cost-benefit"
```

---

### Task 6: 报告与 HTML 全景

**Files:**
- Create: `docs/research/2026-09-21-jev-decision-model-survey.md`
- Create: `docs/jev-decision-model.html`

**Interfaces:**
- Consumes: Task 1–5 全部产出
- Produces: 最终交付物

- [ ] **Step 1: 写报告**

**所有数字必须由脚本从 `repos_classified.jsonl` 与 `04-ondevice-benchmark.md` 真实统计得出，不得手编。** 必须包含：

1. 一句话结论（Jev 是什么、对 laos 值不值得、值得在哪）
2. **Jev 技术实质**：三原语、state/questions 模型、confidence 语义、与 LLM 的分工边界
3. **官方数字可信度**：厂商自测 vs 第三方实测（20–24%）的对照
4. **生态全景**：分类统计表（各类别条数 + star 中位数 + Top 项目）
5. **端侧可行性**：Task 4 实测表与结论
6. **laos 落点**：Task 5 的映射表与 P0–P4 顺序
7. **不值得做的部分**（Task 5 Step 3）
8. **口径裁定记录**（执行过程中产生的全部裁定，编号续接）
9. **未核实清单**：所有 `[待核实]` 与 `验证状态=未核实` 的条目汇总

- [ ] **Step 2: 写 HTML**

深色单文件、**零外部依赖（不引 CDN）**、sticky 导航。风格沿用 `docs/always-on-recording.html`——**先读它前 150 行**了解 CSS 变量、配色、字体、布局套路，照抄风格不照抄内容。板块：三原语示意图、请求/响应 JSON 示例、生态分类分布（内联 SVG）、端侧候选对比表、laos 四段漏斗落点图（内联 SVG）、P0–P4 路线。

**内联 SVG 每个形状必须显式设 `fill`**（已知坑：颜色类如 `c-purple` 未实现，不显式设 fill 会回退黑色，深色背景上看不见）。

- [ ] **Step 3: 校验两份文件的数字一致**

跑一次脚本比对 markdown 与 HTML 里的关键数字（总数、各类条数、Top star 值），**必须完全一致**。

- [ ] **Step 4: 跑全量校验**

Run: `C:\Users\yaoyue\.workbuddy\binaries\python\versions\3.11.9\python.exe -u C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts\check_jev_table.py C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\jev\*.md`
Expected: 0 违规。

- [ ] **Step 5: Commit**

```bash
git add docs/research/2026-09-21-jev-decision-model-survey.md docs/jev-decision-model.html
git commit -m "docs(jev): survey report and HTML panorama"
```

---

## Self-Review

**1. Spec 覆盖：** 用户要求「学习最新的 jev 知识」→ Task 1（口径文件含三原语/API/confidence/可信度分级）；「搜索所有的 jev 相关开源项目」→ Task 2（多 query 引号短语抓取 + 去噪）+ Task 3（分类入表）；「构思有什么值得在项目里面使用的地方」→ Task 4（端侧实测，提供可行性判据）+ Task 5（laos 判定点逐个映射 + P0–P4 + 不值得做的排除理由）；最终交付 → Task 6。三条要求均有对应 Task，无遗漏。

**2. 占位符扫描：** 无 TBD / TODO /「类似 Task N」/「实现时再定」。所有 URL、字段名、限额、星数来自 2026-09-21 实测；所有正则与判据给出完整定义；`laos` 的接口位置精确到文件与函数名。

**3. 类型一致性：** `COLUMNS` 的 12 个列名在 Task 1（schema 定义）、Task 3（三份分档文档的表格）、Task 4（benchmark 表）、Task 6（报告表）之间逐字一致；`category` 的 8 个取值与 Task 1 口径文件第 10 条（复现 vs 单 token 打分的区分）一致；`laos_fit` 三档在 Task 3 定义、Task 5 与 Task 6 消费；`verify_state` 四档与「未核实清单」小节呼应。`bench()` 返回的 `median_ms` / `p95_ms` / `n` 在 Task 4 Step 2 定义并被 Step 4 的表格消费。

**4. 已知风险（非计划缺陷，但执行者须知）：**
- Task 2 的抓取总量可能不足（GitHub search 单 query 上限 1000）。若去重后不足 200 条，属正常——Jev 是两周内新词，生态规模本就有限，**如实报告条数，不要为凑数放宽去噪判据**。
- Task 4 实测可能全数失败（新项目依赖常不完整）。此时 `04-ondevice-benchmark.md` 的结论应写「现有开源复现均未通过本机可跑性验证」，并把 Task 5 的 P0 降级为「先解决可跑性」，**不要跳过实测直接写落点建议**。
