"""laos.micgeom —— 麦克风阵列几何约定与 MPE 位置编码（纯 stdlib）。

来源：采纳书 D 项（docs/research/2026-10-05-repro-adoption.md）。
数值实现与 zones/Repro-ZCode/repro/phasecoder.py 逐行同源——后者对齐了
google-deepmind/phasecoder 的 JAX 源码（GI-DOAEnet 论文 Eq.2-3）。

约定（laos 外挂音频驱动的麦位元数据口径）：
- 坐标：`(M, 3)` 笛卡尔米制，相对阵列质心，z 向上
- 球坐标：r 距离 / theta=elevation=acos(z/r) / phi=azimuth=atan2(y,x)
- MPE：v=(4/d)·arange(d/4)；相位调制 [cos,sin](2πβv+θ) ⊕ [cos,sin](2πβv+φ)；
  频率调制 [cos,sin](θβv) ⊕ [cos,sin](φβv)；幅度 α·r（α=7, β=4, d=256）
"""
from __future__ import annotations

import math

EMBEDDING_DIM = 256
ALPHA = 7.0
BETA = 4.0


def spherical_from_cartesian(mics: list[list[float]]):
    """质心相对球坐标 → (r 列表, theta 列表, phi 列表)。"""
    n = len(mics)
    cx = sum(p[0] for p in mics) / n
    cy = sum(p[1] for p in mics) / n
    cz = sum(p[2] for p in mics) / n
    r, theta, phi = [], [], []
    for p in mics:
        x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
        d = math.sqrt(x * x + y * y + z * z)
        r.append(d)
        theta.append(math.acos(z / d) if d > 0 else 0.0)
        phi.append(math.atan2(y, x))
    return r, theta, phi


def mpe_modulation(r: float, theta: float, phi: float,
                   embedding_dim: int = EMBEDDING_DIM,
                   alpha: float = ALPHA, beta: float = BETA,
                   modulation_type: str = "phase_modulation") -> list[float]:
    """麦克风位置编码（MPE）→ embedding_dim 维向量。"""
    if embedding_dim % 4 != 0:
        raise ValueError(f"embedding_dim must be divisible by 4, got {embedding_dim}")
    v = [(4 / embedding_dim) * k for k in range(embedding_dim // 4)]
    if modulation_type == "phase_modulation":
        parts = []
        for t in (theta, phi):
            parts.append([math.cos(2 * math.pi * beta * x + t) for x in v])
            parts.append([math.sin(2 * math.pi * beta * x + t) for x in v])
    elif modulation_type == "frequency_modulation":
        parts = []
        for t in (theta, phi):
            parts.append([math.cos(t * beta * x) for x in v])
            parts.append([math.sin(t * beta * x) for x in v])
    else:
        raise ValueError(f"Unsupported modulation type: {modulation_type}")
    p_c = parts[0] + parts[1] + parts[2] + parts[3]
    return [alpha * r * x for x in p_c]


def mic_geometry_embedding(mics: list[list[float]],
                           embedding_dim: int = EMBEDDING_DIM,
                           modulation_type: str = "phase_modulation") -> list[list[float]]:
    """任意麦位 → (M, embedding_dim) MPE 矩阵。"""
    r, theta, phi = spherical_from_cartesian(mics)
    return [mpe_modulation(r[i], theta[i], phi[i], embedding_dim,
                           modulation_type=modulation_type)
            for i in range(len(mics))]
