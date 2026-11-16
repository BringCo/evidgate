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
        text = open(os.path.join(ROOT, "examples", "evidgate.yaml"), encoding="utf-8").read()
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
            b1 = open(p, "rb").read()
            build(p, checks, v, "demo")
            b2 = open(p, "rb").read()
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
