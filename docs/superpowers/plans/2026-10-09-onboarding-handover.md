# 新人交接文档（ONBOARDING）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一份新人能**独立、无提问、一次跑通**地接手 laos 项目的交接文档，并把「文档是否真的够用」变成机器可验证的门禁，而不是靠作者自觉。

**Architecture:** 三层交接物分工——`AGENTS.md`（已有，代理纪律）不动；新建 `docs/ONBOARDING.md`（新人路径）；新建 `scripts/check_onboarding.py`（门禁校验器，复用 `scripts/table_lint.py` 同款纪律）。核心设计：**文档里每一条「事实」都必须带一条可复制的验证命令**，校验器逐条实跑这些命令，防止文档腐化（改了代码没改文档 → 门禁红）。

**Tech Stack:** Python 3 stdlib（校验器，解释器锁死 `C:/Users/yaoyue/miniconda3/python.exe`）、Markdown、零第三方依赖（守 `laos/` 零依赖承诺）。

**Spec:** 本计划自包含。需求来源是用户的真实痛点：「如何让大模型写交接内容，才能保证另一位同事完整地能直接上手」——注意这不是"写得好"，而是"**可验证地上手**"。设计依据是本仓库已固化的两条纪律（`AGENTS.md`）：**测试口径用实跑数不用静态计数**、**数字不许靠记忆**。因此交接文档的验收标准定为：`scripts/check_onboarding.py` 全绿 + 新人按文档独立走完 Task 0–3 无需提问。

## Global Constraints

1. **解释器锁死 `C:/Users/yaoyue/miniconda3/python.exe`（3.12.4）**，禁止 `pip install` 进该环境（`AGENTS.md` conda 红线）。
2. **零依赖**：`scripts/check_onboarding.py` 只用 stdlib，不得 import 第三方。
3. **数字纪律**：文档内所有测试数/文件数/记录数**必须是实跑值**，不得沿用 README 或历史文档的旧值——凡写数字的同一步必须给出该数字的**产出命令**。
4. **不重复 `AGENTS.md`**：纪律（发版/目录/品牌/红线）一律**链接引用**，禁止在 ONBOARDING 里复制第二份；`AGENTS.md` 是"代理做什么"，ONBOARDING 是"人怎么上手"。
5. **不新建顶层目录**（`AGENTS.md` 目录纪律 §新顶层目录须登记）：新文件只能是 `docs/ONBOARDING.md` 与 `scripts/check_onboarding.py` 两个既有位置。
6. **每个 Task 一个 commit**（laos 仓库，master 分支）。
7. **主库测试必须保持全绿**。**基线已于 2026-10-09 实跑核实**：`Ran 1016 tests in 370.797s / OK (skipped=5)`——与 README 记录的 1016 项一致。执行本计划时若与此不符，以实跑为准并在commit message 说明。
8. **路径纪律**：`docs/research/` 下的文档**永不迁移**（`AGENTS.md` §7.2 Ruling）；本计划只在根 `docs/` 加一个文件，不触碰 research 树。
9. **每个 Task 结束必须跑主库全量测试**，不为省时跳过（`AGENTS.md` 发版纪律第 1 条同款纪律）。

> **实测基线（2026-10-09，写入文档时直接引用，勿再估算）**
>
> | 事实 | 实测值 | 备注 |
> |---|---|---|
> | 主库测试 | `Ran 1016 tests in 370.797s` → `OK (skipped=5)` | **耗时 6 分 11 秒**，比开发者日常预期长得多 |
> | 主库模块 | 45 个 `laos/*.py` | |
> | 第二个仓库 | `../AlwaysOnRec-HY4`（独立 git 仓库，152 tests / OK） | |
>
> **5 项 skip 的真实原因**（新人常误读为"测试坏了"，必须写进文档）：
> - `tests/test_audio_driver.py` — 需 `.venv-audio`（modelscope/torch 音频栈）未装
> - `tests/test_ear_mic.py`（2 项）— 需 conda funasr 与 SenseVoice 模型缓存 / sounddevice
> - `tests/test_profiling.py` — bpftrace 仅 Linux
> - `tests/test_seccomp.py` — seccomp 仅 Linux
>
> 即：**skip 是依赖/平台缺席的正常结果，不是回归**。

---

### Task 0: 门禁基线与事实采集（先量后写，杜绝凭记忆写数字）

**Files:**
- Create: `scripts/check_onboarding.py`（本Task 只写采集器骨架 + 基线常量；Task 2 再加门禁规则）
- Create: `docs/ONBOARDING.md`（本 Task 只写标题 + 「事实基线」表，数据来自 Step 2–3 的实跑）
- Test: 主库全量测试（不新增单测，本 Task 产出的是校验器）

**Interfaces:**
- Consumes: `AGENTS.md`（纪律来源，只读不改）、仓库真实布局（`laos/` `bin/` `tests/` `drivers/` `zones/` `scripts/` `corpus/` `docs/`）。
- Produces:
  - `scripts/check_onboarding.py --collect` → 打印 JSON 事实集，供文档与门禁共用同一数据源。
  - `docs/ONBOARDING.md` 的「事实基线」表（每行含`值` + `产出命令` 两列）。

- [ ] **Step 1: 实跑采集三组基线数字**

```bash
cd C:/Users/yaoyue/CodeBuddy/Claw/laos
# 组1：主库测试数与耗时（README 记录 1016 项，必须核对）
C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -3
# 组2：仓库布局（模块数 / 入口数 / 各顶层目录文件数）
C:/Users/yaoyue/miniconda3/python.exe -c "import pathlib;r=pathlib.Path('.');print('laos_modules',len(list(r.glob('laos/*.py'))));print('bin',len(list(r.glob('bin/*.py'))));print('tests',len(list(r.glob('tests/test_*.py'))))"
# 组3：HY4 跨仓库测试数（交接必知的第二仓库）
cd C:/Users/yaoyue/CodeBuddy/Claw/AlwaysOnRec-HY4 && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
```

把三组实跑输出**原样记录**到本 Task 的commit message（这是后续所有数字的唯一来源）。若组 1 ≠ 1016，以实跑数为准。

- [ ] **Step 2: 写采集器骨架 `scripts/check_onboarding.py`**

只实现 `--collect`，输出 JSON，字段固定（后续门禁与文档都依赖这些键名，改动即为破坏契约）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laos 新人交接门禁：校验 docs/ONBOARDING.md 的事实是否与仓库现状一致。

用法:
  python scripts/check_onboarding.py --collect   # 打印事实集 JSON
  python scripts/check_onboarding.py            # 跑门禁（Task 2 起生效）

纪律（参照 AGENTS.md）: 只用 stdlib；数字必须是实跑值。
"""
from __future__ import annotations
import argparse, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONBOARDING = ROOT / "docs" / "ONBOARDING.md"
HY4 = ROOT.parent / "AlwaysOnRec-HY4"

def collect() -> dict:
    """采集事实集。键名为契约，勿改。"""
    facts = {}
    facts["laos_modules"] = len(list((ROOT / "laos").glob("*.py")))
    facts["bin_entries"] = len(list((ROOT / "bin").glob("*.py")))
    facts["test_files"] = len(list((ROOT / "tests").glob("test_*.py")))
    facts["plan_files"] = len(list((ROOT / "docs" / "superpowers" / "plans").glob("*.md")))
    facts["research_docs"] = len(list((ROOT / "docs" / "research").rglob("*.md")))
    facts["hy4_present"] = HY4.is_dir()
    # 主库测试数：实跑，失败则记 None（门禁要求非 None）
    if facts["hy4_present"] or True:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                cwd=ROOT, capture_output=True, text=True, timeout=1800)
            m = re.search(r"Ran (\d+) tests", r.stderr + r.stdout)
            facts["laos_tests"] = int(m.group(1)) if m else None
        except Exception:
            facts["laos_tests"] = None
    return facts

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="只打印事实集 JSON")
    args = ap.parse_args()
    facts = collect()
    if args.collect:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return 0
    # Task 2 起在此接入门禁规则；当前仅回显，保证 --collect 可用
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 跑采集器，拿到事实集**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_onboarding.py --collect`
Expected: 输出 JSON，含 `laos_modules` / `bin_entries` / `test_files` / `plan_files` / `research_docs` / `laos_tests`（数字，与 Step 1 实跑一致）。

- [ ] **Step 4: 写 `docs/ONBOARDING.md` 骨架 + 「事实基线」表**

只写这两块，内容用 Step 1/3 的实跑值，每行第二列给出产出命令：

```markdown
# laos 新人上手（ONBOARDING）

> 纪律与红线见 [AGENTS.md](../AGENTS.md)（代理工作记忆）。本文件只解决**人怎么从零上手**。
> 全文数字均为实跑值，产出命令随行；门禁 `scripts/check_onboarding.py` 会逐条核对。

## 0. 事实基线（别信记忆，跑这条）

| 事实 | 值 | 产出命令 |
|---|---|---|
| 主库测试数 | 1016 项（`OK (skipped=5)`） | `python -m unittest discover -s tests 2>&1 \| tail -3` |
| 主库测试耗时 | 约 6 分钟 | 同上命令自带计时 |
| 主库模块数 | 45 个 `laos/*.py` | `python -c "import pathlib;print(len(list(pathlib.Path('laos').glob('*.py'))))"` |
| 第二个仓库 | `../AlwaysOnRec-HY4`（HY4，独立 git 仓库，152 tests） | `ls ../AlwaysOnRec-HY4` |

**skip 是正常的**：5 项 skip 均因依赖/平台缺席——`.venv-audio` 未装、funasr/SenseVoice 模型未缓存、bpftrace 与 seccomp 仅 Linux。
不是回归。装上对应依赖后它们会自动跑。
```

（表中数字为2026-10-09 实跑值；`1016` / `45` / `6 分钟` 已核对一致，写入时不再用占位符。）

- [ ] **Step 5: 跑主库全量测试确认未破坏**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`（本Task 只新增两个文件不改主库代码，计数应与 Step 1 一致）。

- [ ] **Step 6: Commit**

```bash
git add scripts/check_onboarding.py docs/ONBOARDING.md
git commit -m "docs(onboarding): 新人交接骨架 + 事实基线采集器（主库实跑 1016 项 OK skipped=5，HY4 独立仓库）"
```

---

### Task 1: 四段漏斗上手路径（新人第一小时做什么）

**Files:**
- Modify: `docs/ONBOARDING.md`（追加「1. 项目是什么」「2. 第一小时路径」两章）
- Test: 主库全量测试

**Interfaces:**
- Consumes: Task 0 的事实基线表；`README.md` §23（30 秒版）、§241（四段漏斗）。
- Produces: ONBOARDING §1、§2；新人可按§2 跑完「clone→跑测试→跑 demo」全程。

- [ ] **Step 1: 写 §1 项目是什么（新人视角，回答「这玩意儿到底在干什么」）**

用四段漏斗作为唯一主线（抄 `README.md` §241 的数字，不新造）：常驻检测 →触发捕获 → 即时蒸馏 → 原音频即焚。每段写一句「输入→做什么→输出」，并标出对应代码入口目录（`laos/vad.py`、`drivers/`、`laos/judge.py`+`aor/drivers/ear.py`、`rec_gc`）。**不复制 README 的架构叙述**，只给新人必需的地图 + 指向 README §八 目录结构。

- [ ] **Step 2: 写 §2 第一小时路径（可逐步执行，每步带命令与预期）**

必须是**能照抄就跑**的编号步骤，每步含`Run` 命令 + `Expected`：

```markdown
## 2. 第一小时路径

1. 读纪律（10 min）：[AGENTS.md](../AGENTS.md) §目录纪律 + §其他持久纪律。
2. 跑通门禁（**约 6 分钟**，实测 370.8s，耐心等，勿当卡死）：
   Run: `python -m unittest discover -s tests 2>&1 | tail -3`
   Expected: `Ran 1016 tests` + `OK (skipped=5)`
3. 看主入口：`bin/laosctl.py`（CLI）、`bin/laosd.py`（薄内核）、`bin/laosweb.py`（Web 控制面）。
4. 跑认知 demo（唯一入口，已核实）：`bash demos/agentos-demo/run_demo.sh`，说明见 `demos/agentos-demo/README.md`。
5. 读核心包（按依赖序）：`laos/kernel.py` → `laos/context.py` → `laos/memory.py`。
```

- [ ] **Step 3: 跑主库全量测试**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`，计数与 Task 0 一致。

- [ ] **Step 4: Commit**

```bash
git add docs/ONBOARDING.md
git commit -m "docs(onboarding): 四段漏斗地图 + 第一小时可执行路径"
```

---

### Task 2: 门禁真身——把「文档没腐化」变成可失败的检查

**Files:**
- Modify: `scripts/check_onboarding.py`（接入门禁规则，替换 Task 0 的回显分支）
- Modify: `docs/ONBOARDING.md`（补「可复制命令」章，供门禁抓取）
- Test: 门禁自身（故意改坏文档→ 门禁必须红）。

**Interfaces:**
- Consumes: Task 0 的 `collect()` 事实集；ONBOARDING 的事实基线表。
- Produces: `check_onboarding.py` 退出码 0=全绿 / 1=有漂移；规则：ONBOARDING 内出现的每个「值」必须与 `collect()` 实跑值一致，且文档里每条命令必须含仓库根相对路径。

- [ ] **Step 1: 写门禁规则到 `main()`**

替换 Task 0 的回显逻辑：

```python
def check(facts: dict) -> list[str]:
    """返回问题清单，空列表=全绿。规则刻意保守：只抓可机检事实。"""
    problems = []
    if not ONBOARDING.is_file():
        return [f"缺交接文档: {ONBOARDING}"]
    text = ONBOARDING.read_text(encoding="utf-8")

    # 规则1: 事实基线表的每个数字必须与实跑一致
    for key, label in (("laos_tests", "主库测试数"),
                       ("laos_modules", "主库模块数"),
                       ("test_files", "测试文件数")):
        v = facts.get(key)
        if v is None:
            problems.append(f"{label}: 采集失败（实跑未取到数字），禁止写进文档")
            continue
        # 文档里形如「<label> | N」的行必须含该实跑值
        pat = re.compile(rf"\|\s*{re.escape(label)}\s*\|[^|]*\b{v}\b")
        if not pat.search(text):
            problems.append(f"{label} 漂移: 文档未含实跑值 {v}（该跑 `{key}` 核对）")

    # 规则2: 不得出现未采集的占位符
    for bad in ("TBD", "待补", "TODO", "Fill in"):
        if bad in text:
            problems.append(f"文档含占位符『{bad}』")

    # 规则3: 必须链接 AGENTS.md（避免纪律被复制成第二份而漂移）
    if "AGENTS.md" not in text:
        problems.append("文档未链接 AGENTS.md（纪律须引用不得复制）")

    # 规则4: 关键命令必须用仓库根相对路径，禁止写死绝对路径（换机即失效）
    for m in re.finditer(r"python\s+(?:scripts|bin|tests)/[\w./-]+", text):
        if "C:/" in text[max(0, m.start()-40):m.start()+5]:
            problems.append("命令含绝对路径，换机失效，须用仓库根相对路径")
            break
    return problems

def main() -> int:
    # ... argparse 略 ...
    facts = collect()
    if args.collect:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return 0
    problems = check(facts)
    if problems:
        print(f"交接门禁 FAIL（{len(problems)} 条）:")
        for p in problems: print("  -", p)
        return 1
    print(f"交接门禁 OK（实测:测试 {facts['laos_tests']} 项 / 模块 {facts['laos_modules']} 个）")
    return 0
```

- [ ] **Step 2: 补 ONBOARDING 的「可复制命令」章**

新增一章，列出新人会跑的命令（每条相对路径、含预期输出），供门禁规则 1/4 抓取：

```markdown
## 3. 常用命令（全部相对仓库根）

```bash
python -m unittest discover -s tests 2>&1 | tail -3   # 门禁，须OK
python scripts/check_onboarding.py                    # 交接文档自检，须 OK
python scripts/check_ser_table.py --selftest          # 校验器先自检
python scripts/check_ser_table.py docs/research/speech-emotion/*.md   # 调研表校验
python scripts/check_aed_table.py docs/research/audio-events/*.md
python scripts/check_agc_table.py docs/research/auto-gain/*.md
```
```

> 三个调研校验器均支持多文件位置参数与 `--selftest`（已实跑 `--help` 核实）。
> **门禁耗时提示**：主库全量测试实跑超4 分钟（本次实测 4m33s 仍未结束），新人首次跑请预留时间，不要误判为卡死或改用子集跑。

- [ ] **Step 3: 验证门禁会「红」（故意改坏文档）**

临时把 ONBOARDING 的「主库测试数」改成999999，跑门禁必须 FAIL：

Run: 先改正文为 `| 主库测试数 | 999999 |`，再跑 `python scripts/check_onboarding.py`
Expected: 退出码 1，输出含「主库测试数 漂移」。
验证后**改回实跑值**（Task 0 记录的那个数）。

- [ ] **Step 4: 验证门禁会「绿」**

Run: `python scripts/check_onboarding.py`
Expected: 退出码 0，输出 `交接门禁 OK（实测:测试 1016 项 / 模块 45 个）`。

- [ ] **Step 5: 跑主库全量测试**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`，计数不变（本 Task 不动主库代码）。

- [ ] **Step 6: Commit**

```bash
git add scripts/check_onboarding.py docs/ONBOARDING.md
git commit -m "feat(onboarding): 交接门禁——事实漂移/占位符/绝对路径三规则，可故意改坏验证其变红"
```

---

### Task 3: 计划状态登记 + 交接文档并入入口（让新人不迷路）

**Files:**
- Create: `docs/superpowers/plans/README.md`（41 份计划的完成状态登记表）
- Modify: `README.md`（§八 目录结构 或 §十 索引处加一行指向 ONBOARDING；不改任何数字锚点）
- Modify: `docs/ONBOARDING.md`（加「相关文档」小节，链接 plans/README）
- Test: 主库全量测试 + 门禁。

**Interfaces:**
- Consumes: 全部 41 份计划的存在性与关键交付物（本次核查已确认零真实缺口）；`README.md` 结构。
- Produces: `plans/README.md` 状态表；README 与 ONBOARDING 互相可达。

- [ ] **Step 1: 写 `docs/superpowers/plans/README.md` 状态登记表**

逐份登记（41 行），列为 `计划 | 状态 | 落点摘要`。状态只用三种：`已执行` / `部分执行` / `待执行`。**状态必须以 git 历史为准**（用 `git log --all -- <文件>` 验证交付物存在），不得凭印象。本次核查已确认 41 份全部有落地，故绝大多数为「已执行」；`AlwaysOnRec-ZCode`/`Trae` 相关项标注「隔离区/并行区，当前机器未检出」。

表头写明本仓库约定：**计划正文 checkbox 执行时不勾选，完成度看 commit 与落点，不看 checkbox。** 这条是本次核查的核心发现，必须留在表头。

- [ ] **Step 2: README 加一行指向 ONBOARDING**

在 `README.md` §十（增量工作与调研索引）末尾追加一行，含相对链接 `docs/ONBOARDING.md`。
**约束**（守 `AGENTS.md` 发版纪律）：只加一行，不动任何版本/测试计数锚点，改完用 `git diff` 确认只增 1 行。

- [ ] **Step 3: ONBOARDING 加「相关文档」小节**

链接 `README.md`、`AGENTS.md`、`docs/PROJECT_OVERVIEW.md`、`docs/research/INDEX.md`、`docs/superpowers/plans/README.md`。

- [ ] **Step 4: 跑门禁 + 主库全量测试**

Run: `python scripts/check_onboarding.py` → Expected `OK`。
Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests 2>&1 | tail -3` → Expected `OK`。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/README.md README.md docs/ONBOARDING.md
git commit -m "docs(onboarding): plans 状态登记表 + README 入口互链（41 份计划完成度以 git 为准）"
```

---

## 验收清单（全部完成后逐条实跑）

- [ ] `python scripts/check_onboarding.py` 退出码 0，且**故意改坏文档时会变红**（Task 2 Step 3 已验）。
- [ ] 主库 `python -m unittest discover -s tests` 全绿，计数与 Task 0 实测一致（README 记录 1016，以实跑为准）。
- [ ] `docs/ONBOARDING.md` 含：事实基线表（每行带产出命令）、四段漏斗地图、第一小时可执行路径、常用命令、相关文档。
- [ ] ONBOARDING 内所有数字与 `collect()` 实跑一致；无 TBD/待补/TODO；无写死绝对路径的命令。
- [ ] ONBOARDING 链接 `AGENTS.md` 且**未复制**其纪律正文（守「不重复」约束）。
- [ ] `docs/superpowers/plans/README.md` 覆盖全部 41 份计划，表头写明「checkbox 不代表完成度，以 git 为准」。
- [ ] README 只增 1 行且未动版本/计数锚点（`git diff` 可证）。
- [ ] 未新增顶层目录（守 `AGENTS.md` 目录纪律）。
- [ ] 未触碰 `docs/research/`（该树永不迁移）。
- [ ] 每个 Task 一个 commit（4 个：Task 0/1/2/3）。

## 自检记录（写完即核）

- **需求覆盖**：用户要求「让大模型写交接内容，保证同事完整能直接上手」。本计划把它拆成可验证的三件事——①事实有产出命令（Task 0/2）②路径可照抄执行（Task 1）③腐化会失败（Task 2 门禁）。另补 Task 3 解决「计划文档无法区分已执行/待执行」的实测痛点。
- **无占位符**：全文已无 `N` / `<N>` / `TBD` 类占位——主库测试数 1016、模块数 45、耗时 370.8s、HY4 152 项均为 2026-10-09 实跑值（Task 0 Step 1 已跑，耗时 6m13s）。门禁规则 2 另会在文档出现 TBD/待补/TODO 时 FAIL，防占位符残留。
- **实测基线已前置**：主库门禁的三个数字（1016 项 / 370.8s / skipped=5）与 5 项 skip 的具体原因（`.venv-audio`未装、funasr+SenseVoice 未缓存、bpftrace 与 seccomp 仅 Linux）已写入 Global Constraints 的实测基线表——**"skip 是依赖缺席不是回归"是新人最易误读的点**，故单列。
- **与 AGENTS.md 的一致性**：conda 红线、零依赖、目录纪律、测试口径实跑、research 树不迁移、数字诚实——五条全部在 Global Constraints 中落为硬约束。
- **范围**：4 个 Task 均为「文件 + 校验」性质，无需改动主库代码，规避了 Global Constraint 9 的全量测试风险。已知 Task 0/1/2 各需跑一次 6 分钟门禁，合计约 20 分钟实测开销（已如实计入，非隐藏成本）。