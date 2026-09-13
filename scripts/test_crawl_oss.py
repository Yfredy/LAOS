# SPDX-License-Identifier: MIT
"""Task 1 测试：GitHub 补抓器与 schema。

断言点：
  * build_search_url 必须带 fork:false + sort=stars&order=desc
  * parse_repo 输出 14 个字段，字段名与计划逐字一致
  * parse_repo 处理 license=None / topics=None / description=None
  * is_excluded 仅剔除 archived
  * QUERIES 覆盖 audio/speech/voice/agent/tts 三域
  * sleep_between_requests >= 7（速率限制纪律，不得放宽）
"""
import sys, os, json, io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_oss_repos import (build_search_url, parse_repo, is_excluded,
                             QUERIES, sleep_between_requests)


def test_url_has_fork_false_and_sort():
    u = build_search_url("topic:audio", page=1, per_page=100)
    assert "api.github.com/search/repositories" in u
    assert "q=topic%3Aaudio" in u or "topic%3Aaudio" in u
    assert "fork%3Afalse" in u or "fork:false" in u
    assert "sort=stars" in u
    assert "order=desc" in u


def test_parse_repo_extracts_required_fields():
    raw = {"full_name": "a/b", "stargazers_count": 10, "description": "d",
           "language": "Python", "license": {"spdx_id": "MIT"},
           "html_url": "https://github.com/a/b", "created_at": "2020-01-01T00:00:00Z",
           "pushed_at": "2026-01-01T00:00:00Z", "topics": ["audio"],
           "archived": False, "forks_count": 1, "open_issues_count": 2}
    r = parse_repo(raw, "topic:audio", "2026-09-14")
    assert r["full_name"] == "a/b" and r["stars"] == 10
    assert r["license"] == "MIT" and r["language"] == "Python"
    assert r["query"] == "topic:audio" and r["crawled_at"] == "2026-09-14"
    assert r["created_at"] == "2020-01-01"      # 截断到日
    assert set(r.keys()) >= {"full_name", "stars", "description", "language", "license",
                             "html_url", "created_at", "pushed_at", "topics", "archived",
                             "forks", "open_issues", "query", "crawled_at"}


def test_parse_repo_handles_null_license():
    r = parse_repo({"full_name": "x/y", "stargazers_count": 0, "license": None,
                    "topics": None, "description": None,
                    "created_at": "2021-05-05T00:00:00Z", "pushed_at": "2022-05-05T00:00:00Z"},
                   "q", "2026-09-14")
    assert r["license"] in (None, "NOASSERTION", "")
    assert r["topics"] == [] and r["description"] == ""


def test_archived_and_fork_excluded():
    assert is_excluded({"archived": True, "full_name": "a/b"})
    assert not is_excluded({"archived": False, "full_name": "a/b"})


def test_query_set_covers_three_domains():
    joined = " ".join(QUERIES).lower()
    for kw in ["audio", "speech", "voice", "agent", "tts"]:
        assert kw in joined, kw


def test_rate_limit_sleep_is_conservative():
    assert sleep_between_requests >= 7


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", t.__name__, "->", repr(e))
    print("\n%d passed, %d failed" % (len(tests) - failed, failed))
    sys.exit(1 if failed else 0)
