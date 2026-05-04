#!/usr/bin/env python3
"""Safe arithmetic calculator for deterministic extraction math.

This strict skill variant requires the helper to run inside worker_sandbox.py.
"""

from __future__ import annotations

import argparse
import ast
import math
import operator
import os
import sys
from typing import Any, Callable


def _assert_sandbox() -> None:
    if os.environ.get("CFST_SANDBOX") != "1":
        print(
            "[FAIL] This script must run inside worker_sandbox.py (CFST_SANDBOX=1 not set).",
            file=sys.stderr,
        )
        raise SystemExit(1)


ALLOWED_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _round_func(value: float, ndigits: float | None = None) -> float:
    if ndigits is None:
        return float(round(value))
    if not float(ndigits).is_integer():
        raise ValueError("round() digits must be an integer.")
    return float(round(value, int(ndigits)))


def _pow_func(base: float, exponent: float) -> float:
    return float(pow(base, exponent))


ALLOWED_FUNCS: dict[str, Callable[..., Any]] = {
    "abs": abs,
    "min": min,
    "max": max,
    "pow": _pow_func,
    "round": _round_func,
    "floor": math.floor,
    "ceil": math.ceil,
    "sqrt": math.sqrt,
    "hypot": math.hypot,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "degrees": math.degrees,
    "radians": math.radians,
}


def _as_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{context} must be numeric, got {type(value).__name__}.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{context} is not finite.")
    return result


def _parse_vars(items: list[str]) -> dict[str, float]:
    variables: dict[str, float] = {}
    for raw in items:
        if "=" not in raw:
            raise ValueError(f"Invalid --var '{raw}', expected key=value.")
        key, value = raw.split("=", 1)
        name = key.strip()
        if not name.isidentifier():
            raise ValueError(f"Invalid variable name '{name}'.")
        if name in CONSTANTS or name in ALLOWED_FUNCS:
            raise ValueError(f"Variable name '{name}' is reserved.")
        try:
            parsed_value = float(value.strip())
        except ValueError as exc:
            raise ValueError(f"Variable '{name}' value must be numeric.") from exc
        variables[name] = _as_number(parsed_value, f"Variable '{name}'")
    return variables


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return _as_number(node.value, "Literal")
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.Name):
        if node.id in variables:
            return _as_number(variables[node.id], f"Variable '{node.id}'")
        if node.id in CONSTANTS:
            return _as_number(CONSTANTS[node.id], f"Constant '{node.id}'")
        raise ValueError(f"Unknown variable or constant: {node.id}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_BIN_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        return _as_number(ALLOWED_BIN_OPS[op_type](left, right), op_type.__name__)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_UNARY_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _eval_node(node.operand, variables)
        return _as_number(ALLOWED_UNARY_OPS[op_type](operand), op_type.__name__)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct function names are supported, for example sqrt(x).")
        func_name = node.func.id
        if func_name not in ALLOWED_FUNCS:
            raise ValueError(f"Unsupported function: {func_name}. Run --help for supported functions.")
        if node.keywords:
            raise ValueError("Keyword arguments are not supported.")
        args = [_eval_node(arg, variables) for arg in node.args]
        try:
            value = ALLOWED_FUNCS[func_name](*args)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise ValueError(f"{func_name}() failed: {exc}") from exc
        return _as_number(value, f"{func_name}() result")

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


def safe_eval(expression: str, variables: dict[str, float]) -> float:
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression syntax: {exc}") from exc
    return _eval_node(tree.body, variables)


def main() -> int:
    _assert_sandbox()
    parser = argparse.ArgumentParser(
        description="Evaluate one safe engineering arithmetic expression. Requires CFST_SANDBOX=1.",
        epilog="""Examples:
  safe_calc.py --round 3 '211 / 2'
  safe_calc.py --round 3 'sqrt(120**2 + 90**2)'
  safe_calc.py --var ex=120 --var ey=90 --round 3 'hypot(ex, ey)'

Operators: + - * / ** % //, parentheses, unary +/-
Constants: pi e tau
Functions: abs min max pow round floor ceil sqrt hypot log log10 exp
           sin cos tan asin acos atan atan2 degrees radians

Use direct function names such as sqrt(x), not math.sqrt(x). Quote expressions
in the shell; use ** for powers, not ^.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "expression",
        help='Expression to evaluate, for example "141.4 / 2" or "hypot(ex, ey)".',
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        help="Variable assignment in key=value form, repeatable.",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        dest="round_digits",
        help="Optional decimal rounding digits, for example --round 3.",
    )
    args = parser.parse_args()

    try:
        variables = _parse_vars(args.var)
        result = safe_eval(args.expression, variables)
        if args.round_digits is not None:
            result = round(result, args.round_digits)
        print(result)
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
