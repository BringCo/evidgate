"""Clause-coverage rule: what it must catch, and what it must not claim.

The measured case these tests encode: a plan restated five of six requirements
from a notice and dropped the sixth -- the one written as a permission ("也可自行
安排汇报内容顺序") rather than an obligation. Any obligation-keyword filter misses
it, and the plan cited the notice as its source, so a source-existence check passed.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from evidgate.plugins.coverage import (
    _is_heading,
    _norm,
    _strip_page_numbers,
    coverage,
    run,
    split_clauses,
)

# The line break is deliberate: pdftotext splits "打分项顺序" across two lines, and a
# matcher that does not normalise newlines can never find this clause again.
NOTICE = """一、赛前准备
1. 请所有参赛队长加入赛题 QQ 群，通知在群内发布；
2. 由参赛团队代表（首选队长，队员也可）对照评分表打
分项顺序进行 PPT 汇报，也可自行安排汇报内容顺序；
3. 提交的录制视频须无快进，无剪辑，仅可添加字幕。
"""

PLAN_OK = """# 作战计划
- 队长加入 QQ 群，通知在群里看
- 汇报：对照评分表打分项顺序进行 PPT 汇报，也可自行安排汇报内容顺序
- 录制视频无快进、无剪辑，只加字幕
"""

PLAN_MISSING = """# 作战计划
- 队长加入 QQ 群，通知在群里看
- 录制视频无快进、无剪辑，只加字幕
"""


class TestClauseSplitting(unittest.TestCase):
    def test_splits_on_clause_number_without_cutting_linebreaks(self):
        clauses = split_clauses(NOTICE)
        self.assertEqual(len(clauses), 4)  # heading + 3 numbered
        keep = [c for c in clauses if "打分项顺序" in _norm(c.text)]
        self.assertEqual(len(keep), 1, "a clause broken across lines must stay one clause")
        self.assertIn("也可自行安排", keep[0].text)

    def test_bare_heading_is_not_a_clause(self):
        headings = [c for c in split_clauses(NOTICE) if _is_heading(c)]
        self.assertEqual([c.cid for c in headings], ["一、"])

    def test_heading_with_body_is_kept(self):
        # "三、作品提交各参赛选手需在…" -- long and punctuated, not a bare title
        text = "三、作品提交各参赛选手需在 11 月 18 日 23:30 提交，逾期视为弃赛。\n"
        clauses = split_clauses(text)
        self.assertFalse(_is_heading(clauses[0]))


class TestPageMarker(unittest.TestCase):
    def test_marker_on_its_own_line_does_not_glue_two_clauses(self):
        # Measured: with \s* the marker ate the newlines and "2." stopped
        # starting a line, so clause 2 merged into clause 1 (26 instead of 27).
        text = "1. 甲条款正文；\n— 4 —\n2. 乙条款正文；\n"
        out = _strip_page_numbers(text)
        self.assertIn("\n2.", out)
        self.assertEqual([c.cid for c in split_clauses(out)], ["1.", "2."])

    def test_marker_inside_a_word_still_rejoins_it(self):
        out = _strip_page_numbers("…仅可添加字幕。一— 5 —经发现，视为无效作品")
        self.assertIn("一经发现", out)


class TestCoverage(unittest.TestCase):
    def test_present_clause_scores_high(self):
        clause = [c for c in split_clauses(NOTICE) if "打分项顺序" in _norm(c.text)][0]
        self.assertGreater(coverage(clause.text, _norm(PLAN_OK), 4), 0.3)

    def test_dropped_clause_scores_zero(self):
        clause = [c for c in split_clauses(NOTICE) if "打分项顺序" in _norm(c.text)][0]
        self.assertEqual(coverage(clause.text, _norm(PLAN_MISSING), 4), 0.0)

    def test_local_edit_barely_moves_the_score(self):
        # Documented limit: this finds missing clauses, not edited ones.
        clause = "提交的录制视频须无快进，无剪辑，仅可添加字幕；"
        before = coverage(clause, _norm(PLAN_OK), 4)
        after = coverage(clause, _norm("- 录制视频无快进、无剪辑，只加字幕\n"), 4)
        self.assertGreater(after, 0.0)
        self.assertLess(abs(before - after), 0.35)


class TestRuleExitCodes(unittest.TestCase):
    def _write(self, d, name, text):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def _run(self, src_text, doc_text):
        with tempfile.TemporaryDirectory() as d:
            src = self._write(d, "spec.txt", src_text)
            doc = self._write(d, "plan.md", doc_text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run("clauses", ["--src", src, "--doc", doc])
            return code, buf.getvalue()

    def test_missing_clause_exits_1_and_names_it(self):
        code, out = self._run(NOTICE, PLAN_MISSING)
        self.assertEqual(code, 1)
        self.assertIn("打分项顺序", out)
        self.assertIn("请人确认", out)

    def test_full_restatement_exits_0(self):
        code, out = self._run(NOTICE, PLAN_OK)
        self.assertEqual(code, 0)
        self.assertIn("clean", out)

    def test_nothing_to_split_is_not_a_pass(self):
        code, out = self._run("没有任何编号的文字，只是一段话。\n", PLAN_OK)
        self.assertEqual(code, 2)
        self.assertIn("不是通过", out)

    def test_missing_doc_is_an_error_not_clean(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._write(d, "spec.txt", NOTICE)
            with self.assertRaises(FileNotFoundError):
                run("clauses", ["--src", src, "--doc", os.path.join(d, "nope.md")])


class TestSourcesPack(unittest.TestCase):
    def test_pack_is_listed_and_expands(self):
        from evidgate.core.packs import available, load_packs

        self.assertIn("sources", available())
        checks = load_packs(["sources:src=spec.txt,doc=plan.md"])
        self.assertEqual([c.cid for c in checks], ["S1"])
        self.assertEqual(checks[0].severity, "yellow")
        self.assertIn("--src spec.txt", checks[0].method)
        self.assertTrue(checks[0].counter.strip())


class TestEdgeCases(unittest.TestCase):
    def test_page_markers_are_stripped(self):
        from evidgate.plugins.coverage import _strip_page_numbers

        self.assertEqual(_strip_page_numbers("字幕。一— 5 —经发现"), "字幕。一经发现")
        self.assertEqual(_strip_page_numbers("正文 - 12 - 继续"), "正文继续")

    def test_same_file_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "spec.txt")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(NOTICE)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run("clauses", ["--src", p, "--doc", p])
            self.assertEqual(code, 2)
            self.assertIn("同一个文件", buf.getvalue())

    def test_skipped_headings_are_reported(self):
        code, out = TestRuleExitCodes()._run(NOTICE, PLAN_MISSING)
        self.assertEqual(code, 1)
        self.assertIn("按章节标题跳过", out)


class TestSuggestRecommendsWiredPack(unittest.TestCase):
    def _mk(self, d, files):
        for name, body in files.items():
            with open(os.path.join(d, name), "wb") as fh:
                fh.write(body.encode("utf-8"))

    def test_recommendation_carries_both_paths(self):
        from evidgate.core.suggest import probe, render

        with tempfile.TemporaryDirectory() as d:
            self._mk(d, {"spec.pdf": "%PDF-1.4\n", "plan.md": "# plan\n"})
            self.assertIn("sources:src=spec.pdf,doc=plan.md", render(probe(d)))

    def test_a_pdf_named_spec_is_not_a_test_file(self):
        from evidgate.core.suggest import probe, render

        with tempfile.TemporaryDirectory() as d:
            self._mk(d, {"spec.pdf": "%PDF-1.4\n", "plan.md": "# plan\n"})
            self.assertNotIn("repo", render(probe(d)))


if __name__ == "__main__":
    unittest.main()
