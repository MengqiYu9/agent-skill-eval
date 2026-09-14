# Design notes: what actually broke while building and running this

Written from real runs of the bundled suite, not from theory. Every number below is in
`examples/` — reproduce it with the commands in the README.

## 1. A reasoning model spends your `max_tokens` before it writes a word

**Symptom.** With `--max-tokens 2048`, the strict skill version returned an *empty*
content field on 2 of 4 tasks. The harness recorded that as "no answer", the judge scored
every criterion 0, and the report claimed the **better** skill was worse: v2 = judge
1.62 vs v1 = 3.31, check pass 0.50 vs 0.38 (`examples/report-live-2048-truncated.md`).

**Cause.** The model emitted thousands of reasoning tokens, hit the cap, and never
produced an answer (`finish_reason=length`, `content=""`). Reasoning tokens count against
the same budget as the answer. At `--max-tokens 4096` one task still truncated with
10,743 reasoning characters.

**Fix in this repo.** `Completion.truncated` is derived from `finish_reason`, empty
content becomes a *named* error (`empty_content_error()`), the summary carries a
truncation count and a warning line, and each task row has a `finish` column. A cap
problem now looks like a cap problem.

**Rule.** A harness that swallows `finish_reason` will eventually report a token-budget
failure as a quality regression.

## 2. The judge is more generous than the contract — run both, or you will ship a broken skill

Clean run, same model for worker and judge, `--max-tokens 8192`
(`examples/report-live-8192.md`):

| | check pass | judge mean | tokens (in/out) | mean latency |
| --- | --- | --- | --- | --- |
| `structured-digest/v1` (loose prose) | **0.38** (9/24) | **3.19** | 1 508 / 4 871 | 5.68 s |
| `structured-digest/v2` (strict JSON contract) | **0.96** (23/24) | **4.56** | 2 648 / 12 490 | 12.15 s |

v1 produced fluent, readable Markdown that scored 3.0–3.75 on every task — and failed
`json_valid`, `contract_paths` and `cites_sources` on **all four**. **Judge-only
evaluation would have called it acceptable.** The contract checks are what make it
unusable downstream, and they cost nothing to run.

The price of the strict version is visible too: **2.4× the tokens and 2.1× the latency**
for +58% check pass rate. That is the trade-off to argue about in review, and it is a
number, not an opinion.

## 3. Per-criterion scores move in opposite directions — a single scalar would hide it

Judge means per criterion, v1 → v2:

| criterion | v1 | v2 |
| --- | --- | --- |
| `format_contract` | 0.00 | **5.00** |
| `actionability` | 3.00 | 3.75 |
| `uncertainty` | 4.00 | 4.00 |
| `readability` | 5.00 | 5.00 |
| `grounding` | **5.00** | 4.75 |

The strict contract bought format compliance and cost a little grounding — the judge's
notes name the two places v2 inferred beyond the material ("补训安排", "整改无凭证可查").
Averaging these into one score would have reported "improved" and buried the regression
that the next skill edit should target.

## 4. A prompt contract does not fix a failure mode by itself

`no_offtopic` fails in **both** arms on `digest-02`: the material contains an unrelated
reimbursement line, and v2 quoted it anyway despite a 1800-character budget and an
explicit "only what is in the material" rule. The check is what catches it; the prompt
did not. Keep negative checks for the failure you are actually protecting against, and
expect the fix to be a prompt change *verified by the suite*, not assumed.

## 5. Mock fixtures are not a nice-to-have

The gate has to run on every PR, including from people with no API key. `--runner mock`
replays committed fixtures (`examples/mock_outputs.json`, `examples/baseline.mock.json`),
so the runner wiring, check engine, aggregation and report rendering are all exercised
offline and deterministically — v1 = 0.375, v2 = 1.000. Model cost stays in one explicit
command. This is why `tests/` never needs network access.

## 6. What is deliberately *not* here

- **No aggregate "quality score".** Averaging a contract violation against a style
  preference produces a number that moves when the task mix changes, not when the skill
  does.
- **No cost column by default.** Tokens are measured; prices are someone else's
  configurable fact, so they live in `--prices prices.json` and print `n/a` otherwise.
- **No hidden retries.** A failed call is a result: it is reported with its error text.
  Retrying inside the runner is how a flaky eval becomes a green eval.
- **No "improved" without a baseline.** Meaning comes from `--baseline` diffs against a
  previous run of the same suite, not from an absolute score.
