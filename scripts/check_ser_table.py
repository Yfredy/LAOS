#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_ser_table.py —— 声学情感模型调研表的校验器。

调研型计划里没有 pytest 可写，但"每条记录都能被核验"这条必须能被机器检查，
否则"我查过了"和"我觉得它有"没有区别。这个脚本就是那道闸：

    python scripts/check_ser_table.py docs/research/speech-emotion/*.md
    python scripts/check_ser_table.py --selftest

检查项（对应 docs/research/speech-emotion/00-taxonomy-and-metrics.md 的 schema）：
  a. 每行列数 == 12（schema 定义的 12 列，逐字对齐）
  b. 参数量(M) 是数字，或 n/a(非神经)
  c. 来源 含 arxiv.org / huggingface.co / github.com 之一
  d. 许可 非空
  e. 指标 含带基准名的括号，如 "UAR 73.4 (IEMOCAP)"
  f. 单元格不得为 TBD / 待补 / TODO / ?

退出码：0 = 全通过；1 = 有违规。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

COLUMNS = ["模型", "版本/权重", "参数量(M)", "模态", "预训练语料", "输出",
           "基准", "指标", "许可", "权重可得", "edge", "来源"]
NCOL = len(COLUMNS)

PLACEHOLDERS = {"tbd", "待补", "todo", "?"}
NON_NEURAL = "n/a(非神经)"
SOURCE_HOSTS = ("arxiv.org", "huggingface.co", "github.com")


class Violation:
    def __init__(self, path: str, line: int, rule: str, detail: str):
        self.path, self.line, self.rule, self.detail = path, line, rule, detail

    def __str__(self) -> str:
        return f"{self.path}:{self.line}  [{self.rule}] {self.detail}"


def split_row(line: str) -> list[str]:
    """按 markdown 表格切分单元格（不处理转义竖线：调研表里不该出现）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells)


def check_text(text: str, path: str = "<inline>") -> list[Violation]:
    out: list[Violation] = []
    header_idx: dict[int, str] = {}   # 列序号 -> 列名
    in_table = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            in_table = False
            header_idx = {}
            continue

        cells = split_row(line)

        if not in_table:
            # 只认以「模型」开头的数据表，其余表格（如数据集表）不归本校验器管
            if cells and cells[0] == "模型":
                if [c for c in cells] != COLUMNS:
                    out.append(Violation(path, lineno, "schema",
                                         f"表头列与 schema 不一致：{cells}"))
                    continue
                header_idx = {i: c for i, c in enumerate(COLUMNS)}
                in_table = True
            continue

        if is_separator(cells):
            continue

        if not in_table or not header_idx:
            continue

        # a. 列数
        if len(cells) != NCOL:
            out.append(Violation(path, lineno, "cols",
                                 f"列数 {len(cells)} != {NCOL}"))
            continue

        row = dict(zip(COLUMNS, cells))

        # f. 占位符
        for col, val in row.items():
            if val.strip().lower() in PLACEHOLDERS:
                out.append(Violation(path, lineno, "placeholder",
                                     f"{col} 列是占位符 {val!r}"))

        # b. 参数量
        params = row["参数量(M)"]
        if params.strip().lower() != NON_NEURAL and not re.fullmatch(
                r"\d+(\.\d+)?|\d+(\.\d+)?[–-]\d+(\.\d+)?", params):
            out.append(Violation(path, lineno, "params",
                                 f"参数量 {params!r} 不是数字（非神经方法请写 {NON_NEURAL}）"))

        # c. 来源
        src = row["来源"]
        if not any(h in src for h in SOURCE_HOSTS):
            out.append(Violation(path, lineno, "source",
                                 f"来源缺少可核验链接（需含 {' / '.join(SOURCE_HOSTS)} 之一）"))

        # d. 许可
        if not row["许可"].strip():
            out.append(Violation(path, lineno, "license", "许可为空"))

        # e. 指标带基准名
        if not re.search(r"\(.{2,}\)", row["指标"]):
            out.append(Violation(path, lineno, "metric",
                                 f"指标 {row['指标']!r} 缺少带基准名的括号，如 'UAR 73.4 (IEMOCAP)'"))

    return out


def check_file(path: Path) -> list[Violation]:
    return check_text(path.read_text(encoding="utf-8"), str(path))


SELFTEST_BAD = """\
| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| A | v1 | 3.7 | A | AudioSet | 521类 | IEMOCAP | UAR 71.2 (IEMOCAP) | Apache-2.0 | yes | yes: TFLite | https://github.com/tensorflow/models |
| B | v1 | 很多 | A | - | - | IEMOCAP | UAR 71.2 |  | yes | no | 见论文 |
| C | v1 | 30 | A | - | - | IEMOCAP | 待补 | TBD | yes | ? | https://arxiv.org/abs/0000.00000 |
"""

SELFTEST_GOOD = """\
| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| YAMNet | v1 | 3.7 | A | AudioSet | 521类 | IEMOCAP | UAR 71.2 (IEMOCAP) | Apache-2.0 | yes | yes: TFLite | https://github.com/tensorflow/models |
| ComParE+ SVM | opensmile 2016 | n/a(非神经) | A | - | 6类 | IEMOCAP | UAR 68.0 (IEMOCAP) | 研究用途 | yes | yes: 任意 CPU | https://github.com/audeering/opensmile |
"""


def selftest() -> int:
    ok = True

    good = check_text(SELFTEST_GOOD, "selftest-good")
    if good:
        ok = False
        print("FAIL 正例被误判：")
        for v in good:
            print("  ", v)
    else:
        print("ok   正例通过（2 条合规记录未报违规）")

    bad = check_text(SELFTEST_BAD, "selftest-bad")
    rules = {v.rule for v in bad}
    expect = {"params", "source", "license", "metric", "placeholder"}
    if not expect <= rules:
        ok = False
        print(f"FAIL 反例漏检，期望命中 {sorted(expect)}，实际 {sorted(rules)}")
    else:
        print(f"ok   反例全部拦下：{sorted(rules)}")

    # 非目标表格（表头不是「模型」）不应被误伤
    other = check_text("| 数据集 | 语言 | 规模 |\n| --- | --- | --- |\n| IEMOCAP | en | 12h |\n",
                       "selftest-other")
    if other:
        ok = False
        print("FAIL 非目标表格被误检：", other)
    else:
        print("ok   非目标表格（数据集表）未被误伤")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="校验声学情感模型调研表")
    ap.add_argument("files", nargs="*", type=Path, help="要校验的 markdown 文件")
    ap.add_argument("--selftest", action="store_true", help="用内联样例自检")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.files:
        ap.error("请给出文件，或用 --selftest")

    total = 0
    rows = 0
    violations: list[Violation] = []
    for f in args.files:
        if not f.exists():
            print(f"!! 文件不存在: {f}")
            return 1
        vs = check_file(f)
        violations.extend(vs)
        n = sum(1 for line in f.read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("|"))
        rows += n
        total += 1

    for v in violations:
        print(v)
    print(f"\n检查 {total} 个文件 / {rows} 行表格；违规 {len(violations)} 条")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
