# tests/test_asr.py
"""laos.asr —— 转写客户端（OpenAI 兼容 /audio/transcriptions，纯 stdlib）。

    python -m unittest tests.test_asr -v

零依赖红线：multipart 手拼；urlopen 全程 mock——不打真网络。
"""
from __future__ import annotations

import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.asr import AsrError, TranscribeClient, _multipart  # noqa: E402


def _ok_response(text: str):
    body = json.dumps({"text": text}).encode()
    resp = mock.Mock()
    resp.read.return_value = body
    resp.__enter__ = mock.Mock(return_value=resp)
    resp.__exit__ = mock.Mock(return_value=False)
    return resp


class TestFromEnv(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(TranscribeClient.from_env({}))

    def test_full_env(self):
        c = TranscribeClient.from_env({
            "LAOS_ASR_URL": "https://api.groq.com/openai/v1/",
            "LAOS_ASR_KEY": "gsk_x",
            "LAOS_ASR_MODEL": "whisper-large-v3-turbo"})
        self.assertEqual(c.url, "https://api.groq.com/openai/v1")
        self.assertEqual(c.api_key, "gsk_x")
        self.assertEqual(c.model, "whisper-large-v3-turbo")


class TestMultipart(unittest.TestCase):
    def test_shape_file_and_model_fields(self):
        body = _multipart({"model": "m1"}, "file", "a.wav",
                          "audio/wav", b"RIFFxxxx", "B1")
        s = body.decode("utf-8", errors="replace")
        self.assertIn('--B1\r\nContent-Disposition: form-data; name="model"'
                      '\r\n\r\nm1\r\n', s)
        self.assertIn('name="file"; filename="a.wav"', s)
        self.assertIn("Content-Type: audio/wav", s)
        self.assertTrue(s.endswith("--B1--\r\n"))
        # 音频字节原样在体内
        self.assertIn("RIFFxxxx", s)


class TestTranscribe(unittest.TestCase):
    def _client(self, **kw):
        return TranscribeClient(url=kw.get("url", "https://x/v1"),
                                api_key=kw.get("key", ""),
                                model=kw.get("model", "m1"))

    def test_url_join_and_payload(self):
        c = self._client()
        with mock.patch("laos.asr.urllib.request.urlopen",
                        return_value=_ok_response("你好")) as up:
            out = c.transcribe(b"RIFF..", content_type="audio/wav")
        self.assertEqual(out, "你好")
        req = up.call_args[0][0]
        self.assertEqual(req.full_url, "https://x/v1/audio/transcriptions")
        self.assertIn("boundary=",
                      req.headers["Content-type"])  # urllib 规范化键名
        self.assertIn(b'name="model"', req.data)
        self.assertNotIn("Authorization", req.headers)  # 无 key 不带鉴权

    def test_full_endpoint_not_double_appended(self):
        c = self._client(url="https://x/v1/audio/transcriptions")
        with mock.patch("laos.asr.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            c.transcribe(b"a")
        self.assertEqual(up.call_args[0][0].full_url,
                         "https://x/v1/audio/transcriptions")

    def test_auth_header(self):
        c = self._client(key="sk-1")
        with mock.patch("laos.asr.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            c.transcribe(b"a")
        self.assertEqual(up.call_args[0][0].headers.get("Authorization"),
                         "Bearer sk-1")

    def test_network_error(self):
        c = self._client()
        with mock.patch("laos.asr.urllib.request.urlopen",
                        side_effect=urllib.error.URLError("down")):
            with self.assertRaises(AsrError):
                c.transcribe(b"a")

    def test_bad_shape(self):
        resp = mock.Mock()
        resp.read.return_value = b'{"no_text": 1}'
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        c = self._client()
        with mock.patch("laos.asr.urllib.request.urlopen", return_value=resp):
            with self.assertRaises(AsrError):
                c.transcribe(b"a")

    def test_no_model_field_when_blank(self):
        c = TranscribeClient(url="https://x/v1")  # model 空
        with mock.patch("laos.asr.urllib.request.urlopen",
                        return_value=_ok_response("ok")) as up:
            c.transcribe(b"a")
        self.assertNotIn(b'name="model"', up.call_args[0][0].data)


if __name__ == "__main__":
    unittest.main()
