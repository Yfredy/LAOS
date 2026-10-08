# AED 大型模型档（> 500M，含音频大模型路线）

> 口径来源：`docs/research/audio-events/00-taxonomy-and-metrics.md`（12 列 schema、任务类型、
> AudioSet 划分、规模分档全部以该文件为准）。
> 本文件的机器校验：`python scripts/check_aed_table.py docs/research/audio-events/03-large-models.md`
> 姊妹篇：`01-small-models.md`（< 30M）、`02-medium-models.md`（30–500M）、`06-multimodal.md`（多模态轴）。

---

## 0. 本档的边界与三条填写说明

**边界**：参数量 > 500M（量化前、含音频编码器）。30M 归中型、500M 归大型，左闭右开
（口径文件「规模分档」）。

**说明 1 · 三种结构必须在「版本/权重」列写明**（口径文件「候选池 · 大型线」要求）：

| 结构 | 含义 | 本表条数 |
|---|---|---|
| 编码器 + 标签头 | 纯判别；冻结/微调编码器，上面挂分类头，不生成文本 | 3 |
| 端到端音频大模型 | 音频编码器直连 LLM，不产生中间文本，一次前向出结果 | 6 |
| 两段式 | 前段产出文本（ASR / caption / 关键词），后段 LLM 基于文本判定 | 2 |

**说明 2 · 本档没有"统一的 AED 榜单"。** 大型档里只有「编码器 + 标签头」这一支在
AudioSet / DESED 这类 AED 协议下报数；端到端音频大模型（LALM）公开报的几乎是
**captioning（FENSE / CIDEr）与 QA（AIR-Bench / MMAU / MMAR / MMAU-Pro）**，
以及 2026 年才出现的**事件级基准 TACOS（Event F1 / 幻觉率）**。
因此本表**混了四种任务类型**，`mAP ≠ PSDS ≠ FENSE ≠ Event F1`，**任何跨行的大小比较都无效**。
同任务类型内的对比只在 §2 判定点里做，并且逐条标明基准。

**最容易踩的一个坑（先写在这里）**：同样是 DESED，MiDashengLM 论文 Table 5 的
**53.7 是 X-Ares 上片段级分类准确率**，DASM 的 **42.2 是 PSDS1**，**两者不可比**
（准确率不计时间定位，PSDS1 计）。本表已在该单元格括号里标注 `非 PSDS`。

**说明 3 · 参数量口径的两处例外（已标在「版本/权重」列，不静默处理）**：

- **ZerAuCap**：论文只给出文本 LLM（OPT-1.3B）的规模，检索侧 WavCaps 的参数未给，
  故「参数量(M)」记 `1300`，是**下限值**，不是两段之和。
- **TAC→LLM 级联**：记 TAC 本体（Qwen2-Audio-7B 冻结 + LoRA）的 8397M，
  后段 reasoner 是独立模型（论文用 Qwen3-Next-80B-A3B / Gemini 3 Pro），**不计入本列**。
- **Whisper-AT**：论文 Table 1 的「AT #Params」列按脚注**不含 ASR 骨干**（冻结方案只报标签头
  0.7M–40M）。本表按口径文件「含音频编码器」补回编码器：**Whisper-Large 端到端微调行记 655M +
  TL-Tr512 头 7M = 662M**（ASR decoder 不是音频编码器，不计入）。
- **Kimi-Audio-7B-Instruct 的显存**：官方 HF 卡**未写**显存数字，本表 edge 列只写"服务端 GPU"，
  不做推断；第三方部署文档提到的 ~23 GB **未二次核实**，只在报告中列为待核实项。

**AudioSet 合规提示（口径文件红线 2）**：凡预训练/评测语料含 AudioSet 的记录
（Dasheng 系列、Whisper-AT），其音频本体为 YouTube 视频且官方已停止分发完整包，
实际复现依赖第三方镜像或预计算 embedding；**CC-BY 只覆盖本体与标签，不等于能拿到原始音频**。

---

## 1. 大型档记录表（11 条）

| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Dasheng-0.6B | 编码器+标签头：`mispeech/dasheng-0.6B` 冻结 + 线性头 | 600 | A | VGGSound + AudioSet + MTG-Jamendo + ACAV100M，272,356 小时（含 AudioSet） | tagging/527类 | HEAR benchmark | HEAR 环境声域线性评测 82.4 (HEAR benchmark, tagging·多任务均值) | Apache-2.0 | yes | no（服务端 GPU；未见公开端侧转换案例） | https://github.com/XiaoMi/dasheng |
| Dasheng-1.2B | 编码器+标签头：`mispeech/dasheng-1.2B` 冻结 + 线性头 | 1134 | A | VGGSound + AudioSet + MTG-Jamendo + ACAV100M，272,356 小时（含 AudioSet） | tagging/527类 | HEAR benchmark | HEAR 环境声域线性评测 83.2 (HEAR benchmark, tagging·多任务均值) | Apache-2.0 | yes | no（服务端 GPU；未见公开端侧转换案例） | https://github.com/XiaoMi/dasheng |
| Whisper-AT | 编码器+标签头：Whisper-Large 编码器(655M, 冻结) + TL-Tr512 标签头(7M) | 662 | A | Whisper 680k 小时标注语音；AT 头在 AudioSet 上训练（含 AudioSet） | tagging/527类 | AudioSet AS-2M full | mAP 41.5 (AudioSet AS-2M full, tagging)；AS-20K 32.8 (AudioSet AS-20K, tagging) | BSD-2-Clause | yes | no（ASR 骨干需服务端 GPU） | https://github.com/yuangongnd/whisper-at |
| Qwen2-Audio-7B-Instruct | 端到端音频大模型：Whisper 音频编码器直连 Qwen-7B | 8397 | A+T | Qwen-7B 文本基座 + 音频-文本多任务数据（ASR/S2TT/SER/VSC/AIR-Bench，见 arXiv:2407.10759） | 开放词表/任意类 | AIR-Bench Chat | AIR-Bench Chat-Sound 6.99/10 (AIR-Bench Chat, 开放词表音频问答·GPT-4 评分)；VocalSound ACC 0.9392 (VocalSound, ASC/6类人声事件) | Apache-2.0 | yes | no（服务端 GPU） | https://arxiv.org/abs/2407.10759 |
| Qwen2.5-Omni-7B | 端到端音频大模型：Whisper-large-v3 编码器 + Qwen2.5-7B（Thinker+Talker） | 10732 | A+T | Qwen2.5 多模态预训练数据（官方技术报告） | 开放词表/任意类 | 吞吐实测·30s 音频/100 token（非精度基准） | 吞吐 0.45 样本/秒 (30s 音频+100 输出 token, 80GB GPU bf16, batch=1)；batch=16 时 OOM (80GB GPU) | Apache-2.0 | yes | no（服务端 GPU；batch=16 即撑爆 80GB） | https://arxiv.org/abs/2508.03983 |
| Audio Flamingo 3 | 端到端音频大模型：AF-Whisper 统一音频编码器 + 7B LM（LLaVA 架构） | 8267 | A+T | 仅开源音频数据，约 50M 音频-文本对 | 开放词表/任意类 | TACOS | Event F1 0.27 / 幻觉率 11.6% (TACOS, 开放词表事件检测) | 非商用（NVIDIA OneWay Noncommercial；代码 MIT） | yes | no（服务端 GPU；权重非商用，laos 商用不可直接采用） | https://github.com/NVIDIA/audio-flamingo |
| MiDashengLM-7B | 端到端音频大模型：Dasheng 音频编码器(5Hz) + Qwen2.5-Omni-7B Thinker 解码器 | 8282 | A+T | ACAVCaps 等公开音频-文本数据（含 AudioSet/FSD50k 等） | 开放词表/任意类 | 吞吐实测·30s 音频/100 token（非精度基准） | 吞吐 0.65 样本/秒 / TTFT 40 ms (30s 音频+100 输出 token, 80GB GPU bf16, batch=1)；其音频编码器 X-Ares DESED 准确率 53.7 (X-Ares, tagging·片段级分类，非 PSDS) | Apache-2.0 | yes | no（服务端 GPU；有 w4a16 GPTQ 版仍约 3B 量级） | https://arxiv.org/abs/2508.03983 |
| Kimi-Audio-7B-Instruct | 端到端音频大模型：12.5Hz 音频 tokenizer（Whisper 连续特征 + 离散语义 token）+ Qwen2.5-7B | 9766 | A+T | > 1300 万小时语音/声音/音乐 | 开放词表/任意类 | AudioCaps | FENSE 49.00 (AudioCaps, 开放词表音频字幕)；官方卡仅列 SEC/ASC 任务覆盖，**无可核验的事件检测数字** | MIT（Qwen2.5 衍生部分 Apache-2.0） | yes | no（服务端 GPU，9.77B 参数） | https://huggingface.co/moonshotai/Kimi-Audio-7B-Instruct |
| TAC (Timestamped Audio Captioner) | 端到端音频大模型：Qwen2-Audio-7B 冻结 + LoRA r=128，输出带时间戳的事件描述 | 8397 | A+T | 合成动态混音 + 真实音频源（TACOS 训练管线） | 开放词表/任意类（带时间戳） | TACOS | Event F1 0.50 / Segment F1 0.70 / 幻觉率 4.9% (TACOS, 开放词表事件检测) | 未声明（权重未公开发布） | no | no（8×A100-80GB 训练；服务端 GPU） | https://arxiv.org/abs/2602.15766 |
| TAC→LLM 级联 | 两段式：TAC 产出带时间戳文本 → 纯文本 LLM reasoner 基于该文本推理（reasoner 参数另计） | 8397 | A+T | 同 TAC；reasoner 用 Qwen3-Next-80B-A3B 或 Gemini 3 Pro | 开放词表/任意类（带时间戳→文本推理） | MMAR / MMSU / MMAU-Pro | MMAR 71.9% / MMSU 72.4% / MMAU-Pro 62.9% (MMAR、MMSU、MMAU-Pro, 开放词表音频推理·两段式) | 未声明（权重未公开发布） | no | no（服务端 GPU + 独立 reasoner） | https://arxiv.org/abs/2602.15766 |
| ZerAuCap | 两段式：WavCaps 音频-语言模型选 614 个 AudioSet 关键词 → OPT-1.3B 依提示生成（参数量列记 OPT-1.3B，是下限） | 1300 | A+T | AudioSet 类表派生 614 关键词；WavCaps 预训练 | 开放词表/614 AudioSet 关键词 | AudioCaps | CIDEr 28.1 / METEOR 12.3 (AudioCaps, 开放词表音频字幕·零样本)；Clotho CIDEr 14.0 (Clotho, 开放词表音频字幕·零样本) | MIT（代码）；OPT / WavCaps 各依其自身许可 | yes | no（服务端 GPU） | https://arxiv.org/abs/2311.08396 |

### 附：API-only 商业模型（不入主表——参数量未公开，无法填「参数量(M)」列）

| 模型 | 版本 | 参数量 | 许可 | 公开可引用数字 | 来源 |
|---|---|---|---|---|---|
| Gemini 3 Pro | 2025-11 版（TAC 论文评测时点） | 未公开 | proprietary API | Event F1 0.42 / Segment F1 0.64 / 幻觉率 6.1% (TACOS, 开放词表事件检测) | https://arxiv.org/abs/2602.15766 |
| Gemini 2.5 Flash | MMAU-Pro 评测时点 | 未公开 | proprietary API | 57.33% (MMAU-Pro, 开放词表音频推理·5,305 题) | https://arxiv.org/abs/2605.20266 |

> 这两条**不进主表**的原因：口径文件 schema 的「参数量(M)」列必须是数字，商业模型不公开参数量，
> 填任何数字都是编造。它们的数字只在 §2 判定点里作为对照引用，不参与分档。
> 附带结论：**均不可端侧、不可离线**（proprietary API），与 laos「原音频即焚」架构冲突（Task 8 展开）。

---

## 2. 判定点：大型档在 AED 上换了什么

> 三问分别回答。**凡推断一律标注"推断"，凡查不到一律写"未找到公开证据"。**

### (a) 大型档的真正增量是不是开放词表？

**结论：不完全是。开放词表的那一步增益来自"帧级检索式跨模态融合"这个结构，不是来自"模型变大"；
而且把开放词表做上去的那支工作（DASM）根本不在大型档。**

**数字（已回溯原文核实）：**

| 系统 | DESED PSDS1 | 与监督 CRNN 基线的差 | 出处 |
|---|---|---|---|
| DASM（零样本·跨数据集） | **42.2** | **+5.8** | arXiv:2507.16343 §5.3 / Tab. 2 |
| 监督 CRNN 基线（DCASE 2023/2024 baseline） | **36.4**（由 42.2−5.8 反推；论文正文原文 "surpassing the supervised CNN-based baseline by 5.8"） | — | 同上 |
| LAION-CLAP（零样本） | 22.8 | −13.6 | 同上 |
| MGA-CLAP（零样本） | 24.6 | −11.8 | 同上 |
| DASM 在 DESED 上微调后 | 58.8 | — | 同上 |

三点必须写清：

1. **量纲**：口径文件 §指标 示例写 `PSDS1 0.422 (DESED, SED)`，DASM 论文写作 **42.2**
   （百分制 PSDS）。两者是同一数值的两种写法，本表与本节按论文原文写 42.2。
2. **DASM 不是大模型**：它是 HTS-AT / PaSST 编码器 + CLAP 查询生成模块 + 双流解码器，
   参数量在百万级，**不落本档（>500M）**。所以"零样本 PSDS1 首次超过监督 CRNN"这条
   **不能算作大型档的功劳**——它是"帧级检索式跨模态融合 + 推理时注意力掩码"的结构红利。
3. **CLAP 系零样本反而大幅低于监督基线**（22.8 / 24.6 vs 36.4）。即：**"开放词表"本身不是
   增益，"把开放词表做成帧级检索"才是**——架构含义完全不同。

**"audio LLM 不做 tagging" 还是 "做了但做不好"？结论：做了但做不好，且主流 LALM 根本不在 SED 协议下报数。**

- **不做（=SED 协议下无数字）**：Qwen2-Audio（arXiv:2407.10759）报的是 AIR-Bench Chat
  （Speech/Sound/Music/Mixed，GPT-4 评分 0–10）与 VocalSound；Qwen2.5-Omni / Kimi-Audio /
  MiDashengLM 在 arXiv:2508.03983 里比的是 **captioning（FENSE）与 MECAT**，
  **没有一个报 DESED PSDS 或 AudioSet mAP**。
  Kimi-Audio 官方卡只列"sound event/scene classification (SEC/ASC)"的**任务覆盖**，
  **未找到可核验的数字**——按速览版「补充核实清单」第 4 条，此处的结论写：
  **"宣称 SOTA，无公开可比数字"**。
- **做了但做不好**：一旦真的按事件/时间粒度评，7B 级 LALM 就掉下来——
  - TACOS（arXiv:2602.15766 Tab. 1）：**Audio Flamingo 3 Event F1 0.27 / 幻觉率 11.6%**；
    Qwen3-Omni 0.37 / 7.3%；Gemini 3 Pro 0.42 / 6.1%；而 TAC 0.50 / 4.9%。
  - AHA（arXiv:2512.24052，Fig. 2 诊断 Qwen2.5-Omni）：**Event Omission Rate > 40%、
    Boundary IoU < 0.4**，四类幻觉（事件遗漏 / 事件身份编造 / 时序关系错 / 时间量错）**全部命中**。

**架构含义**：不是"LLM 缺一个 tagging 头所以不做"，而是"LLM 有时间定位与漏检的系统性短板"，
补个头解决不了。**开放词表的能力应落在检索式结构（DASM 那类）上，不应指望 LALM 直接出标签。**

### (b) 7B 级模型处理 10 秒音频的耗时 / 显存量级

**可引用的实测数字（全部来自 arXiv:2508.03983 Tab. 13，80GB GPU、bf16、输入 30s 音频、输出固定 100 token）：**

| batch | MiDashengLM-7B（samples/s） | Qwen2.5-Omni-7B（samples/s） | 加速比 |
|---|---|---|---|
| 1 | **0.65**（≈1.5 s/条） | **0.45**（≈2.2 s/条） | 1.4× |
| 8 | 4.67 | 1.44 | 3.2× |
| 16 | 8.93 | **OOM（80GB 撑爆）** | 6.2× |
| 512 | 29.04 | — | 20.2× |

- **TTFT**：160 ms（Qwen2.5-Omni-7B）vs 40 ms（MiDashengLM-7B），最高 4×（同论文 §5.4 / Fig. 7）。
- **显存（可直接核验的部分）**：Audio Flamingo 3 在 MTEB 的模型记录里是 **30.8 GB**
  （8.27B 参数，BF16，https://docs.mteb.org/overview/available_models/audio_text）；
  Kimi-Audio-7B-Instruct 的 9.77B 参数 BF16 权重本身即约 20 GB 量级（**由参数量推算，非实测**）。
  第三方部署文档提到的 Kimi-Audio「~23 GB」**未二次核实**（官方 HF 卡未写显存）。
  综合量级：**8B 级音频大模型 BF16 推理 20–30 GB 显存起步**。
- **10 秒音频的直接测量：未找到公开证据。** 现有可引用的端到端时延数都是 **30 秒**输入。
  **推断（不是事实）**：按 batch=1 的 30s≈2.2 s 上界粗估，10 秒音频在 7B 级仍在**秒级/条**量级，
  且 20–30 GB 的常驻显存与"常驻检测"完全不兼容——**大型档只能做服务端批量，不能做常驻**。

### (c) 失败模式：对"不在提示集里的真实事件"是静默漏检还是误报？

**结论：两者同时存在，且以"静默漏检"为失效主因、"编造型误报"为辅。
这正是它不能做常驻检测的直接理由。**

- **漏检（静默）**：AHA（arXiv:2512.24052）诊断 Qwen2.5-Omni，**Event Omission Rate > 40%**——
  音频里确实存在的、能量偏低的事件（"巨响前的一声轻微嘶声"）被直接跳过，不报。
- **误报（编造）**：Audio Hallucination Attacks（arXiv:2603.29263）构造"预设声音存在"的隐式提问，
  **Audio Flamingo 3 攻击成功率 95.35%、Gemini 3 Pro 79.65%**——模型跳过"验证声音是否真的存在"
  这一步，直接自信作答。LALM Survey（arXiv:2605.20266 §3.1）把这类归为
  **Perceptual Hallucination：编造输入中并不存在的声学事件**。
- **漏检与误报是一对此消彼长的量**：TAC 论文自己观察到，换成随机混音训练后模型变得保守，
  幻觉率 4.9% → 2.2%，但**预测的事件数大幅减少、召回下降，Event F1 从 0.50 掉到 0.47**。
  即"压误报"必然"涨漏检"。
- **针对"提示集之外的真实事件"这一具体情形：未找到公开证据。**
  现有 benchmark（AHA-Eval、TACOS）测的都是"提示里给了假事件"或"给了完整场景"，
  **没有直接测"真实发生了、但不在你的类别提示集里"这种情形**。
  可用的**机制性**证据只有一条：DASM（arXiv:2507.16343 §5.4）的推理时掩码消融显示，
  **把基类查询 mask 掉后，模型几乎完全丧失检测新类的能力**——说明开放词表模型对"基类语义邻居"
  的依赖极强，**不能假设它能自发发现提示集外的事件**。

**落到常驻检测的判断（供 Task 7 landscape 引用）**：
开放词表模型**不会因为"没在提示集里"而报警，它会静默不报**（漏检 > 40% 量级）；
同时在它"想说点什么"的时候又会编造不存在的事件（AF3 幻觉率 11.6%）。
**既不保证召回也不保证精确**，因此**不能作为常驻检测段的唯一判据**；
可用位置是"事后/离线的二次确认"，而不是"是否触发捕获"的那一票。

---

## 3. 未入表的候选及原因

| 候选 | 原因 |
|---|---|
| DASM（Detect Any Sound，arXiv:2507.16343） | 参数量在百万级（HTS-AT/PaSST 编码器 + CLAP 查询模块），**不落 >500M 大型档**；归多模态轴（Task 6）。它的 DESED PSDS1 42.2 是 §2(a) 的关键证据，已在正文引用。 |
| Dasheng-Base（86M） | 中型档（Task 3）。顺带更正：AudioSet 微调后 mAP 49.7 是 **Base** 模型的数（官方 README "Is there an Audioset-finetuned Dasheng?"），**0.6B/1.2B 没有公开的 AudioSet mAP**——官方只给 HEAR 分数，故本表 Dasheng 两条用 HEAR，不用 mAP。 |
| SALMONN-13B / 7B | 参数量无法锁定（Vicuna-13B/7B 主干 + Whisper + BEATs + Q-Former，HF 无 safetensors 元数据），写 13B 只是"主干下限"，不满足口径"含音频编码器之和"。**删。** |
| Audio Flamingo 2（3B LM） | 官方只说"based on a 3B language model"，未给含 CLAP 编码器的总参数，且摘要无可核验的具体数字。**删。** |
| Pengi / LTU / LTU-AS / UniAudio / APE / GAMA | 本轮检索未拿到可核验的（参数量 + AED 相关指标 + 许可）三件套。**删**（口径文件：查不到来源的条目直接删除）。 |
| Gemini / GPT-4o 一类商业模型 | 参数量未公开，填不进 schema 的「参数量(M)」列（必须是数字）。改列入 §1 附表，只在正文作对照引用。 |
| Qwen3-Omni-7B | TACOS 上有 Event F1 0.37 / 幻觉率 7.3%（arXiv:2602.15766），但 HF 未找到可核验的参数量条目。**删**（数字已在 §2 正文引用）。 |

---

## 4. 给下游的交接点

- **Task 6（多模态轴）**：本表 `模态` 列按口径文件「裁定 1」填写——纯编码器记 `A`；
  LALM 记 `A+T`（文本指令/类别提示逐次变化，决定输出空间）。Task 6 若要改写，请附证据并在
  `00-taxonomy-and-metrics.md` 的裁定记录里写明。
- **Task 7（landscape）**：§2(c) 是本档对"常驻检测要不要升级"的直接输入——
  **大型档解决不了常驻**：秒级时延 + 20–30 GB 显存 + 漏检 > 40% 且伴编造型误报。
- **laos 商用注意**：Audio Flamingo 3 权重是 **NVIDIA OneWay Noncommercial（非商用）**，
  代码才是 MIT；DashScoped/API 类服务还有"音频要出网"的问题（Task 8 展开）。
