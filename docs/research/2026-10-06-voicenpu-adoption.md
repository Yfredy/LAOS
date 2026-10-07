# voicenpu_engine（RK3576 语音系统）复现与采纳

> 调研日期：2026-10-06 · 来源：小红书笔记《RK3576语音系统实现功能列表》（笔记 ID 6a7d8501000000002202f2f5）→ 仓库 https://gitee.com/bravexyz/voicenpu_engine.git（AGPL-3.0）

## 一、来源与取件

- 笔记正文：up主称业务代码约 5500 行、依赖约 2G、计划开源、依赖包从 RK 官方库下载；文末直接给出 Gitee 链接。
- up主 Gitee 账号 **bravexyz**（"brave"），公开仓库 2 个：**voicenpu_engine**（本报告主体，克隆成功，13 个 .cpp + 20 个 .h，src 3631 行）与 TimsFM_FDformer（**克隆认证失败=私有仓库**，故障诊断方向，与语音无关，仅记录）。
- 本地 clone 注意：TUN 代理（127.0.0.1:7897）劫持 git 全局配置导致 gitee 直连失败；`git -c http.proxy= -c https.proxy= clone` 绕过后成功。仓库全文已在 var/repro/voicenpu_engine（gitignored 运行期资产）。
- **许可与复现方式声明**：上游 AGPL-3.0。本仓库的复现是**语义级独立实现**（读源码理解算法与协议语义后用 Python 重写，无代码拷贝），测试 fixture 摘录上游 knowledge/company_knowledge.jsonl 前 6 条（数据摘录，来源已注明）。

## 二、上游系统全景（源码通读结论）

**定位**：RK3576/RK3588 端侧离线/在线语音对话引擎，纯 C++17 + ROS2 Humble + PREEMPT_RT。README 口径：端到端首音 1.44s、常驻 1951MB、ASR 端点到最终文本 ~88ms。

**单节点五个 ROS2 topic**：/asr/audio（AEC 后 16k PCM）、/asr/text（ASR 终稿）、/audio/aec_ready（transient_local）、/tts/text、/tts/audio（44.1k int16）。

**音频链路**（M1066 USB 全双工声卡）：
```
capture 16k/mono ──AEC3(webrtc: ProcessReverseStream 48k/stereo 参考延迟40ms
                     +高通+NS level2)──▶ KWS(sherpa-onnx zipformer transducer
                     wenetspeech 3.3M, "小乐") ──▶ VAD(Silero, thr 0.5,
                     min_sil 0.2s) ──▶ 流式 Zipformer(RKNN×3: enc/dec/join)
                     ──▶ 终稿 ──▶ DialogController
TTS 音频 44.1k ──libsamplerate(SINC_FASTEST)──▶ 48k/stereo 播放（PCM 音量135/147）
```
**对话链路**：WakeGate 四态会话机（唤醒=电源键，KWS-only，文本永不唤醒；休眠词"小乐休息/小乐再见"；follow-up 12s / 会话 120s / 6 轮上限；barge-in 仅 AEC ready 后启用）→ 声控模式切换（松散意图解析）→ 知识库短路（JSONL bigram 检索，阈值 0.58，命中绕过 LLM）→ RKLLM Qwen3-VL-2B（w4a16，流式按标点切句、TTS 语音清洗）→ TtsRouter 双后端（在线豆包 Seed-TTS-2.0 双向 wss / 离线 MeloTTS RKNN，失败降级+句中不换声线）。

**调度三机制（精华）**：
1. **generation 版本化打断**——interrupt() 递增代数 + abort LLM/cancel TTS，所有流式回调逐块核对代数，过期回答宁可丢不可播；
2. **投机 prefill + PAUSE 续说合并**——句中停顿 ≥500ms 观察窗即提前启动 LLM prefill，TTS 提交等 commit 窗；窗口内语音恢复且累计 ≥96ms×16 采样则取消投机轮（浪费 token 记指标），新旧句以"，"合并重新入队；commit 判定在 resume 候选时延长 200ms；
3. **latest-only 队列**——新话语入队清空全部排队任务，人只关心最新一句。

**线程拓扑**：audio FIFO 45 @CPU7 / asr FIFO 40 @CPU7 / dialog SCHED_OTHER @CPU4；锁-free SPSC 环形队列（音频 160 帧/结果队列），overrun 自愈=清队列+reset ASR。

**设备自愈**：ALSA EPIPE/ESTRPIPE/EIO → snd_pcm_recover；USB reset ENODEV → close+200ms 重开循环；任何渲染断流 → AEC3 重置 + 重新收敛（100 活跃渲染帧 + 50 稳定捕获帧才重新放行 barge-in）。无 AEC 时半双工保护：播报期间+400ms guard 锁麦克风。

**指标**：dialog_metrics.jsonl 逐轮记录 route/knowledge_id/retrieval_ms/first_text_ms/first_audio_ms/prefill_ms/generate_ms/tokens/memory_mb/total_ms/pause_observation_ms/speculative_cancelled/merged_segments/speculative_tokens_wasted + ASR 侧 vad_ms/zipformer_ms/endpoint_to_final_ms/rtf。

## 三、复现可行性分层裁决

| 层 | 上游实现 | 复现方式 |
|---|---|---|
| 纯逻辑控制面 | wake_gate.h / voice_scheduler.cpp / dialog_controller.cpp / knowledge_retriever.cpp / rkllm_qwen.cpp(切句清洗) / melo_tts.cpp(数字归一化) / tts_backend.h(TtsRouter) | **● 已复现进 laos 主库**（Python 语义重写，零依赖，见 §四） |
| KWS/VAD 推理 | sherpa-onnx C API（Windows 有官方库与模型） | ◐ 驱动子进程模式可实测（本波未做，见 §六） |
| 豆包 TTS 协议 | libwebsockets 双向二进制 wss（帧头 0x11 0x14 0x10 0x00，事件码 1/2/100/101/102/50/150-153/200/352） | ◐ 协议语义已记录；无 API key 不实测合成 |
| Zipformer/MeloTTS/Qwen3 RKNN | librknnrt 2.3.2（aarch64 NPU-only） | ○ 不可复现；laos 已有替身三通道（funasr/SenseVoice zh 主力 + whistle 轻备 + server），TTS 可用 SAPI/豆包协议 |
| ALSA M1066 全双工 / AEC3 / PREEMPT_RT | Linux USB 声卡 + webrtc-audio-processing | ○ 需真机；音频合同（16k 采/48k 放/40ms 延迟/NS2）与自愈语义进文档 |

## 四、laos 落地（本波交付）

| 新模块 | 复现自 | 测试 |
|---|---|---|
| `laos/wakegate.py` | wake_gate.h 四态会话机（可注入时钟） | tests/test_wakegate.py（12 例：全迁移路径/超时/轮数/barge-in/文本永不唤醒） |
| `laos/dialogsched.py` | GenerationGate + PauseWindow + DialogQueue + MicrophoneGate + parse_mode_request + TtsRouter | tests/test_dialogsched.py（23 例：打断代数/合并/窗口延长 200ms/latest-only/半双工/降级不换声线） |
| `laos/knowledge.py` | knowledge_retriever.cpp（bigram 0.7/0.3 双向覆盖+子串=1.0+交集≥2+阈值） | tests/test_knowledge.py（11 例，fixture=上游真数据前 6 条；公式精查 0.666…/阈值闸/交集下限） |
| `laos/speechchunk.py` | speech_chunk_end（字节级：标点即切/15 字节后逗号/14 字兜底）+ clean_for_speech（剥前缀/<think>/markdown/序号/Qwen 本地化/分号→，或者）+ normalize_digits_for_speech（数字→汉字/全角/时刻点） | tests/test_speechchunk.py（16 例，字节语义精查） |
| `tests/test_dialog_e2e.py` | —— 五件组装成完整控制环（唤醒→过闸→声控短路/知识短路/LLM 流→切句清洗→TTS 路由降级→generation 打断→半双工 guard→指标行） | 9 例闭环（上游真知识库答案被切成 5 句流式播报、在线失败降离线、休眠词关会话等） |

**测试：63 + 9 = 72 例新增，全套 573 全绿（501 → 573）。**

## 五、与 laos 既有能力的对照

- **generation 打断** × laos turnpolicy/turnbuf（2026-10-05 speech-weekly 落地的 duplex 判断）：voicenpu 的"代数+逐块准入检查"是 turnpolicy 缺的执行机构——两者正交可组合（turnpolicy 决定何时打断，GenerationGate 保证打断后的陈旧产出不外泄）。
- **知识库短路** × laos MemoryStore/journal：JSONL+bigram 检索是记忆问答的最廉价前置层，0.58 阈值与交集≥2 下限的设计（防两个字面撞车的误命中）可直接用于 journal 历史问答。
- **WakeGate** × laos 隐私红线：唤醒只由端侧 KWS 音频触发、文本永不唤醒、会话有期限——与 laos "录音只由显式 syscall 触发"的审计哲学同构（会话=权限窗口）。
- **投机 prefill**：laos 尚无 LLM 通道，此机制先入库备用；与 confgate 的置信分流互补（confgate 决定去云/本地，投机窗口决定"敢不敢提前说"）。

## 六、后续建议（未做，按价值排序）

1. **sherpa-onnx KWS 实测**（Windows 官方库 + wenetspeech-zipformer 3.3M 模型，ModelScope 可取）——唤醒词"小乐"词表格式已从上游 wake_keywords.txt 拿到（`x iǎo l è @小乐` 拼音流），laos 唤醒层（drv 侧）即可闭环；
2. **豆包 TTS 协议驱动**（帧编解码纯逻辑已可从 §二复写；需要用户提供 API key 才能实测）——补 laos TTS 能力面的在线通道；
3. **AEC3/音频合同**落 laos 驱动文档（16k 采/48k 放/40ms 参考延迟/断流重收敛门槛），为未来真机（或 WSL USB 声卡）铺路；
4. 上游 metrics 字段口径（speculative_tokens_wasted 等）吸收进 laos 审计事件设计。
