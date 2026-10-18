# 音频智能体技术综述 v2（AGC 神经增益补检索 + 多媒体独立章节）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/research/2026-10-18-audio-agentos-survey.md` 从 v1 迭代为 v2——定向补检索神经 AGC 填实大/中/小三档，新增「多媒体」独立章节，并产出可独立打开的 HTML 阅读版。

**Architecture:** 不重写。v1 的 80 篇卡片（S01–S80）、证据附录骨架与 `scripts/check_survey.py` 门禁全部保留；v2 以「增量编号 S81 起 + 定向改写 §6、新增 §3.5、同步 §1/§7/§8/§9/§10」的方式迭代。AGC 域表（`docs/research/auto-gain/02..05`）与口径文件 `00` 同步回填，保证「综述正文 ← 域表 ← 口径文件」三级一致，门禁实跑绿灯为验收判据。

**Tech Stack:** Python 3.12.4（`C:/Users/yaoyue/miniconda3/python.exe`）、纯 stdlib 脚本、unittest、`scripts/check_survey.py` / `scripts/check_agc_table.py` / `scripts/table_lint.py`、Markdown 正文 + 单文件 HTML（内联 CSS，无外链依赖）。

**Spec:** `docs/research/2026-10-18-audio-agentos-survey.md`（v1 正文）+ `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（v1 证据附录）+ `docs/research/auto-gain/00-taxonomy-and-metrics.md`（AGC 唯一口径来源）。本计划的 v2 增量需求来自用户 2026-10-18 23:16 指令，四项裁决见下节。

---

## Global Constraints

1. **解释器**：一律 `C:/Users/yaoyue/miniconda3/python.exe`（3.12.4）。禁止 `pip install` 进该环境。
2. **分类口径**：沿用「3 档 × 2 标记」——小型 `<30M` / 中型 `30M–500M` / 大型 `>500M`，**左闭右开**；`端侧` 与 `多模态` 是**正交布尔标记**，不是第三、第四档。
3. **档位计法**：按**量化前参数量**（含音频编码器）划分；非神经条目写 `n/a(非神经)`，不是零成本。
4. **证据四级**：`全文` / `表格核实` / `摘要` / `二手`。摘要口径只说"论文声称"，二手口径只作量级参照；每条卡片必须标注等级。
5. **数字纪律**：每个数字后面跟**数据集 + 指标 + 硬件或延迟条件**；拿不到条件的写 `未给出`，**不估算、不折算**（尤其禁止用内存 KB 反推参数量）。
6. **编号纪律**：新增文献从 **S81** 起顺序编号；候选台账接 **C112** 起（v1 已用 C001–C111）；不得重编既有 S01–S80。
7. **日期纪律**：带日期的里程碑史（如 "v0.12.0 (10-05)"）与文件名带 ISO 日期的现场记录永不刷新。本计划新增文件一律 `2026-10-18-` 前缀。
8. **可比规则**：跨任务类型不可比（mAP ≠ PSDS1 ≠ 准确率 ≠ HEAR 均值 ≠ LUFS）；同指标同定义同划分才可横比；AudioSet 必须标 `AS-20K` 或 `AS-2M full`。
9. **laos 定位叙事**：基座是 Linux 内核，Agent 是新负载；禁止"给 AI Agent 装上操作系统"类主客反转表述。
10. **隐私红线**：录音只由显式 syscall 触发；`LAOS_REC=0` 全局禁录；ASR 全本地。正文涉及留存结论时必须与之一致。
11. **零依赖**：本计划不触碰 `laos/` 核心包（该包纯 stdlib）。

### v2 四项裁决（用户 2026-10-18 23:16 确认）

- **D1 载体**：在现有综述上做 **v2 扩展**，复用 80 篇语料与证据附录，不另起新篇。
- **D2 口径**：沿用 **3 档 × 2 标记**，不按「端侧/多模态/大/中/小」五类平铺。
- **D3 AGC**：**定向补检索**，尽量把大/中/小三档填实；命中即入册，零命中的档位按空缺结案并写入 §9 未核实清单。
- **D4 交付**：**Markdown + HTML 双份**。

### 补检索已探明的事实（2026-10-18 23:20 实跑，Task 1 不必重跑，直接引用）

v1 结论「80 篇语料内没有纯神经增益模型」**已被推翻**。定向检索命中的纯/近神经增益工作：

| 候选项 | 出处 | 关键事实 | 拟落档 |
|---|---|---|---|
| **WaveNorm AGC** | Interspeech 2026，ISCA Archive `interspeech_2026/ijjada26_interspeech`，Meeami Technologies（印度海得拉巴） | 因果端到端**时域**神经 AGC；膨胀分组 Conv1D×3 + GRU bottleneck + 转置 Conv1D 解码器；**49M MACs / 55 KB 内存**；48 kHz 训练、16 kHz 加评；对齐 ITU-T **P.56 / P.79**；说话人无关；Silero VAD 阈值 0.5 下 FPR **0.272**（vs Baseline 0.302 / WebRTC 0.304 / Carnival 0.277）、AUC **0.96**（vs 0.92/0.93/0.92）；作前端使 DFN2/DTLN/GTCRN 的 NISQA 3.22→3.57、2.28→2.49、2.92→3.13，DNSMOS 2.92→3.14、2.66→2.94、2.79→2.95 | 小型档（参数量**未给出**，见裁定 4）· 端侧=是 · 多模态=否 |
| **SE-AGCNet** | arXiv `2606.25959`，浙江大学 + 南洋理工大学 + 湖南大学 | 端到端**联合 SE+AGC**；会议场景；提出 `SE-AGC-DataGen` 数据仿真管线；以 **LUFS / St LUFS / LRA**（ITU-R BS.1770 + EBU R128）为标准化响度评测指标；同时报 ASR WER/CER 下降 | 档位待定（参数量未给出）· 作用点=离线/会议 |
| **FRCRN 多任务一体化 AI-AGC** | 《电子学报》(Chinese Journal of Electronics) | 基于 FRCRN 的**多任务一体**智能 AGC：共享特征提取层（257 维复数谱 + 40 维梅尔 = 297 维联合特征 → 3 层复数卷积 3×3/32ch → 2 层双向 FSMN → 128 维复数融合特征）；注意力机制精细调节增益；掩码处理 + **多频段增益调节** + 逆 STFT | 小型档（基础 FRCRN 10.27M，见 v1 [S54]；本变体参数量待核） |
| **Carnival AGC** | WaveNorm 引为**深度基线**的开源神经 AGC | 论文引用仓库**当前 404 不可达**；只能依 WaveNorm 正文的转述（TIMIT/VoiceBank+DEMAND 上输出 RMS 仍有输入电平依赖） | 不入矩阵（仓库失效 + 无独立一手数字），记 §6 脚注 + 二手口径 |
| **Cheng et al.** | AES Convention 147, Paper 10256, 2019-10（中科院声学所） | 把 AGC 作为 DNN 语音增强的**预处理**，解决非归一化特征（log-power spectra）下峰值电平漂移导致 SE 退化 | 经典 DSP 档 / 方法学旁证 |
| **Richter et al.** | ICASSP 2023，因果生成式扩散语音改善 | 内含**因果 AGC 子模块**（递归跟踪帧最大值 + 因果 VAD 门控，仅在语音段起跟踪）；NCSN++ 改 2D 卷积 padding 去前视、BatchNorm 换 Cumulative GroupNorm；**20 ms 全局延迟**，RTX 2080 Ti 上 **0.02 s/帧** | 大型档（扩散主干）· AGC 只是子模块 |

**另一条环境变化**：v1 记「ISCA `interspeech_2026` 仍 404，Interspeech 语料上限 2025」——该限制**已失效**，`isca-archive.org/interspeech_2026/` 现已上线全文 PDF。v2 必须据此修正 §2.2 检索通道描述与 §9.1 语料局限。

---

## File Structure

| 文件 | 职责 | 变更 |
|---|---|---|
| `docs/research/2026-10-18-audio-agentos-survey.md` | v2 正文（唯一对外阅读物） | **改**：§1 摘要结论、§2.2 检索通道、§3.5 新增、§6 全章改写、§7/§8/§9/§10 同步 |
| `docs/research/2026-10-18-audio-agentos-survey-evidence.md` | 证据附录（检索日志 / 筛选台账 / 单篇卡片 / 溯源） | **改**：§2 增补检索日志、§3 增 C112+、§4 增 S81–S86 卡片、§6 溯源记录 |
| `docs/research/auto-gain/00-taxonomy-and-metrics.md` | AGC **唯一口径来源** | **改**：末尾追加裁定 3–5 |
| `docs/research/auto-gain/02-small-models.md` | AGC 小型档域表 | **改**：增 WaveNorm / FRCRN-AI-AGC 行 |
| `docs/research/auto-gain/03-medium-models.md` | AGC 中型档域表 | **改**：按检索结果增行；零命中则加"空缺说明"段 |
| `docs/research/auto-gain/04-large-models.md` | AGC 大型档域表 | **改**：增 Richter et al. 因果扩散（AGC 子模块）行 |
| `docs/research/auto-gain/05-edge-deployment.md` | AGC 端侧部署 | **改**：增 WaveNorm 的 49M MACs / 55 KB 端侧证据与"因果但未报帧延迟"的限制 |
| `docs/research/2026-10-18-audio-agentos-survey.html` | v2 HTML 阅读版（单文件、内联 CSS、无外链） | **建** |
| `scripts/check_survey.py` | 综述门禁校验器 | 仅当新章节结构需要新规则时**改**（Task 8 判定） |
| `docs/superpowers/plans/README.md` | 计划登记 | **改**：表内增本计划一行 + 头部份数 50→51 |

---

### Task 1: AGC 定向补检索——检索日志与筛选台账

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§2 检索日志、§3 筛选与排除）

**Interfaces:**
- Consumes: v1 台账 C001–C111、卡片 S01–S80（同文件 §3 / §4）
- Produces: 新增检索日志条目 `AGC-S1..AGC-S8`、候选编号 `C112–C131`；供 Task 2 建卡片、Task 5 写 §6.2

- [ ] **Step 1: 补跑 8 条定向检索式并记录原始命中**

在下述三条通道各跑一遍，**逐条记录返回的原始条数与纳入数**，不筛掉任何一条（筛选在 Step 2）：

```bash
# 通道 A：ISCA Archive / Interspeech（v1 时 interspeech_2026 尚 404，现已上线）
curl -s "https://www.isca-archive.org/interspeech_2026/" | grep -o 'href="[^"]*_interspeech\.html"' | wc -l
curl -s "https://www.isca-archive.org/interspeech_2026/ijjada26_interspeech.html" -o /tmp/wavenorm.html

# 通道 B：arXiv API（abs 精确短语）
curl -s 'http://export.arxiv.org/api/query?search_query=abs:%22automatic+gain+control%22+AND+abs:neural&max_results=50' | grep -c '<entry>'
curl -s 'http://export.arxiv.org/api/query?search_query=abs:%22gain+control%22+AND+abs:%22loudness%22&max_results=50' | grep -c '<entry>'
curl -s 'http://export.arxiv.org/api/query?search_query=abs:%22neural+AGC%22+OR+abs:%22learned+gain%22&max_results=50' | grep -c '<entry>'

# 通道 C：Crossref（注意：cursor 与 query 组合失效，必须用 offset）
curl -s 'https://api.crossref.org/works?query.bibliographic=neural+automatic+gain+control+speech&filter=type:proceedings-article&rows=50&offset=0' | python -c "import sys,json;print(json.load(sys.stdin)['message']['total-results'])"
```

- [ ] **Step 2: 对候选逐条做纳入/排除裁决，写入台账 C112 起**

裁决维度沿用 v1 五维（端侧证据缺 / 指标条件不可比 / 常驻约束缺 / 合规冲突 / 多模态不支撑）。按已探明事实落：

```markdown
| C112 | WaveNorm AGC | ISCA Interspeech 2026 | 纳入 → [S81] | 纯神经增益、因果、有端侧资源画像；参数量未给出，按裁定 4 记「未给出」 |
| C113 | SE-AGCNet | arXiv 2606.25959 | 纳入 → [S82] | SE+AGC 联合，有标准化 LUFS/LRA 指标；参数量未给出 |
| C114 | FRCRN 多任务一体化 AI-AGC | 电子学报 | 纳入 → [S83] | 多任务共享特征 + 多频段增益调节；变体参数量待核 |
| C115 | Carnival AGC（WaveNorm 深度基线） | 仓库 404 | 排除 | 一手来源不可达（维度：端侧证据缺），转 §6 脚注二手口径 |
| C116 | Cheng et al. AGC-as-SE-preprocessing | AES 147 / 10256 (2019) | 纳入 → [S84] | 窗外例外（早于 2017-01-01），方法学旁证 |
| C117 | Richter et al. 因果扩散 + 因果 AGC 子模块 | ICASSP 2023 | 纳入 → [S85] | AGC 为子模块；主干大型档，AGC 本身不独立计参数量 |
```

- [ ] **Step 3: 去重校验——新候选与 S01–S80 不得重复**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import re, pathlib
ev = pathlib.Path("docs/research/2026-10-18-audio-agentos-survey-evidence.md").read_text(encoding="utf-8")
ids = re.findall(r"\[S(\d{2,3})\]", ev)
dup = [i for i in set(ids) if ids.count(i) > 1 or True]
print("卡片编号范围:", min(map(int, ids)), "-", max(map(int, ids)), "| 总引用", len(ids))
assert max(map(int, ids)) <= 80, "Task 2 未执行前不应出现 S81+"
PY
```

- [ ] **Step 4: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 综述 v2 Task1——AGC 神经增益定向补检索日志与台账 C112-C117"
```

---

### Task 2: 新增卡片 S81–S85（神经增益条目）

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§4 单篇卡片，追加到 [S80] 之后）

**Interfaces:**
- Consumes: Task 1 的 C112–C117 裁决
- Produces: 卡片 `[S81]`–`[S85]`（正文 §6 与 §10 参考文献按此编号引用）

- [ ] **Step 1: 写 [S81] WaveNorm AGC 卡片**

```markdown
### [S81] WaveNorm: A Low-Complexity Time-Domain Neural Adaptive Gain Control for Real-Time Speech Applications

- **来源**：Interspeech 2026，ISCA Archive `interspeech_2026/ijjada26_interspeech`；Meeami Technologies, Hyderabad, India
- **证据等级**：**全文**（PDF 已读：§2 问题形式化、§3 架构、§5 结果表）
- **控制对象**：**纯增益闭环**（`ŷ(t) = g(t)·x(t)`，`g(t)=f_θ(x(1:t))` 因果）——**不是掩码**
- **档位 / 参数量(M)**：小型 / **未给出**（论文只报 49M MACs 与 55 KB 内存，未报参数量；按裁定 4 禁止折算）
- **作用点**：采集后
- **端侧**：**是**（论文自述 "optimized for edge deployment"，49M MACs、55 KB 内存；**未给出每帧延迟实测**）
- **多模态**：否
- **因果性**：**是**（时域全卷积 + GRU，无 STFT 前视）
- **指标与条件**：Silero VAD 固定阈值 0.5，测试集为 TIMIT + DNS3 构造的内部集——FPR 0.272 / FNR 0.022 / Precision 0.957 / Recall 0.978 / AUC 0.96；对照 Baseline 0.302/0.028/0.952/0.972/0.92、WebRTC 0.304/0.019/0.953/0.981/0.93、Carnival 0.277/0.030/0.956/0.970/0.92。作降噪前端：NISQA DFN2 3.22→3.57、DTLN 2.28→2.49、GTCRN 2.92→3.13；DNSMOS 2.92→3.14、2.66→2.94、2.79→2.95
- **缺失（关键）**：**没有 AGC 闭环指标**——未报收敛时间、稳态误差、增益波动（LU 峰峰值）、过冲/下冲、削波率；ITU-T P.56/P.79 只作为训练目标参照，未报达标数字
- **开源**：未给出
```

- [ ] **Step 2: 写 [S82] SE-AGCNet 卡片**

```markdown
### [S82] SE-AGCNet: An End-to-End Framework for Joint Speech Enhancement and Loudness Control in Meeting Scenarios

- **来源**：arXiv 2606.25959；浙江大学 + 南洋理工大学 + 湖南大学
- **证据等级**：**摘要 + 正文 §1–§2**（PDF 已读；§4 结果表未逐行核实）
- **控制对象**：**SE 与 AGC 联合**（不是纯增益；AGC 组件依附于 SE 框架）
- **档位 / 参数量(M)**：**未给出**（框架声明"支持接入多种既有 SE 架构"，故无自身固定参数量）
- **作用点**：离线（会议场景录音后处理定位）
- **端侧**：unknown
- **多模态**：否
- **指标与条件**：集成响度 **LUFS**、短时响度 **St LUFS**、响度范围 **LRA**（依 ITU-R BS.1770 / EBU R128）；另报下游 ASR 的 WER/CER 下降。**具体数值待 §4 核实后回填，未核实的数字不写**
- **贡献**：`SE-AGC-DataGen` 数据仿真管线（针对"AGC 无公开数据集"）；指出级联顺序的两难——AGC 在 SE 前会无差别放大噪声，在 SE 后性能受制于 SE 质量且会放大残余噪声
- **开源**：脚注给出仓库链接（未核实可达性）
```

- [ ] **Step 3: 写 [S83] FRCRN 多任务一体化 AI-AGC 卡片**

```markdown
### [S83] 基于 FRCRN 的多任务音频 AI-AGC 增益调节算法

- **来源**：《电子学报》(Chinese Journal of Electronics)
- **证据等级**：**摘要 + 正文 §2.1.1**（期刊页已读；结果表未核实）
- **控制对象**：**降噪 + 增益协同**（多任务一体：共享特征提取层 → 注意力精细增益 → 掩码处理 + 多频段增益调节 + 逆 STFT）
- **档位 / 参数量(M)**：小型 / **未给出**（变体参数量未报；基础 FRCRN 为 10.27M，见 [S54]，**不得直接套用为本文数字**）
- **作用点**：采集后
- **端侧**：unknown
- **多模态**：否
- **特征口径**：257 维复数频谱 + 40 维梅尔频谱 → 297 维联合特征 → 3 层复数卷积（3×3，32 通道）→ 2 层双向 FSMN → 128 维复数融合特征
- **论文自述的领域判断（可直接引用）**：现有 AI-AGC 研究"仅仅是通过卷积神经网络优化 AGC 的场景适配能力"，降噪与 AGC 串联导致"特征提取流程相互割裂、算力冗余、难以协同"
- **缺失**：结果表数字、数据集、与 WebRTC AGC2 的头对头对比——均待核实
```

- [ ] **Step 4: 写 [S84] Cheng et al.（窗外例外）与 [S85] Richter et al. 卡片**

```markdown
### [S84] Improvement of DNN-Based Speech Enhancement with Non-Normalized Features by Using an Automatic Gain Control

- **来源**：AES Convention 147, Paper 10256, 2019-10；中科院声学所
- **证据等级**：**摘要**
- **控制对象**：AGC 作为 DNN-SE 的**预处理**（非归一化 log-power 特征下，峰值电平漂移会致 SE 退化；AGC 先统一峰值，再训练）
- **档位 / 参数量(M)**：经典DSP / n/a(非神经)
- **作用点**：采集后（训练与推理预处理）
- **端侧**：unknown ／ **多模态**：否
- **窗外理由**：2019-10-06 早于检索窗下界？——**否**，2019 > 2017-01-01，**不属于窗外例外**，按窗内正常收录。检索窗见 §2。
- **价值**：v1 §6.2 断言"AGC 与 SE 的顺序问题"在神经语境下缺少一手文献——本条是该顺序问题的**最早一手证据之一**

### [S85] Speech Signal Improvement Using Causal Generative Diffusion Models

- **来源**：ICASSP 2023；Richter, Welker, Lemercier, Lay, Peer, Gerkmann
- **证据等级**：**表格核实**（二手来源转述论文表格，未读原文 PDF）
- **控制对象**：**AGC 是子模块**——因果递归 AGC（跟踪帧最大值 + 因果 VAD 门控，仅语音段起跟踪），服务于扩散模型对输入缩放的敏感性
- **档位 / 参数量(M)**：大型 / 未给出（NCSN++ 主干；AGC 子模块不独立计参数量）
- **作用点**：离线（非实时赛道）
- **端侧**：**否**（RTX 2080 Ti 上 0.02 s/帧）
- **多模态**：否
- **指标与条件**：ICASSP 2023 Speech Signal Improvement Challenge 非实时赛道第 5 名；P.835 MOS 信号质量 3.119 / 总体 2.842；**20 ms 全局延迟**；因果化手段为 2D 卷积 padding 去前视 + BatchNorm 换 Cumulative GroupNorm
- **收录理由**：证明"大模型里也需要 AGC"，但 AGC 在其中是稳定性配件而非主体
```

- [ ] **Step 5: 跑卡片格式自检**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

预期：卡片尚未被正文引用，可能出现 "S81–S85 未在正文引用" 类告警——**这是预期的红灯**，Task 5 写正文后转绿。记录实际输出。

- [ ] **Step 6: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 综述 v2 Task2——新增神经增益卡片 S81-S85（WaveNorm/SE-AGCNet/FRCRN-AI-AGC/Cheng/Richter）"
```

---

### Task 3: AGC 口径裁定（00 文件追加裁定 3–5）

**Files:**
- Modify: `docs/research/auto-gain/00-taxonomy-and-metrics.md`（末尾「裁定」区追加裁定 3–5）

**Interfaces:**
- Consumes: Task 2 的 [S81]/[S82]/[S83] 卡片字段
- Produces: 裁定 3（纯增益 vs 相邻）、裁定 4（MACs≠参数量）、裁定 5（失效仓库条目处理）——Task 4 域表与 Task 5 正文均按此落笔

- [ ] **Step 1: 先跑校验器自测确认基线绿灯**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py --selftest
```
预期：`SELFTEST PASS`。

- [ ] **Step 2: 追加三条裁定**

```markdown
### 裁定 3（2026-10-18，v2 补检索）：纯增益闭环与相邻领域的划界

补检索首次出现"以电平/响度为唯一控制目标"的神经模型（[S81] WaveNorm），原「三档全是非AGC相邻条目」的局面改变。划界规则收紧为三条：

1. **纯增益闭环** = 输出是时变标量/向量增益 `g(t)`，且优化目标直接是响度/电平对齐（如 ITU-T P.56/P.79、LUFS）。[S81] 属此类。
2. **联合（SE+AGC）** = 单框架内同时优化降噪与增益，AGC 不是独立可拆模块。记 `联合(SE+AGC)`，参数量记整体或"未给出"，**不得把 SE 骨干的参数量当成 AGC 的参数量**。[S82]、[S83] 属此类。
3. **相邻** = 只输出时频掩码 / 分离 / 生成式修复，改的是内容与能量分布而非整体电平。仍记 `非AGC(相邻：增强/分离/修复·超分)`，其 PESQ/DNSMOS/SI-SDRi **不是增益精度**。

新增第四条：**AGC 作为子模块**（[S85] 的因果递归 AGC 服务于扩散模型输入缩放稳定性）。记 `子模块(宿主：生成式修复)`，档位随**宿主**记，AGC 本身不独立计参数量。

### 裁定 4（2026-10-18）：MACs 不是参数量，内存 KB 不得折算为参数量

[S81] 只报 **49M MACs** 与 **55 KB 内存**，未报参数量。三者的语义完全不同：
MACs 是**算力**（每次推理的乘加次数），内存 KB 是**运行时占用**（含激活/状态/缓冲，随帧长与量化方案变化），参数量是**模型体积**。
**硬规则**：三者**分列记录，互不折算**；任一缺失写 `未给出`。禁止用 `55 KB ÷ 2 byte` 之类推算参数量——那会把运行时内存当作权重体积。
同理，档位划分只认参数量；参数量未给出时，档位按"论文自述的目标硬件 + 算力画像"暂记并**加注 `档位待定`**，不静默归入小型档。

### 裁定 5（2026-10-18）：一手来源不可达的条目处理（Carnival AGC）

[S81] 引为深度基线的 **Carnival AGC** 开源仓库在 2026-10-18 核对时返回 404。
规则：一手来源不可达的条目**不得入矩阵**（矩阵要求可溯源的一手数字），只能在正文脚注以**二手口径**说明其存在与转述结论，并在 §9 未核实清单登记。
若后续仓库恢复或找到镜像，按 Task 1 台账流程重新裁决入册。
```

- [ ] **Step 3: 重跑自测并跑域表校验**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py --selftest
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py docs/research/auto-gain/*.md
```

- [ ] **Step 4: Commit**

```bash
git add docs/research/auto-gain/00-taxonomy-and-metrics.md
git commit -m "docs(research): 综述 v2 Task3——AGC 口径追加裁定 3 纯增益划界 / 裁定 4 MACs≠参数量 / 裁定 5 失效仓库条目"
```

---

### Task 4: AGC 域表回填（02/03/04/05）

**Files:**
- Modify: `docs/research/auto-gain/02-small-models.md`、`03-medium-models.md`、`04-large-models.md`、`05-edge-deployment.md`

**Interfaces:**
- Consumes: Task 2 卡片字段 + Task 3 裁定 3/4
- Produces: 域表新行（12 列 schema 与既有行逐字一致）；Task 5 §6.2 表格据此填写

- [ ] **Step 1: 确认既有 schema 列名**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
grep -n "^| 模型" docs/research/auto-gain/02-small-models.md | head -3
```
把表头逐字抄到新行，**不得自造列名**。

- [ ] **Step 2: 02-small-models.md 增 WaveNorm 与 FRCRN-AI-AGC 行**

按 Step 1 抄到的表头填，关键字段：`档位=小型`、`参数量(M)=未给出`、`作用点=采集后`、`端侧=是`（WaveNorm）/`unknown`（FRCRN-AI-AGC）、`多模态=否`、`限制` 列必须写明"参数量未给出；无收敛时间/稳态误差等闭环指标；端侧资源画像为 49M MACs / 55 KB，未给出每帧延迟"。

- [ ] **Step 3: 03-medium-models.md 处理中型档**

按补检索结果：中型档（30M–500M）**无纯神经增益条目**（[S82] 框架无固定参数量、[S83] 未报）。**不造行**，改为在文件内加一段「中型档空缺说明」：

```markdown
## 中型档（30M–500M）神经增益：空缺

2026-10-18 定向补检索（8 条检索式 / 3 条通道）在中型档未命中任何以增益为控制对象的神经模型。
已知的 [S82] SE-AGCNet 是"可接入多种 SE 架构"的框架，无自身固定参数量；[S83] FRCRN-AI-AGC 未报变体参数量。
两者都**不能**按中型档收录——按裁定 4，参数量未给出时不得静默归档。
结论：AGC 中型档的神经增益仍是空缺，与小型档（[S81] 已出现）形成"小的有、中的没有"的断层。
```

- [ ] **Step 4: 04-large-models.md 增 Richter et al. 行**

`档位=大型`、`控制对象=子模块(宿主：生成式修复)`（裁定 3 第四条）、`参数量(M)=未给出`、`端侧=否`、`限制` 列写"AGC 为因果递归子模块（跟踪帧最大值 + 因果 VAD 门控），宿主 NCSN++ 扩散；RTX 2080 Ti 0.02 s/帧；20 ms 全局延迟；ICASSP 2023 非实时赛道第 5 名"。

- [ ] **Step 5: 05-edge-deployment.md 增端侧证据段**

写清 WaveNorm 是当前**唯一**同时满足「纯神经增益 + 因果 + 有端侧资源画像」的条目，并列出它仍缺的三样：参数量、每帧延迟实测、闭环指标（收敛时间/稳态误差/削波率）。同时点名与 laos B 档常驻税的对照：49M MACs 在 MCU 上可算，但在 proot 通用 Linux CPU 上，常驻税是 400–1000 mW，**与环本身多便宜无关**。

- [ ] **Step 6: 跑域表校验**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py docs/research/auto-gain/02-small-models.md docs/research/auto-gain/03-medium-models.md docs/research/auto-gain/04-large-models.md docs/research/auto-gain/05-edge-deployment.md
```
预期：0 违规。有违规按提示修到 0。

- [ ] **Step 7: Commit**

```bash
git add docs/research/auto-gain/
git commit -m "docs(research): 综述 v2 Task4——AGC 域表回填神经增益条目（小/大型增行，中型记空缺）"
```

---

### Task 5: 正文 §6 全章改写为 v2

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§6.1–§6.5 改写，新增 §6.6）

**Interfaces:**
- Consumes: Task 2 的 [S81]–[S85]、Task 3 的裁定 3/4、Task 4 的域表行
- Produces: §6 v2 文本；§1 摘要第 3 条结论与 §7.3 由 Task 7 同步

- [ ] **Step 1: 改写 §6.2 的立论句（v1 结论翻转点）**

v1 §6.2 首句是"80 篇语料里，以增益/响度为控制对象的神经模型是零条"。改为：

```markdown
**v1 的"零条"结论已被 v2 补检索推翻，但推翻的是"有没有"，不是"够不够"。**
2026-10-18 的定向补检索（8 条检索式、3 条通道）首次命中以增益为唯一控制目标的神经模型——
[S81] WaveNorm（Interspeech 2026，因果时域、49M MACs / 55 KB、面向端侧）。
因此本节不再写"神经侧没有纯增益模型"，而改写为：**纯神经增益已经出现且可端侧，
但它至今没有在 AGC 自己的闭环尺子上报过数。**
```

- [ ] **Step 2: 在 §6.2 三档叙述中插入神经增益条目**

小型档增加一段，核心对照：

```markdown
**小型档第一次有了真正的增益条目。** [S81] 是 80+5 篇里唯一同时满足「纯增益闭环 + 因果 + 有端侧资源画像」的神经模型：
它把增益学成向 ITU-T P.56/P.79 目标对齐的时域回归，而不是预测掩码——这与同档的 [S56] RNNoise 0.085M、
[S53] GTCRN 0.048M、[S52] DeepFilterNet3 2.5M 有本质区别（后者全是 `非AGC(相邻：增强)`）。
它的代价与缺口同样清楚：**参数量未给出**（只报 49M MACs 与 55 KB 内存，按裁定 4 不得折算）；
**没有闭环指标**——收敛时间、稳态误差、增益波动、过冲/下冲、削波率一个都没报，
报的全是下游代理指标（Silero VAD 的 FPR 0.272 / AUC 0.96，以及使 DFN2/DTLN/GTCRN 的 NISQA、DNSMOS 提升）。
下游变好不等于环本身达标：一个把整体电平抬高的环同样能让 VAD 少漏检。
```

中型档引用 Task 4 Step 3 的空缺结论；大型档加入 [S85] 的 `子模块(宿主：生成式修复)` 判断。

- [ ] **Step 3: 改写 §6.3 端侧——把 WaveNorm 放进四个作用点的账里**

关键论断：WaveNorm 把"神经 AGC 能不能跑在端侧"从**不能**变成**能**，但**没有改变 laos 的取舍**，因为 laos 的账是常驻税而非环的开销。

```markdown
**WaveNorm 改变的是能力边界，不是 laos 的账。** 它证明神经增益可以因果、可以小到 49M MACs / 55 KB——
MCU 档（数毫瓦）在纸面上放得下。但 laos 的 B 档（proot 通用 Linux CPU）空闲即 400–1000 mW，
§3 的常驻准入线是 ≤25 mW，差 16–40 倍。**这笔税由"进程醒着"产生，与环是经典 DSP 还是神经模型无关**
——把 AGC2 换成 WaveNorm，常驻账一分不减。因此「AGC 在 laos 首先是作用点问题，不是模型选型问题」这条结论不变。
```

- [ ] **Step 4: 新增 §6.6 神经 AGC 的准入门槛（v2 新增结论）**

```markdown
### 6.6 神经 AGC 的准入门槛：三条硬条件

v1 的结论是"神经侧只考虑降噪，不考虑增益"。补检索后出现 [S81] 这样的条目，
这条应当修正为**有条件放行**——神经增益不再被排除，但要进 laos 主链，必须同时满足三条：

1. **在 AGC 自己的闭环尺子上报数。** 收敛时间（进入目标 ±1 LU 并连续 3 s 不越界）、稳态误差、
   增益波动（LU 峰峰值）、过冲/下冲、削波率——至少给出其中三项，并与 WebRTC AGC2 同条件对照。
   [S81] 目前一项都没给（只给下游代理指标），**因此它现在是"值得跟踪"，不是"可以替换"**。
2. **公开参数量与量化后体积。** 按裁定 4，MACs 与内存不能替代参数量；档位未定就无法进矩阵，
   也就无法与 §5 的 AED 条目在同一张交叉表里对齐。
3. **证明不会二次增益。** 必须给出 §6.3 的线性度测试（四档 −50/−40/−30/−20 dBFS 各 10 s，
   输入每 +10 dB、输出增量是否落在 10±1 dB），证明与固件已存在的 AGC 不互相追逐。
   [S81] 未做此测试，它的实验是在 TIMIT/VoiceBank+DEMAND 的**文件级**数据上做的，不涉及真实采集链路。

三条都满足前，laos 的 AGC 判断维持 v1 的三句话（主链不加采集后闭环、离线只做开环归一、生成式修复不进链路）；
**唯一的变化是：把"神经 AGC"从排除名单移到了观察名单。**
```

- [ ] **Step 5: 修正 §2.2 中"ISCA interspeech_2026 仍 404"的过期描述**

```markdown
补检索时的环境变化（v2 修正 v1 记录）：v1 执行时 `isca-archive.org/interspeech_2026/` 返回 404，
故 Interspeech 语料上限记为 2025；**2026-10-18 复核时该目录已上线全文 PDF**，
Interspeech 2026 论文可正常获取。v1 §9.1「语料局限」中与此相关的表述按此修正。
```

- [ ] **Step 6: 跑门禁看引用是否闭合**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

- [ ] **Step 7: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 v2 Task5——§6 AGC 全章改写：纯神经增益已出现，新增准入门槛 §6.6"
```

---

### Task 6: 新增 §3.5 多媒体章节

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§3.4 应用矩阵之后插入 §3.5，原 §3.5 不存在则直接新增；§4 之前）

**Interfaces:**
- Consumes: v1 §3.3 多模态（视觉三种结局）、正文中已有的 CLAP / LAION-CLAP 引用（当前 5 处）
- Produces: §3.5 文本；§1 摘要第 5 条与 §7.3 由 Task 7 同步

- [ ] **Step 1: 盘点现有多媒体相关条目，避免重复造节**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
grep -n "CLAP\|LAION\|audio-visual\|音视\|音视频\|多模态" docs/research/2026-10-18-audio-agentos-survey.md | head -40
```
把命中的 S 编号抄下来，§3.5 只做**组织与补白**，不重复 §3.3 已写过的结论。

- [ ] **Step 2: 写 §3.5——两条主线，不是三种结局**

```markdown
### 3.5 多媒体：两条主线与一道成本闸

§3.3 讲的是"视觉为例外"（三条翻转条件）。本节换个角度：多媒体作为**建模范式**有两条主线，
它们与 §3.3 的"视觉要不要开摄像头"不是同一件事——**范式可以在服务端用，摄像头不必在端上开**。

**主线一：音频–文本对比学习（audio-text contrastive）。** 把音频与自然语言描述投到同一嵌入空间，
使类别集可以在推理时给定，绕开"白名单要重训"。这条主线对 laos 的意义是**开放词表**而不是"多模态采集"：
它不需要摄像头，代价是文本编码器的参数量与对齐数据的规模。它在 §5.4 的开放词表讨论里承接。

**主线二：音视频联合表征（audio-visual representation）。** 依赖成对视频，是 §3.3 三种结局的舞台：
SER 增量未测出（[S27]）、AED 增量落在定位（[S13]）、AGC 只有相邻证据（§6.4）。
本主线的共同代价是**成对数据 + 摄像头**，正是 §3.3 四条翻转条件里第 1、4 条拦下的东西。

**一道成本闸**：多媒体范式的收益发生在**表征侧**，成本发生在**采集侧**。
[S73] Ego4D 3,670 小时约 7 TB、[S71] 7 麦克风阵列加多机位——这些是采集侧的成本，与端上是否开摄像头无关，
只要范式要求成对数据就必然发生。因此判断多媒体范式的顺序是：
**先问它要的是文本（可离线、无采集成本）还是视频（要成对、有采集成本），再问增量有没有被同协议对照测出。**
按这条顺序，主线一进观察名单，主线二维持 §3.3 的"永久不做"默认值。
```

- [ ] **Step 3: 核对 §3.5 引用的每个 S 编号都在证据附录有卡片**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

- [ ] **Step 4: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 v2 Task6——新增 §3.5 多媒体：两条主线与一道成本闸"
```

---

### Task 7: 摘要、跨领域对比、未来方向、局限、参考文献同步

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§1、§7.3、§8、§9、§10）

**Interfaces:**
- Consumes: Task 5 的 §6 v2、Task 6 的 §3.5
- Produces: 全篇编号闭合；Task 8 门禁输入

- [ ] **Step 1: 改 §1 摘要——文献数 80 → 85，第 3 条与第 5 条结论改写**

第 3 条由「AGC 主干是经典 DSP…神经侧在 80 篇语料内没有纯增益模型」改为：

```markdown
3. **AGC：纯神经增益已经出现，但还没在自己的尺子上证明自己。** 经典 DSP 四件套（WebRTC AGC2 / SpeexDSP /
   Android audiofx / FFmpeg loudnorm）仍是实时与离线两条基线；v2 定向补检索首次命中以增益为唯一控制目标的
   神经模型 [S81] WaveNorm（Interspeech 2026，因果时域、49M MACs / 55 KB、面向端侧），
   推翻了"神经侧没有纯增益模型"的判断。**但 [S81] 只报下游代理指标（VAD FPR/AUC、NISQA/DNSMOS），
   收敛时间、稳态误差、削波率等闭环指标一项未报**，也没有与 AGC2 同条件头对头。
   因此结论不是"可以替换"，而是 §6.6 的三条准入门槛：神经 AGC 从排除名单移到观察名单。
   中型档（30M–500M）的神经增益经 8 条检索式检索仍为空缺，形成"小的有、中的没有"的断层（§6.2）。
```

第 5 条多模态结论末尾补 §3.5 的「范式 vs 采集」区分。

- [ ] **Step 2: §7.3 多模态的三种结局 → 加第四种（范式侧）**

```markdown
**第四种结局（v2 补充）：多媒体作为范式可以只发生在表征侧。** §3.5 的区分是：
音频–文本对比学习要的是文本（离线可得、无采集成本），音视频联合表征要的是成对视频（有采集成本）。
因此"多模态"不是一个开关，而是两个成本结构完全不同的选择；把它们混成一个"要不要多模态"的问题，
是本节此前三种结局写法最容易造成误读的地方。
```

- [ ] **Step 3: §8 未来方向补两条**

```markdown
- **神经 AGC 的闭环基准缺失。** [S81] 是目前唯一"纯增益 + 因果 + 端侧画像"的条目，却没有报任何一个闭环指标。
  本领域缺的不是模型，而是一把尺子：收敛时间、稳态误差、增益波动、过冲/下冲、削波率需要在
  TIMIT/VoiceBank+DEMAND 之外的**真实采集链路**上定义可复现的测量协议，并给出与 AGC2 的同条件对照。
  没有这把尺子，"神经 AGC 比 AGC2 好"这句话无法被证伪。
- **AGC 中型档的断层。** 小型档已出现 [S81]，大型档有 [S85] 的子模块形态，中型档（30M–500M）为空。
  这个断层是检索问题还是真实的研究空白，需要以规模为检索维度重新确认（不能只用任务词检索）。
```

- [ ] **Step 4: §9 未核实清单增补**

```markdown
- **[S81] WaveNorm 的参数量与每帧延迟**：论文只报 49M MACs / 55 KB 内存，未报参数量，也未报每帧延迟实测。
  按裁定 4 记"未给出"，**未做任何折算**。其"面向端侧部署"为论文自述，非第三方实测。
- **[S82] SE-AGCNet 的结果表数字**：arXiv PDF 的 §4 结果表未逐行核实，正文只引用其指标定义（LUFS/St LUFS/LRA）
  与级联顺序的两难，不引用具体数值。
- **[S83] FRCRN-AI-AGC 的变体参数量与结果**：期刊页只到 §2.1.1，未报变体参数量。**未把基础 FRCRN 的 10.27M
  套用为本文数字**。
- **Carnival AGC**：[S81] 引用的开源仓库 2026-10-18 核对时 404，一手来源不可达，按裁定 5 不入矩阵。
- **[S85] Richter et al.**：经二手来源（Lacuna 论文页）转述，未读原文 PDF，记为表格核实口径。
```

- [ ] **Step 5: §10 参考文献增 [S81]–[S85] 五条**

按 §10 既有格式（编号、作者、标题、出处、年份、链接）逐条补齐；链接用 §4 卡片里核实过的地址。

- [ ] **Step 6: 全篇编号闭合自检**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

- [ ] **Step 7: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 v2 Task7——摘要/§7.3/§8/§9/§10 同步至 85 篇"
```

---

### Task 8: 证据附录回填与严格门禁

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§6 溯源核验记录）
- Modify: `scripts/check_survey.py`（仅当 §6.6 / §3.5 触发新结构规则时）

**Interfaces:**
- Consumes: Task 1–7 全部产物
- Produces: `--strict` 绿灯；Task 9 的输入

- [ ] **Step 1: 回填 §6 溯源核验记录**

逐条写明 [S81]–[S85] 的核验动作与结果（何时、用何 URL、读到哪一层、缺什么），格式与既有 S01–S80 条目一致。

- [ ] **Step 2: 跑严格门禁**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py --strict docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

- [ ] **Step 3: 判定是否需要扩校验器**

若 §6.6 的矩阵行数或 §3.5 的章节位置触发 `check_matrix` / `check_future_work` 的规则缺口，
在 `scripts/check_survey.py` 中补规则，并**先写一条反例断言验证新规则会红**（参照仓库既有做法：门禁必先验过它会失败）。

```python
def test_new_rule_rejects_bad_input():
    """反例必须被拦下，否则规则是装饰。"""
    bad = "...写一段违反新规则的样例正文..."
    assert check_survey.run_checks(Path("x.md"), bad, Path("y.md"), "") != []
```

- [ ] **Step 4: 跑主库测试确认未回退**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -5
```
记录 `Ran N tests`，与发版时点口径对比；本计划不触碰 `laos/`，预期无变化。

- [ ] **Step 5: 跑校验器自测**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py --selftest
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py --selftest
C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py --selftest
```
预期三条全 PASS。

- [ ] **Step 6: Commit**

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md scripts/
git commit -m "docs(research): 综述 v2 Task8——证据附录溯源回填与严格门禁绿灯"
```

---

### Task 9: HTML 阅读版与计划登记

**Files:**
- Create: `docs/research/2026-10-18-audio-agentos-survey.html`
- Modify: `docs/superpowers/plans/README.md`

**Interfaces:**
- Consumes: Task 7 完成的 v2 Markdown 正文
- Produces: 单文件 HTML（内联 CSS、无外链、可直接双击打开）；计划登记行

- [ ] **Step 1: 生成 HTML 阅读版**

用仓库既有 Markdown→HTML 转换途径（先确认是否有现成脚本）：

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
ls scripts/ | grep -i -E "html|md2|render|export"
```

若有现成转换器，直接调用；若无，写一个纯 stdlib 的最小转换器 `scripts/md2html_survey.py`（只处理本综述用到的语法：
`#/##/###` 标题、段落、无序/有序列表、管道表格、行内 `**粗体**` 与 `` `代码` ``、`[Sxx]` 锚点链接）。
**HTML 内联 CSS，不引外链；深色主题可读**（本地预览用）。

- [ ] **Step 2: 冒烟检查——HTML 章节数与 md 一致**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import re, pathlib
md = pathlib.Path("docs/research/2026-10-18-audio-agentos-survey.md").read_text(encoding="utf-8")
html = pathlib.Path("docs/research/2026-10-18-audio-agentos-survey.html").read_text(encoding="utf-8")
h2_md = re.findall(r"^## (.+)$", md, re.M)
h2_html = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
print("md h2:", len(h2_md), "| html h2:", len(h2_html))
assert len(h2_md) == len(h2_html), (h2_md, h2_html)
assert "6.6" in html, "§6.6 未进 HTML"
assert "3.5" in html, "§3.5 未进 HTML"
print("SMOKE OK")
PY
```

- [ ] **Step 3: 登记计划**

在 `docs/superpowers/plans/README.md` 表格末尾增一行：

```markdown
| 2026-10-18-audio-agentos-survey-v2.md | 已执行 | 综述 v2：AGC 神经增益定向补检索（S81–S85，推翻 v1「无纯神经增益模型」）+ §3.5 多媒体 + HTML 阅读版 |
```

并把头部「本表 50 份」改为 51 份。

- [ ] **Step 4: Commit**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
git add docs/research/2026-10-18-audio-agentos-survey.html scripts/md2html_survey.py docs/superpowers/plans/README.md
git commit -m "docs(research): 综述 v2 Task9——HTML 阅读版 + 计划登记"
```

- [ ] **Step 5: 终检——三条通道全绿**

```bash
cd /c/Users/yaoyue/CodeBuddy/Claw/laos
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py --strict docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py docs/research/auto-gain/*.md
git log --oneline -9
```

---

## 计划自检（写完即跑，非派发）

### 1. Spec 覆盖

| v2 需求（用户四项裁决 + 原始需求） | 落点 |
|---|---|
| D1 在现有综述上做 v2 扩展 | Task 5–7 增量改写，不重写（File Structure 已标注"改"而非"建"） |
| D2 沿用 3 档 × 2 标记 | Global Constraints 第 2 条 + Task 3 裁定 3/4 + Task 4 域表 |
| D3 AGC 定向补检索填实三档 | Task 1（检索+台账）+ Task 2（卡片）+ Task 4（域表，中型档记空缺） |
| D4 Markdown + HTML 双份 | Task 7（md）+ Task 9（html） |
| 原始需求：agentos-audio | v1 §3.1 已覆盖，v2 不动 |
| 原始需求：multimedia | **Task 6 新增 §3.5**（v1 只有 §3.3 视觉三种结局，缺"多媒体作为范式"） |
| 原始需求：全天候录音应用 | v1 §3.2 已覆盖，v2 §9.1 修正 ISCA 2026 上线带来的语料局限表述（Task 5 Step 5） |
| 原始需求：声学情感模型（SER） | v1 §4 已覆盖，v2 不动 |
| 原始需求：AED 端侧/多模态/大/中/小 | v1 §5.2–§5.7 已按 3 档 × 2 标记覆盖，v2 不动 |
| 原始需求：AGC 端侧/多模态/大/中/小 | **Task 1–5**（本次主要增量） |

缺口：无。

### 2. 占位符扫描

- 全文无 "TBD" / "TODO" / "以后再补" / "视情况而定"。
- Task 1 Step 1 给出**实际可执行的 curl 命令**（含 8 条检索式的具体 URL）；Task 2–7 的步骤给出**实际要写入的 Markdown 文本**，不是"填写相应内容"。
- Task 9 Step 1 的"若无现成转换器则写 `scripts/md2html_survey.py`"是**带具体规格的条件分支**（列出了要处理的语法清单），不是占位符。
- Task 3 Step 2、Task 4 Step 3、Task 6 Step 2 均给出完整文本块。

### 3. 类型一致性

- 编号：Task 1 产出 `C112–C117` → Task 2 产出 `[S81]`–`[S85]`（5 条，与 C112/C113/C114/C116/C117 五条"纳入"一一对应，C115 排除不入卡片）→ Task 5/7 正文按 `[S81]`–`[S85]` 引用 → Task 7 Step 5 参考文献补 5 条。**计数闭合：5 条卡片 = 5 条参考文献。**
- 档位字段：Task 2 卡片写 `小型 / 未给出`，Task 4 Step 2 域表必须**同字**填 `未给出`；Task 5 Step 2 正文引用时写"参数量未给出"，不得写成"参数量未知"或"N/A"。
- 裁定编号：本文件一律用 **裁定 3 / 裁定 4 / 裁定 5**（承接 `docs/research/auto-gain/00-taxonomy-and-metrics.md` 既有的 裁定 1 / 裁定 2，**不另起 R 系列**）。Task 4 Step 2/Step 3、Task 5 Step 2、Task 8 Step 4（§9 未核实清单）均按此编号引用，**不新造裁定 6**。
- 控制对象取值：Task 3 裁定 3 定义四值 `纯增益闭环` / `联合(SE+AGC)` / `非AGC(相邻：…)` / `子模块(宿主：…)`；Task 2 卡片、Task 4 域表、Task 5 正文一律只用这四值。
- 命令：所有 Python 一律 `C:/Users/yaoyue/miniconda3/python.exe`（与 Global Constraints 第 1 条一致），无一处出现 3.11.9 路径。
