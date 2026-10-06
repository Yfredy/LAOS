# tests/test_ear_whistle.py
"""drv_ear whistle 通道 —— Cactus Whistle 端侧 ASR（16.9MB，7 语言无中文）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_ear_whistle -v

来源：docs/research/2026-10-06-cactus-whistle-adoption.md——小红书笔记
《16.9MB跑完端侧语音识别》复现与接入。全部 mock（subprocess/which/env），
不依赖 cactus 引擎存在；真实引擎效果见 var/asr_eval/results_all.json。
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

from drivers import drv_ear  # noqa: E402


def _fake_run(stdout: str = "", rc: int = 0, stderr: str = ""):
    """构造 subprocess.run 替身（CompletedProcess）。"""
    return subprocess.CompletedProcess(args=["cactus"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


class TestWhistleChannel(unittest.TestCase):
    def setUp(self):
        self.wav = REPO / "var" / "asr_eval" / "en_a.wav"
        if not self.wav.exists():  # 评测集被清理时兜底：现场合成 0.1s 静音 wav
            import wave
            self.wav = REPO / "var" / "asr_eval" / "_tmp_silence.wav"
            self.wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.wav), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(b"\x00\x00" * 1600)

    def test_transcribe_whistle_ok(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        os.environ.pop("LAOS_WHISTLE_CMD", None)
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value="/bin/cactus"), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("loading...\nhello world\n")):
            out = json.loads(drv_ear.ear_transcribe(str(self.wav), "en"))
        self.assertEqual(out["text"], "hello world")  # 取最后一行非空
        self.assertEqual(out["source"], "whistle")
        self.assertEqual(out["language"], "en")
        self.assertIn("latency_ms", out)

    def test_language_auto_maps_to_en(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value="/bin/cactus"), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("hi")) as m:
            drv_ear.ear_transcribe(str(self.wav), "auto")
        self.assertIn("--language", " ".join(m.call_args[0][0]))
        self.assertIn("en", m.call_args[0][0])

    def test_zh_rejected_einval(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value="/bin/cactus"), \
             mock.patch.object(drv_ear.subprocess, "run") as m:
            with self.assertRaisesRegex(ValueError, "no Chinese"):
                drv_ear.ear_transcribe(str(self.wav), "zh")
        m.assert_not_called()

    def test_engine_missing_enoent(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        os.environ.pop("LAOS_WHISTLE_CMD", None)
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "ENOENT"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_cli_failure_eio(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value="/bin/cactus"), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("", rc=1, stderr="boom")):
            with self.assertRaisesRegex(RuntimeError, "EIO"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_empty_output_eio(self):
        env = {"LAOS_ASR_CHANNEL": "whistle"}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value="/bin/cactus"), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("\n \n")):
            with self.assertRaisesRegex(RuntimeError, "no output"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_custom_cmd_template_env(self):
        env = {"LAOS_ASR_CHANNEL": "whistle",
               "LAOS_WHISTLE_CMD": "myengine --audio {wav} --lang {lang}"}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("ok")) as m:
            out = json.loads(drv_ear.ear_transcribe(str(self.wav), "fr"))
        self.assertEqual(out["text"], "ok")
        cmd = m.call_args[0][0]
        self.assertEqual(cmd[0], "myengine")
        self.assertIn("--lang", cmd)

    def test_unknown_channel_still_einval(self):
        with mock.patch.dict(os.environ, {"LAOS_ASR_CHANNEL": "bogus"}, clear=False):
            with self.assertRaisesRegex(ValueError, "EINVAL"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_status_reports_whistle(self):
        with mock.patch.dict(os.environ, {"LAOS_ASR_CHANNEL": "whistle"}, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value=None):
            os.environ.pop("LAOS_WHISTLE_CMD", None)
            st = drv_ear.ear_status()
        self.assertIn("whistle=unavailable", st)


if __name__ == "__main__":
    unittest.main()
