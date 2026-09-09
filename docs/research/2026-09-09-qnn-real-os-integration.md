# 从 AgentOS 到真实操作系统 —— QNN/ADSP 项目学习与结合路线

> 调研日期：2026-09-09。学习对象：`C:\Users\yaoyue\Downloads\QNN`（TIM-Net/LIGHT-SERNET
> 语音情感识别在骁龙 ADSP 上的 QNN 部署工程）；结合对象：laos（Linux AgentOS）。
> 结论先行：**QNN 项目已经是一套"真实操作系统集成"的完整教材**——它跑在骁龙 ADSP 的
> QuRT 实时内核 + SEE 传感器框架上，宿主侧是 Android/Linux。laos 与它的结合点不在 DSP
> 侧（QuRT 是专有静态链接的 RTOS，Python 进不去），而在 **AP 侧的 Android/Linux**：
> 把 laosd 作为设备上的 Agent 语义层，把 QNN 运行时和 ADSP 传感器包装成 laos 驱动。

---

## 一、QNN 项目是什么（学习总结）

**目标**：把超轻量语音情感识别模型（TIM-Net，34,671 参数 / 0.4MB；LIGHT-SERNET，~460K 参数）
量化后部署到骁龙 8 Elite（SM8735 "Bonito"，Hexagon v73M）的 **Audio DSP** 上，实现
always-on、低功耗（Active < 50mW / LPI < 5mW）的端侧情绪识别，7 分类（快乐/悲伤/愤怒/
中性/恐惧/厌恶/惊喜）。

**端到端链路**：

```
训练(Keras) → MFCC 特征(479帧×26维) → 转换(4D SavedModel→ONNX→QNN int8, QAIRT 2.47)
→ 产物(timnet.cpp/.bin/.json 或 .eaix 上下文二进制) → SCons 编入 SEE 镜像
→ ADSP 运行: 麦克风→重采样16k→攒3s→MFCC→int8量化→eAI推理→反量化→argmax→protobuf事件→Android App
```

**关键工程决策**（都是被真实约束逼出来的，也是面试材料的核心）：

1. **初始化走 Active、推理走 Island**：LPI（低功耗岛）模式禁止 malloc/IO——所有内存在
   Active 态预分配好 scratch，Island 态纯计算。这是"不可逆预算"的硬件版：进岛之前
   必须把资源谈好，中途没有后悔药。
2. **算法层不知道 SEE 的存在**：MFCC/量化/推理是纯 C 函数，可独立单测——和 laos
   "语义层与强制层分离"是同构的分层哲学。
3. **int8 走完全程**，只在边界量化/反量化（MFCC float → int8 → eAI → int8 → float）。
4. 转换链路踩了 7 个算子兼容坑（reverse→gather、Lambda→标准算子、causal→ZeroPadding2D、
   1D→4D、SpatialDropout 移除、expand_dims→Reshape、环境隔离）。
5. QNN 编译绕过 cmake，直接 clang-cl + lld-link（ClangCL 集成 / UAC 限制）。

**关键数字**：TIM-Net 123 节点 / 11 种算子 / QNN CPU 推理 ≈ 6ms；输入 `[1,1,479,26]`；
EMO-DB 70.28%（5 折）；蒸馏学生模型 ~174KB .eaix。

---

## 二、它背后的真实操作系统栈（这才是"真正的操作系统"）

从下往上四层，每一层都是真实的操作系统组件，且都能在 QNN 工作区里找到源码/头文件：

### 1. QuRT 实时内核（DSP 上的"Linux"）
`qualcomm/core/kernel/`：高通跑在 Hexagon DSP 上的**实时操作系统内核**。
- `qurt/` 内核构建、`arch/` Hexagon 架构支持、`island_mgr/` **电源岛管理器**
- 提供真实的线程、信号量、锁、内存分区。注意：ADSP 上没有进程，只有 **QuRT 线程**——
  SEE 就是 DSP 上一个特权线程池跑起来的大进程（这也是 laos 的进程模型无法上 DSP 的根因）
- `qdsp6/`：DSP 侧服务——`sysmon`（监控）、`adspservices_qdi`（内核驱动接口 QDI）、
  `qshrink`（镜像裁剪）

### 2. SEE 传感器框架（DSP 上的"用户态内核"）
`qualcomm/qsh_*/`：SEE（Snapdragon Sensor Execution Environment）。
- **驱动注册模型**：`sns_sensor`（注册/探测）+ `sns_sensor_instance`（实例/事件循环）——
  与 laos 的"驱动 = MCP Server"是**同一个抽象**：注册 → 建实例 → 收事件 → 上报
- **事件驱动**：resampler 推音频帧进来（protobuf 解码）→ 算法处理 → pb 编码上报 App
- 静态内存、Island/LPAI 上下文切换由 `sns_island_service` 管理
- 实例源码：`qualcomm/qsh_algorithms/ai_timnet/sensor/src/sns_ai_timnet_sensor_instance_island.c`

### 3. eAI 运行时（DSP 上的"AI 系统调用层"）
`qualcomm/eai/runtime/api/eai.h`：`eai_init / eai_execute / eai_get_properties` +
完整的 `EAI_RESULT` 错误码体系（`EAI_RESOURCE_FAILURE` 内存不足、
`EAI_PROHIBITED_LPI_REQUEST` "Island 态禁止此调用"、`EAI_INVALID_MODEL_VERSION`…）。
**这就是 DSP 上的 syscall 约定**：模型句柄 = 文件描述符，execute = 系统调用，
`EAI_PROHIBITED_LPI_REQUEST` = 硬件级的 errno。

### 4. Android/Linux 宿主（AP 侧）
- `qnnsdk/qairt/2.47.0.260601/lib/aarch64-android/`：**Android 上的 QNN 运行时**
  （libQairtHtp.so + hexagon v68…v81 各版本 stub）——AP 侧用户态库，通过 **FastRPC**
  把推理下沉到 DSP/HTP
- `qualcomm/platform/apps_std`、`HAP_utils`：AP↔DSP 的文件加载与消息通道
- 端侧 App（TimnetLpaiApp / SerFusionApp 等）：Kotlin + JNI，订阅情绪事件
- **这一层底下就是 Linux 内核**——Android 的 binder、权限、cgroup 全都在

---

## 三、laos 与真实系统的映射表

laos 的每个模拟原语，在这套真实栈里都有对应物——这正是两个项目能接上的原因：

| laos 概念（模拟） | QNN/ADSP 真实对应物 | 差距 |
|---|---|---|
| 驱动 = MCP Server 进程 | SEE sensor 驱动（register/instance/event）+ Android 侧 QNN so | 驱动协议：JSON-RPC vs protobuf/FastRPC |
| syscall 网关 + errno | eai.h API + EAI_RESULT 错误码；SEE sns_rc | laos 已对齐（errno 透传设计一致） |
| 能力表（caps） | Android 权限 + SEE 客户端绑定 | laos 更细粒度（工具级 vs 应用级） |
| task_scope 路径边界 | DSP 静态内存分区（进了哪个 scratch 就只能用哪块） | 硬件强制 vs 语义强制 |
| 风险账本 | **LPAI 功耗预算**（Active < 50mW；Island 禁 malloc = 资源预承诺不可逆） | 论文里的 Irreversibility Budget 在 DSP 上是物理现实 |
| 分支 fork/explore/commit | 不存在（DSP 上静态镜像，无法 fork） | laos 的分支语义只能在 AP 侧（Linux）实现 |
| 审计流 | SEE 日志 + Android logcat | laos 的结构化审计更丰富 |
| stale context 广播 | resampler 音频流天然是"新数据" | laos 的观察簿机制可直接服务传感器流 |

**核心洞察**：DSP 侧（QuRT/SEE）是封闭的静态 RTOS 世界——Python 进不去、进程模型不存在、
镜像构建走 SCons 专有工具链。**laos 能且只能落在 AP 侧的 Android/Linux 上**，但这恰好是
最合适的位置：AP 侧有 Linux 内核（laos 的强制层原语全部可用）、有 QNN Android 运行时
（libQairtHtp.so）、有多进程（laos 的进程模型成立）、DSP 侧的 AI 能力以"设备"的形态
暴露给 AP——**对 laos 来说，ADSP 就是一个待接入的硬件驱动**。

---

## 四、结合路线（按可行性排序）

### 路线 A：laosd 上 Android，QNN 变成 `npu.*` 驱动（推荐，AP 侧 Linux）

**形态**：Android 设备上（Termux 或 App 内嵌 Python），laosd 作为常驻语义层；新增
`drivers/drv_npu.py`，包装 QAIRT 的 aarch64-android 运行时（经 JNI/cffi 或独立 JNI
服务），把 `npu.infer(model, input)` 注册为 laos syscall。

```
Agent(caps=["npu.infer"], task_scope=["emotion/"], risk_cap=…)
    → kernel.syscall("npu.infer", …)
    → drv_npu → libQairtHtp.so → FastRPC → HTP/DSP 硬件推理
```

- 强制层直接成立：Android 是 Linux，seccomp/namespace/cgroup（laos 已实现的 Part B）
  对 agent 进程真实生效——**laos 第一次在真 Linux 上开启 full isolation**
- 风险账本有了物理意义：HTP 推理消耗功耗/热预算，把 `irreversibility_cost` 定成
  推理功耗档位，就是论文机制的落地
- 事件回传：ADSP 情绪传感器事件（经 Android App 转发）作为 `emotion.events` 驱动接入，
  agent 用 stale-context 机制订阅——传感器流天然是"新数据"
- 审计/剖析：AgentProf 的 eBPF 部分在 Android 上可用（root），对照 QNN 推理耗时

**工程量**：drv_npu 的 JNI 桥是主要工作（QAIRT Android SDK 齐全，examples 里有完整
参考）；laos 侧零改动——驱动就是 MCP Server，这是驱动模型设计的回报。

**第一步**：在 Termux 里跑通 `python bin/laosd.py`（纯标准库，可行性高）。

### 路线 B：laos 语义层"投影"到 DSP（研究向）

把 laos 的能力表/风险预算**编译**进 SEE 镜像：SEE 传感器注册时声明 capability 清单、
LPAI 预算在 init 阶段检查——给 SEE 写一个"laos 语义运行时"（纯 C）。价值是论文级的
（"AgentOS 语义层在 RTOS 上的实现"），工程上受高通代码授权约束。适合作为研究/面试
深挖方向：它能把"AgentOS 概念 + ADSP 部署经验"串成一个原创技术故事。

### 路线 C：桌面双机演示（零硬件，本仓库已落地）

在 PC 上用 QAIRT 的 x86_64 后端（SDK 自带 CPU/参考后端）跑最小 `npu.infer` 驱动，
laos 面板实时展示 agent 调 NPU 的审计流与风险扣费——路线 A 的纯软件预演。
**本仓库已实现 stub 后端版本**（`drivers/drv_npu.py`，QAIRT 缺席时自动兜底），
demo 里有"NPU 推理"幕。

---

## 五、laos 侧需要补的短板（按路线 A）

1. **Android 可运行性**：laos 目前 154 项测试在 Windows 上全绿（降级模式），但
   `bin/laosweb.py`、驱动子进程模型在 Termux/Android 上未验证——纯标准库实现，
   可行性高，待实测。
2. **驱动事件推送**：接入"传感器事件流"驱动需要事件推送（当前 MCP stdio 是
   请求-响应）。MCP 2026-07-28 升级时已打通双向请求（elicitation 路径），
   server→client notification 是顺路的事。
3. **功耗/热预算动态化**：`irreversibility_cost` 目前是静态标注；接 Android
   `PowerManager`/热传感器可把成本变成动态实测——风险账本从"语义模拟"变"物理实测"。
4. **Android 强制层**：`sandbox.py` 的 unshare/seccomp 在 Android 内核上可用但
   Termux 的 namespace 权限受限——需要实测降级矩阵。

---

## 六、QNN 值得 laos 借鉴的三个设计

1. **"Active 初始化 / Island 推理"的资源预承诺**：laos 的 spawn 准入控制可以学它——
   agent 准入时一次性谈好全部资源（上下文窗口、驱动句柄、风险帽），进入"执行态"后
   只做计算——把"中途资源不足"这类失败在准入时消灭。
2. **算法层不知道框架存在**：laos 的 brain/context 已经做到；驱动层可更进一步——
   驱动只暴露纯函数语义，传输层（MCP stdio / 进程内）可替换。
3. **错误码即文档**：`EAI_PROHIBITED_LPI_REQUEST` 这种自解释错误码，比 laos 现在的
   字符串 errno 更适合跨层传递——laos 的 errno 可升级为结构化对象（code + layer + hint）。

---

## 七、两个项目的共同灵魂

laos 说"AgentOS = Linux kernel + Agent + MCP"；QNN 项目证明的是同一件事的嵌入式版本：
**在资源受限的真实系统上，AI 推理必须有操作系统级的纪律**——预分配、分层、能力边界、
错误码、功耗预算。DSP 工程师叫它"嵌入式工程规范"，AgentOS 研究者叫它"AI 操作系统"。
把两者接起来，就是"端侧 Agent 操作系统"的完整故事：

**Linux（AP）上 laos 管语义与强制，QuRT（DSP）上 QNN 管确定性推理，
FastRPC 是总线，情绪事件是中断。**
