"""laos.foa —— 一阶 Ambisonics（FOA）编解码基础件（纯 stdlib）。

来源：Bin2Ambi（arXiv 2609.39732）把 FOA 定为消费级空间录音的目标格式、
RMS-AQA（arXiv 2610.00935）的基准数据全是 FOA——两个方向都把 FOA 当通用
空间中间表示。本模块是 laos 侧的格式地基：平面波编码、四角扬声器解码、
ACN 通道序。学习式转换（双耳→FOA 模型）属远期驱动子进程，不进核心。

约定（AmbiX 惯例）：
- 本模块元组序 (W, X, Y, Z)：W 全向，X 前，Y 左，Z 上（B-format/XYZ 序）；
- SN3D 归一（默认）：平面波 W=1，(X,Y,Z)=方向单位向量；
- N3D：XYZ 再乘 √3（W 不变）——l 阶增益 √(2l+1)；
- ACN 通道序 index = l(l+1)+m：一阶三通道为 (1,-1)=Y→1、(1,0)=Z→2、(1,1)=X→3，
  即 ACN 数组序是 (W, Y, Z, X)——与本模块元组序经换序对应。

解码幅度律：gain_i = max(0, W + u_i·XYZ)，按最大增益归一。W 全向通道
贡献到每个扬声器，因此正对声源的扬声器增益最大、正对侧为零（1 : 0.5 : 0
: 0.5），不是"独占"。
"""
from __future__ import annotations

import math

__all__ = ["N3D_GAIN", "plane_wave", "decode_quad", "acn_index"]

N3D_GAIN = math.sqrt(3.0)  # SN3D → N3D：一阶 XYZ 通道增益

# 四角扬声器布局（az°，el=0）：右前、左前、左后、右后
_QUAD_AZ = (45.0, 135.0, 225.0, 315.0)


def plane_wave(az_deg: float, el_deg: float,
               norm: str = "sn3d") -> tuple[float, float, float, float]:
    """平面波 FOA 编码 → (W, X, Y, Z)。az 逆时针为正（90°=左），el 上为正。"""
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    x = math.cos(el) * math.cos(az)
    y = math.cos(el) * math.sin(az)
    z = math.sin(el)
    if norm == "sn3d":
        return (1.0, x, y, z)
    if norm == "n3d":
        return (1.0, N3D_GAIN * x, N3D_GAIN * y, N3D_GAIN * z)
    raise ValueError(f"norm must be 'sn3d' or 'n3d', got {norm!r}")


def decode_quad(wxyz: tuple[float, ...]) -> list[float]:
    """FOA → 四角扬声器增益（负增益截 0，按最大增益归一）。"""
    if len(wxyz) != 4:
        raise ValueError(f"expected 4 FOA channels (W,X,Y,Z), got {len(wxyz)}")
    w, x, y, _z = wxyz          # 四角布局 el=0，Z 分量不参与
    gains = []
    for az_deg in _QUAD_AZ:
        az = math.radians(az_deg)
        gains.append(max(0.0, w + x * math.cos(az) + y * math.sin(az)))
    peak = max(gains)
    if peak <= 0.0:
        return [0.0, 0.0, 0.0, 0.0]
    return [g / peak for g in gains]


def acn_index(l: int, m: int) -> int:
    """ACN 通道序号 = l(l+1)+m；要求 l ≥ 0 且 -l ≤ m ≤ l。"""
    if l < 0 or abs(m) > l:
        raise ValueError(f"invalid (l, m) = ({l}, {m})")
    return l * (l + 1) + m
