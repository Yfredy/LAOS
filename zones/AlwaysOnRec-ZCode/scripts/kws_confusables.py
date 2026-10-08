#!/usr/bin/env python3
"""kws_confusables —— 私有唤醒词的"易混词"负样本生成器（零依赖，确定性）。

LLM-Synth4KWS（Interspeech 2025, arXiv:2505.22959）思路的零依赖落地：
用户给 laos 起唤醒词后，先离线生成一串"听起来像"的词（声母/韵母替换），
交给 TTS 合成负样本做对比学习/模板间拒绝阈值标定——压误唤醒。

    python scripts/kws_confusables.py 劳斯 lai si [--limit 20]

输出 JSON：{"phrase", "syllables", "confusables"}。规则确定性，无 LLM 也能跑；
接 LLM 时把本输出当种子 Prompt 即可（结构兼容）。
"""

from __future__ import annotations

import argparse
import json
import sys

# 常见混淆对（普通话）：声母近似 + 韵母前后鼻音/展撮混淆
_INITIAL_CONFUSABLE = {
    "n": ["l"], "l": ["n", "r"],
    "zh": ["z"], "z": ["zh", "c"], "ch": ["c"], "c": ["ch", "s"],
    "sh": ["s"], "s": ["sh"], "h": ["f"], "f": ["h"],
    "b": ["p"], "p": ["b"], "d": ["t"], "t": ["d"],
    "g": ["k"], "k": ["g"], "j": ["q"], "q": ["j", "x"], "x": ["q"],
}
_FINAL_CONFUSABLE = {
    "an": ["ang"], "ang": ["an"], "en": ["eng"], "eng": ["en"],
    "in": ["ing"], "ing": ["in"], "ai": ["ei"], "ei": ["ai"],
    "uo": ["o"], "o": ["uo"], "i": ["e"], "e": ["i"], "u": ["ou"],
}


def _split(syllable: str) -> tuple[str, str]:
    """音节 → (声母, 韵母)。贪心匹配双字母声母，失败则零声母。"""
    for ini in ("zh", "ch", "sh"):
        if syllable.startswith(ini) and len(syllable) > 2:
            return ini, syllable[len(ini):]
    if syllable and syllable[0] in "bpmfdtnlgkhjqxrzcswyl":
        return syllable[0], syllable[1:]
    return "", syllable


def generate(phrase: str, syllables: list[str], *, limit: int = 20) -> list[str]:
    """确定性生成易混词（逐音节替换声母/韵母，各取一变体，去重、排除原词）。"""
    original = " ".join(syllables)
    out: list[str] = []
    for idx, syl in enumerate(syllables):
        ini, fin = _split(syl)
        variants: list[str] = []
        variants += [ini2 + fin for ini2 in _INITIAL_CONFUSABLE.get(ini, [])]
        variants += [ini + fin2 for fin2 in _FINAL_CONFUSABLE.get(fin, [])]
        for v in variants:
            cand = list(syllables)
            cand[idx] = v
            words = " ".join(cand)
            if words != original and words not in out:
                out.append(words)
                if len(out) >= limit:
                    return out
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="私有唤醒词易混词生成器（零依赖）")
    ap.add_argument("phrase", help="唤醒词汉字，如：劳斯")
    ap.add_argument("syllables", nargs="+", help="拼音音节序列，如：lai si")
    ap.add_argument("--limit", type=int, default=20, help="最多生成多少个（默认 20）")
    args = ap.parse_args()

    payload = {
        "phrase": args.phrase,
        "syllables": args.syllables,
        "confusables": generate(args.phrase, args.syllables, limit=args.limit),
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
