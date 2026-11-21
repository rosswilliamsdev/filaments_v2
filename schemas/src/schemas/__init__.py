"""Shared Pydantic schemas used by the Ninja API and the MCP server.

Must not import Django: the MCP server installs this package on its own.
"""

from schemas.common import ErrorDetail, HealthStatus

__all__ = ["ErrorDetail", "HealthStatus"]
