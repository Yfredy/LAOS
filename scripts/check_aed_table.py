#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_aed_table.py —— 音频事件识别（AED）调研表的校验器。

调研型计划里没有 pytest 可写，但"每条记录都能被核验"这条必须能被机器检查，
否则"我查过了"和"我觉得它有"没有区别。这个脚本就是那道闸：

    python scripts/check_aed_table.py docs/research/audio-events/*.md
    python scripts/check_aed_table.py --selftest

口径来源：docs/research/audio-events/00-taxonomy-and-metrics.md
通用规则（a–f）来自共享核心 scripts/table_lint.py，与 SER 校验器逐条对齐：
  a. 每行列数 == 12
  b. 参数量(M) 是数字，或 n/a(非神经)
  c. 来源 含 arxiv.org / huggingface.co / github.com 之一
  d. 许可 非空
  e. 指标 含带基准名的括号，如 "mAP 0.502 (AudioSet AS-2M full, tagging)"
  f. 单元格不得为 TBD / 待补 / TODO / ?

AED 专属两条（以 extra_rules 挂上去）：
  g. task-type     —— 输出 列必须含 tagging / SED / ASC / 开放词表 之一
  h. audioset-split—— 基准 列出现 AudioSet 时，必须同时标注 AS-20K / AS-2M / full 之一
                      （同一模型在 AS-20K 与 AS-2M full 上 mAP 可差 15+ 点，不标划分不许入表）

只校验「表头与 12 列 schema 逐字一致」的数据表。以「模型」开头但列数明显偏少的对照表
（如「模型 / 平台 / 实测时延」）会被跳过，不误报；列数接近 12 却对不上则报 schema 错误。

退出码：0 = 全通过；1 = 有违规。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 `from table_lint import ...` 在本文件被任意 cwd 调用时都能命中同目录的共享核心。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from table_lint import Violation, check_text, run_cli  # noqa: E402

# 12 列，与 docs/research/speech-emotion/ 的 SER schema 逐字一致。
# 唯一差别在「输出」列的填写规则（AED 记"任务类型+类别数"），列名不动。
COLUMNS = ["模型", "版本/权重", "参数量(M)", "模态", "预训练语料", "输出",
           "基准", "指标", "许可", "权重可得", "edge", "来源"]

# 规则 g：任务类型（大小写敏感，写法见口径文件「任务类型」表）
TASK_TYPES = ("tagging", "SED", "ASC", "开放词表")

# 规则 h：AudioSet 划分标记（"AS-2M full" 已被 "AS-2M" 覆盖，仍按口径文件逐字列出）
SPLIT_TOKENS = ("AS-20K", "AS-2M", "full")

# table_lint.check_text 不把 path 透传给 extra_rules，专属规则用统一伪路径；
# 定位靠「行号 + 违规单元格内容」，detail 里会把原值抄出来便于 grep。
RULE_PATH = "<aed>"


def rule_task_type(row: dict, lineno: int) -> list:
    """规则 g：输出 列必须写明任务类型，否则跨任务类型的指标不可比。"""
    val = row.get("输出", "")
    if any(t in val for t in TASK_TYPES):
        return []
    return [Violation(RULE_PATH, lineno, "task-type",
                      f"输出 {val!r} 未标注任务类型"
                      f"（须含 {' / '.join(TASK_TYPES)} 之一，"
                      f"如 'tagging/521类'、'SED/10类'）")]


def rule_audioset_split(row: dict, lineno: int) -> list:
    """规则 h：AudioSet 数字必须注明 AS-20K 还是 AS-2M full。"""
    bench = row.get("基准", "")
    if "audioset" not in bench.lower():
        return []
    low = bench.lower()
    if any(t.lower() in low for t in SPLIT_TOKENS):
        return []
    return [Violation(RULE_PATH, lineno, "audioset-split",
                      f"基准 {bench!r} 含 AudioSet 但未标注划分"
                      f"（须含 {' / '.join(SPLIT_TOKENS)} 之一，"
                      f"如 'AudioSet AS-2M full'）")]


EXTRA_RULES = [rule_task_type, rule_audioset_split]

# 正例：三条合规记录，覆盖 tagging / 开放词表 / ASC，且 AudioSet 都标了划分。
# 数字是格式示例，不代表任何真实模型。
SELFTEST_GOOD = """\
| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| 示例·tagging | v1 | 12.3 | A | AudioSet AS-2M full | tagging/521类 | AudioSet AS-2M full | mAP 0.412 (AudioSet AS-2M full, tagging) | Apache-2.0 | yes | yes: TFLite INT8 | https://github.com/example/repo |
| 示例·开放词表 | CLAP 头 | 86 | A+T | WavCaps | 开放词表/任意类 | DESED | PSDS1 0.422 (DESED, 开放词表 SED) | MIT | yes | no | https://arxiv.org/abs/0000.00000 |
| 示例·ASC | CP-Mobile | 0.122 | A | AudioSet AS-2M full | ASC/10类 | DCASE2025 Task1 | 61.47% (DCASE2025 Task1, ASC) | MIT | yes | unknown(未找到公开转换案例) | https://github.com/example/cp-mobile |
| 示例·非神经 | ComParE 2016 | n/a(非神经) | A | - | tagging/10类 | ESC-50 | 准确率 76.0 (ESC-50, tagging) | 研究用途 | yes | yes: 任意 CPU | https://github.com/audeering/opensmile |
"""

# 反例：覆盖 params / source / license / metric / placeholder / task-type / audioset-split 七类。
SELFTEST_BAD = """\
| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 | 许可 | 权重可得 | edge | 来源 |
| 反例A | v1 | 很多 | A | AudioSet AS-2M full | tagging/521类 | AudioSet AS-2M full | mAP 0.412 |  | yes | no | 见论文 |
| 反例B | v1 | 86 | A | AudioSet AS-2M full | 521类 | AudioSet | mAP 0.486 (AudioSet, tagging) | MIT | 待补 | ? | https://arxiv.org/abs/0000.00000 |
"""


def selftest() -> int:
    ok = True

    good = check_text(SELFTEST_GOOD, COLUMNS, "selftest-good", EXTRA_RULES)
    if good:
        ok = False
        print("FAIL 正例被误判：")
        for v in good:
            print("  ", v)
    else:
        print("ok   正例通过（4 条合规记录未报违规）")

    bad = check_text(SELFTEST_BAD, COLUMNS, "selftest-bad", EXTRA_RULES)
    rules = {v.rule for v in bad}
    expect = {"params", "source", "license", "metric", "placeholder",
              "task-type", "audioset-split"}
    if not expect <= rules:
        ok = False
        missing = sorted(expect - rules)
        print(f"FAIL 反例漏检：未命中 {missing}，实际命中 {sorted(rules)}")
    else:
        print(f"ok   反例七类全部拦下：{sorted(rules)}")

    # 非目标表格（表头不是「模型」）不应被误伤
    other = check_text(
        "| 数据集 | 语言 | 模态 | 规模 | 许可 |\n| --- | --- | --- | --- | --- |\n"
        "| AudioSet | en | A+V | 2,084,320 | CC-BY |\n",
        COLUMNS, "selftest-other", EXTRA_RULES)
    if other:
        ok = False
        print("FAIL 非目标表格（数据集表）被误检：", other)
    else:
        print("ok   非目标表格（数据集表）未被误伤")

    # 以「模型」开头但列数远少于 schema 的对照表不应被误伤
    other_model = check_text(
        "| 模型 | 平台 / 计算单元 | 实测 MMACs |\n| --- | --- | --- |\n"
        "| YAMNet | SD8 Elite NPU | 29.4 |\n",
        COLUMNS, "selftest-other-model-table", EXTRA_RULES)
    if other_model:
        ok = False
        print("FAIL 以「模型」开头的非 schema 对照表被误检：", other_model)
    else:
        print("ok   以「模型」开头的非 schema 对照表未被误伤")

    # 列数接近 12 却对不上的，要报出来（防 schema 表头被打错）
    typo = check_text(
        "| 模型 | 版本/权重 | 参数量(M) | 模态 | 预训练语料 | 输出 | 基准 | 指标 "
        "| 许可 | 权重可得 | 来源 |\n| --- | --- | --- | --- | --- | --- | --- | --- "
        "| --- | --- | --- |\n",
        COLUMNS, "selftest-schema-typo", EXTRA_RULES)
    if not any(v.rule == "schema" for v in typo):
        ok = False
        print("FAIL schema 表头缺列（11 列）未被检出")
    else:
        print("ok   schema 表头缺列（11 列）被检出")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv, COLUMNS, EXTRA_RULES, selftest,
                   "校验音频事件识别（AED）调研表")


if __name__ == "__main__":
    raise SystemExit(main())
