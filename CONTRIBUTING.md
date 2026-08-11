# Contributing

Contributions that improve correctness, safe mathematical coverage, tool descriptions, or
interoperability are welcome.

## Development setup

```sh
git clone https://github.com/matheusbgodoi/scimath-mcp.git
cd scimath-mcp
uv sync --all-groups
```

Run the quality gate before proposing a change:

```sh
uv lock --check
uv run ruff check .
uv run pytest -q
uv build --clear
```

## Change guidelines

- Add regression tests for every bug fix and positive/negative tests for new syntax.
- Keep tools stateless and the catalog compact; prefer a new operation within the correct domain
  over a narrowly scoped tool.
- Never introduce `eval`, arbitrary imports, attribute access, network access, or mutable external
  state into computation paths.
- Preserve exact values as strings and surface numerical caveats in `warnings`.
- Update the tool reference and changelog for user-visible changes.
- Do not commit API keys, provider URLs containing credentials, personal client configuration,
  generated build artifacts, or virtual environments.

## Commit and review expectations

Use focused commits with imperative subjects. Pull requests should explain the numerical behavior,
trust-boundary impact, test evidence, and any new dependency. CI must pass on every supported
Python version before merge.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).
