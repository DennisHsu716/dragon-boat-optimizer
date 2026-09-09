from __future__ import annotations

import ast
import operator
from typing import Dict, Optional

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class FormulaError(ValueError):
    pass


def safe_eval(expr: str, variables: Dict[str, Optional[float]]) -> float:
    """
    Evaluate a restricted arithmetic expression.
    Only numeric constants, named variables, +-*/%** and unary +- are allowed.
    No calls, attributes, subscripts, comparisons, or names outside `variables`.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Invalid formula syntax: {e}") from e

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise FormulaError("Only numeric constants are allowed.")

        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise FormulaError(f"Unknown variable: {node.id}")
            value = variables[node.id]
            if value is None:
                raise FormulaError(f"Variable '{node.id}' has no value for this row.")
            return value

        if isinstance(node, ast.BinOp):
            op_func = _ALLOWED_BINOPS.get(type(node.op))
            if op_func is None:
                raise FormulaError(f"Operator not allowed: {type(node.op).__name__}")
            return op_func(_eval(node.left), _eval(node.right))

        if isinstance(node, ast.UnaryOp):
            op_func = _ALLOWED_UNARYOPS.get(type(node.op))
            if op_func is None:
                raise FormulaError(f"Operator not allowed: {type(node.op).__name__}")
            return op_func(_eval(node.operand))

        raise FormulaError(f"Expression not allowed: {type(node).__name__}")

    return float(_eval(tree))
