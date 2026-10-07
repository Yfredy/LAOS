#!/usr/bin/env python3
"""drv_clef —— 判断层 Clef 决策后端：chroot 子进程适配（重依赖隔离）。

    decide 层挂点   laos/decide.py register_backend("clef", ...) —— 本模块
                    import 即登记；ClefDriver(state, schema) -> Decision。
    chroot 形态     wsl -d <distro> chroot /mnt/armroot python3
                    /opt/eval/clef_infer.py --model /opt/eval/clef-flash
                    --schema <json> --state <json>
                    （wsl.exe/chroot 两层 argv 直传已实测：JSON 引号不转义）
    输出契约        子进程 stdout 单行 JSON {"answer","probabilities",
                    "latency_ms"[,"calibrated"]}（前缀噪声容错：取最后一行
                    以 "{" 开头的行，drv_ear 先例）。

env 契约（LAOS_CLEF_*，drv_ear 同款哲学：调用时读取，全部可覆盖）：

    LAOS_CLEF_CMD      自定义命令模板整体替换默认（{model}/{schema}/{state}）
    LAOS_CLEF_MODEL    --model 实参覆写（默认 chroot 内路径 /opt/eval/clef-flash）
    LAOS_CLEF_TIMEOUT  子进程超时秒（默认 120.0；模型加载重，评测时调大）
    LAOS_CLEF_DISTRO   WSL 发行版名（默认 Ubuntu-22.04——本机 wsl -l 实测；
                       任务书笔面写 "Ubuntu"，实机无此名，默认取真值）
    LAOS_CLEF_CHROOT   chroot 根（默认 /mnt/armroot）
    LAOS_CLEF_SCRIPT   chroot 内推理脚本路径（默认 /opt/eval/clef_infer.py）

T1 两硬约束（progress.md 裁决，违者返工）：

    1. score 判型输出必须**单键**（多键会触发 Decision 的和=1 校验——
       键数约束优先于求和，和=1 的多键同样拒）；
    2. 构造 Decision 前处理 NaN：json.loads 默认接受 NaN 字面量，
       概率值 math.isnan 即 ValueError fail-loud（不钳制——驱动是装配面，
       NaN 是上游契约破裂，静默钳制等于伪造概率）。

来源诚实纪律：Cloudflare 宣称 Clef-flash 中位 38.8ms 是边缘 GPU 口径；
本地 chroot（qemu-aarch64 CPU）实测数字一律另列，不混写。权重在
HF Cloudflare/clef-flash（Apache 2.0，~18.3GB），断网窗彩票脚本在
var/clef_eval/fetch_weights.py（SHA256+大小校验，fetch_model.sh 先例）；
下载耗尽或架构不兼容（transformers 4.46.3 不认 Qwen3_5）→ BLOCKED
收档：证据原文进 task-3 报告，选型表本地列标"未实测（原因）"。
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laos.decide import Decision, DecisionSchema, register_backend  # noqa: E402

#: 权重彩票落盘处（仓库侧；harness 负责同步进 chroot 的 /opt/eval/clef-flash）
DEFAULT_MODEL_DIR = "var/clef_eval/clef-flash"
#: 本机实际 WSL 发行版（wsl -l 实测为 Ubuntu-22.04；LAOS_CLEF_DISTRO 覆盖）
DEFAULT_WSL_DISTRO = "Ubuntu-22.04"
#: 虚拟端侧评测环境（2026-10-06 建：qemu-aarch64 ubuntu-base 22.04 rootfs）
DEFAULT_CHROOT = "/mnt/armroot"
#: chroot 内推理脚本与模型路径
DEFAULT_SCRIPT = "/opt/eval/clef_infer.py"
DEFAULT_CHROOT_MODEL = "/opt/eval/clef-flash"
#: 子进程超时秒（单次决策含模型加载；评测时 LAOS_CLEF_TIMEOUT 调大）
DEFAULT_TIMEOUT = 120.0


class ClefDriver:
    """clef 决策后端驱动：构造 chroot 命令、跑子进程、解析单行 JSON、
    按 T1 约束构造 Decision。可调用实例（__call__ → decide）。"""

    name = "clef"
    #: 最近一次推理的 latency_ms（评测 harness 取用；None=尚未推理）
    last_latency_ms: float | None = None

    def _timeout(self) -> float:
        raw = os.environ.get("LAOS_CLEF_TIMEOUT")
        if raw is None:
            return DEFAULT_TIMEOUT
        value = float(raw)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"EINVAL: LAOS_CLEF_TIMEOUT 必须为正数，实测 {raw!r}")
        return value

    def build_command(self, state: dict, schema: DecisionSchema) -> list[str]:
        """构造推理命令（env 全部调用时读取，测试可 mock）。

        JSON 参数**必须带空格**（默认分隔符 ", "/": "）——wsl.exe 实测
        契约（2026-10-07 本机）：含空格的 argv 元素会被整体加引号直传；
        无空格但含逗号的元素会被按逗号劈开、剥掉花括号（坑值：
        {"a":1,"b":2} → "a":1 "b":2）。任何非空 dict 经默认分隔符
        必含空格，故此约束由构造保证。
        """
        schema_json = json.dumps(
            {"type": schema.type, "options": schema.options,
             "threshold": schema.threshold},
            ensure_ascii=False, sort_keys=True)
        state_json = json.dumps(state, ensure_ascii=False, sort_keys=True)
        model = os.environ.get("LAOS_CLEF_MODEL", DEFAULT_CHROOT_MODEL)
        template = os.environ.get("LAOS_CLEF_CMD")
        if template:
            # 先 split 后 format：JSON 值里的空格/中文不会被劈开，
            # Windows 路径反斜杠也不受 shlex 转义（drv_ear 先例增强版）
            return [tok.format(model=model, schema=schema_json,
                               state=state_json)
                    for tok in template.split()]
        distro = os.environ.get("LAOS_CLEF_DISTRO", DEFAULT_WSL_DISTRO)
        chroot = os.environ.get("LAOS_CLEF_CHROOT", DEFAULT_CHROOT)
        script = os.environ.get("LAOS_CLEF_SCRIPT", DEFAULT_SCRIPT)
        return ["wsl", "-d", distro, "chroot", chroot, "python3", script,
                "--model", model,
                "--schema", schema_json,
                "--state", state_json]

    def decide(self, state: dict, schema: DecisionSchema) -> Decision:
        """跑一次 chroot 推理 → Decision（fail-loud：超时/坏 JSON/契约破裂
        都是 RuntimeError/ValueError，绝不静默兜底到规则后端）。"""
        cmd = self.build_command(state, schema)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=self._timeout())
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"ETIMEDOUT: clef 推理超时 {self._timeout()}s："
                f"{' '.join(cmd[:6])}…（调 LAOS_CLEF_TIMEOUT）") from exc
        if r.returncode != 0:
            raise RuntimeError(
                f"EIO: clef rc={r.returncode}：{(r.stderr or '').strip()[-600:]}")
        line = next((ln for ln in reversed(r.stdout.splitlines())
                     if ln.strip().startswith("{")), None)
        if line is None:
            raise RuntimeError(
                f"EIO: clef 输出无 JSON 行（bad JSON / 空输出）："
                f"stdout={r.stdout.strip()[:200]!r}")
        return self._to_decision(json.loads(line), schema)

    def _to_decision(self, payload: dict, schema: DecisionSchema) -> Decision:
        """单行 JSON → Decision。T1 两硬约束在此把关（见模块 docstring）。"""
        if not isinstance(payload, dict):
            raise ValueError(f"EINVAL: clef 输出非对象：{payload!r}")
        answer = payload.get("answer")
        probabilities = payload.get("probabilities")
        if not isinstance(answer, str) or not answer:
            raise ValueError(
                f"EINVAL: clef answer 必须是非空字符串：{answer!r}")
        if not isinstance(probabilities, dict) or not probabilities:
            raise ValueError(
                f"EINVAL: clef probabilities 必须是非空 dict：{probabilities!r}")
        for key, value in probabilities.items():  # T1-2：构造前处理 NaN
            if isinstance(value, float) and math.isnan(value):
                raise ValueError(
                    f"ENODATA: clef 概率为 NaN（fail-loud 拒绝构造 Decision，"
                    f"不钳制）：{key}=nan")
        if schema.type == "score" and len(probabilities) != 1:  # T1-1：单键
            raise ValueError(
                f"EINVAL: clef score 判型输出必须单键（T1：多键触发和=1 校验），"
                f"实测 {len(probabilities)} 键：{sorted(probabilities)}")
        # 类属性更新（status() 读类属性；每驱动实例通常单例使用）
        ClefDriver.last_latency_ms = payload.get("latency_ms")
        return Decision(answer, probabilities, self.name,
                        calibrated=bool(payload.get("calibrated", False)))

    def __call__(self, state: dict, schema: DecisionSchema) -> Decision:
        return self.decide(state, schema)


#: chroot 内推理脚本模板（/opt/eval/clef_infer.py 的内容）。
#: 写出：python drivers/drv_clef.py --write-script var/clef_eval/clef_infer.py
#: 官方路径 = Cloudflare 发布的 joint_schema_model（custom-code，Qwen3.5-9B
#: backbone + joint head，每 option 一 logit → softmax）；transformers 无
#: Qwen3_5ForConditionalGeneration 时 fail-loud（BLOCKED 分支的证据锚点）。
CLEF_INFER_SCRIPT = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""clef_infer —— chroot 内 Clef-flash 决策推理（由 drivers/drv_clef.py 模板写出）。

用法：python3 clef_infer.py --model /opt/eval/clef-flash \\
           --schema '{"type":"noul","options":null,"threshold":0.5}' \\
           --state '{"flag": true}' [--repeat 20]

输出：stdout 每次推理一行 JSON
    {"answer","probabilities","latency_ms","load_ms","schema_type","calibrated"}
错误：stderr 原文（traceback 不吞）+ 退出码 3——调用方 drv_clef 以 EIO 呈现，
BLOCKED 收档时错误原文即证据。

映射（laos DecisionSchema → Clef question，joint_schema_model.py 契约）：
    noul   question {type:"noul"} → options ("true","false")
           → {"yes": p_true, "no": p_false}，answer 按 threshold
    choice criteria {选项: 选项} → 选项分布原样透传（归一化信任上游），argmax
    score  criteria = ["0.0","0.1",...,"1.0"] 11 档 → 期望值/10 ∈ [0,1]，
           **单键** {"score": v}（T1 约束：严禁多键）
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback

SCORE_LEVELS = 11  # score 判型档数（0.0–1.0 步进 0.1）


def _fail(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
    sys.exit(3)


def _softmax(values: list[float]) -> list[float]:
    top = max(values)
    exps = [math.exp(v - top) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


def _question_for(schema: dict) -> dict:
    kind = schema["type"]
    if kind == "noul":
        return {"type": "noul"}
    if kind == "choice":
        return {"type": "choice",
                "criteria": {str(o): str(o) for o in schema["options"] or []}}
    levels = [f"{i / (SCORE_LEVELS - 1):.1f}" for i in range(SCORE_LEVELS)]
    return {"type": "score", "criteria": levels}


def _emit(probabilities: dict[str, float], option_ids: list[str],
          schema: dict, latency_ms: float, load_ms: float,
          calibrated: bool) -> str:
    kind = schema["type"]
    threshold = float(schema.get("threshold", 0.5))
    for key, value in probabilities.items():
        if isinstance(value, float) and math.isnan(value):
            _fail(f"ENODATA: NaN probability {key}=nan (fail-loud, T1)")
    if kind == "noul":
        p_yes = probabilities["true"]
        probs = {"yes": p_yes, "no": probabilities["false"]}
        answer = "yes" if p_yes >= threshold else "no"
    elif kind == "choice":
        probs = dict(probabilities)
        answer = max(probs, key=probs.__getitem__)  # 并列取第一（sorted 序）
    else:  # score：11 档期望值 /10 → [0,1]，单键（T1）
        score = sum(int(k) * v for k, v in probabilities.items()) / (SCORE_LEVELS - 1)
        probs = {"score": score}
        answer = "yes" if score >= threshold else "no"
    return json.dumps({"answer": answer, "probabilities": probs,
                       "latency_ms": round(latency_ms, 3),
                       "load_ms": round(load_ms, 1),
                       "schema_type": kind, "calibrated": calibrated},
                      ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clef-flash decision inference")
    parser.add_argument("--model", required=True,
                        help="模型目录（chroot 内路径，含 joint_schema_model.py）")
    parser.add_argument("--schema", required=True, help="DecisionSchema JSON")
    parser.add_argument("--state", required=True, help="state JSON")
    parser.add_argument("--repeat", type=int, default=1,
                        help="推理次数（评测取中位用；默认 1）")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    schema = json.loads(args.schema)
    state = json.loads(args.state)

    # 架构门：官方加载路径需要 transformers 提供 Qwen3_5ForConditionalGeneration
    # （README 实测口径 transformers 5.10.2 / torch 2.11）。本行 ImportError 的
    # traceback 就是"架构不兼容 → BLOCKED"分支的证据原文。
    try:
        from transformers import Qwen3_5ForConditionalGeneration  # noqa: F401,F403
    except Exception:
        traceback.print_exc()
        _fail("arch gate: this transformers cannot import "
              "Qwen3_5ForConditionalGeneration (clef-flash backbone)")

    sys.path.insert(0, args.model)
    try:
        import torch
        from joint_schema_model import (collate_records, encode_record,
                                        load_release_model)
        t0 = time.perf_counter()
        model, processor = load_release_model(args.model, device=args.device)
        load_ms = (time.perf_counter() - t0) * 1000
        record = {"state": state, "questions": {"q": _question_for(schema)}}
        encoded = encode_record(processor.tokenizer, record, max_length=4096)
        batch = collate_records([encoded], processor.tokenizer.pad_token_id,
                                torch.device(args.device))
        option_ids = list(encoded.questions[0].option_ids)
        lines = []
        if args.repeat <= 0:  # 仅加载（qemu 宿主的加载实测口径；不走 decide 路径）
            lines.append(json.dumps({"answer": "", "probabilities": {},
                                      "latency_ms": 0.0, "load_ms": round(load_ms, 1),
                                      "schema_type": schema["type"],
                                      "loaded": True}, ensure_ascii=False))
        with torch.inference_mode():
            for _ in range(max(args.repeat, 0)):
                t1 = time.perf_counter()
                logits = model(batch)[0][0]  # 单 record 单 question → [n_options]
                dt = (time.perf_counter() - t1) * 1000
                probs = dict(zip(option_ids,
                                 logits.float().softmax(-1).tolist()))
                # joint head 经 Brier loss + RLCD 概率校准训练（调研 §二）
                lines.append(_emit(probs, option_ids, schema, dt, load_ms,
                                   calibrated=True))
    except Exception:
        traceback.print_exc()
        _fail("clef official path failed (traceback above is the evidence)")
    print("\\n".join(lines), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def write_infer_script(path: Path | str | None = None) -> Path:
    """把推理脚本模板写到仓库侧（harness 再同步进 chroot /opt/eval/）。"""
    dest = Path(path) if path else Path("var/clef_eval") / "clef_infer.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(CLEF_INFER_SCRIPT, encoding="utf-8", newline="\n")
    return dest


def _clef_backend(state: dict, schema: DecisionSchema) -> Decision:
    """register_backend("clef", ...) 登记的适配器（decide 插拔表挂点）。"""
    return ClefDriver().decide(state, schema)


# import 即登记（laos 核心保持零依赖：不 import 本驱动时 get_backend("clef")
# 仍 KeyError——装配面 fail-loud，与 "rule" 预登记对称）
register_backend("clef", _clef_backend)


def status() -> str:
    """纯本地状态一行（不触网不起 wsl，裸解释器可秒答）。"""
    return (f"backend=clef registered=True "
            f"repo_model_dir={Path(DEFAULT_MODEL_DIR).exists()} "
            f"distro={os.environ.get('LAOS_CLEF_DISTRO', DEFAULT_WSL_DISTRO)} "
            f"chroot_model={os.environ.get('LAOS_CLEF_MODEL', DEFAULT_CHROOT_MODEL)} "
            f"timeout={os.environ.get('LAOS_CLEF_TIMEOUT', DEFAULT_TIMEOUT)} "
            f"last_latency_ms={ClefDriver.last_latency_ms}")


if __name__ == "__main__":
    if "--write-script" in sys.argv:
        target = sys.argv[-1] if len(sys.argv) > 2 and sys.argv[-1] != "--write-script" else None
        print(f"wrote {write_infer_script(target)}")
    else:
        print(status())
