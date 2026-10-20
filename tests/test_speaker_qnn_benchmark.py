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

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import numpy as np
except ImportError:  # 主库 discover 环境没有 numpy
    np = None

from scripts.speaker_qnn.benchmark import (  # noqa: E402
    BLOCKED_ACTIONS,
    COLD_LOAD_SAMPLES,
    EMBEDDING_DIM,
    MODEL_LICENSE,
    PERF_PROFILES,
    RECALIBRATED_W8A16_THRESHOLD,
    RESIDENT_CAP_MS,
    REUSED_FP32_THRESHOLD,
    SOAK_PERF_PROFILE,
    STATUS_DEVICE_UNAVAILABLE,
    STATUS_GATE_FAILED,
    STATUS_INCOMPLETE,
    STATUS_PASS,
    TASK_MATRIX,
    WATCHDOG_MS,
    AccuracyMetrics,
    DeviceUnavailableError,
    EmbeddingParity,
    LatencyEvent,
    LatencyMetrics,
    SoakMetrics,
    adjusted_rand_index,
    collect_benchmark,
    dequantize_device_output,
    dequantize_embedding,
    embedding_gate,
    evaluate_accuracy,
    evaluate_embedding_parity,
    extract_embedding_sets,
    identification_top1,
    l2_normalize,
    load_embedding_set,
    main,
    online_cluster,
    parse_execution_timings,
    parse_thermal_sample,
    percentile,
    read_device_output,
    record_benchmark_section,
    require_device_evidence,
    round_robin_order,
    run_latency_benchmark,
    run_soak,
    scan_device_evidence,
    summarize_latency,
    summarize_thermal,
    write_embedding_set,
)
from scripts.speaker_qnn import benchmark as benchmark_module  # noqa: E402
from scripts.speaker_qnn import device as device_module  # noqa: E402
from scripts.speaker_qnn.build import BuildArtifact  # noqa: E402
from scripts.speaker_qnn.contracts import (  # noqa: E402
    PROFILE_UNAVAILABLE,
    ContextMetadata,
    load_context_metadata,
    parse_profile_timings,
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


SCALE = 1e-3
OFFSET = -32768
W8A16_DTYPE = "QNN_DATATYPE_FIXED_POINT_16"
FP32_DTYPE = "QNN_DATATYPE_FLOAT_32"
REAL_INFO_JSON = (
    REPO
    / "var/speaker-benchmark/qnn/campplus-htp-debug/builds"
    / "2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats/context/info.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _item_ids_sha256(ids) -> str:
    return hashlib.sha256("\n".join(str(value) for value in ids).encode("utf-8")).hexdigest()


def _info_payload(*, data_type: str = W8A16_DTYPE, quantized: bool = True) -> dict:
    output: dict = {
        "name": "embedding",
        "dimensions": [1, EMBEDDING_DIM],
        "dataType": data_type,
    }
    if quantized:
        output["quantizeParams"] = {
            "definition": "QNN_DEFINITION_DEFINED",
            "quantizationEncoding": "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET",
            "scaleOffset": {"scale": SCALE, "offset": OFFSET},
        }
    return {
        "buildId": "v2.51.1.261002102551",
        "socModel": 87,
        "numGraphs": 1,
        "graphs": [
            {
                "graphName": "campplus_w8a16_static_stats",
                "graphInputs": [
                    {
                        "name": "x",
                        "dimensions": [1, 80, 298],
                        "dataType": "QNN_DATATYPE_UFIXED_POINT_16",
                    }
                ],
                "graphOutputs": [output],
            }
        ],
        "contextMetadata": {"dspArch": 81},
    }


def _write_variant(root: Path, variant_id: str, *, quantized: bool) -> dict:
    context = root / "builds" / variant_id / "context"
    context.mkdir(parents=True, exist_ok=True)
    info = context / "info.json"
    info.write_text(
        json.dumps(
            _info_payload(
                data_type=W8A16_DTYPE if quantized else FP32_DTYPE,
                quantized=quantized,
            )
        ),
        encoding="utf-8",
    )
    context_bin = context / "context.bin"
    context_bin.write_bytes(f"context-{variant_id}".encode("ascii"))
    return {"variant_id": variant_id, "info_json": str(info), "context_bin": str(context_bin)}


def _write_raw(
    path: Path, values, *, quantized: bool, output_file_dtype: str | None = None
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_file_dtype == "<f4":
        # qnn-net-run 默认落 float32：写入的是已反量化的真实数值。
        np.asarray(values, dtype="<f4").tofile(path)
    elif quantized:
        encoded = np.rint(np.asarray(values, dtype=np.float64) / SCALE + OFFSET)
        np.clip(encoded, -32768, 32767).astype("<i2").tofile(path)
    else:
        np.asarray(values, dtype="<f4").tofile(path)
    return path


def _write_run(
    root: Path,
    name: str,
    output_path: Path | None = None,
    *,
    status: str = "pass",
    output_count: int = EMBEDDING_DIM,
    finite: bool = True,
    output_file_dtype: str = "<f4",
    native_output: bool = False,
) -> Path:
    path = root / "device-runs" / name / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "exit_code": 0,
        "output_path": str(output_path) if output_path is not None else None,
        "output_count": output_count,
        "finite": finite,
        "context_load_us": None,
        "graph_execute_us": None,
        "timeout_ms": None,
        "evidence_paths": [],
        "output_file_dtype": output_file_dtype,
        "native_output": native_output,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _pass_run(root: Path, name: str = "run-pass", *, itemsize: int = 2) -> Path:
    raw = root / "device-runs" / name / "output" / "embedding.raw"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"\x00" * (EMBEDDING_DIM * itemsize))
    if itemsize == 2:
        return _write_run(
            root, name, raw, output_file_dtype="<i2", native_output=True
        )
    return _write_run(root, name, raw)


def _run_entry(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_value = payload.get("output_path")
    if not raw_value or not Path(raw_value).is_file():
        return {"result": str(path)}
    raw = Path(raw_value)
    return {"result": str(path), "raw": str(raw), "raw_sha256": _sha256(raw)}


def _provenance(run_paths) -> dict:
    entries = []
    for path in run_paths:
        if Path(path).is_file():
            entries.append(_run_entry(Path(path)))
        else:
            entries.append({"result": str(path)})
    return {
        "variant_id": "w8a16-unit",
        "context_sha256": "0" * 64,
        "info_json_sha256": "1" * 64,
        "output_dtype": W8A16_DTYPE,
        "output_scale": SCALE,
        "output_offset": OFFSET,
        "item_ids_sha256": _item_ids_sha256(_item_ids()),
        "embeddings": {},
        "device_runs": entries,
    }


def _paired_manifest(
    path: Path,
    speakers: list[str],
    device_runs: list[str],
    *,
    provenance: dict | None = None,
) -> Path:
    payload = _manifest_payload(speakers)
    payload["w8a16_provenance"] = provenance or _provenance(device_runs)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_extraction_spec(
    root: Path,
    *,
    conditions=TASK_MATRIX,
    w8a16=None,
    run_status: str = "pass",
    device_output_dtype: str = "<i2",
) -> Path:
    """host 侧抽取夹具：真实 info.json 结构 + 合成原始输出 + 单次运行记录。"""
    embeddings, _ = _fixture_embeddings()
    if w8a16 is None:
        w8a16 = embeddings
    native = device_output_dtype != "<f4"
    items: list[dict] = []
    first_raw: Path | None = None
    for condition in conditions:
        for index, item_id in enumerate(_item_ids()):
            raw_fp32 = _write_raw(
                root / "raw" / "fp32" / condition / f"{index}.raw",
                embeddings[index],
                quantized=False,
            )
            raw_w8a16 = _write_raw(
                root / "raw" / "w8a16" / condition / f"{index}.raw",
                w8a16[index],
                quantized=native,
                output_file_dtype=device_output_dtype,
            )
            if first_raw is None:
                first_raw = raw_w8a16
            items.append(
                {
                    "item_id": item_id,
                    "condition": condition,
                    "fp32": {"raw": str(raw_fp32)},
                    "w8a16": {"raw": str(raw_w8a16)},
                }
            )
    if run_status == "pass":
        run = _write_run(
            root,
            "w8a16-pass",
            first_raw,
            output_file_dtype=device_output_dtype,
            native_output=native,
        )
    else:
        run = _write_run(
            root,
            "w8a16-ssr",
            None,
            status="ssr",
            output_count=0,
            finite=False,
            output_file_dtype=device_output_dtype,
            native_output=native,
        )
    for item in items:
        item["w8a16"]["run"] = str(run)
    spec = {
        "fp32": _write_variant(root, "fp32-unit", quantized=False),
        "w8a16": _write_variant(root, "w8a16-unit", quantized=True),
        "items": items,
    }
    path = root / "extraction-spec.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _build_evidence_root(
    root: Path,
    *,
    conditions=TASK_MATRIX,
    w8a16=None,
    run_status: str = "pass",
    device_output_dtype: str = "<i2",
) -> Path:
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(_manifest_payload(_speakers())), encoding="utf-8")
    spec = _write_extraction_spec(
        root,
        conditions=conditions,
        w8a16=w8a16,
        run_status=run_status,
        device_output_dtype=device_output_dtype,
    )
    extract_embedding_sets(spec, root / "embeddings")
    return manifest


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
            result_path = _pass_run(root)
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
            result_path = _pass_run(root)
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
            result_path = _pass_run(root)
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
            result_path = _write_run(
                root, "run-ssr", None, status="ssr", output_count=0, finite=False
            )
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
            self.assertIn("extraction.json", record["reason"])
            self.assertEqual(record["blocked_actions"], list(BLOCKED_ACTIONS))
            self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)
            self.assertTrue(output.is_file())
            json.loads(output.read_text(encoding="utf-8"))

    @requires_numpy
    def test_extracted_embeddings_without_pass_run_stay_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = _build_evidence_root(root, run_status="ssr")
            record = collect_benchmark(root, manifest)
            self.assertEqual(record["status"], STATUS_DEVICE_UNAVAILABLE)
            self.assertIn("ssr", record["reason"])
            self.assertIsNone(record["accuracy"])
            self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)

    @requires_numpy
    def test_passing_evidence_produces_gated_metrics(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = _build_evidence_root(root)
            output = root / "benchmark.json"

            record = collect_benchmark(root, manifest, output=output)
            self.assertEqual(record["status"], STATUS_PASS)
            self.assertAlmostEqual(
                record["parity"]["clean-6s"]["median_cosine"], 1.0, places=6
            )
            self.assertTrue(record["gate"]["passed"])
            self.assertEqual(record["threshold_recalibration"], "completed")
            self.assertEqual(set(record["accuracy"]), set(TASK_MATRIX))
            self.assertEqual(
                set(record["accuracy"]["clean-6s"]),
                {REUSED_FP32_THRESHOLD, RECALIBRATED_W8A16_THRESHOLD},
            )
            # provenance 必须把 embedding ↔ build ↔ run 串起来。
            provenance = record["provenance"]
            self.assertEqual(provenance["variant_id"], "w8a16-unit")
            context_bin = root / "builds/w8a16-unit/context/context.bin"
            self.assertEqual(provenance["context_sha256"], _sha256(context_bin))
            self.assertEqual(
                record["embeddings"]["w8a16"]["sha256"],
                _sha256(root / "embeddings" / "w8a16.npz"),
            )
            self.assertEqual(
                record["embeddings"]["item_ids_sha256"], _item_ids_sha256(_item_ids())
            )
            paired = json.loads(
                (root / "benchmark-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                paired["w8a16_provenance"]["context_sha256"],
                provenance["context_sha256"],
            )
            self.assertTrue(output.is_file())

    @requires_numpy
    def test_incomplete_task_matrix_is_not_reported_as_pass(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = _build_evidence_root(root, conditions=("clean-6s",))
            record = collect_benchmark(root, manifest)
            self.assertEqual(record["status"], STATUS_INCOMPLETE)
            self.assertEqual(record["product_admission"], "blocked")
            self.assertEqual(record["threshold_recalibration"], "blocked")
            self.assertEqual(set(record["accuracy"]), {"clean-6s"})
            self.assertEqual(record["blocked_actions"], list(BLOCKED_ACTIONS))
            self.assertIn("clean-1s", record["reason"])

    @requires_numpy
    def test_failed_gate_blocks_accuracy_but_keeps_parity(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            rng = np.random.default_rng(7)
            unrelated = rng.standard_normal(embeddings.shape) * 0.5
            manifest = _build_evidence_root(root, w8a16=unrelated)

            record = collect_benchmark(root, manifest)
            self.assertEqual(record["status"], STATUS_GATE_FAILED)
            self.assertFalse(record["gate"]["passed"])
            self.assertIsNotNone(record["parity"]["clean-6s"])
            self.assertLess(record["parity"]["clean-6s"]["median_cosine"], 0.995)
            self.assertIsNone(record["accuracy"])
            self.assertEqual(record["threshold_recalibration"], "blocked")
            self.assertEqual(record["product_admission"], "blocked")
            self.assertFalse(_numeric_keys(record) & ACCURACY_KEYS)


class TestContextQuantization(unittest.TestCase):
    def test_reads_real_context_output_quantization(self):
        if not REAL_INFO_JSON.is_file():
            self.skipTest("本机没有真实 CAM++ context info.json")
        metadata = load_context_metadata(REAL_INFO_JSON)
        self.assertEqual(metadata.output_data_type, "QNN_DATATYPE_UFIXED_POINT_16")
        self.assertEqual(metadata.output_quant_encoding, "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET")
        self.assertAlmostEqual(metadata.output_scale, 0.00010776489216368645, places=18)
        self.assertEqual(metadata.output_offset, -33100)

    def test_unquantized_context_leaves_quantization_fields_empty(self):
        with tempfile.TemporaryDirectory() as raw_root:
            variant = _write_variant(Path(raw_root), "fp32-unit", quantized=False)
            metadata = load_context_metadata(Path(variant["info_json"]))
            self.assertIsNone(metadata.output_scale)
            self.assertIsNone(metadata.output_offset)
            self.assertEqual(metadata.output_data_type, FP32_DTYPE)
            self.assertIsNone(metadata.output_quant_encoding)
            self.assertIsNone(metadata.to_dict()["output_scale"])


class TestDeviceOutput(unittest.TestCase):
    @requires_numpy
    def test_dequantize_device_output_uses_parsed_metadata(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            variant = _write_variant(root, "w8a16-unit", quantized=True)
            metadata = load_context_metadata(Path(variant["info_json"]))
            raw = np.arange(EMBEDDING_DIM, dtype=np.int64) - 96
            path = root / "output.raw"
            raw.astype("<i2").tofile(path)

            values = dequantize_device_output(path, metadata)
            expected = (raw.astype(np.float64) - OFFSET) * SCALE
            expected = expected / np.linalg.norm(expected)
            self.assertEqual(values.shape, (1, EMBEDDING_DIM))
            np.testing.assert_allclose(values[0], expected, rtol=1e-6, atol=1e-7)
            self.assertAlmostEqual(float(np.linalg.norm(values[0])), 1.0, places=12)

    @requires_numpy
    def test_dequantize_device_output_rejects_wrong_element_count(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            variant = _write_variant(root, "w8a16-unit", quantized=True)
            metadata = load_context_metadata(Path(variant["info_json"]))
            path = root / "short.raw"
            np.arange(100, dtype="<i2").tofile(path)
            with self.assertRaises(ValueError) as caught:
                dequantize_device_output(path, metadata)
            self.assertIn("192", str(caught.exception))

    @requires_numpy
    def test_dequantize_device_output_requires_quantization(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            variant = _write_variant(root, "fp32-unit", quantized=False)
            metadata = load_context_metadata(Path(variant["info_json"]))
            path = root / "output.raw"
            np.zeros(EMBEDDING_DIM, dtype="<f4").tofile(path)
            with self.assertRaises(ValueError) as caught:
                dequantize_device_output(path, metadata)
            self.assertIn("量化", str(caught.exception))

    @requires_numpy
    def test_read_device_output_reads_float32_without_dequantizing(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            variant = _write_variant(root, "fp32-unit", quantized=False)
            metadata = load_context_metadata(Path(variant["info_json"]))
            embeddings, _ = _fixture_embeddings()
            path = root / "output.raw"
            embeddings[0].astype("<f4").tofile(path)
            values = read_device_output(path, metadata)
            expected = l2_normalize(embeddings[0:1])
            np.testing.assert_allclose(values, expected, rtol=1e-6, atol=1e-7)


class TestExtractionPipeline(unittest.TestCase):
    @requires_numpy
    def test_raw_plus_info_generates_paired_npz(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            spec = _write_extraction_spec(root)
            record = extract_embedding_sets(spec, root / "embeddings")

            fp32_blocks, fp32_ids = load_embedding_set(
                root / "embeddings" / "fp32.npz"
            )
            blocks, item_ids = load_embedding_set(
                root / "embeddings" / "w8a16.npz"
            )
            self.assertEqual(item_ids, tuple(_item_ids()))
            self.assertEqual(fp32_ids, item_ids)
            self.assertEqual(list(blocks), list(TASK_MATRIX))
            expected = l2_normalize(_fixture_embeddings()[0])
            for condition in TASK_MATRIX:
                np.testing.assert_allclose(
                    blocks[condition], expected, rtol=0, atol=3e-3
                )
                np.testing.assert_allclose(
                    fp32_blocks[condition], expected, rtol=0, atol=1e-6
                )
            self.assertEqual(
                record["variants"]["w8a16"]["context_sha256"],
                _sha256(root / "builds/w8a16-unit/context/context.bin"),
            )
            self.assertEqual(
                record["variants"]["w8a16"]["npz_sha256"],
                _sha256(root / "embeddings" / "w8a16.npz"),
            )
            self.assertEqual(record["item_ids_sha256"], _item_ids_sha256(_item_ids()))
            self.assertTrue((root / "embeddings" / "extraction.json").is_file())

    @requires_numpy
    def test_condition_item_order_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            spec = _write_extraction_spec(root, conditions=("clean-6s", "clean-3s"))
            payload = json.loads(spec.read_text(encoding="utf-8"))
            payload["items"][5], payload["items"][6] = (
                payload["items"][6],
                payload["items"][5],
            )
            spec.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError) as caught:
                extract_embedding_sets(spec, root / "embeddings")
            self.assertIn("顺序", str(caught.exception))


class TestEvidenceBinding(unittest.TestCase):
    @requires_numpy
    def test_missing_output_file_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            missing = root / "missing.raw"
            result_path = _write_run(root, "run-pass", missing)
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            with self.assertRaises(DeviceUnavailableError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("output", caught.exception.reason)

    @requires_numpy
    def test_output_byte_size_mismatch_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            short = root / "short.raw"
            short.write_bytes(b"\x00" * 10)
            result_path = _write_run(root, "run-pass", short)
            manifest = _paired_manifest(
                root / "manifest.json", _speakers(), [str(result_path)]
            )
            with self.assertRaises(DeviceUnavailableError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("字节", caught.exception.reason)

    @requires_numpy
    def test_raw_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _pass_run(root)
            provenance = _provenance([str(result_path)])
            provenance["device_runs"][0]["raw_sha256"] = "0" * 64
            manifest = _paired_manifest(
                root / "manifest.json",
                _speakers(),
                [str(result_path)],
                provenance=provenance,
            )
            with self.assertRaises(ValueError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("sha256", str(caught.exception).lower())

    @requires_numpy
    def test_embedding_source_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _pass_run(root)
            provenance = _provenance([str(result_path)])
            provenance["embeddings"] = {"w8a16": {"sha256": "0" * 64}}
            manifest = _paired_manifest(
                root / "manifest.json",
                _speakers(),
                [str(result_path)],
                provenance=provenance,
            )
            source = root / "w8a16.npz"
            write_embedding_set(source, {"clean-6s": embeddings}, _item_ids())
            with self.assertRaises(ValueError) as caught:
                evaluate_accuracy(
                    embeddings, embeddings, manifest, w8a16_source=source
                )
            self.assertIn("sha256", str(caught.exception).lower())

    @requires_numpy
    def test_item_ids_digest_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _pass_run(root)
            provenance = _provenance([str(result_path)])
            provenance["item_ids_sha256"] = "0" * 64
            manifest = _paired_manifest(
                root / "manifest.json",
                _speakers(),
                [str(result_path)],
                provenance=provenance,
            )
            with self.assertRaises(ValueError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("item_id", str(caught.exception))

    @requires_numpy
    def test_provenance_without_variant_binding_is_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            embeddings, _ = _fixture_embeddings()
            result_path = _pass_run(root)
            provenance = _provenance([str(result_path)])
            provenance["variant_id"] = ""
            manifest = _paired_manifest(
                root / "manifest.json",
                _speakers(),
                [str(result_path)],
                provenance=provenance,
            )
            with self.assertRaises(DeviceUnavailableError) as caught:
                evaluate_accuracy(embeddings, embeddings, manifest)
            self.assertIn("variant_id", caught.exception.reason)


class TestRelativeEvidenceRoot(unittest.TestCase):
    def test_scan_resolves_relative_root_to_absolute_paths(self):
        with tempfile.TemporaryDirectory() as raw_root:
            base = Path(raw_root)
            run = _pass_run(base / "evidence")
            previous = Path.cwd()
            os.chdir(base)
            try:
                records = scan_device_evidence(Path("evidence"))
            finally:
                os.chdir(previous)
            self.assertEqual(len(records), 1)
            self.assertTrue(Path(records[0]["path"]).is_absolute())
            self.assertTrue(Path(records[0]["path"]).is_file())
            self.assertEqual(Path(records[0]["path"]), run.resolve())


class TestDeviceUnavailableRecord(unittest.TestCase):
    """不依赖 numpy：主库 discover 环境也要锁住落盘契约。"""

    def test_record_carries_status_and_reason(self):
        record = DeviceUnavailableError("no device").to_dict()
        self.assertEqual(record["status"], STATUS_DEVICE_UNAVAILABLE)
        self.assertEqual(record["reason"], "no device")


class TestCli(unittest.TestCase):
    def test_collect_returns_two_when_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(_manifest_payload(["S1", "S2"])), encoding="utf-8"
            )
            code = main(
                [
                    "--root",
                    str(root),
                    "--manifest",
                    str(manifest),
                    "--output",
                    str(root / "benchmark.json"),
                ]
            )
            self.assertEqual(code, 2)


def _passing_artifact(root: Path, *, status: str = "pass") -> BuildArtifact:
    """测试用 artifact：真实 info.json 结构 + 存在的 context 二进制。"""
    context = root / "context" / "campplus_w8a16_static_stats.bin.SM8845.bin"
    context.parent.mkdir(parents=True, exist_ok=True)
    context.write_bytes(b"unit-test-context")
    metadata = ContextMetadata(
        build_id="v2.51.1.261002102551",
        soc_model=87,
        dsp_arch=81,
        graph_name="campplus_w8a16_static_stats",
        input_shape=(1, 80, 298),
        output_shape=(1, 192),
    )
    return BuildArtifact(
        variant_id="unit-latency",
        status=status,
        context_path=str(context),
        metadata=metadata,
        sha256={"context": "0" * 64},
        commands=(),
        error=None,
        warning=None,
    )


class TestLatencyPercentiles(unittest.TestCase):
    """百分位定义在所有环境固定为线性插值（与 numpy 默认 linear 同义）。"""

    def test_median_uses_linear_interpolation(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.5), 2.5)
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.0), 1.0)
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 1.0), 4.0)

    def test_p95_and_p99_are_interpolated_not_index_rounded(self):
        values = list(range(1, 101))
        self.assertAlmostEqual(percentile(values, 0.95), 95.05, places=9)
        self.assertAlmostEqual(percentile(values, 0.99), 99.01, places=9)

    def test_single_sample_returns_itself(self):
        self.assertEqual(percentile([7.0], 0.99), 7.0)

    def test_empty_and_out_of_range_are_rejected(self):
        with self.assertRaises(ValueError):
            percentile([], 0.5)
        with self.assertRaises(ValueError):
            percentile([1.0, 2.0], 1.5)
        with self.assertRaises(ValueError):
            percentile([1.0, 2.0], -0.1)

    def test_input_order_does_not_change_percentile(self):
        ordered = [1.0, 2.0, 3.0, 4.0]
        shuffled = [3.0, 1.0, 4.0, 2.0]
        self.assertEqual(percentile(ordered, 0.5), percentile(shuffled, 0.5))


class TestLatencySummary(unittest.TestCase):
    def test_latency_uses_measured_runs_after_warmup(self):
        events = [
            LatencyEvent(status="pass", graph_us=1_000, context_load_us=250_000)
            for _ in range(100)
        ] + [
            LatencyEvent(status="pass", graph_us=value)
            for value in (1_500, 1_900, 2_000, 2_100, 2_500)
        ]
        metrics = summarize_latency(events, warmups=100)
        self.assertIsInstance(metrics, LatencyMetrics)
        self.assertEqual(metrics.graph_p50_ms, 2.0)
        self.assertEqual(metrics.cold_load_p50_ms, 250.0)
        self.assertEqual(metrics.cold_load_p95_ms, 250.0)

    def test_profile_unit_conversion(self):
        profile = (
            "Context load time: 1.2 s\n"
            "Graph execute time: 4726 us\n"
            "Graph execute time: 5 ms\n"
            "Graph execute time: 0.25 s\n"
        )
        self.assertEqual(parse_execution_timings(profile), (4726, 5000, 250000))
        event = LatencyEvent(
            status="pass", context_load_us=200_000, profile_text="Graph execute time: 4.726 ms"
        )
        metrics = summarize_latency([event], warmups=0)
        self.assertAlmostEqual(metrics.graph_p50_ms, 4.726, places=6)

    def test_cold_and_warm_are_separated(self):
        cold = [
            LatencyEvent(
                status="pass", graph_us=100_000, context_load_us=300_000
            )
        ]
        warm = [
            LatencyEvent(status="pass", graph_us=5_000),
            LatencyEvent(status="pass", graph_us=6_000),
        ]
        metrics = summarize_latency(cold + warm, warmups=1)
        self.assertEqual(metrics.cold_load_p50_ms, 300.0)
        self.assertEqual(metrics.graph_p50_ms, 5.5)
        self.assertAlmostEqual(metrics.graph_p95_ms, 5.95, places=9)
        self.assertAlmostEqual(metrics.graph_p99_ms, 5.99, places=9)

    def test_two_context_transfer_and_scheduling_are_counted(self):
        cold = [LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000)]
        event = LatencyEvent(
            status="pass",
            graph_us=5_000,
            io_us=1_000,
            fbank_us=2_000,
            transfer_us=500,
            schedule_us=1_000,
        )
        metrics = summarize_latency(cold + [event], warmups=1)
        self.assertEqual(metrics.end_to_end_p50_ms, 9.5)
        self.assertAlmostEqual(metrics.throughput_ips, 1000.0 / 9.5, places=9)
        self.assertEqual(metrics.io_p50_ms, 1.0)
        self.assertEqual(metrics.fbank_p50_ms, 2.0)
        self.assertEqual(metrics.transfer_p50_ms, 0.5)
        self.assertEqual(metrics.schedule_p50_ms, 1.0)

    def test_graph_only_events_have_no_end_to_end_or_throughput(self):
        cold = [LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000)]
        warm = [
            LatencyEvent(status="pass", graph_us=5_000),
            LatencyEvent(status="pass", graph_us=6_000),
        ]
        metrics = summarize_latency(cold + warm, warmups=1)
        self.assertEqual(metrics.graph_p50_ms, 5.5)
        self.assertIsNone(metrics.end_to_end_p50_ms)
        self.assertIsNone(metrics.end_to_end_p95_ms)
        self.assertIsNone(metrics.throughput_ips)
        self.assertIsNone(metrics.io_p50_ms)
        self.assertIsNone(metrics.fbank_p50_ms)
        self.assertIsNone(metrics.transfer_p50_ms)
        self.assertIsNone(metrics.schedule_p50_ms)

    def test_partial_components_never_compose_end_to_end(self):
        cold = [LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000)]
        event = LatencyEvent(status="pass", graph_us=5_000, io_us=1_000)
        metrics = summarize_latency(cold + [event], warmups=1)
        self.assertEqual(metrics.io_p50_ms, 1.0)
        self.assertIsNone(metrics.fbank_p50_ms)
        self.assertIsNone(metrics.end_to_end_p50_ms)
        self.assertIsNone(metrics.throughput_ips)

    def test_watchdog_scale_graph_time_is_not_a_speed_value(self):
        cold = [LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000)]
        event = LatencyEvent(status="pass", graph_us=WATCHDOG_MS * 1_000)
        with self.assertRaises(ValueError) as caught:
            summarize_latency(cold + [event], warmups=1)
        self.assertIn("timeout", str(caught.exception))

    def test_non_resident_graph_time_is_rejected(self):
        cold = [LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000)]
        event = LatencyEvent(status="pass", graph_us=RESIDENT_CAP_MS * 1_000)
        with self.assertRaises(ValueError) as caught:
            summarize_latency(cold + [event], warmups=1)
        self.assertIn("不可常驻", str(caught.exception))

    def test_dropped_runs_do_not_enter_percentiles(self):
        events = [
            LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000),
            LatencyEvent(status="timeout", graph_us=10_000_000),
            LatencyEvent(status="pass", graph_us=2_000),
            LatencyEvent(status="ssr", graph_us=None),
            LatencyEvent(status="pass", graph_us=None),
        ]
        metrics = summarize_latency(events, warmups=1)
        self.assertEqual(metrics.graph_p50_ms, 2.0)
        self.assertEqual(metrics.graph_p99_ms, 2.0)
        self.assertLess(metrics.graph_p95_ms, 10_000.0)

    def test_all_measured_runs_dropped_is_rejected(self):
        events = [
            LatencyEvent(status="pass", graph_us=1_000, context_load_us=100_000),
            LatencyEvent(status="timeout", graph_us=None),
            LatencyEvent(status="ssr", graph_us=None),
        ]
        with self.assertRaises(ValueError) as caught:
            summarize_latency(events, warmups=1)
        self.assertIn("measured", str(caught.exception))

    def test_negative_warmup_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_latency([LatencyEvent(status="pass", graph_us=1_000)], warmups=-1)

    def test_missing_cold_load_sample_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_latency([LatencyEvent(status="pass", graph_us=1_000)], warmups=0)
        self.assertIn("cold", str(caught.exception))


class TestThermalSamples(unittest.TestCase):
    def test_parses_battery_and_skin_maxima(self):
        dump = (
            "Current temperatures from HAL:\n"
            "      Temperature{mValue=31.2, mType=0, mName=BATTERY, mStatus=0}\n"
            "      Temperature{mValue=35.9, mType=3, mName=SKIN, mStatus=0}\n"
            "      Temperature{mValue=36.1, mType=3, mName=TP_SKIN, mStatus=0}\n"
        )
        self.assertEqual(parse_thermal_sample(dump), (31.2, 36.1))

    def test_missing_thermal_zones_are_none(self):
        self.assertEqual(parse_thermal_sample("no thermal service\n"), (None, None))
        dump = "Temperature{mValue=34.0, mType=3, mName=SKIN, mStatus=0}\n"
        self.assertEqual(parse_thermal_sample(dump), (None, 34.0))

    def test_soak_temperature_gaps(self):
        self.assertEqual(
            summarize_thermal([(31.2, 35.9), (None, None), (32.0, None)]),
            (32.0, 35.9),
        )
        self.assertEqual(summarize_thermal([(31.0, None)]), (31.0, None))

    def test_soak_without_any_battery_sample_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            summarize_thermal([(None, 35.0), (None, None)])
        self.assertIn("battery", str(caught.exception))


class TestDeviceBoundBenchmarks(unittest.TestCase):
    def test_offline_device_reports_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with mock.patch(
                "scripts.speaker_qnn.benchmark.discover_device_serial", return_value=None
            ):
                with self.assertRaises(DeviceUnavailableError) as caught:
                    run_latency_benchmark(
                        artifact, 100, 1000, "sustained_high_performance"
                    )
            self.assertEqual(caught.exception.status, STATUS_DEVICE_UNAVAILABLE)
            self.assertIn("device_unavailable", caught.exception.reason)
            self.assertIn("1000", caught.exception.reason)

    def test_soak_reports_device_unavailable(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with mock.patch(
                "scripts.speaker_qnn.benchmark.discover_device_serial", return_value=None
            ):
                with self.assertRaises(DeviceUnavailableError) as caught:
                    run_soak(artifact, 1800, 1.0)
            self.assertEqual(caught.exception.status, STATUS_DEVICE_UNAVAILABLE)
            self.assertIn("30 分钟", caught.exception.reason)

    def test_invalid_perf_profile_is_rejected_before_device(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with self.assertRaises(ValueError) as caught:
                run_latency_benchmark(artifact, 1, 1, "turbo")
            self.assertIn("perf_profile", str(caught.exception))
        self.assertIn("sustained_high_performance", PERF_PROFILES)

    def test_config_warning_artifact_is_not_benchmarked(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root), status="config_warning")
            with self.assertRaises(ValueError) as caught:
                run_latency_benchmark(artifact, 1, 1, "burst")
            self.assertIn("告警", str(caught.exception))

    def test_metadata_rejected_artifact_is_not_benchmarked(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root), status="metadata_rejected")
            with self.assertRaises(ValueError):
                run_latency_benchmark(artifact, 1, 1, "burst")

    def test_cold_load_sample_count_matches_plan(self):
        self.assertEqual(COLD_LOAD_SAMPLES, 20)

    def test_metrics_serialize_to_json_ready_dicts(self):
        metrics = LatencyMetrics(
            cold_load_p50_ms=10.0,
            cold_load_p95_ms=11.0,
            graph_p50_ms=20.0,
            graph_p95_ms=21.0,
            graph_p99_ms=22.0,
            end_to_end_p50_ms=30.0,
            end_to_end_p95_ms=31.0,
            throughput_ips=33.3,
        )
        self.assertEqual(metrics.to_dict()["graph_p99_ms"], 22.0)
        self.assertEqual(metrics.to_dict()["fbank_p50_ms"], None)
        graph_only = LatencyMetrics(
            cold_load_p50_ms=10.0,
            cold_load_p95_ms=11.0,
            graph_p50_ms=20.0,
            graph_p95_ms=21.0,
            graph_p99_ms=22.0,
        )
        payload = graph_only.to_dict()
        self.assertIsNone(payload["end_to_end_p50_ms"])
        self.assertIsNone(payload["end_to_end_p95_ms"])
        self.assertIsNone(payload["throughput_ips"])
        self.assertIsNone(payload["transfer_p50_ms"])
        self.assertIsNone(payload["schedule_p50_ms"])
        soak = SoakMetrics(
            duration_s=1800,
            successful_runs=1700,
            failed_runs=100,
            max_battery_temp_c=39.5,
            max_skin_temp_c=None,
            median_graph_ms=20.0,
            final_graph_ms=21.0,
        )
        self.assertIsNone(soak.to_dict()["max_skin_temp_c"])


def _latency_events(count: int = COLD_LOAD_SAMPLES) -> list[LatencyEvent]:
    """20 次冷加载 + 1 次 warmup + 2 次 measured；数值只是算法夹具。"""
    return [
        LatencyEvent(status="pass", graph_us=1_000, context_load_us=250_000)
        for _ in range(count)
    ] + [
        LatencyEvent(status="pass", graph_us=5_000),
        LatencyEvent(status="pass", graph_us=5_000),
        LatencyEvent(status="pass", graph_us=6_000),
    ]


class TestOutputDtypeProvenance(unittest.TestCase):
    """C1：落盘 dtype 只由 result.json 的 provenance 决定。"""

    @requires_numpy
    def test_float32_output_feeds_extraction_and_evidence(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            spec = _write_extraction_spec(root, device_output_dtype="<f4")
            record = extract_embedding_sets(spec, root / "embeddings")

            item = json.loads(spec.read_text(encoding="utf-8"))["items"][0]
            run_path = Path(item["w8a16"]["run"])
            payload = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["output_file_dtype"], "<f4")
            self.assertFalse(payload["native_output"])
            raw = Path(payload["output_path"])
            self.assertEqual(raw.stat().st_size, EMBEDDING_DIM * 4)  # 768 字节

            blocks, _ = load_embedding_set(root / "embeddings" / "w8a16.npz")
            expected = l2_normalize(_fixture_embeddings()[0])
            np.testing.assert_allclose(
                blocks["clean-6s"], expected, rtol=0, atol=1e-6
            )

            records = require_device_evidence(
                root / "manifest.json",
                {"w8a16_provenance": _provenance([str(run_path)])},
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(
                record["variants"]["w8a16"]["data_type"], W8A16_DTYPE
            )

    def test_float32_byte_count_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            short = root / "short.raw"
            short.write_bytes(b"\x00" * (EMBEDDING_DIM * 4 - 1))
            run = _write_run(root, "float32-short", short, output_file_dtype="<f4")
            with self.assertRaises(DeviceUnavailableError) as caught:
                require_device_evidence(
                    root / "manifest.json",
                    {"w8a16_provenance": _provenance([str(run)])},
                )
            self.assertIn("字节", caught.exception.reason)


class TestViewerProfileTimings(unittest.TestCase):
    """C2：qnn-profile-viewer 文本必须能被解析，不可得是显式状态。"""

    def test_execution_timings_read_viewer_text(self):
        text = "Graph Execution Time (us): 4726\nGraph Execution Time (ms): 5.0"
        self.assertEqual(parse_execution_timings(text), (4726, 5000))

    def test_profile_timings_read_viewer_text(self):
        text = "Context Load Time (ms): 12.5\nExecution Time (us): 4726"
        self.assertEqual(parse_profile_timings(text), (12500, 4726))

    def test_all_pass_without_profile_is_explicit_unavailable(self):
        events = [
            LatencyEvent(status="pass", context_load_us=250_000)
            for _ in range(3)
        ]
        with self.assertRaises(DeviceUnavailableError) as caught:
            summarize_latency(events, warmups=0)
        self.assertEqual(caught.exception.status, PROFILE_UNAVAILABLE)
        self.assertIn("profile_unavailable", caught.exception.reason)


class TestBenchmarkPersistence(unittest.TestCase):
    """I4：latency/soak 合并进 benchmark.json，保留原有状态字段。"""

    def test_sections_merge_and_preserve_benchmark_state(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "benchmark.json").write_text(
                json.dumps(
                    {"status": "device_unavailable", "pending": ["首次成功门禁"]}
                ),
                encoding="utf-8",
            )
            latency = LatencyMetrics(
                cold_load_p50_ms=10.0,
                cold_load_p95_ms=11.0,
                graph_p50_ms=20.0,
                graph_p95_ms=21.0,
                graph_p99_ms=22.0,
                perf_profile="burst",
                device_serial="327366100004",
                soc_model=87,
                dsp_arch=81,
                build_id="v2.51.1.261002102551",
                model_license=MODEL_LICENSE,
            )
            soak = SoakMetrics(
                duration_s=1800,
                successful_runs=1700,
                failed_runs=100,
                max_battery_temp_c=39.5,
                max_skin_temp_c=None,
                median_graph_ms=20.0,
                final_graph_ms=21.0,
                device_serial="327366100004",
                soc_model=87,
                dsp_arch=81,
                build_id="v2.51.1.261002102551",
                model_license=MODEL_LICENSE,
            )
            record_benchmark_section(root, "latency", latency.to_dict())
            record_benchmark_section(root, "soak", soak.to_dict())
            payload = json.loads((root / "benchmark.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "device_unavailable")
            self.assertEqual(payload["pending"], ["首次成功门禁"])
            self.assertEqual(payload["kind"], "campplus_w8a16_benchmark")
            self.assertEqual(payload["latency"]["status"], "pass")
            self.assertEqual(payload["latency"]["perf_profile"], "burst")
            self.assertEqual(payload["latency"]["device_serial"], "327366100004")
            self.assertEqual(payload["soak"]["status"], "pass")
            self.assertEqual(payload["soak"]["perf_profile"], SOAK_PERF_PROFILE)

    def test_unknown_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            with self.assertRaises(ValueError) as caught:
                record_benchmark_section(Path(raw_root), "accuracy", {})
            self.assertIn("小节", str(caught.exception))


class TestDeviceIdentityBinding(unittest.TestCase):
    """I5：latency/soak 必须绑定 SM8845 设备身份，型号不符拒绝。"""

    def test_latency_benchmark_binds_device_identity(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with mock.patch.object(
                benchmark_module,
                "_collect_latency_events",
                return_value=_latency_events(),
            ), mock.patch.object(
                device_module,
                "_run_adb",
                return_value=mock.Mock(returncode=0, stdout="SM8845\n"),
            ):
                metrics = run_latency_benchmark(
                    artifact, 1, 2, "burst", serial="327366100004"
                )
            self.assertEqual(metrics.status, STATUS_PASS)
            self.assertEqual(metrics.perf_profile, "burst")
            self.assertEqual(metrics.device_serial, "327366100004")
            self.assertEqual(metrics.soc_model, 87)
            self.assertEqual(metrics.dsp_arch, 81)
            self.assertEqual(metrics.build_id, "v2.51.1.261002102551")
            self.assertEqual(metrics.model_license, MODEL_LICENSE)
            payload = metrics.to_dict()
            self.assertEqual(payload["perf_profile"], "burst")
            self.assertEqual(payload["device_serial"], "327366100004")

    def test_non_sm8845_device_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with mock.patch.object(
                device_module,
                "_run_adb",
                return_value=mock.Mock(returncode=0, stdout="SM8750\n"),
            ):
                with self.assertRaisesRegex(ValueError, "SM8845"):
                    run_latency_benchmark(
                        artifact, 1, 2, "burst", serial="327366100004"
                    )

    def test_soak_rejects_non_resident_inference(self):
        with tempfile.TemporaryDirectory() as raw_root:
            artifact = _passing_artifact(Path(raw_root))
            with mock.patch.object(
                benchmark_module,
                "require_sm8845_device",
                return_value="SM8845",
            ), mock.patch.object(
                benchmark_module,
                "resolve_input_list",
                return_value=Path("input_list.txt"),
            ), mock.patch.object(
                benchmark_module,
                "run_context",
                return_value=mock.Mock(
                    status="pass", graph_execute_us=RESIDENT_CAP_MS * 1_000
                ),
            ), mock.patch.object(
                benchmark_module, "_thermal_sample", return_value=(30.0, 35.0)
            ), mock.patch.object(
                benchmark_module, "_frequency_state_sample", return_value=None
            ), mock.patch(
                "scripts.speaker_qnn.benchmark.time.sleep"
            ):
                with self.assertRaises(ValueError) as caught:
                    run_soak(artifact, 1, 1.0, serial="327366100004")
            self.assertIn("不可常驻", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
