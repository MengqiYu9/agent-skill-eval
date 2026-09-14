# -*- coding: utf-8 -*-
"""End-to-end: load the bundled suite, run both skill versions through the mock runner,
and check that the regression gate actually fires when a version gets worse."""
import json
import os
import unittest

from skilleval.config import RunOptions
from skilleval.report import baseline_from, compare_to_baseline, render_markdown
from skilleval.runner import make_runner
from skilleval.suite import load_skill, load_tasks, run_skill

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "tasks")
FIXTURES = os.path.join(ROOT, "examples", "mock_outputs.json")


class TestSuiteEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tasks = load_tasks(TASKS)
        self.options = RunOptions(runner="mock", mock_outputs=FIXTURES, judge=False, quiet=True)
        self.runner = make_runner(self.options, None)

    def test_tasks_load(self):
        self.assertEqual(len(self.tasks), 4)
        self.assertTrue(all(t.checks for t in self.tasks))

    def test_v2_beats_v1_on_deterministic_checks(self):
        v1 = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v1")),
                       self.tasks, self.runner, self.options, logger=lambda *a: None)
        v2 = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v2")),
                       self.tasks, self.runner, self.options, logger=lambda *a: None)
        a1, a2 = v1.aggregate(), v2.aggregate()
        # v1 (loose prose) passes the "soft" checks (length, language, no placeholders) but
        # fails every contract/grounding check; v2 must pass all of them.
        self.assertLess(a1["checks"]["pass_rate"], a2["checks"]["pass_rate"])
        self.assertEqual(a2["checks"]["pass_rate"], 1.0)
        self.assertIn("json_valid", a1["per_check"])
        self.assertEqual(a1["per_check"]["json_valid"]["passed"], 0)
        self.assertEqual(v2.skill_id, "structured-digest/v2")

    def test_baseline_detects_regression(self):
        """Same skill id, output quality drops -> the gate must fire."""
        healthy = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v2")),
                            self.tasks, self.runner, self.options, logger=lambda *a: None)
        baseline = baseline_from([healthy])
        self.assertEqual(baseline[healthy.skill_id]["check_pass_rate"], 1.0)

        # the same skill, after an edit that dropped the output contract
        degraded = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v1")),
                             self.tasks, self.runner, self.options, logger=lambda *a: None)
        degraded.skill_id = healthy.skill_id

        comparison = compare_to_baseline([degraded], baseline, max_regression=0.0)
        entry = comparison[healthy.skill_id]
        self.assertTrue(entry["baseline_found"])
        self.assertTrue(entry["regression"])
        self.assertLess(entry["check_pass_rate_delta"], 0)
        self.assertIn("json_valid", " ".join(entry["check_regressions"]))

        # no regression when the run matches its own baseline
        self.assertFalse(compare_to_baseline([healthy], baseline, 0.0)[healthy.skill_id]["regression"])

    def test_report_renders_both_arms(self):
        v1 = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v1")),
                       self.tasks, self.runner, self.options, logger=lambda *a: None)
        v2 = run_skill(load_skill(os.path.join(ROOT, "skills", "structured-digest", "v2")),
                       self.tasks, self.runner, self.options, logger=lambda *a: None)
        md = render_markdown([v1, v2], self.options)
        for needle in ("# agent-skill-eval report", "A/B delta", "Per-check outcome",
                       "structured-digest/v1", "structured-digest/v2", "Failure evidence"):
            self.assertIn(needle, md)

    def test_mock_runner_reports_missing_fixture(self):
        options = RunOptions(runner="mock", mock_outputs=None, judge=False)
        runner = make_runner(options, None)
        outcome = runner.complete("s", "u")
        self.assertIsNotNone(outcome.error)
        self.assertIn("no fixture", outcome.error)


if __name__ == "__main__":
    unittest.main()
