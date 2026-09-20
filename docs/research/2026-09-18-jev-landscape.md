# Jev System-One 生态研究报告

- 日期：2026-09-18（核实抓取：2026-09-21）
- 任务：Task 1（供 Task 2-5 引用）
- 语料：`docs/research/corpus/`（4 份 README + `jev_repos_curated.json`，本次从 30 条扩到 **68 条**，全部实抓 GitHub API 元数据）

**核实标记**：
- ✓ = TypeSafe 官方一手来源（blog / docs.typesafe.ai，本次实抓）
- ◐ = 多个独立 README / 仓库交叉印证（corpus 实抓）
- 🔶 = 二手口径（36kr 报道、X 官方账号宣发，未在官方文档复核）
- ⚠ = 项目自述数据，未经独立复现

---

## §1 Jev 是什么

**Jev** 是 TypeSafe AI 于 2026-09-15 发布的 **System One Models** 首个模型（early access）。名字取自经济学家 William Stanley Jevons，"System One" 取自 Kahneman《Thinking, Fast and Slow》的系统一（快思考）✓。

核心语义一句话：**非结构化 state 进 + 类型化 question 进 → 每个问题并行、隔离地评估 → 类型化决策 + 校准概率出**。全程零自回归解码、零生成文本、零 JSON 解析——官方称因此"永不产生类型错误、不能幻觉"✓。它不是聊天模型，是**给软件用的决策层**（分类、路由、rubric 打分、校验、agent 护栏）。

训练栈（官方）✓：新模型架构 + 并行采样器 + **RLCD**（Reinforcement Learning for Calibrated Decisions，以校准为奖励的强化学习）。

### 1.1 三判型表

| 判型 | 语义 | 输入（`questions[key]`） | 输出（`answers[key]`） | 典型延迟 | 单次成本 |
|---|---|---|---|---|---|
| **Noul**（布尔） | 是非判断："这个命题成立吗？" | `{"type":"noul","instructions":"…", "criteria":{"true":"…","false":"…"}}` | `noul`: 0–1 ✓（社区口径 0.01–0.99 ◐） | 70–500ms 端到端，同请求加问题几乎不增时延 ✓ | 按 input token 计费：$0.042/MTok；output token 免费 ✓；36kr 折算口径 🔶：**0.44s / $0.00035 每次** |
| **Choice** | 从候选集选一个（2–255 个 ✓；社区实现口径 2–50 ◐） | `{"type":"choice","instructions":"…","criteria":{"billing":"…","technical":"…"}}` | `choice` + `confidence` + `probabilities`（全分布）✓ | 同上 | 同上 |
| **Score** | 按有序 rubric 打分（2–10 级 ◐ NanoJev；官方 demo 3 级，社区实现 2–50 级） | `{"type":"score","instructions":"…","criteria":["Unsupported","…","Fully supported"]}` | `score`（期望值，可为小数）+ `confidence` + `probabilities` + `legend` ✓ | 同上 | 同上 |

更高基数（>255）官方建议两段式：先独立打分再显式选择 ✓。

### 1.2 API 形状（✓ 官方 quickstart 实抓）

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY

{ "model": "jev-latest",                # 响应回显具体版本，如 "jev-1.13.0"
  "state": "<一段非结构化上下文>",
  "questions": {
    "<问题ID>": { "type": "choice|score|noul", "instructions": "…", "criteria": … }
  } }

→ { "answers": { "<问题ID>": { "choice"/"score"/"noul", "confidence", "probabilities", ["legend"] } },
    "usage": { "input_tokens": 392, "output_tokens": … } }
```

- 官方 Python SDK：`pip install typesafe-sdk`，导出 `TypeSafeClient` / `Choice / Noul / Score` ✓。
- `questions` 用人类可读的描述性 key；每个问题**并行且隔离**地对着同一个 `state` 评估（官方称避免 context-rot）✓。
- `/v1/systemone` 已成社区事实路径别名：simple-jev、new-api 插件等都兼容该路径 ◐。
- 批量实例（36kr 口径 🔶）：**40s 判完 724 条广告、共 8,724 次判断，$0.09**。

### 1.3 必须知道的语义警告

1. **校准不是对称的**：独立测试（scienthoon/jev-ood-calibration，900 条不可见工单 + 3 公开基准，全量原始响应公开 ⚠）发现 **Choice/Score 偏过度自信、Boolean/Noul 偏不自信**。阈值要按判型分别调。
2. **概率排序不总成立**：jev-orderby-bench 用预注册门槛实测，Jev 1.13.0 在 20 Newsgroups 话题上 6 条全过，在 Amazon ESCI 商品相关性上 **6 条挂 4 条** ⚠——"按 Score/Noul 概率 ORDER BY"在分布外任务上不可盲信。
3. **confidence ≠ 答对概率的合同**：官方称 calibrated ✓，但 jevcal 等工具的存在本身说明实践者需要在**自己的数据上重新拟合阈值** ◐。
4. **输出 token 免费** 意味着成本模型 ≈ 输入长度 × $0.042/MTok，与问题个数弱相关——**把多个问题塞进一次调用是成本最优解** ✓（官方："Adding questions barely changes the response time"）。

### 1.4 官方资源与渠道

| 资源 | 链接 | 状态 |
|---|---|---|
| 发布博客 | https://typesafe.ai/blog/introducing-system-one-models-and-jev | ✓ 实抓 |
| 文档站 | https://docs.typesafe.ai（含 `llms.txt`、`/primitives/{choice,score,noul}`、`/introduction/quickstart`、`/api`） | ✓ 实抓 |
| API 端点 | `POST https://api.typesafe.ai/v1/systemone` | ✓ 实抓 |
| 官方 SDK | Python `typesafe-sdk` ✓；社区 Go/Elixir/Swift/PHP/Scala/Ruby/Rust(CLI) SDK ◐ | 混合 |
| 官方技能包 | github.com/typesafe-ai/skills（`npx skills add typesafe-ai/skills`，1,022★） | ✓ 实抓 |
| 网关 | OpenRouter（beta）、Cloudflare AI Gateway、Vercel AI Gateway | 🔶 各官方账号 X 宣布，awesome-jev 收录 |
| HN 发布帖 | news.ycombinator.com/item?id=49717558（1,800 分，~480 评论） | ◐ |

---

## §2 生态地图（按用途分类）

数据基础：awesome-jev 收录 ~245 条（13 类），本次精选并入 curated JSON 至 **68 条**。launch 后 5 天的生态密度本身是信号：**Jev 的用法收敛在"把 LLM 里不需要生成文本的那部分调用抽出来"**。按与 laos 的相关度排序列关键仓库（★ 为 GitHub stars，2026-09-20 前后实抓；"—" 表示本次未取星数）：

### 2.1 上下文压缩 / Compaction（与 laos `context.py` 直接相关）

| 仓库 | ★ | 一句话 |
|---|---|---|
| [tamaratran/fast-jev-compaction](https://github.com/tamaratran/fast-jev-compaction) | 4,873 | Claude Code 插件：不做摘要，一次 fast request 给每条 tool call/result 打"仍需要吗"分，陈旧的丢弃/截断，保留的**逐字保留** |
| [tamaratran/jev-pruner](https://github.com/tamaratran/jev-pruner) | 123 | 在模型看到之前用 Jev 修剪超长 Bash 输出 |
| [compozy/yoshi](https://github.com/compozy/yoshi) | 19 | Claude Code/Codex 代理：Jev 判哪些历史仍被需要再剪枝，"measured not claimed" |
| [kerpopule/hermes-jev-skills](https://github.com/kerpopule/hermes-jev-skills) | 196 | Hermes/Claude/Codex 的 Jev 技能集：路由、记忆、**compaction**、技能选择、电脑/浏览器使用 |
| [leonaaardob/fast-dev-compaction](https://github.com/leonaaardob/fast-dev-compaction) | 3 | 上者的 Codex 移植（压缩点周围逐字恢复上下文） |
| [joelhooks/pi-fast-jev-compaction](https://github.com/joelhooks/pi-fast-jev-compaction) | — | Pi 移植：逐字保留正文，只剪陈旧工具历史，剪不动才回退摘要 |

模式共识：**Jev 判"要不要"，代码执行"怎么删"；保留侧逐字、丢弃侧可逆（可从磁盘找回）**。

### 2.2 Judge-as-Judge / 评估与校准（与 laos 技能质量闸相关）

| 仓库 | ★ | 一句话 |
|---|---|---|
| [vercel/eve](https://github.com/vercel/eve) | — | Vercel agent 引擎把 `typesafe-ai/jev` 设为 evaluate 路径**默认评估模型** |
| [thruwire/foreman](https://github.com/thruwire/foreman) | 422 | "软件工厂"工头：Jev 独立判实现是否完成、测试是否充分、是否需要人 |
| [abhixhek/jevcal](https://github.com/abhixhek/jevcal) | 8 | 在自己的标注数据上拟合每问题的置信阈值→held-out 验证→报告升级率→模型更新破阈值时 CI 失败（**阈值工程的标准工具**） |
| [scienthoon/jev-ood-calibration](https://github.com/scienthoon/jev-ood-calibration) | 3 | 独立 OOD 校准测试：Choice/Score 过信、Boolean 欠信（§1.3 来源） |
| [yodablocks/jev-orderby-bench](https://github.com/yodablocks/jev-orderby-bench) | 0 | "按 Jev 概率排序站得住吗"的预注册基准（§1.3 来源） |
| [frostney/clean-code-review](https://github.com/frostney/clean-code-review) | 6 | PR 每文件 31 个布尔 Clean Code 气味 + 交给写作模型写 prose（**判/写分离**范式） |
| [devagrawal09/jev-review](https://github.com/devagrawal09/jev-review) | 396 | 分阶段代码评审，Jev 闸住每一阶段 |
| LangChain 官博《Can Jev Be a Better Agent Evaluator?》 | — | 结论：对 online eval，Jev 比 LLM judge 更便宜更一致 🔶 |
| [MarissaFamularo/citation-verifier](https://github.com/MarissaFamularo/citation-verifier) | — | Claude 定位引文 → Jev 打支持分 → 人终审 |

### 2.3 浏览器 / 计算机动作（Jev 最大的单点应用）

| 仓库 | ★ | 一句话 |
|---|---|---|
| [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | **11,074** | browser-use 官方 ultrafast agent：Jev 决定每步动作与点击元素，只在要打字时才叫 LLM（**生态旗舰，单仓库≈其余总和**） |
| [jkudish/jev-browser](https://github.com/jkudish/jev-browser) | 179 | 同思路独立实现；已进入 Cline 官方插件集合（`jev-browser`） |
| [droidrun/mobile-jev](https://github.com/droidrun/mobile-jev) | 264 | 移动端动作选择 |
| [wy-coliney/jev-browser-use](https://github.com/wy-coliney/jev-browser-use) | 240 | "Jev 点击、Codex 思考与验证"，5–10x 提速 |
| [Silbercue/public-browser](https://github.com/Silbercue/public-browser) | 9 | 真实 Chrome 档案驱动，自述 -30% token / -25% 成本 ⚠ |
| [forvela/jev-agent-browser](https://github.com/forvela/jev-agent-browser) | 6 | 父 agent 委派有界任务给 Jev 动作循环，歧义/卡死回抛父级 |
| [agent-labs-dev/fastbrowse](https://github.com/agent-labs-dev/fastbrowse) | 5 | Jev 选动作 + LLM 读页规划，答案逐句引用原文 |
| [GoldenLoaf24h/browserclaw](https://github.com/GoldenLoaf24h/browserclaw) | — | 本地 Jev 微循环 + 85%+ 剪枝 DOM 树 + 原生 CDP 事件 |
| [chy4pro/jev-for-chrome](https://github.com/chy4pro/jev-for-chrome) | — | jev-ultrafast 的非官方 Chrome 扩展移植：Choice 选操作，双 Noul（到目标了吗/卡住了吗）否决假 DONE |
| [yikangy873-gif/jev-desktop](https://github.com/yikangy873-gif/jev-desktop) | — | Codex Computer Use 里 Jev 选桌面动作 |
| [OmniJev/PlayJev](https://github.com/OmniJev/PlayJev) | — | 0.8B VLM 单 forward 读 448px 帧出动作分布（视觉版复刻） |

### 2.4 安全闸 / 高危预审（与 laos `kernel.py`/`risk.py` 直接相关）

| 仓库 | ★ | 一句话 |
|---|---|---|
| [coldteadotai/abide](https://github.com/coldteadotai/abide) | 191 | 读 coding agent 每次编辑、Jev 标违规；独立复核对 39 次标仅确认 10 次（**误报率实证**） |
| [y0usaf/pi-jev](https://github.com/y0usaf/pi-jev) | 112 | Pi agent 工具调用闸：先量测再放行 |
| [shiftynick/jev-axi](https://github.com/shiftynick/jev-axi) | 17 | PreToolUse 闸：按破坏性/外传/RCE/弱化安全四维打分；常规命令本地裁决不外发；44/44 自测 ⚠ |
| [luantak/is-malicious](https://github.com/luantak/is-malicious) | 16 | 运行前对源码/构建文件发 Noul 检查，可疑块二次复核 |
| [leepokai/jev-guard](https://github.com/leepokai/jev-guard) | 12 | Claude Code/Codex/Pi/ACP 通用护栏：deny/ask/allow 三档 + 结果注入检测 |
| [anpicasso/hermes-jev-approvals](https://github.com/anpicasso/hermes-jev-approvals) | 9 | Jev 做命令审批：8.7x 快、4.4x 少打扰人（153 条真实命令量测 ⚠） |
| [jesset/pi-verdict](https://github.com/jesset/pi-verdict) | 3 | 确定性规则先裁clear cases，灰色地带一问 allow/ask/deny；**错误/超时=deny** |
| [CodeAlive-AI/mastra-jev-moderation](https://github.com/CodeAlive-AI/mastra-jev-moderation) | 2 | 生产数据：9/9 恶意拦截、0/49 正常误拦，~0.4s 中位，deadline+熔断 **fail-open** ⚠ |
| [noplan-inc/limpet](https://github.com/noplan-inc/limpet) | 1 | Stop hook：Jev 判"真做完了吗"，防过早收工 |
| [shitianfang/wakegate](https://github.com/shitianfang/wakegate) | 0 | 长跑 agent 唤醒闸：wake<0.2 才跳过，错误/超时必醒，21/21 场景 ⚠ |
| [AkashPriyadarshii/jev-git](https://github.com/AkashPriyadarshii/jev-git) | — | 亚秒级 pre-commit/pre-push 反射闸（secret、破坏性命令） |

### 2.5 搜索 / 重排 / 记忆过滤（与 laos `memory.py` 相关）

| 仓库 | ★ | 一句话 |
|---|---|---|
| [superagents-lab/jev-search](https://github.com/superagents-lab/jev-search) | 284 | Noul 判标题+摘要相关性 → 排序 Search1API 结果 |
| [realZachi/pg-jev](https://github.com/realZachi/pg-jev) | 236 | Postgres 扩展：SQL 里 `jev()` 过滤 / 概率排序 |
| [hotchpotch/jev-reranker](https://github.com/hotchpotch/jev-reranker) | 4 | RAG 相关性 Noul 过滤 + 重排，可配阈值 |
| [WiktorB2004/llama-index-jev](https://github.com/WiktorB2004/llama-index-jev) | 3 | LlamaIndex 适配：nfcorpus nDCG@5 0.340→0.396，~$0.0003/查询 ⚠ |
| [shinpr/jev-reranker](https://github.com/shinpr/jev-reranker) | 1 | Rust CLI：独立 Noul 排名/证据阈值/原文抽取 |
| [AkashPriyadarshii/jev-scout](https://github.com/AkashPriyadarshii/jev-scout) | 1 | 投机扇出打分扫仓库/crate，零幻觉 |
| [YehuiTang0316/jev-nlgrep](https://github.com/YehuiTang0316/jev-nlgrep) | 1 | 自然语言条件 grep，阈值可配、按行回链 |
| [kylemclaren/jevql](https://github.com/kylemclaren/jevql) | 7 | 裸 Postgres 上跑 SQL 后对每存活行发 Jev 判断（`jev()`/`jev_prob`/`jev_choice`） |
| [mgaitan/sqlite-jev](https://github.com/mgaitan/sqlite-jev) | 1 | SQLite C 扩展：Jev 判断即 SQL 函数 + 批量虚表 |
| **反例** GoSailGlobal 实测 | — | 33,047 目录、164 真实查询、9,831 分级对：**Jev 重排没有打赢向量检索** 🔶 |

### 2.6 复刻与微调（§3 详述，此处仅列全谱系）

开源复刻已形成 **0.5M–35M 参数全谱系**：laya (2,904★, ~35ms)、laya-mlx (1,113★, Apple Silicon 7–14ms)、NanoJev (1,305★, 0.6B)、kev (801★, MacBook 可训)、von (117★, 395M, <15ms)、litjev (28★, 免训练)、minojev (547k 参数, CPU 从零训练)、CUA-S1-FORMS (706k 参数, 表单专项 99.7% vs Jev 83.6% ⚠)、jevlike-esp32 (MCU 边缘)、openjev-sglang (213★)、SemIf (2,282★)、simple-jev (371★)。

### 2.7 模型路由（Jev 判"该谁干"）

jev-router (244★, Claude Code 最便宜可用模型路由)、prismhq/jev-router（LiteLLM）、pi-jev-router、jcm-router（本地代理+缓存主聊天不动）、Jev-Auto-Router（Codex (model,effort) 对）、jev-agent-skill-router（弱匹配直接拒绝）、dzhng/duet-agent、notra（生产 GEO 平台，`NOTRA_JEV_CLASSIFIERS` 开关把 LLM 分类器迁到 Jev Boolean @0.5 阈值，目标 300ms p50）。

### 2.8 规模信号

- awesome-jev 单列表 245+ 条、13 类；另一导航站（0xLogicrw）收录 287 个项目 ◐。
- GoSailGlobal 统计 19 个开源项目合计 >6,800★（发布后 3 天）🔶；本报告 curated 68 条合计 ≈3.3 万★（含 jev-ultrafast 1.1 万）。
- 判读：**浏览器动作 > 安全闸 > 路由 > 压缩** 是采用密度递减序；"通用 LLM 替换"类（写作、闲聊）没人做——印证 Jev 只吃"类型化决策"这口饭。

---

## §3 本地化路线对比

| 维度 | **NanoJev** (TianyuCodings) | **jevlike** (vinnylarouge) | **simple-jev** (featherless-ai) |
|---|---|---|---|
| 定位 | Jev 的 nano 复刻：0.6B 并行决策模型，全分布输出、零输出解码 | 极简训练库：一个"文本+N 选项→每选项一概率"的单 pass scorer | 网关化：把**任意 HF 开源模型**变成 `/v1/classifier`（别名 `/v1/systemone`）端点，免训练分类头 |
| 参数量 | Qwen3-0.6B 主干 + 决策头（Choice 集合注意力+softmax / Boolean sigmoid / Score 分布期望）◐ | 默认从零 byte-embedding 编码器（MB 级）；可选冻结 Qwen2.5-0.5B + rank-256 LoRA 头 ◐ | 任意兼容模型：demo 用 Qwen3.5-0.8B（CPU）到 Gemma-4-26B-A4B MoE（GPU），也接 Laya 专用检查点 ◐ |
| 训练数据 | **公开可复现**：18,760 题/变体 × 5 splits（train/dev/calibration/test/OOD），896 条专家轨迹 17,498 决策，HF `unified-games-v1` 全量可下 ◐ | 自备 JSONL `{context, options[], label}`；内置 synthetic 生成器 + Wikispeedia 脚本 ◐ | **零训练**起步（读 next-token logits 构响应）；RFDT 流水线支持教师蒸馏 + LoRA 微调到自家判据 ◐ |
| 判型覆盖 | Choice(2–255) + Boolean + Score(2–10) **三判型全** ◐ | 仅 Choice（变长选项单 pass）◐ | choice(2–50) + score(2–50) + noul(0.01–0.99，九 rating token 分布) **三判型全** ◐ |
| 校准 | 训练含 calibration split；完整分布 ◐ | 输出 ECE + 打乱上下文对照组 ◐ | **明示"分布不是校准过的答对概率"** ◐ |
| 部署 | CUDA 服务 `serve_decisions.py` → `POST /api/evaluate`；HF 权重免登录下 ◐ | CPU / Apple MPS / CUDA，`uv` 四条命令跑通 quickstart ◐ | 单文件 HF server；官方 demo API 免鉴权（2k ctx / 2 RPS）；Featherless 付费托管 ◐ |
| 已验证性能（各自自述 ⚠） | 域内强：ViZDoom Basic 128/128（Jev 56/128）、Maze 4/10（Jev 7/10）、Snake 8/8；单 forward、零输出 token | synthetic 菜单 ~98%；Wikispeedia next-click 26–29%（对照 8%）；8 选项单 pass 比小解码器快 ~100x | 4 问 ×1,000-token 公共前缀：4,200→1,200 token（KV 前缀复用）；无端到端精度承诺 |
| 成熟度 | 中：游戏域证据扎实、**域窄**（4 个游戏任务），RLCD 未做（roadmap） | 低：研究起点，作者明言"未复现 TypeSafe 私有方法" | **高**：测试套件、API 参考、版本化 prompt 契约（PROMPT_STRUCTURE_V1）、RFDT、商业托管俱全 |
| 一句话 | 要**专用判据微调**选它（数据/权重/管线全公开） | 要**最小可懂参考实现**或超边缘部署（还有 ESP32 移植）选它 | 要**今天就跑、兼容 Jev API 形状**的本地决策层选它 |

补充两条高价值旁路：**Laya**（2,904★，PyPI+HF，~35ms 单 pass，MLX 上 7–14ms）是复刻里成熟度最高的独立模型；**litjev**（免训练把任意 Qwen 变 `/v1/systemone` 服务）是验证成本最低的本地 POC。

**对 laos 的含义**：本地化不等于复刻。若落点先走云端 Jev（§4 的阈值策略全部先在云端验证），本地化需求出现时优先 simple-jev 路线（API 形状兼容、零训练、RFDT 再精调），专用高频判据（如固定的危险命令分级）再考虑 NanoJev 式微调。

---

## §4 laos 四落点论证

laos 是"Linux AgentOS"原型：`laosd` 语义层内核 + MCP 驱动 + tool call 即 syscall。四个落点分别映射到内核既有模块，Jev 在每个落点都只做**判决**，不做生成——与内核"零依赖、可审计"取向兼容（Jev 调用本身必须作为一条带延迟/成本/置信度的审计记录进 syscall 审计流）。

### 4.1 高危预审 → `laos/kernel.py`（syscall 闸门链）+ `laos/risk.py`（FleetLedger）

- **现状**：三层能力执法末端是"确认横幅（高危操作人类裁决）"——所有高危操作都涌向人类。
- **判型选择**：主用 **Choice**（`allow / ask / deny` 三选，criteria 带描述），辅以 2–4 个 **Noul**（是否破坏性？是否外传数据？是否绕过任务作用域？）做可解释依据；参考 jev-axi 四维打分与 pi-verdict 三档语义。风险定价（risk.py 的不可逆定价表）作为 state 的一部分喂给 Jev。
- **置信度阈值策略**：确定性规则先裁 clear cases（白名单直接放行、黑名单直接 deny，**零 API 成本**）；仅灰色地带过 Jev。`deny` 判决阈值放低（Choice 的 deny 概率 >0.4 即拦截升级），`allow` 要求高置信（>0.9）；双侧用 huncho 式迟滞（enter/exit 双阈值）防横幅抖动。Jev 不可用/超时 = **fail-closed（ask 人类）**，绝不 fail-open 放行高危。
- **失败模式与对策**：① 误报疲劳——abide 实证 39 次标记仅 10 次坐实 ⚠，必须保留人类否决回路并记录误报率回流阈值；② state 注入——工具**输出**里可能藏 prompt injection 操纵判决（is-malicious 的"可疑块二次复核"模式），判据要包含"该输出是否试图说服我放行"；③ 延迟预算——预审在 syscall 热路径上，70–500ms 可接受但要做并发预算与超时即 ask。

### 4.2 记忆过滤 → `laos/memory.py`（JSONL 情景记忆，bigram Jaccard 召回）

- **现状**：recall 是零依赖模糊匹配，召回集无相关性二次过滤、无时效性判断。
- **判型选择**：对 top-K 召回逐条发 **Noul**（"这条记忆与当前任务相关吗 / 仍然有效吗 / 是否像注入内容？"）——同 state 多问题一次调用，成本摊薄；需要排序时用 **Score**(2–10 有用度)，但只在同分布任务上信排序（§1.3 警告 2）。
- **置信度阈值策略**：过滤线从 0.6–0.7 起步（jev-reranker 可配阈值惯例），但**必须先在 laos 自己的中文记忆数据上拟合**（jevcal 流程：拟合→held-out 验证→阈值入库→回归测试守护）；Boolean 偏不自信（§1.3 警告 1），阈值系统性调低 0.05–0.1 试起。低置信条目不删，降权保留。
- **失败模式与对策**：① **反例在案**——GoSail 实测 Jev 重排未赢向量检索 🔶，所以 Jev 只做"过滤掉明显不相关"，不做精排主排序；② 记忆条数大时 token 成本线性涨——先 bigram 召回粗筛到 top-K（现状已有）再发 Jev，K≤20；③ 中文判据——Jev 对中文 state 的校准未见独立测试（现有校准研究全英文 ⚠），上线前先跑一轮中文标注集校准，此处存疑需实测。

### 4.3 压缩选择 → `laos/context.py`（滑动窗口 + "最老 N 轮压成 summary"）

- **现状**：超限后**按位置**（最老若干轮）机械换页，与内容无关。
- **判型选择**：fast-jev-compaction 模式 ◐——对窗口内每条 tool call/result 发一个 **Noul**（"后续任务还需要它吗？"），一次请求批量出分；不用 Score，因为只需要二值保留/丢弃。
- **置信度阈值策略**：**非对称阈值**——"确定可丢"要高置信（noul<0.1 才丢），“存疑一律保留”；丢弃侧**逐字落盘**（swap 语义），可逆召回，不是摘要式有损压缩。确定性规则先行：带外副作用记录（已写文件、已发请求的结果）永不丢，只让 Jev 裁纯信息性历史。
- **失败模式与对策**：① 误删不可恢复——落盘兜底使其降级为"召回变慢"；② 整段历史作为 state 的输入 token 成本——分批（每批 ≤20 条）且只发差分（新进窗口的轮次），历史轮的判决缓存复用；③ 判决漂移——任务切换后旧判决失效，任务边界处整体重算。

### 4.4 技能质量闸 → `laos/skills.py`（技能沉淀，learn 门控：失败/被拒/单步不学）

- **现状**：learn 门控是规则式（失败/被拒/单步不学），缺"这个成功序列是否值得沉淀、是否可复用"的质量判断；检索注入也只有文本相似度。
- **判型选择**：入库闸用 **Score**(2–10 rubric：可复用性/步骤最小性/无副作用残留) + 2 个 **Noul**（序列里是否含敏感信息？是否依赖一次性环境？）——clean-code-review 的"31 布尔 + 判写分离"范式 ◐ 的缩小版；检索侧用 **Choice**（K 个候选技能选 1，替代/增强 bigram 相似度）。
- **置信度阈值策略**：入库 0.7 分界（snifftest 用 0.7 实测 1/54 误报 vs Haiku 4.5 的 37/54 ⚠，0.7 是社区验证过的起点）；**blocking 判决单列**——只有 Noul"含敏感信息">0.9 才硬拒（jev-commit 只在检测到 credential 时 block 的惯例），质量分低只降权不拒。阈值同样走 jevcal 拟合流程。
- **失败模式与对策**：① rubric 设计决定上限——augustus 项目专门做 question-design diagnosis ◐，laos 的 rubric 要随技能库演化迭代；② Jev 通用能力在长尾域弱（luce 实测 GitHub issue priority 仅 41.1 ⚠），技能质量判据要给足 state（任务描述+序列签名+结果 errno），截断会系统性误判；③ 检索 Choice 的候选数控制在 ≤10，>255 的两段式在 laos 技能规模下暂不需要。

### 4.5 四落点通用工程原则（生态共识提炼）

1. **确定性规则先行，Jev 只裁灰色地带**（pi-verdict / jev-axi / notra 的共同结构）——省成本、可审计、可回退。
2. **阈值不拍脑袋**：在自己数据上拟合 + held-out 验证 + 回归守护（jevcal 流程）；按判型分别调（Choice/Score 过信、Boolean 欠信）。
3. **fail-open / fail-closed 按伤害方向定**：安全闸 fail-closed（转人类），压缩/过滤 fail-open（保留/降权）；全部带 deadline + 超时行为明示。
4. **低置信升级不猜**：低于阈值的判决显式升级到 LLM 或人类（jev-cookbook / dsh-auto-mode / Yappy 模式）。
5. **每次 Jev 调用进审计**：请求摘要、置信度、延迟、成本各一列——与 laos "tool call 即审计" 的既有语义严丝合缝。

---

## 附录：数据来源

1. ✓ 官方：`typesafe.ai/blog/introducing-system-one-models-and-jev`；`docs.typesafe.ai`（+ quickstart / primitives / llms.txt）。抓取日期 2026-09-21。
2. ◐ corpus（`docs/research/corpus/`）：NanoJev / jevlike / simple-jev / awesome-jev 四份 README 全文精读。
3. 仓库元数据：GitHub REST API 实抓 38 条（stars/pushed_at/language/description，2026-09-21），并入 `jev_repos_curated.json`（30→68 条，按 stars 排序，已去重）。
4. 🔶 二手：36kr 报道口径（0.44s/$0.00035 每次；724 条广告 8,724 次 $0.09/40s）；OpenRouter / Cloudflare / Vercel AI Gateway 官方 X 账号宣发（经 awesome-jev 收录）。
5. ⚠ 自述数据：各仓库 README 声称的精度/延迟/成本数字均未独立复现，引用处已逐条标注。

**未决问题**（供 Task 2-5 注意）：中文 state 下的校准无公开独立测试；官方 docs 未公布 questions 数量硬上限与限流细则；输出 token 计费口径"免费"是 early access 政策，可能变化。
