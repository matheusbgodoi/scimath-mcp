from __future__ import annotations

import math

import pytest

from scimath_mcp.engines import (
    calculate_engine,
    calculus_engine,
    convert_units_engine,
    linear_algebra_engine,
    physical_constant_engine,
    propagate_uncertainty_engine,
    solve_engine,
    statistics_engine,
)
from scimath_mcp.safety import InputError


def test_exact_decimal_arithmetic() -> None:
    result = calculate_engine({"expression": "0.1 + 0.2", "precision": 40})
    assert result["exact"] == "3/10"
    assert result["approximate"] == "0.3000000000000000000000000000000000000000"


def test_arbitrary_precision_irrational() -> None:
    result = calculate_engine({"expression": "sqrt(2)", "precision": 50})
    assert result["exact"] == "sqrt(2)"
    assert result["approximate"].startswith("1.4142135623730950488016887242096980785696718753769")


def test_degree_mode_is_explicit_and_exact() -> None:
    result = calculate_engine(
        {"expression": "sin(30) + cos(60)", "angle_unit": "degrees", "precision": 30}
    )
    assert result["exact"] == "1"


def test_engineering_formula_with_units() -> None:
    result = calculate_engine(
        {
            "expression": "M*c/I",
            "variables": {"M": "12.4 kN*m", "c": "75 mm", "I": "8.7e-6 m^4"},
            "output_unit": "MPa",
            "precision": 12,
        }
    )
    assert result["unit"] == "MPa"
    assert result["result"] == "106.896551724"


def test_dimensionful_calculate_requires_explicit_output_unit() -> None:
    with pytest.raises(
        InputError,
        match="Dimensionful calculations require an explicit output_unit",
    ):
        calculate_engine(
            {
                "expression": "P*L^3/(3*E*I)",
                "variables": {
                    "P": "18 kN",
                    "L": "2.4 m",
                    "E": "210 GPa",
                    "I": "6.5e-6 m^4",
                },
            }
        )


def test_unit_mismatch_is_rejected() -> None:
    with pytest.raises(InputError, match="Unit conversion failed"):
        calculate_engine(
            {
                "expression": "distance/time",
                "variables": {"distance": "100 m", "time": "9.58 s"},
                "output_unit": "kg",
            }
        )


def test_affine_temperature_conversion_snaps_exact_zero() -> None:
    result = convert_units_engine({"value": "32 degF", "to_unit": "degC", "precision": 12})
    assert result["result"] == "0"
    assert result["unit"] == "°C"


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('touch /tmp/pwned')",
        "(1).__class__",
        "open('/etc/passwd')",
        "[x for x in range(10)]",
        "lambda: 1",
    ],
)
def test_python_execution_surfaces_are_rejected(expression: str) -> None:
    with pytest.raises(InputError):
        calculate_engine({"expression": expression})


def test_resource_exhaustion_limits() -> None:
    with pytest.raises(InputError, match="exponent"):
        calculate_engine({"expression": "2**10001"})
    with pytest.raises(InputError, match="factorial"):
        calculate_engine({"expression": "factorial(1001)"})


def test_quadratic_real_solutions() -> None:
    result = solve_engine(
        {
            "equations": ["x^2 - 5*x + 6 = 0"],
            "variables": ["x"],
            "domain": "real",
            "precision": 20,
        }
    )
    assert result["exact"] == [{"x": "2"}, {"x": "3"}]


def test_two_equation_system() -> None:
    result = solve_engine(
        {
            "equations": ["x + y = 5", "x - y = 1"],
            "variables": ["x", "y"],
            "domain": "real",
        }
    )
    assert result["exact"] == [{"x": "3", "y": "2"}]


def test_complex_domain_includes_real_and_nonreal_roots() -> None:
    real_roots = solve_engine(
        {"equations": ["x^2 - 1 = 0"], "variables": ["x"], "domain": "complex"}
    )
    imaginary_roots = solve_engine(
        {"equations": ["x^2 + 1 = 0"], "variables": ["x"], "domain": "complex"}
    )
    assert real_roots["exact"] == [{"x": "-1"}, {"x": "1"}]
    assert imaginary_roots["exact"] == [{"x": "-I"}, {"x": "I"}]


def test_calculus_exact_derivative_and_integral() -> None:
    derivative = calculus_engine(
        {"operation": "differentiate", "expression": "sin(x^2)", "variable": "x"}
    )
    integral = calculus_engine(
        {
            "operation": "integrate",
            "expression": "x^2",
            "variable": "x",
            "lower_bound": "0",
            "upper_bound": "1",
        }
    )
    assert derivative["exact"] == "2*x*cos(x**2)"
    assert integral["exact"] == "1/3"


def test_exact_linear_algebra() -> None:
    determinant = linear_algebra_engine({"operation": "determinant", "matrix": [[1, 2], [3, 4]]})
    inverse = linear_algebra_engine({"operation": "inverse", "matrix": [[1, 2], [3, 4]]})
    solution = linear_algebra_engine(
        {"operation": "solve", "matrix": [[2, 1], [1, -1]], "other_matrix": [[5], [1]]}
    )
    assert determinant["exact"] == "-2"
    assert inverse["exact"] == [["-2", "1"], ["3/2", "-1/2"]]
    assert solution["exact"] == [["2"], ["1"]]


def test_condition_number_warns_for_instability() -> None:
    result = linear_algebra_engine(
        {
            "operation": "condition_number",
            "matrix": [[1, 1], [1, "1.0000000000001"]],
        }
    )
    assert any("ill-conditioned" in warning for warning in result["warnings"])


def test_statistics_regression_and_describe() -> None:
    regression = statistics_engine(
        {
            "operation": "linear_regression",
            "data": [1, 2, 3, 4],
            "data_y": [2, 4, 6, 8],
            "precision": 12,
        }
    )
    summary = statistics_engine({"operation": "describe", "data": [1, 2, 3, 4]})
    assert regression["result"]["slope"] == "2"
    assert regression["result"]["r_squared"] == "1"
    assert summary["result"]["mean"] == "2.5"
    assert summary["result"]["sample_stdev"].startswith("1.290994")


def test_uncertainty_propagation_with_units() -> None:
    result = propagate_uncertainty_engine(
        {
            "expression": "m/V",
            "measurements": {
                "m": {"value": 10, "uncertainty": 0.1, "unit": "kg"},
                "V": {"value": 2, "uncertainty": 0.02, "unit": "m^3"},
            },
            "output_unit": "kg/m^3",
            "precision": 12,
        }
    )
    assert result["unit"] == "kg / m ** 3"
    assert result["result"]["nominal_value"] == "5"
    assert math.isclose(float(result["result"]["standard_uncertainty"]), math.sqrt(0.005))


def test_physical_constant_lookup_and_conversion() -> None:
    result = physical_constant_engine(
        {"query": "speed_of_light", "output_unit": "km/s", "precision": 15}
    )
    assert result["result"]["name"] == "speed of light in vacuum"
    assert result["result"]["value"] == "299792.458"
    assert result["unit"] == "km / s"
