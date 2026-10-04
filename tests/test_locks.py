"""laos.locks 测试 —— unique_lock 语义（采纳书 C 项）。"""
import threading

import pytest

from laos.locks import UniqueLock


def test_raii_auto_release():
    lock = threading.Lock()
    with UniqueLock(lock):
        assert lock.locked()
    assert not lock.locked()


def test_manual_early_unlock():
    lock = threading.Lock()
    got = []
    with UniqueLock(lock) as ul:
        ul.unlock()
        t = threading.Thread(target=lambda: got.append(lock.acquire(timeout=0.2)))
        t.start(); t.join()
        assert got == [True]
        lock.release()


def test_defer_lock():
    lock = threading.Lock()
    with UniqueLock(lock, defer_lock=True) as ul:
        assert not lock.locked() and not ul.owns_lock()
        ul.lock()
        assert lock.locked() and ul.owns_lock()
    assert not lock.locked()


def test_try_lock_paths():
    lock = threading.Lock()
    lock.acquire()
    with UniqueLock(lock, defer_lock=True) as ul:
        assert ul.try_lock() is False
    lock.release()
    with UniqueLock(lock, defer_lock=True) as ul:
        assert ul.try_lock() is True
    assert not lock.locked()


def test_unlock_without_ownership_raises():
    lock = threading.Lock()
    with UniqueLock(lock, defer_lock=True) as ul:
        with pytest.raises(RuntimeError):
            ul.unlock()


def test_exit_idempotent_after_manual_unlock():
    lock = threading.Lock()
    with UniqueLock(lock) as ul:
        ul.unlock()
    assert not lock.locked()
    assert lock.acquire(timeout=0.2)
    lock.release()


def test_rpc_protocol_note_present():
    """_rpc 改用 UniqueLock 且记录协议事实（全程持锁的理由）。"""
    import inspect
    from laos import mcp
    src = inspect.getsource(mcp.MCPClient._rpc)
    assert "UniqueLock" in src
    assert "串行" in src or "全程" in src
