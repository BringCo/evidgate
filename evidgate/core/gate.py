"""Three-state gate: PASS / DIFF (yellow) / FAIL (red).

Two states is not enough. Forcing every "has evidence but differs from intent" item
into FAIL makes a run that can never be green; nobody looks at the report after that.
Downgrading red to yellow is worse: it is a fake pass.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import List, Tuple

from .check import Check
from .evidence import Evidence, artifacts_in, collect

PASS, DIFF, FAIL, PENDING, SKIP = "PASS", "DIFF", "FAIL", "PENDING", "SKIP"
LABEL = {PASS: "PASS", DIFF: "DIFF(黄)", FAIL: "FAIL(红)",
         PENDING: "待补", SKIP: "SKIP(未覆盖)"}


@dataclass
class Verdict:
    cid: str
    status: str
    detail: str
    evidence: Evidence

    @property
    def done(self) -> bool:
        return self.status in (PASS, DIFF, FAIL)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def evaluate(check: Check, ev: Evidence, cwd: str = ".") -> Tuple[str, str]:
    """Return (status, detail). Pure function of check + evidence + cwd."""
    expr = check.expect.strip()
    if not expr or expr == "manual":
        return PENDING, "manual: no command assertion declared"

    notes: List[str] = []
    ok = True
    for clause in [c.strip() for c in expr.split(";") if c.strip()]:
        kind, _, arg = clause.partition(":")
        kind, arg = kind.strip(), arg.strip()

        if kind == "exit":
            want = int(arg)
            good = ev.exit_code == want
            note = f"exit {ev.exit_code} (want {want})"
            if not good and ev.exit_code == 127:
                note += (" | 命令未找到(127)：它不在 PATH 里。改用 "
                         "builtin:<plugin>:<rule>，或写绝对路径")
            elif not good:
                tail = ev.key_output(2) or (ev.stderr.strip().splitlines() or [""])[-1][:160]
                if tail:
                    note += f" | got: {tail}"
        elif kind == "contains":
            good = arg in ev.stdout
            note = f"contains {'OK' if good else 'MISSING'}:{arg}"
        elif kind == "not_contains":
            good = arg not in ev.stdout
            note = f"not_contains {'OK' if good else 'HIT'}:{arg}"
        elif kind == "regex":
            m = re.search(arg, ev.stdout, re.M)
            good = bool(m)
            note = f"regex {'OK' if good else 'MISS'} ─ {arg}" + (f" -> {m.group(0)[:40]}" if m else "")
        elif kind == "lines>=":
            n = len([l for l in ev.stdout.splitlines() if l.strip()])
            good = n >= int(arg)
            note = f"lines {n} (want >={arg})"
        elif kind == "lines<=":
            n = len([l for l in ev.stdout.splitlines() if l.strip()])
            good = n <= int(arg)
            note = f"lines {n} (want <={arg})"
        elif kind == "file":
            full = arg if os.path.isabs(arg) else os.path.join(cwd, arg)
            good = os.path.exists(full)
            note = f"file {'exists' if good else 'MISSING'}:{arg}"
        elif kind == "md5":
            path, _, want = arg.partition("=")
            full = path if os.path.isabs(path) else os.path.join(cwd, path)
            got = _md5(full) if os.path.exists(full) else ""
            good = got == want.strip()
            note = f"md5 {'MATCH' if good else 'MISMATCH'}:{path}"
        else:
            good, note = False, f"unknown clause '{clause}'"

        notes.append(("+" if good else "-") + note)
        ok = ok and good

    if ok:
        return PASS, " ; ".join(notes)
    return (FAIL if check.severity == "red" else DIFF), " ; ".join(notes)


def run_check(check: Check, cwd: str = ".") -> Verdict:
    ev = collect(check.method, cwd=cwd, timeout=check.timeout,
                 artifacts=artifacts_in(check.expect), shell=check.shell)
    if ev.command_not_found:
        # The command never ran. On Windows `grep ...` exits 1, which is exactly
        # what `expect: exit:1` ("grep found nothing") wants -- so a check can flip
        # to green without having looked at anything.
        hint = f" ({ev.not_found_hint})" if ev.not_found_hint else ""
        return Verdict(check.cid, SKIP if check.optional else FAIL,
                       f"命令未找到{hint}：检查没能执行，不能算通过", ev)
    status, detail = evaluate(check, ev, cwd=cwd)
    if check.optional and status in (FAIL, DIFF):
        return Verdict(check.cid, SKIP, "optional (未覆盖): " + detail, ev)
    gaps = ev.missing(needs_stdout=any(k in check.expect for k in ("contains", "regex", "lines")))
    if status in (PASS, DIFF) and gaps:
        # a green verdict built on incomplete evidence is not a green verdict
        status = PENDING if check.expect.strip() == "manual" else status
        detail += " | evidence gaps: " + ", ".join(gaps)
    return Verdict(check.cid, status, detail, ev)


def summarize(verdicts: List[Verdict]) -> dict:
    counts = {PASS: 0, DIFF: 0, FAIL: 0, PENDING: 0, SKIP: 0}
    for v in verdicts:
        counts[v.status] = counts.get(v.status, 0) + 1
    total = len(verdicts)
    done = counts[PASS] + counts[DIFF] + counts[FAIL] + counts.get(SKIP, 0)
    return {
        **counts,
        "total": total,
        "done": done,
        "coverage": 0.0 if total == 0 else round(done / total, 3),
    }


def release_allowed(verdicts: List[Verdict]) -> Tuple[bool, str]:
    """Red blocks. Yellow goes to a confirmation list. Pending is never 'done'."""
    fails = [v for v in verdicts if v.status == FAIL]
    pend = [v for v in verdicts if v.status == PENDING]
    if fails:
        return False, "blocked by " + ", ".join(v.cid for v in fails)
    if pend:
        return False, "unchecked: " + ", ".join(v.cid for v in pend)
    skips = [v for v in verdicts if v.status == SKIP]
    tail = "; yellow items go to the confirmation list"
    if skips:
        tail += f" ({len(skips)} optional/未覆盖: " + ", ".join(v.cid for v in skips) + ")"
    return True, "all red checks green" + tail
