"""Component-wise Cartesian vector calculus over sympy scalar expressions,
plus a whitelisted evaluator for spec criterion expressions such as
``cross(curl(B), B) - grad(p)``.

Vectors are 3-tuples of scalar sympy ``Expr``. No CoordSys3D. The
evaluator walks a Python AST and allows only numbers, known names,
unary minus, + - * / and calls to grad/div/curl/dot/cross — never eval.
"""
from __future__ import annotations

import ast
from typing import Any

import sympy

COORDS = sympy.symbols("x y z")
Vec = tuple[sympy.Expr, sympy.Expr, sympy.Expr]


class CriterionExprError(ValueError):
    """Raised when a criterion expression is invalid, disallowed, or ill-typed."""


def grad(f: sympy.Expr) -> Vec:
    return tuple(sympy.diff(f, c) for c in COORDS)  # type: ignore[return-value]


def div(F: Vec) -> sympy.Expr:
    return sum(sympy.diff(F[i], COORDS[i]) for i in range(3))


def curl(F: Vec) -> Vec:
    x, y, z = COORDS
    return (
        sympy.diff(F[2], y) - sympy.diff(F[1], z),
        sympy.diff(F[0], z) - sympy.diff(F[2], x),
        sympy.diff(F[1], x) - sympy.diff(F[0], y),
    )


def dot(a: Vec, b: Vec) -> sympy.Expr:
    return sum(a[i] * b[i] for i in range(3))


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _is_vec(v: Any) -> bool:
    return isinstance(v, tuple)


def _scalar(v: Any, fn: str) -> sympy.Expr:
    if _is_vec(v):
        raise CriterionExprError(f"{fn}() needs a scalar argument, got a vector")
    return v


def _vector(v: Any, fn: str) -> Vec:
    if not _is_vec(v):
        raise CriterionExprError(f"{fn}() needs a vector argument, got a scalar")
    return v


_FUNCS = {
    "grad": (1, lambda a: grad(_scalar(a[0], "grad"))),
    "div": (1, lambda a: div(_vector(a[0], "div"))),
    "curl": (1, lambda a: curl(_vector(a[0], "curl"))),
    "dot": (2, lambda a: dot(_vector(a[0], "dot"), _vector(a[1], "dot"))),
    "cross": (2, lambda a: cross(_vector(a[0], "cross"), _vector(a[1], "cross"))),
}


def _binop(op: ast.operator, a: Any, b: Any) -> Any:
    if isinstance(op, (ast.Add, ast.Sub)):
        sign = 1 if isinstance(op, ast.Add) else -1
        if _is_vec(a) and _is_vec(b):
            return tuple(a[i] + sign * b[i] for i in range(3))
        if not _is_vec(a) and not _is_vec(b):
            return a + sign * b
        raise CriterionExprError("cannot add or subtract a vector and a scalar")
    if isinstance(op, ast.Mult):
        if _is_vec(a) and _is_vec(b):
            raise CriterionExprError("use dot()/cross() for vector products, not '*'")
        if _is_vec(a):
            return tuple(c * b for c in a)
        if _is_vec(b):
            return tuple(a * c for c in b)
        return a * b
    if isinstance(op, ast.Div):
        if _is_vec(b):
            raise CriterionExprError("cannot divide by a vector")
        if _is_vec(a):
            return tuple(c / b for c in a)
        return a / b
    raise CriterionExprError(f"unsupported operator {type(op).__name__}")


def _eval(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return sympy.sympify(node.value)
        raise CriterionExprError(f"unsupported constant {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise CriterionExprError(f"unknown name {node.id!r}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _eval(node.operand, env)
        return tuple(-c for c in v) if _is_vec(v) else -v
    if isinstance(node, ast.BinOp):
        return _binop(node.op, _eval(node.left, env), _eval(node.right, env))
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in _FUNCS) or node.keywords:
            raise CriterionExprError("only grad/div/curl/dot/cross may be called")
        arity, fn = _FUNCS[node.func.id]
        if len(node.args) != arity:
            raise CriterionExprError(f"{node.func.id}() takes {arity} argument(s)")
        return fn([_eval(a, env) for a in node.args])
    raise CriterionExprError(f"unsupported syntax: {type(node).__name__}")


def evaluate_expr(text: str, env: dict[str, Any]) -> Any:
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise CriterionExprError(f"invalid expression {text!r}: {e}") from e
    return _eval(tree, env)


def residual_components(value: Any) -> list[sympy.Expr]:
    return list(value) if _is_vec(value) else [value]