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

## Usage

```bash
export MOONSTAR_AUTH_TOKEN=<token>  # from `python -m moonstar_gateway.cli seed-user`
python scripts/test_hypothesis.py "could a muon decay into an electron and a photon?"
```

## Testing

```bash
python -m pytest tests/ -q
```

## Scope

v1 covers: charge/baryon/lepton-flavor conservation, four closed-form QM
systems, and a curated ~16-particle reference dataset. Out of scope (see
the design spec at `../docs/superpowers/specs/2026-07-02-moonstar-physics-design.md`
in the Moonstar-Workbench root): QuTiP-based multi-particle/entanglement
systems, live external data, Studio UI wiring, and
Standard-Model-suppression-vs-hard-violation classification.
