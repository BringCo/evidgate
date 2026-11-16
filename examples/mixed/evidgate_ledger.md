# evidgate ledger · mixed-delivery (fictional)

> One line == one check == one piece of evidence == one resume point.
> Rebuild it with `evidgate run`; do not edit verdicts by hand.

| cid | check | method | expect | counter-test | sev | status | evidence | ts |
|---|---|---|---|---|---|---|---|---|
| D1 | 草稿里的绝对化词带范围或检索日期 | `../../bin/evidgate prose scan --file draft.md --rule absolutes` | `exit:0` | draft.md 里「首次实现」未给检索日期，本项必须变红 | red | FAIL(红) | `../../bin/evidgate prose scan --file draft.md --rule absolu…` · exit=2 · out: L3 [首次实现] 本方案首次实现全自动估价流程。 \\| [absolutes] 1 finding(s)  (exi… · 0.28s | 2026-11-16T12:02:34 |
| D2 | 草稿里的统计数字带口径 | `../../bin/evidgate prose scan --file draft.md --rule numeral_scope` | `exit:0` | draft.md 里「降低 18.4%」不写 n 与协议，应变成黄 | yellow | DIFF(黄) | `../../bin/evidgate prose scan --file draft.md --rule numera…` · exit=3 · out: L3 抽样调参后误差降低 18.4%。 \\| [numeral_scope] 1 finding(s)  (exit … · 0.3s | 2026-11-16T12:02:35 |
| A1 | 产物存在且非空 | `test -s build/out.txt && wc -c < build/out.txt` | `exit:0; regex:\d` | 清空 build/out.txt，本项必须变红 | red | PASS | `test -s build/out.txt && wc -c < build/out.txt` · exit=0 · out: 39 · 0.02s | 2026-11-16T12:02:35 |
| A2 | 正本与其派生副本逐字节一致 | `cmp -s src/app.py src/app.py.bak` | `exit:0` | 改 RATE 但忘了同步 .bak，本项必须变红（示例里就是这样） | red | FAIL(红) | `cmp -s src/app.py src/app.py.bak` · exit=1 · 0.02s | 2026-11-16T12:02:35 |
| C1 | 代码单测全绿 | `cd src && python3 -m unittest -q test_app` | `exit:0` | 把 estimate 改成返回负数，本项必须变红 | red | PASS | `cd src && python3 -m unittest -q test_app` · exit=0 · 0.11s | 2026-11-16T12:02:35 |
| C2 | 源码里没有明文密钥 | `cat src/app.py` | `exit:0; not_contains:api_key; not_conta…` | 在 app.py 里写一行 api_key = "xxx"，本项必须变红 | red | PASS | `cat src/app.py` · exit=0 · out: if __name__ == "__main__": \\|     print(estimate(4, 2)) · 0.03s | 2026-11-16T12:02:35 |
| C3 | 源码里没有残留 TODO | `grep -rn TODO src/` | `exit:1` | 加一行 | yellow | PASS | `grep -rn TODO src/` · exit=1 · 0.03s | 2026-11-16T12:02:35 |

## progress

- total: 7 · PASS 4 · DIFF(黄) 1 · FAIL(红) 2 · 待补 0
- coverage: 7/7 (100.0%)
