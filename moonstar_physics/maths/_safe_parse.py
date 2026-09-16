"""Sandboxed sympy expression parsing shared by IdentityCheckTransform and
the sequence_formula/diophantine conjecture checkers — one parser, one
security surface, never reimplemented.

sympy.parse_expr/sympify routes through eval() internally. Safety comes
from what's exposed to that eval(), not from sympy itself:
  - global_dict is a curated, closed set of sympy names (no builtins at
    all — explicitly setting "__builtins__": {} blocks Python's default
    behavior of injecting the real builtins into a bare eval namespace).
  - local_dict contains only the variable names the caller declares.
  - Any other bare name in the expression becomes an opaque sympy Symbol
    (via parse_expr's auto_symbol transformation) — never a Python name
    lookup, so it can't resolve to anything callable.

A string prefilter and a post-parse complexity cap are belt-and-suspenders
on top of that, and also give a bounded amount of work before `simplify`
is ever called downstream (see Task 3) — there's no cross-platform way to
put a wall-clock timeout on a CPU-bound sympy call (signal.alarm doesn't
work on Windows), so complexity is capped instead.
"""
from __future__ import annotations

import re
from typing import Any

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

_MAX_EXPR_LENGTH = 500
_MAX_OP_COUNT = 200
_FORBIDDEN_PATTERN = re.compile(r"__|import|lambda|exec|eval|;")

_SAFE_GLOBALS: dict[str, Any] = {
    "__builtins__": {},
    "pi": sympy.pi,
    "E": sympy.E,
    "I": sympy.I,
    "oo": sympy.oo,
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "asin": sympy.asin,
    "acos": sympy.acos,
    "atan": sympy.atan,
    "sinh": sympy.sinh,
    "cosh": sympy.cosh,
    "tanh": sympy.tanh,
    "exp": sympy.exp,
    "log": sympy.log,
    "sqrt": sympy.sqrt,
    "Abs": sympy.Abs,
    "factorial": sympy.factorial,
    "Rational": sympy.Rational,
    "Integer": sympy.Integer,
    "Symbol": sympy.Symbol,
    "Float": sympy.Float,
}


class UnsafeExpressionError(ValueError):
    """Raised when an expression string fails the prefilter, length, parse, or complexity checks."""


def safe_parse_expr(text: str, variables: list[str]) -> sympy.Expr:
    if not isinstance(text, str) or not text.strip():
        raise UnsafeExpressionError("expression is empty or not a string")
    if len(text) > _MAX_EXPR_LENGTH:
        raise UnsafeExpressionError(f"expression exceeds {_MAX_EXPR_LENGTH} characters")
    if _FORBIDDEN_PATTERN.search(text):
        raise UnsafeExpressionError("expression contains a disallowed token")

    local_dict = {name: sympy.Symbol(name) for name in variables}
    global_dict = dict(_SAFE_GLOBALS)

    try:
        expr = parse_expr(
            text,
            local_dict=local_dict,
            global_dict=global_dict,
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, ValueError, AttributeError, KeyError) as e:
        raise UnsafeExpressionError(f"failed to parse expression: {e}") from e

    if not isinstance(expr, sympy.Basic):
        raise UnsafeExpressionError("parsed result is not a sympy expression")

    if sympy.count_ops(expr) > _MAX_OP_COUNT:
        raise UnsafeExpressionError(f"expression exceeds complexity cap ({_MAX_OP_COUNT} ops)")

    return expr
