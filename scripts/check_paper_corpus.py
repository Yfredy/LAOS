#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""校验 papers_unified.jsonl：schema 完整 / venue 合法 / year 在范围 / 主题非空 / 无占位符。"""
import collections
import io
import json
import os
import re
import sys

P = os.path.join(r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus",
                 "papers_unified.jsonl")
FIELDS = ["venue", "year", "doi_or_id", "title", "authors", "url",
          "abstract", "topics", "has_abstract", "source"]
# 注意：TBD / TODO 也是合法缩写（TBD = Track-Before-Detect，雷达术语；
# ICASSP 里就有 "Unsupervised TBD-MIG Detectors in Nonhomogeneous Clutter"）。
# 因此不能做裸子串匹配，只在「整个标题就是占位符」或「短标题里出现独立占位符词」时判违规。
PLACEHOLDER_ONLY = re.compile(r"[\s\W]*(TBD|TODO|待补|XXX|N/A)[\s\W]*", re.I)
PLACEHOLDER_WORD = re.compile(r"\b(TBD|TODO|XXX|N/A|待补)\b", re.I)
WORD_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")


def has_placeholder(title):
    t = (title or "").strip()
    if not t:
        return False
    if PLACEHOLDER_ONLY.fullmatch(t):
        return True
    # 短标题（≤5 个实词）里出现独立占位符词才算可疑；长标题里的 TBD 多为专业缩写
    if len(WORD_RE.findall(t)) <= 5 and PLACEHOLDER_WORD.search(t):
        return True
    return False


def check(path=P):
    errs, n = [], 0
    venue_ct, topic_ct = collections.Counter(), collections.Counter()
    for i, line in enumerate(io.open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        n += 1
        try:
            r = json.loads(line)
        except Exception as e:
            errs.append("L%d: JSON 解析失败 %s" % (i, e))
            continue
        for f in FIELDS:
            if f not in r:
                errs.append("L%d: 缺字段 %s" % (i, f))
        if r.get("venue") not in ("ICASSP", "Interspeech"):
            errs.append("L%d: 非法 venue %r" % (i, r.get("venue")))
        if not (2021 <= int(r.get("year", 0)) <= 2026):
            errs.append("L%d: year 越界 %r" % (i, r.get("year")))
        if not r.get("title", "").strip():
            errs.append("L%d: 空标题" % i)
        if has_placeholder(r.get("title", "")):
            errs.append("L%d: 标题是占位符 %r" % (i, r.get("title")))
        if r.get("has_abstract") and not r.get("abstract"):
            errs.append("L%d: has_abstract=True 但 abstract 为空" % i)
        if not r.get("has_abstract") and r.get("abstract"):
            errs.append("L%d: has_abstract=False 但有 abstract" % i)
        venue_ct[r.get("venue")] += 1
        for t in r.get("topics") or []:
            topic_ct[t] += 1
    print("总条目 %d" % n)
    print("按 venue:", dict(venue_ct))
    print("按 topic:", dict(topic_ct.most_common()))
    if errs:
        print("\n违规 %d 条（前 20）：" % len(errs))
        for e in errs[:20]:
            print("  " + e)
        return 1
    print("\nPASS：0 违规")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else P))
