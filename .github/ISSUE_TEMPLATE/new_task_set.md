---
name: New task set
about: Propose a suite for a skill you actually use
labels: task-set
---

The unit of contribution here is **a task set**, not a feature. A good task set is small,
boring to read, and catches a failure you have seen happen.

## The skill under test

- Name / where it lives:
- What it is supposed to guarantee:
- Have you actually shipped a change to it? What broke? <!-- if nothing ever broke, the
  suite is probably not worth writing yet -->

## The tasks

| id | input (1 line) | the failure it protects against |
| --- | --- | --- |
| | | |

## The checks

For each failure above, the deterministic check that catches it
(`json_path`, `regex_none`, `must_not_include`, …). If a failure can only be caught by a
judge, say why a regex cannot express it.

## Evidence plan

- [ ] Inputs are **synthetic** — no customer text, no internal documents, nothing that
      cannot be committed publicly.
- [ ] I have a `vN` that fails at least one check and a `vN+1` that passes, so the suite
      can be shown to discriminate. <!-- a suite everything passes is a smoke test, not a gate -->
- [ ] Report attached (markdown) from a real run.
