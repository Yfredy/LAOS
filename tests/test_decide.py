# tests/test_decide.py
"""decide 决策层测试：Clef 三判型 schema / 类型化 Decision 校验 / RuleBackend
规则打分 / 后端插拔表（Task 3 clef 后端的挂点契约）。

语义依据 docs/research/2026-10-07-cloudflare-clef.md §二：决策步接收状态、
按 schema（noul/choice/score）返回带概率的类型化答案。

    python -m unittest tests.test_decide -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos import decide  # noqa: E402
from laos.decide import (  # noqa: E402
    Decision,
    DecisionSchema,
    RuleBackend,
    get_backend,
    register_backend,
)


class TestDecisionSchema(unittest.TestCase):
    def test_noul_defaults(self):
        schema = DecisionSchema(type="noul")
        self.assertEqual(schema.options, None)
        self.assertEqual(schema.threshold, 0.5)
        self.assertEqual(schema.type, "noul")

    def test_invalid_type_rejected(self):
        for bad in ("bool", "rank", "", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                DecisionSchema(type=bad)

    def test_choice_requires_nonempty_unique_options(self):
        with self.assertRaises(ValueError):
            DecisionSchema(type="choice")  # 缺 options
        with self.assertRaises(ValueError):
            DecisionSchema(type="choice", options=[])
        with self.assertRaises(ValueError):
            DecisionSchema(type="choice", options=["deploy", "deploy"])  # 重复键坍缩
        with self.assertRaises(ValueError):
            DecisionSchema(type="choice", options=["deploy", ""])  # 空选项
        ok = DecisionSchema(type="choice", options=["deploy", "rollback"])
        self.assertEqual(ok.options, ["deploy", "rollback"])

    def test_non_choice_rejects_options(self):
        with self.assertRaises(ValueError):
            DecisionSchema(type="noul", options=["yes", "no"])  # options 仅 choice 可用

    def test_threshold_bounds(self):
        for bad in (-0.1, 1.5, "mid"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                DecisionSchema(type="score", threshold=bad)
        self.assertEqual(DecisionSchema(type="score", threshold=0.0).threshold, 0.0)
        self.assertEqual(DecisionSchema(type="score", threshold=1).threshold, 1)


class TestDecisionValidation(unittest.TestCase):
    def test_noul_valid_sums_one(self):
        d = Decision("yes", {"yes": 0.8, "no": 0.2}, "test")
        self.assertEqual(d.answer, "yes")
        self.assertFalse(d.calibrated)

    def test_out_of_bounds_rejected(self):
        with self.assertRaises(ValueError):
            Decision("yes", {"yes": -0.1, "no": 1.1}, "test")
        with self.assertRaises(ValueError):
            Decision("yes", {"yes": 1.01}, "test")

    def test_multi_key_sum_one_accepted(self):
        d = Decision("a", {k: 0.25 for k in "abcd"}, "test")
        self.assertAlmostEqual(sum(d.probabilities.values()), 1.0)

    def test_multi_key_sum_off_one_rejected(self):
        with self.assertRaises(ValueError):  # 和 1.2（各项本身合法）
            Decision("a", {"a": 0.6, "b": 0.6}, "test")
        with self.assertRaises(ValueError):  # 和 0.9
            Decision("a", {"a": 0.5, "b": 0.4}, "test")

    def test_single_key_exempt_from_sum(self):
        # score 的单键概率即分数本身，不做和=1 约束
        Decision("yes", {"score": 0.3}, "test")


class TestRuleBackendNoul(unittest.TestCase):
    def setUp(self):
        self.backend = RuleBackend()

    def test_bool_field_true_false(self):
        d = self.backend.decide({"flag": True}, DecisionSchema(type="noul"))
        self.assertEqual(d.answer, "yes")
        self.assertEqual(d.probabilities, {"yes": 1.0, "no": 0.0})
        d = self.backend.decide({"flag": False}, DecisionSchema(type="noul"))
        self.assertEqual(d.answer, "no")
        self.assertEqual(d.probabilities, {"yes": 0.0, "no": 1.0})

    def test_probability_field_thresholding(self):
        schema = DecisionSchema(type="noul")  # threshold 0.5
        d = self.backend.decide({"confidence": 0.8}, schema)
        self.assertEqual(d.answer, "yes")
        self.assertAlmostEqual(d.probabilities["yes"], 0.8)
        self.assertAlmostEqual(d.probabilities["no"], 0.2)
        strict = DecisionSchema(type="noul", threshold=0.9)
        d = self.backend.decide({"confidence": 0.8}, strict)
        self.assertEqual(d.answer, "no")

    def test_no_hit_uniform(self):
        d = self.backend.decide({"unrelated": "x"}, DecisionSchema(type="noul"))
        self.assertEqual(d.probabilities, {"yes": 0.5, "no": 0.5})
        self.assertEqual(d.answer, "yes")  # 0.5 >= 默认阈值 0.5
        self.assertIn("uniform", d.source)  # 无命中要在 Decision 标注


class TestRuleBackendChoice(unittest.TestCase):
    def setUp(self):
        self.backend = RuleBackend()
        self.schema = DecisionSchema(type="choice",
                                     options=["deploy", "rollback"])

    def test_keyword_strength_normalized(self):
        state = {"note": "deploy now, deploy again, or rollback"}
        d = self.backend.decide(state, self.schema)
        self.assertEqual(d.answer, "deploy")
        self.assertAlmostEqual(d.probabilities["deploy"], 2 / 3)
        self.assertAlmostEqual(d.probabilities["rollback"], 1 / 3)
        self.assertAlmostEqual(sum(d.probabilities.values()), 1.0)
        self.assertEqual(d.source, "rule")  # 有命中不带 uniform 标注

    def test_no_hit_uniform(self):
        d = self.backend.decide({"note": "nothing relevant"}, self.schema)
        self.assertEqual(d.probabilities, {"deploy": 0.5, "rollback": 0.5})
        self.assertEqual(d.answer, "deploy")  # 并列取第一最大
        self.assertIn("uniform", d.source)


class TestRuleBackendScore(unittest.TestCase):
    def setUp(self):
        self.backend = RuleBackend()

    def test_numeric_passthrough_and_threshold(self):
        d = self.backend.decide({"score": 0.8}, DecisionSchema(type="score"))
        self.assertEqual(d.answer, "yes")  # 0.8 >= 0.5
        self.assertEqual(d.probabilities, {"score": 0.8})
        strict = DecisionSchema(type="score", threshold=0.9)
        self.assertEqual(self.backend.decide({"score": 0.8}, strict).answer, "no")

    def test_boundary_equal_threshold_is_yes(self):
        d = self.backend.decide({"score": 0.9},
                                DecisionSchema(type="score", threshold=0.9))
        self.assertEqual(d.answer, "yes")  # >= 语义（含等号）

    def test_out_of_range_clamped(self):
        d = self.backend.decide({"score": 2.0}, DecisionSchema(type="score"))
        self.assertEqual(d.probabilities, {"score": 1.0})
        d = self.backend.decide({"score": -1.0}, DecisionSchema(type="score"))
        self.assertEqual(d.probabilities, {"score": 0.0})

    def test_no_numeric_field_midpoint(self):
        d = self.backend.decide({"text": "no numbers"}, DecisionSchema(type="score"))
        self.assertEqual(d.probabilities, {"score": 0.5})
        self.assertEqual(d.answer, "yes")
        self.assertIn("uniform", d.source)


class TestBackendRegistry(unittest.TestCase):
    def test_rule_pre_registered(self):
        backend = get_backend("rule")
        d = backend({"score": 0.9}, DecisionSchema(type="score"))
        self.assertEqual(d.answer, "yes")

    def test_register_and_get(self):
        def fake(state, schema):
            return Decision("yes", {"yes": 1.0, "no": 0.0}, "fake")

        register_backend("probe-fake", fake)
        self.assertIs(get_backend("probe-fake"), fake)
        # 同名覆盖（后端热替换的挂点语义）
        register_backend("probe-fake", fake)
        self.assertIs(get_backend("probe-fake"), fake)

    def test_unregistered_key_error(self):
        with self.assertRaises(KeyError):
            get_backend("definitely-not-registered")
        # clef 后端在 Task 3 登记前不可用（fail-loud，不静默兜底）
        try:
            get_backend("clef")
        except KeyError:
            pass
        else:
            self.fail("clef 未登记时应 KeyError")


if __name__ == "__main__":
    unittest.main()
