# tests/test_llm.py
"""laos.llm —— 云端大脑（OpenAI 兼容 chat.completions，纯 stdlib）。

    python -m unittest tests.test_llm -v

零依赖红线：urllib 直连；opt-in 三值 env；异常归一 LLMError（fail 方向：
抛错给调用方降级）。urlopen 全程 mock——不打真网络。
"""
from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.llm import DEFAULT_SYSTEM, LLMClient, LLMError  # noqa: E402


def _ok_response(content: str):
    """构造 OpenAI 兼容成功响应的 mock urlopen 返回。"""
    body = json.dumps({"choices": [{"message": {"role": "assistant",
                                                "content": content}}]}).encode()
    resp = mock.Mock()
    resp.read.return_value = body
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


class TestFromEnv(unittest.TestCase):
    def test_empty_env_returns_none(self):
        self.assertIsNone(LLMClient.from_env({}))
        self.assertIsNone(LLMClient.from_env({"LAOS_LLM_BASE_URL": "https://x"}))
        self.assertIsNone(LLMClient.from_env({"LAOS_LLM_MODEL": "m"}))

    def test_full_env(self):
        c = LLMClient.from_env({"LAOS_LLM_BASE_URL": "https://api.x.com/v1/",
                                 "LAOS_LLM_MODEL": "m1",
                                 "LAOS_LLM_KEY": "sk-x",
                                 "LAOS_LLM_TIMEOUT_S": "5",
                                 "LAOS_LLM_SYSTEM": "自定义"})
        self.assertEqual(c.base_url, "https://api.x.com/v1")  # 尾斜杠剥掉
        self.assertEqual(c.model, "m1")
        self.assertEqual(c.api_key, "sk-x")
        self.assertEqual(c.timeout_s, 5.0)
        self.assertEqual(c.system, "自定义")

    def test_bad_timeout_falls_back(self):
        c = LLMClient.from_env({"LAOS_LLM_BASE_URL": "u", "LAOS_LLM_MODEL": "m",
                                "LAOS_LLM_TIMEOUT_S": "不是数"})
        self.assertEqual(c.timeout_s, 60.0)

    def test_default_system_when_blank(self):
        c = LLMClient.from_env({"LAOS_LLM_BASE_URL": "u", "LAOS_LLM_MODEL": "m",
                                "LAOS_LLM_SYSTEM": "  "})
        self.assertEqual(c.system, DEFAULT_SYSTEM)


class TestChat(unittest.TestCase):
    def _client(self, **kw):
        return LLMClient(base_url=kw.get("base", "https://api.x.com/v1"),
                         model="m1", api_key=kw.get("key", ""))

    def test_success_and_url_join(self):
        c = self._client()
        with mock.patch("laos.llm.urllib.request.urlopen",
                        return_value=_ok_response("你好")) as up:
            out = c.chat([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "你好")
        req = up.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.x.com/v1/chat/completions")
        body = json.loads(req.data.decode())
        self.assertEqual(body["model"], "m1")
        self.assertEqual(body["messages"][0]["content"], "hi")
        self.assertNotIn("Authorization", req.headers)  # 无 key 不带鉴权头

    def test_full_endpoint_not_double_appended(self):
        c = self._client(base="https://x/v1/chat/completions")
        with mock.patch("laos.llm.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            c.chat([{"role": "user", "content": "x"}])
        self.assertEqual(up.call_args[0][0].full_url,
                         "https://x/v1/chat/completions")

    def test_auth_header_when_key_present(self):
        c = self._client(key="sk-1")
        with mock.patch("laos.llm.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            c.chat([{"role": "user", "content": "x"}])
        self.assertEqual(up.call_args[0][0].headers.get("Authorization"),
                         "Bearer sk-1")

    def test_network_error_raises_llm_error(self):
        c = self._client()
        with mock.patch("laos.llm.urllib.request.urlopen",
                        side_effect=urllib.error.URLError("boom")):
            with self.assertRaises(LLMError):
                c.chat([{"role": "user", "content": "x"}])

    def test_bad_shape_raises_llm_error(self):
        resp = mock.Mock()
        resp.read.return_value = b'{"no_choices": true}'
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        c = self._client()
        with mock.patch("laos.llm.urllib.request.urlopen", return_value=resp):
            with self.assertRaises(LLMError):
                c.chat([{"role": "user", "content": "x"}])

    def test_non_ascii_payload_roundtrip(self):
        seen = {}

        def fake_up(req, timeout=None):
            seen["data"] = req.data
            return _ok_response("中文回复")

        c = self._client()
        with mock.patch("laos.llm.urllib.request.urlopen", side_effect=fake_up):
            out = c.chat([{"role": "user", "content": "用中文问"}])
        self.assertEqual(out, "中文回复")
        self.assertIn("用中文问", json.loads(seen["data"].decode())["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
