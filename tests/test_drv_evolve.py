# tests/test_drv_evolve.py
"""drv_evolve —— OpenEvolve 驱动离线测试：命令构造 / env 覆盖 / 单行 JSON
解析（前缀噪声容错）/ rc≠0 与超时 fail-loud / import 即登记执行器。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve -v

全部 mock subprocess（不触网不起 venv）。真跑见 var/rsi/jobs/e2e-smoke.json。
"""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from drivers import drv_evolve  # noqa: E402
from laos.evolve import EvolveJob, EvolveResult  # noqa: E402


def _fake_run(stdout: str = "", rc: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(args=["evolve"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("LAOS_EVOLVE")}
    env.update(extra)
    return env


def _job():
    return EvolveJob(target="var/rsi/jobs/d/initial_program.py",
                     evaluator="var/rsi/jobs/d/evaluator.py",
                     iterations=5, workdir="var/rsi/jobs/d",
                     timeout_s=60.0)


def _payload():
    return json.dumps({"best_score": 0.75,
                       "best_program_path": "var/rsi/jobs/d/o.py",
                       "best_program_sha256": "ab" * 32,
                       "iterations_completed": 5, "elapsed_s": 3.5,
                       "artifacts_dir": "var/rsi/jobs/d"})


class TestCommandConstruction(unittest.TestCase):
    def test_default_shape(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            cmd = drv.build_command(_job())
        self.assertEqual(cmd[0],
                         "var/rsi/openevolve/venv/Scripts/python.exe")
        self.assertEqual(cmd[1],
                         str(Path("drivers/openevolve_job.py").resolve()
                             .as_posix()))
        self.assertEqual(cmd[2], "--job")
        self.assertEqual(json.loads(cmd[3])["iterations"], 5)
        self.assertEqual(json.loads(cmd[3])["target"],
                         "var/rsi/jobs/d/initial_program.py")

    def test_python_env_override(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_PYTHON="py9.exe"),
                             clear=True):
            self.assertEqual(drv.build_command(_job())[0], "py9.exe")

    def test_cmd_template_replaces_whole(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_CMD="run.sh {job}"),
                             clear=True):
            cmd = drv.build_command(_job())
        self.assertEqual(cmd[0], "run.sh")
        self.assertEqual(json.loads(cmd[1])["iterations"], 5)


class TestRun(unittest.TestCase):
    # 本模块 import 副作用登记的执行器保持存活（test_import_registers_executor
    # 及后续用例都依赖它）；ENODEV 敏感断言在 test_evolve 侧以 setUp 清表护栏
    # 做顺序无关（计划 Task 6 Step 6 预警的顺序敏感失败由那边兜底）

    def test_good_payload(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=_payload())):
            r = drv.run(_job())
        self.assertIsInstance(r, EvolveResult)
        self.assertEqual(r.best_score, 0.75)

    def test_noise_prefix_tolerated(self):
        drv = drv_evolve.EvolveDriver()
        noisy = "[llm] thinking…\n" + _payload()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=noisy)):
            self.assertEqual(drv.run(_job()).iterations_completed, 5)

    def test_rc_nonzero_is_eio(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(rc=3, stderr="boom")):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("EIO", str(cm.exception))

    def test_timeout_is_etimedout(self):
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_TIMEOUT="0.001"),
                             clear=True), \
             mock.patch.object(subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(
                                   cmd=["x"], timeout=0.001)):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("ETIMEDOUT", str(cm.exception))

    def test_missing_interpreter_is_enoent(self):
        # venv 活在 gitignored var/ 下——新克隆默认解释器不存在，裸
        # WinError 2 须化成 ENOENT RuntimeError 而非击穿 syscall 协程
        # （review F-A）
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               side_effect=FileNotFoundError(
                                   2, "WinError 2")):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("ENOENT", str(cm.exception))

    def test_non_numeric_timeout_is_einval(self):
        # 终审 M4：LAOS_EVOLVE_TIMEOUT 解析失败同样带 errno 前缀
        # （此前裸 ValueError 无前缀）
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_EVOLVE_TIMEOUT="soon"),
                             clear=True):
            with self.assertRaises(ValueError) as cm:
                drv._timeout()
        self.assertIn("EINVAL", str(cm.exception))

    def test_bad_json_line_is_eio(self):
        # 终审 M4：rc=0 但 JSON 行解析失败（如 "{"oops"）→ EIO RuntimeError
        # 而非裸 JSONDecodeError 击穿 syscall 网关
        drv = drv_evolve.EvolveDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout="{oops")):
            with self.assertRaises(RuntimeError) as cm:
                drv.run(_job())
        self.assertIn("EIO", str(cm.exception))
        self.assertIn("JSON", str(cm.exception))

    def test_import_registers_executor(self):
        # 顺序无关自足（终审 I2）：test_evolve 的 setUp/tearDown 会清空
        # laos.evolve._executors，本用例不得依赖文件级 import 的一次性
        # 副作用——importlib.reload 重放模块顶层，真正重测"import 即登记"
        # （reload 复用同一模块对象，重登记本身就是被测行为；登记存续
        # 即正常 import 后的常态，无需额外清理）
        import laos.evolve as ev
        importlib.reload(drv_evolve)
        self.assertIn("openevolve", ev._executors)
        # run_job 全链：gate 放行 + mock 子进程 → EvolveResult
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=_payload())):
            r = ev.run_job(EvolveJob(
                target="var/rsi/jobs/d/initial_program.py",
                evaluator="var/rsi/jobs/d/evaluator.py", iterations=5))
        self.assertEqual(r.best_score, 0.75)


class TestWorkdirGate(unittest.TestCase):
    """workdir 允许根校验（review F-B）：核心 gate 只查 target/evaluator，
    驱动侧补闸——caller 传入的 workdir 归一化后必须落在 var/rsi/jobs/ 内
    （自分配的带时间戳默认目录天然在根内，不经此闸）。"""

    def _job_wd(self, workdir):
        return EvolveJob(target="var/rsi/jobs/d/initial_program.py",
                         evaluator="var/rsi/jobs/d/evaluator.py",
                         iterations=5, workdir=workdir, timeout_s=60.0)

    def test_outside_root_is_eperm(self):
        # 相对域外 / 绝对路径 / ..逃逸归一 / 分隔符边（jobs2 不得借道
        # jobs 前缀）四类全部 EPERM（EvolveGate.check 同款口径）
        for bad in ("tmp/elsewhere", "C:/Windows/Temp/x",
                    "var/rsi/jobs/../../tmp/x", "var/rsi/jobs2/x"):
            with self.subTest(workdir=bad):
                with mock.patch.dict(os.environ, _clean_env(), clear=True), \
                     mock.patch.object(subprocess, "run",
                                       return_value=_fake_run(
                                           stdout=_payload())):
                    with self.assertRaises(ValueError) as cm:
                        drv_evolve._openevolve_executor(self._job_wd(bad))
                self.assertIn("EPERM", str(cm.exception))

    def test_inside_root_passes_through(self):
        # 根内 caller 自定 workdir 原样透传进 --job JSON（不被改写）
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(
                                   stdout=_payload())) as m:
            r = drv_evolve._openevolve_executor(
                self._job_wd("var/rsi/jobs/custom"))
        self.assertEqual(r.best_score, 0.75)
        cmd = m.call_args[0][0]  # [python, openevolve_job.py, --job, json]
        self.assertEqual(json.loads(cmd[3])["workdir"], "var/rsi/jobs/custom")


if __name__ == "__main__":
    unittest.main()
