# 仓库卫生整改计划 —— 目录组织参照 nanoMuse 分类学

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 根目录清零垃圾与孤儿、四棵 zone 树收进统一目录、docs/ 根层归类，并把目录学约定固化进 AGENTS.md——达到 nanoMuse"根目录只有治理与入口"的纪律。

**Architecture:** 全程 `git mv`（保历史）+ 路径引用同步（release.py 的 zone_test_counts 与 DOC_GLOBS、README/AGENTS 中的路径文案）；每步全量测试绿是闸门。**docs/research/ 平铺不动**（INDEX 是胶水，迁移破坏 90+ 内链——见参照手册 §7.2 Ruling）。

**Tech Stack:** git mv + Python（release.py/AGENTS.md 编辑）；无新代码面。

**Spec:** `docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md` §7（目录组织参照与诊断——本计划实现 §7.3 裁决的 ● 项）。

## Global Constraints

- 每步后 `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q` 全绿（zone 计数路径变了则同步 release.py 后跑 `scripts/release.py --dry-run` 验证计数不漂移：主库实跑数不变、隔离 279/复现 71 两区计数**逐字节不变**）。
- zone 树迁移是**路径敏感操作**：`scripts/release.py` 的 `REPO/"AlwaysOnRec-ZCode"/"tests"` 与 `REPO/"Repro-ZCode"/"tests"`、`DOC_GLOBS` 的 `AlwaysOnRec-*/README.md` 必须与目录同 commit 更新。
- 未跟踪的日志/临时物直接删（`rm`）；被跟踪物一律 `git mv`。
- 版本：并入下一次发版的 docs commit 或独立 PATCH（无代码行为变化；若 release.py 改动则随波 PATCH）。

---

### Task 1: 根目录清零（日志删 + 孤儿归位）

**Files:**
- Delete: `dl.log dl1.log err.log err2.log sel.log`（未跟踪残渣）
- Move: `outputs/` → `var/outputs/`（git mv，audio 评测产物）；`_s2_crawl/` → `var/_s2_crawl/`（未跟踪则 mv）；`fsroot/` 内容确认后删除或 `var/fsroot/`
- Modify: 根 README 若引用 `outputs/` 路径则同步

- [ ] **Step 1: 核对引用**——`grep -rn "outputs/\|_s2_crawl\|fsroot" README.md docs/*.md tests/ scripts/ bin/ | grep -v var/`，记录需同步的引用点（预期近零）。
- [ ] **Step 2: 执行**——删五个 .log；`git mv outputs var/outputs`（tracked 内物）；`mv _s2_crawl var/`、`fsroot` 单文件 `mv var/fsroot_main`（或确认是垃圾后删）。
- [ ] **Step 3: 验证**——`git status`（只见 renames+deletes）；全量测试绿；`ls` 根目录无日志无孤儿。
- [ ] **Step 4: Commit** `chore: 根目录清零——日志残渣删、outputs/_s2_crawl/fsroot 归位 var/`

### Task 2: 四棵 zone 树收进 zones/

**Files:**
- Move: `AlwaysOnRec-Trae/ AlwaysOnRec-ZCode/ AlwaysOnRec-DB/ Repro-ZCode/` → `zones/AlwaysOnRec-Trae/` 等四棵
- Modify: `scripts/release.py`（zone_test_counts 两行路径、DOC_GLOBS `AlwaysOnRec-*/README.md` → `zones/AlwaysOnRec-*/README.md`）；`README.md`/`AGENTS.md`/`docs/PROJECT_OVERVIEW.md` 中 zone 路径文案；`tests/test_release.py` 的 `test_doc_globs_cover_intro_group_and_all_three_trees` 相对路径断言（`AlwaysOnRec-Trae/README.md` → `zones/...`）
- Create: `zones/README.md`（一表说明四区：Trae=哨兵对照树 / ZCode=隔离区测试 279 / DB=数据库沙箱 / Repro-ZCode=复现区测试 71，及"为何平级四树收进 zones"）

- [ ] **Step 1: 全量引用扫描**——`grep -rln "AlwaysOnRec-\|Repro-ZCode" --include="*.py" --include="*.md" . | grep -v zones | grep -v var/ | grep -v docs/research` 得到需改清单（预期：release.py、test_release.py、README、AGENTS、PROJECT_OVERVIEW、CHANGELOG 不改史）。
- [ ] **Step 2: git mv 四树** → **Step 3: 同步全部引用路径**（release.py 两处+DOC_GLOBS+文档文案+测试断言）。
- [ ] **Step 4: 验证**——全量测试绿；`release.py --dry-run` 输出的"隔离 279 + 复现 71"与迁移前逐字节一致（diff 前后 dry-run 输出）；README 页脚总数不变。
- [ ] **Step 5: Commit** `chore: zone 四树收进 zones/ 并同步 release.py/DOC_GLOBS/文档路径`

### Task 3: docs/ 根层归类

**Files:**
- Create: `docs/diagrams/`、`docs/guide/`
- Move: `laos-architecture.html laos-architecture.architecture.json always-on-recording.html audio-ai-agent-oss.html jev-decision-model.html speech-emotion-models.html laos项目结构与使用说明书-详细版.html` → `docs/diagrams/`；`guide-panel.md` → `docs/guide/`；`images/` → `docs/diagrams/images/`（若仅被这些 html 引用）
- Modify: 被移动文件之间的相对引用（html 内 img/a 相对路径）；README/PROJECT_OVERVIEW 指向（若有）

- [ ] **Step 1: 扫描入链**——`grep -rn "always-on-recording.html\|laos-architecture\|guide-panel\|audio-ai-agent-oss" README.md docs/ --include="*.md" | grep -v diagrams`。
- [ ] **Step 2: git mv + 修相对引用** → **Step 3: 验证**（全绿 + `docs/` 根只剩：PROJECT_OVERVIEW.md + 六个子目录）。
- [ ] **Step 4: Commit** `chore: docs 根层归类——diagrams/ 收七件渲染物、guide/ 收指南`

### Task 4: 目录学约定固化 + 发版

**Files:**
- Modify: `AGENTS.md`（追加"目录纪律"节：根目录只放治理与入口；一端一目录；docs 一主题一目录+archive 纪律；zone 树只进 zones/；临时物只进 var/——参照 nanoMuse 分类学，锚点 docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md §7）
- Modify: `CHANGELOG.md`（v0.29.0 或 PATCH 段的 Changed：仓库结构整改条目）；`docs/research/INDEX.md`（参照手册行补 §7 一句）
- Steps: AGENTS.md → CHANGELOG → 全量绿 → 若与 laosweb v3 波合流则并入其发版，否则 `release.py --apply` PATCH → push。

## Self-Review 记录

1. **Spec 覆盖**：§7.3 ● 三项 = Task 1/2/3，约定固化 = Task 4；◐（scripts 分组、var 本地清洁）与 ○（research 平铺）无任务——正确。
2. **占位符**：无；Task 1/3 的"确认后删"类步骤给了判定条件（单文件 chroot 残留=垃圾）。
3. **类型一致性**：路径字符串在 Task 2 三处（release.py/DOC_GLOBS/测试断言）与 Task 3（相对引用）各自闭环，dry-run 逐字节对比是硬闸门。
