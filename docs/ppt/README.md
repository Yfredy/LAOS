# laos 项目介绍 PPT × 5 套（五 skill 实测对比）

> 2026-10-05 ｜ 来源：[知乎《实测 5 个 PPT 神级 Skill，谁是真 PPT 之王？》](https://zhuanlan.zhihu.com/p/2042569361387415436)
> 五个 skill 已安装于 `~/.agents/skills/`；同一份 12 页内容底稿（[laos-intro-outline.md](laos-intro-outline.md)）喂给五个 skill——同内容不同渲染，公平对比。

## 交付物

| # | Skill | 交付物 | 形态 |
|---|---|---|---|
| 1 | **ppt-master** v6.6.0（19.2k★） | [laos-intro-ppt-master.pptx](laos-intro-ppt-master.pptx) | **真 PPTX**：12 页 × 320 形状 × 223 个原生可编辑文本（PowerPoint 直接打开改字） |
| 2 | **guizang-ppt-skill**（歸藏） | [laos-intro-guizang.html](laos-intro-guizang.html) | 单文件 HTML 瑞士国际主义风（IKB 克莱因蓝）；横翻/滚轮/触屏；`P` 演讲者视图+计时+排练 |
| 3 | **frontend-slides** | [laos-intro-frontend-slides.html](laos-intro-frontend-slides.html) | 单文件 HTML 终端绿风（1920×1080 固定舞台）；**E 键页面内改字**+localStorage 自动保存+导出 |
| 4 | **html-ppt-skill** | [laos-intro-html-ppt.html](laos-intro-html-ppt.html) | 单文件 HTML 工程蓝图风（主题 blueprint，资产已按 MIT 内嵌）；**S 键演讲者四卡**（当前页/下一页像素级预览+逐字稿+计时）；`T` 键换 36 主题 |
| 5 | **huashu-design**（花叔） | [laos-intro-huashu.html](laos-intro-huashu.html) + [三方向方向板](laos-intro-huashu-directions.html) | 单文件 HTML 档案黑金台账风（方向 A，自主模式选定；方向板保留 B 纸感宣言红 / C 黑黄新粗野两个备选封面初稿） |

打开方式：pptx 用 PowerPoint/WPS；HTML 用浏览器全屏（F11），方向键翻页。

## 实测对比（本项目的真实体验，非转述）

| 维度 | ppt-master | guizang | frontend-slides | html-ppt | huashu-design |
|---|---|---|---|---|---|
| 输出格式 | **真 pptx（可编辑）** | HTML | HTML | HTML | HTML |
| 视觉纪律 | 质检器强制（字号角色/溢出实测/viewBox 校验） | **版式白名单 S01-S22+验证脚本**（PASSED） | 契约自觉（零依赖/E键编辑写进契约） | 令牌化设计系统（base.css+36 主题） | **三方向硬门**（不豁免） |
| 演讲支持 | 转场/动画菜单（导出参数） | 演讲者视图+观众屏同步+排练记录 | 无（极简） | **最强**：S 键四卡+逐字稿规范（150-300字/页） | 无 |
| 上手摩擦 | **最高**（init→字迹校准→SVG→质检→spec_lock→导出，5 道工序；依赖最多，本机 skia-pathops 缺失靠规避合并形状） | 中（模板 2900 行外壳，但只填 sections；版式文档 900 行需读） | **最低**（一份契约文档照抄） | 低-中（资产齐全可直接内嵌，MIT） | 低（纪律在脑不在流程） |
| 中文字排 | 44px 标题≈22 字/行需按表估算（text_measure 实测校准） | 中文标题分档字号表（≤8字/行规则） | 自由（1920 舞台字号宽裕） | base.css 令牌+主题 | 自由 |
| 本轮抓到的坑 | 未声明字号角色/文本溢出 0.2% 都会被阻断（严格=质量） | 系统帧插队语义需自己想清楚（复现层的问题，非 skill） | 无 | 无 | 无 |

## 裁决（laos 场景）

- **要交给别人在 PowerPoint 里改** → 只有 **ppt-master** 是"真 PPT"（文章结论一致：pptx 需求选它或 huashu；huashu 本轮产 HTML，pptx 能力未在本次链路触发）。
- **要上台演讲** → **guizang**（版式纪律+演讲者视图+观众屏控制）或 **html-ppt**（逐字稿+四卡预览，怕忘词首选）。
- **要快速发一个链接给人看** → **frontend-slides**（最轻、E 键就地改字）。
- **要品牌质感/工作室感** → **huashu**（黑金台账风与 laos"审计/记账"叙事同构，本轮个人最佳视觉）。
- 综合"对本项目的价值"：**guizang**（纪律+演讲全链）与 **ppt-master**（唯一可编辑真身）并列第一；文章把 frontend-slides 评为体验最佳，本项目实测同样最顺滑，但深度功能少于 guizang/html-ppt。

## 复现链路（本目录）

- 内容底稿：`laos-intro-outline.md`（12 页事实来源，五套共用）
- guizang 构建器：`_build_guizang.py`（注入 12 版式 sections + SPEAKER_NOTES，跑官方 `validate-swiss-deck.mjs` → PASSED）
- ppt-master 构建器：`_build_pptmaster.py`（12 页 SVG → 官方质检器 --canonical-authoring 通过 → `svg_to_pptx --quick-generate`）
- ppt-master 工程目录：`~/.agents/projects/laos-intro-master_20261005/`（svg_output/ + spec_lock.md + validation 报告）
- html-ppt 内嵌资产：`html-ppt-assets/`（MIT，来自 lewislulu/html-ppt-skill）
