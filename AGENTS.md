# AGENTS.md — laos 仓库代理工作记忆

> 任何代理（agent）在本仓库工作前必读。本文件是跨会话持久记忆。

## 发版纪律（2026-10-06 用户指令，最高优先级）

**每次发版都必须更新仓库里所有介绍性文件，并自动操作。** 包括且不限于：

- `README.md`、`docs/PROJECT_OVERVIEW.md`、`zones/AlwaysOnRec-Trae/README.md`
- 全部 PPT 组：`docs/ppt/*.md`、`docs/ppt/*.html`、`docs/ppt/detailed/*.html`、
  `docs/ppt/funding/*.html`（封面 stamp / "开源 vX.Y.Z ·" / 页脚 "· vX.Y.Z · NNN tests" /
  大纲跨度端点 / 测试计数）
- 如再生成 pptx/视频等二进制介绍物，重生成后同样对齐版本与测试数

**自动化已落地**：`python scripts/release.py --apply` 现在依次执行——

1. 主库测试套件真跑一遍（**不绿直接拒绝发版**）；
2. 三棵树 `__version__` 同步；
3. `sync_docs()` 自动改写上述全部介绍文件的五类锚点（当前版本声明/封面
   stamp/页脚/版本跨度端点/测试计数），主库计数用实跑数、页脚总数含
   隔离区+复现区；**带日期的里程碑史（如 "v0.12.0 (10-05)"）永远不动**；
4. `--dry-run` 同样输出完整同步报告（不写文件）。

之后照旧：CHANGELOG 人工插入该版段落 → release commit → annotated tag →
push master+tag → GitHub Release 页。漏掉任何一步都算发版事故。

## 目录纪律（2026-10-08 仓库卫生波固化，参照 nanoMuse 分类学）

> 锚点：`docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md` §7。

- **根目录只放治理与入口**：README / AGENTS / CHANGELOG / 配置文件
  （.gitignore/.gitattributes）之外，只允许下列已登记的顶层目录——零日志、
  零临时物、零孤儿目录。
- **一端一目录，绝不互放**：
  - `laos/` 核心包（纯 stdlib，唯一代码家）
  - `bin/` CLI 入口（laosctl/laosd/laosweb）
  - `clients/` 各端薄壳（2026-10-09 登记：`clients/android/` 最小
    WebView 壳——架构取经 nanoMuse 只学设计零抄码；不进主测试套件，
    自带 README；加新端先在此登记）
  - `demos/` 认知演示
  - `zones/` 四棵 zone 树（Trae=哨兵对照 / ZCode=隔离区 / DB=沙箱 /
    Repro-ZCode=复现区）——release.py 的 zone 路径与 DOC_GLOBS 都锚在
    zones/ 下，zone 树不得再裸奔根层
  - `corpus/` 语料、`drivers/` 重依赖驱动子进程（自带 README：模块地图+奖励治理面+三维幻觉审计约定）、`scripts/` 工具、
    `tests/` 测试、`docs/` 文档、`var/` 本地处
- **docs/ 一主题一目录**（design/diagrams/guide/images/ppt/research/
  review/superpowers），根层只留 PROJECT_OVERVIEW.md；过期内容沉没进
  archive，不散落。**唯一例外**：docs/research/ 按日期前缀平铺——
  INDEX.md 是胶水，迁移破坏 90+ 内链（§7.2 Ruling），永不迁移。
- **临时物只进 `var/`**（gitignored 整目录）：评测产物、爬取工作区、调试
  脚本一律 var/；根目录再见到日志/孤儿当场清零。
- **新顶层目录须在本节登记**：未登记的顶层目录视为卫生事故，review 打回。

## 其他持久纪律（此前会话累积）

- **定位叙事**：基座是 Linux 内核；Agent 是新负载（与进程同类）；laos 是内核
  治理在用户态的延伸。禁止"给 AI Agent 装上操作系统"类主客反转表述。
- **品牌名（2026-10-08 起）**：对外品牌名 **nanoLAOS**（README/PROJECT_OVERVIEW/
  PPT 封面用之，副标 "laos · Linux AgentOS"）；技术名/仓库名/包名 `laos`、
  CLI 名 laosctl/laosd/laosweb、`LAOS_*` 环境变量**全部不变**（公开契约）。
- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`，禁止 `pip install`
  进该环境；重依赖只进驱动子进程。
- **零依赖承诺**：`laos/` 核心纯 stdlib。
- **测试口径**：README 写实跑数（`unittest discover` 的 "Ran N tests"），
  不是静态 `def test_` 计数。
- **隐私红线**：录音只由显式 syscall 触发；`LAOS_REC=0` 全局禁录；ASR 全本地。
- **来源诚实**：小红书/微信文章被墙时按预案从可验证来源重构并在文档开头
  声明；评测数字一律实测，不引用宣称值。
- **计划编写纪律（2026-10-09 制度化）**：实施计划进 `docs/superpowers/plans/`
  （现行体例），写完必跑三查（spec 覆盖/占位符扫描/类型一致性），跨 Task
  引用原文重复禁"类似 Task N"（执行者乱序读是常态）；状态登记在
  plans/README.md，新计划与状态变更同步登记。细则见该文件头部。
- **GitHub 通道排障序（2026-10-10 实录）**：本机 `http.proxy=127.0.0.1:7897`
  的**上游出口**会单独故障（SSL 握手重置数小时），而**直连与 SSH 往往正常**
  ——推送/API 失败先按序探测三条通道（`curl -x 代理` / `curl 直连` /
  `git ls-remote`），哪条通走哪条，**不要在坏代理上空转重试**（曾有 3 小时
  60+ 次白试）；git 单次绕代理用 `git -c http.proxy= push ...`。外发动作
  （push/tag/Release 页）失败时起后台退避重试循环并如实记录，恢复后闭环，
  终态不可得时不假定成功。
- **发版内容归档（2026-10-10 制度化）**：`docs/releases/` 每版一文件
  （元信息头+详细正文）+ README 索引，Release 页加长版存 `extended/`；
  **每次发版后跑 `python scripts/gen_release_notes.py` 重新对齐并随发版提交**
  （与 CHANGELOG 同属发版链，漏跑算发版事故）。
