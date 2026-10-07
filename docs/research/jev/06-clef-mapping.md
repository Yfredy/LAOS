# jev/06：Clef 落地对照——三路线选型表与非自回归定论

> 承 00-taxonomy-and-metrics.md 口径（验证状态标注纪律沿用：凡本地未实测的数字
> 一律标引用出处，不许把引用值写进实测列）。上游调研：
> docs/research/2026-10-07-cloudflare-clef.md（Clef 全事实与笔记声称核实）、
> 波次账本 .superpowers/sdd/2026-10-07-clef-decision-layer/progress.md。
> 本篇回答一个问题：**laos 判断层到底用哪条路线，各路线数字各自什么口径。**

## 1. 三路线选型表

| 路线 | 延迟（中位） | 口径 | 体积/依赖 | 三判型覆盖 | 概率输出 | 状态 |
|---|---|---|---|---|---|---|
| rules（laos/decide.py RuleBackend） | ~0ms（纯 Python 规则求值） | 本地实测（构造即测） | 零依赖纯 stdlib | noul/choice/score 全 | 规则强度归一化（无校准） | ● v0.22.0 已落地 |
| edgejev（drv 转接的边缘决策模型） | 157.5ms | 本地实测（2026-09-21 执行前人工核实口径，见 04-ondevice-benchmark.md） | 驱动子进程 | 全 | 有 | ● 既有资产 |
| clef-flash（Cloudflare，Qwen3.5-9B+LoRA） | **38.8ms** / p95 122.4 | **引用**：Cloudflare 边缘 GPU 实测（2026-10-01 Birthday Week 发布口径） | 18.1GB 权重；transformers≥5.10.2+torch≥2.14（Qwen3_5）；官方加载路径 joint_schema_model | noul/choice/score（与 laos 三判型同源） | softmax 全分布+Brier/RLCD 校准训练 | ◐ v0.22.0 驱动就绪，本地实测见 §2 |

选型结论（函数级）：
- **默认路线 rules**：0ms、零依赖、审计友好——判断层的下限保障，永远在。
- **edgejev/clef 为升级路线**：需要校准概率或规则覆盖不了时经 `register_backend`
  插拔（drivers/drv_clef.py import 即登记 "clef"）。38.8ms 是**边缘 GPU 引用值**，
  laos 不复现该口径的硬件前不进默认链。
- 触发面：request_gate 语义（claw_core 同构钩子）→ laos/decide 的后端即挂点。

## 2. clef-flash 本地实测（wsl-x86_64 / qemu chroot 双宿主口径）

权重：HF Cloudflare/clef-flash（Apache 2.0），16 文件 18.1GB，var/clef_eval/（gitignored）。
架构门证据链：var/clef_eval/arch_gate_evidence.txt（transformers 4.46.3 无
Qwen3_5 → 升级 5.10.2+torch 2.14.1 过 import 门，错误原文未删改）。

| 宿主 | 加载 | 单发决策 | 协议 | 证据 |
|---|---|---|---|---|
| qemu chroot aarch64（虚拟端侧） | **19.4s**（760 张量全过） | 未取得：单发尝试在宿主内存压力下 c10 崩溃；GFLOPS 外推 ≈85min/次（0.70 GFLOPS 实测） | 加载实测即止（诚实降档） | forward_chroot.txt / arch_gate_evidence [4] |
| **wsl-x86_64 原生**（CPU bf16 16 线程；RTX4060 8GB 装不下 19GB bf16；torch 2.14.1 / transformers 5.10.2） | **6.4s**（noul 次；choice/score 次仅 2.9/3.1s——page cache 预热） | **noul 中位 33.8s**（p95 35.2，min 33.5/max 39.7，answer=yes 0.976）；**choice 中位 32.8s**（p95 33.6，answer=deploy 0.947）；**score 中位 62.9s**（p95 63.7，answer=yes，score=0.765） | **3 判型 × 20 次全量**（第三轮架构：逐判型独立进程；前两轮全协议死于 18GB 模型顶穿 WSL VM，第二次连带 vhdx 锁死，wsl --shutdown 修复） | var/clef_eval/results.json + raw_{noul,choice,score}_r20.jsonl |

**实测附注**：① 三型 20 次分布完全一致（CPU 决定性推理），无采样抖动，中位≈单值；② score（11 档）延迟≈noul/choice（2–3 档）的 1.9 倍——**实测印证 §3「延迟随选项数近似线性于 logits 维度」**；③ 对照引用值：Cloudflare 38.8ms@edgeGPU vs 本机 CPU bf16 33.8s ≈ **870×**，差距全部来自算力口径（边缘 GPU vs CPU），引用与实测两列分置永不混写。

## 3. 非自回归架构定论（为什么 clef 快得动）

- 决策延迟 = **一次 prefill** 的延迟，不是首 token 延迟：输出空间由 schema 的
  options 在推理前锁定，每个 option 一个 logit，softmax 并行打分——**没有自回归
  解码循环**。这与 Jev 的「输出空间在推理前就被定义」是同一件事（00 §1）。
- 推论：延迟随选项数近似线性于 logits 维度而非序列长度；context 越短越接近
  纯 prefill 下限。38.8ms 口径是短 prompt 边缘 GPU；本地 CPU bf16 的数量级
  差距主要来自算力差（见 §2 实测列），不是架构劣势。
- laos 侧对应：DecisionSchema(type, options, threshold) 的 options 即输出空间
  声明——laos/decide.py 与 Clef 同 schema 形状不是巧合，是同一架构判据。

## 4. 校准节：Brier/RLCD 方法库（laos/calib.py）

- Clef 训练 = SFT→LoRA→**Brier loss 直接优化概率**→RLCD（RL for Calibrated
  Decisions）——把「答案对」和「概率准」分开训练。
- laos 落地的是度量半边：brier_score / ece / reliability（纯 stdlib，v0.22.0），
  供任意后端的概率输出做校准审计；坑值回归：bins=100 的 0.29/0.57/0.58
  （BIN_EPSILON 咬合，test_calib.py 钉死）。
- 校准改进半边（温度缩放/RLCD 微调）不做进核心：重依赖+需要训练数据，属
  驱动子进程域，○ 本波次不做。

## 5. 登记与去向

- 代码：laos/decide.py（22 测试）、laos/calib.py（29 测试）、drivers/drv_clef.py
  （23 测试，chroot 适配+wsl argv 空格契约钉死）。
- 本篇结论进 v0.22.0 CHANGELOG；对外 README 的判断层叙述随下一轮 README
  改版引用本表（当前 README 无判断层小节，不硬塞）。
