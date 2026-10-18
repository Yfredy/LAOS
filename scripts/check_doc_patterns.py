"""批量同步模式的静态+动态审计门槛（发版链旁路检查，不自动跑）。

背景（2026-10-18 实录）：`sync_docs` 的 200 余条锚点模式里出现过两类
结构性腐化——(1) lambda 里 `m.group(N)` 指到旧数字组，分隔符丢失、旧值
粘连（HTML 被写成 "44 天发了 391247 份调研文档"）；(2) 模式首字符类
排除「一」，counts 破千后输出以「一」开头（一千五百三十二）永不可重匹配，
锚点静默冻结。两类都不会让测试变红，只能靠结构回放发现。

四条不变量（对 HEAD 原文件逐模式回放）：
A 静态：`m.group(N)` 的 N 不得超过 `pattern.groups`，且 fmt 调用不抛异常。
B 分隔符组：凡「纯分隔符捕获组」（组文本既无 ASCII 数字也无中文数词）
  必须原样出现在替换输出里。
C 自洽：无 lookaround 的模式，替换输出必须还能被自身再次匹配。
D 幂等：同一模式对原文本 apply 两次，文本必须不变。

口径说明：ctx 里的版本/日期/计数只作为替换值样例参与运算；四条不变量
只查结构与幂等，不校验业务数值，故不随发版跑动（门禁数另见
`scripts/check_onboarding.py`）。
"""
import inspect
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import release  # noqa: E402

REPO = SCRIPTS.parent
CN = set("一二三四五六七八九十百千零两")
DIGITS = set("0123456789")


def tracked_decks() -> list[str]:
    """全部 deck（docs/ppt 下一级与两级 html，排除带 ISO 日期的现场记录）。"""
    out = subprocess.run(["git", "ls-files", "docs/ppt/*.html", "docs/ppt/*/*.html"],
                         cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        print(f"!! git ls-files 失败：{out.stderr.strip()}")
        sys.exit(2)
    return [p for p in out.stdout.splitlines()
            if p and not release._DATED_REPORT_RE.search(Path(p).name)]


def head_text(rel: str) -> str:
    out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        print(f"!! git show 失败：{rel}：{out.stderr.strip()}")
        sys.exit(2)
    return out.stdout


ctx = {"ver": release.read_current_version(),
       "main_tests": 1159, "iso_tests": 279, "repro_tests": 94,
       "total_tests": 1159 + 279 + 94,
       "date": "2026-10-18", "short_date": "26.10.18",
       "intro": release.intro_counts("0.39.0", "2026-10-18"),
       "is_html": True}

orig = {rel: head_text(rel) for rel in tracked_decks()}
print(f"patterns: {len(release._DOC_PATTERNS)}；files: {len(orig)}")
print("=" * 70)

viol_a = viol_b = viol_c = viol_d = 0
for idx, (name, rx, fmt) in enumerate(release._DOC_PATTERNS):
    try:
        src = inspect.getsource(fmt)
    except (OSError, TypeError):
        src = ""
    for n in re.findall(r"m\.group\((\d+)\)", src):
        if int(n) > rx.groups:
            print(f"[A] pattern#{idx} ({name}) 引用 m.group({n}) 但仅 {rx.groups} 组")
            print(f"    rx={rx.pattern[:120]}")
            viol_a += 1

    for rel, text in orig.items():
        for m in rx.finditer(text):
            try:
                out = fmt(m, ctx)
            except Exception as e:  # IndexError 等
                print(f"[A!] pattern#{idx} ({name}) fmt 抛异常：{e!r}")
                print(f"    rx={rx.pattern[:120]}\n    matched: {m.group(0)[:120]!r}")
                viol_a += 1
                continue
            for gi in range(1, rx.groups + 1):
                g = m.group(gi)
                if g is None:
                    continue
                if DIGITS & set(g) or CN & set(g):
                    continue  # 值槽，允许改写
                if g not in out:
                    print(f"[B] pattern#{idx} ({name}) {rel} 分隔符组 g{gi} 丢失")
                    print(f"    rx={rx.pattern[:160]}")
                    print(f"    matched: {m.group(0)[:120]!r}")
                    print(f"    g{gi}={g!r} -> out={out[:120]!r}")
                    viol_b += 1
            # C 仅对无 lookaround 的模式生效：含断言的模式，断言上下文不在
            # 替换 span 内，span 级重匹配必然失败，属检查方法局限。
            if not re.search(r"\(\?[=!<]", rx.pattern) and not rx.search(out):
                print(f"[C] pattern#{idx} ({name}) 输出无法被自身模式重匹配")
                print(f"    rx={rx.pattern[:160]}")
                print(f"    matched: {m.group(0)[:120]!r}\n    out={out[:120]!r}")
                viol_c += 1

    for rel, text in orig.items():
        t1, _ = rx.subn(lambda m, f=fmt: f(m, ctx), text)
        t2, _ = rx.subn(lambda m, f=fmt: f(m, ctx), t1)
        if t1 != t2:
            print(f"[D] pattern#{idx} ({name}) {rel} 二次 apply 文本变化（非幂等）")
            print(f"    rx={rx.pattern[:160]}")
            for a, b in zip(t1.splitlines(), t2.splitlines()):
                if a != b:
                    print(f"    一次: {a[:140]!r}\n    二次: {b[:140]!r}")
                    break
            viol_d += 1

print("=" * 70)
print(f"A(越界/异常)={viol_a} B(分隔符丢失)={viol_b} "
      f"C(不自洽)={viol_c} D(非幂等)={viol_d}")
sys.exit(1 if (viol_a or viol_b or viol_c or viol_d) else 0)
