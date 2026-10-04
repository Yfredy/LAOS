"""unique_lock 语义复现（来源⑥：微信文章 C++ 并发（三））。

C++ 文章结论：lock_guard=简单安全（RAII 作用域锁），unique_lock=可控版
（自动解锁 + 手动提前 unlock 收窄临界区 + defer_lock 延迟加锁 + try_lock
非阻塞尝试）。Python 的 `with lock:` 只等价 lock_guard；本模块用
contextmanager 语义复现 unique_lock 的四种能力：

    with UniqueLock(lock) as ul:      # RAII：退出自动释放（若仍持有）
        ...                            # 临界区 A
        ul.unlock()                    # 手动提前释放
        ...                            # 块内剩余部分不再持锁

    with UniqueLock(lock, defer_lock=True) as ul:   # 进入不持锁
        ...                            # 无锁区
        if ul.try_lock():              # 非阻塞尝试
            ...

laos 现状对照：MCPClient._lock（laos/mcp.py）用手写 acquire/release，
等价于 unique_lock 手动路径；审计写入等长临界区可借"提前 unlock"收窄。
"""
from __future__ import annotations

import threading


class UniqueLock:
    """threading.Lock 的 unique_lock 语义包装（非可重入——与 C++ 一致）。"""

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
        got = self._lock.acquire(blocking=False)
        if got:
            self._owns = True
        return got

    def owns_lock(self) -> bool:
        return self._owns
