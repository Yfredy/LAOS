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

from scripts.speaker_qnn.contracts import DeviceRunResult  # noqa: E402
from scripts.speaker_qnn.probe import (  # noqa: E402
    DEFAULT_CALIBRATION,
    DEFAULT_MODEL,
    ProbeSpec,
    SOURCE_KIND_REAL_AUDIO,
    TensorCut,
    bisect_failure_interval,
    capture_intermediates,
    discover_stage_cuts,
    extract_prefix,
    extract_suffix,
    load_manifest,
    parity_gate,
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
            model, cut, manifests["h"], self.root / "suffix.onnx"
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
        suffix = extract_suffix(model, cut, manifests["h"], self.root / "suffix.onnx")
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
            model, cut, manifests["h"], self.root / "suffix.onnx"
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
            extract_suffix(model, cut, manifest, self.root / "suffix.onnx")

    def test_tampered_intermediate_sha_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()

        def tamper(payload: dict) -> None:
            payload["entries"][0]["sha256"] = "0" * 64

        self._rewrite_manifest(manifest, tamper)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            extract_suffix(model, cut, manifest, self.root / "suffix.onnx")

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
            extract_suffix(model, cut, manifest, self.root / "suffix.onnx")

    def test_model_sha_mismatch_is_rejected(self) -> None:
        model, cut, manifest = self._prepare()
        self._rewrite_manifest(
            manifest, lambda payload: payload.update({"model_sha256": "0" * 64})
        )
        with self.assertRaisesRegex(ValueError, "模型 SHA-256"):
            extract_suffix(model, cut, manifest, self.root / "suffix.onnx")


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


if __name__ == "__main__":
    unittest.main()
