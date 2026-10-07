# 埋点核心实现（telemetry-implementation）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 v0.20.0 埋点设计落成 `laos/telemetry.py` 可用核心（零依赖），含节流/脱敏强制/轮转/LAOS_REC=0 联动/崩溃 flush；给 wakegate/dialogsched 接最小发射钩子；修 laosweb 轮转下 seq 去重键；清 T3 遗留 len 标签漂移；发版 v0.21.0。

**Architecture:** Emitter 单类管 JSONL 落盘（写临时文件+os.replace 原子追加语义沿用 write_jsonl 先例）、每事件类 5s 节流、64MB 轮转；RedactionPolicy 按 v0.20.0 设计的 137 字段表逐事件校验（禁止级字段直接拒发并落 warn）；音频内容类事件挂 LAOS_REC=0 联动静默；模块钩子用可选回调注入（不硬依赖 telemetry——laos 核心零依赖承诺不破）。

**Tech Stack:** 纯 stdlib；unittest；miniconda3 解释器。

**Spec:** docs/design/2026-10-07-instrumentation-design.md（§1 五原则/§3 schema 与字段表/§6 保留与采样/§7 上游对照）——事件与字段的权威定义全在该文档，实现以它为准，冲突时该文档胜过本计划。

## Global Constraints

- 零依赖：laos/ 纯 stdlib；telemetry 不 import 任何第三方。
- 隐私红线落法（设计 §1）：禁止级字段（request/response 明文、音频内容、refine 文本）拒发；内容类只允许 len/sha256 前 8 位/时长/语言码；LAOS_REC=0 时音频内容类事件整体静默。
- 测试数：全部实跑数（-m unittest 逐模块）；全套 697+N。
- 发版：v0.21.0，release.py 函数级 target（next_version 缺新轴的既定裁决沿用，绿闸保留）。

---

### Task 1: laos/telemetry.py 核心 + 测试

**Files:**
- Create: `laos/telemetry.py`
- Test: `tests/test_telemetry.py`

**Interfaces:**
- Produces: `TelemetryEmitter(path, max_bytes=64MB, throttle_sec=5.0, clock=time.monotonic)`；`emit(event, level, module, session, fields)` → bool；`flush()`；`RedactionPolicy`（事件→字段允许表，从设计 §3 派生，含禁止级）；`take_throttled()` 计数。后续任务与实现波次按此调用。

- [ ] **Step 1: 失败测试**（覆盖：schema 信封六键/禁止级字段拒发+warn 落盘/节流 5s 同类丢弃+take_throttled 计数/轮转 64MB 触发 .1 后缀轮换/原子写（.part 中转）/LAOS_REC=0 时 audio 类事件静默/flush 后文件完整可逐行 parse/clock 注入）
- [ ] **Step 2: 红** → **Step 3: 实现**（事件类注册表含设计 §3 的 23 事件最小字段集——至少 6 事件×核心字段；其余事件跑通 schema 即可，逐字段表允许增量注册）
- [ ] **Step 4: 绿 + 全套 697+N** → **Step 5: Commit** `feat(laos): telemetry core — emitter with throttle/redaction/rotation/REC-gate (design v0.20.0)`

### Task 2: wakegate/dialogsched 最小发射钩子

**Files:**
- Modify: `laos/wakegate.py`（状态迁移处可选 `on_event` 回调，默认 None 零行为变化）
- Modify: `laos/dialogsched.py`（DialogQueue.enqueue 与 PauseWindow 取消路径同款可选回调）
- Test: `tests/test_telemetry_hooks.py`

**Interfaces:**
- Consumes: Task 1 `emit` 契约（钩子只传 dict，不 import telemetry——由装配层接线）。
- Produces: `wake.state_change`/`dialog.turn`/`speculative.cancel` 三事件的最小发射点（字段照设计 §3 D 类：from_state/to_state/dialog_id/route 等计数脱敏级）。

- [ ] **Step 1: 失败测试**（注入回调后迁移路径触发、不注入零行为变化、现有测试全不破）→ **Step 2: 红** → **Step 3: 实现**（每处 ≤3 行）→ **Step 4: 绿+全套** → **Step 5: Commit** `feat(laos): minimal telemetry hooks in wakegate/dialogsched (opt-in callbacks)`

### Task 3: laosweb 轮转安全去重键

**Files:**
- Modify: laosweb 侧审计消费去重键（grep 定位 seq 使用处）
- Test: 追加 tests/test_laosweb*.py

**Interfaces:**
- Consumes: 设计 §6.2 轮转使 audit seq 复位的声明。
- Produces: 去重键 seq → (file_epoch, seq) 复合键（或等效方案），轮转后不丢不重。

- [ ] **Step 1: 失败测试**（模拟轮转 seq 重置后两条不同事件不判重）→ **Step 2: 红** → **Step 3: 实现** → **Step 4: 绿+全套** → **Step 5: Commit** `fix(laosweb): rotation-safe audit dedup key (file_epoch, seq)`

### Task 4: 设计文档 len 标签漂移修正 + 登记

**Files:**
- Modify: `docs/design/2026-10-07-instrumentation-design.md`（len 字段"计数/脱敏"标签统一为设计意图级——终审 T3 len 漂移）
- Modify: `docs/research/INDEX.md`（第八节该行关键数补"已实现"一句；机械数核对）

- [ ] **Step 1: 修正+登记** → **Step 2: 全套测试不受影响** → **Step 3: Commit** `docs(design): len field redaction label unified; telemetry implemented note`

### Task 5: 发版 v0.21.0

- [ ] **Step 1**: 全套 697+N 绿 → release.py 函数级 target=0.21.0（绿闸保留）→ CHANGELOG（telemetry 核心落地：23 事件注册表/节流/脱敏强制/轮转/REC 联动 + 三钩子 + laosweb 复合键）→ commit → tag → push → Release 页（json 文件 body；断窗 var/ 重试）
- [ ] **Step 2**: 交付说明

## Self-Review

- 覆盖：telemetry 核心 ✅ 钩子 ✅ laosweb seq ✅ len 漂移 ✅ 发版 ✅；设计文档为 spec 且冲突时胜出 ✅；零依赖/红线/实跑数三约束贯穿 ✅；Task 2 不破既有 697（钩子默认 None）✅。
