# CAM++ SM8845 HTP Timeout Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 定位并消除 CAM++ W8A16 context 在 SM8845 HTP V81 首次执行时触发的 10 秒 FastRPC 超时，使完整 192 维 embedding 链路可重复运行，再完成准确率、延迟、吞吐和热稳定性实测。

**Architecture:** 建立一套可复现的 QNN 构建与真机诊断工具链，将每个 QAIRT/编译配置产物绑定到严格的 `socModel=87`、`dspArch=81` 元数据和哈希。先用有限版本/编译配置矩阵排除编译器回归；仍失败时，使用真实 FP32 中间张量构造 CAM++ 前缀与后缀 probe，对 3,102 节点图做阶段级再到节点区间级二分。首选语义等价的单 context 修复；若故障只在完整图调度中出现，允许双 context 分区作为备用，但必须通过同一数值和性能门禁。

**Tech Stack:** Python 3.10 QAIRT task-local venv；Python 3.11 benchmark venv；ONNX 1.16+；ONNX Runtime；QAIRT/QNN 2.51.1 及经 metadata 门禁确认支持 SM8845/V81 的候选版本；ADB；`qnn-onnx-converter`、`qnn-model-lib-generator`、`qnn-context-binary-generator`、`qnn-context-binary-utility`、`qnn-net-run`、`qnn-profile-viewer`；`unittest`。

**Spec:** `docs/superpowers/specs/2026-10-20-sound-memory-design.md` §6.1、§12；设备与 FP32 基线：`docs/research/2026-10-20-speaker-model-benchmark.md`；故障证据：`var/speaker-benchmark/qnn/campplus-w8a16-v2/device-farf-logcat.txt:105,282-283,559,727,845`。

## Incident Baseline

- 设备固定为 nubia P0310，SoC `SM8845`，board `canoe`，Android API 36，ABI `arm64-v8a`。
- QAIRT 2.51.1 context 可反序列化，元数据为 `socModel=87`、`dspArch=81`，输入 `U16[1,80,298]`，输出 `U16[1,192]`。
- HTP V81 最小 `y=x+1` smoke graph 真机通过：graph `4.726 ms`，含 I/O 约 `5.08 ms`，最大绝对误差 `3.0517578125e-05`。
- CAM++ 在 `gpe_execute_novalidate` 后恰好 `10.001 s` 被 FastRPC 主动终止；QNN 返回 `err 1003` 并触发 CDSP SSR，没有 embedding 输出。
- 将统计池化样本数折叠为静态 `149` 后，40 条真实语音 FP32 输出逐元素一致（`max_abs=0`），但真机仍超时；该路径不是根因。
- QAIRT 2.47 对 SM8845 曾静默回退到 `socModel=0`、`dspArch=68`；任何类似产物必须在上机前拒绝。

## Global Constraints

- 不关闭、不修改 `vendor.fastrpc.process.rpctimeout=1`；10 秒看门狗是安全边界，不是需要绕过的障碍。
- runner、`libQnnHtp.so`、V81 stub/skel、context generator 和 profile viewer 必须来自同一 QAIRT build ID；禁止混用版本。
- 每个候选 context 上机前必须由 `qnn-context-binary-utility` 证明 `socModel == 87`、`dspArch == 81`、graph count `== 1`；不满足即 `metadata_rejected`。
- 量化固定为 W8A16：`weights_bitwidth=8`、`act_bitwidth=16`、真实语音 MinMax calibration；不得用随机张量、W8A8、CPU fallback 或 host 模拟器结果替代。
- 输入固定为 16 kHz、3 秒、80-bin FBank、298 帧；QNN context 物理布局 `[1,80,298]`，模型语义布局 `[1,298,80]`，转换必须显式记录。
- 校准复用现有 20 人 × 2 条真实语音共 40 条，且与原 20 人评测集 speaker overlap 为 0；每次构建先验证 manifest 和 SHA-256。
- 所有语义改写必须先过 40 条输入 FP32 parity：最大绝对误差 `== 0`，或在浮点算子不可逐元素一致时 paired cosine median `>= 0.999999`、minimum `>= 0.99999`，并写明原因。
- 在完整 CAM++ 或明确批准的双 context 管线产生有限 192 维 embedding 前，不运行准确率、阈值、聚类或正式速度矩阵。
- 首次成功门禁：同一真实输入连续 30 次执行，退出码全为 0、无 SSR、无 FastRPC timeout、每次输出 192 个有限值。
- 单次推理 `>= 1 s` 即判为不可常驻；`>= 10 s` 直接 `timeout`，不得报告为速度值。
- 重资产、SDK、context、raw、embedding、profile 和 log 全部留在 `var/speaker-benchmark/qnn/campplus-htp-debug/`；`laos/` 保持纯 stdlib。
- 不修改用户已有 README、laosweb、声音记忆实现和其他未提交改动；每个 Task 一个 conventional commit。

## Review Focus

- 版本看似支持 `sm8845` 但实际静默回退：metadata parser 必须拒绝 `socModel=0`、`dspArch!=81` 和 build ID 混配。
- probe 切点改变了量化或图优化，使“通过”被误当成原图根因：每个 probe 必须记录原节点区间、输入输出 tensor、校准来源、图哈希和编译配置。
- 后缀 probe 使用随机中间张量掩盖数据相关问题：只能使用 FP32 CAM++ 从同一 40 条真实语音捕获的中间 tensor。
- context 加载成功被误报为推理成功：只有存在有限的 192 维输出、退出码 0 且 log 无 SSR 才是 `pass`。
- 双 context 绕过超时但端到端不可用：必须计入中间 tensor 搬运、两次 context 调度、CPU FBank、温升和 sustained profile，不只报告两个 graph time 之和。

---

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `scripts/speaker_qnn/__init__.py` | Create | 导出 schema version 与稳定公共接口 |
| `scripts/speaker_qnn/contracts.py` | Create | build、context metadata、device run、probe、benchmark 数据类型与 JSON 序列化 |
| `scripts/speaker_qnn/build.py` | Create | QAIRT 资产发现、W8A16 转换、model DLL、SM8845/V81 context 构建和 provenance |
| `scripts/speaker_qnn/device.py` | Create | ADB 推送、版本一致性检查、单次/循环运行、profile/logcat/SSR 归类 |
| `scripts/speaker_qnn/probe.py` | Create | FP32 中间 tensor 捕获、前缀/后缀 ONNX 提取、真实 tensor 校准和二分 |
| `scripts/speaker_qnn/benchmark.py` | Create | paired embedding、准确率、延迟、吞吐、温度和 soak 指标 |
| `scripts/speaker_qnn/report.py` | Create | 从 JSON 确定性生成排障与性能报告 |
| `tests/test_speaker_qnn_contracts.py` | Create | schema、状态和 metadata 门禁 |
| `tests/test_speaker_qnn_build.py` | Create | 命令构造、版本配套、W8A16 与 provenance |
| `tests/test_speaker_qnn_device.py` | Create | ADB 输出解析、timeout/SSR/pass 分类和 profile 解析 |
| `tests/test_speaker_qnn_probe.py` | Create | tensor capture、probe 提取、二分与 parity |
| `tests/test_speaker_qnn_benchmark.py` | Create | paired 数值、延迟分位数、门禁与报告字段 |
| `docs/research/2026-10-20-campplus-qnn-sm8845.md` | Create | 根因、修复、真机数值与性能证据 |
| `docs/research/INDEX.md` | Modify | 增加 QNN 真机报告入口 |
| `docs/superpowers/plans/README.md` | Modify | 登记本计划状态 |

运行时布局：

```text
var/speaker-benchmark/qnn/campplus-htp-debug/
  incident.json
  toolchains/<build-id>/inventory.json
  builds/<variant-id>/{model,lib,context,artifact.json}
  intermediates/<tensor-id>/{manifest.json,*.raw}
  probes/<probe-id>/{model,context,artifact.json}
  device-runs/<run-id>/{stdout.log,logcat.txt,profile.log,result.json}
  embeddings/{fp32,w8a16}.npz
  benchmark.json
```

### Task 1: 固化故障基线与真机执行契约

**Files:**
- Create: `scripts/speaker_qnn/__init__.py`
- Create: `scripts/speaker_qnn/contracts.py`
- Create: `scripts/speaker_qnn/device.py`
- Create: `tests/test_speaker_qnn_contracts.py`
- Create: `tests/test_speaker_qnn_device.py`

**Interfaces:**
- Consumes:
  - ADB serial `327366100004`
  - existing smoke context and CAM++ context/logs under `var/speaker-benchmark/qnn/`
- Produces:
  - `ContextMetadata(build_id: str, soc_model: int, dsp_arch: int, graph_name: str, input_shape: tuple[int, ...], output_shape: tuple[int, ...])`
  - `DeviceRunStatus = Literal["pass", "timeout", "ssr", "load_error", "execute_error", "tool_error"]`
  - `DeviceRunResult(status: DeviceRunStatus, exit_code: int, output_path: str | None, output_count: int, finite: bool, context_load_us: int | None, graph_execute_us: int | None, timeout_ms: int | None, evidence_paths: tuple[str, ...])`
  - `validate_sm8845_context(metadata: ContextMetadata) -> None`
  - `classify_device_run(stdout: str, logcat: str, output: numpy.ndarray | None) -> DeviceRunResult`
  - `run_context(serial: str, artifact_dir: Path, input_list: Path, output_dir: Path, num_inferences: int, profiling_level: str, perf_profile: str) -> DeviceRunResult`

- [ ] **Step 1: Write failing contract and log-classification tests**

```python
def test_sm8845_metadata_rejects_silent_arch_fallback():
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

def test_fastrpc_watchdog_is_timeout_not_latency():
    result = classify_device_run(
        stdout="Graph Execution failure",
        logcat="Intentional crash triggered using remote session control timeout: 10000",
        output=None,
    )
    self.assertEqual(result.status, "timeout")
    self.assertEqual(result.timeout_ms, 10000)
```

Add fixtures for smoke pass, context load failure, `err 1003` + SSR, missing output, non-finite 192-D output, build ID mismatch and output with wrong element count.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_contracts tests.test_speaker_qnn_device -v
```

Expected: FAIL because `scripts.speaker_qnn` does not exist.

- [ ] **Step 3: Implement strict contracts and parsers**

`validate_sm8845_context()` must require `soc_model == 87`, `dsp_arch == 81`, input `(1,80,298)`, output `(1,192)` for CAM++; smoke fixtures may opt into explicit expected shapes. `classify_device_run()` must prioritize SSR/timeout evidence over generic `Graph Execution failure`.

- [ ] **Step 4: Implement idempotent device runner**

`run_context()` creates a unique remote directory, pushes same-build runner/backend/stub/skel/context, verifies remote SHA-256, runs without modifying FastRPC properties, pulls stdout/logcat/profile/output, and writes `result.json` atomically.

- [ ] **Step 5: Reproduce both baseline outcomes**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m scripts.speaker_qnn.device smoke --serial 327366100004
C:/Users/yaoyue/miniconda3/python.exe -m scripts.speaker_qnn.device run --artifact var/speaker-benchmark/qnn/campplus-w8a16-v2 --serial 327366100004 --num-inferences 1
```

Expected: smoke `pass` with 16 finite outputs; CAM++ `timeout`, `timeout_ms=10000`, no output, and evidence contains `gpe_execute_novalidate` followed by intentional FastRPC crash.

- [ ] **Step 6: Commit**

```bash
git add scripts/speaker_qnn/__init__.py scripts/speaker_qnn/contracts.py scripts/speaker_qnn/device.py tests/test_speaker_qnn_contracts.py tests/test_speaker_qnn_device.py
git commit -m "test(speaker): codify SM8845 HTP timeout"
```

### Task 2: 建立受限 QAIRT 与编译配置矩阵

**Files:**
- Create: `scripts/speaker_qnn/build.py`
- Create: `tests/test_speaker_qnn_build.py`

**Interfaces:**
- Consumes:
  - `ContextMetadata(build_id: str, soc_model: int, dsp_arch: int, graph_name: str, input_shape: tuple[int, ...], output_shape: tuple[int, ...])`
  - `validate_sm8845_context(metadata: ContextMetadata) -> None`
  - fixed FP32 ONNX and 40-file calibration manifest
- Produces:
  - `ToolchainSpec(build_id: str, root: Path, runner: Path, backend_host: Path, backend_android: Path, stub: Path, skel: Path, converter: Path, context_generator: Path)`
  - `BuildVariant(toolchain: ToolchainSpec, optimization_level: int, vtcm_mb: int, dlbc: bool, graph_name: str)`
  - `BuildArtifact(variant_id: str, status: str, context_path: str | None, metadata: ContextMetadata | None, sha256: dict[str, str], commands: tuple[str, ...], error: str | None)`
  - `discover_toolchains(roots: tuple[Path, ...]) -> tuple[ToolchainSpec, ...]`
  - `build_w8a16_context(model: Path, calibration_list: Path, variant: BuildVariant, output_dir: Path) -> BuildArtifact`

- [ ] **Step 1: Write failing toolchain and build-contract tests**

```python
def test_toolchain_assets_must_share_one_build_id():
    with self.assertRaisesRegex(ValueError, "mixed QAIRT build"):
        ToolchainSpec.from_inventory(MIXED_VERSION_INVENTORY)

def test_build_command_preserves_w8a16_and_real_calibration():
    command = build_converter_command(MODEL, CALIBRATION_LIST, VARIANT)
    self.assertIn("--weights_bitwidth 8", command)
    self.assertIn("--act_bitwidth 16", command)
    self.assertIn(str(CALIBRATION_LIST), command)
```

Add tests for missing V81 skel, absent backend extension, 2.47 silent fallback rejection, graph-name/config mismatch, build command provenance and atomic failed artifact.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_build -v
```

Expected: FAIL because `scripts.speaker_qnn.build` does not exist.

- [ ] **Step 3: Implement inventory and strict build pipeline**

Discover existing 2.47 and 2.51 installations plus QPM-downloaded candidates. A candidate is eligible only if its backend extension recognizes SM8845 and the generated smoke context parses as `socModel=87`, `dspArch=81`; otherwise write `metadata_rejected` and do not push it.

- [ ] **Step 4: Execute staged matrix with stop conditions**

Run Stage A first: QAIRT 2.51 plus the nearest available newer or BSP-matched version, default optimization, VTCM 4 MB, DLBC off. If no candidate is newer, query QPM inventory and record `unavailable`; do not reuse 2.47 as SM8845 evidence.

For each Stage A candidate:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m scripts.speaker_qnn.build matrix --stage toolchain --model var/speaker-benchmark/qnn/campplus-w8a16-v2/campplus-3s-fp32-static-stats.onnx
```

Expected: each eligible artifact has valid metadata and one `DeviceRunResult`. Stop version expansion at the first candidate that passes 30 consecutive inferences.

- [ ] **Step 5: Run bounded compiler configuration matrix only if Stage A fails**

On the newest eligible toolchain, test `optimization_level ∈ {0,1,2,3}` with VTCM 4 MB. If all fail, test VTCM 8 MB for the fastest-progressing variant; test `dlbc=false` explicitly if the toolchain default differs. Cap total full-graph variants at 10.

Expected: matrix JSON distinguishes `metadata_rejected`, `load_error`, `timeout`, `ssr`, and `pass`; no generic “failed” bucket.

- [ ] **Step 6: Commit**

```bash
git add scripts/speaker_qnn/build.py tests/test_speaker_qnn_build.py
git commit -m "feat(speaker): add bounded QNN compiler matrix"
```

### Task 3: 构建真实中间张量的前缀/后缀 Probe

**Files:**
- Create: `scripts/speaker_qnn/probe.py`
- Create: `tests/test_speaker_qnn_probe.py`

**Interfaces:**
- Consumes:
  - `ToolchainSpec(build_id: str, root: Path, runner: Path, backend_host: Path, backend_android: Path, stub: Path, skel: Path, converter: Path, context_generator: Path)`
  - `BuildVariant(toolchain: ToolchainSpec, optimization_level: int, vtcm_mb: int, dlbc: bool, graph_name: str)`
  - `BuildArtifact(variant_id: str, status: str, context_path: str | None, metadata: ContextMetadata | None, sha256: dict[str, str], commands: tuple[str, ...], error: str | None)`
  - original fixed FP32 ONNX
  - 40 real calibration inputs
- Produces:
  - `TensorCut(node_index: int, tensor_name: str, shape: tuple[int, ...], dtype: str)`
  - `ProbeSpec(probe_id: str, kind: Literal["prefix", "suffix"], first_node: int, last_node: int, input_tensors: tuple[str, ...], output_tensors: tuple[str, ...])`
  - `capture_intermediates(model: Path, cuts: tuple[TensorCut, ...], input_list: Path, output_dir: Path) -> dict[str, Path]`
  - `extract_prefix(model: Path, cut: TensorCut, output: Path) -> ProbeSpec`
  - `extract_suffix(model: Path, cut: TensorCut, intermediate_manifest: Path, output: Path) -> ProbeSpec`
  - `bisect_failure_interval(results: tuple[tuple[ProbeSpec, DeviceRunResult], ...]) -> tuple[int, int]`

- [ ] **Step 1: Write failing extraction and bisection tests**

```python
def test_suffix_calibration_uses_captured_real_intermediates():
    spec = extract_suffix(MODEL, CUT, INTERMEDIATE_MANIFEST, OUTPUT)
    self.assertEqual(spec.input_tensors, (CUT.tensor_name,))
    self.assertEqual(
        load_manifest(INTERMEDIATE_MANIFEST).source_kind,
        "fp32_real_audio",
    )

def test_bisection_returns_smallest_pass_to_timeout_interval():
    interval = bisect_failure_interval(PROBE_RESULTS)
    self.assertEqual(interval, (LAST_PASSING_NODE, FIRST_TIMEOUT_NODE))
```

Add tests for stable stage boundaries, multi-consumer tensors, unsupported cut outputs, dynamic dimensions, disconnected initializers, SHA mismatch, NaN intermediate data and a probe whose extracted graph changes output semantics.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_probe -v
```

Expected: FAIL because `scripts.speaker_qnn.probe` does not exist.

- [ ] **Step 3: Implement stage discovery and real tensor capture**

Freeze initial cuts after head, CAM++ block1, block2, block3/transit, out nonlinear, stats concat and final dense by resolving actual ONNX tensor names and node indices. Capture each cut for all 40 real calibration inputs with FP32 ONNX Runtime; persist shape, dtype, source input SHA-256 and tensor SHA-256.

- [ ] **Step 4: Build and validate prefix/suffix probes**

Each prefix uses original FBank input and emits one cut tensor. Each suffix consumes the captured cut tensor and emits the original 192-D embedding. Before QNN conversion, ONNX Runtime must prove `suffix(prefix(x))` matches full FP32 embedding under the parity gate for all 40 inputs.

- [ ] **Step 5: Compile and run stage probes**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m scripts.speaker_qnn.probe stages --variant <best-eligible-variant> --serial 327366100004
```

Expected: JSON identifies the last passing prefix and the first failing prefix, plus suffix outcomes. If every prefix passes but full graph fails, classify `full_graph_scheduling`; do not blame the final stage.

- [ ] **Step 6: Bisect only inside the isolated stage**

Generate midpoint cuts only in the current failing interval, always at a tensor with fully static shape and one representable QNN input. Stop when the interval is at most 16 ONNX nodes or all remaining nodes share one operator family.

Expected: `isolation.json` contains the minimal interval, operator types, tensor shapes, every probe hash and run evidence.

- [ ] **Step 7: Commit**

```bash
git add scripts/speaker_qnn/probe.py tests/test_speaker_qnn_probe.py
git commit -m "feat(speaker): isolate HTP failures with real probes"
```

### Task 4: 实施单 context 修复或双 context 备用分区

**Files:**
- Modify: `scripts/speaker_qnn/probe.py`
- Modify: `scripts/speaker_qnn/build.py`
- Modify: `tests/test_speaker_qnn_probe.py`
- Modify: `tests/test_speaker_qnn_build.py`

**Interfaces:**
- Consumes:
  - `TensorCut(node_index: int, tensor_name: str, shape: tuple[int, ...], dtype: str)`
  - `ProbeSpec(probe_id: str, kind: Literal["prefix", "suffix"], first_node: int, last_node: int, input_tensors: tuple[str, ...], output_tensors: tuple[str, ...])`
  - `bisect_failure_interval(results: tuple[tuple[ProbeSpec, DeviceRunResult], ...]) -> tuple[int, int]`
  - `isolation.json` with the minimal node interval, operator types, tensor shapes, probe hashes and device evidence
- Produces:
  - `RewriteResult(name: str, source_sha256: str, output_sha256: str, parity: dict[str, float], changed_nodes: tuple[str, ...])`
  - `apply_semantic_rewrite(model: Path, isolation: dict[str, object], output: Path) -> RewriteResult`
  - `PartitionPlan(cut: TensorCut, prefix_context: BuildArtifact, suffix_context: BuildArtifact, transfer_bytes: int)`
  - `build_partition(model: Path, cut: TensorCut, variant: BuildVariant, output_dir: Path) -> PartitionPlan`

- [ ] **Step 1: Write failing rewrite and partition acceptance tests**

```python
def test_rewrite_must_pass_fp32_parity_before_qnn_build():
    with self.assertRaisesRegex(ValueError, "FP32 parity"):
        require_rewrite_parity(DRIFTED_REWRITE_RESULT)

def test_partition_accounts_for_intermediate_transfer():
    plan = build_partition(MODEL, CUT, VARIANT, OUTPUT)
    self.assertEqual(
        plan.transfer_bytes,
        math.prod(CUT.shape) * dtype_size(CUT.dtype),
    )
```

Add tests that reject broad unrelated rewrites, missing changed-node names, CPU operators in the final path, more than two partitions and a partition whose suffix calibration is not based on real captured tensors.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_probe tests.test_speaker_qnn_build -v
```

Expected: FAIL on the new rewrite/partition contracts.

- [ ] **Step 3: Implement one operator-family rewrite**

Choose the rewrite from `isolation.json`, not from prior guesses. Examples allowed only when evidence points there: constant-fold static shape arithmetic, replace an equivalent reduction decomposition, normalize reshape/transpose layout, or split a pathological fused CAM block. Record exact changed node names and preserve the FP32 parity gate.

- [ ] **Step 4: Build and run the repaired full context**

Run 30 consecutive real-input inferences with detailed profile on the first and basic profile thereafter.

Expected: `pass` 30/30, finite 192-D output each run, no timeout/SSR; otherwise preserve evidence and proceed to Step 5.

- [ ] **Step 5: Build at most one two-context fallback**

Use the stage cut with the smallest intermediate tensor among cuts where both prefix and suffix pass independently. Run prefix context, transfer its native output, then run suffix context without CPU model operators.

Expected: 30/30 complete embeddings, no SSR, total warm graph time `< 1 s`, and transfer cost reported. If this fails, mark CAM++ W8A16 on the tested QAIRT/device combination `blocked`; do not expand to three or more contexts.

- [ ] **Step 6: Commit**

```bash
git add scripts/speaker_qnn/probe.py scripts/speaker_qnn/build.py tests/test_speaker_qnn_probe.py tests/test_speaker_qnn_build.py
git commit -m "fix(speaker): make CAM++ executable on SM8845 HTP"
```

### Task 5: 验证 W8A16 Embedding 数值与任务准确率

**Files:**
- Create: `scripts/speaker_qnn/benchmark.py`
- Create: `tests/test_speaker_qnn_benchmark.py`

**Interfaces:**
- Consumes:
  - `BuildArtifact(variant_id: str, status: str, context_path: str | None, metadata: ContextMetadata | None, sha256: dict[str, str], commands: tuple[str, ...], error: str | None)`
  - `PartitionPlan(cut: TensorCut, prefix_context: BuildArtifact, suffix_context: BuildArtifact, transfer_bytes: int)`
  - existing FP32 benchmark manifest and frontend
- Produces:
  - `EmbeddingParity(median_cosine: float, p01_cosine: float, minimum_cosine: float, mean_l2: float, p95_l2: float)`
  - `AccuracyMetrics(eer: float, top1: float, fixed_k_ari: float, online_ari: float, cluster_count: int)`
  - `evaluate_embedding_parity(fp32: numpy.ndarray, w8a16: numpy.ndarray) -> EmbeddingParity`
  - `evaluate_accuracy(fp32: numpy.ndarray, w8a16: numpy.ndarray, manifest: Path) -> dict[str, AccuracyMetrics]`

- [ ] **Step 1: Write failing parity and accuracy-gate tests**

```python
def test_embedding_gate_requires_median_and_tail():
    result = embedding_gate(EmbeddingParity(
        median_cosine=0.995,
        p01_cosine=0.980,
        minimum_cosine=0.90,
        mean_l2=0.0,
        p95_l2=0.0,
    ))
    self.assertTrue(result.passed)
```

Add tests for row misalignment, missing outputs, zero vectors, NaN/Inf, dequantization scale/offset, reused versus recalibrated threshold and deterministic online arrival order.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_benchmark -v
```

Expected: FAIL because `scripts.speaker_qnn.benchmark` does not exist.

- [ ] **Step 3: Extract paired FP32/W8A16 embeddings**

Use identical waveforms, FBank implementation, center crops and condition order. Dequantize QNN outputs using context metadata, cast to FP32, L2-normalize, and persist item IDs beside each row.

- [ ] **Step 4: Run parity gate before task metrics**

Require median cosine `>= 0.995` and p01 `>= 0.980`. A gate failure still writes complete parity metrics but blocks threshold recalibration and product admission.

- [ ] **Step 5: Run held-out task matrix**

On the existing 20-speaker evaluation set, compute clean 6/3/2/1 seconds and ESC-50 10/0 dB EER, known-identity Top-1, fixed-k ARI, online ARI and cluster count. Report both reused FP32 threshold and independently recalibrated W8A16 threshold.

- [ ] **Step 6: Commit**

```bash
git add scripts/speaker_qnn/benchmark.py tests/test_speaker_qnn_benchmark.py
git commit -m "test(speaker): validate CAM++ W8A16 accuracy"
```

### Task 6: 测量真机速度、吞吐、温升并生成报告

**Files:**
- Modify: `scripts/speaker_qnn/benchmark.py`
- Create: `scripts/speaker_qnn/report.py`
- Modify: `tests/test_speaker_qnn_benchmark.py`
- Create: `docs/research/2026-10-20-campplus-qnn-sm8845.md`
- Modify: `docs/research/INDEX.md`
- Modify: `docs/superpowers/plans/README.md`

**Interfaces:**
- Consumes:
  - `BuildArtifact(variant_id: str, status: str, context_path: str | None, metadata: ContextMetadata | None, sha256: dict[str, str], commands: tuple[str, ...], error: str | None)`
  - `EmbeddingParity(median_cosine: float, p01_cosine: float, minimum_cosine: float, mean_l2: float, p95_l2: float)`
  - `AccuracyMetrics(eer: float, top1: float, fixed_k_ari: float, online_ari: float, cluster_count: int)`
- Produces:
  - `LatencyMetrics(cold_load_p50_ms: float, cold_load_p95_ms: float, graph_p50_ms: float, graph_p95_ms: float, graph_p99_ms: float, end_to_end_p50_ms: float, end_to_end_p95_ms: float, throughput_ips: float)`
  - `SoakMetrics(duration_s: int, successful_runs: int, failed_runs: int, max_battery_temp_c: float, max_skin_temp_c: float | None, median_graph_ms: float, final_graph_ms: float)`
  - `run_latency_benchmark(artifact: BuildArtifact, warmups: int, measured: int, perf_profile: str) -> LatencyMetrics`
  - `run_soak(artifact: BuildArtifact, duration_s: int, interval_s: float) -> SoakMetrics`
  - `render_report(incident: dict[str, object], benchmark: dict[str, object]) -> str`

- [ ] **Step 1: Write failing latency and report tests**

```python
def test_latency_uses_measured_runs_after_warmup():
    metrics = summarize_latency(WARMUP_AND_MEASURED_EVENTS, warmups=100)
    self.assertEqual(metrics.graph_p50_ms, EXPECTED_MEASURED_P50)

def test_report_never_uses_timeout_as_latency():
    report = render_report(INCIDENT_WITH_TIMEOUT, BENCHMARK_WITHOUT_SUCCESS)
    self.assertNotIn("10,000 ms 推理延迟", report)
    self.assertIn("FastRPC timeout", report)
```

Add tests for percentile definition, profile unit conversion, cold/warm separation, two-context transfer accounting, dropped runs, thermal sample gaps and deterministic Markdown regeneration.

- [ ] **Step 2: Run tests to verify red**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_benchmark -v
```

Expected: FAIL on the new latency/report contracts.

- [ ] **Step 3: Measure cold and warm latency**

Run 20 fresh-process context loads. Then run 100 warmups followed by 1,000 measured inferences for `burst` and `sustained_high_performance`. Report QNN graph time, runner I/O time and CPU FBank time separately; end-to-end is their measured composition, not an estimate.

- [ ] **Step 4: Measure 30 分钟 sustained behavior**

Run a 30-minute 1 Hz soak under `sustained_high_performance`, sampling battery temperature, available skin/SoC thermal zones, frequency state, failures and graph latency. Do not request microphone recording; reuse fixed FBank input.

- [ ] **Step 5: Generate deterministic report**

Report incident timeline, version/config matrix, isolated interval, chosen repair or partition, artifact hashes, paired accuracy, cold/warm latency, p50/p95/p99, throughput and soak. Clearly separate measurements from unavailable metrics.

- [ ] **Step 6: Run focused and repository verification**

Run:

```powershell
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_speaker_qnn_contracts tests.test_speaker_qnn_build tests.test_speaker_qnn_device tests.test_speaker_qnn_probe tests.test_speaker_qnn_benchmark -v
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t .
C:/Users/yaoyue/miniconda3/python.exe -m scripts.speaker_qnn.report --check
git diff --check
```

Expected: focused suite PASS; full suite result reported exactly; report has no drift; `git diff --check` exits 0.

- [ ] **Step 7: Verify provenance and repository hygiene**

Confirm every measured row maps to JSON and profile evidence, every context maps to one build ID/config/hash, no SDK/context/raw/embedding entered git status, and root contains no `tmp_*` build residue.

- [ ] **Step 8: Commit**

```bash
git add scripts/speaker_qnn/benchmark.py scripts/speaker_qnn/report.py tests/test_speaker_qnn_benchmark.py docs/research/2026-10-20-campplus-qnn-sm8845.md docs/research/INDEX.md docs/superpowers/plans/README.md
git commit -m "docs(speaker): report CAM++ SM8845 HTP results"
```

## Final Acceptance

- HTP smoke graph still passes with same-build runtime assets.
- Delivered CAM++ path is either one context or explicitly labeled two-context fallback; no CPU model operators or W8A8 substitution.
- Every delivered context proves `socModel=87` and `dspArch=81`; QAIRT build IDs are not mixed.
- One real 3-second FBank input produces a finite 192-D embedding in less than 1 second.
- Thirty consecutive first-gate runs and 1,000 measured runs complete without FastRPC timeout, SSR or missing output.
- FP32/W8A16 paired cosine median is at least `0.995` and p01 at least `0.980`.
- Accuracy report includes EER, Top-1, fixed-k ARI, online ARI and cluster count under all six existing conditions.
- Speed report includes cold context load, graph p50/p95/p99, I/O, CPU FBank, end-to-end, throughput, burst/sustained profiles and 30-minute soak.
- The 10-second watchdog remains enabled throughout testing and is never reported as inference latency.
- If no eligible toolchain/rewrite/two-context path passes, final status is `blocked` with the smallest isolated node interval and complete reproducible evidence, not a fabricated benchmark.
