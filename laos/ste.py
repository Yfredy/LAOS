"""ste —— 约束语言 lint：AI 输出可理解性的 check-only 检查层。

方法论源自 Karpathy 2026-10-02 帖（x.com/karpathy/status/2105819303471976479）：
AI 写得越来越快，人的理解速度成为瓶颈——让模型用 ASD-STE100 约束语言写
（航空航天维修文档规范：~900 批准词、one word one meaning、一句一事），
输出"a lot more readable"。

本模块是 ASD-STE100 **原则**的可测子集落地，不是标准本身：

- 官方词表再分发受限（ASD 许可），这里不收词表、只取原则——与社区
  asd-ste100-skill（github.com/danyuchn/asd-ste100-skill, MIT）同一取舍；
- **只检查不改写**：简化是有损变换（"格式越好懂，错误藏得越深"——该句
  系小红书笔记层增补，未见于 Karpathy 原帖，但方向成立并被采纳为治理
  姿势）。问题报告永远带原文摘录与位置，原始文本权威，与 jitmem
  "绝不截断原文"同一原则族。

五条规则（均可独立开关，rules=("R1","R2",...)）：

    R1 句长上限   分句（。！？!? 与换行）后每句 > max_sentence_chars
                 （默认 60，中文程序性文本的 STE 同精神约束）报
    R2 术语轮换   Karpathy 点名的痛点（agent/worker/executor 混用）：
                 同义术语组内 ≥2 形并在同一文本出现报；组表可传入，
                 内置 laos 域默认组
    R3 一句多事   句内子句分隔（，、,）计数 > max_clauses（默认 2）报
    R4 hedge 堆叠 同句 ≥2 个模糊限定词（可能/大概/似乎/或许/也许/
                 基本上/某种程度/理论上/估计）报——信息密度塌方信号
    R5 分号并联   ；/; 逐个报——STE"一句一事"写作规则：程序性文本用
                 句号断开，不用分号并联长句

问题按 (位置, 规则号) 确定性排序；R2 是文档级检查（pos=-1）排在最前。

CLI：python -m laos.ste [file|-] [--max-chars N] [--rules R1,R2]
     有问题 exit 1（fail-loud），干净 exit 0。
"""

from __future__ import annotations

import argparse
import re
import sys

DEFAULT_MAX_SENTENCE_CHARS = 60
DEFAULT_MAX_CLAUSES = 2  # 子句分隔符上限（，、, 计数 ≤2 即最多三个子句）

# 内置同义术语组（laos 域）：真正同义且混用会伤读者的才进表
DEFAULT_TERM_GROUPS: list[tuple[str, ...]] = [
    ("agent", "worker", "executor"),
]

HEDGES = ("可能", "大概", "似乎", "或许", "也许",
          "基本上", "某种程度", "理论上", "估计")

_SENTENCE_SPLIT = re.compile(r"[。！？!?\n]+")
_CLAUSE_SEPS = ("，", "、", ",")
_ALL_RULES = ("R1", "R2", "R3", "R4", "R5")


def _excerpt(sentence: str, width: int = 24) -> str:
    return sentence[:width] + ("…" if len(sentence) > width else "")


def lint(text: str, max_sentence_chars: int = DEFAULT_MAX_SENTENCE_CHARS,
         max_clauses: int = DEFAULT_MAX_CLAUSES,
         term_groups: list[tuple[str, ...]] | None = None,
         rules: tuple[str, ...] = _ALL_RULES) -> list[dict]:
    """检查文本，返回问题清单（空 = 通过）。只检查，不改写。

    每个问题：{rule, detail, excerpt, hint, pos}——excerpt 是原文摘录，
    pos 是问题位置（R2 文档级为 -1），按 (pos, 规则号) 排序。
    """
    enabled = tuple(r.upper() for r in rules)
    problems: list[dict] = []

    # R2 术语轮换（文档级）
    if "R2" in enabled:
        groups = DEFAULT_TERM_GROUPS if term_groups is None else term_groups
        lowered = text.lower()
        for group in groups:
            forms = []
            for form in group:
                if form.lower() in lowered:
                    forms.append(form)
            if len(forms) >= 2:
                problems.append({
                    "rule": "R2 术语轮换",
                    "detail": f"同义术语多形并存: {', '.join(forms)}",
                    "excerpt": _excerpt(text),
                    "hint": "one word, one meaning——同一概念全文只用一个名字",
                    "pos": -1,
                })

    # 句级检查：R1 / R3 / R4 / R5
    pos = 0
    for chunk in _SENTENCE_SPLIT.split(text):
        sentence = chunk.strip()
        start = text.find(chunk, pos)
        pos = start + len(chunk) + 1
        if not sentence:
            continue
        if "R1" in enabled and len(sentence) > max_sentence_chars:
            problems.append({
                "rule": "R1 句长",
                "detail": f"{len(sentence)} 字 > {max_sentence_chars}",
                "excerpt": _excerpt(sentence),
                "hint": "拆成多个短句，每句只说一件事",
                "pos": start,
            })
        if "R3" in enabled:
            seps = sum(sentence.count(s) for s in _CLAUSE_SEPS)
            if seps > max_clauses:
                problems.append({
                    "rule": "R3 一句多事",
                    "detail": f"{seps} 个子句分隔 > {max_clauses}",
                    "excerpt": _excerpt(sentence),
                    "hint": "一句一事：按子句拆成独立短句",
                    "pos": start,
                })
        if "R4" in enabled:
            hedge_hits = [(h, sentence.count(h)) for h in HEDGES if h in sentence]
            n = sum(c for _h, c in hedge_hits)
            if n >= 2:
                words = "/".join(h for h, _c in hedge_hits)
                problems.append({
                    "rule": "R4 hedge堆叠",
                    "detail": f"同句 {n} 处模糊限定词（{words}）",
                    "excerpt": _excerpt(sentence),
                    "hint": "删掉限定词或给出确定结论——信息密度优先",
                    "pos": start,
                })
        if "R5" in enabled:
            for i, ch in enumerate(sentence):
                if ch in ("；", ";"):
                    problems.append({
                        "rule": "R5 分号并联",
                        "detail": "分号并联（STE：一句一事，用句号断开）",
                        "excerpt": _excerpt(sentence),
                        "hint": "程序性文本不用分号串联并列句",
                        "pos": start + i,
                    })

    def _key(p: dict):
        code = p["rule"].split()[0]
        return (p["pos"], code)

    problems.sort(key=_key)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="laos.ste",
        description="约束语言 lint（ASD-STE100 原则的 check-only 子集；"
                    "只检查不改写，原文权威）")
    ap.add_argument("file", nargs="?", default="-",
                    help="待检文本文件，缺省或 - 读 stdin")
    ap.add_argument("--max-chars", type=int, default=DEFAULT_MAX_SENTENCE_CHARS,
                    help=f"句长上限（默认 {DEFAULT_MAX_SENTENCE_CHARS}）")
    ap.add_argument("--rules", type=str, default=",".join(_ALL_RULES),
                    help="启用的规则子集，逗号分隔（默认全部）")
    args = ap.parse_args(argv)

    if args.file == "-":
        text = sys.stdin.read()
    else:
        from pathlib import Path
        text = Path(args.file).read_text(encoding="utf-8")
    rules = tuple(r.strip().upper() for r in args.rules.split(",") if r.strip())
    problems = lint(text, max_sentence_chars=args.max_chars, rules=rules)

    if not problems:
        print("STE lint 通过（R1 句长 / R2 术语 / R3 一句一事 / R4 hedge / R5 分号）")
        return 0
    for p in problems:
        print(f"[{p['rule']}] {p['detail']} | {p['excerpt']}")
    print(f"共 {len(problems)} 项（check-only：只检查不改写，原文权威）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
