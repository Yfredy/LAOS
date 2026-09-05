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
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.agent import Agent, run_agents  # noqa: E402
from laos.brain import OpenAIChatBrain, ScriptedBrain  # noqa: E402
from laos.context import ContextManager  # noqa: E402
from laos.kernel import AgentKernel  # noqa: E402

WORKDIR = Path(os.environ.get("LAOS_WORKDIR", REPO / "var"))
DRIVERS = REPO / "drivers"

BAR = "─" * 68


def hr(title: str = "") -> None:
    if title:
        print(f"\n{BAR}\n  {title}\n{BAR}")
    else:
        print(BAR)


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
async def demo(kernel: AgentKernel, use_real: bool, task: str | None) -> None:
    hr("1. 内核启动 / 驱动加载")
    st = kernel.status()
    print(f"  隔离能力   : {st['isolation']}")
    print(f"  驱动数量   : {st['drivers']}")
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

    def new_agent(name: str, caps: list[str], brain) -> Agent:
        ctx = ContextManager(
            system_prompt=system_prompt,
            max_tokens=int(os.environ.get("LAOS_CTX_TOKENS", "2000")),
            swap_dir=WORKDIR / "swap",
        )
        pcb = kernel.spawn(
            name=name,
            caps=caps,
            ctx=ctx,
            branch="exp-A",
            budget=int(os.environ.get("LAOS_BUDGET", "8")),
        )
        agent = Agent(kernel, pcb, brain, max_steps=int(os.environ.get("LAOS_STEPS", "8")))
        print(f"  pid={pcb.pid} name={pcb.name} caps={sorted(pcb.caps.patterns)}")
        print(f"        可见 syscalls: {[t['name'] for t in agent.visible_tools]}")
        return agent

    # ops-agent：权限较全，用来走通主流程；它会去碰 proc.exec，被驱动拦下
    ops = new_agent(
        "ops-agent",
        ["sys.*", "fs.*", "proc.*"],
        OpenAIChatBrain() if use_real else ScriptedBrain(branch="exp-A"),
    )
    # guest-agent：只给了 sys.*，却硬要调 fs.read —— 用来演示内核层的 EPERM
    guest = new_agent(
        "guest-agent",
        ["sys.*"],
        OpenAIChatBrain()
        if use_real
        else ScriptedBrain(
            branch="exp-A",
            deny_probe="fs.read",
            deny_args={"path": "/exp-A/workspace/hosts"},
        ),
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

    if prof is not None:
        probes = prof.stop()
        kernel.audit.write({"t": time.time(), "event": "prof_summary",
                            "backend": prof.reason, "probes": probes})
        print("\n  eBPF: 驱动进程树真实 syscall 分布（top 10，对照上面“声称”的 tool call）:")
        for probe, n in sorted(probes.items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {probe:<44}{n:>10}")

    denied = [r for r in kernel.audit.records if r.get("event") == "syscall" and not r["ok"]]
    if denied:
        print("\n  被拒绝的 syscall（两层防御都命中了）：")
        for r in denied:
            layer = "内核能力表" if r["result"].startswith("EPERM") else "驱动防护"
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
    try:
        asyncio.run(demo(kernel, args.real, args.task))
    finally:
        kernel.shutdown()
        print(f"\n{BAR}\n  laosd 已关闭\n{BAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
