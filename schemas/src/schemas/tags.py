"""Tag normalization and the tag-with-count shape.

The functions here are plain Python so Django views or management commands can
normalize tags without building a Pydantic model. Error messages are short and
plain enough to be read aloud by Claude.
"""

import unicodedata

from pydantic import BaseModel

MAX_TAGS = 8
MAX_TAG_LENGTH = 50
_PREVIEW_LENGTH = 20


def _strip_accents(text: str) -> str:
    """Drop accent marks from Latin letters only.

    Marks on other scripts are part of the letter (Japanese voicing marks,
    Devanagari vowel signs), so they are kept and the text is recomposed.
    """
    kept = []
    base_is_latin = False
    for ch in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(ch):
            if base_is_latin:
                continue
        else:
            base_is_latin = ch.isascii()
        kept.append(ch)
    return unicodedata.normalize("NFC", "".join(kept))


def _is_tag_char(ch: str) -> bool:
    # Marks count as part of a word; `_` and everything else is a separator.
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def _hyphenate(text: str) -> str:
    """Replace each run of non-letters/digits with one "-" and trim "-" from the ends."""
    out: list[str] = []
    for ch in text:
        if _is_tag_char(ch):
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def _preview(text: str) -> str:
    return text if len(text) <= _PREVIEW_LENGTH else text[:_PREVIEW_LENGTH] + "…"


def normalize_tag(raw: str) -> str:
    """Return the canonical form of one tag, or raise ValueError.

    trim -> strip accents -> lowercase -> runs of non-letters/digits become "-"
    -> trim "-". Lowercasing comes after decomposition because NFKD can produce
    capitals ("™" -> "TM"). Empty or over-long results are rejected, never dropped or cut.
    """
    tag = _hyphenate(_strip_accents(raw.strip()).lower())
    if not tag:
        raise ValueError(f"Tag '{_preview(raw)}' is empty after removing punctuation")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Tag '{_preview(tag)}' is longer than {MAX_TAG_LENGTH} characters")
    return tag


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Normalize each tag and drop duplicates, keeping first-seen order.

    Does not check the tag count: write schemas apply MAX_TAGS, filters don't.
    """
    return list(dict.fromkeys(normalize_tag(raw) for raw in raw_tags))


class TagWithCount(BaseModel):
    name: str
    count: int
