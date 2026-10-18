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
