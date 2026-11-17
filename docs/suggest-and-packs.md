[← back to README](../README.md)

# starting a project: `suggest` and packs

## `evidgate suggest`

An empty config is the worst first minute. Ask instead:

```console
$ evidgate suggest
扫到的东西：
  · figs 一带：3 个 svg、4 个 png、3 个 pdf
      → 一个源 + 多个派生 —— 正是 figures 包要盯的结构

建议在 evidgate.yaml 里写一行：
    packs: figures

生成它：evidgate init --packs figures
```

It reads the disk — figure directories, build output, a bibliography, tests — and says
which packs apply and which checks you still need to write yourself. `--write` produces
the config directly. `README.md` and evidgate's own ledger/report are never mistaken for
documents to audit.

## Check packs

Write one line instead of fifteen:

```yaml
project: my-deliverable
ledger: evidgate_ledger.md
packs: figures
```

That is a complete config. `evidgate run` expands it into the pack's checks
(derivatives / manifest / stale / orphan) and blocks on the red one.

| pack | what it adds |
|---|---|
| `figures` | one source, many derivatives: `png`/`pdf`/`eps` stay covered by `artifacts.json` |
| `build` | build output is non-empty, carries no credentials, has no stray `.tmp`/`.bak` |
| `repo` | tests are green, no leftover `TODO`/`FIXME`/`breakpoint()` |
| `sources` | a source document and the one written from it: every clause of the source is either restated or shown to be inapplicable |

Parameters go after a colon: `packs: figures:manifest=my.json,outdir=figs`.
Several options on one pack are separated by commas: `packs: repo:test_cmd=...,pattern=...`.
See what a pack expands to with `evidgate pack show figures`.

## Scope note

This is deliberately not a typography or AI-tone linter — Vale and `deliverable-qa` do
that well and with far more rules. evidgate asks a different question: *is the evidence
behind this claim present, unchanged and still reproducible?* That is why every check runs
a command and records an exit code, a hash and a timestamp, and why most packs check
artifacts rather than prose.

`sources` is the one pack that touches prose, and it still keeps to the same question.
It does not judge whether a clause was restated *well*: it splits the source by clause
number and reports the clauses whose wording appears nowhere in your document. That is a
presence question, not a quality one — the verdict is yellow because "absent" and "did
not need restating" look identical, and only a person can tell them apart. Measured on a
real notice: 13 clauses, 5 restated (0.38–0.83), 1 dropped (0.00).
