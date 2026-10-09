# AuraSE 取长补短落地实施计划 —— evolve 奖励治理面 + 幻觉三维审计立约

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 [AuraSE-IPO 调研](../../research/2026-10-09-aurase-ipo.md) §4 的可执行裁决落进 laos：多目标奖励聚合面（防单指标 hacking 的权重结构 + 版本化锚点）进 `laos/evolve.py`，`evolve.run` 审计链记录奖励构成版本（权重变更可追溯），drivers 层立"生成式音频组件三维幻觉审计"约定。

**Architecture:** 纯加法三件——`RewardSpec`+`aggregate()` 是 evolve 侧的纯函数奖励面（语义源=复现区 `zones/Repro-ZCode/repro/aurase_ipo.py` 已 94 绿的规则版：utterance 内 min-max 归一 + lower-better 翻转 + 加权和；核心侧独立转译、独立测试，不 import 复现区）；`EvolveResult` 加两个带默认值的可选字段（`from_payload` 容缺，旧六字段 payload 照过，`evolve.run` 不带奖励时行为字节级不变）；`drivers/README.md` 立模块地图与三维审计约定（WER=词法/SBS=语义/SIM=说话人，评测维度即失败维度，不发明第四维）。

**Tech Stack:** Python 3 stdlib only（math/dataclasses/frozenset）；测试 unittest（主套件 `tests/`，Windows 宿主直跑）。

**Spec:** `docs/research/2026-10-09-aurase-ipo.md` §4.1（#2 多目标权重结构 ◐P2、#1 幻觉三维 schema ●）与 §4.2（#1 奖励模型/权重变更走治理——版本化锚点）；语义参考实现 `zones/Repro-ZCode/repro/aurase_ipo.py`（本计划只学语义零 import）。执行者先读调研 §4 与复现模块 docstring。

## Global Constraints

- 零依赖红线：`laos/evolve.py` 只准 stdlib；**不 import zones/ 复现区任何代码**（语义转译，测试独立手算锚点）。
- 纯加法：不携带 reward 时 `evolve.run` syscall 行为与审计行**字节级不变**（现有全量测试是回归保障；跑 `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q` 必须全绿——当前基线以实跑为准，本波只增不减）。
- Windows python：`C:/Users/yaoyue/miniconda3/python.exe`；conda 红线（不 pip install 进本体）。
- 版本号：**本计划不占用版本号**——并行 `aor-waves` 波（录音回放 v0.36.0）在途；本波改动随其后的下一个 MINOR 自然携带，发版走 release.py --apply 全流程（AGENTS.md 发版纪律）。
- 每任务一个 commit（`feat: ...` / `docs: ...`），TDD：先红后绿。
- 计划纪律：写完三查（spec 覆盖/占位符扫描/类型一致性）已执行，记录在文末 Self-Review；跨 Task 引用一律原文重复。

### 明确不做（防走偏，继承调研 §4.3 与本计划范围裁决）

1. **不改 jitmem curator 的确定性选择**——调研 ◐#4 的"差距比例采样借鉴"经评估不落地：curator 的确定性 top-k 是可调试/可复现特性，向记忆 briefing 引入随机化有害无益；AuraSE 的采样服务于训练信号多样性，JitMem 没有对应问题。
2. **不做 SE/生成式音频组件本体**（零依赖+AGC 落地篇红线：生成式产出只进评测副本不进记忆副本）。
3. **不动 telemetry.py 事件分类学**（23 事件/138 字段已冻结过设计评审；三维约定立在 drivers/README.md，未来真有生成式驱动接入时再走 telemetry 设计增量）。

---

### Task 1: `RewardSpec` + `aggregate()` 奖励治理面（TDD，纯函数）

**Files:**
- Modify: `laos/evolve.py`（文件尾部 `status()` 之后追加；`__all__` 同步）
- Test: `tests/test_evolve.py`（追加 `TestRewardSpec` / `TestAggregate` 两类）

**Interfaces:**
- Consumes: 无（纯新函数）。
- Produces（Task 2 的驱动与未来 gate 排序消费的精确签名）:
  - `RewardSpec(weights: dict[str, float], lower_better: frozenset[str] = frozenset(), version: str = "v0")`（frozen dataclass；校验 fail-loud：weights 非空且值全 >0、lower_better ⊆ weights 键、version 非空串）
  - `aggregate(candidates: dict[str, dict[str, float]], spec: RewardSpec) -> dict[str, float]`——candidates 为 候选名→各指标值（同一话语/作业的 M 个候选），返回 候选名→奖励 ∈ [0,1]（全指标垫底=0.0 闭端）；归一化=候选集内 min-max（无区分度指标给全员 1.0 中性满分），lower_better 指标翻转，加权和按权重和归一。

- [ ] **Step 1: 追加失败测试**

在 `tests/test_evolve.py` 末尾（`if __name__ == "__main__":` 之前）追加，import 区补 `from laos.evolve import RewardSpec, aggregate`（追加到现有 `from laos.evolve import (...)` 括号内，按字母序）：

```python
class TestRewardSpec(unittest.TestCase):
    def test_valid_spec(self):
        s = RewardSpec({"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0},
                       frozenset({"WER"}), version="aurase-4222")
        self.assertEqual(s.version, "aurase-4222")

    def test_empty_or_nonpositive_weights_rejected(self):
        for bad in ({}, {"OVRL": 0.0}, {"OVRL": -1.0}):
            with self.assertRaises(ValueError) as cm:
                RewardSpec(bad)
            self.assertIn("EINVAL", str(cm.exception))

    def test_lower_better_must_be_subset(self):
        with self.assertRaises(ValueError):
            RewardSpec({"OVRL": 1.0}, frozenset({"WER"}))

    def test_blank_version_rejected(self):
        with self.assertRaises(ValueError):
            RewardSpec({"OVRL": 1.0}, version="")


class TestAggregate(unittest.TestCase):
    # 调研文档 §3 手算例的独立复算（与复现区测试各自独立，不共享代码）：
    # OVRL [3.0,3.2,3.4]→[0,.5,1]；WER(lower) [.10,.08,.12]→[.5,1,0]；
    # SIM [.70,.75,.75]→[0,1,1]；SBS [.90,.90,.88]→[1,1,0]；
    # 4:2:2:2（和 10）→ cand0=0.3 / cand1=0.8 / cand2=0.6
    CANDS = {
        "c0": {"OVRL": 3.0, "WER": 0.10, "SIM": 0.70, "SBS": 0.90},
        "c1": {"OVRL": 3.2, "WER": 0.08, "SIM": 0.75, "SBS": 0.90},
        "c2": {"OVRL": 3.4, "WER": 0.12, "SIM": 0.75, "SBS": 0.88},
    }
    SPEC = RewardSpec({"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0},
                      frozenset({"WER"}), version="aurase-4222")

    def test_hand_computed_4222(self):
        r = aggregate(self.CANDS, self.SPEC)
        self.assertEqual(
            [round(r["c0"], 10), round(r["c1"], 10), round(r["c2"], 10)],
            [0.3, 0.8, 0.6])

    def test_winner_not_ovrl_best(self):
        # 4:2:2:2 下总分王 c1 不是 OVRL 最高的 c2——保真 60% 拉回内容
        r = aggregate(self.CANDS, self.SPEC)
        self.assertEqual(max(r, key=r.get), "c1")

    def test_constant_metric_is_neutral_full(self):
        cands = {"a": {"Q": 1.0, "F": 0.5}, "b": {"Q": 1.0, "F": 0.9}}
        spec = RewardSpec({"Q": 1.0, "F": 1.0}, version="t")
        self.assertEqual(aggregate(cands, spec),
                         {"a": 1.0, "b": 1.0})  # 双指标无区分度 → 中性满分

    def test_rewards_within_unit(self):
        r = aggregate(self.CANDS, self.SPEC)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in r.values()))
        # 全指标垫底的候选恰好得 0.0（值域闭端）
        worst = {"w": {m: (max(c[m] for c in self.CANDS.values())
                           if m == "WER" else
                           min(c[m] for c in self.CANDS.values()))
                       for m in self.SPEC.weights}}
        merged = dict(self.CANDS, **worst)
        self.assertEqual(aggregate(merged, self.SPEC)["w"], 0.0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve.TestRewardSpec tests.test_evolve.TestAggregate -v`
Expected: ERROR——`ImportError: cannot import name 'RewardSpec'`。

- [ ] **Step 3: 最小实现**

`laos/evolve.py`：`__all__` 列表加入 `"RewardSpec"` 与 `"aggregate"`（保持字母序），`status()` 函数之后追加：

```python
@dataclass(frozen=True)
class RewardSpec:
    """多目标奖励规格（AuraSE IPO 4:2:2:2 的 laos 化：防单指标 hacking
    的权重结构 + 版本化锚点——权重变更=新 version，经审计可追溯）。

    约定（docs/research/2026-10-09-aurase-ipo.md §4.1#2）：涉及
    质量/保真两类指标的 spec，保真份额建议 ≥60% 起步（ AuraSE
    OVRL:WER:SIM:SBS = 40%:60% 的配比是防 hacking 的实证模板）。
    """
    weights: dict[str, float]
    lower_better: frozenset[str] = frozenset()
    version: str = "v0"

    def __post_init__(self):
        if not self.weights or any(w <= 0 for w in self.weights.values()):
            raise ValueError(
                f"EINVAL: RewardSpec.weights 须非空且全为正，实测 {self.weights}")
        if not self.lower_better <= self.weights.keys():
            raise ValueError(
                f"EINVAL: lower_better {sorted(self.lower_better)} 须为 "
                f"weights 键子集 {sorted(self.weights)}")
        if not self.version:
            raise ValueError("EINVAL: RewardSpec.version 不得为空串")


def aggregate(candidates: dict[str, dict[str, float]],
              spec: RewardSpec) -> dict[str, float]:
    """候选集内多目标聚合：逐指标 min-max 归一（无区分度→全员 1.0）、
    lower_better 翻转、加权和按权重和归一。返回 候选名→奖励 ∈ [0,1]
    （全指标垫底=0.0 闭端）。

    语义源=zones/Repro-ZCode/repro/aurase_ipo.py（零 import，独立转译）；
    归一化在候选集内进行——集内单指标排序不变，加权交互后语义完好。
    """
    if not candidates:
        return {}
    names = list(candidates)
    total_w = sum(spec.weights.values())
    out: dict[str, float] = {}
    per_metric: dict[str, list[float]] = {}
    for metric, w in spec.weights.items():
        vals = [candidates[n][metric] for n in names]
        lo, hi = min(vals), max(vals)
        if hi == lo:
            norm = [1.0] * len(vals)  # 无区分度：中性满分（保序恒等）
        else:
            norm = [(v - lo) / (hi - lo) for v in vals]
        if metric in spec.lower_better:
            norm = [1.0 - x for x in norm]
        per_metric[metric] = norm
    for i, n in enumerate(names):
        out[n] = sum(w * per_metric[m][i] for m, w in spec.weights.items()
                     ) / total_w
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v`
Expected: 全 PASS（既有 18 例 + 新增 8 例 = 26；18 为 2026-10-09 实测 grep `def test` 计数）。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 全绿（只增不减）。

- [ ] **Step 6: Commit**

```bash
git add laos/evolve.py tests/test_evolve.py
git commit -m "feat: evolve 奖励治理面——RewardSpec+aggregate（AuraSE 4:2:2:2 防单指标 hacking + 版本化锚点）"
```

---

### Task 2: `EvolveResult` 可选 reward 字段 + `evolve.run` 审计记版本（TDD）

**Files:**
- Modify: `laos/evolve.py`（`EvolveResult` 加两字段；`from_payload` 容缺）
- Modify: `laos/kernel.py`（`_impl_evolve_run` 审计行条件记 `reward_version`）
- Test: `tests/test_evolve.py`（`TestPayload` 追加两例；`TestEvolveSyscall` 追加两例）

**Interfaces:**
- Consumes: Task 1 的 `RewardSpec`（驱动侧组装 detail 时用其 version；本任务核心侧只透传字符串与字典，不消费聚合函数）。
- Produces: `EvolveResult.reward_version: str = ""`、`EvolveResult.reward_detail: dict | None = None`（`from_payload` 对缺键容错——旧六字段 payload 照常构造，两字段取默认）；kernel `event:"evolve"` 审计行新增**条件键** `reward_version`（仅当非空串时写入——不带奖励的既有作业审计行字节级不变）。

- [ ] **Step 1: 追加失败测试**

`tests/test_evolve.py` 的 `TestPayload` 类内追加两例：

```python
    def test_optional_reward_fields_roundtrip(self):
        p = self._payload()
        p["reward_version"] = "aurase-4222"
        p["reward_detail"] = {"OVRL": 3.367, "WER": 8.22, "weights": "4:2:2:2"}
        r = EvolveResult.from_payload(p)
        self.assertEqual(r.reward_version, "aurase-4222")
        self.assertEqual(r.reward_detail["WER"], 8.22)

    def test_legacy_payload_without_reward_still_constructs(self):
        r = EvolveResult.from_payload(self._payload())  # 旧六字段
        self.assertEqual(r.reward_version, "")
        self.assertIsNone(r.reward_detail)
```

`TestEvolveSyscall` 类内追加一例：

```python
    def test_audit_records_reward_version_when_present(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d",
            reward_version="aurase-4222"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertEqual(events[-1].get("reward_version"), "aurase-4222")

    def test_audit_omits_reward_version_when_absent(self):
        register_executor(lambda job: EvolveResult(
            0.9, "var/rsi/jobs/d/out.py", "ab" * 32, 5, 1.0, "var/rsi/jobs/d"))
        self._pcb(["evolve.*"])
        res = asyncio.run(self.k.syscall(1, "evolve.run", self._args()))
        self.assertTrue(res.ok, getattr(res, "error", res))
        events = [r for r in self.k.audit.records if r.get("event") == "evolve"]
        self.assertNotIn("reward_version", events[-1])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve.TestPayload tests.test_evolve.TestEvolveSyscall -v`
Expected: 新四例 FAIL/ERROR（`from_payload` 构造无此字段 / `EvolveResult` 不接受 `reward_version` 关键字 / 审计行无该键）。

- [ ] **Step 3: 实现（三处小改）**

`laos/evolve.py` 的 `EvolveResult`（现六字段 dataclass）尾部加两行字段：

```python
@dataclass
class EvolveResult:
    best_score: float
    best_program_path: str
    best_program_sha256: str
    iterations_completed: int
    elapsed_s: float
    artifacts_dir: str
    # AuraSE 锚点相对性纪律（调研 §4.2#1）：奖励构成版本化进审计可追溯；
    # 不携带时两字段为空——既有作业行为与审计行字节级不变
    reward_version: str = ""
    reward_detail: dict | None = None
```

同文件 `from_payload` 在构造处（`artifacts_dir=str(payload["artifacts_dir"])` 之后）补两行，保持其余校验不动：

```python
        r = cls(best_score=float(payload["best_score"]),
                best_program_path=str(payload["best_program_path"]),
                best_program_sha256=str(payload["best_program_sha256"]),
                iterations_completed=int(payload["iterations_completed"]),
                elapsed_s=float(payload["elapsed_s"]),
                artifacts_dir=str(payload["artifacts_dir"]),
                reward_version=str(payload.get("reward_version", "")),
                reward_detail=payload.get("reward_detail"))
```

（`from_payload` 的 `try` 块只包原六键——`reward_*` 两键用 `.get` 容缺，不进 fail-loud 校验面；`reward_detail` 若驱动给了非 dict 则原样透传，类型纪律归驱动侧。）

`laos/kernel.py` 的 `_impl_evolve_run` 审计行改为（在 `"sha256": result.best_program_sha256})` 之前插入条件键）：

```python
        evolve_event = {"t": time.time(), "event": "evolve", "op": "run",
                        "pid": pcb.pid, "target": job.target,
                        "iterations": result.iterations_completed,
                        "best_score": result.best_score,
                        "sha256": result.best_program_sha256}
        if result.reward_version:
            evolve_event["reward_version"] = result.reward_version
        self.audit.write(evolve_event)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v`
Expected: 全 PASS（既有 18 + Task 1 的 8 + 本任务 4 = 30 例）。

- [ ] **Step 5: 全量回归**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`
Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add laos/evolve.py laos/kernel.py tests/test_evolve.py
git commit -m "feat: EvolveResult 可选 reward 字段+审计记 reward_version——奖励构成版本化（AuraSE 锚点治理）"
```

---

### Task 3: `drivers/README.md` —— 模块地图 + 幻觉三维审计立约

**Files:**
- Create: `drivers/README.md`

**Interfaces:**
- Consumes: Task 1 的 `RewardSpec`/`aggregate`（用法示例引用其签名原文：`RewardSpec(weights: dict[str, float], lower_better: frozenset[str] = frozenset(), version: str = "v0")`、`aggregate(candidates: dict[str, dict[str, float]], spec: RewardSpec) -> dict[str, float]`）；Task 2 的 `EvolveResult.reward_version: str = ""` / `reward_detail: dict | None = None`。
- Produces: drivers 层唯一入口文档（目录纪律：一端一目录各带 README 的 drivers 版；未来加驱动先在此登记——与 `clients/android/` README 同款地位）。

- [ ] **Step 1: 写 README 全文**

```markdown
# drivers/ —— 重依赖驱动子进程（laos 核心零依赖的代价转移层）

> laos/ 核心纯 stdlib；一切重依赖（云 API/本地模型/venv 生态）只活在本目录
> 的子进程里，经 import 即登记的装配面接进核心（`register_executor`/
> `register_backend` 哲学，drv_clef/drv_evolve 先例）。核心不 import 本目录
> 任何模块；不 import 对应驱动时 syscall 面 fail-loud（ENODEV）。

## 模块地图（加新驱动先在此登记一行）

| 驱动 | 装配点 | 形态 |
|---|---|---|
| drv_clef.py | laos/decide.py 判断层 | Cloudflare Clef 决策模型 HTTP（远端） |
| drv_evolve.py + openevolve_job.py | laos/evolve.py `register_executor` | OpenEvolve venv 子进程（CLI 稳定面） |
| drv_ear/rec/mic/npu/screen/... | kernel 各 drv_* syscall | 端侧能力子进程（adb/QNN/SAPI 等） |
| drv_audio/genie/apps/... | 同上 | 其余端侧/服务驱动 |

## 奖励治理面（2026-10-09 起，AuraSE-IPO 采纳）

涉及"候选打分/排序"的驱动（evolve 类优先）用 `laos.evolve.RewardSpec` +
`aggregate()` 组装多目标奖励，把 `spec.version` 透传进
`EvolveResult.reward_version`（`reward_detail` 放指标值与权重构成）——
审计行即记录奖励构成版本，权重变更=新版本号，历史可追溯不可变。

约定：质量/保真两类指标并存的 spec，**保真份额 ≥60% 起步**
（AuraSE OVRL:WER:SIM:SBS=4:2:2:2 的防单指标 hacking 实证配比）。

## 生成式音频组件三维幻觉审计（约定，触发即生效）

未来任何生成式音频驱动（SE/修复/超分/语音合成类）上线时，其评测与审计
**必须按三维拆分记录幻觉**，不发明第四维（AuraSE 调研 §4.1#1 采纳）：

| 维度 | 失效模式 | 度量形态 |
|---|---|---|
| 词法（WER 类） | 换词/插音/丢字 | 对参照转写（**不得对条件转写**——抄条件不得分） |
| 语义（SBS 类） | 语义漂移 | 对参照语义编码 |
| 说话人（SIM 类） | 音色漂移 | 对参照说话人嵌入 |

红线继承：生成式产出只进评测副本，**不得进记忆副本**（auto-gain/07 与
AuraSE 调研 §4.3——幻觉可压不可灭，最优系统 WER 仍 8.22%）。
```

- [ ] **Step 2: 核对内链与登记**

- `RewardSpec`/`aggregate`/`reward_version` 签名与本 README 所写逐字符一致（防止文档先于代码漂移）。
- AGENTS.md 目录纪律节 `drivers/` 行追加引用：`（自带 README：模块地图+奖励治理面+三维幻觉审计约定）`——一行 Edit。

- [ ] **Step 3: Commit**

```bash
git add drivers/README.md AGENTS.md
git commit -m "docs: drivers/README——模块地图+奖励治理面用法+生成式音频三维幻觉审计立约（AuraSE 采纳）"
```

---

## Self-Review（写完计划后自查记录）

1. **spec 覆盖**：调研 §4.1 #1（三维 schema）→ Task 3 约定节；#2（4:2:2:2 权重结构 ◐P2）→ Task 1 + Task 3 保真 ≥60% 约定；§4.2 #1（权重/奖励模型变更走治理——版本化锚点）→ Task 1 version 字段 + Task 2 审计条件键；#4（差距比例采样 ◐P3）→ 明确不做的理由成文（计划头部"明确不做"#1）；#5（复现资产 ●）→ 已在 baddb0c 完成，不在本计划。未覆盖项均为文档叙事类（#3 锚点相对性纪律、§4.2 #2/#3 已有机制覆盖），无需代码。
2. **占位符扫描**：无 TBD/TODO/"适当处理"；Task 3 README 全文完整给出；Task 2 三处代码改动均给出精确 diff 上下文；唯一外部依赖（手算锚点）在测试注释内自含推导。
3. **类型一致性**：`RewardSpec(weights: dict[str, float], lower_better: frozenset[str] = frozenset(), version: str = "v0")` 在 Task 1 定义、Task 3 README 引用逐字符一致；`aggregate(candidates: dict[str, dict[str, float]], spec: RewardSpec) -> dict[str, float]` 同；`EvolveResult.reward_version: str = ""`、`reward_detail: dict | None = None` 在 Task 2 定义、Task 3 引用一致；`from_payload` 构造参数序与既有六字段序一致（追加尾部）。
4. **风险点**：Task 2 改 `from_payload` 的 `r = cls(...)` 构造调用——若现有实现变量名/缩进与计划引用有出入，以文件现状为准做等价插入（构造实参追加两行 `.get` 容缺）；`asdict(result)` 会把两个新键带进 ok_text JSON——既有断言只查 `payload["best_score"]`，兼容；审计行条件键保证不带奖励时字节级不变。
5. **三查修错记录（2026-10-09 实跑三查抓到并已改）**：①测试计数漂移——初稿写"既有 20 例"，实测 `grep -c 'def test' tests/test_evolve.py` = **18**，Task 1/2 的 Expected 计数全部重算（26/30）；②初稿 `test_hand_computed_4222` 用了一个名不副实的 `assertAlmostEqual3` 辅助（名为 assert 实为造常量），重写为直白 round 断言；③值域声明 (0,1] 错误——全指标垫底候选恰得 0.0，Interface/实现/测试三处统一改为闭区间 [0,1] 并补闭端断言；④Task 2 "追加一例"实为两例（records/omits 各一），已改。
