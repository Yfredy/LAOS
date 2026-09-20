# 04 · 端侧候选实测（决定是否值得用的关键）

> 本文件是 Task 4 的唯一交付：在本机 **Windows x86 CPU** 上实测 Jev 开源复现的「真数字」，
> 并把结果外推到 laos 的部署环境（Android + proot Ubuntu aarch64、无 NPU、只能 CPU 推理）。
> 任何引用 README 宣称值处都标注 `官方自测`；本机测出的值标注 `第三方`（执行者不是厂商）。
>
> **一句话结论**：唯二「运行时无 torch」的候选里，`yzfly/edgejev` 在本机真跑通了——
> ONNX int8 模型 **324.5 MB**、onnxruntime 运行、3 题批量 **median 157.5 ms**、峰值 RSS **495 MB**、
> 首次加载 **2.1 s**；但 README 宣称的「单题 15.6 ms」是在 **Xeon AVX512-VNNI** 上的硬件特例，
> 本机（AMD Zen3，无 VNNI）实测慢约 10×。**端侧现在能跑，但只能落在离线/非实时路径
> （漏斗③ 蒸馏），不能落在每帧实时路径（漏斗①）；且要先在构建机用 torch 跑一次 `edgejev build`
> 才能拿到模型，仓库本身不发权重。** `wfzyx/von`、`aovestdipaperino/laya-rust` 经静态核查
> 对手机是否决项，未实测。

---

## 1. 方法与环境

- **实测机**：Windows 11，AMD64 Family 25 Model 68（AuthenticAMD，即 **AMD Zen 3**，**无 AVX512-VNNI**），16 逻辑核。
- **隔离环境**：`C:\Users\yaoyue\.workbuddy\binaries\python\envs\default`（Python 3.11.9 venv），装 `edgejev[build]` + `onnxscript` + `psutil`。
- **脚本**：`scripts/bench_jev_local.py`（warmup 1 次后 n=30，取 median/p95；后台线程用 psutil 采样峰值 RSS；记录首次加载耗时与模型目录体积）。
- **基准负载**：与 edgejev README 一致的 3 题样例（choice 路由 + noul 紧急度 + score 情绪），代表 laos 一次 state 的真实决策量。
- **外推声明**：本机 x86 → laos aarch64 **没有可靠换算系数**，下文所有 aarch64 数字均为量级估计，并显式写假设。

---

## 2. Step 1 · 静态可行性预筛（读 README，不下载模型）

对计划指定的 2–3 个优先候选，读 README / pyproject / Cargo.toml 回答四问（基座、是否自训、依赖、体积）：

| 候选 | 基座模型 / 参数量 | 是否自训 | 运行时依赖 | 模型体积 | 是否提供权重 | 端侧风险 |
|---|---|---|---|---|---|---|
| `yzfly/edgejev` | laya / **mmBERT-base 322M**（上游 `convaiinnovations/laya-multilingual`） | 是（需构建期训练/导出） | **运行时不依赖 torch**：仅 onnxruntime + tokenizers + numpy；构建期才需 torch | fp32 ONNX 1290 MB → int8 **324 MB** | **否**，仓库只发导出代码，`edgejev build` 从 HF 拉上游 checkpoint | 最低：拿到了 324 MB int8 即可上 ARM（int8 走 SDOT） |
| `wfzyx/von` | 自有 395M 参数模型（1.5 GB） | 是（权重已在 HF `wfzyx/von-1.0`） | **torch>=2.0 + transformers + accelerate**，`requires-python>=3.12` | **1.5 GB** | 是（HF） | 高：torch + 1.5 GB 权重，手机无法跑；且本机 Python 3.11 不满足 3.12 |
| `aovestdipaperino/laya-rust` | 同 laya 家族（ModernBERT-large 28 层） | 是 | **纯 Rust / candle**（无 torch、无 ONNX） | 权重 ~847 MB（f16 盘上，加载时 upcast f32） | 是（HF，Apache-2.0 ungated） | 高：需 cargo 工具链（本机无）；candle 强制 f32 注意力掩码 → **峰值内存 ~2.4 GB** |

**结论**：只有 `edgejev` 的运行时是 torch-free（onnxruntime），且产出 324 MB int8 适合手机；
`von` 与 `laya-rust` 虽然名义上「端侧」却分别卡在 torch/1.5GB 与 cargo/2.4GB RAM，对 laos 手机是否决项。

---

## 3. Step 2 · 本机实测结果

### 3.1 `yzfly/edgejev` —— 跑通（真实数字）

构建链：本机 pip 装 `edgejev[build]`（含 torch/transformers/laya）→ `edgejev build --backend laya` 从
本地克隆的 `convaiinnovations/laya-multilingual` checkpoint 导出 ONNX 并 int8 量化（API 经代理 502，
改用 `git lfs clone` 拉权重后 `--model` 指向本地目录绕过）。

> 注：`edgejev build` 的 `verify()` 末尾「批次无关性」自检因 edgejev 0.2.1 自身代码 bug
> （`edgejev.backends.laya` 无 `prepare` 属性）报 `AttributeError` 而退出码非 0，但**模型产物已先于该步完整写出**，
> 且三项核心自检（三题/单题长 state/八选项中文）全部 `[OK]`。模型可用，故直接基准。

**模型产物**（`jev-int8/`）：`model.onnx` **324.5 MB** + `tokenizer.json` 34.4 MB + `edgejev.json` ≈ **359 MB** 总体积。

**推理实测（本机 x86，provider=CPU win32 AMD64，3 题批量，n=30，warmup 不计入）**：

| 指标 | 数值 | 说明 |
|---|---|---|
| 首次加载耗时 first_load | **2144 ms** | Agent 构造 + 加载 324 MB onnx + 初始化 onnxruntime 会话；常驻场景必须常驻，不能频繁启停 |
| median 延迟 | **157.5 ms** | 单次 `system_one`（3 题齐发，单 forward pass） |
| p95 延迟 | **233.1 ms** | 同上 |
| min / max | 129.1 / 268.2 ms | 同上 |
| 峰值 RSS | **494.8 MB** | 加载 + 推理全程采样峰值（含 324 MB 模型驻留） |
| 模型目录体积 | 358.9 MB | 落盘需求 |
| 推理结果抽样 | dept=`billing`, urgent=`0.0095`, anger=`1.76` | 输入「信用卡被扣了两次款」→ 路由 billing、低紧急、中等情绪，合理 |

**与 README 宣称的一致性核查**：
- README 称「单题 15.6 ms、模型 324 MB、运行时不依赖 torch」。→ **模型体积 324.5 MB ✓ 一致**；
  **运行时无 torch ✓ 一致**（benchmark 进程仅 import onnxruntime，峰值 RSS 495 MB 不含 torch）。
- **延迟不一致（重点）**：README 的 15.6 ms 是在 **4 vCPU Intel Xeon Cascade Lake（AVX512-VNNI）** 上测的；
  本机是 **AMD Zen 3（无 AVX512-VNNI）**，int8 只能走 AVX2，实测 3 题批量 **157.5 ms（单题量级约 80–130 ms）**，
  比 README 慢约 **10×**。`15.6 ms` 是硬件特例数字，**不能外推到普通 CPU / aarch64**。

### 3.2 `wfzyx/von` —— 未实测（静态判定否决）

- `von-sdk` 依赖 `torch>=2.0` + `transformers` + `accelerate`，`requires-python>=3.12`（本机 3.11 不满足）。
- README 自称 CPU 延迟 **~480 ms**（其 GPU/MPS 才 ~18 ms，所谓「sub-25ms」是 GPU 数字，非 CPU）。
- 权重 1.5 GB + torch 运行时，对手机是否决项（无 NPU、存储与 RAM 都吃紧）。**结论：端侧不可跑，不实测。**

### 3.3 `aovestdipaperino/laya-rust` —— 未实测（静态判定否决）

- 纯 Rust/candle，无 torch，但**需 cargo 工具链**（本机未安装，proot 手机也没有）。
- README 明示 f16 权重加载时 upcast f32，**峰值内存 ~2.4 GB**（candle 强制 f32 注意力掩码），权重 847 MB。
- laos 手机常驻场景下 2.4 GB RAM 是硬否决。**结论：端侧不可跑，不实测。**

### 3.4 覆盖范围说明

`02-oss-reproductions.md` 的其余 47 个复现候选，本次**未逐个实测**（时间/资源所限），其 `端侧可跑` 在 02 中均标
`unknown(未实测)`。其中 `Heman10x-NGU/Verdict-open-jev`（计划第 3 优先）属「真复现」类、基座参数量未公开、
需自训/权重，归为 `unknown(未实测)`；其余多为单 token 打分（借现成 LM 首 token）或文档型，端侧价值更低。
如需后续实测，优先级建议：`Verdict-open-jev`（若放出小基座权重）> 任意单 token 打分（需先解决 torch/LM 权重）。

---

## 4. Step 3 · 外推到 proot aarch64（显式假设，无量级保证）

**核心声明**：x86 Windows → aarch64 proot 的延迟/功耗**没有可靠换算系数**。下面三档均为量级估计。

**假设与来源**：
- A. 端侧数字来源：本机 median 157.5 ms（3 题批量，x86 无 VNNI，onnxruntime CPU EP，int8 动态量化）。
- B. aarch64 上 onnxruntime int8 走 **SDOT**（edgejev README「Linux ARM：CPU，int8 走 SDOT」）；SDOT 单 op 吞吐优于 x86 AVX2 但手机 Cortex-A 核心更弱/核数更少 → 净延迟**不确定**，估计 **100–400 ms / 3 题批量**（与 x86 同量级区间）。
- C. 功耗阶梯（口径文件 Global Constraints 6）：定制 ASIC 0.047–1 µW / 专用音频 NPU 140 µW / aDSP·Sensing Hub <1 mA / 通用 MCU·AP 26–50 mW / **通用 Linux 空闲 400–1000 mW** / 手机 NPU 持续 1–4 W。laos 拿不到 NPU，按「通用 Linux 空闲 + 主动推理」估。

**三档估算（每天 N 次判断 × 单次能耗）**：

| 档 | 场景 | 单次延迟估计 | 单次能耗估计 | 每日 N 次的总额外功耗 |
|---|---|---|---|---|
| 低 | 仅离线路径（漏斗③ 蒸馏、记忆召回），N≈100–1000 次/天 | 100–400 ms | ≈0.15–0.4 J（按 ~0.5–1.5 W 主动推理） | 数十–数百 mJ/天，可忽略 |
| 中 | 触发后二级确认（漏斗① 边界段才调 Jev），N≈1000–5000 次/天 | 同上 | 同上 | 0.5–2 J/天，约 0.1–0.2 mW 常摊，可接受 |
| 高（否决） | 漏斗① 每帧实时调用（常驻检测每帧都过 Jev） | 同上 | 同上 | 若 1 次/秒 → 持续 ~0.5–1.5 W 附加，手机不可承受 → **否决** |

**常驻额外功耗公式**：`P_extra ≈ N_day × t_infer(s) × P_active(W) / 86400`。取 t_infer=0.2 s、P_active=1 W、N=2000：
`P_extra ≈ 2000 × 0.2 × 1 / 86400 ≈ 4.6 mW` 常摊——落在「离线/二级确认」档可忽略；落到「每帧」档则数百 mW 起，否决。

**模型驻留成本**：324 MB 模型常驻 → RSS ~500 MB，Linux 空闲功耗档（400–1000 mW）的一部分需长期承担，但只要不频繁启停（首次加载 2.1 s），属一次性/常驻成本。

---

## 5. 候选对比表（12 列 schema，列名逐字照抄口径文件）

| 项目 | 类别 | 星数 | 语言 | 许可 | 运行时依赖 | 端侧可跑 | 原语 | 报告延迟 | laos 落点 | 验证状态 | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| yzfly/edgejev | 复现 | 2 | Python | Apache-2.0 | onnx | yes | 组合 | 157.5 ms 第三方（3题批量,x86无VNNI） | 漏斗③蒸馏 / 漏斗①(需两级,常驻) | 已实测 | https://github.com/yzfly/edgejev |
| wfzyx/von | 复现 | 117 | Python | Apache-2.0 | torch | no | 组合 | 约480 ms 官方自测（CPU;GPU称sub-25ms） | 漏斗③蒸馏 | 仅README | https://github.com/wfzyx/von |
| aovestdipaperino/laya-rust | 复现 | 1 | Rust | Apache-2.0 | rust | no | 组合 | 未实测 | 漏斗③蒸馏 | 仅README | https://github.com/aovestdipaperino/laya-rust |

> 许可更正：`yzfly/edgejev` 在 02 文档被 GitHub 自动识别为 `NOASSERTION`，本任务直接读其
> `pyproject.toml` 与 README 徽章，实为 **Apache-2.0**，此处以实测源码为准。
> 其余 47 个复现候选的端侧判定见 `02-oss-reproductions.md`（均 `unknown(未实测)`），本次未逐个实测。

---

## 6. 结论（一句话）

端侧现在**能跑** `yzfly/edgejev`（ONNX int8，324 MB，onnxruntime，无 torch），但实测延迟比 README 的
15.6 ms 慢约 10×（本机无 VNNI），且须先在构建机用 torch 跑 `edgejev build` 才能拿到权重、且只能落
**离线/二级确认**路径（漏斗③），**不能落每帧实时路径（漏斗①）**；`von`/`laya-rust` 对手机是否决项，未实测。
