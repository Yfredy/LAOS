# 转写原始记录：《音频信号的预加重：提升语音清晰度》

- note_id: 69953aa6000000001d02605d
- 分组: G-dsp
- 图数: 5
- 读图方式: 主对话逐图直读（2026-10-09，全部有效，无待仲裁段）
- URL 状态: 下列 CDN 链接已过期，仅存档追溯；本地备份 var/xhs_audio/imgs/69953aa6000000001d02605d/*.webp

URL 列表（按图序）：
1. http://sns-webpic-qc.xhscdn.com/202610091039/04508c128eda36f34f8f19ec80a91262/spectrum/1040g34o31sinv0p75e4g5ofav0lk1ms694dgc7g!nd_dft_wlteh_webp_3
2. http://sns-webpic-qc.xhscdn.com/202610091039/1c5dfbe2586bdd20fb9d04e764be5a63/spectrum/1040g34o31sinv0p75e505ofav0lk1ms6lg1gis0!nd_dft_wlteh_webp_3
3. http://sns-webpic-qc.xhscdn.com/202610091039/910c1ae0cd5065b5b489b264073ed621/spectrum/1040g34o31sinv0p75e5g5ofav0lk1ms6ujhi6ag!nd_dft_wlteh_webp_3
4. http://sns-webpic-qc.xhscdn.com/202610091039/e6fbe8bc8b2973cb2242bcdead355f24/spectrum/1040g34o31sinv0p75e605ofav0lk1ms6t43c4ko!nd_dft_wlteh_webp_3
5. http://sns-webpic-qc.xhscdn.com/202610091039/0874749e1f3ff42d73d69a4f2ec08247/spectrum/1040g34o31sinv0p75e6g5ofav0lk1ms6qo7hu6o!nd_dft_wlteh_webp_3

---

## 图 1/5（无编号标题页）

# 音频信号的预加重：提升语音清晰度

### Pre-emphasis：一阶高通的一百种理由

**为什么预加重？**
语音频谱随频率升高下降 6dB/oct——高频能量弱。

## 图 2/5（编号：## 2）

## 一阶高通实现

- **公式**：y[n] = x[n] − α·x[n−1]，α = 0.95-0.97
- **频响**：+20dB/decade 高频提升
- **去加重**：z[n] = y[n] + α·z[n−1] 逆复原

## 图 3/5（编号：## 3）

## 四大作用

1. 平衡频谱（高频补偿）
2. 避免数值问题（LPC 求解数值稳定）
3. 提升信噪比感知（辅音清晰度）
4. **历史包袱**：FM 传输时代残留——现代 DNN 前端常省略

## 图 4/5（编号：## 4）

## 现代还要不要？

- **争论**：传统管线必做；现代 DNN（Conformer/Whisper 前端）多数省略（模型自己学）
- **判断**：小数据 + 经典模型 → 做；大数据 + DNN → 可省
- **技巧**：Mel 域已含部分预加重效果

## 图 5/5（编号：## 5）

## 小结

**预加重一句话**：一阶高通补高频——经典管线必做、DNN 时代可省的历史工艺。
