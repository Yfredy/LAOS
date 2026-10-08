#!/usr/bin/env python3
"""agent —— Linux AgentOS demo 的"Agent"：一个真实 Linux 进程。

启动即真进程（本进程的 pid/退出码/信号都是内核语义，非模拟），且开机
第一件事是自装 seccomp 过滤器（L4 强制层）：execve/socket 一律 EPERM，
内核之外无资源。行为循环：读 var/scripts/<agent_id>.json 的任务脚本，
逐条把 syscall 打到 stdout、从 stdin 读应答——agent 的唯一资源通道就是
这对管道（内核）。

selftest.* 步骤是协议旁路：不发给内核，在本进程里实测危险操作是否真被
seccomp 拦下，结果以 {"op":..., "__self": reply} 一行回内核——内核只入
审计、不回写应答（危险操作必须在被收紧的进程里测，内核不能代劳）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        import seccomp_gate
        seccomp_gate.install()
    except Exception:
        pass  # 装不上照常跑（非 Linux 场景）；装上了 = 物理收紧
    agent_id = sys.argv[1]
    script = json.loads((HERE / "var" / "scripts" / f"{agent_id}.json")
                        .read_text(encoding="utf-8"))
    for step in script:
        if step["op"].startswith("selftest."):
            reply = _selftest_local(step["op"])
            sys.stdout.write(json.dumps(
                {"op": step["op"], "args": {}, "__self": reply},
                ensure_ascii=False) + "\n")
            sys.stdout.flush()
        else:
            sys.stdout.write(json.dumps(step, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            reply = json.loads(sys.stdin.readline())
        print(f"[{agent_id}] {step['op']} -> "
              f"{'OK ' + str(reply.get('result')) if reply['ok'] else reply.get('error')}",
              file=sys.stderr)
    return 0


def _selftest_local(op: str) -> dict:
    """selftest.* 不走内核——agent 在本地实测危险操作是否已被 seccomp 拦下。"""
    try:
        if op == "selftest.execve":
            subprocess.run(["/bin/true"], check=True)   # noqa: F401 已被 seccomp 拦
        elif op == "selftest.socket":
            import socket as _s
            _s.socket().connect(("127.0.0.1", 1))
        return {"ok": True, "result": "DANGEROUS: not blocked"}
    except OSError as exc:  # PermissionError 是 OSError 子类，一并接住
        return {"ok": False, "error": f"blocked: {type(exc).__name__} {exc}"[:120]}


if __name__ == "__main__":
    raise SystemExit(main())
