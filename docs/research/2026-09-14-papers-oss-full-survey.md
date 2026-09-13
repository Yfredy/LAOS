# 论文 × 开源项目全量普查（最终版）：Interspeech 全量 · ICASSP 切片 · GitHub 音频×AI×Agent

> 生成时间：2026-09-14 02:52 ｜ 生成器：corpus/gen_final_report.py（数字全部程序化读出）
> 前序：[ICASSP+Interspeech 遍历报告](2026-09-13-icassp-interspeech-full-survey.md)（Interspeech 全量与 ICASSP 约束链）

## 1. 论文普查现状

- **Interspeech 2021-2025：全量 5507 篇**（2021:999 / 2022:1123 / 2023:1141 / 2024:1065 / 2025:1179）——ISCA Archive 官方索引逐锚点解析，100% 覆盖
- **ICASSP 2022-2026**：
  - 已知规模（openaccept/官方口径）：2022 录用 1,785 / 2023 录用 2,765 / 2024 ~2,812，五届合计 ~1.2 万篇
  - OpenAlex 全量枚举：配额 UTC 午夜重置后执行（脚本就绪 `crawl_icassp_openalex.py`）——**本版暂缺**，属已知未覆盖
  - S2 主题切片真实命中（venue=ICASSP, 2022-2026）：

    | 主题切片 | 命中总数 |
    |---|---|
    | speech enhancement | 5,257 |
    | neural codec | 2,388 |
    | emotion recognition | 1,838 |
    | speaker diarization | 999 |
    | sound event detection | 296 |
    | voice activity detection | 183 |

## 2. GitHub 音频×AI×Agent 开源项目普查

- **去重项目总数：3,529**（10 切片搜索，star 降序翻页）
- 切片命中：

    | 切片 | 命中 |
    |---|---|
    | audio-llm | 1,000（1000 上限截断） |
    | voice-agent | 1,000（1000 上限截断） |
    | audio | 651 |
    | tts | 539 |
    | asr | 479 |
    | speech | 193 |
    | voice-assistant | 156 |
    | diarization | 100 |
    | enhancement | 97 |
    | audio-processing | 96 |

- star 分布：>10k = 370 ｜ 1k-10k = 1,609 ｜ 100-1k = 1,472
- **榜单清洗**：audio-llm/voice-agent 两个自由文本切片命中 981 个 awesome-list/课程类仓库（确定性规则：名称/描述含 awesome|list of|course|checklist|curated|collection of），真实项目榜单按其余 2,548 个计算

### 2.1 真实项目 star 榜 Top 50（清洗后）

| ★ | 项目 | 语言 | 简介 |
|---|---|---|---|
| 257,576 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | JavaScript | The agent harness performance optimization system. Skills, instincts, memory |
| 245,098 | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | Python | The agent that grows with you |
| 165,390 | [huggingface/transformers](https://github.com/huggingface/transformers) | Python | 🤗 Transformers: the model-definition framework for state-of-the-art machine  |
| 152,085 | [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | Shell | A complete AI agency at your fingertips - From frontend wizards to Reddit co |
| 151,868 | [open-webui/open-webui](https://github.com/open-webui/open-webui) | Python | User-friendly AI Interface (Supports Ollama, OpenAI API, ...) |
| 132,640 | [farion1231/cc-switch](https://github.com/farion1231/cc-switch) | Rust | A cross-platform desktop All-in-One assistant for Claude Code, Codex, OpenCo |
| 128,096 | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | C++ | LLM inference in C/C++ |
| 123,134 | [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | Python | 利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short videos from a topic or  |
| 116,362 | [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | Python | Turn any codebase, with its docs, SQL schemas, configs, and PDFs, into a que |
| 95,901 | [nexu-io/open-design](https://github.com/nexu-io/open-design) | TypeScript | 🎨 Best DeepSeek Harness Design Plugin. The open-source Claude Design alterna |
| 83,095 | [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | Python | 🚀🤖 Crawl4AI: Open-source LLM Friendly Web Crawler & Scraper. Don't be shy, j |
| 82,347 | [bytedance/deer-flow](https://github.com/bytedance/deer-flow) | Python | An open-source long-horizon SuperAgent harness that researches, codes, and c |
| 76,104 | [unslothai/unsloth](https://github.com/unslothai/unsloth) | Python | Local UI to run and train LLMs and diffusion models. Supports GGUF, MLX, Qwe |
| 74,742 | [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory) | Python | Unified Efficient Fine-Tuning of 100+ LLMs & VLMs (ACL 2024) |
| 71,450 | [career-ops-hq/career-ops](https://github.com/career-ops-hq/career-ops) | JavaScript | Open-source AI job search: scan job portals, evaluate listings into a struct |
| 65,982 | [Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm) | JavaScript | Stop renting your intelligence. Own it with AnythingLLM. Everything you need |
| 65,894 | [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | HTML | from vibe coding to agentic engineering - practice makes claude perfect |
| 65,865 | [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) | JavaScript | Extracted system prompts from Anthropic - Claude Fable 5.1, Opus 5, Claude D |
| 65,610 | [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute) | TypeScript | Never stop coding. Free MIT AI gateway: one endpoint, 352 providers (150+ fr |
| 64,181 | [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) | C | Mirror of https://git.ffmpeg.org/ffmpeg.git |
| 61,770 | [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | Python | 1 min voice data can also be used to train a good TTS model! (few shot voice |
| 60,131 | [CorentinJ/Real-Time-Voice-Cloning](https://github.com/CorentinJ/Real-Time-Voice-Cloning) | Python | Clone a voice in 5 seconds to generate arbitrary speech in real-time |
| 58,635 | [BerriAI/litellm](https://github.com/BerriAI/litellm) | Python | The fastest, litest AI Gateway. Rust core with Python SDK. Call 100+ LLM API |
| 58,248 | [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | Python | World's first open-source, agentic video production system. 12 production pi |
| 54,428 | [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch) | Python | Learn it. Build it. Ship it for others. |
| 54,243 | [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | Python | Open-Source Frontier Voice AI |
| 54,074 | [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master) | Python | AI turns documents or topics into real, native PowerPoint decks—with native  |
| 53,646 | [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp) | C++ | Port of OpenAI's Whisper model in C/C++ |
| 53,113 | [jamiepine/voicebox](https://github.com/jamiepine/voicebox) | TypeScript | The open-source AI voice studio. Clone, dictate, create. |
| 49,448 | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | TypeScript | Write HTML. Render video. Built for agents. |
| 49,353 | [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) | Python | "CLI-Anything: Making ALL Software Agent-Native" -- CLI-Hub: https://clianyt |
| 49,110 | [moeru-ai/airi](https://github.com/moeru-ai/airi) | TypeScript | 💖🧸 Self hosted, you-owned Grok Companion, a container of souls of waifu, cyb |
| 49,094 | [mudler/LocalAI](https://github.com/mudler/LocalAI) | Go | LocalAI is the open-source AI engine. Run any model - LLMs, vision, voice, i |
| 48,095 | [HKUDS/nanobot](https://github.com/HKUDS/nanobot) | Python | Ultra-lightweight, open-source, self-hosted personal AI agent framework in P |
| 48,001 | [QuantumNous/new-api](https://github.com/QuantumNous/new-api) | Go | A unified AI model hub for aggregation & distribution. It supports cross-con |
| 47,581 | [blader/humanizer](https://github.com/blader/humanizer) | Python | Agent skill that removes signs of AI-generated writing from text |
| 46,948 | [zhayujie/CowAgent](https://github.com/zhayujie/CowAgent) | Python | Open-source super AI assistant & Agent Harness. Plans tasks, runs tools and  |
| 46,006 | [coqui-ai/TTS](https://github.com/coqui-ai/TTS) | Python | 🐸💬 - a deep learning toolkit for Text-to-Speech, battle-tested in research a |
| 44,731 | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | Python | Turn any AI agent into an AI Scientist. The #1 Agent Skills library for scie |
| 39,983 | [novuhq/novu](https://github.com/novuhq/novu) | TypeScript | The open-source communication infrastructure for agents and products |
| 39,833 | [2noise/ChatTTS](https://github.com/2noise/ChatTTS) | Python | A generative speech model for daily dialogue. |
| 39,735 | [tinyhumansai/openhuman](https://github.com/tinyhumansai/openhuman) | Rust | OpenHuman is an open source agent harness with local-first memory, agent orc |
| 39,512 | [HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | Python | DeepTutor: Lifelong Personalized Tutoring. https://deeptutor.info/. |
| 39,129 | [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | TypeScript | Teams-first Multi-agent orchestration for Claude Code |
| 38,635 | [chatchat-space/Langchain-Chatchat](https://github.com/chatchat-space/Langchain-Chatchat) | Python | Langchain-Chatchat（原Langchain-ChatGLM）基于 Langchain 与 ChatGLM, Qwen 与 Llama 等 |
| 37,512 | [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice) | Python | Instant voice cloning by MIT and MyShell. Audio foundation model. |
| 37,496 | [karpathy/LLM101n](https://github.com/karpathy/LLM101n) | — | LLM101n: Let's build a Storyteller |
| 37,053 | [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) | Python | VoxCPM2: Tokenizer-Free TTS for Multilingual Speech Generation, Creative Voi |
| 36,965 | [mpv-player/mpv](https://github.com/mpv-player/mpv) | C | 🎥 Command line media player |
| 36,930 | [google-ai-edge/mediapipe](https://github.com/google-ai-edge/mediapipe) | C++ | Cross-platform, customizable ML solutions for live and streaming media. |

### 2.2 laos 相关分类榜（每类 top8，清洗后）

**TTS/语音克隆**（命中 640）

- ★123,134 [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)——利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short videos from a top
- ★76,104 [unslothai/unsloth](https://github.com/unslothai/unsloth)——Local UI to run and train LLMs and diffusion models. Supports GGUF, ML
- ★61,770 [RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)——1 min voice data can also be used to train a good TTS model! (few shot
- ★60,131 [CorentinJ/Real-Time-Voice-Cloning](https://github.com/CorentinJ/Real-Time-Voice-Cloning)——Clone a voice in 5 seconds to generate arbitrary speech in real-time
- ★58,248 [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage)——World's first open-source, agentic video production system. 12 product
- ★53,113 [jamiepine/voicebox](https://github.com/jamiepine/voicebox)——The open-source AI voice studio. Clone, dictate, create.
- ★49,094 [mudler/LocalAI](https://github.com/mudler/LocalAI)——LocalAI is the open-source AI engine. Run any model - LLMs, vision, vo
- ★46,006 [coqui-ai/TTS](https://github.com/coqui-ai/TTS)——🐸💬 - a deep learning toolkit for Text-to-Speech, battle-tested in rese

**ASR/转写**（命中 626）

- ★165,390 [huggingface/transformers](https://github.com/huggingface/transformers)——🤗 Transformers: the model-definition framework for state-of-the-art ma
- ★53,646 [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)——Port of OpenAI's Whisper model in C/C++
- ★53,113 [jamiepine/voicebox](https://github.com/jamiepine/voicebox)——The open-source AI voice studio. Clone, dictate, create.
- ★26,776 [mozilla/DeepSpeech](https://github.com/mozilla/DeepSpeech)——DeepSpeech is an open source embedded (offline, on-device) speech-to-t
- ★26,113 [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio)——VoiceStudio is the open-source, fully-local ElevenLabs alternative — v
- ★25,376 [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)——Faster Whisper transcription with CTranslate2
- ★24,018 [m-bain/whisperX](https://github.com/m-bain/whisperX)——WhisperX:  Automatic Speech Recognition with Word-level Timestamps (& 
- ★20,306 [modelscope/FunASR](https://github.com/modelscope/FunASR)——Open-source speech recognition toolkit for training, inference, stream

**说话人/分离**（命中 213）

- ★54,074 [hugohe3/ppt-master](https://github.com/hugohe3/ppt-master)——AI turns documents or topics into real, native PowerPoint decks—with n
- ★46,006 [coqui-ai/TTS](https://github.com/coqui-ai/TTS)——🐸💬 - a deep learning toolkit for Text-to-Speech, battle-tested in rese
- ★28,442 [deezer/spleeter](https://github.com/deezer/spleeter)——Deezer source separation library including pretrained models.
- ★26,219 [Anjok07/ultimatevocalremovergui](https://github.com/Anjok07/ultimatevocalremovergui)—— GUI for a Vocal Remover that uses Deep Neural Networks.
- ★24,018 [m-bain/whisperX](https://github.com/m-bain/whisperX)——WhisperX:  Automatic Speech Recognition with Word-level Timestamps (& 
- ★20,306 [modelscope/FunASR](https://github.com/modelscope/FunASR)——Open-source speech recognition toolkit for training, inference, stream
- ★18,437 [NVIDIA-NeMo/Speech](https://github.com/NVIDIA-NeMo/Speech)——A scalable generative AI framework built for researchers and developer
- ★15,481 [kaldi-asr/kaldi](https://github.com/kaldi-asr/kaldi)——kaldi-asr/kaldi is the official location of the Kaldi project.

**增强/降噪**（命中 133）

- ★39,833 [2noise/ChatTTS](https://github.com/2noise/ChatTTS)——A generative speech model for daily dialogue.
- ★14,747 [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)——Speech-to-text, text-to-speech, speaker diarization, speech enhancemen
- ★11,819 [speechbrain/speechbrain](https://github.com/speechbrain/speechbrain)——A PyTorch-based Speech Toolkit
- ★9,955 [espnet/espnet](https://github.com/espnet/espnet)——End-to-End Speech Processing Toolkit
- ★7,930 [adithya-s-k/omniparse](https://github.com/adithya-s-k/omniparse)——Ingest, parse, and optimize any data format ➡️ from documents to multi
- ★5,834 [xiph/rnnoise](https://github.com/xiph/rnnoise)——Recurrent neural network for audio noise reduction
- ★4,703 [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)——Noise supression using deep filtering
- ★4,484 [modelscope/ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio)——An AI-Powered Speech Processing Toolkit and Open Source SOTA Pretraine

**VAD/唤醒/KWS**（命中 65）

- ★123,134 [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)——利用 AI 大模型和自动化工作流，根据主题或关键词一键生成高清短视频。Generate HD short videos from a top
- ★20,306 [modelscope/FunASR](https://github.com/modelscope/FunASR)——Open-source speech recognition toolkit for training, inference, stream
- ★14,747 [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)——Speech-to-text, text-to-speech, speaker diarization, speech enhancemen
- ★10,544 [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio)——Neural building blocks for speaker diarization: speech activity detect
- ★10,205 [snakers4/silero-vad](https://github.com/snakers4/silero-vad)——Silero VAD: pre-trained enterprise-grade Voice Activity Detector
- ★7,870 [smacke/ffsubsync](https://github.com/smacke/ffsubsync)——Automagically synchronize subtitles with video.
- ★4,935 [Picovoice/porcupine](https://github.com/Picovoice/porcupine)——On-device wake word detection powered by deep learning
- ★2,759 [FluidInference/FluidAudio](https://github.com/FluidInference/FluidAudio)——Frontier CoreML audio models in your apps — text-to-speech, speech-to-

**音频 LLM/理解**（命中 20）

- ★23,597 [QwenAudio/CosyVoice](https://github.com/QwenAudio/CosyVoice)——Multi-lingual large voice generation model, providing inference, train
- ★9,299 [QwenAudio/SenseVoice](https://github.com/QwenAudio/SenseVoice)——Open-source SenseVoiceSmall model for Mandarin, Cantonese, English, Ja
- ★8,801 [fishaudio/Bert-VITS2](https://github.com/fishaudio/Bert-VITS2)——vits2 backbone with multilingual-bert
- ★6,336 [canopyai/Orpheus-TTS](https://github.com/canopyai/Orpheus-TTS)——Towards Human-Sounding Speech
- ★2,565 [QwenAudio/qwen-audio-agent](https://github.com/QwenAudio/qwen-audio-agent)——A realtime voice runtime that keeps Agents talking, working, and prese
- ★1,984 [FireRedTeam/FireRedASR](https://github.com/FireRedTeam/FireRedASR)——Open-source industrial-grade ASR models supporting Mandarin, Chinese d
- ★1,949 [QwenLM/Qwen-Audio](https://github.com/QwenLM/Qwen-Audio)——The official repo of Qwen-Audio (通义千问-Audio) chat & pretrained large a
- ★1,535 [QwenAudio/Fun-ASR](https://github.com/QwenAudio/Fun-ASR)——Fun-ASR speech recognition models, with native Hugging Face Transforme

**Voice Agent/助手**（命中 235）

- ★49,110 [moeru-ai/airi](https://github.com/moeru-ai/airi)——💖🧸 Self hosted, you-owned Grok Companion, a container of souls of waif
- ★27,202 [Fosowl/agenticSeek](https://github.com/Fosowl/agenticSeek)——Fully Local Manus AI. No APIs, No $200 monthly bills. Enjoy an autonom
- ★23,771 [slopus/happy](https://github.com/slopus/happy)——Mobile and Web client for Codex and Claude Code, with realtime voice, 
- ★21,324 [RasaHQ/rasa](https://github.com/RasaHQ/rasa)——💬   Open source machine learning framework to automate text- and voice
- ★20,887 [livekit/livekit](https://github.com/livekit/livekit)——End-to-end realtime stack for connecting humans and AI
- ★19,902 [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)——How Python does AI. Agents, realtime voice, image generation, embeddin
- ★17,507 [leon-ai/leon](https://github.com/leon-ai/leon)——🧠 Leon is your open-source personal assistant.
- ★15,495 [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat)——Open Source framework for voice agents, multimodal apps, and realtime 

### 2.3 前 30 深读项目（README 已存 `corpus/oss_top30_readmes/`）

| ★ | 项目 | 一句话 |
|---|---|---|
| 20,306 | [modelscope/FunASR](https://github.com/modelscope/FunASR) | Open-source speech recognition toolkit for training, inference, stream |
| 11,819 | [speechbrain/speechbrain](https://github.com/speechbrain/speechbrain) | A PyTorch-based Speech Toolkit |
| 9,299 | [QwenAudio/SenseVoice](https://github.com/QwenAudio/SenseVoice) | Open-source SenseVoiceSmall model for Mandarin, Cantonese, English, Ja |
| 2,759 | [FluidInference/FluidAudio](https://github.com/FluidInference/FluidAudio) | Frontier CoreML audio models in your apps — text-to-speech, speech-to- |
| 2,664 | [0xShug0/audio.cpp](https://github.com/0xShug0/audio.cpp) | An all-in-one, pure C++ inference engine for audio models, powered by  |
| 2,236 | [meizhong986/WhisperJAV](https://github.com/meizhong986/WhisperJAV) | ASR/STT subtitle generator. Uses Qwen3-ASR, local LLM, Whisper, TEN-VA |
| 1,535 | [QwenAudio/Fun-ASR](https://github.com/QwenAudio/Fun-ASR) | Fun-ASR speech recognition models, with native Hugging Face Transforme |
| 1,419 | [lenML/Speech-AI-Forge](https://github.com/lenML/Speech-AI-Forge) | 🍦 Speech-AI-Forge is a project developed around TTS generation model,  |
| 1,289 | [ictnlp/StreamSpeech](https://github.com/ictnlp/StreamSpeech) | StreamSpeech is an “All in One” seamless model for offline and simulta |
| 1,175 | [soniqo/speech-swift](https://github.com/soniqo/speech-swift) | AI speech toolkit for Apple Silicon — ASR, TTS, speech-to-speech, VAD, |
| 975 | [stepfun-ai/Step-Audio-EditX](https://github.com/stepfun-ai/Step-Audio-EditX) | A powerful 3B-parameter, LLM-based Reinforcement Learning audio edit m |
| 678 | [FireRedTeam/FireRedASR2S](https://github.com/FireRedTeam/FireRedASR2S) | A SOTA Industrial-Grade All-in-One ASR system with ASR, VAD, LID, and  |
| 650 | [TheDeathDragon/LiveTranslate](https://github.com/TheDeathDragon/LiveTranslate) | Real-time audio translation, captures system audio + mic, runs ASR (Wh |
| 578 | [shashikg/WhisperS2T](https://github.com/shashikg/WhisperS2T) | An Optimized Speech-to-Text Pipeline for the Whisper Model Supporting  |
| 468 | [double22a/speech_dataset](https://github.com/double22a/speech_dataset) | The dataset of Speech Recognition |
| 384 | [izwi-ai/izwi](https://github.com/izwi-ai/izwi) | Voice AI runtime. Local first transcription, speaker diarization, TTS, |
| 356 | [kigner/audio.cpp-webui](https://github.com/kigner/audio.cpp-webui) | audio.cpp with a full-task WebUI - pure C++ audio-model inference engi |
| 324 | [OpenBMB/UltraEval-Audio](https://github.com/OpenBMB/UltraEval-Audio) | Your faithful, impartial partner for audio evaluation — know yourself, |
| 324 | [mahimairaja/voiceai](https://github.com/mahimairaja/voiceai) | Set of 📝 with 🔗 to help those building Voice AI agents 🎙️🤖 |
| 311 | [mbzuai-oryx/LLMVoX](https://github.com/mbzuai-oryx/LLMVoX) | LLMVoX: Autoregressive Streaming Text-to-Speech Model for Any LLM |
| 257 | [asiff00/On-Device-Speech-to-Speech-Conversational-AI](https://github.com/asiff00/On-Device-Speech-to-Speech-Conversational-AI) | This is an on-CPU real-time conversational system for two-way speech c |
| 217 | [gpustack/vox-box](https://github.com/gpustack/vox-box) | A text-to-speech and speech-to-text server compatible with the OpenAI  |
| 185 | [EveningStudy/asmr-dubber](https://github.com/EveningStudy/asmr-dubber) | 音视频字幕及配音工具：支持 ASR（语音识别）、台本导入、AI 翻译、双语字幕、音色克隆、TTS（语音合成）与混音以得到双语音频。 |
| 165 | [Ali-hey-0/audio-ai-field-guide](https://github.com/Ali-hey-0/audio-ai-field-guide) | A mental-model-first field guide to Audio AI — from raw waveforms to p |
| 152 | [soniqo/speech-android](https://github.com/soniqo/speech-android) | On-device speech SDK for Android — ASR, TTS, VAD, and noise cancellati |
| 144 | [VideotronicMaker/LM-Studio-Voice-Conversation](https://github.com/VideotronicMaker/LM-Studio-Voice-Conversation) | Python app for LM Studio-enhanced voice conversations with local LLMs. |
| 134 | [lgy1027/matrix-live-diarizer](https://github.com/lgy1027/matrix-live-diarizer) | Local-first meeting transcription — audio & transcripts never leave yo |
| 116 | [VoiceBlender/voiceblender](https://github.com/VoiceBlender/voiceblender) | A programmable Voice AI platform: SIP and WebRTC call control, multi-p |
| 83 | [soniqo/speech-core](https://github.com/soniqo/speech-core) | On-device VAD / streaming STT / TTS / diarization in C++17 (ONNX + Lit |
| 23 | [Etherll/Timbre](https://github.com/Etherll/Timbre) | Extract a target speaker’s clean, non-overlapped speech from multi-spe |

## 3. 论文 ↔ 开源对照（laos 选型视图）

| 主题 | 代表论文（本语料深读） | 对应高星实现 |
|---|---|---|
| 流式说话人分离 | Streaming Sortformer（IS25） | pyannote ★10.5k / FunASR ★20.3k / 3D-Speaker |
| SER 端侧 | TRILLsson（IS22）/ TIM-Net（ICASSP'23） | EmoBox ★（emo-box）/ speechbrain ★11.8k |
| 增强/AGC | GTCRN（ICASSP'24）/ TSDT-Net（IS25）/ UniSE（IS26） | DeepFilterNet ★4.7k / ClearerVoice ★4.5k / FunASR |
| ASR/转写 | Efficient Streaming LLM ASR（ICASSP'25 工业最佳） | whisper.cpp ★53.6k / faster-whisper ★25.4k / whisperX ★24k |
| TTS/回复 | CosyVoice 2 / Kokoro（HF） | GPT-SoVITS ★61.8k / coqui-TTS ★46k / VoxCPM ★37k |
| VAD/唤醒 | LLM-Synth4KWS / FusionVAD（IS25） | silero-vad / openWakeWord（见 laos 主 README 全景表） |
| 编解码留存 | Mimi/SNAC/LFSC | Stable Codec 生态（codec 主题 IS25 45 篇） |
| Voice Agent 框架 | FD-Bench（IS25 全双工） | pipecat ★15.5k / leon ★17.5k / agenticSeek ★27.2k |

## 4. 未覆盖与局限（如实）

- ICASSP OpenAlex 全量枚举：配额重置后运行 `crawl_icassp_openalex.py` 即补齐（脚本就绪）；本版以 S2 切片替代
- S2 轮询仍有切片未放行（未认证池饱和），失败键如实标注 uncovered
- audio-llm/voice-agent 切片 1000 上限截断 + awesome-list 污染已清洗，但清洗规则（正则）可能错杀个别真实项目
- README 深读 30 个按 stars×相关性挑选，非全量 3,529