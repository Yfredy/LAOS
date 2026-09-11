# 全天候录音 · 学术论文线

> 配套文档：`docs/research/always-on-recording-industry-2026-09.md`（商业产品 / 开源项目 / 法律条文）。
> 本文档只覆盖**学术论文**，不重复商业产品、开源项目与法条。

## 学术线的一句话结论

学术界对"全天候录音"已经形成的共识是：**录音本身从来不是瓶颈，瓶颈一直是"录完之后怎么办"**——① 常驻感知的功耗已经被压到亚微瓦级（47 nW 的 VAD、988 nW 的 KWS 均已流片验证），但那是定制 ASIC 的数字，跑在通用 DSP/ADSP 上仍要付出 2 个数量级代价；② 声学事件检测与说话人日志在**受控数据集**上已接近饱和（ESC-50 97%+、VoxConverse DER 4%），但在**真实场景**（DIHARD III 的餐厅/会议/网络视频，DER 中位数 35–45%）远未解决；③ 纵向情绪/健康追踪是证据最扎实、也最接近落地的方向（1,857 人多队列 + 8 周随访已经跑通），但它同时也是**隐私风险最高**的方向——MeMic 的 N=168 实证显示，把"持续录音"换成"只录自己"能让社会接受度显著提升，而 Tabassum (N=178) 与 Malkin 的实证都指向同一件事：**用户对"录了多久、留多久"的认知与实际严重脱节，自动删除是最被期待的隐私功能**。仍在吵的则是三点：真实场景 diarization 的天花板在哪、语音生物标记物到底是"生物标记"还是"数据集相关性"、以及录制者的知情同意能否代替旁观者的同意。

---

## 1. 可穿戴长期录音的真实世界研究

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| Ego4D: Around the World in 3,000 Hours of Egocentric Video | Meta AI + 13 家高校，CVPR 2022（arXiv 2021） | 大规模第一人称日常活动数据 + 情景记忆检索 | 931 名佩戴者、74 个地点、9 国，3,670 小时；含 audio / gaze / 3D mesh / 多机位；5 个 benchmark 中含 **Episodic Memory（情景记忆查询）** 与 **AV Diarization** | 3,670 h；931 人；单次佩戴 1–10 h；数据集约 7 TB | **记忆检索**：Ego4D 的 Episodic Memory 是"每日日记/回溯检索"任务最权威的公开基准；laos 的记忆库检索可直接对标其 NLQ（自然语言查询）任务的评测口径 | [arXiv:2110.07058](https://arxiv.org/abs/2110.07058) |
| Ego-Exo4D: Understanding Skilled Human Activity from First- and Third-Person Perspectives | Meta AI / Univ. of Bristol 等，CVPR 2024 & IJCV 2025 | 同步自我+他者视角的技能性活动理解 | 740 名参与者、13 城、123 个场景；**7 麦克风阵列**多通道音频 + IMU + gaze + 3D 点云 + 专家解说 | 1,286.3 h；5,035 takes；单段 1–42 min；7-mic array | **③蒸馏 + 记忆检索**：这是目前公开数据中**麦克风阵列配置最完整**的日常长时录音集；laos 若要做声源定位/说话人分离的空间先验，这是唯一能直接用的公开基准 | [arXiv:2311.18259](https://arxiv.org/abs/2311.18259) |
| EgoADL: Multimodal Daily-life Logging in Free-living Environments Using Non-visual Egocentric Sensors on a Smartphone | UC San Diego + Samsung Research America（Ke Sun, Chunyu Xia, Xinyu Zhang, Hao Chen, Charlie Jianzhong Zhang），Proc. ACM IMWUT 8(1) Article 17, 2024 | 用非视觉传感器（音频 + CSI + 运动）做自由生活场景的 ADL 日志 | 口袋里的智能手机做多模态传感中枢；采集 120 h 多模态数据，标注 20 h | 120 h 采集；20 h 标注；221 个 ADL、70 个物体交互、91 个动作 | **②触发捕获 + ③蒸馏**：EgoADL 明确了"音频比相机更适合日常日志"的三条理由（对佩戴姿态不敏感、文件远小于视频、覆盖面广）—— 这正是 laos 选音频而非视觉做常驻感知的学理依据 | [DOI:10.1145/3643553](https://doi.org/10.1145/3643553) |
| EgoLog: Ego-Centric Fine-Grained Daily Log with Ubiquitous Wearables | 香港中文大学，2025 | 用耳机/眼镜上的麦克风+IMU 做细粒度日常日志 | 音频-IMU 双路融合（时域场景聚合 + 运动补偿的声源定位），LLM 做场景推理后蒸馏回端上 | 活动识别与场景识别分别超基线 **12% 和 15%** | **③蒸馏 + 记忆检索**：EgoLog 的"LLM 在云端做场景理解 → 知识蒸馏回端上推理"与 laos 的"本地 SenseVoice 蒸馏 + 记忆库"是同构流水线，可直接借鉴其场景层级定义 | [arXiv:2504.02624](https://arxiv.org/abs/2504.02624) |
| Minimal-impact audio-based personal archives | Columbia Univ. (Daniel Ellis)，ACM CARPE 2004 | 采集连续个人音频档案的最小侵扰方案与可行性 | 长时间连续佩戴录音，无监督分割+聚类，与人工标注的环境/情境标签比对 | 与人工标注的环境/情境标签达成"good agreement"（原文未给出具体数值，未证实具体准确率） | **④即焚 + 记忆检索**：这是 audio lifelogging 的奠基工作，明确论证"音频档案文件尺寸远小于视频、对佩戴姿态不敏感"——是 laos"只存文本、焚掉音频"路线最早的学理支撑 | [DOI:10.1145/1026653.1026659](https://doi.org/10.1145/1026653.1026659) |
| Are women really (not) more talkative than men? A registered report... | Univ. of Arizona 等 22 个样本组，JPSP 2025 | **人一天到底说多少话**（用环境录音客观估计） | EAR（Electronically Activated Recorder）环境录音；22 个样本合并 | **2,197 名参与者、631,030 段环境录音**；男性均值 11,950 词/天，女性 13,349 词/天；个体差异跨度 100 → 120,000 词/天；25–64 岁组性别差 3,275 词/天（d=0.32） | **②触发捕获 + 容量规划**：这是给 laos 定存储/蒸馏吞吐的直接锚点——每人每天约 1.2 万词量级，但**个体差异达三个数量级**，最健谈者的 ASR 负载是最沉默者的 1000 倍，触发式捕获的缓冲区必须按长尾设计 | [DOI:10.1037/pspp0000534](https://doi.org/10.1037/pspp0000534) |
| Mehl et al., "Are women really more talkative than men?" | Univ. of Arizona，*Science* 2007 | 同上（原始研究，EAR 方法学奠基） | 396 名大学生，每 12.5 分钟自动录 30 秒，清醒时段全程佩戴（约 17 h/天），研究跨度 1998–2004 | 男女均约 **16,000 词/天**；最健谈者 47,016 词/天 vs 最沉默者 695 词/天，跨度 46,000 词；性别差仅 546 词 | **②触发捕获**：EAR 的"每 12.5 分钟录 30 秒"（≈5–6 次/小时）是学术界验证过的**最低可用采样密度**；laos 的 VAD 触发密度应以此为下界参照 | [U Arizona EAR 方法学章节(PDF)](https://repository.arizona.edu/bitstream/10150/623432/1/EAR%20CDPS%20in%20press.pdf) |

---

## 2. 声学事件与场景理解

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| Audio Set: An ontology and human-labeled dataset for audio events | Google，ICASSP 2017 | 大规模音频事件本体与数据集 | 632 类层级本体；YouTube 10 秒片段人工多标签标注 | **2,084,320 段 10 秒片段**；527 个标注类（本体 632 类）；约 5,800 小时；balanced 子集保证每类 ≥59 例 | **③蒸馏（事件标签）**：laos 的"情感标签 + 事件标签"若想扩展，AudioSet 本体是唯一覆盖 527 类的现成词表；注意 2024 年 3 月已有约 18% 样本因 YouTube 下架失效 | [DOI:10.1109/ICASSP.2017.7952261](https://doi.org/10.1109/ICASSP.2017.7952261) |
| FSD50K: an open dataset of human-labeled sound events | Univ. Pompeu Fabra (MTG)，ICASSP 2022（arXiv 2020） | 开放许可的大词汇量声音事件数据集 | Freesound  sourced，AudioSet 本体子集，多标签 | **51,197 段片段**；200 类（144 叶节点 + 56 中间节点）；**108.3 小时** | **③蒸馏**：FSD50K 是真正可商用许可（CC）的替代 AudioSet 的选项；laos 若要本地微调一个"家庭场景事件标签器"，FSD50K 的 200 类比 AudioSet 的 527 类更适合裁剪 | [arXiv:2010.00475](https://arxiv.org/abs/2010.00475) |
| Efficient Training of Audio Transformers with Patchout (PaSST) | Johannes Kepler Univ. Linz，ICASSP 2022 | 音频 Transformer 在下游任务上的效率与 SOTA | PaSST + Patchout；在 OpenMIC / ESC-50 / DCASE20 / FSD50K 上评测 | ESC-50 **96.8%** acc（5-fold 均值）；FSD50K **mAP 0.653**；DCASE20 **76.3%**；单消费级 GPU <5 min 微调完 ESC-50 | **③蒸馏**：给出"通用音频事件分类"在干净数据集上的实际天花板（ESC-50 ≈ 97%），laos 可用它校准自家事件标签的可信度上限 | [arXiv:2110.05069](https://arxiv.org/abs/2110.05069) |
| DCASE 2024 Task 4: Sound Event Detection with Heterogeneous Data and Missing Labels | INRIA / Tampere Univ. / MERL 等，DCASE 2024 | 家庭/真实环境下的声音事件检测，跨数据集、标签缺失 | DESED（家庭 10 类）+ MAESTRO Real（11 类软标签，3–5 分钟长录音）；CRNN + BEATs 特征 | DESED：弱标注 1,578 段 / 无标注 14,412 段 / 强标注 3,470 段；MAESTRO dev 6,426 段；基线 PSDS 0.549 → 最佳 0.604，联合分 1.343 | **②触发捕获**：DCASE Task 4 是"家庭常驻麦克风该检测什么、检测得有多好"的唯一年度权威考卷（best PSDS ≈ 0.60）；laos 的 ② 触发条件不该只靠人声 VAD，家庭声学事件是重要的上下文 | [arXiv:2406.08056](https://arxiv.org/abs/2406.08056) |
| Large-scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation (CLAP) | LAION / UC San Diego，ICASSP 2023 | 用自然语言监督学通用音频表示，实现零样本音频分类 | 发布 **LAION-Audio-630K**（633,526 音频-文本对）；特征融合 + keyword-to-caption 增强 | 633,526 对；零样本 ESC-50 上达 SOTA，接近有监督水平 | **记忆检索**：CLAP 提供 audio↔text 同一嵌入空间，是 laos 记忆库做"用自然语言检索声音记忆/用声音检索文本记忆"的最直接现成方案 | [arXiv:2211.06687](https://arxiv.org/abs/2211.06687) |
| AudioCLIP: Extending CLIP to Image, Text and Audio | DFKI / TU Kaiserslautern，ICASSP 2022（arXiv 2021） | 把 CLIP 扩展到音频，零样本环境声分类 | ESResNeXt 音频头接入 CLIP，AudioSet 训练 | ESC-50 **97.15%**（微调）/ **69.40%**（零样本）；UrbanSound8K 90.07% / 零样本 68.78% | **记忆检索 + ③蒸馏**：给出了"零样本 vs 微调"的量级差距（ESC-50 上 69.4% → 97.2%）。laos 若走零样本事件标签路线，必须明确告知用户 ~70% 的准确率上限 | [arXiv:2106.13043](https://arxiv.org/abs/2106.13043) |
| Audio-Based Activities of Daily Living (ADL) Recognition with Large-Scale Acoustic Embeddings from Online Videos | Univ. of Texas at Austin，ACM IMWUT 2019 | 只用音频（不用视频）能否识别日常生活活动 | 用 AudioSet 预训练嵌入 + 目标活动与 AudioSet 标签的映射；实验室 + 多受试者研究 | 覆盖沐浴/烹饪/起居/户外等 ADL 类别；用在线视频声音训练即可在真实受试者上取得"promising performance"（论文未在摘要给统一数值，具体各活动 F1 见原文 Table） | **③蒸馏**：证明了从"网上通用声音"迁移到"个人日常活动"是可行的，且不需要个人数据预训练——laos 的冷启动可以照此做，先在通用音频嵌入上跑，再用个人数据增量适配 | [PDF (UT Austin)](https://users.ece.utexas.edu/~ethomaz/papers/j4.pdf) |

---

## 3. 低功耗 always-on 音频（对标 laos 的 ADSP LPAI <5mW 常驻路线）

> 本节的功耗数字是 laos 对外表述"ADSP LPAI <5mW"时必须引用的坐标系。注意：**学术 SOTA 全部是定制 ASIC**，与通用 DSP 上的软件推理不可直接比较，差约 2 个数量级。

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| Advances in Small-Footprint Keyword Spotting: A Comprehensive Review of Efficient Models and Algorithms | NIT Durgapur，Elsevier EAAI 2025 | SF-KWS 的系统性综述，面向 TinyML/MCU 部署 | 归纳 7 类技术（架构 / 学习 / 压缩 / 注意力 / 特征优化 / NAS / 混合），覆盖 **2010–2025 约 250 篇** | 250 篇；CNN 占架构分布 35.4%，DNN 31.2%；MCU 典型约束 **<2 MB flash / <512 KB SRAM** | **①常驻检测**：给 laos 的①环节一个可直接引用的技术选型清单与资源预算口径（<2 MB flash / <512 KB SRAM） | [arXiv:2506.11169](https://arxiv.org/abs/2506.11169) |
| 0.4V 988nW Time-Domain Audio Feature Extraction for Keyword Spotting Using Injection-Locked Oscillators | CEA-Leti，ISSCC 2024 (Session 17.8) | 亚微瓦级 always-on KWS，适配 <0.5V 能量采集供电 | 注入锁定振荡器（ILO）时域特征提取（TD-FEx），65nm，0.4V 供电 | **988 nW**；0.15 mm²（同节点下比先前工艺至少小 3.5×）；10 词 KWS **91% 准确率**；比环形振荡器 TD-FEx 能效高 9× | **①常驻检测**：这是 laos <5mW 最直接的对照点——**学术 SOTA 在 0.988 µW，比 laos 的 5 mW 低约 5000×**。对外表述必须说明这是 ASIC vs 通用 DSP 的差异，否则数字会被质疑 | [DOI:10.1109/ISSCC49657.2024.10454389](https://doi.org/10.1109/ISSCC49657.2024.10454389) |
| A 510-nW Wake-Up Keyword-Spotting Chip Using Serial-FFT-Based MFCC and Binarized Depthwise Separable CNN in 28-nm CMOS | 东南大学等，IEEE JSSC 2021（ISSCC 2020） | 亚微瓦 always-ON KWS 芯片 | 串行 FFT MFCC + 二值化深度可分离 CNN + 逐帧增量计算 + 近阈值电压 | **0.51 µW** @ 40 kHz / 0.41 V；0.23 mm²（28nm）；GSCD 单词 **97.3%**、双词 **94.6%** | **①常驻检测**：给出"亚微瓦 KWS 能到什么准确率"的硬边界——二值化 CNN 下 10 词以内仍有 94–97%，说明 laos 的①环节在通用 DSP 上有充裕的精度余量 | [DOI:10.1109/JSSC.2020.3029097](https://doi.org/10.1109/JSSC.2020.3029097) |
| AAD-KWS: A Sub-µW Keyword Spotting Chip With an Acoustic Activity Detector Embedded in MFCC | IEEE JSSC 2022 | 用声学活动检测（AAD）门控 KWS，进一步压功耗 | 非重叠帧串行 MFCC + 零成本 AAD（用 MFCC 一阶输出门控 NN 与后处理）+ 可调检测窗；28nm，0.4V | **安静场景 0.36 µW / 常态 0.8 µW**；其中 **MFCC 电路仅 170 nW**；AAD 漏检率 0；GSCD 双词 **97.8%** | **①常驻检测**：这是与 laos "VAD 先跑、ASR 后醒"架构**完全同构**的硅验证——两级门控（AAD→KWS）是业已流片证实的正确架构，且 MFCC 前端只占 170 nW | [IEEE Xplore 9888232](https://ieeexplore.ieee.org/document/9888232) |
| A 47-nW Voice Activity Detector (VAD) Featuring a Short-Time CNN Feature Extractor and an RNN-Based Classifier With a Non-Volatile CAP-ROM | Univ. of Macau / Univ. Lisboa，IEEE JSSC 2023（ISSCC 2023） | 极致低功耗 always-on VAD | ST-CNN 特征提取 + RNN 分类器；非易失电容 ROM 存权重，免除上电预加载；65nm | **47 nW**；面积 0.022 mm²；VAD 参数量 **仅 45**；GSCD/TIMIT 整体命中率 **94% / 91%**；0.9–1.3 V、0–60 °C 无显著退化 | **①常驻检测**：**47 nW / 45 参数**是 laos ①环节的理论地板。它证明"VAD 不需要神经网络规模"，laos 若在 ADSP 上跑一个 >1 MFLOP 的 VAD 就明显过重 | [DOI:10.1109/JSSC.2023.3302791](https://doi.org/10.1109/JSSC.2023.3302791) |
| A Self-Sustaining Micro-Watt Programmable Smart Audio Sensor for Always-On Sensing | ETH Zürich / Univ. Bologna，IEEE 2019 | 能量采集自维持的 always-on 音频传感节点 | 混合信号事件驱动前端，最多 128 路时频特征 + 模式识别；室内光伏供能 | always-on 特征提取 **26.89 µW**；含商用 MEMS 麦克风与能量采集子系统的**整机 63 µW**；两类音频流检测准确率 100% | **①常驻检测 + ④即焚**：这是"含麦克风在内的整机功耗"数字（63 µW）——**laos 对外说 <5mW 时最有说服力的对照是这一条**，因为它是系统级而非模块级 | [IEEE Xplore 8752147](https://ieeexplore.ieee.org/document/8752147) |
| An 8.62 µW 75dB-DR SoC End-to-End Spoken-Language-Understanding SoC | Univ. of Zurich / ETH 等，ISSCC 2025 | 端到端口语理解（SLU）SoC，超低功耗 | 通道级 AGC + 时间稀疏性感知的流式 RNN | **8.62 µW**（端到端 SLU）；动态范围 75 dB；文中指出传统 ADC+DSP 中 **AFE + 数字 FEx 合计占系统功耗 >50%** | **③蒸馏**：给出了"把整条 特征提取→理解 链路压到个位数微瓦"的可行性证据，并点明功耗大头在前端而非分类器——laos 优化 ①/③ 时应优先压特征提取 | [DOI:10.1109/ISSCC49661.2025.10904788](https://doi.org/10.1109/ISSCC49661.2025.10904788) |
| TinyChirp: Bird Song Recognition Using TinyML Models on Low-power Wireless Acoustic Sensors | FU Berlin / Inria / RHUL，IEEE IS2 2024 | 低功耗无线声学节点上做在设备端事件检测，替代"全录后取" | nRF52840 (Cortex-M4)；8-bit PTQ + Partial Convolution；时域模型 vs 语谱模型对比 | 精度 **>0.98**；**SD 卡写入减少 90%**；单节电池续航 **2 周 → 8 周**；MCU RAM 预算约 500 KB 量级；语谱图计算在 MCU 上可达 2.4 s（超过推理本身） | **②触发捕获 + ④即焚**：TinyChirp 是"在设备端筛选，只存有价值的片段"的完整量化案例（少写 90%、续航 ×4）。它是 laos "只存有人声片段 + 6 小时后焚毁"这一设计最直接的学术背书 | [arXiv:2407.21453](https://arxiv.org/abs/2407.21453) |

---

## 4. 真实场景说话人日志（speaker diarization in the wild）

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| The Third DIHARD Diarization Challenge | JHU / NIST 等，DIHARD 2021 Workshop | 跨 11 个真实域的鲁棒 diarization | Track1（oracle VAD）/ Track2（system VAD）；EVAL core + full | Track1 最佳单系统 DER **13.45%**（DIHARD I 23.73% → 43% 相对下降）；Track2 最佳 **19.37%**；Track1 中位数从 >30% → 25% → **<20%**；**会议/网络视频/餐厅三域中位数仍高达 35–45%** | **③蒸馏**：这是 laos 必须知道的天花板——"谁在说话"在真实场景仍有 1/3 以上的错误率。laos 若给记忆条目打"说话人"标签，需按 DIHARD III 的真实域 DER（20–45%）设定置信度阈值，而非按会议数据集的个位数 DER | [arXiv:2012.01477](https://arxiv.org/abs/2012.01477) |
| Spot the conversation: speaker diarisation in the wild (VoxConverse) | Univ. of Oxford VGG / Naver，Interspeech 2020 | 野外 YouTube 视频的 diarization 基准 | 半自动标注流水线（视听主动说话人检测 + 说话人验证 + 人工校验） | VoxConverse dev 216 条 / eval 232 条；单条 22–1200 s；**每录音 1–21 位说话人**；BUT 系统 dev **DER 4.0%**（约基线一半）、eval **DER 8.12%** / JER 18.35% | **③蒸馏**：VoxConverse 是"野外音频"最常用基准。注意它的 DER（4–8%）远好于 DIHARD III（13–45%）——**数据集选择会极大影响 laos 对外宣称的 diarization 能力**，必须标明评测集 | [arXiv:2007.01216](https://arxiv.org/abs/2007.01216) |
| AISHELL-4: An Open Source Dataset for Speech Enhancement, Separation, Recognition and Speaker Diarization in Conference Scenario | 西工大 / 北京希尔贝壳 / MSRA，Interspeech 2021 | 中文真实会议场景的多说话人处理 | **8 通道环形麦克风阵列**真实录制会议；含转写 + 说话人语音活动标注 | **211 场会议**、每场 4–8 人、**共 118–120 小时**；含短停顿、重叠语音、快速轮换、噪声 | **③蒸馏（中文）**：laos 是中文场景，AISHELL-4 是唯一公开的真实中文会议阵列语料。laos 的多人分离/说话人归属评测应以此为基准，而非用英文 AMI | [arXiv:2104.03603](https://arxiv.org/abs/2104.03603) |
| M2MeT: The ICASSP 2022 Multi-Channel Multi-Party Meeting Transcription Challenge (AliMeeting) | 阿里巴巴 / 西工大 / 贝壳，ICASSP 2022 | 中文多通道多方会议转写挑战赛 | AliMeeting 语料：8 通道阵列远场 + 头戴近场；Track1 diarization / Track2 multi-speaker ASR | **118.75 小时**（Train 104.75 / Eval 4 / Test 10）；212 / 8 / 20 场；每场 2–4 人、15–30 分钟；DER 采用 RT06 的 0.25 s collar | **③蒸馏（中文）**：与 AISHELL-4 互补（AliMeeting 重叠率更高、2–4 人）。laos 若要宣称中文会议能力，AISHELL-4 + AliMeeting 双基准是行业惯例 | [arXiv:2110.07393](https://arxiv.org/abs/2110.07393) |
| AVA-AVD: Audio-Visual Speaker Diarization in the Wild | Show Lab, National Univ. of Singapore，ACM MM 2022 | 电影等野外视频的视听 diarization（含**完全离屏说话人**） | 在 AVA-Active Speaker 上加 diarization 标注；AVR-Net + 模态掩码 | 从 144 部电影中筛出 **117 部**（剔除配音）；每部 15 min 标注，再切为 3 段 5 min；标注耗时约为视频时长的 8 倍 | **③蒸馏**：AVA-AVD 点出了一个 laos 绕不开的问题——**"听到声音但画面里没有人"**。纯音频的 laos 更依赖这一点：必须假定"录音里有不在场的第三方说话人"，这是隐私四件套设计的输入 | [arXiv:2111.14448](https://arxiv.org/abs/2111.14448) |
| Streaming Sortformer: Speaker Cache-Based Online Speaker Diarization with Arrival-Time Ordering | NVIDIA，2025 | **流式/在线** diarization，低延迟且跨 chunk 保持一致身份 | Arrival-Order Speaker Cache (AOSC) + FIFO 队列 + 当前 chunk；Sort Loss 学到到达时间顺序，规避排列问题 | DIHARD III 上 **DER 18.97% @ ~1 s 延迟**；**19.32% @ 0.32 s 延迟**；训练数据 7,000+ 小时（5,150 h 合成 + 2,030 h 真实，含 AISHELL-4） | **③蒸馏（流式）**：laos 的蒸馏是准实时的，Streaming Sortformer 证明"流式 diarization 在 DIHARD III 上 18.97% 已经比 LS-EEND (19.61%) 更好"——**流式不再是精度妥协**，laos 可以放心做在线归属 | [arXiv:2507.18446](https://arxiv.org/abs/2507.18446) |

---

## 5. 语音情感与健康（vocal biomarkers）

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| emotion2vec: Self-Supervised Pre-Training for Speech Emotion Representation | 上海交大 / 复旦 / 港中文 / 阿里，Findings of ACL 2024 | 通用语音情感表示（跨语言、跨任务） | data2vec 式在线蒸馏；句级损失 + 帧级损失；在 **262 小时**开源情感数据上预训练 | 预训练 262 h；IEMOCAP 上以线性层即超所有同规模 SSL 模型；**9 种语言**数据集上 WA/UA/WF1 均优于基线；emotion2vec+ large 微调数据 42,526 h | **③蒸馏（情感标签）**：laos 用 SenseVoice 打情感标签，emotion2vec 是同赛道最权威的公开基线。laos 的"情感标签准确率"应对标 emotion2vec 在 IEMOCAP 上的线性探测结果，而不是只报 SenseVoice 自报数 | [ACL Anthology 2024.findings-acl.931](https://aclanthology.org/2024.findings-acl.931/) |
| FunAudioLLM (SenseVoice): Voice Understanding and Generation Foundation Models... | 阿里巴巴通义语音团队，2024 | 多语种 ASR + **情感识别 + 音频事件检测**一体化 | SenseVoice-Small 非自回归端到端；SenseVoice-Large | 训练语料 **>300k 小时**；Small 支持 5 语种，Large 支持 50+ 语种；推理比 Whisper-small 快 **5×**、比 Whisper-large 快 **15×** | **③蒸馏**：这就是 laos 当前正在用的模型。论文给出了它的官方口径（300k h 训练、5×/15× 加速），laos 的技术文档应直接引用这两条数字而非二手来源 | [arXiv:2407.04051](https://arxiv.org/abs/2407.04051) |
| Voice Biomarkers for Depression and Anxiety | Kintsugi / MIT，2026 | 直接从原始语音学抑郁/焦虑的**内容无关**生物标记 | 深度网络直接在 raw speech 上训练，与文本特征融合 | **~65,000 段语音 / >23,000 名受试者**训练；在 **~5,000 名独立受试者**上评估；**敏感度与特异度均 71%**；模型已开源 | **情绪周报**：71% 敏感度/特异度是"语音筛查抑郁"目前公开的最大规模数字。laos 的情绪周报**必须以此为标尺**——71% 意味着每 3 次告警约 1 次误报，不能作为临床结论呈现 | [arXiv:2605.09908](https://arxiv.org/abs/2605.09908) |
| Speech-derived acoustic biomarkers for depression: Comprehensive cross-section and longitudinal analyses in different cohorts | 北大六院 / 协和等，*J. Affective Disorders* 2026 | 语音声学标记的跨队列可复现性、症状特异性与**纵向稳定性** | 多队列：发现集 + 独立临床验证集 + **8 周纵向随访**；提取 6,373 个声学特征，稳定性增强弹性网络 + 中介分析，FDR 校正 | **1,857 名参与者**；6,373 特征 → 精简为 **23 个非冗余特征**；**38 个特征**呈异质恢复轨迹；最大普通话抑郁语音数据集（>25k 录音、约 2,000 人）；注册号 ChiCTR2500095151 | **情绪周报**：这是 laos 情绪周报最该引用的一条——它证明"语音特征能追踪**跨 8 周的个体内变化**"，且发现**频谱形状/调制类特征比能量/音质类特征时间敏感度更高**，直接决定 laos 该存哪些特征 | [DOI:10.1016/j.jad.2026.121374](https://doi.org/10.1016/j.jad.2026.121374) |
| Towards the Objective Characterisation of Major Depressive Disorder Using Speech Data from a 12-week Observational Study with Daily Measurements | MIT Media Lab / MGH 等，Interspeech 2025 | 用**每日**语音做 MDD 客观刻画 | 71 例临床确诊 MDD；12 周；每日 PHQ-9 + 5 项语音任务（持续元音、DDK、读句、数字广度、Stroop）；线性混合效应模型分离个体内/个体间 | **71 名患者**；**3,374 次有效音频会话**；言语率与发音率与每日抑郁严重度显著负相关；随改善，基频标准差上升（单调性下降）；HNR 等在真实环境中**不显著**（被手机硬件与背景噪声掩盖） | **情绪周报**：给出 laos 情绪周报的**采样频率设计依据**——需要"每日"而非"每周"才能捕捉到流利度的个体内波动；同时警告：实验室有效的音质特征（HNR）在真实环境失效 | [DOI:10.21437/Interspeech.2025-2556](https://doi.org/10.21437/Interspeech.2025-2556) |
| Behavioral Indicators on a Mobile Sensing Platform Predict Clinically Validated Psychiatric Symptoms of Mood and Anxiety Disorders | MIT / Cogito / DARPA，JMIR 2017 | 被动收集的语音 + 数字痕迹能否预测临床验证的情绪症状 | 73 名参与者为期 12 周；手机平台采集数字痕迹 + 每周语音日记；LASSO 特征选择 + 惩罚逻辑回归 | **73 人 / 12 周 / 1,217 段语音日记 + 51,080,131 个数字痕迹数据点**；交叉验证 AUC：抑郁心境 **0.74**、疲乏 0.56、兴趣缺失 0.75、社会联结 **0.83**；96% 参与者每周至少完成一次语音日记 | **情绪周报 + 隐私四件套**：AUC 0.74–0.83 是"被动感知预测情绪"的经典基线；同时它的可行性数据（96% 周完成率、用户平均"易用性"4.05/5）是 laos 评估长期留存率的参照 | [JMIR 2017;19(3):e75](https://jmir.org/2017/3/e75) |
| Speech as a Multimodal Digital Phenotype for Multi-Task LLM-based Mental Health Prediction | Univ. of Toronto / CAMH / SickKids，2025 | 把语音当**三模态**（转写文本 + 声学 landmark + vocal biomarker）做多任务纵向预测 | 三模态 + 纵向建模 + 多任务学习（同时预测抑郁、自杀意念、睡眠障碍）；Depression Early Warning 数据集 | 平衡准确率 **70.8%**，优于各单模态 / 单任务 / 非纵向方法 | **情绪周报**：证明"纵向建模"本身就能带来增益（非纵向 < 70.8%）。laos 的情绪周报应做成**纵向差分**（相对个人基线），而不是绝对分数判定 | [arXiv:2505.23822](https://arxiv.org/abs/2505.23822) |

---

## 6. 隐私与社会接受度的实证研究

> 本方向只收**实证研究**（问卷、访谈、田野、原型评测），不重复 `always-on-recording-industry-2026-09.md` 里已有的 GDPR / 两方同意州 / 民法典 1033 条。

| 论文 | 机构/会议+年份 | 研究问题 | 方法与数据集 | 关键数字 | 对 laos 的关系 | 链接 |
|---|---|---|---|---|---|---|
| MeMic: Towards Social Acceptability of User-Only Speech Recording Wearables | MIT Media Lab，CHI EA 2024 | **"只录自己"能否提升持续录音的社会接受度** | 硬件 self-VAD 可穿戴（加速度计感知自己发声才开麦）+ 可见指示灯；实验室 N=12 + 在线 N=168 对照实验 | 实验室 N=12，检测错误率 **0.09 ± 0.03**；在线 **N=168**，"自录"范式相对"持续录音"**显著降低社交顾虑与隐私担忧**；形态因素中**吊坠项链最受欢迎** | **隐私四件套**：这是对 laos 最有价值的一条——它用 N=168 实证证明"VAD 触发 + 可见指示灯"这套组合能显著提升接受度。laos 的②触发捕获应配套**显式录音指示灯**，且形态上优先考虑挂坠 | [DOI:10.1145/3613905.3650872](https://doi.org/10.1145/3613905.3650872) |
| Investigating Users' Preferences and Expectations for Always-Listening Voice Assistants | UNC Charlotte / UC Berkeley / Chalmers，ACM IMWUT 2019 | 用户对"下一代 always-listening 语音助手"的期待与数据共享意愿 | **178 人**在线问卷 | N=**178**；参与者能想象的服务大多仍与现有显式指令式助手雷同；当对话不敏感、对服务满意且认为有益、已拥有独立语音助手时，更可能同意共享 | **隐私四件套**：给出 laos 隐私交互设计的关键结论——**同意是情境化的**（取决于内容敏感度 + 感知收益），而非一次性的全局开关。laos 的同意机制应做成分级/情境化 | [DOI:10.1145/3369807](https://doi.org/10.1145/3369807) |
| Privacy Controls for Always-Listening Devices (PhD dissertation) | UC Berkeley，EECS Technical Report 2022 | 为被动收音设备设计隐私许可系统（用户中心视角） | 用浏览器扩展把用户**自己真实的语音助手录音**嵌入问卷；结合问卷、用户研究、原型评测 | 近**一半**参与者不知道自己的交互被**永久存储**；大多数人不知道可以回听；对**超过一半**的录音，参与者认为"永久存储不可接受"（而这正是当前默认）；多数人支持**自动删除**；对家人（如儿童）声音的存储更不适 | **④即焚 + 隐私四件套**：这一条直接为 laos 的"6 小时后焚毁原始 wav"提供了实证依据——**用户明确期待自动删除，而行业默认却是永久存储**。laos 应把"默认 6 小时"作为对外宣传的第一卖点 | [EECS-2022-249 (PDF)](https://digicoll.lib.berkeley.edu/record/273841/files/EECS-2022-249.pdf) |
| I don't mind being logged, but want to remain in control | Aalto Univ. / Tampere Univ. of Technology，CHI 2010 | 手机活动与情境日志（lifelogging）的用户体验田野研究 | 田野研究（field study） | 用户会**很快不再注意**正在被记录；但要求对最私密信息的记录保有**控制权**；浏览被记录内容、从中发现自己生活规律被认为"有趣且好玩" | **隐私四件套 + 记忆检索**：laos 的核心矛盾在这里被精确描述——"不在意被记，但要在意时能控制"。laos 的④即焚之外，还必须提供**用户可随时查看/删除自己记忆**的入口 | [DOI:10.1145/1753326.1753351](https://doi.org/10.1145/1753326.1753351) |
| Engaging research participants to inform the ethical conduct of mobile imaging, pervasive sensing, and location tracking research (iWatch sub-study) | UC San Diego，*J. Transl. Behav. Med.* 2016 | 旁观者（bystander）隐私与知情同意的实证检验 | iWatch 研究（5 个传感器含 SenseCam 外向摄像头）；完成研究后让参与者回顾图像并填退出问卷 | IRB 曾认为**旁观者风险大于研究收益**并要求移除摄像头；但参与者的实际顾虑**主要集中在佩戴不适**，而非隐私或旁观者反应 | **隐私四件套**：揭示了一个 laos 必须警惕的不对称——**伦理审查者担心的（旁观者隐私）与真实用户担心的（佩戴不适）不是同一件事**。laos 的隐私设计不能只满足合规，还要做真实用户研究 | [PMC5110499](https://ncbi.nlm.nih.gov/pmc/articles/PMC5110499/) |
| Using wearable cameras to investigate health-related daily life experiences: A literature review of precautions and risks in empirical studies | Univ. of Birmingham 等，*Research Ethics* 2021 | 可穿戴持续采集在实证研究中的风险与防范综述（含 bystander privacy） | 文献综述；区分 participant privacy 与 bystander privacy 两类风险 | 综述性工作（不提供统一量化指标，具体数字见各原始研究，未证实） | **隐私四件套**：提供了 laos 写"隐私四件套"时最系统的风险分类框架（参与者隐私 / 旁观者隐私 / 数据保密 / 不伤害 / 第三方自主权），可直接作为 laos 隐私文档的分节骨架 | [DOI:10.1177/17470161211054021](https://doi.org/10.1177/17470161211054021) |

---

## 学术界给了哪些定量锚点

> laos 后续所有对外表述都应引用本节数字。每条均带出处，未查到的一律写"未证实"。

### A. 功耗（mW / µW / nW）

| 指标 | 数值 | 出处论文 | 链接 |
|---|---|---|---|
| Always-on VAD（定制 ASIC，65nm） | **47 nW**，0.022 mm²，45 参数，命中率 94%/91% | Lin et al., IEEE JSSC 2023 | [10.1109/JSSC.2023.3302791](https://doi.org/10.1109/JSSC.2023.3302791) |
| MFCC 特征提取单元单独功耗 | **170 nW** | AAD-KWS, IEEE JSSC 2022 | [IEEE 9888232](https://ieeexplore.ieee.org/document/9888232) |
| Sub-µW KWS（AAD 门控，28nm 0.4V） | **0.36 µW（安静）/ 0.8 µW（常态）**，双词 97.8% | AAD-KWS, IEEE JSSC 2022 | [IEEE 9888232](https://ieeexplore.ieee.org/document/9888232) |
| KWS SoC（28nm 0.41V 近阈值） | **0.51 µW**，单词 97.3% / 双词 94.6% | Shan et al., IEEE JSSC 2021 | [10.1109/JSSC.2020.3029097](https://doi.org/10.1109/JSSC.2020.3029097) |
| TD-FEx KWS（0.4V 能量采集） | **988 nW**，0.15 mm²，10 词 91% | CEA-Leti, ISSCC 2024 17.8 | [10.1109/ISSCC49657.2024.10454389](https://doi.org/10.1109/ISSCC49657.2024.10454389) |
| 端到端 SLU SoC | **8.62 µW**，DR 75 dB；AFE+数字 FEx 占系统功耗 >50% | Zhou et al., ISSCC 2025 | [10.1109/ISSCC49661.2025.10904788](https://doi.org/10.1109/ISSCC49661.2025.10904788) |
| **Always-on 音频系统级（含 MEMS 麦克风 + 能量采集）** | **26.89 µW（特征提取）/ 63 µW（整机）** | Magno et al., IEEE 2019 | [IEEE 8752147](https://ieeexplore.ieee.org/document/8752147) |
| 腕戴声学上下文识别（通用传感节点，非 ASIC） | **3.3 mW @ 94% 识别率，续航 168 h** | Pervasive and Mobile Computing 2007 | [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1574119207000053) |
| 常规 MCU 上的音频检测（行业参考，非论文） | 10–30 mW（常规 MCU） vs 400–600 µW（事件驱动/类脑） | 行业汇编（IEEE Spectrum / Innatera 数据），**非同行评审，谨慎引用** | [链接](https://instituteofinterneteconomics.org/always-on-intelligence-is-reshaping-how-the-internet-of-things-operates/) |
| **laos 现状：ADSP LPAI <5mW** | **<5 mW** | laos 项目内部（本仓库），**属于通用 DSP 软件方案** | — |

**解读口径（对外表述建议）**：laos 的 <5 mW 处在两条学术线之间——比定制 ASIC 的系统级 SOTA（63 µW）高约 **80 倍**，但比通用 MCU 的常规模数（10–30 mW）低 **2–6 倍**。正确的说法是"**在通用 DSP 软件栈上做到了与专用音频 ASIC 同一量级的一半数量级以内**"，而不是"达到学术 SOTA"。

### B. 数据量与存储

| 指标 | 数值 | 出处 | 链接 |
|---|---|---|---|
| 人一天说话量（2025 最新大样本） | 男 **11,950** 词/天，女 **13,349** 词/天；个体跨度 **100 → 120,000** 词/天 | Tidwell et al., JPSP 2025（N=2,197，631,030 段录音） | [10.1037/pspp0000534](https://doi.org/10.1037/pspp0000534) |
| 人一天说话量（2007 经典值） | 男女均约 **16,000** 词/天；最健谈 47,016 vs 最沉默 695 | Mehl et al., *Science* 2007（N=396） | [U Arizona PDF](https://repository.arizona.edu/bitstream/10150/623432/1/EAR%20CDPS%20in%20press.pdf) |
| EAR 最低可用采样密度 | 每 **12.5 分钟**录 **30 秒**（≈5–6 次/小时），清醒时段全程佩戴约 17 h/天 | Mehl EAR 方法学 | [同上](https://repository.arizona.edu/bitstream/10150/623432/1/EAR%20CDPS%20in%20press.pdf) |
| **端上筛选带来的存储/续航收益** | SD 卡写入 **减少 90%**，单节电池续航 **2 周 → 8 周**（×4） | TinyChirp, IS2 2024 | [arXiv:2407.21453](https://arxiv.org/abs/2407.21453) |
| Ego4D 数据规模 | 3,670 h / 931 人 / 约 **7 TB**（含视频、音频、gaze、3D） | Ego4D, CVPR 2022 | [arXiv:2110.07058](https://arxiv.org/abs/2110.07058) |
| Ego-Exo4D 数据规模 | 1,286.3 h / 740 人 / **7 麦克风阵列** | Ego-Exo4D, CVPR 2024 | [arXiv:2311.18259](https://arxiv.org/abs/2311.18259) |
| AudioSet 规模 | 2,084,320 段 ×10 s ≈ **5,800 小时**，527 类 | AudioSet, ICASSP 2017 | [10.1109/ICASSP.2017.7952261](https://doi.org/10.1109/ICASSP.2017.7952261) |
| FSD50K 规模 | 51,197 段 / **108.3 小时** / 200 类 | FSD50K, ICASSP 2022 | [arXiv:2010.00475](https://arxiv.org/abs/2010.00475) |
| AISHELL-4 规模 | **118–120 小时** / 211 场 / 每场 4–8 人 / 8 通道 | AISHELL-4, Interspeech 2021 | [arXiv:2104.03603](https://arxiv.org/abs/2104.03603) |
| AliMeeting 规模（含原始体积） | **118.75 小时**；训练集远场 tar.gz **73.24 GB** + 近场 **22.85 GB** | M2MeT, ICASSP 2022 / OpenSLR | [arXiv:2110.07393](https://arxiv.org/abs/2110.07393) · [OpenSLR SLR119](https://www.openslr.org/119/) |
| SenseVoice 训练语料 | **>300k 小时** | FunAudioLLM 2024 | [arXiv:2407.04051](https://arxiv.org/abs/2407.04051) |
| emotion2vec 预训练 / 微调语料 | 预训练 **262 小时**；emotion2vec+ large 微调 **42,526 小时** | emotion2vec, Findings ACL 2024 | [ACL Anthology](https://aclanthology.org/2024.findings-acl.931/) |
| 音频 vs 视频的体积优势 | 音频档案文件尺寸远小于视频或图像序列（定性，原文未给压缩比） | Ellis & Lee, CARPE 2004 | [10.1145/1026653.1026659](https://doi.org/10.1145/1026653.1026659) |
| laos"原音频→文本"的压缩比 | 未证实（本仓库暂无实测数据，建议补测：6 小时 wav 体积 vs 对应文本 + 嵌入体积） | — | — |

### C. 纵向研究规模（人 × 时长）

| 研究 | 规模 | 关键结果 | 链接 |
|---|---|---|---|
| 语音声学标记 · 抑郁多队列纵向 | **1,857 人**（发现集 + 独立临床验证集 + **8 周随访**）；6,373 特征 → **23 个**非冗余；**38 个**特征呈纵向恢复轨迹 | 频谱形状/调制类特征时间敏感度高于能量/音质类 | [10.1016/j.jad.2026.121374](https://doi.org/10.1016/j.jad.2026.121374) |
| MDD 每日语音 · 12 周 | **71 例**确诊 MDD，**12 周**，**3,374 次**有效音频会话，每日 PHQ-9 | 言语率/发音率与每日抑郁严重度显著负相关 | [DOI:10.21437/Interspeech.2025-2556](https://doi.org/10.21437/Interspeech.2025-2556) |
| 移动感知预测情绪症状 | **73 人 / 12 周 / 1,217 段语音日记 + 51,080,131 个数字痕迹点** | AUC：抑郁心境 0.74、社会联结 0.83 | [JMIR 2017;19(3):e75](https://jmir.org/2017/3/e75) |
| 远程抑郁症数字测量 | **600 人受邀 / 415 人登录 / 384 人**产出有效数据，12 周，PHQ-9 完成率 **83.35% (4,151/4,980)** | 34 个行为特征中 11 个与 PHQ-9 显著相关；AUC 0.656 | [PMC8386379](https://pmc.ncbi.nlm.nih.gov/articles/PMC8386379/) |
| 环境音规律性与抑郁 | **112 名志愿者 / 2 周**，每 5 分钟录 15 秒 | 日常规律性与自评抑郁症状负相关 | [U Toronto 报道 (JMIR)](https://www.utoronto.ca/news/smartphones-could-help-monitor-mental-health-recording-ambient-sounds-u-t-researchers) |
| ENV 录音 · 每日词量 | **2,197 人 / 22 个样本 / 631,030 段**环境录音（年龄跨度 10–94） | 男 11,950 / 女 13,349 词/天 | [10.1037/pspp0000534](https://doi.org/10.1037/pspp0000534) |
| 语音生物标记 · 抑郁焦虑 | 训练 **>23,000 人 / ~65,000 段**；评估 **~5,000 名**独立受试者 | 敏感度与特异度均 **71%** | [arXiv:2605.09908](https://arxiv.org/abs/2605.09908) |
| laos 纵向规模 | 未证实（本仓库暂无长期用户研究数据） | — | — |

---

## 学术共识

1. **常驻音频感知的功耗问题在芯片层已经"解决"，瓶颈移到了系统层**——亚微瓦级 VAD（47 nW）与 KWS（0.36–0.99 µW）均已流片验证，且 AAD→KWS 的两级门控架构与 laos 的"VAD 先跑、ASR 后醒"完全同构。（Lin et al., JSSC 2023；AAD-KWS, JSSC 2022；CEA-Leti, ISSCC 2024）
2. **"在设备端筛选、只存有价值片段"是被量化证实的最优架构**——TinyChirp 用 SD 卡写入减少 90%、续航 ×4 证明了这一点，而不是靠"先全录再后处理"。（TinyChirp, IS2 2024）
3. **真实场景的说话人日志远未解决，且数据集选择会剧烈影响宣称的性能**——同一代技术在 VoxConverse 上 DER 4–8%，在 DIHARD III 的真实域（会议/网络视频/餐厅）中位数仍为 35–45%。（DIHARD III 2021；VoxConverse 2020）
4. **语音能追踪个体内的纵向情绪变化，但必须做"相对个人基线"的差分**——1,857 人 8 周随访识别出 38 个纵向特征；多任务纵向建模（70.8%）优于任何单模态/非纵向方法。（JAD 2026；Ali et al. 2025）
5. **用户对"被录多久、留多久"的认知与实际严重脱节，而自动删除是他们最期待的功能**——近一半用户不知道录音被永久保存，超过一半的录音被用户认为"永久存储不可接受"。（Malkin, UC Berkeley 2022）
6. **"只录自己 + 可见指示"能显著提升持续录音的社会接受度**——N=168 的对照实验显示，self-VAD 范式相对持续录音显著降低社交顾虑与隐私担忧。（MeMic, CHI EA 2024）

## 学术分歧 / 未解问题

1. **真实域 diarization 的天花板在哪、还能不能靠规模解决**：DIHARD III 三年间最佳 DER 从 23.73% 降到 13.45%（43% 相对下降），但餐厅/会议/网络视频三域中位数仍卡在 35–45%，尚未看到收敛迹象。（DIHARD III）
2. **语音"生物标记"到底是生理标记还是数据集相关性**：65,000 段 / >23,000 人训练的模型只达到 71% 敏感度与特异度，且训练数据为专有、标签验证方式未公开——评审意见明确指出"无法排除数据集特异性模式"。（arXiv:2605.09908 及其公开评审）
3. **实验室有效的声学特征在真实环境中会失效**：HNR（谐噪比）等音质特征在实验室显著，但在 12 周真实手机录音研究中被硬件差异与背景噪声掩盖而不显著——哪些特征能跨设备迁移仍无定论。（Interspeech 2025）
4. **零样本 vs 微调的量级差距是否可接受**：CLAP/AudioCLIP 的零样本分类在 ESC-50 上只有 69.4%，而微调可达 97.15%——"不训练就能加新事件标签"的梦想与准确率之间仍有近 28 个百分点的鸿沟。（AudioCLIP, ICASSP 2022）
5. **录制者的知情同意能否代替旁观者的同意**：IRB 曾因旁观者风险否决研究，但真实参与者的顾虑却集中在佩戴舒适度而非隐私——审查者视角与用户视角的错位尚无共识解法。（Nebeker et al., JTBМ 2016）
6. **同意应当是"一次性全局"还是"情境化分级"**：178 人调查显示同意高度依赖内容敏感度、感知收益与既有设备拥有情况，但工业界普遍实现的是单次安装时授权——两者之间的接口设计仍未解决。（Tabassum et al., IMWUT 2019）

---

## 建议归档的论文

> 本节供批量下载脚本使用，arXiv ID 已去掉版本号。

- arXiv:2504.02624 — EgoLog: Ego-Centric Fine-Grained Daily Log with Ubiquitous Wearables — 音频+IMU 做细粒度日常日志，超基线 12%/15%，与 laos 的③蒸馏流水线同构。
- arXiv:2110.07058 — Ego4D: Around the World in 3,000 Hours of Egocentric Video — 情景记忆检索（Episodic Memory）最权威公开基准，laos 的记忆检索评测口径来源。
- arXiv:2311.18259 — Ego-Exo4D — 公开数据中麦克风阵列配置最完整的日常长时录音集（7-mic），laos 做声源定位的基准。
- arXiv:2406.08056 — DCASE 2024 Task 4: Sound Event Detection with Heterogeneous Data and Missing Labels — 家庭常驻麦克风"该检测什么"的唯一年度权威考卷（best PSDS 0.604）。
- arXiv:2211.06687 — Large-scale Contrastive Language-Audio Pretraining (CLAP) — audio↔text 同一嵌入空间，laos 记忆库跨模态检索的现成方案。
- arXiv:2106.13043 — AudioCLIP: Extending CLIP to Image, Text and Audio — 给出零样本（69.4%）vs 微调（97.15%）的量级差距，用于校准事件标签的可信度上限。
- arXiv:2010.00475 — FSD50K — 唯一可商用许可（CC）的 200 类声音事件集，比 AudioSet 更适合裁剪成家庭事件标签器。
- arXiv:2110.05069 — Efficient Training of Audio Transformers with Patchout (PaSST) — 通用音频事件分类在干净数据集上的天花板（ESC-50 96.8%）。
- arXiv:2407.21453 — TinyChirp: Bird Song Recognition Using TinyML on Low-power Wireless Acoustic Sensors — "端上筛选、只存有价值片段"的量化背书（少写 90%、续航 ×4）。
- arXiv:2506.11169 — Advances in Small-Footprint Keyword Spotting: A Comprehensive Review — ①常驻检测的技术选型清单与 MCU 资源预算口径（<2 MB flash / <512 KB SRAM）。
- arXiv:2012.01477 — The Third DIHARD Diarization Challenge — 真实域 diarization 的天花板（会议/网络视频/餐厅中位数 DER 35–45%），laos 说话人标签置信度的依据。
- arXiv:2007.01216 — Spot the conversation: speaker diarisation in the wild (VoxConverse) — 野外音频最常用基准，用于说明"数据集选择会剧烈影响宣称性能"。
- arXiv:2104.03603 — AISHELL-4 — 唯一公开的真实中文会议阵列语料（120 h / 8 通道 / 4–8 人），laos 中文场景的必测基准。
- arXiv:2110.07393 — M2MeT / AliMeeting — 与 AISHELL-4 互补的中文会议语料（重叠率更高），双基准是行业惯例。
- arXiv:2111.14448 — AVA-AVD: Audio-Visual Speaker Diarization in the Wild — 提出"完全离屏说话人"问题，是 laos 隐私四件套设计的直接输入。
- arXiv:2507.18446 — Streaming Sortformer: Speaker Cache-Based Online Speaker Diarization — 证明流式 diarization（DIHARD III 18.97% @1s）已不逊离线，laos 可放心做在线归属。
- arXiv:2407.04051 — FunAudioLLM (SenseVoice) — laos 正在用的模型官方口径（>300k h 训练、比 Whisper-large 快 15×），技术文档应直接引用。
- arXiv:2605.09908 — Voice Biomarkers for Depression and Anxiety — 语音筛查抑郁的最大规模公开数字（71% 敏感度/特异度），laos 情绪周报的标尺。
- arXiv:2505.23822 — Speech as a Multimodal Digital Phenotype for Multi-Task LLM-based Mental Health Prediction — 证明纵向建模本身带来增益（70.8%），laos 周报应做纵向差分。
- arXiv:2206.01542 — Detecting the Severity of Major Depressive Disorder from Speech: A Novel HARD-Training Methodology — 基于 RADAR-MDD 远程纵向队列，是"真实世界远程语音采集"方法学的代表。
- arXiv:2407.06947 — Audio-Language Datasets of Scenes and Events: A Survey — 系统梳理 AudioSet/FSD50K/AudioCaps 等数据集的许可与失效问题（含 AudioSet 18% 链接失效的实证）。
- arXiv:2310.15648 — Dynamic Convolutional Neural Networks as Efficient Pre-trained Audio Models — CNN 侧在 ESC-50 / FSD50K / DCASE20 的效率-精度帕累托前沿，用于端上模型选型。
