# 采集手册（acquisition）

读图之前：把目标 up 主/笔记的清单与图片弄到本地。

## 0. 风控红线（最高优先）

- **用户本人在 in-app browser 登录小红书**，你只做真实 UI 导航（滚动、点开笔记、翻页）。
- **禁止伪造 API 签名直调后端接口**——实测会触发风控（300011 错误），危及用户账号。这一条是用一次教训换来的，不可逾越。
- 浏览器导航用 browser-use 技能（control-browser）；导航节奏放慢，像人。

## 1. 三个产物

| 产物 | 路径（laos 约定） | schema |
|---|---|---|
| manifest.json | `var/xhs_audio/manifest.json` | `[{group, id, title, imgs[]}]`——读图任务的唯一索引 |
| details.json | `var/xhs_audio/details.json` | `{id: {id, title, desc, type, time, tags, imgs}}`——正文/标签/发布时间 |
| 图备份 | `var/xhs_audio/imgs/<noteId>/*.webp` | CDN URL 数小时过期，本地备份是权威副本 |

manifest 的 `imgs` 是按序 CDN URL，形如：

```
http://sns-webpic-qc.xhscdn.com/<时间戳>/<hash>/spectrum/<文件名>!nd_dft_wlteh_webp_3
```

## 2. 提取流程

1. **主页枚举**：打开 up 主主页（`.../user/profile/<userId>`），滚动加载全部笔记，收集每篇的 id/标题/封面/xsec_token。
2. **逐篇详情**：带 token 打开每篇（`.../explore/<noteId>?xsec_token=...`），取正文 desc、标签、图集 URL 列表。
3. **落盘**：写 manifest + details；图集 URL 立即批量下载到 `imgs/<noteId>/`（webp 原样）。
4. **分组**：按主题给字母组（看标题即可分组，如 A-interspeech / G-dsp / K-misc），写进 manifest 的 group 字段。

下载/写 JSON 用 `C:/Users/yaoyue/miniconda3/python.exe`（Windows 本机约定；其他环境类推）。量大时分批 + 重试，别让单张失败卡住整批。

## 3. 增量续采

已有 manifest 时，续采只 append 新笔记 id；已读篇不重读。续读会话直接从 manifest 挑未完成的组开始，transcripts/ 已存在的笔记跳过（workflow 也是这个语义）。

## 4. 单篇直读（无采集）

用户只给一篇笔记 URL 且不需要建库时：浏览器打开该篇 → 取图集 URL → 直接进读图阶段，transcript 写不写盘均可（写盘便于日后 digest 阶段复用）。

## 5. 合规与诚实

- 转写内容注明来源（up 主名 + 笔记链接/日期）。
- 涉及评测数字的，digest 保留"up 主实测/论文原文"的来源属性，不混入自己的推断。
- 采集物全部在 var/（gitignored），不进版本库；调研文档只引用结论不贴原图。
