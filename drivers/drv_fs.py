#!/usr/bin/env python3
"""drv_fs —— 文件系统“设备驱动”（MCP Server）。

一个驱动就是一个独立进程，通过 stdio 说 MCP。它把 Linux 的文件系统
封装成 5 条 syscall：fs.read / fs.write / fs.append / fs.list / fs.stat。

驱动自己的可见范围被 LAOS_FS_ROOT 限制住（等价于 chroot），
越界路径直接 EACCES —— 这是纵深防御的第二层，第一层是内核能力表。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.mcp import MCPServer  # noqa: E402
from laos.sandbox import PathJail  # noqa: E402

ROOT = Path(os.environ.get("LAOS_FS_ROOT", "./fsroot")).resolve()
MAX_BYTES = int(os.environ.get("LAOS_FS_MAX_BYTES", str(1 << 20)))  # 1 MiB

jail = PathJail(ROOT)
drv = MCPServer("drv_fs", version="0.1.0")

_SCHEMA_PATH = {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "虚拟路径，如 /main/workspace/hosts"}},
    "required": ["path"],
}


@drv.tool("fs.read", "读取一个文件的内容（受 jail 限制）", _SCHEMA_PATH)
def fs_read(path: str) -> str:
    p = jail.resolve(path)
    if not p.exists():
        raise FileNotFoundError(f"ENOENT: {path}")
    if p.is_dir():
        raise IsADirectoryError(f"EISDIR: {path}")
    data = p.read_bytes()
    if len(data) > MAX_BYTES:
        raise IOError(f"EFBIG: {len(data)} bytes > {MAX_BYTES}")
    return data.decode("utf-8", errors="replace")


@drv.tool(
    "fs.write",
    "覆盖写入一个文件（受 jail 限制）",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
)
def fs_write(path: str, content: str) -> str:
    p = jail.resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"OK wrote {len(content.encode('utf-8'))} bytes -> {jail.unresolve(p)}"


@drv.tool(
    "fs.append",
    "向文件末尾追加内容（受 jail 限制）",
    {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
)
def fs_append(path: str, content: str) -> str:
    p = jail.resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(content)
    return f"OK appended {len(content.encode('utf-8'))} bytes -> {jail.unresolve(p)}"


@drv.tool(
    "fs.list",
    "列出目录内容（受 jail 限制）",
    {
        "type": "object",
        "properties": {"path": {"type": "string", "default": "/"}},
    },
)
def fs_list(path: str = "/") -> str:
    p = jail.resolve(path)
    if not p.is_dir():
        raise NotADirectoryError(f"ENOTDIR: {path}")
    entries = sorted(p.iterdir(), key=lambda x: x.name)
    return "\n".join(f"{'d' if e.is_dir() else '-'}  {e.name}" for e in entries) or "(empty)"


@drv.tool("fs.stat", "查看文件元信息（受 jail 限制）", _SCHEMA_PATH)
def fs_stat(path: str) -> str:
    p = jail.resolve(path)
    if not p.exists():
        raise FileNotFoundError(f"ENOENT: {path}")
    st = p.stat()
    return (
        f"path={jail.unresolve(p)} size={st.st_size} "
        f"mtime={int(st.st_mtime)} mode={oct(st.st_mode & 0o777)}"
    )


if __name__ == "__main__":
    drv.serve_forever()
