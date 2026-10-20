"""CAM++ W8A16 embedding parity 与任务准确率门禁。

口径（2026-10-20）：

- 真机至今没有任何一次成功产出 192 维 embedding（全部 `ssr`/`timeout`）。
  因此本模块的入口在缺少通过证据时只写 `device_unavailable`，不计算、
  不落盘任何 EER/Top-1/ARI 数字；
- parity 门禁要求 paired cosine median `>= 0.995` 且 p01 `>= 0.980`；
  门禁失败仍完整写出 parity 指标，但阻断阈值重标定与产品准入；
- W8A16 输出必须按 context metadata 的 scale/offset 反量化回 FP32，
  再 L2 归一化后与 FP32 基准比较；`mean_l2`/`p95_l2` 是逐条配对向量的
  欧氏距离，用来抓 dequant 比例错误（cosine 对整体缩放不敏感）；
- 准确率只认 `status == "pass"` 且 `finite`、`output_count == 192` 的
  真机运行结果；manifest 未记录 `w8a16_provenance.device_runs` 时直接
  `DeviceUnavailableError`；
- 主库测试环境没有 numpy：numpy 一律延迟导入，模块导入本身保持纯 stdlib。

    python -m scripts.speaker_qnn.benchmark --root <evidence-root> --manifest <manifest.json>
    python -m scripts.speaker_qnn.benchmark extract --spec <spec.json> --output-dir <embeddings>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .contracts import (
    SCHEMA_VERSION,
    load_context_metadata,
    validate_sm8845_context,
    write_json_atomic,
)

if TYPE_CHECKING:  # 主库 discover 环境没有 numpy
    import numpy as np

REPO = Path(__file__).resolve().parents[2]
DEBUG_ROOT = REPO / "var/speaker-benchmark/qnn/campplus-htp-debug"
DEFAULT_EVIDENCE_ROOT = DEBUG_ROOT
DEFAULT_MANIFEST = REPO / "var/speaker-benchmark/manifest.json"

EMBEDDING_DIM = 192
PARITY_MEDIAN_MIN = 0.995
PARITY_P01_MIN = 0.980
PARITY_P01_PERCENTILE = 1.0
PARITY_P95_PERCENTILE = 95.0
REQUIRED_ENROLLMENT_CLIPS = 3
REFERENCE_CONDITION = "clean-6s"

STATUS_PASS = "pass"
STATUS_GATE_FAILED = "gate_failed"
STATUS_INCOMPLETE = "incomplete"
STATUS_DEVICE_UNAVAILABLE = "device_unavailable"

EXTRACTION_KIND = "campplus_embedding_extraction"
EXTRACTION_FILE = "extraction.json"

# info.json 的 dataType → 原始输出读取 dtype。qnn-net-run 的
# `--use_native_output_files` 按 context dtype 落盘，量化输出必须按此读，
# 不能一律当 float32。
QNN_DTYPE_TO_NUMPY = {
    "QNN_DATATYPE_FLOAT_32": "<f4",
    "QNN_DATATYPE_FLOAT_16": "<f2",
    "QNN_DATATYPE_FIXED_POINT_16": "<i2",
    "QNN_DATATYPE_UFIXED_POINT_16": "<u2",
    "QNN_DATATYPE_FIXED_POINT_8": "i1",
    "QNN_DATATYPE_UFIXED_POINT_8": "u1",
    "QNN_DATATYPE_INT_32": "<i4",
    "QNN_DATATYPE_UINT_32": "<u4",
}

REUSED_FP32_THRESHOLD = "reused_fp32_threshold"
RECALIBRATED_W8A16_THRESHOLD = "recalibrated_w8a16_threshold"
THRESHOLD_SOURCES = (REUSED_FP32_THRESHOLD, RECALIBRATED_W8A16_THRESHOLD)

SPEED_MATRIX_ACTION = "speed_matrix"
BLOCKED_ACTIONS = (
    "accuracy_evaluation",
    "threshold_recalibration",
    "online_clustering",
    SPEED_MATRIX_ACTION,
)
PENDING_ACTIONS = (
    "首次成功门禁：同一真实输入连续 30 次、退出码全为 0、无 SSR、无 FastRPC 超时、每次 192 个有限值",
    "用同一波形/FBank/裁剪顺序提取 paired FP32 与 W8A16 embedding",
    "在 20 人 6/3/2/1s 与 ESC-50 10/0dB 矩阵上计算 EER、Top-1、ARI 与簇数",
    "重标定 W8A16 阈值并重算在线聚类",
)
TASK_MATRIX = ("clean-6s", "clean-3s", "clean-2s", "clean-1s", "esc50-10db-3s", "esc50-0db-3s")


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - 主库环境走 skip
        raise RuntimeError(
            "benchmark 数值路径需要 numpy；laos 主库零依赖环境不提供，请用 benchmark venv"
        ) from exc
    return np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DeviceUnavailableError(RuntimeError):
    """没有可信的真机 embedding 证据时禁止计算任务准确率。"""

    status = STATUS_DEVICE_UNAVAILABLE

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "reason": self.reason}


@dataclass(frozen=True)
class EmbeddingParity:
    """paired FP32/W8A16 embedding 的逐条统计量。"""

    median_cosine: float
    p01_cosine: float
    minimum_cosine: float
    mean_l2: float
    p95_l2: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateResult:
    """embedding 门禁判定；失败时仍携带完整 parity 指标。"""

    passed: bool
    reason: str
    parity: EmbeddingParity
    median_min: float
    p01_min: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "median_min": self.median_min,
            "p01_min": self.p01_min,
            "parity": self.parity.to_dict(),
        }


@dataclass(frozen=True)
class AccuracyMetrics:
    """W8A16 候选在同一阈值来源下的任务指标；每条都是实算值。"""

    eer: float
    top1: float
    fixed_k_ari: float
    online_ari: float
    cluster_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_matrix(value: Any, embedding_dim: int, name: str) -> "np.ndarray":
    """把输入归一成 (N, D) float64；行未对齐/非有限都在这里拒绝。"""
    np = _require_numpy()
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError(f"{name} 必须是 (N, {embedding_dim}) 二维数组，实际 shape={array.shape}")
    if array.shape[0] == 0:
        raise ValueError(f"{name} 没有任何行（缺输出）")
    if array.shape[1] != int(embedding_dim):
        raise ValueError(
            f"{name} 维度必须是 {embedding_dim}，实际 {array.shape[1]}"
        )
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} 含非有限值（NaN/Inf），不得参与比较")
    return array


def dequantize_embedding(
    raw: Any,
    *,
    scale: Any,
    offset: Any,
    embedding_dim: int = EMBEDDING_DIM,
) -> "np.ndarray":
    """按 QNN 量化编码反量化：`real = (raw - offset) * scale`。

    scale 可为标量或逐通道一维数组；scale 必须有限且为正，否则拒绝。
    返回 `(N, embedding_dim)` float32，尚未 L2 归一化。
    """
    np = _require_numpy()
    array = np.asarray(raw)
    if array.ndim < 1 or array.size == 0:
        raise ValueError("raw 输出为空，无法反量化")
    if array.shape[-1] != int(embedding_dim):
        raise ValueError(
            f"raw 最后一维必须是 {embedding_dim}，实际 {array.shape[-1]}"
        )
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.floating)
    ):
        raise ValueError(f"raw dtype 不支持：{array.dtype}")
    scale_array = np.asarray(scale, dtype=np.float64)
    offset_array = np.asarray(offset, dtype=np.float64)
    for label, values in (("scale", scale_array), ("offset", offset_array)):
        if values.ndim > 1:
            raise ValueError(f"{label} 只允许标量或逐通道一维数组")
        if not np.all(np.isfinite(values)):
            raise ValueError(f"{label} 含非有限值")
    if np.any(scale_array <= 0):
        raise ValueError(f"scale 必须为正，实际 {scale_array.tolist()}")
    values = (array.astype(np.float64) - offset_array) * scale_array
    if not np.all(np.isfinite(values)):
        raise ValueError("反量化结果含非有限值")
    return values.reshape(-1, int(embedding_dim)).astype(np.float32)


def l2_normalize(
    embeddings: Any, *, embedding_dim: int = EMBEDDING_DIM
) -> "np.ndarray":
    """逐行 L2 归一化；零向量没有方向，直接拒绝。"""
    np = _require_numpy()
    matrix = _as_matrix(embeddings, embedding_dim, "embeddings")
    norms = np.linalg.norm(matrix, axis=1)
    zero_rows = np.flatnonzero(norms == 0.0)
    if zero_rows.size:
        raise ValueError(f"第 {zero_rows.tolist()} 行是零向量，无法归一化或比较")
    return matrix / norms[:, None]


def qnn_dtype_numpy(data_type: str) -> str:
    """把 info.json 的 dataType 映射成 numpy 读取 dtype。"""
    code = QNN_DTYPE_TO_NUMPY.get(str(data_type))
    if code is None:
        raise ValueError(f"不支持的 QNN 输出 dtype：{data_type!r}")
    return code


def qnn_dtype_itemsize(data_type: str) -> int:
    """单元素字节数，供 device run 输出字节校验使用。"""
    np = _require_numpy()
    return int(np.dtype(qnn_dtype_numpy(data_type)).itemsize)


def _read_raw_output(
    raw_path: Path, metadata: Any, embedding_dim: int
) -> "np.ndarray":
    """按 metadata 的 dtype 读设备原始输出，并校验元素个数。"""
    np = _require_numpy()
    path = Path(raw_path)
    if not path.is_file():
        raise ValueError(f"原始输出不存在：{path}")
    data_type = getattr(metadata, "output_data_type", None)
    if not data_type:
        raise ValueError("context metadata 缺少 output_data_type，无法读取原始输出")
    data = np.fromfile(path, dtype=qnn_dtype_numpy(data_type))
    shape = tuple(getattr(metadata, "output_shape", ()) or ())
    expected = math.prod(shape) if shape else int(embedding_dim)
    if int(expected) != int(embedding_dim) or data.size != int(embedding_dim):
        raise ValueError(
            f"原始输出应有 {embedding_dim} 个元素，实际 {data.size}（{path}）"
        )
    return data


def read_device_output(
    raw_path: Path, metadata: Any, *, embedding_dim: int = EMBEDDING_DIM
) -> "np.ndarray":
    """读设备原始输出：量化则反量化，FP32 直接读，最后逐行 L2 归一化。"""
    np = _require_numpy()
    data = _read_raw_output(raw_path, metadata, embedding_dim)
    scale = getattr(metadata, "output_scale", None)
    offset = getattr(metadata, "output_offset", None)
    if scale is not None and offset is not None:
        values = dequantize_embedding(
            data, scale=scale, offset=offset, embedding_dim=embedding_dim
        )
    elif np.issubdtype(data.dtype, np.floating):
        values = data.astype(np.float32).reshape(1, int(embedding_dim))
    else:
        raise ValueError("量化输出缺少 scale/offset，无法反量化")
    return l2_normalize(values, embedding_dim=embedding_dim)


def dequantize_device_output(
    raw_path: Path, metadata: Any, *, embedding_dim: int = EMBEDDING_DIM
) -> "np.ndarray":
    """按 context metadata 的 scale/offset 反量化设备输出并 L2 归一化。"""
    if getattr(metadata, "output_scale", None) is None or getattr(
        metadata, "output_offset", None
    ) is None:
        raise ValueError("context metadata 没有输出量化参数（scale/offset），无法反量化")
    return read_device_output(raw_path, metadata, embedding_dim=embedding_dim)


def _item_ids_sha256(item_ids: Sequence[str]) -> str:
    """item_id 顺序的摘要：把 manifest 与 embedding 文件钉在一起。"""
    payload = "\n".join(str(value) for value in item_ids).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def evaluate_embedding_parity(
    fp32: Any, w8a16: Any, *, embedding_dim: int = EMBEDDING_DIM
) -> EmbeddingParity:
    """逐条比较 paired embedding；行数/顺序不一致必须拒绝。"""
    np = _require_numpy()
    reference = _as_matrix(fp32, embedding_dim, "fp32 embedding")
    candidate = _as_matrix(w8a16, embedding_dim, "w8a16 embedding")
    if reference.shape != candidate.shape:
        raise ValueError(
            f"fp32/w8a16 行未对齐：{reference.shape} != {candidate.shape}"
        )
    reference_norms = np.linalg.norm(reference, axis=1)
    candidate_norms = np.linalg.norm(candidate, axis=1)
    zero_rows = np.flatnonzero((reference_norms == 0.0) | (candidate_norms == 0.0))
    if zero_rows.size:
        raise ValueError(f"第 {zero_rows.tolist()} 行是零向量，cosine 无定义")
    cosines = np.sum(reference * candidate, axis=1) / (reference_norms * candidate_norms)
    cosines = np.clip(cosines, -1.0, 1.0)
    distances = np.linalg.norm(reference - candidate, axis=1)
    return EmbeddingParity(
        median_cosine=float(np.median(cosines)),
        p01_cosine=float(np.percentile(cosines, PARITY_P01_PERCENTILE)),
        minimum_cosine=float(np.min(cosines)),
        mean_l2=float(np.mean(distances)),
        p95_l2=float(np.percentile(distances, PARITY_P95_PERCENTILE)),
    )


def embedding_gate(
    parity: EmbeddingParity,
    *,
    median_min: float = PARITY_MEDIAN_MIN,
    p01_min: float = PARITY_P01_MIN,
) -> GateResult:
    """median/p01 双门禁；minimum 只报告不设门槛（p01 已覆盖尾部）。"""
    values = (
        parity.median_cosine,
        parity.p01_cosine,
        parity.minimum_cosine,
        parity.mean_l2,
        parity.p95_l2,
    )
    if not all(math.isfinite(value) for value in values):
        return GateResult(
            passed=False,
            reason="parity 指标含非有限值，门禁失败",
            parity=parity,
            median_min=median_min,
            p01_min=p01_min,
        )
    passed = parity.median_cosine >= median_min and parity.p01_cosine >= p01_min
    reason = (
        f"median cosine={parity.median_cosine:.6f}（要求 >= {median_min}）、"
        f"p01 cosine={parity.p01_cosine:.6f}（要求 >= {p01_min}）"
    )
    if passed:
        reason = f"达到 W8A16 embedding 门禁：{reason}"
    else:
        reason = f"未达 W8A16 embedding 门禁：{reason}"
    return GateResult(
        passed=passed,
        reason=reason,
        parity=parity,
        median_min=median_min,
        p01_min=p01_min,
    )


def _labels_array(labels: Any) -> "np.ndarray":
    np = _require_numpy()
    array = np.asarray(list(labels) if not isinstance(labels, np.ndarray) else labels)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("labels 必须是一维非空序列")
    return array


def _speaker_ordinals(labels: Sequence[Any]) -> list[int]:
    """每条样本在自己说话人内的序号，用于构造跨说话人的同序号配对。"""
    seen: dict[Any, int] = {}
    ordinals: list[int] = []
    for label in labels:
        ordinals.append(seen.get(label, 0))
        seen[label] = ordinals[-1] + 1
    return ordinals


def verification_pairs(
    embeddings: Any, labels: Any, *, embedding_dim: int = EMBEDDING_DIM
) -> tuple["np.ndarray", "np.ndarray"]:
    """与 FP32 基准一致：同说话人全配对；异说话人只配同序号 utterance。"""
    np = _require_numpy()
    matrix = l2_normalize(embeddings, embedding_dim=embedding_dim)
    label_array = _labels_array(labels)
    if len(matrix) != len(label_array):
        raise ValueError(
            f"embedding 行数 {len(matrix)} 与标签数 {len(label_array)} 不一致"
        )
    ordinals = _speaker_ordinals(label_array.tolist())
    same: list[float] = []
    different: list[float] = []
    for left in range(len(label_array)):
        for right in range(left + 1, len(label_array)):
            score = float(matrix[left] @ matrix[right])
            if label_array[left] == label_array[right]:
                same.append(score)
            elif ordinals[left] == ordinals[right]:
                different.append(score)
    if not same or not different:
        raise ValueError("配对集为空：至少要两个说话人且每人多条样本")
    return np.asarray(same), np.asarray(different)


def eer_threshold(same: Any, different: Any) -> tuple[float, float]:
    """返回 (EER, 阈值)；阈值语义为 `score >= threshold` 判为同一人。"""
    np = _require_numpy()
    genuine = np.asarray(same, dtype=np.float64).ravel()
    impostor = np.asarray(different, dtype=np.float64).ravel()
    if genuine.size == 0 or impostor.size == 0:
        raise ValueError("EER 需要非空的同人/异人对")
    if not (np.all(np.isfinite(genuine)) and np.all(np.isfinite(impostor))):
        raise ValueError("EER 输入含非有限分数")
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(genuine.size), np.zeros(impostor.size)])
    order = np.argsort(-scores, kind="stable")
    sorted_scores = scores[order]
    sorted_labels = labels[order]
    true_positive = np.cumsum(sorted_labels)
    false_positive = np.cumsum(1.0 - sorted_labels)
    false_negative_rate = (genuine.size - true_positive) / genuine.size
    false_positive_rate = false_positive / impostor.size
    # 只在分数边界处评估，避免把同一阈值的中间状态当成候选
    boundary = np.r_[sorted_scores[1:] != sorted_scores[:-1], True]
    fnr = false_negative_rate[boundary]
    fpr = false_positive_rate[boundary]
    thresholds = sorted_scores[boundary]
    index = int(np.argmin(np.abs(fnr - fpr)))
    eer = float((fnr[index] + fpr[index]) / 2.0)
    return eer, float(thresholds[index])


def identification_top1(
    embeddings: Any,
    labels: Any,
    *,
    enrollment: int = REQUIRED_ENROLLMENT_CLIPS,
    embedding_dim: int = EMBEDDING_DIM,
) -> float:
    """known-identity Top-1：每人前 `enrollment` 条建模板，其余作为查询。"""
    np = _require_numpy()
    matrix = l2_normalize(embeddings, embedding_dim=embedding_dim)
    label_array = _labels_array(labels)
    if len(matrix) != len(label_array):
        raise ValueError(
            f"embedding 行数 {len(matrix)} 与标签数 {len(label_array)} 不一致"
        )
    speakers = sorted(set(label_array.tolist()))
    templates: list["np.ndarray"] = []
    queries: list["np.ndarray"] = []
    query_labels: list[Any] = []
    for speaker in speakers:
        indices = np.flatnonzero(label_array == speaker)
        if len(indices) <= enrollment:
            raise ValueError(
                f"说话人 {speaker} 只有 {len(indices)} 条，Top-1 需要多于 {enrollment} 条"
            )
        template = matrix[indices[:enrollment]].mean(axis=0)
        norm = float(np.linalg.norm(template))
        if norm == 0.0:
            raise ValueError(f"说话人 {speaker} 的模板是零向量")
        templates.append(template / norm)
        queries.append(matrix[indices[enrollment:]])
        query_labels.extend([speaker] * int(len(indices) - enrollment))
    scores = np.concatenate(queries) @ np.asarray(templates).T
    predicted = np.asarray(speakers)[np.argmax(scores, axis=1)]
    return float(np.mean(predicted == np.asarray(query_labels)))


def agglomerative_fixed_k(
    embeddings: Any, k: int, *, embedding_dim: int = EMBEDDING_DIM
) -> "np.ndarray":
    """average-linkage + cosine 距离的固定簇数层次聚类（确定性 tie-break）。"""
    np = _require_numpy()
    matrix = l2_normalize(embeddings, embedding_dim=embedding_dim)
    count = len(matrix)
    if k <= 0 or k > count:
        raise ValueError(f"k 必须在 1..{count} 之间，实际 {k}")
    distance = 1.0 - matrix @ matrix.T
    np.fill_diagonal(distance, 0.0)
    sizes = np.ones(count, dtype=np.float64)
    active = list(range(count))
    members: dict[int, list[int]] = {index: [index] for index in range(count)}
    while len(active) > k:
        subset = distance[np.ix_(active, active)]
        masked = np.where(np.eye(len(active), dtype=bool), np.inf, subset)
        position = int(np.argmin(masked))
        row, column = divmod(position, len(active))
        if row > column:
            row, column = column, row
        left, right = active[row], active[column]
        total = sizes[left] + sizes[right]
        for other in active:
            if other in (left, right):
                continue
            merged = (
                sizes[left] * distance[left, other]
                + sizes[right] * distance[right, other]
            ) / total
            distance[left, other] = distance[other, left] = merged
        sizes[left] = total
        members[left].extend(members.pop(right))
        active.remove(right)
    result = np.empty(count, dtype=np.int64)
    for label, key in enumerate(sorted(members)):
        result[members[key]] = label
    return result


def _same_partition(first: Sequence[Any], second: Sequence[Any]) -> bool:
    forward: dict[Any, Any] = {}
    backward: dict[Any, Any] = {}
    for left, right in zip(first, second):
        if forward.setdefault(left, right) != right:
            return False
        if backward.setdefault(right, left) != left:
            return False
    return True


def adjusted_rand_index(first: Any, second: Any) -> float:
    """ARI（与 sklearn adjusted_rand_score 同定义），不引第三方依赖。"""
    np = _require_numpy()
    left = _labels_array(first)
    right = _labels_array(second)
    if len(left) != len(right):
        raise ValueError("ARI 的两份划分长度不一致")
    _, index_left = np.unique(left, return_inverse=True)
    _, index_right = np.unique(right, return_inverse=True)
    contingency = np.zeros(
        (int(index_left.max()) + 1, int(index_right.max()) + 1), dtype=np.float64
    )
    np.add.at(contingency, (index_left, index_right), 1.0)

    def combinations(values: "np.ndarray") -> float:
        return float(np.sum(values * (values - 1.0) / 2.0))

    sum_cells = combinations(contingency)
    sum_left = combinations(contingency.sum(axis=1))
    sum_right = combinations(contingency.sum(axis=0))
    total = float(len(left) * (len(left) - 1) / 2.0)
    expected = sum_left * sum_right / total if total else 0.0
    maximum = (sum_left + sum_right) / 2.0
    if maximum == expected:
        return 1.0 if _same_partition(left.tolist(), right.tolist()) else 0.0
    return float((sum_cells - expected) / (maximum - expected))


def round_robin_order(labels: Any) -> tuple[int, ...]:
    """按说话人 ID 排序后轮转抽取：到达顺序与数组分块顺序无关。"""
    label_array = _labels_array(labels)
    values = label_array.tolist()
    speakers = sorted(set(values))
    indices = {
        speaker: [index for index, value in enumerate(values) if value == speaker]
        for speaker in speakers
    }
    depth = max(len(group) for group in indices.values())
    return tuple(
        indices[speaker][round_index]
        for round_index in range(depth)
        for speaker in speakers
        if round_index < len(indices[speaker])
    )


def online_cluster(
    embeddings: Any,
    labels: Any,
    threshold: float,
    *,
    order: Sequence[int] | None = None,
    embedding_dim: int = EMBEDDING_DIM,
) -> tuple[tuple[int, ...], int]:
    """在线单遍聚类：`score >= threshold` 归入最近簇，否则新建。"""
    np = _require_numpy()
    matrix = l2_normalize(embeddings, embedding_dim=embedding_dim)
    label_array = _labels_array(labels)
    if len(matrix) != len(label_array):
        raise ValueError("embedding 行数与标签数不一致")
    if not math.isfinite(float(threshold)):
        raise ValueError(f"threshold 必须是有限值，实际 {threshold}")
    arrival = (
        round_robin_order(label_array)
        if order is None
        else tuple(int(value) for value in order)
    )
    if sorted(arrival) != list(range(len(matrix))):
        raise ValueError("order 必须是 0..N-1 的排列")
    centroids: list["np.ndarray"] = []
    counts: list[int] = []
    predicted: list[int] = []
    for index in arrival:
        vector = matrix[index]
        if not centroids:
            centroids.append(vector.copy())
            counts.append(1)
            predicted.append(0)
            continue
        scores = np.asarray(centroids) @ vector
        best = int(np.argmax(scores))
        if float(scores[best]) >= float(threshold):
            counts[best] += 1
            merged = centroids[best] * (counts[best] - 1) + vector
            centroids[best] = merged / np.linalg.norm(merged)
            predicted.append(best)
        else:
            centroids.append(vector.copy())
            counts.append(1)
            predicted.append(len(centroids) - 1)
    return tuple(predicted), len(centroids)


def benchmark_items(payload: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """从 manifest 取 (item_id, speaker) 顺序表，两种 schema 都接受。

    - 既有 FP32 基准 `manifest.json`：`speakers[].files[]`，按 speaker 顺序
      展平（与 `results/*-embeddings.npz` 的 `utterances`/`labels` 一致）；
    - paired manifest：显式 `items[{item_id, speaker}]`。
    """
    entries = payload.get("items")
    item_ids: list[str] = []
    speakers: list[str] = []
    if isinstance(entries, list) and entries:
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("items 每条必须是对象")
            item_id = entry.get("item_id")
            speaker = entry.get("speaker")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError("items 缺少非空 item_id")
            if not isinstance(speaker, str) or not speaker:
                raise ValueError(f"item {item_id} 缺少 speaker")
            item_ids.append(item_id)
            speakers.append(speaker)
    else:
        groups = payload.get("speakers")
        if not isinstance(groups, list) or not groups:
            raise ValueError("manifest 必须提供 items 或 speakers")
        for group in groups:
            if not isinstance(group, Mapping):
                raise ValueError("speakers 每条必须是对象")
            speaker = group.get("speaker")
            files = group.get("files")
            if not isinstance(speaker, str) or not speaker:
                raise ValueError("speakers 缺少非空 speaker")
            if not isinstance(files, list) or not files:
                raise ValueError(f"说话人 {speaker} 没有文件列表")
            for relative in files:
                if not isinstance(relative, str) or not relative:
                    raise ValueError(f"说话人 {speaker} 的 file 不是非空字符串")
                item_ids.append(relative)
                speakers.append(speaker)
    if not item_ids:
        raise ValueError("manifest 没有任何条目")
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("item_id 重复，无法保证行对齐")
    if len(set(speakers)) < 2:
        raise ValueError("至少需要两个说话人才能计算 EER/ARI")
    return tuple(item_ids), tuple(speakers)


def _load_manifest_json(path: Path) -> dict[str, Any]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 manifest: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"manifest 必须是 JSON 对象：{path}")
    return payload


def _resolve_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} 必须是非空路径字符串")
    path = Path(value)
    return path if path.is_absolute() else (Path(base) / path).resolve()


def _is_passing_device_result(payload: Mapping[str, Any]) -> bool:
    """唯一 pass 谓词：status/finite/192 三件套。"""
    return (
        payload.get("status") == STATUS_PASS
        and bool(payload.get("finite"))
        and int(payload.get("output_count") or 0) == EMBEDDING_DIM
    )


def require_device_evidence(
    manifest_path: Path,
    payload: Mapping[str, Any],
    *,
    embedding_dim: int = EMBEDDING_DIM,
) -> tuple[dict[str, Any], ...]:
    """只接受 `pass`、`finite`、192 个输出的真机运行作为准确率证据。

    除 result.json 自述外，还核对 `output_path` 存在、字节数等于
    `192 × dtype_size`、以及与抽取记录一致的 SHA-256；provenance 必须
    带 variant_id/context_sha256/output_dtype/item_ids_sha256。
    """
    provenance = payload.get("w8a16_provenance")
    if not isinstance(provenance, Mapping):
        raise DeviceUnavailableError(
            "manifest 未记录真机 W8A16 产出（w8a16_provenance 缺失），拒绝计算准确率"
        )
    for key in ("variant_id", "context_sha256", "output_dtype"):
        value = provenance.get(key)
        if not isinstance(value, str) or not value:
            raise DeviceUnavailableError(
                f"w8a16_provenance 缺少 {key}，embedding 无法与 build/run 对账"
            )
    digest = provenance.get("item_ids_sha256")
    if not isinstance(digest, str) or not digest:
        raise ValueError(
            "w8a16_provenance 缺少 item_ids_sha256，embedding 与 manifest 无法对账"
        )
    itemsize = qnn_dtype_itemsize(provenance["output_dtype"])
    runs = provenance.get("device_runs")
    if not isinstance(runs, (list, tuple)) or not runs:
        raise DeviceUnavailableError("w8a16_provenance.device_runs 为空，没有真机 embedding 证据")
    base = Path(manifest_path).parent
    records: list[dict[str, Any]] = []
    for entry in runs:
        expected_raw: Any = None
        expected_sha: Any = None
        if isinstance(entry, Mapping):
            result_value = entry.get("result")
            expected_raw = entry.get("raw")
            expected_sha = entry.get("raw_sha256")
        else:
            result_value = entry
        result_path = _resolve_path(base, result_value, "device_runs 条目")
        if not result_path.is_file():
            raise DeviceUnavailableError(f"真机运行证据缺失：{result_value}")
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeviceUnavailableError(f"真机运行证据不可读：{result_value}: {exc}") from exc
        if result.get("status") != STATUS_PASS:
            raise DeviceUnavailableError(
                f"真机运行 {result_value} 状态为 {result.get('status')}，不是 pass，"
                "不得据此计算准确率"
            )
        if not _is_passing_device_result(result):
            raise DeviceUnavailableError(
                f"真机运行 {result_value} 没有 {EMBEDDING_DIM} 个有限输出，"
                "不得据此计算准确率"
            )
        output_value = result.get("output_path")
        if not isinstance(output_value, str) or not output_value:
            raise DeviceUnavailableError(
                f"真机运行 {result_value} 没有 output_path，无法把 embedding 绑到原始输出"
            )
        output_path = _resolve_path(result_path.parent, output_value, "output_path")
        if not output_path.is_file():
            raise DeviceUnavailableError(f"真机运行的 output 文件缺失：{output_value}")
        expected_bytes = int(embedding_dim) * itemsize
        actual_bytes = output_path.stat().st_size
        if actual_bytes != expected_bytes:
            raise DeviceUnavailableError(
                f"真机运行的 output 字节数不符：期望 {expected_bytes} 字节"
                f"（{embedding_dim} × {itemsize}），实际 {actual_bytes}（{output_path}）"
            )
        actual_sha = _sha256(output_path)
        if expected_sha is not None and str(expected_sha) != actual_sha:
            raise ValueError(
                f"真机 output 的 sha256 与抽取记录不一致：{output_path}"
            )
        if expected_raw is not None:
            raw_path = _resolve_path(base, expected_raw, "device_runs.raw")
            if raw_path.resolve() != output_path.resolve():
                raise ValueError(
                    f"抽取记录 raw 与真机 output_path 不一致："
                    f"{expected_raw} != {output_value}"
                )
        records.append(
            {
                "result": str(result_path),
                "output_path": str(output_path),
                "output_bytes": actual_bytes,
                "output_sha256": actual_sha,
            }
        )
    return tuple(records)


def evaluate_accuracy(
    fp32: Any,
    w8a16: Any,
    manifest: Path,
    *,
    reused_threshold: float | None = None,
    embedding_dim: int = EMBEDDING_DIM,
    w8a16_source: Path | None = None,
) -> dict[str, AccuracyMetrics]:
    """paired 准确率：同一批 W8A16 embedding，跑两种阈值来源。

    返回键是阈值来源（`reused_fp32_threshold` / `recalibrated_w8a16_threshold`）；
    EER/Top-1/fixed-k ARI 与阈值无关，因此两项共享，只有在线聚类的 ARI
    和簇数随阈值变化。缺真机证据、provenance 与 manifest/embedding 文件
    对不上时拒绝计算。
    """
    np = _require_numpy()
    manifest_path = Path(manifest)
    payload = _load_manifest_json(manifest_path)
    item_ids, speakers = benchmark_items(payload)
    require_device_evidence(manifest_path, payload, embedding_dim=embedding_dim)
    provenance = payload["w8a16_provenance"]
    if provenance.get("item_ids_sha256") != _item_ids_sha256(item_ids):
        raise ValueError("w8a16_provenance.item_ids_sha256 与 manifest 不一致")
    if w8a16_source is not None:
        embeddings_record = provenance.get("embeddings")
        record = (
            embeddings_record.get("w8a16")
            if isinstance(embeddings_record, Mapping)
            else None
        )
        expected_sha = record.get("sha256") if isinstance(record, Mapping) else None
        if not isinstance(expected_sha, str) or expected_sha != _sha256(w8a16_source):
            raise ValueError("W8A16 embedding 文件的 sha256 与 provenance 不一致")
    labels = np.asarray(speakers)
    reference = l2_normalize(fp32, embedding_dim=embedding_dim)
    candidate = l2_normalize(w8a16, embedding_dim=embedding_dim)
    if len(reference) != len(labels) or len(candidate) != len(labels):
        raise ValueError(
            f"行未对齐：manifest {len(item_ids)} 条，fp32 {len(reference)} 行，"
            f"w8a16 {len(candidate)} 行"
        )

    same_fp32, different_fp32 = verification_pairs(
        reference, labels, embedding_dim=embedding_dim
    )
    _, fp32_threshold = eer_threshold(same_fp32, different_fp32)
    same_w8a16, different_w8a16 = verification_pairs(
        candidate, labels, embedding_dim=embedding_dim
    )
    eer, w8a16_threshold = eer_threshold(same_w8a16, different_w8a16)
    top1 = identification_top1(candidate, labels, embedding_dim=embedding_dim)
    speaker_count = len(set(speakers))
    fixed_k = adjusted_rand_index(
        labels, agglomerative_fixed_k(candidate, speaker_count, embedding_dim=embedding_dim)
    )
    reused = fp32_threshold if reused_threshold is None else float(reused_threshold)
    if not math.isfinite(reused):
        raise ValueError(f"reused_threshold 必须是有限值，实际 {reused}")

    arrival = round_robin_order(labels)
    truth = labels[list(arrival)]
    metrics: dict[str, AccuracyMetrics] = {}
    for source, threshold in (
        (REUSED_FP32_THRESHOLD, reused),
        (RECALIBRATED_W8A16_THRESHOLD, w8a16_threshold),
    ):
        predicted, cluster_count = online_cluster(
            candidate, labels, threshold, order=arrival, embedding_dim=embedding_dim
        )
        metrics[source] = AccuracyMetrics(
            eer=float(eer),
            top1=float(top1),
            fixed_k_ari=float(fixed_k),
            online_ari=float(adjusted_rand_index(truth, np.asarray(predicted))),
            cluster_count=int(cluster_count),
        )
    return metrics


def write_embedding_set(
    path: Path, blocks: Mapping[str, Any], item_ids: Sequence[str]
) -> None:
    """按条件块写 paired embedding；item_ids 与行一一对应。"""
    np = _require_numpy()
    ids = [str(value) for value in item_ids]
    if not ids:
        raise ValueError("item_ids 不能为空")
    if not blocks:
        raise ValueError("至少需要一个 embedding 块")
    if "item_ids" in blocks:
        raise ValueError("blocks 不得包含保留键 item_ids")
    arrays: dict[str, Any] = {}
    for name, block in blocks.items():
        matrix = _as_matrix(block, EMBEDDING_DIM, f"block {name}")
        if len(matrix) != len(ids):
            raise ValueError(
                f"块 {name} 行数 {len(matrix)} 与 item_ids {len(ids)} 不一致"
            )
        arrays[str(name)] = matrix.astype(np.float32)
    arrays["item_ids"] = np.asarray(ids, dtype=str)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def load_embedding_set(path: Path) -> tuple[dict[str, "np.ndarray"], tuple[str, ...]]:
    """读 paired embedding；缺 item_ids、维度不是 192、块行数不齐都拒绝。"""
    np = _require_numpy()
    path = Path(path)
    try:
        archive = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError(f"无法读取 embedding 文件 {path}: {exc}") from exc
    try:
        names = list(archive.files)
        if "item_ids" not in names:
            raise ValueError(f"embedding 文件缺少 item_ids：{path}")
        blocks: dict[str, "np.ndarray"] = {}
        for name in names:
            if name == "item_ids":
                continue
            blocks[name] = _as_matrix(archive[name], EMBEDDING_DIM, f"block {name}")
        if not blocks:
            raise ValueError(f"embedding 文件没有任何条件块：{path}")
        item_ids = tuple(str(value) for value in archive["item_ids"].tolist())
    finally:
        archive.close()
    if not item_ids:
        raise ValueError(f"embedding 文件的 item_ids 为空：{path}")
    for name, block in blocks.items():
        if len(block) != len(item_ids):
            raise ValueError(
                f"块 {name} 行数 {len(block)} 与 item_ids {len(item_ids)} 不一致"
            )
    return blocks, item_ids


def scan_device_evidence(root: Path) -> list[dict[str, Any]]:
    """只读扫描 `device-runs/*/result.json`，不把不可读结果当 pass。"""
    root = Path(root)
    records: list[dict[str, Any]] = []
    for result_path in sorted((root / "device-runs").glob("*/result.json")):
        resolved = str(result_path.resolve())
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            records.append(
                {
                    "path": resolved,
                    "status": "unreadable",
                    "exit_code": None,
                    "output_count": 0,
                    "finite": False,
                    "timeout_ms": None,
                }
            )
            continue
        records.append(
            {
                "path": resolved,
                "status": str(payload.get("status")),
                "exit_code": payload.get("exit_code"),
                "output_count": int(payload.get("output_count") or 0),
                "finite": bool(payload.get("finite")),
                "timeout_ms": payload.get("timeout_ms"),
            }
        )
    return records


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取 {label}: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} 必须是 JSON 对象：{path}")
    return payload


def _load_variant(
    spec_dir: Path, entry: Any, label: str
) -> tuple[str, Path, Path, Any]:
    """解出 spec 里的一个 context 变体并校验 SM8845/V81 门禁。"""
    if not isinstance(entry, Mapping):
        raise ValueError(f"extraction spec 的 {label} 变体必须是对象")
    variant_id = entry.get("variant_id")
    if not isinstance(variant_id, str) or not variant_id:
        raise ValueError(f"extraction spec 的 {label}.variant_id 必须是非空字符串")
    info_path = _resolve_path(spec_dir, entry.get("info_json"), f"{label}.info_json")
    if not info_path.is_file():
        raise ValueError(f"{label} 的 context info.json 不存在：{info_path}")
    context_path = _resolve_path(
        spec_dir, entry.get("context_bin"), f"{label}.context_bin"
    )
    if not context_path.is_file():
        raise ValueError(f"{label} 的 context binary 不存在：{context_path}")
    metadata = load_context_metadata(info_path)
    validate_sm8845_context(metadata)
    if label == "w8a16" and (
        metadata.output_scale is None or metadata.output_offset is None
    ):
        raise ValueError(
            "w8a16 context 没有输出量化参数（scale/offset），无法反量化设备输出"
        )
    return variant_id, info_path, context_path, metadata


def extract_embedding_sets(
    spec: Path, output_dir: Path, *, embedding_dim: int = EMBEDDING_DIM
) -> dict[str, Any]:
    """把设备原始输出 + context info.json 落成 paired `fp32.npz`/`w8a16.npz`。

    spec JSON 结构：

        {"fp32": {variant_id, info_json, context_bin},
         "w8a16": {variant_id, info_json, context_bin},
         "items": [{item_id, condition,
                    "fp32": {"raw": ..., "run": ...},
                    "w8a16": {"raw": ..., "run": ...}}]}

    相对路径按 spec 文件所在目录解析；每个 raw 按 context metadata 的
    dtype/scale/offset 反量化并 L2 归一化。同一条 condition 的 item 顺序
    必须与首条 condition 完全一致（npz 的行与 item_ids 全局对齐）。产物旁
    写 `extraction.json`，记录 context/npz/raw 的 SHA-256 与 item_ids 摘要，
    供门禁把 embedding ↔ build ↔ run 对账。
    """
    np = _require_numpy()
    spec_path = Path(spec)
    spec_dir = spec_path.resolve().parent
    payload = _load_json_object(spec_path, "extraction spec")
    variants = {
        label: _load_variant(spec_dir, payload.get(label), label)
        for label in ("fp32", "w8a16")
    }
    entries = payload.get("items")
    if not isinstance(entries, list) or not entries:
        raise ValueError("extraction spec.items 不能为空")

    conditions: list[str] = []
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("extraction spec.items 每条必须是对象")
        item_id = entry.get("item_id")
        condition = entry.get("condition")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError("extraction spec.items 缺少非空 item_id")
        if not isinstance(condition, str) or not condition:
            raise ValueError(f"item {item_id} 缺少 condition")
        if condition not in grouped:
            conditions.append(condition)
            grouped[condition] = []
        grouped[condition].append((item_id, entry))

    reference = [item_id for item_id, _ in grouped[conditions[0]]]
    if len(set(reference)) != len(reference):
        raise ValueError(f"条件 {conditions[0]} 的 item_id 重复，无法保证行对齐")
    for condition in conditions[1:]:
        ids = [item_id for item_id, _ in grouped[condition]]
        if ids != reference:
            raise ValueError(
                f"条件 {condition} 的 item 顺序与 {conditions[0]} 不一致，"
                "无法保证 embedding 行逐条对齐"
            )

    rows: dict[str, dict[str, list["np.ndarray"]]] = {
        "fp32": {condition: [] for condition in conditions},
        "w8a16": {condition: [] for condition in conditions},
    }
    item_records: list[dict[str, Any]] = []
    for entry in entries:
        condition = str(entry["condition"])
        item_id = str(entry["item_id"])
        record: dict[str, Any] = {"item_id": item_id, "condition": condition}
        for label in ("fp32", "w8a16"):
            output = entry.get(label)
            if not isinstance(output, Mapping):
                raise ValueError(f"{condition}/{item_id} 缺少 {label} 输出")
            raw_path = _resolve_path(spec_dir, output.get("raw"), f"{label}.raw")
            values = read_device_output(
                raw_path, variants[label][3], embedding_dim=embedding_dim
            )
            rows[label][condition].append(values[0])
            run_record: dict[str, Any] = {
                "raw": str(raw_path.resolve()),
                "raw_sha256": _sha256(raw_path),
            }
            if output.get("run") is not None:
                run_path = _resolve_path(spec_dir, output.get("run"), f"{label}.run")
                if not run_path.is_file():
                    raise ValueError(
                        f"{condition}/{item_id} 的 {label}.run 不存在：{run_path}"
                    )
                run_record["run"] = str(run_path.resolve())
            record[label] = run_record
        item_records.append(record)

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    npz_paths = {"fp32": target / "fp32.npz", "w8a16": target / "w8a16.npz"}
    for label in ("fp32", "w8a16"):
        blocks = {
            condition: np.asarray(rows[label][condition], dtype=np.float32)
            for condition in conditions
        }
        write_embedding_set(npz_paths[label], blocks, reference)

    variant_records: dict[str, Any] = {}
    for label, (variant_id, info_path, context_path, metadata) in variants.items():
        variant_records[label] = {
            "variant_id": variant_id,
            "info_json": str(info_path.resolve()),
            "info_json_sha256": _sha256(info_path),
            "context_bin": str(context_path.resolve()),
            "context_sha256": _sha256(context_path),
            "data_type": metadata.output_data_type,
            "quantization_encoding": metadata.output_quant_encoding,
            "scale": metadata.output_scale,
            "offset": metadata.output_offset,
            "embedding_dim": int(embedding_dim),
            "npz": str(npz_paths[label].resolve()),
            "npz_sha256": _sha256(npz_paths[label]),
        }

    record = {
        "schema_version": SCHEMA_VERSION,
        "kind": EXTRACTION_KIND,
        "spec": str(spec_path.resolve()),
        "output_dir": str(target.resolve()),
        "conditions": conditions,
        "item_ids": list(reference),
        "item_ids_sha256": _item_ids_sha256(reference),
        "variants": variant_records,
        "items": item_records,
    }
    write_json_atomic(target / EXTRACTION_FILE, record)
    return record


def _manifest_summary(manifest: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(manifest),
        "sha256": None,
        "speakers": None,
        "items": None,
        "conditions": [],
        "error": None,
    }
    if not manifest.is_file():
        summary["error"] = "manifest 文件不存在"
        return summary
    summary["sha256"] = _sha256(manifest)
    try:
        payload = _load_manifest_json(manifest)
        item_ids, speakers = benchmark_items(payload)
    except ValueError as exc:
        summary["error"] = str(exc)
        return summary
    summary["items"] = len(item_ids)
    summary["speakers"] = len(set(speakers))
    conditions = payload.get("conditions")
    if isinstance(conditions, Mapping):
        summary["conditions"] = [str(key) for key in conditions]
    return summary


def collect_benchmark(
    root: Path = DEFAULT_EVIDENCE_ROOT,
    manifest: Path = DEFAULT_MANIFEST,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    """汇总 paired embedding 证据：缺真机产物只写 `device_unavailable`。"""
    root = Path(root)
    manifest = Path(manifest)
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": "campplus_w8a16_benchmark",
        "status": STATUS_DEVICE_UNAVAILABLE,
        "reason": None,
        "evidence_root": str(root),
        "manifest": _manifest_summary(manifest),
        "task_matrix": list(TASK_MATRIX),
        "embeddings": {"fp32": None, "w8a16": None},
        "provenance": None,
        "device_runs": scan_device_evidence(root),
        "parity": None,
        "gate": None,
        "accuracy": None,
        "threshold_recalibration": "blocked",
        "product_admission": "blocked",
        "blocked_actions": list(BLOCKED_ACTIONS),
        "pending": list(PENDING_ACTIONS),
    }
    embeddings_dir = root / "embeddings"
    fp32_path = embeddings_dir / "fp32.npz"
    w8a16_path = embeddings_dir / "w8a16.npz"
    extraction_path = embeddings_dir / EXTRACTION_FILE
    problems: list[str] = []
    if record["manifest"]["error"]:
        problems.append(f"manifest 不可用：{record['manifest']['error']}")
    for path in (fp32_path, w8a16_path):
        if not path.is_file():
            problems.append(f"缺少 paired embedding 文件：{path}")
    if not extraction_path.is_file():
        problems.append(
            f"缺少 embedding 抽取记录：{extraction_path}（extraction.json）"
        )
    if problems:
        record["reason"] = "；".join(problems)
        if output is not None:
            write_json_atomic(Path(output), record)
        return record

    np = _require_numpy()
    payload = _load_manifest_json(manifest)
    item_ids, speakers = benchmark_items(payload)
    labels = np.asarray(speakers)
    extraction = _load_json_object(extraction_path, "extraction 记录")
    variants = extraction.get("variants")
    if not isinstance(variants, Mapping):
        raise ValueError(f"extraction 记录缺少 variants：{extraction_path}")
    w8a16_variant = variants.get("w8a16")
    if not isinstance(w8a16_variant, Mapping):
        raise ValueError(f"extraction 记录缺少 w8a16 变体：{extraction_path}")
    if w8a16_variant.get("scale") is None or w8a16_variant.get("offset") is None:
        raise ValueError("extraction 记录里的 w8a16 变体缺少量化 scale/offset")
    if extraction.get("item_ids_sha256") != _item_ids_sha256(item_ids):
        raise ValueError("extraction 记录的 item_ids 摘要与 manifest 不一致")
    extracted_ids = tuple(str(value) for value in extraction.get("item_ids") or ())
    if extracted_ids != item_ids:
        raise ValueError("extraction 记录的 item_ids 与 manifest 顺序/内容不一致")
    embedding_sha = {
        "fp32": _sha256(fp32_path),
        "w8a16": _sha256(w8a16_path),
    }
    for label in ("fp32", "w8a16"):
        variant = variants.get(label)
        recorded = variant.get("npz_sha256") if isinstance(variant, Mapping) else None
        if not isinstance(recorded, str) or recorded != embedding_sha[label]:
            raise ValueError(
                f"{label} embedding 文件的 SHA-256 与 extraction 记录不一致"
            )

    device_runs: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    for item in extraction.get("items") or ():
        if not isinstance(item, Mapping):
            continue
        w8a16_output = item.get("w8a16")
        if not isinstance(w8a16_output, Mapping):
            continue
        run_value = w8a16_output.get("run")
        if not isinstance(run_value, str) or not run_value:
            continue
        if run_value in seen_runs:
            continue
        seen_runs.add(run_value)
        entry: dict[str, Any] = {"result": run_value}
        raw_value = w8a16_output.get("raw")
        if (
            isinstance(raw_value, str)
            and raw_value
            and w8a16_output.get("raw_sha256")
        ):
            entry["raw"] = raw_value
            entry["raw_sha256"] = str(w8a16_output["raw_sha256"])
        device_runs.append(entry)

    provenance = {
        "variant_id": w8a16_variant.get("variant_id"),
        "context_sha256": w8a16_variant.get("context_sha256"),
        "info_json_sha256": w8a16_variant.get("info_json_sha256"),
        "output_dtype": w8a16_variant.get("data_type"),
        "output_scale": w8a16_variant.get("scale"),
        "output_offset": w8a16_variant.get("offset"),
        "item_ids_sha256": extraction.get("item_ids_sha256"),
        "embeddings": {
            label: {"path": str(path), "sha256": embedding_sha[label]}
            for label, path in (("fp32", fp32_path), ("w8a16", w8a16_path))
        },
        "device_runs": device_runs,
        "extraction": str(extraction_path.resolve()),
        "extraction_sha256": _sha256(extraction_path),
    }
    try:
        require_device_evidence(extraction_path, {"w8a16_provenance": provenance})
    except DeviceUnavailableError as exc:
        record["reason"] = f"真机证据不可用：{exc.reason}"
        if output is not None:
            write_json_atomic(Path(output), record)
        return record

    record["embeddings"] = {
        "fp32": {"path": str(fp32_path), "sha256": embedding_sha["fp32"]},
        "w8a16": {"path": str(w8a16_path), "sha256": embedding_sha["w8a16"]},
        "item_ids": list(item_ids),
        "item_ids_sha256": extraction.get("item_ids_sha256"),
    }
    record["provenance"] = {
        key: provenance[key]
        for key in (
            "variant_id",
            "context_sha256",
            "info_json_sha256",
            "output_dtype",
            "output_scale",
            "output_offset",
            "item_ids_sha256",
            "extraction",
            "extraction_sha256",
        )
    }
    record["provenance"]["device_runs"] = [entry["result"] for entry in device_runs]

    fp32_blocks, fp32_ids = load_embedding_set(fp32_path)
    w8a16_blocks, w8a16_ids = load_embedding_set(w8a16_path)
    if fp32_ids != item_ids or w8a16_ids != item_ids:
        raise ValueError("embedding item_ids 与 manifest 顺序/内容不一致（行未对齐）")
    if set(fp32_blocks) != set(w8a16_blocks):
        raise ValueError("fp32 与 w8a16 的条件块不一致")
    conditions = [
        str(condition)
        for condition in extraction.get("conditions") or ()
        if str(condition) in fp32_blocks
    ]
    if set(conditions) != set(fp32_blocks):
        raise ValueError("extraction 记录的条件与 embedding 文件的条件块不一致")

    parity: dict[str, Any] = {}
    gate_records: dict[str, Any] = {}
    for condition in conditions:
        value = evaluate_embedding_parity(fp32_blocks[condition], w8a16_blocks[condition])
        gate = embedding_gate(value)
        parity[condition] = value.to_dict()
        gate_records[condition] = gate.to_dict()
    gate_passed = all(item["passed"] for item in gate_records.values())
    record["parity"] = parity
    record["gate"] = {
        "passed": gate_passed,
        "reason": (
            "全部条件通过 W8A16 embedding 门禁"
            if gate_passed
            else "；".join(
                f"{condition}: {item['reason']}"
                for condition, item in gate_records.items()
                if not item["passed"]
            )
        ),
        "median_min": PARITY_MEDIAN_MIN,
        "p01_min": PARITY_P01_MIN,
        "conditions": gate_records,
    }
    if not gate_passed:
        record["status"] = STATUS_GATE_FAILED
        record["reason"] = "parity 门禁失败，准确率、阈值重标定与产品准入均被阻断"
        if output is not None:
            write_json_atomic(Path(output), record)
        return record

    destination = Path(output) if output is not None else root / "benchmark.json"
    paired_path = destination.parent / "benchmark-manifest.json"
    paired_payload = {
        "schema_version": SCHEMA_VERSION,
        "source_manifest": str(manifest),
        "items": [
            {"item_id": item_id, "speaker": speaker}
            for item_id, speaker in zip(item_ids, speakers)
        ],
        "w8a16_provenance": provenance,
    }
    write_json_atomic(paired_path, paired_payload)

    reference_condition = (
        REFERENCE_CONDITION if REFERENCE_CONDITION in conditions else conditions[0]
    )
    same, different = verification_pairs(
        fp32_blocks[reference_condition], labels
    )
    reference_eer, reference_threshold = eer_threshold(same, different)
    record["thresholds"] = {
        "reference_condition": reference_condition,
        "fp32_eer": reference_eer,
        "fp32_threshold": reference_threshold,
    }
    accuracy: dict[str, Any] = {}
    for condition in conditions:
        metrics = evaluate_accuracy(
            fp32_blocks[condition],
            w8a16_blocks[condition],
            paired_path,
            reused_threshold=reference_threshold,
            w8a16_source=w8a16_path,
        )
        accuracy[condition] = {
            source: metrics[source].to_dict() for source in THRESHOLD_SOURCES
        }
    record["accuracy"] = accuracy
    missing = [condition for condition in TASK_MATRIX if condition not in conditions]
    if missing:
        record["status"] = STATUS_INCOMPLETE
        record["reason"] = (
            "任务矩阵未覆盖全部条件，缺失：" + ", ".join(missing)
        )
        record["threshold_recalibration"] = "blocked"
        record["product_admission"] = "blocked"
        record["blocked_actions"] = list(BLOCKED_ACTIONS)
    else:
        record["status"] = STATUS_PASS
        record["reason"] = None
        record["threshold_recalibration"] = "completed"
        record["product_admission"] = "blocked_pending_first_success_gate"
        record["blocked_actions"] = [SPEED_MATRIX_ACTION]
        record["pending"] = []
    if output is not None:
        write_json_atomic(Path(output), record)
    return record


def _main_extract(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="benchmark extract",
        description="从设备原始输出 + context info.json 生成 paired embedding",
    )
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args(list(argv))
    try:
        record = extract_embedding_sets(
            Path(arguments.spec), Path(arguments.output_dir)
        )
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2
    summary = {
        "status": "ok",
        "output_dir": record["output_dir"],
        "conditions": record["conditions"],
        "item_ids_sha256": record["item_ids_sha256"],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "extract":
        return _main_extract(args[1:])
    parser = argparse.ArgumentParser(
        description="CAM++ W8A16 embedding parity 与任务准确率门禁"
    )
    parser.add_argument("--root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=None, help="默认写到 <root>/benchmark.json")
    arguments = parser.parse_args(args)
    output = (
        Path(arguments.output)
        if arguments.output
        else Path(arguments.root) / "benchmark.json"
    )
    try:
        record = collect_benchmark(
            Path(arguments.root), Path(arguments.manifest), output=output
        )
    except (ValueError, DeviceUnavailableError) as exc:
        summary = {
            "status": getattr(exc, "status", "error"),
            "reason": str(exc),
            "output": str(output),
            "gate_passed": None,
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 2
    summary = {
        "status": record["status"],
        "reason": record["reason"],
        "output": str(output),
        "gate_passed": record["gate"]["passed"] if record["gate"] else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if record["status"] == STATUS_PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
