# Changelog

## 0.1.1 — 2026-08-11

- Strengthened the mandatory numerical policy to cover intermediate calculations, estimates,
  comparisons, percentages, plausibility checks, and other auxiliary quantitative claims.
- Added a pre-response audit requirement: every derived quantitative claim must be backed by a
  current SciMath tool call, or be explicitly reported as unverified.
- Explicitly prohibited silently recomputing tool output with mental arithmetic or generic code.
- Dimensionful `calculate` calls now require an explicit `output_unit`, preventing models from
  stripping units, inserting manual scale factors, or attaching units to unitless results.

## 0.1.0 — 2026-08-11

- Initial local release.
- Eight stateless scientific-computing tools with MCP structured output.
- Exact arithmetic, engineering units, equation solving, calculus, matrices, statistics,
  uncertainty propagation, and CODATA constant lookup.
- AST expression allowlist, disposable computation workers, timeouts, and context-size limits.
- Verified with Codex CLI, Claude Code CLI, and OpenCode using `local-3090/qwen-quality`.
