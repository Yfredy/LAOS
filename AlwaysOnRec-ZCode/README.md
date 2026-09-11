# AlwaysOnRec-ZCode —— 全天候录音业界对标增量（隔离实现区）

> 本文件夹是 [laos](../README.md) 的**隔离实现区**：把调研报告
> [2026-09-11-verticals-apple-articles.md](../docs/research/always-on-recording/2026-09-11-verticals-apple-articles.md)
> §6 计划中的三个增量任务在这里独立实现（复制 laos/bin/drivers/tests 全量代码，不改动主代码），
> 全部验证通过后再决定是否合回主干。

## 实现的功能（业界对标 → laos 增量）

### 1. journal 记忆条目升级 Apple 式"标题+正文"schema

- **业界依据**：Apple Watch Series 12「Siri Recap」为每段谈话生成 *标题 + 摘要 + 要点*（2026-09-10 发布）；
  laos 的 journal 条目原来只有 `[HH:MM] 转写文本` 裸格式。
- **实现**（`bin/journal.py`）：新增 `_title_of(text)` —— 取转写首句前 20 字作标题
  （无句界 `。！？；` 时回退为全文前 20 字），记忆条目变为：
  ```
  # 今天下午三点和医生讨论了复查安
  [14:30] 今天下午三点和医生讨论了复查安排。他说指标比上个月好转，先维持当前药量。
  ```
- **消费端**（`bin/diary.py`）："五、今天听到的"章节优先渲染标题（剥掉 `#` 前缀），
  标题与时间戳正文同行呈现为 `- 标题｜[HH:MM] 正文截断`。
- **向后兼容**：旧格式条目（无 `# ` 首行）在 diary 中按原样渲染。

### 2. mic.* 能力时间窗（task_scope 新前缀 `time:`）

- **业界依据**：Siri Recap 可"按时间/地点决定何时可听"；laos 原来的 task_scope 只有路径前缀（`/path/`）
  与应用白名单（`pkg:`），没有时间维度。
- **实现**（`laos/kernel.py`）：
  - `task_scope=["time:09:00-18:00"]` → 窗内 `mic.*` 放行，窗外返回
    `EACCES: outside task scope (time window)`；
  - 支持**跨零点**区间（`time:22:00-06:00`，看护夜班场景）；
  - `time:` 只约束 `mic.*` 前缀，其他 syscall 不受影响；无 `time:` 前缀时行为与旧版完全一致；
  - 非法窗口串按不匹配处理（fail-closed：写错 scope 不应意外放行）；
  - 判定时钟 `AgentKernel._now_hhmm()` 为实例可覆盖点（测试注入）；
  - 时间窗外被拒的 `mic.*` 调用同样落 `event:"mic"` 审计（复用 `_deny` 既有红线，隐私语义不变）。
- **用法**：
  ```python
  kernel.spawn(name="daytime-listener", caps=["mic.*"], ctx=ctx, branch="main",
               task_scope=["time:09:00-18:00"])
  ```

### 3. 业界对照文档入口

完整调研（B 端四赛道 / Apple 专题 / 文章语料 / 开源增补）见
[docs/research/always-on-recording/](../docs/research/always-on-recording/)；
本 README 即计划 Task 3 的交付物（在隔离区内文档化，主干 README 待合并时统一更新）。

## 运行与测试

```bash
cd AlwaysOnRec-ZCode
python -m unittest discover -s tests        # 全量回归（含 6 个新增用例）
python -m unittest tests.test_journal tests.test_diary tests.test_scope -v   # 只跑本增量
```

## 变更清单（相对主干）

| 文件 | 变更 |
|---|---|
| `bin/journal.py` | +`_title_of()`；remember 文本升级 `# 标题` schema；pipeline 结果带 title |
| `bin/diary.py` | "今天听到的"渲染标题行（向后兼容旧格式） |
| `laos/kernel.py` | +`_in_time_window()`/`_hhmm_to_min()`；task_scope 闸门新增 `time:` 分支；+`_now_hhmm()` |
| `tests/test_journal.py` | +2 用例（标题 schema / 短文本回退） |
| `tests/test_diary.py` | +1 用例（标题渲染、剥前缀） |
| `tests/test_scope.py` | +`TestTimeWindowScope` 5 用例（窗内/窗外/跨零点/无前缀不误伤/非 mic 不受限） |

隐私红线未动：录音仍必须显式 syscall 触发、`LAOS_REC=0` 全局禁录、每次调用（含时间窗拒绝）写审计。


## 第二批增量（语音模型前沿落地，2026-09-12）

依据 [docs/research/2026-09-12-speech-model-frontiers.md](../docs/research/2026-09-12-speech-model-frontiers.md) §7：

| 模块 | 功能 | 业界依据 |
|---|---|---|
| `laos/vad.py` | **PCEN 前端**（`use_pcen=True`）：能量归一化，大小声同一门限 | EdgeSpot(ICASSP'26)/FusionVAD(Interspeech'25) |
| `laos/kws.py` | **私有唤醒词**：包络 DTW 模板匹配（enroll→match/best），模板纯 JSON 可删 | few-shot KWS 路线（EdgeSpot） |
| `scripts/kws_confusables.py` | **易混词负样本生成器**（声母/韵母替换，确定性零依赖） | LLM-Synth4KWS(Interspeech'25) |
| `laos/audiostore.py` | **编解码留存档**（`journal(archive=...)`）：即焚前留 µ-law 压缩副本（~0.5×）；SNAC 神经编解码为可选依赖 | Mimi/SNAC 低码率 codec（默认关，见下红线） |
| `laos/pronunciation.py` + `ear.assess` | **发音韵律评估**：流利度/节奏两维零依赖；音素准确度留 GOPT 后端插桩 | GOPT+speechocean762 四维口径 |
| `laos/kernel.py`（既有） | `task_scope=["time:HH:MM-HH:MM"]` mic 时间窗 | Apple Siri Recap 时间/地点调度 |

测试：`python -m unittest discover -s tests`（261 → **277 项**）。

## 合规红线（功能设计约束，执法期已到）

全天候录音 + 听觉推断功能的定位边界，来源见 [业界调研·社会接受度篇](../docs/research/always-on-recording/social-acceptance.md) 与 [前沿地图 §5.6](../docs/research/2026-09-12-speech-model-frontiers.md)：

1. **EU AI Act（2025-02-02 生效）**：禁止在**工作场所与教育机构**用生物识别数据推断情绪（医疗/安全目的窄豁免，罚款至全球营业额 7%）。→ laos 的情绪/压力功能必须定位为"用户自主健康监测"，禁止以"员工/学生监控"名义部署；依赖环境不得默认在工作/教学设备常开。
2. **中国 PIPL + GB/T 41807 + 2025 新国标**：**声纹 = 敏感个人信息**，需单独同意，禁止诱导/欺骗采集。→ laos 不建长期声纹库；说话人功能用"到达顺序"（Streaming Sortformer 式）或会话内临时锚定；唤醒词模板只存能量包络（JSON，不含可重建语音）。
3. **健康推断的表述红线**：语音筛查类能力公开上限≈敏感度 71%（抑郁）/59% UAR（MCI）——**只能输出纵向差分提示（"与自己比"），禁止临床/诊断话术**；呼吸/咳嗽类到达筛查级（COPD F1 0.84），不构成诊断。
4. **留存档开启即担责**：`audiostore` 留存的是可重建音频——默认关闭；开启的用户须自行设定档期清理，且对外分享前应走匿名化（VoicePrivacy 协议）。
5. **可见性**：常驻录音必须有系统级可见状态（时间窗 + `LAOS_REC=0` 总开关 + `event:"mic"` 审计 + 真机常驻通知）——旁观者知情是 Apple 尚未做到、laos 的差异化承诺。
