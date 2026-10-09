# AuraSE-IPO 学习与规则版复现 —— 生成式语音增强的幻觉治理（arXiv 2610.06632v1）

> 2026-10-09 · 学习对象：[AuraSE: Low-Hallucination Generative Speech Enhancement via Multimodal Flow Matching and Inference Policy Optimization](https://arxiv.org/abs/2610.06632)（Shen et al.，CUHK-SZ + Microsoft Research，v1 2026-10-05，9 页）——用户提供本地 PDF（Desktop），全文提取入 `var/repro/2610.06632/`
> 复现：**决策面规则版**落 [zones/Repro-ZCode](../../zones/Repro-ZCode/README.md) `repro/aurase_ipo.py`（23 例 pytest 手算锚点，复现区合计 94 绿）；神经训练（MMDiT/Emilia/Whisper-large-v3/DNS 语料/GPU-hours）按红线不碰，诚实偏差登记在区 README
> 姊妹篇：[auto-gain/04-large-models.md](auto-gain/04-large-models.md)（生成式增益档幻觉否决依据——本文是其正面战场）、[2026-10-09-rsi-landscape.md](2026-10-09-rsi-landscape.md)（"评估器在循环外"立论——本文是被治理对象）、[2026-10-09-xhs-qwen-audio-agent-runtime.md](2026-10-09-xhs-qwen-audio-agent-runtime.md)（完成≠交付的调度语义）

## 1. 一句话结论

**AuraSE 把"生成式增强会幻觉"从定性恐惧变成三维可测（WER=词法 / SBS=语义 / SIM=说话人漂移），并用两个杠杆压制：双流 MMDiT 让文本锚内容、退化音频独占通道保说话人（GT 文本 WER 7.69% vs 单流 10.97%）；IPO 把"推理配置敏感性"变成训练信号——8 组配置出候选、多目标奖励（OVRL:WER:SIM:SBS=4:2:2:2，质量 40%+保真 60%）排序成偏好对、在线蒸馏回单一固定 10 步 ODE 解码器（部署零搜索）**。对 laos 最重要的一条结构启示是**锚点相对性**：GT-DPO 直接拿真值当偏好赢家会崩（WER 13.35%），只有"模型自产候选的相对偏好 + 锚点随模型前移"才既提质量又保内容——这与 laos "评测口径与产物分离、实测不引宣称"同一纪律族。laos 侧落地：IPO 决策面规则版进复现区（●），幻觉三维审计 schema 与多目标权重结构立 ◐ 参照。

## 2. 论文核心（全文提取，数字抄原文）

**问题**：生成式 SE 在重退化下会"说得更好听但改了内容"——换词、插音、丢弱语音、漂说话人。实测幻觉量级（带混响集 WER）：LLaSE-G1 28.78%、StoRM 27.61%、SGMSE 22.15%、VoiceFixer 18.80%（vs 噪声输入 10.82%——生成式增强一度比不增强更毁内容）。

**杠杆一：模态（双流 MMDiT）**。mel 流（流状态+退化 mel 拼接）与文本流（转写嵌入 + 4 层 ConvNeXt-V2 预网）经联合注意力交互但保留各自投影，若干双流块后并流转单流 DiT 块；只有 mel token 进速度头。**文本补弱音证据而不替换退化声学**——退化输入全程有专属通道，说话人与信号特征不被文本冲掉。骨干：128 维 log-mel@24kHz、hidden 1024、27 块（9 双+18 单）、16 头、Vocos 声码器；流匹配条件 OT 路径 + 余弦时间表。

**杠杆二：推理（IPO）**。消融发现**推理无单一最优配置**：8 组策略（CFG∈{0,1}×temp∈{0.7,1.0}×steps∈{10,20}）逐话语解码，最优策略胜率最高仅 18.3%（uniform 12.5%），best-of-8 oracle 全面优于任何固定配置——但逐话语搜索部署不起。IPO 闭环：当前模型多配置解码 → 多目标奖励打分 → 正差偏好对按差距比例采样入缓冲 → DPO 式成对更新（流匹配能量代理，锚=上轮模型）→ T_r 有界复用后换血并前移锚点。**候选与锚都来自模型自产，真值只进排序指标永不进偏好对**。部署固定 (0, 1.0, 10)：10 步 ODE、无 CFG、零逐话语搜索。

**主要结果**：合成集（824 混响+824 无混响）AuraSE-IPO 12 项指标 11 项第一（带混响 OVRL 3.367 / WER 8.22% / SIM 0.757 / SBS 0.907——**内容指标首次全面优于噪声输入 10.82%**）；真实 DNS 盲测 DNSMOS 三轴最优 + 输入参照盲听 3.74±0.13（FlowSE 2.79±0.18）。RL 消融：DPO/GRPO 提质量但伤内容（WER 9.42%/10.91%），IPO 双升（7.59%），且超 best-of-8 oracle（5.87% WER 但 OVRL 3.271 < IPO 3.373——**蒸馏出了超出静态选择的能力**）。

**关键机理数字**：多配置候选的奖励离散度（Table 2 reward spread）IPO 0.58 > GRPO-SDE 0.54 > DPO-重播种 0.53——**推理配置多样性优于随机噪声多样性作为偏好源**；δ=0.20 边际下 300 话语出 1704 偏好对（5.7 对/话语），是稠密监督源。

## 3. 规则版复现（Repro-ZCode `repro/aurase_ipo.py`，23 例）

复现的是**决策与治理逻辑**，不是神经训练（诚实偏差四条登记在区 README：归一化用 utterance 内 min-max 替代 supplementary 细节、能量用线性打分器、候选特征合成、锚点对比只做方向性演示）。五个构件逐条对应论文原文：

| 构件 | 论文锚点 | 测试锚点（手算） |
|---|---|---|
| `reward()` 4:2:2:2 加权 + lower-better 翻转 | Eq.13 + "normalized reward weights ... by 4:2:2:2" | 三候选手算 [0.3, 0.8, 0.6]；总分王不是 OVRL 最高者（保真 60% 拉回） |
| `enumerate_pairs()` 正差对 + δ 边际 | "enumerate pairs with a positive reward gap" + Fig.2c | [0.3,0.8,0.6]→3 对；δ=0.25→2 对 |
| `sample_pair()` 差距比例采样 | "probability proportional to that gap" | 2 万次抽样频率 ≈ 0.5/0.2/0.3（±0.02）；同种子确定性 |
| `PreferenceBuffer` T_r 有界复用 + 锚点版本 | "after T_r bounded-reuse steps ... re-sync the anchor" | 3 次取用后 stale；refresh 版本 +1；取用序循环覆盖（反 best-worst 塌缩） |
| `ipo_loss/apply_pair_update` Eq.14-15 | Δ(x)=E_θold(x)−E_θ(x)，L=−log σ(β[Δ(x+)−Δ(x−)]) | θ=锚时 L=log 2；单步更新手算 [−0.0025,+0.0025]；20 步后 chosen 能量边际扩大、损失单调降 |
| `reward_spread/winner_distribution` | Table 2 口径 + Fig.2b | 手算 spread=(0.5+0.8)/2；胜率 [0.5,0.5,0]；平分语义 |

`run_policy_loop()` 提供 IPO vs 冻结锚（offline DPO 语义）的构造性对比：候选分布逐轮漂移时锚点前移的末轮排序相关 ≥ 冻结锚（方向性演示，不断言论文数值）。复现区合计 94 绿（71+23），冒烟命令进 `run_repro_all.py`（spread=0.600、top 胜率 25%<50% 的无占优断言）。

## 4. laos 对照与裁决（取长补短）

### 4.1 取（论文之长，laos 采纳）

| # | 采纳点 | 裁决 |
|---|---|---|
| 1 | **幻觉三维度量学**：WER（词法）/SBS（语义）/SIM（说话人）正交分解"幻觉"这个笼统概念，且各自直接对应可观测失效维度 | ● 已消化（叙事+schema）：若 laos 听觉链路在 drivers 层引入任何生成式组件（SE/修复/超分），审计/telemetry 事件按此三维拆分记录——"幻觉审计 schema"立为约定；评测维度即失败维度，不发明第四维 |
| 2 | **多目标奖励权重结构**：4:2:2:2（质量 40%+保真 60%）防单指标 reward hacking——"更好的分数"≠"更好的输出" | ◐ P2 参照：laos 判断层（sentinel 有序规则链）与风险账本是"规则/预算"范式，不需要加权分；但 evolve.run 之类需要"候选排序"的场合（gate 排序、进化奖励），此权重分配（多数份额给保真而非质量）是模板——laos 若做 evolve 的多目标奖励，保真份额 ≥ 60% 起步 |
| 3 | **锚点相对性纪律**：GT-DPO 拿真值当偏好赢家直接崩（WER 13.35%）；只有模型自产候选的相对偏好 + 锚点随模型前移才有效 | ● 已消化：与 laos "评测数字一律实测、引用与实测不混写"、"JitMem untrained curator 打平 write-time 基线（相对优于绝对）"三处互证——**绝对参照系当训练目标会崩，相对偏好+移动锚是普适纪律**；写进 evolve/判断层叙事 |
| 4 | **有界复用 + 锚点前移（T_r）**：缓冲陈旧化的数值治理——太长过期、太短浪费 rollout | ◐ P3 参照：context.py 过期治理与 64MB diary 水位的"复用预算"同族；JitMem curator 的候选选择可借鉴差距比例采样（不总取 best-worst，保留信息量梯度） |
| 5 | **复现资产**：IPO 决策面规则版 23 例 | ● 已落地（Repro-ZCode，本次 commit） |

### 4.2 补（论文之短，laos 差异化价值）

1. **奖励模型在循环内、无外裁判席**：IPO 的多目标权重（4:2:2:2）人工固定、奖励模型（DNSMOS/Whisper/WavLM）在优化循环内被当真值——作者自己承认"mitigating"而非消除 hacking（换指标组合即可再 hack）。laos 的 RSI 立论（评估器与权限须在进化循环之外）正好补位：**权重向量与奖励模型的变更本身应走治理**——版本化锚点 + 不可变审计，本复现的 `anchor_version` 语义就是这颗种子。
2. **逐话语穷举"部署不起"是调度问题**：best-of-8 全知全能但太贵，IPO 用蒸馏把它折进单解码器——这是"用训练时算力换部署时延迟"的经典调度权衡，laos 的预算/调度语义（EDQUOT、iterations 上限、mixed execution 结论）是同一问题域的内核侧答案。
3. **ASR 条件依赖是外部幻觉入口**：转写由 Whisper 一次性生成并固定，作者承认 "dependence on an external recognizer remains"——ASR 幻觉会传导进 SE 条件。laos 的三通道 ASR + AgenticSR refiner 正是"条件输入治理层"；且论文 **WER 对参照转写而非条件转写评分**（抄条件不得分），与 laos "引用与实测永不混写"同构——评测口径独立于条件输入，这条双方独立收敛。

### 4.3 不做

- **神经复现**（Emilia/LibriTTS-R/DNS 语料、MMDiT 训练、GPU-hours）：全线违反零依赖与 conda 红线，同 RSIGym 裁决 #8。
- **SE 模型进 laos 核心**：laos/ 纯 stdlib 不动；若未来听觉链路要生成式组件，只可能以 drivers 子进程形态（drv_evolve 同款契约），且触发 §4.1 #1 的幻觉审计 schema 才许上线。
- **改判 auto-gain/04 的"生成式不进记忆链路"裁决**：AuraSE-IPO 证明幻觉可压不可灭（最优系统 WER 仍 8.22%，且这是 transcript 条件下的 benchmark 数字）——"原音频即焚+只留文本"架构下，生成式组件产出只能进"评测副本"不得进"记忆副本"（与 AGC 落地篇"增益只作用于送推理的副本"同一条红线）。

## 5. 对账

- 论文全文：本地 PDF 提取 `var/repro/2610.06632/fulltext.txt`（9 页 48,035 字符，2 处 NUL 清洗）；引用数字全部抄自提取原文
- 复现：`zones/Repro-ZCode/repro/aurase_ipo.py` + `tests/test_aurase_ipo.py`（23 例）+ `run_repro_all.py` 冒烟位 + 区 README 模块地图⑤/诚实偏差登记；复现区 `pytest tests/ -q` **94 passed**（71+23）
- 诚实边界：论文 Table 3/4/6 数值均为模型实测（引用不复现）；本复现断言全部手算锚点，零论文数值断言
