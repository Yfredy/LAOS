# nanoMuse/Muse 全参照清单 —— 功能、界面设计与全端兼容（laos 取经手册）

> 2026-10-08 · 用户指令："这两个项目对我的项目很有参考意义，比如功能与前端界面设计，以及在手机、电脑、平板等所有端侧设备上兼容。写出所有能参考的内容"
> 方法：全仓源码（本地克隆 var/repro/nanomuse，含活体容器）+ 论文 §3 十项决策 + Web 前端逐文件盘 + 端侧三壳逐桥盘；每条带锚点，末列 laos 对位（●采纳/◐排队/○不做）
> 姊妹篇：[2026-10-08-nanomuse.md](2026-10-08-nanomuse.md)（Sentinel/记忆深拆）、[2026-10-08-aios-agentos-landscape.md](2026-10-08-aios-agentos-landscape.md)（Muse=OS 内核派展示方向的格局论证）

## 1. 功能全景（16 屏，web/src/App.tsx:146-159 + 组件清单）

| 屏 | 功能 | laos 对位 |
|---|---|---|
| chat | 对话主屏（工具调用 chips、步骤默认展开、审批卡内嵌、文件/截图查看器 FileViewer、听写 Dictation、@设备 前缀跨端委派） | ● laosweb v3 主屏 |
| feed | 每日晨报（daemon 定时生成的日报流） | ◐ 排队（laos diary 已有日报体，差 UI 流） |
| ideas / goals | 灵感池（房间，agent 在隐藏会话写）/ 目标例程（关屏继续跑） | ◐ P2（laos 对话管线后评估） |
| library | 会话库/线程列表（ChatsDrawer 同步多设备） | ● 会话列表 |
| memory | 记忆面板（双线：SQLite 行记忆 + Markdown 文件，可编辑） | ● 直连 MemoryStore/curate（provenance 已就位） |
| skills | 技能面板（MCP servers + skills 管理） | ◐ 接线波（caps/工具表面已有） |
| connections | 连接管理（模型 key 18 providers、ChatGPT 登录态、自托管 relay） | ◐（laos 驱动域已有同构物） |
| channels | IM 渠道（飞书/钉钉/企微/Telegram） | ○ 不做（laos 域外） |
| devices | 跨端设备互操（hub：另一台电脑作为工具；发起端先过审、接收端不再问） | ◐ P3（FleetLedger 多机叙事对位） |
| you（Settings） | 设置（Sentinel 模式 ask/strict/auto、always-ask 列表、taint 说明、中断条、数据控制 DataControls 导出/删除） | ● 治理面板（sentinel 三模式+grants 列表 UI） |
| account / coding / avatar | 账号/编码模式/头像工作室（可换 agent 形象） | ○ 头像不做；coding ◐ |
| 审批中心 | 审批卡（API：`/api/approvals/{id}` 带 **approved/scope/reason** 三字段，`/grants/{key}` DELETE 撤销——见 api.ts:256-259） | ● 与 laos GrantStore(scope) 完全同构，直接抄语义 |
| ModelPicker | 模型切换器（18 providers 运行时可换） | ◐（laos decide 后端注册表面已有） |

**支撑功能**：token-in-link 鉴权（`#token=`，api.ts:67-95）；WS 常连接推送（api.ts:447 connectWs）；i18n 中英（web/src/i18n，zh-CN 全量）；断线分级重连（closeOutcome→retry/auth/gone，api.ts:440）； allowances/配额文案；Markdown+GFM 渲染；听写；分享表单。

## 2. 界面设计参照（论文 §3 十项易读性决策 → UI 结构事实）

**Muse 赢在形态不在基准**的十项（论文逐项 source-marked，全部适用于 laos 对外叙事）：

1. **单 agent 有名有脸**——不是一个工具，是一个"人"（IdentityForm/Avatar 组件族）
2. **一条长会话**——不是工单队列；历史即记忆（Main chat 默认线程）
3. **工具调用 chips**——内联小片而非日志墙（chat 流内）
4. **scoped 审批卡**——once/本会话/always 三钮 + 撤销可见（Cards/审批中心）
5. **记忆即文件**——用户可读可编辑（memory 屏 + Android 线 GLOBAL.md）
6. **五个房间**——Feed/Ideas/Goals/... 空间化而非功能菜单
7. **暗化 live stage**——agent 干活时界面退后（dimmed live stage）
8. **步骤默认展开**——透明是默认，折叠是选项（与"格式越好懂错误藏得越深"的对照设计）
9. 唤起信任的**品牌面**（BrandMark、头像、名字）
10. **移动优先单列**——手机是第一公民，桌面是加宽（mobile-first 实锤：package.json 自述 "mobile-first web app"；desktop.ts 说"知道在 Electron 壳里就按桌面程序布局"）

**UI 工程事实**（可直接抄的结构）：App.tsx 仅 261 行——薄根 + 34 个小组件（Sheet/BackBar/TabHeader/Cards 等每件 ≤300 行）；api.ts 513 行单文件封装全部后端交互；状态机式 tab 路由（无 react-router，URL hash 即 tab，App.tsx:81）；CSS 用 Tailwind 4 + lucide 图标；**测试进 UI 层**（api.test.ts/fences.test.ts/gate.test.ts/Markdown.test.ts，vitest）。

**laos 取舍**：设计语言（十决策+组件化+单列优先）**照抄语义**；React/Vite/Tailwind 技术栈 **不抄**——laos 零依赖纪律下 laosweb 维持 stdlib 内嵌前端，用原生 ES 模块 + CSS 变量达到同等形态（暗色/亮色主题变量、safe-area、响应式断点）。

## 3. 端侧兼容架构（"所有端"的教科书解法：一套 Web UI + 每端一层薄桥）

**核心事实**：全产品只有一个 UI——React Web；Android/iOS/桌面/平板全部是"壳 + 桥"：

| 壳 | 机制 | 桥接口（锚点） | laos 对位 |
|---|---|---|---|
| 浏览器/平板 | PWA：manifest.webmanifest + apple-mobile-web-app 三 meta + viewport-fit=cover（index.html:6-24） | 无桥，纯响应式 | ● laosweb v3 加 PWA 四件套（手机/平板"安装"即用） |
| Android | WebView 宿主 android/（OpenMinis 底子），暴露 `window.NanoMuseAndroid`（android.ts，**14 方法**）：通知开关/无障碍服务态与跳转（屏幕之手）/浏览器接管 takeOverBrowser+hand-back 事件/**保活状态 KeepRunningStatus**（battery_unrestricted/overlay/exact_alarms/boot_start + **厂商自启矩阵 vendor: xiaomi·huawei·honor·oppo·vivo·samsung·meizu**）/开机自启/日志 zip 分享 | ○ 原生不做；**保活矩阵与厂商现实主义是 laos 听觉线端侧化的必抄知识**（AlwaysOnRec 端侧化波引用） |
| 桌面（Win/mac/Linux） | Electron（UI-TARS 移植之手），暴露 `window.nanomuseDesktop`（desktop.ts）：platform/loginItem 自启/**quick-chat 全局快捷键回调**/macOS 红绿灯留白；"知道在壳里就按桌面布局——sidebar 恒显" | ◐ 排队（laosweb 响应式先行；Electron 壳是后续可选项） |
| iOS | 一切功能除"手"（OS 限制，论文 §6 架构图）；TestFlight 分发 | ○ 同 Android 结论 |
| 跨端同步 | relay：文本过云、**文件永不过云**（cloud/sync.py:4-7 "Never a file, never a picture"）；hub 帧互操；presence 10min TTL | ◐ P3（隐私红线友好的同步设计可引用） |

**鉴权与安装零摩擦**：token 进 URL 片段（`#token=`，不进服务器日志）；扫码即用（serve 默认打 QR）；`signInDoorNeeded()` 门（gate.ts：无账号但有自己的模型 key 也可全功能离线用）——**"带自己的模型即可用"是 laos 天然同构的立场**。

## 4. 治理面的 UI 表达（与 laos Sentinel 波的直连）

- Sentinel 三模式（ask/strict/auto）在 Settings 可调 + always-ask 列表编辑 + taint 说明文案——**治理设置是一等界面而非隐藏配置**（config.example.toml:96-106 + SettingsScreen）
- 审批卡三字段语义（approved/**scope**/reason）与 laos GrantStore(once/session/always) **逐字同构**——laosweb v3 审批卡直接按此交互抄
- grants 列表可逐条 DELETE（api.ts:259）= laos `GrantStore.revoke` 的 UI 面
- audit（sentinel/audit.py 七级 channel 阶梯 gui/browser/web/cli/device/api/local）= laos traceviz/audit 流的 UI 化参照

## 5. laos 采纳总表（本手册 → 行动）

| # | 参照 | 裁决 | 落点 |
|---|---|---|---|
| 1 | 十决策设计语言 + 审批卡（scope 三钮+撤销）+ 工具 chips + 步骤默认展开 + 单列移动优先 + 暗亮主题 | ● | **laosweb v3 波**（[实施计划](../superpowers/plans/2026-10-08-laosweb-v3.md)） |
| 2 | PWA 四件套 + 响应式断点（手机/平板） | ● | 同上（laosweb v3 Task） |
| 3 | 审批 API 语义（approved/scope/reason + grants DELETE） | ● | 同上（对 laos sentinel/GrantStore 开 HTTP 面） |
| 4 | 记忆面板（行+文件双视图、provenance 标记） | ● | 同上（MemoryStore/jitmem payload 已有全部数据） |
| 5 | 治理设置一等界面（模式/always-ask/taint 文案） | ● | 同上 |
| 6 | feed 晨报流 / skills 面板 / devices hub | ◐ P2-P3 | 对话管线/接线波后 |
| 7 | Electron 壳 + quick-chat 快捷键 / relay 跨端同步 | ◐ P3 | 响应式 Web 先行验证 |
| 8 | Android 保活厂商矩阵 + 无障碍之手 | ○ 原生不做 | **知识收录**：AlwaysOnRec 端侧化波必引（xiaomi/huawei 等 7 厂商自启管理是常开录音频频被杀的真实原因清单） |
| 9 | React/Vite/Tailwind 技术栈 | ○ 不做 | 零依赖纪律；std lib 内嵌前端达到同等设计语言 |
| 10 | 头像工作室 / IM 渠道 | ○ | 域外 |

## 6. 一句话

nanoMuse 给 laos 的最大礼物不是功能清单，而是**形态哲学**：把治理（审批/权限/污点）做成界面的第一公民、把 UI 写一次让每端做薄壳、把"步骤默认展开"当透明度的默认值——这三条 laos 全部有同构内核（sentinel/laosweb/audit），差的只是表达层；laosweb v3 波补的就是这层表达。
