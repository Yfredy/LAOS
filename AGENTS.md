# AGENTS.md — laos 仓库代理工作记忆

> 任何代理（agent）在本仓库工作前必读。本文件是跨会话持久记忆。

## 发版纪律（2026-10-06 用户指令，最高优先级）

**每次发版都必须更新仓库里所有介绍性文件，并自动操作。** 包括且不限于：

- `README.md`、`docs/PROJECT_OVERVIEW.md`、`AlwaysOnRec-Trae/README.md`
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
