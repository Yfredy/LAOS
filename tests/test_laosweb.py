# tests/test_laosweb.py
"""laosweb —— 内核状态实时面板的回归测试（标准库 unittest，零依赖）。

    python -m unittest tests.test_laosweb -v
"""
from __future__ import annotations

import asyncio
import http.server
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包，路径注入以便 import laosweb

import laosweb  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

DRIVERS = REPO / "drivers"


class KernelTestCase(unittest.TestCase):
    """真内核测试台（沿用 test_laos.py 的 KernelTestCase 模式）。

    真驱动 + main 分支 + 两个能力不同的 agent，随后一次成功 syscall、
    一次被能力表拒绝的 syscall —— 保证 build_state 的每类数据都有内容。
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(self.workdir / "branches"),
        }
        self.kernel.load_driver("fs", [sys.executable, str(DRIVERS / "drv_fs.py")], env=env)
        self.kernel.load_driver("sys", [sys.executable, str(DRIVERS / "drv_sys.py")], env=env)
        main = self.kernel.branches.create_root("main")
        ws = main.workspace / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "hosts").write_text("127.0.0.1 localhost\n", encoding="utf-8")

    def tearDown(self):
        self.kernel.shutdown()
        self._td.cleanup()

    def _spawn(self, name: str, caps: list[str]):
        ctx = ContextManager(system_prompt="test", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx, branch="main")

    def _exercise_kernel(self):
        """一次成功 fs.read + 一次被拒 fs.read（能力剥夺的 agent）。"""
        ops = self._spawn("ops-agent", ["fs.*", "sys.*"])
        res = asyncio.run(self.kernel.syscall(
            ops.pid, "fs.read", {"path": "/main/workspace/hosts"}))
        self.assertTrue(res.ok, res.error)
        guest = self._spawn("guest-agent", ["sys.*"])
        res = asyncio.run(self.kernel.syscall(
            guest.pid, "fs.read", {"path": "/main/workspace/hosts"}))
        self.assertFalse(res.ok)
        self.assertIn("EPERM", res.error)


class TestBuildState(KernelTestCase):
    def test_keys_and_shapes(self):
        self._exercise_kernel()
        st = laosweb.build_state(self.kernel)
        for key in ("status", "procs", "branches", "scheduler", "risk",
                    "isolation", "lsmod", "syscalls", "audit", "demo_done"):
            self.assertIn(key, st)
        # 进程表：两个 agent 都在册
        self.assertEqual(len(st["procs"]), 2)
        self.assertEqual({p["name"] for p in st["procs"]},
                         {"ops-agent", "guest-agent"})
        self.assertTrue(all("stats" in p and "caps" in p for p in st["procs"]))
        # status 直通 kernel.status()
        self.assertEqual(st["status"]["processes"], 2)
        self.assertIn("uptime_s", st["status"])
        # audit：最后 60 条的浅拷贝切片，非空
        self.assertTrue(st["audit"])
        self.assertLessEqual(len(st["audit"]), 60)
        self.assertTrue(any(r.get("event") == "syscall" and not r["ok"]
                            for r in st["audit"]), "denied syscall 应入审计")
        # risk 字段
        for key in ("spent", "remaining", "budget", "per_tool"):
            self.assertIn(key, st["risk"])
        # scheduler：snapshot() 或 sched_view 兜底，spawn 过即非空
        self.assertIsInstance(st["scheduler"], list)
        self.assertTrue(st["scheduler"])
        self.assertIn("pid", st["scheduler"][0])
        # 其余直通字段
        self.assertTrue(st["lsmod"])
        self.assertIn("fs.read", st["syscalls"])
        self.assertIsInstance(st["demo_done"], bool)

    def test_audit_rows_are_copies(self):
        self._exercise_kernel()
        st = laosweb.build_state(self.kernel)
        row = st["audit"][-1]
        row["event"] = "tampered"
        self.assertNotEqual(self.kernel.audit.records[-1]["event"], "tampered",
                            "audit 切片必须是浅拷贝，不得共享顶层 dict")


class TestHttp(unittest.TestCase):
    """HTTP 骨架：类级起 ThreadingHTTPServer，共享一个内核。"""

    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        workdir = Path(cls._td.name) / "var"
        cls.kernel = AgentKernel(workdir, confirm=lambda op: True,
                                 irreversibility_budget=100)
        env = {
            "PYTHONPATH": str(REPO),
            "PYTHONIOENCODING": "utf-8",
            "LAOS_FS_ROOT": str(workdir / "branches"),
        }
        cls.kernel.load_driver("fs", [sys.executable, str(DRIVERS / "drv_fs.py")], env=env)
        cls.kernel.load_driver("sys", [sys.executable, str(DRIVERS / "drv_sys.py")], env=env)
        cls.kernel.branches.create_root("main")
        cls._prev_kernel = laosweb._kernel
        laosweb._kernel = cls.kernel
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), laosweb.Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        laosweb._kernel = cls._prev_kernel
        cls.kernel.shutdown()
        cls._td.cleanup()

    def test_api_state_returns_kernel_json(self):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/api/state") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/json", resp.headers["Content-Type"])
            data = json.loads(resp.read().decode("utf-8"))
        self.assertIn("status", data)
        self.assertIn("procs", data)
        self.assertIn("audit", data)

    def test_index_serves_page(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])
            body = resp.read().decode("utf-8")
        self.assertIn("laosweb", body)

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/nope")
        self.assertEqual(cm.exception.code, 404)

    def test_state_unavailable_503(self):
        prev = laosweb._kernel
        laosweb._kernel = None
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/state")
            self.assertEqual(cm.exception.code, 503)
        finally:
            laosweb._kernel = prev


if __name__ == "__main__":
    unittest.main(verbosity=2)
