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
| `manifest` | is every registered file still present, and does a recorded md5 still match? | red |
| `stale` | is a derivative older than its source (i.e. never regenerated)? | yellow |
| `sync` | does a `same_as_source` derivative still equal its source? | red |
| `orphan` | is there a file on disk the manifest never registered? | yellow |

The gate's own files (`evidgate.yaml`, `evidgate_ledger.md`, `gate_report.md`) never
count as orphans — they are configuration and output, not deliverables.

## Plugin: prose (Chinese)

`evidgate prose scan --rule <name>` — exits `0` clean, `2` blocking, `3` advisory:

| rule | catches |
|---|---|
| `denominator` | sentence count of the body (info; makes coverage countable) |
| `absolutes` | 首次/首创/唯一/未见 without a search date or scope |
| `uncited` | claim verbs (说明/证明/表明…) with no citation and no measured marker |
| `numeral_scope` | ρ / R² / 倍 / % sentences with no `n`, protocol or script path |
| `citation_chain` | `[n]` in the body missing from the bibliography, and listed-but-never-cited entries |

These encode lessons from real review rounds. They are heuristics, not oracles —
yellow is where a human should look, which is exactly why yellow exists.

## Examples

Both are **fictional**; every defect is planted on purpose.

- `examples/mixed/` — prose + artifact + code in one ledger (the output above).
  Run: `./bin/evidgate run --dir examples/mixed`
- `examples/` — a Chinese draft, six checks, 2 PASS / 2 DIFF / 2 FAIL.
  Run: `cd examples && ../bin/evidgate run --dir .`

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