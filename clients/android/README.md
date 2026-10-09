# laos 安卓客户端（最小 WebView 壳）

> 架构取经 [nanoMuse](https://github.com/nano-muse/nanoMuse)（GPL-3.0——**只学设计，零代码拷贝**，守 laos 的许可边界）：一套 Web UI 服务所有端，每端只留薄壳。本壳约 40 行 Kotlin，完整功能全在服务端 `bin/laosweb.py`。

## 两条路，按需选

### 路 A：PWA（零代码，推荐先用）

laosweb v3 已带 PWA 四件套（manifest/icon/standalone/theme_color）——手机 Chrome 打开 `http://<电脑IP>:8800` → 菜单「添加到主屏幕」即得全屏 App 入口，无需本目录任何构建。

### 路 B：本目录的 WebView 壳 APK（要独立图标/离线壳时）

1. 电脑上启动 laosweb（配好云端大脑，见下）：
   ```bash
   export LAOS_LLM_BASE_URL=https://openrouter.ai/api/v1   # 任意 OpenAI 兼容端点
   export LAOS_LLM_MODEL=<模型名>                            # 如 qwen/qwen3-235b-a22b:free
   export LAOS_LLM_KEY=<你的 key>                            # 本地推理服务可省
   python bin/laosweb.py
   ```
2. 改两处 IP 为你电脑的实际局域网 IP：
   - `app/build.gradle.kts` → `LAOSWEB_URL`
   - `app/src/main/res/xml/network_security_config.xml` → `<domain>`（只认精确 IP，不支持网段）
3. Android Studio 打开本目录（`clients/android/`），Sync → Run，装到手机。

## 设计边界（v0.2）

- 壳做四件事：全屏 WebView + JS/DOM 存储 + 返回键回退 + **laosBridge 语音桥**。
- **语音桥**（v0.2 新增）：`VoiceBridge.kt` 原生 AudioRecord（16kHz 单声道 PCM16 → WAV → base64），JS 侧 `laosBridge.startRecord()/stopRecord()`；**为什么不用 getUserMedia**：Chromium 安全上下文策略禁掉了 http 局域网源上的麦克风采集，而 laosweb 正是局域网 http——原生桥不受限，这也是 nanoMuse"设备能力走原生薄桥"架构的本义。音频只在按下期间进内存，松手上传即焚，不落盘。
- 服务端配 `LAOS_ASR_URL`（OpenAI 兼容 `/audio/transcriptions`，如 Groq 的 whisper-large-v3-turbo 免费档）后，会话卡的 🎙 按住说话、松手自动转写发送；🔇/🔊 切换回复朗读（浏览器 speechSynthesis，本地不出网）。
- 明文 http 只放行你电脑一个 IP（networkSecurityConfig），公网流量一律 https。
- 对话历史在服务端内存（重启即清，但**对话记忆已落库跨重启**——v0.32.0）；审批/审计/记忆/治理四个 tab 与桌面完全同源。
- PWA 路线的 🎙 需要安全上下文（https 或 localhost）——局域网 http 下建议直接用本壳。

## 路线图（后续项，非本壳范围）

- **唤醒词**：端侧 KWS（sherpa-onnx，laos 已实测 7.56ms 零误报）替代按住说话；
- **更多原生桥**：通知/保活（nanoMuse 的 7 厂商保活矩阵已收录在
  [端侧参照手册](../../docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md)，届时照设计自实现）；
- **远程访问**：手机不在局域网时走 Tailscale/frp，不改壳。

## 已知限制

- `onBackPressed` 用了 deprecated API（v0.1 刻意为之——最小依赖；迁移
  `OnBackPressedCallback` 留给加桥的波次）。
- 无图标资源（用系统默认），个人自建够用。
