# 对话管线装配 + 接线波 —— 排队任务兑现记录

> 2026-10-08 · 排队波次执行（非笔记复现）：espclaw 报告 §五裁决 #2（事件规则表 ◐P2）兑现 + v0.21.0 埋点波三件债（phase="done"/env 覆盖/diary 跨代）清账 + P3 两项（phase 对齐/双分区播种）对照收档
> 验收：主库 **942 绿**（911→942，OK skipped=5）；落地件 `laos/evroute.py` + `laos/dialogflow.py` + diary 跨代 + `WakeConfig.from_env`

## 1. 落地件

| 件 | 内容 | 测试 |
|---|---|---|
| `laos/evroute.py` | **事件规则表**（esp-claw claw_event_router 转译，P2 兑现）：JSON 规则热载（load_file+reload）+ CRUD（重复 id/未支持动作 fail-loud 拒绝）；match{type/source/text/text_match(exact\|prefix)}；三动作 call_cap（回调注入，装配层接 caps.py）/drop（事件防火墙）/emit（派生事件回注+字段拷贝）；**consume_on_match**（首条消费）与 **fail_open**（per-action，默认 False=保守中止）语义保留；无规则命中=passthrough 放行；RouteResult 与 claw_event_router_result_t 同构（matched/matched_rules/action_count/failed_actions/first_rule_id + dropped/emitted） | 16 例 |
| `laos/dialogflow.py` | **对话管线装配**：入口防火墙（wake/asr/barge_in 先过 EventRouter，dropped 不进对话核）→ WakeGate → DialogQueue（latest-only）；**phase="done" 债兑现**（turn_done 补发同 turn_id 的 d.dialog.turn phase="done"，v0.21.0 明言"完成态归装配层"）；**JitMem 接入**（会话首 turn curate 一次、payload 会话级缓存、每轮 turn_done 即时成败 outcome 回填——v0.24.0 四步循环第④步在对话域闭合）；LAOS_DIALOG_OBS_MS/RESUME_MS env 覆盖 | 13 例 |
| `laos/wakegate.py` | `WakeConfig.from_env()`：LAOS_WAKE_ENABLED/WAKE_WORDS/SLEEP_WORDS/MAX_TURNS/SESSION_SEC/FOLLOWUP_SEC 覆盖面；坏值回退默认（env 是用户输入不 fail-loud），空 env=全默认 | 并入上项 |
| `bin/diary.py` | **diary 跨代聚合**（v0.21.0 已知缺口）：`_load_audit` 读活文件+同目录全部 audit-*.jsonl.gz 归档代，**按代序**（数字序非字典序，gen10>gen2）拼接——轮转后当天记录分居两处，只读活文件会漏归档段 | 2 例 |

## 2. esp-claw 构件 → laos 转译对照（P2 兑现细节）

| esp-claw claw_event_router | laos evroute | 取舍 |
|---|---|---|
| match 六字段（event_type/event_key/source_cap/channel/chat_id/content_type）+text/text_match | match{type/source/text/text_match} | laos 事件无信道语义，channel/chat_id/content_type 不承载，按需再扩 |
| 六动作 CALL_CAP/RUN_AGENT/RUN_SCRIPT/SEND_MESSAGE/EMIT_EVENT/DROP | call_cap/drop/emit | run_agent/run_script/send_message 属 kernel 信箱/驱动子进程域，不进零依赖核心；装配层可经 call_cap 回调自行动作化（kernel 域接线留后续） |
| rules_path JSON + reload() 热载 + CRUD（add/update/delete + JSON 变体） | load_file+reload + add/delete/list | update=delete+add（等价复合，不单列） |
| claw_event_router_result_t | RouteResult 同构 + dropped/emitted | dropped 让防火墙语义对调用方显式 |
| consume_on_match / per-action fail_open | 同名同语义 | fail_open 默认 False（保守）：esp-claw 头文件未标默认值，laos 显式化选保守侧并文档写明 |

装配联动：DialogPipeline 的入口三事件（wake.word/asr.final/user.barge_in + vad.speech_start）先过路由器——**DROP 规则成为对话面防火墙**（测试钉住：规则吞掉的 asr.final 永不进唤醒闸、永不触发 JIT curate；未命中事件照常放行）。这正是 espclaw 报告"对话管线装配波次的规则面：VAD/唤醒/打断的声明式路由"的落地形态。

## 3. 三件债与一项核对

1. **phase="done"**（v0.21.0）：✅ 兑现——dialogflow.turn_done 补发，与入队时 phase="queued" 同 turn_id 配对，消费侧可辨完整生命周期。
2. **env 覆盖**（接线波）：✅ 兑现——LAOS_WAKE_*（六变量）+ LAOS_DIALOG_OBS_MS/RESUME_MS；坏值回退不炸。
3. **diary 跨代聚合**（v0.21.0 已知缺口）：✅ 兑现——_load_audit 归档+活文件拼接，代序数字序。
4. **64MB 水位**（接线波）：✅ **核对已实装，无需代码**——telemetry.py `max_bytes=64*1024*1024` 构造默认 + `_write_line` 写前查水位先归档（v0.21.0 波内已做，当时排队的只是"保留策略"说明；现保留=归档不删，行为与设计一致）。

## 4. P3 两项对照收档（不新增代码）

| esp-claw | laos 既有同构物 | 结论 |
|---|---|---|
| claw_core 8 相位状态机（IDLE→…→FINALIZING，agent 循环相位） | d.wake.state_change 四态（sleeping/listening/processing/follow_up，会话生命周期）+ d.dialog.turn phase（queued/done，轮次相位） | **语义域不同不硬搬枚举**（埋点字典对照吸收）；同构做法已各有体现：状态迁移统一出口（wakegate._transition）+ reason 枚举（wake/turn/sleep_word/max_turns/session_timeout/followup_timeout/speech/barge_in/finish_turn） |
| 双 FATFS（只读 system 种子+可写 storage+运行时重格式化再播种） | AuditLog 轮转四件套（gzip 归档=不可变基线 + 活文件可写 + epoch/seq 跨代去重 + 本波 diary 跨代聚合）；diary 日记作为记忆再入库（自播种雏形） | laos 已有"不可变归档+可写活区+跨代消费"同构物；"运行时重建播种"对 laos 场景（个人记忆库不可重建）**方向不适用**，收档不做 |

## 5. 验收与登记

- 全量 **942 绿**（911→942；evroute 16 + dialogflow 13 + diary 2），OK skipped=5。
- 实现注记：装配层事件 sink 协议为两参 `(event, fields)`（dialogsched.safe_emit 房型协议）——本波测试首版误用单参 list.append 当 sink，TypeError 被 safe_emit 按设计吞掉（埋点永不影响主链路），暴露为"事件全空"而非崩溃；测试 sink 已按协议适配。此为协议使用坑，非代码 bug，特此记录。
- espclaw 报告 §五裁决表同步更新：#2 ◐P2→●兑现（本波）；#3/#4 ◐P3→对照收档。

## 6. 排队清底状态（2026-10-08 补）

- **sherpa-onnx KWS 实测：✅ 完成**（驱动子进程域 var/kws_eval/.venv，重依赖红线合规）。模型 sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01（int8，32.6MB，GitHub releases 断点续传三段拼齐）；sherpa-onnx 1.13.8；测试音=Windows SAPI 离线合成（唤醒词"小劳小劳"1.86s + 对照句"今天天气怎么样"2.45s，22.05k 线性重采样 16k）。**结果：唤醒词检出 1 次零误报；流式解码延迟中位 7.56ms / p95 8.47ms（100ms 块喂入，chunk 320ms 解码窗，Windows x86 CPU）**——远低于实时，wakegate.wake() 的 KWS 触发源在 Windows 宿主实测可用；关键词经现场 keywords 文件注入（拼音声调单元 `x iǎo l áo x iǎo l áo @小劳小劳`，1.13.8 无 stream.add_keyword API）。后续接 drv_ear 域成常驻驱动属接线范畴，另行排队。
- **豆包 TTS：BLOCKED 收档**——全仓代码/文档零引用、环境无 API key；解阻条件=用户提供 key（届时进驱动子进程域，对标 TtsRouter 在线后端位）。
