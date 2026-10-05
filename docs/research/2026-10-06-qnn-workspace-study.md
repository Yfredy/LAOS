# QNN 工作区通读学习（C:\Users\yaoyue\Downloads\QNN）

> 学习日期：2026-10-06。方法：Explore agent 全区测绘（22GB/73,492 文件，跳过个人文件与
> tmp/ 12GB 杂物）+ 五份关键文件精读（BUILD.md / lpai-ser-dataflow.md / InferenceServer.kt /
> sns_ai_timnet_sensor.c / PROJECT_LEARNING.md）。

## 一句话总结

这不是"另一套内核"，而是**在真实固件基座上做了一次 laos 同款动作**：把 18,481 文件的原厂
Qualcomm ADSP 固件树（adsp_proc tarball）从"无法编译"修到一条命令出**签名固件**
`bonito.adsp.prodQ`，然后把自己量化好的 SER（语音情感识别）模型注册成 SEE 框架里的
**一个虚拟传感器**（与加速度计、陀螺仪同类），常驻 SLPI 低功耗岛——**AP 深睡时推理照常，
结果走传感器事件流上报**。

## 一、地形图

| 区域 | 角色 |
|---|---|
| `qualcomm/` | **主战场**：ADSP 固件源码树（git 管理，基线 `a178e157`=原厂 tarball 逐字节一致，其后 `298f2602` 等提交全为自研修复与新增） |
| `qualcomm/qsh_algorithms/ai_timnet/` | TIM-Net SER 作为 SEE 虚拟传感器：sensor 胶水（注册/生命周期/实例）+ algo（岛内 MFCC、int8 量化、86KB 模型 C 数组、EAI 运行时绑定） |
| `qualcomm/qsh_algorithms/audio_recorder/` | 全天候低功耗录音器 SEE 单元：30s 环形缓冲 + 能量 VAD（RMS>800/300ms 开段、静音 1.5s 切、预滚 1s） |
| `qualcomm/build/ms/run_build.py` | 自研三阶段构建入口（libs→shared→link+签名），替代缺失的官方 setenv.py |
| `SER/SER-Projects/` | 模型侧：TIM-Net/LIGHT-SERNET 训练、QNN int8 量化全流水线、蒸馏、4 个 Android App |
| `SER/.../TimnetLpaiApp/.../InferenceServer.kt` | **laos 桥梁**：127.0.0.1:8900 零依赖 HTTP 服务，注释明言供 "laos AgentOS over adb forward" 调用 |
| `qnnsdk/qairt/2.47.0.260601/` | Qualcomm QAIRT/QNN SDK（纯依赖，未改） |
| `docs/` | 自研文档：PROJECT_LEARNING 总笔记、survey 普查流水线、jev 研究、8 份执行计划 |

## 二、为什么说这是"内核优先"架构观的最强佐证

用户的架构观：**基座不动，新负载以基座已有的类别注册进去，治理沿用基座机制**。
QNN 工作区在固件层把这个动作完整做了一遍：

1. **基座不动**：ADSP 固件树的调度（QuRT）、内存（island/普通段）、传感器框架（SEE）、
   签名加载（PIL）全部沿用原厂机制；自研工作 = 修兼容（~60 文件电池管理桩、Py3/Windows
   构建适配）+ 加新算法单元，**不改内核结构**；
2. **新负载进既有类别**：AI 推理没有另起"AI 子系统"，而是注册成 SEE **虚拟传感器**
   （`sns_ai_timnet_sensor_register`）——suid 查找 resampler/audio、发布属性、on-change
   事件流，和任何物理传感器走完全一样的路。**这与"Agent 是新负载，与进程同类"是同一条
   设计公理在两个层面的实例化**：固件层=AI 算法与传感器同类；Linux 层=Agent 与进程同类；
3. **治理/预算先行**：模型入镜像前做了符号级内存审计（`hexagon-nm` 量出模型 rodata
   86,241B、island 段差分为零、岛内已有 345KB 占用），并诚实记录"本变体 SEE 岛被禁用，
   SER 实际常驻在 qshtech 普通段"——**先测预算、再谈常驻**，与 laos FleetLedger
   先扣账后派发同一精神；
4. **两条部署路线并存**：固件内 C 数组（改模型需重编固件）vs QAIRT LPAI `.eaix`（免重编
   动态加载）——对应"内核内置驱动 vs 可加载模块"的经典权衡。

## 三、端到端链路（已验证入镜像的 ai_timnet）

```
数字麦克风(PDM/I2S) → sns_resampler(16kHz) → sns_ai_timnet 虚拟传感器
  → 攒 3s 窗 → 岛内 MFCC(479×26) → int8 量化 → EAI 运行时(eai_execute, v4.14.0)
  → 反量化 argmax → sns_ai_timnet_result{emotion,confidence}(nanopb)
  → SEE 事件流 → AP 侧客户端 / AP 深睡照常
```

AP 侧另一条路（HLOS 路线）：`.eaix` 上下文二进制由 Android App JNI 加载
`libQnnLpai*.so` 推理，经 **InferenceServer.kt** 暴露：
`GET /health`、`POST /infer`（base64 PCM→7 类概率+latency）、`GET /events?since=`
（情感变化环形缓冲轮询）、`GET /battery`、`POST /rec/start|/rec/stop`、`GET /rec/segments`
（VAD 触发式录音段落盘清单）。**只绑 127.0.0.1**，PC 侧经 `adb forward tcp:8900` 访问
——这正是 laos `npu.infer` syscall 的设备端对端。

## 四、对 laos 的借鉴裁决

| 项 | 内容 | 落点 | 档 |
|---|---|---|---|
| A | **VAD 语义两侧对齐**：InferenceServer.runRecorder 注释明言"判据与 laos/vad.py 语义一致"，但参数有漂移（设备端 min_speech=400ms/静音切 400ms，laos 默认 200/400ms） | 本档记录 + qnn 真机 runbook 交叉引用；laos 侧不改（参数本就可调） | ◐ |
| B | **置信度三段闸**（与同日四篇文章采纳件 A 汇流）：SER 概率低时不应触发上层动作 | `laos/confgate.py`（本波次落地） | ● |
| C | **事件轮询协议** `/events?since=<ms>` + 环形缓冲上限（100 条）：增量拉取、有界内存——laos 驱动事件流的成熟模式，laosweb 轮询对齐此语义 | 记录；laos events 驱动已有同类设计，对照不改动 | ◐ |
| D | **回环绑定原则**：零依赖手写 HTTP 只绑 127.0.0.1，跨机访问必须经 adb forward（等价于显式隧道授权）——laosweb 的安全底线同款，作为不变式写入对照 | 记录（laosweb 已遵守，作为回归检查点） | ◐ |
| E | **Active 初始化 / Island 推理双模式**：重路径（malloc/IO/模型加载）只在初始化走，常驻路径纯静态内存——laos 驱动子进程"启动重、稳态轻"的同构原则 | 记录进驱动设计原则 | ◐ |
| F | **符号级预算审计法**（nm/readelf 量占用、开关差分、md5 确认两份构建确实不同）| FleetLedger 精神的固件侧镜像，本档记录方法论 | ○ |

**红线对照**：QNN 的设备端 `/rec/start` 是无鉴权回环端点（信任 adb forward 隧道对端）——
laos 侧录音仍必须走显式 syscall 闸门（能力表→确认横幅→审计 event:"mic"），设备端点
视为"已被 laos 闸门治理的裸硬件能力"。**分层不变**：治理在 laos，不在设备端点。

## 五、事实口径备忘（两套数字并存，引用时注意）

- 构建目标：`bonito.adsp.prodQ`，Hexagon v68（BUILD.md）；PROJECT_LEARNING.md 写
  SM8735/v73M——以 BUILD.md（实测构建配置）为准；
- 模型大小：86,241B rodata（符号级实测）vs "0.4MB"（参数量口径）——引用用 86KB 常驻；
- ai_lightsernet：算法库 557KB 已编译，**缺 SEE 胶水未入镜像**（诚实边界）；
- SER-Distill：学生模型 ~53-55% 验证准确率，导出脚本 Functional 无 export() 崩溃未收尾。

## 六、后续可做的衔接（未排期，记录备查）

1. laos npu 驱动接入 `/events` 情感变化流（现为 /infer 拉模式）；
2. laos FleetLedger 为 npu.infer 增加 latency_ms 记账（设备端已返回该字段）；
3. qnn 真机 runbook（laos/docs/）补一节"InferenceServer 端点对照表"。
