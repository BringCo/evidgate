"""Look at a project and say what is worth checking.

The first minute with a gate tool is the hard part: the config is empty and the
user has no idea whether their project even has anything to check. This module
answers that question from evidence on disk -- directories, file types, a
bibliography -- instead of from a template.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List

FIG_DIRS = ("figures", "figs", "plots", "charts", "images", "imgs", "img", "pictures")
# Vector/authoring sources that real theses actually use, not just SVG.
FIG_SRC_EXTS = (".svg", ".fig", ".dia", ".drawio", ".ipe", ".gp")
FIG_OUT_EXTS = (".png", ".pdf", ".eps", ".jpg", ".jpeg", ".tif", ".tiff")
# A script or Makefile that regenerates the figures is proof of a derivation chain
# even when the produced file is not checked in next to its source.
GEN_HINT = re.compile(r"(mkplot|mkfig|mkimage|makefig|makeplot|plot.*\.sh|fig.*\.sh)", re.I)
OUT_DIRS = ("dist", "build", "output", "out", "release")
DOC_NAMES = ("paper.md", "draft.md", "manuscript.md", "report.md")
# files evidgate itself (or common project furniture) writes; never "documents to audit"
SKIP_DOCS = {"readme.md", "changelog.md", "license.md", "contributing.md",
             "evidgate_ledger.md", "gate_report.md", "gate_report.example.md"}
TEST_HINTS = ("test_", "_test.", "tests", "spec")


@dataclass
class Finding:
    what: str
    packs: List[str] = field(default_factory=list)
    note: str = ""


def _stems(root: str, ext: str) -> set:
    """Basenames (without extension) of files with this extension, anywhere."""
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        out |= {os.path.splitext(f)[0] for f in filenames if f.lower().endswith(ext)}
    return out


def _count(root: str, ext: str) -> int:
    """Count files by extension anywhere under root (skipping .git)."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        total += sum(1 for f in filenames if f.lower().endswith(ext))
    return total


def _has_bibliography(path: str) -> bool:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    if re.search(r"^#{1,3}\s*(参考文献|References|Bibliography)", text, re.M | re.I):
        return True
    return len(re.findall(r"^\s*\[\d+\]\s+\S", text, re.M)) >= 3


def probe(root: str = ".") -> Dict[str, object]:
    """Return findings plus the packs they imply. Read-only."""
    findings: List[Finding] = []
    packs: List[str] = []
    entries = os.listdir(root) if os.path.isdir(root) else []

    # 1. figures: a vector source plus a raster/print derivative somewhere in the tree
    svg, png, pdf = _count(root, ".svg"), _count(root, ".png"), _count(root, ".pdf")
    # Only a shared basename proves a derivative relationship (a.svg -> a.png).
    # A tree with unrelated svgs and pngs has nothing for the figures pack to guard:
    # it would go green on an empty check set, which is worse than saying nothing.
    src_stems = set()
    for ext in FIG_SRC_EXTS:
        src_stems |= _stems(root, ext)
    out_stems = set()
    for ext in FIG_OUT_EXTS:
        out_stems |= _stems(root, ext)
    paired = src_stems & out_stems
    gen_scripts = [f for f in entries if GEN_HINT.search(f)]
    has_makefile = any(f.lower() in ("makefile", "makefile.am") for f in entries)
    # Two independent ways to see a derivation chain:
    #   1. same basename in a source format and an output format (a.svg -> a.png)
    #   2. a figure-generating script or Makefile plus outputs on disk
    chained = bool(paired) or bool(gen_scripts) or (has_makefile and out_stems)
    if (src_stems or gen_scripts) and out_stems and chained:
        where = next((n for n in FIG_DIRS if os.path.isdir(os.path.join(root, n))), ".")
        outs = sum(_count(root, e) for e in FIG_OUT_EXTS)
        proof = (f"{len(paired)} 组同名" if paired
                 else ("生成脚本 " + "、".join(gen_scripts[:2]) if gen_scripts
                       else ("Makefile" if has_makefile else "输出文件")))
        findings.append(Finding(
            what=f"{where} 一带：{outs} 个位图/PDF 输出，派生依据：{proof}",
            packs=["figures"],
            note="有源就有派生链 —— figures 包盯的是「派生是不是跟着源更新」"))
        packs.append("figures")

    # 2. build output directories
    for name in OUT_DIRS:
        d = os.path.join(root, name)
        if os.path.isdir(d):
            n = sum(len(fs) for _r, _ds, fs in os.walk(d))
            if n:
                findings.append(Finding(
                    what=f"{name}/ 里有 {n} 个文件",
                    packs=["build"],
                    note="交付前值得确认：非空、无明文密钥、无临时文件"))
                packs.append("build")
                break

    # 3. documents with a bibliography (README alone is not a document to audit)
    doc_hit = None
    for name in DOC_NAMES:
        p = os.path.join(root, name)
        if os.path.isfile(p) and _has_bibliography(p):
            doc_hit = name
            break
    if doc_hit:
        findings.append(Finding(
            what=f"{doc_hit} 带参考文献表",
            packs=[],
            note="prose 检查可用：evidgate prose-init（列而不引、缺口径、绝对化词）"))
    else:
        docs = [f for f in entries
                if f.lower().endswith(".md") and f.lower() not in SKIP_DOCS]
        if len(docs) >= 2:
            findings.append(Finding(
                what=f"有 {len(docs)} 个 .md（{', '.join(docs[:3])}…），没有识别到参考文献表",
                note="正文要与文献表对得上，得用 [n] 编号制；否则 citation_chain 无法判断"))

    # 4. tests
    has_tests = any(any(h in e.lower() for h in TEST_HINTS) for e in entries)
    if not has_tests:
        has_tests = any(os.path.isdir(os.path.join(root, n)) for n in ("tests", "test", "spec"))
    if has_tests:
        findings.append(Finding(what="有测试文件或 tests/ 目录", packs=["repo"],
                                note="交付前跑一遍单测；没装依赖的话用 optional: true"))
        packs.append("repo")

    # 5. credential risk: a secret-looking file that is not ignored
    risky = [n for n in (".env", "secrets.yml", "credentials.json")
             if os.path.isfile(os.path.join(root, n))]
    if risky:
        findings.append(Finding(
            what="存在 " + "、".join(risky),
            note="确认它被 .gitignore 挡住；build 包的密钥扫描只查交付目录"))

    # de-duplicate, keep order
    seen, ordered = set(), []
    for p in packs:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    return {"findings": findings, "packs": ordered}


def render(result: Dict[str, object]) -> str:
    findings: List[Finding] = result["findings"]          # type: ignore[assignment]
    packs: List[str] = result["packs"]                    # type: ignore[assignment]
    lines: List[str] = []
    if not findings:
        lines.append("这个目录里没扫到图目录、构建产物、文档或测试 —— 不需要 evidgate。")
        return "\n".join(lines)

    lines.append("扫到的东西：")
    for f in findings:
        lines.append(f"  · {f.what}")
        if f.note:
            lines.append(f"      → {f.note}")

    lines.append("")
    if packs:
        spec = ", ".join(packs)
        lines.append(f"建议在 evidgate.yaml 里写一行：")
        lines.append(f"    packs: {spec}")
        lines.append("")
        lines.append(f"生成它：evidgate init --packs {spec.replace(', ', ',')}")
    else:
        lines.append("没有现成的包能覆盖上面这些 —— 需要自己写检查项。")

    return "\n".join(lines)