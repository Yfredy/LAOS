# 如何让 AI 输出更容易理解 —— 复现与 laos 采纳

> 2026-10-08 · 小红书笔记《如何让 AI 输出更容易理解》复现轨道
> 来源链：XHS 笔记（og:description + 01:07 视频）→ 溯源 [Karpathy 原帖 2026-10-02](https://x.com/karpathy/status/2105819303471976479) → laos 采纳落地（`laos/ste.py` + `laos/traceviz.py` + `laosctl traceviz` + kernel lint 钩子，主库 911 测试绿）
> 定位：laos 输出层的可理解性波次——上一波（JitMem，v0.24.0）刚造出 laos 自己的"AI 输出物"（curate briefing），本波用 Karpathy 四阶梯改进它。

## 1. 笔记抄录（◐ 转译源）

og:description（webReader 服务器侧取件）：

> AI 写得越来越快，人越读越累——Karpathy 说这是理解速度的瓶颈。
> 如何让 AI 输出更容易理解，他提出四个方法：
> 🸸 约束语言：ASD-STE100 规范，字数砍半
> 🸸 生成图表：架构、调用链一张图看懂
> 🸸 交互网页：参数亲手拨，即时验证
> 🸸 解释视频：3Blue1Brown 风格动画
> 提醒：格式越好懂，错误藏得越深。你会先试哪一个？

## 2. 溯源核实

| 项 | 事实 | 核实 |
|---|---|---|
| 出处 | Karpathy 原帖 2026-10-02（x.com/karpathy/status/2105819303471976479），四阶梯**升序有用性**：Writing（ASD-STE100 或"80% of the way to ASD-STE100"）→ Diagrams（"a lot easier to process, parse, and understand"）→ Web pages（要 HTML 交互）→ Explainer videos（他"most bullish on"，3b1b 风格 + ElevenLabs 配音，"This is actually starting to work!"） | ●（fxtwitter API + [Search Engine Journal 报道](https://searchenginejournal.com/karpathy-llm-aircraft-manual-writing/591813)交叉） |
| 背景主张 | "a lot more of our work will rise up the abstractions into oversight and understanding"——理解/监督成为主要工作 | ● |
| ASD-STE100 | 欧洲航空航天协会（ASD）维护的国际技术写作标准：写作规则 + **~900 批准词**字典，one word one meaning；FAQ 明言 STE 非通用写作用途、无工具能替代标准本身；标准免费分发但**词表再分发受限** | ●（SEJ 转 ASD FAQ） |
| 社区落地 | [asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)（MIT，~4k stars）：Claude Code skill + 确定性 Python linter（查同义词轮换/被动语态/长句/分号/hedge 堆叠等）；**刻意不含官方词表**（许可证限制，只取原则） | ● |
| 笔记四方法 vs 原帖 | 约束语言/图表/交互网页/解释视频四项全部对得上（顺序=原帖升序） | ● 转译无讹变 |
| "格式越好懂，错误藏得越深" | **未见于原帖与两篇报道**——笔记转译层增补（方向合理：简化是有损变换），本报告按治理原则采纳但不归于 Karpathy | ○ 笔记增补 |
| "字数砍半" | 笔记表述；原帖/SEJ 未给此数字（STE 仅有句长/一句一事等规则） | ○ 未证实数字 |

## 3. laos 采纳：四阶梯 × 裁决

| Karpathy 阶梯 | laos 裁决 | 落点 |
|---|---|---|
| ① 约束语言 ASD-STE100 | ● 本波落地（check-only lint） | `laos/ste.py`：五规则可测子集——R1 句长（分句后 >60 字）、R2 术语轮换（同义组 ≥2 形并存；Karpathy 点名痛点 agent/worker/executor）、R3 一句多事（子句分隔 >2）、R4 hedge 堆叠（同句 ≥2 模糊限定词）、R5 分号并联；`python -m laos.ste` CLI（有问题 exit 1，fail-loud）；**只检查不改写**，问题带原文摘录+位置 |
| ② 生成图表（调用链一张图） | ● 本波落地 | `laos/traceviz.py`：audit.jsonl 的 event:"syscall" → mermaid sequenceDiagram（agent↔kernel，失败调用 `--x` 显式标出）；`laosctl traceviz --tail N` 子命令 + `python -m laos.traceviz`；**只读派生视图**，审计永远是权威源 |
| ③ 交互网页 | ◐ P2 排队 | laosweb 已有审计查看页；"参数亲手拨"式交互属前端增强，不入内核波次 |
| ④ 解释视频 | ○ 不做 | 3b1b 风格视频管线需重依赖 + 云端 TTS（ElevenLabs），撞零依赖与隐私双红线；内核域无此管线 |
| 警告句（笔记增补） | ● 采纳为治理原则 | 简化是有损变换——一切派生物双层结构：ste 报告带原文摘录不改写；traceviz 不回写审计；kernel lint 钩子只记数不动文本。与 JitMem"绝不截断原文"同一原则族 |

**词表许可声明**：本波不收 ASD 官方 ~900 词表（再分发受限），与 asd-ste100-skill 同一取舍——只取原则（一句一事/one word one meaning/短句），规则全部自研且开源可测。

## 4. 落地件与验收

| 件 | 内容 | 测试 |
|---|---|---|
| `laos/ste.py` | `lint(text, max_sentence_chars=60, max_clauses=2, term_groups=None, rules=all)` → 问题清单（rule/detail/excerpt/hint/pos，按位置确定性排序，R2 文档级 pos=-1 最前）；CLI `python -m laos.ste [file|-] [--max-chars N] [--rules R1,R2]` | 17 例（含 CLI 子进程 exit code、边界值、中文分句、术语组注入、规则开关） |
| `laos/traceviz.py` | `to_mermaid(records, tail=40)`；参与者名清洗（`:` `;` 换行破坏 mermaid 语法）；非 syscall 行忽略；tail 最近窗口 | 10 例（含 laosctl 子命令子进程、`python -m` 入口） |
| `bin/laosctl.py` | 新子命令 `traceviz`（+`--tail`，默认 40） | 并入上项 |
| `laos/kernel.py` | `LAOS_STE_LINT=1` 时 `mem.curate` 的 briefing 过 lint，`ste_problems` 计数入审计（opt-in，默认零行为变化；payload 文本原样返回） | 2 例（启用记数/默认无字段） |

**改进对象即上一波产物**：JitMem curate briefing 是 laos 第一个系统性"AI 输出物"，本波给它的可读性上了治理钩子——这就是"用这个进行改进"的落点。全套 **911 绿**（884→911，OK skipped=5）。

## 5. 结论

Karpathy 四阶梯是提示工程层的建议，laos 的取法是把它翻译成**治理件**：约束语言变成 check-only lint（不改写、原文权威），图表变成审计的只读派生视图，交互页排队，视频不做——每一条都过一遍"与红线的关系"再落地。笔记那句"格式越好懂，错误藏得越深"虽非 Karpathy 原话，却恰好说中了派生视图的治理要害，采纳为双层结构原则：**一切好懂的东西都必须能回到不好懂的原始记录**。
