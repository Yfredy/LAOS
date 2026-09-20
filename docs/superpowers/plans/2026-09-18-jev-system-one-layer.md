# Jev "System One" 判断层 —— 学习/普查/laos 落地实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学透 Jev（TypeSafe AI 的 System One 判断模型，2026-09-15 发布）并普查其开源生态，把「廉价结构化判断」作为一层（judge layer）落进 laos：高危操作机器预审、记忆入库过滤、上下文压缩判断、技能沉淀质量闸。

**Architecture:** 新增 `laos/judge.py`——可插拔判断后端（`none` 零依赖兜底 / `cloud` TypeSafe API / `local` 本地 OpenAI 兼容端点跑 NanoJev/jevlike 权重），三判型对齐 Jev 语义：`noul()`(布尔+置信度)、`choice()`(2-255 选项)、`score()`(2-10 有序级)。内核三处消费：确认横幅预审、mem.remember 过滤、ContextManager 压缩选择；SkillStore 一处消费：沉淀质量闸。所有消费点由 `LAOS_JEV_*` 环境变量开关，**默认全关**（零依赖与"默认收紧"红线不变）。

**Tech Stack:** 纯 stdlib + curl 子进程（同既有爬虫纪律）；本地后端经 OpenAI 兼容 HTTP 端点（用户自架 NanoJev/jevlike/simple-jev）；测试用 FakeJudge 注入。

**Spec:** 本计划 §0 即规格（Jev 语义三判型 + 生态事实），依据：
- 36kr/机器之心报道（2026-09-20）：Jev 0.44s/次、$0.00035/次、40s 判 724 条广告 8,724 次判断 $0.09
- `corpus/jev_readme_TianyuCodings__NanoJev.md`：0.6B 本地复刻（Qwen3-0.6B+决策头，批量并行判断，零输出 token 解码；ViZDoom 128/128 vs Jev 56/128）
- `corpus/jev_readme_vinnylarouge__jevlike.md`：option-attention 极简架构（每选项 query→context 注意力→共享打分→softmax）
- `corpus/jev_readme_yibie__awesome-jev.md` + `jev_repos_curated.json`（20 仓库，browser-use/jev-ultrafast ★11k、fast-jev-compaction ★4.9k、simple-jev"任意开源模型变 jev 端点"）
- LangChain Jev-as-a-judge 实验（09-20）：单次 0.44s/$0.00035

## Global Constraints

- 零第三方依赖（stdlib only）；HTTP 一律 curl 子进程
- 隐私红线不动：判断层只读"当前操作的文本表示"，不新增录音/遥测；`LAOS_REC=0` 等既有开关不受影响
- **所有 judge 消费点默认关闭**：`LAOS_JEV_BACKEND=none` 时内核行为与现状逐字节一致（每处集成有回归测试钉住）
- 判断结果必须写审计（`event:"jev"`，含 question 哈希、判定、置信度）——可追责口径与 mic 审计一致
- 主库 253 + 隔离区 279 测试为底线，新增 ~20 项

---

### Task 1: Jev 生态研究报告

**Files:**
- Create: `docs/research/2026-09-18-jev-landscape.md`
- Modify: `docs/research/corpus/jev_repos_curated.json`（已有 20 条，补抓 awesome-jev 内的遗漏项目）

**Interfaces:**
- Produces: 研究报告（Jev 三判型语义表、API 形态、生态仓库分级清单、本地复刻路线对比 NanoJev/jevlike/simple-jev），供 Task 2-5 引用

- [ ] **Step 1:** 精读已抓 4 份 README（NanoJev/jevlike/simple-jev/awesome-jev），从 awesome-jev 提取官方资源（TypeSafe blog/docs/API）与社区项目全名单，补入 curated JSON
- [ ] **Step 2:** WebFetch TypeSafe 官方 blog（introducing-system-one-models-and-jev）核实三判型的确切 API 形状与定价口径
- [ ] **Step 3:** 写研究报告：§1 Jev 是什么（三判型/概率输出/零生成）§2 生态地图（按 用途分类：compaction/judge/浏览器/微调复刻）§3 本地化路线对比（NanoJev 0.6B vs jevlike 极简 vs simple-jev 网关）§4 laos 四个落点的论证
- [ ] **Step 4:** `git commit -m "docs(research): Jev System-One landscape"`

### Task 2: `laos/judge.py` 判断器骨架（可插拔后端 + 零依赖兜底）

**Files:**
- Create: `laos/judge.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Produces（后续任务消费的确切签名）:
```python
class JudgeResult:  # dataclass
    verdict: str      # "allow" | "deny" | "level_0".."level_9" | 选项文本
    confidence: float # 0..1
    raw: dict         # 后端原始返回（审计用）

class JudgeBackend:
    def noul(self, context: str, question: str) -> JudgeResult
    def choice(self, context: str, question: str, options: list[str]) -> JudgeResult
    def score(self, context: str, question: str, levels: int = 5) -> JudgeResult

def select() -> JudgeBackend   # LAOS_JEV_BACKEND: none(默认)|rule|cloud|local
class RuleBackend(JudgeBackend)  # 零依赖兜底：确定性关键词规则（question 内含 deny 词表→deny 0.99 之类），保证默认链路可测
class CloudBackend(JudgeBackend) # TypeSafe API（LAOS_JEV_API_KEY）
class LocalBackend(JudgeBackend) # OpenAI 兼容端点（LAOS_JEV_ENDPOINT，如 NanoJev/simple-jev 服务）
```

- [ ] **Step 1: 写失败测试 `tests/test_judge.py`**——用例：①`select()` 默认返回 RuleBackend ②RuleBackend.noul 命中 deny 词表返回 ("deny", ≥0.99) ③RuleBackend.choice 均匀打分返回第一项 ④CloudBackend 构造带 API key 且请求体含 context/question（mock curl）⑤LocalBackend 解析 OpenAI 兼容响应 ⑥`select()` 按 `LAOS_JEV_BACKEND=local` 返回 LocalBackend
- [ ] **Step 2:** `python -m unittest tests.test_judge -v` 确认 FAIL
- [ ] **Step 3:** 实现 `laos/judge.py`（RuleBackend 词表判定：deny 词表 = ["危险","删除全部","格式化","rm -rf","泄露隐私"]；Cloud/Local 的 HTTP 走 curl 子进程，请求体 JSON：`{"context","question","mode","options","levels"}`）
- [ ] **Step 4:** 测试 PASS
- [ ] **Step 5:** `git commit -m "feat(judge): pluggable System-One judge backends"`

### Task 3: 内核确认横幅机器预审

**Files:**
- Modify: `laos/kernel.py`（confirm 闸门处，`spec.risk == "high"` 分支之前插预审）
- Test: `tests/test_jev_gate.py`

**Interfaces:**
- Consumes: Task 2 `judge.select()`
- Produces: 审计事件 `{"event":"jev","tool":...,"verdict":...,"confidence":...}`；`LAOS_JEV_AUTOGATE=1` 且 confidence≥`LAOS_JEV_AUTOGATE_MIN`(默认0.95) 时跳过人类确认直接放行

- [ ] **Step 1: 写失败测试**——FakeJudge 注入 kernel（`kernel.judge = FakeJudge(("allow",0.97))`）：①AUTOGATE=1+高置信 → `proc.exec` 不经 confirm 直接成功且审计含 `event:"jev"` ②低置信(0.6) → 仍走人类 confirm ③默认 BACKEND=none → 行为与现状一致（无 jev 审计、confirm 照旧）④FakeJudge(("deny",0.99)) → 直接拒绝 EDENIED 且 reason 带 `jev-prejudge`
- [ ] **Step 2:** 确认 FAIL
- [ ] **Step 3:** 实现——kernel.__init__ 里 `self.judge = judge.select()`；confirm 前：`if self.judge 非 none 且 (AUTOGATE or LAOS_JEV_PREVIEW)`: noul(f"允许执行 {tool} {args} 吗？agent={pcb.name}")；verdict=="deny"→`_deny(... "EDENIED: denied by jev prejudge")`；allow+高置信+AUTOGATE→跳过 confirm；每次写 `event:"jev"` 审计
- [ ] **Step 4:** 全量测试 PASS（含"默认行为不变"用例）
- [ ] **Step 5:** `git commit -m "feat(kernel): jev prejudge gate for high-risk syscalls (opt-in)"`

### Task 4: 记忆入库过滤 + 上下文压缩判断

**Files:**
- Modify: `laos/memory.py`（MemoryStore.remember 增可选 `judge=` 参数）
- Modify: `laos/context.py`（`_compact_if_needed` 的受害者选择增 judge 分支）
- Test: `tests/test_jev_mem_ctx.py`

**Interfaces:**
- Consumes: Task 2 `JudgeBackend.noul`
- Produces: `MemoryStore.remember(kind,text,tags,judge=None)`——judge 非 None 时 noul("值得长期记住且无隐私风险") 为 deny → 拒绝入库返回 None（审计留在调用方）；`ContextManager(judge=)`——压缩时对候选 victims 逐条 noul("此消息可安全丢弃（信息已概括或临时）")，deny 的消息移出 victims 保留

- [ ] **Step 1: 写失败测试**——①remember + FakeJudge(deny) → 记忆库 total 不变、返回 None ②FakeJudge(allow) → 正常入库 ③不传 judge → 行为与现状一致 ④ContextManager(judge=FakeJudge(deny 首条)) → 压缩时首条消息被保留、其余照常压缩 ⑤默认无 judge → 压缩仍按最老 1/3（既有测试不破）
- [ ] **Step 2:** 确认 FAIL
- [ ] **Step 3:** 实现（两处均为可选参数路径；laosweb/laosd 的装配由 `LAOS_JEV_MEM=1`/`LAOS_JEV_COMPACT=1` 控制，进 Task 5）
- [ ] **Step 4:** 全量 PASS
- [ ] **Step 5:** `git commit -m "feat(mem,ctx): jev-filtered memory intake and compaction (opt-in)"`

### Task 5: SkillStore 沉淀质量闸 + 装配与文档

**Files:**
- Modify: `laos/skills.py`（技能沉淀处 noul("此任务轨迹确实达成了目标")，deny 不沉淀）
- Modify: `bin/laosd.py`（装配：按环境变量把 judge 注入 kernel/memory/context/skills）
- Modify: `README.md`（第十节后补"Jev 判断层"小节：三判型表 + 环境变量表新增 6 行）
- Test: `tests/test_jev_skills.py`

**Interfaces:**
- Consumes: Task 2-4 全部
- Produces: `SkillStore.record(trace, judge=None)`；环境变量：`LAOS_JEV_BACKEND / LAOS_JEV_API_KEY / LAOS_JEV_ENDPOINT / LAOS_JEV_AUTOGATE / LAOS_JEV_AUTOGATE_MIN / LAOS_JEV_MEM / LAOS_JEV_COMPACT / LAOS_JEV_SKILL`

- [ ] **Step 1: 写失败测试**——FakeJudge(deny) → skill 库不新增；allow → 新增；无 judge → 现状一致
- [ ] **Step 2:** FAIL 确认
- [ ] **Step 3:** 实现 skills.py + laosd 装配 + README 小节
- [ ] **Step 4:** 全量 PASS（两端 253+279 底线 + 新增）
- [ ] **Step 5:** `git commit -m "feat(skills): jev quality gate for skill distillation + wiring/docs"`

### Task 6: 收尾推送

- [ ] **Step 1:** 全量测试（主库 + 隔离区）
- [ ] **Step 2:** `git push origin master`（失败等 60s ×3）
- [ ] **Step 3:** 交付说明（Jev 是什么/四落点/开关清单/本地化路线：要真离线，架个 NanoJev 或 simple-jev 端点即可）

## Self-Review

- 覆盖：学习（Task 1）✓ 全量搜索（Task 1 Step 1 + 已入库 `jev_repos_curated.json` 20 条 + awesome-jev 生态图）✓ laos 落地构思（Task 2-5 四落点）✓
- 占位符：判型签名/环境变量/词表/测试用例全部写实 ✓
- 类型一致：`JudgeResult`/`select()` 签名在 Task 2 Produces 与 Task 3-5 Consumes 逐字一致 ✓
- 红线核查：默认全关 + 回归钉住 ✓；judge 只读操作文本 ✓
