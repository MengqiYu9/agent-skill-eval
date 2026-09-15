# -*- coding: utf-8 -*-
"""CLI: run an eval suite over one or more skill versions and gate on regressions.

    skilleval run --suite tasks/ --skill skills/digest/v1 --skill skills/digest/v2
    skilleval run --suite tasks/ --skill skills/digest/v2 --baseline baseline.json

Exit codes: 0 = pass, 1 = regression / below floor, 2 = pipeline error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import math
from pathlib import Path
from .gate import decide_verdict, complete

from .config import DEFAULT_BASE_URL, DEFAULT_MODEL, Prices, RunOptions, resolve_api_key
from .report import (VERDICT_ERROR, VERDICT_PASS, VERDICT_REGRESSION, baseline_from,
                     compare_to_baseline, render_markdown, write_outputs)
from .runner import RunnerError, make_runner
from .suite import SuiteError, load_skill, load_tasks, run_skill


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--suite", required=True, help="task file or directory of .yaml/.json task sets")
    p.add_argument("--skill", action="append", default=[], required=True,
                   help="skill dir (containing SKILL.md) or a prompt .md file; repeat for A/B")
    p.add_argument("--runner", choices=["llm", "mock", "codex", "claude", "gemini", "cursor"], default="llm")
    p.add_argument("--mock-outputs", help="fixture JSON for --runner mock, keys: '<skill>::<task>'")
    p.add_argument("--model", default=os.environ.get("SKILLEVAL_MODEL"))
    p.add_argument("--judge-model", default=None, help="defaults to --model")
    p.add_argument("--base-url", default=os.environ.get("SKILLEVAL_BASE_URL", DEFAULT_BASE_URL))
    p.add_argument("--api-key", default=None, help="prefer env var / --env-file over argv")
    p.add_argument("--env-file", default=None, help="e.g. %%LOCALAPPDATA%%/hermes/.env")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-tokens", type=int, default=4096,
                   help="must cover reasoning tokens as well as the answer; truncation is reported")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--no-judge", action="store_true", help="deterministic checks only")
    p.add_argument("--prices", default=None, help="prices JSON (per-1M tokens) to enable cost column")
    p.add_argument("--out", default="reports")
    p.add_argument("--baseline", default=None, help="baseline JSON to compare against")
    p.add_argument("--save-baseline", default=None, help="write this run as the new baseline")
    p.add_argument("--max-regression", type=float, default=0.0,
                   help="allowed pass-rate drop vs baseline before failing (0.0 = any drop fails)")
    p.add_argument("--fail-under", type=float, default=None, help="absolute floor for check pass rate")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--baseline-skill", help="explicit baseline entry to compare the candidate to")
    p.add_argument("--allow-legacy-baseline", action="store_true")
    p.add_argument("--compare-first", action="store_true", help="gate later arms against the first arm")
    p.add_argument("--no-skill", action="store_true", help="prepend an unskilled control arm")
    p.add_argument("--judge-fail-under", type=float)
    p.add_argument("--max-cost", type=float, help="maximum total USD per arm, including judging")
    p.add_argument("--max-latency", type=float, help="maximum total seconds per arm, including judging")
    p.add_argument("--agent-command", help="native CLI executable path")
    p.add_argument("--agent-arg", action="append", default=[], help="extra native CLI argument (use --agent-arg=VALUE)")
    p.add_argument("--invocation", choices=["explicit", "implicit"], default="explicit")


def cmd_run(args):
    native = args.runner not in ("llm", "mock")
    model = args.model or ("" if native else DEFAULT_MODEL)
    options = RunOptions(
        base_url=args.base_url or DEFAULT_BASE_URL, model=model, temperature=args.temperature,
        max_tokens=args.max_tokens, timeout=args.timeout, runner=args.runner,
        judge=not args.no_judge, judge_model=args.judge_model,
        mock_outputs=args.mock_outputs, api_key=args.api_key, env_file=args.env_file,
        prices_file=args.prices, out_dir=args.out, baseline=args.baseline,
        save_baseline=args.save_baseline, max_regression=args.max_regression,
        fail_under=args.fail_under, quiet=args.quiet, repeats=args.repeats,
        baseline_skill=args.baseline_skill, allow_legacy_baseline=args.allow_legacy_baseline,
        compare_first=args.compare_first, no_skill=args.no_skill,
        judge_fail_under=args.judge_fail_under, max_cost=args.max_cost, max_latency=args.max_latency,
        agent_command=args.agent_command, agent_args=args.agent_arg, invocation=args.invocation,
    )
    log = (lambda *a: None) if args.quiet else print
    for name, value, low, high in (
        ("max-regression", args.max_regression, 0, 1), ("fail-under", args.fail_under, 0, 1),
        ("temperature", args.temperature, 0, 2), ("judge-fail-under", args.judge_fail_under, 0, 5),
        ("max-cost", args.max_cost, 0, float("inf")), ("max-latency", args.max_latency, 0, float("inf"))):
        if value is not None and (not math.isfinite(value) or not low <= value <= high):
            raise SuiteError("invalid --" + name)
    if args.repeats < 1 or args.max_tokens < 1 or args.timeout < 1:
        raise SuiteError("repeats, max-tokens and timeout must be positive")
    if args.compare_first and args.baseline:
        raise SuiteError("--compare-first and --baseline are mutually exclusive")
    if args.baseline_skill and (not args.baseline or len(args.skill) != 1 or args.no_skill):
        raise SuiteError("--baseline-skill requires one candidate and --baseline")
    if args.save_baseline and Path(args.save_baseline).exists():
        raise SuiteError("--save-baseline cannot overwrite; use accept-baseline --replace after reviewing a report")
    tasks = load_tasks(args.suite)
    skills = [load_skill(p) for p in args.skill]
    if args.no_skill:
        skills.insert(0, load_skill("__no_skill__"))
    if len({s.id for s in skills}) != len(skills):
        raise SuiteError("duplicate skill ids; pass distinct skill version directories")
    if args.compare_first and len(skills) < 2:
        raise SuiteError("--compare-first requires at least two arms")
    if not native and any(t.files or any("artifact" in c for c in t.checks) for t in tasks):
        raise SuiteError("file fixtures/artifact checks require a native runner")
    if args.runner == "mock" and options.judge:
        raise SuiteError("mock requires --no-judge; recorded worker outputs cannot judge themselves")
    if native and options.judge and not args.judge_model:
        raise SuiteError("native judging requires --judge-model for the separate API judge, or --no-judge")
    if args.judge_fail_under is not None and (not options.judge or any(not t.rubric for t in tasks)):
        raise SuiteError("--judge-fail-under requires judging and a rubric on every task")
    baseline = None
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8-sig"))
        if not isinstance(baseline, dict):
            raise SuiteError("baseline must be an object")
        if "__schema_version__" not in baseline and not args.allow_legacy_baseline:
            raise SuiteError("legacy baseline: use --allow-legacy-baseline explicitly or migrate")
        if any((args.baseline_skill or s.id) not in baseline for s in skills):
            raise SuiteError("baseline entry missing for a candidate")
    key, source = (None, None)
    if args.runner == "llm" or options.judge:
        key, source = resolve_api_key(args.api_key, args.env_file)
        if not key:
            raise SuiteError("no API key configured")
    prices = Prices.load(args.prices, model)
    judge_prices = Prices.load(args.prices, args.judge_model or model)
    runner = make_runner(options, key)
    judge_runner = None
    if native and options.judge:
        from .runner import LLMRunner
        judge_runner = LLMRunner(options.base_url, key, args.judge_model, 0, args.max_tokens, args.timeout)
    log("runner=%s model=%s" % (args.runner, model or "platform default"))
    results = []
    for skill in skills:
        result = run_skill(skill, tasks, runner, options, logger=log, judge_runner=judge_runner)
        result.prices, result.judge_prices = prices, judge_prices
        results.append(result)
    comparison = None
    if baseline:
        comparison = compare_to_baseline(results, baseline, args.max_regression,
                                         args.baseline_skill, args.allow_legacy_baseline)
    elif args.compare_first and complete(results[0]):
        comparison = compare_to_baseline(results[1:], baseline_from(results[:1]),
                                         args.max_regression, results[0].skill_id)
    verdict = decide_verdict(results, options, comparison)
    markdown = render_markdown(results, options, comparison=comparison, verdict=verdict)
    md_path, json_path = write_outputs(results, options, args.out, markdown,
                                       comparison=comparison, verdict=verdict)
    if args.save_baseline:
        if verdict == VERDICT_PASS:
            with open(args.save_baseline, "x", encoding="utf-8") as fh:
                json.dump(baseline_from(results), fh, ensure_ascii=False, indent=2)
        else:
            log("baseline was not saved: verdict is " + verdict)
    log("report: %s\n%s\nverdict: %s" % (md_path, json_path, verdict))
    return {VERDICT_PASS: 0, VERDICT_REGRESSION: 1, VERDICT_ERROR: 2}[verdict]


def cmd_accept_baseline(args):
    report = json.loads(Path(args.report).read_text(encoding="utf-8-sig"))
    candidate = report.get("baseline_candidate")
    if report.get("schema_version") != 2 or report.get("verdict") != VERDICT_PASS or not isinstance(candidate, dict) or candidate.get("__schema_version__") != 2:
        raise SuiteError("only a complete v2 PASS report can be accepted")
    if Path(args.out).exists() and not args.replace:
        raise SuiteError("baseline exists; review the report then use --replace explicitly")
    # Keep the old baseline intact if serialization or writing fails.
    import tempfile
    destination = Path(args.out).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as fh:
        temporary = Path(fh.name)
        json.dump(candidate, fh, ensure_ascii=False, indent=2)
    try:
        if args.replace:
            os.replace(temporary, destination)
        else:
            # Exclusive creation refuses a competing writer.
            with destination.open("x", encoding="utf-8") as fh:
                fh.write(temporary.read_text(encoding="utf-8"))
    finally:
        temporary.unlink(missing_ok=True)
    print("accepted baseline: %s" % destination)
    return 0


def cmd_validate(args) -> int:
    """Load everything without calling a model — catches broken YAML/skills before spending."""
    try:
        tasks = load_tasks(args.suite)
        skills = [load_skill(p) for p in args.skill]
    except SuiteError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print("suite : %s" % os.path.abspath(args.suite))
    print("tasks : %d -> %s" % (len(tasks), ", ".join(t.id for t in tasks)))
    check_ids = sorted({c.get("id", "?") for t in tasks for c in t.checks})
    print("checks: %d unique -> %s" % (len(check_ids), ", ".join(check_ids)))
    for s in skills:
        print("skill : %-24s %d chars  %s" % (s.id, len(s.instructions), s.path))
    return 0


def cmd_init(args) -> int:
    """Scaffold a new skill version + task template so a suite can grow."""
    root = os.path.abspath(args.path)
    skill_dir = os.path.join(root, "skills", args.name, args.version)
    task_dir = os.path.join(root, "tasks")
    os.makedirs(skill_dir, exist_ok=True)
    os.makedirs(task_dir, exist_ok=True)
    skill_file = os.path.join(skill_dir, "SKILL.md")
    task_file = os.path.join(task_dir, "%s-01.yaml" % args.name)
    if not os.path.exists(skill_file):
        with open(skill_file, "w", encoding="utf-8") as fh:
            fh.write("---\nname: %s\ndescription: TODO one-line trigger\n---\n\n"
                     "# %s\n\nDescribe the behaviour, the output contract, and what must never happen.\n"
                     % (args.name, args.name))
    if not os.path.exists(task_file):
        with open(task_file, "w", encoding="utf-8") as fh:
            fh.write(
                "tasks:\n"
                "  - id: %s-01\n"
                "    notes: what this case is protecting against\n"
                "    input: |\n"
                "      在这里放输入材料（用合成数据，别放真实客户/内部资料）。\n"
                "    checks:\n"
                "      - id: json_valid\n"
                "        type: json_valid\n"
                "      - id: no_placeholders\n"
                "        type: must_not_include\n"
                "        any: [\"TODO\", \"待补充\", \"XXX\"]\n"
                "      - id: length_cap\n"
                "        type: max_chars\n"
                "        value: 1200\n"
                "    rubric:\n"
                "      - id: grounding\n"
                "        desc: 每个结论都能回溯到输入材料，不引入外部事实\n"
                % args.name)
    print("scaffolded:\n  %s\n  %s" % (skill_file, task_file))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skilleval",
                                     description="Regression gate for agent skills / prompt versions")
    from . import __version__
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run a suite over one or more skill versions")
    _add_run_args(p_run)
    p_run.set_defaults(func=cmd_run)

    p_val = sub.add_parser("validate", help="dry-run: load suite + skills, no model calls")
    p_val.add_argument("--suite", required=True)
    p_val.add_argument("--skill", action="append", default=[], required=True)
    p_val.set_defaults(func=cmd_validate)

    p_init = sub.add_parser("init", help="scaffold a new skill version + task template")
    p_init.add_argument("--path", default=".")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--version", default="v1")
    p_init.set_defaults(func=cmd_init)
    p_accept = sub.add_parser("accept-baseline", help="promote a reviewed PASS report")
    p_accept.add_argument("--report", required=True)
    p_accept.add_argument("--out", required=True)
    p_accept.add_argument("--replace", action="store_true")
    p_accept.set_defaults(func=cmd_accept_baseline)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (SuiteError, RunnerError, OSError, ValueError, TypeError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
