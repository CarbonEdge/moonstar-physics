"""P4.3 acceptance: run residual diagnostics over the failing corpus candidates (< 10 s, non-empty for >= 80 %)."""
import json
import pathlib
import time

import yaml

from moonstar_physics import construct_residuals as cr
from moonstar_physics.construct_spec import load_construct_spec

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = {"mhd": "constructs/analytic-3d-mhd-equilibrium.yaml", "axisym": "constructs/axisymmetric-mhd-equilibrium.yaml"}


def main() -> None:
    exp = yaml.safe_load((ROOT / "tests/corpus/expected.yaml").read_text(encoding="utf-8"))
    n = ok = 0
    worst = 0.0
    for name, e in exp.items():
        if e["verdict"] == "CONSTRUCTED":
            continue
        spec = load_construct_spec(ROOT / SPECS[e["spec"]])
        cand = json.loads((ROOT / f"tests/corpus/{name}.json").read_text(encoding="utf-8"))
        gates = [c.id for c in spec.criteria if c.check in cr.GATE_CHECKS]
        t = time.time()
        d = cr.diagnose_gate_failures(spec, cand, gates)
        dt = time.time() - t
        worst = max(worst, dt)
        n += 1
        ok += bool(d)
        print(f"{name:45s} {e['verdict']:10s} {dt:5.1f}s  {sorted(d)}")
    print(f"non-empty {ok}/{n}; slowest {worst:.1f}s")


if __name__ == "__main__":
    main()
