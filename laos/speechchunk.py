# laos/speechchunk.py
"""LLM 流式输出 → TTS 友好文本的三段适配层。

语义复现自 voicenpu_engine（Gitee bravexyz，AGPL-3.0）：
- speech_chunk_end()   ← src/llm/rkllm_qwen.cpp completeSpeechChunkEnd()
- clean_for_speech()   ← 同文件 cleanForSpeech()
- normalize_digits_for_speech() ← src/tts/melo_tts.cpp 同名函数

为什么这一层值得进 laos：流式 LLM 回复要在"逐 token 生成"的同时送 TTS
逐句合成，必须等一句话在语义上完整才切；而 TTS 拿到的文本不能带
"乐乐："、<think>、markdown、序号、阿拉伯数字这类会念出来或打断韵律的
东西。上游把这套规则打磨成了纯函数，零依赖、可单测。

字节级语义说明：上游按 UTF-8 字节串操作（逗号检索起点 = 第 15 字节
≈ 5 个汉字，防止"三，"这类过早早停）。Python 侧同样先编码为 UTF-8
字节再按字节执行同一套规则，保证与上游行为逐字节一致。
"""
from __future__ import annotations

# 上游字面量（UTF-8 字节口径）
_SENTENCE_ENDS = ["。".encode(), "！".encode(), "？".encode(), "；".encode()]
_COMMA = "，".encode()
_LIST_SEP = "、".encode()
_ASSISTANT_NAME = "本地语音助手"
_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"
_MARKDOWN = set('#*`$[]{}<>_-|\'"')
_DIGITS_ZH = "零一二三四五六七八九"


def speech_chunk_end(text: str) -> int:
    """流式缓冲里第一个"可送 TTS 的完整句"的字符终点（不含），0=还不够。

    规则（上游优先级）：句末标点（。！？；）立即可切；逗号/顿号须在
    第 15 字节之后才可切；都没有则攒满 14 个 UTF-8 字符兜底切（防
    词中截断导致 TTS 给每个半词配引子+尾静音）。
    """
    data = text.encode("utf-8")
    end = -1
    for punct in _SENTENCE_ENDS:
        pos = data.find(punct)
        if pos != -1:
            end = pos + 3 if end == -1 else min(end, pos + 3)
    comma = data.find(_COMMA, 15)
    if comma != -1:
        end = comma + 3 if end == -1 else min(end, comma + 3)
    sep = data.find(_LIST_SEP, 15)
    if sep != -1:
        end = sep + 3 if end == -1 else min(end, sep + 3)
    if end != -1:
        return len(data[:end].decode("utf-8", errors="ignore"))
    # 兜底：14 个 UTF-8 字符（按码点步进，不切断多字节字符）
    count = 0
    for i, _ in enumerate(text):
        count += 1
        if count == 14:
            return i + 1
    return 0


def clean_for_speech(text: str) -> str:
    """LLM 原始输出 → 可直接朗读的干净文本。

    步骤（与上游同序）：去前导空白 → 去"乐乐：/助手：/机器人："-类
    前缀 → 去"1."/"1、"式行首序号 → 去 <think>…</think> → Qwen 系名
    替换为本地方别名 → 去"1."~"3."与"数字、/：/．"残片 → 分号改口语
    连接词 → 换行制表改空格 → 去 markdown 符号 → 去全部空白。
    """
    out = text.lstrip()
    for prefix in ("乐乐：", "乐乐:", "助手：", "助手:", "机器人：", "机器人:"):
        if out.startswith(prefix):
            out = out[len(prefix):]
            break
    # 行首 "3." / "12、" 式序号
    i = 0
    while i < len(out) and out[i].isdigit() and out[i].isascii():
        i += 1
    if 0 < i < len(out):
        if out[i] == ".":
            out = out[i + 1:]
        elif out.startswith("、", i):
            out = out[i + 1:]
    # 思考链整块剔除（生成侧关了 thinking，这里兜底）
    begin = out.find(_THINK_OPEN)
    end = out.find(_THINK_CLOSE)
    if begin != -1 and end != -1 and end >= begin:
        out = out[:begin] + out[end + len(_THINK_CLOSE):]
    out = out.replace("Qwen3-VL", _ASSISTANT_NAME).replace("Qwen", _ASSISTANT_NAME)
    out = out.replace("1.", "").replace("2.", "").replace("3.", "")
    out = out.replace("；", "，或者")
    for d in "123456789":
        out = out.replace(d + "、", "").replace(d + "：", "").replace(d + "．", "")
    out = "".join(" " if ch in "\n\r\t" else ch for ch in out)
    out = "".join(ch for ch in out if ch not in _MARKDOWN)
    return "".join(out.split())


def normalize_digits_for_speech(text: str) -> str:
    """数字朗读归一化（MeloTTS 前处理）：0-9 与全角０-９ → 汉字，
    数字之间的 : 或 . → 点（"3:30"/"3.30" → "三点三零"）。"""
    out: list[str] = []
    for i, ch in enumerate(text):
        if "0" <= ch <= "9":
            out.append(_DIGITS_ZH[int(ch)])
            continue
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch in ":." and prev.isdigit() and nxt.isdigit():
            out.append("点")
            continue
        out.append(ch)
    return "".join(out).translate(
        {0xFF10 + d: ord(_DIGITS_ZH[d]) for d in range(10)})
