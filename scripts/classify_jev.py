#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify_jev.py —— Jev 生态分类、入表与端侧初筛（Task 3）。

读 `docs/research/jev/repos_raw.jsonl`（Task 2 交付的 778 条干净集），
对每条仓库推断四字段并落盘 `repos_classified.jsonl`：
    category     ∈ {官方/客户端/复现/复现(单token打分)/应用/清单/评测/工具}
    laos_fit     ∈ {core/ref/unrelated}
    fit_notes    短说明（仅落 jsonl，不进 12 列表）
    verify_state ∈ {已实测/已读代码/仅README/未核实}

随后按 8 类生成三份分档文档（各含 12 列表），供 check_jev_table.py 校验。

判据刚性（口径文件 J9 / Global Constraints）：
  * 复现 vs 复现(单token打分) 必须区分——前者真训非自回归决策头，后者借 LM 首 token。
  * 官方/客户端 封装云端 API → laos_fit=unrelated（违反本地优先）。
  * core 只在「已证明可端侧跑」的候选上给（本阶段仅 edgejev / laya-rust）。
  * 查不到的字段一律写 未知 / 未核实，不编造。
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

BASE = Path(r"C:/Users/yaoyue/CodeBuddy/Claw/laos/docs/research/jev")
RAW = BASE / "repos_raw.jsonl"
OUT_JSONL = BASE / "repos_classified.jsonl"

DOC_01 = BASE / "01-official-and-clients.md"
DOC_02 = BASE / "02-oss-reproductions.md"
DOC_03 = BASE / "03-oss-applications.md"

CATS = ["官方", "客户端", "复现", "复现(单token打分)", "应用", "清单", "评测", "工具"]

COLUMNS = ["项目", "类别", "星数", "语言", "许可", "运行时依赖",
           "端侧可跑", "原语", "报告延迟", "laos 落点", "验证状态", "来源"]

# ---------------------------------------------------------------------------
# 候选池逐条覆盖（来自 00-taxonomy-and-metrics.md §8 的实测线索 + fetch Top20 新发现）。
# 星数/语言/许可 优先取 API 原值；此处只覆盖「口径文件已实测/明确标注」的属性，
# 其余一律 未知 / 未核实，不编造。每条 tuple：
#   (cat, fit, notes, dep, edge, lat, prim, point, base, verify)
# 任一为 None → 走按类别取的默认值。
# ---------------------------------------------------------------------------
CURATED = {
    # ---- 官方 / 客户端（封装云端 API → unrelated）----
    "browser-use/jev-ultrafast": (
        "客户端", "unrelated",
        "browser-use 官方参考超快客户端；依赖 TypeSafe 云端 API（中国大陆未开放），laos 不能直接作运行时依赖",
        "未知", "no", "未实测", "组合", "不值得（官方云端 API）", None, None),
    "typesafe-ai/skills": (
        "官方", "unrelated",
        "TypeSafe 官方 agent skills，依赖官方云端 API，不得作运行时依赖",
        "云端API", "no", "未实测", "组合", "不值得（官方云端 API）", None, None),
    "jkudish/jev-mcp": (
        "客户端", "unrelated", "Jev MCP server，封装官方 API",
        "云端API", "no", "未实测", "组合", "不值得（云端 API 封装）", None, None),
    "jkudish/jev-browser": (
        "客户端", "unrelated", "Jev 浏览器自动化客户端，封装官方 API",
        "云端API", "no", "未实测", "组合", "不值得（云端 API 封装）", None, None),
    "itsmostafa/typesafe-mcp": (
        "客户端", "unrelated", "TypeSafe MCP 客户端，封装官方 API",
        "云端API", "no", "未实测", "组合", "不值得（云端 API 封装）", None, None),
    "dabit3/jev-experiments": (
        "客户端", "unrelated", "官方 API 实验，封装云端 API",
        "云端API", "no", "未实测", "组合", "不值得（云端 API 封装）", None, None),
    "dbreunig/building-with-jev-skill": (
        "客户端", "unrelated", "构建 Jev skill 的示例，依赖官方 API",
        "云端API", "no", "未实测", "组合", "不值得（云端 API 封装）", None, None),

    # ---- 真复现（非自回归决策头）----
    "yzfly/edgejev": (
        "复现", "core",
        "README 称 CPU 单题 15.6 ms、模型 324 MB、运行时不依赖 torch；端侧风险最低，待 Task 4 实测",
        "未知", "yes", "15.6 ms 未实测", "组合", "漏斗③蒸馏 / 漏斗①触发（候选）", None, "仅README"),
    "wfzyx/von": (
        "复现", "ref",
        "Apache-2.0，称 sub-15ms 非自回归；需自训/权重，校准与端侧可行性待 Task 4 实测",
        "未知", "unknown(未实测)", "15 ms 未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "Heman10x-NGU/openJev-verdict-2.0": (
        "复现", "ref",
        "ModernBERT 151M，称 77.10% acc / Brier 0.0636；需校准验证",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", "ModernBERT 151M", "仅README"),
    "Heman10x-NGU/Verdict-open-jev": (
        "复现", "ref", "Verdict 系列开源复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "receptron/laya": (
        "复现", "ref", "Laya typed decision 运行时复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "aovestdipaperino/laya-rust": (
        "复现", "core",
        "纯 Rust 推理，无 torch 依赖，端侧风险最低；待 Task 4 实测",
        "rust", "yes", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "jaredpalmer/kev": (
        "复现", "ref",
        "Apache-2.0，Qwen2.5-0.5B 可自训练；基座较大，端侧需量化",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", "Qwen2.5-0.5B", "仅README"),
    "TianyuCodings/NanoJev": (
        "复现", "ref", "MIT，nano 级复现 + 端到端训练管线",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "zhihz/openjev": (
        "复现", "ref", "双语开源复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "kshetrajna12/reflex": (
        "复现", "ref", "MIT，Qwen3.5 基座复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", "Qwen3.5", "仅README"),
    "logan-markewich/jeff": (
        "复现", "ref", "自托管 drop-in 复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "Argos1111/jev_local": (
        "复现", "ref", "本地 Jev 复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "intikhab49/open-jev-typed-decision-engine": (
        "复现", "ref", "开源 typed decision engine 复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "mkeco/Cerebellum-2B": (
        "复现", "ref", "Cerebellum-2B 复现",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "TheoLeeCJ/SemIf": (
        "复现", "ref",
        "MIT，基于开放模型的家庭 GPU 语义 if（非自回归决策），端侧需量化",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", "开放模型", "仅README"),

    # ---- 复现(单token打分)（借 LM 首 token logits，无需自训）----
    "Yinsongxu/LLM2Jev": (
        "复现(单token打分)", "ref",
        "Apache-2.0，借用现成 LM 首 token logits 当打分，无需自训；校准性依赖基座 LM",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏（范式参考，非真复现）", None, "仅README"),
    "featherless-ai/simple-jev": (
        "复现(单token打分)", "ref",
        "借用现成 LM 首 token logits，无需自训",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏（范式参考）", None, "仅README"),
    "APUS-AI-Lab/fast-browser-use": (
        "复现(单token打分)", "ref",
        "MIT，Qwen3.5-9B 本地推理（单 token 打分），9B 过大不适合端侧",
        "未知", "no", "未实测", "组合", "参考（基座过大）", "Qwen3.5-9B", "仅README"),

    # ---- 语音 / 音频 + Jev（与 laos 最贴近，应用类）----
    "moritzkremb/jev-voice-browser": (
        "应用", "ref", "语音+浏览器应用，Jev 经云端 API，本地仅 STT",
        "云端API", "no", "未实测", "组合", "漏斗③蒸馏（STT 先例）", None, "仅README"),
    "kevinbadi/jev-voice": (
        "应用", "ref", "local whisper.cpp + one Jev call；STT 本地、Jev 走云端",
        "云端API", "no", "未实测", "组合", "常驻语音（STT 先例）", None, "仅README"),
    "chasemc67/Jevis": (
        "应用", "ref",
        "Jev-filtered always-on speech harness: mic→STT→Jev→text，常驻语音最贴近 laos 的先例",
        "云端API", "no", "未实测", "组合", "常驻语音（架构先例）", None, "仅README"),
    "sgaabdu4/capture": (
        "应用", "ref", "Private Mac voice diary：本地 Parakeet 转写 + Jev 分类",
        "云端API", "no", "未实测", "组合", "常驻语音（隐私本地转写先例）", None, "仅README"),
    "nikotaronosuke/jev-voice-decision": (
        "应用", "ref", "语音决策小项目",
        "云端API", "no", "未实测", "组合", "常驻语音", None, "仅README"),
    "santos-sanz/jev-audio-beeper": (
        "应用", "ref", "音频 beeper 小项目",
        "未知", "unknown(未实测)", "未实测", "组合", "常驻语音", None, "仅README"),
    "winter-loo/jev-voice-browser": (
        "应用", "ref", "语音浏览器小项目",
        "云端API", "no", "未实测", "组合", "常驻语音", None, "仅README"),

    # ---- Android / 移动端（应用类）----
    "droidrun/mobile-jev": (
        "应用", "ref",
        "官方引用，真机驱动 Uber：9 动作约 21 s 未完成下单；移动端 agent 先例",
        "云端API", "no", "未实测", "组合", "参考（移动端 agent）", None, "仅README"),
    "ufec/jev-block-android-ad": (
        "应用", "ref", "JevNoiseGate 过滤通知/短信，移动端噪声门先例",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（移动端噪声门）", None, "仅README"),
    "antiyro/jevdroid": (
        "应用", "ref", "ADB + typed Python 移动端",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（移动端）", None, "仅README"),
    "Friedjof/jev-mobile": (
        "应用", "ref", "移动端 Jev",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（移动端）", None, "仅README"),
    "dougsong/jev-android": (
        "应用", "ref", "Kotlin Android SDK，端侧 SDK 先例",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（Android SDK）", None, "仅README"),

    # ---- 清单（awesome，unrelated）----
    "yibie/awesome-jev": (
        "清单", "unrelated", "awesome 清单，非可运行组件",
        "未知", "unknown(未实测)", "未实测", "-", "不值得（清单类）", None, "仅README"),
    "Anil-matcha/awesome-jev-by-typesafe": (
        "清单", "unrelated", "awesome 清单",
        "未知", "unknown(未实测)", "未实测", "-", "不值得（清单类）", None, "仅README"),
    "v-modal/awesome-jev-tools": (
        "清单", "unrelated", "awesome 清单",
        "未知", "unknown(未实测)", "未实测", "-", "不值得（清单类）", None, "仅README"),
    "cobanov/awesome-jev": (
        "清单", "unrelated", "awesome 清单",
        "未知", "unknown(未实测)", "未实测", "-", "不值得（清单类）", None, "仅README"),
    "AbdelStark/awesome-typesafe": (
        "清单", "unrelated", "awesome 清单",
        "未知", "unknown(未实测)", "未实测", "-", "不值得（清单类）", None, "仅README"),

    # ---- 评测（benchmark，ref）----
    "fstandhartinger/jevbench": (
        "评测", "ref", "Jev 基准测试",
        "未知", "unknown(未实测)", "未实测", "-", "参考（校准/评测方法）", None, "仅README"),
    "AbdelStark/jev-benchmarks": (
        "评测", "ref", "Jev 基准",
        "未知", "unknown(未实测)", "未实测", "-", "参考（校准/评测方法）", None, "仅README"),
    "wondertwins/jev-benchmark": (
        "评测", "ref", "Jev 基准",
        "未知", "unknown(未实测)", "未实测", "-", "参考（校准/评测方法）", None, "仅README"),

    # ---- 其他应用 ----
    "kerpopule/hermes-jev-skills": (
        "应用", "ref",
        "Jev 驱动的 model routing / memory / compaction / skill selection，决策模式参考",
        "云端API", "no", "未实测", "组合", "Brain 路由 / 技能路由", None, "仅README"),
    "tamaratran/fast-jev-compaction": (
        "应用", "ref",
        "MIT，用 Jev 决策替代 compaction 摘要，stale 丢弃/截断",
        "云端API", "no", "未实测", "组合", "上下文压缩", None, "仅README"),
    "leepokai/jev-guard": (
        "应用", "ref", "deny/ask/allow 闸门，决策模式参考",
        "云端API", "no", "未实测", "组合", "不可逆闸门", None, "仅README"),
    "realZachi/pg-jev": (
        "应用", "ref", "Postgres + Jev 应用",
        "云端API", "no", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "superagents-lab/jev-search": (
        "应用", "ref", "Jev 搜索应用",
        "云端API", "no", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "devagrawal09/jev-review": (
        "应用", "ref", "Jev 评审应用",
        "云端API", "no", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "thruwire/foreman": (
        "应用", "ref", "foreman agent 应用",
        "云端API", "no", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "ChetasLua/jevmeter": (
        "应用", "ref", "Jev 计量/评测小工具",
        "未知", "unknown(未实测)", "未实测", "-", "参考", None, "仅README"),
    "AboveColin/HA-Jev": (
        "应用", "ref", "Home Assistant + Jev",
        "云端API", "no", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "jarrodwatts/jev-trader": (
        "应用", "unrelated",
        "交易决策，领域与 laos 音频无关；且依赖官方 API",
        "云端API", "no", "未实测", "组合", "不值得（领域不符+云端）", None, "仅README"),

    # ---- fetch Top20 新发现（非候选池，但高星，需逐条核实）----
    "OpenByteInc/QuantDinger": (
        "应用", "unrelated",
        "交易 OS，集成官方 Jev API；领域不符且云端",
        "云端API", "no", "未实测", "组合", "不值得（领域不符+云端）", None, "仅README"),
    "mizorewww/laya-mlx": (
        "复现", "ref",
        "Apache-2.0，Laya typed decision 的 MLX 原生运行时，M3 Max 7–14 ms，无文本生成/PyTorch/云端；但 MLX 仅 Apple Silicon，不适用于 Android proot",
        "未知", "no", "7–14 ms 未实测", "组合", "漏斗③蒸馏（Apple Silicon 限定）", "Laya/MLX", "仅README"),
    "vinnylarouge/jevlike": (
        "工具", "ref", "jev-like 项目，description 为空无法判定类型，需人工复核",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（未核实）", None, "未核实"),
    "bespokelabsai/nimble": (
        "复现", "ref",
        "本地 typed decisions + 对比数据策展 + 模型评测；可作复现基线",
        "未知", "unknown(未实测)", "未实测", "组合", "漏斗③蒸馏", None, "仅README"),
    "reticlehq/reticle": (
        "应用", "ref", "Jev-style 机器原生运行时感知，web/desktop agent",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "samuelfaj/distill": (
        "应用", "ref", "轻量 coding agent harness，description 未明确 Jev 用法，需复核",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "milind-soni/tiptour-macos": (
        "应用", "ref", "本地计算机操控，fast local computer use",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "pulseaiclub/phi": (
        "应用", "ref", "coding agent + mcp + 子代理",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（领域应用）", None, "仅README"),
    "Sac-Y/Jev-cu": (
        "工具", "ref", "Jev CUDA 项目，description 为空，需复核",
        "未知", "unknown(未实测)", "未实测", "组合", "参考（未核实）", None, "未核实"),
}


# ---------------------------------------------------------------------------
# 规则兜底分类（仅当不在 CURATED 时调用）
# ---------------------------------------------------------------------------
def classify_rule(name: str, desc: str, topics) -> str:
    n = (name or "").lower()
    d = (desc or "").lower()
    t = " ".join(topics or []).lower()
    blob = n + " " + d + " " + t
    owner = name.split("/")[0].lower() if "/" in name else ""

    if owner == "typesafe-ai":
        return "官方"
    if "awesome" in n or "curated list" in d or "list of" in d or "a list of" in d:
        return "清单"
    if ("bench" in n) or ("benchmark" in blob) or ("leaderboard" in blob) \
       or ("brier" in blob and "benchmark" in blob):
        return "评测"
    if (owner == "browser-use" and "jev-ultrafast" in n) or ("mcp" in blob) \
       or (" sdk" in blob) or ("client" in blob) or n.endswith("-skill") \
       or ("skill" in n and "jev" in n) or ("jev-browser" in n) or ("jev-mcp" in n):
        return "客户端"
    # 单 token 打分（借 LM 首 token logits，无自训）
    if any(k in blob for k in ("single-token", "first token", "logits",
                               "turn any open model", "adapt any local",
                               "adapt local", "llm2jev", "simple-jev",
                               "fast-browser-use", "qwen3.5-9b")):
        return "复现(单token打分)"
    # 真复现（自训非自回归决策头）
    # 注意：reflex / drop-in / openjev(子串) 过宽会误命中「reflex 网关」「drop-in 筛子」
    # 以及 OpenJEVis（Java 能源项目），故只保留带连字符/空格的 open-jev / open jev，
    # 并移除 reflex、drop-in，避免把「用官方 API 的网关」错判成「复现」。
    if any(k in blob for k in ("replica", "reproduc", "non-autoregressive",
                               "end-to-end training", "train and run",
                               "train your own", "open alternative",
                               "nano replica", "tiny jev", "verdict",
                               "typed decision model", "semantic if",
                               "open-jev", "open jev", "cerebellum",
                               "local typed decision")):
        return "复现"
    # 应用（领域信号）
    if any(k in blob for k in ("browser", "voice", "speech", "stt", "whisper",
                               "android", "guard", "triage", "routing",
                               "compaction", "agent", "trader", "trade",
                               "search", "review", "always-on", "always on",
                               "memory", "home assistant", "ha-jev",
                               "computer use", "skill selection",
                               "model routing", "decision")):
        return "应用"
    return "工具"


# ---------------------------------------------------------------------------
# 按类别取的默认值（CURATED 未覆盖时）
# ---------------------------------------------------------------------------
FIT_DEFAULT = {
    "官方": "unrelated", "客户端": "unrelated", "清单": "unrelated",
    "评测": "ref", "工具": "ref", "应用": "ref",
    "复现": "ref", "复现(单token打分)": "ref",
}
NOTES_DEFAULT = {
    "官方": "TypeSafe 官方闭源云端 API，违反 laos 本地优先（中国大陆未开放），不得作运行时依赖",
    "客户端": "封装官方云端 API 的客户端/SDK/MCP，laos 不能依赖云端，标 unrelated",
    "清单": "awesome/清单类聚合，非可运行组件",
    "评测": "基准/评测工具，提供校准与评测方法论参考",
    "工具": "Jev 相关小工具，参考价值，需人工复核",
    "应用": "Jev 领域应用，决策模式参考价值",
    "复现": "开源非自回归决策头复现，端侧可行性待 Task 4 实测",
    "复现(单token打分)": "借用现成 LM 首 token logits 打分，无需自训，校准性依赖基座 LM",
}
EDGE_DEFAULT = {"官方": "no", "客户端": "no"}
PRIM_DEFAULT = {"清单": "-", "评测": "-"}  # 其余 组合
POINT_DEFAULT = {
    "官方": "不值得（官方云端 API）",
    "客户端": "不值得（云端 API 封装）",
    "复现": "漏斗③蒸馏",
    "复现(单token打分)": "漏斗③蒸馏（借用基座 LM 首 token）",
    "应用": "参考（领域应用）",
    "清单": "不值得（清单类）",
    "评测": "参考（校准/评测方法）",
    "工具": "参考",
}


import re

# 语音/常驻：名称中需出现整词的 voice/audio/speech/stt/whisper/asr/mic（避免 mic 误命中 nanmicoder）
VOICE_NAME_RE = re.compile(r"\b(voice|audio|speech|stt|whisper|asr|mic)\b", re.I)

# 判断 description 是否含有 Jev 决策模型的实质信号词（整词匹配，避免 jevis/openjev 子串误判）
SIGNAL_RE = re.compile(r"\bjev\b|\btypesafe\b|decision|system[\s-]?one|typed|calibr|probab", re.I)


def has_jev_signal(desc: str) -> bool:
    return bool(SIGNAL_RE.search(desc or ""))


def detect_false_tag(cat: str, desc: str) -> str:
    # 仅当 description 完全无 Jev 决策实质信号时提示（名称/topic 误命中）
    if not has_jev_signal(desc):
        return "；desc 无 Jev 决策实质信号，疑名称/topic 误命中，需人工复核"
    return ""


def classify_row(r: dict) -> dict:
    name = r.get("full_name", "")
    desc = r.get("description", "") or ""
    topics = r.get("topics") or []
    stars = r.get("stars", 0)
    lang = r.get("language", "") or ""
    lic = r.get("license", "") or ""
    url = r.get("html_url", "") or ""

    if name in CURATED:
        cat, fit, notes, dep, edge, lat, prim, point, _base, verify = CURATED[name]
        dep = dep or "未知"
        edge = edge or EDGE_DEFAULT.get(cat, "unknown(未实测)")
        lat = lat or "未实测"
        prim = prim or PRIM_DEFAULT.get(cat, "组合")
        point = point or POINT_DEFAULT[cat]
        verify = verify or "仅README"
        notes = notes or NOTES_DEFAULT[cat]
    else:
        cat = classify_rule(name, desc, topics)
        # 误命中降级：description 无任何 Jev 决策信号时，复现类降级为工具/应用
        if not has_jev_signal(desc):
            if cat == "复现":
                cat = "工具"
            elif cat == "复现(单token打分)":
                cat = "应用"
        fit = FIT_DEFAULT[cat]
        notes = NOTES_DEFAULT[cat] + detect_false_tag(cat, desc)
        dep = "未知"
        edge = EDGE_DEFAULT.get(cat, "unknown(未实测)")
        lat = "未实测"
        prim = PRIM_DEFAULT.get(cat, "组合")
        point = POINT_DEFAULT[cat]
        # 验证状态：有 description 视为仅 README；空 desc 视为未核实
        verify = "仅README" if desc.strip() else "未核实"

    # 星数/语言/许可 一律取 API 原值；空置为 未知（校验器要求许可非空）
    star_str = str(stars) if stars not in (None, "", 0) else ("0" if stars == 0 else "未知")
    # 注意：stars==0 是真实值（小项目），保留 0；缺失才写 未知
    if stars is None or stars == "":
        star_str = "未知"
    else:
        star_str = str(int(stars))
    lang_str = lang if lang else "未知"
    lic_str = lic if lic else "未知"

    out = dict(r)
    out["category"] = cat
    out["laos_fit"] = fit
    out["fit_notes"] = notes
    out["verify_state"] = verify
    # 还给文档生成用的派生字段（不污染 raw 语义字段）
    out["_dep"] = dep
    out["_edge"] = edge
    out["_lat"] = lat
    out["_prim"] = prim
    out["_point"] = point
    out["_star_str"] = star_str
    out["_lang_str"] = lang_str
    out["_lic_str"] = lic_str
    out["_url"] = url
    return out


def load_raw():
    rows = []
    with open(RAW, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def build_table(rows, columns=COLUMNS):
    lines = []
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for r in rows:
        cells = [
            r["full_name"],
            r["category"],
            r["_star_str"],
            r["_lang_str"],
            r["_lic_str"],
            r["_dep"],
            r["_edge"],
            r["_prim"],
            r["_lat"],
            r["_point"],
            r["verify_state"],
            r["_url"],
        ]
        # 去除单元格内可能破坏表格的管道符
        cells = [str(c).replace("|", "/") for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# 经逐条核实的「语音 + 常驻」先例（与 laos 最贴近的一条线）。
# 仅纳入确为「语音/常驻语音输入 harness」的项目；browser / computer-use / transcript /
# arena / cli 等虽含 audio 字样但非常驻语音录入的，不列入，避免夸大契合度。
VOICE_PRECEDENTS = {
    # 候选池（口径文件 §8 语音线）
    "moritzkremb/jev-voice-browser", "kevinbadi/jev-voice", "chasemc67/Jevis",
    "sgaabdu4/capture", "nikotaronosuke/jev-voice-decision",
    "santos-sanz/jev-audio-beeper", "winter-loo/jev-voice-browser",
    # 778 新发现中逐条核实确为语音/常驻的项目
    "savka777/jev-use", "brudarko/jev-mac-voice", "harshil1712/slidepilot",
    "chris-wozniczek/jev-voice-control", "hari007sh/jev", "gaborishka/jev-canvas",
    "CumulativeWebInc/cwi-voice-command",
}


def voice_always_on(rows):
    # 用整词边界匹配，避免 "mic" 误命中 nanmicoder / micha0827 之类。
    out = []
    for r in rows:
        if r["full_name"] in VOICE_PRECEDENTS or VOICE_NAME_RE.search(r["full_name"]):
            out.append(r)
    return out


def gen_docs(rows):
    # 01: 官方 + 客户端
    f01 = [r for r in rows if r["category"] in ("官方", "客户端")]
    f01.sort(key=lambda r: -(int(r["stars"]) if isinstance(r.get("stars"), (int, float)) else 0))
    doc01 = ["# 01 · Jev 官方与客户端（SDK / MCP / Agent Skill）", "",
             "> 列名逐字照抄 12 列 schema（口径文件 §7）。校验：`check_jev_table.py`。",
             "> 关键判据：官方/客户端封装 TypeSafe 云端 API，中国大陆未开放，",
             "> **laos_fit 一律 unrelated**（违反本地优先，不得作运行时依赖）。", "",
             build_table(f01), ""]
    DOC_01.write_text("\n".join(doc01), encoding="utf-8")

    # 02: 复现 + 复现(单token打分)
    repro = [r for r in rows if r["category"] == "复现"]
    st = [r for r in rows if r["category"] == "复现(单token打分)"]
    repro.sort(key=lambda r: -(int(r["stars"]) if isinstance(r.get("stars"), (int, float)) else 0))
    st.sort(key=lambda r: -(int(r["stars"]) if isinstance(r.get("stars"), (int, float)) else 0))

    doc02 = ["# 02 · Jev 开源复现（本次调研核心文档）", "",
             "> **命门**：`复现` 与 `复现(单token打分)` 必须区分（口径 J9）。",
             "> 前者真训非自回归决策头（需自训/权重）；后者只借现成 LM 首 token logits 打分。",
             "> 不区分会得出「端侧跑 Jev 只要 15 ms」的错结论。", "",
             "## 2.1 真复现（非自回归决策头，需自训/权重）", "",
             build_table(repro), "",
             "## 2.2 复现(单token打分)（借 LM 首 token logits，无需自训）", "",
             build_table(st), "",
             "## 2.3 每条复现的「四问核查」", "",
             "> 四问：①是否真非自回归 ②基座模型与参数量 ③是否需要自训练 ④许可。查不到写 未知。", ""]
    # 四问核查：只针对 curated 中明确已知的复现
    for r in repro + st:
        name = r["full_name"]
        cat = r["category"]
        base = CURATED.get(name, (None,)*10)[8]
        is_nar = "是（非自回归决策头）" if cat == "复现" else "否（借 LM 首 token logits）"
        need_train = "是（需自训/提供权重）" if cat == "复现" else "否（依赖现成 LM）"
        lic = r["_lic_str"]
        base_s = base if base else "未知"
        doc02.append(f"- **{name}** — ①非自回归：{is_nar}；②基座/参数量：{base_s}；"
                     f"③需自训：{need_train}；④许可：{lic}")
    # 四问核查：覆盖全部 复现/复现(单token打分) 行（含规则分类的未核实项）
    for r in repro + st:
        name = r["full_name"]
        cat = r["category"]
        cbase = CURATED.get(name)
        base = cbase[8] if cbase else None
        is_nar = "是（非自回归决策头）" if cat == "复现" else "否（借 LM 首 token logits）"
        need_train = "是（需自训/提供权重）" if cat == "复现" else "否（依赖现成 LM）"
        lic = r["_lic_str"]
        base_s = base if base else "未知"
        vs = r["verify_state"]
        flag = "【未核实】" if vs == "未核实" else ""
        doc02.append(f"- **{name}**{flag} — ①非自回归：{is_nar}；②基座/参数量：{base_s}；"
                     f"③需自训：{need_train}；④许可：{lic}")
    doc02.append("")
    DOC_02.write_text("\n".join(doc02), encoding="utf-8")

    # 03: 应用 + 清单 + 评测 + 工具
    app = [r for r in rows if r["category"] == "应用"]
    lst = [r for r in rows if r["category"] == "清单"]
    bench = [r for r in rows if r["category"] == "评测"]
    tool = [r for r in rows if r["category"] == "工具"]
    for s in (app, lst, bench, tool):
        s.sort(key=lambda r: -(int(r["stars"]) if isinstance(r.get("stars"), (int, float)) else 0))

    vo = voice_always_on(rows)
    vo.sort(key=lambda r: -(int(r["stars"]) if isinstance(r.get("stars"), (int, float)) else 0))

    doc03 = ["# 03 · Jev 开源应用与生态（browser / voice / android / guard / 清单 / 评测 / 工具）", "",
             "> 列名逐字照抄 12 列 schema。本文件覆盖 应用 / 清单 / 评测 / 工具 四类。", "",
             "## 3.1 语音 + 常驻 先例（与 laos 最贴近的一条线）", "",
             "> 这些项目把 Jev 接到 STT/常驻语音流水线上，是 laos 四段漏斗最贴近的参考。",
             "> 多数 0–3★ 小项目：如实记录，不因其小忽略，也不因其契合夸大成熟度。",
             "> 注意：其中 Jev 调用多数仍走官方云端 API（本地仅 STT），故 laos_fit 多标 ref（架构先例）。", "",
             build_table(vo), "",
             "> 补充（口径文件候选池提及、本次 778 抓取未覆盖）：`chasemc67/Jevis`"
             "（mic→STT→Jev→text 常驻语音 harness）、`sgaabdu4/capture`（本地 Parakeet 转写 + Jev 分类 私人语音日记）、"
             "`winter-loo/jev-voice-browser`，三者是 laos 最贴近的常驻语音先例，建议 Task 4/6 补入实测。", "",
             "## 3.2 应用（browser / android / guard / routing / compaction / 其他）", "",
             build_table(app), "",
             "## 3.3 清单（awesome / curated list，非可运行组件）", "",
             build_table(lst), "",
             "## 3.4 评测（benchmark / calibration）", "",
             build_table(bench), "",
             "## 3.5 工具", "",
             build_table(tool), ""]
    DOC_03.write_text("\n".join(doc03), encoding="utf-8")


def main():
    rows = load_raw()
    out = [classify_row(r) for r in rows]

    # 写分类 jsonl（去掉派生 _ 字段，保持 raw + 4 字段）
    clean = []
    for r in out:
        c = {k: v for k, v in r.items() if not k.startswith("_")}
        clean.append(c)
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for c in clean:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    gen_docs(out)

    # ---- 统计（汇报用）----
    from collections import Counter, defaultdict
    cat_cnt = Counter(r["category"] for r in out)
    cat_star = defaultdict(list)
    for r in out:
        s = r.get("stars")
        if isinstance(s, (int, float)):
            cat_star[r["category"]].append(s)
    fit_cnt = Counter(r["laos_fit"] for r in out)
    repro_n = cat_cnt.get("复现", 0)
    st_n = cat_cnt.get("复现(单token打分)", 0)
    vo = voice_always_on(out)

    print("== 分类总条数:", len(out))
    print("== 各类别条数 / star 中位数:")
    for c in CATS:
        ss = cat_star.get(c, [])
        med = statistics.median(ss) if ss else 0
        print(f"   {c:14s} {cat_cnt.get(c,0):4d}  中位星 {med:.0f}")
    print("== laos_fit:", dict(fit_cnt))
    print("== 复现:", repro_n, " 复现(单token打分):", st_n)
    print("== 语音+常驻先例:", len(vo), "->", [r["full_name"] for r in vo])
    print("== core 列表:")
    for r in out:
        if r["laos_fit"] == "core":
            print("   ", r["full_name"], r["category"], r["stars"], r["verify_state"])


if __name__ == "__main__":
    main()
