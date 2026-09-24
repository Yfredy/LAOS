#!/usr/bin/env python3
"""laosd —— Linux AgentOS 的引导器（init）。

职责等价于传统 OS 的 init + udev：
  1. 建工作目录（/var/lib/laos）
  2. insmod 各 MCP 驱动（fs / proc / sys）
  3. 建立 root branch（main）
  4. fork 探索分支 -> 起 Agent 进程 -> commit / abort
  5. 打印运行报告，关闭内核

用法：
    python bin/laosd.py                  # 跑完整 demo（脚本化大脑，无需 API key）
    python bin/laosd.py --real           # 有 OPENAI_API_KEY 时用真 LLM
    python bin/laosd.py --task "..."     # 自定义任务（仅 --real 生效）
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos import judge as jev  # noqa: E402
from laos.agent import Agent, run_agents  # noqa: E402
from laos.brain import OpenAIChatBrain, ScriptedBrain  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.judge import SafeJudge, env_flag  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402
from laos.memory import REMEMBER_JUDGE_QUESTION  # noqa: E402
from laos.skills import SKILL_JUDGE_QUESTION  # noqa: E402

WORKDIR = Path(os.environ.get("LAOS_WORKDIR", REPO / "var"))
DRIVERS = REPO / "drivers"

BAR = "─" * 68


def hr(title: str = "") -> None:
    if title:
        print(f"\n{BAR}\n  {title}\n{BAR}")
    else:
        print(BAR)


# --------------------------------------------------------------------------
# Jev 判断层装配（Task 5）------------------------------------------------
#
# LAOS_JEV_BACKEND=none（默认）时零改动：不构造后端、kernel/memory/context
# /skills 四个消费点保持现状。显式选择 rule/cloud/local 时，构造后端并用
# SafeJudge 包裹（遗留 B：后端每次调用都可能抛 JudgeError——缺 key、网络
# 故障、响应不合契约——kernel 自身有 try/except 兜，但 memory/context/
# skills 路径没有；SafeJudge 把异常 fail-open 成
# JudgeResult("allow", 0.0, {"error": ...})，即回落"无 judge"的既有行为），
# 再按三个独立开关（默认全 0 关）注入三处消费：
#
#     消费点          开关                问句（Task 3 起为 criteria 式两段：
#                                         指示段 + 判据段，题首保留原问句）
#     kernel.judge    LAOS_JEV_AUTOGATE /  PREJUDGE_JUDGE_QUESTION（Task 3；
#                     LAOS_JEV_PREVIEW     deny=拒绝执行终审，高置信 allow 代拍）
#     kernel.memory   LAOS_JEV_MEM         REMEMBER_JUDGE_QUESTION（题首
#                                          "值得长期记住且无隐私风险吗？"，
#                                          deny=不入库；kind=="skill" 的沉淀
#                                          改走 LAOS_JEV_SKILL 的闸，见代理）
#     ContextManager  LAOS_JEV_COMPACT     COMPACT_JUDGE_QUESTION（题首
#                                          "此消息可安全丢弃…吗？"，
#                                          deny=不可丢弃）
#     （技能沉淀）     LAOS_JEV_SKILL       SKILL_JUDGE_QUESTION（题首
#                                          "此任务轨迹确实达成了目标吗？"，
#                                          deny=不沉淀）


class JevGatedMemory:
    """MemoryStore 装配代理：按条目类型把 judge 接到存储边界。

    kernel 的 mem.* syscall 与 agent.py 的 SkillStore 沉淀都经
    kernel.memory.remember 落库，代理在这里拦，两边零改动：

        kind == "skill"  走 skill_judge（LAOS_JEV_SKILL=1），问
                         SKILL_JUDGE_QUESTION——轨迹没达成目标不沉淀
        其余 kind         走 mem_judge（LAOS_JEV_MEM=1），问
                         REMEMBER_JUDGE_QUESTION——不值得记/涉隐私不入库

    deny → 返回 None 不落库（调用方 None-safe：SkillStore 天然吞 None，
    kernel mem.remember 对 None 回 EDENIED 并留审计）；未注入的闸不启用，
    allow（含 SafeJudge fail-open）原样转发。recall/forget/stats 透传。
    """

    def __init__(self, store, mem_judge=None, skill_judge=None):
        self.store = store
        self.mem_judge = mem_judge
        self.skill_judge = skill_judge

    def remember(self, kind, text, tags=None, judge=None):
        kind = str(kind)
        is_skill = kind == "skill"
        gate = self.skill_judge if is_skill else self.mem_judge
        if gate is not None:
            question = (SKILL_JUDGE_QUESTION if is_skill
                        else REMEMBER_JUDGE_QUESTION)
            if gate.noul(str(text), question).verdict == "deny":
                return None
        # 闸归本代理所有：不向内层转发 judge，避免代理闸+内层闸双问
        return self.store.remember(kind, text, tags=tags, judge=None)

    def recall(self, query, k=5):
        return self.store.recall(query, k=k)

    def forget(self, mid):
        return self.store.forget(mid)

    def stats(self):
        return self.store.stats()


def wire_judge(kernel: AgentKernel):
    """按 LAOS_JEV_BACKEND 构造判断层并注入各消费点（Task 5 装配）。

    返回 SafeJudge 包裹后的后端供 ContextManager(judge=) 注入压缩闸；
    BACKEND=none（默认）返回 None 且 kernel 零改动。
    """
    if os.environ.get("LAOS_JEV_BACKEND", "none").strip().lower() == "none":
        return None
    safe = SafeJudge(jev.select())
    kernel.judge = safe  # ① 确认横幅预审（AUTOGATE/PREVIEW 开关在 kernel）
    mem_judge = safe if env_flag("LAOS_JEV_MEM") else None
    skill_judge = safe if env_flag("LAOS_JEV_SKILL") else None
    if mem_judge is not None or skill_judge is not None:
        # ② 入库/沉淀闸：代理在存储边界拦，mem.* 与 SkillStore 零改动
        kernel.memory = JevGatedMemory(kernel.memory, mem_judge=mem_judge,
                                       skill_judge=skill_judge)
    return safe  # ③ 压缩闸由 demo 的 new_agent 按 LAOS_JEV_COMPACT 注入


# --------------------------------------------------------------------------
def boot_kernel(workdir: Path) -> AgentKernel:
    kernel = AgentKernel(workdir)
    env = {
        "PYTHONPATH": str(REPO),
        "PYTHONIOENCODING": "utf-8",
        "LAOS_FS_ROOT": str(workdir / "branches"),
        "LAOS_PRIVACY_MASK": os.environ.get("LAOS_PRIVACY_MASK", "1"),
    }
    py = sys.executable
    kernel.load_driver("fs", [py, str(DRIVERS / "drv_fs.py")], env=env)
    kernel.load_driver("proc", [py, str(DRIVERS / "drv_proc.py")], env=env)
    kernel.load_driver("sys", [py, str(DRIVERS / "drv_sys.py")], env=env)
    kernel.load_driver("npu", [py, str(DRIVERS / "drv_npu.py")], env=env)
    # 语音增强驱动需要 modelscope/torch（仓库外依赖）：仅在音频 venv 存在时加载
    audio_py = REPO / ".venv-audio" / "Scripts" / "python.exe"
    if audio_py.exists():
        kernel.load_driver("audio", [str(audio_py), str(DRIVERS / "drv_audio.py")],
                           env={"LAOS_FS_ROOT": env["LAOS_FS_ROOT"]})
    # 听觉双驱动：drv_ear（双通道 ASR，server 通道零依赖）+ drv_mic（录音，
    # 必须 sounddevice 所在的解释器）。LAOS_EAR_PYTHON 优先，其次本机 conda
    # python，都没有则退回主解释器（此时仅 server 通道 / status 可用）。
    ear_py = os.environ.get("LAOS_EAR_PYTHON") or (
        "C:/Users/yaoyue/miniconda3/python.exe"
        if Path("C:/Users/yaoyue/miniconda3/python.exe").exists() else py)
    kernel.load_driver("ear", [ear_py, str(DRIVERS / "drv_ear.py")], env=env)
    kernel.load_driver("mic", [ear_py, str(DRIVERS / "drv_mic.py")], env=env)
    return kernel


def seed_main_branch(kernel: AgentKernel) -> None:
    main = kernel.branches.create_root("main")
    ws = main.workspace / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "hosts").write_text(
        "127.0.0.1   localhost\n"
        "::1         localhost\n"
        "# managed-by: laosd\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
async def demo(kernel: AgentKernel, use_real: bool, task: str | None,
               jev_judge=None) -> None:
    hr("1. 内核启动 / 驱动加载")
    st = kernel.status()
    print(f"  隔离能力   : {st['isolation']}")
    print(f"  驱动数量   : {st['drivers']}")
    print(f"  Jev 判断层 : {jev_judge.name if jev_judge else '未启用（LAOS_JEV_BACKEND=none）'}")
    print(f"  系统调用表 : {st['syscalls']} 条 -> {', '.join(kernel.syscalls())}")
    for m in kernel.lsmod():
        print(f"    [{m['driver']:>4}] pid={m['pid']:<6} tools={m['tools']}")

    # ---- 分支：fork / explore / commit -----------------------------------
    hr("2. BranchContext: fork -> explore -> commit")
    main = kernel.branches.get("main")
    assert main is not None
    exp_a = main.fork("exp-A")  # 走的通的那条路
    exp_b = main.fork("exp-B")  # 会被 first-commit-wins 作废的兄弟分支
    kernel.branches.register(exp_a)
    kernel.branches.register(exp_b)
    exp_b.explore("workspace/hosts.bak", "stale content", op="write")
    print(main.tree())

    # ---- 起 Agent --------------------------------------------------------
    hr("3. fork Agent 进程（能力受限，并发执行）")
    system_prompt = (
        "你是一个运行在 Linux AgentOS 上的运维 Agent。"
        "只能通过系统调用（MCP tool）操作世界，越权调用会被内核拒绝并返回 errno。"
    )

    def new_agent(name: str, caps: list[str], brain, task_scope=None) -> Agent:
        ctx = ContextManager(
            system_prompt=system_prompt,
            max_tokens=int(os.environ.get("LAOS_CTX_TOKENS", "2000")),
            swap_dir=WORKDIR / "swap",
            # Jev 压缩丢弃预审（LAOS_JEV_COMPACT=1 时启用，其余 None 零改动）
            judge=jev_judge if env_flag("LAOS_JEV_COMPACT") else None,
        )
        pcb = kernel.spawn(
            name=name,
            caps=caps,
            ctx=ctx,
            branch="exp-A",
            budget=int(os.environ.get("LAOS_BUDGET", "16")),
            task_scope=task_scope,
        )
        agent = Agent(kernel, pcb, brain, max_steps=int(os.environ.get("LAOS_STEPS", "8")))
        print(f"  pid={pcb.pid} name={pcb.name} caps={sorted(pcb.caps.patterns)} "
              f"scope={pcb.task_scope}")
        print(f"        可见 syscalls: {[t['name'] for t in agent.visible_tools]}")
        return agent

    # ops-agent：权限较全，用来走通主流程；它会去碰 proc.exec，被驱动拦下
    ops = new_agent(
        "ops-agent",
        ["sys.*", "fs.*", "proc.*", "msg.*", "npu.*", "audio.*",
         "ear.*", "mic.*", "mem.*"],
        OpenAIChatBrain() if use_real else ScriptedBrain(branch="exp-A"),
    )
    # guest-agent：只给了 sys.*，却硬要调 fs.read —— 用来演示内核层的 EPERM；
    # task_scope 把它的任务边界收窄到 /exp-A/（能力随任务意图收窄）
    guest = new_agent(
        "guest-agent",
        ["sys.*", "msg.*"],
        OpenAIChatBrain()
        if use_real
        else ScriptedBrain(
            branch="exp-A",
            deny_probe="fs.read",
            deny_args={"path": "/exp-A/workspace/hosts"},
        ),
        task_scope=["/exp-A/"],
    )
    print(f"  brain={ops.brain.name}")

    # ---- 执行 ------------------------------------------------------------
    hr("4. ReAct 循环（每一次 tool call 都是一次 syscall）")
    t0 = time.perf_counter()
    user_task = task or "确保 hosts 中存在 myapp.local -> 127.0.0.1 的解析记录，并回读验证。"

    # ---- eBPF 语义 profiling（可选，缺席自动降级）-------------------------
    prof = None
    if os.environ.get("LAOS_PROF", "1") != "0":
        from laos.profiling import BpfTraceProfiler
        # 必须是真实驱动 pid（unshare wrapper 的子进程），wrapper 本身是空闲父进程
        driver_pids = [p for p in (m["driver_pid"] for m in kernel.lsmod()) if p]
        if driver_pids:  # bpftrace 不接受空谓词，无驱动 pid 时降级
            prof = BpfTraceProfiler(driver_pids)
            if not prof.start():
                print(f"  [profiler] 未启用: {prof.reason}")
                kernel.audit.write({"t": time.time(), "event": "prof_summary",
                                    "backend": f"unavailable: {prof.reason}", "probes": {}})
                prof = None
        else:
            kernel.audit.write({"t": time.time(), "event": "prof_summary",
                                "backend": "unavailable: no driver pids", "probes": {}})

    results = await run_agents(kernel, [ops, guest], [user_task, user_task])

    name_of = {r.pid: kernel.procs[r.pid].name for r in results}
    for res in results:
        print(f"\n  ── pid={res.pid} {name_of[res.pid]} ──")
        for row in res.trace:
            if "syscall" in row:
                args = ", ".join(f"{k}={v!r}" for k, v in row["args"].items())
                print(f"    step{row['step']}  {row['syscall']}({args})")
                print(f"           -> {row['ret'][:160]}")
            else:
                print(f"    step{row['step']}  [think] {row['say'][:120]}")
        print(f"    结论: {res.answer}")

    # ---- 内核 IPC：信箱 + 运行时能力委托 ----------------------------------
    hr("4.5 内核 IPC：msg.* 与运行时能力委托")
    res = await kernel.syscall(ops.pcb.pid, "msg.send",
                               {"to_pid": guest.pcb.pid, "text": "exp-A 即将提交，请注意 main 变化"})
    print(f"  ops -> guest: {res.text}")
    res = await kernel.syscall(guest.pcb.pid, "msg.recv", {})
    print(f"  guest 收取: {res.text.splitlines()[0]}")
    res = await kernel.syscall(ops.pcb.pid, "sys.delegate",
                               {"to_pid": guest.pcb.pid, "caps_subset": ["fs.read"],
                                "ttl_calls": 1})
    print(f"  ops 委托 fs.read 给 guest: {res.text}")
    res = await kernel.syscall(guest.pcb.pid, "fs.read",
                               {"path": "/main/workspace/hosts"})
    print(f"  guest 经委托读取: {'OK' if res.ok else res.error}")
    res = await kernel.syscall(guest.pcb.pid, "fs.read",
                               {"path": "/main/workspace/hosts"})
    print(f"  guest 二次读取（TTL 已耗尽）: {'OK' if res.ok else res.error}")

    # ---- 端侧 NPU 推理（真实 OS 集成：QNN/ADSP 驱动，见 docs/research §四）--
    hr("4.6 端侧 NPU 推理：npu.* 驱动（风险定价 cost=2）")
    res = await kernel.syscall(ops.pcb.pid, "npu.devices", {})
    for line in res.text.splitlines():
        print(f"  {line}")
    res = await kernel.syscall(ops.pcb.pid, "npu.infer",
                               {"model": "timnet", "input": "audio-feature-26x479"})
    print(f"  ops 推理 → top1: {res.text.splitlines()[-1] if res.ok else res.error}")
    print(f"  风险账本: spent={kernel.risk.spent} remaining={kernel.risk.remaining}")

    # ---- 语音增强（Qwen Audio 开源模型，ModelScope 驱动）------------------
    if "audio" in kernel.drivers:
        hr("4.7 语音增强：audio.* 驱动（Qwen Audio 开源模型）")
        import wave as _wave
        mix = WORKDIR / "demo_mix.wav"
        with _wave.open(str(mix), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            frames = bytearray()
            for i in range(16000):
                v = 0.5 * math.sin(2 * math.pi * 300 * i / 8000) \
                    + 0.5 * math.sin(2 * math.pi * 800 * i / 8000)
                frames += int(v * 26000).to_bytes(2, "little", signed=True)
            w.writeframes(bytes(frames))
        res = await kernel.syscall(ops.pcb.pid, "audio.models", {})
        print(f"  {res.text}")
        res = await kernel.syscall(ops.pcb.pid, "audio.separate", {"wav": str(mix)})
        print(f"  分离: {res.text.splitlines()[0]}")

    # ---- 记忆：mem.* 内建 syscall（个人记忆库，episodic memory）------------
    hr("4.8 记忆：mem.* 内建 syscall（个人记忆库）")
    res = await kernel.syscall(ops.pcb.pid, "mem.remember",
                               {"kind": "fact", "text": "用户偏好中文回复"})
    print(f"  ops 记住: {res.text}")
    res = await kernel.syscall(ops.pcb.pid, "mem.recall", {"query": "偏好"})
    print(f"  ops 回忆: {res.text.splitlines()[0] if res.ok else res.error}")
    res = await kernel.syscall(ops.pcb.pid, "mem.stats", {})
    print(f"  记忆库: {res.text}")

    # ---- 提交 ------------------------------------------------------------
    hr("5. commit（first-commit-wins）")
    print(f"  exp-A 与 main 的差异: {exp_a.diff()}")
    # Stale Context：diff 必须在 commit 前取（提交后两侧一致，diff 变空）；
    # 提交落地后向所有观察过 /main/... 路径的上下文广播失效
    committed_paths = [e["path"] for e in exp_a.diff()]
    applied = exp_a.commit()
    kernel.on_branch_committed("main", committed_paths)
    print(f"  exp-A 提交 {applied} 项变更到 main")
    print(main.tree())
    final = (main.workspace / "workspace" / "hosts").read_text(encoding="utf-8")
    print("  main/workspace/hosts 现在的内容：")
    for line in final.splitlines():
        print(f"    | {line}")

    # ---- 结果 ------------------------------------------------------------
    hr("6. 运行报告")
    for res in results:
        print(f"  {res}  ({name_of[res.pid]})")
    print(f"  耗时     : {time.perf_counter() - t0:.2f}s")
    print(f"  审计记录 : {len(kernel.audit.records)} 条 -> {kernel.audit.path}")
    print(f"  风险账本   : spent={kernel.risk.spent} remaining={kernel.risk.remaining} "
          f"(budget={kernel.risk.budget}, reserve={kernel.risk.reserve})")

    from laos.agentprof import build_spans, score, export_otlp
    spans = build_spans(kernel.audit.records)
    if spans:
        trace_dir = WORKDIR / "traces"
        export_otlp(spans, trace_dir)
        print(f"  语义剖析   : {len(spans)} 个 agent span -> {trace_dir}")
        for sp in spans:
            for flag in score(sp):
                print(f"    [pid={sp.pid} {sp.name}] {flag}")

    # 调度快照：token/err 双预算与挂起状态（可靠性预算耗尽即挂起，见 scheduler.py）。
    # Agent 退出即被 retire 出调度器，故在册视图为空时回退到内核留存的
    # 末次派发视图（kernel.sched_view），保证运行报告里每 pid 一行。
    rows = kernel.scheduler.snapshot() or list(kernel.sched_view.values())
    suspended = [r for r in rows if r["suspended"]]
    print(f"  调度快照   : {len(rows)} agents, {len(suspended)} suspended")
    for r in rows:
        print(f"    pid={r['pid']} err={r['err_used']}/{r['err_budget']} "
              f"tokens={r['token_used']}{'' if not r['suspended'] else f' ({r['reason']})'}")

    if prof is not None:
        probes = prof.stop()
        kernel.audit.write({"t": time.time(), "event": "prof_summary",
                            "backend": prof.reason, "probes": probes})
        print("\n  eBPF: 驱动进程树真实 syscall 分布（top 10，对照上面“声称”的 tool call）:")
        for probe, n in sorted(probes.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {probe:<44}{n:>10}")

    denied = [r for r in kernel.audit.records if r.get("event") == "syscall" and not r["ok"]]
    if denied:
        print("\n  被拒绝的 syscall（多层防御都命中了）：")
        for r in denied:
            if r["result"].startswith("EPERM"):
                layer = "内核能力表"
            elif "outside task scope" in r["result"]:
                layer = "内核 task_scope"
            else:
                layer = "驱动防护"
            print(f"    [{layer}] pid={r['pid']} {r['tool']} -> {r['result']}")

    hr("7. 内核状态")
    for k, v in kernel.status().items():
        print(f"  {k:>14}: {v}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Linux AgentOS 引导器")
    ap.add_argument("--real", action="store_true", help="使用真实 LLM（需 OPENAI_API_KEY）")
    ap.add_argument("--task", type=str, default=None, help="自定义任务（--real 时生效）")
    ap.add_argument("--workdir", type=str, default=str(WORKDIR))
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    workdir = Path(args.workdir)
    kernel = boot_kernel(workdir)
    seed_main_branch(kernel)
    jev_judge = wire_judge(kernel)  # Jev 判断层装配（BACKEND=none 时零改动）
    try:
        asyncio.run(demo(kernel, args.real, args.task, jev_judge))
    finally:
        kernel.shutdown()
        print(f"\n{BAR}\n  laosd 已关闭\n{BAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
