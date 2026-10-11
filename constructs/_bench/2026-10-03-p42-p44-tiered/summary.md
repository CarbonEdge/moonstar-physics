# Construct bench: p42-p44-tiered

- date: 2026-10-03
- spec: analytic-3d-mhd-equilibrium
- models: models.tiered-flash-pro.json
- max_rounds: 5
- candidates_per_round: 4
- note: P4.2+P4.3+P4.4: carry-over/regression feedback, residual diagnostics, 4 candidates/round, flash breadth + pro repair
- runs: 10 (10 completed, 0 failed)

## Outcomes

| verdict | runs | 95% Wilson interval |
|---|---|---|
| CONSTRUCTED | 1 / 10 | 2% - 40% |
| PARTIAL | 3 / 10 | 11% - 60% |
| NOT_FOUND | 6 / 10 | 31% - 83% |

- runs whose best candidate reached <= 1 unmet hard criterion: 10 / 10 (72% - 100%)
- min unmet hard criteria (best candidate over all rounds) histogram: {0: 8, 1: 2}
- rounds to first PARTIAL-or-better: min 1.0 / median 3.5 / max 5.0
- regression events per run (best candidate got worse vs previous round): min 0.0 / median 1.0 / max 1.0

## Cost and time

- cost per run, USD, **reported by OpenRouter per call, incl. truncated retries; failed/timed-out calls are not counted**: min 0.146 / median 0.305 / max 0.433
- of which wasted on truncated attempts, USD: min 0.000 / median 0.000 / max 0.002
- elapsed per run, seconds: min 1864 / median 2267 / max 21500

## Runs

| # | status | verdict | rounds | stop | final unmet (best) | min unmet | regressions | cost |
|---|---|---|---|---|---|---|---|---|
| 1 | ok | CONSTRUCTED | 4 | constructed | None | 0 | 0 | $0.146 |
| 2 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 0 | 1 | $0.302 |
| 3 | ok | NOT_FOUND | 5 | max_rounds | None | 0 | 1 | $0.417 |
| 4 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 0 | 1 | $0.433 |
| 5 | ok | PARTIAL | 5 | max_rounds | [] | 0 | 0 | $0.367 |
| 6 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 0 | 1 | $0.243 |
| 7 | ok | NOT_FOUND | 5 | max_rounds | None | 0 | 0 | $0.308 |
| 8 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 1 | 0 | $0.310 |
| 9 | ok | PARTIAL | 3 | wallclock | ['nonaxisym'] | 1 | 1 | $0.167 |
| 10 | ok | PARTIAL | 5 | max_rounds | ['nonaxisym'] | 0 | 1 | $0.300 |
