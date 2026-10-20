# tests/test_speaker_qnn_report.py
"""CAM++ SM8845 排障报告的确定性渲染与漂移校验。

口径（2026-10-20）：真机没有任何 CAM++ 成功 embedding，报告终态必须是
`blocked`；任何 `timeout`/`ssr` 只能写成 FastRPC timeout / CDSP SSR，
绝不能渲染成"推理延迟"数字。本测试只验证渲染逻辑与 CLI 退出码，
夹具里的数值不是真机结果。
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.speaker_qnn.report import (  # noqa: E402
    DEFAULT_OUTPUT,
    collect_incident,
    load_benchmark,
    main,
    render_report,
)


def _incident_with_timeout() -> dict:
    return {
        "schema_version": 1,
        "kind": "campplus_htp_incident",
        "terminal_status": "blocked",
        "device": {"available": False, "serial": None},
        "toolchains": [
            {
                "build_id": "v2.51.1.261002102551",
                "root": "var/speaker-benchmark/qnn/sdk-2.51/qairt/2.51.1.261002",
            }
        ],
        "matrix_summary": {
            "full_graph_rows": 1,
            "full_graph_variants": 1,
            "statuses": {"config_warning": 1},
        },
        "matrix": [
            {
                "variant_id": "2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats",
                "kind": "full",
                "status": "config_warning",
                "metadata": {
                    "build_id": "v2.51.1.261002102551",
                    "soc_model": 87,
                    "dsp_arch": 81,
                    "input_shape": [1, 80, 298],
                    "output_shape": [1, 192],
                },
                "sha256": {"context": "a" * 64, "model": "b" * 64},
                "warning": "92.9ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66",
                "reason": "context 配置告警未闭环，未上机",
            }
        ],
        "timeline": [
            {
                "run_id": "20261020-220315-campplus-w8a16-v2",
                "status": "ssr",
                "exit_code": 17,
                "output_count": 0,
                "finite": False,
                "timeout_ms": None,
            }
        ],
        "isolation": {
            "status": "awaiting_device",
            "interval": None,
            "awaiting_interval": [0, 3101],
            "reason": "设备不在 adb，二分未取得真机证据（awaiting_device）",
        },
        "rewrite": {
            "status": "blocked_on_isolated_interval",
            "reason": "isolation 状态为 awaiting_device，没有已验证的节点区间",
        },
        "partition": {
            "status": "device_unavailable",
            "selection_basis": "smallest_intermediate_only",
            "solves_root_cause": "unproven",
            "candidate_upgrade": {"eligible": False, "reason": "isolation 尚未验证"},
        },
    }


def _benchmark_without_success() -> dict:
    return {
        "schema_version": 1,
        "kind": "campplus_w8a16_benchmark",
        "status": "device_unavailable",
        "reason": "缺少 paired embedding 文件：embeddings/fp32.npz",
        "parity": None,
        "gate": None,
        "accuracy": None,
        "embeddings": {"fp32": None, "w8a16": None},
        "latency": None,
        "soak": None,
        "threshold_recalibration": "blocked",
        "product_admission": "blocked",
        "task_matrix": ["clean-6s", "clean-3s"],
        "device_runs": [
            {
                "path": "var/speaker-benchmark/qnn/campplus-htp-debug/device-runs/"
                "20261020-220315-campplus-w8a16-v2/result.json",
                "status": "ssr",
                "exit_code": 17,
                "output_count": 0,
                "finite": False,
                "timeout_ms": None,
            }
        ],
        "pending": ["首次成功门禁：同一真实输入连续 30 次"],
    }


def _minimal_root(root: Path) -> Path:
    """最小证据根：只有 matrix/isolation/rewrite/partition/benchmark。"""
    probe_dir = root / "probes"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (root / "matrix.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "variants": _incident_with_timeout()["matrix"],
                "summary": _incident_with_timeout()["matrix_summary"],
                "toolchains": _incident_with_timeout()["toolchains"],
            }
        ),
        encoding="utf-8",
    )
    (probe_dir / "isolation.json").write_text(
        json.dumps(_incident_with_timeout()["isolation"]), encoding="utf-8"
    )
    (probe_dir / "rewrite.json").write_text(
        json.dumps(_incident_with_timeout()["rewrite"]), encoding="utf-8"
    )
    partition_dir = probe_dir / "partition-3093"
    partition_dir.mkdir(parents=True, exist_ok=True)
    (partition_dir / "partition.json").write_text(
        json.dumps(_incident_with_timeout()["partition"]), encoding="utf-8"
    )
    (root / "benchmark.json").write_text(
        json.dumps(_benchmark_without_success()), encoding="utf-8"
    )
    return root


class TestReportRendering(unittest.TestCase):
    def test_report_never_uses_timeout_as_latency(self):
        report = render_report(_incident_with_timeout(), _benchmark_without_success())
        self.assertNotIn("10,000 ms 推理延迟", report)
        self.assertNotIn("10000 ms 推理延迟", report)
        self.assertIn("FastRPC timeout", report)

    def test_timeout_and_ssr_are_labelled_as_watchdog_events(self):
        report = render_report(_incident_with_timeout(), _benchmark_without_success())
        self.assertIn("CDSP SSR", report)
        self.assertIn("10 秒看门狗", report)
        self.assertIn("不是推理延迟", report)

    def test_report_is_deterministic(self):
        first = render_report(_incident_with_timeout(), _benchmark_without_success())
        second = render_report(_incident_with_timeout(), _benchmark_without_success())
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))

    def test_report_separates_measured_from_unavailable(self):
        report = render_report(_incident_with_timeout(), _benchmark_without_success())
        for section in (
            "## 1. 实测与不可得分列",
            "## 2. 事件时间线",
            "## 3. 版本与配置矩阵",
            "## 4. 隔离区间",
            "## 5. 选定修复 / 分区",
            "## 6. Artifact 哈希",
            "## 7. Paired accuracy",
            "## 8. 冷/暖延迟与吞吐",
            "## 9. 30 分钟 soak",
        ):
            self.assertIn(section, report)
        self.assertIn("**实测：**", report)
        self.assertIn("**不可得：**", report)
        self.assertIn("blocked", report)
        self.assertIn("awaiting_device", report)
        self.assertIn("unproven", report)

    def test_report_carries_matrix_hashes_and_gate_status(self):
        report = render_report(_incident_with_timeout(), _benchmark_without_success())
        self.assertIn("2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats", report)
        self.assertIn("a" * 64, report)
        self.assertIn("b" * 64, report)
        self.assertIn("socModel=87", report)
        self.assertIn("dspArch=81", report)
        self.assertIn("config_warning", report)

    def test_report_tolerates_empty_incident(self):
        report = render_report({}, {"status": "device_unavailable"})
        self.assertIn("blocked", report)
        self.assertIn("不可得", report)

    def test_numeric_latency_only_rendered_when_present(self):
        benchmark = _benchmark_without_success()
        benchmark["latency"] = {
            "cold_load_p50_ms": 12.5,
            "cold_load_p95_ms": 15.0,
            "graph_p50_ms": 42.0,
            "graph_p95_ms": 45.0,
            "graph_p99_ms": 47.0,
            "end_to_end_p50_ms": 55.0,
            "end_to_end_p95_ms": 60.0,
            "throughput_ips": 18.18,
        }
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("42.000 ms", report)
        self.assertIn("18.180 IPS", report)


class TestReportCollection(unittest.TestCase):
    def test_collect_incident_reads_probe_evidence(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = _minimal_root(Path(raw_root))
            incident = collect_incident(root)
            self.assertEqual(incident["terminal_status"], "blocked")
            self.assertEqual(incident["isolation"]["status"], "awaiting_device")
            self.assertIsNone(incident["isolation"]["interval"])
            self.assertEqual(incident["partition"]["status"], "device_unavailable")
            self.assertEqual(len(incident["matrix"]), 1)
            self.assertEqual(incident["matrix"][0]["status"], "config_warning")

    def test_collect_incident_tolerates_missing_files(self):
        with tempfile.TemporaryDirectory() as raw_root:
            incident = collect_incident(Path(raw_root))
            self.assertEqual(incident["terminal_status"], "blocked")
            self.assertEqual(incident["matrix"], [])
            self.assertIsNone(incident["isolation"])

    def test_collect_incident_counts_device_run_statuses(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = _minimal_root(Path(raw_root))
            run = root / "device-runs" / "20261020-220315-campplus-w8a16-v2"
            run.mkdir(parents=True)
            (run / "result.json").write_text(
                json.dumps(
                    {
                        "status": "ssr",
                        "exit_code": 17,
                        "output_count": 0,
                        "finite": False,
                        "timeout_ms": None,
                    }
                ),
                encoding="utf-8",
            )
            incident = collect_incident(root)
            self.assertEqual(
                [record["run_id"] for record in incident["timeline"]],
                ["20261020-220315-campplus-w8a16-v2"],
            )
            self.assertEqual(incident["timeline"][0]["status"], "ssr")

    def test_load_benchmark_tolerates_missing_file(self):
        with tempfile.TemporaryDirectory() as raw_root:
            benchmark = load_benchmark(Path(raw_root))
            self.assertEqual(benchmark["status"], "device_unavailable")


class TestReportCli(unittest.TestCase):
    def test_cli_writes_then_check_passes(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = _minimal_root(Path(raw_root) / "evidence")
            output = Path(raw_root) / "report.md"
            self.assertEqual(main(["--root", str(root), "--output", str(output)]), 0)
            self.assertTrue(output.is_file())
            self.assertEqual(
                main(["--root", str(root), "--output", str(output), "--check"]), 0
            )

    def test_cli_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = _minimal_root(Path(raw_root) / "evidence")
            output = Path(raw_root) / "report.md"
            self.assertEqual(main(["--root", str(root), "--output", str(output)]), 0)
            output.write_text(
                output.read_text(encoding="utf-8") + "\n漂移\n", encoding="utf-8"
            )
            self.assertEqual(
                main(["--root", str(root), "--output", str(output), "--check"]), 1
            )

    def test_cli_check_returns_two_when_report_is_missing(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = _minimal_root(Path(raw_root) / "evidence")
            missing = Path(raw_root) / "missing.md"
            self.assertEqual(
                main(["--root", str(root), "--output", str(missing), "--check"]), 2
            )

    def test_default_output_is_the_committed_report(self):
        self.assertEqual(
            DEFAULT_OUTPUT.relative_to(REPO).as_posix(),
            "docs/research/2026-10-20-campplus-qnn-sm8845.md",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
