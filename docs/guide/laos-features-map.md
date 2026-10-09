# laos 功能地图与使用 SOP（features map）

> 2026-10-09 · 基于 v0.35.0 实盘点（数字均为实跑实数：47 个核心模块 / 17 个驱动 / 1051 项测试全绿 / 108 份调研 / 42 份计划）。
> 回答一个问题：**这个项目到底有什么？** 按"AI/Agent 能力 · 纯工程能力 · 内核治理"三层分好类，每项带使用 SOP（命令/环境变量/入口）。
> 配套海报：[docs/diagrams/laos-features-poster.html](../diagrams/laos-features-poster.html)（竖版深色，浏览器打开即看）。

## 0. 一句话定位

**laos（对外 nanoLAOS）= Linux 内核治理在用户态的延伸；Agent 是与进程同类的新负载。** 它不是一个"调 LLM API 的聊天应用"，而是一套给 Agent 装上操作系统级治理（能力/审批/审计/记忆/语音）的完整系统——恰好与小红书那篇电商 Agent 的口号相反方向：那边是"不只是调 API 的 Agent 应用"，这边是"Agent 之下不只是 API 的那一层"。

## 1. 第一层：AI / Agent 能力（有模型参与的）

| # | 功能 | 是什么 | 使用 SOP |
|---|---|---|---|
| A1 | **云端大脑** `laos/llm.py` | OpenAI 兼容 LLM 对话（纯 stdlib） | `export LAOS_LLM_BASE_URL=… LAOS_LLM_MODEL=… [LAOS_LLM_KEY=…]` → laosweb 对话卡 |
| A2 | **语音转写** `laos/asr.py` | 按住说话：音频→文本（OpenAI 兼容 transcriptions） | `export LAOS_ASR_URL=… [LAOS_ASR_KEY/MODEL]` → 🎙 按住说话松手发 |
| A3 | **回复朗读** TTS | 浏览器 speechSynthesis 本地朗读 | 对话卡 🔇/🔊 切换（不出网） |
| A4 | **agent 记忆闭环** laosweb+memory | 你的话自动落库为"人写行"，下轮召回注入上下文 | 默认开；`LAOS_CHAT_MEMORY=0` 关；记忆面板看"人写"徽标 |
| A5 | **判断层** `laos/judge.py` | 决策快问快答（rules/edgejev/clef 三路线），入库预审 | `python scripts/calibrate_judge.py --backend rule`；`LAOS_JEV_*` env |
| A6 | **JIT 记忆整理** `laos/jitmem.py` | 用时再检索：三分量检索+去重+预算+首条优势 bandit | 内建 `mem.curate/mem.outcome` syscall（自动） |
| A7 | **语音对话栈** wakegate/dialogsched/turnpolicy | 唤醒四态机/打断版本化/附和吞掉/语义话轮路由 | 代码级能力（对话框管线装配）；KWS 实测 7.56ms |
| A8 | **HY4 听觉蒸馏**（姊妹仓） | SenseVoice ASR+情感一次前向（sherpa 通道） | `AOR_ASR_CHANNEL=sherpa AOR_SHERPA_DIR=…`（HY4 仓库内） |
| A9 | **Linux AgentOS demo** demos/agentos-demo | 30 秒讲清 kernel+Agent+MCP+seccomp 的认知演示 | `bash demos/agentos-demo/run_demo.sh`（WSL/Git Bash） |
| A10 | **录音回放** `rec.replay` | 常听会话最近 15–60s 音频快照+ASR 转写（听障/没听清辅助；内存环冲即焚，LAOS_REC=0 禁） | laosweb「录音回放」卡；内核 syscall `rec.replay` |

## 2. 第二层：纯工程能力（无模型参与，传统系统件）

| # | 功能 | 是什么 | 使用 SOP |
|---|---|---|---|
| E1 | **四段漏斗管线** | 常驻检测→触发捕获→即时蒸馏→原音频即焚 | 入口 `laos/vad.py`→`drivers/drv_rec.py`→`drivers/drv_ear.py`→`rec_gc` |
| E2 | **个人记忆库** `laos/memory.py` | JSONL 追加式+bigram 模糊召回+自检 | `python bin/laosctl.py selfcheck`；`bin/diary.py` CLI |
| E3 | **每日日记/周报** diary/journal | 审计+记忆聚合成 hour/day/week 摘要 | laosweb「生成今日日记」按钮 |
| E4 | **Web 控制面** bin/laosweb.py | 零依赖单文件面板：会话/审计/记忆/治理四 tab，PWA | `python bin/laosweb.py` → `http://127.0.0.1:8800` |
| E5 | **安卓客户端** clients/android | WebView 薄壳+原生语音桥（~40 行 Kotlin） | Release 页下 APK → 首启填电脑 IP；或 PWA 加主屏幕 |
| E6 | **审计系统** kernel.audit | 一行一事件 JSONL，gzip 轮转，epoch|seq 复合键 | 审计 tab 实时流；`bin/laosctl.py traceviz --tail` 转 mermaid |
| E7 | **埋点** laos/telemetry.py | 23 事件/138 字段，四级脱敏 | 自动（`LAOS_TELEMETRY_*` 配置） |
| E8 | **事件路由** laos/evroute.py | 声明式 JSON 规则热载+DROP 防火墙 | 对话管线入口自动；规则 JSON 可 CRUD |
| E9 | **发版管线** scripts/release.py | 真跑测试门禁+三树版本+五类锚点机器同步 | `python scripts/release.py --dry-run|--apply` |
| E10 | **交接门禁** scripts/check_onboarding.py | 交接文档数字漂移→当场红 | `python scripts/check_onboarding.py`（改码后必跑） |
| E11 | **调研校验器** check_{ser,aed,agc}_table.py | 调研表占位词/来源/口径机器校验 | 见 ONBOARDING §3 常用命令 |
| E12 | **语料库** corpus/ | 19,792 论文+3,724 OSS+38 venue 123,271 行 | `python scripts/query_corpus.py --topic audio-speech --strong-only` |
| E13 | **约束语言 lint** laos/ste.py | ASD-STE100 式 check-only 输出规范 | `LAOS_STE_LINT=1` 时钩 JitMem briefing |
| E14 | **17 个驱动** drivers/ | rec/mic/ear/screen/notify/comms/battery/events/npu/fs/…（重依赖子进程） | 经内核 syscall 调用（demo/laosd 装配） |

## 3. 第三层：内核治理（laos 的灵魂，别处没有的）

| # | 功能 | 是什么 | 使用 SOP |
|---|---|---|---|
| K1 | **syscall 闸门链** laos/kernel.py | caps→task_scope→sentinel→不可逆闸→dispatch 五道闸 | AgentKernel 装配即生效；每次调用落审计 |
| K2 | **Sentinel 动作闸** laos/sentinel.py | 六级判定+taint 永不回退+scoped grants(once/session/always) | 治理 tab：mode 三档/grants 撤销/污点 pids |
| K3 | **能力框架** laos/caps.py | per-agent allow-list（不在表内→EPERM） | 装配时授权；审批卡四钮（拒/一次/会话/总是） |
| K4 | **风险预算** | 不可逆操作的" irreversible budget"记账 | build_state 的 risk 面板 |
| K5 | **强制层** laos/seccomp.py | seccomp-BPF 物理禁锢（execve/socket 族 EPERM） | Linux 真机生效（Windows 测试自动 skip） |
| K6 | **分支与上下文** branch/context.py | BranchContext+ContextManager（operator/agent 会话域） | 内核内部件 |
| K7 | **隐私红线四件套** | 录音必须显式 syscall；`LAOS_REC=0` 全局禁录；录音成败都审计；ASR 全本地 | 环境变量即武器；审计 event:"mic" |

## 4. SOP：三分钟用好这套系统

**① 起服务（电脑）**
```bash
export LAOS_LLM_BASE_URL=… LAOS_LLM_MODEL=… [LAOS_LLM_KEY=…]
export LAOS_ASR_URL=… [LAOS_ASR_KEY=… LAOS_ASR_MODEL=whisper-large-v3-turbo]
python bin/laosweb.py          # http://<电脑IP>:8800
```
**② 手机接入**：Release 页下 `laos-client.apk`（首启填地址）或 Chrome 加主屏幕（PWA）。
**③ 日常**：对话卡打字/🎙 说话 → 审批卡处理 agent 的权限请求 → 审计 tab 看每一步 → 记忆 tab 看它记住了你什么 → 治理 tab 管 grants/mode。
**④ 维护**：改完代码 `python -m unittest discover -s tests`（1051 全绿）→ `python scripts/check_onboarding.py`（文档无漂移）→ `python scripts/release.py --apply` 发版（tag 推送后 CI 自动出 APK）。

## 5. 红线（治理层的"不做"清单）

录音只在显式 syscall 时发生且 6 小时即焚 · 对话内容/音频永不进审计 · taint 永不回退 · 支付/密码永不记忆 · 核心包零第三方依赖 · 只用 `C:/Users/yaoyue/miniconda3/python.exe`。
