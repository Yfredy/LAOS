#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Task 2 Step 3: 引号短语 / topic: 精准补抓。

纪律（2026-09-14 实测）：
  * search 限额 10 次/分钟 -> 每请求间隔 >= 7s（crawl_oss_repos.sleep_between_requests）。
  * 只用 search 端点，不补 core 字段。
  * 单 query 上限 1000 条 -> 每 query 取 1-2 页（按 stars 降序的 top 即可）。
  * 严禁裸关键词全文检索；一律引号短语或 topic: 过滤。

本批 10 个 query（克制）：混合「找回被噪声稀释的 audio-llm/voice-agent 真项目」
与「原 8 个干净切片未覆盖的 topic」（audio-classification / speech-synthesis /
keyword-spotting / voice-ai / sound）。落盘 repos_fetched.jsonl（仅增量）。
"""
import sys, io, os, time, datetime

sys.path.insert(0, r"C:\Users\yaoyue\CodeBuddy\Claw\laos\scripts")
import crawl_oss_repos as m

OUT = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss\repos_fetched.jsonl"

# 引号短语：找回被裸词检索埋没的真音频项目
REFETCH = [
    '"audio language model" in:name,description',
    '"speech emotion recognition" in:name,description',
    '"voice activity detection" in:name,description',
    '"voice agent" in:name,description',
    '"realtime voice" in:name,description',
    # topic: 过滤：原 8 干净切片未覆盖的音频子域（100% 相关，补真实覆盖）
    "topic:audio-classification",
    "topic:speech-synthesis",
    "topic:keyword-spotting",
    "topic:voice-ai",
    "topic:sound",
]

PAGES = 2


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    seen = {}  # crawl_oss_repos.search() 要求 seen 为 dict（按 full_name 去重）
    total = 0
    with io.open(OUT, "w", encoding="utf-8") as f:
        for qi, q in enumerate(REFETCH):
            c, ex = m.search(q, pages=PAGES, out=f, seen=seen)
            total += c
            sys.stdout.write("  q%-2d %-46s +%d 累计%d\n"
                            % (qi, q[:46], c, total))
            sys.stdout.flush()
            time.sleep(m.sleep_between_requests)  # 查询间也限速
    print("DONE 补抓 %d 条（已按 full_name 去重）-> %s" % (total, OUT))


if __name__ == "__main__":
    main()
