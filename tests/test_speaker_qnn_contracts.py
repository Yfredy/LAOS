# tests/test_speaker_qnn_contracts.py
"""SM8845/V81 QNN 契约门禁：context 元数据 + schema 序列化。

故障基线（2026-10-20 实录）：CAM++ W8A16 context 在 SM8845（HTP V81）
上 `gpe_execute_novalidate` 后 10.001 s 被 FastRPC 看门狗终止，QNN 返回
`err 1003` 并触发 CDSP SSR，没有 embedding 输出；同一台机器的 y=x+1
smoke context 正常。QAIRT 2.47 对 SM8845 曾静默回退 `socModel=0`、
`dspArch=68`——任何这类产物都必须在上机前被拒绝，不能靠"看起来能跑"。

本文件只锁 metadata 门禁与 JSON 契约；真机输出分类在
`tests/test_speaker_qnn_device.py`。

    python -m unittest tests.test_speaker_qnn_contracts -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.speaker_qnn import SCHEMA_VERSION  # noqa: E402
from scripts.speaker_qnn.contracts import (  # noqa: E402
    ContextMetadata,
    load_context_metadata,
    validate_sm8845_context,
)


def context_info(**overrides: object) -> dict:
    """一份真实形状的 context info.json（CAM++ W8A16, QAIRT 2.51.1）。"""
    payload: dict = {
        "buildId": "v2.51.1.261002102551",
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


class TestContextMetadataGate(unittest.TestCase):
    def test_schema_version_is_declared(self) -> None:
        self.assertIsInstance(SCHEMA_VERSION, int)
        self.assertGreaterEqual(SCHEMA_VERSION, 1)

    def test_sm8845_metadata_rejects_silent_arch_fallback(self):
        metadata = ContextMetadata(
            build_id="v2.47.0",
            soc_model=0,
            dsp_arch=68,
            graph_name="campplus",
            input_shape=(1, 80, 298),
            output_shape=(1, 192),
        )
        with self.assertRaisesRegex(ValueError, "SM8845/V81"):
            validate_sm8845_context(metadata)

    def test_sm8845_metadata_accepts_campplus(self) -> None:
        metadata = ContextMetadata(
            build_id="v2.51.1.261002102551",
            soc_model=87,
            dsp_arch=81,
            graph_name="campplus_w8a16_static_stats",
            input_shape=(1, 80, 298),
            output_shape=(1, 192),
        )
        validate_sm8845_context(metadata)

    def test_rejects_semantic_layout_as_physical_input(self) -> None:
        """语义布局 [1,298,80] 不是 context 的物理输入布局，必须拒绝。"""
        metadata = ContextMetadata(
            build_id="v2.51.1.261002102551",
            soc_model=87,
            dsp_arch=81,
            graph_name="campplus_w8a16_static_stats",
            input_shape=(1, 298, 80),
            output_shape=(1, 192),
        )
        with self.assertRaisesRegex(ValueError, "SM8845/V81"):
            validate_sm8845_context(metadata)

    def test_rejects_wrong_embedding_width(self) -> None:
        metadata = ContextMetadata(
            build_id="v2.51.1.261002102551",
            soc_model=87,
            dsp_arch=81,
            graph_name="campplus_w8a16_static_stats",
            input_shape=(1, 80, 298),
            output_shape=(1, 256),
        )
        with self.assertRaisesRegex(ValueError, "SM8845/V81"):
            validate_sm8845_context(metadata)

    def test_smoke_may_opt_into_explicit_shapes(self) -> None:
        metadata = ContextMetadata(
            build_id="v2.51.1.261002102551",
            soc_model=87,
            dsp_arch=81,
            graph_name="smoke_w8a16",
            input_shape=(1, 16),
            output_shape=(1, 16),
        )
        validate_sm8845_context(
            metadata,
            expected_input_shape=(1, 16),
            expected_output_shape=(1, 16),
        )

    def test_metadata_serializes_shapes_as_lists(self) -> None:
        metadata = ContextMetadata(
            build_id="v2.51.1.261002102551",
            soc_model=87,
            dsp_arch=81,
            graph_name="campplus_w8a16_static_stats",
            input_shape=(1, 80, 298),
            output_shape=(1, 192),
        )
        payload = json.loads(metadata.to_json())
        self.assertEqual(payload["input_shape"], [1, 80, 298])
        self.assertEqual(payload["output_shape"], [1, 192])
        self.assertEqual(payload["build_id"], "v2.51.1.261002102551")


class TestLoadContextMetadata(unittest.TestCase):
    def _write(self, payload: dict) -> Path:
        directory = Path(self.tmp.name)
        path = directory / "info.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_reads_single_graph_context(self) -> None:
        metadata = load_context_metadata(self._write(context_info()))
        self.assertEqual(
            metadata,
            ContextMetadata(
                build_id="v2.51.1.261002102551",
                soc_model=87,
                dsp_arch=81,
                graph_name="campplus_w8a16_static_stats",
                input_shape=(1, 80, 298),
                output_shape=(1, 192),
            ),
        )

    def test_rejects_multiple_graphs(self) -> None:
        payload = context_info(numGraphs=2)
        payload["graphs"].append(dict(payload["graphs"][0]))
        with self.assertRaisesRegex(ValueError, "graph"):
            load_context_metadata(self._write(payload))

    def test_rejects_missing_soc_model(self) -> None:
        payload = context_info()
        del payload["socModel"]
        with self.assertRaisesRegex(ValueError, "SM8845/V81"):
            load_context_metadata(self._write(payload))

    def test_rejects_missing_dsp_arch(self) -> None:
        payload = context_info(contextMetadata={})
        with self.assertRaisesRegex(ValueError, "SM8845/V81"):
            load_context_metadata(self._write(payload))

    def test_rejects_wrong_input_count(self) -> None:
        payload = context_info()
        payload["graphs"][0]["graphInputs"].append({"dimensions": [1, 16]})
        with self.assertRaisesRegex(ValueError, "input"):
            load_context_metadata(self._write(payload))


if __name__ == "__main__":
    unittest.main()
