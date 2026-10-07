# tests/test_drv_clef.py
"""drv_clef —— Clef 决策驱动（chroot 后端）离线测试：env 契约 / 命令构造 /
JSON 输出解析 / T1 两硬约束（score 单键 + NaN fail-loud）/ 超时与坏 JSON。

    C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_drv_clef -v

全部 mock subprocess（不触网、不起 wsl）。真实 chroot 实测见
var/clef_eval/results.json（权重窗口彩票分支）。

来源：docs/research/2026-10-07-cloudflare-clef.md §二（schema 语义）；
T1 硬约束（progress.md 裁决）：clef 后端 score 输出必须单键、构造
Decision 前处理 NaN。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from drivers import drv_clef  # noqa: E402
from laos.decide import DecisionSchema, get_backend  # noqa: E402


def _fake_run(stdout: str = "", rc: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(args=["clef"], returncode=rc,
                                       stdout=stdout, stderr=stderr)


def _payload(answer="yes", probabilities=None, **extra):
    body = {"answer": answer,
            "probabilities": probabilities if probabilities is not None
            else {"yes": 0.8, "no": 0.2},
            "latency_ms": 41.5}
    body.update(extra)
    return json.dumps(body)


def _clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("LAOS_CLEF")}
    env.update(extra)
    return env


class TestCommandConstruction(unittest.TestCase):
    """默认 chroot wsl 命令 + LAOS_CLEF_* env 覆盖契约（drv_ear 同款哲学）。"""

    def setUp(self):
        self.schema = DecisionSchema(type="choice",
                                     options=["deploy", "rollback"])
        self.state = {"note": "invoice overdue", "total": 1250}

    def test_default_command_shape(self):
        drv = drv_clef.ClefDriver()
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            cmd = drv.build_command(self.state, self.schema)
        self.assertEqual(cmd[:2], ["wsl", "-d"])
        self.assertEqual(cmd[2], drv_clef.DEFAULT_WSL_DISTRO)
        self.assertEqual(cmd[3:9], ["chroot", "/mnt/armroot", "python3",
                                    "/opt/eval/clef_infer.py", "--model",
                                    "/opt/eval/clef-flash"])
        # --schema/--state 携带可 round-trip 的 JSON（wsl.exe 实测直传不转义）
        self.assertEqual(cmd[-4], "--schema")
        self.assertEqual(json.loads(cmd[-3]),
                         {"type": "choice", "options": ["deploy", "rollback"],
                          "threshold": 0.5})
        self.assertEqual(cmd[-2], "--state")
        self.assertEqual(json.loads(cmd[-1]), self.state)

    def test_distro_env_override(self):
        drv = drv_clef.ClefDriver()
        with mock.patch.dict(os.environ, _clean_env(LAOS_CLEF_DISTRO="Debian"),
                             clear=True):
            cmd = drv.build_command(self.state, self.schema)
        self.assertEqual(cmd[2], "Debian")

    def test_model_env_override_verbatim(self):
        drv = drv_clef.ClefDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_CLEF_MODEL="/data/clef-flash"),
                             clear=True):
            cmd = drv.build_command(self.state, self.schema)
        self.assertEqual(cmd[cmd.index("--model") + 1], "/data/clef-flash")

    def test_json_args_carry_spaces_wsl_contract(self):
        """wsl.exe 实测契约（2026-10-07 本机坑值）：无空格含逗号的 argv
        会被劈开剥括号（{"a":1,"b":2} → "a":1 "b":2）；含空格则整体直传。
        JSON 参数必须带默认分隔符的空格——本测试钉住该构造保证。"""
        drv = drv_clef.ClefDriver()
        state = {"flag": True}
        with mock.patch.dict(os.environ, _clean_env(), clear=True):
            cmd = drv.build_command(state, DecisionSchema(type="noul"))
        schema_arg = cmd[cmd.index("--schema") + 1]
        state_arg = cmd[cmd.index("--state") + 1]
        self.assertIn(": ", schema_arg)          # 非空 dict 必含冒号后空格
        self.assertNotRegex(schema_arg, r",\S")  # 逗号后必跟空格
        self.assertIn(": ", state_arg)
        self.assertNotRegex(state_arg, r",\S")

    def test_custom_cmd_env_replaces_default(self):
        """LAOS_CLEF_CMD 模板整体替换默认命令（{model}/{schema}/{state} 占位）。"""
        drv = drv_clef.ClefDriver()
        template = "myinfer --m {model} --sch {schema} --st {state}"
        with mock.patch.dict(os.environ, _clean_env(LAOS_CLEF_CMD=template),
                             clear=True):
            cmd = drv.build_command(self.state, self.schema)
        self.assertEqual(cmd[0], "myinfer")
        self.assertNotIn("wsl", cmd)
        self.assertEqual(json.loads(cmd[cmd.index("--sch") + 1]),
                         {"type": "choice", "options": ["deploy", "rollback"],
                          "threshold": 0.5})
        self.assertEqual(json.loads(cmd[cmd.index("--st") + 1]), self.state)

    def test_timeout_env_override(self):
        drv = drv_clef.ClefDriver()
        with mock.patch.dict(os.environ,
                             _clean_env(LAOS_CLEF_TIMEOUT="1.5"), clear=True), \
             mock.patch.object(drv_clef.subprocess, "run",
                               return_value=_fake_run(_payload())) as m:
            drv.decide(self.state, self.schema)
        self.assertEqual(m.call_args[1]["timeout"], 1.5)


class TestDecideParsing(unittest.TestCase):
    """子进程单行 JSON（answer/probabilities/latency_ms）→ Decision。"""

    def setUp(self):
        self.drv = drv_clef.ClefDriver()
        os.environ.pop("LAOS_CLEF_CMD", None)

    def _decide(self, payload_str, schema, rc: int = 0, stderr: str = ""):
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(drv_clef.subprocess, "run",
                               return_value=_fake_run(payload_str, rc=rc,
                                                      stderr=stderr)):
            return self.drv.decide({"x": 1}, schema)

    def test_noul_payload(self):
        d = self._decide(_payload("no", {"yes": 0.3, "no": 0.7}),
                         DecisionSchema(type="noul"))
        self.assertEqual(d.answer, "no")
        self.assertEqual(d.probabilities, {"yes": 0.3, "no": 0.7})
        self.assertEqual(d.source, "clef")
        self.assertFalse(d.calibrated)
        self.assertEqual(self.drv.last_latency_ms, 41.5)

    def test_choice_trust_upstream_normalization(self):
        probs = {"deploy": 0.55, "rollback": 0.35, "hold": 0.10}
        d = self._decide(_payload("deploy", probs), self._choice_schema())
        self.assertEqual(d.probabilities, probs)  # 归一化信任上游，不重排

    def _choice_schema(self):
        return DecisionSchema(type="choice",
                              options=["deploy", "rollback", "hold"])

    def test_score_single_key_ok(self):
        d = self._decide(_payload("yes", {"score": 0.7}),
                         DecisionSchema(type="score"))
        self.assertEqual(d.probabilities, {"score": 0.7})  # T1：单键即分数

    def test_score_multikey_rejected(self):
        """T1 硬约束：score 判型多键输出必须拒（多键触发和=1 校验——
        键数约束优先于求和，合法和=1 的多键同样拒）。"""
        with self.assertRaisesRegex(ValueError, "score.*单键|single"):
            self._decide(_payload("yes", {"a": 0.5, "b": 0.5}),
                         DecisionSchema(type="score"))

    def test_nan_rejected_fail_loud(self):
        """T1 硬约束：构造 Decision 前处理 NaN——json.loads 默认接受 NaN
        字面量，驱动必须显式拒绝（fail-loud），不能让 NaN 溜进概率。"""
        raw = '{"answer":"yes","probabilities":{"yes":NaN,"no":NaN},"latency_ms":1}'
        with self.assertRaisesRegex(ValueError, "NaN"):
            self._decide(raw, DecisionSchema(type="noul"))

    def test_out_of_range_surfaces_decision_error(self):
        with self.assertRaises(ValueError):
            self._decide(_payload("yes", {"yes": 1.5, "no": -0.5}),
                         DecisionSchema(type="noul"))

    def test_payload_shape_validated(self):
        for bad in ('{"probabilities": {"yes": 0.5, "no": 0.5}}',  # 缺 answer
                    '{"answer": "yes"}',                            # 缺 probabilities
                    '{"answer": [], "probabilities": {"a": 1.0}}',  # answer 非串
                    '{"answer": "yes", "probabilities": [1, 2]}'):  # probabilities 非 dict
            with self.assertRaises(ValueError, msg=bad):
                self._decide(bad, DecisionSchema(type="noul"))

    def test_json_line_found_among_noise(self):
        # drv_ear 先例：stdout 取最后一行以 "{" 开头的行（前缀噪声容错）
        noisy = "loading model...\n" + _payload("yes") + "\n"
        d = self._decide(noisy, DecisionSchema(type="noul"))
        self.assertEqual(d.answer, "yes")

    def test_bad_json_eio(self):
        with self.assertRaisesRegex(RuntimeError, "EIO.*bad JSON|no JSON"):
            self._decide("totally not json\n", DecisionSchema(type="noul"))
        with self.assertRaisesRegex(RuntimeError, "EIO"):
            self._decide("\n  \n", DecisionSchema(type="noul"))

    def test_rc_nonzero_eio_with_raw_stderr(self):
        # 错误原文必须进异常（BLOCKED 收档时的证据链）
        stderr = ("ImportError: cannot import name "
                  "'Qwen3_5ForConditionalGeneration' from 'transformers'")
        with self.assertRaisesRegex(RuntimeError, "Qwen3_5"):
            self._decide("", DecisionSchema(type="noul"), rc=2, stderr=stderr)

    def test_timeout_etimedout(self):
        env = _clean_env(LAOS_CLEF_TIMEOUT="7")
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(drv_clef.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(
                                   cmd=["wsl"], timeout=7.0)):
            with self.assertRaisesRegex(RuntimeError, "ETIMEDOUT.*7"):
                self.drv.decide({"x": 1}, DecisionSchema(type="noul"))

    def test_calibrated_passthrough(self):
        d = self._decide(_payload("yes", calibrated=True),
                         DecisionSchema(type="noul"))
        self.assertTrue(d.calibrated)  # 上游声明校准过（Brier/RLCD）才置 True


class TestBackendRegistration(unittest.TestCase):
    def test_clef_registered_in_decide(self):
        backend = get_backend("clef")
        self.assertTrue(callable(backend))

    def test_backend_path_returns_decision(self):
        drv = drv_clef.ClefDriver()
        payload = _payload("yes", {"score": 0.9})
        with mock.patch.dict(os.environ, _clean_env(), clear=True), \
             mock.patch.object(drv_clef.subprocess, "run",
                               return_value=_fake_run(payload)):
            d = get_backend("clef")({"score": 0.9},
                                    DecisionSchema(type="score"))
        self.assertEqual(d.answer, "yes")
        self.assertEqual(d.source, "clef")


class TestInferScriptTemplate(unittest.TestCase):
    """/opt/eval/clef_infer.py 模板：可编译 + 契约锚点齐全。"""

    def test_template_compiles(self):
        compile(drv_clef.CLEF_INFER_SCRIPT, "clef_infer.py", "exec")

    def test_template_contract_anchors(self):
        src = drv_clef.CLEF_INFER_SCRIPT
        self.assertIn("--schema", src)
        self.assertIn("--state", src)
        self.assertIn("--model", src)
        self.assertIn("Qwen3_5ForConditionalGeneration", src)  # 官方加载路径
        self.assertIn("softmax", src)                          # logits→概率
        self.assertIn("latency_ms", src)

    def test_write_infer_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = drv_clef.write_infer_script(Path(tmp) / "clef_infer.py")
            self.assertTrue(path.exists())
            compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
