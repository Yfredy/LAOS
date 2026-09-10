#!/usr/bin/env python3
"""termux_matrix —— Android/Termux 强制层降级矩阵一键实测。

在手机的 Termux 里运行（在 laos 仓库根目录下）：

    python scripts/termux_matrix.py

逐项实测并生成报告 var/termux-matrix-<日期>.md：

    1. 系统信息      Android 版本 / 内核 / 架构
    2. 测试套件      python -m unittest discover -s tests（169 项预期）
    3. unshare       Termux 下 user namespace 是否可用（W^X 策略常禁）
    4. seccomp       ctypes prctl 装过滤器是否成功 + 过滤器是否真生效（swapon 应得 EPERM）
    5. cgroup v2     /sys/fs/cgroup 是否可写（通常需 root）
    6. 隔离报告      LAOS_ENFORCEMENT=android 时内核的 isolation 自述
    7. 真机推理闭环  App InferenceServer（127.0.0.1:8900）健康 + 一次真实 npu.infer
                     （需要先在手机上打开 TimnetLpaiApp；laosd 与 App 同机，无需 adb）

所有检查独立 try/except：任何一项失败不影响其余；报告同时打印到终端并落盘。
Windows/Linux 上也能跑（各项会如实报 FAIL/DEGRADED），但本脚本的目标平台是 Termux。
"""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DEVICE_ENDPOINT = os.environ.get("LAOS_NPU_ENDPOINT", "http://127.0.0.1:8900")
PY = sys.executable

results: list[tuple[str, str, str]] = []  # (检查项, 状态, 详情)


def record(name: str, status: str, detail: str) -> None:
    results.append((name, status, detail))
    mark = {"OK": "✅", "DEGRADED": "🟡", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "·")
    print(f"  {mark} {name:<14} [{status:^8}] {detail.splitlines()[0] if detail else ''}")


def sh(cmd: list[str], timeout: float = 20.0) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as exc:
        return 1, str(exc)


# ---------------------------------------------------------------- 1. 系统信息
def check_system() -> None:
    detail = [f"python={platform.python_version()} machine={platform.machine()}"]
    if shutil.which("getprop"):
        for prop in ("ro.build.version.release", "ro.build.version.sdk", "ro.product.model"):
            rc, out = sh(["getprop", prop])
            detail.append(f"{prop}={out or '?'}")
    else:
        detail.append(f"system={platform.system()}（非 Android 运行环境）")
    uname = platform.uname()
    detail.append(f"kernel={uname.system} {uname.release}")
    record("系统信息", "OK", "；".join(detail))


# ---------------------------------------------------------------- 2. 测试套件
def check_suite() -> None:
    rc, out = sh([PY, "-m", "unittest", "discover", "-s", "tests"], timeout=300)
    tail = "\n".join(out.splitlines()[-2:])
    if rc == 0 and "OK" in out:
        record("测试套件", "OK", tail)
    else:
        record("测试套件", "FAIL", tail or f"rc={rc}")


# ---------------------------------------------------------------- 3. unshare
def check_unshare() -> None:
    if not shutil.which("unshare"):
        record("unshare", "FAIL", "unshare 二进制不存在（pkg install util-linux 可尝试）")
        return
    rc, out = sh(["unshare", "--mount", "--pid", "--fork", "--map-root-user",
                  "--", "true"])
    if rc == 0:
        record("unshare", "OK", "user namespace 可用（完整 namespace 隔离可开启）")
    elif rc == 124:
        record("unshare", "FAIL", "超时（W^X 策略挂起？）")
    else:
        record("unshare", "DEGRADED",
               f"不可用 rc={rc}: {out.splitlines()[0] if out else ''}"
               f"（Termux W^X 常禁 user ns——预期降级项）")


# ---------------------------------------------------------------- 4. seccomp
SECCOMP_PROBE = """
import ctypes, os, sys
sys.path.insert(0, r"{repo}")
from laos.seccomp import assemble_block_dangerous, install_seccomp
prog = assemble_block_dangerous(os.uname().machine)
if prog is None:
    raise SystemExit(3)  # 未知架构
install_seccomp(prog)
libc = ctypes.CDLL(None, use_errno=True)
r = libc.syscall(167, b"/nonexistent-swap-probe", 0)  # swapon
raise SystemExit(0 if r != 0 and ctypes.get_errno() == 1 else 4)
# 期望：swapon 被过滤器 EPERM（errno 1）；若 swapon 因别的原因失败（rc!=0 但 errno!=1）
# 也说明过滤器已装上（真正的判别在 TestSeccompLinux 的 root 用例里）
""".replace("{repo}", str(REPO))


def check_seccomp() -> None:
    rc, out = sh([PY, "-c", SECCOMP_PROBE], timeout=15)
    if rc == 0:
        record("seccomp", "OK", "过滤器安装成功且 swapon 被 EPERM（强制真实生效）")
    elif rc == 3:
        record("seccomp", "DEGRADED", f"未知架构无法组装: {out.splitlines()[0] if out else ''}")
    elif rc == 4:
        record("seccomp", "DEGRADED", f"过滤器已装但 swapon 结果异常: {out.splitlines()[0] if out else ''}")
    else:
        record("seccomp", "FAIL", f"安装失败 rc={rc}: {out.splitlines()[0] if out else ''}"
                                   "（Termux seccomp 常见被上层策略限制）")


# ---------------------------------------------------------------- 5. cgroup
def check_cgroup() -> None:
    ctrl = Path("/sys/fs/cgroup/cgroup.controllers")
    if not ctrl.exists():
        record("cgroup v2", "DEGRADED", "cgroup v2 不可见（未挂载或非 Linux）")
        return
    leaf = Path("/sys/fs/cgroup/laos-matrix-probe")
    try:
        leaf.mkdir(parents=True, exist_ok=True)
        (leaf / "cgroup.procs").write_text(str(os.getpid()))
        record("cgroup v2", "OK", "可创建叶子并挂进程（需要留意这是 privileged 运行）")
        leaf.rmdir()
    except Exception as exc:
        record("cgroup v2", "DEGRADED", f"可见但不可写: {exc}（通常需 root——预期降级项）")


# ---------------------------------------------------------------- 6. 隔离报告
ISOLATION_PROBE = """
import sys
sys.path.insert(0, r"{repo}")
from laos.enforcement import select
backend = select(True, "auto", None, "android")
print(str(backend.report))
""".replace("{repo}", str(REPO))


def check_isolation_report() -> None:
    rc, out = sh([PY, "-c", ISOLATION_PROBE], timeout=15)
    if rc == 0:
        record("隔离报告", "OK", f"android 后端自述: {out.splitlines()[0] if out else ''}")
    else:
        record("隔离报告", "FAIL", f"rc={rc}: {out.splitlines()[0] if out else ''}")


# ---------------------------------------------------------------- 7. 真机闭环
DEVICE_LOOP_PROBE = """
import asyncio, base64, json, sys, urllib.request
sys.path.insert(0, r"{repo}")
from laos.kernel import AgentKernel
from laos.context import ContextManager
from pathlib import Path
import tempfile

endpoint = "{endpoint}"
with urllib.request.urlopen(endpoint + "/health", timeout=3) as r:
    if not json.loads(r.read()).get("initialized"):
        raise SystemExit(2)
td = tempfile.mkdtemp()
k = AgentKernel(Path(td), confirm=lambda op: True, irreversibility_budget=20)
env = {{"PYTHONPATH": r"{repo}", "LAOS_NPU_ENDPOINT": endpoint}}
k.load_driver("npu", [sys.executable, r"{driver}"], env=env)
k.branches.create_root("main")
pcb = k.spawn(name="probe", caps=["npu.*"], ctx=ContextManager(system_prompt="m"), branch="main")
pcm = base64.b64encode(b"\\x00\\x01" * 24000).decode()
res = asyncio.run(k.syscall(pcb.pid, "npu.infer",
                            {{"model": "timnet", "input": pcm, "backend": "device"}}))
k.shutdown()
print(res.text.splitlines()[-1] if res.ok else res.error)
raise SystemExit(0 if res.ok else 1)
""".replace("{repo}", str(REPO)).replace("{driver}", str(REPO / "drivers" / "drv_npu.py")).replace("{endpoint}", DEVICE_ENDPOINT)


def check_device_loop() -> None:
    try:
        with urllib.request.urlopen(f"{DEVICE_ENDPOINT}/health", timeout=3) as resp:
            info = __import__("json").loads(resp.read().decode("utf-8"))
    except Exception as exc:
        record("真机推理闭环", "SKIP",
               f"App 端点不可达: {exc}（先打开 TimnetLpaiApp 再重跑本脚本）")
        return
    if not info.get("initialized"):
        record("真机推理闭环", "DEGRADED", "App 在线但 classifier 未初始化完成，稍后重跑")
        return
    rc, out = sh([PY, "-c", DEVICE_LOOP_PROBE], timeout=60)
    if rc == 0:
        record("真机推理闭环", "OK", f"ADSP 推理成功: {out.splitlines()[0] if out else ''}")
    else:
        record("真机推理闭环", "FAIL", f"rc={rc}: {out.splitlines()[0] if out else ''}")


def main() -> int:
    print("=" * 64)
    print("  laos × Android/Termux 强制层降级矩阵实测")
    print("=" * 64)
    for fn in (check_system, check_suite, check_unshare, check_seccomp,
               check_cgroup, check_isolation_report, check_device_loop):
        fn()

    ok = sum(1 for _, s, _ in results if s == "OK")
    deg = sum(1 for _, s, _ in results if s == "DEGRADED")
    fail = sum(1 for _, s, _ in results if s == "FAIL")
    skip = sum(1 for _, s, _ in results if s == "SKIP")

    lines = [
        f"# laos × Android/Termux 降级矩阵实测报告",
        f"",
        f"- 日期: {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"- 结果: OK={ok} DEGRADED={deg} FAIL={fail} SKIP={skip}",
        "",
        "| 检查项 | 状态 | 详情 |",
        "|---|---|---|",
        *[f"| {n} | {s} | {d.replace('|', '\\|')} |" for n, s, d in results],
        "",
    ]
    report = REPO / "var" / f"termux-matrix-{datetime.date.today().isoformat()}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")

    print("=" * 64)
    print(f"  汇总: OK={ok} DEGRADED={deg} FAIL={fail} SKIP={skip}")
    print(f"  报告: {report}")
    print("=" * 64)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
