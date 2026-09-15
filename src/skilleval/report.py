# -*- coding: utf-8 -*-
"""Report rendering (markdown) and baseline comparison / regression verdict."""
from __future__ import annotations

import json
import os
import uuid
import html

from .gate import (VERDICT_PASS, VERDICT_REGRESSION, VERDICT_ERROR, baseline_from, compare_to_baseline)


def render_markdown(results: list, options, baseline_info: dict | None = None,
                    comparison: dict | None = None, verdict: str = VERDICT_PASS) -> str:
    lines = []
    lines.append("# agent-skill-eval report")
    lines.append("")
    lines.append("| field | value |")
    lines.append("| --- | --- |")
    lines.append("| runner | `%s` |" % options.runner)
    lines.append("| model | `%s` |" % options.model)
    lines.append("| judge | %s |" % ("`%s`" % (options.judge_model or options.model) if options.judge else "off"))
    first = results[0] if results else None
    lines.append("| started | %s |" % (first.started_at if first else "-"))
    lines.append("| skills | %d |" % len(results))
    lines.append("| verdict | **%s** |" % verdict)
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| skill | mean task checks | check pass | judge mean | mean latency | tokens (in/out) | cost | truncated |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        agg = r.aggregate()
        cost = "n/a" if agg["cost_usd"] is None else "$%.4f" % agg["cost_usd"]
        lines.append("| `%s` | %.2f | %.2f (%d/%d) | %s | %s s | %d / %d | %s | %d |" % (
            r.skill_id, agg["task_pass_rate"], agg["checks"]["pass_rate"],
            agg["checks"]["passed"], agg["checks"]["total"],
            "n/a" if agg["judge_mean"] is None else "%.2f" % agg["judge_mean"],
            "n/a" if agg["latency_mean_s"] is None else agg["latency_mean_s"],
            agg["tokens"]["prompt"], agg["tokens"]["completion"], cost,
            len(agg.get("truncated_tasks", []))))
    truncated = [(r.skill_id, t) for r in results for t in r.aggregate().get("truncated_tasks", [])]
    if truncated:
        lines.append("")
        lines.append("> **Truncation warning** — %d task(s) stopped at the token cap, so their output is "
                     "incomplete: %s. Raise `--max-tokens` before reading these numbers as a skill result."
                     % (len(truncated), ", ".join("`%s`/`%s`" % t for t in truncated)))
    lines.append("")

    if len(results) > 1:
        lines.append("## A/B delta (first skill = baseline arm)")
        lines.append("")
        base = results[0].aggregate()
        lines.append("| skill | Δ task pass | Δ check pass | Δ judge | Δ mean latency |")
        lines.append("| --- | --- | --- | --- | --- |")
        for r in results[1:]:
            agg = r.aggregate()
            dj = ("n/a" if (agg["judge_mean"] is None or base["judge_mean"] is None)
                  else "%+.2f" % (agg["judge_mean"] - base["judge_mean"]))
            dl = ("n/a" if (agg["latency_mean_s"] is None or base["latency_mean_s"] is None)
                  else "%+.2f s" % (agg["latency_mean_s"] - base["latency_mean_s"]))
            lines.append("| `%s` | %+.2f | %+.2f | %s | %s |" % (
                r.skill_id, agg["task_pass_rate"] - base["task_pass_rate"],
                agg["checks"]["pass_rate"] - base["checks"]["pass_rate"], dj, dl))
        lines.append("")

    lines.append("## Completion and judging")
    lines.append("")
    for r in results:
        a = r.aggregate()
        lines.append("- %s: %d/%d scored attempts; task success %.2f; judge errors %d; worker tokens %s; judge tokens %s" % (r.skill_id, a["scored_tasks"], a["tasks"], a["task_success_rate"], len(a["judge_errors"]), a["worker_tokens"], a["judge_tokens"]))
        lines.append("  Judge criteria: %s" % a["per_judge"])
    lines.append("")
    lines.append("## Per-check outcome")
    lines.append("")
    check_ids = sorted({c.id for r in results for o in r.outcomes for c in o.checks})
    lines.append("| check | " + " | ".join("`%s`" % r.skill_id for r in results) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in results) + " |")
    for cid in check_ids:
        cells = []
        for r in results:
            passed = total = 0
            for o in r.outcomes:
                for c in o.checks:
                    if c.id == cid:
                        total += 1
                        passed += 1 if c.passed else 0
            cells.append("%d/%d" % (passed, total) if total else "-")
        lines.append("| `%s` | %s |" % (cid, " | ".join(cells)))
    lines.append("")

    lines.append("## Per-task detail")
    lines.append("")
    for r in results:
        lines.append("### `%s`" % r.skill_id)
        lines.append("")
        lines.append("| task | checks | judge | latency | finish | failed checks | error |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for o in r.outcomes:
            lines.append("| `%s` | %d/%d | %s | %.2f s | %s | %s | %s |" % (
                o.task_id + " #" + str(o.repeat), o.check_summary["passed"], o.check_summary["total"],
                "-" if not o.judge else ("err" if o.judge.error else "%.2f" % o.judge.mean),
                o.latency_s,
                (o.finish_reason or "-") + (" ⚠" if o.truncated else ""),
                ", ".join("`%s`" % c.id for c in o.checks if not c.passed) or "-",
                (o.error or "-")[:70]))
        lines.append("")

    if comparison:
        lines.append("## Baseline comparison")
        lines.append("")
        lines.append("| skill | baseline | task pass Δ | check pass Δ | regressions |")
        lines.append("| --- | --- | --- | --- | --- |")
        for sid, entry in comparison.items():
            if not entry.get("baseline_found"):
                lines.append("| `%s` | missing | - | - | baseline entry not found |" % sid)
                continue
            lines.append("| `%s` | yes | %+.2f | %+.2f | %s |" % (
                sid, entry.get("task_pass_rate_delta", 0.0), entry.get("check_pass_rate_delta", 0.0),
                "; ".join(entry.get("check_regressions", [])) or entry.get("error") or "; ".join(entry.get("notes", [])) or "none"))
        lines.append("")

    lines.append("## Failure evidence")
    lines.append("")
    shown = 0
    for r in results:
        for o in r.outcomes:
            failed = [c for c in o.checks if not c.passed]
            if not failed and not o.error and not o.truncated and not (o.judge and o.judge.error):
                continue
            shown += 1
            lines.append("<details><summary><code>%s</code> / <code>%s</code></summary>" % (r.skill_id, o.task_id))
            lines.append("")
            for c in failed:
                lines.append("- `%s` (%s) — %s" % (c.id, c.type, c.detail))
            if o.error:
                lines.append("- runner error: %s" % o.error)
            if o.truncated:
                lines.append("- output truncated; excluded from quality aggregates")
            if o.judge and o.judge.error:
                lines.append("- judge error: " + html.escape(o.judge.error))
            if o.judge and o.judge.notes:
                lines.append("- judge notes: %s" % o.judge.notes)
            snippet = (o.output or "")[:600].replace("```", "ʼʼʼ")
            lines.append("")
            lines.append("```text")
            lines.append(snippet + ("\n…[truncated]" if len(o.output or "") > 600 else ""))
            lines.append("```")
            lines.append("</details>")
            lines.append("")
    if not shown:
        lines.append("No failures — every check passed on every task.")
        lines.append("")
    return "\n".join(lines)


def write_outputs(results: list, options, out_dir: str, markdown: str, baseline_info=None,
                  comparison=None, verdict: str = VERDICT_PASS):
    os.makedirs(out_dir, exist_ok=True)
    stamp = uuid.uuid4().hex
    md_path = os.path.join(out_dir, "report-%s.md" % stamp)
    json_path = os.path.join(out_dir, "report-%s.json" % stamp)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    payload = {
        "schema_version": 2,
        "verdict": verdict,
        "options": {k: v for k, v in vars(options).items() if k != "api_key"},
        "results": [r.as_dict() for r in results],
        "baseline_comparison": comparison,
        "baseline_candidate": baseline_from(results) if verdict == VERDICT_PASS else None,
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return md_path, json_path
