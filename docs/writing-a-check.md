[← back to README](../README.md)

# Writing a check

## One ledger, several domains

The engine does not know what a document is. It knows `command`, `expect`, `counter`,
`severity` and an exit code. Seven checks from three different worlds can share one table
and one release decision:

| domain | example check | assertion |
|---|---|---|
| prose (a drafted document) | 绝对化词是否带检索日期或范围 | `exit:0` on a prose rule |
| artifact (a produced file) | 产物非空 / 正本与派生副本逐字节一致 | `regex:\d`, `cmp -s` |
| code (what produced the artifact) | 单测全绿 / 没有明文密钥 / 没有残留 TODO | `exit:0`, `not_contains:`, `exit:1` |

That last row is worth noticing: `grep -rn TODO src/` **asserts `exit:1`** — "no match"
is a legitimate expectation. Anything with a deterministic exit code is checkable.

## The shape of a check

```yaml
checks:
  - cid: A2
    name: 正本与其派生副本逐字节一致
    method: cmp -s src/app.py src/app.py.bak
    expect: exit:0
    counter: 改常量但忘了同步 .bak，本项必须变红
    severity: red        # red = blocking, yellow = non-blocking (DIFF)
```

`counter` is not optional. A check without one is refused at load time: *a gate that
cannot fail is not a gate, it is a wish.*

## `method`: two forms

| form | when |
|---|---|
| `cmp -s a b` / any shell command | your own script or tool. Must be resolvable — `doctor` tells you if it is not |
| `builtin:prose:absolutes draft.md` | checks shipped with evidgate; dispatched **in-process**, so no `PATH` involved |

## Optional checks

Add `optional: true` when a check only applies to some setups (a missing input, an
absent service). A failing optional check becomes `SKIP(未覆盖)` — listed in the report,
counted as handled, **never blocking**. Without it, "my project has no such file" would
show up as a red failure, which is how a gate loses its audience.

## `expect` clauses

Join with `;`; all must hold.

| clause | meaning |
|---|---|
| `exit:N` | exit code equals (any value — `exit:1` is a valid expectation) |
| `contains:TEXT` / `not_contains:TEXT` | stdout contains / does not contain |
| `regex:PATTERN` | stdout matches (multiline) |
| `lines>=N` / `lines<=N` | non-empty stdout line count |
| `file:PATH` | path exists (byte size + md5 recorded) |
| `md5:PATH=HEX` | file hash matches |
| `manual` | no command assertion; stays 待补 and blocks |

## The evidence self-check

An assertion that needs stdout (`contains` / `regex` / `lines`) fails if the command
printed nothing — a `not_contains` on empty output would otherwise be a tautology.

Likewise `not_contains` without an `exit:` clause is refused at load time: if the command
dies and prints nothing, the assertion holds vacuously and the check reports green on a
missing file.

## Adding a domain

No `core/` changes needed: write a script that exits 0 / 2 / 3 and declare it as a check.
That is the whole plugin contract.
