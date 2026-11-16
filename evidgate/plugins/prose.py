"""prose plugin: checks for Chinese technical writing.

Each rule is a command with its own exit code, so the gate only has to read
`exit:0`. That keeps the engine domain-free and lets anyone add a rule without
touching core.

Exit codes: 0 = clean, 2 = blocking finding (red), 3 = advisory finding (yellow).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import List, Tuple

SKIP_PREFIX = ("#", ">", "|", "-", "!", "```", "$$", "$", "注：", "图注", "虚线", "实线", "点线")
SENT_SPLIT = re.compile(r"(?<=[。；！？])")

CITE = re.compile(r"\[\d+\]|（[^）]*\d{4}[^）]*）")
CHART = re.compile(r"§\s*\d|第\s*\d+\s*节|图\s*\d|表\s*\d|公式|表\s*注")
STAT = re.compile(r"p\s*[=<>≈]|p\([A-Za-z]+\)\s*[=<>≈]|\b\d+\s*/\s*\d+\b|n\s*=|±|"
                   r"\bHolm\b|\bBH\b|\bpp\b|seed|划分|基线|对照组|"
                   r"\bS\d+[a-z]?\b|split\s*\d|\d[\d,]*\s*(窗|块|个|条|张|组)")
SCOPE_WORD = re.compile(r"实测|复算|协议|消融|逐\s*(组|单元|cell)|全池|均值|中位|批次|脚本|路径|本文|我们|口径|汇报|惯例|定义|设定|划分|seed|基线")
CLAIM = re.compile(r"(表明|说明|证明|意味着|取决于)")
# "本文/我们 ... 首次/首创" or "首次/首创 + 首创类动词" -- descriptive uses of 首次/唯一
# (first drop below 0.8, the only negative gap) are not priority claims and must not fire.
ABS_SELF = re.compile(r"(本文|我们|本工作|本研究|本方法)\s*[^，。；]{0,10}(首次|首创|最先|率先|前所未有)")
ABS_VERB = re.compile(r"(首次|首创|最先|率先|前所未有)\s*(提出|实现|证明|报道|引入|建立|完成|构建|给出)")
ABS_SCOPE = re.compile(r"(检索日期|query|本协议|范围内|据我们|目前可检索|就本文所见)")
NUMSTAT = re.compile(r"(ρ|r\s*=|R²|相关系数|\d+\.?\d*\s*%)|"
                     r"((提升|降低|下降|增加|减少|高出|低于|降幅|增益|误差)\s*[约]?\s*[+\-−]?\d)")


def _extra() -> "re.Pattern | None":
    """Domain evidence markers the user adds: EVIDGATE_EVIDENCE='pat1|pat2'."""
    raw = os.environ.get("EVIDGATE_EVIDENCE", "").strip()
    if not raw:
        return None
    try:
        return re.compile(raw)
    except re.error:
        return None


def _has(pats, s: str) -> bool:
    return any(p.search(s) for p in pats if p is not None)


def evidence_any(sentence: str) -> bool:
    """Does this sentence show any trace of evidence at all (citation, chart, stat, %)."""
    pats = [CITE, CHART, STAT, SCOPE_WORD, _extra(), re.compile(r"%")]
    return _has(pats, sentence)


def evidence_for_numbers(sentence: str) -> bool:
    """Same, but a bare % does not count -- otherwise numeral_scope can never fire."""
    return _has([CITE, CHART, STAT, SCOPE_WORD, _extra()], sentence)


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
        m = ABS_SELF.search(s) or ABS_VERB.search(s)
        if m and not ABS_SCOPE.search(s):
            hits.append(f"L{ln} [{m.group(0)[:12]}] {s[:70]}")
    return hits


def rule_uncited(lines: List[Tuple[int, str]]) -> List[str]:
    hits = []
    for ln, s in lines:
        if CLAIM.search(s) and not evidence_any(s):
            hits.append(f"L{ln} {s[:70]}")
    return hits


def rule_numeral_scope(lines: List[Tuple[int, str]]) -> List[str]:
    hits = []
    for ln, s in lines:
        # no length threshold: a short sentence carrying a bare percentage is exactly
        # the case that slips through when the rule "looks" like it is working.
        if NUMSTAT.search(s) and not evidence_for_numbers(s):
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
    if cited and not listed:
        # the bibliography uses another scheme (author-year, "1." numbering, EndNote
        # paste). Saying 38 times "reference missing" would be a false alarm barrage;
        # say once that the scheme was not recognised.
        return [f"文献表制式未被识别：正文有 {len(cited)} 处 [n] 编号，但文献表里没有 [n]。"
                f"本规则只支持编号制；该文献表可能是作者-年份制或其他格式。"]
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
