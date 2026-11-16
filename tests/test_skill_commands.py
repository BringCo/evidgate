"""SKILL.md is a contract: every command it shows must actually run.

A skill that drifts out of sync with the CLI is the same failure this tool exists to
catch — a documented step that nobody re-runs. This module executes the commands inside
the `skill-check` markers in `skill/evidgate/SKILL.md`, in one sandbox, in the
   documented order.

Two ways this test could lie, both closed:

* the block is empty or the markers disappear  -> `test_block_declares_enough_commands`
* the subprocess cannot import the package, so every command exits 1 and "1 is allowed"
  -> `test_the_cli_is_importable_from_a_foreign_cwd` plus `No module named` in BAD_OUTPUT
"""
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skill", "evidgate", "SKILL.md")
START = "<!-- skill-check:start -->"
END = "<!-- skill-check:end -->"

# Output that means "the command did not exist / the argument was not accepted / the
# process never got as far as running anything", i.e. the documentation is wrong.
BAD_OUTPUT = ("Traceback", "unrecognized arguments", "invalid choice",
              "No such file or directory", "unknown command", "No module named")


def load_commands():
    """Commands from the skill-check block, in file order."""
    with open(SKILL, encoding="utf-8") as fh:
        md = fh.read()
    m = re.search(re.escape(START) + r"(.*?)" + re.escape(END), md, re.S)
    if not m:
        raise AssertionError("skill-check markers missing from skill/evidgate/SKILL.md")
    cmds = []
    for line in m.group(1).splitlines():
        line = line.split("  #")[0].strip()
        if not line or line.startswith(("#", "```")):
            continue
        if line.startswith("evidgate "):
            cmds.append(line)
    return cmds


class TestSkillCommandsAreReal(unittest.TestCase):

    def _run(self, argv, cwd):
        env = dict(os.environ)
        env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run([sys.executable, "-m", "evidgate.cli", *argv],
                              cwd=cwd, capture_output=True, text=True, env=env)

    def test_block_declares_enough_commands(self):
        cmds = load_commands()
        self.assertGreaterEqual(
            len(cmds), 8, f"skill-check block only declares {len(cmds)} commands: {cmds}")

    def test_the_cli_is_importable_from_a_foreign_cwd(self):
        """Guards every other assertion: a crashed process also exits 1."""
        with tempfile.TemporaryDirectory() as d:
            r = self._run(["--version"], d)
            out = (r.stdout or "") + (r.stderr or "")
            self.assertEqual(r.returncode, 0, out[-400:])
            self.assertIn("evidgate", r.stdout)

    def test_every_documented_command_runs(self):
        cmds = load_commands()
        for cmd in cmds:
            self.assertNotIn("<", cmd, f"placeholder left in an executable command: {cmd}")
        with tempfile.TemporaryDirectory() as d:
            # The sandbox needs something to gate; the prose rules need a Chinese draft.
            with open(os.path.join(d, "draft.md"), "w", encoding="utf-8") as fh:
                fh.write("本文首次实现了全自动估价流程，误差降低 18.4%。\n")
            for cmd in cmds:
                argv = shlex.split(cmd)[1:]          # drop the leading `evidgate`
                r = self._run(argv, d)
                out = (r.stdout or "") + (r.stderr or "")
                # 0 = fine, 1 = blocked / not ready, both are documented outcomes.
                self.assertIn(r.returncode, (0, 1),
                              f"`{cmd}` exited {r.returncode}\n{out[-400:]}")
                self.assertTrue(out.strip(), f"`{cmd}` printed nothing at all")
                for bad in BAD_OUTPUT:
                    self.assertNotIn(bad, out, f"`{cmd}` produced {bad!r}\n{out[-400:]}")


if __name__ == "__main__":
    unittest.main()
