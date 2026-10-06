# tests/test_ear_whistle.py
"""drv_ear whistle 通道 —— Cactus Whistle 端侧 ASR（needle 引擎形态）。

    /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_ear_whistle -v

来源：docs/research/2026-10-06-cactus-whistle-adoption.md——小红书笔记
《16.9MB跑完端侧语音识别》复现与接入。实测：en WER 10.8%（SenseVoice 基线
2.7%）、zh 不可用（7 语言无中文）、ttft ~651ms、解码 ~300 tok/s（Windows x86
CPU 原生，needle.exe 1.56MB + whistle.cact 16.9MB）。全部 mock，不依赖引擎
存在；真实数字见 var/asr_eval/results_whistle.json。
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
    return subprocess.CompletedProcess(args=["needle"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


def _engine_env(**extra):
    env = {"LAOS_ASR_CHANNEL": "whistle",
           "LAOS_WHISTLE_BIN": str(REPO / "var/asr_eval/needle/needle.exe"),
           "LAOS_WHISTLE_MODEL": str(REPO / "var/asr_eval/whistle/whistle.cact")}
    env.update(extra)
    return env


class TestWhistleChannel(unittest.TestCase):
    def setUp(self):
        self.wav = REPO / "var" / "asr_eval" / "en_a.wav"
        if not self.wav.exists():
            import wave
            self.wav = REPO / "var" / "asr_eval" / "_tmp_silence.wav"
            self.wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(self.wav), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
                w.writeframes(b"\x00\x00" * 1600)
        os.environ.pop("LAOS_WHISTLE_CMD", None)

    def test_transcribe_whistle_json_output(self):
        out_json = json.dumps({"text": "hello world", "language": "en",
                               "ttft_ms": 457.1, "decode_tps": 307.4})
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run(out_json)):
            out = json.loads(drv_ear.ear_transcribe(str(self.wav), "en"))
        self.assertEqual(out["text"], "hello world")
        self.assertEqual(out["source"], "whistle")
        self.assertEqual(out["ttft_ms"], 457.1)

    def test_default_cmd_passes_model_and_language(self):
        out_json = json.dumps({"text": "hi"})
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run(out_json)) as m:
            drv_ear.ear_transcribe(str(self.wav), "auto")
        cmd = m.call_args[0][0]
        self.assertIn("--model", cmd)
        self.assertIn("--audio-language", cmd)
        self.assertIn("en", cmd)  # auto → en

    def test_zh_rejected_einval(self):
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run") as m:
            with self.assertRaisesRegex(ValueError, "no Chinese"):
                drv_ear.ear_transcribe(str(self.wav), "zh")
        m.assert_not_called()

    def test_engine_missing_enoent(self):
        env = _engine_env(LAOS_WHISTLE_BIN="Z:/nowhere/needle.exe")
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "ENOENT"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_cli_failure_eio(self):
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("", rc=1, stderr="boom")):
            with self.assertRaisesRegex(RuntimeError, "EIO"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_empty_output_eio(self):
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("\n \n")):
            with self.assertRaisesRegex(RuntimeError, "no output"):
                drv_ear.ear_transcribe(str(self.wav), "en")

    def test_plain_text_fallback(self):
        # 引擎若输出纯文本（无 JSON），回退取最后一行
        with mock.patch.dict(os.environ, _engine_env(), clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run("loading\nhello world\n")):
            out = json.loads(drv_ear.ear_transcribe(str(self.wav), "en"))
        self.assertEqual(out["text"], "hello world")

    def test_custom_cmd_template_env(self):
        env = _engine_env(LAOS_WHISTLE_CMD="myengine --audio {wav} --lang {lang}")
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(drv_ear.subprocess, "run",
                               return_value=_fake_run(json.dumps({"text": "ok"}))) as m:
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
        env = _engine_env(LAOS_WHISTLE_BIN="Z:/nowhere/needle.exe")
        with mock.patch.dict(os.environ, {"LAOS_ASR_CHANNEL": "whistle", **env},
                             clear=False), \
             mock.patch.object(drv_ear.shutil, "which", return_value=None):
            os.environ.pop("LAOS_WHISTLE_CMD", None)
            st = drv_ear.ear_status()
        self.assertIn("whistle=unavailable", st)


if __name__ == "__main__":
    unittest.main()
