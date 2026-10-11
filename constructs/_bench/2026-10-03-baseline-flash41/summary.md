# Construct bench: baseline-flash41

- date: 2026-10-03
- spec: analytic-3d-mhd-equilibrium
- models: models.derive-flash41.json
- max_rounds: 5
- note: P4.2/P4.4 combined-gate baseline: code at efc46d8 (pre-P4.1/2/3/4), flash derive
- runs: 10 (10 completed, 0 failed)

## Outcomes

| verdict | runs | 95% Wilson interval |
|---|---|---|
| CONSTRUCTED | 0 / 10 | 0% - 28% |
| PARTIAL | 1 / 10 | 2% - 40% |
| NOT_FOUND | 9 / 10 | 60% - 98% |

- runs whose best candidate reached <= 1 unmet hard criterion: 10 / 10 (72% - 100%)
- min unmet hard criteria (best candidate over all rounds) histogram: {0: 8, 1: 2}
- rounds to first PARTIAL-or-better: min 5.0 / median 5.0 / max 5.0
- regression events per run (best candidate got worse vs previous round): min 0.0 / median 1.0 / max 2.0

## Cost and time

- cost per run, USD, **reported by OpenRouter per call, incl. truncated retries; failed/timed-out calls are not counted**: min 0.029 / median 0.035 / max 0.040
- of which wasted on truncated attempts, USD: min 0.000 / median 0.000 / max 0.004
- elapsed per run, seconds: min 306 / median 451 / max 857

## Runs

| # | status | verdict | rounds | stop | final unmet (best) | min unmet | regressions | cost |
|---|---|---|---|---|---|---|---|---|
| 1 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 2 | $0.034 |
| 2 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 1 | $0.035 |
| 3 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 2 | $0.031 |
| 4 | ok | PARTIAL | 5 | max_rounds | [] | 0 | 1 | $0.040 |
| 5 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 1 | $0.039 |
| 6 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 1 | 1 | $0.029 |
| 7 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 2 | $0.034 |
| 8 | ok | NOT_FOUND | 5 | max_rounds | ['force_balance'] | 1 | 0 | $0.029 |
| 9 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 2 | $0.038 |
| 10 | ok | NOT_FOUND | 5 | max_rounds | [] | 0 | 0 | $0.040 |
