# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- `suites/doc-to-actions/` — a second suite that evaluates a **real-world skill**
  (`document-to-action-items`, the Hermes bundled skill, MIT) on 4 synthetic Chinese
  contract / minutes / notice documents, with 14 distinct checks around citation,
  modality (`应当` / `可以` / `宜`), unresolved owners and cross-clause conflicts.
- `docs/CASE-STUDY-doc-to-actions.md` — the full before/after story with raw numbers,
  including what the improved version still fails.
- `docs/notes/2026-09-14-reasoning-tokens-ate-my-budget.md` — write-up of the failure
  mode where a reasoning model spends `max_tokens` before answering and the harness
  reports it as a quality regression.

### Changed

- `.github/workflows/eval.yml` — the offline job now also `validate`s the second suite
  (no model calls), so a broken task set fails on structure before anyone spends tokens.
- `suites/doc-to-actions/contract-02.yaml` — replaced the literal `must_include` date check
  with format-tolerant regex checks (`2026-05-20` and `2026 年 5 月 20 日` are the same
  fact). The first 16 384-token run failed a correct answer because of it; the case study
  documents both runs.

### Notes

- First live numbers for the real-skill suite: `doc-to-actions/v1` 0.59 check pass /
  3.64 judge vs `v2` 1.00 / 4.88 (1.74× output tokens, 1.53× latency). Same skill, same
  suite, temperature 0, three runs: v1 check pass came out 0.48 / 0.52 / 0.59 — treat
  sub-0.1 arm differences as noise.

## [0.1.0] - 2026-09-14

### Added

- Deterministic check engine: `json_valid`, `json_path`, `must_include`,
  `must_not_include`, `regex_all`, `regex_none`, `max_chars`, `min_chars`, `language`.
  Unknown types and malformed specs fail as checks with their error text.
- Rubric-based LLM judge (JSON-only replies; runner errors and non-JSON replies are
  recorded on the result instead of raising).
- OpenAI-compatible runner over stdlib `urllib` + a mock runner that replays committed
  fixtures, so the gate runs in CI without an API key or spend.
- A/B between two skill versions in one run: per-arm summary, per-check matrix, per-task
  detail, A/B deltas, and failure evidence attached to the report.
- Baseline gating: `--baseline`, `--max-regression`, `--fail-under`, with exit codes
  `0` pass / `1` regression / `2` pipeline error.
- Truncation and empty-content diagnostics: `finish_reason=length` and empty answers are
  reported as token-budget problems, never scored as bad answers.
- CLI: `run`, `validate` (dry run, no model calls), `init` (scaffold a skill version and
  a task template).
- 27 offline unit tests; committed example reports from real runs; `docs/DESIGN-NOTES.md`.
