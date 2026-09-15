# -*- coding: utf-8 -*-
"""Judge parsing/robustness, without touching a network."""
import unittest

from skilleval.judge import judge_output
from skilleval.runner import Completion

RUBRIC = [{"id": "grounding", "desc": "no invented facts"},
          {"id": "actionability", "desc": "actions are specific"}]


class FakeRunner:
    kind = "llm"
    model = "fake"

    def __init__(self, reply):
        self.reply = reply
        self.seen = None

    def complete(self, system, user):
        self.seen = (system, user)
        return Completion(self.reply, 0.01, 10, 5, "fake")


class TestJudge(unittest.TestCase):
    def test_parses_scores(self):
        r = judge_output(FakeRunner('{"scores": {"grounding": 5, "actionability": 3}, "notes": "ok"}'),
                         RUBRIC, "input", "output")
        self.assertEqual(r.scores, {"grounding": 5, "actionability": 3})
        self.assertAlmostEqual(r.mean, 4.0)
        self.assertIsNone(r.error)

    def test_rejects_out_of_range(self):
        r = judge_output(FakeRunner('{"scores": {"grounding": 99, "actionability": -4}}'),
                         RUBRIC, "input", "output")
        self.assertIsNotNone(r.error)
        self.assertEqual(r.mean, 0.0)

    def test_records_missing_criteria_as_none(self):
        r = judge_output(FakeRunner('{"scores": {"grounding": 4}}'), RUBRIC, "i", "o")
        self.assertIsNone(r.scores["actionability"])
        self.assertIsNotNone(r.error)
        self.assertEqual(r.mean, 0.0)

    def test_non_json_reply_is_an_error_not_a_crash(self):
        r = judge_output(FakeRunner("I think it is quite good."), RUBRIC, "i", "o")
        self.assertIsNotNone(r.error)
        self.assertEqual(r.mean, 0.0)

    def test_runner_error_propagates(self):
        class Broken(FakeRunner):
            def complete(self, system, user):
                return Completion("", 0.0, error="HTTP 401")

        r = judge_output(Broken(""), RUBRIC, "i", "o")
        self.assertEqual(r.error, "HTTP 401")

    def test_rubric_is_passed_to_the_judge_prompt(self):
        runner = FakeRunner('{"scores": {"grounding": 5, "actionability": 5}}')
        judge_output(runner, RUBRIC, "THE INPUT", "THE OUTPUT")
        system, user = runner.seen
        self.assertIn("grounding", user)
        self.assertIn("THE INPUT", user)
        self.assertIn("THE OUTPUT", user)
        self.assertIn("JSON", system)


class TestRunnerDiagnostics(unittest.TestCase):
    def test_truncation_is_explained(self):
        from skilleval.runner import Completion, empty_content_error
        msg = empty_content_error("length", 2048, 2048)
        self.assertIn("--max-tokens", msg)
        self.assertIn("reasoning", msg)
        self.assertTrue(Completion("", 0.0, finish_reason="length").truncated)
        self.assertFalse(Completion("ok", 0.0, finish_reason="stop").truncated)

    def test_empty_content_without_truncation_still_reports_a_cause(self):
        from skilleval.runner import empty_content_error
        self.assertIn("finish_reason=stop", empty_content_error("stop", 0, 4096))


if __name__ == "__main__":
    unittest.main()
