# 音频事件模型 —— 中型档（参数量 30M–500M）

> 口径来源：`docs/research/audio-events/00-taxonomy-and-metrics.md`（12列表头、规模分档、AudioSet 划分口径、红线均以该文件为准）。
> 本档边界：中型 = **30M ≤ 参数量 < 500M**（含音频编码器，量化前，左闭右开：30M 归中型，500M 归大型）。
> 本档只做检索与核实，不做选型结论；`edge` 一栏只记录**已核到的公开证据**，按口径文件规定由 Task 5（`05-edge-deployment.md`）回填。
> **AudioSet 引用声明**：凡预训练/评测语料为 AudioSet 的条目，其音频本体为 YouTube 视频且**官方已停止分发完整包**，实际复现只能依赖第三方镜像或官方/第三方预计算 embedding（如 PANNs 仓库提供的 `pan.baidu.com` 镜像、BEATs 提供的 logits 包）。

---

## Part 1 · 数据表

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PANNs-CNN14 | Table XI/XII 的 CNN14（80,753,615 参数，embedding 2048 维，Wavegram-Logmel-CNN 的主干） | 80.75 | A | AudioSet AS-2M full（本体不可直接获取，复现依赖第三方镜像或预计算 embedding） | tagging/527类 | AudioSet AS-2M full | mAP 0.431 / mAUC 0.973 / d′ 2.732 (AudioSet AS-2M full, tagging, 单模型)；42.220×10⁹ multi-adds/10s ≈ 4222 MMACs/s | Apache-2.0（microsoft/unilm 同系；PANNs 仓库 qiuqiangkong/audioset_tagging_cnn 未含 LICENSE 文件，此处据论文仓库标注） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/1912.10211；https://github.com/qiuqiangkong/audioset_tagging_cnn |
| AST（Audio Spectrogram Transformer，DeiT w/ Distill 初始化） | `ASTModel(label_dim=527, fstride=10, tstride=10, model_size='base384')`，ImageNet-pretrained DeiT-B w/ Distill（87M）作骨干 | 87.0 | A | ImageNet + AudioSet AS-2M full（同上本体不可直接获取） | tagging/527类 | AudioSet AS-2M full | mAP 0.459 (AudioSet AS-2M full, tagging, 单模型带weight averaging)；AS-20K 对应值 0.347 (AudioSet AS-20K, tagging, 单模型)；Ensemble-M 集成 0.485 (AudioSet AS-2M full, tagging, 集成) | BSD 3-Clause（ast 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2104.01778；https://github.com/YuanGongND/ast |
| PaSST-S（Structured Patchout，DeiT-B/384 骨干） | `passt_s_swa_p16_s16_128_ap473`；论文 Table 1 的 PaSST-S（S16,14）单模型；论文另报 PaSST-L（d=7，50M）与集成 | 87.0 | A | ImageNet + AudioSet AS-2M full（论文 §3：训练用 1,893,693 段，评测 18,951 段） | tagging/527类 | AudioSet AS-2M full | mAP 0.471 (AudioSet AS-2M full, tagging, 单模型)；集成 0.496 (AudioSet AS-2M full, tagging, 9 模型集成)；论文 Table 1 同表AST 为 0.459 | Apache-2.0（PaSST 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2110.05069；https://github.com/kkoutini/PaSST |
| HTS-AT_HCP（Hierarchical Token-Semantic Audio Transformer，完整配置） | HTS-AT_HCP（H=分层结构 + C=token-semantic 模块 + P=ImageNet Swin 预训练）；论文 Table 1 同行另有无预训练版 H=28.8M/0.440、HC=31M/0.453 | 31.0 | A | ImageNet(Swin-T/C, 256×256) + AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.471 (AudioSet AS-2M full, tagging, 单模型)；集成 0.487 (AudioSet AS-2M full, tagging, 6 seed 集成) | 仓库未检索到 LICENSE 文件（`YuanGongND/h-ts-transformer` 的 main/master 分支均未取到，许可未明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2202.00874 |
| MaskSpec（Masked Spectrogram Prediction，ViT-Base） | 论文 best model（encoder-decoder，masked patch 重建） | 86.0 | A | AudioSet AS-2M full（仓库自述mean/std 取自 unbalanced 训练集） | tagging/527类 | AudioSet AS-2M full | mAP 0.471 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.323（据 CED 论文 Table 4 转引） | Apache-2.0（MaskSpec 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2204.12768；https://github.com/SafuanA/MaskSpec |
| AudioMAE（Masked Autoencoders that Listen，ViT-Base） | AudioMAE ViT-B，AS-2M 预训练 + 微调；仓库日志 `n_parameters: 85,659,407` | 85.66 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.473 (AudioSet AS-2M full, tagging, 单模型，仓库日志实测 0.4729)；AS-20K 对应值约 0.370 (AudioSet AS-20K, tagging) | CC-BY 4.0（仓库 LICENSE，README 明示） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2211.08553；https://github.com/facebookresearch/AudioMAE |
| BEATs iter3 | `BEATs iter3`，自蒸馏 tokenizer 第 3 轮迭代；90M ViT | 90.0 | A | AudioSet AS-2M full（自监督，无标签） | tagging/527类 | AudioSet AS-2M full | mAP 0.480 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.383 (AudioSet AS-20K, tagging, 单模型) | MIT（microsoft/unilm 根目录 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2212.09058；https://github.com/microsoft/unilm/tree/master/beats |
| BEATs iter3+ | `BEATs iter3+`，第 3 轮迭代 + 用微调后模型作tokenizer 教师 | 90.0 | A | AudioSet AS-2M full（自监督，无标签） | tagging/527类 | AudioSet AS-2M full | mAP 0.486 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.389 (AudioSet AS-20K, tagging, 单模型)；5/10 模型集成 0.504 / 0.506 (AudioSet AS-2M full, tagging, 集成) | MIT（microsoft/unilm 根目录 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2212.09058；https://github.com/microsoft/unilm/tree/master/beats |
| EAT-base（Efficient Audio Transformer，ViT-B，10 epoch 预训练） | `EAT-base`，ViT-B，AudioSet 上预训练 10 epoch 后微调 | 88.0 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.486 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.403 (AudioSet AS-20K, tagging) | MIT（EAT 仓库 LICENSE badge） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/cwx-worst-one/EAT |
| EAT-base（30 epoch 预训练版） | `EAT-base epoch30`，同为 ViT-B，预训练延长至 30 epoch | 88.0 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.489 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.413 (AudioSet AS-20K, tagging) | MIT（EAT 仓库 LICENSE badge） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/cwx-worst-one/EAT |
| EAT-large（ViT-L，20 epoch 预训练） | `EAT-large epoch20`，ViT-L 骨干 | 309.0 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.495 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.420 (AudioSet AS-20K, tagging) | MIT（EAT 仓库 LICENSE badge） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/cwx-worst-one/EAT |
| M2D/0.7（Masked Modeling Duo，ViT-Base） | `m2d_vit_base-80x1001p16x16-221006-mr7_as_46ab246d`，AS2M 微调权重（encoder only） | 86.0 | A | AudioSet AS-2M full（论文 §IV-A：2,005,132 段 10s 音频，5569h） | tagging/527类 | AudioSet AS-2M full | mAP 0.479±0.000 (AudioSet AS-2M full, tagging, 单模型，论文 Table VI)；AS-20K 对应值 0.386±0.000 (AudioSet AS-20K, tagging) | 仓库以 LICENSE.pdf 发布（PDF 内嵌字体子集，未能逐字读出许可类型；商用前须自行打开 LICENSE.pdf 确认） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2404.06095；https://github.com/nttcslab/m2d |
| M2D-AS/0.7（AudioSet 专用继续预训练） | `m2d_as_vit_base-80x1001p16x16-240213_AS-FT_enconly` | 86.0 | A | AudioSet AS-2M full | tagging/527类 | AudioSet AS-2M full | mAP 0.485±0.000 (AudioSet AS-2M full, tagging, 单模型，论文 Table VI)；AS-20K 对应值 0.418±0.000 (AudioSet AS-20K, tagging) | 仓库以 LICENSE.pdf 发布（PDF 内嵌字体子集，未能逐字读出许可类型） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2404.06095；https://github.com/nttcslab/m2d |
| ATST-Clip（Audio Teacher-Student Transformer，clip 级） | `ATST-Clip base`，12 blocks / 12 heads / 768 维；AS-2M 无标签预训练 | 86.0 | A | AudioSet AS-2M full（自监督，无标签） | tagging/527类 | AudioSet AS-2M full | mAP 0.452 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.379 (AudioSet AS-20K, tagging) | 代码 MIT；预训练 checkpoint CC-BY 4.0（audiossl仓库 LICENSE 明示两者不同） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/Audio-WestlakeU/audiossl |
| ATST-Frame（frame 级） | `ATST-Frame base`，12 blocks / 12 heads / 768 维；AS-2M 无标签预训练 | 86.0 | A | AudioSet AS-2M full（自监督，无标签） | tagging/527类 | AudioSet AS-2M full | mAP 0.480 (AudioSet AS-2M full, tagging, 单模型)；AS-20K 对应值 0.390 (AudioSet AS-20K, tagging) | 代码 MIT；预训练 checkpoint CC-BY 4.0 | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/Audio-WestlakeU/audiossl |
| ATST-C2F（ATST-Clip → ATST-Frame 知识蒸馏） | ATST-C2F，在微调阶段把 ATST-Clip 蒸馏进 ATST-Frame（论文标注 ** 为跨模型蒸馏） | 86.0 | A | AudioSet AS-2M full（自监督，无标签） | tagging/527类 | AudioSet AS-2M full | mAP 0.497 (AudioSet AS-2M full, tagging, 单模型，无模型集成)；AS-20K 对应值 0.405 (AudioSet AS-20K, tagging, 单模型) | 代码 MIT；预训练 checkpoint CC-BY 4.0 | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2306.04186；https://github.com/Audio-WestlakeU/audiossl |
| ATST-SED（ATST-Frame 微调成 SED 系统，两阶段训练） | ATST-SED；用 ATST-Frame 作骨干 + SED 头，两阶段（先冻结训练再解冻微调）；† 版本额外用 7,384 条AudioSet 强标注片段 | 86.0 | A | AudioSet AS-2M full（自监督，无标签）+ DCASE 训练集微调 | SED/10类 | DCASE2023 Task 4（DESED 室内声音事件，弱标注+无标签） | PSDS1 0.583 / PSDS2 0.810 (DCASE2023 Task 4, SED)；额外加 7,384 条 AudioSet 强标注后 PSDS1 0.587 / PSDS2 0.812 (DCASE2023 Task 4, SED) | 代码 MIT；预训练 checkpoint CC-BY 4.0 | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2309.08153；https://github.com/Audio-WestlakeU/audiossl |
| A-JEPA ViT-B（Joint-Embedding Predictive Architecture） | A-JEPA ViT-B（context encoder + EMA target encoder + predictor 16层/512维） | 86.0 | A | AudioSet AS-2M full（自监督，从头训练，无外部数据） | tagging/527类 | AudioSet AS-2M full | mAP 0.486 (AudioSet AS-2M full, tagging, 单模型，论文 Table 2/3/4 一致)；AS-20K 对应值 0.384 (AudioSet AS-20K, tagging, 论文 Table 2) | 未找到公开仓库/许可文件（论文给出 arXiv 编号，未检索到官方实现仓库） | no | unknown(未找到公开转换案例) | https://arxiv.org/abs/2311.15830 |
| M2D-CLAP（Masked Modeling Duo + CLAP 文本对齐，CLAP 仅训练期对齐） | `m2d_clap_vit_base-80x1001p16x16-240128_AS-FT_enconly`（文本仅作训练期对齐/教师，推理时只吃音频） | 86.0 | A | AudioSet AS-2M full + CLAP 文本-音频对齐（文本仅训练期，推理不吃文本） | tagging/527类 | AudioSet AS-2M full | mAP 0.485 (AudioSet AS-2M full, tagging, 单模型，官方 release 页所载AS2M mAP)；AS-20K 对应值 0.318 (AudioSet AS-20K, tagging, linear eval，官方 README) | 仓库以 LICENSE.pdf 发布（PDF 内嵌字体子集，未能逐字读出许可类型） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2404.06095；https://github.com/nttcslab/m2d |
| CED-Base（Consistent Ensemble Distillation，ViT 风格） | `ced_base`（`mispeech/ced-base`），Base=86M/768 embed/3072 MLP / 12 heads；大型教师集成（论文称 5-way ensemble teacher AS-2M 50.1）蒸馏；label-free（无人工标注） | 86.0 | A | AudioSet AS-2M full（教师集成产出软标签，学生只用 logits 训练） | tagging/527类 | AudioSet AS-2M full | mAP 0.500 (AudioSet AS-2M full, tagging, 单模型，论文 Table 4)；AS-20K 对应值 0.440 (AudioSet AS-20K, tagging, 论文 Table 4) | Apache-2.0（huggingface.co/mispeech/ced-base 卡片 license 字段） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2308.11957；https://huggingface.co/mispeech/ced-base |
| EfficientAT-mn30_as（MobileNetV3 width_mult=3.0，AudioSet 微调 + PaSST 蒸馏） | `mn30_as`，ImageNet 预训练后 ImageNet→AudioSet，PaSST 离线蒸馏 | 39.09 | A | AudioSet AS-2M full + ImageNet（同上本体不可直接获取） | tagging/527类 | AudioSet AS-2M full | mAP 0.482 (AudioSet AS-2M full, tagging)；4.55 GMACs/10s ≈ 455 MMACs/s | MIT（EfficientAT 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2211.04772；https://github.com/fschmid56/EfficientAT |
| EfficientAT-dymn20_as（Dynamic MobileNet width_mult=2.0） | `dymn20_as`，Dy-Conv + Dy-ReLU + Coordinate Attention，width_mult=2.0 | 40.02 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.491 (AudioSet AS-2M full, tagging)；2.2 GMACs/10s ≈ 220 MMACs/s | MIT（EfficientAT 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2310.15648；https://github.com/fschmid56/EfficientAT |
| EfficientAT-mn40_as（MobileNetV3 width_mult=4.0） | `mn40_as`，width_mult=4.0 | 68.43 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.484 (AudioSet AS-2M full, tagging)；8.03 GMACs/10s ≈ 803 MMACs/s | MIT（EfficientAT 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2211.04772；https://github.com/fschmid56/EfficientAT |
| EfficientAT-mn40_as_ext（`mn40_as` 延长训练 300 epoch 版） | `mn40_as_ext`，同结构、延长训练 | 68.43 | A | AudioSet AS-2M full + ImageNet | tagging/527类 | AudioSet AS-2M full | mAP 0.487 (AudioSet AS-2M full, tagging)；8.03 GMACs/10s ≈ 803 MMACs/s | MIT（EfficientAT 仓库 LICENSE） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2211.04772；https://github.com/fschmid56/EfficientAT |
| Dasheng-Base（Deep Audio-Signal Holistic Embeddings） | `dasheng_base`；272,356h 通用音频自监督（VGGSound/AudioSet/MTG-Jamendo/ACAV100M）；AudioSet 微调权重 `dasheng_audioset_mAP497.pt` | 86.0 | A | 272,356h 通用音频（VGGSound + AudioSet + MTG-Jamendo + ACAV100M） | tagging/527类 | AudioSet AS-2M full | mAP 0.497 (AudioSet AS-2M full, tagging, 单模型，官方 README「the performance for the base model is 49.7 mAP」)；官方另报 HEAR benchmark 线性评测（非 AudioSet mAP，不可与本行并列） | Apache-2.0（dasheng 仓库 LICENSE badge） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2409.05556；https://github.com/RicherMans/Dasheng |
| SSLAM（Self-Supervised Learning from Audio Mixtures，ViT-B/EAT 架构） | `ta012/SSLAM_AS2M_Finetuned`；在源混合音频上做教师-学生自蒸馏 + source retention loss；HF safetensors 实测 90,379,535 参数 | 90.38 | A | AudioSet AS-2M full（自监督，用源混合音频） | tagging/527类 | AudioSet AS-2M full | mAP 0.502 (AudioSet AS-2M full, tagging, 单模型，论文摘要「reaching a mean average precision (mAP) of 50.2」)；AS-20K 对应值 0.409 (AudioSet AS-20K, tagging) | MIT（HF 卡片 license 字段，README 亦标 MIT） | yes | unknown(未找到公开转换案例) | https://arxiv.org/abs/2506.12222；https://huggingface.co/ta012/SSLAM_AS2M_Finetuned |

**表内说明**

- **跨任务类型不可直接比较。** 本表含 **tagging**（AudioSet mAP）与 **SED**（DCASE PSDS1/PSDS2）两类：mAP 与 PSDS 不是一个量纲，**禁止放在一起比大小**。本表唯一的 SED 条目是 **ATST-SED（第 17 行）**，它夹在tagging 段中间——**读表时必须逐行看「基准」列**，凡基准为 DCASE 的行其指标与 AudioSet 行不同量纲，请勿跨段横向比数字。
- **AudioSet 划分已逐条标注，主表全部记AS-2M full。** 依据逐条回溯原文：PANNs 默认 `full_train`；AST 论文 Table 1 明确分列 "Balanced mAP / Full mAP"；PaSST 论文 §3 写明训练用 1,893,693 段（约 2M）；BEATs 论文 Table 1 表头为 AS-2M；CED 论文 Table 4 表头为 "AS-20K / AS-2M"；M2D 论文 Table I/II 定义 AS2M=全 2M、AS20K=balanced 21K；EAT 官方 README 表头为 "AS-20K mAP / AS-2M mAP"。**同一模型两处都有报告的，主表记AS-2M full，AS-20K 值写进「指标」列备注**（本表 16 条给出 AS-20K 对应值）。
- **MMACs/秒是折算值，不是原文数字。** PANNs 报multi-adds（×10⁹/10s）、EfficientAT 报 GMACs（/10s），折算时假设 multi-add ≈ MAC 且 MACs 随时长线性；DCASE 系列与本表无关。折算值**不含CUDNN/BLAS 实现开销，也不含 mel 滤波器组前端**。
- **集成（ensemble）与单模型已区分。** 主表 `指标` 列凡带"集成"字样者均为多模型集成结果，与单模型**不可直接比较**：同一模型集成常比单模型高 1–2 点（如 AST 0.459 单 → 0.485 集；PaSST 0.471 单 → 0.496 集；HTS-AT 0.471 单 → 0.487 集）。CED-Base 的 0.500 是**单模型**，其教师集成为 50.1（论文 §4.3），二者同样不可并列。
- **`AudioMAE` 参数量取仓库日志实测值 85,659,407**（README 逐epoch 日志里的 `n_parameters`），而非第三方转引的86M。EAT 各变体的参数量同样取官方 README 表格原值88M/309M。
- **A-JEPA 只报"未找到公开仓库"**：论文（arXiv 2311.15830）给出 ViT-S 22M/ViT-B 86M/ViT-L 304M 与 AS-2M 0.461/0.486/0.488，但**未检索到官方实现仓库**，故 `权重可得` 记 `no`、`edge` 记 `unknown`。本档只收 ViT-B 一条（ViT-L 304M 同为中型档，但为免同一论文重复占行，其参数与 mAP 差异记在此备注）。
- **M2D 系三个变体的许可无法逐字确认**：仓库以 `LICENSE.pdf` 发布，PDF 内嵌字体子集，本机解压未能读出许可正文，故`许可` 列如实写"未能逐字读出许可类型"，**不猜 MIT/Apache**。M2D-CLAP 的 `模态` 记 `A`（CLAP 文本只在训练期做对齐，推理时只吃音频，按 00 口径裁定 1 细则）。
- **本档的三处空白（如实记录，不给数字）**：
  1. **SED（中型）**：只找到 1 条可核验记录（ATST-SED）。DCASE2023 Task 4 官方结果页只报 PSDS1/PSDS2 与事件级 F1，**不含参数量列**，因此该赛道的多数系统无法落进本schema；ATST-SED 的对比对象（AST-SED 0.514、PaSST-SED 0.555/0.791、FDY-LKA-BEATs 0.546/0.807、MFDConv-BEATs 0.552/0.794）引自 ATST-SED 论文 Table 4 的转引，**这些系统的参数量未能核实，因此不入表**。
  2. **ASC（中型）**：未检索到 30M–500M 且同时给出「参数量 + DCASE 官方准确率」的 ASC 条目。口径文件 §硬规定 3 已警示ASC 结论不能外推到 tagging，本档不外推。
  3. **开放词表（中型）**：CLAP 系的音频-文本对齐属Task 6（多模态线）范围，本档不重复收录。
- `edge` 列**全部为 `unknown(未找到公开转换案例)`**——这是口径文件的合法值，表示"我没找到证据"，不等于"不能部署"。按计划该列由 Task 5 回填，本档不越权下结论。

**因缺少可靠来源或落不进本档而删除的候选（不写入表）**

| 候选 | 删除原因 |
| --- | --- |
| SPEARs+a XLarge（起点线索「≈50.0mAP」） | **数字与参数量均已核实到，但不属于本档**：论文（arXiv 2510.25955）原文为 "our largest model SPEARs+a XLarge ... setting a new state-of-the-art for SSL models on AS-2M AT task by achieving an mAP of **50.0**"，参数量 **600M**（论文 Table 3「SPEARs+a XLarge 600M197k」），按左闭右开属**大型档**（>500M），归Task 4 |
| ATST-C2F / ATST-F2C 的 `A+T` 误判风险 | ATST-C2F 的 0.497 是**纯音频**（ATST-Clip→ATST-Frame 蒸馏），无文本输入通道，故 `模态` 记 `A`；不存在开放词表版本 |
| EAT-CH / EAT-CSU（arXiv 2605.17512） | 报出 mAP 49.61±0.27（best 50.04）、111M 参数，但**未检索到对应的官方实现仓库**，且论文自述 EAT-CH/CSU 为本次新配置、第三方无法核验其权重可得性；只保留可核验的 EAT-base/large 两行 |
| MATPAC / met（arXiv 2508.12709、2508.12709） | 报出 AS-2M 0.4809（patchout FT）/ 0.4698（standard FT），但该文自身明确说明其AudioSet 版本与其他论文不同（「dataset version differences may cause significant differences」），**跨论文比较前提不成立**，不与本表并列；且未检索到官方权重仓库 |
| CAT（arXiv 2601.21612） | 报出 91M/AS-2M 0.502，与 SSLAM 同为 0.502；但该文的对比表把 PANNs 记为 0.431、AST 记为 45.9而其自身 AST 行参数写 86M，与 AST 原论文 Table 1（0.459 full / 0.347 balanced）口径不一致，**在协议对齐前不入表** |
| Dasheng-0.6B / Dasheng-1.2B | 600M / 1200M，按左闭右开属**大型档**，归 Task 4 |
| ATST-Clip/ATST-Frame small（22M） | 22M < 30M，按分档属**小型档**（口径文件裁定 2），不在本文件范围 |
| PaSST-L（50M） | 参数与 mAP（0.459）均可核，但与同论文的 PaSST-S（87M/0.471）构成同论文同结构缩比，保留一条即可，PaSST-L 记在此备注 |
| MaskSpec 的 AS-20K 主数值 | MaskSpec 原论文只报AudioSet 0.471（未在表头标划分），本档依 CED 论文 Table 4 的转引把 AS-20K 0.323 写进备注；**不把转引值当作独立出处** |
| EAT-large 的 309M 是否越界 | 309M < 500M，按左闭右开**确属中型**，已入表；此条仅说明边界判定依据 |
| 「CED 参数量约 52M」（速览版 §2.3） | 与 CED 论文正文 Table 1/Table 4 冲突：Base 为 **86M**（另有 Tiny 5.5M / Mini 10M / Small 22M，无52M 档）。**速览版的52M 说法不成立，已按论文正文纠正**；§1.1 的「~52.2 mAP」在论文中亦未找到（论文正文为Base 单模型 50.0、教师集成 50.1），**该数字已删除** |

---

## Part 2 · 中型档是 AED 的精度甜点

> 本节只做**同基准同任务**（AudioSet AS-2M full + 多标签 tagging + 单模型）的横向对比。
> 跨任务类型（mAP vs PSDS vs 准确率）与跨划分（AS-20K vs AS-2M full）**一律不参与本节比较**。

### 2.1 中型档在 AS-2M full 上的 mAP 区间

**区间：mAP 0.431（PANNs-CNN14，80.75M）– 0.502（SSLAM，90.38M），中位落在 0.48–0.49。**

分层看（同为 AS-2M full + tagging + 单模型）：

| 层| 代表模型 | 参数量 | mAP (AS-2M full, tagging, 单模型) |
| --- | --- | --- | --- |
| 区间下沿 | PANNs-CNN14（纯监督，CNN） | 80.75M | 0.431 |
| 监督+ImageNet 迁移 | AST | 87.0M | 0.459 |
| 纯音频自监督（ViT-B 级） | BEATs iter3 / ATST-Frame / M2D / AudioMAE / MaskSpec | 85.7–90.0M | 0.473 – 0.486 |
| 蒸馏 + 更强教师 | ATST-C2F（0.497）、CED-Base（0.500） | 86.0M | 0.497 – 0.500 |
| 区间上沿 | SSLAM（源混合音频自蒸馏） | 90.38M | 0.502 |

**关键观察：在 85M–90M 这个几乎不变的参数量窄带上，mAP 从 0.431 拉到 0.502，跨度 7.1 个点。** 这说明中型档内部的精度差异**几乎全部来自预训练/训练配方，而不是模型容量**——把 CED-Base（86M）换到 A-JEPA ViT-B（86M）、把 AST（87M）换到 SSLAM（90.4M），参数量基本没变，mAP 却差 4+ 点。

### 2.2 与小型档的同基准同任务对比

小型档数字**已逐条回溯原文核实**（下表三行出处见括注）：

| 模型 | 档 | 参数量(M) | mAP (AudioSet AS-2M full, tagging) | 出处 |
| --- | --- | --- | --- | --- |
| YAMNet | 小 | 3.7 | 0.306（另d′ 2.318 / lwlrap 0.393；69.2M multiplies/960ms 帧） | 官方 README 逐字："the classifier has 3.7M weights and performs 69.2M multiplies for each 960ms input frame"、"balanced mAP is 0.306" |
| EfficientAT-mn10_as | 小 | 4.88 | 0.471 | EfficientAT 官方 README 表（mn10_as，mAP 47.1） |
| EfficientAT-mn20_as | 小 | 17.91 | 0.478 | EfficientAT 官方 README 表（mn20_as，mAP 47.8） |
| **中型下沿** | 中 | 80.75 | **0.431**（PANNs-CNN14） | PANNs 论文 Table XI/XII |
| **中型上沿** | 中 | 90.38 | **0.502**（SSLAM） | SSLAM 论文摘要 + HF 权重 |

**结论一：中型档相对小型档的增益是实打实的，但不是线性的。**
从小型档上限（mn20_as，17.91M，0.478）到中型档上沿（SSLAM，90.38M，0.502），**参数量 ×5.0，mAP 只+2.4 个点**；而从 YAMNet（3.7M，0.306）到 mn20_as（17.91M，0.478），**参数量 ×4.8，mAP +17.2 个点**。也就是说：**最大的精度跃升发生在小型档内部（<20M），跨过30M 之后每加一个数量级参数只换来 2–4 个点。**

**结论二：小型档的性价比拐点在 20M 附近，30M 是"过了拐点仍在爬坡"的位置。**
- **≤20M（小型档）**：0.306（3.7M）→ 0.478（17.9M），平均每翻倍参数涨约 6–7 点 mAP。
- **30M–90M（中型档）**：0.431（80.75M，CNN）→ 0.502（90.38M），但**同参数量下换配方就能涨 4–7 点**（见 §2.1）。
- 因此 laos 若要"AudioSet tagging 精度上限"，30M–90M 是**必须进入的区间**；若要"低成本够用"，20M 附近的 EfficientAT-mn20_as（0.478）性价比最高——**它比中型档最弱的 PANNs-CNN14（0.431）还高 4.7 个点，而参数量只有其 1/4.5**。

### 2.3 代价：参数量、MMACs 与能否实时

| 维度 | 小型档（3.7M–17.9M） | 中型档（31M–90.4M，本档主体） | 涨幅 |
| --- | --- | --- | --- |
| 参数量 | 3.7M（YAMNet）–17.9M（mn20_as） | 31M（HTS-AT）–90.4M（SSLAM）；本档另有 309M（EAT-large） | **×8–24×** |
| 计算量 | 11–206 MMACs/s（EfficientAT mn04_as→mn20_as，/10s 口径） | 220–803 MMACs/s（EfficientAT dymn20_as→mn40_as，/10s 口径）；PANNs-CNN14 为 4222 MMACs/s | **×20–36×** |
| 单帧实时性 | YAMNet 逐 960ms 帧只需 69.2M multiplies，**天然近实时**（官方 README 逐字给出） | ViT-B 类（EAT-base/SSLAM/HTS-AT）**未找到公开的 RTF 或单帧 MMACs 实测**；EfficientAT 有 MACs 原值可查 | — |
| 端侧转换证据 | 本档唯一有官方路径的是 YAMNet（TFLite） | **本档 26 条 `edge` 全为 `unknown(未找到公开转换案例)`** | — |

**能否实时，如实给出三条可核验事实与一条未知：**

1. **可核验事实 · 计算量级：** 中型档的 CNN 路线（EfficientAT dymn20_as 2.2 GMACs/10s、mn40_as 8.03 GMACs/10s）比小型档 mn20_as（2.06 GMACs/10s）**只贵 1.07×–3.9×**——**注意这一比值远小于参数量比（39.09/17.91 ≈ 2.2×到 68.43/17.91 ≈ 3.8×）**，说明 width_mult 增大时计算量与参数近似同阶增长，没有出现"参数暴涨、算量不涨"的特例。
2. **可核验事实 · 与小型档的绝对差距：** 中型下沿 PANNs-CNN14 的 4222 MMACs/s 是小型档 EfficientAT mn20_as（206 MMACs/s）的 **20.5 倍**，也是 YAMNet（72 MMACs/s）的 **58.6 倍**。**按 00 口径 Part 2.3 的推导（DCASE 赛道 fp16 处参数与 MMACs 两条预算同时到顶、ρ≈481），这个算量级已远超端侧"每分析窗可花多少 MMACs"的预算**。
3. **可核验事实 · 结构性瓶颈：** 本档全部为**多标签 sigmoid + 逐类阈值**的 tagging 头（521/527 类），比小型档的同类头只多几十万个参数，**但头不是瓶颈——瓶颈是 ViT/CNN 主干的算量**。从 mn40_as（8.03 GMACs/10s ≈ 803 MMACs/s）到 EAT-large（309M ViT-L）再往上，单次 10 秒窗口的算量会再涨一个量级。
4. **未知（不给数字）：** 本档**未找到任何一条可核验的实测 RTF、单帧时延或端侧转换案例**。因此**"中型档能否实时"在本档无法回答**，只能给出两条间接事实：(a) 中型档最小的HTS-AT（31M）参数量仅为 AST（87M）的 36%，论文明确报告其训练时间为 AST 的 **13%**（80 小时 vs 600 小时，4×V-100）——**这是本档唯一一条官方的效率对比，但它说的是训练而非推理**；(b) `edge` 列的证据由 Task 5 补齐后再判。

**给 Task 5 / Task 6 / Task 8 的落地提示（不越权下结论，只把账摆清）：**
- 若laos 的检测段要求**逐帧出标签、不做时间定位**，那么中型档里**性价比最可疑的是纯 ViT-B 大参数量路线**（AST/EAT/SSLAM/A-JEPA 都在 86–90M 且mAP 集中在 0.46–0.50），而 **EfficientAT 系列的 MACs/参数比明显更省**（dymn20_as 40.02M / 2.2 GMACs 拿到 0.491，是本档"算力/精度比"最突出的一条）。
- 若要求**时间定位**（SED），本档只有 ATST-SED 一条（PSDS1 0.583/0.812，DCASE2023 Task 4），**且它用了 7,384 条 AudioSet 强标注片段**，在"只用弱标注"的前提下这个数字会掉到 0.583——**不可把它当作弱标注条件下的能力**。
- **两条必须写进选型结论的负信息**：M2D 系三个变体的 `LICENSE.pdf` 本机无法逐字读出；HTS-AT 官方仓库未检索到 LICENSE 文件。**这两条商用风险要留到 Task 7 处理。**

---

## 红线自检

- **可核验性**：26 条记录全部带 `arxiv.org` / `github.com` / `huggingface.co` 链接；**每条数字都回溯到了论文表格正文、官方 README 或 HF 权重元数据**，未照抄语料或聚合站摘要。删除理由见「因缺少可靠来源或落不进本档而删除的候选」。
- **无裸数字**：所有指标都带「基准名 + 任务类型」，且 AudioSet 一律标 `AS-2M full` 或 `AS-20K`；16 条同时给出 AS-20K 对应值（写在同一格的备注里），主表按口径文件规定 3 记 full。
- **跨类型不混比**：tagging 与 SED 分段排列并在表内说明处显式写明"禁止放在一起比大小"；§2.3 表格中 DCASE 与 AudioSet 不同行。
- **集成与单模型区分**：所有集成值在`指标` 列写明"集成"，并在表内说明处给出"集成高1–2 点、不可与单模型并列"的提醒。
- **AudioSet 现实性**：文件抬头与表格相应行都写明"本体不可直接获取，依赖第三方镜像或预计算 embedding"。
- **参数量口径**：统一按"量化前、含音频编码器、含标签头"；M2D/SSLAM 的数值取自 HF safetensors 实测元数据（89.97M 预训练 / 90.38M 微调后），AudioMAE 取仓库日志实测 85,659,407。**速览版的「CED ~52M」与「PaSST ~86M」两条🔶 断言中，前者与论文正文（86M）冲突已纠正，后者由 PaSST 论文正文「87M in the full model」与本文档一致。**
- **起点线索四项的核实结果**：SSLAM 50.2 ✅（数值对、**参数量 88M 错，实际 90.38M**）；CED 86M ≈ 50.0 ✅（数值与参数量均对）；SPEARs+a XLarge ≈ 50.0 ✅ 数值对但**参数量 600M，属大型档，已移出本档**；BEATs iter3+ ≈ 48.6 ✅（且必须写明是**单模型**，同论文集成版为 50.4/50.6）。
- **中文空白不冒充**：§2 的所有对比数字均来自英文 YouTube 语料AudioSet；**不得据此宣称中文家庭环境事件可用**（后果由 Task 7 记录）。
- **声纹**：本档未引入任何带说话人识别/验证能力的模型。