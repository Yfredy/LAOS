# tests/test_enforcement.py
"""enforcement OSAL 层测试：select 工厂 / 后端契约 / Android 报告 / 显式覆盖。

只测新面——既有 Sandbox 行为由 test_sandbox / test_seccomp 全量守护。

    python -m unittest tests.test_enforcement -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.enforcement import (  # noqa: E402
    AndroidBackend,
    LinuxBackend,
    StubBackend,
    select,
)
from laos.sandbox import Sandbox  # noqa: E402

_WD = Path(".")


class TestEnforcement(unittest.TestCase):
    def test_select_auto_by_platform(self):
        # auto：按 sys.platform 三态选后端
        for plat, cls in (("linux", LinuxBackend),
                          ("android", AndroidBackend),
                          ("win32", StubBackend)):
            with mock.patch("sys.platform", plat):
                backend = select(True, "off", _WD)
            self.assertIsInstance(backend, cls, plat)

    def test_select_explicit_override(self):
        # LAOS_ENFORCEMENT=stub：任何宿主都强制 StubBackend
        self.assertIsInstance(select(True, "off", _WD, override="stub"), StubBackend)
        with mock.patch.dict(os.environ, {"LAOS_ENFORCEMENT": "stub"}):
            self.assertIsInstance(Sandbox(enabled=True)._backend, StubBackend)
        # LAOS_ENFORCEMENT=linux：Linux 宿主拿真后端（skipUnless Linux）；
        # 其他宿主尊重选择但降级 stub，原因可读
        if sys.platform == "linux":
            with mock.patch.dict(os.environ, {"LAOS_ENFORCEMENT": "linux"}):
                self.assertIsInstance(Sandbox(enabled=True)._backend, LinuxBackend)
            self.assertIsInstance(select(True, "off", _WD, override="linux"), LinuxBackend)
        else:
            bk = select(True, "off", _WD, override="linux")
            self.assertIsInstance(bk, StubBackend)
            self.assertIn("降级 stub", " ".join(bk.report.reasons))

    def test_android_backend_reports_termux_notes(self):
        backend = AndroidBackend(True, "off", _WD)
        self.assertEqual(backend.name, "android")
        self.assertIn("Termux", " ".join(backend.report.reasons))

    def test_invalid_override_falls_back_auto(self):
        backend = select(True, "off", _WD, override="bogus")
        auto = select(True, "off", _WD)  # 同宿主的 auto 结果
        self.assertIsInstance(backend, type(auto))
        self.assertIn("bogus", " ".join(backend.report.reasons))

    def test_sandbox_delegates_to_backend(self):
        sb = Sandbox(enabled=True)
        self.assertEqual(sb.report, sb._backend.report)
        self.assertEqual(sb.seccomp_mode, sb._backend.seccomp_mode)
        self.assertIs(sb._seccomp_prog, sb._backend._seccomp_prog)
        self.assertEqual(sb.wrap(["echo", "hi"]), sb._backend.wrap(["echo", "hi"]))
        self.assertEqual(sb.estimate(), sb._backend.estimate())
        expected_name = {"linux": "linux", "android": "android"}.get(
            sys.platform, "stub")
        self.assertEqual(sb._backend.name, expected_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
