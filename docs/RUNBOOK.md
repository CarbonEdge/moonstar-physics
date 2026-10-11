# moonstar-physics construct pipeline - runbook

## Start the gateway (moonstar-rs)
```bash
cd moonstar-rs
set -a && . ./.env && set +a            # exports OPENROUTER_API_KEY (harness.sh does NOT find it otherwise)
bash scripts/harness.sh serve            # gateway + worker, background (needs the moonstar-rs-db container)
export MOONSTAR_AUTH_TOKEN=$(bash scripts/harness.sh token | tail -1)
curl -s -H "Authorization: Bearer $MOONSTAR_AUTH_TOKEN" localhost:8000/whoami   # expect tenant_id/user_id
```
- `harness.sh token` prints docker/cargo noise first: take the **last** line.
- Access-denied from `/whoami` = stale token: mint a new one (every `token` call rotates it).
- Stop: `bash scripts/harness.sh stop`.

## Run
```bash
cd moonstar-physics
python scripts/run_construct.py constructs/<spec>.yaml [--max-rounds N] [--candidates K] [--models pipelines/models.X.json]
```
Specs: `analytic-3d-mhd-equilibrium` (hard), `axisymmetric-mhd-equilibrium` (known-answer control),
`beltrami-force-free`, `euler-invariant-surfaces`, `harmonic-nonlinear`.
- `--candidates K` (2-6): candidates per round, generated `CONSTRUCT_MAX_CONCURRENT` at a time (default 2).
  Gateway limits (moonstar-rs `config.rs`, env vars): `MAX_GLOBAL_TRANSFORMS` (20), `MAX_SESSION_PARALLELISM` (4),
  `OPENROUTER_MAX_INFLIGHT` (20). The old "~2 LLM transforms at once" was provider pace, not a gateway cap;
  raise `CONSTRUCT_MAX_CONCURRENT` only after measuring wallclock and error rate.
- `MODEL_REPAIR` in the models file: that model does every Derive call in repair rounds (rounds >= 2).
- Results: `runs/<slug>/<session>.json`. Exit code 0 only for CONSTRUCTED.

## Read a result
1. Verdict is computed by code; CONSTRUCTED never means novel or proven.
2. Read the **candidates**, not just verdicts: `rounds[i].artifacts` -> `Generator_A.response`, `criteria_a` (met/unmet/unverified + evidence).
   A degenerate family (z-independent screw pinch, constant B) can pass gates - every new one becomes a `tests/corpus` entry.
3. `must_still_pass` / `regressions` in the next round's Derive input show what the repair kept or broke; `residual_diagnostics` shows residuals at 5 labelled points and `(curl B) x B` vs `grad p`.
4. Cost: `cost_is_exact` true only if every call reported OpenRouter `usage.cost`; otherwise the figure is a price-table estimate.

## Benchmarks
```bash
python scripts/bench_construct.py <spec> --tag <tag> --n 10 --max-rounds 5 [--candidates K] [--models ...]
python scripts/bench_report.py constructs/_bench/<date>-<tag>      # rebuild summary.md from raw JSON
```
One live run at a time. N < 10 prints a warning - do not claim a difference from it. Raw JSON stays untracked; commit `summary.md` and one replay fixture under `tests/corpus/runs/`.

## Known failure modes
| Symptom | Cause / action |
|---|---|
| `transform_failed` on every LLM call | `OPENROUTER_API_KEY` not exported before `harness.sh serve` - stop, export, restart |
| 16-24k tokens, empty content | hidden reasoning ate the budget - `reasoning: {enabled: false}` on that node (already set for DeepSeek) |
| round fails after 3 gateway retries (~20 min each) | provider returned an undecodable body; the orchestrator retries once, then keeps completed rounds (`stop_reason: round_failed`) |
| zombie sessions after Ctrl-C | cancel via moonstar-rs `/sessions/{id}`; the bench runner records a crashed run as failed |
| iota criteria all `unverified` | sandbox image not built (`scripts/build_sandbox_image.sh`) or the trace could not be trusted - read `iota_*` artifact `detail` |
| a candidate is NOT_FOUND with `candidate rejected` | unsafe/unparseable expression or unresolved symbol (only x, y, z and the spec's degrees of freedom are allowed) |
