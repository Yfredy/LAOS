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

from scripts.release import (  # noqa: E402
    VERSION_FILES,
    changelog_section,
    commits_since,
    next_version,
    sync_versions,
)

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


if __name__ == "__main__":
    unittest.main()
