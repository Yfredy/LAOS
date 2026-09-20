#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task 2 驱动：用既有 crawl_oss_repos.search() 做 10 query x 3 页抓取。
不修改既有脚本；仅导入其 search()，把去重后的原始结果落盘到
docs/research/jev/_raw_crawl.jsonl（含噪声，留待 _task2_denoise.py 去噪）。

速率纪律由 crawl_oss_repos 内部保证（页间/query 间各 sleep 7s，约 8.5 req/min < 10）。
"""
import sys, io, os

LAOS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos"
sys.path.insert(0, os.path.join(LAOS, "scripts"))
import crawl_oss_repos as C  # noqa

OUT_DIR = os.path.join(LAOS, "docs", "research", "jev")
os.makedirs(OUT_DIR, exist_ok=True)
RAW = os.path.join(OUT_DIR, "_raw_crawl.jsonl")

# 计划 Task 2 Step 2 的 query 清单（引号短语 + topic 限定）
QUERIES = [
    'jev in:name',
    '"jev" in:description',
    '"typesafe" in:name,description',
    '"system one" decision model',
    '"decision model" in:description',
    'topic:jev',
    'topic:typesafe',
    '"typed decisions"',
    '"non-autoregressive" decision',
    'jev-ultrafast',
]

def main():
    seen = {}
    total = 0
    excluded = 0
    with io.open(RAW, "w", encoding="utf-8") as f:
        for qi, q in enumerate(QUERIES):
            try:
                c, ex = C.search(q, pages=3, out=f, seen=seen, excluded=excluded)
            except Exception as e:
                sys.stderr.write("  q%d EXC %s\n" % (qi, str(e)[:120]))
                c, ex = 0, excluded
            total += c
            excluded = ex
            sys.stdout.write("q%-2d %-44s 累计%5d 剔除归档%d\n" % (qi, q[:44], total, excluded))
            sys.stdout.flush()
    print("DONE unique=%d archived_excluded=%d -> %s" % (total, excluded, RAW))

if __name__ == "__main__":
    main()
