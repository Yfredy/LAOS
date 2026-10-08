# tests/test_notify.py
"""drv_notify + drv_comms —— 通知与通信驱动（termux/app 双传输）。

    python -m unittest tests.test_notify -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "drivers"))

NOTIF_JSON = json.dumps([{"key": "n1", "title": "微信", "text": "hi"}])


class _FakeCompleted:
    def __init__(self, out):
        self.stdout = out
        self.returncode = 0


class _FakeResp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def read(self):
        return json.dumps([{"app": "WeChat", "title": "hi"}]).encode()


class TestNotifyTransports(unittest.TestCase):
    """双传输：termux（subprocess）与 app（HTTP /notifications）。"""

    def _load(self, transport):
        import importlib
        import urllib.request
        os.environ["LAOS_NOTIFY_TRANSPORT"] = transport
        os.environ["LAOS_PHONE_ENDPOINT"] = "http://127.0.0.1:8900"
        sys.modules.pop("drv_notify", None)
        mod = importlib.import_module("drv_notify")
        captured = {}

        def fake_run(args, timeout=10):
            captured["args"] = args
            return _FakeCompleted(NOTIF_JSON)

        mod._runner = fake_run
        if transport == "app":
            def fake_urlopen(req, timeout=0):
                captured["url"] = req if isinstance(req, str) else getattr(req, "full_url", str(req))
                return _FakeResp()
            urllib.request.urlopen = fake_urlopen
        return mod, captured

    def test_list_via_termux(self):
        mod, captured = self._load("termux")
        out = json.loads(mod.notify_list())
        self.assertEqual(out[0]["title"], "微信")
        self.assertIn("termux-notification-list", captured["args"][0])

    def test_list_via_app(self):
        mod, captured = self._load("app")
        out = json.loads(mod.notify_list())
        self.assertEqual(out[0]["app"], "WeChat")
        self.assertIn("/notifications", captured.get("url", ""))


class TestComms(unittest.TestCase):
    def test_sms_send_builds_termux_command(self):
        import drv_comms as m
        captured = {}

        def fake_run(args, timeout=15):
            captured["args"] = args

            class R:
                returncode = 0
                stdout = ""
            return R()

        m._runner = fake_run
        out = m.sms_send("10086", "hello")
        self.assertIn("OK", out)
        self.assertIn("10086", captured["args"])
        self.assertIn("hello", captured["args"])

    def test_sms_send_requires_number(self):
        import drv_comms as m
        with self.assertRaises(ValueError):
            m.sms_send("", "hi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
