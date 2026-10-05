# tests/test_foa.py
"""laos.foa —— 一阶 Ambisonics 编解码基础件（纯 stdlib）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_foa -v

来源：Bin2Ambi（arXiv 2609.39732，双耳+头动→FOA 新任务）与 RMS-AQA
（arXiv 2610.00935，FOA 问答基准）都把 FOA 当通用空间中间格式——本模块
是 laos 侧的格式地基（平面波编码 / 四角扬声器解码 / ACN 通道序），学习式
转换属远期驱动子进程。

坐标：az 方位角（水平面、x 轴起、逆时针为正）、el 仰角（上为正），单位度。
解码幅度律：gain_i = max(0, W + u_i·XYZ)，按最大增益归一——W 全向通道对
所有扬声器都有贡献，故"正对声源的扬声器最大、正对侧为零"而非"独占"。
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.foa import N3D_GAIN, acn_index, decode_quad, plane_wave  # noqa: E402


class TestPlaneWave(unittest.TestCase):
    def test_front_is_w_plus_x(self):
        self.assertEqual(plane_wave(0.0, 0.0), (1.0, 1.0, 0.0, 0.0))

    def test_left_is_w_plus_y(self):
        w, x, y, z = plane_wave(90.0, 0.0)
        self.assertAlmostEqual(w, 1.0)
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 1.0)
        self.assertAlmostEqual(z, 0.0, places=12)

    def test_zenith_is_w_plus_z(self):
        w, x, y, z = plane_wave(0.0, 90.0)
        self.assertAlmostEqual(w, 1.0)
        self.assertAlmostEqual(x, 0.0, places=12)
        self.assertAlmostEqual(y, 0.0, places=12)
        self.assertAlmostEqual(z, 1.0)

    def test_n3d_scales_xyz_by_sqrt3_w_unchanged(self):
        w, x, y, z = plane_wave(45.0, 30.0, norm="n3d")
        ws, xs, ys, zs = plane_wave(45.0, 30.0, norm="sn3d")
        self.assertEqual(w, ws)
        self.assertAlmostEqual(x, N3D_GAIN * xs)
        self.assertAlmostEqual(y, N3D_GAIN * ys)
        self.assertAlmostEqual(z, N3D_GAIN * zs)
        self.assertAlmostEqual(N3D_GAIN, math.sqrt(3.0))

    def test_bad_norm_raises(self):
        with self.assertRaises(ValueError):
            plane_wave(0.0, 0.0, norm="maxre")


class TestDecodeQuad(unittest.TestCase):
    def test_source_direction_loudest_opposite_silent(self):
        wxyz = plane_wave(45.0, 0.0)   # 指向首扬声器（az=45°）
        gains = decode_quad(wxyz)
        self.assertAlmostEqual(max(gains), gains[0])
        self.assertAlmostEqual(gains[0], 1.0)   # 归一化后最大增益为 1
        self.assertAlmostEqual(gains[2], 0.0)   # 正对侧（az=225°）无声
        self.assertAlmostEqual(gains[1], 0.5)   # 相邻角 = W 的一半贡献
        self.assertAlmostEqual(gains[3], 0.5)

    def test_opposite_direction_rotates(self):
        gains = decode_quad(plane_wave(225.0, 0.0))
        self.assertAlmostEqual(max(gains), gains[2])


class TestACN(unittest.TestCase):
    def test_acn_order_first_degree(self):
        # ACN 一阶序：W→0、(1,-1)=Y→1、(1,0)=Z→2、(1,1)=X→3
        self.assertEqual([acn_index(l, m) for l, m in
                          [(0, 0), (1, -1), (1, 0), (1, 1)]], [0, 1, 2, 3])
        self.assertEqual(acn_index(2, 2), 8)   # 二阶末通道

    def test_acn_rejects_bad_degree_order(self):
        with self.assertRaises(ValueError):
            acn_index(1, 2)   # |m| > l
        with self.assertRaises(ValueError):
            acn_index(-1, 0)  # l < 0


if __name__ == "__main__":
    unittest.main(verbosity=2)
