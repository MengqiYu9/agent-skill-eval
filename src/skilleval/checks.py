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


def strict_json(text):
    """One complete JSON value; reject duplicate keys and non-finite numbers."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: %s" % key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("invalid JSON constant: %s" % value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def schema_validator(schema):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except Exception:
        class Error:
            def __init__(self, message): self.message = message
        class Draft202012Validator:
            def __init__(self, schema, format_checker=None): self.schema = schema
            @staticmethod
            def check_schema(schema):
                if not isinstance(schema, dict): raise ValueError("schema must be an object")
            def iter_errors(self, value, schema=None, path=""):
                schema = self.schema if schema is None else schema
                typ = schema.get("type")
                if typ == "object" and not isinstance(value, dict): yield Error("is not of type object"); return
                if typ == "array" and not isinstance(value, list): yield Error("is not of type array"); return
                if typ == "string" and not isinstance(value, str): yield Error("is not of type string"); return
                if "const" in schema and value != schema["const"]: yield Error("does not match const")
                if "enum" in schema and value not in schema["enum"]: yield Error("is not one of enum values")
                if isinstance(value, dict):
                    for key in schema.get("required", []):
                        if key not in value: yield Error("%s is a required property" % key)
                    if schema.get("additionalProperties") is False:
                        for key in value:
                            if key not in schema.get("properties", {}): yield Error("additional property %s" % key)
                    for key, child in schema.get("properties", {}).items():
                        if key in value: yield from self.iter_errors(value[key], child, path + "." + key)
                if isinstance(value, list):
                    if len(value) < schema.get("minItems", 0): yield Error("has too few items")
                    if len(value) > schema.get("maxItems", 10**9): yield Error("has too many items")
                    for item in value: yield from self.iter_errors(item, schema.get("items", {}), path)
                if isinstance(value, str) and len(value) < schema.get("minLength", 0): yield Error("is too short")

        class FormatChecker: pass
    # Evaluation must not retrieve schemas over the network.
    def inspect(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "$dynamicRef") and (not isinstance(item, str) or not item.startswith("#")):
                    raise ValueError("only local schema references are supported")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)
    inspect(schema)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_check(spec):
    """Reject invalid test definitions before executing a model."""
    if not isinstance(spec, dict):
        raise ValueError("check must be an object")
    kind = spec.get("type")
    if kind in ("json_valid", "json_strict"):
        return
    if kind == "json_schema":
        if "schema" not in spec:
            raise ValueError("json_schema requires schema")
        schema_validator(spec["schema"])
        return
    if kind == "json_equals":
        if not isinstance(spec.get("path"), str) or "value" not in spec:
            raise ValueError("json_equals requires path and value")
        return
    field = {"must_include": "all", "must_not_include": "any", "json_path": "paths"}.get(kind)
    if field:
        values = spec.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValueError("%s requires nonempty string list %s" % (kind, field))
        return
    if kind in ("regex_all", "regex_none"):
        if not isinstance(spec.get("pattern"), str) or not spec["pattern"]:
            raise ValueError("regex requires a nonempty pattern")
        re.compile(spec["pattern"])
        if kind == "regex_all" and (type(spec.get("min_matches", 1)) is not int or spec.get("min_matches", 1) < 1):
            raise ValueError("min_matches must be a positive integer")
        return
    if kind in ("max_chars", "min_chars"):
        if type(spec.get("value")) is not int or spec["value"] < 0:
            raise ValueError("length limit must be a nonnegative integer")
        return
    if kind == "language" and spec.get("value") in ("zh", "en"):
        return
    raise ValueError("unknown check type or invalid specification: %r" % kind)


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


def _dig(obj, path: str, missing=None):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except Exception:
                return missing
        elif isinstance(cur, dict):
            if part not in cur:
                return missing
            cur = cur[part]
        else:
            return missing
    return cur


def run_checks(specs: list[dict], text: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    for spec in specs or []:
        out.append(_one(spec, text))
    return out


def _one(spec: dict, text: str) -> CheckResult:
    if not isinstance(spec, dict):
        return CheckResult("invalid", "invalid", False, "check must be an object")
    cid = spec.get("id") or spec.get("type", "check")
    ctype = spec.get("type", "")
    text = text or ""

    try:
        if ctype == "json_strict":
            strict_json(text)
            return CheckResult(cid, ctype, True, "complete JSON value")

        if ctype == "json_schema":
            data = strict_json(text)
            errors = list(schema_validator(spec["schema"]).iter_errors(data))
            return CheckResult(cid, ctype, not errors, "; ".join(e.message for e in errors[:5]) or "schema matched")

        if ctype == "json_equals":
            actual = _dig(strict_json(text), spec["path"], missing=object())
            expected = spec["value"]
            passed = type(actual) is type(expected) and actual == expected
            return CheckResult(cid, ctype, passed, "actual=%r expected=%r" % (actual, expected))

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
