# laos/cow.py
"""CoW —— 写时复制原语：绝不原地修改可能被硬链接共享的 inode。

BranchContext.fork 用 os.link 把父分支目录树硬链接进子分支（数据块
全共享，fork 零字节拷贝）。此后子分支的**任何**写入都必须先"断链"：

    写 temp 文件（新 inode） -> os.replace 原子换掉目录项

旧 inode 上还挂着的父分支/兄弟分支链接不受影响 —— 这就是 BranchFS
在用户态的 COW 等价物（论文把这套语义下沉到 FUSE；我们用 hardlink）。

实现上**永远**走 temp+replace，不判断 st_nlink 再决定写法：
"先判断后写入"在 fork 并发下是 TOCTOU 竞态。os.replace 在
Windows/POSIX 都是原子目录项替换。临时文件带 pid+tid，驱动进程
单线程 stdio 串行，不会互相踩。
"""

from __future__ import annotations

import os
import threading
from pathlib import Path


def is_shared(p: Path) -> bool:
    """文件是否被多个目录项共享（st_nlink > 1）。stat 失败按未共享处理。"""
    try:
        return p.stat().st_nlink > 1
    except OSError:
        return False


def _atomic_replace(p: Path, raw: bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.cow-{os.getpid()}-{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(raw)
        os.replace(tmp, p)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return p


def cow_write(p: Path, data: str | bytes, encoding: str = "utf-8") -> Path:
    """覆盖写：temp + os.replace，共享 inode 上的人看不到这次写入。"""
    raw = data.encode(encoding) if isinstance(data, str) else data
    return _atomic_replace(p, raw)


def cow_append(p: Path, data: str, encoding: str = "utf-8") -> Path:
    """追加写：读旧内容（缺文件按空）+ 新内容，整体原子替换。"""
    try:
        old = p.read_bytes()
    except FileNotFoundError:
        old = b""
    return _atomic_replace(p, old + data.encode(encoding))
