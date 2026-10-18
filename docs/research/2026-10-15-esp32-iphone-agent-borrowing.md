# 2026-10-15 esp32-iphone-agent 借鉴清单

> **来源与诚实声明**：本文全部结论来自对本地私有仓库 esp32-iphone-agent（`C:/Users/yaoyue/Downloads/esp32-iphone-agent`）33 个源文件的逐行通读，外加一次无硬件端到端模拟实证（伪造 TCP 板子 + PIL 合成帧 + 脚本化 LLM 驱动真实 Agent 主循环，跑通 plan → precise tap → 闭环纠偏 → type → done，含 `changed=True` 检出与温度 0→0.4 重试）。**非公开文献，无二手转述**；所有 esp32 侧锚点对源码复核，所有 laos 侧锚点对 v0.38.0 工作树复核。厂商数字/宣称值不适用（本项目无外部宣称）。

## 一句话定位

esp32-iphone-agent 是「让视觉大模型真正动手操作 iPhone」的最小闭环：AirPlay 镜像（眼）+ ESP32-S3 USB HID 桥（手，板子零逻辑）+ planner/actor 双模型（脑）+ 服务端指针跟踪与动作后验证（闭环）。它对 laos 的核心价值一句话：**它用一整套工程回答了「动作之后怎么知道世界变了」，而这正是 laos `screen.*` syscall 面缺失的一课。**

## 两个项目定位对照

| 维度 | esp32-iphone-agent | laos |
|---|---|---|
| 感知 | AirPlay 镜像 → 8fps JPEG 帧（`screen.py`） | `screen.dump` 控件树 + `screen.shot`（adb） |
| 执行 | ESP32-S3 HID 伪装鼠标键盘（行命令协议） | `screen.tap/swipe/text/key…`（`adb shell input`） |
| 决策 | planner ≤6 步 + actor 单步（THINK/DO 行协议） | Brain（Scripted/OpenAI）+ judge/decide 三判型 |
| 治理 | 服务端指针跟踪、温度阶梯、重复检测 | 能力表 / task_scope / Sentinel / 风险账本 / 审计 |
| 约束 | 电脑需 macOS/Linux + iPhone + ESP32 | 核心纯 stdlib；Linux 真隔离，macOS/Windows 降级 |

可比性本质：两者都是「感知 → 决策 → 执行」三层解构，且**执行器都是不可靠的外部设备**。esp32 面对 HID 相对指针漂移 + 零反馈通道；laos 面对 adb 指令「发了不等于生效」。

## 核心判断：闭环验证落差（价值最高的单点）

laos `drivers/drv_screen.py:84-88`：`screen.tap` 执行 `adb shell input tap` 后返回 `"OK tapped (x,y) in pkg"`——**只证明命令已发出，不证明屏幕已响应**。弹窗遮挡、坐标被软键盘顶离、前台漂移、点击落在不可响应区域，Agent 都会拿到虚假 OK 继续决策，错误沿任务链放大。laos 已有动作*前*校验（`_require_pkg` 前台包名比对，`drv_screen.py:56-62`），唯独缺动作*后*校验。

esp32 的对应物是 `vision.py:12 changed(before, after, ignore, threshold)`：32×64 粗 pass + 半分辨率细 pass 的双阈值纯 PIL 差分（指针移动区域掩帽不计变化），每个 DO 动作后调用，`changed=True/False` 连同变化区域回喂 actor。已在无硬件模拟中实证：tap → changed=True（按钮消失）、type → changed=True（键盘弹出）。

## 借鉴清单详表（9 项）

裁决码沿用本仓库口径：●已落地 / ◐待落地（附优先级）/ ○不做。

| # | 借鉴项 | esp32 源头锚点 | 要解决的问题 | laos 落点与形态 | 裁决 |
|---|---|---|---|---|---|
| 1 | 屏幕动作闭环验证 | `vision.py:12 changed()` 双阈值差分 + 结论回喂 | `screen.*` 返回值无效果证据（`drv_screen.py:84-88`） | **结构化差分优先**：操控前后各一次 uiautomator dump 做节点差集（复用 `_dump()`，`drv_screen.py:47`），返回 `changed + delta`，纯 stdlib 零新 tool；**像素差分兜底**：新 tool `screen.verify`，PIL 活在 `drivers/` 子进程（符合重依赖纪律），用于无控件树场景（游戏/自绘/WebView） | ◐P0（第二波） |
| 2 | 重复无效动作检测 + 解析失败容错阶梯 | `agent.py:240 _repeating(limit=3)`；升温 0→0.4→0.8；`agent.py:78/100` 解析失败走同一阶梯 | 见下节两个现存洞 | `brain.py` 解析失败转可重试 Thought + temperature 参数；`agent.py` 主循环温度阶梯 + 重复 syscall 检测器（同 tool+同参数第 3 次触发 `ctx.notice` 强制换策略，复用既有通知面） | ◐P0（**第一波，计划已写** `docs/superpowers/plans/2026-10-15-brain-reliability-repeat-guard.md`） |
| 3 | 传感器失效绝不盲操作 | `agent.py:122 BlindError`，无帧即停 | dump 失败后 Agent 可能拿过期控件树继续盲点（`screen_adb.py:78-80` 抛 EINVAL 后无拦截） | 把**已有的** STALE notice 机制（`agent.py:126-130` 的 `drain_notices`，HKU stale context 落地件）扩展到屏幕域：dump 失败/空 hierarchy → 内核发 notice；连续 3 次 → 强制 `finish(ok=False)` | ◐P0（与 #4 同子系统） |
| 4 | 动作后缓存失效纪律 | 每步 DO 后重新取帧（`screen.py:93 settled()/:100 fresh()`） | ctx 里 dump 结果无失效机制，tap 后不重dump 则后续 think 看旧树 | kernel 在 `screen.*` 操控成功后把该 pid 上下文里此前 dump 标记 stale，notice 提示重读 | ◐P1（与 #3 一并建设） |
| 5 | 只从"验证过的成功"学技能 | 校准样本只采自精确点按的瞄准→落点配对 | `agent.py:169-174` `learn_from_result` 只要 `result.ok` 就沉淀，「靠运气绕开失败」的序列会进 `[skill-hint]` 自我复制 | `SkillStore.learn_from_result` 增加证据门槛：trace 中 screen 操控 verify 证据全 `changed=True`（或无 screen 动作）才沉淀；含 `changed=False` 降级进 memory 作反面案例 | ◐P1 |
| 6 | 审计流记录"世界反应" | 每步 changed 结论进 trace | `kernel.py:652` `audit.write` 只记「发了什么命令」，不记「世界怎么反应」，`laosctl` 回放看不到命令-效果配对 | 审计行返回体附加 `changed / delta_summary` 字段，纯 payload 扩展 | ◐P1 |
| 7 | 驱动健康度 | 断线立即松开所有按键；8s 看门狗；USB 休眠 remote wakeup 否则秒回 `err phone usb asleep` | `screen_adb.py:40` 30s 裸超时；adb server 死亡/设备离线时 errno 语义模糊，in-flight 无快速失败 | drv_screen 增加 health 面（连续失败计数 → unhealthy + 探活）；kernel 对 unhealthy 驱动 in-flight 快速失败 `EIO` 并允许一次自动重连；「device offline」等映射明确 errno | ◐P2 |
| 8 | 验证器本身的概率校准 | calibration 越用越准 + 落盘 `~/.hidagent/calibration.json` | `calib.py` 的 `brier_score/ece` 目前只有手算锚点测试，**没有真实证据流消费它**——校准台建好了没有待校仪器 | 把 #1 的 verify 信号与任务最终成败（`result.ok`）对齐构成 (prob, outcome) 对，喂 brier/ece 回答「laos 的验证信号本身准不准」；两套验证器（结构化/像素）横向比校准质量定阈值。**校准的不是坐标（adb 绝对坐标无漂移），是验证器的概率** | ◐P2 |
| 9 | 无硬件测试基建增量 | PIL 合成帧 / 内存 TCP 假板子 / MockTransport / TestClient 全循环 | laos 基建更全（FakeAdb `tests/test_screen.py:22`、ScriptedBrain `brain.py:46`、1146 回归），**缺屏幕域闭环用例**——假屏树有了，「tap 之后世界怎么变」的剧本没有 | 合成 uiautomator XML 生成器（内置弹窗遮挡/软键盘顶位/前台漂移三类事故场景，放 `tests/data/`）+ 屏幕任务 SOP 脚本脑 + e2e 断言闭环证据进 trace/审计 | ◐P2 |

## laos 现存两个代码洞（#2 的直接依据）

1. **`laos/brain.py:211`**：`json.loads(c["function"]["arguments"] or "{}")`——LLM 返回的 tool_call arguments 不是合法 JSON 时 `JSONDecodeError` 从 `think()` 直接逃逸；`Agent.run`（`agent.py:112-179`）只在 `finally` 收尾，`result.ok=False`、trace 丢失、上下文无失败记录，**一次模型输出抖动报废整个任务**。esp32 同款位置（行协议解析）是升温重试而非崩溃。
2. **`laos/agent.py:124-159`**：主循环全部止损是 `max_steps=12` 硬截断。模型对同一失败动作连试 12 次不会被识别、不会换策略，token 预算被死循环烧穿——违背 laos 自己的预算纪律（EDQUOT 闸之前的浪费无从拦截）。esp32 `_repeating` 用二十行解决同一问题。

## 不适用项（诚实边界，○）

| esp32 机制 | 不适用的原因 |
|---|---|
| 两点坐标校准 + 最小二乘在线纠偏 | adb 绝对坐标无漂移，uiautomator bounds 精确到像素，无可校准的坐标误差源。唯一例外：#1 方案 B 的视觉兜底路径（无控件树时校准截图坐标→设备坐标映射） |
| 相对指针定期 home 归零 / 拖拽不归位 / 换链路先松键 | HID 相对指针特定问题，laos 无对应物；其精神（执行器状态不留残、异常路径先清理）转译为 #7 |
| AirPlay/UxPlay 镜像采集管道 | laos 的 `screencap` + 控件树是严格上位替代 |
| THINK/DO 行协议 | laos 用原生 function calling 更稳；只借其容错阶梯（#2），不借协议本身 |

⚠️ 以上「不适用」均以 laos 当前 Android/adb 执行面为前提。若未来接入无控件树执行面（游戏、车机、自绘终端），#1 方案 B + 坐标校准应整体升级为必选项。

## 互相印证（laos 已更强，无行动项）

- **执行前状态校验**：laos `_require_pkg` 每次操控前 dumpsys 校验前台（`drv_screen.py:56-62`）vs esp32 每 10 个手势 home 归零——laos 更严格。
- **薄执行器厚核心**：esp32 固件 156 行零逻辑 ↔ laos drivers 薄（drv_screen 209 行）/ `laos/` 厚（kernel 1210 行）——同一哲学的独立佐证。
- **无硬件测试**：假 TCP 板子 ↔ FakeAdb；合成帧 ↔ 合成 XML 可扩展——同款哲学且 laos 覆盖更全。

## 反向借鉴（esp32 ← laos）

1. 能力表 + task_scope 白名单 → esp32 板子命令面可加命令白名单，防提示注入拼出危险组合键。
2. 不可逆风险账本与定价 → esp32 给「可能拨号/发消息/删除」的手势定风险价。
3. 审计 + 回放（laosctl）→ esp32 手势日志升级为带 errno 语义的审计流。
4. branch / COW → esp32 探索性操作（进未知设置页）可先开分支、可回滚。
5. judge 三判型（`judge.py`/`decide.py`）→ esp32 的 verify 结论可接判断层决定「重试/换路/上报人类」。

## 落地顺序与计划链接

四波：**第一波 #2**（修现存洞，不依赖新机制）→ 第二波 #1 方案 A + #3 + #4（同一「屏幕观测新鲜度」子系统）→ 第三波 #5 + #6（消费证据流，闭环到「越用越聪明」入口）→ 第四波 #7/#8/#9（打磨项，#8 依赖前三波积累的真实证据）。

第一波实施计划：`docs/superpowers/plans/2026-10-15-brain-reliability-repeat-guard.md`（状态登记见 `docs/superpowers/plans/README.md`）。

## 落地纪律（AGENTS.md 继承）

- 核心零依赖：PIL 只能进 `drivers/` 子进程；结构化差分纯 stdlib。
- 新 tool（`screen.verify`）需在 `drivers/README.md` 模块地图登记 + kernel syscall 装配面注册。
- fail-loud：verify 失败不静默兜底。
- 测试口径：`python -m unittest discover -s tests` 实跑数写 README；新测试无真机可跑。
- 第一波遵守计划编写三查（spec 覆盖/占位符扫描/类型一致性）与乱序阅读禁令。
