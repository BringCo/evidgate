"""Clause coverage between a source document and the document derived from it.

`method: builtin:coverage:clauses --src spec.pdf --doc plan.md`

The failure this catches, measured on a real case: a one-page plan restated five of
six requirements from an official notice and silently dropped the sixth --
"对照评分表打分项顺序进行 PPT 汇报，也可自行安排汇报内容顺序". That clause carried no
obligation word (必须/不得/应当), so any keyword filter misses it; and the plan did
cite the notice as its source, so a source-existence check passed.

What the measurement showed, on that notice (13 clauses, 5 restated, 1 dropped):

  * split by clause number, NOT line by line and NOT by obligation keyword.
    Line-splitting put the dropped clause outside the sample entirely.
  * n=4. At n=8 a rewritten-but-present clause fell to 0.03 and became
    indistinguishable from an absent one; at n=6 already 0.16.
  * the dropped clause scored 0.00, the five present ones 0.38-0.83. Gap 0.38.

What it does NOT do: local edits. Deleting one sentence moves a score by ~0.02
(measured 0.58 -> 0.56); only removing the whole restatement takes it to 0.00.
This finds missing clauses, not wrong ones -- a stable 0.58 must not be read as
"this clause is faithfully restated".

It stays yellow on purpose. A low score means "shares no wording", which is either
a dropped clause or a clause this document did not need to restate. Only a human
can tell those apart, so the finding goes to the confirmation list, never to red.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from typing import List, NamedTuple

RULES = ("clauses",)

CLAUSE_HEAD = re.compile(r"^\s*(?:附件\s*)?(\d+[.、]|[一二三四五六七八九十]+、)")
PUNCT = re.compile(r"[\s\u3000，。；：、（）()「」『』“”\"'‘’,.;:%％—\-–…·]")
DEFAULT_N = 4
DEFAULT_THRESH = 0.05
DEFAULT_LIMIT = 20


class Clause(NamedTuple):
    cid: str
    text: str


def split_clauses(text: str) -> List[Clause]:
    """Split on clause numbers (1. / 二、 / 附件), keeping following lines attached.

    Newlines are kept inside a clause: pdftotext breaks mid-sentence, and the
    dropped clause in the measured case straddled such a break
    ("对照评分表打\\n分项顺序"). Normalisation removes them before matching.
    """
    blocks: List[Clause] = []
    cid, cur = "", []
    for line in text.splitlines():
        if not line.strip():
            continue
        m = CLAUSE_HEAD.match(line)
        if m:
            if cur:
                blocks.append(Clause(cid or "#1", "\n".join(cur)))
            cid, cur = m.group(1), [line]
        else:
            cur.append(line)
    if cur:
        blocks.append(Clause(cid or f"#{len(blocks) + 1}", "\n".join(cur)))
    return blocks


def _norm(text: str) -> str:
    return PUNCT.sub("", text)


def coverage(clause: str, doc_norm: str, n: int = DEFAULT_N) -> float:
    """Share of the clause's n-grams that also occur in the derived document."""
    cn = _norm(clause)
    if not cn:
        return 1.0
    if len(cn) <= n:
        return 1.0 if cn in doc_norm else 0.0
    grams = [cn[i:i + n] for i in range(len(cn) - n + 1)]
    return sum(1 for g in grams if g in doc_norm) / len(grams)


_PAGE_MARK = re.compile(r"[ \t]*[—–-][ \t]*\d{1,3}[ \t]*[—–-][ \t]*")


def _strip_page_numbers(text: str) -> str:
    """Drop pdftotext page markers ("— 5 —"), which land mid-sentence.

    Measured: "…仅可添加字幕。一— 5 —经发现，视为无效作品" -- the marker splits
    "一经发现" and the leftover digits eat n-grams, understating coverage on a
    clause the derived document restates in full (0.38 measured, deserved higher).

    Only horizontal whitespace may be eaten. With ``\\s*`` the marker also ate the
    newlines around it, so a marker standing on its own line glued the next line
    onto the previous one; a clause number that used to start a line
    ("2. 评审时间…") no longer started one and the whole clause merged into the
    clause before it. Measured on the 86号 notice: 30 blocks / 26 clauses with
    ``\\s*``, 31 blocks / 27 clauses with the horizontal-only pattern.
    """
    return _PAGE_MARK.sub("", text)


def _read(path: str) -> str:
    if not path.lower().endswith(".pdf"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    exe = shutil.which("pdftotext")
    if not exe:
        raise SystemExit(
            f"{path}: PDF 需要 pdftotext 才能读文本层。二选一：\n"
            f"    pdftotext -layout {path} spec.txt   然后 --src spec.txt\n"
            "  或先由人把条款抄进一个 .txt —— 扫描版 PDF 本来就没有文本层"
        )
    proc = subprocess.run([exe, "-layout", path, "-"],
                          capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise SystemExit(f"{path}: pdftotext 失败：{(proc.stderr or '').strip()[:200]}")
    return proc.stdout


def _is_heading(clause: Clause) -> bool:
    """A section title ("三、总决赛安排") is structure, not a clause to restate.

    Measured on the notice: 3 of 31 blocks were bare headings, and every one of
    them read as 0.00 coverage -- pure noise in the confirmation list.
    """
    text = re.sub(r"\s+", "", clause.text)
    if text.startswith(clause.cid):
        text = text[len(clause.cid):]
    return len(text) < 12 and not re.search(r"[，。；：,.;:]", text)


def _preview(clause: Clause) -> str:
    text = re.sub(r"\s+", "", clause.text)
    if text.startswith(clause.cid):
        text = text[len(clause.cid):]
    return text[:46]


def run(rule: str, argv: List[str]) -> int:
    if rule != "clauses":
        raise SystemExit(f"unknown coverage rule {rule!r}; have: {', '.join(RULES)}")
    ap = argparse.ArgumentParser(prog="evidgate coverage")
    ap.add_argument("--src", required=True, help="一手源：规范/通知原文（.txt/.md/.pdf）")
    ap.add_argument("--doc", required=True, help="由它写成的本件（交付稿/执行清单）")
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--thresh", type=float, default=DEFAULT_THRESH)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = ap.parse_args(argv)

    raw = split_clauses(_strip_page_numbers(_read(args.src)))
    if not any(not c.cid.startswith("#") for c in raw):
        print(f"[coverage] {args.src} 里找不到任何编号条款（1./2./一、二、）—— 不判定，不是通过")
        return 2
    clauses = [c for c in raw if not _is_heading(c)]
    if not clauses:
        print(f"[coverage] {args.src} 切出的全是章节标题，没有可核条款 —— 不判定，不是通过")
        return 2
    skipped = len(raw) - len(clauses)
    if os.path.realpath(args.src) == os.path.realpath(args.doc):
        print("[coverage] --src 与 --doc 是同一个文件，自己比自己恒为满分 —— 不判定，不是通过")
        return 2
    doc_norm = _norm(_strip_page_numbers(_read(args.doc)))

    scored = [(c, coverage(c.text, doc_norm, args.n)) for c in clauses]
    low = sorted((x for x in scored if x[1] < args.thresh), key=lambda x: x[1])

    if not low:
        print(f"[coverage] clean —— {len(clauses)} 条条款（n={args.n}）在本件中都能找到对应内容")
        return 0

    print(f"[coverage] {len(low)}/{len(clauses)} 条条款在本件中找不到对应内容"
          f"（n={args.n}，阈值 {args.thresh}）：")
    for clause, score in low[:args.limit]:
        print(f"  · {clause.cid}  {_preview(clause)}")
        print(f"      → 覆盖率 {score:.2f}：可能漏抄，也可能本件不需要重述这一条 —— 请人确认")
    if len(low) > args.limit:
        print(f"  …另有 {len(low) - args.limit} 条，见 --limit")
    if skipped:
        print(f"[coverage] 另有 {skipped} 条按章节标题跳过"
              "（不足 12 字且无标点）；若其中有真条款，需人工确认")
    print(f"[coverage] {len(low)} finding(s)  (exit 1)")
    return 1


def main(argv: List[str] | None = None) -> int:
    return run("clauses", list(argv) if argv is not None else [])
