# Architecture

SciMath is a stateless MCP server with a deliberately narrow trust boundary. The agent decides
what to calculate; SciMath validates and executes the supplied formulation.

```text
Codex / Claude Code / OpenCode
              |
              | MCP over stdio
              v
       server.py (8 tools)
              |
              | validated JSON payload
              v
    isolation.py (spawn + timeout)
              |
              v
 safety.py + engines.py
              |
     +--------+--------+-----------+
     |        |        |           |
   SymPy     Pint    SciPy   uncertainties
              |
              v
 structured MathResult + warnings
```

## Request lifecycle

1. The MCP SDK validates the tool schema generated from Python type hints and Pydantic models.
2. SciMath serializes the primitive payload and enforces a 5 MB request limit.
3. A disposable process is spawned for the computation. Normal calls time out after 15 seconds;
   selected symbolic and matrix calls receive 30 seconds. `SCIMATH_TIMEOUT_SECONDS` may set the
   normal timeout from 1 to 120 seconds.
4. The expression parser accepts only explicitly allowed AST nodes, operators, symbols, and direct
   function calls.
5. A specialized engine performs the operation with SymPy, Pint, SciPy, NumPy, mpmath, or
   uncertainties.
6. The worker serializes a structured response capped at 250 kB. The parent terminates workers
   that exceed their deadline.

## Modules

| Module | Responsibility |
| --- | --- |
| `server.py` | MCP catalog, descriptions, annotations, and transport |
| `models.py` | Stable output and measurement schemas |
| `safety.py` | AST validation and symbolic parsing without Python evaluation |
| `engines.py` | Mathematical, unit, statistical, and uncertainty backends |
| `isolation.py` | Process boundary, payload/result limits, timeouts, safe errors |

## Design properties

- **Local and closed-world:** the stdio server opens no socket and performs no network calls.
- **Stateless:** every request includes all inputs, making calls reproducible and independent.
- **Compact catalog:** eight domain-oriented tools reduce tool-selection burden on local models.
- **Precision-preserving:** strings retain exact rational and symbolic values where available.
- **Explicit failure:** incompatible dimensions, unsupported syntax, and exceeded bounds return
  tool errors instead of guessed values.

## Non-goals

SciMath is not a computer algebra sandbox, arbitrary Python runner, simulation environment, finite
element solver, or proof assistant. It does not verify governing equations, unit conventions,
measurement independence, statistical design, or the physical validity of a model.
