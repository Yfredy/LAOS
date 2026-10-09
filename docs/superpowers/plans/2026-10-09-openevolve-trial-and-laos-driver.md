# OpenEvolve 试跑 + laos 受治理进化驱动 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 var/ 里试跑 OpenEvolve（AlphaEvolve 开源实现），然后以 drv_clef 同款契约把它接进 laos：核心侧纯 stdlib 作业面 `laos/evolve.py` + 内建 syscall `evolve.run`（走完整闸门链）+ 重依赖子进程驱动 `drivers/drv_evolve.py`。

**Architecture:** 三层分离——进化循环内（OpenEvolve 只活在 var/ 的独立 venv 子进程里）、进化循环外（gate/预算/审计常驻 laos 核心，这正是 RSI 调研 §8 的"裁判席在循环外"落地）。内核挂点用内建 syscall 表（`_builtin_specs`/`_builtin_impls`，msg.*/mem.* 先例），白得 caps→validate→EDQUOT→sentinel→audit 全链；驱动侧 import 即登记执行器（decide/judge 装配面先例）。

**Tech Stack:** Python 3.10+（venv 内 openevolve）；laos 核心纯 stdlib（json/posixpath/dataclasses/pathlib/os/time/hashlib）；测试 unittest + mock（全离线，不起子进程不触网）。

**Spec:** `docs/research/2026-10-09-rsi-landscape.md` §7（实践入口排序：OpenEvolve 为唯一可试跑项）与 §8（裁决表 #1/#2/#5：进化循环外治理 + 自改写防线 + 零依赖红线）。

## Global Constraints

- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`；**绝不** `pip install` 进 conda 本体——OpenEvolve 装进 `var/rsi/openevolve/venv`（`python -m venv` 创建，装进 venv 不算碰 conda）。
- **零依赖红线**：`laos/evolve.py` 纯 stdlib，不 import openevolve、不起子进程；重依赖只进 `drivers/` 与 venv 子进程。
- **目录纪律**：不新建顶层目录（只用 laos/ drivers/ tests/ var/ docs/）；一切试跑产物进 `var/`（整目录 gitignored）。
- **测试口径**：新增测试全离线（mock subprocess.run，先例 tests/test_drv_clef.py）；真跑只在 Task 7 手动门控步骤，结果落 var/。
- **fail-loud errno 风格**：EPERM（越允许根）/ EINVAL（参数坏）/ ENODEV（驱动未装配）/ ETIMEDOUT / EIO（rc≠0 或坏 JSON）/ ENOENT（checkpoint 缺失）——不静默兜底（drv_clef T1 哲学）。
- **审计红线**：`evolve.run` 走内建分支自动落 `event:"syscall"` 审计；另加 `event:"evolve"` 一行（best_score/sha256 可观测）。
- **Windows**：venv 解释器是 `Scripts/python.exe`；所有可执行脚本包 `if __name__ == "__main__":`（OpenEvolve README 明示 Windows 需要）。
- **自改写防线**：gate 默认只放行 `var/rsi/jobs/` 前缀；`laos/ drivers/ tests/ bin/ clients/ docs/ scripts/ zones/` 永不放行（env `LAOS_EVOLVE_ROOTS` 可扩不可缩禁区）。

---

### Task 1: venv 隔离安装 OpenEvolve（var/，不碰 conda）

**Files:**
- Create: `var/rsi/openevolve/`（gitignored，venv + 源码克隆）
- Create: `var/rsi/openevolve/OBSERVATIONS.md`（试跑观察记录，Task 3 续写）

**Interfaces:**
- Produces: `var/rsi/openevolve/venv/Scripts/python.exe`（后续任务子进程解释器）；`var/rsi/openevolve/src/`（OpenEvolve 源码 + examples/ + openevolve-run.py CLI）。

- [ ] **Step 1: 建目录与 venv**

```bash
mkdir -p var/rsi/openevolve
C:/Users/yaoyue/miniconda3/python.exe -m venv var/rsi/openevolve/venv
var/rsi/openevolve/venv/Scripts/python.exe --version
```

Expected: `Python 3.1x.x`（≥3.10）。

- [ ] **Step 2: 克隆源码并装进 venv**

```bash
git clone --depth 1 https://github.com/algorithmicsuperintelligence/openevolve var/rsi/openevolve/src
var/rsi/openevolve/venv/Scripts/python.exe -m pip install var/rsi/openevolve/src
```

Expected: pip 输出 `Successfully installed openevolve-…` 及其依赖（装在 venv，conda 未动）。

- [ ] **Step 3: 冒烟验证 import 与 CLI 存在**

```bash
var/rsi/openevolve/venv/Scripts/python.exe -c "import openevolve; print(openevolve.__file__)"
ls var/rsi/openevolve/src/openevolve-run.py var/rsi/openevolve/src/examples/function_minimization/
```

Expected: 包路径指向 venv site-packages；CLI 脚本与示例目录都在。任一失败 → 停，把报错原文记入 OBSERVATIONS.md 收档（clef BLOCKED 先例）。

- [ ] **Step 4: 初始化 OBSERVATIONS.md**

```markdown
# OpenEvolve 试跑观察（var/rsi/openevolve/）

- 日期：2026-10-09；venv Python：<Step 1 输出>；openevolve 版本：<pip 输出>
- 来源：algorithmicsuperintelligence/openevolve（Apache-2.0，7.5k★，实查见 docs/research/2026-10-09-rsi-landscape.md §7）
```

（无 commit——var/ 不进库。）

---

### Task 2: LLM 后端探测与配置

**Files:**
- Modify: `var/rsi/openevolve/OBSERVATIONS.md`

**Interfaces:**
- Produces: 可用的 LLM 后端结论（env key 名或 ollama 端点），写入 OBSERVATIONS.md §后端；Task 3/7 依赖它。

- [ ] **Step 1: 探测环境变量与本地 ollama**

```bash
env | grep -iE "OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY|BIGMODEL|ZAI|GLM" | sed 's/=.*/=<set>/'
curl -s -m 3 http://localhost:11434/api/tags | head -c 300
```

Expected: 命中至少一个 key，或 ollama 返回 `{"models":[…]}`；全空 → OBSERVATIONS.md 记 `BLOCKED: 无可用 LLM 后端`，Task 3/7 改为收档（clef 彩票脚本先例：证据原文进记录）。

- [ ] **Step 2: 确认 OpenEvolve 的自定义端点配置面**

```bash
grep -rn "api_base\|base_url" var/rsi/openevolve/src/openevolve/config/ 2>/dev/null | head -20
ls var/rsi/openevolve/src/openevolve/config/ 2>/dev/null || grep -rn "class.*Config" var/rsi/openevolve/src/openevolve/*.py | head -10
```

Expected: 找到 llm 配置字段名（README 称支持任意 OpenAI 兼容端点）。把字段名原文记入 OBSERVATIONS.md §后端——Task 6 的 openevolve_job.py 只引用这里抄下的字段名，不凭记忆猜。

---

### Task 3: 首跑 function_minimization + 记录进化循环形态

**Files:**
- Modify: `var/rsi/openevolve/OBSERVATIONS.md`

**Interfaces:**
- Produces: OBSERVATIONS.md §首跑（best score、迭代日志样例、checkpoint 落盘布局**逐文件列出**）——Task 6 的 `_find_best`/`_best_score` 直接按此布局写，不猜。

- [ ] **Step 1: 跑官方 quickstart（20 迭代省钱）**

```bash
cd var/rsi/openevolve/src
../venv/Scripts/python.exe openevolve-run.py examples/function_minimization/initial_program.py examples/function_minimization/evaluator.py --iterations 20 2>&1 | tail -40
```

Expected: 迭代日志 + 终态 best score。Windows 下若 multiprocessing 报错，重跑前在 `initial_program.py` 检查 `if __name__ == "__main__":` 守卫（README 明示）。

- [ ] **Step 2: 记录 checkpoint 布局与结果**

```bash
find . -path ./venv -prune -o -name "*.py" -newer openevolve-run.py -print | head
find checkpoints -maxdepth 3 -type f 2>/dev/null | head -20
cat checkpoints/best/best_program.py 2>/dev/null | head -20
```

Expected: 确认 best program 落盘路径（README/HF 博客口径是 `checkpoints/best/best_program.py`，以实查为准）。把：best score 数值、日志中 score 行的原样一行、checkpoint 文件树——三样抄进 OBSERVATIONS.md §首跑。

（无 commit。）

---

### Task 4: `laos/evolve.py` —— 核心侧纯 stdlib 作业面（TDD）

**Files:**
- Create: `laos/evolve.py`
- Test: `tests/test_evolve.py`

**Interfaces:**
- Produces: `EvolveJob(target:str, evaluator:str, iterations:int, workdir:str|None=None, timeout_s:float=1800.0)`；`EvolveResult(best_score:float, best_program_path:str, best_program_sha256:str, iterations_completed:int, elapsed_s:float, artifacts_dir:str)` + `from_payload(dict)`（类型校验 fail-loud）；`EvolveGate.check(job)`（抛 ValueError，消息带 errno 前缀）；`register_executor(fn)` / `run_job(job) -> EvolveResult`（未装配抛 RuntimeError ENODEV）。Task 5 的 `_impl_evolve_run` 与 Task 6 的驱动都消费这组签名。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_evolve.py
"""evolve —— 受治理进化作业面离线测试：gate 路径政策 / job-result 契约 /
ENODEV 装配面 / payload round-trip。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v

来源：docs/research/2026-10-09-rsi-landscape.md §8 裁决 #2（自改写防线）；
装配面哲学同 laos/decide.py（drv_clef 先例）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.evolve import (EvolveGate, EvolveJob, EvolveResult,  # noqa: E402
                         register_executor, run_job)


def _job(**kw):
    base = dict(target="var/rsi/jobs/demo/initial_program.py",
                evaluator="var/rsi/jobs/demo/evaluator.py", iterations=10)
    base.update(kw)
    return EvolveJob(**base)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.gate = EvolveGate(roots=("var/rsi/jobs",))

    def test_inside_root_passes(self):
        self.gate.check(_job())  # 不抛即过

    def test_outside_root_is_eperm(self):
        with self.assertRaises(ValueError) as cm:
            self.gate.check(_job(target="laos/kernel.py"))
        self.assertIn("EPERM", str(cm.exception))

    def test_dotdot_escape_is_eperm(self):
        with self.assertRaises(ValueError):
            self.gate.check(_job(target="var/rsi/jobs/../../laos/kernel.py"))

    def test_separator_edge_no_false_prefix(self):
        with self.assertRaises(ValueError):  # jobs2 不得借道 jobs 前缀
            self.gate.check(_job(target="var/rsi/jobs2/x.py"))

    def test_iterations_bounds_are_einval(self):
        for bad in (0, -1, 501):
            with self.assertRaises(ValueError) as cm:
                self.gate.check(_job(iterations=bad))
            self.assertIn("EINVAL", str(cm.exception))


class TestRunJob(unittest.TestCase):
    def tearDown(self):
        # 清掉本类注册的执行器，避免污染其他测试
        import laos.evolve as ev
        ev._executors.clear()

    def test_enODEV_without_driver(self):
        with self.assertRaises(RuntimeError) as cm:
            run_job(_job())
        self.assertIn("ENODEV", str(cm.exception))

    def test_registered_executor_roundtrip(self):
        seen = {}

        def fake(job):
            seen["job"] = job
            return EvolveResult(0.87, "var/rsi/jobs/demo/out.py",
                                "ab" * 32, 10, 1.5, "var/rsi/jobs/demo")

        register_executor(fake)
        result = run_job(_job())
        self.assertEqual(result.best_score, 0.87)
        self.assertEqual(seen["job"].iterations, 10)


class TestPayload(unittest.TestCase):
    def _payload(self):
        return {"best_score": 0.5, "best_program_path": "var/rsi/jobs/d/o.py",
                "best_program_sha256": "cd" * 32, "iterations_completed": 9,
                "elapsed_s": 2.0, "artifacts_dir": "var/rsi/jobs/d"}

    def test_roundtrip(self):
        r = EvolveResult.from_payload(self._payload())
        self.assertEqual(r.best_program_sha256, "cd" * 32)

    def test_bad_types_fail_loud(self):
        bad = self._payload()
        bad["best_score"] = "high"
        with self.assertRaises(ValueError):
            EvolveResult.from_payload(bad)
        bad2 = self._payload()
        bad2["iterations_completed"] = -1
        with self.assertRaises(ValueError):
            EvolveResult.from_payload(bad2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v`
Expected: FAIL/ERROR——`ModuleNotFoundError: No module named 'laos.evolve'`。

- [ ] **Step 3: 最小实现**

```python
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
import time
from dataclasses import asdict, dataclass
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v`
Expected: 全 PASS。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 既有全绿 + 新增 12 例。

- [ ] **Step 6: Commit**

```bash
git add laos/evolve.py tests/test_evolve.py
git commit -m "feat: laos/evolve.py 受治理进化作业面（gate+ENODEV 装配面，RSI 裁决#2 自改写防线）"
```

---

### Task 5: 内建 syscall `evolve.run`（TDD）

**Files:**
- Modify: `laos/kernel.py`（`_builtin_specs`/`_builtin_impls` 各加一条，kernel.py:302 与 kernel.py:366 两处字典）
- Test: `tests/test_evolve.py`（追加 TestEvolveSyscall 类）

**Interfaces:**
- Consumes: Task 4 的 `EvolveJob/run_job`（签名如上）。
- Produces: `evolve.run` syscall（args: target/evaluator/iterations），走完整闸门链；成功返回 ok_text(JSON payload)，失败 CallResult.fail(errno 消息)。Task 7 e2e 消费。

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_evolve.py 追加（import 区补 asyncio / from laos.kernel import …）
import asyncio  # noqa: E402

from laos.kernel import AgentKernel, CapabilitySet, PCB  # noqa: E402


class TestEvolveSyscall(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.k = AgentKernel(Path(self.td.name) / "var", audit_mode="w",
                             confirm=lambda op: False)

    def tearDown(self):
        self.k.shutdown()
        self.td.cleanup()
        import laos.evolve as ev
        ev._executors.clear()

    def _pcb(self, caps):
        pcb = PCB(pid=1, name="evo", caps=CapabilitySet(caps), budget=None)
        self.k.procs[1] = pcb
        return pcb

    def _args(self):
        return {"target": "var/rsi/jobs/d/initial_program.py",
                "evaluator": "var/rsi/jobs/d/evaluator.py", "iterations": 5}

    def test_eperm_without_cap(self):
        self._pcb([])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)

    def test_enODEV_without_driver(self):
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertFalse(res.ok)
        self.assertIn("ENODEV", res.error)

    def test_ok_with_fake_executor_and_audit(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        import json as _json
        payload = _json.loads(res.text)
        self.assertEqual(payload["best_score"], 0.9)
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertTrue(events and events[-1]["sha256"] == "ab" * 32)

    def test_gate_violation_fails_not_crashes(self):
        self._pcb(["evolve.*"])
        bad = self._args()
        bad["target"] = "laos/kernel.py"
        res = asyncio.run(self.k.syscall(1, "evolve.run", bad))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve.TestEvolveSyscall -v`
Expected: FAIL——`ENOSYS: no such syscall`（四例全是）。

- [ ] **Step 3: 内核登记（两处字典 + impl 方法）**

`_builtin_specs`（kernel.py:302 起，mem.outcome 条目之后）追加：

```python
            "evolve.run": ToolSpec(
                "evolve.run",
                "受治理的进化优化作业（OpenEvolve 后端，重依赖 venv 子进程隔离；"
                "target/evaluator 须在 var/rsi/jobs/ 允许根内）",
                {"type": "object",
                 "properties": {"target": {"type": "string"},
                                "evaluator": {"type": "string"},
                                "iterations": {"type": "integer",
                                               "minimum": 1}},
                 "required": ["target", "evaluator", "iterations"]},
                reversible=True, risk="medium"),
```

`_builtin_impls`（kernel.py:366 起）追加 `"evolve.run": self._impl_evolve_run,`，并在 `_impl_mem_outcome`（kernel.py:915）后新增方法（文件已 import asdict/json/time，零新 import）：

```python
    def _impl_evolve_run(self, pcb: PCB, args: dict) -> "CallResult":
        from .mcp import CallResult

        from .evolve import EvolveJob, run_job
        try:
            job = EvolveJob(target=str(args["target"]),
                            evaluator=str(args["evaluator"]),
                            iterations=int(args["iterations"]))
            result = run_job(job)
        except (ValueError, RuntimeError, TypeError) as exc:
            # gate 的 EPERM/EINVAL、装配面 ENODEV：fail-loud 冒泡为 CallResult
            return CallResult.fail(str(exc))
        self.audit.write({"t": time.time(), "event": "evolve", "op": "run",
                          "pid": pcb.pid, "target": job.target,
                          "iterations": result.iterations_completed,
                          "best_score": result.best_score,
                          "sha256": result.best_program_sha256})
        return CallResult.ok_text(json.dumps(asdict(result),
                                             ensure_ascii=False, sort_keys=True))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v`
Expected: 全 PASS（含 Task 4 的 12 例）。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add laos/kernel.py tests/test_evolve.py
git commit -m "feat: evolve.run 内建 syscall（caps→validate→sentinel→audit 全链，event:evolve 审计）"
```

---

### Task 6: `drivers/drv_evolve.py` + `drivers/openevolve_job.py`（TDD，离线）

**Files:**
- Create: `drivers/drv_evolve.py`（核心侧适配器，drv_clef 同款契约）
- Create: `drivers/openevolve_job.py`（venv 内作业执行器，由 drv_evolve 以 venv python 启动）
- Test: `tests/test_drv_evolve.py`

**Interfaces:**
- Consumes: Task 4 的 `EvolveJob/EvolveResult/register_executor`；Task 3 OBSERVATIONS.md §首跑 的 checkpoint 布局（`_find_best`/`_best_score` 按实查布局实现）与 §后端 的 llm 配置字段名。
- Produces: `EvolveDriver.build_command(job) -> list[str]`、`.run(job) -> EvolveResult`、模块级 `status()`；import 即 `register_executor`。env 契约 `LAOS_EVOLVE_PYTHON`（venv 解释器，默认 `var/rsi/openevolve/venv/Scripts/python.exe`）、`LAOS_EVOLVE_CMD`（模板整体替换，`{python}`/`{job}` 占位）、`LAOS_EVOLVE_TIMEOUT`（默认 1800.0）、`LAOS_EVOLVE_SRC`（默认 `var/rsi/openevolve/src`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_drv_evolve.py
"""drv_evolve —— OpenEvolve 驱动离线测试：命令构造 / env 覆盖 / 单行 JSON
解析（前缀噪声容错）/ rc≠0 与超时 fail-loud / import 即登记执行器。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve -v

全部 mock subprocess（不触网不起 venv）。真跑见 var/rsi/jobs/e2e-smoke.json。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from drivers import drv_evolve  # noqa: E402
from laos.evolve import EvolveJob, EvolveResult  # noqa: E402


def _fake_run(stdout: str = "", rc: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(args=["evolve"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("LAOS_EVOLVE")}
    env.update(extra)
    return env


def _job():
    return EvolveJob(target="var/rsi/jobs/d/initial_program.py",
                     evaluator="var/rsi/jobs/d/evaluator.py",
                     iterations=5, workdir="var/rsi/jobs/d",
                     timeout_s=60.0)


def _payload():
    return json.dumps({"best_score": 0.75,
                       "best_program_path": "var/rsi/jobs/d/o.py",
                       "best_program_sha256": "ab" * 32,
                       "iterations_completed": 5, "elapsed_s": 3.5,
                       "artifacts_dir": "var/rsi/jobs/d"})


class TestCommandConstruction(unittest.TestCase):
    def test_default_shape(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            cmd = drv.build_command(_job())
        self.assertEqual(cmd[0],
                         "var/rsi/openevolve/venv/Scripts/python.exe")
        self.assertEqual(cmd[1],
                         str(Path("drivers/openevolve_job.py").resolve()
                             .as_posix()))
        self.assertEqual(cmd[2], "--job")
        self.assertEqual(json.loads(cmd[3])["iterations"], 5)
        self.assertEqual(json.loads(cmd[3])["target"],
                         "var/rsi/jobs/d/initial_program.py")

    def test_python_env_override(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_PYTHON="py9.exe"),
                             clear=True):
            self.assertEqual(drv.build_command(_job())[0], "py9.exe")

    def test_cmd_template_replaces_whole(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_CMD="run.sh {job}"),
                             clear=True):
            cmd = drv.build_command(_job())
        self.assertEqual(cmd[0], "run.sh")
        self.assertEqual(json.loads(cmd[1])["iterations"], 5)


class TestRun(unittest.TestCase):
    def test_good_payload(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=_payload())):
            r = drv.run(_job())
        self.assertIsInstance(r, EvolveResult)
        self.assertEqual(r.best_score, 0.75)

    def test_noise_prefix_tolerated(self):
        drv = drv_evolve.EvolveDriver()
        noisy = "[llm] thinking…\n" + _payload()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=noisy)):
            self.assertEqual(drv.run(_job()).iterations_completed, 5)

    def test_rc_nonzero_is_eio(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(rc=3, stderr="boom")):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("EIO", str(cm.exception))

    def test_timeout_is_etimedout(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_TIMEOUT="0.001"),
                             clear=True), \
             mock.patch.object(subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(
                                   cmd=["x"], timeout=0.001)):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("ETIMEDOUT", str(cm.exception))

    def test_import_registers_executor(self):
        import laos.evolve as ev
        self.assertIn("openevolve", ev._executors)
        # run_job 全链：gate 放行 + mock 子进程 → EvolveResult
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=_payload())):
            r = ev.run_job(EvolveJob(
                target="var/rsi/jobs/d/initial_program.py",
                evaluator="var/rsi/jobs/d/evaluator.py", iterations=5))
        self.assertEqual(r.best_score, 0.75)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve -v`
Expected: ERROR——`ModuleNotFoundError: No module named 'drivers.drv_evolve'`。

- [ ] **Step 3: 写 openevolve_job.py（venv 内执行器）**

```python
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
```

- [ ] **Step 4: 写 drv_evolve.py（核心侧适配器）**

```python
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
```

- [ ] **Step 5: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve -v`
Expected: 全 PASS。

- [ ] **Step 6: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 全绿（注意 test_drv_evolve 的 import 登记会留在 `ev._executors`——若与 test_evolve 的 tearDown 清理次序冲突导致顺序敏感失败，把清理改为 `ev._executors.pop("openevolve", None)` 放进 test_drv_evolve 的 tearDown/addCleanup，重跑确认）。

- [ ] **Step 7: Commit**

```bash
git add drivers/drv_evolve.py drivers/openevolve_job.py tests/test_drv_evolve.py
git commit -m "feat: drv_evolve + openevolve_job——OpenEvolve 重依赖驱动（venv 子进程，CLI 稳定面）"
```

---

### Task 7: 真跑 e2e（手动门控：需 Task 2 后端可用）

**Files:**
- Create: `var/rsi/jobs/e2e-smoke/`（initial_program.py + evaluator.py，从官方示例拷入允许根）
- Create: `var/rsi/jobs/e2e-smoke.json`（syscall 真跑结果存档）

**Interfaces:**
- Consumes: Task 5 的 `evolve.run` syscall、Task 6 的驱动、Task 2 的后端配置。

- [ ] **Step 1: 备料进允许根**

```bash
mkdir -p var/rsi/jobs/e2e-smoke
cp var/rsi/openevolve/src/examples/function_minimization/initial_program.py \
   var/rsi/openevolve/src/examples/function_minimization/evaluator.py \
   var/rsi/jobs/e2e-smoke/
```

- [ ] **Step 2: 经内核 syscall 真跑（demo 脚本一次性）**

```bash
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import asyncio, json, sys
sys.path.insert(0, ".")
import drivers.drv_evolve  # 装配（ENODEV → opnevolve executor）
from laos.kernel import AgentKernel, CapabilitySet, PCB
from pathlib import Path

k = AgentKernel(Path("var/rsi/kernel-e2e"), audit_mode="w",
                confirm=lambda op: False)
k.procs[1] = PCB(pid=1, name="evo-e2e", caps=CapabilitySet(["evolve.*"]),
                 budget=None)
res = asyncio.run(k.syscall(1, "evolve.run", {
    "target": "var/rsi/jobs/e2e-smoke/initial_program.py",
    "evaluator": "var/rsi/jobs/e2e-smoke/evaluator.py",
    "iterations": 10}))
print(res.ok, getattr(res, "text", getattr(res, "error", "")))
Path("var/rsi/jobs/e2e-smoke.json").write_text(
    json.dumps({"ok": res.ok, "out": getattr(res, "text", res.error)},
               ensure_ascii=False, indent=2), encoding="utf-8")
k.shutdown()
PY
```

Expected: `True` + JSON payload（best_score/iterations_completed/sha256）；若 Task 3 发现 CLI 需要显式 config/后端参数，把补法回写 OBSERVATIONS.md 并在本步骤命令里相应加 `LAOS_EVOLVE_CMD` 覆盖演示（模板整体替换是设计好的逃生门）。

- [ ] **Step 3: 核对治理面证据**

```bash
tail -5 var/rsi/kernel-e2e/audit.jsonl 2>/dev/null || find var/rsi/kernel-e2e -name "*.jsonl" -exec tail -5 {} \;
```

Expected: 有 `event:"syscall"`（tool=evolve.run, builtin=true）与 `event:"evolve"`（best_score/sha256）两行——治理在循环外的实证，存档进 e2e-smoke.json 同目录说明行。

（无 commit——产物在 var/。）

---

### Task 8: 文档回写

**Files:**
- Modify: `docs/research/2026-10-09-rsi-landscape.md`（§7 实践入口排序行 + §8 裁决表 #2/#4 状态）

- [ ] **Step 1: §7 排序段补落地注**

在"实践入口排序"段末尾追加一句（原文风格）：

> 2026-10-09 后续：①已兑现——OpenEvolve 经 `drivers/drv_evolve.py`（venv 子进程）+ `laos/evolve.py`（gate/装配面）+ 内建 syscall `evolve.run`（caps→validate→sentinel→audit 全链）接入 laos，真跑存档 var/rsi/jobs/e2e-smoke.json；②的治理模式精读由本落地自然覆盖一半（worktree 隔离对照 cow.py 另案）。

- [ ] **Step 2: §8 裁决表状态更新**

`#2` 行裁决列改为 `◐ P2 → ● 已落地（evolve.run gate：禁区永不可放行，var/rsi/jobs 允许根）`；`#6`（RSI-Index 口径）追加 `e2e 已用 (final−initial)/(1−initial) 记录`（若 Step 真跑数字支持；不支持则照实写未记）。

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-10-09-rsi-landscape.md
git commit -m "docs: RSI 调研 §7/§8 回写——OpenEvolve 驱动落地状态"
```

---

## Self-Review（写完计划后自查记录）

1. **Spec 覆盖**：调研 §8 裁决 #2（自改写防线）→ Task 4 gate + Task 5 syscall 链；#5（auth/预算同构）→ Task 5 内建分支审计 + iterations 上限；#6（RSI-Index 口径）→ Task 8 Step 2；试跑（用户要求）→ Task 1–3。#3/#7（技能污染对照/JitMem 负面结果）不在本计划范围——它们是 ◐P2 对照检查项，与驱动落地正交，不混入。
2. **占位符扫描**：无 TBD/TODO；唯一的外部未知（OpenEvolve checkpoint 布局、llm 配置字段名）均由 Task 2/3 的实查步骤先行钉死，Task 6 代码只消费实查结论且有 rglob+fail-loud 兜底。
3. **类型一致性**：`EvolveJob(target, evaluator, iterations, workdir, timeout_s)` 与 `EvolveResult(best_score, best_program_path, best_program_sha256, iterations_completed, elapsed_s, artifacts_dir)` 在 Task 4/5/6 三处引用逐字段核对一致；`register_executor(fn)` 单键 "openevolve" 三处一致；kernel impl 消费 `(self, pcb, args) -> CallResult` 与 msg/mem 先例一致（kernel.py:897）。
4. **风险点**：unittest 发现顺序导致 `_executors` 残留（Task 6 Step 6 已写处置）；OpenEvolve Windows multiprocessing（Task 3 Step 1 已写守卫处置）；CLI 需要 config 才能跑（Task 7 Step 2 的 LAOS_EVOLVE_CMD 逃生门）。
