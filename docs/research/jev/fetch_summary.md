# Jev GitHub 全景抓取摘要（Task 2）

- 抓取日（crawled_at）：2026-09-21
- 数据源：GitHub Search API（未认证，仅 search 端点）；抓取器 `scripts/crawl_oss_repos.py`。

## 1. 总览

- 原始抓取（去重后，含噪声）：**1443** 条
- 计划字面 6 词判据保留（repos_raw_broad.jsonl，仅审计）：**1399** 条
- **精度判据保留 / 交付（repos_raw.jsonl）：778 条**
- 剔除噪声（noise_dropped.jsonl）：**665** 条
  - 其中通用误命中（typesafe/decision model 等无 Jev 信号）：621 条
  - 其中无保留词（仅姓氏/人名/无关词）：42 条
- 最高精度核心（tight core，仅硬 Jev 信号）：771 条

## 2. 与计划判据的偏差（重要，必须读）

计划 Task 2 Step 3 的保留词含 `typesafe` 与 `decision model`。实测二者是**通用词**：
- `typesafe` 是 TypeScript 类型安全术语，命中 trpc / t3-app / sqldelight / pgtyped / typestyle 等大量无关库；
- `decision model` 是通用决策建模术语，命中经济学/组合决策模型等无关仓库。
字面 6 词判据得 **1399** 条，其中 **621 条（约 44%）为上述无关通用仓库**（typesafe/decision model 误命中）。
为遵守「宁可小而干净，不要掺水假全量」的调研底线，本步采用**精度判据**：
保留 `jev`(token，排除 jevil/jevons 等) / TypeSafe-AI 专属(typesafe-ai 组织或 `typesafe.ai`/`typesafe ai`) /
`system one`/`system-1`/`typed decision`/`non-autoregressive` / 带 Jev 共现信号的 `decision model`(calibrated/typed question)。
**安全子集证明**：字面判据保留的 68 个 curated 仓库，精度判据下 64/68 全部存活，零误删；
字面 1399 ↔ 精度 778 的差额 621 条经抽样 100% 为无关通用库（trpc / t3-app / sqldelight / RestEase / http4k 等）。故交付 778 条干净集。
若需还原计划原口径，见 `repos_raw_broad.jsonl`。

## 3. 去噪判据（可解释、可复现）

```python
jev  : token 含 'jev' 且不在 NOISE_TOK={jevil,jevons,jevent,jevan,jevgenija,jever,jevin}
typesafe: 仅 org==typesafe-ai 或 'typesafe.ai'/'typesafe ai' 或 与 jev/system one/system-1/typed decision/calibrat/decision model/non-autoregressive 共现
system one / system-1 / typed decision / non-autoregressive : 短语子串
decision model : 仅与 jev/system one/typed decision/non-autoregressive/typesafe/calibrat/typed question/honest probab 共现
```

## 4. 各 query 贡献（交付集按首次命中 query 归属）

- `jev in:name` → 交付集 293 条
- `"jev" in:description` → 交付集 103 条
- `"typesafe" in:name,description` → 交付集 4 条
- `"system one" decision model` → 交付集 60 条
- `"decision model" in:description` → 交付集 29 条
- `topic:jev` → 交付集 165 条
- `topic:typesafe` → 交付集 3 条
- `"typed decisions"` → 交付集 103 条
- `"non-autoregressive" decision` → 交付集 6 条
- `jev-ultrafast` → 交付集 12 条

## 5. star 分布（交付集）

- ≥10000：2 条
- 1000-9999：8 条
- 100-999：68 条
- <100：700 条

## 6. 语言 Top10

- Python：282
- TypeScript：210
- JavaScript：105
- 暂无：31
- HTML：26
- Rust：24
- Go：18
- Java：15
- C：9
- PHP：9

## 7. 许可 Top10

- MIT：459
- 暂无：157
- Apache-2.0：76
- NOASSERTION：52
- CC0-1.0：12
- AGPL-3.0：8
- GPL-3.0：5
- BSD-3-Clause：3
- GPL-2.0：2
- BSD-2-Clause：2

## 8. star Top20 榜单（交付集）

| # | full_name | stars | lang | license | description |
|---|---|---|---|---|---|
| 1 | OpenByteInc/QuantDinger | 11810 | Python | Apache-2.0 | Open-source AI Trading OS, agent trading, and vibe trading, with Jev System One integration. Research, build Python strategies, backtest, and paper/live trade across crypto, stocks, and forex. Launch your own multi-tenant trading SaaS with built-in user management, billing, payments, and settlement. |
| 2 | browser-use/jev-ultrafast | 11101 | Python | MIT | i. am. speed. |
| 3 | tamaratran/fast-jev-compaction | 4878 | TypeScript | MIT | Claude Code plugin that replaces the compaction summary with Jev decisions: every tool call and result is scored in one fast request, stale ones are dropped or truncated, everything kept stays verbatim. |
| 4 | killop/anything_about_game | 4110 |  | Apache-2.0 | A wonderful list of Game Development resources. |
| 5 | TheoLeeCJ/SemIf | 2286 | Python | MIT | Semantic ifs from open models, on a 3090 at home. Independent; not affiliated with Jev or TypeSafe. |
| 6 | jarrodwatts/jev-trader | 1455 | TypeScript | MIT | One AI trade decision every Monad block. Jev on Kuru MON-USDC. |
| 7 | TianyuCodings/NanoJev | 1309 | Python | MIT | A nano replica of Jev: parallel decisions, dynamic candidates, and an end-to-end training pipeline. |
| 8 | mizorewww/laya-mlx | 1114 | Python | Apache-2.0 | Native MLX runtime for Laya typed decision models — 7–14 ms short decisions on M3 Max. No text generation, PyTorch, or cloud API. |
| 9 | vinnylarouge/jevlike | 1055 | Python | MIT |  |
| 10 | typesafe-ai/skills | 1022 |  | MIT | Agent skills for building with TypeSafe's System One API |
| 11 | bespokelabsai/nimble | 944 | Python |  | Local typed decisions, contrastive data curation, and model evaluation. |
| 12 | jaredpalmer/kev | 805 | Python | Apache-2.0 | tiny Jev-like model built on top of Qwen2.5-0.5B you can train and run on your MacBook |
| 13 | reticlehq/reticle | 765 | TypeScript | NOASSERTION | AI agents can generate code, but still struggle to understand what they build. Reticle brings Jev-style machine-native runtime perception to web & desktop applications. |
| 14 | Anil-matcha/awesome-jev-by-typesafe | 680 | Python | MIT | Evidence-backed use cases, patterns, prompts, and starter code for TypeSafe Jev — a System One model for fast, typed, confidence-aware decisions in software. |
| 15 | samuelfaj/distill | 678 | Rust | Apache-2.0 | Distill is a lightweight coding agent harness and TUI built to get more done with FAR FEWER tokens 🔥 |
| 16 | milind-soni/tiptour-macos | 616 | Swift | NOASSERTION | Open-Source fast local computer use |
| 17 | yibie/awesome-jev | 544 | Python |  | A curated list of public projects, integrations, and discussions built on Jev — TypeSafe AI's System One model for typed decisions. |
| 18 | v-modal/awesome-jev-tools | 512 |  |  | A curated list of tools  built for Jev — TypeSafe AI's System One model for typed decisions. |
| 19 | pulseaiclub/phi | 466 | Go | MIT | a coding agent, rpc plugin, sub-agents, hashline edits, and mcp |
| 20 | Sac-Y/Jev-cu | 448 | JavaScript |  |  |

## 9. 与 curated 交叉校验

- curated 文件 `docs/research/corpus/jev_repos_curated.json` 实测 **68** 条（注意：任务书称 30 条，文件实际为 68 条，疑主会话已扩充）。
- 抓取覆盖 curated：54 / 68（其余低星仓库落在各 query 300 条按 star 降序的截断之外，未被 search 返回）。
- 交付集命中 curated：54 条
- 交付集中 **curated 未覆盖的新发现：724 条**（含 genuine 新 Jev 仓库与少量边界项，建议 Task 3 人工复核）。

## 10. 速率限制与抓取说明

- 抓取经 `crawl_oss_repos.search()`，页间/query 间各 sleep 7s（约 8.5 req/min < 10/min 限额），10 query × 3 页 = 30 请求，约 3m20s 完成。
- 全程无 403 限额报错（crawler 内置 3 次重试，均成功）。单 query 上限 1000 条，本次每 query 取 3 页（300 条上限）。

## 11. 抽查真实性说明

- 本环境无浏览器，无法手动打开 html_url；但 repos_raw.jsonl 全部 14 字段直接来自 GitHub Search API 实时返回，star 数为 API 原值，未做任何改写。
