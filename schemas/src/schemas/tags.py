"""Tag normalization and the tag-with-count shape.

The functions here are plain Python so Django views or management commands can
normalize tags without building a Pydantic model. Error messages are short and
plain enough to be read aloud by Claude.
"""

import re
import unicodedata

from pydantic import BaseModel

MAX_TAGS = 8
MAX_TAG_LENGTH = 50

# `\W` excludes `_` (it counts as a word character), so name it explicitly.
_SEPARATORS = re.compile(r"[\W_]+")


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_tag(raw: str) -> str:
    """Return the canonical form of one tag, or raise ValueError.

    trim -> lowercase -> strip accents -> runs of non-letters/digits become "-"
    -> trim "-". Empty or over-long results are rejected, never dropped or cut.
    """
    tag = _strip_accents(raw.strip().lower())
    tag = _SEPARATORS.sub("-", tag).strip("-")
    if not tag:
        raise ValueError(f"Tag '{raw}' is empty after removing punctuation")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Tag '{tag[:20]}…' is longer than {MAX_TAG_LENGTH} characters")
    return tag


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Normalize each tag and drop duplicates, keeping first-seen order.

    Does not check the tag count: write schemas apply MAX_TAGS, filters don't.
    """
    return list(dict.fromkeys(normalize_tag(raw) for raw in raw_tags))


class TagWithCount(BaseModel):
    name: str
    count: int
