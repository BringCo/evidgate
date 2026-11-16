"""Evidence: fresh, verifiable, traceable.

A check that cannot show *what was run*, *what came back*, and *when* did not run.
"""
from __future__ import annotations

import hashlib
import os
import re
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
    command_not_found: bool = False   # the command itself never ran
    not_found_hint: str = ""

    def key_output(self, n: int = 3) -> str:
        lines = [l for l in self.stdout.splitlines() if l.strip()]
        return redact(" | ".join(lines[-n:]))[:400]

    def missing(self, needs_stdout: bool = False) -> List[str]:
        """Evidence three-piece self-check. Empty list == evidence is complete.

        An exit-code-only assertion is fully evidenced by the exit code; demanding
        stdout there would flag every quiet-but-correct check as incomplete.
        """
        gaps = []
        if self.exit_code is None:
            gaps.append("no exit code")
        if needs_stdout and not self.stdout.strip():
            gaps.append("assertion needs stdout but the command printed nothing")
        if not self.started_at:
            gaps.append("no timestamp")
        for a in self.artifacts:
            if not a.exists:
                gaps.append(f"artifact missing: {a.path}")
        return gaps


_SECRET = re.compile(
    r"(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


_NOT_FOUND = re.compile(
    r"command not found"                      # bash/dash
    r"|: not found"                           # sh
    r"|is not recognized as an internal or external command"   # cmd (en)
    r"|不是内部或外部命令"                                        # cmd (zh, GBK)
    r"|не является внутренней",                # cmd (ru) -- harmless extra
)


def _missing_tool(code, stderr: str, stdout: str = "") -> bool:
    """Did the shell fail to find the command, rather than the command failing?

    Exit codes alone are not usable here: measured on Windows, the same missing
    command yields 1, 9009 and even 0 depending on the shell wrapper. The text is
    the reliable signal; the codes only corroborate it.
    """
    if code == 9009:            # cmd's dedicated "command not found"
        return True
    blob = (stderr or "") + "\n" + (stdout or "")
    if _NOT_FOUND.search(blob):
        return True
    return code == 127 and not blob.strip().startswith("usage")


def _decode(raw: bytes) -> str:
    """Decode a child process's output on any platform.

    A Chinese Windows console writes GBK; decoding that as utf-8 with 'replace'
    turns "不是内部或外部命令" into mojibake, which silently defeats the
    "command not found" detection below.
    """
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def redact(text: str) -> str:
    """Never let a credential reach the ledger.

    A check like `grep -n AKIA .env` is exactly the check you want, and its stdout
    is exactly what must not land in a file you then commit. Detection uses the raw
    text; only display is redacted.
    """
    return _SECRET.sub("***REDACTED***", text)


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(command: str, cwd: str = ".", timeout: int = 120,
            artifacts: Optional[List[str]] = None) -> Evidence:
    """Run a shell command and record everything needed to re-check it later."""
    from . import builtin
    if builtin.is_builtin(command):
        return builtin.dispatch(command, cwd=cwd)

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(
            ["bash", "-lc", command] if os.name != "nt" else ["cmd", "/c", command],
            cwd=cwd, capture_output=True, timeout=timeout, env=env,
        )
        code = p.returncode
        out, err = _decode(p.stdout), _decode(p.stderr)
    except subprocess.TimeoutExpired:
        code, out, err = None, "", f"timeout after {timeout}s"
    except Exception as exc:  # pragma: no cover - environment failure path
        code, out, err = None, "", f"could not run: {exc}"

    missing_tool = _missing_tool(code, err, out)
    arts = []
    for rel in artifacts or []:
        full = rel if os.path.isabs(rel) else os.path.join(cwd, rel)
        if os.path.exists(full):
            arts.append(Artifact(rel, True, os.path.getsize(full), _md5(full)))
        else:
            arts.append(Artifact(rel, False))

    hint = ""
    if missing_tool:
        hint = (err.strip().splitlines() or [""])[0][:120]
    return Evidence(command, code, out, err, round(time.time() - t0, 2), started, arts,
                    missing_tool, hint)


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
