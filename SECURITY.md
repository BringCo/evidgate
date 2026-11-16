# Security policy

## What this tool does that a linter does not

evidgate **executes the commands written in `evidgate.yaml`**. That is the whole design:
a check is a command plus an assertion, and the exit code is the evidence. Two
consequences follow, and neither is a vulnerability in itself:

- Running an `evidgate.yaml` you did not write is equivalent to running someone else's
  shell commands. Review the `method:` lines first, especially any with `shell: bash`.
- `evidgate` does not sandbox, chroot or restrict what a check may do. It is a gate, not
  a jail.

Reports that amount to "it ran the command I asked it to run" will be closed as by
design. The sections below are about what is *not* intended.

## Reporting a vulnerability

Use GitHub's private reporting: **Security → Advisories → Report a vulnerability** on
`BringCo/evidgate`. Please do not open a public issue for anything that could be
exploited before it is fixed.

Include: the version (`evidgate --version`), the platform, the smallest `evidgate.yaml`
that reproduces it, and what you expected instead.

## In scope

- Command injection or argument mangling that makes a check run something other than
  what its `method:` says.
- A check that reports `PASS` when the command did not run, did not exit with the
  declared code, or produced no evidence. False green is the failure mode this project
  exists to prevent, so it is always treated as a security issue, not a cosmetic one.
- Credentials or secrets written into `evidgate_ledger.md` or `gate_report.md`. The
  writer is supposed to redact before recording; a leak is a bug.
- Anything that lets a repo being *read* influence the machine running evidgate beyond
  the declared checks.

## Out of scope

- The tool executing a `method:` that you (or a file you chose to run) declared.
- Denial of service by writing a check that runs forever; `timeout:` exists for this,
  and defaults to 120s.
- Findings in third-party tools that evidgate shells out to.

## Supported versions

The latest release only. Fixes land on `master` and are released as a patch version;
older versions do not receive backports.