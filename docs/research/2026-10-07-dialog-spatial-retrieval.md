# 对话听觉与空间隐私定向检索（强命中语料复用）

> 日期：2026-10-07
> 来源：venue-expansion 语料（35 venue 切片，[多场地普查](2026-10-06-venue-expansion-survey.md)）`laos_relevant_strong` 强命中工作集（934 行），用 Task 2 成品 `scripts/query_corpus.py` 做定向 grep。
> 纪律：year/venue/题目一律抄自语料 json；无摘要篇目按标题级裁决（见文末诚实声明）；子题计数是**强命中工作集内的标题+摘要正则命中数**，不是文献全集。
> 姊妹篇：[agentos-governance-literature](2026-10-07-agentos-governance-literature.md)（Task 3，agent-os 窄分支 49 篇）。

---

## §方法

- **取材**：`query_corpus.py --strong-only --limit 0 --json --grep <宽交替正则>`（crossref 文件多无摘要，交替式必须放宽到同义词族，如 `barge|interrupt|full-duplex|turn-taking`）。§二 用 `--topic spatial-privacy --strong-only --limit 0 --json` 全量导出 114 行后按六词根（binaural / spatial audio / beamform / acoustic camera / speech privacy / audio watermark，即 Task 2 主题词表原文）归桶。
- **§一 计数**：barge/interrupt/full-duplex/turn-taking **4** · wake[- ]?word|keyword spotting **27** · voice activity|endpoint|end-point **24** · diariz|speaker separation **44**。四子题互有重叠（VAP 篇同时落在 barge 与 VAD 两题；桥接篇单独点名）。
- **§二 计数**：spatial-privacy 主题 114 行 = binaural/spatial/beamform/acoustic-camera 类 **105** + audio watermark 类 **9** + speech privacy 类 **0** + 其他 **0**（105+9+0+0=114，分类完备）。
- **裁决记法**：●已落地（laos 侧机构在库）/ ◐部分落地或推荐 / ○不做（附理由）。

---

## §一 对话调度线

### 1.1 barge-in / 打断 / 全双工 —— 4 篇

检索式 `--grep "barge|interrupt|full-duplex|turn-taking"`，命中 **4**，全部真命中（VAP——语音活动投影——一族）：

| # | year·venue·题目 |
|---|---|
| 1 | 2025·COLING·Investigating the Impact of Incremental Processing and Voice Activity Projection on Spoken Dialogue Systems |
| 2 | 2024·LREC-COLING·Multilingual Turn-taking Prediction Using Voice Activity Projection（含普通话） |
| 3 | 2025·EMNLP·Proactive Hearing Assistants that Isolate Egocentric Conversations（桥接篇：自中心双耳耳机自动隔离佩戴者的对话伙伴，跨到 §二空间线） |
| 4 | 2025·NAACL·Yeah, Un, Oh: Continuous and Real-time Backchannel Prediction with Fine-tuning of Voice Activity Projection（backchannel="嗯/对"附和预测） |

**与 laos 的关系**：文献的 VAP 路线是**学习式预测**（模型预测未来数百 ms 的双方语音活动来决定何时发起/让位/附和），laos 的 dialogsched.py（GenerationGate 代数打断：interrupt() 作废一切在途流、is_current() 逐块准入，"迟到的回答宁可丢不可播"）+ wakegate.py barge_in()（仅 Processing 态有效）+ turnpolicy.py（speak/hold/stop 三态策略位、min_hold_ms 防过早响应）是**规则态执行机构**——两者正交：turnpolicy 的策略位正是 VAP 类模型将来的接入点，但学习式模型只进驱动子进程，核心保持纯函数。

**裁决：●**（打断执行机构 v0.17.0 起在库；VAP 预测列为远期驱动候选，不欠债）。

### 1.2 唤醒词 / KWS —— 27 篇（语音 KWS 有效 ≈23）

检索式 `--grep "wake[- ]?word|keyword spotting"`，命中 **27**，其中 4 篇为词面撞车（PRADO/EMNLP'19-demo 文档分类摘要顺带提 wake word、ACL'14 形态学分词文本 KWS、TPAMI'19 文档图像 KWS、AfriHate 摘要顺带提 keyword spotting），语音侧有效约 **23**。强命中 ≤8：

| # | year·venue·题目 |
|---|---|
| 1 | 2025·Findings-ACL·AnalyticKWS: Towards Exemplar-Free Analytic Class Incremental Learning for Small-footprint Keyword Spotting（小足迹 KWS 的类增量学习——唤醒词词表演进的免回放路线） |
| 2 | 2024·NAACL·The taste of IPA: Towards open-vocabulary keyword spotting and forced alignment in any language（音素模型 → 任意语言**开放词表** KWS） |
| 3 | 2022·COLING·Recycle Your Wav2Vec2 Codebook: A Speech Perceiver for Keyword Spotting（复用预训练码本的小参数 KWS） |
| 4 | 2022·IJCAI·BiFSMN: Binary Neural Network for Keyword Spotting（二值网络极限压缩） |
| 5 | 2023·ACM-MM·TE-KWS: Text-Informed Speech Enhancement for Noise-Robust Keyword Spotting（文本引导增强+KWS 联合，抗噪） |
| 6 | 2020·EURASIP-JASMP·A depthwise separable convolutional neural network for keyword spotting on an embedded system（嵌入式实测——与 laos 端侧约束同场景） |
| 7 | 2023·EURASIP-JASMP·Multi-task deep cross-attention networks for far-field speaker verification and keyword spotting（**声纹+唤醒合一**的个性化触发） |
| 8 | 2026·TASLP·Effective User-Defined Keyword Spotting With Dual-Stage Matching, Multi-Modal Enrollment, and Continual Adaptation（用户自定义唤醒词+持续适配） |

值得点名的未列篇：NAACL'22-industry **AB/BA analysis**（隐私约束下的 KWS 召回评测框架——口径与 §二隐私线互文）；SIGIR'21 **Multimodal Activation**（不用唤醒词唤醒对话机器人——wakegate 的反例路线）；WASPAA'23 **唤醒词 DoA（弹性面板单传感器）**（唤醒与空间定位合一，跨到 §二）；NAACL'22-industry **FPI**（Alexa/Cortana 级助手唤醒→ASR 链路的失败点隔离——唤醒链路当"电源键"的工程同构）；IJCAI'22 之外的 EMNLP'19-demo Honkling（浏览器内 KWS 个性化）。

**与 laos 的关系**：wakegate.py 的四态会话机（Sleeping→Listening→Processing→FollowUp，唤醒只由端侧 KWS 音频触发、ASR 文本永不唤醒、会话有期限="权限窗口"）是**消费者**，触发源在驱动侧——文献恰为该触发源供弹药：小足迹（#1/#3/#4/#6 ↔ sherpa-onnx wenetspeech-zipformer **3.3M** 量级）、开放词表/自定义词（#2/#8 ↔ 已从上游 wake_keywords.txt 拿到"小乐"词表 `x iǎo l è @小乐` 拼音流）、声纹+唤醒合一（#7 ↔ 可选的"只认主人"增强）。**实测项回指**：[voicenpu-adoption](2026-10-06-voicenpu-adoption.md) §六#1——Windows 官方 sherpa-onnx 库 + wenetspeech 3.3M 模型 + "小乐"词表三件已备齐，laos 唤醒层（drv 侧）即可闭环，本批文献不改该计划、只补齐其选型依据。

**裁决：◐**（会话状态机已落地 ●；端侧 KWS 实测闭环是 voicenpu §六#1 的待办，文献确认 3.3M 级小模型+自定义词表是成熟路线）。

### 1.3 VAD / 端点 —— 24 篇

检索式 `--grep "voice activity|endpoint|end-point"`，命中 **24**（约 5 篇为管线顺带提及：消防面罩通讯、字幕缺失检测、车载 AEC、心理治疗行为码管线、TokenVerse 统一框架——其摘要含 "voice activity detection" 字样；另有 VAP 两篇与 1.1 重叠）。强命中 ≤8：

| # | year·venue·题目 |
|---|---|
| 1 | 2024·LREC-COLING·InaGVAD: A Challenging French TV and Radio Corpus Annotated for Speech Activity Detection and Speaker Gender Segmentation（广播域 SAD 标注语料——全天候听觉日志的域外对照） |
| 2 | 2016·EURASIP-JASMP·Voice activity detection algorithm based on long-term pitch information（长时基音——能量 VAD 的经典上界：不靠响度靠有声性） |
| 3 | 2022·EURASIP-JASMP·AUC optimization for deep learning-based voice activity detection（直接优化 AUC 而非 F1 的训练口径） |
| 4 | 2023·EURASIP-JASMP·Voice activity detection in the presence of transient based on graph（**瞬态噪声**下的 VAD——敲门/餐具声比语音更"响"） |
| 5 | 2025·EURASIP-JASMP·Single-microphone speaker separation and voice activity detection in noisy and reverberant environments（单麦分离+VAD 联合，混响域） |
| 6 | 2026·TASLP·Dual-Branch Residual-Attention Network With LASCP Features for Robust Joint Direction of Arrival Estimation and Voice Activity Detection（**DOA+VAD 联合**——跨到 §二空间线："有方向的人声"） |
| 7 | 2026·TASLP·Low-Rate Voice Activity Detector Over Wireless Acoustic Sensor Networks（低码率 VAD 事件流——常驻漏斗的带宽对偶问题） |
| 8 | 2019·GlobalSIP·A Comparison of Boosted Deep Neural Networks for Voice Activity Detection（DNN 增强路线代表作） |

未列点名词根近亲：JASMP'15 长时谱平坦度 VAD（Erratum；能量/谱平坦度正是 laos 能量 VAD 的直接同族）、TMM'16 Visual VAD in the Wild、TMM'21 RealVAD（身体运动判语音活动）。

**与 laos 的关系**：vad.py（RMS 能量阈值+滞回+补边，流式=批式一致，零依赖 audioop 兜底纯 Python）+ vadmetrics.py（FA/FR/F1 + **BG-FAR** 背景误报率，f1≥floor 防装死闸门）已把"常驻检测只判有没有人声、无声块零存储"的漏斗第一级落地；文献 DNN 路线不进核心（零依赖承诺锁死选型），但 #4 瞬态噪声难点与 #6 DOA+VAD 联合是两张期票——前者正是 BG-FAR 指标存在的理由（隔壁桌说话/敲桌子的误报），后者是 binaural.py 与 vad.py 合并成"空间选择性 VAD"的文献形态。

**裁决：●**（能量 VAD+指标口径在库；DNN VAD 若将来要，走驱动子进程，当前无缺口）。

### 1.4 说话人 / 分离 —— 44 篇（四子题最厚）

检索式 `--grep "diariz|speaker separation"`，命中 **44**（1 篇词面撞车：Findings-ACL'24 Who Wrote When? 作者 diarization=文本署名）。强命中 ≤8（偏"laos 常驻/流式场景"挑选）：

| # | year·venue·题目 |
|---|---|
| 1 | 2020·COLING·A Comprehensive Evaluation of Incremental Speech Recognition and Diarization for Conversational AI（**流式增量** SR+diarization 评测——最贴 laos 常驻漏斗的一篇） |
| 2 | 2024·LREC-COLING·ALLIES: A Speech Corpus for Segmentation, Speaker Diarization, Speech Recognition and Speaker Change Detection（分割/diarization/ASR/说话人变化四任务语料+评测协议） |
| 3 | 2024·CHiME-workshop·The CHiME-8 DASR Challenge for Generalizable and Array Agnostic Distant ASR and Diarization（阵列无关远场 ASR+diarization——消费级麦克风的行业靶场） |
| 4 | 2024·ICME·Winner Takes It All: An Efficient Overlap-Aware Hybrid Online Diarization with Partial Backtracking（**在线**+重叠感知+部分回溯——流式与纠错的折中） |
| 5 | 2026·AAAI·SpeakerLM: End-to-End Versatile Speaker Diarization and Recognition with Multimodal LLMs（LLM 端到端 diarization） |
| 6 | 2026·AAAI·WhisperDiari: A Whisper-Based Speaker Diarization Framework in Token Space（Whisper token 空间做 diarization——与 laos 本地 ASR 栈同底座） |
| 7 | 2026·TASLP·Efficient and Robust Speaker Diarization via Structured Pruning of Self-Supervised Models（SSL 模型剪枝——端侧化方向） |
| 8 | 2026·TASLP·Label-Free Speaker Diarization Using Self-Supervised Speaker Embeddings（免标注 diarization） |

未列点名块：EMNLP'22 Speaker Overlap-aware Neural Diarization（会议多人重叠）、ACM-MM'22 AVA-AVD / ACM-MM'23 远场视听 diarization（视觉辅助）、ACM-MM'24 Keynote Speaker Diarization、医疗应用块（心理治疗行为码/痴呆长访谈/自动病历 scribe——diarization 的"谁在说"在临床记录里是合规刚需）。

**与 laos 的关系**：laos 当前是**单用户**常驻听觉（唤醒会话内一个主人），diarization 无核心落点；它的两个远期挂点是——①多人场景下 journal 转写的"谁在说"属性（若 laos 进入会议/家庭多人场景，#1/#4 的在线增量口径是唯一可用的形态，批式 diarization 与常驻漏斗不兼容）；②WhisperDiari 证明 diarization 可以寄生在 ASR 模型 token 空间，与 laos"本地 ASR 全本地"红线同向（不引第二个大模型）。

**裁决：○**（当前单用户场景不做；多人场景列为远期驱动子进程候选，#1/#4/#6 三篇留档）。

---

## §二 空间隐私线

`--topic spatial-privacy --strong-only --limit 0 --json` 全量 **114 行**（2014–2026；有摘要仅 **38/114**，76 篇标题级）。按 Task 2 主题词表六词根归桶（一词多根按并集计，105+9+0+0=114 完备）：

> venue 分布：EURASIP-JASMP 31 · GlobalSIP 19 · TASLP 17 · WASPAA 15 · ACM-MM 6 · AAAI 6 · NeurIPS 5 · ACL 系 4 · TMM 3 · ICME 2 · TOMM 2 · 其他（ICCV'21/IJCAI'23/IJCAI'26/PAMI'23）4。**声学四大件（JASMP+TASLP+WASPAA+GlobalSIP）占 72%**——这条线的文献重心在信号处理圈，不在 NLP 圈。

### 2.1 binaural / spatial / beamform / acoustic camera 类 —— 105 篇

词根构成：beamform 涉及 50（仅 beamform 47）· binaural 涉及 38（仅 binaural 31）· spatial audio 涉及 25（仅 spatial audio 20）；acoustic camera 词根 **0 命中**。其中 **17 篇是 GlobalSIP 无线/雷达/声呐波束成形**（massive MIMO/mmWave/MISO 下链/相控阵——与声学只有数学同源），声学侧实为 **88** 篇。代表 3 篇：

| # | year·venue·题目 | 桶内角色 |
|---|---|---|
| 1 | 2025·EMNLP·Proactive Hearing Assistants that Isolate Egocentric Conversations | 自中心双耳自动分离"佩戴者的对话伙伴"——**空间选择性听觉**的隐私形态（§一 1.1#3 同篇，两线桥接） |
| 2 | 2025·EURASIP-JASMP·Improving multi-talker binaural DOA estimation by combining periodicity and spatial features | 多说话人双耳 DOA=周期性+空间双流——与 laos binaural.py（Goertzel 逐频点 ILD/IPD）+ vad（能量流）的双流结构同构 |
| 3 | 2022·EURASIP-JASMP·An overview of machine learning and other data-based methods for spatial audio capture, processing, and reproduction | 空间音频采集/处理/重放的数据方法**综述锚**——本桶 105 篇的地图页 |

桶内其他值得点名：WASPAA'25 Learning Robust Spatial Representations from Binaural Audio（双耳特征蒸馏）、TASLP'26 Array-Aware Ambisonics and HRTF Encoding for Binaural Reproduction with Wearable Arrays（可穿戴阵列→Ambisonics→双耳，正是 foa.py 的应用形态）、NeurIPS'25 MRSAudio（大规模实测空间音频数据集）、NeurIPS'22 BinauralGrad / ACL'25 In-the-wild Audio Spatialization（生成式单声道→双耳）、WASPAA'25/TASLP'26 ROI（感兴趣区）波束成形三连（会议/助听眼镜的"指向性听觉"）。

**与 laos 的关系**：binaural.py（ILD/IPD 信号侧线索）+ micgeom.py（阵列几何先验）+ foa.py（FOA 编解码格式地基）已是这条线的**最小内核版**，本桶证明该地基的文献密度足够厚（88 声学篇）；学习式渲染/波束成形/空间生成全部属驱动子进程，核心只保留纯 stdlib 线索件。ROI 波束成形一族是"听觉的 task_scope"——空间上的选择性注意，与 laos 治理叙事（选择性授权）同构但暂不做。

**裁决：◐**（线索件三件已落地 ●；学习式空间处理与 ROI 波束成形列远期驱动，核心零依赖不动）。

### 2.2 audio watermark 类 —— 9 篇

词根 `audio watermark` 恰 9 篇（2018–2026，神经水印为主）。代表 3 篇：

| # | year·venue·题目 | 桶内角色 |
|---|---|---|
| 1 | 2024·EMNLP·IDEAW: Robust Neural Audio Watermarking with Invertible Dual-Embedding | 可逆双嵌入神经水印——NLP 圈也认的锚点件 |
| 2 | 2024·NeurIPS·AudioMarkBench: Benchmarking Robustness of Audio Watermarking | 神经音频水印鲁棒性**基准**——本桶的评测地图 |
| 3 | 2026·AAAI·Yours or Mine? Overwriting Attacks Against Neural Audio Watermarking | 水印**覆写攻击**——水印作为安全机制的攻面 |

其余 6 篇：AudioQR（NeurIPS'23，水印携 QR 码）、Adversarial Audio Watermarking（ICME'23，深特征嵌入）、V²A-Mark（ACM-MM'24，视听水印+篡改定位）、区块链分发水印（TOMM'22）、DCT-SVD 图像嵌音频（JASMP'18）、SNR 约束参数优化（TMM'18）。

**与 laos 的关系**：水印是**内容侧**的可追溯技术，laos 隐私红线是**行为侧**治理——录音只由显式 syscall 触发、`LAOS_REC=0` 全局禁录、ASR 全本地（不录＞会匿名）。两者不在一个层面：laos 的立场是"少录、显式录、录了不出本机"，因此匿名化/水印都无用武之地；唯一期票是将来若 journal 音频段需要带出处外发（证据链/审计调档），AudioMarkBench 式水印可作 provenance 件再评估。

**裁决：○**（当前不做；provenance 场景出现时按 AudioMarkBench 基准重开）。

### 2.3 speech privacy 类 —— 0 篇

词根 `speech privacy` **零命中**；放宽到 privacy/anonymize/de-identify/eavesdrop/surveillance 等近义词，114 行里也只有 2.2#6 区块链水印一篇摘要顺带提到 "privacy"。**这是本线最重要的发现**：主题名"spatial-privacy"的一半（privacy）在语料里没有独立文献支撑——捕获语料时 privacy 半名实际全靠 binaural/spatial（听觉的"空间选择性"隐喻）撑住。对 laos 恰是背书：设备侧语音隐私的可行解不是"语音匿名化技术"（文献稀缺不是偶然——效果与可逆性互相拆台），而是**治理式红线**（不录/显式录/本地处理），laos 三条红线（syscall 触发、LAOS_REC=0、本地 ASR）正是这条稀疏文献带里少数站得住的工程答案。

**裁决：○**（无需做——红线即方案；语音匿名化不进任何层）。

### 2.4 其他 —— 0 篇

六词根分类后无剩余（105+9+0+0=114），无分类外溢出。

---

## 附注：DRIFT / TuneAgent 标题上下文补查（Task 3 遗留）

Task 3 报告疑虑#1 提到 agent-os 窄分支有两篇【仅标题】高权重裁决篇。本次定向检索顺带补查，两篇**在语料中仍无摘要**（crossref 会议记录快照），但标题本身的信息量可以再榨一层：

- **DRIFT: Dynamic Rule-Based Defense with Injection Isolation for Securing LLM Agents**（NeurIPS 38·2025·DOI 10.52202/085713-2791）——标题三段拆解：动态规则（dynamic rule-based）+ 注入隔离（injection isolation）+ 守护对象是 LLM agent。比 Task 3 表中"沙箱线确认"更具体的读法：它是**规则库动态更新的隔离防御**，与 laos 的 risk.py/judge.py（规则闸门）+ sandbox.py（隔离执行）是同构的两件套——Task 3 的 ◐P2 裁决（prejudge 注入特征检查）维持不变，标题级证据略强化"规则态而非学习态防御"的路线一致性。
- **TuneAgent: Agentic Operating System Kernel Tuning with Reinforcement Learning**（KDD 2026 V.2·DOI 10.1145/3770855.3817987）——标题明确 "kernel tuning"（内核参数调优）而非"内核改造"：RL agent 调的是 sysctl/调度器参数族。与 laos 的关系不变：laos 是用户态薄内核、立场是治理延伸而非自动改参（审计红线：参数变更必须可追溯），Task 3 的 ○（与 SchedCP 同裁决）维持。

两篇维持 Task 3 原裁决，无需改表；若后续补到摘要再复核。

---

## 诚实声明

1. **检索为标题级为主**：spatial-privacy 114 行中仅 38 行有摘要；§一 各子题的 crossref 会议文件（KDD/IJCAI/AAAI 部分、GlobalSIP、WASPAA、TASLP 新文）多无摘要，正则实际命中的多为标题。凡按无摘要篇目做的判断（如 2.2 各篇角色、1.2#8）均为标题+领域常识级，未编造摘要内容。
2. **子题计数是工作集内口径**：四子题计数（4/27/24/44）是 **934 行强命中工作集**内的标题+摘要正则命中数，不是该文献领域的全集规模（未进强命中词表的文件不参与）；"语音 KWS 有效≈23""diarization 有效 43"等净数已在各节内标注撞车篇。
3. **归桶口径**：§二 四小类按 Task 2 主题词表六词根归桶而非语义精读；beamform 桶 105 中 17 篇 GlobalSIP 无线/雷达波束成形与声学仅数学同源，已在节内单列净数 88。
4. **重叠未去重**：query_corpus 不做跨子题去重，VAP 两篇同时落在 1.1/1.3，Proactive Hearing Assistants 同时落在 1.1/2.1，均在文中点名而非隐藏。

---

## 附：复核命令

```bash
# §一 四子题计数（stderr 的 hit 数应分别为 4/27/24/44）
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --strong-only --limit 0 --grep "barge|interrupt|full-duplex|turn-taking"
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --strong-only --limit 0 --grep "wake[- ]?word|keyword spotting"
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --strong-only --limit 0 --grep "voice activity|endpoint|end-point"
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --strong-only --limit 0 --grep "diariz|speaker separation"
# §二 全量 114 行 + 摘要可得性（应得 114 / 38）
C:/Users/yaoyue/miniconda3/python.exe scripts/query_corpus.py --topic spatial-privacy --strong-only --limit 0 --json > var/t4_spatial.json
C:/Users/yaoyue/miniconda3/python.exe -c "import json;rows=[json.loads(l) for l in open('var/t4_spatial.json',encoding='utf-8') if l.strip()];print(len(rows),sum(1 for r in rows if (r.get('abstract') or '').strip()))"
```
