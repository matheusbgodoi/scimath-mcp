from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class MathResult(BaseModel):
    """Stable, machine-readable result shared by every computation tool."""

    operation: str = Field(description="Operation actually performed.")
    result: Any = Field(description="Primary result; strings preserve mathematical precision.")
    exact: Any | None = Field(default=None, description="Exact symbolic result when available.")
    approximate: Any | None = Field(
        default=None, description="Numerical approximation at the requested precision."
    )
    unit: str | None = Field(default=None, description="Output unit, when dimensionful.")
    normalized_input: Any | None = Field(
        default=None, description="Canonical input used by the computation engine."
    )
    warnings: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class Measurement(BaseModel):
    """A measured value with standard uncertainty and an optional unit."""

    value: float
    uncertainty: float = Field(ge=0)
    unit: str | None = None

    @field_validator("value", "uncertainty")
    @classmethod
    def finite_numbers_only(cls, value: float) -> float:
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("measurement values must be finite")
        return value
