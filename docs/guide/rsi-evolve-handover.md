# RSI/OpenEvolve 驱动落地——波次交接文档

> 2026-10-09 · 波次：RSI 方向调研 → OpenEvolve 试跑 → laos 受治理进化驱动落地 → 终审合并 master（565dec8）
> 读者：下一位接手的通用 SWE（不预设你了解 RSI、laos 或本波历史）
> 体例：按本仓 `docs/guide/llm-handover-methodology.md` 的 L0–L4 五层架构编写；所有命令带实跑输出原文（捕获时点见各节）
> 配套：结构图 `docs/diagrams/rsi-evolve-architecture.html`（archify）与 `rsi-evolve-handover.drawio`（drawio 源）；交接 PPT `docs/ppt/laos-rsi-evolve-handover.html`

## L0 生存层：这是什么

**30 秒陈述**：laos 是"Linux 内核治理在用户态的延伸"，Agent 是新负载。本波把一个真实的自改进负载（OpenEvolve——AlphaEvolve 的开源实现，进化式代码优化 agent）接进了 laos：**进化循环在 venv 子进程里跑，治理（权限/预算/审计/人类确认席）常驻内核**——"评估器与权限在进化循环之外"（Lilian Weng 2026-07 综述七瓶颈之五）的工程化落地。

**是 X 不是 Y**：
- **是** laos 的第一个"会自改写负载"驱动：`evolve.run` 内建 syscall + 纯 stdlib 作业面 + venv 子进程驱动。
- **不是** RSI 算法实现——laos 不做进化/训练/rollout（那是负载的事），laos 是它的 cgroup/seccomp/audit。
- **不是**已完成品：LLM 后端 BLOCKED（§L4），e2e 真跑收档待解锁；后续三件见 `docs/superpowers/plans/2026-10-09-evolve-followups.md`。

**一句话技术栈**：laos 核心纯 stdlib（零依赖红线）；OpenEvolve 0.4.0 只活在 `var/rsi/openevolve/venv`（gitignored）；测试 unittest 全离线。

**顶层落点地图**（本波新增/改动）：

| 文件 | 职责 | 关键行锚 |
|---|---|---|
| `laos/evolve.py` | 作业面：路径闸（允许根/禁区）+ ENODEV 装配面 | EvolveGate:72 / register_executor:104 / run_job:109 |
| `laos/kernel.py` | `evolve.run` 内建 syscall：闸门链 + 阻塞派发 + 双行审计 | ToolSpec:381 / to_thread:691 / _impl_evolve_run:961 / event:"evolve":978 |
| `drivers/drv_evolve.py` | 驱动适配器：命令构造/子进程/单行 JSON 契约 | EvolveDriver:42 / build_command:62 / _openevolve_executor:121 / import 即登记:146 |
| `drivers/openevolve_job.py` | venv 内执行器：官方 CLI 子进程 + checkpoint 解析 | _find_best:32 / _best_score:45 / main:64 |
| `tests/test_evolve.py` + `tests/test_drv_evolve.py` | 离线测试（闸/syscall 链/驱动契约/并发让出） | — |
| `scripts/evolve_e2e.py` | （**待执行**，followups T3）e2e 解锁 runbook | 计划已写死代码 |

## L1 冷启动层：怎么跑起来

**解释器**：只用 `C:/Users/yaoyue/miniconda3/python.exe`（conda 红线：禁止 pip install 进它；OpenEvolve 在独立 venv，conda 本体未动）。

**venv 重建**（若 var/ 被清）：

```bash
mkdir -p var/rsi/openevolve
C:/Users/yaoyue/miniconda3/python.exe -m venv var/rsi/openevolve/venv
git clone --depth 1 https://github.com/algorithmicsuperintelligence/openevolve var/rsi/openevolve/src
var/rsi/openevolve/venv/Scripts/python.exe -m pip install var/rsi/openevolve/src
```

预期末行：`Successfully installed ... openevolve-0.4.0 ...`（实装记录见 `var/rsi/openevolve/OBSERVATIONS.md`）。

**测试**（不需要 venv、不需要网络、不需要 key——全部 mock）：

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q
```

预期输出（2026-10-09 18:5x 捕获于 aor-waves@4d8b48f；master 合并点 565dec8 为 1085）：

```
Ran 1111 tests in 107.773s

OK (skipped=5)
```

**驱动状态一行**（裸解释器秒答，不起子进程）：

```bash
C:/Users/yaoyue/miniconda3/python.exe drivers/drv_evolve.py
```

实跑输出原文：

```
backend=openevolve registered=True executor_registered=True roots=('var/rsi/jobs',) max_iterations=500 timeout_s=1800.0 venv=True src=True last_best_score=None
```

**顺序无关验证**（曾因执行器注册表污染翻车，终审 I2 修复后双向都要绿）：

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_evolve tests.test_drv_evolve
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_evolve tests.test_evolve
```

实跑（前者）：`Ran 39 tests in 0.134s` / `OK`。

**Windows 坑**：venv 解释器是 `Scripts/python.exe`；OpenEvolve CLI 的入口脚本在 Windows 下需要 `if __name__ == "__main__":` 守卫（其 README 明示，示例已带）。

## L2 日常操作层：怎么用这套东西

**装配**（零改动核心，import 即登记）：任何宿主（laosctl/脚本/测试）`import drivers.drv_evolve` 后，`laos.evolve.run_job` 即有执行器；不 import 则 ENODEV fail-loud（装配面哲学，decide/drv_clef 同款）。

**syscall 调用形**（完整可跑例子见 `tests/test_evolve.py` TestEvolveSyscall）：

```python
import drivers.drv_evolve                       # 装配
from laos.kernel import AgentKernel, CapabilitySet, PCB
k = AgentKernel(Path("var/kernel-x"), audit_mode="w", confirm=lambda op: False)
k.procs[1] = PCB(pid=1, name="evo", caps=CapabilitySet(["evolve.*"]), budget=None)
res = asyncio.run(k.syscall(1, "evolve.run", {
    "target": "var/rsi/jobs/<job>/initial_program.py",
    "evaluator": "var/rsi/jobs/<job>/evaluator.py",
    "iterations": 10}))
# res.ok → res.text 是 EvolveResult JSON（best_score/sha256/iterations_completed/...）
```

**env 契约**（全部调用时读取、全部可覆盖）：`LAOS_EVOLVE_PYTHON`（venv 解释器路径）/ `LAOS_EVOLVE_CMD`（模板整体替换，注意 `{job}` JSON 含空格会被按空白劈开——简单命令逃生门，复杂场景用包装脚本）/ `LAOS_EVOLVE_TIMEOUT`（默认 1800s）/ `LAOS_EVOLVE_SRC`（源码目录）/ `LAOS_EVOLVE_ROOTS`（只扩允许根，**永不放行禁区**）。

**加作业**：target/evaluator 必须放 `var/rsi/jobs/` 下（gate 红线）；workdir 不传则驱动自动分配 `var/rsi/jobs/job-<时间戳>-<rand>`（同样在允许根内）。

**常见报错对照**：

| 报错 | 原因 | 解法 |
|---|---|---|
| `ENODEV: evolve 驱动未装配` | 没 import drivers.drv_evolve | 宿主侧补 import |
| `ENOENT: venv 解释器不存在` | var/ 被清或未跑试跑 | 走 L1 venv 重建 |
| `EPERM: ... 不在允许根/触碰禁区` | target/evaluator/workdir 越界 | 移进 var/rsi/jobs/ 或设 LAOS_EVOLVE_ROOTS（禁区仍不可） |
| `ETIMEDOUT` | 进化跑超时 | 调 LAOS_EVOLVE_TIMEOUT |
| `EIO: openevolve-run rc=...` | CLI 失败（多为后端） | 看 stderr 尾 600 字符（错误原文带回）；后端问题见 L4 |

## L3 架构与决策层：为什么长这样

**三层分离**（结构图的两条大边界）：

1. **循环外·laos 核心**（纯 stdlib）：syscall 闸门链（caps→task_scope→validate→EDQUOT→sentinel→审计）+ `EvolveGate`（允许根/禁区/迭代上限）。治理代码不被进化的 agent 触碰——这就是"审判席在循环外"。
2. **装配面·drivers/**：`drv_evolve` 适配器，import 即登记；重依赖止步于此。
3. **循环内·venv 子进程**：`openevolve_job`（官方 CLI 稳定面，不依赖库内部 API）→ `openevolve-run.py` → LLM 后端 → checkpoints。

**关键决策记录**（被否掉的方案与理由——别当 bug"修"掉）：

| 决策 | 当时为什么 | 被否方案 |
|---|---|---|
| 官方 CLI 子进程而非库 API | 库签名不进公开契约，CLI 是文档化稳定面 | 直接 import openevolve（签名漂移风险） |
| `_BLOCKING_BUILTINS` 白名单走 `asyncio.to_thread` | evolve.run 是首个阻塞型内建（默认 30 分钟），不能卡死事件循环——MCP 驱动路径已有同款先例 | 全体内建一律 to_thread（msg./mem. 是内存操作，白付线程开销） |
| AuditLog 加 `threading.Lock` | worker 线程落 `event:"evolve"` 与循环线程并发写，"GIL 下足够原子"假设作废 | 无锁（seq==下标 不变式会破） |
| 禁区（laos/ drivers/ tests/ …）永不可经 env 放行 | 自改写防线：进化产物不得改写 laos 本体（RSI 调研 §8 裁决 #2） | env 全量可配（治理面可被负载改写=防线失守） |
| workdir 驱动侧再闸一遍 | 核心 gate 不查 workdir（Task 4 评审遗留），驱动侧补位防御纵深 | 只信核心 gate（漏一层） |
| checkpoint 解析 canonical→rglob→ENOENT | 布局未经真跑实证（后端 BLOCKED），宁可 fail-loud 不猜 | 按 README 布局硬编码（布局漂移即静默错） |
| `EvolveResult.from_payload` 强转而非严格校验 | 唯一执行器（受信驱动）出准 JSON 类型 | 严格 isinstance（收益小噪音大）——如需收紧属 followups 范畴 |

**已知疤痕**（不是 bug，是记录）：99fac0f 单提交不自绿（并行会话文件被扫入，下一提交 0462915 治愈）——bisect 到该点 skip 即可；分支已整体进 master（565dec8 合并提交内含 INDEX 计数修正）。

## L4 治理与红线层：什么不能碰

1. **conda 红线**：只准 `C:/Users/yaoyue/miniconda3/python.exe`；pip 只进 venv。违反=污染唯一解释器环境，全仓工具链失效。
2. **零依赖红线**：`laos/` 纯 stdlib。把 openevolve/网络库 import 进核心=架构事故（循环内外分离就是为这个）。
3. **目录纪律**：进化作业产物只落 `var/`（gitignored）；target/evaluator/workdir 必须在 `var/rsi/jobs/` 允许根内——gate 会拒，别试图绕。
4. **后端 BLOCKED 现状**（2026-10-09 实测）：环境里唯一 key 是内网网关会话密钥（api.mimo-v2.com 公网 NXDOMAIN，七端点 401），ollama 未运行。**证据原文**：`var/rsi/openevolve/OBSERVATIONS.md` §后端。解锁路径：任一 OpenAI 兼容 key（OpenEvolve 读 `OPENAI_API_BASE`/`OPENAI_API_KEY`，配置面字段已验证同文件）或装 ollama。解锁后第一跑必须：验证事件循环让出（在途并发 syscall）+ 钉死 `_best_score` 的 checkpoint 布局——两件事 followups T3 的 `scripts/evolve_e2e.py` 已写成代码。
5. **sentinel 政策待落地**：当前默认配置下 `evolve.run`（medium+reversible+非 egress）在 ④ 级默认放行；followups T1 已预决把它入 `always_ask`（③ 级，全 mode 生效，② 显式 rule 唯一免问通道）——"审判席"叙事的最后一块，未执行前别误以为是已生效行为。
6. **排程红线**：`AuditLog.rotate()` 补锁（followups T2）与 aor-waves 的 kernel.py 改动同文件——执行 followups 前先看 aor-waves 是否已落地（rec.replay 4d8b48f 已复用 `_BLOCKING_BUILTINS`，说明波次正在动内核）。

## 资产索引

- **调研**：`docs/research/2026-10-09-rsi-landscape.md`（RSIGym/九篇论文/ICLR26 Workshop 110 篇/开源生态/laos 裁决 ●◐○）
- **计划**：`docs/superpowers/plans/2026-10-09-openevolve-trial-and-laos-driver.md`（已执行主体）/ `2026-10-09-evolve-followups.md`（待执行三件）
- **图**：`docs/diagrams/rsi-evolve-architecture.html`（archify 交互图，candidate JSON 同名并存）/ `docs/diagrams/rsi-evolve-handover.drawio`（drawio 源，浏览器打开方式见文件头注释）
- **PPT**：`docs/ppt/laos-rsi-evolve-handover.html`（10 页，frontend-slides 血统，←/→ 翻页、E 键编辑）
- **关键 commit**（master 侧）：20e2ae8（laos/evolve.py）→ 99fac0f（env 红线测试）→ 0462915（evolve.run）→ 558f93d（驱动）→ 301da48（F-A/F-B）→ befb9ec（终审修复波）→ 565dec8（合并）
- **试跑证据**：`var/rsi/openevolve/OBSERVATIONS.md`（安装/后端探测/解锁路径，gitignored——本仓 clone 后按 L1 重建）
