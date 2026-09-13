# ICASSP 2022-2026 普查覆盖率（Crossref 枚举，自动生成）

| 年份 | 抓到唯一论文 | 官方录用 | 覆盖率 | DOI/front-matter 复核 | 状态 |
|---|---|---|---|---|---|
| 2022 | 1863 | 1785 | 104.4% | 0 异常 | OK |
| 2023 | 2720 | 2765 | 98.4% | 0 异常 | OK |
| 2024 | 2699 | 2812 | 96.0% | 0 异常 | OK |
| 2025 | 3163 | 未公布 | 未知(官方录用数未公布) | 0 异常 | OK |
| 2026 | 3840 | 未公布 | 未知(官方录用数未公布) | 0 异常 | OK |

> 枚举方式：`query.bibliographic=ICASSP <YEAR> ...` + `filter=type:proceedings-article` + `offset` 分页，DOI 前缀正则 `10\.1109/icassp\d+\.<YEAR>\.` 精确过滤。
> 实测：单靠 base query 即可接近穷尽一届，20 个主题分片对 ICASSP 增量极小。

## 覆盖率 >100% 的说明

- **2022 年抓到 1863 条，多于官方录用数 1785（104.4%）**。DOI 前缀正则保证每条都是 `10.1109/icassp<id>.2022.*`，故不存在他源污染。差额来自：official 录用数为会议公布的「accepted papers」口径，而 IEEE Xplore proceedings 实际还含增补/后补条目、special session 增补等。以 **抓到数为准，覆盖率按超过 100% 如实标注**。

> 覆盖率 <60% 的年份在最终报告中必须显著声明为「部分枚举」，不得称「全量」。

## 真实性抽查样本（random.seed=7，各年 10 条）

### 2022（共 1863 条）

| DOI | 标题 |
|---|---|
| `10.1109/icassp43922.2022.9746706` | Training Strategies for Improved Lip-Reading |
| `10.1109/icassp43922.2022.9746322` | Coupled Feature Learning Via Structured Convolutional Sparse Coding for Multimodal Image F |
| `10.1109/icassp43922.2022.9746852` | Injecting Text and Cross-Lingual Supervision in Few-Shot Learning from Self-Supervised Mod |
| `10.1109/icassp43922.2022.9747385` | Sensors to Sign Language: A Natural Approach to Equitable Communication |
| `10.1109/icassp43922.2022.9746104` | Multi-Task RNN-T with Semantic Decoder for Streamable Spoken Language Understanding |
| `10.1109/icassp43922.2022.9746156` | Few-Shot Learning with Improved Local Representations via Bias Rectify Module |
| `10.1109/icassp43922.2022.9747734` | Discrete Multi-Kernel K-Means with Diverse and Optimal Kernel Learning |
| `10.1109/icassp43922.2022.9747148` | Dynamic Multi-Scale Loss Balance for Object Detection |
| `10.1109/icassp43922.2022.9746200` | Enhancing Class Understanding Via Prompt-Tuning For Zero-Shot Text Classification |
| `10.1109/icassp43922.2022.9746791` | Cross-Domain Few-Shot Learning for Rare-Disease Skin Lesion Segmentation |

### 2023（共 2720 条）

| DOI | 标题 |
|---|---|
| `10.1109/icassp49357.2023.10095881` | An Empirical Study on Speech Restoration Guided by Self-Supervised Speech Representation |
| `10.1109/icassp49357.2023.10095169` | Mutual Information Based Reweighting for Precipitation Nowcasting |
| `10.1109/icassp49357.2023.10096173` | Ultimate Negative Sampling for Contrastive Learning |
| `10.1109/icassp49357.2023.10097234` | MarginNCE: Robust Sound Localization with a Negative Margin |
| `10.1109/icassp49357.2023.10094748` | Detail-Aware Uncalibrated Photometric Stereo |
| `10.1109/icassp49357.2023.10094847` | Non-Convex Approaches for Low-Rank Tensor Completion under Tubal Sampling |
| `10.1109/icassp49357.2023.10096750` | ST360IQ: No-Reference Omnidirectional Image Quality Assessment With Spherical Vision Trans |
| `10.1109/icassp49357.2023.10094936` | Meta Learning with Adaptive Loss Weight for Low-Resource Speech Recognition |
| `10.1109/icassp49357.2023.10096053` | Meeting Action Item Detection with Regularized Context Modeling |
| `10.1109/icassp49357.2023.10096943` | A Wavelet Scattering Approach for Load Identification with Limited Amount of Training Data |

### 2024（共 2699 条）

| DOI | 标题 |
|---|---|
| `10.1109/icassp48485.2024.10447138` | Multi-Objective Progressive Clustering for Semi-Supervised Domain Adaptation in Speaker Ve |
| `10.1109/icassp48485.2024.10446412` | Exact Classification of NMR Spectra from NMR Signals |
| `10.1109/icassp48485.2024.10447431` | Adaptive Multi-View Joint Contrastive Learning on Graphs |
| `10.1109/icassp48485.2024.10448482` | Near-Field Localization with 1-bit Quantized Hybrid A/D Reception |
| `10.1109/icassp48485.2024.10445989` | Can We Trust Explainable AI Methods on ASR? An Evaluation on Phoneme Recognition |
| `10.1109/icassp48485.2024.10446089` | Efficient Quantum Recurrent Reinforcement Learning Via Quantum Reservoir Computing |
| `10.1109/icassp48485.2024.10448009` | MEPE: A Minimalist Ensemble Policy Evaluation Operator for Deep Reinforcement Learning |
| `10.1109/icassp48485.2024.10446179` | Radio Slam with Hybrid Sensing for Mixed Reflection Type Environments |
| `10.1109/icassp48485.2024.10447311` | A 3D Virtual Try-On Method with Global-Local Alignment and Diffusion Model |
| `10.1109/icassp48485.2024.10448202` | Optimal ANN-SNN Conversion with Group Neurons |

### 2025（共 3163 条）

| DOI | 标题 |
|---|---|
| `10.1109/icassp49660.2025.10888954` | TheSHY-3D: Texture and Structure HarmonY for Multi-View 3D Object Detection |
| `10.1109/icassp49660.2025.10888218` | Learning Two-factor Representation for Magnetic Resonance Image Super-resolution |
| `10.1109/icassp49660.2025.10889258` | SlimSpeech: Lightweight and Efficient Text-to-Speech with Slim Rectified Flow |
| `10.1109/icassp49660.2025.10890362` | Raw Audio Deep Learning Filter Banks for Acoustic Scene Classification |
| `10.1109/icassp49660.2025.10887765` | An End-to-End Graph-Guided Spatiotemporal Model for Adaptive Frame-Level Facial Affect Ana |
| `10.1109/icassp49660.2025.10887869` | Gen-A: Generalizing Ambisonics Neural Encoding to Unseen Microphone Arrays |
| `10.1109/icassp49660.2025.10889868` | An Explainable Probabilistic Attribute Embedding Approach for Spoofed Speech Characterizat |
| `10.1109/icassp49660.2025.10887976` | Camouflaged Object Detection via Neural Architecture Search |
| `10.1109/icassp49660.2025.10889136` | Multiple Sclerosis Detection with Reinforcement Learning and Differential Evolution |
| `10.1109/icassp49660.2025.10890069` | Investigating F0 Estimation in Speech Synthesis from Real-time MRI Articulatory Data |

### 2026（共 3840 条）

| DOI | 标题 |
|---|---|
| `10.1109/icassp55912.2026.11462178` | Semantic-Aware Address Sanitization with Metric Differential Privacy |
| `10.1109/icassp55912.2026.11461319` | Hierarchical Tokenization of Multimodal Music Data for Generative Music Retrieval |
| `10.1109/icassp55912.2026.11462532` | Multi-Stage Music Source Restoration with BandSplit-RoFormer Separation and HiFi++ GAN |
| `10.1109/icassp55912.2026.11463775` | LipsAM: Lipschitz-Continuous Amplitude Modifier for Audio Signal Processing and its Applic |
| `10.1109/icassp55912.2026.11460617` | Efficient and Scalable Tobit Gaussian Process Regression for Modeling Air Quality Data |
| `10.1109/icassp55912.2026.11460744` | Bridging the Semantic Gap: Cross-Attentive Fusion for Joint Acoustic-Semantic Speech Quali |
| `10.1109/icassp55912.2026.11464603` | Achieving Pareto Optimality in Games via Single-Bit Feedback |
| `10.1109/icassp55912.2026.11463212` | Semanticshield: LLM-Powered Audits Expose Shilling Attacks in Recommender Systems |
| `10.1109/icassp55912.2026.11460859` | EBCF: Strict Error-Bounded Compression of Numerical Climate Data with Discrete Normalizing |
| `10.1109/icassp55912.2026.11462388` | Lightweight Image Super-Resolution via Efficient Shift Convolution and Edge-Enhanced Atten |
