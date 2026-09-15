"""Validated task loading, isolated execution and auditable aggregation."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from .checks import run_checks, summarize, validate_check
from .judge import JudgeResult, judge_output

try:
    import yaml
    if not hasattr(yaml, "safe_load"):
        raise ImportError("incomplete PyYAML installation")
except Exception:
    yaml = None


class SuiteError(RuntimeError):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def safe_relative(value):
    if not isinstance(value, str):
        raise ValueError("relative path must be text")
    path = Path(value)
    if not isinstance(value, str) or not value or path.is_absolute() or ".." in path.parts or ":" in value or "\\" in value:
        raise ValueError("expected a portable relative path: %r" % value)
    return path


@dataclass
class Skill:
    id: str
    path: str
    instructions: str
    version: str = ""
    digest: str = ""
    name: str = ""


@dataclass
class Task:
    id: str
    input: str
    checks: list = field(default_factory=list)
    rubric: list = field(default_factory=list)
    notes: str = ""
    files: dict = field(default_factory=dict)

    def system_prompt(self, skill):
        return skill.instructions

    def user_prompt(self):
        return self.input


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise SuiteError(str(exc)) from exc


def load_skill(path):
    if path == "__no_skill__":
        return Skill("no-skill", "", "", digest=fingerprint(""), name="no-skill")
    path = Path(path).absolute()
    target = path / "SKILL.md" if path.is_dir() else path
    instructions = read_text(target)
    sid = "/".join(path.parts[-2:]) if path.is_dir() else path.stem
    name = path.parent.name if path.is_dir() else path.stem
    if instructions.startswith("---"):
        try:
            frontmatter = instructions.split("---", 2)[1]
            if yaml is not None:
                meta = yaml.safe_load(frontmatter)
            else:
                meta = {}
                for line in frontmatter.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meta[key.strip()] = value.strip().strip("\"'")
            if not isinstance(meta, dict) or not isinstance(meta.get("name"), str) or not isinstance(meta.get("description"), str):
                raise ValueError("skill frontmatter requires name and description")
            name = meta["name"]
        except (ValueError, IndexError, yaml.YAMLError) as exc:
            raise SuiteError("invalid skill frontmatter: %s" % exc) from exc
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise SuiteError("skill name must be lowercase letters, digits and hyphens")
    resources = {}
    root = target.parent
    for resource in sorted(root.rglob("*")) if path.is_dir() else [target]:
        if resource.is_symlink():
            raise SuiteError("skill packages must not contain symlinks")
        if resource.is_file():
            resources[resource.relative_to(root).as_posix()] = hashlib.sha256(resource.read_bytes()).hexdigest()
    return Skill(sid, str(path), instructions, path.name if path.is_dir() else "",
                 fingerprint(resources), name)


def _load_doc(path):
    text = read_text(path)
    try:
        if str(path).endswith((".yaml", ".yml")):
            if yaml is None:
                raise SuiteError("PyYAML not installed")
            return yaml.safe_load(text)
        return json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SuiteError("%s: %s" % (path, exc)) from exc
    except Exception as exc:
        raise SuiteError("%s: %s" % (path, exc)) from exc


def load_tasks(path):
    path = Path(path).absolute()
    files = sorted(p for p in path.iterdir() if p.suffix in (".yaml", ".yml", ".json")) if path.is_dir() else [path]
    tasks, ids = [], set()
    for f in files:
        doc = _load_doc(f)
        items = doc if isinstance(doc, list) else doc.get("tasks") if isinstance(doc, dict) else None
        if not isinstance(items, list) or not items:
            raise SuiteError("%s: tasks must be a nonempty list" % f)
        for raw in items:
            try:
                if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"].strip():
                    raise ValueError("task requires a nonempty id")
                if raw["id"] in ids:
                    raise ValueError("duplicate task id: %s" % raw["id"])
                if not isinstance(raw.get("input"), str) or not raw["input"].strip():
                    raise ValueError("task requires a nonempty input")
                checks, rubric = raw.get("checks"), raw.get("rubric", [])
                if not isinstance(checks, list) or not checks:
                    raise ValueError("task requires at least one check")
                check_ids = set()
                for check in checks:
                    validate_check(check)
                    cid = check.get("id")
                    if not isinstance(cid, str) or not cid or cid in check_ids:
                        raise ValueError("check ids must be nonempty and unique within a task")
                    check_ids.add(cid)
                    if "artifact" in check:
                        safe_relative(check["artifact"])
                if not isinstance(rubric, list):
                    raise ValueError("rubric must be a list")
                rub_ids = set()
                for criterion in rubric:
                    if not isinstance(criterion, dict) or not isinstance(criterion.get("id"), str) or not criterion["id"] or criterion["id"] in rub_ids or not isinstance(criterion.get("desc"), str):
                        raise ValueError("rubric requires unique ids and descriptions")
                    rub_ids.add(criterion["id"])
                inputs = raw.get("files", {})
                if not isinstance(inputs, dict):
                    raise ValueError("files must map relative paths to text")
                for name, text in inputs.items():
                    safe_relative(name)
                    if name.split("/")[0].startswith(".") or not isinstance(text, str):
                        raise ValueError("fixture files must be text and cannot install project configuration")
                tasks.append(Task(raw["id"], raw["input"], checks, rubric, raw.get("notes", ""), inputs))
                ids.add(raw["id"])
            except Exception as exc:
                raise SuiteError("%s: %s" % (f, exc)) from exc
    if not tasks:
        raise SuiteError("no tasks found at %s" % path)
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
    repeat: int = 1
    events: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def as_dict(self):
        return asdict(self)


@dataclass
class RunResult:
    skill_id: str
    model: str
    outcomes: list = field(default_factory=list)
    duration_s: float = 0.0
    cost: float | None = None
    started_at: str = ""
    provenance: dict = field(default_factory=dict)
    prices: object = None
    judge_prices: object = None

    def aggregate(self, prices=None):
        valid = [o for o in self.outcomes if not o.error and not o.truncated]
        rates = [o.check_summary.get("pass_rate", 0) for o in valid]
        judges = [o.judge for o in valid if o.judge and not o.judge.error]
        per_check, per_task, per_judge = {}, {}, {}
        total = passed = 0
        for o in valid:
            row = per_task.setdefault(o.task_id, {"passed": 0, "total": 0})
            row["passed"] += o.check_summary.get("passed", 0)
            row["total"] += o.check_summary.get("total", 0)
            for c in o.checks:
                entry = per_check.setdefault(c.id, {"passed": 0, "total": 0})
                entry["total"] += 1
                entry["passed"] += int(c.passed)
                total += 1
                passed += int(c.passed)
            if o.judge and not o.judge.error:
                for cid, score in o.judge.scores.items():
                    per_judge.setdefault(cid, []).append(score)
        pt = sum(o.prompt_tokens for o in self.outcomes)
        ct = sum(o.completion_tokens for o in self.outcomes)
        jpt = sum(o.judge.prompt_tokens for o in self.outcomes if o.judge)
        jct = sum(o.judge.completion_tokens for o in self.outcomes if o.judge)
        wp = prices or self.prices
        jp = self.judge_prices or wp
        worker_cost = wp.cost(pt, ct) if wp else None
        if any(o.metadata.get("cost_supported") is False for o in self.outcomes):
            worker_cost = None
        judge_cost = (jp.cost(jpt, jct) if jp else None) if any(o.judge for o in self.outcomes) else 0.0
        latencies = [o.latency_s for o in valid]
        return {
            "tasks": len(self.outcomes), "unique_tasks": len({o.task_id for o in self.outcomes}),
            "scored_tasks": len(valid),
            "task_pass_rate": sum(rates) / len(rates) if rates else 0.0,
            "task_success_rate": sum(r == 1 for r in rates) / len(rates) if rates else 0.0,
            "checks": {"passed": passed, "total": total, "pass_rate": passed / total if total else 0.0},
            "judge_mean": sum(j.mean for j in judges) / len(judges) if judges else None,
            "judge_tasks": len(judges),
            "per_judge": {k: sum(v) / len(v) for k, v in per_judge.items()},
            "latency_mean_s": sum(latencies) / len(latencies) if latencies else None,
            "tokens": {"prompt": pt + jpt, "completion": ct + jct, "total": pt + ct + jpt + jct},
            "worker_tokens": {"prompt": pt, "completion": ct},
            "judge_tokens": {"prompt": jpt, "completion": jct},
            "cost_usd": worker_cost + judge_cost if worker_cost is not None and judge_cost is not None else None,
            "errors": [o.task_id for o in self.outcomes if o.error],
            "judge_errors": [o.task_id for o in self.outcomes if o.judge and o.judge.error],
            "truncated_tasks": [o.task_id for o in self.outcomes if o.truncated],
            "per_check": per_check,
            "per_task": {k: v["passed"] / v["total"] if v["total"] else 0 for k, v in per_task.items()},
        }

    def as_dict(self, prices=None):
        return {"skill_id": self.skill_id, "model": self.model, "started_at": self.started_at,
                "duration_s": self.duration_s, "provenance": self.provenance,
                "aggregate": self.aggregate(prices), "outcomes": [o.as_dict() for o in self.outcomes]}


def run_skill(skill, tasks, runner, options, logger=print, judge_runner=None):
    started = time.monotonic()
    config = {k: getattr(options, k) for k in (
        "runner", "model", "temperature", "max_tokens", "judge", "judge_model",
        "repeats", "invocation", "agent_args", "timeout")}
    config["runtime_version"] = getattr(runner, "version", "")
    config["base_url"] = options.base_url if options.runner == "llm" or options.judge else ""
    result = RunResult(skill.id, getattr(runner, "model", options.model),
                       started_at=datetime.now(timezone.utc).isoformat(),
                       provenance={"suite_sha256": fingerprint([asdict(t) for t in tasks]),
                                   "config_sha256": fingerprint(config),
                                   "skill_sha256": skill.digest, "config": config})
    for repeat in range(1, options.repeats + 1):
        for task in tasks:
            key = "%s::%s" % (skill.id, task.id)
            if hasattr(runner, "execute"):
                completion = runner.execute(skill, task)
            elif runner.kind == "mock":
                completion = runner.complete(skill.instructions, task.input, key=key)
                if completion.error:
                    completion = runner.complete(skill.instructions, task.input, key=task.id)
            else:
                completion = runner.complete(skill.instructions, task.input)
            error = completion.error
            if not error and not completion.text.strip() and not completion.artifacts:
                error = "empty output"
            checks = []
            if not error and not completion.truncated:
                for spec in task.checks:
                    artifact = spec.get("artifact")
                    target = completion.artifacts.get(artifact) if artifact else completion.text
                    if artifact and target is None:
                        from .checks import CheckResult
                        checks.append(CheckResult(spec["id"], spec["type"], False, "artifact missing: %s" % artifact))
                    else:
                        checks.extend(run_checks([spec], target))
            outcome = Outcome(task.id, completion.text, checks, summarize(checks),
                              latency_s=completion.latency_s, prompt_tokens=completion.prompt_tokens,
                              completion_tokens=completion.completion_tokens, error=error,
                              finish_reason=completion.finish_reason, truncated=completion.truncated,
                              reasoning_chars=completion.reasoning_chars, repeat=repeat,
                              events=completion.events, artifacts=completion.artifacts, metadata=completion.metadata)
            if options.judge and task.rubric and not error and not completion.truncated:
                evidence = completion.text
                if completion.artifacts:
                    evidence += "\nARTIFACTS:\n" + json.dumps(completion.artifacts, ensure_ascii=False)
                outcome.judge = judge_output(judge_runner or runner, task.rubric, task.input, evidence,
                                            model=options.judge_model)
            result.outcomes.append(outcome)
            logger("  %s repeat=%d checks=%d/%d%s" % (
                task.id, repeat, outcome.check_summary["passed"], outcome.check_summary["total"],
                " ERROR " + error if error else " TRUNCATED" if outcome.truncated else ""))
    result.duration_s = time.monotonic() - started
    return result
