# 音频 / AI / Agent 开源项目星标全景

> laos 四段漏斗选型调研 · 最终报告（Task 4）

- **抓取日期**: 2026-09-14（GitHub Search API 未认证快照，star 数为时变量）
- **语料规模**: 3724 条干净仓库（去噪 2153 + 引号短语补抓 1571）
- **分类数**: 15 类（可多标签）
- **laos 适配**: core 132 ｜ ref 2864 ｜ unrelated 728

## 0 · 摘要（TL;DR）

- 遍历 **3724** 个音频 / 语音 AI / 语音·多模态 Agent 方向高星开源项目，覆盖 **15** 个功能类别。
- 真正能进 laos 四段漏斗的 **core 仅 132 个（3.5%）**；
  76.9% 是「参考/借鉴」级（ref），19.5% 与漏斗无关（unrelated）。
- core 集中于四段漏斗的 **①常驻检测（VAD/唤醒词）** 与 **③即时蒸馏（ASR/降噪/声音事件）**；
  ②触发捕获多用通用采集库（FFmpeg/pyaudio 类），④原音频即焚是策略而非第三方组件。
- **许可字段缺失 2801/3724（75.2%）**，core 仅排除云 API wrapper，
  不保证全部可商用；落地前须逐条核 SPDX（见第 6 节）。

## 1 · 方法与限额说明

数据来自 GitHub Search API（`search/repositories` 端点，未认证），遵守实测限额：

- `search` 限额 **10 次/分钟** → 每请求 `sleep 7`；`core` 限额 60 次/小时且常为 0 → **只用 search 端点**，不补字段。
- search 端点单次响应已含 `stars`/`description`/`language`/`license.spdx_id`/`html_url`/`topics`/`archived` 等全部所需字段。
- 单 query 最多返回 **1000 条**，按 stars 降序取 top，不追求全量。
- 统一加 `fork:false`；落盘后剔除 `archived:true`。
- 去噪纪律（Task 2）：8 个 `topic:` 切片 100% 相关直接复用；`audio-llm`/`voice-agent` 两裸关键词切片相关率仅 20%/16%，逐条重筛剔除 1376 条噪声（含 `public-apis` 479k★、`awesome-python` 320k★），再用引号短语补抓找回真相关项目。
- 抓取时间 `2026-09-14` 落盘；star 为快照，可能已过时。

## 2 · 总榜 Top 40（star 降序）

| # | star | 仓库 | 语言 | 许可 | 一句话用途 |
|---|---:|---|---|---|---|
| 1 | 165,390 | `huggingface/transformers` | Python | - | 🤗 Transformers: the model-definition framework for state-of… |
| 2 | 123,134 | `harry0703/MoneyPrinterTurbo` | Python | - | 利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short videos… |
| 3 | 76,104 | `unslothai/unsloth` | Python | - | Local UI to run and train LLMs and diffusion models. Suppor… |
| 4 | 64,181 | `FFmpeg/FFmpeg` | C | - | Mirror of https://git.ffmpeg.org/ffmpeg.git |
| 5 | 61,770 | `RVC-Boss/GPT-SoVITS` | Python | - | 1 min voice data can also be used to train a good TTS model… |
| 6 | 60,131 | `CorentinJ/Real-Time-Voice-Cloning` | Python | - | Clone a voice in 5 seconds to generate arbitrary speech in … |
| 7 | 58,248 | `calesthio/OpenMontage` | Python | - | World&#x27;s first open-source, agentic video production system.… |
| 8 | 54,243 | `microsoft/VibeVoice` | Python | - | Open-Source Frontier Voice AI |
| 9 | 54,074 | `hugohe3/ppt-master` | Python | - | AI turns documents or topics into real, native PowerPoint d… |
| 10 | 53,646 | `ggml-org/whisper.cpp` | C++ | - | Port of OpenAI&#x27;s Whisper model in C/C++ |
| 11 | 53,113 | `jamiepine/voicebox` | TypeScript | - | The open-source AI voice studio. Clone, dictate, create. |
| 12 | 49,110 | `moeru-ai/airi` | TypeScript | - | 💖🧸 Self hosted, you-owned Grok Companion, a container of so… |
| 13 | 49,094 | `mudler/LocalAI` | Go | - | LocalAI is the open-source AI engine. Run any model - LLMs,… |
| 14 | 46,006 | `coqui-ai/TTS` | Python | - | 🐸💬 - a deep learning toolkit for Text-to-Speech, battle-tes… |
| 15 | 39,833 | `2noise/ChatTTS` | Python | - | A generative speech model for daily dialogue. |
| 16 | 37,512 | `myshell-ai/OpenVoice` | Python | - | Instant voice cloning by MIT and MyShell. Audio foundation … |
| 17 | 37,053 | `OpenBMB/VoxCPM` | Python | - | VoxCPM2: Tokenizer-Free TTS for Multilingual Speech Generat… |
| 18 | 36,965 | `mpv-player/mpv` | C | - | 🎥 Command line media player |
| 19 | 36,930 | `google-ai-edge/mediapipe` | C++ | - | Cross-platform, customizable ML solutions for live and stre… |
| 20 | 36,910 | `babysor/MockingBird` | Python | - | 🚀Clone a voice in 5 seconds to generate arbitrary speech in… |
| 21 | 32,671 | `fishaudio/fish-speech` | Python | - | SOTA Open Source TTS |
| 22 | 29,238 | `ossrs/srs` | C++ | - | SRS is a simple, high-performance, AI-driven real-time medi… |
| 23 | 28,442 | `deezer/spleeter` | Python | - | Deezer source separation library including pretrained model… |
| 24 | 28,110 | `svc-develop-team/so-vits-svc` | Python | - | SoftVC VITS Singing Voice Conversion |
| 25 | 28,076 | `ATH-MaaS/Pixelle-Video` | Python | - | 🚀 AI 全自动短视频引擎 | AI Fully Automated Short Video Engine |
| 26 | 28,001 | `mastra-ai/mastra` | TypeScript | - | Mastra is the modern TypeScript framework for AI-powered ap… |
| 27 | 27,202 | `Fosowl/agenticSeek` | Python | - | Fully Local Manus AI. No APIs, No $200 monthly bills. Enjoy… |
| 28 | 26,915 | `Igglybuff/awesome-piracy` | HTML | - | A curated list of awesome warez and piracy links |
| 29 | 26,776 | `mozilla/DeepSpeech` | C++ | - | DeepSpeech is an open source embedded (offline, on-device) … |
| 30 | 26,403 | `resemble-ai/chatterbox` | Python | - | SoTA open-source TTS |
| 31 | 26,219 | `Anjok07/ultimatevocalremovergui` | Python | - | GUI for a Vocal Remover that uses Deep Neural Networks. |
| 32 | 26,113 | `debpalash/VoiceStudio` | Python | - | VoiceStudio is the open-source, fully-local ElevenLabs alte… |
| 33 | 25,960 | `mozilla-ai/llamafile` | C++ | - | Distribute and run LLMs with a single file. |
| 34 | 25,376 | `SYSTRAN/faster-whisper` | Python | - | Faster Whisper transcription with CTranslate2 |
| 35 | 25,342 | `goldfire/howler.js` | JavaScript | - | Javascript audio library for the modern web. |
| 36 | 24,307 | `readest/readest` | TypeScript | - | Readest is a modern, feature-rich ebook reader designed for… |
| 37 | 24,018 | `m-bain/whisperX` | Python | - | WhisperX:  Automatic Speech Recognition with Word-level Tim… |
| 38 | 23,987 | `processing/p5.js` | JavaScript | LGPL-2.1 | p5.js is a client-side JS platform that empowers artists, d… |
| 39 | 23,935 | `index-tts/index-tts` | Python | - | An Industrial-Level Controllable and Efficient Zero-Shot Te… |
| 40 | 23,771 | `slopus/happy` | TypeScript | - | Mobile and Web client for Codex and Claude Code, with realt… |

## 3 · 分类榜（15 类，各 Top 12）

> 说明：**实际统计得到 15 个类别标签**，而非背景简报所述的「14 类」——多出的 `ml-framework`（540 条）与 `agent-llm`（126 条）在分类器规则中被单独命中。下表以真实 15 类为准。

### 3.0 类别总览

| 类别 | 条数 | star 中位数 |
|---|---:|---:|
| asr | 1206 | 162 |
| tts | 837 | 295 |
| agent | 696 | 83 |
| ml-framework | 540 | 191 |
| kws-vad | 367 | 15 |
| dsp-lib | 303 | 339 |
| enhance | 170 | 177 |
| serving | 161 | 90 |
| dataset | 151 | 31 |
| agent-llm | 126 | 203 |
| music | 120 | 600 |
| audio-llm | 118 | 153 |
| speaker | 59 | 95 |
| codec | 57 | 501 |
| aed | 48 | 14 |

### 3.1 asr（1206 个，中位 162★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 165,390 | `huggingface/transformers` | - | 🤗 Transformers: the model-definition framework for stat… |
| 53,646 | `ggml-org/whisper.cpp` | - | Port of OpenAI&#x27;s Whisper model in C/C++ |
| 53,113 | `jamiepine/voicebox` | - | The open-source AI voice studio. Clone, dictate, create. |
| 26,776 | `mozilla/DeepSpeech` | - | DeepSpeech is an open source embedded (offline, on-devi… |
| 26,113 | `debpalash/VoiceStudio` | - | VoiceStudio is the open-source, fully-local ElevenLabs … |
| 25,960 | `mozilla-ai/llamafile` | - | Distribute and run LLMs with a single file. |
| 25,376 | `SYSTRAN/faster-whisper` | - | Faster Whisper transcription with CTranslate2 |
| 24,018 | `m-bain/whisperX` | - | WhisperX:  Automatic Speech Recognition with Word-level… |
| 21,557 | `screenpipe/screenpipe` | - | YC (S26) | Open Computer History | Record your screen c… |
| 20,306 | `modelscope/FunASR` | - | Open-source speech recognition toolkit for training, in… |
| 19,434 | `pot-app/pot-desktop` | - | 🌈一个跨平台的划词翻译和OCR软件 | A cross-platform software for text … |
| 18,997 | `jianchang512/pyvideotrans` | - | Translate the video from one language to another and em… |

### 3.2 tts（837 个，中位 295★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 123,134 | `harry0703/MoneyPrinterTurbo` | - | 利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short vi… |
| 76,104 | `unslothai/unsloth` | - | Local UI to run and train LLMs and diffusion models. Su… |
| 61,770 | `RVC-Boss/GPT-SoVITS` | - | 1 min voice data can also be used to train a good TTS m… |
| 60,131 | `CorentinJ/Real-Time-Voice-Cloning` | - | Clone a voice in 5 seconds to generate arbitrary speech… |
| 58,248 | `calesthio/OpenMontage` | - | World&#x27;s first open-source, agentic video production sys… |
| 54,243 | `microsoft/VibeVoice` | - | Open-Source Frontier Voice AI |
| 53,113 | `jamiepine/voicebox` | - | The open-source AI voice studio. Clone, dictate, create. |
| 49,094 | `mudler/LocalAI` | - | LocalAI is the open-source AI engine. Run any model - L… |
| 46,006 | `coqui-ai/TTS` | - | 🐸💬 - a deep learning toolkit for Text-to-Speech, battle… |
| 39,833 | `2noise/ChatTTS` | - | A generative speech model for daily dialogue. |
| 37,512 | `myshell-ai/OpenVoice` | - | Instant voice cloning by MIT and MyShell. Audio foundat… |
| 37,053 | `OpenBMB/VoxCPM` | - | VoxCPM2: Tokenizer-Free TTS for Multilingual Speech Gen… |

### 3.3 agent（696 个，中位 83★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 76,104 | `unslothai/unsloth` | - | Local UI to run and train LLMs and diffusion models. Su… |
| 58,248 | `calesthio/OpenMontage` | - | World&#x27;s first open-source, agentic video production sys… |
| 54,074 | `hugohe3/ppt-master` | - | AI turns documents or topics into real, native PowerPoi… |
| 49,110 | `moeru-ai/airi` | - | 💖🧸 Self hosted, you-owned Grok Companion, a container o… |
| 39,833 | `2noise/ChatTTS` | - | A generative speech model for daily dialogue. |
| 27,202 | `Fosowl/agenticSeek` | - | Fully Local Manus AI. No APIs, No $200 monthly bills. E… |
| 23,771 | `slopus/happy` | - | Mobile and Web client for Codex and Claude Code, with r… |
| 21,557 | `screenpipe/screenpipe` | - | YC (S26) | Open Computer History | Record your screen c… |
| 21,324 | `RasaHQ/rasa` | - | 💬   Open source machine learning framework to automate … |
| 20,976 | `w-okada/voice-changer` | NOASSERTION | リアルタイムボイスチェンジャー Realtime Voice Changer |
| 19,902 | `pydantic/pydantic-ai` | - | How Python does AI. Agents, realtime voice, image gener… |
| 17,507 | `leon-ai/leon` | - | 🧠 Leon is your open-source personal assistant. |

### 3.4 ml-framework（540 个，中位 191★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 165,390 | `huggingface/transformers` | - | 🤗 Transformers: the model-definition framework for stat… |
| 60,131 | `CorentinJ/Real-Time-Voice-Cloning` | - | Clone a voice in 5 seconds to generate arbitrary speech… |
| 46,006 | `coqui-ai/TTS` | - | 🐸💬 - a deep learning toolkit for Text-to-Speech, battle… |
| 37,053 | `OpenBMB/VoxCPM` | - | VoxCPM2: Tokenizer-Free TTS for Multilingual Speech Gen… |
| 36,910 | `babysor/MockingBird` | - | 🚀Clone a voice in 5 seconds to generate arbitrary speec… |
| 28,442 | `deezer/spleeter` | - | Deezer source separation library including pretrained m… |
| 28,110 | `svc-develop-team/so-vits-svc` | - | SoftVC VITS Singing Voice Conversion |
| 26,776 | `mozilla/DeepSpeech` | - | DeepSpeech is an open source embedded (offline, on-devi… |
| 26,219 | `Anjok07/ultimatevocalremovergui` | - | GUI for a Vocal Remover that uses Deep Neural Networks. |
| 26,113 | `debpalash/VoiceStudio` | - | VoiceStudio is the open-source, fully-local ElevenLabs … |
| 21,967 | `huggingface/datasets` | - | 🤗 The largest hub of ready-to-use datasets for AI model… |
| 20,306 | `modelscope/FunASR` | - | Open-source speech recognition toolkit for training, in… |

### 3.5 kws-vad（367 个，中位 15★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 20,306 | `modelscope/FunASR` | - | Open-source speech recognition toolkit for training, in… |
| 14,747 | `k2-fsa/sherpa-onnx` | - | Speech-to-text, text-to-speech, speaker diarization, sp… |
| 10,205 | `snakers4/silero-vad` | - | Silero VAD: pre-trained enterprise-grade Voice Activity… |
| 10,127 | `KoljaB/RealtimeSTT` | MIT | A robust, efficient, low-latency speech-to-text library… |
| 7,870 | `smacke/ffsubsync` | - | Automagically synchronize subtitles with video. |
| 4,935 | `Picovoice/porcupine` | - | On-device wake word detection powered by deep learning |
| 4,342 | `cmusphinx/pocketsphinx` | - | A small speech recognizer |
| 2,759 | `FluidInference/FluidAudio` | - | Frontier CoreML audio models in your apps — text-to-spe… |
| 2,664 | `0xShug0/audio.cpp` | - | An all-in-one, pure C++ inference engine for audio mode… |
| 2,264 | `TEN-framework/ten-vad` | - | Voice Activity Detector (VAD) : low-latency, high-perfo… |
| 2,236 | `meizhong986/WhisperJAV` | - | ASR/STT subtitle generator. Uses Qwen3-ASR, local LLM, … |
| 1,783 | `k2-fsa/sherpa-ncnn` | - | Real-time speech recognition and voice activity detecti… |

### 3.6 dsp-lib（303 个，中位 339★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 123,134 | `harry0703/MoneyPrinterTurbo` | - | 利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short vi… |
| 64,181 | `FFmpeg/FFmpeg` | - | Mirror of https://git.ffmpeg.org/ffmpeg.git |
| 58,248 | `calesthio/OpenMontage` | - | World&#x27;s first open-source, agentic video production sys… |
| 39,833 | `2noise/ChatTTS` | - | A generative speech model for daily dialogue. |
| 36,965 | `mpv-player/mpv` | - | 🎥 Command line media player |
| 29,238 | `ossrs/srs` | - | SRS is a simple, high-performance, AI-driven real-time … |
| 25,342 | `goldfire/howler.js` | - | Javascript audio library for the modern web. |
| 20,887 | `livekit/livekit` | - | End-to-end realtime stack for connecting humans and AI |
| 18,688 | `alyssaxuu/screenity` | - | The free and privacy-friendly screen recorder with no l… |
| 17,801 | `ffmpegwasm/ffmpeg.wasm` | - | FFmpeg for browser, powered by WebAssembly |
| 16,775 | `pion/webrtc` | - | Pure Go implementation of the WebRTC API |
| 16,327 | `leandromoreira/digital_video_introduction` | - | A hands-on introduction to video technology: image, vid… |

### 3.7 enhance（170 个，中位 177★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 28,442 | `deezer/spleeter` | - | Deezer source separation library including pretrained m… |
| 26,219 | `Anjok07/ultimatevocalremovergui` | - | GUI for a Vocal Remover that uses Deep Neural Networks. |
| 14,747 | `k2-fsa/sherpa-onnx` | - | Speech-to-text, text-to-speech, speaker diarization, sp… |
| 11,819 | `speechbrain/speechbrain` | - | A PyTorch-based Speech Toolkit |
| 9,955 | `espnet/espnet` | - | End-to-End Speech Processing Toolkit |
| 7,930 | `adithya-s-k/omniparse` | - | Ingest, parse, and optimize any data format ➡️ from doc… |
| 5,834 | `xiph/rnnoise` | - | Recurrent neural network for audio noise reduction |
| 4,703 | `Rikorose/DeepFilterNet` | - | Noise supression using deep filtering |
| 4,484 | `modelscope/ClearerVoice-Studio` | - | An AI-Powered Speech Processing Toolkit and Open Source… |
| 3,165 | `stemrollerapp/stemroller` | - | Isolate vocals, drums, bass, and other instrumental ste… |
| 2,584 | `asteroid-team/asteroid` | - | The PyTorch-based audio source separation toolkit for r… |
| 2,422 | `resemble-ai/resemble-enhance` | - | AI powered speech denoising and enhancement |

### 3.8 serving（161 个，中位 90★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 36,930 | `google-ai-edge/mediapipe` | - | Cross-platform, customizable ML solutions for live and … |
| 23,597 | `QwenAudio/CosyVoice` | - | Multi-lingual large voice generation model, providing i… |
| 20,306 | `modelscope/FunASR` | - | Open-source speech recognition toolkit for training, in… |
| 14,844 | `NVIDIA/DeepLearningExamples` | - | State-of-the-Art Deep Learning scripts organized by mod… |
| 14,747 | `k2-fsa/sherpa-onnx` | - | Speech-to-text, text-to-speech, speaker diarization, sp… |
| 13,775 | `supertone-oss-archive/supertonic` | - | Lightning-Fast, On-Device, Multilingual TTS — running n… |
| 10,842 | `openvinotoolkit/openvino` | - | OpenVINO™ is an open source toolkit for optimizing and … |
| 10,205 | `snakers4/silero-vad` | - | Silero VAD: pre-trained enterprise-grade Voice Activity… |
| 9,566 | `xorbitsai/inference` | - | Swap GPT for any LLM by changing a single line of code.… |
| 6,261 | `PaddlePaddle/PaddleX` | - | All-in-One Development Tool based on PaddlePaddle |
| 6,008 | `cactus-compute/cactus` | - | Quantization, kernels, runtime and inference engine for… |
| 5,759 | `NVIDIA/DALI` | - | A GPU-accelerated library containing highly optimized b… |

### 3.9 dataset（151 个，中位 31★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 21,967 | `huggingface/datasets` | - | 🤗 The largest hub of ready-to-use datasets for AI model… |
| 10,171 | `mozilla/TTS` | - | :robot: :speech_balloon: Deep learning for Text to Spee… |
| 10,001 | `yzhao062/pyod` | - | A Python library for anomaly detection across tabular, … |
| 4,402 | `EvolvingLMMs-Lab/lmms-eval` | - | One-for-All Multimodal Evaluation Toolkit Across Text, … |
| 3,130 | `zzw922cn/awesome-speech-recognition-speech-synthesis-papers` | - | Automatic Speech Recognition (ASR), Speaker Verificatio… |
| 2,832 | `zzw922cn/Automatic_Speech_Recognition` | - | End-to-end Automatic Speech Recognition for Madarian an… |
| 2,426 | `alan-ai/alan-sdk-web` | - | The Self-Coding System for Your App — Alan AI SDK for W… |
| 2,227 | `jim-schwoebel/voice_datasets` | - | 🔊 A comprehensive list of open-source datasets for voic… |
| 1,867 | `karolpiczak/ESC-50` | - | ESC-50: Dataset for Environmental Sound Classification |
| 1,113 | `xid32/SoundMind` | MIT | We introduce the Audio Logical Reasoning (ALR) dataset,… |
| 867 | `jtkim-kaist/VAD` | - | Voice activity detection (VAD) toolkit including DNN, b… |
| 729 | `thorstenMueller/Thorsten-Voice` | - | Thorsten-Voice: A free to use, offline working, high qu… |

### 3.10 agent-llm（126 个，中位 203★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 76,104 | `unslothai/unsloth` | - | Local UI to run and train LLMs and diffusion models. Su… |
| 39,833 | `2noise/ChatTTS` | - | A generative speech model for daily dialogue. |
| 27,202 | `Fosowl/agenticSeek` | - | Fully Local Manus AI. No APIs, No $200 monthly bills. E… |
| 21,557 | `screenpipe/screenpipe` | - | YC (S26) | Open Computer History | Record your screen c… |
| 19,902 | `pydantic/pydantic-ai` | - | How Python does AI. Agents, realtime voice, image gener… |
| 13,724 | `Open-LLM-VTuber/Open-LLM-VTuber` | - | Talk to any LLM with hands-free voice interaction, voic… |
| 10,606 | `VoltAgent/voltagent` | - | AI Agent Engineering Platform built on an Open Source T… |
| 8,801 | `fishaudio/Bert-VITS2` | - | vits2 backbone with multilingual-bert |
| 6,336 | `canopyai/Orpheus-TTS` | - | Towards Human-Sounding Speech |
| 4,095 | `OpenMOSS/MOSS-TTS` | - | An open-source model family for long-form speech, dialo… |
| 3,772 | `PeterH0323/Streamer-Sales` | - | Streamer-Sales 销冠 —— 卖货主播 LLM 大模型🛒🎁，一个能够根据给定的商品特点从激发用户购… |
| 3,754 | `aiming-lab/SimpleMem` | - | SimpleMem: Efficient Lifelong Memory for LLM Agents — T… |

### 3.11 music（120 个，中位 600★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 28,110 | `svc-develop-team/so-vits-svc` | - | SoftVC VITS Singing Voice Conversion |
| 12,678 | `ace-step/ACE-Step-1.5` | - | The most powerful local music generation model that out… |
| 11,459 | `AudioKit/AudioKit` | - | Audio synthesis, processing, &amp; analysis platform for iO… |
| 10,288 | `open-mmlab/Amphion` | MIT | Amphion (/æmˈfaɪən/) is a toolkit for Audio, Music, and… |
| 9,955 | `espnet/espnet` | - | End-to-End Speech Processing Toolkit |
| 7,141 | `mixxxdj/mixxx` | - | Mixxx is Free DJ software that gives you everything you… |
| 5,601 | `cgzirim/seek-tune` | - | An implementation of Shazam&#x27;s song recognition algorith… |
| 5,564 | `spotify/basic-pitch` | - | A lightweight yet powerful audio-to-MIDI converter with… |
| 5,280 | `Ardour/ardour` | - | Mirror of Ardour Source Code |
| 4,872 | `fspecii/ace-step-ui` | - | 🎵 The Ultimate Open Source Suno Alternative - Professio… |
| 4,859 | `MoonInTheRiver/DiffSinger` | - | DiffSinger: Singing Voice Synthesis via Shallow Diffusi… |
| 4,824 | `ace-step/ACE-Step` | - | ACE-Step: A Step Towards Music Generation Foundation Mo… |

### 3.12 audio-llm（118 个，中位 153★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 39,833 | `2noise/ChatTTS` | - | A generative speech model for daily dialogue. |
| 12,683 | `PaddlePaddle/PaddleSpeech` | - | Easy-to-use Speech Toolkit including Self-Supervised Le… |
| 10,169 | `AIGC-Audio/AudioGPT` | - | AudioGPT: Understanding and Generating Speech, Music, S… |
| 8,801 | `fishaudio/Bert-VITS2` | - | vits2 backbone with multilingual-bert |
| 7,879 | `Blaizzy/mlx-audio` | - | A text-to-speech (TTS), speech-to-text (STT) and speech… |
| 6,336 | `canopyai/Orpheus-TTS` | - | Towards Human-Sounding Speech |
| 4,337 | `jitsi/jitsi` | - | Jitsi is an audio/video and chat communicator that supp… |
| 4,274 | `collabora/WhisperLive` | - | A nearly-live implementation of OpenAI&#x27;s Whisper. |
| 4,095 | `OpenMOSS/MOSS-TTS` | - | An open-source model family for long-form speech, dialo… |
| 4,010 | `QwenLM/Qwen3-Omni` | - | Qwen3-omni is a natively end-to-end, omni-modal LLM dev… |
| 3,692 | `SakiRinn/LiveCaptions-Translator` | - | Lightweight and powerful real-time audio/speech transla… |
| 3,576 | `gpt-omni/mini-omni` | - | open-source multimodal large language model that can he… |

### 3.13 speaker（59 个，中位 95★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 20,306 | `modelscope/FunASR` | - | Open-source speech recognition toolkit for training, in… |
| 14,747 | `k2-fsa/sherpa-onnx` | - | Speech-to-text, text-to-speech, speaker diarization, sp… |
| 12,683 | `PaddlePaddle/PaddleSpeech` | - | Easy-to-use Speech Toolkit including Self-Supervised Le… |
| 11,030 | `QuentinFuxa/WhisperLiveKit` | - | Real-time, local speech-to-text with streaming ASR, spe… |
| 10,544 | `pyannote/pyannote-audio` | - | Neural building blocks for speaker diarization: speech … |
| 5,644 | `MahmoudAshraf97/whisper-diarization` | - | Automatic Speech Recognition with Speaker Diarization b… |
| 3,134 | `modelscope/3D-Speaker` | - | A Repository for Single- and Multi-modal Speaker Verifi… |
| 3,130 | `zzw922cn/awesome-speech-recognition-speech-synthesis-papers` | - | Automatic Speech Recognition (ASR), Speaker Verificatio… |
| 2,759 | `FluidInference/FluidAudio` | - | Frontier CoreML audio models in your apps — text-to-spe… |
| 1,958 | `OpenMOSS/MOSS-Transcribe-Diarize` | - | A 0.9B model for long-form transcription in 50+ languag… |
| 1,899 | `wq2012/awesome-diarization` | - | A curated list of awesome Speaker Diarization papers, l… |
| 1,588 | `google/uis-rnn` | - | This is the library for the Unbounded Interleaved-State… |

### 3.14 codec（57 个，中位 501★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 29,238 | `ossrs/srs` | - | SRS is a simple, high-performance, AI-driven real-time … |
| 16,327 | `leandromoreira/digital_video_introduction` | - | A hands-on introduction to video technology: image, vid… |
| 4,958 | `Anil-matcha/AI-Youtube-Shorts-Generator` | - | Open-source alternative to Opus Clip, Vidyo.ai, Klap &amp; … |
| 3,754 | `aiming-lab/SimpleMem` | - | SimpleMem: Efficient Lifelong Memory for LLM Agents — T… |
| 3,315 | `xiph/opus` | - | Modern audio compression for the internet. |
| 2,501 | `axiomatic-systems/Bento4` | - | Full-featured MP4 format, MPEG DASH, HLS, CMAF SDK and … |
| 2,414 | `xiph/flac` | - | Free Lossless Audio Codec |
| 2,253 | `vgmstream/vgmstream` | - | vgmstream - A library for playback of various streamed … |
| 1,961 | `enzo1982/freac` | - | The fre:ac audio converter project |
| 1,950 | `lieff/minimp3` | - | Minimalistic MP3 decoder single header library |
| 1,857 | `descriptinc/descript-audio-codec` | - | State-of-the-art audio codec with 90x compression facto… |
| 1,569 | `eibols/ffmpeg_batch` | - | FFmpeg Batch AV Converter |

### 3.15 aed（48 个，中位 14★）

| star | 仓库 | 许可 | 一句话用途 |
|---:|---|---|---|
| 9,299 | `QwenAudio/SenseVoice` | - | Open-source SenseVoiceSmall model for Mandarin, Cantone… |
| 586 | `seth814/Audio-Classification` | MIT | Code for YouTube series: Deep Learning for Audio Classi… |
| 528 | `FireRedTeam/FireRedVAD` | Apache-2.0 | A SOTA Industrial-Grade Voice Activity Detection &amp; Audi… |
| 519 | `towhee-io/examples` | Apache-2.0 | Analyze the unstructured data with Towhee, such as reve… |
| 508 | `gkonovalov/android-vad` | - | Android Voice Activity Detection (VAD) library. Support… |
| 313 | `lRomul/argus-freesound` | - | Kaggle | 1st place solution for Freesound Audio Tagging… |
| 277 | `m3hrdadfi/soxan` | - | Wav2Vec for speech recognition, classification, and aud… |
| 165 | `Ali-hey-0/audio-ai-field-guide` | - | A mental-model-first field guide to Audio AI — from raw… |
| 151 | `YuanGongND/psla` | BSD-3-Clause | Code for the TASLP paper &quot;PSLA: Improving Audio Tagging… |
| 137 | `micah5/pyAudioClassification` | MIT | 🎶 dead simple audio classification |
| 131 | `luuil/Tensorflow-Audio-Classification` | Apache-2.0 | Audio classification with VGGish as feature extractor i… |
| 107 | `CVxTz/audio_classification` | MIT | CNN 1D vs 2D audio classification |

## 4 · laos 适配结论（core 落地清单）

共 **132** 个 `laos_fit=core`，按 stars 降序列出。漏斗落点取自分类器写入的 `laos_stage` 字段；
端侧可行性（C1）以「命中 on-device 信号」为判据（已在 core 判定中通过），具体功耗档位见 `docs/research/speech-emotion/04-edge-deployment.md` 的 A/B 档口径；许可（C3）见第 6 节缺失说明。

**漏斗落点分布（core 组件去重计数，一个组件可落多段）：**

- ①常驻检测：42 个组件
- ②触发捕获：25 个组件
- ③即时蒸馏：117 个组件
- ④原音频即焚：0 个组件

**core 落地清单（全量，132 个）：**

| star | 仓库 | 类别 | 漏斗落点(laos_stage) | 许可 |
|---:|---|---|---|---|
| 64,181 | `FFmpeg/FFmpeg` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 53,646 | `ggml-org/whisper.cpp` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 26,776 | `mozilla/DeepSpeech` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 20,306 | `modelscope/FunASR` | asr,kws-vad,speaker,serving,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 15,126 | `alphacep/vosk-api` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 14,747 | `k2-fsa/sherpa-onnx` | asr,tts,enhance,kws-vad,speaker,serving | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(降噪/分离前置) / ①常驻检测(VAD/唤醒词能量门) | - |
| 12,800 | `abus-aikorea/voice-pro` | asr,tts,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |
| 12,683 | `PaddlePaddle/PaddleSpeech` | asr,tts,audio-llm,speaker | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | - |
| 11,030 | `QuentinFuxa/WhisperLiveKit` | asr,speaker,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 10,205 | `snakers4/silero-vad` | asr,kws-vad,serving,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 10,127 | `KoljaB/RealtimeSTT` | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | MIT |
| 9,299 | `QwenAudio/SenseVoice` | asr,aed,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(声音事件/场景理解) | - |
| 6,300 | `modelscope/FunClip` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 6,099 | `snakers4/silero-models` | asr,tts,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 6,008 | `cactus-compute/cactus` | asr,serving | ③即时蒸馏(ASR 转写写记忆) | - |
| 5,834 | `xiph/rnnoise` | enhance | ③即时蒸馏(降噪/分离前置) | - |
| 5,632 | `xiangyuecn/Recorder` | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |
| 4,623 | `gradio-app/fastrtc` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 4,342 | `cmusphinx/pocketsphinx` | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 4,122 | `umlx5h/LLPlayer` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 3,692 | `SakiRinn/LiveCaptions-Translator` | asr,audio-llm | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | - |
| 3,671 | `ufal/whisper_streaming` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 3,576 | `gpt-omni/mini-omni` | audio-llm,agent | ③即时蒸馏(多模态理解/结构化) | - |
| 3,125 | `AutoArk/GPA` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 3,086 | `off-grid-ai/OGAM` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 2,565 | `QwenAudio/qwen-audio-agent` | asr,tts,agent,serving | ③即时蒸馏(ASR 转写写记忆) | - |
| 2,536 | `VITA-MLLM/VITA` | audio-llm,agent-llm | ③即时蒸馏(多模态理解/结构化) | - |
| 2,381 | `pschatzmann/arduino-audio-tools` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 2,364 | `filoe/cscore` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 2,264 | `TEN-framework/ten-vad` | asr,kws-vad,agent | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 2,024 | `juanmc2005/diart` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,914 | `handy-computer/transcribe.cpp` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,913 | `krzemienski/awesome-video` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 1,783 | `k2-fsa/sherpa-ncnn` | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 1,765 | `wwbin2017/bailing` | asr,tts,agent,agent-llm | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,747 | `antirez/voxtral.c` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,606 | `royshil/obs-localvocal` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,535 | `QwenAudio/Fun-ASR` | asr,enhance,serving,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(降噪/分离前置) | - |
| 1,475 | `silverstein/minutes` | asr,agent | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,474 | `DicioTeam/dicio-android` | asr,tts,kws-vad,agent | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 1,365 | `elevenyellow/handcrafted-persona-engine` | asr,tts,agent | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,361 | `mbailey/voicemode` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,318 | `HG-ha/MTools` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,306 | `Henry-23/VideoChat` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,289 | `ictnlp/StreamSpeech` | asr,tts,audio-llm,enhance | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) / ③即时蒸馏(降噪/分离前置) | - |
| 1,253 | `roc-streaming/roc-toolkit` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 1,174 | `sgl-project/sglang-omni` | asr,tts,audio-llm,serving,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | - |
| 1,116 | `ardha27/AI-Waifu-Vtuber` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,107 | `nobodywho-ooo/nobodywho` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,094 | `alumae/kaldi-gstreamer-server` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 1,057 | `introlab/odas` | enhance | ③即时蒸馏(降噪/分离前置) | MIT |
| 1,051 | `MattMoony/figaro` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 1,010 | `TensorSpeech/TensorFlowASR` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 988 | `k2-fsa/sherpa` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 964 | `MycroftAI/mycroft-precise` | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 869 | `yeyupiaoling/PPASR` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 823 | `VocaHQ/vocalinux` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 820 | `TrevorS/voxtral-mini-realtime-rs` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 814 | `AlphaAvatar/AlphaAvatar` | audio-llm,agent,agent-llm | ③即时蒸馏(多模态理解/结构化) | - |
| 805 | `lobehub/lobe-tts` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 802 | `mybigday/whisper.rn` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 763 | `fluxions-ai/vui` | asr,tts,audio-llm,agent,dsp-lib,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) / ①②采集与能量门(录音/读取/预处理) | - |
| 755 | `amanvirparhar/chaplin` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 751 | `Macoron/whisper.unity` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 746 | `soupslurpr/Transcribro` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 742 | `breizhn/DTLN` | enhance,dsp-lib,ml-framework | ③即时蒸馏(降噪/分离前置) / ①②采集与能量门(录音/读取/预处理) | - |
| 739 | `Xiaobin-Rong/gtcrn` | enhance | ③即时蒸馏(降噪/分离前置) | - |
| 726 | `rapidaai/voice-ai` | asr,tts,kws-vad,agent | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | NOASSERTION |
| 721 | `omeryusufyagci/fast-music-remover` | enhance,dsp-lib | ③即时蒸馏(降噪/分离前置) / ①②采集与能量门(录音/读取/预处理) | - |
| 705 | `GRVYDEV/S.A.T.U.R.D.A.Y` | asr,codec,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |
| 689 | `vilassn/whisper_android` | asr,tts,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 680 | `iceychris/LibreASR` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 650 | `TheDeathDragon/LiveTranslate` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 636 | `woheller69/whisperIME` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 627 | `CrispStrobe/CrispASR` | asr,tts,serving | ③即时蒸馏(ASR 转写写记忆) | - |
| 614 | `reriiasu/speech-to-text` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 613 | `Audio-WestlakeU/FullSubNet` | enhance,ml-framework | ③即时蒸馏(降噪/分离前置) | - |
| 608 | `dpirch/libfvad` | kws-vad,dsp-lib | ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | BSD-3-Clause |
| 600 | `calebj0seph/spectro` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 595 | `hirofumi0810/neural_sp` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 541 | `opendilab/CleanS2S` | asr,agent | ③即时蒸馏(ASR 转写写记忆) | - |
| 528 | `ccoreilly/vosk-browser` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 528 | `FireRedTeam/FireRedVAD` | aed,kws-vad,dsp-lib | ③即时蒸馏(声音事件/场景理解) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | Apache-2.0 |
| 508 | `gkonovalov/android-vad` | aed,kws-vad,dsp-lib | ③即时蒸馏(声音事件/场景理解) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | - |
| 505 | `alphacep/vosk` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 463 | `hcmlab/vadnet` | kws-vad | ①常驻检测(VAD/唤醒词能量门) | LGPL-3.0 |
| 460 | `YeJe-cpu/talk-to-fengge` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 450 | `Demfier/multimodal-speech-emotion-recognition` | asr,dsp-lib,dataset,ml-framework | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | MIT |
| 446 | `AndraxDev/speak-gpt` | asr,agent | ③即时蒸馏(ASR 转写写记忆) | - |
| 444 | `Boof2015/astra` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 436 | `Ikaros-521/RealtimeSTT_LLM_TTS` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 425 | `xifan2333/fcitx5-vinput` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 413 | `cyberofficial/Synthalingua` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 409 | `alphacep/awesome-russian-speech` | asr,tts | ③即时蒸馏(ASR 转写写记忆) | - |
| 393 | `altunenes/parakeet-rs` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 383 | `kstonekuan/tambourine-voice` | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | AGPL-3.0 |
| 380 | `oliverguhr/wav2vec2-live` | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |
| 379 | `mailong25/self-supervised-speech-recognition` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 376 | `istupakov/onnx-asr` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 373 | `bambocher/pocketsphinx-python` | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 369 | `jzi040941/PercepNet` | enhance,ml-framework | ③即时蒸馏(降噪/分离前置) | - |
| 367 | `smixs/agent-second-brain` | kws-vad,agent,agent-llm | ①常驻检测(VAD/唤醒词能量门) | - |
| 350 | `haoxiangsnr/A-Convolutional-Recurrent-Neural-Network-for-Real-Time-Speech-Enhancement` | enhance,ml-framework | ③即时蒸馏(降噪/分离前置) | - |
| 346 | `estebanstifli/LocalText2Voice` | tts,dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 341 | `Renovamen/Speech-and-Text` | asr,tts,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 341 | `oboroge0/hayamimi` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 339 | `deeeed/audiolab` | dsp-lib | ①②采集与能量门(录音/读取/预处理) | - |
| 328 | `seanwood/gcc-nmf` | enhance | ③即时蒸馏(降噪/分离前置) | - |
| 324 | `mahimairaja/voiceai` | asr,tts,agent,dsp-lib,agent-llm | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |
| 317 | `jishengpeng/WavChat` | audio-llm,codec | ③即时蒸馏(多模态理解/结构化) | - |
| 315 | `sayksii/Aria` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 314 | `thewh1teagle/sherpa-rs` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 313 | `lRomul/argus-freesound` | aed,ml-framework | ③即时蒸馏(声音事件/场景理解) | - |
| 304 | `Frikallo/parakeet.cpp` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 302 | `gtreshchev/RuntimeSpeechRecognizer` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 296 | `kouhxp/yapsnap` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 295 | `narcotic-sh/senko` | kws-vad,speaker | ①常驻检测(VAD/唤醒词能量门) | - |
| 293 | `lucianodato/speech-denoiser` | enhance | ③即时蒸馏(降噪/分离前置) | - |
| 278 | `devnen/Kitten-TTS-Server` | tts,enhance,ml-framework | ③即时蒸馏(降噪/分离前置) | - |
| 277 | `m3hrdadfi/soxan` | asr,aed | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(声音事件/场景理解) | - |
| 275 | `voicekit-team/T-one` | asr,serving | ③即时蒸馏(ASR 转写写记忆) | - |
| 268 | `QuintinShaw/openasr` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 267 | `ASR-project/Multilingual-PR` | asr,ml-framework | ③即时蒸馏(ASR 转写写记忆) | - |
| 257 | `asiff00/On-Device-Speech-to-Speech-Conversational-AI` | asr,tts,kws-vad,agent | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | - |
| 252 | `whitphx/streamlit-stt-app` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 251 | `HKAllThingsLink/streaming-asr` | asr,kws-vad,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | MIT |
| 248 | `XiaoMi/kaldi-onnx` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 233 | `hyperconnect/TC-ResNet` | kws-vad | ①常驻检测(VAD/唤醒词能量门) | Apache-2.0 |
| 228 | `pszemraj/vid2cleantxt` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 217 | `Kaljurand/dictate.js` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 211 | `ChetanXpro/nodejs-whisper` | asr | ③即时蒸馏(ASR 转写写记忆) | - |
| 206 | `streamcoreai/streamcore-server` | asr,tts,agent,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | - |

**与既有选型的冲突/替代（节选）：**

- `k2-fsa/sherpa-onnx` 优于 `modelscope/FunASR` 作为端侧 ASR 运行时（已见于 SER 04 §8：ONNX 推理在 proot aarch64 上更稳、体积更小）。
- `snakers4/silero-vad` / `k2-fsa/sherpa-onnx` 的 VAD 是 ①常驻检测首选，纯 CPU、毫秒级、可常驻。
- `ggml-org/whisper.cpp` 是 ③即时蒸馏 ASR 主选；`alphacep/vosk-api` 提供离线多语种备选。
- `xiph/rnnoise` / `breizhn/DTLN` / `Audio-WestlakeU/FullSubNet` 等降噪模型作 ③前置。`sherpa-onnx` 同时含降噪与 VAD。

## 5 · 明确不推荐清单（高星但不适配）

下列仓库 star 很高，但**不应直接作为 laos 组件**——原因是范围外（laos 只听不说）、缺端侧信号、或是云/媒体服务器/编排层。避免「star 高就该用」的误判。

| star | 仓库 | 类别 | 不推荐理由(fit_notes) |
|---:|---|---|---|
| 165,390 | `huggingface/transformers` | asr,ml-framework | funnel-cat:asr / no-on-device-signal(C1?) |
| 123,134 | `harry0703/MoneyPrinterTurbo` | tts,dsp-lib | funnel-cat:dsp-lib / no-on-device-signal(C1?) |
| 76,104 | `unslothai/unsloth` | tts,agent,agent-llm | out-of-scope(laos只听不说/不生成音乐) |
| 61,770 | `RVC-Boss/GPT-SoVITS` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 60,131 | `CorentinJ/Real-Time-Voice-Cloning` | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 58,248 | `calesthio/OpenMontage` | tts,agent,dsp-lib | vision/multimodal-agent(not-audio-pipeline) |
| 54,243 | `microsoft/VibeVoice` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 54,074 | `hugohe3/ppt-master` | agent | orchestration/eval-not-funnel-component |
| 53,113 | `jamiepine/voicebox` | asr,tts | funnel-cat:asr / needs-gpu(C1✗) |
| 49,110 | `moeru-ai/airi` | agent | orchestration/eval-not-funnel-component |
| 49,094 | `mudler/LocalAI` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 46,006 | `coqui-ai/TTS` | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 39,833 | `2noise/ChatTTS` | tts,audio-llm,agent,dsp-lib,agent-llm | funnel-cat:dsp-lib / no-on-device-signal(C1?) |
| 37,512 | `myshell-ai/OpenVoice` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 37,053 | `OpenBMB/VoxCPM` | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 36,965 | `mpv-player/mpv` | dsp-lib | funnel-cat:dsp-lib / no-on-device-signal(C1?) |
| 36,930 | `google-ai-edge/mediapipe` | serving | orchestration/eval-not-funnel-component |
| 36,910 | `babysor/MockingBird` | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 32,671 | `fishaudio/fish-speech` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 29,238 | `ossrs/srs` | codec,dsp-lib | media-server/transport-infra(not-on-device) |
| 28,442 | `deezer/spleeter` | enhance,ml-framework | funnel-cat:enhance / no-on-device-signal(C1?) |
| 28,110 | `svc-develop-team/so-vits-svc` | music,ml-framework | out-of-scope(laos不做音乐/music-transcription) |
| 28,076 | `ATH-MaaS/Pixelle-Video` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 28,001 | `mastra-ai/mastra` | tts | out-of-scope(laos只听不说/不生成音乐) |
| 27,202 | `Fosowl/agenticSeek` | agent,agent-llm | orchestration/eval-not-funnel-component |

典型模式：
- **音乐/TTS 生成类**（so-vits-svc / GPT-SoVITS / Coqui TTS / fish-speech）：laos 只听不说，范围外。
- **巨型框架/编排**（transformers / unsloth / mastra / agenticSeek）：缺 on-device 信号或属 agent 编排层，非漏斗组件。
- **媒体服务器/传输**（ossrs/srs）：属基础设施，非端侧组件。
- **unrelated 泄漏**（awesome-piracy / audacity / seamless_communication）：与漏斗无关，属补抓噪声复核残留。

## 6 · 局限与需人工复核

本报告如实保留 Task 3 执行者标注的「需人工复核」项，**未做粉饰**：

1. **speaker 类「隐私红线」是策略性一律降级**——未区分「纯 diarization 分割（可借鉴）」与「声纹注册（碰红线 C5）」。若某项目仅做流式分割，应人工复核后上调为 core 候选。
2. **端侧可行性（C1）靠关键词近似判定**，未在 proot aarch64 上实测跑通；silero / sherpa-onnx / whisper.cpp 等经 SER 04 §8 论证可行，其余需实测。
3. **许可字段 2801/3724（75.2%）缺失**，core 仅排除云 API wrapper，未逐条核 SPDX，不替代法律意见。
4. **少数 speech-foundation 大模型**（如 `facebookresearch/seamless_communication`）因描述措辞未被关键词命中，被误分到 unrelated。

通用局限：star 数为抓取时刻快照（时变）；类别依赖作者自填 `topics`+`description`，存在标签噪声导致漏标/错标；判定仅基于元数据，未读源码。

