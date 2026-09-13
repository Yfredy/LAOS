# OSS 抓取摘要（去噪 + 精准补抓后）

**生成日期**: 2026-09-14
**干净语料文件**: `docs/research/oss/repos_raw.jsonl`

## 1. 总规模

- 合并后总数：**3724 条**（去噪保留 2153 + 补抓新增 1571）
- 噪声已剔除：见 `oss_audit.md`（共 1376 条，来自 audio-llm/voice-agent 裸词切片）
- 补抓泄漏复核：1850 条补抓中命中音频域判据 **1850 / 1850**（漏进噪声 0 条）

## 2. Star 分布

| 档位 | 数量 |
|---|---:|
| >=10000 | 107 |
| 1000-9999 | 656 |
| 100-999 | 1595 |
| <100 | 1366 |

## 3. 语言分布 top10

| 语言 | 数量 |
|---|---:|
| Python | 1696 |
| TypeScript | 322 |
| Jupyter Notebook | 248 |
| C++ | 229 |
| JavaScript | 210 |
| (none) | 182 |
| C | 161 |
| Rust | 97 |
| Swift | 85 |
| C# | 79 |

## 4. 星级 top20

| star | 仓库 | 语言 | 一句话用途 |
|---:|---|---|---|
| 165390 | huggingface/transformers | Python | 🤗 Transformers: the model-definition framework for |
| 123134 | harry0703/MoneyPrinterTurbo | Python | 利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD sho |
| 76104 | unslothai/unsloth | Python | Local UI to run and train LLMs and diffusion model |
| 64181 | FFmpeg/FFmpeg | C | Mirror of https://git.ffmpeg.org/ffmpeg.git |
| 61770 | RVC-Boss/GPT-SoVITS | Python | 1 min voice data can also be used to train a good  |
| 60131 | CorentinJ/Real-Time-Voice-Cloning | Python | Clone a voice in 5 seconds to generate arbitrary s |
| 58248 | calesthio/OpenMontage | Python | World's first open-source, agentic video productio |
| 54243 | microsoft/VibeVoice | Python | Open-Source Frontier Voice AI |
| 54074 | hugohe3/ppt-master | Python | AI turns documents or topics into real, native Pow |
| 53646 | ggml-org/whisper.cpp | C++ | Port of OpenAI's Whisper model in C/C++ |
| 53113 | jamiepine/voicebox | TypeScript | The open-source AI voice studio. Clone, dictate, c |
| 49110 | moeru-ai/airi | TypeScript | 💖🧸 Self hosted, you-owned Grok Companion, a contai |
| 49094 | mudler/LocalAI | Go | LocalAI is the open-source AI engine. Run any mode |
| 46006 | coqui-ai/TTS | Python | 🐸💬 - a deep learning toolkit for Text-to-Speech, b |
| 39833 | 2noise/ChatTTS | Python | A generative speech model for daily dialogue. |
| 37512 | myshell-ai/OpenVoice | Python | Instant voice cloning by MIT and MyShell. Audio fo |
| 37053 | OpenBMB/VoxCPM | Python | VoxCPM2: Tokenizer-Free TTS for Multilingual Speec |
| 36965 | mpv-player/mpv | C | 🎥 Command line media player |
| 36930 | google-ai-edge/mediapipe | C++ | Cross-platform, customizable ML solutions for live |
| 36910 | babysor/MockingBird | Python | 🚀Clone a voice in 5 seconds to generate arbitrary  |

## 5. 补抓说明

补抓用 `crawl_oss_repos.search()` 跑 10 个引号短语 / `topic:` 查询（每 query 2 页，遵守 search 10/min 限速），共取回 1850 条增量，并入后净增 **1571** 条。查询清单：
  - `"audio language model"`
  - `"speech emotion recognition"`
  - `"voice activity detection"`
  - `"voice agent"`
  - `"realtime voice"`
  - `topic:audio-classification`
  - `topic:speech-synthesis`
  - `topic:keyword-spotting`
  - `topic:voice-ai`
  - `topic:sound`

## 6. 许可信息缺失说明（重要）

- 干净语料中 **2801 / 3724** 条缺失 `license` 字段。
- 缺失来自两部分：(a) 原 `oss_corpus.json` 语料本身无 license 字段（已置空，未编造）；(b) 补抓条目经 search 端点已带 license，但部分为 `NOASSERTION`。
- 报告与榜单中**不得**把缺失当「无许可」，需在 Task 4 报告中标注「许可信息需另行核实，非法律意见」。

## 7. 衔接

- 去噪审计明细：`oss_audit.md`（各切片相关率、剔除判据、被剔除高星仓库列表）。
- 下一步（Task 3）：对 `repos_raw.jsonl` 分类打标 + laos 四段漏斗适配映射。