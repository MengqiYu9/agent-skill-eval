"""Regression tests for release gates and native process contracts; no model calls."""
import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skilleval.checks import run_checks, strict_json
from skilleval.cli import main
from skilleval.config import Prices, RunOptions
from skilleval.gate import baseline_from, compare_to_baseline, decide_verdict
from skilleval.judge import judge_output
from skilleval.native import NativeRunner, parse_native
from skilleval.report import render_markdown, write_outputs
from skilleval.runner import Completion
from skilleval.suite import Skill, Task, SuiteError, load_tasks, run_skill


class Worker:
    kind = "llm"
    model = "fake"
    def __init__(self, text="ok", error=None, finish="stop"):
        self.text, self.error, self.finish = text, error, finish
        self.calls = 0
    def complete(self, system, user):
        self.calls += 1
        self.seen = user
        return Completion(self.text, .1, 10, 20, "fake", self.error, self.finish)


def result(text="ok", **kwargs):
    options = RunOptions(judge=False, model="fake", **kwargs)
    tasks = [Task("a", "input", [{"id": "contains", "type": "must_include", "all": ["ok"]}])]
    return run_skill(Skill("skill/v1", "", "instructions"), tasks, Worker(text), options, lambda *a: None)


class Gates(unittest.TestCase):
    def test_missing_baseline_is_error(self):
        r = result()
        c = compare_to_baseline([r], {"__schema_version__": 2}, 0)
        self.assertEqual(decide_verdict([r], RunOptions(judge=False), c), "ERROR")

    def test_explicit_cross_version_mapping(self):
        good = result()
        base = baseline_from([good])
        candidate = result("bad")
        candidate.skill_id = "skill/v2"
        c = compare_to_baseline([candidate], base, 0, "skill/v1")
        self.assertTrue(c["skill/v2"]["regression"])

    def test_suite_change_is_incomparable(self):
        r = result()
        base = baseline_from([r])
        r.provenance["suite_sha256"] = "changed"
        self.assertIsNotNone(compare_to_baseline([r], base, 0)[r.skill_id]["error"])

    def test_config_change_is_incomparable(self):
        base = baseline_from([result()])
        r = result(repeats=2)
        self.assertIsNotNone(compare_to_baseline([r], base, 0)[r.skill_id]["error"])

    def test_deleted_task_check_detected(self):
        r = result()
        base = baseline_from([r])
        base[r.skill_id]["per_task_check"]["deleted::check"] = 1
        self.assertIsNotNone(compare_to_baseline([r], base, 0)[r.skill_id]["error"])

    def test_legacy_requires_opt_in(self):
        r = result()
        base = baseline_from([r])
        del base["__schema_version__"]
        self.assertIsNotNone(compare_to_baseline([r], base, 0)[r.skill_id]["error"])
        self.assertIsNone(compare_to_baseline([r], base, 0, allow_legacy=True)[r.skill_id]["error"])

    def test_tolerance_applies_to_individual_checks(self):
        r = result()
        base = baseline_from([r])
        r.outcomes[0].checks[0].passed = False
        r.outcomes[0].check_summary.update(passed=0, pass_rate=0)
        self.assertFalse(compare_to_baseline([r], base, 1)[r.skill_id]["regression"])
        self.assertTrue(compare_to_baseline([r], base, .9)[r.skill_id]["regression"])

    def test_partial_error_overrides_threshold(self):
        r = result()
        broken = copy.deepcopy(r.outcomes[0])
        broken.error = "timeout"
        r.outcomes.append(broken)
        self.assertEqual(decide_verdict([r], RunOptions(fail_under=0)), "ERROR")

    def test_truncation_excluded_and_blocks_baseline(self):
        r = result()
        r.outcomes[0].truncated = True
        self.assertEqual(r.aggregate()["scored_tasks"], 0)
        self.assertEqual(decide_verdict([r], RunOptions()), "ERROR")
        with self.assertRaises(ValueError):
            baseline_from([r])

    def test_default_gate_rejects_bad_answers(self):
        self.assertEqual(decide_verdict([result("wrong")], RunOptions()), "REGRESSION")

    def test_judge_error_blocks_pass(self):
        from skilleval.judge import JudgeResult
        r = result()
        r.outcomes[0].judge = JudgeResult(error="missing criterion")
        self.assertEqual(decide_verdict([r], RunOptions()), "ERROR")

    def test_judge_regression_is_detected(self):
        from skilleval.judge import JudgeResult
        r = result()
        r.outcomes[0].judge = JudgeResult(scores={"grounded": 5}, mean=5)
        base = baseline_from([r])
        r.outcomes[0].judge = JudgeResult(scores={"grounded": 1}, mean=1)
        self.assertTrue(compare_to_baseline([r], base, 0)[r.skill_id]["regression"])

    def test_repeats_execute_and_aggregate(self):
        self.assertEqual(len(result(repeats=3).outcomes), 3)
        self.assertEqual(result(repeats=3).aggregate()["unique_tasks"], 1)

    def test_judge_cost_in_report(self):
        from skilleval.judge import JudgeResult
        r = result()
        r.outcomes[0].judge = JudgeResult(scores={"x": 5}, mean=5, prompt_tokens=100, completion_tokens=200)
        r.prices = Prices(1, 2)
        r.judge_prices = Prices(3, 4)
        self.assertAlmostEqual(r.aggregate()["cost_usd"], .00115)
        self.assertIn("$0.0011", render_markdown([r], RunOptions()))

    def test_unknown_native_cost_is_not_zero(self):
        r = result()
        r.prices = Prices(1, 2)
        r.outcomes[0].metadata["cost_supported"] = False
        self.assertIsNone(r.aggregate()["cost_usd"])
        self.assertEqual(decide_verdict([r], RunOptions(max_cost=1)), "ERROR")


class StrictChecks(unittest.TestCase):
    def test_wrapped_json_fails_strict(self):
        self.assertFalse(run_checks([{"id": "x", "type": "json_strict"}], 'text {"a":1}')[0].passed)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                strict_json(text)

    def test_schema_checks_all_array_items(self):
        schema = {"type": "array", "items": {"type": "object", "required": ["citation"]}}
        check = {"id": "x", "type": "json_schema", "schema": schema}
        self.assertFalse(run_checks([check], '[{"citation":"1"},{}]')[0].passed)

    def test_schema_never_fetches_remote_refs(self):
        check = {"id": "x", "type": "json_schema", "schema": {"$ref": "https://example.com/schema"}}
        self.assertFalse(run_checks([check], "{}")[0].passed)

    def test_validate_rejects_bad_definitions(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tasks.json"
            base = {"id": "x", "input": "input", "checks": [{"id": "c", "type": "json_strict"}]}
            for tasks in ([base, base], [dict(base, checks=[])],
                          [dict(base, checks=[{"id": "c", "type": "regex_all", "pattern": "["}])],
                          [dict(base, files={"../outside": "x"})]):
                p.write_text(json.dumps(tasks))
                with self.subTest(tasks=tasks), self.assertRaises(SuiteError):
                    load_tasks(p)

    def test_judge_invalid_types_fail(self):
        for value in (True, "5", 4.5, None):
            r = judge_output(Worker(json.dumps({"scores": {"a": value}})), [{"id": "a"}], "i", "o")
            self.assertIsNotNone(r.error)

    def test_judge_sees_full_evidence(self):
        worker = Worker('{"scores":{"a":5}}')
        judge_output(worker, [{"id": "a"}], "i" * 9000 + "INPUT_END", "o" * 9000 + "OUTPUT_END")
        self.assertIn("INPUT_END", worker.seen)
        self.assertIn("OUTPUT_END", worker.seen)

    def test_judge_model_does_not_mutate_worker(self):
        worker = Worker('{"scores":{"a":5}}')
        judge_output(worker, [{"id": "a"}], "i", "o", model="judge")
        self.assertEqual(worker.model, "fake")


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "skill.md").write_text("answer correctly")
        self.tasks = [{"id": "a", "input": "input", "checks": [{"id": "c", "type": "must_include", "all": ["ok"]}]}]
        self.write("tasks.json", self.tasks)
        self.write("fixtures.json", {"a": "ok"})

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data))

    def run_cli(self, *extra):
        args = ["run", "--suite", str(self.root / "tasks.json"), "--skill", str(self.root / "skill.md"),
                "--runner", "mock", "--mock-outputs", str(self.root / "fixtures.json"),
                "--no-judge", "--out", str(self.root / "reports"), "--quiet", *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(args)

    def test_partial_missing_fixture_nonzero(self):
        self.tasks.append(dict(self.tasks[0], id="b"))
        self.write("tasks.json", self.tasks)
        self.assertEqual(self.run_cli(), 2)

    def test_bad_run_cannot_save_baseline(self):
        self.write("fixtures.json", {"a": "wrong"})
        destination = self.root / "baseline.json"
        self.assertEqual(self.run_cli("--save-baseline", str(destination)), 1)
        self.assertFalse(destination.exists())

    def test_save_never_overwrites(self):
        destination = self.root / "baseline.json"
        destination.write_text("original")
        self.assertEqual(self.run_cli("--save-baseline", str(destination)), 2)
        self.assertEqual(destination.read_text(), "original")

    def test_negative_and_nan_arguments(self):
        for flag, value in (("--repeats", "0"), ("--max-regression", "nan"), ("--fail-under", "2")):
            self.assertEqual(self.run_cli(flag, value), 2)

    def test_accept_report_and_protect_existing_baseline(self):
        self.assertEqual(self.run_cli(), 0)
        report = next((self.root / "reports").glob("*.json"))
        args = ["accept-baseline", "--report", str(report), "--out", str(self.root / "base.json")]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 2)

    def test_report_names_do_not_collide(self):
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(len(list((self.root / "reports").glob("*.json"))), 2)


class NativeContracts(unittest.TestCase):
    def test_codex_requires_terminal(self):
        event = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}})
        self.assertIsNotNone(parse_native("codex", event, 1).error)
        done = json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}})
        r = parse_native("codex", event + "\n" + done, 1)
        self.assertIsNone(r.error)
        self.assertEqual(r.text, "ok")

    def test_claude_cursor_result_envelope(self):
        for platform in ("claude", "cursor"):
            r = parse_native(platform, '{"type":"result","subtype":"success","result":"ok"}', 1)
            self.assertIsNone(r.error)
            self.assertEqual(r.text, "ok")
            bad = parse_native(platform, '{"type":"result","subtype":"error_max_turns","is_error":true}', 1)
            self.assertIsNotNone(bad.error)

    def test_gemini_pretty_json_and_error(self):
        r = parse_native("gemini", '{\n"response": "ok"\n}', 1)
        self.assertEqual(r.text, "ok")
        self.assertIsNotNone(parse_native("gemini", '{"error":{"message":"denied"}}', 1).error)

    def test_malformed_output(self):
        for platform in ("codex", "claude", "gemini", "cursor"):
            self.assertIsNotNone(parse_native(platform, "not json", 1).error)

    def test_actual_child_process_artifact_and_skill_installation(self):
        options = RunOptions(runner="codex", model="", judge=False, agent_command=sys.executable)
        runner = NativeRunner(options)
        with tempfile.TemporaryDirectory() as d:
            skill_file = Path(d) / "SKILL.md"
            skill_file.write_text("instructions")
            skill = Skill("example/v1", str(skill_file), "instructions", name="example")
            task = Task("a", "write result", [{"id": "out", "type": "json_strict", "artifact": "result.json"}])
            script = ('from pathlib import Path; import json; '
                      'assert Path(".agents/skills/example/SKILL.md").read_text()=="instructions"; '
                      'Path("result.json").write_text("{}"); '
                      'print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"done"}})); '
                      'print(json.dumps({"type":"turn.completed","usage":{}}))')
            with patch.object(runner, "command", return_value=[sys.executable, "-c", script]):
                output = runner.execute(skill, task)
            self.assertIsNone(output.error)
            self.assertEqual(output.artifacts, {"result.json": "{}"})

    def test_native_timeout(self):
        runner = NativeRunner(RunOptions(runner="codex", agent_command=sys.executable, timeout=1))
        with patch.object(runner, "command", return_value=[sys.executable, "-c", "import time; time.sleep(10)"]):
            output = runner.execute(Skill("no-skill", "", ""), Task("a", "input"))
        self.assertIn("timed out", output.error)


if __name__ == "__main__":
    unittest.main()

