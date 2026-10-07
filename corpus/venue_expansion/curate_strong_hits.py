#!/usr/bin/env python
"""corpus/venue_expansion/curate_strong_hits.py — 强命中精炼器（Task 1，
2026-10-07 corpus reuse-upgrade）。

把 filter_laos_relevant.py 的产物 laos_relevant.jsonl（2,103 行）净化成强命中
工作集 laos_relevant_strong.jsonl（Task 3/4 的唯一输入）。v0.18.0 报告 §3 注记
的弱命中两类来源在此清除：audio-speech 的裸子串 asr/tts/vad 误标（LLM 安全论文
"attack success rate (asr)" 68 篇）与 agent-os 的宽分支泛 LLM-agent 论文。

强命中规则（task-1 brief Step 3）：
- audio-speech：须命中多词短语（wake word / keyword spotting / speech
  recognition / voice activity / echo cancell / far-field / text-to-speech /
  speech translation / spoken dialogue / voice agent / audio-visual speech /
  diarization），或裸词 asr/tts/vad（词边界）与音频语境词
  （speech/audio/voice/acoustic）前后 60 字符内同现。原词表的 always-on
  不在强短语表——唯一证据是 always-on 的行判弱。
- agent-os：只认窄治理分支——agent 与 operating system/sandbox/syscall/
  kernel/governan/resource/quota/isolation 在 40 字符内同现（双向：治理词
  在前也算，brief 正例 "Kernel-level sandboxing of LLM agents"）。仅宽分支
  （(llm|language model)…agent）判弱。
- spatial-privacy：词表本身即短语级，全保。

用法：
  python curate_strong_hits.py            # laos_relevant.jsonl -> laos_relevant_strong.jsonl
  python curate_strong_hits.py --stats    # 另打 topic×强/弱 计数表

产出行为：只读原文件；写出 = 原行全部字段 + "strong": true +
"strong_terms": [命中的强词组标签]（短语标签在前、bare 词在后，去重保序）；
行序与输入一致；弱命中行不写出但计入统计。写行沿用 write_jsonl 纪律
（U+2028/U+2029/U+0085 转义，JSON 值不变）。
零第三方依赖（argparse/json/re/sys/collections/pathlib，纯 stdlib）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ---- audio-speech 强短语表（brief 逐词；label = strong_terms 里记录的标签） ----
AUDIO_PHRASES: tuple[tuple[str, str], ...] = (
    ("wake word", r"wake[- ]?word"),
    ("keyword spotting", r"keyword spotting"),
    ("speech recognition", r"speech recognition"),
    ("voice activity", r"voice activity"),
    ("echo cancellation", r"echo cancell\w*"),
    ("far-field", r"far[- ]?field"),
    ("text-to-speech", r"text[- ]?to[- ]?speech"),
    ("speech translation", r"speech translation"),
    ("spoken dialogue", r"spoken dialogue"),
    ("voice agent", r"voice agent"),
    ("audio-visual speech", r"audio[- ]?visual[- ]?speech"),
    ("diarization", r"diariz\w*"),
)
# 裸词（须词边界）+ 音频语境词 + 同现窗口（brief：前后 60 字符）
AUDIO_BARE_WORDS: tuple[str, ...] = ("asr", "tts", "vad")
_BARE_RX = {w: re.compile(rf"\b{w}\b") for w in AUDIO_BARE_WORDS}
AUDIO_CONTEXT = re.compile(r"\b(?:speech|audio|voice|acoustic)")
CONTEXT_WINDOW = 60

# ---- agent-os 窄治理分支：治理词与 filter_laos_relevant 窄分支逐字一致（含 quota） ----
AGENT_GOV_TERMS: tuple[str, ...] = ("operating system", "sandbox", "syscall",
                                    "kernel", "governan", "resource",
                                    "quota", "isolation")
AGENT_SPAN = 40  # 与 filter_laos_relevant 窄分支同跨度
# 双向同现：agent…gov 或 gov…agent（brief 正例 Kernel-level sandboxing of
# LLM agents 即治理词在前、agent 在后）
_AGENT_NARROW_RX = tuple(
    (gov, re.compile(rf"agent.{{0,{AGENT_SPAN}}}{gov}|{gov}.{{0,{AGENT_SPAN}}}agent"))
    for gov in AGENT_GOV_TERMS
)

# ---- spatial-privacy：短语级词表，全保（覆盖 = filter_laos_relevant 原词表） ----
SPATIAL_PHRASES: tuple[tuple[str, str], ...] = (
    ("binaural", r"binaural"),
    ("spatial audio", r"spatial audio"),
    ("beamforming", r"beamform\w*"),
    ("acoustic camera", r"acoustic camera"),
    ("speech privacy", r"speech privacy"),
    ("audio watermark", r"audio watermark"),
)


def _text(entry: dict) -> str:
    """标题+摘要（若有）拼串 casefold，与 filter_laos_relevant.is_relevant 同口径。"""
    return " ".join(part for part in (entry.get("title") or "",
                                      entry.get("abstract") or "") if part).casefold()


def _audio_terms(text: str) -> list[str]:
    """audio-speech 强词组：短语标签命中即强；bare 词须 ±窗口 内有音频语境词。"""
    terms = [label for label, pat in AUDIO_PHRASES if re.search(pat, text)]
    for word in AUDIO_BARE_WORDS:
        if any(AUDIO_CONTEXT.search(text[max(0, m.start() - CONTEXT_WINDOW):
                                         m.end() + CONTEXT_WINDOW])
               for m in _BARE_RX[word].finditer(text)):
            terms.append(word)
    return terms


def _agent_terms(text: str) -> list[str]:
    """agent-os 强词组：窄分支双向同现，标签记 "agent+<治理词>"。"""
    return [f"agent+{gov}" for gov, rx in _AGENT_NARROW_RX if rx.search(text)]


def _spatial_terms(text: str) -> list[str]:
    return [label for label, pat in SPATIAL_PHRASES if re.search(pat, text)]


_RULES = {"audio-speech": _audio_terms,
          "agent-os": _agent_terms,
          "spatial-privacy": _spatial_terms}


def strong_terms(entry: dict) -> list[str]:
    """按 laos_topic 施加强规则，返回命中的强词组标签（去重保序；空 = 弱）。

    未知/缺失 laos_topic、空文本一律无词组（判弱）。
    """
    rule = _RULES.get(entry.get("laos_topic") or "")
    if rule is None:
        return []
    return rule(_text(entry))


def is_strong(entry: dict) -> bool:
    """强命中判定：strong_terms 非空。"""
    return len(strong_terms(entry)) > 0


def _dumps_line(row: dict) -> str:
    s = json.dumps(row, ensure_ascii=False)
    return (s.replace("\u2028", "\\u2028")
             .replace("\u2029", "\\u2029")
             .replace("\x85", "\\u0085"))


def run_curate(in_path, out_path) -> dict:
    """逐行精炼写 out_path（只读原文件），返回统计 dict。

    强命中行写出 = 原行全部字段 + strong:true + strong_terms，行序与输入一致；
    弱命中行不写出。per_topic 为 topic -> {"strong": n, "weak": m}（三主线
    固定出现，含 0）。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total_in = strong = weak = written = 0
    per_topic: dict[str, Counter] = {t: Counter() for t in _RULES}
    with Path(in_path).open("r", encoding="utf-8") as rf, \
            out_path.open("w", encoding="utf-8", newline="\n") as fh:
        for line in rf:
            line = line.strip()
            if not line:
                continue
            total_in += 1
            entry = json.loads(line)
            topic = entry.get("laos_topic")
            terms = strong_terms(entry)
            if terms:
                strong += 1
                written += 1
                if topic in per_topic:
                    per_topic[topic]["strong"] += 1
                fh.write(_dumps_line({**entry, "strong": True,
                                      "strong_terms": terms}) + "\n")
            else:
                weak += 1
                if topic in per_topic:
                    per_topic[topic]["weak"] += 1
    return {"total_in": total_in, "strong": strong, "weak": weak,
            "written": written,
            "per_topic": {t: {"strong": c["strong"], "weak": c["weak"]}
                          for t, c in per_topic.items()}}


def print_stats(stats: dict) -> None:
    """topic×强/弱 计数表 + 总计数（CLI --stats）。"""
    print("topic × 强/弱 计数（强命中行才写出）")
    for topic, c in stats["per_topic"].items():
        print(f"  {topic:16s} 强 {c.get('strong', 0):5d}   弱 {c.get('weak', 0):5d}")
    print(f"  {'TOTAL':16s} 强 {stats['strong']:5d}   弱 {stats['weak']:5d}")
    print(f"输入行 {stats['total_in']} | 强命中 {stats['strong']} | "
          f"弱命中 {stats['weak']} | 写出 {stats['written']} 行")


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(
        description="强命中精炼器：laos_relevant.jsonl -> "
                    "laos_relevant_strong.jsonl（原字段 + strong:true + "
                    "strong_terms，只读原文件）")
    ap.add_argument("--in", dest="in_path",
                    default=str(here / "laos_relevant.jsonl"),
                    help="输入 jsonl（默认脚本目录 laos_relevant.jsonl）")
    ap.add_argument("--out", dest="out_path",
                    default=str(here / "laos_relevant_strong.jsonl"),
                    help="输出 jsonl（默认脚本目录 laos_relevant_strong.jsonl）")
    ap.add_argument("--stats", action="store_true",
                    help="另打 topic×强/弱 计数表")
    args = ap.parse_args(argv)
    in_path, out_path = Path(args.in_path), Path(args.out_path)
    if not in_path.exists():
        print(f"input not found: {in_path}", file=sys.stderr)
        return 1
    if out_path.resolve() == in_path.resolve():
        print("--out must differ from --in (原文件只读，禁止覆盖)",
              file=sys.stderr)
        return 1
    stats = run_curate(in_path, out_path)
    print(f"{in_path.name} -> {out_path}（写出 {stats['written']} 行，"
          f"强命中 {stats['strong']}，弱命中 {stats['weak']}）")
    if args.stats:
        print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
