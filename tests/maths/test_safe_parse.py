"""Tests for the sandboxed expression parser shared by both transforms.

sympy.parse_expr/sympify routes through eval() internally — safety comes
from what's exposed to it (empty __builtins__, a curated global_dict of
sympy functions, only declared variables in local_dict), not from sympy
itself. These tests cover both the prefilter/complexity-cap layer and the
underlying sandboxing.
"""
from __future__ import annotations

import sympy
import pytest

from moonstar_physics.maths._safe_parse import UnsafeExpressionError, safe_parse_expr


def test_parses_polynomial():
    expr = safe_parse_expr("x**2 + 2*x + 1", ["x"])
    assert expr.equals(sympy.parse_expr("(x + 1)**2"))


def test_parses_trig_functions():
    expr = safe_parse_expr("sin(x)**2 + cos(x)**2", ["x"])
    x = sympy.Symbol("x")
    assert sympy.simplify(expr - 1) == 0


def test_empty_string_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("", ["x"])


def test_non_string_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr(None, ["x"])  # type: ignore[arg-type]


def test_oversized_string_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("x + " * 200, ["x"])


def test_dunder_injection_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("__import__('os').system('echo hi')", [])


def test_import_keyword_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("import os", [])


def test_lambda_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("lambda: 1", [])


def test_semicolon_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("x; os.system('echo hi')", ["x"])


def test_malformed_syntax_rejected():
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("x +* 1", ["x"])


def test_undeclared_builtin_name_has_no_python_meaning():
    # "open" isn't a declared variable and isn't in the safe function set,
    # so it becomes an opaque sympy Symbol — never Python's builtin open().
    expr = safe_parse_expr("open + 1", [])
    assert isinstance(expr, sympy.Basic)
    assert sympy.Symbol("open") in expr.free_symbols


def test_over_complexity_expression_rejected():
    # Build a deliberately deep expression exceeding the 200-op cap.
    terms = " + ".join(f"x**{i}" for i in range(1, 250))
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr(terms, ["x"])


def test_function_call_notation_rejected_not_crashed():
    # A name immediately followed by "(...)" (e.g. an LLM writing physics
    # notation like "v(y, t)") makes sympy's parser attempt
    # Function('v')(y, t) — but "Function" is deliberately absent from the
    # sandboxed globals, so plain eval() raises NameError. This must degrade
    # to the same UnsafeExpressionError every other rejection path uses,
    # never propagate as an uncaught NameError that crashes the caller.
    with pytest.raises(UnsafeExpressionError):
        safe_parse_expr("v(y, t)", ["y", "t"])
