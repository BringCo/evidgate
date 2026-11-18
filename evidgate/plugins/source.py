"""Source freshness: is there a newer document on the same topic than the one you cite?

`method: builtin:source:fresh --cited <file> [--dir DIR] [--glob '*.md'] [--all]`

The failure this catches, measured 2026-11-18: a claim cited a report that resolved fine
(the file exists, the grep matches) while a report written later on the same topic had
already superseded it. Existence checks pass; the answer is wrong. Same session, same
shape, twice: answered "cloud runs the V4 frontend" from a stop-point file three days
older than the report that recorded the user reversing that decision.

Scope is the whole point. Point --dir at ONE topic's folder (or narrow with --glob).
Scoped wrong, any newer file -- another thread's report sitting in the same tree -- reds
the check; the three-state test hit exactly that with an unrelated `04_d.md`.

What it does NOT do: it cannot tell whether the report is *correct*, only that no newer
same-topic one exists. And it sees mtime only -- `cp -p` and sync tools carry the old
mtime across, so a rewritten report can look ancient and pass. That is why the cited
file's md5 is printed: pair the two, and treat "no newer mtime" as "no newer mtime",
never as "content fresh".

Exit codes: 0 = cited file is the newest in scope; 1 = newer files exist (release
blocked); 2 = the check declined to run (bad arguments, missing file) -- never a pass.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import List

# Backup/history trees never count as "newer": a snapshot in `_历史原稿/` is an older
# version under a fresh mtime, and counting it reds the check for no reason (measured:
# a `_历史原稿/03_c.md` copy flipped a green check to FAIL).
SKIP_DIR_NAMES = {"_废料桶", "_历史原稿", "_历史索引", "99_历史与参考",
                  "node_modules", "__pycache__", "dist", ".git"}

RULES = ("fresh",)


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse(argv: List[str]):
    cited = None
    root = None
    pat = "*.md"
    show_all = False
    recursive = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--cited" and i + 1 < len(argv):
            cited = argv[i + 1]; i += 2; continue
        if a == "--dir" and i + 1 < len(argv):
            root = argv[i + 1]; i += 2; continue
        if a == "--glob" and i + 1 < len(argv):
            pat = argv[i + 1]; i += 2; continue
        if a == "--all":
            show_all = True; i += 1; continue
        if a == "--recursive":
            recursive = True; i += 1; continue
        if a.startswith("--"):
            raise SystemExit(f"unknown option {a!r}; have --cited --dir --glob --all --recursive")
        if cited is None:
            cited = a; i += 1; continue
        raise SystemExit(f"unexpected argument {a!r}")
    if not cited:
        raise SystemExit("missing --cited <file>")
    return cited, root, pat, show_all, recursive


def _iter_scope(root: str, pat: str, recursive: bool):
    """Files in scope. One level by default: on a 9p mount (/mnt/c, WSL) a recursive walk of a
    big tree stats thousands of files and took >60s in the live test, while the actual question
    -- "anything newer in this topic's folder" -- is answered by one listing. --recursive opts in,
    with a hard cap so a wrong scope fails fast instead of hanging."""
    import fnmatch

    if not recursive:
        for name in sorted(os.listdir(root)):
            if not fnmatch.fnmatch(name, pat):
                continue
            path = os.path.join(root, name)
            if os.path.isfile(path):
                yield path
        return

    budget = 5000
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in SKIP_DIR_NAMES]
        for name in filenames:
            if not fnmatch.fnmatch(name, pat):
                continue
            budget -= 1
            if budget < 0:
                print(f"DECLINED scope over 5000 files under {root}; narrow --dir or drop --recursive")
                return
            yield os.path.join(dirpath, name)


def run(rule: str, argv: List[str]) -> int:
    if rule not in RULES:
        raise SystemExit(f"unknown source rule {rule!r}; have: {', '.join(RULES)}")

    cited, root, pat, show_all, recursive = _parse(argv)
    if not os.path.isfile(cited):
        print(f"DECLINED cited file does not exist: {cited}")
        return 2

    root = root or os.path.dirname(os.path.abspath(cited)) or "."
    if not os.path.isdir(root):
        print(f"DECLINED --dir is not a directory: {root}")
        return 2

    cited_real = os.path.realpath(cited)
    cited_mtime = os.path.getmtime(cited)

    scanned = 0
    newer = []
    for path in _iter_scope(root, pat, recursive):
        if os.path.realpath(path) == cited_real:
            continue
        scanned += 1
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        if mt > cited_mtime:
            newer.append((mt, path))

    newer.sort(reverse=True)
    head = (f"cited={cited} mtime={_iso(cited_mtime)} md5={_md5(cited)[:12]} "
            f"scope={root} glob={pat} scanned={scanned} newer={len(newer)}")

    if not newer:
        print(f"OK {head}")
        return 0

    print(f"NEWER {head}")
    for mt, path in (newer if show_all else newer[:10]):
        print(f"  newer: {_iso(mt)}  {path}")
    if not show_all and len(newer) > 10:
        print(f"  ... {len(newer) - 10} more (use --all)")
    print("VERDICT citation is stale: read the newer file(s) above before answering from it")
    return 1