# SciMath MCP

[![CI](https://github.com/matheusbgodoi/scimath-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/matheusbgodoi/scimath-mcp/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-2.0-6F42C1)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

SciMath is a local, read-only Model Context Protocol server for reliable engineering and
scientific computation. It moves arithmetic and mathematical manipulation out of an LLM's
reasoning and into established numerical, symbolic, unit, and uncertainty libraries.

It is designed specifically for tool-calling agents—including smaller quantized local models—so
the model chooses and explains a calculation while mature libraries execute it reproducibly.

## What it provides

- Exact and arbitrary-precision arithmetic with SymPy.
- Unit-aware formulas and dimensional validation with Pint.
- Equations, calculus, and exact linear algebra.
- Descriptive statistics, regression, confidence intervals, and Welch t-tests.
- First-order propagation of independent measurement uncertainties.
- Physical constants from SciPy's bundled CODATA table.
- Structured MCP output containing exact values, approximations, normalized inputs, metadata,
  and warnings.

Every expression is parsed by an AST allowlist. Python `eval`, attribute access, imports,
comprehensions, indexing, assignment, and arbitrary function calls are not available. Each
calculation runs in a disposable subprocess with input, result-size, complexity, and time limits.

## Tools

| Tool | Purpose |
| --- | --- |
| `calculate` | Arithmetic, scientific functions, high precision, and unit-aware formulas |
| `convert_units` | Compatible unit conversion and dimensional validation |
| `solve` | Real or complex algebraic equations and systems |
| `calculus` | Derivatives, integrals, limits, and series |
| `linear_algebra` | Exact matrix operations plus condition-number warnings |
| `statistics` | Summaries, correlation, regression, intervals, and Welch t-tests |
| `propagate_uncertainty` | Measurement uncertainty with optional units |
| `physical_constant` | CODATA constant lookup with uncertainty and unit conversion |

## Run locally

Prerequisites: Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
PYTHONPATH=src uv run python -m scimath_mcp
```

Install a stable executable:

```sh
uv tool install --force /absolute/path/to/scimath-mcp
```

Then register the same stdio executable in each client:

```sh
codex mcp add scimath -- "$HOME/.local/bin/scimath-mcp"
claude mcp add --scope user scimath -- "$HOME/.local/bin/scimath-mcp"
opencode mcp add scimath -- "$HOME/.local/bin/scimath-mcp"
```

Verify with `codex mcp get scimath`, `claude mcp get scimath`, and `opencode mcp list`. The
executable requires no network access. After changing the source, rerun the `uv tool install`
command to refresh the installed wheel.

See [Client setup](docs/CLIENT_SETUP.md) for complete JSON/TOML examples and troubleshooting.

## Expression syntax

Use explicit multiplication (`2*x`). Both `**` and `^` mean exponentiation. Common functions
include `sqrt`, `cbrt`, `exp`, `ln`, `log`, `log10`, `sin`, `cos`, `tan`, inverse and hyperbolic
trigonometry, `factorial`, `gamma`, `erf`, `floor`, `ceil`, `min`, and `max`. Constants include
`pi`, `tau`, `e`, `phi`, and complex `I` in unitless calculations.

Put dimensionful values in the `variables` object:

```json
{
  "expression": "M*c/I",
  "variables": {
    "M": "12.4 kN*m",
    "c": "75 mm",
    "I": "8.7e-6 m^4"
  },
  "output_unit": "MPa"
}
```

## Reliability boundary

SciMath makes the execution of a supplied formula reproducible. It cannot prove that an LLM
selected the correct physical model, sign convention, branch, domain, units, or statistical
assumptions. Consumers should show normalized inputs and warnings for consequential work.

## Documentation

- [Client setup](docs/CLIENT_SETUP.md) — Codex CLI, Claude Code, and OpenCode.
- [Tool reference](docs/TOOL_REFERENCE.md) — inputs, operations, limits, and examples.
- [Architecture](docs/ARCHITECTURE.md) — trust boundaries and request lifecycle.
- [Design notes](docs/DESIGN.md) — reviewed community projects and design decisions.
- [Security](SECURITY.md) — threat model, reporting, and numerical safety.
- [Contributing](CONTRIBUTING.md) — development workflow and release checks.

## Tests

```sh
uv run pytest
uv run ruff check .
uv build --clear
```

## License

MIT
