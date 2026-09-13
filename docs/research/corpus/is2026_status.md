# Interspeech 2026 探测 + 摘要层补全状态

> 实测日期：2026-09-14。执行者：Task 3 子代理。

## 1. ISCA 2026 上线探测（不得假设，已实测）

| 年份 | URL | 结果 | 说明 |
|---|---|---|---|
| 2026 | `https://www.isca-archive.org/interspeech_2026/` | **FAIL · HTTP 404** | ISCA 尚未上线 2026 会议存档 |
| 2025 | `https://www.isca-archive.org/interspeech_2025/` | OK · ~1.13 MB | 静态 HTML 全文免费，可正常抓取 |

**结论：ISCA 尚未上线 Interspeech 2026，本语料（与整个普查）的 Interspeech 上限只能到 2025。最终报告必须同样声明，"2026 数据"不在范围内。**

## 2. 摘要层补全方法

- 数据源：语料每条 `url` 指向的 ISCA 摘要页（如 `https://www.isca-archive.org/interspeech_2021/pucher21_interspeech.html`）。
- 解析器实测结论：ISCA 摘要页摘要位于 `<div id="abstract"><p>…</p></div>`，**无** `<meta name="description">` 摘要。计划原版 `parse_abstract` 只查 `class="…abstract…"` 会漏掉 `id="abstract"`，已修正为先查 `id="abstract"`，再回退 class 与 meta。
- 增量 + 断点续传：已有 `abstract` 的条目跳过；每 50 条落盘一次。
- 限流：0.8 s/条；`fetch()` 带 3 次重试 + 递增退避，应对 ISCA 偶发 `SSL UNEXPECTED_EOF`。
- 抓不到就标 `abstract_failed`，**绝不编造摘要**。

## 3. 验证（60 条先验）

`crawl_interspeech_abstracts.py 60` → **ok=60 / fail=0（100.0%）**。ok 率远超 70% 阈值，解析器无需再修。

## 4. 批量补全结果（1200 条 × 6 主题，后台运行）

待后台任务完成后填入：
- 最终 ok / fail 数
- 总体摘要覆盖率
- 各主题（emotion / edge / kws_vad / event / codec / enhance）摘要覆盖率

## 5. SSL / 限流情况

待填入。
