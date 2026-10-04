"""ShoNet：论文 Fig.1 精确架构（arXiv 2607.02129v1）。

输入 (B, 2C, T, 128) 多通道 STFT 相位 sin/cos 特征：
  Conv2d(2C→64, 3×3, pad1)+ReLU+MaxPool(5×4)
  Conv2d(64→64, 3×3, pad1)+ReLU+MaxPool(1×4)
  Conv2d(64→64, 3×3, pad1)+ReLU+MaxPool(1×2)
  → 频率维 128/(4·4·2)=4 → reshape (B, T/5, 64×4=256)
  → BiGRU(128)×2 → (B, T/5, 128)
  → MHSA(8 头)+残差+LayerNorm ×2
  → AdaptiveMaxPool1d(1) → (B, 128) → FC 128 → FC 128→2 = (cosθ, sinθ)
输出 (cosθ, sinθ)；θ = atan2(sin,cos)·180/π mod 360（论文 §2 公式）。
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn


class _MHABlock(nn.Module):
    def __init__(self, d: int = 128, heads: int = 8):
        super().__init__()
        self.attn = nn.MultiheadAttention(d, heads, batch_first=True)
        self.norm = nn.LayerNorm(d)

    def forward(self, x):
        a, _ = self.attn(x, x, x, need_weights=False)
        return self.norm(x + a)


class ShoNet(nn.Module):
    def __init__(self, n_mics: int = 6):
        super().__init__()
        in_ch = 2 * n_mics
        self.conv = nn.Sequential(
            nn.Conv2d(in_ch, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d((5, 4)),
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d((1, 4)),
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d((1, 2)),
        )
        self.gru = nn.GRU(64 * 4, 128, num_layers=2, batch_first=True,
                          bidirectional=True)
        # BiGRU(128 双向) 输出 256 → 线性折回 128（论文口径"embeddings T/5×128"）
        self.proj = nn.Linear(256, 128)
        self.mha = nn.Sequential(_MHABlock(128, 8), _MHABlock(128, 8))
        self.pool = nn.AdaptiveMaxPool1d(1)
        self.fc = nn.Sequential(nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, 2))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b = x.shape[0]
        h = self.conv(x)                       # (B, 64, T/5, 4)
        t = h.shape[2]
        h = h.permute(0, 2, 1, 3).reshape(b, t, 64 * 4)
        h, _ = self.gru(h)                     # (B, T/5, 256)
        h = self.proj(h)                       # (B, T/5, 128)
        h = self.mha(h)
        h = self.pool(h.transpose(1, 2)).squeeze(-1)   # (B, 128)
        return self.fc(h)                      # (B, 2) = (cosθ, sinθ)


def predict_degrees(model: ShoNet, feats: np.ndarray) -> np.ndarray:
    """特征 (N, 2C, T, 128) → 角度（度，[0,360)）。"""
    model.eval()
    with torch.no_grad():
        y = model(torch.from_numpy(np.ascontiguousarray(feats))).numpy()
    deg = np.degrees(np.arctan2(y[:, 1], y[:, 0])) % 360.0
    return deg


class AngleDataset(torch.utils.data.Dataset):
    """(N, 2C, T, 128) 特征 + 角度（度）→ 训练样本（角度转弧度）。"""

    def __init__(self, feats: np.ndarray, angles_deg: np.ndarray):
        self.X = np.ascontiguousarray(feats, dtype=np.float32)
        self.Y = np.deg2rad(np.asarray(angles_deg, dtype=np.float32))

    def __len__(self):
        return len(self.Y)

    def __getitem__(self, i):
        return torch.from_numpy(self.X[i]), float(self.Y[i])
