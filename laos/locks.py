"""laos.locks —— unique_lock 语义的锁生命周期工具（采纳书 C 项）。

来源：C++ unique_lock 一课（复现于 Repro-ZCode/repro/locks.py）：
`with lock:` 等价 lock_guard（RAII 作用域锁）；本模块补齐"可控版"四种能力
——RAII 自动释放 / 手动提前 unlock 收窄临界区 / defer_lock 延迟加锁 /
try_lock 非阻塞尝试 / owns_lock 显式所有权。

用法：

    with UniqueLock(lock) as ul:      # RAII：退出自动释放（若仍持有）
        ...                            # 临界区 A（必须持锁）
        ul.unlock()                    # 提前释放
        ...                            # 临界区 B 外（无锁）

注意：非可重入（threading.Lock 同语义）；_rpc 之类的协议路径可能必须
全程持锁——锁生命周期服从协议事实，不服从"越窄越好"的教条（见
laos/mcp.py MCPClient._rpc 的记录）。
"""
from __future__ import annotations

import threading


class UniqueLock:
    """threading.Lock 的 unique_lock 语义包装（非可重入）。"""

    def __init__(self, lock: threading.Lock, defer_lock: bool = False):
        self._lock = lock
        self._owns = False
        self._defer = defer_lock

    def __enter__(self) -> "UniqueLock":
        if not self._defer:
            self.lock()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._owns:
            self._lock.release()
            self._owns = False

    def lock(self) -> None:
        if self._owns:
            raise RuntimeError("already owns the lock")
        self._lock.acquire()
        self._owns = True

    def unlock(self) -> None:
        if not self._owns:
            raise RuntimeError("unlock without ownership")
        self._lock.release()
        self._owns = False

    def try_lock(self) -> bool:
        if self._owns:
            return True
        if self._lock.acquire(blocking=False):
            self._owns = True
            return True
        return False

    def owns_lock(self) -> bool:
        return self._owns
