#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 方法论参考 jev-chat-jarvis tools/jev/calibrate.py（MIT, github.com/jev-chat/jev-chat-jarvis）——labeled set + per-question confusion + 置信分桶
"""calibrate_judge.py —— 判断层校准台（stdlib only）。

对 laos 四个 Jev gate 问句跑人工标注集，量出一个判断后端的混淆矩阵与
置信分布——高置信段的误判即"过自信警报"（RuleBackend 的误杀/漏杀都要
暴露，边界例正是校准的意义，例：jail 内合法 `rm -rf /tmp/work` 人工标
expect_deny=false，规则后端却按关键词 deny → 记一次 fp）。

四个 gate 的 (context, question) 忠实复刻各消费点的真实调用形态：

    prejudge  laos/kernel.py _jev_prejudge：context 固定为横幅描述，
              问句 = PREJUDGE_JUDGE_QUESTION.format(...)（kernel 导出的
              criteria 式模板常量；标注例 context 充任 {tool}，{args} 留空）
    memory    laos/memory.py REMEMBER_JUDGE_QUESTION（deny=不入库）
    compact   laos/context.py COMPACT_JUDGE_QUESTION（deny=不可丢弃）
    skill     laos/skills.py SKILL_JUDGE_QUESTION（deny=轨迹未达成不沉淀）

CLI：

    python scripts/calibrate_judge.py [--backend rule|local] [--limit N]

    rule   零依赖关键词兜底（默认，LAOS_JEV_BACKEND 的同名后端）
    local  OpenAI 兼容端点（读 LAOS_JEV_ENDPOINT；缺端点/网络故障逐例
           fail-open 记 allow 0.0 并标 error 键，全例失败时退出码 1）

输出：终端人读报告（render_report）——总体/各 gate 混淆 + 置信分桶 +
过自信警报点名。退出码 0（校准台量数，不把准确率当门禁——阈值另议）；
唯一非零路径 = 全例后端故障（fail-open 记的 allow/0.0 不构成校准数据）。

    python -m unittest tests.test_calibrate_judge -v
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from laos.context import COMPACT_JUDGE_QUESTION  # noqa: E402
from laos.judge import LocalBackend, RuleBackend  # noqa: E402
from laos.kernel import PREJUDGE_JUDGE_QUESTION  # noqa: E402
from laos.memory import REMEMBER_JUDGE_QUESTION  # noqa: E402
from laos.skills import SKILL_JUDGE_QUESTION  # noqa: E402

__all__ = [
    "GATES",
    "PREJUDGE_CONTEXT",
    "confidence_buckets",
    "confusion",
    "gate_question",
    "load_labeled_set",
    "main",
    "render_report",
    "run_cases",
]

GATES = ("prejudge", "memory", "compact", "skill")

# kernel._jev_prejudge 的 context 实参（逐字复刻）
PREJUDGE_CONTEXT = "内核高风险 syscall 确认横幅预审"
# 问句模板的 agent 名（校准台自报身份，进审计友好）
CALIB_AGENT = "calibrate"

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "judge_labeled_set.json"

# 标注集契约：总量与每 gate 下限（校准台自身的验收线）
MIN_TOTAL = 48
MIN_PER_GATE = 12


def gate_question(gate: str, case_context: str) -> tuple[str, str]:
    """标注例 → 该 gate 的真实 (context, question) 调用形态。"""
    if gate == "prejudge":
        # PREJUDGE_JUDGE_QUESTION.format（与 kernel._jev_prejudge 同一模板，
        # kernel.py 模块常量；标注例的 context 充任 {tool}，{args} 留空——
        # bench 例不拆参数）
        return PREJUDGE_CONTEXT, PREJUDGE_JUDGE_QUESTION.format(
            tool=case_context, args="", agent=CALIB_AGENT)
    if gate == "memory":
        return case_context, REMEMBER_JUDGE_QUESTION
    if gate == "compact":
        return case_context, COMPACT_JUDGE_QUESTION
    if gate == "skill":
        return case_context, SKILL_JUDGE_QUESTION
    raise ValueError(f"未知 gate：{gate}（合法值 {GATES}）")


def run_cases(cases: list[dict], backend) -> list[dict]:
    """逐例跑后端 noul，返回 [{id, gate, expect_deny, got_deny, confidence}]。

    got_deny = (verdict == "deny")。单例后端故障不炸整轮：该例记
    allow 0.0 并附 "error" 键（与 SafeJudge 的 fail-open 哲学一致——
    校准台量数，不因一例网络抖动丢整轮统计）。
    """
    rows: list[dict] = []
    for case in cases:
        context, question = gate_question(case["gate"], case["context"])
        try:
            result = backend.noul(context, question)
            verdict = str(result.verdict)
            confidence = min(max(float(result.confidence), 0.0), 1.0)
            error = None
        except Exception as exc:  # noqa: BLE001 —— 单例 fail-open，整轮照跑
            verdict, confidence, error = "allow", 0.0, str(exc)
        row = {"id": case["id"], "gate": case["gate"],
               "expect_deny": bool(case["expect_deny"]),
               "got_deny": verdict == "deny",
               "confidence": confidence}
        if error:
            row["error"] = error
        rows.append(row)
    return rows


def confusion(rows) -> dict:
    """混淆矩阵（deny 为正类）：tp/fp/tn/fn + accuracy/precision/recall。

    空集安全（全 0，accuracy=0.0）；比率 round 4 位，免浮点尾噪。
    """
    tp = fp = tn = fn = 0
    for row in rows:
        expect, got = bool(row["expect_deny"]), bool(row["got_deny"])
        if expect and got:
            tp += 1
        elif got:
            fp += 1
        elif expect:
            fn += 1
        else:
            tn += 1
    total = tp + fp + tn + fn
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
    }


# 分桶阶梯：顶桶闭区间 [0.9, 1.0]（0.95 与 1.0 皆入顶桶），其余左闭右开
BUCKET_EDGES = (("0.0-0.3", 0.0, 0.3), ("0.3-0.5", 0.3, 0.5),
                ("0.5-0.7", 0.5, 0.7), ("0.7-0.9", 0.7, 0.9))
TOP_BUCKET = "0.9-1.0"
BUCKET_ORDER = (TOP_BUCKET, "0.7-0.9", "0.5-0.7", "0.3-0.5", "0.0-0.3")


def _bucket_label(confidence: float) -> str:
    if confidence >= 0.9:
        return TOP_BUCKET
    for label, lo, hi in BUCKET_EDGES:
        if lo <= confidence < hi:
            return label
    return BUCKET_EDGES[-1][0]  # 理论不可达（confidence 已钳 0..1）


def confidence_buckets(rows) -> dict:
    """按置信度分桶：{"0.9-1.0": {"n": x, "deny_rate": y}, ...}（五桶恒在）。

    顶桶的 n×deny_rate 叠加混淆里的 fp/fn 即"过自信警报"——后端在最高
    置信段仍判错，说明置信度不可直接当放行阈值（LAOS_JEV_AUTOGATE_MIN）。
    """
    counts = {label: {"n": 0, "deny": 0} for label in BUCKET_ORDER}
    for row in rows:
        bucket = counts[_bucket_label(min(max(float(row["confidence"]), 0.0), 1.0))]
        bucket["n"] += 1
        if row["got_deny"]:
            bucket["deny"] += 1
    return {label: {"n": b["n"],
                    "deny_rate": round(b["deny"] / b["n"], 4) if b["n"] else 0.0}
            for label, b in counts.items()}


def render_report(rows) -> str:
    """人读报告（终端打印）：总体 + 各 gate 混淆 + 置信分桶 + 过自信警报。"""
    overall = confusion(rows)
    lines = [
        "判断层校准报告（labeled set → judge backend）",
        "=" * 48,
        f"n={len(rows)}  tp={overall['tp']} fp={overall['fp']} "
        f"tn={overall['tn']} fn={overall['fn']}",
        f"accuracy={overall['accuracy']}  precision={overall['precision']}  "
        f"recall={overall['recall']}",
        "",
        "各 gate 混淆（per-question）：",
    ]
    for gate in GATES:
        sub = [row for row in rows if row["gate"] == gate]
        cm = confusion(sub)
        lines.append(
            f"  {gate:<8} n={len(sub):>3}  tp={cm['tp']} fp={cm['fp']} "
            f"tn={cm['tn']} fn={cm['fn']}  accuracy={cm['accuracy']}  "
            f"precision={cm['precision']}  recall={cm['recall']}")
    lines += ["", "置信分桶（n / deny_rate）："]
    for label in BUCKET_ORDER:
        bucket = confidence_buckets(rows)[label]
        lines.append(f"  {label}  n={bucket['n']:>3}  deny_rate={bucket['deny_rate']}")
    # 过自信警报：顶桶内判错的例点名（高置信误杀/漏杀）
    wrong_top = [row for row in rows
                 if row["confidence"] >= 0.9 and row["got_deny"] != row["expect_deny"]]
    lines.append("")
    if wrong_top:
        detail = ", ".join(f"{row['id']}({'误杀' if row['got_deny'] else '漏杀'})"
                           for row in wrong_top)
        lines.append(f"过自信警报：0.9-1.0 桶误判 {len(wrong_top)}/{sum(1 for row in rows if row['confidence'] >= 0.9)} → {detail}")
    else:
        lines.append("过自信警报：0.9-1.0 桶无判错例")
    errors = [row for row in rows if "error" in row]
    if errors:
        lines.append(f"后端故障 {len(errors)} 例（fail-open 记 allow 0.0）："
                     + ", ".join(row["id"] for row in errors))
    return "\n".join(lines)


def load_labeled_set(path: str | Path | None = None) -> list[dict]:
    """读标注集并验收契约：总量 ≥48、每 gate ≥12、字段齐全、id 唯一。"""
    fixture = Path(path) if path else FIXTURE
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) < MIN_TOTAL:
        raise ValueError(f"标注集应 ≥{MIN_TOTAL} 例，实得 {len(cases)}")
    seen: set[str] = set()
    for case in cases:
        missing = {"id", "gate", "context", "expect_deny"} - set(case)
        if missing:
            raise ValueError(f"标注例缺字段 {missing}：{case}")
        if case["gate"] not in GATES:
            raise ValueError(f"未知 gate：{case['gate']}（{case['id']}）")
        if not isinstance(case["expect_deny"], bool):
            raise ValueError(f"expect_deny 应为 bool：{case['id']}")
        if case["id"] in seen:
            raise ValueError(f"id 重复：{case['id']}")
        seen.add(case["id"])
    for gate in GATES:
        n = sum(1 for case in cases if case["gate"] == gate)
        if n < MIN_PER_GATE:
            raise ValueError(f"gate {gate} 仅 {n} 例（应 ≥{MIN_PER_GATE}）")
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="判断层校准台：标注集 → 混淆矩阵 + 置信分桶 + 过自信警报")
    parser.add_argument("--backend", choices=("rule", "local"), default="rule",
                        help="rule=关键词兜底（默认）；local=OpenAI 兼容端点"
                             "（读 LAOS_JEV_ENDPOINT）")
    parser.add_argument("--limit", type=int, default=None,
                        help="只跑前 N 例（冒烟）")
    args = parser.parse_args(argv)

    backend = RuleBackend() if args.backend == "rule" else LocalBackend()
    cases = load_labeled_set()
    if args.limit is not None:
        cases = cases[:max(int(args.limit), 0)]
    rows = run_cases(cases, backend)
    # 全例后端故障 = 本轮没有一条真实判断（fail-open 的 allow/0.0 是占位
    # 不是数据），报告不可读作校准结论——首行打醒目警告并退出码 1；部分
    # 故障照常退出 0（报告末行已点名"后端故障 N 例"）
    all_errored = bool(rows) and all("error" in row for row in rows)
    if all_errored:
        print(f"⚠️ 全部 {len(rows)} 例后端故障——fail-open 记的 allow/0.0 "
              f"不构成校准数据，本次报告无效（检查端点/key/网络后重跑），退出码 1")
    print(render_report(rows))
    print(f"\nbackend={backend.name}  cases={len(cases)}  "
          f"fixture={FIXTURE.relative_to(REPO)}")
    return 1 if all_errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
