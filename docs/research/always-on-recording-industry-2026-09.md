# 全天候录音业界调研：产品、开源与技术机制

> 调研时间：2026-09-11
> 对象：全天候 / 连续 / 环境录音（always-on / continuous / ambient recording）在消费产品、AI 硬件与开源社区中的应用现状
> 目的：为 laos 的"听觉记忆 / 全天候录音"能力找业界参照——业界到底怎么实现 24/7 录音、哪些开源组件可直接复用、隐私合规如何应对、对 laos 的音频子系统设计有何启示。
> 方法：通用网络搜索 + 官网 / GitHub README / 官方公告 / 权威科技媒体核实。每条事实附来源 URL；标注 ✅官方源已查证 与 🔶第三方/媒体声称。

---

## 1. 一句话结论

**2024–2026 年的全天候录音经历了一场"常开幻想破灭 → 克制版落地"的洗牌。** 纯常开（always-on passive）阵营几乎全部倒下或被平台收购（Rewind→Limitless→Meta、Humane AI Pin→HP；低成本可穿戴 Bee 亦于 2025-07 被 Amazon 收编），存活路径收敛为三条：**按键/VAD 触发 + 本地长续航**（Plaud、讯飞）、**端侧 ASR + 本地向量记忆**（Google Gemini Nano、Apple Intelligence、screenpipe）、**耳机/眼镜形态嵌入持续听觉**（华为 FreeBuds Pro 5、小米音频眼镜、Apple Watch Live Rewind）。开源侧已形成完整可抄管道：Silero VAD → sherpa-onnx / FunASR 流式 ASR → Opus 压缩 → SQLite + 向量库记忆。

---

## 2. 业界图谱：形态 × 处理位置 × 触发方式 × 开源/闭源

| 维度 | 分类 | 代表 |
|---|---|---|
| **形态** | 手机 App | Rewind、Pixel Recorder、Samsung Voice Recorder、讯飞听见、豆包录音纪要 |
| | 录音笔 / 录音卡 | 讯飞 SR 系列、Plaud Note、安克 soundcore Work |
| | 胸针 / 徽章 / 项链 | Limitless Pendant、Omi、Plaud NotePin、Bee、Humane AI Pin |
| | 智能眼镜 | Meta Ray-Ban、小米智能音频眼镜 2、Brilliant Frame/OpenGlass |
| | 耳机 / 耳夹 | 华为 FreeBuds Pro 5、有道 OpenPods、小米耳夹式耳机 |
| | 手表 | Apple Watch（Live Rewind 听觉辅助） |
| **处理位置** | 纯端侧 | Google Pixel Recorder（Gemini Nano）、Apple Intelligence（Private Cloud Compute）、screenpipe、Vosk、sherpa-onnx |
| | 纯云端 | Limitless Pendant、Plaud 转写、腾讯会议录音笔、火山引擎 ASR |
| | 混合 | Omi（可自托管）、讯飞 SR702（云端+离线）、FunASR（端侧+MCP serving） |
| **触发方式** | 常开被动（always-on） | Limitless Pendant、Omi（24h+ 连续捕获）、Rewind（后台捕获） |
| | VAD 门控 | screenpipe、8ta4/say、绝大多数语音助手 |
| | 唤醒词 | Meta Ray-Ban（Hey Meta）、OpenVoiceOS、openWakeWord 生态 |
| | 按键手动 | Plaud NotePin、Bee、讯飞录音笔、Pixel Recorder、小米眼镜（长按镜腿） |
| **开源/闭源** | 完全开源 | Omi（BasedHardware）、screenpipe、sherpa-onnx、FunASR、Silero VAD、whisper.cpp |
| | 部分开源 / 开源 SDK | Porcupine（SDK 开源、模型付费）、openWakeWord（代码 Apache、模型 CC-BY-NC） |
| | 闭源 | Limitless、Meta Ray-Ban、Apple、Google、Plaud、讯飞 |

---

## 3. 消费产品与 AI 硬件

### 3.1 西方产品

#### 3.1.1 Rewind → Limitless → Meta（常开幻想的完整生命周期）

这是全天候录音领域最具代表性的案例，完整经历了"理念爆发 → 转型云端 → 被平台收购 → 产品停服"四阶段。

- **Rewind.ai（2022–2024）**：macOS 后台 App，持续捕获屏幕 + 麦克风/系统音频，以"mind-boggling compression"（10GB 录制约压缩到 <3MB）和"数据永不出设备"为卖点。✅官方源已查证（rewind.ai 历史页）
- **改名 Limitless（2024）**：产品方向从纯 Mac 本地 App 转向云端 + 硬件 Pendant。✅官方源已查证（rewind.ai/what-happened-to-rewind）
- **Limitless Pendant**：约 32mm 直径铝制圆形徽章，多麦克风阵列，**常开被动录音**，无按键；音频上传云端转写；官方宣称 ~100 小时续航，第三方实测真实录音约 6–7 小时；隐私政策明确"we will receive audio recordings"。🔶第三方/媒体声称（vibe.us、aiwiki）
- **被 Meta 收购（2025-12-05）**：CEO Dan Siroker 发信确认，团队并入 Reality Labs。✅官方源已查证（limitless.ai 公告）
- **停服（2025-12-19）**：Rewind Mac/iPhone App 禁用全部屏幕与音频捕获功能；Pendant 停售；存量用户保留支持至少 12 个月，订阅转免费。✅官方源已查证（9to5Mac 引述官方邮件）

**关键教训**：以"本地处理"建立信任 → 转向云端 → 被以广告变现著称的 Meta 收购，用户信任链断裂。这是"常开录音 + 纯云依赖"商业模式的致命问题。

来源：https://rewind.ai/what-happened-to-rewind/ ；https://limitless.ai/ ；https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/

#### 3.1.2 Omi（BasedHardware 开源硬件）

- **前身**：Kickstarter 上原名 Friend，因另一旧金山硬件厂商发布同名产品并以 $1.8M 购得 friend.com 域名，为避免混淆于 2025-01（CES 期间）改名 Omi；GitHub 仓库/文档于 2025-02 完成 Friend→Omi 重命名（issue #1801、PR #1149）。创始人 Nik Shevchenko（Thiel Fellow）。🔶第三方/媒体声称（desiblitz、GitHub）
- **硬件规格（消费版）**：nRF5340 双核 BLE SoC + nRF7002 Wi-Fi 6、2× TDK T5838 PDM 麦克风、8GB NAND、150mAh LiPo。✅官方源已查证（docs.omi.me）
- **触发方式**：24h+ 连续捕获；硬件无唤醒词，App 侧实时转写。✅官方源已查证（GitHub README）
- **处理位置**：App 调用云端模型（GPT-4o 等）做实时转写与摘要；**完全开源**，可自托管后端、自选模型。✅官方源已查证
- **续航**：官方称 24h+ 连续捕获；支持离线录音（本地先存，事后 10–20s 完成离线转写），实时模式延迟 500–2000ms。✅官方源已查证（omi.me）
- **2026 现状**：活跃销售（Omi Dev Kit 2，2025-08 起推出 Unlimited 订阅）；GitHub README 称 "Trusted by 300,000+ professionals"（官方口径为**用户数**而非开发者数），仓库 36,000+ commits，社区 250+ App。✅官方源已查证

来源：https://github.com/basedhardware/omi ；https://docs.omi.me/doc/hardware/consumer ；https://www.omi.me/products/omi-dev-kit-2

#### 3.1.3 Plaud NotePin / Note

- **形态**：胸针/项链/腕带/夹扣四戴法，51×21×11mm，16.6g。✅官方源已查证
- **触发方式**：**物理按键手动录音**（press to record），**非常开**。✅官方源已查证
- **转写**：Plaid Intelligence 云端，112 种语言、说话人分离；免费 Starter 计划 300 分钟/月。✅官方源已查证
- **续航/存储**：NotePin 270mAh，连续录音 20 小时、待机 40 天；**64GB 本地存储**（约 480 小时音频）。✅官方源已查证
- **2026 现状**：活跃销售，持续迭代 NotePin S 等新型号。✅官方源已查证

来源：https://global.plaud.ai/products/plaud-notepin ；https://tw.plaud.ai/products/notepin

#### 3.1.4 Bee（bee.computer）

- **创始人**：Maria de Lourdes Zollo 与 Ethan Sutin（2022 年创立于旧金山）。✅官方/权威源已查证（Amazon 官方博客、澎湃新闻）
- **形态**：腕带 / 胸针夹（黄色硅胶腕带可拆，配黑色衬衫夹）；USB-C 充电。
- **触发方式**：**按键开始/停止**，LED 绿色=正在录制、灭=未录制；公司描述为 "always-on hardware"，但实际由按键触发会话。🔶第三方/媒体声称
- **续航**：官方宣称 **160 小时（约 7 天）**。✅官方源已查证（bee.computer）
- **处理位置**：实时处理，**不保存原始音频**，只保留转写/摘要/提醒等派生数据。🔶第三方/媒体声称
- **被 Amazon 收购（2025-07-22 官宣）**：团队全员收到 Amazon Devices & Services 加入邀约，交易条款未披露；$49.99 硬件 + 订阅模式不变。✅官方/权威源已查证（Amazon 官方、The Verge、澎湃新闻）
- **2026 现状**：**被 Amazon 收购后继续迭代**——2026-01 Amazon 官方博客披露已上线 Voice Notes、Actions（连接邮件/日历）、Daily Insights 等功能；"实时处理、不存原始音频"的隐私口径保留；作为独立消费品牌的路线图已并入 Amazon ambient AI 产品线。✅官方源已查证

来源：https://bee.computer/ ；https://www.aboutamazon.com/news/devices/bee-amazon-wearable-ai-device-new-features ；https://www.thepaper.cn/newsDetail_forward_31240075 ；https://www.latent.space/p/bee

#### 3.1.5 Meta Ray-Ban 智能眼镜

- **形态**：Wayfarer/Headliner 镜框；Gen 2 为 5 麦克风阵列 + 12MP 摄像头 + 开放式扬声器；2025-09 发布 Ray-Ban Display（右镜片微投影 + "Neural Band" 肌电感应）。🔶第三方/媒体声称
- **触发方式**：**常开麦克风监听唤醒词 "Hey Meta"**，低功耗端侧检测唤醒词后才上流云处理；录制/拍照由按键或语音触发。🔶第三方/媒体声称
- **隐私争议**：
  - 汉堡数据监管机构认定眼镜使旁观者在未同意情况下被采集。🔶第三方/媒体声称（ppc.land，2026-09-10）
  - 2025-04 起欧洲默认 opt-out 用于 AI 训练。
  - 2026-07-07 强制固件更新：LED 被物理篡改即关停摄像头（消费级可穿戴首个 camera-kill）。✅官方源已查证（Meta《Bystander Privacy》）
  - 肯尼亚外包标注丑闻："Hey Meta"拍摄的视频被发往肯尼亚外包公司人工审核，内容含浴室/更衣室片段。🔶第三方/媒体声称
- **市场地位**：Counterpoint 数据显示 2025 H1 Meta 占全球智能眼镜出货 73%。🔶第三方/媒体声称
- **2026 现状**：活跃迭代。

来源：https://about.fb.com/wp-content/uploads/2026/07/Bystander-Privacy.pdf ；https://ppc.land/hamburg-regulator-finds-ray-ban-meta-glasses-expose-bystanders-without-consent/ ；https://www.softwareseni.com/privacy-trust-and-the-architecture-of-ai-smart-glasses/

#### 3.1.6 Humane AI Pin（已关停，反面教材）

- **形态**：胸前方形别针，高通骁龙，无屏幕，激光投影至手掌；麦克风 + 摄像头。🔶第三方/媒体声称
- **关停原因**：2024-04 上市即口碑差（续航 <8h、体验缺陷、AI 幻觉），累计销售仅约 700 万美元。🔶第三方/媒体声称（ars technica 2024-06）
- **结局**：2025-02 HP 以约 1.16 亿美元收购资产/团队/IP（不含硬件产品）；2025-02-28 服务器关停，设备变砖；绝大多数用户无退款。✅官方/权威源已查证（Ars Technica、Digital Trends）
- **对全天候录音的启示**：纯云依赖 + 胸前常开麦克风 + 激光投影的组合被市场证伪；证明硬件续航、隐私社交接受度、离线可用性是硬约束。

来源：https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/

#### 3.1.7 Apple

- **语音备忘录转录**：iOS 起支持实时转写，iPhone 12 及以上，支持 10+ 语言（含简中/繁中）。✅官方源已查证（support.apple.com）
- **Apple Intelligence 音频摘要**：iOS 18 起在"备忘录"与"电话"App 中录制、转录、摘要；通话录音时**自动告知对方**。需 iPhone 16 / 15 Pro。✅官方源已查证（apple newsroom 2024-10）
- **处理位置**：Apple Intelligence 端侧优先，敏感音频处理走 Private Cloud Compute。✅官方源已查证
- **AirPods Pro 2/3 听觉健康**：Hearing Test、OTC Hearing Aid、**Conversation Awareness（对话感知）**——是"环境声感知/对话增强"而非录音。✅官方源已查证
- **Apple Watch Audio Intelligence（2026）**：端侧识别警笛、婴儿哭、门铃并主动通知（听觉辅助），非录音。🔶第三方/媒体声称
- **方向判断**：Apple 走"按需录音 + 端侧摘要"路线，**未做常开 ambient recording**。

来源：https://support.apple.com/en-in/guide/iphone/iph00953a982/ios ；https://www.apple.com/hu/newsroom/2024/10/apple-intelligence-is-available-today-on-iphone-ipad-and-mac/ ；https://www.apple.com/airpods-pro/hearing-health/

#### 3.1.8 Google Pixel Recorder

- **形态**：Pixel 手机自带 App。
- **触发方式**：**手动按键录音**（非常开）；UI 提示 "Record respectfully around others"。🔶第三方/媒体声称
- **转写**：**端侧离线实时转写**（Tensor 芯片），说话人分离；Pixel 8 及以上支持 AI 摘要。✅官方源已查证
- **Gemini 集成**：Recorder "Summarize" 由 **Gemini Nano 端侧**完成，无需联网。✅官方源已查证（blog.google）
- **方向判断**：端侧 VAD + Gemini Nano 摘要，**不做 always-on ambient 录音**。

来源：https://blog.google/products-and-platforms/devices/pixel/pixel-drop-march-2025/ ；https://store.google.com/intl/de/ideas/articles/gemini-nano-offline/

#### 3.1.9 Samsung Galaxy AI（Transcript Assist）

- **形态**：Galaxy 手机自带 Voice Recorder / Samsung Notes。
- **触发方式**：手动录音；One UI 7 起通话录音可一键开启。✅官方源已查证
- **能力**：Transcript Assist 转写 + 说话人分离 + 摘要 + 翻译；S25 系列 Call Transcript 抽取要点。✅官方源已查证
- **处理位置**：宣称 on-device（"directly on your device"）；早期部分功能云端，2025-07 起部分地区转为端侧。✅官方源已查证

来源：https://www.samsung.com/us/support/answer/ANS10004613/ ；https://www.samsung.com/in/support/mobile-devices/how-to-use-call-transcript-feature-in-galaxy-devices/

### 3.2 中文生态

#### 3.2.1 科大讯飞

- **产品形态**：AI 录音笔 SR 系列（SR302 / SR502 星火版 ¥2499 / SR702 星火版 ¥3999，64GB+20GB 云存储），新款 S6 系列、Pokee 系列、Magic；AI 录音卡；讯飞听见 App/网页。✅官方源已查证（iflytekrecord.com）
- **触发方式**：**按键手动录音**（非常开）；SR702 支持远程录音（手机 App 远端触发）。
- **处理位置**：**混合**——在线转写走云端星火大模型；SR702 支持**离线转写**（端侧），主打"机密高度保密"。✅官方源已查证
- **准确率**：官方称 2025 年第三方机构实测 S6/Pokee/Magic 在线普通话转写准确率 **98.6%**；支持 12 种中文方言 + 多语种 + OCR。✅官方源已查证（iflytekrecord.com/Aboutzation/141）
- **2026 现状**：活跃；S6 系列获 2025 Red Dot 红点奖。✅官方源已查证

来源：https://www.iflytekrecord.com/Aboutzation/141.html ；https://www.iflytekrecord.com/Goods/1.html

#### 3.2.2 华为

- **FreeBuds Pro 5（2025-11-28 发布）**：首款 HarmonyOS 6 TWS，**新增 AI 录音转写**——通话/会议时自动录音转写、识别发言人、生成摘要、摘要同步日历待办；支持最长 **200 分钟录音**，星闪秒级回传。✅官方/权威源已查证（中新网、环球网）
- **手机（Mate/Pura 系列）**：系统录音机 App + 小艺；AI 字幕（实时将视频/语音转字幕，多语言，说话人识别）。🔶第三方/媒体声称
- **处理位置**：未明确披露端/云划分，鸿蒙生态以本地处理 + 小艺云结合。
- **2026 现状**：活跃，耳机端录音转写是 2025 下半年新方向。

来源：http://www.chinanews.com.cn/cj/2025/11-28/10522958.shtml ；https://tech.huanqiu.com/article/4PIL8sqJlVx

#### 3.2.3 小米

- **手机（HyperOS）**：录音机 App 支持**实时文字转录、自动识别说话人、录音摘要、中英德俄法韩双语翻译**。✅权威源已查证（腾讯新闻 MIX Flip 评测）
- **小米智能音频眼镜 2（2025-11）**：长按镜腿触发现场/通话录音，**录音时亮灯提醒**（隐私设计），随录随存，米家眼镜 App 管理。✅权威源已查证（新浪科技）
- **Xiaomi 耳夹式耳机（2026-05）**：耳机本体与充电盒均可录音，配合 App 转写并生成智能摘要；小爱陪伴模式。🔶第三方/媒体声称
- **2026 现状**：活跃，眼镜 + 耳机是录音硬件新载体。

来源：https://tech.sina.cn/2025-11-30/detail-infzeuyy5004914.d.html ；https://view.inews.qq.com/a/20250628A0220Q00

#### 3.2.4 网易有道

- **词典笔 X8 系列（2026-06）**：课堂笔记功能——单条最长 90 分钟录音（会员），录音 + 抓拍板书自动生成结构化 AI 笔记（全文转写、摘要、知识点微课、思维导图）。✅官方/权威源已查证（中国教育在线）
- **OpenPods AI 耳机（2026-08-27 预售，¥1499）**：定位"戴在耳朵上的同传"+ iPhone Agent 耳机；一键通话录音、AI 会议助手、十几种语言实时互译；录音结束自动转写、区分发言人、输出结构化纪要/待办/思维导图；耳机舱可当录音卡/翻译机。✅权威源已查证（新华网、深圳新闻网）
- **处理位置**：云端 AI 转写为主（订阅制）。
- **2026 现状**：活跃，从教育硬件转向办公音频工作流。

来源：http://www.xinhuanet.com/tech/20260829/8fc452655ed141a7971f29899398f58f/c.html ；http://www.sznews.com/news/content/2026-09/10/content_32168566.htm

#### 3.2.5 其他中文产品

- **安克 soundcore Work "AI 录音豆"**：磁吸在手机背面的录音卡，**字节豆包大模型驱动转写**，飞书多模态理解；实时总结、声纹区分说话人、自动关联飞书日程。🔶第三方/媒体声称
- **腾讯会议"录音笔"**：腾讯会议 App 内置纯音频录制工具（v3.30+），实时转写文字，录制结束留存本地。✅官方源已查证（meeting.tencent.com 帮助中心）
- **豆包 App "录音纪要"**：豆包 App/PC 端内置，支持现场会议、微信语音会议、腾讯会议；实时转写、自动生成纪要、导出逐字稿；免费。🔶第三方/媒体声称
- **火山引擎/豆包语音（B 端）**：流式语音识别 + 大模型录音文件识别（≤4h），是上述硬件的底层 ASR。✅官方源已查证（volcengine.com）

### 3.3 消费产品总对比表

| 产品 | 形态 | 触发方式 | 处理位置 | 续航 | 隐私设计 | 2026 现状 |
|---|---|---|---|---|---|---|
| Rewind.ai | Mac/iPhone App | 常开后台 | 早期纯端侧 | N/A | 本地存储承诺 | **已停服**，并入 Meta |
| Limitless Pendant | 胸针/挂绳 | **always-on 被动** | **纯云端** | 官方 100h / 实测 6–7h | Consent Mode、Confidential Cloud | **停售**，并入 Meta |
| Omi | 项链/胸针 | 24h+ 连续捕获 | 混合（**可自托管开源**） | 24h+ | 完全开源、可选端侧 | **活跃** |
| Plaud NotePin | 胸针/项链/腕带 | **物理按键手动** | 云端 + 64GB 本地 | 20h 录音 / 40 天待机 | 本地为主、Find My | **活跃** |
| Bee | 腕带/胸针夹 | 按键触发，LED 指示 | 实时、**不存原始音频** | 160h / 7 天 | LED 绿=录、不存 raw | **被 Amazon 收购**（2025-07），并入后持续迭代 |
| Meta Ray-Ban | 眼镜 | 唤醒词常开监听 | 唤醒端侧，查询上云 | 全天 | LED tamper detection、欧洲 opt-out | **活跃** |
| Humane AI Pin | 胸前别针 | 按住激活 | **纯云** | <8h | 无 | **已关停变砖**，HP 收 IP |
| Apple | iPhone + AirPods | 手动；对话感知非录音 | **端侧 + PCC** | N/A | 通话录音自动告知对方 | **活跃** |
| Google Pixel Recorder | Pixel App | 手动 | **端侧 Gemini Nano** | N/A | 离线可用、"record respectfully" | **活跃** |
| Samsung | Galaxy App | 手动 / 通话一键 | 端侧（宣称） | N/A | 通话录音规范告知 | **活跃** |
| 科大讯飞 SR | 录音笔/录音卡 | 按键（含远程） | **混合**：云端 + SR702 离线 | 超长待机 | 离线转写保密 | **活跃** |
| 华为 FreeBuds Pro 5 | TWS 耳机 | 按键/通话自动 | 鸿蒙混合 | 耳机录音 200min | 未重点披露 | **活跃** |
| 小米（眼镜 2 / 耳夹 / 手机） | 眼镜 + 耳机 + 手机 | 长按镜腿/按键 | 云端转写 | 未核 | **录音亮灯提醒** | **活跃** |
| 有道 OpenPods / X8 | AI 耳机 + 词典笔 | 一键录音 | 云端（订阅制） | 未核 | 麦克风式耳戴 | **活跃** |
| 安克 soundcore Work | 磁吸手机背卡片 | 按键 | 豆包大模型云 + 飞书 | 未核 | 飞书生态授权 | **活跃** |
| 腾讯会议"录音笔" | 会议 App 内置 | 会议内手动录制 | 云端实时转写 | N/A | 录制结束留存本地 | **活跃** |

---

## 4. 开源项目生态

### 4.1 流式 / 连续 ASR 框架

| 项目 | 仓库 | Star(约) | 许可证 | 流式 | 端侧 | 核心特点 | laos 可复用性 |
|---|---|---|---|---|---|---|---|
| **sherpa-onnx** | k2-fsa/sherpa-onnx | 14.7k | Apache-2.0 | ✅原生 | 纯端侧 | **一站式**：ASR(流式+非流式)+TTS+说话人 diarization+VAD+语音增强+声源分离；int8 Zipformer RTF≈0.078–0.123；多平台(Android/iOS/Web/嵌入式/NPU) | **极高** |
| **FunASR** | modelscope/FunASR | 16k+ | MIT(代码) | ✅WebSocket | 端侧 | 工业级中文 ASR；Paraformer-zh-streaming(chunk 600ms)；FSMN-VAD；标点；说话人 diarization；CPU 170x 实时；**原生 MCP 服务** | 高 |
| **faster-whisper** | SYSTRAN/faster-whisper | 20k+ | MIT | 后端 | 端侧 | Whisper 的 CTranslate2 重实现，4x 快、减半显存；非流式但常被流式框架包装 | 高 |
| **whisper_streaming** | ufal/whisper_streaming | 1k+ | MIT | ✅原生 | 端侧 | LocalAgreement / adaptive latency 策略，streaming Whisper 事实 baseline；论文 arXiv:2307.14743 | 高 |
| **Vosk** | alphacep/vosk-api | 14k+ | Apache-2.0 | ✅原生 | 端侧 | 离线 STT，20+ 语言(含中文)，模型 50MB–1GB，原生流式 API 返回 partial result，Raspberry Pi 可跑 | 高 |
| **SenseVoice** | FunAudioLLM/SenseVoice | 8k+ | MIT(代码) | 伪流式 | 端侧 | 多任务：ASR+LID+情感识别(SER)+音频事件检测(AED)；中/粤/英/日/韩；超快(15x 实时以上) | 高 |
| **WhisperLive** | collabora/WhisperLive | 5k+ | MIT | 近实时 | 均可 | near-live Whisper 转写，WebSocket server/client 分离，faster-whisper 后端；支持多客户端 | 中 |
| **whisper.cpp** | ggml-org/whisper.cpp | 40k+ | MIT | 示例级 | 端侧 | Whisper 的 C/C++ port，纯 CPU 可跑；examples/stream/ 是经典麦克风实时转写 demo；含 OpenAI API 兼容 server | 中 |
| **SpeechBrain** | speechbrain/speechbrain | 8.2k | LGPL-3.0 | 研究级 | 端侧 | 研究向语音工具包，ASR/说话人/增强/分离全有；Conformer-Transducer 流式 recipe | 中 |
| **NVIDIA NeMo** | NVIDIA-NeMo/NeMo | 10k+ | Apache-2.0 | ✅原生 | GPU 服务 | 训练+推理工具包；Nemotron-3.5-ASR-Streaming-0.6B(40 语言，80ms–1s 延迟可调)；生产级但依赖 GPU | 中 |
| **openai/whisper** | openai/whisper | 108.6k | MIT | ❌ | 端侧 | 30s 块非流式；99 语言；事实标准模型；2022 后基本冻结 | 低(模型权重) |
| **Coqui STT** | coqui-ai/STT | 10k+ | MPL-2.0 | ✅ | 端侧 | **已停止维护**（README 明示，建议迁移 Whisper） | 低 |

**关键发现**：sherpa-onnx 是最接近 laos 音频子系统需求的"一站式"开源库——VAD、声源分离、说话人识别、流式 ASR 全部内置，纯端侧，Apache-2.0 许可，且 2026-09 仍在高频更新。FunASR 是中文场景首选，且其原生 MCP serving 模式与 laos 的"MCP Server 作为设备驱动"理念一致。

来源：https://github.com/k2-fsa/sherpa-onnx ；https://github.com/modelscope/FunASR ；https://github.com/SYSTRAN/faster-whisper ；https://github.com/ufal/whisper_streaming ；https://github.com/alphacep/vosk-api ；https://github.com/FunAudioLLM/SenseVoice

### 4.2 开源个人记忆 / 全天候录音项目

#### 4.2.1 screenpipe（Rewind 开源替代事实标准）

- **仓库**：https://github.com/screenpipe/screenpipe （YC S26）
- **Star**：约 20k+；"shipping daily"，2026-09 仍有 commit
- **许可证**：MIT（source-available）
- **语言**：Rust 核心 + TypeScript
- **核心**：**24/7 屏幕+音频连续捕获**，本地 SQLite + mp4，accessibility tree + OCR，本地 Whisper 转写（Large-V3-Turbo），说话人 diarization，语义/全文搜索，Ollama 集成，开发者 API。Mac/Win/Linux。
- **laos 可复用性：极高** —— 这就是 laos `drivers/rec` + 记忆层的 closest 开源参照；Rust 管道设计、SQLite schema、VAD→Whisper 流水线都值得直接抄。

#### 4.2.2 其他个人记忆项目

| 项目 | 仓库 | 核心 | laos 可复用性 |
|---|---|---|---|
| **mem0** | mem0ai/mem0 (64.8k⭐) | AI Agent 记忆层(user/session/agent 三级)，从文本对话抽取事实；非音频原生，issue #5506 讨论加 FunASR/SenseVoice | 中（记忆抽取/检索层可借鉴） |
| **BasedHardware/Omi** | BasedHardware/Omi (15k⭐) | 开源 AI 可穿戴项链，24h+ 连续录音，BLE 流式音频到手机，实时转写摘要；硬件设计文件全开源 | 高（硬件+固件+后端协议栈完整） |
| **Windrecorder** | yuka-friends/Windrecorder (5k⭐) | Windows 上的 Rewind 替代，屏幕小帧 + OCR + 图像描述，本地运行 | 低（偏屏幕） |
| **8ta4/say** | 8ta4/say (89⭐) | 全天候音频记录，Deepgram nova-3 流式 + Silero VAD on-device 预过滤 | 中（VAD→云端 STT 架构样本） |
| **LocalRecorder** | drequil/LocalRecorder | Whisper 本地 + 分层摘要(hour→day→week) + Markdown 存储 | 中（schema 可参考） |
| **infinite-recall** | mjaverto/infinite-recall | macOS，WhisperKit 本地，SQLite，Omi-shaped REST API 给 MCP 客户端 | 中 |
| **Recall** | trevhud/recall | macOS 会议录制，Whisper + pyannote diarization + Ollama | 中 |

来源：https://github.com/screenpipe/screenpipe ；https://github.com/mem0ai/mem0 ；https://github.com/BasedHardware/Omi

### 4.3 开源语音助手的常开麦克风实现

| 项目 | 仓库 | 状态 | 核心 | laos 可复用性 |
|---|---|---|---|---|
| **OpenVoiceOS** | OpenVoiceOS/ovos-core | 活跃（Mycroft 社区延续） | 完整语音助手栈：mic → VAD plugin → wakeword plugin(precise-lite/vosk/openwakeword) → STT → intent → TTS；插件化架构 | 中（插件化架构对 MCP 驱动设计有参考价值） |
| **openWakeWord** | dscripka/openWakeWord (3k⭐) | 维护中，v0.6.0 | 开源唤醒词框架，预训练 hey_jarvis 等模型，支持自训练；TFLite；Home Assistant 默认 | 高（常开麦克风第一级触发器，纯 Python，可直接挂 MCP） |
| **Porcupine** | Picovoice/porcupine (2k⭐) | 活跃 | 商业级唤醒词，97.3% 准确率，树莓派 5 CPU 占用 0.6%，可跑在 Cortex-M 单片机上；SDK Apache-2.0，**模型/自定义唤醒词需 AccessKey 商用付费** | 中（性能好但有许可陷阱） |
| **Mycroft Precise** | MycroftAI/mycroft-precise (4k⭐) | 官方冻结，社区 precise-lite | RNN 唤醒词引擎，轻量，可自训练 | 中（被 openWakeWord 取代） |
| **Rhasspy** | rhasspy/rhasspy (2.75k⭐) | **v2 archived** | 完全离线语音助手，MQTT/Hermes 协议拼装 STT/NLU/TTS；核心维护者现就职 Nabu Casa，实质被 Home Assistant Wyoming 生态吸收 | 低（历史参考；架构思想仍有价值） |
| **Wyoming Satellite** | rhasspy/wyoming-satellite | **deprecated** | 卫星(麦克风+喇叭)与中央 STT/TTS/wakeword 服务之间的 JSON+音频 socket 协议；每个卫星本地跑 openWakeWord | 中（"常开麦克风卫星"协议设计可参考） |
| **Snowboy** | Kitt-AI/snowboy (9k⭐) | **2020-12 关停** | 历史上最流行的自定义唤醒词引擎；社区 fork seasalt-ai/snowboy 维护训练模块 | 低（不要新项目用） |

来源：https://github.com/OpenVoiceOS/ovos-core ；https://github.com/dscripka/openWakeWord ；https://github.com/Picovoice/porcupine

### 4.4 开源智能眼镜 / 可穿戴

| 项目 | 仓库 | 核心 | laos 可复用性 |
|---|---|---|---|
| **OpenGlass** | BasedHardware/OpenGlass (3k⭐) | <$25 现成元件把普通眼镜改成智能眼镜，ESP32-S3 + 摄像头 + 麦克风 | 中（硬件 BOM 与固件参考） |
| **Brilliant Frame** | brilliantlabsAR/frame-codebase | nRF52 + FPGA，单 MEMS 麦克风，Micropython/Lua on-device，BLE 通信 | 中（BLE 音频流式协议可参考） |
| **Brilliant Halo** | brilliantlabsAR/halo-firmware | Alif Balletto SoC + Zephyr RTOS + Lua VM，**双麦 + 音频活动检测(AAD)硬件级低功耗唤醒**，骨传导，14h 电池 | 中（低功耗常开麦克风硬件设计参考） |

来源：https://github.com/BasedHardware/OpenGlass ；https://github.com/brilliantlabsAR/frame-codebase

### 4.5 VAD / 音频处理基础库

| 项目 | 仓库 | 许可证 | 核心 | laos 可复用性 |
|---|---|---|---|---|
| **Silero VAD** | snakers4/silero-vad (15k⭐) | MIT | 深度学习 VAD，模型 ~2MB，30ms chunk <1ms CPU，ONNX 推理再快 4-5x；screenpipe/omi/say 都用它 | **极高**（24/7 常开麦克风事实标准 VAD） |
| **WebRTC VAD** | wiseman/py-webrtcvad | BSD-3 | 经典 VAD，20ms 帧，4 档激进度，纯 C，极轻量；准确率 ~86% | 高（久经考验） |
| **RNNoise** | xiph/rnnoise (5k⭐) | BSD-3 | RNN 噪声抑制，毫秒级，极轻量 | 高（人声分离前的预处理） |
| **SpeexDSP** | xiph/speexdsp | BSD-3 | **AEC(声学回声消除)+噪声抑制+AGC+VAD** 四位一体；成熟、专利免费 | 高（drivers/audio 的 AEC 实现可直接用） |
| **Opus** | xiph/opus | BSD-3+专利免费 | 交互式音频编码，帧长 2.5–60ms，最低 5ms 延迟；BLE/流式音频事实标准 | 高（mic→ear 低延迟传输编码） |

来源：https://github.com/snakers4/silero-vad ；https://github.com/xiph/rnnoise ；https://github.com/xiph/speexdsp ；https://github.com/xiph/opus

### 4.6 开源可抄的管道推荐

基于 laos 现有 `drivers/mic` → `drivers/audio`(AEC+人声分离) → VAD → `drivers/ear`(ASR) → `drivers/rec`(日志) 的分层，推荐组件组合：

**最低功耗常开层**
- 第一遍：**SpeexDSP**（AEC+AGC+NS）
- 语音段切分：**Silero VAD**（<1ms/chunk，2MB 模型，screenpipe/omi 都用它）
- 备选显式唤醒词：**openWakeWord**（如果 laos 也要指令式交互）

**ASR 层（与 laos `drivers/ear` 双通道完美对应）**
- **流式近实时通道**：**sherpa-onnx**（首选，端侧、含 VAD/说话人分离/声源分离一站式）或 **FunASR** Paraformer-zh-streaming（中文最佳、原生 MCP serving）
- **高精度异步通道**：**faster-whisper**（CTranslate2，4x 加速）跑 30s 块做二次校准；**SenseVoice** 做情感/事件标签
- **伪流式策略**：抄 **whisper_streaming** 的 LocalAgreement（self-adaptive latency）——不要固定 1s 分片

**降噪/编码**
- **RNNoise** 做二次降噪；**Opus**（16kbps）做 mic→ear 的低延迟流式编码

**记忆层**
- 直接抄 **screenpipe 的 SQLite schema**（`audio_transcriptions` 表：timestamp、speaker、text、offset）+ **mem0** 的"事实抽取"思路
- 说话人：sherpa-onnx 的 CAM++ / pyannote.audio

**不建议抄的**：Snowboy（停更）、Coqui STT（停更）、Rhasspy（archived）、openai/whisper 原版（慢）。

---

## 5. 技术机制拆解

### 5.1 VAD + 唤醒词 + 流式 ASR 标准流水线

常开听觉设备的经典三层门控：

```
麦克风 PCM
  ↓
[VAD] 常驻运行，判断"有没有人说话"——端点检测、barge-in、只对语音段做后续处理
  ↓ (语音段)
[唤醒词/KWS] 极低功耗，检测"Hey Siri"/"Hey Meta"/自定义词后才激活主 ASR
  ↓ (唤醒命中 或 VAD 门控的语音段内)
[流式 ASR] 实时转写，输出 partial + final 结果
  ↓
转写文本 → 向量嵌入 → 记忆检索
```

**各层开源组件实测指标：**

| 组件 | 典型指标 | 来源 |
|---|---|---|
| Silero VAD | 模型 ~2MB；单帧处理延迟 ~0.8ms；准确率 ~99%；ONNX 推理 batch=4 仅 4ms | https://github.com/Kai-Karren/silero-vad |
| WebRTC VAD | 准确率 ~86%，单帧 ~2.3ms；libVAD 已不维护 | https://theneuralbase.com/conversational-ai/learn/intermediate/voice-activity-detection/ |
| Porcupine 唤醒词 | 97.3% 唤醒准确率（1 次误报/10 小时、10dB SNR）；树莓派 5 CPU 占用 0.6%；可跑在 Cortex-M 单片机 | https://picovoice.ai/products/voice/wake-word/ |
| sherpa-onnx 流式 Zipformer | int8 在 2 线程上 RTF≈0.078–0.123（1 秒音频耗时 0.08–0.12 秒） | https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html |
| faster-whisper streaming | 约落后实时 1.5s | https://github.com/bhargavchippada/faster-whisper-dictation |
| 云侧流式 ASR | Google Chirp 200–400ms / WER 7–9%；AssemblyAI 150–300ms / 6–8% | https://www.yashchudasama.com/blog/ai/realtime-ai-pipelines/ |

**典型端侧延迟预算**（小模型栈实测）：VAD 帧窗 32ms → 端点静音 300ms → STT tiny.en 短段 50–150ms（CPU 4 线程）→ 本地小 LLM TTFT 30–80ms。合计端到端语音→文字约数百毫秒。来源：https://docs.rs/crate/skadoosh/0.4.0

### 5.2 端侧 vs 云侧转写

| 维度 | 端侧转写 | 云侧转写 |
|---|---|---|
| 延迟 | 流式数百 ms–1.5s（受模型大小制约） | 150–400ms（网络往返+服务端解码） |
| 隐私 | 音频不出设备，合规友好 | 音频离端，受各国录音/跨境传输监管 |
| 成本 | 无按分钟计费；一次部署 | 按分钟计费（Limitless 月赠 1200 分钟约只够 3 天全天录音） |
| 准确率 | 小模型 WER 略高；1B 参数 Whisper 经优化可匹敌 gpt-4o-transcribe | 前沿模型略优 |
| 模型大小 | 27M–1B 参数，需量化/蒸馏 | 无本地体积约束 |
| 适用 | 隐私敏感、离线、7×24 低功耗、带宽受限 | 最高准确率、多说话人、复杂口音 |

**2024–2026 端侧化关键进展：**
- **WhisperKit**（Apple 设备）：约 1B 参数在 Apple 端侧实时流式转写，声称匹配或超过 gpt-4o-transcribe（2025）。arXiv 2507.10860
- **Edge-ASR 量化**：对 Whisper 与 Useful Sensors Moonshine（27M–244M 参数）做训练后量化，面向常开低功耗边缘设备。arXiv 2507.07877
- **EdgeSLU（ACM 2025）**：1.58-bit 混合精度量化 + SIMD 内核，树莓派 5 上 STT 仅需 35MB RAM、2.1s 延迟、6.37% WER。https://dl.acm.org/doi/pdf/10.1145/3746252.3761477
- **AMD Ryzen AI NPU**：2025 年起官方支持 Whisper 经 NPU 实时转写。https://www.amd.com/en/developer/resources/technical-articles/2025/unlocking-on-device-asr-with-whisper-on-ryzen-ai-npus.html

### 5.3 24/7 续航支撑技术

**(a) 低功耗常开硬件（AON / Sensing Hub / 音频协处理器）：**

| 硬件 | 核心设计 | 来源 |
|---|---|---|
| Qualcomm Sensing Hub + Hexagon DSP | Snapdragon 8 Elite Gen 5 的 "Dual Always-Sensing" 微 NPU 专司音频、语音、传感器，主 SoC 休眠时由其工作 | https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/Snapdragon-8-Elite-Gen-5-SM8850-1-AB-V-Series.pdf |
| Snapdragon W5+ Gen 1 | 混合架构——4nm 主 SoC + 22nm AON 协处理器，专司显示、传感器、音频、通知 | https://www.qualcomm.com/wearables/products/snapdragon-w5-plus-gen-1-wearable-platform |
| Ambiq Apollo 系列 | SPOT 亚阈值功耗技术，Apollo510 每焦耳推理吞吐提升 300× | https://ambiq.com/soc/ |
| Apple 路线 | "Hey Siri"由 SoC 内独立超低功耗协处理器/传感器中枢常驻处理麦克风流；Apple Watch Live Rewind 由 S11 做持续听觉，双击表冠给出"过去 15 秒说了什么" | https://www.macrumors.com/ |
| Brilliant Halo | Alif Balletto SoC + **音频活动检测(AAD)硬件级低功耗唤醒**，14h 电池 | https://github.com/brilliantlabsAR/halo-firmware |

**(b) 软件侧省电策略：**
- **事件驱动 / VAD 门控录音**：只在检测到语音段时触发编码与上传，静音帧直接丢弃——这是 24/7 续航的核心。
- **缓冲+突发上传（buffer-and-burst）**：音频先以 Opus 压缩存本地，在充电/连 WiFi 时批量回传转写。产品实证：Omi 支持离线录音（本地先存，事后 10–20s 完成离线转写）；Limitless 支持约 35 小时离线录音后再处理。

**(c) 硬件产品实际续航（标称 vs 实测）：**

| 产品 | 标称续航 | 实测/典型 | 来源 |
|---|---|---|---|
| Limitless Pendant | 100h 待机 | 全天常开实际 12–14h；会议录音 1.5–2 天一充 | https://www.umevo.ai/blogs/ume-all-posts/wearable-ai-wars-2026-limitless-pendant-vs-bee-pioneer-vs-plaud-notepin |
| Plaud Note | Enhance 30h / Endurance 50h | 厂商规格 | https://eu.plaud.ai/pages/plaud-note |
| Plaud NotePin | 20h 录音 | 实测约 12–14h | https://www.humai.blog/ai-gadgets-for-productivity-tools-that-replace-your-assistant/ |
| Omi | 24h+ 连续捕获 | 与标称接近；离线录音支持 | https://www.omi.me/pages/product |
| Bee Pioneer | 7 天（待机+轻用） | 重负载持续听 1.5–2 天 | https://www.umevo.ai/blogs/ume-all-posts/wearable-ai-wars-2026-limitless-pendant-vs-bee-pioneer-vs-plaud-notepin |

**关键结论**：常开 ASR 处理是耗电大头——Limitless 标称 100h 待机但开启持续转写后仅 12–14h，说明真正 24/7 语音理解在当前电池+SoC 工艺下仍需"本地低码率录音 + 事后批量转写"而非"全程流式上云"。

### 5.4 存储与压缩流水线（数据量估算，已实际计算）

**流水线**：麦克风 PCM → Opus 编码 → 转写文本 → 向量嵌入 → 向量库。

**(1) 音频原始/压缩（单声道 16kHz）：**

| 编码 | 码率 | 每小时 | 计算过程 |
|---|---|---|---|
| PCM 16-bit | 256 kbps | **115.2 MB** | 16000×16 = 256,000 bps = 32 KB/s × 3600 |
| Opus 24 kbps | 24 kbps | **10.8 MB** | 3,000 B/s × 3600 |
| Opus 16 kbps | 16 kbps | **7.2 MB** | 2,000 B/s × 3600 |
| Opus 8 kbps | 8 kbps | **3.6 MB** | 1,000 B/s × 3600 |

Opus 官方规格：RFC 6716，6–64 kbps，算法延迟约 25ms（20ms 帧），16kHz 语音常用 24 kbps。来源：https://datatracker.ietf.org/doc/draft-ietf-codec-opus

**(2) 转写文本：**
- 英文 ~150 词/分钟 ≈ 9000 词/小时 → **约 45–55 KB/小时**（~1.1–1.2 万 token/小时）
- 中文 ~200–250 字/分钟 → 1.2–1.5 万字/小时 → **约 36–45 KB/小时**（~0.8–1 万 token/小时）

**(3) 向量嵌入：**

| 嵌入模型 | 维度 | fp32 向量大小 | int8 | 模型体积 |
|---|---|---|---|---|
| all-MiniLM-L6-v2 | 384 | 1.5 KB | 384 B | ~22–46MB |
| bge-small / bge-base | 384 / 768 | 1.5 / 3 KB | — | 35–130MB |
| bge-large-en/zh-v1.5 | 1024 | 4 KB | 1 KB | ~1.3GB |
| bge-m3（多语言） | 1024 | 4 KB | 1 KB | — |
| text-embedding-ada-002 | 1536 | 6 KB | — | 云 API |

**(4) 全天（12 小时活跃录音）量级估算：**

| 阶段 | 12h 量级 |
|---|---|
| PCM 原始 | ~1.38 GB |
| Opus 24kbps | ~130 MB |
| 转写文本 | 英文 ~0.6 MB / 中文 ~0.5 MB |
| 向量（512 token/块，约 220 块） | MiniLM int8 ~85 KB；bge-large fp32 ~0.9 MB |

**核心洞察**：音频压缩 10:1 于 PCM；转写文本再比音频小 200×以上；向量与文本同量级。这解释了 Rewind/Limitless 宣传的"一天十几 GB 原始屏幕+音频可压到很小"的技术路线。

### 5.5 本地记忆与检索（RAG / 个人记忆栈）

**典型实现**：转写文本按会话/时间窗分块（256–512 token）→ 嵌入模型向量化 → 元数据（时间、说话人、App/地点）随向量入库 → 查询时向量相似度+元数据过滤 → top-k 注入 LLM。

**开源组件选型（2026 生态）：**
- **向量库**：Chroma（本地原型、小规模易用）；FAISS（库式嵌入）；Qdrant（向量+关键词混合检索、元数据过滤、gRPC，适合自托管生产）
- **记忆层框架**：Mem0（自改进记忆层，可挂 Qdrant/Chroma）；Letta（原 MemGPT，带自我编辑记忆）
- **检索增强做法**：查询改写——不仅用原始 query，还把"记忆中召回的文本片段 + 由记忆生成的替代问题"一并去检索（multi-query），显著提升全局问题召回
- **个人记忆项目实证**：claude-rag-memory 用 sentence-transformers(all-MiniLM-L6-v2)+LanceDB，复合排序综合相似度/时间新近度/重要性/访问频率，并以 SQLite 存带时间窗的实体关系三元组
- **端侧全栈范例**：memtomem 用 ONNX 嵌入（MiniLM/bge-small/bge-m3）+ Ollama，纯本地

来源：https://github.com/ekaagragupta/mem0RAG ；https://qdrant.tech/documentation/frameworks/mem0/ ；https://mem0.ai/blog/rag-vs-ai-memory ；https://github.com/jonburchel/claude-rag-memory

---

## 6. 学术论文前沿（arXiv 补采）

> 既有 119 篇调研语料（Agent/LLM-OS 方向）经索引证实 0 篇音频相关（见 [papers_index.md](papers_index.md)），
> 本节为 2026-09-11 按 9 组查询全新采集的结果（另加 4 组补充查询补齐"记忆留存消费/声学事件"维度，见 §6.2）。
> 8 篇 PDF 已按既有命名规约存入 [papers/](papers/)，登记于 [papers/MANIFEST.txt](papers/MANIFEST.txt) 编号 120–127。

### 6.1 按漏斗分段归类

四段漏斗：①常驻低耗检测 → ②触发式捕获 → ③即时蒸馏（ASR/情感）→ ④原音频即焚+结构化记忆。

**① 常驻低耗检测**（对应 laos `laos/vad.py` 常驻层）

- **On-Device Domain Learning for Keyword Spotting on Low-Power Extreme Edge Embedded Systems**（IEEE AICAS 2024，[arXiv:2403.10549](https://arxiv.org/abs/2403.10549)）
  - 研究问题：常开 KWS 在真实噪声下精度衰减，能否完全在设备端现场自适应恢复？
  - 与 laos 的关系：漏斗①——端侧域适应只需 <10 kB 内存、806 mJ / 14 s 即可在电池设备完成，证明在 `vad.py` 之上加"可自我校准的 KWS 二级门控"处于功耗预算内。
- **Keyword Spotting System and Evaluation of Pruning and Quantization Methods on Low-power Edge Microcontrollers**（DCASE 2022 Workshop 投稿，[arXiv:2208.02765](https://arxiv.org/abs/2208.02765)）
  - 研究问题：KWS 的剪枝/量化方法在 Cortex-M 微控制器上的真实加速收益如何？
  - 与 laos 的关系：漏斗①——实测 37 ms/决策；**结构化剪枝在 MCU 上远优于非结构化**（稀疏权重难以加速），量化 + SIMD 才有收益，为常驻检测层的模型压缩路线给出工程结论。

**② 触发式捕获**（对应 laos `drivers/drv_rec.py`）

- **WearVox: An Egocentric Multichannel Voice Assistant Benchmark for Wearables**（arXiv 预印本 2025-12，[arXiv:2601.02391](https://arxiv.org/abs/2601.02391)）
  - 研究问题：AI 眼镜等可穿戴场景下，语音助手如何在运动噪声、快速微交互与背景对话中分辨"设备指向语音"？
  - 与 laos 的关系：漏斗②——3,842 条多通道自我中心录音显示语音 LLM 准确率仅 29–59%，多通道输入显著提升 Side-Talk Rejection；`drv_rec.py` 触发捕获必须假设"戴着设备≠在对它说话"，该基准可直接用于评测。

**③ 即时蒸馏（ASR / 情感）**（对应 laos `drivers/drv_ear.py`）

- **Speech as a Multimodal Digital Phenotype for Multi-Task LLM-based Mental Health Prediction**（arXiv 预印本 2025（v3），[arXiv:2505.23822](https://arxiv.org/abs/2505.23822)）
  - 研究问题：把语音当作"数字表型"，能否同时预测抑郁、自杀意念与睡眠障碍？
  - 与 laos 的关系：漏斗③——转写文本 + 声学 landmark + vocal biomarker 三模态 + 纵向多任务建模达 70.8% 平衡准确率，优于一切单模态/单任务/非纵向方法；`drv_ear` 的 SenseVoice 情感输出应做纵向差分而非绝对分判定。
- **Generalized Dilated CNN Models for Depression Detection Using Inverted Vocal Tract Variables**（Interspeech 2021 投稿，[arXiv:2011.06739](https://arxiv.org/abs/2011.06739)）
  - 研究问题：基于声道变量的 vocal biomarker 能否跨语料库泛化地检测抑郁？
  - 与 laos 的关系：漏斗③——跨语料评估相对提升约 10%，说明声学健康特征有真信号；但它属**敏感生物特征**，印证 laos 按 §7（隐私与合规）默认不落盘声纹/生物标记物、只留临时情感标签的设计。

**声学事件 / 环境场景**（laos 差异化方向：SenseVoice AED 通道）

- **Characterizing dynamically varying acoustic scenes from egocentric audio recordings in workplace setting**（ICASSP 2020 投稿，[arXiv:1911.03843](https://arxiv.org/abs/1911.03843)）
  - 研究问题：能否从可穿戴音频徽章的长时自我中心录音中刻画动态变化的声学场景？
  - 与 laos 的关系：漏斗③/④——医院真实佩戴数据 + TDNN 段级建模，证明"声学场景序列与用户职业性质相关"，为 laos 给记忆条目打"环境/场景"标签提供学理依据。

**④ 留存消费：原音频即焚 + 结构化记忆**（对应 laos `mem.recall`）

- **Evaluating Memory Capability in Continuous Lifelog Scenario**（ACL 2026 Findings，[arXiv:2604.11182](https://arxiv.org/abs/2604.11182)）
  - 研究问题：可穿戴设备连续 lifelog 环境对话时，现有记忆系统的真实能力如何？
  - 与 laos 的关系：漏斗④——LifeDialBench（EgoMem/LifeMem）在线（时间因果）评测发现**复杂记忆系统竟输给简单 RAG 基线**，元凶是过度设计与有损压缩；`mem.recall` 应保留高保真转写文本、慎做激进结构化，评测须防时间泄漏。
- **OpenLifelogQA: An Open-Ended Multi-Modal Lifelog Question-Answering Dataset**（SoICT 2025，[arXiv:2508.03583](https://arxiv.org/abs/2508.03583)）
  - 研究问题：18 个月多模态 lifelog 数据能否支撑开放式问答与记忆增强？
  - 与 laos 的关系：漏斗④——14,187 组 QA 给出"个人记忆问答"的评测口径；其语料以图像/位置为主、连续音频对话稀缺，反证 laos 以音频为主的 lifelog QA 基线在学界尚属空白。

### 6.2 检索记录

检索端点 `export.arxiv.org/api/query`（Atom），sortBy=relevance，每组取相关性 top5，2023 年以后优先。

| # | 查询 | 命中 | 采纳 |
|---|---|---|---|
| 1 | `all:"audio lifelogging"` | 0 | 0（低命中） |
| 2 | `all:"acoustic lifelog"` | 0 | 0（低命中） |
| 3 | `all:"wearable memory aid"` | 0 | 0（低命中） |
| 4 | `ti:"memory prosthesis"` | 0 | 0（低命中） |
| 5 | `all:"always-on" AND all:"keyword spotting"` | 22 | 2（2403.10549、2208.02765） |
| 6 | `all:"vocal biomarkers" AND all:"depression"` | 2 | 2（2505.23822、2011.06739） |
| 7 | `all:"egocentric audio"` | 12 | 2（2601.02391、1911.03843） |
| 8 | `all:"duty-cycled" AND all:"acoustic"` | 13 | 0（top5 全为日震学/电机/超声驱动，无一相关） |
| 9 | `all:"on-device speech recognition" AND all:"survey"` | 1 | 0（唯一命中为汽车 UI 综述，无关） |
| 补充 | `all:"lifelogging"` | 62 | 1（2508.03583） |
| 补充 | `all:"lifelog" AND all:"audio"` | 4 | 1（2604.11182） |
| 补充 | `all:"acoustic scene" AND all:"earable"` | 0 | 0（低命中） |
| 补充 | `all:"continual" AND all:"audio" AND all:"privacy"` | 51 | 0（命中以 deepfake 检测/联邦学习为主，无一相关） |

说明：①查询 1–4 在 arXiv 全字段短语匹配下 0 命中，如实记录、不硬凑；②查询 8/9 命中数虽高但无一相关；③主查询仅凑得 6 篇强相关，为覆盖漏斗④（记忆留存消费）这一 laos 核心差异段，追加 4 组补充查询、采纳其中 2 篇（2508.03583、2604.11182）；④采纳 8 篇中 5 篇为 2023 年以后工作（2604.11182、2601.02391、2505.23822、2508.03583、2403.10549），3 篇较早文献（2208.02765、2011.06739、1911.03843）分别为查询 5/6/7 的最相关命中，作为对应漏斗段的基线证据保留。

---

## 7. 隐私与合规

### 7.1 录音同意法律框架（分法域）

#### 美国：一方同意 vs 全体同意

- **联邦法（18 U.S.C. §2511）**默认**一方同意**（participant recording 合法）。
- **明确全体同意（all-party）的 9 州**：California、Florida、Illinois、Maryland、Massachusetts、Montana、New Hampshire、Pennsylvania、Washington。另有 CT、DE、OR 为"混合州"。
- **加州 Penal Code §632**：对"confidential communication"，未经**全体参与者**同意，使用任何电子放大/录音设备窃听或录音即构成犯罪，并有民事救济；§632.7 扩及蜂窝电话通信。
- **纽约**属一方同意州（NY Penal Law §250.00）。
- 违法录音可构成轻罪（部分重罪）+ 民事赔偿；非法录音不得作为证据。

来源：https://www.recordinglaw.com/united-states-recording-laws/ ；https://www.recordinglaw.com/party-two-party-consent-states/ ；https://www.leginfo.ca.gov/pub/15-16/bill/asm/ab_0901-0950/ab_925_bill_20150326_amended_asm_v98.pdf

#### 欧盟 / GDPR

- **数据最小化（Art.5(1)(c)）**：只收集"充分、相关且限于必要"的数据，优先匿名化。
- **目的限定（Art.5(1)(b)）**：不得为初始目的之外再处理。
- **合法依据**：同意须"自由、具体、知情、明确"；"合法利益"需通过三部分测试（目的/必要性/平衡）。
- **EDPB 对录音电话的口径**：录音须告知对方录音目的、接收方、反对权与查阅权；敏感数据原则上禁止处理。

来源：https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en ；https://www.edpb.europa.eu/contact/frequently-asked-questions_en

#### 中国

- **《民法典》第 1033 条**：除法律另有规定或权利人明确同意外，任何组织/个人不得"拍摄、窥视、窃听、公开他人的私密活动"。
- **《民法典》第 1034 条**：个人信息包括生物识别信息等；私密信息优先适用隐私权规定。
- **《个人信息保护法》第 13 条**：处理个人信息须有合法基础，首要为"取得个人同意"。
- **声音/声纹定性**：自然人声音属个人信息；从声音提取的声学特征模式（声纹）属**生物识别信息，即敏感个人信息**，处理须更严格告知-同意。
- **司法实践三要素**：判断录音是否合法看①获取手段（是否使用窃听器材/侵入性技术）②获取场所（私密空间 vs 公共场合低隐私期待）③获取内容。公共场合录不特定公众的非私密对话一般不违法，但针对特定对象长期跟踪录制仍违法。
- **录音证据**：实务转向"获取手段不侵害他人合法权益、不违反法律禁止性规定"即可作为证据（即未同意≠必然排除）。

来源：http://www.npc.gov.cn/c2/c30834/202012/t20201216_309218.html ；http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html ；http://www.legaldaily.com.cn/commentary/content/2026-04/01/content_9366284.html

#### 国际对比小结

| 法域 | 同意规则 | 关键法条 | 对 24/7 随身录音的含义 |
|---|---|---|---|
| 美国联邦 | 一方同意 | 18 U.S.C. §2511 | 录音者本人参与即可 |
| 美国 CA/FL/IL 等 9–12 州 | 全体同意 | CA Penal Code §632 | 在场所有人都须知情同意，否则刑事+民事 |
| 欧盟 | 须合法依据+告知+最小化 | GDPR Art.5/6 | 7×24 录路人极难满足目的限定与最小化 |
| 中国 | 私密活动不得窃听；声音=个人信息、声纹=敏感信息 | 民法典 §1033/1034；个保法 §13 | 对特定人持续录制/私密空间录制高风险 |

### 7.2 产品的隐私回应机制

| 机制 | 代表产品做法 | 来源 |
|---|---|---|
| **LED 录制指示灯** | Ray-Ban Meta 二代 LED 从 0.9mm 加大到 2mm 并改动态闪烁；2026-07-07 强制固件更新：LED 被物理篡改即关停摄像头（消费级可穿戴首个 camera-kill） | Meta《Bystander Privacy》https://about.fb.com/wp-content/uploads/2026/07/Bystander-Privacy.pdf |
| **硬件断开/物理开关** | 录音笔普遍有 R/Off 滑动开关（机械触觉确认在录）；Anker Soundcore Work 录制时按钮下压锁定提供触觉确认 | https://electronicsdigest.org/best-spy-microphone-recorder/ |
| **仅端侧模式** | Rewind 默认屏幕+音频全部本地处理、AES-256 加密、不上云；Omi 提供免费"手机端本地转写"档位；ZScribe 等开源"local-first" | https://aisotools.com/blog/rewind-ai-review-2026 ；https://www.omi.me/pages/product |
| **敏感内容/PII 处理** | 端侧工具提供"上云前可选脱敏"；企业级产品宣称 ISO 27001/SOC2/HIPAA/GDPR 合规；音频脱敏（姓名/账号/卡号 masked）是单独工程领域 | https://redactor.ai/blog/how-to-redact-audio-recordings |
| **告知与同意** | Apple 通话录音自动告知对方；产品通用做法：App 内权限提示、录制状态灯；行业尚无统一"beep 音"标准 | https://www.advertise.co.uk/?q=node%2F222312 |

### 7.3 全天候录音的隐私争议事件

- **Meta Ray-Ban 肯尼亚外包标注事件**：瑞典媒体调查曝光，"Hey Meta"拍摄的视频图像被发往肯尼亚内罗毕外包公司 Sama，人工审核员标注训练 AI，内容含浴室/更衣室片段甚至裸露与银行卡信息。🔶第三方/媒体声称
- **Meta "NameTag"人脸识别代码**：2026-06 Malwarebytes 在 Meta companion app（装机量 5000 万+）中发现未启用的人脸识别代码（SCRFD 检测+KPSAligner 对齐+SFace 生物特征嵌入）。🔶第三方/媒体声称
- **"变态眼镜"舆论**：2026 夏"pervert glasses"反弹致 Instagram 封禁至少两个百万粉丝账号的智能眼镜骚扰视频。🔶第三方/媒体声称
- **Humane AI Pin 的失败**：$240M 融资、$699 售价；发热（召回电池）、简单查询 10s 延迟、强依赖云端；2025-02 HP 收 IP 后服务器关闭设备变砖——暴露"云依赖硬件"的消费者保护与隐私风险。
- **Rewind/Limitless 的隐私信任反转**：以"数据永不出设备"起家 → 转向云转写 → 被 Meta 收购并入 Reality Labs——批评者认为用户录音数据最终落入"规模化变现个人信息"的公司政策下。

来源：https://post.m.smzdm.com/p/ae6rlelq/ ；https://www.softwareseni.com/privacy-trust-and-the-architecture-of-ai-smart-glasses/ ；https://screenpipe.com/blog/rewind-ai-alternative-2026 ；https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/

---

## 8. 2024–2026 趋势

### 8.1 从云转写走向端侧记忆 Agent

驱动因素：①NPU/DSP 普及使 1B 级模型可端侧实时（WhisperKit、AMD Ryzen AI、Apple Neural Engine）；②量化/蒸馏把 ASR 压到几十 MB、1.58-bit（EdgeSLU/Edge-ASR 论文）；③隐私监管与用户不信任云录音；④LLM 端侧化让"记忆"无需往返云。

架构正从"录音→云转写→云摘要"变为"本地低码率录音→本地/半本地转写→本地向量记忆→按需云 LLM 增强"。

### 8.2 AI 硬件爆发期与形态演变

- 2023–2024"AI 吊坠"命题：屏外、麦克风+LLM 做对话记忆。Humane AI Pin（$240M 融资）、Rabbit R1、Limitless Pendant（$99，Sam Altman 背书）同期登场。
- **洗牌**：2025-02 Humane 资产售 HP 后变砖；2025-07 **Amazon 收购 Bee**（团队并入 Devices & Services，独立消费品牌路线图停摆）；2025-12 **Meta 收购 Limitless**并入 Reality Labs，吊坠停售——平台型公司（HP、Amazon、Meta）批量吸收独立 AI 硬件初创，独立"常听可穿戴"作为独立品类已基本消亡。
- **市场数据**：2025 上半年全球智能眼镜出货 406.5 万台，同比 +64.2%；2025 前三季度全球腕戴设备出货 1.5 亿台，中国 5843 万台同比 +27.6%。
- **形态路线**：智能手表 → AI 徽章/吊坠（Pendant、NotePin、Omi）→ AI 眼镜（Ray-Ban/Oakley Meta 2025 单年销量超 700 万副，2023–2024 两年合计仅约 200 万副；EssilorLuxottica 财报口径）→ 项链/耳机内嵌持续听觉（Apple Watch Live Rewind、华为 FreeBuds Pro 5）。

来源：https://sacra.com/research/why-meta-bought-limitless/ ；https://news.cctv.com/2026/01/30/ARTIwl6eMHPEIPj7YRixZnlB260130.shtml ；https://www.c114pro.com/terminal/181641.html

### 8.3 "环境智能"（Ambient Intelligence）愿景与现实

- **愿景**：常开传感器（麦、摄像头、IMU）+ 端侧 AI 持续理解环境，设备"无需唤醒即在场"（Meta 的"personal superintelligence"叙事）。
- **现实约束**：①续航——持续流式 ASR 把 100h 待机压到 12–14h；②隐私——bystander 无感知录制引发 LED 强制、外包标注丑闻、人脸识别代码曝光；③云依赖风险——Humane 变砖证明端云耦合的脆弱性；④监管——GDPR 目的限定/数据最小化与"什么都录"的根本冲突。
- **技术折中正在成形**：**VAD 门控 + 本地 Opus 缓冲 + 事件触发转写 + 本地向量记忆 + LED/物理开关/可排除 App**，成为 2026 年可落地的"克制版 ambient intelligence"。

---

## 9. 对 laos 的启示

laos 已有音频子系统：`drivers/mic`（麦克风）、`drivers/ear`（ASR 双通道）、`drivers/rec`（听觉日志）、VAD、`drivers/audio`（人声分离+AEC）。以下是基于业界调研的具体启示。

### 9.1 供电预算：不要假设"全程流式上云"可行

业界实测证明：常开 ASR 处理是耗电大头。Limitless 标称 100h 待机，开启持续转写后仅 12–14h。laos 如果运行在电池供电设备上，**必须采用"本地低码率录音 + 事后批量转写"而非"全程流式上云"**。

具体建议：
- `drivers/mic` 默认以 Opus 16kbps（7.2MB/h）编码存本地环形缓冲，不做实时 ASR
- `drivers/ear` 的流式通道仅在 VAD 检测到语音段 + 用户/策略明确要求实时时激活
- 高精度异步通道在充电/连 WiFi 时批量处理本地缓冲（buffer-and-burst）
- 参考 Apple Watch Live Rewind 的"环形缓冲+事件触发"架构：持续保留最近 N 秒音频，用户双击/事件触发时才转写

### 9.2 VAD 门控录音：常开的正确姿势是"不常开"

业界存活路径证明：纯常开（always-on passive）几乎全部倒下。正确做法是 **VAD 门控 + 事件驱动**——麦克风硬件层常开（低功耗 AON），但软件层只在检测到语音时才编码/转写/存储。

具体建议：
- `drivers/mic` 与 VAD 之间加一层"语音段门控"：Silero VAD（<1ms/chunk，2MB 模型）做第一级，静音帧直接丢弃
- 参考 screenpipe 的实现：VAD → 语音段累积 → 段尾触发 Whisper 转写 → 写入 SQLite
- 如果需要唤醒词交互，加 openWakeWord 做第二级触发器（纯 Python，可直接挂 MCP）
- 这与 laos 的"能力表强制"理念一致：VAD 门控本质是一种"资源预算门控"——没有语音就不消耗 ASR/存储/网络预算

### 9.3 存储配额：用 Opus + 文本 + 向量的三级压缩

数据量估算（12h 活跃录音）：PCM 1.38GB → Opus 130MB → 转写文本 0.5MB → 向量 <1MB。**转写文本比原始音频小 200×以上**，这是存储配额设计的核心依据。

具体建议：
- `drivers/rec` 不存 PCM 原始音频，默认存 Opus 24kbps（10.8MB/h）+ 转写文本
- 原始音频设 TTL 即焚（与 laos 听觉日志管线一致：转写成功后默认数小时删除，`LAOS_JOURNAL_KEEP_H=6`），转写文本和向量长期保留
- 向量库选 bge-m3（1024 维，多语言，fp32 4KB/块）或 MiniLM int8（384 维，384B/块），按存储预算取舍
- 直接抄 screenpipe 的 SQLite schema：`audio_transcriptions` 表（timestamp、speaker、text、offset）+ 元数据（说话人、App/地点）
- 分层摘要：参考 LocalRecorder 的 hour→day→week 分层摘要，用 LLM 对转写文本做压缩，进一步降低长期存储

### 9.4 隐私能力模型：把"录音"做成受权限管控的系统资源

业界隐私争议证明：bystander 无感知录制是全天候录音最大的社会接受度障碍。laos 作为 AgentOS，应把"录音能力"做成**受能力表强制管控的系统资源**，而非 agent 可随意调用的普通工具。

具体建议：
- **能力分级**：
  - `mic.listen`：仅 VAD 能量检测（不存音频、不转写）——最低权限
  - `mic.record`：VAD 门控的语音段录音（存 Opus，不转写）——需用户授权
  - `mic.transcribe`：对录音做 ASR 转写——需更高权限
  - `mic.always_on`：24/7 连续捕获（绕过 VAD 门控）——最高权限，默认拒绝，需显式人类释放
- **录制状态指示**：laos 应提供系统级"正在录音"状态（类似 Meta 的 LED tamper detection），任何 agent 启动录音时内核必须发出可感知的状态信号（桌面通知、LED、系统托盘图标）
- **可排除机制**：参考 Rewind 的"可排除特定 App"——laos 应支持用户配置"某些应用/窗口/时段不录音"
- **端侧优先**：默认纯端侧处理（sherpa-onnx / FunASR），上云转写需单独授权且应支持上云前脱敏（PII redaction）
- **不录音他人口音声纹**：中国法语境下声纹属敏感个人信息，laos 默认不应提取/存储说话人声纹，说话人识别用临时 diarization（speaker_1/speaker_2）而非声纹注册

### 9.5 端侧 ASR 选型：sherpa-onnx 是一站式首选

laos 的 `drivers/ear` 是双通道设计（流式近实时 + 高精度异步），与业界最佳实践完全对应。

具体建议：
- **流式近实时通道**：**sherpa-onnx**（首选）——int8 Zipformer RTF≈0.078–0.123，纯端侧，Apache-2.0，内置 VAD/说话人分离/声源分离，一站式覆盖 laos 音频子系统多个驱动的需求。中文场景备选 **FunASR** Paraformer-zh-streaming（chunk 600ms，原生 MCP serving，与 laos 的 MCP Server 驱动理念一致）
- **高精度异步通道**：**faster-whisper**（CTranslate2，4x 加速）跑 30s 块做二次校准；**SenseVoice** 做情感/事件标签（对"环境记忆"特别有价值）
- **伪流式策略**：抄 **whisper_streaming** 的 LocalAgreement（self-adaptive latency）——不要固定 1s 分片，根据语音复杂度自适应
- **不建议**：openai/whisper 原版（慢，30s 块非流式）、Coqui STT（停更）

### 9.6 常开麦克风作为受权限管控的系统资源：总结

把以上五条合起来，laos 的"全天候录音"能力模型应是：

```
硬件层：AON 低功耗麦克风常开（DSP/VPU 级）
  ↓
内核层：能力表强制管控
  mic.listen (VAD 能量) → mic.record (VAD 门控录音) → mic.transcribe (ASR) → mic.always_on (24/7)
  每级需独立授权，默认收紧，人类一次性释放
  ↓
驱动层：
  drivers/mic → SpeexDSP(AEC+AGC+NS) → Silero VAD → Opus 16kbps 环形缓冲
  drivers/ear → sherpa-onnx 流式(近实时) + faster-whisper(异步高精度)
  drivers/rec → SQLite(转写+元数据) + 向量库(bge-m3) + 分层摘要
  ↓
隐私层：系统级录制状态指示 + 可排除 App/时段 + 端侧优先 + 上云前脱敏 + 不存声纹
  ↓
续航层：VAD 门控(静音不处理) + buffer-and-burst(充电时批量转写) + 原始音频 TTL
```

这就是 2026 年业界验证过的"克制版 ambient intelligence"在 laos 上的落地形态。

---

## 10. 参考来源

### 消费产品
- Rewind/Limitless：https://rewind.ai/what-happened-to-rewind/ ；https://limitless.ai/ ；https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/ ；https://screenpipe.com/blog/rewind-ai-alternative-2026
- Omi：https://github.com/basedhardware/omi ；https://docs.omi.me/doc/hardware/consumer ；https://www.omi.me/products/omi-dev-kit-2 ；https://www.desiblitz.com/content/what-is-omi-and-how-do-you-use-it
- Plaud：https://global.plaud.ai/products/plaud-notepin ；https://tw.plaud.ai/products/notepin
- Bee：https://bee.computer/ ；https://www.aboutamazon.com/news/devices/bee-amazon-wearable-ai-device-new-features ；https://www.thepaper.cn/newsDetail_forward_31240075 ；https://www.latent.space/p/bee
- Meta Ray-Ban：https://about.fb.com/wp-content/uploads/2026/07/Bystander-Privacy.pdf ；https://ppc.land/hamburg-regulator-finds-ray-ban-meta-glasses-expose-bystanders-without-consent/ ；https://www.softwareseni.com/privacy-trust-and-the-architecture-of-ai-smart-glasses/
- Humane AI Pin：https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/
- Apple：https://support.apple.com/en-in/guide/iphone/iph00953a982/ios ；https://www.apple.com/hu/newsroom/2024/10/apple-intelligence-is-available-today-on-iphone-ipad-and-mac/ ；https://www.apple.com/airpods-pro/hearing-health/
- Google：https://blog.google/products-and-platforms/devices/pixel/pixel-drop-march-2025/ ；https://store.google.com/intl/de/ideas/articles/gemini-nano-offline/
- Samsung：https://www.samsung.com/us/support/answer/ANS10004613/
- 科大讯飞：https://www.iflytekrecord.com/Aboutzation/141.html ；https://www.iflytekrecord.com/Goods/1.html
- 华为：http://www.chinanews.com.cn/cj/2025/11-28/10522958.shtml ；https://tech.huanqiu.com/article/4PIL8sqJlVx
- 小米：https://tech.sina.cn/2025-11-30/detail-infzeuyy5004914.d.html ；https://view.inews.qq.com/a/20250628A0220Q00
- 有道：http://www.xinhuanet.com/tech/20260829/8fc452655ed141a7971f29899398f58f/c.html ；http://www.sznews.com/news/content/2026-09/10/content_32168566.htm
- 其他中文：https://meeting.tencent.com/support/topic/2214/index.html ；https://www.volcengine.com/docs/6561/163032

### 开源项目
- ASR 框架：https://github.com/k2-fsa/sherpa-onnx ；https://github.com/modelscope/FunASR ；https://github.com/SYSTRAN/faster-whisper ；https://github.com/ufal/whisper_streaming ；https://github.com/alphacep/vosk-api ；https://github.com/FunAudioLLM/SenseVoice ；https://github.com/collabora/WhisperLive ；https://github.com/ggml-org/whisper.cpp ；https://github.com/openai/whisper ；https://github.com/speechbrain/speechbrain ；https://github.com/coqui-ai/STT ；https://github.com/NVIDIA-NeMo/NeMo
- 个人记忆：https://github.com/screenpipe/screenpipe ；https://github.com/mem0ai/mem0 ；https://github.com/BasedHardware/Omi ；https://github.com/yuka-friends/Windrecorder
- 语音助手：https://github.com/OpenVoiceOS/ovos-core ；https://github.com/dscripka/openWakeWord ；https://github.com/Picovoice/porcupine ；https://github.com/rhasspy/rhasspy
- 可穿戴：https://github.com/BasedHardware/OpenGlass ；https://github.com/brilliantlabsAR/frame-codebase
- 基础库：https://github.com/snakers4/silero-vad ；https://github.com/wiseman/py-webrtcvad ；https://github.com/xiph/rnnoise ；https://github.com/xiph/speexdsp ；https://github.com/xiph/opus

### 技术机制
- VAD/唤醒词/ASR 指标：https://github.com/Kai-Karren/silero-vad ；https://picovoice.ai/products/voice/wake-word/ ；https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html ；https://www.yashchudasama.com/blog/ai/realtime-ai-pipelines/
- 端侧 ASR 进展：https://arxiv.org/pdf/2507.10860 ；https://arxiv.org/html/2507.07877v2 ；https://dl.acm.org/doi/pdf/10.1145/3746252.3761477 ；https://www.amd.com/en/developer/resources/technical-articles/2025/unlocking-on-device-asr-with-whisper-on-ryzen-ai-npus.html
- 低功耗硬件：https://www.qualcomm.com/wearables/products/snapdragon-w5-plus-gen-1-wearable-platform ；https://ambiq.com/soc/ ；https://www.macrumors.com/
- 续航实测：https://www.umevo.ai/blogs/ume-all-posts/wearable-ai-wars-2026-limitless-pendant-vs-bee-pioneer-vs-plaud-notepin
- 存储/压缩：https://datatracker.ietf.org/doc/draft-ietf-codec-opus ；https://insiderllm.com/pdfs/embedding-models-rag.pdf ；https://bge.baai.ac.cn/
- RAG/记忆：https://qdrant.tech/documentation/frameworks/mem0/ ；https://mem0.ai/blog/rag-vs-ai-memory ；https://github.com/jonburchel/claude-rag-memory

### 法律与隐私
- 美国：https://www.recordinglaw.com/united-states-recording-laws/ ；https://www.recordinglaw.com/party-two-party-consent-states/
- 欧盟：https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en ；https://www.edpb.europa.eu/contact/frequently-asked-questions_en
- 中国：http://www.npc.gov.cn/c2/c30834/202012/t20201216_309218.html ；http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_313088.html ；http://www.legaldaily.com.cn/commentary/content/2026-04/01/content_9366284.html
- 产品隐私机制：https://about.fb.com/wp-content/uploads/2026/07/Bystander-Privacy.pdf ；https://redactor.ai/blog/how-to-redact-audio-recordings
- 争议事件：https://post.m.smzdm.com/p/ae6rlelq/ ；https://www.softwareseni.com/privacy-trust-and-the-architecture-of-ai-smart-glasses/

### 趋势与市场
- https://sacra.com/research/why-meta-bought-limitless/ ；https://news.cctv.com/2026/01/30/ARTIwl6eMHPEIPj7YRixZnlB260130.shtml ；https://observer.com/2025/12/meta-acquires-ai-pendant-maker-limitless/ ；https://www.c114pro.com/terminal/181641.html
