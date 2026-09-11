#!/usr/bin/env python3
"""drv_npu —— NPU/加速器"设备驱动"（MCP Server）。

把端侧 AI 推理硬件（骁龙 HTP/DSP、QNN x86 后端、stub 模拟器）封装成 syscall：

    npu.devices  列出可用推理后端与加载状态
    npu.infer    执行一次推理（按功耗定价，消耗风险账本）

路线 C（桌面原型，docs/research/2026-09-09-qnn-real-os-integration.md）：
QAIRT SDK（QAIRT_ROOT 或默认路径）里的 libQnnCpu 会被 ctypes 真实加载以验证
链路；推理图级绑定（QnnContext_create/eai_execute）属于路线 A 的工作，原型
在加载成功后返回 ENOSYS 指引。stub 后端零依赖可用：确定性 7 类 softmax，
让能力表/风险计费/审计流的演示不依赖任何硬件。

路线 A（真机闭环）：设置 LAOS_NPU_ENDPOINT（如 http://127.0.0.1:8900，经
`adb forward tcp:8900 tcp:8900` 指到真机 App 的 InferenceServer）后，可用
backend="device" 走真机 QNN LPAI 推理——input 传 base64(PCM16LE) 音频。
一次真机推理 = laos 审计流里的一条 syscall + 风险账本的一次功耗扣费。

定价语义来自 QNN/ADSP 的物理现实（docs/research §三）：推理消耗的功耗是
不可逆的——所以 npu.infer 标注 reversible=False（消耗风险账本），而不是
"可以撤销的计算"。
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402

drv = MCPServer("drv_npu", version="0.2.0")

EMOTION_CLASSES = ("happy", "sad", "angry", "neutral", "fear", "disgust", "surprise")

#: 真机推理服务端点（App 内 InferenceServer，经 adb forward 暴露到本机）
DEVICE_ENDPOINT = os.environ.get("LAOS_NPU_ENDPOINT", "")

#: QAIRT SDK 的候选根目录：环境变量优先，其次本机已知安装位置
_QAIRT_CANDIDATES = (
    os.environ.get("QAIRT_ROOT", ""),
    r"C:\Users\yaoyue\Downloads\QNN\qnnsdk\qairt\2.47.0.260601",
)


def _qnn_backend_lib() -> Path | None:
    """定位 QNN CPU 后端库（Windows 叫 QnnCpu.dll，Linux 叫 libQnnCpu.so）。"""
    if sys.platform == "win32":
        arch, name = "x86_64-windows-msvc", "QnnCpu.dll"
    else:
        arch, name = "x86_64-linux-clang", "libQnnCpu.so"
    for root in _QAIRT_CANDIDATES:
        if not root:
            continue
        p = Path(root) / "lib" / arch / name
        if p.exists():
            return p
    return None


def _device_health(timeout_s: float = 2.0) -> dict:
    """真机推理服务健康探测（None = 端点未配置/不可达）。"""
    if not DEVICE_ENDPOINT:
        return {"name": "device-timnet", "kind": "qnn-lpai", "available": False,
                "detail": "未配置 LAOS_NPU_ENDPOINT（adb forward tcp:8900 后设为 http://127.0.0.1:8900）"}
    try:
        with urllib.request.urlopen(f"{DEVICE_ENDPOINT}/health", timeout=timeout_s) as resp:
            info = json.loads(resp.read().decode("utf-8"))
        return {"name": "device-timnet", "kind": "qnn-lpai", "available": True,
                "detail": f"model={info.get('model')} initialized={info.get('initialized')} @ {DEVICE_ENDPOINT}"}
    except Exception as exc:
        return {"name": "device-timnet", "kind": "qnn-lpai", "available": False,
                "detail": f"端点不可达: {exc}"}


def _device_infer(model: str, input_b64: str, sample_rate: int) -> str:
    """真机推理：POST base64 PCM16 到 App 的 /infer，返回 7 类概率。"""
    body = json.dumps({"samples_b64": input_b64, "sample_rate": sample_rate}).encode("utf-8")
    req = urllib.request.Request(
        f"{DEVICE_ENDPOINT}/infer", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    lines = [f"backend=device-timnet model={model} latency={out.get('latency_ms')}ms "
             f"samples={out.get('samples')}"]
    labels = list(out.get("labels") or EMOTION_CLASSES)
    probs = [float(p) for p in (out.get("probs") or [])]
    for label, p in zip(labels, probs):
        lines.append(f"  {str(label):<10}{p * 100:5.1f}%")
    top1 = str(out.get("top1", ""))
    conf = probs[labels.index(top1)] * 100 if top1 in labels else 0.0
    lines.append(f"top1={top1} conf={conf:.1f}%")
    return "\n".join(lines)


def _backend_report() -> list[dict]:
    """探测所有推理后端：stub 永远可用；qnn-cpu 取决于库是否存在且可加载。"""
    out = []
    if DEVICE_ENDPOINT:
        out.append(_device_health(timeout_s=2.0))
    out.append({
        "name": "stub",
        "kind": "simulator",
        "available": True,
        "detail": "确定性模拟推理（7 类情感），零硬件依赖",
    })
    lib = _qnn_backend_lib()
    if lib is None:
        out.append({
            "name": "qnn-cpu",
            "kind": "qairt",
            "available": False,
            "detail": "未找到 libQnnCpu（设置 QAIRT_ROOT 指向 QAIRT SDK）",
        })
        return out
    try:
        ctypes.CDLL(str(lib))
        out.append({
            "name": "qnn-cpu",
            "kind": "qairt",
            "available": True,
            "detail": f"已加载 {lib.name}（图级推理绑定见路线 A）",
        })
    except OSError as exc:
        out.append({
            "name": "qnn-cpu",
            "kind": "qairt",
            "available": False,
            "detail": f"库加载失败: {exc}",
        })
    return out


def _stub_infer(model: str, payload: bytes) -> str:
    """确定性模拟推理：输入哈希 → 7 类 softmax 分布（标注 stub，可复现）。"""
    digest = hashlib.sha256(f"{model}::{payload.decode('latin-1')}".encode()).digest()
    scores = [b / 255.0 for b in digest[: len(EMOTION_CLASSES)]]
    total = sum(scores) or 1.0
    probs = sorted(
        ((cls, s / total) for cls, s in zip(EMOTION_CLASSES, scores)),
        key=lambda kv: -kv[1],
    )
    lines = [f"backend=stub model={model} classes={len(EMOTION_CLASSES)}"]
    for cls, p in probs:
        lines.append(f"  {cls:<10}{p * 100:5.1f}%")
    lines.append(f"top1={probs[0][0]} conf={probs[0][1] * 100:.1f}%")
    return "\n".join(lines)


@drv.tool(
    "npu.devices",
    "列出可用推理后端（QNN/stub）与加载状态",
    {"type": "object", "properties": {}},
)
def npu_devices() -> str:
    lines = []
    for b in _backend_report():
        flag = "OK " if b["available"] else "-- "
        lines.append(f"[{flag}] {b['name']:<8} ({b['kind']}) {b['detail']}")
    return "\n".join(lines)


@drv.tool(
    "npu.infer",
    "执行一次端侧推理（消耗功耗预算：reversible=False, cost=2）",
    {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "模型名，如 timnet"},
            "input": {"type": "string",
                      "description": "stub: 任意文本；device: base64(PCM16LE 音频)"},
            "backend": {"type": "string",
                        "description": "auto(默认)/stub/qnn-cpu/device"},
            "sample_rate": {"type": "integer", "description": "device 后端的采样率（默认 16000）"},
        },
        "required": ["model", "input"],
    },
    reversible=False,
    risk="medium",
    irreversibility_cost=2,
)
def npu_infer(model: str, input: str, backend: str = "auto",
              sample_rate: int = 16000) -> str:
    backends = {b["name"]: b for b in _backend_report()}
    if backend == "device":
        backend = "device-timnet"  # 别名：真机后端
    if backend == "auto":
        # auto 的语义：能真推理由的优先——真机 > stub。qnn-cpu 的图级绑定
        # 未实现（ENOSYS），只在显式指定时走。
        backend = "device-timnet" if backends.get("device-timnet", {}).get("available") \
            else "stub"
    if backend not in backends:
        raise ValueError(f"EINVAL: unknown backend {backend!r}")
    if not backends[backend]["available"]:
        raise IOError(f"EIO: backend {backend} unavailable: {backends[backend]['detail']}")

    if backend == "device-timnet":
        return _device_infer(model, input, sample_rate)

    if backend == "qnn-cpu":
        lib = _qnn_backend_lib()
        try:
            ctypes.CDLL(str(lib))
        except OSError as exc:
            raise IOError(f"EIO: qnn-cpu load failed: {exc}") from exc
        # 图级推理（QnnContext_create/eai_execute）是路线 A 的 JNI/cffi 绑定工作
        raise NotImplementedError(
            "ENOSYS: qnn-cpu graph binding not implemented in prototype "
            "(see docs/research/2026-09-09-qnn-real-os-integration.md Route A)")

    return _stub_infer(model, input.encode("utf-8"))


if __name__ == "__main__":
    drv.serve_forever()
