# Muse Gadget SDK 学习报告 —— Meta 官方开源的端云治理链（源码级）

> 2026-10-08 · 学习对象：[facebookincubator/muse-gadget-sdk](https://github.com/facebookincubator/muse-gadget-sdk)（Apache-2.0，2026-10-02 开源；Muse 本体 2026-09-23 Meta Connect 发布）——用户指令"学习 muse 开源的内容"（XHS 笔记已 404，标题转译 ◐："Muse好大的野心！😮 这波AI弯道超车 10月2日发布的Mus…"）
> 方法：XHS 404 → 按预案直取仓库（var/repro/espclaw/src_muse，api.github.com trees+blobs 取件 586 路径）；Linux SDK 全量精读 + skills 目录补取（CATALOG+样本）；叙事链 TechCrunch/Verge 报道核对
> 姊妹篇：[espclaw-vs-muse-agent-core](2026-10-08-espclaw-vs-muse-agent-core.md)（架构对照+caps 落地）、[nanomuse](2026-10-08-nanomuse.md)（GPL 社区对照物）、[nanomuse-ui-xdevice-reference](2026-10-08-nanomuse-ui-xdevice-reference.md)（UI/端侧）

## 1. 一句话结论

**官方 Muse SDK 的核心不是"gadget"，是一条把 agent 放云、把能力放端、把凭据与执行分账户隔离的治理链**：租用 VM 里的 agent 经 Noise XX 加密链路 `link.invoke` 下发命令，设备端 executor 以**非特权 `run_as` 账户**执行（永不用持有设备凭据的服务账户）——这修正了姊妹篇"全账号权限直授、无能力分级"的粗糙表述（README 那句 "same access as the account" 指的是 run_as 账户）。对 laos 最值得拿走的三件：**技能五段式文档规范**（Identify/Prerequisites/Workflow/**Verify the Result**/**Limits**）、**输出预算的 JSON escape 感知收缩**、**file.write 分块+sha256+原子替换**——后两件与 laos 既有资产互证（cow.py 的 os.replace 同款）。

## 2. 全链架构（源码逐跳）

```
ESP32/RPi gadget ──BLE 配对──▶ Muse App（iOS/Android，Settings>Devices，
   │                            需 gadgets.muse.ai 的 SDK token + 开发者模式）
   ├── api.muse.ai /fetch_vms：设备令牌 → 租用 VM 清单（vm_ws_url+vm_auth_token）
   ├── /v1/noise：WebSocket + Noise XX 握手（端↔VM 端到端加密）
   ├── /link-control：长流，LE u32 长度前缀 JSON
   │     设备→VM：link.register（能力=COMMAND_SPECS 注册）+ link.result
   │     VM→设备：link.invoke（命令）+ link.unpaired 等事件
   └── /chat/stream：设备发起的对话通道
 executor：system.run / file.read / file.write / device.health 四命令，
   跑在 run_as 非特权账户（start_new_session+组击杀+96KiB 输出预算）
```

关键纪律（muse_api.py:137-165 / link_client.py:49-69）：`hatch_refresh:` 前缀**防双前缀**（App 交来的令牌已带前缀，rsplit 去重）；刷新响应的 access token **不直接采用**（服务器可能 200 返回全端点都拒的替换令牌——先验证再落盘）；401 语义二分（配对失效→重配对 vs 传输失败→重试）。Outcome 枚举五值（CLOSED/AUTH_REJECTED/FORBIDDEN/UNPAIRED/STOPPED）驱动重连策略。

## 3. executor.py 治理四招（本报告的核心增量）

1. **凭据/执行分账户**：`_child_options()` 在 root 运行服务时以 `user/group/extra_groups` 降权到 `run_as` 账户起子进程；服务账户（持设备令牌）**永不执行**模型命令——命令的权限面=该非特权账户的权限面。laos 对照：驱动子进程+seccomp 同方向，但 Muse 没有 per-command 能力分级与审批（无 Sentinel 对应物——laos 治理面仍是差异点）
2. **极小命令面 + 模型自描述**：全 SDK 只有四命令，`COMMAND_SPECS` 就是工具 schema，经 `link.register` 的 `commands_v2` 注册给 VM——能力声明与执行在同一张表，无第二真相源
3. **子进程生存期纪律**：默认 120s/上限 600s 超时；非阻塞读**只取已排队字节**（防孙进程 setsid 后持管道拖到 EOF）；超时 `killpg(SIGKILL)`+2s 宽限；shell 退出后 0.5s 排空
4. **输出预算的 escape 感知收缩**（_clip，executor.py:281-290）：96 KiB 截断后**循环检查 `json.dumps(text)` 的实际尺寸**再缩 3/4——因为 JSON 转义会把非 ASCII 写成 6–12 字节、坏字节变 U+FFFD，"96 KiB 字节"不等于"96 KiB 消息"；/link-control 单消息上限 256 KiB 是硬约束
5. file.write：64 KiB base64 分块顺序写 + 末块 sha256 校验 + 原子替换 + create_parents/overwrite 显式化——与 laos memory `_rewrite()` 的 temp+`os.replace` **同构互证**

另：identity.py 的设备身份是**随机本地管理 MAC**（首字节 unicast+locally administered），"不读网络接口、不暴露真硬件地址、升级/解配对后保持"——隐私细节与 node_id/BLE 名后缀六位对应的命名约定。

## 4. 技能系统：Markdown-only 的能力文档（43 active / 86 目录）

CATALOG.md 自述："43 active skills: 42 device/family skills and one shared Google Cast skill"。分发方式是**运行时自取**：README 原话 "give your muse a link to this GitHub repo in its chat and let it find the skills it needs"——技能不是代码是**给 agent 读的操作规程**。格式（YAML frontmatter name+description + 五段）：

| 段 | 作用（HomePod mini 样本实测） |
|---|---|
| Identify the Device | 型号/服务端点匹配；"服务广播 alone 不证明能力可用"——能力边界以实测为准 |
| Prerequisites | 前置规则：**"不弱化既有访问设置来获得连接"**、"请求的动作与目标扬声器都要有权限" |
| Workflow | 操作步骤；每步带验证（"写入后读回——某些固件会应答 setter 却不变更"） |
| Verify the Result | 动作后读状态复核；"不可用的元数据要诚实报告" |
| Limits | 明确不做什么（"不假定本客户端能控制别处开始的播放"） |

**与 laos 的关系**：这就是 laos 仓库自身纪律（AGENTS.md/skills/docs）的工业界同款——Anthropic skills、Meta skills 都收敛到"Markdown 规程 + 验证段 + 诚实边界"。laos 已有同等实践（发版纪律五类锚点、来源三档），**五段式里 laos 缺的是显式的 "Verify the Result" 段惯例**——laos 文档多写"怎么验"进 CHANGELOG/报告，但技能/指南类文档没有固定验证段。

## 5. 采纳裁决

| # | 裁决 | 内容 |
|---|---|---|
| A1 采纳（惯例） | **技能/指南五段式**进 laos 文档纪律：新增 guide/skill 类文档带 "Verify the Result" 与 "Limits" 固定段（Identify/Prerequisites 随文体）——低成本高收益的诚实性结构 |
| A2 采纳（设计） | **输出预算 escape 感知收缩**记入 telemetry/审计的输出裁剪设计参考（laos 审计行含中文，json.dumps 膨胀同问题；现实现按字符截断，遇代理/管道场景可援引此模式） |
| A3 互证 | file.write 分块+sha256+原子替换 ↔ memory `_rewrite`/cow.py `os.replace`——两边独立同款；run_as 分账户 ↔ laos 驱动子进程+seccomp 同方向 |
| A4 修正 | 姊妹篇 espclaw-vs-muse 的"全账号权限直授"表述细化为："run_as 账户的全权限、无逐命令分级审批"——特权分离存在，能力分级缺失（laos Sentinel 仍是差异点） |
| A5 不采纳 | Noise XX 协议栈自实现（laos 不做加密协议）；租用 VM 依赖（云依赖违红线——laos 叙事反其道：治理在端、模型可换） |
| A6 参照 | 技能运行时自取（丢链接让 agent 找技能）——laos MCP/驱动生态未来分发形态的参照；"may eventually be made available in the Muse product"=社区技能→产品集成的上升通道 |

## 6. "野心"叙事的诚实核对（●◐○）

- ● Meta Connect 2026-09-23 发布 Muse（含 Muse Charm 硬件）；2026-10-02 开源 Muse Gadgets SDK（TechCrunch/The Verge 报道 + 仓库自证）
- ● 开源范围=ESP32 固件+Linux SDK+88 路径技能目录；**不开源**=Muse agent 本体/租用 VM/App
- ◐ XHS 笔记标题一句（"野心/弯道超车"——已 404，正文不可核）；本报告不依赖其任何表述
- ○ "每用户免费云电脑"的持续性与商业意图（报道口径不一，不下结论）

---
*laos 采纳状态：A1/A2 为文档与设计惯例（下次涉及 guide/telemetry 裁剪时落地）；A4 修正已在本文 §5 完成；其余互证/参照留档。与 [INDEX](INDEX.md) 同步。*
