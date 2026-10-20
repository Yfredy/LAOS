"""CAM++ 前缀/后缀 probe：真实 FP32 中间张量捕获、切点冻结与故障区间二分。

设计口径（2026-10-20 故障基线绑定）：

- 后缀 probe 的校准输入只能是 FP32 ONNX Runtime 从同一 40 条真实语音
  捕获的中间张量；`source_kind` 必须是 `fp32_real_audio`，随机张量、
  手工构造张量一律拒绝；
- 每个 cut 记录原节点区间、输入/输出 tensor 名、calibration 来源、ONNX
  图 SHA-256 与编译配置，避免"切点改变了图优化，却把通过当成原图根因"；
- 切点必须是静态形状、单一可表示输入、且该张量确实是节点输出；后缀
  需要的跨区张量必须只包含 cut 张量，否则该切点不是有效边界；
- 每个 probe 的 context 仍走 `build_w8a16_context` 的 socModel/dspArch/
  graph 门禁；真机结果只认 `DeviceRunResult`，设备不在线时显式
  `device_unavailable`，绝不伪造或拿 host 模拟器冒充；
- 语义改写（前缀/后缀拼回）必须先过 40 条 FP32 parity：`max_abs == 0`，
  或在浮点算子不可逐元素一致时 paired cosine median `>= 0.999999`、
  minimum `>= 0.99999`。

    python -m scripts.speaker_qnn.probe stages --variant <variant-id> [--serial <serial>]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Sequence

from .build import (
    BUILD_CONFIG_WARNING,
    BUILD_READY,
    BuildArtifact,
    BuildVariant,
    ToolchainSpec,
    build_w8a16_context,
    discover_toolchains,
)
from .contracts import (
    CAMPLUS_INPUT_SHAPE,
    CAMPLUS_OUTPUT_SHAPE,
    SCHEMA_VERSION,
    ContextMetadata,
    DeviceRunResult,
    write_json_atomic,
)
from .device import parse_input_list, run_context

if TYPE_CHECKING:  # 主库 discover 环境没有 numpy/onnx；运行时按需导入
    import numpy as np
    import onnx

REPO = Path(__file__).resolve().parents[2]
DEBUG_ROOT = REPO / "var/speaker-benchmark/qnn/campplus-htp-debug"
DEFAULT_MODEL = REPO / "var/speaker-benchmark/qnn/campplus-w8a16-v2/campplus-3s-fp32-static-stats.onnx"
DEFAULT_CALIBRATION = REPO / "var/speaker-benchmark/qnn/campplus-w8a16/input_list.txt"
REFERENCE_VARIANT = "2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats"

SOURCE_KIND_REAL_AUDIO = "fp32_real_audio"
FLOAT_DTYPES = frozenset({"float32", "float16"})
PARITY_MEDIAN_MIN = 0.999999
PARITY_MINIMUM_MIN = 0.99999
FAILING_STATUSES = frozenset({"timeout", "ssr", "load_error", "execute_error"})
PROBE_GRAPH_NAME = "campplus_probe"

# 阶段边界按真实 ONNX 节点名解析（不是猜结构）：head → block1 → block2 →
# block3/transit → out nonlinear → stats concat → final dense。
STAGE_BOUNDARIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("head", ("/head/",)),
    ("block1", ("/xvector/block1/",)),
    ("block2", ("/xvector/block2/",)),
    ("block3-transit", ("/xvector/block3/", "/xvector/transit")),
    ("out-nonlinear", ("/xvector/out_nonlinear/",)),
    ("stats", ("/xvector/stats/",)),
    ("dense", ("/xvector/dense/",)),
)

_DTYPE_BY_ENUM = {1: "float32", 10: "float16"}
_ENUM_BY_DTYPE = {value: key for key, value in _DTYPE_BY_ENUM.items()}
_SAFE_ID_RE = re.compile(r"[^0-9A-Za-z]+")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - 由 benchmark venv 提供
        raise RuntimeError(
            "probe 需要 numpy：请用 var/speaker-benchmark/.venv 运行"
        ) from exc
    return np


def _require_onnx():
    try:
        import onnx
    except ImportError as exc:  # pragma: no cover - 由 benchmark venv 提供
        raise RuntimeError(
            "probe 需要 onnx：请用 var/speaker-benchmark/.venv 运行"
        ) from exc
    return onnx


def _slug(value: str, limit: int = 32) -> str:
    safe = _SAFE_ID_RE.sub("_", value).strip("_")
    return (safe or "tensor")[:limit]


def _probe_id(kind: str, cut: "TensorCut") -> str:
    return f"{kind}-{cut.node_index:04d}-{_slug(cut.tensor_name)}"


@dataclass(frozen=True)
class TensorCut:
    """一个 probe 切点：节点索引 + 该节点产出的中间张量。

    `shape` 必须是完全静态的正维度；动态维度或空 shape 不能作为 QNN
    probe 的输入/输出。
    """

    node_index: int
    tensor_name: str
    shape: tuple[int, ...]
    dtype: str

    def __post_init__(self) -> None:
        if self.node_index < 0:
            raise ValueError(f"node_index 不能为负：{self.node_index}")
        if not self.tensor_name:
            raise ValueError("tensor_name 不能为空")
        if not self.shape or any(int(dim) <= 0 for dim in self.shape):
            raise ValueError(
                f"cut tensor 必须是完全静态的正 shape：{self.tensor_name} {self.shape}"
            )
        if self.dtype not in FLOAT_DTYPES:
            raise ValueError(
                f"cut tensor dtype 必须是浮点（{sorted(FLOAT_DTYPES)}）："
                f"{self.tensor_name} {self.dtype}"
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["shape"] = list(self.shape)
        return payload


@dataclass(frozen=True)
class ProbeSpec:
    """一个前缀/后缀 probe 的节点区间与输入输出张量。"""

    probe_id: str
    kind: Literal["prefix", "suffix"]
    first_node: int
    last_node: int
    input_tensors: tuple[str, ...]
    output_tensors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_tensors"] = list(self.input_tensors)
        payload["output_tensors"] = list(self.output_tensors)
        return payload


@dataclass(frozen=True)
class IntermediateEntry:
    """一条真实语音在 cut 张量上的捕获记录。"""

    input_path: str
    input_sha256: str
    raw_path: str
    sha256: str
    shape: tuple[int, ...]
    dtype: str


@dataclass(frozen=True)
class IntermediateManifest:
    """一个 cut 的 FP32 真实中间张量清单。"""

    path: Path
    source_kind: str
    tensor_name: str
    node_index: int
    shape: tuple[int, ...]
    dtype: str
    model_sha256: str
    input_list_sha256: str
    entries: tuple[IntermediateEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_kind": self.source_kind,
            "tensor_name": self.tensor_name,
            "node_index": self.node_index,
            "shape": list(self.shape),
            "dtype": self.dtype,
            "model_sha256": self.model_sha256,
            "input_list_sha256": self.input_list_sha256,
            "entries": [
                {
                    "input_path": entry.input_path,
                    "input_sha256": entry.input_sha256,
                    "raw_path": entry.raw_path,
                    "sha256": entry.sha256,
                    "shape": list(entry.shape),
                    "dtype": entry.dtype,
                }
                for entry in self.entries
            ],
        }

    def calibration_sources(self) -> tuple[tuple[str, str], ...]:
        """(raw 路径, tensor sha256)；后缀输入列表的唯一来源。"""
        return tuple((entry.raw_path, entry.sha256) for entry in self.entries)


def load_manifest(path: Path) -> IntermediateManifest:
    """读取 cut 中间张量清单（不做文件级 SHA 校验，校验在 extract_suffix）。"""
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取中间张量 manifest：{path}: {exc}") from exc
    try:
        entries = tuple(
            IntermediateEntry(
                input_path=str(row["input_path"]),
                input_sha256=str(row["input_sha256"]),
                raw_path=str(row["raw_path"]),
                sha256=str(row["sha256"]),
                shape=tuple(int(dim) for dim in row["shape"]),
                dtype=str(row["dtype"]),
            )
            for row in payload.get("entries") or ()
        )
        return IntermediateManifest(
            path=path,
            source_kind=str(payload["source_kind"]),
            tensor_name=str(payload["tensor_name"]),
            node_index=int(payload["node_index"]),
            shape=tuple(int(dim) for dim in payload["shape"]),
            dtype=str(payload["dtype"]),
            model_sha256=str(payload["model_sha256"]),
            input_list_sha256=str(payload.get("input_list_sha256") or ""),
            entries=entries,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"中间张量 manifest 字段不完整：{path}: {exc}") from exc


def _load_model(model: Path) -> "onnx.ModelProto":
    onnx = _require_onnx()
    model = Path(model)
    if not model.is_file():
        raise FileNotFoundError(f"ONNX 模型不存在：{model}")
    return onnx.load(str(model))


def _tensor_value_info(name: str, shape: Sequence[int], dtype: str):
    onnx = _require_onnx()
    return onnx.helper.make_tensor_value_info(
        name, _ENUM_BY_DTYPE[dtype], [int(dim) for dim in shape]
    )


def _node_stage_indices(model: "onnx.ModelProto") -> tuple[tuple[str, int], ...]:
    """按真实节点名解析每个阶段最后一个节点索引。"""
    indices: list[tuple[str, int]] = []
    nodes = list(model.graph.node)
    for stage, prefixes in STAGE_BOUNDARIES:
        matched = [
            index
            for index, node in enumerate(nodes)
            if any(node.name.startswith(prefix) for prefix in prefixes)
        ]
        if not matched:
            raise ValueError(f"ONNX 图里找不到阶段 {stage} 的节点（前缀 {prefixes}）")
        indices.append((stage, matched[-1]))
    values = [index for _, index in indices]
    if any(later <= earlier for earlier, later in zip(values, values[1:])):
        raise ValueError(f"阶段边界必须先严格递增：{indices}")
    return tuple(indices)


def _instrumented_model(
    model: "onnx.ModelProto", tensor_names: Sequence[str]
) -> "onnx.ModelProto":
    """把中间张量追加为 graph output，让 ORT 保留这些值。

    ONNX Runtime 默认只保留 graph output，直接按名字取中间张量会报
    `Invalid output name`；追加输出不改变任何计算。类型/shape 由 ORT
    从图推断（空 ValueInfo），避免写死动态占位维度。
    """
    onnx = _require_onnx()
    graph = copy.deepcopy(model.graph)
    existing = {output.name for output in graph.output}
    for name in tensor_names:
        if name not in existing:
            graph.output.append(onnx.helper.make_empty_tensor_value_info(name))
    return onnx.helper.make_model(
        graph,
        opset_imports=copy.deepcopy(model.opset_import),
        producer_name="laos-speaker-qnn-probe",
        ir_version=model.ir_version,
    )


def _input_array(raw_path: Path, expected: tuple[int, ...]) -> "np.ndarray":
    np = _require_numpy()
    data = np.fromfile(Path(raw_path), dtype="<f4")
    count = math.prod(expected)
    if data.size != count:
        raise ValueError(
            f"输入 {raw_path} 元素数不匹配：{data.size} != {count}（shape {expected}）"
        )
    if not np.all(np.isfinite(data)):
        raise ValueError(f"输入 {raw_path} 含非有限值")
    return data.reshape(expected)


def _model_input_spec(model: "onnx.ModelProto") -> tuple[str, tuple[int, ...]]:
    inputs = list(model.graph.input)
    if len(inputs) != 1:
        raise ValueError(f"probe 只支持单输入 ONNX，实际 {len(inputs)} 个")
    dims = inputs[0].type.tensor_type.shape.dim
    shape: list[int] = []
    for dim in dims:
        if not dim.HasField("dim_value") or int(dim.dim_value) <= 0:
            raise ValueError(f"模型输入必须是完全静态 shape：{inputs[0].name}")
        shape.append(int(dim.dim_value))
    return inputs[0].name, tuple(shape)


def discover_stage_cuts(model: Path, sample_input: Path) -> tuple[TensorCut, ...]:
    """冻结 7 个阶段边界 cut（真实节点名/索引/实测 shape）。

    shape 来自 FP32 ONNX Runtime 对一条真实输入的实测；capture 时会再
    对所有 40 条输入逐一校验 shape 一致，动态维度不会漏过。
    """
    np = _require_numpy()
    ort = _import_onnxruntime()
    model_proto = _load_model(model)
    boundaries = _node_stage_indices(model_proto)
    names = [model_proto.graph.node[index].output[0] for _, index in boundaries]
    input_name, input_shape = _model_input_spec(model_proto)
    array = _input_array(sample_input, input_shape)
    session = ort.InferenceSession(
        _instrumented_model(model_proto, names).SerializeToString(),
        _session_options(),
        providers=["CPUExecutionProvider"],
    )
    values = session.run(names, {input_name: array})
    cuts: list[TensorCut] = []
    for (stage, index), name, value in zip(boundaries, names, values):
        shape = tuple(int(dim) for dim in value.shape)
        dtype = str(value.dtype)
        if any(dim <= 0 for dim in shape) or dtype not in FLOAT_DTYPES:
            raise ValueError(f"阶段 {stage} 的 cut 张量不可用：{name} {shape} {dtype}")
        if not np.all(np.isfinite(value)):
            raise ValueError(f"阶段 {stage} 的 cut 张量含非有限值：{name}")
        cuts.append(TensorCut(index, name, shape, dtype))
    return tuple(cuts)


def _session_options():
    ort = _import_onnxruntime()
    options = ort.SessionOptions()
    # 关闭图优化：probe 只验证"同一计算图被切开后语义不变"，不能引入
    # 新的算子融合把差异掩盖掉。
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.intra_op_num_threads = 1
    return options


def _import_onnxruntime():
    try:
        import onnxruntime as ort
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "probe 需要 onnxruntime：请用 var/speaker-benchmark/.venv 运行"
        ) from exc
    return ort


def capture_intermediates(
    model: Path,
    cuts: Sequence[TensorCut],
    input_list: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """用 FP32 ONNX Runtime 捕获每个 cut 在 40 条真实语音上的中间张量。

    返回 `{tensor_name: manifest_path}`；每条记录含源输入 SHA-256、张量
    SHA-256、shape 与 dtype。张量出现非有限值即拒绝，避免 NaN 进入后缀
    校准把故障掩盖成"数据问题"。
    """
    np = _require_numpy()
    ort = _import_onnxruntime()
    if not cuts:
        raise ValueError("capture_intermediates 需要至少一个 cut")
    tensor_names = [cut.tensor_name for cut in cuts]
    if len(set(tensor_names)) != len(tensor_names):
        raise ValueError("cut tensor 名重复")
    model = Path(model)
    model_proto = _load_model(model)
    nodes = list(model_proto.graph.node)
    for cut in cuts:
        _check_cut_node(model_proto, cut)
    entries = parse_input_list(Path(input_list))
    if not entries:
        raise ValueError("input list 为空")
    input_name, input_shape = _model_input_spec(model_proto)
    session = ort.InferenceSession(
        _instrumented_model(model_proto, tensor_names).SerializeToString(),
        _session_options(),
        providers=["CPUExecutionProvider"],
    )
    model_sha = _sha256(model)
    input_list_sha = _sha256(Path(input_list))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: dict[str, list[IntermediateEntry]] = {cut.tensor_name: [] for cut in cuts}
    for entry_index, (_, raw_path) in enumerate(entries):
        array = _input_array(raw_path, input_shape)
        values = session.run(tensor_names, {input_name: array})
        for cut, value in zip(cuts, values):
            shape = tuple(int(dim) for dim in value.shape)
            dtype = str(value.dtype)
            if shape != cut.shape or dtype != cut.dtype:
                raise ValueError(
                    f"cut {cut.tensor_name} 实测 {shape} {dtype}，"
                    f"与冻结值 {cut.shape} {cut.dtype} 不一致（动态或形状漂移）"
                )
            if not np.all(np.isfinite(value)):
                raise ValueError(
                    f"cut {cut.tensor_name} 在输入 {raw_path} 上出现非有限值"
                )
            tensor_dir = output_dir / _slug(f"{cut.node_index:04d}-{cut.tensor_name}")
            tensor_dir.mkdir(parents=True, exist_ok=True)
            raw_path_out = tensor_dir / f"{entry_index:03d}-{Path(raw_path).stem}.raw"
            np.asarray(value, dtype="<f4").tofile(raw_path_out)
            records[cut.tensor_name].append(
                IntermediateEntry(
                    input_path=str(Path(raw_path)),
                    input_sha256=_sha256(Path(raw_path)),
                    raw_path=str(raw_path_out),
                    sha256=_sha256(raw_path_out),
                    shape=shape,
                    dtype=dtype,
                )
            )

    manifests: dict[str, Path] = {}
    for cut in cuts:
        manifest = IntermediateManifest(
            path=output_dir / _slug(f"{cut.node_index:04d}-{cut.tensor_name}") / "manifest.json",
            source_kind=SOURCE_KIND_REAL_AUDIO,
            tensor_name=cut.tensor_name,
            node_index=cut.node_index,
            shape=cut.shape,
            dtype=cut.dtype,
            model_sha256=model_sha,
            input_list_sha256=input_list_sha,
            entries=tuple(records[cut.tensor_name]),
        )
        write_json_atomic(manifest.path, manifest.to_dict())
        manifests[cut.tensor_name] = manifest.path
    return manifests


def _check_cut_node(model: "onnx.ModelProto", cut: TensorCut) -> None:
    nodes = list(model.graph.node)
    if cut.node_index >= len(nodes):
        raise ValueError(f"cut node_index 越界：{cut.node_index} >= {len(nodes)}")
    node = nodes[cut.node_index]
    if cut.tensor_name not in node.output:
        raise ValueError(
            f"cut 张量 {cut.tensor_name} 不是节点 {cut.node_index}（{node.name}）的输出"
        )
    if not cut.tensor_name:
        raise ValueError("cut 张量名为空")


def _used_initializers(model: "onnx.ModelProto", nodes: Sequence[Any]) -> list[Any]:
    used = {name for node in nodes for name in node.input if name}
    return [
        copy.deepcopy(initializer)
        for initializer in model.graph.initializer
        if initializer.name in used
    ]


def _build_subgraph(
    model: "onnx.ModelProto",
    nodes: Sequence[Any],
    inputs: Sequence[Any],
    outputs: Sequence[Any],
    name: str,
):
    onnx = _require_onnx()
    graph = onnx.helper.make_graph(
        list(nodes),
        name,
        list(inputs),
        list(outputs),
        initializer=_used_initializers(model, nodes),
    )
    return onnx.helper.make_model(
        graph,
        opset_imports=copy.deepcopy(model.opset_import),
        producer_name="laos-speaker-qnn-probe",
        ir_version=model.ir_version,
    )


def _external_inputs(
    model: "onnx.ModelProto", nodes: Sequence[Any], allowed: set[str]
) -> tuple[str, ...]:
    produced = {name for node in nodes for name in node.output if name}
    initializers = {initializer.name for initializer in model.graph.initializer}
    external: list[str] = []
    for node in nodes:
        for name in node.input:
            if not name or name in produced or name in initializers:
                continue
            if name not in allowed and name not in external:
                external.append(name)
    return tuple(external)


def _output_path(path: Path, default_name: str) -> Path:
    path = Path(path)
    if path.suffix.lower() == ".onnx":
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    path.mkdir(parents=True, exist_ok=True)
    return path / default_name


def extract_prefix(model: Path, cut: TensorCut, output: Path) -> ProbeSpec:
    """节点 `0..cut.node_index` 的子图，输出唯一 cut 张量。"""
    onnx = _require_onnx()
    model = Path(model)
    model_proto = _load_model(model)
    _check_cut_node(model_proto, cut)
    nodes = list(model_proto.graph.node)[: cut.node_index + 1]
    allowed = {value.name for value in model_proto.graph.input}
    external = _external_inputs(model_proto, nodes, allowed)
    if external:
        raise ValueError(f"前缀子图缺少输入张量：{external}")
    graph = _build_subgraph(
        model_proto,
        nodes,
        copy.deepcopy(list(model_proto.graph.input)),
        [_tensor_value_info(cut.tensor_name, cut.shape, cut.dtype)],
        name=f"campplus_prefix_{cut.node_index:04d}",
    )
    _save_model(graph, _output_path(output, "prefix.onnx"))
    return ProbeSpec(
        probe_id=_probe_id("prefix", cut),
        kind="prefix",
        first_node=0,
        last_node=cut.node_index,
        input_tensors=tuple(value.name for value in model_proto.graph.input),
        output_tensors=(cut.tensor_name,),
    )


def _verify_manifest(cut: TensorCut, manifest: IntermediateManifest, model: Path) -> None:
    if manifest.source_kind != SOURCE_KIND_REAL_AUDIO:
        raise ValueError(
            f"后缀校准必须来自 {SOURCE_KIND_REAL_AUDIO}，实际 {manifest.source_kind!r}"
        )
    if manifest.tensor_name != cut.tensor_name:
        raise ValueError(
            f"manifest 张量 {manifest.tensor_name} 与 cut {cut.tensor_name} 不一致"
        )
    if manifest.node_index != cut.node_index:
        raise ValueError(
            f"manifest 节点 {manifest.node_index} 与 cut {cut.node_index} 不一致"
        )
    if manifest.shape != cut.shape or manifest.dtype != cut.dtype:
        raise ValueError(
            f"manifest shape/dtype {manifest.shape}/{manifest.dtype} "
            f"与 cut {cut.shape}/{cut.dtype} 不一致"
        )
    if manifest.model_sha256 != _sha256(Path(model)):
        raise ValueError(
            "中间张量 manifest 的模型 SHA-256 与当前模型不一致："
            f"{manifest.model_sha256} != {_sha256(Path(model))}"
        )
    if not manifest.entries:
        raise ValueError("中间张量 manifest 没有任何校准条目")
    np = _require_numpy()
    for entry in manifest.entries:
        raw = Path(entry.raw_path)
        if not raw.is_file():
            raise ValueError(f"中间张量文件不存在：{raw}")
        if _sha256(raw) != entry.sha256:
            raise ValueError(
                f"中间张量 SHA-256 不匹配：{raw} "
                f"期望 {entry.sha256} 实际 {_sha256(raw)}"
            )
        if entry.shape != cut.shape or entry.dtype != cut.dtype:
            raise ValueError(f"中间张量条目 shape/dtype 与 cut 不一致：{raw}")
        data = np.fromfile(raw, dtype="<f4")
        if data.size != math.prod(cut.shape):
            raise ValueError(f"中间张量元素数不匹配：{raw}")
        if not np.all(np.isfinite(data)):
            raise ValueError(f"中间张量含非有限值（NaN/Inf）：{raw}")


def extract_suffix(
    model: Path,
    cut: TensorCut,
    intermediate_manifest: Path,
    output: Path,
) -> ProbeSpec:
    """节点 `cut.node_index+1..end` 的子图，输入唯一 cut 张量，输出原 embedding。"""
    onnx = _require_onnx()
    model = Path(model)
    model_proto = _load_model(model)
    _check_cut_node(model_proto, cut)
    manifest = load_manifest(Path(intermediate_manifest))
    _verify_manifest(cut, manifest, model)
    nodes = list(model_proto.graph.node)[cut.node_index + 1 :]
    if not nodes:
        raise ValueError(
            f"cut {cut.tensor_name} 是最后一个节点，没有后缀子图；"
            "该 cut 只作为完整图前缀使用"
        )
    external = _external_inputs(model_proto, nodes, {cut.tensor_name})
    if external:
        raise ValueError(
            f"cut {cut.tensor_name} 不是有效边界：后缀还需要跨区张量 {external}"
        )
    if cut.tensor_name not in {name for node in nodes for name in node.input}:
        raise ValueError(f"后缀子图没有消费 cut 张量 {cut.tensor_name}")
    graph = _build_subgraph(
        model_proto,
        nodes,
        [_tensor_value_info(cut.tensor_name, cut.shape, cut.dtype)],
        copy.deepcopy(list(model_proto.graph.output)),
        name=f"campplus_suffix_{cut.node_index:04d}",
    )
    _save_model(graph, _output_path(output, "suffix.onnx"))
    return ProbeSpec(
        probe_id=_probe_id("suffix", cut),
        kind="suffix",
        first_node=cut.node_index + 1,
        last_node=len(model_proto.graph.node) - 1,
        input_tensors=(cut.tensor_name,),
        output_tensors=tuple(value.name for value in model_proto.graph.output),
    )


def _save_model(model: "onnx.ModelProto", path: Path) -> None:
    onnx = _require_onnx()
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


def write_suffix_calibration(
    manifest: IntermediateManifest, output: Path
) -> Path:
    """后缀 W8A16 校准列表：`<cut tensor>:=<真实捕获的 raw>`。"""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{manifest.tensor_name}:={entry.raw_path}" for entry in manifest.entries]
    if not lines:
        raise ValueError("manifest 没有条目，无法写校准列表")
    output.write_text("\n".join(lines) + "\n", encoding="ascii")
    return output


def parity_gate(reference: "np.ndarray", candidate: "np.ndarray") -> dict[str, Any]:
    """40 条输入的 FP32 parity 门禁。

    首选逐元素一致（`max_abs == 0`）；只有在浮点算子无法逐元素一致时
    才退到 paired cosine：median `>= 0.999999`、minimum `>= 0.99999`。
    """
    np = _require_numpy()
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)
    if reference.shape != candidate.shape:
        return {
            "passed": False,
            "reason": f"形状不一致：{reference.shape} != {candidate.shape}",
            "max_abs": None,
            "cosine_median": None,
            "cosine_minimum": None,
        }
    if reference.ndim == 1:
        reference = reference.reshape(1, -1)
        candidate = candidate.reshape(1, -1)
    if reference.ndim != 2 or reference.shape[0] == 0:
        return {
            "passed": False,
            "reason": f"parity 需要 (N, D) 数组：{reference.shape}",
            "max_abs": None,
            "cosine_median": None,
            "cosine_minimum": None,
        }
    if not (np.all(np.isfinite(reference)) and np.all(np.isfinite(candidate))):
        return {
            "passed": False,
            "reason": "parity 输入含非有限值",
            "max_abs": None,
            "cosine_median": None,
            "cosine_minimum": None,
        }
    max_abs = float(np.max(np.abs(reference - candidate)))
    if max_abs == 0.0:
        return {
            "passed": True,
            "mode": "exact",
            "reason": "max_abs == 0，逐元素一致",
            "max_abs": max_abs,
            "cosine_median": 1.0,
            "cosine_minimum": 1.0,
        }
    norms = np.linalg.norm(reference, axis=1) * np.linalg.norm(candidate, axis=1)
    numerator = np.sum(reference * candidate, axis=1)
    cosines = np.divide(
        numerator, norms, out=np.zeros_like(numerator, dtype=np.float64), where=norms > 0
    )
    median = float(np.median(cosines))
    minimum = float(np.min(cosines))
    passed = median >= PARITY_MEDIAN_MIN and minimum >= PARITY_MINIMUM_MIN
    return {
        "passed": passed,
        "mode": "cosine",
        "reason": (
            f"cosine median={median:.9f} minimum={minimum:.9f}；"
            f"要求 median>={PARITY_MEDIAN_MIN} minimum>={PARITY_MINIMUM_MIN}"
        ),
        "max_abs": max_abs,
        "cosine_median": median,
        "cosine_minimum": minimum,
    }


def verify_probe_parity(
    model: Path,
    prefix_model: Path,
    suffix_model: Path,
    cut: TensorCut,
    input_list: Path,
) -> dict[str, Any]:
    """证明 `suffix(prefix(x))` 与完整 FP32 embedding 在 40 条输入上一致。

    前缀/后缀各自是独立 ONNX 会话（关闭图优化），拼接输出与完整图
    逐条比较；任何一条出现 NaN 或形状漂移都直接判失败。
    """
    np = _require_numpy()
    ort = _import_onnxruntime()
    model_proto = _load_model(model)
    input_name, input_shape = _model_input_spec(model_proto)
    output_name = model_proto.graph.output[0].name
    entries = parse_input_list(Path(input_list))
    if not entries:
        raise ValueError("parity 的 input list 为空")
    full_session = ort.InferenceSession(
        model_proto.SerializeToString(), _session_options(),
        providers=["CPUExecutionProvider"],
    )
    prefix_session = ort.InferenceSession(
        Path(prefix_model).read_bytes(), _session_options(),
        providers=["CPUExecutionProvider"],
    )
    suffix_proto = _load_model(suffix_model)
    suffix_input = suffix_proto.graph.input[0].name
    suffix_session = ort.InferenceSession(
        suffix_proto.SerializeToString(), _session_options(),
        providers=["CPUExecutionProvider"],
    )
    full: list["np.ndarray"] = []
    stitched: list["np.ndarray"] = []
    intermediates: list["np.ndarray"] = []
    for _, raw_path in entries:
        array = _input_array(raw_path, input_shape)
        full.append(
            np.asarray(full_session.run([output_name], {input_name: array})[0])
        )
        cut_value = np.asarray(prefix_session.run([cut.tensor_name], {input_name: array})[0])
        if tuple(cut_value.shape) != cut.shape:
            return {
                "passed": False,
                "reason": (
                    f"前缀输出 shape {tuple(cut_value.shape)} 与 cut {cut.shape} 不一致"
                ),
                "inputs": len(full),
            }
        if not np.all(np.isfinite(cut_value)):
            return {
                "passed": False,
                "reason": "前缀输出含非有限值",
                "inputs": len(full),
            }
        intermediates.append(cut_value)
        stitched.append(
            np.asarray(suffix_session.run([output_name], {suffix_input: cut_value})[0])
        )
    reference = np.stack([value.reshape(-1) for value in full], axis=0)
    candidate = np.stack([value.reshape(-1) for value in stitched], axis=0)
    gate = parity_gate(reference, candidate)
    gate["inputs"] = len(full)
    gate["cut_shape"] = list(intermediates[0].shape)
    return gate


def bisect_failure_interval(
    results: tuple[tuple[ProbeSpec, DeviceRunResult], ...],
) -> tuple[int, int]:
    """取最小 `[最后通过的节点, 首个失败的节点]` 区间。

    只看 prefix 证据；`tool_error` 是工具故障，不能当成模型失败，直接
    拒绝。全部通过说明故障在完整图调度（`full_graph_scheduling`），
    没有可二分区间。
    """
    prefixes = [item for item in results if item[0].kind == "prefix"]
    if not prefixes:
        raise ValueError("二分需要至少一个 prefix probe 结果")
    passing = [spec for spec, result in prefixes if result.status == "pass"]
    failing = [spec for spec, result in prefixes if result.status in FAILING_STATUSES]
    tool_errors = [spec for spec, result in prefixes if result.status == "tool_error"]
    if tool_errors:
        raise ValueError(
            "probe 运行出现 tool_error，不能当成模型失败："
            + ", ".join(spec.probe_id for spec in tool_errors)
        )
    unknown = [
        spec for spec, result in prefixes
        if result.status not in FAILING_STATUSES and result.status != "pass"
    ]
    if unknown:
        raise ValueError(
            "存在不可分类的 probe 状态：" + ", ".join(spec.probe_id for spec in unknown)
        )
    if not failing:
        raise ValueError(
            "所有 prefix 都通过：故障只在完整图调度，应归类 full_graph_scheduling"
        )
    first_failing = min(failing, key=lambda spec: spec.last_node)
    last_passing_node = (
        max(spec.last_node for spec in passing) if passing else 0
    )
    if first_failing.last_node < last_passing_node:
        raise ValueError(
            "probe 结果自相矛盾：失败节点早于通过节点 "
            f"({first_failing.last_node} < {last_passing_node})"
        )
    return last_passing_node, first_failing.last_node


def _load_variant_artifact(variant_id: str, output_root: Path) -> BuildArtifact:
    path = Path(output_root) / "builds" / variant_id / "artifact.json"
    if not path.is_file():
        raise FileNotFoundError(f"变体 artifact 不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = payload.get("metadata")
    metadata = (
        ContextMetadata(
            build_id=str(row["build_id"]),
            soc_model=int(row["soc_model"]),
            dsp_arch=int(row["dsp_arch"]),
            graph_name=str(row["graph_name"]),
            input_shape=tuple(int(value) for value in row["input_shape"]),
            output_shape=tuple(int(value) for value in row["output_shape"]),
        )
        if row
        else None
    )
    return BuildArtifact(
        variant_id=str(payload["variant_id"]),
        status=str(payload["status"]),
        context_path=payload.get("context_path"),
        metadata=metadata,
        sha256=dict(payload.get("sha256") or {}),
        commands=tuple(payload.get("commands") or ()),
        error=payload.get("error"),
        warning=payload.get("warning"),
    )


def _resolve_toolchain(artifact: BuildArtifact) -> ToolchainSpec:
    if artifact.metadata is None:
        raise ValueError(f"变体 {artifact.variant_id} 没有 context 元数据")
    roots = discover_toolchains()
    if not roots:
        raise FileNotFoundError("本机没有可用的同 build QAIRT 树")
    for spec in roots:
        if spec.build_id == artifact.metadata.build_id:
            return spec
    raise ValueError(
        f"变体 {artifact.variant_id} 的 QAIRT build {artifact.metadata.build_id} "
        "不在本地候选树里"
    )


def _device_available(serial: str | None) -> bool:
    if not serial:
        return False
    try:
        completed = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == serial and parts[1] == "device":
            return True
    return False


def _probe_record(
    spec: ProbeSpec,
    cut: TensorCut,
    model: Path,
    probe_dir: Path,
    *,
    parity: dict[str, Any],
    calibration_source: str,
    calibration_sha256: str,
) -> dict[str, Any]:
    onnx_path = probe_dir / "onnx" / f"{spec.kind}.onnx"
    return {
        "probe_id": spec.probe_id,
        "kind": spec.kind,
        "node_interval": [spec.first_node, spec.last_node],
        "input_tensors": list(spec.input_tensors),
        "output_tensors": list(spec.output_tensors),
        "tensor": cut.to_dict(),
        "calibration_source": calibration_source,
        "calibration_sha256": calibration_sha256,
        "source_model": {"path": str(model), "sha256": _sha256(Path(model))},
        "graph": {
            "path": str(onnx_path),
            "sha256": _sha256(onnx_path) if onnx_path.is_file() else None,
        },
        "parity": parity,
    }


def _qnn_input_shape(shape: tuple[int, ...]) -> tuple[int, ...]:
    """QNN converter 对 rank-3 输入折叠一次 Transpose（语义 → 物理布局）。

    完整图 `[1,298,80]` → context `[1,80,298]` 是同一规则；后缀的
    rank-3 cut 张量必须按该物理布局声明，否则元数据门禁会把合法
    context 误判为形状不匹配。rank<=2 保持原样。
    """
    if len(shape) == 3:
        return (shape[0], shape[2], shape[1])
    return tuple(shape)


def _build_probe(
    probe_dir: Path,
    onnx_path: Path,
    calibration_list: Path,
    toolchain: ToolchainSpec,
    cut: TensorCut,
    kind: str,
) -> tuple[BuildArtifact, BuildVariant]:
    graph_name = f"{PROBE_GRAPH_NAME}_{kind}_{cut.node_index:04d}"
    variant = BuildVariant(toolchain, 2, 4, False, graph_name)
    expected_input = (
        tuple(CAMPLUS_INPUT_SHAPE) if kind == "prefix" else _qnn_input_shape(cut.shape)
    )
    expected_output = (
        tuple(cut.shape) if kind == "prefix" else tuple(CAMPLUS_OUTPUT_SHAPE)
    )
    artifact = build_w8a16_context(
        onnx_path,
        calibration_list,
        variant,
        probe_dir,
        expected_input_shape=expected_input,
        expected_output_shape=expected_output,
    )
    return artifact, variant


def run_stages(
    variant_id: str,
    *,
    serial: str | None = None,
    model: Path = DEFAULT_MODEL,
    calibration_list: Path = DEFAULT_CALIBRATION,
    output_root: Path = DEBUG_ROOT,
    build_probes: bool = True,
) -> dict[str, Any]:
    """Step 5：捕获真实中间张量、提取前缀/后缀、parity、编译 probe。

    设备不在线时所有 device 字段写 `device_unavailable`，不构造
    DeviceRunResult，也不写任何"通过/超时"的伪造结论。
    """
    output_root = Path(output_root)
    model = Path(model)
    calibration_list = Path(calibration_list)
    artifact = _load_variant_artifact(variant_id, output_root)
    if artifact.status not in (BUILD_READY, BUILD_CONFIG_WARNING):
        raise ValueError(
            f"参考变体 {variant_id} 状态为 {artifact.status}，不能用于 probe"
        )
    toolchain = _resolve_toolchain(artifact)
    entries = parse_input_list(calibration_list)
    if not entries:
        raise ValueError("校准列表为空")
    cuts = discover_stage_cuts(model, entries[0][1])
    intermediates_root = output_root / "intermediates"
    probes_root = output_root / "probes"
    manifests = capture_intermediates(model, cuts, calibration_list, intermediates_root)

    prefixes: list[tuple[ProbeSpec, dict[str, Any]]] = []
    suffixes: list[tuple[ProbeSpec, dict[str, Any]]] = []
    probe_lists: dict[str, Path] = {}
    probe_artifacts: dict[str, BuildArtifact] = {}
    for cut in cuts:
        prefix_dir = probes_root / _probe_id("prefix", cut)
        prefix_onnx = prefix_dir / "onnx" / "prefix.onnx"
        prefix_spec = extract_prefix(model, cut, prefix_onnx)
        prefix_list = prefix_dir / "input_list.txt"
        shutil.copyfile(calibration_list, prefix_list)
        probe_lists[prefix_spec.probe_id] = prefix_list

        manifest_path = manifests[cut.tensor_name]
        suffix_dir = probes_root / _probe_id("suffix", cut)
        suffix_onnx = suffix_dir / "onnx" / "suffix.onnx"
        suffix_parity: dict[str, Any] | None
        try:
            suffix_spec = extract_suffix(model, cut, manifest_path, suffix_onnx)
        except ValueError as exc:
            if "没有后缀子图" not in str(exc):
                raise
            suffix_spec = ProbeSpec(
                probe_id=_probe_id("suffix", cut),
                kind="suffix",
                first_node=cut.node_index + 1,
                last_node=cut.node_index,
                input_tensors=(cut.tensor_name,),
                output_tensors=(),
            )
            suffix_parity = None
        else:
            suffix_manifest = load_manifest(manifest_path)
            suffix_list = write_suffix_calibration(
                suffix_manifest, suffix_dir / "input_list.txt"
            )
            probe_lists[suffix_spec.probe_id] = suffix_list
            suffix_parity = verify_probe_parity(
                model, prefix_onnx, suffix_onnx, cut, calibration_list
            )
            write_json_atomic(suffix_dir / "parity.json", suffix_parity)

        # 语义改写必须先过 40 条 FP32 parity，才允许进入 QNN 编译。
        parity_passed = suffix_parity is None or bool(suffix_parity.get("passed"))
        prefix_artifact = prefix_variant = None
        if build_probes and parity_passed:
            prefix_artifact, prefix_variant = _build_probe(
                prefix_dir, prefix_onnx, prefix_list, toolchain, cut, "prefix"
            )
            probe_artifacts[prefix_spec.probe_id] = prefix_artifact
        prefix_fields = _build_fields(prefix_artifact, prefix_variant)
        if not parity_passed:
            prefix_fields["build_status"] = "parity_rejected"
        prefixes.append((
            prefix_spec,
            _probe_record(
                prefix_spec,
                cut,
                model,
                prefix_dir,
                parity=suffix_parity,
                calibration_source="real_audio_fbank",
                calibration_sha256=_sha256(calibration_list),
            ) | prefix_fields,
        ))

        if suffix_parity is None:
            suffixes.append((
                suffix_spec,
                {
                    "probe_id": suffix_spec.probe_id,
                    "kind": "suffix",
                    "status": "not_applicable",
                    "reason": (
                        f"cut {cut.tensor_name} 是最后一个节点，没有后缀子图；"
                        "该 cut 只作为完整图前缀使用"
                    ),
                },
            ))
            continue
        suffix_artifact = suffix_variant = None
        if build_probes and parity_passed:
            suffix_artifact, suffix_variant = _build_probe(
                suffix_dir,
                suffix_onnx,
                probe_lists[suffix_spec.probe_id],
                toolchain,
                cut,
                "suffix",
            )
            probe_artifacts[suffix_spec.probe_id] = suffix_artifact
        suffix_fields = _build_fields(suffix_artifact, suffix_variant)
        if not parity_passed:
            suffix_fields["build_status"] = "parity_rejected"
        suffixes.append((
            suffix_spec,
            _probe_record(
                suffix_spec,
                cut,
                model,
                suffix_dir,
                parity=suffix_parity,
                calibration_source=SOURCE_KIND_REAL_AUDIO,
                calibration_sha256=_sha256(manifest_path),
            ) | suffix_fields,
        ))

    device_online = _device_available(serial)
    device_runs: dict[str, dict[str, Any]] = {}
    device_results: list[tuple[ProbeSpec, DeviceRunResult]] = []
    for spec, _ in prefixes + suffixes:
        probe_artifact = probe_artifacts.get(spec.probe_id)
        if probe_artifact is None:
            continue
        if (
            probe_artifact.metadata is None
            or probe_artifact.status not in (BUILD_READY, BUILD_CONFIG_WARNING)
        ):
            device_runs[spec.probe_id] = {
                "status": "device_unavailable",
                "reason": f"probe context 构建状态为 {probe_artifact.status}，不上机",
                "device_run": None,
            }
            continue
        if not device_online:
            device_runs[spec.probe_id] = {
                "status": "device_unavailable",
                "reason": (
                    "未提供 --serial" if not serial else f"adb 设备 {serial} 不在线"
                ),
                "device_run": None,
            }
            continue
        result = run_context(
            serial,
            probes_root / spec.probe_id,
            probe_lists[spec.probe_id],
            probes_root / "device-runs" / spec.probe_id,
            num_inferences=1,
            expected_input_shape=tuple(probe_artifact.metadata.input_shape),
            expected_output_shape=tuple(probe_artifact.metadata.output_shape),
        )
        device_runs[spec.probe_id] = {
            "status": result.status,
            "device_run": result.to_dict(),
            "reason": None,
        }
        device_results.append((spec, result))

    prefix_records = [
        record | {"spec": spec.to_dict(), "device": device_runs.get(spec.probe_id)}
        for spec, record in prefixes
    ]
    suffix_records = [
        record | {"spec": spec.to_dict(), "device": device_runs.get(spec.probe_id)}
        for spec, record in suffixes
    ]
    parity_failures = [
        row["probe_id"]
        for row in suffix_records
        if row.get("parity") and not row["parity"].get("passed")
    ]
    stage_outcome, isolation = _stage_outcome(
        model, prefixes, device_results, device_online, variant_id, parity_failures
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "variant": {
            "variant_id": artifact.variant_id,
            "status": artifact.status,
            "warning": artifact.warning,
            "toolchain": toolchain.build_id,
        },
        "model": {"path": str(model), "sha256": _sha256(model)},
        "calibration": {
            "path": str(calibration_list),
            "sha256": _sha256(calibration_list),
            "entries": len(entries),
            "source_kind": SOURCE_KIND_REAL_AUDIO,
        },
        "device": {
            "serial": serial,
            "available": device_online,
            "status": "available" if device_online else "device_unavailable",
        },
        "cuts": [cut.to_dict() for cut in cuts],
        "prefixes": prefix_records,
        "suffixes": suffix_records,
        "parity_failures": parity_failures,
        "stage_outcome": stage_outcome,
    }
    write_json_atomic(probes_root / "stages.json", payload)
    write_json_atomic(probes_root / "isolation.json", isolation)
    return payload


def _build_fields(
    artifact: BuildArtifact | None, variant: BuildVariant | None
) -> dict[str, Any]:
    return {
        "variant": variant.variant_id if variant else None,
        "build_status": artifact.status if artifact else None,
        "metadata": (
            artifact.metadata.to_dict()
            if artifact is not None and artifact.metadata is not None
            else None
        ),
        "context": artifact.context_path if artifact else None,
        "context_sha256": (
            (artifact.sha256 or {}).get("context") if artifact else None
        ),
        "sha256": dict(artifact.sha256) if artifact else {},
        "build_error": artifact.error if artifact else None,
        "warning": artifact.warning if artifact else None,
    }


def _stage_outcome(
    model: Path,
    prefixes: Sequence[tuple[ProbeSpec, dict[str, Any]]],
    device_results: Sequence[tuple[ProbeSpec, DeviceRunResult]],
    device_online: bool,
    variant_id: str,
    parity_failures: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prefix_devices = [
        (spec, result) for spec, result in device_results if spec.kind == "prefix"
    ]
    suffix_devices = [
        (spec, result) for spec, result in device_results if spec.kind == "suffix"
    ]
    isolation = {
        "schema_version": SCHEMA_VERSION,
        "status": "device_unavailable",
        "reason": "手机不在 adb，无法取得 prefix 的真机通过/超时证据，拒绝伪造区间",
        "interval": None,
        "probes": [
            {
                "probe_id": record["probe_id"],
                "kind": record["kind"],
                "node_interval": record.get("node_interval"),
                "tensor": record.get("tensor"),
                "graph_sha256": (record.get("graph") or {}).get("sha256"),
                "context_sha256": record.get("context_sha256"),
                "device": record.get("device"),
            }
            for _, record in prefixes
        ],
        "pending": [
            "设备恢复后重跑 `python -m scripts.speaker_qnn.probe stages "
            f"--variant {variant_id} --serial <serial>` 取得真机 prefix/suffix 结果",
            "有 prefix 失败证据后按 bisect_failure_interval 在当前失败区间内生成中点 cut",
        ],
        "parity_failures": list(parity_failures),
    }
    if not device_online:
        return (
            {
                "last_passing_prefix": None,
                "first_failing_prefix": None,
                "classification": "device_unavailable",
            },
            isolation,
        )
    if not prefix_devices:
        raise ValueError("设备在线但没有任何 prefix 真机结果")
    try:
        interval = bisect_failure_interval(tuple(prefix_devices))
    except ValueError as exc:
        if "full_graph_scheduling" not in str(exc):
            raise
        isolation.update({
            "status": "no_prefix_failure",
            "reason": str(exc),
            "suffix_statuses": {
                spec.probe_id: result.status for spec, result in suffix_devices
            },
        })
        return (
            {
                "last_passing_prefix": (
                    max((spec.last_node for spec, result in prefix_devices
                         if result.status == "pass"), default=None)
                ),
                "first_failing_prefix": None,
                "classification": "full_graph_scheduling",
            },
            isolation,
        )
    start, end = interval
    nodes = list(_load_model(model).graph.node)
    node_types = sorted({node.op_type for node in nodes[start + 1 : end + 1]})
    isolation.update({
        "status": "bisected",
        "reason": "最小 [最后通过, 首个失败] 区间",
        "interval": [start, end],
        "node_count": max(end - start, 0),
        "operator_families": node_types,
        "suffix_statuses": {
            spec.probe_id: result.status for spec, result in suffix_devices
        },
    })
    return (
        {
            "last_passing_prefix": start,
            "first_failing_prefix": end,
            "classification": "stage_isolated",
        },
        isolation,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    stages = subcommands.add_parser("stages", help="捕获真实中间张量并编译阶段 probe")
    stages.add_argument("--variant", required=True)
    stages.add_argument("--serial")
    stages.add_argument("--model", default=str(DEFAULT_MODEL))
    stages.add_argument("--calibration-list", default=str(DEFAULT_CALIBRATION))
    stages.add_argument("--output-root", default=str(DEBUG_ROOT))
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    payload = run_stages(
        arguments.variant,
        serial=arguments.serial,
        model=Path(arguments.model),
        calibration_list=Path(arguments.calibration_list),
        output_root=Path(arguments.output_root),
    )
    for row in payload["prefixes"]:
        print(
            f"prefix  {row['probe_id']:<40} parity={row.get('parity')} "
            f"build={row.get('build_status')} device={(row.get('device') or {}).get('status')}"
        )
    for row in payload["suffixes"]:
        print(
            f"suffix  {row['probe_id']:<40} "
            f"parity={(row.get('parity') or {}).get('passed')} "
            f"build={row.get('build_status')} device={(row.get('device') or {}).get('status')}"
        )
    print(json.dumps(payload["stage_outcome"], ensure_ascii=False, sort_keys=True))
    return 0 if not payload["parity_failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
