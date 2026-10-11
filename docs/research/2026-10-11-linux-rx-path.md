# Linux 收包的一生（六图）学习 —— RX 全链路转写与 laos 治理对照

> 学习日期：2026-10-11。来源：小红书《Linux收包的一生：6张图看懂 网卡收到包，程序就能立刻读到吗》
> <https://xhslink.cn/o/1V0e2tn9AsU>（图卡 6 张，逐图视觉转写 ✅ 6/6）。
> 来源链：博主**重述/图示重绘**自 kernel-internals.org（每张图脚注标明）——该站本仓
> 2026-10-06 已登记（four-wechat-articles §三，资源档 D 条），本篇是其网络 RX 章节的
> 图解化，机制事实为双跳转述；图面内容按 ● 记录，机制正确性与主流内核文档一致
> （NAPI/GRO/softirq 为标准内容，未逐行核源码）。
> 取件通道：移动 UA curl（imageList 六图直下，var/xhs_rx/ 留档）。
> 消费：本文自足；对照 laos 五道闸/信箱/审计/调度器资产。
> 产出：六图转写 + 九处同构对照（§2）+ 两条叙事印证裁决（§3）。纯学习波零代码。

---

## §1 六图逐图转写（内容忠实）

**图1 全链路总览**——《一个数据包如何到达你的程序？》：自底向上五层——
NIC（DMA 写 RX buffer，回写描述符）→ Network Driver（驱动 poll() 批量收包、构造 skb）→
Network Device Core（NAPI 调度 / GRO / 协议分发）→ 协议栈与 Socket（以太网 → IPv4 →
TCP → 接收队列）→ 应用程序（recv() / read() 读取数据）。
阅读范围：常见以太网 + IPv4 + 已建立 TCP 连接。

**图2 硬件与内存**——《先到内存，再通知 CPU》：① 驱动提前预分配 RX buffer，把 DMA
地址填入描述符；② 网卡收到以太网帧，按 RX 描述符找到可写的内存位置；③ DMA 写入数据 +
回写描述符（长度、完成状态）；④ IRQ 通知接收处理——**通常配合中断合并，不要求每个包
触发一次 IRQ**。记住这组分工：**描述符记录"在哪、是否完成"；RX buffer 承载实际数据**。

**图3 接收调度**——《IRQ 负责通知，NAPI 批量收包》（典型软中断模式；busy-poll/线程化
NAPI 不展开）：硬中断只做"安排 NAPI"（暂时抑制该队列后续 RX 中断）→ NET_RX_SOFTIRQ
（net_rx_action() 调度驱动的 poll()）→ 驱动 poll(budget) 批量取包 → 构造 skb → 递交
GRO → 判断"本轮是否已处理完"（结合实际工作量与 budget）：还有工作/用满预算 → 后续继续
轮询；完成 → napi_complete_done() 恢复 RX 中断。

**图4 协议分发**——《从以太网进入 IPv4》：napi_gro_receive()（GRO 聚合/递交接收核心）
→ 以太网协议分发 \_\_netif_receive_skb_core()（旁路：AF_PACKET——tcpdump 观察副本，
可选抓包旁路）→ ip_rcv() / PREROUTING（检查 IPv4 首部，经过已注册 hook）→ 路由决定去向
（本机地址 or 转发 ip_forward()）→ ip_local_deliver() / INPUT（按 IP protocol 交给
TCP/UDP 等）。函数为代表节点：GRO 后也可能走批量接收入口。

**图5 交付到程序**——《到 Socket，还没到应用》：tcp_v4_rcv()（检查 TCP 首部，查找匹配
Socket）→ TCP 状态机/已建立连接（处理序号、ACK、乱序，准备可读取的有序数据）→ Socket
接收队列（已可读取的数据等待应用消费）→ tcp_recvmsg()（普通 recv() 通常把数据复制到用户
缓冲区）。**金句：可读通知与应用读取是两件事**——sk->sk_data_ready(sk) 通知可读、唤醒
等待者，**应用被调度后才能继续执行 recv()/read()；唤醒不等于马上得到 CPU**。

**图6 定位思路**——《收包慢，按层找证据》：先确定数据卡在哪一层，再选工具——
网卡/驱动 `ethtool -S eth0`（RX 错误/丢包/队列统计）→ 接收调度 `/proc/net/softnet_stat`
（drop / time_squeeze 增量，结合 CPU 与软中断）→ IP/TCP `nstat -az`（Ip*/Tcp*/TcpExt*
协议计数器）→ Socket `ss -tin`（ESTABLISHED 的 Recv-Q：通常是**应用未读字节数**）→
应用层（时间戳/tracing：在等数据，还是醒了却没及时得到 CPU？）。
金句：**计数器要看增量与上下文；tcpdump 抓到了，不代表程序已经读到了。**

## §2 与 laos 的九处同构对照

| # | RX 路径事实 | laos 对应 | 性质 |
|---|---|---|---|
| 1 | 程序读到数据要过五层（NIC→驱动→core→协议栈→socket），**没有一层在应用里** | laos 定位叙事的教科书实例：能力进内核过五道闸（caps→task_scope→sentinel→不可逆→dispatch），治理语义在内核不在应用 | ● 叙事印证 |
| 2 | 描述符（在哪/是否完成）与 RX buffer（数据本体）分工 | audit.jsonl（记录发生了什么）与 memory.jsonl（内容本体）的分工——审计永不承载内容本体 | ● 同构 |
| 3 | IRQ 中断合并不每包一次 + NAPI poll(budget) 批量处理 | syscall 预算（EDQUOT）+ 风险记账 attempt-based pricing——预算制批量是内核通例，laos 闸门链与之同律 | ● 同构 |
| 4 | softnet_stat 的 drop / time_squeeze 增量计数 | Patient Bytes 可靠性记账（调度器预算、信箱积压 msg.list）——**积压/挤压必须可计数可观测** | ● 同构 |
| 5 | AF_PACKET tcpdump 观察副本，不改主路径 | laosweb 审计 tab / traceviz 读 audit 流——观察者永远不入派发路径 | ● 同构 |
| 6 | 路由决定"本机交付 or 转发"两条路径 | dispatch 的同步路径 vs task 路径（MCP Tasks） | ◐ 对照 |
| 7 | **"可读通知与应用读取是两件事"——唤醒 ≠ 得到 CPU** | laos 已立两个解耦（打断≠取消、完成≠交付，qwen-audio-agent 波）；本篇补第三条同族：**就绪 ≠ 调度**——后台任务语音化第一缺口的底层原理 | ● 三解耦族补员 |
| 8 | Recv-Q = 应用未读字节数（ss -tin 可查） | 信箱积压（msg.list "积压情况"）——消费滞后必须量化可见 | ◐ 对照 |
| 9 | 图6"按层找证据"+"计数器看增量与上下文" | laos 排障序（audit→telemetry→tracing）+ 测试口径哲学（实跑数不看宣称值） | ◐ 方法论同源 |

## §3 裁决

- **D1 ● 叙事印证（对照 #1–#5）**：RX 全链路是"治理在内核"最经典的教科书案例——
  分层、预算制批量、观察旁路、积压可计数，五处与 laos 闸门链逐一同构。进 PPT/README
  素材库（"内核怎么收一个包，laos 就怎么收一个 syscall"）。
- **D2 ● 三解耦族补员（对照 #7）**："就绪 ≠ 调度"与"打断 ≠ 取消""完成 ≠ 交付"并列为
  runtime 三个法定解耦；后台任务语音化（排队项）设计时直接引用。
- **D3 ◐ 无代码动作**：本篇为图解重述（kernel-internals.org 内容的再组织），机制无新
  事实需落码；价值在六图的组织方式与 §2 对照表。
- **D4 ○ 来源链声明**：双跳转述（XHS 重述 kernel-internals.org，本仓 10-06 已登记该站
  资源档）；机制事实如需一手引用以 kernel 文档/源码为准。

## §4 自检

1. 六图逐图转写完整（6/6，无标题级浏览）；
2. 来源链与既有资产衔接（kernel-internals.org 资源档 D 条）已声明，双跳转述不冒充一手；
3. 九处对照逐条给性质标签，● 印证不做代码动作；
4. 纯学习波零代码，主库测试数不受影响（1146 绿维持）。
