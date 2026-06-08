# tools\calculator_tools.py
import ast
import operator
from typing import Any, Dict

from core.tool_registry import register_tool


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError("不支持的运算符")
        return _ALLOWED_OPERATORS[op_type](_safe_eval(node.left), _safe_eval(node.right))

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _ALLOWED_OPERATORS:
            raise ValueError("不支持的一元运算")
        return _ALLOWED_OPERATORS[op_type](_safe_eval(node.operand))

    raise ValueError("表达式不安全或不支持")


@register_tool(
    name="calculate",
    description="安全计算数学表达式，例如 2*(3+4) 或 10/2。",
    parameters={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "要计算的数学表达式"}
        },
        "required": ["expression"],
    },
)
def calculate(expression: str) -> Dict:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return {
            "success": True,
            "content": str(result),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "content": "",
            "error": f"计算失败：{exc}",
        }