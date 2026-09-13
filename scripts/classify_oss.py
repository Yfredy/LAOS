#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Task 3: 给 repos_raw.jsonl 打 category 与 laos_fit 两字段，并产出分类体系文档。

设计原则（可解释、可复现，非主观逐个挑选）：
  * category 用 topics / description / name 的规则匹配，可多标签。
  * laos_fit 用「laos 四段漏斗硬约束」驱动：
      C1 端侧 CPU 可跑（proot Ubuntu glibc aarch64，无 NPU，仅 CPU，400-1000mW）
      C2 低延迟/可流式（漏斗③即时蒸馏）
      C3 许可可商用/可自托管（本地优先）
      C4 不依赖云 API
      C5 不存声纹（隐私红线）
  * 档位：
      core  - 直接可作 laos 链路组件（进四段漏斗①②③），满足 C1+C2+C4 且非 C5
      ref   - 与 laos 同域或架构可借鉴，但组件本身不直接落地
      unrelated - 与 laos 常驻音频采集+蒸馏漏斗无关
  * 每条 core/ref 都写 fit_notes（命中的规则），便于人工复核与复现。

输入: docs/research/oss/repos_raw.jsonl
输出: docs/research/oss/repos_classified.jsonl
      docs/research/oss/classification_system.md
"""
import json, io, os, re, sys, collections, statistics

BASE = r"C:/Users/yaoyue/CodeBuddy/Claw/laos/docs/research/oss"
SRC = os.path.join(BASE, "repos_raw.jsonl")
DST = os.path.join(BASE, "repos_classified.jsonl")
DOC = os.path.join(BASE, "classification_system.md")

# ---------------------------------------------------------------------------
# 1. 分类体系（14 类，可多标签）。规则全部基于 name/description/topics 正则。
#    注意：前缀词（separat/transcri/enhance/recogni...）只用「前导 \b」，
#    不用「尾随 \b」——否则 separation/transcription/enhancement 因词内无边界而漏匹配。
# ---------------------------------------------------------------------------
CATEGORY_RULES = {
    "asr":        r"(?i)\b(asr|speech[- ]?to[- ]?text|transcri\w*|whisper|recogni\w*|stt|wav2vec|vosk|deepspeech)\b",
    "tts":        r"(?i)\b(text[- ]?to[- ]?speech|\btts\b|vocoder|speech synthesis|voice clone\w*|voice generation|speech generation|voice ai|coqui)\b",
    "audio-llm":  r"(?i)\b(audio[- ]?(?:llm|language model)|speech[- ]?llm|speech translation|\bspeech model\b|foundational (?:speech|audio)|omni(?:-?modal)?|multimodal (?:audio|speech)|audio (?:gpt|chat)|sound (?:llm|language))\b",
    "enhance":    r"(?i)\b(denois\w*|enhance\w*|dereverberat\w*|noise (?:reduction|suppress\w*|remov\w*)|separat\w*|source separation|beamform\w*|echo cancell\w*|isolation)\b",
    "aed":        r"(?i)\b(audio tagging|sound event\w*|acoustic scene|audio classification|event detection|yamnet|panns)\b",
    "codec":      r"(?i)\b(codec|encodec|audio compress\w*|opus|soundstream|neural codec|quantiz\w* audio)\b",
    "kws-vad":    r"(?i)\b(keyword spotting|wake[- ]?word|voice activity|\bvad\b|hotword|always[- ]?on|porcupine|pocketsphinx)\b",
    "speaker":    r"(?i)\b(speaker (?:verification|diarization|identification|recognition)|voiceprint|\bspk\b|ecapa|resemblyzer)\b",
    "agent":      r"(?i)\b(agent|assistant|conversational|voicebot|realtime (?:voice|audio)|copilot|companion|autonomous|agentic)\b",
    "serving":    r"(?i)\b(serving|inference server|runtime|onnxruntime|\btensorrt\b|vllm|\bpipeline\b|deploy\w*|microservice)\b",
    "dsp-lib":    r"(?i)\b(ffmpeg|librosa|soundfile|audio (?:library|processing|io)|dsp|pyaudio|sox|webrtc|torchaudio|audiomentations)\b",
    "music":      r"(?i)\b(music (?:generation|source|separation)|midi|song|singing|beat|bach|suno|udio)\b",
    "dataset":    r"(?i)\b(dataset|corpus|benchmark|commons|librispeech|thchs)\b",
    "ml-framework": r"(?i)\b(transformers|diffusers|\bpytorch\b|model[- ]?hub|hugging ?face|llama\.cpp|mlc-?llm|stable diffusion|tensorflow)\b",
}
CAT = {k: re.compile(v) for k, v in CATEGORY_RULES.items()}

# ---------------------------------------------------------------------------
# 2. laos 硬约束信号
# ---------------------------------------------------------------------------
# 端侧 / CPU / 轻量 / 流式 正向信号（C1+C2）
ON_DEVICE_RE = re.compile(
    r"(?i)(whisper\.cpp|sherpa|silero|onnxruntime|\bonnx\b|funasr|sensevoice|"
    r"piper|kokoro|webrtc|rnnoise|speex|pocketsphinx|vosk|"
    r"edge-?tts|on-?device|on device|edge\b|lightweight|real-?time|realtime|"
    r"streaming|audio tagging|yamnet|\bggml\b|tensorflow lite|\btflite\b|"
    r"mobile\b|tiny\b|\bcpu\b|wav2vec)")

# 云端 API wrapper 负向信号（违反 C4）——命中则即便功能对口也不算 core
CLOUD_RE = re.compile(
    r"(?i)(requires an api|api key|cloud (?:api|service|speech|transcription)|"
    r"\bsaas\b|hosted|twilio|elevenlabs|picovoice|azure (?:speech|cognitive)|google cloud|"
    r"amazon transcribe|aws (?:transcribe|polly)|openai (?:api|whisper api|gpt)|"
    r"\bgroq\b|replicate|huggingface inference|serverless|paid api|commercial api|"
    r"sign up|subscribe|rest api|webhook)")

# 媒体服务器 / 传输基础设施——不是端侧组件，判 ref（架构借鉴）
SERVER_RE = re.compile(
    r"(?i)(media server|\bsfu\b|realtime (?:media|communication) server|"
    r"signaling server|streaming server|webrtc server|rtc (?:server|platform)|"
    r"streaming platform|sip server)")

# Apple/iOS/macOS-only（错误硬件：laos 跑在 Android + proot，无 Apple ML 栈）
APPLE_RE = re.compile(r"(?i)(ios|iphone|ipad|apple|coreml|macos|swiftui|objective-?c)")
APPLE_LANGS = {"Swift", "Objective-C", "Objective-C++"}

# 教学 / 列表 / 示例 仓库——不是可部署组件，判 ref
EDU_RE = re.compile(
    r"(?i)((?:^|[-_ ])(tutorial|introduction|book|cheatsheet|examples?|demo|sample|template)|"
    r"^(awesome|learn|awesome-|rust-audio)-|introduction to |a (?:book|course|tutorial) )")

# 需要 GPU / 重型训练的负向信号（违反 C1）
HEAVY_RE = re.compile(
    r"(?i)(\bcuda\b|gpu (?:accelerat|required|inference)|pytorch (?:lightning)? training|"
    r"distributed training|fine-?tun\w* (?:llm|large)|train (?:a|your) (?:model|llm))")

# 能映射进四段漏斗的「功能对口」类别（这些类别里的仓库才可能是 core）
#   kws-vad     -> ①常驻检测
#   asr         -> ③即时蒸馏
#   enhance     -> ③即时蒸馏（前置降噪）
#   aed         -> ③即时蒸馏（声音事件理解）
#   audio-llm   -> ③即时蒸馏（理解/结构化）
#   dsp-lib     -> ①② 采集/能量门
FUNNEL_CORE_CATS = {"kws-vad", "asr", "enhance", "aed", "audio-llm", "dsp-lib"}

# 这些类别即便功能相关也不标 core（原因见下）：
#   codec   -> ②捕获压缩，可选非必需（原音频即焚，不常驻），判 ref
#   speaker -> 触碰 C5 隐私红线（声纹/说话人识别），仅 diarization 分割可借鉴，判 ref
#   tts     -> laos 只听不说，语音合成不在漏斗内，判 ref（out-of-scope）
#   music   -> 音乐生成不在 laos 听感蒸馏范围，判 ref（out-of-scope）
#   agent   -> 编排/对话框架，非漏斗组件，判 ref
#   serving -> 推理服务基础设施，判 ref
#   dataset -> 评测/训练数据，判 ref
OUT_OF_CORE_CATS = {"codec", "speaker", "tts", "music", "agent", "serving", "dataset"}

# core 成熟度门槛（stars）——低于此值视为玩具/未成熟，降级 ref。可审计阈值。
CORE_STAR_MIN = 200

# 漏斗落点映射（仅 core 用）
STAGE_MAP = {
    "kws-vad": "①常驻检测(VAD/唤醒词能量门)",
    "dsp-lib": "①②采集与能量门(录音/读取/预处理)",
    "asr": "③即时蒸馏(ASR 转写写记忆)",
    "enhance": "③即时蒸馏(降噪/分离前置)",
    "aed": "③即时蒸馏(声音事件/场景理解)",
    "audio-llm": "③即时蒸馏(多模态理解/结构化)",
}


def text_of(r):
    return " ".join([r.get("full_name", ""), r.get("description", ""),
                     " ".join(r.get("topics") or [])]).lower()


def classify(r):
    t = text_of(r)
    cats = [k for k, rx in CAT.items() if rx.search(t)]
    # llm 话题且带 agent 时补 agent-llm（仅用于检索，不计主类统计冲突）
    if ("llm" in (r.get("topics") or []) or "llm" in r.get("full_name", "").lower()) \
            and ("agent" in cats or "audio-llm" in cats):
        cats.append("agent-llm")
    return cats


def fit(r, cats):
    t = text_of(r)
    notes = []
    stars = r.get("stars", 0)
    lang = r.get("language") or ""
    name = r.get("full_name", "").lower()

    # 先排除「非可部署组件」：教学/列表/示例、媒体服务器、Apple-only
    if EDU_RE.search(name) or EDU_RE.search(t[:120]):
        notes.append("educational/list/not-deployable")
        return "ref", notes
    if SERVER_RE.search(t):
        notes.append("media-server/transport-infra(not-on-device)")
        return "ref", notes
    if lang in APPLE_LANGS or (APPLE_RE.search(t) and "android" not in t and "cross-platform" not in t):
        notes.append("apple/ios-only(hw-mismatch: laos=Android+proot)")
        return "ref", notes
    # laos 是纯音频 Agent；视觉/视频 Agent 框架不是其漏斗组件
    if "agent" in cats and ("video" in t or "computer vision" in t or "vision model" in t):
        notes.append("vision/multimodal-agent(not-audio-pipeline)")
        return "ref", notes

    # 能映射进四段漏斗的「理解类」类别（audio-llm 若同时带 tts/music 视为生成模型，排除）
    # 音乐生成/转写不在 laos 听感蒸馏范围（laos 只听不说、不做音乐），一律 out-of-scope
    if "music" in cats:
        notes.append("out-of-scope(laos不做音乐/music-transcription)")
        return "ref", notes
    understanding = {"kws-vad", "asr", "enhance", "aed", "dsp-lib"}
    if "audio-llm" in cats and "tts" not in cats:
        understanding.add("audio-llm")
    core_cats = [c for c in cats if c in understanding]
    if core_cats:
        # webrtc-only 传输库不是音频组件（laos 本地采集，不需要传输栈）
        if core_cats == ["dsp-lib"] and "webrtc" in t \
                and not any(k in t for k in ("ffmpeg", "pyaudio", "librosa",
                                             "audio processing", "sox", "torcha")):
            notes.append("webrtc-transport-only(not-audio-component)")
            return "ref", notes
        notes.append("funnel-cat:" + "/".join(core_cats))
        cloud = bool(CLOUD_RE.search(t))
        heavy = bool(HEAVY_RE.search(t))
        ondev = bool(ON_DEVICE_RE.search(t))
        if cloud:
            notes.append("cloud-api-wrapper(C4✗)")
            return "ref", notes
        if heavy and not ondev:
            notes.append("needs-gpu(C1✗)")
            return "ref", notes
        if not ondev:
            notes.append("no-on-device-signal(C1?)")
            return "ref", notes
        if stars < CORE_STAR_MIN:
            notes.append("stars<%d(immature)" % CORE_STAR_MIN)
            return "ref", notes
        notes.append("on-device✓ streaming-ok✓ no-cloud✓ stars>=%d✓" % CORE_STAR_MIN)
        return "core", notes
    # 功能不对口：按是否同域给 ref / unrelated
    if any(c in OUT_OF_CORE_CATS for c in cats) or "ml-framework" in cats:
        if "tts" in cats or "music" in cats:
            notes.append("out-of-scope(laos只听不说/不生成音乐)")
        elif "speaker" in cats:
            notes.append("privacy-red-line(声纹/C5)")
        elif "codec" in cats:
            notes.append("optional-not-core(原音频即焚)")
        elif "ml-framework" in cats:
            notes.append("ml-framework(ref: 模型底座非组件)")
        else:
            notes.append("orchestration/eval-not-funnel-component")
        return "ref", notes
    # 没有任何音频功能类别命中 -> 与 laos 漏斗无关
    notes.append("no-funnel-category(unrelated)")
    return "unrelated", notes


def stage_of(cats):
    stages = [STAGE_MAP[c] for c in cats if c in STAGE_MAP]
    return " / ".join(stages)


def median(xs):
    return int(statistics.median(xs)) if xs else 0


def main():
    rows = [json.loads(l) for l in io.open(SRC, encoding="utf-8") if l.strip()]
    out = []
    for r in rows:
        cats = classify(r)
        f, notes = fit(r, cats)
        rec = dict(r)
        rec["category"] = cats
        rec["laos_fit"] = f
        rec["laos_stage"] = stage_of(cats)
        rec["fit_notes"] = notes
        out.append(rec)

    with io.open(DST, "w", encoding="utf-8") as f:
        for rec in out:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------------- 统计 ----------------
    fc = collections.Counter(rec["laos_fit"] for rec in out)
    cc = collections.Counter()
    for rec in out:
        for c in rec["category"]:
            cc[c] += 1

    by_cat = collections.defaultdict(list)
    for rec in out:
        for c in rec["category"]:
            by_cat[c].append(rec)

    core = sorted([r for r in out if r["laos_fit"] == "core"], key=lambda x: -x["stars"])
    ref = sorted([r for r in out if r["laos_fit"] == "ref"], key=lambda x: -x["stars"])
    unr = sorted([r for r in out if r["laos_fit"] == "unrelated"], key=lambda x: -x["stars"])

    # ---------------- 写文档 ----------------
    L = []
    L.append("# Task 3 分类体系与 laos 适配映射\n")
    L.append("**源数据**: `repos_raw.jsonl`（%d 条，Task 2 去噪+补抓后干净语料）" % len(out))
    L.append("**生成日期**: 2026-09-14  **分类器**: `scripts/classify_oss.py`（规则可复现）\n")

    L.append("## 1. 分类体系（14 类，可多标签）\n")
    L.append("判据：对 `full_name` + `description` + `topics` 做不区分大小写正则匹配，命中即打标；一条仓库可同时命中多类。\n")
    L.append("| 类别 | 命中正则（简述） | laos 漏斗落点倾向 |")
    L.append("|---|---|---|")
    L.append("| asr | asr / speech-to-text / transcri / whisper / recogni / stt / wav2vec / vosk | ③即时蒸馏 |")
    L.append("| tts | text-to-speech / tts / vocoder / speech synthesis / voice cloning | 不在漏斗（laos 只听不说）|")
    L.append("| audio-llm | audio llm / speech llm / omni / multimodal audio / audio gpt / speech translation | ③即时蒸馏 |")
    L.append("| enhance | denois / enhance / dereverb / noise suppress / separat / beamform | ③即时蒸馏(前置) |")
    L.append("| aed | audio tagging / sound event / acoustic scene / event detection / yamnet | ③即时蒸馏 |")
    L.append("| codec | codec / encodec / opus / soundstream / neural codec | ②可选(原音频即焚) |")
    L.append("| kws-vad | keyword spotting / wake-word / voice activity / vad / always-on | ①常驻检测 |")
    L.append("| speaker | speaker verification/diarization / voiceprint / ecapa | 隐私红线(C5)，不落地 |")
    L.append("| agent | agent / assistant / conversational / voicebot / copilot | 编排(ref) |")
    L.append("| serving | serving / inference server / onnxruntime / tensorrt / vllm | 基础设施(ref) |")
    L.append("| dsp-lib | ffmpeg / librosa / pyaudio / sox / webrtc / torchaudio | ①②采集/能量门 |")
    L.append("| music | music generation / midi / song / singing / beat | 不在漏斗 |")
    L.append("| dataset | dataset / corpus / benchmark / librispeech | 评测(ref) |")
    L.append("| ml-framework | transformers / diffusers / pytorch / model-hub / llama.cpp / tensorflow | 模型底座(ref，非组件) |")

    L.append("\n## 2. laos_fit 判定规则（落到硬约束）\n")
    L.append("硬约束：C1 端侧 CPU 可跑（proot glibc aarch64，无 NPU）｜C2 低延迟/流式｜"
             "C3 许可可商用自托管｜C4 不依赖云 API｜C5 不存声纹。\n")
    L.append("```")
    L.append("understanding = {kws-vad, asr, enhance, aed, dsp-lib} (+ audio-llm 仅当无 tts/music)")
    L.append("core  = 命中 understanding")
    L.append("        且 非 CLOUD_RE(云API wrapper) 且 非 SERVER_RE(媒体服务器) 且 非 APPLE(苹果独占)")
    L.append("        且 非 EDU_RE(教学/列表) 且 (非 HEAVY_RE 或 有 on-device 信号)")
    L.append("        且 有 ON_DEVICE_RE 信号(C1+C2) 且 stars >= %d(成熟度)" % CORE_STAR_MIN)
    L.append("ref   = 功能对口但违反某约束(云API/GPU/媒体服务器/苹果独占)｜或 out-of-scope/privacy")
    L.append("        (codec/speaker/tts/music/agent/serving/dataset/ml-framework)｜或 stars 未达门槛")
    L.append("unrelated = 未命中任何功能类别（音频相关但无漏斗组件角色：列表/编辑器/播放器…）")
    L.append("```")
    L.append("正向信号 ON_DEVICE_RE 含：whisper.cpp / sherpa / silero / onnxruntime / onnx / "
             "funasr / sensevoice / piper / kokoro / webrtc / rnnoise / porcupine / vosk / "
             "edge / on-device / realtime / streaming / ggml / tflite / cpu …")
    L.append("负向信号 CLOUD_RE 含：api key / cloud speech / saas / hosted / twilio / elevenlabs / "
             "azure / google cloud / amazon transcribe / openai api / groq / replicate / serverless …")
    L.append("负向信号 HEAVY_RE 含：cuda / gpu required / distributed training / fine-tune llm …")
    L.append("> 许可：因语料 2801/3724 条缺失 license（见 oss_fetch_summary.md §6），"
             "C3 仅做「非云 API wrapper」的弱判定，不替代法律意见；真正落地前须逐条核实 license。")

    L.append("\n## 3. 总体适配度分布\n")
    L.append("| laos_fit | 条数 | 占比 |")
    L.append("|---|---:|---:|")
    for k in ("core", "ref", "unrelated"):
        L.append("| %s | %d | %.1f%% |" % (k, fc.get(k, 0), 100.0 * fc.get(k, 0) / len(out)))
    L.append("| **合计** | %d | 100%% |" % len(out))

    L.append("\n## 4. 各类别统计（条数 + star 中位数 + Top5）\n")
    L.append("| 类别 | 条数 | star 中位数 | star Top5（仓库 / stars） |")
    L.append("|---|---:|---:|---|")
    for c in sorted(by_cat, key=lambda k: -len(by_cat[k])):
        items = sorted(by_cat[c], key=lambda x: -x["stars"])
        top5 = "、".join("%s/%d" % (r["full_name"], r["stars"]) for r in items[:5])
        L.append("| %s | %d | %d | %s |" % (c, len(items), median([r["stars"] for r in items]), top5))

    L.append("\n## 5. laos 适配清单（core 组件，真正可落地）\n")
    L.append("共 **%d** 条 `laos_fit=core`。下列按 stars 降序列出，并标注落点漏斗段落。\n" % len(core))
    L.append("| star | 仓库 | 类别 | 漏斗落点 | 一句话用途 |")
    L.append("|---:|---|---|---|---|")
    for r in core:
        L.append("| %d | %s | %s | %s | %s |" % (
            r["stars"], r["full_name"], ",".join(c for c in r["category"] if c in FUNNEL_CORE_CATS),
            r["laos_stage"], (r["description"] or "").replace("|", "/")[:60]))

    L.append("\n## 6. 适配度最高但被判 ref 的代表（说明为何不标 core）\n")
    L.append("| star | 仓库 | 类别 | 降级原因(fit_notes) |")
    L.append("|---:|---|---|---|")
    for r in ref[:25]:
        L.append("| %d | %s | %s | %s |" % (
            r["stars"], r["full_name"], ",".join(r["category"][:4]),
            "；".join(r["fit_notes"]).replace("|", "/")[:70]))

    if unr:
        L.append("\n## 7. unrelated 样本（与 laos 漏斗无关，来自补抓泄漏复核）\n")
        L.append("共 %d 条。Top10：" % len(unr))
        L.append("| star | 仓库 | 类别 | 命中原因 |")
        L.append("|---:|---|---|---|")
        for r in unr[:10]:
            L.append("| %d | %s | %s | %s |" % (
                r["stars"], r["full_name"], ",".join(r["category"][:4]) or "-",
                "；".join(r["fit_notes"]).replace("|", "/")[:50]))

    L.append("\n## 8. 局限与需人工复核\n")
    L.append("- 分类完全依赖作者自填的 topics + description 文本，_topic 标签噪声_会导致漏标/错标"
             "（例如只打 `llm` 未打 `audio` 的音频仓库可能被错分）。")
    L.append("- laos_fit 的 C1（端侧 CPU）靠关键词信号近似，未实测 proot aarch64 上能否真正跑通；"
             "silero/sherpa-onnx/whisper.cpp 等经 SER 04 §8 论证可行，其余需实测。")
    L.append("- C3 许可因 75%% 语料缺 license 字段无法逐条判定，core 仅排除「云 API wrapper」类，"
             "不保证全部可商用；落地前须逐条核 SPDX。")
    L.append("- `music` / `tts` 一律判 ref 属产品范围决策（laos 只听不说），非技术不可行；"
             "若未来 laos 加语音播报，tts 类需重估。")
    L.append("- 最不可靠部分：**speaker 类「隐私红线」判定是策略性一律降级**，未区分纯 diarization"
             "（分割，可借鉴）与声纹注册（verification，碰红线）；若有项目仅做流式 diarization 分割，"
             "应人工复核后上调为 core 候选。")

    io.open(DOC, "w", encoding="utf-8").write("\n".join(L) + "\n")

    # ---------------- 控制台 ----------------
    print("总条数", len(out))
    print("适配度:", dict(fc))
    print("分类分布:", dict(cc.most_common()))
    print("\ncore 组件 %d 个，top30:" % len(core))
    for r in core[:30]:
        print("  %8d  %-38s %-22s %s" % (
            r["stars"], r["full_name"], r["laos_stage"][:22], ",".join(r["category"])[:30]))
    print("\nref top10（核对降级原因）:")
    for r in ref[:10]:
        print("  %8d  %-38s %s" % (r["stars"], r["full_name"], ";".join(r["fit_notes"])[:60]))
    print("\n-> %s" % DST)
    print("-> %s" % DOC)


if __name__ == "__main__":
    main()
