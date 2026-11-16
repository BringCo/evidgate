"""The ledger table.

Why one table: a report and a ledger kept apart drift. Here a line carries the check,
its command, its counter-test, the evidence, the timestamp and the verdict -- so
"what is left" and "what proves it" are the same read.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from ..core.check import Check
from ..core.gate import LABEL, Verdict

HEADER = ("| cid | check | method | expect | counter-test | sev | status | evidence | ts |\n"
          "|---|---|---|---|---|---|---|---|---|\n")


def _cell(s: str, limit: int = 90) -> str:
    s = (s or "").replace("|", "\\|").replace("\n", " ").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _evidence_cell(v: Optional[Verdict]) -> str:
    if v is None:
        return "—"
    ev = v.evidence
    bits = [f"`{_cell(ev.command, 60)}`", f"exit={ev.exit_code}"]
    if ev.stdout.strip():
        bits.append(f"out: {_cell(ev.key_output(2), 60)}")
    for a in ev.artifacts:
        if a.exists:
            bits.append(f"{a.path} {a.size}B md5={a.md5[:8]}")
        else:
            bits.append(f"{a.path} MISSING")
    bits.append(f"{ev.seconds}s")
    return _cell(" · ".join(bits), 200)


def render(checks: List[Check], verdicts: Dict[str, Verdict],
           project: str = "project", prev: Optional[Dict[str, dict]] = None) -> str:
    prev = prev or {}
    body = []
    for c in checks:
        v = verdicts.get(c.cid)
        if v is None and c.cid in prev and prev[c.cid]["status"] not in ("—", ""):
            # resumed run: keep the row we already verified instead of blanking it
            row = prev[c.cid]
            body.append("| " + " | ".join([
                c.cid, _cell(c.name, 46), f"`{_cell(c.method, 70)}`",
                f"`{_cell(c.expect, 40)}`", _cell(c.counter, 46), c.severity,
                row["status"], _cell(row["evidence"], 200), row["ts"],
            ]) + " |")
            continue
        body.append("| " + " | ".join([
            c.cid,
            _cell(c.name, 46),
            f"`{_cell(c.method, 70)}`",
            f"`{_cell(c.expect, 40)}`",
            _cell(c.counter, 46),
            c.severity,
            LABEL.get(v.status, "—") if v else "—",
            _evidence_cell(v),
            (v.evidence.started_at if v else "—"),
        ]) + " |")

    counts = {"PASS": 0, "DIFF": 0, "FAIL": 0, "PENDING": 0}
    for c in checks:
        v = verdicts.get(c.cid)
        if v:
            counts[v.status] = counts.get(v.status, 0) + 1
    total = len(checks)
    done = counts["PASS"] + counts["DIFF"] + counts["FAIL"]
    pct = 0 if total == 0 else round(100 * done / total, 1)

    head = [
        f"# evidgate ledger · {project}",
        "",
        "> One line == one check == one piece of evidence == one resume point.",
        "> Rebuild it with `evidgate run`; do not edit verdicts by hand.",
        "",
        HEADER.rstrip("\n"),
    ]
    tail = [
        "",
        "## progress",
        "",
        f"- total: {total} · PASS {counts['PASS']} · DIFF(黄) {counts['DIFF']} · "
        f"FAIL(红) {counts['FAIL']} · 待补 {counts['PENDING']}",
        f"- coverage: {done}/{total} ({pct}%)",
        "",
    ]
    return "\n".join(head + body) + "\n" + "\n".join(tail)


def build(path: str, checks: List[Check], verdicts: Dict[str, Verdict],
          project: str = "project", previous: Optional[Dict[str, dict]] = None) -> str:
    """Write the ledger. Idempotent: same checks + same verdicts -> same bytes."""
    text = render(checks, verdicts, project)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return text


_ROW = re.compile(r"^\|\s*([A-Za-z]+\d+)\s*\|")


def load_rows(path: str) -> Dict[str, dict]:
    """Parse existing ledger rows -> {cid: {status, evidence, ts}} (for resume)."""
    if not os.path.exists(path):
        return {}
    rows: Dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for line in lines:
        m = _ROW.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        rows[cells[0]] = {"status": cells[6], "evidence": cells[7], "ts": cells[8]}
    return rows


def resume_cids(checks: List[Check], rows: Dict[str, dict]) -> List[str]:
    """Checks never run, or run but unresolved, are the resume set."""
    out = []
    for c in checks:
        row = rows.get(c.cid)
        if not row or row["status"] in ("—", "待补", ""):
            out.append(c.cid)
    return out
