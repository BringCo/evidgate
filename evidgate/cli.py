"""evidgate CLI: init / run / resume / report / mutate / prose."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from typing import Dict, List

from . import __version__
from .core import builtin
from .core.check import load_checks
from .core.gate import FAIL, LABEL, PENDING, PASS, SKIP, summarize, release_allowed, run_check
from .core.gate import Verdict
from .ledger import build, load_rows, resume_cids
from .plugins import prose

CONFIG = "evidgate.yaml"

TPL_ACTIVE = """# evidgate config. One check = one command + one assertion + one counter-test.
project: {project}
ledger: evidgate_ledger.md

checks:
  - cid: C1
    name: 交付文件存在且非空
    method: test -s {target} && wc -c < {target}
    expect: exit:0; regex:\\d
    counter: 删掉 {target} 或清空它，本项必须变红
    severity: red
"""

TPL_EMPTY = """# evidgate config. 这个目录里没找到可交付文件，所以下面是注释模板。
# 写第一条检查: method 是一条会给出确定退出码的命令, counter 是「怎么让它变红」。
project: {project}
ledger: evidgate_ledger.md

checks:
  # 复制下面三行, 去掉 #, 改成你自己的
  # - cid: C1
  #   name: 交付文件存在且非空
  #   method: test -s your_output.md && wc -c < your_output.md
  #   expect: exit:0; regex:\\d
  #   counter: 删掉 your_output.md 或清空它, 本项必须变红
  #   severity: red
"""

NOTE = "note: PASS 表示「证据存在且可复现」，不表示数值本身正确。"
CANDIDATES = ("report.md", "draft.md", "paper.md", "README.md", "main.py", "src")

PROSE_TEMPLATE = """
  - cid: {cid}
    name: {name}
    method: builtin:prose:{rule} {paper}
    expect: exit:0
    counter: {counter}
    severity: {sev}
"""

PROSE_CHECKS = [
    ("P1", "正文可分词（分母可算）", "denominator", "yellow",
     "给一个空文件或纯表格文件，本项应报错而不是静默 0 句"),
    ("P2", "绝对化词带范围或检索日期", "absolutes", "red",
     "写一句「本文首次实现 X」且不给检索日期，本项必须变红"),
    ("P3", "结论句带引用或实测标记", "uncited", "yellow",
     "写一句「结果说明 A 优于 B」不给引用，本项应变黄"),
    ("P4", "统计数字带口径", "numeral_scope", "yellow",
     "写「降幅 21.2%」不写 n 与协议，本项应变黄"),
    ("P5", "正文引用与文献表双向对上", "citation_chain", "red",
     "正文写 [9] 而文献表只到 [8]，本项必须变红"),
]


def _load(dir_: str):
    cfg_path = os.path.join(dir_, CONFIG)
    if not os.path.exists(cfg_path):
        sys.exit(f"no {CONFIG} in {dir_}. run: evidgate init --dir {dir_}")
    from .core.check import _mini_yaml
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = _mini_yaml(fh.read())
    packs = cfg.get("packs") or []
    if isinstance(packs, str):
        packs = [x.strip() for x in packs.strip("[]").split(",") if x.strip()]
    try:
        checks = load_checks(cfg_path, allow_empty=bool(packs))
    except ValueError as exc:
        sys.exit(str(exc))
    if packs:
        from .core.packs import load_packs
        packed = load_packs(packs)
        own = {c.cid for c in checks}
        dup = sorted({c.cid for c in packed if c.cid in own})
        if dup:
            sys.exit(f"pack 检查项编号与本项目的冲突：{dup}。改 pack 的 cid 或删掉自有同名项。")
        checks = checks + packed
    ledger = cfg.get("ledger", "evidgate_ledger.md")
    project = cfg.get("project", os.path.basename(os.path.abspath(dir_)))
    return cfg, checks, os.path.join(dir_, ledger), project


def _run(checks, dir_: str, only=None) -> Dict[str, Verdict]:
    verdicts: Dict[str, Verdict] = {}
    for c in checks:
        if only and c.cid not in only:
            continue
        v = run_check(c, cwd=dir_)
        verdicts[c.cid] = v
        print(f"  {v.cid:>3} {LABEL.get(v.status, v.status):<8} {c.name}  ─  {v.detail[:100]}")
    return verdicts


def _summary_line(verdicts) -> str:
    s = summarize(list(verdicts.values()))
    return (f"PASS {s[PASS]} · DIFF(黄) {s['DIFF']} · FAIL(红) {s[FAIL]} · "
            f"待补 {s[PENDING]} · 未覆盖 {s.get('SKIP', 0)} | "
            f"coverage {s['done']}/{s['total']} ({round(100*s['coverage'],1)}%)")


def cmd_init(a) -> int:
    d = a.dir
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, CONFIG)
    target = next((c for c in CANDIDATES if os.path.exists(os.path.join(d, c))), None)
    project = os.path.basename(os.path.abspath(d))
    body = (TPL_ACTIVE if target else TPL_EMPTY).format(project=project, target=target or "report.md")
    if os.path.exists(p) and not a.force:
        print(f"{p} exists (use --force to overwrite)")
    else:
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
        print(f"wrote {p}")
        if target:
            print(f"  starter check targets existing file: {target}")
        else:
            print("  目录里没有可交付文件，已生成注释模板；写下你的第一条检查后再 run")
    print(f"next: evidgate doctor --dir {d}  →  evidgate run --dir {d}")
    return 0


def cmd_prose_init(a) -> int:
    d = a.dir
    p = os.path.join(d, CONFIG)
    if not os.path.exists(p):
        sys.exit(f"no {CONFIG}; run `evidgate init --dir {d}` first")
    text = open(p, encoding="utf-8").read().rstrip("\n")
    if "cid: P1" in text:
        print("prose checks already present")
        return 0
    add = []
    for cid, name, rule, sev, counter in PROSE_CHECKS:
        add.append(PROSE_TEMPLATE.format(cid=cid, name=name, paper=a.file,
                                         rule=rule, counter=counter, sev=sev))
    open(p, "w", encoding="utf-8", newline="\n").write(text + "\n" + "".join(add))
    print(f"appended {len(PROSE_CHECKS)} prose checks to {p}")
    return 0




def cmd_artifact_init(a) -> int:
    """Scan a directory into a first-draft manifest, so nobody has to write JSON by hand."""
    from .plugins import artifact as art
    d = a.dir
    out = os.path.join(d, a.out)
    if os.path.exists(out) and not a.force:
        sys.exit(f"{out} exists (use --force to overwrite)")
    items = []
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in art.SKIP_DIRS]
        for f in fn:
            if f in art.SKIP_FILES or f == a.out:
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, d).replace(os.sep, "/")
            items.append({"path": rel, "role": "source", "md5": art._md5(full)})
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"root": ".", "items": items}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"wrote {out} ({len(items)} files, all role=source)")
    print("next: 把派生文件改成 role=derivative 并填 source；手改过的副本加 same_as_source: true")
    return 0




def cmd_artifact_stamp(a) -> int:
    """Record that a derivative was just generated from the current source."""
    from .plugins import artifact as art
    out = os.path.join(a.dir, a.manifest)
    if not os.path.exists(out):
        sys.exit(f"{out} 不存在；先跑 artifact-init")
    paths = a.path or []
    if not paths:
        sys.exit("--path 至少给一个派生文件，例如: --path build/report.html")
    n = art.stamp(out, paths)
    print(f"已盖章 {n} 项（记录当前源哈希）")
    print("只对刚刚重新生成的文件盖章；批量盖章等于宣称全都是新的。")
    return 0


def cmd_artifact_update(a) -> int:
    """Recompute recorded hashes after a deliberate regeneration."""
    from .plugins import artifact as art
    out = os.path.join(a.dir, a.manifest)
    if not os.path.exists(out):
        sys.exit(f"{out} 不存在；先跑 artifact-init")
    n = art.refresh(out)
    print(f"{out}: 更新了 {n} 个 md5（未动 source_md5；那要用 artifact-stamp 显式盖章）")
    print("now re-run the gate: evidgate run --dir " + a.dir)
    return 0


def cmd_pack(a) -> int:
    from .core.packs import DEFAULTS, available, load_packs
    if a.action == "list":
        names = available()
        if not names:
            print("没有可用的 pack")
            return 0
        print("可用 pack（在 evidgate.yaml 里写 packs: 名字, 名字2:参数=值）\n")
        for n in names:
            try:
                n_chk = load_packs([n])
                print(f"  {n:9s} {len(n_chk)} 条 · " + "; ".join(c.name for c in n_chk))
            except SystemExit as exc:
                print(f"  {n:9s} 加载失败：{exc}")
            params = DEFAULTS.get(n) or {}
            if params:
                print(f"  {'':9s} 参数：{' '.join(f'{k}=…' for k in params)}")
        return 0
    if not a.name:
        print("用法：evidgate pack show <名字>")
        return 2
    for c in load_packs([a.name]):
        print(f"{c.cid:6s} [{c.severity}] {c.name}")
        print(f"       method : {c.method}")
        print(f"       expect : {c.expect}")
        print(f"       counter: {c.counter}")
    return 0


def cmd_doctor(a) -> int:
    """Check the environment before blaming the project."""
    d = a.dir
    print(f"evidgate doctor · {os.path.abspath(d)}")
    cfg = os.path.join(d, CONFIG)
    if not os.path.exists(cfg):
        print(f"  [BAD ] {CONFIG} 不存在 —— 先跑: evidgate init --dir {d}")
        return 1
    try:
        _, checks, ledger_path, project = _load(d)
    except SystemExit as exc:
        if exc.code not in (0, None):
            print(f"  [BAD ] {exc.code}")
        return 1
    except Exception as exc:
        print(f"  [BAD ] yaml 解析失败: {exc}")
        return 1
    print(f"  [OK  ] yaml 可解析 · {len(checks)} 条检查 · project={project}")
    import shutil as _sh
    if os.name == "nt":
        bash = _sh.which("bash")
        print("  [WARN] 检查项在 cmd 下执行；POSIX 命令（grep/test/$()）会报「命令未找到」")
        if bash:
            print(f"         本机有 bash（{bash}），但 evidgate 当前不会用它；Windows 请优先用 builtin: 检查项")
        else:
            print("         建议：安装 Git Bash，或把检查项换成 builtin:（build/repo 包已提供 builtin 版）")
    else:
        print(f"  [OK  ] shell: {'bash' if _sh.which('bash') else 'sh'}（POSIX，检查项可用 shell 语法）")
    all_ok = True
    for c in checks:
        m = c.method.strip()
        if builtin.is_builtin(m):
            verdict = builtin.describe(m, cwd=d)
        else:
            head = (m.split() or [""])[0]
            shell_builtin = {"cd", "test", "echo", "true", "false", "export", "set",
                             "source", ".", "printf", "read", "if", "for", "while"}
            if not head:
                verdict = "BAD: method 为空"
            elif head in shell_builtin:
                verdict = "OK (shell 内建)"
            elif shutil.which(head):
                verdict = "OK (在 PATH 中)"
            elif os.path.exists(os.path.join(d, head)):
                verdict = "OK (项目内文件)"
            else:
                verdict = f"BAD: 命令 {head!r} 不在 PATH，也不是项目内文件"
        bad = verdict.startswith("BAD")
        all_ok = all_ok and not bad
        print(f"  [{'BAD ' if bad else 'OK  '}] {c.cid:>4} {c.name[:26]:26s} {verdict}")
    print(f"  ledger: {ledger_path}")
    print("  " + ("环境就绪，可以 run" if all_ok else "先修上面 BAD 项，再 run"))
    return 0 if all_ok else 1


def cmd_run(a) -> int:
    cfg, checks, ledger_path, project = _load(a.dir)
    only = set(x.strip() for x in a.only.split(",")) if a.only else None
    print(f"evidgate {__version__} · {project} · {len(checks)} checks"
          + (f" (only {sorted(only)})" if only else ""))
    verdicts = _run(checks, a.dir, only)
    build(ledger_path, checks, verdicts, project)
    print("\n" + _summary_line(verdicts))
    ok, why = release_allowed(list(verdicts.values()))
    print(("RELEASE OK  " if ok else "RELEASE BLOCKED  ") + why)
    print(f"ledger: {ledger_path}")
    print(NOTE)
    return 0 if ok else 1


def cmd_resume(a) -> int:
    cfg, checks, ledger_path, project = _load(a.dir)
    rows = load_rows(ledger_path)
    todo = resume_cids(checks, rows)
    if not todo:
        print("nothing to resume: every check has a verdict")
        return 0
    print(f"resuming {len(todo)} unresolved check(s): {', '.join(todo)}")
    verdicts = _run([c for c in checks if c.cid in todo], a.dir)
    # keep earlier verdicts from the ledger
    for cid, row in rows.items():
        if cid not in verdicts and row["status"] not in ("—", ""):
            pass
    build(ledger_path, checks, verdicts, project, previous=rows)
    print("\n" + _summary_line(verdicts) + "  (partial: only resumed rows rerun)")
    return 0


def cmd_report(a) -> int:
    cfg, checks, ledger_path, project = _load(a.dir)
    if not os.path.exists(ledger_path):
        sys.exit("no ledger yet; run `evidgate run` first")
    rows = load_rows(ledger_path)
    verdicts = {cid: type("V", (), {"cid": cid, "status": r["status"],
                                    "detail": r["evidence"], "evidence": None})()
                for cid, r in rows.items()}
    label_to_status = {v: k for k, v in LABEL.items()}
    for cid, v in verdicts.items():
        v.status = label_to_status.get(v.status, v.status)
    fails = [c.cid for c in checks if verdicts.get(c.cid) and verdicts[c.cid].status == FAIL]
    pend = [c.cid for c in checks if not verdicts.get(c.cid) or verdicts[c.cid].status == PENDING]
    yellows = [c.cid for c in checks if verdicts.get(c.cid) and verdicts[c.cid].status == "DIFF"]
    skips = [c.cid for c in checks if verdicts.get(c.cid) and verdicts[c.cid].status == SKIP]
    out = [
        f"# release gate report · {project}", "",
        "## 1. 检查表", "", "| cid | check | status | evidence |", "|---|---|---|---|",
    ]
    for c in checks:
        v = verdicts.get(c.cid)
        out.append(f"| {c.cid} | {c.name} | {LABEL.get(v.status,'—') if v else '—'} | "
                   f"{(v.detail if v else '—')[:120]} |")
    out += ["", "## 2. 待确认（黄项）", ""]
    out += [f"- {cid}" for cid in yellows] or ["- 无"]
    out += ["", "## 3. 待补与未覆盖", ""]
    out.append("**待补（没核过）**：" + ("、".join(pend) if pend else "无"))
    out.append("")
    out.append("**未覆盖（optional/不适用，不阻塞）**：" + ("、".join(skips) if skips else "无"))
    out += ["", "## 4. 放行结论", ""]
    if fails or pend:
        out.append(f"- **不可放行**：红项 {fails or '无'}；待补 {pend or '无'}")
    else:
        out.append("- **可进下一阶段**")
    if skips:
        out.append(f"- 另有 {len(skips)} 项未覆盖（{', '.join(skips)}）：不阻塞，但确实没验过")
    report_path = os.path.join(a.dir, "gate_report.md")
    with open(report_path, "w", encoding="utf-8", newline=chr(10)) as fh:
        fh.write("\n".join(out) + "\n")
    print(f"wrote {report_path}")
    return 0 if not fails and not pend else 1


def cmd_mutate(a) -> int:
    """Detection power: the same checks must pass on the baseline and go red on the mutant."""
    cfg, checks, _, _ = _load(a.dir)
    if a.only:
        keep = {x.strip() for x in a.only.split(",")}
        checks = [c for c in checks if c.cid in keep]
    base_v = {c.cid: run_check(c, cwd=a.baseline) for c in checks}
    mut_v = {c.cid: run_check(c, cwd=a.mutant) for c in checks}
    rows, caught = [], 0
    for c in checks:
        b, m = base_v[c.cid], mut_v[c.cid]
        ok = b.status == PASS and m.status != PASS
        caught += 1 if ok else 0
        rows.append((c.cid, c.name, b.status, m.status, "caught" if ok else "NOT caught"))
    print("| cid | check | baseline | mutant | detection |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1][:36]} | {r[2]} | {r[3]} | {r[4]} |")
    print(f"\ndetection power: {caught}/{len(checks)}")
    return 0 if caught == len(checks) else 1


def _fix_console() -> None:
    """Never die on a console that cannot encode our output.

    A Chinese Windows console is GBK; printing a replacement character there raises
    UnicodeEncodeError and kills the run halfway through the checks.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv=None) -> int:
    _fix_console()
    ap = argparse.ArgumentParser(prog="evidgate", description="evidence gates for documents")
    ap.add_argument("--version", action="version", version=f"evidgate {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write a starter evidgate.yaml")
    p.add_argument("--dir", default=".")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("run", help="run every check, rebuild the ledger")
    p.add_argument("--dir", default=".")
    p.add_argument("--only", default="")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("resume", help="rerun only unresolved checks")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_resume)

    p = sub.add_parser("report", help="write gate_report.md from the ledger")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("artifact-init", help="scan a directory into a first-draft artifacts.json")
    p.add_argument("--dir", default=".")
    p.add_argument("--out", default="artifacts.json")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_artifact_init)

    p = sub.add_parser("artifact-stamp", help="record that a derivative was just regenerated")
    p.add_argument("--dir", default=".")
    p.add_argument("--manifest", default="artifacts.json")
    p.add_argument("--path", action="append", help="derivative path (repeatable)")
    p.set_defaults(fn=cmd_artifact_stamp)

    p = sub.add_parser("artifact-update", help="recompute an artifact's own recorded hash")
    p.add_argument("--dir", default=".")
    p.add_argument("--manifest", default="artifacts.json")
    p.set_defaults(fn=cmd_artifact_update)

    p = sub.add_parser("pack", help="list reusable check packs, or show one expanded")
    p.add_argument("action", nargs="?", default="list", choices=["list", "show"])
    p.add_argument("name", nargs="?", default="")
    p.set_defaults(fn=cmd_pack)

    p = sub.add_parser("doctor", help="check yaml + commands before blaming the project")
    p.add_argument("--dir", default=".")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("mutate", help="prove the checks can go red")
    p.add_argument("--dir", default=".")
    p.add_argument("--baseline", required=True)
    p.add_argument("--mutant", required=True)
    p.add_argument("--only", default="")
    p.set_defaults(fn=cmd_mutate)

    p = sub.add_parser("prose", help="Chinese prose rules")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(fn=None)

    p = sub.add_parser("prose-init", help="append prose checks to evidgate.yaml")
    p.add_argument("--dir", default=".")
    p.add_argument("--file", default="paper.md")
    p.set_defaults(fn=cmd_prose_init)

    a = ap.parse_args(argv)
    if a.cmd == "prose":
        return prose.main(a.rest)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
