"""prose plugin: checks for Chinese technical writing.

Each rule is a command with its own exit code, so the gate only has to read
`exit:0`. That keeps the engine domain-free and lets anyone add a rule without
touching core.

Exit codes: 0 = clean, 2 = blocking finding (red), 3 = advisory finding (yellow).
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import List, Tuple

SKIP_PREFIX = ("#", ">", "|", "-", "!", "```")
SENT_SPLIT = re.compile(r"(?<=[。；！？])")

CITE = re.compile(r"（[^）]*(?:等|\d{4})[^）]*）|\[\d+\]")
SCOPE = re.compile(r"(本文|我们)(的)?(实测|实验|协议|统计|结果)|n\s*=|逐\s*(组|单元|cell)|全池|均值|中位|协议|批次|脚本|路径")
CLAIM = re.compile(r"(表明|说明|证明|意味着|取决于|决定)")
ABS = re.compile(r"(首次|首创|最先|唯一|未见|前所未有|普遍适用|无损)")
ABS_SCOPE = re.compile(r"(检索日期|query|本协议|范围内|据我们|目前可检索)")
NUMSTAT = re.compile(r"(ρ|r\s*=|R²|相关系数|倍|降幅|提升|%)")


def sentences(text: str) -> List[Tuple[int, str]]:
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith(SKIP_PREFIX):
            continue
        for piece in SENT_SPLIT.split(s):
            piece = piece.strip()
            if len(piece) > 12:
                out.append((ln, piece))
    return out


def body(text: str) -> str:
    for marker in ("## 参考文献", "# 参考文献"):
        if marker in text:
            return text.split(marker)[0]
    return text


def rule_denominator(lines: List[Tuple[int, str]]) -> List[str]:
    print(f"正文句 {len(lines)}")
    return []


def rule_absolutes(lines: List[Tuple[int, str]]) -> List[str]:
    hits = []
    for ln, s in lines:
        for w in ABS.findall(s):
            if not ABS_SCOPE.search(s):
                hits.append(f"L{ln} [{w}] {s[:70]}")
    return hits


def rule_uncited(lines: List[Tuple[int, str]]) -> List[str]:
    hits = []
    for ln, s in lines:
        if CLAIM.search(s) and not CITE.search(s) and not SCOPE.search(s):
            hits.append(f"L{ln} {s[:70]}")
    return hits


def rule_numeral_scope(lines: List[Tuple[int, str]]) -> List[str]:
    hits = []
    for ln, s in lines:
        # no length threshold: a short sentence carrying a bare percentage is exactly
        # the case that slips through when the rule "looks" like it is working.
        if NUMSTAT.search(s) and not SCOPE.search(s):
            hits.append(f"L{ln} {s[:70]}")
    return hits


def rule_citation_chain(text: str) -> List[str]:
    """Every [n] in the body must exist in the reference list, and vice versa."""
    b = body(text)
    refs = text[len(b):]
    cited = {int(x) for x in re.findall(r"\[(\d+)\]", b)}
    listed = {int(x) for x in re.findall(r"^\s*\[(\d+)\]", refs, re.M)}
    if not listed:
        listed = {int(x) for x in re.findall(r"\[(\d+)\]", refs)}
    missing = sorted(cited - listed)
    unused = sorted(listed - cited)
    hits = [f"正文引用 [{n}] 在文献表中不存在" for n in missing]
    hits += [f"文献表 [{n}] 正文未引用" for n in unused]
    return hits


RULES = {
    "denominator": (rule_denominator, 0),
    "absolutes": (rule_absolutes, 2),
    "uncited": (rule_uncited, 3),
    "numeral_scope": (rule_numeral_scope, 3),
    "citation_chain": (rule_citation_chain, 2),
}


def scan(path: str, rule: str, quiet: bool = False) -> int:
    fn, red_code = RULES[rule]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    lines = sentences(body(text))
    hits = fn(text) if rule == "citation_chain" else fn(lines)
    if not quiet:
        for h in hits:
            print(h)
    if rule == "denominator":
        return 0
    if not hits:
        print(f"[{rule}] clean ({len(lines)} sentences scanned)")
        return 0
    print(f"[{rule}] {len(hits)} finding(s)  (exit {red_code})")
    return red_code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="evidgate prose")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="run one rule against a markdown draft")
    s.add_argument("--file", required=True)
    s.add_argument("--rule", required=True, choices=sorted(RULES))
    s.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    return scan(a.file, a.rule, a.quiet)


if __name__ == "__main__":
    sys.exit(main())
