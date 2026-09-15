# agent-skill-eval v2.1.0

[![eval](https://github.com/MengqiYu9/agent-skill-eval/actions/workflows/eval.yml/badge.svg)](https://github.com/MengqiYu9/agent-skill-eval/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)

**A regression gate for agent skills and prompt versions.** Edit a `SKILL.md`, run the
suite, get a pass/fail verdict and a diff against the last accepted run — in CI, before
the change reaches a user.

> 「我改了一行 SKILL.md，行为坏了没有？」—— 这个仓库就是回答这个问题的。
> 确定性断言 + 评分员双轨、两个版本 A/B、和基线对比，输出可当 PR 门禁的报告。

Editing a prompt is a blind change: nothing fails, nothing warns, and the regression shows
up as "the agent got worse lately". Existing evaluators mostly rank frameworks or models;
this one treats **a skill diff** as the unit under test.

## v2.1.0

Fail-closed regression gates, strict JSON/Schema validation, full-evidence judging,
versioned baselines and experimental Codex / Claude Code / Gemini CLI / Cursor runners.

See [release notes and migration](docs/RELEASE-v2.1.0.md) for breaking behavior,
native CLI setup, baseline promotion and validation limits. The native adapters have
offline contract tests; authenticated platform runs have not been certified.

Quick offline v2.1 skill check:

```bash
pip install -e ".[dev]"
skilleval run --suite suites/doc-to-actions-v2.1 --skill skills/doc-to-actions/v2.1 \
  --runner mock --mock-outputs examples/mock-doc-to-actions-v2.1.json --no-judge
```

The mock validates the harness and assertions. It does not measure prompt improvements.
Without a baseline, the default check floor is 1.0. Missing baselines, incomplete runs
and invalid judges return exit code 2. Old baselines require explicit compatibility mode.

## What it does

- **Two independent signals per task.** Deterministic checks (`json_valid`, `regex_all`,
  `must_not_include`, `max_chars`, `language`, …) that are cheap and stable, plus an
  optional rubric-based **LLM judge** for qualities a regex cannot express.
- **A/B between two skill versions** on the same task set, with per-check and per-task
  breakdowns — not just one mean.
- **Baseline gating.** `--baseline baseline.json --allow-legacy-baseline --max-regression 0.0` exits non-zero when
  a check or the pass rate drops. Suitable as a CI gate.
- **Failure evidence in the report.** Every failed check prints its reason; failing outputs
  are attached, truncated. A red build tells you what to look at.
- **Truncation is a first-class result.** A token-cap problem is reported as a cap problem,
  never as a worse skill (see `docs/DESIGN-NOTES.md`, finding #1).
- **Small Python runtime:** PyYAML for task files and jsonschema for strict contracts.
  The API runner uses standard-library HTTP for compatible Chat Completions endpoints.
  Native CLI runners execute installed agent platforms in fresh work directories.

## Quick start

```bash
git clone <this repo> && cd agent-skill-eval

# 1) offline: no API key, no money. Runs the pipeline, checks and report end to end.
PYTHONPATH=src python -m skilleval run \
  --suite tasks \
  --skill skills/structured-digest/v1 --skill skills/structured-digest/v2 \
  --runner mock --mock-outputs examples/mock_outputs.json --no-judge \
  --baseline examples/baseline.mock.v2.1.json --max-regression 0.0

# 2) dry run: does the suite parse, what will it execute?
PYTHONPATH=src python -m skilleval validate --suite tasks --skill skills/structured-digest/v2

# 3) live, with the judge
export SKILLEVAL_API_KEY=...            # or --env-file path/to/.env
PYTHONPATH=src python -m skilleval run \
  --suite tasks \
  --skill skills/structured-digest/v1 --skill skills/structured-digest/v2 \
  --model deepseek-flash --max-tokens 8192 \
  --baseline baseline.json --allow-legacy-baseline --max-regression 0.0 \
  --out reports

# tests
PYTHONPATH=src python -m unittest discover -s tests -t .     # offline harness and native contract tests
```

Exit codes: `0` pass · `1` regression / below `--fail-under` · `2` pipeline error.
Installable as a package too: `pip install -e .` then `skilleval ...`.

## Historical measurements (before v2.1.0)

Suite: 4 tasks (`tasks/digest-0*.yaml`), 12 distinct checks, 2 skill versions, 24 checks
per arm. Worker and judge both `deepseek-flash`, `--max-tokens 8192`. This is the bundled
demo — the deltas are the point, not the absolute values.

| arm | check pass | judge mean | tokens in/out | mean latency |
| --- | --- | --- | --- | --- |
| `structured-digest/v1` — loose prose instructions | 0.38 (9/24) | 3.19 | 1 508 / 4 871 | 5.68 s |
| `structured-digest/v2` — strict JSON contract + citations | **0.96 (23/24)** | **4.56** | 2 648 / 12 490 | 12.15 s |

- The judge called v1 "readable, well-grounded" on every task; the contract checks failed
  on all four. **Judge-only evaluation would have shipped it.**
- The strict version costs **2.4× tokens and 2.1× latency** for that +58% pass rate.
- Its one remaining failure (`no_offtopic`) is a real leakage the prompt did not fix —
  the check is what catches it.
- Per-criterion, v2 is not better everywhere: `format_contract` 0.00 → 5.00, but
  `grounding` 5.00 → 4.75. Full breakdown in `docs/DESIGN-NOTES.md`.

Raw reports: [`examples/report-live-8192.md`](examples/report-live-8192.md) ·
[offline mock run](examples/report-offline-mock.md) ·
[the truncation run that looked like a regression](examples/report-live-2048-truncated.md).

## Case study: a real shipped skill, not a demo

The suite above is a demo I wrote to exercise the harness. `suites/doc-to-actions/` is the
point of the repo: it evaluates **`document-to-action-items`**, a skill that is actually
shipped and used, on 4 synthetic Chinese contract / minutes / notice documents, then
measures one targeted edit.

| arm | check pass | judge mean | tokens (in/out) | mean latency |
| --- | --- | --- | --- | --- |
| `doc-to-actions/v1` — as shipped | 0.59 (20/34) | 3.64 | 3 119 / 16 285 | 20.33 s |
| `doc-to-actions/v2` — + output contract | **1.00 (34/34)** | **4.88** | 3 547 / 28 407 | 31.06 s |

What came out of it is more interesting than the delta:

- v1's prose extraction is *good* (5.0 on actionability, modality, uncertainty) but it
  specifies no output format, so 0/4 on `json_valid` and 0/4 on `contract_paths`.
- The judge caught what the checks could not: v1 **converted "30 日内" into a concrete date**
  (`2026-04-09`) in one task — precisely what the skill forbids — and softened a genuine
  cross-clause inconsistency instead of flagging it.
- v2 fixed all of that but **lost `uncertainty` 5.0 → 3.0**: its contract had a slot for
  conflicts and none for "unknown inputs". That regression is only visible per-criterion,
  and it defines v3.
- One check was itself wrong: a literal date match failed a correctly reformatted
  `2026-05-20`. Fixed to a format-tolerant regex — a suite that only fails the other arm is
  usually measuring its own assumptions.

Full narrative, including the token-cap truncation that struck this suite too:
[`docs/CASE-STUDY-doc-to-actions.md`](docs/CASE-STUDY-doc-to-actions.md).

## Task format

```yaml
tasks:
  - id: digest-01
    notes: 基础契约：必须是 JSON、必须有溯源、必须压到 1800 字符内
    input: |
      请把以下材料整理成结构化结论。
      === 材料开始 ===
      ...synthetic material goes here...
      === 材料结束 ===
    checks:
      - id: json_valid
        type: json_valid
      - id: cites_sources
        type: regex_all
        pattern: '\[S\d+\]'
        min_matches: 3
      - id: undecided_marked
        type: must_include
        all: ["待确认"]
      - id: no_placeholders
        type: must_not_include
        any: ["TODO", "待补充", "XXX"]
    rubric:
      - id: grounding
        desc: every claim traces back to the material; no outside facts
      - id: actionability
        desc: actions name the actor; unknown owners are marked 未定
```

Use **synthetic material**. A suite that contains real customer data cannot be run in CI,
shared, or published as evidence — write the task so the failure mode is reproducible
without the private text.

## Check types

| type | fields | passes when |
| --- | --- | --- |
| `json_strict` | — | the complete response is valid JSON, with no wrapper, duplicate keys or non-finite constants |
| `json_schema` | `schema: {...}` | strict JSON satisfies Draft 2020-12 schema |
| `json_equals` | `path`, `value` | a dotted path exists and equals the typed value |
| `json_valid` | — | the output contains a parseable JSON object (fenced or bare) |
| `json_path` | `paths: [...]` | every dotted path exists and is non-empty |
| `must_include` | `all: [...]` | all needles present |
| `must_not_include` | `any: [...]` | none of the needles present |
| `regex_all` | `pattern`, `min_matches` | ≥ N **unique** matches |
| `regex_none` | `pattern` | no match |
| `max_chars` / `min_chars` | `value` | length within bound |
| `language` | `value: zh\|en` | CJK / latin ratio within bound |

The CLI validates task/check specifications before model calls. Unknown check types,
invalid schemas, duplicate task/check ids and malformed specs return a pipeline error.
Malformed model output produces failed checks with evidence.

## Repo layout

```
src/skilleval/
  checks.py    deterministic assertions (the CI gate)
  judge.py     rubric judge, JSON-only replies, errors recorded not raised
  runner.py    OpenAI-compatible + mock runners, truncation/empty-content diagnostics
  suite.py     skill + task loading, one run = skill × tasks, aggregation
  report.py    markdown/JSON rendering, baseline diff, regression verdict
  cli.py       run / validate / init
skills/structured-digest/{v1,v2}/SKILL.md   starter example: loose prose → strict contract
tasks/digest-0*.yaml                        starter suite (4 tasks, 12 checks)
skills/doc-to-actions/{v1,v2}/SKILL.md      the real thing: a shipped skill vs its strict version
suites/doc-to-actions/*.yaml                its suite (4 synthetic documents, 14 checks)
tests/                                      offline regression and native contract tests
examples/                                   committed reports + mock fixtures + baseline
docs/DESIGN-NOTES.md                        what broke for real, with numbers
docs/CASE-STUDY-doc-to-actions.md           before/after on a real skill, including what still fails
docs/notes/                                 longer write-ups
```

## Baseline promotion

After reviewing a successful v2 report, accept its candidate baseline:

```bash
skilleval accept-baseline --report reports/report-<id>.json --out baseline.local.json
```

Use `--replace` only for an intentional baseline update. `--save-baseline` is kept as
a create-only shortcut and refuses failed runs and existing paths. For cross-version
comparison, pass one candidate with `--baseline-skill my-skill/v1`. See the migration guide.

## Adding your own

```bash
skilleval init --path . --name my-skill --version v1
# Edit the generated skill and task, then run and review the report.
skilleval run --suite tasks --skill skills/my-skill/v1 --save-baseline baseline.local.json
# After creating v2, explicitly compare it with the accepted v1:
skilleval run --suite tasks --skill skills/my-skill/v2 \
  --baseline baseline.local.json --baseline-skill my-skill/v1
```

## Cost

Worker and judge tokens are reported separately and together per arm; prices are not guessed. Pass
`--prices prices.json` — `{"default": {"input_per_mtok": 0.14, "output_per_mtok": 0.28}}`
— to add a cost column. A 4-task, 2-arm run like the one above is ~22 k tokens total.

## License

MIT.
