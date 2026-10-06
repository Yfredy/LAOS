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

注意：BREAKING 请务必在 subject 上用 "!" 标注（如 feat!: / fix(kernel)!:）——
本脚本只读取提交 subject（%s），body/footer 形态的 BREAKING CHANGE 检测不到。

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


# ── 发版文档同步（记忆规则：每次发版更新所有介绍性文件；AGENTS.md） ──────────

#: 介绍性文件（发版时同步版本号/测试数）。研究文档与带日期的里程碑史【不】在此列。
DOC_GLOBS = [
    "README.md",
    "docs/PROJECT_OVERVIEW.md",
    "docs/ppt/laos-detailed-outline.md",
    "docs/ppt/laos-funding-outline.md",
    "docs/ppt/laos-detailed-v6.html",
    "docs/ppt/laos-funding-v6.html",
    "docs/ppt/detailed/*.html",
    "docs/ppt/funding/*.html",
    "AlwaysOnRec-Trae/README.md",
]

#: 替换模式（带上下文锚点，防误伤历史里程碑行：带日期的 v0.x.y (MM-DD) 不匹配）。
#  每条 = (编译好的正则, 格式化函数(lambda m, ctx -> str))
_DOC_PATTERNS = [
    # README 版本行：当前版本 **vX.Y.Z**
    (re.compile(r"(当前版本\s*\*{0,2})v\d+\.\d+\.\d+(\*{0,2})"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 封面 stamp：<span class="stamp">vX.Y.Z</span>
    (re.compile(r'(<span class="stamp">)v\d+\.\d+\.\d+(</span>)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 正文："开源 vX.Y.Z ·"
    (re.compile(r"(开源\s*)v\d+\.\d+\.\d+(\s*·)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 页脚："github.com/Yfredy/LAOS · vX.Y.Z · NNN tests"
    (re.compile(r"(github\.com/Yfredy/LAOS\s*·\s*)v\d+\.\d+\.\d+(\s*·\s*)\d+(\s*tests)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['total_tests']}{m.group(3)}"),
    # outline 跨度端点："v0.1.0 → vX.Y.Z"
    (re.compile(r"(v0\.1\.0\s*→\s*)v\d+\.\d+\.\d+"),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    # 测试计数（主库口径，三字数字防误伤 "42 测试" 里程碑）：
    (re.compile(r"\d{3}(?= 项回归测试)"), lambda m, c: str(c["main_tests"])),
    (re.compile(r"(?<=主库 )\d{3}(?= 测试)"), lambda m, c: str(c["main_tests"])),
    (re.compile(r"\d{3}(?= 项测试守护)"), lambda m, c: str(c["main_tests"])),
    (re.compile(r"\d{3}(?= 项回归测试（)"), lambda m, c: str(c["main_tests"])),
]


def count_test_functions(tests_dir: Path) -> int:
    """静态数 tests 目录下 `def test_` 方法数（文档口径；与 unittest 运行数一致量级）。"""
    if not tests_dir.is_dir():
        return 0
    n = 0
    for py in tests_dir.rglob("test_*.py"):
        n += len(re.findall(r"^\s*def test_", py.read_text(encoding="utf-8"), re.MULTILINE))
    return n


def zone_test_counts(main_by_run: bool = False) -> dict:
    """三个测试区的计数：主库 / 隔离区(ZCode) / 复现区(Repro)。

    main_by_run=True 时主库数以真跑 `unittest discover` 的 "Ran N tests" 为准
    （静态 def test_ 计数与实跑有少量出入，文档口径用实跑数）；套件非 OK
    则抛错——**测试不绿不许发版**。隔离/复现区用静态计数（与其运行数一致）。
    """
    counts = {
        "main_tests": 0,
        "iso_tests": count_test_functions(REPO / "AlwaysOnRec-ZCode" / "tests"),
        "repro_tests": count_test_functions(REPO / "Repro-ZCode" / "tests"),
    }
    if main_by_run:
        import subprocess
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                           capture_output=True, text=True, timeout=900, cwd=str(REPO))
        out = r.stdout + r.stderr
        m = re.search(r"Ran (\d+) tests?", out)
        if r.returncode != 0 or not m or "OK" not in out:
            tail = "\n".join(out.strip().splitlines()[-6:])
            raise RuntimeError(f"主库测试套件未全绿，拒绝发版：\n{tail}")
        counts["main_tests"] = int(m.group(1))
    else:
        counts["main_tests"] = count_test_functions(REPO / "tests")
    return counts


def sync_docs(version: str, *, dry_run: bool = False,
              globs: list[str] | None = None, counts: dict | None = None) -> list[str]:
    """发版时同步全部介绍性文件（README/PROJECT_OVERVIEW/全部 PPT deck）。

    规则来源：AGENTS.md 记忆条目"每次发版更新所有介绍性文档"（2026-10-06）。
    只动"当前版本声明/封面 stamp/页脚/版本跨度端点/测试计数"五类锚点，
    带日期的里程碑史（如 "v0.12.0 (10-05)"）不动。返回逐文件报告行。
    counts 缺省用静态计数；发版主流程传 main_by_run 的实跑数。
    """
    counts = counts or zone_test_counts()
    ctx = {"ver": version,
           "main_tests": counts["main_tests"],
           "total_tests": counts["main_tests"] + counts["iso_tests"] + counts["repro_tests"]}
    report = [f"docs-sync ctx: v{version}, 主库 {ctx['main_tests']} 测试, "
              f"总 {ctx['total_tests']} tests（含隔离 {counts['iso_tests']} + 复现 {counts['repro_tests']}）"]
    for pattern_glob in (globs or DOC_GLOBS):
        p = Path(pattern_glob)
        if p.is_absolute():  # 绝对路径（测试 fixture / 单文件点改）
            paths = [p] if p.is_file() else []
        else:
            paths = sorted(REPO.glob(pattern_glob))
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            new_text, hits = text, 0
            for rx, fmt in _DOC_PATTERNS:
                new_text, n = rx.subn(lambda m, f=fmt: fmt(m, ctx), new_text)
                hits += n
            if hits:
                try:
                    rel = path.relative_to(REPO)
                except ValueError:
                    rel = path  # 仓库外绝对路径（测试 fixture）
                if not dry_run:
                    path.write_text(new_text, encoding="utf-8")
                report.append(f"docs-sync: {rel} ({hits} 处{'，dry-run 未写' if dry_run else '，已写'})")
    return report


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
        # 记忆规则（AGENTS.md）：发版 = 版本同步 + 全部介绍性文档同步 + 先绿后发
        counts = zone_test_counts(main_by_run=True)
        for path in sync_versions(target):
            print(f"sync: {path.relative_to(REPO)} → __version__ = \"{target}\"")
        print()
        for line in sync_docs(target, counts=counts):
            print(line)
    else:
        print()
        print(f"（dry-run：未写文件；--apply 将同步三棵树 __version__ → {target}）")
        print()
        for line in sync_docs(target, dry_run=True):
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
