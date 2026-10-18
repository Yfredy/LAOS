# tests/test_check_survey.py
"""综述校验器：结构/引用/条件/证据附录五组不变量。纯离线。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import check_survey as cs  # noqa: E402


GOOD_SURVEY = """# 测试综述

## 1. 摘要与结论
本文纳入 1 篇文献。[S01]

## 2. 范围、检索与筛选方法
检索与筛选见证据附录。

## 3. AgentOS × 音频 × 多模态 × 全天候录音
| 应用/系统 | 形态 | 处理位置 | 触发方式 | 音频角色 | 代表文献 | 可借鉴点 | 限制（含部署/合规条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |

## 4. 声学情感模型（SER）
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M | 小型 | 1.0 | 是 | 否 | [S01] | 低延迟 | 仅在 IEMOCAP（4 类） |

## 5. 音频事件识别（AED）
| 模型 | 档位 | 参数量(M) | 端侧 | 多模态 | 任务类型 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 小型 | 0.1 | 是 | 否 | tagging | [S01] | 可量化 | 仅 DCASE 低复杂度（128 KiB） |

## 6. 自动增益控制（AGC）
| 模型 | 档位 | 参数量(M) | 作用点 | 端侧 | 多模态 | 代表文献 | 优势 | 限制（含实验条件） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G | 经典DSP | n/a(非神经) | 采集后 | 是 | 否 | [S01] | 零延迟 | 仅闭环增益（无噪声场景） |

## 7. 跨领域对比
| 领域 | 规模分档依据 | 端侧判定依据 | 多模态现状 | 可比指标 | 不可比陷阱 | 代表文献 |
| --- | --- | --- | --- | --- | --- | --- |
| SER | 参数量 | 实测功耗 | 有但薄 | UAR | 类别数不同（4 类 vs 6 类） | [S01] |

## 8. 研究空白与未来方向
1. 做端侧中文场景评测（源于 [S01] 的局限：仅原型验证）。

## 9. 局限与未核实清单
- [未核实] 未取得全文的结论不进入正文。

## 10. 参考文献
| 编号 | 文献 | 年份 | 发表 venue | 链接 | 核验层级 | 局限 |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |
"""

GOOD_EVIDENCE = """# 证据附录

## 1. 范围合同
主题、核心问题、时间窗、纳入/排除标准见正文。

## 2. 检索日志
| 检索日 | 库/通道 | 检索式 | 年份窗 | 命中 | 纳入候选 |
| --- | --- | --- | --- | --- | --- |
| 2026-10-18 | corpus | audio event | 2017-2026 | 10 | 3 |

## 3. 筛选与排除
| 编号 | 文献 | 决定 | 理由 |
| --- | --- | --- | --- |
| C01 | Test Paper | 纳入 | 与核心问题直接相关 |

## 4. 单篇卡片
### [S01] Test Paper
- 问题：问题
- 方法：方法
- 数据：数据
- 指标与条件：指标（数据集）
- 局限：局限
- 对话：对话

## 5. 叙事大纲
| 小节 | 回答的问题 | 为什么这几篇放在一起 | 读者带走的一句判断 | 代表文献 |
| --- | --- | --- | --- | --- |
| §3 | 应用怎么落地 | 能力与失效互补 | 端侧克制常开 | [S01] |

## 6. 溯源核验记录
| 编号 | 核验对象 | 方式 | 结果 |
| --- | --- | --- | --- |
| S01 | 指标 | 原文表格 | 一致 |

## 7. 未核实清单
- [U01] 某宣称值 — 无全文 — 影响 §3
"""


def rules(vs):
    return {v.rule for v in vs}


def check(survey=GOOD_SURVEY, evidence=GOOD_EVIDENCE, strict=False):
    return cs.run_checks("s.md", survey, "e.md", evidence, strict=strict)


class CheckSurveyTest(unittest.TestCase):
    def test_good_pair_passes(self):
        self.assertEqual(check(), [])

    def test_strict_requires_all_sections(self):
        vs = check(survey=GOOD_SURVEY.replace("## 10. 参考文献", ""), strict=True)
        self.assertIn("survey-section", rules(vs))

    def test_duplicate_ref_id(self):
        dup = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S01 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        self.assertIn("ref-id", rules(check(survey=dup)))

    def test_undefined_citation(self):
        bad = GOOD_SURVEY.replace("| X | 耳机 | 端侧 | 显式 | 触发 | [S01] |",
                                  "| X | 耳机 | 端侧 | 显式 | 触发 | [S09] |")
        self.assertIn("cite-undefined", rules(check(survey=bad)))

    def test_unused_reference(self):
        bad = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S02 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        self.assertIn("cite-unused", rules(check(survey=bad)))

    def test_matrix_requires_condition(self):
        bad = GOOD_SURVEY.replace("仅在 IEMOCAP（4 类）", "仅在 IEMOCAP")
        self.assertIn("matrix-condition", rules(check(survey=bad)))

    def test_metric_without_condition(self):
        bad = GOOD_SURVEY.replace(
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |",
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | mAP 0.5 | 无任何条件 |")
        self.assertIn("metric-condition", rules(check(survey=bad)))

    def test_future_work_needs_citation_and_limitation(self):
        bad = GOOD_SURVEY.replace(
            "1. 做端侧中文场景评测（源于 [S01] 的局限：仅原型验证）。",
            "1. 做端侧中文场景评测。")
        self.assertIn("future-work-ref", rules(check(survey=bad)))
        self.assertIn("future-work-basis", rules(check(survey=bad)))

    def test_weak_ref_section_needs_qualifier(self):
        bad = GOOD_SURVEY.replace("| 全文 | 仅原型验证（n=1） |",
                                  "| 摘要 | 仅原型验证（n=1） |")
        self.assertIn("abstract-qualifier", rules(check(survey=bad)))

    def test_card_field_required(self):
        bad = GOOD_EVIDENCE.replace("- 局限：局限\n", "")
        self.assertIn("card-field", rules(check(evidence=bad)))

    def test_strict_outline_covers_every_ref(self):
        survey = GOOD_SURVEY.replace(
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |",
            "| S01 | Test Paper | 2024 | Interspeech | https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n"
            "| S02 | Test Two | 2024 | Interspeech | https://example.org/p2 | 全文 | 仅原型验证（n=2） |")
        survey = survey.replace("本文纳入 1 篇文献。[S01]", "本文纳入 2 篇文献。[S01][S02]")
        self.assertIn("outline-coverage", rules(check(survey=survey, strict=True)))

    def test_strict_empty_ref_table_and_unverified_leak(self):
        # 回归（review 发现 1）：§10 只剩表头+分隔线时，严格模式的
        # ref-count/citation 门禁与 [未核实] 泄漏扫描都不能整体失效。
        ref_row = ("| S01 | Test Paper | 2024 | Interspeech | "
                   "https://example.org/p1 | 全文 | 仅原型验证（n=1） |\n")
        self.assertIn(ref_row, GOOD_SURVEY)
        strict_vs = rules(check(survey=GOOD_SURVEY.replace(ref_row, ""), strict=True))
        self.assertIn("ref-count", strict_vs)
        self.assertIn("ref-schema", strict_vs)

        leaked = GOOD_SURVEY.replace(ref_row, "").replace(
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |",
            "| X | 耳机 | 端侧 | 显式 | 触发 | [S01] | 环形缓冲 | 仅原型验证（n=1） |\n"
            "[未核实] 某宣称数值待补原文")
        self.assertIn("unverified-leak", rules(check(survey=leaked)))

    def test_strict_header_only_evidence_ledgers(self):
        # 回归（review 发现 2）：§2/§3 只剩表头时不得被当成"证据完整"。
        log_row = "| 2026-10-18 | corpus | audio event | 2017-2026 | 10 | 3 |\n"
        screen_row = "| C01 | Test Paper | 纳入 | 与核心问题直接相关 |\n"
        self.assertIn(log_row, GOOD_EVIDENCE)
        self.assertIn(screen_row, GOOD_EVIDENCE)
        empty = GOOD_EVIDENCE.replace(log_row, "").replace(screen_row, "")
        vs = rules(check(evidence=empty, strict=True))
        self.assertIn("search-log", vs)
        self.assertIn("screen-table", vs)

    def test_selftest_cli(self):
        self.assertEqual(cs.main(["--selftest"]), 0)


if __name__ == "__main__":
    unittest.main()
