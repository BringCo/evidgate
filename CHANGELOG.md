# Changelog

One line per user-visible change. Dates are when the change landed.

## 0.9.0 — 2026-11-16

### Found by running against personal deliverables, not polished projects
Four repositories from the second batch (`nmbader/phd_thesis`,
`robstewart57/phd-thesis`, `astroHaoPeng/FiguresInMyPhdThesis`, `megrxu/zjureport`).
The first eight repos produced zero findings; these four produced three real defects.

**1. `artifact-init` crashed on an Emacs lock file.**
`robstewart57/phd-thesis` contains `results/scripts/.#plot-scaleup.R` — a dangling
symlink — and the scan died with `FileNotFoundError`, producing no manifest at all.
Now: `.#*` entries are skipped as editor locks, symlinks and dangling links are skipped,
and a single unreadable file no longer aborts the scan (it is counted and reported).

**2. The `figures` pack reported 3 PASS over a manifest of 172 sources.**
With no derivative registered, `manifest`, `stale` and `orphan` have nothing to compare,
so all three came back clean and the summary read `coverage 4/4 · 100%`. That is a false
green of the same family as the Windows `grep` one: not "the check is wrong" but "the
check had no object". New `builtin:artifact:derivatives` and a `GF0` check in the pack:

```
GF0 FAIL(红)  清单里至少有一条派生项  ─  没有任何派生项：172 条全部是 source
RELEASE BLOCKED  blocked by GF0
```

**3. `suggest` could not see the derivation chain in a real thesis repo.**
It only recognised SVG. `robstewart57/phd-thesis` builds its figures with `mkImages.sh`
and `mkPlots.sh` from `.fig`/`.dia`/`.dat`/`.Rdata`. Recognised now by two independent
signals: a shared basename across a source/output extension pair
(`.svg .fig .dia .drawio .ipe .gp` → `.png .pdf .eps .jpg .tif`), or a figure-generating
script / Makefile plus outputs on disk. That repo now gets `packs: figures`; a tree with
neither still gets nothing.

### Compatibility
All four bundled examples unchanged (`6/6 · 7/7 · 4/4 · 3/3`), except `examples/figures`
which uses a hand-written config and keeps its original three checks.

## 0.8.1 — 2026-11-16

### Fixed from a horizontal run over eight real repositories

| repo | files | `build` | `figures` | `prose` |
|---|---|---|---|---|
| `lightning-hydra-template` | 114 | 3 PASS · 0.79 s | — | — |
| `IDSIA/sacred` | 201 | 3 PASS · 0.77 s | — | — |
| `the-nix-way/dev-templates` | 131 | 3 PASS · 0.62 s | — | — |
| `jlevy/the-art-of-command-line` | 52 | 3 PASS · 0.57 s | — | uncited 1/56 |
| `sindresorhus/awesome` | 52 | 3 PASS · 0.52 s | 3 PASS · 0.60 s | — |
| `google/styleguide` | 78 | 3 PASS · 0.54 s | — | — |
| `chubin/cheat.sh` | 154 | 3 PASS · 0.59 s | — | — |
| `karpathy/nanoGPT` | 55 | 3 PASS · 0.64 s | — | — |

What that run changed:

- **`suggest` demanded proof of a derivative relationship.** `awesome` has six unrelated
  SVGs and two PNGs, and the old rule ("any svg + any raster") recommended the `figures`
  pack for a tree where *nothing derives from anything* — the pack then went green on an
  empty check set, which is worse than staying quiet. It now requires a shared basename
  (`a.svg` + `a.png`). `awesome` still qualifies on its one real pair; a tree with no
  pairs no longer gets the recommendation.
- **`CLAIM` no longer includes 意味着.** On a real Chinese README it fired on
  「你 *有能力* 在 Bash 中玩一些奇技淫巧并不意味着你应该去做」— ordinary prose, not a
  claim about evidence. Removed; that document goes 1 finding → 0, and the 581-sentence
  manuscript still reports the same 2 findings.
- `suggest` printed each bibliography note twice; the duplicate block is gone.

### Honest result
The `build` pack found **nothing** in eight mature open-source repositories. That is not a
bug — those projects do not commit credentials or leave `.bak` files around. It does mean
the pack's value is in **personal deliverables before hand-over**, not in auditing
established projects, and the README should not imply otherwise.

## 0.8.0 — 2026-11-16

### Added — `evidgate suggest`
Answers the real first question ("what should I even check?") from evidence on disk
instead of from a template:

- a vector source plus a raster/print derivative anywhere in the tree → `figures`
- a `dist/` / `build/` / `output/` with files in it → `build`
- a document with a real bibliography → suggests `prose-init`, and says so when the
  citation scheme is not `[n]`-numbered
- test files or a `tests/` directory → `repo`
- `.env` / `secrets.yml` / `credentials.json` present → tells you to confirm it is ignored

`evidgate init --packs figures,build` writes the config directly; `--write` does it
straight from `suggest`.

Measured on six directories, no configuration:

| directory | suggested |
|---|---|
| `examples/figures` | `figures` |
| `examples/artifact` | `build` |
| `IDSIA/sacred` | `repo` |
| `ashleve/lightning-hydra-template` | `repo` |
| `the-nix-way/dev-templates` | none — said so instead of inventing checks |

Excludes `README.md`, the ledger and the gate report: a project's own furniture is not a
document to audit.

### Fixed during development
- `probe()` referenced `TEST_HINTS` without the inner loop and used `entries` before it
  was defined — both were caught by running it, neither by reading it.

## 0.7.1 — 2026-11-16

### Fixed — `build` pack GB3 tested the wrong thing
The `build` pack's "no leftover temp files" check was written as

```
grep -rIl -E "\.(tmp|bak|swp|orig)$" {outdir}
```

which searches file **contents** for a line ending in `.bak`. It never looked at file
**names**, so a `model.ckpt.bak` sitting in the delivery directory passed as clean.
Found by running the pack against three real repositories; fixed to a `find -name`
test with the same counter (drop a `.bak`, it must go red).

### Measured against three real repositories
Cloned shallow, ran the `build` pack unchanged (no configuration, no hand-written checks):

| repo | files | time | GB1 | GB2 | GB3 |
|---|---|---|---|---|---|
| `ashleve/lightning-hydra-template` | 114 | 0.79 s | PASS | PASS | PASS (buggy) |
| `IDSIA/sacred` | 201 | 0.77 s | PASS | PASS | PASS (buggy) |
| `the-nix-way/dev-templates` | 131 | 0.62 s | PASS | PASS | PASS (buggy) |

Detection power checked by injection, not by the green result:

- dropped `AKIAIOSFODNN7EXAMPLE` into a tracked `.py` → GB2 goes **FAIL(red)**,
  release blocked, and the key appears **0 times** in the ledger.
- dropped `model.ckpt.bak` → before the fix GB3 stayed PASS; after the fix it is
  **FAIL(red)**; removing the file restores PASS.

### Known limit, now explicit
`artifact-init` on a general source repository produced **172 entries, all
`role=source`** — it cannot infer which file derives from which. The artifact rules are
useful for **structured output directories** (`figures/`, `dist/`), not for arbitrary
code trees. Annotating 172 files by hand is not a workflow.

## 0.7.0 — 2026-11-16

### Changed — **breaking**: a check no longer runs through a shell by default
Before, every check went through `bash -lc` (POSIX) or `cmd /c` (Windows) — the
interpreter depended on the platform, which is exactly how the same check behaves
differently per OS. Now:

- **No `shell:` key** → the command is split into argv and executed directly.
- **`shell: bash|sh|cmd|powershell|pwsh`** → run through that shell, explicitly.

This mirrors what `prek` does (its `shell` option defaults to `null` = no shell), and is
the only arrangement where a check means the same thing everywhere.

**Migration**: any check using `|`, `>`, `$()`, `&&` or `cd` needs `shell: bash` added.
Without it the run fails with: `命令未找到：cd（…若命令里有 | > $() && 等语法，请在该检查项上写 shell: bash）`.

### Added
- `find_posix_shell()` — on Windows looks for **Git Bash** in its install locations and
  deliberately ignores `PATH`, where `bash` resolves to `C:\Windows\System32\bash.exe`
  (the WSL entry point, `/mnt/e/...` instead of `/e/...`).
- `shell:`, `sh`, `bash`, `cmd`, `powershell`, `pwsh` validated at load time;
  anything else is refused.
- Missing shell is reported through the same "command could not run" channel as a
  missing tool: it blocks the release instead of being silently skipped.

### Measured (native Windows, `E:\Python3106`, `examples/mixed`, 7 checks)

| | v0.6.1 | v0.7.0 |
|---|---|---|
| PASS | 0 | **3** (A1, C2, C3 — real execution through Git Bash) |
| DIFF | 0 | 1 |
| FAIL | 7 | 3 |

The remaining C1 difference (`cd src && python3 -m unittest`) is a genuine environment
difference — Git Bash has no `python3` — which is the accepted cost of the explicit-shell
design: the check must be written for the platform it runs on.

### Compatibility
- Implementations that never went near `collect()` are untouched; `builtin:` checks
  behave identically.
- All four example projects produce byte-identical verdicts before and after.

## 0.6.1 — 2026-11-16

### Fixed — a command that never ran could produce a green verdict
Measured on native Windows (`E:\Python3106`), running `examples/mixed`:

| check | before | after |
|---|---|---|
| C3 「源码里没有残留 TODO」 | **PASS** | FAIL 命令未找到 |
| D1, D2, A1, A2, C2 | FAIL (`operable program or batch file`) | FAIL 命令未找到 |

C3 was a **silent false green**: `grep` does not exist in `cmd`, and `cmd` exits `1`,
which is exactly what `expect: exit:1` ("grep found nothing") asks for. The check
reported "no leftover TODO" without ever looking at a file.

- `_missing_tool()` detects a command that was never executed. Text is the primary
  signal (`command not found`, `is not recognized…`, `不是内部或外部命令`), because exit
  codes are not usable: the same missing command measured 1, 9009 and even 0 depending
  on the shell wrapper. `9009` (cmd's dedicated code) and `127` corroborate.
- Checks the failing command's **stdout as well as stderr** — `cmd` writes
  "not recognized" to stdout in some paths, which is why `exit 9009` was initially missed.
- `_decode()` tries UTF-8 then GBK. Decoding a Chinese Windows console as UTF-8 with
  `replace` turned `不是内部或外部命令` into mojibake and silently defeated the detection.
- A missing command now yields **FAIL(red)** for a required check and **SKIP** for an
  `optional:` one — no new status was added to the three-state model.
- `_fix_console()` reconfigures stdout/stderr to UTF-8 with `errors="replace"`; a GBK
  console previously raised `UnicodeEncodeError` mid-run.
- `evidgate doctor` prints the shell it will use and warns on Windows that POSIX checks
  (`grep`/`test`/`$()`) will not run there.
- README: Windows section — `builtin:` checks work everywhere, shell checks need a
  POSIX shell.

## 0.6.0 — 2026-11-16

### Added
- **Check packs.** `packs: figures` in `evidgate.yaml` is now a complete config — no
  checks of your own required. Three packs ship in the box:

  | pack | checks |
  |---|---|
  | `figures` | manifest · stale · orphan, for one source / many derivatives |
  | `build` | output non-empty · no credentials · no stray temp files |
  | `repo` | tests green · no leftover TODO/FIXME/breakpoint |

  Parameters: `packs: figures:manifest=my.json,outdir=figs`. Inspect with
  `evidgate pack list` / `evidgate pack show figures`.
- Pack checks carry their own counter-tests and are refused by the same `validate()`
  as hand-written ones.
- `load_checks(..., allow_empty=True)`: a project whose checks all come from packs may
  legitimately declare none of its own.
- **Credentials are redacted before display.** A check like `grep -n AKIA .env` is the
  check you want, and its stdout is exactly what must not land in a ledger you commit.
  Detection uses the raw text; only what is written to the ledger is redacted.
- `evidgate/packs/*.yaml` is shipped in the wheel (`package-data`).

### Scope note (also in README)
evidgate is not a typography or AI-tone linter — Vale and `deliverable-qa` do that with
far more rules. The packs here check artifacts, not prose, because that is the part
those tools cannot reach.

## 0.5.2 — 2026-11-16

### Fixed (found by running against real drafts, not examples)
- `citation_chain` fired **38 times** on an English manuscript whose bibliography uses a
  non-`[n]` scheme. It now recognises "the scheme is unknown" and says so **once**
  ("正文有 38 处 [n] 编号，但文献表里没有 [n]") instead of emitting 38 false alarms.
- Evidence markers extended to the forms a real manuscript actually uses: `(S5)`
  provenance codes, `p(t)=`, `7,234 窗` / `12 块电池` (counts with units), `split0–2`,
  and figure-caption lines (`虚线为…`) are no longer scanned as body assertions.
  Effect on the 581-sentence draft: 28 → 22 findings.

## 0.5.1 — 2026-11-16

### Added
- `examples/figures/` — one SVG source with three derivatives (png/pdf/eps), the layout
  every figure directory ends up with. It demonstrates all three `stale` verdicts in one
  run: stamped and clean, never stamped ("cannot tell"), and stamped-then-source-edited
  ("source moved on"). Figures are generated programmatically, not real assets.

## 0.5.0 — 2026-11-16

### Changed (prose rules re-calibrated on a real manuscript)
Running the rules on a real 581-sentence paper fired 222 times with ~95% false
positives. What was wrong and what changed:

- `absolutes` matched the words 首次/唯一 on their own. In engineering prose they are
  mostly descriptive (`SOH 首次跌破`, `唯一缺口为负者`). It now requires a self-reference
  (`本文/我们`) or a novelty verb (`首次提出/首次实现/…`). 18 → 0 on that draft.
- `uncited` recognised only `(author, year)` and `n=` as evidence. Real drafts also use
  `§4`, `图 4`, `表 2`, `p<0.001`, `20/20`, `Holm`, `pp`. 18 → 2.
- `numeral_scope` demanded an explicit scope on every sentence; in practice the scope is
  given once and later sentences cite it. Also: `提升/降低/倍` now require an adjacent
  number, `口径/惯例/定义` sentences are exempt, and formula lines (`$$…$$`) are no
  longer treated as body text. 184 → 28.
- `SCOPE_WORD` deliberately does **not** treat 结果/验证/对照/实验/统计 as evidence —
  measured: those words made the rules go silent on their own examples (`结果说明…`
  is exactly the sentence `uncited` exists for).

### Added
- `EVIDGATE_EVIDENCE` env var: `|`-separated regex for field-specific evidence markers.
- 9 regression tests pinning descriptive wordings that must stay quiet.

## 0.4.0 — 2026-11-16

### Changed (behaviour, and the point of this release)
- `source_md5` now has exactly one writer: the new `artifact-stamp`, run right after a
  derivative is regenerated. `artifact-init` no longer writes it (at build time nobody
  knows the history, so writing the current hash is a false claim) and
  `artifact-update` no longer touches it.
  Why: 0.3.x let one `artifact-update` mark every derivative up to date without
  regenerating anything. Running the rules on a real figure directory (10 SVG sources,
  30 derivatives) showed the contradiction — the manifest was constructed declaring all
  30 fresh, so the "0 findings" result was proving my own assumption. With honest
  bookkeeping those 30 read "cannot tell" until stamped.
- `artifact-update` only touches derivatives' own `md5`, and no longer adds `md5` to
  source entries.

### Added
- `evidgate artifact-stamp --path <derivative>` — record the source hash at generation
  time. The only way to make `stale` able to answer.

### Fixed
- `artifact:manifest` decides "is this a derivative" by structure (`source` present,
  `same_as_source`, or `role`), not by the `role` label alone. A manifest entry that
  wrote `source` but forgot `role` was silently skipped — measured with a deliberately
  wrong md5 returning no findings.

## 0.3.1 — 2026-11-16

### Fixed (found by running the rules on a real project, not the example)
- `artifact:manifest` no longer hash-checks `source` entries. Editing a source is the
  normal workflow; failing the gate for it made the check unusable. Only derivatives are
  guarded, and `stale` is what notices that they are now out of date.
- `artifact:orphan` precompiles its globs and caps its printed output at 30 lines.
- `orphan` on a repository root is documented against: a real 17k-file project reported
  6002 unregistered files, and 17k files took 40 s across a WSL `/mnt/c` mount versus
  0.01 s for 2k files on ext4.

## 0.3.0 — 2026-11-16

### Changed (behaviour)
- `artifact:stale` is now decided by the recorded `source_md5` instead of file mtime.
  The mtime version gave different answers in a working tree and in a fresh clone
  (measured: `1 PASS / 2 DIFF` vs `2 PASS / 1 DIFF`), so it could not be used in CI.
  A derivative without a recorded `source_md5` now reports "cannot tell" instead of
  silently passing.

### Added
- `ignore` list in the manifest (`["*.log", "tmp/", "*.tmp"]`, shell globs) so
  build logs and temp files are not reported as unregistered.
- `evidgate artifact-update` — recompute `md5` / `source_md5` after regenerating.

## 0.2.0 — 2026-11-16

### Added
- `artifact` plugin, four manifest-driven checks: `manifest` (registered file
  still present and unedited), `stale` (derivative older than its source),
  `sync` (`same_as_source` copy still equals the source), `orphan` (file on disk
  never registered).
- `evidgate artifact-init` — scan a directory into a first-draft `artifacts.json`.
- `evidgate doctor` — yaml parseable, every command resolvable, shell builtins
  recognised; run this before blaming the project.
- `method: builtin:<plugin>:<rule>` — checks dispatched in-process, so a check
  generated by the tool cannot fail with `exit 127` for being off `PATH`.
- `optional: true` — a failing optional check becomes `SKIP(未覆盖)`: listed,
  counted, never blocking.
- `run` prints a fixed reminder that PASS means "evidence exists and reproduces",
  not "the numbers are right".

### Fixed
- `not_contains` without an `exit:` clause could pass on empty output — now
  refused at load time.
- Ledger rows were dropped after `resume`; `P*`-prefixed check ids were not
  recognised by the resume parser.
- Table pipes were double-escaped; evidence gaps were reported for exit-code-only
  checks that legitimately print nothing.
- `build/` in `.gitignore` swallowed the example artifacts, so a clean clone
  failed its own examples.
- `prose numeral_scope` silently skipped short sentences carrying a bare
  percentage.
- `init` generated a check against a file the project did not have.

## 0.1.0 — 2026-11-16 (never published; first release was 0.2.0)

- `core`: check registry, evidence (command/exit code/output tail/artifact
  hash/timestamp), three-state verdicts, release rule.
- `ledger`: one line == check == evidence == resume point; idempotent rebuild.
- `prose` plugin: denominator, absolutes, uncited, numeral_scope,
  citation_chain.
- `mutate`: run the same checks against a baseline and a planted-defect copy,
  report detection power.
- Examples (fictional), initial test suite, ATTRIBUTION, skill adapter, MIT license.
