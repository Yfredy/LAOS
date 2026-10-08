"""PhaseCoder 几何无关编码复现测试（来源②：google-deepmind/phasecoder JAX 源码精确移植）。

源码依据（var/phasecoder-src/phasecoder_jax/，Apache-2.0）：
- phasecoder_model.py::mpe_modulation / arbitrary_mic_geometry_embeddings
  （基于 GI-DOAEnet, IEEE 11027482, Eq.2-3）
- utils.py::get_mag_phase_features（STFT 幅度+原始相位，窗 256/步 128）
- model_hparams.py（az 38 / dist 13 / el 18 / embed 256 / 5 blocks / 4 heads）
"""
import numpy as np

from repro.phasecoder import (
    spherical_from_cartesian,
    mpe_modulation,
    arbitrary_mic_geometry_embeddings,
    mag_phase_features,
    tokenize_patches,
    output_heads_meta,
)
from repro.sho.ism import circular_array

FS = 16000


def test_spherical_centroid_relative():
    p = circular_array(6, 0.045)
    r, theta, phi = spherical_from_cartesian(p)
    assert np.allclose(r, 0.045, atol=1e-9)
    # 源码 theta = acos(z/r)：z=0 → π/2（colatitude 口径）
    assert np.allclose(theta, np.pi / 2, atol=1e-9)
    ang = np.sort(phi % (2 * np.pi))
    assert np.allclose(np.diff(ang), 2 * np.pi / 6, atol=1e-9)


def test_mpe_shape_and_r_zero():
    e = mpe_modulation(r=0.045, theta=np.pi / 2, phi=0.3)
    assert e.shape == (256,)
    assert np.allclose(mpe_modulation(0.0, 0.1, 0.2), 0.0)      # r=0 → 全零


def test_mpe_alpha_r_scaling():
    a = mpe_modulation(0.02, 0.5, 1.0)
    b = mpe_modulation(0.04, 0.5, 1.0)
    assert np.allclose(b, 2 * a, atol=1e-12)                    # α·r 线性


def test_mpe_modulation_types_differ():
    pm = mpe_modulation(0.05, 0.8, 1.2, modulation_type="phase_modulation")
    fm = mpe_modulation(0.05, 0.8, 1.2, modulation_type="frequency_modulation")
    assert not np.allclose(pm, fm)


def test_geometry_embedding_shape_var_mics():
    for M in (3, 5, 8):
        rng = np.random.default_rng(M)
        p = rng.uniform(-0.09, 0.09, (M, 3))
        e = arbitrary_mic_geometry_embeddings(p, embedding_dim=256)
        assert e.shape == (M, 256)


def test_rotation_invariance_as_set():
    """绕 z 轴旋转圆阵 = 麦序重排：每行编码在原集合中都有精确对应。"""
    p = circular_array(6, 0.045)
    ang = np.deg2rad(60.0)
    R = np.array([[np.cos(ang), -np.sin(ang), 0],
                  [np.sin(ang), np.cos(ang), 0], [0, 0, 1]])
    e1 = arbitrary_mic_geometry_embeddings(p, embedding_dim=256)
    e2 = arbitrary_mic_geometry_embeddings(p @ R.T, embedding_dim=256)
    used = set()
    for row in e2:
        d = np.abs(e1 - row).max(axis=1)
        j = int(np.argmin(d))
        assert d[j] < 1e-9 and j not in used
        used.add(j)
    assert len(used) == 6


def test_mag_phase_features_layout():
    x = np.random.default_rng(0).standard_normal((4, FS)).astype(np.float64)
    f = mag_phase_features(x, FS)
    frames = (FS - 256) // 128 + 1
    assert f.shape == (frames, 129, 8)          # (frames, fft bins, mag+phase × 4 mic)
    mag_block, phase_block = f[:, :, :4], f[:, :, 4:]
    assert np.all(mag_block >= 0)
    assert np.all(np.abs(phase_block) <= np.pi + 1e-9)


def test_tokenize_patches():
    x = np.random.default_rng(1).standard_normal((3, FS)).astype(np.float64)
    f = mag_phase_features(x, FS)
    tokens = tokenize_patches(f)
    frames = (FS - 256) // 128 + 1
    assert tokens.shape == (frames * 3, 2 * 129)   # 每 token = (帧,麦) 的 [mag|phase]


def test_heads_meta_matches_repo():
    h = output_heads_meta()
    assert h["azimuth"] == 38 and h["distance"] == 13 and h["elevation"] == 18
    assert h["embedding"] == 256
    assert h["window_size"] == 256 and h["hop_size"] == 128
    assert h["num_blocks"] == 5 and h["num_heads"] == 4
