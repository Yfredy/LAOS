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
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping, Sequence

from .build import (
    BUILD_CONFIG_WARNING,
    BUILD_METADATA_REJECTED,
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
# capture/verify 以 `<f4` 读写；float16 cut 会被静默误读，因此只接受 float32。
FLOAT_DTYPES = frozenset({"float32"})
PARITY_MEDIAN_MIN = 0.999999
PARITY_MINIMUM_MIN = 0.99999
PARITY_SCALE_TOL = 1e-5
FAILING_STATUSES = frozenset({"timeout", "ssr", "load_error", "execute_error"})
PROBE_GRAPH_NAME = "campplus_probe"
BISECTION_MAX_NODES = 16
# 单算子族停止允许区间宽度超过 16：门禁只认这个机器码，不认自由文本。
BISECTION_STOP_SINGLE_FAMILY = "single_operator_family"
LAYOUT_SAMPLE_ENTRIES = 3

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
                f"cut tensor dtype 必须是浮点且仅为 float32（capture 按 <f4 读写）："
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


def _verify_input_list(
    manifest: IntermediateManifest, input_list: Path
) -> None:
    """证明 manifest 的每条张量都对应 input list 中同序的真实输入。"""
    input_list = Path(input_list)
    if not input_list.is_file():
        raise ValueError(f"input list 不存在：{input_list}")
    actual = _sha256(input_list)
    if manifest.input_list_sha256 != actual:
        raise ValueError(
            "中间张量 manifest 的 input list SHA-256 不一致："
            f"{manifest.input_list_sha256} != {actual}"
        )
    listed = parse_input_list(input_list)
    if len(listed) != len(manifest.entries):
        raise ValueError(
            f"input list 条目数 {len(listed)} 与中间张量条目数 "
            f"{len(manifest.entries)} 不一致"
        )
    for index, ((_, path), entry) in enumerate(zip(listed, manifest.entries)):
        if Path(path).resolve() != Path(entry.input_path).resolve():
            raise ValueError(
                f"input list 第 {index} 条输入 {path} 与 manifest "
                f"{entry.input_path} 不一致"
            )


def _verify_sample_entries(
    model: Path, cut: TensorCut, manifest: IntermediateManifest
) -> int:
    """抽样重跑 FP32 ORT，逐元素证明 raw 是该输入的真实中间张量。"""
    np = _require_numpy()
    ort = _import_onnxruntime()
    model_proto = _load_model(Path(model))
    input_name, input_shape = _model_input_spec(model_proto)
    session = ort.InferenceSession(
        _instrumented_model(model_proto, [cut.tensor_name]).SerializeToString(),
        _session_options(),
        providers=["CPUExecutionProvider"],
    )
    entries = manifest.entries
    indices = sorted({0, len(entries) // 2, len(entries) - 1})
    checked = 0
    for index in indices:
        entry = entries[index]
        array = _input_array(Path(entry.input_path), input_shape)
        value = session.run([cut.tensor_name], {input_name: array})[0]
        expected = np.fromfile(Path(entry.raw_path), dtype="<f4")
        actual = np.asarray(value, dtype="<f4").reshape(-1)
        if actual.size != expected.size or not np.array_equal(actual, expected):
            raise ValueError(
                f"中间张量不是该输入的真实 FP32 输出（重算不一致）："
                f"{entry.raw_path} 对应 {entry.input_path}"
            )
        checked += 1
    return checked


def _verify_manifest(
    cut: TensorCut,
    manifest: IntermediateManifest,
    model: Path,
    input_list: Path,
) -> None:
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
        if not Path(entry.input_path).is_file():
            raise ValueError(f"源输入不存在：{entry.input_path}")
        if _sha256(Path(entry.input_path)) != entry.input_sha256:
            raise ValueError(
                f"源输入 SHA-256 不匹配：{entry.input_path} "
                f"期望 {entry.input_sha256}"
            )
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
    _verify_input_list(manifest, Path(input_list))
    _verify_sample_entries(model, cut, manifest)


def extract_suffix(
    model: Path,
    cut: TensorCut,
    intermediate_manifest: Path,
    output: Path,
    *,
    input_list: Path,
) -> ProbeSpec:
    """节点 `cut.node_index+1..end` 的子图，输入唯一 cut 张量，输出原 embedding。

    `input_list` 必须显式传入：manifest 与真实输入的同序绑定是校准来源
    证明的一部分，不允许静默跳过。
    """
    onnx = _require_onnx()
    model = Path(model)
    model_proto = _load_model(model)
    _check_cut_node(model_proto, cut)
    manifest = load_manifest(Path(intermediate_manifest))
    _verify_manifest(cut, manifest, model, input_list)
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
    reference_norms = np.linalg.norm(reference, axis=1)
    candidate_norms = np.linalg.norm(candidate, axis=1)
    norms = reference_norms * candidate_norms
    numerator = np.sum(reference * candidate, axis=1)
    cosines = np.divide(
        numerator, norms, out=np.zeros_like(numerator, dtype=np.float64), where=norms > 0
    )
    # cosine 对整体缩放不敏感；整体缩放 1.01 倍必须被拒。
    scale_deviation = np.abs(
        np.divide(
            candidate_norms,
            reference_norms,
            out=np.ones_like(candidate_norms, dtype=np.float64),
            where=reference_norms > 0,
        )
        - 1.0
    )
    scale_max = float(np.max(scale_deviation)) if scale_deviation.size else 0.0
    median = float(np.median(cosines))
    minimum = float(np.min(cosines))
    passed = (
        median >= PARITY_MEDIAN_MIN
        and minimum >= PARITY_MINIMUM_MIN
        and scale_max <= PARITY_SCALE_TOL
    )
    return {
        "passed": passed,
        "mode": "cosine",
        "reason": (
            f"cosine median={median:.9f} minimum={minimum:.9f} "
            f"scale_max_deviation={scale_max:.9g}；"
            f"要求 median>={PARITY_MEDIAN_MIN} minimum>={PARITY_MINIMUM_MIN} "
            f"scale_deviation<={PARITY_SCALE_TOL}"
        ),
        "max_abs": max_abs,
        "cosine_median": median,
        "cosine_minimum": minimum,
        "scale_max_deviation": scale_max,
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


REWRITE_SELECTED = "selected"
REWRITE_BLOCKED = "blocked_on_isolated_interval"
REWRITE_UNSUPPORTED = "unsupported_operator_family"
REWRITE_UNSUPPORTED_KIND = "unsupported_kind"
REWRITE_UNPROVEN = "unproven_isolation"

# 二分停止条件会把剩余区间收敛到单一算子族；只有下列算子族存在定义良好
# 的等价改写。没有隔离区间或算子族未注册时一律拒绝，不在证据不足时猜改写。
REWRITE_BY_FAMILY: dict[str, str] = {
    "Shape": "constant_fold_static_shape",
    "Gather": "constant_fold_static_shape",
    "ReduceMean": "reduction_decomposition",
    "ReduceSum": "reduction_decomposition",
    "Reshape": "layout_normalization",
    "Transpose": "layout_normalization",
}

# 只有真正有 handler 的 kind 才能在 select 阶段返回 `selected`；其余 kind
# 在 select 阶段即拒绝，避免 `rewrite.json` 出现"已选中但不可 apply"。
REWRITE_IMPLEMENTED_KINDS = frozenset({"constant_fold_static_shape"})

# 改写 parity 的硬下限：只接受与完整校准集同样规模的 40 条真实输入。
REWRITE_PARITY_INPUTS = 40

# HTP V81 不执行的算子：出现在最终路径即说明回退到 CPU，必须拒绝。
CPU_ONLY_OPERATORS = frozenset(
    {"NonMaxSuppression", "StringNormalizer", "TfIdfVectorizer", "Loop", "If", "Scan"}
)


@dataclass(frozen=True)
class RewriteResult:
    """一次语义改写的可审计结果；`parity` 必须是 40 条真实输入的 FP32 比较。"""

    name: str
    source_sha256: str
    output_sha256: str
    parity: dict[str, Any]
    changed_nodes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["changed_nodes"] = list(self.changed_nodes)
        return payload


def _rewrite_interval(interval: Any) -> tuple[int, int]:
    """把 isolation 区间解析成 `(start, end)`；结构不合法直接拒绝。"""
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError(
            f"isolation.interval 必须是 [start, end] 两元区间，实际 {interval!r}"
        )
    try:
        start, end = int(interval[0]), int(interval[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"isolation.interval 必须是整数区间，实际 {interval!r}"
        ) from exc
    if start < 0 or end <= start:
        raise ValueError(
            f"isolation.interval 必须满足 0 <= start < end，实际 {interval!r}"
        )
    return start, end


def _isolation_evidence(
    isolation: Mapping[str, Any],
) -> list[tuple[int, str | None, bool]]:
    """收集 `(节点索引, 真机状态, 是否有 probe context SHA-256)`。

    `probes` 记录初始阶段 prefix 真机结果，`steps` 记录二分中点结果；
    两者共同覆盖停止条件在首轮即满足（steps 为空）的已验证区间。
    """
    rows: list[tuple[int, str | None, bool]] = []
    probes = isolation.get("probes")
    for probe in probes if isinstance(probes, list) else ():
        if not isinstance(probe, Mapping):
            continue
        node_interval = probe.get("node_interval")
        if not isinstance(node_interval, (list, tuple)) or len(node_interval) != 2:
            continue
        device = probe.get("device")
        status = device.get("status") if isinstance(device, Mapping) else None
        rows.append((
            int(node_interval[1]),
            str(status) if status is not None else None,
            bool(probe.get("context_sha256")),
        ))
    steps = isolation.get("steps")
    for step in steps if isinstance(steps, list) else ():
        if not isinstance(step, Mapping) or not isinstance(step.get("node_index"), int):
            continue
        device = step.get("device")
        status = device.get("status") if isinstance(device, Mapping) else None
        probe = step.get("probe")
        rows.append((
            int(step["node_index"]),
            str(status) if status is not None else None,
            bool(isinstance(probe, Mapping) and probe.get("context_sha256")),
        ))
    return rows


def _isolation_provenance_problems(
    isolation: Mapping[str, Any], interval: tuple[int, int]
) -> list[str]:
    """区间端点必须能追到真机探针与探针哈希，且宽度已收敛。

    只校验与当前区间端点相关的证据：终点 `interval[1]` 必须是失败 probe，
    起点 `interval[0]`（非图输入 0）必须是通过 probe。与区间无关的 probe
    （例如已被 `metadata_rejected`、没有 context 的 3076）不得污染门禁。
    宽度超过二分阈值时，只有 `stop_reason="single_operator_family"` 的
    单算子族停止才豁免；其余情况一律判未收敛。
    """
    start, end = interval
    problems: list[str] = []
    rows = _isolation_evidence(isolation)
    if not rows:
        problems.append("缺少真机探针证据（probes 与 steps 均为空）")
        return problems
    end_evidence = [(status, hashed) for index, status, hashed in rows if index == end]
    if not any(status in FAILING_STATUSES and hashed for status, hashed in end_evidence):
        if not end_evidence:
            problems.append(f"区间终点 {end} 没有失败 probe 的真机证据")
        else:
            problems.append(
                f"区间终点 {end} 的真机证据不完整"
                f"（需要失败状态与 context SHA-256）：{end_evidence}"
            )
    if start != 0:
        start_evidence = [
            (status, hashed) for index, status, hashed in rows if index == start
        ]
        if not any(status == "pass" and hashed for status, hashed in start_evidence):
            if not start_evidence:
                problems.append(f"区间起点 {start} 没有通过 probe 的真机证据")
            else:
                problems.append(
                    f"区间起点 {start} 的真机证据不完整"
                    f"（需要 pass 状态与 context SHA-256）：{start_evidence}"
                )
    if end - start > BISECTION_MAX_NODES:
        if isolation.get("stop_reason") == BISECTION_STOP_SINGLE_FAMILY:
            pass
        else:
            problems.append(
                f"区间宽度 {end - start} 超过二分停止阈值 {BISECTION_MAX_NODES}，"
                "且不是单算子族停止，未收敛区间不能作为改写依据"
            )
    return problems


def select_rewrite(isolation: Mapping[str, Any]) -> dict[str, Any]:
    """只从 `isolation.json` 的已验证区间选改写；没有证据就显式 blocked。"""
    status = str(isolation.get("status") or "")
    interval = isolation.get("interval")
    families = tuple(str(item) for item in isolation.get("operator_families") or ())
    record: dict[str, Any] = {
        "status": REWRITE_BLOCKED,
        "kind": None,
        "interval": None,
        "awaiting_interval": isolation.get("awaiting_interval"),
        "operator_families": list(families),
        "reason": (
            f"isolation 状态为 {status or 'unknown'}，没有已验证的节点区间；"
            "改写必须由真机隔离区间驱动，禁止凭猜测构造"
        ),
    }
    if status != "verified" or interval is None:
        return record
    bounds = _rewrite_interval(interval)
    kinds = {REWRITE_BY_FAMILY.get(family) for family in families}
    if len(families) != 1 or None in kinds:
        record.update({
            "status": REWRITE_UNSUPPORTED,
            "reason": (
                f"算子族 {list(families)} 没有已注册的等价改写；"
                f"只接受单一且属于 {sorted(REWRITE_BY_FAMILY)} 的算子族"
            ),
        })
        return record
    kind = next(iter(kinds))
    if kind not in REWRITE_IMPLEMENTED_KINDS:
        record.update({
            "status": REWRITE_UNSUPPORTED_KIND,
            "interval": list(bounds),
            "reason": (
                f"算子族 {families[0]} 对应改写 {kind}，但该改写没有实现；"
                "未实现的 kind 不能被选中"
            ),
        })
        return record
    problems = _isolation_provenance_problems(isolation, bounds)
    if problems:
        record.update({
            "status": REWRITE_UNPROVEN,
            "interval": list(bounds),
            "reason": "；".join(problems),
        })
        return record
    record.update({
        "status": REWRITE_SELECTED,
        "kind": kind,
        "interval": list(bounds),
        "reason": f"隔离区间 {list(bounds)} 的单一算子族 {families[0]}",
    })
    return record


def require_rewrite_parity(result: RewriteResult) -> None:
    """硬门禁：改写必须在 40 条真实输入上过 FP32 parity，否则不得编译。"""
    parity = result.parity or {}
    inputs = parity.get("inputs")
    if not isinstance(inputs, int) or inputs != REWRITE_PARITY_INPUTS:
        raise ValueError(
            f"改写 {result.name} 的 FP32 parity 只覆盖 {inputs} 条输入，"
            f"必须覆盖 {REWRITE_PARITY_INPUTS} 条真实输入"
        )
    max_abs = parity.get("max_abs")
    median = parity.get("cosine_median")
    minimum = parity.get("cosine_minimum")
    detail = parity.get("reason") or "缺少 parity 证据"
    if not parity.get("passed") or max_abs is None:
        raise ValueError(f"改写 {result.name} 未通过 FP32 parity：{detail}")
    if float(max_abs) == 0.0:
        return
    if median is None or minimum is None:
        raise ValueError(
            f"改写 {result.name} 的 FP32 parity 不是逐元素一致，且缺少 cosine 证据"
        )
    if float(median) < PARITY_MEDIAN_MIN or float(minimum) < PARITY_MINIMUM_MIN:
        raise ValueError(
            f"改写 {result.name} 未通过 FP32 parity：cosine median={median} "
            f"minimum={minimum}（要求 median>={PARITY_MEDIAN_MIN} "
            f"minimum>={PARITY_MINIMUM_MIN}）"
        )


def require_htp_executable(model: Path | "onnx.ModelProto") -> None:
    """最终路径不得含 CPU 回退算子。"""
    model_proto = _as_model(model)
    offenders = sorted({node.op_type for node in model_proto.graph.node} & CPU_ONLY_OPERATORS)
    if offenders:
        raise ValueError(f"最终路径含 CPU 算子：{offenders}，拒绝上机")


def _static_shapes(model: "onnx.ModelProto") -> dict[str, tuple[int, ...]]:
    """经 shape inference 得到所有完全静态张量的 shape。"""
    onnx = _require_onnx()
    inferred = onnx.shape_inference.infer_shapes(model)
    shapes = {
        value.name: tuple(int(dim.dim_value) for dim in value.type.tensor_type.shape.dim)
        for value in list(inferred.graph.input) + list(inferred.graph.value_info)
        + list(inferred.graph.output)
        if value.type.tensor_type.HasField("shape")
        and all(
            dim.HasField("dim_value") and int(dim.dim_value) > 0
            for dim in value.type.tensor_type.shape.dim
        )
    }
    for initializer in inferred.graph.initializer:
        shapes[initializer.name] = tuple(int(dim) for dim in initializer.dims)
    return shapes


def _int_attribute(node: Any, name: str) -> int | None:
    for attribute in node.attribute:
        if attribute.name == name:
            return int(attribute.i)
    return None


def _fold_static_shape(
    model_proto: "onnx.ModelProto",
    interval: tuple[int, int],
) -> tuple["onnx.ModelProto", tuple[str, ...]]:
    """把隔离区间内的静态 `Shape` 及其常量 `Gather` 折成 `Constant`。

    只处理 `interval[0] < index <= interval[1]` 的节点；区间外原样保留。
    区间内出现无法安全折叠的算子（Shape 带部分 start/end、Gather 非 axis 0、
    输入 shape 非静态、非常量索引）时直接拒绝，不做猜测。
    """
    onnx = _require_onnx()
    np = _require_numpy()
    shapes = _static_shapes(model_proto)
    constants: dict[str, tuple[str, "np.ndarray"]] = {}
    nodes: list[Any] = []
    changed: list[str] = []
    indices = {
        initializer.name: np.frombuffer(
            initializer.raw_data, dtype="<i8"
        ) if initializer.data_type == 7 else np.asarray(
            initializer.int64_data, dtype="<i8"
        )
        for initializer in model_proto.graph.initializer
    }
    for index, node in enumerate(model_proto.graph.node):
        in_interval = interval[0] < index <= interval[1]
        if not in_interval:
            nodes.append(node)
            continue
        if node.op_type == "Shape":
            if len(node.input) != 1:
                raise ValueError(f"区间内 Shape {node.name} 输入数不是 1，无法安全折叠")
            shape = shapes.get(node.input[0])
            if shape is None:
                raise ValueError(
                    f"区间内 Shape {node.name} 的输入 {node.input[0]} 不是静态 shape，"
                    "无法安全折叠"
                )
            start = _int_attribute(node, "start")
            end = _int_attribute(node, "end")
            if (start is not None and start != 0) or (
                end is not None and end != len(shape)
            ):
                raise ValueError(
                    f"区间内 Shape {node.name} 带 start/end=({start},{end})，"
                    f"全量 shape 长度为 {len(shape)}，无法安全折叠"
                )
            tensor = np.asarray(shape, dtype="<i8")
            constants[node.output[0]] = (node.name, tensor)
            nodes.append(
                onnx.helper.make_node(
                    "Constant",
                    [],
                    [node.output[0]],
                    name=node.name,
                    value=onnx.helper.make_tensor(
                        f"{node.output[0]}_value",
                        onnx.TensorProto.INT64,
                        [len(shape)],
                        tensor.tolist(),
                    ),
                )
            )
            changed.append(node.name)
            continue
        if node.op_type == "Gather":
            axis = _int_attribute(node, "axis")
            if axis is not None and axis != 0:
                raise ValueError(
                    f"区间内 Gather {node.name} 的 axis={axis}，"
                    "只有 axis=0 的静态 Shape 索引可以安全折叠"
                )
            if (
                len(node.input) != 2
                or node.input[0] not in constants
                or node.input[1] not in indices
            ):
                raise ValueError(
                    f"区间内 Gather {node.name} 不是静态 Shape 上的常量索引，"
                    "无法安全折叠"
                )
            tensor = constants[node.input[0]][1][indices[node.input[1]]]
            nodes.append(
                onnx.helper.make_node(
                    "Constant",
                    [],
                    [node.output[0]],
                    name=node.name,
                    value=onnx.helper.make_tensor(
                        f"{node.output[0]}_value",
                        onnx.TensorProto.INT64,
                        list(tensor.shape) or [1],
                        tensor.reshape(-1).tolist(),
                    ),
                )
            )
            changed.append(node.name)
            continue
        raise ValueError(
            f"区间内节点 {node.name}（{node.op_type}）不属于该改写族，无法安全折叠"
        )

    used = {name for node in nodes for name in node.input if name}
    initializers = [
        copy.deepcopy(initializer)
        for initializer in model_proto.graph.initializer
        if initializer.name in used
    ]
    graph = onnx.helper.make_graph(
        nodes,
        model_proto.graph.name,
        copy.deepcopy(list(model_proto.graph.input)),
        copy.deepcopy(list(model_proto.graph.output)),
        initializer=initializers,
    )
    rewritten = onnx.helper.make_model(
        graph,
        opset_imports=copy.deepcopy(model_proto.opset_import),
        producer_name="laos-speaker-qnn-rewrite",
        ir_version=model_proto.ir_version,
    )
    return rewritten, tuple(changed)


REWRITE_HANDLERS: dict[
    str, Callable[[Any, tuple[int, int]], tuple[Any, tuple[str, ...]]]
] = {
    "constant_fold_static_shape": _fold_static_shape,
}


def verify_rewrite_parity(
    model: Path,
    rewritten: Path,
    input_list: Path,
) -> dict[str, Any]:
    """改写后完整 FP32 输出 vs 原图，逐条比较 40 条真实输入。"""
    np = _require_numpy()
    ort = _import_onnxruntime()
    original = _load_model(Path(model))
    input_name, input_shape = _model_input_spec(original)
    output_name = original.graph.output[0].name
    entries = parse_input_list(Path(input_list))
    if not entries:
        raise ValueError("改写 parity 的 input list 为空")
    original_session = ort.InferenceSession(
        original.SerializeToString(), _session_options(),
        providers=["CPUExecutionProvider"],
    )
    rewritten_proto = _load_model(Path(rewritten))
    if rewritten_proto.graph.output[0].name != output_name:
        return {
            "passed": False,
            "reason": "改写后输出张量名变化，无法逐条配对",
            "max_abs": None,
            "cosine_median": None,
            "cosine_minimum": None,
        }
    rewritten_session = ort.InferenceSession(
        rewritten_proto.SerializeToString(), _session_options(),
        providers=["CPUExecutionProvider"],
    )
    reference: list["np.ndarray"] = []
    candidate: list["np.ndarray"] = []
    for _, raw_path in entries:
        array = _input_array(raw_path, input_shape)
        reference.append(
            np.asarray(original_session.run([output_name], {input_name: array})[0])
        )
        candidate.append(
            np.asarray(rewritten_session.run([output_name], {input_name: array})[0])
        )
    gate = parity_gate(
        np.stack([value.reshape(-1) for value in reference], axis=0),
        np.stack([value.reshape(-1) for value in candidate], axis=0),
    )
    gate["inputs"] = len(reference)
    return gate


def validate_rewrite_result(
    result: RewriteResult,
    isolation: Mapping[str, Any],
    *,
    model: Path | "onnx.ModelProto",
    output: Path | None = None,
) -> None:
    """改写必须记录节点名、落在隔离区间内，且最终路径无 CPU 算子。"""
    if not result.changed_nodes:
        raise ValueError(f"改写 {result.name} 没有记录 changed_nodes")
    interval = isolation.get("interval")
    if interval is None:
        raise ValueError("isolation 没有已验证区间，无法判定改写范围")
    model_proto = _as_model(model)
    positions = {node.name: index for index, node in enumerate(model_proto.graph.node)}
    missing = [name for name in result.changed_nodes if name not in positions]
    if missing:
        raise ValueError(f"改写记录的节点不在原图里：{missing}")
    outside = [
        name
        for name in result.changed_nodes
        if not int(interval[0]) < positions[name] <= int(interval[1])
    ]
    if outside:
        raise ValueError(f"改写范围 {outside} 超出隔离区间 {interval}，属于无关改写")
    require_htp_executable(Path(output) if output is not None else model_proto)


def apply_semantic_rewrite(
    model: Path,
    isolation: Mapping[str, Any],
    output: Path,
    *,
    input_list: Path = DEFAULT_CALIBRATION,
) -> RewriteResult:
    """选改写 → 改写 → FP32 parity 硬门禁 → 记录 changed_nodes。

    没有已验证隔离区间时直接拒绝（`blocked_on_isolated_interval`），
    被 parity 门禁拒绝的产物会立即删除，绝不留下可被误编译的 ONNX。
    """
    selection = select_rewrite(isolation)
    if selection["status"] != REWRITE_SELECTED:
        raise ValueError(
            f"改写被拒绝（{selection['status']}）：{selection['reason']}"
        )
    handler = REWRITE_HANDLERS.get(str(selection["kind"]))
    if handler is None:
        raise ValueError(f"改写族 {selection['kind']} 没有实现")
    model = Path(model)
    rewritten, changed = handler(
        _load_model(model), (int(selection["interval"][0]), int(selection["interval"][1]))
    )
    if not changed:
        raise ValueError(f"改写 {selection['kind']} 没有命中任何节点，拒绝生成空改写")
    output = _output_path(Path(output), "rewrite.onnx")
    _save_model(rewritten, output)
    result = RewriteResult(
        name=str(selection["kind"]),
        source_sha256=_sha256(model),
        output_sha256=_sha256(output),
        parity=verify_rewrite_parity(model, output, Path(input_list)),
        changed_nodes=tuple(changed),
    )
    try:
        validate_rewrite_result(result, isolation, model=model, output=output)
        require_rewrite_parity(result)
    except ValueError:
        output.unlink(missing_ok=True)
        raise
    return result


def _transpose_axes(
    source: tuple[int, ...], target: tuple[int, ...]
) -> tuple[int, ...] | None:
    """返回 `axes` 使 `transpose(source, axes).shape == target`；无法置换返回 None。"""
    if len(source) != len(target) or sorted(source) != sorted(target):
        return None
    used = [False] * len(source)
    axes: list[int] = []
    for dim in target:
        for index, value in enumerate(source):
            if not used[index] and value == dim:
                used[index] = True
                axes.append(index)
                break
        else:
            return None
    return tuple(axes)


def _inverse_axes(axes: Sequence[int]) -> tuple[int, ...]:
    inverse = [0] * len(axes)
    for position, axis in enumerate(axes):
        inverse[axis] = position
    return tuple(inverse)


def verify_layout_handoff(
    cut: TensorCut,
    manifest: IntermediateManifest,
    prefix_metadata: ContextMetadata | None,
    suffix_metadata: ContextMetadata | None,
) -> dict[str, Any]:
    """显式声明并验证 prefix 物理输出 → suffix 物理输入的 transpose。

    用 3 条真实捕获中间张量做 transposed round-trip：语义 → prefix 物理
    → 声明 transpose → suffix 物理 → 逆变换恢复语义，要求逐元素一致。
    元素数或轴集合不衔接的组合必须拒绝，不能静默通过。
    """
    np = _require_numpy()
    semantic = tuple(cut.shape)
    result: dict[str, Any] = {
        "semantic_output_shape": list(semantic),
        "prefix_physical_output_shape": None,
        "suffix_physical_input_shape": None,
        "transpose_axes": None,
        "verified": False,
        "cosine_minimum": None,
        "round_trip_max_abs": None,
        "samples": 0,
    }
    if prefix_metadata is None or suffix_metadata is None:
        result["reason"] = "缺少 prefix 或 suffix context metadata，无法声明布局链"
        return result
    prefix_shape = tuple(prefix_metadata.output_shape)
    suffix_shape = tuple(suffix_metadata.input_shape)
    result["prefix_physical_output_shape"] = list(prefix_shape)
    result["suffix_physical_input_shape"] = list(suffix_shape)
    if math.prod(prefix_shape) != math.prod(suffix_shape):
        result["reason"] = f"元素数不衔接：{prefix_shape} vs {suffix_shape}"
        return result
    handoff_axes = _transpose_axes(prefix_shape, suffix_shape)
    if handoff_axes is None:
        result["reason"] = f"形状不是同一元素的轴置换：{prefix_shape} -> {suffix_shape}"
        return result
    semantic_to_prefix = _transpose_axes(semantic, prefix_shape)
    semantic_to_suffix = _transpose_axes(semantic, suffix_shape)
    if semantic_to_prefix is None or semantic_to_suffix is None:
        result["reason"] = (
            f"cut 语义 shape {semantic} 无法映射到物理布局 "
            f"{prefix_shape}/{suffix_shape}"
        )
        return result
    result["transpose_axes"] = list(handoff_axes)
    entries = manifest.entries
    indices = sorted({0, len(entries) // 2, len(entries) - 1})[:LAYOUT_SAMPLE_ENTRIES]
    cosine_minimum = 1.0
    max_abs = 0.0
    checked = 0
    for index in indices:
        raw = np.fromfile(Path(entries[index].raw_path), dtype="<f4").reshape(semantic)
        prefix_value = np.transpose(raw, semantic_to_prefix)
        suffix_value = np.transpose(prefix_value, handoff_axes)
        if tuple(suffix_value.shape) != suffix_shape:
            result["reason"] = (
                f"transpose 后 shape {suffix_value.shape} 与 suffix 输入 {suffix_shape} 不一致"
            )
            return result
        round_trip = np.transpose(
            np.transpose(suffix_value, _inverse_axes(handoff_axes)),
            _inverse_axes(semantic_to_prefix),
        )
        if tuple(round_trip.shape) != semantic:
            result["reason"] = f"round-trip shape {round_trip.shape} 与语义 {semantic} 不一致"
            return result
        delta = np.abs(
            np.asarray(round_trip, dtype=np.float64) - np.asarray(raw, dtype=np.float64)
        )
        max_abs = max(max_abs, float(np.max(delta)) if delta.size else 0.0)
        left = np.asarray(raw, dtype=np.float64).reshape(-1)
        right = np.asarray(round_trip, dtype=np.float64).reshape(-1)
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        cosine = float(np.dot(left, right) / denominator) if denominator else 1.0
        cosine_minimum = min(cosine_minimum, cosine)
        checked += 1
    result["samples"] = checked
    result["round_trip_max_abs"] = max_abs
    result["cosine_minimum"] = cosine_minimum
    if max_abs != 0.0 or cosine_minimum < PARITY_MINIMUM_MIN:
        result["reason"] = (
            f"transposed round-trip 不一致：max_abs={max_abs} "
            f"cosine_min={cosine_minimum}"
        )
        return result
    result["verified"] = True
    result["reason"] = (
        f"transpose {list(handoff_axes)} 经 {checked} 条真实张量 round-trip 验证"
    )
    return result


def _as_model(model: Path | "onnx.ModelProto") -> "onnx.ModelProto":
    if hasattr(model, "graph"):
        return model  # type: ignore[return-value]
    return _load_model(Path(model))


def _node_operator_families(
    model: Path | "onnx.ModelProto", first_node: int, last_node: int
) -> tuple[str, ...]:
    """区间 `first_node+1..last_node` 内剩余节点的算子族。"""
    model_proto = _as_model(model)
    nodes = list(model_proto.graph.node)[first_node + 1 : last_node + 1]
    return tuple(sorted({node.op_type for node in nodes}))


def bisection_stop(
    model: Path | "onnx.ModelProto", first_node: int, last_node: int
) -> dict[str, Any] | None:
    """brief Step 6 停止条件：≤16 个节点，或剩余节点同属一个算子族。

    `stop_reason` 是机器码（`node_count` / `single_operator_family`），
    供 `isolation.json` 与改写门禁判断"宽度超限是否由单算子族豁免"；
    人类可读说明放在 `stop_detail`。
    """
    node_count = last_node - first_node
    families = _node_operator_families(model, first_node, last_node)
    if node_count <= BISECTION_MAX_NODES:
        return {
            "stop_reason": "node_count",
            "stop_detail": f"区间 {node_count} 个 ONNX 节点 <= {BISECTION_MAX_NODES}",
            "node_count": node_count,
            "operator_families": list(families),
        }
    if len(families) == 1:
        return {
            "stop_reason": "single_operator_family",
            "stop_detail": f"剩余节点同属算子族 {families[0]}",
            "node_count": node_count,
            "operator_families": list(families),
        }
    return None


def _cut_at_node(
    model_proto: "onnx.ModelProto",
    node_index: int,
    input_name: str,
    array: "np.ndarray",
    ort,
) -> TensorCut | None:
    node = model_proto.graph.node[node_index]
    if not node.output:
        return None
    tensor_name = node.output[0]
    try:
        session = ort.InferenceSession(
            _instrumented_model(model_proto, [tensor_name]).SerializeToString(),
            _session_options(),
            providers=["CPUExecutionProvider"],
        )
        value = session.run([tensor_name], {input_name: array})[0]
        shape = tuple(int(dim) for dim in value.shape)
        dtype = str(value.dtype)
        if any(dim <= 0 for dim in shape) or dtype not in FLOAT_DTYPES:
            return None
        if not np_all_finite(value):
            return None
        return TensorCut(node_index, tensor_name, shape, dtype)
    except Exception:
        return None


def np_all_finite(value) -> bool:
    np = _require_numpy()
    return bool(np.all(np.isfinite(value)))


def midpoint_cut(
    model: Path | "onnx.ModelProto",
    first_node: int,
    last_node: int,
    sample_input: Path,
) -> TensorCut | None:
    """在 `(first_node, last_node)` 内选中点附近第一个静态可表示的 cut。"""
    ort = _import_onnxruntime()
    model_proto = _as_model(model)
    input_name, input_shape = _model_input_spec(model_proto)
    array = _input_array(Path(sample_input), input_shape)
    candidates = list(range(first_node + 1, last_node))
    if not candidates:
        return None
    middle = (first_node + last_node) / 2.0
    candidates.sort(key=lambda index: (abs(index - middle), index))
    for index in candidates:
        cut = _cut_at_node(model_proto, index, input_name, array, ort)
        if cut is not None:
            return cut
    return None


ProbeRunner = Callable[
    ["TensorCut"], tuple[ProbeSpec, dict[str, Any], DeviceRunResult]
]


def run_bisection(
    model: Path | "onnx.ModelProto",
    interval: tuple[int, int],
    sample_input: Path,
    probe_at_cut: ProbeRunner | None,
    *,
    device_online: bool = True,
    max_steps: int = 16,
) -> dict[str, Any]:
    """Step 6 二分循环：只在当前失败区间内生成中点 cut，直到停止条件。

    设备不可用时停在 `awaiting_device`：`interval` 为 None（未验证），
    只保留 `awaiting_interval` 与待真机说明，绝不把未验证区间当成结论。
    """
    model_proto = _as_model(model)
    start, end = int(interval[0]), int(interval[1])
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "awaiting_device",
        "verified": False,
        "interval": None,
        "awaiting_interval": [start, end],
        "node_count": max(end - start, 0),
        "operator_families": [],
        "stop_reason": "awaiting_device",
        "stop_detail": "设备不在 adb，二分未取得真机证据（awaiting_device）",
        "steps": [],
    }
    if not device_online or probe_at_cut is None:
        return payload
    if start >= end:
        raise ValueError(f"二分区间自相矛盾：{start} >= {end}")
    steps: list[dict[str, Any]] = []
    for _ in range(max_steps):
        stop = bisection_stop(model_proto, start, end)
        if stop is not None:
            payload.update({
                "status": "verified",
                "verified": True,
                "interval": [start, end],
                "node_count": stop["node_count"],
                "operator_families": stop["operator_families"],
                "stop_reason": stop["stop_reason"],
                "stop_detail": stop["stop_detail"],
                "steps": steps,
            })
            return payload
        cut = midpoint_cut(model_proto, start, end, sample_input)
        if cut is None:
            payload.update({
                "status": "no_static_cut",
                "stop_reason": "no_static_cut",
                "stop_detail": (
                    f"区间 ({start}, {end}) 内没有静态可表示的 cut，无法继续二分"
                ),
                "steps": steps,
            })
            return payload
        try:
            spec, record, result = probe_at_cut(cut)
        except Exception as exc:  # 单个中点失败不能中断整个二分、丢掉已有证据
            steps.append({
                "node_index": cut.node_index,
                "cut": cut.to_dict(),
                "probe": None,
                "device": None,
                "status": "probe_error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            payload.update({
                "status": "probe_error",
                "awaiting_interval": [start, end],
                "stop_reason": "probe_error",
                "stop_detail": (
                    f"中点 cut {cut.node_index} 的 probe 构建/校验失败，"
                    f"已保留 {len(steps)} 步证据后终止："
                    f"{type(exc).__name__}: {exc}"
                ),
                "steps": steps,
            })
            return payload
        steps.append({
            "node_index": cut.node_index,
            "cut": cut.to_dict(),
            "probe": record,
            "device": result.to_dict(),
        })
        if result.status == "pass":
            start = cut.node_index
        elif result.status in FAILING_STATUSES:
            end = cut.node_index
        else:
            payload.update({
                "status": "inconclusive",
                "awaiting_interval": [start, end],
                "stop_reason": "inconclusive",
                "stop_detail": f"中点 probe 状态 {result.status}，不能当模型失败",
                "steps": steps,
            })
            return payload
    payload.update({
        "status": "max_steps",
        "awaiting_interval": [start, end],
        "stop_reason": "max_steps",
        "stop_detail": f"二分达到 {max_steps} 步仍未满足停止条件",
        "steps": steps,
    })
    return payload


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


MAX_PARTITION_CONTEXTS = 2
_DTYPE_SIZES = {"float32": 4, "float16": 2, "int16": 2, "int8": 1, "uint8": 1}


def dtype_size(dtype: str) -> int:
    """cut 张量单元素字节数；未知 dtype 直接拒绝。"""
    try:
        return _DTYPE_SIZES[dtype]
    except KeyError as exc:
        raise ValueError(f"不支持的 cut dtype：{dtype}") from exc


PARTITION_SELECTION_BASIS = "smallest_intermediate_only"
PARTITION_SOLVES_ROOT_CAUSE = "unproven"
PARTITION_UPGRADE_RULE = (
    "只有 isolation 已验证且故障区间完全落在 prefix 之外"
    "（interval[0] >= cut.node_index）时，才把该分区升级为根因候选"
)


@dataclass(frozen=True)
class PartitionPlan:
    """双 context 分区：cut 两侧各一个 context，中间张量只走原生 I/O 搬运。"""

    cut: TensorCut
    prefix_context: BuildArtifact
    suffix_context: BuildArtifact
    transfer_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cut": self.cut.to_dict(),
            "prefix": self.prefix_context.to_dict(),
            "suffix": self.suffix_context.to_dict(),
            "transfer_bytes": self.transfer_bytes,
            "selection_basis": PARTITION_SELECTION_BASIS,
            "solves_root_cause": PARTITION_SOLVES_ROOT_CAUSE,
        }


def require_partition_limit(artifacts: Sequence[BuildArtifact]) -> None:
    """双 context 是硬上限；三段及以上直接拒绝，不扩展试错空间。"""
    if len(artifacts) > MAX_PARTITION_CONTEXTS:
        raise ValueError(
            f"分区最多 {MAX_PARTITION_CONTEXTS} 段，实际 {len(artifacts)} 段；"
            "三段以上方案不进入本计划"
        )


def partition_candidate_upgrade(
    isolation: Mapping[str, Any] | None, cut: TensorCut
) -> dict[str, Any]:
    """按真机隔离区间判断该分区能否从"最小中间张量"升级为根因候选。"""
    record: dict[str, Any] = {"eligible": False, "condition": PARTITION_UPGRADE_RULE}
    if not isolation or isolation.get("status") != "verified":
        record["reason"] = "isolation 尚未验证，分区只按最小中间张量选择，不能声称解决根因"
        return record
    interval = isolation.get("interval")
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        record["reason"] = f"isolation 区间不完整：{interval!r}"
        return record
    first = int(interval[0])
    if first >= cut.node_index:
        record.update({
            "eligible": True,
            "reason": (
                f"故障区间 {list(interval)} 完全落在 prefix（节点 <= {cut.node_index}）之外"
            ),
        })
        return record
    record["reason"] = (
        f"故障区间 {list(interval)} 与 prefix（节点 <= {cut.node_index}）重叠；"
        "该分区不能解决主体超时"
    )
    return record


def _partition_manifest(cut: TensorCut, output_dir: Path) -> Path:
    """在 output_dir 上方最近三层里找 cut 的真实中间张量 manifest。"""
    slug = _slug(f"{cut.node_index:04d}-{cut.tensor_name}")
    base = Path(output_dir)
    for ancestor in (base, *tuple(base.parents)[:3]):
        candidate = ancestor / "intermediates" / slug / "manifest.json"
        if candidate.is_file():
            return candidate
    raise ValueError(
        f"找不到 cut {cut.tensor_name} 的真实中间张量 manifest"
        f"（intermediates/{slug}/manifest.json）"
    )


def build_partition(
    model: Path,
    cut: TensorCut,
    variant: BuildVariant,
    output_dir: Path,
    *,
    input_list: Path = DEFAULT_CALIBRATION,
    intermediate_manifest: Path | None = None,
    serial: str | None = None,
    isolation: Mapping[str, Any] | None = None,
) -> PartitionPlan:
    """构建 cut 两侧的 prefix + suffix context（同一 QAIRT build）。

    suffix 只以 FP32 真实捕获的中间张量做校准；两侧上下文先过拼接 parity
    与布局交接校验才返回。设备不在线时 `partition.json` 记
    `device_unavailable`，不构造任何真机结论。
    """
    model = Path(model)
    input_list = Path(input_list)
    output_dir = Path(output_dir)
    manifest_path = (
        Path(intermediate_manifest)
        if intermediate_manifest is not None
        else _partition_manifest(cut, output_dir)
    )
    manifest = load_manifest(manifest_path)
    if manifest.source_kind != SOURCE_KIND_REAL_AUDIO:
        raise ValueError(
            f"后缀校准必须来自 {SOURCE_KIND_REAL_AUDIO}，实际 {manifest.source_kind!r}"
        )

    prefix_dir = output_dir / "prefix"
    suffix_dir = output_dir / "suffix"
    prefix_onnx = prefix_dir / "onnx" / "prefix.onnx"
    suffix_onnx = suffix_dir / "onnx" / "suffix.onnx"
    extract_prefix(model, cut, prefix_onnx)
    extract_suffix(model, cut, manifest_path, suffix_onnx, input_list=input_list)
    # 两个分区 ONNX 与改写走同一 CPU 算子门禁：任一含 CPU-only 算子即拒绝编译。
    require_htp_executable(prefix_onnx)
    require_htp_executable(suffix_onnx)
    prefix_list = prefix_dir / "input_list.txt"
    shutil.copyfile(input_list, prefix_list)
    suffix_list = write_suffix_calibration(manifest, suffix_dir / "input_list.txt")

    parity = verify_probe_parity(model, prefix_onnx, suffix_onnx, cut, input_list)
    write_json_atomic(output_dir / "parity.json", parity)
    if not parity.get("passed"):
        raise ValueError(f"双 context 分区未过 FP32 parity：{parity.get('reason')}")

    prefix_variant = BuildVariant(
        variant.toolchain,
        variant.optimization_level,
        variant.vtcm_mb,
        variant.dlbc,
        f"{PROBE_GRAPH_NAME}_partition_prefix_{cut.node_index:04d}",
    )
    suffix_variant = BuildVariant(
        variant.toolchain,
        variant.optimization_level,
        variant.vtcm_mb,
        variant.dlbc,
        f"{PROBE_GRAPH_NAME}_partition_suffix_{cut.node_index:04d}",
    )
    prefix_artifact = build_w8a16_context(
        prefix_onnx,
        prefix_list,
        prefix_variant,
        prefix_dir,
        expected_input_shape=CAMPLUS_INPUT_SHAPE,
        expected_output_shape=tuple(cut.shape),
    )
    suffix_artifact = build_w8a16_context(
        suffix_onnx,
        suffix_list,
        suffix_variant,
        suffix_dir,
        expected_input_shape=_qnn_input_shape(cut.shape),
        expected_output_shape=CAMPLUS_OUTPUT_SHAPE,
    )
    require_partition_limit((prefix_artifact, suffix_artifact))
    for artifact in (prefix_artifact, suffix_artifact):
        if artifact.status not in (BUILD_READY, BUILD_CONFIG_WARNING):
            raise ValueError(
                f"分区 context 构建失败：{artifact.variant_id} "
                f"{artifact.status}：{artifact.error}"
            )

    layout = verify_layout_handoff(
        cut, manifest, prefix_artifact.metadata, suffix_artifact.metadata
    )
    write_json_atomic(output_dir / "layout.json", layout)
    if not layout["verified"]:
        raise ValueError(f"分区布局交接未验证：{layout.get('reason')}")

    transfer_bytes = math.prod(cut.shape) * dtype_size(cut.dtype)
    plan = PartitionPlan(cut, prefix_artifact, suffix_artifact, transfer_bytes)
    device_online = _device_available(serial)
    write_json_atomic(
        output_dir / "partition.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "device_unavailable" if not device_online else "device_pending",
            "reason": (
                "adb 无在线设备，host 侧构建完成但未上机"
                if not device_online
                else "context 已构建，双 context 串联真机运行尚未执行"
            ),
            "device": {"serial": serial, "available": device_online},
            "plan": plan.to_dict(),
            "selection_basis": PARTITION_SELECTION_BASIS,
            "solves_root_cause": PARTITION_SOLVES_ROOT_CAUSE,
            "candidate_upgrade": partition_candidate_upgrade(isolation, cut),
            "parity": parity,
            "layout": layout,
            "pending": [
                "设备恢复后先跑 prefix context，把原生输出按 layout.transpose_axes "
                "搬到 suffix context 的原生输入，再跑 suffix context",
                "同一真实输入连续 30 次完整 embedding：退出码 0、无 SSR、无 FastRPC "
                "timeout、每次 192 个有限值，总 warm graph time < 1 s",
                f"报告中间张量搬运成本 {transfer_bytes} 字节与两次 context 调度开销",
            ],
        },
    )
    return plan


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


def _probe_cut_on_device(
    cut: TensorCut,
    *,
    model: Path,
    toolchain: ToolchainSpec,
    calibration_list: Path,
    probes_root: Path,
    intermediates_root: Path,
    serial: str,
) -> tuple[ProbeSpec, dict[str, Any], DeviceRunResult]:
    """二分中点 probe：捕获真实中间张量 → parity → 编译 → 布局校验 → 真机。"""
    model = Path(model)
    calibration_list = Path(calibration_list)
    manifests = capture_intermediates(
        model, (cut,), calibration_list, Path(intermediates_root) / "bisect"
    )
    manifest_path = manifests[cut.tensor_name]
    manifest = load_manifest(manifest_path)

    prefix_dir = Path(probes_root) / "bisect" / _probe_id("prefix", cut)
    prefix_onnx = prefix_dir / "onnx" / "prefix.onnx"
    prefix_spec = extract_prefix(model, cut, prefix_onnx)
    prefix_list = prefix_dir / "input_list.txt"
    shutil.copyfile(calibration_list, prefix_list)

    suffix_dir = Path(probes_root) / "bisect" / _probe_id("suffix", cut)
    suffix_onnx = suffix_dir / "onnx" / "suffix.onnx"
    extract_suffix(model, cut, manifest_path, suffix_onnx, input_list=calibration_list)
    suffix_list = write_suffix_calibration(manifest, suffix_dir / "input_list.txt")
    parity = verify_probe_parity(model, prefix_onnx, suffix_onnx, cut, calibration_list)
    write_json_atomic(suffix_dir / "parity.json", parity)
    if not parity.get("passed"):
        raise ValueError(
            f"中点 cut {cut.tensor_name} 未过 FP32 parity：{parity.get('reason')}"
        )

    prefix_artifact, prefix_variant = _build_probe(
        prefix_dir, prefix_onnx, prefix_list, toolchain, cut, "prefix"
    )
    suffix_artifact, suffix_variant = _build_probe(
        suffix_dir, suffix_onnx, suffix_list, toolchain, cut, "suffix"
    )
    layout = verify_layout_handoff(
        cut, manifest, prefix_artifact.metadata, suffix_artifact.metadata
    )
    write_json_atomic(suffix_dir / "layout.json", layout)
    if not layout["verified"]:
        raise ValueError(
            f"中点 cut {cut.tensor_name} 布局交接未验证：{layout.get('reason')}"
        )

    run_dir = Path(probes_root) / "bisect-device-runs" / _probe_id("prefix", cut)
    result = run_context(
        serial,
        prefix_dir,
        prefix_list,
        run_dir,
        num_inferences=1,
        expected_input_shape=tuple(prefix_artifact.metadata.input_shape),
        expected_output_shape=tuple(prefix_artifact.metadata.output_shape),
    )
    record = _probe_record(
        prefix_spec,
        cut,
        model,
        prefix_dir,
        parity=parity,
        calibration_source="real_audio_fbank",
        calibration_sha256=_sha256(calibration_list),
    )
    record |= _build_fields(prefix_artifact, prefix_variant)
    record |= _shape_fields(cut, "prefix", prefix_artifact)
    record["layout"] = layout
    return prefix_spec, record, result


def _device_gate_reason(
    record: Mapping[str, Any], artifact: BuildArtifact | None
) -> str | None:
    """上机门禁：返回拒绝原因；None 表示允许推送真机。

    `layout_rejected` / `parity_rejected` / `metadata_rejected` 是语义或
    元数据不成立的明确拒绝，不能因为 context 构建成功就放行。
    """
    status = str(record.get("build_status") or "")
    if status in (BUILD_METADATA_REJECTED, "layout_rejected", "parity_rejected"):
        return f"probe 记录状态为 {status}，拒绝上机"
    if artifact is None:
        return "probe 没有编译产物，不上机"
    if artifact.metadata is None:
        return "probe context 缺少元数据，不上机"
    if artifact.status not in (BUILD_READY, BUILD_CONFIG_WARNING):
        return f"probe context 构建状态为 {artifact.status}，不上机"
    return None


def _run_device_probes(
    records: Sequence[tuple[ProbeSpec, dict[str, Any]]],
    probe_artifacts: Mapping[str, BuildArtifact],
    probe_lists: Mapping[str, Path],
    probes_root: Path,
    *,
    device_online: bool,
    serial: str | None,
) -> tuple[dict[str, dict[str, Any]], list[tuple[ProbeSpec, DeviceRunResult]]]:
    """逐个 probe 过上机门禁并推送真机；被拒绝的 probe 不调用 run_context。"""
    device_runs: dict[str, dict[str, Any]] = {}
    device_results: list[tuple[ProbeSpec, DeviceRunResult]] = []
    for spec, record in records:
        artifact = probe_artifacts.get(spec.probe_id)
        reason = _device_gate_reason(record, artifact)
        if reason is not None:
            device_runs[spec.probe_id] = {
                "status": "device_unavailable",
                "reason": reason,
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
            expected_input_shape=tuple(artifact.metadata.input_shape),
            expected_output_shape=tuple(artifact.metadata.output_shape),
        )
        device_runs[spec.probe_id] = {
            "status": result.status,
            "device_run": result.to_dict(),
            "reason": None,
        }
        device_results.append((spec, result))
    return device_runs, device_results


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
        suffix_manifest: IntermediateManifest | None
        suffix_parity: dict[str, Any] | None
        try:
            suffix_spec = extract_suffix(
                model, cut, manifest_path, suffix_onnx, input_list=calibration_list
            )
        except ValueError as exc:
            if "没有后缀子图" not in str(exc):
                raise
            suffix_manifest = None
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
        prefix_fields |= _shape_fields(cut, "prefix", prefix_artifact)
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
        suffix_fields |= _shape_fields(cut, "suffix", suffix_artifact)

        # prefix 物理输出 → suffix 物理输入必须显式声明 transpose，并用
        # 真实捕获中间张量做 round-trip；不衔接的组合拒绝上机。
        layout = verify_layout_handoff(
            cut,
            suffix_manifest,
            prefix_artifact.metadata if prefix_artifact is not None else None,
            suffix_artifact.metadata if suffix_artifact is not None else None,
        )
        layout["prefix_context_sha256"] = prefix_fields.get("context_sha256")
        layout["suffix_context_sha256"] = suffix_fields.get("context_sha256")
        write_json_atomic(suffix_dir / "layout.json", layout)
        if not parity_passed:
            suffix_fields["build_status"] = "parity_rejected"
        elif not layout["verified"]:
            suffix_fields["build_status"] = "layout_rejected"
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
            ) | suffix_fields | {"layout": layout},
        ))

    device_online = _device_available(serial)
    device_runs, device_results = _run_device_probes(
        prefixes + suffixes,
        probe_artifacts,
        probe_lists,
        probes_root,
        device_online=device_online,
        serial=serial,
    )

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
    runner: ProbeRunner | None = None
    if device_online and serial:
        def probe_at_cut(cut: TensorCut):
            return _probe_cut_on_device(
                cut,
                model=model,
                toolchain=toolchain,
                calibration_list=calibration_list,
                probes_root=probes_root,
                intermediates_root=intermediates_root,
                serial=serial,
            )

        runner = probe_at_cut

    stage_outcome, isolation = _stage_outcome(
        model,
        prefixes,
        device_results,
        device_online,
        variant_id,
        parity_failures,
        Path(entries[0][1]),
        runner,
    )
    rewrite = select_rewrite(isolation)
    write_json_atomic(probes_root / "rewrite.json", rewrite)
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
        "rewrite": rewrite,
    }
    write_json_atomic(probes_root / "stages.json", payload)
    write_json_atomic(probes_root / "isolation.json", isolation)
    return payload


def _build_fields(
    artifact: BuildArtifact | None, variant: BuildVariant | None
) -> dict[str, Any]:
    fields: dict[str, Any] = {
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
    # 被拒绝的构建已删除 context 产物：不能把已删除文件的 SHA-256 留在记录里。
    if (
        artifact is not None
        and (
            artifact.status not in (BUILD_READY, BUILD_CONFIG_WARNING)
            or not artifact.context_path
        )
    ):
        fields["context"] = None
        fields["context_sha256"] = None
        fields["sha256"].pop("context", None)
    return fields


def _shape_fields(
    cut: TensorCut, kind: str, artifact: BuildArtifact | None
) -> dict[str, Any]:
    """显式声明 cut 的语义 shape 与 QNN context 的物理 shape。"""
    metadata = artifact.metadata if artifact is not None else None
    if kind == "prefix":
        return {
            "semantic_output_shape": list(cut.shape),
            "physical_output_shape": (
                list(metadata.output_shape) if metadata is not None else None
            ),
        }
    return {
        "semantic_input_shape": list(cut.shape),
        "physical_input_shape": (
            list(metadata.input_shape) if metadata is not None else None
        ),
    }


def _stage_outcome(
    model: Path,
    prefixes: Sequence[tuple[ProbeSpec, dict[str, Any]]],
    device_results: Sequence[tuple[ProbeSpec, DeviceRunResult]],
    device_online: bool,
    variant_id: str,
    parity_failures: Sequence[str],
    sample_input: Path,
    probe_at_cut: ProbeRunner | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prefix_devices = [
        (spec, result) for spec, result in device_results if spec.kind == "prefix"
    ]
    suffix_devices = [
        (spec, result) for spec, result in device_results if spec.kind == "suffix"
    ]
    # isolation.probes 的 device 必须来自真实 run 记录，而不是 probe 记录
    # 里可能缺失的字段；否则设备恢复后所有端点都会被判"缺真机状态"。
    device_by_probe = {
        spec.probe_id: result.to_dict() for spec, result in device_results
    }
    isolation: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "awaiting_device",
        "reason": None,
        "stop_reason": None,
        "interval": None,
        "awaiting_interval": None,
        "node_count": None,
        "operator_families": [],
        "steps": [],
        "probes": [
            {
                "probe_id": record["probe_id"],
                "kind": record["kind"],
                "node_interval": record.get("node_interval"),
                "tensor": record.get("tensor"),
                "semantic_output_shape": record.get("semantic_output_shape"),
                "physical_output_shape": record.get("physical_output_shape"),
                "graph_sha256": (record.get("graph") or {}).get("sha256"),
                "context_sha256": record.get("context_sha256"),
                "device": device_by_probe.get(record["probe_id"]),
            }
            for _, record in prefixes
        ],
        "pending": [
            "设备恢复后重跑 `python -m scripts.speaker_qnn.probe stages "
            f"--variant {variant_id} --serial <serial>` 取得真机 prefix/suffix 结果",
            "有 prefix 失败证据后从 [最后通过, 首个失败] 区间生成中点 cut，"
            f"二分到区间 <= {BISECTION_MAX_NODES} 个节点或剩余节点同属一个算子族",
        ],
        "parity_failures": list(parity_failures),
    }
    last_node = len(_load_model(Path(model)).graph.node) - 1

    if not device_online:
        bisection = run_bisection(
            model, (0, last_node), Path(sample_input), None, device_online=False
        )
        isolation.update({
            "status": bisection["status"],
            "reason": bisection["stop_detail"],
            "stop_reason": bisection["stop_reason"],
            "interval": bisection["interval"],
            "awaiting_interval": bisection["awaiting_interval"],
            "node_count": bisection["node_count"],
            "operator_families": bisection["operator_families"],
            "steps": bisection["steps"],
        })
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
            "stop_reason": "no_prefix_failure",
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

    bisection = run_bisection(
        model,
        interval,
        Path(sample_input),
        probe_at_cut,
        device_online=True,
    )
    isolation.update({
        "status": bisection["status"],
        "reason": bisection["stop_detail"],
        "stop_reason": bisection["stop_reason"],
        "interval": bisection["interval"],
        "awaiting_interval": bisection["awaiting_interval"],
        "node_count": bisection["node_count"],
        "operator_families": bisection["operator_families"],
        "steps": bisection["steps"],
        "suffix_statuses": {
            spec.probe_id: result.status for spec, result in suffix_devices
        },
    })
    return (
        {
            "last_passing_prefix": interval[0],
            "first_failing_prefix": interval[1],
            "classification": (
                "stage_isolated"
                if bisection["status"] == "verified"
                else bisection["status"]
            ),
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
    rewrite = subcommands.add_parser("rewrite", help="从 isolation.json 选改写并落盘状态")
    rewrite.add_argument("--isolation", default=str(DEBUG_ROOT / "probes/isolation.json"))
    rewrite.add_argument("--model", default=str(DEFAULT_MODEL))
    rewrite.add_argument("--calibration-list", default=str(DEFAULT_CALIBRATION))
    rewrite.add_argument("--output")
    partition = subcommands.add_parser("partition", help="构建 cut 两侧的双 context 备用分区")
    partition.add_argument("--variant", required=True)
    partition.add_argument("--cut-node", type=int, required=True)
    partition.add_argument("--serial")
    partition.add_argument("--model", default=str(DEFAULT_MODEL))
    partition.add_argument("--calibration-list", default=str(DEFAULT_CALIBRATION))
    partition.add_argument("--output-root", default=str(DEBUG_ROOT))
    partition.add_argument("--optimization-level", type=int, default=2)
    partition.add_argument("--vtcm-mb", type=int, default=4)
    partition.add_argument("--dlbc", action="store_true")
    return parser


def _rewrite_command(arguments: argparse.Namespace) -> int:
    isolation_path = Path(arguments.isolation)
    isolation = json.loads(isolation_path.read_text(encoding="utf-8"))
    selection = select_rewrite(isolation)
    record_path = isolation_path.parent / "rewrite.json"
    print(json.dumps(selection, ensure_ascii=False, sort_keys=True))
    if selection["status"] != REWRITE_SELECTED:
        write_json_atomic(record_path, selection)
        return 0
    try:
        result = apply_semantic_rewrite(
            Path(arguments.model),
            isolation,
            Path(arguments.output)
            if arguments.output
            else isolation_path.parent / "rewrite" / "rewrite.onnx",
            input_list=Path(arguments.calibration_list),
        )
    except Exception as exc:
        # apply 失败必须原子改写为 apply_failed，不能留下"selected 但没产出"的假状态。
        write_json_atomic(
            record_path,
            selection | {
                "status": "apply_failed",
                "reason": f"{type(exc).__name__}: {exc}",
            },
        )
        raise
    write_json_atomic(
        record_path,
        selection | {
            "output_sha256": result.output_sha256,
            "changed_nodes": list(result.changed_nodes),
        },
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


def _partition_command(arguments: argparse.Namespace) -> int:
    output_root = Path(arguments.output_root)
    artifact = _load_variant_artifact(arguments.variant, output_root)
    toolchain = _resolve_toolchain(artifact)
    stages = json.loads(
        (output_root / "probes/stages.json").read_text(encoding="utf-8")
    )
    cut_row = next(
        (
            row
            for row in stages.get("cuts") or ()
            if int(row["node_index"]) == arguments.cut_node
        ),
        None,
    )
    if cut_row is None:
        raise ValueError(f"stages.json 里没有节点 {arguments.cut_node} 的 cut")
    cut = TensorCut(
        int(cut_row["node_index"]),
        str(cut_row["tensor_name"]),
        tuple(int(dim) for dim in cut_row["shape"]),
        str(cut_row["dtype"]),
    )
    variant = BuildVariant(
        toolchain,
        arguments.optimization_level,
        arguments.vtcm_mb,
        arguments.dlbc,
        str(artifact.metadata.graph_name) if artifact.metadata else "campplus",
    )
    isolation_path = output_root / "probes" / "isolation.json"
    isolation = (
        json.loads(isolation_path.read_text(encoding="utf-8"))
        if isolation_path.is_file()
        else None
    )
    plan = build_partition(
        Path(arguments.model),
        cut,
        variant,
        output_root / "probes" / f"partition-{cut.node_index:04d}",
        input_list=Path(arguments.calibration_list),
        serial=arguments.serial,
        isolation=isolation,
    )
    print(json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "rewrite":
        return _rewrite_command(arguments)
    if arguments.command == "partition":
        return _partition_command(arguments)
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
    print(json.dumps(payload["rewrite"], ensure_ascii=False, sort_keys=True))
    return 0 if not payload["parity_failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
