# laos 项目介绍 PPT × 5 套（五 skill 实测对比）

> 2026-10-05 ｜ 来源：[知乎《实测 5 个 PPT 神级 Skill，谁是真 PPT 之王？》](https://zhuanlan.zhihu.com/p/2042569361387415436)
> 五个 skill 已安装于 `~/.agents/skills/`；同一份 12 页内容底稿（[laos-intro-outline.md](laos-intro-outline.md)）喂给五个 skill——同内容不同渲染，公平对比。
>
> **第二波（2026-10-05 下午）**：两个新题材各再跑五 skill + 一个 v6 合成版——
> ①详细技术深潜版（底稿 [laos-detailed-outline.md](laos-detailed-outline.md)，18 内容域）；②创新融资版（底稿 [laos-funding-outline.md](laos-funding-outline.md)，15 页，诚实原则：进展数字全真、金额与市场规模标"示例"）。见文末"第二波"两节。

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

---

# 第二波 ①：详细技术深潜版（5 skill + v6 合成）

交付物（`detailed/`，同底稿 18 内容域：A1-E3）：

| Skill | 交付物 | 页数 | 质检 |
|---|---|---|---|
| ppt-master | [detailed/laos-detailed-ppt-master.pptx](detailed/laos-detailed-ppt-master.pptx) | 19 | final gate 19/19 零告警；423 个可编辑文本框；八环闸门链=原生流程图（downArrow×6） |
| guizang | [detailed/laos-detailed-guizang.html](detailed/laos-detailed-guizang.html) | 19 | validate-swiss-deck PASS（含 Playwright 渲染测量）+ presenter 0 error；13 版式；构建器 `_build_detailed.mjs` |
| frontend-slides | [detailed/laos-detailed-frontend-slides.html](detailed/laos-detailed-frontend-slides.html) | 19 | 31 事实逐项 grep 验证；八环终端流水线+拒绝 trace；E 键编辑 |
| html-ppt | [detailed/laos-detailed-html-ppt.html](detailed/laos-detailed-html-ppt.html) | 20 | 令牌纪律 0 字面色、20 页备注全非空（agent 收尾被限速打断，成品经主线程验证完整） |
| huashu | [detailed/laos-detailed-huashu.html](detailed/laos-detailed-huashu.html) + [方向板](detailed/laos-detailed-huashu-directions.html) | 19 | Playwright 逐页审计 0 溢出/0 越界；LEDGER CORRECTION 订正条（157.5ms 推翻 15.6ms） |

**v6 合成版**：[laos-detailed-v6.html](laos-detailed-v6.html)（19 页）——取长板公式：
ppt-master 字号角色体系+Hero breathing 大数字 ｜ guizang 12 列 Swiss 网格+`data-layout` 版式登记+accent 只承载治理事实 ｜ frontend-slides 1920×1080 舞台自缩放+E 键编辑+拒绝 trace ｜ html-ppt `:root` 令牌（内容区 0 字面色）+S 键演讲者四卡+逐字讲稿 ｜ huashu 台账母题+LEDGER CORRECTION 订正条。P02 是"裁决板"透明度页（每个长板可溯源）。视觉验收 6 关键页 PASS（Playwright 0 溢出 + visual-judge）。

# 第二波 ②：创新融资版（5 skill + v6 合成）

交付物（`funding/`，同底稿 P1-P15）：

| Skill | 交付物 | 页数 | 质检 |
|---|---|---|---|
| ppt-master | [funding/laos-funding-ppt-master.pptx](funding/laos-funding-ppt-master.pptx) | 15 | final gate 15/15；323 可编辑文本框；用资环形图为原生 blockArc（角度逐段坐标校验） |
| guizang | [funding/laos-funding-guizang.html](funding/laos-funding-guizang.html) | 15 | 验证器首轮 PASS + presenter 0 error；13 版式匹配数据形状（账单/象限/比例塔）；构建器 `_build_funding.py` |
| frontend-slides | [funding/laos-funding-frontend-slides.html](funding/laos-funding-frontend-slides.html) | 15 | CDP 逐页渲染 0 溢出；P6 环② EPERM 戳+熄灭后六环 |
| html-ppt | [funding/laos-funding-html-ppt.html](funding/laos-funding-html-ppt.html) | 15 | ledger-ink 主题（令牌 0 字面色）；15 页逐字路演稿含投资人 Q&A 预埋 |
| huashu | [funding/laos-funding-huashu.html](funding/laos-funding-huashu.html) + [方向板](funding/laos-funding-huashu-directions.html) + gate 文件 | 15 | Playwright 0 溢出（修复 4 处后）；壹贰叁防涂改数字=台账母题同构 |

**v6 合成版**：[laos-funding-v6.html](laos-funding-v6.html)（16 页 = 15 内容页 + 1 页 v6 出处附录）——同上公式，融资特化：huashu 壹贰叁痛点三柱、示例红章、诚实框正色；guizang 四象限/真比例用资塔；ppt-master 结论式标题+breathing 四大数（12/765/19,792/4）；每页 S 键逐字路演稿。视觉验收 11/12 直接过，P14 面板空置被判 fail → 已修（台账面板化）并复审。

## 第二波裁决（增量结论）

- **信息密度上限**：guizang（19 页塞 18 域仍可扫读——mono 锚点+accent 纪律是关键）；**故事密度上限**：huashu 融资版（壹贰叁/台账/订正条，形式即论证）。
- **可交付给非技术方修改**：仍是 ppt-master 独占（两个 pptx 共 746 个可编辑文本框）。
- **v6 的定位**：不是第六个风格，而是"引擎统一、母题各表"——两个 v6 共用同一舞台/键盘/令牌/演讲者引擎（互为拷贝可维护），detailed 用墨黑+瑞士蓝+账本金，funding 用墨蓝+金+衬线。E 键就地改字在两个 v6 里都是一等公民。
- **限速教训**：10 个 skill agent 并发触发了账户速率限制（2 个折翼：html-ppt 详细版死在汇报前但成品完好、huashu 详细版重派成功）——下一波并发上限设 5。

## 定位修正（2026-10-05 晚，用户裁决）

用户澄清并裁决叙事主客关系：**基座与核心是 Linux 内核；Agent 只是内核之上的上层补充/新负载；laos 是内核治理向 Agent 的用户态延伸**。此前两波 deck 中"给 AI Agent 装上操作系统（的治理内核）/ 用户态 Agent 内核 / 给 AI Agent 一座操作系统"等措辞把主客说反了（Agent 不是被安装 OS 的主体），已全部修正为内核优先表述：

- 融资版封面 → "Linux 内核的 Agent 治理层：基座不变，治理延伸"
- 方案格/产品页 → "laos = Linux 内核的用户态治理延伸""laosd 薄内核（治理延伸层）"
- 第一波副题 → "Linux 内核的 Agent 治理层"
- 两份底稿已写入"立场声明"作为全篇叙事基准（`laos-funding-outline.md` P1）

保留不改的表述（方向正确）："把 Linux 变成 Agent 的操作系统"（主语是内核）、"给工具调用装上 syscall 语义"（宾语是工具调用）、"模型负责想，laos 负责说「不」"（主语是 laos）。

**已知残留**：两个 pptx（`laos-funding-ppt-master.pptx`、`laos-detailed-ppt-master.pptx`）封面仍带旧口号（pptx 无法文本替换），演示前可在 PowerPoint 中直接改字，或下波用修正后底稿重新生成。
