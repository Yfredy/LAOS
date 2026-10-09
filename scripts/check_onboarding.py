#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laos 新人交接门禁：校验 docs/ONBOARDING.md 的事实是否与仓库现状一致。

用法:
  python scripts/check_onboarding.py --collect   # 打印事实集 JSON
  python scripts/check_onboarding.py             # 跑门禁（漂移→退出码 1）

纪律（参照 AGENTS.md）: 只用 stdlib；数字必须是实跑值。
注意：门禁内含主库全量测试（collect 会实跑 unittest discover，
约 1–7 分钟，负载敏感）——这是设计而非事故：文档里的数字与门禁共用
同一数据源，改了代码没改文档，门禁当场红。
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONBOARDING = ROOT / "docs" / "ONBOARDING.md"
HY4 = ROOT.parent / "AlwaysOnRec-HY4"


def collect() -> dict:
    """采集事实集。键名为契约，勿改。"""
    facts = {}
    facts["laos_modules"] = len(list((ROOT / "laos").glob("*.py")))
    facts["bin_entries"] = len(list((ROOT / "bin").glob("*.py")))
    facts["test_files"] = len(list((ROOT / "tests").glob("test_*.py")))
    facts["plan_files"] = len(list((ROOT / "docs" / "superpowers" / "plans").glob("*.md")))
    facts["research_docs"] = len(list((ROOT / "docs" / "research").rglob("*.md")))
    facts["hy4_present"] = HY4.is_dir()
    # 主库测试数：实跑，失败则记 None（门禁要求非 None）
    try:
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT, capture_output=True, text=True, timeout=1800)
        m = re.search(r"Ran (\d+) tests", r.stderr + r.stdout)
        facts["laos_tests"] = int(m.group(1)) if m else None
    except Exception:
        facts["laos_tests"] = None
    return facts


def check(facts: dict) -> list[str]:
    """返回问题清单，空列表=全绿。规则刻意保守：只抓可机检事实。"""
    problems = []
    if not ONBOARDING.is_file():
        return [f"缺交接文档: {ONBOARDING}"]
    text = ONBOARDING.read_text(encoding="utf-8")

    # 规则1: 事实基线表的每个数字必须与实跑一致
    for key, label in (("laos_tests", "主库测试数"),
                       ("laos_modules", "主库模块数"),
                       ("test_files", "测试文件数")):
        v = facts.get(key)
        if v is None:
            problems.append(f"{label}: 采集失败（实跑未取到数字），禁止写进文档")
            continue
        # 文档里形如「<label> | N」的行必须含该实跑值
        pat = re.compile(rf"\|\s*{re.escape(label)}\s*\|[^|]*\b{v}\b")
        if not pat.search(text):
            problems.append(f"{label} 漂移: 文档未含实跑值 {v}（该跑 `{key}` 核对）")

    # 规则2: 不得出现未采集的占位符
    for bad in ("TBD", "待补", "TODO", "Fill in"):
        if bad in text:
            problems.append(f"文档含占位符『{bad}』")

    # 规则3: 必须链接 AGENTS.md（避免纪律被复制成第二份而漂移）
    if "AGENTS.md" not in text:
        problems.append("文档未链接 AGENTS.md（纪律须引用不得复制）")

    # 规则4: 关键命令必须用仓库根相对路径，禁止写死绝对路径（换机即失效）
    for m in re.finditer(r"python\s+(?:scripts|bin|tests)/[\w./-]+", text):
        if "C:/" in text[max(0, m.start()-40):m.start()+5]:
            problems.append("命令含绝对路径，换机失效，须用仓库根相对路径")
            break
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="只打印事实集 JSON")
    args = ap.parse_args()
    facts = collect()
    if args.collect:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return 0
    problems = check(facts)
    if problems:
        print(f"交接门禁 FAIL（{len(problems)} 条）:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"交接门禁 OK（实测:测试 {facts['laos_tests']} 项 / 模块 {facts['laos_modules']} 个）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
