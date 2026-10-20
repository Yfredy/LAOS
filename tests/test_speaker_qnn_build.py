# tests/test_speaker_qnn_build.py
"""受限 QNN 构建矩阵：同 build 资产、W8A16 转换、SM8845/V81 元数据门禁。

口径（2026-10-20）：版本看似支持 SM8845 但实际静默回退（2.47 →
`socModel=0`、`dspArch=68`）的产物必须在上机前被判 `metadata_rejected`；
转换固定 `--weights_bitwidth 8 --act_bitwidth 16` + 真实语音校准列表；
缺少 V81 skel 或 HTP backend extension 时不得进入构建。矩阵的完整图变体
总数硬上限 10，避免无界试错。

    python -m unittest tests.test_speaker_qnn_build -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.speaker_qnn.build import (  # noqa: E402
    MAX_FULL_GRAPH_VARIANTS,
    BuildVariant,
    ToolchainSpec,
    build_context_command,
    build_converter_command,
    build_model_lib_command,
    build_w8a16_context,
    compiler_variants,
    read_context_metadata,
    require_toolchain_files,
    write_backend_configs,
)

BUILD_ID = "v2.51.1.261002102551"
MODEL = Path("C:/models/campplus-3s-fp32-static-stats.onnx")
CALIBRATION_LIST = Path("C:/models/input_list.txt")


def make_toolchain(root: Path = Path("C:/qairt"), **overrides: object) -> ToolchainSpec:
    values: dict = {
        "build_id": BUILD_ID,
        "root": root,
        "runner": root / "bin/aarch64-android/qnn-net-run",
        "backend_host": root / "lib/x86_64-windows-msvc/QnnHtp.dll",
        "backend_android": root / "lib/aarch64-android/libQnnHtp.so",
        "stub": root / "lib/aarch64-android/libQnnHtpV81Stub.so",
        "skel": root / "lib/hexagon-v81/unsigned/libQnnHtpV81Skel.so",
        "converter": root / "bin/x86_64-windows-msvc/qnn-onnx-converter",
        "context_generator": (
            root / "bin/x86_64-windows-msvc/qnn-context-binary-generator.exe"
        ),
    }
    values.update(overrides)
    return ToolchainSpec(**values)


MIXED_VERSION_INVENTORY = {
    "root": "C:/qairt",
    "build_id": BUILD_ID,
    "components": {
        name: {"path": f"C:/qairt/{name}", "build_id": BUILD_ID}
        for name in (
            "runner",
            "backend_host",
            "backend_android",
            "stub",
            "skel",
            "converter",
            "context_generator",
        )
    },
}
MIXED_VERSION_INVENTORY["components"]["skel"]["build_id"] = "v2.47.0.260601114230"

VARIANT = BuildVariant(
    toolchain=make_toolchain(),
    optimization_level=2,
    vtcm_mb=4,
    dlbc=False,
    graph_name="campplus_w8a16_static_stats",
)


def context_info(**overrides: object) -> dict:
    """真实 2.51.1 CAM++ context info 形状；overrides 用于注入回退值。"""
    payload: dict = {
        "buildId": BUILD_ID,
        "socModel": 87,
        "numGraphs": 1,
        "graphs": [
            {
                "graphName": "campplus_w8a16_static_stats",
                "graphInputs": [{"name": "x", "dimensions": [1, 80, 298]}],
                "graphOutputs": [{"name": "embedding", "dimensions": [1, 192]}],
            }
        ],
        "contextMetadata": {"dspArch": 81},
    }
    payload.update(overrides)
    return payload


class TestToolchainInventory(unittest.TestCase):
    def test_toolchain_assets_must_share_one_build_id(self):
        with self.assertRaisesRegex(ValueError, "mixed QAIRT build"):
            ToolchainSpec.from_inventory(MIXED_VERSION_INVENTORY)

    def test_inventory_must_describe_every_component(self):
        inventory = {
            "root": "C:/qairt",
            "build_id": BUILD_ID,
            "components": {"runner": {"path": "C:/qairt/runner", "build_id": BUILD_ID}},
        }
        with self.assertRaisesRegex(ValueError, "inventory"):
            ToolchainSpec.from_inventory(inventory)

    def test_missing_v81_skel_is_rejected_before_build(self):
        toolchain = make_toolchain(skel=Path("C:/qairt/missing/libQnnHtpV81Skel.so"))
        with self.assertRaisesRegex(FileNotFoundError, "V81 skel"):
            require_toolchain_files(toolchain)


class TestBuildCommands(unittest.TestCase):
    def test_build_command_preserves_w8a16_and_real_calibration(self):
        command = build_converter_command(MODEL, CALIBRATION_LIST, VARIANT)
        self.assertIn("--weights_bitwidth 8", command)
        self.assertIn("--act_bitwidth 16", command)
        self.assertIn(str(CALIBRATION_LIST), command)

    def test_model_lib_command_keeps_graph_name_and_windows_target(self):
        command = build_model_lib_command(
            Path("C:/builds/model/campplus_w8a16_static_stats.cpp"),
            Path("C:/builds/model/campplus_w8a16_static_stats.bin"),
            VARIANT,
            Path("C:/builds/lib"),
        )
        self.assertIn("campplus_w8a16_static_stats.cpp", command)
        self.assertIn("windows-x86_64", command)
        self.assertIn(str(Path("C:/builds/lib")), command)

    def test_context_command_pins_sm8845_and_variant_switches(self):
        command = build_context_command(
            Path("C:/builds/model/campplus_w8a16_static_stats.dll"),
            Path("C:/builds/context"),
            Path("C:/builds/context/backend_extensions.json"),
            VARIANT,
        )
        self.assertIn("--htp_socs sm8845", command)
        self.assertIn("--optimization_level_override 2", command)
        self.assertIn("--dlbc_override false", command)
        self.assertIn("--backend", command)

    def test_backend_config_carries_vtcm_and_graph_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extension = root / "lib/x86_64-windows-msvc/QnnHtpNetRunExtensions.dll"
            extension.parent.mkdir(parents=True)
            extension.write_bytes(b"stub")
            variant = BuildVariant(
                toolchain=make_toolchain(root), optimization_level=3, vtcm_mb=8,
                dlbc=False, graph_name="campplus_w8a16_static_stats",
            )
            graph_config, wrapper = write_backend_configs(root / "context", variant)
            graph = json.loads(graph_config.read_text(encoding="utf-8"))
            outer = json.loads(wrapper.read_text(encoding="utf-8"))
            self.assertEqual(graph["graphs"][0]["vtcm_mb"], 8)
            self.assertEqual(
                graph["graphs"][0]["graph_names"], ["campplus_w8a16_static_stats"]
            )
            self.assertEqual(
                outer["backend_extensions"]["shared_library_path"],
                str(extension),
            )
            self.assertEqual(
                outer["backend_extensions"]["config_file_path"], str(graph_config)
            )

    def test_absent_backend_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            variant = BuildVariant(
                toolchain=make_toolchain(root), optimization_level=2, vtcm_mb=4,
                dlbc=False, graph_name="campplus_w8a16_static_stats",
            )
            with self.assertRaisesRegex(FileNotFoundError, "QnnHtpNetRunExtensions"):
                write_backend_configs(root / "context", variant)


class TestContextMetadataGate(unittest.TestCase):
    def inspect(self, payload: dict) -> tuple:
        with tempfile.TemporaryDirectory() as temporary:
            info = Path(temporary) / "info.json"
            info.write_text(json.dumps(payload), encoding="utf-8")
            return read_context_metadata(info, graph_name="campplus_w8a16_static_stats")

    def test_qairt_247_silent_fallback_is_metadata_rejected(self):
        metadata, error = self.inspect(
            context_info(socModel=0, contextMetadata={"dspArch": 68})
        )
        self.assertIsNone(metadata)
        self.assertIn("socModel=0", error or "")
        self.assertIn("dspArch=68", error or "")

    def test_graph_name_mismatch_is_metadata_rejected(self):
        payload = context_info()
        payload["graphs"][0]["graphName"] = "other_graph"
        metadata, error = self.inspect(payload)
        self.assertIsNone(metadata)
        self.assertIn("graph", (error or "").lower())
        self.assertIn("other_graph", error or "")

    def test_wrong_shapes_are_metadata_rejected(self):
        payload = context_info()
        payload["graphs"][0]["graphInputs"][0]["dimensions"] = [1, 298, 80]
        metadata, error = self.inspect(payload)
        self.assertIsNone(metadata)
        self.assertIn("形状", error or "")

    def test_sm8845_v81_metadata_is_accepted(self):
        metadata, error = self.inspect(context_info())
        self.assertIsNone(error)
        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata.soc_model, 87)
        self.assertEqual(metadata.dsp_arch, 81)
        self.assertEqual(metadata.input_shape, (1, 80, 298))


class TestBoundedMatrix(unittest.TestCase):
    def test_compiler_matrix_covers_all_levels_at_4mb_and_stays_bounded(self):
        variants = compiler_variants(make_toolchain())
        self.assertLessEqual(len(variants), MAX_FULL_GRAPH_VARIANTS)
        self.assertEqual(
            {variant.optimization_level for variant in variants}, {0, 1, 2, 3}
        )
        self.assertEqual({variant.vtcm_mb for variant in variants}, {4})
        self.assertTrue(all(not variant.dlbc for variant in variants))
        self.assertEqual(
            len({variant.variant_id for variant in variants}), len(variants)
        )


class TestFailedArtifact(unittest.TestCase):
    def test_failed_build_writes_atomic_artifact_without_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "model.onnx"
            model.write_bytes(b"onnx")
            calibration = root / "input_list.txt"
            calibration.write_text("x:=a.raw\n", encoding="ascii")
            variant = BuildVariant(
                toolchain=make_toolchain(root / "qairt", converter=root / "absent"),
                optimization_level=2, vtcm_mb=4, dlbc=False,
                graph_name="campplus_w8a16_static_stats",
            )
            output_dir = root / "builds/variant"
            artifact = build_w8a16_context(model, calibration, variant, output_dir)
            self.assertEqual(artifact.status, "build_error")
            self.assertIsNone(artifact.context_path)
            payload = json.loads(
                (output_dir / "artifact.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["status"], "build_error")
            self.assertEqual(payload["variant_id"], artifact.variant_id)
            self.assertTrue(payload["error"])
            self.assertEqual(
                list((output_dir / "context").glob("*.bin")), []
            )


if __name__ == "__main__":
    unittest.main()
