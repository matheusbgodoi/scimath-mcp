from __future__ import annotations

import difflib
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import mpmath
import numpy as np
import sympy as sp
from pint import DimensionalityError, Quantity, UnitRegistry
from scipy import constants as scipy_constants
from scipy import stats as scipy_stats
from uncertainties import UFloat, ufloat, umath

from scimath_mcp.models import MathResult, Measurement
from scimath_mcp.safety import InputError, safe_evaluate, split_equation, validate_identifier

MAX_PRECISION = 100
MAX_MATRIX_DIMENSION = 25
MAX_DATA_POINTS = 100_000
MAX_FACTORIAL = 1_000

ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)


def _validate_precision(precision: int) -> int:
    if not 2 <= precision <= MAX_PRECISION:
        raise InputError(f"precision must be between 2 and {MAX_PRECISION} significant digits.")
    return precision


def _format_number(value: Any, precision: int) -> str:
    if isinstance(value, UFloat):
        value = value.nominal_value
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, complex):
        real = mpmath.nstr(value.real, precision)
        imag = mpmath.nstr(abs(value.imag), precision)
        sign = "+" if value.imag >= 0 else "-"
        return f"{real} {sign} {imag}*I"
    try:
        numeric = float(value)
        if not math.isfinite(numeric):
            return str(value)
    except (TypeError, ValueError, OverflowError):
        return str(value)
    if isinstance(value, (float, np.floating)):
        return format(float(value), f".{min(precision, 17)}g")
    return mpmath.nstr(value, precision, strip_zeros=False)


def _sympy_literal(source: str, value: int | float) -> sp.Expr:
    if isinstance(value, int):
        return sp.Integer(value)
    try:
        return sp.Rational(source)
    except (TypeError, ValueError):
        return sp.Float(source)


def _checked_factorial(value: Any) -> Any:
    if getattr(value, "is_number", False):
        if value.is_integer is not True or value.is_nonnegative is not True:
            raise InputError("factorial requires a non-negative integer.")
        if int(value) > MAX_FACTORIAL:
            raise InputError(f"factorial input exceeds {MAX_FACTORIAL}.")
    elif isinstance(value, (int, float)):
        if int(value) != value or value < 0 or value > MAX_FACTORIAL:
            raise InputError(f"factorial requires an integer from 0 through {MAX_FACTORIAL}.")
    return sp.factorial(value)


def _symbolic_functions(angle_unit: str) -> dict[str, Callable[..., Any]]:
    if angle_unit not in {"radians", "degrees"}:
        raise InputError("angle_unit must be 'radians' or 'degrees'.")
    factor = sp.pi / 180 if angle_unit == "degrees" else sp.Integer(1)
    inverse_factor = 180 / sp.pi if angle_unit == "degrees" else sp.Integer(1)
    return {
        "abs": sp.Abs,
        "sqrt": sp.sqrt,
        "cbrt": lambda x: sp.real_root(x, 3),
        "exp": sp.exp,
        "ln": sp.log,
        "log": sp.log,
        "log10": lambda x: sp.log(x, 10),
        "sin": lambda x: sp.sin(x * factor),
        "cos": lambda x: sp.cos(x * factor),
        "tan": lambda x: sp.tan(x * factor),
        "asin": lambda x: sp.asin(x) * inverse_factor,
        "acos": lambda x: sp.acos(x) * inverse_factor,
        "atan": lambda x: sp.atan(x) * inverse_factor,
        "atan2": lambda y, x: sp.atan2(y, x) * inverse_factor,
        "sinh": sp.sinh,
        "cosh": sp.cosh,
        "tanh": sp.tanh,
        "floor": sp.floor,
        "ceil": sp.ceiling,
        "ceiling": sp.ceiling,
        "factorial": _checked_factorial,
        "gamma": sp.gamma,
        "erf": sp.erf,
        "erfc": sp.erfc,
        "sign": sp.sign,
        "min": sp.Min,
        "max": sp.Max,
        "re": sp.re,
        "im": sp.im,
        "conjugate": sp.conjugate,
    }


def _symbolic_names() -> dict[str, Any]:
    return {
        "pi": sp.pi,
        "tau": 2 * sp.pi,
        "e": sp.E,
        "E": sp.E,
        "I": sp.I,
        "phi": sp.GoldenRatio,
        "oo": sp.oo,
    }


def _parse_symbolic(
    expression: str,
    *,
    symbols: dict[str, sp.Symbol] | None = None,
    angle_unit: str = "radians",
    allow_new_symbols: bool = True,
) -> tuple[sp.Expr, dict[str, sp.Symbol]]:
    symbol_table = symbols if symbols is not None else {}

    def symbol_for(name: str) -> sp.Symbol:
        if not allow_new_symbols:
            raise InputError(f"Unknown name {name!r} in a numeric value.")
        return symbol_table.setdefault(name, sp.Symbol(name))

    expression_value = safe_evaluate(
        expression,
        names={**_symbolic_names(), **symbol_table},
        functions=_symbolic_functions(angle_unit),
        literal_factory=_sympy_literal,
        unknown_name=symbol_for,
    )
    return sp.sympify(expression_value), symbol_table


def _numeric_substitution(value: int | float | str) -> sp.Expr:
    if isinstance(value, bool):
        raise InputError("Boolean variable values are not mathematical scalars.")
    if isinstance(value, int):
        return sp.Integer(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InputError("Variable values must be finite.")
        return sp.Rational(str(value))
    parsed, _ = _parse_symbolic(value, allow_new_symbols=False)
    if parsed.free_symbols:
        raise InputError(f"Variable value {value!r} is not numeric.")
    return parsed


def _looks_dimensionful(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return not ureg.Quantity(value).dimensionless
    except Exception:
        return False


def _quantity_value(value: int | float | str) -> Quantity:
    if isinstance(value, bool):
        raise InputError("Boolean variable values are not mathematical scalars.")
    try:
        if isinstance(value, str):
            return ureg.Quantity(value)
        if not math.isfinite(float(value)):
            raise InputError("Variable values must be finite.")
        return ureg.Quantity(value)
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f"Could not parse quantity {value!r}: {exc}.") from None


def _dimensionless_magnitude(value: Any) -> Any:
    if isinstance(value, Quantity):
        try:
            return value.to(ureg.dimensionless).magnitude
        except DimensionalityError:
            raise InputError("This function requires a dimensionless argument.") from None
    return value


def _trig_input(value: Any, angle_unit: str) -> Any:
    if isinstance(value, Quantity):
        try:
            return value.to("radian").magnitude
        except DimensionalityError:
            raise InputError(
                "Trigonometric functions require an angle or dimensionless value."
            ) from None
    return math.radians(value) if angle_unit == "degrees" else value


def _unit_functions(angle_unit: str) -> dict[str, Callable[..., Any]]:
    if angle_unit not in {"radians", "degrees"}:
        raise InputError("angle_unit must be 'radians' or 'degrees'.")

    def inverse(value: Any, function: Callable[[Any], Any]) -> Any:
        result = function(_dimensionless_magnitude(value))
        return math.degrees(result) if angle_unit == "degrees" else result

    return {
        "abs": abs,
        "sqrt": lambda x: x**0.5,
        "cbrt": lambda x: x ** (1 / 3),
        "exp": lambda x: math.exp(_dimensionless_magnitude(x)),
        "ln": lambda x: math.log(_dimensionless_magnitude(x)),
        "log": lambda x, base=math.e: math.log(
            _dimensionless_magnitude(x), _dimensionless_magnitude(base)
        ),
        "log10": lambda x: math.log10(_dimensionless_magnitude(x)),
        "sin": lambda x: math.sin(_trig_input(x, angle_unit)),
        "cos": lambda x: math.cos(_trig_input(x, angle_unit)),
        "tan": lambda x: math.tan(_trig_input(x, angle_unit)),
        "asin": lambda x: inverse(x, math.asin),
        "acos": lambda x: inverse(x, math.acos),
        "atan": lambda x: inverse(x, math.atan),
        "atan2": lambda y, x: (
            math.degrees(math.atan2(_dimensionless_magnitude(y), _dimensionless_magnitude(x)))
            if angle_unit == "degrees"
            else math.atan2(_dimensionless_magnitude(y), _dimensionless_magnitude(x))
        ),
        "sinh": lambda x: math.sinh(_dimensionless_magnitude(x)),
        "cosh": lambda x: math.cosh(_dimensionless_magnitude(x)),
        "tanh": lambda x: math.tanh(_dimensionless_magnitude(x)),
        "floor": lambda x: math.floor(_dimensionless_magnitude(x)),
        "ceil": lambda x: math.ceil(_dimensionless_magnitude(x)),
        "min": min,
        "max": max,
    }


def _quantity_result(
    value: Any,
    *,
    output_unit: str | None,
    precision: int,
    operation: str,
    normalized_input: Any,
) -> MathResult:
    quantity = value if isinstance(value, Quantity) else ureg.Quantity(value)
    if not quantity.dimensionless and not output_unit:
        raise InputError(
            "Dimensionful calculations require an explicit output_unit. Retry with the requested "
            "unit and the original unscaled physical expression; do not insert manual conversion "
            "factors or attach a unit after calculation."
        )
    try:
        if output_unit:
            quantity = quantity.to(output_unit)
    except (DimensionalityError, ValueError) as exc:
        raise InputError(f"Unit conversion failed: {exc}.") from None
    magnitude = quantity.magnitude
    try:
        if not math.isfinite(float(magnitude)):
            raise InputError("Calculation produced NaN or infinity.")
    except (TypeError, ValueError, OverflowError):
        pass
    unit = None if quantity.dimensionless else f"{quantity.units:~}"
    formatted = _format_number(magnitude, precision)
    return MathResult(
        operation=operation,
        result=formatted,
        approximate=formatted,
        unit=unit,
        normalized_input=normalized_input,
        warnings=[
            "Unit-aware magnitudes use the numeric precision of the Pint backend; "
            "precision controls displayed significant digits."
        ],
        details={"dimension": str(quantity.dimensionality), "precision": precision},
    )


def calculate_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    expression = str(payload["expression"])
    variables = dict(payload.get("variables") or {})
    precision = _validate_precision(int(payload.get("precision", 30)))
    angle_unit = str(payload.get("angle_unit", "radians"))
    output_unit = payload.get("output_unit") or None
    if len(variables) > 100:
        raise InputError("Provide at most 100 variables.")
    for name in variables:
        validate_identifier(name, label="variable")
    if any(isinstance(value, str) and len(value) > 500 for value in variables.values()):
        raise InputError("Variable values may contain at most 500 characters.")

    unit_mode = bool(output_unit) or any(_looks_dimensionful(value) for value in variables.values())
    if unit_mode:
        names: dict[str, Any] = {"pi": math.pi, "tau": math.tau, "e": math.e}
        names.update({name: _quantity_value(value) for name, value in variables.items()})
        value = safe_evaluate(
            expression,
            names=names,
            functions=_unit_functions(angle_unit),
        )
        return _quantity_result(
            value,
            output_unit=output_unit,
            precision=precision,
            operation="calculate",
            normalized_input={"expression": expression, "variables": variables},
        ).model_dump(mode="json")

    symbols = {name: sp.Symbol(name) for name in variables}
    parsed, _ = _parse_symbolic(expression, symbols=symbols, angle_unit=angle_unit)
    substitutions = {
        symbols[name]: _numeric_substitution(value) for name, value in variables.items()
    }
    value = sp.simplify(parsed.subs(substitutions))
    if value.free_symbols:
        missing = ", ".join(sorted(str(symbol) for symbol in value.free_symbols))
        raise InputError(f"Missing numeric values for: {missing}.")
    if value.has(sp.nan, sp.zoo):
        raise InputError("Calculation produced an undefined value.")
    warnings: list[str] = []
    if value.has(sp.oo, -sp.oo):
        warnings.append("Result is infinite; verify the expression domain or limiting process.")
    exact = sp.sstr(value)
    approximate = sp.sstr(sp.N(value, precision))
    return MathResult(
        operation="calculate",
        result=exact,
        exact=exact,
        approximate=approximate,
        normalized_input=sp.sstr(parsed),
        warnings=warnings,
        details={
            "precision": precision,
            "angle_unit": angle_unit,
            "is_exact": bool(value.is_number and not value.has(sp.Float)),
        },
    ).model_dump(mode="json")


def convert_units_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = str(payload["value"])
    to_unit = str(payload["to_unit"])
    precision = _validate_precision(int(payload.get("precision", 15)))
    try:
        source = ureg.Quantity(value)
        converted = source.to(to_unit)
        zero_in_source = ureg.Quantity(0, to_unit).to(source.units).magnitude
        if math.isclose(
            float(source.magnitude),
            float(zero_in_source),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            converted = ureg.Quantity(0, to_unit)
    except (DimensionalityError, ValueError, TypeError) as exc:
        raise InputError(f"Unit conversion failed: {exc}.") from None
    result = _quantity_result(
        converted,
        output_unit=to_unit,
        precision=precision,
        operation="convert_units",
        normalized_input=f"{source.magnitude} {source.units:~}",
    )
    result.warnings = []
    result.details.update(
        {
            "source_unit": f"{source.units:~}",
            "target_unit": f"{converted.units:~}",
        }
    )
    return result.model_dump(mode="json")


def _approximate_sympy(value: Any, precision: int) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _approximate_sympy(item, precision) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_approximate_sympy(item, precision) for item in value]
    if isinstance(value, sp.MatrixBase):
        return [[sp.sstr(sp.N(cell, precision)) for cell in row] for row in value.tolist()]
    if isinstance(value, sp.Basic):
        return sp.sstr(sp.N(value, precision))
    return value


def _exact_sympy(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _exact_sympy(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_exact_sympy(item) for item in value]
    if isinstance(value, sp.MatrixBase):
        return [[sp.sstr(cell) for cell in row] for row in value.tolist()]
    if isinstance(value, sp.Basic):
        return sp.sstr(value)
    return value


def solve_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    equations = list(payload["equations"])
    variables = list(payload["variables"])
    domain = str(payload.get("domain", "real"))
    precision = _validate_precision(int(payload.get("precision", 30)))
    if not 1 <= len(equations) <= 8:
        raise InputError("Provide between 1 and 8 equations.")
    if not 1 <= len(variables) <= 8:
        raise InputError("Provide between 1 and 8 variables.")
    if domain not in {"real", "complex"}:
        raise InputError("domain must be 'real' or 'complex'.")
    symbols = {}
    for name in variables:
        valid_name = validate_identifier(name, label="variable")
        symbols[valid_name] = (
            sp.Symbol(valid_name, real=True) if domain == "real" else sp.Symbol(valid_name)
        )
    expressions: list[sp.Expr] = []
    normalized: list[str] = []
    for equation in equations:
        left_text, right_text = split_equation(str(equation))
        left, symbols = _parse_symbolic(left_text, symbols=symbols)
        right, symbols = _parse_symbolic(right_text, symbols=symbols)
        expressions.append(left - right)
        normalized.append(f"{sp.sstr(left)} = {sp.sstr(right)}")
    requested = [symbols[name] for name in variables]
    solutions = sp.solve(expressions, requested, dict=True, simplify=True)
    exact = [
        {
            name: sp.sstr(solution.get(symbol, symbol))
            for name, symbol in zip(variables, requested, strict=True)
        }
        for solution in solutions
    ]
    approximate = [
        {
            name: sp.sstr(sp.N(solution.get(symbol, symbol), precision))
            for name, symbol in zip(variables, requested, strict=True)
        }
        for solution in solutions
    ]
    warnings = [] if solutions else ["No solution was found in the requested domain."]
    return MathResult(
        operation="solve",
        result=exact,
        exact=exact,
        approximate=approximate,
        normalized_input=normalized,
        warnings=warnings,
        details={"domain": domain, "solution_count": len(solutions), "precision": precision},
    ).model_dump(mode="json")


def calculus_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = str(payload["operation"])
    expression = str(payload["expression"])
    variable_name = validate_identifier(str(payload.get("variable", "x")), label="variable")
    precision = _validate_precision(int(payload.get("precision", 30)))
    symbol = sp.Symbol(variable_name)
    symbols = {variable_name: symbol}
    parsed, symbols = _parse_symbolic(expression, symbols=symbols)
    warnings: list[str] = []

    if operation == "differentiate":
        order = int(payload.get("order", 1))
        if not 1 <= order <= 20:
            raise InputError("Derivative order must be between 1 and 20.")
        value = sp.diff(parsed, symbol, order)
    elif operation == "integrate":
        lower = payload.get("lower_bound")
        upper = payload.get("upper_bound")
        if (lower is None) != (upper is None):
            raise InputError("Provide both lower_bound and upper_bound, or neither.")
        if lower is None:
            value = sp.integrate(parsed, symbol)
        else:
            lower_value, symbols = _parse_symbolic(str(lower), symbols=symbols)
            upper_value, symbols = _parse_symbolic(str(upper), symbols=symbols)
            value = sp.integrate(parsed, (symbol, lower_value, upper_value))
    elif operation == "limit":
        point = payload.get("point")
        if point is None:
            raise InputError("point is required for a limit.")
        point_value, symbols = _parse_symbolic(str(point), symbols=symbols)
        direction = str(payload.get("direction", "+-"))
        if direction not in {"+", "-", "+-"}:
            raise InputError("direction must be '+', '-', or '+-'.")
        value = sp.limit(parsed, symbol, point_value, dir=direction)
    elif operation == "series":
        order = int(payload.get("order", 6))
        if not 1 <= order <= 50:
            raise InputError("Series order must be between 1 and 50.")
        point_text = str(payload.get("point", "0"))
        point_value, symbols = _parse_symbolic(point_text, symbols=symbols)
        value = sp.series(parsed, symbol, point_value, order)
    else:
        raise InputError("operation must be differentiate, integrate, limit, or series.")

    if isinstance(value, sp.Integral):
        warnings.append(
            "The symbolic engine could not close the integral; an unevaluated form is returned."
        )
    exact = sp.sstr(value)
    approximate = sp.sstr(sp.N(value, precision))
    return MathResult(
        operation=operation,
        result=exact,
        exact=exact,
        approximate=approximate,
        normalized_input=sp.sstr(parsed),
        warnings=warnings,
        details={"variable": variable_name, "precision": precision},
    ).model_dump(mode="json")


def _parse_matrix(data: Sequence[Sequence[int | float | str]], *, label: str) -> sp.Matrix:
    if not data or not isinstance(data, Sequence):
        raise InputError(f"{label} must be a non-empty matrix.")
    rows = [list(row) for row in data]
    if not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise InputError(f"{label} must be rectangular with at least one column.")
    if len(rows) > MAX_MATRIX_DIMENSION or len(rows[0]) > MAX_MATRIX_DIMENSION:
        raise InputError(
            f"{label} exceeds the {MAX_MATRIX_DIMENSION}x{MAX_MATRIX_DIMENSION} limit."
        )
    parsed_rows: list[list[sp.Expr]] = []
    for row in rows:
        parsed_row: list[sp.Expr] = []
        for cell in row:
            parsed_row.append(_numeric_substitution(cell))
        parsed_rows.append(parsed_row)
    return sp.Matrix(parsed_rows)


def linear_algebra_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = str(payload["operation"])
    precision = _validate_precision(int(payload.get("precision", 20)))
    matrix = _parse_matrix(payload["matrix"], label="matrix")
    other_data = payload.get("other_matrix")
    other = _parse_matrix(other_data, label="other_matrix") if other_data is not None else None
    warnings: list[str] = []
    details: dict[str, Any] = {"shape": list(matrix.shape), "precision": precision}

    if operation == "determinant":
        if not matrix.is_square:
            raise InputError("determinant requires a square matrix.")
        value: Any = matrix.det()
    elif operation == "inverse":
        if not matrix.is_square:
            raise InputError("inverse requires a square matrix.")
        if matrix.det() == 0:
            raise InputError("matrix is singular and has no inverse.")
        value = matrix.inv()
    elif operation == "solve":
        if other is None:
            raise InputError("other_matrix is required as the right-hand side for solve.")
        if not matrix.is_square or matrix.rows != other.rows:
            raise InputError("solve requires a square matrix and a matching right-hand side.")
        value = matrix.inv() * other if matrix.det() != 0 else None
        if value is None:
            raise InputError("linear system matrix is singular.")
    elif operation == "multiply":
        if other is None:
            raise InputError("other_matrix is required for multiply.")
        if matrix.cols != other.rows:
            raise InputError("matrix dimensions are incompatible for multiplication.")
        value = matrix * other
    elif operation == "transpose":
        value = matrix.T
    elif operation == "rank":
        value = sp.Integer(matrix.rank())
    elif operation == "rref":
        reduced, pivots = matrix.rref()
        value = reduced
        details["pivot_columns"] = list(pivots)
    elif operation == "eigenvalues":
        if not matrix.is_square:
            raise InputError("eigenvalues require a square matrix.")
        eigenvalues = matrix.eigenvals()
        value = [
            {"value": eigenvalue, "multiplicity": multiplicity}
            for eigenvalue, multiplicity in eigenvalues.items()
        ]
    elif operation == "eigenvectors":
        if not matrix.is_square:
            raise InputError("eigenvectors require a square matrix.")
        value = [
            {
                "value": eigenvalue,
                "multiplicity": multiplicity,
                "vectors": vectors,
            }
            for eigenvalue, multiplicity, vectors in matrix.eigenvects()
        ]
    elif operation == "norm":
        value = matrix.norm()
    elif operation == "condition_number":
        numeric = np.asarray(matrix.evalf(), dtype=float)
        condition = float(np.linalg.cond(numeric))
        value = sp.Float(condition)
        if condition > 1e12:
            warnings.append(
                "Matrix is severely ill-conditioned; numerical solutions may be unstable."
            )
        elif condition > 1e8:
            warnings.append("Matrix is ill-conditioned; interpret numerical results cautiously.")
    else:
        raise InputError(
            "operation must be determinant, inverse, solve, multiply, transpose, rank, rref, "
            "eigenvalues, eigenvectors, norm, or condition_number."
        )

    exact = _exact_sympy(value)
    approximate = _approximate_sympy(value, precision)
    return MathResult(
        operation=operation,
        result=exact,
        exact=exact,
        approximate=approximate,
        normalized_input=_exact_sympy(matrix),
        warnings=warnings,
        details=details,
    ).model_dump(mode="json")


def _finite_data(values: Sequence[float], *, label: str) -> np.ndarray:
    if not 1 <= len(values) <= MAX_DATA_POINTS:
        raise InputError(f"{label} must contain between 1 and {MAX_DATA_POINTS} values.")
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise InputError(f"{label} must be a one-dimensional list of finite numbers.")
    return array


def _rounded_dict(values: Mapping[str, Any], precision: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, (int, np.integer)):
            result[key] = int(value)
        elif value is None:
            result[key] = None
        else:
            result[key] = _format_number(value, precision)
    return result


def statistics_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    operation = str(payload["operation"])
    precision = _validate_precision(int(payload.get("precision", 15)))
    data = _finite_data(payload["data"], label="data")
    data_y_raw = payload.get("data_y")
    data_y = _finite_data(data_y_raw, label="data_y") if data_y_raw is not None else None
    confidence = float(payload.get("confidence", 0.95))
    if not 0 < confidence < 1:
        raise InputError("confidence must be strictly between 0 and 1.")
    warnings: list[str] = []

    if operation == "describe":
        q1, q3 = np.quantile(data, [0.25, 0.75])
        raw = {
            "count": len(data),
            "mean": np.mean(data),
            "median": np.median(data),
            "minimum": np.min(data),
            "maximum": np.max(data),
            "q1": q1,
            "q3": q3,
            "population_variance": np.var(data, ddof=0),
            "population_stdev": np.std(data, ddof=0),
            "sample_variance": np.var(data, ddof=1) if len(data) > 1 else None,
            "sample_stdev": np.std(data, ddof=1) if len(data) > 1 else None,
        }
    elif operation == "correlation":
        if data_y is None or len(data_y) != len(data):
            raise InputError("correlation requires data_y with the same length as data.")
        if np.std(data) == 0 or np.std(data_y) == 0:
            raise InputError("correlation is undefined for constant data.")
        coefficient, p_value = scipy_stats.pearsonr(data, data_y)
        raw = {"pearson_r": coefficient, "p_value": p_value, "count": len(data)}
    elif operation == "linear_regression":
        if data_y is None or len(data_y) != len(data):
            raise InputError("linear_regression requires data_y with the same length as data.")
        regression = scipy_stats.linregress(data, data_y)
        raw = {
            "slope": regression.slope,
            "intercept": regression.intercept,
            "r_value": regression.rvalue,
            "r_squared": regression.rvalue**2,
            "p_value": regression.pvalue,
            "slope_standard_error": regression.stderr,
            "intercept_standard_error": regression.intercept_stderr,
        }
    elif operation == "confidence_interval_mean":
        if len(data) < 2:
            raise InputError("confidence_interval_mean requires at least two observations.")
        mean = float(np.mean(data))
        standard_error = float(scipy_stats.sem(data))
        critical = float(scipy_stats.t.ppf((1 + confidence) / 2, len(data) - 1))
        margin = critical * standard_error
        raw = {
            "mean": mean,
            "lower": mean - margin,
            "upper": mean + margin,
            "confidence": confidence,
            "degrees_of_freedom": len(data) - 1,
        }
    elif operation == "t_test_independent":
        if data_y is None or len(data_y) < 2 or len(data) < 2:
            raise InputError(
                "t_test_independent requires at least two observations in each sample."
            )
        statistic, p_value = scipy_stats.ttest_ind(data, data_y, equal_var=False)
        raw = {"welch_t": statistic, "p_value": p_value, "n_x": len(data), "n_y": len(data_y)}
    else:
        raise InputError(
            "operation must be describe, correlation, linear_regression, "
            "confidence_interval_mean, or t_test_independent."
        )
    result = _rounded_dict(raw, precision)
    return MathResult(
        operation=operation,
        result=result,
        approximate=result,
        normalized_input={
            "data_count": len(data),
            "data_y_count": None if data_y is None else len(data_y),
        },
        warnings=warnings,
        details={"precision": precision, "confidence": confidence},
    ).model_dump(mode="json")


def _uncertainty_functions(angle_unit: str) -> dict[str, Callable[..., Any]]:
    if angle_unit not in {"radians", "degrees"}:
        raise InputError("angle_unit must be 'radians' or 'degrees'.")

    def trig_input(value: Any) -> Any:
        if isinstance(value, Quantity):
            try:
                return value.to("radian").magnitude
            except DimensionalityError:
                raise InputError("Trigonometric functions require angular units.") from None
        return value * math.pi / 180 if angle_unit == "degrees" else value

    def dimensionless(value: Any) -> Any:
        return _dimensionless_magnitude(value)

    return {
        "abs": abs,
        "sqrt": lambda x: x**0.5,
        "cbrt": lambda x: x ** (1 / 3),
        "exp": lambda x: umath.exp(dimensionless(x)),
        "ln": lambda x: umath.log(dimensionless(x)),
        "log": lambda x: umath.log(dimensionless(x)),
        "log10": lambda x: umath.log10(dimensionless(x)),
        "sin": lambda x: umath.sin(trig_input(x)),
        "cos": lambda x: umath.cos(trig_input(x)),
        "tan": lambda x: umath.tan(trig_input(x)),
        "sinh": lambda x: umath.sinh(dimensionless(x)),
        "cosh": lambda x: umath.cosh(dimensionless(x)),
        "tanh": lambda x: umath.tanh(dimensionless(x)),
        "min": min,
        "max": max,
    }


def propagate_uncertainty_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    expression = str(payload["expression"])
    raw_measurements = dict(payload["measurements"])
    precision = _validate_precision(int(payload.get("precision", 15)))
    output_unit = payload.get("output_unit") or None
    angle_unit = str(payload.get("angle_unit", "radians"))
    coverage_factor = float(payload.get("coverage_factor", 2.0))
    if not 0 < coverage_factor <= 10:
        raise InputError("coverage_factor must be greater than 0 and at most 10.")
    if not 1 <= len(raw_measurements) <= 50:
        raise InputError("Provide between 1 and 50 measurements.")

    names: dict[str, Any] = {"pi": math.pi, "tau": math.tau, "e": math.e}
    normalized: dict[str, Any] = {}
    for name, raw in raw_measurements.items():
        validate_identifier(name, label="measurement")
        measurement = raw if isinstance(raw, Measurement) else Measurement.model_validate(raw)
        uncertain = ufloat(measurement.value, measurement.uncertainty)
        names[name] = uncertain * ureg(measurement.unit) if measurement.unit else uncertain
        normalized[name] = measurement.model_dump(mode="json")

    value = safe_evaluate(
        expression,
        names=names,
        functions=_uncertainty_functions(angle_unit),
    )
    if isinstance(value, Quantity):
        try:
            value = value.to(output_unit) if output_unit else value.to_reduced_units()
        except (DimensionalityError, ValueError) as exc:
            raise InputError(f"Uncertainty unit conversion failed: {exc}.") from None
        unit = None if value.dimensionless else f"{value.units:~}"
        uncertain_value = value.magnitude
    else:
        if output_unit:
            raise InputError("output_unit was provided but the result is dimensionless.")
        unit = None
        uncertain_value = value
    if not isinstance(uncertain_value, UFloat):
        uncertain_value = ufloat(float(uncertain_value), 0.0)
    nominal = float(uncertain_value.nominal_value)
    standard = float(uncertain_value.std_dev)
    relative = abs(standard / nominal * 100) if nominal else None
    lower = nominal - coverage_factor * standard
    upper = nominal + coverage_factor * standard
    result = {
        "nominal_value": _format_number(nominal, precision),
        "standard_uncertainty": _format_number(standard, precision),
        "relative_uncertainty_percent": None
        if relative is None
        else _format_number(relative, precision),
        "coverage_factor": coverage_factor,
        "coverage_interval": [
            _format_number(lower, precision),
            _format_number(upper, precision),
        ],
    }
    return MathResult(
        operation="propagate_uncertainty",
        result=result,
        approximate=result,
        unit=unit,
        normalized_input={"expression": expression, "measurements": normalized},
        warnings=[
            "Propagation uses first-order linear uncertainty analysis and assumes "
            "independent inputs."
        ],
        details={"precision": precision, "angle_unit": angle_unit},
    ).model_dump(mode="json")


CONSTANT_ALIASES = {
    "c": "speed of light in vacuum",
    "speed_of_light": "speed of light in vacuum",
    "g": "standard acceleration of gravity",
    "gravity": "standard acceleration of gravity",
    "G": "Newtonian constant of gravitation",
    "gravitational_constant": "Newtonian constant of gravitation",
    "h": "Planck constant",
    "planck": "Planck constant",
    "hbar": "reduced Planck constant",
    "k_B": "Boltzmann constant",
    "boltzmann": "Boltzmann constant",
    "N_A": "Avogadro constant",
    "avogadro": "Avogadro constant",
    "elementary_charge": "elementary charge",
    "electron_mass": "electron mass",
    "proton_mass": "proton mass",
    "gas_constant": "molar gas constant",
}


def physical_constant_engine(payload: Mapping[str, Any]) -> dict[str, Any]:
    query = str(payload["query"]).strip()
    precision = _validate_precision(int(payload.get("precision", 15)))
    output_unit = payload.get("output_unit") or None
    if not query:
        raise InputError("query cannot be empty.")
    canonical = CONSTANT_ALIASES.get(query, query)
    keys = list(scipy_constants.physical_constants)
    if canonical not in scipy_constants.physical_constants:
        lowered = {key.lower(): key for key in keys}
        canonical = lowered.get(canonical.lower(), canonical)
    if canonical not in scipy_constants.physical_constants:
        matches = difflib.get_close_matches(canonical, keys, n=5, cutoff=0.45)
        if not matches:
            raise InputError(f"Unknown physical constant {query!r}.")
        if len(matches) > 1 and difflib.SequenceMatcher(None, canonical, matches[0]).ratio() < 0.75:
            raise InputError(f"Ambiguous constant {query!r}; close matches: {', '.join(matches)}.")
        canonical = matches[0]
    value, unit, uncertainty = scipy_constants.physical_constants[canonical]
    if output_unit:
        try:
            converted = ureg.Quantity(value, unit).to(output_unit)
            scale = float(converted.magnitude) / value if value else 1.0
            value = float(converted.magnitude)
            uncertainty = abs(uncertainty * scale)
            unit = f"{converted.units:~}"
        except (DimensionalityError, ValueError, TypeError) as exc:
            raise InputError(f"Constant unit conversion failed: {exc}.") from None
    result = {
        "name": canonical,
        "value": _format_number(value, precision),
        "unit": unit,
        "standard_uncertainty": _format_number(uncertainty, precision),
    }
    return MathResult(
        operation="physical_constant",
        result=result,
        approximate=result["value"],
        unit=unit or None,
        normalized_input=query,
        details={
            "source": "scipy.constants.physical_constants",
            "precision": precision,
            "relative_precision": scipy_constants.precision(canonical),
        },
    ).model_dump(mode="json")


ENGINE_FUNCTIONS: dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]] = {
    "calculate": calculate_engine,
    "convert_units": convert_units_engine,
    "solve": solve_engine,
    "calculus": calculus_engine,
    "linear_algebra": linear_algebra_engine,
    "statistics": statistics_engine,
    "propagate_uncertainty": propagate_uncertainty_engine,
    "physical_constant": physical_constant_engine,
}
