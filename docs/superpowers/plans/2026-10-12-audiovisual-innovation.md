# 音视频创新波（Audiovisual Innovation Wave）构思与实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有全天候录音（听觉四段漏斗）与 AgentOS 内核治理之上，把「音视频」缺失的**视觉半边**补成同构的第一段漏斗，并把三项已付成本却从未接线的能力（立体声线索 / 听觉预算 / 信息流污点）变为生产功能。

**Architecture:** 三波递进，全部守住「内核侧纯 stdlib + 驱动挂钩 + 零新依赖」姿势。Wave 1 屏幕语义漏斗：轮询既有只读 syscall `screen.dump` → 界面签名（丢弃全部文本内容）→ 稳定段成会话 → `kind="screen"` 记忆 → 日记第七章双模态时间线；**原始 XML 字节零落盘**，比音频「落盘后 TTL 删」更彻底。Wave 2 听觉预算：把 ASR/回放/分离这类烧钱烧时延的听觉输入变成内核可记账资源，超预算走 sentinel 审批。Wave 3 空间方向：`LAOS_MIC_CHANNELS=2` 前置门下，把孤立的 `binaural.py` ILD/IPD 接成每段的「声音从哪来」记忆维度。

**Tech Stack:** Python 3 纯 stdlib（`xml.etree.ElementTree` / `array` / `math` / `json` / `time` / `hashlib`）；零新依赖；测试 unittest（`C:/Users/yaoyue/miniconda3/python.exe`）；驱动侧挂钩不新增第三方库。

**Spec:** 用户指令（2026-10-12）："针对本项目音视频功能，全天候录音 + AgentOS 内核，还能做什么创新"。本文件即 spec：§0 为勘察结论（可复算），§1 为创新候选池与取舍论证，§2 为波次划分，§3 为 Wave 1 可执行计划，§4 为 Wave 2/3 设计级详设。

## Global Constraints

以下约束逐字取自 `AGENTS.md`（唯一纪律来源，本计划不复制其正文、只引用）：

- **定位叙事**：基座是 Linux 内核；Agent 是新负载（与进程同类）；laos 是内核治理在用户态的延伸。禁止"给 AI Agent 装上操作系统"类主客反转表述。本计划四波一律表述为"漏斗/治理语义在新模态链路上的同构延伸"。
- **conda 红线**：只用 `C:/Users/yaoyue/miniconda3/python.exe`，禁止 `pip install` 进该环境；重依赖只进驱动子进程。
- **零依赖承诺**：`laos/` 核心纯 stdlib。本计划新增 `laos/screenlog.py` 等只准 import 标准库 + 既有 laos 模块。
- **隐私红线（本计划最高优先）**：录音只由显式 syscall 触发；`LAOS_REC=0` 全局禁录；ASR 全本地。**新增视觉红线**：屏幕 dump 的 `text`/`resource-id` 可能是聊天内容/验证码/账号，一律当场丢弃、不进记忆、不进审计、不进日志；视觉链路**不新增任何"隐式采集"**——`screen.dump` 是既有只读 syscall，本波只做"轮询频率由用户显式开启"（`LAOS_SCREENLOG=1`），默认关。
- **目录纪律**：不新建顶层目录。新文件只落在既有位置：`laos/`（核心）、`bin/`（CLI）、`tests/`、`docs/`。
- **测试口径**：README 写实跑数（`unittest discover` 的 "Ran N tests"），不是静态 `def test_` 计数。
- **来源诚实**：评测数字一律实测；本计划 §0 的每个事实都附产出命令。
- **计划编写纪律**：跨 Task 引用一律原文重复（禁"类似 Task N"）；状态登记同步进 `docs/superpowers/plans/README.md`。
- **提交**：conventional commits；每 Task 一 commit；master 分支。
- **发版纪律**：本波若发版，走 `python scripts/release.py --apply`（不绿拒绝）→ CHANGELOG 人工插段 → release commit → annotated tag → push → `python scripts/gen_release_notes.py` 对齐归档。
- **全量测试命令（每条 Step 复用，勿改写）**：
  ```bash
  cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
  ```

---

## §0 勘察结论（先看清棋盘，再谈创新）

> 每条结论附产出命令，可复算。**结论 1-3 是本计划的存在理由。**

| # | 结论 | 证据 / 产出命令 |
|---|---|---|
| 1 | **视觉栈为零**：「音视频」的「视」半边完全空白 | `grep -rl "opencv\|cv2\|pillow\|PIL\|vision\|camera\|ffmpeg" laos/ drivers/ bin/` → 空。`ls laos/*.py \| wc -l` = 51（含 `__init__.py`，与 README 数据面板「51 个核心模块」一致），无一涉视觉 |
| 2 | **`screen.shot` 截屏无人消费、未注册**：截了图但没有代码读它 | `grep -rn "var/screen\|screen.shot" laos/ drivers/ bin/ --include=*.py \| grep -v drv_screen.py` → 空；`grep -rn "screen.shot" bin/laosweb.py laos/kernel.py` → 空 |
| 3 | **空间音频三件是孤立件**：实现了、有测试、从未接线 | `laos/binaural.py`（`goertzel`/`ild_db`/`ipd_rad`/`binaural_features`）、`laos/foa.py`（`plane_wave`/`decode_quad`/`acn_index`）、`laos/micgeom.py`；`grep -rn "binaural\|import foa\|micgeom" laos/ drivers/ bin/` 除自身外 → 空，只有 `tests/test_{binaural,foa,micgeom}.py` 引用 |
| 4 | 采集链路是**单声道**，空间方向有硬件前置 | `drivers/drv_mic.py:51` `CHANNELS = 1`；`binaural_features(left, right, sr)` 要双通道 → Wave 3 必须带 `LAOS_MIC_CHANNELS=2` 显式门 |
| 5 | `drv_audio.py` 已有模型侧分离（`audio.separate` FLASepformer / `audio.aec`），走 .venv-audio 子进程 | `grep -oE "audio\.[a-z_]+" drivers/drv_audio.py` → `audio.aec`/`audio.models`/`audio.separate` |
| 6 | 控件树解析已具备且纯 stdlib | `drivers/screen_adb.py:69` `parse_uiautomator_xml(xml) -> {"package","nodes"}`，节点字段 `text/cls/package/resource_id/clickable/bounds[l,t,r,b]`；`drivers/drv_screen.py:47` `_dump(adb) -> dict`；`screen.dump` 是**只读** syscall |
| 7 | 内核内建 syscall 现有面 | `grep -oE '"[a-z]+\.[a-z_]+"' laos/kernel.py` → `audit.jsonl`/`ear.transcribe`/`evolve.run`/`fs.*`/`mem.*`/`mic.replay`/`msg.*`/`rec.replay`/`sys.delegate`（无听觉预算、无屏幕类） |
| 8 | 治理件可复用 | `laos/risk.py:30` `class FleetLedger`（预算记账先例）；`laos/confgate.py` 置信度三段闸；`laos/sentinel.py` 进程级 taint + scoped grants |
| 9 | 记忆与日记接口 | `laos/memory.py:124` `remember(kind, text, tags=None, judge=None, origin="agent", origin_pid=None)`；`bin/diary.py:197` `build_diary(date, audit_records, memory_store, brain=None) -> dict`；`SECTION_TITLES` 在 `bin/diary.py:43`（当前 6 章） |
| 10 | 语料与调研**无语视覆盖** | `query_corpus.py --help` 主题仅 `{agent-os, audio-speech, spatial-privacy}`；`docs/research/` 42 份无视觉/多模态方向 |
| 11 | 已有待执行计划占坑情况（**不得重复**） | `docs/superpowers/plans/2026-10-12-auditory-governance-wave.md` 已占 A 说话人分离/B 听觉缺页召回/C 声景调度/D 即焚回执；`2026-10-09-evolve-followups.md` 占 sentinel/rotate/e2e |

---

## §1 创新候选池（7 个方向，含取舍论证）

> 分级判据：**创新性**（是否别处没有）× **可行性**（零依赖/无硬件前置/红线相容）× **不重复**（与 §0.11 占坑错开）。S=本波就做，A=下一波，B=远期或明确不推荐。

### S1 · 屏幕语义漏斗（零模型视觉第一段）——**Wave 1 主体**

- **创新点**：把四段漏斗从听觉同构复制到视觉，且**不引入任何视觉模型**。更关键的是即焚方式比音频更彻底——音频必须落盘才能送 ASR，视觉的控件树在内存里就能蒸馏完，**XML 字节零落盘**。
- **地基**：§0.6 控件树解析已在；`screen.dump` 只读 syscall 已在；缺的只是"蒸馏成记忆"这一层。
- **回答的新问题**：音频日记只能答"你说了什么"，答不了"你当时在干什么"。双模态时间线能答"下午 3 点我在用什么 App 时说了什么"。
- **红线相容**：默认关（`LAOS_SCREENLOG=1` 显式开）；text/resource_id 当场丢弃；无隐式采集。
- **前置**：无（adb 设备在不在由 dump_fn 失败跳过处理，见 Task 2）。

### S2 · 双模态时间线（日记第七章）——**Wave 1 Task 4**

- **创新点**：`kind="screen"` 会话与 `kind="journal"` 音频记忆按时间窗交叉渲染，产出"屏幕在做什么 × 耳朵在听到什么"的当日横截面。这是记忆层第一次跨模态。
- **地基**：`build_diary` 已收 `memory_store`，直接 `recall` 两类记忆即可，无需新存储。

### A1 · 听觉预算（ear budget）——**Wave 2**

- **创新点**：把"听"变成内核可记账资源。ASR/回放/说话人分离都烧钱烧时延，但现无任何上限——agent 可以无限触发。用 `FleetLedger` 同构记账，超预算即被 sentinel 拦下要人工审批。这是 K4 不可逆预算从"写操作"扩展到"感知操作"。
- **风险**：中（改内核热路径，需默认关闭 + 阈值可配）。

### A2 · 听觉 taint（信息流级污点）——**Wave 2**

- **创新点**：`sentinel` 的 taint 现在是**进程级**（agent 碰过敏感操作即永久污点）。本方向细化到**信息流级**：agent 处理过含红线词（支付/密码）的段落后，其后续 `mem.remember` 被红线规则拦截。把"支付/密码永不记忆"从被动字符串匹配升级为主动传播跟踪。
- **风险**：中（需与 confgate/evroute 明确职责边界，防重复拦截）。

### B1 · 空间方向记忆（立体声门下）——**Wave 3，硬件前置**

- **创新点**：把 §0.3 三件孤立件接进生产：`LAOS_MIC_CHANNELS=2` 时每段记一个声源方向标签（L/C/R），journal 文本从 `[HH:MM] text` 升级为 `[HH:MM][L] text`，diary 聚合「今天声音主要从哪来」。
- **诚实的前置**：§0.4 采集是单声道，`CHANNELS=1`。**不改成 2 就不能用**，且多数 Windows 笔记本是双麦阵列（可行但需实测）。因此排 Wave 3 且必须显式门控，默认保持单声道字节兼容。
- **与待执行波 A 的关系**：A（speaker）答"几个人"，B1 答"几个方向/从哪来"，正交可叠加。

### B2 · FOA 多声源方向数估计——远期，不本波

- `laos/foa.py` 的 `plane_wave`/`decode_quad` 是编解码地基，方向数估计需要真实多通道阵列数据，本机无。**列入远期，不占本波 Task**。

### X · 明确不推荐（记录否决理由，防后人重提）

| 方向 | 否决理由 |
|---|---|
| 视觉常驻事件检测（摄像头/帧差 + 事件模型） | AED 调研已裁定"暂不引入常驻 AED"；视频敏感度高于音频，常驻采集与即焚哲学冲突；且需视觉模型，破零依赖 |
| 跨会话声纹身份（"同一人=日记主人"） | 说话人分离调研 §2 明确列为 open problem；PIPL 下声纹是敏感个人信息，需单独同意——与"默认开"互斥 |
| 唇读（lip-read）辅助 ASR | 需视觉模型 + 摄像头常开，双重破线；且 ASR 已全本地够用 |
| 把截屏 PNG 喂多模态大模型 | 截图含验证码/聊天内容，出网即破隐私红线；且违反"ASR 全本地"的同源纪律 |

---

## §2 波次划分

| 波次 | 内容 | Task 数 | 硬件前置 | 红线风险 | 建议时机 |
|---|---|---|---|---|---|
| **Wave 1** | S1 屏幕语义漏斗 + S2 双模态日记 | 5 | 无 | 低（默认关 + 零落盘） | **立即** |
| Wave 2 | A1 听觉预算 + A2 听觉 taint | 4-6 | 无 | 中（内核热路径） | Wave 1 发版后 |
| Wave 3 | B1 空间方向记忆 | 3-4 | **需双麦实测** | 低 | 有立体声设备时 |

**Scope Check（writing-plans 纪律）**：本文件是构思+路线图（spec）。Wave 1 已展开为可执行计划（§3）；**Wave 2/3 是独立子系统，届时各自拆成单独计划文件**，不在本文件内展开步骤——本文件只给到接口级（§4）。

---

## §3 Wave 1 实施计划：屏幕语义漏斗（零模型视觉第一段）

### Task 1: 界面签名纯函数（laos/screenlog.py）

**Files:**
- Create: `laos/screenlog.py`
- Test: `tests/test_screenlog.py`

**Interfaces:**
- Consumes: `drivers/screen_adb.parse_uiautomator_xml` 产出的 dict 形状（本 Task 不 import 驱动，只按 `{"package": str, "nodes": [{"text","cls","package","resource_id","clickable","bounds"}]}` 契约消费——保持 `laos/` 核心不依赖 `drivers/`）。
- Produces:
  - `screen_signature(dump: dict) -> dict` —— 返回 `{"package": str, "nodes": int, "clickable": int, "classes": dict[str,int], "ink": int}`；**不含 text/resource_id/bounds**。
  - `signature_distance(a: dict, b: dict) -> float` —— 不同 package → `1.0`；否则类直方图 L1 归一化 ×0.7 + 节点数相对差 ×0.3，四舍五入 4 位。
  - `segment_sessions(samples: list[tuple[float, dict]], *, threshold: float = 0.35, min_samples: int = 4, max_gap_s: float = 60.0) -> list[dict]` —— 返回 `[{"start": float, "end": float, "package": str, "anchor": dict, "samples": int}]`；不足 `min_samples` 的段丢弃；幸存段中相邻且同 `package`、间隔 ≤ `max_gap_s` 的缝回一段。
  - `merge_adjacent(sessions: list[dict], *, max_gap_s: float = 60.0) -> list[dict]` —— 同 package 相邻段按间隔缝合（防单样本抖动劈断会话）；`max_gap_s=0.0` 时不缝。
  - `render_session(sess: dict) -> str` —— 形如 `[14:00-14:07] com.tencent.mm · 12节点/3可点/2类 · 7样本`。
  - `to_memory_rows(sessions: list[dict], *, kind: str = "screen") -> list[dict]` —— `[{"kind": kind, "text": render_session(s)}]`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_screenlog.py`：

```python
"""screenlog —— 屏幕界面签名与会话切分（纯 stdlib，零视觉模型）。

    python -m unittest tests.test_screenlog -v
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from laos.screenlog import (render_session, screen_signature,  # noqa: E402
                            segment_sessions, signature_distance,
                            to_memory_rows)


def _dump(package: str = "com.tencent.mm", n_nodes: int = 8,
          n_clickable: int = 2) -> dict:
    """造一个与 parse_uiautomator_xml 同构的 dump（含敏感 text/id）。"""
    nodes = []
    for i in range(n_nodes):
        nodes.append({
            "text": f"敏感聊天内容{i}",
            "cls": "android.widget.TextView" if i % 2 else "android.widget.ImageView",
            "package": package,
            "resource_id": f"com.tencent.mm:id/secret_{i}",
            "clickable": i < n_clickable,
            "bounds": [0, i * 10, 100, i * 10 + 8],
        })
    return {"package": package, "nodes": nodes}


class TestScreenSignature(unittest.TestCase):
    def test_signature_drops_sensitive_fields(self):
        # 隐私硬断言：text / resource_id / bounds 一律不进签名
        sig = screen_signature(_dump())
        blob = json.dumps(sig, ensure_ascii=False)
        self.assertNotIn("敏感聊天内容", blob)
        self.assertNotIn("secret_", blob)
        self.assertNotIn("bounds", blob)

    def test_signature_counts(self):
        sig = screen_signature(_dump(n_nodes=8, n_clickable=2))
        self.assertEqual(sig["package"], "com.tencent.mm")
        self.assertEqual(sig["nodes"], 8)
        self.assertEqual(sig["clickable"], 2)
        self.assertEqual(len(sig["classes"]), 2)      # TextView / ImageView
        self.assertEqual(sig["classes"]["TextView"], 4)
        self.assertGreater(sig["ink"], 0)

    def test_empty_dump_is_safe(self):
        sig = screen_signature({"package": "", "nodes": []})
        self.assertEqual(sig["nodes"], 0)
        self.assertEqual(sig["classes"], {})
        self.assertEqual(sig["ink"], 0)


class TestSignatureDistance(unittest.TestCase):
    def test_different_package_is_max(self):
        a = screen_signature(_dump("com.tencent.mm"))
        b = screen_signature(_dump("com.android.settings"))
        self.assertEqual(signature_distance(a, b), 1.0)

    def test_same_source_is_zero(self):
        a = screen_signature(_dump())
        self.assertEqual(signature_distance(a, dict(a)), 0.0)

    def test_node_count_change_is_partial(self):
        a = screen_signature(_dump(n_nodes=8))
        b = screen_signature(_dump(n_nodes=20))
        d = signature_distance(a, b)
        self.assertGreater(d, 0.0)
        self.assertLess(d, 1.0)


class TestSegmentSessions(unittest.TestCase):
    def _samples(self, pkgs, step=5.0, t0=1000.0):
        return [(t0 + i * step, screen_signature(_dump(p)))
                for i, p in enumerate(pkgs)]

    def test_stable_run_becomes_one_session(self):
        s = segment_sessions(self._samples(["a"] * 6))
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["samples"], 6)
        self.assertEqual(s[0]["package"], "a")

    def test_package_switch_splits(self):
        s = segment_sessions(self._samples(["a"] * 4 + ["b"] * 4))
        self.assertEqual(len(s), 2)
        self.assertEqual([x["package"] for x in s], ["a", "b"])

    def test_short_blip_merged_not_split(self):
        # 4+1+4：中间 1 样本的抖动段不足 min_samples 被丢弃，且不得把
        # 两侧同 App 段劈开——缝回 1 段 8 样本（interval=5s 的通知横幅场景）
        s = segment_sessions(self._samples(["a"] * 4 + ["b"] + ["a"] * 4))
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0]["package"], "a")
        self.assertEqual(s[0]["samples"], 8)

    def test_long_gap_not_merged(self):
        # 离开又回来（间隔 985s > max_gap_s 默认 60s）确实是新会话，不缝
        samples: list[tuple[float, dict]] = []
        t = 0.0
        for pkg, n in (("a", 4), ("b", 4), ("a", 4)):
            for _ in range(n):
                samples.append((t, screen_signature(_dump(pkg))))
                t += 5.0
            t += 985.0
        s = segment_sessions(samples)
        self.assertEqual([x["package"] for x in s], ["a", "b", "a"])
        self.assertEqual([x["samples"] for x in s], [4, 4, 4])

    def test_max_gap_zero_disables_merge(self):
        s = segment_sessions(self._samples(["a"] * 4 + ["b"] + ["a"] * 4),
                             max_gap_s=0.0)
        self.assertEqual(len(s), 2)
        self.assertEqual([x["samples"] for x in s], [4, 4])

    def test_min_samples_boundary(self):
        s = segment_sessions(self._samples(["a"] * 4))
        self.assertEqual(len(s), 1)                  # == min_samples 保留
        s2 = segment_sessions(self._samples(["a"] * 3))
        self.assertEqual(len(s2), 0)                 # < min_samples 丢弃

    def test_render_and_rows(self):
        s = segment_sessions(self._samples(["com.tencent.mm"] * 7))[0]
        text = render_session(s)
        self.assertIn("com.tencent.mm", text)
        self.assertIn("节点", text)
        rows = to_memory_rows([s])
        self.assertEqual(rows[0]["kind"], "screen")
        self.assertEqual(rows[0]["text"], text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laos.screenlog'`

- [ ] **Step 3: 写最小实现**

创建 `laos/screenlog.py`：

```python
"""screenlog —— 屏幕界面语义蒸馏（纯 stdlib，零视觉模型）。

四段漏斗的视觉同构第一段：`drivers/screen_adb.parse_uiautomator_xml` 已能
把 `screen.dump` 的控件树解析成 dict（纯 stdlib ET），但 dump 产物从未被
蒸馏成记忆——本项目「音视频」的「视」半边是空白（实测 `ls laos/*.py | wc -l` = 51
一涉视觉；`screen.shot` 截屏无人消费、未在内核/laosweb 注册）。

与听觉漏斗逐段同构，但即焚更彻底：
    常驻检测  按间隔轮询 screen.dump（既有只读 syscall，已被内核审计）
    触发捕获  界面签名连续稳定才成「会话」（防抖动，过渡态不成记忆）
    即时蒸馏  签名只留形状统计量；text / resource_id 当场丢弃
    原物即焚  **XML 字节零落盘**——音频必须落盘才能送 ASR，视觉不必

隐私设计（比音频更严）：控件树 text 可能是聊天内容/验证码/账号，故签名只含
package / 节点数 / 可点击数 / 类直方图 / 墨水面积；text、resource_id、bounds
一律不进记忆、不进审计、不进日志（连文本长度都不统计——长度也是侧信道）。
本模块不 import drivers/：按 dict 契约消费，保持 laos/ 核心零驱动依赖。
"""

from __future__ import annotations

import time


def screen_signature(dump: dict) -> dict:
    """控件树 dump → 界面签名（丢弃全部内容字段，只留形状）。"""
    nodes = dump.get("nodes") or []
    classes: dict[str, int] = {}
    clickable = 0
    ink = 0
    for n in nodes:
        cls = (n.get("cls") or "").rsplit(".", 1)[-1] or "Unknown"
        classes[cls] = classes.get(cls, 0) + 1
        if n.get("clickable"):
            clickable += 1
        l, t, r, b = n.get("bounds") or [0, 0, 0, 0]
        ink += max(0, r - l) * max(0, b - t)
    return {"package": dump.get("package") or "", "nodes": len(nodes),
            "clickable": clickable, "classes": classes, "ink": int(ink)}


def signature_distance(a: dict, b: dict) -> float:
    """0.0=同一界面，1.0=不同 App。类直方图 L1 归一化 + 节点数相对差。"""
    if (a.get("package") or "") != (b.get("package") or ""):
        return 1.0
    ca, cb = a.get("classes") or {}, b.get("classes") or {}
    l1 = sum(abs(ca.get(k, 0) - cb.get(k, 0)) for k in set(ca) | set(cb))
    denom = max(1, sum(ca.values()) + sum(cb.values()))
    hist = l1 / denom
    na, nb = float(a.get("nodes", 0)), float(b.get("nodes", 0))
    cnt = abs(na - nb) / max(1.0, max(na, nb))
    return round(0.7 * hist + 0.3 * cnt, 4)


def merge_adjacent(sessions: list[dict], *,
                   max_gap_s: float = 60.0) -> list[dict]:
    """合并相邻且同 package 的会话（间隔 <= max_gap_s）。

    动机：interval=5s 时，一条 5 秒的通知横幅/下拉栏会造成单样本抖动段，
    该段本身不足 min_samples 被丢弃——但它的存在会把一段连续会话**劈成两
    段**（锚点被切换）。这里把"同 App 且间隔很短"的相邻段缝回去。
    长间隔（离开又回来）不缝：那确实是新会话。
    """
    out: list[dict] = []
    for s in sessions:
        if out and out[-1]["package"] == s["package"] \
                and (s["start"] - out[-1]["end"]) <= max_gap_s:
            out[-1]["end"] = s["end"]
            out[-1]["samples"] += s["samples"]
        else:
            out.append(dict(s))
    return out


def segment_sessions(samples: list[tuple[float, dict]], *,
                     threshold: float = 0.35, min_samples: int = 4,
                     max_gap_s: float = 60.0) -> list[dict]:
    """等间隔 (ts, signature) 样本 → 界面会话列表。

    新会话起点 = 与当前会话锚点（该段首个样本）距离 > threshold。
    不足 min_samples 的段视为抖动/过渡态，不成记忆；幸存段中相邻且同
    package、间隔 <= max_gap_s 的会被缝回一段（防单样本抖动劈断会话）。
    """
    sessions: list[dict] = []
    cur: dict | None = None
    for ts, sig in samples:
        if cur is None or signature_distance(sig, cur["anchor"]) > threshold:
            cur = {"start": ts, "end": ts, "package": sig.get("package", ""),
                   "anchor": sig, "samples": 1}
            sessions.append(cur)
        else:
            cur["end"] = ts
            cur["samples"] += 1
    kept = [s for s in sessions if s["samples"] >= min_samples]
    return merge_adjacent(kept, max_gap_s=max_gap_s)


def _hm(ts: float) -> str:
    return time.strftime("%H:%M", time.localtime(ts))


def render_session(sess: dict) -> str:
    """会话 → 记忆文本行（只含形状，无任何内容）。"""
    a = sess["anchor"]
    return (f"[{_hm(sess['start'])}-{_hm(sess['end'])}] "
            f"{a.get('package', '')} · {a.get('nodes', 0)}节点/"
            f"{a.get('clickable', 0)}可点/{len(a.get('classes') or {})}类 · "
            f"{sess['samples']}样本")


def to_memory_rows(sessions: list[dict], *, kind: str = "screen") -> list[dict]:
    return [{"kind": kind, "text": render_session(s)} for s in sessions]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: PASS（13 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/screenlog.py tests/test_screenlog.py
git commit -m "feat(screenlog): 界面签名与会话切分纯函数（丢弃text/id，零视觉模型）——S1-T1"
```

### Task 2: 轮询采集（collect_samples + collect_sessions）

**Files:**
- Modify: `laos/screenlog.py`（追加两个函数，不动 Task 1 已交付签名）
- Test: `tests/test_screenlog.py`（追加 `TestCollect` 类，勿删既有）

**Interfaces:**
- Consumes: Task 1 的 `screen_signature`/`segment_sessions`。
- Produces:
  - `collect_samples(dump_fn: Callable[[], dict], *, seconds: float = 300.0, interval: float = 5.0, now: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep) -> list[tuple[float, dict]]` —— 轮询 `n = max(1, int(seconds/interval))` 次；首次立即采；`dump_fn` 抛异常该次跳过（无设备/解析失败不中断整轮）；返回 `(ts, signature)` 列表。
  - `collect_sessions(dump_fn, *, seconds: float = 300.0, interval: float = 5.0, threshold: float = 0.35, min_samples: int = 4, now=None, sleep=None) -> list[dict]` —— `segment_sessions(collect_samples(...), threshold=..., min_samples=...)`。

- [ ] **Step 1: 写失败测试（追加到 tests/test_screenlog.py 末尾的 import 之后）**

```python
from laos.screenlog import collect_samples, collect_sessions  # noqa: E402


class _FakeClock:
    def __init__(self, t0: float = 1000.0):
        self.t = t0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s


class TestCollect(unittest.TestCase):
    def test_sample_count_and_no_sleep_before_first(self):
        clk = _FakeClock()
        got = collect_samples(lambda: _dump(), seconds=25.0, interval=5.0,
                              now=clk.now, sleep=clk.sleep)
        self.assertEqual(len(got), 5)
        self.assertEqual(clk.slept, [5.0, 5.0, 5.0, 5.0])   # 首采不前置睡
        self.assertIsInstance(got[0][1], dict)

    def test_dump_failure_is_skipped_not_fatal(self):
        clk = _FakeClock()
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("EINVAL: no device")
            return _dump()

        got = collect_samples(flaky, seconds=20.0, interval=5.0,
                              now=clk.now, sleep=clk.sleep)
        self.assertEqual(len(got), 3)          # 4 次尝试，1 次失败被跳过

    def test_collect_sessions_end_to_end(self):
        clk = _FakeClock()
        seq = ["com.tencent.mm"] * 5 + ["com.android.settings"] * 5
        it = iter(seq)

        def fn():
            return _dump(next(it))

        sess = collect_sessions(fn, seconds=50.0, interval=5.0,
                                now=clk.now, sleep=clk.sleep)
        self.assertEqual([s["package"] for s in sess],
                         ["com.tencent.mm", "com.android.settings"])
        self.assertEqual(sess[0]["samples"], 5)

    def test_collect_sessions_empty_when_all_fail(self):
        clk = _FakeClock()

        def boom():
            raise OSError("adb not found")

        self.assertEqual(collect_sessions(boom, seconds=20.0, interval=5.0,
                                          now=clk.now, sleep=clk.sleep), [])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: FAIL — `ImportError: cannot import name 'collect_samples'`

- [ ] **Step 3: 写最小实现（追加到 laos/screenlog.py 末尾）**

```python
from typing import Callable  # noqa: E402  （追加到文件顶部 from __future__ 之后）


def collect_samples(dump_fn: Callable[[], dict], *,
                    seconds: float = 300.0, interval: float = 5.0,
                    now: Callable[[], float] = time.time,
                    sleep: Callable[[float], None] = time.sleep
                    ) -> list[tuple[float, dict]]:
    """轮询 dump_fn() 采 (ts, signature)；XML 字节在本函数内即弃，不落盘。

    dump_fn 返回 parse_uiautomator_xml 同构 dict。首次采样立即执行（不前置
    sleep）；dump_fn 抛异常（无设备/解析失败）该次跳过——单次失败不废整轮，
    否则临时拔线会让 5 分钟采集整体作废。
    """
    n = max(1, int(seconds / interval))
    out: list[tuple[float, dict]] = []
    for i in range(n):
        if i:
            sleep(interval)
        try:
            out.append((now(), screen_signature(dump_fn())))
        except Exception:
            continue
    return out


def collect_sessions(dump_fn: Callable[[], dict], *,
                      seconds: float = 300.0, interval: float = 5.0,
                      threshold: float = 0.35, min_samples: int = 4,
                      now: Callable[[], float] | None = None,
                      sleep: Callable[[float], None] | None = None
                      ) -> list[dict]:
    """采样 + 切分会话一站式（CLI 主入口）。"""
    kw: dict = {}
    if now is not None:
        kw["now"] = now
    if sleep is not None:
        kw["sleep"] = sleep
    samples = collect_samples(dump_fn, seconds=seconds, interval=interval, **kw)
    return segment_sessions(samples, threshold=threshold,
                            min_samples=min_samples)
```

（`Callable` 的 import 放在 `laos/screenlog.py` 顶部 `from __future__ import annotations` 之后、`import time` 之前。）

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: PASS（17 tests）

- [ ] **Step 5: 提交**

```bash
git add laos/screenlog.py tests/test_screenlog.py
git commit -m "feat(screenlog): collect_samples/collect_sessions 轮询采集（单次失败不废整轮）——S1-T2"
```

### Task 3: CLI 与记忆落库（bin/screenlog.py）

**Files:**
- Create: `bin/screenlog.py`
- Test: `tests/test_screenlog.py`（追加 `TestCli` 类）

**Interfaces:**
- Consumes: Task 2 的 `collect_sessions`、Task 1 的 `to_memory_rows`；`laos.memory.MemoryStore(path).remember(kind, text, tags=None)`（§0.9 签名）。
- Produces:
  - `run_pipeline(memory: MemoryStore, dump_fn: Callable[[], dict], *, seconds: float = 300.0, interval: float = 5.0) -> dict` —— 返回 `{"sessions": int, "remembered": int, "rows": list[str]}`；默认 `kind="screen"`，`tags=["screen"]`。
  - `main() -> int` —— argparse：`--minutes`（默认 5，换算 seconds）、`--interval`（默认 5.0）、`--memory`（默认 `var/memory/mem.jsonl`）、`--dry-run`（只打印不落库）。**门控**：未设 `LAOS_SCREENLOG=1` 且未传 `--force` 时直接退出并打印说明（默认关，隐私红线）。

- [ ] **Step 1: 写失败测试（追加到 tests/test_screenlog.py）**

```python
class TestCli(unittest.TestCase):
    def _mem(self, d):
        from laos.memory import MemoryStore
        return MemoryStore(Path(d) / "mem.jsonl")

    def test_run_pipeline_remembers_screen_rows(self):
        import os
        import tempfile
        os.environ["LAOS_SCREENLOG"] = "1"
        from screenlog import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            mem = self._mem(d)
            seq = ["com.tencent.mm"] * 5
            it = iter(seq)
            res = run_pipeline(mem, lambda: _dump(next(it)),
                               seconds=25.0, interval=5.0)
            self.assertEqual(res["sessions"], 1)
            self.assertEqual(res["remembered"], 1)
            rows = [r for r in mem.recall("com.tencent.mm", k=5)
                    if r.get("kind") == "screen"]
            self.assertEqual(len(rows), 1)
            self.assertIn("com.tencent.mm", rows[0]["text"])
        os.environ.pop("LAOS_SCREENLOG", None)

    def test_gate_blocks_without_env_or_force(self):
        import os
        import tempfile
        os.environ.pop("LAOS_SCREENLOG", None)
        from screenlog import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            res = run_pipeline(self._mem(d), lambda: _dump())
            self.assertEqual(res["remembered"], 0)
            self.assertEqual(res["sessions"], 0)
            self.assertIn("gated", res)

    def test_force_bypasses_gate(self):
        import os
        import tempfile
        os.environ.pop("LAOS_SCREENLOG", None)
        from screenlog import run_pipeline
        with tempfile.TemporaryDirectory() as d:
            seq = ["com.tencent.mm"] * 5
            it = iter(seq)
            res = run_pipeline(self._mem(d), lambda: _dump(next(it)),
                               seconds=25.0, interval=5.0, force=True)
            self.assertEqual(res["remembered"], 1)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'screenlog'`

- [ ] **Step 3: 写最小实现**

创建 `bin/screenlog.py`：

```python
#!/usr/bin/env python3
"""screenlog —— 屏幕界面语义轮询（视觉漏斗第一段，零视觉模型）。

与 bin/journal.py（听觉批处理）对偶：journal 把已落盘的 wav 蒸馏成记忆，
screenlog 把实时轮询的控件树蒸馏成记忆，且**字节零落盘**。

隐私：默认关。须显式 `LAOS_SCREENLOG=1` 或 `--force` 才轮询——视觉链路
不新增任何隐式采集（AGENTS.md 隐私红线的同源纪律）。dump 的 text/
resource_id 在 laos.screenlog.screen_signature 内即弃，不进本文件、
不进记忆、不进审计。

    LAOS_SCREENLOG=1 python bin/screenlog.py --minutes 5
    python bin/screenlog.py --minutes 5 --force --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "laos"))
sys.path.insert(0, str(REPO / "bin"))

from laos.memory import MemoryStore          # noqa: E402
from laos.screenlog import (collect_sessions,  # noqa: E402
                            to_memory_rows)

GATE_ENV = "LAOS_SCREENLOG"


def _gate_open(force: bool) -> bool:
    return bool(force) or os.environ.get(GATE_ENV) == "1"


def run_pipeline(memory: MemoryStore, dump_fn, *, seconds: float = 300.0,
                 interval: float = 5.0, force: bool = False) -> dict:
    """轮询 → 切分会话 → 落 kind="screen" 记忆。门控关时零副作用。"""
    if not _gate_open(force):
        return {"sessions": 0, "remembered": 0, "rows": [],
                "gated": f"未设 {GATE_ENV}=1 且未传 --force；视觉链路默认关"}
    sessions = collect_sessions(dump_fn, seconds=seconds, interval=interval)
    rows = to_memory_rows(sessions)
    remembered = 0
    for row in rows:
        rec = memory.remember(kind=row["kind"], text=row["text"],
                              tags=["screen"])
        if rec is not None:
            remembered += 1
    return {"sessions": len(sessions), "remembered": remembered,
            "rows": [r["text"] for r in rows]}


def main() -> int:
    ap = argparse.ArgumentParser(description="屏幕界面语义轮询（默认关）")
    ap.add_argument("--minutes", type=float, default=5.0,
                    help="轮询时长（分钟，默认 5）")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="采样间隔秒（默认 5）")
    ap.add_argument("--memory", default=str(REPO / "var" / "memory" / "mem.jsonl"),
                    help="记忆库路径")
    ap.add_argument("--force", action="store_true",
                    help=f"绕过 {GATE_ENV} 门控（仅测试/演示用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不落库")
    args = ap.parse_args()

    if not _gate_open(args.force):
        print(f"[screenlog] 未设 {GATE_ENV}=1 且未传 --force，退出（默认关）。")
        print(f"[screenlog] 显式开启：{GATE_ENV}=1 python bin/screenlog.py")
        return 0

    def dump_fn():
        # 生产通道：经 adb 取控件树。adb 不在/无设备时抛异常，由
        # collect_samples 逐次跳过（不中断整轮）。
        from drivers.screen_adb import (Adb, parse_current_focus,  # noqa: E402
                                        parse_uiautomator_xml, run)
        adb = Adb()
        xml = run(adb, "shell", "uiautomator", "dump", "/dev/tty") or ""
        return parse_uiautomator_xml(xml)

    mem = MemoryStore(Path(args.memory))
    res = run_pipeline(mem, dump_fn, seconds=args.minutes * 60.0,
                       interval=args.interval, force=args.force)
    if args.dry_run:
        res["remembered"] = 0
    for text in res["rows"]:
        print(text)
    print(f"[screenlog] 会话 {res['sessions']} · 落库 {res['remembered']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

> **Step 3 附带的读现场确认动作（非占位）**：`drivers/screen_adb.py` 的 `run(...)`/`Adb()` 精确签名与 `uiautomator dump` 取回方式，执行前跑一次核对：
> Run: `C:/Users/yaoyue/miniconda3/python.exe -X utf8 -c "import sys;sys.path.insert(0,'drivers');import screen_adb,inspect;print(inspect.signature(screen_adb.run));print(inspect.signature(screen_adb.Adb.__init__))"`
> Expected: 得到真实签名；若与本块写的 `run(adb, "shell", "uiautomator", "dump", "/dev/tty")` 不一致，按真实签名改 `dump_fn` 一处，其余不动（测试用假 `dump_fn`，不依赖真机）。

- [ ] **Step 4: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_screenlog -v`
Expected: PASS（20 tests）

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add bin/screenlog.py tests/test_screenlog.py
git commit -m "feat(screenlog): CLI+记忆落库（LAOS_SCREENLOG 默认关门控，dry-run）——S1-T3"
```

### Task 4: 双模态时间线（bin/diary.py 第七章）

**Files:**
- Modify: `bin/diary.py`（`SECTION_TITLES` 由 6 → 7；`build_diary` 主体追加第七章渲染）
- Test: `tests/test_diary.py`（若无则建；追加双模态用例，勿删既有）

**Interfaces:**
- Consumes: `build_diary(date, audit_records, memory_store, brain=None)` 现有签名（§0.9，**不改签名**，只在主体内新增 `memory_store.recall` 查询）；`kind="screen"` 记忆行（Task 3 Produces）；既有 `kind="journal"` 行。
- Produces: `build_diary` 输出 markdown 新增 `## 七、双模态时间线` 小节：当日 `screen` 会话与 `journal` 记录按时间窗（±10 分钟）配对，渲染 `屏幕: <pkg 时段> × 耳听: <HH:MM 文本摘要>`；无 screen 记忆时整节不出现（零副作用兼容）。

- [ ] **Step 1: 先读现有实现再动手（读现场确认，非占位）**

Run: `C:/Users/yaoyue/miniconda3/python.exe -X utf8 -c "import sys;sys.stdout.reconfigure(encoding='utf-8');print(open(r'bin/diary.py',encoding='utf-8').read())" | grep -n "SECTION_TITLES\|第六章\|节律\|声景\|def build_diary\|recall\|remember"`
Expected: 定位 `SECTION_TITLES`（§0.9 记在 `bin/diary.py:43`）、第六章段落边界、`build_diary` 内既有 `memory_store` 用法；确认追加第七章不破坏 6 章契约（旧日记文件不重写）。

- [ ] **Step 2: 写失败测试**

创建/追加 `tests/test_diary.py`：

```python
from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "bin"))
from laos.memory import MemoryStore      # noqa: E402
from diary import build_diary            # noqa: E402


class TestDiaryBimodal(unittest.TestCase):
    def _mem_with_both(self, d):
        mem = MemoryStore(Path(d) / "mem.jsonl")
        # 同日同时段：屏幕在微信，耳朵在说话（ts 用 14:00 本地时刻）
        import time
        base = time.mktime(time.strptime("1970-01-01 14:00:00", "%Y-%m-%d %H:%M:%S"))
        mem.remember(kind="screen",
                     text="[14:00-14:07] com.tencent.mm · 12节点/3可点/2类 · 7样本",
                     tags=["screen"], origin="screenlog")
        mem.remember(kind="journal", text="[14:03] 明天开会记得带材料",
                     tags=["NEUTRAL"])
        mem.remember(kind="journal", text="[18:20] 晚上吃面", tags=["NEUTRAL"])
        return mem, base

    def test_chapter7_pairs_screen_with_journal(self):
        with tempfile.TemporaryDirectory() as d:
            mem, _ = self._mem_with_both(d)
            out = build_diary("1970-01-01", [], mem)
            md = out["markdown"] if isinstance(out, dict) else str(out)
            self.assertIn("双模态时间线", md)
            self.assertIn("com.tencent.mm", md)
            self.assertIn("明天开会记得带材料", md)   # 同时段被配上
            self.assertNotIn("晚上吃面", md)          # 跨时段不配

    def test_chapter7_absent_without_screen_memory(self):
        with tempfile.TemporaryDirectory() as d:
            mem = MemoryStore(Path(d) / "mem.jsonl")
            mem.remember(kind="journal", text="[09:00] 早", tags=["NEUTRAL"])
            out = build_diary("1970-01-01", [], mem)
            md = out["markdown"] if isinstance(out, dict) else str(out)
            self.assertNotIn("双模态时间线", md)
```

- [ ] **Step 3: 跑测试确认失败**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_diary -v`
Expected: FAIL — `assertIn("双模态时间线", md)` 不成立

- [ ] **Step 4: 改实现**

在 `bin/diary.py`：

1. `SECTION_TITLES`（`bin/diary.py:43`）末尾追加 `"七、双模态时间线"`（由 6 元组变 7 元组）。
2. 在模块级追加纯函数（放在 `_aggregate` 附近，供单测与 `build_diary` 共用）：

```python
def _pair_bimodal(screen_rows: list[dict], journal_rows: list[dict],
                  window_s: float = 600.0) -> list[tuple[dict, list[dict]]]:
    """屏幕会话 × journal 记录按时间窗配对（±window_s 秒）。

    screen_rows/journal_rows 必含 ts（epoch 秒）。返回 [(screen_row, [jr,...])]，
    无配对的屏幕会话也保留（journal 列表为空）——"在用 App 但没说话"本身
    是有效信息。跨时段不配对（Task 4 测试的 assertNotIn 钉此行为）。
    """
    out: list[tuple[dict, list[dict]]] = []
    for s in screen_rows:
        st = float(s.get("ts", 0.0))
        near = [j for j in journal_rows
                if abs(float(j.get("ts", 0.0)) - st) <= window_s]
        out.append((s, near))
    return out


def _render_bimodal(pairs: list[tuple[dict, list[dict]]]) -> str:
    lines = ["## 七、双模态时间线", ""]
    for s, js in pairs:
        head = (s.get("text") or "").strip() or "(屏幕会话)"
        if js:
            for j in js:
                lines.append(f"- 屏幕 {head} × 耳听 {(j.get('text') or '').strip()}")
        else:
            lines.append(f"- 屏幕 {head} × 耳听 （无声）")
    lines.append("")
    return "\n".join(lines)
```

3. `build_diary` 主体内，在写完第六章后、落盘前追加（`_records_of_day` 是既有助手，§0.9 记于 `bin/diary.py:91`）：

```python
    # 第七章：双模态时间线（screenlog 落库的 kind=="screen" × journal）
    screen_rows = _records_of_day(
        [r for r in memory_store._records if r.get("kind") == "screen"], date)
    if screen_rows:
        journal_rows = _records_of_day(
            [r for r in memory_store._records if r.get("kind") == "journal"], date)
        pairs = _pair_bimodal(screen_rows, journal_rows)
        body.append(_render_bimodal(pairs))
```

（若 `MemoryStore` 的记录访问不叫 `_records`，按 Step 1 读到的真实字段名替换；只此一处。`body` 若在现有实现里叫别的名，同样按现场名替换——**替换仅限这两个标识符**，逻辑不变。）

- [ ] **Step 5: 跑测试确认通过**

Run: `C:/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_diary -v`
Expected: PASS（含既有全部 + 2 新用例）

- [ ] **Step 6: 全量回归 + 提交**

```bash
cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3
git add bin/diary.py tests/test_diary.py
git commit -m "feat(diary): 第七章双模态时间线（screen×journal 时间窗配对，无 screen 记忆时零副作用）——S2-T4"
```

### Task 5: 登记、门禁与文档对齐

**Files:**
- Modify: `docs/ONBOARDING.md`（§3 常用命令追加 screenlog 两条；§0 事实基线不变——本波不改测试基线数字，除非实跑数变）
- Modify: `README.md`（功能地图 A 段追加 A12；数据面板测试数以**实跑**为准，仅当实跑数变化才改）
- Modify: `docs/guide/laos-features-map.md`（A 段追加 A12 行，体例同 A10/A11）
- Modify: `docs/superpowers/plans/README.md`（登记本计划为 `已执行`，落点摘要）

**Interfaces:**
- Consumes: Task 1-4 的全部交付物。
- Produces: 三处文档登记 + 门禁绿 + （若发版）CHANGELOG 段。

- [ ] **Step 1: 实跑取权威测试数**

Run: `cd C:\Users\yaoyue\CodeBuddy\Claw\laos && C:/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -t . 2>&1 | tail -3`
Expected: `Ran N tests` + `OK (skipped=5)`；N 记入本 Task 报告，**只有 N 变化时才改 README 数据面板**（数字纪律：不预设、不照抄旧值）。

- [ ] **Step 2: 跑交接门禁（必须绿才算文档对齐）**

Run: `C:/Users/yaoyue/miniconda3/python.exe scripts/check_onboarding.py`
Expected: `交接门禁 OK（实测:测试 N 项 / 模块 M 个）`

- [ ] **Step 3: 三处文档登记**

1. `docs/guide/laos-features-map.md` A 段表格末尾追加一行（体例同 A11）：

```markdown
| A12 | **屏幕语义漏斗** `laos/screenlog.py`+`bin/screenlog.py` | 视觉同构第一段：轮询既有只读 `screen.dump` → 界面签名（丢弃全部 text/id）→ 稳定段成会话 → `kind="screen"` 记忆；**XML 字节零落盘**，比音频即焚更彻底；默认关 | `LAOS_SCREENLOG=1 python bin/screenlog.py --minutes 5`；日记第七章「双模态时间线」自动配对 |
```

2. `README.md`：在功能地图等价位置补 A12 一行 + 数据面板旁加"视觉链路默认关"一句。
3. `docs/ONBOARDING.md` §3 常用命令追加：

```bash
LAOS_SCREENLOG=1 python bin/screenlog.py --minutes 5   # 屏幕语义轮询（默认关，零落盘）
python bin/screenlog.py --minutes 1 --force --dry-run   # 不落库试跑
```

- [ ] **Step 4: 计划状态登记**

在 `docs/superpowers/plans/README.md` 表内追加一行：

```markdown
| 2026-10-12-audiovisual-innovation.md | 已执行（Wave 1） | Wave1 屏幕语义漏斗：laos/screenlog.py（签名/切分/轮询）+ bin/screenlog.py（LAOS_SCREENLOG 门控）+ diary 第七章双模态时间线；零视觉模型、text/id 即弃、XML 零落盘；Wave 2/3 见该计划 §4 |
```

- [ ] **Step 5: 三查后提交**

自查（非派发）：① spec 覆盖——§1 的 S1/S2 是否都有 Task（S1→T1/T2/T3，S2→T4）；② 占位符——grep `TBD|加适当|处理边界|为上述写测试` 应空；③ 类型一致——`collect_sessions`/`to_memory_rows`/`_pair_bimodal` 跨 Task 名一致。

```bash
git add docs/ONBOARDING.md README.md docs/guide/laos-features-map.md docs/superpowers/plans/README.md
git commit -m "docs: 登记 A12 屏幕语义漏斗+双模态日记+计划状态（Wave 1 收尾）——S1/S2-T5"
```

> **Wave 1 收尾**：可独立发版。发版走 AGENTS.md 全链：`python scripts/release.py --apply` → CHANGELOG 人工插 `## [vX.Y.Z]` 段（标题建议「屏幕语义漏斗：视觉同构第一段」）→ release commit → annotated tag → push master+tag → `python scripts/gen_release_notes.py`。

---

## §4 Wave 2 / Wave 3 设计级详设（接口冻结，届时各自拆独立计划）

> 按 writing-plans 的 Scope Check：Wave 2/3 是独立子系统，**不在本文件展开步骤**。以下只冻结接口与红线，执行时各建 `2026-10-XX-<name>.md`。

### Wave 2 · 听觉预算（laos/earbudget.py，内核侧）

- **Files（预分配）**：Create `laos/earbudget.py` / `tests/test_earbudget.py`；Modify `laos/kernel.py`（`_impl_ear_transcribe` 与 `rec.replay`/`mic.replay` 前置扣费）、`laos/sentinel.py`（超预算转 always_ask）。
- **Produces（接口冻结）**：
  - `class EarBudget` —— `__init__(self, *, daily_units: float = 100.0, state_path: Path | None = None)`；`charge(tool: str, units: float) -> dict`（返回 `{"ok": bool, "remaining": float, "reason": str}`）；`remaining() -> float`；`reset() -> None`。
  - 常量 `UNIT_COST = {"ear.transcribe": 1.0, "rec.replay": 0.5, "mic.replay": 0.5, "audio.separate": 3.0}`（驱动侧重计费，成本可配）。
- **红线**：预算耗尽**不静默失败**——返回 EPERM 带原因并升 sentinel always_ask（人工可一次性扩容）；`LAOS_EAR_BUDGET=0` 关闭（默认关，行为字节不变）；预算状态落 `var/`（gitignored），不进审计内容。
- **验收**：超预算调用返回 EPERM；`--dry-run` 式 `charge` 不改状态；并发 `charge` 不超支（锁内读改写，同 `memory.remember` 的 `_lock` 纪律）。

### Wave 2 · 听觉 taint（信息流级污点）

- **Files（预分配）**：Create `laos/eartaint.py` / `tests/test_eartaint.py`；Modify `laos/kernel.py`（`mem.remember` 前置）、`laos/sentinel.py`（污点源登记）。
- **Produces（接口冻结）**：
  - `REDACT_PATTERNS: tuple[str, ...]` —— 支付/密码/验证码类的**正则常量**（单一来源，测试钉死）。
  - `taint_of(text: str) -> list[str]` —— 返回命中的规则名列表（空=干净）。
  - `propagate(agent_pid: int, hits: list[str], ttl_s: float = 3600.0) -> None`；`is_tainted(agent_pid: int) -> bool`。
- **红线**：污点**带 TTL 可过期**（区别于 sentinel 进程级 taint 的永不回退——那是操作污点，这是信息流污点，语义不同须在文档写明）；命中即拦截 `mem.remember`，**但不拦截已发生的转写**（转写是 agent 分内事）；`LAOS_EAR_TAINT=0` 关闭。
- **与 confgate 的边界**：confgate 管"置信度分流"，eartaint 管"内容红线传播"，两者不重叠；evroute 的 DROP 防火墙保持既有职责。

### Wave 3 · 空间方向记忆（laos/spatialdir.py，硬件前置）

- **前置（硬门）**：`drivers/drv_mic.py:51` `CHANNELS = 1` → 需新增 `LAOS_MIC_CHANNELS=2` 显式开关（默认 1，字节兼容）；**无双麦实测通过前不得默认开启**。
- **Files（预分配）**：Create `laos/spatialdir.py` / `tests/test_spatialdir.py`；Modify `bin/journal.py`（`--spatial` 追加末位关键字参数，默认 False）、`bin/diary.py`（第六章追加「声音从哪来」聚合）。
- **Produces（接口冻结）**：
  - `direction_label(ild_db: float, ipd_rad: float, *, ild_gate_db: float = 3.0) -> str` —— `"L"`/`"C"`/`"R"`/`"?"`；ILD 低于门限返回 `"?"`（正面/不可辨，不硬猜）。
  - `segment_direction(left: bytes, right: bytes, sr: int = 16000) -> dict` —— 调 `laos.binaural.binaural_features` 后返回 `{"label": str, "ild_db": float, "ipd_rad": float}`。
- **红线**：方向是**粗标签**（三值），不存连续角度、不存任何可重构空间位置的特征；`--spatial` 默认关；与待执行波 A（说话人分离）正交叠加，不合并实现。
- **依赖的既有件**：`laos/binaural.py` 的 `ild_db(left, right, sr, freqs=None)` / `ipd_rad(...)` / `binaural_features(left, right, sr, ...)`（§0.3，已实现已测，本波只做接线）。

---

## Self-Review 结论（作者自查）

- **spec 覆盖**：用户问"音视频 + 全天候录音 + AgentOS 内核还能做什么创新"——§0 用 11 条可复算事实锁定棋盘；§1 给 7 个方向 + 4 条明确否决（含否决理由，防后人重提）；§2 分波；§3 Wave 1 五个 Task 全覆盖 S1（T1/T2/T3）与 S2（T4）+ 登记（T5）。A1/A2/B1/B2 在 §4 有接口冻结，无悬空需求。
- **占位符扫描**：无 "TBD/加适当错误处理/处理边界情况/为上述写测试"。两处「按现场名替换」均伴随**精确的读现场命令与预期输出**（Task 3 Step 3 附注、Task 4 Step 1），且限定替换范围到 1-2 个标识符——这是读现场确认动作，不是占位。
- **类型一致**：`screen_signature`/`signature_distance`/`segment_sessions`/`render_session`/`to_memory_rows`（T1）在 T2/T3 消费名一致；`collect_samples`/`collect_sessions`（T2）在 T3 一致；`_pair_bimodal`/`_render_bimodal`（T4）单一来源；Wave 2/3 的 `charge`/`taint_of`/`direction_label` 在 §4 内自洽。
- **与 AGENTS.md 一致性**：conda 红线、零依赖、目录纪律（不新建顶层目录）、隐私红线（新增视觉红线且默认关）、测试口径实跑、来源诚实、计划编写纪律（跨 Task 原文重复）、发版链——全部落为 Global Constraints 或 Task 内硬断言。
- **与既有待执行计划不错峰**：§0.11 明确列出 auditory-governance-wave（A/B/C/D）与 evolve-followups 的占坑；本计划 S1/S2/A1/A2/B1 均在其外。B1 与波 A 的关系（正交）已注明，不合并。
- **已知取舍（非 bug，刻意）**：
  1. `laos/screenlog.py` 不 import `drivers/`（按 dict 契约消费）——保持核心包零驱动依赖，代价是 `bin/screenlog.py` 的 `dump_fn` 要自己接线 adb（已给附注命令核对）。
  2. Wave 3 排最后且带硬门——因为 §0.4 单声道是既成事实，不装作今天能跑。
  3. `collect_samples` 用宽 `except Exception` 跳过单次失败——理由已写进 docstring（临时拔线不废整轮），测试 `test_dump_failure_is_skipped_not_fatal` 钉住该语义。
- **本计划已过代码级试跑验证（2026-10-12，非纸面审查）**：Task 1 的实现与测试被提取到 `var/scratch/` 实际执行，**抓到并修掉一处真 bug**——初版 `segment_sessions` 用「锚点切换即新段」，导致 5 秒通知横幅这单样本抖动会把一段连续会话**劈成两段**（实测 `test_short_blip_dropped` 断言 1 实得 2）。修正为追加 `merge_adjacent`（同 package 相邻段按 `max_gap_s` 缝合），并补 2 条反向用例（长间隔不缝 / `max_gap_s=0` 不缝）。修正后 11 项全绿，三向语义（长间隔 3 段 / 抖动缝回 1 段 8 样本 / 关门得 2 段）均实测确认。**文档内的代码即试跑通过版**，执行者不应再看到非预期红。
