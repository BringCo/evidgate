[← back to README](../README.md)

# Shell handling and Windows

A check runs **without a shell** unless you declare one. That is deliberate: it is the
only way the same check means the same thing on every platform.

```yaml
- cid: C3
  method: grep -rn TODO src/       # split into argv, executed directly
  expect: exit:1
```

If the command needs pipes, redirection, `$()` or `&&`, say so:

```yaml
- cid: A1
  shell: bash                      # bash | sh | cmd | powershell | pwsh
  method: test -s build/out.txt && wc -c < build/out.txt
```

## Boundaries, stated plainly

- Without `shell:`, a command that needs shell syntax fails with a message telling you to
  add `shell: bash` — it does not silently pick a shell for you. `doctor` reports the
  omission as `BAD` before you run anything.
- `shell: bash` on Windows looks for **Git Bash** in its standard install locations. It
  deliberately does **not** use `bash` from `PATH`, because there that name resolves to
  `C:\Windows\System32\bash.exe` — the WSL entry point, which uses `/mnt/e/...` instead
  of `/e/...` and would look in the wrong place.
- No Git Bash, no `shell: bash` checks. They report "命令未找到" and block the release.
  `builtin:` checks need nothing and work everywhere.

## Windows

Everything that ships as `builtin:` (all of `packs/figures`) works on both platforms.
Anything written as a shell command (`grep`, `test -d`, `$(...)`) needs a POSIX shell.

If a command is not found at all, evidgate says so and fails the check rather than
accepting the exit code — because on Windows a missing `grep` exits `1`, which is exactly
what `expect: exit:1` ("grep found nothing") looks for. That was a real silent false
green.

On Windows, prefer `builtin:` checks, or run under Git Bash / WSL.
