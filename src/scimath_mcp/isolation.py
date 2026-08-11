from __future__ import annotations

import json
import multiprocessing as mp
import os
from collections.abc import Mapping
from multiprocessing.connection import Connection
from typing import Any

from scimath_mcp.engines import ENGINE_FUNCTIONS
from scimath_mcp.safety import InputError

DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 120.0
MAX_PAYLOAD_BYTES = 5_000_000
MAX_RESULT_BYTES = 250_000


class ComputationError(RuntimeError):
    """A safe, user-facing computation failure."""


def _worker(connection: Connection, operation: str, payload: dict[str, Any]) -> None:
    try:
        function = ENGINE_FUNCTIONS[operation]
        result = function(payload)
        encoded_result = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded_result) > MAX_RESULT_BYTES:
            raise InputError(
                f"Result exceeds the {MAX_RESULT_BYTES}-byte context-safety limit; "
                "reduce the input size or split the computation."
            )
        connection.send(("ok", result))
    except InputError as exc:
        connection.send(("input_error", str(exc)))
    except Exception as exc:  # pragma: no cover - defensive protocol boundary
        connection.send(("internal_error", f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


def _timeout_from_environment() -> float:
    raw = os.environ.get("SCIMATH_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    return min(max(timeout, 1.0), MAX_TIMEOUT_SECONDS)


def run_isolated(
    operation: str,
    payload: Mapping[str, Any],
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run one bounded computation in a disposable subprocess."""
    if operation not in ENGINE_FUNCTIONS:
        raise ComputationError(f"Unknown computation operation {operation!r}.")
    primitive_payload = dict(payload)
    try:
        payload_size = len(
            json.dumps(primitive_payload, ensure_ascii=False, separators=(",", ":")).encode()
        )
    except (TypeError, ValueError) as exc:
        raise ComputationError(f"Computation payload is not JSON-compatible: {exc}.") from None
    if payload_size > MAX_PAYLOAD_BYTES:
        raise ComputationError(
            f"Computation payload exceeds the {MAX_PAYLOAD_BYTES}-byte safety limit."
        )
    timeout = _timeout_from_environment() if timeout is None else timeout
    context = mp.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(child, operation, primitive_payload),
        name=f"scimath-{operation}",
        daemon=True,
    )
    process.start()
    child.close()
    try:
        if not parent.poll(timeout):
            process.terminate()
            process.join(1.0)
            if process.is_alive():
                process.kill()
                process.join(1.0)
            raise ComputationError(
                f"{operation} exceeded the {timeout:g}-second computation timeout. "
                "Simplify the input or split it into smaller steps."
            )
        try:
            status, result = parent.recv()
        except EOFError:
            raise ComputationError(
                f"{operation} worker exited without returning a result."
            ) from None
    finally:
        parent.close()
        process.join(1.0)
    if status == "ok":
        return result
    if status == "input_error":
        raise ComputationError(result)
    raise ComputationError(f"Internal {operation} failure: {result}")
