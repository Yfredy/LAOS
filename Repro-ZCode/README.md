# Repro-ZCode —— 四来源复现隔离区

> [laos](../README.md) 的第二个隔离实现区：把 [四来源学习报告](../docs/research/2026-10-05-four-article-repro.md)
> 中可复现的内容全部 TDD 落地。**零主代码改动**——本区不复制 laos 树、不 import 主库，
> 与 `AlwaysOnRec-ZCode/` 平级但更轻（纯复现模块，无内核耦合）。

## 模块地图

| 模块 | 来源 | 内容 |
|---|---|---|
| `repro/bs1770.py` | ④ LUFS 文章 | ITU-R BS.1770-4 全套：K 计权（48k Annex 精确系数 + 任意 fs 参数化互验）、门控积分响度、Momentary/Short-term、LRA（EBU 3342）、True Peak 4× 过采样、PLR |
| `repro/anc.py` | ③ 车载 ANC 文章 | 发动机阶次合成（rpm→阶次谐波）、单通道 FxLMS、次级通路最小二乘辨识、2×2 多通道 FxLMS |
| `repro/sho/` | ① 头部朝向论文（arXiv 2607.02129v1） | `ism.py` Allen-Berkley 镜像源法 + 6 麦 r=4.5cm 环形阵 + 论文区间房间采样；`speech.py` 伪语音 + cardioid 族指向性；`features.py` STFT 相位 sin/cos 特征（2C×T×128）+ 环形 MAE；`noise.py` 各向同性扩散场噪声（sinc 相干 Cholesky）；`model.py` 论文 Fig.1 架构（3×Conv+2×BiGRU+2×MHSA） |
| `repro/phasecoder.py` | ② PhaseCoder 文章 | 几何无关麦位编码（对齐 google-deepmind/phasecoder JAX 源码）：球坐标相位调制嵌入 + 幅度/相位补丁特征 + 输出头口径 |

## 运行

```bash
cd Repro-ZCode
C:/Users/yaoyue/miniconda3/python.exe -m pytest tests/ -q          # 全部测试
python scripts/run_sho_repro.py --n-utt 120 --iters 400            # 端到端训练实验
python scripts/run_repro_all.py                                     # 四模块冒烟汇总
```

## 诚实偏差（详见复现报告）

- 论文数字不作为断言：40,295 语句×200k 步 → 等比缩到百语句×数百步（冒烟验证管线正确性）
- 22 条实测 VDP → cardioid 族替代；VCTK → 伪语音；WHAM → 自造扩散噪声；ISM 阶次 20 → 默认 6
- PhaseCoder：不装 JAX、不跑 checkpoint——读源码后 numpy 复现编码数学
