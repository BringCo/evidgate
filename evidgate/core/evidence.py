"""Evidence: fresh, verifiable, traceable.

A check that cannot show *what was run*, *what came back*, and *when* did not run.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Artifact:
    path: str
    exists: bool
    size: int = 0
    md5: str = ""


@dataclass
class Evidence:
    command: str
    exit_code: Optional[int]
    stdout: str
    stderr: str
    seconds: float
    started_at: str
    artifacts: List[Artifact] = field(default_factory=list)

    def key_output(self, n: int = 3) -> str:
        lines = [l for l in self.stdout.splitlines() if l.strip()]
        return " | ".join(lines[-n:])[:400]

    def missing(self) -> List[str]:
        """Evidence three-piece self-check. Empty list == evidence is complete."""
        gaps = []
        if self.exit_code is None:
            gaps.append("no exit code")
        if not self.stdout.strip() and not self.artifacts:
            gaps.append("no output and no artifact")
        if not self.started_at:
            gaps.append("no timestamp")
        for a in self.artifacts:
            if not a.exists:
                gaps.append(f"artifact missing: {a.path}")
        return gaps


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(command: str, cwd: str = ".", timeout: int = 120,
            artifacts: Optional[List[str]] = None) -> Evidence:
    """Run a shell command and record everything needed to re-check it later."""
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(
            ["bash", "-lc", command] if os.name != "nt" else ["cmd", "/c", command],
            cwd=cwd, capture_output=True, timeout=timeout, env=env,
        )
        code, out, err = p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        code, out, err = None, "", f"timeout after {timeout}s"
    except Exception as exc:  # pragma: no cover - environment failure path
        code, out, err = None, "", f"could not run: {exc}"

    arts = []
    for rel in artifacts or []:
        full = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        if os.path.exists(full):
            arts.append(Artifact(rel, True, os.path.getsize(full), _md5(full)))
        else:
            arts.append(Artifact(rel, False))

    return Evidence(command, code, out, err, round(time.time() - t0, 2), started, arts)


def artifacts_in(expect: str) -> List[str]:
    """Pull artifact paths out of an expect string (file:/md5: clauses)."""
    paths = []
    for clause in expect.split(";"):
        clause = clause.strip()
        if clause.startswith("file:"):
            paths.append(clause[5:].strip())
        elif clause.startswith("md5:"):
            paths.append(clause.split("=")[0][4:].strip())
    return paths
