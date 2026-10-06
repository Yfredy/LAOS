"""laos.refiner —— AgenticSR 规则版 Refiner：口语转写 → 干净意图文本。

来源：docs/research/2026-10-06-agenticasr-adoption.md——AgenticASR（arXiv
2607.28175）把 ASR 重构为 AgenticSR 任务：输入含填充词/口吃/自我纠正的口语，
输出"说话者最终意图"的干净书面文本。论文 Refiner = Qwen3-4B + LoRA 微调
（端侧小模型微调打赢 Qwen3-560B 零样本：19.7 vs 25.8 WER）。

本模块是该任务的**确定性子集**（纯 stdlib，零依赖）：
1. 填充词去除：纯语气词（呃/嗯/啊/唉/哦 与 uh/um/er/ah/hmm）。
   "那个/这个"是指示词，不当填充词（语境判定交给学习型 Refiner）。
2. 口吃折叠：中文同一字连续 ≥3 折为 1（双叠是合法构词：谢谢/看看/想想）；
   英文同一词连续 ≥2 折为 1（英文双重复即口吃）。
3. 自我纠正解析："不对/不是"须后随逗号或引导词才判为纠正标记（防"这个
   不对需要修改"这类谓语用法误触发）；命中后按标记分段**取最后一段**——
   "最终意图 = 最后一次说出口的内容"（末段与首段共享前缀时即完整重述，
   取末段天然成立）。
4. 清理：重复标点、多余空白。

**已知局限（即论文卖点）**：子句级替换型纠正（"发邮件给张三，不对，我是说
李四"——意图="发邮件给李四"）需要语义对齐，规则版只能给出"李四"。这是
学习型 Refiner（genie 端侧 LLM 通道）的存在理由；本模块是其下界与回退基线。
"""
from __future__ import annotations

import re

__all__ = ["refine", "CORRECTION_MARKERS"]

#: 纯语气词（填充词）。注意：不含"那个/这个"——指示词误删比漏删伤害大。
_FILLERS_ZH = "呃嗯啊唉哦诶"
_FILLERS_EN = {"uh", "um", "er", "ah", "hmm", "umm", "uhh", "erm"}

#: 自我纠正分割标记（正则，命中即分段，取最后一段）。
CORRECTION_MARKERS = [
    # 须后随停顿/引导字，防"这个不对需要修改"这类谓语误触发（ASR 常丢标点，
    # 故 "不对是X" 无逗号形态也认——已知代价："不对，是错的"这类陈述会被当纠正）
    r"不对(?=[，,]|我是说|是说|是)",
    r"不是(?=[，,]|我是说|是说|是)",
    r"我说错[了啦]?[，,]?",
    r"(我是说|是说|准确地说|应该说是|怎么说呢)[，,]?",
    r"(no wait|i mean|or rather)[,.]?",
    r"sorry[,.]",
]
_MARKER_RE = re.compile("|".join(CORRECTION_MARKERS), re.IGNORECASE)


def _strip_fillers(text: str) -> str:
    """删纯语气词（英文按词匹配，防误删子串）。"""
    text = re.sub(f"[{_FILLERS_ZH}]+", " ", text)
    out = []
    for tok in text.split():
        if tok.lower().strip(".,!?;:") in _FILLERS_EN:
            continue
        out.append(tok)
    return " ".join(out)


def _fold_stutter_zh(text: str) -> str:
    """中文口吃折叠：同一字连续 ≥3 折为 1（双叠合法：谢谢/看看/想想）；
    这/那双叠除外（无合法叠词，"这这/那那"必是口吃）。"""
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return re.sub(r"([这那])\1", r"\1", text)


def _fold_stutter_en(text: str) -> str:
    """英文同一词连续 ≥2 折为 1。"""
    return re.sub(r"\b(\w+)( \1\b)+", r"\1", text, flags=re.IGNORECASE)


def _resolve_correction(text: str) -> str:
    """自我纠正：按标记分段，取最后一段（最终意图 = 最后说的内容）。

    末段 <2 字（纠错标记后说半句/只剩残片）时回退前段。无标记原样返回。
    """
    if not _MARKER_RE.search(text):
        return text
    segments = [s for s in _MARKER_RE.split(text) if s and s.strip()]
    if not segments:
        return text
    tail = segments[-1].strip()
    return tail if len(tail) >= 2 else segments[0].strip()


def refine(text: str) -> str:
    """口语转写 → 干净意图文本（AgenticSR 的规则版下界）。幂等。"""
    s = str(text)
    s = _strip_fillers(s)
    s = _resolve_correction(s)
    s = _fold_stutter_zh(s)
    s = _fold_stutter_en(s)
    if _is_cjk(s):
        s = re.sub(r"[，,。！!？?；;、\s]+", "", s)
    else:
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"([.,!?;:])\1+", r"\1", s)
    return s


def _is_cjk(text: str) -> bool:
    """以 CJK 字符为主的文本（中文路径：去空白；否则保留空格）。"""
    s = text.replace(" ", "")
    if not s:
        return False
    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    return cjk * 2 >= len(s)
