# Mobile MCP（mobile-next/mobile-mcp）评估 —— 对 laos 的帮助

> 日期：2026-09-29 ｜ 类型：开源项目评估（微信文章引入）｜ 对照基线：laos v0.7.0（HEAD 66ac984）
> 来源：[微信文章](https://mp.weixin.qq.com/s/LnfBW8fjtUfO3pkslII23w) + [GitHub 仓库](https://github.com/mobile-next/mobile-mcp)

## §0 一句话结论

Mobile MCP 是一个**无治理的手机设备驱动**（30 个工具、零能力闸门、默认遥测上报），它 7k+★ 恰好验证了 laos "MCP Server = 设备驱动"命题的真实需求；对 laos 的最大帮助是三件事：**① laos 的 `kernel.load_driver()` 可以把它直接 insmod 成内核驱动（桥已存在）；② 它的 30 工具清单是 drv_screen 下一轮迭代的免费差距分析；③ 它"无闸门 + 默认遥测"的对照组姿态，正是 laos 差异化的活广告**。

## §1 项目名片

| 字段 | 值 |
|---|---|
| 仓库 | mobile-next/mobile-mcp |
| Star | 7k+（文章口径；抓取时 ~8.3k，716 fork） |
| 语言/许可 | TypeScript / Apache-2.0 |
| 定位 | 让 AI 通过 MCP 协议直接操控手机（Android + iOS，真机 + 模拟器） |
| 依赖 | 无 Appium / 无 WebDriverAgent / 无 XCUITest / 无 Espresso；只要 Node 20+ + Android Platform Tools（adb）/ Xcode CLT |
| 传输 | stdio 默认；`--listen` 起 Streamable HTTP（POST /mcp，无状态） |
| 遥测 | **默认开启**（PostHog + Scarf），`MOBILEMCP_DISABLE_TELEMETRY=1` 关闭 |
| 生态 | mobilecli（JSON-RPC 设备 CLI）、mobilewright（"手机版 Playwright"）、Mobile Next Cloud（租真机云池） |

## §2 功能全景（30 工具，按域分组）

| 域 | 工具 | 说明 |
|---|---|---|
| 设备管理 | `mobile_list_available_devices` / `mobile_get_screen_size` / `mobile_get_orientation` / `mobile_set_orientation` / `mobile_set_location` / `mobile_clipboard` | 列设备、尺寸、横竖屏、**虚拟 GPS**、**剪贴板读写** |
| 云真机 | `mobile_login_to_cloud_provider` / `mobile_list_remote_devices` / `mobile_allocate_remote_device` / `mobile_release_remote_device` | 外部付费云设备池租还 |
| 应用管理 | `mobile_list_apps` / `mobile_get_foreground_app` / `mobile_launch_app` / `mobile_terminate_app` / `mobile_install_app` / `mobile_uninstall_app` | 列/启/停/**装卸 App** |
| 屏幕交互 | `mobile_take_screenshot` / `mobile_save_screenshot` / `mobile_list_elements_on_screen` / `mobile_click_on_screen_at_coordinates` / `mobile_double_tap_on_screen` / `mobile_long_press_on_screen_at_coordinates` / `mobile_swipe_on_screen` / `mobile_start_screen_recording` / `mobile_stop_screen_recording` | 截屏/**录屏**/点/双击/长按/滑 |
| 输入导航 | `mobile_type_keys` / `mobile_press_button` / `mobile_open_url` | 打字 / HOME·BACK·VOLUME·ENTER / 开 URL |
| 日志批处理 | `mobile_get_device_logs` / `mobile_list_crashes` / `mobile_get_crash` / `mobile_batch_commands` | logcat/统一日志、崩溃报告、**一次调用串多条工具** |

**核心设计决策：无障碍树优先（accessibility-first）**——优先走原生无障碍树驱动 App，避免视觉模型和图像 token，仅在必要时回退截屏+坐标。与 laos `screen.dump` 解析 uiautomator XML 的选择完全同源。

## §3 与 laos 现有实现逐项对照

laos 手机侧现有 15 个工具（五层）：`screen.dump/tap/swipe/text/back/shot` + `notify.list` + `comms.sms_list/sms_send/tts_speak` + `battery.status` + `events.since/status`。

| Mobile MCP 能力 | laos 现状 | 差距判定 |
|---|---|---|
| 无障碍树列元素 | `screen.dump`（uiautomator XML 解析） | **平手**——设计同源，laos 还多一层 pkg 白名单闸 |
| 点按/滑动/输入/返回 | `screen.tap/swipe/text/back` | 平手（laos 每 op 校验前台包名） |
| 截屏 | `screen.shot` | 平手 |
| 双击/长按 | ✗ | **缺口**（`input swipe` 同点 600ms 即长按，两行代码） |
| HOME/VOLUME/ENTER 等按键 | 仅 `screen.back` | **缺口**（`input keyevent`，一行） |
| 列已装 App / 启动 / 停止 | ✗（未暴露为工具；`Adb.devices()` 仅内部） | **缺口**（`pm list packages` / `am start` / `am force-stop`，天然适配 pkg: 闸门） |
| 装/卸 App | ✗ | 缺口，但**高危**（不可逆）——须 FleetLedger 计价 + 确认横幅 |
| 录屏 | ✗ | **缺口**（`screenrecord`；对 laos 真机验收直接有用） |
| 剪贴板读写 | ✗ | **敏感**（个人手机剪贴板=密码/验证码载体） |
| 虚拟 GPS | ✗ | 与 laos 合规红线冲突（考勤/摇一摇作弊面） |
| logcat / 崩溃报告 | ✗（drv_events 拉的是自建 App /events 端点，非 logcat） | 缺口（诊断价值；logcat 需按 pkg 过滤防跨应用泄漏） |
| 批量命令 | ✗ | **哲学对立**：laos 每次 syscall 独立过闸+审计，批处理会绕开预算与审计粒度 |
| iOS 支持 | ✗（仅 Android/adb） | 远期方向（需 Xcode 环境，本项目无 Mac） |
| 云真机池 | ✗ | 外部付费服务，与 laos 本地优先相悖 |
| 多设备枚举 | `Adb.devices()` 内部有、未暴露 | 小缺口（可暴露 `screen.devices`） |

## §4 架构启示（4 条）

1. **"MCP Server = 设备驱动"命题被市场验证**。7k+★ 说明"AI 直接操控手机"是真实刚需，而它只是一个裸驱动。laos 的定位顺势清晰：**做这类驱动的内核**——任何 mobile-mcp 式服务器都应该是 laos 的一个 insmod 对象，而不是独立给 Agent 直连。
2. **laos 的驱动桥已经存在**：`kernel.load_driver(name, argv, env)`（laos/kernel.py:281）以子进程拉起任意 MCP Server、经 sandbox 包装、cgroup 限流、工具自动注册进 syscall_table、`driver_load` 落审计。**mobile-mcp 可以零改码挂载**：
   ```python
   kernel.load_driver(
       "mobile",
       ["npx", "mobile-mcp@latest"],
       env={"MOBILEMCP_DISABLE_TELEMETRY": "1"},   # 遥测必须关：PostHog/Scaf 默认回传
   )
   ```
   挂载后其 30 工具即成为 laos syscall，受能力表/task_scope/EDQUOT/FleetLedger/审计管辖。
3. **诚实边界：外挂驱动的闸门粒度降级**。laos 自研 `drv_screen` 的 pkg 校验在**驱动内部**逐 op 检查前台包名；外挂 mobile-mcp 时闸门只能到"工具名+参数 schema"层（它参数叫 `app_id` 而非 `pkg`，laos 的 `pkg:` scope 语义不迁移）。**结论：快速获得能力 → 外挂；长期治理 → 自研驱动逐个吸收**，两路并存。
4. **无障碍树优先的选型被同行验证**：mobile-mcp 明确"避免视觉模型与图像 token"，与 laos `screen.dump` 结构化优先同源——laos 在 v0.5.0 已押对方向。

## §5 采纳决策表

状态：●已落地 ｜ ◐推荐（下轮迭代） ｜ ○不做（记录理由）

| # | 采纳项 | 落点 | 状态 |
|---|---|---|---|
| 1 | load_driver 外挂路径写入手机能力文档（mobile-mcp 作首个"外挂驱动"示例，遥测必关） | README §七 + drivers/ 文档 | ◐ |
| 2 | `screen.key`（HOME/VOLUME_UP/VOLUME_DOWN/ENTER，`input keyevent`） | drv_screen.py + FakeAdb 用例 | ◐ |
| 3 | `screen.longpress` / `screen.doubletap`（同点 swipe 600ms / 连续两 tap） | drv_screen.py + FakeAdb 用例 | ◐ |
| 4 | `apps.list` / `apps.launch` / `apps.close`（`pm list packages` / `am start` / `am force-stop`，全部走 pkg: 白名单） | 新 drivers/drv_apps.py 或并入 drv_screen | ◐ |
| 5 | `screen.record_start/record_stop`（`screenrecord`，时长上限 + 审计 `event:"screen"` + 仅显式 syscall 触发，对齐录音红线） | drv_screen.py | ◐ |
| 6 | `screen.devices`（暴露现有 `Adb.devices()`，只读） | drv_screen.py | ◐ |
| 7 | `apps.install` / `apps.uninstall`（不可逆 → FleetLedger 高计价 + 确认横幅） | 新驱动 + kernel 风险表 | ◐（低优先，风险设计先行） |
| 8 | logcat/崩溃报告（**按 pkg 过滤** `logcat --pid`，防跨应用泄漏） | drv_events.py 扩展 | ◐（低优先） |
| 9 | 剪贴板读 | deny-by-default + Jev 预审 + 内容永不入 mem.*（密码/验证码载体） | ○（除非显式开闸，默认不做） |
| 10 | 虚拟 GPS（`mobile_set_location` 同类） | 与 laos 合规红线冲突（作弊面），不做 | ○ |
| 11 | `mobile_batch_commands` 同类批处理 | 与 laos"每 syscall 独立过闸+审计+预算"哲学对立；laos 答案是 sys.delegate/技能编排，不是裸批 | ○ |
| 12 | 云真机池 4 工具 | 外部付费服务、远端流屏，与本地优先相悖 | ○ |
| 13 | iOS 支持 | 无 Mac/Xcode 环境，记为远期方向 | ○（远期） |

## §6 红线对照（laos 合规红线在它身上全部失守）

| laos 红线 | mobile-mcp 现状 |
|---|---|
| 每次操控审计落账 | 无审计概念，仅 stdout 日志 |
| 能力最小化/白名单 | 30 工具全量暴露，装卸 App 一视同仁 |
| 隐私外发默认禁止 | **PostHog + Scarf 遥测默认开**（须 `MOBILEMCP_DISABLE_TELEMETRY=1`） |
| 不可逆操作计价+确认 | `uninstall` 无任何确认 |
| 敏感数据（剪贴板/通知）可信闸 | 剪贴板可直接读写 |

这正是 laos 差异化的对照组：**同样的设备能力，laos 给它装上 syscall 闸门链**。

## §7 复现与诚实清单

- 信息源：微信文章 + GitHub README 抓取（2026-09-29）；**未克隆源码逐文件审读、未真机集成实测**——工具清单与行为以 README 自述为准，遥测开关变量名来自其文档。
- Star 数两处口径：文章 7k+ / 抓取时 ~8.3k，取"7k+"保守表述。
- §5 全部 ◐ 项均**未实现**，属下轮迭代候选；实现前应先跑 §4-3 所述外挂 PoC 验证桥路（npx 可用性、Windows 下 stdio 编码）。
- 与 capstone（2026-09-19-laos-adoption-capstone.md）关系：本文是手机子域的单项深评，总纲视角下 mobile-mcp 计入"OSS 普查"域的新增对照项。
