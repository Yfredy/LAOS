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
from laos.branch import BranchContext  # noqa: E402
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


class TestRaceFreeReads(KernelTestCase):
    """laosweb 的 1s 轮询读 vs demo 线程写：内核可观测面不得抛竞态异常。"""

    def test_pcb_to_dict_excludes_live_ctx(self):
        """to_dict 不得深拷贝"活的" ContextManager。

        回归背景：asdict 会深拷贝非 dataclass 叶子 —— 包括 demo 线程仍在
        向 _window 追加消息的 ctx，1s 轮询 × 每 agent 放大后既慢又可能在
        拷贝途中 RuntimeError。输出形状必须不变：无 ctx 键、caps 为排序列表。
        """
        ctx = ContextManager(system_prompt="race", max_tokens=2000,
                             swap_dir=self.workdir / "swap")
        ctx.append("user", "hello world")
        pcb = self.kernel.spawn(name="snap-agent", caps=["b", "a"], ctx=ctx,
                                branch="main")
        d = pcb.to_dict()
        self.assertNotIn("ctx", d)
        self.assertEqual(d["caps"], ["a", "b"])
        # 此后继续向上下文追加：已返回的 dict 不受影响（不得共享引用）
        before = json.dumps(d, sort_keys=True, ensure_ascii=False)
        ctx.append("assistant", "x" * 400)
        self.assertEqual(json.dumps(d, sort_keys=True, ensure_ascii=False), before)

    def test_concurrent_spawn_while_reading_ps_and_branches(self):
        """并发冒烟：spawn 线程边写表，主线程边读 ps()/branches.list()。

        未快照/未加锁时，dict 视图迭代撞上插入会抛
        RuntimeError: dictionary changed size during iteration。
        """
        errors: list[BaseException] = []
        main = self.kernel.branches.get("main")

        def spawner():
            try:
                for i in range(50):
                    ctx = ContextManager(system_prompt=f"s{i}", max_tokens=500,
                                         swap_dir=self.workdir / "swap")
                    self.kernel.spawn(name=f"race-{i}", caps=["sys.*"],
                                      ctx=ctx, branch="main")
                    if i % 5 == 0:  # 让 branches.list() 的竞态也真实发生
                        self.kernel.branches.register(BranchContext(
                            name=f"race-b{i}", base=main.workspace,
                            workspace=main.workspace))
            except BaseException as exc:
                errors.append(exc)

        t = threading.Thread(target=spawner)
        t.start()
        for _ in range(50):  # 与 spawn 并发交错的固定读取次数（短且确定）
            self.kernel.ps()
            self.kernel.branches.list()
        t.join()
        self.assertFalse(errors, f"并发读写期间出现异常: {errors!r}")
        self.assertEqual(len(self.kernel.ps()), 50)
        names = {b["name"] for b in self.kernel.branches.list()}
        self.assertIn("main", names)
        self.assertTrue(any(n.startswith("race-b") for n in names))


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
        # 静态骨架唯一性（防 per-tick 重复渲染回归）：单 h1、六个固定面板体
        self.assertEqual(body.count("<h1"), 1)
        self.assertEqual(body.count('class="panel'), 6)
        for panel_id in ("procs-body", "branches-body", "risk-body",
                         "sched-body", "audit-body", "syscalls-body"):
            self.assertEqual(body.count(f'id="{panel_id}"'), 1)

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/nope")
        self.assertEqual(cm.exception.code, 404)

    def test_head_liveness(self):
        # curl -sI 探活：HEAD / 与 HEAD /api/state 均 200，未知路径 404
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/html", resp.headers["Content-Type"])
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/state", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/nope", method="HEAD")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
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
