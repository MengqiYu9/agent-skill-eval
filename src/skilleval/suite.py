# -*- coding: utf-8 -*-
"""Loading skills + task sets, and executing one skill against one task set."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

from .checks import CheckResult, run_checks, summarize
from .judge import JudgeResult, judge_output

try:  # PyYAML is optional: JSON task sets work without it
    import yaml
except Exception:  # pragma: no cover
    yaml = None


class SuiteError(RuntimeError):
    pass


@dataclass
class Skill:
    id: str
    path: str
    instructions: str
    version: str = ""


@dataclass
class Task:
    id: str
    input: str
    checks: list = field(default_factory=list)
    rubric: list = field(default_factory=list)
    notes: str = ""

    def system_prompt(self, skill: Skill) -> str:
        return skill.instructions

    def user_prompt(self) -> str:
        return self.input


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_skill(path: str) -> Skill:
    path = os.path.abspath(path)
    if os.path.isdir(path):
        skill_md = os.path.join(path, "SKILL.md")
        if not os.path.exists(skill_md):
            raise SuiteError("no SKILL.md in %s" % path)
        target = skill_md
        parts = os.path.normpath(path).split(os.sep)
        sid = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    else:
        target = path
        sid = os.path.splitext(os.path.basename(path))[0]
    return Skill(id=sid, path=path, instructions=read_text(target))


def _load_doc(path: str):
    text = read_text(path)
    if path.endswith((".yaml", ".yml")):
        if yaml is None:
            raise SuiteError("PyYAML not installed; use .json task files or pip install pyyaml")
        return yaml.safe_load(text)
    return json.loads(text)


def load_tasks(path: str) -> list[Task]:
    path = os.path.abspath(path)
    files = []
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            if name.endswith((".yaml", ".yml", ".json")):
                files.append(os.path.join(path, name))
    else:
        files.append(path)
    if not files:
        raise SuiteError("no task files found at %s" % path)

    tasks: list[Task] = []
    for f in files:
        doc = _load_doc(f)
        items = doc if isinstance(doc, list) else (doc or {}).get("tasks", [])
        for raw in items:
            if "id" not in raw or "input" not in raw:
                raise SuiteError("%s: every task needs 'id' and 'input'" % f)
            tasks.append(Task(id=raw["id"], input=raw["input"], checks=raw.get("checks", []),
                              rubric=raw.get("rubric", []), notes=raw.get("notes", "")))
    if not tasks:
        raise SuiteError("no tasks parsed from %s" % path)
    return tasks


@dataclass
class Outcome:
    task_id: str
    output: str = ""
    checks: list = field(default_factory=list)
    check_summary: dict = field(default_factory=dict)
    judge: JudgeResult | None = None
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None
    finish_reason: str = ""
    truncated: bool = False
    reasoning_chars: int = 0

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "output": self.output,
            "checks": [c.as_dict() for c in self.checks],
            "check_summary": self.check_summary,
            "judge": self.judge.as_dict() if self.judge else None,
            "latency_s": round(self.latency_s, 2),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "finish_reason": self.finish_reason,
            "truncated": self.truncated,
            "reasoning_chars": self.reasoning_chars,
            "error": self.error,
        }


@dataclass
class RunResult:
    skill_id: str
    model: str
    outcomes: list = field(default_factory=list)
    duration_s: float = 0.0
    cost: float | None = None
    started_at: str = ""

    def aggregate(self, prices=None) -> dict:
        n = len(self.outcomes)
        pass_rates = [o.check_summary.get("pass_rate", 0.0) for o in self.outcomes]
        judges = [o.judge.mean for o in self.outcomes if o.judge and not o.judge.error]
        lat = [o.latency_s for o in self.outcomes if o.latency_s]
        checks_total = sum(o.check_summary.get("total", 0) for o in self.outcomes)
        checks_passed = sum(o.check_summary.get("passed", 0) for o in self.outcomes)
        per_check: dict = {}
        for o in self.outcomes:
            for c in o.checks:
                entry = per_check.setdefault(c.id, {"passed": 0, "total": 0})
                entry["total"] += 1
                entry["passed"] += 1 if c.passed else 0
        pt = sum(o.prompt_tokens for o in self.outcomes)
        ct = sum(o.completion_tokens for o in self.outcomes)
        errors = [o.task_id for o in self.outcomes if o.error]
        return {
            "tasks": n,
            "task_pass_rate": round(sum(pass_rates) / n, 4) if n else 0.0,
            "checks": {"passed": checks_passed, "total": checks_total,
                       "pass_rate": round(checks_passed / checks_total, 4) if checks_total else 0.0},
            "judge_mean": round(sum(judges) / len(judges), 3) if judges else None,
            "judge_tasks": len(judges),
            "latency_mean_s": round(sum(lat) / len(lat), 2) if lat else None,
            "tokens": {"prompt": pt, "completion": ct, "total": pt + ct},
            "cost_usd": prices.cost(pt, ct) if prices else None,
            "errors": errors,
            "truncated_tasks": [o.task_id for o in self.outcomes if o.truncated],
            "per_check": per_check,
        }

    def as_dict(self, prices=None) -> dict:
        return {"skill_id": self.skill_id, "model": self.model, "started_at": self.started_at,
                "duration_s": round(self.duration_s, 2),
                "aggregate": self.aggregate(prices),
                "outcomes": [o.as_dict() for o in self.outcomes]}


def run_skill(skill: Skill, tasks: list[Task], runner, options, logger=print) -> RunResult:
    started = time.time()
    result = RunResult(skill_id=skill.id, model=options.model,
                       started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    for task in tasks:
        key = "%s::%s" % (skill.id, task.id)
        if runner.kind == "mock":
            completion = runner.complete(task.system_prompt(skill), task.user_prompt(), key=key)
            if completion.error:
                completion = runner.complete(task.system_prompt(skill), task.user_prompt(),
                                             key=task.id)
        else:
            completion = runner.complete(task.system_prompt(skill), task.user_prompt())

        checks = run_checks(task.checks, completion.text)
        outcome = Outcome(
            task_id=task.id,
            output=completion.text,
            checks=checks,
            check_summary=summarize(checks),
            latency_s=completion.latency_s,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            error=completion.error,
            finish_reason=completion.finish_reason,
            truncated=completion.truncated,
            reasoning_chars=completion.reasoning_chars,
        )
        if options.judge and not completion.error:
            outcome.judge = judge_output(runner, task.rubric, task.input, completion.text,
                                        model=options.judge_model)
        result.outcomes.append(outcome)
        logger("  %-28s checks %d/%d%s%s" % (
            task.id, outcome.check_summary["passed"], outcome.check_summary["total"],
            "  judge %.2f" % outcome.judge.mean if outcome.judge and not outcome.judge.error else "",
            "  ERROR %s" % outcome.error[:60] if outcome.error else ""))
    result.duration_s = time.time() - started
    return result
