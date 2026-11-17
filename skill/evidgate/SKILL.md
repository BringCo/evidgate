---
name: evidgate
description: "Use when 能不能交付/证据还在不在/要台账。claims → commands + ledger, with a counter-test per claim."
---

# evidgate

Release gates for whatever you hand over. It does not judge whether the content is
right; it judges whether the evidence you claim for it is **real, still there, and
reproducible**, and writes that into one ledger you can hand over.

One line of the ledger = one check = its command = its evidence = its resume point =
its release decision.

## When to use it

Use it when:

- a deliverable is about to leave your hands (report, paper draft, application
  material, a built artifact directory), or is handed to another window or person;
- the user asks "能不能交付 / 每句话有依据吗 / 帮我过一遍再发 / 这个数字哪来的";
- a check that used to pass may have quietly stopped working.

Do not use it for: typography, term consistency, AI-sounding prose (`deliverable-qa`,
Vale do those better); whether a cited paper really says what you claim (`refchecker`).
The `prose` rules only ask "does this sentence carry a scope and a citation" — never
"is this number correct".

Hand off rather than overlap: `claim-by-claim-audit` decides what a specific sentence
rests on; `paper-claim-gates` holds the writing-time rules. evidgate's job is narrower —
express the claim as a command and keep the exit code. If a claim cannot be written as
an assertion, it stays with those two, not here.

## First minute

<!-- skill-check:start -->
```bash
evidgate --version
evidgate suggest --dir .
evidgate init --dir .
evidgate doctor --dir .
evidgate run --dir .
evidgate prose-init --dir . --file draft.md
evidgate resume --dir .
evidgate report --dir .
evidgate artifact-init --dir . --out artifacts.json
evidgate pack
```
<!-- skill-check:end -->

`suggest` reads the disk and names the pack that applies — an empty yaml is the worst
first minute. `doctor` checks the yaml and the commands before you blame the project.
`exit 1` from `run` means blocked: **never report success from a non-zero run.**

## What one check looks like

Two forms work; both carry a `counter` (see below):

```yaml
checks:
  - cid: P2                 # builtin: runs in-process, same behaviour on every OS
    name: 绝对化词带范围或检索日期
    method: builtin:prose:absolutes draft.md
    expect: exit:0
    counter: 写一句「本文首次实现 X」且不给检索日期，本项必须变红
    severity: red

  - cid: A1                 # shell form: declare the shell, every time
    shell: bash
    name: 产物存在且非空
    method: test -s build/out.txt && wc -c < build/out.txt
    expect: exit:0; regex:\d
    counter: 清空 build/out.txt，本项必须变红
    severity: red
```

The loader refuses these at load time, not at run time:

- **`counter` is mandatory** — "how does this go red". A check that cannot fail is a
  wish, not a gate.
- `not_contains:` needs an `exit:` clause, otherwise empty output makes it vacuously true.
- A `method` using shell syntax (`&&`, `|`, `>`, `<`, `$(`, backticks) **must** declare
  `shell:`. `doctor` reports the omission as BAD. On Windows prefer `builtin:` checks —
  they need no shell at all.
- Anything with a deterministic exit code is checkable. `exit:1` is a legitimate
  expectation — that is how "no matches" gets asserted.

## The five verdicts

| verdict | meaning | what to do |
|---|---|---|
| `PASS` | the command ran and its assertion held | nothing; it is evidence, not a guarantee the content is right |
| `DIFF(黄)` | ran, but the evidence is incomplete (a number without scope, a derivative not regenerated) | goes to the **confirmation list**; a human decides |
| `FAIL(红)` | the assertion did not hold | blocks the release |
| `PENDING(待补)` | declared, not yet evidenced | **never counts as done** |
| `SKIP(未覆盖)` | not applicable here | not coverage — say so, never round it up |

Red blocks; yellow is a list; 待补 is not done. Two states is not enough, which is why
there are five.

## Commands

```bash
evidgate init --dir <proj> [--packs figures,build] [--force]
evidgate suggest --dir <proj> [--write]        # --write also writes evidgate.yaml
evidgate doctor --dir <proj>
evidgate run --dir <proj> [--only C1,P2]
evidgate resume --dir <proj>
evidgate report --dir <proj>
evidgate mutate --dir <proj> --baseline <good> --mutant <planted-defect> [--only C1]
evidgate prose-init --dir <proj> --file <draft.md>
evidgate prose scan --file <draft.md> --rule <absolutes|numeral_scope|uncited|citation_chain|denominator>
evidgate artifact-init --dir <proj> [--out artifacts.json] [--force]
evidgate artifact-stamp --dir <proj> --path <file>      # after regenerating a derivative
evidgate artifact-update --dir <proj> --manifest artifacts.json
evidgate pack [list|show <name>]
```

`mutate` is the one command that proves the gates are alive: it runs the same checks
against a good tree and against a copy with one planted defect, then reports
`detection power: 1/1` or `NOT caught`.

## Troubleshooting

1. **`doctor` says BAD** — fix that first; the project is not at fault yet. Either the
   yaml does not parse, or a command is not on `PATH`, or a `method` needs a `shell:` it
   does not declare.
2. **Windows** — `builtin:` checks are the only ones guaranteed to work. Shell checks
   need Git Bash; without it they go red with a clear message instead of passing quietly.
3. **The `build` pack finds nothing on mature open-source repos** — that is correct, not a
   bug. Mature projects do not commit secrets or leave `.bak` files. Its value is the last
   look at your own deliverable before you hand it over; do not sell it as an audit tool
   for other people's repositories.

## Working rules

- Never edit a verdict by hand, and never rebuild the ledger to make it look green. The
  ledger is rebuilt from execution; `artifact-stamp` is the only writer of `source_md5`,
  because anything else could wash a stale derivative into a fresh one.
- A green check whose row carries no evidence is not green.
- Yellow items go into the confirmation list — never into "done".
- When reporting to the user, quote the ledger rows (cid, verdict, exit code) rather than
  a summary you wrote yourself.