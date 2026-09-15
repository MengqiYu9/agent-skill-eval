"""Fail-closed baseline comparison and verdict policy."""
from __future__ import annotations

import math
import copy

VERDICT_PASS = "PASS"
VERDICT_REGRESSION = "REGRESSION"
VERDICT_ERROR = "ERROR"


def complete(result):
    return bool(result.outcomes) and all(
        not o.error and not o.truncated and o.checks and not (o.judge and o.judge.error)
        for o in result.outcomes)


def task_checks(result):
    groups = {}
    for outcome in result.outcomes:
        for check in outcome.checks:
            groups.setdefault(outcome.task_id + "::" + check.id, []).append(int(check.passed))
    return {key: sum(values) / len(values) for key, values in groups.items()}


def task_judges(result):
    groups = {}
    for outcome in result.outcomes:
        if outcome.judge and not outcome.judge.error:
            for key, score in outcome.judge.scores.items():
                groups.setdefault(outcome.task_id + "::" + key, []).append(score / 5)
    return {key: sum(values) / len(values) for key, values in groups.items()}


def baseline_from(results):
    if not results or any(not complete(r) for r in results):
        raise ValueError("cannot create baseline from incomplete or invalid results")
    baseline = {"__schema_version__": 2}
    for r in results:
        if r.skill_id in baseline:
            raise ValueError("duplicate skill id")
        a = r.aggregate()
        baseline[r.skill_id] = {
            "task_pass_rate": a["task_pass_rate"], "task_success_rate": a["task_success_rate"],
            "check_pass_rate": a["checks"]["pass_rate"], "judge_mean": a["judge_mean"],
            "per_check": {k: v["passed"] / v["total"] for k, v in a["per_check"].items()},
            "per_task": a["per_task"], "per_task_check": task_checks(r),
            "per_task_judge": task_judges(r), "model": r.model, "provenance": copy.deepcopy(r.provenance),
        }
    return baseline


def compare_to_baseline(results, baseline, max_regression, baseline_skill=None, allow_legacy=False):
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    version = baseline.get("__schema_version__")
    if version not in (None, 2):
        raise ValueError("unsupported baseline schema version")
    report = {}
    for r in results:
        key = baseline_skill or r.skill_id
        base = baseline.get(key)
        entry = {"skill_id": r.skill_id, "baseline_skill": key, "baseline_found": isinstance(base, dict),
                 "regression": False, "error": None, "notes": [], "check_regressions": []}
        report[r.skill_id] = entry
        if not isinstance(base, dict) or not base:
            entry["error"] = "baseline entry not found: %s" % key
            continue
        if version is None and not allow_legacy:
            entry["error"] = "legacy baseline has no fingerprints; migrate it or explicitly use --allow-legacy-baseline"
            continue
        if version is None:
            entry["notes"].append("legacy baseline: suite/configuration identity cannot be verified")
        else:
            metadata = base.get("provenance", {})
            if not r.provenance or any(not metadata.get(k) or metadata[k] != r.provenance.get(k)
                                       for k in ("suite_sha256", "config_sha256")):
                entry["error"] = "baseline suite/configuration fingerprint mismatch"
                continue
        a = r.aggregate()
        maps = {"per_check": {k: v["passed"] / v["total"] for k, v in a["per_check"].items()},
                "per_task": a["per_task"]}
        if version == 2:
            maps.update(per_task_check=task_checks(r), per_task_judge=task_judges(r))
        invalid = False
        for field, current in maps.items():
            before = base.get(field)
            if not isinstance(before, dict) or set(before) != set(current):
                entry["error"] = "baseline coverage differs: %s" % field
                invalid = True
                break
            for name, value in before.items():
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                    entry["error"] = "invalid baseline rate: %s/%s" % (field, name)
                    invalid = True
                    break
                if current[name] < value - max_regression - 1e-9:
                    entry["check_regressions"].append("%s/%s: %.4f -> %.4f" % (field, name, value, current[name]))
        if invalid:
            continue
        for key, current in (("task_pass_rate", a["task_pass_rate"]),
                             ("check_pass_rate", a["checks"]["pass_rate"])):
            previous = base.get(key)
            if type(previous) not in (int, float) or not math.isfinite(previous) or not 0 <= previous <= 1:
                entry["error"] = "invalid baseline rate: %s" % key
                break
            entry[key] = current
            entry[key + "_delta"] = current - previous
            if current < previous - max_regression - 1e-9:
                entry["check_regressions"].append("%s dropped" % key)
        entry["regression"] = bool(entry["check_regressions"])
    return report


def decide_verdict(results, options, comparison=None):
    # Infrastructure/measurement errors always take precedence over quality thresholds.
    if not results or any(not complete(r) for r in results):
        return VERDICT_ERROR
    if comparison and any(e.get("error") for e in comparison.values()):
        return VERDICT_ERROR
    if comparison and any(e.get("regression") for e in comparison.values()):
        return VERDICT_REGRESSION
    floor = options.fail_under
    if floor is None and not comparison:
        floor = 1.0
    for r in results:
        a = r.aggregate()
        if floor is not None and a["checks"]["pass_rate"] < floor:
            return VERDICT_REGRESSION
        if options.judge_fail_under is not None:
            if a["judge_mean"] is None:
                return VERDICT_ERROR
            if a["judge_mean"] < options.judge_fail_under:
                return VERDICT_REGRESSION
        if options.max_cost is not None:
            if a["cost_usd"] is None:
                return VERDICT_ERROR
            if a["cost_usd"] > options.max_cost:
                return VERDICT_REGRESSION
        if options.max_latency is not None and r.duration_s > options.max_latency:
            return VERDICT_REGRESSION
    return VERDICT_PASS

