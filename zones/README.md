# zones/ —— 四棵 zone 树

| 目录 | 角色 | 测试 |
|---|---|---|
| `AlwaysOnRec-Trae/` | Trae 哨兵对照树（同一工作负载在另一 IDE 下的对照实现） | 与主库同套 discover 口径 |
| `AlwaysOnRec-ZCode/` | 隔离区测试树（全天候录音前沿增量，独立可跑、不合主干即不生效） | 279 |
| `AlwaysOnRec-DB/` | DB 沙箱区（数据库沙箱实验场，整树 gitignore，不入库） | — |
| `Repro-ZCode/` | 复现区测试树（论文/文章数字过手复现，pytest 口径） | 71 |

> 四树原平铺于仓库根目录，2026-10-08 收拢进 `zones/`——参照 nanoMuse 目录学
> （docs/research/2026-10-08-nanomuse-ui-xdevice-reference.md §7）：根目录只放
> 治理与入口，zone 隔离树作为一个类别归入同一目录。发版口径的路径引用
> （scripts/release.py 的 VERSION_FILES / DOC_GLOBS / zone_test_counts）已同步。
