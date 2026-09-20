# Jev 决策模型调研 —— 技术实质、开源生态与 laos 落点

> 调研日期：2026-09-21 ｜ 口径来源：`docs/research/jev/00-taxonomy-and-metrics.md` ｜ 校验器：`scripts/check_jev_table.py`
> 数据来源：GitHub Search API 全量抓取（1443 条原始 → 去噪 778 条）+ 本机端侧实测

---

## 1. 一句话结论

**Jev 值得在 laos 用，但只值得用在离线路径上——不是「接入一个更聪明的判定器」，而是把 laos 里 11 处硬阈值换成带校准度的打分，且必须共享单一常驻 session。**

拆成三句：

1. **值得用在哪**：laos 现有 11 个判定点全部是硬阈值或朴素相似度（`threshold_dbfs=-35.0`、`bigram_jaccard`、`RECENCY_HALF_LIFE_DAYS=14.0`、`remaining > reserve`）。Jev 的 `Choice`/`Score`/`Noul` 正好对应这些形状，且返回 `confidence`——这是硬阈值给不了的东西。
2. **不能怎么用**：**漏斗①常驻每帧调用被否决**（持续 0.5–1.5 W 附加，手机不可承受）。官方云端 API 也不可用（闭源、无自托管、未向中国大陆开放）。
3. **唯一的端侧可行方案**：`yzfly/edgejev`（ONNX int8，无 torch 依赖），实测 3 题批量 median **157.5 ms**。**但 README 宣称的 15.6 ms 是硬件特例，实测慢约 10×。**

---

## 2. Jev 技术实质

### 2.1 它是什么

TypeSafe AI 的 **System One** 决策模型（对标 Kahneman 快慢分工中的「快系统」）。transformer-based，但**不生成文本**——非自回归 + 并行采样器。训练方法 **RLCD**（Reinforcement Learning for Calibrated Decisions，对标 RLHF）。

**与「小 LLM」的本质区别不是参数量，而是输出空间在推理前就被定义。** LLM 从整个词表采样；Jev 从调用方给定的候选集里选。这是它能返回校准概率、且加题几乎不增延迟的原因。

### 2.2 三个原语

| 原语 | 问什么 | 返回 | 典型用途 |
|---|---|---|---|
| `Choice` | 从 N 个选项里选一个 | `choice` + `probabilities` + `confidence`（≤255 选项） | 分类、路由 |
| `Score` | 打几分 | `score` + `legend` + `probabilities` + `confidence`（**可落在两个等级之间**） | 重要度、风险度 |
| `Noul` | 是/否 | `noul`（0–1 概率，**无独立 confidence**） | 闸门、过滤 |

三个原语可在**一次请求内并行且隔离**求值。**加题几乎不增延迟**——这条直接决定了 laos 的架构（见 §7.3）。

### 2.3 confidence 的语义（最容易讲错的一点）

`confidence` 来自**概率分布形状**，不是胜出选项的概率。

官方示例：billing 拿到 **0.84**（最高），但 `confidence` 只有 **0.596**——因为 technical 仍占 0.159，分布不够"尖"。

三档处置（官方建议，阈值按错判代价缩放）：
- **高置信** → 自动执行
- **中等** → 入复核队列
- **低置信** → 转人工

> **裁定 J6**：`Noul` 原语**没有独立 confidence 字段**。laos 里凡用 `Noul` 的落点，"不可行/边界"判定只能靠 `noul` 阈值，**不得自行补 confidence 字段**。

### 2.4 与 LLM 的分工边界

| | LLM | Jev |
|---|---|---|
| 输出 | 自由文本 | 类型化决策 |
| 采样空间 | 整个词表 | 调用方给定候选集 |
| 返回校准概率 | 否 | 是 |
| 加题成本 | 线性 | 近乎为零 |
| 适合 | 生成、推理、改写 | 判定、路由、闸门 |

**Jev 不替代 LLM，也不替代 ASR 或情绪模型**——它不生成文本。

---

## 3. 官方数字的可信度分级

**这是本次调研的诚信底线：官方数字全部是厂商自测，与第三方实测差距巨大。**

| 官方宣称 | 实测/第三方 | 判定 |
|---|---|---|
| 端到端 **70–500 ms** | — | `官方自测` |
| $0.042 / 1M input tokens，output 免费 | — | `官方自测` |
| **193.6× 更快** | — | `官方自测`（参照系：GPT-6 Astra 与 Fable 5.1 的平均） |
| **444.6× 更便宜** | — | `官方自测`（同上） |
| — | **20–24% 提升** | `第三方`（AGI Hunt 汇总的复现实测） |
| **0% 结构化输出错误** | — | **schema 保证，非经验实测——答案仍可能错** |

**193.6× vs 20–24% 差了一个数量级。** 任何引用官方数字处必须标注 `官方自测`。

### 为什么官方 API 不能作为 laos 运行时依赖

| 理由 | 说明 |
|---|---|
| 闭源、无权重 | 无法自托管、无法审计 |
| 无自托管选项 | 违反 laos 本地优先架构 |
| **未向中国大陆开放** | 央广网 2026-09-20 报道 APUS 复现时明确提及；laos 用户在境内 |
| 定价与配额 | 常驻场景调用量不可控 |

---

## 4. 生态全景（778 条）

### 4.1 抓取与去噪

原始 **1443 条** → 字面判据 1399 → **精度判据 778 条**（剔除 **665 条**）。

**去噪是必需的**：Jev 是两周内新词，裸词检索会混入大量噪声。被剔除的例子：`KRLW890/jevil-simulator`（Jevil bossfight）、`grabbou/jevil`、`killme2008/jevent`（libevent for java）、`vs-jevil-android-port`、`JEVAN-BINDU-ANDROID`。

> **口径说明**：计划里的字面保留词 `typesafe` / `decision model` 太宽泛（会混进 trpc / TanStack / http4k / RestEase），已改用精度判据。用原口径得 1399 条、近半无关，审计副本保留在 `repos_raw_broad.jsonl`。

### 4.2 分类分布（8 类）

| 类别 | 条数 | star 中位数 | Top 项目 |
|---|---|---|---|
| 应用 | **344** | 2 | QuantDinger(11810)、fast-jev-compaction(4878)、jev-trader(1455) |
| 工具 | 201 | 7 | jevlike(1055)、Jev-cu(448)、jev-router(244) |
| 客户端 | 102 | 2 | jev-ultrafast(11101)、tinystruct(354)、jev-experiments(328) |
| **复现** | **42** | 2 | SemIf(2286)、NanoJev(1309)、laya-mlx(1114) |
| 评测 | 41 | 2 | laya-coreml(212)、cultivar(40)、typesafe-ai-benchmark(34) |
| 清单 | 36 | 12 | anything_about_game(4110)、awesome-jev-by-typesafe(680)、awesome-jev(544) |
| **复现(单token打分)** | **8** | 2 | simple-jev(371)、LLM2Jev(63)、mini-jev(29) |
| 官方 | 4 | 185 | typesafe-ai/skills(1022)、system-one-adapter-python(192)、typesafe-sdk-js(178) |

### 4.3 star 分布

| 区间 | 条数 | 占比 |
|---|---|---|
| ≥10000 | 2 | 0.3% |
| 1000–9999 | 8 | 1.0% |
| 100–999 | 68 | 8.7% |
| **<100** | **700** | **90.0%** |

**90% 的项目不到 100 star。** 这个生态是两周内爆发的小项目集合，不是成熟生态。`laos_fit=core` 只有 **2 条**，这个严格度是有意为之。

### 4.4 关键裁定：复现 ≠ 借用范式

生态里混着两类完全不同的东西，**不区分会得出「端侧跑 Jev 只要 15 ms」的错结论**：

| | `复现`（42 条） | `复现(单token打分)`（8 条） |
|---|---|---|
| 做法 | 重新训练出非自回归决策头 | 借用现成 LM 的**首个 token logits** |
| 代表 | `wfzyx/von`、`Heman10x-NGU/openJev-verdict-2.0`、`jaredpalmer/kev`、`TianyuCodings/NanoJev` | `featherless-ai/simple-jev`、`Yinsongxu/LLM2Jev`、`APUS-AI-Lab/fast-browser-use` |
| 是否需要训练 | **是** | **否** |
| 延迟构成 | 单次 forward pass | 生成式，受生成长度影响 |
| 校准性 | 训练目标即校准 | 未经校准训练，概率不可信 |

### 4.5 「语音 + 常驻」先例

这是与 laos 最贴近的一条线，在 778 条里找到 **11 条**：

| 项目 | star | 形态 |
|---|---|---|
| `moritzkremb/jev-voice-browser` | 146 | 语音驱动浏览器 |
| `kevinbadi/jev-voice` | 37 | local whisper.cpp + one Jev call |
| `brudarko/jev-mac-voice` | — | mic → STT → Jev |
| `chasemc67/Jevis` | 1 | **Jev-filtered always-on speech input harness** |
| `sgaabdu4/capture` | 2 | Private Mac voice diary |
| 其余 6 条 | 0–2 | 同类小项目 |

**全部是 0–146★ 的小项目。** 说明「常驻语音 → STT → Jev 决策」这条路**有人走过，没人做成**——laos 有现成的四段漏斗，这正是可以补的位置。但也意味着**没有成熟方案可抄**。

---

## 5. 端侧可行性（实测，非 README）

### 5.1 三个候选的实际结果

| 候选 | 结果 | 原因/数字 |
|---|---|---|
| **`yzfly/edgejev`** | ✅ **跑通** | ONNX int8，运行时**不依赖 torch** |
| `wfzyx/von` | ❌ 否决未实测 | 依赖 torch + 1.5 GB 权重，手机装不下 |
| `aovestdipaperino/laya-rust` | ❌ 否决未实测 | 需 cargo 编译，峰值 RAM 2.4 GB |

### 5.2 `edgejev` 实测数字（本机 x86，AMD Zen 3）

| 指标 | 实测值 | 备注 |
|---|---|---|
| 首次加载 | **2144 ms** | 加载 324 MB ONNX + 初始化会话；**不能频繁启停** |
| median 延迟 | **157.5 ms** | 3 题齐发，单 forward pass（单题量级约 80–130 ms） |
| p95 延迟 | **233.1 ms** | 同上 |
| 峰值 RSS | **494.8 MB** | 含 324 MB 模型驻留 |
| 模型目录 | **358.9 MB** | `model.onnx` 324.5 MB + tokenizer 34.4 MB |

### 5.3 README 宣称的 15.6 ms 被否证

- ✅ 模型体积 324 MB —— 一致
- ✅ 运行时无 torch —— 一致
- ❌ **延迟 —— 不一致，慢约 10×**

`15.6 ms` 是在 **4 vCPU Intel Xeon Cascade Lake（AVX512-VNNI）** 上测的硬件特例；本机 **AMD Zen 3 无 AVX512-VNNI**，int8 只能走 AVX2。

> **裁定 J7**：凡本调研的延迟/内存/功耗数字，一律来自 `04-ondevice-benchmark.md` 实测。**README 的 15.6 ms 已否证，不得在落点代价中引用。**

### 5.4 外推到 proot aarch64（量级估计，无可靠系数）

| 场景 | 估算 | 判定 |
|---|---|---|
| 离线/二级确认（每天数百–数千次） | 常摊 **4.6 mW** 量级 | ✅ 可忽略 |
| **常驻每帧调用（1 次/秒）** | 持续 **0.5–1.5 W** 附加 | ❌ **否决** |

**假设**：aarch64 上 onnxruntime int8 走 **SDOT**（优于 x86 AVX2），但手机 Cortex-A 核心更弱、核数更少 → 净延迟不确定。对照 laos 既有功耗阶梯：通用 Linux 空闲 400–1000 mW，手机 NPU 持续 1–4 W。

**x86 → aarch64 没有可靠换算系数**，以上只是量级估计。

### 5.5 一句话结论

**端侧现在能跑 `yzfly/edgejev`（ONNX int8，359 MB，onnxruntime，无 torch），但延迟比 README 慢约 10×，且须先在构建机用 torch 跑 `edgejev build` 才能拿到权重——只够漏斗③蒸馏，不够漏斗①常驻。**

---

## 6. laos 落点

### 6.1 11 个判定点（逐个核对源码确认）

| 位置 | 当前判定 | 类型 |
|---|---|---|
| `laos/vad.py:43/107` `split_segments(-35.0)`、`StreamingVAD` | 固定能量阈值 | 硬阈值 |
| `drivers/drv_mic.py:61/183` `mic_listen_start(-40.0)`、`split_on_silence(-40)` | 固定能量阈值 | 硬阈值 |
| `laos/memory.py:35` `bigram_jaccard` | bigram Jaccard | 朴素相似度 |
| `laos/memory.py:120` `recall` | `jaccard*0.7 + tag*0.2 + recency*0.1` 三硬权重 | 硬权重 |
| `laos/memory.py:43` `RECENCY_HALF_LIFE_DAYS=14.0` | 固定半衰期 | 硬阈值 |
| `laos/risk.py:40/48` `can_admit` → `remaining > reserve` | 布尔硬规则 | 硬阈值 |
| `laos/context.py:127/162/174` `_compact_if_needed` / `_swap_out` | 按 token 窗口换出 | 硬阈值 |
| `laos/skills.py:48` `match` | 走 `memory.recall` | 朴素相似度 |
| `laos/brain.py:220` `make_brain` | 单一 brain，无路由 | 空缺 |
| `drivers/drv_ear.py:191` `ear_transcribe` | 固定 ASR 通道 | 固定 |
| `laos/scheduler.py:41/86` `next_pid` / `note_outcome` | 优先级 + token 预算 | 规则调度 |

### 6.2 映射到三原语

| 落点 | 原语 | 说明 |
|---|---|---|
| 1. 漏斗① 触发 | `Noul` | **否决**（见 §6.4） |
| 2. 蒸馏后重要度 | `Score` | 决定进长期记忆 vs 即焚 |
| 3. 记忆类别路由 | `Choice` | 替代调用方自己传 `kind` |
| 4. 记忆召回 | `Score` | **两级**：Jaccard 召回 + Jev 精排 |
| 5. 记忆半衰期 | `Score` | 由固定 14 天改为按分档 |
| 6. 不可逆闸门 | `Score` + confidence 三档 | **价值最高**（防烧预算） |
| 7. 技能路由 | `Choice` | 替代文本相似 |
| 8. 上下文压缩 | `Noul` | 对标 `fast-jev-compaction`(4878★) |
| 9. Brain 路由 | `Choice` | 对标 `hermes-jev-skills` |

**分布**：`Choice` × 3 / `Score` × 4 / `Noul` × 2。

> **偏差 A（重要）**：`memory.remember`(memory:106-112) 与 `context._compact_if_needed`(context:131-156) **已存在 opt-in `judge.noul` 钩子**——来自并行实现线（提交 `c685f32`），不是本调研写的。即「记忆入库预审」「上下文压缩预审」两条 Noul 落点的骨架**已经就位**。

### 6.3 落地顺序 P0–P4

| 优先级 | 落点 | 原语 | 理由 |
|---|---|---|---|
| **P0** | 上下文压缩(8) + 记忆召回精排(4) | Noul / Score | 均**离线非实时**，不碰常驻每帧路径；157.5 ms/批、每天数百次 → 常摊 **4.6 mW**（可忽略）；压缩钩子骨架已就位，**落地成本最低** |
| P1 | 蒸馏重要度(2) + 记忆类别路由(3) | Score / Choice | 漏斗③蒸馏后触发（非每帧）；共享同一常驻 session，加题不增延迟 |
| P2 | 不可逆操作闸门(6) | Score + confidence | 价值最高（防烧预算），但 `charge` 按尝试计费且 kill 不退款 → 阈值须严调 |
| P3 | 记忆半衰期分档(5) + 技能路由(7) | Score / Choice | 半衰期需重构 `recall` 的 `recency` 项（中改动） |
| P4 | Brain 路由(9) | Choice | 改动最大、收益边际 |

### 6.4 否决项

**漏斗① 常驻每帧调用 Jev —— 否决。** 1 次/秒 → 持续 0.5–1.5 W 附加，手机不可承受；且常驻 495 MB RSS 长期占用。

改为**两级结构**：能量门先过（0 代价），Jev 仅在边界有声段做二次确认（N≈1000–5000/天 → 常摊 **0.1–0.2 mW**，可接受）。但属实时触发路径，**须先在 proot aarch64 实测功耗后再评估，不进当前落地**。

---

## 7. 不值得做的部分

1. **官方云端 API 进运行时** —— 闭源 / 未开放中国大陆 / 违反本地优先。
2. **为 laos 自训练一个决策头** —— 成本与收益不匹配（`复现` 类已有 42 条，且 `edgejev` 已可跑）。
3. **用 Jev 替代 ASR 或情绪模型本身** —— Jev 不生成文本，不是生成模型的替代品。
4. **在漏斗①每帧路径上无条件调用** —— 功耗否决（0.5–1.5 W）。
5. **为每个判定点独立加载/启停 edgejev 实例** —— 首次加载 **2144 ms**、常驻即占 **~495 MB**，N 个实例线性放大 RAM，**手机上直接 OOM**。

> **第 5 条是前面所有落点的架构前提**：所有 Jev 落点必须以**单一常驻 session** 服务（多个 Noul/Score/Choice 题可一次 `system_one` 齐发，加题几乎不增延迟）。

---

## 8. 与并行实现线的关系（重要）

**在本次调研进行的同时，另一路工作在同一个仓库里推进，并且已经把 Jev 实现进 laos 代码了。** 这不是冲突，而是互补——但因为两路人马互不知情，有**一处接口不匹配**必须点名。

### 8.1 并行线已完成的

| 提交 | 内容 |
|---|---|
| `3399dbc` | `docs/superpowers/plans/2026-09-18-jev-system-one-layer.md` |
| `be08c72` | `docs/research/2026-09-18-jev-landscape.md`（239 行）+ 扩充 `jev_repos_curated.json` |
| `509189a` | **`laos/judge.py`（333 行）+ `tests/test_judge.py`** |
| `a65932a` | `laos/kernel.py` 高危 syscall 的 jev prejudge 闸门（opt-in） |
| `c685f32` | `laos/memory.py` / `laos/context.py` 记忆入库与压缩预审（opt-in） |

`laos/judge.py` 的四个后端：`RuleBackend`（规则兜底）/ `CloudBackend`（TypeSafe API）/ **`LocalBackend`（`LAOS_JEV_ENDPOINT`）** / `SafeJudge`（异常降级）。

### 8.2 ✅ 值得肯定：默认不走云端

```python
def select() -> JudgeBackend:
    want = os.environ.get("LAOS_JEV_BACKEND", "none").strip().lower()
    if want == "cloud":  return CloudBackend()
    if want == "local":  return LocalBackend()
    return RuleBackend()  # none | rule | 未知值 → 零依赖兜底
```

**默认是 `none` → `RuleBackend()`，零依赖、零网络。** 云端必须显式设 `LAOS_JEV_BACKEND=cloud` 才启用。这与「中国大陆未开放 + 本地优先」的硬约束**不冲突**。`SafeJudge` 也在后端异常时 fail-open 回落既有行为，设计是对的。

### 8.3 ⚠️ 必须点名：`LocalBackend` 与实测唯一的端侧候选接口不匹配

**这是两条线交汇处唯一真正的问题。**

`LocalBackend` 的实现是 **OpenAI 兼容 HTTP 端点**：

```python
url = f"{self.endpoint}/v1/chat/completions"
body = {"messages": [{"role": "user", "content": json.dumps(inner, ...)}]}
payload = _post_curl(url, body, {}, self.timeout)
verdict, confidence = _verdict_from_payload(payload)   # 解析生成出的 JSON
```

而本次实测**唯一跑通**的 `yzfly/edgejev` 是 **进程内 ONNX 直推**（`system_one(questions)` → 单次 forward pass），**不是 HTTP 服务**。

由此产生三个后果：

1. **要接 edgejev，必须先写一个 OpenAI 兼容的 HTTP shim**，把 `/v1/chat/completions` 翻译成 ONNX 直推。这是额外工程量，且引入了常驻 HTTP 服务。
2. **更本质的问题**：走 chat completions 意味着**从生成结果里解析 JSON verdict**——这是 §4.4 里 `复现(单token打分)` 那一类的形态，**不是真非自回归决策头**。延迟会是生成式绑定的，拿不到 edgejev 实测的 157.5 ms。
3. `LocalBackend` docstring 写的目标是「NanoJev/simple-jev」——**这两个都在 `复现(单token打分)` 或未经实测的一类里**，没有一个是本次实测验证过端侧可跑的。

**建议**：若要真正吃到 edgejev 的 157.5 ms，应新增一个 `OnnxBackend`（进程内直推），而不是把它塞进 `LocalBackend` 的 HTTP 契约里。

### 8.4 本次调研相对 `2026-09-18-jev-landscape.md` 的增量

| 维度 | 并行线（09-18） | 本次（09-21） |
|---|---|---|
| 生态规模 | ~20–68 条（curated） | **778 条**（全量抓取 + 去噪，含去噪判据） |
| 端侧可行性 | 未实测 | **实测**（157.5 ms / 495 MB / 359 MB），**并否证了 README 15.6 ms** |
| 判定点映射 | 4 个集成点 | **11 个判定点**（逐个核对源码行号）+ P0–P4 |
| 落点代价 | 未量化 | **量化**（常摊 4.6 mW vs 常驻 0.5–1.5 W 否决） |
| 架构前提 | 未讨论 | **单一常驻 session**（N×495 MB 会 OOM） |

**核心增量是「端侧实测数字」与「判定点映射」**——这两项正是并行线实现时缺的判据。反过来，并行线已经把骨架写进了代码，本次调研的落点设计可以直接挂上去。

---

## 9. 口径裁定记录

| 编号 | 裁定 |
|---|---|
| **J1** | `table_lint.check_text` 把 schema 触发列硬编码为「模型」，Jev 表以「项目」开头会被**静默跳过、零校验**。已维护触发列可变的 `check_text` 副本，**未改 `table_lint.py`** |
| **J2** | 通用规则 `params` / `metric` 依赖的列在 Jev schema 中不存在，天然 inert；selftest 据此对齐「九类」而非强行断言 |
| **J3** | **「真复现」vs「借单 token logits 打分」必须在 `类别` 列区分**，否则会得出「端侧只要 15 ms」的错结论 |
| **J4** | `Violation` 实际签名是四参 `(path, line, rule, detail)`，计划骨架三参为笔误 |
| **J5** | 判定点映射表列数 ≠ 12，`check_jev_table.py` 自动跳过（`MIN_SCHEMA_COLS` 保护） |
| **J6** | **`Noul` 无独立 confidence**，laos 落点不得自行补该字段 |
| **J7** | 凡延迟/内存/功耗数字一律引 `04-ondevice-benchmark.md` 实测；**README 的 15.6 ms 已否证（慢 10×），禁用** |
| **J8** | 字面保留词 `typesafe` / `decision model` 过宽（混入 trpc/TanStack/http4k），改用精度判据；原口径审计副本保留在 `repos_raw_broad.jsonl` |

---

## 10. 未核实清单

| 项 | 状态 |
|---|---|
| `verify_state=仅README` | **740 / 778 条**（95.1%）——仅读 README 判断，未读代码、未跑 |
| `verify_state=未核实` | 38 条 |
| `laos_fit=core` 的两条（`edgejev`、`laya-rust`） | `edgejev` **已实测**；`laya-rust` **仍待实测**（需 cargo，静态否决） |
| 各复现的许可 / 参数量 / 是否需自训练 | 多数标 `[待核实]`，仅 `02-oss-reproductions.md` 中已核实的字段可信 |
| 外推 aarch64 的数字 | **无量级保证**，x86→arm 无可靠换算系数 |
| 复现类的低星长尾 | 被 `verdict` / `typed decision model` / `open-jev` 子串误命中（如 `OpenJEVis` 是 Java 能源项目），已标注需人工复核 |
| 官方 70–500 ms / 193.6× / 444.6× | 全部 `官方自测`，无第三方验证 |

---

## 11. 红线自检

| 红线 | 状态 |
|---|---|
| 不引用 README 宣称的 15.6 ms | ✅ 裁定 J7 禁用，全文引用实测 157.5 ms |
| 官方数字标 `官方自测` | ✅ §3 逐条标注 |
| 不把官方云端 API 当运行时依赖 | ✅ §3 四条否决，§8.2 确认实现线默认不走云端 |
| 不编造 star 数 / 延迟 / 许可 | ✅ 全部来自 `repos_classified.jsonl` 与实测 |
| 不把「借用范式」当真复现 | ✅ 裁定 J3，§4.4 分列 |
| 区分 `复现` 与 `复现(单token打分)` | ✅ 42 vs 8 条 |
| 与并行线不冲突 | ✅ 未修改 `laos/` 与 `bin/` 任何文件 |

---

## 12. 参考来源

1. **口径与校验**：`docs/research/jev/00-taxonomy-and-metrics.md`、`scripts/check_jev_table.py`
2. **生态抓取**：`docs/research/jev/repos_raw.jsonl`（778）、`fetch_summary.md`、`noise_dropped.jsonl`、`repos_raw_broad.jsonl`（字面口径审计副本）
3. **分类**：`scripts/classify_jev.py`、`repos_classified.jsonl`、`01/02/03-*.md`
4. **端侧实测**：`scripts/bench_jev_local.py`、`04-ondevice-benchmark.md`
5. **落点设计**：`05-laos-placement.md`
6. **并行实现线**：`laos/judge.py`、`laos/kernel.py`、`laos/memory.py`、`laos/context.py`、`docs/research/2026-09-18-jev-landscape.md`、`docs/superpowers/plans/2026-09-18-jev-system-one-layer.md`
7. **计划**：`docs/superpowers/plans/2026-09-21-jev-decision-model-survey.md`
