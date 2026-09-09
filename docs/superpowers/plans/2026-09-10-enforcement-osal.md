# 强制层 OSAL 化（CherryUSB 模式）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学 CherryUSB 的 OSAL 模式，把 `laos/sandbox.py` 里的强制隔离逻辑（探测/wrap/seccomp shim/cgroup）抽成**显式的 enforcement 后端层**：核心内核只依赖一小撮原语，"换平台 = 换一个后端文件"；Android/Termux 成为有名字、有文档的一等后端（路线 A 的工程前提）。

**Architecture:** 新建 `laos/enforcement/` 包：`base.py`（`EnforcementBackend` 契约 + `IsolationReport`）、`linux.py`（现有 Linux 实现：探测/unshare+shim wrap/cgroup）、`android.py`（Termux 限制矩阵文档化，继承 Linux 探测但报告更精确的原因）、`stub.py`（非 Linux 降级）、`__init__.py`（`select()` 工厂：平台探测 + `LAOS_ENFORCEMENT` 显式覆盖，Kconfig 思想的运行时版）。`laos/sandbox.py` 保留 `Sandbox`/`PathJail` 公共 API（kernel/drivers/tests 的调用点零改动），内部全部委托后端。**重构不是重写**：Linux 后端的逻辑从 sandbox.py 原样搬运（git diff 可对照），行为零变化是硬验收。

**Tech Stack:** Python 3.10+ 标准库，零第三方依赖。

**Spec:** `docs/research/2026-09-10-cherry-embed-learning.md` §二.1（OSAL 模式）；现状逻辑在 `laos/sandbox.py`。

## Global Constraints

- 零第三方依赖；不破坏执行时基线（以实测为准，当前 164 项全绿）。
- **行为零变化**：`Sandbox` 的公共 API（`__init__(workdir, allow_network, enabled, seccomp)`、`wrap`、`estimate`、`make_cgroup`、`attach`、`report`、`seccomp_mode`、`_seccomp_prog`、`PathJail`）签名与语义完全不变；既有测试（含 `tests/test_seccomp.py` 的 TestWrapShim/TestSeccompLinux、`test_sandbox.py`）**零改动通过**。
- 新增测试放 `tests/test_enforcement.py`：只测新面（select 工厂、后端契约、Android 后端报告、显式覆盖 env）。
- 解释器 `$PY`（同前）；每 task 一个 commit。
- 强制力红线不变：seccomp 安装失败 fail-closed；非 Linux 降级不抛错。

## 现状关键事实

- `laos/sandbox.py`（约 260 行）：`IsolationReport`（dataclass）、`Sandbox`（`__init__` 读 LAOS_SECCOMP、`_probe` 平台探测、`wrap` unshare 前缀 + `_seccomp_shim` bootstrap、`estimate`、`make_cgroup`、`attach` 静态）、`PathJail`（平台无关）。
- `laos/seccomp.py` 独立（组装器 + 安装器）——不动。
- 调用方：`kernel.py`（`Sandbox(workdir)`、`wrap`、`make_cgroup`、`attach`、`report`）、`tests/test_seccomp.py`（`Sandbox(enabled=True, seccomp=...)`、`_seccomp_prog`、`wrap`）、`tests/test_sandbox.py`（`wrap` 降级）。
- 环境变量：`LAOS_SECCOMP`（off/block-dangerous）、`LAOS_CONFIRM` 等（enforcement 不新增语义，只新增 `LAOS_ENFORCEMENT` 显式覆盖：`auto|linux|android|stub`）。

---

### Task 1: enforcement 包骨架 + Linux/Stub 后端搬运

**Files:**
- Create: `laos/enforcement/__init__.py`、`laos/enforcement/base.py`、`laos/enforcement/linux.py`、`laos/enforcement/stub.py`
- Modify: `laos/sandbox.py`（委托后端；逻辑搬走）
- Test: 全量回归（零新测试——本 task 是纯搬运，既有 164 项即行为守卫）

**Interfaces:**
- Produces:
  - `IsolationReport` 移到 `base.py`（`sandbox.IsolationReport` 保留为 re-export 别名，既有 import 零改动）。
  - `EnforcementBackend`（base.py）：属性 `name`；方法 `probe() -> IsolationReport`、`wrap(argv) -> list`、`popen_kwargs() -> dict`、`make_cgroup(name, cpu_max, mem_max) -> Path | None`；静态 `attach(cgroup, pid)`。构造签名 `(enabled: bool, seccomp_mode: str, workdir: Path)`。
  - `LinuxBackend`（linux.py）：**原样搬运** sandbox.py 现有 `_probe/wrap/_seccomp_shim/make_cgroup` 逻辑（含 `_seccomp_prog` 属性、`BLOCKED_X86_64` 引用、`estimate` 语义）。
  - `StubBackend`（stub.py）：非 Linux 行为——probe 返回 `none(host)`（含"非 Linux 宿主…"原因）、wrap 原样返回、cgroup None。
  - `select(enabled, seccomp_mode, workdir, override=None) -> EnforcementBackend`：`override` 来自 `LAOS_ENFORCEMENT`（`auto|linux|android|stub`）；auto 时按 `sys.platform`（linux→LinuxBackend / android→AndroidBackend / 其他→StubBackend）；显式指定的后端若与平台不符则**报告原因但尊重选择**（在 IsolationReport.reasons 里写明"显式指定 linux 后端但宿主是 Windows——降级为 stub 行为"并返回对应平台后端实例……简化：显式选择只允许 auto + 当前平台后端 + stub，非法值按 auto 并在 reasons 记录）。
- `Sandbox` 重构后：`__init__` 构造后端（`self._backend`），`report/wrap/estimate/make_cgroup/attach/seccomp_mode/_seccomp_prog` 全部委托（`__init__` 里 `self.seccomp_mode = backend.seccomp_mode` 保持既有属性可写性——test_seccomp 直接赋值 `sb.seccomp_mode = "off"` 后调 wrap？检查：test_seccomp 用构造参数，不直接赋值——确认后可只读委托）。

- [ ] **Step 1: 搬运**——按 Interfaces 把逻辑移入 `linux.py`/`stub.py`/`base.py`/`__init__.py`；`sandbox.py` 的 `Sandbox` 改为薄委托（`wrap = lambda argv: self._backend.wrap(argv)` 形式的方法委托，保持可被子类/测试替换）；`PathJail` 不动。
- [ ] **Step 2: 全量回归**——`$PY -m unittest discover -s tests` 164 项零改动全绿；`grep -rn "seccomp import" laos/sandbox.py` 确认 sandbox.py 不再直接 import seccomp 组装器（已由 linux.py 接管）。
- [ ] **Step 3: Commit** — `refactor(laos): enforcement OSAL skeleton (linux/stub backends moved verbatim)`

---

### Task 2: Android 后端 + select 工厂 + 测试

**Files:**
- Create: `laos/enforcement/android.py`
- Modify: `laos/enforcement/__init__.py`（select 支持 android）、`laos/sandbox.py`（透传 `LAOS_ENFORCEMENT`）
- Test: `tests/test_enforcement.py`（新建）

**Interfaces:**
- Produces:
  - `AndroidBackend(LinuxBackend)`：`probe()` 在 Linux 探测基础上叠加 Termux 限制文档（reasons 追加：`Termux: user namespace 受 W^X 策略限制，unshare 可能不可用——实测矩阵见 docs/research §五.4`）；wrap 逻辑同 Linux（Termux 的 proot 有单独说明）；类 docstring 列出 Termux 降级矩阵（namespace/seccomp/cgroup 哪些通常可用）。
  - `select()`：`LAOS_ENFORCEMENT=linux|android|stub` 显式覆盖（平台不符 → 尊重选择但 reasons 记录"显式指定 X 后端在 Y 宿主上行为=stub 降级"，此时返回 StubBackend 实例但 name 保留请求名）；`auto` 按平台。
- 测试用例（`tests/test_enforcement.py`）：
  1. `test_select_auto_by_platform`——monkeypatch `sys.platform` 三态，断言后端类型正确。
  2. `test_select_explicit_override`——`LAOS_ENFORCEMENT=stub` 强制 Windows/Linux 都拿 StubBackend；`LAOS_ENFORCEMENT=linux` 在 Linux 拿 LinuxBackend（skipUnless Linux）。
  3. `test_android_backend_reports_termux_notes`——直接实例化 AndroidBackend，probe 的 reasons 含 "Termux"。
  4. `test_invalid_override_falls_back_auto`——`LAOS_ENFORCEMENT=bogus` → auto 行为 + reason 记录。
  5. `test_sandbox_delegates_to_backend`——`Sandbox(...)._backend.name` 与 `report` 一致性。
- [ ] 实现 + 测试全绿（基线 + ~5）
- [ ] **Commit** — `feat(laos): android enforcement backend + LAOS_ENFORCEMENT selection`

---

### Task 3: 文档 + 收尾

**Files:**
- Modify: `README.md`（§7 目录结构加 `enforcement/` 包行；测试数实测）、`docs/research/2026-09-10-cherry-embed-learning.md`（§五标注"OSAL 化已落地"）

- [ ] README 两处更新；guide-panel 不动
- [ ] 全量回归 + **手工验收**：`LAOS_ENFORCEMENT=stub $PY bin/laosd.py 2>&1 | grep 隔离`（隔离报告出现 stub 相关原因）+ 默认启动对比
- [ ] **Commit** — `docs(laos): enforcement OSAL in README and learning notes`

## 验收清单

- [ ] 全量测试全绿（基线 164 + ~5 新）
- [ ] 既有测试文件零改动（refactor 纯度）
- [ ] `LAOS_ENFORCEMENT=stub` 显式覆盖在 demo 隔离报告中可见
- [ ] 本计划恰 3 个 commit
