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
