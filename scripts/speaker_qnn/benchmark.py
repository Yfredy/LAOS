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
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .contracts import SCHEMA_VERSION, write_json_atomic

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
STATUS_DEVICE_UNAVAILABLE = "device_unavailable"

REUSED_FP32_THRESHOLD = "reused_fp32_threshold"
RECALIBRATED_W8A16_THRESHOLD = "recalibrated_w8a16_threshold"
THRESHOLD_SOURCES = (REUSED_FP32_THRESHOLD, RECALIBRATED_W8A16_THRESHOLD)

BLOCKED_ACTIONS = (
    "accuracy_evaluation",
    "threshold_recalibration",
    "online_clustering",
    "speed_matrix",
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


def require_device_evidence(
    manifest_path: Path, payload: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    """只接受 `pass`、`finite`、192 个输出的真机运行作为准确率证据。"""
    provenance = payload.get("w8a16_provenance")
    if not isinstance(provenance, Mapping):
        raise DeviceUnavailableError(
            "manifest 未记录真机 W8A16 产出（w8a16_provenance 缺失），拒绝计算准确率"
        )
    runs = provenance.get("device_runs")
    if not isinstance(runs, (list, tuple)) or not runs:
        raise DeviceUnavailableError("w8a16_provenance.device_runs 为空，没有真机 embedding 证据")
    manifest_dir = Path(manifest_path).parent
    records: list[dict[str, Any]] = []
    for entry in runs:
        if not isinstance(entry, str) or not entry:
            raise ValueError("device_runs 每条必须是非空路径")
        path = Path(entry)
        if not path.is_absolute():
            path = manifest_dir / path
        if not path.is_file():
            raise DeviceUnavailableError(f"真机运行证据缺失：{entry}")
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeviceUnavailableError(f"真机运行证据不可读：{entry}: {exc}") from exc
        status = result.get("status")
        if status != "pass":
            raise DeviceUnavailableError(
                f"真机运行 {entry} 状态为 {status}，不是 pass，不得据此计算准确率"
            )
        if not result.get("finite") or int(result.get("output_count") or 0) != EMBEDDING_DIM:
            raise DeviceUnavailableError(
                f"真机运行 {entry} 没有 {EMBEDDING_DIM} 个有限输出，不得据此计算准确率"
            )
        records.append(result)
    return tuple(records)


def evaluate_accuracy(
    fp32: Any,
    w8a16: Any,
    manifest: Path,
    *,
    reused_threshold: float | None = None,
    embedding_dim: int = EMBEDDING_DIM,
) -> dict[str, AccuracyMetrics]:
    """paired 准确率：同一批 W8A16 embedding，跑两种阈值来源。

    返回键是阈值来源（`reused_fp32_threshold` / `recalibrated_w8a16_threshold`）；
    EER/Top-1/fixed-k ARI 与阈值无关，因此两项共享，只有在线聚类的 ARI
    和簇数随阈值变化。缺真机证据时抛 `DeviceUnavailableError`。
    """
    np = _require_numpy()
    manifest_path = Path(manifest)
    payload = _load_manifest_json(manifest_path)
    item_ids, speakers = benchmark_items(payload)
    require_device_evidence(manifest_path, payload)
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
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            records.append(
                {
                    "path": str(result_path),
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
                "path": str(result_path),
                "status": str(payload.get("status")),
                "exit_code": payload.get("exit_code"),
                "output_count": int(payload.get("output_count") or 0),
                "finite": bool(payload.get("finite")),
                "timeout_ms": payload.get("timeout_ms"),
            }
        )
    return records


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
        "device_runs": scan_device_evidence(root),
        "parity": None,
        "gate": None,
        "accuracy": None,
        "threshold_recalibration": "blocked",
        "product_admission": "blocked",
        "blocked_actions": list(BLOCKED_ACTIONS),
        "pending": list(PENDING_ACTIONS),
    }
    fp32_path = root / "embeddings" / "fp32.npz"
    w8a16_path = root / "embeddings" / "w8a16.npz"
    problems: list[str] = []
    if record["manifest"]["error"]:
        problems.append(f"manifest 不可用：{record['manifest']['error']}")
    for path in (fp32_path, w8a16_path):
        if not path.is_file():
            problems.append(f"缺少 paired embedding 文件：{path}")
    passing = [
        run
        for run in record["device_runs"]
        if run["status"] == "pass"
        and run["finite"]
        and run["output_count"] == EMBEDDING_DIM
    ]
    if not passing:
        statuses = sorted({run["status"] for run in record["device_runs"]}) or ["no-run"]
        output_counts = sorted(
            {run["output_count"] for run in record["device_runs"] if run["status"] == "pass"}
        )
        detail = "现有状态：" + ", ".join(statuses)
        if output_counts:
            detail += "；pass 运行的输出元素数：" + ", ".join(
                str(value) for value in output_counts
            )
        problems.append(
            f"没有产出 {EMBEDDING_DIM} 维有限 embedding 的 pass 真机运行（{detail}）"
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
    fp32_blocks, fp32_ids = load_embedding_set(fp32_path)
    w8a16_blocks, w8a16_ids = load_embedding_set(w8a16_path)
    if fp32_ids != item_ids or w8a16_ids != item_ids:
        raise ValueError("embedding item_ids 与 manifest 顺序/内容不一致（行未对齐）")
    if set(fp32_blocks) != set(w8a16_blocks):
        raise ValueError("fp32 与 w8a16 的条件块不一致")
    conditions = list(fp32_blocks)

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
    record["embeddings"] = {"fp32": str(fp32_path), "w8a16": str(w8a16_path)}
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
        "w8a16_provenance": {
            "device_runs": [run["path"] for run in passing],
            "required_status": STATUS_PASS,
        },
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
        )
        accuracy[condition] = {
            source: metrics[source].to_dict() for source in THRESHOLD_SOURCES
        }
    record["accuracy"] = accuracy
    record["status"] = STATUS_PASS
    record["reason"] = None
    record["threshold_recalibration"] = "completed"
    record["product_admission"] = "blocked_pending_first_success_gate"
    record["blocked_actions"] = ["speed_matrix"]
    record["pending"] = []
    if output is not None:
        write_json_atomic(Path(output), record)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CAM++ W8A16 embedding parity 与任务准确率门禁"
    )
    parser.add_argument("--root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=None, help="默认写到 <root>/benchmark.json")
    arguments = parser.parse_args(argv)
    output = (
        Path(arguments.output)
        if arguments.output
        else Path(arguments.root) / "benchmark.json"
    )
    record = collect_benchmark(Path(arguments.root), Path(arguments.manifest), output=output)
    summary = {
        "status": record["status"],
        "reason": record["reason"],
        "output": str(output),
        "gate_passed": record["gate"]["passed"] if record["gate"] else None,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
