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

| Type | What it does |
|---|---|
| `ConservationLawCheckTransform` | Charge, baryon number, per-flavor lepton number (exact, via sympy.Rational), and a rest-mass-energy threshold check |
| `QMCalculationTransform` | Closed-form energy-level/uncertainty calculations for infinite well, harmonic oscillator, hydrogen-like levels |
| `ReferenceDataLookupTransform` | Looks up particle properties from the bundled `data/particles.json` |
| `DimensionConsistencyTransform` | Checks fiber-bundle total-space dimensions and Spin(n) spinor representation dimensions against closed-form formulas |

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
on `PATH`, optional — enables `review.pdf` export for upload to ScienceOpen;
skipped with a warning if absent.

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
Writes `reviews/geometric-unity/review.md` (+ `review.pdf` if `pandoc` is
installed) and `reviews/geometric-unity/review_data.json`.

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
