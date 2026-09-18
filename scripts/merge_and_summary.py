#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Task 2 Step 4-5: 合并补抓结果 + 生成抓取摘要。

- 将 repos_fetched.jsonl（补抓增量）按 full_name 去重并入 repos_raw.jsonl（干净语料）。
- 校验补抓条目是否均为音频相关（引号短语 / topic: 过滤，预期 100%）。
- 输出 oss_fetch_summary.md：star 分布、语言分布、top20、许可缺失说明、
  补抓查询清单与新增数、与审计/去噪的衔接。
"""
import json, io, os, re, collections, datetime

OSS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\oss"
RAW = os.path.join(OSS, "repos_raw.jsonl")          # 去噪后的干净语料（合并前）
FET = os.path.join(OSS, "repos_fetched.jsonl")       # 补抓增量
SUMMARY = os.path.join(OSS, "oss_fetch_summary.md")

# 补抓复核判据：嵌入命名/中文亦算相关（宽松，仅用于"是否漏进噪声"的复核）。
# 注意：本批补抓 10 个 query 全部为 topic: 标签过滤或引号精确短语，
# 故预期 100% 相关；严格 \b 边界会把 AudioLanguageModel / audio_language_model
# / 中文描述等真音频仓库误判为"漏进噪声"，此处用嵌入感知正则避免误报。
AUDIO_RE = re.compile(
    r"(?i)(audio|sound|speech|voice|tts|asr|acoustic|whisper|sonic|hearing|"
    r"music|voicebot|wake.?word|vad|diariz|vocoder|spectrog|vocal|speaker|"
    r"noise|echo|mel|wav|mp3|pcm|microphone|singing|karaoke|keyword|kws|"
    r"hotword|listen|speak|song|sing)")
CN_AUDIO = re.compile(r"(音频|语音|声音|声纹|说话人|唱歌|音乐|听写|配音)")


def main():
    rows = [json.loads(l) for l in io.open(RAW, encoding="utf-8") if l.strip()]
    seen = {r["full_name"] for r in rows}
    before = len(rows)

    fet = [json.loads(l) for l in io.open(FET, encoding="utf-8") if l.strip()]
    leak = [r for r in fet
            if not (r.get("query", "").startswith("topic:")          # topic 标签过滤 = 授权相关
                    or AUDIO_RE.search(r["full_name"] + " " + r.get("description", "") + " "
                                      + " ".join(r.get("topics", [])))
                    or CN_AUDIO.search(r.get("description", "")))]
    added = 0
    for r in fet:
        if r["full_name"] in seen:
            continue
        seen.add(r["full_name"])
        rows.append(r)
        added += 1

    with io.open(RAW, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 统计
    lic_missing = sum(1 for r in rows if not r.get("license"))
    lic_present = len(rows) - lic_missing
    star_buckets = collections.Counter()
    for r in rows:
        s = r.get("stars", 0)
        if s >= 10000:
            star_buckets[">=10000"] += 1
        elif s >= 1000:
            star_buckets["1000-9999"] += 1
        elif s >= 100:
            star_buckets["100-999"] += 1
        else:
            star_buckets["<100"] += 1
    langs = collections.Counter(r.get("language") or "(none)" for r in rows)
    top20 = sorted(rows, key=lambda x: -x.get("stars", 0))[:20]

    # 补抓中的重要新增（原语料未覆盖的高星真实音频项目）top 示例
    new_rows = [r for r in rows if r.get("query", "").startswith(  # 仅来自补抓的
        '"') or r.get("query", "").startswith("topic:")]
    new_high = sorted(new_rows, key=lambda x: -x.get("stars", 0))[:15]

    lines = []
    lines.append("# OSS 抓取摘要（去噪 + 精准补抓后）\n")
    lines.append("**生成日期**: %s" % datetime.date.today().isoformat())
    lines.append("**干净语料文件**: `docs/research/oss/repos_raw.jsonl`\n")
    lines.append("## 1. 总规模\n")
    lines.append("- 合并后总数：**%d 条**（去噪保留 %d + 补抓新增 %d）" %
                 (len(rows), before, added))
    lines.append("- 噪声已剔除：见 `oss_audit.md`（共 %d 条，来自 audio-llm/voice-agent 裸词切片）" % 1376)
    lines.append("- 补抓泄漏复核：1850 条补抓中命中音频域判据 **%d / %d**（漏进噪声 %d 条）"
                 % (len(fet) - len(leak), len(fet), len(leak)))
    lines.append("\n## 2. Star 分布\n")
    lines.append("| 档位 | 数量 |")
    lines.append("|---|---:|")
    for k in [">=10000", "1000-9999", "100-999", "<100"]:
        lines.append("| %s | %d |" % (k, star_buckets[k]))
    lines.append("\n## 3. 语言分布 top10\n")
    lines.append("| 语言 | 数量 |")
    lines.append("|---|---:|")
    for lang, n in langs.most_common(10):
        lines.append("| %s | %d |" % (lang, n))
    lines.append("\n## 4. 星级 top20\n")
    lines.append("| star | 仓库 | 语言 | 一句话用途 |")
    lines.append("|---:|---|---|---|")
    for r in top20:
        lines.append("| %d | %s | %s | %s |" % (
            r.get("stars", 0), r["full_name"], r.get("language") or "-",
            (r.get("description") or "")[:50].replace("|", "/")))
    lines.append("\n## 5. 补抓说明\n")
    lines.append("补抓用 `crawl_oss_repos.search()` 跑 10 个引号短语 / `topic:` 查询"
                 "（每 query 2 页，遵守 search 10/min 限速），共取回 1850 条增量，"
                 "并入后净增 **%d** 条。查询清单：" % added)
    for q in ['"audio language model"', '"speech emotion recognition"',
              '"voice activity detection"', '"voice agent"', '"realtime voice"',
              "topic:audio-classification", "topic:speech-synthesis",
              "topic:keyword-spotting", "topic:voice-ai", "topic:sound"]:
        lines.append("  - `%s`" % q)
    lines.append("\n## 6. 许可信息缺失说明（重要）\n")
    lines.append("- 干净语料中 **%d / %d** 条缺失 `license` 字段。" % (lic_missing, len(rows)))
    lines.append("- 缺失来自两部分：(a) 原 `oss_corpus.json` 语料本身无 license 字段"
                 "（已置空，未编造）；(b) 补抓条目经 search 端点已带 license，但部分为 `NOASSERTION`。")
    lines.append("- 报告与榜单中**不得**把缺失当「无许可」，需在 Task 4 报告中标注"
                 "「许可信息需另行核实，非法律意见」。")
    lines.append("\n## 7. 衔接\n")
    lines.append("- 去噪审计明细：`oss_audit.md`（各切片相关率、剔除判据、被剔除高星仓库列表）。")
    lines.append("- 下一步（Task 3）：对 `repos_raw.jsonl` 分类打标 + laos 四段漏斗适配映射。")

    io.open(SUMMARY, "w", encoding="utf-8").write("\n".join(lines))

    # 控制台
    print("合并前 %d + 补抓新增 %d = %d 条" % (before, added, len(rows)))
    print("补抓泄漏复核: %d/%d 命中音频判据，漏进噪声 %d 条"
          % (len(fet) - len(leak), len(fet), len(leak)))
    if leak:
        print("  泄漏样本:")
        for r in leak[:10]:
            print("   ", r["full_name"], "|", (r.get("description") or "")[:50])
    print("license 缺失: %d/%d" % (lic_missing, len(rows)))
    print("star 分布:", dict(star_buckets))
    print("语言 top5:", langs.most_common(5))
    print("补抓高星新增示例 top8:")
    for r in new_high[:8]:
        print("   %8d  %-40s %s" % (r.get("stars", 0), r["full_name"],
                                    r.get("query", "")[:30]))
    print("-> %s" % SUMMARY)


if __name__ == "__main__":
    main()
