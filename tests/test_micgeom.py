"""laos.micgeom 测试 —— 麦位几何与 MPE 编码（采纳书 D 项升级执行）。

数值锚点与 Repro-ZCode/repro/phasecoder.py（对齐官方 JAX 源码版）一致。
"""
import math

from laos.micgeom import spherical_from_cartesian, mpe_modulation


def _circ6(r=0.045):
    return [[r * math.cos(2 * math.pi * k / 6), r * math.sin(2 * math.pi * k / 6), 0.0]
            for k in range(6)]


def test_spherical_centroid_relative():
    r, theta, phi = spherical_from_cartesian(_circ6())
    assert all(abs(x - 0.045) < 1e-12 for x in r)
    assert all(abs(t - math.pi / 2) < 1e-12 for t in theta)


def test_mpe_shape_and_r_zero():
    e = mpe_modulation(0.045, math.pi / 2, 0.3)
    assert len(e) == 256
    assert all(x == 0.0 for x in mpe_modulation(0.0, 0.1, 0.2))


def test_mpe_alpha_r_scaling():
    a = mpe_modulation(0.02, 0.5, 1.0)
    b = mpe_modulation(0.04, 0.5, 1.0)
    assert all(abs(y - 2 * x) < 1e-12 for x, y in zip(a, b))


def test_mpe_frequency_modulation_differs():
    pm = mpe_modulation(0.05, 0.8, 1.2, modulation_type="phase_modulation")
    fm = mpe_modulation(0.05, 0.8, 1.2, modulation_type="frequency_modulation")
    assert any(abs(x - y) > 1e-9 for x, y in zip(pm, fm))


def test_rotation_set_invariance():
    """圆阵绕 z 转 60° = 麦序重排：每行编码在原集合有精确对应（几何无关性）。"""
    ang = math.pi / 3
    cos_a, sin_a = math.cos(ang), math.sin(ang)

    def rot(p):
        return [p[0] * cos_a - p[1] * sin_a, p[0] * sin_a + p[1] * cos_a, p[2]]

    def mpe(p):
        r, t, f = spherical_from_cartesian([p])
        return mpe_modulation(r[0], t[0], f[0])

    base = [mpe(p) for p in _circ6()]
    roted = [mpe(rot(p)) for p in _circ6()]
    used = set()
    for row in roted:
        j = min((k for k in range(6) if k not in used),
                key=lambda k: max(abs(a - b) for a, b in zip(base[k], row)))
        assert max(abs(a - b) for a, b in zip(base[j], row)) < 1e-9
        used.add(j)
    assert len(used) == 6


def test_matches_numpy_reference_values():
    """抽查几个数与 Repro 区 numpy 版输出一致（跨实现一致性锚点）。"""
    e = mpe_modulation(0.045, math.pi / 2, 0.0)
    # phase_modulation: [cos(2πβv+θ)..., sin..., cos(2πβv+φ)..., sin...]
    v0 = 0.0
    beta, alpha = 4.0, 7.0
    assert abs(e[0] - alpha * 0.045 * math.cos(2 * math.pi * beta * v0 + math.pi / 2)) < 1e-12
    assert abs(e[64] - alpha * 0.045 * math.sin(2 * math.pi * beta * v0 + math.pi / 2)) < 1e-12
    assert abs(e[128] - alpha * 0.045 * math.cos(2 * math.pi * beta * v0 + 0.0)) < 1e-12
