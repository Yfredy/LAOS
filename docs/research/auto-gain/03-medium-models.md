# 中型神经网络档（30M–500M）—— 预期稀疏，结论：确实稀疏

> 本文件是 `docs/research/auto-gain/` 的**中型档**（参数量 30M–500M，左闭右开）。
> 表格 schema 由 `scripts/check_agc_table.py` 机器校验（12 列，规则 g/h/i/j + 通用 6 条）。
> 口径来源：`00-taxonomy-and-metrics.md`。

**一句话定位**：在 30M–500M 区间内，**没有任何以「增益控制 / 响度控制」为主业的神经模型**。
本档收录的 4 条记录全部是**语音分离**（相邻领域），按 `00` 控制对象枚举必须标 `非AGC(相邻：分离)`。
这**印证了** `00` 的预期假设（中型档稀疏，不得为凑数灌水），**未推翻**它，故不向 `00` 追加裁定。

---

## 主表：中型神经网络（30M–500M，均为相邻领域）

| 模型 | 版本/形态 | 参数量(M) | 输入 | 控制对象 | 作用点 | 基准 | 指标 | 许可 | 可得 | edge | 来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MossFormer2 (S) | 神经·Transformer + FSMN | 37.8 | 16kHz（时域） | 非AGC(相邻：分离) | 离线 | WSJ0-2mix | SI-SDRi 23.2 dB (WSJ0-2mix) | Apache-2.0 | yes | unknown(未找到端侧转换案例) | https://github.com/modelscope/MossFormer2（arXiv:2312.11825） |
| MossFormer2 | 神经·Transformer + FSMN | 55.7 | 16kHz（时域） | 非AGC(相邻：分离) | 离线 | WSJ0-2mix | SI-SDRi 24.1 dB (WSJ0-2mix) | Apache-2.0 | yes | unknown(未找到端侧转换案例) | https://arxiv.org/abs/2312.11825 |
| MossFormer | 神经·Transformer | 42.1 | 16kHz（时域） | 非AGC(相邻：分离) | 离线 | WSJ0-2mix | SI-SDRi 22.8 dB (WSJ0-2mix) | Apache-2.0 | yes | unknown(未找到端侧转换案例) | https://arxiv.org/abs/2212.05771 |
| SFSRNet | 神经·分离 + 超分 | 59.0 | 16kHz | 非AGC(相邻：分离) | 离线 | WSJ0-2mix | SI-SDRi 24.0 dB (WSJ0-2mix) | 未明示 | yes | unknown(未找到端侧转换案例) | https://github.com/arda-num/SFSRNet（AAAI22 复现仓库） |
**表数核对**：本表 1 张、4 行 schema 记录。校验器打印应一致（GC 3）。

---

## §1. 稀疏判定：稀疏，且与预期一致

- **条目数**：4 条，全部标 `非AGC(相邻：分离)`，无一条是增益/响度控制主业。
- **为什么没有更多**：增益与增强是低层信号处理，精度在几十 M 参数量内已饱和
  （见 `02-small-models.md`：RNNoise 0.085M、DTLN 0.243M、DeepFilterNet2 2.0M 已是实时增强的甜点）；
  再往上堆参数，收益落在**分离 / 生成**等相邻任务，不在「增益控制」。
- **实时性约束先于精度触顶**：本档 4 条全是离线 / GPU 推理（MossFormer2 RTF 0.036–0.053 是在 V100 上测的，
  CPU 上远非实时），与 laos 常驻链路完全不搭。它们出现在中型档只是因为分离任务天然需要更大容量，
  **不是因为增益任务需要**。

---

## §2. 本档对 landscape 的含义

- 在 `2026-09-landscape.md` 的交叉表里，中型档（神经）这一行**只有相邻领域占位**，不贡献任何「增益控制」条目。
- 增益控制的真实选项仍只在两处：经典 DSP（`01-classical-dsp.md`）与小型神经增强（`02-small-models.md` 的降噪掩码）。
  中型档的空缺进一步支持 `00` 的结论：AGC 不是「模型越大越好」的问题。

---

## §3. 自检与疑虑

1. **校验器覆盖**：主表首列 `模型`，不会被 `table_lint` 静默跳过；已核表数 = 记录数 = 4。
2. **未追加 00 裁定**：稀疏结论与 `00` 预期假设一致，按 Ruling 不追加（只有「证伪」才追加，见 `06-multimodal.md` 裁定 2）。
3. **未二次核实项**：① SFSRNet 许可仓库未明示单一 LICENSE，标 `未明示`；
   ② MossFormer2 端侧 RTF 仅见 GPU 数字，CPU 实时性标 `unknown(未找到端侧转换案例)`；
   ③ MossFormer 的 arXiv 编号按公开记录填 2212.05771（Transformer 版），未逐页复核。
4. **跨任务类型不互比**：SI-SDRi 统一标 WSJ0-2mix / WHAMR，未与 VoiceBank-DEMAND 的 PESQ 混比。
