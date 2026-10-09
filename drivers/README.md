# drivers/ —— 重依赖驱动子进程（laos 核心零依赖的代价转移层）

> laos/ 核心纯 stdlib；一切重依赖（云 API/本地模型/venv 生态）只活在本目录
> 的子进程里，经 import 即登记的装配面接进核心（`register_executor`/
> `register_backend` 哲学，drv_clef/drv_evolve 先例）。核心不 import 本目录
> 任何模块；不 import 对应驱动时 syscall 面 fail-loud（ENODEV）。

## 模块地图（加新驱动先在此登记一行）

| 驱动 | 装配点 | 形态 |
|---|---|---|
| drv_clef.py | laos/decide.py 判断层 | Cloudflare Clef 决策模型 HTTP（远端） |
| drv_evolve.py + openevolve_job.py | laos/evolve.py `register_executor` | OpenEvolve venv 子进程（CLI 稳定面） |
| drv_ear/rec/mic/npu/screen/... | kernel 各 drv_* syscall | 端侧能力子进程（adb/QNN/SAPI 等） |
| drv_audio/genie/apps/... | 同上 | 其余端侧/服务驱动 |

## 奖励治理面（2026-10-09 起，AuraSE-IPO 采纳）

涉及"候选打分/排序"的驱动（evolve 类优先）用 `laos.evolve.RewardSpec` +
`aggregate()` 组装多目标奖励，把 `spec.version` 透传进
`EvolveResult.reward_version`（`reward_detail` 放指标值与权重构成）——
审计行即记录奖励构成版本，权重变更=新版本号，历史可追溯不可变。

约定：质量/保真两类指标并存的 spec，**保真份额 ≥60% 起步**
（AuraSE OVRL:WER:SIM:SBS=4:2:2:2 的防单指标 hacking 实证配比）。

## 生成式音频组件三维幻觉审计（约定，触发即生效）

未来任何生成式音频驱动（SE/修复/超分/语音合成类）上线时，其评测与审计
**必须按三维拆分记录幻觉**，不发明第四维（AuraSE 调研 §4.1#1 采纳）：

| 维度 | 失效模式 | 度量形态 |
|---|---|---|
| 词法（WER 类） | 换词/插音/丢字 | 对参照转写（**不得对条件转写**——抄条件不得分） |
| 语义（SBS 类） | 语义漂移 | 对参照语义编码 |
| 说话人（SIM 类） | 音色漂移 | 对参照说话人嵌入 |

红线继承：生成式产出只进评测副本，**不得进记忆副本**（auto-gain/07 与
AuraSE 调研 §4.3——幻觉可压不可灭，最优系统 WER 仍 8.22%）。
