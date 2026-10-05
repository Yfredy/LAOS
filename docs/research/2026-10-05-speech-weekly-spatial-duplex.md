# 本周语音 AI 论文（8 篇）：空间音频 × 全双工 —— 学习与采纳评估

> 学习日期：2026-10-05。来源：用户分享的小红书周报《本周语音AI论文（8篇）｜空间音频、全双工》
> （`xhslink.cn/o/4mTG7i7Prci`，笔记 id `6ac11e69000000000b005c2f`，分享时间戳 ≈ 2026-10-03）。
>
> **来源诚实声明**：小红书正文在登录墙+滑块验证之后，webReader/WebFetch/搜索均无法直接取出。
> 本文档的论文清单是**按"当周时间窗（2026-09-25 ~ 10-01）+ 标题宣称的两个主题（空间音频、全双工）
> 各取新论文"从 arXiv eess.AS 反推重构的**：该周恰好存在 4 篇空间音频 + 4 篇全双工 = 8 篇高显示度
> 新论文，与周报标题的"8 篇｜空间音频、全双工"严格吻合（4+4）。若原帖 8 篇与此有出入，差异大概率
> 落在文末"同期备选"列表内（同周同主题的另外 4~5 篇）——内容学习价值不受影响，但**标注为重构而非
> 原文转录**。摘要素材来自 arXiv API（export.arxiv.org）逐篇拉取的官方 abstract，非二手转述。

## 〇、8 篇总览

| # | 主题 | 论文 | arXiv | 日期 | 一句话 |
|---|---|---|---|---|---|
| 1 | 空间音频 | RMS-AQA：家庭空间音频问答基准 | 2610.00935 | 10-01 | 两阶段 SAQA：先定位声音事件、再做时空推理，专测"并发声源/远场/sim-to-real"三大失败模式 |
| 2 | 空间音频 | Bin2Ambi：双耳+头动 → Ambisonics | 2609.39732 | 09-30 | 用智能耳机头动追踪消解双耳的前后镜像与混乱锥，定义并基线化了 Bin2Ambi 新任务 |
| 3 | 空间音频 | OmniDream：任意视频 → 沉浸式音视 | 2609.36295 | 09-28 | 免训练：对象中心音频表示把"声源内容"与"场景声学"解耦，声音随视线环游保持空间对齐 |
| 4 | 空间音频 | SAIL：LLM 理解空间音频 | 2609.34347 | 09-28 | 声学流（mel）与空间流（双耳相位差）解耦 + 按声源槽组织的双流 Q-Former，多声源对应不丢 |
| 5 | 全双工 | CharDuplex：角色一致全双工对话 | 2609.34461 | 09-28 | GLM-4-Voice 改双流常开 + 角色数据 SFT + FDGym 模拟用户 RL，开源模型 SpeechRole-Eval 最高 |
| 6 | 全双工 | SALMONN-duo：快慢双系统语音代理 | 2609.34247 | 09-28 | 系统 1 常开全双工管实时交互、系统 2 异步深思代理管工具推理，学会"何时委托" |
| 7 | 全双工 | Context Spanning：检索信息注入全双工模型 | 2609.33443 | 09-27 | 分块预填把外部 LLM 检索到的**原始文本**在实时帧预算内单次前向注入，不经潜在空间压缩 |
| 8 | 全双工 | Duplex-MPE：多方全双工交互基准 | 2609.31948 | 09-25 | 2,000 场景 × 3-4 人 + 1 助手，评"何时答/沉默/停"四能力，MiniCPM-o 4.5 三项领先 |

---

## 一、空间音频 4 篇

### 1. RMS-AQA（arXiv 2610.00935，2026-10-01）

**RMS-AQA: A Two-Stage Spatial Audio Question Answering Benchmark for Real-World Domestic Environments**
（Peihao Chen, Qing Wang, Lichun Fan, et al.）

家庭具身助手必须推断"发生了什么事件、在何处何时发生、应如何响应"。RMS-AQA 用**两阶段问答**
显式拆开这两步：第一阶段定位可听声音事件，第二阶段基于定位结果做复杂时空推理。数据为真实
一阶 Ambisonics（FOA）录音 + 实测 RIR 合成的高保真数据混合；另附一个轻量"空间插件"把 FOA
四通道注入冻结的音频-语言骨干。结论：主要失败模式是**并发声源、远距离、仿真→现实的域差距**。

**与 laos 的关系**：laos 的空间听觉栈（micgeom 几何编码 + ShoNet DOA 复现 + 未来的 foa 工具）
缺的正是"拿什么评"——RMS-AQA 的数据格式（FOA wav + 两阶段问题）可以直接当 laos 空间栈的
外部验收集；其"空间插件把几何信息旁路注入冻结骨干"与 laos micgeom 的哲学同构（几何先验与
声学特征分离供给）。**→ 采纳 ◐D（FOA 基础件）+ 远期评测钩子。**

### 2. Bin2Ambi（arXiv 2609.39732，2026-09-30）

**Bin2Ambi: Learning Ambisonic Soundfield Reconstruction from Head-Tracked Binaural Audio**
（Gavin Milner, Nils Peters —— IEEE 中央研究院风格的音频组）

用户生成内容时代，消费级硬件录不了空间音频；但智能耳机普及，双耳录音人人可得。双耳信号固有
缺陷：前后镜像（front-back ambiguity）与混乱锥（cone-of-confusion）内测向误差。本文**定义了
Bin2Ambi 新任务**并给出基线：利用耳机运动传感器同步的头动数据（用户自然环视 = 天然的角度
采样），让模型学出方向信息与扩散场信息。结果：平均方向误差最高约 **11.8°**，主观感知空间质量
与 DirAC 真值模型相当；头动尤其压制极端定位误差。

**与 laos 的关系**：laos 若做空间录音回放/空间记忆，双耳（手机立体声麦/耳机双麦）是现实输入，
FOA 是通用中间表示——Bin2Ambi 指出的路径是"用运动传感器补双耳的角度欠定"。laos 侧可先落的
是**FOA 这个中间格式的读写与编解码基础件**（`laos/foa.py`），学习模型部分留在驱动子进程远期。
**→ 采纳 ◐D。**

### 3. OmniDream（arXiv 2609.36295，2026-09-28）

**Enabling Immersive Audio-Visual Experience from Any Video**（OmniDream）
（Zitong Lan, Mutian Tong, Jiatao Gu, et al.）

单目无声视频 → 可自由环视、声画空间对齐的沉浸式体验，**免训练**。核心是对象中心的音频表示：
把每个声源的**固有音频内容**与**场景相关的声学效果**（传播、混响）解耦——于是内容生成、物理
传播模拟、空间渲染三者可独立进行再组合。音画对齐、空间正确性、感知沉浸感均超基线。

**与 laos 的关系**：离 laos 内核最远（生成式音视合成），但它的**元数据三段式**值得抄：一个音频
事件存"内容（是什么声）+ 空间（在哪）+ 声学（什么房间条件下）"三段独立字段——这正是 laos
audio-events 记忆 schema 的进化方向（现在只有内容+时间戳）。**→ ○E 记入文档，不动代码。**

### 4. SAIL（arXiv 2609.34347，2029-09-28）

**SAIL: Spatial Audio Intelligence with Large Language Models via Disentangled Acoustic-Spatial
Encoding and Dual-Stream Q-Former**（Zhengding Luo, Jinyang Wu, Haozhe Ma, et al.）

现有空间音频 LLM 的通病：声学与空间特征**早期融合** + 与声源无关的 token 表示 → 多声源场景
"哪个声源在哪个方向"的对应关系丢失。SAIL 全程保持声学-空间结构与声源级对应：
① 解耦空间音频 Transformer——mel 频谱（声学流）与**双耳相位差**（空间流）分开编码；
② 源判别式任务查询——每个声源各学事件/方向/距离；
③ 双流 Q-Former——声学查询与空间查询**按声源槽配对**后再对齐 LLM。双声源事件检测、方向/距离
估计、空间推理全面超早期融合基线。

**与 laos 的关系**：直接验证了 laos 的两条既有路线——(a) micgeom 把几何先验单独编码（而非
混进特征）；(b) ShoNet 用相位特征做空间推断。SAIL 指出最小可用的**空间流特征就是双耳相位差
（IPD）与强度差（ILD）**——纯 stdlib 可算，正好补 laos 空间特征工具的缺口（现在有几何编码
micgeom、没有信号侧线索）。**→ 采纳 ●C（`laos/binaural.py`：Goertzel ILD/IPD）。**

---

## 二、全双工 4 篇

### 5. CharDuplex（arXiv 2609.34461，2026-09-28）

**CharDuplex: Building Character-Consistent Full-Duplex Spoken Dialogue Models**
（Donghang Wu, Yisi Liu, Chen Chen, et al.）

全双工语音模型解决了"何时说话"，但自然对话还取决于"作为什么角色说话"。三步：① 把 GLM-4-Voice
改造成常开双流架构并训练全双工对话；② 全自动流水线从开源角色描述构建角色条件化对话数据做 SFT；
③ **FDGym**——LLM 模拟的用户与模型动态多轮交互下做进化式 RL。SpeechRole-Eval 上开源最高分、
与闭源系统保持竞争力。

**与 laos 的关系**：两点。(a) 角色一致性在 laos 里归 context/system prompt 层管（内核不掺和，
正确分工）；(b) **FDGym 的"LLM 模拟用户做对话回归测试"是 laos 语音链路缺的测试形态**——laos
现有测试全部 Fake 驱动注入，没有一个"模拟用户持续说话→观察轮转决策"的闭环。**→ ○E 记录，
远期做 fake-user 回归驱动。**

### 6. SALMONN-duo（arXiv 2609.34247，2026-09-28）

**SALMONN-duo: Adaptive Dual-System Coordination for Full-Duplex Voice Agents**
（Wenyi Yu, Siyin Wang, Terumi Chiba, et al.）

双过程认知理论的工程化：**系统 1** = 常开的快思考全双工语音 LLM（实时听与说），**系统 2** =
强大的异步慢思考 LLM 代理（工具调用、深思推理）。矛盾点在延迟与成本不可变，与实时时序冲突。
SALMONN-duo 让系统 1 学会：何时直接回答、**何时委托**；委托后系统 1 保持说话不冷场；系统 2
返回的信息**无缝织入进行中的对话**（不暴露工具痕迹、不丢上下文）。知识边界感知训练避免无谓
委托；成本感知 RL 进一步优化"任务性能 vs 后端使用"的权衡（τ-Voice 业务实测）。

**与 laos 的关系**：这就是 laos 架构的语音版镜像——驱动层（实时、流式、薄）= 系统 1；
AgentKernel + Jev + syscall 闸门（深思、异步、重）= 系统 2。laos 缺的是**委托期间的轮次语义**：
慢 syscall 挂起时，语音侧该说什么（保活播报）、结果回来怎么插进当前轮。**→ 采纳 ●B
（`TurnBuffer.interject`：结果插队注入语义）。**

### 7. Context Spanning（arXiv 2609.33443，2026-09-27，投稿 ICASSP 2027）

**Context Spanning: A Communication Framework for Full-Duplex Speech Models and External
LLM Backends**（Seonghyeon Go, Yongwoo Kim, Hyeonjin Cha, et al.）

全双工语音模型困在参数化知识里，拿不到实时信息、调不了工具；即使外挂 LLM 检索到了信息，主流
双工模型在**压缩的潜在空间**里处理注入信息而非原始文本——压缩即损失。Context Spanning 用
**实时分块预填（chunked prefill）**：检索到的原文切成帧，在实时帧预算内经**单次前向传播**编码
后直接注入语音模型，模型对原始信息自行推理作答。全双工基准高性能、问答强。

**与 laos 的关系**：laos 的记忆/上下文链路本来就是"原文进原文出"（mem.remember 存原文、
无压缩中间层）——这篇论文用实验证明了这条设计决策的价值（压缩注入 = 信息损失）。可采纳的是
**注入动作本身的语义**：外部结果到达时以"插队帧"进入当前轮而非等下一轮。与 ●B 同一接口
（interject）。**→ 采纳 ●B。**

### 8. Duplex-MPE（arXiv 2609.31948，2026-09-25）

**Duplex-MPE: Benchmarking Multi-Party Interaction in Full-Duplex Dialogue**
（Chengqian Ma, Wenhao Feng, Weixuan Jin, et al.，27 页）

现有全双工基准都围着"一个指定用户"转；真实多方对话里助手只是参与者之一。Duplex-MPE：**2,000
个场景，3-4 名人类说话者 + 1 个助手**，显式/隐式指代的同一请求配对出现；模型只听连续对话音频
（无转录、无轮次边界）。四项评分：**新回复的发起、回答准确性、沉默保持（别人聊别人的时不插嘴）、
人类自行解决后停止说话**。评了五个开权重系统（MiniCPM-o 4.5 / Moshi / FLM-Audio / Voila /
Freeze-Omni）：MiniCPM-o 4.5 三项领先；其他系统"频繁发言"常与"答不准/该闭嘴没闭嘴"并存。
转录版 Gemini 3.1 Pro 参考系统对显式请求的响应率比对隐式高 **64.3 个百分点**。

**与 laos 的关系**：这篇给了全双工能力的**可操作分解**——发起/准确/沉默/停止四项中，"发起、
沉默、停止"是纯时序决策（不涉及内容质量），恰好是 laos 作为 OS 层能管、也该管的部分：
laos 已有 TurnBuffer（打断即作废）但**没有"该不该开口"的策略位**。**→ 采纳 ●A（duplex 时序
度量）+ ●B（TurnPolicy 三态决策）。**

---

## 三、同期备选（若原帖清单与此有出入，差异大概率在这里）

| 论文 | arXiv | 日期 | 主题 | 一句话 |
|---|---|---|---|---|
| 低码率 FOA 参数编解码器（DirAC+RVQ） | 2609.33554 | 09-27 | 空间音频 | 一阶 Ambisonics 的低码率参数化编码 |
| LateIntent-Bench | 2610.00272 | 09-24 | 全双工 | 意图延迟揭示：过早响应率指标 |
| RePlay 检索式语音回放 | 2609.31588 | 09-25 | 全双工 | 预录台词检索回放，中位延迟 383ms |
| 声学→文本 KV 压缩 | 2609.31224 | 09-25 | 全双工 | 空闲期把声学转文本记忆，峰值 KV 降 64.6% |
| 频谱水印 Redwing | 2609.33774 | 09-27 | 语音安全 | token 重标记结构水印抗多次编解码 |

---

## 四、采纳裁决（沿用 ●执行 / ◐基础件或文档 / ○不做 三档）

| 项 | 内容 | 来源论文 | 落点 | 档 |
|---|---|---|---|---|
| A | **双工时序度量**：事件时间线 → 响应延迟/打断响应/重叠率/抢话计数，JSON 摘要 | Duplex-MPE（+CharDuplex 时序面） | 新 `laos/duplex.py` | ● |
| B | **轮转三态策略 + 委托注入**：`TurnPolicy.decide()→speak/hold/stop`；`TurnBuffer.interject()` 插队帧 | Duplex-MPE + SALMONN-duo + Context Spanning | 新 `laos/turnpolicy.py`、改 `laos/turnbuf.py` | ● |
| C | **双耳空间线索**：Goertzel 逐频点 ILD(dB)/IPD(rad)，纯 stdlib | SAIL（空间流特征最小内核版） | 新 `laos/binaural.py` | ● |
| D | **FOA 基础件**：平面波编码 WXYZ（SN3D/N3D）、四角扬声器解码、ACN 序 | Bin2Ambi + RMS-AQA | 新 `laos/foa.py` | ◐ |
| E | 角色一致性归 context 层；FDGym 式模拟用户回归；OmniDream 三段式音频事件元数据 | CharDuplex + OmniDream | 本文档记录 | ○ |

实施计划（writing-plans 格式，TDD）：`docs/research/plans/2026-10-05-speech-weekly-adoption.md`。

> **执行注记（2026-10-05，v0.12.0）**：A/B/C/D 四项当波全部落地——`laos/duplex.py`
> （11 测试）、`laos/turnpolicy.py`（11 测试，含计划外补的"已答话轮不重复触发
> speak"守卫）、`TurnBuffer.interject()`（4 测试，与既有 turnbuf 8 测试不破）、
> `laos/binaural.py`（8 测试；Goertzel 终值公式 X = e^{−iω(N−1)}·(s[N−1] − e^{−iω}·s[N−2])
> 与直接 DFT 逐点互验）、`laos/foa.py`（8 测试；修正：ACN 一阶序是 W,Y,Z,X 而非
> W,X,Y,Z，四角解码"正对最大/对侧为零"而非"独占"——W 全向贡献使然）。全量
> 415 测试绿。

**红线自查**：A-D 全部纯 stdlib（Goertzel/状态机/事件配对，无 numpy 依赖），不破 laos 核心零依赖
承诺；不装任何包（conda 红线）；不触碰录音触发语义（LAOS_REC、显式 syscall、审计不变）。
