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


def _reverse_key_order(value):
    """递归反转 dict 键序，用于证明渲染不依赖映射迭代顺序。"""
    if isinstance(value, dict):
        return {key: _reverse_key_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [_reverse_key_order(item) for item in value]
    return value


def _section(report: str, heading: str) -> str:
    start = report.index(heading)
    end = report.find("\n## ", start + 1)
    return report[start:] if end == -1 else report[start:end]


def _columns(report: str, heading: str) -> tuple[str, str]:
    """把一节拆成 `**实测：**` 列与 `**不可得：**` 列。"""
    measured, _, unavailable = _section(report, heading).partition("**不可得：**")
    return measured, unavailable


def _full_pass_record(run_id: str = "run-pass") -> dict:
    return {
        "run_id": run_id,
        "status": "pass",
        "exit_code": 0,
        "output_count": 192,
        "finite": True,
        "graph_execute_us": 41_000,
    }


def _complete_latency() -> dict:
    return {
        "cold_load_p50_ms": 12.5,
        "cold_load_p95_ms": 15.0,
        "graph_p50_ms": 42.0,
        "graph_p95_ms": 45.0,
        "graph_p99_ms": 47.0,
        "end_to_end_p50_ms": 55.0,
        "end_to_end_p95_ms": 60.0,
        "throughput_ips": 18.18,
        "io_p50_ms": 3.0,
        "fbank_p50_ms": 4.0,
        "transfer_p50_ms": 0.5,
        "schedule_p50_ms": 1.0,
    }


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
        shuffled_incident = _reverse_key_order(
            json.loads(json.dumps(_incident_with_timeout(), ensure_ascii=False))
        )
        shuffled_benchmark = _reverse_key_order(
            json.loads(json.dumps(_benchmark_without_success(), ensure_ascii=False))
        )
        second = render_report(shuffled_incident, shuffled_benchmark)
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))

    def test_status_distribution_is_rendered_as_sorted_kv(self):
        report = render_report(_incident_with_timeout(), _benchmark_without_success())
        self.assertIn("config_warning=1", report)
        self.assertNotIn("{'config_warning'", report)

    def test_benchmark_reason_paths_have_no_backslashes(self):
        benchmark = _benchmark_without_success()
        benchmark["reason"] = (
            "缺少 paired embedding 文件："
            "var\\speaker-benchmark\\qnn\\campplus-htp-debug\\embeddings\\fp32.npz"
        )
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertNotIn("\\", report)
        self.assertIn(
            "var/speaker-benchmark/qnn/campplus-htp-debug/embeddings/fp32.npz", report
        )

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
            "io_p50_ms": 3.0,
            "fbank_p50_ms": 4.0,
            "transfer_p50_ms": 0.5,
            "schedule_p50_ms": 1.0,
        }
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("42.000 ms", report)
        self.assertIn("18.180 IPS", report)

    def test_latency_section_never_composes_unmeasured_end_to_end(self):
        benchmark = _benchmark_without_success()
        benchmark["latency"] = {
            "cold_load_p50_ms": 12.5,
            "cold_load_p95_ms": 15.0,
            "graph_p50_ms": 42.0,
            "graph_p95_ms": 45.0,
            "graph_p99_ms": 47.0,
            "end_to_end_p50_ms": None,
            "end_to_end_p95_ms": None,
            "throughput_ips": None,
            "io_p50_ms": None,
            "fbank_p50_ms": None,
            "transfer_p50_ms": None,
            "schedule_p50_ms": None,
        }
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("42.000 ms", report)
        self.assertIn("| 端到端 p50 | 不可得 |", report)
        self.assertIn("| 吞吐 | 不可得 |", report)
        self.assertIn("| runner I/O p50 | 不可得 |", report)
        self.assertNotIn("实测组成项之和", report)

    def test_soak_none_values_render_as_unavailable(self):
        benchmark = _benchmark_without_success()
        benchmark["soak"] = {
            "duration_s": 1800,
            "successful_runs": 1700,
            "failed_runs": 100,
            "max_battery_temp_c": None,
            "max_skin_temp_c": None,
            "median_graph_ms": None,
            "final_graph_ms": 21.0,
        }
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("| battery 最高温 | 不可得 |", report)
        self.assertIn("| 中位 graph | 不可得 |", report)
        self.assertIn("21.000 ms", report)


class TestReportEvidenceDerivation(unittest.TestCase):
    def test_matrix_sentence_counts_rows_without_metadata(self):
        incident = _incident_with_timeout()
        incident["matrix"] = [
            {
                "variant_id": "with-metadata",
                "kind": "full",
                "stage": "compiler",
                "status": "config_warning",
                "metadata": {
                    "build_id": "v2.51.1.261002102551",
                    "soc_model": 87,
                    "dsp_arch": 81,
                    "input_shape": [1, 80, 298],
                    "output_shape": [1, 192],
                },
                "sha256": {"context": "a" * 64},
            },
            {
                "variant_id": "without-metadata",
                "kind": "smoke",
                "stage": "eligibility",
                "status": "metadata_rejected",
                "metadata": None,
                "sha256": {"context": "c" * 64},
            },
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("2 行离线构建产物", report)
        self.assertIn("1 行没有元数据", report)
        self.assertNotIn("每行都有", report)

    def test_probe_table_exposes_missing_context_hash(self):
        incident = _incident_with_timeout()
        incident["isolation"] = {
            "status": "awaiting_device",
            "interval": None,
            "awaiting_interval": [0, 3101],
            "node_count": 3101,
            "reason": "设备不在 adb",
            "probes": [
                {
                    "probe_id": "prefix-a",
                    "kind": "prefix",
                    "node_interval": [0, 49],
                    "semantic_output_shape": [1, 320, 298],
                    "context_sha256": "d" * 64,
                    "graph_sha256": "e" * 64,
                    "device": None,
                },
                {
                    "probe_id": "prefix-b",
                    "kind": "prefix",
                    "node_interval": [0, 3076],
                    "semantic_output_shape": [1, 512, 149],
                    "context_sha256": None,
                    "graph_sha256": "f" * 64,
                    "device": None,
                },
            ],
        }
        report = render_report(incident, _benchmark_without_success())
        self.assertNotIn("已全部落盘", report)
        self.assertIn("1 个 probe 缺少 context SHA-256", report)
        self.assertIn("d" * 64, report)
        self.assertIn("f" * 64, report)

    def test_fix_section_reads_partition_parity_and_layout(self):
        incident = _incident_with_timeout()
        incident["partition"] = {
            "status": "device_unavailable",
            "selection_basis": "smallest_intermediate_only",
            "solves_root_cause": "unproven",
            "parity": {"inputs": 40, "max_abs": 0.0, "mode": "exact", "passed": True},
            "layout": {
                "verified": True,
                "transpose_axes": [0, 1],
                "samples": 3,
                "round_trip_max_abs": 0.0,
            },
            "plan": {
                "cut": {
                    "node_index": 3093,
                    "tensor_name": "/xvector/stats/Concat_output_0",
                    "shape": [1, 1024],
                },
                "transfer_bytes": 4096,
            },
        }
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("40 条真实张量", report)
        self.assertIn("max_abs=0", report)
        self.assertIn("布局转置 [0,1] 已验证", report)

    def test_smoke_baseline_renders_only_when_recorded(self):
        benchmark = _benchmark_without_success()
        benchmark["smoke_baseline"] = {
            "graph_us": 4726,
            "io_us": 5080,
            "max_abs": 3.0517578125e-05,
        }
        benchmark["static_stats_parity"] = {"frames": 149, "inputs": 40, "max_abs": 0.0}
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("4.726 ms", report)
        self.assertIn("3.0517578125e-05", report)
        self.assertIn("149 帧", report)

    def test_absent_evidence_never_prints_measured_numbers(self):
        report = render_report({}, {"status": "device_unavailable"})
        self.assertNotIn("4.726 ms", report)
        self.assertNotIn("3.0517578125e-05", report)
        self.assertNotIn("149 帧", report)
        self.assertNotIn("40 条真实张量", report)
        self.assertIn("不可得", report)

    def test_status_sentences_follow_recovered_device_evidence(self):
        incident = _incident_with_timeout()
        incident["terminal_status"] = "blocked"  # 故意留旧的终态字段
        incident["timeline"] = [
            {
                "run_id": "run-pass",
                "status": "pass",
                "exit_code": 0,
                "output_count": 192,
                "finite": True,
                "graph_execute_us": 41_000,
            }
        ]
        incident["matrix"][0]["status"] = "pass"
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("- **终态：** `pass`", report)
        self.assertIn("完整 192 维 embedding：`pass`", report)
        self.assertNotIn("没有任何一行同时满足", report)
        self.assertNotIn("没有任何一行是 `pass`", report)
        self.assertIn("graph 41.000 ms", report)

    def test_full_pass_evidence_stays_in_measured_column(self):
        incident = _incident_with_timeout()
        incident["timeline"] = [_full_pass_record()]
        benchmark = _benchmark_without_success()
        benchmark["accuracy"] = {
            "clean-6s": {
                "reused_fp32": {
                    "eer": 0.012,
                    "top1": 0.98,
                    "fixed_k_ari": 0.9,
                    "online_ari": 0.85,
                    "cluster_count": 4,
                }
            }
        }
        benchmark["latency"] = _complete_latency()
        report = render_report(incident, benchmark)
        measured, unavailable = _columns(report, "## 1. ")
        self.assertIn("完整 192 维 embedding：`pass`", measured)
        self.assertIn("accuracy", measured)
        self.assertIn("见第 8 节", measured)
        self.assertNotIn("pass", unavailable)
        self.assertNotIn("accuracy", unavailable)
        self.assertNotIn("见第 8 节", unavailable)
        measured7, unavailable7 = _columns(report, "## 7. ")
        self.assertIn("eer=", measured7)
        self.assertNotIn("不计算任何准确率", measured7)
        self.assertNotIn("accuracy", unavailable7)

    def test_graph_only_latency_names_missing_components(self):
        benchmark = _benchmark_without_success()
        benchmark["latency"] = {
            "cold_load_p50_ms": 12.5,
            "cold_load_p95_ms": 15.0,
            "graph_p50_ms": 42.0,
            "graph_p95_ms": 45.0,
            "graph_p99_ms": 47.0,
            "end_to_end_p50_ms": None,
            "end_to_end_p95_ms": None,
            "throughput_ips": None,
            "io_p50_ms": None,
            "fbank_p50_ms": None,
            "transfer_p50_ms": None,
            "schedule_p50_ms": None,
        }
        report = render_report(_incident_with_timeout(), benchmark)
        self.assertIn("缺少的组成项", report)
        self.assertIn("runner I/O（io）", report)
        self.assertIn("CPU FBank（fbank）", report)
        self.assertIn("中间张量搬运（transfer）", report)
        self.assertIn("第二次调度（schedule）", report)

    def test_isolation_section_has_no_double_punctuation(self):
        incident = _incident_with_timeout()
        incident["isolation"]["probes"] = [
            {
                "probe_id": "prefix-a",
                "kind": "prefix",
                "node_interval": [0, 49],
                "semantic_output_shape": [1, 320, 298],
                "context_sha256": "d" * 64,
                "graph_sha256": "e" * 64,
                "device": None,
            },
            {
                "probe_id": "prefix-b",
                "kind": "prefix",
                "node_interval": [0, 3076],
                "semantic_output_shape": [1, 512, 149],
                "context_sha256": None,
                "graph_sha256": "f" * 64,
                "device": None,
            },
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertNotIn("。；", report)
        self.assertIn("；其中 1 个 probe 缺少 context SHA-256。", report)

    def test_blocked_embedding_sentence_derives_timeline_statuses(self):
        incident = _incident_with_timeout()
        incident["timeline"] = [
            {
                "run_id": "run-execute-error",
                "status": "execute_error",
                "exit_code": 1,
                "output_count": 0,
                "finite": False,
            },
            {
                "run_id": "run-load-error",
                "status": "load_error",
                "exit_code": 1,
                "output_count": 0,
                "finite": False,
            },
            {
                "run_id": "run-ssr",
                "status": "ssr",
                "exit_code": 17,
                "output_count": 0,
                "finite": False,
            },
            {
                "run_id": "run-smoke",
                "status": "pass",
                "exit_code": 0,
                "output_count": 16,
                "finite": True,
            },
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("execute_error=1", report)
        self.assertIn("load_error=1", report)
        self.assertIn("ssr=1", report)
        self.assertNotIn("全部 timeout/SSR", report)

    def test_matrix_sentence_counts_rows_with_build_id(self):
        incident = _incident_with_timeout()
        incident["matrix"] = [
            {
                "variant_id": "with-build-id",
                "kind": "full",
                "stage": "compiler",
                "status": "config_warning",
                "metadata": {
                    "build_id": "v2.51.1.261002102551",
                    "soc_model": 87,
                    "dsp_arch": 81,
                },
                "sha256": {"context": "a" * 64},
            },
            {
                "variant_id": "metadata-without-build-id",
                "kind": "smoke",
                "stage": "eligibility",
                "status": "config_warning",
                "metadata": {"soc_model": 87, "dsp_arch": 81},
                "sha256": {"context": "c" * 64},
            },
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("2 行有元数据", report)
        self.assertIn("1 行带 build ID", report)
        self.assertNotIn("2 行有 build ID", report)

    def test_smoke_pass_never_renders_graph_time(self):
        incident = _incident_with_timeout()
        incident["timeline"] = [
            {
                "run_id": "run-smoke",
                "status": "pass",
                "exit_code": 0,
                "output_count": 16,
                "finite": True,
                "graph_execute_us": 12_000,
            }
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertNotIn("graph 12.000 ms", report)
        self.assertIn("不是 192 维有限 embedding", report)

    def test_pass_label_depends_on_persisted_graph_time(self):
        incident = _incident_with_timeout()
        incident["timeline"] = [
            {
                "run_id": "run-pass",
                "status": "pass",
                "exit_code": 0,
                "output_count": 16,
                "finite": True,
                "graph_execute_us": None,
            }
        ]
        report = render_report(incident, _benchmark_without_success())
        self.assertIn("本次没有持久化 graph 时间", report)
        self.assertIn("没有任何一行同时满足", report)


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
