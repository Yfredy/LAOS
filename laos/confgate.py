"""laos.confgate —— 置信度三段闸：本地执行 / 云端校验 / 丢弃。

来源：docs/research/2026-10-06-four-wechat-articles.md 采纳件 A
（EdgeAI-KWS 端侧部署的边云置信度分流回调）：

    confidence >= local      → 本地直接执行（高置信，不等网络）
    confidence >= cloud      → 云端二次校验（中置信，公网往返换准确率）
    其余                      → 丢弃（防误触发）

与 syscall 闸门链同构的微缩版：本地能定的本地定，定不了的分级上抛，
没把握的丢弃。隐私默认：cloud_enabled=False 时中段直接丢弃——
纯本地模式一个字节都不上传（laos 隐私红线：ASR 全本地）。
纯函数零依赖，可进任何驱动子进程。
"""
from __future__ import annotations

__all__ = ["ConfidenceGate"]


class ConfidenceGate:
    """三段置信度闸。阈值边界含在对应段（>= 判定）。"""

    def __init__(self, *, local: float = 0.9, cloud: float = 0.7,
                 cloud_enabled: bool = True) -> None:
        if not (0.0 < cloud < local <= 1.0):
            raise ValueError(
                f"require 0 < cloud < local <= 1, got local={local} cloud={cloud}")
        self.local = local
        self.cloud = cloud
        self.cloud_enabled = cloud_enabled

    def decide(self, score: float) -> str:
        """返回 "local"（本地执行）| "cloud"（云端校验）| "drop"（丢弃）。"""
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"score out of range [0,1]: {score}")
        if score >= self.local:
            return "local"
        if score >= self.cloud:
            return "cloud" if self.cloud_enabled else "drop"
        return "drop"
