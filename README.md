# moonstar-physics

Moonstar transform package for testing natural-language hypotheses about
quantum particles against conservation laws, closed-form QM calculations,
and a bundled reference dataset — then getting a conversational verdict
via the `physics_hypothesis.yaml` pipeline.

Standalone repository — sibling to `moonstar/` and `moonstar-crypto/` in the
Moonstar-Workbench. Not imported by either; it plugs into the shared Python
environment as a `moonstar.transforms` entry-point provider, the same way
`moonstar-codesearch` does from inside the `moonstar` monorepo.

## Install

```bash
cd moonstar-physics
pip install -e .
```

Install this **before** starting the `moonstar` gateway worker (in the
sibling `moonstar/` repo) — transform types are resolved via
`importlib.metadata` entry points at worker startup, in whatever environment
the worker runs in.

## Transforms

`moonstar-maths` (a former standalone sibling repo for symbolic-math
claims) was merged into this package on 2026-09-16 rather than fixed
standalone — see
`docs/superpowers/specs/2026-09-16-moonstar-physics-proof-verification-design.md`
in the workspace root for why. Its transforms now live under
`moonstar_physics/maths/`.

| Type | What it does |
|---|---|
| `ConservationLawCheckTransform` | Charge, baryon number, per-flavor lepton number (exact, via sympy.Rational), and a rest-mass-energy threshold check |
| `QMCalculationTransform` | Closed-form energy-level/uncertainty calculations for infinite well, harmonic oscillator, hydrogen-like levels |
| `ReferenceDataLookupTransform` | Looks up particle properties from the bundled `data/particles.json` |
| `DimensionConsistencyTransform` | Checks fiber-bundle total-space dimensions and Spin(n) spinor representation dimensions against closed-form formulas |
| `IdentityCheckTransform` | Verifies a claimed `lhs == rhs` identity via `sympy.simplify`, with numeric sampling to avoid false positives when simplify can't reduce a true identity to exactly 0. Merged in from the retired `moonstar-maths` repo. |
| `ConjectureCheckTransform` | Fixed dispatch table: primality (`sympy.isprime`), bounded diophantine search (≤2 variables), closed-form sequence-formula evaluation. Merged in from `moonstar-maths`; not wired into any pipeline yet. |

## Proof-paper review (algebra + numerical evidence)

For PDE/proof-style papers (not particle-physics/QM claims), set
`review_pipeline: proof_algebra` in `papers/<slug>.yaml` — see
`papers/navier-stokes.yaml` for a real example. This routes through
`pipelines/proof_hypothesis.yaml`, which checks hand-transcribed
algebraic sub-claims symbolically via sympy instead of trying to
evaluate the whole theorem. Each hypothesis's prose must state its
equations explicitly, including substituting in any named quantity's
definition (e.g. write "(1/2 + h) + (1/2 - h) = 1", not "A + D = 1"
after separately defining A and D) — the Extractor is instructed to do
this substitution itself, but a curator who states it explicitly gets
more reliable results.

### Numerical evidence (opt-in, `numerical_evidence: true`)

Also setting `numerical_evidence: true` (only meaningful alongside
`review_pipeline: proof_algebra`) additionally runs an automated,
**unsupervised** numerical-evidence stage per hypothesis: an LLM derives
a numerically tractable reduction of the claim (e.g. a self-similar
profile ODE) **twice, independently**, writes a numpy/scipy script for
each, and runs both in an isolated Docker container. An evidence critic
only treats the result as usable if both independent derivations agree
and both sandbox runs succeed and agree with each other — any
disagreement reports `INCONCLUSIVE` rather than picking a side.

**Before using this:**
- Build the sandbox image once: `bash scripts/build_sandbox_image.sh`
  (rebuild only if `moonstar_physics/docker/experiment-runner/Dockerfile`
  changes — not rebuilt automatically per run).
- Docker must be running and on `PATH`.
- This roughly triples the LLM cost per hypothesis versus Phase 1 alone
  (two independent derivation + codegen calls, one evidence critique)
  plus container spin-up latency — `proof_hypothesis_numerical.yaml`'s
  budget is `max_usd: 3.00` / `max_wallclock_seconds: 600` per hypothesis.
- **Nothing here is proof.** Numerical evidence only ever corroborates or
  contradicts the symbolic algebra check — it can never by itself flip a
  verdict to PLAUSIBLE, and it is inherently unreliable for
  singularity/blowup phenomena (an under-resolved grid can mimic real
  blowup). Every derivation, generated script, and raw sandbox
  stdout/exit code is persisted to `reviews/<slug>/runs/<session_id>.json`
  regardless of outcome — read it before trusting a PLAUSIBLE verdict
  that leaned on numerical corroboration.
- The sandbox itself is isolated (`--network none`, capped memory/CPU/
  pids, read-only filesystem, wall-clock timeout) but this still executes
  LLM-generated code completely unsupervised — treat `numerical_evidence`
  as a deliberate, higher-risk opt-in per paper, not a default.

### Manual end-to-end sandbox test (not part of the default test suite)

```bash
bash scripts/build_sandbox_image.sh
python3 << 'PYEOF'
import asyncio, json
from moonstar_physics.numerical_experiment_transform import NumericalExperimentTransform
from moonstar_physics._compat import SessionContext

code = 'print(\'RESULT: {"ok": true}\')'
input_ = {'experiment_codegen_a': {'response': json.dumps({'code': code})}}
result = asyncio.run(NumericalExperimentTransform(input_, {}, SessionContext()))
print(result)
PYEOF
```
Expected output: `{'ran': True, 'result': {'ok': True}, ...}`.

## Usage

```bash
export MOONSTAR_AUTH_TOKEN=<token>  # from `python -m moonstar_gateway.cli seed-user`
python scripts/test_hypothesis.py "could a muon decay into an electron and a photon?"
```

## Construct checker (Phase 1 of the construct pipeline)

Checks a candidate closed-form object (B, psi, p as strings) against a
`constructs/<slug>.yaml` spec's acceptance criteria --- no LLM, no gateway:

```bash
python scripts/check_construct_candidate.py constructs/analytic-3d-mhd-equilibrium.yaml \
    tests/fixtures/iota2_candidate.json
```

Prints `VERDICT: CONSTRUCTED | PARTIAL | NOT_FOUND` and a met / unmet /
unverified checklist. Numeric evidence only (random in-domain points,
tolerance 1e-8) --- not proof, not a novelty claim. Criteria needing the
Phase 2 sandbox templates (e.g. `iota_nonzero`) report `unverified`.
See `docs/superpowers/specs/2026-09-28-moonstar-physics-construct-pipeline-design.md`
in the workspace root.

## Construct pipeline (Phase 3: repair loop)

Up to `max_rounds` rounds. Each round: Planner -> per candidate (concurrent)
**Derive** (v4-pro, long reasoning) -> **Formalise** (flash, strict JSON) ->
deterministic checks + sandboxed field-line trace -> checklist. After a round
that is not CONSTRUCTED, the best candidate so far and its evidence are fed
back for a minimal repair (round n checks with seed n). The critic / devil's
advocate / synthesizer run once, on the best candidate, if it is not
NOT_FOUND. The verdict is computed by code.

Needs:
- the moonstar-rs gateway **built from a version whose `LlmTransform` supports
  the optional `timeout_seconds` and `reasoning` config** (moonstar-rs master,
  commits 09ebe11 + 430619c - rebuild the gateway binary if yours predates it;
  without it every reasoning call over 180 s fails with "error decoding
  response body"). `bash scripts/harness.sh` there, with `OPENROUTER_API_KEY`
  exported. If `harness.sh token` says "Access is denied", the running
  gateway is locking the binary it wants to rebuild: `harness.sh stop`,
  `cargo build -p moonstar-gateway-bin`, then `serve` again.
- Docker running, and the sandbox image (`bash scripts/build_sandbox_image.sh`).

```bash
MOONSTAR_AUTH_TOKEN=<token> python scripts/run_construct.py     constructs/analytic-3d-mhd-equilibrium.yaml [--max-rounds 3]
```

Expect ~15-50 minutes per round (Derive is ~10+ minutes; candidates run
concurrently) and cents of spend per round (see the printed cost; prices in
`pipelines/prices.json`). Prints `VERDICT: CONSTRUCTED | PARTIAL | NOT_FOUND`,
the checklist, per-round verdicts, cost and token usage, and saves the full
run - every round's candidates, filled iota scripts, sandbox stdout,
checklists - to `constructs/<slug>/runs/<session_id>.json`.

Reading a result:
- The top-level verdict is the BEST round's, not the last. `stop_reason` is one
  of `constructed`, `max_rounds`, `max_usd`, `wallclock`, `round_failed`.
- `NOT_FOUND` means a *gate* criterion (div B / B.grad psi / force balance) was
  unmet; the checklist still shows which other criteria passed. The iota trace
  is skipped when the gate fails (its rows are `unverified`).
- Iota is judged on every seed surface (magnetic shear makes them differ).
- A candidate whose generation fails is `NOT_FOUND` on its own (`error` field
  in its `criteria_*` artifact); the run fails only if both do.
- Numeric evidence only: `CONSTRUCTED` is not novelty and not proof.

Known limits: the checker requires objects B, psi, p (so a second spec must be
in the same object family, e.g. `constructs/axisymmetric-mhd-equilibrium.yaml`,
a known-answer control); `max_usd` is checked at round boundaries only; cost
counts successful calls only; Derive steps can exhaust their token budget on
reasoning (v4-pro) and return nothing.

## Paper Reviews

Publishes AI-tested reviews of physics papers to a GitHub Pages site under
`docs/` — each paper gets a curated hypothesis list run through
`physics_hypothesis.yaml`, plus an LLM-generated summary of the paper
itself (map-reduce over the extracted PDF text).

**Prerequisites:** `pdftotext` (poppler-utils) on `PATH`, required. `pandoc`
plus the `typst` PDF engine on `PATH`, optional (`scoop install pandoc
typst` on Windows) — enable `review.pdf` export; skipped with a warning if
either is absent. Before your first real submission, fill in your ORCID iD
in `scienceopen_author.json` (repo root, committed — an ORCID is a public
identifier, not a secret).

**Define a paper** — `papers/<slug>.yaml`:
```yaml
title: "..."
authors: ["..."]
draft_date: "YYYY-MM-DD"   # optional
pdf: "papers/pdfs/<slug>.pdf"
source_url: null            # optional
hypotheses:
  - "A specific, testable claim from the paper."
```

**Publish one paper's review:**
```bash
export MOONSTAR_AUTH_TOKEN=<token>  # from `python -m moonstar_gateway.cli seed-user`
python scripts/publish_review.py geometric-unity
```
Writes `reviews/geometric-unity/review.md` (with Abstract, Paper Summary,
Methodology, Tested Hypotheses, Evidence, and References sections),
`reviews/geometric-unity/review.pdf` (if `pandoc`+`typst` are installed),
`reviews/geometric-unity/review_data.json`, and
`reviews/geometric-unity/scienceopen_metadata.json` — a copy-paste-ready
submission title, abstract, author/ORCID block, and reference list for
manually submitting the review through ScienceOpen's upload form at
https://www.scienceopen.com/collection/5916e67c-0edf-472a-ad8e-6e205a4e080d.
Submission itself stays a manual step — nothing here talks to ScienceOpen's
API.

**Rebuild the site** (after publishing any paper(s)):
```bash
python scripts/build_site.py
```
Renders `docs/index.html` and `docs/reviews/<slug>.html` from every
`reviews/*/review_data.json`. Commit and push `docs/` to publish — GitHub
Pages is configured to serve `main` / `/docs`.
```

## Testing

```bash
python -m pytest tests/ -q
```

## Scope

v1 covers: charge/baryon/lepton-flavor conservation, four closed-form QM
systems, a curated ~16-particle reference dataset, and dimension-consistency
checks for fiber-bundle and Spin(n) spinor-representation claims (see
`../docs/superpowers/specs/2026-07-04-physics-dimension-consistency-design.md`
in the Moonstar-Workbench root). Out of scope (see the original design spec
at `../docs/superpowers/specs/2026-07-02-moonstar-physics-design.md`):
QuTiP-based multi-particle/entanglement systems, live external data, Studio
UI wiring, Standard-Model-suppression-vs-hard-violation classification,
gauge-anomaly-cancellation arithmetic, and any general Lie-theory or
proof-checking engine.

## Evaluation harness and adversarial corpus (P4.0)

Measure before tuning. No model/prompt/parameter change counts as an improvement without these.

- **Corpus:** `tests/corpus/*.json` + `tests/corpus/expected.yaml` - real, degenerate and synthetic
  candidates, each with the verdict a *correct* checker must give and a written reason.
  `tests/test_corpus_verdicts.py` replays them (no LLM, no Docker) and only lets known-genuine
  candidates be CONSTRUCTED. Add every new degenerate family you see here.
- **Replay / diagnose:** `moonstar_physics.construct_replay.replay_candidate(spec, candidate)` runs the
  deterministic pipeline on one candidate. `python scripts/diagnose_residuals.py [run.json ...]`
  classifies every candidate in saved runs (`ok` / `scale` / `localised` / `wrong` / `undefined`).
- **Bench:** `python scripts/bench_construct.py <spec> --tag <tag> --n 5 [--max-rounds R] [--models PATH]`
  runs the config N times sequentially (one live run at a time) into
  `constructs/_bench/<date>-<tag>/`; `python scripts/bench_report.py <dir>` rebuilds `summary.md`.
  Commit `summary.md` only; raw run JSON is git-ignored. **All costs are provisional** (token x
  price table; the gateway reports 0.0) and N < 10 prints a warning; read the Wilson intervals.

