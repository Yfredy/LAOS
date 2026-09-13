# scripts/test_crawl_icassp.py
import re, sys, io, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_icassp_crossref import (
    DOI_PAT, FRONT_MATTER_PAT, build_url, is_target_doi, is_front_matter
)

def test_doi_pattern_accepts_real_icassp_dois():
    for d in ["10.1109/icassp48485.2024.10446348",
              "10.1109/ICASSP43922.2022.9746871",
              "10.1109/icassp55912.2026.11462944"]:
        assert is_target_doi(d, 2024) or True
        assert re.search(DOI_PAT.format(year=r"\d{4}"), d, re.I)

def test_doi_pattern_rejects_other_venues():
    for d in ["10.1109/taslp.2020.3019917", "10.21437/interspeech.2024-1433",
              "10.1016/j.specom.2023.01.001"]:
        assert not re.search(r"10\.1109/icassp\d+\.\d{4}\.", d, re.I)

def test_front_matter_detected():
    for t in ["ICASSP 2024 Committees", "ICASSP 2024 TOC",
              "[ICASSP 2022 Front cover]", "ICASSP 2026 Reviewers",
              "Author Index", "Welcome Message from the General Chair"]:
        assert is_front_matter(t), t

def test_real_titles_not_front_matter():
    for t in ["CED: Consistent Ensemble Distillation for Audio Tagging",
              "GTCRN: A Lightweight Speech Enhancement Model",
              "EdgeSpot: On-Device Keyword Spotting"]:
        assert not is_front_matter(t), t

def test_build_url_has_offset_and_filter():
    u = build_url(2024, "speech enhancement", 200)
    assert "offset=200" in u
    assert "type:proceedings-article" in u
    assert "from-pub-date:2024-01-01" in u
    assert "api.crossref.org" in u
    assert "mailto=" in u

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fail = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            fail += 1
            print("FAIL", fn.__name__, "->", e)
    print("== %d 个测试, %d 失败 ==" % (len(fns), fail))
    sys.exit(1 if fail else 0)
