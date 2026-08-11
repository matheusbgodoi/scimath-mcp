# Tool reference

Every tool is read-only, idempotent, and local. All return the same `MathResult` envelope:

| Field | Meaning |
| --- | --- |
| `operation` | Operation actually executed |
| `result` | Primary result; strings preserve mathematical precision |
| `exact` | Exact symbolic value when available |
| `approximate` | Requested-precision numerical value when available |
| `unit` | Output unit for dimensionful results |
| `normalized_input` | Canonical input used by the engine |
| `warnings` | Numerical or modeling cautions that must be reviewed |
| `details` | Backend-specific metadata |

## `calculate`

Evaluates safe arithmetic and scientific expressions. Pass dimensionful values in `variables` and
request a compatible `output_unit` when useful.

```json
{
  "expression": "M*c/I",
  "variables": {"M": "12.4 kN*m", "c": "75 mm", "I": "8.7e-6 m^4"},
  "precision": 12,
  "output_unit": "MPa"
}
```

`angle_unit` is `radians` or `degrees`. Precision is 2–100 significant digits. Unit-aware
magnitudes use Pint's numeric backend; precision controls display formatting.

## `convert_units`

Converts one value string to a dimensionally compatible target.

```json
{"value": "32 degF", "to_unit": "degC", "precision": 12}
```

## `solve`

Solves one to eight equations for one to eight variables in the `real` or `complex` domain.
Equations may use `left = right` or a zero-valued expression.

```json
{"equations": ["x^2 - 5*x + 6 = 0"], "variables": ["x"], "domain": "real"}
```

## `calculus`

Supports `differentiate`, `integrate`, `limit`, and `series`. Definite integrals require both
bounds; limits and series require `point`. `order` selects derivative order or series term count.

```json
{"operation": "integrate", "expression": "sin(x)^2", "variable": "x",
 "lower_bound": "0", "upper_bound": "pi"}
```

## `linear_algebra`

Supports `determinant`, `inverse`, `solve`, `multiply`, `transpose`, `rank`, `rref`,
`eigenvalues`, `eigenvectors`, `norm`, and `condition_number`. Matrices are limited to 25×25.
String entries such as `"1/3"` preserve exact values. `other_matrix` is the second factor or the
right-hand side of a linear solve.

## `statistics`

Supports `describe`, `correlation`, `linear_regression`, `confidence_interval_mean`, and
`t_test_independent` (Welch's test). Arrays may contain up to 100,000 finite points. Correlation
and regression require equal-length `data` and `data_y`; the t-test treats them as independent
samples.

## `propagate_uncertainty`

Propagates independent standard uncertainties through an expression using first-order methods.
One to 50 measurements are accepted.

```json
{
  "expression": "mass/volume",
  "measurements": {
    "mass": {"value": 10.0, "uncertainty": 0.1, "unit": "g"},
    "volume": {"value": 4.0, "uncertainty": 0.05, "unit": "cm^3"}
  },
  "output_unit": "kg/m^3",
  "coverage_factor": 2.0
}
```

## `physical_constant`

Looks up SciPy's bundled CODATA constants by common alias or full name, and optionally converts
the result to a compatible unit. Useful aliases include `c`, `G`, `h`, `hbar`, `k_B`, `N_A`,
`e_charge`, `m_e`, `m_p`, `epsilon_0`, and `mu_0`.

## Expression grammar and limits

- Use explicit multiplication: `2*x`, not `2x`.
- `**` and `^` both represent powers.
- Constants: `pi`, `tau`, `e`, `phi`, and unitless complex `I`.
- Common functions: roots, exponential/logarithmic, trigonometric and hyperbolic functions,
  inverses, `factorial`, `gamma`, `erf`, `floor`, `ceil`, `min`, and `max`.
- Expressions are limited to 2,000 characters, 500 AST nodes, 16 arguments per call, 1,000
  digits per integer literal, and literal exponents with absolute value at most 10,000.
- Imports, attributes, indexing, assignment, comprehensions, lambdas, strings, and builtins are
  rejected.
