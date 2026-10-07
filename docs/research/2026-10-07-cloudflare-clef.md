# Cloudflare Clef 决策模型学习与 laos 判断层对照

> 调研日期：2026-10-07 · 来源：小红书《38.8毫秒返回分类答案》→ Cloudflare 博客《Clef decision models》（2026-10-01T15:34Z，Birthday Week 2026）

## 一、来源诚实声明（笔记转译链核对）

笔记四条声称逐条核实：

| 笔记声称 | 核实结果 |
|---|---|
| "38.8 毫秒返回分类答案"（10-01 Cloudflare 博客） | ✅ **真实**：Clef-flash 中位延迟 38.8ms（p95 122.4ms），跨 43 项评测基准——但它是**决策延迟**（prefill-only 非自回归，无逐 token 生成），笔记说成"首 token 延迟"属转译失真 |
| "llama.cpp-SURGE 推理引擎""越大越快/每千 token 成本随模型增大而降" | ❌ **未证实**：Birthday Week 2026 全部 46 条公告（wrap-up 页核对）与 Clef 原文均无此引擎；最接近的真身是 2025-08 自研 Rust 引擎 **Infire**（continuous batching+分页 KV+JIT CUDA 内核），但无 SURGE 之名、无"越大越便宜"表述 |
| "✨Spark 免费（无服务器函数不按 token 计费）""7B $0.26 / 15B $0.16" | ❌ **未证实**：46 条公告与 Clef 原文均无 Spark 模型与该定价表 |
| "连续批处理优化" | ◐ Cloudflare 真实技术（Infire 的 continuous batching with chunked prefill），但与笔记语境的绑定不可证 |

结论：笔记以一条真实核心（Clef 38.8ms）混入三条不可证装饰（疑为转译链编造或张冠李戴）。本文只采信 Clef 原文事实。

## 二、Clef 是什么（原文全事实）

- **定位**：Agent 工作流的**决策步**——接收状态、按 schema（noul/choice/score）返回带概率的类型化答案，供代码路由/升级/转人工；可置于 agent 热路径。
- **两型**：Clef（精度型，Qwen3.8-27B 基座冻结）与 Clef-flash（低延迟型，Qwen3.5-9B 基座）；联合优化 routing head + rank-256 LoRA。
- **延迟本质**：**非自回归**——prefill 一遍后并行给 schema 选项打分。基准（中位/p95 ms）：Clef 209.3/238.6、Clef-flash 38.8/122.4、（对照 Jev 524.1/536.0、Kev-9B 51.4/187.9、Laya 5.8/222.5、DiffusionGemma 84.4/211.2）。实测工作流：Browser Run 抓取+域名分类 2.2s（gpt-oss-120b 同任务 4.7s）。
- **训练**：label-smoothed CE + **Brier loss 概率校准**；RLCD（校准决策强化学习）二级优化；合成数据集；FDE 人工微调 → 自助 RL 平台（AI Gateway 采集/Workers AI rollouts/Containers 沙箱评分/Trainer 更新/BYO 重部署）。
- **开放性**：HuggingFace `Cloudflare/clef` 与 `Cloudflare/clef-flash`，**Apache 2.0**；托管 Workers AI（@cf/cloudflare/clef），承诺不读取/存储/不用于训练。
- **其他**：上下文 64k、视觉编码器支持图像分类、API 兼容 Jev 输出严格类型化结构、BFCL case exact 98.47/98.76（vs Jev 95.75）。
- 名字寓意：谱号（clef）定义后续音符——决策步定义 agent 的后续行为。

## 三、laos 判断层对照（本轮学习的核心增量）

laos 判断层现状（2026-09 调研 + 实测）：Jev 四闸门/11 处硬阈值映射；端侧 edgejev 实测 median **157.5ms**（ONNX int8 324.5MB，README 宣称 15.6ms 被否证）；三判型 Noul/Choice/Score；判断层落点结论=常驻每帧调用否决（0.5–1.5W）、离线/二级确认档可接受（4.6mW）。

Clef 带来的四个增量认知：

1. **判断层的第三条路线成立**：规则阈值（laos 现行）→ edgejev（端侧小模型）→ **Clef-flash 权重本地部署**（9B 基座+rank-256 LoRA，Apache 2.0 可下载）。38.8ms 是边缘 GPU 口径，端侧 CPU 会显著慢——但它把"决策模型"的延迟基线从 Jev 的 524ms 拉到 38.8ms（13.5×），证明**非自回归 prefill 打分才是判断层可进热路径的正确架构**。这与 laos 判断层"每帧调用的成本模型"结论互证。
2. **schema 同源**：Clef 的 noul/choice/score 三字段与 laos 判断层调研的三判型原语**同名同义**（Jev 兼容 API）——laos judge 概念模型可直接映射 Clef 调用面，切换成本低。
3. **校准方法论**：Brier loss 概率校准 + RLCD 是 laos 判断层"校准台"调研的工程化补全——决策模型不只对答案，还要**对概率负责**（laos 四闸门的阈值本质也是概率门）。
4. **隐私承诺同构**："不读取/存储/不训练"承诺 + 开放权重可自托管——与 laos 红线（本地优先、显式触发、不上传）完全兼容；自托管权重即可完全落在红线内。

## 四、采纳裁决

| 项 | 裁决 | 理由 |
|---|---|---|
| Clef-flash 权重本地部署评测 | ◐ P2 | Apache 2.0 权重在 HF（Cloudflare/clef-flash）；9B 基座对 laos 现有端侧预算偏重（对照 whistle 16.9MB/edgejev 324MB 梯度），但作为判断层精度-延迟新基线值得一次实测（wer.py 同款纪律：先测再裁）；断网窗口 HF 下载待机 |
| 非自回归 prefill-only 决策架构 | ● 已消化（认知层） | 判断层热路径架构定型结论 +1 佐证；laos 判断层设计文档引用 |
| Brier/RLCD 校准 | ◐ P3 | 校准台方法库条目 |
| Workers AI 云端调用 | ○ | 云依赖，违 laos 本地优先（自托管权重后另议） |
| 笔记中 SURGE/Spark/定价 | ○ 不采信 | 三条均不可证，记入来源诚实档案 |

## 五、后续（可选）

1. HF 窗口开时下载 clef-flash 权重做端侧实测（延迟/体积/三判型覆盖）——判断层 P2 项落地即此；
2. 与 edgejev（157.5ms/324MB）同台对比出"判断层选型表"终版；
3. laos 判断层文档补 Clef 条目（jev/ 目录加一篇对照）。
