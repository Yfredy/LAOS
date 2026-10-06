# scripts/eval_whistle.py
"""端侧 ASR 效果评测 harness：Cactus Whistle vs funasr(SenseVoice) 基线。

    /c/Users/yaoyue/miniconda3/python.exe scripts/eval_whistle.py --backend whistle
    /c/Users/yaoyue/miniconda3/python.exe scripts/eval_whistle.py --backend funasr
    /c/Users/yaoyue/miniconda3/python.exe scripts/eval_whistle.py --backend all

评测集：var/asr_eval/ground_truth.json（SAPI TTS 合成的已知文本，16kHz/16bit/mono，
en×3 + zh×1，每段 ≤30s）。指标：laos.wer 的 WER(词)/CER(字) + 墙钟时延 + RTF。
结果写 var/asr_eval/results_<backend>.json，控制台打 markdown 表。

whistle 后端：调 cactus 引擎 CLI（LAOS_WHISTLE_CMD 覆盖，{wav}/{lang} 占位），
默认 "cactus transcribe Cactus-Compute/whistle --file {wav} --language {lang}"。
funasr 后端：与 drivers/drv_ear.py 相同的本机直推（SenseVoiceSmall + fsmn-vad）。
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.wer import cer, wer  # noqa: E402

GT_PATH = REPO / "var" / "asr_eval" / "ground_truth.json"
WHISTLE_DIR = REPO / "var" / "asr_eval" / "whistle"
DEFAULT_WHISTLE_CMD = ("cactus transcribe Cactus-Compute/whistle "
                       "--file {wav} --language {lang}")
SENSEVOICE_PATH = "D:/ldf/sensevoice_asr/models/models/iic--SenseVoiceSmall/snapshots/master"
FSMN_VAD_PATH = "D:/ldf/sensevoice_asr/models/models/iic--fsmn-vad"


def _clean(text: str) -> str:
    """剥转写格式标记（SenseVoice 的 <|en|><|NEUTRAL|>… 富标签）——格式不是内容。"""
    return re.sub(r"<\|[^|]*\|>", " ", text).strip()


def run_whistle(wav: Path, lang: str) -> tuple[str, float]:
    """调 cactus CLI 转写，返回 (text, wall_seconds)。"""
    tmpl = os.environ.get("LAOS_WHISTLE_CMD", DEFAULT_WHISTLE_CMD)
    cmd = tmpl.format(wav=str(wav), lang=lang).split()
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="replace")
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        return f"<ERROR rc={r.returncode}: {r.stderr.strip()[:200]}>", dt
    out = r.stdout.strip()
    # CLI 可能把转写文本放在最后一行非空输出（无 --json 时）
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return (lines[-1] if lines else "<EMPTY>"), dt


_funasr_model = None


def run_funasr(wav: Path, lang: str) -> tuple[str, float]:
    """funasr SenseVoice 本机直推（与 drv_ear funasr 通道同构），返回 (text, wall_seconds)。"""
    global _funasr_model
    t0 = time.perf_counter()
    if _funasr_model is None:
        from funasr import AutoModel  # 重依赖：惰性导入
        # 注：本机 funasr 1.4.0 的 fsmn-vad 注册损坏（RuntimeError: not registered）；
        # 评测段全部 ≤30s，SenseVoice 直吃整段，无需 VAD 切分。
        _funasr_model = AutoModel(
            model=SENSEVOICE_PATH,
            disable_update=True, disable_pbar=True, disable_log=True)
    with contextlib.redirect_stdout(io.StringIO()):  # funasr 往 stdout 打日志
        res = _funasr_model.generate(input=str(wav), cache={})
    dt = time.perf_counter() - t0
    text = res[0].get("text", "") if res else ""
    return _clean(text), dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["whistle", "funasr", "all"], default="all")
    ap.add_argument("--gt", default=str(GT_PATH))
    args = ap.parse_args()

    gt = json.load(open(args.gt, encoding="utf-8"))
    runners = {}
    if args.backend in ("whistle", "all"):
        runners["whistle"] = run_whistle
    if args.backend in ("funasr", "all"):
        runners["funasr"] = run_funasr

    results = {}
    for name, run in runners.items():
        rows = []
        for key, item in sorted(gt.items()):
            wav = Path(item["wav"])
            if not wav.exists():
                rows.append({"id": key, "error": f"missing {wav}"})
                continue
            text, dt = run(wav, item["lang"])
            metric = cer(item["text"], text) if item["lang"] == "zh" else wer(item["text"], text)
            rows.append({"id": key, "lang": item["lang"], "seconds": item["seconds"],
                         "wall_s": round(dt, 2), "rtf": round(dt / item["seconds"], 3),
                         "error_rate": round(metric, 4), "ref": item["text"], "hyp": text})
        ok = [r for r in rows if "error_rate" in r]
        agg = {"items": len(rows),
               "mean_err_en": _mean([r["error_rate"] for r in ok if r["lang"] == "en"]),
               "mean_err_zh": _mean([r["error_rate"] for r in ok if r["lang"] == "zh"]),
               "mean_rtf": _mean([r["rtf"] for r in ok]),
               "total_wall_s": round(sum(r.get("wall_s", 0) for r in ok), 2)}
        results[name] = {"rows": rows, "aggregate": agg}
        print(f"\n## {name}  (err=WER for en, CER for zh)\n")
        print("| id | lang | audio_s | wall_s | rtf | err | hyp |")
        print("|---|---|---|---|---|---|---|")
        for r in rows:
            if "error" in r:
                print(f"| {r['id']} | - | - | - | - | - | {r['error']} |")
            else:
                print(f"| {r['id']} | {r['lang']} | {r['seconds']} | {r['wall_s']} "
                      f"| {r['rtf']} | {r['error_rate']} | {r['hyp'][:60]} |")
        print(f"\naggregate: {json.dumps(agg, ensure_ascii=False)}")

    out = REPO / "var" / "asr_eval" / f"results_{args.backend}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nresults -> {out}")
    return 0


def _mean(xs: list) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


if __name__ == "__main__":
    raise SystemExit(main())
