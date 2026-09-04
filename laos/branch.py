"""BranchContext —— fork / explore / commit 三原语。

对应 arXiv:2602.08199《Fork, Explore, Commit: OS Primitives for Agentic
Exploration》。Agent 在探索期会并行尝试多条解法，每条解法都会改文件、
起进程；OS 必须提供：

    fork()     O(1) 复制出一个写时隔离的分支
    explore()  在分支内随意破坏
    commit()   原子提交回父分支，first-commit-wins
    abort()    丢弃，兄弟分支自动失效

论文用 FUSE 实现 BranchFS（微秒级 fork、原子 commit）。本 demo 用纯
Python 的 overlay + 操作日志实现同一套语义，便于跨平台阅读与验证；
语义层与论文一致，底层可替换成 BranchFS。

实现：fork 用硬链接共享数据块（O(inode)、零字节拷贝），写入走
laos.cow 的 temp+os.replace 断链 —— 这是 BranchFS COW 在用户态的
零依赖等价物；BranchContext 接口不变，日后可整体替换为 FUSE。
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cow import cow_write


class BranchState:
    EXPLORING = "exploring"
    COMMITTED = "committed"
    ABORTED = "aborted"
    INVALIDATED = "invalidated"  # 被兄弟分支的 first-commit-wins 干掉


def _hardlink_tree(src: Path, dst: Path) -> bool:
    """把 src 目录树硬链接到 dst。返回是否全部走硬链接。

    目录 mkdir、普通文件 os.link、符号链接与链接失败退 copy2（不整体失败）。
    硬链接共享数据块：fork 只复制目录项，后续写入靠 laos.cow 断链。
    """
    all_linked = True
    for p in src.rglob("*"):
        t = dst / p.relative_to(src)
        if p.is_dir():
            t.mkdir(parents=True, exist_ok=True)
        elif p.is_symlink():
            all_linked = False
            shutil.copy2(p, t, follow_symlinks=False)
        else:
            try:
                os.link(p, t)
            except OSError:
                all_linked = False
                shutil.copy2(p, t)
    return all_linked


@dataclass
class BranchContext:
    name: str
    base: Path  # 只读基线（父分支的当前内容）
    workspace: Path  # 本分支的可写工作区
    parent: "BranchContext | None" = None
    state: str = BranchState.EXPLORING
    children: list["BranchContext"] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    committed_at: float | None = None
    cow: bool = False  # fork 是否全程硬链接（混合/纯拷贝为 False）

    # ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        """对外暴露的根：探索期是 workspace，提交后是 base。"""
        return self.workspace if self.state == BranchState.EXPLORING else self.base

    def _assert_alive(self) -> None:
        if self.state != BranchState.EXPLORING:
            raise RuntimeError(f"EINVAL: branch {self.name} is {self.state}")

    # -- 生命周期 --------------------------------------------------------
    def fork(self, name: str, copy_mode: str = "auto") -> "BranchContext":
        """复制出子分支。

        copy_mode="auto"：硬链接父分支整棵目录树 —— 只复制目录项，
        数据块全共享（fork 零字节拷贝）；后续写入靠 laos.cow 断链。
        单个文件链接失败（跨设备/不支持）自动退 copy2，整体仍成功。
        copy_mode="copy"：退回 shutil.copytree 全量拷贝（旧行为）。
        语义两者一致：子分支拿到独立可写视图，提交前不影响父分支。
        目录名即分支名，便于通过虚拟路径 `/<branch>/...` 访问。
        """
        self._assert_alive()
        child_ws = self.workspace.parent / name
        if child_ws.exists():
            shutil.rmtree(child_ws)
        child_ws.mkdir(parents=True)
        used_cow = False
        if copy_mode == "auto":
            used_cow = _hardlink_tree(self.workspace, child_ws)
        else:
            shutil.copytree(self.workspace, child_ws, dirs_exist_ok=True)
        child = BranchContext(
            name=name, base=self.workspace, workspace=child_ws,
            parent=self, cow=used_cow,
        )
        self.children.append(child)
        return child

    def explore(self, rel_path: str, content: str | None = None, op: str = "write") -> Path:
        """在分支内做一次修改尝试，并记 journal（用于原子提交）。"""
        self._assert_alive()
        target = (self.workspace / rel_path.lstrip("/")).resolve()
        if self.workspace.resolve() not in target.parents and target != self.workspace.resolve():
            raise PermissionError(f"EACCES: {rel_path} escapes branch workspace")
        if op == "write":
            target.parent.mkdir(parents=True, exist_ok=True)
            # 硬链接 fork 后 workspace 文件可能与父/兄弟分支共享 inode，
            # 原地 write_text 会改写共享数据块 —— 必须走 CoW 断链写入
            cow_write(target, content or "", encoding="utf-8")
        elif op == "delete":
            target.unlink(missing_ok=True)
        else:
            raise ValueError(f"ENOTSUP: op={op}")
        self.journal.append({"op": op, "path": rel_path, "ts": time.time()})
        return target

    def diff(self) -> list[dict]:
        """对比 workspace 与 base，返回真实差异。

        为什么不用 journal：Agent 的写操作发生在 MCP 驱动进程里，
        分支层看不见（这正是 BranchFS 要把 COW 下沉到 FUSE 的原因）。
        因此提交时以**目录快照 diff** 为准，journal 只留作审计。
        语义等价于 overlayfs 的 upper/lower 合并。
        """
        changed, deleted = self._diff_files()
        return [
            {"op": "write", "path": str(r).replace("\\", "/")} for r in sorted(changed)
        ] + [{"op": "delete", "path": str(r).replace("\\", "/")} for r in sorted(deleted)]

    def _diff_files(self) -> tuple[set, set]:
        def snapshot(root: Path) -> dict:
            if not root.exists():
                return {}
            return {p.relative_to(root): p for p in root.rglob("*") if p.is_file()}

        base_files = snapshot(self.base)
        ws_files = snapshot(self.workspace)

        def same(a: Path, b: Path) -> bool:
            try:
                sa, sb = a.stat(), b.stat()
            except OSError:
                return False
            if sa.st_size != sb.st_size:
                return False
            # inode 快路径：CoW 原语保证共享 inode 从不原地改写，
            # 同 dev+ino 即同内容，免去整文件字节比对
            if sa.st_ino and sa.st_dev == sb.st_dev and sa.st_ino == sb.st_ino:
                return True
            try:
                return a.read_bytes() == b.read_bytes()
            except OSError:
                return False

        changed = {
            rel for rel, p in ws_files.items() if rel not in base_files or not same(self.base / rel, p)
        }
        deleted = {rel for rel in base_files if rel not in ws_files}
        return changed, deleted

    def commit(self) -> int:
        """原子提交到父分支：first-commit-wins，兄弟分支自动失效。

        返回实际应用的变更条数。
        """
        self._assert_alive()
        if self.parent is None:
            self.state = BranchState.COMMITTED
            self.committed_at = time.time()
            return len(self.journal)

        self.parent._assert_alive()
        changed, deleted = self._diff_files()
        # 必须在应用变更之前算 diff，否则提交后两边一致，差异就消失了
        entries = [{"op": "write", "path": str(r).replace("\\", "/")} for r in sorted(changed)]
        entries += [{"op": "delete", "path": str(r).replace("\\", "/")} for r in sorted(deleted)]

        # 父分支文件可能被兄弟分支硬链接共享 —— 必须用 CoW 替换，
        # 绝不能 shutil.copy2 原地截断共享 inode（会改写兄弟分支的内容）
        for rel in changed:
            cow_write(self.parent.workspace / rel, (self.workspace / rel).read_bytes())
        for rel in deleted:
            (self.parent.workspace / rel).unlink(missing_ok=True)

        applied = len(changed) + len(deleted)
        self.journal.extend(entries)

        # first-commit-wins：兄弟分支全部失效
        for sibling in self.parent.children:
            if sibling is not self and sibling.state == BranchState.EXPLORING:
                sibling.state = BranchState.INVALIDATED

        self.state = BranchState.COMMITTED
        self.committed_at = time.time()
        return applied

    def abort(self) -> None:
        self._assert_alive()
        self.state = BranchState.ABORTED
        shutil.rmtree(self.workspace, ignore_errors=True)

    # -- 观测 ------------------------------------------------------------
    def tree(self, indent: int = 0) -> str:
        pad = "  " * indent
        out = [f"{pad}- {self.name} [{self.state}] changes={len(self.journal)}"]
        for c in self.children:
            out.append(c.tree(indent + 1))
        return "\n".join(out)


class BranchTable:
    """内核里的分支表，类似于进程表。"""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._branches: dict[str, BranchContext] = {}

    def create_root(self, name: str = "main") -> BranchContext:
        ws = self.root / name
        ws.mkdir(parents=True, exist_ok=True)
        with self._lock:
            ctx = BranchContext(name=name, base=ws, workspace=ws)
            self._branches[name] = ctx
        return ctx

    def register(self, ctx: BranchContext) -> None:
        with self._lock:
            self._branches[ctx.name] = ctx

    def get(self, name: str) -> BranchContext | None:
        return self._branches.get(name)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": b.name,
                "state": b.state,
                "changes": len(b.journal),
                "parent": b.parent.name if b.parent else None,
            }
            for b in self._branches.values()
        ]
