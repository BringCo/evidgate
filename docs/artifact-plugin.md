[← back to README](../README.md)

# Plugin: artifact (manifest-driven)

Five checks derived from three rules that govern content assets: one asset has one
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
| `derivatives` | does the manifest contain at least one derivative at all? (with none, every other rule is vacuous) | red |
| `manifest` | is every registered file still present, and does a **derivative's** recorded md5 still match? | red |
| `stale` | did the source change since this derivative was generated? (compared by hash, not mtime) | yellow |
| `sync` | does a `same_as_source` derivative still equal its source? | red |
| `orphan` | is there a file in the scanned directory the manifest never registered? | yellow |

The gate's own files (`evidgate.yaml`, `evidgate_ledger.md`, `gate_report.md`) never count
as orphans — they are configuration and output, not deliverables.

## Why `stale` compares hashes, not file times

An earlier version used mtime and was wrong: `git clone`, unzip and `rsync` all stamp
"now", so the same example reported `1 PASS / 2 DIFF` in a working tree and
`2 PASS / 1 DIFF` after a clone. Hash comparison gives the same verdict in both.

What `stale` can and cannot say: it answers "did the source change since this stamp". It
cannot tell whether a derivative was ever in sync. A derivative with no `source_md5` is
reported as **cannot tell**, never as clean. Measured on a real figure directory (10 SVG
sources, 30 derivatives): before stamping, all 30 read "cannot tell"; the mtime heuristic
had called 10 of them stale, but that verdict was itself unreliable.

## Point `orphan` at the artifact directory

Measured on a real 17k-file project: scanning the repo root reported 6002 "unregistered"
files (sources, docs, `.bak` copies) — true but useless. Scanning only `build/` is the
intended use.

Cost matters too: the same 201 files took 0.001 s on ext4 and 0.818 s across a WSL
`/mnt/c` mount (≈800× per file), so width matters more than count on a mounted drive.

## Ignoring files

Files you never want registered (build logs, temp files) go in the manifest's `ignore`
list, matched with shell globs:

```json
{"root": ".", "ignore": ["*.log", "tmp/", "*.tmp"], "items": [...]}
```

## One writer for `source_md5`

`source_md5` has exactly one writer: **`artifact-stamp`**, called right after you
regenerate. `artifact-update` deliberately does *not* touch it. An earlier version did,
which meant a single command made every stale derivative look fresh without regenerating
anything — that is laundering, not gating.

```bash
evidgate artifact-stamp --dir . --path build/report.html   # only after regenerating
```
