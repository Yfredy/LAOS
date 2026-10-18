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
from datetime import date as _date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# 三棵树：主库 + 两个 IDE 隔离区快照
VERSION_FILES = [
    REPO / "laos" / "__init__.py",
    REPO / "zones" / "AlwaysOnRec-ZCode" / "laos" / "__init__.py",
    REPO / "zones" / "AlwaysOnRec-Trae" / "laos" / "__init__.py",
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

    新文档域轴（README §十"新文档域=完整需求波次=MINOR"）：纯 docs 波次
    无法从文本自动识别"新域"，约定 subject **尾部**显式标记 "+new-domain"
    → 按 feat 等价升 minor（任何 conventional 类型上均可携带）。必须收尾
    于 subject 末端——正文提及 "+new-domain" 字样（如本工具自身的文档
    提交）不得误触发（2026-10-08 自指 bug 实录：fix 提交 subject 写着
    "+new-domain minor axis" 被推成 MINOR）。
    """
    major, minor, patch = (int(part) for part in current.split("."))
    has_breaking = has_feat = has_fix = False
    for subject in subjects:
        ctype, breaking = _parse_subject(subject)
        if breaking:
            has_breaking = True
        if subject.strip().endswith("+new-domain"):
            has_feat = True   # 新文档域波次：显式标记，feat 等价
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
#: 2026-10-08 补全：intro 组 deck/outline（docs/ppt 直下）与三棵树 README
#: 通配（核查发现 AlwaysOnRec-DB/README.md 带 3 处锚点却从未被同步）。
DOC_GLOBS = [
    "README.md",
    "docs/PROJECT_OVERVIEW.md",
    "docs/ppt/*.md",     # 三组 outline（detailed/funding/intro）+ ppt README（无锚点零命中无害）
    # 2026-10-18：三条显式 html glob 收敛为递归式（ppt-audit §4-②）——等价
    # 19 文件实测相同，且新建子目录的 deck 自动纳入同步面
    "docs/ppt/**/*.html",
    # 2026-10-18：ONBOARDING 与飞书介绍活文档此前在 DOC_GLOBS 外、靠发版时手工
    # 对齐（CHANGELOG v0.39.0 明载）。只收这两个「活文档」：docs/guide 下的
    # 讲稿/lecture 目录是某日快照（开场会声明 10-05 封面数字），纳入同步面
    # 等于改写历史陈述。
    "docs/ONBOARDING.md",
    "docs/guide/laos-feishu-intro.md",
    "zones/AlwaysOnRec-*/README.md",   # 三棵树（Trae/DB/ZCode；ZCode 暂无锚点零命中无害）
]

def _split_pcts(counts: dict) -> tuple[float, float, float]:
    """三树占比（一位小数），最大树吸收舍入残差使三数合计恰为 100.0。"""
    total = counts["main_tests"] + counts["iso_tests"] + counts["repro_tests"]
    iso = round(counts["iso_tests"] * 100 / total, 1)
    repro = round(counts["repro_tests"] * 100 / total, 1)
    main = round(100.0 - iso - repro, 1)
    return main, iso, repro


# ── 叙事计数（驱动数/天数/版本数）与中文数词行文 ────────────────────────────

#: 首版 v0.1.0 的 tag 日（2026-09-04）——deck「N 天」叙事锚的零点
FIRST_RELEASE = _date(2026, 9, 4)

_CN_DIGITS = {"0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
              "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}
_CN_VAL = {v: int(k) for k, v in _CN_DIGITS.items()}


def _cn(n: int) -> str:
    """int → 中文数词（0–9999，deck 行文口径：十七 / 三十九 / 一千五百三十二）。

    只服务牌组行文的保形转换（"十五个驱动"→"十七个驱动"）；1010 一类的
    零位结构按"一千零一十"处理。数值越界直接抛错——行文出现超范围数词
    说明锚点语义已变，应人工复核而非静默截断。
    """
    if not 0 <= n < 10000:
        raise ValueError(f"_cn 仅支持 0–9999，得到 {n}")
    if n < 10:
        return _CN_DIGITS[str(n)]
    if n < 20:
        return "十" + ("" if n == 10 else _CN_DIGITS[str(n % 10)])
    if n < 100:
        tens, ones = divmod(n, 10)
        return _CN_DIGITS[str(tens)] + "十" + (_CN_DIGITS[str(ones)] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        head = _CN_DIGITS[str(hundreds)] + "百"
        if rest == 0:
            return head
        if rest < 10:
            return head + "零" + _CN_DIGITS[str(rest)]
        return head + _cn(rest)
    thousands, rest = divmod(n, 1000)
    head = _CN_DIGITS[str(thousands)] + "千"
    if rest == 0:
        return head
    if rest < 10:
        return head + "零" + _CN_DIGITS[str(rest)]
    if rest < 100:
        return head + "零" + _cn(rest)
    return head + _cn(rest)


def _cn_parse(s: str) -> int:
    """中文数词 → int（_cn 的逆；deck 行文出现的小数词足够，含十二/七百六十五）。"""
    total = num = 0
    for ch in s:
        if ch in _CN_VAL:
            num = _CN_VAL[ch]
        elif ch == "十":
            total += (num or 1) * 10
            num = 0
        elif ch == "百":
            total += (num or 1) * 100
            num = 0
        elif ch == "千":
            total += (num or 1) * 1000
            num = 0
        elif ch == "零":
            continue
        else:
            raise ValueError(f"非中文数词字符: {ch!r} in {s!r}")
    return total + num


def intro_counts(version: str, release_date: str) -> dict:
    """叙事计数：驱动数 / 天数 / 小版本数(minor) / 总版本数。

    这些量随代码与发版自然增长，deck 里写死必腐化（2026-10-18 实录：三族
    牌组停在 v0.12.0 时代的 15 驱动 / 30 天 / 12 MINOR，而仓库已是
    17 驱动 / 44 天 / 39 MINOR / 43 版本）。git 不可用时 minors/versions
    按 semver 推导（version 自身计入、漏历史 patch 发版，记保守下限），
    drivers/days 永远可算（glob 与日期运算）。
    """
    drivers = len(list((REPO / "drivers").glob("drv_*.py")))
    days = (_date.fromisoformat(release_date) - FIRST_RELEASE).days
    minors = versions = 0
    try:
        out = subprocess.run(["git", "tag", "--sort=-v:refname"],
                             cwd=REPO, capture_output=True, text=True,
                             check=True, timeout=30)
        for line in out.stdout.splitlines():
            m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)$", line.strip())
            if not m:
                continue
            versions += 1
            if int(m.group(3)) == 0:
                minors += 1
    except (OSError, subprocess.SubprocessError):
        major, minor, patch = (int(p) for p in version.split("."))
        minors = minor
        versions = minor + (1 if patch else 0)
    return {"drivers": drivers, "days": days,
            "minors": minors, "versions": versions}


#: 替换模式（带上下文锚点，防误伤历史里程碑行：带日期的 v0.x.y (MM-DD) 不匹配）。
#  每条 = (锚点名, 编译好的正则, 格式化函数(lambda m, ctx -> str))——锚点名供
#  sync_docs(detail=True) 的逐锚点细目（"项"模式）报告使用
_DOC_PATTERNS = [
    # README 版本行：当前版本 **vX.Y.Z**
    ("当前版本行",
     re.compile(r"(当前版本\s*\*{0,2})v\d+\.\d+\.\d+(\*{0,2})"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 封面 stamp：<span class="stamp">vX.Y.Z</span>
    ("封面stamp",
     re.compile(r'(<span class="stamp">)v\d+\.\d+\.\d+(</span>)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 正文："开源 vX.Y.Z ·" / "开源 <b>vX.Y.Z</b>" / 药丸 "开源 vX.Y.Z"
    ("开源行",
     re.compile(r"(开源\s*)v\d+\.\d+\.\d+(\s*·)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("开源行",
     re.compile(r"(开源\s*)v\d+\.\d+\.\d+"),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("开源行",
     re.compile(r"(开源\s*<b>)v\d+\.\d+\.\d+(</b>)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # deck 页脚："github.com/Yfredy/LAOS · vX.Y.Z · NNN tests"
    ("deck页脚",
     re.compile(r"(github\.com/Yfredy/LAOS\s*·\s*)v\d+\.\d+\.\d+(\s*·\s*)\d+(\s*tests)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['total_tests']}{m.group(3)}"),
    # ── deck 其余版本锚（2026-10-18 补，ppt-audit §4-② 收口）─────────────
    # 此前只覆盖 stamp / 开源行 / 一种页脚；detailed·funding 的页首、台账
    # 页脚、封面与终场卡的版本锚从未进同步面，这是 v0.9.0/v0.12.0 漂移
    # 一个多月的另一半原因。全部锚在结构上下文上：带日期的里程碑史
    # （v0.12.0 (10-05) / v0.1.0（09-04）→ …）不会命中。
    ("封面stamp",
     re.compile(r'(class="(?:seal|pill)">)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}(</span>)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}{m.group(3)}"),
    ("封面stamp",
     re.compile(r'(class="t-meta"[^>]*>)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}"),
    ("封面stamp",
     re.compile(r'(class="t-meta"[^>]*>)[vV]\d+\.\d+\.\d+'),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("封面stamp",
     re.compile(r'(>)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}(\s*·\s*github\.com/Yfredy/LAOS)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}{m.group(3)}"),
    ("封面stamp",
     re.compile(r'(>)[vV]\d+\.\d+\.\d+(\s*·\s*GitHub\s+)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(REV\s+)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}"),
    ("封面stamp",
     re.compile(r'(REV\s+)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{2}\.\d{2}\.\d{2}'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['short_date']}"),
    ("封面stamp",
     re.compile(r'(<span class="p">)[vV]\d+\.\d+\.\d+(</span>)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(>)[vV]\d+\.\d+\.\d+(\s*开源)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(laos(?:\s*·\s*Linux AgentOS)?\s+)[vV]\d+\.\d+\.\d+(\s*——)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(版本基准\s*)[vV]\d+\.\d+\.\d+'),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("封面stamp",
     re.compile(r'(数字全部真实，)[vV]\d+\.\d+\.\d+(\s*基准)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(laos · Linux AgentOS · )[vV]\d+\.\d+\.\d+'),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("封面stamp",
     re.compile(r'(创新融资\s*·\s*项目介绍\s*·\s*)[vV]\d+\.\d+\.\d+'),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("封面stamp",
     re.compile(r'(class="dim mt-s">)[vV]\d+\.\d+\.\d+(\s*全量)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    # funding 封面角标 / 备忘录 SRC 行 / ticker 三段式：版本号被 <b> 包起来
    # 的正文字形（2026-10-18 收口时实测 funding-huashu 封面仍标 v0.12.0）
    ("封面stamp",
     re.compile(r'(<span class="chip">v<b>)\d+\.\d+\.\d+(</b></span>)'),
     lambda m, c: f"{m.group(1)}{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(SRC / <b>v)\d+\.\d+\.\d+(</b>)'),
     lambda m, c: f"{m.group(1)}{c['ver']}{m.group(2)}"),
    ("封面stamp",
     re.compile(r'(\[<b>V)\d+\.\d+\.\d+(</b>\])'),
     lambda m, c: f"{m.group(1)}{c['ver']}{m.group(2)}"),
    ("deck页脚",
     re.compile(r'(<span>laos\s*)[vV]\d+\.\d+\.\d+(</span>)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}"),
    ("deck页脚",
     re.compile(r'(shutdown — )[vV]\d+\.\d+\.\d+'),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    # 跨度端点的短形态："语义化版本 v0.1 → v0.9"
    ("跨度端点",
     re.compile(r'(语义化版本 v0\.1\s*→\s*)[vV]\d+\.\d+(?!\.\d)'),
     lambda m, c: f"{m.group(1)}v{c['ver'].rsplit('.', 1)[0]}"),
    ("deck页脚",
     re.compile(r'(github\.com/Yfredy/LAOS\s*·\s*)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}"),
    ("deck页脚",
     re.compile(r'(\[ OK \]</span>\s*)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date']}"),
    # detailed frontend 页脚：<span class="fnum">v0.12.0 · 765 tests · 15 drivers
    ("deck页脚",
     re.compile(r'(<span class="fnum">)[vV]\d+\.\d+\.\d+(\s*·\s*)\d+(\s*tests)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['total_tests']}{m.group(3)}"),
    # detailed html-ppt 页首：class="mono">v0.12.0 · 765 TESTS · 15 DRIVERS
    ("deck页首",
     re.compile(r'(class="mono">)[vV]\d+\.\d+\.\d+(\s*·\s*)\d+(\s*TESTS)(\s*·)'),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['total_tests']}{m.group(3)}{m.group(4)}"),
    # detailed huashu 页脚：class="meta">V0.12.0 · 765 TESTS · 15 DRV
    ("deck页脚",
     re.compile(r'(class="meta">)[vV]\d+\.\d+\.\d+(\s*·\s*)\d+(\s*TESTS)(\s*·)'),
     lambda m, c: f"{m.group(1)}V{c['ver']}{m.group(2)}{c['total_tests']}{m.group(3)}{m.group(4)}"),
    # detailed huashu 尾页：GITHUB.COM/... · V0.12.0 · 26.10.05 · 765 TESTS
    ("deck页脚",
     re.compile(r'(GITHUB\.COM/YFREDY/LAOS\s*·\s*)[vV]\d+\.\d+\.\d+(\s*·\s*)\d{2}\.\d{2}\.\d{2}(\s*·\s*)\d+(\s*TESTS)'),
     lambda m, c: f"{m.group(1)}V{c['ver']}{m.group(2)}{c['short_date']}{m.group(3)}{c['total_tests']}{m.group(4)}"),
    # outline 跨度端点："v0.1.0 → vX.Y.Z" / "v0.1.0..vX.Y.Z" / 带日期的区间
    ("跨度端点",
     re.compile(r"(v0\.1\.0\s*→\s*)v\d+\.\d+\.\d+"),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("跨度端点",
     re.compile(r"(v0\.1\.0\.\.)[vV]\d+\.\d+\.\d+"),
     lambda m, c: f"{m.group(1)}v{c['ver']}"),
    ("跨度端点",
     re.compile(r"(v0\.1\.0（09-04）→\s*)[vV]\d+\.\d+\.\d+(（)\d{2}-\d{2}(）)"),
     lambda m, c: f"{m.group(1)}v{c['ver']}{m.group(2)}{c['date'][5:]}{m.group(3)}"),
    # 测试计数（主库口径，\d{3,} 全量匹配：三位起步防误伤 "42 测试" 里程碑，
    # 但必须吃满整个数字串——\d{3} 在千位计数下只匹配尾三位，每次发版叠一个 "1"
    # （2026-10-09 实录：README 被写成 111111051，六次发版六层套娃））：
    ("测试计数", re.compile(r"\d{3,}(?= 项回归测试)"),
     lambda m, c: str(c["main_tests"])),
    ("测试计数", re.compile(r"(?<=主库 )\d{3,}(?= 测试)"),
     lambda m, c: str(c["main_tests"])),
    ("测试计数", re.compile(r"\d{3,}(?= 项测试守护)"),
     lambda m, c: str(c["main_tests"])),
    ("测试计数", re.compile(r"\d{3,}(?= 项回归测试（)"),
     lambda m, c: str(c["main_tests"])),
    # "N 项测试全绿"（README 数据面板 / guide 口径行）——
    # 2026-10-18 实录：该形态不在上述任一模式内，README L69 停在 1146 而
    # 实跑已 1159，故补此模式收口。
    # 但 "主库 353 + 隔离区 350 = 1159 项测试全绿" 这类算术式里的数字是
    # 合计而非主库（2026-10-18 实测：上一版同步把它刷成 353+350=1159 的
    # 假等式）——前置 "= "/"+ " 的合计一律不碰，交给三段式模式重算。
    # 显式「主库 N 项测试全绿」永远是主库口径（outline 常用），与文件类型无关
    ("测试计数", re.compile(r"(主库\s*)\d{3,}(?= 项测试全绿)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    # 裸 "N 项测试全绿" 的口径按文件类型分：deck（html）说三树合计，markdown
    # 介绍文档说主库实跑数（AGENTS.md：页脚/展示用总数，README 用主库实跑）。
    # 2026-10-18 修正：上一版一律按主库刷，把 deck 里原本 765（415+279+71）
    # 的合计写成 1159，数值自洽但口径错了；"主库 N" 前缀仍固定主库。
    ("测试计数", re.compile(r"(?<!\d)(?<!主库 )([=+]\s*)?(\d{3,})(?= 项测试全绿)"),
     lambda m, c: m.group(0) if m.group(1)
     else str(c["total_tests"] if c["is_html"] else c["main_tests"])),
    # intro 组 deck 的英文戳："NNN TESTS GREEN" / "APPROVED · NNN GREEN"
    # （2026-10-08 补：这两形态自 v0.20.0 后从未被同步，一直在漂移）
    ("测试计数", re.compile(r"\d{3,}(?=\s*TESTS GREEN)"),
     lambda m, c: str(c["main_tests"])),
    ("测试计数", re.compile(r"(?<=·\s)\d{3,}(?=\s*GREEN)"),
     lambda m, c: str(c["main_tests"])),
    # ── 测试计数的 deck 展示形态（2026-10-18 补）────────────────────────
    # 页脚/页首/印章口径 = 三树合计（AGENTS.md：页脚总数含隔离区+复现区）
    ("测试计数",
     re.compile(r'(<span class="stamp">)\d+(\s*tests</span>)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="stamp">)\d+(\s*测试全绿</span>)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="mono p">)\d+(</span>\s*测试\s*·\s*<span class="mono p">)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    # 三树组件式（主库/隔离区/复现区 三段齐全时才重算，杜绝单点改写）
    ("测试计数",
     re.compile(r"(主库\s*)\d+(\s*[+/·]\s*(?:隔离区|AlwaysOnRec)\s*)\d+(\s*[+/·]\s*(?:复现区|Repro)\s*)\d+"),
     lambda m, c: (f"{m.group(1)}{c['main_tests']}{m.group(2)}"
                   f"{c['iso_tests']}{m.group(3)}{c['repro_tests']}")),
    ("测试计数",
     re.compile(r"(主库\s*)\d+(\s*\+\s*隔离区\s*)\d+(\s*=\s*)\d+(\s*项测试全绿)"),
     lambda m, c: (f"{m.group(1)}{c['main_tests']}{m.group(2)}{c['iso_tests']}"
                   f" + 复现区 {c['repro_tests']}{m.group(3)}{c['total_tests']}{m.group(4)}")),
    # 四段式（三树 + 合计）：必须能重匹配自己的输出，否则第二次发版起
    # 明细会继续更新而合计永远停在第一次同步的数（2026-10-18 实测：
    # intro-guizang 停在 1532）。三树式同理，输出形态与输入一致。
    ("测试计数",
     re.compile(r"(主库\s*)\d+(\s*\+\s*隔离区\s*)\d+(\s*\+\s*复现区\s*)\d+(\s*=\s*)\d+(\s*项测试全绿)"),
     lambda m, c: (f"{m.group(1)}{c['main_tests']}{m.group(2)}{c['iso_tests']}"
                   f"{m.group(3)}{c['repro_tests']}{m.group(4)}"
                   f"{c['total_tests']}{m.group(5)}")),
    ("测试计数",
     re.compile(r'(·\s*)\d+(\s*tests green \(主库)\s*\d+(\s*\+\s*隔离区)\s*\d+'
                r'(?:\s*\+\s*复现区\s*\d+)?(\))'),
     lambda m, c: (f"{m.group(1)}{c['total_tests']}{m.group(2)}{c['main_tests']}"
                   f"{m.group(3)}{c['iso_tests']} + 复现区 {c['repro_tests']}{m.group(4)}")),
    # ONBOARDING 与飞书介绍活文档（2026-10-18 收进 DOC_GLOBS）：
    # 前者是"主库测试数 | N 项"表格行与 `Ran N tests` 期望值，后者是
    # 口径头的 "N 项测试（DATE 实跑）" 与 "N 项测试全绿（主库，DATE 实跑）"。
    # 只命中带结构上下文的形态，日期同步到发版日（活文档的"实跑"就是当下）。
    ("测试计数",
     re.compile(r"(\|\s*主库测试数\s*\|\s*)\d{3,}(?=\s*项（)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(\bRan\s+)\d{3,}(?=\s*tests)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    # 讲稿类活文档的裸主库口径（"实跑"是讲稿锚点声明的固定措辞）
    ("测试计数",
     re.compile(r"(｜\s*)\d{3,}(?=\s*项测试（实跑）)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(\d{3,})(\s*项测试（)\d{4}-\d{2}-\d{2}(\s*实跑）)"),
     lambda m, c: f"{c['main_tests']}{m.group(2)}{c['date']}{m.group(3)}"),
    ("测试计数",
     re.compile(r"(\d{3,})(\s*项测试全绿\*{0,2}（主库，)\d{4}-\d{2}-\d{2}(\s*实跑[^）]*）)"),
     lambda m, c: f"{c['main_tests']}{m.group(2)}{c['date']}{m.group(3)}"),
    # ── deck 正文的「合计」展示位（2026-10-18 补）──────────────────────
    # 面板/台账/终场卡把测试总数单独做成了大字号，此前只刷三树明细，
    # 合计停在旧值（765），造成同页"明细已新、合计仍旧"的分裂。以下每条
    # 都锚死展示结构（class/相邻文案），不动讲稿里的"765 测试"叙述
    # （那类常带 415+279+71 算术，属于重建时的人工内容）。
    ("测试计数",
     re.compile(r'(<span class="mono p">)\d+(</span>\s*green（主库)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     # 2026-10-18：原 "→ N collected · N passed"（pytest --co 行）已按当日
     # 实测改为 unittest discover 形态；该形态复跑可验且被下条 Ran 模式覆盖，
     # 换成主库实跑口径的同步形态（原 collected 模式随之作废）
     re.compile(r'(→\s*Ran\s+)\d+(\s*tests\s*·\s*OK)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(合计\s*<span[^>]*>)\d+( 全绿</span>)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="ledger-num"[^>]*>)\d+(</span>\s*<div class="ledger-label"><div[^>]*>测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<div class="ledger-num"[^>]*>)\d+(</div>\s*<div class="ledger-label"><div[^>]*>TESTS GREEN)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<h2><span class="gold">)\d+(</span> 测试，全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<div class="bignum" style="font-size:120px">)\d+(</div>\s*<hr class="hair">\s*<p[^>]*>全仓测试总数)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="tag green">)\d+( 测试</span>)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<b>)\d+(</b> 全绿（主库)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<tr><td>测试</td><td class="m">)\d+(</td><td>主库)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(·\s*)\d+( 测试</div>)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    # ── 三树明细展示位与算术式（2026-10-18 收口）───────────────────────
    # 合计刷了、明细没刷，同页会自相矛盾（"合计 1537" 旁边写 "主库 415"）。
    # 明细锚一律绑死树名/色块结构，避免碰到"六来源 71 项测试"这类合法子集
    # 数字（复现区现行 94 = 六来源 71 + AuraSE 规则版 23，两者不是同一量）。
    ("测试计数",
     re.compile(r'(font-weight:700">laos</span> 主库 <span class="c mono" style="font-size:19px">)\d+( tests)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(font-weight:700">Repro</span> 复现区 <span class="c mono" style="font-size:19px">)\d+( tests)'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}{m.group(2)}"),
    # 比例条：数字与宽度必须同源重算，否则条形与标签打架
    ("测试计数",
     re.compile(r'(<div class="stbar">\s*<div style="flex:)[\d.]+(;background:var\(--green\)">)\d+'
                r'(</div>\s*<div style="flex:)[\d.]+(;background:var\(--blue\)">)\d+'
                r'(</div>\s*<div style="flex:)[\d.]+(;background:var\(--purple\)">)\d+(</div>)'),
     lambda m, c: (f"{m.group(1)}{_split_pcts(c)[0]:.1f}{m.group(2)}{c['main_tests']}"
                   f"{m.group(3)}{_split_pcts(c)[1]:.1f}{m.group(4)}{c['iso_tests']}"
                   f"{m.group(5)}{_split_pcts(c)[2]:.1f}{m.group(6)}{c['repro_tests']}{m.group(7)}")),
    ("测试计数",
     re.compile(r'(<div class="sg1" style="width:)[\d.]+(%">主库 )\d+(</div>)'),
     lambda m, c: f"{m.group(1)}{_split_pcts(c)[0]:.1f}{m.group(2)}{c['main_tests']}{m.group(3)}"),
    ("测试计数",
     re.compile(r'(<div class="sg2" style="width:)[\d.]+(%">AlwaysOnRec )\d+(</div>)'),
     lambda m, c: f"{m.group(1)}{_split_pcts(c)[1]:.1f}{m.group(2)}{c['iso_tests']}{m.group(3)}"),
    ("测试计数",
     re.compile(r'(<div class="sg3" style="width:)[\d.]+(%">Repro )\d+(</div>)'),
     lambda m, c: f"{m.group(1)}{_split_pcts(c)[2]:.1f}{m.group(2)}{c['repro_tests']}{m.group(3)}"),
    ("测试计数",
     re.compile(r'(<div class="legend"><span><b>)[\d.]+(%</b> 内核与驱动语义</span><span><b>)'
                r'[\d.]+(%</b> 录音沙箱</span><span><b>)[\d.]+(%</b> 论文复现)'),
     lambda m, c: (f"{m.group(1)}{_split_pcts(c)[0]:.1f}{m.group(2)}"
                   f"{_split_pcts(c)[1]:.1f}{m.group(3)}"
                   f"{_split_pcts(c)[2]:.1f}{m.group(4)}")),
    # guizang 台账行：树名在 ledger-label 里
    ("测试计数",
     re.compile(r'(<span class="ledger-num"[^>]*>)\d+(</span>\s*<div class="ledger-label"><div[^>]*>laos 主库)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="ledger-num"[^>]*>)\d+(</span>\s*<div class="ledger-label"><div[^>]*>Repro 复现区)'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}{m.group(2)}"),
    # html-ppt 三树表
    ("测试计数",
     re.compile(r'(<tr><td><b>laos</b> 主库</td><td>内核 \+ 驱动</td><td class="mono">)\d+(</td>)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<tr><td><b>Repro</b></td><td>论文复现区</td><td class="mono">)\d+(</td>)'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}{m.group(2)}"),
    # funding 封面角标 / 里程碑大数字 / ticker
    ("测试计数",
     re.compile(r'(<span class="chip"><b>)\d+(</b> 测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(\[TESTS <b>)\d+( GREEN</b>\])'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<div class="bignum">)\d+(</div><hr class="hair">\s*<p[^>]*>测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    # v6 合成版：算术式必须四数同源重算
    ("测试计数",
     re.compile(r'(<span>D · 质量文化组</span><span>)\d+( = )\d+( \+ )\d+( \+ )\d+(</span>)'),
     lambda m, c: (f"{m.group(1)}{c['total_tests']}{m.group(2)}{c['main_tests']}"
                   f"{m.group(3)}{c['iso_tests']}{m.group(4)}{c['repro_tests']}{m.group(5)}")),
    ("测试计数",
     re.compile(r'(<div class="gold mono" style="font-size:64px;font-weight:800">)\d+'
                r'(</div><div class="caption">测试全绿<br>)\d+( 主库 \+ )\d+( 隔离 \+ )\d+( 复现</div>)'),
     lambda m, c: (f"{m.group(1)}{c['total_tests']}{m.group(2)}{c['main_tests']}"
                   f"{m.group(3)}{c['iso_tests']}{m.group(4)}{c['repro_tests']}{m.group(5)}")),
    # 底稿（docs/ppt/*.md）的角标/仓库行：测试数写成"… · N 测试"或
    # "… N 版本/N 测试/…"。锚死行首标签，dated 版本史行不命中。
    ("测试计数",
     re.compile(r"(仓库：[^\n]*?·\s*)\d+(?= 测试)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(角标：[^\n]*?·\s*)\d+(?= 测试)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(角标[^\n]*?·\s*测试\s*)\d+(?=\s*·)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(版本/)\d+(?= 测试/)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r"(版本\s*/\s*)\d+(?= 测试\s*/)"),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r'(\b)\d+(?=\s*测试全绿)'),
     lambda m, c: str(c["total_tests"])),
    ("测试计数",
     re.compile(r'(<span class="hl">)\d+(</span>\s*测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<h2 class="h2 mt-s">)\d+(\s*全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(>)\d+(\s*项测试，全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(class="stat-num">)\d+(\s*<small>GREEN)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(class="stat-num">)\d+(</p><p class="stat-sub">测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(data-count=")\d+(">)\d+(</span>\s*<span class="k">测试全绿)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}{c['total_tests']}{m.group(3)}"),
    ("测试计数",
     re.compile(r'(class="n">)\d+(</div>\s*<div class="decomp">)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<b>)\d+(</b>\s*主库)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<b>)\d+(</b>\s*AlwaysOnRec)'),
     lambda m, c: f"{m.group(1)}{c['iso_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<b>)\d+(</b>\s*Repro)'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}{m.group(2)}"),
    # intro 封面三树药丸
    ("测试计数",
     re.compile(r'(<span class="pill">主库\s*)\d+(\s*tests)'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}{m.group(2)}"),
    ("测试计数",
     re.compile(r'(<span class="pill">AlwaysOnRec\s*)\d+'),
     lambda m, c: f"{m.group(1)}{c['iso_tests']}"),
    ("测试计数",
     re.compile(r'(<span class="pill">Repro\s*)\d+'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}"),
    # detailed 质量页四张卡
    ("测试计数",
     re.compile(r'(data-tag="主库"><p class="stat-num">)\d+'),
     lambda m, c: f"{m.group(1)}{c['main_tests']}"),
    ("测试计数",
     re.compile(r'(data-tag="录音隔离区"><p class="stat-num">)\d+'),
     lambda m, c: f"{m.group(1)}{c['iso_tests']}"),
    ("测试计数",
     re.compile(r'(data-tag="复现区"><p class="stat-num">)\d+'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}"),
    ("测试计数",
     re.compile(r'(data-tag="合计"[^>]*><p class="stat-num">)\d+(\s*<small>GREEN)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(2)}"),
    # ── 叙事计数锚点（2026-10-18 补，ppt-audit §6 遗留项收口）────────────
    # 驱动数/天数/小版本数/总版本数此前不在五类锚点自动化面内，三族 deck 停在
    # v0.12.0 时代的 15 驱动/30 天/12 MINOR（底稿已更正、html 无人跟进）。
    # ctx["intro"] 由 intro_counts() 实算（glob + git tag + 日期运算）。
    # 每条锚在结构上下文（class/相邻文案/完整短语）上；中文数词行文用 _cn()
    # 保形转换，数词模式首字符排除"一"——定义句（"每个 MCP Server = 一个
    # 驱动"/"一个 MINOR = 一个完整需求波次"）与演示句（"加载 3 个驱动"是
    # Arabic 形态同样不命中）一律不碰。带日期的里程碑史不匹配这些形态。
    #
    # — 驱动数 —
    # deck 页脚：<span class="fnum">vX · N tests · 15 drivers · NN / 19
    ("驱动数",
     re.compile(r'(<span class="fnum">[vV]\d+\.\d+\.\d+\s*·\s*\d+\s*tests\s*·\s*)\d+(\s*drivers)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # deck 页首：class="mono">vX · N TESTS · 15 DRIVERS · 12 RELEASES
    # （驱动数与总版本数同锚重算；版本/测试数已由前述模式先刷）
    ("驱动数",
     re.compile(r'(TESTS\s*·\s*)\d+(\s*DRIVERS\s*·\s*)\d+(\s*RELEASES)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"
                   f"{c['intro']['versions']}{m.group(3)}")),
    # huashu 页脚：class="meta">VX · N TESTS · 15 DRV · 12 MINOR
    # （锚 class="meta" 防误伤方向稿里引用旧角标的叙述行）
    ("驱动数",
     re.compile(r'(class="meta">[vV]\d+\.\d+\.\d+\s*·\s*\d+\s*TESTS\s*·\s*)\d+(\s*DRV\s*·\s*)\d+(\s*MINOR)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"
                   f"{c['intro']['minors']}{m.group(3)}")),
    # v6 封面印章：15 drivers / 12 minors / 30 天 / 30 天 · 12 个版本
    ("驱动数",
     re.compile(r'(<span class="stamp">)\d+(\s*drivers</span>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("天数版本数",
     re.compile(r'(<span class="stamp">)\d+(\s*minors\s*/\s*)(\d+)(\s*天</span>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['minors']}{m.group(2)}"
                   f"{c['intro']['days']}{m.group(4)}")),
    ("天数版本数",
     re.compile(r'(<span class="stamp">)\d+(\s*天\s*·\s*)(\d+)(\s*个版本</span>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                   f"{c['intro']['versions']}{m.group(4)}")),
    # 架构层标签 / 封面药丸 / 页面标题属性
    ("驱动数",
     re.compile(r'(<span class="layer-tag">)\d+(\s*DRIVERS</span>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(<span class="pill">)\d+(\s*个驱动</span>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(data-title="C1 驱动全景\s*·\s*)\d+(\s*驱动")'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # 命令行：$ ls /laos/drivers/ -1 | wc -l → 15
    ("驱动数",
     re.compile(r'(ls /laos/drivers/ -1 \| wc -l → )\d+'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}"),
    # 正文/讲稿短语（锚相邻文案）
    ("驱动数",
     re.compile(r'(闸门\s*·\s*)\d+(\s*驱动\s*·\s*端侧)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(开源\s*v\d+\.\d+\.\d+\s*·\s*)\d+(\s*驱动\s*·\s*端侧)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(\d+)(\s*个驱动子进程)'),
     lambda m, c: f"{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(驱动子进程\s*·\s*<span class="mono p">)\d+(</span>\s*×\s*drv_\*)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(驱动子进程</span>\s*·\s*)\d+(\s*×\s*drv_\*，重依赖隔离)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(驱动全景\s*<span class="hl">·</span>\s*)\d+(\s*个 drv_\* 子进程)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(驱动全景：)\d+(\s*个设备。)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # guizang talk 数组 title：「驱动全景 15 个设备（重点表格页）」——
    # 与 h2「驱动全景：N 个设备。」同源的计数锚（表格 15 张卡按审计裁定
    # 保持代表驱动不动，仅计数锚同步）
    ("驱动数",
     re.compile(r'(title: "驱动全景 )(\d+)( 个设备（重点表格页）")'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(3)}"),
    ("驱动数",
     re.compile(r'(预告三个硬数字：)\d+(\s*驱动\s*/\s*8\s*环闸门\s*/\s*)\d+(\s*测试)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"
                   f"{c['total_tests']}{m.group(3)}")),
    ("驱动数",
     re.compile(r'(进展锚点：)\d+(\s*驱动\s*/\s*纯 stdlib)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(Linux 内核的 Agent 扩展（用户态 · 零内核改动）：)\d+(\s*个驱动\s*·\s*8\s*环 syscall 闸门)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # README 数据面板：… 项测试全绿 · 17 个驱动 · …（md 口径由测试模式先刷）
    ("驱动数",
     re.compile(r'(项测试全绿\s*·\s*)\d+(\s*个驱动)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # PROJECT_OVERVIEW 驱动目录行（每个=一个 MCP Server 子进程，17 个）
    ("驱动数",
     re.compile(r'(drivers/\s*★\s*设备驱动（每个=一个 MCP Server 子进程，)\d+( 个）)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # html-ppt C1 等数额：15 个驱动 = 3 听觉 + 6 手机 + 6 系统（系统段同源重算）
    ("驱动数",
     re.compile(r'(<h2 class="h2 mt-s">)\d+(\s*个驱动\s*=\s*)(\d+)(\s*听觉\s*\+\s*)(\d+)(\s*手机\s*\+\s*)(\d+)(\s*系统。</h2>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}{m.group(3)}{m.group(4)}"
                   f"{m.group(5)}{m.group(6)}"
                   f"{c['intro']['drivers'] - int(m.group(3)) - int(m.group(5))}{m.group(8)}")),
    # 分解式无合计形态：听觉 3 · 手机 6 · 系统 6（系统段同源重算，与等数额 h2 同源；
    # 讲稿 talk 数组用 "/" 分隔——两种分隔符都吃）
    ("驱动数",
     re.compile(r'(听觉\s*)(\d+)(\s*[·/]\s*手机\s*)(\d+)(\s*[·/]\s*系统\s*)(\d+)'),
     lambda m, c: (f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}"
                   f"{c['intro']['drivers'] - int(m.group(2)) - int(m.group(4))}")),
    # guizang 驱动页大数字：num-mega 15 + t-meta「BUILT-IN DRIVERS · …」
    ("驱动数",
     re.compile(r'(<span class="num-mega"[^>]*>)\d+(</span>\s*<span class="t-meta">BUILT-IN DRIVERS)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # 角上四个数字（tests 数已由「N 项测试全绿」模式先刷成同锚值）
    ("驱动数",
     re.compile(r'(先报一遍：<strong>\d+\s*项测试全绿、)\d+(\s*个驱动、)(\d+)(\s*天发了\s*)(\d+)(\s*个 MINOR 版本、)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}{c['intro']['days']}"
                   f"{m.group(4)}{c['intro']['minors']}{m.group(6)}")),
    # 目录标签「15 驱动 C1」/ 底稿「C1 驱动全景表（15 驱动）」
    ("驱动数",
     re.compile(r'(<p class="dim" style="font-size:15px">)\d+(\s*驱动 C1<br>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    ("驱动数",
     re.compile(r'(C1 驱动全景表（)\d+( 驱动）)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(2)}"),
    # 中文数词三段算术：听觉三个、手机六个、系统六个，一共十五个
    ("驱动数",
     re.compile(r'(听觉)([一二三四五六七八九十百千零两]+)(、手机)([一二三四五六七八九十百千零两]+)'
                r'(、系统)([一二三四五六七八九十百千零两]+)(，一共)([一二三四五六七八九十百千零两]+)(个)'),
     lambda m, c: (f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}"
                   f"{_cn(c['intro']['drivers'] - _cn_parse(m.group(2)) - _cn_parse(m.group(4)))}"
                   f"{m.group(7)}{_cn(c['intro']['drivers'])}{m.group(9)}")),
    # 中文数词行文（保形转换；「一个驱动」定义句不命中——首字符排除"一"）
    ("驱动数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个驱动)'),
     lambda m, c: f"{_cn(c['intro']['drivers'])}{m.group(2)}"),
    # 「N 个设备驱动」三形态（2026-10-18 补：outline 早写 17，decks 7 处
    # 阿拉伯 + 1 处中文停在 15——audit 批「15→17 驱动」只覆盖了驱动子进程/
    # DRIVERS 标签/RGE 印章，短语形态漏网）。数字单独成槽的加粗形
    # （<b>15</b> 个设备驱动）与整体加粗形（<b>15 个设备驱动</b>）互斥。
    ("驱动数",
     re.compile(r'(<b>)(\d+)(</b>\s*个设备驱动)'),
     lambda m, c: f"{m.group(1)}{c['intro']['drivers']}{m.group(3)}"),
    ("驱动数",
     re.compile(r'(\d+)(\s*个设备驱动)'),
     lambda m, c: f"{c['intro']['drivers']}{m.group(2)}"),
    # 中文形：十五个设备驱动（notes 实录）。毯式首类排除「一」，
    # 散文「一个设备驱动」不命中（当前语料无此形，防御性保持双轨制）。
    ("驱动数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个设备驱动)'),
     lambda m, c: f"{_cn(c['intro']['drivers'])}{m.group(2)}"),
    # — 天数 / 版本数 —
    # guizang 台账标签 / 大标题 / 章节眉
    ("天数版本数",
     re.compile(r'(">MINOR · )\d+( 天)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(2)}"),
    ("天数版本数",
     re.compile(r'(">MINOR VERSIONS / )\d+( 天)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(2)}"),
    # ledger 大数字行：span 形态（detailed「MINOR · N 天」）与 div 形态
    # （funding「MINOR VERSIONS / N 天」）——标签天数已同步，大数字不得停在旧值
    ("天数版本数",
     re.compile(r'(<span class="ledger-num"[^>]*>)\d+(</span>\s*<div class="ledger-label"><div[^>]*>MINOR)'),
     lambda m, c: f"{m.group(1)}{c['intro']['minors']}{m.group(2)}"),
    ("天数版本数",
     re.compile(r'(<div class="ledger-num"[^>]*>)\d+(</div>\s*<div class="ledger-label"><div[^>]*>MINOR VERSIONS)'),
     lambda m, c: f"{m.group(1)}{c['intro']['minors']}{m.group(2)}"),
    # 版本史页大数字：num-mega 12 + t-meta「MINOR RELEASES · V0.1.0 → … · N DAYS」
    ("天数版本数",
     re.compile(r'(<span class="num-mega"[^>]*>)\d+(</span>\s*<span class="t-meta">MINOR RELEASES)'),
     lambda m, c: f"{m.group(1)}{c['intro']['minors']}{m.group(2)}"),
    ("天数版本数",
    re.compile(r'(<h2 class="h-xl"[^>]*>)\d+(\s*天，)(\d+)(\s*个 MINOR。</h2>)'),
    lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                  f"{c['intro']['minors']}{m.group(4)}")),
    ("天数版本数",
    re.compile(r'(<h2>)\d+(\s*天，)(\d+)(\s*个 MINOR，每版本)'),
    lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                  f"{c['intro']['minors']}{m.group(4)}")),
    ("天数版本数",
     re.compile(r'(<h2>)([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(天，<span class="gold">)'
                r'([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个 MINOR</span>。</h2>)'),
     lambda m, c: (f"{m.group(1)}{_cn(c['intro']['days'])}{m.group(3)}"
                   f"{_cn(c['intro']['minors'])}{m.group(5)}")),
    ("天数版本数",
    re.compile(r'(<h2 class="h-xl"[^>]*>)\d+(\s*天，)(\d+)(\s*个版本，)'),
    lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                  f"{c['intro']['versions']}{m.group(4)}")),
    ("天数版本数",
    re.compile(r'(<h2>)\d+(\s*天\s*)(\d+)(\s*版本，每一行)'),
    lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                  f"{c['intro']['versions']}{m.group(4)}")),
    ("天数版本数",
     re.compile(r'(letter-spacing:-\.01em">)\d+(\s*天</span>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(2)}"),
    # guizang 标题卡眉：MINOR RELEASES · V0.1.0 → V0.12.0 · 30 DAYS
    #（跨度端点与天数同锚；短形态版本端点一并归队）
    ("天数版本数",
     re.compile(r'(MINOR RELEASES · V0\.1\.0 → V0\.)(\d+\.\d+)( · )(\d+)( DAYS)'),
     lambda m, c: (f"{m.group(1)}{c['ver'].split('.', 1)[1]}{m.group(3)}"
                   f"{c['intro']['days']}{m.group(5)}")),
    # funding guizang 封面 t-meta：v0.39.0 · 30 天 12 版本 · 1532 测试
    ("天数版本数",
     re.compile(r'(t-meta"[^>]*>v[\d.]+ · )(\d+)(\s*天\s*)(\d+)(\s*版本 · )(\d+)(\s*测试)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}{c['total_tests']}{m.group(7)}")),
    # v6 funding 单句
    ("天数版本数",
     re.compile(r'(协作流水线，)(\d+)(\s*天的产出)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(3)}"),
    ("天数版本数",
     re.compile(r'(流水线\s*)(\d+)(\s*天做到这个产出)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(3)}"),
    ("天数版本数",
     re.compile(r'(，但\s*)(\d+)(\s*天的交付节奏)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(3)}"),
    ("天数版本数",
     re.compile(r'(font-size:64px;font-weight:800">)(\d+)(</div><div class="caption">个 MINOR 版本 / )(\d+)(\s*天)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['minors']}{m.group(3)}"
                   f"{c['intro']['days']}{m.group(5)}")),
    # funding 族绿签 / 大标题 / 计数 stat / 正文缎带
    ("天数版本数",
     re.compile(r'(<span class="tag green">)(\d+)(\s*天\s*·\s*)(\d+)(\s*个版本</span>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(<h2 class="title reveal d1">)(\d+)(\s*天\s*·\s*)(\d+)(\s*版本\s*·\s*)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(data-count=")(\d+)(">)(\d+)(</span><span class="k">MINOR 版本)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['minors']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(\d+)(\s*天完成\s*(?:<b[^>]*>)?)(\d+)(\s*版本\s*/\s*)(\d+)(\s*测试\s*/)'),
     lambda m, c: (f"{c['intro']['days']}{m.group(2)}{c['intro']['versions']}"
                   f"{m.group(4)}{c['total_tests']}{m.group(6)}")),
    ("天数版本数",
     re.compile(r'(独立开发者\s*[·：]\s*)(\d+)(\s*天\s*)(\d+)(\s*版本\s*/\s*)(\d+)(\s*测试\s*/)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}{c['total_tests']}{m.group(7)}")),
    # pill 形态：funding「30 天 · 12 个 MINOR 版本」与 detailed「30 天 · 12 个
    # MINOR」——「版本」整词可选（原 `版本?` 只让「本」可选，「版」仍必需，
    # detailed 无后缀形永远漏刷，2026-10-18 修复）
    ("天数版本数",
     re.compile(r'(<span class="pill">)(\d+)(\s*天\s*·\s*)(\d+)(\s*个 MINOR\s*(?:版本)?</span>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(全部真实：)(\d+)(\s*天，)(\d+)(\s*个版本，)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(<p class="stat-num">)(\d+)(</p><p class="stat-sub">MINOR 版本 / <b>)(\d+)(\s*天</b>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['minors']}{m.group(3)}"
                   f"{c['intro']['days']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(纯 stdlib；)(\d+)(\s*天\s*)(\d+)(\s*个版本、)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(MINOR 版本 / )(\d+)(\s*天<br>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['days']}{m.group(3)}"),
    # kicker 命令行：→ 30 天 · 12 MINOR / ——30 天 12 个 MINOR（…）/
    # § D2 · RELEASE TIMELINE · 30 天 12 个 MINOR / 30 天 12 个 MINOR（重点表格页）
    ("天数版本数",
     re.compile(r'(→\s*)(\d+)(\s*天\s*·\s*)(\d+)(\s*MINOR)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(commits</b>——)(\d+)(\s*天\s*)(\d+)(\s*个 MINOR（)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(RELEASE TIMELINE · )(\d+)(\s*天\s*)(\d+)(\s*个 MINOR)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
    re.compile(r'(title: ")\d+(\s*天\s*)(\d+)(\s*个 MINOR（重点表格页）")'),
    lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                  f"{c['intro']['minors']}{m.group(4)}")),
    # frontend D2 页内嵌 span：30 天 <span class="mono pp" …>12</span> 个 MINOR
    ("天数版本数",
     re.compile(r'(<p>)\d+(\s*天\s*<span class="mono pp"[^>]*>)(\d+)(</span>\s*个 MINOR)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(2)}"
                   f"{c['intro']['minors']}{m.group(4)}")),
    # huashu 方向稿的 chip / r 行 / 台账表行 / ticker（模板态，随锚点刷新一致）
    ("天数版本数",
     re.compile(r'(<span class="chip">)(\d+)(\s*天\s*<b>)(\d+)(</b>\s*个版本</span>)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(<span class="k">RELEASES</span><span class="v">)(\d+)(\s*天\s*<b>)(\d+)(</b>\s*个 MINOR 版本)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(<tr><td>MINOR 版本</td><td class="m">)(\d+)(</td>)'),
     lambda m, c: f"{m.group(1)}{c['intro']['minors']}{m.group(3)}"),
    ("天数版本数",
     re.compile(r'(\[RELEASES <b>)(\d+)(/)(\d+)(D</b>\])'),
     lambda m, c: (f"{m.group(1)}{c['intro']['versions']}{m.group(3)}"
                   f"{c['intro']['days']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(font-size:34px">)(\d+)(\s*天，)(\d+)(\s*个版本：)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['versions']}{m.group(5)}")),
    # huashu 版本纪律卡：commits；30 天 12 个 MINOR（v0.1.0 → v0.39.0）——
    # 同行版本端点本就由跨度端点模式刷掉，卡片正文的天数/版本数却没有
    # 专属锚，长期停在 30/12（2026-10-18 补；「commits；」前缀防误伤）
    ("天数版本数",
     re.compile(r'(commits；)(\d+)(\s*天\s*)(\d+)(\s*个 MINOR（)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}"
                   f"{c['intro']['minors']}{m.group(5)}")),
    ("天数版本数",
     re.compile(r'(数字大字化（)(\d+)(\s*天\s*)(\d+)(\s*版本\s*/\s*)(\d+)(\s*测试\s*/\s*8\s*环\s*/\s*)(\d+)(\s*驱动\s*/\s*19,792\s*论文）)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}{c['intro']['versions']}"
                   f"{m.group(5)}{c['total_tests']}{m.group(7)}{c['intro']['drivers']}{m.group(9)}")),
    # v6 开场 notes 的四印章复述（版本/天数/测试/驱动一次重算）
    ("天数版本数",
     re.compile(r'(真实数字：)(\d+)(\s*个版本发在\s*)(\d+)(\s*天里，)(\d+)(\s*个测试每晚全绿)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['versions']}{m.group(3)}{c['intro']['days']}"
                   f"{m.group(5)}{c['total_tests']}{m.group(7)}")),
    ("天数版本数",
     re.compile(r'(真实数字：)(\d+)(\s*天发了\s*)(\d+)(\s*个版本，)(\d+)(\s*个测试，)(\d+)(\s*个设备驱动。)'),
     lambda m, c: (f"{m.group(1)}{c['intro']['days']}{m.group(3)}{c['intro']['versions']}"
                   f"{m.group(5)}{c['total_tests']}{m.group(7)}{c['intro']['drivers']}{m.group(9)}")),
    # 中文数词：天+个 MINOR / 天+个版本 成对才重写（单飞"三十天"不碰——
    # 「第五天/七天即焚/一天/当天」类叙事安全）；个 MINOR / 个版本单项；
    # 项测试 / 项全绿；讲稿的三树中文算术（主库…、隔离区…、复现区…）
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(天[，,、]?\s*)'
                r'([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个 MINOR)'),
     lambda m, c: f"{_cn(c['intro']['days'])}{m.group(2)}{_cn(c['intro']['minors'])}{m.group(4)}"),
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(天[，,、]?\s*)'
                r'([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个版本)'),
     lambda m, c: f"{_cn(c['intro']['days'])}{m.group(2)}{_cn(c['intro']['versions'])}{m.group(4)}"),
    ("天数版本数",
     re.compile(r'(和我这)([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(天做出的答案)'),
     lambda m, c: f"{m.group(1)}{_cn(c['intro']['days'])}{m.group(3)}"),
    # 动词分隔的中文对："三十天发十二个 MINOR"（"发"字隔开相邻配对形态）
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(天发)'
                r'([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个 MINOR)'),
     lambda m, c: f"{_cn(c['intro']['days'])}{m.group(2)}{_cn(c['intro']['minors'])}{m.group(4)}"),
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个 MINOR)'),
     lambda m, c: f"{_cn(c['intro']['minors'])}{m.group(2)}"),
    ("天数版本数",
     # 「连发 N 个版本」是第一波收官史（里程碑叙事，不在同步面）：
     # 负向后视挡住，否则 43 总版本会冒充"最后三天连发"数
     re.compile(r'(?<![一二三四五六七八九十百千零两])(?<!连发)([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(个版本)'),
     lambda m, c: f"{_cn(c['intro']['versions'])}{m.group(2)}"),
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([二三四五六七八九十百千零两][一二三四五六七八九十百千零两]*)(项测试)'),
     lambda m, c: f"{_cn(c['total_tests'])}{m.group(2)}"),
    # 破千分支：total_tests ≥1000 后 _cn() 输出以「一」开头（一千五百三十二），
    # 上条毯式模式首字符类排除「一」防散文「一项测试」误伤，破千值从此永不可
    # 匹配，锚点冻结在本次值（2026-10-18 全量扫描实测冻结 5 处显示位）。千
    # 字面量分支接管 ≥1000：数词必须含「千」——散文「一项/每一项测试」无千
    # 仍不可命中；两类按数量级互斥（<1000 走上条，≥1000 走本分支）。
    ("天数版本数",
     re.compile(r'(?<![一二三四五六七八九十百千零两])([一二三四五六七八九十百千零两]*千[一二三四五六七八九十百千零两]+)(项测试)'),
     lambda m, c: f"{_cn(c['total_tests'])}{m.group(2)}"),
    # 锚定形态（首尾皆字面量：先看测试规模：…项全绿）——数词类必须含「一」，
    # 与三树算术同理：破千值一千五百三十二否则永不可匹配（2026-10-18 修复；
    # 此前误随毯式排除「一」，intro deck 的 703→1532 只刷一次就冻结）。
    ("天数版本数",
     re.compile(r'(先看测试规模：)([一二三四五六七八九十百千零两]+)(项全绿)'),
     lambda m, c: f"{m.group(1)}{_cn(c['total_tests'])}{m.group(3)}"),
    # 三树中文算术：值槽含「一」（四百一十五/一千一百五十九），与毯式模式
    # 不同——锚点是「主库/、隔离区/、复现区」字面量，无定义句误伤风险，
    # 故数词类必须含「一」，否则四百一十五永不可匹配（2026-10-18 修复）
    ("天数版本数",
     re.compile(r'(主库)([一二三四五六七八九十百千零两]+)(、隔离区)([一二三四五六七八九十百千零两]+)(、复现区)([一二三四五六七八九十百千零两]+)'),
     lambda m, c: (f"{m.group(1)}{_cn(c['main_tests'])}{m.group(3)}"
                   f"{_cn(c['iso_tests'])}{m.group(5)}{_cn(c['repro_tests'])}")),
    # 散点 Arabic 短语：D 组 765 测试 / 每个数字都在仓库里——765 项测试
    ("天数版本数",
     re.compile(r'(D\s*组\s*)(\d+)(\s*测试和复现文化)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(3)}"),
    ("天数版本数",
     re.compile(r'(每个数字都在仓库里——)(\d+)(\s*项测试、)'),
     lambda m, c: f"{m.group(1)}{c['total_tests']}{m.group(3)}"),
    # deck 复现区命令行：$ pytest zones/Repro-ZCode/ -q → 71 passed
    ("测试计数",
     re.compile(r'(pytest zones/Repro-ZCode/ -q → )\d+( passed)'),
     lambda m, c: f"{m.group(1)}{c['repro_tests']}{m.group(2)}"),
    # deck 封面/尾页的日期脚（无版本号同排的裸日期戳）
    ("封面stamp",
     re.compile(r'(>)\d{4}-\d{2}-\d{2}(\s*·\s*github\.com/Yfredy/LAOS</span>)'),
     lambda m, c: f"{m.group(1)}{c['date']}{m.group(2)}"),
    # 讲稿 talk 数组里的版本基准声明（与封面 stamp 同源）
    ("封面stamp",
     re.compile(r'(声明版本基准：v)\d+\.\d+\.\d+(\s*·\s*)\d{4}-\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}{c['ver']}{m.group(2)}{c['date']}"),
    # 讲稿 notes 的版本角标（无日期同排形态）：「角标三个数字…：版本 v0.12.0、」
    # 与「语义化版本 v0.1 → v0.39」（短端点，另一模式管）不撞：
    # 要求完整 x.y.z 且后随「、」
    ("封面stamp",
     re.compile(r'(版本 v)\d+\.\d+\.\d+(?=、)'),
     lambda m, c: f"{m.group(1)}{c['ver']}"),
    # 短形态版本端点："v0.1 → v0.9"（intro 治理页三处，2026-10-18 收口）
    ("跨度端点",
     re.compile(r'(v0\.1\s*→\s*v0\.)\d+'),
     lambda m, c: f"{m.group(1)}{c['ver'].split('.')[1]}"),
    # 天数叙述的日期跨度端点："2026-09-04 → 10-05"——首版日（09-04）是
    # 固定历史事实，末端随发版日走（与同行「N 天」叙述同源，2026-10-18 收口）
    ("跨度端点",
     re.compile(r'(2026-09-04\s*→\s*)\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}{c['date'][5:]}"),
    # 短形态（无年份前缀）：guizang D2「44 天」卡实录——天数刷了、卡片
    # 日期端点没刷，同卡 "44 天" 对 "09-04 → 10-05"（31 天）自相矛盾。
    # (?<!-) 防误食上年份形态的尾部（两者替换值相同，纯粹为模式卫生）。
    ("跨度端点",
     re.compile(r'(?<!-)(09-04\s*→\s*)\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}{c['date'][5:]}"),
    # 「到」字形态：html-ppt D2 标题"09-04 到 10-05：一个完整需求波次 =
    # 一次 MINOR"——同页 kicker 已刷"44 天 39 个 MINOR"、frontend/guizang
    # 两个姊妹 deck 的 headline 均已随发版日走到 10-18，唯此标题端点
    # 漏刷（2026-10-18 收口；下方时间线表止于 v0.12.0 是内容级缺口，
    # 不阻碍本锚点，与 frontend 表同样止于 v0.12.0 的处理一致）。
    ("跨度端点",
     re.compile(r'(?<!-)(09-04\s*到\s*)\d{2}-\d{2}'),
     lambda m, c: f"{m.group(1)}{c['date'][5:]}"),
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
        "iso_tests": count_test_functions(REPO / "zones" / "AlwaysOnRec-ZCode" / "tests"),
        "repro_tests": count_test_functions(REPO / "zones" / "Repro-ZCode" / "tests"),
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


#: 文件名带 ISO 日期的「现场记录」类报告（如 2026-10-18-ppt-audit.md）：
#: 它们是某日取证/审计的快照，锚点数字必须停在当天——随后续发版刷新
#: 等于伪造历史。2026-10-18 实录：docs/ppt/*.md glob 曾把审计报告里的
#: "1146 TESTS GREEN" 取证行刷成新发版数，靠人工 checkout 才回退。
_DATED_REPORT_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def sync_docs(version: str, *, dry_run: bool = False,
              globs: list[str] | None = None, counts: dict | None = None,
              intro: dict | None = None,
              detail: bool = False, release_date: str | None = None) -> list[str]:
    """发版时同步全部介绍性文件（README/PROJECT_OVERVIEW/全部 PPT deck）。

    规则来源：AGENTS.md 记忆条目"每次发版更新所有介绍性文档"（2026-10-06）。
    只动"当前版本声明/封面 stamp/页脚/版本跨度端点/测试计数/叙事计数"六类锚点，
    带日期的里程碑史（如 "v0.12.0 (10-05)"）不动。返回逐文件报告行。
    counts 缺省用静态计数；发版主流程传 main_by_run 的实跑数。
    intro 缺省由 intro_counts(version, release_date) 实算（驱动数/天数/
    minor/总版本）；测试可显式传入固定值。
    release_date 缺省取当天（仅用于与当前版本同排的封面日期戳；历史里程碑
    日期不在同步面内）。
    detail=True（"项"模式）：报告行附逐锚点命中细目
    `[当前版本行×1,deck页脚×2,...]`，供终审五类锚点核查使用。
    """
    counts = counts or zone_test_counts()
    iso_date = release_date or _date.today().isoformat()
    ctx = {"ver": version,
           "main_tests": counts["main_tests"],
           "iso_tests": counts["iso_tests"],
           "repro_tests": counts["repro_tests"],
           "total_tests": counts["main_tests"] + counts["iso_tests"] + counts["repro_tests"],
           "date": iso_date,
           "short_date": iso_date[2:].replace("-", "."),
           "intro": intro or intro_counts(version, iso_date)}
    report = [f"docs-sync ctx: v{version}, 主库 {ctx['main_tests']} 测试, "
              f"总 {ctx['total_tests']} tests（含隔离 {counts['iso_tests']} + 复现 {counts['repro_tests']}）"
              f"，驱动 {ctx['intro']['drivers']} / {ctx['intro']['days']} 天 / "
              f"{ctx['intro']['minors']} MINOR / {ctx['intro']['versions']} 版本"]
    for pattern_glob in (globs or DOC_GLOBS):
        p = Path(pattern_glob)
        if p.is_absolute():  # 绝对路径（测试 fixture / 单文件点改）
            paths = [p] if p.is_file() else []
        else:
            paths = sorted(REPO.glob(pattern_glob))
        for path in paths:
            if not path.is_file():
                continue
            if _DATED_REPORT_RE.search(path.name):
                # dated 现场记录：排除 + 透明报告（防静默漏同步的误判）
                try:
                    rel = path.relative_to(REPO)
                except ValueError:
                    rel = path
                report.append(f"docs-sync: {rel} (dated 现场记录，排除刷新)")
                continue
            text = path.read_text(encoding="utf-8")
            new_text, hits = text, 0
            per_anchor: dict[str, int] = {}
            fctx = {**ctx, "is_html": path.suffix.lower() == ".html"}
            for name, rx, fmt in _DOC_PATTERNS:
                new_text, n = rx.subn(lambda m, f=fmt: f(m, fctx), new_text)
                hits += n
                if n:
                    per_anchor[name] = per_anchor.get(name, 0) + n
            if hits:
                try:
                    rel = path.relative_to(REPO)
                except ValueError:
                    rel = path  # 仓库外绝对路径（测试 fixture）
                if not dry_run:
                    path.write_text(new_text, encoding="utf-8")
                line = f"docs-sync: {rel} ({hits} 处{'，dry-run 未写' if dry_run else '，已写'})"
                if detail:
                    breakdown = ",".join(f"{k}×{v}" for k, v in per_anchor.items())
                    line += f" [{breakdown}]"
                report.append(line)
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
