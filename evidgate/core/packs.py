"""Reusable check bundles.

`packs: figures, build:outdir=dist` in evidgate.yaml pulls in ready-made checks.
A pack is nothing but checks with placeholders -- it obeys the same rule as a
hand-written check: no counter-test, no load.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from .check import Check, _mini_yaml

PACK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "packs"
)

# Defaults so `packs: figures` works with no arguments. Override with
# `packs: figures manifest=my.json,outdir=figs`.
DEFAULTS: Dict[str, Dict[str, str]] = {
    "figures": {"manifest": "artifacts.json", "outdir": "png"},
    "build": {
        "outdir": "dist",
        "secret": "AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}"
                  "|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    },
    "repo": {"test_cmd": "python3 -m pytest -q", "pattern": "TODO|FIXME|breakpoint\\(\\)"},
}

_PH = re.compile(r"\{(\w+)\}")


def available() -> List[str]:
    if not os.path.isdir(PACK_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(PACK_DIR) if f.endswith(".yaml"))


def _split(entry) -> Tuple[str, Dict[str, str]]:
    """'figures:manifest=a.json,outdir=figs' -> ('figures', {...})"""
    if not isinstance(entry, str):
        return str(entry.get("name", "")), dict(entry.get("options") or {})
    head, _, tail = entry.partition(":")
    opts: Dict[str, str] = {}
    for pair in tail.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            opts[k.strip()] = v.strip().strip("\"'")
    return head.strip(), opts


def _sub(text: str, params: Dict[str, str], pack: str) -> str:
    def rep(m):
        key = m.group(1)
        if key not in params:
            raise SystemExit(
                f"pack {pack}: 没有 {key} 的值。写法：packs: {pack}:{key}=..."
            )
        return params[key]

    return _PH.sub(rep, text)


def load_packs(entries) -> List[Check]:
    out: List[Check] = []
    for entry in entries:
        name, opts = _split(entry)
        if not name:
            continue
        path = os.path.join(PACK_DIR, name + ".yaml")
        if not os.path.exists(path):
            raise SystemExit(
                f"unknown pack {name!r}; 可用：{', '.join(available()) or '(none)'}"
            )
        with open(path, encoding="utf-8") as fh:
            cfg = _mini_yaml(fh.read())
        params = dict(DEFAULTS.get(name) or {})
        params.update(opts)
        for item in cfg.get("checks") or []:
            item = dict(item)
            for key in ("name", "method", "expect", "counter", "note"):
                if isinstance(item.get(key), str):
                    item[key] = _sub(item[key], params, name)
            item.setdefault("severity", "red")
            check = Check(**{k: v for k, v in item.items() if k in Check.__annotations__})
            check.validate()
            check.note = (check.note + f" [pack:{name}]").strip()
            out.append(check)
    return out
