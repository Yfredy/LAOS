# tests/test_screen.py
"""drv_screen —— 屏幕理解与操控（adb 通道，pkg 作用域）。

    python -m unittest tests.test_screen -v

测试策略：adb 交互全部经 `Adb` 传输类收口——测试用 FakeAdb 注入伪造输出，
无需真机；uiautomator XML 解析是纯函数，用真实形状的 fixture 直测。
真机手工验收见 docs/research/qnn-real-device-runbook.md。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

from laos.context import ContextManager  # noqa: E402
from screen_adb import Adb, parse_current_focus, parse_uiautomator_xml  # noqa: E402

FIXTURE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.timnet.lpai" content-desc="" checkable="false" checked="false" clickable="false" enabled="true" bounds="[0,0][720,1520]">
    <node index="0" text="Start Recording" resource-id="com.timnet.lpai:id/btnRecord" class="android.widget.Button" package="com.timnet.lpai" content-desc="" checkable="false" clickable="true" enabled="true" bounds="[40,1300][680,1420]"/>
    <node index="1" text="Ready - serving :8900" resource-id="com.timnet.lpai:id/tvStatus" class="android.widget.TextView" package="com.timnet.lpai" content-desc="" checkable="false" clickable="false" enabled="true" bounds="[40,200][680,260]"/>
  </node>
</hierarchy>"""

DUMPSYS_SAMPLE = """  Window #2 Window{5a3c2d u0 com.timnet.lpai/com.timnet.lpai.MainActivity} type=baseApplication
    mHasSurface=true isReadyForDisplay=true
  mCurrentFocus = Window{5a3c2d u0 com.timnet.lpai/com.timnet.lpai.MainActivity}
"""


class TestParseUiautomator(unittest.TestCase):
    def test_parses_nodes_fields(self):
        out = parse_uiautomator_xml(FIXTURE_XML)
        self.assertEqual(out["package"], "com.timnet.lpai")
        self.assertEqual(len(out["nodes"]), 2)
        btn = out["nodes"][0]
        self.assertEqual(btn["text"], "Start Recording")
        self.assertEqual(btn["resource_id"], "com.timnet.lpai:id/btnRecord")
        self.assertTrue(btn["clickable"])
        self.assertEqual(btn["bounds"], [40, 1300, 680, 1420])

    def test_bad_xml_raises_einval(self):
        with self.assertRaises(ValueError):
            parse_uiautomator_xml("not xml at all <<<")

    def test_parse_current_focus(self):
        self.assertEqual(parse_current_focus(DUMPSYS_SAMPLE), "com.timnet.lpai")
        self.assertIsNone(parse_current_focus("nothing here"))


class FakeAdb(Adb):
    """注入伪造输出的 Adb（不调任何真实进程）。"""

    def __init__(self, responses: dict[str, str] | None = None):
        super().__init__(adb_path="fake-adb")
        self.responses = responses or {}
        self.calls: list[list[str]] = []

    def _run(self, args, timeout=30.0):
        self.calls.append(args)
        key = " ".join(args)
        for pattern, out in self.responses.items():
            if pattern in key:
                return 0, out
        return 0, ""

    def exec_out(self, args, timeout=30.0) -> bytes:
        self.calls.append(args)
        key = " ".join(args)
        for pattern, out in self.responses.items():
            if pattern in key:
                return out.encode("utf-8")
        return b""


class TestAdbTransport(unittest.TestCase):
    def test_devices_parses_skipping_header(self):
        adb = FakeAdb()
        adb.responses = {}
        out = adb.devices.__wrapped__ if hasattr(adb.devices, "__wrapped__") else None
        # 直接测解析逻辑：devices 内部用 _run 的输出——改用注入法
        adb2 = FakeAdb()
        adb2._run = lambda args, timeout=30.0: (
            0, "List of devices attached\n\tabc123\tdevice\n\tde456\tunauthorized\n")
        self.assertEqual(adb2.devices(), ["abc123"])  # unauthorized 不算可用

    def test_shell_raises_on_rc(self):
        adb = FakeAdb()
        adb._run = lambda args, timeout=30.0: (1, "boom")
        with self.assertRaises(IOError):
            adb.shell(["true"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDrvScreen(unittest.TestCase):
    """驱动逻辑（进程内 + FakeAdb 注入，不依赖真机）。"""

    def setUp(self):
        import drv_screen
        self.drv = drv_screen
        self.fake = FakeAdb(responses={
            "dumpsys window": DUMPSYS_SAMPLE,
            "uiautomator dump": FIXTURE_XML,
        })
        drv_screen.set_adb(self.fake)

    def tearDown(self):
        self.drv.set_adb(None)

    def test_dump_returns_nodes_and_package(self):
        import json
        out = self.drv.screen_dump()
        data = json.loads(out)
        self.assertEqual(data["current_package"], "com.timnet.lpai")
        self.assertGreaterEqual(len(data["nodes"]), 2)

    def test_tap_success_records_input_command(self):
        out = self.drv.screen_tap(360, 1360, pkg="com.timnet.lpai")
        self.assertIn("OK tapped", out)
        self.assertIn(["shell", "input", "tap", "360", "1360"], self.fake.calls)

    def test_tap_foreground_mismatch_denied(self):
        with self.assertRaises(PermissionError) as cm:
            self.drv.screen_tap(360, 1360, pkg="com.other.app")
        self.assertIn("foreground package mismatch", str(cm.exception))

    def test_text_escapes_spaces(self):
        self.drv.screen_text("hello world", pkg="com.timnet.lpai")
        self.assertIn(["shell", "input", "text", "hello%sworld"], self.fake.calls)


class TestKernelPkgScope(unittest.TestCase):
    """内核 pkg 作用域闸门（真驱动子进程；越界在闸门就被拒，不触 adb）。"""

    def setUp(self):
        import asyncio
        self.asyncio = asyncio
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        from laos.kernel import AgentKernel
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True)
        env = {"PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"}
        self.kernel.load_driver(
            "screen", [sys.executable, str(REPO / "drivers" / "drv_screen.py")], env=env)
        self.kernel.branches.create_root("main")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def test_pkg_scope_denies_foreign_app(self):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        pcb = self.kernel.spawn(name="a", caps=["screen.*"], ctx=ctx, branch="main",
                                task_scope=["pkg:com.allowed"])
        res = self.asyncio.run(self.kernel.syscall(
            pcb.pid, "screen.tap", {"x": 10, "y": 10, "pkg": "com.denied"}))
        self.assertFalse(res.ok)
        self.assertIn("outside task scope", res.error)

    def test_pkg_scope_allows_listed(self):
        ctx = ContextManager(system_prompt="t", max_tokens=2000)
        pcb = self.kernel.spawn(name="a", caps=["screen.*"], ctx=ctx, branch="main",
                                task_scope=["pkg:com.allowed"])
        res = self.asyncio.run(self.kernel.syscall(
            pcb.pid, "screen.tap", {"x": 10, "y": 10, "pkg": "com.allowed"}))
        # 闸门放行后驱动层 adb 失败（本机无真机）——但绝不是 task_scope 拒绝
        self.assertNotIn("outside task scope", res.error or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

