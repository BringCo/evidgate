# evidgate

**Release gates for documents.** Every check is a command, every verdict carries evidence,
and one ledger line is the check, its proof, its resume point and its release decision.

Built for the case where an agent (or you, at 2 a.m.) wrote a paper, a report or an
application package, and someone will eventually ask: *"这数据哪来的？什么口径？"*

```console
$ evidgate run --dir examples
evidgate 0.1.0 · campus-book-pricing (fictional example) · 6 checks
   C1 PASS     交付产物存在且非空  ─  +exit 0 (want 0) ; +regex OK ─ \d -> 1
   P1 PASS     正文可分词（分母可算）  ─  +exit 0 (want 0) ; +regex OK ─ 正文句 \d+ -> 正文句 9
   P2 FAIL(红)  绝对化词带范围或检索日期  ─  -exit 2 (want 0) | got: L15 [首次] 本系统首次实现… | [absolutes] 1 finding(s)
   P3 DIFF(黄)  结论句带引用或实测标记  ─  -exit 3 (want 0) | got: L15 结果说明该方法优于传统人工定价。…
   P4 DIFF(黄)  统计数字带口径  ─  -exit 3 (want 0) | got: L16 …预估误差降低 21.2%…
   P5 FAIL(红)  正文引用与文献表双向对上  ─  -exit 2 (want 0) | got: 文献表 [8] 正文未引用

PASS 2 · DIFF(黄) 2 · FAIL(红) 2 · 待补 0 | coverage 6/6 (100.0%)
RELEASE BLOCKED  blocked by P2, P5
```

Red blocks the release. Yellow goes to a confirmation list. **待补 is never "done".**
Exit code 1 means blocked — a non-zero run can not be reported as a pass.

## Why this is not another linter

| | typical linter | checklist (human) | evidgate |
|---|---|---|---|
| Who decides pass | the rule | a person ticking a box | the command + its exit code |
| What proves it | nothing | nothing | command, exit code, output tail, artifact hash, timestamp |
| What if the rule stops working | silent | silent | `evidgate mutate` reports "detection 1/6" |
| Where "what is left" lives | nowhere | another sheet | the same ledger line |
| Can a rule exist without a way to fail | yes | yes | **refused at load time** |

That last row is the design constraint: `counter` (how this check goes red) is a
required field. A gate that cannot fail is not a gate, it is a wish.

## Install

```bash
git clone https://github.com/BringCo/evidgate && cd evidgate
./bin/evidgate --version        # zero-install entry point, stdlib only

# or, as a package
pip install evidgate
```

Python ≥ 3.9, no third-party dependencies. PyYAML is used if present; a
built-in parser covers the examples otherwise.

## Commands

```bash
evidgate init --dir <proj>                      # starter evidgate.yaml
evidgate prose-init --dir <proj> --file draft.md # add the Chinese prose checks (P1..P5)
evidgate run --dir <proj> [--only C1,P2]         # run + rebuild the ledger; exit 1 = blocked
evidgate resume --dir <proj>                     # rerun only unresolved checks
evidgate report --dir <proj>                     # gate_report.md: table, yellows, unverified, verdict
evidgate mutate --baseline A --mutant B [--only C1]  # does the check actually go red?
evidgate prose scan --file draft.md --rule absolutes  # one rule, standalone
```

## Writing a check

```yaml
checks:
  - cid: C1
    name: 交付产物存在且非空
    method: test -s report.md && wc -c < report.md
    expect: exit:0; regex:\d
    counter: 删掉 report.md 或清空它，本项必须变红
    severity: red        # red = blocking, yellow = non-blocking (DIFF)
```

`expect` clauses (join with `;`, all must hold):

| clause | meaning |
|---|---|
| `exit:0` | exit code equals |
| `contains:TEXT` | stdout contains |
| `not_contains:TEXT` | stdout does not contain |
| `regex:PATTERN` | stdout matches (multiline) |
| `lines>=N` / `lines<=N` | non-empty stdout line count |
| `file:PATH` | path exists (byte size + md5 recorded) |
| `md5:PATH=HEX` | file hash matches |
| `manual` | no command assertion; stays 待补 and blocks |

## Prose rules (Chinese)

`evidgate prose scan --rule <name>` — each rule exits `0` clean, `2` blocking, `3` advisory:

| rule | catches |
|---|---|
| `denominator` | sentence count of the body (info; makes coverage countable) |
| `absolutes` | 首次/首创/唯一/未见 without a search date or scope |
| `uncited` | claim verbs (说明/证明/表明…) with no citation and no measured marker |
| `numeral_scope` | ρ / R² / 倍 / % sentences with no `n`, protocol or script path |
| `citation_chain` | `[n]` in the body missing from the bibliography, and listed-but-never-cited entries |

These encode lessons from real review rounds. They are heuristics, not oracles —
yellow is where "a human should look", which is exactly why yellow exists.

## Example

`examples/` is a **fictional** project (campus second-hand book pricing). Its planted
defects — an unsupported 首次, an uncited comparison, a percentage with no `n`, a
dangling `[9]` — are there so `run` and `mutate` can be demonstrated without
publishing anyone's real data.

```bash
cd examples && ../bin/evidgate run --dir .          # 2 PASS / 2 DIFF / 2 FAIL
cd .. && ./bin/evidgate mutate --dir examples \
    --baseline examples/base --mutant examples/mut --only C1   # detection 1/1
```

## Scope

- **Does not** verify that a reference exists or says what you claim — use
  [refchecker](https://github.com/markrussinovich/refchecker) or similar for that.
- **Does not** detect AI-generated text.
- **Does** check that the evidence you claim for your own numbers and statements is
  real, reproducible and recorded.

## Attribution

Evidence triples and three-state verdicts follow obra/superpowers'
`verification-before-completion`; the evidence-gate framing follows TestifySec
Pushgate. What is new here is listed in [ATTRIBUTION.md](ATTRIBUTION.md).

## License

MIT
