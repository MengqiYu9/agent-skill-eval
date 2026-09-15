# v2.1.0 release and migration

## What changed

v2.1.0 hardens the regression gate and adds experimental native CLI runners.
It is an intentional version jump from the repository's 0.1.0 package version;
the historical skill versions v1/v2 are separate from the package version.

- Execution errors, truncated answers, missing baselines and invalid judge scores cannot PASS.
- Judge responses require every rubric criterion, integer scores in [0, 5] and complete JSON.
  The entire task input and output are sent to the judge.
- Incomplete worker attempts are excluded from quality aggregates and still block the gate.
- Baseline schema 2 stores task/config/skill fingerprints and per-task/check/judge scores.
  Every rate comparison uses the configured tolerance; judge scores are normalized to [0, 1].
- Repeats execute independent attempts and preserve per-attempt evidence.
- Strict JSON rejects prose wrappers, duplicate keys and non-finite constants.
  JSON Schema uses Draft 2020-12 with format validation and no remote references.
- Costs include worker and judge usage with separate model prices.
  Native missing usage or unsupported cache pricing produces unknown cost, never a free run.
- A new doc-to-actions/v2.1 skill and six synthetic edge cases cover empty/short documents,
  missing dates, non-obligation background, injected instructions and long-input tail evidence.
- The existing skills and historical live reports remain unchanged.

## Gate behavior and exit codes

0 = PASS; 1 = quality/budget regression; 2 = execution or comparison error.
Errors take precedence over score thresholds. With no baseline or --compare-first,
the default check floor is 1.0. Use --fail-under explicitly for a different policy.
A run with --no-judge does not execute a judge; generation itself is not deterministic.
When judging is enabled, tasks without a rubric skip judging. --judge-fail-under
requires a rubric on every task and a valid judge score for every attempt.

task_pass_rate is retained as the mean per-task check fraction for compatibility.
task_success_rate is the fraction of scored attempts passing every check.
scored_tasks and tasks expose incomplete attempts instead of hiding them.

## Baseline migration

New baselines are accepted from reviewed PASS reports:

```bash
skilleval run --suite tasks --skill skills/structured-digest/v2 \
  --runner mock --mock-outputs examples/mock_outputs.json --no-judge --out reports
skilleval accept-baseline --report reports/report-<id>.json --out baseline.local.json
```

Replacing an accepted baseline is explicit: add --replace to accept-baseline.
The compatibility --save-baseline option creates a new file only, never overwrites,
and never saves a failed run.

Compare a new version with an explicitly selected older baseline entry:

```bash
skilleval run --suite my-suite --skill skills/my-skill/v2.1 \
  --baseline baseline.local.json --baseline-skill my-skill/v2
```

Missing entries, changed task/check coverage or different suite/config fingerprints
return ERROR. Regenerate and review a baseline when intentionally changing the suite,
model, runtime version, generation/judge configuration, repeats or execution settings.
Do not copy fingerprints between unrelated runs.

Historical v1 baseline files remain available as evidence. --allow-legacy-baseline
is required to compare them, and the report warns that suite/config identity is unverifiable.
The new examples/baseline.mock.v2.1.json was generated from recorded fixtures, not a model run.

## Native platforms (experimental)

Native adapters install the full skill package in a fresh temporary work directory:
Codex: .agents/skills; Claude: .claude/skills; Gemini: .gemini/skills; Cursor: .cursor/skills.

```bash
skilleval run --runner codex --suite suites/doc-to-actions-v2.1 \
  --skill skills/doc-to-actions/v2.1 --no-judge --timeout 180
skilleval run --runner claude --suite suites/doc-to-actions-v2.1 \
  --skill skills/doc-to-actions/v2.1 --no-judge
skilleval run --runner gemini --suite suites/doc-to-actions-v2.1 \
  --skill skills/doc-to-actions/v2.1 --no-judge
skilleval run --runner cursor --suite suites/doc-to-actions-v2.1 \
  --skill skills/doc-to-actions/v2.1 --no-judge
```

Install/authenticate the selected CLI first. Use --agent-command for an executable path;
Cursor defaults to agent. --model is optional for native runs and uses the platform default
when omitted. Extra arguments use --agent-arg=VALUE. Native execution retains platform
permission settings; the harness does not add bypass-approval flags.
Windows batch shims (.cmd/.bat) are rejected; use a native executable wrapper or run in WSL.
No model names, prices or cross-platform quality improvements are claimed by this release.

--invocation explicit asks the agent to use the installed named skill. implicit sends only
the task. --no-skill prepends an unskilled control; --compare-first gates later arms against
the first. Run controls in a clean CI image: platform user configuration and authentication
are inherited, so a temporary directory alone does not remove globally installed skills.
It is also not an OS security boundary. Pin the CLI/model/configuration and isolate untrusted
tasks in a CI container. Runtime version, arguments and observed usage are recorded.
Automatic activation is not inferred from a good final answer; inspect recorded events.
Gemini JSON mode retains the final envelope and statistics, not a complete tool trace.

Native judging uses a separate API worker: supply --judge-model and the API endpoint/key,
or --no-judge. The native platform model and API judge are distinct configurations.

Tasks can supply text files and assert requested text artifacts:

```yaml
tasks:
  - id: artifact-example
    input: Read input.txt and write result.json containing {"ok": true}.
    files:
      input.txt: "Synthetic input."
    checks:
      - id: result
        artifact: result.json
        type: json_schema
        schema:
          type: object
          required: [ok]
          properties:
            ok: {const: true}
          additionalProperties: false
```

Only named artifacts (up to 2 MB each) are collected; symlink/path escapes fail.
JSON reports retain raw native events where available. Treat reports as task data and
review them before publishing. Native token/cost metadata differs by provider.

## CI

The default matrix runs offline harness tests on Python 3.9, 3.11 and 3.12.
Mock regression checks validate the harness and assertions, not prompt behavior.
Set repository variable ENABLE_LIVE_EVAL=true plus SKILLEVAL_API_KEY and endpoint/model
variables to enable real behavior evaluation on pushes, trusted same-repository PR heads,
and manual runs. Missing required credentials then fail explicitly.
Fork PR code is never run with repository secrets. There is no pull_request_target job.

The live suite uses the historical digest baseline with explicit legacy compatibility
and runs the v2.1 edge suite three times with check and judge thresholds.
Real runs cost API credits; they were not executed during offline release validation.

## Sources and validation boundary

Adapter commands were checked against official documentation on 2026-09-15:

- https://learn.chatgpt.com/docs/non-interactive-mode
- https://learn.chatgpt.com/docs/build-skills
- https://code.claude.com/docs/en/headless
- https://code.claude.com/docs/en/skills
- https://geminicli.com/docs/cli/headless/
- https://geminicli.com/docs/cli/skills/
- https://cursor.com/docs/cli/reference/output-format
- https://cursor.com/docs/skills

Offline tests cover parser envelopes, subprocess invocation, skill staging, artifact
collection, timeout handling and gate failures. They do not certify authenticated native
platform behavior or prove that a new skill performs better. Historical live measurements
belong to earlier versions; no new live benchmark results are presented.

