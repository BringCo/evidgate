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


def _split_argv(command: str) -> List[str]:
    """Split a command into argv without a shell (the default path)."""
    import shlex
    try:
        return shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError(
            f"命令无法拆成参数（{exc}）。如果用了管道 | 重定向 > $() 或 &&，"
            f"请在检查项上显式写 shell: bash"
        )


def find_posix_shell() -> str:
    """Locate a real POSIX shell; on Windows this must be Git Bash.

    Deliberately does NOT consult PATH on Windows: `where bash` resolves to
    C:\\Windows\\System32\\bash.exe, which is the WSL entry point and uses an
    entirely different path scheme (/mnt/e/... vs /e/...).
    """
    import shutil
    if os.name != "nt":
        for name in ("bash", "sh"):
            path = shutil.which(name)
            if path:
                return path
        return ""
    candidates = [
        r"C:\\Program Files\\Git\\bin\\bash.exe",
        r"C:\\Program Files (x86)\\Git\\bin\\bash.exe",
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs",
                     "Git", "bin", "bash.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


def _build_argv(command: str, shell: str):
    """-> (argv, error). An error means the check could not be run at all."""
    import shutil
    shell = (shell or "").strip().lower()
    if not shell:
        try:
            return _split_argv(command), ""
        except ValueError as exc:
            return [], str(exc)
    if shell in ("bash", "sh"):
        found = find_posix_shell()
        if not found:
            return [], (f"检查项声明 shell: {shell}，但本机没找到可用的 POSIX shell"
                        f"（Windows 请安装 Git Bash，或改用 builtin: 检查项）")
        return [found, "-lc", command], ""
    if shell == "cmd":
        if os.name != "nt":
            return [], "shell: cmd 只能在 Windows 上使用"
        return ["cmd", "/c", command], ""
    if shell in ("powershell", "pwsh"):
        exe = shutil.which(shell)
        if not exe:
            return [], f"检查项声明 shell: {shell}，但没找到该可执行文件"
        return [exe, "-Command", command], ""
    return [], f"未知 shell {shell!r}"


def collect(command: str, cwd: str = ".", timeout: int = 120,
            artifacts: Optional[List[str]] = None, shell: str = "") -> Evidence:
    """Run a shell command and record everything needed to re-check it later."""
    from . import builtin
    if builtin.is_builtin(command):
        return builtin.dispatch(command, cwd=cwd)

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    argv, build_error = _build_argv(command, shell)
    missing_tool = False
    if build_error:
        return Evidence(command, None, "", build_error, 0.0, started, [],
                        True, build_error)
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True,
                           timeout=timeout, env=env)
        code = p.returncode
        out, err = _decode(p.stdout), _decode(p.stderr)
    except FileNotFoundError:
        code, out = 127, ""
        err = (f"命令未找到：{argv[0] if argv else command}（默认不经 shell 直接执行；"
               f"若命令里有 | > $() && 等语法，请在该检查项上写 shell: bash）")
        missing_tool = True
    except subprocess.TimeoutExpired:
        code, out, err = None, "", f"timeout after {timeout}s"
    except Exception as exc:  # pragma: no cover - environment failure path
        code, out, err = None, "", f"could not run: {exc}"

    missing_tool = missing_tool or _missing_tool(code, err, out)
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
