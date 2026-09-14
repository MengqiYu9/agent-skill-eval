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

from .config import DEFAULT_BASE_URL, DEFAULT_MODEL, Prices, RunOptions, resolve_api_key
from .report import (VERDICT_ERROR, VERDICT_PASS, VERDICT_REGRESSION, baseline_from,
                     compare_to_baseline, render_markdown, write_outputs)
from .runner import RunnerError, make_runner
from .suite import SuiteError, load_skill, load_tasks, run_skill


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--suite", required=True, help="task file or directory of .yaml/.json task sets")
    p.add_argument("--skill", action="append", default=[], required=True,
                   help="skill dir (containing SKILL.md) or a prompt .md file; repeat for A/B")
    p.add_argument("--runner", choices=["llm", "mock"], default="llm")
    p.add_argument("--mock-outputs", help="fixture JSON for --runner mock, keys: '<skill>::<task>'")
    p.add_argument("--model", default=os.environ.get("SKILLEVAL_MODEL", DEFAULT_MODEL))
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


def cmd_run(args) -> int:
    options = RunOptions(
        base_url=args.base_url, model=args.model, temperature=args.temperature,
        max_tokens=args.max_tokens, timeout=args.timeout, runner=args.runner,
        judge=not args.no_judge, judge_model=args.judge_model,
        mock_outputs=args.mock_outputs, api_key=args.api_key, env_file=args.env_file,
        prices_file=args.prices, out_dir=args.out, baseline=args.baseline,
        save_baseline=args.save_baseline, max_regression=args.max_regression,
        fail_under=args.fail_under, quiet=args.quiet,
    )
    log = (lambda *a, **k: None) if args.quiet else print

    api_key, source = (None, "not needed (mock runner)")
    if args.runner == "llm":
        api_key, source = resolve_api_key(args.api_key, args.env_file)
        if not api_key:
            print("error: no API key found (checked --api-key, SKILLEVAL_API_KEY/DEEPSEEK_API_KEY,"
                  " --env-file). Use --runner mock to run offline.", file=sys.stderr)
            return 2
    log("runner=%s model=%s key=%s" % (args.runner, args.model, source if api_key else "n/a"))

    try:
        tasks = load_tasks(args.suite)
        skills = [load_skill(p) for p in args.skill]
        runner = make_runner(options, api_key)
    except (SuiteError, RunnerError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    log("suite=%s tasks=%d skills=%s" % (args.suite, len(tasks), [s.id for s in skills]))
    prices = Prices.load(args.prices, args.model)

    results = []
    for skill in skills:
        log("→ %s" % skill.id)
        results.append(run_skill(skill, tasks, runner, options, logger=log))

    verdict = VERDICT_PASS
    comparison = None
    if any(o.error for r in results for o in r.outcomes):
        errors = [o.error for r in results for o in r.outcomes if o.error]
        if all(o.error for r in results for o in r.outcomes):
            verdict = VERDICT_ERROR
        log("note: %d task(s) reported runner errors, e.g. %s" % (len(errors), errors[0][:120]))

    if args.baseline and not verdict == VERDICT_ERROR:
        if not os.path.exists(args.baseline):
            print("error: baseline %s not found" % args.baseline, file=sys.stderr)
            return 2
        with open(args.baseline, encoding="utf-8") as fh:
            baseline = json.load(fh)
        comparison = compare_to_baseline(results, baseline, args.max_regression)
        if any(v.get("regression") for v in comparison.values()):
            verdict = VERDICT_REGRESSION

    if args.fail_under is not None:
        for r in results:
            if r.aggregate()["checks"]["pass_rate"] < args.fail_under:
                verdict = VERDICT_REGRESSION
                log("below floor: %s check pass rate < %.2f" % (r.skill_id, args.fail_under))

    markdown = render_markdown(results, options, comparison=comparison, verdict=verdict)
    md_path, json_path = write_outputs(results, options, args.out, markdown, comparison=comparison,
                                       verdict=verdict)
    if args.save_baseline:
        with open(args.save_baseline, "w", encoding="utf-8") as fh:
            json.dump(baseline_from(results), fh, ensure_ascii=False, indent=2)

    log("\n%s" % markdown.split("## Failure evidence")[0])
    log("report: %s\n        %s" % (md_path, json_path))
    log("verdict: %s" % verdict)
    return {VERDICT_PASS: 0, VERDICT_REGRESSION: 1, VERDICT_ERROR: 2}[verdict]


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
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
