# 全语音信号模型前沿地图：SER/AED/AGC 之外的六大领域（2024–2026 逐篇文献跟踪）

> 调研时间：2026-09-12 ｜ 姊妹篇：[SER](2026-09-11-ser-model-landscape.md) ｜ [AED/AGC](2026-09-11-aed-agc-model-landscape.md) ｜ [全天候录音业界](always-on-recording/2026-09-landscape.md)
> 由四路文献调研子代理执行（说话人 / 前端触发 / 编解码与语音生成 / 副语言学与健康声学），共 51 篇逐篇条目。
> 目标：找出**全部**能用上的语音信号专用模型，支撑全天候录音的后续应用与"更贴近用户"的功能。
> 记法：✅ 官方源已查证 ｜ 🔶 未在官方源逐字核实。

---

## 1. 一句话结论

1. **"去声纹化"的个性化已经成熟**：流式说话人分离（Streaming Sortformer）用"到达顺序"当身份、
   personal VAD（USEF-TP）用帧级注意力替代预注册声纹嵌入——**"谁的日记"可以不建长期声纹库就实现**，
   与中国法域（声纹=敏感个人信息需单独同意）和 EU AI Act 完全对齐。
2. **神经编解码把即焚前的留存成本降了两个数量级**：Mimi 1.1kbps ≈ **0.5MB/小时**（PCM 是 115MB/h、
   Opus 16k 是 7.2MB/h），且 codec token 直接就是语音 LLM 的输入表示——**留存格式与模型表示可以合一**。
3. **贴近用户功能里落地成本最低的是发音评估**：GOPT + speechocean762 全开源基线现成；
   最高风险的是健康推断（认知筛查基线仅 59% UAR、抑郁 71% 敏感度）与情绪类功能在职场/教育场景
   已被 EU AI Act（2025-02 起）直接禁止——**功能命名与定位必须按"用户自主健康监测/纵向差分"设计**。

---

## 2. 说话人模型（diarization / 嵌入 / 目标说话人提取 / 匿名化）——14 篇

### 2.1 逐篇条目

- **Sortformer**（Taejin Park 等，NVIDIA；ICML 2025）[arXiv:2409.06656](https://arxiv.org/abs/2409.06656)
  "Sort Loss" 按说话人到达顺序解决排列问题，单编码器同时出"谁在何时说"；随 NeMo 开源。
  关键数字：第三方 LibriConvo 基准 DER **11.1%**（pyannote 约 24.4%，[arXiv:2510.23320](https://arxiv.org/abs/2510.23320)）。
  → laos：日记骨架；4 说话人上限假设。
- **Streaming Sortformer**（Medennikov 等，NVIDIA；Interspeech 2025）[arXiv:2507.18446](https://arxiv.org/abs/2507.18446)
  Arrival-Order Speaker Cache（AOSC）实现低延迟流式分离；**说话人身份=到达顺序，天然不建长期声纹库**。
  → laos：目前最对口的"全天候流式 who-spoke-when"方案。🔶 具体 DER 需读全文。
- **在线分离综述 + 延迟基准**（Aperdannier 等，2024）[arXiv:2406.14464](https://arxiv.org/abs/2406.14464)、[arXiv:2407.04293](https://arxiv.org/abs/2407.04293)、DIART 端侧优化 [arXiv:2408.02341](https://arxiv.org/abs/2408.02341)
  实测 DIART+pyannote 延迟最低；**量化+层融合可降延迟不掉精度，蒸馏反而掉点**。→ 端侧最稳组合。
- **分离引导的在线分离**（Gruttadauria 等；ICASSP 2024）[arXiv:2402.00067](https://arxiv.org/abs/2402.00067)：AMI headset mix 全条件 SOTA（含重叠）。→ 重叠段是日记漏录主因，但算力偏重。
- **O-EENC-SD**（2025）[arXiv:2512.15229](https://arxiv.org/abs/2512.15229)：EEND 系在线化，双人电话场景可端侧跑。
- **Continuous TSE**（He Zhao 等，2024）[arXiv:2401.15993](https://arxiv.org/abs/2401.15993)：TSVAD 时间戳 + TSE 级联，"只提取主人"路线；注册音可**会话内临时采集，不必长期存声纹**。
- **USEF-TP：Universal Speaker Embedding Free TSE + Personal VAD**（Zeng/Li 等；Computer Speech & Language 2025）[arXiv:2501.03612](https://arxiv.org/abs/2501.03612)
  帧级 cross-attention 替代说话人嵌入，联合 TSE+personal VAD。→ **最贴合 laos 隐私立场：个人 VAD 不依赖长期声纹库**。
- **CAM++**（阿里/3D-Speaker；Interspeech 2023）[arXiv:2303.00332](https://arxiv.org/abs/2303.00332)：精度超 ECAPA-TDNN 且更快，CN-Celeb 中文强。→ 若必须做会话级嵌入：用它且只在内存保留。
- **3D-Speaker-Toolkit**（阿里，2024）[arXiv:2403.19971](https://arxiv.org/abs/2403.19971)：中文嵌入/分离 pipeline 现成来源。
- **VoicePrivacy 2024**（Tomashenko 等；Interspeech 2024 workshop）[arXiv:2404.02677](https://arxiv.org/abs/2404.02677)
  匿名化协议：隐藏身份同时保留语言内容与**情感状态**。→ 日记对外分享先匿名化的标准协议。
- **Local Information Disclosure**（Šterns 等，2026）[arXiv:2607.06259](https://arxiv.org/abs/2607.06259)：顶级匿名化系统 EER 近满分仍泄露 ≤1 bit/trial。→ **匿名化≠零泄露**。
- **StreamVoiceAnon+**（Kuzmin 等，2026）[arXiv:2603.06079](https://arxiv.org/abs/2603.06079)：首批**流式**匿名化，帧级蒸馏保情感（攻击者 EER 49.0%，情感 UAR +24%）。→ "本地原声+外发匿名版"双轨制的现成组件。
- **全双工对话模型的隐私泄露**（Kuzmin 等，2026）[arXiv:2603.08179](https://arxiv.org/abs/2603.08179)：Moshi/SALM-Duplex 隐藏状态会泄露说话人身份（EER 11.2%→41.0% 可防御）。→ **中间表征本身即敏感信息**。
- **MLC-SLM 挑战赛**（Interspeech 2025 workshop）[arXiv:2509.13785](https://arxiv.org/abs/2509.13785)：11 语言 1604h 真实会话 ASR+分离双任务，78 队；BUT 队 DiCoW/DiariZen 超 pyannote 基线。→ 中文混合语环境有可复现基线。

### 2.2 趋势与未解

趋势：① 分离从"嵌入+聚类"走向单模型流式端到端，端侧瓶颈从精度转向延迟工程（量化+层融合）；② 个性化从"预注册声纹"转向"会话内临时锚定"（连续 TSE/帧级 attention/文本提示）——与法域合规同向；③ 隐私评估从 EER 走向泄露度量，匿名化从离线走向流式。

未解：① **跨天"同一人=同一日记主人"如何在不建长期声纹库下实现**（会话密钥+即时比对后丢弃？）无公开方案；② 匿名化-个性化帕累托前沿在端侧算力约束下无测量；③ 重叠语音的说话人计数在家庭嘈杂场景无基准。

---

## 3. 前端触发（VAD / 关键词唤醒 / 声源定位）——12 篇

### 3.1 逐篇条目

- **Silero VAD v5/v6**（开源工程，2024–2026）[GitHub](https://github.com/snakers4/silero-vad)
  模型 2MB（~100K 参数）；30ms 块 <1ms 单线程 CPU，ONNX 再快 4–5×；v6 真实噪声错误率 -16%；v6.2.1 起 ONNX 可选。
  → laos 自研 StreamingVAD 的升级/对照基线（固定窗+因果小 GRU 结构可借鉴）。
- **FSMN-Monophone VAD**（阿里达摩院）[HF](https://huggingface.co/funasr/fsmn-vad)：流式毫秒级起止点；纯 Python 复刻可行。→ 中文场景第二触发器。
- **FusionVAD**（Interspeech 2025）[arXiv:2506.01365](https://arxiv.org/abs/2506.01365)：MFCC+SSL 特征**简单相加**即超交叉注意力（多数据集平均超 pyannote 2.04%）。→ 自研能量 VAD 加一路 MFCC 即可提升噪声鲁棒性。
- **Transformer VAD（跨语言 SSL）**（Interspeech 2024）[ISCA](https://www.isca-archive.org/interspeech_2024/karan24_interspeech.pdf) 🔶：wav2vec2 特征最鲁棒。
- **Noise-Robust Target-Speaker VAD**（Aalborg+Oticon；投 TASLP 2025）[arXiv:2501.03184](https://arxiv.org/abs/2501.03184)：因果 DN-APC 预训练 + FiLM 说话人条件化，噪声下 +2%。→ TS-VAD="声纹即唤醒"，可做触发后授权校验。
- **Porcupine v4**（Picovoice，2025-12）[GitHub](https://github.com/Picovoice/porcupine)：闭源商用；参考"每词一个微型二分类器"架构与私有词训练产品形态。
- **openWakeWord**（MIT 开源）[GitHub](https://github.com/dscripka/openWakeWord)：Home Assistant 默认本地唤醒；合成数据+谱特征+双向 GRU 管线是纯 Python 复刻私有词 KWS 的最短路径。
- **LLM-Synth4KWS**（Interspeech 2025）[arXiv:2505.22995](https://arxiv.org/abs/2505.22995)
  LLM 生成易混词组+TTS 合成做对比学习，零人工标注；AUC +3.7%、易混词 c-AUC +11.3%。→ **用户给 laos 起私有唤醒词**时压误唤醒的合成管线。
- **EdgeSpot**（ICASSP 2026）[arXiv:2601.16316](https://arxiv.org/abs/2601.16316)
  BC-ResNet+可训练 PCEN 前端+时间自注意+SSL 蒸馏的 **10-shot KWS：29.4M MACs / 128K 参数**，10-shot@1%FAR 73.7%→82.0%。→ **PCEN 前端值得移植进纯 Python VAD**（逐通道能量归一化，几十行）。
- **WakeWords+SpeakerRecognition 案例研究**（2024）[arXiv:2407.18985](https://arxiv.org/abs/2407.18985) 🔶：嵌入式"唤醒词先触发→声纹后授权"两段式。→ laos 三级级联（能量 VAD→关键词→声纹）把最贵的校验放最后。
- **双耳两阶段 CNN DOA**（EURASIP JASMP 2025）[论文](https://link.springer.com/article/10.1186/s13636-025-00392-8) 🔶：双麦互功率谱相位做多说话人 DOA。→ 直接对上 laos 双麦/耳戴形态。
- **34.7 µW KWS 专用 IC**（MDPI Electronics 2023）[论文](https://www.mdpi.com/2079-9292/12/15/3287)：待机 1.65µW / KWS 平均 34.7µW。→ ADSP 触发器功耗预算标尺：纯能量 VAD 应压在个位数 µW。

### 3.2 趋势与未解

趋势：① VAD 分层化——常驻第一级亚毫秒小模型，精度层"手工特征+少量神经层"（加法优于注意力）；② 私有唤醒词零样本化（enrollment + 10-shot + LLM/TTS 合成易混词，用户说出即可上线）；③ 多因素联合触发（关键词×声纹×方位）与 µW 级硬件化。

未解：① SSL 级 VAD 无 <100µW ADSP 端实测功耗数据（可跑性仍是推断）；② 双麦 DOA 缺"阵列随头转动"公开基准；③ few-shot 唤醒论文报 1% FAR 固定语料指标，缺真实家庭 24/7 的每小时误唤醒（FA/h）报告。

---

## 4. 神经编解码与端侧语音生成（留存 + 回复）——13 篇

### 4.1 编解码（录音留存侧）

- **Moshi/Mimi**（Kyutai；2024）[arXiv:2410.00037](https://arxiv.org/abs/2410.00037)、[GitHub](https://github.com/kyutai-labs/moshi)
  Mimi：12.5Hz、语义-声学 split RVQ、总码率 **1.1kbps ≈ 0.5MB/小时**（PCM 115MB/h 的 1/233）；纯因果卷积流式 80ms。→ **6h 即焚前的留存理想档**；codec token 即对话模型输入（留存格式=模型表示）。
- **LFSC**（NVIDIA，2024）[arXiv:2409.12117](https://arxiv.org/abs/2409.12117)：FSQ+WavLM 语义蒸馏，1.89kbps/21.5fps，加速 LLM-TTS 3×，[权重开放](https://huggingface.co/nvidia/low-frame-rate-speech-codec-22khz)。
- **SNAC**（NeurIPS 2024 WS；MIT）[arXiv:2410.14411](https://arxiv.org/abs/2410.14411)、[GitHub](https://github.com/hubertsiuzdak/snac)：24kHz **0.98kbps / 19.8M 参数**，多尺度粗 token ~10Hz。→ 零依赖 Python 包、参数最小，最贴 laos。
- **FunCodec**（阿里；ICASSP 2024）[arXiv:2309.07405](https://arxiv.org/abs/2309.07405)：频域 FreqCodec 降算力，训练配方最完整。
- **DAC**（Descript；NeurIPS 2023）[arXiv:2306.06546](https://arxiv.org/abs/2306.06546)：44.1kHz 8kbps 通用高保真。→ "重要片段"高保真档。
- **Opus**（RFC 6716）[RFC](https://www.rfc-editor.org/info/rfc6716/)：16kbps ≈ 7.2MB/h 宽带近透明。→ 零依赖基线；神经 codec 要在 1–2kbps 打平它才值得引入。

### 4.2 语音生成（回复侧）

- **CosyVoice 2**（阿里；2024）[arXiv:2412.10117](https://arxiv.org/abs/2412.10117)：流式 TTS 首包 **~150ms**，零样本克隆，中英双语。→ 中文语音回复首选，但需蒸馏/量化上端侧。
- **F5-TTS**（上海交大等，2024）[arXiv:2410.06885](https://arxiv.org/abs/2410.06885)：非自回归 flow matching，RTF 0.15，中英混读。
- **Kokoro-82M**（hexgrad，2025，Apache-2.0）[HF](https://huggingface.co/hexgrad/Kokoro-82M)
  **82M 参数**仅解码器 TTS，质量比肩大模型（TTS Arena 靠前）；$1000 训练成本；固定音色库（不支持克隆），中文需 v1.1-zh 🔶。→ **端侧语音回复目前性价比之王**。
- **Spark-TTS**（西工大等，2025）[arXiv:2503.01710](https://arxiv.org/abs/2503.01710)：BiCodec 把"用户音色"压成**定长全局 token**——个性化音色的端侧友好表示。
- **MegaTTS 3**（字节/浙大，2025）[arXiv:2502.18924](https://arxiv.org/abs/2502.18924)：8 步采样合成分钟级语音；0.15B 🔶；非流式对对话偏慢。

### 4.3 信任基建（水印/深伪）

- **AudioSeal**（Meta；ICML 2024）[arXiv:2401.17264](https://arxiv.org/abs/2401.17264)：首个样本级局部化语音水印，检测单次前向快 2 个数量级。→ 给 laos TTS 输出加水印的现成件。
- **深伪检测新基准**（2025）[arXiv:2508.10949](https://arxiv.org/abs/2508.10949)、[VoiceWukong（USENIX Sec 2025）](https://www.usenix.org/system/files/usenixsecurity25-yan-ziwei.pdf)：22 个检测器对新攻击平均**掉 43%**。→ 依赖检测不可靠，水印+本地白名单更稳。

### 4.4 趋势与未解

趋势：① 低帧率语义-声学分离 codec 成语音 LLM 标配，留存格式与模型表示合一；② TTS 两极分化——做减法（Kokoro 82M 固定音色）vs LLM 骨干流式（CosyVoice 2 150ms+克隆），**"轻量"与"个性化克隆"未在同一模型兼得**（克隆系最小 0.15B）；③ 克隆外溢催生水印基建，共识从"事后检测"转向"生成端主动水印"。

未解：① 1–2kbps 神经 codec 在非语音内容（音乐/环境声）质量仍明显差于 DAC 8kbps——全天候混音场景如何自适应选档无系统结论；② 客观指标与主观感知脱节（Mimi 纯对抗训练 MUSHRA +22 而 VisQOL 反降），留存"够用线"缺自动化指标；③ 流式全双工与高保真克隆仍是两套系统。

---

## 5. 副语言学与健康声学（贴近用户的功能面）——12 篇

### 5.1 发音评估（语言学习——落地成本最低）

- **Multi-task Pretraining for L2 Pronunciation Assessment**（APSIPA-ASC 2025）[arXiv:2509.16876](https://arxiv.org/abs/2509.16876)：音素级编码器多任务预训练，APA+口语水平联合输出，可解释。
- **GOPT**（MIT；ICASSP 2022）[arXiv:2205.03432](https://arxiv.org/abs/2205.03432) + **speechocean762**：四维（准确/流利/完整/韵律）多粒度评分的开源基线。
- **ACL 2024 预训练模型发音评估**（[ACL](https://aclanthology.org/2024.acl-long.95/)）："预训练底座+轻量评分头"成立，laos 不必自采标注。
→ **laos 语言学习功能的直接对标：GOPT + speechocean762，落地成本最低**。

### 5.2 口吃/流利度

- **AS-70 普通话口吃数据集**（StammerTalk；Interspeech 2024）[arXiv:2406.07256](https://arxiv.org/abs/2406.07256)、[HF](https://huggingface.co/datasets/AImpower/MandarinStutteredSpeech)：~70 名说话者，ASR+口吃事件双任务；社区共创（口吃者自采）是合规样本范式。→ 中文口吃/流利度唯一公开数据源。
- **Whisper 表征做口吃检测**（Interspeech 2024）[ISCA](https://www.isca-archive.org/interspeech_2024/changawala24_interspeech.pdf)：SEP-28k（28k 段/5 类事件）上系统分析层选择与池化。→ **同一 ASR 底座同时做转写+副语言检测**。
- **wav2vec 2.0 自注意力权重做口吃检测**（Interspeech 2025）[ISCA](https://www.isca-archive.org/interspeech_2025/miyahara25_interspeech.pdf)：冻结底座+注意力统计，省算力。→ 端侧友好。

### 5.3 咳嗽/呼吸/看护

- **两级咳嗽分类**（Han 等，2025）[PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12218819/)：检测+疾病分类，咳嗽检测准确率 0.9883（自采数据 🔶 泛化存疑）。→ 老人看护咳嗽事件架构模板。
- **呼吸音筛查哮喘/COPD**（Sci Reports 2026）[Nature](https://www.nature.com/articles/s41598-026-54803-7)：总体 90.3%；F1 健康 0.945/哮喘 0.915/**COPD 0.842**。→ 只能到筛查级，不可出诊断话术。
- **老人居家声场景实时识别**（MDPI Sensors 2025）[论文](https://www.mdpi.com/1424-8220/25/6/1746)：边缘计算端侧部署验证。→ 与 laos 跌倒/异常声方向一致。

### 5.4 认知衰退（红线最清晰的一档）

- **TAUKADIAL Challenge**（Interspeech 2024）[ISCA](https://www.isca-archive.org/interspeech_2024/barreraaltuna24_interspeech.pdf)、[赛题页](https://taukadial-luzs-69e3bf4b9878b99a6f03aea43776344580b77b9fe54725f4.gitlab.io/)
  中英双语 MCI 诊断+MMSE 回归；**官方基线仅 59.18% UAR**；语音时长与停顿是最强跨语言特征。→ **MCI 语音检测绝对性能仍低（~60%），laos 只能做纵向差分提示**。
- **AD 语音检测综述**（AI Review 2024）[Springer](https://link.springer.com/article/10.1007/s10462-024-10961-6)：多语言、跨库泛化、可解释性三大短板；停顿/语速类特征优先。→ laos 认知功能边界依据。

### 5.5 年龄/性别/压力

- **声学年龄性别分类**（Reza；ACM 2024）[ACM](https://dl.acm.org/doi/full/10.1145/3723178.3723219)：年龄 88.1%/性别 96.9%（粗分箱）。→ 画像冷启动可用；注意 AI Act 下可能构成"生物识别分类"。
- **压力的时间进程建模**（2025）[arXiv:2510.08586](https://arxiv.org/abs/2510.08586)、[ISCA](https://www.isca-archive.org/interspeech_2025/xiong25_interspeech.pdf)：基础模型微调+时序建模跨语料 +5.4–13.4%（StressID +18%）。→ 压力/疲劳**只做纵向差分**有实证支撑。

### 5.6 合规（执法期已到）

- **EU AI Act 情绪识别禁令**（FPF 解读）[FPF](https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/)：2025-02-02 起禁止职场/教育场景用生物识别数据推断情绪（医疗/安全窄豁免；罚款至全球营业额 7%）。
- **中国：声纹=敏感个人信息**（PIPL 28/29 条 + GB/T 41807；2025-06 新国标）[China Briefing](https://www.china-briefing.com/news/sensitive-personal-data-in-china-guidelines/)：需单独同意，禁止诱导/欺骗获取。→ **laos 双市场红线：健康推断须显式健康目的+单独同意；情绪类功能在职场/教育直接禁用**。

### 5.7 趋势与未解

趋势：① Whisper/wav2vec2 表征成口吃/认知/压力统一特征源（研究方向=选层与池化）；② 方法学从横截面分类转向纵向/回归（TAUKADIAL 做 MMSE 回归、压力做时间进程）——**与 laos"纵向差分"结论同向且有定量支持**；③ 合规从讨论期进入执法期。

未解：① 实验室咳嗽/呼吸模型（90%+）在真实家庭远场混响下性能未知；② 说话人内纵向认知衰退追踪无公开基准（"每人自己当基线"无法离线验证）；③ 语音推导的健康推断在 GDPR/AI Act 下是否算"生物识别数据"仍有争议。

---

## 6. 对 laos 的功能映射（按落地优先级）

| 优先级 | 功能 | 支撑模型（本篇 §） | 落地档位 | 为什么现在做 |
|---|---|---|---|---|
| P0 | **录音留存压缩**（漏斗②升级） | Mimi 1.1kbps / SNAC 0.98kbps（§4.1） | PC 批处理 + 端侧实验 | 0.5MB/h vs PCM 115MB/h；token 直接可喂语音 LLM；SNAC 零依赖 Python |
| P0 | **发音评估**（语言学习） | GOPT + speechocean762（§5.1） | PC GPU（ drv_ear 同环境） | 全开源基线现成，always-on 调研已验证用途，落地成本最低 |
| P1 | **私有唤醒词**（"叫 laos 的名字"） | openWakeWord 管线 + LLM-Synth4KWS 合成 + EdgeSpot PCEN 前端（§3） | 桌面端先行，ADSP 后置 | "用户说出即可上线"是贴近用户的标志性功能；PCEN 几十行可进纯 Python VAD |
| P1 | **"谁的日记"说话人标注** | Streaming Sortformer 到达顺序 / USEF-TP personal VAD（§2） | PC 批处理 | 到达顺序=身份，不建长期声纹库，法域合规；跨天身份问题列为开放课题（会话密钥方案） |
| P2 | **TTS 语音回复** | Kokoro-82M（中文 v1.1-zh）/ CosyVoice 2（§4.2） | PC GPU | 端侧性价比之王；回复加水印（AudioSeal） |
| P2 | **咳嗽/异常声健康事件** | 两级咳嗽分类架构（§5.3） | ADSP 白名单事件（与 AED 篇 §6 合并） | 筛查级可用；红线=只提示不诊断 |
| P3 | **认知/压力纵向差分** | TAUKADIAL 口径 + 压力时序建模（§5.4/5.5） | 远期 | 绝对性能不足（~60%），只做"与自己比"的提示 |
| 不做 | 多模态/视频类；职场/教育场景情绪识别 | — | — | EU AI Act 禁令 + laos 无摄像头红线 |

## 7. 可选落地项（如需执行另行确认）

1. **`laos/audiostore.py` 神经编解码留存档**：SNAC 0.98kbps 打包为可选依赖；`rec_gc` 前先转 codec token 再落盘（0.5MB/h×6h≈3MB/天）
2. **`drv_ear` 发音评估通道**：GOPT+speechocean762 基线接入 .venv-audio 环境，输出四维分数入记忆（kind="pronunciation"）
3. **`laos/vad.py` 移植 PCEN 前端**：几十行纯 Python，噪声鲁棒性对齐 FusionVAD 结论
4. **私有唤醒词训练脚本**：openWakeWord 式合成管线 + LLM-Synth4KWS 易混词增广（离线训练）
5. **README 合规红线一节**：AI Act 职场/教育情绪禁令、PIPL 声纹单独同意、健康功能定位话术

## 8. 参考来源

全部链接已内嵌正文；四路子代理检索记录中的关键未命中已如实标注（DCASE 2026 未索引、ECAMA-PATN 未证实、ComParE 2024/2025 未办、ICASSP 2025 AEC Challenge 官方报告缺位、MER2025 冠军汇总缺位）——这些"查不到"本身也是跟踪结论的一部分。
