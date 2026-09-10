#!/usr/bin/env python3
"""FLASepformer GPU 基准 —— 在带 CUDA 的 SenseVoice 环境（miniconda3）跑。

用法（Git Bash）：
    PYTHONPATH="D:/ms;D:/ms-deps" C:/Users/yaoyue/miniconda3/python.exe \
        scripts/flasep_gpu_bench.py

对比 CPU / GPU 推理延迟；长音频（15s/30s 合成混合语音）验证线性复杂度；
确认推理真实落在 GPU（显存采样）；分离产物写 outputs/audio/gpu_*.wav。
"""

import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np
import soundfile as sf
import torch
from modelscope.outputs import OutputKeys
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

MODEL = "iic/speech_flatsepreformer_separation_temporal_8k_base_libri2mix100"
OUT = REPO / "outputs" / "audio"

SAMPLE_URLS = (
    ("https://modelscope.cn/api/v1/models/damo/speech_flatflocoformer_separation_timefrequency_8k_middle_libri2mix360/repo?Revision=master&FilePath=examples/mix_speech1.wav", 2.5),
    ("https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/jaec/nearend_mic.wav", 10.0),
)


def make_long_mix(seconds: float, path: Path) -> None:
    """合成 8kHz 双人（双频）混合语音，验证长序列线性复杂度。"""
    import math
    import wave
    n = int(8000 * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        frames = bytearray()
        for i in range(n):
            v = (0.4 * math.sin(2 * math.pi * 300 * i / 8000)
                 + 0.4 * math.sin(2 * math.pi * 800 * i / 8000)
                 + 0.2 * math.sin(2 * math.pi * 1200 * i / 8000))
            frames += int(max(-1, min(1, v)) * 26000).to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))


def bench(pipeline_obj, wav: str, runs: int = 3) -> tuple[float, dict, object]:
    times = []
    last = None
    for _ in range(runs):
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        last = pipeline_obj(wav)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)
    meta = {}
    if torch.cuda.is_available():
        meta["gpu_peak_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    return statistics.median(times), meta, last


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    gpu = torch.cuda.is_available()
    print(f"torch={torch.__version__} cuda_available={gpu} "
          f"device={torch.cuda.get_device_name(0) if gpu else 'cpu'}")

    # 素材：文章示例（2.5s，8kHz）+ 合成长音频（10s/15s/30s，8kHz，验证线性复杂度）
    wavs = []
    url, _ = SAMPLE_URLS[0]
    name = url.rsplit("/", 1)[-1]
    p = OUT / name
    if not p.exists():
        urllib.request.urlretrieve(url, p)
    wavs.append(p)
    for secs in (10, 15, 30):
        p = OUT / f"mix_synth_{int(secs)}s.wav"
        if not p.exists():
            make_long_mix(secs, p)
        wavs.append(p)

    print("loading pipelines (cuda + cpu)...")
    p_gpu = pipeline(Tasks.speech_separation, model=MODEL,
                     trust_remote_code=True, device="cuda" if gpu else "cpu") if gpu else None
    p_cpu = pipeline(Tasks.speech_separation, model=MODEL,
                     trust_remote_code=True, device="cpu")

    rows = []
    for wav in wavs:
        info = sf.info(str(wav))
        dur = info.frames / info.samplerate
        cpu_t, _, _ = bench(p_cpu, str(wav))
        row = {"wav": wav.name, "dur_s": round(dur, 1), "cpu_s": round(cpu_t, 2)}
        if p_gpu is not None:
            gpu_t, meta, last = bench(p_gpu, str(wav))
            row["gpu_s"] = round(gpu_t, 2)
            row["speedup"] = round(cpu_t / gpu_t, 2)
            row["gpu_peak_mb"] = meta.get("gpu_peak_mb")
            if wav.name.startswith("mix_speech1"):
                for i, signal in enumerate(last[OutputKeys.OUTPUT_PCM_LIST]):
                    sf.write(str(OUT / f"gpu_separated_spk{i+1}.wav"),
                             np.frombuffer(signal, dtype=np.int16), 8000)
        rows.append(row)

    print()
    print(f"{'音频':<22}{'时长':>7}{'CPU(s)':>9}{'GPU(s)':>9}{'加速比':>8}{'显存峰值':>10}")
    for r in rows:
        gpu_s = f"{r['gpu_s']:.2f}" if "gpu_s" in r else "-"
        sp = f"{r['speedup']}x" if "speedup" in r else "-"
        mem = f"{r['gpu_peak_mb']}MB" if "gpu_peak_mb" in r else "-"
        print(f"{r['wav']:<22}{r['dur_s']:>6.1f}s{r['cpu_s']:>9.2f}{gpu_s:>9}{sp:>8}{mem:>10}")

    (OUT / "flasep_gpu_bench.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果 JSON: {OUT / 'flasep_gpu_bench.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
