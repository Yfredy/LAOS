# tests/test_apps.py
"""drv_apps —— 应用管理驱动（mobile-mcp 采纳：apps.list/launch/close）。

    python -m pytest tests/test_apps.py -q

策略与 test_screen 相同：FakeAdb 注入，无需真机；内核 pkg 闸门用真驱动
子进程验证（越界在闸门被拒，不触 adb）。
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

from laos.context import ContextManager  # noqa: E402
from screen_adb import Adb  # noqa: E402


class FakeAdb(Adb):
    def __init__(self, responses=None):
        super().__init__(adb_path="fake-adb")
        self.responses = responses or {}
        self.calls = []

    def _run(self, args, timeout=30.0):
        self.calls.append(args)
        key = " ".join(args)
        for pattern, out in self.responses.items():
            if pattern in key:
                return 0, out
        return 0, ""


PM_LIST = ("package:com.timnet.lpai\npackage:com.android.settings\n"
           "package:com.example.game\n")


class TestDrvApps(unittest.TestCase):
    def setUp(self):
        import drv_apps
        self.drv = drv_apps
        self.fake = FakeAdb(responses={"pm list packages": PM_LIST})
        drv_apps.set_adb(self.fake)

    def tearDown(self):
        self.drv.set_adb(None)

    def test_list_parses_packages(self):
        import json
        out = self.drv.apps_list()
        data = json.loads(out)
        self.assertEqual(data["packages"],
                         ["com.timnet.lpai", "com.android.settings", "com.example.game"])

    def test_launch_uses_monkey_launcher(self):
        out = self.drv.apps_launch("com.timnet.lpai")
        self.assertIn("OK", out)
        self.assertIn(["shell", "monkey", "-p", "com.timnet.lpai",
                       "-c", "android.intent.category.LAUNCHER", "1"],
                      self.fake.calls)

    def test_launch_rejects_suspicious_pkg_chars(self):
        with self.assertRaises(ValueError):
            self.drv.apps_launch("com.evil;rm -rf /")
        with self.assertRaises(ValueError):
            self.drv.apps_launch("")

    def test_close_uses_force_stop(self):
        out = self.drv.apps_close("com.example.game")
        self.assertIn("OK", out)
        self.assertIn(["shell", "am", "force-stop", "com.example.game"],
                      self.fake.calls)


class TestKernelPkgScopeApps(unittest.TestCase):
    """内核 pkg 闸门对 apps.* 生效（越界拒绝在闸门，不触 adb）。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        from laos.kernel import AgentKernel
        self.kernel = AgentKernel(Path(self._td.name) / "var", confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver(
            "apps", [sys.executable, str(REPO / "drivers" / "drv_apps.py")], env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        return self.kernel.spawn(name="a", caps=["apps.*"], ctx=ctx, branch="main",
                                 task_scope=["pkg:com.allowed"])

    def test_launch_outside_scope_denied(self):
        pcb = self._spawn()
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "apps.launch", {"pkg": "com.denied"}))
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_close_outside_scope_denied(self):
        pcb = self._spawn()
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "apps.close", {"pkg": "com.denied"}))
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_launch_in_scope_passes_gate(self):
        pcb = self._spawn()
        res = asyncio.run(self.kernel.syscall(
            pcb.pid, "apps.launch", {"pkg": "com.allowed"}))
        # 闸门放行（后续 adb 在本机失败，但绝不是 task_scope 拒绝）
        self.assertNotIn("outside task scope", res.error or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
