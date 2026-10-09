# laos 新人上手（ONBOARDING）

> 纪律与红线见 [AGENTS.md](../AGENTS.md)（代理工作记忆）。本文件只解决**人怎么从零上手**。
> 全文数字均为实跑值，产出命令随行；门禁 `scripts/check_onboarding.py` 会逐条核对（改了代码没改文档 → 门禁红）。

## 0. 事实基线（别信记忆，跑命令）

| 事实 | 值 | 产出命令 |
|---|---|---|
| 主库测试数 | 1016 项（`OK (skipped=5)`） | `python -m unittest discover -s tests 2>&1 \| tail -3` |
| 主库测试耗时 | **1–7 分钟**（两次实测 105s / 371s，机器负载敏感） | 同上命令自带计时 |
| 主库模块数 | 45 个 `laos/*.py` | `python -c "import pathlib;print(len(list(pathlib.Path('laos').glob('*.py'))))"` |
| 测试文件数 | 79 个 `tests/test_*.py` | `python -c "import pathlib;print(len(list(pathlib.Path('tests').glob('test_*.py'))))"` |
| 第二个仓库 | `../AlwaysOnRec-HY4`（HY4，独立 git 仓库，无远端不外推，152 tests / OK） | `cd ../AlwaysOnRec-HY4 && python -m unittest discover -s tests -t . 2>&1 \| tail -2` |

**skip 是正常的**：5 项 skip 均因依赖/平台缺席——`tests/test_audio_driver.py` 需 `.venv-audio`（modelscope/torch 音频栈）未装；`tests/test_ear_mic.py`（2 项）需 conda funasr 与 SenseVoice 模型缓存 / sounddevice；`tests/test_profiling.py` 需 bpftrace 仅 Linux；`tests/test_seccomp.py` 需 seccomp 仅 Linux。**不是回归**。装上对应依赖后它们会自动跑。

## 1. 项目是什么（四段漏斗，唯一主线）

**laos（对外 nanoLAOS）= Linux 内核治理在用户态的延伸；Agent 是与进程同类的新负载。**核心叙事与红线见 [AGENTS.md](../AGENTS.md)（基座是内核，禁止"给 Agent 装操作系统"的主客反转表述）。

主线是全天候录音的**四段漏斗**（数字与入口抄自 `README.md` §六，不另造）：

| 段 | 输入→做什么→输出 | 代码入口 |
|---|---|---|
| ① 常驻检测 | 音频流 → 只有"有没有人声"这一个比特 → 静音根本不落盘 | `laos/vad.py`（StreamingVAD：能量阈值+迟滞+padding） |
| ② 触发捕获 | 有人声的段 → VAD 门控落盘 + 配额 FIFO | `drivers/drv_rec.py`（rec_start/stop/segments） |
| ③ 即时蒸馏 | 音频段 → 文本+情感标签入记忆 | `drivers/drv_ear.py`（ASR+情感）→ `bin/journal.py`（mem.remember） |
| ④ 原音频即焚 | 只有文本记忆留存，原始音频定时删 | `rec_gc(keep_hours=6)`（`drivers/drv_rec.py` 内） |

目录全图见 `README.md` §八；判断层（决策核）从 `laos/judge.py` 读起。**不复制 README 的架构叙述**——本节只是地图。

## 2. 第一小时路径（照抄就能跑）

1. **读纪律（10 min）**：[AGENTS.md](../AGENTS.md) 全文——发版纪律、conda 红线、零依赖、隐私红线、叙事红线，全部是硬约束。
2. **跑通门禁（1–7 分钟，实测 105s/371s 负载敏感，耐心等勿当卡死）**：
   Run: `python -m unittest discover -s tests 2>&1 | tail -3`
   Expected: `Ran 1016 tests` + `OK (skipped=5)`（skip 原因见 §0）
3. **看主入口**：`bin/laosctl.py`（CLI）、`bin/laosd.py`（薄内核守护）、`bin/laosweb.py`（Web 控制面，`python bin/laosweb.py` → `http://127.0.0.1:8800`）。
4. **跑认知 demo（30 秒讲清 kernel+Agent+MCP）**：
   Run: `bash demos/agentos-demo/run_demo.sh`（Windows 上经 WSL 或 Git Bash；`.gitattributes` 已设 `*.sh eol=lf`）
   说明：`demos/agentos-demo/README.md`——五幕剧本，Agent 是真 Linux 进程、MCP 文件服务是真驱动、seccomp 是真强制层。
5. **读核心包（按依赖序）**：`laos/kernel.py`（syscall 闸门链）→ `laos/context.py` → `laos/memory.py`；然后按兴趣下钻四段漏斗的对应入口（§1 表）。
