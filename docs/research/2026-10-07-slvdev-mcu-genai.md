# 单片机跑生成式模型（slvDev 三项目）复现与采纳

> 调研日期：2026-10-07 · 来源：小红书《单片机上跑起生成式模型》→ OpenSourceForU《Microcontrollers Now Run a Diffusion Model and 289M LLM》（Ananthu Ashok，2026-09-28，Adafruit 09-29 转载）→ GitHub 作者 slvDev

## 一、来源与诚实声明

- 笔记正文三条：STM32N6570-DK 上 3.36MB 量化扩散模型出 64×64 灰度图（Cortex-M55+Ethos-U55）；NXP FRDM-MCXN947 上 2.89 亿参数 LLM；ESP32-S3 上 2890 万参数 LLM @9.88 tok/s 权重驻闪存。共同点：裸机（无 Linux/GPU/外接加速器）。
- **溯源核对**：OSFY 原文实测可读，内容与笔记一致；但 [theaivibe 的平行报道](https://theaivibe.org/edge/a-diffusion-model-and-a-289m-llm-both-now-run-on-bare-microcontrollers-2026-09-24)给出 **"28.9M"而非"289M"**——OSFY 的"2.89 亿"极可能是 28.9M 的十进制误读（我们克隆仓库后实测证实 28.9M 为真，见 §二）。
- **三仓定位**：作者 GitHub = slvDev：`esp32-ai`（28.9M PLE TinyLM，已克隆+复现）、`stm32-diffusion`（纯 C 扩散模型）、`stm32-voice`（纯 C 无 RTOS 语音管线 VAD/STT/TTS）。**后两仓在 2026-10-07 深度断网窗内克隆 30+ 轮未果**（GitHub 直连与服务器侧读取同时不可用），长线重试挂机中，落地后补篇；本文对它们的全部表述限于 README 可见信息并标注未验证。
- 仓库描述声称 "Generation, transcription, and dictation"——**全仓 grep `whisper|transcri|dictation|asr|speech|stt` 零命中**：转写/听写为营销话术，不存在实现（诚实纠偏，笔记若含此意则为讹传）。

## 二、esp32-ai 复现（核心，Windows x86 实测）

**项目本质**：28.9M 参数 PLE TinyLM（TinyStories 风格故事生成）跑在 ESP32-S3 N16R8（16MB flash/8MB PSRAM）上，与宿主 PC 共用同一份单文件 C 运行时 `runtime/llm.h`（作者原注释："Same code runs on the host and on the ESP32"）。

**架构（源码测绘）**：
- 模型格式：自定义 `model.bin`（魔数 `PLE\0`，56B 头），张量序 tok_emb→ple 投影→**ple_table**→6 层{attn+SwiGLU+PLE 门控}→out_head；
- 量化：int4 nibble + fp16 分组 scale（group=128），28.9M→**14.91MB**；
- 三层内存：SRAM=激活/norm/scratch，PSRAM=int8 staging 核心+输出头+KV cache，**FLASH=25M 参数 PLE 查表**（分区 mmap 零拷贝，每 token 只读 ~450B）——28.9M 的真相：559K dense core + 3.1M 输出头 + 25M PLE 查表（作者 RESULTS.md 自注"stored parameters，非能力倍数"）；
- PLE（Per-Layer Embeddings）：`ple_table[V, L*P]` 按 token 取行切 L 份逐层门控注入——忠实 Gemma 3n 机制；
- 板端 9.88 tok/s = 94.9ms/token（作者分解：输出头 59.4/注意力 20.5/PLE 6.4/FFN 6.5/输入 2.2ms）。

**本机复现实测（MinGW gcc 16.1，-O3）**：
1. **model.bin 经 HF 下载，SHA256 与仓内钉死值精确命中**（1d8326c0…，14,912,348B）；
2. **staging_verify PASS（0 失败）**：int4 加载/绑定/前向数值校验全过（Windows 宿主）；
3. **自回归贪心生成跑通**：模型实态 Vin=32768/Vout=25353/D=96/L=6/H=4/F=66/P=128/group=128；板端预置提示词 "Once upon a time"（id 433,447,259,405）→ 64 token 生成 **481 tok/s host-x86**（ESP32 的 48.7×，240MHz 双核 vs 3.5GHz 桌面量级合理），id 流有句读结构、零即时重复；
4. 分词器资产（vocab.json/layout.json）在 HF 仓库根路径 "Entry not found"（20+ 轮）——文本级解码待资产到手（prep_assets.py+gen.c 已备好），当前以 token id 流证生成链路。

## 三、stm32-diffusion / stm32-voice（未验证，README 口径）

- stm32-diffusion：纯 C 的扩散模型实现（"stable-ish"，面向带 LCD 与 RAM 的 STM32 板）——若与 OSFY 的 3.36MB/64×64 灰度图对应，则笔记第一条的板子归属存疑（AI Vibe 报道同题材为 **RP2350** 4MB flash 内的 latent diffusion）；STM32N6570-DK/Ethos-U55 的表述以 OSFY 为唯一来源，未见项目侧证据。
- stm32-voice：纯 C 无 RTOS 的 STM32 语音助手管线（VAD/STT/TTS）——与 laos 听觉栈同题材，克隆到手后按 voicenpu 波次同款流程复现裁决。

## 四、laos 采纳裁决

| 项 | 裁决 | 理由 |
|---|---|---|
| host_verify 方法论（宿主=板端同一运行时+golden 数值对拍） | ● 已消化 | laos 驱动子进程模式同构；whistle/needle 波次已实践"单文件运行时跨平台"，本项目把该模式推到 LLM 推理核 |
| 三层内存分层（SRAM 激活/PSRAM staging/FLASH 权重 mmap） | ◐ P2 | laos npu 驱动（QNN SER）未来真机化时的内存预算设计参照 |
| PLE（25M 参数驻 flash 每 token 只读 450B） | ◐ P3 | "权重按需分页"思想对 laos 端侧大模型内存治理有启发；当前无对应能力面 |
| 无重复字节流式输出+LZ4 块解码（果蝇连接组） | ○ | 领域过远 |
| stm32-voice | 待克隆 | 听觉栈同题材，到手后单独裁决 |

## 五、附：如何在嵌入式端跑"深圳市导航"

笔记读者自然的问题。答案分三层（laos 视角）：
1. **导航本体不需要生成式模型**——路径规划是确定性算法：离线路网（深圳市 OSM 裁剪后 ~几十 MB）+ 收缩层级/CH 预处理 → Cortex-M/RISC-V 上毫秒级最短路；地图渲染 = 瓦片位图从 flash 直出 LVGL。这比跑 LLM 容易一个数量级，ESP32-S3 已有开源 LVGL 地图 demo 先例。
2. **生成式模型的正确角色是指令解析层**：语音说"导航去南山科技园"→ 端侧 ASR（laos 三通道）→ 28.9M 级 TinyLM/规则槽位抽取意图 → 调确定性导航 API。slvDev 本项目证明这一层的算力在 $8 芯片上已可行（9.88 tok/s 够槽位填充）。
3. **laos 落点**：这恰是 laos 对话控制面（wakegate→asr→knowledge/LLM→TTS）+ 既有 refiner 的标准管线——导航作为 dialog.route 的一个知识库条目即可，不需要新能力面。

## 六、工具与网络事件（复现环境记录）

- HF resolve 通道间歇可用（model.bin 一次成功）；GitHub clone 深窗（esp32-ai 在早期窗口成功）；gitee 需 `-c http.proxy=` 绕 TUN 全局代理；
- MinGW-w64 gcc 16.1（C:\mingw64）编译 llm.h 全家零改动零警告；
- fetch_model.sh 钉死 SHA256 的工程实践值得学习（laos 语料下载可引入同款 pins）。
