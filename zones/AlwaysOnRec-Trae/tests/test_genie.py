# tests/test_genie.py
"""drv_genie —— 端侧 LLM 大脑驱动（QAIRT Genie / OpenAI 兼容双后端）。

    python -m unittest tests.test_genie -v

测试策略：genie 后端注入 fake runner（断言命令行形状）；openai 后端用
mock HTTP；双后端缺失断言 EIO 且消息含两个原因。真机 Genie/ollama 的
实际调用留给 runbook 手工验收。
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

import drv_genie  # noqa: E402

ENV_KEYS = ("LAOS_GENIE_BIN", "LAOS_GENIE_CONFIG", "LAOS_LLM_BASE_URL",
            "LAOS_LLM_BACKEND", "LAOS_LLM_MODEL", "LAOS_LLM_TIMEOUT")


class EnvCleanCase(unittest.TestCase):
    """清理 LLM 相关 env 与模块配置变量，保证探测确定性。"""

    def setUp(self):
        self._prev_exe = drv_genie._genie_exe_path
        self._prev_cfg = drv_genie._genie_cfg_path
        self._prev_base = drv_genie._openai_base_url
        self._prev_runner = drv_genie._genie_runner
        self._prev_env = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        drv_genie._genie_exe_path = None
        drv_genie._genie_cfg_path = None
        drv_genie._openai_base_url = None
        drv_genie._genie_runner = None

    def tearDown(self):
        drv_genie._genie_exe_path = self._prev_exe
        drv_genie._genie_cfg_path = self._prev_cfg
        drv_genie._openai_base_url = self._prev_base
        drv_genie._genie_runner = self._prev_runner
        for k, v in self._prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestGenieBackend(EnvCleanCase):
    def setUp(self):
        super().setUp()
        drv_genie._genie_exe_path = "fake-genie-t2t-run.exe"
        drv_genie._genie_cfg_path = "C:/models/qwen/config.json"

    def test_calls_runner_with_config_and_prompt(self):
        calls = []
        drv_genie._genie_runner = (
            lambda exe, config, prompt, timeout: calls.append((exe, config, prompt))
            or "genie-answer")
        drv_genie._genie_cfg_path = "C:/models/qwen/config.json"
        out = drv_genie.llm_chat("你好", system="你是 laos", max_tokens=64)
        self.assertIn("genie-answer", out)
        self.assertEqual(calls[0][1], "C:/models/qwen/config.json")
        self.assertIn("你好", calls[0][2])
        self.assertIn("你是 laos", calls[0][2])  # system 并入 prompt

    def test_backend_reported(self):
        drv_genie._genie_runner = lambda *a, **k: "ok"
        drv_genie._genie_cfg_path = "C:/models/qwen/config.json"
        out = drv_genie.llm_chat("hi")
        self.assertIn('"backend": "genie"', out)


class TestOpenAIBackend(EnvCleanCase):
    def test_chat_via_openai_compatible(self):
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            status = 200

            def read(self):
                return json.dumps(
                    {"choices": [{"message": {"content": "ollama-answer"}}]}
                ).encode()

        def fake_urlopen(req, timeout=0):
            captured["url"] = req if isinstance(req, str) else req.full_url
            captured["body"] = json.loads(req.data.decode()) \
                if hasattr(req, "data") else {}
            return FakeResp()

        drv_genie._genie_runner = None
        drv_genie._genie_cfg_path = None
        with mock.patch("urllib.request.urlopen", fake_urlopen), \
             mock.patch.dict(os.environ, {"LAOS_LLM_BASE_URL": "http://127.0.0.1:11434/v1",
                                          "LAOS_LLM_MODEL": "qwen-local"}), \
             mock.patch.object(drv_genie, "_openai_base_url", "http://127.0.0.1:11434/v1"), \
             mock.patch.object(drv_genie, "_genie_exe_path", None):
            out = drv_genie.llm_chat("hi", max_tokens=32)
        self.assertIn("ollama-answer", out)
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/v1/chat/completions")
        self.assertEqual(captured["body"]["max_tokens"], 32)
        self.assertEqual(captured["body"]["model"], "qwen-local")


class TestNoBackend(EnvCleanCase):
    def test_reports_both_reasons(self):
        with mock.patch.object(drv_genie, "_genie_exe_path", None), \
             mock.patch.dict(os.environ, {"LAOS_LLM_BASE_URL": "http://127.0.0.1:1/v1"}), \
             self.assertRaises(IOError) as cm:
            drv_genie.llm_chat("hi")
        self.assertIn("genie:", str(cm.exception))
        self.assertIn("openai:", str(cm.exception))


class TestStatus(EnvCleanCase):
    def test_status_lists_backends(self):
        out = drv_genie.llm_status()
        self.assertIn("genie", out)
        self.assertIn("openai", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
