# laos 埋点设计（2026-10-07）

> **评审对象**：laos v0.19.0（主库 691 项测试实跑通过；页脚总数 1041 = 691 + 隔离区 279 + 复现区 71）。
> **本文角色**：上线前评审波次（Task 3）核心交付——事件分类学、统一 schema、发射点清单、问题→埋点诊断矩阵。本文件是 `laos/telemetry.py`（下一实现波次）的实现规格。**交付口径（消费侧）**：依赖装配层或未接线发射点的事件（`d.dialog.turn`/`d.mic.guard`/`f.tts.fallback`/`a.device.reopen` 等）在接线前存在空窗——§5 矩阵判定逻辑已按"空窗=已知未接线、非新故障"口径区分（P01①/P07/P09/P11），消费方照此读表。
> **输入契约（三份冻结源）**：
> 1. 需求评审 §6 问题域清单 P01–P15（docs/review/2026-10-07-requirements-review.md，编号冻结）——诊断矩阵逐条消费；
> 2. 技术评审 §4 风险表 R1–R11（docs/review/2026-10-07-technical-review.md，编号冻结）——发射点覆盖面与"预留位"标注源；
> 3. voicenpu 上游 metrics 字段口径（docs/research/2026-10-06-voicenpu-adoption.md §二；字段全集已对 var/repro/voicenpu_engine/src/scheduler/dialog_controller.cpp:387-418 源码复核，见 §7）。
> **隐私红线（最高约束，继承需求评审 §4.3 第 7 条）**：埋点默认不采集音频内容与转写文本明文；内容类只允许长度/哈希前 8 位/计数/时长/语言码；挂既有审计流（`event:"mic"` 联动语义），不开新后道；`LAOS_REC=0` 时音频内容类埋点同步静默。
> **数字口径**：本文全部数字取自仓库既有实测/源码实取（引用处逐一标注文件:行号），未实测维度明写"未实测"。

---

## §1 设计原则（五条，红线落法）

### 1.1 本地优先：默认 JSONL 落盘，无云端

- 埋点事件全部落在 laosd workdir 下的既有审计文件（`audit.jsonl`），**不引入任何网络发射路径**（无 OTLP / HTTP 上报默认值；profiling.py 的 eBPF/OTLP 通道是独立能力面，不经本设计触碰）。
- 与需求评审 Won't 表 W1（云端默认上传）对齐：任何外发仅显式 opt-in 且永不默认；本设计不定义外发接口。
- 落盘即终点：消费方（laosweb 面板 / laosctl 查询 / 人工 jq）从本地文件读。

### 1.2 计数优先于内容：逐字段脱敏分级

每个事件字段表（§3）逐字段标注**脱敏级别**，四级：

| 级别 | 语义 | 允许的字段形态 |
|---|---|---|
| **明文** | 无隐私面：标识符、计数、时延、配置值 | turn_id、ms 值、阈值、布尔 |
| **计数** | 只记次数/数量，不记内容 | tokens、hits、lines、`len`（字节数/字符数，`*_len` 字段族）、过程时延 ms 值（`latency_ms`/`retrieval_ms`/`session_ms` 等） |
| **脱敏** | 内容的不可逆派生 | `sha256(text)[:8]`（记作 `*_sha8`）、内容时长（秒/毫秒：`duration_ms`/`start_ms`/`duration_sec`）、语言码（BCP-47 短码如 `zh`/`en`） |
| **禁止** | 红线：永不入事件 | 音频字节、转写文本明文、refine 前后文本明文、唤醒/休眠词命中原文 |

**内容类字段只允许三种形态：len / sha256 前 8 位 / 时长+语言码**（需求评审 §4.3#7 原文落法）。凡来源函数接触文本/音频的发射点，字段表末尾显式列"禁止对照行"，供自查与代码评审对照。

> **len 级别勘误（2026-10-07 统一，以 `laos/telemetry.py` `EVENT_FIELDS` 注册表实态为准）**：`*_len` 字段族（`text_len`/`in_len`/`out_len`/`utter_len`）=**计数**（数量语义）；内容时长（`duration_ms`/`start_ms`/`duration_sec`）=**脱敏**（内容派生语义）；过程时延（`latency_ms`/`retrieval_ms` 等 ms 值）=**计数**。§3.2–3.7 字段表与本表按此对齐。

### 1.3 挂既有审计流：复用 audit 通道，不新开后门

- 埋点事件经 `laos/kernel.py AuditLog.write()`（kernel.py:134-142）写入同一 `audit.jsonl`：**逐条 `seq` 盖章 + 逐条 flush** 语义原样继承——不建第二个写通道、不建旁路 socket、不给驱动子进程直写审计文件的权限。
- 驱动子进程（drv_ear/drv_mic/drv_rec，独立解释器）**不直接持有审计句柄**：驱动把脱敏遥测字段放进工具返回 JSON（drv_ear 统一出口 JSON 已含 `latency_ms`，模式同源），内核在 `syscall()` 派发尾部按工具名前缀转写为 `s.*`/`a.*` 事件——与 `event:"mic"` 的尾部追写模式（kernel.py:560-563 / kernel.py:757-759）同构。
- 与 `event:"mic"` 的联动：录音类遥测（`a.vad.endpoint` 等）只描述段级计数，**放行/拒绝的追责语义仍唯一归属 `event:"mic"`**；遥测事件不重复记 pid/agent 归责面。
- 既有事件名（`syscall`/`mic`/`jev`/`driver_load`/`spawn`/…）一概不改；新分类学事件用 `l./a./s./d./p./f.` 前缀命名，天然不与既有名冲突（技术评审 §2.3"未知字段宽容"演化路径）。

### 1.4 节流必设：同类事件 5s 节流，防风暴

- **默认窗口 5s**（本设计定值），节流键 = `(event, module, session)`；窗口内首条立即发射，后续静默计数，窗口后首条携带 `throttled: N`（被压制条数）。
- **豁免清单**（永不节流）：`level=error` 的一切事件、`f.rec.bypass`（红线断言，压一条都算丢证据）、`l.crash.recover` 的 `phase=detect`、`l.sys.init`。
- 防风暴对象：`a.mic.frame_overrun`（P15 overrun 风暴本身会高频触发，上游自愈语义"清队列+reset ASR"循环反复）、`a.mic.stream_error`/`a.device.reopen`（P09 断连重试循环）、`d.mic.guard`（每 100ms 音频块一次的 allow() 查询，dialogsched MicrophoneGate 调用频率）。
- 设计动机学上游：上游 overrun 自愈语义（voicenpu 采纳报告 §二"锁-free SPSC 环形队列，overrun 自愈=清队列+reset ASR"）在无节流观测下自身就是事件风暴源——**观测不得成为故障放大器**。

### 1.5 `LAOS_REC=0` 联动：禁录时音频内容类埋点同步静默

- `LAOS_REC` 读取口径与现有闸门一致（`os.environ.get("LAOS_REC", "1") == "0"`，drivers/drv_rec.py:91）。
- 静默规则（按事件与字段的"内容派生"属性，非一刀切）：

| 范围 | `LAOS_REC=0` 时行为 |
|---|---|
| `a.vad.endpoint`、`a.mic.*` | **静默**（只可能来自常开采集路径，禁录时不应有任何采集活动） |
| `s.asr.result` / `s.refine.delta` 的内容派生字段（`audio_sha8`/`text_sha8`/`*_len`/`duration_sec`） | 仅当 `source="capture"`（常开采集转写）时静默；`source="file"`（显式 `ear.transcribe` 用户提供文件）照发——ASR 全本地与禁录是两条红线，互不扩大 |
| `d./p./f./l.` 计数与调度语义 | 照发（禁录不禁调度与性能观测） |
| `f.rec.bypass` | **永不静默**（它就是禁录态的哨兵） |

- 实现位：`laos/telemetry.py` 的 emit 入口统一判定（§4 发射点表"REC 联动"列逐事件标注）。

---

## §2 事件分类学（六类，23 事件）

事件名 = `<类字母>.<域>.<名>`（如 `d.dialog.turn`）。类字母小写前缀是命名空间，防与既有审计事件名冲突。

### L — 生命周期（4）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `l.sys.init` | laosd 启动快照：版本/解释器/驱动数/禁录态/ASR 通道 | info | 每次启动 1 条 |
| `l.driver.load` | 驱动加载结果（含听觉解释器探测链结果，R11） | info / fail→warn | 每次 load_driver 1 条 |
| `l.driver.unload` | 驱动卸载 | info | 每次 1 条 |
| `l.crash.recover` | 崩溃检测与恢复（detect / recovered 两相位，P11） | warn / error | 异常路径 |

### A — 音频链路（4）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `a.mic.frame_overrun` | 音频队列 overrun 计数（P15；学上游清队列+reset 自愈语义的观测位） | warn | 风暴路径，节流 5s |
| `a.device.reopen` | 设备断连自愈重开（P09；学上游 USB ENODEV close+200ms 重开循环） | warn | 异常路径，节流 5s |
| `a.vad.endpoint` | VAD 端点闭合（一段有声段结束）：段级时长/阈值，不落音频 | info | 每有声段 1 条，节流 5s 聚合 |
| `a.mic.stream_error` | 采集流错误（设备占用/拔出等，drv_mic 现有 `_listen_error` 落点的结构化） | warn | 异常路径，节流 5s |

### S — 语音服务（2）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `s.asr.result` | 每次 ASR 转写的脱敏指纹：通道/语言/时长/延迟/文本哈希（**cer 本地无 ref 无法在线算→记 duration+lang+哈希**，WER 侧车字段留给离线评测回灌） | info | 每次转写 1 条 |
| `s.refine.delta` | refiner 修正增量：**只记 delta 计数与前后哈希，不记文本**（R5：线上替换率可观测） | info | 每次 refine 1 条 |

### D — 对话调度（5）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `d.dialog.turn` | 对话轮汇总（吸收 voicenpu 22 字段口径，§7）：路由/分段延迟/打断/投机/合并 | info | 每轮 1 条 |
| `d.wake.state_change` | WakeGate 四态迁移：from/to/reason（P01/P02/P06） | info | 每次迁移 1 条 |
| `d.barge_in` | 打断：代数递增与打断来源（P05） | info / 拒绝→warn | 每次打断 1 条 |
| `d.mic.guard` | 半双工麦克风闸触发/释放（R4：AEC 接线后记 aec_ready 翻转） | info | 节流 5s |
| `d.speculative.cancel` | 投机轮取消（resume 判定 / latest-only 丢弃 / 被新轮作废，P14） | info | 每次取消 1 条 |

### P — 性能（3）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `p.rtf` | 实时率分位聚合（rtf = wall/input，上游 ASR 侧 rtf 口径的聚合版） | info | 默认每 16 次转写或 5min 1 条 |
| `p.memory` | 进程 RSS 采样（纯 stdlib 双平台探测；P10） | info | 默认 60s 1 条 |
| `p.jsonl.water` | JSONL 水位：audit/memory 行数与字节（R10：无界增长观测位） | info | 默认 10min 1 条 |

### F — 降级与故障（5）

| 事件 | 语义 | level | 频率预期 |
|---|---|---|---|
| `f.tts.fallback` | TTS 在线→离线降级（句中不换声线保护触发同记，P07；R3 降级语义先行） | warn | 每次降级 1 条 |
| `f.asr.channel_fail` | ASR 通道失败（funasr/server/whistle 各自错误，P03/P08） | warn/error | 每次失败 1 条 |
| `f.model.load_fail` | 模型加载失败（SenseVoice 路径/whistle 引擎/NPU 模型，P08） | error | 每次失败 1 条 |
| `f.rec.bypass` | 禁录断言命中：`LAOS_REC=0` 下出现放行的 `event:"mic"`（P13，红线级，永不节流） | error | 违例时 |
| `f.audit.gap` | 审计对账缺口：派发计数 vs 落盘行数差（P12，红线级） | error | 对账周期发现缺口时 |

---

## §3 统一 schema

### 3.1 行信封（envelope）

埋点事件是 `audit.jsonl` 里的一行 JSON，信封字段如下（与既有 `AuditLog.write()` 兼容：`seq` 由 write() 盖章，kernel.py:139）：

```json
{"t": 1760000000.123, "ts": 45678.901, "seq": 1042,
 "event": "d.dialog.turn", "level": "info", "module": "dialogsched",
 "session": "a3f9c1d2", "fields": {"...": 0}}
```

| 信封字段 | 类型 | 脱敏级别 | 说明 |
|---|---|---|---|
| `t` | float（wall 时钟，epoch 秒） | 明文 | 既有审计行惯例（kernel.py 各 write 点均带 `t`） |
| `ts` | float（**monotonic 毫秒**） | 明文 | 单调时钟，跨行差值即真实时延，不受 NTP 跳变影响（`time.monotonic()` 换算 ms） |
| `seq` | int | 明文 | AuditLog 盖章，== records 下标（防前端去重漂移，kernel.py:135-139 原语义） |
| `event` | str | 明文 | `<类字母>.<域>.<名>`，见 §2 |
| `level` | str | 明文 | `info` / `warn` / `error`（error 永不节流） |
| `module` | str | 明文 | laos 模块名（`kernel`/`dialogsched`/`wakegate`/`drv_ear`…） |
| `session` | str | 明文 | 会话 id：WakeGate 会话 uuid 前 8 hex；无会话语境（启动期/采样器）用 `boot` + 启动计数。**非用户标识**，不携带主机名（`LAOS_PRIVACY_MASK=1` 语义继承，drivers/drv_sys.py:23） |
| `fields` | object | 表级控制 | 每事件字段表见 3.2–3.7，逐字段脱敏级别 |

节流元字段（仅节流窗口后首条出现）：`throttled`：int（计数级，窗口内被压制条数）。

### 3.2 L 类字段表

**`l.sys.init`**（发射点：bin/laosd.py `boot_kernel()` 返回处）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `version` | str | 明文 | `laos.__version__`（laos/__init__.py:18，"0.19.0"） |
| `py_exec` | str | 脱敏（路径，按 `LAOS_PRIVACY_MASK` 掩码用户名段） | `sys.executable` |
| `platform_masked` | str | 脱敏 | `platform.platform()` + 掩码（drv_sys.py MASK 同款语义） |
| `drivers` | int | 计数 | `len(kernel.drivers)` |
| `rec_enabled` | bool | 明文 | `os.environ.get("LAOS_REC","1") != "0"` |
| `asr_channel` | str | 明文 | `LAOS_ASR_CHANNEL`（默认 funasr，drivers/drv_ear.py 文件头） |
| `ear_python_source` | str | 明文（枚举 `env`/`conda`/`fallback-main`） | bin/laosd.py:163-165 探测链结果 |
| `boot_count` | int | 计数（workdir 下 boot 标记文件累计） | telemetry 维护 |

**`l.driver.load`**（发射点：laos/kernel.py `load_driver()` 现有审计写入处 kernel.py:297-306，增发分类学行；旧 `event:"driver_load"` 行保留）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `driver` | str | 明文 | `name`（load_driver 形参） |
| `tools` | int | 计数 | `len(client.tools)` |
| `ok` | bool | 明文 | 加载是否成功（异常路径 level=warn） |
| `err` | str | 明文（errno 风格错误串，无内容） | 异常 `str(exc)` 截断 120 字符 |
| `interpreter_source` | str | 明文（枚举） | 听觉驱动解释器探测（bin/laosd.py:163-165） |
| `channels_available` | list[str] | 明文 | `ear.status()` 通道可达集（drv_ear `status` 工具；R11：探测失败=能力静默变窄，此字段使其面板可见） |
| `driver_pid` | int | 明文 | `client.driver_pid` |

**`l.driver.unload`**（发射点：kernel.py `unload_driver()` kernel.py:315 既有行增发）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `driver` | str | 明文 | 形参 |
| `reason` | str | 明文（`shutdown`/`error`） | 调用方语境 |

**`l.crash.recover`**（发射点：detect = kernel.py `syscall()` 驱动异常路径 kernel.py:526-527；recovered = 预留重启逻辑，见 §4）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `driver` | str | 明文 | `driver_name` |
| `phase` | str | 明文（`detect`/`recovered`） | 状态机 |
| `err` | str | 明文（errno 串） | `str(exc)` 截断 |
| `uptime_s` | float | 计数 | `time.time() - kernel.boot_at` |
| `restarts` | int | 计数 | telemetry 累计 |

### 3.3 A 类字段表

**`a.mic.frame_overrun`**（发射点：预留——drv_rec.py `on_audio` 回调的 PortAudio status 溢出位（当前形参被忽略，drv_rec.py:99-101）+ 未来 SPSC 队列；对应 P15，上游自愈语义已入档）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `queue` | str | 明文（`spsc-audio`/`spsc-result`/`portaudio`） | 队列标识 |
| `overruns` | int | 计数 | 环形队列 overrun 计数器（学上游锁-free SPSC） |
| `dropped_frames` | int | 计数 | 清队列丢弃帧数 |
| `recovered` | bool | 明文（是否执行了 reset ASR 自愈） | 自愈路径 |

**`a.device.reopen`**（发射点：预留——音频前端自愈位（学上游 USB ENODEV close+200ms 重开循环，voicenpu 采纳报告 §二"设备自愈"）；对应 P09 / 技术评审 §5.2 盲区）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `device` | str | 脱敏（设备名，掩码序列号段） | 声卡枚举 |
| `attempt` | int | 计数 | 重开循环第 N 次 |
| `backoff_ms` | int | 计数 | 上游语义 200ms（采纳报告 §二） |
| `err` | str | 明文（errno 串：ENODEV/EPIPE/ESTRPIPE/EIO） | ALSA/PortAudio 错误 |
| `ok` | bool | 明文 | 重开是否成功 |

**`a.vad.endpoint`**（发射点：drv_rec.py `on_audio` → `laos/vad.py StreamingVAD.feed()` 返回段时（vad.py:125）；REC=0 静默，§1.5）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `duration_ms` | int | 脱敏（时长） | `len(wav)/2 / sr * 1000`（16k PCM16） |
| `start_ms` | int | 脱敏（时长） | feed 返回的 `start_ms`（段相对流起点） |
| `threshold_dbfs` | float | 明文 | StreamingVAD 构造参数（drv_rec rec_start 默认 -35.0） |
| `sr` | int | 明文 | 16000（drv_rec.py:32 SAMPLE_RATE） |
| `source` | str | 明文（`rec` 常开采集） | 发射语境 |
| （禁止对照）音频字节 `wav` | bytes | **禁止** | feed 返回值中的 wav 只可落盘走 rec_gc 6h 即焚（drv_rec.py:158），**永不入遥测** |

**`a.mic.stream_error`**（发射点：drv_mic.py `_listen_loop` except 路径（drv_mic.py:122-123，现有 `_listen_error` 字符串的结构化）；经 mic.status 或内核尾部转发，见 §4）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `err` | str | 明文（errno 串截断） | `str(exc)` |
| `phase` | str | 明文（`open`/`read`/`flush`） | 异常所在段（drv_mic.py:110/122/139） |
| `device_hint` | str | 脱敏 | `sd.default.device` 探测结果掩码 |

### 3.4 S 类字段表

**`s.asr.result`**（发射点：drivers/drv_ear.py `transcribe` 统一出口 JSON（文件头契约：`{"text","language","emotions","source","latency_ms"}`）增补脱敏遥测字段，内核 `syscall()` 尾部按 `ear.*` 前缀转写——`event:"mic"` 尾部追写同款模式 kernel.py:560-563；REC=0 且 source=capture 时静默，§1.5）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `channel` | str | 明文（funasr/server/whistle） | `LAOS_ASR_CHANNEL` 生效通道 |
| `ok` | bool | 明文 | 转写成败 |
| `lang` | str | 脱敏（语言码：`zh`/`en`/…， SenseVoice 标签解析产物） | `_parse_tags`（drv_ear.py:127-133） |
| `latency_ms` | float | 计数 | 统一出口既有 `latency_ms`（文件头契约） |
| `duration_sec` | float | 脱敏（音频时长） | 输入 wav 时长 |
| `audio_sha8` | str | 脱敏（输入音频字节 sha256 前 8 位） | telemetry 侧对输入文件流式摘要 |
| `text_len` | int | 计数（终稿字符数） | `len(text)` |
| `text_sha8` | str | 脱敏（终稿文本 sha256 前 8 位） | sha256(text)[:8] |
| `emotions_n` | int | 计数（情感标签数；不记标签值——情感属内容派生） | `len(emotions)` |
| `endpoint_to_final_ms` | float | 计数 | 端点→终稿延迟（上游 ~88ms 锚点对照位；funasr 非流式=整段口径，whistle=ttft 口径 651ms 实测，docs/research/2026-10-06-cactus-whistle-adoption.md） |
| `source` | str | 明文（`file`/`capture`） | 调用语境（ear.transcribe 显式文件 / 常开管线） |
| `req_lang` | str | 明文（调用方请求语言参数，与 `lang` 出入=语言误判信号，P03） | transcribe 形参 |
| （禁止对照）`text` 明文 / 音频字节 / `emotions` 标签值 | — | **禁止** | 统一出口 JSON 的明文字段只在 syscall 返回值与 audit 既有 `result` 截断（kernel.py:507，既有语义不因本设计扩大）中存在，**遥测事件永不携带** |

> **WER 侧车说明**（brief 口径）：线上无 ref 文本，CER/WER 无法在线计算——laos `wer.py` 只做离线评测。故在线只记 `duration+lang+哈希`；离线评测回灌（AASR-Bench 917 例管线）可用 `audio_sha8` 对齐线上样本，把线下 WER 标注拼回时序——字段位为此预留。

**`s.refine.delta`**（发射点：laos/refiner.py `refine()` 返回处（refiner.py:101）经 telemetry sink；**只记 delta 计数不记文本**——brief 红线）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `in_len` / `out_len` | int | 计数（修正前后字符数） | `len()` |
| `in_sha8` / `out_sha8` | str | 脱敏（前后文本 sha256 前 8 位，供跨事件对齐） | sha256[:8] |
| `hits_filler` | int | 计数（语气词剥除命中） | `_strip_fillers`（refiner.py:50） |
| `hits_stutter` | int | 计数（口吃折叠命中，zh/en 分计并入此字段族） | `_fold_stutter_zh/_en`（refiner.py:61/68） |
| `hits_correction` | int | 计数（子句级替换修正命中——R5"替换命中计数"落位） | `_resolve_correction`（refiner.py:77） |
| `changed` | bool | 明文 | 前后哈希是否不同 |
| （禁止对照）修正前后文本明文 / 被替换子句原文 | — | **禁止** | R5 缓解建议原文即"内容脱敏"："记录 refine 前后文本哈希与替换命中计数" |

### 3.5 D 类字段表

**`d.dialog.turn`**（发射点：装配层在轮完成/取消时拼装——上游 `writeMetrics` 语义；laos 侧原型 = tests/test_dialog_e2e.py:146 的 `self.metrics.append({...})` 行。字段吸收 voicenpu 22 字段口径，逐字段对照见 §7）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `turn_id` | int | 明文 | `DialogQueue._next_id`（dialogsched.py:241） |
| `phase` | str | 明文（`queued`/`done` 两态） | 裁决（2026-10-07，一轮一条契约）：`DialogQueue.enqueue()` 成功入队即发 `phase="queued"`（dialogsched.py:299-303 最小发射点）；轮完成/取消时由装配层拼装发 `phase="done"`（接线波） |
| `route` | str | 明文（`knowledge`/`llm`/`tts`/`none`） | 装配层路由决策（上游 route 口径；e2e 测试同款取值） |
| `knowledge_id` | str | 明文（知识条目 id 或空） | `KnowledgeRetriever.search` 命中（knowledge.py:116） |
| `knowledge_score` | float | 明文（bigram 得分，阈值 0.58，knowledge.py:117） | 同上 |
| `retrieval_ms` | float | 计数 | 检索耗时（上游同名口径） |
| `ok` | bool | 明文 | 轮成败（上游 success） |
| `interrupted` | bool | 明文 | 该轮是否被后续代打断（P05 判定主字段） |
| `generation` | int | 计数 | 轮入队时的代数快照 |
| `first_text_ms` | float | 计数 | 轮起点→LLM/知识首文本 |
| `first_audio_ms` | float | 计数 | 轮起点→TTS 首音（TTS 合成后端缺位 R3 期间记 null——降级形态文字输出时此字段空即证据） |
| `prefill_ms` | float | 计数 | 投机 prefill 耗时（无常驻 LLM 通道时 null，预留） |
| `generate_ms` | float | 计数 | 生成耗时 |
| `tokens` | int | 计数 | 生成 token 数 |
| `total_ms` | float | 计数 | 轮总耗时 |
| `pause_observation_ms` | int | 计数 | `PauseWindow.observation_ms`（默认 500，dialogsched.py:92） |
| `speculative` | bool | 明文 | 是否投机轮 |
| `speculative_cancelled` | bool | 明文 | 投机轮是否被取消（`take_cancelled`，dialogsched.py:190） |
| `merged_segments` | int | 计数 | 合并段数（`PauseCandidate.merged_segments`，dialogsched.py:83） |
| `speculative_tokens_wasted` | int | 计数 | 取消轮浪费 token（上游同名字段，P14 主指标） |
| `dropped_latest_only` | int | 计数 | latest-only 清队丢弃数（`DialogQueue.dropped`，dialogsched.py:233） |
| `utter_len` | int | 计数（用户话语字符数） | `len(text)` |
| `utter_sha8` | str | 脱敏（话语 sha256 前 8 位，与 `s.asr.result.text_sha8` 对齐同轮） | sha256[:8] |
| `chunks_out` | int | 计数（speechchunk 切句数） | speechchunk 输出句计数 |
| （禁止对照）用户话语明文 / 回答文本明文（上游 `request`/`response` 两字段） | — | **禁止** | laos 红线落法：以 `utter_len`/`utter_sha8` 替代（§7 排除行） |

**`d.wake.state_change`**（发射点：laos/wakegate.py 四态迁移处——wake()/process()/speech_started()/barge_in()/finish_turn()/_expire()；实现形态=新增可选 `on_transition(old,new,reason)` 回调注入位，默认 None 零行为变化，与 GenerationGate `on_interrupt` 同款注入模式（技术评审 §2.2））

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `from` / `to` | str | 明文（sleeping/listening/processing/follow_up，wakegate.py:34-38） | 迁移两端 |
| `reason` | str | 明文（`wake`/`speech`/`sleep_word`/`max_turns`/`session_timeout`/`followup_timeout`/`barge_in`/`finish_turn`） | 触发函数名映射 |
| `turns` | int | 计数 | `self._turns`（上限 6，wakegate.py:48） |
| `session_ms` | int | 计数 | 会话已历时（上限 120s，wakegate.py:47） |
| （禁止对照）触发迁移的 ASR 文本 / 命中的唤醒·休眠词原文 | — | **禁止** | 只记 `reason` 枚举；`_normalize` 后的文本不入事件（wakegate.py:172-177 的文本仅闸内使用） |

**`d.barge_in`**（发射点：dialogsched.py `GenerationGate.interrupt()`（dialogsched.py:60-66，经 on_interrupt 回调链）+ wakegate `barge_in()` 返回 True 处；拒绝路径（非 Processing 态返回 False）记 warn 级同事件）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `generation` | int | 计数 | `interrupt()` 返回的新代数 |
| `source` | str | 明文（`wake`/`sched`/`turnpolicy`——turnpolicy 接线前不出现，R1） | 打断发起方 |
| `state` | str | 明文 | WakeGate 当时状态（拒绝路径诊断：非 processing 即入口条件不满足） |

**`d.mic.guard`**（发射点：装配层调用 `MicrophoneGate.allow()/emit_audio()/extend_guard()` 处（dialogsched.py:271-288）；节流 5s，`blocked_ms` 累计口径）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `action` | str | 明文（`block`/`release`/`extend`） | 调用语境 |
| `blocked_ms` | int | 计数（窗口内累计封锁时长） | `_blocked_until - now`（dialogsched.py:275） |
| `aec_ready` | bool | 明文 | allow() 形参（R4：drv_audio JAEC 就绪信号接入后开始翻转，当前恒 false） |
| `post_tts_guard_ms` | float | 明文（默认 400.0，dialogsched.py:263） | 构造参数 |

**`d.speculative.cancel`**（发射点：dialogsched.py `PauseWindow.handle_speech_activity()` 返回 True 处（dialogsched.py:159-165，经新增可选回调）+ `DialogQueue.enqueue()` 清队路径（dialogsched.py:243-245——该路径的投机轮"不会再到 writeMetrics"，必须独立发射否则 P14 丢数据））

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `dialog_id` | int | 明文 | 被取消轮 id |
| `reason` | str | 明文（`resume_cancel`：续说 ≥96ms×16 采样判定取消 / `latest_only_dropped`：新话语清队 / `superseded`） | handle_speech_activity / enqueue / register_dialog 三路径 |
| `merged` | bool | 明文 | 是否置合并标志（dialogsched.py:162） |
| `tokens_wasted_est` | int | 计数（latest-only 丢弃路径无计时，记估计值或 0） | 丢弃路径 |

### 3.6 P 类字段表

**`p.rtf`**（发射点：telemetry 聚合器；样本 = `s.asr.result` 的 `duration_sec`（input）与 `latency_ms`（wall），rtf = wall/input——上游 ASR 侧 rtf 口径的聚合形态，voice_node.cpp:423 同式）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `channel` | str | 明文 | 分通道聚合键 |
| `n` | int | 计数 | 窗口样本数 |
| `p50` / `p95` / `max` | float | 计数 | 分位数（SenseVoice GPU RTF≈0.01 实测锚点对照，docs/PROJECT_OVERVIEW 能力版图④） |

**`p.memory`**（发射点：telemetry 定时器；RSS 探测纯 stdlib：Linux 读 `/proc/self/status` VmRSS，Windows 经 ctypes `GetProcessMemoryInfo`——零依赖红线 ADR-1 下不引入 psutil；探测失败记 null 仍发事件）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `rss_kb` | int | 计数 | 平台探测（上游对照锚点：常驻 1951MB，采纳报告 §二） |
| `vms_kb` | int | 计数（探测可得时） | 同上 |
| `audit_records` | int | 计数 | `len(kernel.audit.records)`（kernel.py:132） |
| `uptime_s` | float | 计数 | `time.time() - kernel.boot_at` |

**`p.jsonl.water`**（发射点：telemetry 定时器；R10"JSONL 行数/字节水位事件"落位）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `file` | str | 明文（`audit`/`memory`/`rec_journal`） | 观测对象枚举 |
| `lines` | int | 计数 | 行计数（memory.jsonl → `MemoryStore.stats().total`，laos/memory.py:172） |
| `bytes` | int | 计数 | `Path.stat().st_size` |
| `watermark_hit` | bool | 明文 | 超容量水位（§6）时 true |

### 3.7 F 类字段表

**`f.tts.fallback`**（发射点：dialogsched.py `TtsRouter.synthesize_stream()` 降级路径 `self._fell_back = True`（dialogsched.py:364-365），经 `take_fell_back()`（dialogsched.py:368）由装配层发射；降级语义已可测（23 例 dialogsched 测试含降级不换声线），合成后端落地前事件源 = 装配层 mock/真后端通用，R3 缓解建议原文"降级路径埋点先落"）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `backend` | str | 明文（`online→offline`） | TtsRouter 状态 |
| `stage` | str | 明文（`synthesis_fail` 降级 / `mid_sentence_block` 句中不换声线保护拒绝） | synthesize_stream 分支 |
| `sentence_emitted` | bool | 明文（降级时本轮是否已发过在线音频） | `emitted` 局部变量语义（dialogsched.py:350-353） |
| `route` | str | 明文 | 所属轮 route（关联 d.dialog.turn） |

**`f.asr.channel_fail`**（发射点：drv_ear 三通道各自 except 路径——funasr `_get_model` RuntimeError（drv_ear.py:107-113）/ server urllib.error / whistle which 探测 ENOENT；经统一出口 err 字段由内核尾部转写）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `channel` | str | 明文 | 通道名 |
| `err` | str | 明文（errno 串截断 120 字符） | 异常串 |
| `requested_lang` | str | 明文 | 请求语言参数 |

**`f.model.load_fail`**（发射点：drv_ear `_get_model()` except（drv_ear.py:109）/ whistle 引擎探测 / drv_npu 模型加载；经 status 或首次推理路径转写）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `model` | str | 脱敏（模型路径掩码用户名段） | `LAOS_SENSEVOICE_MODEL` 等 env |
| `kind` | str | 明文（`sensevoice`/`whistle_engine`/`qnn`） | 加载对象 |
| `err` | str | 明文（errno 串） | 异常串 |
| `interpreter_source` | str | 明文（枚举；R11 探测链结果） | bin/laosd.py:163-165 |

**`f.rec.bypass`**（发射点：telemetry 断言器——对账窗口内扫描 audit 新增 `event:"mic"` 行，凡 `LAOS_REC=0` 生效期出现 `ok=true && denied=false` 即触发；error 级、永不节流、永不静默）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `tool` | str | 明文 | 违例的 mic.* 工具名 |
| `pid` | int | 明文 | 违例行 pid |
| `detail` | str | 明文（违例摘要：seq 与判定式） | 断言器拼装 |

> **断言器动机（P13 现状实取）**：仓库内 `LAOS_REC=0` 强制点当前仅 `drv_rec.rec_start` 一处（drivers/drv_rec.py:91-92，grep 全仓实取）；`drv_mic.mic.record`（drv_mic.py:153-170）未设闸。断言器正是"无禁录态全局断言"（需求评审 P13 现有观测点栏）的补位。**2026-10-07 已补闸（commit 84b5128：drv_mic 的 mic.record 与 mic.listen_start 双路径 EACCES）**——该旁路缺口已闭合，但断言器仍必设（防"新驱动绕过闸门"类未知旁路；本设计只定义观测，不改闸门语义）。

**`f.audit.gap`**（发射点：telemetry 对账器——内核 `syscall()` 派发尾记数（`pcb.stats["syscalls"]` 累计，kernel.py:503/541）vs audit `seq` 增量对账，差值>0 触发；error 级不节流）

| 字段 | 类型 | 脱敏级别 | 来源函数 |
|---|---|---|---|
| `expected` | int | 计数 | 派发侧累计 |
| `seen` | int | 计数 | audit 行数 |
| `gap` | int | 计数 | 差值 |
| `window_ms` | int | 计数 | 对账窗口宽 |

---

## §4 发射点清单（事件 ↔ laos 模块函数）

> "已落地"= 现有代码已有该数据位点，telemetry 波次只需接线；"预留"= 语义位尚不存在，标对应风险/问题编号。发射通道统一经 `laos/telemetry.py` 的 `emit()`（模块级 sink，由装配层 attach 到 `kernel.audit`；未 attach 时 no-op——裸解释器 import 零副作用，ADR-1）。

| 事件 | laos 模块 · 函数/位点 | 状态 | 预留对应 |
|---|---|---|---|
| `l.sys.init` | bin/laosd.py · `boot_kernel()` 返回处（laosd.py:142-168） | 接线位现成 | — |
| `l.driver.load` | laos/kernel.py · `load_driver()`（kernel.py:297-306 既有 driver_load 行增发）；听觉解释器探测字段源 bin/laosd.py:163-165 | 接线位现成 | R11（channels_available 使探测降级面板可见） |
| `l.driver.unload` | laos/kernel.py · `unload_driver()`（kernel.py:315） | 接线位现成 | — |
| `l.crash.recover` | detect：laos/kernel.py · `syscall()` 驱动异常路径（kernel.py:526-527 `EIO: driver … failed`） | detect 接线位现成；recovered **预留** | P11（驱动重启逻辑不存在）/ R10 |
| `a.mic.frame_overrun` | drivers/drv_rec.py · `on_audio` 回调 status 位（drv_rec.py:99-101，现被忽略）+ 未来 SPSC 环形队列 | **预留** | P15（上游 overrun 自愈语义已入档，技术评审 §5.2） |
| `a.device.reopen` | 音频前端自愈位（close+200ms 重开循环）——laos 尚无该循环 | **预留** | P09（上游 ENODEV/EPIPE 语义入档未实现）/ 技术评审 §5.2 盲区 |
| `a.vad.endpoint` | drivers/drv_rec.py · `on_audio` → laos/vad.py `StreamingVAD.feed()` 返回段（vad.py:125-160）；事件经内核 ear/rec 尾部转写 | 接线位现成 | — |
| `a.mic.stream_error` | drivers/drv_mic.py · `_listen_loop` except（drv_mic.py:122-123 `_listen_error` 落点结构化） | 接线位现成 | — |
| `s.asr.result` | drivers/drv_ear.py · 统一出口 JSON（文件头契约）增补脱敏字段；laos/kernel.py `syscall()` 尾部 `ear.*` 前缀转写（`event:"mic"` 模式同款 kernel.py:560-563） | 接线位现成 | — |
| `s.refine.delta` | laos/refiner.py · `refine()` 返回处（refiner.py:101）；调用方 bin/journal.py 管线 attach sink | 接线位现成 | R5（替换率线上观测正是其缓解建议） |
| `d.dialog.turn` | 装配层（消费 `DialogQueue` 的语音管线）轮完成/取消拼装；原型 = tests/test_dialog_e2e.py:146 metrics 行；dialogsched 保持纯决策核不持 sink | **预留**（语音问答管线未组装；R3 TTS 缺位仅影响 `first_audio_ms`=null） | R1（turnpolicy 接线后 `source=turnpolicy` 出现）/ R3 |
| `d.wake.state_change` | laos/wakegate.py · 六个迁移函数（wake/process/speech_started/barge_in/finish_turn/_expire）；**新增可选 `on_transition` 回调注入位**（默认 None 零行为变化，GenerationGate `on_interrupt` 同款模式） | 回调位待加（行为零变化） | R2（KWS 真音频触发未跑——reason=wake 的真机事件流空窗） |
| `d.barge_in` | laos/dialogsched.py · `GenerationGate.interrupt()`（dialogsched.py:60-66）+ laos/wakegate.py `barge_in()`（wakegate.py:121-127，True/False 双路径） | 接线位现成 | R1（source=turnpolicy）/ R4（AEC ready 后 barge-in 启用语义） |
| `d.mic.guard` | laos/dialogsched.py · `MicrophoneGate.allow()/emit_audio()/extend_guard()`（dialogsched.py:271-288）；装配层发射，节流 5s | 接线位现成 | R4（aec_ready 恒 false→翻转观测） |
| `d.speculative.cancel` | laos/dialogsched.py · `PauseWindow.handle_speech_activity()` 返回 True（dialogsched.py:159-165）+ `DialogQueue.enqueue()` 清队（dialogsched.py:243-245，注释明言该路径"不会再到 writeMetrics"）；**新增可选回调注入位** | 回调位待加（行为零变化） | P14 |
| `p.rtf` | laos/telemetry.py 聚合器（样本源 `s.asr.result`） | 新逻辑（telemetry 波次） | — |
| `p.memory` | laos/telemetry.py 定时器（stdlib 双平台 RSS 探测） | 新逻辑 | R10 / P10 |
| `p.jsonl.water` | laos/telemetry.py 定时器（audit/memory/rec_journal 三目标） | 新逻辑 | R10 |
| `f.tts.fallback` | laos/dialogsched.py · `TtsRouter.synthesize_stream()` 降级路径（dialogsched.py:356-366）经 `take_fell_back()`（dialogsched.py:368） | 接线位现成（降级语义已测） | R3（真合成后端）/ P07 |
| `f.asr.channel_fail` | drivers/drv_ear.py · 三通道 except（drv_ear.py:109-113 等）；内核尾部转写 | 接线位现成 | P03（通道自动切换不存在，LAOS_ASR_CHANNEL 手动——误切靠事件回溯） |
| `f.model.load_fail` | drivers/drv_ear.py `_get_model()`（drv_ear.py:100-124）+ drivers/drv_npu.py 模型加载 | 接线位现成 | P08 / R11 / R6（npu.infer 端点可达性另由 R6 缓解建议覆盖） |
| `f.rec.bypass` | laos/telemetry.py 断言器（扫描 `event:"mic"` 行 vs `LAOS_REC` 态） | 新逻辑 | P13（红线级；设计时点强制点仅 drv_rec.py:91 一处——2026-10-07 已补闸 84b5128，drv_mic 双路径，断言器仍必设） |
| `f.audit.gap` | laos/telemetry.py 对账器（`pcb.stats["syscalls"]` vs audit seq） | 新逻辑 | P12（红线级） |

**风险表覆盖核对**（技术评审 §4 R1–R11 逐条在本设计中有着落）：R1→`d.barge_in.source` 预留值 + `d.dialog.turn.interrupted/generation`；R2→`d.wake.state_change`（reason=wake 空窗即证据）；R3→`f.tts.fallback` + `first_audio_ms=null` 口径；R4→`d.mic.guard.aec_ready`；R5→`s.refine.delta.hits_*`；R6→`f.model.load_fail(kind=qnn)`；R7→不在运行时埋点面（研究资产层采集链路，技术评审缓解建议"采集成功/失败事件"属 scripts 层，本设计范围外，明记）；R8→不在埋点面（发版纪律面）；R9→不在埋点面（测试口径面）；R10→`p.memory`+`p.jsonl.water`；R11→`l.driver.load.channels_available`+`f.model.load_fail.interpreter_source`。

---

## §5 问题→埋点诊断矩阵（P01–P15，15 行全覆盖）

> 消费需求评审 §6 冻结编号。每行：症状 → 看哪个事件哪些字段 → 判定逻辑。

| # | 问题域（症状） | 看什么（事件 · 字段） | 判定逻辑 |
|---|---|---|---|
| **P01** | 唤醒不灵（喊唤醒词没反应，会话开不起来） | `d.wake.state_change`（reason=wake 计数）；`a.vad.endpoint`（duration_ms 分布）；`l.driver.load`（driver=ear/mic，ok）；`l.sys.init`（ear_python_source/asr_channel） | 三分支：① `a.vad.endpoint` 正常产生有声段但 reason=wake 迁移为 0 → KWS 漏唤醒/未接线（阈值/词表问题，R2 空窗期该分支恒真，属已知而非新故障）；② `a.vad.endpoint` 也无 → 音频前端未起，查 `a.mic.stream_error` 与 `l.driver.load.ok=false`（解释器探测失败→ear_python_source=fallback-main）；③ wake 迁移被拒 → `state` 字段显示卡在非 sleeping 态（会话内 `wake()` 只在 Sleeping 态生效，wakegate.py:85-86）→ 上轮会话未睡（P06 联查） |
| **P02** | 误唤醒（没叫它自己醒） | `d.wake.state_change`（from=sleeping→listening 的 reason=wake 密度/时段）；`a.vad.endpoint`（同时段有声段时长分布） | 睡眠时段（用户不自知的低频期）wake 密度超个人基线 → KWS 假阳性；伴随短 duration_ms（<1s）碎段触发 → VAD 灵敏度/电视背景音（负样本生成器接入前的先计数策略，R2 缓解建议原文） |
| **P03** | ASR 误识别劣化（转写越来越错） | `s.asr.result`（channel 漂移、req_lang vs lang 出入率、text_len/duration_sec 比值、latency_ms）；`s.refine.delta`（hits_correction 突增）；`p.rtf`（分位走势） | ① `channel` 从 funasr 变 whistle/server → 通道误切（ADR-4 列名的新故障模式：whistle 无中文且 en WER 10.8% vs funasr 2.7%，精度阶差即劣化）；② `req_lang`≠`lang` 出入率升 → 语言判定漂移；③ text_len/duration_sec 比值突降 → 前端增益漂移或 VAD 切碎（联查 `a.vad.endpoint.duration_ms` 分布左移）；④ `hits_correction` 突增 → 口语输入变多或 refiner 回归（R5：线上替换率可观测）；线上无 ref 无法算 CER——`audio_sha8` 供离线评测回灌对齐（§3.4 侧车说明） |
| **P04** | 端到端延迟劣化（越来越卡/首音变慢） | `d.dialog.turn`（first_text_ms/first_audio_ms/prefill_ms/generate_ms/retrieval_ms/total_ms 分位）；`s.asr.result`（latency_ms/endpoint_to_final_ms） | 分段归因：total_ms 膨胀时逐段看——retrieval_ms 高→知识检索段；generate_ms/first_text_ms 高→LLM 段；first_audio_ms−first_text_ms 大→TTS 段（R3 落地后）；`s.asr.result.latency_ms` 高→ASR 段（whistle ttft 651ms 实测锚点，funasr 非流式整段口径）；pause_observation_ms 高占比 + speculative_cancelled 率升→投机窗判定退化（联查 P14 行）；上游端到端锚点 1.44s（采纳报告 §二）对照 |
| **P05** | 打断失效（抢话了还在播旧回答） | `d.barge_in`（generation 递增序列）；`d.dialog.turn`（interrupted、generation）；`d.mic.guard`（blocked_ms、action） | 判定链：① `d.barge_in` 无事件 → 打断入口未触发：`state`≠processing（WakeGate 拒绝）或 `d.mic.guard` 显示 block 期（半双工锁麦，400ms guard）→ 属半双工预期而非 bug（R4）；② `d.barge_in` 有且 generation 递增，但该轮 `interrupted==false` 且 generation 未跟上 → **调度旁路**：过期代未被逐块核对（GenerationGate.is_current 缺失路径，R1 turnpolicy×GenerationGate 未组合的候选成因——技术评审 R1 原文"埋点在打断路径记录代数与发起方"落位）；③ interrupted=true 但仍播旧 → TTS 队列未清空（R3 落地后查 f.tts.fallback.stage） |
| **P06** | 会话异常（还在聊着突然睡了） | `d.wake.state_change`（to=sleeping 的 reason 分布：session_timeout/followup_timeout/max_turns/sleep_word；session_ms/turns 值） | ① reason=followup_timeout 但紧邻的 `a.vad.endpoint` 显示窗口内有声活动 → follow-up 12s 边界误判或时钟问题；② reason=max_turns 且 turns<6 → 轮数计数漂移；③ reason=sleep_word 但用户否认说过 → 休眠词误命中（ASR 文本侧问题，联查 P03：`utter_sha8` 对齐该轮 `s.asr.result.text_sha8` 看是否同源劣化）；④ reason=session_timeout 且 session_ms≈120000 → 正常超时（口径：follow-up 12s/会话 120s/6 轮，wakegate.py:46-48） |
| **P07** | TTS 降级频繁（声线突变/播报失败/不说话） | `f.tts.fallback`（stage/backend/sentence_emitted 计数率）；`d.dialog.turn`（route、first_audio_ms null 率） | `f.tts.fallback` 条数/轮数比率超阈值（如 >20%，阈值为面板参数非红线）→ 在线通道失败率高；stage=mid_sentence_block 占比高→句中不换声线保护频繁触发（design 选择而非故障）；first_audio_ms=null 率高→降级到文字输出形态（R3 空窗期的"不说话"主形态）；TTS 落地前本行事件源=装配层 mock，语义先行（R3 缓解建议原文） |
| **P08** | 模型加载失败（启动报错或通道静默不可用） | `f.model.load_fail`（kind/model/err/interpreter_source）；`l.driver.load`（channels_available）；`l.sys.init`（ear_python_source） | ① err 含 ENOENT + interpreter_source=fallback-main → 解释器探测失败（conda 迁移/多环境，R11"能力悄悄变窄"——现在变面板可见）；② channels_available 只剩 [server] → funasr/whistle 模型路径缺失（探测语义 drv_ear 文件头）；③ kind=qnn → NPU 通道（R6 真机链路漂移观测位）；④ 联查 `f.asr.channel_fail` 同通道计数 |
| **P09** | 音频设备断连（拔掉后链路死） | `a.mic.stream_error`（err/phase）；`a.device.reopen`（attempt/ok）；`a.vad.endpoint`（静默期长度） | ① stream_error 有 EIO 后无任何 reopen 事件 → 自愈未实现（**预留位空窗即判定**：上游 close+200ms 重开语义已入档未接，P09 现状）；② reopen attempt 递增但 ok 恒 false → 反复重开失败（节流 5s 内 throttled 计数即风暴强度）；③ vad.endpoint 长静默 + 无 error → 设备枚举漂移（无声失败，联查 mic.status） |
| **P10** | 内存增长（跑几天越来越胖） | `p.memory`（rss_kb 时间斜率；audit_records 同图）；`p.jsonl.water`（audit/memory lines/bytes 增速）；`a.vad.endpoint`（节流 throttled 值=段密度） | ① rss 单调升且 audit_records 同步升 → JSONL 无界增长驱动（R10：AuditLog.records 全量驻留内存 kernel.py:132-141；治理策略后置，观测先行）；② rss 升但 lines 平 → 队列/缓冲泄漏（drv_mic 监听原型"不裁剪缓冲，长时监听内存随时长增长"——drv_mic.py:92 docstring 自述）；③ 对照锚点：上游常驻 1951MB（采纳报告 §二），laos 未实测基线由本事件首次建立 |
| **P11** | 崩溃后恢复（crash 后状态不一致/录音开关态丢失） | `l.crash.recover`（phase=detect 无 recovered 配对；restarts）；`l.sys.init`（boot_count 递增 + rec_enabled 与崩溃前快照对比） | ① detect 后无 recovered → 驱动子进程死亡未自愈（现状：kernel EIO 返回后无重启，kernel.py:526-527——预留位空窗即判定）；② boot_count 递增且 rec_enabled 翻转 → 环境态跨崩溃不一致（P11 候选成因"驱动子进程未继承环境"）；③ 崩溃窗口的 `f.audit.gap` → 崩溃时审计 flush 缺失证据（§6.4：逐条 flush 语义下 gap 应恒 0，非 0 即异常路径） |
| **P12** | 审计缺失（某次调用/录音查不到记录，红线级） | `f.audit.gap`（expected/seen/gap）；`event:"mic"` 行（放行+被拒双路径完整性）；`f.rec.bypass`（禁录对账） | ① gap>0 → 派发计数与落盘行数不一致（异常吞审计/写入路径故障——errno 被包成 EIO 类问题复发的观测位）；② `event:"mic"` 放行/被拒对账：内核双写点（kernel.py:560-563/757-759）各应有的行缺失 → 红线双路径破洞；③ 对账周期默认 60s（§6.3），缺口定位到窗口 |
| **P13** | `LAOS_REC=0` 旁路（禁录下仍有录音行为，红线级） | `f.rec.bypass`（tool/pid/detail）；`l.sys.init`（rec_enabled 快照）；`event:"mic"`（denied 分布） | 判定式唯一且硬性：rec_enabled=false 生效期出现 `event:"mic"` 且 `ok=true && denied=false` → **红线违例**（error 级，永不节流/静默）；现状实取：强制点仅 drv_rec.rec_start（drv_rec.py:91-92），`mic.record` 路径未设闸——**2026-10-07 已补闸（84b5128，mic.record/mic.listen_start 双路径）**，断言器仍必设（§3.7 断言器动机：防未知旁路）；正常态对照：rec_enabled=false 时 `event:"mic"` 应全为 denied=true（EACCES） |
| **P14** | 投机取消风暴（回答变慢 + token 消耗 spike） | `d.speculative.cancel`（reason 分布、计数率、tokens_wasted_est）；`d.dialog.turn`（speculative_cancelled/speculative_tokens_wasted/pause_observation_ms/merged_segments） | ① reason=resume_cancel 占比高 + speculative_tokens_wasted 突增 → resume 判定过敏（≥96ms×16 采样阈值误判，dialogsched.py:93——上游口径"窗口内语音恢复且累计达限即取消"的过敏面）；② reason=latest_only_dropped 高 → 用户连续说话的正常丢弃（dropped_latest_only 佐证），若伴随用户感知变慢则查总排队时延；③ merged_segments 均值升 → 续说合并频繁（观察窗 500ms 与语速失配候选） |
| **P15** | 音频队列 overrun 风暴（识别断续、丢字） | `a.mic.frame_overrun`（overruns/dropped_frames/recovered 计数斜率；throttled 值）；`s.asr.result`（text_len/duration_sec 比值密度下降） | ① overruns 斜率陡升 + recovered 反复 true → 生产>消费→清队列+reset ASR 循环（上游自愈语义的副作用，采纳报告 §二"锁-free SPSC…overrun 自愈=清队列+reset ASR"）；② 伴随 asr 轮密度下降（同样时长内 s.asr.result 条数减）→ 丢字外显；③ 现状空窗即判定：laos 无 SPSC 队列，drv_rec status 位先接（§4 预留），事件未实现期该问题靠 `a.vad.endpoint` 段断裂间接观测 |

---

## §6 保留与采样

### 6.1 滚动保留

- **默认 7 天**（本设计定值；env `LAOS_TELEMETRY_KEEP_D=7` 覆盖）。
- 保留对象：`audit.jsonl` 当前文件 + 轮转归档段（见 6.2）。超过保留期的归档段删除；**当期文件不因保留期截断**（审计完整性优先）。
- 与 `rec_gc` 语义分立：原音频即焚 6h（drv_rec.py:158，LAOS_JOURNAL_KEEP_H）管音频；本节管 JSONL。两者互不扩大。

### 6.2 容量上限与轮转

- 单文件水位：**默认 64MB**（`LAOS_AUDIT_MAX_MB=64`）；`p.jsonl.water.watermark_hit` 字段在超水位时置 true（先告警）。
- 轮转：达水位后 `audit.jsonl` → `audit-<UTC日期>-<n>.jsonl.gz`（gzip 归档），重开空文件继续追加。归档总集超 7 天或总量超 **256MB**（gzip 后口径）删最旧。
- **seq 语义跨轮转**：`AuditLog.write()` 的 seq==records 下标（kernel.py:139）在轮转后 records 清零会重启——消费方去重键升级为 `(归档代, seq)` 复合键；laosweb 侧适配属实现波次（技术评审 §2.3"未知字段宽容"既定演化）。归档文件名内嵌单调递增 `n` 即归档代。

### 6.3 采样率（P 类；其余事件全量）

| 事件 | 默认采样 | env 覆盖 |
|---|---|---|
| `p.memory` | 60s 周期 | `LAOS_TEL_MEM_S=60` |
| `p.jsonl.water` | 10min 周期 | `LAOS_TEL_WATER_S=600` |
| `p.rtf` | 每 16 个样本或 5min 先到者 | `LAOS_TEL_RTF_N=16` |
| `a.vad.endpoint` | 全量但 5s 节流聚合（throttled 计数承载） | 节流窗 `LAOS_TEL_THROTTLE_MS=5000` |
| `f.audit.gap` 对账周期 | 60s | `LAOS_TEL_RECONCILE_S=60` |
| 其余（L/D/S/F 全部） | 全量（节流豁免清单见 §1.4） | — |

### 6.4 崩溃 flush 语义

- **逐条 flush 继承**：埋点事件与既有审计行同走 `AuditLog.write()` 的 `write()+flush()`（kernel.py:141-142）——每事件落盘即 flush 到 OS，进程崩溃（含未捕获异常退出）**不丢已发射事件**。
- 边界声明：flush 到 OS 页缓存后、断电/内核 panic 级丢失不在承诺内（既有审计同边界）。
- `level=error` 的事件（`f.rec.bypass`/`f.audit.gap`/`f.model.load_fail`）额外同步写一行到 stderr——崩溃现场（终端/journalctl）直接可见，不依赖文件 survived。
- 崩溃后自证：下次启动 `l.sys.init.boot_count` 递增 + 前一 boot 末尾无 `event:"shutdown"` → 未正常关机判定（P11 对账素材）。

---

## §7 与 voicenpu metrics 口径对照表（22 字段）

> **口径核实（源码实取）**：上游 `dialog_metrics.jsonl` 每行字段全集 = **25 个**——必有段 19（`dialog_id, request, response, route, knowledge_id, retrieval_ms, success, interrupted, first_text_ms, first_audio_ms, prefill_ms, generate_ms, tokens, memory_mb, total_ms, pause_observation_ms, speculative_cancelled, merged_segments, speculative_tokens_wasted`）+ ASR 条件段 6（`asr_input_sec, asr_wall_sec, vad_compute_ms, zipformer_ms, endpoint_to_final_ms, speech_to_first_audio_estimate_ms`），实取自 var/repro/voicenpu_engine/src/scheduler/dialog_controller.cpp:387-418。
> **冻结"22 字段"口径的构成**：25 − `request`/`response`（明文内容字段，laos 红线禁采）− `speech_to_first_audio_estimate_ms`（纯派生值：= vad_endpoint_ms + endpoint_to_final_ms + first_audio_ms，dialog_controller.cpp:416-418，已有字段加和可复得）= **22 个可观测指标字段**，即下表。三个排除字段列于表后备注行。

| # | 上游字段 | 处置 | laos 落位（事件 · 字段） | 说明 |
|---|---|---|---|---|
| 1 | `dialog_id` | **改名** | `d.dialog.turn` · `turn_id` | 与信封 `session`/`seq` 三层定位一轮 |
| 2 | `route` | **直接采纳** | `d.dialog.turn` · `route` | 取值 knowledge/llm/tts（e2e 测试同款） |
| 3 | `knowledge_id` | **直接采纳** | `d.dialog.turn` · `knowledge_id` | 知识短路命中条目 id（阈值 0.58） |
| 4 | `retrieval_ms` | **直接采纳** | `d.dialog.turn` · `retrieval_ms` | knowledge.search 耗时 |
| 5 | `success` | **改名** | `d.dialog.turn` · `ok` | 与 laos syscall 审计 `ok` 命名对齐 |
| 6 | `interrupted` | **直接采纳** | `d.dialog.turn` · `interrupted` | P05 判定主字段 |
| 7 | `first_text_ms` | **直接采纳** | `d.dialog.turn` · `first_text_ms` | — |
| 8 | `first_audio_ms` | **直接采纳** | `d.dialog.turn` · `first_audio_ms` | TTS 缺位期 null（null 率本身是 R3 观测） |
| 9 | `prefill_ms` | **直接采纳** | `d.dialog.turn` · `prefill_ms` | 无常驻 LLM 通道时 null，预留 |
| 10 | `generate_ms` | **直接采纳** | `d.dialog.turn` · `generate_ms` | — |
| 11 | `tokens` | **直接采纳** | `d.dialog.turn` · `tokens` | 计数级 |
| 12 | `memory_mb` | **改名（迁类）** | `p.memory` · `rss_kb` | 上游按轮记常驻；laos 独立为 P 类周期采样（kb 口径），dialog.turn 不重复采——轮级归因经 `ts` 对齐 |
| 13 | `total_ms` | **直接采纳** | `d.dialog.turn` · `total_ms` | — |
| 14 | `pause_observation_ms` | **直接采纳** | `d.dialog.turn` · `pause_observation_ms` | PauseWindow.observation_ms（默认 500） |
| 15 | `speculative_cancelled` | **直接采纳** | `d.dialog.turn` · `speculative_cancelled` | — |
| 16 | `merged_segments` | **直接采纳** | `d.dialog.turn` · `merged_segments` | — |
| 17 | `speculative_tokens_wasted` | **直接采纳** | `d.dialog.turn` · `speculative_tokens_wasted` + `d.speculative.cancel` · `tokens_wasted_est` | P14 主指标；取消路径被 latest-only 丢弃时由独立事件兜底（§3.5） |
| 18 | `vad_compute_ms` | **改名** | `s.asr.result` ·（asr 段 vad 耗时子字段，随 `latency_ms` 分解预留） | 上游字段名 `vad_compute_ms`（JSONL 内）；采纳报告 §二写作 `vad_ms` |
| 19 | `zipformer_ms` | **改名** | `s.asr.result` · `endpoint_to_final_ms` 的通道分解口径 | zipformer 是上游 RKNN 专属模型名；laos 三通道（funasr/whistle/server）统一记通道名+延迟，不引入模型专名字段 |
| 20 | `endpoint_to_final_ms` | **直接采纳** | `s.asr.result` · `endpoint_to_final_ms` | 上游 ~88ms 锚点对照位 |
| 21 | `asr_input_sec` | **直接采纳（改名 duration_sec）** | `s.asr.result` · `duration_sec` | 音频时长=脱敏允许形态 |
| 22 | `asr_wall_sec` | **直接采纳（换算 latency_ms）** | `s.asr.result` · `latency_ms` | 毫秒口径；与 duration_sec 之比即 rtf（→ `p.rtf`） |

**排除字段（3，红线/冗余）：**

| 上游字段 | 处置 | 理由 |
|---|---|---|
| `request`（用户话语明文） | **不采纳（红线禁止）** | laos 以 `d.dialog.turn` · `utter_len` + `utter_sha8`（len/sha256 前 8 位）替代——可对齐不可还原 |
| `response`（回答文本明文） | **不采纳（红线禁止）** | 回答文本经 `chunks_out` 计数与既有 syscall 审计 `result` 截断（kernel.py:507，既有语义）覆盖，遥测不复制 |
| `speech_to_first_audio_estimate_ms` | **不采纳（纯派生）** | = vad_endpoint_ms + endpoint_to_final_ms + first_audio_ms（源码三字段加和，dialog_controller.cpp:416-418），消费方可自行计算 |

**备注**：采纳报告 §二 另提及 ASR 侧 `rtf`——实为上游日志行的派生值（rtf = wall/input，voice_node.cpp:423-429），不在 dialog_metrics.jsonl 字段集内；laos 以 `p.rtf` 聚合事件采纳该口径。`knowledge_score`、`generation`、`dropped_latest_only`、`utter_len`、`utter_sha8`、`chunks_out` 六个字段为 laos 增补（上游无），服务 P03/P05/P14 判定。

---

## §8 自查核对（交付前硬条）

1. **诊断矩阵 15 行全覆盖**：§5 表 P01–P15 逐行对应需求评审 §6 冻结编号，无缺行（15 行机械计数）。
2. **每字段表有脱敏级别列**：§3.1 信封表 + §3.2–3.7 全部 23 事件字段表，逐字段标 `明文|计数|脱敏|禁止`；内容接触点（`a.vad.endpoint`/`s.asr.result`/`s.refine.delta`/`d.dialog.turn`/`d.wake.state_change`）各带"禁止对照行"（5 处）。
3. **隐私红线零违反**：全文无任何字段采音频字节/转写明文；`s.refine.delta` 只记 delta 计数与哈希（brief 红线原文落位）；内容类字段只用 len/sha8/时长/语言码四种形态（§1.2）；`LAOS_REC=0` 联动静默规则成表（§1.5）。
4. **数字有源**：25/22 字段（dialog_controller.cpp:387-418 实取）；400ms guard（dialogsched.py:263）；96ms×16（dialogsched.py:93）；12s/120s/6 轮（wakegate.py:46-48）；0.58（knowledge.py:117）；6h（drv_rec.py:158）；-35.0 dBFS（drv_rec.py:89）；1.44s/1951MB/~88ms/200ms 重开（采纳报告 §二）；651ms/10.8%/16.9MB（cactus-whistle 采纳报告）；-15.2%/0.4571→0.3875、CER 1.563→0.042（agenticasr 采纳报告）；691/279/71/31（两评审报告实跑口径）；5s 节流/7 天/64MB/256MB/采样周期（本设计定值，§1.4/§6 显式声明）。
5. **风险表覆盖**：R1–R11 逐条在 §4 末尾核对表有着落（R7/R8/R9 明记"不在埋点面"而非假覆盖）。

---

### 附：本文引用来源

- 需求评审：docs/review/2026-10-07-requirements-review.md（§4.3 隐私红线、§6 P01–P15）
- 技术评审：docs/review/2026-10-07-technical-review.md（§2.3 审计契约、§4 R1–R11、§5.2 盲区、§6.2 未实测清单）
- voicenpu 采纳报告：docs/research/2026-10-06-voicenpu-adoption.md（§二 上游全景与调度三机制/自愈语义、§六 后续建议）
- 上游源码实取：var/repro/voicenpu_engine/src/scheduler/dialog_controller.cpp:387-418（metrics 字段全集）、src/engine/voice_node.cpp:423-429（rtf 派生式）、include/scheduler/dialog_controller.h（AsrMetrics）
- laos 源码实取（2026-10-07）：laos/kernel.py（AuditLog:125-145、event:"mic":557-563/754-760、driver_load:297-306、EIO 路径:526-527）、laos/wakegate.py（四态:34-38、参数:46-48）、laos/dialogsched.py（GenerationGate:51-74、PauseWindow:86-206、DialogQueue:222-249、MicrophoneGate:258-288、TtsRouter:320-383）、laos/refiner.py、laos/knowledge.py、laos/vad.py、laos/memory.py、drivers/drv_ear.py（通道/惰性加载:95-124）、drivers/drv_mic.py（_listen_loop:90-140、mic_record:153-170）、drivers/drv_rec.py（LAOS_REC:91、rec_gc:156-166）、bin/laosd.py（boot_kernel:142-168）、tests/test_dialog_e2e.py（metrics 原型:146）
- 计划事实基线：docs/superpowers/plans/2026-10-07-review-instrumentation.md
