"""soundscape —— 频域声景特征（纯 stdlib：Goertzel 分带能量 + 复用 loudness）。

全天候录音的"频域记忆"数据源：journal 管线在原音频即焚（rec.gc）之前对
每段提取特征，按小时聚合成一条 kind="soundscape" 文本记忆——不存任何
音频字节。用途（见 plans/2026-10-09-aor-lifelog.md §双记忆的五个落地
用途）：场景指纹（带谱+flatness 相似度）、噪声暴露健康档案（LUFS 日
剂量）、未来 AGC 预判数据底座、麦克风自检（带谱异常=遮挡/故障）。

成本：Goertzel 每带一次全窗扫描——10s@16kHz 段约 7×160k 次乘加（纯
Python 亚秒级），journal 离线批处理可接受；不做流式。
"""

from __future__ import annotations

import array
import math

from laos.loudness import integrated_loudness, true_peak

#: 倍频程近似分带（Hz）——16kHz 采样上限 8kHz，6000 是有意义的最高带
BANDS = (125, 250, 500, 1000, 2000, 4000, 6000)
FLOOR_DB = -120.0


def _samples(pcm16: bytes) -> array.array:
    """PCM16 LE 字节 → 归一化 float 样本（奇数字节尾巴丢弃）。"""
    usable = len(pcm16) - len(pcm16) % 2
    a = array.array("h")
    a.frombytes(pcm16[:usable])
    return array.array("d", (s / 32768.0 for s in a))


def _goertzel_power(x: array.array, sr: int, freq: float) -> float:
    """单频点功率（Goertzel）：相对量纲，供分带间 dB 比较。"""
    if not x:
        return 0.0
    k = 2.0 * math.cos(2.0 * math.pi * freq / sr)
    s1 = s2 = 0.0
    for v in x:
        s0 = v + k * s1 - s2
        s2, s1 = s1, s0
    return (s1 * s1 + s2 * s2 - k * s1 * s2) / (len(x) * len(x))


def band_energies_db(pcm16: bytes, sr: int = 16000) -> dict[int, float]:
    x = _samples(pcm16)
    if not x:
        return {b: FLOOR_DB for b in BANDS}
    out: dict[int, float] = {}
    for b in BANDS:
        p = _goertzel_power(x, sr, float(b))
        out[b] = FLOOR_DB if p <= 1e-12 else round(10.0 * math.log10(p), 1)
    return out


def describe(pcm16: bytes, sr: int = 16000) -> dict:
    """一段 PCM16 的完整声景特征（响度三件套复用 loudness.py）。

    floor 防护：integrated_loudness 对 <0.4s 信号或全静音返回 -inf
    （loudness.py:128 `if not loud: return -inf`）——一律钳到 FLOOR_DB，
    PLR 由两 floor 值推导（避免 -inf-(-inf)=nan）。"""
    x = _samples(pcm16)
    if not x:
        return {"lufs": FLOOR_DB, "true_peak_dbtp": FLOOR_DB, "plr": 0.0,
                "bands_db": {b: FLOOR_DB for b in BANDS},
                "flatness": 0.0, "peak_band": 0}
    bands = band_energies_db(pcm16, sr)
    lin = [10.0 ** (v / 10.0) for v in bands.values()]
    geo = math.exp(sum(math.log(max(p, 1e-12)) for p in lin) / len(lin))
    lufs = max(FLOOR_DB, round(integrated_loudness([x], sr), 1))
    tp = max(FLOOR_DB, round(true_peak([x], sr), 1))
    plr_v = round(tp - lufs, 1) if (tp > FLOOR_DB and lufs > FLOOR_DB) else 0.0
    return {"lufs": lufs, "true_peak_dbtp": tp, "plr": plr_v,
            "bands_db": bands,
            "flatness": round(geo / (sum(lin) / len(lin)), 3),
            "peak_band": max(bands, key=bands.get)}


def aggregate(feats: list[dict]) -> dict:
    """多段均值聚合：数值键逐个平均，bands_db 逐带平均，peak_band 重算。"""
    if not feats:
        raise ValueError("EINVAL: aggregate of empty list")
    n = len(feats)

    def mean(key: str) -> float:
        return round(sum(f[key] for f in feats) / n, 1)

    bands = {b: round(sum(f["bands_db"][b] for f in feats) / n, 1)
             for b in BANDS}
    return {"lufs": mean("lufs"), "true_peak_dbtp": mean("true_peak_dbtp"),
            "plr": mean("plr"), "bands_db": bands,
            "flatness": round(sum(f["flatness"] for f in feats) / n, 3),
            "peak_band": max(bands, key=bands.get)}


def render(feats: dict, hour: str, n_segments: int) -> str:
    """单行记忆文本：'14时 3段：LUFS -23.4 PLR 9.8 峰值带 1000Hz(-30.1dB)
    flatness 0.012'——供 kind="soundscape" 记忆与日记第六章直拼。"""
    pk = feats["peak_band"]
    return (f"{hour}时 {n_segments}段：LUFS {feats['lufs']} "
            f"PLR {feats['plr']} 峰值带 {pk}Hz({feats['bands_db'][pk]}dB) "
            f"flatness {feats['flatness']}")
