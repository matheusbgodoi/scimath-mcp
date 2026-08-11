# Design notes and community references

SciMath was implemented from scratch after reviewing several open-source calculator and symbolic
MCP servers. No source code was copied. The review focused on tool discoverability for smaller
local models, mathematical coverage, protocol quality, input safety, and reproducibility.

## References reviewed

- [cyanheads/calculator-mcp-server](https://github.com/cyanheads/calculator-mcp-server): a strong
  compact-tool design with structured errors, annotations, input/result limits, and a deliberately
  restricted math.js environment. SciMath adopts its emphasis on compact schemas and explicit
  recovery metadata, while adding exact SymPy arithmetic, engineering units, uncertainty, SciPy,
  and process isolation.
- [sdiehl/sympy-mcp](https://github.com/sdiehl/sympy-mcp): broad symbolic coverage and useful
  variable assumptions. Its stateful, many-tool workflow is powerful but expensive in tool context
  and harder for a quantized local model to orchestrate. SciMath instead uses explicit stateless
  calls grouped into a few mathematical domains.
- [huhabla/calculator-mcp-server](https://github.com/huhabla/calculator-mcp-server): useful breadth
  across symbolic math, matrices, and statistics. Its direct expression evaluation and many tools
  motivated SciMath's AST allowlist and smaller catalog.
- [thinkitpossible/CalcMCP](https://github.com/thinkitpossible/CalcMCP): the three-domain
  consolidation (`symbolic`, `numpy`, `scipy`) is a useful model-selection pattern. SciMath keeps
  domain grouping but gives high-frequency tasks distinct tools and avoids Python `eval` paths.
- [yinebebt/mcp-calculator-server](https://github.com/yinebebt/mcp-calculator-server): good use of
  server instructions, read-only annotations, structured results, resources, and strict input
  bounds. SciMath follows those MCP protocol practices with a scientific rather than basic engine.
- [wrtnlabs/calculator-mcp](https://github.com/wrtnlabs/calculator-mcp): demonstrates that a tiny
  arithmetic server is easy for models to call, but its six basic-operation tools do not cover the
  engineering reliability problem.

## Resulting decisions

1. Eight stateless tools: explicit enough for reliable selection, small enough for local context.
2. MCP Python SDK 2.0 structured output and server-level numerical policy.
3. An AST allowlist instead of `eval`, `sympify`, or `parse_expr` on untrusted text.
4. Disposable subprocesses and timeouts around symbolic/numerical execution.
5. Exact results plus requested-precision approximations wherever meaningful.
6. Pint dimensional validation, SciPy CODATA metadata, uncertainty propagation, and numerical
   conditioning warnings.
7. Compact normalized inputs so large datasets do not echo into the model context.

## Trust boundary

The server verifies execution of the supplied mathematical formulation. It cannot determine
whether the calling model chose the correct governing equation, convention, domain, or statistical
assumption. Tool output therefore retains normalized inputs, warnings, units, and backend metadata.
