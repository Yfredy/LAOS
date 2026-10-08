# Changelog（laos）

所有重要变更记录于此。本项目遵循 [Semantic Versioning](https://semver.org/spec/v2.0.0.html) 与 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)。
0.x 阶段：minor 即功能波次，breaking 不升 major。

## [Unreleased]

## [v0.30.0] - 2026-10-08

### Added
- feat(laos): **ARVIS 波——话轮路由三件（R1 附和吞掉 / R2 语义路由 opt-in / R3 播报时窗）**（spec=[2026-10-08-arvis.md](docs/research/2026-10-08-arvis.md) §7 裁决 R1-R3；ARVIS Apache-2.0，学设计零拷贝）。① **R1 附和白名单**：`turnpolicy.classify_barge_in`+`normalize_utterance`（剥全/半角标点+casefold）——播报（Processing 态）中的用户终稿不再"开口即让位"，**整句**命中 15 词附和表（嗯/嗯嗯/啊/哦/噢/对/好的/好/知道了/继续/是的/yes/yeah/ok/okay，ARVIS 13 词同位+补"是的"）吞掉不打断、播报继续，其余按真打断让位（终稿权威原则；"嗯，但是…"不是附和）。**行为变更两处**：speech_started 在 Processing 态不再迁移（barge 候选语义——VAD 起点只算候选，让位与否等 ASR 终稿过路由；telemetry 迁移事件随之改由 process() 让位路径发 reason="barge_in"）；播报中喊休眠词从"丢弃"改为"生效回睡"。wakegate 锁 Lock→RLock（注入分类器在 process 持锁期间回调 backchannel_words 只读属性，非重入锁死锁——实施时自查抓获）；WakeConfig.backchannel_words（LAOS_WAKE_BACKCHANNEL_WORDS env 覆盖）；WakeResult.backchannel 标记；set_barge_classifier 注入口，分类器异常按真打断（fail 方向：宁让位不装聋）。② **R2 语义话轮路由（opt-in）**：`turnpolicy.TimedTurnJudge` 限时包装（默认 120ms 预算=ARVIS 同值；工作线程+join，超时后线程仍跑 daemon——判断后端须自兜网络超时），超时/异常/废值一律 ("fallback", reason) **落回关键词档**——附和白名单离线仍生效、真打断照常让位（与 ARVIS 失败方向"保播报"相反：不引入"判断服务挂了就装聋"的静默失效面）；DialogPipeline(turn_judge=) 装配：continue=吞（播报继续）/ yield·wait=让位进 turn（wait 的澄清反问+锁工具语义归执行方，裁决经事件可观测）；note_answer() 喂助手侧滚动尾串（2000 字符，ARVIS 用 4000 减半）；每次裁决发 **d.dialog.turn_route** {decision, source}（无文本脱敏级；吞与放行两态都发——被吞的话轮也是一次治理决策，首版只记放行的审计空档为实施时自查抓获）。③ **R3 播报时窗**（ARVIS AnnouncementWindow 三条件语义）：announce(text) 把后台任务播报压进窗口——用户说话中 / 话轮未落地（asr_final→turn_done）/ TTS 音频未走完（turn_done 的 tts_remaining_sec 计截止线）三条件全空才放行；阻塞的 FIFO 挂起，窗口开（speech_ended / turn_done 过截止线 / tick）自动冲刷；放行队列 take_announcements() 由调用方取走发声——**不走 DialogQueue**（latest-only 会互相清队）、**不过唤醒闸**（agent 主动发声，治理在内核侧）；d.dialog.announce {accepted, pending} 无文本。27 例新增测试（turnpolicy 8＋wakegate 7＋dialogflow 11＋telemetry 契约更新 1），全套 **1016 全绿**（989→1016，OK skipped=5）
- docs(research): **ARVIS 学习报告**（INDEX 93 资产）——XHS 笔记 404 → GitHub 溯源 GHJ20001017/Full-Duplex-Model（Apache-2.0，HF speech-to-speech 修改版）：级联式全双工工程解法全拆解（AEC3 回声消除/双档打断路由/话轮 revision 化投机重开/播报时窗/保留信封守卫/qwen-audio-agent 三层架构）；**语义路由请求体=jev 协议原文**（与 laos 判断层同方言）；CancelScope=GenerationGate 同构互证、sherpa-onnx KWS 双边同款；未采纳项留档：R5 AEC3 走驱动子进程参照（MicrophoneGate aec_ready 预留位吻合）/R6 e2e 训练侧不采纳/R7 互证记录；Sentinel grants 补 TTL/LRU 上限进排队清单；INDEX 头部计数对准实数 95（分项漂移归属"INDEX 预存计数漂移归属波"排队项）

## [v0.29.0] - 2026-10-08

### Added
- feat(laosweb): **laosweb v3 波——Muse 形态哲学的 laos 化**（spec=[2026-10-08-nanomuse-ui-xdevice-reference.md](docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md) 采纳 #1-#5；零依赖纪律不破：抄设计语言不抄 React 技术栈，仍纯 stdlib http.server+单文件内嵌原生前端，零 npm/构建链/CDN 外链）。① **/api/sentinel 治理面**（GET/POST）：GET 投影 {enabled,mode,private_tools,egress_tools,grants,tainted_pids} 直连 kernel.sentinel；POST 三动作 grant(tool_glob,target,scope)/revoke(gid)/set_mode(ask|auto|strict 直改 cfg.mode)，未知 action→400；**未装配优雅降级**（{"enabled": false}+空列表，与核心 opt-in 哲学一致）。② **审批卡 scope 三档语义**（nanoMuse 审批 API 三字段 approved/scope/reason 的 laos 化）：pending 条目新增 reason（sentinel 决策因透传，无 sentinel 时 null）；POST /api/confirm 扩 {cid,approved,scope,tool}——approved 且 scope∈{session,always} 时**先落 grant 再放行**（deny/once 不落 grant），旧 id/allow 键回退保留无双破。③ **v3 骨架**：PAGE 重写为 mobile-first 底部四 tab（会话/审计/记忆/治理）+暗亮双主题（CSS 变量+prefers-color-scheme）+≥900px 桌面侧栏恒显（参照 nanoMuse desktop.ts 语义）+**PWA 四件套**（manifest.webmanifest/icon.svg 内联 SVG 零二进制资产/viewport-fit=cover/theme_color #0f6f5c）。④ **四视图**：chat=状态 chips+**审批卡**（tool chip+reason 徽标+四钮：拒绝/允许一次/本会话/总是——后两钮带 scope，前端始终显式带 tool 不给服务端 "*" 兜底留门）+进程表 kill+operator 信箱+restart 运维（v2 五 POST 全回归）；audit=工具 chips 流（ok/err 着色+失败截 80 字符辅文+固定容器只 prepend）；memory=stats+**provenance 徽标**（origin=user 亮显「人写」——人写行胜模型行，v0.28.0 用户行神圣的前端表达）；gov=enabled 门控（未装配只读+POST 400）+mode 三选一+grants 表逐条撤销+污点 pids chips+private/egress 工具面只读。数据整形抽模块层纯函数 _chips_rows/_memory_rows（可单测，键名按 build_state 实际而非计划伪码）；XSS 地基=动态内容全 createElement/textContent，全页无 innerHTML（静态断言钉死）。**实施与审查裁决三要点如实记**：（a）**tick 容错**——T3 移交必修：tick() 循环体 try/catch 且 setTimeout(tick) 排 catch 之外，fetch/渲染任一故障只吞一轮绝不杀死轮询（POST 后刷新走一次性 refreshNow 不并自排程循环）；（b）**复合键恢复**——T3 下线旧 JS 时轮转安全去重正向断言随之退役（仅剩"裸 seq 不得复活"守卫），T4 审计视图恢复 **epoch|seq|t|tool 复合键去重**+正向静态断言（v0.21.0 语义在 v3 前端续命，客户端 200 行上限+restart 清账本）；（c）**F1 smoke 留档**——审查发现首轮人工验收日志 0 字节（证据空档），重做真实 live smoke 落盘 var/laosweb-smoke.log（2799B：/api/state 200→四钮语义 deny→pending 清空审计续滚→sentinel 未装配 GET 200 降级）。15 例新增测试（T1 4＋T2 2＋T3 净增 1＋T4 净增 8），全套 **989 全绿**（974→989，OK skipped=5）
- docs(research): **nanoMuse/Muse UI 全参照手册**（INDEX 88 份）——功能 16 屏/界面十决策/全端兼容架构（一套 Web UI+每端薄桥：Android WebView 14 方法桥含 7 厂商保活矩阵/Electron 桥/PWA 四件套）：审批 API 三字段与 laos GrantStore 同构、React 栈不抄（零依赖纪律）；§7 目录组织学=仓库卫生波 spec（INDEX 行注记）；采纳 #1-#5 直供本波，Android 保活厂商矩阵留作端侧化波必引

### Changed
- chore: **仓库卫生波**（spec=参照手册 §7 目录组织学）——① 根目录清零（日志残渣删/outputs 归档 corpus/audio-eval/_s2_crawl 归位 var//fsroot 残件删）；② zone 四树收进 zones/（release.py VERSION_FILES/DOC_GLOBS/文档路径同步；该 commit **198 个 rename 全程 git 保历史**，全波合计 218 rename，rename-only 不触测试锚点——release.py --dry-run 计数前后不变）；③ docs 根层归类（diagrams/ 收七件渲染物/guide/ 收指南）；④ 目录学约定固化 AGENTS.md+.gitignore 失效规则清理；⑤ 品牌层改名 **nanoLAOS**（副标 laos · Linux AgentOS；对外名变、技术名/包名/CLI/LAOS_* 契约不变）

## [v0.28.1] - 2026-10-08

### Fixed
- fix(laos): **Sentinel 终审 F1——private_tools 幽灵工具名 + mic 读不置污**（whole-branch 终审发现）。① SentinelConfig.private_tools 默认值的 `"mic.read"` 是幽灵名（全仓无此工具；真实驱动面为 mic.record/listen_start/listen_stop/**segments**/status）——改为真实读取面 `("mem.recall","mem.curate","mic.segments")`（mic.record 属采集面、已有 confirm/审计覆盖，不算隐私读）；② 污点标记从 _impl_mem_recall/_impl_mem_curate 两处硬编码改为**闸门通用路径**（sentinel 放行后按 assessment.reads_private 统一置污，fail-closed：dispatch 失败也置污只增摩擦不漏污）；③ 新增 test_mic_segments_read_taints 双层断言（decide 语义 + kernel 级清单驱动置污→msg.send 触发 taint-egress）。1 例新增测试，全套 **974 全绿**（973+1，OK skipped=5）。plan 文档中两处 mic.read 为带日期历史档案按惯例不改写，勘误在任务报告备案

## [v0.28.0] - 2026-10-08

### Added
- feat(laos): **Sentinel 动作闸波次**（nanoMuse 采纳，docs/research/2026-10-08-nanomuse.md §4/§5 裁决 #1/#2；GPL 红线=只学设计零代码拷贝）。① `laos/sentinel.py` **判定核六级有序动作闸**：Assessment(tool, risk, reversible, reads_private, egress)→Decision(action, reason, grant_scopes)，判定序 ①deny_tools 硬拒→②显式规则（tool_glob，allow/ask/deny——唯一能放行污点出站与终审警告的通道）→③always_allow/always_ask 列表→④风险×模式（auto 全放/strict 非 low 问/ask 默认：不可逆或高风险问）→⑤taint 升级（污点 pid 的出站工具强制 ask，auto 也生效、永不回退）→⑥终审警告（不可逆∧高风险→ask 且仅 once 档，auto 除外）。② **GrantStore scoped 授权**：add(tool_glob, target, scope∈{once,session,always}) 非法档 ValueError＋covers 消费式命中（once 命中即焚、target 绑定、查询缺 target 视通配）＋revoke/list_grants，单锁线程安全；**TaintTracker** 并入 Sentinel：mark_private_read/is_tainted/untaint，污点只涨不清、per-pid 隔离、唯一清除通道=进程退出（kernel kill 路径）。③ **kernel opt-in 接线**：`AgentKernel(..., sentinel=None)` 缺省**字节级不变**（四钩子全守护、零 sentinel 审计行，test_default_none_is_byte_compatible 钉死）；ask 走既有 confirm 回调、grants 命中 session/always 档免问（⑤taint-egress/⑥终审的仅 once 档恒问人类）、deny→EDENIED；装 sentinel 的 syscall 各落一条 `event:"sentinel"` 审计（pid/tool/decision/reason/grant）；mem.recall/mem.curate 成功即置污点、kill 清污。④ **记忆 provenance**：`remember(origin="agent", origin_pid=None)` 新参缺省零变化（syscall 落库记忆可追溯 pid，旧行缺键读作 agent；bin/laosd.py JevGatedMemory 纯透传、bin/diary.py 自记行 origin="diary"）；JitMem curate **用户行豁免**：去重循环用户行神圣（不作为被去重对象、同文 agent 行让位）＋预算循环豁免（计入 entries 不计 used/budget_dropped）——人写一行胜模型任何行。**实施裁决四要点**（brief 逐字实现与逐字测试矛盾处，均经独立审查实跑证实）：⑥终审原落位在④条件真子集、永不可达→**双修正**（④加 not-terminal 守卫＋⑥加 mode!="auto" 门控，六级文档序不变）；⑤taint-egress 的 grant_scopes 收敛为**仅 once 档**（session/always 持久授权不得压制污点出站“永不回退”，唯一豁免=②显式 allow 规则）；**egress→不可逆仅喂 Assessment**（闸门内 reversible=spec.reversible and not egress，spec.reversible 与既有风险记账口径零漂移）；**用户行优先预排序**（稳定排序把用户行排到去重循环前部；无 origin 的既有 jitmem 23 例排序键全同、顺序不变零回归）。26 例新增测试（T1 10＋T2 7＋T3 6＋T4 3），全套 **973 全绿**（947→973，OK skipped=5；v0.26.1 段所记 946 系既往记账偏差——其后至本波前无任何 tests/ 提交，波前实跑基线 947，本段起锚定实跑数）
- docs(research): nanoMuse 学习报告（INDEX 87 份）——论文 arXiv:2610.08699＋仓库 33 次 GitHub API 源码直读：Meta Muse 开源对照物（GPL-3.0）的 Sentinel 动作闸/taint/scoped grants/记忆双线全拆解；自认“policy 边界非特权边界”=laos caps+seccomp 差异化定位的反证，Muse 生产复刻段（每人一台 Linux VM＋seccomp＋kernel taint＋Sentinel 唯一权限权威）为 laos 内核治理叙事的商业印证（详见该报告条目）

## [v0.27.0] - 2026-10-08

### Added
- feat(demo): **Linux AgentOS 认知 demo**（demos/agentos-demo/，四任务 TDD，三路调研报告 [2026-10-08-aios-agentos-landscape.md](docs/research/2026-10-08-aios-agentos-landscape.md) 的直接产物）——把"Linux AgentOS = Linux kernel + Agent + MCP 服务"命题做成 30 秒可演示的自包含认知物：① `mcp_fs.py` **MCP 文件服务（设备驱动角色）**：stdio JSON-RPC 2.0，fs.read/fs.write 限 jail（DEMO_JAIL）+ time.now，越界驱动侧拒；② `kernel.py`+`agent.py` **内核+Agent 进程模型（监督者角色）**：Agent=真实 Linux 进程（pid/SIGTERM/负退出码全真，AIOS 调度器=threading.Thread 的用户态模拟对照）、per-agent 能力表（allow-list→EPERM）、audit.jsonl 一行一事件（拒答也留痕）、syscall 经 _McpProxy 代理到驱动；③ `seccomp_gate.py` **L4 强制层**：agent 进程自装 seccomp-BPF（execve/execveat/socket/socketpair/connect→EPERM，其余放行；arch fail-closed；复刻 laos/seccomp.py 交错布局）——"能力管许可、seccomp 管物理"；selftest 旁路协议让 agent 在自己进程里实测危险操作被拦；④ `run_demo.sh` 五幕叙事 + README 四行对应表（Agent↔进程/内核↔监督者/MCP↔驱动/seccomp↔强制层）。7 例测试（WSL 运行，非 Linux SKIP 2）+ 幂等叙事脚本。**实施注记：计划自带 _filter() BPF 跳距 off-by-one（照抄=全放行坏过滤器且 arch fail-open），实施者改用 laos/seccomp.py 交错布局+fail-closed，任务审查者以 BPF 解释器模拟独立证实（59/322/41/53/42 全 EPERM、其余 ALLOW）**。.gitattributes 新增 *.sh eol=lf（防 autocrlf 破坏 WSL bash）。demo 自包含零依赖不 import laos、不进主测试套件（主库 946 绿口径不变）
- docs(research): AIOS/AgentOS 三轨全景调研（+new-domain 新文档域）：四派分层判定 + 真内核碎片清单 + 全天候录音增量（详见该报告条目）

## [v0.26.1] - 2026-10-08

### Fixed
- fix(scripts): **release 工具债三件**（排队清底）。① next_version **新文档域轴**：纯 docs 波次（README §十"新文档域=MINOR"）无法自动识别"新域"，约定 subject **尾部**标记 `+new-domain` → feat 等价升 MINOR；标记必须收尾于末端——正文提及字样不得误触发（**自指 bug 实录**：本工具自己的 fix 提交 subject 写着 "+new-domain minor axis" 被首版实现推成 MINOR 0.27.0，当即回滚版本同步并收紧为 endswith+回归测试钉死）；② sync_docs **"项"模式**（detail=True）：报告行附逐锚点命中细目 `[当前版本行×1,deck页脚×2,...]`（_DOC_PATTERNS 全面命名化），供终审五类锚点核查，缺省输出不回归；③ **DOC_GLOBS 补全**：`docs/ppt/*.md`+`docs/ppt/*.html`（intro 组 deck/outline 入列）+ `AlwaysOnRec-*/README.md`（三棵树通配）——核查发现 **AlwaysOnRec-DB/README.md 带 5 处测试计数锚点从未被同步**、intro 组 "703 TESTS GREEN"/"APPROVED · 703 GREEN" 戳自 v0.20.0 起漂移，新增两条英文戳模式后一并捕获；README §十补标记约定说明。6 例新增测试（新域轴 2+中置不触发 1+detail 1+覆盖 1+回归内嵌），全套 **946 全绿**（942→946，OK skipped=5）

## [v0.26.0] - 2026-10-08

### Added
- feat(laos): **对话管线装配 + 接线波**（排队任务兑现，docs/research/2026-10-08-dialogflow-assembly.md；espclaw 报告 §五裁决 #2 ◐P2 → ●兑现、#3/#4 ◐P3 → ●对照收档）。① `laos/evroute.py` **事件规则表**——esp-claw claw_event_router（Apache-2.0）转译：JSON 规则热载（load_file+reload）+ CRUD（重复 id/未支持动作 fail-loud 拒绝）；match{type/source/text/text_match(exact\|prefix)}；六动作映射三动作 call_cap（回调注入，装配层接 caps.py）/drop（事件防火墙）/emit（派生事件回注+字段拷贝），run_agent/run_script/send_message 属 kernel/驱动域经 call_cap 动作化；**consume_on_match**（首条消费）+ **fail_open**（per-action，默认 False=保守中止）语义保留；无规则命中=passthrough 放行；RouteResult 与 claw_event_router_result_t 同构（matched/matched_rules/action_count/failed_actions/first_rule_id + dropped/emitted）。② `laos/dialogflow.py` **管线装配**：入口三事件+VAD 先过路由器（DROP=对话面防火墙，测试钉住规则吞掉的 asr.final 永不进唤醒闸/JIT curate）→ WakeGate → DialogQueue（latest-only）；**phase="done" 债兑现**（turn_done 补发同 turn_id 的 d.dialog.turn，与入队 phase="queued" 配对——v0.21.0 明言"完成态归装配层"）；**JitMem 接入**（v0.24.0 四步循环第④步在对话域闭合：会话首 turn curate 一次、payload 会话级缓存、每轮 turn_done 即时成败 outcome 回填）。③ 接线债清账：`WakeConfig.from_env()`（LAOS_WAKE_ENABLED/WAKE_WORDS/SLEEP_WORDS/MAX_TURNS/SESSION_SEC/FOLLOWUP_SEC，坏值回退默认）+ LAOS_DIALOG_OBS_MS/RESUME_MS env 覆盖；**diary 跨代聚合**（v0.21.0 已知缺口：`_load_audit` 读活文件+同目录全部 audit-*.jsonl.gz 归档代，**按数字代序**非字典序拼接，轮转后当天记录不再漏归档段）；64MB 水位核对已实装无需代码（telemetry max_bytes=64MB+写前归档，v0.21.0 波内已做）。④ P3 对照收档：phase 命名对齐（claw 8 相位=agent 循环相位 vs laos 四态+queued/done=会话/轮次相位，语义域不同不硬搬枚举；统一出口+reason 枚举同构做法已有）、双分区播种（AuditLog gzip 归档=不可变基线+活文件可写+epoch/seq 跨代去重+本波 diary 跨代聚合=同构已有；"运行时重建播种"对个人记忆库方向不适用）。31 例新增测试（16+13+2），全套 **942 全绿**（911→942，OK skipped=5）。实现注记：装配层事件 sink 协议为两参 (event, fields)（dialogsched.safe_emit 房型协议），测试首版误用单参 list.append 被 safe_emit 按设计吞 TypeError（埋点永不影响主链路）——协议使用坑记录在案，非代码 bug

## [v0.25.0] - 2026-10-08

### Added
- feat(laos): **AI 输出可理解性波次**（Karpathy 四阶梯复现与采纳，docs/research/2026-10-08-readable-output.md）。溯源 Karpathy 原帖 2026-10-02（x.com/karpathy/status/2105819303471976479）：理解速度成瓶颈，四阶梯升序=ASD-STE100 约束语言→图表→HTML 交互页→解释视频。① `laos/ste.py`——ASD-STE100 **原则**的 check-only lint（官方 ~900 词表再分发受限不收录，与社区 asd-ste100-skill 同取舍）：五规则 R1 句长（分句后>60 字）/R2 术语轮换（同义组≥2 形并存，Karpathy 点名 agent/worker/executor 痛点）/R3 一句多事（子句分隔>2）/R4 hedge 堆叠（同句≥2 模糊限定词）/R5 分号并联；问题带原文摘录+位置按确定性排序，**只检查不改写**；CLI `python -m laos.ste`（有问题 exit 1）；② `laos/traceviz.py`——audit.jsonl 的 syscall 事件→mermaid sequenceDiagram（agent↔kernel 调用链，失败 `--x` 显式标出，参与者名清洗防破坏 mermaid 语法），**只读派生视图**审计永远权威；③ `laosctl traceviz --tail N` 新子命令 + `python -m laos.traceviz`；④ kernel 钩子：`LAOS_STE_LINT=1` 时 `mem.curate` 的 briefing 过 lint、`ste_problems` 计数入审计（opt-in 默认零行为变化）——上一波 JitMem curate briefing 即 laos 第一个系统性 AI 输出物，本波即"用这个进行改进"的落点。裁决：③交互页 ◐P2 排队（laosweb 已有查看页）、④解释视频 ○不做（重依赖+云端 TTS 撞零依赖/隐私双红线）；笔记"格式越好懂错误藏得越深"未见于原帖（转译层增补），采纳为双层结构治理原则：一切派生物必须能回到原始记录。27 例新增测试（17+10），全套 **911 全绿**（884→911，OK skipped=5）
- docs(research): 可读性笔记复现报告（INDEX 84 份）——Karpathy 原帖四阶梯逐项 ●证实（fxtwitter API+SEJ 报道交叉），笔记两处表述如实分档（警告句 ○笔记增补、"字数砍半" ○未证实数字）

## [v0.24.0] - 2026-10-08

### Added
- feat(laos): **Just-in-Time Memory 波次**——记忆在使用时再被理解（read-time curation，论文 arXiv:2609.27334《Just-in-Time Memory: Learning to Curate Task-Adaptive Memory for LLM Agents》转译落地，docs/research/2026-10-08-jitmem.md）。论文四步循环（检索→整理→执行→回填）完整进内核 syscall 面：① `laos/jitmem.py` Curator（纯 stdlib）：MemoryStore.recall 检索（零相关预过滤沿用户型 bigram Jaccard）→三分量自适应加权（与 recall 同源 0.7/0.2/0.1 起步，随成败进化）→近重复去重（文本 bigram Jaccard≥0.6 整条丢）→字符预算**整条取舍、绝不截断原文**（top-1 豁免守卫；论文核心主张"再强的检索也只能找回已经缺失细节的摘要"）→kind 分组、section 内时间升序→briefing 文本（≈1.9K tokens 量级对齐论文 payload 预算）；② `mem.curate`/`mem.outcome` 内建 syscall：任务到来时 curate 出 payload（id 即回填句柄）、任务成败 outcome 回填——reward=即时任务成败、时间隔零（论文原样）；③ 训练降级诚实声明：论文 GRPO 8×H200 21–27h → laos 首条优势归因指数 bandit（payload 首条相对候选池均值的分量差为归因信号，全池同质分量差≈0 自动不参与，避免无信息漂移；乘性更新后归一化，登记表封顶 128 最老出队）；规则版 Curator 立论支点=论文自己实证 untrained curator 已打平/超过 write-time 基线（WebShop 61.0 vs 41.0 SR）。与 esp-claw claw_memory 正交（一个治理存储分层、一个治理读取时机）；write-time 质量压缩方向明确不做（论文批评对象）。23 例新增测试，全套 **884 全绿**（861→884，OK skipped=5）
- docs(research): JitMem 笔记复现报告（小红书 2026-10-08 笔记，视频 18 帧）——溯源全 ●证实：Salesforce 系团队（Yefan Zhou/Yang Li/Zeyu Leo Liu/Semih Yavuz/Shafiq Joty），2026-09-23 提交，ALFWorld/WebShop/τ²-bench 超最强基线 +16.2/+16.3/+3.9 绝对成功率点；笔记 4 帧转译零讹变（"Memory abstraction should be late-bound. Store first, interpret when needed."逐字核实）；论文无官方代码仓库（Comments 域空）；LLM Curator 挂 judge/decide 后端 ◐P2 排队（对话管线装配波后评估）。INDEX 登记（83 份）

## [v0.23.0] - 2026-10-08

### Added
- feat(laos): **能力注册表 `laos/caps.py`**——ESP-Claw vs Muse-Gad 复现波次的采纳落地（docs/research/2026-10-08-espclaw-vs-muse-agent-core.md §五）。esp-claw claw_cap.h 取长补短的纯 stdlib 同构件：**caller 四级**（SYSTEM/AGENT/CONSOLE/SUB_AGENT）＋**权限位四枚**（CALLABLE_BY_LLM/EMITS_EVENTS/RESTRICTED/ROOT_AGENT_ONLY，RESTRICTED 拒非 SYSTEM、ROOT_AGENT_ONLY 拒 SUB_AGENT/CONSOLE）＋**状态机含 DRAINING 排空**（in-flight 计数+Condition 等待，drain(timeout) 排空后才 DISABLED）＋**per-session LLM 可见域**（set_llm_visible 全局/session 双层覆盖，tools_for 最小暴露面目录）＋**审计钩子**（每次 call 记 {cap,caller,ok}，CalCap 适配 telemetry a.* 口径）。叙事落位：Agent 调工具=进程调 syscall，能力表=syscall 表的权限位治理。实现修一真 bug：execute() 必须在注册表锁外执行（初版持锁跑用户函数→全部能力调用被串行化+drain 拿不到锁死等，drain 测试当场抓获）。21 例新增测试，全套 **861 全绿**（840→861，OK skipped=5）
- docs(research): **ESP-Claw vs Muse-Gad「Agent 本体能力对比」笔记复现**（小红书 2026-10-07 笔记）。双仓溯源证实：ESP-Claw=espressif/esp-claw（乐鑫官方，Apache 2.0，C/ESP-IDF，MCU 上完整 Agent 闭环）；Muse-Gad=facebookincubator/muse-gadget-sdk（Meta 2026-10-02 开源，ESP32 固件+Linux SDK+88 项 gadget 技能清单）；"Muse Secure-VM 独立 Linux 容器"证实（每用户云 Ubuntu VM）。笔记数字声称 ○未证实×2（拓展坞 8GB/128GB、RESTful 16 Agent 上限）。复现：github 主域克隆三连败（代理拒连/gitclone 502/index-pack 流损坏）→ **api.github.com trees+blobs 通道**（git 凭据 token，89 文件）＋**用户迅雷半成品 zip 抢救**（仅下载 6.2/17.0MB 停滞——本地头自携尺寸，顺序+跳洞解压救出 1053 文件与 GitHub 树逐字节零失配，含 claw_core/src 27 文件完整实现）；**muse Linux SDK 测试套件双环境实跑**（Windows miniconda 142 passed/1 failed/1 skipped——唯一失败=test_identity_persists 的 Unix 0o600 权限断言，Windows st_mode 恒 0o666 环境差异非 bug；WSL Ubuntu-22.04 真目标环境 **167 passed/1 skipped**）；esp-claw 固件构建烧录 BLOCKED（无板无 ESP-IDF，结构级判读七构件对照表收档）。实现级锚点：claw_core 8 相位状态机 :138-454、request_gate 为**循环准入闸**（:174-179）；muse Linux SDK "Muse gets the same access as the account"（无能力分级）与 esp-claw RESTRICTED/ROOT_AGENT_ONLY 形成正面对照=laos 治理面价值主张的独立反证。后续排队：事件规则表（router_rules JSON 热载+DROP/fail_open）P2 对话管线装配、phase 命名对齐/双分区播种 P3 接线波。INDEX 登记（82 份，jev 组 8 份）

## [v0.22.0] - 2026-10-08

### Added
- feat(laos): **判断层 Clef 落地波次**（Cloudflare Clef 学习→实现，docs/research/2026-10-07-cloudflare-clef.md + jev/06 对照篇）。① `laos/decide.py` 决策接口：DecisionSchema(type="noul"|"choice"|"score", options, threshold)＋Decision(answer, probabilities, source, calibrated)（越界拒绝、多键和=1 启发式 1e-6 容差、单键豁免）＋RuleBackend（无命中均匀分布+标注、score 钳制 [0,1]）＋register_backend/get_backend 插拔点；② `laos/calib.py` 校准度量纯 stdlib：brier_score/ece/reliability（4 元组供 ECE 权重重算；BIN_EPSILON 咬合坑值回归——bins=100 的 0.29/0.57/0.58，文档原示例 0.3×10=2.999 实测精确 3.0 系伪坑值已纠正）；③ `drivers/drv_clef.py` clef-flash 驱动（chroot wsl 适配；**wsl.exe argv 空格契约实测钉死**——无空格含逗号参数被劈开剥括号，JSON 默认分隔符带空格构造保证+测试钉住；T1 两硬约束：score 判型输出必须单键、构造 Decision 前 NaN fail-loud 不钳制；CLEF_INFER_SCRIPT 模板含 Qwen3_5 架构门与三判型→Clef question 映射）；④ **clef-flash 权重彩票命中**（HF Cloudflare/clef-flash，Apache 2.0，16 文件 18.1GB 落盘 var/clef_eval）；架构门破局：chroot 内 transformers 4.46.3 无 Qwen3_5（BLOCKED 条件命中）→ 升级 5.10.2+torch 2.14.1 过 import 门（arch_gate_evidence.txt 三段证据链原文未删改）；⑤ **本地实测双宿主**（引用 38.8ms@edgeGPU 与本地实测永不混写）：qemu chroot 加载 19.4s（760 张量全过，单发未取得——宿主内存压力 c10 崩溃，GFLOPS 外推 ≈85min/次）；**x86 WSL 原生 3 判型×20 全量**（第三轮架构=逐判型独立进程；前两轮死于 18GB 模型顶穿 WSL VM）：noul 中位 **33.8s**/choice **32.8s**/score **62.9s**（score 11 档≈2–3 档型的 1.9 倍，实测印证"延迟随选项数线性于 logits 维度"；三型 20 次分布完全一致=CPU 决定性推理）。74 例新增测试（22+29+23），全套 **840 全绿**（766→840，OK skipped=5）
- docs(research): jev/06-clef-mapping.md 对照篇（jev 组第 7 份）——三路线选型表（rules ~0ms 本地实测/edgejev 157.5ms 本地实测/clef-flash 38.8ms **边缘 GPU 引用**）＋非自回归架构定论（决策延迟=一次 prefill，输出空间由 schema options 推理前锁定）＋Brier/RLCD 校准方法库映射（laos 落度量半边，训练半边属驱动子进程域不进核心）

### Fixed
- fix(laos): telemetry 终审修复波（final-review 必修 6 + Important-1 前向勘误）——① v0.21.0 段"9 触发点"勘误为 **10**（六迁移+入队 1+三路径；tag message 不可改，仅前向勘误，GitHub Release body 已同步）；② 节流状态加 `throttle_max_keys=1024` 上限、超限逐最旧端 LRU 淘汰（长跑 (event,module,session) 键无界累积封口，淘汰只丢窗口元数据不丢事件）；③ wakegate `speech_started()`/`barge_in()`/`finish_turn()` 三迁移补发 d.wake.state_change（reason=speech/barge_in/finish_turn，设计 §298 六函数发射点全覆盖；无状态变更的空转不发）；④ `AuditLog.rotate()` 中途异常保底以追加模式重开原文件后原样上抛（审计不断流、代数未变、半途归档残件清除可重试）；⑤ `AuditLog` mode='a' 跨 boot 开机检测文件尾已盖 epoch 换新代续写（同文件 (epoch,seq) 复合键不再跨 boot 重复）；⑥ telemetry.py len 注释归类修正（`*_len`=计数，设计 §1.2 勘误，不再误归"脱敏"级）。13 例新增测试，全套 766 全绿（753→766，OK skipped=5）
- fix(laos): calib 分桶坑值纠正——bins=100 浮点累积真坑值为 0.29/0.57/0.58（文档原称 0.3×10=2.999 实测精确 3.0），eps 咬合回归钉死


## [v0.21.0] - 2026-10-07

### Added
- feat(laos): 埋点核心落地波次——v0.20.0 埋点设计（docs/design/2026-10-07-instrumentation-design.md）的实现首波，三条线全部落地。① **telemetry 核心** `laos/telemetry.py`（纯 stdlib，裸 import 零副作用）：设计 §3 **23 事件全量注册表**（L4/A4/S2/D5/P3/F5；事件字段 130 槽逐字段三档标注明文/计数/脱敏，实现允许表 133 槽 = 设计 130 + 钩子波补注册 use_llm/resume_samples/dropped_ids）；**节流**同 (event,module,session) 键 5s 窗口首条即发、后续静默计数、窗口后首条携带 throttled:N（error/f.rec.bypass/l.sys.init/crash·detect 四豁免永不节流）；**脱敏强制**禁止级字段（明文文本/音频字节/唤醒词）拒发整条事件落 telemetry.reject warn 行，内容类只许 len/sha256 前 8 位/时长/语言码，已注册事件混入未列字段时剥除并落 **telemetry.strip warn 只记字段名不记值**（同键去重防刷屏）；**写盘** .part 追加流逐条 flush + flush 整批并入 + os.replace 原子轮转（64MB 水位触发与保留策略归接线波）；**LAOS_REC=0 联动** a.* 整体静默、s.* 仅 capture 剥内容派生字段、f.rec.bypass 永不静默（禁录态哨兵）；**level=error 事件同步镜像单行 JSON 到 stderr**（§6.4 崩溃现场不依赖文件 survived）。② **10 触发点可选钩子**（wakegate/dialogsched 构造尾参 on_event，默认 None 零行为变化，两生产核不 import telemetry，回调异常吞掉埋点永不影响主链路）：d.wake.state_change 六迁移（wake/turn 放行/sleep_word/max_turns/session_timeout/followup_timeout，统一经 `_transition` 出口、休眠路径先发射后清零拿决策时刻轮数）、d.dialog.turn 入队时刻 phase="queued"（完成态 phase="done" 归装配层接线波，一轮两 phase 消费侧可辨）、d.speculative.cancel 三路径（语音恢复 resume_cancel、§325 必须级 enqueue 清队 latest_only_dropped 逐条 + register_dialog 作废 superseded）。③ **laosweb 轮转安全去重键**：audit.jsonl 轮转后 seq 复位，前端裸 seq 去重会把同号新事件误判重复——`AuditLog.write()` epoch/seq 同点盖章（行内新增 epoch 字段），`rotate()` 轮转原语（gzip 归档 audit-<UTC日期>-<代>.jsonl.gz → 重开空文件 → records 清零 epoch+1），开机扫归档从 max 代+1 续代，PAGE JS 键升级 **epoch|seq|t|tool 复合键**——去重正确性从"概率不撞"变"结构不撞"；diary 等文件侧消费者跨代聚合与 64MB 水位接线为已知后续缺口。56 例新增测试，全套 **753 全绿**（697→753，OK skipped=5）

## [v0.20.0] - 2026-10-07

### Added
- docs(review+design): 上线前评审与埋点设计波次——新文档域 docs/review + docs/design，三份长文档落地。① **需求评审** docs/review/2026-10-07-requirements-review.md：四场景完成度（仅 S2 语音问答达完整体验 ◐）、MoSCoW 全量核对、Go/No-Go（G6 限语音问答完整体验口径 / G8 阻塞运营不阻塞部署）、**上线后问题清单 P01–P15 冻结**（其 §6 → 埋点诊断矩阵行数契约）；② **技术评审** docs/review/2026-10-07-technical-review.md：五层清单、逐模块契约审计（模块测试数全部实跑核对）、**风险与债务表 R1–R11**、ADR×5、四维就绪度 **对话 4.0 / 听觉 3.5 / 治理 4.0 / 可观测性 1.5**——可观测性垫底直接引出 telemetry 实现波次；③ **埋点设计** docs/design/2026-10-07-instrumentation-design.md：**六类 23 事件 / 137 字段**（信封 8+事件字段 129，逐字段脱敏四级标注，内容类只许 len/sha256 前 8 位/时长+语言码）、发射点全图（含风险预留位 R1–R11 呼应）、**P01–P15 诊断矩阵 15 行全覆盖**、voicenpu 上游 metrics 25−2−1=**22 字段**逐项对照（明文 request/response 与纯派生值不入集）。纯文档波次+隐私最小修复，按 README 版本定义"新文档域=MINOR"发版（先例 v0.14.0）；INDEX 第八节+README 交叉登记（79 份）

### Fixed
- fix(mic): P13 隐私补闸——drv_mic mic.record 与 mic.listen_start 双入口新增 LAOS_REC=0 闸（84b5128 同一提交为两条录音路径同时加闸，v0.19.0 时 drv_mic 无任何闸，两闸均系本波新增而非既有；自此"录音只由显式 syscall 触发、LAOS_REC=0 全局禁录"红线在两条录音路径全覆盖），+6 测试，全套 **697 全绿**（691→697）

## [v0.19.0] - 2026-10-07

### Added
- feat(corpus): 语料复用升级波次——v0.18.0 落库的 38 venue / 120,234 行全量语料首次系统性复用，四条线全部落地。① **强命中精炼器** corpus/venue_expansion/curate_strong_hits.py：对 2,103 行 laos 三主线过滤命中逐行标注 strong/strong_terms（多词命中词在 title/abstract 共现即短语级真强），产出可复用工作集 laos_relevant_strong.jsonl **934 行强命中**（audio-speech 771 / agent-os 49 / spatial-privacy 114；771 超出原 42% 弱命中估算系口径差异——短语真强占绝对多数，全文件 attack success=1 属 spatial 水印论文合法保留，audio-speech 侧为 0）；37 例新增测试。② **语料查询 CLI** scripts/query_corpus.py：--topic / --strong-only / --grep（正则宽交替，crossref 多无摘要）/ --stats / --limit / --json 跨 38 venue 文件可复用检索（全扫 123,271 行无损）；20 例新增测试。③ **49 篇治理文献对照** docs/research/2026-10-07-agentos-governance-literature.md + corpus/venue_expansion/agent_os_narrow.tsv：agent-os 窄治理分支 49 篇对 agentos-landscape 八分类零虚构双射，采纳梯度 ●1+●9+◐10+○29，两篇仅标题文按标题论据归类并披露。④ **对话+空间定向检索** docs/research/2026-10-07-dialog-spatial-retrieval.md：audio-speech 四子题 barge-in 4● / KWS 27◐ / VAD 24● / diarization 44○；spatial-privacy 四小类 105+9+0+0=114，speech privacy 0 = 隐私红线背书（录音只由显式 syscall 触发的路线不引入偷听式文献）。⑤ 叙事吸收：agentos-landscape 校验附注、capstone +2、README/INDEX 计数校正（INDEX 各节计数按机械行数对齐，主报告节历史错账一并修正，现共 76 份 / 主报告 33 份）。57 例新增测试（37+20），全套 691 全绿（634→691）

## [v0.18.0] - 2026-10-07

### Added
- feat(corpus): 顶会语料扩展普查波次——38 venue 整卷全量落库 **120,234 行**（ACL Anthology 42,939 = acl 14,599/emnlp 15,349/naacl 5,480/coling 5,676/conll 1,040/tacl 795；Crossref 期刊 19,860（8 刊，tpami 5,323/tmm 4,850/aaai 增量 4,920…；jmlr=Crossref 无缴存 0 行）；Crossref 会议 57,435（16 会，neurips 16,691/iccv 6,491/acmmm 5,383/ijcai 5,964…；pcm=Crossref 无容器名缺口））+ laos 三主线过滤命中 **2,103**（agent-os 880/audio-speech 1,109/spatial-privacy 114，跨文件去重剔 13）——注记：agent-os 宽分支 836 为泛 LLM-agent 论文，**窄治理分支仅 44 篇才是 laos 头条数**；audio-speech 42% 为裸子串弱命中（attack success rate 误标 68）。数据源结构性结论：Anthology bib dump + Crossref ISSN/container 模糊召回双主通道覆盖 36/38 venue；DBLP/OpenReview 实测 JS 反爬、PMLR 无 DOI（icml/iclr=deferred）；icassp/interspeech/asru/slt 为 2026-27 未来窗未缴存（--force 重跑即接）；TASLP 后继刊 ISSN 2998-4173（2329-9290 存量停 2024）；IEEE 三刊 abstract 不向 Crossref 缴存（置 None 是口径非 bug）；TUN 断窗以退避+断点续抓兜底。报告 docs/research/2026-10-06-venue-expansion-survey.md（INDEX 主报告 25→26 份）；61 例新增测试（registry 6 + anthology 14 + crossref 25 + filter 16），全套 634 全绿（573→634）

### Fixed
- fix(corpus): jsonl 写出转义 U+2028/U+2029/U+0085 行分隔符（ijcai 一行 title 内嵌 U+2028 会炸 splitlines 逐行读法；重写后 5,964 行逐行 json.loads 全通过，含回归测试）

## [v0.17.0] - 2026-10-06

### Added
- feat(dialog): voicenpu_engine 复现波次（小红书《RK3576语音系统》→ Gitee bravexyz/voicenpu_engine，AGPL-3.0，13 cpp 全源码通读后的**语义级独立实现**非拷贝）——RK3576 端侧全双工对话引擎的控制面五件全部落进 laos 零依赖主库：① `laos/wakegate.py` 四态唤醒会话机（Sleeping/Listening/Processing/FollowUp，唤醒只由 KWS 音频触发、ASR 文本永不唤醒，休眠词/follow-up 12s/会话 120s/6 轮上限/barge-in）；② `laos/dialogsched.py` 对话调度核（generation 版本化打断——过期代数的回答宁可丢不可播；投机 prefill 窗口——句中停顿 500ms 提前起 LLM、TTS 提交等 commit 窗、语音恢复 ≥96ms×16 采样取消投机轮并"，"合并续说、commit 判定延长 200ms；latest-only 队列；半双工麦克风闸+400ms guard；松散口径声控模式切换；TtsRouter 双后端降级——在线失败且一句未发才降级、句中不换声线）；③ `laos/knowledge.py` 本地知识库短路（UTF-8 符号 bigram、0.7/0.3 双向覆盖打分、子串=1.0、交集≥2 下限、阈值 0.58，命中绕过 LLM；兼容上游 JSONL 格式）；④ `laos/speechchunk.py` LLM→TTS 适配层（流式切句字节级语义：句末标点即切/逗号顿号第 15 字节后才可切/14 字兜底；播报清洗：剥"助手："前缀/<think>/markdown/序号、Qwen→本地语音助手、分号→"，或者"；数字→汉字与时刻"点"归一化）；⑤ tests/test_dialog_e2e.py 五件闭环集成（唤醒→过闸→声控/知识短路/LLM 流→切句清洗→TTS 路由→打断→半双工，9 例，上游真知识库 fixture）。72 例新增测试，全套 573 全绿（501→573）。裁决余量：sherpa-onnx KWS（3.3M wenetspeech+"小乐"拼音词表已拿到）与豆包 wss 协议（帧头 0x11141000 事件码族已记录）留驱动通道；RKNN/ALSA/AEC3 需真机不落地，ASR/TTS 由 laos 既有 funasr/whistle 三通道替身

## [v0.16.0] - 2026-10-06

### Added
- feat(ear): whistle channel landed end-to-end — the needle3 engine discovery (HF Cactus-Compute/needle3 ships all-platform engine binaries incl. windows-x86_64/needle.exe, 1.56MB single file; whistle's designated engine per its config) unblocked Windows-native inference: `needle --model whistle.cact --audio X.wav --audio-language en` → JSON. Official benchmark (SAPI known-text set, Windows CPU native): **whistle en WER 10.8%** (ttft 651ms, ~300 tok/s decode) vs SenseVoice baseline 2.7%/CER 0.0% — zh audio hallucinated as English transliteration (7 langs, no zh, behavior matches config); systematic defects recorded (today→"to day" tokenization splits, British spellings, digit normalization). drv_ear whistle channel upgraded to needle form (LAOS_WHISTLE_BIN/MODEL envs, JSON parsing with plain-text fallback, zh EINVAL guard, 10 tests + real-engine smoke through ear.transcribe at 597ms latency). Verdict locked: laos three-channel ASR — zh main = funasr/SenseVoice, multilingual light = whistle (value = tiny footprint 16.9MB+1.56MB all-platform incl. WASM/Android, not accuracy), HTTP = server. Full suite 496 green

## [v0.15.1] - 2026-10-06

### Fixed
- fix(laos): refiner self-correction upgraded from take-last-segment to **comma-scope discard** (the corrected fragment is the last clause before the marker; head without internal clause boundaries falls back to take-last; overly short tails fall back to original). Official AASR-Bench full set (ModelScope, 917 cases zh 510 / en 407): error rate 0.4571→0.3875 (**-15.2%**), 17 of 18 scenes improved or neutral (zh/explanation -0.649, voice_search -0.180, navigation -0.128), both passthrough scenes zero-damage; the only two positive deltas (en/daily_chat +0.091, zh/academic +0.014 = whole-predicate-replacement corrections) re-confirm the paper's case for a learned Refiner with laos's own data. Official repo audit recorded: 917 + 6,637 rubrics, LLaMA-Factory full finetune (template cpm4), onnx-int4 variant runnable under local onnxruntime. Tests 25 (+2), full suite 495 green

## [v0.15.0] - 2026-10-06

### Added
- feat(ear): AgenticASR reproduction & adoption — laos/refiner.py rule-based AgenticSR Refiner (filler removal with demonstrative preservation, stutter folding zh≥3/en≥2 with 这/那 double-fold exception, self-correction take-last-segment with predicate-guard for "不对/不是", idempotent cleanup; paper arXiv 2607.28175, XHS note login-walled → honest reconstruction from primary sources); drv_ear ear.refine tool + ear.transcribe(refine=True) — the paper's decoupled ASR→Refiner landed as a laos syscall; text-level 13-case error rate 1.083→0.113 (-90%), end-to-end (SAPI TTS disfluent speech → funasr → refiner) CER 1.563→0.042 (-97%); restatement-style corrections proven robust to ASR noise (errors fall in the discarded pre-correction segment); sub-clause replacement kept as documented limitation for the genie learned-refiner channel; 23 new tests, full suite 493 green

## [v0.14.0] - 2026-10-06

### Added
- docs(research): Transformer 效率演进时间线（小红书视频笔记整理）——视频五路取件全失败（App-only+登录墙），按既有预案从可验证来源重构并作诚实声明；三大脉络 少算（稀疏/近似/MoE）→ 少搬（FlashAttention IO 感知/PagedAttention）→ 少存（MQA→GQA→MLA→DSA、int8→FP8）+ 跳出注意力（Mamba→混合架构→DeltaNet 回流），关键节点全部带 arXiv 编号；与 laos 关系全 ○/◐（PagedAttention=OS 分页反哺模型层的方向论印证；端侧 MoE 对 npu 配额按激活口径计价的远期含义）。纯文档波次，按 README 版本定义"新文档域=MINOR"发版（先例 v0.6.0 调研语料库）

## [v0.13.0] - 2026-10-06

### Added
- feat(laos): confidence gate + paired VAD metrics — laos/confgate.py three-band ConfidenceGate (>= local execute locally / >= cloud second-pass verify with cloud_enabled=False privacy default dropping mid-band, never uploading / rest drop; EdgeAI-KWS edge-cloud split as a miniature of the syscall gate chain); laos/vadmetrics.py evaluate_vad (FA/FR/precision/recall/F1 + BG-FAR over foreground-silent∧background-active frames; bg_far_valid = f1 >= f1_floor anti-play-dead gate, Foreground VAD arXiv 2609.19856 metric-pairing principle); 24 new tests, full suite 439 green
- docs(research): four WeChat articles study (EdgeAI-KWS dual-MCU deploy / Foreground VAD / kernel-internals.org / GitHub 2026-09 trend — adoption ●×2 ◐×2 ○×1) + QNN workspace deep study (22GB Explore survey + five key files: vendor ADSP base untouched, SER registered as a SEE virtual sensor resident on SLPI inferring through AP deep-sleep, InferenceServer.kt on 127.0.0.1:8900 is the device-side counterpart of laos npu.infer; rulings A–F); INDEX 18→20 main reports; README test count 415→439

## [v0.12.0] - 2026-10-05

### Added
- feat(duplex+turnpolicy): speech-AI weekly adoption, timing core — laos/duplex.py event-timeline metrics (response latency / barge-in response / overlap ratio / premature-response count; Duplex-MPE four-capability decomposition, JSON-friendly summarize; unclosed intervals and beyond-horizon pairings dropped); laos/turnpolicy.py speak/hold/stop state machine with min-speech/tail-silence/min-hold gates (LateIntent premature-response guard; already-answered turns don't re-trigger); TurnBuffer.interject() head-of-queue frames for delegate results (SALMONN-duo seamless weaving / Context Spanning raw-text injection)
- feat(binaural+foa): spatial primitives — laos/binaural.py Goertzel per-band ILD/IPD binaural cues (SAIL disentangled spatial stream; exact-DFT final combining X = e^(-iω(N-1))·(s[N-1] − e^(-iω)·s[N-2]) verified against direct sum); laos/foa.py plane-wave FOA encode SN3D/N3D + quad-speaker decode + ACN order (Bin2Ambi / RMS-AQA groundwork; ACN first order is W,Y,Z,X, decode gives source-facing max / opposite zero, not exclusive)
- docs(research): speech-AI weekly digest (8 papers: spatial audio ×4 + full-duplex ×4, XHS login wall → arXiv week+theme reconstruction with honest note) + adoption plan + execution notes; 42 new tests, full suite 415 green

## [v0.11.0] - 2026-10-05

### Added
- feat(phone+micgeom): mobile-mcp borrowed features landed — screen.key/longpress/doubletap/devices + new drv_apps driver (apps.list/launch/close, kernel pkg gate extended to apps.*), laos/micgeom.py pure-stdlib MPE (cross-impl diff 0.0 vs numpy reference); adoption statuses updated

## [v0.10.0] - 2026-10-05

### Added
- feat(turnbuf+locks): Pipecat two lessons + unique_lock semantics into core — TurnBuffer (interrupt drops undelivered; commit records only delivered waterline into mem.* with judge passthrough); UniqueLock util + MCPClient._rpc adopts it with protocol-fact lock-lifetime note (adoption items B/C)
- feat(loudness): BS.1770-4 pure-stdlib adoption — K-weight/gated integrated/M/S/LRA + local-peak sinc true-peak; new ear.lufs driver tool (adoption item A from repro wave; calibration anchors -23.00 LUFS / mono -26.0 held)
- feat(docs): laos intro deck x5 — one outline, five PPT skills (ppt-master editable pptx 12p/320 shapes via quality-gated SVG pipeline; guizang Swiss validated deck; frontend-slides terminal-green 16:9 stage + E-key edit; html-ppt blueprint theme + vendored MIT assets + presenter mode; huashu black-gold ledger + 3-direction board); comparison README

## [v0.9.0] - 2026-10-05

### Added
- feat(repro): unique_lock semantics — RAII + early unlock + defer_lock + try_lock + owns_lock (Python contextmanager port of C++ article patterns)
- feat(repro): Pipecat frame-pipeline architecture — SystemFrame/DataFrame split, InterruptionFrame drains queued data while system frames survive, streaming pass-through, aggregator-after-output, HandoffGuard swallow+inject

## [v0.8.0] - 2026-10-05

### Added
- feat(repro): end-to-end SHO runner (sim→features→train→MAE-by-bin artifact) + per-image directivity in ISM (critical: orientation label needs VDP correlate) + four-module smoke aggregator
- feat(repro): PhaseCoder numpy port — exact MPE (GI-DOAEnet Eq.2-3: phase/freq modulation, alpha*r scaling, centroid spherical), mag+phase STFT layout (256/128), (frame,mic) tokenization, hparams meta; aligned line-by-line to cloned JAX source
- feat(repro): ShoNet — paper Fig.1 exact architecture (3xConv+2xBiGRU+2xMHSA+AdaMaxPool, cos/sin head)
- feat(repro): isotropic diffuse-field noise via sinc-coherence Cholesky mixing (2607.02129 §3.1 noise aug)
- feat(repro): pseudo-speech synth + cardioid VDP substitute + STFT phase sin/cos features (2CxTx128) + circular MAE
- feat(repro): Allen-Berkley ISM room sim + 6-mic r=4.5cm circular array + paper-range room sampler (2607.02129 §3.1)
- feat(repro): FxLMS ANC — engine-order reference synth, single-channel (>20dB tonal), LS secondary-path ID, mismatch robustness, coupled 2x2 multichannel (~15dB both error mics)
- feat(repro): BS.1770-4 loudness — K-weighting (48k Annex + parametric dual-path), gated integrated, M/S, LRA, true peak, PLR; fixed in-place K-weight mutation (double-filtering bug caught by idempotence test)
- feat(corpus): wave B v3 — longest-alias container hint unlocks KDD/WWW/WSDM/RecSys/MMSys/ICMR (8.8k papers, 24 yielding venues); ICLR/ICML/JMLR/CoNLL/ECCV/CHiME honest zeros (no Crossref registration)
- feat(corpus): OpenAlex top-up for Crossref-absent venues — ACL/EMNLP/NAACL/COLING real yields, CoNLL honest zero (topic disjoint), CHiME no source
- feat(corpus): multivenue wave A via Crossref backend — speech-adjacent venues rich (SLT/ASRU/WASPAA/TASLP/EURASIP), NLP confs structurally absent from Crossref (ACL Anthology), TACL/CL journals OK
- feat(scripts): multivenue crawler + venue probe (8 resolved) + fuzzy venue_of + opportunistic harvest
- feat(scripts): release helper — semver derivation from conventional commits, three-tree __version__ sync

### Fixed
- fix(corpus): AAAI unlocked via ISSN exact-filter route (600 papers) — relevance ranking drowns AAAI main proceedings; chime honest-zero restored; survey updated (29 yielding venues / 9,908 records)
- fix(scripts): enforce 75s floor on retry path + self-sufficient anti-hijack test

## [v0.7.0] - 2026-09-28

Jev 判断层四闸门 + selfcheck 加固 + 调研资产总纲收束。

### Added

- 可插拔 System-One 判断后端（judge backends）：rule 后端先行，live E2E 实测全链路（autogate 开启时 `rm -rf` 被拒并落 jev 审计）。
- 高危 syscall jev 预审闸门（opt-in）：高风险调用先过判断层裁决再放行。
- jev 过滤的记忆摄入与压缩（opt-in）：MemoryStore 入口与 compaction 均可挂判断闸（JevGatedMemory）。
- 技能蒸馏 jev 质量闸门：任务轨迹升格为可复用技能前先经判断层把关。
- 判断校准台（scripts/judge）：标注集 + 混淆矩阵 + 置信分桶，量化 judge 成色。
- criteria 问句常量：instructions 与 true/false 判据两套问艺模板（源自 jev-chat-jarvis 评估的采纳项）。
- memory `self_check`：JSONL 完整性 + 归一化 + 召回 sanity 三检（模式取自 jev-chat-jarvis KbSelfCheck，MIT）。
- 调研收束三件：Jev System-One 版图（GitHub 778 仓库普查、8 类分类、端上实测 157.5ms 中位——证伪 README 15.6ms 旧口径）、jev-chat-jarvis 评估（拒绝伪装捕获红线，采纳校准/问艺/自检）、laos 落地总纲 capstone（全部调研资产按"来源→可取之处→落点→状态"映射为 59 份文档的主索引）。

### Changed

- README 测试计数对齐至 288（判断层并入后 253→288），判断层参数口径措辞同步修订。

### Fixed

- JevGatedMemory 的 judge 转发缝隙收敛，live E2E 验证通过（rule 后端 + autogate + rm-rf 拒绝带审计）。
- selfcheck 两轮加固：先显式化 bad-line 丢弃副作用（docstring + stderr 警告）并容忍非标量 id；随后措辞精确化（仅不可解析行被移除）且 `_next_id` 容忍损坏记录（live 发现的 KeyError）。
- 收尾杂修：autogate/rule 后端警告、校准台退出码、版图条目相邻锚点。
- capstone / INDEX 计数与一致性修正：59 份文档总数对账、优先级一致、§G 与 README 对账、三棵树路径前缀、第 4 状态锚点。

## [v0.6.0] - 2026-09-18

调研语料库波次：19,792 篇双会议论文 + 3,724 个 OSS 仓库 + 分域模型地图。

### Added

- 19,792 篇统一论文语料库：ICASSP 2022–2026 五年全量 14,285 篇 + Interspeech 五年全量 5,507 篇（ISCA 档案逐篇枚举，回填 1,069 篇摘要、89.1% 成功率），统一语料带验证器。
- OSS 版图：GitHub 音频/AI/Agent 仓库遍历 3,529 个，去噪 + 回填后 3,724 个清洁仓库（2,153 清洁 + 1,571 回填），14 类分类 + laos_fit 映射。
- 语料工具链：ICASSP Crossref 枚举器（offset 分页 + DOI 前缀过滤）、GitHub 仓库爬虫（引号短语搜索）、研究表格共享 markdown lint。
- 语音情感（SER）分档地图：edge / small（<30M）/ medium（30M–500M）/ large + 语音 LLM / multimodal 五轴，附交叉表、决策树与 HTML 全景；多模态轴裁决"不引入视觉模态"。
- 语音前沿逐篇跟踪：说话人 / 前端 / 编解码-TTS / 副语言 51 篇（2024–2026），映射到 laos 用户可感知功能。
- AlwaysOnRec-ZCode 隔离区语音前沿增量：PCEN VAD 前端、envelope-DTW 唤醒词（含易混淆词）、opt-in 音频归档、ear.assess 发音韵律评估、合规红线章节（279 测试全绿）。
- 研究地图与索引：常开录音"漏斗 × 模型能力"路线图（含合规红线）嵌入 README 第 10 节，附研究索引与 2026-09 修订日志。

### Changed

- 五年遍历报告定稿：主题矩阵改为从源文件重算（ICASSP 的 jsonl 标签已损坏、不可信）。

### Fixed

- SER 档位表补正：SALMONN-7B/13B 遗漏行按裁决 3 记为 A 档。

## [v0.5.0] - 2026-09-11

常开录音内核能力 + 双沙箱并行推进 + 情感/事件模型地图。

### Added

- 麦克风能力阶梯：listen / record / transcribe / always_on 四级内核能力，逐级授权。
- 常开录音模式：环形缓冲 + 回溯（rewind）；drv_rec Opus 编码（带回退链）+ 存储配额。
- 双沙箱并行落地 Apple 基准增量：AlwaysOnRec-Trae 实现能力阶梯 / Opus 编码 / 常开模式三件，AlwaysOnRec-ZCode 隔离区实现 journal 标题 schema 与 mic `time:` 窗口作用域（261 测试全绿）。
- 模型地图两份：SER 边缘-小-中-大-多模态五分类选型映射；音频事件识别（AED）+ AGC/语音增强五分类（以 DCASE'25 冠军 61.5% @122K 参数的蒸馏范式为端侧锚点，README 现有口径）。

### Fixed

- 常开录音调研报告终审修订（final review fixes）。

## [v0.4.0] - 2026-09-11

听觉 + 记忆 + 日记波次，手机五层感官驱动，强制层 OSAL 化。

### Added

- 听觉双驱动：drv_mic 显式录音（每次调用写 `event:mic` 审计）+ drv_ear SenseVoice 双通道转写。
- MemoryStore 情景记忆 + `mem.*` 内建 syscall；每日日记（audit + memory 整合沉淀）与 laosweb 记忆 / 日记面板。
- 手机五层感官驱动波次：drv_screen（adb + uiautomator 屏幕理解与操控，pkg 作用域）、drv_genie 双后端 LLM（QAIRT Genie / OpenAI 兼容）、drv_notify + drv_comms、drv_battery + 电池感知动态电力定价（风险乘数）、drv_events（端上传感写入记忆）。
- 常开音频链路：零依赖流式 VAD（批 / 流一致性）→ drv_rec VAD 门控录音会话 → journal 管线（批量 ASR 分段入记忆、自动 GC）→ 日记"五、今天听到的"段落 + 每周心情报告。
- 技能库：成功任务轨迹蒸馏为可复用技能。
- 强制层 OSAL 化：linux / stub / android 三后端（含 Termux 检测）经 `LAOS_ENFORCEMENT` 运行时选择。
- drv_npu 真机闭环：adb 设备传输层 + runbook；drv_audio 语音分离 / 回声消除（FLASepformer + JAEC AEC）+ RTX 4060 GPU 基准（线性复杂度验证）。
- 调研波次：常开录音全景（产品 / OSS / 论文 / 功耗 / 隐私，21 篇论文归档 + arXiv 工具 + HTML 交付）、垂直应用与 Apple Watch S12 音频智能。

### Changed

- 强制层重构为 OSAL 骨架（linux / stub 后端原样迁移），多平台后端可插拔。

### Fixed

- 记忆与监听加固：MemoryStore 原子重写（temp+replace）、mic 拒绝时补写审计、监听线程加固。
- 架构图重叠修复：容器标签固定置顶，audit / enforcement / adb 连线改走空白边距。

## [v0.3.0] - 2026-09-09

laosweb 交互控制台 + NPU 驱动。

### Added

- laosweb 交互端点：confirm 队列 / restart / kill / operator msg。
- laosweb 控制台：确认横幅、重启、终止、操作员消息四类操作落地。
- drv_npu 驱动：QNN 后端探测 + 计价推理，接入 demo act 4.6。
- 调研：QNN / ADSP 真机集成路线研究（A / B / C 三条路）。

### Fixed

- laosweb confirm 不再读 stdin——面板场景默认拒绝（dashboard-safe default deny）。
- 控制台交互两轮评审加固：fail-safe 重启、killed 状态守卫、调度器锁、double-get 修复。
- laosweb v2 计划文档 fence 配对与接口契约修正。

## [v0.2.0] - 2026-09-05

内核强制层与语义扩展大波次：seccomp / CoW / eBPF / FleetLedger / MCP Tasks / 信箱 / laosweb。

### Added

- seccomp BPF 系统调用强制：纯 Python 零依赖 BPF 汇编器，接入驱动 spawn 全链路（含 cgroup 集成）。
- CoW 文件系统隔离：原子 temp+replace 原语、硬链接 COW fork（零数据拷贝）、inode 快速 diff，覆盖驱动写入 / 追加路径。
- eBPF 系统调用画像：bpftrace 后端（可选，缺依赖时优雅降级），接入 demo 与 `laosctl prof`。
- FleetLedger 不可逆风险账本（Irreversibility Budget 2.0）：加权风险记账、每 Agent 风险上限、带舰队风险储备的 spawn 准入控制、`laosctl budget` 台账回放。
- 陈旧上下文检测：上下文观察簿 + 内核失效接线 + Agent 循环通知注入与提交钩子。
- AgentProf 语义画像：审计流 span 构建与启发式归因、OTLP / JSON 导出契约，接入 demo 与 laosctl。
- 内核语义扩展套件：双向 MCP 请求（elicitation）+ MCP Tasks 异步工具调用（客户端轮询）、信箱 IPC `msg.send/recv/list` 内建 syscall（配额契约）、运行时能力委托（TTL + 可撤销）。
- 调度语义与面板：每 Agent 可靠性预算（Patient Bytes）+ 意图驱动 task_scope 路径收窄 + laosweb 实时仪表盘（状态 API + 面板页）。

### Fixed

- seccomp 两轮修复：勘误 pivot_root / finit_module 的 x86_64 系统调用号；unshare 之后经 bootstrap shim 安装 seccomp（含 shim 测试断言与架构守卫）。
- 驱动 PID 与审计修正：cgroup / 画像取真实驱动 PID、E2E 加固、mount API denylist 收口；固定测试环境旋钮、risk_cap 在 fork_child 传递、EDQUOT 判定先于风险闸。
- 观测与调度修复：span 计时改用审计 t（每调用粒度，R206）、暂停 Agent 的调度等待上界（R307）、task_scope 路径匹配遍历加固。
- laosweb 稳定性：面板原地刷新（消除每 tick 重复渲染）、内核状态无锁快照读（ctx 副本 + audit seq）。

## [v0.1.0] - 2026-09-04

基线：内核 + 强制层骨架 + 研究文档基线。

### Added

- 用户态薄内核 laosd 语义层骨架：进程表、能力表、驱动路由、审计（kernel / agent / brain / scheduler / sandbox / mcp 等 9 个模块）；不改内核，用 namespace / cgroup / seccomp / landlock 做强制层。
- 首批驱动与工具：drv_fs / drv_proc / drv_sys 三驱动 + laosctl 控制台；零第三方依赖，macOS / Windows 自动降级为"仅能力表"。
- 研究与测试基线：AgentOS 版图、AIOS 深读（docs/research）+ 回归测试起步，全仓 149 个文件。
