# Interspeech 2026 语音增强（SE）技术风向 —— 微信公众号文章学习与溯源

> 来源：微信公众号「声息实验室」《Interspeech 2026 语音增强技术风向》，
> <https://mp.weixin.qq.com/s/psx7S5bsf4pNSvrvBypZ_Q>（2026-10-09 发布）。
> 取件通道：WebFetch 被微信验证墙拦截（"当前环境异常"）；webReader 服务器侧取件成功，
> 全文到手（纯文字正文自足，无逐图 OCR 依赖）。
> 消费：本文自足；与 laos 语音三域调研线（`auto-gain/`、`audio-events/`、`speech-emotion/`）
> 及 wakegate/dialogsched/wer 代码资产对照。
> 产出：六风向整理 + 逐条 laos 映射与裁决（§4），代码零改动（纯学习波）。

---

## §0 溯源与核实等级（来源诚实）

| 项 | 等级 | 依据 |
|---|---|---|
| 文章全文取到 | ● | webReader 全文，正文完整（标题/正文/结论俱全），非标题级浏览 |
| 内部数字自洽 | ● | 分项 67（SE）+29（TSE/分离）+10（ANC/声区/丢包）+9（评测）= **115** ✓ |
| Enroll-on-Wakeup 论文 | ● | 独立证实：arXiv:2602.15519（云知声 Unisound），"wake-word segment as enrollment clue" 与文章转述一致；Interspeech 2026 wiki 有条目 |
| SBM 论文（文章头牌） | ● | 独立证实：arXiv:2510.16834（华为团队，Interspeech 2026 录用，papers.cool `yang26e@interspeech_2026`），Schrödinger Bridge + Mamba + 一步增强三要素一致 |
| 其余 ~12 篇论文细节 | ◐ | 仅文章转述（EffDiffSE+ / ADDSE / StuPASE / UniSE / ETH GSPO / LaCo-SENet / NTT 延迟适配器 / RT-SEMamba / 皮肤加速度计 SE / Hamburg / Fraunhofer / Ouroboros），未逐篇核验；引用时均标 ◐ |
| EoW 署名细节 | ◐ | 文章称"上海师范大学+云知声"；arXiv/wiki 机构显示 Unisound AI Technology（云知声英文名）——存在合作署名可能，未逐作者核验 |

> 本文性质：二手转译综述（公众号对 115 篇论文的编辑性归纳）。两篇对 laos 最要害的
> 论文已抽检为真（●），其余按 ◐ 引用；文章的**归纳性论断**（如"没有新的统一架构"）
> 属作者观点，引用时注明。

---

## §1 文章骨架

- **规模**：Interspeech 2026 语音增强主题 15 个 session / **115 篇**论文；
  ISCA Archive 该索引下共 1,379 条。
- **文章总判断**：今年**没有出现新的统一架构**；工程约束（延迟 / 算力 / 传感器）第一次
  与指标（PESQ 等）平起平坐成为一等公民；评测、训练、安全三方面都在被质疑；
> "驱动这一切的，是把模型放进设备。"

## §2 六大风向整理

### 2.1 一步生成式增强（扩散步数压缩）● 定性 / ◐ 细节

扩散模型增强质量好但多步采样慢 → 全场都在压步数：

| 工作 | 机构 | 手法 |
|---|---|---|
| SBM | 华为 | Schrödinger Bridge + Mamba，**一步**去噪+去混响，流式 RTF（arXiv:2510.16834 ●） |
| EffDiffSE+ | TU Braunschweig + Goodix | 单次迭代扩散 + 可学习 Schrödinger bridge |
| ADDSE | DTU | 吸收态离散扩散，在神经编解码码本空间做增强 |

**MeanFlow 一年内铺开四个方向**（◐：MeanFlow-TSE 哥伦比亚大学、MeCo KAIST 多通道、波形生成、零样本 VC）——方法学扩散速度本身是个信号：单步建模思想正在成为生成式语音的公共底座。

### 2.2 幻觉记账（hallucination accounting）● 定性 / ◐ 细节

生成式增强音质好但会**编出没说过的话**，今年成了显式研究方向：

- **StuPASE**（NJU+Cisco+地平线）：Low-Hallucination 路线——对 PASE 做 dry-target 微调 + 用 flow-matching 替代 GAN；
- **UniSE**（阿里 Qwen）：decoder-only 自回归语言模型统一"修复/抽取/分离"三任务 + 渐进式 RL；
- **ETH Zurich**：GSPO 后训练，把 DNSMOS/WER/UTMOS 等**不可微指标直接当奖励**；
  关键发现：**单指标训练会 reward hacking，多指标复合在人类评测里赢过任一单指标**。

### 2.3 延迟成为旋钮（latency as a knob）◐

不是"越低越好"而是"一个模型覆盖多档延迟"：

- **LaCo-SENet**（POSTECH+Intus）：1.37M 参数家族覆盖 12.5–75ms；12.5ms 因果档 PESQ 3.35 **反超**此前 46.5ms 档最好成绩 3.27；
- **NTT**：延迟控制适配器，一个模型 7 档延迟模式，质量反超逐档训练且省 76% 参数；
- **RT-SEMamba**（中研院+NTU+NVIDIA）：因果时频 Mamba + 渐进蒸馏 8 层→1 层。

### 2.4 真实场景（real-world scenarios）● 定性 / ◐ 细节

- **Enroll-on-Wakeup（EoW）**（上海师大+云知声；arXiv:2602.15519 ●）——对 laos 最要害的一篇：
  **用唤醒词那一段音频自动当说话人注册参考**做目标说话人抽取（TSE），免专门注册。
  论文性质是**问题定义+首个对照研究**（5 种真实声学条件），结论是**现有 TSE 模型在该设定下普遍降级**；用 LLM-TTS 增强注册音可改善听感但 WER 差距仍在。
- **POSTECH 皮肤加速度计辅助 SE**：46K 参数，比传声器方案小 68×，可穿戴 MCU 上 48.66ms/帧；
- 无人机自噪声、穿墙雷达、毫米波雷达辅助——**非声学传感器辅助增强**成小潮流。

### 2.5 播放侧与无净语料训练 ◐

- 播放侧 10 篇：ANC / 个人声区 / 丢包隐藏（耳机与车载）；
- 无净语料（no-clean-speech）训练：内蒙古大学文本标注噪声监督双学习；南科大混响目标 + DSP→神经网络蒸馏的无监督去混响。

### 2.6 泼冷水面（对整个领域的自我质疑）◐

| 工作 | 泼的冷水 |
|---|---|
| Hamburg 大学 "Too Good to Be True" | **ASR 当评测器不可靠**——ASR 越强对声学质量差异越不敏感；transducer 最可靠但其鲁棒性又让它失明 |
| Fraunhofer "Screening Matters" | 众包听测可经事后+连续筛查挽救；**1,379 篇里标题含听测的只有 1 篇** |
| 宁波大学 Ouroboros | **SE 模型后门攻击**：以"干净理想输出"为天然触发器，存活于过滤与微调，可定向篡改内容——SE 是链路最前模块，污染它等于污染下游一切 |
| 分数压缩 | 因果档 PESQ 头部挤在 3.27–3.43，区分度递减——听测/真实场景/部署成本比分数更要紧 |

---

## §3 与 laos 资产对照

### 3.1 EoW ↔ WakeGate + 四段漏斗（本篇头条收获）

laos 侧事实：`laos/wakegate.py:156` KWS 命中唤醒词只在 Sleeping 态触发迁移——
**唤醒词那一段音频目前用完即弃**。EoW 范式说明这段音频有第二用途：**免费的说话人注册音**
（用户说唤醒词的那 1–2 秒就是"我是谁"的声学凭证），可喂给 TSE 做说话人自适应增强，
正好落在四段漏斗第①段（唤醒）与第③段（转写）之间。

但**不落地**，理由两条：
1. EoW 论文自身结论是"现有模型在此设定下普遍降级"——这是问题定义论文，不是解法论文；
   立刻接只会引入降级。
2. laos 当前 B 档（proot CPU）没有 TSE 模型可跑的算力位（同 `audio-events/07-adoption.md`
   §2.1 的判定口径）。

**触发条件登记**（与 AEC3 驱动子进程波 R5 同波评估）：端侧真机波（A 档）落地后，
若 ASR 通道在多说话人场景实测 CER 劣化，再评估"唤醒段→注册音→TSE"链路。

### 3.2 幻觉记账 ↔ auto-gain/04 红线（外部印证，红线不动）

`auto-gain/04-large-models.md:24` 红线原文：**"生成式修复不得进入会产生记忆的链路"**。
Interspeech 2026 把这件事升级成了显式研究方向（StuPASE 专做 Low-Hallucination、
UniSE 把修复/抽取/分离统一进一个可问责框架）——**增强社区自己承认生成式增强会编造语音内容**，
laos 红线获得学界正面印证，且从"直觉红线"升级为"有文献支撑的红线"。

副产品：**ETH 多指标复合奖励防 reward hacking** 的思想与 laos JitMem bandit 的 reward
设计同构（即时成败 reward 已有；若未来加多维 reward，必须复合，不能单指标——单指标必被
钻空）。登记为 reward 设计参考，当前无改动需求。

### 3.3 延迟旋钮 ↔ dialogsched 预算家族（同构互证，零改动）

NTT"一个模型多档延迟、质量反超逐档训练"与 laos `laos/dialogsched.py` 的
PauseWindow/延迟预算参数化是同一思想在模型侧与治理侧的各自表达：**延迟不是常量，
是被治理的预算**。互证记录，无需改动。

### 3.4 ASR-as-judge 不可靠 ↔ wer.py 评测口径（盲区警示）

laos 的 WER/CER 框架（`laos/wer.py`，agenticasr/refiner 评测用）若用 funasr
**既当转写通道又当评测裁判**，正是 Hamburg 论文点名的盲区：裁判与被测同源，
鲁棒性让它对声学质量差异失明。登记进评测口径注记：**裁判模型应与被测通道异源**
（如被测 funasr 通道用 whistle 或人工文本当裁判），当前 agenticasr 复现用的
AASR-Bench 官方 rubric 恰好异源，无存量问题。

### 3.5 Ouroboros 后门 ↔ 治理前置叙事（第四条印证链）

SE 是听觉链路**最前**的模块——被下毒则转写、记忆、审计下游全错，且"干净理想输出"
这种触发器在常规过滤/微调下存活。这正是 laos"治理必须前置到最前模块 +
provenance 来源追踪"的学术侧印证。印证链现已四条：
Anthropic containment（93% 批准率靠 egress 拦）、Muse Secure-VM、OpenAI dots
approval rules、**Ouroboros（前端模块污染全链）**。进叙事素材库（PPT/README 引用），
不落代码。

### 3.6 一步式 SE ↔ capstone B-③"先增强再转写"蓝图（候选更新）

capstone B-③ 条目"先增强再转写"的候选池以 GTCRN/RNNoise/DeepFilterNet 为主
（`auto-gain/02-small-models.md`）；一步式生成增强（SBM/EffDiffSE+）把扩散成本压到
单步后，**端侧可行性量级改善**。但：①均未开源核验（SBM 论文页未见权重发布）；
②B 档算力位仍不现实。候选池记一笔，选型时把"一步式"当筛选条件，非立即行动。

## §4 裁决总表

| # | 风向 | 裁决 | 动作 |
|---|---|---|---|
| D1 | EoW 唤醒段当注册音 | ◐ 远线 | 触发条件登记（A 档真机 + 多说话人 CER 劣化实测），与 AEC3 同波 |
| D2 | 生成式增强幻觉记账 | ● 印证 | 红线维持并升级为"有文献支撑"；引用本文 + arXiv:2510.16834 佐证 |
| D3 | 多指标复合奖励 | ◐ 参考 | JitMem reward 设计参考（未来加多维 reward 时必复合） |
| D4 | 延迟旋钮 | ○ 互证 | dialogsched 已同构，零改动 |
| D5 | ASR-as-judge 盲区 | ◐ 口径 | 评测口径加注"裁判与被测通道异源"；存量无问题 |
| D6 | Ouroboros 前端后门 | ● 叙事 | 治理前置第四条印证链，进 PPT/README 素材库 |
| D7 | 一步式 SE 候选池 | ◐ 储备 | B-③ 蓝图候选更新，"一步式"列为筛选条件 |
| D8 | MeanFlow 扩散观察 | ○ 记录 | 方法学扩散速度信号，无 laos 动作 |

## §5 排队登记（并入既有排队清单）

1. **EoW 说话人自适应**：触发条件 = A 档真机落地 ∧ 多说话人场景 ASR 实测劣化（与 AEC3/R5 同波评估）；
2. **评测异源裁判注记**：写入评测口径文档的下一个修订波（当前无存量问题，非急）；
3. **Ouroboros 叙事素材**：下次 PPT/README 修订时并入"治理前置"论据组。

## §6 自检

1. **来源诚实**：§0 三档分级；两篇要害论文独立溯源为 ●（arXiv 号在案），其余 ◐ 不冒充 ●；
2. **零代码改动**：纯学习波，主库测试数不受影响（1054 绿维持）；
3. **不骑墙**：D1 明确"不落地+触发条件"，D2 明确"红线不动"，与 auto-gain/04、
   audio-events/07 既有裁决口径一致，无翻案无重复；
4. **数字口径**：115=67+29+10+9 自洽核验；引文注明是作者观点还是论文事实；
5. **登记完整**：INDEX 增补 + 排队三条并入既有清单格式。
