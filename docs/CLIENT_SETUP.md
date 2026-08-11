# Client setup

SciMath uses the local `stdio` transport. All three clients can launch the same executable; no
port, token, or hosted service is required.

## Install the executable

From a clone of this repository:

```sh
uv tool install --force .
command -v scimath-mcp
```

Use the absolute path returned by `command -v` in client configuration. On a standard uv setup it
is `$HOME/.local/bin/scimath-mcp`.

## Codex CLI

```sh
codex mcp add scimath -- "$HOME/.local/bin/scimath-mcp"
codex mcp get scimath
```

Equivalent `~/.codex/config.toml` entry:

```toml
[mcp_servers.scimath]
command = "/absolute/path/to/scimath-mcp"
```

## Claude Code

Register at user scope so the server is available in every project:

```sh
claude mcp add --scope user scimath -- "$HOME/.local/bin/scimath-mcp"
claude mcp get scimath
```

Prefer the CLI command instead of editing Claude's settings by hand.

## OpenCode

OpenCode accepts the following entry in `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scimath": {
      "type": "local",
      "command": ["/absolute/path/to/scimath-mcp"],
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

Preserve unrelated provider and model settings when adding this object. Verify the resulting
configuration with `opencode mcp list`.

For a local provider whose API key is referenced as `{env:LOCAL_AI_API_KEY}`, ensure the variable
is loaded by the shell that starts OpenCode. Do not place the key in this repository or inline it
in `opencode.json`.

## Smoke test

Ask the client:

> Use SciMath, not mental arithmetic. Calculate the bending stress M*c/I for M=12.4 kN*m,
> c=75 mm, and I=8.7e-6 m^4. Return MPa and mention the tool used.

The expected value is approximately `106.896551724 MPa`. The client trace should show a call to
`calculate` (some clients prefix it as `scimath_calculate`).

## Troubleshooting

- **Disconnected server:** run the absolute executable directly. An MCP stdio server normally
  waits silently for protocol input; use `Ctrl-C` to stop it.
- **Command not found:** rerun `uv tool install --force .` and use `command -v scimath-mcp`.
- **Changes not visible:** uv tool installations are isolated snapshots; reinstall after source
  changes and restart the client.
- **Provider returns 401:** the model provider credential is missing from the launching shell.
  This is separate from SciMath, which needs no credential.
- **Tool is present but ignored:** explicitly instruct the model to use SciMath for every
  non-trivial calculation and to inspect the returned warnings.
