# tests/test_drv_evolve.py
"""drv_evolve —— OpenEvolve 驱动离线测试：命令构造 / env 覆盖 / 单行 JSON
解析（前缀噪声容错）/ rc≠0 与超时 fail-loud / import 即登记执行器。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve -v

全部 mock subprocess（不触网不起 venv）。真跑见 var/rsi/jobs/e2e-smoke.json。
"""
from __future__ import annotations

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

    def test_import_registers_executor(self):
        import laos.evolve as ev
        self.assertIn("openevolve", ev._executors)
        # run_job 全链：gate 放行 + mock 子进程 → EvolveResult
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(subprocess, "run",
                               return_value=_fake_run(stdout=_payload())):
            r = ev.run_job(EvolveJob(
                target="var/rsi/jobs/d/initial_program.py",
                evaluator="var/rsi/jobs/d/evaluator.py", iterations=5))
        self.assertEqual(r.best_score, 0.75)


if __name__ == "__main__":
    unittest.main()
