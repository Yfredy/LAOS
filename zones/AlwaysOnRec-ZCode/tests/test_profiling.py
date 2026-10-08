# tests/test_profiling.py
"""bpftrace 集成层测试（脚本生成与解析是纯 Python，全平台可跑；
   真实采集见 TestBpfTraceLinux，仅 Linux+root+bpftrace 执行）。

    python -m unittest tests.test_profiling -v
"""
from __future__ import annotations

import platform
import unittest

from laos.profiling import BpfTraceProfiler

SAMPLE_OUTPUT = """\
Attaching 5 probes...
@[syscalls:sys_enter_read]: 42
@[syscalls:sys_enter_openat]: 7
@[syscalls:sys_enter_write]: 13
"""


class TestScriptAndParse(unittest.TestCase):
    def test_script_targets_pids_and_children(self):
        s = BpfTraceProfiler(pids=[11, 22]).script()
        self.assertIn("syscalls:sys_enter_*", s)
        self.assertIn("pid == 11", s)
        self.assertIn("pid == 22", s)
        self.assertIn("ppid == 11", s)  # proc.exec 的孙子进程按 ppid 覆盖

    def test_parse_accumulates_duplicate_probes(self):
        got = BpfTraceProfiler.parse(SAMPLE_OUTPUT)
        self.assertEqual(got["syscalls:sys_enter_read"], 42)
        self.assertEqual(got["syscalls:sys_enter_openat"], 7)
        # 两份相同快照（interval 周期打印 + 退出兜底打印）应累加
        doubled = BpfTraceProfiler.parse(SAMPLE_OUTPUT + SAMPLE_OUTPUT)
        self.assertEqual(doubled["syscalls:sys_enter_read"], 84)

    def test_parse_ignores_noise(self):
        got = BpfTraceProfiler.parse("Attaching 5 probes...\n\n随机日志行")
        self.assertEqual(got, {})


class TestAvailable(unittest.TestCase):
    def test_available_returns_reason_tuple(self):
        ok, why = BpfTraceProfiler(pids=[1]).available()
        self.assertIsInstance(ok, bool)
        self.assertTrue(why)
        if platform.system() != "Linux":
            self.assertFalse(ok, "非 Linux 必须报告不可用")
            self.assertIn("Linux", why)


@unittest.skipUnless(platform.system() == "Linux", "bpftrace 仅 Linux")
class TestBpfTraceLinux(unittest.TestCase):
    def test_real_capture_of_sleep_process(self):
        import shutil
        import subprocess
        import time

        prof = BpfTraceProfiler(pids=[])
        ok, why = prof.available()
        if not ok:
            self.skipTest(why)
        child = subprocess.Popen(["sleep", "3"])
        try:
            prof2 = BpfTraceProfiler(pids=[child.pid])
            self.assertTrue(prof2.start())
            time.sleep(3.5)
        finally:
            child.wait()
        probes = prof2.stop()
        # sleep 进程至少会 clock_nanosleep -> 对应 enter 探针出现
        self.assertTrue(
            any("clock_nanosleep" in k for k in probes),
            f"未捕捉到 clock_nanosleep: {probes}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
