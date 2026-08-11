from __future__ import annotations

import ast
import math
import operator
import re
from collections.abc import Callable, Mapping
from typing import Any

MAX_EXPRESSION_LENGTH = 2_000
MAX_AST_NODES = 500
MAX_CALL_ARGUMENTS = 16
MAX_INTEGER_DIGITS = 1_000
MAX_ABS_LITERAL_EXPONENT = 10_000
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class InputError(ValueError):
    """User-correctable input error safe to return through MCP."""


def validate_identifier(name: str, *, label: str = "identifier") -> str:
    if not IDENTIFIER.fullmatch(name) or name.startswith("__"):
        raise InputError(
            f"Invalid {label} {name!r}; use 1-64 ASCII letters, digits, or underscores, "
            "starting with a letter."
        )
    return name


def normalize_expression(expression: str) -> str:
    if not isinstance(expression, str):
        raise InputError("Expression must be a string.")
    expression = expression.strip()
    if not expression:
        raise InputError("Expression cannot be empty.")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise InputError(f"Expression exceeds {MAX_EXPRESSION_LENGTH} characters.")
    if "\x00" in expression:
        raise InputError("Expression contains a null byte.")
    # Mathematical prompts commonly use ^ for exponentiation. Python reserves it for XOR.
    return expression.replace("^", "**")


def split_equation(equation: str) -> tuple[str, str]:
    normalized = normalize_expression(equation)
    if any(token in normalized for token in ("==", "<=", ">=", "!=")):
        raise InputError("Use one '=' to separate the left and right sides of an equation.")
    pieces = normalized.split("=")
    if len(pieces) == 1:
        return pieces[0], "0"
    if len(pieces) != 2 or not all(piece.strip() for piece in pieces):
        raise InputError("Equation must contain at most one '=' with expressions on both sides.")
    return pieces[0].strip(), pieces[1].strip()


class SafeEvaluator(ast.NodeVisitor):
    """Evaluate a small expression language without Python eval or attribute access."""

    _binary_operators: Mapping[type[ast.operator], Callable[[Any, Any], Any]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_operators: Mapping[type[ast.unaryop], Callable[[Any], Any]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(
        self,
        expression: str,
        *,
        names: Mapping[str, Any],
        functions: Mapping[str, Callable[..., Any]],
        literal_factory: Callable[[str, int | float], Any] | None = None,
        unknown_name: Callable[[str], Any] | None = None,
    ) -> None:
        self.expression = normalize_expression(expression)
        self.names = names
        self.functions = functions
        self.literal_factory = literal_factory or (lambda _source, value: value)
        self.unknown_name = unknown_name
        try:
            self.tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as exc:
            raise InputError(f"Invalid expression syntax: {exc.msg}.") from None
        if sum(1 for _ in ast.walk(self.tree)) > MAX_AST_NODES:
            raise InputError(f"Expression exceeds the {MAX_AST_NODES}-node complexity limit.")

    def evaluate(self) -> Any:
        return self.visit(self.tree)

    def generic_visit(self, node: ast.AST) -> Any:
        raise InputError(f"Unsupported syntax: {type(node).__name__}.")

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InputError("Only real numeric literals are allowed; use I for sqrt(-1).")
        if isinstance(value, int) and len(str(abs(value))) > MAX_INTEGER_DIGITS:
            raise InputError(f"Integer literal exceeds {MAX_INTEGER_DIGITS} digits.")
        if isinstance(value, float) and not math.isfinite(value):
            raise InputError("Numeric literals must be finite.")
        source = ast.get_source_segment(self.expression, node) or repr(value)
        return self.literal_factory(source, value)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("__"):
            raise InputError("Private or dunder names are forbidden.")
        if node.id in self.names:
            return self.names[node.id]
        if self.unknown_name is not None:
            validate_identifier(node.id, label="symbol")
            return self.unknown_name(node.id)
        raise InputError(f"Unknown name {node.id!r}; provide it in variables.")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        operation = self._binary_operators.get(type(node.op))
        if operation is None:
            raise InputError(f"Unsupported operator: {type(node.op).__name__}.")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Pow):
            try:
                numeric_exponent = float(right)
            except (TypeError, ValueError, OverflowError):
                numeric_exponent = None
            if (
                numeric_exponent is not None
                and math.isfinite(numeric_exponent)
                and abs(numeric_exponent) > MAX_ABS_LITERAL_EXPONENT
            ):
                raise InputError(f"Literal exponent exceeds ±{MAX_ABS_LITERAL_EXPONENT}.")
        try:
            return operation(left, right)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise InputError(f"Invalid arithmetic operation: {exc}.") from None

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operation = self._unary_operators.get(type(node.op))
        if operation is None:
            raise InputError(f"Unsupported unary operator: {type(node.op).__name__}.")
        return operation(self.visit(node.operand))

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise InputError("Only direct calls to documented mathematical functions are allowed.")
        if node.keywords:
            raise InputError("Keyword arguments are not supported in mathematical expressions.")
        function = self.functions.get(node.func.id)
        if function is None:
            raise InputError(f"Unknown or forbidden function {node.func.id!r}.")
        if len(node.args) > MAX_CALL_ARGUMENTS:
            raise InputError(f"A function call may have at most {MAX_CALL_ARGUMENTS} arguments.")
        arguments = [self.visit(argument) for argument in node.args]
        try:
            return function(*arguments)
        except InputError:
            raise
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise InputError(f"Invalid call to {node.func.id}: {exc}.") from None


def safe_evaluate(
    expression: str,
    *,
    names: Mapping[str, Any],
    functions: Mapping[str, Callable[..., Any]],
    literal_factory: Callable[[str, int | float], Any] | None = None,
    unknown_name: Callable[[str], Any] | None = None,
) -> Any:
    return SafeEvaluator(
        expression,
        names=names,
        functions=functions,
        literal_factory=literal_factory,
        unknown_name=unknown_name,
    ).evaluate()
