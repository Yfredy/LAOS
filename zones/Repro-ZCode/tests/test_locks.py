"""unique_lock 语义复现测试（来源⑥：C++ 并发（三））。

文章口径：unique_lock = 可控版 lock_guard —— RAII 自动解锁 + 手动提前
unlock + 延迟加锁 defer_lock + try_lock。laos 是 Python 项目，用
contextmanager 复现其语义（Python 的 `with lock:` 只覆盖 lock_guard 场景）。
"""
import threading

import pytest

from repro.locks import UniqueLock


def test_raii_auto_release_on_exit():
    lock = threading.Lock()
    with UniqueLock(lock):
        assert lock.locked()
    assert not lock.locked()


def test_manual_early_unlock():
    """提前 unlock：块内剩余部分不再持锁（文章核心卖点：锁粒度收窄）。"""
    lock = threading.Lock()
    other_got = []
    with UniqueLock(lock) as ul:
        ul.unlock()
        # 另一线程此刻能拿到锁
        t = threading.Thread(target=lambda: other_got.append(lock.acquire(timeout=0.2)))
        t.start(); t.join()
        assert other_got == [True]
        lock.release()          # 归还测试线程拿到的锁，避免影响后续
    assert not lock.locked()


def test_defer_lock():
    lock = threading.Lock()
    with UniqueLock(lock, defer_lock=True) as ul:
        assert not lock.locked()          # 进入时不持锁
        assert not ul.owns_lock()
        ul.lock()                          # 需要时才加锁
        assert lock.locked() and ul.owns_lock()
    assert not lock.locked()


def test_try_lock_paths():
    lock = threading.Lock()
    lock.acquire()                         # 被他者持有
    with UniqueLock(lock, defer_lock=True) as ul:
        assert ul.try_lock() is False      # 拿不到——不死等
        assert not ul.owns_lock()
    lock.release()

    with UniqueLock(lock, defer_lock=True) as ul:
        assert ul.try_lock() is True       # 空闲——拿到
        assert ul.owns_lock()
    assert not lock.locked()


def test_unlock_without_ownership_raises():
    lock = threading.Lock()
    with UniqueLock(lock, defer_lock=True) as ul:
        with pytest.raises(RuntimeError):
            ul.unlock()


def test_exit_idempotent_after_manual_unlock():
    """手动 unlock 后退出作用域不重复释放。"""
    lock = threading.Lock()
    with UniqueLock(lock) as ul:
        ul.unlock()
    assert not lock.locked()
    # 锁可正常被他人使用
    assert lock.acquire(timeout=0.2)
    lock.release()


def test_context_returns_self():
    lock = threading.Lock()
    with UniqueLock(lock) as ul:
        assert ul.owns_lock()
    assert not ul.owns_lock()
