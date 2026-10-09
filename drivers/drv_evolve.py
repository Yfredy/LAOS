#!/usr/bin/env python3
"""drv_evolve —— OpenEvolve 进化优化后端（重依赖隔离，drv_clef 同款契约）。

    核心挂点     laos/evolve.py register_executor(...) —— 本模块 import 即
                 登记；EvolveDriver(job).run() -> EvolveResult
    子进程形态   {LAOS_EVOLVE_PYTHON 默认 var/rsi/openevolve/venv/Scripts/
                 python.exe} drivers/openevolve_job.py --job <json>（作业
                 内部再起官方 CLI，两层都是 venv python，conda 未动）
    输出契约     stdout 单行 JSON EvolveResult payload（前缀噪声容错：
                 取最后一行以 "{" 开头的行，drv_clef/drv_ear 先例）

env 契约（LAOS_EVOLVE_*，调用时读取，全部可覆盖）：
    LAOS_EVOLVE_PYTHON  venv 解释器路径
    LAOS_EVOLVE_CMD     自定义命令模板整体替换（{python}/{job}）
    LAOS_EVOLVE_TIMEOUT 子进程超时秒（默认 1800.0）
    LAOS_EVOLVE_SRC     OpenEvolve 源码目录（传入 job 的 src_dir）
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.evolve import (EvolveJob, EvolveResult, register_executor,  # noqa: E402
                          status as core_status)

DEFAULT_PYTHON = "var/rsi/openevolve/venv/Scripts/python.exe"
DEFAULT_SRC = "var/rsi/openevolve/src"
DEFAULT_TIMEOUT = 1800.0


class EvolveDriver:
    """OpenEvolve 后端驱动：构造命令、跑 venv 子进程、解析单行 JSON。"""

    name = "openevolve"
    last_best_score: float | None = None

    def _timeout(self) -> float:
        raw = os.environ.get("LAOS_EVOLVE_TIMEOUT")
        if raw is None:
            return DEFAULT_TIMEOUT
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"EINVAL: LAOS_EVOLVE_TIMEOUT 必须为正数，实测 {raw!r}")
        return value

    def build_command(self, job: EvolveJob) -> list[str]:
        payload = {"target": job.target, "evaluator": job.evaluator,
                   "iterations": job.iterations, "workdir": job.workdir,
                   "timeout_s": min(job.timeout_s, self._timeout()),
                   "src_dir": os.environ.get("LAOS_EVOLVE_SRC", DEFAULT_SRC)}
        job_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        template = os.environ.get("LAOS_EVOLVE_CMD")
        if template:
            return [tok.format(python=os.environ.get(
                                     "LAOS_EVOLVE_PYTHON", DEFAULT_PYTHON),
                               job=job_json)
                    for tok in template.split()]
        return [os.environ.get("LAOS_EVOLVE_PYTHON", DEFAULT_PYTHON),
                str((Path(__file__).parent / "openevolve_job.py")
                    .resolve().as_posix()),
                "--job", job_json]

    def run(self, job: EvolveJob) -> EvolveResult:
        cmd = self.build_command(job)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=self._timeout())
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"ETIMEDOUT: evolve 作业超时 {self._timeout()}s："
                f"target={job.target}（调 LAOS_EVOLVE_TIMEOUT）") from exc
        if r.returncode != 0:
            raise RuntimeError(
                f"EIO: evolve rc={r.returncode}：{(r.stderr or '').strip()[-600:]}")
        line = next((ln for ln in reversed(r.stdout.splitlines())
                     if ln.strip().startswith("{")), None)
        if line is None:
            raise RuntimeError(
                f"EIO: evolve 输出无 JSON 行：stdout={r.stdout.strip()[:200]!r}")
        result = EvolveResult.from_payload(json.loads(line))
        EvolveDriver.last_best_score = result.best_score
        return result

    def __call__(self, job: EvolveJob) -> EvolveResult:
        return self.run(job)


def _openevolve_executor(job: EvolveJob) -> EvolveResult:
    """register_executor 登记的适配器；workdir 未指定时分配带时间戳目录。"""
    if job.workdir is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        job = EvolveJob(job.target, job.evaluator, job.iterations,
                        workdir=f"var/rsi/jobs/job-{stamp}-"
                                f"{os.urandom(3).hex()}",
                        timeout_s=job.timeout_s)
    return EvolveDriver().run(job)


# import 即登记（核心零依赖：不 import 本驱动时 run_job → ENODEV）
register_executor(_openevolve_executor)


def status() -> str:
    return (f"backend=openevolve registered=True "
            f"{core_status()} "
            f"venv={Path(DEFAULT_PYTHON).exists()} "
            f"src={Path(DEFAULT_SRC).exists()} "
            f"last_best_score={EvolveDriver.last_best_score}")


if __name__ == "__main__":
    print(status())
