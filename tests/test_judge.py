# tests/test_judge.py
"""judge 判断器测试：select 工厂 / Rule 零依赖兜底 / Cloud·Local HTTP 契约。

只测新面——HTTP 全程 mock curl（subprocess.run），不发真实网络请求。

    python -m unittest tests.test_judge -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.context import COMPACT_JUDGE_QUESTION  # noqa: E402
from laos.judge import (  # noqa: E402
    CloudBackend,
    JudgeBackend,
    JudgeError,
    JudgeResult,
    LocalBackend,
    RuleBackend,
    SafeJudge,
    env_flag,
    select,
)
from laos.kernel import PREJUDGE_JUDGE_QUESTION  # noqa: E402
from laos.memory import REMEMBER_JUDGE_QUESTION  # noqa: E402
from laos.skills import SKILL_JUDGE_QUESTION  # noqa: E402

_DENY_WORDS = ("危险", "删除全部", "格式化", "rm -rf", "泄露隐私")


def _curl_ok(stdout: str) -> mock.Mock:
    """伪造 curl 子进程：退出码 0、stdout 为给定响应体。"""
    return mock.Mock(return_value=subprocess.CompletedProcess([], 0,
                                                             stdout=stdout,
                                                             stderr=""))


class TestSelect(unittest.TestCase):
    def test_default_returns_rule(self):
        # 未设置 / none / rule → RuleBackend（零依赖兜底，保证默认链路可测）
        with mock.patch.dict(os.environ):
            os.environ.pop("LAOS_JEV_BACKEND", None)
            self.assertIsInstance(select(), RuleBackend)
        for value in ("none", "rule"):
            with mock.patch.dict(os.environ, {"LAOS_JEV_BACKEND": value}):
                self.assertIsInstance(select(), RuleBackend, value)
                self.assertIsInstance(select(), JudgeBackend)

    def test_env_local_selects_local(self):
        with mock.patch.dict(os.environ, {"LAOS_JEV_BACKEND": "local"}):
            self.assertIsInstance(select(), LocalBackend)

    def test_env_cloud_selects_cloud(self):
        with mock.patch.dict(os.environ, {"LAOS_JEV_BACKEND": "cloud"}):
            self.assertIsInstance(select(), CloudBackend)

    def test_invalid_value_falls_back_rule(self):
        # 未知值不炸链路：兜底 RuleBackend（与 enforcement.select 同款哲学）
        with mock.patch.dict(os.environ, {"LAOS_JEV_BACKEND": "bogus"}):
            self.assertIsInstance(select(), RuleBackend)


class TestRuleBackend(unittest.TestCase):
    def setUp(self):
        self.bk = RuleBackend()

    def test_noul_deny_wordlist(self):
        # question 命中 deny 词表 → deny，置信度 ≥ 0.99，且 raw 记录命中词（审计）
        for word in _DENY_WORDS:
            with self.subTest(word=word):
                r = self.bk.noul("整理相册", f"帮我把这些照片 {word} 掉")
                self.assertIsInstance(r, JudgeResult)
                self.assertEqual(r.verdict, "deny")
                self.assertGreaterEqual(r.confidence, 0.99)
                self.assertEqual(r.raw["matched"], word)

    def test_noul_case_insensitive(self):
        # rm -rf 大小写变体同样命中（词表匹配不区分大小写）
        r = self.bk.noul("ctx", "please RM -RF the disk")
        self.assertEqual(r.verdict, "deny")

    def test_noul_clean_allows(self):
        r = self.bk.noul("ctx", "把照片按日期排序可以吗")
        self.assertEqual(r.verdict, "allow")
        self.assertIsNone(r.raw["matched"])

    def test_choice_uniform_returns_first(self):
        # 均匀打分：等概率 → 返回第一项，置信度 1/N
        options = ["方案甲", "方案乙", "方案丙", "方案丁"]
        r = self.bk.choice("ctx", "选一个", options)
        self.assertEqual(r.verdict, "方案甲")
        self.assertAlmostEqual(r.confidence, 0.25)

    def test_choice_empty_options_failsafe_deny(self):
        # 空选项是调用方 bug：兜底拒绝（fail-safe），置信度 0
        r = self.bk.choice("ctx", "选一个", [])
        self.assertEqual(r.verdict, "deny")
        self.assertEqual(r.confidence, 0.0)

    def test_score_uniform_middle(self):
        # 均匀打分：取中位 level，置信度 1/levels
        r = self.bk.score("ctx", "评个分", levels=5)
        self.assertEqual(r.verdict, "level_2")
        self.assertAlmostEqual(r.confidence, 0.2)


class TestCloudBackend(unittest.TestCase):
    def test_request_contract_context_question_and_auth(self):
        resp = json.dumps({"verdict": "allow", "confidence": 0.8})
        fake = _curl_ok(resp)
        bk = CloudBackend(api_key="sk-test",
                          base_url="https://api.example.test/v1")
        with mock.patch("laos.judge.subprocess.run", fake):
            r = bk.noul("夜里整理照片", "可以删除模糊的吗")
        fake.assert_called_once()
        cmd = fake.call_args.args[0]
        self.assertIn("https://api.example.test/v1/systemone", cmd)
        self.assertIn("Authorization: Bearer sk-test", cmd)
        self.assertEqual(cmd[cmd.index("-X") + 1], "POST")
        body = json.loads(cmd[cmd.index("--data-binary") + 1])
        self.assertEqual(body["mode"], "noul")
        self.assertEqual(body["context"], "夜里整理照片")
        self.assertEqual(body["question"], "可以删除模糊的吗")
        self.assertEqual(body["options"], [])
        self.assertEqual(body["levels"], 0)
        self.assertEqual(r.verdict, "allow")
        self.assertAlmostEqual(r.confidence, 0.8)
        self.assertEqual(r.raw, json.loads(resp))

    def test_curl_failure_raises_judge_error(self):
        fake = mock.Mock(return_value=subprocess.CompletedProcess(
            [], 7, stdout="", stderr="curl: (7) 连接被拒"))
        bk = CloudBackend(api_key="sk-test")
        with mock.patch("laos.judge.subprocess.run", fake):
            with self.assertRaises(JudgeError):
                bk.noul("ctx", "q")


class TestLocalBackend(unittest.TestCase):
    def test_parses_openai_compatible_response(self):
        content = json.dumps({"verdict": "deny", "confidence": 0.93},
                             ensure_ascii=False)
        resp = json.dumps(
            {"choices": [{"message": {"role": "assistant",
                                      "content": content}}]},
            ensure_ascii=False)
        fake = _curl_ok(resp)
        bk = LocalBackend(endpoint="http://127.0.0.1:8931")
        with mock.patch("laos.judge.subprocess.run", fake):
            r = bk.score("系统上下文", "危险吗", levels=5)
        fake.assert_called_once()
        cmd = fake.call_args.args[0]
        self.assertIn("http://127.0.0.1:8931/v1/chat/completions", cmd)
        self.assertEqual(cmd[cmd.index("-X") + 1], "POST")
        body = json.loads(cmd[cmd.index("--data-binary") + 1])
        msg = body["messages"][0]
        self.assertEqual(msg["role"], "user")
        inner = json.loads(msg["content"])
        self.assertEqual(inner["mode"], "score")
        self.assertEqual(inner["context"], "系统上下文")
        self.assertEqual(inner["question"], "危险吗")
        self.assertEqual(inner["levels"], 5)
        # OpenAI 兼容响应：choices[0].message.content 为 JSON
        self.assertEqual(r.verdict, "deny")
        self.assertAlmostEqual(r.confidence, 0.93)
        self.assertEqual(
            json.loads(r.raw["choices"][0]["message"]["content"])["verdict"],
            "deny")


class TestSafeJudge(unittest.TestCase):
    """安全代理（遗留 B）：后端健康时透传，故障时 fail-open 到 allow 0.0。"""

    class _Ok(JudgeBackend):
        name = "ok"

        def noul(self, context, question):
            return JudgeResult("deny", 0.9, {"src": "noul"})

        def choice(self, context, question, options):
            return JudgeResult(options[0], 1.0)

        def score(self, context, question, levels=5):
            return JudgeResult("level_1", 0.5)

    class _Boom(JudgeBackend):
        name = "boom"

        def noul(self, context, question):
            raise JudgeError("缺少 TypeSafe API key")

        def choice(self, context, question, options):
            raise JudgeError("网络超时")

        def score(self, context, question, levels=5):
            raise RuntimeError("非 JudgeError 的异常也必须兜住")

    def test_passthrough_when_backend_healthy(self):
        safe = SafeJudge(self._Ok())
        r = safe.noul("ctx", "q")
        self.assertEqual((r.verdict, r.confidence), ("deny", 0.9))
        self.assertEqual(safe.choice("ctx", "q", ["甲", "乙"]).verdict, "甲")
        self.assertEqual(safe.score("ctx", "q", levels=3).verdict, "level_1")
        self.assertIn("ok", safe.name)

    def test_fails_open_on_any_backend_error(self):
        # 三判型任一异常（含非 JudgeError）→ allow 0.0，raw 带上错误供审计
        safe = SafeJudge(self._Boom())
        for call in (lambda: safe.noul("ctx", "q"),
                     lambda: safe.choice("ctx", "q", ["甲"]),
                     lambda: safe.score("ctx", "q")):
            with self.subTest(call=call):
                r = call()
                self.assertEqual(r.verdict, "allow")
                self.assertEqual(r.confidence, 0.0)
                self.assertIn("error", r.raw)
                self.assertIn("boom", r.raw["backend"])
        self.assertIn("boom", safe.name)


class TestEnvFlag(unittest.TestCase):
    """Jev 开关值解析（遗留 A 裁决）：仅 1/true/yes 为真，0/false/no 是关。"""

    def test_truthy_values_only(self):
        for value in ("1", "true", "TRUE", "Yes", " yes "):
            with mock.patch.dict(os.environ, {"LAOS_JEV_X": value}):
                self.assertTrue(env_flag("LAOS_JEV_X"), value)
        for value in ("0", "false", "no", "off", "", "  "):
            with mock.patch.dict(os.environ, {"LAOS_JEV_X": value}):
                self.assertFalse(env_flag("LAOS_JEV_X"), value)
        with mock.patch.dict(os.environ):
            os.environ.pop("LAOS_JEV_X", None)
            self.assertFalse(env_flag("LAOS_JEV_X"))


class TestJudgeQuestionCriteria(unittest.TestCase):
    """四闸问句的 criteria 式结构（Task 3）：单字符串内"指示段\\n判据段"。

    判据段必须与各 gate 的 deny 方向一致——方向写反会直接毁掉闸门：
    memory deny=不入库 / compact deny=不可丢弃 / skill deny=不沉淀 /
    prejudge deny=拒绝执行。全文与消费点的一致性由
    test_calibrate_judge 的 import 契约及各消费测试的关键词钉守住，
    此处只钉结构与方向。
    """

    # 常量 → (allow 邻接判据, deny 邻接判据)——方向词必须紧跟所属分支：
    # “是”后括注 allow 语义后果、“否”后括注 deny 语义后果。独立子串断言
    # 漏掉方向词漂移（如 allow 词漂进“否”分支时旧四断言仍全绿），
    # 邻接钉 + 分号衔接钉保证正反判据各自成段不互换
    DIRECTIONS = {
        REMEMBER_JUDGE_QUESTION: ("判“是”（allow，可入库）",
                                  "；判“否”（deny，不入库）"),
        COMPACT_JUDGE_QUESTION: ("判“是”（allow，可丢弃并入摘要）",
                                 "；判“否”（deny，不可丢弃，保留在窗口）"),
        SKILL_JUDGE_QUESTION: ("判“是”（allow，可沉淀为技能）",
                               "；判“否”（deny，不沉淀）"),
        PREJUDGE_JUDGE_QUESTION: ("判“是”（allow，放行）",
                                  "；判“否”（deny，拒绝执行）"),
    }

    def test_four_questions_carry_two_part_criteria(self):
        for question, (allow_adj, deny_adj) in self.DIRECTIONS.items():
            with self.subTest(head=question[:12]):
                self.assertIsInstance(question, str)
                self.assertIn("\n", question)        # 两段式：指示段 + 判据段
                self.assertIn(allow_adj, question)   # “是”分支邻接 allow 后果
                self.assertIn(deny_adj, question)    # 分号衔接“否”分支，邻接 deny 后果
        # prejudge 是模板常量：保留 {tool}/{args}/{agent} 注入位（判据文本
        # 不得引入额外花括号，否则 .format 渲染炸内核链路）
        for placeholder in ("{tool}", "{args}", "{agent}"):
            self.assertIn(placeholder, PREJUDGE_JUDGE_QUESTION)
        rendered = PREJUDGE_JUDGE_QUESTION.format(
            tool="proc.exec", args={"cmdline": "echo"}, agent="jev")
        for placeholder in ("{tool}", "{args}", "{agent}"):
            self.assertNotIn(placeholder, rendered)  # 无未渲染占位符
        self.assertTrue(rendered.startswith("允许执行 proc.exec"))


if __name__ == "__main__":
    unittest.main()
