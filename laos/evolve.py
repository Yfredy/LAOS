# laos/evolve.py
"""evolve —— 受治理的进化优化作业面（RSI 驱动的核心侧薄接口）。

分工（docs/research/2026-10-09-rsi-landscape.md §8）：
    循环外   本模块常驻 laos 核心：路径闸 + 参数校验 + 执行器装配面
    循环内   OpenEvolve 只活在 drivers/drv_evolve.py 起的 venv 子进程里

零依赖红线：本文件纯 stdlib，不 import openevolve、不起子进程；执行器由
驱动侧 import 即登记（laos/decide.py register_backend 同款装配面哲学，
drv_clef 先例）。gate 默认只放行 var/rsi/jobs/ ——进化产物不得自改写
laos 本体（自改写防线：禁区永不可经 env 放行）。
"""
from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

__all__ = ["DEFAULT_MAX_ITERATIONS", "DEFAULT_ROOTS", "DEFAULT_TIMEOUT_S",
           "FORBIDDEN_ROOTS", "EvolveGate", "EvolveJob", "EvolveResult",
           "register_executor", "run_job", "status"]

DEFAULT_ROOTS = ("var/rsi/jobs",)
FORBIDDEN_ROOTS = ("laos/", "drivers/", "tests/", "bin/", "clients/",
                   "docs/", "scripts/", "zones/", "corpus/", "demos/")
DEFAULT_MAX_ITERATIONS = 500
DEFAULT_TIMEOUT_S = 1800.0

_executors: dict[str, Callable[["EvolveJob"], "EvolveResult"]] = {}


@dataclass
class EvolveJob:
    target: str                 # 初始程序（须在允许根内）
    evaluator: str              # 评估器（同上）
    iterations: int             # 1..DEFAULT_MAX_ITERATIONS
    workdir: str | None = None  # None=驱动侧分配（var/rsi/jobs/job-<ts>-<rand>）
    timeout_s: float = DEFAULT_TIMEOUT_S


@dataclass
class EvolveResult:
    best_score: float
    best_program_path: str
    best_program_sha256: str
    iterations_completed: int
    elapsed_s: float
    artifacts_dir: str

    @classmethod
    def from_payload(cls, payload: dict) -> "EvolveResult":
        """单行 JSON → Result（类型校验 fail-loud；sha256 恰 64 hex）。"""
        try:
            r = cls(best_score=float(payload["best_score"]),
                    best_program_path=str(payload["best_program_path"]),
                    best_program_sha256=str(payload["best_program_sha256"]),
                    iterations_completed=int(payload["iterations_completed"]),
                    elapsed_s=float(payload["elapsed_s"]),
                    artifacts_dir=str(payload["artifacts_dir"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"EINVAL: evolve 结果 payload 契约破裂：{exc}") from exc
        if len(r.best_program_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in r.best_program_sha256):
            raise ValueError("EINVAL: best_program_sha256 须为 64 位 hex")
        if r.iterations_completed < 0 or r.elapsed_s < 0:
            raise ValueError("EINVAL: iterations/elapsed 不得为负")
        return r


class EvolveGate:
    """路径与预算闸：target/evaluator 归一化后必须落在允许根内
    （分隔符收边，kernel task_scope 同款），禁区永不可放行。"""

    def __init__(self, roots: tuple[str, ...] | None = None):
        self.roots = roots

    def _roots(self) -> tuple[str, ...]:
        if self.roots is not None:
            return self.roots
        raw = os.environ.get("LAOS_EVOLVE_ROOTS")
        return tuple(s for s in raw.split(",") if s) if raw else DEFAULT_ROOTS

    def check(self, job: EvolveJob) -> None:
        for label, raw in (("target", job.target), ("evaluator", job.evaluator)):
            norm = posixpath.normpath(Path(raw).as_posix())
            if norm.startswith(".."):
                raise ValueError(f"EPERM: evolve {label} 逃逸允许根：{raw}")
            for forbidden in FORBIDDEN_ROOTS:
                if norm == forbidden.rstrip("/") or norm.startswith(forbidden):
                    raise ValueError(
                        f"EPERM: evolve {label} 触碰禁区 {forbidden}（自改写防线）：{raw}")
            if not any(norm == r or norm.startswith(r.rstrip("/") + "/")
                       for r in self._roots()):
                raise ValueError(
                    f"EPERM: evolve {label} 不在允许根 {self._roots()} 内：{raw}")
        if not 1 <= job.iterations <= DEFAULT_MAX_ITERATIONS:
            raise ValueError(
                f"EINVAL: iterations 须在 1..{DEFAULT_MAX_ITERATIONS}，"
                f"实测 {job.iterations}")


def register_executor(fn: Callable[[EvolveJob], EvolveResult]) -> None:
    """驱动侧装配登记（import drivers.drv_evolve 即生效）。"""
    _executors["openevolve"] = fn


def run_job(job: EvolveJob) -> EvolveResult:
    """闸 → 执行器 → 结果（ENODEV/EPERM/EINVAL 原样冒泡，绝不静默兜底）。"""
    EvolveGate().check(job)
    fn = _executors.get("openevolve")
    if fn is None:
        raise RuntimeError(
            "ENODEV: evolve 驱动未装配（需 import drivers.drv_evolve；"
            "核心保持零依赖，装配面 fail-loud）")
    result = fn(job)
    if not isinstance(result, EvolveResult):
        raise TypeError(f"EINVAL: 执行器返回 {type(result)!r}，须 EvolveResult")
    return result


def status() -> str:
    """纯本地状态一行（不起子进程不触网，drv_clef.status 同款）。"""
    return (f"executor_registered={'openevolve' in _executors} "
            f"roots={EvolveGate()._roots()} "
            f"max_iterations={DEFAULT_MAX_ITERATIONS} "
            f"timeout_s={DEFAULT_TIMEOUT_S}")
