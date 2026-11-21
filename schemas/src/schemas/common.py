"""Shapes shared by every part of the API."""

from typing import Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Error body for non-validation errors, matching Ninja's default shape."""

    detail: str


class HealthStatus(BaseModel):
    """Body of a successful `GET /api/health`."""

    status: Literal["ok"]
