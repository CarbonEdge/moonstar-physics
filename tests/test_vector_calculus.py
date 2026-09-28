"""Tests for component-wise vector calculus and the whitelisted criterion evaluator."""
from __future__ import annotations

import pytest
import sympy

from moonstar_physics.vector_calculus import (
    COORDS,
    CriterionExprError,
    cross,
    curl,
    div,
    dot,
    evaluate_expr,
    grad,
    residual_components,
)

x, y, z = COORDS


def _simp(vec):
    return tuple(sympy.simplify(c) for c in vec)


def test_grad():
    assert _simp(grad(x**2 + y * z)) == (2 * x, z, y)


def test_div():
    assert sympy.simplify(div((x, y, z))) == 3


def test_curl_of_rotation_field():
    assert _simp(curl((-y, x, sympy.Integer(0)))) == (0, 0, 2)


def test_curl_of_gradient_is_zero():
    f = x**2 * y + sympy.sin(z)
    assert _simp(curl(grad(f))) == (0, 0, 0)


def test_dot_and_cross():
    a = (sympy.Integer(1), sympy.Integer(0), sympy.Integer(0))
    b = (sympy.Integer(0), sympy.Integer(1), sympy.Integer(0))
    assert dot(a, b) == 0
    assert cross(a, b) == (0, 0, 1)


def test_evaluate_force_balance_expression_zero_for_known_solution():
    # B = (-y, x, 0): curl B = (0,0,2); curl B x B = (-2x, -2y, 0) = grad(1 - x^2 - y^2)
    B = (-y, x, sympy.Integer(0))
    p = 1 - x**2 - y**2
    value = evaluate_expr("cross(curl(B), B) - grad(p)", {"B": B, "p": p})
    assert all(sympy.simplify(c) == 0 for c in residual_components(value))


def test_evaluate_scalar_expression_and_numbers():
    value = evaluate_expr("2*div(B) - 6", {"B": (x, y, z)})
    assert sympy.simplify(value) == 0
    assert residual_components(value) == [value]


def test_negation_and_scalar_times_vector():
    value = evaluate_expr("-2*grad(p)", {"p": x})
    assert value == (-2, 0, 0)


@pytest.mark.parametrize(
    "text",
    [
        "__import__('os').system('x')",
        "B.x",
        "lambda: 1",
        "open('f')",
        "B[0]",
        "eval('1')",
        "unknown(B)",
        "B**2",
        "",
        "div(",
    ],
)
def test_disallowed_or_invalid_syntax_rejected(text):
    with pytest.raises(CriterionExprError):
        evaluate_expr(text, {"B": (x, y, z)})


def test_unknown_name_rejected():
    with pytest.raises(CriterionExprError, match="Q"):
        evaluate_expr("div(Q)", {"B": (x, y, z)})


def test_type_errors_rejected():
    env = {"B": (x, y, z), "p": x}
    for text in ("div(p)", "grad(B)", "B + p", "B * B", "p / B", "dot(B, p)"):
        with pytest.raises(CriterionExprError):
            evaluate_expr(text, env)