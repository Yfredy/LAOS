# tests/test_laosweb.py
"""laosweb —— 内核状态实时面板的回归测试（标准库 unittest，零依赖）。

    python -m unittest tests.test_laosweb -v
"""
from __future__ import annotations

import asyncio
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包，路径注入以便 import laosweb

import laosd  # noqa: E402  （laosweb 已把 bin/ 注入 sys.path，此处取同一模块对象）
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
        # 静态骨架唯一性（防 per-tick 重复渲染回归）：单 h1、九个固定面板体
        # （v0.3 增记忆面板 mem-body + 日记面板 diary-list）
        self.assertEqual(body.count("<h1"), 1)
        self.assertEqual(body.count('class="panel'), 9)
        for panel_id in ("procs-body", "branches-body", "risk-body",
                         "sched-body", "audit-body", "syscalls-body", "msgs-body",
                         "mem-body", "diary-list"):
            self.assertEqual(body.count(f'id="{panel_id}"'), 1)
        # 交互骨架：确认横幅与重启控制台各一份
        for node_id in ("confirm-banner", "restart-console"):
            self.assertEqual(body.count(f'id="{node_id}"'), 1)

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

def _safe_shutdown(kernel) -> None:
    """二次 shutdown 会向已关闭的审计句柄写记录 —— 只关还没关过的。"""
    if kernel is None or kernel.audit._fh.closed:
        return
    kernel.shutdown()


class TestInteractivity(unittest.TestCase):
    """POST 交互端点：确认队列 / kill / operator 信箱 / restart。

    内核不带驱动（kill 与 msg.* 是内建路径，无需 MCP 子进程）；restart
    用例自行把 laosd.WORKDIR / laosd.demo 换成临时桩，避免重跑完整 demo。
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name) / "var"
        self.kernel = AgentKernel(self.workdir, confirm=lambda op: True,
                                  irreversibility_budget=100)
        self._prev_kernel = laosweb.get_kernel()
        self._prev_operator = laosweb._operator_pid
        self._prev_auto = laosweb._auto_yes
        self._prev_demo_done = laosweb._demo_done
        self._prev_env = {k: os.environ.get(k)
                          for k in ("LAOS_CONFIRM", "LAOS_RISK_BUDGET")}
        laosweb.set_kernel(self.kernel)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                      laosweb.Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        cur = laosweb.get_kernel()
        laosweb.set_kernel(self._prev_kernel)
        laosweb._operator_pid = self._prev_operator
        laosweb._auto_yes = self._prev_auto
        laosweb._demo_done = self._prev_demo_done
        for key, val in self._prev_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        self.server.shutdown()
        self.server.server_close()
        _safe_shutdown(cur)          # restart 用例：cur 是重启后的新内核
        _safe_shutdown(self.kernel)  # 未 restart 的用例：老内核在此关闭
        self._td.cleanup()

    def _spawn(self, name: str, caps: list[str]):
        ctx = ContextManager(system_prompt="test", max_tokens=500,
                             swap_dir=self.workdir / "swap")
        return self.kernel.spawn(name=name, caps=caps, ctx=ctx)

    def _post(self, path, body):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req).read())

    def _post_raw(self, path, data: bytes):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data,
            headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req)

    def _get_state(self):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/api/state") as resp:
            return json.loads(resp.read().decode("utf-8"))

    # -- 确认队列 ----------------------------------------------------------

    def test_confirm_roundtrip(self):
        answers = []

        def ask():
            answers.append(laosweb.web_confirm(
                {"tool": "proc.exec", "message": "rm -rf /"}))

        t = threading.Thread(target=ask, daemon=True)
        t.start()
        deadline = time.time() + 2
        while not laosweb._pending and time.time() < deadline:
            time.sleep(0.02)
        state = self._get_state()
        self.assertEqual(len(state["pending_confirm"]), 1)
        row = state["pending_confirm"][0]
        self.assertEqual(row["tool"], "proc.exec")
        self.assertEqual(row["message"], "rm -rf /")
        self.assertTrue(row["id"])
        self.assertIn("operator_pid", state)
        res = self._post("/api/confirm", {"id": row["id"], "allow": True})
        self.assertTrue(res["ok"])
        t.join(timeout=2)
        self.assertFalse(t.is_alive(), "裁决后 web_confirm 必须返回")
        self.assertEqual(answers, [True])
        self.assertEqual(laosweb._pending, {}, "已裁决的队列项必须移除")

    def test_confirm_deny_roundtrip(self):
        answers = []

        def ask():
            answers.append(laosweb.web_confirm({"tool": "proc.exec"}))

        t = threading.Thread(target=ask, daemon=True)
        t.start()
        deadline = time.time() + 2
        while not laosweb._pending and time.time() < deadline:
            time.sleep(0.02)
        cid = next(iter(laosweb._pending))
        self._post("/api/confirm", {"id": cid, "allow": False})
        t.join(timeout=2)
        self.assertEqual(answers, [False])
        self.assertEqual(laosweb._pending, {})

    def test_confirm_unknown_id_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post("/api/confirm", {"id": "c999", "allow": True})
        self.assertEqual(cm.exception.code, 404)

    def test_confirm_timeout_denies_and_cleans_queue(self):
        old = laosweb.CONFIRM_TIMEOUT_S
        laosweb.CONFIRM_TIMEOUT_S = 0.3  # monkeypatch：等 0.3s 即超时
        try:
            res = laosweb.web_confirm({"tool": "x", "message": "y"})
        finally:
            laosweb.CONFIRM_TIMEOUT_S = old
        self.assertFalse(res, "超时按拒绝处理")
        self.assertEqual(laosweb._pending, {}, "超时后队列项必须清掉")

    def test_auto_yes_short_circuits_without_queueing(self):
        laosweb._auto_yes = True
        self.assertTrue(laosweb.web_confirm({"tool": "proc.exec"}))
        self.assertEqual(laosweb._pending, {}, "auto-yes 不得压队")

    def test_post_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post("/api/nope", {})
        self.assertEqual(cm.exception.code, 404)

    def test_post_invalid_json_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post_raw("/api/confirm", b"{not json")
        self.assertEqual(cm.exception.code, 400)

    # -- kill --------------------------------------------------------------

    def test_kill_agent(self):
        victim = self._spawn("victim", ["msg.*"])
        res = self._post("/api/kill", {"pid": victim.pid})
        self.assertTrue(res["ok"])
        self.assertEqual(self.kernel.procs[victim.pid].state, "killed")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post("/api/kill", {"pid": 424242})
        self.assertEqual(cm.exception.code, 404)

    # -- operator 信箱 -----------------------------------------------------

    def test_operator_spawn_not_in_scheduler(self):
        """回归：operator 若留在调度器轮转队列，会以 (priority, last_served)
        平局首位（dict 插入序最先）永久霸占 next_pid()——它没有脑循环、
        永不 acquire 让位，全部真 agent 会被饿死在 acquire() 的自旋上
        （laosweb 手工验收复现：demo 的 agent 一个 syscall 都发不出）。"""
        op_pid = laosweb._spawn_operator(self.kernel)
        self.assertEqual(self.kernel.procs[op_pid].name, "operator")
        self.assertIsNone(self.kernel.scheduler.next_pid(),
                          "operator 不得占用调度器轮转位")
        agent = self._spawn("worker", ["msg.*"])
        self.assertEqual(self.kernel.scheduler.next_pid(), agent.pid,
                         "agent 必须能被调度器正常轮转到")

    def test_operator_msg_send_and_recv(self):
        operator = self._spawn("operator", ["msg.*"])
        target = self._spawn("worker", ["msg.*"])
        laosweb._operator_pid = operator.pid  # 生产中由 _boot_stack 装配
        res = self._post("/api/msg", {"to_pid": target.pid, "text": "hi"})
        self.assertTrue(res["ok"])
        recv = asyncio.run(self.kernel.syscall(target.pid, "msg.recv", {}))
        self.assertTrue(recv.ok)
        self.assertIn("hi", recv.text)
        # /api/recv：以目标 pid 自己的身份收取信箱（再来一条验证端点）
        self._post("/api/msg", {"to_pid": target.pid, "text": "again"})
        res2 = self._post("/api/recv", {"pid": target.pid})
        self.assertTrue(res2["ok"])
        self.assertIn("again", res2["text"])
        # 发给不存在的 pid：syscall 层 ESRCH → ok=false 透传
        res3 = self._post("/api/msg", {"to_pid": 987654, "text": "nope"})
        self.assertFalse(res3["ok"])

    # -- restart -----------------------------------------------------------

    def test_restart_rebuilds_kernel(self):
        async def _noop_demo(kernel, use_real, task):
            await asyncio.sleep(0)

        prev_workdir = laosd.WORKDIR
        prev_demo = laosd.demo
        laosd.WORKDIR = self.workdir      # 新内核落盘进临时目录
        laosd.demo = _noop_demo           # 不重跑完整 demo（保持用例快速）
        # 非法 confirm 先拒（此时旧内核还活着）
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._post("/api/restart", {"confirm": "banana", "risk_budget": 3})
        self.assertEqual(cm.exception.code, 400)
        try:
            res = self._post("/api/restart",
                             {"confirm": "auto-yes", "risk_budget": 9})
        finally:
            laosd.WORKDIR = prev_workdir
            laosd.demo = prev_demo
        self.assertTrue(res["ok"])
        newk = laosweb.get_kernel()
        self.assertIsNot(newk, self.kernel, "restart 必须换新内核对象")
        self.assertEqual(os.environ.get("LAOS_RISK_BUDGET"), "9")
        self.assertEqual(os.environ.get("LAOS_CONFIRM"), "auto-yes")
        self.assertTrue(laosweb._auto_yes)
        # 新内核含 operator 进程，且 state 暴露 operator_pid
        names = {p["name"] for p in newk.ps()}
        self.assertIn("operator", names)
        state = self._get_state()
        self.assertIsNotNone(state["operator_pid"])
        self.assertEqual(state["operator_pid"], laosweb._operator_pid)
        self.assertIn("pending_confirm", state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
