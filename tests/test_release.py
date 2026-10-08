# tests/test_release.py
"""发版助手（Task 3）：conventional commits → semver 推导 + 三棵树 __version__ 同步。

覆盖任务书 Step 1 的七条用例：
    ①②③④ next_version 四规则（feat 集→0.8.0 / fix→0.7.1 / "!"→0.8.0（0.x 不动
    major）/ 纯 docs·chore→不变）
    ⑤   sync_versions("0.7.0") 后三棵树 __version__ 一致（测试自带备份恢复，
        不把仓库状态钉死在 0.7.0）
    ⑥   changelog_section 六分类草稿段（至少出现实际有的 Added/Fixed）
    ⑦   commits_since 用注入的 subprocess mock 测（不依赖真实 tag）

    python -m unittest tests.test_release -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.release as release  # noqa: E402
from scripts.release import (  # noqa: E402
    VERSION_FILES,
    changelog_section,
    commits_since,
    next_version,
    sync_versions,)

VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


class NextVersionRules(unittest.TestCase):
    """next_version：0.x 阶段四条推导规则（任务书 ①-④）。"""

    def test_feat_set_bumps_minor(self):  # ①
        self.assertEqual(next_version("0.7.0", ["feat: a", "feat: b"]), "0.8.0")

    def test_fix_bumps_patch(self):  # ②
        self.assertEqual(next_version("0.7.0", ["fix: a"]), "0.7.1")

    def test_bang_marker_bumps_minor_not_major_in_0x(self):  # ③
        self.assertEqual(next_version("0.7.0", ["feat!: a"]), "0.8.0")
        self.assertEqual(next_version("0.7.0", ["feat(api)!: a"]), "0.8.0")

    def test_docs_chore_only_keeps_current(self):  # ④
        self.assertEqual(next_version("0.7.0", ["docs: a", "chore: b"]), "0.7.0")

    def test_breaking_footer_in_subject_also_bumps(self):
        self.assertEqual(next_version("0.7.0", ["feat: a (BREAKING CHANGE: drop old api)"]), "0.8.0")

    def test_mixed_fix_and_feat_feat_wins(self):
        self.assertEqual(next_version("0.7.0", ["fix: a", "feat: b", "docs: c"]), "0.8.0")
        self.assertEqual(next_version("0.7.0", ["docs: a", "chore: b", "fix: c"]), "0.7.1")

    def test_major_ge_1_breaking_bumps_major(self):
        # 0.x 不动 major；到 1.x 后 breaking 恢复 semver 常规（major+1）
        self.assertEqual(next_version("1.2.3", ["feat!: a"]), "2.0.0")
        self.assertEqual(next_version("1.2.3", ["feat: a"]), "1.3.0")


class ChangelogSection(unittest.TestCase):
    """changelog_section：Keep a Changelog 六分类草稿段，只列实际有的分类（⑥）。"""

    def test_added_and_fixed_present(self):  # ⑥
        section = changelog_section("0.8.0", ["feat: x", "fix: y"])
        self.assertIn("## [v0.8.0]", section)
        self.assertIn("### Added", section)
        self.assertIn("### Fixed", section)
        self.assertIn("- feat: x", section)
        self.assertIn("- fix: y", section)

    def test_only_categories_with_entries_appear(self):
        section = changelog_section("0.7.1", ["fix: y"])
        self.assertIn("### Fixed", section)
        self.assertNotIn("### Added", section)
        self.assertNotIn("### Changed", section)

    def test_breaking_entry_flagged(self):
        section = changelog_section("0.8.0", ["feat!: drop legacy api"])
        self.assertIn("BREAKING", section)


class SyncVersions(unittest.TestCase):
    """sync_versions：三棵树 __version__ 同步一致（⑤）。"""

    def setUp(self):
        self._backup = {p: p.read_text(encoding="utf-8") for p in VERSION_FILES}

    def tearDown(self):
        for p, text in self._backup.items():
            p.write_text(text, encoding="utf-8")

    def test_sync_writes_all_three_trees(self):  # ⑤
        written = sync_versions("0.7.0")
        self.assertEqual(
            sorted(str(w) for w in written),
            sorted(str(p) for p in VERSION_FILES),
        )
        for p in VERSION_FILES:
            m = VERSION_RE.search(p.read_text(encoding="utf-8"))
            self.assertIsNotNone(m, f"{p} 缺 __version__")
            self.assertEqual(m.group(1), "0.7.0", f"{p} 未同步")


class CommitsSince(unittest.TestCase):
    """commits_since：git log <tag>..HEAD --format=%s（注入 mock，⑦）。"""

    def test_parses_subjects_and_invokes_git_correctly(self):  # ⑦
        fake = mock.Mock(stdout="feat: a\nfix: b\n\ndocs: c\n", returncode=0)
        with mock.patch("scripts.release.subprocess.run", return_value=fake) as run:
            subjects = commits_since("v0.6.0")
        run.assert_called_once_with(
            ["git", "log", "v0.6.0..HEAD", "--format=%s"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(subjects, ["feat: a", "fix: b", "docs: c"])  # 空行剔除


class CountTestFunctions(unittest.TestCase):
    def test_counts_def_test_methods(self):
        import tempfile
        td = Path(__import__("tempfile").mkdtemp())
        try:
            (td / "test_a.py").write_text(
                "def test_one():\n    pass\ndef helper():\n    pass\n"
                "def test_two():\n    pass\n", encoding="utf-8")
            (td / "test_b.py").write_text(
                "class T:\n    def test_x(self):\n        pass\n", encoding="utf-8")
            self.assertEqual(release.count_test_functions(td), 3)
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_missing_dir_returns_zero(self):
        self.assertEqual(release.count_test_functions(REPO / "no_such_dir"), 0)


class SyncDocs(unittest.TestCase):
    """发版文档同步（记忆规则：AGENTS.md『每次发版更新所有介绍性文件』）。"""

    def _fixture(self, tmp: Path):
        f = tmp / "deck.html"
        f.write_text(
            '<span class="stamp">v0.12.0</span>'
            '开源 v0.12.0 · 15 驱动'
            'github.com/Yfredy/LAOS · v0.12.0 · 765 tests'
            'v0.1.0 → v0.12.0，每版本有 tag'
            'v0.12.0 (10-05) 双工时序'
            '论文周报 → 42 测试 → v0.12.0'
            '当前版本 **v0.15.1**（主库 495 测试 + 495 项回归测试 + 253 项测试守护）',
            encoding="utf-8")
        return f

    def test_all_anchors_updated_and_history_kept(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._fixture(Path(d))
            release.sync_docs("0.16.0", globs=[str(f)])
            text = f.read_text(encoding="utf-8")
            self.assertIn('<span class="stamp">v0.16.0</span>', text)
            self.assertIn("开源 v0.16.0 ·", text)
            self.assertIn("LAOS · v0.16.0 · ", text)
            self.assertIn("v0.1.0 → v0.16.0", text)
            self.assertIn("v0.12.0 (10-05) 双工时序", text)   # 带日期里程碑史保留
            self.assertIn("42 测试 → v0.12.0", text)          # 历史叙述保留
            main_n = release.zone_test_counts()["main_tests"]
            self.assertIn(f"主库 {main_n} 测试", text)
            self.assertNotIn("495 项回归测试", text)

    def test_dry_run_does_not_write(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._fixture(Path(d))
            before = f.read_text(encoding="utf-8")
            release.sync_docs("0.16.0", dry_run=True, globs=[str(f)])
            self.assertEqual(f.read_text(encoding="utf-8"), before)

    def test_missing_glob_ignored(self):
        report = release.sync_docs("0.16.0", globs=["no_such_file.md"])
        self.assertEqual(len(report), 1)  # 只有 ctx 行


class TestNewDomainAxisAndDocGlobs(unittest.TestCase):
    """release 工具债三件：新文档域轴（+new-domain 标记）+ sync_docs 项模式
    （detail 逐锚点细目）+ DOC_GLOBS 补全（intro 组 deck/outline 与三棵树
    README——2026-10-08 核查发现 AlwaysOnRec-DB/README.md 带 3 处锚点但
    从未被同步）。"""

    def test_new_domain_marker_bumps_minor(self):
        # README §十：新文档域 = 完整需求波次 = MINOR；纯 docs 波次用
        # subject 尾部 "+new-domain" 标记显式声明（next_version 无法从
        # 文本自动识别"新域"）
        self.assertEqual(
            next_version("0.7.0", ["docs(corpus): 19,792 篇语料库 +new-domain"]),
            "0.8.0")
        self.assertEqual(next_version("1.2.3", ["docs: 新指南 +new-domain"]), "1.3.0")

    def test_plain_docs_still_no_release(self):
        self.assertEqual(next_version("0.7.0", ["docs(corpus): 语料快照"]), "0.7.0")

    def test_marker_mentioned_mid_subject_does_not_trigger(self):
        # 自指 bug 回归：subject 正文提及 "+new-domain" 字样（文档/工具提交）
        # 不得误触发 MINOR——标记必须收尾于 subject 末端
        self.assertEqual(
            next_version("0.7.0", ["fix(scripts): document +new-domain minor axis"]),
            "0.7.1")
        self.assertEqual(
            next_version("0.7.0", ["docs: explain the +new-domain marker convention"]),
            "0.7.0")

    def test_sync_docs_detail_reports_per_anchor_counts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "intro.md"
            f.write_text("当前版本 **v0.16.0**" + "\n" + "123 项回归测试" + "\n",
                         encoding="utf-8")
            report = release.sync_docs("0.17.0", globs=[str(f)], dry_run=True,
                                       detail=True)
            line = [ln for ln in report if str(f) in ln][0]
            self.assertIn("当前版本行×1", line)
            self.assertIn("测试计数×1", line)
            # 缺省 detail=False：输出行与既有格式不回归（无逐锚点细目）
            plain = release.sync_docs("0.17.0", globs=[str(f)], dry_run=True)
            pline = [ln for ln in plain if str(f) in ln][0]
            self.assertNotIn("×", pline)

    def test_doc_globs_cover_intro_group_and_all_three_trees(self):
        covered = set()
        for g in release.DOC_GLOBS:
            for p in release.REPO.glob(g):
                covered.add(p.relative_to(release.REPO).as_posix())
        for rel in ("docs/ppt/laos-intro-outline.md",
                    "docs/ppt/laos-intro-html-ppt.html",
                    "docs/ppt/laos-intro-huashu.html",
                    "docs/ppt/laos-detailed-outline.md",
                    "docs/ppt/laos-funding-outline.md",
                    "zones/AlwaysOnRec-Trae/README.md",
                    "zones/AlwaysOnRec-DB/README.md",
                    "zones/AlwaysOnRec-ZCode/README.md"):
            self.assertIn(rel, covered, f"DOC_GLOBS 漏覆盖 {rel}")


if __name__ == "__main__":
    unittest.main()
