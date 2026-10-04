# 四篇微信文章 + arXiv 2607.02129 复现 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把四个知识源（①说话人头部朝向 STFT 相位论文 arXiv 2607.02129v1 / ②PhaseCoder 几何无关空间音频编码器 / ③车载 ANC FxLMS 机制 / ④LUFS·True Peak 响度计量）中**能复现的全部复现出来**，落在新隔离区 `Repro-ZCode/`，TDD、零主代码改动。

**Architecture:** 新建 `Repro-ZCode/`（与 `AlwaysOnRec-ZCode/` 平级的隔离实现区，但不复制 laos 树——四个复现均不触碰 laos 代码）。四个互不依赖的模块包：`repro/bs1770/`（纯 numpy 响度计量）、`repro/anc/`（纯 numpy FxLMS）、`repro/sho/`（numpy 仿真 + torch 模型，复现论文全管线）、`repro/phasecoder/`（numpy 复现 DeepMind JAX 编码数学）。主库只新增 docs。

**Tech Stack:** numpy 2.4 / scipy 1.18 / torch 2.6（CPU 即可，模型 <1M 参数）/ matplotlib（结果图）。**不安装任何新包**（pyroomacoustics 缺失 → 自研 Allen-Berkley 镜像源法；JAX 缺失 → 读源码后用 numpy 复现数学）。

**Spec:** `docs/research/2026-10-05-four-article-repro.md`（Task 0 先建学习摘要版，收尾任务补结果）——四个来源：微信文章 ×4 + `C:\Users\yaoyue\Desktop\2607.02129v1.pdf`（Tampere 头部朝向论文 5 页全文）。

## Global Constraints

- **conda 环境红线**：只准用 `C:/Users/yaoyue/miniconda3/python.exe` 跑测试/训练，**禁止 pip install / 任何环境修改**（pyroomacoustics/JAX 均不得安装）。
- 测试命令统一：`cd Repro-ZCode && C:/Users/yaoyue/miniconda3/python.exe -m pytest tests/ -q`（Git Bash 路径 `/c/Users/yaoyue/miniconda3/python.exe`）。
- 主库 `laos/`、`drivers/`、`AlwaysOnRec-ZCode/` **零改动**；所有新代码在 `Repro-ZCode/`。
- 一切随机过程显式 `numpy.random.default_rng(seed)`，测试确定性。
- 论文参数忠实优先，跑不动时**等比缩距**并在代码 docstring + 复现文档里写明偏差（诚实清单是交付物的一部分）。
- 每个 Task 一个 commit（`feat(repro): ...` conventional 格式）；收尾用 `scripts/release.py` 走 v0.8.0 发版流程。

## 来源→复现物映射（哪些能复现、哪些不能）

| 来源 | 能复现 | 不能复现（记入文档） |
|---|---|---|
| ① 头部朝向论文（PDF 全文） | STFT 相位特征（4ms/2ms/F=128）、6 麦环形阵 ISM 仿真、声源指向性、扩散噪声、CNN+BiGRU+MHSA 模型全架构、MAE 环形误差、个性化微调协议、10° 分桶分析 | 论文数字（40,295 训练样本×200k 步→等比缩到 ~百样本×数百步）；22 条实测 VDP（用 cardioid 族 a+b·cosθ 替代）；VCTK 语料（自造伪语音）；WHAM（自造扩散噪声）；VAD 模块 [20]（能量裁剪替代） |
| ② PhaseCoder | 克隆 google-deepmind/phasecoder 读 JAX 源码，numpy 复现 `arbitrary_mic_geometry_embeddings` + `get_mag_phase_features` + 输出头结构（38 az / 13 dist / 18 el softmax） | 1.5M RIR 预训练、checkpoint 推理（JAX 缺失）、Gemma 3n 集成 |
| ③ 车载 ANC | 单通道 FxLMS（发动机阶次参考 + 宽带）、次级通路估计、收敛与降噪量测量、2×2 多通道 FxLMS | 厂商营销数字（Bose 3-6dB 等，仅作锚点引用）；真车 DSP 实时性 |
| ④ LUFS/True Peak | BS.1770-4 全套：K 计权双二阶节（48k 精确系数 + 任意 fs 参数化）、门控积分响度、M/S 时间尺度、LRA（EBU 3342）、True Peak 4× 过采样、PLR | ——（该文全部核心概念均可规范复现） |

## File Structure

```
Repro-ZCode/
  README.md                     # 隔离区章程：四来源→模块地图→测试运行法
  repro/__init__.py
  repro/bs1770.py               # K 计权/门控响度/M/S/LRA/True Peak/PLR
  repro/anc.py                  # 阶次合成/FxLMS 单通道+2×2/次级通路辨识
  repro/sho/__init__.py
  repro/sho/ism.py              # Allen-Berkley 镜像源法 + 环形阵 + 房间采样
  repro/sho/speech.py           # 伪语音合成 + cardioid 指向性声源
  repro/sho/features.py         # STFT 相位 sin/cos 特征 (2C×T×128)
  repro/sho/noise.py            # 扩散场相干噪声 Γ(f)=sinc(2πfd/c)
  repro/sho/model.py            # torch: Conv×3+BiGRU×2+MHSA×2 (Fig.1)
  repro/phasecoder.py           # mic 几何相位调制编码 + STFT 补丁特征（读 JAX 源码后对齐）
  scripts/run_sho_repro.py      # 端到端: 生成→训练→评测→指标 JSON + 分桶 PNG
  scripts/run_repro_all.py      # 四模块冒烟汇总
  var/                          # 运行工件（.gitignore 除外指标 JSON）
  tests/test_bs1770.py
  tests/test_anc.py
  tests/test_ism.py
  tests/test_speech.py
  tests/test_features.py
  tests/test_noise.py
  tests/test_model.py           # 含标记 slow 的快速训练冒烟
  tests/test_phasecoder.py
docs/research/2026-10-05-four-article-repro.md
docs/research/plans/2026-10-05-four-article-repro-plan.md   # 本文件
```

---

## Task 0: 学习摘要文档（Spec）+ 隔离区骨架

**Files:**
- Create: `docs/research/2026-10-05-four-article-repro.md`
- Create: `Repro-ZCode/README.md`、`Repro-ZCode/repro/__init__.py`、`Repro-ZCode/tests/__init__.py`、`Repro-ZCode/var/.gitkeep`

**Steps:**

- [ ] **Step 1** 写 `docs/research/2026-10-05-four-article-repro.md` 骨架：四来源各一节（学到什么/可复现物/不可复现物/替代方案），映射表照抄上方"来源→复现物映射"。
- [ ] **Step 2** 建 `Repro-ZCode/` 目录骨架 + README（章程：四模块、运行命令、零主改动承诺）。
- [ ] **Step 3** Commit: `git add Repro-ZCode docs/research/2026-10-05-four-article-repro.md docs/research/plans/2026-10-05-four-article-repro-plan.md && git commit -m "docs(repro): four-source learning digest + repro plan + isolation zone scaffold"`

---

## Task 1: BS.1770-4 K 计权与门控响度（bs1770）

**Files:**
- Create: `Repro-ZCode/repro/bs1770.py`
- Test: `Repro-ZCode/tests/test_bs1770.py`

**Interfaces (Produces):**
- `k_weight_biquads(fs: float) -> tuple[np.ndarray, np.ndarray]`：返回 `(b_coeffs(2,3), a_coeffs(2,3))`——第一行 shelving、第二行 highpass，均为 `[b0,b1,b2] / [1,a1,a2]`
- `integrated_loudness(x: np.ndarray, fs: float) -> float`：x 形状 `(C, N)` 或 `(N,)`（通道权重：单声道 1.0、立体声 L/R 各 1.0），返回 LUFS
- `momentary_loudness(x, fs) -> np.ndarray` / `short_term_loudness(x, fs) -> np.ndarray`：逐窗响度数组（LUFS）
- `loudness_range(x, fs) -> float`（LRA, LU）、`true_peak(x, fs) -> float`（dBTP）、`plr(x, fs) -> float`
- 内部 `_apply_biquad(x, b, a)` 直接 II 转置结构；`_block_loudness(x, fs, win_s, hop_s)` 供门控复用

**关键规范事实（写死进测试）：**
- 48 kHz 精确系数（BS.1770-4 Annex）：shelving `b=[1.53512485958697,-2.69169618940638,1.19839281085285], a=[1,-1.69065929318241,0.73248077421585]`；highpass `b=[1,-2,1], a=[1,-1.99004745483398,0.99007225036621]`
- 任意 fs 参数化（EBU/pyloudnorm 口径）：shelf f0=1681.974450955533 Hz, G=3.99984385397 dB, Q=0.7071752369554196；hp f0=38.13547087602444, Q=0.5003270373238773（RBJ cookbook 公式）
- 块 400 ms / 步 100 ms；绝对门 −70 LUFS；相对门 =（过绝对门的块的响度均值）− 10 LU；`z = −0.691 + 10·log10(Σ_c G_c · mean_sq)`
- M 窗 400 ms 逐块无门控（滑到尾）、S 窗 3 s；LRA：S 块、绝对门 −70、相对门 −20 LU、10–95 分位差

- [ ] **Step 1: 写失败测试**（关键校准锚点：997 Hz 正弦 @ −23 dBFS 立体声 → I = −23.0±0.1 LUFS；左右同信号比单声道高 3.01 LU；门控：前 2 s −23 dBFS 信号 + 后 2 s −80 dBFS 底噪 → I 基本由前段决定 ±0.5；48k 参数化系数频率响应与 Annex 精确系数响应偏差 <1e-6 dB；True Peak：997 Hz 0.5 幅度正弦 → TP ≈ −6.02±0.15 dBTP；LRA：常响度信号 ≈ 0；PLR = TP − I）

```python
import numpy as np
from repro.bs1770 import (k_weight_biquads, integrated_loudness,
                          momentary_loudness, short_term_loudness,
                          loudness_range, true_peak, plr)

def _sine(f, fs, dur, amp):
    t = np.arange(int(fs*dur))/fs
    return amp*np.sin(2*np.pi*f*t)

def test_calibration_stereo_sine_minus23():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 10.0, 10**(-23/20))]*2)
    assert abs(integrated_loudness(x, fs) - (-23.0)) < 0.1

def test_stereo_identical_plus3_over_mono():
    fs = 48000
    s = _sine(997.0, fs, 10.0, 10**(-23/20))
    m = integrated_loudness(s, fs)
    st = integrated_loudness(np.stack([s, s]), fs)
    assert abs((st - m) - 3.01) < 0.1

def test_gating_drops_quiet_tail():
    fs = 48000
    loud = _sine(997.0, fs, 2.0, 0.5)
    quiet = _sine(997.0, fs, 2.0, 10**(-80/20))
    x = np.stack([np.concatenate([loud, quiet])]*2)
    ref = integrated_loudness(np.stack([_sine(997.0, fs, 4.0, 0.5)]*2), fs)
    assert abs(integrated_loudness(x, fs) - ref) < 0.5

def test_parametric_biquads_match_annex_at_48k():
    fs = 48000
    b, a = k_weight_biquads(fs)
    annex_b = np.array([[1.53512485958697,-2.69169618940638,1.19839281085285],
                        [1.0,-2.0,1.0]])
    annex_a = np.array([[1,-1.69065929318241,0.73248077421585],
                        [1,-1.99004745483398,0.99007225036621]])
    w = np.linspace(1, 24000, 2000)          # 频率响应逐点比对（幅度 dB）
    z = np.exp(1j*2*np.pi*w/fs)
    for i in range(2):
        H_new = np.polyval(b[i], 1/z) / np.polyval(a[i], 1/z)
        H_ref = np.polyval(annex_b[i], 1/z) / np.polyval(annex_a[i], 1/z)
        d = 20*np.log10(np.abs(H_new)+1e-30) - 20*np.log10(np.abs(H_ref)+1e-30)
        assert np.max(np.abs(d)) < 1e-3

def test_momentary_short_term_shapes_and_values():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 8.0, 0.5)]*2)
    m, s = momentary_loudness(x, fs), short_term_loudness(x, fs)
    assert len(m) > len(s) > 0 and abs(m[0] - (-12.2)) < 0.3   # 0.5幅度≈-6dBFS+K≈0

def test_lra_constant_signal_near_zero():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 20.0, 0.3)]*2)
    assert loudness_range(x, fs) < 1.0

def test_true_peak_sine_and_plr():
    fs = 48000
    x = np.stack([_sine(997.0, fs, 5.0, 0.5)]*2)
    tp = true_peak(x, fs)
    assert abs(tp - (-6.02)) < 0.15
    assert abs(plr(x, fs) - (tp - integrated_loudness(x, fs))) < 1e-9
```

- [ ] **Step 2** `cd Repro-ZCode && /c/Users/yaoyue/miniconda3/python.exe -m pytest tests/test_bs1770.py -q` → 全 FAIL（ModuleNotFoundError）
- [ ] **Step 3** 实现 `repro/bs1770.py`：RBJ 双二阶节设计（shelf/highpass）、级联滤波（`scipy.signal.lfilter` 可用则用，否则手写转置直接 II——scipy 在环境里，直接用）、`_block_loudness` 400ms/100ms 滑块 + 门控两遍法、M/S、LRA 分位、True Peak = FFT 零填充 4× 上采样取 max|·|（通道独立取最大）
- [ ] **Step 4** 跑测试 → 全 PASS（校准锚点不过就调 K 计权实现，不许放宽断言）
- [ ] **Step 5** Commit: `feat(repro): BS.1770-4 loudness — K-weighting, gated integrated, M/S, LRA, true peak, PLR`

---

## Task 2: FxLMS 主动降噪（anc）

**Files:**
- Create: `Repro-ZCode/repro/anc.py`
- Test: `Repro-ZCode/tests/test_anc.py`

**Interfaces (Produces):**
- `engine_harmonics(rpm: float, orders: list[float], fs: float, dur_s: float, amp: float, rng) -> np.ndarray`：rpm→基频 f0=rpm/60，逐阶次 `amp/order` 正弦合成
- `fir_apply(x: np.ndarray, h: np.ndarray) -> np.ndarray`（full 卷积截齐）
- `fxlms(x, p_ir, s_ir, mu: float, L: int, s_hat: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]`：返回 `(e, w)`；d = p_ir∗x（初级通路），y = w∗x 经 s_ir 传播，e = d + s_ir∗y，`w[n+1] = w[n] - mu·e[n]·(s_hat∗x)[n-L+1:n+1][::-1]`（反相抵消约定）
- `identify_path(probe, y, L: int) -> np.ndarray`：最小二乘 FIR 辨识（次级通路估计 Ŝ）
- `fxlms_mc(x, P_ir, S_ir, mu, L, s_hat_list)`：2 参考×2 误差点矩阵版（车厂多扬声器形态）

**规范事实：** P/S 用短 FIR（如 P=[0.05,0.9,0.15]、S=[0.6,0.35,0.08]）；音调参考收敛后误差麦克风处降噪 >20 dB；μ 取 0.02–0.05 保证稳定；2×2 版两误差点均 >10 dB。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
from repro.anc import engine_harmonics, fir_apply, fxlms, identify_path, fxlms_mc

def _att_db(e, d):
    return 10*np.log10(np.mean(d**2)/np.mean(e**2))

def test_engine_harmonics_orders_and_f0():
    rng = np.random.default_rng(7)
    fs, rpm = 8000, 2400.0                      # f0 = 40 Hz
    x = engine_harmonics(rpm, [2,3], fs, 2.0, 1.0, rng)
    X = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(len(x), 1/fs)
    for k in (80.0, 120.0):                     # 阶次 2/3 → 80/120 Hz
        assert X[np.argmin(np.abs(f-k))] > 0.5*np.max(X)

def test_fxlms_tonal_attenuation_gt20db():
    rng = np.random.default_rng(3)
    fs = 8000
    x = engine_harmonics(2400.0, [2], fs, 3.0, 1.0, rng)
    p_ir, s_ir = np.array([0.05,0.9,0.15]), np.array([0.6,0.35,0.08])
    d = fir_apply(x, p_ir)
    e, w = fxlms(x, p_ir, s_ir, mu=0.03, L=24, s_hat=s_ir)
    tail = slice(int(1.5*fs), None)             # 收敛后
    assert _att_db(e[tail], d[tail]) > 20.0

def test_secondary_path_mismatch_still_converges():
    rng = np.random.default_rng(5)
    fs = 8000
    x = engine_harmonics(1800.0, [2,4], fs, 3.0, 1.0, rng)
    p_ir, s_ir = np.array([0.1,0.8,0.2]), np.array([0.5,0.4,0.1])
    s_hat = np.array([0.45,0.4,0.12])           # 估计有偏
    d = fir_apply(x, p_ir)
    e, _ = fxlms(x, p_ir, s_ir, mu=0.02, L=32, s_hat=s_hat)
    assert _att_db(e[int(2*fs):], d[int(2*fs):]) > 10.0

def test_identify_path_recovers_fir():
    rng = np.random.default_rng(11)
    fs = 8000
    probe = rng.standard_normal(4000)*0.1
    s_ir = np.array([0.5,0.35,0.1,0.05])
    y = fir_apply(probe, s_ir)
    est = identify_path(probe, y, L=4)
    assert np.allclose(est, s_ir, atol=1e-6)

def test_fxlms_mc_2x2_both_error_mics():
    rng = np.random.default_rng(13)
    fs = 8000
    x = engine_harmonics(2400.0, [2], fs, 3.0, 1.0, rng)
    P = np.array([[0.05,0.9,0.15],[0.1,0.8,0.2]])      # 2 初级通路
    S = np.array([[[0.6,0.35,0.08],[0.3,0.5,0.1]],     # S[m][k]: 误差m←扬声k
                  [[0.4,0.3,0.2],[0.55,0.3,0.05]]])
    E, W = fxlms_mc(x, P, S, mu=0.02, L=16)
    D = np.stack([fir_apply(x, p) for p in P])
    for m in range(2):
        assert _att_db(E[m][int(1.5*fs):], D[m][int(1.5*fs):]) > 10.0
```

- [ ] **Step 2** 跑测试 → FAIL
- [ ] **Step 3** 实现 `repro/anc.py`（向量化逐样本更新循环即可，N~24k 样本纯 Python 循环 <2 s 可接受；fxlms_mc 用 2×2 权重矩阵同构）
- [ ] **Step 4** 跑测试 → PASS
- [ ] **Step 5** Commit: `feat(repro): FxLMS ANC — engine-order reference, secondary-path ID, 2x2 multichannel`

---

## Task 3: 镜像源法仿真 + 环形阵 + 房间采样（sho/ism）

**Files:**
- Create: `Repro-ZCode/repro/sho/__init__.py`、`Repro-ZCode/repro/sho/ism.py`
- Test: `Repro-ZCode/tests/test_ism.py`

**Interfaces (Produces):**
- `circular_array(n_mics: int, radius_m: float) -> np.ndarray`：`(n_mics, 3)` xy 平面均匀圆阵（0° 起 60° 间隔 for n=6）
- `rir_ism(room: tuple[3,float], src: np.ndarray(3), mic: np.ndarray(3), fs: float, absorption: float, max_order: int, rir_len: int | None = None) -> np.ndarray`：能量反射系数 R=√(1−absorption)；每镜像幅度 `R^(|i|+|j|+|k|)/(4πd)`，线性插值分数延迟
- `sample_room(rng) -> dict`：论文区间采样——尺寸 [3,12]×[3,12]×[2,6] m、absorption U(0.2,0.6)、声源/阵列位置均匀且高 1.5 m、朝向角 U[0,360)
- `simulate_multichannel(speech: np.ndarray, room_dict, fs, max_order) -> np.ndarray (C,N)`：对每麦克风生成 RIR 后与 speech 卷积
- `rt60_sabine(room, absorption) -> float`（对照用）

**规范事实：** 论文：房间上述区间、阵 r=4.5 cm 6 麦 60° 间隔、高 1.5 m、镜像阶次 20（**我们默认 max_order=6**：样本量等比缩小后阶次 20 的 RT60≈0.85 s 无需达到，偏差记档）、fs=16 kHz。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
from repro.sho.ism import circular_array, rir_ism, sample_room, simulate_multichannel

FS = 16000

def test_circular_array_geometry():
    m = circular_array(6, 0.045)
    assert m.shape == (6,3) and np.allclose(np.linalg.norm(m[:,:2],axis=1), 0.045)
    ang = np.sort(np.degrees(np.arctan2(m[:,1], m[:,0])) % 360)
    assert np.allclose(np.diff(ang), 60.0, atol=1e-9)

def test_anechoic_rir_is_direct_path_only():
    src, mic = np.array([2.,2.,1.5]), np.array([3.,2.,1.5])
    rir = rir_ism((4,4,3), src, mic, FS, absorption=0.99, max_order=0, rir_len=2048)
    d = float(np.linalg.norm(src-mic)); c = 343.0
    peak = int(np.argmax(rir))
    assert abs(peak - d/ c*FS) <= 1.5
    assert np.isclose(np.max(rir), 1/(4*np.pi*d), rtol=0.2)
    rir[np.maximum(peak-3,0):peak+4] = 0
    assert np.sum(rir**2) < (1/(4*np.pi*d))**2 * 0.05   # 无其他显著能量

def test_more_reflections_more_energy_lower_absorption():
    common = dict(room=(5,4,3), src=np.array([2.,2.,1.5]),
                  mic=np.array([3.5,2.8,1.5]), fs=FS, rir_len=4096)
    e_rev = np.sum(rir_ism(absorption=0.25, max_order=4, **common)**2)
    e_abs = np.sum(rir_ism(absorption=0.55, max_order=4, **common)**2)
    assert e_rev > e_abs*1.5

def test_sample_room_paper_ranges():
    rng = np.random.default_rng(42)
    r = sample_room(rng)
    for i,lo,hi in ((0,3,12),(1,3,12),(2,2,6)):
        assert lo <= r["room"][i] <= hi
    assert 0.2 <= r["absorption"] <= 0.6
    assert r["src"][2] == 1.5 and r["array_center"][2] == 1.5
    assert 0 <= r["orientation_deg"] < 360 and len(r["mics"]) == 6

def test_simulate_multichannel_shape_and_delay():
    rng = np.random.default_rng(1)
    speech = rng.standard_normal(16000)*0.1
    rd = sample_room(rng)
    y = simulate_multichannel(speech, rd, FS, max_order=2)
    assert y.shape[0] == 6 and y.shape[1] >= 16000
```

- [ ] **Step 2** FAIL → **Step 3** 实现（镜像偏移向量化：`i,j,k ∈ [−O..O]`，Le/Te/Re 墙面镜像坐标公式；`np.add.at` 累积 RIR；分数延迟线性插值）
- [ ] **Step 4** PASS → **Step 5** Commit: `feat(repro): Allen-Berkley ISM room sim + 6-mic circular array per 2607.02129`

---

## Task 4: 伪语音 + 指向性声源（sho/speech）

**Files:**
- Create: `Repro-ZCode/repro/sho/speech.py`
- Test: `Repro-ZCode/tests/test_speech.py`

**Interfaces (Produces):**
- `synth_speech(dur_s: float, fs: int, rng) -> np.ndarray`：f0 120–220 Hz 带漂移轮廓 + 15 次谐波（幅度 1/k）+ 3 个共振峰带通（scipy.signal）+ 音节包络（2–5 Hz）+ 静音段；峰值归一 −6 dBFS
- `directivity_gain(theta_rad: float, a: float, b: float) -> float`：cardioid 族 `a + b*cos(theta)`，`(a,b)` 由 rng 每语句采（替代论文 22 条实测 VDP——偏差记档）
- `oriented_room_dict(rng)`：`sample_room` + `directivity (a,b)`（约束 a∈[0.3,0.7]、a+b=1 前向无衰减）

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
from repro.sho.speech import synth_speech, directivity_gain, oriented_room_dict

FS = 16000

def test_speech_seedable_and_speechlike():
    s1 = synth_speech(2.0, FS, np.random.default_rng(9))
    s2 = synth_speech(2.0, FS, np.random.default_rng(9))
    assert s1.shape == (32000,) and np.array_equal(s1, s2)
    assert np.max(np.abs(s1)) <= 10**(-6/20) + 1e-9
    # 谱重心显著低于白噪声（有低频谐波结构）
    S = np.abs(np.fft.rfft(s1)); f = np.fft.rfftfreq(len(s1), 1/FS)
    assert np.sum(f*S)/np.sum(S) < FS/4

def test_directivity_front_stronger_than_back():
    assert directivity_gain(0.0, 0.5, 0.5) == 1.0
    assert directivity_gain(np.pi, 0.5, 0.5) == 0.0
    assert directivity_gain(np.pi, 0.7, 0.3) > directivity_gain(2.5, 0.7, 0.3)

def test_oriented_room_dict_has_vdp():
    rd = oriented_room_dict(np.random.default_rng(2))
    assert {"a","b"} <= set(rd["directivity"].keys())
```

- [ ] **Step 2** FAIL → **Step 3** 实现 → **Step 4** PASS
- [ ] **Step 5** Commit: `feat(repro): pseudo-speech synth + cardioid-family VDP substitute`

---

## Task 5: STFT 相位特征（sho/features）

**Files:**
- Create: `Repro-ZCode/repro/sho/features.py`
- Test: `Repro-ZCode/tests/test_features.py`

**Interfaces (Produces):**
- `stft_phase_features(x: np.ndarray (C,N), fs: int) -> np.ndarray (2C, T, 128)`：Hann 窗 4 ms（64 样本 @16k）、步 2 ms（32）、nfft=256 零填充、rfft 相位 → 每 ch `[sin, cos]` 交错堆叠、丢 DC bin → F=128（论文口径 F=128；nfft=256 的 129 bin 去掉 DC 的工程决定，docstring 记档）
- `angular_mae(theta_true_deg, theta_pred_deg) -> float`：环形误差 `min(|Δ|, 360−|Δ|)` 均值（论文公式）

**规范事实：** 论文 4 ms/2 ms 窗、sin/cos 表示避 ±π 断续、输入 `2C×T×F`、F=128、C=6 → 12×T×128。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
from repro.sho.features import stft_phase_features, angular_mae

FS = 16000

def test_feature_shape_2CxTxF128():
    x = np.random.default_rng(0).standard_normal((6, 16000))*0.1
    f = stft_phase_features(x, FS)
    assert f.shape[0] == 12 and f.shape[2] == 128
    assert f.shape[1] == (16000-64)//32 + 1

def test_known_delay_linear_phase():
    n = np.arange(16000)/FS
    base = np.sin(2*np.pi*500*n)
    tau = 4/FS                                   # 4 样本延迟
    delayed = np.concatenate([np.zeros(4), base[:-4]])
    x = np.stack([base, delayed])
    f = stft_phase_features(x, FS)
    k = np.arange(1, 129)                        # 丢 DC 后 bin 1..128
    expected = -2*np.pi*k*4/256                  # nfft=256
    s0, c0 = f[0], f[1]; s1, c1 = f[2], f[3]     # ch0 sin/cos, ch1 sin/cos
    dphi = np.arctan2(s1, c1) - np.arctan2(s0, c0)
    keep = np.abs(expected) < np.pi              # 仅无混叠低频 bin
    err = np.abs(np.angle(np.exp(1j*(dphi[keep]-expected[keep]))))
    assert np.mean(err) < 0.1

def test_angular_mae_wraparound():
    assert angular_mae([359.0],[1.0]) == 2.0
    assert angular_mae([90.0],[90.0]) == 0.0
    t = np.full(100, 0.0); p = np.random.default_rng(1).uniform(0,360,100)
    assert 70 < angular_mae(t, p) < 110          # 随机≈90°
```

- [ ] **Step 2** FAIL → **Step 3** 实现（`np.fft.rfft` 滑窗批处理：`libframes = sliding_window_view(x, 64)[::32]`）→ **Step 4** PASS
- [ ] **Step 5** Commit: `feat(repro): STFT phase sin/cos features (2C×T×128) + circular MAE`

---

## Task 6: 扩散场噪声（sho/noise）

**Files:**
- Create: `Repro-ZCode/repro/sho/noise.py`
- Test: `Repro-ZCode/tests/test_noise.py`

**Interfaces (Produces):**
- `diffuse_noise(n_samples: int, mic_positions: np.ndarray, fs: int, rng, spectral_shape=np.ndarray|None) -> np.ndarray (C,N)`：STFT 域逐 bin 生成 C 路独立复高斯 → Cholesky(L(f)) 混合到目标相干 `Γ_ij(f)=sinc(2πf·d_ij/c)`（sinc 归一 `sin(x)/x`）→ ISTFT；spectral_shape 可给伪语音谱包络
- `measure_coherence(x: np.ndarray (C,N)) -> np.ndarray (C,C,F)`（验证用）

**规范事实：** 论文噪声合成"phase-randomizing uncorrelated copies … under isotropic diffuse field assumptions, following [31,32]"——sinc 相干模型即各向同性扩散场双麦相干（论文口径）。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np
from repro.sho.noise import diffuse_noise, measure_coherence
from repro.sho.ism import circular_array

FS = 16000

def test_coherence_matches_sinc():
    mics = circular_array(6, 0.045)
    x = diffuse_noise(8*FS, mics, FS, np.random.default_rng(3))
    assert x.shape == (6, 8*FS)
    C = measure_coherence(x)
    f = np.fft.rfftfreq(1024, 1/FS)
    d01 = np.linalg.norm(mics[0]-mics[1]); c = 343.0
    idx = (f > 200) & (f < 3000)                 # sinc 有效的中频带
    est = np.abs(C[0,1,idx])
    tgt = np.abs(np.sinc(2*f[idx]*d01/c))
    assert np.mean(np.abs(est-tgt)) < 0.15

def test_coherence_unity_at_dc_and_falling():
    mics = circular_array(2, 0.045)
    x = diffuse_noise(8*FS, mics, FS, np.random.default_rng(4))
    C = measure_coherence(x)
    assert C[0,1,0] > 0.95
    f = np.fft.rfftfreq(1024, 1/FS)
    assert C[0,1,np.argmin(np.abs(f-4000))] < C[0,1,np.argmin(np.abs(f-500))]
```

- [ ] **Step 2** FAIL → **Step 3** 实现（逐 bin 构造 Γ 矩阵 → `np.linalg.cholesky`，bin 间共用可分带降开销；ISTFT 用 hann 分析/综合重叠相加）→ **Step 4** PASS
- [ ] **Step 5** Commit: `feat(repro): isotropic diffuse-field noise via sinc coherence Cholesky mixing`

---

## Task 7: 头部朝向模型（sho/model，torch）

**Files:**
- Create: `Repro-ZCode/repro/sho/model.py`
- Test: `Repro-ZCode/tests/test_model.py`

**Interfaces (Produces):**
- `class ShoNet(torch.nn.Module)`：`__init__(n_mics: int = 6)`；`forward(x: Tensor(B, 2C, T, 128)) -> Tensor(B, 2)` 输出 `(cosθ, sinθ)`
  - 精确论文架构（Fig.1）：Conv2d(2C→64, 3×3, pad 1)+ReLU+MaxPool(5,4) → Conv2d(64→64)+ReLU+MaxPool(1,4) → Conv2d(64→64)+ReLU+MaxPool(1,2) → reshape `(B, T/5, 64·4=256)` → BiGRU(128)×2 → MHSA(128, 8 heads)+残差+LayerNorm ×2 → AdaptiveMaxPool1d(1) → FC 128 → FC 128→2
- `predict_degrees(model, feats) -> np.ndarray`：atan2·180/π mod 360
- `class AngleDataset(torch.utils.data.Dataset)`：`(feeds, theta_deg)` 对

**规范事实：** MSE 损失 on (cosθ,sinθ)、Adam lr=4e-4 线性衰减（我们按 iter 数等比缩距）；论文 MAE：模拟 clean 19.9°、个人化最优 11.3°（不作为断言阈值，只作报告参照）。

- [ ] **Step 1: 写失败测试**

```python
import numpy as np, torch
from repro.sho.model import ShoNet, predict_degrees

def test_forward_shape_and_small():
    torch.manual_seed(0)
    m = ShoNet(n_mics=6)
    x = torch.randn(2, 12, 100, 128)
    y = m(x)
    assert y.shape == (2, 2)
    n = sum(p.numel() for p in m.parameters())
    assert n < 2_000_000                       # 轻量（GRU+MHSA 128 维）

def test_output_unit_circle_and_degrees():
    torch.manual_seed(0)
    m = ShoNet(n_mics=6).eval()
    y = m(torch.randn(3, 12, 60, 128))
    deg = predict_degrees(m, np.random.default_rng(0).standard_normal((3,12,60,128)).astype(np.float32))
    assert deg.shape == (3,) and np.all((deg >= 0) & (deg < 360))
```

- [ ] **Step 2** FAIL → **Step 3** 实现（MHSA 块 = `nn.MultiheadAttention(128, 8, batch_first=True)` + 残差 + `nn.LayerNorm`）→ **Step 4** PASS
- [ ] **Step 5** Commit: `feat(repro): ShoNet — paper Fig.1 CNN+BiGRU+MHSA orientation regressor`

---

## Task 8: PhaseCoder 几何无关编码（phasecoder）

**Files:**
- Create: `Repro-ZCode/repro/phasecoder.py`
- Test: `Repro-ZCode/tests/test_phasecoder.py`

**Interfaces (Produces):**
- `spherical_from_cartesian(mic_positions (M,3)) -> (r (M,), az (M,), el (M,))`：相对阵列质心
- `mic_geometry_embedding(mic_positions, nfft: int = 256, fs: int = 16000, d_model: int = 64) -> np.ndarray (M, nfft//2+1, d_model)`：三路拼接（文章口径）——①序列位置编码（麦序 sin/cos）②时间帧/频率位置编码 ③**球坐标相位调制**：`φ_m(f) = -2π f/c · r_m · cos(el_m) · cos(az_m - φ_sweep(f))` 按正弦扫描方向逐 bin 调制 → sin/cos(φ) 展开
- `mag_phase_patch_features(x (C,N), fs, patch_t: int = 8, patch_f: int = 16) -> np.ndarray (n_patches, patch_t·patch_f·2)`：STFT 幅度+相位（sin/cos）按 patch 展平（文章"magnitude+phase patches"）
- `output_heads_meta() -> dict`：`{"azimuth": 38, "distance": 13, "elevation": 18, "embedding": 256}`（README 实测口径）

**执行期对齐步骤（先于实现）：** `git clone --depth 1 https://github.com/google-deepmind/phasecoder var/phasecoder-src`（克隆失败→回退按文章描述实现，docstring 记"未对齐源码"）；读 `phasecoder_jax/` 中 `arbitrary_mic_geometry_embeddings` 与 `utils.get_mag_phase_features`，**用其真实公式替换上方占位数学**；测试随之以真实公式的不变量为准（形状/旋转等变性/变麦数）。

- [ ] **Step 1: 克隆 + 读源码，把真实编码公式抄进本任务实现块（更新本文件此节）**
- [ ] **Step 2: 写失败测试**

```python
import numpy as np
from repro.phasecoder import (spherical_from_cartesian, mic_geometry_embedding,
                              mag_phase_patch_features, output_heads_meta)
from repro.sho.ism import circular_array

FS = 16000

def test_spherical_centroid_relative():
    p = circular_array(6, 0.045)
    r, az, el = spherical_from_cartesian(p)
    assert np.allclose(r, 0.045, atol=1e-9) and np.allclose(el, 0.0, atol=1e-9)

def test_embedding_shape_var_mics():
    for M in (3, 5, 8):
        rng = np.random.default_rng(M)
        p = rng.uniform(-0.09, 0.09, (M, 3))
        e = mic_geometry_embedding(p, nfft=256, fs=FS)
        assert e.shape[0] == M and e.shape[1] == 129 and e.shape[2] > 0

def test_rotation_equivariance():
    p = circular_array(6, 0.045)
    ang = np.deg2rad(30.0)
    R = np.array([[np.cos(ang),-np.sin(ang),0],[np.sin(ang),np.cos(ang),0],[0,0,1]])
    e1 = mic_geometry_embedding(p, nfft=256, fs=FS)
    e2 = mic_geometry_embedding(p @ R.T, nfft=256, fs=FS)
    assert np.allclose(e1, e2, atol=1e-6)      # 圆阵+绝对角度编码→旋转=麦序重排，集合等变

def test_patch_features_shape():
    x = np.random.default_rng(6).standard_normal((4, FS)).astype(np.float32)
    f = mag_phase_patch_features(x, FS, patch_t=8, patch_f=16)
    assert f.ndim == 2 and f.shape[1] == 8*16*2 and f.shape[0] > 10

def test_heads_meta_matches_repo_readme():
    h = output_heads_meta()
    assert h["azimuth"] == 38 and h["distance"] == 13 and h["elevation"] == 18
```

- [ ] **Step 3** FAIL → **Step 4** 实现 → **Step 5** PASS → **Step 6** Commit: `feat(repro): PhaseCoder geometry-agnostic mic-position phase-modulation encoding (aligned to JAX source)`

---

## Task 9: 端到端复现实验脚本 + 快速训练冒烟测试

**Files:**
- Create: `Repro-ZCode/scripts/run_sho_repro.py`、`Repro-ZCode/scripts/run_repro_all.py`
- Test: `Repro-ZCode/tests/test_model.py` 追加（`@pytest.mark.slow`）

**Interfaces (Consumes):** Task 3–7 全部。**Produces:** `var/sho_metrics.json`（train MAE / test MAE / 随机基线 90° / per-10°-bin MAE）、`var/sho_mae_by_bin.png`。

- [ ] **Step 1: 冒烟测试（标记 slow，默认跑，全量 ~2 min）**

```python
@pytest.mark.slow
def test_quick_train_beats_random():
    """80 语句模拟集（order 4）/ 300 步 / CPU：held-out MAE 显著优于随机 90°。"""
    from repro.sho.speech import synth_speech, oriented_room_dict
    from repro.sho.ism import simulate_multichannel
    from repro.sho.features import stft_phase_features, angular_mae
    from repro.sho.model import ShoNet
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(2026)
    feats, angs = [], []
    for i in range(80):
        s = synth_speech(1.5, 16000, rng)
        rd = oriented_room_dict(rng)
        y = simulate_multichannel(s, rd, 16000, max_order=4)
        feats.append(stft_phase_features(y[:, :24000], 16000))
        angs.append(rd["orientation_deg"])
    T = min(f.shape[1] for f in feats)
    X = np.stack([f[:, :T] for f in feats]).astype(np.float32)
    Y = np.array(angs, dtype=np.float32)
    model = ShoNet(6); opt = torch.optim.Adam(model.parameters(), lr=4e-4)
    for step in range(300):
        idx = rng.integers(0, len(X), 16)
        xt = torch.from_numpy(X[idx]); th = torch.from_numpy(np.deg2rad(Y[idx]))
        yt = torch.stack([torch.cos(th), torch.sin(th)], -1)
        loss = torch.mean((model(xt) - yt) ** 2)
        opt.zero_grad(); loss.backward(); opt.step()
    pred = predict_degrees(model, X[64:])
    mae = angular_mae(Y[64:], pred)
    assert mae < 70.0        # 保守阈：显著优于随机 90°（论文 19.9° 需 40k 样本×200k 步）
```

- [ ] **Step 2** FAIL（训练不收敛/报错）→ **Step 3** 实现 `run_sho_repro.py`（argparse：n_utt/iters/max_order；流程=采房→伪语→ISM→特征→训练→评测→JSON+PNG 分桶图）与 `run_repro_all.py`（跑四模块各一条代表性命令并汇总 exit code）
- [ ] **Step 4** 跑 slow 测试 + `scripts/run_sho_repro.py --n-utt 120 --iters 400` 全 PASS/出图
- [ ] **Step 5** Commit: `feat(repro): end-to-end SHO repro runner — sim→features→train→MAE-by-bin artifact`

---

## Task 10: 复现报告 + 索引 + 发版 v0.8.0

**Files:**
- Modify: `docs/research/2026-10-05-four-article-repro.md`（补"实际复现结果"节：各测试数、SHO 冒烟 MAE、与论文数字对照表、诚实偏差清单）
- Modify: `Repro-ZCode/README.md`（结果表）、`docs/research/INDEX.md`（+1 行）、`README.md` §10.1 表（+1 行）+ 测试规模行（复现区 N 项）

**Steps:**

- [ ] **Step 1** 全量测试：`cd Repro-ZCode && pytest -q` + 主库 `pytest tests/ -q`（356）双绿
- [ ] **Step 2** 写报告：每来源"复现了什么（文件/测试锚点）/ 数字对照 / 没复现什么+为什么"；SHO 表格列 论文值 vs 本复现值（19.9° vs 冒烟值、11.3° vs 未做全量个性化——冒烟级只跑协议代码路径）
- [ ] **Step 3** INDEX/README 行接入；`git add -A && git commit -m "docs(repro): four-source repro report — tests, paper-vs-repro table, honest deviations"`
- [ ] **Step 4** 发版：`python scripts/release.py --dry-run` → 确认推导 0.8.0 → `--apply` → CHANGELOG 段落润色 → `git commit -m "chore(release): v0.8.0"` → `git tag -a v0.8.0` → `git push origin master --tags`
- [ ] **Step 5** gh Release 页（`gh` 不可用则给手动 URL 清单）；GitHub 仓库页 `Repro-ZCode/` 目录可见性确认

---

## Self-Review 结论

- **覆盖**：四来源全部有对应 Task；论文五要素（特征/仿真/模型/评测/个性化协议）→ Task 5/3·4·6/7/9；PhaseCoder 三编码→Task 8；FxLMS 全家→Task 2；BS.1770 全家→Task 1。缺口语：论文的"真实数据集[3]评估"（DoV 数据集公开但下载+8 分类微调超范围，记入不可复现清单）。
- **占位符**：Task 8 的编码公式是**文章口径占位**，Step 1 明确要求执行期用克隆源码的真实公式替换后再写测试——这是有意的设计（防止我此刻凭二手文章臆造公式）。
- **类型一致性**：`stft_phase_features` 输出 `(2C,T,128)` 被 Task 7 `ShoNet(2C=12)` 与 Task 9 消费；`oriented_room_dict`/`simulate_multichannel`/`angular_mae` 跨 Task 3/4/5/9 签名一致。

---

## 增补 Task 11-13（2026-10-05 第二批：来源⑤⑥）

**来源：** ⑤[微信·Pipecat](https://mp.weixin.qq.com/s/viuSMBiWZIQtAloMBeE9bQ)（Daily 团队语音 Agent 框架，BSD-2，15k★）⑥[微信·C++ unique_lock](https://mp.weixin.qq.com/s/4nvqU7EZr1GhxZpuBDRptA)

**可复现判定：** ⑤不装 pipecat（conda 红线），用纯 asyncio 复现其**架构内核**——帧分类（SystemFrame 立即处理/打断不清空 vs DataFrame 排队/打断清空）、InterruptionFrame 穿管作废、全程流式、assistant 聚合器放 output 之后（只记实际播出的内容）、HandoffGuard 自定义处理器模式。⑥laos 是 Python 项目，复现 unique_lock 的**语义**（RAII 自动释放 + 手动提前 unlock + defer_lock + try_lock + owns_lock）。

### Task 11: `repro/framepipe.py` — Pipecat 帧管道架构复现（来源⑤）
- 接口：`Frame/SystemFrame/DataFrame/InterruptionFrame/TranscriptionFrame/LLMTextFrame/TTSAudioFrame/TTSSpeakFrame/MetricsFrame`；`FrameProcessor.process_frame/push_frame(direction)`；`Pipeline(processors).run()`；`SourceProcessor/SinkCollector`
- 测试断言（TDD 先行）：①打断后 Sink 不再收到排队的 DataFrame，但 SystemFrame（Metrics）照常穿管；②流式：Sink 在 LLM 还没生成完就收到第一段 TTS 输出；③聚合器在 output 之后：被打断的半句话不进上下文；④HandoffGuard：命中关键词吞帧+直接注入播报帧，LLM 收不到该帧；⑤上下游方向都通
### Task 12: `repro/locks.py` — unique_lock 语义复现（来源⑥）
- 接口：`UniqueLock(lock, defer_lock=False)`：`__enter__/__exit__/lock()/unlock()/try_lock()/owns_lock`
- 测试断言：①作用域结束自动释放；②提前 unlock 后块内剩余部分不再持锁（他线程 acquire(blocking=False) 成功）；③defer_lock 进入时不持锁；④try_lock 两条路径；⑤未持锁 unlock → RuntimeError；⑥owns_lock 状态翻转
### Task 13: 报告增补（⑤⑥两节学习笔记+复现结果）+ INDEX/README 行 + 发版（feat→MINOR）
