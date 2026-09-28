#!/usr/bin/env python3
"""发版助手 —— conventional commits 推导 semver + CHANGELOG 草稿段 + 三棵树 __version__ 同步。

用法：
    python scripts/release.py                       # 默认 --dry-run：只打印推导，不写任何文件
    python scripts/release.py --dry-run             # 同上（显式）
    python scripts/release.py --dry-run --since v0.6.0
        # 可选参数 --since TAG：覆盖默认起点 tag 重演推导（验证发版逻辑 /
        # 复盘"如果 0.6.0 后就上这套规则会推出什么版本"）。
    python scripts/release.py --apply               # 真写：同步三棵树 __version__ 并打印 CHANGELOG 草稿段

推导规则（0.x 阶段，major 不动；minor 即功能波次）：
    BREAKING（subject 带 "!" 或含 "BREAKING CHANGE"）→ minor+1（major>=1 时才升 major）
    feat  → minor+1
    fix   → patch+1
    仅 docs / chore（及其他非 feat·fix 类型）→ 不发版，返回 current

当前版本口径：主树 laos/__init__.py 的 __version__（应与最新 git tag 一致）；
提交范围口径：最新 tag..HEAD（--since 可覆盖）。

stdlib only。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 三棵树：主库 + 两个 IDE 隔离区快照
VERSION_FILES = [
    REPO / "laos" / "__init__.py",
    REPO / "AlwaysOnRec-ZCode" / "laos" / "__init__.py",
    REPO / "AlwaysOnRec-Trae" / "laos" / "__init__.py",
]

# conventional commit subject: type(scope)!: description
_SUBJECT_RE = re.compile(r"^(\w+)(?:\([^)]*\))?(!)?:\s")

# Keep a Changelog 六分类：conventional type → 分类（未列出的 type 不进草稿段）
_CHANGELOG_BUCKETS = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "style": "Changed",
    "test": "Changed",
    "build": "Changed",
    "ci": "Changed",
    "revert": "Removed",
    "remove": "Removed",
}
_CATEGORY_ORDER = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]


def commits_since(tag: str) -> list[str]:
    """返回 `git log <tag>..HEAD --format=%s` 的 conventional subject 列表（空行剔除）。"""
    out = subprocess.run(
        ["git", "log", f"{tag}..HEAD", "--format=%s"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def latest_tag() -> str:
    """最新版本 tag（`git tag --sort=-v:refname` 首行）；无 tag 时抛 RuntimeError。"""
    out = subprocess.run(
        ["git", "tag", "--sort=-v:refname"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    tags = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    if not tags:
        raise RuntimeError("仓库无版本 tag，无法确定提交范围；请用 --since 指定或先打 tag")
    return tags[0]


def _parse_subject(subject: str) -> tuple[str, bool]:
    """解析单条 subject → (type, breaking)。不符合 conventional 格式的行 type 为空。"""
    m = _SUBJECT_RE.match(subject)
    if not m:
        return "", False
    ctype, bang = m.group(1).lower(), bool(m.group(2))
    breaking = bang or "BREAKING CHANGE" in subject.upper()
    return ctype, breaking


def next_version(current: str, subjects: list[str]) -> str:
    """按 subjects 推导下一版本；仅 docs/chore → 返回 current（不发版）。

    0.x 不动 major：BREAKING 与 feat 都只升 minor；major>=1 后 BREAKING 恢复
    semver 常规（major+1.0.0）。
    """
    major, minor, patch = (int(part) for part in current.split("."))
    has_breaking = has_feat = has_fix = False
    for subject in subjects:
        ctype, breaking = _parse_subject(subject)
        if breaking:
            has_breaking = True
        if ctype == "feat":
            has_feat = True
        elif ctype == "fix":
            has_fix = True
    if has_breaking and major > 0:
        return f"{major + 1}.0.0"
    if has_breaking or has_feat:
        return f"{major}.{minor + 1}.0"
    if has_fix:
        return f"{major}.{minor}.{patch + 1}"
    return current


def changelog_section(version: str, subjects: list[str]) -> str:
    """生成 Keep a Changelog 六分类草稿段（只列实际有条目的分类；日期留待人工补）。"""
    buckets: dict[str, list[str]] = {}
    for subject in subjects:
        ctype, breaking = _parse_subject(subject)
        bucket = _CHANGELOG_BUCKETS.get(ctype)
        if bucket is None:
            continue  # docs/chore 及无法解析的行不进草稿段
        entry = f"- {subject}"
        if breaking:
            entry = f"- **BREAKING** {subject}"
        buckets.setdefault(bucket, []).append(entry)
    lines = [f"## [v{version}]"]
    for category in _CATEGORY_ORDER:
        entries = buckets.get(category)
        if entries:
            lines.append("")
            lines.append(f"### {category}")
            lines.extend(entries)
    return "\n".join(lines) + "\n"


def read_current_version() -> str:
    """主树 laos/__init__.py 的 __version__（当前版本口径）。"""
    m = re.search(r'^__version__ = "([^"]+)"$', VERSION_FILES[0].read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        raise RuntimeError(f"{VERSION_FILES[0]} 缺 __version__")
    return m.group(1)


def sync_versions(version: str) -> list[Path]:
    """把三棵树 laos/__init__.py 的 __version__ 统一改为 version，返回已写文件。"""
    written = []
    for path in VERSION_FILES:
        text = path.read_text(encoding="utf-8")
        new_text, n = re.subn(r'^__version__ = "[^"]*"$', f'__version__ = "{version}"', text, count=1, flags=re.MULTILINE)
        if n != 1:
            raise RuntimeError(f"{path} 未找到 __version__ 行（期望恰好 1 处，实际 {n} 处）")
        path.write_text(new_text, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只打印推导结果，不写文件（默认）")
    mode.add_argument("--apply", action="store_true", help="真写：同步三棵树 __version__")
    parser.add_argument("--since", metavar="TAG", default=None, help="覆盖默认起点 tag（默认取最新 tag）")
    args = parser.parse_args(argv)

    current = read_current_version()
    tag = args.since or latest_tag()
    subjects = commits_since(tag)

    n = {"feat": 0, "fix": 0, "other": 0}
    for subject in subjects:
        ctype, _ = _parse_subject(subject)
        if ctype == "feat":
            n["feat"] += 1
        elif ctype == "fix":
            n["fix"] += 1
        else:
            n["other"] += 1

    print(f"当前版本 {current}，提交范围 {tag}..HEAD 共 {len(subjects)} 个提交"
          f"（feat {n['feat']} / fix {n['fix']} / docs·chore等 {n['other']}）")

    if not subjects:
        print("无未发版提交（范围为空）。")
        return 0

    target = next_version(current, subjects)
    if target == current:
        print(f"无发版需要：仅 docs/chore 等非 feat·fix 提交，版本保持 {current}。")
        return 0

    print(f"建议下一版本 {target}")
    print()
    print(changelog_section(target, subjects), end="")

    if args.apply:
        for path in sync_versions(target):
            print(f"sync: {path.relative_to(REPO)} → __version__ = \"{target}\"")
    else:
        print()
        print(f"（dry-run：未写文件；--apply 将同步三棵树 __version__ → {target}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
