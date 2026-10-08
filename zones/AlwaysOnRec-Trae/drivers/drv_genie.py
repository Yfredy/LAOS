#!/usr/bin/env python3
"""drv_genie —— 端侧 LLM"大脑"驱动（MCP Server）。

把端侧 LLM 推理封装成 syscall `llm.chat`，双后端：

    genie    QAIRT Genie 运行时（Windows: genie-t2t-run.exe；Android:
             libGenie.so）——真机 HTP 离线推理，需要已转换的模型上下文
    openai   任意 OpenAI 兼容端点（ollama / llama.cpp server / vLLM）——
             桌面立即可用（LAOS_LLM_BASE_URL 默认 ollama 11434）

选择：LAOS_LLM_BACKEND = auto|genie|openai；auto 时 genie 探测通过优先
（离线/私有），否则 openai 可达则用；都不可用 → EIO 且消息带两个原因。

设计边界：本驱动是"Agent 把 LLM 当工具调用"（如本地摘要、改写）；Agent
自身的大脑仍由 Brain 接口承担（OpenAIChatBrain 已支持 OpenAI 兼容端点）。
配置在模块加载时从 env 解析一次（确定性；测试直接改模块变量）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_genie", version="0.2.0")

_QAIRT_CANDIDATES = (
    os.environ.get("QAIRT_ROOT", ""),
    r"C:\Users\yaoyue\Downloads\QNN\qnnsdk\qairt\2.47.0.260601",
)


def _find_genie_exe() -> str | None:
    exe = os.environ.get("LAOS_GENIE_BIN")
    if exe and Path(exe).exists():
        return exe
    arch = "x86_64-windows-msvc" if sys.platform == "win32" else "x86_64-linux-clang"
    ext = ".exe" if sys.platform == "win32" else ""
    for root in _QAIRT_CANDIDATES:
        if not root:
            continue
        p = Path(root) / "bin" / arch / f"genie-t2t-run{ext}"
        if p.exists():
            return str(p)
    return None


# -- 模块加载时解析一次（确定性；测试直接覆盖这些变量）----------------------
_genie_exe_path = _find_genie_exe()
_genie_cfg_path: str | None = os.environ.get("LAOS_GENIE_CONFIG") or None
_openai_base_url: str | None = os.environ.get("LAOS_LLM_BASE_URL") or None
_genie_runner = None  # 可注入的 genie 执行器（默认 _run_genie；测试替换）


def _genie_ready() -> tuple[bool, str]:
    if _genie_exe_path and _genie_cfg_path:
        return True, f"exe={Path(_genie_exe_path).name} config={_genie_cfg_path}"
    miss = []
    if not _genie_exe_path:
        miss.append("genie-t2t-run 缺失")
    if not _genie_cfg_path:
        miss.append("LAOS_GENIE_CONFIG 未设")
    return False, "；".join(miss)


def _openai_ready() -> tuple[bool, str]:
    if not _openai_base_url:
        return False, "未设置 LAOS_LLM_BASE_URL"
    try:
        with urllib.request.urlopen(f"{_openai_base_url.rstrip('/')}/models",
                                    timeout=2) as r:
            return (r.status == 200), f"{_openai_base_url} 可达"
    except Exception as exc:
        return False, f"{_openai_base_url} 不可达: {exc}"


def _backend_report() -> list[dict]:
    g_ok, g_detail = _genie_ready()
    o_ok, o_detail = _openai_ready()
    return [
        {"name": "genie", "kind": "qairt", "available": g_ok, "detail": g_detail},
        {"name": "openai", "kind": "http", "available": o_ok, "detail": o_detail},
    ]


def _pick_backend() -> tuple[str | None, str]:
    report = {b["name"]: b for b in _backend_report()}
    backend = os.environ.get("LAOS_LLM_BACKEND", "auto")
    if backend == "genie":
        ok, detail = report["genie"]["available"], report["genie"]["detail"]
        return ("genie", "") if ok else (None, detail)
    if backend == "openai":
        ok, detail = report["openai"]["available"], report["openai"]["detail"]
        return ("openai", "") if ok else (None, detail)
    for name in ("genie", "openai"):
        if report[name]["available"]:
            return name, ""
    return None, f"genie: {report['genie']['detail']}; openai: {report['openai']['detail']}"


def _run_genie(exe: str, config: str, prompt: str, timeout: float) -> str:
    r = subprocess.run([exe, "-c", config, "--prompt", prompt],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise IOError(f"EIO: genie rc={r.returncode}: {(r.stderr or r.stdout)[:200]}")
    return r.stdout


def _chat_openai(base: str, model: str, prompt: str, system: str,
                 max_tokens: int, timeout: float) -> str:
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(f"{base.rstrip('/')}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


@drv.tool(
    "llm.chat",
    "端侧 LLM 对话（Genie 离线 / OpenAI 兼容端点；可重跑的计算）",
    {"type": "object",
     "properties": {"prompt": {"type": "string"},
                    "system": {"type": "string"},
                    "max_tokens": {"type": "integer"}},
     "required": ["prompt"]},
)
def llm_chat(prompt: str, system: str = "", max_tokens: int = 512) -> str:
    timeout = float(os.environ.get("LAOS_LLM_TIMEOUT", "120"))
    backend, reason = _pick_backend()
    if backend is None:
        raise IOError(f"EIO: no llm backend available ({reason})")
    t0 = time.time()
    if backend == "genie":
        full = f"{system}\n{prompt}" if system else prompt
        runner = _genie_runner or _run_genie
        text = runner(_genie_exe_path, _genie_cfg_path, full, timeout)
    else:
        text = _chat_openai(_openai_base_url,
                            os.environ.get("LAOS_LLM_MODEL", "local-model"),
                            prompt, system, max_tokens, timeout)
    return json.dumps({"text": text, "backend": backend,
                       "latency_ms": round((time.time() - t0) * 1000)},
                      ensure_ascii=False)


@drv.tool("llm.status", "列出 LLM 后端探测报告", {"type": "object", "properties": {}})
def llm_status() -> str:
    lines = []
    for b in _backend_report():
        flag = "OK " if b["available"] else "-- "
        lines.append(f"[{flag}] {b['name']:<7} ({b['kind']}) {b['detail']}")
    return "\n".join(lines)


if __name__ == "__main__":
    drv.serve_forever()
