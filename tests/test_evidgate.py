"""The gate's own tests. Run: python3 -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from evidgate.core.check import Check, _mini_yaml, load_checks
from evidgate.core.evidence import Evidence, collect
from evidgate.core.gate import (DIFF, FAIL, PASS, PENDING, evaluate,
                                release_allowed, run_check)
from evidgate.ledger import build, load_rows, resume_cids


class TestCounterTestDiscipline(unittest.TestCase):
    def test_check_without_counter_test_is_refused(self):
        c = Check("C1", "x", "true", "exit:0", counter="  ")
        with self.assertRaises(ValueError) as ctx:
            c.validate()
        self.assertIn("counter-test", str(ctx.exception))

    def test_load_refuses_missing_counter(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "g.yaml")
            open(p, "w").write("checks:\n  - cid: C1\n    name: n\n    method: true\n    expect: exit:0\n")
            with self.assertRaises(ValueError):
                load_checks(p)


class TestMiniYaml(unittest.TestCase):
    def test_parses_the_example_without_pyyaml(self):
        with open(os.path.join(ROOT, "examples", "evidgate.yaml"), encoding="utf-8") as fh:
            text = fh.read()
        data = _mini_yaml.__wrapped__(text) if hasattr(_mini_yaml, "__wrapped__") else None
        # exercise the dependency-free branch directly
        import evidgate.core.check as ch
        real = ch.yaml if hasattr(ch, "yaml") else None
        try:
            if real is not None:
                ch.yaml = None
            got = ch._mini_yaml(text)
        finally:
            if real is not None:
                ch.yaml = real
        self.assertEqual(len(got["checks"]), 6)
        self.assertEqual(got["checks"][0]["cid"], "C1")
        self.assertEqual(got["checks"][1]["expect"], "exit:0; regex:正文句 \\d+")


class TestThreeStates(unittest.TestCase):
    def _ev(self, code, out=""):
        return Evidence("cmd", code, out, "", 0.1, "2026-01-01T00:00:00")

    def test_pass(self):
        c = Check("C1", "n", "true", "exit:0", counter="break it", severity="red")
        self.assertEqual(evaluate(c, self._ev(0, "OK"))[0], PASS)

    def test_red_becomes_fail_yellow_becomes_diff(self):
        red = Check("C1", "n", "false", "exit:0", counter="break it", severity="red")
        yellow = Check("C2", "n", "false", "exit:0", counter="break it", severity="yellow")
        self.assertEqual(evaluate(red, self._ev(2))[0], FAIL)
        self.assertEqual(evaluate(yellow, self._ev(3))[0], DIFF)

    def test_manual_is_pending_and_blocks_release(self):
        c = Check("C1", "n", "true", "manual", counter="break it")
        v = run_check(c, cwd=ROOT)
        self.assertEqual(v.status, PENDING)
        ok, why = release_allowed([v])
        self.assertFalse(ok)
        self.assertIn("unchecked", why)

    def test_fail_blocks_release(self):
        red = Check("C1", "n", "false", "exit:0", counter="x", severity="red")
        v = run_check(red, cwd=ROOT)
        ok, why = release_allowed([v])
        self.assertFalse(ok)
        self.assertIn("blocked", why)

    def test_all_probes_satisfied_allows_release(self):
        ok_c = Check("C1", "n", "true", "exit:0", counter="x")
        ok, _ = release_allowed([run_check(ok_c, cwd=ROOT)])
        self.assertTrue(ok)


class TestLedger(unittest.TestCase):
    def _checks(self):
        return [Check("C1", "a", "true", "exit:0", counter="x"),
                Check("P2", "b", "true", "exit:0", counter="x", severity="yellow")]

    def test_idempotent_build(self):
        checks = self._checks()
        v = {c.cid: run_check(c, cwd=ROOT) for c in checks}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.md")
            a = build(p, checks, v, "demo")
            with open(p, "rb") as fh:
                b1 = fh.read()
            build(p, checks, v, "demo")
            with open(p, "rb") as fh:
                b2 = fh.read()
        self.assertEqual(b1, b2, "ledger rebuild is not byte-identical")

    def test_resume_sees_letter_prefixed_ids(self):
        checks = self._checks()
        v = {c.cid: run_check(c, cwd=ROOT) for c in checks}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.md")
            build(p, checks, v, "demo")
            rows = load_rows(p)
        self.assertIn("P2", rows)
        self.assertEqual(resume_cids(checks, rows), [])

    def test_resume_finds_untouched_checks(self):
        checks = self._checks()
        rows = {"C1": {"status": "PASS", "evidence": "e", "ts": "t"}}
        self.assertEqual(resume_cids(checks, rows), ["P2"])

    def test_pipe_is_escaped_once(self):
        c = [Check("C1", "a|b", "true", "exit:0", counter="x|y")]
        v = {"C1": run_check(c[0], cwd=ROOT)}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.md")
            text = build(p, c, v, "demo")
        self.assertNotIn("\\\\|", text, "double-escaped pipe in table")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestBuiltinDispatch(unittest.TestCase):
    """A check the tool generates must run the way the tool is installed (no PATH)."""

    def test_builtin_prose_runs_in_process(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "p.md"), "w", encoding="utf-8") as fh:
                fh.write("本系统首次实现校园二手书的智能定价功能。\n")
            ev = collect("builtin:prose:absolutes p.md", cwd=d)
        self.assertEqual(ev.exit_code, 2)
        self.assertIn("首次", ev.stdout)

    def test_unknown_plugin_is_reported(self):
        ev = collect("builtin:nope:rule p.md", cwd=ROOT)
        self.assertIsNone(ev.exit_code)
        self.assertIn("unknown builtin plugin", ev.stderr)


class TestDiagnosability(unittest.TestCase):
    def test_missing_command_explains_127(self):
        c = Check("C1", "n", "definitely-not-a-command-xyz", "exit:0", counter="x")
        v = run_check(c, cwd=ROOT)
        self.assertEqual(v.status, FAIL)
        self.assertIn("命令未找到", v.detail)

    def test_doctor_flags_missing_command(self):
        import io
        import contextlib
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "evidgate.yaml"), "w", encoding="utf-8") as fh:
                fh.write("checks:\n  - cid: C1\n    name: n\n"
                         "    method: no-such-binary-xyz\n    expect: exit:0\n"
                         "    counter: x\n    severity: red\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["doctor", "--dir", d])
        self.assertEqual(rc, 1)
        self.assertIn("BAD", buf.getvalue())


class TestOptionalSkip(unittest.TestCase):
    def test_optional_failure_is_skip_and_does_not_block(self):
        c = Check("C1", "n", "false", "exit:0", counter="x", optional=True)
        v = run_check(c, cwd=ROOT)
        self.assertEqual(v.status, "SKIP")
        ok, _ = release_allowed([v])
        self.assertTrue(ok, "an optional/not-applicable check must not block release")


class TestInitAdaptive(unittest.TestCase):
    def test_empty_dir_gets_commented_template(self):
        import io
        import contextlib
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "--dir", d])
            with open(os.path.join(d, "evidgate.yaml"), encoding="utf-8") as fh:
                txt = fh.read()
            self.assertIn("# - cid: C1", txt)
            with self.assertRaises(ValueError) as ctx:
                load_checks(os.path.join(d, "evidgate.yaml"))
            self.assertIn("没有任何启用", str(ctx.exception))

    def test_existing_file_gets_a_runnable_check(self):
        import io
        import contextlib
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "draft.md"), "w", encoding="utf-8") as fh:
                fh.write("x\n")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "--dir", d])
            checks = load_checks(os.path.join(d, "evidgate.yaml"))
        self.assertIn("draft.md", checks[0].method)


class TestArtifactPlugin(unittest.TestCase):
    """Manifest-driven checks: registered? not stale? not hand-edited? not orphaned?"""

    def _project(self, d):
        import json
        import time
        os.makedirs(os.path.join(d, "src"))
        os.makedirs(os.path.join(d, "build"))
        os.makedirs(os.path.join(d, "draft"))
        src = os.path.join(d, "src", "s.md")
        html = os.path.join(d, "build", "s.html")
        old = os.path.join(d, "build", "s.pdf")
        cp = os.path.join(d, "draft", "c.md")
        for p, t in [(src, "# source\n"), (html, "html\n"), (old, "pdf\n"), (cp, "changed\n")]:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(t)
        with open(os.path.join(d, "note.txt"), "w", encoding="utf-8") as fh:
            fh.write("unregistered\n")
        now = time.time()
        os.utime(old, (now - 9000, now - 9000))   # derivative older than source
        os.utime(src, (now - 3600, now - 3600))
        os.utime(html, (now, now))
        man = {"root": ".", "items": [
            {"path": "src/s.md", "role": "source"},
            {"path": "build/s.html", "role": "derivative", "source": "src/s.md"},
            {"path": "build/s.pdf", "role": "derivative", "source": "src/s.md"},
            {"path": "draft/c.md", "role": "derivative", "source": "src/s.md",
             "same_as_source": True},
        ]}
        with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        return d

    def test_rules(self):
        with tempfile.TemporaryDirectory() as d:
            self._project(d)
            self.assertEqual(collect("builtin:artifact:manifest artifacts.json", cwd=d).exit_code, 0)
            self.assertEqual(collect("builtin:artifact:stale artifacts.json", cwd=d).exit_code, 3)
            self.assertEqual(collect("builtin:artifact:sync artifacts.json", cwd=d).exit_code, 2)
            ev = collect("builtin:artifact:orphan artifacts.json --dir .", cwd=d)
            self.assertEqual(ev.exit_code, 3)
            self.assertIn("note.txt", ev.stdout)

    def test_manifest_catches_hand_edit_when_md5_recorded(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            self._project(d)
            mp = os.path.join(d, "artifacts.json")
            with open(mp, encoding="utf-8") as fh:
                man = json.load(fh)
            man["items"][1]["md5"] = "0" * 32   # recorded hash will not match
            with open(mp, "w", encoding="utf-8") as fh:
                json.dump(man, fh)
            ev = collect("builtin:artifact:manifest artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 2)
        self.assertIn("内容变了", ev.stdout)

    def test_gate_own_files_are_not_orphans(self):
        with tempfile.TemporaryDirectory() as d:
            self._project(d)
            for name in ("evidgate.yaml", "evidgate_ledger.md", "gate_report.md"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
            ev = collect("builtin:artifact:orphan artifacts.json --dir .", cwd=d)
        self.assertNotIn("evidgate.yaml", ev.stdout)
        self.assertIn("note.txt", ev.stdout)


class TestReportCoversSkip(unittest.TestCase):
    """The report is the artifact a human reads; SKIP items must not vanish from it."""

    def test_skip_and_pending_listed_separately(self):
        import contextlib
        import io
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "evidgate.yaml"), "w", encoding="utf-8") as fh:
                fh.write(
                    "project: t\nledger: l.md\nchecks:\n"
                    "  - cid: S1\n    name: optional-fails\n    method: 'false'\n"
                    "    expect: exit:0\n    counter: x\n    severity: red\n"
                    "    optional: true\n"
                    "  - cid: R1\n    name: needs-a-human\n    method: 'true'\n"
                    "    expect: manual\n    counter: x\n    severity: red\n")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["run", "--dir", d])
                main(["report", "--dir", d])
            with open(os.path.join(d, "gate_report.md"), encoding="utf-8") as fh:
                rep = fh.read()
        self.assertIn("S1", rep)
        self.assertIn("R1", rep)
        self.assertIn("未覆盖", rep)
        self.assertIn("待补", rep)
        # guard against the report collapsing into one line of literal \n
        self.assertGreater(rep.count("\n"), 10, "report is not multi-line")


class TestArtifactStaleByHash(unittest.TestCase):
    """stale must be decided by content hash, never by mtime."""

    def _mk(self, d):
        import hashlib
        import json
        os.makedirs(os.path.join(d, "src"))
        os.makedirs(os.path.join(d, "build"))
        sp = os.path.join(d, "src", "s.md")
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write("v1\n")
        with open(sp, "rb") as fh:
            src_md5 = hashlib.md5(fh.read()).hexdigest()
        with open(os.path.join(d, "build", "s.html"), "w", encoding="utf-8") as fh:
            fh.write("generated from v1\n")
        man = {"root": ".", "ignore": ["*.log"], "items": [
            {"path": "src/s.md", "role": "source"},
            {"path": "build/s.html", "role": "derivative", "source": "src/s.md",
             "source_md5": src_md5},
        ]}
        with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        return sp

    def test_clean_when_source_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            self._mk(d)
            self.assertEqual(collect("builtin:artifact:stale artifacts.json", cwd=d).exit_code, 0)

    def test_stale_when_source_changed_even_if_files_are_new(self):
        with tempfile.TemporaryDirectory() as d:
            sp = self._mk(d)
            with open(sp, "a", encoding="utf-8") as fh:
                fh.write("v2\n")   # newer file, but the derivative is now out of date
            ev = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 3)
        self.assertIn("源已变", ev.stdout)

    def test_refresh_does_not_clear_stale(self):
        """artifact-update refreshes hashes; it must NOT declare a derivative fresh."""
        import contextlib
        import io
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            sp = self._mk(d)
            with open(sp, "a", encoding="utf-8") as fh:
                fh.write("v2\n")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact-update", "--dir", d])
            ev = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 3, "update must not launder a stale derivative")

    def test_missing_source_md5_is_reported_not_silently_passed(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            self._mk(d)
            mp = os.path.join(d, "artifacts.json")
            with open(mp, encoding="utf-8") as fh:
                man = json.load(fh)
            del man["items"][1]["source_md5"]
            with open(mp, "w", encoding="utf-8") as fh:
                json.dump(man, fh)
            ev = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 3)
        self.assertIn("未记录 source_md5", ev.stdout)
        self.assertIn("artifact-stamp", ev.stdout, "hint must point at the only writer")

    def test_ignore_rule_silences_matching_orphans(self):
        with tempfile.TemporaryDirectory() as d:
            self._mk(d)
            for name in ("debug.log", "real.txt"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
            ev = collect("builtin:artifact:orphan artifacts.json --dir .", cwd=d)
        self.assertNotIn("debug.log", ev.stdout)
        self.assertIn("real.txt", ev.stdout)


class TestManifestOnlyHashesDerivatives(unittest.TestCase):
    """Editing a source is the normal workflow; only derivatives are guarded by hash."""

    def test_editing_a_source_does_not_trip_manifest(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as d:
            sp = os.path.join(d, "s.md")
            with open(sp, "w", encoding="utf-8") as fh:
                fh.write("v1\n")
            with open(sp, "rb") as fh:
                src_md5 = hashlib.md5(fh.read()).hexdigest()
            with open(os.path.join(d, "out.txt"), "w", encoding="utf-8") as fh:
                fh.write("derived\n")
            man = {"root": ".", "items": [
                {"path": "s.md", "role": "source", "md5": src_md5},
                {"path": "out.txt", "role": "derivative", "source": "s.md",
                 "source_md5": src_md5},
            ]}
            with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
                json.dump(man, fh)
            with open(sp, "a", encoding="utf-8") as fh:
                fh.write("v2\n")   # edit the source on purpose
            ev_manifest = collect("builtin:artifact:manifest artifacts.json", cwd=d)
            ev_stale = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev_manifest.exit_code, 0, "editing a source must not fail manifest")
        self.assertEqual(ev_stale.exit_code, 3, "but the derivative is now out of date")

    def test_hand_editing_a_derivative_still_fails(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "s.md"), "w", encoding="utf-8") as fh:
                fh.write("v1\n")
            op = os.path.join(d, "out.txt")
            with open(op, "w", encoding="utf-8") as fh:
                fh.write("derived\n")
            with open(op, "rb") as fh:
                out_md5 = hashlib.md5(fh.read()).hexdigest()
            man = {"root": ".", "items": [
                {"path": "out.txt", "role": "derivative", "source": "s.md", "md5": out_md5},
            ]}
            with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
                json.dump(man, fh)
            with open(op, "a", encoding="utf-8") as fh:
                fh.write("hand edit\n")
            ev = collect("builtin:artifact:manifest artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 2)
        self.assertIn("内容变了", ev.stdout)


class TestStampingIsExplicit(unittest.TestCase):
    """A gate must never be able to launder a stale derivative into a fresh one."""

    def _proj(self, d):
        import hashlib
        import json
        sp = os.path.join(d, "s.md")
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write("v1\n")
        with open(sp, "rb") as fh:
            v1 = hashlib.md5(fh.read()).hexdigest()
        dp = os.path.join(d, "out.txt")
        with open(dp, "w", encoding="utf-8") as fh:
            fh.write("derived from v1\n")
        with open(dp, "rb") as fh:
            dm = hashlib.md5(fh.read()).hexdigest()
        man = {"root": ".", "items": [
            {"path": "s.md", "role": "source"},
            {"path": "out.txt", "role": "derivative", "source": "s.md",
             "md5": dm, "source_md5": v1},
        ]}
        with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
            json.dump(man, fh)
        with open(sp, "a", encoding="utf-8") as fh:
            fh.write("v2\n")          # source moved on
        return dp

    def test_update_does_not_launder_a_stale_derivative(self):
        import contextlib
        import io
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            self._proj(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact-update", "--dir", d])
            ev = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 3,
                         "artifact-update must not clear a stale item without regenerating")

    def test_stamp_after_real_regeneration_clears_it(self):
        import contextlib
        import io
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            dp = self._proj(d)
            with open(dp, "w", encoding="utf-8") as fh:
                fh.write("derived from v2\n")     # actually regenerated
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact-stamp", "--dir", d, "--path", "out.txt"])
            ev = collect("builtin:artifact:stale artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 0)

    def test_manifest_detects_derivative_by_structure_not_label(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "s.md"), "w", encoding="utf-8") as fh:
                fh.write("v1\n")
            with open(os.path.join(d, "out.txt"), "w", encoding="utf-8") as fh:
                fh.write("derived\n")
            man = {"root": ".", "items": [
                {"path": "out.txt", "source": "s.md", "md5": "0" * 32},  # no role field
            ]}
            with open(os.path.join(d, "artifacts.json"), "w", encoding="utf-8") as fh:
                json.dump(man, fh)
            ev = collect("builtin:artifact:manifest artifacts.json", cwd=d)
        self.assertEqual(ev.exit_code, 2, "a derivative must be detected structurally")
        self.assertIn("内容变了", ev.stdout)

    def test_update_adds_no_md5_to_sources(self):
        import contextlib
        import io
        import json
        from evidgate.cli import main
        with tempfile.TemporaryDirectory() as d:
            self._proj(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact-update", "--dir", d])
            with open(os.path.join(d, "artifacts.json"), encoding="utf-8") as fh:
                man = json.load(fh)
        self.assertNotIn("md5", man["items"][0])


class TestProseAgainstRealWorldWording(unittest.TestCase):
    """Calibrated on a real 581-sentence manuscript, not on invented examples.

    Before this calibration the three rules fired 222 times on that draft with ~95%
    false positives; the descriptive uses below are what caused it.
    """

    def _hits(self, rule, sentence):
        import evidgate.plugins.prose as prose
        return prose.RULES[rule][0]([(1, sentence)])

    def test_descriptive_unique_is_not_a_priority_claim(self):
        self.assertEqual(self._hits(
            "absolutes", "四个主干中唯一缺口为负者反向提升 19.34%。"), [])

    def test_descriptive_first_is_not_a_priority_claim(self):
        self.assertEqual(self._hits(
            "absolutes", "每块电池的循环序列截断到首次跌破阈值处。"), [])

    def test_actual_priority_claim_still_fires(self):
        self.assertTrue(self._hits(
            "absolutes", "本系统首次实现校园二手书的智能定价。"))

    def test_claim_with_chart_reference_is_not_unccited(self):
        self.assertEqual(self._hits(
            "uncited", "这一分解决定了方法取向，参见 §4 与图 4。"), [])

    def test_claim_with_evidence_pair_is_not_uncited(self):
        self.assertEqual(self._hits(
            "uncited", "结构式锚定相对基线下降 30.53%（20/20，Holm 1.70e-12）。"), [])

    def test_bare_conclusion_still_fires(self):
        self.assertTrue(self._hits("uncited", "结果说明该方法优于传统人工定价。"))

    def test_bare_percentage_still_fires(self):
        self.assertTrue(self._hits("numeral_scope", "在验证组上，预估误差降低 21.2%。"))

    def test_qualified_statistic_does_not_fire(self):
        self.assertEqual(self._hits(
            "numeral_scope", "误差降低 21.2%（20/20 划分，脚本 scripts/a.py）。"), [])

    def test_formula_lines_are_not_scanned(self):
        import evidgate.plugins.prose as prose
        body = "正文一句足够长的句子用来测试。\n$$ x = mean(a) / b \\times 100 $$\n"
        lines = prose.sentences(body)
        self.assertEqual(len(lines), 1)


class TestPacks(unittest.TestCase):
    def test_figures_pack_expands_to_three_checks(self):
        from evidgate.core.packs import load_packs
        chks = load_packs(["figures"])
        self.assertEqual([c.cid for c in chks], ["GF1", "GF2", "GF3"])
        self.assertIn("artifacts.json", chks[0].method)
        for c in chks:
            self.assertTrue(c.counter.strip(), "a pack check must carry its counter-test")

    def test_options_override_defaults(self):
        from evidgate.core.packs import load_packs
        chks = load_packs(["figures:manifest=mine.json,outdir=figs"])
        self.assertIn("mine.json", chks[0].method)
        self.assertIn("figs", chks[2].name)
        self.assertIn("--dir figs", chks[2].method)

    def test_unknown_pack_fails_loudly(self):
        from evidgate.core.packs import load_packs
        with self.assertRaises(SystemExit):
            load_packs(["no_such_pack"])

    def test_missing_placeholder_value_fails(self):
        from evidgate.core.packs import _sub
        with self.assertRaises(SystemExit):
            _sub("hello {missing}", {}, "figures")

    def test_pack_only_project_may_have_no_own_checks(self):
        import tempfile
        from evidgate.core.check import load_checks
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "evidgate.yaml")
            with open(cfg, "w", encoding="utf-8") as fh:
                fh.write("project: x\npacks: figures\n")
            self.assertEqual(load_checks(cfg, allow_empty=True), [])
            with self.assertRaises(ValueError):
                load_checks(cfg)

    def test_credentials_never_reach_the_ledger(self):
        from evidgate.core.evidence import redact
        out = redact("AWS_KEY=AKIAIOSFODNN7EXAMPLE\nother line")
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", out)
        self.assertIn("REDACTED", out)
        self.assertIn("other line", out)


class TestMissingCommand(unittest.TestCase):
    """A command that never ran must never produce a verdict of its own."""

    def test_missing_command_with_exit1_expectation_is_red_not_green(self):
        # The exact Windows failure: `grep` does not exist, cmd exits 1, and
        # `expect: exit:1` means "grep found nothing" -- a silent false green.
        from evidgate.core.check import Check
        from evidgate.core.gate import run_check
        c = Check(cid="X1", name="no TODO left",
                  method="definitely_no_such_tool_xyz -rn TODO .",
                  expect="exit:1", counter="add a TODO", severity="red")
        v = run_check(c, cwd="/tmp")
        self.assertEqual(v.status, "FAIL")
        self.assertIn("命令未找到", v.detail)

    def test_missing_command_on_optional_check_is_skip(self):
        from evidgate.core.check import Check
        from evidgate.core.gate import run_check
        c = Check(cid="X2", name="optional tool", method="definitely_no_such_tool_xyz",
                  expect="exit:1", counter="c", severity="red", optional=True)
        self.assertEqual(run_check(c, cwd="/tmp").status, "SKIP")

    def test_real_failure_is_not_mistaken_for_a_missing_tool(self):
        from evidgate.core.check import Check
        from evidgate.core.gate import run_check
        c = Check(cid="X3", name="grep on a missing dir", severity="red",
                  method="grep -rn TODO /tmp/no_such_dir_abc", expect="exit:2",
                  counter="c")
        self.assertEqual(run_check(c, cwd="/tmp").status, "PASS")

    def test_missing_tool_detection_across_shells(self):
        from evidgate.core.evidence import _decode, _missing_tool
        gbk = _decode(b"'grep' \xb2\xbb\xca\xc7\xc4\xda\xb2\xbf\xbb\xf2\xcd\xe2\xb2\xbf\xc3\xfc\xc1\xee")
        self.assertTrue(_missing_tool(127, "bash: grep: command not found"))
        self.assertTrue(_missing_tool(127, "sh: 1: grep: not found"))
        self.assertTrue(_missing_tool(1, "'grep' is not recognized as an internal or external command"))
        self.assertTrue(_missing_tool(1, gbk), "a GBK console must be decoded before matching")
        self.assertFalse(_missing_tool(1, ""))
        self.assertFalse(_missing_tool(2, "grep: dist: No such file or directory"))


class TestShellDeclaration(unittest.TestCase):
    """Default is no shell; a shell is an explicit, declared choice."""

    def test_default_runs_without_a_shell(self):
        from evidgate.core.evidence import _build_argv
        argv, err = _build_argv("grep -rn TODO .", "")
        self.assertEqual(err, "")
        self.assertEqual(argv, ["grep", "-rn", "TODO", "."])

    def test_explicit_bash_goes_through_bash(self):
        from evidgate.core.evidence import _build_argv, find_posix_shell
        argv, err = _build_argv("echo a && echo b", "bash")
        self.assertEqual(err, "")
        if find_posix_shell():
            self.assertEqual(argv[1], "-lc")
            self.assertIn("bash", argv[0])

    def test_shell_syntax_without_shell_says_what_to_do(self):
        from evidgate.core.evidence import collect
        ev = collect("cd src && python3 -m unittest", cwd="/tmp")
        self.assertTrue(ev.command_not_found, "argv[0]='cd' cannot be executed directly")
        self.assertIn("shell: bash", ev.not_found_hint)

    def test_invalid_shell_name_is_rejected_at_load(self):
        from evidgate.core.check import Check
        with self.assertRaises(ValueError):
            Check(cid="X", name="n", method="m", expect="exit:0",
                  counter="c", shell="fish").validate()
