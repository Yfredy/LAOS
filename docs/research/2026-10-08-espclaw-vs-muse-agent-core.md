# ESP-Claw vs Muse-Gad「Agent 本体能力对比」笔记复现与 laos 采纳裁决

- 日期：2026-10-08（笔记发布 2026-10-07 15:45Z，同日取件当晚开做）
- 笔记：小红书短链 xhslink.cn/o/6xEYdgz4xbt《Agent本体能力对比，ESP-Claw vs Muse-Gad Agent核心》
- 方法：XHS 既定流程——webReader 服务器侧取件（og:description + 9 图逐张 OCR）→ 双项目溯源 → 克隆读码 → 可复现部分实测 → laos 采纳裁决（取长补短）
- 状态：进行中（本文件随波次推进补全；数字一律实测/引用分列）

## 一、笔记内容抄录（图 1–5 OCR + description 拼合）

1. **核心论题**："Agent 核心就是：感知 - 思考 - 规划 - 工具执行 - 记忆 - 输出闭环"；本体五件事：①接收输入（文本/语音转文本、事件、传感器信号）②推理（大模型生成思考、目标、多步计划）③工具调用（解析模型输出执行外部动作，结果喂回模型）④记忆（后续推理可以读取）⑤循环（多轮迭代直到目标完成）。
2. **三容器论**："Muse Secure-VM 里的 Agent、OpenClaw-Gateway 里的 Agent、ESP-Claw本地MCU Agent，三者都实现了上面完整5步闭环，都是真正Agent。差别不在'是不是Agent'，差别在这个Agent实例被放在什么运行容器里跑，容器能提供多少资源与存活条件。"
3. Muse Agent = 本体 + 豪华容器（独立 Linux VM），容器带来附加（图截断处：附……）。
4. 绿色横幅："ESP-Claw本地MCU与Gateway模式实现完整Agent闭环，无需VM，硬件断电后仍可运行。"（本地模式适用于硬件断电后仍需运行的场景）
5. 拓展坞+底板：ESP-Claw 8GB 内存 + 128GB 存储，对比 Muse-Gad Agent核心（4GB/64GB）"2倍内存/存储"。
6. "RESTful API 变复杂：当 Agent 数量超过 16 个时，RESTful 管理界面会变卡。>16 个 Agent 时建议用 MCP 协议管理。16 是门槛：Muse-Gad 的 RESTful 管理能力上限约 16 Agent。"
7. 评论区："esp-claw 很像 JoyAgent-B，JoyAgent-B 的起售價是 2600 元，就连机器狗的四足版本都做出来了，esp-claw 2600 以内的机会高，esp-claw 汇出了几个 mpu 的竞品。"
8. 标签：#howto入门codex #howto手搓skill #榨干软件howto #开发者选项 #颗粒度对齐

## 二、双项目溯源核实

| 笔记声称 | 溯源结果 | 判 |
|---|---|---|
| ESP-Claw = 本地 MCU 上跑完整 Agent 闭环的框架 | **真**：espressif/esp-claw（Apache-2.0，C/ESP-IDF）。官方定位 "Chat Coding「聊天造物」式 AI Agent 框架……在乐鑫芯片上本地完成感知、决策与执行的完整闭环"；主应用 application/edge_agent | ● |
| ESP-Claw "Gateway 模式" | README 无 "Gateway 模式"字样；生态确有 OpenClaw-Gateway（笔记图 3 引）；esp-claw README 致谢 "Inspired by the OpenClaw concept" | ◐ 转译 |
| Muse-Gad = "Agent核心（4GB/64GB）" + "Secure-VM 独立 Linux 容器" | **真（两体）**：facebookincubator/muse-gadget-sdk（Apache-2.0，2026-10-02 开源，ESP32 固件 + Linux SDK + skills 目录）；"Secure-VM" 对应 Meta Muse 每用户免费云电脑（Ubuntu，2 vCPU / 7.7GB RAM，root 运行，安全研究者已指出可利用面——Stark Insider / Security Boulevard 报道）。4GB/64GB 为笔记自加的硬件规格，官方仓库无此数 | ●/◐ |
| 三容器都实现完整闭环 "都是真正 Agent" | 架构判读成立（见 §四源码对照） | ●（判读） |
| "硬件断电后仍可运行"（MCU 本地模式） | MCU flash/深睡语义 vs VM 进程语义，方向成立；"断电后仍可运行"表述不精确（应为"掉电不丢配置、上电即恢复"） | ◐ |
| 8GB/128GB vs 4GB/64GB 拓展坞 | 无可验证来源（两官方仓库均无此配置页） | ○ 未证实 |
| RESTful >16 Agent 变卡、上限约 16，>16 用 MCP | 无可验证来源；Muse 管理面未见 "16" 文档 | ○ 未证实 |
| JoyAgent-B 2600 元起售、四足版本 | 未溯源（评论区补充，与两仓无关） | ○ 未溯源 |

（●已证实 ◐部分证实/转译 ○未证实——沿用 2026-10-07-cloudflare-clef.md 三档口径）

## 三、复现记录

**网络条件**（2026-10-07 深夜—10-08 凌晨，TUN 断窗+代理恢复期实测）：
github.com 主域克隆三连败（代理拒连→gitclone 镜像 502→代理流损坏 `invalid index-pack output`）；**api.github.com 直连可用**——trees API 取全仓路径+SHA，blobs API 配 git 凭据 token 批量取文件（token 不回显，仓库纪律）。此通道为本波次源码取件主径。

| 项 | 结果 |
|---|---|
| esp-claw 源码 | API 取件 45 文件（.agents/design.md、claw_core/event_router/memory/cap/manager 五模块头文件、edge_agent 与 mcp_server_point 主程序、docs/、lua_lvgl_web_sim README）+ 全树 1697 路径存档 var/repro/espclaw/tree.json |
| muse-gadget-sdk 源码 | API 取件 44 文件（linux/ 全树含 noise 协议栈与测试向量、skills 目录样本 3 份、esp32/README）+ 全树 586 路径存档 muse_tree.json |
| **muse Linux SDK 测试套件** | **双环境实跑**：Windows miniconda（依赖现成零安装：cryptography 42.0.5/websockets 17.0.1/pytest 9.1.1）**142 passed / 1 failed / 1 skipped**——唯一失败 `test_identity_persists` 是 Unix 0o600 权限断言，Windows `st_mode` 恒 0o666，环境差异非 bug；**WSL Ubuntu-22.04（SDK 真目标环境）全量 11 文件：167 passed / 1 skipped in 9.43s**（0o600 断言在 Linux 如预期通过，证明 Windows 侧失败确系环境差异） |
| esp-claw 固件构建/烧录 | **BLOCKED（诚实收档）**：需 ESP-IDF v5.5.x 工具链 + ESP32 硬件（S3/P4/C5）；本波次无板。复现深度=结构级：全树+核心源码逐行判读（§四） |
| Clef 顺带（clef_eval 同窗） | 权重 16/16 落盘；qemu chroot 加载实测 **19.4s**（760 张量）；qemu 单发决策在宿主内存压力下 c10 崩溃（forward_chroot.txt 证据）——qemu 本地实测止步于加载+GFLOPS 外推（arch_gate_evidence [4] 口径）；x86 WSL 原生 3 判型×20 次评测由 T3 harness 执行中（RTX4060 8GB 装不下 19GB bf16 → CPU bf16 16 线程，host 标注如实） |

## 四、架构对照与源码判读

esp-claw 四模块（claw_modules）+ 能力层（claw_capabilities 85 项 cap_*）+ 双应用（edge_agent 全功能/mcp_server_point 精简 MCP 装置）。逐模块对照 laos 既有资产：

| esp-claw 构件 | 源码要点（file:line） | laos 对应资产 | 关系 |
|---|---|---|---|
| claw_core.h agent 循环 | 8 相位枚举 IDLE→BEFORE/BOOTING_ITERATION_CONTEXT→BEFORE/IN_LLM_HTTP→AFTER_LLM_BEFORE_TOOL→RUNNING_TOOL→FINALIZING（claw_core.h:29-37）；`claw_core_get_agent_loop_phase()` 运行时可查；`USER_INTERRUPT` 请求位（:41）；`request_gate` 回调可拒请求（:90-93,147）；context provider 三类 SYSTEM_PROMPT/MESSAGES/TOOLS（:101-105） | v0.21.0 telemetry phase（dialog.turn queued/done）、wakegate barge_in、判断层 decide()、MemoryStore 注入 | 同构独立趋同 |
| claw_event_router.h 事件路由 | JSON 规则文件热载+CRUD（rules_path/reload/add_rule_json）；匹配六维 event_type/key/source_cap/channel/chat_id/content_type/text EXACT|PREFIX（:64-78）；**六动作 CALL_CAP/RUN_AGENT/RUN_SCRIPT/SEND_MESSAGE/EMIT_EVENT/DROP**（:55-62）；fail_open/consume_on_match/ack（:89-99） | 强制层+信箱 IPC | **事件防火墙**——laos 缺声明式规则面 |
| claw_memory.h 三层记忆 | 4 provider：profile/long_term/long_term_lightweight/session_history（:95-98）；条目 summary_ids[3]/tags/keywords/**access_count**/软删 deleted（:43-55）；forget/update 带 changed 检测；delete_session_history 会话 GC | MemoryStore+diary+journal | 趋同；access_count/轻量档可借鉴 |
| **claw_cap.h 能力框架** | caller 五级 SYSTEM/AGENT/CONSOLE/ROOT_AGENT/SUB_AGENT（:24-30）；**权限位 CALLABLE_BY_LLM/EMITS_EVENTS/RESTRICTED/ROOT_AGENT_ONLY**（:32-38）；状态机 REGISTERED→STARTED→DISABLED→DRAINING→UNLOADING（:40-46）；调用上下文带 agent 血统链 parent_agent_id/correlation_id（:48-63）；`set_llm_visible_groups`/`set_session_llm_visible_groups` per-session 可见域（:150-153）；root/sub agent 分工具表（:176-181） | **→ 本波次落地 laos/caps.py（§五）** | 采纳源 |
| edge_agent 双 FATFS | 只读 system 分区（种子：技能清单+内置 Lua/文档）+ 可写 storage 分区（运行时可重格式化再从 system 播种）——app_fs.c/main.c:334-337 | 不可变基线+审计轮转（AuditLog rotate 四件套） | 趋同；播种模式可借鉴 |
| mcp_server_point | 精简装置：仅 cap_lua+cap_mcp_server；MCP 工具 lua.run_script/run_script_async/list_jobs/get_job/stop_job/stop_all_jobs（异步作业模型）；无 HTTP 门户无 CLI | 驱动子进程模式（drv_*） | 最小暴露面范例 |
| LLM 供应链 | 云 API only（OpenAI/Anthropic 兼容+GPT-5.4/qwen3.6-plus/claude4.6-sonnet/deepseek-v4-pro 推荐）——**MCU 上无本地模型**，感知决策执行的"决策"仍在云端 | laos 判断层三路线（rules/edgejev/clef）含本地 | 差异点：闭环编排本地、推理云端 |

Muse 侧（facebookincubator/muse-gadget-sdk）：esp32/ 固件（components/muse、camera、noise_core、avatar 像素吉祥物）+ linux/ Python SDK（`musegadget`：pairing/link_client/**noise XX 协议栈自实现**/executor/service，BLE framing 带测试向量）+ skills/（**88 项 gadget 技能清单**，SKILL.md+CATALOG.md，覆盖 HomePod/Apple TV/打印机/Dyson/ESPHome 等）。README 原话："**Muse gets the same access to the machine as the account you install it for**"——全账号权限直授、无能力分级（与 esp-claw 的 RESTRICTED/ROOT_AGENT_ONLY 形成正面对照，也正是 laos 治理面的价值主张）。

## 五、laos 采纳裁决（取长补短）

| # | 采纳 | 裁决 | 状态 |
|---|---|---|---|
| 1 | **能力注册表 laos/caps.py**：caller 四级（SYSTEM/AGENT/CONSOLE/SUB_AGENT）/权限位四枚/状态机含 DRAINING 排空/per-session LLM 可见域/审计钩子 CalCap→telemetry 口径 | claw_cap 与"Agent 调工具=进程调 syscall"叙事完全同构，且 muse SDK 反证无分级的后果 → 立即落地 | ● **已落地 30c15f7（21 测试，全套 861 绿）**；实现时修一真 bug：execute 须在注册表锁外跑（否则全能力串行化+drain 死等） |
| 2 | 事件规则表（router_rules JSON 热载+DROP/fail_open/consume_on_match） | 对话管线装配波次的规则面：VAD/唤醒/打断的声明式路由 | ◐ P2 排队（对话管线装配） |
| 3 | phase 命名对齐（claw 8 相位 vs laos telemetry phase） | 埋点字典对照吸收，不硬搬枚举 | ◐ P3 排队（接线波） |
| 4 | 双分区播种（只读种子+可写区+运行时重建） | diary/AuditLog 跨代持久化设计参考 | ◐ P3 排队（接线波） |
| 5 | 叙事印证："三容器皆真 Agent，差别在容器" | 独立趋同=laos"基座是内核、Agent 是新负载"定位的反向印证，引用进对外叙事（不引号搬运，注明来源） | ● 引用 |
| 6 | esp-claw 固件本体 | 无板无工具链，BLOCKED 收档；后续购板再启（boards 目录+浏览器烧录已就绪的路径写明） | ○ 待硬件 |
| 7 | muse noise XX/BLE 协议栈 | 与 laos 语音线无交集；留作端侧配对调研引文 | ○ 不做 |

## 六、结论与登记

1. 笔记核心论题**成立**（源码级证实）：esp-claw MCU 闭环（claw_core 循环+claw_cap 工具+claw_memory 记忆+事件路由）与 Muse VM 容器均为完整五步 Agent；差别确在容器资源与存活条件。
2. 笔记数字声称：拓展坞 8GB/128GB vs 4GB/64GB、RESTful 16 Agent 上限——**均未证实**（§二 ○）；"Muse Secure-VM 独立 Linux 容器"证实（云 Ubuntu VM，媒体口径 2 vCPU/7.7GB root 运行）。
3. 复现深度：esp-claw=结构级（BLOCKED 构建烧录）；muse=测试套件双环境实跑。
4. 部署：laos/caps.py（能力治理面）落地；后续排队两项（事件规则表/phase 对齐）。
5. 登记：INDEX +1 行（2026-10-08，含 muse 双环境测试数与 caps 提交号）。

