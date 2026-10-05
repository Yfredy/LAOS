# 本周语音 AI 论文（空间音频×全双工）采纳 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把周报 8 篇论文中对 laos 有直接帮助的四件东西落进主库：●A 双工时序度量（`laos/duplex.py`）、●B 轮转三态策略 + 委托注入（`laos/turnpolicy.py` + `TurnBuffer.interject`）、●C 双耳空间线索（`laos/binaural.py`）、◐D FOA 基础件（`laos/foa.py`）。全部纯 stdlib、TDD。

**Architecture:** 四个新模块互不依赖，全部进 `laos/`（核心零依赖承诺——Goertzel/状态机/事件配对无需 numpy）。A 消费事件时间线（与审计日志同构的 `(t, kind)` 序列）；B 之一 `TurnPolicy` 是纯函数状态机（duplex 度量的决策面），之二给既有 `TurnBuffer` 加一个插队方法（SALMONN-duo 委托返回 + Context Spanning 原文注入的语义）；C/D 是空间侧工具件，与 micgeom（几何先验）互补、不重叠。

**Tech Stack:** Python 3.x stdlib only（`math`/`dataclasses`/`threading`）。无新依赖、无新环境。

**Spec:** `docs/research/2026-10-05-speech-weekly-spatial-duplex.md`（学习文档：8 篇逐篇摘要 + 采纳裁决表 + 来源诚实声明）。

## Global Constraints

- **conda 环境红线**：只准用 `C:/Users/yaoyue/miniconda3/python.exe` 跑测试（Git Bash 路径 `/c/Users/yaoyue/miniconda3/python.exe`），**禁止 pip install / 任何环境修改**。
- 测试命令：`cd /c/Users/yaoyue/CodeBuddy/Claw/laos && /c/Users/yaoyue/miniconda3/python.exe -m unittest tests.test_duplex tests.test_turnpolicy tests.test_binaural tests.test_foa -v`；收尾跑全量 `... -m unittest discover -s tests -q`（当前基线 398 全绿，本计划只增不减）。
- **laos 核心零依赖**：四个新模块只准 `import` stdlib + `from .locks import UniqueLock`（turnbuf 改动处）。
- 录音/隐私语义零触碰：LAOS_REC、显式 syscall 触发、审计 event:"mic" 一概不动——本计划只加**纯计算**层。
- 阈值全部显式可配、默认值写进 docstring 并注明论文出处（Duplex-MPE 的四能力分解 / SAIL 的双耳相位差）。
- 每个 Task 一个 commit（`feat(...)`/`test(...)` conventional 格式）；全部完成后走 `scripts/release.py` 发 **v0.12.0**（feat 集 → MINOR；一个完整需求波次 = 一次 MINOR）。

## 来源→落点映射

| 论文 | 落点 | 不做（记入文档） |
|---|---|---|
| Duplex-MPE 2609.31948 | ●A `duplex.py` 四能力中三个时序项的客观计量；●B `turnpolicy.py` "何时答/沉默/停" | 回答准确性评分（需内容语义，归 ASR/Jev 层） |
| SALMONN-duo 2609.34247 | ●B `TurnBuffer.interject()` 委托返回插队注入 | 双系统模型本身（laos 架构已是快慢分层） |
| Context Spanning 2609.33443 | ●B 注入语义 = 原文插队帧（验证 mem 原文存储的既有决策） | chunked prefill 机制（模型层，非 OS 层） |
| SAIL 2609.34347 | ●C `binaural.py` 空间流最小内核：Goertzel ILD/IPD | 双流 Q-Former / LLM 对齐（模型层） |
| Bin2Ambi 2609.39732 / RMS-AQA 2610.00935 | ◐D `foa.py` FOA 中间格式基础件 | 学习式双耳→FOA（驱动子进程远期）；RMS-AQA 评测集接入（待 FOA 件就绪） |
| CharDuplex 2609.34461 / OmniDream 2609.36295 | ○ 学习文档记录（角色归 context 层；三段式元数据启示） | 无代码 |

## File Structure

```
laos/
  duplex.py        # 新：事件时间线 → 双工时序度量（DuplexMetrics + analyze + summarize）
  turnpolicy.py    # 新：TurnPolicy.decide() -> speak/hold/stop 纯状态机
  turnbuf.py       # 改：+interject()（插队帧，UniqueLock 保护）
  binaural.py      # 新：goertzel / ild_db / ipd_rad / binaural_features
  foa.py           # 新：plane_wave(SN3D/N3D) / decode_quad / acn_index
tests/
  test_duplex.py
  test_turnpolicy.py    # 含 turnbuf.interject 测试
  test_binaural.py
  test_foa.py
docs/research/2026-10-05-speech-weekly-spatial-duplex.md            # 已建（Spec）
docs/research/plans/2026-10-05-speech-weekly-adoption.md            # 本文件
```

---

## Task 1: ●A `laos/duplex.py` 双工时序度量

**Files:**
- Create: `laos/duplex.py`、`tests/test_duplex.py`

**接口（精确）：**

```python
# 事件 = (t_seconds: float, kind: str)；kind ∈ {"user_start","user_end","agent_start","agent_end","barge_in"}
# 与内核审计日志同构：分析器不产生事件，只消费调用方给的时间线。

@dataclass
class DuplexMetrics:
    response_latencies: list[float]      # 每次 user_end → 其后最近 agent_start（秒）
    barge_in_latencies: list[float]      # 每次 barge_in → 其后最近 agent_end
    overlap_durations: list[float]       # 用户与代理同时有声的时段
    total_user_speech: float
    total_agent_speech: float
    premature_responses: int             # agent_start 早于 user_end 的次数（抢话，Duplex-MPE"沉默保持"的反面计数）
    interrupts: int                      # barge_in 总数

    @property
    def overlap_ratio(self) -> float: ...   # overlap 总时长 / (user+agent 总时长)，两者皆 0 → 0.0

def analyze(events: list[tuple[float, str]], *, horizon: float = 10.0) -> DuplexMetrics:
    """排序后单遍扫描配对；超出 horizon 未配到的事件不计（防脏日志拖垮中位数）。"""

def summarize(m: DuplexMetrics) -> dict:
    """JSON 友好：各延迟的 median/p90/max + overlap_ratio + 计数。空列表 → None 字段。"""
```

**Steps:**

- [ ] **Step 1** 先写测试（预计 8 个）：响应延迟配对（1 例）；抢话计数（agent_start 先于 user_end）；打断响应延迟；重叠时段（交叉区间求交）；overlap_ratio 边界（全 0 → 0.0）；horizon 截断（11s 后的 agent_start 不算）；乱序输入先排序；summarize JSON 可序列化 + 空度量全 None。合成事件全部手写数值，断言精确值。
- [ ] **Step 2** 实现 `laos/duplex.py`：`sorted(events)` 单遍扫描；用户/代理有声区间各自由 start/end 配成区间（未闭合区间在扫描结束时按末事件闭合或丢弃——选**丢弃**并 docstring 注明，脏数据宁缺毋滥）；区间求交得 overlap；响应延迟 = 每个 user_end 向后找第一个 agent_start（≤horizon）。
- [ ] **Step 3** 跑 `tests.test_duplex` 全绿；commit `feat(duplex): full-duplex timing metrics from event timelines (Duplex-MPE capability decomposition)`。

---

## Task 2: ●B-1 `laos/turnpolicy.py` 轮转三态

**Files:**
- Create: `laos/turnpolicy.py`、`tests/test_turnpolicy.py`

**接口（精确）：**

```python
class TurnPolicy:
    """Duplex-MPE 三决策（何时答/沉默/停）的时序策略位。纯函数式状态机，无副作用。"""

    def __init__(self, *, tail_silence_ms: int = 500, min_speech_ms: int = 200,
                 min_hold_ms: int = 250) -> None: ...

    def decide(self, events: list[tuple[int, str]], now_ms: int) -> str:
        """events = [(t_ms, kind)]，kind 同 duplex.py。返回：
        "stop"  —— 代理正在说 + 用户开口（barge-in：停，TurnBuffer.interrupt 的策略入口）
        "speak" —— 用户话轮完成：有声 ≥ min_speech_ms 且尾部静默 ≥ tail_silence_ms
                   且（now - 用户最后活动）≥ min_hold_ms（意图保持闸，防 LateIntent 式过早响应）
        "hold"  —— 其余一切（用户在说/在听别人说/静默未达阈值）
        优先级 stop > speak > hold。
        """
```

**Steps:**

- [ ] **Step 1** 先写测试（预计 9 个）：用户说完静默 600ms → speak；静默只有 300ms → hold；说话只持续 100ms（咔哒）→ hold（min_speech 闸）；min_hold 未到 → hold；代理说话中用户开口 → stop；stop 优先于 speak；无事件 → hold；参数自定义生效（tail_silence_ms=200 时 300ms 静默 → speak）；时间线乱序输入。
- [ ] **Step 2** 实现：内部复用区间逻辑（不 import duplex——保持两模块零耦合，允许少量重复换取独立性，docstring 注明）。
- [ ] **Step 3** 全绿；commit `feat(turnpolicy): speak/hold/stop turn-taking policy state machine (Duplex-MPE)`。

---

## Task 3: ●B-2 `TurnBuffer.interject()` 委托注入

**Files:**
- Modify: `laos/turnbuf.py`；`tests/test_turnpolicy.py` 追加 TestInterject 类

**接口（精确）：**

```python
def interject(self, text: str) -> None:
    """插队帧：外部结果（慢系统返回/检索到的原文）插到待送达队列**头部**，
    下一次 deliver 先送它（SALMONN-duo 委托返回无缝织入 + Context Spanning 原文注入）。
    interrupt() 之后仍可用（清场后新起一轮播报）。空文本忽略。UniqueLock 保护。"""
```

**Steps:**

- [ ] **Step 1** 测试（4 个）：append("A") 后 interject("B") → deliver "BA"；interrupt 后 interject 仍进 pending；空串 no-op；并发 interject/append 线程安全（两线程各 500 次，最终 pending 长度=1000）。
- [ ] **Step 2** 实现：锁内 `self._pending.insert(0, text)`（非空时）；docstring 注明语义来源（SALMONN-duo/Context Spanning，与 commit 的"只记已送达"正交：插队帧同样只在送达后进记忆）。
- [ ] **Step 3** 全绿；commit `feat(turnbuf): interject() — delegate-result head-of-queue frames (SALMONN-duo / Context Spanning)`。

---

## Task 4: ●C `laos/binaural.py` 双耳空间线索

**Files:**
- Create: `laos/binaural.py`、`tests/test_binaural.py`

**接口（精确）：**

```python
def goertzel(samples: Sequence[int], sr: int, f0: float) -> complex:
    """单频点 DFT 系数（Wolfgang Goertzel 1958）。48k 下千点窗纯 Python 实测 <1ms。"""

def ild_db(left: Sequence[int], right: Sequence[int], sr: int,
           freqs: Sequence[float] = (250.0, 500.0, 1000.0, 2000.0, 4000.0)) -> list[float]:
    """逐频点强度差：20·log10(|L(f)|/|R(f)|)；两通道该频点皆近零 → 0.0（记 0 不记 NaN）。"""

def ipd_rad(left, right, sr, freqs=同上) -> list[float]:
    """逐频点相位差 angle(L(f)) - angle(R(f))，wrap 到 (-π, π]。"""

def binaural_features(left, right, sr, freqs=同上) -> dict:
    """{"ild_db": [...], "ipd_rad": [...]}——SAIL 空间流的最小内核特征包。"""
```

**Steps:**

- [ ] **Step 1** 测试（预计 7 个）：合成 1kHz 正弦右通道延迟 π/3 相位 → `ipd_rad` 在 1000Hz 处 ≈ -π/3（±0.05，注意 wrap 方向）；右通道幅度减半 → 该频点 ILD ≈ +6.02 dB；静音输入 ILD=0.0 且不抛错；freqs 自定义单点；两通道全同 → ILD≈0/IPD≈0；goertzel 与手算 DFT 单点互验（同一窗直接 Σx·e^{-j2πfn/N}）；`binaural_features` 键与长度。
- [ ] **Step 2** 实现 Goertzel（标准两系数递推 + 复数合并步）；ILD/IPD 按接口约定。 PCM16 整数输入（与 vad.py 同一约定，32768 满幅——比值无量纲不受影响）。
- [ ] **Step 3** 全绿；commit `feat(binaural): Goertzel ILD/IPD binaural spatial cues (SAIL spatial stream)`。

---

## Task 5: ◐D `laos/foa.py` FOA 基础件

**Files:**
- Create: `laos/foa.py`、`tests/test_foa.py`

**接口（精确）：**

```python
N3D_GAIN = math.sqrt(3.0)   # SN3D → N3D：XYZ 通道增益 √3（W 不变）

def plane_wave(az_deg: float, el_deg: float, norm: str = "sn3d") -> tuple[float, float, float, float]:
    """平面波 FOA 编码 → (W, X, Y, Z)。方位角 az（水平面，逆时针为正）、仰角 el。
    SN3D：W=1.0，X=cos(el)cos(az)，Y=cos(el)sin(az)，Z=sin(el)。N3D：XYZ × √3。
    norm 非法 → ValueError(EINVAL 语义)。"""

def decode_quad(wxyz: tuple[float, ...]) -> list[float]:
    """解码到四角扬声器（az 45°/135°/225°/315°，el=0）：gain_i = W + dot(u_i, XYZ)，
    负增益截 0，按最大增益归一。"""

def acn_index(l: int, m: int) -> int:
    """ACN 通道序：l(l+1)+m（一阶 = W0,X1,Y2,Z3 → 与 (W,X,Y,Z) 元组序一致）。非法 l/m → ValueError。"""
```

**Steps:**

- [ ] **Step 1** 测试（预计 6 个）：az=0/el=0 → (1,1,0,0)；az=90 → (1,0,1,0)；el=90 → (1,0,0,1)；N3D 模式 XYZ=√3·SN3D；decode_quad 对 az=45 平面波 → 首扬声器独占（其余 ≈0）；acn_index 表 + 非法输入。
- [ ] **Step 2** 实现（纯三角函数）；docstring 注明 Bin2Ambi/RMS-AQA 是动机、学习式转换属远期驱动子进程。
- [ ] **Step 3** 全绿；commit `feat(foa): first-order Ambisonics encode/decode primitives (Bin2Ambi / RMS-AQA groundwork)`。

---

## Task 6: 收尾——文档登记 + 全量回归 + v0.12.0 发版

**Files:**
- Modify: `docs/research/INDEX.md`（清单表加一行本周报学习文档）、`docs/research/2026-10-05-speech-weekly-spatial-duplex.md`（裁决表 A-D 标"●已落地（v0.12.0 执行注记）"）

**Steps:**

- [ ] **Step 1** 全量测试：`/c/Users/yaoyue/miniconda3/python.exe -m unittest discover -s tests -q`——398 基线 + 新增（预计 ~34）全绿，零失败零跳过异常。
- [ ] **Step 2** INDEX.md 登记 + 学习文档执行注记；commit `docs: register speech-weekly digest + adoption execution notes`。
- [ ] **Step 3** 发版 v0.12.0：`/c/Users/yaoyue/miniconda3/python.exe scripts/release.py --dry-run` 核对推导 → `--apply` 同步三棵树 `__version__` → **人工**把草稿段插入 CHANGELOG.md（v0.12.0，2026-10-05，Added：duplex/turnpolicy/interject/binaural/foa）→ commit → **先 commit 后打 tag**（v0.11.0 教训）→ `git push origin master --tags` → gh 建 Release 页（token 经 `git credential fill`，不回显）。
- [ ] **Step 4** 交付说明：四件落地物一句话 + 测试数 + Release 链接。

---

## 验收清单（Definition of Done）

- [ ] 四个新模块纯 stdlib（`grep -E "^import |^from " laos/{duplex,turnpolicy,binaural,foa}.py` 无第三方）
- [ ] 新增测试 ≥30 且全量 398+ 全绿
- [ ] duplex.summarize() 输出可 `json.dumps`
- [ ] TurnPolicy.decide 无副作用（同输入同输出，重复调用验证）
- [ ] v0.12.0 tag 指向 CHANGELOG commit 之后
