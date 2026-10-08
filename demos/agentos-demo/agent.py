#!/usr/bin/env python3
"""agent —— Linux AgentOS demo 的"Agent"：一个真实 Linux 进程。

启动即真进程（本进程的 pid/退出码/信号都是内核语义，非模拟）。行为循环：
读 var/scripts/<agent_id>.json 的任务脚本，逐条把 syscall 打到 stdout、
从 stdin 读应答——agent 的唯一资源通道就是这对管道（内核）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    agent_id = sys.argv[1]
    script = json.loads((HERE / "var" / "scripts" / f"{agent_id}.json")
                        .read_text(encoding="utf-8"))
    for step in script:
        sys.stdout.write(json.dumps(step, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        reply = json.loads(sys.stdin.readline())
        print(f"[{agent_id}] {step['op']} -> "
              f"{'OK ' + str(reply.get('result')) if reply['ok'] else reply.get('error')}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
