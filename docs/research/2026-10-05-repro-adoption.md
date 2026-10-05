# 复现批次采纳执行书 —— 六来源 + 五 PPT skill 对 laos 的实际帮助

> 2026-10-05 ｜ 性质：采纳裁决 + 执行记录（对 [复现报告](2026-10-05-four-article-repro.md) §落点建议的落地）
> 2026-10-05 第二批执行（v0.11.0）：mobile-mcp 评估书采纳项 2/3/4/6 落地（screen.key/longpress/doubletap/devices + 新驱动 drv_apps）；本表 D 项从文档化升级为 `laos/micgeom.py` 实现。

> 原则：**laos 核心零依赖承诺不破坏**（drv_audio 先例：重依赖只存在于驱动子进程）；每项采纳 TDD 进主库；不采纳的写明理由。

## §1 采纳裁决总表

| # | 来源 | 可采纳物 | 裁决 | 落点 |
|---|---|---|---|---|
| A | ④ BS.1770-4 响度 | journal/录音的响度口径（LUFS/True Peak/PLR） | **● 执行** | `laos/loudness.py`（纯 stdlib 移植）+ `drivers/drv_ear.py` 新工具 `ear.lufs` |
| B | ⑤ Pipecat 帧管道 | 打断即作废 + 聚合器放 output 之后（只记实际送达内容） | **● 执行** | `laos/turnbuf.py`（TurnBuffer：数据帧累积/送达水位/打断丢弃/只提交已送达部分进 mem.*） |
| C | ⑥ unique_lock | 锁生命周期显式化（owns_lock/defer/try） | **● 执行** | `laos/locks.py`（UniqueLock）+ `laos/mcp.py` MCPClient._rpc 改用（并记录"为什么此处必须全 spans 持锁"的协议事实） |
| D | ② PhaseCoder MPE | 几何无关麦位元数据约定 + 纯 stdlib 实现 | **● 执行（v0.11.0 升级）** | `laos/micgeom.py`：球坐标 + MPE（相位/频率双调制，α=7/β=4），与 Repro 区 numpy 版逐值一致（max diff 0.0）；驱动约定：外挂音频驱动麦位元数据用 `(M,3)` 质心相对笛卡尔坐标 |
| E | ③ FxLMS ANC | — | **○ 不做** | 车载域 DSP，与 laos 能力管控无交集；保留 Repro 区作语料 |
| F | ① 头部朝向 SHO 全管线 | — | **○ 不做（现在）** | 依赖 torch 训练管线，违反零依赖；"指令定向"记入 drv_mic 远期路线（须过 mic.* 闸+审计+PIPL 声纹红线评估） |
| G | 五 PPT skill | 项目介绍物料 + 方法论 | **◐ 已交付** | docs/ppt/ 五套 deck + 对比 README（上一轮完成）；ppt-master 的"质检门"方法论与本仓库 release 纪律同构，不再重复建设 |

## §2 各项设计决定

### A. laos/loudness.py —— 纯 stdlib 的 BS.1770-4 子集

- 复现区 `Repro-ZCode/repro/bs1770.py` 用了 numpy/scipy；主库零依赖 → **手写转置直接 II 双二阶节 + 分块能量**（O(n) 纯 Python，10s@48k 约 0.5s 内）。
- 范围：K 计权（48k Annex 精确系数 + 任意 fs 参数化）、门控积分响度（400ms/100ms、-70/-10 双门）、Momentary/Short-term、LRA。**True Peak 用"局部峰值 sinc 重构"近似**（只在与峰值相邻的点做带限插值，避免全域 4× FFT）——记档为近似口径（±0.2dB 级）。
- 驱动工具 `ear.lufs(wav)`：读 wav（wave 模块，PCM16）→ `{"lufs":…, "tp_dbtp":…, "plr":…}`；自动过内核闸门与审计（drv 工具天然属性）。

### B. laos/turnbuf.py —— Pipecat 两课进内核语义层

- **课 1（打断即作废）**：`interrupt()` 丢弃未送达尾部——对应 Pipecat 的 InterruptionFrame 清空排队 DataFrame。
- **课 2（聚合器放 output 之后）**：`commit(memory, kind, tags)` 只把**已送达水位**内的文本 mem.remember——被打断没说出口的半句话永远不进记忆（与 laos 记忆闸门同构：记实际发生的交互）。
- 接口：`append(text)`（数据帧）/ `deliver(upto_chars)` 或 `deliver_more(text)`（推进送达水位）/ `interrupt()` / `delivered_text` / `pending_text` / `commit(...)`；线程安全（一把锁，生命周期显式化呼应 C）。

### C. laos/locks.py —— unique_lock 语义 + _rpc 重构

- `UniqueLock(lock, defer_lock=False)`：RAII + 手动 unlock + try_lock + owns_lock（与 Repro 区同语义，但作为主库公共工具）。
- `MCPClient._rpc` 改用 UniqueLock 并在 docstring 记录关键工程事实：**stdio JSON-RPC 的 id 配对要求写-读全程串行，此处不能提前 unlock**（这是文章"锁生命周期要懂协议"的反向教材：不是所有临界区都该收窄）。

### D. 麦位约定（文档级）

外挂音频驱动（load_driver 装载）如暴露空间能力，元数据约定：麦克风坐标 `(M,3)` 笛卡尔米制、相对阵列质心、z 向上——与 PhaseCoder `arbitrary_mic_geometry_embeddings` 入参同口径，保证未来空间前端可直接消费。

## §3 执行清单（TDD）

1. `tests/test_loudness.py`：997Hz@−23dBFS 立体声 → −23.0±0.1；单声道 −26.0；门控剔除静音尾；M/S；LRA；TP 正弦锚点；`ear.lufs` 工具契约（临时 wav）
2. `tests/test_turnbuf.py`：打断丢弃未送达；commit 只记已送达；水位推进；记忆 judge 联动（deny 则零落盘）
3. `tests/test_locks.py`：RAII/提前解锁/defer/try/未持锁解锁抛错；_rpc 行为回归（现有 mcp 测试全绿）
4. 主库全量测试 + Repro 区回归；release v0.10.0（feat 波次）
