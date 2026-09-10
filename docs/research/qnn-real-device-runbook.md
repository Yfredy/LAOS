# 真机闭环运行手册 —— laos AgentOS × 骁龙 ADSP 情感识别

> 目标：laos 面板发出的 `npu.infer` syscall 经 adb 到达真机 App，由 **ADSP 上的 QNN
> LPAI 推理**算出 7 类情感概率，结果回到 laos 审计流并扣减风险账本——真实硬件闭环。

## 链路全景

```
浏览器(laos 面板/审计流)
   → kernel.syscall("npu.infer")        # laosd（Windows/Linux，纯标准库）
   → drivers/drv_npu.py                  # LAOS_NPU_ENDPOINT HTTP 传输
   → adb forward tcp:8900 → 手机:8900
   → TimnetLpaiApp InferenceServer.kt    # localhost HTTP（本仓库新增）
   → EmotionClassifier JNI               # 已有
   → QNN LPAI / ADSP                     # 真实硬件推理
   ← 7 类概率 + 真实延迟(ms)             # 原路返回，风险账本扣 2 分
```

## 前置（一次性）

- App 已含本手册配套改动：`InferenceServer.kt`（localhost:8900 推理服务）+
  `INTERNET` 权限 + `EmotionClassifier.isInitialized()`，APK 已重新构建
  （`app/build/outputs/apk/debug/app-debug.apk`，构建成功于 2026-09-09）。
- 电脑侧 laos 仓库：`drivers/drv_npu.py` 支持 `LAOS_NPU_ENDPOINT` 传输（已合入）。

## 连接真机（每次）

```bash
ADB="C:/Users/yaoyue/AppData/Local/Android/Sdk/platform-tools/adb.exe"
"$ADB" devices                      # 确认设备已连接（开 USB 调试）
"$ADB" install -r "C:/Users/yaoyue/Downloads/QNN/SER/SER-Projects/TimnetLpaiApp/app/build/outputs/apk/debug/app-debug.apk"
"$ADB" forward tcp:8900 tcp:8900    # 电脑 8900 → 手机 8900
"$ADB" shell am start -n com.timnet.lpai/.MainActivity   # 启动 App（初始化 QNN）
curl http://127.0.0.1:8900/health   # 期待 {"status":"ok","initialized":true}
```

## 启动 laos 闭环

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos
set LAOS_NPU_ENDPOINT=http://127.0.0.1:8900
python bin\laosweb.py
```

浏览器 `http://127.0.0.1:8800`：审计流里 `npu.devices` 会多出一行
`[OK ] device-timnet (qnn-lpai) model=timnet-lpai initialized=True`。

## 触发一次真实推理

方式一（直接 HTTP，验证链路最短路径）：

```bash
# 生成 3 秒 16kHz 静音 PCM 并 base64（也可换成真录音）
python -c "import base64;print(base64.b64encode(b'\\x00\\x01'*48000).decode())" > pcm.b64
curl -X POST http://127.0.0.1:8900/infer -H "Content-Type: application/json" \
     -d "{\"samples_b64\":\"$(cat pcm.b64)\",\"sample_rate\":16000}"
```

方式二（完整 AgentOS 语义）：面板重跑 demo 后，用 operator 信箱或直接写一个
携带 `caps=["npu.*"]` 的脚本 agent 调 `npu.infer`（backend=device）——审计流出现
`npu.infer ok=True`，**风险账本 spent +2**（功耗定价），AgentProf 会记下真实延迟。

## 录真音频推理（可选）

手机 App 本身仍可正常录音推理（原功能不变）。想让 laos 推理用真实录音：在 App
录一次音，把 PCM 导出（或用 `adb shell screenrecord` 时代的音频工具），转
base64 后走上面方式一。原型阶段静音即可验证闭环。

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `/health` 连接拒绝 | App 未启动或未初始化完 | 等 "Ready - serving :8900" 再试 |
| `adb: no devices` | 未开 USB 调试/未授权 | 手机弹窗允许调试 |
| driver 报 `端点不可达` | adb forward 失效（拔线后） | 重跑 `adb forward tcp:8900 tcp:8900` |
| infer 返回 503 | classifier 未初始化 | App 冷启动需要数秒加载 QNN 上下文 |
| 风险账本 exhausted | irreversibility 预算（默认 3）被推理扣完 | `set LAOS_RISK_BUDGET=20` 后重启面板 |

## 安全提示

InferenceServer 只绑定手机 `127.0.0.1`，仅 adb forward 能从外部访问；无鉴权——
这是调试用的设计选择，不要在公共网络下把 8900 端口暴露出设备。

## 屏幕层（drv_screen）：真机操作

前置：设备已连接（`adb devices` 可见）、`LAOS_ADB` 指向 adb（默认已探测 SDK 路径）。

```bash
# 1. 确认驱动已加载（laosd 启动日志 [screen] 行）
# 2. 面板/agent 调用示例：
#    screen.dump  → 控件树 + 前台包名（只读，不进风险账本）
#    screen.tap {"x":360,"y":1360,"pkg":"com.timnet.lpai"} → 真实点击（计 1 点风险）
#    screen.text {"text":"hello","pkg":"..."} → 输入（空格自动转 %s）
#    screen.shot → var/screen/shot-<ts>.png
```

安全语义：
- `pkg` 参数必须同时通过 ①内核 `pkg:` task_scope 白名单 ②驱动前台包名校验
- 操控类 syscall 全部 `reversible=False`（真机动作不可撤销），每次扣 1 点风险
- 无 task_scope 限制时 pkg 仅由驱动前台校验兜底——建议生产环境总是设置 `pkg:` 作用域
