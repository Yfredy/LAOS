# AuraSE 取长补短落地 + 调研纪律制度化——波次交接文档

> 2026-10-09 · 波次：小红书 Qwen Audio Agent 调研 → 计划编写纪律制度化 → openevolve 计划续执行（并行协同）→ AuraSE-IPO 论文学习与规则版复现 → aurase-adoption 计划 Subagent-Driven 执行
> 读者：下一位接手的通用 SWE（不预设你了解 AuraSE、laos 或本波历史）
> 体例：按本仓 `docs/guide/llm-handover-methodology.md` 的 L0–L4 五层架构编写；所有命令带实跑输出原文（捕获时点见各节）
> 配套：结构图 `docs/diagrams/aurase-adoption-architecture.html`（archify，证据锚定）与 `aurase-adoption-handover.drawio`（drawio 源）；交接 PPT `docs/ppt/laos-aurase-adoption-handover.html`
> 姊妹交接：`docs/guide/rsi-evolve-handover.md`（openevolve 驱动波，已合并 master 565dec8）——本波的 evolve.run 基座在那边

## L0 生存层：这是什么

**30 秒陈述**：本波把一篇论文（[AuraSE，arXiv 2610.06632v1](../research/2026-10-09-aurase-ipo.md)：低幻觉生成式语音增强，流匹配 + 推理策略优化 IPO）的三个可执行结论落进了 laos：**多目标奖励治理面**（`RewardSpec`+`aggregate`，防单指标 hacking 的 4:2:2:2 权重结构 + 版本化锚点）、**奖励构成审计化**（`evolve.run` 审计行条件记 `reward_version`——权重变更=新版本，历史可追溯不可变）、**生成式音频三维幻觉审计立约**（WER=词法/SBS=语义/SIM=说话人，drivers/README 触发即生效）。外加一件制度：**计划编写纪律**（写完三查/Task 尺寸判据/乱序阅读禁令）进 plans/README.md 与 AGENTS.md。

**是 X 不是 Y**：
- **是** evolve 生态的奖励面与治理升级——纯加法，不携带 reward 时 `evolve.run` 行为与审计行字节级不变（评审者独立验证过：AuditLog 按字典插入序序列化，条件键不改变旧键集与顺序）。
- **不是** SE/生成式音频组件本体——零依赖红线，生成式产出只进评测副本不进记忆副本（auto-gain/07 红线维持）。
- **不是** IPO 神经复现——决策面规则版在 Repro-ZCode（23 测），论文数值一概不断言。

**一句话技术栈**：laos 核心纯 stdlib；复现区 pytest（ zones/Repro-ZCode，不进主套件）；测试 unittest 全离线。

**顶层落点地图**（本波新增/改动）：

| 文件 | 职责 | 关键行锚 |
|---|---|---|
| `laos/evolve.py` | RewardSpec（版本化奖励规格:141）+ aggregate（集内 min-max+翻转+加权:170）+ EvolveResult 可选 reward 字段（:54-55，from_payload 容缺:67-70） | — |
| `laos/kernel.py` | `_impl_evolve_run` 审计行条件记 `reward_version`（:995-996，非空才写） | — |
| `drivers/README.md` | drivers 层唯一入口：模块地图/奖励面用法（保真≥60% 起步）/三维幻觉审计约定 | :19 / :27 |
| `zones/Repro-ZCode/repro/aurase_ipo.py` + `tests/test_aurase_ipo.py` | IPO 决策面规则版（偏好对采样/缓冲/锚点边际/诊断统计），23 例手算锚点 | — |
| `docs/research/2026-10-09-aurase-ipo.md` | 调研 + 裁决（●◐○）+ 复现对账 | §4 取长补短 |
| `docs/superpowers/plans/2026-10-09-aurase-adoption.md` | 实施计划（三任务+三不做+三查修错记录） | 已执行 |
| `docs/superpowers/plans/README.md` | 计划编写纪律节（写完三查等）+ 本波全部登记 | 头部纪律节 |
| `docs/research/2026-10-09-xhs-qwen-audio-agent-runtime.md` | Qwen Audio Agent 2.0 调研（Voice Model ≠ Voice Agent，三链核实零讹变） | INDEX 已登记 |

## L1 冷启动层：怎么跑起来

**解释器**：只用 `C:/Users/yaoyue/miniconda3/python.exe`（conda 红线）。

**主套件**（2026-10-09 22:4x 捕获于 aor-waves@99af75d；含并行录音回放波测试）：

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q
```

```
Ran 1121 tests in ...
OK (skipped=5)
```

**本波面测试**（32 例 = 18 基线 + 8 奖励面 + 4 契约 + 2 边界修复）：

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve -v
```

实跑末行：`Ran 32 tests ... OK`。

**复现区**（不进主套件；决策面规则版）：

```bash
cd zones/Repro-ZCode && C:/Users/yaoyue/miniconda3/python.exe -m pytest tests/ -q
```

实跑（2026-10-09）：`94 passed, 1 warning in 204.88s`（71 基线 + 23 本波）。

**冒烟**（区根目录）：`C:/Users/yaoyue/miniconda3/python.exe scripts/run_repro_all.py`——含 AuraSE-IPO 位（spread/top-win 无占优断言）。

## L2 日常操作层：怎么用这套东西

**奖励面三步**（驱动/编排侧组装，核心侧零改动）：

```python
from laos.evolve import RewardSpec, aggregate
spec = RewardSpec(
    weights={"OVRL": 4.0, "WER": 2.0, "SIM": 2.0, "SBS": 2.0},
    lower_better=frozenset({"WER"}),          # WER 越低越好，自动翻转
    version="aurase-4222")                     # 权重构成版本——变更即升版
rewards = aggregate({"cand_a": {...}, "cand_b": {...}}, spec)
# → {"cand_a": 0.3, ...} ∈ [0,1]；集内 min-max 归一，无区分度指标=中性满分 1.0
```

**审计透传**：执行器把 `spec.version` 填进 `EvolveResult(reward_version=..., reward_detail={...指标值+权重构成})` → `evolve.run` 审计行自动多出 `reward_version` 键（**仅非空时**）；旧六字段 payload 照常构造（from_payload 容缺，null→空串）。

**手算锚点速查**（新测试就用它，别再造）：三候选 4:2:2:2 → [0.3, 0.8, 0.6]，总分王不是 OVRL 最高者（保真 60% 拉回）；全指标垫底=0.0 闭端；θ=锚时 IPO 损失=log 2。

**约定速查**（drivers/README.md 全文为准）：质量/保真两类指标并存的 spec，**保真份额 ≥60% 起步**；未来生成式音频驱动上线必须三维幻觉审计（对参照转写评分，不得对条件转写——抄条件不得分）。

## L3 架构与决策层：为什么长这样

**关键决策记录**（被否掉的方案与理由——别当 bug"修"掉）：

| 决策 | 当时为什么 | 被否方案 |
|---|---|---|
| 版本化锚点（RewardSpec.version + 审计条件键） | AuraSE 论文自认"mitigating 非 eliminating"hacking——奖励模型在循环内被当真值；laos 补位=权重构成变更走版本化审计，历史不可变 | env 可配权重不留痕（变更无迹可查=锚点治理失守） |
| 集内 min-max 归一 | 论文 supplementary 未随 v1 发布；集内归一保序，加权交互后语义完好（诚实偏差登记在复现区 README） | 全局固定区间归一（跨集可比但无一手依据，编造） |
| 审计行**条件**记 reward_version | 纯加法约束：不带奖励的既有作业审计行字节级不变 | 恒记空串（旧行漂移，回归面扩大） |
| jitmem curator 不引入差距比例采样 | 确定性 top-k 是可调试/可复现特性；briefing 随机化有害无益 | 照搬 IPO 采样（训练信号多样性 ≠ 记忆检索需求） |
| SE 本体/telemetry 冻结面不动 | 零依赖；23 事件/138 字段过设计评审冻结 | 本波顺手扩 telemetry（越权） |
| 复现区独立转译（零 import） | laos 核心 vs 复现区两棵树职责不同；测试锚点各自独立 | 核心 import 复现区（树间耦合，零依赖红线） |

**Subagent-Driven 执行实录**（本波是 SDD 技能的完整首跑）：T1-T3 各派新实现者+独立评审（评审者独立复算了手算锚点、重跑了模块测试、独立论证了字节级不变性）；终审 Clean 后仍对两条 Minor（JSON null→"None" 审计污染 / NaN 权重绕过校验）裁定派修复波——新鲜代码上的真边界一行可修，不带债交接；修复波 scoped 复审 both ADDRESSED。台账存 `var/sdd-ledger-aurase-adoption.md`（gitignored），Rulings 全录。

**已知疤痕**：并行会话与我共享 aor-waves 工作树，期间三次热文件竞态（plans/README.md INDEX 计数、测试文件被对方提交卷入 99fac0f）——全部内容无损、以对方提交落地；bisect 到 99fac0f 单点不自绿属已知（rsi-evolve-handover L3 已记）。

## L4 治理与红线层：什么不能碰

1. **零依赖红线**：`laos/` 纯 stdlib；不 import zones/ 复现区。
2. **纯加法约束**：改 `_impl_evolve_run` 审计时保持条件键语义——想恒记某键先问"旧作业审计行会不会漂移"。
3. **生成式红线**：SE/修复类组件若未来进 drivers，三维幻觉审计是上线前置；产出只进评测副本不进记忆副本（auto-gain/07 + AuraSE 调研 §4.3 双重裁决）。
4. **保真份额 ≥60%**：奖励面 spec 涉质量/保真两类时的文档级约定（不是代码强制——违规在 review 层拦）。
5. **计划纪律已制度化**（plans/README.md 头部）：写计划必跑三查（spec 覆盖/占位符扫描/类型一致性）；跨 Task 引用原文重复禁"类似 Task N"；**本波的教训实证**：aurase-adoption 计划的三查实跑抓到四条错（计数漂移/名不副实的断言辅助/(0,1] 值域错/一例两例笔误），T1 执行中又抓到第五条（fixture 自相矛盾）——纪律有效，别省。
6. **SDD 台账在 var/**：`var/sdd-ledger-aurase-adoption.md`（gitignored），clone 后不可恢复——rulings 已全录在本文件 L3 与计划 Self-Review 节。
7. **分支状态（2026-10-09 收口实况）**：`aor-waves` 已由并行会话合入 master 并删分支（录音回放波 A10 登记随 8d63a45）；本波全部提交现已在 master（领先 origin 1 提交，**未推送**——推送属发版纪律动作，归用户）；本波不占版本号，随下一 MINOR 携带。

## 资产索引

- **调研**：`docs/research/2026-10-09-aurase-ipo.md`（主篇）· `2026-10-09-xhs-qwen-audio-agent-runtime.md`（Voice Agent Runtime）· INDEX.md 各登记行
- **计划**：`docs/superpowers/plans/2026-10-09-aurase-adoption.md`（已执行，Self-Review 含三查修错记录）
- **图**：`docs/diagrams/aurase-adoption-architecture.html`（archify 交互图，candidate JSON 同名并存）/ `aurase-adoption-handover.drawio`（drawio 源，打开方式见文件头注释）
- **PPT**：`docs/ppt/laos-aurase-adoption-handover.html`（10 页，frontend-slides 血统，←/→ 翻页、E 键编辑）
- **本波 commit**（aor-waves 侧）：baddb0c（调研+复现）→ ebec4c9（计划）→ 55e787c（RewardSpec+aggregate）→ 8a28b82（契约+审计）→ 2fdbb69（drivers/README 立约）→ 99af75d（边界修复波）→ ec448f6（登记收尾）；另有 3ef138f/a9ba588/0462915/558f93d/baa3e0d/e1f9a4d 在 openevolve-driver→master（565dec8）线上
- **复现证据**：`var/repro/2610.06632/fulltext.txt`（论文提取）+ Repro-ZCode 区 README 诚实偏差登记

> **archify 门禁诚实声明（2026-10-09 本机实况）**：validate ✅（candidateFrozen，schema+仓库证据+布局全绿）/ render ✅（自包含 HTML 766KB）/ check ✅（非 provenance 模式）/ **deliver·finalize ❌ 环境阻断**——根因实证：本机 Windows/NTFS 上 `fs.lstatSync().dev` 恒为 `0n` 而 `fs.fstatSync().dev` 为卷 ID（archify.mjs `sameFileIdentity` 恒 false，投递锁安全检查拒开）；**browser-check ❌ 环境阻断**——Chrome 可用但巡检不完成。两处均为宿主环境不兼容而非候选缺陷；证据链存 `.archify/architecture-aurase-adoption-20261009-233000/`。在健康环境重跑 `finalize` 即可补齐 provenance 与浏览器证据（候选已冻结，sha 见 validate 回执）。
