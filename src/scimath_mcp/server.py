from __future__ import annotations

from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from scimath_mcp import __version__
from scimath_mcp.isolation import ComputationError, run_isolated
from scimath_mcp.models import MathResult, Measurement

SERVER_INSTRUCTIONS = (
    "Mandatory numerical policy: use this server for every non-trivial numeric, symbolic, "
    "unit, statistical, matrix, uncertainty, or physical-constant result. Do not perform "
    "arithmetic mentally. Preserve the user's units and significant figures, pass explicit "
    "variables, inspect warnings, and report both exact and approximate results when returned. "
    "Reject incompatible dimensions instead of guessing. Tools are read-only and local. "
    "Expressions allow explicit + - * / % ** (^ is accepted as power), direct documented "
    "function calls, pi/e/I, and no Python code or attribute access."
)

mcp = MCPServer(
    name="scimath",
    title="SciMath — verified scientific computing",
    description=(
        "Secure local scientific computation for engineering and science: exact arithmetic, "
        "units, equations, calculus, matrices, statistics, uncertainties, and constants."
    ),
    instructions=SERVER_INSTRUCTIONS,
    version=__version__,
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

Scalar = int | float | str
Matrix = list[list[Scalar]]


def _result(operation: str, payload: dict, *, timeout: float | None = None) -> MathResult:
    try:
        return MathResult.model_validate(run_isolated(operation, payload, timeout=timeout))
    except ComputationError as exc:
        raise ToolError(str(exc)) from None


@mcp.tool(annotations=READ_ONLY)
def calculate(
    expression: str,
    variables: dict[str, Scalar] | None = None,
    precision: int = 30,
    angle_unit: Literal["radians", "degrees"] = "radians",
    output_unit: str | None = None,
) -> MathResult:
    """Evaluate one arithmetic/scientific expression safely. Use explicit `*` and variables;
    variable strings may carry units (for example `12.4 kN*m`). Returns exact and high-precision
    numeric forms when unitless. Set output_unit for dimensional engineering calculations."""
    return _result(
        "calculate",
        {
            "expression": expression,
            "variables": variables or {},
            "precision": precision,
            "angle_unit": angle_unit,
            "output_unit": output_unit,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def convert_units(value: str, to_unit: str, precision: int = 15) -> MathResult:
    """Convert a dimensionful value such as `32 degF`, `120 km/hour`, or `5 psi` to a compatible
    target unit. Dimensional mismatches are errors rather than guessed conversions."""
    return _result(
        "convert_units",
        {"value": value, "to_unit": to_unit, "precision": precision},
    )


@mcp.tool(annotations=READ_ONLY)
def solve(
    equations: list[str],
    variables: list[str],
    domain: Literal["real", "complex"] = "real",
    precision: int = 30,
) -> MathResult:
    """Solve up to eight algebraic equations for explicitly named variables. Each equation may
    use `left = right` or a zero-valued expression. Returns every solution in exact and numerical
    form; choose the real or complex domain explicitly."""
    return _result(
        "solve",
        {
            "equations": equations,
            "variables": variables,
            "domain": domain,
            "precision": precision,
        },
        timeout=30,
    )


@mcp.tool(annotations=READ_ONLY)
def calculus(
    operation: Literal["differentiate", "integrate", "limit", "series"],
    expression: str,
    variable: str = "x",
    order: int = 1,
    lower_bound: str | None = None,
    upper_bound: str | None = None,
    point: str | None = None,
    direction: Literal["+", "-", "+-"] = "+-",
    precision: int = 30,
) -> MathResult:
    """Differentiate, integrate, take a limit, or expand a series symbolically. For definite
    integrals provide both bounds; for limits and series provide point. `order` selects derivative
    order or the number of series terms."""
    return _result(
        "calculus",
        {
            "operation": operation,
            "expression": expression,
            "variable": variable,
            "order": order,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "point": point,
            "direction": direction,
            "precision": precision,
        },
        timeout=30,
    )


@mcp.tool(annotations=READ_ONLY)
def linear_algebra(
    operation: Literal[
        "determinant",
        "inverse",
        "solve",
        "multiply",
        "transpose",
        "rank",
        "rref",
        "eigenvalues",
        "eigenvectors",
        "norm",
        "condition_number",
    ],
    matrix: Matrix,
    other_matrix: Matrix | None = None,
    precision: int = 20,
) -> MathResult:
    """Perform exact matrix and linear-algebra operations on matrices up to 25x25. Supply
    other_matrix for multiplication or as the right-hand side of solve. String entries such as
    `1/3` preserve exact values. Condition-number results include numerical-stability warnings."""
    return _result(
        "linear_algebra",
        {
            "operation": operation,
            "matrix": matrix,
            "other_matrix": other_matrix,
            "precision": precision,
        },
        timeout=30,
    )


@mcp.tool(annotations=READ_ONLY)
def statistics(
    operation: Literal[
        "describe",
        "correlation",
        "linear_regression",
        "confidence_interval_mean",
        "t_test_independent",
    ],
    data: list[float],
    data_y: list[float] | None = None,
    confidence: float = 0.95,
    precision: int = 15,
) -> MathResult:
    """Compute descriptive statistics, Pearson correlation, linear regression, a Student-t
    confidence interval for a mean, or an independent Welch t-test. Provide data_y for paired
    correlation/regression or the second t-test sample."""
    return _result(
        "statistics",
        {
            "operation": operation,
            "data": data,
            "data_y": data_y,
            "confidence": confidence,
            "precision": precision,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def propagate_uncertainty(
    expression: str,
    measurements: dict[str, Measurement],
    output_unit: str | None = None,
    coverage_factor: float = 2.0,
    angle_unit: Literal["radians", "degrees"] = "radians",
    precision: int = 15,
) -> MathResult:
    """Propagate independent standard uncertainties through an expression. Each measurement has
    value, uncertainty, and optional unit. Returns nominal value, standard uncertainty, relative
    uncertainty, and a coverage interval; use output_unit when the result is dimensionful."""
    return _result(
        "propagate_uncertainty",
        {
            "expression": expression,
            "measurements": {
                name: measurement.model_dump(mode="json")
                for name, measurement in measurements.items()
            },
            "output_unit": output_unit,
            "coverage_factor": coverage_factor,
            "angle_unit": angle_unit,
            "precision": precision,
        },
    )


@mcp.tool(annotations=READ_ONLY)
def physical_constant(
    query: str,
    output_unit: str | None = None,
    precision: int = 15,
) -> MathResult:
    """Look up a physical constant from SciPy's bundled CODATA table by common alias or name.
    Returns its value, unit, standard uncertainty, source metadata, and an optional compatible
    unit conversion. Examples: c, G, hbar, Boltzmann constant, electron mass."""
    return _result(
        "physical_constant",
        {"query": query, "output_unit": output_unit, "precision": precision},
    )


@mcp.resource(
    "scimath://guide",
    name="scimath_guide",
    title="SciMath expression and reliability guide",
    description="Compact syntax, tool-selection, and reliability guidance for SciMath.",
    mime_type="text/markdown",
)
def guide() -> str:
    return """# SciMath guide

- Delegate every non-trivial calculation; do not mentally recompute tool output.
- `calculate` handles arithmetic and unit-aware formulas. Put units in variable values.
- Use explicit multiplication (`2*x`) and `**` or `^` for powers.
- Supported common functions include sqrt, exp, ln/log, log10, trigonometry, hyperbolic
  functions, factorial, gamma, erf, floor/ceil, min/max, and complex `I` in unitless mode.
- Use `solve`, `calculus`, `linear_algebra`, and `statistics` for their explicit domains.
- Check every `warnings` field. A numerically correct answer can still reflect a wrong formula,
  unit convention, domain, branch, or statistical model.
- For reportable measurements, use `propagate_uncertainty`; its inputs are assumed independent.
"""


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
