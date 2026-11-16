[← back to README](../README.md)

# Plugin: prose (Chinese)

`evidgate prose scan --rule <name>` — exits `0` clean, `2` blocking, `3` advisory.

| rule | what fires (after calibration) |
|---|---|
| `denominator` | sentence count of the body — info only, makes coverage countable |
| `absolutes` | **`本文/我们` + 首次/首创/率先**, or **首次/首创 + 提出/实现/证明/引入/建立** — and no search date. Descriptive uses ("the metric first fell below X", "the only negative gap") do not fire |
| `uncited` | claim verbs (表明/说明/证明/意味着/取决于) with **no** citation, chart, §-reference, statistic or measured marker |
| `numeral_scope` | a bare number (ρ / R² / 倍 / % / 降低 N) with no `n=`, `m/m`, `p=`, ±, 口径/协议/脚本/路径 nearby |
| `citation_chain` | `[n]` in the body missing from the bibliography, and listed-but-never-cited entries |

## Calibration (this is the part that matters)

The first version of these rules was calibrated against invented examples and it was
wrong. On a real 581-sentence manuscript it fired **222 times** with roughly 95% false
positives — it flagged a descriptive "the metric first fell below its target" as a
priority claim, a bare "first drop" as a novelty claim, and every sentence containing
`20/20` or `p=1.7e-12` as "missing an n".

After calibration it fires **32 times** on the same draft, and the nine regression tests
in `tests/` pin the descriptive wordings that must stay quiet.

## Two conventions

- **Sentence boundary**: prose rules split on `。；！？`. A ledger that counts *lines*
  (including table rows) will report a different denominator — e.g. 581 sentences vs 251
  ledger lines on the same file. Coverage numbers are not comparable across tools.
- **Your field's own markers**: add them with `EVIDGATE_EVIDENCE`, a `|`-separated regex,
  e.g. `EVIDGATE_EVIDENCE='20/20|Holm|pp|§[0-9]'`. The built-in list only knows the common
  ones.

These are heuristics, not oracles — yellow is where a human should look, which is exactly
why yellow exists.
