# 全天候录音：社会接受度实证研究 + 2024–2026 争议事件时间线

> 配套文档：
> - 业界图谱 / 技术机制 / 法律条文 → [`../always-on-recording-industry-2026-09.md`](../always-on-recording-industry-2026-09.md)（§7 已覆盖民法典 1033/1034、个保法、加州 Penal Code §632、GDPR Art.5/6，**本文不重复法条**）
> - 本文只做两件事：**(a) 学界对持续录音的实证社会接受度研究**；**(b) 2024–2026 争议事件的完整时间线与真实后果**
>
> 标注约定：
> - **✅** = 官方公告 / 监管机构文件 / 论文原文（含 DOI、arXiv 全文）已查证
> - **🔶** = 媒体或第三方声称，未经一手文件确认
> - **`未证实`** = 检索不到可核验的一手证据，不给数字、不编
>
> 检索时间：2026-09-11。

---

## ① 一句话结论

**社会接受度确实是全天候录音的第一瓶颈，但它不是"要不要录音"的问题，而是"录谁"和"在哪录"的问题。**

三条支撑证据：

1. **自我录音（self-VAD）vs 连续录音的社会接受度差异是统计显著的**，而"是不是在录音"这个二元开关反而不是主因。MIT Media Lab 的 MeMic 研究（CHI EA '24）在 N=168 的在线对照实验中验证：只录佩戴者自己声音的范式，相比连续录音，显著降低旁观者的隐私担忧与社会恐惧感（`p` 显著）。这对 laos 的含义是致命的——**laos 目前只做了"开/关"和"审计"，没有做"只录该录的人"**，而学界证据表明后者才是接受度的真正杠杆。✅ [MeMic, CHI EA '24](https://doi.org/10.1145/3613905.3650872)

2. **场景（context）是接受度的首要决定因素，而不是设备或机制。** CHI 2026 对 N=525 人的多利益相关方研究显示，场景主效应 `F=56.440, p<.001`，远大于任何单一隐私机制的效果；在健身房/陌生人场景下 **80%** 的旁观者会采取躲避相机的防御行为，而会议室场景下被动接受率仍达 **35%**。✅ [Mind the Gap, CHI '26](https://ar5iv.labs.arxiv.org/html/2603.04930)

3. **业界已经用"变砖、下架、监管认定、刑事控告"给这个问题定了价。** 2024–2026 年间至少 4 款主打常开传感的消费设备因社会/监管阻力死亡或被迫转向：Humane Ai Pin（$116M 卖给 HP、设备变砖）、Rewind/Limitless（被 Meta 收购、全球停服）、Friend（欧盟上市无限期推迟）、Rabbit R1（硬编码密钥 + 不可删除数据）。**没有一款死于技术，全部死于信任。**

**推论**：laos 的隐私四件套（显式触发 / `LAOS_REC=0` / 全量审计 / 本地 ASR / 6 小时即焚）在**"录制者信任"维度上已经达到甚至超过业界最优**，但在**"旁观者信任"维度上几乎是空白**，而后者才是学界与监管共同指向的瓶颈。详见 §6。

---

## ② 社会接受度实证研究表

> 筛选标准：CHI / CSCW / Ubicomp / IMWUT / USENIX Security / SOUPS / HICSS 等同行评审 venue，或 Pew / YouGov 等有明示抽样方法与样本量的调查。
> **诚实声明**：专门针对"音频持续录音 + 旁观者"的实证研究数量**远少于**摄像头眼镜。下表中音频专属研究只有 5 条（#1 MeMic、#4 Alexa、#5 Tangible Privacy SVA、#6 Candid Mic、#9 Is Someone Listening），其余为视觉/通用常开传感研究——它们的社会机制（隐蔽性、可感知性、同意摩擦）可迁移，但**音频场景的定量数字不能直接套用**，表中已逐条标注模态。

| # | 研究 | 会议 + 年份 | 研究问题 | 方法 (N=) | 定量结论 | 对产品设计的含义 | 链接 |
|---|---|---|---|---|---|---|---|
| 1 | **MeMic: Towards Social Acceptability of User-Only Speech Recording Wearables**（Zulfikar, Pierce, Maes；MIT Media Lab） | CHI EA '24（2024-05-11） | 只用硬件 self-VAD 录佩戴者自己的声音，能否提升持续录音可穿戴的社会接受度？ | 实验室研究 **N=12**（佩戴 MeMic 做任务）+ 在线对照研究 **N=168**（self-recording vs continuous recording）。模态：**音频** | 检测错误率 **0.09 ± 0.03**；在线实验中 self-recording 范式相比连续录音，**社会恐惧感与隐私担忧均显著降低**，社会接受度显著提升；四种形态中 **pendant necklace（吊坠）最被偏好**，其次眼镜 | **对 laos 最关键的一条。** ①"只录自己的声音"比"不录/全录"的二元开关更能换接受度 → laos 应在 syscall 层之上加 **self-VAD / speaker-verification 门控**；②硬件级默认关麦（mic off by default）+ 说话时才上电，是可被感知的隐私保证；③形态上吊坠优于眼镜 | https://doi.org/10.1145/3613905.3650872 ✅ |
| 2 | **Mind the Gap: Mapping Wearer–Bystander Privacy Tensions and Context-Adaptive Pathways for Camera Glasses**（Wang, Peng, Yi, Li；清华 + Utah） | CHI '26（2026-04-13，Barcelona） | 佩戴者与旁观者的隐私期望差距有多大？12 种 PET 哪些真的有效？ | 两项研究：Study 1 问卷 **N=525**（wearers **232** + bystanders **293**，中国样本）；Study 2 配对访谈 **N=20**（10 组）。模态：摄像头眼镜 | ①差距最大场景 **Gym×Strangers**：数据分享 `ΔM=1.04`、内容透明 `ΔM=0.98`、事前同意 `ΔM=0.81`（7 点量表，均 `p<.001`）；②**65%–90%** 旁观者会采取至少一种防御行为（商场 80% 躲避、健身房 68% 躲避；正式投诉峰值健身房 13%、医院 11%）；③**只有 6.1% 旁观者认为单靠 LED 就够**（佩戴者 18.5%）；LED 不足原因：太小易忽视 41.6%、强光下不可见 38.6%、可被故意遮挡 41.3%；④12 种 PET 中 **Geofencing（地理围栏）评分最高（HCI 6.8 / 用户 6.0）**、人脸匿名化次之（5.6/5.4）；**手势识别公开场景选择率 0%**；协商平台隐私保护强（5.6/5.8）但**可用性仅 2.6**；⑤最想要的增强通知：**声音警报 71.7%**（旁观者） | ①**LED 是必要但不充分的**——只有 6.1% 旁观者买账，laos 不能只靠指示灯；②**地理围栏是性价比最高的机制**（评分最高），laos 应支持"进入敏感区域自动禁录"；③旁观者最想要的是**声音警报**而非更强的灯；④"让用户协商同意"这条路已被实测证伪（可用性 2.6/7）→ **不要做交互式同意弹窗，要做默认保护** | https://ar5iv.labs.arxiv.org/html/2603.04930 ✅（arXiv 全文镜像）；正式版 https://doi.org/10.1145/3772318.3791848 |
| 3 | **Tangible Privacy: Towards User-Centric Sensor Designs for Bystander Privacy**（Ahmad, Farzan, Kapadia, Lee） | PACM CSCW2, 2020-10-15 | IoT 设备（摄像头/麦克风）的旁观者如何管理自己的隐私边界？ | 半结构化访谈研究（IoT 设备的旁观者）。模态：摄像头 + 麦克风 | 参与者的行为符合 Altman 边界调节理论，但在"实际是否被录"不确定时，会发明各种 **tangible workaround**（贴胶带、拔电源、物理遮挡）；现有设计缺少**真正的关闭按钮** | 提出 **tangible privacy** 概念：设备必须**无歧义地**传达传感器状态。→ laos 的 `LAOS_REC=0` 如果只存在于内核态，旁观者感知不到，等于没有；需要有**物理/外部可见**的对应物 | https://doi.org/10.1145/3415187 ✅ |
| 4 | **Alexa, Are You Listening? Privacy Perceptions, Concerns and Privacy-seeking Behaviors with Smart Speakers**（Lau, Zimmerman, Schaub；UMich） | PACM CSCW, 2018-11 | 常开麦克风设备的使用者与非使用者，各自的隐私认知与应对行为？ | 日记研究 + 访谈：使用者 **N=17**（日记 + 访谈）+ 非使用者 **N=17**（访谈），共 **34**。模态：**音频** | 非使用者主要因"看不到价值"或"不信任厂商"而不采用；使用者表达很少隐私担忧，但其合理化理由显示**对风险理解不完整**、对厂商是**复杂的信任关系**；存在 **privacy resignation（隐私认命）**；primary / secondary / incidental 用户之间存在隐私张力；**现有隐私控制极少被使用**，因为与用户需求不匹配 | ①默认假设"用户会主动配置隐私"是错的——laos 的 `LAOS_REC=0` 必须是**默认态或一键可达**，而不是藏在配置文件里；②非使用者不是因为隐私而不买，是因为**看不到价值** → 单纯堆隐私保护换不来采用率 | https://doi.org/10.1145/3274371 ✅；摘要 https://www.infodocket.com/2018/11/27/research-article-alexa-are-you-listening-privacy-perceptions-concerns-and-privacy-seeking-behaviors-with-smart-speakers/ |
| 5 | **Tangible Privacy for Smart Voice Assistants: Bystanders' Perceptions of Physical Device Controls**（Ahmad, Akter, Buher, Farzan, Kapadia, Lee） | PACM CSCW2, 2022-11（Article 364） | 语音助手的**物理**开关 vs 软件开关，旁观者更信任哪种？ | 组间在线实验 **N=261**（6 种设计，评估 risk / trust / reliability / usability / control）。模态：**音频（麦克风）** | 带**内建物理控制**的设备被评为**更可信、更易用**，显著优于非物理（软件/触控）机制 | **硬性证据支持"硬件物理开关 > 软件开关"**。→ laos 若只在软件层做 `LAOS_REC=0`，接受度上限受限于"可被感知"这一点；应要求/推荐硬件 mute switch 并把内核态与其绑定 | https://doi.org/10.1145/3555089 ✅；PDF https://homes.luddy.indiana.edu/kapadia/papers/tangible-privacy-cscw22.pdf ；NSF https://par.nsf.gov/biblio/10498061 |
| 6 | **Powering for Privacy: Improving User Trust in Smart Speaker Microphones with Intentional Powering and Perceptible Assurance**（Do, Arora, Mirzazadeh, Moon, Xu, Zhang, Abowd, Das；Candid Mic） | CHI / IMWUT 系列（2023–2024） | 能否用"只能由用户主动供能"的麦克风，提供**可被感知**的隐私保证？ | 迭代设计 + **within-subjects 实验**（对照：Candid Mic vs 静音按钮）。模态：**音频** | Candid Mic（无电池、只能靠用户主动交互采集能量供能，且**用户可目视检查**供能模块与麦克风的连接状态）**显著提升用户对"麦克风是否在采集"的可感知保证，并提升信任**，优于传统静音按钮 | **"可被物理感知"比"厂商承诺"值钱。** → laos 的审计日志若能外化为**用户可核对的证据**（而不是只有内核日志），信任增益会大得多 | https://doi.org/10.5555/3620237.3620376 ✅ |
| 7 | **In Focus, Out of Privacy: The Wearer's Perspective on the Privacy Dilemma of Camera Glasses**（Bhardwaj, Ponticello, Tomar, Dabrowski, Krombholz；CISPA） | CHI '24 | **佩戴者自己**（而非旁观者）在长期使用摄像眼镜时的隐私困境与情感负担？ | 微纵向日记研究 **N=15**（佩戴者）+ 退出访谈 | 佩戴者认为现有隐私指示器**无效**；会主动采用**外观隐藏技术**（把设备伪装成普通眼镜、遮挡 LED）；佩戴者承担显著的**情感与社会负担**（为他人的反应负责、需要解释设备） | ①**佩戴者会主动破坏你设计的隐私指示器**（隐藏 LED）——Meta 2026-07 强制固件正是针对这点，反向证明了这条研究结论；②laos 若面向 Agent，**"谁为录制行为承担社会成本"必须明确**，否则使用者的自然反应是关掉指示器 | https://doi.org/10.1145/3613904.3642242 ✅；CISPA https://cispa.de/en/research/publications ；USENIX 镜像 https://www.usenix.org/node/301586 |
| 8 | **In situ with bystanders of augmented reality glasses**（Denning, Dehlawi, Kohno；UW） | CHI '14 | 真实公共场所中，旁观者对 AR 眼镜的即时反应？ | **12 场**咖啡馆实地部署 + **31 名**旁观者访谈 | 反应呈两极：**漠然**或**明确负面**；负面反应主要归因于三点——**设备隐蔽、录制太容易、尚未普及**；旁观者普遍希望**被主动询问许可**，并希望有**录制阻断设备** | 经典基线研究。→ ①"被问许可"是 2014 年就已被提出的需求，2026 年仍未有任何主流产品实现；②**阻断工具**（bystander-side jammer/marker）是持续被提出但从未商业化的缺口，laos 可作为开源差异化点 | https://doi.org/10.1145/2556288.2557352 ✅ |
| 9 | **Is Someone Listening? Audio-Related Privacy Perceptions, Behaviors, and Strategies of People Who Are Visually Impaired / Guardians, Pragmatists, and Cynics**（Dunbar, Bascom, Boone, Hiniker；UW） | IMWUT 2021（DOI 10.1145/3478091） | 常开音频的隐私感知如何随"采用前 / 使用中 / 事后"三阶段变化？ | 访谈 + 焦点小组 + 设计工作坊，**35 名**参与者。模态：**音频** | 提出三阶段模型：**adoption / in-the-moment / downstream**；识别三类人群：**guardians（守护者）/ pragmatists（实用主义者）/ cynics（犬儒者）**；隐私决策随阶段迁移，事后（downstream）阶段是现有产品最薄弱的环节 | ①**"事后"阶段是 laos 审计日志的真正战场**——laos 已有全量审计，但缺的是让**被录者**在此阶段能查询/撤回；②"cynic"人群无法被任何隐私机制说服 → 应把资源投向 guardian + pragmatist | https://www.readkong.com/page/is-someone-listening-audio-related-privacy-perceptions-behaviors-and-strategies-of-people-who-are-visually-impaired-4735497 🔶（原始 DOI 10.1145/3478091，ACM 付费墙，本条经二手源转述） |
| 10 | **Privacy behaviors of lifeloggers using wearable cameras** | （期刊论文，lifelogging 方向） | 佩戴 lifelogging 相机一周后，佩戴者与旁观者的实际隐私行为如何？ | **N=36**，佩戴一周 + 问卷 + 退出访谈 | 实际遭遇的**旁观者反对极少**，但参与者**仍然持续担心**旁观者的隐私——即"客观阻力低、主观焦虑高"的错配 | 这条对"要不要做常开"是**反直觉的好消息**：真实社会阻力常低于预期。但佩戴者的焦虑本身会抑制使用 → **降低焦虑的机制（可解释、可撤回）比降低真实阻力的机制更值得投入** | https://www.scilit.com/publications/7d20f852524da22e2de7853e90403c5a 🔶 |
| 11 | **Recorded Work Meetings and Algorithmic Tools: Anticipated Boundary Turbulence** | HICSS-54（2021） | 职场会议被系统性录音，并叠加算法工具后，组织边界如何动荡？ | 跨国职场场景研究（定性 + 理论构建） | 识别 **boundary turbulence（边界动荡）**：当录音用途从"协作辅助"滑向"绩效评估"，员工信任迅速崩塌；**opt-in 机制是维持边界的关键** | 职场是 laos 的高价值场景（会议记录 Agent）。→ **必须在产品层明确"录制数据不得用于评估/考核"**，且这一条要能被技术强制（而不只是政策承诺） | https://aisel.aisnet.org/cgi/viewcontent.cgi?article=1007&context=hicss-54 ✅ |
| 12 | **"Like, Are You Okay With Being Recorded?"**（Tebbe, Aissa, Burger, Zytko） | CSCW Companion '25 | 亲密/社交场景下（VR dating），如何设计被录者的同意机制？ | **16 名**女性 / LGBTQIA+ 利益相关者参与式设计 | 提出三个设计目标：① **视觉中断**以触发显式同意交换；②同意交换应当**定义公私情境边界**；③须有**平台级默认 + 用户可控的阻断工具** | ①同意机制必须由**视觉/可感知中断**触发，而不是后台静默；②**默认 + 可覆盖**优于纯用户自控——这直接支持 laos 的"默认禁录 + 显式触发"架构 | https://dl.acm.org/doi/abs/10.1145/3715070.3749278 ✅；密歇根库 https://deepblue.lib.umich.edu/handle/2027.42/198987 |
| 13 | **Americans and AI 2026**（Pew Research Center） | 调查报告，2026-06-17 发布（调查期 2026-02-17~23） | 美国公众对 AI 的整体态度与信任基线 | 概率抽样 **N=5,119** 美国成年人 | **49%** 使用过 chatbot；**63%** 认为 AI 发展太快；**71%** 认为自己的个人信息比 5 年前更不安全；**67%** 对政府监管 AI **无信心**；**59%** 对企业负责任使用 AI **无信心** | 宏观信任基线：**企业自我承诺的边际信任收益极低**（59% 对企业无信心）。→ laos 的隐私主张必须**可被第三方验证**（开源 + 可审计），不能只写在 README 里 | https://www.pewresearch.org/?p=310973 ✅；PDF https://www.pewresearch.org/wp-content/uploads/sites/20/2026/06/PI_2026.06.17_Americans-and-AI_REPORT.pdf |
| 14 | **英国 body-worn camera（BWC）公众态度调查**（YouGov，HALOS 委托） | 调查报告，2025-06（调查期 2025-06-05~06） | 公众对随身摄像设备的不适感与行为改变 | **N=2,268** 英国成年人 | **18–24 岁：29% 感到不适、65% 表示会因此三思而行**；**55+ 岁：仅 17% 不适、33% 三思**；**38% 从未注意到**被摄录设备，52% 曾见过 | ①**年龄是最重要的分层变量**，年轻人不适感约为老年人的 1.7 倍 → 目标用户若是开发者/年轻群体，摩擦更大；②**38% 的人根本没注意到设备** → 指示器有效性存在天然天花板 | https://halosbodycams.com/press-release-body-worn-camera-survey ✅；报告 PDF https://halosbodycams.com/hubfs/YouGov-BWCs-UK-Survey-Research-Report.pdf 🔶（PDF 直链镜像） |

**研究条目数：14 条**（其中音频专属 5 条、摄像头/通用 9 条）。

### 实证研究里最刺眼的三句话

> - 「**只有 6.1% 的旁观者认为单靠 LED 就够**」——CHI '26, N=525 ✅
> - 「**65%–90% 的旁观者会采取至少一种防御行为**」——CHI '26 ✅
> - 「**地理围栏是所有 PET 中评分最高的（6.8/6.0）**」——CHI '26 ✅

**整合推论（对产品设计）**：
1. **"只录自己" > "可关闭" > "有指示灯"**（MeMic #1 提供最强因果证据，#2/#3/#8 佐证）。
2. **场景感知的自动保护 > 交互式同意协商**（#2 中协商机制可用性仅 2.6/7，手势识别选择率 0%）。
3. **物理/可感知 > 软件/可配置**（#5 N=261、#6、#3 三条独立研究一致）。
4. **事后（downstream）是最大的未满足需求**（#9 明确指出，且目前无主流产品提供被录者查询/撤回通道）。

---

## ③ 争议事件时间线

> 排序：按"对产品设计的教训价值"而非时间。每条含 **时间线 → 后果 → 一句话教训**。

### 事件 1：Humane Ai Pin —— 从 $699 到变砖，11 个月

**时间线**
- 2023-11：Ai Pin 开启预售，**$699 + $24/月**订阅。🔶
- 2024-04：正式上市，媒体评测普遍负面（发热、延迟、续航）。🔶
- 2024-06：充电盒召回（火灾风险）。🔶
- 2024-10：价格降至 **$499**。🔶
- 2024-05 起：Humane 开始寻找买家，要价 **$750M–$1B**。🔶
- **2025-02-18**：HP 宣布以 **$116M** 收购 Humane 大部分资产（含 CosmOS 平台、300+ 专利、团队），**明确不含 Ai Pin 硬件业务**。✅/🔶
- **2025-02-28 12:00 PM PST**：Humane 关停服务器，**所有 Ai Pin 变砖**，消费者数据**永久删除**。仅 **2024-11-15 之后发货**的设备（90 天窗口）可申请退款，申请截止 **2025-02-27**。✅
- 2025：创始人成立 HP IQ 部门并入 HP。🔶

**后果**
- **消费者**：$699 设备变成塑料砖头，绝大多数人拿不到退款（Ars Technica 标题直接引用用户原话 "truly a middle finger"）。✅
- **公司**：$750M–$1B 要价 → $116M 成交，**估值缩水约 85%–88%**。🔶
- **行业信号**：**云端依赖型 AI 硬件的"公司死亡 = 设备死亡"风险被第一次公开演示。**

**一句话教训**：**任何把关键功能绑在公司服务器上的常开传感设备，都必须预置"公司死了设备还能用"的降级路径**——本地优先不是隐私卖点，是**生存卖点**。

**来源**：[Ars Technica 2025-02](https://arstechnica.com/gadgets/2025/02/truly-a-middle-finger-humane-bricking-700-ai-pins-with-limited-refunds/) ✅；[Tom's Hardware](https://www.tomshardware.com/peripherals/hp-buys-humane-ai-start-up-for-us-usd116-million) ✅；[Mashable](https://mashable.com/article/humane-ai-pin-discontinued-killed) ✅

---

### 事件 2：Rewind → Limitless → Meta —— "数据永不出设备"到被 Meta 收购

**时间线**
- 2022：Rewind 上线，核心承诺 **"your data never leaves your device"**（全本地录制、本地索引、本地检索）。✅
- 2024：改名 **Limitless**，推出 **Pendant** 吊坠。隐私承诺开始松动——Pendant 需要**云端转写**，隐私政策明文写 "we will receive audio recordings"。✅
- **2025-12-05**：Meta 宣布收购 Limitless。Pendant **即日停售**。✅
- **2025-12-19**：Rewind 应用**禁用全部屏幕捕获与音频捕获**功能。✅
- 2025-12：**巴西、中国、欧盟、以色列、韩国、土耳其、英国**用户须在 12-19 前自行下载数据，**逾期账户与数据永久删除**。存量 Pendant 用户获至少一年免费 Unlimited；继续使用需同意更新后的隐私政策。✅

**后果**
- **信任反转**：从"数据永不出设备"到"数据交给 Meta"，是这轮周期里**最刺眼的承诺背反**。
- **数据强制迁移**：非美国用户被限期下载，否则销毁——**用户对自己数据的控制权在最需要它的时刻归零**。
- **硬件死亡**：Pendant 从发布到停售不到两年。

**一句话教训**：**"本地优先"如果是竞争优势，就不能是可撤销的产品决策——必须下沉为架构约束**（laos 把它做成 syscall + 内核态 `LAOS_REC` 正是正确方向，但要确保它**不可被用户态应用或后续版本静默放宽**）。

**来源**：[Limitless 官方公告](https://limitless.ai) ✅；[9to5Mac 2025-12-05](https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/) ✅；[MLQ.ai](https://mlq.ai/news/meta-acquires-ai-wearables-startup-limitless-ending-sales-of-pendant-device) ✅

---

### 事件 3：Friend 吊坠 —— 被广告牌反噬的"监控"标签

**时间线**
- 2023-10：Avi Schiffmann 推出首个产品，原名 **Tab**（见事件 10）。🔶
- 2024-02-06：以 **$1.8M** 买下 `friend.com` 域名并更名 Friend。🔶
- **2025**：纽约地铁投放 **11,000+ 车厢广告 + 1,000+ 站台海报 + 130 块城市面板**，总花费 **<$1M**。🔶
- **2025（同步）**：广告被**大规模涂鸦**——"AI doesn't care"、"surveillance capitalism"、"AI is not your friend"、"this is surveillance"。催生专门的在线"破坏博物馆"网站。✅（Ars Technica 报道）
- 2025：扩展到洛杉矶（Fortune 报道 500+ 公交站亭）、芝加哥、巴黎。**2026-02 巴黎广告同样被涂鸦**。🔶
- **2025-11**：CNN 报道累计融资约 **$10M**、售出约 **5,000 台**，价格从 $99 涨至 $129。🔶
- **2026-07-30/31**：发布 **Friend 2.0，售价 $249**，新增**扬声器语音回复**，$10/月记忆订阅。Schiffmann 表示因 **GDPR 合规成本可能暂不进入欧盟**。🔶

**后果**
- **舆论**：这是全天候录音产品遭遇的**第一次有组织的线下抵制**——不是负评，是物理破坏广告牌。组织化反对（Boycott AI、stopfriend.com）持续存在。🔶
- **监管/合规**：隐私政策 v2 被指收集 ambient 音视频 + 生物识别（面部/声音）、保留期超 5 年、可能用于训练模型；存在 **BIPA**（伊利诺伊生物识别信息隐私法）诉讼风险；**欧洲上市无限期推迟**。🔶
- **商业**：约 5,000 台销量 / $10M 融资 —— **投入产出比极差**。🔶

**一句话教训**：**"全天候录音"这个卖点本身在公共场所是负资产。** Friend 把"我一直在听"当营销主张，直接触发了公众对监控的本能抵触；**隐私能力应该是产品的免责声明，不应该是广告语**。

**来源**：[Ars Technica 2025-10（涂鸦事件）](https://arstechnica.com/tech-policy/2025/10/vandals-deface-ads-for-ai-necklaces-that-listen-to-all-your-conversations/) ✅；[Cybernews](https://cybernews.com/ai-news/ai-necklace-friend-wearables-privacy-nyc/) 🔶；[404 Media（diss track）](https://www.404media.co/ai-companion-device-releases-diss-track-against-friend) 🔶；[Consumer Rights Wiki（隐私政策分析）](https://consumerrights.wiki/index.php?title=Friend_app) 🔶

---

### 事件 4：Meta Ray-Ban —— LED 防篡改强制固件（2026-07）

**时间线**
- **2026-07-07/08**：Meta 推送 **v26 强制固件**，覆盖 **Ray-Ban Meta / Oakley Meta / Meta Glasses**。核心机制：**对录制指示灯 LED 做硬件完整性校验；一旦检测到 LED 被物理篡改/钻除，永久禁用摄像头**——不可跳过、不可回滚。✅
- 同月：Meta 同步清理第三方"LED 拆除服务"的广告与账号，并宣称 "No other kind of camera has done this"。✅
- **2026-07-31**：Engadget 调查发现，售价约 **$2 的遮光贴纸**（TikTok Shop 上约 $15 一张）即可绕过该防篡改机制。🔶

**后果**
- **正面**：业界第一次有厂商把"指示器不可绕过"做成**硬件级强制**，而非政策承诺。
- **负面**：**$2 贴纸即破**，证明"硬件防篡改"只要还是"贴片式"就注定是可以被贴纸对付的军备竞赛。
- **监管背景**：汉堡数据监管机构同期认定 LED **太弱、不足以构成知情同意**（见事件 7）——即**监管与厂商对同一机制的评估结论相反**。

**一句话教训**：**指示器防篡改的价值不在"防住"，而在"抬高成本 + 留下可归责证据"**；真正有效的方向是 CHI '26 评分最高的**地理围栏/场景自动禁录**，而不是在贴纸层面打补丁。

**来源**：[Meta 官方 Bystander Privacy 说明 PDF](https://about.fb.com/wp-content/uploads/2026/07/Bystander-Privacy.pdf) ✅；[Machine Herald](https://machineherald.io/article/2026-07/15-meta-locks-down-ray-ban-glasses-privacy-light-with-mandatory-firmware-update-as-it-preps-a-non-blinking-super-sensing-prototype) 🔶；[Smart Glasses Daily](https://smartglassesdaily.com/en/article/meta-hard-disables-smart-glasses-with-tampered-privacy-leds-33ydu) 🔶；[Engadget 2026-07-31（$2 贴纸）](https://www.smartwearables.io/news/meta-ray-ban-privacy-light-camera-kill-mandatory-update-v26-july-2026) 🔶

---

### 事件 5：Meta Ray-Ban —— 肯尼亚外包人工标注丑闻

**时间线**
- **2026-02 底**：瑞典《Svenska Dagbladet》与《Göteborgs-Posten》联合调查披露：内罗毕 **Sama** 公司员工审阅 Ray-Ban Meta 用户上传的视频，内容包括**如厕、更衣、性行为、银行卡**，且**未做匿名化**。✅
- **2026-04-16**：Sama 向 **1,108 名员工**发出裁员通知，通知期仅 **6 天**。Meta 回应称 Sama "不符合我们的标准"；Sama 否认，称**从未收到任何不合格通知**；劳工组织指控为**对吹哨的报复**。✅/🔶

**后果**
- **1,108 人失业**，被普遍解读为举报的连带代价。
- 直接摧毁了"人工审核只是常规流程"的行业叙事，把**"云端处理必然涉及陌生人观看"**这一事实推到台前。
- 强化了 laos 类产品最有力的论据：**ASR 全本地不只是延迟/成本优化，它是唯一能杜绝"陌生人看到"的路径**。

**一句话教训**：**只要音频/视频离开设备，你的隐私承诺就等价于你对供应商的管控能力**——而这条链路上任何一环节失控，代价由用户承担。

**来源**：[The Next Web](https://thenextweb.com/news/meta-smart-glasses-sama-kenya-workers) ✅；[GIGAZINE](https://www.gigazine.net/gsc_news/en/20260303-meta-smart-glasses-data-privacy/) ✅；[The Decoder](https://the-decoder.de/meta-laesst-subunternehmer-in-kenia-intimate-nutzervideos-aus-ki-brillen-sichten/) ✅；[安全内参](https://www.secrss.com/articles/88177) 🔶

---

### 事件 6：Meta "NameTag" 人脸识别代码曝光

**时间线**
- 2026-02-13：《纽约时报》/ TechCrunch 报道 Meta 考虑在 2026 年推出人脸识别功能 **"Name Tag"**。🔶
- **2026-06-04**：WIRED 报道，装机量 **5000 万+** 的 **Meta AI companion app** 中包含**休眠状态的 NameTag 代码**：SCRFD 人脸检测 → 裁剪 → **SFace 生成 2048 维生物特征模板** → 本地 gallery 匹配 → 可触发 "Person recognized"。代码自 **2026-01** 起已随 app 分发。✅（EFF Threat Lab 静态分析验证）
- **2026-06-05**：Meta 发布 app 更新，**删除**该代码。✅
- Meta 回应称"纯探索性，未做最终决定"；Ray-Ban 官方 FAQ 仍称"未使用人脸识别"。🔶
- 同期：德州总检察长 **Ken Paxton** 就生物识别隐私展开调查；**75 家公民自由组织**（含 ACLU、EPIC）于 2026-04 联署要求停止。🔶

**后果**
- **"休眠代码"成为新的信任杀伤方式**：功能没上线，但代码已经在 5000 万台设备上躺着，随时可远程激活。
- 直接推翻厂商"我们不做 X"的口头承诺的可信度。
- 监管从"你做了什么"转向"**你能做什么**"。

**一句话教训**：**隐私承诺必须是"代码里不存在的能力"，而不是"功能开关关掉了的能力"。** 对 laos 的直接含义：**不要实现"远程启用人脸识别/声纹识别"的能力，哪怕默认关闭**——一旦存在，你的承诺就不可信。

**来源**：[iTechGuides（NameTag 梳理）](https://www.itechguides.com/meta-reportedly-developed-facial-recognition-for-its-smart-glasses-but-nametag-is-not-publicly-available) 🔶；[IDTechWire（EFF 验证）](https://idtechwire.com/researchers-find-dormant-face-recognition-code-in-metas-smart-glasses-app/) 🔶；[Elephas（时间线）](https://elephas.app/resources/meta-ai-smart-glasses-facial-recognition) 🔶

---

### 事件 7：Meta Ray-Ban —— 汉堡监管机构认定 + "pervert glasses" 舆论

**时间线（监管侧）**
- **2026-05**：法国 **CNIL** 对智能眼镜发出警告。🔶
- **2026-06**：德国波茨坦市禁止在**公共泳池/桑拿**佩戴智能眼镜。🔶
- **2026-07-30**：德国 ARD tagesschau 报道监管动向。✅
- **2026-09-10**：MLex 报道，**汉堡数据保护机构（Hamburg DPA，Thomas Fuchs）实测认定**：① Ray-Ban Meta 眼镜 **"generally" 不得录制用户亲友圈以外的人**；② **LED 太弱，不足以构成知情同意**；③ 通常**也缺乏用这些录音训练 AI 的合法依据**；正与爱尔兰 DPC 沟通。✅
- 德国 **TDDDG §27** 禁止将摄录设备伪装成日常物品，可处罚款或最高 **2 年监禁**。✅
- **HateAid** 已向法兰克福检方提起**刑事控告**，对象包括 Meta Platforms Technologies Ireland、Luxottica、Fielmann、Apollo-Optik、Mister Spex、MediaMarkt。🔶
- 德国 **BNetzA** 表示"正在市场监督中"，尚未正式调查。🔶
- **EDPB** 智能眼镜报告预计 2026 年夏末发布。🔶

**时间线（舆论侧）**
- 2026-03：WIRED 报道 "Meta creeps" 现象。🔶
- **2026-07-26/28**：Instagram 负责人 **Adam Mosseri** 宣布移除用眼镜偷拍骚扰的内容；**Meta 确认封禁至少 2 个各超 100 万粉丝的 pickup-artist 账号**（@itspolokid、@rizzzcam）。✅
- 同期：Monopoly Events 在英国 Comic-Con **禁用**智能眼镜；歌手 **Lorde** 公开抨击。🔶
- 2026-06~07：Police Scotland 调查 TikToker Scott Margerison（苏格兰自驾偷拍）。🔶

**后果**
- **首次有监管机构对具体产品形态给出实测性负面认定**（"不得录制亲友圈以外的人"），而非抽象的合规建议。
- **销售渠道被卷入刑事风险**（眼镜连锁店、电器卖场同被控告）——**这是分销层面的系统性风险**。
- **"pervert glasses" 成为主流媒体通用标签**，直接压制了智能眼镜的社交可接受性。

**一句话教训**：**当监管机构开始评估"你的指示器够不够亮"时，你已经输了这场军备竞赛。** 唯一可持续的解法是把敏感场景设为**默认不可录**（地理围栏，CHI '26 评分最高的机制），而不是把"看得见"做到极致。

**来源**：[MLex 2026-09-10](https://www.mlex.com/mlex/data-privacy-security/articles/2523664/) ✅；[Mezha（刑事控告）](https://mezha.ua/en/news/u-nimechchini-podali-kriminalnu-skargu-cherez-prodazh-ray-ban-meta-314131) 🔶；[The Next Web（pervert glasses）](https://thenextweb.com/news/instagram-meta-glasses-harassment-ban-pervert-glasses) ✅；[Fortune 2026-07-28](https://fortune.com/2026/07/28/ray-ban-meta-pervert-glasses-secret-videos-women) ✅；[Futurism](https://futurism.com/artificial-intelligence/meta-ban-creeps-ai-pervert-glasses) 🔶；[Cybernews](https://cybernews.com/news/instagram-bans-meta-glasses-creeps-pranksters) 🔶

---

### 事件 8：Microsoft Recall —— 从默认开启到默认关闭

**时间线**
- **2024-05-20**：Build 大会宣布 Recall，原定 2024-06-18 随 Copilot+ PC 推出（**默认开启**）。✅
- 2024-06：安全研究者（Kevin Beaumont 等）证明快照数据库**明文存储、可轻易提取**；**首次推迟**。✅
- 2024-09-30：宣布集成 **Purview 敏感信息过滤**。✅
- **2024-10-31**：**再次推迟**至 12 月。✅
- 2024-12：Dev Channel Insider 预览。✅
- 2025-04-10：进入 Release Preview。✅
- **2025-04-25**：向零售 Copilot+ PC 开放，**EEA（欧洲经济区）除外**。架构大改：改为 **opt-in（默认关闭）**、可卸载、强制 **Windows Hello**、**VBS Enclave + TPM** 加密、BitLocker 必需、默认排除隐私浏览。✅
- 2025-06：EEA 导出工具（一次性/连续导出码，**Microsoft 无法恢复**）+ 完全重置 + 默认存储上限从无限改为 **90 天**。✅
- 企业管理：`AllowRecallEnablement` 策略，**企业环境默认禁用/移除**。✅

**2026 年是否加入音频捕获？——没有。** Microsoft 官方文档明确："**Recall does not record audio or save continuous video**"。✅

**后果**
- **发布推迟两次、延迟约 10 个月、EEA 至今受限**——这是大型厂商在隐私阻力下的真实代价。
- 架构被迫从"默认开启 + 明文库"重写为"默认关闭 + 硬件飞地 + 生物识别解锁 + 90 天 TTL"。
- **Microsoft 明确拒绝加入音频**——业界最大软件厂商用行动表态：**音频捕获的隐私成本高于其产品价值**。

**一句话教训**：**Recall 的最终形态就是 laos 隐私架构的参照系**——opt-in 默认、硬件级隔离、强制生物识别、TTL 上限、管理员可全局禁用、区域化合规。**laos 已有的 `LAOS_REC=0` + 全量审计 + 6h 即焚，恰好对应其中三条；缺的是"硬件级隔离"和"管理员/组织级策略"。**

**来源**：[Microsoft Learn 官方管理文档](https://learn.microsoft.com/en-us/windows/client-management/manage-recall) ✅；[AIcerts（推迟时间线）](https://www.aicerts.ai/news/microsoft-recall-faces-new-os-feature-setback/) 🔶；[TechRepublic（扩大推送）](https://www.techrepublic.com/article/news-microsoft-recall-expands-rollout) 🔶；[WinBuzzer 2024-11-01（二次推迟）](https://winbuzzer.com/2024/11/01/microsoft-delays-controversial-windows-recall-feature-again-due-to-privacy-concerns-xcxwbn/) ✅；[WinBuzzer 2025-06-16（EEA 导出码）](https://winbuzzer.com/2025/06/16/microsofts-windows-recall-feature-gets-export-tool-in-the-eu-amid-ongoing-privacy-concerns-xcxwbn/) ✅

---

### 事件 9：Bee → Amazon —— 一个尚未爆发的定时炸弹

**时间线**
- 2022：Bluush Inc. 成立，累计融资约 **$8.5M**。🔶
- 产品：**$49.99 腕带 + $19/月**订阅。核心隐私主张：**不存储原始音频**，只存转写/摘要，可随时删除，声称不用于训练。🔶
- 正在开发按**主题/地点自动暂停**的边界功能。🔶
- **2025-07-22/23**：Amazon 确认收购 Bee（**金额保密**）。发言人 Alexandra Miller 称"深度重视客户隐私与安全"、"将与 Bee 合作给用户更多控制权"。✅
- **关键缺口**：Amazon **未承诺延续"不保存音频"政策**。🔶
- 背景：**2025-03-28 起，Amazon 移除了 Echo 的"不发送录音到云"选项**。🔶

**后果**
- 目前**尚未爆发**争议——这本身是信号：**收购完成到政策变更通常有 6–18 个月滞后期**（参考 Rewind 2024 改名 → 2025 被收购）。
- Bee 原本的"不存原始音频"立场，与 Amazon Echo 同期移除"不上传"选项的动作方向**相反**。

**一句话教训**：**对收购方的隐私尽调，看的不是被收购方当下的政策，而是收购方既有产品线的政策轨迹。** 对 laos 的含义：**开源 + 协议层约束（而非公司政策）是唯一能抵抗"被收购后政策反转"的机制**。

**来源**：[The Verge 2025-07-22](https://www.theverge.com/news/711621/amazon-bee-ai-wearable-acquisition) ✅；[GIGAZINE 2025-07-23](https://gigazine.net/gsc_news/en/20250723-amazon-buys-bee-ai-wearable-device) ✅；[Market Business News](https://marketbusinessnews.com/amazon-buys-ai-wearable-startup-bee/440337) 🔶；[TMCnet（Echo 政策变更）](https://blog.tmcnet.com/blog/rich-tehrani/ai/key-takeaways-3.html) 🔶

---

### 事件 10：Rabbit R1 —— 工程能力的信任崩塌

**时间线**
- 2024：R1 上市。🔶
- **2024-05-01**：Ars Technica / The Verge 揭露 **R1 只是一个 Android App**，可被提取并运行在普通手机上。✅
- **2024-06**：Engadget 报道 Rabbitude 团队发现**硬编码 API 密钥**（ElevenLabs、Azure、Yelp、Google Maps、SendGrid），可访问 R1 的所有历史响应、致砖、篡改响应。Rabbit 称代码由"已被解雇、仍在调查中的员工"泄露。✅/🔶
- **2024-07**：公司承认**所有用户的聊天与配对数据记录在设备上且无法删除**，后补上出厂重置。🔶
- **2024-07**：David Buchanan 的 **carroot jailbreak** 揭示设备记录**精确位置、Wi-Fi 名、基站 ID、IP、用户令牌、全部语音输入及转写文本**，且**无 SIM 卡也上传**。并指出 GPL 违规（闭源驱动链接 GPL 内核镜像）。🔶

**后果**
- 产品信誉基本归零；"AI 硬件"品类整体被牵连质疑。
- **技术层面的关键事实**：**"全部语音输入及转写文本"都存在于设备上并可被提取** —— 说明"本地存储"如果没有**加密 + 访问控制 + TTL**，只是把风险从云端搬到本地。

**一句话教训**：**"本地处理"不等于"本地安全"。** laos 的 6 小时即焚是对的方向，但必须确认**加密落盘 + 密钥不可被用户态任意读取 + 到期确定性擦除**，否则本地存储只是换了个被拖库的地方。

**来源**：[Ars Technica 2024-05-01](https://arstechnica.com/gadgets/2024/05/rabbit-r1-ai-box-is-just-an-android-app-and-the-software-can-run-on-a-phone/) ✅；[GIGAZINE（carroot jailbreak）](https://gigazine.net/gsc_news/en/20240718-rabbitos-jailbreaking/) 🔶；[Wikipedia: Rabbit r1](https://en.wikipedia.org/wiki/Rabbit_r1) 🔶

---

### 事件 11：Tab（Friend 前身）与 Omi —— 开源也不自动等于可信

**Tab（2023）**
- Avi Schiffmann 于 2023 推出，**$600** 早期单位售出 **$100,000**，融资 **$1.9M**（估值 $15–20M），续航 30 小时。🔶
- 架构：音频经**蓝牙 → 手机 → 云 → ChatGPT 转写**；承诺不存储/出售/共享用户数据。🔶

**Omi（BasedHardware）**
- **全栈开源（MIT 许可）**：固件、后端、App 全部开源，**可自托管**。$89 吊坠，**24h+ 连续捕获**，64GB 板载存储，一键数据删除。✅
- **批评点**：①默认数据存 **Firebase / Google Cloud Storage** 而非本地；②**始终监听、无明确旁观者指示**；③规划 **2026–2027 推出脑机接口（EEG）模块**，引发"精神隐私"担忧。🔶
- 学生媒体（The Battalion）评论标题即 "Our Minds Are Not Public Property"。🔶

**后果与教训**
- **Omi 证明了"开源"本身不足以解决旁观者问题**——代码开源解决的是**使用者对厂商**的信任，完全不解决**旁观者对使用者**的信任。
- **教训**：开源解决"你有没有偷偷上传"，解决不了"你在录我"。**这两件事需要两套完全不同的机制**（前者靠审计/本地化，后者靠可感知性/场景禁录/被录者权利）。

**来源**：[Omi 梳理](https://chatgate.ai/post/omi-2) 🔶；[The Battalion（评论）](https://thebatt.com/opinion/opinion-our-minds-are-not-public-property/) 🔶；[TechBloat](https://www.techbloat.com/omi-a-competitor-to-friend-wants-to-boost-your-productivity-using-ai-and-a-brain-interface.html) 🔶；[Tab 对比](https://www.toolify.ai/ai-news/the-ai-wearable-wars-tab-vs-rewind-who-will-win-2494504) 🔶

---

**争议事件条目数：11 个独立事件**（覆盖用户要求的 7 类 + 4 个补充）。

---

## ④ 业界成型的隐私设计范式清单

> 判断标准：该机制是否已被**至少两款商业产品**采用，或已有**同行评审实证研究**评估。
> "有效性证据"一列严格区分：**实证（有 N、有统计检验）** vs **监管认可** vs **仅厂商声称**。

| 机制 | 代表产品 | 有效性证据 | 成本 / 代价 |
|---|---|---|---|
| **可见录制指示器（LED）** | Meta Ray-Ban（v26 防篡改）、Apple（状态栏橙/绿点）、Recording 指示灯 | **实证：弱。** CHI '26 N=525：**仅 6.1% 旁观者认为单靠 LED 够**；41.6% 说太小易忽视、38.6% 强光下不可见、41.3% 可被遮挡 ✅。**监管：汉堡 DPA 2026-09 认定"LED 太弱，不足以构成知情同意"** ✅ | 低（硬件成本极小）；但**防篡改是持续军备竞赛**——Meta v26 被 $2 贴纸绕过 🔶 |
| **硬件物理开关 / 物理断电** | Plaud 录音笔（物理 REC 键）、传统录音笔 Hold 键、Candid Mic（能量采集供能） | **实证：强。** CSCW '22 N=261：**带内建物理控制的设备被评为更可信、更易用**，显著优于非物理机制 ✅；Candid Mic within-subjects：可感知供能 > 静音按钮 ✅；CSCW '20 tangible privacy：旁观者因不确定而自发采用物理遮挡 ✅ | 中（BOM + 结构成本）；且**可感知性与设备美观/隐蔽性直接冲突**（CHI '24 N=15：佩戴者会主动隐藏指示器 ✅） |
| **一键全局禁录（kill switch）** | **laos `LAOS_REC=0`**、Microsoft Recall（`AllowRecallEnablement` 企业策略，默认禁用）、各类设备飞行模式 | **实证：间接。** CSCW '18 N=34：**现有隐私控制极少被使用，因为与用户需求不匹配** ✅ → 关键不是"有没有"，而是**是否默认、是否一键、是否可感知**。**监管：Recall 因默认开启被推迟两次、EEA 受限** ✅ | 极低（laos 已实现）。**但 laos 的缺口在于它是软件态/内核态的，旁观者不可感知** |
| **本地优先处理（on-device）** | laos（本地 ASR）、Apple Private Cloud Compute、Google Gemini Nano、Omi（可自托管） | **实证：无直接社会接受度实验**，但**反向证据极强**：Sama 1,108 人失业丑闻 ✅、Rewind "永不出设备"承诺反转 ✅。**监管：汉堡 DPA 认定缺乏把录音用于 AI 训练的合法依据** ✅ | 高（算力、模型体积、功耗）；端侧 ASR 精度仍低于云侧大模型 |
| **即焚 / TTL（短期保留）** | **laos 6 小时**、Microsoft Recall（默认 **90 天** 上限）、Snapchat（阅后即焚） | **实证：未证实**（无对照实验证明 TTL 提升接受度）。**监管：间接认可**——Recall 将"无限保留"改为 90 天才得以在 EEA 推进 ✅ | 低；但会损失"回溯检索"的产品价值（6 小时对 diary 类场景偏短） |
| **审计日志（谁在何时录了什么）** | **laos 全量审计（含被拒请求）**、企业 DLP 系统 | **实证：无直接评估**，但 IMWUT '21 指出 **downstream（事后）阶段是现有产品最薄弱环节** ✅；CHI '26 四个权衡之一即 **accountability vs exposure** ✅。**业界罕见——laos 在此处领先** | 低（laos 已实现）。**代价：审计日志本身成为高价值攻击目标**（Rabbit R1：全部语音输入 + 转写文本可被提取 🔶）→ 必须与加密/访问控制配套 |
| **被录者可见性与撤回权** | **几乎无商业产品实现**。研究原型：MeMic、协商平台（CHI '26 B4）、阻断标记（CHI '26 B2） | **实证：需求强烈但机制难做。** CHI '14 N=31：旁观者**普遍希望被询问许可** ✅；CHI '26：协商平台隐私保护评分高（5.6/5.8）但**可用性仅 2.6/7** ✅；**手势识别公开场景选择率 0%** ✅ | 高。**结论：不要做交互式协商，做默认保护 + 事后可查询/撤回** |
| **可排除名单（App / 网站 / 时段 / 地点）** | Microsoft Recall（应用/网站过滤 + 默认排除隐私浏览）✅、Bee（规划中的"按主题/地点自动暂停"）🔶 | **实证：这是评分最高的机制类别。** CHI '26：**Geofencing 隐私保护评分 6.8（HCI）/ 6.0（用户），为 12 种 PET 中最高**；敏感场景选择率 **60%–70%** ✅ | 低—中（需要位置/上下文感知）；**隐私悖论：地理围栏本身需要知道你在哪** → 围栏判定必须本地完成 |
| **只录自己（self-VAD / 声纹门控）** | MeMic（研究原型）、Plaud（通话录音）、部分会议设备的说话人分离 | **实证：最强。** CHI EA '24 N=168：**self-recording 相比连续录音显著降低社会恐惧与隐私担忧**，社会接受度显著提升；检测错误率 **0.09 ± 0.03** ✅ | 中（需 self-VAD / speaker embedding）；**误判代价**——漏录自己 / 误录他人 |
| **数据最小化（不存原始音频）** | Bee（声称不存原始音频）🔶、laos（转写后即焚） | **实证：未证实**。**但监管方向一致**——GDPR 数据最小化原则（见已有文档 §6） | 中（无法回溯校对 ASR 错误、无法做说话人分离后处理） |
| **透明度报告 / 第三方审计 / 认证** | **业界基本缺位**。无主流常开录音产品发布过独立的第三方隐私审计报告 | **实证：缺位即风险。** Pew 2026 N=5,119：**59% 美国人对企业负责任使用 AI 无信心、67% 对政府监管无信心** ✅ → **厂商自证的边际收益极低** | 高（审计费用、流程）；**但对 laos（开源项目）而言，这是成本最低、差异化最大的一条** |
| **明确排除生物识别能力（架构级）** | Meta 反例：NameTag 休眠代码随 5000 万装机分发，2026-06-05 才删除 ✅ | **实证：反向证据。** 休眠代码被 EFF Threat Lab 静态分析发现并曝光，直接摧毁"我们不做人脸识别"的承诺可信度 ✅ | 低（**不做**某件事的成本）；代价是放弃功能可能性 |

### 范式清单的三条收敛结论

1. **业界已经在"使用者侧"机制上收敛**（指示器 + 物理开关 + 一键禁录 + 本地优先 + TTL），**在"旁观者侧"几乎全是空白** —— 这正是汉堡 DPA 2026-09 认定的核心问题。
2. **有效性排序（按实证强度）**：self-VAD/只录自己（N=168 因果实验）> 物理可感知开关（N=261）> 地理围栏自动禁录（评分最高）> 指示器（仅 6.1% 买账）> 交互式同意（可用性 2.6/7）。
3. **laos 在"审计日志"这一项上已经领先业界**，在"self-VAD"和"地理围栏"两项上完全空白。

---

## ⑤ 被低估的风险 / 被高估的风险

### 被低估的风险：**"Agent 自主发起录音"带来的同意链断裂**

**为什么被低估**：所有人（包括 laos 现有设计）都在讨论"人按了按钮才录"，但 laos 的产品定位是**给 AI Agent 用的 OS**——录音的发起方天然就是 Agent，而不是人。`LAOS_REC=0` 防的是"系统被滥用"，防不住"Agent 在用户许可范围内、合乎规则地、但用户此刻并不知道地、持续地录"。

**证据链**：
- CHI '26 N=525：**context 是接受度的首要决定因素**（场景主效应 `F=56.440, p<.001`），而 Agent 恰恰是最不擅长判断 context 的参与者 ✅
- CHI '26：**65%–90% 旁观者会采取防御行为**，且**只有 6.1% 认为 LED 够** ✅ → 一旦 Agent 在健身房/医院/更衣室这类场景发起录音，旁观者的反应是躲避或投诉（正式投诉峰值 13%）
- IMWUT '21：隐私决策的 **downstream（事后）阶段是最薄弱环节** ✅ → Agent 引发的录音，事后问责链比人工录音更长

**风险的具体形态**：laos 目前的"显式 syscall 触发"假设了触发者是有意图的人。**当触发者是一个每 30 秒决定"这段对话值得记住"的 Agent 时，"显式触发"在技术上成立，在社会学上完全失效**——旁观者看到的仍是一台一直在录的机器。

**建议**：laos 需要在 syscall 之上加一层 **context gate**（场景/地理围栏 + 说话人归属判定），让 Agent 的录音请求在敏感场景下**内核级被拒**，而不是等事后审计发现。这也正好是 CHI '26 评分最高的机制（Geofencing 6.8/6.0）。

### 被高估的风险：**"黑客远程窃听麦克风"**

**为什么被高估**：这是隐私讨论里最容易想到的威胁模型，但**在 2024–2026 年所有真实发生的重大争议中，没有一起是"远程黑客打开麦克风窃听"**。真实发生的全是：
- **厂商自己改政策**（Rewind → Meta：承诺从"永不出设备"反转为云端转写 + 被收购）✅
- **外包人员观看**（Sama 1,108 人，含浴室/更衣/性爱片段）✅
- **休眠功能被预埋**（NameTag，5000 万装机，2026-01 分发、2026-06 才删）✅
- **公司死亡导致设备变砖 + 数据销毁**（Humane，2025-02-28）✅
- **本地存储无加密被提取**（Rabbit R1 carroot jailbreak：全部语音输入 + 转写文本）✅

**结论**：**真正的威胁模型是"合法但违背预期的数据使用"，不是"非法的入侵"。** 远程入侵是低概率、高可见、厂商有强动机修复的事件；而"厂商按条款合法地把你的音频用于训练"是高概率、低可见、用户几乎无救济的事件。

**对 laos 的资源配置含义**：与其把工程预算投向麦克风访问的攻防加固，**不如投向**：
1. **让"本地处理"成为架构不可撤销的约束**（防 Rewind 式反转）
2. **让审计日志可被第三方验证**（防 NameTag 式预埋）
3. **让"公司死了/项目停了"仍有降级路径**（防 Humane 式变砖）

---

## ⑥ 对 laos 的隐私缺口分析

### 现状对照表

| 业界范式 | laos 现状 | 评级 |
|---|---|---|
| 显式触发（opt-in / 默认关闭） | ✅ 必须显式 syscall | **领先**（对标 Recall 2025-04 才改为 opt-in） |
| 一键全局禁录 | ✅ `LAOS_REC=0` | **领先但不可感知** |
| 全量审计（含被拒） | ✅ | **业界罕见，领先** |
| 本地优先 ASR | ✅ | **主流最优解** |
| 即焚 / TTL | ✅ 6 小时 | **优于 Recall 90 天，但缺乏分级** |
| **只录自己（self-VAD / 声纹门控）** | ❌ **完全空白** | **最高优先级缺口**（MeMic N=168 因果证据） |
| **场景感知自动禁录（地理围栏）** | ❌ **完全空白** | **高**（CHI '26 评分最高机制 6.8/6.0） |
| **可感知指示器 / 物理开关绑定** | ❌ 内核态，外部不可见 | **中高**（CSCW '22 N=261 实证） |
| **被录者事后查询 / 撤回** | ❌ 审计日志不对被录者开放 | **中**（IMWUT '21 指出 downstream 最薄弱） |
| **第三方审计 / 形式化验证** | ❌ | **中低，但成本最低、差异化最大** |
| 审计日志加密与访问控制 | ⚠️ `未证实` | **中**（Rabbit R1 教训） |
| 组织级策略（管理员强制禁录） | ❌ | **低**（对标 Recall `AllowRecallEnablement`） |

### 按优先级排序的 5 条可执行建议

---

#### P0 — 在 syscall 层之上加 **self-VAD / 说话人归属门控**（`LAOS_REC_SPEAKER=owner`）

**为什么最优先**：这是唯一有**因果对照实验**（N=168）证明能显著提升社会接受度的机制 ✅，而 laos 目前完全空白。

**具体做法**：
1. 在 `drv_rec` 的录音通路中，把"是否录"的判定从"是否有人说话"（通用 VAD）改为"**是否是 device owner 在说话**"（self-VAD + speaker embedding）。
2. MeMic 用的是**加速度计检测佩戴者发声**（硬件 self-VAD，检测错误率 0.09±0.03）——对耳机/吊坠/贴身设备形态，这条路比纯声纹更鲁棒且**天然不采集他人声音**。
3. 提供一个 `LAOS_REC_SCOPE` 枚举：`off` / `owner_only`（默认）/ `all`。`owner_only` 下，非 owner 的语音段在**进入缓冲区之前**就被丢弃，不落盘、不进 ASR。
4. 审计日志增加字段：`rejected_speaker_mismatch`，统计被丢弃的时长——**把"我们确实没录别人"变成可核对的数字**。

**验收标准**：错误接受率（把他人声音当作 owner）< 5%；可通过 `tests/test_rec.py` 增加双说话人语料回归测试。

---

#### P1 — 引入 **context gate**：场景/地理围栏自动禁录

**为什么**：CHI '26 中 Geofencing 是 12 种 PET 里评分最高的（HCI 6.8 / 用户 6.0），敏感场景选择率 60–70% ✅；汉堡 DPA 2026-09 的认定也指向"敏感场景默认不可录" ✅。

**具体做法**：
1. 新增 `LAOS_REC_ZONES` 配置：一组"禁录区"规则（可基于 GPS 围栏、Wi-Fi SSID/BSSID、蓝牙信标、或用户显式标注的地点）。
2. **判定必须全本地完成**——围栏逻辑不能依赖任何网络服务，否则围栏本身成为位置泄露源。
3. 进入禁录区时：**内核级拒绝**录音 syscall，并返回 `E_PERM`，同时**写审计**（符合现有"被拒也记"的设计）。
4. 提供一组开箱即用的默认敏感类别标签（医疗、更衣/卫浴、宗教场所、教育机构），但不预置具体坐标——**避免"我们需要知道全世界的医院在哪"这个不可能任务**。

**验收标准**：进入禁录区后任何 Agent 的录音请求 100% 被拒且被审计；Agent 无法通过任何用户态手段绕过（这与 `LAOS_REC=0` 的保证等级一致）。

---

#### P2 — 把 `LAOS_REC=0` 从内核态**外化**为可感知状态

**为什么**：CSCW '22 N=261 实证——**物理/可感知控制显著优于软件控制** ✅；CSCW '20 发现旁观者因不确定而自发贴胶带/拔电源 ✅。laos 的 `LAOS_REC=0` 目前只有内核和运维知道，**旁观者无从判断**。

**具体做法**：
1. 定义统一的 **"recording state" 内核导出接口**（sysfs / dev node / D-Bus signal），让任何 UI、LED、外壳指示灯都能订阅。
2. 提供**硬件绑定约定**：若设备有硬件 mute switch，内核应把它与 `LAOS_REC` 强制绑定（硬件关 = 内核禁录，用户态无法覆盖）。
3. 状态要**三态而非二态**：`disabled`（全局禁录，指示器灭）/ `armed`（允许但未在录）/ `recording`（正在录，指示器亮）。**`armed` 与 `recording` 的区分是关键**——"mic on by default" 与 "mic off by default" 在接受度上差异巨大（MeMic 明确采用默认关麦）。
4. 在审计日志中记录状态变更事件，使其可被外部审计工具对账。

**验收标准**：任何第三方外壳/LED 仅需订阅一个接口即可反映真实录音状态，且无法在不触发审计的情况下伪造。

---

#### P3 — 给审计日志加**加密 + 访问控制 + 被录者查询通道**

**为什么**：
- 反例：Rabbit R1 的 carroot jailbreak 提取出**全部语音输入及转写文本** 🔶 → **审计日志本身是最高价值的攻击目标**。
- 正例：IMWUT '21 指出 **downstream（事后）阶段是现有产品最薄弱环节** ✅ → 这是 laos 把领先项转化为护城河的机会。

**具体做法**：
1. **加密落盘**：审计日志与音频缓冲使用设备绑定的密钥加密；确保 `LAOS_REC=0` 状态下密钥不可被用户态读取。
2. **TTL 分级**：目前统一 6 小时。改为分级——原始音频 6 小时（保持）、审计元数据默认 90 天（对齐 Recall）、用户可全局下调至 0（纯内存）。
3. **被录者查询接口**（这是业界无人做的差异化点）：提供一个本地 HTTP/CLI 端点，任何人可凭**设备在某时段的可见 ID** 查询"这段时间里有没有关于我的录音"，并可提交**撤回请求**。请求进入审计日志并等待 owner 处理——**不自动删除**（否则成拒绝服务向量），但**owner 不响应时录音在下次 TTL 自动消失**。
4. 审计日志格式固定、可导出、可被第三方脚本解析——**这是 laos 最便宜的"第三方可审计性"**。

**验收标准**：审计文件在 `LAOS_REC=0` 时不可读；提供 `laos-rec-audit-export` 工具输出标准 JSON；被录者查询端点在不泄漏他人内容的前提下返回 yes/no + 时长。

---

#### P4 — 用**开源 + 协议层约束**锁定"本地优先"，防止 Rewind 式反转

**为什么**：Rewind 从"数据永不出设备"到云端转写到被 Meta 收购，用了约 3 年 ✅；Bee 被 Amazon 收购后未承诺延续政策 🔶；Pew 2026：**59% 美国人对企业无信心** ✅ → **公司政策是不可信的承诺载体**。

**具体做法**：
1. 把"ASR 全本地不上传"写进 **CONTRIBUTING / 治理文档**中的**不可协商约束**（类似 Debian Social Contract / 内核的 no-BLOB 立场），任何改动需要明确的治理流程。
2. 在**构建层面**强制：任何引入网络外发音频路径的 patch，CI 必须失败（可用 egress 检测 / 代码路径静态检查）。
3. **架构级排除生物识别**：**不要实现**声纹识别、人脸识别、说话人身份聚类能力，哪怕默认关闭——NameTag 的教训是"能远程启用的能力"等同于"已经启用的能力" ✅。
   - 注意与 P0 的张力：P0 需要判断"是不是 owner 在说话"。**解法：用加速度计/骨传导等物理 self-VAD，而非声纹识别**——既实现"只录自己"，又不具备识别他人身份的能力，从根上避免生物识别能力存在。
4. 发布**独立的隐私架构白皮书 + 自检清单**，让第三方可复现验证。这是业界完全空白的一项（**没有任何主流常开录音产品发布过独立第三方隐私审计**）——**对开源项目来说这是成本最低、差异化最大的一条**。

**验收标准**：CI 中存在一条显式检查"录音数据路径上任意外发网络调用 → fail"；README 与治理文档中有不可协商条款。

---

### 一句话总结

> laos 现在的隐私四件套，**把"使用者 vs 厂商"的信任问题解决了 80%，把"使用者 vs 旁观者"的信任问题解决了 0%**。而 CHI '26（N=525）、MeMic（N=168）、汉堡 DPA（2026-09）三方证据共同指向：**后者才是全天候录音真正的瓶颈**。
>
> **最该补的一条：P0 —— self-VAD / 只录自己。** 它是唯一有因果实验证明能提升社会接受度的机制，业界无人做，laos 有内核层优势可以做到别人做不到的保证等级。

---

## 附：本文 `未证实` 清单（诚实声明）

以下条目在本次检索中**未找到可核验的一手证据**，文中已避免使用具体数字或已标注 🔶：

1. MeMic 在线研究 N=168 的**具体效应量**（只确认"显著降低"，未拿到均值/置信区间）—— ✅ 确认显著性，数字 `未证实`
2. Tangible Privacy (CSCW '20) 的**确切访谈人数**—— `未证实`（ACM 摘要未披露）
3. HICSS-54 职场会议研究的**样本量**—— `未证实`（定性研究）
4. Lifelogging N=36 研究的**完整发表 venue 与年份**—— 🔶（仅经 Scilit 索引页转述）
5. IMWUT '21 "Is Someone Listening" 的**原文全文**—— 🔶（ACM 付费墙，经二手源转述三分类框架）
6. Meta v26 固件的**官方技术细节文档**（PDF 为政策说明，非技术规范）—— 🔶
7. 汉堡 DPA 认定的**正式决定文书编号**—— `未证实`（仅经 MLex 报道）
8. EDPB 智能眼镜报告—— `未证实`（报道称 2026 夏末发布，截至检索日未见正式发布）
9. Friend 2.0 的**销量/退款数据**—— `未证实`
10. Omi 脑机接口模块的**具体时间表**—— 🔶（仅媒体转述"2026–2027"）
