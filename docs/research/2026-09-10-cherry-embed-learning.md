# CherryUSB + CherryAVP 学习分析 —— 嵌入式"小而美"的两堂架构课

> 调研日期：2026-09-10。学习对象：`C:\Users\yaoyue\Downloads\CherryEmbed\`
> 下同源的 CherryUSB（嵌入式 USB 主从协议栈）与 CherryAVP（MCU 音视频处理库），
> 作者 sakumisu，Apache-2.0。关联项目：laos（AgentOS）、QNN/ADSP（语音情感识别）。

## 一、两个项目是什么

| | CherryUSB | CherryAVP |
|---|---|---|
| 定位 | 带 USB IP 的 MCU 上的**高性能 USB 主从协议栈** | 专为 MCU 设计的**低内存音视频处理库** |
| 结构 | core（主从协议栈核心）/ class（cdc/hid/msc/audio/video/adb/midi…15+ 类驱动）/ osal（6 种 RTOS 适配）/ port（IP 移植层）/ demo | avcodec（ADPCM/AAC/AMR/FLAC/G711/MP3/Opus/Vorbis）/ avfilter / avformat / **avmfcc**（MFCC 特征）/ avswresample / dsp_acc（HPMicro DSP 覆盖） |
| 哲学 | "porting 直连寄存器零抽象 + 零拷贝 + 中断分包"——热路径无封装 | "官方库 + 固定 commit + 统一 API"——换芯片不换接口 |
| 配置 | Kconfig 编译期特性裁剪 | 同（Kconfig） |

## 二、CherryUSB 的四个可迁移设计

### 1. OSAL：内核原语的"六选一"抽象层（最值得学）

`osal/usb_osal_freertos.c / _rtthread.c / _nuttx.c / _threadx.c / _zephyr.c / _liteos_m.c`
——核心协议栈**一个 RTOS 头文件都不 include**，只调 `usb_osal_thread_create /
sem_create / mutex_lock / msleep` 等自定原语；换 RTOS = 换一个 200 行的 osal 文件。

**对 laos 的意义**：laos 的强制层（`sandbox.py`）目前是"Linux 全开 / 其他全关"的
二值降级。学 CherryUSB，把它重写成显式 OSAL：`enforcement_linux_seccomp.py /
enforcement_macos_seatbelt.py / enforcement_stub.py`——核心内核只依赖一个
`enforcement_*` 原语集（wrap/popen_kwargs/cgroup/audit-hook），上 Android、上
WSL、上真实 Linux 都只是"再写一个 osal 文件"。**路线 A（Android 闭环）的工程
障碍会小一半。**

### 2. 类驱动契约：两个回调就是一台"设备"

```c
struct usbh_class_driver {
    const char *driver_name;
    int (*connect)(struct usbh_hubport *hport, uint8_t intf);
    int (*disconnect)(struct usbh_hubport *hport, uint8_t intf);
};
```
加 VID/PID 匹配表，一个 USB 类驱动就注册完成——`class/` 下 15+ 种设备全用这
同一个契约。**对比 laos**：MCP 驱动契约是"一个进程 + 三方法协议"，换来的是隔离
（驱动崩溃不连累内核）；CherryUSB 证明契约可以小到极致，laos 的教训是契约要
**小而稳定**（Task 2 的 popen_kwargs 设计变更波及三个文件，就是因为契约里
混进了传输细节）。

### 3. 热路径零抽象、冷路径全抽象
"Porting 驱动直接对接寄存器，无抽象层封装；分包过程在中断中执行；Memory zero
copy"——**抽象只放在变化频率高的地方**（RTOS、USB IP），数据面（每包的收发）
零开销。laos 的 syscall 网关每调用都要过 5 层闸门 + 审计 JSON 序列化——若将来
要扛真 agent 高频调用，审计应改环形缓冲异步落盘（数据面），闸门（控制面）保持清晰。

### 4. Kconfig + 模板化贡献
`cherryusb_config_template.h` 把"你能配置什么"变成一份可 grep 的清单；class/port
目录里的 `template/` 让贡献者填空。laos 的驱动添加目前靠抄 drv_sys.py——值得
加一个 `drivers/template/`。

## 三、CherryAVP 的三个可迁移设计

### 1. avmfcc：把"每次重写的算法"变成"流式库"
`avmfcc/inc/avp_mfcc.h`：`avp_mfcc_open(config) / avp_mfcc_process(任意长度
PCM16 chunk) / avp_mfcc_close`——内部自己攒帧、窗口滑动，调用方喂流即可。
对比 QNN 项目：`timnet_mfcc.c`（309 行）把同一条 MFCC 管线**焊死在一个传感器里**
（帧长 400/帧移 200/Mel 26 全是宏），换模型要重抄。CherryAVP 的版本配置结构化
（`window.size_ms / filterbank.num_channels / num_coefficients`）、流式、可独立单测。
**对 QNN 项目的意义**：下一个部署直接用 avmfcc 替换私有 MFCC（开源 Apache-2.0，
同为 sakumisu 维护），LPAI Island 约束下它还有 Q15 定点 FFT 路径。

### 2. dsp override：热路径的"平台接管"开关
`dsp_acc/hpmicro/mp3_dsp_override.h`：默认全部走可移植 C；定义
`CONFIG_CHERRYAVP_MFCC_RFFT_OVERRIDE` 时 MFCC 的 FFT 跳到
`avp_mfcc_dsp_rfft_q15`（厂商 DSP 指令实现）。**默认可移植、显式接管加速**——
和"porting 直连寄存器"是同一哲学的两个面。laos 的 `approx_tokens`（中英混合
token 估算，每次 append 都跑）就是该模式的第一候选：默认正则版，接 `tiktoken`
或 C 扩展时开 override。

### 3. 官方源 + 固定 commit 的供应链纪律
README 明言"使用的开源库来源混乱（我们只使用官方库 + 对应 commit 版本）"——
供应链纪律写进项目宪章。laos 目前零依赖是终极形态；将来若引入依赖，照此办理。

## 四、三方（laos × QNN × Cherry）的交叉结合点

1. **MFCC 三兄弟归一**：QNN 的 `timnet_mfcc.c`（私有、焊死）、CherryAVP 的
   `avmfcc`（开源、流式）、laos 的 drv_npu（只传 base64 PCM）。路线 A 的下一
   步可以让 laos 的 `npu.infer` 接受两种输入——原始音频（device 端用 avmfcc
   或 App 内 MFCC 提特征）或现成特征向量——特征提取变成可选的"前端驱动"。
2. **USB 总线变体**：CherryUSB device 模式能让 MCU/调试板把自己枚举成一台
   "AI 传感器 USB 设备"（vendor class），laos 的 drv_npu 走 libusb 对话——
   与 FastRPC（QNN）、HTTP（adb forward）并列的第三种总线。对没有网络/adb 的
   嵌入式板子（HPMicro 等 CherryAVP 目标）这是唯一的接法。
3. **OSAL × 强制层**（见上）：laos 的下一个重构方向。
4. **面试叙事**：CherryUSB 的 OSAL/class-driver、CherryAVP 的 dsp-override、
   QNN 的 LPAI 预算、laos 的 AgentOS 语义层——四段可以串成"端侧 AI 系统的
   分层设计"完整方法论，比单点经验值钱得多。

## 五、一句话各自带走

- **CherryUSB**：抽象层只放在变化频率高的地方；驱动契约小到两个回调；换平台 =
  换一个 osal 文件。
- **CherryAVP**：算法第一次写对就要写成库（配置结构化、流式、可单测）；热路径
  留 override 开关给硬件。
- **对 laos**：强制层 OSAL 化、驱动模板化、审计数据面异步化——三个重构方向都
  有现成教材。
