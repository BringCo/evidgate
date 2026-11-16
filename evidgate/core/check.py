"""Check registry.

A check is only a check if it has a counter-test: the thing you would break to make
it go red. A check without a counter-test is a wish, not a gate -- load_checks()
refuses it.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import List

SEVERITIES = ("red", "yellow")
SHELLS = ("", "sh", "bash", "cmd", "powershell", "pwsh")


@dataclass
class Check:
    cid: str                 # C1
    name: str                # what is being checked
    method: str              # shell command that produces evidence
    expect: str              # assertion, e.g. "exit:0; contains:OK" or "manual"
    counter: str = ""        # counter-test; empty is refused by validate()
    severity: str = "red"    # red -> blocking, yellow -> non-blocking (DIFF)
    optional: bool = False   # true -> a failing command becomes SKIP (not applicable), not red
    timeout: int = 120
    note: str = ""
    shell: str = ""          # "" = exec the command directly (no shell);
                             # "bash" / "sh" / "cmd" / "powershell" / "pwsh"
                             # = run it through that shell explicitly

    def validate(self) -> None:
        if not self.cid:
            raise ValueError("check without id")
        if not self.name:
            raise ValueError(f"{self.cid}: check without name")
        if not self.counter.strip():
            raise ValueError(
                f"{self.cid} ({self.name}): no counter-test. "
                "Declare how this check goes red, or drop it -- "
                "a gate that cannot fail is not a gate."
            )
        if self.shell not in SHELLS:
            raise ValueError(
                f"{self.cid}: shell must be one of {SHELLS} (or empty for no shell)"
            )
        if self.severity not in SEVERITIES:
            raise ValueError(f"{self.cid}: severity must be one of {SEVERITIES}")
        if "not_contains" in self.expect and "exit:" not in self.expect:
            raise ValueError(
                f"{self.cid} ({self.name}): 'not_contains' without an 'exit:' clause. "
                "If the command fails and prints nothing, not_contains passes on empty "
                "output -- a tautology that reports green when the file is gone. "
                "Pair it with exit:0."
            )


_HEAD = re.compile(r"^\s*-\s*(\w+)\s*:\s*(.*)$")
_KV = re.compile(r"^\s+(\w+)\s*:\s*(.*)$")


def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _mini_yaml(text: str) -> dict:
    """Tiny YAML subset: top-level keys, and lists of flat key/value maps.

    Keeps evidgate dependency-free; a real YAML parser is used when available.
    """
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        pass

    out, cur, cur_list = {}, None, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _HEAD.match(raw)
        if m:  # "- key: value" starts a new list item
            if cur_list is None:
                cur_list = []
            cur = {}
            if out.get("_pending_list"):
                out[out.pop("_pending_list")] = cur_list
            cur_list.append(cur)
            cur[m.group(1)] = _scalar(m.group(2))
            continue
        m = _KV.match(raw)
        if m:
            if cur is not None:
                cur[m.group(1)] = _scalar(m.group(2))
            else:
                out[m.group(1)] = _scalar(m.group(2))
            continue
        m = re.match(r"^\s*(\w+)\s*:\s*$", raw)
        if m:
            out[m.group(1)] = []
            cur_list = out[m.group(1)]
            cur = None
    if cur_list is not None:
        for k, v in out.items():
            if v is cur_list:
                break
            out.setdefault(k, v)
    return out


def load_checks(path: str, allow_empty: bool = False) -> List[Check]:
    """Load and validate checks from a .yaml / .json file.

    allow_empty: a project that declares `packs:` may legitimately write no checks
    of its own; the packs supply them.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if path.endswith(".json"):
        data = json.loads(text)
    else:
        data = _mini_yaml(text)
    raw = data.get("checks") or []
    checks = []
    for i, item in enumerate(raw, 1):
        item = dict(item)
        item.setdefault("cid", f"C{i}")
        item.setdefault("severity", "red")
        item.setdefault("expect", "exit:0")
        checks.append(Check(**{k: v for k, v in item.items() if k in Check.__annotations__}))
    for c in checks:
        c.validate()
    if not checks and not allow_empty:
        raise ValueError(f"{path}: 没有任何启用的检查项（注释模板不算）；打开它，去掉 # 写下第一条")
    ids = [c.cid for c in checks]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        raise ValueError(f"duplicate check ids: {sorted(dup)}")
    return checks
