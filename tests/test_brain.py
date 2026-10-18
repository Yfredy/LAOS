# tests/test_brain.py
"""Brain 可靠性与温度阶梯（第一波：brain-reliability-repeat-guard）。

    python -m unittest tests.test_brain -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.brain import OpenAIChatBrain, ScriptedBrain, Thought  # noqa: E402


def _ok_response(content: str = "hi"):
    body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    resp = mock.Mock()
    resp.read.return_value = body
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


class TestThoughtRetryable(unittest.TestCase):
    def test_retryable_defaults_false(self):
        t = Thought(text="x")
        self.assertFalse(t.retryable)
        self.assertEqual(t.tool_calls, [])
        self.assertFalse(t.finish)


class TestThinkTemperature(unittest.TestCase):
    def test_scripted_brain_accepts_temperature(self):
        brain = ScriptedBrain(branch="main")
        thought = brain.think([{"role": "user", "content": "task"}],
                              [{"name": "sys.info"}], temperature=0.7)
        self.assertFalse(thought.retryable)
        self.assertTrue(thought.tool_calls or thought.text)

    def test_openai_payload_includes_temperature(self):
        brain = OpenAIChatBrain(api_key="sk-test",
                                base_url="https://x.test/v1")
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            brain.think([{"role": "user", "content": "hi"}], [], temperature=0.4)
        payload = json.loads(up.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0.4)

    def test_openai_default_temperature_zero(self):
        brain = OpenAIChatBrain(api_key="sk-test",
                                base_url="https://x.test/v1")
        with mock.patch("laos.brain.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            brain.think([{"role": "user", "content": "hi"}], [])
        payload = json.loads(up.call_args[0][0].data)
        self.assertEqual(payload["temperature"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
