"""端到端 SHO 复现实验：仿真 → 特征 → 训练 → 评测 → 指标 JSON + 分桶图。

论文口径（arXiv 2607.02129v1）：模拟 clean MAE 19.9°（40,295 语句×200k 步）。
本脚本默认冒烟规模（--n-utt 120 --iters 400），验证管线正确性而非复现数字。

用法：
    python scripts/run_sho_repro.py --n-utt 120 --iters 400 --max-order 4
产出：
    var/sho_metrics.json     train/holdout MAE、随机基线 90°、10° 分桶 MAE
    var/sho_mae_by_bin.png   分桶误差图（论文 Fig.2 形态）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from repro.sho.speech import synth_speech, oriented_room_dict
from repro.sho.ism import simulate_multichannel
from repro.sho.features import stft_phase_features, angular_mae
from repro.sho.model import ShoNet, predict_degrees


def build_dataset(n_utt: int, fs: int, dur_s: float, max_order: int, seed: int):
    import torch
    rng = np.random.default_rng(seed)
    feats, angs = [], []
    for _ in range(n_utt):
        s = synth_speech(dur_s, fs, rng)
        rd = oriented_room_dict(rng)
        y = simulate_multichannel(s, rd, fs, max_order=max_order)
        feats.append(stft_phase_features(y[:, : int(dur_s * fs)], fs))
        angs.append(rd["orientation_deg"])
    T = min(f.shape[1] for f in feats)
    X = np.stack([f[:, :T] for f in feats]).astype(np.float32)
    Y = np.array(angs, dtype=np.float32)
    n_train = int(0.8 * n_utt)
    return (X[:n_train], Y[:n_train]), (X[n_train:], Y[n_train:])


def train(Xtr, Ytr, iters: int, lr: float = 4e-4, batch: int = 16, seed: int = 7):
    import torch
    torch.manual_seed(seed)
    model = ShoNet(6)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.LinearLR(opt, 1.0, 0.1, total_iters=iters)
    rng = np.random.default_rng(seed)
    losses = []
    for step in range(iters):
        idx = rng.integers(0, len(Xtr), batch)
        xt = torch.from_numpy(Xtr[idx])
        th = torch.from_numpy(np.deg2rad(Ytr[idx]))
        yt = torch.stack([torch.cos(th), torch.sin(th)], -1)
        loss = torch.mean((model(xt) - yt) ** 2)
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        losses.append(float(loss))
    return model, losses


def mae_by_bin(true_deg, pred_deg, width_deg=10):
    bins = np.arange(0, 360, width_deg)
    rows = []
    for b in bins:
        m = (true_deg >= b) & (true_deg < b + width_deg)
        if m.sum() > 0:
            rows.append({"bin_deg": float(b), "n": int(m.sum()),
                         "mae": float(angular_mae(true_deg[m], pred_deg[m]))})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-utt", type=int, default=120)
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--dur", type=float, default=1.0)
    ap.add_argument("--max-order", type=int, default=4)
    ap.add_argument("--fs", type=int, default=16000)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    t0 = time.time()
    print(f"[1/3] 仿真 {args.n_utt} 语句（order {args.max_order}）…")
    (Xtr, Ytr), (Xho, Yho) = build_dataset(args.n_utt, args.fs, args.dur,
                                           args.max_order, args.seed)
    print(f"      特征 {Xtr.shape[1:]}，用时 {time.time()-t0:.0f}s")

    print(f"[2/3] 训练 {args.iters} 步（Adam 4e-4 线性衰减，MSE on cos/sin）…")
    model, losses = train(Xtr, Ytr, args.iters, seed=args.seed)
    tr_pred = predict_degrees(model, Xtr)
    print(f"      loss {losses[0]:.4f} → {losses[-1]:.4f}")

    print("[3/3] 评测…")
    ho_pred = predict_degrees(model, Xho)
    mae_tr = angular_mae(Ytr, tr_pred)
    mae_ho = angular_mae(Yho, ho_pred)
    bins = mae_by_bin(Yho, ho_pred)
    metrics = {
        "paper_ref": {"sim_clean_mae_deg": 19.9,
                      "personalized_best_mae_deg": 11.3,
                      "scale": "40295 utts x 200k iters"},
        "this_run": {"n_utt": args.n_utt, "iters": args.iters,
                     "max_order": args.max_order, "fs": args.fs,
                     "train_mae_deg": round(mae_tr, 2),
                     "holdout_mae_deg": round(mae_ho, 2),
                     "random_baseline_deg": 90.0,
                     "wall_s": round(time.time() - t0, 1)},
        "mae_by_bin": bins,
    }
    out = Path(__file__).resolve().parents[1] / "var"
    out.mkdir(exist_ok=True)
    (out / "sho_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"      train MAE {mae_tr:.1f}° / holdout MAE {mae_ho:.1f}°"
          f"（随机 90°，论文 19.9°）")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        centers = [r["bin_deg"] + 5 for r in bins]
        vals = [r["mae"] for r in bins]
        fig, ax = plt.subplots(figsize=(8, 3.2))
        ax.bar(centers, vals, width=8)
        ax.axhline(90, color="r", ls="--", lw=1, label="random 90°")
        ax.axhline(19.9, color="g", ls="--", lw=1, label="paper clean 19.9°")
        ax.set_xlabel("orientation bin (deg)")
        ax.set_ylabel("MAE (deg)")
        ax.set_title(f"SHO repro (smoke): holdout MAE {mae_ho:.1f}°")
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "sho_mae_by_bin.png", dpi=120)
        print(f"      分桶图 → var/sho_mae_by_bin.png")
    except Exception as e:                       # 图形环境缺失不致命
        print(f"      （跳过分桶图：{e}）")
    print(json.dumps(metrics["this_run"], ensure_ascii=False))


if __name__ == "__main__":
    main()
