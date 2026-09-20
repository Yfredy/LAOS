#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_jev_local.py —— Jev 开源复现的端侧候选实测（本机 Windows / x86 CPU）。

用途：对已经 `edgejev build` 产出的 ONNX 模型目录做延迟 / 内存 / 体积实测。
只测"运行时不依赖 torch"的 onnxruntime 路径（yzfly/edgejev），因为这是 laos
（proot aarch64、无 NPU、CPU 推理）唯一可行的一类。其余候选的失败原因由
04-ondevice-benchmark.md 静态记录。

测量约定（与计划 Task 4 Step 2 对齐）：
- 首次调用（含 Agent 构造 / 权重加载 / onnxruntime 会话初始化）不计入延迟，但单独记录
  `first_load_ms`（常驻场景最关键——加载慢=不能频繁启停）。
- warmup 1 次后跑 n=30 取 median 与 p95（排除懒加载/编译抖动）。
- 峰值内存用 ctypes 调 GetProcessMemoryInfo 取当前进程 WorkingSet（Windows 下 RSS 代理），
  在"加载 + 推理"全程用后台线程采样取最大值。
- 模型体积取模型目录总字节数（含 model.onnx + tokenizer.json + edgejev.json）。

注意：本机是 x86 Windows，实测值外推到 aarch64 proot 没有可靠系数，只是量级估计
（见 04 文档 Step 3）。

用法：
    python scripts/bench_jev_local.py <model_dir> [--n 30] [--out result.json]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time

try:
    import psutil
except Exception as exc:  # pragma: no cover
    psutil = None
    print("!! 未安装 psutil，峰值内存将记为 0：%s" % exc, file=sys.stderr)

try:
    import onnxruntime  # noqa: F401  仅用于探测 provider 信息
except Exception as exc:  # pragma: no cover
    print("!! 无法导入 onnxruntime：%s" % exc, file=sys.stderr)
    onnxruntime = None


# ---- 进程常驻内存（RSS / 工作集）采样 -------------------------------------
def _rss_bytes() -> int:
    """当前进程的常驻内存（Windows 下为工作集）。无 psutil 时回退 0。"""
    if psutil is None:
        return 0
    try:
        return psutil.Process(os.getpid()).memory_info().rss
    except Exception:
        return 0


class _RssSampler(threading.Thread):
    """后台线程：在基准期间周期性采样进程常驻内存，记录峰值（字节）。"""

    def __init__(self, stop_event: threading.Event, interval: float = 0.02):
        super().__init__(daemon=True)
        self._stop_ev = stop_event
        self._interval = interval
        self.peak = 0

    def run(self):
        while not self._stop_ev.is_set():
            ws = _rss_bytes()
            if ws > self.peak:
                self.peak = ws
            time.sleep(self._interval)


def _dir_size_mb(path: str) -> float:
    total = 0
    for d, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return total / 1e6


def bench_infer(fn, n: int = 30):
    """warmup 1 次后跑 n 次，返回 (median_ms, p95_ms, xs)。首次调用不计入。"""
    fn()  # warmup：触发 onnxruntime 图优化 / 首次内核编译
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t0) * 1000.0)
    xs.sort()
    p95_idx = min(int(0.95 * len(xs)), len(xs) - 1)
    return statistics.median(xs), xs[p95_idx], xs


# laos 相关的三题样例（与 edgejev README 一致：choice / noul / score 齐发）。
SAMPLE_STATE = "我的信用卡被扣了两次款，麻烦退一笔。"
SAMPLE_QUESTIONS = {
    "dept": {"type": "choice", "instructions": "该转给哪个组？",
             "criteria": {"billing": "支付、扣款、发票、退款",
                          "technical": "程序缺陷、报错",
                          "sales": "售前咨询、定价"}},
    "urgent": {"type": "noul", "instructions": "这条消息表达了紧急或时间压力"},
    "anger": {"type": "score", "instructions": "客户的不满程度",
              "criteria": ["平静陈述", "有情绪但讲道理", "非常愤怒"]},
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="本地实测 edgejev ONNX 模型的延迟/内存/体积")
    ap.add_argument("model_dir", help="edgejev build 产出的模型目录（含 edgejev.json）")
    ap.add_argument("--n", type=int, default=30, help="正式采样次数（warmup 不计入）")
    ap.add_argument("--out", default="", help="把结果写成 JSON 的路径")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.model_dir):
        print("!! 模型目录不存在：%s" % args.model_dir, file=sys.stderr)
        return 2

    try:
        from edgejev import Agent
    except Exception as exc:
        print("!! 无法导入 edgejev（运行时需 onnxruntime+tokenizers+numpy）：%s" % exc,
              file=sys.stderr)
        return 3

    stop = threading.Event()
    sampler = _RssSampler(stop)
    stop.clear()
    sampler.start()

    # 首次加载耗时（构造 Agent + 加载 onnx + tokenizer）。
    t_load0 = time.perf_counter()
    ag = Agent(args.model_dir)
    first_load_ms = (time.perf_counter() - t_load0) * 1000.0
    provider = getattr(ag, "provider_note", "?")

    def run_once():
        ag.system_one(SAMPLE_STATE, SAMPLE_QUESTIONS)

    median_ms, p95_ms, xs = bench_infer(run_once, n=args.n)
    stop.set()
    sampler.join(timeout=2.0)

    model_mb = _dir_size_mb(args.model_dir)
    peak_rss_mb = sampler.peak / 1e6

    # 跑一次取真实答案，验证能出合理结果（不计入延迟统计）。
    probe = ag.system_one(SAMPLE_STATE, SAMPLE_QUESTIONS)
    probe_ans = {k: (v.get("choice") or v.get("noul") or v.get("score"))
                 for k, v in probe.get("answers", {}).items()}

    result = {
        "model_dir": os.path.abspath(args.model_dir),
        "runtime": "onnxruntime",
        "provider": provider,
        "n": args.n,
        "first_load_ms": round(first_load_ms, 2),
        "median_ms": round(median_ms, 2),
        "p95_ms": round(p95_ms, 2),
        "min_ms": round(xs[0], 2),
        "max_ms": round(xs[-1], 2),
        "peak_rss_mb": round(peak_rss_mb, 1),
        "model_size_mb": round(model_mb, 1),
        "sample_state": SAMPLE_STATE,
        "probe_answers": probe_ans,
        "platform": "%s %s" % (sys.platform, os.uname().machine if hasattr(os, "uname") else "?"),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
