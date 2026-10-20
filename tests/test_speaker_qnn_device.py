# tests/test_speaker_qnn_device.py
"""真机执行契约：输出分类、ADB 解析与"看门狗中性"的命令构造。

口径（2026-10-20）：FastRPC 10 秒看门狗是安全边界，`timeout` 是被动
证据，不是延迟；`err 1003` + `SSR detected` 是超时的下游后果。分类器
先认看门狗证据，再认 SSR，最后才落到通用 `Graph Execution failure`。
`--timeout` / `rpctimeout` 绝不出现在 runner 命令里（不得绕过看门狗）。

    python -m unittest tests.test_speaker_qnn_device -v
"""
from __future__ import annotations

import contextlib
import io
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.speaker_qnn import device as device_module  # noqa: E402
from scripts.speaker_qnn.contracts import classify_device_run  # noqa: E402
from scripts.speaker_qnn.device import (  # noqa: E402
    ADSP_SEARCH_ROOTS,
    FARF_CONFIG_MASK,
    FARF_CONFIG_NAME,
    TOOLCHAIN_LAYOUT,
    TOOLCHAIN_VERSIONED,
    QairtToolchain,
    build_adsp_library_path,
    build_remote_command,
    detect_build_id,
    farf_remote_path,
    filter_logcat_for_pid,
    main,
    parse_input_list,
    parse_profile_timings,
    qnn_run_pid,
    require_same_build_id,
    resolve_input_list,
    verify_toolchain,
    write_farf_config,
)


class TestClassifyDeviceRun(unittest.TestCase):
    def test_fastrpc_watchdog_is_timeout_not_latency(self):
        result = classify_device_run(
            stdout="Graph Execution failure",
            logcat="Intentional crash triggered using remote session control timeout: 10000",
            output=None,
        )
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.timeout_ms, 10000)
        self.assertIsNone(result.graph_execute_us)
        self.assertEqual(result.output_count, 0)

    def test_smoke_pass_with_16_finite_outputs(self) -> None:
        result = classify_device_run(
            stdout="qnn-net-run completed\n",
            logcat="",
            output=[0.25] * 16,
            expected_output_shape=(1, 16),
        )
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.output_count, 16)
        self.assertTrue(result.finite)
        self.assertIsNone(result.timeout_ms)

    def test_timeout_wins_over_downstream_ssr(self) -> None:
        """真实 CAM++ logcat 同时有看门狗与 SSR；根因必须是 timeout。"""
        result = classify_device_run(
            stdout="Graph Execution failure",
            logcat=(
                "gpe_execute_novalidate called: n_in=1 n_out=1\n"
                "Intentional crash triggered using remote session control "
                "for libQnnHtpV81Skel.so timeout: 10000 domain: 100000\n"
                "SSR detected on device config {0,0,0}\n"
                "failed in execution with err 1003\n"
            ),
            output=None,
        )
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.timeout_ms, 10000)

    def test_user_pd_rpc_timeout_is_not_watchdog(self) -> None:
        """真实 logcat:113 的 user PD 属性回显不是看门狗证据。"""
        user_pd = (
            "10-20 22:03:16.991 17864 17864 I qnn-net-run: vendor/qcom/proprietary/"
            "adsprpc/src/fastrpc_apps_user.c:6293: Created user PD on domain 100000, "
            "dbg_trace 0x0, enabled attr=> RPC timeout:10000, Dbg Mode:Y, CRC:N, "
            "Unsigned:Y, Signed:N, Adapt QOS:N, PD dump: (Config:N, Dbg:N), "
            "Perf: (Kernel:N, DSP:N), Iregion:N, QTF:N, UAF:N userPD initmem "
            "len:0x500000, Log pkt: N"
        )
        result = classify_device_run(
            stdout="Finished Executing Graphs\n",
            logcat=user_pd,
            output=[0.25] * 16,
            expected_output_shape=(1, 16),
        )
        self.assertEqual(result.status, "pass")
        self.assertIsNone(result.timeout_ms)

    def test_cdsp_crash_report_is_timeout(self) -> None:
        """历史 logcat:739：cdsprpcd 崩溃报告用 `crashed in thread` 标注超时。"""
        crash = (
            '10-20 21:43:23.208  2677  2850 V adsprpc : 68032a:587: CDSP0:[R]: '
            'Process "/frpc/f0589320 qnn-net-run" crashed in thread '
            '"fr/14734/14740/" libQnnHtpV81Skel.so timeout: 10000 domain: 100000 '
            "sc: 0x7020100 handle: 0x2cba90 tidA: 14734 because Application "
            "called qurt_exit() "
        )
        result = classify_device_run(stdout="Graph Execution failure", logcat=crash, output=None)
        self.assertEqual(result.status, "timeout")
        self.assertEqual(result.timeout_ms, 10000)

    def test_err_1003_with_ssr_is_ssr(self) -> None:
        result = classify_device_run(
            stdout="Graph Execution failure",
            logcat=(
                "Graph campplus_w8a16_static_stats failed in execution with err 1003\n"
                "SSR detected on device config {0,0,0}\n"
            ),
            output=None,
        )
        self.assertEqual(result.status, "ssr")
        self.assertIsNone(result.timeout_ms)

    def test_context_load_failure(self) -> None:
        result = classify_device_run(
            stdout="Error: Failed to load context binary\n",
            logcat="QnnDsp <E> Failed to load context binary\n",
            output=None,
        )
        self.assertEqual(result.status, "load_error")

    def test_missing_output_is_not_pass(self) -> None:
        result = classify_device_run(
            stdout="qnn-net-run completed\n",
            logcat="",
            output=None,
        )
        self.assertEqual(result.status, "execute_error")
        self.assertFalse(result.finite)

    def test_non_finite_output_rejected(self) -> None:
        output = [0.0] * 191 + [float("nan")]
        result = classify_device_run(stdout="", logcat="", output=output)
        self.assertEqual(result.status, "execute_error")
        self.assertFalse(result.finite)
        self.assertEqual(result.output_count, 192)

    def test_wrong_element_count_rejected(self) -> None:
        result = classify_device_run(stdout="", logcat="", output=[0.0] * 191)
        self.assertEqual(result.status, "execute_error")
        self.assertEqual(result.output_count, 191)

    def test_negative_infinity_is_not_finite(self) -> None:
        result = classify_device_run(
            stdout="", logcat="", output=[0.0] * 191 + [-math.inf]
        )
        self.assertEqual(result.status, "execute_error")
        self.assertFalse(result.finite)


class TestBuildConsistency(unittest.TestCase):
    def test_detect_build_id_reads_embedded_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "runner"
            binary.write_bytes(b"\x7fELF junk v2.51.1.261002102551 tail")
            self.assertEqual(detect_build_id(binary), "v2.51.1.261002102551")

    def test_detect_build_id_rejects_unversioned_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "runner"
            binary.write_bytes(b"\x7fELF no version here")
            with self.assertRaisesRegex(ValueError, "build ID"):
                detect_build_id(binary)

    def test_build_id_mismatch_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "build ID"):
            require_same_build_id(
                "v2.51.1.261002102551",
                {
                    "context": "v2.51.1.261002102551",
                    "libQnnHtp.so": "v2.47.0.260601",
                },
            )

    def test_matching_build_ids_pass(self) -> None:
        require_same_build_id(
            "v2.51.1.261002102551",
            {"context": "v2.51.1.261002102551", "qnn-net-run": "v2.51.1.261002102551"},
        )

    def test_unversioned_system_lib_does_not_break_toolchain_check(self) -> None:
        """libQnnSystem.so 不内嵌版本串；同 root 内其余四件一致即可放行。"""
        build_id = "v2.51.1.261002102551"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative, name in TOOLCHAIN_LAYOUT:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = b"\x7fELF " + (build_id.encode("ascii") if name in TOOLCHAIN_VERSIONED else b"")
                path.write_bytes(payload)
            toolchain = QairtToolchain(root=root, build_id=build_id)
            verify_toolchain(toolchain, build_id)


class TestAdbParsing(unittest.TestCase):
    def test_parse_input_list_resolves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "input.raw").write_bytes(b"\x00" * 8)
            listing = root / "input-list.txt"
            listing.write_text(
                "# comment\nx:=input.raw\n\ny:=C:/data/y.raw\n", encoding="ascii"
            )
            entries = parse_input_list(listing)
        self.assertEqual(entries[0][0], "x")
        self.assertEqual(entries[0][1], root / "input.raw")
        self.assertEqual(entries[1][0], "y")
        self.assertEqual(entries[1][1], Path("C:/data/y.raw"))

    def test_remote_command_keeps_watchdog_untouched(self) -> None:
        command = build_remote_command(
            "/data/local/tmp/nanolaos-qnn/run-1", 1, "basic", "default"
        )
        self.assertIn("cd /data/local/tmp/nanolaos-qnn/run-1", command)
        self.assertIn("--retrieve_context ./context.bin", command)
        self.assertIn("--input_list ./input-list.txt", command)
        self.assertIn("--num_inferences 1", command)
        self.assertIn("--log_level verbose", command)
        self.assertIn("LD_LIBRARY_PATH=.", command)
        self.assertIn('ADSP_LIBRARY_PATH=".', command)
        self.assertIn(";/vendor/lib/rfsa/adsp", command)
        self.assertNotIn("--timeout", command)
        self.assertNotIn("rpctimeout", command)

    def test_farf_config_content_and_search_placement(self) -> None:
        """farf 必须落在 ADSP 搜索路径（cwd）里；只写本地文件不算数。"""
        remote = "/data/local/tmp/nanolaos-qnn/run-1"
        with tempfile.TemporaryDirectory() as tmp:
            path = write_farf_config(Path(tmp))
            content = path.read_text(encoding="ascii").strip()
        self.assertEqual(path.name, FARF_CONFIG_NAME)
        self.assertEqual(path.name, "qnn-net-run.farf")
        self.assertEqual(content, FARF_CONFIG_MASK)
        self.assertEqual(int(content, 16) & 0x01, 0x01)  # DEBUG 位 → [DU]

        target = farf_remote_path(remote)
        self.assertEqual(target, f"{remote}/qnn-net-run.farf")
        self.assertEqual(target.rsplit("/", 1)[0], remote)
        search = build_adsp_library_path(remote).split(";")
        self.assertEqual(search[0], ".")
        self.assertIn(remote, search)  # 文件所在目录在复合搜索串里
        for root in ADSP_SEARCH_ROOTS:
            self.assertIn(root, search)
        self.assertIn(target.rsplit("/", 1)[0], search)

    def test_logcat_pid_filter_drops_foreign_processes(self) -> None:
        logcat = "\n".join(
            [
                "10-20 22:03:17.161 17864 17864 V QNN     : event added 1003",
                "10-20 22:03:23.093  1961 17879 I vendor.bytedance.thermalextservice"
                ".service: Created user PD on domain 100000  RPC timeout:10000",
                "10-20 22:03:27.173  2677  2850 V adsprpc : SSR detected on device",
                "10-20 22:03:27.184 17864 17864 E QNN     : Graph campplus_w8a16"
                "_static_stats failed in execution with err 1003",
                '10-20 22:03:27.208  2677  2850 V adsprpc : Process "/frpc/f0589320 '
                'qnn-net-run" crashed in thread "fr/17864/17866/" libQnnHtpV81Skel.so '
                "timeout: 10000",
            ]
        )
        filtered = filter_logcat_for_pid(logcat, 17864)
        self.assertIn("event added 1003", filtered)
        self.assertIn("failed in execution with err 1003", filtered)
        self.assertIn("crashed in thread", filtered)
        self.assertNotIn("thermalextservice", filtered)
        self.assertNotIn("SSR detected", filtered)

    def test_foreign_ssr_lines_do_not_pollute_pass(self) -> None:
        """一次成功运行 + 外部进程 SSR 噪声，过滤后仍必须是 pass。"""
        logcat = "\n".join(
            [
                "10-20 22:03:17.161 17864 17864 V QNN     : Executing Graphs",
                "10-20 22:03:23.093  1961 17879 E vendor.bytedance.thermalextservice"
                ".service: SSR detected on device config {0,0,0}",
                "10-20 22:03:23.094  1961 17879 E vendor.bytedance.thermalextservice"
                ".service: Failed to load context binary",
            ]
        )
        result = classify_device_run(
            stdout="qnn-net-run pid:17864\nFinished Executing Graphs\n",
            logcat=filter_logcat_for_pid(logcat, qnn_run_pid("qnn-net-run pid:17864")),
            output=[0.25] * 16,
            expected_output_shape=(1, 16),
        )
        self.assertEqual(result.status, "pass")
        self.assertIsNone(result.timeout_ms)

    def test_qnn_run_pid_parsed_from_stdout(self) -> None:
        self.assertEqual(qnn_run_pid("qnn-net-run pid:17864\n"), 17864)
        self.assertIsNone(qnn_run_pid("no pid line"))

    def test_parse_profile_timings(self) -> None:
        text = (
            "QNN (load binary) time: 1.5 ms\n"
            "QNN (execute) time: 4726 us\n"
        )
        load_us, execute_us = parse_profile_timings(text)
        self.assertEqual(load_us, 1500)
        self.assertEqual(execute_us, 4726)

    def test_parse_profile_timings_absent(self) -> None:
        self.assertEqual(parse_profile_timings("no timings here"), (None, None))


class TestInputListResolution(unittest.TestCase):
    def test_run_without_input_list_falls_back_to_artifact_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "campplus-w8a16-v2"
            artifact.mkdir()
            candidate = artifact / "input-list-host.txt"
            candidate.write_text("x:=000.raw\n", encoding="ascii")
            self.assertEqual(resolve_input_list(artifact, None, smoke=False), candidate)

    def test_run_without_input_list_falls_back_to_debug_inputs(self) -> None:
        """brief Step 5 的裸命令依赖该回退：artifact 内没有 input_list.txt。"""
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "campplus-w8a16-v2"
            artifact.mkdir()
            debug_root = Path(tmp) / "debug"
            (debug_root / "inputs").mkdir(parents=True)
            fallback = debug_root / "inputs/campplus-input-list-host.txt"
            fallback.write_text("x:=000.raw\n", encoding="ascii")
            with mock.patch.object(device_module, "DEBUG_ROOT", debug_root):
                self.assertEqual(
                    resolve_input_list(artifact, None, smoke=False), fallback
                )

    def test_missing_input_list_reports_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact"
            artifact.mkdir()
            with mock.patch.object(device_module, "DEBUG_ROOT", Path(tmp) / "debug"):
                with self.assertRaisesRegex(FileNotFoundError, "找不到 input list"):
                    resolve_input_list(artifact, None, smoke=False)

    def test_explicit_missing_input_list_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.txt"
            with self.assertRaisesRegex(FileNotFoundError, "input list 不存在"):
                resolve_input_list(Path(tmp), str(missing), smoke=False)

    def test_cli_missing_input_list_exits_2_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(device_module, "DEBUG_ROOT", Path(tmp) / "debug"):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    code = main(["run", "--artifact", tmp, "--serial", "x"])
        self.assertEqual(code, 2)
        self.assertIn("找不到 input list", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
