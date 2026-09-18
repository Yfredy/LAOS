#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""审计 + 去噪 + 归一化已有 OSS 语料（corpus/oss_corpus.json）。

背景（2026-09-14 实测，见计划 Global Constraints 第 10 条）：
  * 8 个 topic: 切片 100% 相关，免检复用。
  * audio-llm / voice-agent 两个裸关键词切片相关率仅 20%/15%，须逐条重筛。
  * 噪声根因：裸关键词全文检索被 GitHub 拆词匹配，混入 public-apis / awesome-python 等通用高星仓库。
  * 已有语料缺 license/created_at/forks 字段 -> 归一化时置空，不编造。

相关性判据（可解释，写进产出物）：
  一条仓库「音频相关」当且仅当在其 full_name / description / topics 中命中下列
  任意音频域词（不区分大小写）：
    audio, sound, speech, voice, tts, asr, acoustic, whisper, sonic, hearing,
    music, voicebot, wake-word, vad, diariz*, vocoder, spectrogram, vocal,
    speaker, noise, echo, mel, wav, mp3, pcm, microphone, singing, karaoke
  若命中 -> 保留；否则 -> 剔除噪声。
  8 个 topic: 切片（audio/tts/asr/speech/voice-assistant/diarization/
  enhancement/audio-processing）的仓库 topic 即含 audio/speech/voice 等词，
  按此判据必为 100% 相关，故直接复用。
"""
import json, io, os, re, collections, datetime

CORPUS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\oss_corpus.json"
OUT_DIR = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"
RAW = os.path.join(OUT_DIR, "repos_raw.jsonl")
NOISE = os.path.join(OUT_DIR, "noise_dropped.jsonl")
AUDIT = os.path.join(OUT_DIR, "oss_audit.md")

# 第一组：通用音频域词（独立成词，避免 audience/audit/invoice 之类误命中）。
# 第二组：明确的音频库 / 模型 / 厂商品牌名（无歧义，用于找回被嵌入命名或
#         品牌名遮蔽的真音频项目，如 FireRedAudio / elevenlabs-mcp / sherpa-*）。
AUDIO_RE = re.compile(
    r"(?i)(\baudio\b|\bsound\b|\bspeech\b|\bvoice\b|\btts\b|\basr\b|"
    r"\bacoustic\b|\bwhisper\b|\bsonic\b|\bhearing\b|\bmusic\b|"
    r"\bvoicebot\b|\bwake.?word\b|\bvad\b|\bdiariz|\bvocoder\b|"
    r"\bspectrogram\b|\bvocal\b|\bspeaker\b|\bnoise\b|\becho\b|"
    r"\bmel\b|\bwav\b|\bmp3\b|\bpcm\b|\bmicrophone\b|"
    r"\bsinging\b|\bkaraoke\b|"
    r"\b(whisperx|faster-?whisper|openai-?whisper|librosa|torchaudio|"
    r"webrtc|porcupine|sherpa|funasr|silero|coqui|piper|demucs|spleeter|"
    r"audiocraft|musicgen|speechbrain|wav2vec|hubert|espeak|pydub|"
    r"sounddevice|so-?vits|sovits|bark|kokoro|cosyvoice|sensevoice|"
    r"fish-?audio|elevenlabs|resemble|playht|cartesia|chattts|f5-?tts|"
    r"index-?tts|maskgct|orpheus|suno|udio|qwen2?-?audio|glm-?4-?voice|"
    r"rvc|rvcspeech|firered)\b)")
CLEAN_SLICES = {"audio", "tts", "asr", "speech", "voice-assistant",
                "diarization", "enhancement", "audio-processing"}


def audio_related(r):
    text = " ".join([r.get("full_name", ""), r.get("description") or "",
                     " ".join(r.get("topics") or [])])
    return bool(AUDIO_RE.search(text))


def norm(r, crawled_at, reason=""):
    n = {
        "full_name": r.get("full_name", ""),
        "stars": r.get("stars", 0),
        "description": r.get("description") or "",
        "language": r.get("language") or "",
        "license": r.get("license") or "",
        "html_url": r.get("url") or r.get("html_url", ""),
        "created_at": r.get("created_at", ""),
        "pushed_at": (r.get("pushed_at") or "")[:10],
        "topics": r.get("topics") or [],
        "archived": bool(r.get("archived")),
        "forks": r.get("forks", 0),
        "open_issues": r.get("open_issues", 0),
        "query": ",".join(r.get("slices") or []) or "corpus:oss_corpus.json",
        "crawled_at": crawled_at,
    }
    if reason:
        n["drop_reason"] = reason
    return n


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    repos = json.load(io.open(CORPUS, encoding="utf-8"))["repos"]

    slice_total = collections.Counter()
    slice_related = collections.Counter()
    kept, dropped = [], []
    from_dirty_kept = 0
    for r in repos:
        sl = r.get("slices") or []
        rel = audio_related(r)
        for s in sl:
            slice_total[s] += 1
            if rel:
                slice_related[s] += 1
        in_clean = bool(set(sl) & CLEAN_SLICES)
        if in_clean or rel:
            kept.append(r)
            if (not in_clean) and (set(sl) & {"audio-llm", "voice-agent"}):
                from_dirty_kept += 1
        else:
            dropped.append(r)

    # 去重（按 full_name）落盘
    seen = {}
    n_raw = 0
    with io.open(RAW, "w", encoding="utf-8") as f, \
         io.open(NOISE, "w", encoding="utf-8") as g:
        for r in kept:
            n = norm(r, today)
            if n["full_name"] in seen:
                continue
            seen[n["full_name"]] = 1
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
            n_raw += 1
        for r in dropped:
            # 敲定剔除原因：两个脏切片中、且未命中音频域词
            reason = ("未命中音频域判据（name/description/topics 均不含 "
                      "audio/speech/voice/tts/asr/...）；源于裸关键词拆词检索噪声")
            g.write(json.dumps(norm(r, today, reason), ensure_ascii=False) + "\n")

    # ---- 控制台 + markdown 报告 ----
    lines = []
    lines.append("# OSS 语料审计与去噪报告\n")
    lines.append("**语料来源**: `docs/research/corpus/oss_corpus.json`")
    lines.append("**审计日期**: %s" % today)
    lines.append("**总仓库数（去重）**: %d\n" % len(repos))

    lines.append("## 1. 相关性判据（可解释规则）\n")
    lines.append("一条仓库「音频相关」当且仅当其 `full_name` / `description` / "
                 "`topics` 命中以下任意音频域词（不区分大小写）：\n")
    lines.append("> audio, sound, speech, voice, tts, asr, acoustic, "
                 "whisper, sonic, hearing, music, voicebot, wake-word, vad, "
                 "diariz*, vocoder, spectrogram, vocal, speaker, noise, "
                 "echo, mel, wav, mp3, pcm, microphone, singing, karaoke\n")
    lines.append("8 个 `topic:` 切片因 topic 标签本身含 audio/speech/voice 等词，"
                 "按此判据必为 100%% 相关，直接复用；"
                 "`audio-llm` / `voice-agent` 两切片原为裸关键词全文检索，"
                 "被 GitHub 拆词匹配混入通用高星仓库，须逐条重筛。\n")

    lines.append("## 2. 各切片条数与相关率\n")
    lines.append("| 切片 | 命中条数 | 相关条数 | 相关率 |")
    lines.append("|---|---:|---:|---:|")
    for s in sorted(slice_total, key=lambda x: -slice_total[x]):
        tot = slice_total[s]
        rel = slice_related[s]
        tag = "（干净复用）" if s in CLEAN_SLICES else "（需重筛）"
        lines.append("| %s%s | %d | %d | %.0f%% |" %
                     (s, tag, tot, rel, 100.0 * rel / max(tot, 1)))

    lines.append("\n## 3. 去噪结果\n")
    lines.append("- 保留（写 `repos_raw.jsonl`，已按 full_name 去重）：**%d 条**" % n_raw)
    lines.append("  - 其中来自两脏切片、经重筛确认为真相关的：**%d 条**" % from_dirty_kept)
    lines.append("- 剔除噪声（写 `noise_dropped.jsonl`）：**%d 条**" % len(dropped))
    lines.append("  - 全部来自 `audio-llm` / `voice-agent` 两裸关键词切片，"
                 "且未命中音频域判据。\n")

    lines.append("## 4. 被剔除的高星仓库（用户可能质疑，单独列示）\n")
    lines.append("这些仓库 star 很高但**与音频无关**，原样入榜会得出"
                 "「高星音频项目其实和音频无关」的错结论，故剔除：\n")
    lines.append("| star | 仓库 | 切片 | 剔除原因 |")
    lines.append("|---:|---|---|---|")
    for r in sorted(dropped, key=lambda x: -x.get("stars", 0))[:25]:
        sl = ",".join(r.get("slices") or [])
        lines.append("| %d | %s | %s | 未命中音频域判据 |" %
                     (r.get("stars", 0), r.get("full_name"), sl))

    lines.append("\n## 5. 下一步\n")
    lines.append("- 用引号短语 / `topic:` 精准补抓（Task 2 Step 3），找回被噪声稀释的真音频项目。")
    lines.append("- 补抓结果按 `full_name` 去重并入 `repos_raw.jsonl`（Task 2 Step 4）。")

    md = "\n".join(lines)
    io.open(AUDIT, "w", encoding="utf-8").write(md)

    # 控制台摘要
    print("=== 各切片相关率 ===")
    for s in sorted(slice_total, key=lambda x: -slice_total[x]):
        tot = slice_total[s]
        rel = slice_related[s]
        print("  %-18s 总%5d 相关%5d (%.0f%%)" %
              (s, tot, rel, 100.0 * rel / max(tot, 1)))
    print("\n保留 %d 条（去重），其中脏切片真相关 %d 条；剔除噪声 %d 条"
          % (n_raw, from_dirty_kept, len(dropped)))
    print("被剔除高星 top10:")
    for r in sorted(dropped, key=lambda x: -x.get("stars", 0))[:10]:
        print("   %7d  %s" % (r.get("stars", 0), r.get("full_name")))
    print("-> %s (%d 条)\n-> %s (%d 条)\n-> %s"
          % (RAW, n_raw, NOISE, len(dropped), AUDIT))


if __name__ == "__main__":
    main()
