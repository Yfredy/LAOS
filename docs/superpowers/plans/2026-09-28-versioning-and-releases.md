# laos 语义化版本 + Release 流程 实施计划（已批准）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 179 个"不知道干了什么"的提交组织成可理解的版本序列：回溯建立 7 个版本（v0.1.0–v0.7.0），打 tag + 建 GitHub Release + 写 CHANGELOG.md（Keep a Changelog 规范），并落地 `scripts/release.py` 让此后每个完整需求自动生成版本号。

**Architecture:** 三层交付：① `CHANGELOG.md` 回溯（7 个版本段，Keep a Changelog 六分类，人类可读功能叙述而非 commit 流水）；② 回溯 annotated tag v0.1.0–v0.7.0 + `gh release create`（gh 不可用则输出手动建页 URL 清单）；③ `scripts/release.py` 发版助手（自上次 tag 后的 conventional commits 推导下一版本：feat→MINOR / fix→PATCH / BREAKING→MINOR+记 breaking（0.x 不动 MAJOR），三棵树 `__version__` 同步，CHANGELOG 草稿段生成）。

**Tech Stack:** git tag / gh CLI / stdlib。规范依据：SemVer 2.0（0.x 阶段 breaking 不升 MAJOR）、Keep a Changelog 1.1.0、Conventional Commits（feat→MINOR、fix→PATCH、`!`/BREAKING→MAJOR，docs/chore/test 不触发）、Release 页样例（pydantic v 前缀 + changelog 式 body + compare 链接）。

**Spec:** 版本边界（已逐 commit 实测，179 提交七段无重无漏）：

| 版本 | 发版 commit | 日期 | 提交数 | 波次 |
|---|---|---|---|---|
| v0.1.0 | `06edb3c` | 09-04 | 1 | baseline：内核+强制层骨架+研究文档基线（149 文件） |
| v0.2.0 | `bdfae15` | 09-05 | 51 | 内核强制层：seccomp BPF、CoW、eBPF profiler、FleetLedger |
| v0.3.0 | `dff4269` | 09-09 | 11 | 内核语义扩展：AgentProf、MCP Tasks、信箱 IPC、laosweb、drv_npu |
| v0.4.0 | `cadc4a6` | 09-11 | 46 | 听觉+记忆+日记（drv_mic/drv_ear/MemoryStore/diary/journal）+ Apple/垂直调研 |
| v0.5.0 | `7de6f59` | 09-11 | 9 | 五层手机能力（drv_screen/notify/comms/battery/events/vad）+ AlwaysOnRec 双沙箱 |
| v0.6.0 | `073a3c5` | 09-18 | 30 | 调研语料库：19,792 篇双会议论文 + 3,724 OSS + 模型地图 |
| v0.7.0 | `5bedf60` | 09-28 | 31 | Jev 判断层四闸门 + selfcheck 加固 + capstone 总纲 |

（图表修复 6a9f7b4 在 v0.5.0 之内，独立 v0.5.1 取消。）

## Global Constraints

- SemVer 2.0 + v 前缀；0.x 阶段 breaking 不升 MAJOR
- CHANGELOG.md：遵循声明 + `[Unreleased]` 空段 + 版本段最新在前；六分类；条目=用户可感知功能叙述
- tag 用 annotated（`git tag -a -m`）；push 用 `git push origin --tags`
- **tag push 与 GitHub Release 建页是外发动作：Task 2 Step 2 前向用户展示清单并获得确认**
- 回溯条目只写能从提交历史确证的事实

---

### Task 1: CHANGELOG.md 回溯
- Create `CHANGELOG.md`。逐版本 `git log --oneline <prev>..<ver>` 读全量提交按功能族归组（每版本 Added 3-8 / Changed·Fixed 1-4；素材锚点：v0.2.0=seccomp/CoW/eBPF/FleetLedger；v0.3.0=AgentProf/MCP Tasks/信箱/laosweb/drv_npu；v0.4.0=听觉双驱动/MemoryStore/diary/journal/Apple S12；v0.5.0=屏幕/通知/传感器/双沙箱；v0.6.0=19,792 论文+3,724 OSS；v0.7.0=Jev 四闸门/criteria 问句/校准台/capstone）
- 头部声明 + `[Unreleased]` + 7 段（最新在前），标题 `## [v0.x.y] - 2026-09-NN`
- `git commit -m "docs: CHANGELOG.md — retroactive 7-release history (Keep a Changelog)"`

### Task 2: 回溯 tag + GitHub Releases（外发先确认）
- `git tag -a v0.1.0 06edb3c -m "..."` … 7 个（message=CHANGELOG 一句话摘要）
- 展示 7 tag + 7 Release 标题清单 → **用户确认后** `git push origin --tags`
- `gh release create v0.x.y --title --notes "<CHANGELOG 段>"`；gh 不可用 → 7 条手动 URL 清单写交付说明
- 验证：`git tag -l`=7、`git ls-remote --tags origin` 一致、`gh release view v0.7.0` 抽查

### Task 3: 发版助手 scripts/release.py + 版本同步
- Create `scripts/release.py` + `tests/test_release.py`；Modify 三棵树 `laos/__init__.py`（"0.1.0"→"0.7.0"）
- 接口：`commits_since(tag)` / `next_version(current, subjects)`（BREAKING→minor+1、feat→minor+1、fix→patch+1、纯 docs/chore→不发版）/ `changelog_section(version, subjects)` / `sync_versions(version)` / CLI `--dry-run|--apply`
- TDD：next_version 四规则（feat 集→0.8.0 / fix 集→0.7.1 / "!"→0.8.0 / 纯 docs→不变）、sync 三文件一致、changelog 含 "### Added"；全量 316+新增 全绿；`--dry-run` 实跑
- `git commit -m "feat(scripts): release helper — semver derivation from conventional commits, three-tree __version__ sync"`

### Task 4: README 版本小节 + 收尾
- 头部加一行：`当前版本 v0.7.0（主库 316 测试 + 隔离区 279）——版本史见 [CHANGELOG.md](CHANGELOG.md) 与 [Releases](https://github.com/Yfredy/LAOS/releases)`
- 新增 `## 十、版本与发布`：版本语义（0.x 规则）+"多少提交算一个版本"定义（**一个完整需求波次 = 一次 MINOR**，识别特征=新模块/新驱动/新文档域；review 闭环 fix=PATCH）+ 发布流程四步
- 全量全绿；push master；交付说明：7 版本表 + Release 链接（或手动清单）+ 今后流程
