"""Shared Pydantic schemas used by the Ninja API and the MCP server.

Must not import Django: the MCP server installs this package on its own.
"""

from schemas.common import ErrorDetail, HealthStatus
from schemas.filaments import (
    FilamentCreate,
    FilamentList,
    FilamentListParams,
    FilamentOut,
    FilamentUpdate,
)
from schemas.tags import MAX_TAG_LENGTH, MAX_TAGS, TagWithCount, normalize_tag, normalize_tags

__all__ = [
    "MAX_TAGS",
    "MAX_TAG_LENGTH",
    "ErrorDetail",
    "FilamentCreate",
    "FilamentList",
    "FilamentListParams",
    "FilamentOut",
    "FilamentUpdate",
    "HealthStatus",
    "TagWithCount",
    "normalize_tag",
    "normalize_tags",
]
