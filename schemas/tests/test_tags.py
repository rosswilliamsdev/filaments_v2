"""Tag normalization: see the openspec shared-schemas spec."""

import pytest

from schemas.tags import MAX_TAG_LENGTH, normalize_tag, normalize_tags


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Album Art ", "album-art"),
        ("#music", "music"),
        ("rock'n'roll", "rock-n-roll"),
        ("album_art", "album-art"),
        ("node.js", "node-js"),
        ("--a  --  b--", "a-b"),
        ("Café", "cafe"),
        ("Crème Brûlée", "creme-brulee"),
        ("Музыка", "музыка"),
        ("2026", "2026"),
        # NFKD can produce capitals, so lowercasing happens after it.
        ("Acme™", "acmetm"),
        ("ℌistory", "history"),
        ("𝐀rt", "art"),
        ("İstanbul", "istanbul"),
        ("Tiếng Việt", "tieng-viet"),
        # Marks that belong to non-Latin letters are kept, not stripped or hyphenated.
        ("ギター", "ギター"),
        ("संगीत", "संगीत"),
        ("Йога", "йога"),
    ],
)
def test_normalize_tag(raw, expected):
    assert normalize_tag(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "#", "--", "!!!"])
def test_empty_after_normalization_rejected(raw):
    with pytest.raises(ValueError, match="empty after removing punctuation"):
        normalize_tag(raw)


def test_empty_tag_message_is_truncated():
    with pytest.raises(ValueError) as exc:
        normalize_tag("-" * 5000)

    assert len(str(exc.value)) < 80


def test_length_limit_applies_after_normalization():
    assert normalize_tag("a" * MAX_TAG_LENGTH) == "a" * MAX_TAG_LENGTH
    # Surrounding punctuation is trimmed before the length check.
    assert normalize_tag("#" + "a" * MAX_TAG_LENGTH + "#") == "a" * MAX_TAG_LENGTH

    with pytest.raises(ValueError, match="longer than 50 characters"):
        normalize_tag("a" * (MAX_TAG_LENGTH + 1))


def test_normalize_tags_dedupes_keeping_order():
    assert normalize_tags(["Music", "design", "music ", "#music", "Design"]) == [
        "music",
        "design",
    ]


def test_normalize_tags_has_no_count_limit():
    assert len(normalize_tags([f"tag-{i}" for i in range(20)])) == 20
