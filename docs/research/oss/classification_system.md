# Task 3 分类体系与 laos 适配映射

**源数据**: `repos_raw.jsonl`（3724 条，Task 2 去噪+补抓后干净语料）
**生成日期**: 2026-09-14  **分类器**: `scripts/classify_oss.py`（规则可复现）

## 1. 分类体系（13 类，可多标签）

判据：对 `full_name` + `description` + `topics` 做不区分大小写正则匹配，命中即打标；一条仓库可同时命中多类。

| 类别 | 命中正则（简述） | laos 漏斗落点倾向 |
|---|---|---|
| asr | asr / speech-to-text / transcri / whisper / recogni / stt / wav2vec / vosk | ③即时蒸馏 |
| tts | text-to-speech / tts / vocoder / speech synthesis / voice cloning | 不在漏斗（laos 只听不说）|
| audio-llm | audio llm / speech llm / omni / multimodal audio / audio gpt | ③即时蒸馏 |
| enhance | denois / enhance / dereverb / noise suppress / separat / beamform | ③即时蒸馏(前置) |
| aed | audio tagging / sound event / acoustic scene / event detection / yamnet | ③即时蒸馏 |
| codec | codec / encodec / opus / soundstream / neural codec | ②可选(原音频即焚) |
| kws-vad | keyword spotting / wake-word / voice activity / vad / always-on | ①常驻检测 |
| speaker | speaker verification/diarization / voiceprint / ecapa | 隐私红线(C5)，不落地 |
| agent | agent / assistant / conversational / voicebot / copilot | 编排(ref) |
| serving | serving / inference server / onnxruntime / tensorrt / vllm | 基础设施(ref) |
| dsp-lib | ffmpeg / librosa / pyaudio / sox / webrtc / torchaudio | ①②采集/能量门 |
| music | music generation / midi / song / singing / beat | 不在漏斗 |
| dataset | dataset / corpus / benchmark / librispeech | 评测(ref) |

## 2. laos_fit 判定规则（落到硬约束）

硬约束：C1 端侧 CPU 可跑（proot glibc aarch64，无 NPU）｜C2 低延迟/流式｜C3 许可可商用自托管｜C4 不依赖云 API｜C5 不存声纹。

```
understanding = {kws-vad, asr, enhance, aed, dsp-lib} (+ audio-llm 仅当无 tts/music)
core  = 命中 understanding
        且 非 CLOUD_RE(云API wrapper) 且 非 SERVER_RE(媒体服务器) 且 非 APPLE(苹果独占)
        且 非 EDU_RE(教学/列表) 且 (非 HEAVY_RE 或 有 on-device 信号)
        且 有 ON_DEVICE_RE 信号(C1+C2) 且 stars >= 200(成熟度)
ref   = 功能对口但违反某约束(云API/GPU/媒体服务器/苹果独占)｜或 out-of-scope/privacy
        (codec/speaker/tts/music/agent/serving/dataset/ml-framework)｜或 stars 未达门槛
unrelated = 未命中任何功能类别（音频相关但无漏斗组件角色：列表/编辑器/播放器…）
```
正向信号 ON_DEVICE_RE 含：whisper.cpp / sherpa / silero / onnxruntime / onnx / funasr / sensevoice / piper / kokoro / webrtc / rnnoise / porcupine / vosk / edge / on-device / realtime / streaming / ggml / tflite / cpu …
负向信号 CLOUD_RE 含：api key / cloud speech / saas / hosted / twilio / elevenlabs / azure / google cloud / amazon transcribe / openai api / groq / replicate / serverless …
负向信号 HEAVY_RE 含：cuda / gpu required / distributed training / fine-tune llm …
> 许可：因语料 2801/3724 条缺失 license（见 oss_fetch_summary.md §6），C3 仅做「非云 API wrapper」的弱判定，不替代法律意见；真正落地前须逐条核实 license。

## 3. 总体适配度分布

| laos_fit | 条数 | 占比 |
|---|---:|---:|
| core | 132 | 3.5% |
| ref | 2864 | 76.9% |
| unrelated | 728 | 19.5% |
| **合计** | 3724 | 100% |

## 4. 各类别统计（条数 + star 中位数 + Top5）

| 类别 | 条数 | star 中位数 | star Top5（仓库 / stars） |
|---|---:|---:|---|
| asr | 1206 | 162 | huggingface/transformers/165390、ggml-org/whisper.cpp/53646、jamiepine/voicebox/53113、mozilla/DeepSpeech/26776、debpalash/VoiceStudio/26113 |
| tts | 837 | 295 | harry0703/MoneyPrinterTurbo/123134、unslothai/unsloth/76104、RVC-Boss/GPT-SoVITS/61770、CorentinJ/Real-Time-Voice-Cloning/60131、calesthio/OpenMontage/58248 |
| agent | 696 | 83 | unslothai/unsloth/76104、calesthio/OpenMontage/58248、hugohe3/ppt-master/54074、moeru-ai/airi/49110、2noise/ChatTTS/39833 |
| ml-framework | 540 | 191 | huggingface/transformers/165390、CorentinJ/Real-Time-Voice-Cloning/60131、coqui-ai/TTS/46006、OpenBMB/VoxCPM/37053、babysor/MockingBird/36910 |
| kws-vad | 367 | 15 | modelscope/FunASR/20306、k2-fsa/sherpa-onnx/14747、snakers4/silero-vad/10205、KoljaB/RealtimeSTT/10127、smacke/ffsubsync/7870 |
| dsp-lib | 303 | 339 | harry0703/MoneyPrinterTurbo/123134、FFmpeg/FFmpeg/64181、calesthio/OpenMontage/58248、2noise/ChatTTS/39833、mpv-player/mpv/36965 |
| enhance | 170 | 177 | deezer/spleeter/28442、Anjok07/ultimatevocalremovergui/26219、k2-fsa/sherpa-onnx/14747、speechbrain/speechbrain/11819、espnet/espnet/9955 |
| serving | 161 | 90 | google-ai-edge/mediapipe/36930、QwenAudio/CosyVoice/23597、modelscope/FunASR/20306、NVIDIA/DeepLearningExamples/14844、k2-fsa/sherpa-onnx/14747 |
| dataset | 151 | 31 | huggingface/datasets/21967、mozilla/TTS/10171、yzhao062/pyod/10001、EvolvingLMMs-Lab/lmms-eval/4402、zzw922cn/awesome-speech-recognition-speech-synthesis-papers/3130 |
| agent-llm | 126 | 203 | unslothai/unsloth/76104、2noise/ChatTTS/39833、Fosowl/agenticSeek/27202、screenpipe/screenpipe/21557、pydantic/pydantic-ai/19902 |
| music | 120 | 600 | svc-develop-team/so-vits-svc/28110、ace-step/ACE-Step-1.5/12678、AudioKit/AudioKit/11459、open-mmlab/Amphion/10288、espnet/espnet/9955 |
| audio-llm | 118 | 153 | 2noise/ChatTTS/39833、PaddlePaddle/PaddleSpeech/12683、AIGC-Audio/AudioGPT/10169、fishaudio/Bert-VITS2/8801、Blaizzy/mlx-audio/7879 |
| speaker | 59 | 95 | modelscope/FunASR/20306、k2-fsa/sherpa-onnx/14747、PaddlePaddle/PaddleSpeech/12683、QuentinFuxa/WhisperLiveKit/11030、pyannote/pyannote-audio/10544 |
| codec | 57 | 501 | ossrs/srs/29238、leandromoreira/digital_video_introduction/16327、Anil-matcha/AI-Youtube-Shorts-Generator/4958、aiming-lab/SimpleMem/3754、xiph/opus/3315 |
| aed | 48 | 14 | QwenAudio/SenseVoice/9299、seth814/Audio-Classification/586、FireRedTeam/FireRedVAD/528、towhee-io/examples/519、gkonovalov/android-vad/508 |

## 5. laos 适配清单（core 组件，真正可落地）

共 **132** 条 `laos_fit=core`。下列按 stars 降序列出，并标注落点漏斗段落。

| star | 仓库 | 类别 | 漏斗落点 | 一句话用途 |
|---:|---|---|---|---|
| 64181 | FFmpeg/FFmpeg | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Mirror of https://git.ffmpeg.org/ffmpeg.git |
| 53646 | ggml-org/whisper.cpp | asr | ③即时蒸馏(ASR 转写写记忆) | Port of OpenAI's Whisper model in C/C++ |
| 26776 | mozilla/DeepSpeech | asr | ③即时蒸馏(ASR 转写写记忆) | DeepSpeech is an open source embedded (offline, on-device) s |
| 20306 | modelscope/FunASR | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Open-source speech recognition toolkit for training, inferen |
| 15126 | alphacep/vosk-api | asr | ③即时蒸馏(ASR 转写写记忆) | Offline speech recognition API for Android, iOS, Raspberry P |
| 14747 | k2-fsa/sherpa-onnx | asr,enhance,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(降噪/分离前置) / ①常驻检测(VAD/唤醒词能量门) | Speech-to-text, text-to-speech, speaker diarization, speech  |
| 12800 | abus-aikorea/voice-pro | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | Gradio WebUI for creators and developers, featuring key TTS  |
| 12683 | PaddlePaddle/PaddleSpeech | asr,audio-llm | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | Easy-to-use Speech Toolkit including Self-Supervised Learnin |
| 11030 | QuentinFuxa/WhisperLiveKit | asr | ③即时蒸馏(ASR 转写写记忆) | Real-time, local speech-to-text with streaming ASR, speaker  |
| 10205 | snakers4/silero-vad | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Silero VAD: pre-trained enterprise-grade Voice Activity Dete |
| 10127 | KoljaB/RealtimeSTT | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | A robust, efficient, low-latency speech-to-text library with |
| 9299 | QwenAudio/SenseVoice | asr,aed | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(声音事件/场景理解) | Open-source SenseVoiceSmall model for Mandarin, Cantonese, E |
| 6300 | modelscope/FunClip | asr | ③即时蒸馏(ASR 转写写记忆) | FunASR-powered video transcription, subtitle generation, and |
| 6099 | snakers4/silero-models | asr | ③即时蒸馏(ASR 转写写记忆) | Silero Models: pre-trained text-to-speech models made embarr |
| 6008 | cactus-compute/cactus | asr | ③即时蒸馏(ASR 转写写记忆) | Quantization, kernels, runtime and inference engine for mobi |
| 5834 | xiph/rnnoise | enhance | ③即时蒸馏(降噪/分离前置) | Recurrent neural network for audio noise reduction |
| 5632 | xiangyuecn/Recorder | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | html5 js 录音 mp3 wav ogg webm amr g711a g711u 格式，支持pc和Android |
| 4623 | gradio-app/fastrtc | asr | ③即时蒸馏(ASR 转写写记忆) | The python library for real-time communication |
| 4342 | cmusphinx/pocketsphinx | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | A small speech recognizer |
| 4122 | umlx5h/LLPlayer | asr | ③即时蒸馏(ASR 转写写记忆) | The media player for language learning, with dual subtitles, |
| 3692 | SakiRinn/LiveCaptions-Translator | asr,audio-llm | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | Lightweight and powerful real-time audio/speech translation  |
| 3671 | ufal/whisper_streaming | asr | ③即时蒸馏(ASR 转写写记忆) | Whisper realtime streaming for long speech-to-text transcrip |
| 3576 | gpt-omni/mini-omni | audio-llm | ③即时蒸馏(多模态理解/结构化) | open-source multimodal large language model that can hear, t |
| 3125 | AutoArk/GPA | asr | ③即时蒸馏(ASR 转写写记忆) | [AutoArk] GPA (General Purpose Audio) can do ASR, TTS and vo |
| 3086 | off-grid-ai/OGAM | asr | ③即时蒸馏(ASR 转写写记忆) | The Swiss Army Knife of Offline AI. Chat, see, speak, and ge |
| 2565 | QwenAudio/qwen-audio-agent | asr | ③即时蒸馏(ASR 转写写记忆) | A realtime voice runtime that keeps Agents talking, working, |
| 2536 | VITA-MLLM/VITA | audio-llm | ③即时蒸馏(多模态理解/结构化) | ✨✨[NeurIPS 2025] VITA-1.5: Towards GPT-4o Level Real-Time Vi |
| 2381 | pschatzmann/arduino-audio-tools | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Audio Tools (a powerful Audio library for Arduino, PlatformI |
| 2364 | filoe/cscore | dsp-lib | ①②采集与能量门(录音/读取/预处理) | An advanced audio library, written in C#. Provides tons of f |
| 2264 | TEN-framework/ten-vad | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Voice Activity Detector (VAD) : low-latency, high-performanc |
| 2024 | juanmc2005/diart | asr | ③即时蒸馏(ASR 转写写记忆) | A python package to build AI-powered real-time audio applica |
| 1914 | handy-computer/transcribe.cpp | asr | ③即时蒸馏(ASR 转写写记忆) |  ggml speech-to-text inference for 16+ model families |
| 1913 | krzemienski/awesome-video | dsp-lib | ①②采集与能量门(录音/读取/预处理) | A curated list of awesome streaming video tools, frameworks, |
| 1783 | k2-fsa/sherpa-ncnn | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Real-time speech recognition and voice activity detection (V |
| 1765 | wwbin2017/bailing | asr | ③即时蒸馏(ASR 转写写记忆) | 百聆 是一个类似GPT-4o的语音对话机器人，通过ASR+LLM+TTS实现，集成DeepSeek R1等优秀大模型，接 |
| 1747 | antirez/voxtral.c | asr | ③即时蒸馏(ASR 转写写记忆) | Pure C inference of Mistral Voxtral Realtime 4B speech to te |
| 1606 | royshil/obs-localvocal | asr | ③即时蒸馏(ASR 转写写记忆) | OBS plugin for local speech recognition and captioning using |
| 1535 | QwenAudio/Fun-ASR | asr,enhance | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(降噪/分离前置) | Fun-ASR speech recognition models, with native Hugging Face  |
| 1475 | silverstein/minutes | asr | ③即时蒸馏(ASR 转写写记忆) | Open-source, local-first Granola/Otter alternative that Clau |
| 1474 | DicioTeam/dicio-android | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Dicio assistant app for Android |
| 1365 | elevenyellow/handcrafted-persona-engine | asr | ③即时蒸馏(ASR 转写写记忆) | An AI-powered interactive avatar engine using Live2D, LLM, A |
| 1361 | mbailey/voicemode | asr | ③即时蒸馏(ASR 转写写记忆) | Natural voice conversations with Claude Code |
| 1318 | HG-ha/MTools | asr | ③即时蒸馏(ASR 转写写记忆) | MTools 是一个功能强大的多功能桌面应用程序，集成了音视频处理、图片编辑、文本操作和编码工具，内置AI增强功能。旨在 |
| 1306 | Henry-23/VideoChat | asr | ③即时蒸馏(ASR 转写写记忆) | 实时交互数字人，可自定义形象与音色，支持音色克隆，对话延迟低至3s。Real-time voice interactiv |
| 1289 | ictnlp/StreamSpeech | asr,audio-llm,enhance | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) / ③即时蒸馏(降噪/分离前置) | StreamSpeech is an “All in One” seamless model for offline a |
| 1253 | roc-streaming/roc-toolkit | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Real-time audio streaming over the network. |
| 1174 | sgl-project/sglang-omni | asr,audio-llm | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) | SGLang-Omni is a high-performance serving framework for audi |
| 1116 | ardha27/AI-Waifu-Vtuber | asr | ③即时蒸馏(ASR 转写写记忆) | AI Vtuber for Streaming on Youtube/Twitch |
| 1107 | nobodywho-ooo/nobodywho | asr | ③即时蒸馏(ASR 转写写记忆) | NobodyWho is an inference engine that lets you run LLMs loca |
| 1094 | alumae/kaldi-gstreamer-server | asr | ③即时蒸馏(ASR 转写写记忆) | Real-time full-duplex speech recognition server, based on th |
| 1057 | introlab/odas | enhance | ③即时蒸馏(降噪/分离前置) | ODAS: Open embeddeD Audition System |
| 1051 | MattMoony/figaro | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Real-time voice-changer for voice-chat, etc. Will support ma |
| 1010 | TensorSpeech/TensorFlowASR | asr | ③即时蒸馏(ASR 转写写记忆) | :zap: TensorFlowASR: Almost State-of-the-art Automatic Speec |
| 988 | k2-fsa/sherpa | asr | ③即时蒸馏(ASR 转写写记忆) | Speech-to-text server framework with next-gen Kaldi |
| 964 | MycroftAI/mycroft-precise | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | A lightweight, simple-to-use, RNN wake word listener |
| 869 | yeyupiaoling/PPASR | asr | ③即时蒸馏(ASR 转写写记忆) | 基于PaddlePaddle实现端到端中文语音识别，从入门到实战，超简单的入门案例，超实用的企业项目。支持当前最流行的D |
| 823 | VocaHQ/vocalinux | asr | ③即时蒸馏(ASR 转写写记忆) | Free, open-source, 100% offline voice dictation for Linux. S |
| 820 | TrevorS/voxtral-mini-realtime-rs | asr | ③即时蒸馏(ASR 转写写记忆) | Voxtral ASR & TTS running natively and in the browser. A Rus |
| 814 | AlphaAvatar/AlphaAvatar | audio-llm | ③即时蒸馏(多模态理解/结构化) | A real-time interactive Omni Avatar built on LiveKit, which  |
| 805 | lobehub/lobe-tts | asr | ③即时蒸馏(ASR 转写写记忆) | 🎤 Lobe TTS - A high-quality & reliable TTS/STT library for S |
| 802 | mybigday/whisper.rn | asr | ③即时蒸馏(ASR 转写写记忆) | React Native binding of whisper.cpp. |
| 763 | fluxions-ai/vui | asr,audio-llm,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(多模态理解/结构化) / ①②采集与能量门(录音/读取/预处理) | Vui Nano — a small, context-aware text-to-speech model train |
| 755 | amanvirparhar/chaplin | asr | ③即时蒸馏(ASR 转写写记忆) | A real-time silent speech recognition tool. |
| 751 | Macoron/whisper.unity | asr | ③即时蒸馏(ASR 转写写记忆) | Running speech to text model (whisper.cpp) in Unity3d on you |
| 746 | soupslurpr/Transcribro | asr | ③即时蒸馏(ASR 转写写记忆) | Private and on-device speech recognition keyboard and servic |
| 742 | breizhn/DTLN | enhance,dsp-lib | ③即时蒸馏(降噪/分离前置) / ①②采集与能量门(录音/读取/预处理) | Tensorflow 2.x implementation of the DTLN real time speech d |
| 739 | Xiaobin-Rong/gtcrn | enhance | ③即时蒸馏(降噪/分离前置) | The official implementation of GTCRN, an ultra-lightweight S |
| 726 | rapidaai/voice-ai | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Rapida is an open-source, end-to-end voice AI orchestration  |
| 721 | omeryusufyagci/fast-music-remover | enhance,dsp-lib | ③即时蒸馏(降噪/分离前置) / ①②采集与能量门(录音/读取/预处理) | A C++ based, lightweight music and noise remover for YouTube |
| 705 | GRVYDEV/S.A.T.U.R.D.A.Y | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | A toolbox for working with WebRTC, Audio and AI |
| 689 | vilassn/whisper_android | asr | ③即时蒸馏(ASR 转写写记忆) | Offline Speech Recognition with OpenAI Whisper and TensorFlo |
| 680 | iceychris/LibreASR | asr | ③即时蒸馏(ASR 转写写记忆) | :speech_balloon: An On-Premises, Streaming Speech Recognitio |
| 650 | TheDeathDragon/LiveTranslate | asr | ③即时蒸馏(ASR 转写写记忆) | Real-time audio translation, captures system audio + mic, ru |
| 636 | woheller69/whisperIME | asr | ③即时蒸馏(ASR 转写写记忆) | Android Input Method Editor (IME) based on Whisper |
| 627 | CrispStrobe/CrispASR | asr | ③即时蒸馏(ASR 转写写记忆) | C++ ggml runtime hub for multilingual ASR and TTS models: Co |
| 614 | reriiasu/speech-to-text | asr | ③即时蒸馏(ASR 转写写记忆) | Real-time transcription using faster-whisper |
| 613 | Audio-WestlakeU/FullSubNet | enhance | ③即时蒸馏(降噪/分离前置) | PyTorch implementation of "FullSubNet: A Full-Band and Sub-B |
| 608 | dpirch/libfvad | kws-vad,dsp-lib | ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | Voice activity detection (VAD) library, based on WebRTC's VA |
| 600 | calebj0seph/spectro | dsp-lib | ①②采集与能量门(录音/读取/预处理) | 🎶 Real-time audio spectrogram generator for the web |
| 595 | hirofumi0810/neural_sp | asr | ③即时蒸馏(ASR 转写写记忆) | End-to-end ASR/LM implementation with PyTorch |
| 541 | opendilab/CleanS2S | asr | ③即时蒸馏(ASR 转写写记忆) | High-quality and streaming Speech-to-Speech interactive agen |
| 528 | ccoreilly/vosk-browser | asr | ③即时蒸馏(ASR 转写写记忆) | A speech recognition library running in the browser thanks t |
| 528 | FireRedTeam/FireRedVAD | aed,kws-vad,dsp-lib | ③即时蒸馏(声音事件/场景理解) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | A SOTA Industrial-Grade Voice Activity Detection & Audio Eve |
| 508 | gkonovalov/android-vad | aed,kws-vad,dsp-lib | ③即时蒸馏(声音事件/场景理解) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | Android Voice Activity Detection (VAD) library. Supports Web |
| 505 | alphacep/vosk | asr | ③即时蒸馏(ASR 转写写记忆) | VOSK Speech Recognition Toolkit |
| 463 | hcmlab/vadnet | kws-vad | ①常驻检测(VAD/唤醒词能量门) | Real-time Voice Activity Detection in Noisy Eniviroments usi |
| 460 | YeJe-cpu/talk-to-fengge | asr | ③即时蒸馏(ASR 转写写记忆) | Talk to 峰哥 — 克隆任何人的声音和性格，实时语音对话，工程延迟 < 1 秒 / Clone anyone's  |
| 450 | Demfier/multimodal-speech-emotion-recognition | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | Lightweight and Interpretable ML Model for Speech Emotion Re |
| 446 | AndraxDev/speak-gpt | asr | ③即时蒸馏(ASR 转写写记忆) | Your personal voice assistant based on OpenAI ChatGPT. |
| 444 | Boof2015/astra | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Audiophile music player with gapless playback, parametric EQ |
| 436 | Ikaros-521/RealtimeSTT_LLM_TTS | asr | ③即时蒸馏(ASR 转写写记忆) | 实时STT，连接OpenAI接口/智谱AI（流式LLM）和GPT-SOVITS/Edge-TTS，通过网页的方式，进行跨 |
| 425 | xifan2333/fcitx5-vinput | asr | ③即时蒸馏(ASR 转写写记忆) | Voice input for Fcitx5 — local and cloud ASR, LLM rewriting, |
| 413 | cyberofficial/Synthalingua | asr | ③即时蒸馏(ASR 转写写记忆) | Synthalingua - Real Time Translation |
| 409 | alphacep/awesome-russian-speech | asr | ③即时蒸馏(ASR 转写写记忆) | Russian speech technology links |
| 393 | altunenes/parakeet-rs | asr | ③即时蒸馏(ASR 转写写记忆) | very fast speech-to-text, diarization, streaming (even in CP |
| 383 | kstonekuan/tambourine-voice | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | Your personal voice interface for any app. Speak naturally a |
| 380 | oliverguhr/wav2vec2-live | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | A live speech recognition using Facebooks wav2vec 2.0 model. |
| 379 | mailong25/self-supervised-speech-recognition | asr | ③即时蒸馏(ASR 转写写记忆) | speech to text with self-supervised learning based on wav2ve |
| 376 | istupakov/onnx-asr | asr | ③即时蒸馏(ASR 转写写记忆) | A lightweight Python package for Automatic Speech Recognitio |
| 373 | bambocher/pocketsphinx-python | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Python interface to CMU Sphinxbase and Pocketsphinx librarie |
| 369 | jzi040941/PercepNet | enhance | ③即时蒸馏(降噪/分离前置) | Unofficial implementation of PercepNet: A Perceptually-Motiv |
| 367 | smixs/agent-second-brain | kws-vad | ①常驻检测(VAD/唤醒词能量门) | An always-on second brain you talk to. Voice notes in Telegr |
| 350 | haoxiangsnr/A-Convolutional-Recurrent-Neural-Network-for-Real-Time-Speech-Enhancement | enhance | ③即时蒸馏(降噪/分离前置) | A minimum unofficial implementation of the "A Convolutional  |
| 346 | estebanstifli/LocalText2Voice | dsp-lib | ①②采集与能量门(录音/读取/预处理) | A complete local production workflow for clean narration, st |
| 341 | Renovamen/Speech-and-Text | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | Speech to text (PocketSphinx, Iflytex API, Baidu API) and te |
| 341 | oboroge0/hayamimi | asr | ③即时蒸馏(ASR 转写写记忆) | 早耳 - Real-time multilingual speech-to-text on CPU only. Live |
| 339 | deeeed/audiolab | dsp-lib | ①②采集与能量门(录音/读取/预处理) | Cross-platform audio processing SDK for React Native — strea |
| 328 | seanwood/gcc-nmf | enhance | ③即时蒸馏(降噪/分离前置) | Real-time GCC-NMF Blind Speech Separation and Enhancement |
| 324 | mahimairaja/voiceai | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | Set of 📝 with 🔗 to help those building Voice AI agents 🎙️🤖 |
| 317 | jishengpeng/WavChat | audio-llm | ③即时蒸馏(多模态理解/结构化) | A Survey of Spoken Dialogue Models (60 pages) |
| 315 | sayksii/Aria | asr | ③即时蒸馏(ASR 转写写记忆) | ARIA - AI Realtime Intelligent Audio / Universal real-time A |
| 314 | thewh1teagle/sherpa-rs | asr | ③即时蒸馏(ASR 转写写记忆) | Rust bindings to https://github.com/k2-fsa/sherpa-onnx |
| 313 | lRomul/argus-freesound | aed | ③即时蒸馏(声音事件/场景理解) | Kaggle / 1st place solution for Freesound Audio Tagging 2019 |
| 304 | Frikallo/parakeet.cpp | asr | ③即时蒸馏(ASR 转写写记忆) | Ultra fast and portable Parakeet implementation for on-devic |
| 302 | gtreshchev/RuntimeSpeechRecognizer | asr | ③即时蒸馏(ASR 转写写记忆) | Cross-platform, real-time, offline speech recognition plugin |
| 296 | kouhxp/yapsnap | asr | ③即时蒸馏(ASR 转写写记忆) | Snap any video URL or audio file into plaintext. No GPU. No  |
| 295 | narcotic-sh/senko | kws-vad | ①常驻检测(VAD/唤醒词能量门) | Very fast, accurate speaker diarization |
| 293 | lucianodato/speech-denoiser | enhance | ③即时蒸馏(降噪/分离前置) | A speech denoise lv2 plugin based on RNNoise library |
| 278 | devnen/Kitten-TTS-Server | enhance | ③即时蒸馏(降噪/分离前置) | Self-host the ultra-lightweight Kitten TTS model with this e |
| 277 | m3hrdadfi/soxan | asr,aed | ③即时蒸馏(ASR 转写写记忆) / ③即时蒸馏(声音事件/场景理解) | Wav2Vec for speech recognition, classification, and audio cl |
| 275 | voicekit-team/T-one | asr | ③即时蒸馏(ASR 转写写记忆) | T-one is a high-performance streaming ASR pipeline for Russi |
| 268 | QuintinShaw/openasr | asr | ③即时蒸馏(ASR 转写写记忆) | Local-first speech-to-text: no cloud, no telemetry, fail-clo |
| 267 | ASR-project/Multilingual-PR | asr | ③即时蒸馏(ASR 转写写记忆) | Phoneme Recognition using pre-trained models Wav2vec2, HuBER |
| 257 | asiff00/On-Device-Speech-to-Speech-Conversational-AI | asr,kws-vad | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) | This is an on-CPU real-time conversational system for two-wa |
| 252 | whitphx/streamlit-stt-app | asr | ③即时蒸馏(ASR 转写写记忆) | Real time web based Speech-to-Text app with Streamlit |
| 251 | HKAllThingsLink/streaming-asr | asr,kws-vad,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①常驻检测(VAD/唤醒词能量门) / ①②采集与能量门(录音/读取/预处理) | A lightweight client-server system for real-time audio proce |
| 248 | XiaoMi/kaldi-onnx | asr | ③即时蒸馏(ASR 转写写记忆) | Kaldi model converter to ONNX |
| 233 | hyperconnect/TC-ResNet | kws-vad | ①常驻检测(VAD/唤醒词能量门) | Code for Temporal Convolution for Real-time Keyword Spotting |
| 228 | pszemraj/vid2cleantxt | asr | ③即时蒸馏(ASR 转写写记忆) | Python API & command-line tool to easily transcribe speech-b |
| 217 | Kaljurand/dictate.js | asr | ③即时蒸馏(ASR 转写写记忆) | A small Javascript library for browser-based real-time speec |
| 211 | ChetanXpro/nodejs-whisper | asr | ③即时蒸馏(ASR 转写写记忆) | NodeJS Bindings for Whisper - the CPU version of OpenAI's Wh |
| 206 | streamcoreai/streamcore-server | asr,dsp-lib | ③即时蒸馏(ASR 转写写记忆) / ①②采集与能量门(录音/读取/预处理) | Open-source realtime voice agent server in Go with WebRTC (W |

## 6. 适配度最高但被判 ref 的代表（说明为何不标 core）

| star | 仓库 | 类别 | 降级原因(fit_notes) |
|---:|---|---|---|
| 165390 | huggingface/transformers | asr,ml-framework | funnel-cat:asr；no-on-device-signal(C1?) |
| 123134 | harry0703/MoneyPrinterTurbo | tts,dsp-lib | funnel-cat:dsp-lib；no-on-device-signal(C1?) |
| 76104 | unslothai/unsloth | tts,agent,agent-llm | out-of-scope(laos只听不说/不生成音乐) |
| 61770 | RVC-Boss/GPT-SoVITS | tts | out-of-scope(laos只听不说/不生成音乐) |
| 60131 | CorentinJ/Real-Time-Voice-Cloning | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 58248 | calesthio/OpenMontage | tts,agent,dsp-lib | vision/multimodal-agent(not-audio-pipeline) |
| 54243 | microsoft/VibeVoice | tts | out-of-scope(laos只听不说/不生成音乐) |
| 54074 | hugohe3/ppt-master | agent | orchestration/eval-not-funnel-component |
| 53113 | jamiepine/voicebox | asr,tts | funnel-cat:asr；needs-gpu(C1✗) |
| 49110 | moeru-ai/airi | agent | orchestration/eval-not-funnel-component |
| 49094 | mudler/LocalAI | tts | out-of-scope(laos只听不说/不生成音乐) |
| 46006 | coqui-ai/TTS | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 39833 | 2noise/ChatTTS | tts,audio-llm,agent,dsp-lib | funnel-cat:dsp-lib；no-on-device-signal(C1?) |
| 37512 | myshell-ai/OpenVoice | tts | out-of-scope(laos只听不说/不生成音乐) |
| 37053 | OpenBMB/VoxCPM | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 36965 | mpv-player/mpv | dsp-lib | funnel-cat:dsp-lib；no-on-device-signal(C1?) |
| 36930 | google-ai-edge/mediapipe | serving | orchestration/eval-not-funnel-component |
| 36910 | babysor/MockingBird | tts,ml-framework | out-of-scope(laos只听不说/不生成音乐) |
| 32671 | fishaudio/fish-speech | tts | out-of-scope(laos只听不说/不生成音乐) |
| 29238 | ossrs/srs | codec,dsp-lib | media-server/transport-infra(not-on-device) |
| 28442 | deezer/spleeter | enhance,ml-framework | funnel-cat:enhance；no-on-device-signal(C1?) |
| 28110 | svc-develop-team/so-vits-svc | music,ml-framework | out-of-scope(laos不做音乐/music-transcription) |
| 28076 | ATH-MaaS/Pixelle-Video | tts | out-of-scope(laos只听不说/不生成音乐) |
| 28001 | mastra-ai/mastra | tts | out-of-scope(laos只听不说/不生成音乐) |
| 27202 | Fosowl/agenticSeek | agent,agent-llm | orchestration/eval-not-funnel-component |

## 7. unrelated 样本（与 laos 漏斗无关，来自补抓泄漏复核）

共 728 条。Top10：
| star | 仓库 | 类别 | 命中原因 |
|---:|---|---|---|
| 26915 | Igglybuff/awesome-piracy | - | no-funnel-category(unrelated) |
| 23987 | processing/p5.js | - | no-funnel-category(unrelated) |
| 18433 | Huanshere/VideoLingo | - | no-funnel-category(unrelated) |
| 18413 | audacity/audacity | - | no-funnel-category(unrelated) |
| 18037 | mahmoud/awesome-python-applications | - | no-funnel-category(unrelated) |
| 17244 | koel/koel | - | no-funnel-category(unrelated) |
| 12130 | sonic-pi-net/sonic-pi | - | no-funnel-category(unrelated) |
| 12021 | SFML/SFML | - | no-funnel-category(unrelated) |
| 11854 | facebookresearch/seamless_communication | - | no-funnel-category(unrelated) |
| 11351 | File-New-Project/EarTrumpet | - | no-funnel-category(unrelated) |

## 8. 局限与需人工复核

- 分类完全依赖作者自填的 topics + description 文本，_topic 标签噪声_会导致漏标/错标（例如只打 `llm` 未打 `audio` 的音频仓库可能被错分）。
- laos_fit 的 C1（端侧 CPU）靠关键词信号近似，未实测 proot aarch64 上能否真正跑通；silero/sherpa-onnx/whisper.cpp 等经 SER 04 §8 论证可行，其余需实测。
- C3 许可因 75%% 语料缺 license 字段无法逐条判定，core 仅排除「云 API wrapper」类，不保证全部可商用；落地前须逐条核 SPDX。
- `music` / `tts` 一律判 ref 属产品范围决策（laos 只听不说），非技术不可行；若未来 laos 加语音播报，tts 类需重估。
- 最不可靠部分：**speaker 类「隐私红线」判定是策略性一律降级**，未区分纯 diarization（分割，可借鉴）与声纹注册（verification，碰红线）；若有项目仅做流式 diarization 分割，应人工复核后上调为 core 候选。
