"""Fixed field-line-trace script template for the construct pipeline's
sandbox-experiment criteria (iota_nonzero / iota_noninteger).

The generator never writes this script. `build_iota_script` fills fixed
placeholders with numpy code *printed by sympy* from already-parsed
expressions, so candidate text can never inject Python into the sandbox.

Method: for each toroidal angle phi = atan2(y, x), the magnetic axis is the
minimiser of psi in the (rho, z) half-plane (specs require psi = 0 on the
axis). A field line is traced with d(rho, z)/d(phi) = rho * (B_rho, B_z) / B_phi
for one toroidal turn from two seed offsets; iota = (unwrapped change in the
meridional angle about the axis) / 2*pi. The script reports `error` — never a
number — when the trace can't be trusted (no zero minimum of psi, B_phi
vanishing, non-finite field, integration failure, psi drift, seed disagreement).
This is numeric evidence, not proof.
"""
from __future__ import annotations

import math
from typing import Sequence

import sympy
from sympy.printing.numpy import NumPyPrinter


class IotaTemplateError(ValueError):
    """The candidate cannot be turned into a trace script."""


_COORDS = {sympy.Symbol("x"), sympy.Symbol("y"), sympy.Symbol("z")}
_RHO_LO = 0.05

_TEMPLATE = '''\
import json
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize

RHO_LO, RHO_HI = @@RHO_LO@@, @@RHO_HI@@
Z_LO, Z_HI = @@Z_LO@@, @@Z_HI@@
SEED_OFFSETS = (0.05, 0.1)
N_STEPS = 200
AXIS_PSI_TOL = 1e-6
PSI_DRIFT_TOL = 1e-4
SEED_AGREEMENT_TOL = 1e-3
BPHI_MIN = 1e-9


def field(x, y, z):
    return (@@BX@@, @@BY@@, @@BZ@@)


def psi(x, y, z):
    return @@PSI@@


def psi_rz(rz, phi):
    v = psi(rz[0] * np.cos(phi), rz[0] * np.sin(phi), rz[1])
    return 1e300 if np.isnan(float(v)) else float(v)


def find_axis(phi, starts):
    best = None
    for start in starts:
        r = minimize(psi_rz, start, args=(phi,), method="Nelder-Mead",
                     options={"xatol": 1e-11, "fatol": 1e-16})
        if best is None or r.fun < best.fun:
            best = r
    return best.x, float(best.fun)


def rhs(phi, u):
    rho, z = u
    bx, by, bz = (float(v) for v in field(rho * np.cos(phi), rho * np.sin(phi), z))
    br = bx * np.cos(phi) + by * np.sin(phi)
    bp = -bx * np.sin(phi) + by * np.cos(phi)
    if not np.isfinite([br, bp, bz]).all():
        raise ValueError("field is not finite along the field line")
    if abs(bp) < BPHI_MIN:
        raise ValueError("toroidal field component vanishes along the field line")
    return [rho * br / bp, rho * bz / bp]


def main():
    starts = [(r, z) for r in np.linspace(RHO_LO, RHO_HI, 8) for z in np.linspace(Z_LO, Z_HI, 5)]
    ax0, psi_min = find_axis(0.0, starts)
    if psi_min > AXIS_PSI_TOL:
        return {"error": "psi has no zero minimum in the meridional plane (min %.3g)" % psi_min}
    phis = np.linspace(0.0, 2 * np.pi, N_STEPS + 1)
    iotas = []
    drift = 0.0
    for off in SEED_OFFSETS:
        u0 = [ax0[0] + off, ax0[1]]
        sol = solve_ivp(rhs, (0.0, 2 * np.pi), u0, t_eval=phis, rtol=1e-10, atol=1e-12)
        if not sol.success:
            return {"error": "field-line integration failed: " + str(sol.message)}
        psi0 = psi_rz(u0, 0.0)
        drift = max(drift, max(abs(psi_rz(sol.y[:, i], sol.t[i]) - psi0) for i in range(len(sol.t))))
        guess = ax0
        theta = []
        for ph, r, z in zip(sol.t, sol.y[0], sol.y[1]):
            guess, _ = find_axis(ph, [guess])
            theta.append(np.arctan2(z - guess[1], r - guess[0]))
        theta = np.unwrap(theta)
        iotas.append(float((theta[-1] - theta[0]) / (2 * np.pi)))
    if drift > PSI_DRIFT_TOL:
        return {"error": "field line does not stay on a psi surface (max psi drift %.3g)" % drift}
    if max(iotas) - min(iotas) > SEED_AGREEMENT_TOL:
        return {"error": "seed offsets disagree on iota: %r" % (iotas,)}
    return {"iota": sum(iotas) / len(iotas), "iota_seeds": iotas,
            "psi_drift": float(drift), "axis_psi_min": psi_min}


if __name__ == "__main__":
    try:
        with np.errstate(all="ignore"):
            out = main()
    except Exception as e:
        out = {"error": "%s: %s" % (type(e).__name__, e)}
    print("RESULT: " + json.dumps(out))
'''


def _code(expr: sympy.Expr) -> str:
    raw = NumPyPrinter().doprint(expr)
    return raw.replace("numpy.", "np.")


def build_iota_script(
    B: Sequence[sympy.Expr],
    psi: sympy.Expr,
    dof_values: dict[str, float],
    sample_box: dict[str, tuple[float, float]],
) -> str:
    if len(B) != 3:
        raise IotaTemplateError("B must have exactly 3 components")
    subs = {sympy.Symbol(name): sympy.Float(value) for name, value in dof_values.items()}
    exprs = [sympy.sympify(e).subs(subs) for e in (*B, psi)]
    for e in exprs:
        extra = e.free_symbols - _COORDS
        if extra:
            raise IotaTemplateError(
                f"expression has unresolved symbol(s) {sorted(str(s) for s in extra)}"
            )
    rho_hi = math.hypot(
        max(abs(v) for v in sample_box["x"]), max(abs(v) for v in sample_box["y"])
    )
    if rho_hi <= _RHO_LO:
        raise IotaTemplateError("sample_box is too small for the meridional search")
    fills = {
        "@@RHO_LO@@": repr(_RHO_LO), "@@RHO_HI@@": repr(float(rho_hi)),
        "@@Z_LO@@": repr(float(sample_box["z"][0])), "@@Z_HI@@": repr(float(sample_box["z"][1])),
        "@@BX@@": _code(exprs[0]), "@@BY@@": _code(exprs[1]), "@@BZ@@": _code(exprs[2]),
        "@@PSI@@": _code(exprs[3]),
    }
    script = _TEMPLATE
    for key, value in fills.items():
        script = script.replace(key, value)
    return script