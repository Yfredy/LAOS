#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""GitHub 高星开源项目抓取（search 端点，未认证）。

实测约束（2026-09-14）：
  * search 限额 10 次/分钟 -> 每请求 sleep 7s
  * core 限额 60 次/小时且常为 0 -> 只用 search 端点，不补充字段
  * 单 query 上限 1000 条 -> 按 stars 降序取 top 即可（本任务只要高星的）

关键修复（相对 corpus/crawl_github_oss.py 的噪声）：
  关键词查询一律用「引号短语」或 topic: 过滤，禁止裸关键词全文检索。
  例如 '\"audio language model\" in:name,description' 不会被 GitHub 拆词匹配，
  从而不再混入 public-apis / awesome-python 这类与音频无关的通用高星仓库。
"""
import urllib.request, urllib.parse, json, ssl, time, sys, os, io, datetime

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "laos-research/1.0"}

# 速率限制纪律：search 10/min，请求间隔 >= 7s。被测试断言，不得放宽。
sleep_between_requests = 7

OUT_DIR = r"C:/Users/yaoyue/CodeBuddy/Claw/laos/docs/research/oss"

# 三域覆盖：音频基础 / 语音 AI / Agent。规模见计划 Global Constraints 第 2 条。
# topic: 切片 100% 相关可直接复用；关键词切片全部用引号短语（修复噪声）。
QUERIES = [
    "topic:audio", "topic:speech-recognition", "topic:text-to-speech",
    "topic:voice", "topic:llm-agent", "topic:ai-agent",
    "topic:audio-classification", "topic:speech-synthesis",
    "topic:voice-assistant", "topic:sound",
    '"speech recognition" in:name,description',
    '"voice assistant" in:name,description',
    '"audio language model" in:name,description',
    '"voice agent" in:name,description',
    '"realtime speech" in:name,description',
    '"keyword spotting" in:name,description',
    '"on-device speech" in:name,description',
    '"tts" in:name,description',
]


def build_search_url(query, page=1, per_page=100):
    """构造 search/repositories 请求 URL。

    query 原样（含引号短语）经 urlencode 透传；统一追加 fork:false 并
    按 stars 降序。引号会被编码为 %22，GitHub 仍按短语精确匹配。
    """
    q = query + " fork:false"
    return ("https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) +
            "&sort=stars&order=desc&per_page=%d&page=%d" % (per_page, page))


def parse_repo(raw, query, crawled_at):
    """从 search 单条 item 解析出 14 字段 schema（字段名与计划逐字一致）。

    license 为 None / 无 spdx_id 时置空字符串；description/topics 缺失置默认。
    日期截断到日。star 数、license、语言一律取 API 原值，不编造。
    """
    lic = raw.get("license")
    lic = lic.get("spdx_id") if isinstance(lic, dict) else lic
    return {
        "full_name": raw.get("full_name", ""),
        "stars": raw.get("stargazers_count", 0),
        "description": raw.get("description") or "",
        "language": raw.get("language") or "",
        "license": lic or "",
        "html_url": raw.get("html_url", ""),
        "created_at": (raw.get("created_at") or "")[:10],
        "pushed_at": (raw.get("pushed_at") or "")[:10],
        "topics": raw.get("topics") or [],
        "archived": bool(raw.get("archived")),
        "forks": raw.get("forks_count", 0),
        "open_issues": raw.get("open_issues_count", 0),
        "query": query,
        "crawled_at": crawled_at,
    }


def is_excluded(r):
    """仅剔除已归档仓库。fork 已由 URL 中的 fork:false 过滤。"""
    return bool(r.get("archived"))


def fetch(url, tries=3, wait=20):
    """GET 一个 URL，返回 bytes；失败重试。仅用 search 端点。"""
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
                return r.read()
        except Exception as e:
            sys.stderr.write("  retry%d %s\n" % (t, str(e)[:70]))
            if t < tries - 1:
                time.sleep(wait * (t + 1))
    return None


def search(query, pages=1, per_page=100, out=None, seen=None, excluded=0):
    """执行单个 query 的 1..pages 页抓取。

    返回 (count, excluded)。若 out 为文件句柄且 seen 为 dict，则逐条去重写盘。
    """
    count = 0
    if seen is None:
        seen = {}
    for page in range(1, pages + 1):
        raw = fetch(build_search_url(query, page=page, per_page=per_page))
        if raw is None:
            break
        try:
            d = json.loads(raw.decode("utf-8"))
        except Exception:
            break
        items = d.get("items") or []
        if not items:
            break
        for it in items:
            r = parse_repo(it, query, datetime.date.today().isoformat())
            if is_excluded(r):
                excluded += 1
                continue
            if r["full_name"] in seen:
                continue
            seen[r["full_name"]] = 1
            if out is not None:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
            count += 1
        if out is not None:
            out.flush()
        if len(items) < per_page:
            break
        time.sleep(sleep_between_requests)
    return count, excluded


def main(pages_per_query=3, out_name="repos_raw.jsonl"):
    """全量抓取所有 QUERIES（默认 3 页）。落盘 repos_raw.jsonl。

    注意：完整跑会耗尽 search 限额；小规模验证请用 search() 单 query。
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    crawled_at = datetime.date.today().isoformat()
    out_path = os.path.join(OUT_DIR, out_name)
    seen, total, excluded = {}, 0, 0
    with io.open(out_path, "w", encoding="utf-8") as f:
        for qi, q in enumerate(QUERIES):
            c, ex = search(q, pages=pages_per_query, out=f, seen=seen,
                           excluded=excluded)
            total += c
            excluded = ex
            sys.stdout.write("  q%-2d %-44s 累计%5d 剔除归档%d\n"
                             % (qi, q[:44], total, excluded))
            sys.stdout.flush()
            time.sleep(sleep_between_requests)
    print("DONE unique=%d archived_excluded=%d -> %s" % (total, excluded, out_path))


if __name__ == "__main__":
    main(pages_per_query=int(sys.argv[1]) if len(sys.argv) > 1 else 3)
