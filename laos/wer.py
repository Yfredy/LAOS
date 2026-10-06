"""laos.wer —— ASR 评测指标：词错率 WER / 字错率 CER（纯标准库）。

来源：docs/research/2026-10-06-cactus-whistle-adoption.md——端侧 ASR 通道
接入前的效果量化（"先测效果再接入"是硬闸门）。中文按字级 CER、英文按词级
WER；归一化统一处理大小写、标点（含中文标点）、全角/半角、空白折叠。

编辑距离为经典 Levenshtein DP（两行滚动数组，O(len·len) 时间、O(len) 空间），
对 ≤30s 转写文本（几百词）瞬时完成；不做前缀/后缀修剪——评测口径要的是
教科书定义，不是被修剪美化过的数字。
"""
from __future__ import annotations

import re
import string
import unicodedata

__all__ = ["edit_distance", "normalize", "wer", "cer"]

_CJK_PUNCT = "，。！？；：、""''（）《》〈〉【】…—·～"
_PUNCT_MAP = {ord(c): " " for c in string.punctuation}
_PUNCT_MAP.update({ord(c): None for c in _CJK_PUNCT})


def normalize(text: str) -> str:
    """转写文本归一化：NFKC 全角→半角、去各类标点、折叠空白、小写。

    中文内容原样保留（汉字不受上述任何一步影响）。
    """
    s = unicodedata.normalize("NFKC", str(text))
    s = s.translate(_PUNCT_MAP)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def edit_distance(a, b) -> int:
    """Levenshtein 编辑距离。a/b 为序列（str 或 list）。"""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1,        # 删除
                         cur[j - 1] + 1,     # 插入
                         prev[j - 1] + (ca != cb))  # 替换/保留
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> float:
    """词错率 = 编辑距离(词序列) / 参照词数。归一化后按空白切词。

    参照为空是评测配置错误（无答案不可评分）→ ValueError；
    假设为空（模型装死）→ 1.0 满错。
    """
    r, h = normalize(ref).split(), normalize(hyp).split()
    if not r:
        raise ValueError("empty reference text")
    return edit_distance(r, h) / len(r)


def cer(ref: str, hyp: str) -> float:
    """字错率 = 编辑距离(去空白字符序列) / 参照字数。中文主用。"""
    r = normalize(ref).replace(" ", "")
    h = normalize(hyp).replace(" ", "")
    if not r:
        raise ValueError("empty reference text")
    return edit_distance(r, h) / len(r)
