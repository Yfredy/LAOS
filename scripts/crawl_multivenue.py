#!/usr/bin/env python3
"""多顶会主题切片爬虫（Semantic Scholar Graph API）——ICASSP/Interspeech 普查的泛化版。

覆盖六类 ~36 个 venue（NLP/ML/CV/语音近邻/多媒体/交叉），按主题切片检索，
年份窗口 2021-2026，输出 docs/research/corpus/multivenue_<venue>.json。

用法：
    python scripts/crawl_multivenue.py --probe                # venue 精确串探测（先跑这个）
                                                               # 已解析 venue 会沿用 strings.json 增量续跑，
                                                               # 可用 --deadline-minutes 分段多次运行
    python scripts/crawl_multivenue.py --wave A [--venue SLT] # 波 A：语音近邻 + NLP 核心
    python scripts/crawl_multivenue.py --wave B               # 波 B：ML/多媒体/交叉（+CV 仅音视）
    python scripts/crawl_multivenue.py --wave A --dry-run     # 只打印将发起的 URL，不发请求
    python scripts/crawl_multivenue.py --harvest              # 读 observed.json 输出建议新增规范串

幂等性：目标 venue 文件 docs/research/corpus/multivenue_<venue>.json 已存在则跳过
该 venue（无论 --wave/--venue 如何指定）。要重爬某 venue，先删除对应文件。
全部查询都失败的 venue 不写文件，下次运行自动重试。

限流纪律（照搬 corpus/crawl_icassp_s2_round3.py 验证参数 + 耐心重扫）：
    - 请求间最小间距 75s，且重试同受此下限约束：429/miss 后经 pacer 等满
      75s 才发第二次——任意两次 curl 间距 >= 75s；
    - 单次请求仍失败不放弃：按 round-3 的 sweep 语义，未完成的主题/候选串
      在后续轮次继续重试，直到预算或墙钟截止（如实在文件/strings.json 标注）；
    - 预算按**成功响应数**计（默认 probe=40、wave=90；429 空转不计入，
      以免限流风暴耗尽预算——真实 API 压力由 75s 间距控制）；
    - 墙钟硬上限：probe 默认 120 分钟，wave 默认 240 分钟（--deadline-minutes 覆盖）。

venue 串解析：S2 的 venue= 过滤是模糊匹配，返回可能含邻居串；本脚本
(a) 用 --probe 对每个候选串跑 query=<串>&venue=<串> 取 top5 的 venue 字段
    众数（>=2 票或唯一结果）作为规范串，落
    docs/research/corpus/multivenue_strings.json（含 unresolved 记录试过的串）；
(b) 爬取时对 S2 返回的 venue 字段做客户端精确匹配（venue_of）后才入库；
(c) venue_of_fuzzy 提供宽松分类（casefold+去标点双向子串，别名表含
    resolved+tried 并集）——用于人工核对/ harvested 串归类，不改变入库口径；
(d) 波次爬取把返回 paper 的真实 venue 串累计到
    docs/research/corpus/multivenue_observed.json（机会式采集），
    --harvest 据此输出"建议新增规范串"（计数 >=3 且未精确收录）。

每条记录均来自 API 实际返回（title/year/venue/citationCount/externalIds/abstract），
抓不到的主题/venue 如实标 uncovered，禁止用训练知识补数。
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS_DIR = REPO / "docs" / "research" / "corpus"
STRINGS_PATH = CORPUS_DIR / "multivenue_strings.json"
OBSERVED_PATH = CORPUS_DIR / "multivenue_observed.json"
HARVEST_MIN_COUNT = 3    # --harvest 建议门槛：出现次数 >= 此值才提示新增

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,year,venue,citationCount,externalIds,abstract"
YEAR_WINDOW = "2021-2026"
REQUEST_GAP_S = 75        # 请求间最小间距（round-3 验证的生存参数；重试路径同受约束）
SWEEP_GAP_S = 30          # 无进展轮次之间的额外等待
CURL_TIMEOUT_S = 45
PROBE_WALL_S = 120 * 60   # 探测默认墙钟上限
WAVE_WALL_S = 240 * 60    # 爬波默认墙钟上限（计划波预算 90 请求 x 75s 约 2 小时 + 重试余量）
PROBE_TOP_K = 5           # 探测取 top5 的 venue 众数

# ---------------------------------------------------------------------------
# Spec venue 清单：六类 -> venue 短名（CLI --venue / 输出文件名用）
# ---------------------------------------------------------------------------
VENUE_NAMES: dict[str, list[str]] = {
    "speech_adj": ["SLT", "ASRU", "WASPAA", "CHiME", "TASLP", "EURASIP"],
    "nlp": ["ACL", "EMNLP", "NAACL", "COLING", "CoNLL", "TACL", "CL"],
    "ml": ["ICLR", "NeurIPS", "ICML", "AAAI", "IJCAI", "JMLR"],
    "cv": ["CVPR", "ECCV", "ICCV", "TPAMI", "IJCV"],
    "multimedia": ["ACMMM", "ICMR", "MMSys", "ICME", "PCM", "TMM", "TOMM"],
    "cross": ["SIGIR", "KDD", "WWW", "WSDM", "RecSys"],
}

# 候选串：探测前的合理初值（有序，第一个为主候选）。
# 探测后与 multivenue_strings.json 的 resolved 规范串取并集进 VENUES（别名保留）。
CANDIDATES: dict[str, list[str]] = {
    # -- 语音近邻 --
    "SLT": [
        "IEEE Spoken Language Technology Workshop",
        "IEEE Spoken Language Technology Workshop (SLT)",
        "Spoken Language Technology Workshop",
    ],
    "ASRU": [
        "IEEE Automatic Speech Recognition and Understanding Workshop",
        "IEEE Automatic Speech Recognition and Understanding Workshop (ASRU)",
    ],
    "WASPAA": [
        "IEEE Workshop on Applications of Signal Processing to Audio and Acoustics",
        "IEEE Workshop on Applications of Signal Processing to Audio and Acoustics (WASPAA)",
        "WASPAA",
    ],
    "CHiME": ["CHiME", "CHiME Challenge"],
    "TASLP": [
        "IEEE/ACM Transactions on Audio, Speech, and Language Processing",
        "IEEE Transactions on Audio, Speech, and Language Processing",
    ],
    "EURASIP": ["EURASIP Journal on Audio, Speech, and Music Processing"],
    # -- NLP --
    "ACL": ["ACL", "Annual Meeting of the Association for Computational Linguistics"],
    "EMNLP": [
        "EMNLP",
        "Conference on Empirical Methods in Natural Language Processing",
        "Empirical Methods in Natural Language Processing",
    ],
    "NAACL": [
        "NAACL",
        "North American Chapter of the Association for Computational Linguistics",
        "North American Chapter Meeting of the Association for Computational Linguistics",
    ],
    "COLING": ["COLING", "International Conference on Computational Linguistics"],
    "CoNLL": [
        "CoNLL",
        "Conference on Computational Natural Language Learning",
        "SIGNLL Conference on Computational Natural Language Learning",
    ],
    "TACL": ["Transactions of the Association for Computational Linguistics", "TACL"],
    "CL": ["Computational Linguistics", "CL"],
    # -- ML --
    "ICLR": ["ICLR", "International Conference on Learning Representations"],
    "NeurIPS": [
        "NeurIPS",
        "Advances in Neural Information Processing Systems",
        "Annual Conference of the Neural Information Processing Systems",
    ],
    "ICML": ["ICML", "International Conference on Machine Learning"],
    "AAAI": [
        "AAAI",
        "AAAI Conference on Artificial Intelligence",
        "Proceedings of the AAAI Conference on Artificial Intelligence",
    ],
    "IJCAI": [
        "IJCAI",
        "International Joint Conference on Artificial Intelligence",
        "Proceedings of the International Joint Conference on Artificial Intelligence",
    ],
    "JMLR": ["Journal of Machine Learning Research"],
    # -- CV（可选类，仅音视主题）--
    "CVPR": [
        "CVPR",
        "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        "IEEE Conference on Computer Vision and Pattern Recognition",
    ],
    "ECCV": ["ECCV", "European Conference on Computer Vision"],
    "ICCV": [
        "ICCV",
        "IEEE/CVF International Conference on Computer Vision",
        "International Conference on Computer Vision",
    ],
    "TPAMI": ["IEEE Transactions on Pattern Analysis and Machine Intelligence"],
    "IJCV": ["International Journal of Computer Vision"],
    # -- 多媒体 --
    "ACMMM": [
        "ACM Multimedia",
        "Proceedings of the ACM International Conference on Multimedia",
        "ACM International Conference on Multimedia",
    ],
    "ICMR": ["ICMR", "ACM International Conference on Multimedia Retrieval"],
    "MMSys": [
        "MMSys",
        "ACM Multimedia Systems Conference",
        "Proceedings of the ACM Multimedia Systems Conference",
    ],
    "ICME": ["IEEE International Conference on Multimedia and Expo", "ICME"],
    "PCM": ["Pacific-Rim Conference on Multimedia", "PCM", "Pacific Rim Conference on Multimedia"],
    "TMM": ["IEEE Transactions on Multimedia"],
    "TOMM": [
        "ACM Transactions on Multimedia Computing, Communications, and Applications",
        "ACM Transactions on Multimedia Computing, Communications, and Applications (TOMM)",
    ],
    # -- 交叉 --
    "SIGIR": [
        "SIGIR",
        "International ACM SIGIR Conference on Research and Development in Information Retrieval",
    ],
    "KDD": ["KDD", "Knowledge Discovery and Data Mining"],
    "WWW": ["WWW", "The Web Conference", "World Wide Web"],
    "WSDM": ["WSDM", "ACM International Conference on Web Search and Data Mining"],
    "RecSys": ["RecSys", "ACM Conference on Recommender Systems"],
}

# ---------------------------------------------------------------------------
# 主题集：12 既有（ICASSP/Interspeech 普查口径）+ 5 扩展（NLP/ML 场）
# ---------------------------------------------------------------------------
TOPICS_12 = [
    "speech enhancement", "speaker diarization", "keyword spotting",
    "neural codec", "text to speech", "sound event detection",
    "self-supervised speech", "streaming speech recognition",
    "speech language model", "paralinguistic",
    "emotion recognition", "voice activity detection",
]
TOPICS_EXT5 = [
    "LLM agent tool use", "agent memory", "audio language model",
    "multimodal agent", "on-device inference",
]
TOPICS_ALL = TOPICS_12 + TOPICS_EXT5

# 波次主题分配（类别 -> 主题列表；venue 顺序按 VENUE_NAMES 中的优先级）
WAVE_TOPICS: dict[str, list[tuple[str, list[str]]]] = {
    # 波 A：语音近邻 6 venue 全 17 主题；NLP 核心 8 主题（5 扩展 + emotion/paralinguistic/codec）
    "A": [
        ("speech_adj", TOPICS_ALL),
        ("nlp", TOPICS_EXT5 + ["emotion recognition", "paralinguistic", "neural codec"]),
    ],
    # 波 B：ML 6 主题（5 扩展 + SSL）；多媒体 audio/video 相关；交叉 agent/memory；
    #      CV 三大会+期刊仅音视两主题（可选低优先，排在最后）
    "B": [
        ("ml", TOPICS_EXT5 + ["self-supervised speech"]),
        ("multimedia", [
            "multimodal agent", "audio language model", "sound event detection",
            "neural codec", "on-device inference",
        ]),
        ("cross", ["LLM agent tool use", "agent memory", "multimodal agent", "on-device inference"]),
        ("cv", ["audio-visual", "audio language model"]),
    ],
}

# 探测顺序：laos 优先级高的类在前，CV（可选）最后——预算/墙钟耗尽时牺牲的是低优先级
PROBE_ORDER = ["speech_adj", "nlp", "ml", "multimedia", "cross", "cv"]


# ---------------------------------------------------------------------------
# VENUES 构建：候选串 ∪ 已解析规范串（multivenue_strings.json 存在时）
# ---------------------------------------------------------------------------
def _load_strings() -> dict:
    try:
        if STRINGS_PATH.exists():
            with io.open(STRINGS_PATH, encoding="utf-8") as f:
                return json.loads(f.read())
    except (OSError, json.JSONDecodeError):
        pass
    return {}


_STRINGS = _load_strings()


def _build_venues() -> dict[str, list[str]]:
    resolved = _STRINGS.get("resolved") or {}
    unresolved = _STRINGS.get("unresolved") or {}
    venues: dict[str, list[str]] = {}
    for cat, keys in VENUE_NAMES.items():
        vals: list[str] = []
        for key in keys:
            for cand in CANDIDATES.get(key, []):
                if cand not in vals:
                    vals.append(cand)
            canon = resolved.get(key)
            if isinstance(canon, str) and canon and canon not in vals:
                vals.append(canon)
            unres = unresolved.get(key)
            if isinstance(unres, dict):
                for tried in unres.get("tried") or []:
                    if isinstance(tried, str) and tried and tried not in vals:
                        vals.append(tried)
        venues[cat] = vals
    return venues


VENUES: dict[str, list[str]] = _build_venues()
"""类别 -> venue 精确串列表（含别名）。初值为 CANDIDATES 展开；探测落
multivenue_strings.json 后自动并入 resolved 规范串 + unresolved 的 tried 串
（并集，别名保留）——tried 串是合理候选，供模糊匹配使用。"""

VENUE_SET = frozenset(s for strings in VENUES.values() for s in strings)


def venue_of(paper: dict) -> str | None:
    """paper["venue"] 精确匹配 VENUES 展开集（大小写/空白敏感），命中返回该串，否则 None。"""
    v = paper.get("venue") if isinstance(paper, dict) else None
    return v if isinstance(v, str) and v in VENUE_SET else None


# ---------------------------------------------------------------------------
# 模糊匹配：casefold + 去标点 -> 双向子串（等值或双方均 >=3 字符的包含）
# ---------------------------------------------------------------------------
_PUNCT_RE = re.compile(r"[^\w\s]|_")


def _norm_venue(s: str) -> str:
    """venue 串规范化：casefold、标点/下划线 -> 空格、折叠连续空白。"""
    return " ".join(_PUNCT_RE.sub(" ", s.casefold()).split())


# 预计算规范化别名表：(类别, 规范化别名) 列表
_VENUES_NORM: list[tuple[str, str]] = [
    (cat, _norm_venue(s))
    for cat, strings in VENUES.items()
    for s in strings
    if _norm_venue(s)
]

_FUZZY_MIN_LEN = 3  # 子串包含方向的最短别名/venue 长度（挡住 "cl" ⊂ "iclr" 这类劫持）


def venue_of_fuzzy(paper: dict) -> str | None:
    """paper["venue"] 模糊匹配 VENUES，命中返回类别名，否则 None。

    规则：casefold + 去标点后，venue 与某别名相等、或双向子串包含
    （双向均 >=3 字符，防 "CL" 劫持 "ICLR"）。多个类别命中时取
    规范化别名最长者（最具体优先），平局按 VENUES 类别顺序。
    例："NeurIPS" 串能匹配 "Neural Information Processing Systems"；
    "EMNLP" 不含全称子串，靠别名表（CANDIDATES ∪ resolved ∪ tried）命中 nlp。
    """
    v = paper.get("venue") if isinstance(paper, dict) else None
    if not isinstance(v, str):
        return None
    nv = _norm_venue(v)
    if not nv:
        return None
    best_cat: str | None = None
    best_len = 0
    for cat, na in _VENUES_NORM:
        hit = na == nv or (
            len(na) >= _FUZZY_MIN_LEN and len(nv) >= _FUZZY_MIN_LEN
            and (na in nv or nv in na)
        )
        if hit and len(na) > best_len:
            best_len = len(na)
            best_cat = cat
    return best_cat


def canonical_string(venue_key: str) -> str:
    """venue 短名 -> 探测解析的规范串（未解析/未探测时用第一候选串）。"""
    resolved = _STRINGS.get("resolved") or {}
    canon = resolved.get(venue_key)
    if isinstance(canon, str) and canon:
        return canon
    return CANDIDATES[venue_key][0]


def slice_query(venue: str, topic: str) -> str:
    """构造 S2 paper/search URL：venue 过滤 + 年份窗口 + 固定 fields + limit=100。"""
    return (
        S2_SEARCH
        + "?query=" + urllib.parse.quote(topic)
        + "&venue=" + urllib.parse.quote(venue)
        + f"&year={YEAR_WINDOW}&fields={FIELDS}&limit=100"
    )


# ---------------------------------------------------------------------------
# merge：跨 venue 文件合并去重
# ---------------------------------------------------------------------------
def _papers_from(obj) -> list[dict]:
    """从爬虫产物提取论文记录；支持三种形态：
    {"queries": {topic: {"total", "papers"}}} / {"papers": [...]} / S2 裸响应 {"data": [...]} / 裸列表。"""
    out: list[dict] = []
    if isinstance(obj, list):
        out.extend(p for p in obj if isinstance(p, dict))
    elif isinstance(obj, dict):
        if isinstance(obj.get("papers"), list):
            out.extend(p for p in obj["papers"] if isinstance(p, dict))
        elif isinstance(obj.get("data"), list):
            out.extend(p for p in obj["data"] if isinstance(p, dict))
        elif isinstance(obj.get("queries"), dict):
            for entry in obj["queries"].values():
                if isinstance(entry, dict) and isinstance(entry.get("papers"), list):
                    out.extend(p for p in entry["papers"] if isinstance(p, dict))
    return out


def merge(paths) -> dict:
    """合并多个 multivenue_<venue>.json：按 (title.lower(), year) 去重。

    同 title 同 year 出现在多个 venue（或同 venue 多次）只留一条，但每个
    venue 各计一次命中（venue_counts / 论文的 venues / venue_hits）；
    citationCount 保留跨副本最大值。
    返回 {"papers", "venue_counts", "unique_papers", "total_records", "duplicates"}。
    """
    by_key: dict[tuple[str, int], dict] = {}
    total_records = 0
    for path in paths:
        with io.open(path, encoding="utf-8") as f:
            obj = json.loads(f.read())
        for p in _papers_from(obj):
            total_records += 1
            title = p.get("title")
            year = p.get("year")
            if not isinstance(title, str) or not title.strip() or not year:
                continue
            key = (title.strip().lower(), year)
            rec = by_key.get(key)
            if rec is None:
                rec = dict(p)
                rec["_venues"] = []
                by_key[key] = rec
            v = p.get("venue")
            if isinstance(v, str) and v and v not in rec["_venues"]:
                rec["_venues"].append(v)
            cc = p.get("citationCount")
            if isinstance(cc, int) and cc > (rec.get("citationCount") or 0):
                rec["citationCount"] = cc

    papers: list[dict] = []
    venue_counts: dict[str, int] = {}
    for rec in by_key.values():
        venues = sorted(rec.pop("_venues"))
        rec["venues"] = venues
        rec["venue_hits"] = len(venues)
        papers.append(rec)
        for v in venues:
            venue_counts[v] = venue_counts.get(v, 0) + 1
    papers.sort(key=lambda r: (-(r.get("citationCount") or 0), r.get("title") or ""))
    return {
        "papers": papers,
        "venue_counts": venue_counts,
        "unique_papers": len(papers),
        "total_records": total_records,
        "duplicates": total_records - len(papers),
    }


# ---------------------------------------------------------------------------
# 机会式采集：波次爬取记录 S2 返回 paper 的真实 venue 串 -> multivenue_observed.json
# ---------------------------------------------------------------------------
def _load_observed(observed_path: Path | None = None) -> dict[str, int]:
    """读 observed.json -> {venue 串: 计数}。兼容 {"observed": {...}} 包装与裸 {...} 形态。"""
    path = observed_path if observed_path is not None else OBSERVED_PATH
    try:
        if path.exists():
            with io.open(path, encoding="utf-8") as f:
                doc = json.loads(f.read())
        else:
            doc = {}
    except (OSError, json.JSONDecodeError):
        doc = {}
    observed = doc.get("observed") if isinstance(doc, dict) else doc
    if not isinstance(observed, dict):
        return {}
    return {
        k: v for k, v in observed.items()
        if isinstance(k, str) and k and isinstance(v, int)
    }


def _write_observed(counter: Counter, observed_path: Path | None = None) -> None:
    """把 {venue: 计数} 落盘 observed.json（按计数降序），供 --harvest 与人工审阅。"""
    path = observed_path if observed_path is not None else OBSERVED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "updated_at": _now(),
        "note": (
            "波次爬取机会式采集：S2 返回 paper 的 venue 字段串 -> 出现计数。"
            "用 --harvest 生成建议新增规范串（计数 >= %d 且 VENUES 未精确收录）。"
            % HARVEST_MIN_COUNT
        ),
        "observed": dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False, indent=1)
    )


def harvest_suggestions(min_count: int = HARVEST_MIN_COUNT,
                        observed: dict[str, int] | None = None) -> list[dict]:
    """从 observed 计数生成"建议新增规范串"清单。

    建议条件：计数 >= min_count 且该串未被 VENUES 精确收录（VENUE_SET）。
    返回 [{"venue": 串, "count": 计数}]，按计数降序（平局按字典序）。
    observed 缺省时读 multivenue_observed.json。
    """
    if observed is None:
        observed = _load_observed()
    known = VENUE_SET
    suggestions = [
        {"venue": venue, "count": count}
        for venue, count in sorted(observed.items(), key=lambda kv: (-kv[1], kv[0]))
        if count >= min_count and venue not in known
    ]
    return suggestions



class Pacer:
    """请求间最小间距节流（首个请求不等待）。"""

    def __init__(self, gap_s: float = REQUEST_GAP_S, enabled: bool = True):
        self.gap_s = gap_s
        self.enabled = enabled
        self._last = 0.0

    def wait(self) -> None:
        if self.enabled:
            delta = time.time() - self._last
            if delta < self.gap_s:
                time.sleep(self.gap_s - delta)
        self._last = time.time()


def _curl_json(url: str) -> dict | None:
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(CURL_TIMEOUT_S), url],
        capture_output=True,
    )
    if r.returncode != 0:
        return None
    txt = r.stdout.decode("utf-8", "replace").strip()
    if not txt.startswith("{"):
        return None  # 429 文本/HTML 包装或其他错误
    try:
        d = json.loads(txt)
    except json.JSONDecodeError:
        return None
    return d if isinstance(d.get("data"), list) else None


def s2_fetch(url: str, counters: dict, pacer: Pacer) -> dict | None:
    """单次请求；429/miss 重试一次，且重试前经 pacer.wait() 等满 75s 间距下限——
    任意两次 curl 间距 >= REQUEST_GAP_S（attempts 计 curl 次数；成功由调用方计预算）。"""
    for attempt in (1, 2):
        counters["attempts"] += 1
        d = _curl_json(url)
        if d is not None:
            return d
        if attempt == 1:
            print(f"[429/miss] 等满 {REQUEST_GAP_S}s 间距下限后重试一次: {url[:100]}",
                  flush=True)
            pacer.wait()
    return None


def _now() -> str:
    return f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}"


def _stop_reason(budget: dict, limit: int, t0: float, wall_s: float) -> str | None:
    if budget["used"] >= limit:
        return "request-budget"
    if time.time() - t0 > wall_s:
        return "wall-clock"
    return None


# ---------------------------------------------------------------------------
# --probe：venue 精确串探测（round-3 式耐心重扫）
# ---------------------------------------------------------------------------
def _parse_venue_filter(venue_filter: str | None) -> set[str] | None:
    """--venue 参数（逗号分隔的 venue 短名/类别名）-> 小写集合；None/空 -> None（全选）。"""
    if not venue_filter:
        return None
    return {s.strip().lower() for s in venue_filter.split(",") if s.strip()}


def _venue_selected(key: str, cat: str, names: set[str] | None) -> bool:
    """--venue 过滤：names 为小写短名/类别名集合；None 表示全选。"""
    if not names:
        return True
    return key.lower() in names or cat.lower() in names


def run_probe(limit_requests: int, dry_run: bool, wall_s: float = PROBE_WALL_S,
              venue_filter: str | None = None) -> int:
    """对每个候选串跑 query=<串>&venue=<串>，取 top5 venue 字段众数为规范串。

    人工不可介入；结果落 multivenue_strings.json（resolved + unresolved[tried]）。
    单次 429 不放弃：该候选串留在轮换中，后续轮次继续重试，直到预算/墙钟截止。
    增量续跑：multivenue_strings.json 中已 resolved 的 venue 沿用上次结果并跳过，
    因此可用 --deadline-minutes 分段多次运行逐步补齐（段间不重复消耗已解析 venue）。
    """
    budget = {"used": 0, "attempts": 0}  # used=成功响应数（预算口径），attempts=curl 总次数
    pacer = Pacer(enabled=not dry_run)
    t0 = time.time()

    order = [
        key for cat in PROBE_ORDER for key in VENUE_NAMES[cat]
        if _venue_selected(key, cat, _parse_venue_filter(venue_filter))
    ]
    # 每 venue 状态：exhausted[i]=True 表示第 i 个候选已拿到数据但无众数（不再试）
    state = {
        key: {
            "ptr": 0,
            "exhausted": [False] * len(CANDIDATES[key]),
            "tried": [],
            "observed": [],
            "attempts": 0,
            "hit": None,
        }
        for key in order
    }
    # 增量续跑：strings.json 里已 resolved 的 venue 直接带入，不重复探测
    prev_resolved = _STRINGS.get("resolved") or {}
    for key in order:
        prev = prev_resolved.get(key)
        if isinstance(prev, str) and prev:
            state[key]["hit"] = {
                "string": prev, "votes": "carried-over", "queried_with": None,
                "carried_over": True,
            }
            print(f"[CARRY] {key} -> {prev!r}（沿用上次探测结果）", flush=True)

    def venue_done(key: str) -> bool:
        st = state[key]
        return st["hit"] is not None or all(st["exhausted"])

    def sweep() -> str | None:
        """对所有未完成 venue 各发一次请求；返回截止原因（无则 None）。"""
        for key in order:
            if venue_done(key):
                continue
            stop = None if dry_run else _stop_reason(budget, limit_requests, t0, wall_s)
            if stop:
                return stop
            st = state[key]
            cands = CANDIDATES[key]
            n = len(cands)
            while st["exhausted"][st["ptr"] % n]:
                st["ptr"] += 1
            cand = cands[st["ptr"] % n]
            st["ptr"] += 1
            url = (
                S2_SEARCH
                + "?query=" + urllib.parse.quote(cand)
                + "&venue=" + urllib.parse.quote(cand)
                + f"&limit={PROBE_TOP_K}&fields=title,year,venue"
            )
            if dry_run:
                print(f"[DRY] probe {key} <- {cand!r}", flush=True)
                continue
            pacer.wait()
            d = s2_fetch(url, budget, pacer)
            st["attempts"] += 1
            if cand not in st["tried"]:
                st["tried"].append(cand)
            if d is None:
                print(f"[miss] probe {key} <- {cand!r}  ({_now()})", flush=True)
                continue
            budget["used"] += 1
            idx = cands.index(cand)
            seen = [
                p["venue"] for p in d["data"]
                if isinstance(p.get("venue"), str) and p["venue"]
            ]
            st["observed"].extend(seen)
            if not seen:
                st["exhausted"][idx] = True  # 有数据但无 venue 字段：此候选串无效
                continue
            top, votes = Counter(seen).most_common(1)[0]
            if votes >= 2 or len(seen) == 1:
                st["hit"] = {"string": top, "votes": f"{votes}/{len(seen)}", "queried_with": cand}
                print(f"[RESOLVED] {key} -> {top!r} ({votes}/{len(seen)})  ({_now()})", flush=True)
            else:
                st["exhausted"][idx] = True  # 有数据但无众数：换下一候选
                print(f"[no-majority] {key} <- {cand!r} seen={sorted(set(seen))[:3]}", flush=True)
        return None

    if dry_run:
        sweep()
        print(f"[DRY] probe 预算 {limit_requests}（按成功响应计），候选串总数 "
              f"{sum(len(v) for v in CANDIDATES.values())}", flush=True)
        return 0

    stop = None
    while True:
        stop = sweep()
        if stop or all(venue_done(k) for k in order):
            break
        time.sleep(SWEEP_GAP_S)

    resolved = {k: state[k]["hit"]["string"] for k in order if state[k]["hit"]}
    detail = {k: state[k]["hit"] for k in order if state[k]["hit"]}
    unresolved = {}
    for k in order:
        if state[k]["hit"]:
            continue
        st = state[k]
        reason = stop or "no-majority"
        unresolved[k] = {
            "tried": st["tried"],
            "observed_venues": sorted(set(st["observed"]))[:5],
            "reason": reason,
            "attempts": st["attempts"],
        }
        print(f"[UNRESOLVED] {k} ({reason}) tried={st['tried']}", flush=True)

    # 本次未涉及的 venue：沿用 strings.json 既有记录（--venue 过滤探测时不丢成果）
    for k, v in prev_resolved.items():
        if k not in state and k not in resolved:
            resolved[k] = v
    for k, v in (_STRINGS.get("unresolved") or {}).items():
        if k not in state and k not in resolved:
            unresolved[k] = v

    doc = {
        "probed_at": _now(),
        "probe_method": (
            f"对每候选串跑 query=<串>&venue=<串>&limit={PROBE_TOP_K}，"
            "取返回 top5 的 venue 字段众数（>=2 票或唯一结果）为规范串"
        ),
        "request_budget": {"successful": budget["used"], "attempts": budget["attempts"],
                           "limit": limit_requests},
        "stop_reason": stop,
        "resolved": resolved,
        "unresolved": unresolved,
        "detail": detail,
    }
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    io.open(STRINGS_PATH, "w", encoding="utf-8").write(
        json.dumps(doc, ensure_ascii=False, indent=1)
    )
    print(
        f"[WRITE] {STRINGS_PATH.name}: resolved={len(resolved)} "
        f"unresolved={len(unresolved)} successful={budget['used']}/{limit_requests} "
        f"attempts={budget['attempts']}",
        flush=True,
    )
    return 0


# ---------------------------------------------------------------------------
# --wave：主题切片爬取（round-3 式耐心重扫）
# ---------------------------------------------------------------------------
def run_wave(wave: str, venue_filter: str | None, limit_requests: int, dry_run: bool,
             wall_s: float = WAVE_WALL_S) -> int:
    budget = {"used": 0, "attempts": 0}  # used=成功响应数（预算口径）
    pacer = Pacer(enabled=not dry_run)
    t0 = time.time()
    names = _parse_venue_filter(venue_filter)
    observed = Counter(_load_observed())  # 机会式采集：venue 串 -> 计数（跨运行累加）

    for cat, topics in WAVE_TOPICS[wave]:
        for key in VENUE_NAMES[cat]:
            if not _venue_selected(key, cat, names):
                continue
            out_path = CORPUS_DIR / f"multivenue_{key.lower()}.json"
            if out_path.exists():
                print(f"[SKIP] {key}: {out_path.name} 已存在（幂等）", flush=True)
                continue

            venue_str = canonical_string(key)
            queries: dict[str, dict] = {}
            truncated_by: str | None = None
            pending = list(topics)
            attempts_this_venue = 0

            while pending:
                progressed = False
                for topic in list(pending):
                    stop = None if dry_run else _stop_reason(budget, limit_requests, t0, wall_s)
                    if stop:
                        truncated_by = stop
                        break
                    url = slice_query(venue_str, topic)
                    if dry_run:
                        print(f"[DRY] {key} ({venue_str!r}) <- {topic!r}\n       {url}", flush=True)
                        continue
                    pacer.wait()
                    d = s2_fetch(url, budget, pacer)
                    attempts_this_venue += 1
                    if d is None:
                        queries[topic] = {"error": "429/miss after 1 retry (will re-sweep)"}
                        print(f"[FAIL] {key} | {topic}  ({_now()})", flush=True)
                        continue
                    budget["used"] += 1
                    progressed = True
                    # 机会式采集：记录返回 paper 的真实 venue 串（含被拒的邻居串，
                    # 它们揭示 S2 venue= 模糊过滤实际命中的规范串，喂给 --harvest）
                    for p in d["data"]:
                        pv = p.get("venue") if isinstance(p, dict) else None
                        if isinstance(pv, str) and pv:
                            observed[pv] += 1
                    _write_observed(observed)
                    kept = [p for p in d["data"] if venue_of(p)]
                    queries[topic] = {
                        "total": d.get("total", len(kept)),
                        "kept": len(kept),
                        "papers": kept,
                    }
                    pending.remove(topic)
                    print(
                        f"[OK] {key} | {topic}: total={queries[topic]['total']} "
                        f"kept={len(kept)} (budget {budget['used']}/{limit_requests})  ({_now()})",
                        flush=True,
                    )
                if dry_run:
                    break
                if truncated_by or not pending:
                    break
                if not progressed:
                    time.sleep(SWEEP_GAP_S)

            if dry_run:
                continue
            if not any("papers" in q for q in queries.values()):
                print(f"[SKIP-WRITE] {key}: 无任何成功查询，不写文件（下次运行重试）", flush=True)
                continue
            doc = {
                "venue": key,
                "category": cat,
                "canonical_venue_string": venue_str,
                "wave": wave,
                "generated_at": _now(),
                "topics": topics,
                "request_budget": {"successful": budget["used"], "limit": limit_requests,
                                   "attempts": attempts_this_venue},
                "truncated_by": truncated_by,
                "failed_queries": sum(1 for q in queries.values() if "error" in q),
                "queries": queries,
            }
            io.open(out_path, "w", encoding="utf-8").write(
                json.dumps(doc, ensure_ascii=False, indent=1)
            )
            print(f"[WRITE] {out_path.name}  ({_now()})", flush=True)

    print(
        f"DONE wave {wave}: successful={budget['used']}/{limit_requests} "
        f"attempts={budget['attempts']}"
        f"{'' if dry_run else ' — 按幂等规则重复运行可续爬未完成 venue'}",
        flush=True,
    )
    return 0


def run_harvest(min_count: int = HARVEST_MIN_COUNT) -> int:
    """--harvest：读 observed.json 打印建议新增规范串清单（人工审核后并入 CANDIDATES）。"""
    suggestions = harvest_suggestions(min_count=min_count)
    for s in suggestions:
        print(f"{s['count']:>6}  {s['venue']}")
    print(
        f"共 {len(suggestions)} 条建议新增规范串（计数 >= {min_count} 且 VENUES 未精确收录；"
        f"源 {OBSERVED_PATH.name}）",
        flush=True,
    )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="多顶会主题切片爬虫（S2 Graph API；详见模块 docstring 的幂等/限流规则）"
    )
    ap.add_argument("--wave", choices=("A", "B"),
                    help="爬取波次：A=语音近邻+NLP 核心；B=ML/多媒体/交叉(+CV 仅音视)")
    ap.add_argument("--probe", action="store_true",
                    help="venue 精确串探测（每候选串 1 请求，写 multivenue_strings.json）")
    ap.add_argument("--harvest", action="store_true",
                    help="读 multivenue_observed.json 输出建议新增规范串清单"
                         f"（计数 >= {HARVEST_MIN_COUNT} 且 VENUES 未精确收录）")
    ap.add_argument("--venue", metavar="NAME",
                    help="只处理指定 venue 短名/类别名（如 SLT、speech_adj），逗号分隔可多个")
    ap.add_argument("--limit-requests", type=int, default=None, metavar="N",
                    help="成功响应预算上限（默认：--probe 为 40，--wave 为 90）")
    ap.add_argument("--deadline-minutes", type=int, default=None, metavar="M",
                    help="墙钟上限（分钟；默认 probe=120，wave=240）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将发起的 URL，不发请求")
    args = ap.parse_args(argv)

    if args.probe:
        limit = args.limit_requests if args.limit_requests is not None else 40
        wall = (args.deadline_minutes * 60) if args.deadline_minutes else PROBE_WALL_S
        return run_probe(limit, args.dry_run, wall, args.venue)
    if args.harvest:
        return run_harvest()
    if not args.wave:
        ap.error("需要 --wave A|B 或 --probe/--harvest 之一")
    limit = args.limit_requests if args.limit_requests is not None else 90
    wall = (args.deadline_minutes * 60) if args.deadline_minutes else WAVE_WALL_S
    return run_wave(args.wave, args.venue, limit, args.dry_run, wall)


if __name__ == "__main__":
    sys.exit(main())
