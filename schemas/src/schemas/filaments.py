"""Filament request and response shapes, shared by the Ninja API and the MCP server.

Every model is flat so FastMCP can turn it into flat tool arguments.
"""

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError

from schemas.tags import MAX_TAGS, normalize_tags


def _normalize(raw_tags: list[str]) -> list[str]:
    # Re-raise as PydanticCustomError so the message isn't prefixed with "Value error, ".
    try:
        return normalize_tags(raw_tags)
    except ValueError as exc:
        raise PydanticCustomError("invalid_tag", str(exc)) from None


def _normalize_with_limit(raw_tags: list[str]) -> list[str]:
    tags = _normalize(raw_tags)
    if len(tags) > MAX_TAGS:
        raise PydanticCustomError(
            "tag_limit",
            "Tag limit is {limit}; got {count}",
            {"limit": MAX_TAGS, "count": len(tags)},
        )
    return tags


def _not_blank(text: str) -> str:
    if not text.strip():
        raise PydanticCustomError("blank", "Body can't be empty")
    return text


# Not Field(max_length=8): that would count duplicates and publish maxItems to Claude.
WriteTags = Annotated[
    list[str],
    AfterValidator(_normalize_with_limit),
    Field(
        description=(
            f"Up to {MAX_TAGS} tags. Normalized to lowercase with hyphens "
            "(e.g. 'Album Art' becomes 'album-art'); duplicates are merged."
        )
    ),
]
FilterTags = Annotated[
    list[str],
    AfterValidator(_normalize),
    Field(description="Only filaments that have all of these tags. Normalized like write tags."),
]
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    Field(description="Short title, up to 200 characters."),
]
Body = Annotated[str, AfterValidator(_not_blank), Field(description="Markdown body.")]


class FilamentCreate(BaseModel):
    """A new filament. `source` is not accepted; the server sets it."""

    title: Title
    body: Body
    tags: WriteTags = []


def _drop_null_defaults(schema: dict[str, Any]) -> None:
    # The None defaults only mark a field as optional; advertising `default: null`
    # would invite Claude to send null, which is rejected.
    for prop in schema.get("properties", {}).values():
        if "default" in prop and prop["default"] is None:
            del prop["default"]


class FilamentUpdate(BaseModel):
    """PATCH: omitted fields are unchanged; `tags: []` clears; a tag list replaces the set.

    Fields are typed without `| None` so an explicit null is rejected and the JSON schema
    never suggests null. Defaults aren't validated, so omitting a field still works.
    """

    model_config = ConfigDict(json_schema_extra=_drop_null_defaults)

    title: Title = None  # type: ignore[assignment]
    body: Body = None  # type: ignore[assignment]
    tags: WriteTags = None  # type: ignore[assignment]

    def changes(self) -> dict[str, Any]:
        """Only the fields the caller actually sent."""
        return self.model_dump(include=self.model_fields_set)


def _tag_names(value: Any) -> Any:
    """Accept a Django related manager or queryset of tags as well as a list of names.

    Duck-typed so this package never imports Django.
    """
    if callable(getattr(value, "all", None)):
        value = value.all()
    if isinstance(value, (str, bytes, dict)):
        return value  # let the list[str] check reject it
    try:
        items = list(value)
    except TypeError:
        return value
    return [item if isinstance(item, str) else getattr(item, "name", item) for item in items]


class FilamentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    body: str
    tags: Annotated[list[str], BeforeValidator(_tag_names), AfterValidator(sorted)]
    source: Literal["claude", "web"]
    created_at: dt.datetime
    updated_at: dt.datetime


class FilamentList(BaseModel):
    items: list[FilamentOut]
    total: int
    limit: int
    offset: int


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


class FilamentListParams(BaseModel):
    q: Annotated[
        str | None,
        BeforeValidator(_blank_to_none),
        Field(description="Keywords to search titles, bodies and tag names."),
    ] = None
    tags: FilterTags = []
    date_from: Annotated[
        dt.date | None, Field(description="Earliest day, inclusive, in the home timezone.")
    ] = None
    date_to: Annotated[
        dt.date | None, Field(description="Latest day, inclusive, in the home timezone.")
    ] = None
    limit: Annotated[int, Field(ge=1, le=100, description="How many to return, 1-100.")] = 20
    offset: Annotated[int, Field(ge=0, description="How many to skip.")] = 0

    @model_validator(mode="after")
    def _dates_in_order(self) -> "FilamentListParams":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise PydanticCustomError(
                "date_order",
                "Start date {date_from} is after end date {date_to}",
                {"date_from": str(self.date_from), "date_to": str(self.date_to)},
            )
        return self
