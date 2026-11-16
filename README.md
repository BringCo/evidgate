# evidgate

[![PyPI](https://img.shields.io/pypi/v/evidgate.svg)](https://pypi.org/project/evidgate/)
[![Python](https://img.shields.io/pypi/pyversions/evidgate.svg)](https://pypi.org/project/evidgate/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/BringCo/evidgate/actions/workflows/ci.yml/badge.svg)](https://github.com/BringCo/evidgate/actions/workflows/ci.yml)

**English** · [简体中文](README.zh-CN.md)

**A command-line tool that turns a deliverable's claims into checks — and refuses to
load a check that cannot go red.**

It does not judge whether the content is right. It judges whether the evidence you claim
for it is real, still there, and reproducible, then writes that judgement into one ledger
you can hand to somebody else.

One ledger line = one check = the command that ran = the exit code it produced = the
point where you resume = the decision to release or block.

## The failure this exists to catch

A check that reports green for the wrong reason is worse than no check: you stop
looking. Three shapes of that, all encountered while building this:

**1. The command never ran.** On Windows there is no `grep`. Running a missing command
exits `1` — and `exit:1` is exactly how you assert "grep found nothing". So a check that
never executed reported PASS, indefinitely. evidgate now tells "the command did not run"
apart from "the command ran and returned this code"; only the second can pass.

**2. The check had nothing to check.** A 172-file manifest where every entry was a
source made the `figures` pack report **3 PASS with 100% coverage**: with no derivative
there is nothing to compare, so every rule held vacuously. There is now a `GF0` check
whose only job is to fail when a manifest contains no derivative at all.

**3. Nobody ever asked the check to fail.** This one is silent by construction: a rule
written straight into CI and never run against a broken version is an untested rule.
So `counter` — *how does this check go red* — is a required field, and a check without
it is refused at load time, not at run time.

## How it differs

| | typical linter | checklist (human) | evidgate |
|---|---|---|---|
| Who decides pass | the rule | a person ticking a box | the command + its exit code |
| What proves it | nothing | nothing | command, exit code, output tail, artifact hash, timestamp |
| If the rule silently stops working | silent | silent | `evidgate mutate` reports "detection 1/1" or "NOT caught" |
| Where "what is left" lives | nowhere | another sheet | the same ledger line |
| Can a rule exist with no way to fail | yes | yes | **refused at load time** |

`counter` is a required field, so **a gate that cannot fail is not a gate, it is a wish.**

## 30 seconds

```bash
pip install evidgate
cd <your project>
evidgate init --dir .        # writes evidgate.yaml; picks a file that actually exists
evidgate doctor --dir .      # yaml parseable? every command resolvable? — before blaming the project
evidgate run --dir .         # ledger + verdicts; exit 1 = blocked

# straight from a clone, no install needed (stdlib only):
./bin/evidgate --version
```

If `doctor` prints `BAD`, fix that first — the most common failure is a `method` whose
command is not on `PATH`, or a `method` that needs `shell:` and does not declare it.

Running the bundled three-domain example:

```console
$ evidgate run --dir examples/mixed
evidgate 0.9.2 · mixed-delivery (fictional) · 7 checks
   D1 FAIL(红)  草稿里的绝对化词带范围或检索日期  ─  -exit 2 (want 0) | got: L3 [首次实现] 本方案首次实现全自动估价流程。 | [absolutes] 1 finding(s)  (exit 2)
   D2 DIFF(黄)  草稿里的统计数字带口径  ─  -exit 3 (want 0) | got: L3 抽样调参后误差降低 18.4%。 | [numeral_scope] 1 finding(s)  (exit 3)
   A1 PASS     产物存在且非空  ─  +exit 0 (want 0) ; +regex OK ─ \d -> 3
   A2 FAIL(红)  正本与其派生副本逐字节一致  ─  -exit 1 (want 0)
   C1 PASS     代码单测全绿  ─  +exit 0 (want 0)
   C2 PASS     源码里没有明文密钥  ─  +exit 0 (want 0) ; +not_contains OK:api_key ; +not_contains OK:secret_key
   C3 PASS     源码里没有残留 TODO  ─  +exit 1 (want 1)

PASS 4 · DIFF(黄) 1 · FAIL(红) 2 · 待补 0 · 未覆盖 0 | coverage 7/7 (100.0%)
RELEASE BLOCKED  blocked by D1, A2
note: PASS 表示「证据存在且可复现」，不表示数值本身正确。
```

The example deliberately mixes Chinese check names with English output: the shipped
`prose` rules target Chinese drafts, and one ledger holds either language.

Red blocks the release. Yellow goes to a confirmation list. **待补 is never "done".**
Exit code 1 means blocked — a non-zero run cannot be reported as a pass.

## What it finds on real things

| target | size | result |
|---|---|---|
| Mature open-source repos | 8 | **0 findings** |
| Personal deliverable repos | 4 | **3 real defects** |
| A real paper draft | 581 sentences | 222 findings before calibration → **32** |

The zero is the boundary, not a weakness: mature projects do not commit credentials or
leave `.bak` files behind. Personal repos produced a crash on a broken symlink, the
vacuous-green manifest above, and a `suggest` that could not see `.fig`/`.dia`/`.dat` as
figure sources. This tool is for **the last look before you hand something over**.

## Who this is for

- You are about to hand a draft, a report, an application package or a build directory to
  someone who will ask "where did this number come from?"
- You work across several windows or agents, and "done" from another context is a claim
  you would like to check rather than trust.
- You already run tests and linters, and none of them leave a record of *what was
  verified, with which command, when*.

## Who it is not for

- **Content correctness** — whether the number is right or the argument holds.
- **Typography, terminology, AI-tone linting** — [Vale](https://vale.sh/) and
  `deliverable-qa` have far more rules for that.
- **Auditing mature repositories** — expect zero findings.
- **Approval workflows** — no roles, no multi-user sign-off; this is a single-user CLI.

## Commands

```bash
evidgate init --dir <proj>                       # starter evidgate.yaml
evidgate suggest --dir <proj> [--write]          # read the disk, name the pack that applies
evidgate doctor --dir <proj>                     # yaml + command resolvability, before you blame the project
evidgate run --dir <proj> [--only C1,P2]         # run + rebuild the ledger; exit 1 = blocked
evidgate resume --dir <proj>                     # rerun only unresolved checks
evidgate report --dir <proj>                     # gate_report.md: table, yellows, unverified, verdict
evidgate mutate --dir <proj> --baseline A --mutant B [--only C1]   # does the check actually go red?
evidgate prose-init --dir <proj> --file <draft>  # append the Chinese prose checks (P1..P5)
evidgate artifact-init --dir <proj> --out artifacts.json   # scan a directory into a manifest
evidgate artifact-update --dir <proj>            # recompute an artifact's own md5 (never source_md5)
evidgate artifact-stamp --dir <proj> --path P    # after regenerating: record the source hash
evidgate pack [list|show <name>]                 # what a pack expands to
```

## Documentation

| doc | covers |
|---|---|
| [Writing a check](docs/writing-a-check.md) | `method` forms, `optional`, every `expect` clause, the evidence self-check, adding your own domain |
| [Artifact plugin](docs/artifact-plugin.md) | the five manifest rules, why `stale` hashes instead of comparing mtimes, `orphan` scope and cost, the one writer of `source_md5` |
| [Prose plugin](docs/prose-plugin.md) | the five Chinese rules, the calibration story, sentence boundaries, `EVIDGATE_EVIDENCE` |
| [Shell and Windows](docs/shell-and-windows.md) | why no shell by default, Git Bash discovery, the Windows false green |
| [suggest and packs](docs/suggest-and-packs.md) | the first command, the three packs and their parameters |

## Examples

All examples are **fictional**; every defect is planted on purpose.

- `examples/mixed/` — prose + artifact + code in one ledger (the output above)
- `examples/` — a Chinese draft, six checks, 2 PASS / 2 DIFF / 2 FAIL
- `examples/figures/` — one SVG source, three derivatives, all three `stale` verdicts
  side by side
- `examples/artifact/` — one markdown source with two derivatives, four asset checks

Mutation demo:

```bash
./bin/evidgate mutate --dir examples --baseline examples/base --mutant examples/mut --only C1
# detection power: 1/1
```

## Scope

**Does not** verify that a reference exists or says what you claim — use
[refchecker](https://github.com/markrussinovich/refchecker) for that.
**Does not** detect AI-generated text, judge typography, or decide whether a number is
correct.
**Does** check that the evidence you claim for your own statements, numbers and
artifacts is real, reproducible and recorded — in whatever domain your command can
observe.

`prose` is a writing prompt, not a proofreader. Measured honestly: of 22 problems found
by reading a draft by hand, and 26 reported by the rules, the overlap was small.

## Attribution

Evidence triples and three-state verdicts follow obra/superpowers'
`verification-before-completion`; the evidence-gate framing follows TestifySec Pushgate.
What is new here is listed in [ATTRIBUTION.md](ATTRIBUTION.md).

## License

MIT