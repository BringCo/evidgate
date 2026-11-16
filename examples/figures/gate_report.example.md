# release gate report · figure-pipeline (fictional)

## 1. 检查表

| cid | check | status | evidence |
|---|---|---|---|
| F1 | 登记图形齐全且派生未被手改 | FAIL(红) | `builtin:artifact:manifest artifacts.json` · exit=2 · out: 内容变了(手改或重跑过): pdf/fig01_pipeline.pdf  md5 2aeb4cf0 != 登记 00…  |
| F2 | 派生是否跟随源（盖章后才可判定） | DIFF(黄) | `builtin:artifact:stale artifacts.json` · exit=3 · out: 源已变，派生未重新生成: eps/fig03_timeline.eps <- figs/fig03_timeline.… · 0 |
| F3 | 产物目录里没有漏纳管的文件 | DIFF(黄) | `builtin:artifact:orphan artifacts.json --dir png` · exit=3 · out: 未登记(漏纳管): png/fig04_draft.png \\ |

## 2. 待确认（黄项）

- F2
- F3

## 3. 待补与未覆盖

**待补（没核过）**：无

**未覆盖（optional/不适用，不阻塞）**：无

## 4. 放行结论

- **不可放行**：红项 ['F1']；待补 无
