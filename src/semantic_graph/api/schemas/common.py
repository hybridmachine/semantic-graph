"""Shared Pydantic models used across the API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    """Standard JSON error envelope returned by the API."""

    detail: str = Field(..., description="Human-readable error description")
    error_type: str = Field(..., description="Machine-readable error category")
    status_code: int = Field(..., description="HTTP status code")


class PaginationParams(BaseModel):
    """Reusable pagination query parameters."""

    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records to return (1-100)",
    )

    @field_validator("limit")
    @classmethod
    def _clamp_limit(cls, v: int) -> int:
        # Pydantic ge/le already handle this; the validator is a safety net
        # and provides a consistent range contract.
        return max(1, min(v, 100))


class StatusResponse(BaseModel):
    """Generic status message for simple acknowledgements."""

    status: str = Field(..., description="Status label (e.g. 'ok', 'error')")
    message: str | None = Field(
        default=None, description="Optional human-readable context"
    )
