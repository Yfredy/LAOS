# tests/test_laosweb.py
"""laosweb —— 内核状态实时面板的回归测试（标准库 unittest，零依赖）。

    python -m unittest tests.test_laosweb -v
"""
from __future__ import annotations

import asyncio
import gzip
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
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bin"))  # bin/ 非包，路径注入以便 import laosweb

import laosd  # noqa: E402  （laosweb 已把 bin/ 注入 sys.path，此处取同一模块对象）
import laosweb  # noqa: E402
from laos.branch import BranchContext  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel, AuditLog  # noqa: E402

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
        # 轮转安全复合键两组分必须全程可见（设计 §6.2：seq 轮转复位归零，
        # 前端按 (epoch, seq) 去重）——epoch/seq 均由 AuditLog.write 盖章
        self.assertTrue(all("epoch" in r and "seq" in r for r in st["audit"]))
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
        self.assertIn("<!doctype html>", body)
        # v3 骨架（mobile-first + 底部 tab）：四个 tab 按钮 + 四个 section
        # 容器各带 data-view —— Task 4 在 section 容器内逐 view 填充内容
        self.assertEqual(body.count("data-view="), 8)
        for view in ("chat", "audit", "memory", "gov"):
            self.assertEqual(body.count(f'data-view="{view}"'), 2)
            self.assertEqual(body.count(f'id="v-{view}"'), 1)
        self.assertIn("manifest.webmanifest", body)   # PWA manifest 挂载
        self.assertIn("--accent", body)               # CSS 变量主题（暗/亮）

    def test_index_has_four_view_render_markers(self):
        """Task 4 四视图关键标记：审批卡四钮文案 / 治理门控未装配态 /
        记忆 provenance 人写标注 / XSS 地基（禁 innerHTML）/ tick 自愈。"""
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/") as resp:
            body = resp.read().decode("utf-8")
        # 审批卡四钮：拒绝 / 允许一次（不带 scope）/ 本会话 / 总是（带 scope）
        for label in ("拒绝", "允许一次", "本会话", "总是"):
            self.assertIn(label, body)
        self.assertIn("/api/confirm", body)
        # 治理门控：未装配态文本（禁写控件由 JS disabled 门控）
        self.assertIn("未装配", body)
        self.assertIn("/api/sentinel", body)
        # 记忆 provenance：人写亮显中文标注
        self.assertIn("人写", body)
        # XSS 地基：动态内容一律 DOM API/textContent 构造，禁止 innerHTML
        self.assertNotIn("innerHTML", body)
        # T3 移交必修：tick 失败也排下一轮（自排程语句必须在 try/catch 外）
        self.assertIn("setTimeout(tick", body)

    def test_manifest_and_icon_served(self):
        # PWA 四件套之 manifest：固定 JSON、内联 SVG 图标（无二进制资产）
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/manifest.webmanifest") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/manifest+json",
                          resp.headers["Content-Type"])
            data = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(data["name"], "laos 控制台")
        self.assertEqual(data["short_name"], "laos")
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["theme_color"], "#000000")  # v0.35 iOS 分组风换肤：纯黑
        self.assertIn("/icon.svg", [i["src"] for i in data["icons"]])
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/icon.svg") as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("image/svg+xml", resp.headers["Content-Type"])
            svg = resp.read().decode("utf-8")
        self.assertIn("<svg", svg)
        self.assertIn("#0f6f5c", svg)

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


class TestRenderData(unittest.TestCase):
    """Task 4 渲染数据整形（纯函数）：审计 chips 行 / 记忆 provenance 行。

    PAGE JS 是这些纯函数的浏览器侧镜像——键名/形状在此钉死，前端漂移
    会被 DOM 标记断言（见 TestHttp）与人工验收捕获。
    """

    def test_chips_rows_shape_and_err_truncation(self):
        state = {"audit": [
            {"event": "syscall", "tool": "fs.read", "ok": True, "result": "3 B",
             "pid": 3, "t": 1.0, "epoch": 0, "seq": 0},
            {"event": "syscall", "tool": "proc.exec", "ok": False,
             "result": "E" * 100, "pid": 4, "t": 2.0, "epoch": 0, "seq": 1},
        ]}
        rows = laosweb._chips_rows(state)
        self.assertEqual(rows[0], {"tool": "fs.read", "ok": True, "pid": 3,
                                   "t": 1.0, "err": None})
        self.assertFalse(rows[1]["ok"])
        self.assertEqual(rows[1]["err"], "E" * 80, "err 辅文截断到 80 字符")

    def test_chips_rows_limit_takes_latest(self):
        state = {"audit": [
            {"event": "syscall", "tool": f"t{i}", "ok": True, "t": float(i),
             "epoch": 0, "seq": i} for i in range(50)]}
        rows = laosweb._chips_rows(state, limit=40)
        self.assertEqual(len(rows), 40)
        self.assertEqual([r["tool"] for r in (rows[0], rows[-1])], ["t10", "t49"],
                         "取最后 limit 条（最新在尾）")

    def test_chips_rows_non_syscall_falls_back_to_event(self):
        """非 syscall 事件（spawn/kill/admission/…）无 tool/ok 键：chip 用
        事件名、ok 中性 True——中性事件不得被误报成 err。"""
        rows = laosweb._chips_rows({"audit": [
            {"event": "spawn", "name": "a", "pid": 2, "t": 1.0,
             "epoch": 0, "seq": 0}]})
        self.assertEqual(rows[0]["tool"], "spawn")
        self.assertTrue(rows[0]["ok"])
        self.assertIsNone(rows[0]["err"])

    def test_chips_rows_empty_and_missing_audit(self):
        self.assertEqual(laosweb._chips_rows({}), [])
        self.assertEqual(laosweb._chips_rows({"audit": []}), [])

    def test_memory_rows_origin_default_and_user_highlight(self):
        """memories 键以 build_state 实际为准（{"stats","recent"}）：行取
        recent；origin=user 是亮显位，缺省（老库行）按 agent。"""
        state = {"memories": {"stats": {"total": 2}, "recent": [
            {"id": 1, "kind": "fact", "text": "人写的", "origin": "user"},
            {"id": 2, "kind": "episodic", "text": "模型写的"},  # 无 origin
        ]}}
        rows = laosweb._memory_rows(state)
        self.assertEqual(rows[0]["id"], 1)
        self.assertEqual(rows[0]["origin"], "user")
        self.assertTrue(rows[0]["user"], "origin=user 是亮显位（人写胜模型）")
        self.assertEqual(rows[1]["origin"], "agent", "origin 缺省 agent")
        self.assertFalse(rows[1]["user"])
        self.assertEqual(rows[1]["text"], "模型写的")
        self.assertEqual(rows[1]["kind"], "episodic")

    def test_memory_rows_empty_and_missing(self):
        self.assertEqual(laosweb._memory_rows({}), [])
        self.assertEqual(laosweb._memory_rows({"memories": {}}), [])


class TestRotationSafeAuditKey(unittest.TestCase):
    """设计 §6.2：audit.jsonl 轮转换代后 seq 复位归零。

    消费者按 (file_epoch 轮转代, seq) 复合键去重；裸 seq 键在轮转后会把
    新代同 seq 的事件误判为重复而丢弃。两组分均由 AuditLog.write 在 append
    前盖章。这里用真 AuditLog 走真轮转路径（不手搓 dict），保证复合键的
    两组分在生产路径上真实存在、真实递增。（v3 Task 4 审计视图落地时，
    前端去重键应恢复对 PAGE 的复合键静态断言。）
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.path = Path(self._td.name) / "audit.jsonl"
        self.audit = AuditLog(self.path)

    def tearDown(self):
        self.audit.close()
        self._td.cleanup()

    @staticmethod
    def _old_js_key(r: dict) -> str:
        """旧前端去重键：裸 seq（轮转后误判重复的缺陷键）。"""
        return f"{r['seq']}|{r['t']}|{r.get('tool', '')}"

    @staticmethod
    def _new_js_key(r: dict) -> str:
        """新前端去重键：(epoch, seq) 复合键 + t/tool 联合（同代同秒同
        工具多次调用仍靠 seq 区分）。"""
        return f"{r['epoch']}|{r['seq']}|{r['t']}|{r.get('tool', '')}"

    def test_rows_carry_epoch_and_seq(self):
        self.audit.write({"t": 1.0, "event": "syscall", "tool": "fs.read"})
        self.audit.write({"t": 1.1, "event": "spawn", "name": "a"})
        self.assertEqual([r["epoch"] for r in self.audit.records], [0, 0])
        self.assertEqual([r["seq"] for r in self.audit.records], [0, 1])

    def test_rotation_same_seq_two_events_not_deduped(self):
        """核心场景（任务书 Step 1）：轮转前后各一条同 t/同 tool/同 seq 的
        不同事件——旧键判重（错误，轮转后新事件被丢），新键不判重。"""
        old_row = {"t": 100.0, "event": "syscall", "tool": "fs.read",
                   "pid": 7, "result": "ok"}
        self.audit.write(old_row)            # 旧代 seq=0
        self.audit.rotate()
        new_row = {"t": 100.0, "event": "syscall", "tool": "fs.read",
                   "pid": 8, "result": "EACCES"}
        self.audit.write(new_row)            # 新代 seq=0（轮转复位）
        self.assertEqual(old_row["seq"], new_row["seq"],
                         "前置：轮转后 seq 复位，两代首条同 seq")
        self.assertNotEqual(old_row["pid"], new_row["pid"],
                            "前置：两条确是不同事件")
        # 旧键必然判重——这正是 §6.2 声明的缺陷（记录在案，非回归目标）
        self.assertEqual(self._old_js_key(old_row), self._old_js_key(new_row),
                         "旧裸 seq 键在轮转边界必然碰撞（§6.2 缺陷）")
        # 新键必须把两代同 seq 事件区分开：不丢不重
        self.assertEqual(new_row["epoch"], old_row["epoch"] + 1,
                         "轮转换代：epoch 必须单调 +1")
        self.assertNotEqual(self._new_js_key(old_row), self._new_js_key(new_row),
                             "(epoch, seq) 复合键必须区分两代同 seq 事件")

    def test_rotate_archives_current_file_gzip(self):
        """轮转原语：当前文件 gzip 归档（audit-<UTC日期>-<代>.jsonl.gz），
        重开空文件继续追加；records 清零、epoch +1，落盘行同样带复合键。"""
        for i in range(3):
            self.audit.write({"t": float(i), "event": "spawn", "name": f"a{i}"})
        self.audit.rotate()
        archives = list(self.path.parent.glob("audit-*.jsonl.gz"))
        self.assertEqual(len(archives), 1, "轮转恰好归档一份当前代")
        self.assertRegex(archives[0].name, r"^audit-\d{8}-0\.jsonl\.gz$",
                         "归档名 = audit-<UTC日期>-<轮转代>.jsonl.gz（§6.2）")
        with gzip.open(archives[0], "rt", encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        self.assertEqual([r["seq"] for r in rows], [0, 1, 2],
                         "归档段保完整旧代行，逐行可 parse")
        # 当前文件重开为空；内存账本清零、换代
        self.assertEqual(self.path.read_text(encoding="utf-8"), "")
        self.assertEqual(self.audit.records, [])
        self.assertEqual(self.audit.epoch, 1)
        # 轮转后首条：seq 复位归零、epoch 换代（内存与落盘同一口径）
        self.audit.write({"t": 9.0, "event": "spawn", "name": "b"})
        self.assertEqual(self.audit.records[0]["epoch"], 1)
        self.assertEqual(self.audit.records[0]["seq"], 0)
        line = json.loads(self.path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((line["epoch"], line["seq"]), (1, 0),
                         "落盘行同样携带复合键两组分（文件消费者同口径）")

    def test_epoch_continues_from_existing_archives(self):
        """归档名内嵌单调代 n（§6.2）：新 AuditLog 开机扫已有归档续代，
        重启后新内核的 (epoch, seq) 不会与旧代碰撞。"""
        self.audit.close()
        with gzip.open(self.path.parent / "audit-20260101-3.jsonl.gz", "wb"):
            pass  # 预置历史归档：已轮转 4 代（0..3）
        self.audit = AuditLog(self.path)
        self.assertEqual(self.audit.epoch, 4, "换代从 max 归档代 + 1 续起")
        self.audit.write({"t": 1.0, "event": "spawn", "name": "a"})
        self.assertEqual(self.audit.records[0]["epoch"], 4)
        self.assertEqual(self.audit.records[0]["seq"], 0)

    def test_page_has_no_bare_seq_dedup_key(self):
        """v3 骨架弃用了旧 PAGE 的全部 JS（renderAudit 去重逻辑随之下线，
        Task 4 审计视图重写时恢复）。底线守卫：裸 seq 去重键（轮转后误判
        重复的缺陷键）不得在新 PAGE 里复活。"""
        self.assertNotIn("const key = r.seq + '|'", laosweb.PAGE,
                         "裸 seq 去重键不得残留（轮转后误判重复）")

    def test_page_uses_composite_epoch_seq_dedup_key(self):
        """Task 4 恢复正向断言：PAGE 审计流去重键必须是 (epoch, seq, t,
        tool) 复合键（与上条负面断言配套）——seq 轮转复位归零后裸 seq 键
        会把新代同 seq 事件误判重复而丢弃。"""
        self.assertIn('r.epoch + "|" + r.seq', laosweb.PAGE,
                      "审计流去重键必须以 epoch|seq 复合键开头")

    # ---- 终审 T3 修复波：rotate 异常恢复 + mode='a' 跨 boot 键语义 ----

    def test_rotate_failure_keeps_stream_usable(self):
        """T3-1：close 后归档任一步抛错不留下已关句柄断流——保底以追加
        模式重开原文件后原样上抛；数据未丢、代数未变、半途归档残件清掉。"""
        self.audit.write({"t": 1.0, "event": "spawn", "name": "a"})
        with mock.patch("gzip.GzipFile", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.audit.rotate()
        # 半途归档残件被清：开机扫档不会误续代
        self.assertEqual(list(self.path.parent.glob("audit-*.jsonl.gz")), [])
        # 审计不断流：句柄可用、原数据仍在、代数未变，可继续写可重试
        self.assertEqual(self.audit.epoch, 0)
        self.audit.write({"t": 2.0, "event": "spawn", "name": "b"})
        self.assertEqual([r["seq"] for r in self.audit.records], [0, 1])
        lines = [json.loads(ln)
                 for ln in self.path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([(r["epoch"], r["seq"]) for r in lines],
                         [(0, 0), (0, 1)])
        self.audit.rotate()                        # 重试成功，语义照常
        self.assertEqual(self.audit.epoch, 1)

    def test_append_mode_cross_boot_epoch_continues(self):
        """T3-2：mode='a' 跨 boot 同文件不出现重复 (epoch, seq) 键——新
        boot 开机检测文件尾已盖 epoch，换新代续写。"""
        self.audit.close()
        self.audit = AuditLog(self.path, mode="a")
        self.audit.write({"t": 1.0, "event": "spawn", "name": "boot1a"})
        self.audit.write({"t": 1.1, "event": "spawn", "name": "boot1b"})
        boot1_epoch = self.audit.records[-1]["epoch"]
        self.audit.close()
        self.audit = AuditLog(self.path, mode="a")     # 第二次 boot，累积模式
        self.audit.write({"t": 2.0, "event": "spawn", "name": "boot2"})
        self.assertEqual(self.audit.epoch, boot1_epoch + 1, "跨 boot 换代续写")
        self.assertEqual(self.audit.records[0]["seq"], 0)
        rows = [json.loads(ln)
                for ln in self.path.read_text(encoding="utf-8").splitlines()]
        keys = [(r["epoch"], r["seq"]) for r in rows]
        self.assertEqual(len(keys), len(set(keys)),
                         "同文件 (epoch, seq) 复合键跨 boot 不重复")

    def test_append_mode_after_rotate_cross_boot_epoch_continues(self):
        """T3-2 轮转组合：boot1 轮转后续写（文件内是代 1），boot2 开机取
        归档扫描与文件尾代两者较大者 +1——归档与未轮转内容都算数。"""
        self.audit.close()
        self.audit = AuditLog(self.path, mode="a")
        self.audit.write({"t": 1.0, "event": "spawn", "name": "b1"})
        self.audit.rotate()                            # 归档代 0，文件内代 1
        self.audit.write({"t": 1.1, "event": "spawn", "name": "b1post"})
        self.audit.close()
        self.audit = AuditLog(self.path, mode="a")
        self.assertEqual(self.audit.epoch, 2,
                         "归档扫描给 1，文件尾代 1 再 +1 → 2")
        self.audit.write({"t": 2.0, "event": "spawn", "name": "b2"})
        rows = [json.loads(ln)
                for ln in self.path.read_text(encoding="utf-8").splitlines()]
        keys = [(r["epoch"], r["seq"]) for r in rows]
        self.assertEqual(keys, [(1, 0), (2, 0)], "两代同 seq 不撞键")


class TestSentinelApi(KernelTestCase):
    """治理 API 面：sentinel 未装配优雅降级；装配后 grants/taints/mode 可读写。"""

    def _boot_with_sentinel(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="ask"))
        self.kernel.sentinel.grants.add("msg.send", scope="session")
        self.kernel.sentinel.mark_private_read(1001)
        return self.kernel.sentinel

    def test_disabled_when_not_assembled(self):
        from laosweb import _sentinel_view
        self.assertEqual(_sentinel_view(self.kernel),
                         {"enabled": False, "mode": None, "private_tools": [],
                          "egress_tools": [], "grants": [], "tainted_pids": []})

    def test_view_projects_grants_and_taints(self):
        self._boot_with_sentinel()
        from laosweb import _sentinel_view
        v = _sentinel_view(self.kernel)
        self.assertTrue(v["enabled"])
        self.assertEqual(v["mode"], "ask")
        self.assertEqual(v["grants"][0]["tool_glob"], "msg.send")
        self.assertIn(1001, v["tainted_pids"])

    def test_post_grant_revoke_set_mode(self):
        s = self._boot_with_sentinel()
        from laosweb import _sentinel_post
        r = _sentinel_post(self.kernel, {"action": "grant", "tool_glob": "fs.*",
                                         "target": None, "scope": "always"})
        self.assertTrue(r["ok"]); self.assertIsInstance(r["gid"], int)
        self.assertTrue(_sentinel_post(self.kernel, {"action": "revoke",
                                                     "gid": r["gid"]})["ok"])
        _sentinel_post(self.kernel, {"action": "set_mode", "mode": "auto"})
        self.assertEqual(s.cfg.mode, "auto")

    def test_post_unknown_action_400(self):
        self._boot_with_sentinel()
        from laosweb import _sentinel_post
        with self.assertRaises(KeyError):
            _sentinel_post(self.kernel, {"action": "nope"})


class TestApprovalScope(KernelTestCase):
    """审批卡 scope 语义：approved+session/always → 先落 grant 再放行。

    nanoMuse 审批三字段语义的 laos 化（spec §4）：POST /api/confirm 扩展为
    {cid, approved, scope, tool}——approved 且 scope∈{session,always} 且
    sentinel 已装配时先 grants.add 再放行；deny 不落 grant。web_confirm 的
    pending 条目携带 "reason"（= op.get("sentinel")，无 sentinel 时 None）。
    """

    def setUp(self):
        super().setUp()
        # _handle_confirm 经模块级持有者找 sentinel：接线 + 测毕还原
        self._prev_kernel = laosweb.get_kernel()
        laosweb.set_kernel(self.kernel)

    def tearDown(self):
        laosweb.set_kernel(self._prev_kernel)
        super().tearDown()

    @staticmethod
    def _queue_confirm(op: dict) -> tuple[threading.Thread, dict]:
        """压一条待裁决项并等它入队（web_confirm 阻塞在独立线程）。"""
        results: dict = {}

        def asker():
            results["ok"] = laosweb.web_confirm(op)

        t = threading.Thread(target=asker, daemon=True)
        t.start()
        deadline = time.time() + 2
        while not laosweb._pending and time.time() < deadline:
            time.sleep(0.02)
        return t, results

    def test_confirm_with_session_scope_grants(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="ask"))
        t, results = self._queue_confirm(
            {"tool": "msg.send", "args": {}, "sentinel": "taint-egress"})
        cid = next(iter(laosweb._pending))
        self.assertEqual(laosweb._pending[cid]["reason"], "taint-egress")
        code, _body = laosweb._handle_confirm(
            {"cid": cid, "approved": True, "scope": "session", "tool": "msg.send"})
        self.assertEqual(code, 200)
        t.join(timeout=2)
        self.assertTrue(results["ok"])
        g = self.kernel.sentinel.grants.list_grants()
        self.assertEqual([(x["tool_glob"], x["scope"]) for x in g],
                         [("msg.send", "session")])

    def test_confirm_deny_no_grant(self):
        from laos.sentinel import Sentinel, SentinelConfig
        self.kernel.sentinel = Sentinel(SentinelConfig(mode="ask"))
        t, results = self._queue_confirm({"tool": "msg.send", "args": {}})
        cid = next(iter(laosweb._pending))
        code, _ = laosweb._handle_confirm({"cid": cid, "approved": False})
        self.assertEqual(code, 200)
        t.join(timeout=2)
        self.assertFalse(results["ok"])
        self.assertEqual(self.kernel.sentinel.grants.list_grants(), [],
                         "deny 不得落 grant")


class TestChatApi(KernelTestCase):
    """个人 agent 对话面：未配置降级 / 假客户端全流程 / 审计脱敏。

    模块级 _llm 与 _chat_log 在用例间必须复位（Task 0 教训：全局状态
    不得跨用例泄漏）。
    """

    class _StubClient:
        def __init__(self, reply="回声"):
            self.system = "test-system"
            self.model = "stub-model"
            self.reply = reply
            self.calls = []

        def chat(self, messages):
            self.calls.append([dict(m) for m in messages])
            return self.reply

    def setUp(self):
        super().setUp()
        import laosweb
        self._llm_backup = laosweb._llm
        self._log_backup = list(laosweb._chat_log)
        self._kernel_backup = laosweb._kernel
        laosweb._llm = None
        laosweb._chat_log.clear()
        laosweb._kernel = self.kernel      # _audit_llm 经 get_kernel() 取内核

    def tearDown(self):
        import laosweb
        laosweb._llm = self._llm_backup
        laosweb._chat_log[:] = self._log_backup
        laosweb._kernel = self._kernel_backup
        super().tearDown()

    def test_unconfigured_returns_503(self):
        from laosweb import _handle_chat
        code, payload = _handle_chat({"text": "hi"})
        self.assertEqual(code, 503)
        self.assertIn("LAOS_LLM", payload["error"])

    def test_empty_text_400(self):
        from laosweb import _handle_chat
        self.assertEqual(_handle_chat({"text": "  "})[0], 400)

    def test_chat_flow_with_stub_client(self):
        import laosweb
        stub = self._StubClient("你好，我是 stub")
        laosweb._llm = stub
        code, payload = laosweb._handle_chat({"text": "在吗"})
        self.assertEqual(code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reply"], "你好，我是 stub")
        self.assertEqual(payload["model"], "stub-model")
        # 会话历史：一问一答成对入 log
        self.assertEqual([m["role"] for m in payload["log"]],
                         ["user", "assistant"])
        # 消息组装：system 前置 + 历史 + 本轮 user
        self.assertEqual(stub.calls[0][0]["content"], "test-system")
        self.assertEqual(stub.calls[0][-1], {"role": "user", "content": "在吗"})
        # 第二轮携带第一轮历史
        laosweb._handle_chat({"text": "第二问"})
        roles = [m["role"] for m in stub.calls[1]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])

    def test_reset_clears_log(self):
        import laosweb
        laosweb._llm = self._StubClient()
        laosweb._handle_chat({"text": "a"})
        code, payload = laosweb._handle_chat({"reset": True})
        self.assertEqual(code, 200)
        self.assertEqual(payload["log"], [])
        self.assertEqual(laosweb._chat_view(), [])

    def test_audit_content_free(self):
        import laosweb
        laosweb._llm = self._StubClient("秘密回复内容")
        secret_q = "这个问题包含秘密123"
        laosweb._handle_chat({"text": secret_q})
        recs = [r for r in self.kernel.audit.records if r.get("event") == "llm"]
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["ok"])
        self.assertEqual(recs[0]["model"], "stub-model")
        self.assertIn("ms", recs[0])
        # 隐私红线：内容永不入审计——问句与回复都不得出现在任何审计行
        for r in self.kernel.audit.records:
            self.assertNotIn(secret_q, json.dumps(r, ensure_ascii=False))
            self.assertNotIn("秘密回复内容", json.dumps(r, ensure_ascii=False))

    def test_build_state_includes_chat(self):
        import laosweb
        state = laosweb.build_state(self.kernel)
        self.assertIn("chat", state)
        self.assertFalse(state["chat"]["configured"])
        self.assertEqual(state["chat"]["log"], [])
        laosweb._llm = self._StubClient()
        state = laosweb.build_state(self.kernel)
        self.assertTrue(state["chat"]["configured"])
        self.assertEqual(state["chat"]["model"], "stub-model")

    def test_user_turn_remembered_as_human_row(self):
        import laosweb
        laosweb._llm = self._StubClient("好的")
        laosweb._handle_chat({"text": "我偏好浓缩咖啡"})
        rows = [r for r in self.kernel.memory.recall("浓缩", k=10)
                if r.get("kind") == "chat"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origin"], "user")   # 用户的话=人写行
        self.assertIn("stub-model", rows[0]["tags"])

    def test_memory_disabled_by_env(self):
        import laosweb
        laosweb._llm = self._StubClient("好的")
        with mock.patch.dict(os.environ, {"LAOS_CHAT_MEMORY": "0"}):
            laosweb._handle_chat({"text": "这句不落库"})
        self.assertEqual([r for r in self.kernel.memory.recall("不落库", k=10)
                          if r.get("kind") == "chat"], [])

    def test_recall_injects_relevant_memory_into_system(self):
        import laosweb
        self.kernel.memory.remember("fact", "意式浓缩咖啡的粉水比是 1:2",
                                    tags=["咖啡"], origin="user")
        laosweb._llm = self._StubClient("答")
        laosweb._handle_chat({"text": "浓缩咖啡怎么配"})
        system = laosweb._llm.calls[0][0]["content"]
        self.assertIn("1:2", system)                 # 相关记忆进了 prompt
        self.assertIn("相关记忆", system)

    def test_reset_keeps_memory(self):
        import laosweb
        laosweb._llm = self._StubClient("好的")
        laosweb._handle_chat({"text": "记住我喜欢安静"})
        laosweb._handle_chat({"reset": True})
        self.assertTrue([r for r in self.kernel.memory.recall("安静", k=10)
                         if r.get("kind") == "chat"])  # 记忆不随会话清空

    def test_voice_unconfigured_503(self):
        from laosweb import _handle_voice
        code, payload = _handle_voice({"audio_b64": "QUJD"})
        self.assertEqual(code, 503)
        self.assertIn("LAOS_ASR_URL", payload["error"])

    def test_voice_empty_and_oversize(self):
        from laosweb import _handle_voice
        self.assertEqual(_handle_voice({})[0], 400)
        import laosweb
        code, _ = _handle_voice({"audio_b64": "A" * (laosweb.VOICE_AUDIO_CAP + 1)})
        self.assertEqual(code, 413)

    def test_voice_success_and_audit_metadata_only(self):
        import base64
        import laosweb

        class _StubAsr:
            def transcribe(self, audio, content_type, filename):
                self.seen = (audio, content_type, filename)
                return "  你好，语音世界。 "

        stub = _StubAsr()
        laosweb._asr = stub
        self.addCleanup(setattr, laosweb, "_asr", None)
        code, payload = laosweb._handle_voice(
            {"audio_b64": base64.b64encode(b"RIFFabc").decode(),
             "content_type": "audio/wav"})
        self.assertEqual(code, 200)
        self.assertEqual(payload["text"], "你好，语音世界。")  # strip
        self.assertEqual(stub.seen[0], b"RIFFabc")
        self.assertEqual(stub.seen[2], "audio.wav")
        recs = [r for r in self.kernel.audit.records if r.get("event") == "asr"]
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["ok"])
        self.assertEqual(recs[0]["bytes"], 7)
        # 隐私红线：音频字节与转写文本都不得进审计
        for r in self.kernel.audit.records:
            blob = json.dumps(r, ensure_ascii=False)
            self.assertNotIn("RIFFabc", blob)
            self.assertNotIn("语音世界", blob)

    def test_voice_asr_failure_502(self):
        import base64
        import laosweb
        from laos.asr import AsrError

        class _BadAsr:
            def transcribe(self, *a, **kw):
                raise AsrError("HTTPError: 401")

        laosweb._asr = _BadAsr()
        self.addCleanup(setattr, laosweb, "_asr", None)
        code, payload = laosweb._handle_voice(
            {"audio_b64": base64.b64encode(b"xy").decode()})
        self.assertEqual(code, 502)
        self.assertIn("401", payload["error"])

    def test_state_voice_flag_and_page_anchors(self):
        import laosweb
        state = laosweb.build_state(self.kernel)
        self.assertIn("voice_configured", state["chat"])
        for anchor in ('id="btn-llm-mic"', 'id="btn-llm-tts"',
                       '"/api/voice"', "laosBridge", "speechSynthesis"):
            self.assertIn(anchor, laosweb.PAGE)

    def test_page_wires_chat_dom(self):
        # 前端契约：对话卡 DOM 锚点与 XSS 纪律（textContent，无 innerHTML）
        from laosweb import PAGE
        for anchor in ('id="llm-log"', 'id="llm-in"', 'id="btn-llm-send"',
                       "renderLlm", '"/api/chat"'):
            self.assertIn(anchor, PAGE)
        self.assertNotIn("innerHTML", PAGE)



if __name__ == "__main__":
    unittest.main(verbosity=2)
