# 四来源知识学习与复现报告（头部朝向 / PhaseCoder / 车载 ANC / LUFS）

> 日期：2026-10-05 ｜ 类型：学习 + 复现 ｜ 实现区：`Repro-ZCode/`（零主代码改动）
> 来源：①[微信·STFT 相位头部朝向](https://mp.weixin.qq.com/s/AjVIIA6DZ-2RXJ2m7tT1Hw) + 论文 PDF（arXiv 2607.02129v1，Tampere，5 页全文） ②[微信·PhaseCoder](https://mp.weixin.qq.com/s/2LW0r534oYFb9ZFP8NvTwA)（[google-deepmind/phasecoder](https://github.com/google-deepmind/phasecoder)，ICML 2026，arXiv 2601.21124） ③[微信·车载主动降噪厂商集锦](https://mp.weixin.qq.com/s/nxRfX224KKmaLBweiKV6IQ) ④[微信·dB/RMS/LUFS/True Peak](https://mp.weixin.qq.com/s/nV_JJv_SlFIUWNWXS6jvSQ)

## §0 一句话

四个知识源里**可复现的全部落进 `Repro-ZCode/`**：论文①的完整管线（镜像源法房间仿真 + 6 麦环形阵 + STFT 相位特征 + CNN-BiGRU-MHSA 模型 + 环形 MAE 评测 + 个性化协议代码路径）、②的几何无关麦位相位调制编码（对齐 DeepMind JAX 源码）、③的 FxLMS 主动降噪（阶次参考 + 次级通路辨识 + 2×2 多通道）、④的 BS.1770-4 全套响度计量（K 计权/门控积分/M/S/LRA/True Peak/PLR）。

## 来源→复现物映射

| 来源 | 能复现 | 不能复现（及替代/理由） |
|---|---|---|
| ① 头部朝向论文 | STFT 相位特征（4ms/2ms/F=128，sin/cos 表示）；Allen-Berkley 镜像源法 3D 仿真（房间区间/吸收系数/1.5m 高度照论文）；6 麦 r=4.5cm 环形阵；声源指向性；各向同性扩散场噪声（sinc 相干）；模型全架构（3×Conv+2×BiGRU+2×MHSA+AdaMaxPool+cos/sin 头）；MSE+Adam 4e-4；环形 MAE；个性化（Room-only/Speaker-only/Speaker+Room）协议代码路径；10° 分桶误差图 | 论文数字本身（40,295 语句×200k 步 → 等比缩到百语句×数百步，冒烟验证管线而非复现 19.9°/11.3°）；22 条实测 VDP → cardioid 族 a+b·cosθ 替代；VCTK → 自造伪语音（f0 轮廓+谐波+共振峰+音节包络）；WHAM → 自造扩散噪声；Silero 级 VAD → 能量裁剪；镜像阶次 20 → 默认 6；DoV 真实数据集[3] 8 分类微调（数据集下载+协议超范围） |
| ② PhaseCoder | 克隆官方仓库读 JAX 源码 → numpy 复现 `arbitrary_mic_geometry_embeddings`（球坐标相位调制）与 `get_mag_phase_features`（幅度+相位补丁）；输出头口径（az 38 / dist 13 / el 18 / emb 256）；变麦数 3-8、旋转等变性测试 | 1.5M RIR 两阶段课程预训练；checkpoint 推理（JAX 缺失且不装包）；Gemma 3n 集成；空间转录/定向转录任务 |
| ③ 车载 ANC | 发动机阶次信号合成（rpm→阶次谐波）；单通道 FxLMS（初级/次级通路 FIR、收敛后 >20dB 降噪断言）；次级通路最小二乘辨识；估计失配鲁棒性；2×2 多通道 FxLMS | 厂商数字（Bose 3-6dB、歌尔 11.2dB(A)、ADI 2ms 等——营销口径，仅作锚点记档）；真车 DSP/传感器工程 |
| ④ LUFS/True Peak | BS.1770-4 K 计权（48k Annex 精确系数 + 任意 fs 参数化双实现互验）；门控积分响度（400ms/100ms、-70 绝对门、-10 相对门）；997Hz 校准锚点测试；Momentary/Short-term；LRA（EBU 3342：-20 LU 相对门、10-95 分位）；True Peak（4× FFT 过采样）；PLR | ——（核心概念全部可规范复现） |

## 逐来源学习笔记（关键机制）

### ① 说话人头部朝向（arXiv 2607.02129v1, Turi/Politis/Sudarsanam/Virtanen）

- **任务**：单说话人 0–360° 水平朝向估计，输入一段多通道语音，输出一个角度（静态假设）。应用：智能家居指令定向、会议 addressee 识别、驾驶员注意力监测。
- **核心洞见**：STFT **相位**携带指向性信息（短窗 2–4ms 时相位信息最丰富——跟随 [21]）；用 sin/cos 表示避 ±π 断续；幅度特征无增益。混响**反而有益**（早期反射提供朝向依赖的相位结构；消声室下 ±90° 侧向模糊），而 ITD/ILD 类手工特征怕混响。
- **管线**：VAD 裁头尾 → 每通道 STFT（Hann 4ms/2ms）→ 相位 sin/cos → 堆叠 `2C×T×128`（C=6 麦）→ 3×Conv2d(64,3×3)+MaxPool(5×4/1×4/1×2) → reshape `T/5×256` → 2×BiGRU(128) → 2×MHSA(8 头)+残差+LayerNorm → AdaptiveMaxPool → FC → `(cosθ,sinθ)`。
- **仿真**：22 条实测声源指向性 VDP × VCTK；房间 [3,12]×[3,12]×[2,6]m、吸收 0.2-0.6、散射 0.1-0.5；声源/阵列随机位、高 1.5m；6 麦环形 r=4.5cm@60°；Pyroomacoustics ISM 阶次 20（RT60≈0.85s）；最长 3s。噪声：WHAM 单声道 → 相位随机化不相关副本 → 混合到各向同性扩散场目标相干（[31,32]）。
- **结果**：模拟 clean MAE 19.9°（vs 原始波形+CNN 44.8°、ITD/ILD 52.7°）；个性化：Room-only 17.6° / Speaker-only 14.2° / Speaker+Room 11.3°（**说话人个性 > 房间个性**——个体指向性差异大）；真实数据 8 分类 73.2%（预训练+微调）> 只用真实 62.6% > DoV 基线 65.4%。
- **对 laos 的启示**：朝向=指令定向（"你在跟我说话吗"）的廉价声学代理；6 麦 r=4.5cm 环形阵正是智能音箱/手表形态；与 laos 四段漏斗的第①②层（常驻检测+触发）天然衔接。

### ② PhaseCoder（Google DeepMind + MIT, ICML 2026）

- **问题**：多模态 LLM"听声辨位"，但现有空间音频前端绑定特定阵列几何（训练时的麦位固化进权重），换阵列即失效。
- **做法**：6M 参数几何无关编码器——输入原始多通道音频 + 麦克风笛卡尔坐标（米），STFT 幅度+相位补丁化，**三路固定位置编码**（麦克风序列/时间帧/麦克风球坐标相位调制——第三路把几何信息直接以物理相位形式注入），5 层 Transformer + [CLS]，输出 az（38 类含无源）/dist（13 类 0.1-6m）/el（18 类）softmax + 256 维空间嵌入，可插 Gemma 3n。
- **数据**：全合成——1.5M RIR、4M 条 250ms 片段、3-8 麦半径 7-18cm 随机阵、Freesound 噪声 -5~15dB SNR、两阶段课程（先易后难）。
- **对 laos 的启示**：`mcp` 驱动生态里"几何无关"= 同一驱动跨设备复用（手表/音箱/车机不同麦位共用一个空间前端）；球坐标相位调制是"物理先验进位置编码"的范例。

### ③ 车载主动降噪厂商集锦

- **机制光谱**：EOC（发动机阶次，参考 RPM/CAN 信号，确定性前馈）< RNC（路噪，加速度计参考，宽带前馈）< ESS/AVAS（电动声浪合成）。
- **共同算法底座**：FxLMS（filtered-x least mean squares）——参考信号 x 经自适应滤波器 W 产生反相声波，误差麦克风 e 校正，滤波路径 Ŝ 补偿次级通路（扬声器→误差麦）相位滞后。
- **厂商锚点**（营销口径，记档不复现）：Bose RNC 4 加速度计 3-6dB 平均/10-15dB 峰值；歌尔 AI-RNC 端到端 11.2dB(A)（50+ 场景识别、<1s 收敛、虚拟传感）；ADI RANC 2ms/-3dB；Silentium 30Hz-1kHz >5dB(A)；华研 7dB(A) OA/20dB 峰值/1ms；拾音科技 ENC 免硬件（RPM 经 CAN）、每阶次 >10dB 峰值、<200µs 周期。
- **对 laos 的启示**：车内是"全天候音频+强制隔离"的又一落地域；加速度计参考=传感器即参考信号（无需声学参考）的设计思想。

### ④ dB / RMS / LUFS / True Peak

- **三把尺**：Peak=瞬时最高（削波风险）；RMS=短期能量（"整体多强"）；LUFS=K 计权+门控的响度（"听感多响"，流媒体分发标准 -14 LUFS）。
- **BS.1770-4 细节**：K 计权=高频搁置（+4dB@~1.7kHz，模仿头/耳传递）+ 高通 38Hz；块 400ms/步 100ms；绝对门 -70 LUFS + 相对门（均值-10LU）；M=400ms 滑窗、S=3s 滑窗；LRA=过 -20LU 相对门的 S 块 10-95 分位差；True Peak=4× 过采样重构峰值（样本峰会低估 intersample peak）；PLR=TP−I（响度战争度量）。
- **对 laos 的启示**：journal/录音留档的响度归一化口径；AGC 目标该用 LUFS 而非 RMS；PLR 可作"录音动态健康"指标进日记。

## 实际复现结果

（Task 10 收尾时填写：测试计数、SHO 冒烟 MAE vs 论文 19.9°、偏差清单终版）
