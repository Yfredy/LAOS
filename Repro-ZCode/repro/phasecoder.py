"""PhaseCoder 几何无关空间音频编码（来源②）——numpy 精确移植。

移植自 google-deepmind/phasecoder（Apache-2.0）phasecoder_jax/：
- phasecoder_model.py::mpe_modulation / arbitrary_mic_geometry_embeddings /
  convert_mics_to_spherical_coordinates —— 麦克风位置编码（MPE），
  基于 GI-DOAEnet 论文（IEEE 11027482）Eq.2-3：
      v = (4/d)·arange(d/4)                       d=embedding_dim
      相位调制: [cos(2πβv+θ), sin(2πβv+θ), cos(2πβv+φ), sin(2πβv+φ)]
      频率调制: [cos(θβv), sin(θβv), cos(φβv), sin(φβv)]
      MPE = α·r·p_c                              α=7, β=4
  θ=elevation=acos(z/r)、φ=azimuth=atan2(y,x)，均相对阵列质心。
- utils.py::get_mag_phase_features —— STFT（窗 256/步 128）幅度+原始相位，
  (frames, 129, 2C) 布局：前 C 通道幅度、后 C 通道相位。
- 模型 patch 化（phasecoder_model.py::__call__）：token = (帧, 麦) 对，
  特征 [mag(129) | phase(129)] = 258 维（comb_size_single_mic）。
JAX 缺失不装包——数学与布局逐行对齐，行为等价（JAX stft 的帧对齐
按 noverlap 语义：nperseg=256, noverlap=128 → hop=128，与本文一致）。
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

EMBEDDING_DIM = 256
ALPHA = 7.0
BETA = 4.0
WINDOW_SIZE = 256
HOP_SIZE = 128


def find_centroid(mics: np.ndarray) -> np.ndarray:
    return mics.mean(axis=0)


def spherical_from_cartesian(mics: np.ndarray):
    """质心相对球坐标 (r, theta=elevation=acos(z/r), phi=azimuth=atan2(y,x))。"""
    rel = mics - find_centroid(mics)
    r = np.linalg.norm(rel, axis=1)
    theta = np.arccos(np.divide(rel[:, 2], r, where=r > 0,
                                out=np.zeros_like(r)))
    phi = np.arctan2(rel[:, 1], rel[:, 0])
    return r, theta, phi


def mpe_modulation(r: float, theta: float, phi: float,
                   embedding_dim: int = EMBEDDING_DIM,
                   alpha: float = ALPHA, beta: float = BETA,
                   modulation_type: str = "phase_modulation") -> np.ndarray:
    """麦克风位置编码（源码 mpe_modulation 精确移植）。"""
    if embedding_dim % 4 != 0:
        raise ValueError(f"embedding_dim must be divisible by 4, got {embedding_dim}")
    v = (4 / embedding_dim) * np.arange(embedding_dim / 4)
    if modulation_type == "phase_modulation":
        elevation_cos = np.cos(2 * np.pi * beta * v + theta)
        elevation_sin = np.sin(2 * np.pi * beta * v + theta)
        azimuth_cos = np.cos(2 * np.pi * beta * v + phi)
        azimuth_sin = np.sin(2 * np.pi * beta * v + phi)
    elif modulation_type == "frequency_modulation":
        elevation_cos = np.cos(theta * beta * v)
        elevation_sin = np.sin(theta * beta * v)
        azimuth_cos = np.cos(phi * beta * v)
        azimuth_sin = np.sin(phi * beta * v)
    else:
        raise ValueError(f"Unsupported modulation type: {modulation_type}")
    p_c = np.concatenate((elevation_cos, elevation_sin, azimuth_cos, azimuth_sin))
    return alpha * r * p_c


def arbitrary_mic_geometry_embeddings(
        mics_coord_cartesian: np.ndarray,
        embedding_dim: int = EMBEDDING_DIM,
        position_modulation_type: str = "phase_modulation") -> np.ndarray:
    """任意麦位 → MPE (num_mics, embedding_dim)（源码同名函数移植）。"""
    r, theta, phi = spherical_from_cartesian(mics_coord_cartesian)
    out = np.zeros((len(r), embedding_dim))
    for i in range(len(r)):
        out[i] = mpe_modulation(r[i], theta[i], phi[i], embedding_dim,
                                modulation_type=position_modulation_type)
    return out


def mag_phase_features(x: np.ndarray, fs: int,
                       window_size: int = WINDOW_SIZE,
                       hop_size: int = HOP_SIZE) -> np.ndarray:
    """多通道音频 → (frames, window_size//2+1, 2C)：前 C 幅度、后 C 相位。

    源码 get_mag_phase_features 布局：(batch, frames, fft, 2·mics)。
    """
    xc = np.atleast_2d(np.asarray(x, dtype=np.float64))
    if xc.shape[0] > xc.shape[1]:               # (N, C) → (C, N)
        xc = xc.T
    C, N = xc.shape
    frames = sliding_window_view(xc, window_size, axis=1)[:, ::hop_size]
    win = np.hanning(window_size + 1)[:window_size]
    spec = np.fft.rfft(frames * win, n=window_size, axis=-1)   # (C, T, F)
    mag = np.abs(spec).transpose(1, 2, 0)                       # (T, F, C)
    phase = np.angle(spec).transpose(1, 2, 0)
    return np.concatenate([mag, phase], axis=-1)               # (T, F, 2C)


def tokenize_patches(mag_phase: np.ndarray) -> np.ndarray:
    """(frames, F, 2C) → (frames·C, 2F)：每 token = (帧,麦) 的 [mag|phase]。

    源码 __call__ 的补丁化：split 通道维为 mag/phase，特征维拼接后按
    (帧×麦) 展平——token 特征 = comb_size_single_mic = 2·(window//2+1)。
    """
    frames, F, two_c = mag_phase.shape
    C = two_c // 2
    mags, phases = mag_phase[:, :, :C], mag_phase[:, :, C:]
    merged = np.concatenate([mags, phases], axis=1)            # (T, 2F, C)
    tokens = merged.transpose(0, 2, 1).reshape(frames * C, 2 * F)
    return tokens


def output_heads_meta() -> dict:
    """输出头与超参口径（model_hparams.py + README 实测）。"""
    return {
        "azimuth": 38,          # 10°×36 + 无源
        "distance": 13,         # 0.1-6.0m + 无源
        "elevation": 18,
        "embedding": 256,
        "window_size": WINDOW_SIZE,
        "hop_size": HOP_SIZE,
        "num_blocks": 5,
        "num_heads": 4,
        "ff_dim": 256,
        "num_cls_tokens": 1,
    }
