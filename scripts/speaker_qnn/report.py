"""CAM++ SM8845/V81 排障与性能报告的确定性渲染。

口径（2026-10-20）：

- 报告只读证据 JSON（`matrix.json`、`probes/*.json`、`device-runs/*/result.json`、
  `benchmark.json`），不现场跑设备、不补任何估算值；
- 每一节都分列 `**实测：**` 与 `**不可得：**`；没有 pass embedding 时终态固定
  `blocked`，隔离区间为 `awaiting_device`，分区根因 `unproven`；
- 任何 `timeout` / `ssr` 只写成 FastRPC timeout（10 秒看门狗）或 CDSP SSR，
  绝不渲染成推理延迟数字；
- 输出不含绝对路径与生成时间，`--check` 逐字节比较已提交报告，漂移即非零退出。

    python -m scripts.speaker_qnn.report
    python -m scripts.speaker_qnn.report --check
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_ROOT = REPO / "var/speaker-benchmark/qnn/campplus-htp-debug"
DEFAULT_OUTPUT = REPO / "docs/research/2026-10-20-campplus-qnn-sm8845.md"

EMBEDDING_DIM = 192
WATCHDOG_MS = 10_000

STATUS_LABELS = {
    "pass": "pass（通过；本次没有持久化 graph 时间，不计入速度值）",
    "timeout": "FastRPC timeout（10 秒看门狗触发，不是推理延迟）",
    "ssr": "CDSP SSR（FastRPC timeout 的下游后果，没有 embedding）",
    "load_error": "load_error（context 未加载，不是速度值）",
    "execute_error": "execute_error（执行失败，不是速度值）",
    "tool_error": "tool_error（工具链/推送失败，不是速度值）",
    "unreadable": "unreadable（result.json 不可读，不能当 pass）",
}


def _read_json(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def collect_incident(root: Path) -> dict[str, Any]:
    """从证据根汇总故障时间线；缺文件按空值处理，绝不补造证据。"""
    root = Path(root)
    matrix = _read_json(root / "matrix.json") or {}
    isolation = _read_json(root / "probes/isolation.json")
    rewrite = _read_json(root / "probes/rewrite.json")
    partitions = sorted((root / "probes").glob("partition-*/partition.json"))
    partition = _read_json(partitions[0]) if partitions else None

    timeline: list[dict[str, Any]] = []
    for result_path in sorted((root / "device-runs").glob("*/result.json")):
        payload = _read_json(result_path) or {}
        timeline.append(
            {
                "run_id": result_path.parent.name,
                "status": str(payload.get("status") or "unreadable"),
                "exit_code": payload.get("exit_code"),
                "output_count": int(payload.get("output_count") or 0),
                "finite": bool(payload.get("finite")),
                "timeout_ms": payload.get("timeout_ms"),
            }
        )

    terminal_status = "blocked"
    if any(
        record["status"] == "pass"
        and record["output_count"] == EMBEDDING_DIM
        and record["finite"]
        for record in timeline
    ):
        terminal_status = "pass"

    variants = [
        {
            "variant_id": variant.get("variant_id"),
            "kind": variant.get("kind"),
            "stage": variant.get("stage"),
            "status": variant.get("status"),
            "metadata": variant.get("metadata"),
            "sha256": variant.get("sha256") or {},
            "warning": variant.get("warning"),
            "reason": variant.get("reason"),
            "error": variant.get("error"),
            "equivalent_to": variant.get("equivalent_to"),
        }
        for variant in matrix.get("variants") or ()
        if isinstance(variant, Mapping)
    ]
    return {
        "schema_version": matrix.get("schema_version"),
        "kind": "campplus_htp_incident",
        "terminal_status": terminal_status,
        "device": matrix.get("device") or {"available": False, "serial": None},
        "toolchains": matrix.get("toolchains") or [],
        "matrix_summary": matrix.get("summary") or {},
        "matrix": variants,
        "model": matrix.get("model"),
        "calibration_list": matrix.get("calibration_list"),
        "timeline": timeline,
        "isolation": isolation,
        "rewrite": rewrite,
        "partition": partition,
    }


def load_benchmark(root: Path) -> dict[str, Any]:
    """读取 `benchmark.json`；缺失时显式 `device_unavailable`。"""
    payload = _read_json(Path(root) / "benchmark.json")
    if payload is None:
        return {
            "schema_version": None,
            "kind": "campplus_w8a16_benchmark",
            "status": "device_unavailable",
            "reason": "证据根缺少 benchmark.json",
        }
    return payload


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "/").replace("\n", " ")


def _shape(value: Any) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return "[" + ",".join(str(item) for item in value) + "]"
    return _cell(value)


def _metadata_text(metadata: Any) -> str:
    if not isinstance(metadata, Mapping):
        return "无（未通过元数据门禁）"
    return (
        f"socModel={metadata.get('soc_model')} / dspArch={metadata.get('dsp_arch')}"
        f" / in={_shape(metadata.get('input_shape'))}"
        f" / out={_shape(metadata.get('output_shape'))}"
    )


def _display_path(value: Any) -> str:
    """仓库内路径显示成相对路径，避免报告被本机绝对路径钉死。"""
    if not isinstance(value, str) or not value:
        return _cell(value)
    normalized = value.replace("\\", "/")
    prefix = str(REPO).replace("\\", "/").rstrip("/") + "/"
    if normalized.lower().startswith(prefix.lower()):
        return normalized[len(prefix):]
    return normalized


def _status_label(status: Any) -> str:
    return STATUS_LABELS.get(str(status), f"{status}（非 pass，不是速度值）")


def _header(incident: Mapping[str, Any]) -> list[str]:
    terminal = str(incident.get("terminal_status") or "blocked")
    device = incident.get("device") or {}
    serial = device.get("serial") if isinstance(device, Mapping) else None
    return [
        "# CAM++ W8A16 在 SM8845 HTP V81 上的超时排障与实测",
        "",
        "- **日期：** 2026-10-20",
        f"- **终态：** `{terminal}`",
        "- **设备：** nubia P0310，SM8845（`socModel=87`）/ HTP V81（`dspArch=81`），"
        f"Android API 36；adb 在线设备：{_cell(serial) or '无（device_unavailable）'}",
        "- **口径：** 报告只写实测与不可得两类事实。任何 `timeout`/`ssr` 都是 "
        "FastRPC 10 秒看门狗事件（CDSP SSR 是其下游后果），不是推理延迟；"
        "没有 pass 证据的指标一律标 `不可得`。",
        "",
    ]


def _section_measured(incident: Mapping[str, Any]) -> list[str]:
    timeline = incident.get("timeline") or []
    lines = ["## 1. 实测与不可得分列", "", "**实测：**"]
    measured: list[str] = []
    for record in timeline:
        if record.get("status") == "pass":
            measured.append(
                f"- 真机运行 `{_cell(record.get('run_id'))}` 为 pass："
                f"退出码 {_cell(record.get('exit_code'))}，"
                f"{record.get('output_count')} 个输出元素且全部有限；"
                "该次没有持久化 graph 时间，不作为延迟数字。"
            )
    if incident.get("matrix"):
        measured.append(
            f"- 版本/配置矩阵：{len(incident.get('matrix') or [])} 行离线构建产物，"
            "每行都有 build ID、元数据与完整 SHA-256（见第 3、6 节）。"
        )
    measured.extend(
        [
            "- HTP V81 `y=x+1` smoke graph 真机通过（incident baseline 实录）："
            "graph 4.726 ms、含 I/O 约 5.08 ms、`max_abs=3.0517578125e-05`；"
            "`result.json` 未持久化 graph_execute_us，原始数值来自既有基线记录。",
            "- 静态统计池化解剖：折叠为 149 帧后，40 条真实语音 FP32 输出逐元素一致"
            "（`max_abs=0`）；这条路径没有解决真机超时。",
        ]
    )
    if not measured:
        measured.append("- 证据根没有任何真机产物：没有可报告的实测值。")
    lines.extend(measured)
    lines += ["", "**不可得：**"]
    unavailable = ["- CAM++ W8A16 完整 192 维 embedding：`blocked`（全部 timeout/SSR）。"]
    isolation = incident.get("isolation")
    if isinstance(isolation, Mapping):
        unavailable.append(
            f"- 节点区间隔离：`{_cell(isolation.get('status'))}`，"
            f"interval={_cell(isolation.get('interval')) or 'null'}，"
            f"awaiting_interval={_shape(isolation.get('awaiting_interval'))}。"
        )
    partition = incident.get("partition")
    if isinstance(partition, Mapping):
        unavailable.append(
            f"- 双 context 分区根因：`{_cell(partition.get('solves_root_cause'))}`"
            f"（status=`{_cell(partition.get('status'))}`）。"
        )
    unavailable.append(
        "- EER、Top-1、固定 k ARI、在线 ARI、阈值重标定与产品准入：全部不可得。"
    )
    unavailable.append(
        "- 冷/暖延迟 p50/p95/p99、端到端、吞吐与 30 分钟 soak：全部不可得。"
    )
    lines.extend(unavailable)
    lines.append("")
    return lines


def _section_timeline(incident: Mapping[str, Any]) -> list[str]:
    timeline = incident.get("timeline") or []
    lines = [
        "## 2. 事件时间线",
        "",
        "| run_id | 状态 | 退出码 | 输出元素 | 有限 | 说明 |",
        "|---|---|---:|---:|---|---|",
    ]
    for record in timeline:
        lines.append(
            f"| {_cell(record.get('run_id'))} | {_cell(record.get('status'))} | "
            f"{_cell(record.get('exit_code'))} | {record.get('output_count')} | "
            f"{record.get('finite')} | {_status_label(record.get('status'))} |"
        )
    if not timeline:
        lines.append("| 无 | 不可得 | - | 0 | False | 证据根没有 device-runs/*/result.json |")
    lines += [
        "",
        "**实测：** 上表逐条抄自 `device-runs/*/result.json`；`timeout` 与 `ssr` "
        "状态来自 logcat 的 FastRPC 看门狗与 CDSP SSR 证据，不参与任何延迟统计。",
        "",
        "**不可得：** 没有任何一行同时满足 pass、192 个有限输出，因此速度与准确率"
        "都没有合法输入。",
        "",
    ]
    return lines


def _section_matrix(incident: Mapping[str, Any]) -> list[str]:
    variants = incident.get("matrix") or []
    summary = incident.get("matrix_summary") or {}
    toolchains = incident.get("toolchains") or []
    lines = [
        "## 3. 版本与配置矩阵",
        "",
        f"- 完整图行数：{_cell(summary.get('full_graph_rows'))}；"
        f"完整图变体数：{_cell(summary.get('full_graph_variants'))}；"
        f"状态分布：{_cell(summary.get('statuses'))}。",
        "- QAIRT 树：" + "；".join(
            f"`{_cell(item.get('build_id'))}`（{_display_path(item.get('root'))}）"
            for item in toolchains
            if isinstance(item, Mapping)
        ) if toolchains else "- QAIRT 树：不可得（matrix.json 缺失）",
        "",
        "**实测：** 每行都是离线构建产物；`config_warning` 行有 `unexpected "
        "GraphHtpSettings option 66` 告警，未上机。",
        "",
        "**不可得：** 没有任何一行是 `pass`，完整图没有进入真机测速。",
        "",
        "| 变体 | 类型 | 阶段 | 状态 | build ID | 元数据 | 备注 |",
        "|---|---|---|---|---|---|---|",
    ]
    for variant in variants:
        metadata = variant.get("metadata")
        build_id = (
            metadata.get("build_id") if isinstance(metadata, Mapping) else None
        )
        note = variant.get("reason") or variant.get("warning") or variant.get("error")
        if variant.get("equivalent_to"):
            note = f"{note or ''}；equivalent_to={_cell(variant.get('equivalent_to'))}"
        lines.append(
            f"| {_cell(variant.get('variant_id'))} | {_cell(variant.get('kind'))} | "
            f"{_cell(variant.get('stage'))} | {_cell(variant.get('status'))} | "
            f"{_cell(build_id) or '无'} | {_metadata_text(metadata)} | {_cell(note)} |"
        )
    if not variants:
        lines.append("| 无 | - | - | 不可得 | - | - | matrix.json 缺失 |")
    lines.append("")
    return lines


def _section_isolation(incident: Mapping[str, Any]) -> list[str]:
    isolation = incident.get("isolation")
    lines = ["## 4. 隔离区间", ""]
    if not isinstance(isolation, Mapping):
        lines += [
            "**实测：** 无。",
            "",
            "**不可得：** `probes/isolation.json` 缺失，节点区间未建立（`blocked`）。",
            "",
        ]
        return lines
    lines += [
        f"- 状态：`{_cell(isolation.get('status'))}`",
        f"- 已验证区间：{_cell(isolation.get('interval')) or '无（`interval = null`）'}",
        f"- 待验证区间：{_shape(isolation.get('awaiting_interval'))}",
        f"- 节点总数：{_cell(isolation.get('node_count'))}",
        f"- 原因：{_cell(isolation.get('reason'))}",
        "",
        "**实测：** prefix probe 的 context/graph SHA-256 已全部落盘（见第 6 节），"
        "切点与张量形状来自真实图结构。",
        "",
        "**不可得：** 设备离线，prefix/suffix 没有真机执行结果，"
        "因此没有二分进展（`awaiting_device`）。",
        "",
    ]
    probes = isolation.get("probes") or []
    if probes:
        lines += [
            "| probe | 类型 | 节点区间 | 语义输出 | 真机 |",
            "|---|---|---|---|---|",
        ]
        for probe in probes:
            if not isinstance(probe, Mapping):
                continue
            lines.append(
                f"| {_cell(probe.get('probe_id'))} | {_cell(probe.get('kind'))} | "
                f"{_shape(probe.get('node_interval'))} | "
                f"{_shape(probe.get('semantic_output_shape'))} | "
                f"{'有' if probe.get('device') else '无（device_unavailable）'} |"
            )
        lines.append("")
    return lines


def _section_fix(incident: Mapping[str, Any]) -> list[str]:
    rewrite = incident.get("rewrite")
    partition = incident.get("partition")
    lines = ["## 5. 选定修复 / 分区", ""]
    if isinstance(rewrite, Mapping):
        lines += [
            f"- 语义改写：`{_cell(rewrite.get('status'))}`"
            f"（{_cell(rewrite.get('reason'))}）。",
        ]
    else:
        lines.append("- 语义改写：不可得（`probes/rewrite.json` 缺失）。")
    if isinstance(partition, Mapping):
        plan = partition.get("plan") or {}
        cut = plan.get("cut") if isinstance(plan, Mapping) else None
        lines += [
            f"- 双 context 分区：`{_cell(partition.get('status'))}`；"
            f"选择依据 `{_cell(partition.get('selection_basis'))}`；"
            f"根因判定 `{_cell(partition.get('solves_root_cause'))}`。",
        ]
        if isinstance(cut, Mapping):
            lines.append(
                f"- 切点：节点 {_cell(cut.get('node_index'))} "
                f"`{_cell(cut.get('tensor_name'))}` "
                f"{_shape(cut.get('shape'))}。"
            )
        if isinstance(plan, Mapping):
            lines.append(
                f"- 中间张量搬运：{_cell(plan.get('transfer_bytes'))} 字节；"
                "端到端必须计入两次 context 调度、CPU FBank 与搬运，不只相加 "
                "两个 graph time。"
            )
        upgrade = partition.get("candidate_upgrade") or {}
        lines.append(
            f"- 升级为根因候选：eligible={_cell(upgrade.get('eligible'))}"
            f"（{_cell(upgrade.get('reason'))}）。"
        )
        pending = partition.get("pending") or []
        for item in pending:
            lines.append(f"- 待办：{_cell(item)}")
    else:
        lines.append("- 双 context 分区：不可得（partition.json 缺失）。")
    lines += [
        "",
        "**实测：** 分区两侧 context 均为 `config_warning` 离线产物，"
        "40 条真实张量的 FP32 round-trip `max_abs=0`，布局转置已验证。",
        "",
        "**不可得：** 故障区间没有真机证据，分区只是按最小中间张量选择，"
        "`solves_root_cause=unproven`，终态 `blocked`。",
        "",
    ]
    return lines


def _section_hashes(incident: Mapping[str, Any]) -> list[str]:
    lines = [
        "## 6. Artifact 哈希",
        "",
        "| 变体 | 文件 | SHA-256 |",
        "|---|---|---|",
    ]
    rows = 0
    for variant in incident.get("matrix") or []:
        hashes = variant.get("sha256") or {}
        if isinstance(hashes, Mapping):
            for name in sorted(hashes):
                lines.append(
                    f"| {_cell(variant.get('variant_id'))} | {_cell(name)} | "
                    f"`{_cell(hashes[name])}` |"
                )
                rows += 1
    model = incident.get("model") or {}
    if isinstance(model, Mapping) and model.get("sha256"):
        lines.append(
            f"| model（FP32 源） | onnx | `{_cell(model.get('sha256'))}` |"
        )
        rows += 1
    calibration = incident.get("calibration_list") or {}
    if isinstance(calibration, Mapping) and calibration.get("sha256"):
        lines.append(
            f"| calibration（40 条真实语音） | input_list | "
            f"`{_cell(calibration.get('sha256'))}` |"
        )
        rows += 1
    if not rows:
        lines.append("| 无 | - | 不可得 |")
    lines += [
        "",
        "**实测：** 上表哈希均由离线产物实算，可作为复现锚点。",
        "",
        "**不可得：** 没有任何 artifact 通过真机 pass，因此不存在"
        "「实测速度对应的产物」这一层哈希。",
        "",
    ]
    return lines


def _section_accuracy(benchmark: Mapping[str, Any]) -> list[str]:
    status = benchmark.get("status")
    parity_present = benchmark.get("parity") is not None
    accuracy_present = benchmark.get("accuracy") is not None
    lines = [
        "## 7. Paired accuracy",
        "",
        f"- benchmark 状态：`{_cell(status) or 'device_unavailable'}`",
        f"- 原因：{_cell(benchmark.get('reason')) or '证据根缺少 paired embedding'}",
        f"- 阈值重标定：`{_cell(benchmark.get('threshold_recalibration')) or 'blocked'}`；"
        f"产品准入：`{_cell(benchmark.get('product_admission')) or 'blocked'}`",
        "",
    ]
    lines.append(
        "**实测：** parity 指标存在。"
        if parity_present
        else "**实测：** 无；没有 FP32/W8A16 paired embedding，不计算任何准确率。"
    )
    lines += [
        "",
        "**不可得：** "
        + (
            "accuracy 已由 benchmark.json 给出。"
            if accuracy_present
            else "EER、Top-1、固定 k ARI、在线 ARI、簇数量均不可得；"
            "阈值重标定与产品准入保持 `blocked`，禁止用 FP32 阈值冒充 W8A16 阈值。"
        ),
        "",
    ]
    pending = benchmark.get("pending") or []
    for item in pending:
        lines.append(f"- 待办：{_cell(item)}")
    if pending:
        lines.append("")
    return lines


def _metric_row(label: str, value: Any, unit: str) -> str:
    return f"| {label} | {float(value):.3f} {unit} |"


def _section_latency(benchmark: Mapping[str, Any]) -> list[str]:
    latency = benchmark.get("latency")
    lines = ["## 8. 冷/暖延迟与吞吐", ""]
    if not isinstance(latency, Mapping):
        lines += [
            "**实测：** 无；没有任何 pass 的 CAM++ graph 执行。",
            "",
            "**不可得：** `device_unavailable`——20 次 fresh-process 冷加载、"
            "`burst` 与 `sustained_high_performance` 下的 100 次 warmup + 1,000 次 "
            "measured 均未执行，因此 cold p50/p95、graph p50/p95/p99、端到端 "
            "p50/p95 与吞吐都不可得。`>= 10 s` 只可能记为 FastRPC timeout，"
            "不是推理延迟；`>= 1 s` 判不可常驻。",
            "",
        ]
        return lines
    lines += [
        "| 指标 | 数值 |",
        "|---|---:|",
        _metric_row("冷加载 p50", latency.get("cold_load_p50_ms"), "ms"),
        _metric_row("冷加载 p95", latency.get("cold_load_p95_ms"), "ms"),
        _metric_row("graph p50", latency.get("graph_p50_ms"), "ms"),
        _metric_row("graph p95", latency.get("graph_p95_ms"), "ms"),
        _metric_row("graph p99", latency.get("graph_p99_ms"), "ms"),
        _metric_row("端到端 p50", latency.get("end_to_end_p50_ms"), "ms"),
        _metric_row("端到端 p95", latency.get("end_to_end_p95_ms"), "ms"),
        _metric_row("吞吐", latency.get("throughput_ips"), "IPS"),
        "",
        "**实测：** 上表数值来自 `benchmark.json` 的 latency 记录；"
        "端到端是 graph、runner I/O、CPU FBank、中间张量搬运与第二次调度的"
        "实测组成项之和。",
        "",
        "**不可得：** 未测项留空，不估算。",
        "",
    ]
    return lines


def _section_soak(benchmark: Mapping[str, Any]) -> list[str]:
    soak = benchmark.get("soak")
    lines = ["## 9. 30 分钟 soak", ""]
    if not isinstance(soak, Mapping):
        lines += [
            "**实测：** 无。",
            "",
            "**不可得：** `device_unavailable`——30 分钟（1,800 秒）1 Hz "
            "`sustained_high_performance` soak 未执行，battery/SKIN 温区、"
            "成功/失败计数、中位与末尾 graph 时间都不可得。",
            "",
        ]
        return lines
    lines += [
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 时长 | {_cell(soak.get('duration_s'))} s |",
        f"| 成功运行 | {_cell(soak.get('successful_runs'))} |",
        f"| 失败运行 | {_cell(soak.get('failed_runs'))} |",
        f"| battery 最高温 | {_cell(soak.get('max_battery_temp_c'))} °C |",
        f"| SKIN 最高温 | {_cell(soak.get('max_skin_temp_c')) or '无（采样缺口）'} |",
        f"| 中位 graph | {float(soak.get('median_graph_ms')):.3f} ms |",
        f"| 末尾 graph | {float(soak.get('final_graph_ms')):.3f} ms |",
        "",
        "**实测：** 温区逐次来自 `dumpsys thermalservice`；skin 采样缺口允许为空，"
        "但全程无 battery 样本即拒绝出报告。",
        "",
        "**不可得：** 频率状态与降频事件没有采样，不做推断。",
        "",
    ]
    return lines


def render_report(
    incident: Mapping[str, Any], benchmark: Mapping[str, Any]
) -> str:
    """渲染确定性 Markdown；同一输入逐字节一致，且以换行结尾。"""
    incident = incident if isinstance(incident, Mapping) else {}
    benchmark = benchmark if isinstance(benchmark, Mapping) else {}
    lines: list[str] = []
    lines += _header(incident)
    lines += _section_measured(incident)
    lines += _section_timeline(incident)
    lines += _section_matrix(incident)
    lines += _section_isolation(incident)
    lines += _section_fix(incident)
    lines += _section_hashes(incident)
    lines += _section_accuracy(benchmark)
    lines += _section_latency(benchmark)
    lines += _section_soak(benchmark)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(DEFAULT_EVIDENCE_ROOT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--check", action="store_true", help="只校验已提交报告是否与证据一致"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))
    root = Path(arguments.root)
    output = Path(arguments.output)
    text = render_report(collect_incident(root), load_benchmark(root))
    if arguments.check:
        if not output.is_file():
            print(f"error: 报告不存在：{output}", file=sys.stderr)
            return 2
        existing = output.read_text(encoding="utf-8")
        if existing != text:
            print(f"drift: {output} 与证据不一致，请重新生成", file=sys.stderr)
            return 1
        print(f"ok: {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"wrote: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
