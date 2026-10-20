# tests/test_speaker_qnn_probe.py
"""CAM++ 前缀/后缀 probe：真实中间张量、切点门禁、parity 与故障区间二分。

口径（2026-10-20）：后缀校准只能来自 FP32 ONNX Runtime 从同一 40 条
真实语音捕获的中间张量（`source_kind == "fp32_real_audio"`）；切点必须
是静态形状、且后缀除 cut 张量外不依赖跨区张量；`suffix(prefix(x))` 必须
过 FP32 parity（`max_abs == 0`，或 cosine median `>= 0.999999`、minimum
`>= 0.99999`）。二分只认 prefix 真机证据，`tool_error` 不得当模型失败。

本文件的小模型是纯合成图，只验证抽取/门禁逻辑；真实 CAM++ 的 7 个阶段
边界在 `TestRealStageCuts`（模型不存在时 skip）。

    C:/Users/Admin/Documents/Trae-CN/pyProj/LAOS/var/speaker-benchmark/.venv/Scripts/python.exe \
        -m unittest tests.test_speaker_qnn_probe -v
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

try:
    import numpy as np
    import onnx
    import onnxruntime as ort
    from onnx import TensorProto, helper
except ImportError:  # 主库 discover 环境没有 onnx/numpy
    np = None
    onnx = None
    ort = None
    TensorProto = helper = None

from unittest import mock  # noqa: E402

import scripts.speaker_qnn.probe as probe_module  # noqa: E402
from scripts.speaker_qnn.build import BuildArtifact  # noqa: E402
from scripts.speaker_qnn.contracts import ContextMetadata, DeviceRunResult  # noqa: E402
from scripts.speaker_qnn.probe import (  # noqa: E402
    DEFAULT_CALIBRATION,
    DEFAULT_MODEL,
    IntermediateEntry,
    IntermediateManifest,
    PartitionPlan,
    ProbeSpec,
    REWRITE_BLOCKED,
    REWRITE_SELECTED,
    SOURCE_KIND_REAL_AUDIO,
    RewriteResult,
    TensorCut,
    _run_device_probes,
    apply_semantic_rewrite,
    bisect_failure_interval,
    bisection_stop,
    build_partition,
    capture_intermediates,
    discover_stage_cuts,
    dtype_size,
    extract_prefix,
    extract_suffix,
    load_manifest,
    midpoint_cut,
    parity_gate,
    require_htp_executable,
    require_partition_limit,
    require_rewrite_parity,
    run_bisection,
    select_rewrite,
    validate_rewrite_result,
    verify_layout_handoff,
    verify_probe_parity,
    write_suffix_calibration,
)

NEEDS_ONNX = unittest.skipIf(
    onnx is None or np is None or ort is None,
    "probe 测试需要 onnx/numpy/onnxruntime（var/speaker-benchmark/.venv）",
)


def _weight(name: str = "W", size: int = 4) -> "onnx.TensorProto":
    values = [0.0] * (size * size)
    for index in range(size):
        values[index * size + index] = 1.0
    values[1] = 0.25
    values[size + 2] = -0.5
    return helper.make_tensor(name, TensorProto.FLOAT, [size, size], values)


def _tiny_model(*, unused_initializer: bool = False) -> "onnx.ModelProto":
    node0 = helper.make_node("MatMul", ["x", "W"], ["h"], name="stage0")
    node1 = helper.make_node("Relu", ["h"], ["r"], name="stage1")
    node2 = helper.make_node("MatMul", ["r", "W"], ["y"], name="stage2")
    initializers = [_weight()]
    if unused_initializer:
        initializers.append(
            helper.make_tensor("unused", TensorProto.FLOAT, [2], [1.0, 2.0])
        )
    graph = helper.make_graph(
        [node0, node1, node2],
        "tiny",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 4])],
        initializer=initializers,
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)


def _stage_model() -> "onnx.ModelProto":
    names = [
        "/head/Identity",
        "/xvector/block1/Identity",
        "/xvector/block2/Identity",
        "/xvector/block3/Identity",
        "/xvector/out_nonlinear/Identity",
        "/xvector/stats/Identity",
        "/xvector/dense/Identity",
    ]
    nodes = []
    previous = "x"
    for index, name in enumerate(names):
        output = f"t{index}"
        nodes.append(helper.make_node("Identity", [previous], [output], name=name))
        previous = output
    graph = helper.make_graph(
        nodes,
        "stages",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
        [helper.make_tensor_value_info("t6", TensorProto.FLOAT, [1, 4])],
        initializer=[],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)


def _chain_model(count: int) -> "onnx.ModelProto":
    """`count` 个交替 Identity/Relu 节点，避免单算子族提前停止。"""
    nodes = []
    previous = "x"
    for index in range(count):
        output = f"t{index}"
        op = "Identity" if index % 2 == 0 else "Relu"
        nodes.append(helper.make_node(op, [previous], [output], name=f"n{index}"))
        previous = output
    graph = helper.make_graph(
        nodes,
        "chain",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
        [helper.make_tensor_value_info(previous, TensorProto.FLOAT, [1, 4])],
        initializer=[],
    )
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8)


def _write_raw(path: Path, values: list[float]) -> Path:
    np.asarray(values, dtype="<f4").tofile(path)
    return path


def _input_list(root: Path, rows: int = 2) -> Path:
    lines = []
    for index in range(rows):
        raw = _write_raw(
            root / f"input-{index}.raw",
            [float(index + 1), 0.5, -0.25, 2.0],
        )
        lines.append(f"x:={raw}")
    path = root / "input_list.txt"
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


class _TempDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)


@NEEDS_ONNX
class TestCaptureAndExtraction(_TempDirTest):
    def test_capture_uses_real_audio_and_suffix_consumes_cut_tensor(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        input_list = _input_list(self.root)
        cut = TensorCut(0, "h", (1, 4), "float32")
        manifests = capture_intermediates(
            model, (cut,), input_list, self.root / "intermediates"
        )
        manifest = load_manifest(manifests["h"])
        self.assertEqual(manifest.source_kind, SOURCE_KIND_REAL_AUDIO)
        self.assertEqual(len(manifest.entries), 2)
        self.assertEqual(manifest.shape, (1, 4))
        self.assertTrue(all(entry.input_sha256 for entry in manifest.entries))
        self.assertTrue(all(entry.sha256 for entry in manifest.entries))

        prefix = extract_prefix(model, cut, self.root / "prefix.onnx")
        suffix = extract_suffix(
            model,
            cut,
            manifests["h"],
            self.root / "suffix.onnx",
            input_list=input_list,
        )
        self.assertEqual(prefix.input_tensors, ("x",))
        self.assertEqual(prefix.output_tensors, ("h",))
        self.assertEqual(suffix.input_tensors, ("h",))
        self.assertEqual(suffix.output_tensors, ("y",))
        parity = verify_probe_parity(
            model,
            self.root / "prefix.onnx",
            self.root / "suffix.onnx",
            cut,
            input_list,
        )
        self.assertTrue(parity["passed"], parity["reason"])
        self.assertEqual(parity["max_abs"], 0.0)

    def test_suffix_calibration_list_points_at_captured_raw(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        input_list = _input_list(self.root)
        cut = TensorCut(0, "h", (1, 4), "float32")
        manifests = capture_intermediates(
            model, (cut,), input_list, self.root / "intermediates"
        )
        manifest = load_manifest(manifests["h"])
        path = write_suffix_calibration(manifest, self.root / "suffix-list.txt")
        lines = path.read_text(encoding="ascii").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(line.startswith("h:=") for line in lines))

    def test_multi_consumer_cut_still_extracts_valid_suffix(self) -> None:
        model = self.root / "branches.onnx"
        weights = _weight()
        nodes = [
            helper.make_node("MatMul", ["x", "W"], ["h"], name="stage0"),
            helper.make_node("Relu", ["h"], ["r1"], name="stage1"),
            helper.make_node("Neg", ["h"], ["r2"], name="stage2"),
            helper.make_node("Add", ["r1", "r2"], ["y"], name="stage3"),
        ]
        graph = helper.make_graph(
            nodes,
            "branches",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 4])],
            initializer=[weights],
        )
        onnx.save(
            helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8),
            str(model),
        )
        cut = TensorCut(0, "h", (1, 4), "float32")
        manifests = capture_intermediates(
            model, (cut,), _input_list(self.root), self.root / "intermediates"
        )
        extract_prefix(model, cut, self.root / "prefix.onnx")
        suffix = extract_suffix(
            model,
            cut,
            manifests["h"],
            self.root / "suffix.onnx",
            input_list=_input_list(self.root),
        )
        self.assertEqual(suffix.input_tensors, ("h",))
        parity = verify_probe_parity(
            model,
            self.root / "prefix.onnx",
            self.root / "suffix.onnx",
            cut,
            _input_list(self.root),
        )
        self.assertTrue(parity["passed"], parity["reason"])
        loaded = onnx.load(str(self.root / "suffix.onnx"))
        self.assertEqual([value.name for value in loaded.graph.input], ["h"])

    def test_disconnected_initializers_are_pruned(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(unused_initializer=True), str(model))
        cut = TensorCut(0, "h", (1, 4), "float32")
        manifests = capture_intermediates(
            model, (cut,), _input_list(self.root), self.root / "intermediates"
        )
        prefix_model = extract_prefix(model, cut, self.root / "prefix.onnx")
        suffix_model = extract_suffix(
            model,
            cut,
            manifests["h"],
            self.root / "suffix.onnx",
            input_list=_input_list(self.root),
        )
        self.assertEqual(prefix_model.output_tensors, ("h",))
        self.assertEqual(suffix_model.input_tensors, ("h",))
        prefix = onnx.load(str(self.root / "prefix.onnx"))
        suffix = onnx.load(str(self.root / "suffix.onnx"))
        self.assertEqual([item.name for item in prefix.graph.initializer], ["W"])
        self.assertEqual([item.name for item in suffix.graph.initializer], ["W"])

    def test_cut_tensor_must_belong_to_node(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        with self.assertRaisesRegex(ValueError, "不是节点"):
            extract_prefix(
                model, TensorCut(0, "y", (1, 4), "float32"), self.root / "p.onnx"
            )

    def test_invalid_cut_shapes_and_dtypes_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "静态"):
            TensorCut(0, "h", (1, -1), "float32")
        with self.assertRaisesRegex(ValueError, "静态"):
            TensorCut(0, "h", (1, 0), "float32")
        with self.assertRaisesRegex(ValueError, "浮点"):
            TensorCut(0, "h", (1, 4), "int64")
        with self.assertRaisesRegex(ValueError, "float32"):
            TensorCut(0, "h", (1, 4), "float16")


@NEEDS_ONNX
class TestSuffixCalibrationGate(_TempDirTest):
    def _prepare(self) -> tuple[Path, TensorCut, Path]:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        cut = TensorCut(0, "h", (1, 4), "float32")
        manifests = capture_intermediates(
            model, (cut,), _input_list(self.root), self.root / "intermediates"
        )
        return model, cut, manifests["h"]

    def _rewrite_manifest(self, path: Path, mutate) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_random_tensor_source_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()
        self._rewrite_manifest(
            manifest, lambda payload: payload.update({"source_kind": "random_tensor"})
        )
        with self.assertRaisesRegex(ValueError, "fp32_real_audio"):
            extract_suffix(
                model,
                cut,
                manifest,
                self.root / "suffix.onnx",
                input_list=self.root / "input_list.txt",
            )

    def test_tampered_intermediate_sha_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()

        def tamper(payload: dict) -> None:
            payload["entries"][0]["sha256"] = "0" * 64

        self._rewrite_manifest(manifest, tamper)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            extract_suffix(
                model,
                cut,
                manifest,
                self.root / "suffix.onnx",
                input_list=self.root / "input_list.txt",
            )

    def test_random_tensor_manifest_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw = Path(payload["entries"][0]["raw_path"])
        fake = np.random.default_rng(0).standard_normal(4).astype("<f4")
        fake.tofile(raw)
        payload["entries"][0]["sha256"] = hashlib.sha256(raw.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "真实 FP32 输出|重算不一致"):
            extract_suffix(
                model,
                cut,
                manifest,
                self.root / "suffix.onnx",
                input_list=self.root / "input_list.txt",
            )

    def test_nan_intermediate_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        raw = Path(payload["entries"][0]["raw_path"])
        values = np.fromfile(raw, dtype="<f4")
        values[0] = np.nan
        values.tofile(raw)
        payload["entries"][0]["sha256"] = hashlib.sha256(
            raw.read_bytes()
        ).hexdigest()
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "非有限"):
            extract_suffix(
                model,
                cut,
                manifest,
                self.root / "suffix.onnx",
                input_list=self.root / "input_list.txt",
            )

    def test_model_sha_mismatch_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()
        self._rewrite_manifest(
            manifest, lambda payload: payload.update({"model_sha256": "0" * 64})
        )
        with self.assertRaisesRegex(ValueError, "模型 SHA-256"):
            extract_suffix(
                model,
                cut,
                manifest,
                self.root / "suffix.onnx",
                input_list=self.root / "input_list.txt",
            )


@NEEDS_ONNX
class TestParityGate(unittest.TestCase):
    def test_exact_parity_passes(self) -> None:
        reference = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = parity_gate(reference, reference.copy())
        self.assertTrue(result["passed"])
        self.assertEqual(result["max_abs"], 0.0)

    def test_semantics_changed_probe_fails(self) -> None:
        reference = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        candidate = np.array([[2.0, 1.0], [4.0, 3.0]], dtype=np.float32)
        result = parity_gate(reference, candidate)
        self.assertFalse(result["passed"])
        self.assertGreater(result["max_abs"], 0.0)
        self.assertLess(result["cosine_minimum"], 0.99999)

    def test_tiny_float_drift_uses_cosine_branch(self) -> None:
        reference = np.ones((2, 192), dtype=np.float32)
        candidate = reference + 1e-7
        result = parity_gate(reference, candidate)
        self.assertGreater(result["max_abs"], 0.0)
        self.assertGreaterEqual(result["cosine_median"], 0.999999)
        self.assertTrue(result["passed"])

    def test_global_scale_change_is_rejected(self) -> None:
        reference = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        candidate = (reference * 1.01).astype(np.float32)
        result = parity_gate(reference, candidate)
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["cosine_minimum"], 1.0, places=6)
        self.assertAlmostEqual(result["scale_max_deviation"], 0.01, places=5)

    def test_shape_mismatch_is_rejected(self) -> None:
        result = parity_gate(
            np.ones((2, 4), dtype=np.float32), np.ones((2, 5), dtype=np.float32)
        )
        self.assertFalse(result["passed"])
        self.assertIn("形状", result["reason"])


def _spec(kind: str, last_node: int) -> ProbeSpec:
    return ProbeSpec(
        probe_id=f"{kind}-{last_node}",
        kind=kind,
        first_node=0 if kind == "prefix" else last_node + 1,
        last_node=last_node,
        input_tensors=("x",),
        output_tensors=("h",),
    )


def _result(status: str) -> DeviceRunResult:
    return DeviceRunResult(
        status=status,
        exit_code=0 if status == "pass" else 2,
        output_path=None,
        output_count=4 if status == "pass" else 0,
        finite=status == "pass",
        context_load_us=None,
        graph_execute_us=None,
        timeout_ms=10000 if status == "timeout" else None,
        evidence_paths=(),
    )


class TestBisection(unittest.TestCase):
    def test_bisection_returns_smallest_pass_to_timeout_interval(self) -> None:
        results = (
            (_spec("prefix", 10), _result("pass")),
            (_spec("prefix", 50), _result("pass")),
            (_spec("prefix", 100), _result("timeout")),
            (_spec("prefix", 200), _result("timeout")),
            (_spec("suffix", 50), _result("pass")),
        )
        self.assertEqual(bisect_failure_interval(results), (50, 100))

    def test_all_pass_is_full_graph_scheduling(self) -> None:
        results = (
            (_spec("prefix", 50), _result("pass")),
            (_spec("prefix", 100), _result("pass")),
        )
        with self.assertRaisesRegex(ValueError, "full_graph_scheduling"):
            bisect_failure_interval(results)

    def test_tool_error_is_not_a_model_failure(self) -> None:
        results = (
            (_spec("prefix", 50), _result("pass")),
            (_spec("prefix", 100), _result("tool_error")),
        )
        with self.assertRaisesRegex(ValueError, "tool_error"):
            bisect_failure_interval(results)

    def test_no_pass_interval_starts_at_graph_input(self) -> None:
        results = ((_spec("prefix", 49), _result("timeout")),)
        self.assertEqual(bisect_failure_interval(results), (0, 49))


@NEEDS_ONNX
class TestBisectionLoop(_TempDirTest):
    def _stage_model_path(self) -> Path:
        model = self.root / "stages.onnx"
        onnx.save(_stage_model(), str(model))
        return model

    def test_bisection_stop_at_small_interval(self) -> None:
        stop = bisection_stop(self._stage_model_path(), 0, 6)
        self.assertIsNotNone(stop)
        self.assertEqual(stop["node_count"], 6)
        self.assertIn("<= 16", stop["stop_reason"])

    def test_bisection_stop_when_single_operator_family(self) -> None:
        model = self.root / "identity-chain.onnx"
        nodes = []
        previous = "x"
        for index in range(21):
            output = f"t{index}"
            nodes.append(helper.make_node("Identity", [previous], [output], name=f"n{index}"))
            previous = output
        graph = helper.make_graph(
            nodes,
            "identity-chain",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
            [helper.make_tensor_value_info(previous, TensorProto.FLOAT, [1, 4])],
            initializer=[],
        )
        onnx.save(
            helper.make_model(
                graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8
            ),
            str(model),
        )
        stop = bisection_stop(model, 0, 20)
        self.assertIsNotNone(stop)
        self.assertEqual(stop["operator_families"], ["Identity"])
        self.assertIn("算子族", stop["stop_reason"])

    def test_midpoint_cut_picks_static_middle_tensor(self) -> None:
        sample = _write_raw(self.root / "sample.raw", [1.0, 2.0, 3.0, 4.0])
        cut = midpoint_cut(self._stage_model_path(), 0, 6, sample)
        self.assertIsNotNone(cut)
        self.assertEqual(cut.node_index, 3)
        self.assertEqual(cut.tensor_name, "t3")
        self.assertEqual(cut.shape, (1, 4))
        self.assertEqual(cut.dtype, "float32")

    def test_offline_bisection_awaits_device(self) -> None:
        sample = _write_raw(self.root / "sample.raw", [1.0, 2.0, 3.0, 4.0])
        payload = run_bisection(
            self._stage_model_path(), (0, 6), sample, None, device_online=False
        )
        self.assertEqual(payload["status"], "awaiting_device")
        self.assertFalse(payload["verified"])
        self.assertIsNone(payload["interval"])
        self.assertEqual(payload["awaiting_interval"], [0, 6])
        self.assertEqual(payload["steps"], [])
        self.assertEqual(payload["operator_families"], [])

    def test_bisection_narrows_interval_with_probe_runner(self) -> None:
        model = self.root / "chain.onnx"
        onnx.save(_chain_model(41), str(model))
        sample = _write_raw(self.root / "sample.raw", [1.0, 2.0, 3.0, 4.0])

        def runner(cut: TensorCut):
            status = "pass" if cut.node_index < 20 else "timeout"
            return _spec("prefix", cut.node_index), {"cut": cut.node_index}, _result(status)

        payload = run_bisection(model, (0, 40), sample, runner, device_online=True)
        self.assertEqual(payload["status"], "verified")
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["interval"], [10, 20])
        self.assertEqual(payload["node_count"], 10)
        self.assertEqual(len(payload["steps"]), 2)
        self.assertEqual(payload["steps"][0]["node_index"], 20)
        self.assertEqual(payload["steps"][0]["device"]["status"], "timeout")
        self.assertEqual(payload["steps"][1]["node_index"], 10)
        self.assertEqual(payload["steps"][1]["device"]["status"], "pass")

    def test_probe_error_is_recorded_and_keeps_earlier_steps(self) -> None:
        model = self.root / "chain.onnx"
        onnx.save(_chain_model(41), str(model))
        sample = _write_raw(self.root / "sample.raw", [1.0, 2.0, 3.0, 4.0])

        def runner(cut: TensorCut):
            if cut.node_index >= 30:
                raise ValueError("布局交接未验证")
            return _spec("prefix", cut.node_index), {"cut": cut.node_index}, _result("pass")

        payload = run_bisection(model, (0, 40), sample, runner, device_online=True)
        self.assertEqual(payload["status"], "probe_error")
        self.assertFalse(payload["verified"])
        self.assertIsNone(payload["interval"])
        self.assertEqual(payload["awaiting_interval"], [20, 40])
        self.assertEqual(len(payload["steps"]), 2)
        self.assertEqual(payload["steps"][0]["node_index"], 20)
        self.assertEqual(payload["steps"][0]["device"]["status"], "pass")
        self.assertEqual(payload["steps"][1]["node_index"], 30)
        self.assertEqual(payload["steps"][1]["status"], "probe_error")
        self.assertIn("布局交接未验证", payload["steps"][1]["error"])


class TestDeviceGate(unittest.TestCase):
    def _artifact(self) -> BuildArtifact:
        return BuildArtifact(
            variant_id="test",
            status="config_warning",
            context_path="context.bin",
            metadata=ContextMetadata(
                build_id="v2.51.1.261002",
                soc_model=87,
                dsp_arch=81,
                graph_name="campplus_probe_suffix_0747",
                input_shape=(1, 149, 512),
                output_shape=(1, 192),
            ),
            sha256={},
            commands=(),
            error=None,
        )

    def test_rejected_probes_are_not_pushed_to_device(self) -> None:
        pushed: list[Path] = []

        def fake_run_context(*args, **kwargs):
            pushed.append(args[1])
            return _result("pass")

        specs = [
            ProbeSpec(f"suffix-{node}", "suffix", node + 1, 3101, ("t",), ("embedding",))
            for node in (747, 3076)
        ]
        records = [
            (specs[0], {"probe_id": specs[0].probe_id, "build_status": "layout_rejected"}),
            (specs[1], {"probe_id": specs[1].probe_id, "build_status": "metadata_rejected"}),
        ]
        with mock.patch.object(probe_module, "run_context", fake_run_context):
            runs, results = _run_device_probes(
                records,
                {spec.probe_id: self._artifact() for spec in specs},
                {spec.probe_id: Path("list.txt") for spec in specs},
                Path("probes"),
                device_online=True,
                serial="327366100004",
            )
        self.assertEqual(pushed, [])
        self.assertEqual(results, [])
        for spec in specs:
            self.assertEqual(runs[spec.probe_id]["status"], "device_unavailable")
            self.assertIsNone(runs[spec.probe_id]["device_run"])
        self.assertIn("layout_rejected", runs[specs[0].probe_id]["reason"])
        self.assertIn("metadata_rejected", runs[specs[1].probe_id]["reason"])

    def test_allowed_probe_is_pushed_once(self) -> None:
        spec = ProbeSpec("suffix-747", "suffix", 748, 3101, ("t",), ("embedding",))
        pushed: list[Path] = []

        def fake_run_context(*args, **kwargs):
            pushed.append(args[1])
            return _result("pass")

        with mock.patch.object(probe_module, "run_context", fake_run_context):
            runs, results = _run_device_probes(
                [(spec, {"probe_id": spec.probe_id, "build_status": "config_warning"})],
                {spec.probe_id: self._artifact()},
                {spec.probe_id: Path("list.txt")},
                Path("probes"),
                device_online=True,
                serial="327366100004",
            )
        self.assertEqual(len(pushed), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(runs[spec.probe_id]["status"], "pass")
        self.assertEqual(results[0][0], spec)


@NEEDS_ONNX
class TestLayoutHandoff(_TempDirTest):
    def _manifest(self, semantic: tuple[int, ...]) -> IntermediateManifest:
        raw = (np.arange(int(np.prod(semantic)), dtype="<f4") + 1.0).reshape(semantic)
        raw_path = self.root / "cut.raw"
        raw.tofile(raw_path)
        entry = IntermediateEntry(
            input_path=str(self.root / "input.raw"),
            input_sha256="0" * 64,
            raw_path=str(raw_path),
            sha256="0" * 64,
            shape=semantic,
            dtype="float32",
        )
        return IntermediateManifest(
            path=self.root / "manifest.json",
            source_kind=SOURCE_KIND_REAL_AUDIO,
            tensor_name="h",
            node_index=0,
            shape=semantic,
            dtype="float32",
            model_sha256="0" * 64,
            input_list_sha256="0" * 64,
            entries=(entry,),
        )

    def _metadata(self, input_shape, output_shape) -> ContextMetadata:
        return ContextMetadata(
            build_id="test",
            soc_model=87,
            dsp_arch=81,
            graph_name="probe",
            input_shape=tuple(input_shape),
            output_shape=tuple(output_shape),
        )

    def test_rank3_handoff_transpose_is_verified(self) -> None:
        cut = TensorCut(0, "h", (1, 2, 3), "float32")
        layout = verify_layout_handoff(
            cut,
            self._manifest((1, 2, 3)),
            self._metadata((1, 4), (1, 2, 3)),
            self._metadata((1, 3, 2), (1, 192)),
        )
        self.assertTrue(layout["verified"], layout.get("reason"))
        self.assertEqual(layout["transpose_axes"], [0, 2, 1])
        self.assertEqual(layout["semantic_output_shape"], [1, 2, 3])
        self.assertEqual(layout["prefix_physical_output_shape"], [1, 2, 3])
        self.assertEqual(layout["suffix_physical_input_shape"], [1, 3, 2])
        self.assertEqual(layout["round_trip_max_abs"], 0.0)
        self.assertEqual(layout["cosine_minimum"], 1.0)

    def test_incompatible_handoff_is_rejected(self) -> None:
        cut = TensorCut(0, "h", (1, 2, 3), "float32")
        layout = verify_layout_handoff(
            cut,
            self._manifest((1, 2, 3)),
            self._metadata((1, 4), (1, 2, 3)),
            self._metadata((1, 2, 2), (1, 192)),
        )
        self.assertFalse(layout["verified"])
        self.assertIn("元素数不衔接", layout["reason"])

    def test_missing_metadata_is_rejected(self) -> None:
        cut = TensorCut(0, "h", (1, 2, 3), "float32")
        layout = verify_layout_handoff(
            cut, self._manifest((1, 2, 3)), None, self._metadata((1, 3, 2), (1, 192))
        )
        self.assertFalse(layout["verified"])
        self.assertIn("metadata", layout["reason"])


@NEEDS_ONNX
class TestStageDiscovery(_TempDirTest):
    def test_stage_boundaries_are_stable_and_use_real_node_indices(self) -> None:
        model = self.root / "stages.onnx"
        onnx.save(_stage_model(), str(model))
        sample = _write_raw(self.root / "sample.raw", [1.0, 2.0, 3.0, 4.0])
        cuts = discover_stage_cuts(model, sample)
        self.assertEqual([cut.node_index for cut in cuts], list(range(7)))
        self.assertEqual(cuts[-1].tensor_name, "t6")
        self.assertEqual(cuts[0].shape, (1, 4))
        self.assertEqual(cuts[0].dtype, "float32")
        self.assertEqual(cuts, discover_stage_cuts(model, sample))


@NEEDS_ONNX
@unittest.skipUnless(DEFAULT_MODEL.is_file(), "真实 CAM++ 模型不在本机")
class TestRealStageCuts(unittest.TestCase):
    def test_real_campplus_stage_cuts_are_frozen(self) -> None:
        if not DEFAULT_CALIBRATION.is_file():
            self.skipTest("真实校准列表不在本机")
        first = DEFAULT_CALIBRATION.read_text(encoding="utf-8").splitlines()[0]
        sample = Path(first.split(":=", 1)[1].strip())
        cuts = discover_stage_cuts(DEFAULT_MODEL, sample)
        self.assertEqual(
            [cut.node_index for cut in cuts], [49, 747, 2142, 3076, 3077, 3093, 3101]
        )
        self.assertEqual(
            [cut.tensor_name for cut in cuts],
            [
                "/head/Reshape_output_0",
                "/xvector/block1/Concat_11_output_0",
                "/xvector/block2/Concat_23_output_0",
                "/xvector/transit3/linear/Conv_output_0",
                "/xvector/out_nonlinear/relu/Relu_output_0",
                "/xvector/stats/Concat_output_0",
                "embedding",
            ],
        )
        self.assertTrue(all(cut.shape and cut.dtype == "float32" for cut in cuts))


def _rewrite_result(
    *,
    changed_nodes: tuple[str, ...] = ("stage1",),
    parity: dict | None = None,
) -> RewriteResult:
    return RewriteResult(
        name="constant_fold_static_shape",
        source_sha256="a" * 64,
        output_sha256="b" * 64,
        parity=parity
        if parity is not None
        else {"passed": True, "mode": "exact", "max_abs": 0.0},
        changed_nodes=changed_nodes,
    )


class TestRewriteGate(_TempDirTest):
    def test_rewrite_must_pass_fp32_parity_before_qnn_build(self) -> None:
        result = _rewrite_result(
            parity={
                "passed": False,
                "mode": "cosine",
                "reason": "cosine 漂移",
                "max_abs": 1e-3,
                "cosine_median": 0.99,
                "cosine_minimum": 0.9,
            }
        )
        with self.assertRaisesRegex(ValueError, "FP32 parity"):
            require_rewrite_parity(result)

    def test_exact_parity_is_accepted(self) -> None:
        require_rewrite_parity(_rewrite_result())

    def test_cosine_below_floor_is_rejected(self) -> None:
        result = _rewrite_result(
            parity={
                "passed": True,
                "mode": "cosine",
                "max_abs": 1e-7,
                "cosine_median": 0.9999995,
                "cosine_minimum": 0.9999,
            }
        )
        with self.assertRaisesRegex(ValueError, "FP32 parity"):
            require_rewrite_parity(result)

    def test_cosine_at_threshold_is_accepted(self) -> None:
        result = _rewrite_result(
            parity={
                "passed": True,
                "mode": "cosine",
                "max_abs": 1e-7,
                "cosine_median": 0.999999,
                "cosine_minimum": 0.99999,
            }
        )
        require_rewrite_parity(result)

    def test_awaiting_isolation_blocks_rewrite(self) -> None:
        isolation = {
            "status": "awaiting_device",
            "interval": None,
            "awaiting_interval": [0, 3101],
            "operator_families": [],
        }
        selection = select_rewrite(isolation)
        self.assertEqual(selection["status"], REWRITE_BLOCKED)
        self.assertIsNone(selection["kind"])
        with self.assertRaisesRegex(ValueError, "blocked_on_isolated_interval"):
            apply_semantic_rewrite(
                Path("absent.onnx"), isolation, Path("rewrite.onnx")
            )

    def test_unsupported_operator_family_is_rejected(self) -> None:
        selection = select_rewrite({
            "status": "verified",
            "interval": [10, 12],
            "operator_families": ["MatMul", "Add"],
        })
        self.assertEqual(selection["status"], "unsupported_operator_family")

    def test_missing_changed_node_names_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "changed_nodes"):
            validate_rewrite_result(
                _rewrite_result(changed_nodes=()),
                {"status": "verified", "interval": [0, 1]},
                model=Path("absent.onnx"),
            )

    @NEEDS_ONNX
    def test_unrelated_rewrite_outside_interval_is_rejected(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        with self.assertRaisesRegex(ValueError, "超出隔离区间"):
            validate_rewrite_result(
                _rewrite_result(changed_nodes=("stage2",)),
                {"status": "verified", "interval": [0, 1]},
                model=model,
            )

    @NEEDS_ONNX
    def test_cpu_operator_in_final_path_is_rejected(self) -> None:
        graph = helper.make_graph(
            [
                helper.make_node(
                    "NonMaxSuppression", ["boxes", "scores"], ["selected"],
                    name="nms",
                )
            ],
            "cpu",
            [helper.make_tensor_value_info("boxes", TensorProto.FLOAT, [1, 4, 4])],
            [helper.make_tensor_value_info("selected", TensorProto.INT64, [1, 1])],
        )
        model = self.root / "cpu.onnx"
        onnx.save(
            helper.make_model(
                graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8
            ),
            str(model),
        )
        with self.assertRaisesRegex(ValueError, "CPU 算子"):
            require_htp_executable(model)

    @NEEDS_ONNX
    def test_static_shape_rewrite_passes_exact_parity(self) -> None:
        identity = helper.make_node("Identity", ["x"], ["x0"], name="identity")
        shape_node = helper.make_node("Shape", ["x0"], ["s"], name="shape")
        graph = helper.make_graph(
            [identity, shape_node],
            "shape-only",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])],
            [helper.make_tensor_value_info("s", TensorProto.INT64, [2])],
            initializer=[],
        )
        model = self.root / "shape.onnx"
        onnx.save(
            helper.make_model(
                graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=8
            ),
            str(model),
        )
        result = apply_semantic_rewrite(
            model,
            {
                "status": "verified",
                "interval": [0, 1],
                "operator_families": ["Shape"],
            },
            self.root / "rewrite.onnx",
            input_list=_input_list(self.root),
        )
        self.assertEqual(result.changed_nodes, ("shape",))
        self.assertEqual(result.parity["max_abs"], 0.0)
        selection = select_rewrite({
            "status": "verified",
            "interval": [0, 1],
            "operator_families": ["Shape"],
        })
        self.assertEqual(selection["status"], REWRITE_SELECTED)
        self.assertEqual(selection["kind"], "constant_fold_static_shape")


@NEEDS_ONNX
class TestRewriteGateWithModel(_TempDirTest):
    """落在隔离区间内的改写允许通过（与超范围/缺名字用例形成对照）。"""

    def test_rewrite_inside_interval_is_accepted(self) -> None:
        model = self.root / "tiny.onnx"
        onnx.save(_tiny_model(), str(model))
        validate_rewrite_result(
            _rewrite_result(changed_nodes=("stage1",)),
            {"status": "verified", "interval": [0, 2]},
            model=model,
        )


class TestPartition(_TempDirTest):
    def _manifest(self, *, source_kind: str = SOURCE_KIND_REAL_AUDIO) -> Path:
        raw = self.root / "cut.raw"
        raw.write_bytes(b"\x00" * 16)
        manifest = self.root / "manifest.json"
        manifest.write_text(
            json.dumps({
                "source_kind": source_kind,
                "tensor_name": "h",
                "node_index": 0,
                "shape": [1, 4],
                "dtype": "float32",
                "model_sha256": "0" * 64,
                "entries": [
                    {
                        "input_path": str(self.root / "input.raw"),
                        "input_sha256": "0" * 64,
                        "raw_path": str(raw),
                        "sha256": "0" * 64,
                        "shape": [1, 4],
                        "dtype": "float32",
                    }
                ],
            }),
            encoding="utf-8",
        )
        return manifest

    def test_transfer_bytes_is_cut_tensor_size(self) -> None:
        cut = TensorCut(3093, "h", (1, 1024), "float32")
        self.assertEqual(math.prod(cut.shape) * dtype_size(cut.dtype), 4096)
        self.assertEqual(dtype_size("float32"), 4)
        with self.assertRaisesRegex(ValueError, "dtype"):
            dtype_size("int64")

    def test_more_than_two_partitions_are_rejected(self) -> None:
        artifacts = [
            BuildArtifact(
                variant_id=f"p{index}",
                status="config_warning",
                context_path=None,
                metadata=None,
                sha256={},
                commands=(),
                error=None,
            )
            for index in range(3)
        ]
        with self.assertRaisesRegex(ValueError, "最多"):
            require_partition_limit(artifacts)

    def test_non_real_suffix_calibration_is_rejected(self) -> None:
        manifest = self._manifest(source_kind="random_tensor")
        with self.assertRaisesRegex(ValueError, "fp32_real_audio"):
            build_partition(
                self.root / "absent.onnx",
                TensorCut(0, "h", (1, 4), "float32"),
                variant=mock.Mock(),
                output_dir=self.root / "partition",
                intermediate_manifest=manifest,
            )

    @NEEDS_ONNX
    def test_partition_accounts_for_intermediate_transfer(self) -> None:
        cut = TensorCut(0, "h", (1, 4), "float32")
        input_list = _input_list(self.root)
        manifest = self._manifest()
        toolchain = mock.Mock(build_id="v2.51.1.261002102551", short_version="2.51.1")
        variant = mock.Mock(
            toolchain=toolchain,
            optimization_level=2,
            vtcm_mb=4,
            dlbc=False,
            graph_name="campplus",
        )

        def fake_extract(*args, **kwargs):
            output = Path(args[-1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"onnx")
            return mock.Mock()

        def fake_build(model, calibration, build_variant, output_dir, **kwargs):
            metadata = ContextMetadata(
                build_id="v2.51.1.261002102551",
                soc_model=87,
                dsp_arch=81,
                graph_name=build_variant.graph_name,
                input_shape=(1, 80, 298),
                output_shape=(1, 4),
            )
            return BuildArtifact(
                variant_id=build_variant.variant_id,
                status="config_warning",
                context_path=str(Path(output_dir) / "context" / "g.bin"),
                metadata=metadata,
                sha256={"context": "c" * 64},
                commands=(),
                error=None,
                warning="unexpected GraphHtpSettings option 66",
            )

        with mock.patch.object(probe_module, "extract_prefix", fake_extract), \
                mock.patch.object(probe_module, "extract_suffix", fake_extract), \
                mock.patch.object(
                    probe_module, "verify_probe_parity",
                    return_value={"passed": True, "max_abs": 0.0},
                ), \
                mock.patch.object(
                    probe_module, "build_w8a16_context", fake_build
                ), \
                mock.patch.object(
                    probe_module, "verify_layout_handoff",
                    return_value={"verified": True},
                ):
            plan = build_partition(
                self.root / "model.onnx",
                cut,
                variant,
                self.root / "partition",
                input_list=input_list,
                intermediate_manifest=manifest,
            )
        self.assertIsInstance(plan, PartitionPlan)
        self.assertEqual(
            plan.transfer_bytes, math.prod(cut.shape) * dtype_size(cut.dtype)
        )
        self.assertEqual(plan.prefix_context.metadata.soc_model, 87)
        record = json.loads(
            (self.root / "partition" / "partition.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["status"], "device_unavailable")
        self.assertIsNone(record["device"]["serial"])
        self.assertEqual(record["plan"]["transfer_bytes"], plan.transfer_bytes)


if __name__ == "__main__":
    unittest.main()
