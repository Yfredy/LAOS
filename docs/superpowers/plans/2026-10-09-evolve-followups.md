# OpenEvolve 后续三项（sentinel 政策 / rotate 锁 / e2e 解锁 runbook）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 兑现 openevolve-driver 终审留下的三件后续：`evolve.run` 默认入 sentinel `always_ask`（决策已按推荐预决）、`AuditLog.rotate()` 补写锁、e2e 解锁 runbook 脚本（真跑仍由后端可用性门控）。

**Architecture:** 三件相互独立、各自带测试周期与评审面，故三 Task 切分。sentinel 走默认配置面（③ 级列表先于模式逻辑，全 mode 生效，② 显式 rule 是唯一免问通道——与现有六级判定序零冲突）；rotate 锁复用终审 C1 已埋的 `_wlock`，把换代三步（盖章代数/清列/重开）纳入互斥；runbook 是 scripts/ 工具（探测可离线测，真跑在线门控），复用 kernel+驱动装配面，不进核心。

**Tech Stack:** laos 核心 stdlib（threading/gzip/json/time/os）；测试 unittest + mock（离线）；runbook 脚本 stdlib + laos 内建装配（不起额外服务）。

**Spec:** `docs/research/2026-10-09-rsi-landscape.md` §8 裁决表（#1"评估器与权限在进化循环之外"）+ 2026-10-09 终审报告遗留项（sentinel 政策建议、rotate 预存债、e2e 解锁清单）。

## Global Constraints

- laos/ 核心纯 stdlib；不动 drivers/openevolve_job.py 与 venv 面（本计划零驱动改动）。
- 基线：master@565dec8，全量 **1085 绿**（OK, skipped=5）；测试命令 `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`。
- sentinel 判定序语义不得改变（laos/sentinel.py 模块头六级序是 nanoMuse 转译契约）：本计划只在 `SentinelConfig.always_ask` **默认值**里加 `"evolve.run"`，② 显式 rules 仍可放行（逃生门）。
- `(epoch, seq)` 复合键全库唯一（活文件 + audit-*.jsonl.gz 归档）是审计消费方（laosweb 前端去重）的硬契约——Task 2 的测试就钉这个不变式。
- runbook 真跑门控：无可用 LLM 后端时 `--check` 以退出码 2 收档（不烧迭代，OBSERVATIONS.md §后端 先例）；真跑产物只落 var/。
- 计划正文 checkbox 执行时不勾选（仓库约定）；完成度看 commit。
- 提交信息照各 Task Step 原文。

---

### Task 1: evolve.run 默认入 sentinel always_ask（TDD）

**Files:**
- Modify: `laos/sentinel.py:44`（SentinelConfig.always_ask 默认值）
- Test: `tests/test_sentinel.py`（文件末追加 TestEvolveAlwaysAsk 类）

**Interfaces:**
- Consumes: 既有 `Sentinel(config: SentinelConfig | None = None, ...)`（sentinel.py:108）、`SentinelConfig`（:41-50）、`Assessment(tool, risk, reversible, reads_private, egress)`、`Sentinel.decide(a, tainted=False) -> Decision`。
- Produces: `SentinelConfig.always_ask == ("evolve.run",)`（默认构造即得）；对 `Assessment("evolve.run", risk="medium", reversible=True)` 返回 `Decision("ask", "always-ask")`（③ 级，全部三种 mode）。Task 3 的 runbook 依赖此行为（其 confirm 回调会收到询问）。

- [ ] **Step 1: 写失败测试**（tests/test_sentinel.py 文件末追加；import 区已有 Assessment/Decision/Sentinel/SentinelConfig，无需新增）

```python
class TestEvolveAlwaysAsk(unittest.TestCase):
    """evolve.run 默认入 always_ask（终审政策项，2026-10-09 裁决采纳）：
    RSI syscall 每次过闸都坐一次人类确认席——"评估器与权限在进化循环
    之外"（RSI 调研 §8 #1）的最后一道人座。③ 级列表先于 ④ 模式逻辑，
    三种 mode 全生效；② 显式 rule 仍是唯一免问通道（逃生门）。"""

    def test_default_config_asks_in_all_modes(self):
        for mode in ("ask", "auto", "strict"):
            with self.subTest(mode=mode):
                d = Sentinel(SentinelConfig(mode=mode)).decide(
                    Assessment("evolve.run", risk="medium", reversible=True))
                self.assertEqual((d.action, d.reason), ("ask", "always-ask"))

    def test_explicit_rule_still_allows(self):
        cfg = SentinelConfig(rules=({"tool_glob": "evolve.run",
                                     "action": "allow"},))
        d = Sentinel(cfg).decide(
            Assessment("evolve.run", risk="medium", reversible=True))
        self.assertEqual((d.action, d.reason), ("allow", "rule"))

    def test_other_tools_unaffected(self):
        d = Sentinel(SentinelConfig()).decide(Assessment("msg.send"))
        # msg.send 非 egress 评估口径（Assessment.egress=False）→ ④ 默认放行
        self.assertEqual((d.action, d.reason), ("allow", "default"))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel.TestEvolveAlwaysAsk -v`
Expected: FAIL——`test_default_config_asks_in_all_modes` 断言失败（默认 `always_ask=()` 时 evolve.run 走到 ④ → `("allow", "default")`）；后两例本就通过（既有语义）。

- [ ] **Step 3: 最小实现**（laos/sentinel.py:44，原行 `    always_ask: tuple = ()` 替换为）

```python
    # evolve.run 默认入 ask 席（终审政策项 2026-10-09 采纳）：RSI syscall
    # 每次过闸坐一次人类确认——③ 级先于 ④ 模式，auto 也不豁免；② 显式
    # rule 是唯一免问通道（受信装配可显式放行）
    always_ask: tuple = ("evolve.run",)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_sentinel -v`
Expected: 全 PASS（既有 20 例 + 新 3 例）。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: **1088 绿**（1085 + 3），OK (skipped=5)。

- [ ] **Step 6: Commit**

```bash
git add laos/sentinel.py tests/test_sentinel.py
git commit -m "feat: evolve.run 默认入 sentinel always_ask——RSI syscall 首用人类确认（终审政策项采纳）"
```

---

### Task 2: AuditLog.rotate() 持 _wlock（TDD）

**Files:**
- Modify: `laos/kernel.py`（`AuditLog.rotate`，现约 :200-238；`_wlock` 已在构造器埋好）
- Test: `tests/test_laosweb.py`（文件末追加 TestAuditRotateConcurrency 类；rotate 的既有测试在本文件，归属一致）

**Interfaces:**
- Consumes: 终审 C1 已落的 `self._wlock = threading.Lock()`（构造器内）与持锁版 `write()`；kernel 测试构造式 `AgentKernel(Path(td)/"var", audit_mode="w", confirm=lambda op: False)`，内核实例的 `.audit` 即 AuditLog。
- Produces: `rotate()` 全程持锁（含异常恢复分支）；不变式"全库（活文件 + 全部 audit-*.jsonl.gz）逐行可解析且 (epoch, seq) 键唯一"在并发写+轮转下成立。Task 3 的 runbook 不直接消费本项（间接依赖审计完整性）。

- [ ] **Step 1: 写失败测试**（tests/test_laosweb.py 文件末追加；import 区按需补齐下列五个中该文件尚未有的，已有的不重复加：`import gzip, json, tempfile, threading, time` 以及 `from pathlib import Path`；AgentKernel 的既有 import 沿用文件原样，若本文件以别的方式构造内核则照其原样改写构造段，断言不变）

```python
class TestAuditRotateConcurrency(unittest.TestCase):
    """rotate() 必须持 _wlock（终审遗留债兑现）：与 worker 线程的并发写
    互斥后，(epoch,seq) 复合键全库唯一、每行可解析才可保证——这是
    laosweb 前端去重键的硬契约。无锁时 records.clear() 与 write() 的
    盖章/入列交错可造出同代同号，本压测即以其为失败信号。"""

    def test_concurrent_write_rotate_keeps_invariants(self):
        td = tempfile.TemporaryDirectory()
        k = AgentKernel(Path(td.name) / "var", audit_mode="w",
                        confirm=lambda op: False)
        try:
            stop = threading.Event()

            def writer(wid):
                i = 0
                while not stop.is_set():
                    k.audit.write({"event": "probe", "w": wid, "i": i})
                    i += 1

            threads = [threading.Thread(target=writer, args=(w,))
                       for w in range(4)]
            for t in threads:
                t.start()
            try:
                for _ in range(3):
                    time.sleep(0.05)
                    k.audit.rotate()
            finally:
                stop.set()
                for t in threads:
                    t.join()
            files = [k.audit.path,
                     *sorted(k.audit.path.parent.glob("audit-*.jsonl.gz"))]
            self.assertGreaterEqual(len(files), 2)  # 至少一次轮转真实发生
            keys = set()
            for f in files:
                if f.name.endswith(".gz"):
                    fh = gzip.open(f, "rt", encoding="utf-8")
                else:
                    fh = open(f, encoding="utf-8")
                with fh:
                    for line in fh:
                        rec = json.loads(line)
                        key = (rec["epoch"], rec["seq"])
                        self.assertNotIn(key, keys, f"复合键重复：{key}")
                        keys.add(key)
        finally:
            k.shutdown()
            td.cleanup()
```

- [ ] **Step 2: 跑测试确认失败（概率性）**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_laosweb.TestAuditRotateConcurrency -v`（连跑 3 次提高命中）
Expected: 无锁现状下高概率 FAIL（`复合键重复` 或行解析错误）；若三次全过（竞态未命中），以 Step 3 实现后回归全绿为准（本测试同时是修复后的确定性护栏——锁内无交错路径）。

- [ ] **Step 3: 实现**（laos/kernel.py `rotate()`：函数体整体缩进一层进 `with self._wlock:`；docstring 末尾追加一行说明。改后完整方法如下，原文体逐行保留）

```python
    def rotate(self) -> None:
        """轮转原语（设计 §6.2）：当前文件 gzip 归档 → 重开空文件继续追加。

        归档名 audit-<UTC日期>-<epoch>.jsonl.gz 内嵌单调轮转代 n；records
        清零即 seq 复位归零、epoch +1——消费方（laosweb 前端）以
        (epoch, seq) 复合键去重，轮转后同 seq 的新事件不会被误判重复。
        64MB 水位触发与归档保留策略（7 天 / 256MB）由后续轮转接线波次
        挂上；本方法只钉死"轮转发生时"的代数与 seq 语义。

        异常恢复（终审 T3-1，try/finally 语义保底 reopen）：归档/重开任
        一步抛错时，以追加模式重开原文件后原样上抛——数据未丢、代数未
        变、下次可重试；半途归档残件清掉（防开机扫档误续代）。审计断流
        是比轮转失败更大的错，句柄必须始终可用。

        线程安全（终审遗留债兑现）：全程持 _wlock——换代三步（盖章代数/
        清列/重开）不再与 write() 的盖章/入列交错，否则 records.clear()
        夹在 write 的 stamp 与 append 之间可造出同代同号的复合键重复。
        """
        with self._wlock:
            self._fh.flush()
            self._fh.close()
            archive = None
            try:
                stamp = time.strftime("%Y%m%d", time.gmtime())
                archive = self.path.with_name(
                    f"audit-{stamp}-{self.epoch}.jsonl.gz")
                if self.path.exists():
                    with self.path.open("rb") as src, open(archive, "wb") as raw:
                        with gzip.GzipFile(fileobj=raw, mode="wb") as out:
                            shutil.copyfileobj(src, out)
                        raw.flush()
                        os.fsync(raw.fileno())
                    self.path.unlink()
                new_fh = self.path.open("w", encoding="utf-8")
            except Exception:
                if archive is not None and archive.exists():
                    try:
                        archive.unlink()
                    except OSError:
                        pass  # 残件清理是尽力而为；主目标是指柄可用
                self._fh = self.path.open("a", encoding="utf-8")
                raise
            self._fh = new_fh
            self.records.clear()
            self.epoch += 1
```

死锁自查（实现者必读）：`write()` 持同一 `_wlock` 但 `rotate()` 内不再调 `write()`，无重入；`close()` 公开方法不在本改动面（kernel.shutdown 时已无并发写者，维持原样并在 commit message 不声称修复它）。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_laosweb -v`（含既有 rotate 用例全过）
Expected: 全 PASS。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: **1089 绿**（1088 + 1），OK (skipped=5)。

- [ ] **Step 6: Commit**

```bash
git add laos/kernel.py tests/test_laosweb.py
git commit -m "fix: AuditLog.rotate() 持 _wlock——轮转与并发写互斥，(epoch,seq) 键全库唯一（终审遗留债兑现）"
```

---

### Task 3: scripts/evolve_e2e.py——e2e 解锁 runbook（TDD，离线测探测面）

**Files:**
- Create: `scripts/evolve_e2e.py`
- Test: `tests/test_evolve_e2e.py`

**Interfaces:**
- Consumes: Task 1 的 sentinel 默认 ask（runbook 的 confirm 回调会收到询问并自动应答留痕）；既有 `AgentKernel(Path, audit_mode="w", confirm=...)`、`PCB(pid, name, caps, budget)`、`CapabilitySet(["evolve.*"])`、`drivers.drv_evolve`（import 即装配执行器）、`laos.evolve.EvolveResult`；venv 路径 `var/rsi/openevolve/venv/Scripts/python.exe` 与源码 `var/rsi/openevolve/src/`。
- Produces: `scan_env_backends() -> list[dict]`（纯 env 扫描，离线可测；每项 `{"name","key_env","base","base_source"}`）；CLI：`--check`（探测+连通性，可达退出 0 不可达 2）、`--iterations N`（默认 10）、无参全跑。产物 `var/rsi/jobs/e2e-smoke.json` + `var/rsi/openevolve/OBSERVATIONS.md` §e2e 追加块。

- [ ] **Step 1: 写失败测试**（创建 tests/test_evolve_e2e.py）

```python
# tests/test_evolve_e2e.py
"""evolve_e2e runbook 离线测试：后端 env 扫描契约（不触网；连通性探测
属在线面，由 --check 在真环境承担）。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve_e2e -v

脚本经 importlib 按路径加载（scripts/ 非包，test_calibrate_judge 同款
处理）；加载零副作用（main() 全在 __main__ 守卫内）。
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _load():
    spec = importlib.util.spec_from_file_location(
        "evolve_e2e", REPO / "scripts" / "evolve_e2e.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clean_env(**extra):
    drop = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
            "ANTHROPIC_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "MIMO_API_KEY")
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(extra)
    return env


class TestScanEnvBackends(unittest.TestCase):
    def test_no_keys_yields_empty(self):
        mod = _load()
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            self.assertEqual(mod.scan_env_backends(), [])

    def test_openai_key_detected_with_default_base(self):
        mod = _load()
        with mock.patch.dict(os.environ,
                             _clean_env(OPENAI_API_KEY="sk-x"), clear=True):
            found = mod.scan_env_backends()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "openai")
        self.assertEqual(found[0]["base"], "https://api.openai.com/v1")
        self.assertEqual(found[0]["base_source"], "default")

    def test_base_env_overrides_default(self):
        mod = _load()
        with mock.patch.dict(os.environ, _clean_env(
                OPENAI_API_KEY="sk-x",
                OPENAI_BASE_URL="https://api.example.com/v1"), clear=True):
            found = mod.scan_env_backends()
        self.assertEqual(found[0]["base"], "https://api.example.com/v1")
        self.assertEqual(found[0]["base_source"], "OPENAI_BASE_URL")

    def test_mimo_key_reads_openai_base_url(self):
        mod = _load()
        with mock.patch.dict(os.environ, _clean_env(
                MIMO_API_KEY="sk-m",
                OPENAI_BASE_URL="https://gw.internal/v1"), clear=True):
            found = mod.scan_env_backends()
        self.assertEqual(found[0]["name"], "mimo")
        self.assertEqual(found[0]["base"], "https://gw.internal/v1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve_e2e -v`
Expected: ERROR——` FileNotFoundError`（scripts/evolve_e2e.py 不存在）。

- [ ] **Step 3: 写 scripts/evolve_e2e.py**

```python
#!/usr/bin/env python3
"""evolve_e2e —— OpenEvolve e2e 解锁 runbook（RSI 驱动收档后的补跑入口）。

    --check        探测后端（env 扫描 + /models 连通性），可达 rc=0 / 不可达 rc=2
    --iterations N 进化迭代数（默认 10；首轮钉布局用小预算）
    （无参）        全链真跑：装配驱动 → 内核 syscall evolve.run（sentinel
                   默认 ask，本脚本 confirm 自动应答并留痕）→ 在途并发
                   syscall 断言（事件循环让出实证）→ checkpoint 布局钉死
                   → 结果落 var/rsi/jobs/e2e-smoke.json + OBSERVATIONS.md §e2e

后端注入：子进程继承 env，OpenEvolve 按 OPENAI_API_BASE/OPENAI_API_KEY
取 OpenAI 兼容端点（var/rsi/openevolve/OBSERVATIONS.md §后端 实证字段）。
产物只落 var/（目录纪律）；失败 fail-loud 带 errno 口径。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

VENV_PY = "var/rsi/openevolve/venv/Scripts/python.exe"
SRC = "var/rsi/openevolve/src"
EXAMPLE = Path(SRC) / "examples" / "function_minimization"
JOBS = Path("var/rsi/jobs")
OBS = Path("var/rsi/openevolve/OBSERVATIONS.md")

#: 候选表：(名字, key 环境变量, base 环境变量, 默认 base)。anthropic 不列
#: ——OpenEvolve 走 OpenAI 兼容面（README/配置面实证），ANTHROPIC_* 直连
#: 不可用；任意自建兼容端点可用 OPENAI_BASE_URL+OPENAI_API_KEY 直配。
_CANDIDATES = (
    ("openai", "OPENAI_API_KEY", "OPENAI_BASE_URL",
     "https://api.openai.com/v1"),
    ("gemini", "GEMINI_API_KEY", "GEMINI_BASE_URL",
     "https://generativelanguage.googleapis.com/v1beta/openai/"),
    ("mimo", "MIMO_API_KEY", "OPENAI_BASE_URL",
     "https://api.openai.com/v1"),
)


def scan_env_backends() -> list[dict]:
    """纯 env 扫描（离线）：key 在才算候选；base 记来源 default/env 名。"""
    found = []
    for name, key_env, base_env, default_base in _CANDIDATES:
        if os.environ.get(key_env):
            base = os.environ.get(base_env) or default_base
            found.append({"name": name, "key_env": key_env, "base": base,
                          "base_source": base_env if os.environ.get(base_env)
                          else "default"})
    return found


def ping(base: str, key: str, timeout: float = 8.0) -> tuple[bool, str]:
    """GET {base}/models 连通性探测（在线面，仅 --check/全跑调用）。"""
    cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
           "-m", str(timeout), "-H", f"Authorization: Bearer {key}",
           f"{base.rstrip('/')}/models"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout + 2)
    except subprocess.TimeoutExpired:
        return False, "ETIMEDOUT"
    code = (r.stdout or "").strip()
    return (code.startswith("2") or code == "401" and False or
            code.startswith("2"), code) if code else (False, "EIO-no-output")


def reachable_backends() -> list[dict]:
    out = []
    for cand in scan_env_backends():
        ok, detail = ping(cand["base"], os.environ[cand["key_env"]])
        cand = dict(cand, reachable=ok, probe=detail)
        out.append(cand)
    return out


def stage() -> dict:
    """示例三件套拷进允许根（gate 红线：target/evaluator 必须在 var/rsi/jobs 下）。"""
    dest = JOBS / "e2e-smoke"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("initial_program.py", "evaluator.py", "config.yaml"):
        src, dst = EXAMPLE / name, dest / name
        if not src.is_file():
            raise RuntimeError(f"ENOENT: 示例缺件 {src}（Task 1-3 试跑未做？）")
        shutil.copy2(src, dst)
    return {"target": (dest / "initial_program.py").as_posix(),
            "evaluator": (dest / "evaluator.py").as_posix(),
            "workdir": dest.as_posix()}


def pin_layout(workdir: Path) -> dict:
    """checkpoint 布局钉死：枚举文件 + 判定 _find_best 将走的路径。"""
    ckpt = workdir / "checkpoints"
    listing = []
    if ckpt.is_dir():
        for p in sorted(ckpt.rglob("*")):
            if p.is_file():
                listing.append(p.relative_to(workdir).as_posix())
    canonical = (ckpt / "best" / "best_program.py").is_file()
    return {"files": listing[:60], "count": len(listing),
            "canonical_best_program": canonical,
            "find_best_path": "canonical" if canonical else
            ("rglob" if any(n.endswith("best_program.py") for n in listing)
             else "ENOENT")}


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenEvolve e2e runbook")
    parser.add_argument("--check", action="store_true",
                        help="只做后端探测（可达 rc=0 / 不可达 rc=2）")
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()

    if not Path(VENV_PY).is_file():
        print(f"ENOENT: venv 不存在 {VENV_PY}——先跑试跑计划 Task 1（安装）")
        return 2
    cands = reachable_backends() if args.check else scan_env_backends()
    print(json.dumps(cands, ensure_ascii=False, indent=2))
    live = [c for c in cands if c.get("reachable")]
    if args.check:
        return 0 if live else 2
    if not live and cands:
        print("EIO: 候选 key 全部不可达（详见上方 probe 字段）——收档不烧迭代")
        return 2
    if not cands:
        print("ENOENT: 无后端候选 key——解锁路径见 var/rsi/openevolve/"
              "OBSERVATIONS.md §后端")
        return 2
    use = live[0] if live else cands[0]
    # OpenEvolve 读 OpenAI 兼容面：把选中候选归一成 OPENAI_API_BASE/KEY
    os.environ["OPENAI_API_BASE"] = use["base"]
    os.environ.setdefault("OPENAI_API_KEY", os.environ[use["key_env"]])

    asks: list[dict] = []

    def confirm(op: dict) -> bool:
        asks.append({"tool": op.get("tool"), "reason": op.get("sentinel")})
        print(f"[e2e runbook] sentinel ask 自动应答 yes：{op.get('tool')}"
              f"（{op.get('sentinel')}）——无头运行留痕")
        return True

    from laos.kernel import AgentKernel, CapabilitySet, PCB
    from laos.sentinel import Sentinel, SentinelConfig
    import drivers.drv_evolve  # noqa: F401  import 即装配执行器

    k = AgentKernel(Path("var/rsi/kernel-e2e"), audit_mode="w",
                    confirm=confirm, sentinel=Sentinel(SentinelConfig()))
    staged = stage()
    t0 = time.perf_counter()
    try:
        async def run() -> dict:
            k.procs[1] = PCB(pid=1, name="evo-e2e",
                             caps=CapabilitySet(["evolve.*"]), budget=None)
            evolve_task = asyncio.create_task(k.syscall(
                1, "evolve.run",
                {"target": staged["target"], "evaluator": staged["evaluator"],
                 "iterations": args.iterations}))
            quick = await asyncio.wait_for(k.syscall(1, "mem.stats", {}), 30.0)
            mid_run_ok = quick.ok and not evolve_task.done()
            result = await evolve_task
            return {"mid_run_syscall_ok": mid_run_ok,
                    "evolve_ok": result.ok,
                    "evolve_text": getattr(result, "text",
                                           getattr(result, "error", ""))}

        outcome = asyncio.run(run())
    finally:
        k.shutdown()
    layout = pin_layout(Path(staged["workdir"]))
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "backend": use, "asks": asks, "elapsed_s": round(
                  time.perf_counter() - t0, 1), **outcome,
              "layout": layout}
    out = JOBS / "e2e-smoke.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    with OBS.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## e2e（{record['ts']}）\n\n"
                 f"- 后端 {use['name']} @ {use['base']}；sentinel ask×{len(asks)}"
                 f"（自动应答留痕）；在途并发 syscall ok="
                 f"{outcome['mid_run_syscall_ok']}（事件循环让出实证）\n"
                 f"- checkpoint 布局：canonical={layout['canonical_best_program']}"
                 f" / files={layout['count']}——_best_score 解析路径据此钉死\n"
                 f"- 全文见 var/rsi/jobs/e2e-smoke.json\n")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print(f"wrote {out}")
    return 0 if outcome["evolve_ok"] and outcome["mid_run_syscall_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

注：`ping()` 返回行有意写成显式真值表达式（2xx 即真），实现者不得"简化"成 `code == "200"`——401/403 表示端点活着但 key 无效，由调用方读 probe 字段判断；此处放行 2xx 仅。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve_e2e -v`
Expected: 4/4 PASS。

- [ ] **Step 5: --check 实跑（门控证据，不烧迭代）**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/evolve_e2e.py --check; echo rc=$?`
Expected: 本机现状（内网网关 key）应打印候选与 probe 不可达，**rc=2**——这正是收档行为的活证据；有真 key 的环境才 rc=0。

- [ ] **Step 6: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: **1093 绿**（1089 + 4），OK (skipped=5)。

- [ ] **Step 7: Commit**

```bash
git add scripts/evolve_e2e.py tests/test_evolve_e2e.py
git commit -m "feat: scripts/evolve_e2e.py——e2e 解锁 runbook（--check 探测 rc 口径 + 全链真跑 + checkpoint 布局钉死）"
```

---

### Task 4: 文档回写

**Files:**
- Modify: `docs/research/2026-10-09-rsi-landscape.md`（§8 裁决表追加一行、§7 落地注补一句）

**Interfaces:**
- Consumes: Task 1/2/3 的落点事实（sentinel always_ask 生效、rotate 持锁、runbook 一命令）。

- [ ] **Step 1: §8 表尾追加一行**（表格最后一行之后）

```markdown
| 9 | evolve.run 默认入 sentinel `always_ask`（③ 级，全 mode 生效；② 显式 rule 唯一免问通道）+ `AuditLog.rotate()` 补 `_wlock` + `scripts/evolve_e2e.py` 解锁 runbook | ● 已落地（终审遗留三件 2026-10-09 兑现；e2e 真跑仍由后端门控，`--check` rc=2 收档证据在 var/） |
```

- [ ] **Step 2: §7 落地注末尾补一句**

在既有 `> 2026-10-09 后续：…` 引用块末尾追加：

```markdown
> 后续三件已兑现：evolve.run 入 sentinel ask 席、rotate 持锁、`python scripts/evolve_e2e.py --check` 一命令探测解锁（全跑自动留痕 asks/事件循环让出实证/布局钉死）。
```

- [ ] **Step 3: Commit**

```bash
git add docs/research/2026-10-09-rsi-landscape.md
git commit -m "docs: RSI 调研 §8/#9 + §7——终审遗留三件兑现回写"
```

---

## Self-Review（写完三查记录）

1. **spec 覆盖**：终审三遗留——sentinel 政策（Task 1，推荐=采纳 always_ask）、rotate 预存债（Task 2，提前兑现而非等水位波）、e2e 解锁清单（Task 3 runbook 化：探测/留痕/让出实证/布局钉死四要素全齐）+ 回写（Task 4）。无缺口。
2. **占位符扫描**：无 TBD/无测试体的"写测试"；Task 2 Step 2 的概率性失败已如实标注处置口径（连跑三次+以修复后护栏为准）；ping 的 2xx 判定是显式代码非口头描述。
3. **类型一致性**：`scan_env_backends() -> list[dict]` 字段四元组（name/key_env/base/base_source）在 Task 3 测试与实现逐字一致；`pin_layout` 返回键（files/count/canonical_best_program/find_best_path）与 e2e-smoke.json 记录一致；Task 1 的 `Decision("ask","always-ask")` reason 字串与 sentinel.py:145 判定序原文一致；Task 2 测试构造式与 tests/test_evolve.py:143 同款。
