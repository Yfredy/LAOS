"""强制隔离接入（补 AIOS 缺失的 L4）。

sandbox.wrap 把驱动启动命令包进 Linux unshare；非 Linux 或 disabled 时
原样返回（跨平台降级不报错）。estimate() 产出带 active 标记的探测报告。

    python -m unittest tests.test_sandbox -v
"""
from __future__ import annotations

import platform
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.sandbox import IsolationReport, Sandbox  # noqa: E402


class TestSandbox(unittest.TestCase):
    def test_wrap_downgrades_off_linux(self):
        sb = Sandbox(enabled=True)
        cmd = ["python", "-c", "print(1)"]
        if platform.system() != "Linux":
            self.assertEqual(sb.wrap(cmd), cmd)  # 跨平台降级：原样
        else:
            self.assertNotEqual(sb.wrap(cmd), cmd)  # Linux：包了 unshare

    def test_wrap_disabled_returns_verbatim(self):
        sb = Sandbox(enabled=False)
        cmd = ["python", "-c", "print(1)"]
        self.assertEqual(sb.wrap(cmd), cmd)

    def test_estimate_reports_active(self):
        rep = Sandbox(enabled=True).estimate()
        self.assertIsInstance(rep, IsolationReport)


if __name__ == "__main__":
    unittest.main()
