# Case study: putting a real shipped skill on the gate

The starter suite (`structured-digest`) is a demo I wrote to exercise the harness. This one
is the point of the repo: take a skill that is **actually shipped and used**, run it, and
report what breaks — then make one targeted edit and let the gate measure it.

**Skill under test:** `document-to-action-items` — "extract cited obligations, deadlines,
tasks from documents" (Hermes bundled skill, MIT, by Ben Barclay).

**Adaptation, stated plainly:** the original skill's steps 1–2 read documents through tools
(`read_file` / `pdf`). This harness sends one system prompt + one user turn to a model, so
the documents are supplied **inline** and the run starts at step 3. Everything else — the
classification rules, the modality rule (`应当` / `可以` / `宜` must stay distinct), "unknown
owner/date stays unresolved, never invented", the conflict-surfacing rule — is the skill
as written. Tool orchestration is *not* covered by this suite; that is a real limitation,
not a footnote.

- `skills/doc-to-actions/v1/SKILL.md` — the skill's rules, unchanged.
- `skills/doc-to-actions/v2/SKILL.md` — same rules + a machine-readable output contract
  (JSON schema, per-item `citation`, `modality` enum, `未明确` for unknowns, 2500-char cap).
- `suites/doc-to-actions/` — 4 synthetic documents (contract excerpt, purchase order terms,
  meeting minutes, rectification notice), 15 checks.
- Model + judge: `deepseek-flash`, `--max-tokens 16384`, temperature 0.

Inputs are synthetic on purpose: a suite containing real contract text cannot be committed,
shared, or used as public evidence.

## Result

| arm | check pass | judge mean | tokens (in/out) | mean latency |
| --- | --- | --- | --- | --- |
| `doc-to-actions/v1` — as shipped | **0.59** (20/34) | **3.64** | 3 119 / 16 285 | 20.33 s |
| `doc-to-actions/v2` — + output contract | **1.00** (34/34) | **4.88** | 3 547 / 28 407 | 31.06 s |

Δ +0.41 check pass rate, +1.24 judge — for **1.74× the output tokens and 1.53× the latency**.
Report: [`examples/report-doc-to-actions-16384.md`](../examples/report-doc-to-actions-16384.md).

## What v1 actually failed on

Structural (all four tasks):

- `json_valid` 0/4, `contract_paths` 0/4 — the skill specifies no output format, so the model
  writes Markdown prose. Anything downstream that wants to *use* the extraction has to parse
  prose. This is the single biggest gap and it costs nothing to close.
- `length_cap` 0/4 — 3 276–3 846 characters against a 2 500 budget.

Content, and this is the interesting part — the judge's notes, not the checks:

- `notice-01`: v1 **converted a relative deadline into a date** — it took "30 日内" from a
  3 月 10 日 notice and computed 2026-04-09. The skill explicitly forbids this ("unknown
  owner/date stays `unresolved` — never invented"). A deterministic check cannot reliably
  catch a wrong date; the judge caught it and named the line.
- `contract-01`: v1 added derived dates (`2026-05-05`, `2027-04-05`) that appear nowhere in
  the material.
- `notice-01`: v1 softened a real inconsistency — it noted the正文 lists 三项 and 附件二 has
  四行, then called the counts "自洽" instead of flagging the mismatch.
- `unresolved_marked` 2/3, `owner_unresolved` 0/1: the "mark unknowns as 未明确" rule is
  applied inconsistently in prose.

Meanwhile v1 scored **5.0** on `actionability`, `modality`, `no_upgrade` and `uncertainty`:
the extraction is good, the *delivery* is what fails. Judge-only evaluation would have
called this skill fine (`grounding` 4.0); check-only evaluation would have missed the
invented date. Both signals were needed to describe the same run.

## What v2 fixed, and what it broke

Fixed: contract 0.25 → 5.00, grounding 4.00 → 5.00, every structural check green, zero
invented dates.

**Regressed: `uncertainty` 5.0 → 3.0.** On `notice-01`, v2 stopped flagging the unknown
contact person — v1 had it, v2's contract has a slot for `conflicts` but none for "inputs
that are missing or unknown", so the uncertainty fell out of the output. Per-criterion
scoring is the only reason this is visible; a single mean would have reported "v2 is better
everywhere".

That is the next iteration, already specified by the data: **v3 adds an `unknowns` array to
the contract** and a check that every document referencing a missing annex or unnamed
contact surfaces at least one `unknowns` entry.

## Three things the harness itself got wrong on the way

1. **`--max-tokens 8192` truncated 2 of 4 v2 tasks**, which showed up as `json_valid` failures
   — i.e. the report blamed the skill for a token budget. Raising the cap to 16 384 fixed it.
   This is finding #1 in [`DESIGN-NOTES.md`](DESIGN-NOTES.md), reproduced on a second suite.
2. **A check was wrong, not the skill.** `dates_preserved` used literal `must_include` for
   `"2026 年 5 月 20 日"`; v2 wrote `2026-05-20`, which is the same fact in a different
   format. Rewritten as a format-tolerant `regex_all` (`2026\s*[-/年]\s*0?5\s*[-/月]\s*20`).
   A suite that only ever fails the other arm is usually measuring its own assumptions.
3. **Run-to-run variance is real.** Same suite, same skill, temperature 0: v1's check pass
   rate was **0.48 / 0.52 / 0.59** across three runs. Treat sub-0.1 differences between two
   arms as noise unless the suite is bigger or the run is repeated.

## Reproduce

```bash
python -m skilleval validate --suite suites/doc-to-actions \
  --skill skills/doc-to-actions/v1 --skill skills/doc-to-actions/v2

python -m skilleval run --suite suites/doc-to-actions \
  --skill skills/doc-to-actions/v1 --skill skills/doc-to-actions/v2 \
  --model deepseek-flash --max-tokens 16384 \
  --baseline baseline.doc-to-actions.json --max-regression 0.0
```
