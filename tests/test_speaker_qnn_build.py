# tests/test_speaker_qnn_build.py
"""受限 QNN 构建矩阵：同 build 资产、W8A16 转换、SM8845/V81 元数据门禁。

口径（2026-10-20）：版本看似支持 SM8845 但实际静默回退（2.47 →
`socModel=0`）的产物必须在上机前被判 `metadata_rejected`；转换固定
`--weights_bitwidth 8 --act_bitwidth 16` + 真实语音校准列表；缺少 V81 skel
或 HTP backend extension 时不得进入构建。矩阵的完整图变体总数硬上限 10，
避免无界试错。另有四条硬约束：真执行只用 argv 构造器（测试断言真 argv）、
context 的 build ID 必须与候选树一致、context generator 的
`unexpected GraphHtpSettings` 必须记 `config_warning`、失败的构建不得留下
任何 context 产物。

    python -m unittest tests.test_speaker_qnn_build -v
"""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.speaker_qnn.build as build_module  # noqa: E402
from scripts.speaker_qnn.build import (  # noqa: E402
    BUILD_CALIBRATION_REJECTED,
    CALIBRATION_MANIFEST_NAME,
    CALIBRATION_SUMS_NAME,
    MAX_FULL_GRAPH_VARIANTS,
    BuildArtifact,
    BuildVariant,
    ToolchainSpec,
    _parse_qpm_versions,
    _qpm_record,
    build_context_argv,
    build_context_command,
    build_converter_argv,
    build_converter_command,
    build_model_lib_command,
    build_w8a16_context,
    compare_contexts,
    compiler_variants,
    config_warning,
    probe_qpm_candidates,
    read_context_metadata,
    require_toolchain_files,
    validate_calibration,
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
        "profile_viewer": root / "bin/x86_64-windows-msvc/qnn-profile-viewer.exe",
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
            "profile_viewer",
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


def make_toolchain_files(toolchain: ToolchainSpec) -> None:
    """把 ToolchainSpec 里的十个文件落成真实占位文件。"""
    for path in (
        toolchain.runner,
        toolchain.backend_host,
        toolchain.backend_android,
        toolchain.stub,
        toolchain.skel,
        toolchain.converter,
        toolchain.context_generator,
        toolchain.model_lib_generator,
        toolchain.context_utility,
        toolchain.net_run_extensions,
        toolchain.profile_viewer,
    ):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"stub")


def fake_pipeline(*, info_overrides: dict | None = None, warning: bool = False):
    """按步骤伪造 QAIRT 产物，用于验证目录清理/配置告警而不跑真编译。"""
    graph = "campplus_w8a16_static_stats"

    def run(argv, log_path, *, env, timeout, cwd=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok\n", encoding="utf-8")
        joined = " ".join(str(part) for part in argv)
        if "qnn-onnx-converter" in joined:
            (log_path.parent / f"{graph}.cpp").write_text("// cpp", encoding="utf-8")
            (log_path.parent / f"{graph}.bin").write_bytes(b"bin")
        elif "qnn-model-lib-generator" in joined:
            dll = log_path.parent / "lib/x64" / f"{graph}.dll"
            dll.parent.mkdir(parents=True, exist_ok=True)
            dll.write_bytes(b"dll")
        elif "qnn-context-binary-generator" in joined:
            (log_path.parent / f"{graph}.bin.SM8845.bin").write_bytes(b"ctx")
            if warning:
                log_path.write_text(
                    "qnn-context-binary-generator pid:1\n"
                    "    74.9ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66\n",
                    encoding="utf-8",
                )
        elif "qnn-context-binary-utility" in joined:
            (log_path.parent / "info.json").write_text(
                json.dumps(context_info(**(info_overrides or {}))), encoding="utf-8"
            )
        return 0

    return run


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_calibration(
    base: Path,
    *,
    records: int = 40,
    speakers: int = 20,
    overlap: bool = False,
    corrupt_sha: bool = False,
    omit_raw_from_sums: bool = False,
) -> Path:
    """真实形状的校准清单：40 条 raw、20 个说话人、评估集排他。"""
    calibration_dir = base / "calibration"
    calibration_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    sum_lines = []
    for index in range(records):
        speaker = f"{3000 + index % speakers}"
        raw = calibration_dir / f"{index:03d}-{speaker}.raw"
        raw.write_bytes(f"raw-{index}".encode("ascii"))
        actual = _sha256(raw)
        digest = actual
        if corrupt_sha and index == 0:
            digest = "0" * 64
        entries.append(
            {
                "speaker": speaker,
                "raw": f"calibration/{raw.name}",
                "raw_sha256": digest,
            }
        )
        if not (omit_raw_from_sums and index == 0):
            sum_lines.append(f"{actual}  calibration/{raw.name}\n")
    excluded = [f"{9000 + index}" for index in range(speakers)]
    if overlap:
        excluded[0] = entries[0]["speaker"]
    manifest_path = base / CALIBRATION_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "evaluation_speakers_excluded": excluded,
                "records": entries,
            }
        ),
        encoding="utf-8",
    )
    (base / CALIBRATION_SUMS_NAME).write_text(
        f"{_sha256(manifest_path)}  {CALIBRATION_MANIFEST_NAME}\n"
        + "".join(sum_lines),
        encoding="ascii",
    )
    return base / "input_list.txt"


def make_build_inputs(root: Path) -> tuple[Path, Path, ToolchainSpec]:
    model = root / "model.onnx"
    model.write_bytes(b"onnx")
    calibration = write_calibration(root)
    calibration.write_text("x:=a.raw\n", encoding="ascii")
    toolchain = make_toolchain(root / "qairt")
    make_toolchain_files(toolchain)
    return model, calibration, toolchain


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


class TestCalibrationGate(unittest.TestCase):
    def test_valid_calibration_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base)
            summary = validate_calibration(calibration)
            self.assertEqual(summary["records"], 40)
            self.assertEqual(summary["speakers"], 20)

    def test_record_count_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base, records=39)
            with self.assertRaisesRegex(ValueError, "记录数"):
                validate_calibration(calibration)

    def test_raw_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base, corrupt_sha=True)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                validate_calibration(calibration)

    def test_evaluation_speaker_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base, overlap=True)
            with self.assertRaisesRegex(ValueError, "重叠"):
                validate_calibration(calibration)

    def test_manifest_raw_absent_from_sums_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base, omit_raw_from_sums=True)
            with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
                validate_calibration(calibration)

    def test_same_named_raw_elsewhere_does_not_satisfy_sums(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            calibration = write_calibration(base)
            first = base / "calibration" / "000-3000.raw"
            decoy = base / "decoy" / first.name
            decoy.parent.mkdir(parents=True)
            decoy.write_bytes(first.read_bytes())
            sums = base / CALIBRATION_SUMS_NAME
            text = sums.read_text(encoding="utf-8").replace(
                "calibration/000-3000.raw", "decoy/000-3000.raw"
            )
            sums.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
                validate_calibration(calibration)

    def test_artifact_binds_calibration_manifest_and_sums(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, calibration, toolchain = make_build_inputs(root)
            variant = BuildVariant(
                toolchain, 2, 4, False, "campplus_w8a16_static_stats"
            )
            with mock.patch.object(build_module, "_run_step", fake_pipeline()):
                artifact = build_w8a16_context(
                    model, calibration, variant, root / "builds/variant"
                )
            self.assertEqual(
                artifact.sha256["calibration_manifest"],
                _sha256(root / CALIBRATION_MANIFEST_NAME),
            )
            self.assertEqual(
                artifact.sha256["calibration_sums"],
                _sha256(root / CALIBRATION_SUMS_NAME),
            )

    def test_derived_input_list_gates_against_source_calibration(self):
        """probe 前缀/后缀用的是派生清单，门禁必须回到源校准集对账。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, calibration, toolchain = make_build_inputs(root)
            derived_dir = root / "probe"
            derived_dir.mkdir(parents=True)
            derived = derived_dir / "input_list.txt"
            derived.write_bytes(calibration.read_bytes())
            variant = BuildVariant(
                toolchain, 2, 4, False, "campplus_w8a16_static_stats"
            )
            with mock.patch.object(build_module, "_run_step", fake_pipeline()):
                rejected = build_w8a16_context(
                    model, derived, variant, root / "builds/derived"
                )
                accepted = build_w8a16_context(
                    model,
                    derived,
                    variant,
                    root / "builds/derived-evidence",
                    calibration_evidence=calibration,
                )
            self.assertEqual(rejected.status, BUILD_CALIBRATION_REJECTED)
            self.assertIn("校准清单缺失", rejected.error or "")
            self.assertNotEqual(accepted.status, BUILD_CALIBRATION_REJECTED)
            self.assertEqual(
                accepted.sha256["calibration_list"], _sha256(derived)
            )

    def test_execute_error_counts_as_build_failure(self):
        self.assertIn("execute_error", build_module.FAILURE_STATUSES)

    def test_bad_calibration_refuses_build_before_converter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, calibration, toolchain = make_build_inputs(root)
            write_calibration(root, overlap=True)
            variant = BuildVariant(
                toolchain, 2, 4, False, "campplus_w8a16_static_stats"
            )
            output_dir = root / "builds/variant"
            with mock.patch.object(
                build_module, "_run_step", side_effect=AssertionError("不得启动转换")
            ):
                artifact = build_w8a16_context(model, calibration, variant, output_dir)
            self.assertEqual(artifact.status, BUILD_CALIBRATION_REJECTED)
            self.assertIn("校准清单被拒绝", artifact.error or "")
            self.assertIsNone(artifact.context_path)


class TestBuildCommands(unittest.TestCase):
    def test_build_command_preserves_w8a16_and_real_calibration(self):
        command = build_converter_command(MODEL, CALIBRATION_LIST, VARIANT)
        self.assertIn("--weights_bitwidth 8", command)
        self.assertIn("--act_bitwidth 16", command)
        self.assertIn(str(CALIBRATION_LIST), command)

    def test_real_converter_argv_is_the_rendered_command(self):
        """真执行用的 argv 才是唯一真源：删掉 W8A16 参数必须在这里红。"""
        argv = build_converter_argv(MODEL, CALIBRATION_LIST, VARIANT)
        self.assertIn("--weights_bitwidth", argv)
        self.assertEqual(argv[argv.index("--weights_bitwidth") + 1], "8")
        self.assertIn("--act_bitwidth", argv)
        self.assertEqual(argv[argv.index("--act_bitwidth") + 1], "16")
        self.assertEqual(argv[argv.index("--input_list") + 1], str(CALIBRATION_LIST))
        self.assertEqual(
            build_converter_command(MODEL, CALIBRATION_LIST, VARIANT),
            subprocess.list2cmdline(argv),
        )

    def test_real_context_argv_pins_sm8845_and_variant_switches(self):
        argv = build_context_argv(
            Path("C:/builds/model/campplus_w8a16_static_stats.dll"),
            Path("C:/builds/context"),
            Path("C:/builds/context/backend_extensions.json"),
            VARIANT,
        )
        self.assertEqual(argv[argv.index("--htp_socs") + 1], "sm8845")
        self.assertEqual(argv[argv.index("--optimization_level_override") + 1], "2")
        self.assertEqual(argv[argv.index("--dlbc_override") + 1], "false")
        self.assertEqual(argv[argv.index("--backend") + 1], str(VARIANT.toolchain.backend_host))

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

    def test_build_id_mismatch_is_metadata_rejected(self):
        """context 出自别的 QAIRT build（如 2.47 的产物）必须被拒。"""
        with tempfile.TemporaryDirectory() as temporary:
            info = Path(temporary) / "info.json"
            info.write_text(
                json.dumps(context_info(buildId="v2.47.0.260601114230")),
                encoding="utf-8",
            )
            metadata, error = read_context_metadata(
                info,
                graph_name="campplus_w8a16_static_stats",
                expected_build_id=BUILD_ID,
            )
        self.assertIsNone(metadata)
        self.assertIn("build ID", error or "")
        self.assertIn("v2.47.0.260601114230", error or "")


class TestConfigWarningGate(unittest.TestCase):
    def test_graph_htp_settings_error_is_marked_as_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "context-generator.log"
            log.write_text(
                "qnn-context-binary-generator pid:1\n"
                "    74.9ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66\n"
                "Cache binary for SM8845 copied\n",
                encoding="utf-8",
            )
            warning = config_warning(log)
        self.assertIsNotNone(warning)
        self.assertIn("GraphHtpSettings", warning or "")

    def test_clean_log_has_no_warning(self):
        with tempfile.TemporaryDirectory() as temporary:
            log = Path(temporary) / "context-generator.log"
            log.write_text("Cache binary for SM8845 copied\n", encoding="utf-8")
            self.assertIsNone(config_warning(log))
        self.assertIsNone(config_warning(Path("C:/absent/context-generator.log")))

    def test_warning_build_is_config_warning_not_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, calibration, toolchain = make_build_inputs(root)
            variant = BuildVariant(toolchain, 2, 4, False, "campplus_w8a16_static_stats")
            with mock.patch.object(
                build_module, "_run_step", fake_pipeline(warning=True)
            ):
                artifact = build_w8a16_context(
                    model, calibration, variant, root / "builds/variant"
                )
            self.assertEqual(artifact.status, "config_warning")
            self.assertIn("GraphHtpSettings", artifact.warning or "")
            self.assertIsNotNone(artifact.context_path)
            self.assertTrue((root / "builds/variant/context").is_dir())


class TestFailedBuildCleanup(unittest.TestCase):
    def test_metadata_rejected_leaves_no_context_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, calibration, toolchain = make_build_inputs(root)
            variant = BuildVariant(toolchain, 2, 4, False, "campplus_w8a16_static_stats")
            output_dir = root / "builds/variant"
            with mock.patch.object(
                build_module, "_run_step",
                fake_pipeline(info_overrides={"socModel": 0}),
            ):
                artifact = build_w8a16_context(model, calibration, variant, output_dir)
            self.assertEqual(artifact.status, "metadata_rejected")
            self.assertIsNone(artifact.context_path)
            self.assertEqual(
                sorted(path.name for path in output_dir.iterdir()), ["artifact.json"]
            )
            self.assertEqual(list(output_dir.rglob("*.bin")), [])
            self.assertFalse((output_dir / "context").exists())


class TestQpmInventory(unittest.TestCase):
    QPM_OUTPUT = (
        "\nProduct Name           : qualcomm_ai_runtime_community\n"
        "Product Classification : Executable\n"
        "Installed version      : None\n"
        "Available version(s)   : 2.51.40.260930\n"
        "                         2.51.1.261002\n"
        "                         2.47.0.260601\n"
        "\n"
    )

    def test_versions_are_parsed_from_qpm_info(self):
        self.assertEqual(
            _parse_qpm_versions(self.QPM_OUTPUT),
            ["2.51.40.260930", "2.51.1.261002", "2.47.0.260601"],
        )

    def test_successful_query_reports_available_versions(self):
        record = probe_qpm_candidates(runner=lambda command: self.QPM_OUTPUT)
        self.assertEqual(record["status"], "available")
        self.assertEqual(record["product"], "qualcomm_ai_runtime_community")
        self.assertIn("2.51.40.260930", record["available_versions"])

    def test_offline_query_is_explicitly_unavailable(self):
        def offline(command: str) -> str:
            raise OSError("network unreachable")

        record = probe_qpm_candidates(runner=offline)
        self.assertEqual(record["status"], "unavailable")
        self.assertIn("network unreachable", record["reason"])

    def test_empty_output_is_explicitly_unavailable(self):
        record = probe_qpm_candidates(runner=lambda command: "no versions here\n")
        self.assertEqual(record["status"], "unavailable")
        self.assertIn("版本", record["reason"])

    def test_newer_qpm_version_without_local_tree_is_unavailable(self):
        """QPM 列出更新版本但本机没装：必须显式 unavailable + 原因。"""
        toolchain = make_toolchain()
        record = _qpm_record(
            (toolchain.root,),
            (toolchain,),
            {
                "status": "available",
                "product": "qualcomm_ai_runtime_community",
                "command": "C:/qpm/qpm-cli.exe",
                "available_versions": ["2.51.40.260930", "2.51.1.261002"],
            },
        )
        self.assertEqual(record["status"], "unavailable")
        self.assertIn("2.51.40.260930", record["reason"])
        self.assertEqual(record["newer_than_local"], ["2.51.40.260930"])
        self.assertEqual(record["local_build_ids"], [BUILD_ID])

    def test_qpm_newest_version_installed_is_recorded_as_installed(self):
        """QPM 最新的 2.51.40 已纳入本地矩阵：不再是 unavailable。"""
        toolchain = make_toolchain(build_id="v2.51.40.260930230134")
        record = _qpm_record(
            (toolchain.root,),
            (toolchain,),
            {
                "status": "available",
                "product": "qualcomm_ai_runtime_community",
                "command": "C:/qpm/qpm-cli.exe",
                "available_versions": ["2.51.40.260930", "2.51.1.261002"],
            },
        )
        self.assertEqual(record["status"], "installed")
        self.assertEqual(record["newer_than_local"], [])
        self.assertEqual(record["installed_versions"], ["2.51.40.260930"])
        self.assertEqual(record["local_build_ids"], ["v2.51.40.260930230134"])

    def test_mixed_installed_and_missing_versions_only_lists_missing(self):
        """已装+未装混态：`newer_than_local` 只能含未安装版本。

        本地树同时含 2.51.1 与 2.51.40，QPM 列表里这两版已装、2.52.0 未装；
        若过滤条件退化成 `>=` 或丢失"排除已装"，2.51.40.260930 会重新落
        进 `newer_than_local`，本用例即失败。
        """
        installed = make_toolchain(root=Path("C:/qairt-2.51.1"))
        newer = make_toolchain(
            root=Path("C:/qairt-2.51.40"),
            build_id="v2.51.40.260930230134",
        )
        record = _qpm_record(
            (installed.root, newer.root),
            (installed, newer),
            {
                "status": "available",
                "product": "qualcomm_ai_runtime_community",
                "command": "C:/qpm/qpm-cli.exe",
                "available_versions": [
                    "2.52.0.261001000000",
                    "2.51.40.260930",
                    "2.51.1.261002",
                ],
            },
        )
        self.assertEqual(record["status"], "unavailable")
        self.assertEqual(record["newer_than_local"], ["2.52.0.261001000000"])
        self.assertEqual(
            record["installed_versions"], ["2.51.40.260930", "2.51.1.261002"]
        )


class TestVtcmEquivalence(unittest.TestCase):
    def artifact(self, variant_id: str, digest: str) -> BuildArtifact:
        return BuildArtifact(
            variant_id=variant_id,
            status="ready",
            context_path=f"C:/builds/{variant_id}/context/graph.bin",
            metadata=None,
            sha256={"context": digest},
            commands=(),
            error=None,
        )

    def test_identical_context_binaries_are_equivalent(self):
        record = compare_contexts(
            self.artifact("2.51.1-opt2-vtcm4-dlbc0-g", "a" * 64),
            self.artifact("2.51.1-opt2-vtcm8-dlbc0-g", "a" * 64),
        )
        self.assertEqual(record["status"], "equivalent")

    def test_different_context_binaries_are_distinct(self):
        record = compare_contexts(
            self.artifact("2.51.1-opt2-vtcm4-dlbc0-g", "a" * 64),
            self.artifact("2.51.1-opt2-vtcm8-dlbc0-g", "b" * 64),
        )
        self.assertEqual(record["status"], "distinct")

    def test_missing_context_hash_is_unavailable(self):
        record = compare_contexts(
            self.artifact("2.51.1-opt2-vtcm4-dlbc0-g", "a" * 64),
            BuildArtifact(
                variant_id="2.51.1-opt2-vtcm8-dlbc0-g",
                status="build_error",
                context_path=None,
                metadata=None,
                sha256={},
                commands=(),
                error="context 生成失败",
            ),
        )
        self.assertEqual(record["status"], "unavailable")


class TestMatrixEquivalenceDedup(unittest.TestCase):
    """opt0 与 opt2 同 context → 后者不算独立变体；VTCM 未证实前不升级。"""

    def artifact(
        self, variant: BuildVariant, status: str, digest: str,
        warning: str | None = None,
    ) -> BuildArtifact:
        return BuildArtifact(
            variant_id=variant.variant_id,
            status=status,
            context_path=f"C:/builds/{variant.variant_id}/context/{variant.graph_name}.bin",
            metadata=None,
            sha256={"context": digest},
            commands=(),
            error=None if status != "timeout" else "watchdog",
            warning=warning,
        )

    def test_same_context_and_unproven_vtcm_do_not_extend_budget(self):
        toolchain = make_toolchain()
        digests = {0: "a" * 64, 1: "b" * 64, 2: "a" * 64, 3: "c" * 64}

        def fake_build(model, calibration_list, variant, output_dir, **kwargs):
            if variant.graph_name == "smoke_w8a16":
                return self.artifact(variant, "ready", "f" * 64)
            if variant.vtcm_mb == 8:
                # 8 MB 与 opt2 的 4 MB 逐字节相同 → VTCM 不是独立变量。
                return self.artifact(variant, "config_warning", "a" * 64, "warn")
            return self.artifact(
                variant, "timeout", digests[variant.optimization_level]
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(
                build_module, "discover_toolchains", return_value=(toolchain,)
            ), mock.patch.object(
                build_module, "build_w8a16_context", side_effect=fake_build
            ):
                payload = build_module.run_matrix(
                    "compiler",
                    output_root=root,
                    qpm_probe={"status": "unavailable", "reason": "test"},
                )
        rows = {row["variant_id"]: row for row in payload["variants"]}
        opt0 = f"{toolchain.short_version}-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats"
        opt2 = f"{toolchain.short_version}-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats"
        self.assertEqual(rows[opt2]["equivalent_to"], opt0)
        self.assertNotIn("equivalent_to", rows[opt0])
        self.assertEqual(payload["summary"]["full_graph_variants"], 3)
        self.assertEqual(payload["summary"]["full_graph_rows"], 4)
        self.assertEqual(payload["vtcm_equivalence"]["status"], "equivalent")
        self.assertEqual(payload["vtcm_escalation"]["status"], "skipped")
        self.assertIn("不是独立变量", payload["vtcm_escalation"]["reason"])
        self.assertFalse(
            any(row["variant_id"].endswith("vtcm8-dlbc0-campplus_w8a16_static_stats")
                for row in payload["variants"])
        )
        self.assertEqual(payload["qpm"]["status"], "unavailable")


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
