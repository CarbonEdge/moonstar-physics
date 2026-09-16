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
python -c "
import asyncio, json
from moonstar_physics.numerical_experiment_transform import NumericalExperimentTransform
from moonstar_physics._compat import SessionContext

code = 'print(\"RESULT: {\\\"ok\\\": true}\")'
input_ = {'experiment_codegen_a': {'response': json.dumps({'code': code})}}
result = asyncio.run(NumericalExperimentTransform(input_, {}, SessionContext()))
print(result)
"
```
Expected output: `{'ran': True, 'result': {'ok': True}, ...}`.

## Usage

```bash
export MOONSTAR_AUTH_TOKEN=<token>  # from `python -m moonstar_gateway.cli seed-user`
python scripts/test_hypothesis.py "could a muon decay into an electron and a photon?"
```

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
