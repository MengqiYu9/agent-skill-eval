# -*- coding: utf-8 -*-
"""Rubric-based LLM judge.

The judge scores free-form qualities that deterministic checks cannot express
("is this actually grounded in the input?"). It is deliberately separate from
the generating call so one model instance cannot grade its own homework in the
same turn, and it is *optional*: a run with --no-judge is fully deterministic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .checks import extract_json

JUDGE_SYSTEM = """You are a strict evaluation judge. You score model output against a rubric.
Rules:
- Score each criterion from 0 to 5 (integers only).
- 0 = completely fails the criterion, 5 = fully satisfies it.
- Judge only what is in the OUTPUT. Do not reward length or confidence.
- If the output is not in the expected format, that is a failure of the criteria that require it.
- Reply with JSON only, no prose outside the JSON object:
{"scores": {"<criterion_id>": <int>, "..."}, "notes": "<one short sentence per problem you found>"}"""


@dataclass
class JudgeResult:
    scores: dict = field(default_factory=dict)
    notes: str = ""
    mean: float = 0.0
    error: str | None = None

    def as_dict(self) -> dict:
        return {"scores": self.scores, "notes": self.notes, "mean": self.mean, "error": self.error}


def judge_output(runner, rubric: list[dict], task_input: str, output: str,
                 model: str | None = None) -> JudgeResult:
    if not rubric:
        return JudgeResult(error="no rubric configured")
    criteria = "\n".join("- %s: %s" % (c["id"], c.get("desc", "")) for c in rubric)
    user = (
        "## Input given to the worker\n%s\n\n"
        "## Rubric\n%s\n\n"
        "## Output to score\n%s\n\n"
        "Return the JSON with one integer score per criterion id."
    ) % (task_input[:4000], criteria, output[:6000])

    prev = getattr(runner, "model", None)
    if model:
        runner.model = model
    try:
        completion = runner.complete(JUDGE_SYSTEM, user)
    finally:
        if model:
            runner.model = prev

    if completion.error:
        return JudgeResult(error=completion.error)
    data = extract_json(completion.text)
    if not isinstance(data, dict):
        return JudgeResult(error="judge did not return JSON: %s" % completion.text[:160])
    raw = data.get("scores") or {}
    scores = {}
    for crit in rubric:
        value = raw.get(crit["id"])
        try:
            scores[crit["id"]] = max(0, min(5, int(value)))
        except (TypeError, ValueError):
            scores[crit["id"]] = None
    valid = [v for v in scores.values() if isinstance(v, int)]
    mean = sum(valid) / len(valid) if valid else 0.0
    return JudgeResult(scores=scores, notes=str(data.get("notes", ""))[:400], mean=mean)
