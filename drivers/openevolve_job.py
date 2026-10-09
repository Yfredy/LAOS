#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openevolve_job —— venv 内进化作业执行器（drv_evolve 以 venv python 启动）。

用法：venv-python drivers/openevolve_job.py --job '<EvolveJob JSON>'
输出：stdout 单行 JSON（EvolveResult payload）；失败 stderr 原文 + rc=3。

实现走**官方 CLI 子进程**（README quickstart 原样），不直接调库——
库 API 签名不进公开契约，CLI 才是文档化稳定面：
    {sys.executable} {src}/openevolve-run.py {target} {evaluator}
        --iterations {n}
checkpoint 布局按 var/rsi/openevolve/OBSERVATIONS.md §首跑 实查口径解析
（rglob 兜底 + 找不到即 ENOENT fail-loud，不猜布局）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
    sys.exit(3)


def _find_best(workdir: Path) -> Path:
    """best program 落盘定位：优先官方口径 checkpoints/best/best_program.py，
    rglob 兜底；双 miss 即 ENOENT（布局漂移的证据就是这条 stderr）。"""
    canonical = workdir / "checkpoints" / "best" / "best_program.py"
    if canonical.is_file():
        return canonical
    hits = sorted(workdir.rglob("best_program.py"))
    if hits:
        return hits[-1]
    _fail(f"ENOENT: checkpoints 下无 best_program.py（布局漂移？实查 "
          f"{workdir / 'checkpoints'}）：{list(workdir.rglob('*'))[:20]}")


def _best_score(workdir: Path, cli_stdout: str) -> float:
    """best score 两路：checkpoints 侧 JSON 数值字段 → CLI stdout 正则；
    双 miss fail-loud（宁可 ENOENT 不编 0.0——评测数字一律实测）。"""
    for jf in sorted((workdir / "checkpoints").rglob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for key in ("best_score", "combined_score", "score"):
            v = data.get(key) if isinstance(data, dict) else None
            if isinstance(v, (int, float)):
                return float(v)
    m = re.findall(r"best score[:=]\s*([0-9]*\.?[0-9]+)",
                   cli_stdout, re.IGNORECASE)
    if m:
        return float(m[-1])
    _fail("ENOENT: 两路均未解析出 best_score（checkpoint JSON 与 CLI stdout）")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenEvolve job executor")
    parser.add_argument("--job", required=True, help="EvolveJob JSON")
    args = parser.parse_args()
    job = json.loads(args.job)
    t0 = time.perf_counter()
    workdir = Path(job.get("workdir") or "var/rsi/jobs/run").resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    src = Path(job.get("src_dir") or "var/rsi/openevolve/src")
    cli = [sys.executable, str(src / "openevolve-run.py"),
           str(job["target"]), str(job["evaluator"]),
           "--iterations", str(job["iterations"])]
    try:
        r = subprocess.run(cli, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           cwd=str(workdir), timeout=float(job["timeout_s"]))
    except subprocess.TimeoutExpired:
        _fail(f"ETIMEDOUT: openevolve-run 超时 {job['timeout_s']}s")
    if r.returncode != 0:
        _fail(f"EIO: openevolve-run rc={r.returncode}："
              f"{(r.stderr or '')[-600:]}")
    best = _find_best(workdir)
    score = _best_score(workdir, r.stdout)
    iters = None
    m = re.findall(r"iteration\s+(\d+)", r.stdout, re.IGNORECASE)
    if m:
        iters = int(m[-1])
    print(json.dumps({
        "best_score": score,
        "best_program_path": best.as_posix(),
        "best_program_sha256": hashlib.sha256(
            best.read_bytes()).hexdigest(),
        "iterations_completed": iters if iters is not None
        else int(job["iterations"]),
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "artifacts_dir": workdir.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
