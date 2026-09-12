#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_agc_table.py —— 自动增益（AGC）调研表的校验器。

与 check_ser_table.py / check_aed_table.py 同构：通用六条规则在共享核心
`scripts/table_lint.py` 里（列数 / 参数量 / 来源域名 / 许可非空 / 指标带括号 /
无占位符），本文件只声明 AGC 的 12 列名，并挂四条领域专属规则：

    python scripts/check_agc_table.py docs/research/auto-gain/*.md
    python scripts/check_agc_table.py --selftest

四条专属规则（对应 docs/research/auto-gain/00-taxonomy-and-metrics.md）：
  g. stage          作用点 列必须含 采集前 / 采集后 / 播放前 / 离线 之一
  h. control-target 控制对象 列必须含 数字增益 / 模拟增益 / 响度(LUFS) /
                    降噪掩码 / 联合(SE+AGC) / 非AGC(相邻 之一
  i. non-neural-form 参数量(M) 为 n/a(非神经) 时，版本/形态 必须含
                    经典 DSP 或 标准/测量算法
  j. selftest-ref   基准 列写 自测(no public benchmark) 时，指标 列必须
                    引用某个编号自测口径（匹配 自测口径 N）

g/h 是 AGC 的两条硬约束：作用点写错层不是"效果差"，是削波与增益泵浦；
控制对象不写清楚，降噪就会被混记为增益控制。
i 保证"没有参数量"只出现在非神经条目上，不成为逃避核实的口子。
j 保证"没有公开基准"不等于"可以不写指标"——必须引用口径编号。

只校验「表头与 12 列 schema 逐字一致」的数据表。以「模型」开头但列数明显偏少的
对照表会被跳过，不误报（该判据在 table_lint.MIN_SCHEMA_COLS）。

退出码：0 = 全通过；1 = 有违规。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from table_lint import Violation, check_text, run_cli  # noqa: E402

COLUMNS = ["模型", "版本/形态", "参数量(M)", "输入", "控制对象", "作用点",
           "基准", "指标", "许可", "可得", "edge", "来源"]

# --- 规则 g/h 的合法取值（与 00 口径文件的枚举表逐字一致） -------------------
STAGES = ("采集前", "采集后", "播放前", "离线")
CONTROL_TARGETS = ("数字增益", "模拟增益", "响度(LUFS)", "降噪掩码",
                   "联合(SE+AGC)", "非AGC(相邻")

NON_NEURAL = "n/a(非神经)"
NON_NEURAL_FORMS = ("经典 DSP", "标准/测量算法")

# 基准列写这个值，表示"该组件无公开基准，只能按 00 的编号自测口径测"
SELFTEST_BENCH_RE = re.compile(r"自测\s*[（(]\s*no\s+public\s+benchmark\s*[)）]", re.I)
# 指标列必须引用编号，如「自测口径 1」「自测口径2」
SELFTEST_REF_RE = re.compile(r"自测口径\s*\d+")


def rule_stage(row: dict, lineno: int) -> list:
    """g. 作用点：AGC 的第一列语义，写错层的后果是削波与增益泵浦。"""
    val = row.get("作用点", "")
    if not any(s in val for s in STAGES):
        return [Violation("<inline>", lineno, "stage",
                          f"作用点 {val!r} 未含 {STAGES} 之一")]
    return []


def rule_control_target(row: dict, lineno: int) -> list:
    """h. 控制对象：把 AGC 与相邻领域（降噪、修复）分开。"""
    val = row.get("控制对象", "")
    if not any(t in val for t in CONTROL_TARGETS):
        return [Violation("<inline>", lineno, "control-target",
                          f"控制对象 {val!r} 未含 {CONTROL_TARGETS} 之一")]
    return []


def rule_non_neural_form(row: dict, lineno: int) -> list:
    """i. 非神经条目必须在「版本/形态」列写明它是 DSP 还是标准/测量算法。"""
    if row.get("参数量(M)", "").strip() != NON_NEURAL:
        return []
    form = row.get("版本/形态", "")
    if not any(f in form for f in NON_NEURAL_FORMS):
        return [Violation("<inline>", lineno, "non-neural-form",
                          f"参数量为 {NON_NEURAL}，但版本/形态 {form!r} "
                          f"未含 {' / '.join(NON_NEURAL_FORMS)}")]
    return []


def rule_selftest_ref(row: dict, lineno: int) -> list:
    """j. 无公开基准的条目必须在「指标」列引用编号自测口径。"""
    if not SELFTEST_BENCH_RE.search(row.get("基准", "")):
        return []
    if SELFTEST_REF_RE.search(row.get("指标", "")):
        return []
    return [Violation("<inline>", lineno, "selftest-ref",
                      f"基准为自测(no public benchmark)，但指标 "
                      f"{row.get('指标', '')!r} 未引用「自测口径 N」")]


EXTRA_RULES = [rule_stage, rule_control_target, rule_non_neural_form, rule_selftest_ref]


# --- --selftest 样例 ---------------------------------------------------------

SELFTEST_GOOD = """\
| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
| WebRTC AGC2 | 经典 DSP（C 定点实现） | n/a(非神经) | 48kHz/10ms/单通道 | 数字增益 | 采集后 | 自测(no public benchmark) | 收敛时间 0.8s、稳态误差 0.4dB (自测口径 1) | BSD-3-Clause | yes | yes: 任意 CPU（C 定点实现） | https://github.com/webrtc-uwp/webrtc |
| GTCRN | 神经·卷积循环 | 0.048 | 16kHz/10ms/单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | yes: ONNX Runtime Mobile INT8 | https://github.com/Xiaobin-Rong/gtcrn |
"""

# 每行只触犯一类规则，便于确认九类反例各自命中
SELFTEST_BAD = """\
| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
| BadParams | 神经·卷积 | 很多 | 16kHz/10ms/单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | no | https://github.com/x/y |
| BadSource | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | no | 见论文 |
| BadLicense | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) |  | yes | no | https://github.com/x/y |
| BadMetric | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 降噪掩码 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 | MIT | yes | no | https://github.com/x/y |
| BadPlaceholder | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 待补 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | no | https://github.com/x/y |
| BadStage | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 降噪掩码 | 采集时 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | no | https://github.com/x/y |
| BadTarget | 神经·卷积 | 1.2 | 16kHz/10ms/单通道 | 增益 | 采集后 | VoiceBank-DEMAND | PESQ 2.87 (VoiceBank-DEMAND) | MIT | yes | no | https://github.com/x/y |
| BadNonNeuralForm | v2.0 | n/a(非神经) | 48kHz/10ms/单通道 | 数字增益 | 采集后 | 自测(no public benchmark) | 收敛时间 0.8s (自测口径 1) | BSD-3-Clause | yes | no | https://github.com/x/y |
| BadSelftestRef | 经典 DSP（C 定点实现） | n/a(非神经) | 48kHz/10ms/单通道 | 数字增益 | 采集后 | 自测(no public benchmark) | 收敛时间 0.8s (VoiceBank-DEMAND) | BSD-3-Clause | yes | no | https://github.com/x/y |
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
        print("ok   正例通过（2 条合规记录未报违规：经典 DSP + 小型神经，"
              "含 n/a(非神经) 与 自测口径 1 引用）")

    bad = check_text(SELFTEST_BAD, COLUMNS, "selftest-bad", EXTRA_RULES)
    rules = {v.rule for v in bad}
    expect = {"params", "source", "license", "metric", "placeholder",
              "stage", "control-target", "non-neural-form", "selftest-ref"}
    if not expect <= rules:
        ok = False
        print(f"FAIL 反例漏检，期望命中 {sorted(expect)}，实际 {sorted(rules)}")
    else:
        print(f"ok   反例全部拦下（{len(expect)} 类）：{sorted(rules)}")

    # 非目标表格（表头不是「模型」）不应被误伤
    other = check_text(
        "| 标准 | 目标响度 | 容差 | 真峰值上限 |\n| --- | --- | --- | --- |\n"
        "| GY/T 282-2014 | -24 LKFS | ±2 LU | -2 dBTP |\n",
        COLUMNS, "selftest-other", EXTRA_RULES)
    if other:
        ok = False
        print("FAIL 非目标表格被误检：", other)
    else:
        print("ok   非目标表格（响度标准表）未被误伤")

    # 以「模型」开头但列数远少于 schema 的对照表也不应被误伤
    other_model = check_text(
        "| 模型 | 作用点 | 实测 MCPS |\n| --- | --- | --- |\n"
        "| WebRTC AGC2 | 采集后 | 1.2 MCPS |\n",
        COLUMNS, "selftest-other-model-table", EXTRA_RULES)
    if other_model:
        ok = False
        print("FAIL 以「模型」开头的非 schema 对照表被误检：", other_model)
    else:
        print("ok   以「模型」开头的非 schema 对照表未被误伤")

    # 列数接近 12 却对不上的，要报出来（防 schema 表头被打错）
    typo = check_text(
        "| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 "
        "| 指标 | 许可 | 可得 | 来源 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n",
        COLUMNS, "selftest-schema-typo", EXTRA_RULES)
    if not any(v.rule == "schema" for v in typo):
        ok = False
        print("FAIL schema 表头缺列未被检出")
    else:
        print("ok   schema 表头缺列（11 列）被检出")

    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    return run_cli(argv, COLUMNS, EXTRA_RULES, selftest,
                   "校验自动增益（AGC）调研表")


if __name__ == "__main__":
    raise SystemExit(main())
