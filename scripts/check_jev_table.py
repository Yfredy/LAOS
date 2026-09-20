#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_jev_table.py —— Jev 决策模型调研表的校验器。

复用 `scripts/table_lint.py` 的共享部分：
  - `Violation` 类型（违规记录的字段容器）
  - `split_row` / `is_separator`（markdown 表格解析）
  - `PLACEHOLDERS` / `SOURCE_HOSTS`（通用常量）

口径裁定（续接计划 Task 1，编号 J1–J4，详见
`docs/research/jev/00-taxonomy-and-metrics.md` 的「口径裁定记录」）：

- **J1**：`table_lint.check_text` 的表头触发列**硬编码为「模型」**（见
  `table_lint.py` 第 110 行），而本调研的 12 列 schema 以「项目」开头。
  直接调 `run_cli` / `check_text` 会**整张 Jev 表被跳过、零校验**。
  因此本文件在复用上述共享符号的前提下，维护一份触发列可变的 `check_text`
  副本；**不修改 `table_lint.py`**。
- **J2**：`table_lint` 的通用规则 b(params) / e(metric) 依赖「参数量(M)」「指标」
  两列，Jev schema 没有这两列，天然 inert。Jev 可触发的通用规则为
  `cols` / `source` / `license` / `placeholder` 四类 + 4 条 Jev 专属规则；
  再加 `schema` 表头错配，selftest 一共覆盖 **9 类**违规，与计划「九类反例」
  对齐（params / metric 两类不适用，不强行断言）。
- **J3**：`rule_category` 的合法枚举不含「复现(单token打分)」，但用**子串匹配**
  （"复现" ∈ "复现(单token打分)"）使其通过——这是有意设计，既允许真复现、
  也允许单 token 打分两类都合法，同时杜绝「客户端 / 应用 / 其他」之外的自由发挥。
- **J4**：`Violation` 实际签名是 `(path, line, rule, detail)` 四参，计划骨架里
  `Violation(lineno, ...)` 是笔误，已按真实签名修正。

用法：

    python scripts/check_jev_table.py docs/research/jev/*.md
    python scripts/check_jev_table.py --selftest

退出码：0 = 全通过；1 = 有违规 / 用法错误。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 让脚本自身目录进入 sys.path，确保 `python scripts/check_jev_table.py` 能找到
# 同目录的 table_lint.py（不依赖调用方 cwd）。
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---- 复用 table_lint 的共享部分（不修改 table_lint.py）-----------------------
from table_lint import (  # noqa: F401  —— 这些是本校验器的可复用核心
    Violation,
    split_row,
    is_separator,
    PLACEHOLDERS,
    SOURCE_HOSTS,
)

# 与 SER 校验器一致的「非 schema 对照表」判定阈值：列数少于此值的「项目」表
# 视作别的对照表，跳过不误报；列数接近 12 却对不上的，报 schema 错误。
MIN_SCHEMA_COLS = 10

# 12 列 schema（列名逐字照抄口径文件，Task 2/3/4/5/6 全部按名消费）。
COLUMNS = ["项目", "类别", "星数", "语言", "许可", "运行时依赖",
           "端侧可跑", "原语", "报告延迟", "laos 落点", "验证状态", "来源"]

# 通用规则按列名索引（领域无关）。Jev schema 只有「许可」「来源」两列命中，
# 故只有 license / source 两条通用规则会被触发；placeholder / cols 对所有列生效。
COL_SOURCE = "来源"
COL_LICENSE = "许可"

# 类别合法枚举（J3：子串匹配，故「复现(单token打分)」凭 "复现" 通过）。
CAT_OK = ("官方", "客户端", "复现", "应用", "清单", "评测", "工具")

# 运行时依赖必须点名的关键字（不许写「轻量」之类模糊词）。
DEP_OK = ("torch", "onnx", "rust", "云端API", "llama.cpp", "未知")

# 延迟数据源标记（每条延迟必须说明是哪种来源）。
LAT_SRC = ("官方自测", "第三方", "未实测")


# ---------------------------------------------------------------------------
# 四条 Jev 专属规则（签名 (row, lineno) -> list[Violation]）
# 专属规则构造 Violation 时第一参填占位串，check_text 会统一覆写为真实文件名。
# ---------------------------------------------------------------------------

def rule_category(row, lineno):
    """规则 g：类别必须落在枚举内，杜绝自由发挥。"""
    v = row.get("类别", "")
    if not any(k in v for k in CAT_OK):
        return [Violation("<jev>", lineno, "category",
                          "类别必须含 %s 之一，当前=%r" % ("/".join(CAT_OK), v))]
    return []


def rule_runtime_dep(row, lineno):
    """规则 h：运行时依赖不许写模糊词，必须点名。"""
    v = row.get("运行时依赖", "")
    if not any(k in v for k in DEP_OK):
        return [Violation("<jev>", lineno, "runtime-dep",
                          "运行时依赖必须点名 %s 之一（不许写'轻量'），当前=%r"
                          % ("/".join(DEP_OK), v))]
    return []


def rule_edge_conflict(row, lineno):
    """规则 i：端侧可跑=yes 时，运行时依赖不得含云端API（本调研最易犯的错）。"""
    if row.get("端侧可跑", "").strip() == "yes" and "云端API" in row.get("运行时依赖", ""):
        return [Violation("<jev>", lineno, "edge-conflict",
                          "端侧可跑=yes 但依赖云端API，矛盾")]
    return []


def rule_latency(row, lineno):
    """规则 j：延迟数字必须带单位 + 必须标数据源（官方自测/第三方/未实测）。"""
    v = row.get("报告延迟", "")
    if re.search(r"\d", v):
        if not re.search(r"\d+\s*(ms|s|µs)", v):
            return [Violation("<jev>", lineno, "latency", "延迟缺单位：%r" % v)]
        if not any(k in v for k in LAT_SRC):
            return [Violation("<jev>", lineno, "latency",
                              "延迟未标数据源（官方自测/第三方/未实测）：%r" % v)]
    return []


EXTRA_RULES = [rule_category, rule_runtime_dep, rule_edge_conflict, rule_latency]


# ---------------------------------------------------------------------------
# check_text：触发列可变的副本（J1）。其余逻辑与 table_lint.check_text 对齐。
# ---------------------------------------------------------------------------

def check_text(text: str,
               path: str = "<inline>",
               columns=COLUMNS,
               extra_rules=EXTRA_RULES) -> list:
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
            # 只认以 schema 首列（「项目」）开头、且列名逐字一致的 12 列数据表。
            # 列数明显少于 schema 的（对照表）直接跳过，不误报。
            if cells and cells[0] == columns[0]:
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

        # d. 许可
        if COL_LICENSE in row and not row[COL_LICENSE].strip():
            out.append(Violation(path, lineno, "license", "许可为空"))

        # c. 来源
        if COL_SOURCE in row:
            src = row[COL_SOURCE]
            if not any(h in src for h in SOURCE_HOSTS):
                out.append(Violation(path, lineno, "source",
                                     f"来源缺少可核验链接"
                                     f"（需含 {' / '.join(SOURCE_HOSTS)} 之一）"))

        # 领域专属规则（统一覆写 path，保证 file:line 可直接跳转）。
        for rule in extra_rules:
            for v in rule(row, lineno):
                v.path = path
                out.append(v)

    return out


def check_file(path: Path) -> list:
    return check_text(Path(path).read_text(encoding="utf-8"), str(path))


def count_rows(path: Path) -> int:
    return sum(1 for line in Path(path).read_text(encoding="utf-8").splitlines()
               if line.strip().startswith("|"))


# ---------------------------------------------------------------------------
# 内联 selftest：正例通过、九类反例各命中、非目标表不误伤。
# ---------------------------------------------------------------------------

SELFTEST_GOOD = """\
| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| edgejev | 复现 | 2 | Python | MIT | torch | yes | Choice | 15.6 ms 官方自测 | 漏斗③蒸馏 | 已读代码 | https://github.com/yzfly/edgejev |
| von | 复现(单token打分) | 116 | Python | Apache-2.0 | onnx | no | Score | 未实测 | 漏斗① | 仅 README | https://github.com/wfzyx/von |
"""

# 反例集：覆盖 source / license / placeholder / category / runtime-dep /
# latency / edge-conflict / cols 八类，schema 表头错配单独再测 → 共九类。
SELFTEST_BAD = """\
| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bad1 | 未知类 | 1 | ? |  | 轻量 | no | 啥 | 15 | 无 | 未核实 | 见论文 |
| bad2 | 复现 | 1 | Python | MIT | 云端API | yes | Choice | 15 ms 官方自测 | 漏斗③ | 已实测 | https://github.com/foo/baz |
| bad3 | 复现 | 1 | Python | MIT | torch | no | Choice | 15 ms 官方自测 | 漏斗③ | 已实测 |
"""

# 表头缺一列（11 列），应触发 schema 错配。
SELFTEST_SCHEMA_TYPO = """\
| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| x | 复现 | 1 | Py | MIT | torch | no | Choice | 15 ms 官方自测 | 漏斗③ | 已实测 |
"""

# 非目标表：不以「项目」开头的对照表，不应被误检。
SELFTEST_OTHER = "| 数据集 | 语言 | 规模 |\n| --- | --- | --- |\n| IEMOCAP | en | 12h |\n"

# 以「项目」开头但列数远少于 schema 的对照表，不应被误检。
SELFTEST_OTHER_MODEL = (
    "| 项目 | 平台 / 计算单元 | 实测时延 |\n| --- | --- | --- |\n"
    "| edgejev | aarch64 CPU | 15.6 ms |\n"
)


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
    expect = {"source", "license", "placeholder", "category",
              "runtime-dep", "latency", "edge-conflict", "cols"}
    if not expect <= rules:
        ok = False
        print(f"FAIL 反例漏检，期望命中 {sorted(expect)}，实际 {sorted(rules)}")
    else:
        print(f"ok   八类 Jev 反例全部拦下：{sorted(rules)}")

    typo = check_text(SELFTEST_SCHEMA_TYPO, "selftest-schema-typo")
    if not any(v.rule == "schema" for v in typo):
        ok = False
        print("FAIL schema 表头缺列未被检出")
    else:
        print("ok   schema 表头缺列（11 列）被检出")

    other = check_text(SELFTEST_OTHER, "selftest-other")
    if other:
        ok = False
        print("FAIL 非目标表格被误检：", other)
    else:
        print("ok   非目标表格（数据集表）未被误伤")

    other_model = check_text(SELFTEST_OTHER_MODEL, "selftest-other-model")
    if other_model:
        ok = False
        print("FAIL 以「项目」开头的非 schema 对照表被误检：", other_model)
    else:
        print("ok   以「项目」开头的非 schema 对照表未被误伤")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    # J1：不直接调 table_lint.run_cli（其 check_text 硬编码「模型」触发列会导致
    # Jev 表被整张跳过）；此处用本文件的 check_text + EXTRA_RULES 组装等价 CLI。
    ap = argparse.ArgumentParser(description="校验 Jev 决策模型调研表")
    ap.add_argument("files", nargs="*", type=Path, help="要校验的 markdown 文件")
    ap.add_argument("--selftest", action="store_true", help="用内联样例自检")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.selftest:
        return selftest()
    if not args.files:
        ap.error("请给出文件，或用 --selftest")

    violations: list = []
    total = 0
    rows = 0
    for f in args.files:
        if not f.exists():
            print(f"!! 文件不存在: {f}")
            return 1
        violations.extend(check_file(f))
        rows += count_rows(f)
        total += 1

    for v in violations:
        print(v)
    print(f"\n检查 {total} 个文件 / {rows} 行表格；违规 {len(violations)} 条")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
