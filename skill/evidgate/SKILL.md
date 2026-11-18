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
- the deliverable restates an official notice, a spec, or another document, and you need
  to know whether a clause of it went missing — that is the `sources` pack, below;
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
evidgate init --dir <proj> --packs sources:src=notice.pdf,doc=plan.md   # the one pack that needs paths
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

## The `sources` pack

`packs: sources:src=<one-hand source>,doc=<what you wrote from it>` — clause coverage
between the two. `suggest` spots "a source PDF and documents next to it" and prints the
line with both paths filled in; bare `sources` keeps the `spec.txt`/`draft.md`
placeholders and dies on first run.

It exists because of a measured failure: a plan restated five of six requirements from an
official notice, cited the notice as its source, and dropped the sixth — the only clause
expressed with 也可, carrying no obligation word. Source-existence checks passed; every
keyword filter passed.

- Splits the source by **clause number** (`1.` / `二、` / `附件`), not by line and not by
  obligation word. Line-splitting puts the dropped clause outside the sample.
- n-gram coverage, n=4, threshold 0.05. The dropped clause measured 0.00; the five present
  ones 0.38–0.83.
- **Yellow, always.** A low score means "shares no wording", which is either a dropped
  clause or a clause this document never needed to restate. Only a human can tell those
  apart, so it goes to the confirmation list and never to red.
- Limits, measured: finds a **whole missing clause, not a half-copied one** (0.05–0.11 is
  noise territory); one `doc` per run — three documents means three runs; deleting one
  sentence moves a score by ~0.02, so a stable score is **not** proof of faithful
  restatement. Clause count is reported; clauses skipped as bare section headings are
  counted out loud.
- Needs clause numbers and a text layer. A scanned PDF has neither → exit 2 (declined, not
  passed). Install `poppler-utils` for `pdftotext`.

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
4. **`sources` exits 2** — it declined to judge; that is not a pass. Causes: the source has
   no clause numbers, no text layer (scanned PDF, missing `pdftotext`), or `--src` and
   `--doc` point at the same file.

## Sources must be fresh (the half `artifact-stamp` does not cover)

`artifact-stamp` stops a stale *derivative* from being sold as fresh. The mirror failure is a
stale *source*: a report, a status file, a screenshot describing an older reality than the one
you are answering about. A citation that resolves only proves the file exists.

Measured failure: answered "cloud runs the V4 frontend" from a stop-point file dated three days
earlier, while a report written one day later recorded the user reversing that decision — every
existence check passed, the answer was wrong. Same session, second instance: read a 02:06
wrap-up as "the full picture" and missed a 23:24 report from the same night that had already
shipped the feature.

Rules, when a claim's evidence is a report or status doc:

- **Scan by mtime, never by filename.** `ls -t` over the last 48 hours *and across days*; the
  `0N_` prefix says nothing about age, and a same-day `02_…` can be hours newer than the `03_…`
  you happened to open first.
- **Stop-point / index files expire first.** If `00_…_READ_FIRST.md` is older than the newest
  report, say "stop-point is from <date>, stale" before quoting it — never present it as current.
- **Conflicts resolve to newest mtime + a first-hand probe** (source tree, DB, live endpoint).
  Older reports are history, not status.
- **Make it a gate, not a habit.** Now built in — `builtin:source:fresh` (evidgate ≥ 0.10.0,
  `plugins/source.py`), so it works on every OS with no shell and no PATH:

```yaml
checks:
  - cid: F1
    name: 引用的报告是同主题最新（不存在更新的同主题报告）
    method: builtin:source:fresh --cited 每日报告/2026-11/2026-11-18/银光之慧/03_收口.md --glob '0*_*.md'
    expect: exit:0
    counter: 在同目录放一份 mtime 更新、同主题的报告，本项必须变红
    severity: red
```

  Output is self-describing: green prints `OK cited=… mtime=… md5=… scanned=N newer=0`;
  red prints `NEWER …` plus each newer file with its mtime, and exit 1. A missing cited file
  exits **2 (DECLINED)** — never a pass. Flags: `--cited` (required), `--dir` (scope, defaults
  to the cited file's folder), `--glob` (default `*.md`), `--all` (no 10-line cap),
  `--recursive` (walk subfolders, capped at 5000 files).
  **One command, no yaml:** `evidgate source --cited <file> [--dir <topic folder>]`.
  Scan is **one level deep by default** — on a 9p mount (/mnt/c in WSL) a recursive walk of a
  month of reports took 23s and of the whole tree over 60s, while "anything newer in this
  topic's folder" is answered by one listing (1.6s, mostly interpreter startup).
  Backup trees (`_历史原稿/`, `_废料桶/`, `99_历史与参考/`) are skipped in recursive mode: a dated
  snapshot is an older version carrying a fresh mtime and reds a correct citation.
  The same check is also wired as a Hermes `post_tool_call` hook
  (`~/.hermes/hooks/source_fresh_gate.py`), so reading an outdated report injects a warning
  without anyone having to remember to run it.

  Shell form, if you must (no evidgate available):

```yaml
checks:
  - cid: F1s
    shell: bash
    method: |
      n=$(find "$RPT_DIR" -name "$GLOB" -newer "$CITED" | wc -l); echo "$n"; test "$n" -eq 0
    expect: exit:0; regex:^0$
    counter: 放一份 mtime 更新、同主题的报告，本项必须变红
    severity: red
```

- Report the cited file's mtime beside the claim, the same way you report an exit code.

**Limits, measured against a live run** (evidgate 0.10.0.post1, three-state test: cite an
older report → `F1 FAIL(红) RELEASE BLOCKED`; cite the newest → `PASS`; add one more newer
file → red again, so the counter holds):

- **It must be scoped or it cries wolf.** `find $RPT_DIR -newer` reds on *any* newer file,
  including unrelated threads. Point `RPT_DIR` at one topic's folder (or add a `-name` glob);
  in the test an unrelated file `04_d.md` alone flipped it red.
- **It only sees mtime, and mtime lies.** `cp -p` / sync tools carry the old mtime across, so a
  rewritten report can look ancient and pass. Pair it with a content hash on the files you
  actually cite (`md5sum`), and treat "no newer mtime" as "no newer mtime", not "content fresh".
- It cannot tell whether the report itself is *correct* — only that no newer same-topic one
  exists. Conflicts still resolve to a first-hand probe (source tree, DB, live endpoint).
- **Same-second writes are indistinguishable on 9p** (/mnt/c from WSL): two files created in
  one second report the identical mtime (`1794975875.240521789` for both, measured), so
  "report 02 was written right after 01" can pass as "no newer file". If two reports of the
  same topic share a timestamp to the second, break the tie with the content (which one quotes
  the other) instead of trusting the order.

## Working rules

- Never edit a verdict by hand, and never rebuild the ledger to make it look green. The
  ledger is rebuilt from execution; `artifact-stamp` is the only writer of `source_md5`,
  because anything else could wash a stale derivative into a fresh one.
- A green check whose row carries no evidence is not green.
- Yellow items go into the confirmation list — never into "done".
- When reporting to the user, quote the ledger rows (cid, verdict, exit code) rather than
  a summary you wrote yourself.