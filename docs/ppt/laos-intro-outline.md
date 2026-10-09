# laos 项目介绍 PPT · 共享内容底稿（12 页）

> 五套 PPT（ppt-master / guizang / frontend-slides / html-ppt / huashu）共用此底稿，
> 保证"同内容不同渲染"的公平对比。事实全部来自仓库 README/CHANGELOG/调研报告。

## P1 封面
- 标题：**laos · Linux AgentOS**
- 副题：Linux 内核的 Agent 治理层 —— 内核强制的能力边界，而不是提示词恳求
- 版本 v0.9.0 ｜ GitHub: Yfredy/LAOS ｜ 主库 353 + AlwaysOnRec 279 + Repro 71 = 703 项测试

## P2 问题
- 今天的 AI Agent 拿着用户的全部权限在裸奔：
  - 一条 `rm -rf` 就能删光家目录；一个恶意 MCP 工具就能把剪贴板/通知发出去
  - "不要做危险的事"写在提示词里——提示词是恳求，不是强制
- 缺的不是更聪明的模型，是**操作系统**：能力、调度、审计、记账、隔离

## P3 命题
- **Linux AgentOS = Linux kernel + Agent + MCP**
- 不改内核一行代码：复用 Linux 已有的强制原语
  - namespace（隔离视图）/ cgroup（资源上限）/ seccomp BPF（系统调用白名单）/ Landlock（路径沙箱）
- laosd 是**薄内核**：只做语义层（能力/审计/记账），把"设备"留给 MCP 驱动

## P4 一张类比表
| Linux | laos |
|---|---|
| 进程 | Agent（PCB/能力集/预算） |
| 系统调用 | MCP tool call（JSON-RPC） |
| 设备驱动 | MCP Server（drv_mic/drv_ear/drv_screen…） |
| 内核 | laosd 薄内核 |
| insmod | kernel.load_driver（可外挂任意 MCP 服务器） |

## P5 syscall 闸门链（核心卖点）
能力表 → task_scope（路径前缀 / `pkg:` 应用白名单 / `time:` 时间窗）→ schema 校验 → EDQUOT 预算 → FleetLedger 不可逆计价 → Jev 预审（opt-in）→ 确认横幅 → 派发 → 全量审计
- 每一次工具调用都过闸、都落账——事后可完整回放"谁在何时用掉了什么权限"

## P6 强制层三件套
- seccomp BPF：进程级系统调用白名单（真拦截，非约定）
- cgroup v2：驱动子进程 CPU/内存上限（驱动失控不拖垮宿主）
- eBPF profiler + CoW：行为画像与执行隔离

## P7 驱动即设备
- 内建：drv_mic（麦克风）/ drv_ear（ASR+评估）/ drv_screen（adb 屏幕操控+pkg 白名单）/ drv_notify / drv_comms / drv_battery / drv_events / drv_npu
- 手机五层能力：屏幕操控→LLM→通知→通信→传感器（对标 Mobile MCP 30 工具差距分析）
- **外挂路线**：kernel.load_driver 一行把任意 MCP 服务器（如 mobile-mcp）insmod 成内核驱动——遥测必须关

## P8 听觉管线·四段漏斗
① 常驻检测（VAD/PCEN，µW 级）→ ② 触发捕获（环形缓冲/唤醒词 DTW）→ ③ 即时蒸馏（SenseVoice 本地 ASR+情感）→ ④ 即焚（6h）
- 红线：录音只由显式 syscall 触发、LAOS_REC=0 全局禁录、每次调用审计、ASR 全本地
- Apple Watch S12 已验证同构路线（旁观者可见性是差异化）

## P9 Jev 判断层·快问快答
- 三判型：Noul（是非）/ Choice（2-255 选项）/ Score（2-10 级）
- 四闸门：高危预审 / 记忆过滤 / 压缩选择 / 技能质量
- 诚实教训：rule 后端校准实测 accuracy 0.519、高置信桶错误率 33% → **AUTOGATE 禁配 rule 后端**（校准先于自动化）

## P10 研究语料（不是拍脑袋设计）
- 双会议全量遍历：Interspeech 5,507 + ICASSP 14,285 = **19,792 篇**
- 开源普查 3,724 仓库；多顶会切片 35 venue / 9,908 条（数据源结构性地图）
- 采纳总纲 76 条映射（●已落地 33 / ◐推荐 23 / ○不做 20）

## P11 复现隔离区（六来源 71 测试）
BS.1770-4 响度计量（R128 校准点 −23.00 LUFS ±0.1）｜FxLMS 主动降噪（音调 >20dB）｜说话人头部朝向论文全管线（冒烟 holdout 56.5°）｜PhaseCoder 几何无关麦位编码（对齐官方 JAX 源码）｜Pipecat 帧管道（打断作废排队帧）｜unique_lock 语义
- 复现方法论：TDD、零新依赖、论文数字不作断言、偏差全记档

## P12 版本治理与路线
- v0.1.0 → v0.31.0 语义化版本 + Keep a Changelog + GitHub Release 页（一个完整需求波次 = 一次 MINOR）
- 合规红线：EU AI Act 职场情绪识别禁令 / PIPL 声纹单独同意 / 拒绝伪装采集链路
- Roadmap：drv_screen 多轮真机验收 → 外挂驱动 PoC（mobile-mcp）→ bs1770 响度合入主库 → SHO 指令定向过 mic.* 闸门
