## What changed

<!-- One paragraph. Which skill version moved, which checks moved with it. -->

## Evidence

- [ ] `python -m unittest discover -s tests -t .` passes (offline)
- [ ] `python -m skilleval validate --suite <suite> --skill <v1> --skill <v2>` passes
- [ ] Offline gate still passes: `--runner mock --baseline examples/baseline.mock.json`
- [ ] Report attached if a live model run changed a verdict

| arm | check pass | judge mean | tokens in/out |
| --- | --- | --- | --- |
| before | | | |
| after | | | |

## Honesty box

- [ ] Any new number in the README/report came from a real run, and the command that
      produced it is in the PR description.
- [ ] Truncated runs are labelled as truncated, not averaged into a skill's score.
- [ ] No prices, model names, or capabilities are asserted that were not verified on the
      endpoint actually used.
