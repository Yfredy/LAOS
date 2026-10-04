"""Allen-Berkley 镜像源法（ISM）房间仿真（来源①：arXiv 2607.02129v1 §3.1）。

论文用 Pyroomacoustics（阶次 20、RT60≈0.85s）；本复现自研向量化 ISM
（环境红线：不安装新包）。公式（Allen & Berkley 1979）：

    镜像源位置（逐墙翻转）：
      x + 2 q Lx（q∈ℤ，Lx 房间 x 边长），y/z 同理
    每镜像到麦距离 d = |img - mic|，幅度 = R^(|i|+|j|+|k|) / (4πd)
    （R = √(1-α) 为能量→幅度反射系数）
    延迟 τ = d/c，分数延迟用线性插值

声源指向性（cardioid 族）由 speech.py 的调用方在源信号上按镜像方向加权——
本模块只管无指向性传播；朝向信息在 sample_room() 的 orientation_deg 里。
"""
from __future__ import annotations

import numpy as np

C_SOUND = 343.0


def circular_array(n_mics: int, radius_m: float) -> np.ndarray:
    """xy 平面均匀圆阵（麦克风朝上 z=0 相对中心），0° 起逆时针。"""
    ang = 2 * np.pi * np.arange(n_mics) / n_mics
    return np.stack([radius_m * np.cos(ang), radius_m * np.sin(ang),
                     np.zeros(n_mics)], axis=-1)


def rt60_sabine(room: tuple[float, float, float], absorption: float) -> float:
    """Sabine 混响时间（对照口径，非仿真输出）。"""
    V = room[0] * room[1] * room[2]
    S = 2 * (room[0] * room[1] + room[1] * room[2] + room[0] * room[2])
    return 0.161 * V / (S * absorption)


def rir_ism(room: tuple[float, float, float], src: np.ndarray, mic: np.ndarray,
            fs: float, absorption: float, max_order: int,
            rir_len: int | None = None) -> np.ndarray:
    """单源单麦 RIR。镜像阶数截到 max_order，能量反射系数 R=√(1-α)。"""
    Lx, Ly, Lz = room
    R = np.sqrt(1.0 - absorption)
    if rir_len is None:
        rir_len = int(0.3 * fs)

    rir = np.zeros(rir_len)
    idx_range = np.arange(-max_order, max_order + 1)
    for i in idx_range:
        img_x = _mirror(src[0], int(i), Lx)
        for j in idx_range:
            img_y = _mirror(src[1], int(j), Ly)
            for k in idx_range:
                img_z = _mirror(src[2], int(k), Lz)
                order = abs(i) + abs(j) + abs(k)
                if order > max_order:
                    continue
                img = np.array([img_x, img_y, img_z])
                d = float(np.linalg.norm(img - mic))
                amp = (R ** order) / (4 * np.pi * d)
                delay = d / C_SOUND * fs
                base = int(np.floor(delay))
                frac = delay - base
                if base >= rir_len:
                    continue
                w1 = amp * (1 - frac)
                rir[base] += w1
                if base + 1 < rir_len:
                    rir[base + 1] += amp * frac
    return rir


def _mirror(x: float, i: int, L: float) -> float:
    """镜像坐标：i 偶 → x + 2iL；i 奇 → -x + 2iL。"""
    return (x if i % 2 == 0 else -x) + 2 * i * L


def sample_room(rng: np.random.Generator) -> dict:
    """论文 §3.1 区间采样一个场景（含朝向角与 6 麦阵）。"""
    room = (rng.uniform(3, 12), rng.uniform(3, 12), rng.uniform(2, 6))
    absorption = rng.uniform(0.2, 0.6)
    src = np.array([rng.uniform(0.5, room[0] - 0.5),
                    rng.uniform(0.5, room[1] - 0.5), 1.5])
    center = np.array([rng.uniform(0.5, room[0] - 0.5),
                       rng.uniform(0.5, room[1] - 0.5), 1.5])
    # 声源与阵列中心至少隔 0.8 m（避免贴脸）
    for _ in range(50):
        if np.linalg.norm(src - center) > 0.8:
            break
        center = np.array([rng.uniform(0.5, room[0] - 0.5),
                           rng.uniform(0.5, room[1] - 0.5), 1.5])
    return {
        "room": room,
        "absorption": absorption,
        "src": src,
        "array_center": center,
        "mics": center + circular_array(6, 0.045),
        "orientation_deg": rng.uniform(0, 360),
    }


def simulate_multichannel(speech: np.ndarray, room_dict: dict, fs: float,
                          max_order: int = 6) -> np.ndarray:
    """对每麦克风生成 RIR 后与语音卷积。返回 (C, N+rir_len-1)。"""
    n_mic = room_dict["mics"].shape[0]
    out = np.zeros((n_mic, len(speech)))
    for m in range(n_mic):
        rir = rir_ism(room_dict["room"], room_dict["src"], room_dict["mics"][m],
                      fs, room_dict["absorption"], max_order)
        out[m] = np.convolve(speech, rir)[: len(speech)]
    return out
