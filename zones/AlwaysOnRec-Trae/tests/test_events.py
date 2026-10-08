# tests/test_events.py
"""drv_events —— 全天候感知事件驱动（fetch/ingest，mock App 端点）。

    python -m unittest tests.test_events -v
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

EVENTS_JSON = json.dumps({
    "events": [
        {"ts": 1000, "type": "emotion", "emotion": "HAPPY", "confidence": 0.8},
        {"ts": 2000, "type": "emotion", "emotion": "NEUTRAL", "confidence": 0.6},
    ]
})


class TestFetchEvents(unittest.TestCase):
    def setUp(self):
        os.environ["LAOS_NPU_ENDPOINT"] = "http://127.0.0.1:8900"
        if "drv_events" in sys.modules:
            del sys.modules["drv_events"]
        import drv_events
        self.mod = drv_events

    def tearDown(self):
        os.environ.pop("LAOS_NPU_ENDPOINT", None)
        sys.modules.pop("drv_events", None)

    def test_fetch_builds_since_url(self):
        captured = {}

        def fake_urlopen(url, timeout=0):
            captured["url"] = url

            class R:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    pass

                def read(self):
                    return EVENTS_JSON.encode()
            return R()

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            events = self.mod.fetch_events(since_ts=500)
        self.assertEqual(captured["url"], "http://127.0.0.1:8900/events?since=500")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["emotion"], "HAPPY")

    def test_ingest_into_memory(self):
        from laos.memory import MemoryStore
        import tempfile
        td = tempfile.TemporaryDirectory()
        try:
            store = MemoryStore(Path(td.name) / "memory.jsonl")
            events = self.mod.fetch_events.__wrapped__ if False else json.loads(
                EVENTS_JSON)["events"]
            n = self.mod.ingest_events(events, store)
            self.assertEqual(n, 2)
            self.assertEqual(store.stats()["by_kind"].get("sensor"), 2)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
