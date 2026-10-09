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

## 设计边界（v0.1）

- 壳只做三件事：全屏 WebView + JS/DOM 存储 + 返回键回退；**无 JS 桥**——laosweb 本身就是完整 UI，桥是后续项。
- 明文 http 只放行你电脑一个 IP（networkSecurityConfig），公网流量一律 https。
- 对话历史在服务端内存（重启即清）；审批/审计/记忆/治理四个 tab 与桌面完全同源。

## 路线图（后续项，非本壳范围）

- **语音入口**：接 laos 语音栈（wakegate/dialogflow）——壳侧只加录音权限与 JS 桥；
- **原生桥**：toast/通知/保活（nanoMuse 的 7 厂商保活矩阵已收录在
  [端侧参照手册](../../docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md)，届时照设计自实现）；
- **远程访问**：手机不在局域网时走 Tailscale/frp，不改壳。

## 已知限制

- `onBackPressed` 用了 deprecated API（v0.1 刻意为之——最小依赖；迁移
  `OnBackPressedCallback` 留给加桥的波次）。
- 无图标资源（用系统默认），个人自建够用。
