#!/usr/bin/env bash
# Linux AgentOS 认知 demo —— 30 秒讲清：内核 + Agent(进程) + MCP(驱动)
# 运行：wsl -- bash demos/agentos-demo/run_demo.sh   （非零退出 = 某幕断言失败）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
echo "== 幕一：设备上线（MCP 文件服务 = 驱动） =="
python3 -u - <<'PY'
from kernel import DemoKernel
from pathlib import Path
k = DemoKernel()                       # 懒起真 mcp_fs.py（DEMO_JAIL=var/jail）
Path("var/jail").mkdir(parents=True, exist_ok=True)
Path("var/jail/a.txt").write_text("hello-from-jail", encoding="utf-8")
for stale in ("b.txt", "c.txt"):       # 清上次残留，保证幕四断言可复现
    p = Path("var/jail") / stale
    if p.exists():
        p.unlink()

print("== 幕二：Agent 上场（真实 Linux 进程） ==")
k.write_script("reader", [
    {"op": "fs.read", "args": {"path": "a.txt"}},
    {"op": "fs.write", "args": {"path": "b.txt", "data": "reader-was-here"}},
    {"op": "selftest.execve", "args": {}},
])
k.write_script("writer", [
    {"op": "fs.write", "args": {"path": "c.txt", "data": "writer-rulez"}},
])
r = k.spawn("reader", caps=["fs.read", "selftest.execve"])   # 无 fs.write
w = k.spawn("writer", caps=["fs.read", "fs.write"])
print(f"  reader pid={r}  writer pid={w}")

print("== 幕三：syscall 循环（能力闸 + 代理到驱动） ==")
k.syscall_loop(timeout=15)

print("== 幕四：验证（越权被拒 / seccomp 生效 / jail 落盘） ==")
rows = k.audit_rows()
for row in rows:
    mark = "OK " if row["ok"] else "DENY"
    print(f"  [{mark}] pid={row['pid']} {row['op']} -> {row['result'][:48]}")
assert any(r_["op"] == "fs.write" and not r_["ok"] for r_ in rows), "能力闸未拦越权"
assert any(r_["op"] == "selftest.execve" and not r_["ok"] for r_ in rows), "seccomp 未拦"
b = Path("var/jail/b.txt")
assert not b.exists(), "越权写竟落盘"
assert Path("var/jail/c.txt").read_text(encoding="utf-8") == "writer-rulez"

print("== 幕五：审计（内核日志，一行一事件） ==")
print(f"AUDIT {len(rows)} rows -> {k.audit_path}")
print("demo 通过：Agent=进程 / 内核=监督者(能力+审计) / MCP=驱动 / seccomp=强制层")
PY
