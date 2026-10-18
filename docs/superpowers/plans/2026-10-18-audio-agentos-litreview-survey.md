# 音频智能体技术综述（AgentOS / 多模态 / 全天候录音 / SER / AED / AGC）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 LitReview 九步 SOP（S0–S8）产出一篇可溯源、可机器校验的中文文献综述，覆盖 AgentOS×音频、多模态、全天候录音、声学情感（SER）、音频事件识别（AED）、自动增益控制（AGC），并把用户提出的“端侧/多模态/大中小”五类拆成可比较的正交维度。

**Architecture:** 以仓库既有三份领域调研（SER 46 条 / AED 58 条 / AGC 35+3 条）与全天候录音、AgentOS 两份调研为证据基座；只对缺口做限时定向补检（本地 123,271 条 venue 元数据 + arXiv/官方榜单）。综述正文与证据附录分离：正文只放叙事与对比矩阵，范围合同、检索日志、筛选理由、单篇卡片、溯源记录全部进证据附录。新增 `scripts/check_survey.py` 把“引用可解析、每行有条件、未来方向有出处、未核实不混入正文”变成退出码。

**Tech Stack:** Python 3（纯 stdlib：argparse/re/pathlib/urllib/xml.etree）、Markdown、既有 `scripts/query_corpus.py` 与 `scripts/check_{ser,aed,agc}_table.py`；不新增任何第三方依赖。

**Spec:** `docs/research/2026-10-18-litreview-skill-workflow.md`（S0–S8 工作流、验收清单、语料边界）；领域与分类要求来自用户 2026-10-18 指令（AgentOS-audio / multimedia / 全天候录音 / SER / AED / AGC，AED 与 AGC 各含端侧、多模态、大中小）。

## Global Constraints

以下约束对每个 Task 隐式生效，数值逐字照抄，不得在正文里改写：

- **零依赖**：`laos/` 核心纯 stdlib；本计划所有脚本同样只用 stdlib。禁止 `pip install`/`conda install`/新建 venv。Python 只用 `C:/Users/yaoyue/miniconda3/python.exe`。
- **规模分档（三个领域共用）**：小型 `[0, 30M)`；中型 `[30M, 500M)`；大型 `[500M, +∞)`。边界左闭右开，参数量按“量化前、含音频编码器”计。
- **分类维度**：用户说的“端侧部署 / 多模态 / 大 / 中 / 小”**不在同一维度**。综述必须写成“规模为主键 + `edge`/`multimodal` 两个正交标记”；AGC 另加“经典 DSP 档”（无参数量，是本领域实际主力）。AED 再多一个主键维度“任务类型”：`tagging` / `SED` / `ASC` / `开放词表`；跨任务类型指标不可比。
- **AudioSet 口径**：任何 AudioSet 数字必须标 `AS-20K` / `AS-2M` / `full` 之一；同模型双报时主表记 full。
- **AGC 作用点**：`采集前` / `采集后` / `播放前` / `离线`；控制对象六值见 `docs/research/auto-gain/00-taxonomy-and-metrics.md`。相邻领域必须写 `非AGC(相邻：…)` 并给出收录理由。
- **证据等级**：参考文献表 `核验层级` 只能是 `全文` / `表格核实` / `摘要` / `二手`。引用 `摘要` 或 `二手` 的小节必须出现“摘要口径”或“二手口径”声明。
- **数字规则**：正文里每个跨论文数字都必须带数据集/指标/硬件或配置条件；缺任一项只能定性描述，不得进对比矩阵。数字只进表格，表格行必须含条件括号。
- **参考文献下限**：`--strict` 要求 ≥60 篇；本计划目标 80 篇。每篇必须有可打开的 `https://` 链接、四位年份、非空“局限”字段。
- **语料诚实**：`corpus/venue_expansion` 是 123,271 条 venue 元数据（标题/摘要/DOI），`docs/research/papers/` 有 147 个 PDF（索引口径 115 篇）。综述不得声称对全量语料做过全文精读；摘要级结论按上面的等级规则标注。
- **来源诚实**：拿不到全文/核不到的内容进“未核实清单”，不得混入正文事实层；外部页面访问失败如实记录，不引用宣称值。
- **目录纪律**：新增文件只放 `docs/research/`、`scripts/`、`tests/`；临时抓取物只进 `var/litreview/`（gitignored）。不新建顶层目录。
- **发版锚点不动**：本计划不更新 README/PPT/`__version__` 的版本与测试计数；新测试导致的计数变化留到下次发版由 `scripts/release.py` 统一刷新。
- **既有校验器必须常绿**：`check_ser_table.py` / `check_aed_table.py` / `check_agc_table.py` 的退出码必须保持 0；新增记录若写回领域文档，必须先过对应校验器。

## File Structure

| 路径 | 职责 |
|---|---|
| `docs/research/2026-10-18-audio-agentos-survey.md` | 综述正文（§1–§10），只放叙事、对比矩阵、结论、参考文献 |
| `docs/research/2026-10-18-audio-agentos-survey-evidence.md` | 证据附录（§1–§7）：范围合同、检索日志、筛选理由、单篇卡片、叙事大纲、溯源记录、未核实清单 |
| `scripts/check_survey.py` | 正文+附录结构/引用/条件校验器，`--strict` 为交付门禁 |
| `tests/test_check_survey.py` | 校验器单元测试（unittest，纯离线） |
| `var/litreview/` | 临时检索产物（corpus JSONL、arXiv XML/TSV、URL 探测结果），不进 git |
| `docs/research/INDEX.md` | 论文资产清单登记（两份新文档） |
| `docs/superpowers/plans/README.md` | 计划状态表登记 |

正文小节固定为（标题逐字一致，校验器按前缀匹配）：

```text
## 1. 摘要与结论
## 2. 范围、检索与筛选方法
## 3. AgentOS × 音频 × 多模态 × 全天候录音
## 4. 声学情感模型（SER）
## 5. 音频事件识别（AED）
## 6. 自动增益控制（AGC）
## 7. 跨领域对比
## 8. 研究空白与未来方向
## 9. 局限与未核实清单
## 10. 参考文献
```

证据附录小节固定为：

```text
## 1. 范围合同
## 2. 检索日志
## 3. 筛选与排除
## 4. 单篇卡片
## 5. 叙事大纲
## 6. 溯源核验记录
## 7. 未核实清单
```

---

### Task 1: 综述校验器与单元测试

**Files:**
- Create: `scripts/check_survey.py`
- Test: `tests/test_check_survey.py`

**Interfaces:**
- Consumes: 无（独立新脚本）。
- Produces:
  - `run_checks(survey_path: str, survey_text: str, evidence_path: str, evidence_text: str, strict: bool = False) -> list[Violation]`
  - `main(argv: list[str] | None = None) -> int`
  - CLI：`python scripts/check_survey.py [--strict] SURVEY.md EVIDENCE.md`；`--selftest`
  - 违规规则名（后续 Task 用退出码与规则名验证）：`survey-section`、`ref-schema`、`ref-id`、`ref-year`、`ref-url`、`ref-level`、`ref-limitation`、`ref-seq`、`ref-count`、`ref-count-claim`、`cite-undefined`、`cite-unused`、`matrix`、`matrix-ref`、`matrix-tier`、`matrix-condition`、`matrix-flag`、`matrix-count`、`matrix-tier-cover`、`matrix-dsp`、`metric-condition`、`future-work`、`future-work-ref`、`future-work-basis`、`unverified-leak`、`abstract-qualifier`、`evidence-section`、`search-log`、`screen-table`、`screen-decision`、`screen-reason`、`card-field`、`card-missing`、`outline-table`、`outline-cell`、`outline-ref`、`outline-coverage`、`outline-sections`

- [ ] **Step 1: 写失败测试（完整测试文件）**

```python
# tests/test_check_survey.py
"""综述校验器：结构/引用/条件/证据附录五组不变量。纯离线。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_survey as cs  # noqa: E402


GOOD_SURVEY = """# 测试综述

## 1. 摘要与结论
本文纳入 1 篇文献。[S01]

## 2. 范围、检索与筛选方法
检索与筛选见证据附录。

## 3. AgentOS × 音频 × 多模态 × 全天候录音
| 应用/系统 | 形态 | 处理位置 | 触发方式 | 音频角色 | 代表文献 | 可借鉴点 | 限制（含部署/合规条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |

## 4. 声学情感模型（SER）
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M | 小型 | 1.0 | 是 | 否 | [S01] | 低延迟 | 仅在 IEMOCAP（4 类） |

## 5. 音频事件识别（AED）
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 任务类型 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 小型 | 0.1 | 是 | 否 | tagging | [S01] | 可量化 | 仅 DCASE 低复杂度（128 KiB） |

## 6. 自动增益控制（AGC）
| 模型 | 档位 | 参数量(M) | 作用点 | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G | 经典DSP | n/a(非神经) | 采集后 | 是 | 否 | [S01] | 零延迟 | 仅闭环增益（无噪声场景） |

## 7. 跨领域对比
| 领域 | 规模分档依据 | 端侧判定依据 | 多模态现状 | 可比指标 | 不可比陷阱 | 代表文献 |
| --- | --- | --- | --- | --- | --- | --- |
| SER | 参数量 | 实测功耗 | 有但薄 | UAR | 类别数不同（4 类 vs 6 类） | [S01] |

## 8. 研究空白与未来方向
1. 做端侧中文场景评测（源于 [S01] 的局限：仅原型验证）。

## 9. 局限与未核实清单
- [未核实] 未取得全文的结论不进入正文。

## 10. 参考文献
| 编号 | 文献 | 年份 | 发表 venue | 链接 | 核验层级 | 局限 |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |
"""

GOOD_EVIDENCE = """# 证据附录

## 1. 范围合同
主题、核心问题、时间窗、纳入/排除标准见正文。

## 2. 检索日志
| 检索日 | 库/通道 | 检索式 | 年份窗 | 命中 | 纳入候选 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | corpus | audio event | 2017-2026 | 10 | 3 |

## 3. 筛选与排除
| 编号 | 文献 | 年份 | 决定 | 理由 |
| --- | --- | --- | --- | --- |
| C01 | Test Paper | 纳入 | 与核心问题直接相关 |

## 4. 单篇卡片
### [S01] Test Paper
- 问题：问题
- 方法：方法
- 数据：数据
- 指标与条件：指标（数据集）
- 局限：局限
- 对话：对话

## 5. 叙事大纲
| 小节 | 回答的问题 | 为什么这几篇放在一起 | 读者带走的一句判断 | 代表文献 |
| --- | --- | --- | --- | --- |
| §3 | 应用怎么落地 | 能力与失效互补 | 端侧克制常开 | [S01] |

## 6. 溯源核验记录
| 编号 | 核验对象 | 方式 | 结果 |
| --- | --- | --- | --- |
| S01 | 指标 | 原文表格 | 一致 |

## 7. 未核实清单
- [U01] 某宣称值 — 无全文 — 影响 §3
"""


def rules(vs):
    return {v.rule for v in vs}


def check(survey=GOOD_SURVEY, evidence=GOOD_EVIDENCE, strict=False):
    return cs.run_checks("s.md", survey, "e.md", evidence, strict=strict)


class CheckSurveyTest(unittest.TestCase):
    def test_good_pair_passes(self):
        self.assertEqual(check(), [])

    def test_strict_requires_all_sections(self):
        vs = check(survey=GOOD_SURVEY.replace("## 10. 参考文献", ""), strict=True)
        self.assertIn("survey-section", rules(vs))

    def test_duplicate_ref_id(self):
        dup = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S01 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        self.assertIn("ref-id", rules(check(survey=dup)))

    def test_undefined_citation(self):
        bad = GOOD_SURVEY.replace("| X | 耳机 | 端侧 | 显式 | 触发 | [S01] |",
                                  "| X | 耳机 | 端侧 | 显式 | 触发 | [S09] |")
        self.assertIn("cite-undefined", rules(check(survey=bad)))

    def test_unused_reference(self):
        bad = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S02 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        self.assertIn("cite-unused", rules(check(survey=bad)))

    def test_matrix_requires_condition(self):
        bad = GOOD_SURVEY.replace("仅在 IEMOCAP（4 类）", "仅在 IEMOCAP")
        self.assertIn("matrix-condition", rules(check(survey=bad)))

    def test_metric_without_condition(self):
        bad = GOOD_SURVEY.replace(
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |",
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | mAP 0.5 | 无任何条件 |")
        self.assertIn("metric-condition", rules(check(survey=bad)))

    def test_future_work_needs_citation_and_limitation(self):
        bad = GOOD_SURVEY.replace(
            "1. 做端侧中文场景评测（源于 [S01] 的局限：仅原型验证）。",
            "1. 做端侧中文场景评测。")
        self.assertIn("future-work-ref", rules(check(survey=bad)))
        self.assertIn("future-work-basis", rules(check(survey=bad)))

    def test_weak_ref_section_needs_qualifier(self):
        bad = GOOD_SURVEY.replace("| 全文 | 仅原型验证（n=1） |",
                                  "| 摘要 | 仅原型验证（n=1） |")
        self.assertIn("abstract-qualifier", rules(check(survey=bad)))

    def test_card_field_required(self):
        bad = GOOD_EVIDENCE.replace("- 局限：局限\n", "")
        self.assertIn("card-field", rules(check(evidence=bad)))

    def test_strict_outline_covers_every_ref(self):
        survey = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S02 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        survey = survey.replace("本文纳入 1 篇文献。[S01]", "本文纳入 2 篇文献。[S01][S02]")
        self.assertIn("outline-coverage", rules(check(survey=survey, strict=True)))

    def test_selftest_cli(self):
        self.assertEqual(cs.main(["--selftest"]), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_check_survey -v
```

Expected: `ModuleNotFoundError: No module named 'check_survey'`。

- [ ] **Step 3: 写解析核心与参考文献/引用规则**

创建 `scripts/check_survey.py`，先写以下内容（后续步骤在同一文件追加）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_survey.py — 综述正文与证据附录的结构/引用/条件校验器（纯 stdlib）。

用法：
    python scripts/check_survey.py SURVEY.md EVIDENCE.md
    python scripts/check_survey.py --strict SURVEY.md EVIDENCE.md
    python scripts/check_survey.py --selftest

非严格模式只校验已写内容（空小节/空参考文献表跳过），供写作过程逐节验证；
--strict 追加完整性要求（10 节齐全、纳入 >= 60 篇、矩阵行数下限、卡片/大纲全覆盖）。

退出码：0 = 通过；1 = 有违规。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SURVEY_SECTIONS = (
    "## 1. 摘要与结论",
    "## 2. 范围、检索与筛选方法",
    "## 3. AgentOS × 音频 × 多模态 × 全天候录音",
    "## 4. 声学情感模型（SER）",
    "## 5. 音频事件识别（AED）",
    "## 6. 自动增益控制（AGC）",
    "## 7. 跨领域对比",
    "## 8. 研究空白与未来方向",
    "## 9. 局限与未核实清单",
    "## 10. 参考文献",
)
EVIDENCE_SECTIONS = (
    "## 1. 范围合同",
    "## 2. 检索日志",
    "## 3. 筛选与排除",
    "## 4. 单篇卡片",
    "## 5. 叙事大纲",
    "## 6. 溯源核验记录",
    "## 7. 未核实清单",
)
REF_COLS = ("编号", "文献", "年份", "发表 venue", "链接", "核验层级", "局限")
LEVELS = ("全文", "表格核实", "摘要", "二手")
TIERS = ("小型", "中型", "大型", "经典DSP")
PLACEHOLDERS = ("tbd", "todo", "待补", "?", "无", "略")
CITE_RE = re.compile(r"\[(S\d{2})\]")
METRIC_RE = re.compile(r"\b(mAP|UAR|WA|Acc|DER|PSDS|LUFS|dB|ms|MB)\b", re.I)
CARD_FIELDS = ("问题", "方法", "数据", "指标与条件", "局限", "对话")
MIN_REFS = 60


class Violation:
    def __init__(self, path: str, rule: str, detail: str):
        self.path, self.rule, self.detail = path, rule, detail

    def __str__(self) -> str:
        return f"{self.path}  [{self.rule}] {self.detail}"


def split_h2(text: str) -> dict[str, str]:
    """只按 '## ' 二级标题切分；返回 {标题行: 正文}。"""
    out: dict[str, str] = {}
    cur = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf)
            cur, buf = line.strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out[cur] = "\n".join(buf)
    return out


def find_section(sections: dict[str, str], prefix: str):
    for head, body in sections.items():
        if head.startswith(prefix):
            return head, body
    return None, None


def parse_tables(body: str) -> list[tuple[list[str], list[list[str]]]]:
    """解析 markdown 表格；返回 [(header, rows)]，跳过 | --- | 分隔行。"""
    tables = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            if len(block) >= 2:
                header = [c.strip() for c in block[0].strip("|").split("|")]
                rows = []
                for raw in block[1:]:
                    cells = [c.strip() for c in raw.strip("|").split("|")]
                    if cells and all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                        continue
                    rows.append(cells)
                tables.append((header, rows))
        else:
            i += 1
    return tables


def require_cols(path: str, header: list[str], cols: tuple[str, ...], rule: str):
    missing = [c for c in cols if c not in header]
    if missing:
        return [Violation(path, rule, f"表头缺列 {missing}（实际 {header}）")]
    return []


def parse_refs(path: str, body: str, strict: bool):
    if not body.strip():
        return [], ([] if not strict else
                    [Violation(path, "ref-schema", "参考文献小节为空")])
    for header, rows in parse_tables(body):
        if "编号" in header and "链接" in header:
            errs = require_cols(path, header, REF_COLS, "ref-schema")
            if errs:
                return [], errs
            idx = {c: header.index(c) for c in REF_COLS}
            out = []
            for cells in rows:
                cells = cells + [""] * (len(header) - len(cells))
                out.append({c: cells[idx[c]] for c in REF_COLS})
            return out, []
    return [], [Violation(path, "ref-schema", "未找到参考文献表（需含 编号/链接 列）")]


def check_refs(path: str, rows: list[dict]) -> list[Violation]:
    out = []
    seen = set()
    nums = []
    for r in rows:
        rid = r["编号"]
        if not re.fullmatch(r"S\d{2}", rid):
            out.append(Violation(path, "ref-id", f"编号 {rid!r} 非 S01 形"))
        elif rid in seen:
            out.append(Violation(path, "ref-id", f"编号重复 {rid}"))
        else:
            nums.append(int(rid[1:]))
        seen.add(rid)
        if not re.fullmatch(r"(19|20)\d{2}", r["年份"]):
            out.append(Violation(path, "ref-year", f"{rid} 年份 {r['年份']!r} 非四位年"))
        if not r["链接"].startswith("https://"):
            out.append(Violation(path, "ref-url", f"{rid} 链接非 https：{r['链接']!r}"))
        if r["核验层级"] not in LEVELS:
            out.append(Violation(path, "ref-level",
                                 f"{rid} 核验层级 {r['核验层级']!r} 不在 {LEVELS}"))
        lim = r["局限"].strip()
        if len(lim) < 4 or lim.lower() in PLACEHOLDERS:
            out.append(Violation(path, "ref-limitation",
                                 f"{rid} 局限为空/占位：{lim!r}"))
    if nums and sorted(nums) != list(range(1, len(nums) + 1)):
        out.append(Violation(path, "ref-seq", f"编号不连续：{sorted(nums)[:6]}"))
    return out


def check_citations(path: str, body: str, refs: list[dict], strict: bool):
    out = []
    defined = {r["编号"] for r in refs}
    cited = set(CITE_RE.findall(body))
    for rid in sorted(cited - defined):
        out.append(Violation(path, "cite-undefined", f"正文引用未定义编号 {rid}"))
    for rid in sorted(defined - cited):
        out.append(Violation(path, "cite-unused", f"参考文献 {rid} 从未在正文引用"))
    if strict and len(refs) < MIN_REFS:
        out.append(Violation(path, "ref-count", f"纳入文献 {len(refs)} 篇 < {MIN_REFS}"))
    m = re.search(r"纳入\s*(\d+)\s*篇", body)
    if m and int(m.group(1)) != len(refs):
        out.append(Violation(path, "ref-count-claim",
                             f"摘要称纳入 {m.group(1)} 篇，参考文献表 {len(refs)} 篇"))
    return out
```

- [ ] **Step 4: 追加矩阵、条件、未来方向、未核实规则**

在 `scripts/check_survey.py` 末尾追加：

```python
MATRIX_COLS = {
    "APP": ("应用/系统", "形态", "处理位置", "触发方式", "音频角色",
            "代表文献", "可借鉴点", "限制（含部署/合规条件）"),
    "SER": ("模型", "档位", "参数量(M)", "端侧", "多模态",
            "代表文献", "优势", "限制（含实验条件）"),
    "AED": ("模型", "档位", "参数量(M)", "端侧", "多模态", "任务类型",
            "代表文献", "优势", "限制（含实验条件）"),
    "AGC": ("模型", "档位", "参数量(M)", "作用点", "端侧", "多模态",
            "代表文献", "优势", "限制（含实验条件）"),
    "CROSS": ("领域", "规模分档依据", "端侧判定依据", "多模态现状",
              "可比指标", "不可比陷阱", "代表文献"),
}
SECTION_MATRIX = {
    "## 3.": ("APP", 8),
    "## 4.": ("SER", 10),
    "## 5.": ("AED", 15),
    "## 6.": ("AGC", 12),
    "## 7.": ("CROSS", 5),
}
LIMIT_COL = {
    "APP": "限制（含部署/合规条件）",
    "SER": "限制（含实验条件）",
    "AED": "限制（含实验条件）",
    "AGC": "限制（含实验条件）",
    "CROSS": "不可比陷阱",
}


def check_matrix(path, sections, prefix, kind, min_rows, refs, strict):
    head, body = find_section(sections, prefix)
    if head is None:
        return [Violation(path, "matrix", f"缺小节 {prefix}")] if strict else []
    if not body.strip():
        return [Violation(path, "matrix", f"{prefix} 为空")] if strict else []
    cols = MATRIX_COLS[kind]
    found = None
    for header, rows in parse_tables(body):
        if all(c in header for c in cols):
            found = (header, rows)
            break
    if found is None:
        return [Violation(path, "matrix", f"{prefix} 未找到列齐的 {kind} 矩阵（需 {cols}）")]
    header, rows = found
    idx = {c: header.index(c) for c in cols}
    out = []
    defined = {r["编号"] for r in refs}
    for n, cells in enumerate(rows, 1):
        cells = cells + [""] * (len(header) - len(cells))
        row = {c: cells[idx[c]] for c in cols}
        cited = CITE_RE.findall(row["代表文献"])
        if not cited:
            out.append(Violation(path, "matrix-ref", f"{kind} 第 {n} 行无代表文献"))
        for rid in cited:
            if defined and rid not in defined:
                out.append(Violation(path, "matrix-ref", f"{kind} 第 {n} 行引用未定义 {rid}"))
        if kind in ("AED", "AGC", "SER") and row["档位"] not in TIERS:
            out.append(Violation(path, "matrix-tier",
                                 f"{kind} 第 {n} 行档位 {row['档位']!r} 非法"))
        lim = row[LIMIT_COL[kind]]
        if len(lim) < 4 or not re.search(r"[（(]", lim):
            out.append(Violation(path, "matrix-condition",
                                 f"{kind} 第 {n} 行条件列不足：{lim!r}"))
        for flag in ("端侧", "多模态"):
            if flag in row and not row[flag]:
                out.append(Violation(path, "matrix-flag", f"{kind} 第 {n} 行 {flag} 为空"))
    if strict and len(rows) < min_rows:
        out.append(Violation(path, "matrix-count", f"{kind} 矩阵 {len(rows)} 行 < {min_rows}"))
    tiers = set()
    if kind in ("AED", "AGC", "SER"):
        for cells in rows:
            cells = cells + [""] * (len(header) - len(cells))
            tiers.add(cells[idx["档位"]])
    if kind in ("AED", "AGC") and strict:
        missing = {"小型", "中型", "大型"} - tiers
        if missing:
            out.append(Violation(path, "matrix-tier-cover",
                                 f"{kind} 缺档位 {sorted(missing)}"))
    if kind == "AGC" and strict and "经典DSP" not in tiers:
        out.append(Violation(path, "matrix-dsp", "AGC 矩阵缺经典DSP档"))
    return out


def check_metric_conditions(path, text):
    out = []
    for header, rows in parse_tables(text):
        if "编号" in header and "链接" in header:
            continue
        for n, cells in enumerate(rows, 1):
            joined = " | ".join(cells)
            if METRIC_RE.search(joined) and not re.search(r"[（(]", joined):
                out.append(Violation(path, "metric-condition",
                                     f"表第 {n} 行含指标但无条件括号：{joined[:80]!r}"))
    return out


def check_future_work(path, sections, refs, strict):
    head, body = find_section(sections, "## 8.")
    if head is None:
        return [Violation(path, "future-work", "缺 §8")] if strict else []
    if not body.strip():
        return [Violation(path, "future-work", "§8 为空")] if strict else []
    items = [ln for ln in body.splitlines() if re.match(r"^\d+\.\s", ln)]
    out = []
    if strict and len(items) < 5:
        out.append(Violation(path, "future-work", f"未来方向 {len(items)} 条 < 5"))
    for ln in items:
        if not CITE_RE.search(ln):
            out.append(Violation(path, "future-work-ref", f"未来方向无出处：{ln[:60]!r}"))
        if "局限" not in ln:
            out.append(Violation(path, "future-work-basis",
                                 f"未来方向未追溯到局限：{ln[:60]!r}"))
    return out


def check_unverified(path, sections, refs):
    out = []
    levels = {r["编号"]: r["核验层级"] for r in refs}
    if not levels:
        return out
    for head, body in sections.items():
        if head.startswith("## 9."):
            continue
        if "[未核实]" in body:
            out.append(Violation(path, "unverified-leak",
                                 f"{head} 含 [未核实] 标记，应移入 §9"))
        cited = CITE_RE.findall(body)
        weak = [rid for rid in cited if levels.get(rid) in ("摘要", "二手")]
        if weak and not re.search(r"摘要口径|二手口径", body):
            out.append(Violation(path, "abstract-qualifier",
                                 f"{head} 引用 {sorted(set(weak))} 但未声明摘要/二手口径"))
    return out
```

- [ ] **Step 5: 追加证据附录规则、`run_checks` 与 CLI**

在 `scripts/check_survey.py` 末尾追加：

```python
CARD_HEAD_RE = re.compile(r"^### \[(S\d{2})\].*$", re.M)


def parse_cards(text):
    matches = list(CARD_HEAD_RE.finditer(text))
    out = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1)] = text[m.end():end]
    return out


def check_evidence(path, text, refs, strict):
    sections = split_h2(text)
    out = []
    if strict:
        for sec in EVIDENCE_SECTIONS:
            if find_section(sections, sec)[0] is None:
                out.append(Violation(path, "evidence-section", f"缺小节 {sec}"))

    head, body = find_section(sections, "## 2.")
    if head is not None and body.strip():
        found = False
        for header, rows in parse_tables(body):
            if all(c in header for c in ("检索日", "库/通道", "检索式", "年份窗", "命中")):
                found = True
                for n, cells in enumerate(rows, 1):
                    if len(cells) < 6 or any(not c.strip() for c in cells[:6]):
                        out.append(Violation(path, "search-log", f"检索日志第 {n} 行有空列"))
        if not found:
            out.append(Violation(path, "search-log", "§2 缺检索日志表"))
    elif strict:
        out.append(Violation(path, "search-log", "§2 检索日志为空"))

    head, body = find_section(sections, "## 3.")
    if head is not None and body.strip():
        found = False
        for header, rows in parse_tables(body):
            if all(c in header for c in ("编号", "文献", "决定", "理由")):
                found = True
                iv = header.index("决定")
                rv = header.index("理由")
                for n, cells in enumerate(rows, 1):
                    cells = cells + [""] * (len(header) - len(cells))
                    dec, reason = cells[iv].strip(), cells[rv].strip()
                    if dec not in ("纳入", "排除"):
                        out.append(Violation(path, "screen-decision",
                                             f"筛选第 {n} 行决定 {dec!r} 非法"))
                    if len(reason) < 4 or reason == "不相关":
                        out.append(Violation(path, "screen-reason",
                                             f"筛选第 {n} 行理由不足：{reason!r}"))
        if not found:
            out.append(Violation(path, "screen-table", "§3 缺筛选表"))
    elif strict:
        out.append(Violation(path, "screen-table", "§3 筛选表为空"))

    head, body = find_section(sections, "## 4.")
    if head is not None and body.strip():
        cards = parse_cards(body)
        for rid, block in cards.items():
            for field in CARD_FIELDS:
                m = re.search(rf"^- {field}：(.+)$", block, re.M)
                if not m or len(m.group(1).strip()) < 2:
                    out.append(Violation(path, "card-field", f"[{rid}] 缺字段 {field}"))
        if strict:
            for r in refs:
                if r["编号"] not in cards:
                    out.append(Violation(path, "card-missing", f"缺单篇卡片 [{r['编号']}]"))
    elif strict:
        out.append(Violation(path, "card-missing", "§4 单篇卡片为空"))

    head, body = find_section(sections, "## 5.")
    if head is not None and body.strip():
        found = False
        cols = ("小节", "回答的问题", "为什么这几篇放在一起", "读者带走的一句判断", "代表文献")
        for header, rows in parse_tables(body):
            if all(c in header for c in cols):
                found = True
                idx = {c: header.index(c) for c in cols}
                defined = {r["编号"] for r in refs}
                covered = set()
                outline_sections = []
                for n, cells in enumerate(rows, 1):
                    cells = cells + [""] * (len(header) - len(cells))
                    row = {c: cells[idx[c]] for c in cols}
                    outline_sections.append(row["小节"])
                    if any(len(row[c]) < 2 for c in cols):
                        out.append(Violation(path, "outline-cell",
                                             f"大纲第 {n} 行有空列"))
                    cited = CITE_RE.findall(row["代表文献"])
                    if not cited:
                        out.append(Violation(path, "outline-ref",
                                             f"大纲第 {n} 行无代表文献"))
                    for rid in cited:
                        if defined and rid not in defined:
                            out.append(Violation(path, "outline-ref",
                                                 f"大纲第 {n} 行引用未定义 {rid}"))
                    covered.update(cited)
                if strict:
                    missing = {r["编号"] for r in refs} - covered
                    if missing:
                        out.append(Violation(path, "outline-coverage",
                                             f"未被大纲覆盖的文献：{sorted(missing)}"))
                    for num in range(3, 9):
                        if not any(re.match(rf"^§{num}", sec) for sec in outline_sections):
                            out.append(Violation(path, "outline-sections",
                                                 f"大纲缺 §{num} 的小节行"))
        if not found:
            out.append(Violation(path, "outline-table", "§5 缺叙事大纲表"))
    elif strict:
        out.append(Violation(path, "outline-table", "§5 叙事大纲为空"))

    return out


def run_checks(survey_path, survey_text, evidence_path, evidence_text, strict=False):
    sections = split_h2(survey_text)
    out = []
    if strict:
        for sec in SURVEY_SECTIONS:
            if find_section(sections, sec)[0] is None:
                out.append(Violation(survey_path, "survey-section", f"缺小节 {sec}"))
    refs, ref_errs = parse_refs(survey_path, sections.get("## 10. 参考文献", ""), strict)
    out.extend(ref_errs)
    if refs:
        out.extend(check_refs(survey_path, refs))
        body = survey_text.split("## 10.")[0]
        out.extend(check_citations(survey_path, body, refs, strict))
    for prefix, (kind, min_rows) in SECTION_MATRIX.items():
        out.extend(check_matrix(survey_path, sections, prefix, kind,
                                min_rows, refs, strict))
    out.extend(check_metric_conditions(survey_path, survey_text))
    out.extend(check_future_work(survey_path, sections, refs, strict))
    out.extend(check_unverified(survey_path, sections, refs))
    out.extend(check_evidence(evidence_path, evidence_text, refs, strict))
    return out


def selftest():
    """用内联最小样例验证核心规则；细节由 tests/test_check_survey.py 覆盖。"""
    survey = """# t
## 1. 摘要与结论
本文纳入 1 篇文献。[S01]

## 10. 参考文献
| 编号 | 文献 | 年份 | 发表 venue | 链接 | 核验层级 | 局限 |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | T | 2024 | V | https://x | 全文 | 仅原型验证（n=1） |
"""
    evidence = """# e
## 2. 检索日志
| 检索日 | 库/通道 | 检索式 | 年份窗 | 命中 | 纳入候选 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | corpus | q | 2017-2026 | 1 | 1 |
"""
    bad = survey.replace("https://x", "http://x")
    cases = [
        ("good", run_checks("s", survey, "e", evidence), 0),
        ("bad-url", run_checks("s", bad, "e", evidence), 1),
    ]
    ok = True
    for name, vs, want in cases:
        got = 1 if vs else 0
        if got != want:
            print(f"!! selftest {name}: want {want}, got {got}: {vs}")
            ok = False
    print("selftest:", "ok" if ok else "FAILED")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="校验综述正文与证据附录")
    ap.add_argument("files", nargs="*", type=Path)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if len(args.files) != 2:
        ap.error("需要 SURVEY.md 与 EVIDENCE.md 两个文件")
    survey_path, evidence_path = args.files
    for p in (survey_path, evidence_path):
        if not p.exists():
            print(f"!! 文件不存在: {p}")
            return 1
    vs = run_checks(str(survey_path), survey_path.read_text(encoding="utf-8"),
                    str(evidence_path), evidence_path.read_text(encoding="utf-8"),
                    strict=args.strict)
    for v in vs:
        print(v)
    print(f"\n检查 2 个文件；违规 {len(vs)} 条")
    return 1 if vs else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: 运行全部测试**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_check_survey -v
```

Expected: `Ran 15 tests` + `OK`（Fix round 1 增补 2 个严格门禁回归测试；Task 3 增补 1 个 `纳入 Sxx` 回归测试）。

- [ ] **Step 7: 运行 CLI 自检**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py --selftest
```

Expected: `selftest: ok`，退出码 0。

- [ ] **Step 8: 提交**

```bash
git add scripts/check_survey.py tests/test_check_survey.py
git commit -m "feat(research): 综述校验器——引用/条件/未核实/证据附录五组不变量（纯 stdlib + 15 测试）"
```

---

### Task 2: S0 范围合同与空骨架

**Files:**
- Create: `docs/research/2026-10-18-audio-agentos-survey.md`
- Create: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`
- Test: `scripts/check_survey.py`（非严格模式）

**Interfaces:**
- Consumes: Task 1 的 CLI。
- Produces: 两份文档骨架；证据 §1 的六大证据基座计数（SER 46 / AED 58 / AGC 35+3 / 全天候学术 41 / AgentOS 窄分支 49 / 语料 123,271 元数据 + 147 个 PDF（索引口径 115 篇））。

- [ ] **Step 1: 建正文空骨架（只有十个 H2，标题逐字照抄 File Structure 段）**

正文首行写：

```markdown
# 音频智能体技术综述：AgentOS、多模态、全天候录音、声学情感、音频事件与自动增益（2017–2026）

> 综述方法：LitReview S0–S8（`docs/research/2026-10-18-litreview-skill-workflow.md`）。
> 证据等级：见 §2.3；未核实内容统一在 §9。
```

十个 `##` 小节全部保留，正文暂空。

- [ ] **Step 2: 写证据附录 §1 范围合同**

必须逐项写全，不得用“等”省略：

```markdown
## 1. 范围合同

### 1.1 主题与核心问题
- 主题：音频智能体（agentic audio）在端侧/边缘的可用技术栈。
- Q1：AgentOS 语境下，音频是“传感器 + 动作面”还是独立能力？已有系统把它放在哪一层？
- Q2：全天候录音的产品与学术证据，对端侧音频栈给出哪些硬约束（功耗/触发/留存）？
- Q3：多模态（音+视）在 SER/AED/AGC 三个任务里，真实增量与合规代价各是什么？
- Q4：AED 的端侧/多模态/大中小如何拆成可比较维度？每档的代表系统与硬数字是什么？
- Q5：AGC 的模型化边界在哪？经典 DSP、神经增强、多模态各自解决什么问题？

### 1.2 时间窗与读者
- 检索窗：2017-01-01 至 2026-10-18；重点 2023–2026。
- 读者：laos/nanoLAOS 的技术评审与路线评审；默认读者懂 Python 与端侧部署，不默认懂音频领域。
- 交付物：综述正文 + 证据附录 + 机器校验器；不交付 benchmark 重跑与产品选型报价。

### 1.3 纳入标准
- 同行评审论文、arXiv 预印本、官方技术报告/挑战赛榜单、可核验的开源权重仓库。
- 与六个领域之一直接相关，且至少满足一条：给出参数量/算力/延迟/功耗；给出可复现指标与条件；给出端侧部署证据；给出合规/社会接受度实证。

### 1.4 排除标准
- 纯音乐生成、纯语音识别（不涉及情感/事件/增益/常驻采集）、纯视觉、纯 NLP。
- 只有营销口径没有可核数字的产品稿；无法定位原文的二手转述（除非作为“二手”证据并标注）。
- 与端侧/常驻/治理无关的纯云端大模型榜单。

### 1.5 这篇综述不写什么
- 不对 123,271 条 venue 元数据做全量全文精读（`docs/research/papers/` 147 个 PDF，索引口径 115 篇）。
- 不重跑任何 benchmark；所有数字均为原文/官方榜单口径，并附条件。
- 不做临床有效性、法律合规意见或采购建议。

### 1.6 证据基座（开工前盘点）
| 基座 | 数量 | 位置 | 用途 |
| --- | --- | --- | --- |
| SER 记录 | 46 条 | `docs/research/speech-emotion/` | §4 主证据 |
| AED 记录 | 58 条 | `docs/research/audio-events/` | §5 主证据 |
| AGC 记录 | 35 条 schema 记录（另 3 条多模态） | `docs/research/auto-gain/` | §6 主证据 |
| 全天候录音学术线 | 41 篇（六表数据行实计） | `docs/research/always-on-recording/academic-papers.md` | §3 约束 |
| AgentOS 窄分支 | 49 篇 | `docs/research/2026-10-07-agentos-governance-literature.md` | §3 分层 |
| venue 元数据 | 123,271 条 | `corpus/venue_expansion/*.jsonl` | 补检候选 |
| 论文 PDF | 147 个 PDF（索引口径 115 篇） | `docs/research/papers/` + `docs/research/papers_index.md` | 全文核验 |
```

- [ ] **Step 3: 核对基座计数**

Run:

```bash
grep -n "46 条\|58 条\|48 条\|47 篇\|49 篇" docs/research/speech-emotion/2026-09-landscape.md docs/research/audio-events/2026-09-landscape.md docs/research/auto-gain/2026-09-landscape.md docs/research/always-on-recording/academic-papers.md docs/research/2026-10-07-agentos-governance-literature.md
```

Expected: 五个数字各至少命中一次；若某个数字与文件不符，以文件原文为准改写 §1.6，不得保留旧数。

- [ ] **Step 4: 跑非严格校验**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`（空小节与空参考文献表在非严格模式跳过）。

- [ ] **Step 5: 提交**

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 音频智能体综述 S0——范围合同与证据基座盘点"
```

---

### Task 3: S1/S2 检索日志与筛选台账

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§2、§3）
- Temp: `var/litreview/`（gitignored）

**Interfaces:**
- Consumes: Task 2 的 §1 纳入/排除标准。
- Produces: 候选编号 `C001…`；纳入编号 `S01…`（按“领域顺序 + 年份倒序”分配）；§3 的纳入/排除决定。后续 Task 的卡片/大纲/参考文献只使用这些 `Sxx`。

- [ ] **Step 1: 建临时目录并跑六条本地语料查询**

Run:

```bash
mkdir -p var/litreview
export PYTHONIOENCODING=utf-8
P=C:/Users/yaoyue/miniconda3/python.exe
$P scripts/query_corpus.py --topic audio-speech --strong-only --grep "audio event|sound event|acoustic event|DCASE" --limit 0 --json > var/litreview/corpus_aed.jsonl
$P scripts/query_corpus.py --topic audio-speech --strong-only --grep "automatic gain|gain control|AGC|dynamic range|loudness" --limit 0 --json > var/litreview/corpus_agc.jsonl
$P scripts/query_corpus.py --topic audio-speech --strong-only --grep "emotion|affect|valence|arousal" --limit 0 --json > var/litreview/corpus_ser.jsonl
$P scripts/query_corpus.py --topic spatial-privacy --strong-only --grep "always-on|wearable|continuous|lifelog|lifelogging|recording" --limit 0 --json > var/litreview/corpus_alwayson.jsonl
$P scripts/query_corpus.py --topic agent-os --strong-only --limit 0 --json > var/litreview/corpus_agentos.jsonl
$P scripts/query_corpus.py --topic audio-speech --strong-only --grep "multimodal|multi-modal|audio-visual|audiovisual" --limit 0 --json > var/litreview/corpus_multimodal.jsonl
wc -l var/litreview/corpus_*.jsonl
```

Expected（2026-10-18 实测基线，允许因语料更新而增加）：`corpus_aed 2`、`corpus_agc 15`、`corpus_ser 49`、`corpus_alwayson 5`、`corpus_agentos 49`、`corpus_multimodal 87`。若某条为 0，把检索式放宽一次并如实记录两次命中数。

- [ ] **Step 2: 跑六条 arXiv 查询**

Run:

```bash
for q in \
  'abs:"agent operating system" AND (abs:audio OR abs:speech)' \
  'abs:"always-on" AND abs:audio AND abs:recording' \
  'abs:"sound event detection" AND abs:"on-device"' \
  'abs:"automatic gain control" AND abs:audio' \
  'abs:"speech emotion recognition" AND abs:"on-device"' \
  'abs:"audio-visual" AND abs:"sound event"'; do
  name=$(echo "$q" | md5sum | cut -c1-8)
  curl -sG "https://export.arxiv.org/api/query" \
    --data-urlencode "search_query=$q" \
    --data-urlencode "start=0" --data-urlencode "max_results=100" \
    -o "var/litreview/arxiv_$name.xml"
done
grep -c "<entry>" var/litreview/arxiv_*.xml
```

Expected: 每个文件命中 0–100 条；`<entry>` 计数写入 §2。若 curl 失败（网关/证书），记录 `HTTP/证书错误 + 日期`，不重试超过 3 次，继续用本地语料与既有调研。

- [ ] **Step 3: 把 arXiv 命中转成候选 TSV**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import glob, re, xml.etree.ElementTree as ET, csv
ns = {"a": "http://www.w3.org/2005/Atom"}
rows = []
for path in sorted(glob.glob("var/litreview/arxiv_*.xml")):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        continue
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        summary = " ".join((e.findtext("a:summary", "", ns) or "").split())
        link = e.findtext("a:id", "", ns)
        pub = e.findtext("a:published", "", ns)[:10]
        rows.append([path, pub, title, link, summary])
with open("var/litreview/arxiv_candidates.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    w.writerow(["source", "published", "title", "url", "abstract"])
    w.writerows(rows)
print("candidates:", len(rows))
PY
```

Expected: `candidates: N`，N ≥ 60（六条查询合计；不足则把时间窗放宽到 2015 后再跑一次并记录）。

- [ ] **Step 4: 写 §2 检索日志**

每条查询一行，至少 12 行（6 本地 + 6 arXiv）；列与校验器逐字一致：

```markdown
## 2. 检索日志

| 检索日 | 库/通道 | 检索式 | 年份窗 | 命中 | 纳入候选 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | corpus/audio-speech | audio event\|sound event\|acoustic event\|DCASE | 2017-2026 | 2 | 2 |
```

“命中”填命令实际输出数；“纳入候选”填进入 §3 标题/摘要筛选的条数。检索式里的 `|` 必须转义为 `\|`，否则会撑破表格。

- [ ] **Step 5: 写 §3 筛选台账（先 40 条，再补齐到 ≥100）**

列与校验器逐字一致：

```markdown
## 3. 筛选与排除

| 编号 | 文献 | 年份 | 决定 | 理由 |
| --- | --- | --- | --- | --- |
| C001 | YAMNet: ... | 纳入 S01 | 端侧 TFLite Micro 证据 + AudioSet full mAP |
| C002 | ... | 排除 | 纯云端 ASR，无事件/情感/增益/常驻维度 |
```

理由必须写到维度（端侧证据/指标条件/常驻约束/合规/多模态），不得只写“不相关”。每条纳入行在“决定”列写 `纳入 Sxx`，并与 §4 卡片编号一致。

- [ ] **Step 6: 补齐到 ≥100 条候选、≥80 条纳入**

从三个领域文档的表格逐行取候选：SER 46 + AED 58 + AGC 35+3 中先各取约 30，再补全天候 41 与 AgentOS 49 中的相关条目。允许一个领域多取，但最终 §3 的纳入集合必须覆盖 §4 卡片、§5 大纲、§10 参考文献三处的编号。

Run:

```bash
grep -c '^| C' docs/research/2026-10-18-audio-agentos-survey-evidence.md
grep -c '^| C.*| 纳入 S' docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: 第一行 ≥100；第二行 ≥80。

- [ ] **Step 7: 跑非严格校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`。

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 综述 S1/S2——12 条检索日志 + 100 候选筛选台账（80 纳入）"
```

---

### Task 4: S3 单篇卡片

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§4）

**Interfaces:**
- Consumes: Task 3 的 `S01…S80` 纳入集合。
- Produces: 每篇一个 `### [Sxx]` 卡片，六字段齐全；后续 §5 大纲与 §10 参考文献的“局限”字段从这里抄录。

- [ ] **Step 1: 写卡片模板与第一批（S01–S20：AgentOS/全天候/多模态）**

每张卡片严格六行（字段名逐字一致）：

```markdown
### [S01] 论文标题
- 问题：这篇论文要回答什么。
- 方法：模型/系统/研究设计。
- 数据：数据集、规模、语言、采集条件。
- 指标与条件：指标名 + 数值 + 数据集/划分/硬件/延迟条件。
- 局限：作者承认的 + 本文核对发现的限制。
- 对话：与哪几篇构成“能力→失效 / 方法→代价 / 结论→反例”。
```

- [ ] **Step 2: 第二批（S21–S40：SER + AED 小型/中型）**

SER 优先覆盖 `YAMNet`、`openSMILE ComParE_2016`、`TRILLsson`、`emotion2vec+`、`SenseVoice`、`Qwen2-Audio-7B`；AED 优先覆盖 `YAMNet`、`EfficientAT-mn04/mn10/mn20`、`PANNs-CNN14`、`AST`、`PaSST-S`、`BEATs iter3+`、`EAT-base`、`CED-Base`。每条数字从对应领域文档的表格行抄录，条件列原样保留。

- [ ] **Step 3: 第三批（S41–S60：AED 大型 + AGC 全档）**

AED 大型覆盖 `Dasheng-0.6B/1.2B`、`Qwen2-Audio-7B-Instruct`、`Audio Flamingo 3`、`Kimi-Audio-7B-Instruct`、`DASM`、`LAION-CLAP`；AGC 覆盖 `WebRTC AGC2`、`SpeexDSP AGC`、`FFmpeg loudnorm`、`Android AutomaticGainControl`、`RNNoise`、`GTCRN`、`DeepFilterNet3`、`MossFormer2`、`Miipher-2`、`UNIVERSE++`。AGC 相邻领域条目（如 AVSE）在“局限”里注明 `非AGC(相邻：增强)` 的收录理由。

- [ ] **Step 4: 第四批（S61–S80：全天候/端侧/补充）**

覆盖 `Silero VAD`（若作为官方仓库条目）、`DCASE Low-Complexity` 基线、`Ego4D`、`Ego-Exo4D`、`EgoADL`、`EgoLog`、`Apple Watch S12`（二手）、`Rewind/Limitless`（二手，产品史）、`QNN/ONNX/TFLite` 端侧证据（表格核实）。二手条目必须在卡片“指标与条件”里写“二手口径”。

- [ ] **Step 5: 校对卡片与筛选台账一致**

Run:

```bash
grep -c '^### \[S' docs/research/2026-10-18-audio-agentos-survey-evidence.md
grep -c '^| C.*| 纳入 S' docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: 两个数字相等，且 ≥80。

- [ ] **Step 6: 跑校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`。

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 综述 S3——80 篇六字段卡片（问题/方法/数据/指标条件/局限/对话）"
```

---

### Task 5: S5 叙事大纲

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§5）

**Interfaces:**
- Consumes: Task 4 的卡片与 `Sxx` 编号。
- Produces: §5 大纲表；每行 = 正文一个 H3；`代表文献` 覆盖全部 80 篇。

- [ ] **Step 1: 写大纲表头与 §2–§3 行**

表头逐字一致：

```markdown
## 5. 叙事大纲

| 小节 | 回答的问题 | 为什么这几篇放在一起 | 读者带走的一句判断 | 代表文献 |
| --- | --- | --- | --- | --- |
```

先写 §2 的 3 行（2.1 六领域与维度 / 2.2 检索与筛选 / 2.3 证据等级与可比规则）与 §3 的 4 行（3.1 AgentOS / 3.2 全天候 / 3.3 多模态 / 3.4 应用矩阵）。“为什么放在一起”必须写成关系词：`能力→失效`、`方法→代价`、`结论→反例`、`同任务不同条件`，不得写“都相关”。

- [ ] **Step 2: 写 §4–§6 行**

- §4：4.1 任务/指标陷阱；4.2 三档规模与端侧；4.3 多模态 SER 增量；4.4 SER 矩阵判断。
- §5：5.1 维度拆解；5.2 小型档 DCASE；5.3 中型档甜点；5.4 大型档开放词表；5.5 端侧 runtime；5.6 多模态定位；5.7 AED 矩阵判断。
- §6：6.1 经典 DSP 档；6.2 三档模型；6.3 端侧延迟/功耗；6.4 多模态 AGC（非空但薄）；6.5 AGC 矩阵判断。

- [ ] **Step 3: 写 §7–§8 行**

§7 至少 3 行：7.1 跨领域指标可比性；7.2 端侧预算的三种语言（mW/ms/MB）；7.3 多模态的三种结局（有增量/薄/默认不做）。§8 至少 1 行总览，指向 6 条未来方向。

- [ ] **Step 4: 核对覆盖**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import re
p = "docs/research/2026-10-18-audio-agentos-survey-evidence.md"
t = open(p, encoding="utf-8").read()
outline = t.split("## 5. 叙事大纲")[1].split("## 6.")[0]
cards = set(re.findall(r"^### \[(S\d{2})\]", t, re.M))
covered = set(re.findall(r"\[(S\d{2})\]", outline))
print("cards", len(cards), "covered", len(covered), "missing", sorted(cards - covered))
PY
```

Expected: `missing []`；若不为空，把缺失文献补进对应小节行。

- [ ] **Step 5: 跑校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`。

```bash
git add docs/research/2026-10-18-audio-agentos-survey-evidence.md
git commit -m "docs(research): 综述 S5——叙事大纲（每节回答什么 + 为什么这几篇放在一起）"
```

---

### Task 6: 正文 §1–§3（摘要、方法、应用侧图景）

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§1–§3）

**Interfaces:**
- Consumes: 证据 §1–§5；`Sxx` 编号。
- Produces: 正文 §1–§3；§3 应用矩阵（≥8 行）。

- [ ] **Step 1: 写 §1 摘要与结论**

必须包含：
1. “纳入 N 篇”（N = 最终参考文献行数，写作时先按 80 占位，Task 9 核对）。
2. 六条结论，每条一句话：维度拆解、AED 三档结论、AGC 经典 DSP 为主、SER 辅助定位、多模态三种结局、全天候约束。
3. 一句边界声明：语料是元数据+领域表格核实，不是全量全文精读。

- [ ] **Step 2: 写 §2 范围、检索与筛选方法**

三个 H3：
- 2.1 六领域与两个分类维度：解释“五类不平行”，给出 `规模主键 + edge/multimodal 标记`，AED 加任务类型，AGC 加经典 DSP 与作用点。
- 2.2 检索与筛选：本地 123,271 元数据、6 条 corpus 查询、6 条 arXiv 查询、筛选 ≥100 候选纳入 ≥80；引用证据 §2/§3。
- 2.3 证据等级与可比规则：四种核验层级；跨任务类型不可比；AudioSet 划分；数字必须带条件。

- [ ] **Step 3: 写 §3.1–§3.3**

- 3.1 AgentOS：说明“AgentOS 名号八种含义、无内核级音频层”；音频在现有系统里是工具调用/传感器，不是调度对象；引 AgentOS 窄分支与 STEPX Neo（二手）作为商业印证。
- 3.2 全天候录音：产品史（纯常开全灭）→ 端侧克制常开；三条硬约束：触发方式、功耗阶梯（定制 ASIC 亚微瓦 → AP 数百 mW）、留存/即焚。
- 3.3 多模态：音频为主、视觉为例外；SER/AED 的视觉增量与合规否决；写出“默认永久不做”的翻转条件（需同时满足法律与产品定位）。

- [ ] **Step 4: 写 §3.4 应用矩阵（≥8 行）**

表头逐字一致：

```markdown
| 应用/系统 | 形态 | 处理位置 | 触发方式 | 音频角色 | 代表文献 | 可借鉴点 | 限制（含部署/合规条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

至少覆盖：AIOS/AgentOS 类、STEPX Neo、Rewind/Limitless、Apple Watch S12、Ego4D/Ego-Exo4D、EgoADL/EgoLog、Silero VAD 管道、laos 四段漏斗（可用仓库文档作“系统”行，代表文献引对应卡片）。

- [ ] **Step 5: 跑校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`（§4–§6 仍空，非严格模式跳过）。

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 §1–§3——方法、维度拆解与应用侧图景"
```

---

### Task 7: 正文 §4–§6（SER / AED / AGC 三张矩阵）

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§4–§6）

**Interfaces:**
- Consumes: 证据 §4 卡片、§5 大纲；领域文档 `speech-emotion/`、`audio-events/`、`auto-gain/`。
- Produces: SER 矩阵 ≥10 行、AED 矩阵 ≥15 行、AGC 矩阵 ≥12 行；每行 `代表文献` + `限制（含实验条件）`。

- [ ] **Step 1: 写 §4 SER（4.1–4.4 + 矩阵 ≥10 行）**

矩阵表头逐字一致：

```markdown
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

必须覆盖三档：小型 `YAMNet` / `openSMILE` / `TRILLsson`；中型 `wav2vec 2.0` / `emotion2vec+` / `SenseVoice`；大型 `Qwen2-Audio-7B` / `SALMONN` / `Emotion-LLaMA`。`端侧`/`多模态` 列只能填 `是`/`否`/`部分`/`unknown`。限制必须带条件括号，例如 `仅在 IEMOCAP（4 类，WA）`。

- [ ] **Step 2: 写 §5.1 维度拆解**

必须写出：
- 五类不平行：规模互斥；edge 是能力标记；multimodal 是输入标记。
- AED 的第四维：`tagging`/`SED`/`ASC`/`开放词表`，跨任务指标不可比。
- AudioSet AS-20K vs AS-2M full 可差 15+ 点。

- [ ] **Step 3: 写 §5.2–§5.6**

- 5.2 小型档：DCASE Low-Complexity 是端侧事实标准；128 KiB 口径（fp32 32,768 参数）；准确率窄带 60.8→62.7→62.1→61.5，无趋势性提升。
- 5.3 中型档：AST/PaSST-S/BEATs/EAT 是精度甜点；同模型双报时主表记 full。
- 5.4 大型档：开放词表的代价；区分纯判别/端到端音频大模型/两段式；DASM 的 42.2 是 PSDS1 不是 mAP。
- 5.5 端侧：B 档（proot 通用 CPU）400–1000 mW 常驻税 vs ≤25 mW 预算 → 不做常驻 AED，只做事件驱动。
- 5.6 多模态：视觉的真正增量是事件定位而非分类；隐私/合规成本使视觉不进常驻链路。

- [ ] **Step 4: 写 §5.7 AED 矩阵（≥15 行）**

表头逐字一致：

```markdown
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 任务类型 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

至少 5 行小型、5 行中型、3 行大型，另加 2 行端侧/多模态交叉。`任务类型` 只能取四值之一。

- [ ] **Step 5: 写 §6.1–§6.4**

- 6.1 经典 DSP 档：WebRTC AGC1/AGC2、SpeexDSP、ffmpeg loudnorm/dynaudnorm、Android AGC；闭环指标是收敛时间/稳态误差/增益波动，不是 mAP。
- 6.2 三档模型：AGC 专用神经模型几乎全部是“增强+增益”联合；纯 AGC 神经模型稀缺；相邻领域必须标 `非AGC(相邻：…)`。
- 6.3 端侧：采集前层第三方 App 通常改不了；采集后层是唯一可选层，且要防“二次增益”。
- 6.4 多模态：判定为“非空但薄”；AVSE 类工作算相邻领域；没有证据支持常驻多模态 AGC。

- [ ] **Step 6: 写 §6.5 AGC 矩阵（≥12 行）**

表头逐字一致：

```markdown
| 模型 | 档位 | 参数量(M) | 作用点 | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

必须含 `经典DSP` 行（`参数量(M)` 写 `n/a(非神经)`）；`作用点` 只能取 `采集前/采集后/播放前/离线`；至少 2 行 `非AGC(相邻：增强)` 并在限制列写收录理由。

- [ ] **Step 7: 跑校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`。

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 §4–§6——SER/AED/AGC 三张条件化矩阵与维度拆解"
```

---

### Task 8: 正文 §7–§9（跨领域对比、未来方向、局限）

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§7–§9）

**Interfaces:**
- Consumes: §4–§6 矩阵；证据 §7 未核实清单。
- Produces: 跨领域矩阵 ≥5 行；未来方向 ≥5 条（每条含 `[Sxx]` 与“局限”）；§9 与证据 §7 一一对应。

- [ ] **Step 1: 写 §7 跨领域对比（≥5 行）**

表头逐字一致：

```markdown
| 领域 | 规模分档依据 | 端侧判定依据 | 多模态现状 | 可比指标 | 不可比陷阱 | 代表文献 |
| --- | --- | --- | --- | --- | --- | --- |
```

至少 5 行（SER/AED/AGC/全天候/AgentOS）；“不可比陷阱”要具体到口径（AS-20K vs full、mAP vs PSDS、UAR vs WA、dB vs LUFS、mW vs ms）。

- [ ] **Step 2: 写 §8 未来方向（≥5 条）**

每条格式固定：

```markdown
1. **方向名**：做法 + 验收口径（源于 [Sxx] 的局限：……）。
```

六条建议：中文场景 AED 评测；端侧多模态的事件定位（带合规前置）；AGC 的采集前/后分层测量；SER 的跨语料泛化；音频智能体的 syscall/治理接口；常驻链路的功耗-留存联合预算。

- [ ] **Step 3: 写 §9 局限与未核实清单**

三类：
- 语料局限：123,271 条元数据 vs 147 个 PDF（索引口径 115 篇）；无全量全文精读。
- 方法局限：未见 benchmark 重跑；数字来自原文/榜单。
- 未核实清单：逐条抄证据 §7 的 `[Uxx]`，写“影响章节 + 为何未核实 + 读者应如何对待”。

正文其他小节不得出现 `[未核实]` 标记。

- [ ] **Step 4: 跑校验并提交**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`（参考文献表仍空，非严格模式跳过引用检查）。

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md
git commit -m "docs(research): 综述 §7–§9——跨领域可比性、六条未来方向与未核实隔离"
```

---

### Task 9: §10 参考文献、溯源核验、严格门禁与登记

**Files:**
- Modify: `docs/research/2026-10-18-audio-agentos-survey.md`（§10、§1 的 N）
- Modify: `docs/research/2026-10-18-audio-agentos-survey-evidence.md`（§6、§7）
- Modify: `docs/research/INDEX.md`
- Modify: `docs/superpowers/plans/README.md`

**Interfaces:**
- Consumes: 全部 `Sxx` 卡片与大纲。
- Produces: 可解析参考文献表；`--strict` 0 违规；INDEX 与计划状态登记。

- [ ] **Step 1: 写 §10 参考文献表**

表头逐字一致：

```markdown
| 编号 | 文献 | 年份 | 发表 venue | 链接 | 核验层级 | 局限 |
| --- | --- | --- | --- | --- | --- | --- |
```

规则：
- 编号从 `S01` 连续到 `S80`（或实际纳入数），不得跳号。
- `年份` 四位；`链接` 必须 `https://`；`核验层级` 四值之一；`局限` ≥4 字且具体。
- 每行 `文献` 建议用“短标题（作者/系统名）”，与卡片标题一致。
- 摘要级/二手指向的小节，必须在对应 §3–§7 增加“本节含摘要口径：Sxx”声明。

- [ ] **Step 2: 写证据 §6 溯源核验记录**

至少三类行：
- URL 可达性：对全部 `Sxx` 链接跑探测，记录 `200/403/timeout`。
- 数字抽样复核：每个领域抽 5 条，回原文表格/官方榜单核对，记录“一致/修正”。
- 口径复核：AudioSet 划分、AGC 作用点、SER 类别数三项逐条核对。

跑 URL 探测：

```bash
C:/Users/yaoyue/miniconda3/python.exe - <<'PY'
import re, urllib.request, ssl
p = "docs/research/2026-10-18-audio-agentos-survey.md"
text = open(p, encoding="utf-8").read()
refs = re.findall(r"\| (S\d{2}) \|.*?\| (https://[^ |]+)", text)
ctx = ssl.create_default_context()
for rid, url in refs:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "laos-survey/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            print(f"{rid}\t{r.status}\t{url}")
    except Exception as e:
        print(f"{rid}\tERR {type(e).__name__}\t{url}")
PY
```

Expected: 每行 `Sxx 200/403/ERR`。把结果写进 §6；`ERR/timeout` 的条目移入 §7 未核实清单或在 §6 注明“链接暂不可达，保留 DOI”。

- [ ] **Step 3: 修正 §1 的纳入数**

Run:

```bash
grep -c '^| S[0-9][0-9] |' docs/research/2026-10-18-audio-agentos-survey.md
```

把 §1 的“纳入 N 篇”改成该数字；校验器会交叉核对。

- [ ] **Step 4: 跑严格门禁**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_survey.py --strict docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md
```

Expected: `违规 0 条`。若报 `outline-coverage`，把缺的编号补进 §5；若报 `card-missing`，补 §4 卡片；若报 `matrix-condition`，补条件括号。

- [ ] **Step 5: 跑领域校验器与单测**

Run:

```bash
C:/Users/yaoyue/miniconda3/python.exe scripts/check_ser_table.py docs/research/speech-emotion/*.md
C:/Users/yaoyue/miniconda3/python.exe scripts/check_aed_table.py docs/research/audio-events/*.md
C:/Users/yaoyue/miniconda3/python.exe scripts/check_agc_table.py docs/research/auto-gain/*.md
C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_check_survey -v
```

Expected: 三个校验器均 `违规 0 条`；单测 `Ran 15 tests` + `OK`。

- [ ] **Step 6: 登记 INDEX 与计划状态**

`docs/research/INDEX.md`：
- 头部总数从 `117 = 115 份资产 + capstone + 本文件` 改为 `119 = 117 份资产 + capstone + 本文件`。
- 在“模型地图支撑卷宗”附近新增两行，一句话定位 + 关键结论（纳入数、三张矩阵、未核实清单）。

`docs/superpowers/plans/README.md`：
- 在状态表末尾新增一行：

```markdown
| 2026-10-18-audio-agentos-litreview-survey.md | 已执行 | 音频智能体综述（LitReview S0–S8）：正文+证据附录+check_survey.py；80 篇纳入、三张条件化矩阵、未核实隔离，strict 0 违规 |
```

执行完成前该行写 `待执行`；Task 9 完成后改 `已执行`。

- [ ] **Step 7: 最终提交**

```bash
git add docs/research/2026-10-18-audio-agentos-survey.md docs/research/2026-10-18-audio-agentos-survey-evidence.md docs/research/INDEX.md docs/superpowers/plans/README.md
git commit -m "docs(research): 音频智能体综述交付——80 篇引用、三张矩阵、strict 门禁 0 违规"
```

---

## 计划自检（写完即跑，非派发）

### 1. Spec 覆盖

| Spec 要求 | 落点 |
|---|---|
| 遍历 AgentOS-audio / multimedia / 全天候录音 | Task 3 检索、Task 6 §3 |
| 声学情感模型 | Task 7 §4 |
| AED：端侧、多模态、大/中/小 | Task 7 §5（3 档 + 2 标记 + 任务类型） |
| AGC：端侧、多模态、大/中/小 | Task 7 §6（经典 DSP + 3 档 + 2 标记 + 作用点） |
| 用 LitReview 方案写综述 | 证据 §1–§7 对应 S0–S8；正文 §1–§10 |
| 质量经验：论文对话、条件化数字、表先给地图、未来方向有出处、交付完整、未核实隔离 | 校验器规则 `outline-*` / `matrix-condition` / `future-work-*` / `ref-*` / `abstract-qualifier` |
| 语料边界诚实 | Global Constraints + §1.5 + §9 |

### 2. 占位符扫描

- 计划中无 `TBD`、`TODO`、`待补`、`适当处理`、`类似 Task N`。
- 所有命令给出确切路径与预期输出；所有代码块为可直接落盘的完整代码（Task 1 的四段代码已按顺序拼接验证：15 测试全绿 + `--selftest` 通过；其中 2 个是执行期审查补的严格门禁回归测试、1 个是 Task 3 补的 `纳入 Sxx` 回归测试）。

### 3. 类型一致性

- 正文/证据的两套 H2 标题在 File Structure、Task 1 常量、Task 2 骨架、Task 9 校验中逐字一致。
- 矩阵列名在 Task 1 `MATRIX_COLS`、Task 6/7/8 的表头、Global Constraints 中一致。
- 编号形态 `S\d{2}` 贯穿筛选（`纳入 Sxx`）、卡片（`### [Sxx]`）、大纲（`[Sxx]`）、参考文献（`| Sxx |`）与校验器。
- 字段名 `限制（含实验条件）` / `限制（含部署/合规条件）` 在矩阵与校验器中逐字对应。
