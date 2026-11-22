"""Turn API data and errors into short text Claude can read aloud.

Every reply leads with a speakable sentence. Ids only appear in trailing brackets so
Claude can make follow-up calls without reading them out.
"""

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

EXCERPT_LENGTH = 200
# Location segments that name the request part rather than the field.
_CONTAINER_LOCS = {"body", "query", "path", "data", "params"}


def spoken_datetime(value: str) -> str:
    """'2026-11-24T23:30:00-06:00' -> 'Tue Nov 24, 11:30 PM' (keeps the API's local offset)."""
    moment = dt.datetime.fromisoformat(value)
    hour = moment.hour % 12 or 12
    return f"{moment:%a %b} {moment.day}, {hour}:{moment:%M %p}"


def excerpt(body: str, length: int = EXCERPT_LENGTH) -> str:
    """The body on one line, cut at a word boundary near `length` characters."""
    text = " ".join(body.split())
    if len(text) <= length:
        return text
    cut = text[:length]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:.-") + "…"


def join_words(words: Sequence[str]) -> str:
    """['a'] -> 'a'; ['a', 'b'] -> 'a and b'; ['a', 'b', 'c'] -> 'a, b and c'."""
    if len(words) <= 1:
        return "".join(words)
    return f"{', '.join(words[:-1])} and {words[-1]}"


def _with_tags(tags: Sequence[str]) -> str:
    return f"with tags {join_words(tags)}" if tags else "with no tags"


def _id(filament: Mapping[str, Any]) -> str:
    return f"[id {filament['id']}]"


def saved(filament: Mapping[str, Any]) -> str:
    return f'Saved "{filament["title"]}" {_with_tags(filament["tags"])}. {_id(filament)}'


def updated(filament: Mapping[str, Any], changed: Iterable[str]) -> str:
    changed = set(changed)
    parts = []
    text_fields = [field for field in ("title", "body") if field in changed]
    if text_fields:
        parts.append(f"{join_words(text_fields)} changed")
    if "tags" in changed:
        tags = filament["tags"]
        parts.append(f"tags are now {join_words(tags)}" if tags else "tags cleared")
    return f'Updated "{filament["title"]}": {"; ".join(parts)}. {_id(filament)}'


def deleted(filament: Mapping[str, Any]) -> str:
    return f'Deleted "{filament["title"]}".'


def _summary_line(filament: Mapping[str, Any]) -> str:
    line = f'"{filament["title"]}" — {spoken_datetime(filament["created_at"])}'
    if filament["tags"]:
        line += f" — {', '.join(filament['tags'])}"
    return line


def search_results(page: Mapping[str, Any], *, has_query: bool) -> str:
    items, total = page["items"], page["total"]
    if not items:
        return "No notes matched." if total == 0 else f"No more notes; there are {total} in all."
    noun = "note" if total == 1 else "notes"
    header = f"Found {total} {noun}" + (":" if has_query else ", newest first:")
    lines = [header]
    for number, filament in enumerate(items, start=page["offset"] + 1):
        lines.append(f"{number}. {_summary_line(filament)}")
        lines.append(f"   {excerpt(filament['body'])} {_id(filament)}")
    first, last = page["offset"] + 1, page["offset"] + len(items)
    if first > 1 or last < total:
        lines.append(f"Showing {first}–{last} of {total}.")
    return "\n".join(lines)


def full_filament(filament: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"{_summary_line(filament)} {_id(filament)}",
            "",
            filament["body"],
        ]
    )


def tag_counts(tags: Sequence[Mapping[str, Any]]) -> str:
    if not tags:
        return "No tags yet."
    return ", ".join(f"{tag['name']} ({tag['count']})" for tag in tags)


def validation_message(errors: Iterable[Mapping[str, Any]]) -> str:
    """Pydantic errors or an API 422 `detail` list -> 'tags: Tag limit is 8; got 9'.

    Both use the same {loc, msg} shape. Errors without a field (model-level rules)
    are just the message.
    """
    messages = []
    for error in errors:
        message = str(error.get("msg", "Invalid input")).removeprefix("Value error, ")
        fields = [
            str(part)
            for part in error.get("loc", ())
            if not isinstance(part, int) and part not in _CONTAINER_LOCS
        ]
        messages.append(f"{fields[-1]}: {message}" if fields else message)
    return "; ".join(messages) or "Invalid input"
