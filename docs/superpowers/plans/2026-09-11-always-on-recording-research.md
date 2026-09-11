# 全天候录音行业调研（文章 + 开源项目）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全方面搞清业界如何应用"全天候录音"——商业产品、开源项目、学术论文、隐私法律、功耗工程、失败案例六个维度——产出一份与 `docs/research/agentos-landscape-2026-08.md` 同风格的全景报告，并落出"对 laos 的启示"。

**Architecture:** 调研 = 种子盘点 → 分维度采集（每个维度一轮"精确搜索 → 逐条验证 → 立即写入报告对应章节 → commit"）→ 综合分类学。核心交付物是一个文件：`docs/research/2026-09-11-always-on-recording-landscape.md`，骨架先建好，六个 task 各自往里填章节，每个 task 独立可验收、独立 commit。论文 PDF 下载复用仓库既有脚本模式（`var/download_papers.py`）。

**Tech Stack:** WebSearch / WebFetch（官方页、Hacker News Algolia API、GitHub 页面）、arXiv API（复用 `var/search_arxiv.py` / `var/download_papers.py` 的模式）、纯 markdown 报告。

**Spec:** 用户需求（"找出全天候录音的文章与开源项目，全方面了解业界如何应用"）；既有基础 = `docs/superpowers/plans/2026-09-10-always-on-audio-journal.md` Part A（已点名 Limitless/Plaud/Otter/Recall/Corama/Ellipsis/Alexa Care Hub）+ `docs/research/papers/MANIFEST.txt`（119 篇 AIOS 论文，其中音频相关者需筛出）。本计划产出报告后，Part A 的"谁在做"一节就有了完整证据链。

## Global Constraints

- 报告文件固定为 `docs/research/2026-09-11-always-on-recording-landscape.md`，全文中文、引用保留原文（与既有 research 笔记风格一致）
- **每条事实必须带可点击来源 URL**；无法双源验证的写"待验证"标注，不得当定论
- 所有商业产品必须标注**现状（2026-09 时点）**：在售 / 已死 / 被收购 / 转型——这个领域一年一洗牌，2024 年的结论不能直接抄
- 不付费、不下载盗版内容；商业信息优先官网与主流科技媒体（The Verge / TechCrunch / 404 Media），开源信息优先 GitHub 仓库本体
- 新下载的论文 PDF 存入 `docs/research/papers/` 并同步更新 `MANIFEST.txt`
- 与既有 plan Part A 的结论（四段漏斗、2.7GB/天、即焚策略）**不矛盾**，报告是对它的证据补全与扩展
- 每完成一个 task：报告更新 → `git commit`（`docs(research): landscape §N ...`）
- 验收底线（终审 task 检查）：≥15 个商业产品、≥12 个开源项目、≥8 篇相关论文、3 个专题（隐私/功耗/失败案例）、1 节"对 laos 的启示"

---

### Task 1: 种子盘点与报告骨架

**Files:**
- Create: `docs/research/2026-09-11-always-on-recording-landscape.md`（骨架 + §1 已知事实）
- Read: `docs/superpowers/plans/2026-09-10-always-on-audio-journal.md`（Part A）、`docs/research/agentos-landscape-2026-08.md`（风格基准）、`var/search_arxiv.py`、`var/download_papers.py`（确认可复用的函数签名）

**Inputs:** 既有调研里已点名但未展开的产品与论文。
**Outputs:** 报告骨架全部章节就位；§1"已知事实"填满；119 篇论文标题拉取完成、音频相关者列表产出（供 Task 4 用）。

报告骨架（照抄进文件）：

```markdown
# 全天候录音（Always-on Audio）行业全景调研
> 调研时间：2026-09-11
> 目的：回答"业界如何应用全天候录音"——谁在做、怎么做的（架构）、
> 为什么有人付钱（场景）、怎么死的（教训）、laos 能学到什么。
> 姊妹篇：[agentos-landscape-2026-08.md](agentos-landscape-2026-08.md)（AgentOS 路线）；
> 本文为其"听觉感官"维度的展开，并给 [always-on-audio-journal 计划](../superpowers/plans/2026-09-10-always-on-audio-journal.md) Part A 补全证据链。

## 1. 已知事实（来自既有调研，本文补全证据）
## 2. 商业产品全景（形态光谱 + 对比表）
## 3. 开源项目全景（对比表 + 六个深读）
## 4. 学术论文（既有 119 篇筛选 + 新采集）
## 5. 隐私与法律专题
## 6. 功耗、存储与硬件工程专题
## 7. 失败案例与教训
## 8. 共性架构模式（业界收敛出的漏斗）
## 9. 对 laos 的启示
## 10. 参考清单
```

§1 需从 Part A 抄入并补证据链接的已知事实（每条一行，标注来源）：

- Limitless Pendant：$199 吊坠，全天候录音+转写+摘要，定位"记忆外挂"（ limitless.ai ）
- Plaud Note：录音卡片（ plaud.ai ）
- Otter.ai：会议转写独角兽（ otter.ai ）
- Microsoft Recall：全屏截图版常驻记录，隐私争议极大（support.microsoft.com + 批评报道）
- Corama / Ellipsis Health：语音生物标记物方向
- Amazon Alexa Care Hub：看护场景
- 16kHz 16bit 原始音频 = 2.76GB/天 → 原音频必须即焚（算术：16000×2×86400≈2.76e9 B）
- 中国民法典 1033 条：录制他人需知情同意

- [ ] **Step 1:** 读 Part A / agentos-landscape / 两个 var 脚本，确认可复用点（`download_papers.py` 的下载函数、`search_arxiv.py` 的 API 封装）
- [ ] **Step 2:** 用 arXiv API 批量拉取 119 个 ID 的标题（shell 里 `python - <<'EOF'` 调 API 一次拿全，或复用既有脚本），按标题关键词（audio/speech/sound/acoustic/wearable/memory/voice）筛出相关子集，写入 §4 的"既有论文筛选"小节
- [ ] **Step 3:** 创建报告文件，写入上述骨架 + §1 八条已知事实
- [ ] **Step 4:** Commit — `docs(research): landscape skeleton and known facts`

### Task 2: 商业产品全景（报告 §2）

**Files:**
- Modify: `docs/research/2026-09-11-always-on-recording-landscape.md` §2

**Inputs:** Task 1 骨架。
**Outputs:** ≥15 个产品的对比表 + top5 产品各 2–3 行深度点评；每个产品含"现状(2026-09)"。

对比表列定义（照抄，每行必须有来源链接，无源写"待验证"）：

```markdown
| 产品 | 形态 | 价格 | 录音策略 | 存储/保留 | ASR 云/本地 | 隐私机制 | 商业模式 | 现状(2026-09) | 来源 |
|---|---|---|---|---|---|---|---|---|---|
| Limitless Pendant | 吊坠+App+Web | $199 | 全天常录 | 云端，可删 | 云 | 请求在场者同意模式 | 硬件+订阅 | 待验证 | [link] |
```

必查清单（16 个种子，逐一搜索验证；搜不到/已死也要在表里给一行"已死/查无"结论）：

1. Limitless（pendant + desktop app，Rewind 转型而来）
2. Omi / BasedHardware（前 Friend，$89 吊坠 + DevKit，开源含硬件）
3. Friend 吊坠（消费品牌，2025-06 纽约地铁广告"监控"争议）
4. Bee（$49 腕带；2025-07 被 Amazon 收购——验证现状与团队去向）
5. Plaud Note / NotePin（录音卡片/胸针，订阅制转写）
6. Tab by Avi Schiffmann（AI 伴侣吊坠，验证价格与现状）
7. Meta Ray-Ban Display + Neural Band（2025-09 发布；持续拾音边界）
8. Ray-Ban Meta Gen2（对比项：常驻唤醒 vs 常驻录音的产品边界）
9. Humane AI Pin（已死；HP 收购，复盘在 Task 5/7）
10. Rabbit R1（现状）
11. Granola（Mac 会议笔记 App，屏幕音频混合路线）
12. Otter.ai（会议 bot 路线）
13. Fireflies.ai / tl;dv（bot 派代表，表里合并一行即可）
14. Microsoft Recall（截图派；验证 2025-2026 是否加入音频）
15. Google Pixel Recorder + Call Notes / Pixel Journal（手机端本地转写代表）
16. 讯飞录音笔（SR 系列）+ 讯飞听见（中国市场常录+实时转写硬件代表；另查一道智能录音耳机的做法）

搜索词（逐条执行，英文为主、中文产品用中文搜）：

- `Limitless pendant review 2026`；`Omi AI wearable BasedHardware 2026`；`Friend pendant surveillance backlash`
- `Bee wearable Amazon acquisition`；`Plaud NotePin review`；`Tab AI companion pendant price`
- `Meta Ray-Ban Display always listening privacy`；`Humane AI Pin what went wrong`
- `Granola AI notetaker how it works`；`Microsoft Recall audio recording 2026`
- `Pixel 10 Recorder on-device transcription`；`讯飞录音笔 实时转写 隐私`
- `audio journal app voice diary 2026`（捞长尾：Voicenotes、AudioPen 一类，捞到 2 个即可入表）

- [ ] **Step 1:** 按 16+3 条搜索词逐条 WebSearch；官网 WebFetch 确认价格/隐私页；每个产品记入对比表（含"现状"字段）
- [ ] **Step 2:** 为 Limitless、Omi、Bee、Meta Ray-Ban Display、Pixel Recorder 五个写 2–3 行点评：录音何时开、数据存哪、谁付钱
- [ ] **Step 3:** §2 开头写"形态光谱"一段：手机App → 桌面App → 录音笔 → 吊坠/腕带 → 眼镜 → （截图派对照）
- [ ] **Step 4:** Commit — `docs(research): landscape commercial products survey`

### Task 3: 开源项目全景（报告 §3）

**Files:**
- Modify: `docs/research/2026-09-11-always-on-recording-landscape.md` §3

**Inputs:** Task 1 骨架。
**Outputs:** ≥12 个仓库的对比表 + 6 个深读小节（每个：架构一图流水线、栈、活跃度、对 laos 可借鉴点）。

对比表列定义：

```markdown
| 项目 | ★/最近提交 | 形态 | 采集层 | VAD/唤醒 | ASR | 存储/记忆 | 本地or云 | 硬件平台 | 对 laos 可借鉴点 |
|---|---|---|---|---|---|---|---|---|---|
```

种子清单（12 个已知 + 3 轮捞新；owner 名以 GitHub 实搜为准，不确定就先搜再写）：

1. `BasedHardware/omi`——开源 AI 可穿戴全栈（固件 C++ + App Flutter + 后端）
2. `mediar-ai/screenpipe`——Rust 24/7 屏幕+音频采集本地库 + 插件生态（与 laos 漏斗最像）
3. open-recall（GitHub 搜 `open recall`）——MS Recall 的开源复刻，截图+OCR
4. `snakers4/silero-vad`——事实标准流式 VAD（ONNX）
5. `espressif/esp-sr` + ESP-Skainet——ESP32-S3 上的唤醒词+VAD（毫瓦级常驻检测的代表）
6. `rhasspy/wyoming-satellite`——开源语音卫星（常听 + 触发上报的分布式方案）
7. HeyWillow/willow——开源语音卫星（验证是否已归档，归档时间即"社区项目生命周期"样本）
8. `dscripka/openWakeWord` 与 ESPHome microWakeWord——本地唤醒词
9. `ggml-org/whisper.cpp`——本地 ASR 事实标准
10. `moonshine-ai/moonshine`——边缘 ASR（Useful Sensors）
11. `k2-fsa/sherpa-onnx`——流式端侧 ASR/说话人（laos 可直接换用的选项）
12. `pyannote/pyannote-audio`——说话人分离（"多人环境录到他人"的工程解）
13. `OpenAcousticDevices/AudioMoth`——野生动物声学记录仪（跨域：duty-cycle 省电调度样本）
14. `thewh1teagle/vibe`——桌面转写 App（UI 层参考）

捞新搜索词（GitHub 搜索页或 API）：

- `always-on audio recording`；`audio lifelogging`；`24/7 audio capture local`；`audio diary self-hosted`；`personal AI wearable open source`
- HN 捞：`https://hn.algolia.com/api/v1/search?query=screenpipe&tags=story` 与 `query=Show%20HN%20audio%20diary`——评论区常挖出小而美仓库

深读 6 选（README + 架构文档 + commits 活跃度）：omi、screenpipe、open-recall、esp-sr、wyoming-satellite、silero-vad。每个深读必须回答三个问题：① 漏斗怎么分段（采集/检测/蒸馏/存储）② 隐私默认值是什么 ③ laos 漏斗（laos/vad.py → drv_rec → ear.journal → mem）与之差在哪一步。

- [ ] **Step 1:** 14 个种子逐一 WebFetch GitHub 页：确认 ★/最近提交/语言/架构描述 → 填表
- [ ] **Step 2:** 3 轮捞新搜索，新仓库 ≥2 个才写"捞新增补"小节（没有就写"未发现新形态"——空结论也是结论）
- [ ] **Step 3:** 6 个深读小节，每个含"对 laos 可借鉴点"收尾句
- [ ] **Step 4:** Commit — `docs(research): landscape open-source projects survey`

### Task 4: 学术论文（报告 §4）

**Files:**
- Modify: `docs/research/2026-09-11-always-on-recording-landscape.md` §4
- Create: `docs/research/papers/<arxiv-id>.pdf`（≤8 篇）
- Modify: `docs/research/papers/MANIFEST.txt`

**Inputs:** Task 1 的既有论文筛选结果。
**Outputs:** ≥8 篇新论文，每篇 2 行注释（问题/与 laos 关系）。

arXiv API 查询串（`http://export.arxiv.org/api/query?search_query=...`，逐条执行，取相关性 top5）：

- `all:"audio lifelogging"` 与 `all:"acoustic lifelog"`（生活日志录音）
- `all:"wearable memory aid"` 与 `ti:"memory prosthesis"`（记忆外挂/假体）
- `all:"always-on" AND all:"keyword spotting"`（毫瓦级常驻检测）
- `all:"vocal biomarkers" AND all:"depression"`（情绪健康追踪）
- `all:"egocentric audio"`（第一视角音频，Aria/Ego4D 系）
- `all:"duty-cycled" AND all:"acoustic"`（省电占空比调度）
- `all:"on-device speech recognition" AND all:"survey"`（端侧 ASR 综述）

- [ ] **Step 1:** 逐条执行查询，摘 title/abs/日期，按"与四段漏斗哪一段相关"归组写入 §4
- [ ] **Step 2:** 选 ≤8 篇必读下载 PDF 到 `papers/`（复用 `var/download_papers.py` 的请求模式），更新 `MANIFEST.txt`（新增"Always-on audio 相关"小节）
- [ ] **Step 3:** 每篇写 2 行注释：研究问题一句话 + 对 laos 的关系一句话
- [ ] **Step 4:** Commit — `docs(research): landscape academic papers for always-on audio`

### Task 5: 三大专题（报告 §5–7）

**Files:**
- Modify: `docs/research/2026-09-11-always-on-recording-landscape.md` §5–7

**Inputs:** Task 2/3 积累的产品与仓库事实。
**Outputs:** 隐私法律 / 功耗存储 / 失败案例三个专题，各 ≥3 个带来源的论据。

§5 隐私与法律，必查：

- Friend 吊坠"监控广告"抵制事件（404 Media / The Verge 报道）
- Microsoft Recall 隐私争议时间线（推迟→改默认关→欧洲上市受阻）
- 录音同意的司法辖区差异：中国民法典 1033 条、美国 one-party vs two-party consent（加州）、GDPR 对持续生物特征处理的要求
- on-device 派的隐私主张：Pixel Recorder/Omi 的"音频不出设备"宣传与实际差距（是否有云 fallback）

§6 功耗存储工程，必查：

- 常驻拾音功耗阶梯：模拟前端+DSP 唤醒（esp-sr 官方功耗数据）→ 手机前台服务（Android wake lock 代价）→ AP 常醒（不可行，与既有 plan Part B 结论互证）
- AudioMoth 的 duty-cycle 调度参数（录 X 秒睡 Y 秒）——laos ADSP 常驻路线的调度参考
- 存储算术：16kHz/16bit = 2.76GB/天 vs "仅存有声段"实测值（omi/screenpipe 社区数据）
- 商业产品的保留策略对照：Limitless/Recall 各自默认存多久

§7 失败案例与教训，必查（每个 = 死因一句话 + 对 laos 的教训一句话）：

- Humane AI Pin（过热/续航/云依赖；HP 收购复盘报道）
- Rewind → Limitless 转型（无限录屏不可持续 → 转硬件+会议场景）
- Friend 广告抵制（"录音"的公众感知 = 监控，产品命名与营销如何踩雷）
- HeyWillow 归档（开源社区项目的维护成本）
- Rabbit R1 现状（验证）

- [ ] **Step 1:** §5 四组论据逐条 WebSearch + 链接
- [ ] **Step 2:** §6 四组论据（esp-sr 功耗数据从官方文档拿）
- [ ] **Step 3:** §7 五个失败案例，WebFetch 各一篇复盘文章
- [ ] **Step 4:** Commit — `docs(research): landscape privacy power and failure case studies`

### Task 6: 综合分类学与 laos 启示（报告 §1/8/9）+ 终审

**Files:**
- Modify: `docs/research/2026-09-11-always-on-recording-landscape.md`（§8、§9、§10；§1 若有修正一并改）

**Outputs:** 业界共性架构分类学 + 对 laos 的可执行启示 + 全文引用核查。

§8 共性架构模式（从 Task 2/3 事实归纳，预期结构）：

- **四段漏斗是业界收敛解**：常驻低耗检测 → 触发捕获 → 即时蒸馏 → 原始数据即焚。每段列 2 个业界实例（产品侧 + 开源侧）
- **分叉点一：蒸馏位置**——云端（Limitless/Otter）vs 本地（Pixel/omi/screenpipe）；隐私卖点与成本结构互为因果
- **分叉点二：触发模型**——全天常录 vs 唤醒词/按钮显式触发 vs 人在场判定（Limitless 的 consent 模式）
- **记忆层模式**——时间线浏览（Pixel/Plaud）vs 检索问答（Limitless/Recall）vs 情绪曲线（临床派）；laos 的 mem.recall 属检索派+情绪曲线混合

§9 对 laos 的启示（三条必须落成可执行句，不用空话）：

- 可直接借鉴：逐条指向 laos 具体文件（如 screenpipe 的插件式消费层 ↔ laos diary/mood_report 的扩展点）
- 应避免：逐条对应 §7 死因（如云依赖 ↔ laos 本地 ASR 路线的正确性）
- 差异化定位一句话：laos = 唯一"零云 + DSP 常驻情绪检测 + Agent 记忆系统打通"的开源路线（用 §2/§3 表格反证没有第二家）

§10 参考清单：全文 URL 汇总，按 产品/开源/论文/报道 分组。

- [ ] **Step 1:** 写 §8/§9/§10
- [ ] **Step 2:** 终审自查：① 数量线——产品 ≥15、仓库 ≥12、论文 ≥8 ② 来源线——每个非"待验证"事实有 URL，报告内无 `[TBD]`/空单元格 ③ 一致线——与 Part A 四段漏斗、2.76GB/天、即焚策略无矛盾 ④ 风格线——与 `agentos-landscape-2026-08.md` 同款（分类坐标轴开头、表格为主体、每节有判断句）
- [ ] **Step 3:** Commit — `docs(research): landscape synthesis and laos implications`

---

## 验收清单

- [ ] `docs/research/2026-09-11-always-on-recording-landscape.md` 十节齐全，§2/§3/§4 达到数量底线
- [ ] 每条事实有来源 URL 或明确"待验证"标注
- [ ] `docs/research/papers/MANIFEST.txt` 已更新且 PDF 落盘
- [ ] §9 对 laos 的启示可执行（指向具体文件/具体产品死因）
- [ ] 6 个 commit（每 task 一个）
