"""镜像源法（ISM）房间仿真测试（来源①：arXiv 2607.02129v1 §3.1）。

论文口径：房间 [3,12]×[3,12]×[2,6] m、吸收 0.2-0.6、声源/阵列均匀采样、
高 1.5 m、6 麦 r=4.5cm 环形阵 60° 间隔、阶次 20（本复现默认 6，等比缩距）。
"""
import numpy as np

from repro.sho.ism import circular_array, rir_ism, sample_room, simulate_multichannel

FS = 16000
C = 343.0


def test_circular_array_geometry():
    m = circular_array(6, 0.045)
    assert m.shape == (6, 3)
    assert np.allclose(np.linalg.norm(m[:, :2], axis=1), 0.045)
    assert np.allclose(m[:, 2], 0.0)
    ang = np.sort(np.degrees(np.arctan2(m[:, 1], m[:, 0])) % 360)
    assert np.allclose(np.diff(ang), 60.0, atol=1e-9)


def test_anechoic_rir_is_direct_path_only():
    src, mic = np.array([2.0, 2.0, 1.5]), np.array([3.0, 2.0, 1.5])
    rir = rir_ism((4, 4, 3), src, mic, FS, absorption=0.99, max_order=0, rir_len=2048)
    d = float(np.linalg.norm(src - mic))
    peak = int(np.argmax(rir))
    assert abs(peak - d / C * FS) <= 1.5
    # 线性插值把直达脉冲劈到相邻两 tap——窗口内幅度守恒
    assert np.isclose(np.sum(rir[max(peak - 2, 0) : peak + 3]), 1 / (4 * np.pi * d),
                      rtol=0.05)
    rir[max(peak - 3, 0) : peak + 4] = 0
    assert np.sum(rir ** 2) < (1 / (4 * np.pi * d)) ** 2 * 0.05


def test_more_reflections_more_energy_lower_absorption():
    common = dict(room=(5, 4, 3), src=np.array([2.0, 2.0, 1.5]),
                  mic=np.array([3.5, 2.8, 1.5]), fs=FS, rir_len=4096)
    e_rev = np.sum(rir_ism(absorption=0.25, max_order=4, **common) ** 2)
    e_abs = np.sum(rir_ism(absorption=0.55, max_order=4, **common) ** 2)
    assert e_rev > e_abs * 1.5


def test_direct_path_position_moves_with_mic():
    src = np.array([2.0, 2.0, 1.5])
    for mic in (np.array([2.5, 2.0, 1.5]), np.array([2.0, 3.0, 1.5])):
        rir = rir_ism((4, 4, 3), src, mic, FS, 0.9, max_order=0, rir_len=2048)
        d = float(np.linalg.norm(src - mic))
        assert abs(int(np.argmax(rir)) - d / C * FS) <= 1.5


def test_sample_room_paper_ranges():
    rng = np.random.default_rng(42)
    r = sample_room(rng)
    for i, lo, hi in ((0, 3, 12), (1, 3, 12), (2, 2, 6)):
        assert lo <= r["room"][i] <= hi
    assert 0.2 <= r["absorption"] <= 0.6
    assert r["src"][2] == 1.5 and r["array_center"][2] == 1.5
    assert 0 <= r["orientation_deg"] < 360
    assert r["mics"].shape == (6, 3)
    # 声源与阵列都在房间内
    for key in ("src", "array_center"):
        p = r[key]
        assert all(0.2 < p[i] < r["room"][i] - 0.2 for i in range(3))


def test_rir_reproducible_with_seed_free_interface():
    a = rir_ism((5, 4, 3), np.array([2.0, 2.0, 1.5]), np.array([3.0, 2.0, 1.5]),
                FS, 0.4, max_order=3, rir_len=2048)
    b = rir_ism((5, 4, 3), np.array([2.0, 2.0, 1.5]), np.array([3.0, 2.0, 1.5]),
                FS, 0.4, max_order=3, rir_len=2048)
    assert np.array_equal(a, b)


def test_simulate_multichannel_shape_and_delay():
    rng = np.random.default_rng(1)
    speech = rng.standard_normal(16000) * 0.1
    rd = sample_room(rng)
    y = simulate_multichannel(speech, rd, FS, max_order=2)
    assert y.shape[0] == 6 and y.shape[1] >= 16000
    # 各通道到达时间与到阵列中心距离单调一致（近的麦先到）
    d_center = np.linalg.norm(rd["mics"] - rd["src"], axis=1)
    first_idx = [int(np.argmax(np.abs(ch) > 0.002 * np.max(np.abs(y)))) for ch in y]
    corr = np.corrcoef(d_center, first_idx)[0, 1]
    assert corr > 0.8


def test_directivity_front_mic_gets_more_energy():
    """指向性加上后：朝向侧麦收能量 > 背向侧麦（消声、同距）。"""
    src = np.array([2.0, 2.0, 1.5])
    d = 1.0
    front = src + np.array([d, 0, 0])          # 声源朝 +x
    back = src + np.array([-d, 0, 0])
    kw = dict(room=(4, 4, 3), fs=FS, absorption=0.9, max_order=0, rir_len=2048,
              orientation_rad=0.0, directivity=(0.3, 0.7))
    e_front = np.sum(rir_ism(src=src, mic=front, **kw) ** 2)
    e_back = np.sum(rir_ism(src=src, mic=back, **kw) ** 2)
    assert e_front > e_back * 2.0
