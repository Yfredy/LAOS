"""四模块复现冒烟汇总：各跑一条代表性命令，汇总退出码。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CASES = [
    ("bs1770 校准", [sys.executable, "-c",
      "import numpy as np; from repro.bs1770 import integrated_loudness, true_peak; "
      "fs=48000; t=np.arange(fs*8)/fs; "
      "x=np.stack([10**(-23/20)*np.sin(2*np.pi*997*t)]*2); "
      "I=integrated_loudness(x,fs); TP=true_peak(x,fs); "
      "assert abs(I-(-23.0))<0.1 and abs(TP-(-23.0))<0.2; "
      "print('  stereo 997Hz@-23dBFS: I=%.2f LUFS, TP=%.2f dBTP' % (I, TP))"]),
    ("FxLMS 降噪", [sys.executable, "-c",
      "import numpy as np; from repro.anc import engine_harmonics, fir_apply, fxlms; "
      "rng=np.random.default_rng(3); fs=8000; "
      "x=engine_harmonics(2400.0,[2],fs,3.0,1.0,rng); "
      "p,s=np.array([0.05,0.9,0.15]),np.array([0.6,0.35,0.08]); d=fir_apply(x,p); "
      "e,_=fxlms(x,p,s,mu=0.03,L=24); "
      "att=10*np.log10(np.mean(d[12000:]**2)/np.mean(e[12000:]**2)); "
      "assert att>20; print('  tonal attenuation: %.1f dB' % att)"]),
    ("SHO 端到端（小规模）", [sys.executable, str(ROOT / "scripts" / "run_sho_repro.py"),
      "--n-utt", "24", "--iters", "40"]),
    ("PhaseCoder MPE", [sys.executable, "-c",
      "import numpy as np; from repro.phasecoder import arbitrary_mic_geometry_embeddings; "
      "from repro.sho.ism import circular_array; "
      "e=arbitrary_mic_geometry_embeddings(circular_array(6,0.045)); "
      "assert e.shape==(6,256); print('  6-mic MPE: %s, |max|=%.2f'"
      " % (e.shape, np.abs(e).max()))"]),
]


def main():
    fails = 0
    for name, cmd in CASES:
        print(f"== {name} ==")
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip()
        if out:
            print(out)
        if r.returncode != 0:
            fails += 1
            print((r.stderr or "").strip()[-500:])
            print(f"  [FAIL rc={r.returncode}]")
        else:
            print("  [OK]")
    print(f"\n{'ALL OK' if fails == 0 else f'{fails} FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
