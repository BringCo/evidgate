# evidgate

**Release gates for whatever you hand over.** A check is a command plus an assertion
plus a declared way to fail. One ledger line holds the check, its proof, its resume
point and its release decision — whether the thing being checked is a paragraph, a
produced file, or the code that produced it.

```console
$ evidgate run --dir examples/mixed
evidgate 0.1.0 · mixed-delivery (fictional) · 7 checks
   D1 FAIL(红)  草稿里的绝对化词带范围或检索日期  ─  -exit 2 (want 0) | got: L3 [首次] 本方案首次实现全自动估价流程。
   D2 DIFF(黄)  草稿里的统计数字带口径  ─  -exit 3 (want 0) | got: L3 抽样调参后误差降低 18.4%。
   A1 PASS     产物存在且非空  ─  +exit 0 (want 0) ; +regex OK ─ \d -> 3
   A2 FAIL(红)  正本与其派生副本逐字节一致  ─  -exit 1 (want 0)
   C1 PASS     代码单测全绿  ─  +exit 0 (want 0)
   C2 PASS     源码里没有明文密钥  ─  +not_contains OK:api_key ; +not_contains OK:secret_key
   C3 PASS     源码里没有残留 TODO  ─  +exit 1 (want 1)

PASS 4 · DIFF(黄) 1 · FAIL(红) 2 · 待补 0 | coverage 7/7 (100.0%)
RELEASE BLOCKED  blocked by D1, A2
```

Red blocks the release. Yellow goes to a confirmation list. **待补 is never "done".**
Exit code 1 means blocked — a non-zero run cannot be reported as a pass.

## One ledger, several domains

The engine does not know what a document is. It knows `command`, `expect`, `counter`,
`severity` and an exit code. Above, seven checks from three different worlds share one
table and one release decision:

| domain | example check | assertion |
|---|---|---|
| prose (a drafted document) | 绝对化词是否带检索日期或范围 | `exit:0` on a prose rule |
| artifact (a produced file) | 产物非空 / 正本与派生副本逐字节一致 | `regex:\d`, `cmp -s` |
| code (what produced the artifact) | 单测全绿 / 没有明文密钥 / 没有残留 TODO | `exit:0`, `not_contains:`, `exit:1` |

That last row is worth noticing: `grep -rn TODO src/` **asserts `exit:1`** — "no match"
is a legitimate expectation. Anything with a deterministic exit code is checkable.

Add your own domain without touching `core/`: write a script that exits 0 / 2 / 3 and
declare it as a check. That is the whole plugin contract.

## Why this is not another linter

| | typical linter | checklist (human) | evidgate |
|---|---|---|---|
| Who decides pass | the rule | a person ticking a box | the command + its exit code |
| What proves it | nothing | nothing | command, exit code, output tail, artifact hash, timestamp |
| If the rule silently stops working | silent | silent | `evidgate mutate` reports "detection 1/1" or "NOT caught" |
| Where "what is left" lives | nowhere | another sheet | the same ledger line |
| Can a rule exist with no way to fail | yes | yes | **refused at load time** |

That last row is the design constraint: `counter` (how this check goes red) is a
required field. A gate that cannot fail is not a gate, it is a wish.

## Install

```bash
git clone https://github.com/BringCo/evidgate && cd evidgate
./bin/evidgate --version        # zero-install entry point, stdlib only

# or as a package
pip install evidgate
```

Python 3.9+; CI runs the suite on 3.9 and 3.12 (developed and exercised on 3.12/3.14).
No third-party dependencies. PyYAML is used when present; a built-in
parser covers the examples otherwise.

### 30 seconds, on your own project

```bash
evidgate init --dir .          # writes evidgate.yaml; picks a file that actually exists
evidgate prose-init --dir . --file draft.md   # optional: the Chinese prose checks
evidgate doctor --dir .        # yaml parseable? every command resolvable? — before blaming the project
evidgate run --dir .           # ledger + verdicts; exit 1 = blocked
```

If `doctor` prints `BAD`, fix that first — the most common failure is a `method` whose
command is not on `PATH`. Checks written by this tool use `builtin:` and run in-process,
so they cannot hit that.

## Commands

```bash
evidgate init --dir <proj>                       # starter evidgate.yaml
evidgate doctor --dir <proj>                     # yaml + command resolvability, before you blame the project
evidgate run --dir <proj> [--only C1,P2]         # run + rebuild the ledger; exit 1 = blocked
evidgate resume --dir <proj>                     # rerun only unresolved checks
evidgate report --dir <proj>                     # gate_report.md: table, yellows, unverified, verdict
evidgate mutate --baseline A --mutant B [--only C1]   # does the check actually go red?
evidgate prose-init --dir <proj> --file <draft>  # append the Chinese prose checks (P1..P5)
evidgate artifact-init --dir <proj>              # scan a directory into a first-draft artifacts.json
evidgate artifact-update --dir <proj>            # recompute an artifact's own md5 (never source_md5)
evidgate artifact-stamp --dir <proj> --path P    # after regenerating: record the source hash
evidgate prose scan --file <draft> --rule absolutes   # one rule, standalone
```

## Writing a check

```yaml
checks:
  - cid: A2
    name: 正本与其派生副本逐字节一致
    method: cmp -s src/app.py src/app.py.bak
    expect: exit:0
    counter: 改常量但忘了同步 .bak，本项必须变红
    severity: red        # red = blocking, yellow = non-blocking (DIFF)
```

`method` takes two forms:

| form | when |
|---|---|
| `cmp -s a b` / any shell command | your own script or tool. Must be resolvable — `doctor` tells you if it is not |
| `builtin:prose:absolutes draft.md` | checks shipped with evidgate; dispatched **in-process**, so no `PATH` involved |

Add `optional: true` when a check only applies to some setups (a missing input, an
absent service). A failing optional check becomes `SKIP(未覆盖)` — listed in the report,
counted as handled, **never blocking**. Without it, "my project has no such file"
would show up as a red failure, which is how a gate loses its audience.

`expect` clauses (join with `;`, all must hold):

| clause | meaning |
|---|---|
| `exit:N` | exit code equals (any value — `exit:1` is a valid expectation) |
| `contains:TEXT` / `not_contains:TEXT` | stdout contains / does not contain |
| `regex:PATTERN` | stdout matches (multiline) |
| `lines>=N` / `lines<=N` | non-empty stdout line count |
| `file:PATH` | path exists (byte size + md5 recorded) |
| `md5:PATH=HEX` | file hash matches |
| `manual` | no command assertion; stays 待补 and blocks |

An assertion that needs stdout (`contains` / `regex` / `lines`) fails the evidence
self-check if the command printed nothing — a `not_contains` on empty output would
otherwise be a tautology.

## Plugin: artifact (manifest-driven)

Four checks derived from three rules that govern content assets: one asset has one
source; a derivative is regenerated, never hand-edited; registering at creation time is
cheap. Everything is decidable from a manifest, so nothing is guessed.

```bash
evidgate artifact-init --dir .        # scans into artifacts.json (all role=source)
# then mark what is a derivative and what came from where
```

```yaml
- cid: A1
  name: 登记产物齐全且未被手改
  method: builtin:artifact:manifest artifacts.json
  expect: exit:0
```

| rule | asks | red/yellow |
|---|---|---|
| `manifest` | is every registered file still present, and does a **derivative's** recorded md5 still match? | red |
| `stale` | did the source change since this derivative was generated? (compared by hash, not mtime) | yellow |
| `sync` | does a `same_as_source` derivative still equal its source? | red |
| `orphan` | is there a file in the scanned directory the manifest never registered? | yellow |

The gate's own files (`evidgate.yaml`, `evidgate_ledger.md`, `gate_report.md`) never
count as orphans — they are configuration and output, not deliverables.

`stale` compares the recorded `source_md5` against the source's hash now — never file
times. An earlier version used mtime and was wrong: `git clone`, unzip and `rsync` all
stamp "now", so the same example reported `1 PASS / 2 DIFF` in a working tree and
`2 PASS / 1 DIFF` after a clone. Hash comparison gives the same verdict in both.

**Point `orphan` at the artifact directory, not the repo root.** Measured on a real
17k-file project: scanning the root reported 6002 "unregistered" files (sources, docs,
`.bak` copies) — true but useless. Scanning only `build/` is the intended use. Cost: the same
201 files took 0.001 s on ext4 and 0.818 s across a WSL `/mnt/c` mount (≈800× per file),
so width matters more than count on a mounted drive.

Files you never want registered (build logs, temp files) go in the manifest's `ignore`
list, matched with shell globs:

```json
{"root": ".", "ignore": ["*.log", "tmp/", "*.tmp"], "items": [...]}
```

`source_md5` has exactly one writer: **`artifact-stamp`**, called right after you
regenerate. `artifact-update` deliberately does *not* touch it. An earlier version did,
which meant a single command made every stale derivative look fresh without regenerating
anything — that is laundering, not gating.

```bash
evidgate artifact-stamp --dir . --path build/report.html   # only after regenerating
```

What `stale` can and cannot say: it answers "did the source change since this stamp".
It cannot tell whether a derivative was ever in sync. A derivative with no `source_md5`
is reported as **cannot tell**, never as clean. Measured on a real figure directory
(10 SVG sources, 30 derivatives): before stamping, all 30 read "cannot tell"; the
mtime heuristic had called 10 of them stale, but that verdict was itself unreliable.

## Plugin: prose (Chinese)

`evidgate prose scan --rule <name>` — exits `0` clean, `2` blocking, `3` advisory:

| rule | what fires (after calibration) |
|---|---|
| `denominator` | sentence count of the body — info only, makes coverage countable |
| `absolutes` | **`本文/我们` + 首次/首创/率先**, or **首次/首创 + 提出/实现/证明/引入/建立** — and no search date. Descriptive uses (`首次跌破`, `唯一缺口为负者`) do not fire |
| `uncited` | claim verbs (表明/说明/证明/意味着/取决于) with **no** citation, chart, §-reference, statistic or measured marker |
| `numeral_scope` | a bare number (ρ / R² / 倍 / % / 降低 N) with no `n=`, `m/m`, `p=`, ±, 口径/协议/脚本/路径 nearby |
| `citation_chain` | `[n]` in the body missing from the bibliography, and listed-but-never-cited entries |

### Calibration (this is the part that matters)

The first version of these rules was calibrated against invented examples and it was
wrong. On a real 581-sentence manuscript it fired **222 times** with roughly 95% false
positives — it flagged `唯一缺口为负者` as a priority claim, `SOH 首次跌破` as a novelty
claim, and every sentence containing `20/20` or `p=1.7e-12` as "missing an n".
After calibration it fires **32 times** on the same draft, and the nine regression tests
in `tests/` pin the descriptive wordings that must stay quiet.

Two conventions you should know:

- **Sentence boundary**: prose rules split on `。；！？`. A ledger that counts *lines*
  (including table rows) will report a different denominator — e.g. 581 sentences vs
  251 ledger lines on the same file. Coverage numbers are not comparable across tools.
- **Your field's own markers**: add them with `EVIDGATE_EVIDENCE`, a `|`-separated regex,
  e.g. `EVIDGATE_EVIDENCE='20/20|Holm|pp|§[0-9]'`. The built-in list only knows the
  common ones.

These are heuristics, not oracles — yellow is where a human should look, which is
exactly why yellow exists.

## Shell: no shell by default

A check runs **without a shell** unless you declare one. That is deliberate: it is the
only way the same check means the same thing on every platform.

```yaml
- cid: C3
  method: grep -rn TODO src/       # split into argv, executed directly
  expect: exit:1
  ```

If the command needs pipes, redirection, `$()` or `&&`, say so:

```yaml
- cid: A1
  shell: bash                      # bash | sh | cmd | powershell | pwsh
  method: test -s build/out.txt && wc -c < build/out.txt
```

Boundaries, stated plainly:

- Without `shell:`, a command that needs shell syntax fails with a message telling you
  to add `shell: bash` — it does not silently pick a shell for you.
- `shell: bash` on Windows looks for **Git Bash** in its standard install locations.
  It deliberately does **not** use `bash` from `PATH`, because there that name resolves
  to `C:\Windows\System32\bash.exe` — the WSL entry point, which uses `/mnt/e/...`
  instead of `/e/...` and would look in the wrong place.
- No Git Bash, no `shell: bash` checks. They report "命令未找到" and block the release.
  `builtin:` checks need nothing and work everywhere.

### Windows

Checks run through `bash -lc` on POSIX and `cmd /c` on Windows. Everything that ships
as `builtin:` (all of `packs/figures`) works on both. Anything written as a shell
command (`grep`, `test -d`, `$(...)`) needs a POSIX shell.

If a command is not found at all, evidgate now says so and fails the check rather than
accepting the exit code — because on Windows a missing `grep` exits `1`, which is
exactly what `expect: exit:1` ("grep found nothing") looks for. That was a real silent
false green.

On Windows, prefer `builtin:` checks, or run under Git Bash / WSL.

## Check packs

Write one line instead of fifteen:

```yaml
project: my-deliverable
ledger: evidgate_ledger.md
packs: figures
```

That is a complete config. `evidgate run` expands it into three real checks
(manifest / stale / orphan) and blocks on the red one.

| pack | what it adds |
|---|---|
| `figures` | one source, many derivatives: `png`/`pdf`/`eps` stay covered by `artifacts.json` |
| `build` | build output is non-empty, carries no credentials, has no stray `.tmp`/`.bak` |
| `repo` | tests are green, no leftover `TODO`/`FIXME`/`breakpoint()` |

Parameters go after a colon: `packs: figures:manifest=my.json,outdir=figs`.
See what a pack expands to with `evidgate pack show figures`.

**Scope note.** This is deliberately not a typography or AI-tone linter — Vale and
`deliverable-qa` do that well and with far more rules. evidgate asks a different
question: *is the evidence behind this claim present, unchanged and still
reproducible?* That is why every check runs a command and records an exit code,
a hash and a timestamp, and why packs here check artifacts rather than prose.

## Examples

Both are **fictional**; every defect is planted on purpose.

- `examples/mixed/` — prose + artifact + code in one ledger (the output above).
  Run: `./bin/evidgate run --dir examples/mixed`
- `examples/` — a Chinese draft, six checks, 2 PASS / 2 DIFF / 2 FAIL.
  Run: `cd examples && ../bin/evidgate run --dir .`
- `examples/figures/` — the real shape of a figure directory: **one SVG source, three
  derivatives** (png/pdf/eps). It shows all three `stale` verdicts side by side: stamped
  and clean, never stamped ("cannot tell"), stamped but the source moved on. Figures are
  generated, not real assets.
  Run: `./bin/evidgate run --dir examples/figures`

Mutation demo:

```bash
./bin/evidgate mutate --dir examples --baseline examples/base --mutant examples/mut --only C1
# detection power: 1/1
```

## Scope

- **Does not** verify that a reference exists or says what you claim — use
  [refchecker](https://github.com/markrussinovich/refchecker) or similar for that.
- **Does not** detect AI-generated text.
- **Does** check that the evidence you claim for your own statements, numbers and
  artifacts is real, reproducible and recorded — in whatever domain your command
  can observe.

## Attribution

Evidence triples and three-state verdicts follow obra/superpowers'
`verification-before-completion`; the evidence-gate framing follows TestifySec
Pushgate. What is new here is listed in [ATTRIBUTION.md](ATTRIBUTION.md).

## License

MIT