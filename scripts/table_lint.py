#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""table_lint.py —— 与领域无关的 markdown 调研表校验核心。

三个调研（SER / AED / AGC）都需要同一件事：**"每条记录都能被核验"必须能被机器检查**，
否则"我查过了"和"我觉得它有"没有区别。三个领域的表格列不同、专属规则不同，
但核心的六条通用规则完全一样，因此抽在这里，各领域只写薄 CLI：

    scripts/check_ser_table.py   语音情感（已定稿，不改动）
    scripts/check_aed_table.py   音频事件识别
    scripts/check_agc_table.py   自动增益

用法（各领域 CLI）：

    from table_lint import check_text, check_file, run_cli

    COLUMNS = ["模型", ...]                       # 12 列，逐字照抄口径文件
    EXTRA_RULES = [rule_task_type, rule_split]    # 领域专属规则，可选

    sys.exit(run_cli(sys.argv[1:], COLUMNS, EXTRA_RULES, selftest, "说明文字"))

通用六条规则（与 check_ser_table.py 逐条对齐）：
  a. 每行列数 == len(COLUMNS)
  b. 参数量(M) 是数字，或 n/a(非神经)
  c. 来源 含 arxiv.org / huggingface.co / github.com 之一
  d. 许可 非空
  e. 指标 含带基准名的括号，如 "UAR 73.4 (IEMOCAP)"
  f. 单元格不得为 TBD / 待补 / TODO / ?

只校验「表头与 schema 逐字一致」的数据表。以「模型」开头但列数明显偏少的对照表
（如「模型 / 平台 / 实测时延」）会被跳过，不误报；列数接近却对不上则报 schema 错误。

退出码：0 = 全通过；1 = 有违规。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

# 列数少于此值的「模型」开头表格视作另一张对照表，跳过不误报。
# 只有列数接近 schema 却对不上的，才认为是表头打错了，需要报出来。
MIN_SCHEMA_COLS = 10

PLACEHOLDERS = {"tbd", "待补", "todo", "?"}
NON_NEURAL = "n/a(非神经)"
SOURCE_HOSTS = ("arxiv.org", "huggingface.co", "github.com")

PARAMS_RE = re.compile(r"\d+(\.\d+)?|\d+(\.\d+)?[–-]\d+(\.\d+)?")
METRIC_RE = re.compile(r"\(.{2,}\)")

# 通用规则按列名索引，不依赖列位置——各领域列名集合不同，但都含这四个通用列。
COL_PARAMS = "参数量(M)"
COL_SOURCE = "来源"
COL_LICENSE = "许可"
COL_METRIC = "指标"

ExtraRule = Callable[[dict, int], list]


class Violation:
    def __init__(self, path: str, line: int, rule: str, detail: str):
        self.path, self.line, self.rule, self.detail = path, line, rule, detail

    def __str__(self) -> str:
        return f"{self.path}:{self.line}  [{self.rule}] {self.detail}"

    def __repr__(self) -> str:  # pragma: no cover
        return str(self)


def split_row(line: str) -> list:
    """按 markdown 表格切分单元格（不处理转义竖线：调研表里不该出现）。"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def is_separator(cells: Sequence[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells)


def check_text(text: str,
               columns: Sequence[str],
               path: str = "<inline>",
               extra_rules: Iterable[ExtraRule] = ()) -> list:
    """校验一段 markdown，返回 Violation 列表。"""
    columns = list(columns)
    ncol = len(columns)
    out: list = []
    in_table = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            in_table = False
            continue

        cells = split_row(line)

        if not in_table:
            # 只认以「模型」开头、且列名与 schema 逐字一致的数据表。
            # 列数明显少于 schema 的（对照表、规则表）直接跳过，不误报。
            if cells and cells[0] == "模型":
                if len(cells) < MIN_SCHEMA_COLS:
                    continue
                if list(cells) != columns:
                    out.append(Violation(path, lineno, "schema",
                                         f"表头列与 schema 不一致：{cells}"))
                    continue
                in_table = True
            continue

        if is_separator(cells):
            continue

        if not in_table:
            continue

        # a. 列数
        if len(cells) != ncol:
            out.append(Violation(path, lineno, "cols",
                                 f"列数 {len(cells)} != {ncol}"))
            continue

        row = dict(zip(columns, cells))

        # f. 占位符
        for col, val in row.items():
            if val.strip().lower() in PLACEHOLDERS:
                out.append(Violation(path, lineno, "placeholder",
                                     f"{col} 列是占位符 {val!r}"))

        # b. 参数量（按列名索引，领域无关）
        if COL_PARAMS in row:
            params = row[COL_PARAMS]
            if params.strip().lower() != NON_NEURAL and not PARAMS_RE.fullmatch(params):
                out.append(Violation(path, lineno, "params",
                                     f"参数量 {params!r} 不是数字"
                                     f"（非神经方法请写 {NON_NEURAL}）"))

        # c. 来源
        if COL_SOURCE in row:
            src = row[COL_SOURCE]
            if not any(h in src for h in SOURCE_HOSTS):
                out.append(Violation(path, lineno, "source",
                                     f"来源缺少可核验链接"
                                     f"（需含 {' / '.join(SOURCE_HOSTS)} 之一）"))

        # d. 许可
        if COL_LICENSE in row and not row[COL_LICENSE].strip():
            out.append(Violation(path, lineno, "license", "许可为空"))

        # e. 指标带基准名
        if COL_METRIC in row and not METRIC_RE.search(row[COL_METRIC]):
            out.append(Violation(path, lineno, "metric",
                                 f"指标 {row[COL_METRIC]!r} 缺少带基准名的括号，"
                                 f"如 'UAR 73.4 (IEMOCAP)'"))

        # 领域专属规则。
        # 专属规则的签名是 (row, lineno)，拿不到 path，因此它们构造 Violation 时
        # 只能填一个占位（如 "<aed>"）。这里统一覆写为真实文件名，
        # 保证违规输出的 file:line 可以直接跳转。
        for rule in extra_rules:
            for v in rule(row, lineno):
                v.path = path
                out.append(v)

    return out


def check_file(path: Path,
               columns: Sequence[str],
               extra_rules: Iterable[ExtraRule] = ()) -> list:
    return check_text(Path(path).read_text(encoding="utf-8"),
                      columns, str(path), extra_rules)


def count_rows(path: Path) -> int:
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines()
               if line.strip().startswith("|"))


def run_cli(argv: Sequence[str] | None,
            columns: Sequence[str],
            extra_rules: Iterable[ExtraRule] = (),
            selftest_fn: Callable[[], int] | None = None,
            description: str = "校验调研表") -> int:
    """各领域 CLI 的 main() 直接调这个。"""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("files", nargs="*", type=Path, help="要校验的 markdown 文件")
    ap.add_argument("--selftest", action="store_true", help="用内联样例自检")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        if selftest_fn is None:
            print("!! 本校验器未定义 --selftest")
            return 1
        return selftest_fn()
    if not args.files:
        ap.error("请给出文件，或用 --selftest")

    violations: list = []
    total = 0
    rows = 0
    for f in args.files:
        if not f.exists():
            print(f"!! 文件不存在: {f}")
            return 1
        violations.extend(check_file(f, columns, extra_rules))
        rows += count_rows(f)
        total += 1

    for v in violations:
        print(v)
    print(f"\n检查 {total} 个文件 / {rows} 行表格；违规 {len(violations)} 条")
    return 1 if violations else 0


if __name__ == "__main__":  # pragma: no cover
    print("table_lint.py 是共享核心，请通过各领域的 check_*_table.py 调用。")
    sys.exit(2)
