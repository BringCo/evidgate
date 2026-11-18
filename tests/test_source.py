"""Source-freshness rule: what it must catch, and the two ways it can lie.

The measured case these tests encode (2026-11-18): a claim cited a report that resolved
fine while a newer report on the same topic had superseded it -- "cloud runs the V4
frontend", taken from a stop-point three days older than the report recording the user
reversing that decision. Existence checks passed; the answer was wrong.

Two honest limits are encoded here as tests, because both showed up in the live
three-state run:

  * unscoped, ANY newer file reds the check -- an unrelated thread's report sitting in
    the same tree (measured with `04_d.md`), which is why --dir/--glob are mandatory in
    practice;
  * it sees mtime only. cp -p carries the old mtime across, so a rewritten report can
    look ancient and pass. The cited file's md5 is printed so callers can pair the two.
"""
import contextlib
import io
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evidgate.plugins import source  # noqa: E402


def _write(dirpath, name, body="# x\n", mtime=None):
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _run(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = source.run("fresh", argv)
    return code, buf.getvalue()


class TestSourceFresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="srcfresh_")
        base = time.time() - 10_000
        self.old = _write(self.tmp, "01_a.md", "# 报告 A\n", base)
        self.mid = _write(self.tmp, "02_b.md", "# 报告 B\n", base + 100)
        self.new = _write(self.tmp, "03_c.md", "# 报告 C\n", base + 200)

    def test_newest_passes(self):
        code, out = _run(["--cited", self.new])
        self.assertEqual(code, 0)
        self.assertIn("OK", out)
        self.assertIn("newer=0", out)

    def test_stale_citation_reds_and_names_the_newer_file(self):
        code, out = _run(["--cited", self.old])
        self.assertEqual(code, 1)
        self.assertIn("NEWER", out)
        self.assertIn("03_c.md", out)
        self.assertIn("02_b.md", out)
        self.assertIn("VERDICT", out)

    def test_prints_cited_md5_so_mtime_can_be_paired_with_content(self):
        code, out = _run(["--cited", self.new])
        self.assertEqual(code, 0)
        self.assertRegex(out, r"md5=[0-9a-f]{12}")

    def test_unrelated_newer_file_reds_when_unscoped(self):
        # Honest limit, encoded: this is why --dir/--glob must scope to one topic.
        _write(self.tmp, "04_unrelated_topic.md", "# 另一条线\n", time.time() + 50)
        code, out = _run(["--cited", self.new])
        self.assertEqual(code, 1)
        self.assertIn("04_unrelated_topic.md", out)

    def test_glob_narrowing_removes_the_false_red(self):
        _write(self.tmp, "04_unrelated_topic.md", "# 另一条线\n", time.time() + 50)
        code, out = _run(["--cited", self.new, "--glob", "0[123]_*.md"])
        self.assertEqual(code, 0)
        self.assertIn("newer=0", out)

    def test_history_folder_snapshot_is_not_counted_as_newer(self):
        # A dated snapshot under _历史原稿/ is an older version with a fresh mtime; counting
        # it reds a correct citation (measured live before this guard existed).
        hist = os.path.join(self.tmp, "_历史原稿")
        os.makedirs(hist, exist_ok=True)
        _write(hist, "03_c.md", "# 旧版快照\n", time.time() + 3600)
        code, out = _run(["--cited", self.new])
        self.assertEqual(code, 0, out)
        self.assertIn("newer=0", out)

    def test_missing_cited_file_declines_not_passes(self):
        code, out = _run(["--cited", os.path.join(self.tmp, "nope.md")])
        self.assertEqual(code, 2)
        self.assertIn("DECLINED", out)

    def test_dir_option_scopes_the_scan(self):
        other = tempfile.mkdtemp(prefix="srcfresh_other_")
        _write(other, "99_other.md", "# 别处\n", time.time() + 500)
        code, out = _run(["--cited", self.new, "--dir", self.tmp])
        self.assertEqual(code, 0)

    def test_cited_file_is_not_counted_as_its_own_newer(self):
        code, out = _run(["--cited", self.new])
        self.assertEqual(code, 0)
        self.assertNotIn("03_c.md  ", out.split("VERDICT")[0].split("newer:")[-1] if "newer:" in out else "")


if __name__ == "__main__":
    unittest.main()