# -*- coding: utf-8 -*-
"""Deterministic check behaviour — these are the gate, so they get the most tests."""
import unittest

from skilleval.checks import extract_json, run_checks, summarize


class TestExtractJson(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(extract_json('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        self.assertEqual(extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_wrapped(self):
        self.assertEqual(extract_json('好的，结果如下：{"a": 1} 以上。'), {"a": 1})

    def test_broken(self):
        self.assertIsNone(extract_json("{not json"))
        self.assertIsNone(extract_json(""))


class TestCheckTypes(unittest.TestCase):
    def test_must_include(self):
        r = run_checks([{"id": "x", "type": "must_include", "all": ["a", "b"]}], "a and b")[0]
        self.assertTrue(r.passed)
        r = run_checks([{"id": "x", "type": "must_include", "all": ["a", "z"]}], "a and b")[0]
        self.assertFalse(r.passed)
        self.assertIn("z", r.detail)

    def test_must_not_include(self):
        r = run_checks([{"id": "x", "type": "must_not_include", "any": ["TODO"]}], "done")[0]
        self.assertTrue(r.passed)
        r = run_checks([{"id": "x", "type": "must_not_include", "any": ["TODO"]}], "TODO: fix")[0]
        self.assertFalse(r.passed)

    def test_regex_all_counts_unique(self):
        spec = [{"id": "c", "type": "regex_all", "pattern": r"\[S\d+\]", "min_matches": 3}]
        self.assertFalse(run_checks(spec, "[S1] [S1] [S2]")[0].passed)
        self.assertTrue(run_checks(spec, "[S1] [S2] [S3]")[0].passed)

    def test_json_path(self):
        spec = [{"id": "p", "type": "json_path", "paths": ["summary", "next_actions.0.action"]}]
        good = '{"summary": "s", "next_actions": [{"action": "do it"}]}'
        bad = '{"summary": "s", "next_actions": []}'
        self.assertTrue(run_checks(spec, good)[0].passed)
        self.assertFalse(run_checks(spec, bad)[0].passed)

    def test_length_limits(self):
        self.assertFalse(run_checks([{"id": "l", "type": "max_chars", "value": 5}], "123456")[0].passed)
        self.assertTrue(run_checks([{"id": "l", "type": "min_chars", "value": 3}], "123456")[0].passed)

    def test_language(self):
        self.assertTrue(run_checks([{"id": "z", "type": "language", "value": "zh"}], "中文摘要内容")[0].passed)
        self.assertFalse(run_checks([{"id": "z", "type": "language", "value": "zh"}], "english only text")[0].passed)

    def test_regex_none(self):
        spec = [{"id": "n", "type": "regex_none", "pattern": r"截止.{0,6}3\s*月\s*14\s*日"}]
        self.assertFalse(run_checks(spec, "整改截止 3 月 14 日")[0].passed)
        self.assertTrue(run_checks(spec, "截止日期待确认")[0].passed)

    def test_unknown_type_fails_loudly(self):
        r = run_checks([{"id": "u", "type": "nope"}], "text")[0]
        self.assertFalse(r.passed)
        self.assertIn("unknown check type", r.detail)

    def test_bad_spec_does_not_raise(self):
        r = run_checks([{"id": "b", "type": "max_chars", "value": "abc"}], "text")[0]
        self.assertFalse(r.passed)
        self.assertIn("check raised", r.detail)

    def test_summarize(self):
        results = run_checks([{"id": "a", "type": "must_include", "all": ["x"]},
                              {"id": "b", "type": "must_include", "all": ["zz"]}], "x here")
        s = summarize(results)
        self.assertEqual((s["total"], s["passed"]), (2, 1))
        self.assertAlmostEqual(s["pass_rate"], 0.5)
        self.assertEqual(s["failed_ids"], ["b"])


if __name__ == "__main__":
    unittest.main()
