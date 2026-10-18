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

    def test_dated_field_report_excluded(self):
        """2026-10-18 实录：DOC_GLOBS 的 docs/ppt/*.md 会把 dated 审计报告
        （2026-10-18-ppt-audit.md 的 "1146 TESTS GREEN" 取证行）刷成新值——
        文件名带 ISO 日期的报告是现场记录，不随后续发版漂移；活文档照常同步。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            dated = tmp / "2026-10-18-ppt-audit.md"
            dated.write_text("stamp 已刷 **1146 TESTS GREEN**\n", encoding="utf-8")
            living = tmp / "laos-intro-outline.md"
            living.write_text("# 765 项回归测试\n", encoding="utf-8")
            report = release.sync_docs("0.39.0", globs=[str(dated), str(living)])
            # dated 报告一字未动
            self.assertIn("1146 TESTS GREEN", dated.read_text(encoding="utf-8"))
            # 活文档照常同步
            self.assertNotIn("765", living.read_text(encoding="utf-8"))
            # 跳过必须透明：报告里有排除行
            self.assertTrue(
                any("排除" in line for line in report), report)


class DeckAnchorForms(unittest.TestCase):
    """2026-10-18 补：deck 页首/页脚/封面/终场卡的其余版本与测试锚形态。

    这些形态此前不在同步面内，detailed·funding 的 v0.12.0/765 长期漂移；
    同时钉住"三段式算术式重算"——防止主库计数模式把 `= 703` 直接刷成
    主库数，造出 353+350=1159 的假等式（当日实测事故）。
    """

    COUNTS = {"main_tests": 1159, "iso_tests": 279, "repro_tests": 94}

    def _fixture(self, tmp: Path) -> Path:
        f = tmp / "deck.html"
        f.write_text(
            '<span class="fnum">v0.12.0 · 765 tests · 15 drivers · 01 / 19</span>\n'
            '<span class="mono">v0.12.0 · 765 TESTS · 15 DRIVERS · 12 RELEASES</span>\n'
            '<span class="meta">V0.12.0 · 765 TESTS · 15 DRV · 12 MINOR</span>\n'
            '<span class="seal">v0.12.0 · 2026-10-05</span>\n'
            '<p>v0.12.0 · 2026-10-05 · github.com/Yfredy/LAOS</p>\n'
            '<p>REV v0.12.0 · 2026-10-05</p>\n'
            '<p>GITHUB.COM/YFREDY/LAOS · V0.12.0 · 26.10.05 · 765 TESTS</p>\n'
            'v0.1.0（09-04）→ v0.12.0（10-05）\n'
            'v0.1.0..v0.12.0\n'
            '主库 353 + 隔离区 350 = 703 项测试全绿\n'
            'v0.12.0 · GitHub Yfredy/LAOS · 703 tests green (主库353 + 隔离区350)\n'
            '主库 1146 项测试全绿\n'
            '<h2 class="h-xl">30 天，12 个版本，<br/>765 项测试全绿。</h2>\n'
            '<span class="pill">765 项测试全绿</span>\n'
            '<span class="mono p">765</span> green（主库 1159 + 隔离区 279 + 复现区 94）\n'
            '<div class="ledger-num">765</div>\n'
            '  <div class="ledger-label"><div>TESTS GREEN</div></div>\n'
            '<tr><td>测试</td><td class="m">765</td><td>主库 1159 / 隔离区 279</td></tr>\n'
            'v0.12.0 (10-05) 双工时序\n',
            encoding="utf-8")
        return f

    def test_chrome_version_date_and_total_synced(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._fixture(Path(d))
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn("v0.39.0 · 1532 tests · 17 drivers", text)
            self.assertIn("v0.39.0 · 1532 TESTS · 17 DRIVERS", text)
            self.assertIn("V0.39.0 · 1532 TESTS · 17 DRV", text)
            self.assertIn("v0.39.0 · 2026-10-18", text)
            self.assertIn("V0.39.0 · 26.10.18 · 1532 TESTS", text)
            self.assertIn("v0.1.0（09-04）→ v0.39.0（10-18）", text)
            self.assertIn("v0.1.0..v0.39.0", text)
            self.assertIn("1532 tests green (主库1159 + 隔离区279 + 复现区 94)", text)
            # 裸 "N 项测试全绿" 在 deck（html）里是三树合计：原 765（415+279+71）
            # 不得被刷成主库 1159（2026-10-18 实测的口径错位）
            self.assertIn("44 天，43 个版本，<br/>1532 项测试全绿", text)
            self.assertIn('<span class="pill">1532 项测试全绿</span>', text)
            # 合计展示位（字体/台账/表格大数字）同样按三树合计刷新
            self.assertIn('<span class="mono p">1532</span> green（主库', text)
            self.assertIn('<div class="ledger-num">1532</div>', text)
            self.assertIn('<td class="m">1532</td><td>主库', text)

    def test_markdown_bare_green_count_uses_main_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "intro.md"
            f.write_text("51 个核心模块 · 1146 项测试全绿 · 17 个驱动\n",
                         encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn("· 1159 项测试全绿 ·", text)
            self.assertNotIn("1532", text)

    def test_onboarding_and_living_guide_forms(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "onboarding.md"
            f.write_text(
                "| 主库测试数 | 1146 项（`OK (skipped=5)`） |\n"
                "Expected: `Ran 1146 tests` + `OK (skipped=5)`\n"
                "> 数字口径：v0.39.0 ｜ 1146 项测试（2026-10-18 实跑）｜ 51 模块\n"
                "- **1146 项测试全绿**（主库，2026-10-18 实跑；skipped=5）\n",
                encoding="utf-8")
            release.sync_docs("0.40.0", globs=[str(f)],
                              counts={"main_tests": 1200,
                                      "iso_tests": 280, "repro_tests": 95},
                              release_date="2026-10-25")
            text = f.read_text(encoding="utf-8")
            self.assertIn("| 主库测试数 | 1200 项（", text)
            self.assertIn("`Ran 1200 tests`", text)
            self.assertIn("1200 项测试（2026-10-25 实跑）", text)
            self.assertIn("**1200 项测试全绿**（主库，2026-10-25 实跑", text)

    def test_composition_recomputed_not_overwritten(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._fixture(Path(d))
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn("主库 1159 + 隔离区 279 + 复现区 94 = 1532 项测试全绿", text)
            self.assertNotIn("353 + 350 = 1159", text)
            self.assertIn("主库 1159 项测试全绿", text)
            # 幂等：同步输出必须能被同一套模式再次匹配（2026-10-18 实测：
            # "…… + 隔离区 350)" 的输出加了复现区后旧模式不再命中，合计
            # 从第二次发版起就冻住了）。第二次同步必须零变化。
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_zone_breakdown_and_arithmetic_forms(self):
        """三树明细/比例条/算术式与 funding chrome 的收口形态。

        合计已刷而明细停在旧值时同页自相矛盾；比例条必须与数字同源重算。
        同时钉住边界：六来源 "71 项测试" 是复现区的合法子集（94 = 71 + 23），
        不得被三树明细模式误伤。
        """
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(
                '<span class="chip">v<b>0.12.0</b></span>\n'
                '<span class="chip"><b>765</b> 测试全绿</span>\n'
                '<div class="ticker">[<b>V0.12.0</b>]&nbsp;[TESTS <b>765 GREEN</b>]</div>\n'
                '<p>SRC / <b>v0.12.0</b></p>\n'
                '<div><div class="bignum">765</div><hr class="hair">\n'
                '  <p style="x">测试全绿 · TDD 先红后绿<br>主库 1159 / 隔离区 279 / 复现区 94</p></div>\n'
                '<span class="cmd">$ python -m unittest discover -s tests → Ran 1146 tests · OK</span>\n'
                '<p><span style="font-weight:700">laos</span> 主库 <span class="c mono" style="font-size:19px">415 tests</span></p>\n'
                '<p><span style="font-weight:700">Repro</span> 复现区 <span class="c mono" style="font-size:19px">71 tests</span></p>\n'
                '<div class="stbar">\n'
                '  <div style="flex:54.2;background:var(--green)">415</div>\n'
                '  <div style="flex:36.5;background:var(--blue)">279</div>\n'
                '  <div style="flex:9.3;background:var(--purple)">71</div>\n'
                '</div>\n'
                '<div class="splitbar">\n'
                '  <div class="sg1" style="width:54.2%">主库 415</div>\n'
                '  <div class="sg2" style="width:36.5%">AlwaysOnRec 279</div>\n'
                '  <div class="sg3" style="width:9.3%">Repro 71</div>\n'
                '</div>\n'
                '<div class="legend"><span><b>54.2%</b> 内核与驱动语义</span>'
                '<span><b>36.5%</b> 录音沙箱</span><span><b>9.3%</b> 论文复现</span></div>\n'
                '<span class="ledger-num">415</span>\n'
                '  <div class="ledger-label"><div>laos 主库</div></div>\n'
                '<span class="ledger-num">71</span>\n'
                '  <div class="ledger-label"><div>Repro 复现区</div></div>\n'
                '<tr><td><b>laos</b> 主库</td><td>内核 + 驱动</td><td class="mono">415</td></tr>\n'
                '<tr><td><b>Repro</b></td><td>论文复现区</td><td class="mono">71</td></tr>\n'
                '<div class="foot"><span>D · 质量文化组</span><span>765 = 415 + 279 + 71</span></div>\n'
                '<div class="c3 panel"><div class="gold mono" style="font-size:64px;font-weight:800">765</div>'
                '<div class="caption">测试全绿<br>415 主库 + 279 隔离 + 71 复现</div></div>\n'
                '<p>六来源 71 项测试：TDD</p>\n'
                '<p>**v0.39.0 ｜ 765 项测试（实跑）**</p>\n'
                '<p>工程质量被主库 765 项测试全绿和 116 份调研兜住。</p>\n'
                '<p>我们用主库 765 项测试全绿兜住行为。</p>\n',
                encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn('<span class="chip">v<b>0.39.0</b></span>', text)
            self.assertIn('<span class="chip"><b>1532</b> 测试全绿</span>', text)
            self.assertIn('[<b>V0.39.0</b>]', text)
            self.assertIn('[TESTS <b>1532 GREEN</b>]', text)
            self.assertIn('SRC / <b>v0.39.0</b>', text)
            self.assertIn('<div class="bignum">1532</div>', text)
            self.assertIn('→ Ran 1159 tests · OK', text)
            self.assertIn('font-size:19px">1159 tests', text)
            self.assertIn('font-size:19px">94 tests', text)
            self.assertIn('flex:75.7;background:var(--green)">1159', text)
            self.assertIn('flex:18.2;background:var(--blue)">279', text)
            self.assertIn('flex:6.1;background:var(--purple)">94', text)
            self.assertIn('width:75.7%">主库 1159', text)
            self.assertIn('width:18.2%">AlwaysOnRec 279', text)
            self.assertIn('width:6.1%">Repro 94', text)
            self.assertIn('<b>75.7%</b> 内核与驱动语义', text)
            self.assertIn('<b>18.2%</b> 录音沙箱', text)
            self.assertIn('<b>6.1%</b> 论文复现', text)
            self.assertIn('1532 = 1159 + 279 + 94', text)
            self.assertIn('1532</div><div class="caption">测试全绿<br>1159 主库 + 279 隔离 + 94 复现', text)
            # 复现区合法子集不得被明细锚误伤
            self.assertIn('六来源 71 项测试', text)
            # 讲稿类裸主库口径
            self.assertIn('｜ 1159 项测试（实跑）', text)
            self.assertIn('被主库 1159 项测试全绿', text)
            self.assertIn('用主库 1159 项测试全绿', text)
            # 幂等：第二轮零变化
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_dated_milestone_history_untouched(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._fixture(Path(d))
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertIn("v0.12.0 (10-05) 双工时序",
                          f.read_text(encoding="utf-8"))

    def test_huashu_semver_card_days_minors(self):
        # huashu 版本纪律卡：commits；30 天 12 个 MINOR（v0.1.0 → v0.39.0）——
        # HEAD 实录的混合态：同行版本端点刷了、卡片天数/版本数停在 30/12。
        # 「commits；」前缀锚 + 幂等复验
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(
                '<p>SemVer + conventional commits；30 天 12 个 MINOR（v0.1.0 → v0.39.0）。</p>\n',
                encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn('commits；44 天 39 个 MINOR（v0.1.0 → v0.39.0）。', text)
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_pill_days_minors_optional_version(self):
        # pill 形态：「30 天 · 12 个 MINOR 版本」（funding）与「30 天 · 12 个
        # MINOR」（detailed，无「版本」后缀）——原模式 `版本?` 只让「本」可选，
        # detailed 形永远漏刷（2026-10-18 修复）
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(
                '<span class="pill">30 天 · 12 个 MINOR 版本</span>\n'
                '<span class="pill">30 天 · 12 个 MINOR</span>\n',
                encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn('<span class="pill">44 天 · 39 个 MINOR 版本</span>', text)
            self.assertIn('<span class="pill">44 天 · 39 个 MINOR</span>', text)
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_device_driver_phrase_three_forms(self):
        # 「N 个设备驱动」三形态（2026-10-18 补）：整体加粗 / 数字单独加粗 /
        # 中文形。outline 早写 17，decks 7 处阿拉伯 + 1 处中文停在 15。
        # 散文「一个设备驱动」不得误伤（毯式首类排除一）。
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(
                '<p>开源 v0.39.0 · 15 个设备驱动 · 听觉栈自研</p>\n'
                '<p>8 环闸门 + <b>15 个设备驱动</b> + 端侧听觉栈</p>\n'
                '<span class="chip"><b>15</b> 个设备驱动</span>\n'
                '<p>进展：十五个设备驱动、听觉栈纯标准库</p>\n'
                '<p>每一个设备驱动都是隔离子进程。</p>\n',
                encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            text = f.read_text(encoding="utf-8")
            self.assertIn('· 17 个设备驱动 · 听觉栈自研', text)
            self.assertIn('<b>17 个设备驱动</b>', text)
            self.assertIn('<span class="chip"><b>17</b> 个设备驱动</span>', text)
            self.assertIn('十七个设备驱动、听觉栈纯标准库', text)
            self.assertIn('每一个设备驱动都是隔离子进程。', text)  # 散文不碰
            release.sync_docs("0.39.0", globs=[str(f)], counts=self.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)


class NarrativeAnchorGroupNumbers(unittest.TestCase):
    """2026-10-18 实录 bug 的回归钉：叙事锚模式组号错位。

    四条 h2 模式把「原始匹配数字组」当「尾随文案组」用——尾随文案被丢弃，
    "30 天，12 个版本，" 刷成 "44 天，4312"；title 模式还引用了不存在的
    g5（真实 deck 上直接 IndexError）；guizang t-meta 丢了 g3 分隔符并把
    原始天数重复追加在新天数后；短端点用 rsplit 拼出 "v0.0.39"。替换必须
    落在裸数字上、尾随文案原样接回。
    """

    def _sync(self, text: str) -> str:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(text, encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)],
                              counts=DeckAnchorForms.COUNTS,
                              release_date="2026-10-18")
            return f.read_text(encoding="utf-8")

    def test_h2_tail_text_preserved(self):
        text = self._sync(
            '<h2 class="h-xl">30 天，12 个 MINOR。</h2>\n'
            '<h2>30 天，12 个 MINOR，每版本都有 changelog</h2>\n'
            '<h2 class="h-xl">30 天，12 个版本，<br/>765 项测试全绿。</h2>\n'
            '<h2>30 天 12 版本，每一行都可复现</h2>\n')
        self.assertIn('<h2 class="h-xl">44 天，39 个 MINOR。</h2>', text)
        self.assertIn('<h2>44 天，39 个 MINOR，每版本都有 changelog</h2>', text)
        self.assertIn('<h2 class="h-xl">44 天，43 个版本，<br/>1532 项测试全绿。</h2>', text)
        self.assertIn('<h2>44 天 43 版本，每一行都可复现</h2>', text)

    def test_talk_title_tmeta_and_short_endpoint(self):
        text = self._sync(
            'title: "30 天 12 个 MINOR（重点表格页）"\n'
            'title: "驱动全景 15 个设备（重点表格页）"\n'
            '<span class="t-meta">MINOR RELEASES · V0.1.0 → V0.12.0 · 30 DAYS</span>\n'
            '语义化版本 v0.1 → v0.12 · 一个完整需求波次 = 一次 MINOR\n')
        self.assertIn('title: "44 天 39 个 MINOR（重点表格页）"', text)
        self.assertIn('title: "驱动全景 17 个设备（重点表格页）"', text)
        self.assertIn('MINOR RELEASES · V0.1.0 → V0.39.0 · 44 DAYS', text)
        self.assertIn('语义化版本 v0.1 → v0.39 · ', text)

    def test_main_lab_runline_form(self):
        """主库命令行锚：pytest collect 形态已改为 unittest 实跑形态，
        模式必须命中 "→ Ran N tests · OK" 并只刷主库数。"""
        text = self._sync(
            '<span class="cmd">$ python -m unittest discover -s tests → Ran 1146 tests · OK</span>\n')
        self.assertIn('→ Ran 1159 tests · OK', text)
        self.assertNotIn('1146', text)

    def test_chinese_numeral_idempotent(self):
        """中文数词锚的幂等钉：_cn(1532)="一千五百三十二" 首字"一"不在
        首字符类里，无负向后视时第二次 apply 会从第 2 字起匹配自己的输出、
        每次回贴一个"一"（2026-10-18 实录：跑三轮刷成"一一一千五百三十二"）。
        首刷转换与二次零变化都必须成立。"""
        fixture = (
            '七百六十五项测试全绿\n'
            '三十天，十二个版本\n'
            '十二个 MINOR\n'
            '十五个驱动\n'
            '四十四天，三十九个 MINOR\n'
        )
        text = self._sync(fixture)
        self.assertIn('一千五百三十二项测试全绿', text)
        self.assertIn('四十四天，四十三个版本', text)
        self.assertIn('三十九个 MINOR', text)
        self.assertIn('十七个驱动', text)
        # 二次 apply 必须零变化（含 &gt;1000 的项测试与全部数词形态）
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(text, encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)],
                              counts=DeckAnchorForms.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)

    def test_days_row_date_span_endpoints(self):
        """天数叙述的同行日期端点（三种形态，2026-10-18 收口）：
        年份形态、短形态、「到」字形态都必须随发版日走到 10-18——guizang
        D2「44 天」卡实录：天数刷了、短日期端点没刷，同卡 "44 天" 对
        "09-04 → 10-05"（31 天）自相矛盾；html-ppt D2 标题"09-04 到
        10-05"同页 kicker 已刷 44 天，端点同样漏刷。页眉 chrome
        "SS · 26.10.05" 不在同步面。"""
        text = self._sync(
            '<p class="sub reveal">2026-09-04 → 10-05：三十天，十二个 MINOR</p>\n'
            '<span class="t-meta">09-04 → 10-05</span>\n'
            '<h2 class="h2 mt-s">09-04 到 10-05：<em>一个完整需求波次 = 一次 MINOR。</em></h2>\n'
            '<header class="chrome-min"><div class="r">SS · 26.10.05 · 01 / 19</div></header>\n')
        self.assertIn('2026-09-04 → 10-18：四十四天，三十九个 MINOR', text)
        self.assertIn('<span class="t-meta">09-04 → 10-18</span>', text)
        self.assertIn('09-04 到 10-18：<em>一个完整需求波次', text)
        self.assertIn('SS · 26.10.05 · 01 / 19', text)  # chrome 日期不动
        # 幂等：二次 apply 零变化（短形态不得误食年形态尾部）
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(text, encoding="utf-8")
            release.sync_docs("0.39.0", globs=[str(f)],
                              counts=DeckAnchorForms.COUNTS,
                              release_date="2026-10-18")
            self.assertEqual(f.read_text(encoding="utf-8"), text)


class TestTestCountAnchorFullMatch(unittest.TestCase):
    """2026-10-09 实录 bug 的回归钉：测试计数锚点 \d{3} 只吃尾三位，
    千位计数下每次发版叠一个 "1"（README 被写成 111111051）。锚点必须
    全量匹配数字串——千位数原样、腐化串整体吃掉、两位里程碑仍不碰。"""

    CASES = [  # (锚点正则片段, 该锚点的语境样本)
        (r"\d{3,}(?= 项回归测试)", "# 1051 项回归测试"),
        (r"(?<=主库 )\d{3,}(?= 测试)", "主库 1051 测试"),
        (r"\d{3,}(?= 项测试守护)", "1051 项测试守护"),
        (r"\d{3,}(?= 项回归测试（)", "1051 项回归测试（注"),
        (r"(?<!\d)(?<!主库 )([=+]\s*)?(\d{3,})(?= 项测试全绿)", "1051 项测试全绿"),
        (r"\d{3,}(?=\s*TESTS GREEN)", "1051 TESTS GREEN"),
        (r"(?<=·\s)\d{3,}(?=\s*GREEN)", "· 1051 GREEN"),
    ]

    def _patterns(self):
        return [(rx.pattern, rx) for name, rx, _ in release._DOC_PATTERNS
                if name == "测试计数"]

    def test_thousand_count_matched_whole(self):
        pats = dict(self._patterns())
        for frag, text in self.CASES:
            self.assertIn(frag, pats, f"锚点缺失: {frag}")
            m = pats[frag].search(text)
            self.assertIsNotNone(m, f"{frag} 未命中 {text!r}")
            self.assertEqual(m.group(), "1051", f"{frag} 在 {text!r} 只吃了部分数字")

    def test_corrupted_prepended_ones_matched_entirely(self):
        # 六次叠 1 的腐化串必须被整串吃掉（修复后一次同步即复原为实跑数）
        pats = dict(self._patterns())
        m = pats[r"\d{3,}(?= 项回归测试)"].search("# 111111051 项回归测试")
        self.assertEqual(m.group(), "111111051")

    def test_two_digit_milestone_still_untouched(self):
        # 原防误伤意图保留：两位数里程碑行不命中"主库 N 测试"锚点
        pats = dict(self._patterns())
        self.assertIsNone(pats[r"(?<=主库 )\d{3,}(?= 测试)"].search("主库 42 测试里程碑"))


class TestCnTestCountThousandBranch(unittest.TestCase):
    """2026-10-18 冻结锚回归：毯式中文数词模式首字符类排除「一」防散文
    误伤，但 total_tests 破千后 _cn() 输出以「一」开头（一千五百三十二），
    4 处显示位（项测试×4 / 先看测试规模…项全绿×1）永久冻结——下次发版
    静默不刷新。修复：锚定形态数词类含「一」；毯式项测试按数量级分叉，
    千字面量分支接管 ≥1000（散文「一项测试」无千仍不命中）。"""

    NEXT = {"main_tests": 1227, "iso_tests": 279, "repro_tests": 94}  # total 1600
    NOW = {"main_tests": 1159, "iso_tests": 279, "repro_tests": 94}   # total 1532

    def _sync(self, text: str, counts: dict, version: str = "0.40.0") -> str:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "deck.html"
            f.write_text(text, encoding="utf-8")
            release.sync_docs(version, globs=[str(f)], counts=counts,
                              release_date="2026-11-01")
            return f.read_text(encoding="utf-8")

    def test_thousand_cn_total_not_frozen(self):
        # 破千值的两种中文锚点都必须随新 total（1600）走，而不是冻结在 1532
        text = self._sync(
            '先看测试规模：一千五百三十二项全绿。\n'
            '角标三个数字：一千五百三十二项测试全绿。\n'
            '流水线证据：一千五百三十二项测试、四十七份调研。\n',
            counts=self.NEXT)
        self.assertIn('先看测试规模：一千六百项全绿。', text)
        self.assertIn('一千六百项测试全绿。', text)
        self.assertIn('一千六百项测试、四十七份调研。', text)

    def test_prose_one_still_untouched(self):
        # 散文「一项/每一项测试」无千，两个模式都不可命中（防误伤语义不变）
        prose = '每一项测试都 nightly 全绿，一项测试都不许跳过。\n'
        self.assertEqual(self._sync(prose, counts=self.NEXT), prose)

    def test_below_thousand_still_blanket(self):
        # <1000 值仍由毯式模式接管（七百六十五 → 六百六十五），千分支不抢食
        text = self._sync(
            '七百六十五项测试全绿\n',
            counts={"main_tests": 500, "iso_tests": 100, "repro_tests": 65})
        self.assertIn('六百六十五项测试全绿', text)

    def test_idempotent_at_thousand(self):
        # 同值（1532）二次 apply 零变化：千分支与锚定形态都重算同值
        once = self._sync(
            '先看测试规模：一千五百三十二项全绿。\n一千五百三十二项测试全绿。\n',
            counts=self.NOW, version="0.39.0")
        twice = self._sync(once, counts=self.NOW, version="0.39.0")
        self.assertEqual(once, twice)


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
                    "docs/ONBOARDING.md",
                    "docs/guide/laos-feishu-intro.md",
                    "zones/AlwaysOnRec-Trae/README.md",
                    "zones/AlwaysOnRec-DB/README.md",
                    "zones/AlwaysOnRec-ZCode/README.md"):
            self.assertIn(rel, covered, f"DOC_GLOBS 漏覆盖 {rel}")
        # 讲稿/lecture 是某日快照（开场声明 10-05 封面数字），不进同步面
        self.assertNotIn("docs/guide/laos-feishu-intro-speech.md", covered)


if __name__ == "__main__":
    unittest.main()
