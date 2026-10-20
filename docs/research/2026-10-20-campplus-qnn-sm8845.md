# CAM++ W8A16 在 SM8845 HTP V81 上的超时排障与实测

- **日期：** 2026-10-20
- **终态：** `blocked`
- **设备：** nubia P0310，SM8845（`socModel=87`）/ HTP V81（`dspArch=81`），Android API 36；adb 在线设备：无（device_unavailable）
- **口径：** 报告只写实测与不可得两类事实。任何 `timeout`/`ssr` 都是 FastRPC 10 秒看门狗事件（CDSP SSR 是其下游后果），不是推理延迟；没有 pass 证据的指标一律标 `不可得`。

## 1. 实测与不可得分列

**实测：**
- 真机运行 `20261020-220201-smoke` 为 pass：退出码 0，16 个输出元素（不是 192 维有限 embedding，不作为速度值；该行不渲染 graph 时间）。
- 真机运行 `20261020-220308-smoke` 为 pass：退出码 0，16 个输出元素（不是 192 维有限 embedding，不作为速度值；该行不渲染 graph 时间）。
- 版本/配置矩阵：8 行离线构建产物；7 行有元数据，其中 7 行带 build ID；1 行没有元数据；8 行记录了 context SHA-256（见第 3、6 节）。

**不可得：**
- CAM++ W8A16 完整 192 维 embedding：`blocked`（时间线状态分布：execute_error=2，load_error=1，pass=2，ssr=2）。
- 节点区间隔离：`awaiting_device`，interval=null，awaiting_interval=[0,3101]。
- 双 context 分区根因：`unproven`（status=`device_unavailable`）。
- EER、Top-1、固定 k ARI、在线 ARI、阈值重标定与产品准入：全部不可得。
- 冷/暖延迟 p50/p95/p99、端到端、吞吐与 30 分钟 soak：全部不可得。

## 2. 事件时间线

| run_id | 状态 | 退出码 | 输出元素 | 有限 | 说明 |
|---|---|---:|---:|---|---|
| 20261020-220113-smoke | execute_error | 126 | 0 | False | execute_error（执行失败，不是速度值） |
| 20261020-220125-smoke | load_error | 11 | 0 | False | load_error（context 未加载，不是速度值） |
| 20261020-220145-smoke | execute_error | 127 | 0 | False | execute_error（执行失败，不是速度值） |
| 20261020-220201-smoke | pass | 0 | 16 | True | pass（通过；本次没有持久化 graph 时间，且不是 192 维有限 embedding，不计入速度值） |
| 20261020-220223-campplus-w8a16-v2 | ssr | 17 | 0 | False | CDSP SSR（CDSP 崩溃，没有 embedding） |
| 20261020-220308-smoke | pass | 0 | 16 | True | pass（通过；本次没有持久化 graph 时间，且不是 192 维有限 embedding，不计入速度值） |
| 20261020-220315-campplus-w8a16-v2 | ssr | 17 | 0 | False | CDSP SSR（CDSP 崩溃，没有 embedding） |

**实测：** 上表逐条抄自 `device-runs/*/result.json`；`timeout` 与 `ssr` 状态来自 logcat 的 FastRPC 看门狗与 CDSP SSR 证据，不参与任何延迟统计。

**不可得：** 没有任何一行同时满足 pass、192 个有限输出，因此速度与准确率都没有合法输入。

## 3. 版本与配置矩阵

- 完整图行数：5；完整图变体数：4；状态分布：config_warning=7，metadata_rejected=1。
- QAIRT 树：`v2.47.0.260601114230`（var/speaker-benchmark/qnn/sdk/qairt/2.47.0.260601）；`v2.51.1.261002102551`（var/speaker-benchmark/qnn/sdk-2.51/qairt/2.51.1.261002）；`v2.51.40.260930230134`（var/speaker-benchmark/qnn/sdk-2.51.40/qairt/2.51.40.260930）

**实测：** 7 行 `config_warning` 有 `unexpected GraphHtpSettings option 66` 告警，未上机。

**不可得：** 没有任何一行是 `pass`，完整图没有进入真机测速。

| 变体 | 类型 | 阶段 | 状态 | build ID | 元数据 | 备注 |
|---|---|---|---|---|---|---|
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | smoke | eligibility | metadata_rejected | 无 | 无（未通过元数据门禁） | metadata rejected: SM8845/V81 元数据不匹配：socModel=0, dspArch=81；要求 socModel=87, dspArch=81 |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | full | compiler | config_warning | v2.51.1.261002102551 | socModel=87 / dspArch=81 / in=[1,80,298] / out=[1,192] | context 配置告警未闭环，未上机：83.1ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | full | compiler | config_warning | v2.51.1.261002102551 | socModel=87 / dspArch=81 / in=[1,80,298] / out=[1,192] | context 配置告警未闭环，未上机：92.5ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | full | toolchain | config_warning | v2.51.1.261002102551 | socModel=87 / dspArch=81 / in=[1,80,298] / out=[1,192] | context 配置告警未闭环，未上机：92.9ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66；equivalent_to=2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | smoke | eligibility | config_warning | v2.51.1.261002102551 | socModel=87 / dspArch=81 / in=[1,16] / out=[1,16] | 46.8ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | full | compiler | config_warning | v2.51.1.261002102551 | socModel=87 / dspArch=81 / in=[1,80,298] / out=[1,192] | context 配置告警未闭环，未上机：423.8ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | full | toolchain | config_warning | v2.51.40.260930230134 | socModel=87 / dspArch=81 / in=[1,80,298] / out=[1,192] | context 配置告警未闭环，未上机：75.6ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | smoke | eligibility | config_warning | v2.51.40.260930230134 | socModel=87 / dspArch=81 / in=[1,16] / out=[1,16] | 47.3ms [ ERROR ]  <E> unexpected GraphHtpSettings option 66 |

## 4. 隔离区间

**实测：** 7 个 probe 中 6 个记录 context SHA-256、7 个记录 graph SHA-256；切点与张量形状来自真实图结构；其中 1 个 probe 缺少 context SHA-256。

**不可得：** 设备离线，prefix/suffix 没有真机执行结果，因此没有二分进展（`awaiting_device`）。

| probe | 类型 | 节点区间 | 语义输出 | context SHA-256 | graph SHA-256 | 真机 |
|---|---|---|---|---|---|---|
| prefix-0049-head_Reshape_output_0 | prefix | [0,49] | [1,320,298] | `fd7e02711d9f8b0e133a8ef0de20d3e7fcbfa45045a89208f69b9a454e4c2a9d` | `c4987ad6f61cec0f2413add0472a09cc65182a9102bb3b7381a48776b9468563` | 无（device_unavailable） |
| prefix-0747-xvector_block1_Concat_11_output_ | prefix | [0,747] | [1,512,149] | `fbc91be0bbb689d65bf41eb355b6d764295196c85ac124d081b24db3b136b89d` | `53187df22e094e21bdf378eed5bb0244ab80ea829606577d6f898667d07e9ae6` | 无（device_unavailable） |
| prefix-2142-xvector_block2_Concat_23_output_ | prefix | [0,2142] | [1,1024,149] | `cbe29bd1db8eef5c9cfe00363ab7b40a6a1ce32eacfdc401518700cebdcecaf0` | `5ae8858086f32eac805b4068da119dbd31efb486636edeaf3229be8d7d1bbd3e` | 无（device_unavailable） |
| prefix-3076-xvector_transit3_linear_Conv_out | prefix | [0,3076] | [1,512,149] | 无 | `40047c80b6af1b45ed267714a3827e51552a81d9ec062a0600ceb9397735ddc4` | 无（device_unavailable） |
| prefix-3077-xvector_out_nonlinear_relu_Relu_ | prefix | [0,3077] | [1,512,149] | `5487594176e1e7a0aab6c3e49c4a754d3266c41049585d1dcd8283ec49899c70` | `a8e5303657501adaeb4e376f50718053dd253d879dbbb049b9be132575c12e3b` | 无（device_unavailable） |
| prefix-3093-xvector_stats_Concat_output_0 | prefix | [0,3093] | [1,1024] | `94f7704d5448c1a9a61d43c7f77571d308307b819d2a6d47387c7694e206cff8` | `e6072dd32aa1d7c73e565999263b1e6acda8b3e206bd37d8eebfb5f9ee354ead` | 无（device_unavailable） |
| prefix-3101-embedding | prefix | [0,3101] | [1,192] | `0827fc69d5c79a2e750384754db3112b277c4b17d0c30c38b6c88b47d7b41b8e` | `afcd56fa8f6238a7de9ebe9290f41b4dde938863a7b319ca030b0a1a08f5186e` | 无（device_unavailable） |

## 5. 选定修复 / 分区

- 语义改写：`blocked_on_isolated_interval`（isolation 状态为 awaiting_device，没有已验证的节点区间；改写必须由真机隔离区间驱动，禁止凭猜测构造）。
- 双 context 分区：`device_unavailable`；选择依据 `smallest_intermediate_only`；根因判定 `unproven`。
- 切点：节点 3093 `/xvector/stats/Concat_output_0` [1,1024]。
- 中间张量搬运：4096 字节；端到端必须计入两次 context 调度、CPU FBank 与搬运，不只相加 两个 graph time。
- 升级为根因候选：eligible=False（isolation 尚未验证，分区只按最小中间张量选择，不能声称解决根因）。
- 待办：设备恢复后先跑 prefix context，把原生输出按 layout.transpose_axes 搬到 suffix context 的原生输入，再跑 suffix context
- 待办：同一真实输入连续 30 次完整 embedding：退出码 0、无 SSR、无 FastRPC timeout、每次 192 个有限值，总 warm graph time < 1 s
- 待办：报告中间张量搬运成本 4096 字节与两次 context 调度开销

**实测：** 分区两侧 context 均为 prefix=`config_warning`、suffix=`config_warning` 离线产物；离线 round-trip 覆盖 40 条真实张量（mode=`exact`，`max_abs=0.0`）；布局转置 [0,1] 已验证（3 个样本，`round_trip_max_abs=0.0`）。

**不可得：** 故障区间没有真机证据，分区只是按最小中间张量选择，`solves_root_cause=unproven`，终态 `blocked`。

## 6. Artifact 哈希

| 变体 | 文件 | SHA-256 |
|---|---|---|
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | bin | `6d796b0f51e97d35cb33a8f320bfad9132fbc8e849fe666df715f28f50925959` |
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | calibration_list | `126638bcb7801f3f7e2f6f6517957ca36760828539938e08a8a3ae2e5ed64a45` |
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | context | `2fb453745e55084852e42a5178eed2fdccca63eb6fcd16b541eeb812442e62ab` |
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | cpp | `004573aec570fbd7c1e6f8514399386744add9be7483b8d315d0ee6def0a9ebc` |
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | model | `ad99dba5ad60ed75190902fabaab11bb132076376d32683743f9bf62b1bf7b66` |
| 2.47.0-opt2-vtcm4-dlbc0-smoke_w8a16 | model_lib | `aa8eb248b6f53247d3b3ef3fdd99bfb40dea655c19e140d10d63c74d975528e4` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | bin | `827b81805a0453cc3dbadaf9faae5c275eb2f448325d84999db41498c2b1f297` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | calibration_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | context | `ed275a0ac4a55d80315883b6f1e537ccd6c08bc6c5e7df40ef3b1135b5167a6f` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | cpp | `b76fd6168519c2b20cf2f7156e4fe9407990492b9754983e6d47bd8b1f7059a0` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | model | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| 2.51.1-opt0-vtcm4-dlbc0-campplus_w8a16_static_stats | model_lib | `8b16fe98d9d391da1e2823f60ffc851eeb8d0ebfaeba650aeab17b587ad0cd4b` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | bin | `827b81805a0453cc3dbadaf9faae5c275eb2f448325d84999db41498c2b1f297` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | calibration_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | context | `ad6554bd3cab815154368373bc03869f00b4fd8ce769a396f42ba9049ac2a4fd` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | cpp | `b76fd6168519c2b20cf2f7156e4fe9407990492b9754983e6d47bd8b1f7059a0` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | model | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| 2.51.1-opt1-vtcm4-dlbc0-campplus_w8a16_static_stats | model_lib | `986fb2b3b1d18907dbc60b11eb9d370789db8bea7763491b696a1a898d9fc49d` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | bin | `827b81805a0453cc3dbadaf9faae5c275eb2f448325d84999db41498c2b1f297` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | calibration_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | context | `ed275a0ac4a55d80315883b6f1e537ccd6c08bc6c5e7df40ef3b1135b5167a6f` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | cpp | `b76fd6168519c2b20cf2f7156e4fe9407990492b9754983e6d47bd8b1f7059a0` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | model | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| 2.51.1-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | model_lib | `4028d6f7579d4e93c04e72b7fd3b31b3f9000cde5a6449d04ce53fbbe411902a` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | bin | `6d796b0f51e97d35cb33a8f320bfad9132fbc8e849fe666df715f28f50925959` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | calibration_list | `126638bcb7801f3f7e2f6f6517957ca36760828539938e08a8a3ae2e5ed64a45` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | context | `e578b51df2b3bd48ea34104ccebb9b9035a2dcf2ed928905bb8c720eefa9de9a` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | cpp | `8a7b8c110f1fa7c5ba6069f884bcff3526eb931d8185e077edaa02f8fea97e9b` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | model | `ad99dba5ad60ed75190902fabaab11bb132076376d32683743f9bf62b1bf7b66` |
| 2.51.1-opt2-vtcm4-dlbc0-smoke_w8a16 | model_lib | `3150a07e48e9190b0fc299ed0d2e8a9bd03d52eb58ddce733c7ebb6670ec86c0` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | bin | `827b81805a0453cc3dbadaf9faae5c275eb2f448325d84999db41498c2b1f297` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | calibration_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | context | `555533bdc772e68c79c69b67729ce1f6d3a24fd2263b2a446160c4afec21b19b` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | cpp | `b76fd6168519c2b20cf2f7156e4fe9407990492b9754983e6d47bd8b1f7059a0` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | model | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| 2.51.1-opt3-vtcm4-dlbc0-campplus_w8a16_static_stats | model_lib | `843fe037d0935f5a7696eeeccf76bd90b7073489e319dae87f11a22038fc8d41` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | bin | `827b81805a0453cc3dbadaf9faae5c275eb2f448325d84999db41498c2b1f297` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | calibration_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | context | `005179bd50c5aff78e22b31e16c1679900d3ce7d2eb6ff8e3d239c033a1cd6cc` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | cpp | `641c129676ca24b7caf9c108ba5610efe00cda04947e030f6b97249c5716c1d4` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | model | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| 2.51.40-opt2-vtcm4-dlbc0-campplus_w8a16_static_stats | model_lib | `c542c8e343061c3f9d73037fc87a4feb4b53bf2ceac44a090dc366d6ed5b476c` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | bin | `6d796b0f51e97d35cb33a8f320bfad9132fbc8e849fe666df715f28f50925959` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | calibration_list | `126638bcb7801f3f7e2f6f6517957ca36760828539938e08a8a3ae2e5ed64a45` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | context | `0a58ca1f3fa3813779c3540315cdcb7598cb89b9595d7f3464f68d2e19e588d8` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | cpp | `a0613cff5add49573549f6cf1d8cb4f5b76637ef00115878850fe1d8c496594c` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | model | `ad99dba5ad60ed75190902fabaab11bb132076376d32683743f9bf62b1bf7b66` |
| 2.51.40-opt2-vtcm4-dlbc0-smoke_w8a16 | model_lib | `94523c532e013cb2d3ec4578c1ac90d428e43f77d27b8b39b561180a274bf732` |
| model（FP32 源） | onnx | `9fc42a6616a50d8951811cd838b601449dd63dc8a51ab363707a11ee55cd96f3` |
| calibration（40 条真实语音） | input_list | `9d3c5217f154be10002a2ef2b30e92d9b94a67790985f3fc421b0b1a5419bdd0` |

**实测：** 上表哈希均由离线产物实算，可作为复现锚点。

**不可得：** 没有任何 artifact 通过真机 pass，因此不存在「实测速度对应的产物」这一层哈希。

## 7. Paired accuracy

- benchmark 状态：`device_unavailable`
- 原因：缺少 paired embedding 文件：var/speaker-benchmark/qnn/campplus-htp-debug/embeddings/fp32.npz；缺少 paired embedding 文件：var/speaker-benchmark/qnn/campplus-htp-debug/embeddings/w8a16.npz；缺少 embedding 抽取记录：var/speaker-benchmark/qnn/campplus-htp-debug/embeddings/extraction.json（extraction.json）
- 阈值重标定：`blocked`；产品准入：`blocked`

**实测：** 无；没有 FP32/W8A16 paired embedding，不计算任何准确率。

**不可得：** parity 指标不可得；EER、Top-1、固定 k ARI、在线 ARI、簇数量均不可得；阈值重标定与产品准入保持 `blocked`，禁止用 FP32 阈值冒充 W8A16 阈值。

- 待办：首次成功门禁：同一真实输入连续 30 次、退出码全为 0、无 SSR、无 FastRPC 超时、每次 192 个有限值
- 待办：用同一波形/FBank/裁剪顺序提取 paired FP32 与 W8A16 embedding
- 待办：在 20 人 6/3/2/1s 与 ESC-50 10/0dB 矩阵上计算 EER、Top-1、ARI 与簇数
- 待办：重标定 W8A16 阈值并重算在线聚类

## 8. 冷/暖延迟与吞吐

**实测：** 无；没有同时具备 pass 与 perf_profile 的延迟记录。

**不可得：** `device_unavailable`——20 次 fresh-process 冷加载、`burst` 与 `sustained_high_performance` 下的 100 次 warmup + 1,000 次 measured 均未执行，因此 cold p50/p95、graph p50/p95/p99、端到端 p50/p95 与吞吐都不可得。`>= 10 s` 只可能记为 FastRPC timeout，不是推理延迟；`>= 1 s` 判不可常驻。

## 9. 30 分钟 soak

**实测：** 无；没有同时具备 pass 与 perf_profile 的 soak 记录。

**不可得：** `device_unavailable`——30 分钟（1,800 秒）1 Hz `sustained_high_performance` soak 未执行，battery/SKIN 温区、成功/失败计数、中位与末尾 graph 时间都不可得。
