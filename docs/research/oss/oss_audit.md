# OSS 语料审计与去噪报告

**语料来源**: `docs/research/corpus/oss_corpus.json`
**审计日期**: 2026-09-14
**总仓库数（去重）**: 3529

## 1. 相关性判据（可解释规则）

一条仓库「音频相关」当且仅当其 `full_name` / `description` / `topics` 命中以下任意音频域词（不区分大小写）：

> audio, sound, speech, voice, tts, asr, acoustic, whisper, sonic, hearing, music, voicebot, wake-word, vad, diariz*, vocoder, spectrogram, vocal, speaker, noise, echo, mel, wav, mp3, pcm, microphone, singing, karaoke

8 个 `topic:` 切片因 topic 标签本身含 audio/speech/voice 等词，按此判据必为 100%% 相关，直接复用；`audio-llm` / `voice-agent` 两切片原为裸关键词全文检索，被 GitHub 拆词匹配混入通用高星仓库，须逐条重筛。

## 2. 各切片条数与相关率

| 切片 | 命中条数 | 相关条数 | 相关率 |
|---|---:|---:|---:|
| audio-llm（需重筛） | 1000 | 205 | 20% |
| voice-agent（需重筛） | 1000 | 155 | 16% |
| audio（干净复用） | 651 | 651 | 100% |
| tts（干净复用） | 539 | 539 | 100% |
| asr（干净复用） | 479 | 479 | 100% |
| speech（干净复用） | 193 | 193 | 100% |
| voice-assistant（干净复用） | 156 | 156 | 100% |
| diarization（干净复用） | 100 | 100 | 100% |
| enhancement（干净复用） | 97 | 97 | 100% |
| audio-processing（干净复用） | 96 | 96 | 100% |

## 3. 去噪结果

- 保留（写 `repos_raw.jsonl`，已按 full_name 去重）：**2153 条**
  - 其中来自两脏切片、经重筛确认为真相关的：**189 条**
- 剔除噪声（写 `noise_dropped.jsonl`）：**1376 条**
  - 全部来自 `audio-llm` / `voice-agent` 两裸关键词切片，且未命中音频域判据。

## 4. 被剔除的高星仓库（用户可能质疑，单独列示）

这些仓库 star 很高但**与音频无关**，原样入榜会得出「高星音频项目其实和音频无关」的错结论，故剔除：

| star | 仓库 | 切片 | 剔除原因 |
|---:|---|---|---|
| 479673 | public-apis/public-apis | audio-llm,voice-agent | 未命中音频域判据 |
| 389598 | openclaw/openclaw | voice-agent | 未命中音频域判据 |
| 320390 | vinta/awesome-python | audio-llm,voice-agent | 未命中音频域判据 |
| 318968 | awesome-selfhosted/awesome-selfhosted | audio-llm,voice-agent | 未命中音频域判据 |
| 257576 | affaan-m/ECC | audio-llm,voice-agent | 未命中音频域判据 |
| 245098 | NousResearch/hermes-agent | audio-llm,voice-agent | 未命中音频域判据 |
| 243519 | trimstray/the-book-of-secret-knowledge | voice-agent | 未命中音频域判据 |
| 184019 | avelino/awesome-go | audio-llm,voice-agent | 未命中音频域判据 |
| 183512 | microsoft/markitdown | audio-llm | 未命中音频域判据 |
| 152085 | msitarzewski/agency-agents | audio-llm,voice-agent | 未命中音频域判据 |
| 151868 | open-webui/open-webui | voice-agent | 未命中音频域判据 |
| 137885 | Shubhamsaboo/awesome-llm-apps | audio-llm,voice-agent | 未命中音频域判据 |
| 137263 | ripienaar/free-for-dev | audio-llm,voice-agent | 未命中音频域判据 |
| 132843 | garrytan/gstack | voice-agent | 未命中音频域判据 |
| 132640 | farion1231/cc-switch | audio-llm | 未命中音频域判据 |
| 128096 | ggml-org/llama.cpp | audio-llm | 未命中音频域判据 |
| 116362 | Graphify-Labs/graphify | audio-llm | 未命中音频域判据 |
| 115663 | VoltAgent/awesome-design-md | audio-llm,voice-agent | 未命中音频域判据 |
| 113706 | jaywcjlove/awesome-mac | audio-llm,voice-agent | 未命中音频域判据 |
| 95901 | nexu-io/open-design | audio-llm | 未命中音频域判据 |
| 94895 | punkpeye/awesome-mcp-servers | audio-llm,voice-agent | 未命中音频域判据 |
| 93383 | ruvnet/RuView | audio-llm,voice-agent | 未命中音频域判据 |
| 89210 | MunGell/awesome-for-beginners | audio-llm | 未命中音频域判据 |
| 83488 | Developer-Y/cs-video-courses | audio-llm,voice-agent | 未命中音频域判据 |
| 83095 | unclecode/crawl4ai | audio-llm | 未命中音频域判据 |

## 5. 下一步

- 用引号短语 / `topic:` 精准补抓（Task 2 Step 3），找回被噪声稀释的真音频项目。
- 补抓结果按 `full_name` 去重并入 `repos_raw.jsonl`（Task 2 Step 4）。