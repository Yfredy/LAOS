#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""从 ISCA 摘要页补抓 abstract（Interspeech 语料摘要层补全）。

设计（2026-09-14 实测结论，不得偏离）：
  * ISCA 摘要页结构：<div id="abstract"><p>...</p></div>，无 meta description 摘要。
    计划原版只查 class="...abstract..." 会漏掉 id="abstract"，这里已修正。
  * ISCA 偶发 SSL UNEXPECTED_EOF，fetch 带 3 次重试 + 递增退避，可恢复。
  * 增量：已有 abstract 的条目跳过；每 50 条落盘一次，中途崩溃不全丢。
  * 只写 abstract / abstract_failed 两个字段，绝不改动已有字段。
  * 礼貌限速 0.8s/条（1200 条约 16 分钟）。

用法：
  python crawl_interspeech_abstracts.py 60
  python crawl_interspeech_abstracts.py 1200 emotion,edge,kws_vad,event,codec,enhance
"""
import urllib.request, ssl, json, re, io, os, sys, time

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "laos-research/1.0 (mailto:laos-survey@example.com)"}
CORPUS = r"C:\Users\yaoyue\CodeBuddy\Claw\laos\docs\research\corpus\interspeech_corpus.json"


def fetch(url, tries=3, wait=6):
    """带重试/退避的 GET。ISCA 偶发 SSL UNEXPECTED_EOF，重试可恢复。"""
    last = None
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            sys.stderr.write("  retry%d %s %s\n" % (t, type(e).__name__, str(e)[:60]))
            if t < tries - 1:
                time.sleep(wait * (t + 1))
    return None


def _clean(text):
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"&[a-zA-Z]+;", " ", t)        # 去 HTML 实体占位
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_abstract(html):
    """从 ISCA 摘要页抽取摘要正文。

    优先级：meta description（部分旧页有）→ <div id="abstract">（主结构）
    → class 含 abstract/summary 的块。正文需 > 80 字符才算有效。
    """
    if not html:
        return None
    # 1) meta description 兜底
    m = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    if m:
        t = _clean(m.group(1))
        if len(t) > 80:
            return t
    # 2) 主结构：<div id="abstract">...</div>
    blk = re.search(r'(?is)<div[^>]*id="abstract"[^>]*>(.*?)</div>', html)
    if blk:
        t = _clean(blk.group(1))
        if len(t) > 80:
            return t
    # 3) class 含 abstract / summary 的块（兼容其他模板）
    blk = re.search(r'(?is)<div[^>]*class="[^"]*(?:abstract|summary)[^"]*"[^>]*>(.*?)</div>', html)
    if blk:
        t = _clean(blk.group(1))
        if len(t) > 80:
            return t
    return None


def dump_sample(url, html, path):
    """诊断用：把样本页 HTML 落盘，便于肉眼看结构。"""
    try:
        io.open(path, "w", encoding="utf-8").write(
            "URL: %s\n\n%s" % (url, html or "(None)"))
        print("  已 dump 样本页结构 -> %s" % path)
    except Exception as e:
        print("  dump 失败 %s" % e)


def main(limit, only_topics):
    corpus = json.load(io.open(CORPUS, encoding="utf-8"))
    papers = corpus["papers"]
    targets = [p for p in papers if not p.get("abstract")]
    if only_topics:
        targets = [p for p in targets if set(p.get("topics") or []) & set(only_topics)]
    targets = targets[:limit]
    print("待抓 %d 条" % len(targets))
    ok = fail = 0
    dump_done = False
    for i, p in enumerate(targets):
        html = fetch(p["url"])
        a = parse_abstract(html)
        if a:
            p["abstract"] = a
            ok += 1
        else:
            p["abstract_failed"] = True
            fail += 1
            # 前几条失败就 dump 一篇看结构（诊断 ok 率过低时用）
            if fail <= 3 and not dump_done and html is not None:
                dump_sample(p["url"], html,
                            os.path.join(os.path.dirname(CORPUS), "abstract_sample_dump.html"))
                dump_done = True
        if (i + 1) % 20 == 0:
            sys.stdout.write("  %d/%d ok=%d fail=%d\n" % (i + 1, len(targets), ok, fail))
            sys.stdout.flush()
        if (i + 1) % 50 == 0:
            io.open(CORPUS, "w", encoding="utf-8").write(
                json.dumps(corpus, ensure_ascii=False))
        time.sleep(0.8)
    io.open(CORPUS, "w", encoding="utf-8").write(json.dumps(corpus, ensure_ascii=False))
    print("DONE ok=%d fail=%d rate=%.1f%%" % (ok, fail, 100.0 * ok / max(1, ok + fail)))


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    topics = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    main(lim, topics)
