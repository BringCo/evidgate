---
name: evidgate
description: Use when a document or deliverable needs a release gate — turn claims into checks with commands, evidence and a ledger.
---

# evidgate (agent adapter)

Install: `pip install evidgate`, or copy this folder to your agent's skills dir
and keep the repo on PATH.

Use it when the user asks "能不能交付 / 每句话有依据吗 / 帮我过一遍再发".

1. `evidgate init --dir <project>` — writes `evidgate.yaml` (one check = command + assertion + counter-test).
2. `evidgate prose-init --dir <project> --file <draft.md>` — appends the Chinese prose checks.
3. `evidgate run --dir <project>` — exit 1 means blocked; never report success from a non-zero run.
4. `evidgate resume --dir <project>` — rerun only unresolved checks.
5. `evidgate mutate --baseline <good> --mutant <planted-bug>` — prove a check can go red.

Rules: do not edit verdicts by hand; a green check without evidence is not green;
yellow items go to a confirmation list, never into "done".
