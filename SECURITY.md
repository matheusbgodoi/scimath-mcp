# Security and numerical safety

SciMath is a local, read-only computation server. It opens no listening socket in its installed
configuration and makes no network requests.

## Supported versions

The latest release on the default branch receives security fixes. Pre-1.0 releases may change
their public schema between minor versions.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository: **Security → Advisories → New
draft security advisory**. Please include affected versions, a minimal reproduction, impact, and
any suggested mitigation. Do not disclose the issue publicly until a fix is available.

Maintainers will acknowledge a report as soon as practical, validate it, prepare a regression
test and fix, and coordinate disclosure with the reporter.

## Input boundary

- Expressions are parsed with Python's AST module and evaluated through an explicit allowlist.
- Imports, attributes, indexing, assignment, comprehensions, lambdas, strings, and Python builtins
  are unavailable inside expressions.
- Symbolic input is never passed to Python `eval`, SymPy `sympify`, or `parse_expr`.
- Computations run in disposable subprocesses with time, complexity, payload, and result limits.
- MCP tools are marked read-only, non-destructive, idempotent, and closed-world.

## Numerical boundary

Exact symbolic results are retained whenever possible. Unit-aware and SciPy operations may use
IEEE-754 arithmetic; their output says so and reports the requested display precision. Matrix
condition numbers and unresolved symbolic integrals produce warnings.

This server verifies a supplied computation, not the scientific model behind it. Consequential
results still require review of the normalized formula, units, domain, branch, assumptions, and
warnings.
