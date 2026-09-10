# 智能手机 Agent 五层能力实施计划（laos × 骁龙真机）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 laos 现有内核上分五层落地"智能手机操作系统里的 Agent"：① 屏幕理解与操控（`drv_screen`，adb 通道）② 端侧 LLM 大脑（`drv_genie`，QAIRT Genie / OpenAI 兼容双后端）③ 通知与通信（`drv_notify`/`drv_comms`/动态功耗定价）④ 全天候感知（App `/events` + `drv_events`）⑤ 越用越聪明（技能库 + 动态风险定价）。五部分相互独立、可单独交付，每部分落地后 laos 的智能手机 Agent 能力上一个台阶。

**Architecture:** 全部新能力都走已验证的两个既有模式：**MCP 驱动**（drv_npu/drv_audio 先例：独立子进程、惰性重导入、缺失优雅降级、能力表/风险账本/审计自动生效）与**内核内建 syscall**（msg.*/mem.* 先例）。屏幕层的 adb 交互全部收口在 `Adb` 传输类之后——测试用 FakeAdb + 真 uiautomator XML fixture，**无真机也能全测**；真机 runbook 单列。隐私与安全红线沿用：操控类 syscall 一律 reversible=False 消耗风险账本；`pkg:` 作用域把屏幕操控限制在白名单 App；录音/通知类均显式触发。

**Tech Stack:** laos 核心与驱动保持零第三方依赖（stdlib `xml.etree`/`subprocess`/`urllib`）；重依赖只存在于驱动子进程或外部服务（QAIRT Genie 二进制、Termux:API、App Kotlin）。构建：TimnetLpaiApp 走 `gradlew assembleDebug`（JDK `D:\Android\jdk17\jdk-17.0.12`）。

**Spec:** 本计划（五层设计）；前置调研 `docs/research/2026-09-09-qnn-real-os-integration.md`、`docs/research/2026-09-10-cherry-embed-learning.md`；真机操作 `docs/research/qnn-real-device-runbook.md`。

## Global Constraints（全部五部分适用）

- laos 核心与驱动零第三方依赖；重依赖只允许存在于驱动子进程/外部服务，且**惰性导入 + 缺失优雅降级**（drv_npu 模式：探测 → 可用则真实 → 缺席则 stub/ENOSYS 指引）。
- 不破坏执行时基线（以实测为准，当前 203 项全绿）；新增测试放 `tests/test_screen.py`、`tests/test_genie.py`、`tests/test_notify.py`、`tests/test_events.py`、`tests/test_skills.py`。
- 操控类 syscall（tap/swipe/text/back）一律 `reversible=False`（真实设备上的动作不可撤销）+ 消耗风险账本；`screen.dump`/`shot` 只读可逆。
- **pkg: 作用域**：`task_scope` 支持 `pkg:<package>` 前缀条目；内核在 `screen.tap/swipe/text` 派发前校验调用参数的 `pkg` 字段（或 dump 的前台包名）∈ 作用域，越界 → `EACCES: outside task scope`（与路径作用域同语义）。
- 隐私红线沿用：通知/录音/传感只在显式调用或显式开关后工作，全部写审计。
- Windows 宿主解释器：`/c/Users/yaoyue/AppData/Roaming/uv/python/cpython-3.12.14-windows-x86_64-none/python.exe`（记 `$PY`）；conda 重依赖环境：`C:/Users/yaoyue/miniconda3/python.exe`；音频 venv：`.venv-audio`。
- 每 task 一个 commit；每 Part 结束跑全量回归并推送。
- 测试策略总则：**协议与解析逻辑全部 fixture/mock 可测；只有真机硬件行为留给 runbook 手工验收**。

## 现状关键事实（执行者必读）

- adb：`C:/Users/yaoyue/AppData/Local/Android/Sdk/platform-tools/adb.exe`（当前无设备连接——Part 1 的测试不得依赖真机）。
- `uiautomator dump` 输出 XML：根节点 `<hierarchy>`，节点带 `text`/`class`/`bounds="[l,t][r,b]"`/`clickable`/`package`/`resource-id` 属性；`adb exec-out uiautomator dump /dev/tty` 可把 XML 打到 stdout。
- 前台包名：`adb shell dumpsys window | grep mCurrentFocus`（形如 `Window{... u0 com.pkg.name/...}`）。
- QAIRT Genie：Windows 二进制 `bin/x86_64-windows-msvc/genie-t2t-run.exe`（用法 `-c <config.json> --prompt <text>`）；头文件 `include/Genie/GenieDialog.h`；Android `lib/aarch64-android/libGenie.so`；examples/Genie 有配置样例。Genie 需要**已转换的 LLM 上下文二进制**（用户尚未下载任何模型包）。
- TimnetLpaiApp：已含 InferenceServer（127.0.0.1:8900，/health、/infer）；manifest 已有 INTERNET 权限；构建命令 `JAVA_HOME="D:\Android\jdk17\jdk-17.0.12" ./gradlew.bat assembleDebug`。
- 内建 syscall 模式：`kernel._builtin_specs`/`_builtin_impls`（msg.*、mem.* 先例）；风险账本：`kernel.risk`，闸门在 `syscall()` 内 `cost = max(1, spec.irreversibility_cost)`。
- laosweb：`build_state(kernel)` + `Handler`（GET /, /api/state；POST /api/confirm|restart|kill|msg|recv|diary）+ `PAGE`（固定 id 面板，tick() 每秒）。
- 测试基线：203 项全绿（skipped=3）。

---

# Part 1：drv_screen —— 屏幕理解与操控（第 1 层）

**价值**：智能手机 Agent 的本质能力（看屏幕 + 动手）。adb 通道免 root、免 App 改动、当前即可开发测试（FakeAdb）。

### Task 1.1: Adb 传输类 + uiautomator XML 解析器

**Files:**
- Create: `drivers/screen_adb.py`（Adb 传输 + 解析纯函数，供 drv_screen import）
- Test: `tests/test_screen.py`（新建，含 fixture）

**Interfaces:**
- `class Adb:` —— adb 交互的唯一收口（测试用 FakeAdb 替换）：
  - `__init__(adb_path: str | None = None, serial: str | None = None)`：adb_path 默认 env `LAOS_ADB` → 常见安装路径探测 → `"adb"`；serial 来自 `LAOS_ADB_SERIAL`
  - `shell(args: list[str], timeout: float = 30) -> str`（`adb [-s serial] shell ...`，非零 rc 抛 `IOError(f"EIO: adb shell rc={rc}: {out}")`）
  - `exec_out(args: list[str], timeout: float = 30) -> bytes`（`adb exec-out ...`）
  - `devices() -> list[str]`（`adb devices` 解析，跳过表头与 `*` 行）
- `parse_uiautomator_xml(xml_text: str) -> dict`（模块级纯函数）：`xml.etree.ElementTree` 解析 `<hierarchy>`；递归收集节点为 `{"text", "cls", "package", "resource_id", "clickable", "bounds": [l, t, r, b]}`（bounds 从 `"[l,t][r,b]"` 解析为 int 四元组）；返回 `{"package": 根package, "nodes": [...]}`；空/非法 XML → `ValueError("EINVAL: bad uiautomator dump")`
- `parse_current_focus(dumpsys_out: str) -> str | None`：从 `dumpsys window` 输出提取 `mCurrentFocus` 里的包名（正则 `u0 ([\w.]+)/`）；无 → None

- [ ] **Step 1: 写失败测试**（tests/test_screen.py）：fixture 内嵌一段真实形状的 uiautomator XML（2 层节点：根 package="com.timnet.lpai"，含 1 个可点击节点 text="Start Recording"、1 个文本节点）→ 断言 parse 结果逐字段正确；非法 XML → ValueError；`parse_current_focus` 用三行样例输出断言包名提取；`Adb.devices()` 用 FakeAdb 断言解析（表头跳过）。
- [ ] **Step 2: 确认失败 → Step 3: 实现 → Step 4: 全量回归（基线 203 + ~5）**
- [ ] **Step 5: Commit** — `feat(laos): adb transport + uiautomator parser (screen layer foundation)`

### Task 1.2: drv_screen 驱动 + pkg 作用域

**Files:**
- Create: `drivers/drv_screen.py`
- Modify: `laos/kernel.py`（screen.* 的 pkg 作用域闸门：`task_scope` 含 `pkg:` 条目时，screen.tap/swipe/text 的 `pkg` 参数必须匹配某条 scope 去掉 `pkg:` 前缀后的值，否则 EACCES；实现为闸门链里 task_scope 检查的扩展——仅当 tool 以 `screen.` 开头且 args 含 `pkg`）
- Modify: `bin/laosd.py`（boot 加载 drv_screen；ops caps 增 `screen.*`）
- Test: `tests/test_screen.py`（追加）

**Interfaces:**
- `drv = MCPServer("drv_screen", version="0.1.0")`；`Adb` 实例模块级创建（env 可覆盖）。
- `screen.dump()` → `{"current_package": ..., "nodes": [...]}`（内部：`exec_out uiautomator dump /dev/tty` → parse；再 `shell dumpsys window` → current_focus）——只读，reversible=True
- `screen.tap(x: int, y: int, pkg: str)` / `screen.swipe(x1,y1,x2,y2,ms=300,pkg)` / `screen.text(text: str, pkg: str)` / `screen.back(pkg: str)`：`reversible=False, risk="medium", irreversibility_cost=1`；实现 = `shell input tap/swipe/text/input keyevent 4`；全部走内核 pkg 作用域闸门（kernel 校验 args.pkg ∈ task_scope 的 pkg: 条目）
- `screen.shot() -> str`：`exec_out screencap -p` → 写 `var/screen/shot-<ts>.png`，返回路径（只读）
- 驱动内 pkg 二次校验：tap/swipe/text 执行前 `dump` 一次取 `current_package`，与 args["pkg"] 不符 → `EACCES: foreground package mismatch`（纵深防御第二层，防内核与设备状态漂移）

- [ ] **Step 1: 写失败测试**：FakeAdb 注入（drv_screen 允许 `set_adb(adb)` 测试注入点）——tap 成功路径（FakeAdb 伪造 focus+dump）、foreground mismatch → EACCES、kernel pkg 作用域越界 → EACCES（spawn 带 `task_scope=["pkg:com.allowed"]`，调 screen.tap pkg="com.denied"）、back/text 参数校验
- [ ] **Step 2: 确认失败 → Step 3: 实现（含 kernel 闸门扩展）→ Step 4: 全量回归（基线 + ~6）**
- [ ] **Step 5: Commit** — `feat(laos): drv_screen (adb-backed screen understanding and control, pkg-scoped)`

### Task 1.3: 真机 runbook + 面板提示 + 文档

**Files:**
- Modify: `docs/research/qnn-real-device-runbook.md`（追加屏幕层章节：设备连接、LAOS_ADB/SERIAL、示例——dump TimnetLpaiApp 界面并点 Start Recording）、`README.md`（驱动清单 + 测试数）、`docs/guide-panel.md`（pkg 作用域用法）

- [ ] **Step 1: runbook + docs → Step 2: 全量回归 → Step 3: Commit** — `docs(laos): screen layer runbook and docs`

---

# Part 2：drv_genie —— 端侧 LLM 大脑（第 2 层）

**价值**：Agent 大脑离线化/私有化。双后端：QAIRT Genie（真机 HTP/桌面 exe，需用户下载模型包）+ OpenAI 兼容端点（ollama/llama.cpp/vLLM，桌面立即可用）。

### Task 2.1: drv_genie 驱动（双后端 + 探测）

**Files:**
- Create: `drivers/drv_genie.py`
- Test: `tests/test_genie.py`（新建）

**Interfaces:**
- 后端选择 `LAOS_LLM_BACKEND = auto|genie|openai`（默认 auto：genie 探测通过则 genie，否则 openai 可达则 openai，否则都不可用）：
  - genie 探测：`LAOS_GENIE_BIN`（或 QAIRT_ROOT/bin/x86_64-windows-msvc）下 `genie-t2t-run.exe` 存在 且 `LAOS_GENIE_CONFIG` 指向的 config json 存在
  - openai 探测：`LAOS_LLM_BASE_URL`（默认 `http://127.0.0.1:11434/v1`，即 ollama）`GET /models` 200
- `llm.chat(prompt: str, system?: str, max_tokens?: int = 512)` → `{"text", "backend", "latency_ms"}`
  - genie：subprocess `genie-t2t-run.exe -c <config> --prompt <prompt>`（system 并入 prompt 前缀；timeout `LAOS_LLM_TIMEOUT` 默认 120s）
  - openai：stdlib urllib `POST {base}/chat/completions {"model": LAOS_LLM_MODEL 默认 "local-model", "messages": [...], "max_tokens"}` → choices[0].message.content
  - 两后端都不可用 → `EIO: no llm backend available (genie: <原因>; openai: <原因>)`
- `llm.status` → 后端探测报告（drv_npu.devices 同款格式）
- 标注：`reversible=True`（纯计算可重跑，区别于 NPU 功耗定价）

- [ ] **Step 1: 写失败测试**：genie 后端 mock subprocess（FakeAdb 风格——`set_runner(callable)` 注入，断言命令行参数含 config 与 prompt）；openai 后端 mock HTTP（返回 OpenAI 形状 JSON）→ chat 断言 text/backend/latency；双后端缺失 → EIO 且消息含两个原因；status 报告
- [ ] **Step 2: 确认失败 → Step 3: 实现 → Step 4: 全量回归（基线 + ~6）**
- [ ] **Step 5: Commit** — `feat(laos): drv_genie dual-backend LLM driver (QAIRT Genie / OpenAI-compatible)`

### Task 2.2: 文档 + （可选）Genie 真模型指引

**Files:**
- Modify: `docs/research/qnn-real-device-runbook.md`（Genie 章节：模型获取——QAIRT Model CoLB 或 HuggingFace 的 QNN context binary 下载、config.json 形状——引用 examples/Genie 配置、Android 侧 libGenie.so 部署）、`README.md`（驱动清单 + 测试数）

- [ ] **Step 1: 文档 → Step 2: 回归 → Step 3: Commit** — `docs(laos): genie backend runbook (model bundle + config)`

---

# Part 3：通知、通信与动态功耗定价（第 3 层）

**价值**：Agent 的耳朵（通知/短信）与嘴（TTS/回复），并把"功耗预算"变成电池真值。

### Task 3.1: 动态功耗定价（内核钩子 + 电池输入）

**Files:**
- Modify: `laos/kernel.py`（`FleetLedger.charge` 的 cost 计算改为 `max(1, round(base_cost * self.multiplier))`；`multiplier: float = 1.0` 属性 + `kernel.set_pricing_multiplier(m)` 写审计 `event:"pricing"`）
- Create: `drivers/drv_battery.py`（`battery.status` → 传输二选一：Termux `termux-battery-status`（subprocess JSON）或 App `/battery`（HTTP）；返回 `{"percent", "charging"}`；laosweb tick 或专用轻循环在 percent<20 && !charging 时 `kernel.set_pricing_multiplier(3.0)`，恢复正常回 1.0）
- Test: `tests/test_battery.py`（定价乘数内核测试 + 驱动 JSON 解析测试）

- [ ] **Step 1: 失败测试**（低电量 → mem.remember 类的不可逆调用 cost×3；恢复后回 1）→ **Step 2: 实现** → **Step 3: 回归（+~4）**
- [ ] **Step 4: Commit** — `feat(laos): dynamic power pricing (battery-aware risk multiplier)`

### Task 3.2: drv_notify + drv_comms（通知/短信/TTS）

**Files:**
- Create: `drivers/drv_notify.py`、`drivers/drv_comms.py`
- Modify: `bin/laosd.py`（按传输可用性加载）、`README.md`
- Test: `tests/test_notify.py`

**Interfaces:**
- `drv_notify.py`：`notify.list(since?)` → 传输二选一（`LAOS_NOTIFY_TRANSPORT = app|termux`）：
  - app：GET `{LAOS_PHONE_ENDPOINT http://127.0.0.1:8900}/notifications` → JSON 数组（**需要 Part 4 的 App 端点**——本 task 先实现传输与解析，App 端点在 Part 4 落地，测试用 mock）
  - termux：`termux-notification-list`（subprocess JSON）
- `drv_comms.py`：`comms.sms_list` / `comms.sms_send(to, text)` / `comms.tts_speak(text)`（传输 termux：`termux-sms-list`/`termux-sms-send -n <to>`/`termux-tts-speak`，subprocess；全部 `reversible=False`——发短信不可撤回，`risk="medium"`）
- **隐私**：sms/通知是敏感数据——文档明示 caps 要求（`comms.*`/`notify.*` 仅授给可信 agent），审计自然覆盖

- [ ] **Step 1: 失败测试**（termux 传输用 fake subprocess 注入断言命令行；app 传输 mock HTTP；sms_send 断言 reversible=False 在 spec 里）
- [ ] **Step 2: 实现 → Step 3: 回归（+~5）**
- [ ] **Step 4: Commit** — `feat(laos): drv_notify + drv_comms (notifications, sms, tts; termux/app transports)`

---

# Part 4：全天候感知 —— App 事件流 + drv_events（第 4 层）

**价值**：把手机变成 laos 的常驻感官（情感变化、说话段、电量），事件驱动 Agent 行为。**本 Part 涉及真机 Kotlin 改动与实机验证，安排在 Part 1-3 稳定后执行。**

### Task 4.1: App 侧事件服务（Kotlin）

**Files:**
- Modify: TimnetLpaiApp `InferenceServer.kt`（新增 `GET /events?since=<ts>` → 情感变化事件数组 + `POST /events/clear`；内部：classifier 每次推理结果与上次不同即记事件（环形缓冲 100 条）；另加 `GET /battery` → BatteryManager 读数）
- Modify: `MainActivity.kt`（若实现前台 Service 常驻录音则单列；本 task 维持手动触发粒度）

- [ ] **Step 1: Kotlin 实现 → Step 2: `gradlew assembleDebug` 构建通过 → Step 3: 无设备边界——真机验证项写入 runbook**
- [ ] **Step 4: Commit（QNN 工作区，非 git 则记录变更清单）**

### Task 4.2: laos `drv_events` + 记忆集成

**Files:**
- Create: `drivers/drv_events.py`
- Modify: `bin/laosd.py`（加载；laosweb build_state 增 events 摘要）
- Test: `tests/test_events.py`

**Interfaces:**
- `events.since(since_ts: float = 0)` → GET `{LAOS_NPU_ENDPOINT}/events?since=` → 事件数组；`events.watch` → 轮询一次并把新事件 `mem.remember(kind="sensor", ...)` 入库（情感变化 → 记忆 → 日记素材）
- 测试：mock App 端点（事件 JSON）→ since 增量、入库断言

- [ ] **Step 1: 失败测试 → Step 2: 实现 → Step 3: 回归（+~4）**
- [ ] **Step 4: Commit** — `feat(laos): drv_events (on-device sensing into memory)`

---

# Part 5：越用越聪明 —— 技能库（第 5 层）

**价值**：成功任务序列沉淀为可复用技能，新任务先查历史——"越用越聪明"的机制化。

### Task 5.1: laos/skills.py 技能库

**Files:**
- Create: `laos/skills.py`
- Test: `tests/test_skills.py`（新建）

**Interfaces:**
- `SkillStore(memory: MemoryStore)`——技能**存储复用 MemoryStore**（kind="skill"），本模块只做提取与匹配：
  - `digest_trace(trace: list[dict]) -> str`：工具调用序列签名（`tool1→tool2→tool3`，参数抽象为工具名+首个参数键集）
  - `learn_from_result(result, memory_store) -> dict | None`：AgentResult `ok=True && denied==0 && syscalls>=2` 时，提取 `{signature, task_fingerprint(bigram), description=result.answer 前 100 字, sequence}` → `memory_store.remember(kind="skill", text=description, tags=[signature])`；否则 None
  - `match(query: str, memory_store, k=3) -> list`：`memory_store.recall` 过滤 kind=="skill"
- 内核/Agent 集成：`laos/agent.py` `Agent.run` 成功结束（result.ok）后调 `skills.learn_from_result`（惰性导入，失败不响）；`run` 开始时 `match(task)` 的 top 技能描述注入上下文（user 角色 `[skill-hint]` 前缀，仿 kernel-notice 先例）

- [ ] **Step 1: 失败测试**（digest 确定性、learn 门控（denied>0 → None）、match 检索、agent 集成 hint 注入——用 ScriptedBrain + 成功 run 断言第二次 run 的上下文含 skill-hint）
- [ ] **Step 2: 实现 → Step 3: 回归（+~5）**
- [ ] **Step 4: Commit** — `feat(laos): skill library (successful task traces become reusable skills)`

### Task 5.2: 文档收尾

- [ ] README（技能库 + 五层能力表）、guide-panel、learning notes 标注落地 → Commit — `docs(laos): five-layer smartphone agent capability map`

---

# 交付顺序与依赖

```
Part 1（屏幕）──┐
Part 2（LLM）──┼── 互不依赖，可任意顺序；Part 3.1 的定价钩子独立
Part 3（通知/通信/电池）┘
Part 4（全天候）── 依赖 Part 3 的 App 端点先例；需真机验证
Part 5（技能库）── 依赖 Part 1（屏幕序列最有价值）但机制上只依赖 AgentResult，可先行
```

**建议执行顺序**：Part 5 → Part 1 → Part 2 → Part 3 → Part 4（技能库最独立；屏幕价值最大；全天候压轴需真机）。

## 全局验收清单（每 Part 完成后核对）

- [ ] 全量测试全绿（203 起步，每 Part +N，实测为准）
- [ ] 既有测试零改动（新面板类 UI 测试的必要调整除外，需在报告披露）
- [ ] 隐私/安全红线：操控与通信类 syscall 全部 reversible=False + 风险计费 + pkg/显式触发限制
- [ ] 真机相关部分附 runbook（连接、转发、验证命令）
