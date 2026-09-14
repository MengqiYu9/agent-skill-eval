# -*- coding: utf-8 -*-
"""Deterministic assertions.

These are the part of the eval that does not need a model: cheap, stable and
suitable as a CI gate. Every check returns a CheckResult and never raises on
malformed model output — a broken output must be *reported*, not crash the run.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

CJK_RE = re.compile(r"[\u4e00-\u9fff]")

MIN_LATIN_LETTERS = 20  # below this we treat the text as non-latin for language checks


@dataclass
class CheckResult:
    id: str
    type: str
    passed: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "passed": self.passed, "detail": self.detail}


def extract_json(text: str):
    """Best-effort: prefer a fenced ```json block, else the outermost {...}."""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    candidate = fence.group(1) if fence else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(candidate[start:end + 1])
    except Exception:
        return None


def _dig(obj, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return None
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur


def run_checks(specs: list[dict], text: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    for spec in specs or []:
        out.append(_one(spec, text))
    return out


def _one(spec: dict, text: str) -> CheckResult:
    cid = spec.get("id") or spec.get("type", "check")
    ctype = spec.get("type", "")
    text = text or ""

    try:
        if ctype == "must_include":
            needles = spec.get("all") or []
            missing = [n for n in needles if n not in text]
            if not needles:
                return CheckResult(cid, ctype, True, "no needles configured")
            return CheckResult(cid, ctype, not missing,
                               "missing: %s" % missing if missing else "all %d present" % len(needles))

        if ctype == "must_not_include":
            needles = spec.get("any") or []
            found = [n for n in needles if n in text]
            return CheckResult(cid, ctype, not found, "found: %s" % found if found else "clean")

        if ctype == "regex_all":
            pattern = spec.get("pattern", "")
            matches = re.findall(pattern, text)
            need = int(spec.get("min_matches", 1))
            unique = len(set(matches))
            passed = unique >= need
            return CheckResult(cid, ctype, passed,
                               "%d unique match(es) of /%s/, need %d" % (unique, pattern, need))

        if ctype == "regex_none":
            pattern = spec.get("pattern", "")
            matches = re.findall(pattern, text)
            return CheckResult(cid, ctype, not matches,
                               "matched %s" % matches[:5] if matches else "no match")

        if ctype == "json_valid":
            data = extract_json(text)
            return CheckResult(cid, ctype, data is not None,
                               "parsed" if data is not None else "no parseable JSON object found")

        if ctype == "json_path":
            data = extract_json(text)
            if data is None:
                return CheckResult(cid, ctype, False, "no parseable JSON")
            missing = [p for p in spec.get("paths", []) if _dig(data, p) in (None, "", [], {})]
            return CheckResult(cid, ctype, not missing,
                               "missing/empty: %s" % missing if missing else "all paths present")

        if ctype == "max_chars":
            limit = int(spec.get("value", 1000))
            n = len(text)
            return CheckResult(cid, ctype, n <= limit, "%d chars (limit %d)" % (n, limit))

        if ctype == "min_chars":
            limit = int(spec.get("value", 100))
            n = len(text)
            return CheckResult(cid, ctype, n >= limit, "%d chars (min %d)" % (n, limit))

        if ctype == "language":
            want = spec.get("value", "zh")
            cjk = len(CJK_RE.findall(text))
            latin = len(re.findall(r"[A-Za-z]", text))
            if want == "zh":
                passed = cjk > 0 and cjk >= 0.15 * (cjk + latin)
                return CheckResult(cid, ctype, passed, "cjk=%d latin=%d" % (cjk, latin))
            passed = cjk == 0 and latin >= MIN_LATIN_LETTERS
            return CheckResult(cid, ctype, passed, "cjk=%d latin=%d" % (cjk, latin))

        return CheckResult(cid, ctype, False, "unknown check type %r" % ctype)

    except Exception as exc:  # never let a bad spec kill the run
        return CheckResult(cid, ctype, False, "check raised %s: %s" % (type(exc).__name__, exc))


def summarize(results: list[CheckResult]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    return {
        "total": total,
        "passed": passed,
        "pass_rate": (passed / total) if total else 0.0,
        "failed_ids": [r.id for r in results if not r.passed],
    }
