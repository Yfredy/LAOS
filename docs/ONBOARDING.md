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
