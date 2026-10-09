---
name: xhs-vision-digest
description: 逐图视觉转写小红书图片笔记并产出结构化调研文档的完整流程（采集→清单→读图→幻觉仲裁→digest→登记）。Use whenever 用户提供小红书链接（主页/单篇/explore URL）并要求读取、转写、精读、调研或学习其中内容，或说"读一下这个小红书""把这篇的图都读了""继续读红书笔记""这个 up 主的内容过一遍"——即使用户没说"转写"二字。纯文字笔记不适用（只登记正文摘要，不读图）。
---

# 小红书图集逐图转写调研

把一个小红书 up 主的图片笔记变成可信的结构化调研文档。两条铁律：

1. **每张图都要真实读过**（视觉模型逐图转写），绝不只看标题/正文摘要就下结论。
2. **视觉模型会幻觉**——每篇都要做页码连续性校验，可疑图单张重读仲裁（见 references/playbook.md）。

本 skill 的实战底本是 2026-10-09 一次 134 篇 / 1706 图的全量调研（docs/research/2026-10-09-xhs-ai-audio-research-full.md，laos 仓库）。

## 流程总览（六阶段）

```
采集 → 清单 → 读图 → 仲裁 → digest 入档 → 对账登记
```

**阶段 1 采集**：用户在 in-app browser 登录小红书并打开目标主页/笔记；你用真实 UI 导航提取笔记列表与图集 URL，落成三个产物（manifest / details / 本地图备份）。schema、风控红线、提取细节见 `references/acquisition.md`——**尚未采集时先读它**。

**阶段 2 清单**：`manifest.json` = `[{group, id, title, imgs}]`（laos 仓库约定放 `var/xhs_audio/`；其他仓库用对应 var/ 或临时目录）。按主题给字母分组（A-interspeech、G-dsp 这类"字母-主题"式），统计每组 篇数×图数。分组就是后续文档的章节结构。

**阶段 3 读图**：核心阶段，见下节。

**阶段 4 仲裁**：读图时同步做（页码校验/幻觉剔除/单张重读），完整规程在 `references/playbook.md`。

**阶段 5 digest 入档**：每篇笔记浓缩成一个 digest 块追加进当日调研文档；每组末尾写组总结；全部读完写裁决/启示附录。**有已保存的 workflow `xhs-digest-fanout`（laos 仓库 .zcode/workflows/）可并行干这阶段**，见下文"digest 阶段"。

**阶段 6 对账登记**：文档声明的 篇数/图数 必须 = manifest 实数；`docs/research/INDEX.md` 登记（登记前先 Read 它，插在同系列前作之后）；`docs(research): …` 风格提交。

## 读图阶段（核心）

视觉工具：`mcp__4_5v_mcp__analyze_image`，直接传图集 CDN URL（远程直读，不落盘也能读）。标准转写 prompt，照抄：

> 请逐段转写这张技术笔记图片的全部文字内容，包括正文段落、公式、表格每一格、代码块、图示每个框和标签。不要省略，中文输出。先报告图内是否有页码或编号标题。

最后那句"页码/编号标题"是仲裁的钩子——多数技术笔记每页有 `## 3. xxx` 式编号，是检验回传真实性的最强信号。

### 少量图（≤10 张）：主对话直读

双张一批最稳；4-5 张一批丢失率明显升高。回传异常（丢失/空串/乱码）→ 该图单张重读。

### 大批量（>10 张，默认推荐）：Agent 工具并行 fan-out

**关键认知：`Agent` 工具的 general-purpose 子代理（Tools: *）能调用视觉 MCP，而动态 workflow 的子代理不能。** 所以读图用 Agent 并行，每个子代理领 1 篇笔记的全部图：

```
并行派 N 个 general-purpose agent（同一条消息多个 Agent 调用；篇数多时可 run_in_background 分波），
每个的 prompt：
- 你负责小红书笔记《{title}》（id={id}，共 {n} 图）。逐张调用 mcp__4_5v_mcp__analyze_image
  （URL 按序如下：…），使用这个 prompt：{上面的标准转写 prompt}
- 每张回传先查：页码编号是否与前图连续；出现幻觉签名（尾部乱码洪水/虚构 meta 段/无关内容注入）
  → 单张重读该图；仍异常 → 在转写里标 <!-- 待仲裁:图N -->
- 把逐图转写按图序写入 var/xhs_audio/transcripts/{id}.md（格式：文件头记 note_id/标题/分组/图数/
  URL 列表，然后每图一节 "## 图 k/N"+完整转写文字）
- 返回一句话总结：成功几张、存疑几张、文件路径
```

原始转写落盘后，主对话只消费子代理的一句话总结，**上下文压力从"1706 图全文"降到"134 行状态"**。若子代理回传说无法调用视觉工具（环境差异），退回主对话双张批读模式。

转写文件格式范本：本 skill 自带的 `assets/transcript-sample.md`（5 图完整样例；laos 仓库的活副本在 `var/xhs_audio/transcripts/` 下，仅本地不入库）。

## digest 阶段

原始转写就绪后两种方式：

**方式一（推荐）：跑 saved workflow `xhs-digest-fanout`**

```
CreateWorkflow 的 saved 源：{ name: "xhs-digest-fanout", args: {
  out: "docs/research/2026-10-10-xhs-<主题>.md",   // 必填
  group: "G",        // 可选：只处理某字母分组
  maxNotes: 3,       // 可选：试跑上限
} }
```

它会：逐篇并行撰写 digest（每篇一位撰写员读该篇转写文件）→ 按组提炼总结 → 组装调研文档 → 独立读者通读把关 → 发布成品 artifact。缺转写的笔记自动跳过并列进 notCovered。

**方式二：手动**。每篇 digest 模板：

```markdown
#### 《标题》（N 图）

- 要点分节，引用图号如（02/03）；保留全部硬数字（参数量/RTF/MOS/许可/价格/延迟）
- **契合点**：3-6 条可落地启示（结合使用者自己的项目语境）

```

追加用 python heredoc（`open(p,'a',encoding='utf-8')`），勿用 Edit 长串匹配（长文档必然失配）。

## 幻觉仲裁速查（完整版在 references/playbook.md）

| 症状 | 处置 |
|---|---|
| 页码断档（图 3 回传却是 "## 5."） | 该图单张重读 |
| 尾部乱码洪水（成片 `\n`/占位符） | 剔除污染段，前半有效则用前半 |
| 虚构 meta 段（"与 XX 的关系（转写补充）"式自注） | 整段剔除——图内不可能有 |
| 无关内容注入（突然出现市场数据等） | 同上 |
| 同图两次回传不一致 | 单张重读版为准 |
| 空回传 / 429 | 重试；连续失败换批 |

## 环境与纪律（laos 仓库约定，其他仓库类推）

- Windows python：`C:/Users/yaoyue/miniconda3/python.exe`
- 临时物（manifest/transcripts/digests/imgs）只进 `var/`（gitignored）
- 调研文档进 `docs/research/`（日期前缀平铺，永不迁移）；CDN URL 约数小时过期——采集时立即下载 `imgs/<noteId>/*.webp` 备份
- 评测数字一律转写原文实测，不引用宣称值
