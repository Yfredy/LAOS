#!/usr/bin/env python3
"""laosweb —— Linux AgentOS 内核状态实时面板。

不重复造轮子：内核引导 / 种子分支 / demo 全部复用 laosd，
本模块只做两件事——
  1. build_state(kernel)：把内核可观测面聚合成一个可 JSON 化的 dict
  2. http.server 起一个单页面板 + /api/state（1s 轮询，零依赖）

用法：
    python bin/laosweb.py                # 内核 + demo + 面板 (http://127.0.0.1:8800)
    LAOS_WEB_PORT=9000 python bin/laosweb.py
"""

from __future__ import annotations

import asyncio
import http.server
import json
import os
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import laosd  # noqa: E402  复用引导器：boot_kernel / seed_main_branch / demo / WORKDIR

PORT = int(os.environ.get("LAOS_WEB_PORT", "8800"))

# 模块级持有者：Handler 与测试共享当前内核（main() 里装配）
_kernel = None
# demo 线程结束后置 True，面板据此前置"运行中/已结束"徽标
_demo_done = False


# --------------------------------------------------------------------------
def build_state(kernel) -> dict:
    """聚合内核可观测面为单个 dict（纯函数，可直接单测 / JSON 序列化）。"""
    # snapshot 在 agent 全部 retire 后为空，回退到内核留存的末次派发视图
    scheduler = kernel.scheduler.snapshot() or list(kernel.sched_view.values())
    return {
        "status": kernel.status(),
        "procs": kernel.ps(),
        "branches": kernel.branches.list(),
        "scheduler": scheduler,
        "risk": {
            "spent": kernel.risk.spent,
            "remaining": kernel.risk.remaining,
            "budget": kernel.risk.budget,
            "per_tool": dict(kernel.risk.per_tool),
        },
        "isolation": str(kernel.isolation),
        "lsmod": kernel.lsmod(),
        "syscalls": kernel.syscalls(),
        "audit": [dict(r) for r in kernel.audit.records[-60:]],
        "demo_done": bool(_demo_done),
    }


# --------------------------------------------------------------------------
PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<title>laosweb</title></head>
<body><h1>laosweb</h1><p>内核状态面板骨架 —— 完整面板随后续版本交付。</p></body></html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    """GET / -> PAGE；GET /api/state -> 内核状态 JSON；其余 404。"""

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            try:
                payload = json.dumps(build_state(_kernel), ensure_ascii=False)
            except Exception:
                self._send(503, b'{"error": "kernel state unavailable"}',
                           "application/json; charset=utf-8")
                return
            self._send(200, payload.encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain; charset=utf-8")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass  # 静默访问日志，避免刷屏


# --------------------------------------------------------------------------
def main() -> int:
    global _kernel
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    kernel = laosd.boot_kernel(laosd.WORKDIR)
    laosd.seed_main_branch(kernel)
    _kernel = kernel

    def _run_demo():
        global _demo_done
        try:
            asyncio.run(laosd.demo(kernel, use_real=False, task=None))
        finally:
            _demo_done = True

    threading.Thread(target=_run_demo, daemon=True).start()

    url = f"http://127.0.0.1:{PORT}/"
    print(f"laosweb 面板: {url}  (Ctrl-C 退出)")
    try:
        http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        kernel.shutdown()
        print("laosweb 已关闭")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
