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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="只打印事实集 JSON")
    args = ap.parse_args()
    facts = collect()
    if args.collect:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return 0
    # Task 2 起在此接入门禁规则；当前仅回显，保证 --collect 可用
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
