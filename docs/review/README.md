# docs/review 索引（评审文档家族）

> 本目录是 laos 全部评审文档的**总入口**。评审文档回答「做不做、怎么做、先做哪个」——讲解材料（docs/ppt、docs/guide）回答「项目是什么」，两者别混用。
> 维护规则：新增评审文档必须在本文登记（文件名 + 时点版本 + 评审类型 + 编号体系），未登记不计入家族；编号一经冻结只顺延不回收。

---

## 1. 两代评审

| 代际 | 文档 | 时点/版本 | 主库测试数 | 定位 |
|---|---|---|---|---|
| **第一代（快照）** | [2026-10-07-requirements-review.md](2026-10-07-requirements-review.md) | v0.19.0（2026-10-07） | 691 | 上线前需求评审快照：**§6 问题域编号 P01–P15 自其时冻结**，是 Task 3《埋点设计》的需求源头 |
| | [2026-10-07-technical-review.md](2026-10-07-technical-review.md) | v0.19.0（2026-10-07） | 691 | 上线前技术评审快照：**§4 风险/债务编号 R1–R11 自其时冻结**，ADR ×5 |
| **第二代（现行）** | [2026-10-18-requirements-review.md](2026-10-18-requirements-review.md) | v0.39.0（2026-10-18） | **1180**（口径见 §3） | 对第一代的刷新版：沿用 P01–P15 冻结编号逐条更新状态，三条产品线口径 |
| | [2026-10-18-technical-review.md](2026-10-18-technical-review.md) | v0.39.0（2026-10-18） | **1180** | R1–R11 状态更新 + **R12–R16 新增**（R16=并发写入窗口期）；ADR ×8 |
| | [2026-10-18-roadmap-review.md](2026-10-18-roadmap-review.md) | v0.39.0（2026-10-18） | **1180** | **laos 第一份路线评审**（第一代未设此类型）：时间轴主线，43 个 tag 全史 + 下一波→v1.0 路线图 |

第一代是历史快照，**不再更新**；引用其编号（P01–P15、R1–R11）时以第二代文档的现行状态为准。

---

## 2. 现行代的两套载体（同一时点的两种用途）

第二代同日（2026-10-18）存在两套载体，**数字口径完全一致**（见 §3），按会议场景选用：

| 载体 | 文件 | 用途 | 编号体系 |
|---|---|---|---|
| **详细版**（本目录平铺三份） | `2026-10-18-{requirements,technical,roadmap}-review.md` | 逐条审计底稿：证据链完整，适合会前精读与会后归档 | 需求 P01–P15 / 技术 R1–R16 / 路线无编号（按 §1–§7 组织） |
| **会议包**（[2026-10-18/](2026-10-18/)） | [00-review-pack.md](2026-10-18/00-review-pack.md) + [01](2026-10-18/01-requirements-review.md)/[02](2026-10-18/02-technical-review.md)/[03](2026-10-18/03-roadmap-review.md) | 现场评审用：含议程（90 分钟标准场）、决议规则、Go/No-Go 门槛、现场结论区 | 需求 R-01–R-18 / 技术 C-01–C-08·T-01–T-12·ADR-01–06 / 路线 M-01–M-12·DP-01–DP-06·RR-01–RR-06 |

两套载体的关系：**会议包是现场交互面，详细版是证据层**。会议包中每条结论都可在详细版找到同源证据；若两套数字冲突，以本目录 §3 口径段与 ONBOARDING.md 门禁实跑为准，并按「腐化要会失败」流程修复。

---

## 3. 数字口径（两档，均已实跑对账）

| 锚点 | 值 | 口径 | 适用文件 |
|---|---|---|---|
| 主库测试数（**发版时点**） | **1158** | v0.39.0 `release.py --apply` 发版硬闸真跑 `Ran N` 写入 | README/PROJECT_OVERVIEW/guide/decks 等**介绍文件**（由 sync_docs 在发版时刷新，平时不手改） |
| 主库测试数（**门禁实跑**） | **1180** | `scripts/check_onboarding.py` 当日实跑 discover：`Ran 1180 tests · OK (skipped=5)` | ONBOARDING.md 事实表与本目录全部评审文档 |
| 两档差 | **+22** | 1（dated 报告排除回归 d396f37）+ 6（锚点同步回归）+ 15（check_survey 校验器回归） | 未发版增量，下次发版由 release.py 统一刷新 |
| 隔离区 / 复现区 / 对照树 | 279 / 94 / 276 | 各树 discover 实跑（复现区为 pytest collect） | 四树合计 **1829** |

静态 `def test_` 计数 1211 = 实跑 1180 + 31 个 pytest-only 盲区（4 个 pytest 风格模块）；盲区测试由 pytest 单独运行验证（31 passed）。

---

## 4. 会议使用指引（飞书文档）

| 评审会 | 主文档 | 必读附件 |
|---|---|---|
| **需求评审** | 会议包 [01-requirements-review.md](2026-10-18/01-requirements-review.md) | 详细版 [2026-10-18-requirements-review.md](2026-10-18-requirements-review.md)；冻结编号 P01–P15 状态表 |
| **技术评审** | 会议包 [02-technical-review.md](2026-10-18/02-technical-review.md) | 详细版 [2026-10-18-technical-review.md](2026-10-18-technical-review.md)；R1–R16 风险表 + 逐模块测试表 |
| **路线评审** | 会议包 [03-roadmap-review.md](2026-10-18/03-roadmap-review.md) | 详细版 [2026-10-18-roadmap-review.md](2026-10-18-roadmap-review.md)；§2 版本全史 + §5 下一波路线图 |

会议包 [00-review-pack.md](2026-10-18/00-review-pack.md) §2 备有 90 分钟标准议程；决议规则（§3）要求阻塞项必须写成「现象+证据+验收标准+责任人+时间盒」五元组。

---

## 5. 关联文档

- `docs/ONBOARDING.md` §0「事实基线」——两档口径的设计说明与交接门禁规则（check_onboarding.py）
- `scripts/release.py`——发版硬闸（真跑测试）+ sync_docs 锚点同步（介绍面五类文档）
- `docs/research/INDEX.md`——调研资产清单（评审结论的调研侧来源）
- `docs/superpowers/plans/README.md`——计划状态登记（评审建议的落地去向）
