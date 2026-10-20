# tests/test_speaker_qnn_benchmark.py
"""CAM++ W8A16 embedding parity 与任务准确率门禁。

口径（2026-10-20）：真机至今没有产出过任何 192 维 embedding（全部
`ssr`/`timeout`）。因此本模块只验证数值/门禁/证据逻辑；没有 pass 的
真机运行证据时 `evaluate_accuracy` 必须抛 `DeviceUnavailableError`，
`collect_benchmark` 必须写 `device_unavailable` 记录且不含任何
EER/Top-1/ARI 数字。测试里的数组只是算法夹具，不冒充真机结果。

    C:/Users/Admin/Documents/Trae-CN/pyProj/LAOS/var/speaker-benchmark/.venv/Scripts/python.exe \
        -m unittest tests.test_speaker_qnn_benchmark -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import numpy as np
except ImportError:  # 主库 discover 环境没有 numpy
    np = None

from scripts.speaker_qnn.benchmark import (  # noqa: E402
    EMBEDDING_DIM,
    RECALIBRATED_W8A16_THRESHOLD,
    REUSED_FP32_THRESHOLD,
    STATUS_DEVICE_UNAVAILABLE,
    STATUS_GATE_FAILED,
    STATUS_PASS,
    AccuracyMetrics,
    DeviceUnavailableError,
    EmbeddingParity,
    adjusted_rand_index,
    collect_benchmark,
    dequantize_embedding,
    embedding_gate,
    evaluate_accuracy,
    evaluate_embedding_parity,
    identification_top1,
    l2_normalize,
    load_embedding_set,
    online_cluster,
    round_robin_order,
    write_embedding_set,
)

requires_numpy = unittest.skipIf(np is None, "主库测试环境没有 numpy")


def _unit(index: int, size: int = EMBEDDING_DIM) -> "np.ndarray":
    vector = np.zeros(size, dtype=np.float64)
    vector[index] = 1.0
    return vector


def _fixture_embeddings(speakers: int = 4, per_speaker: int = 4, noise: float = 1e-4):
    """每个说话人一个正交基向量加同量级噪声；嵌入天然可分。"""
    vectors = []
    labels = []
    for speaker in range(speakers):
        for item in range(per_speaker):
            vectors.append(_unit(speaker) + noise * _unit(per_speaker * 8 + item))
            labels.append(f"S{speaker + 1}")
    return np.asarray(vectors), labels


def _speakers(count: int = 4) -> list[str]:
    return [f"S{index + 1}" for index in range(count)]


def _item_ids(count: int = 4, per_speaker: int = 4) -> list[str]:
    return [
        f"S{speaker + 1}-{item}.wav"
        for speaker in range(count)
        for item in range(per_speaker)
    ]


def _manifest_payload(speakers: list[str], files_per_speaker: int = 4) -> dict:
    return {
        "selection": "unit-test fixture",
        "speakers": [
            {"speaker": speaker, "files": [f"{speaker}-{index}.wav" for index in range(files_per_speaker)]}
            for speaker in speakers
        ],
        "conditions": {"clean-6s": [6.0, None]},
    }


def _write_result(root: Path, name: str, payload: dict) -> Path:
    path = root / "device-runs" / name / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _pass_result() -> dict:
    return {
        "status": "pass",
        "exit_code": 0,
        "output_path": "output.raw",
        "output_count": EMBEDDING_DIM,
        "finite": True,
        "context_load_us": 1000,
        "graph_execute_us": 2000,
        "timeout_ms": None,
        "evidence_paths": [],
    }


def _paired_manifest(path: Path, speakers: list[str], device_runs: list[str]) -> Path:
    payload = _manifest_payload(speakers)
    payload["w8a16_provenance"] = {"device_runs": device_runs}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _numeric_keys(payload) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.add(str(key))
            found |= _numeric_keys(value)
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found |= _numeric_keys(item)
    return found


ACCURACY_KEYS = {"eer", "top1", "fixed_k_ari", "online_ari", "cluster_count"}


class TestEmbeddingGate(unittest.TestCase):
    @requires_numpy
    def test_embedding_gate_requires_median_and_tail(self):
        result = embedding_gate(
            EmbeddingParity(
                median_cosine=0.995,
                p01_cosine=0.980,
                minimum_cosine=0.90,
                mean_l2=0.0,
                p95_l2=0.0,
            )
        )
        self.assertTrue(result.passed)

    @requires_numpy
    def test_gate_fails_below_median_boundary_but_keeps_metrics(self):
        parity = EmbeddingParity(
            median_cosine=0.9949999,
            p01_cosine=0.999,
            minimum_cosine=0.999,
            mean_l2=0.01,
            p95_l2=0.02,
        )
        result = embedding_gate(parity)
        self.assertFalse(result.passed)
        self.assertIn("median", result.reason)
        payload = result.to_dict()
        self.assertEqual(payload["parity"], parity.to_dict())
        self.assertAlmostEqual(payload["parity"]["median_cosine"], 0.9949999)

    @requires_numpy
    def test_gate_fails_below_p01_boundary(self):
        result = embedding_gate(
            EmbeddingParity(
                median_cosine=0.999,
                p01_cosine=0.9799999,
                minimum_cosine=0.5,
                mean_l2=0.0,
                p95_l2=0.0,
            )
        )
        self.assertFalse(result.passed)
        self.assertIn("p01", result.reason)

    @requires_numpy
    def test_gate_rejects_non_finite_parity(self):
        result = embedding_gate(
            EmbeddingParity(
                median_cosine=float("nan"),
                p01_cosine=1.0,
                minimum_cosine=1.0,
                mean_l2=0.0,
                p95_l2=0.0,
            )
        )
        self.assertFalse(result.passed)
        self.assertIn("非有限", result.reason)


class TestEmbeddingParity(unittest.TestCase):
    @requires_numpy
    def test_identical_embeddings_are_exact(self):
        embeddings, _ = _fixture_embeddings()
        parity = evaluate_embedding_parity(embeddings, embeddings)
        self.assertEqual(parity.median_cosine, 1.0)
        self.assertEqual(parity.p01_cosine, 1.0)
        self.assertEqual(parity.minimum_cosine, 1.0)
        self.assertEqual(parity.mean_l2, 0.0)
        self.assertEqual(parity.p95_l2, 0.0)

    @requires_numpy
    def test_scale_only_drift_shows_in_l2_not_cosine(self):
        embeddings, _ = _fixture_embeddings()
        scaled = embeddings * 0.5
        parity = evaluate_embedding_parity(embeddings, scaled)
        self.assertAlmostEqual(parity.median_cosine, 1.0, places=12)
        self.assertAlmostEqual(parity.minimum_cosine, 1.0, places=12)
        self.assertGreater(parity.mean_l2, 0.0)

    @requires_numpy
    def test_row_count_misalignment_is_rejected(self):
        embeddings, _ = _fixture_embeddings()
        with self.assertRaises(ValueError):
            evaluate_embedding_parity(embeddings, embeddings[:-1])

    @requires_numpy
    def test_empty_output_is_rejected(self):
        empty = np.zeros((0, EMBEDDING_DIM))
        with self.assertRaises(ValueError):
            evaluate_embedding_parity(empty, empty)

    @requires_numpy
    def test_one_dimensional_input_is_rejected(self):
        vector = _unit(0)
        with self.assertRaises(ValueError):
            evaluate_embedding_parity(vector, vector)

    @requires_numpy
    def test_zero_vector_is_rejected(self):
        good = np.stack([_unit(0), _unit(1)])
        zero = good.copy()
        zero[1] = 0.0
        with self.assertRaises(ValueError) as caught:
            evaluate_embedding_parity(good, zero)
        self.assertIn("零向量", str(caught.exception))

    @requires_numpy
    def test_nan_and_inf_are_rejected(self):
        good = np.stack([_unit(0), _unit(1)])
        nan = good.copy()
        nan[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            evaluate_embedding_parity(good, nan)
        inf = good.copy()
        inf[0, 0] = float("inf")
        with self.assertRaises(ValueError):
            evaluate_embedding_parity(inf, good)

    @requires_numpy
    def test_parity_reports_p01_as_first_percentile(self):
        # 100 条里 5 条翻转方向：p01 必须落进坏行区间，median 仍为 1。
        embeddings = np.stack([_unit(0) for _ in range(100)])
        drifted = embeddings.copy()
        drifted[:5] = _unit(1)
        parity = evaluate_embedding_parity(embeddings, drifted)
        self.assertAlmostEqual(parity.minimum_cosine, 0.0, places=12)
        self.assertLess(parity.p01_cosine, 0.1)
        self.assertAlmostEqual(parity.median_cosine, 1.0, places=12)


class TestDequantization(unittest.TestCase):
    @requires_numpy
    def test_scale_and_offset_follow_qnn_encoding(self):
        raw = np.asarray([[0, 127, 254, 100]], dtype=np.uint16)
        values = dequantize_embedding(raw, scale=0.5, offset=127, embedding_dim=4)
        np.testing.assert_allclose(values, [[-63.5, 0.0, 63.5, -13.5]])
        self.assertEqual(values.dtype, np.float32)

    @requires_numpy
    def test_per_channel_scale_and_offset(self):
        raw = np.asarray([[100, 200]], dtype=np.int16)
        values = dequantize_embedding(
            raw,
            scale=np.asarray([0.5, 0.25]),
            offset=np.asarray([100, 200]),
            embedding_dim=2,
        )
        np.testing.assert_allclose(values, [[0.0, 0.0]])

    @requires_numpy
    def test_non_positive_scale_is_rejected(self):
        raw = np.asarray([[1, 2]], dtype=np.uint16)
        for scale in (0.0, -1.0):
            with self.assertRaises(ValueError):
                dequantize_embedding(raw, scale=scale, offset=0, embedding_dim=2)

    @requires_numpy
    def test_non_finite_scale_is_rejected(self):
        raw = np.asarray([[1, 2]], dtype=np.uint16)
        with self.assertRaises(ValueError):
            dequantize_embedding(raw, scale=float("nan"), offset=0, embedding_dim=2)

    @requires_numpy
    def test_wrong_embedding_dim_is_rejected(self):
        raw = np.asarray([[1, 2, 3]], dtype=np.uint16)
        with self.assertRaises(ValueError):
            dequantize_embedding(raw, scale=1.0, offset=0, embedding_dim=2)

    @requires_numpy
    def test_l2_normalize_zero_row_is_rejected(self):
        vectors = np.stack([_unit(0), np.zeros(EMBEDDING_DIM)])
        with self.assertRaises(ValueError):
            l2_normalize(vectors)


class TestAccuracyMetrics(unittest.TestCase):
    @requires_numpy
    def test_identical_embeddings_are_perfect(self):
        embeddings, labels = _fixture_embeddings()
        self.assertEqual(identification_top1(embeddings, labels), 1.0)
        predicted = np.asarray(labels)[list(round_robin_order(labels))]
        self.assertEqual(adjusted_rand_index(predicted, predicted), 1.0)

    @requires_numpy
    def test_evaluate_accuracy_reports_both_thresholds(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _write_result(root, "run-pass", _pass_result())
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            metrics = evaluate_accuracy(embeddings, embeddings, manifest)

            self.assertEqual(
                set(metrics),
                {REUSED_FP32_THRESHOLD, RECALIBRATED_W8A16_THRESHOLD},
            )
            for value in metrics.values():
                self.assertIsInstance(value, AccuracyMetrics)
                self.assertEqual(value.eer, 0.0)
                self.assertEqual(value.top1, 1.0)
                self.assertEqual(value.fixed_k_ari, 1.0)
                self.assertEqual(value.cluster_count, len(_speakers()))

    @requires_numpy
    def test_reused_threshold_override_changes_online_clustering(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _write_result(root, "run-pass", _pass_result())
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            default = evaluate_accuracy(embeddings, embeddings, manifest)
            reused = evaluate_accuracy(
                embeddings, embeddings, manifest, reused_threshold=2.0
            )
            self.assertEqual(default[RECALIBRATED_W8A16_THRESHOLD].cluster_count, 4)
            # 阈值不可达时每条样本自成簇：证明 reused 与 recalibrated 是两条独立路径。
            self.assertEqual(reused[REUSED_FP32_THRESHOLD].cluster_count, len(embeddings))
            self.assertEqual(
                reused[RECALIBRATED_W8A16_THRESHOLD].cluster_count, 4
            )

    @requires_numpy
    def test_row_misalignment_against_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _write_result(root, "run-pass", _pass_result())
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            with self.assertRaises(ValueError):
                evaluate_accuracy(embeddings[:-1], embeddings, manifest)

    @requires_numpy
    def test_missing_device_provenance_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            manifest = root / "manifest.json"
            payload = _manifest_payload(_speakers())
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(DeviceUnavailableError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertEqual(caught.exception.status, STATUS_DEVICE_UNAVAILABLE)
            self.assertTrue(caught.exception.reason)

    @requires_numpy
    def test_failed_device_run_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            payload = _pass_result()
            payload.update({"status": "ssr", "finite": False, "output_count": 0})
            result_path = _write_result(root, "run-ssr", payload)
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            with self.assertRaises(DeviceUnavailableError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("ssr", caught.exception.reason)

    @requires_numpy
    def test_missing_device_run_file_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), ["device-runs/missing/result.json"]
            )
            with self.assertRaises(DeviceUnavailableError):
                evaluate_accuracy(embeddings, embeddings, manifest)


class TestDeterministicOnlineOrder(unittest.TestCase):
    @requires_numpy
    def test_round_robin_order_starts_from_sorted_speakers(self):
        first = ["S1"] * 3 + ["S2"] * 3
        swapped = ["S2"] * 3 + ["S1"] * 3
        self.assertEqual(round_robin_order(first), (0, 3, 1, 4, 2, 5))
        # 说话人块整体换位后，到达顺序仍按 speaker ID 排序（S1 行先到）。
        self.assertEqual(round_robin_order(swapped), (3, 0, 4, 1, 5, 2))
        self.assertEqual(round_robin_order(first), round_robin_order(first))

    @requires_numpy
    def test_online_clustering_is_repeatable(self):
        embeddings, labels = _fixture_embeddings()
        embeddings = l2_normalize(embeddings)
        first = online_cluster(embeddings, labels, threshold=0.9)
        second = online_cluster(embeddings, labels, threshold=0.9)
        self.assertEqual(first, second)
        self.assertEqual(first[1], 4)
        self.assertEqual(len(first[0]), len(labels))

    @requires_numpy
    def test_swapped_speaker_blocks_give_identical_clustering(self):
        embeddings, labels = _fixture_embeddings(speakers=2, per_speaker=3)
        embeddings = l2_normalize(embeddings)
        blocks = [list(range(0, 3)), list(range(3, 6))]
        swapped = np.concatenate([embeddings[blocks[1]], embeddings[blocks[0]]])
        swapped_labels = labels[3:] + labels[:3]
        original = online_cluster(embeddings, labels, threshold=0.9)
        reordered = online_cluster(swapped, swapped_labels, threshold=0.9)
        self.assertEqual(original[1], reordered[1])
        self.assertEqual(
            adjusted_rand_index(np.asarray(original[0]), np.asarray(reordered[0])), 1.0
        )


class TestEmbeddingSetIO(unittest.TestCase):
    @requires_numpy
    def test_roundtrip_preserves_blocks_and_item_ids(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            path = root / "fp32.npz"
            write_embedding_set(path, {"clean-6s": embeddings}, [f"item-{i}" for i in range(len(embeddings))])
            blocks, item_ids = load_embedding_set(path)
            self.assertEqual(list(blocks), ["clean-6s"])
            np.testing.assert_allclose(blocks["clean-6s"], embeddings, rtol=0, atol=1e-6)
            self.assertEqual(item_ids[0], "item-0")
            self.assertEqual(len(item_ids), len(embeddings))

    @requires_numpy
    def test_missing_item_ids_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "fp32.npz"
            np.savez_compressed(path, **{"clean-6s": np.zeros((2, EMBEDDING_DIM))})
            with self.assertRaises(ValueError):
                load_embedding_set(path)

    @requires_numpy
    def test_wrong_dimension_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "fp32.npz"
            np.savez_compressed(
                path,
                **{"clean-6s": np.zeros((2, 32)), "item_ids": np.asarray(["a", "b"])},
            )
            with self.assertRaises(ValueError):
                load_embedding_set(path)


class TestCollectBenchmark(unittest.TestCase):
    @requires_numpy
    def test_empty_evidence_root_writes_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(_manifest_payload(["S1", "S2"])), encoding="utf-8"
            )
            output = root / "benchmark.json"
            record = collect_benchmark(root, manifest, output=output)
            self.assertEqual(record["status"], STATUS_DEVICE_UNAVAILABLE)
            self.assertIsNone(record["accuracy"])
            self.assertIsNone(record["parity"])
            self.assertIn("embeddings", record["reason"])
            self.assertEqual(
                record["blocked_actions"],
                [
                    "accuracy_evaluation",
                    "threshold_recalibration",
                    "online_clustering",
                    "speed_matrix",
                ],
            )
            self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)
            self.assertTrue(output.is_file())
            json.loads(output.read_text(encoding="utf-8"))

    @requires_numpy
    def test_embeddings_without_pass_run_stay_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            write_embedding_set(
                root / "embeddings" / "fp32.npz",
                {"clean-6s": embeddings},
                _item_ids(),
            )
            _write_result(root, "run-ssr", {"status": "ssr", "finite": False, "output_count": 0})
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(_speakers())), encoding="utf-8")
            record = collect_benchmark(root, manifest)
            self.assertEqual(record["status"], STATUS_DEVICE_UNAVAILABLE)
            self.assertIn("pass", record["reason"])
            self.assertIsNone(record["accuracy"])

    @requires_numpy
    def test_passing_evidence_produces_gated_metrics(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            item_ids = _item_ids()
            write_embedding_set(
                root / "embeddings" / "fp32.npz", {"clean-6s": embeddings}, item_ids
            )
            write_embedding_set(
                root / "embeddings" / "w8a16.npz", {"clean-6s": embeddings}, item_ids
            )
            _write_result(root, "run-pass", _pass_result())
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(_speakers())), encoding="utf-8")

            record = collect_benchmark(root, manifest, output=root / "benchmark.json")
            self.assertEqual(record["status"], STATUS_PASS)
            self.assertAlmostEqual(
                record["parity"]["clean-6s"]["median_cosine"], 1.0, places=12
            )
            self.assertTrue(record["gate"]["passed"])
            self.assertEqual(record["threshold_recalibration"], "completed")
            self.assertIn("clean-6s", record["accuracy"])
            self.assertEqual(
                set(record["accuracy"]["clean-6s"]),
                {REUSED_FP32_THRESHOLD, RECALIBRATED_W8A16_THRESHOLD},
            )

    @requires_numpy
    def test_failed_gate_blocks_accuracy_but_keeps_parity(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            rng = np.random.default_rng(7)
            unrelated = rng.standard_normal(embeddings.shape)
            item_ids = _item_ids()
            write_embedding_set(
                root / "embeddings" / "fp32.npz", {"clean-6s": embeddings}, item_ids
            )
            write_embedding_set(
                root / "embeddings" / "w8a16.npz", {"clean-6s": unrelated}, item_ids
            )
            _write_result(root, "run-pass", _pass_result())
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(_manifest_payload(_speakers())), encoding="utf-8")

            record = collect_benchmark(root, manifest)
            self.assertEqual(record["status"], STATUS_GATE_FAILED)
            self.assertFalse(record["gate"]["passed"])
            self.assertIsNotNone(record["parity"]["clean-6s"])
            self.assertLess(record["parity"]["clean-6s"]["median_cosine"], 0.995)
            self.assertIsNone(record["accuracy"])
            self.assertEqual(record["threshold_recalibration"], "blocked")
            self.assertEqual(record["product_admission"], "blocked")
            self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)


class TestRealEvidenceRoot(unittest.TestCase):
    """真实证据目录：设备离线 + 无 embedding，必须落 device_unavailable。"""

    def test_repository_evidence_is_device_unavailable(self):
        from scripts.speaker_qnn.benchmark import DEFAULT_EVIDENCE_ROOT, DEFAULT_MANIFEST

        if not DEFAULT_EVIDENCE_ROOT.is_dir() or not DEFAULT_MANIFEST.is_file():
            self.skipTest("本机没有 CAM++ 真机证据目录")
        record = collect_benchmark(DEFAULT_EVIDENCE_ROOT, DEFAULT_MANIFEST)
        self.assertEqual(record["status"], STATUS_DEVICE_UNAVAILABLE)
        self.assertIsNone(record["accuracy"])
        self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
