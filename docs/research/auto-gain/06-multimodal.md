# AGC 跨切轴二 —— 多模态

> 口径来源：`docs/research/auto-gain/00-taxonomy-and-metrics.md`（作用点 / 控制对象 / 12 列 schema / 编号化自测口径，均以该文件为准）。
> 本文件只回答一个问题：**AGC 的多模态象限是空还是非空**，并给出可核验的检索证据。
> 本文件**不做落地推荐**（推荐在 `07-adoption.md`）。
> **结论先行：非空（判定被证伪）。** 找到 **3 条**输入含非音频模态、且被控量确为增益的真实工作，
> 其中 **1 条**满足 `00` 的 schema 可入表，**2 条为专利**（不满足 schema 的来源域规则，见§3）。
> 已在 `00` 追加**裁定 2** 记录对"预期为空"的推翻。

---

## Part 0 · 判定

**判定：非空。`00` 的"AGC 领域多模态预期为空"被证伪。**

| 维度 | 结论 |
|---|---|
| 真实多模态 AGC 工作条数 | **3**（达到 brief 的 ≥3 证伪阈值） |
| 其中可入 schema 表 | **1**（AV-NeuroAMP） |
| 其中不可入表 | **2**（均为**已授权专利**，无 arxiv/github/huggingface 来源、无权重、无公开基准，被 schema `source` 规则挡下） |
| 贴边但不计入的工作 | **2**（Visually-Guided Acoustic Highlighting、Tri-Ergon —— 均为**离线生成式音频重混**，见 §2.4） |
| 文本模态贡献 | **0**。7 个检索词无一命中"用文本/转写内容控制增益"的工作 |

一句话：**"多模态 AGC"作为研究命题是空的，作为工程命题不空**——它被写进了专利，没被写进论文。

---

## Part 1 · 七个检索词逐条结果

7 个检索词全部实际执行（WebSearch，2026-10-08），**无一遇429**。逐条记录：

| # | 检索词 | 命中 | 是否算多模态 AGC | 理由（逐字证据见 §3来源清单） |
|---|---|---|---|---|
| 1 | `audio-visual gain control` | **无多模态 AGC 命中**（命中项全为单通道 AGC / 视频亮度 AGC） | ✗ | 命中的是 TI 的 ALC/AGC 系列（`ti.com/lit/an/spraaj4a`、`ti.com/lit/wp/spraal1`）、WebRTC 式反馈环、以及**视频亮度/对比度 AGC**（Grokipedia 条目"A Video Processing"节讲相机自动增益）。后者控制的量是**图像亮度**，不是音频增益；前者只用麦克风单通道，不含视觉输入。**"audio-visual" 这个词组在 AGC 语境下几乎不产出真正的多模态 AGC**——这是本次最强的"空"信号 |
| 2 | `visual-assisted automatic gain control` | **2 条真命中**（均为专利）：**Nuance US9293151B2**、**Intel US 12,412,420 B2**；另命中 Yamaha CS-800 产品页 | ✓✓ / ✗ | Nuance 与 Intel 两条**就是多模态 AGC**：由摄像头估计说话人-麦克风距离 / 用户贴近度，直接驱动**增益**。但都是专利（§3）。Yamaha CS-800 的`Self-Volume Balancer` 官方原文是"automatically adjust the volume according to the **ambient noise**"——驱动量是**环境噪声（音频）**，且作用在**扬声器输出端**，不是麦克风增益；其视觉部分驱动的是 `Face Focus Beamforming`（波束形成=空间滤波，控制对象是波束不是增益） |
| 3 | `multimodal loudness normalization` | **2 条贴边命中**：Visually-Guided Acoustic Highlighting（arXiv 2602.03762）、Tri-Ergon（arXiv 2412.20378）；另命中 Royal Society 会议讲者页（Gijbels / Brimijoin，听觉感知研究） | ✗ | 两条 arXiv 都是**离线生成式音频重混/生成**：Tri-Ergon 是 video-to-audio **生成**（LUFS 是生成条件，不是闭环测量目标）；VisAH 是 flow matching **重混**。Royal Society 那两条是**心理物理实验**（AV 场景如何影响主观响度感知、TMR 下降 2–3 dB），不是增益控制器 |
| 4 | `audio-visual speech enhancement` | **大量命中，全部为增强**：AVSEC/AVSE 系列、RT-LA-VocE、VisualVoice、Spatial-VisualVoice、MAVe、VI-NBFNet、AVMamba、SSL-AVSE、EANet | ✗ | 与 `00` §3.5 的预判一致，且本次逐条核实：AVSE 的控制对象是**时频掩码 / 分离 / 波束**，输出"干净语音"而非"归一到目标电平"。Emergentmind 的 AVSE 条目给出形式化定义`|Ŝ(f,τ)| = M(f,τ)·|Y(f,τ)|`——`M` 是掩码。增益闭环的判据是"输出电平是否收敛到目标 LUFS"，AVSE 全文不涉及。**按 `00` 控制对象枚举，AVSE 一律记 `非AGC(相邻：增强)`** |
| 5 | `speaker distance estimation visual gain` | **2 条真命中**（即 #2 的两条专利，检索式换了说法）；另命中机器人视觉伺服波束形成论文 | ✓✓ / ✗ | 同 #2。机器人视觉伺服那两条（arXiv 1906.07298、Speech Communication 2020）里的 "directivity gain" 是**波束指向性增益**，由波束形成器实现，**不是对信号电平做闭环**——`00` 控制对象枚举里没有这一类，应记 `非AGC(相邻：波束形成)` |
| 6 | `video conferencing audio video joint normalization` | **1 条产品级命中**（Yamaha CS-800 `SoundCap Eye`）；另命中 Tandberg 7000 用户手册 | ✗ | Yamaha 官方页把"音视频融合"讲得很漂亮（"pinpoints participant locations ... using BOTH the voice and camera pickup"），但拆开看：视觉→定位→`Face Focus Beamforming`（波束），`Self-Silence`→HVAD（纯音频 VAD），`Self-Volume Balancer`→按**环境噪声**调**扬声器**音量。**没有一路"视觉→麦克风增益"**。Tandberg 手册则是**纯音频 AGC**（"maintains the audio signal level at a fixed value"），反证产品级 AGC 不需要视觉 |
| 7 | `跨模态 响度 归一 视觉 增益控制 语音` | **1 条真命中**：**AV-NeuroAMP**（arXiv 2610.08579）；另命中 EANet（AVSE 权重调制）、AV-NeuroAMP 同族的 NeuroAMP | ✓（本文件唯一入表条目）/ ✗ | AV-NeuroAMP 输入含**目标说话人视频** + **听力图**，输出为**联合 SE + 个性化放大 + 动态范围压缩**——被控量确为增益，属`联合(SE+AGC)`。EANet 是 AVSE（按 SNR 调融合权重，控制对象是掩码）；NeuroAMP（arXiv 2502.10822）是**纯音频**放大器（输入只有频谱 + 听力图），它是 AV-NeuroAMP 的音频only对照，恰好说明"加视频"才是多模态那一半 |

### 检索结果的形状（比"有/没有"更有信息量）

7 个词里，**产出真多模态 AGC 的只有 2 个词（#2、#5），且产出的是同两条专利**；
产出学术论文的词（#3、#4、#7）全部落在**增强 / 生成 / 心理物理**上。
即：**多模态 AGC 在"学术可发表"维度上是空的，在"可专利工程实现"维度上不空。**

---

## Part 2 · 逐条判定：命中项为什么不算

### 2.1 audio-visual speech enhancement（最大的一类命中，全部不算）

`00` §3.5 已预判"AVSE 是增强不是增益控制，控制对象是掩码不是增益"，本次**逐条核实后确认该预判成立**：

| 工作 | 出处 | 被控量 | 判定 |
|---|---|---|---|
| AVSE 综述（形式化定义） | emergentmind AVSE 条目 | T-F 掩码 `M(f,τ)`，`|Ŝ|=M·|Y|` | `非AGC(相邻：增强)` |
| AVSEC-4 冠军系统（分离先去混响） | arXiv 2510.26825 | PESQ/STOI/SI-SDR 提升、目标说话人提取 | `非AGC(相邻：增强)` |
| AVSE 部署架构对比（云/边/端） | arXiv 2508.08468 | 语音质量、时延 | `非AGC(相邻：增强)` |
| RT-LA-VocE（实时 AVSE） | arXiv 2407.07825 | 40 ms 帧级干净语音 | `非AGC(相邻：增强)` |
| Spatial-VisualVoice + MAVe | arXiv 2510.16437 | SI-SDR/STOI/PESQ | `非AGC(相邻：增强)` |
| SSL-AVSE（人工耳蜗仿真） | PubMed 41037547 | PESQ 1.43→1.67、STOI 0.70→0.74、NCM | `非AGC(相邻：增强)` |
| EANet（按 SNR 调AV 融合权重） | PubMed 39874821 | 融合权重 + 掩码 | `非AGC(相邻：增强)` |
| VI-NBFNet（视觉引导波束形成） | arXiv 2603.05270 | 波束权重 | `非AGC(相邻：波束形成)` |
| 视觉伺服波束形成 | arXiv 1906.07298 / Speech Communication 2020 | `directivity gain`（波束指向性） | `非AGC(相邻：波束形成)` |

**判据**：AGC 的定义性特征是**对输出电平做闭环**，收敛目标是**可写进标准的量**（LUFS / dBFS），
判据是"电平是否落在目标 ±容差内、是否削波"。上表 9 项**没有一项**报告电平收敛、LUFS 收敛时间、
增益波动或真峰值上限——它们报告的是 PESQ/STOI/SI-SDR/MOS。**指标集合本身就证明了控制对象不是增益。**

### 2.2 视频会议产品级音视频融合（不算）

Yamaha CS-800 的 `SoundCap Eye` 是本轮最容易被误判为多模态 AGC 的命中。逐项拆开（全部来自 Yamaha 官方页）：

| 子技术 | 官方描述 | 视觉是否参与 | 被控量 | 判定 |
|---|---|---|---|---|
| `Face Focus Beamforming` | 4K 相机 AI 追踪人脸 + 六麦阵列，"suppresses noise coming from directions other than the person captured in the camera" | ✓ | 波束指向 | `非AGC(相邻：波束形成)` |
| `Self-Silence` | 基于 HVAD 自动静音 | ✗（HVAD 是人声检测） | 静音门控 | `非AGC(相邻：降噪/门控)` |
| `Self-Volume Balancer` | "automatically adjust the volume according to the **ambient noise**"，作用于 **speaker / monitor speaker** | ✗ | 播放端音量 | `非AGC(相邻：播放端音量)` |

结论：**"音视频联合"是真的，"音视频联合增益控制"不成立**——视觉那一路最终落在波束形成上。
这条与 Tandberg 7000 手册形成对照：后者是**纯音频 AGC**（"the AGC maintains the audio signal level at a fixed value by attenuating strong signals and amplifying weak signals"），
说明产品级会议 AGC 的实现路径根本不需要摄像头。

### 2.3 视觉亮度 AGC（不算，且是词义陷阱）

检索词 #1 大量返回相机/电视领域的 AGC（自动增益、auto-exposure）。这类 AGC 控制的量是**图像亮度**，
与音频增益只是**同名**，无技术关系。记录在此是为了防止后续 Task 把"AV 自动增益"误读成"音视频自动增益"。

### 2.4 离线生成式音频重混（贴边，按 `00` 记`非AGC(相邻：生成)`）

这两条是检索词 #3 的命中，也是**最接近"多模态响度控制"字面含义**的工作，但都不是AGC：

| 工作 | 出处 | 做什么 | 为什么不是 AGC |
|---|---|---|---|
| Tri-Ergon（AAAI 2025） | arXiv 2412.20378 | video-to-audio **扩散生成**；引入 **LUFS embedding**，让用户手工指定各声道随时间变化的响度曲线；LUFS 也可由 DINO-V2 从视频帧预测 | ① 被控量是**生成结果的响度**，闭环不存在——AGC 要测量**输入**电平并与目标比较，Tri-Ergon 是把 LUFS 当**条件**喂给生成器；② `作用点` 是**离线**（Foley / 影视配音）；③ 参数量 881M / 1.1B + 扩散步数，是生成式模型，按 `00` 红线三不进laos 链路。**收录理由（`00` 要求注明）**：它是"视觉→响度"唯一一条有明确响度单位的学术工作，用于说明**视觉能预测的是内容语义上的突出度，不是麦克风口的瞬时电平** |
| Visually-Guided Acoustic Highlighting（VisAH-FM, Meta） | arXiv 2602.03762 | 以视频为引导**重混**音频，"rebalancing loudness of different audio sources (speech, music, sound effects) to reflect their relative prominence as implied by the visual context" |① 是**离线重混/再生成**（flow matching 整段重渲染），不是对既有信号的增益乘法；② 重混目标是**源间相对突出度**，不是绝对电平目标（无 LUFS/dBFS 闭环）；③ 论文自述场景是"Raw daily recordings... poorly balanced audio due to recording device limitations"的后期制作 |

**这两条恰好构成对 brief 物理解释的一个有意思的反证压力**：视觉确实能携带"谁更重要"的信息——
但它服务的是**内容编辑意图**，不是**电平闭环**。视觉给的是"该突出谁"，AGC 要的是"现在多少 dB、差多少 dB"。

---

## Part 3 · 三条真实多模态 AGC 工作（证伪证据）

三条都满足"输入含非音频模态 + 被控量确为增益"。**只有第一条能进 schema 表**。

### 3.1 ✓ 入表：AV-NeuroAMP（arXiv 2610.08579）

| 项 | 值 | 出处 |
|---|---|---|
| 名称 | AV-NeuroAMP（Audiovisual joint learning for end-to-end hearing aids） | arXiv 摘要页 |
| 团队 / 时间 | You-Jin Li、Yu Tsao、Borching Su、Kuan-Chung Ting、Fan-Gang Zeng（台大通识 + 中研院 + 荣总医院 + UCI）；**v1 提交 2026-10-06** | arXiv 摘要页 |
| 许可 | **CC BY 4.0**（arXiv HTML 页脚标注） | arXiv HTML |
| 多模态输入 | 噪声语音（16 kHz，512 点 STFT，hop 128）+ **目标说话人视频**（25 fps、224×224 灰度全脸） | §II.5 |
| 被控量 | **个性化放大 + 动态范围压缩**（训练目标由 NAL-R+WDRC 生成），与 SE **端到端联合** | §II.2.3 |
| 参数量 | **18.019 M**（视觉编码器 14.627 M，其中 **11.185 M 为冻结**；AVNN 3.370 M；AC-FiLM 0.022 M）→按 `00` 分档属**小型档** | §II.5 + Table 1 |
| 计算量 | **232.16 GMACs / 2 s 视听输入**（AVNN 137.38 + 视觉 94.78+ AC-FiLM <0.01） | Table 1 |
| 基准 | 训练与域内评测 **AVSEC-2**；跨语言域外评测 **TMSV**（台湾普通话影音）；听力图来自 **Clarity Challenge**（272 耳：166 训练 / 106 测试） | §II.3 |
| 指标 | 噪声输入：**HASPI 0.780、HASQI 0.625**（对照 NeuroAMP 0.419 / 0.268、Conventional 0.449 / 0.283）；干净输入：HASPI 0.925、HASQI 0.932（对照 NeuroAMP 0.917 / 0.902） | §III.1 |
| 代码 / 权重 | **未找到**。全文出现的唯一 GitHub 链接是 **基线** NAL-R/WDRC 的 `claritychallenge/clarity`，**不是本文代码** | §II.4脚注 |
| 作者自述的部署限制 | 原文："the current system processes complete utterances and **is not yet designed for causal wearable operation**. Practical deployment will require a streaming implementation with controlled algorithmic latency, memory use, and power consumption." | §IV.4 Limitations |

**为什么它算多模态 AGC**：被控量是增益（放大 + DRC），且视频进入增益预测通路
（视听特征经 AC-FiLM 调制后由 AVNN 直接预测放大后的频谱），不是"视频只做选人、视频不进增益通路"。

**但必须同时说清它的边界（否则会高估这条）**：
增益的**主条件变量是听力图**（1×6 阈值向量，经 AC-FiLM 生成缩放/偏移/门控），
**视频的作用是目标说话人区分**。干净输入下音频only 对照 NeuroAMP 已达 HASPI 0.917 / AV-NeuroAMP 0.925——
**视频的增益几乎全部体现在噪声/竞争说话人条件**（0.419→0.780）。即：**视频回答"放大谁"，听力图回答"放大多少"。**

### 3.2 ✗ 不入表：Nuance US9293151B2 / EP2766901 / WO2013058728

| 项 | 值 |
|---|---|
| 名称 | Speech Signal Enhancement Using Visual Information |
| 申请人 | **Nuance Communications, Inc.**（发明人 Markus Buck / Tobias Herbig / Tobias Wolff） |
| 时间 | PCT 2011-10-17 提交；WO 2013-04-25 公开；EP2766901 B1 2016-09-21；**US9293151B2 已授权** |
| 视觉做什么 | 图像分析器估计**说话人↔麦克风距离**、房间 RTF、说话人朝向、反射面位置 |
| 被控量 | **overall gain**——原文："Sound pressure level (SPL) of an acoustic signal... drops off with distance. For example, **a doubling of distance causes a loss of 6 dB**. The tuner 126 adjusts **overall gain** in the audio signal processor 108 to compensate for the loss in SPL";另有按朝向调**分频段增益**（背对时抬高高频） |
| **不入表理由** | ① `来源` 列按 `00` 必须含 `arxiv.org` / `huggingface.co` / `github.com` 之一，本条只有 `patents.google.com` → 触发 schema `source` 规则；② 无参数量（权利要求书不披露）、无权重、无公开基准 → 指标列无法合规填写；③ `可得: no`（仅专利，无实现） |

**这条专利是本次"预期被推翻"的最强单点证据**：它是 2011 年就申请、2013–2016 公开授权的
**完整可实施多模态 AGC 方案**（视觉估距 → 6 dB/倍距离补偿 → 调总增益与分频增益）。
**该想法存在了十余年且已授权，却没有任何论文把它当作研究命题**——这本身就是一条关于领域偏好的证据。

### 3.3 ✗ 不入表：Intel US 12,412,420 B2（申请 US20210318850A1）

| 项 | 值 |
|---|---|
| 名称 | Apparatus, systems, and methods for microphone gain control for electronic user devices |
| 申请人 | **Intel Corporation**（发明人 Tigi Thomas，班加罗尔）；申请号 17/358,894，申请日 2021-06-25，公开 2021-10-14，**2025-09-09 授权**，调整后到期 2043-07-18，状态 Active |
| 视觉做什么 | 视频会议中由摄像头图像检测**用户到设备的距离**——用**鼻梁宽度像素数**作距离代理（原文解释选鼻梁是因"a width of the nose bridge may have less variance across demographics (e.g., genders, nationalities) than other facial features"） |
| 被控量 | **麦克风增益**——原文："a gain applied to a voice band of the audio signal... is increased when the proximity of the user to the camera is determined to be greater than a threshold distance"；目的是"an audio output level of the user's voice is **independent of the position of the user** relative to the camera" |
| 动机（值得引用的自述） | 原文指出经典 AGC 的结构性局限："AGC control systems **do not discriminate input signals based on audio type**. Therefore, the AGC system may adjust the gain on the input signal without discriminating between, for instance, frequency differences between background noise and a speaker's voice"，并指出可能在噪声环境下把背景噪声一起放大 |
| **不入表理由** | 同 §3.2（专利来源域不合规、无参数量/权重/公开基准） |

**注意 Intel 这条专利里有一句与 `00` 结论方向一致的观察**：即便厂商做视觉增益，
它解决的也不是"电平测量不准"，而是"**AGC 分不清语音与噪声类型**"——
这恰好说明厂商承认增益决策的瓶颈在**音频侧的判别**，而视觉只是补了一个距离代理量。

---

## Part 4 · 物理解释：为什么这个象限近乎为空（预期论证的最终表述）

brief 给出的预期论证是"增益是瞬时电平闭环问题，视觉与文本不提供额外瞬时电平信息"。
本次检索**没有推翻这个论证的物理部分，但推翻了它的"因此为空"结论**。修正后的表述如下。

### 4.1 论证仍然成立的部分（且被本次证据加强）

**（a）决策变量全在音频侧。** AGC 每一次更新的输入只有三个量：当前电平、目标电平、噪声底/语音段判别。
这三者都是**麦克风口信号的泛函**，不需要任何外部模态。Nuance 专利自己就把这条写成了物理量：
"a doubling of distance causes a loss of 6 dB"——而**这个 6 dB 直接体现在采样值里**。
用摄像头像素反推距离再换算成增益，比直接测电平多走一步、还多一个误差源。

**（b）文本模态贡献为 0（本次新增的量化结论）。** 7 个检索词里，
"文本/转写内容→增益"的命中数为 **0**。这与预期完全一致，且比预期更强：
文本是**语义**信号，语义与瞬时电平之间没有稳定的映射（同一句话可以轻声说也可以大喊），
所以文本连"视觉那样的辅助量"都不是。

**（c）视觉是唯一有物理意义的多模态输入，但它只能定"目标"不能定"电平"。**
Nuance / Intel 两条专利都只做同一件事：**估计说话人相对麦克风的距离/贴近度**。
没有任何一条工作用视觉去估计**绝对电平**、**噪声底**或**目标响度**——因为视觉原理上观测不到这些。
视觉给的是"**该放大谁**"，AGC 要的是"**现在多少 dB、差多少 dB**"。

### 4.2 被证据加强的部分：代价是**可量化的**，不再是定性判断

brief 说"声学方法更直接省电、视觉方案要开摄像头（合规与功耗高一个量级）"。
AV-NeuroAMP 的公开数字让这句话从定性变成可核对：

| 证据 | 数字 | 含义 |
|---|---|---|
| AV-NeuroAMP 视觉前端参数量 | **11.185 M 冻结 / 14.627 M 合计**，占全模型 18.019 M 的**约 81%** | 为了"识别说话人"这一个信息，投入了八成参数 |
| AV-NeuroAMP 视觉计算占比 | **94.78 / 232.16 GMACs ≈ 41%**（2 s 输入） | 视觉占了四成算力 |
| 实时性 | **232.16 GMACs / 2 s ≈ 116 GMAC/s** | 远超实时；作者自述"not yet designed for causal wearable operation" |
| 对照：增益决策实际需要的输入 | **1×6 听力图向量** | 决定"放大多少"只需要 6 个数 |

即：**增益决策本身只需要 6 个数，而获取"放大谁"这条辅助信息花掉了八成参数、四成算力，并且仍不可实时。**
这直接印证 brief 的"高一个量级"，且是论文自己给的数字。

### 4.3 最终表述（供 Task 15 直接引用）

> **AGC 的多模态象限不是"空"，而是"薄"：它只有 3 条真实工作（1 篇论文 + 2 项已授权专利），
> 且 3 条全部使用视觉、0 条使用文本。**
>
> 物理原因是：增益闭环的决策变量（当前电平 / 目标电平 / 噪声底）**全部是麦克风口信号的泛函**，
> 视觉与文本都不携带这些量；视觉唯一能提供的是**说话人距离与朝向**，
> 而距离到增益的换算（−6 dB / 倍距离）**本身就已经在采样值里可测**，
> 视觉方案是用一个含噪的估计去替换一个直接测量。
>
> 因此该象限的真正形态是：**想法早已存在并被专利化（Nuance 2011 申请 / Intel 2021 授权），
> 但从未被当作研究命题**，因为学术界认为它不构成新问题。
> 这与 AVSE 象限相反——AVSE 有大量论文，因为那里视觉提供的是**声学确实丢失的信息**（唇动→音素），
> 而增益那里视觉提供的是**声学已经有的信息**（电平）。
>
> 唯一在学术侧成立的例外是**助听器场景**（AV-NeuroAMP）：
> 那里增益目标由**听力图**决定（而非由电平决定），
> 于是视觉有了不可替代的分工——**视觉定"放大谁"，听力图定"放大多少"**。
> 这条印证了论证的边界：**只要增益目标偏离"输出电平"而变成"某人听清"，多模态就有意义。**

### 4.4 论证的可证伪点（留给后续 Task）

若将来出现以下任一情况，本节的物理解释需要再次修正，本文件结论也需重估：
1. 有工作证明**视觉估计的电平比麦克风电平估计更准**（例如在强混响、远场、
   或麦克风被遮挡/风噪工况下）——这会打破 4.1(a)；
2. 有端侧视觉前端的**实测功耗**低到与音频前端同量级（本次只有论文里的 GMACs 推算，
   **无实测 mW**，见 §5 疑虑）——这会打破 4.2；
3. 出现以**文本/转写**为条件的增益工作（当前为 0）——这会打破 4.1(b)。

---

## Part 5 · schema 表（1 条入表记录）

12 列，列名逐字照抄 `00`。**本表是本文件唯一需要 schema 校验的表。**

| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AV-NeuroAMP | 神经·多模态联合（视觉前端冻结 + TCN adapter + AC-FiLM + AVNN） | 18.019 | 16kHz/32ms 帧(512点STFT, hop 128)/单通道 + 25fps 224×224 灰度人脸视频（目标说话人） | 联合(SE+AGC) | 采集后 | AVSEC-2 / TMSV | HASPI 0.780、HASQI 0.625 (TMSV噪声输入)；18.019M 参数、232.16 GMACs/2s (AVSEC-2) | CC BY 4.0（论文）；代码与权重未公开 | no（仅论文，全文唯一仓库链接为基线 claritychallenge/clarity） | no（232.16 GMACs/2s ≈ 116 GMAC/s，作者自述非流式、未面向可穿戴实时） | https://arxiv.org/abs/2610.08579 |

**逐列填写说明（供审阅）**：

- **`作用点` = 采集后**：助听器链路为「麦克风 → ADC → 数字域放大/DRC → DAC → 耳道」，
  增益施加在被采信号上。⚠️ 但对laos 而言它同时是**该设备的播放端**，
  因此**它不是 laos 采集链的候选**，只作能力记录（`00` 作用点表对 `播放前` 的说明同样适用）。
- **`控制对象` = 联合(SE+AGC)**：按 `00` 枚举，输出既降噪又放大/压缩，故填联合值，
  并在此写明联合方式——SE、个性化放大、DRC 三者在同一张端到端网络里联合训练。
- **`edge` = no**：依据是论文自述非流式 + 算力推算，**不是**已找到的转换失败证据；
  若日后出现端侧实现，此格需重评。
- **未入表的2 条**（Nuance US9293151B2、Intel US 12,412,420 B2）**故意不进上表**，
  原因见 §3.2 / §3.3（来源域不合规 + 无参数量/权重/公开基准）。
  它们是**证伪证据**，但不是**表条目**——请勿在 landscape 中按表条目引用。

---

## Part 6 · 本文件不回答什么

1. **不回答"laos 要不要上多模态"**——落地判断在 `07-adoption.md`。
   本文件只提供一条输入：多模态增益控制在论文层只有 1 条、且不可实时，
   而真正被工程验证过的多模态增益（两条专利）均为**专利封闭、无公开实现**。
2. **不回答 `01-classical-dsp.md` 的二次增益问题**——只提示本文件不改变该结论。
3. **不给 AVSE 象限下结论**——本文件对 AVSE 的一致判定是 `非AGC(相邻：增强)`，
   理由见 §2.1；若后续需要给 AVSE 单独立档，应在 landscape 层面处理。

---

## 附：实际访问过的来源（全部为2026-10-08 实访问）

**检索命中但判定为"不算"的**：
- https://www.ti.com/lit/an/spraaj4a/spraaj4a.pdf（ALC for speech, PID）
- https://www.ti.com/lit/wp/spraal1/spraal1.pdf（Software AGC for speech）
- https://patents.google.com/patent/US8121835
- https://grokipedia.com/page/Automatic_gain_control（含视频亮度 AGC）
- https://blog.csdn.net/XiaoXiaoPengBo/article/details/149858275（AGC 链路与 VAD）
- https://www.emergentmind.com/topics/audio-visual-speech-enhancement-avse
- https://www.emergentmind.com/topics/audio-visual-speech-enhancement-avse-system
- https://arxiv.org/html/2508.08468v1（AVSE 部署架构）
- https://arxiv.org/html/2510.26825v1（AVSEC-4 冠军）
- https://pubmed.ncbi.nlm.nih.gov/41037547/（SSL-AVSE）
- https://pubmed.ncbi.nlm.nih.gov/39874821/（EANet）
- https://arxiv.org/html/2603.05270（VI-NBFNet，经 paperreading.club 检索页转引）
- https://arxiv.org/pdf/1906.07298、https://sciencedirect.com/science/article/pii/s0885230820300693（视觉伺服波束形成）
- https://export.arxiv.org/pdf/2407.07825（RT-LA-VocE）
- https://ui.adsabs.harvard.edu/link_gateway/2025arXiv251016437Y/EPRINT_HTML（Spatial-VisualVoice / MAVe）
- https://arxiv.org/html/2512.18099v1（SAM Audio）
- https://arxivsignals.io/papers/2507.21448（RAVEN）
- https://wlv.openrepository.com/items/5b6a0979-70fb-4ac3-819d-57713b425d77（AVSE 博士论文）
- https://hackernoon.com/lite/the-future-of-clearer-speech-is-multimodal
- https://royalsociety.org/science-events-and-lectures/2026/03/vision-augmented-hearing/（AV 场景与主观响度）
- https://arxiv.org/html/2502.10822、https://arxiv.org/abs/2502.10822、https://www.computer.org/csdl/journal/ai/2026/03/11145141/29zY7FpUHZu（NeuroAMP，音频only 对照）
- https://www.citi.sinica.edu.tw/aiic/aiic-research-results、https://www.sumobrain.com/patents/wipo/Signal-processing-method-device-hearing/WO2026011076A1.html
- https://github.com/Shafique-Khattak/NeuroAMP

**产品级音视频融合**：
- https://ca.yamaha.com/en/business/audio/products/video-collaboration-systems/cs-800/、https://www.yamaha.com/2/cs-800/（CS-800 SoundCap Eye 官方页）
- https://www.manualslib.com/manual/168157/Tandberg-Video-Conferencing-System-7000.html?page=66（Tandberg AGC 手册）
- https://www.datapro.co.th/product/anyco-v8、https://www.ava.com.cn/portal/article/index/id/799.html、https://manuals.plus/m/7eb30b1b5f58de462caa879e2fc20b303c266cf4419ac4773ccbb8e01b3e5d72、https://esco.asia/blog/lets-start-new-logicofwork、https://blog.peoplelinkvc.com/?p=21988、https://www.tz1288.com/ask/8983190.html

**证伪证据（真多模态 AGC）**：
- https://arxiv.org/abs/2610.08579、https://arxiv.org/html/2610.08579v1（AV-NeuroAMP，全文与参数表已逐条读取）
- https://arxiv.org/abs/2602.03762、https://arxiv.org/html/2602.03762v3（VisAH）
- https://arxiv.org/html/2412.20378v1、https://arxiv.org/pdf/2412.20378.pdf、https://export.arxiv.org/abs/2412.20378v1、https://dl.acm.org/doi/abs/10.1609/aaai.v39i5.32487（Tri-Ergon）
- https://patents.google.com/patent/US9293151B2/en（Nuance，已授权）
- http://patentsencyclopedia.com/patents/app/20140337016、https://uspto.report/patent/app/20140337016、https://www.freepatentsonline.com/EP2766901.html、https://www.freepatentsonline.com/WO2013058728.html（同一专利族）
- https://patents.google.com/patent/US20210318850A1/en、https://patentimages.storage.googleapis.com/13/2c/f8/ed3f25f1bb4079/US20210318850A1.pdf、http://local.patents-review.com/a/20210318850-apparatus-systems-methods-microphone-gain-control-user.html、https://app.lexdana.ai/us/patent/12412420、https://thepatentplace.com/iplibrary/patent-pdf/12412420（Intel，已授权）

**未能执行 / 未获结果**：
- `api.github.com` 元数据查询（Tri-Ergon 与 NeuroAMP 仓库的 license 字段）返回 **HTTP 403 rate limit**，
  故两仓库的许可**未能核实**。这不影响结论：两条工作均**不作为 schema 表条目**
  （VisAH / Tri-Ergon 见 §2.4；AV-NeuroAMP 的许可已由 arXiv 页脚 CC BY 4.0 直接确认）。
- 会议信息页（ACM MM 2026、beri.net、allai.events、2026.acmmm.org）在检索结果中出现，
  仅为会议宣传页，**不含**多模态 AGC 工作，未作为证据引用。