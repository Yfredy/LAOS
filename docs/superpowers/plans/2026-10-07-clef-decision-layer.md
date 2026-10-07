# 判断层 Clef 落地（clef-decision-layer）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Cloudflare Clef 学习成果落进 laos 判断层：决策 schema（noul/choice/score，Clef 兼容）+ 概率校准度量（Brier/ECE，校准台方法库）+ Clef-flash 本地评测驱动（窗口彩票，诚实 BLOCKED 路径）+ jev/ 对照篇 + 发版 v0.22.0。

**Architecture:** laos 核心零依赖两件：decide.py（类型化决策接口+规则后端，Clef 同 schema——后端可插拔：rules/edgejev/clef/server）；calib.py（校准度量纯数学）。重依赖走 chroot 驱动（drv_clef.py，transformers 4.46.3 后端，Qwen3.5 架构兼容性风险如实记录）。选型表三路线对照（rules 0ms / edgejev 157.5ms / clef-flash 38.8ms@edgeGPU 引用值或本地实测值）。

**Tech Stack:** laos/ 纯 stdlib；驱动 WSL chroot（torch 2.4.1+transformers 4.46.3）；unittest；miniconda3 解释器。

**Spec:** docs/research/2026-10-07-cloudflare-clef.md（§二 Clef 全事实=接口依据；§四 裁决表=范围依据）；laos 判断层既有资产 docs/research/jev/（00 口径/05 落点）。

## Global Constraints

- 零依赖：laos/ 纯 stdlib；重依赖只在驱动子进程/chroot。
- 来源诚实：选型表区分"实测/引用"两口径——38.8ms 是 Cloudflare 边缘 GPU 引用值，本地实测列在拿到权重前留空并标 BLOCKED 原因；不把引用值当实测。
- 测试实跑数；发版 v0.22.0（函数级 target，绿闸保留）。
- HF 下载走断网窗重试脚本（model.bin 先例）；架构不兼容（transformers 4.46.3 不认 Qwen3.5）则驱动任务如实 BLOCKED 收档，不硬造数据。

---

### Task 1: laos/decide.py 决策接口 + 规则后端

**Files:** Create `laos/decide.py`; Test `tests/test_decide.py`

**Interfaces:**
- Produces: `DecisionSchema(type="noul"|"choice"|"score", options=[...], threshold=0.5)`；`Decision(answer, probabilities, source, calibrated=False)`；`RuleBackend.decide(state: dict, schema) -> Decision`（规则打分：阈值/包含匹配，概率来自规则强度的归一化）；`register_backend(name, fn)` 插拔点（Task 3 clef 后端挂此处）。

- [ ] 失败测试：三判型各 1 例（noul 二值/choice 多选归一化/score 连续值+阈值）；未注册后端 KeyError；概率和=1；类型化输出拒越界 → 红 → 实现 → 绿 → 全套（766+N）→ commit `feat(laos): Clef-compatible decision schema + rule backend (noul/choice/score)`

### Task 2: laos/calib.py 校准度量

**Files:** Create `laos/calib.py`; Test `tests/test_calib.py`

**Interfaces:**
- Produces: `brier_score(probs, outcomes) -> float`；`ece(probs, outcomes, bins=10) -> float`；`reliability(probs, outcomes, bins=10) -> [(bucket, avg_p, freq)]`。

- [ ] 失败测试：完美校准 Brier=0/ECE=0；反例手算值；空 bins 边界 → 红 → 实现 → 绿 → 全套 → commit `feat(laos): probability calibration metrics — Brier/ECE/reliability (Clef 校准台方法库)`

### Task 3: drv_clef.py 驱动 + 权重窗口彩票

**Files:** Create `drivers/drv_clef.py`; Create `var/clef_eval/`（gitignored）；Test `tests/test_drv_clef.py`（离线：命令构造/env 契约/输出解析，不触网）

- [ ] 离线 TDD：LAOS_CLEF_CMD env 分支/默认 chroot python 命令构造/JSON 输出解析（answer/probabilities/latency_ms）/超时 → 绿
- [ ] 权重下载：var/ 后台脚本轮询 HF（cloudflare/clef-flash 断网窗 3h，model.bin 先例：SHA 校验后落盘）
- [ ] 到手则 chroot 实测（transformers 加载+短 prompt 决策 20 次取中位）；**架构不兼容或下载耗尽 → BLOCKED 收档**（报告记证据，选型表本地列标"未实测（原因）"）
- [ ] commit `feat(drivers): clef decision driver + eval harness (chroot backend, honest-blocked path)`

### Task 4: jev/ 对照篇 + 登记

**Files:** Create `docs/research/jev/06-clef-mapping.md`；Modify INDEX

- [ ] jev/06：三路线选型表（rules/edgejev/clef-flash：延迟/体积/三判型覆盖/口径标注）+ 非自回归架构定论 + Brier/RLCD 校准节 + Task 3 实测或 BLOCKED 结果
- [ ] INDEX +1 行（jev 组 7→8 份口径机械对齐）+ 全套测试 → commit `docs(research): jev-layer Clef mapping — three-route selection table`

### Task 5: 发版 v0.22.0

- [ ] 全套绿 → release.py 函数级 target=0.22.0 → CHANGELOG（判断层波次：decide/calib 两核心件+clef 驱动+选型表）→ tag → push → Release 页（json 文件法；断窗 var/ 重试）→ 交付说明

## Self-Review

- 覆盖：schema+规则后端 ✅ 校准度量 ✅ clef 实测驱动（含诚实 BLOCKED）✅ jev 对照 ✅ 发版 ✅；引用/实测口径分离贯穿 Task 3/4；零依赖/实跑数/函数级 target 三约束沿用。✅
