"""Speakable replies: see the openspec mcp-tools spec."""

import pytest
from pydantic import ValidationError

from filaments_mcp import formatting
from schemas import FilamentCreate, FilamentUpdate

NOTE = {
    "id": "1784d374-fa73-4878-8a5f-4a624b6302a9",
    "title": "Album cover ideas",
    "body": "Matte sleeve, hand-drawn type",
    "tags": ["design", "music"],
    "source": "claude",
    "created_at": "2026-11-24T23:30:00-06:00",
    "updated_at": "2026-11-24T23:30:00-06:00",
}
ID = "[id 1784d374-fa73-4878-8a5f-4a624b6302a9]"


@pytest.mark.parametrize(
    ("value", "spoken"),
    [
        ("2026-11-24T23:30:00-06:00", "Tue Nov 24, 11:30 PM"),
        ("2026-11-25T00:05:00-06:00", "Wed Nov 25, 12:05 AM"),
        ("2026-11-25T12:00:00.123-06:00", "Wed Nov 25, 12:00 PM"),
        ("2026-07-04T09:07:00-05:00", "Sat Jul 4, 9:07 AM"),
    ],
)
def test_spoken_datetime_keeps_the_local_offset(value, spoken):
    assert formatting.spoken_datetime(value) == spoken


def test_excerpt_cuts_at_a_word_boundary():
    body = ("word " * 100).strip()

    text = formatting.excerpt(body)

    assert text.endswith("word…")
    assert len(text) <= formatting.EXCERPT_LENGTH + 1


def test_excerpt_collapses_whitespace_and_keeps_short_bodies():
    assert formatting.excerpt("Line one\n\n  line two") == "Line one line two"


@pytest.mark.parametrize(
    ("words", "joined"),
    [([], ""), (["a"], "a"), (["a", "b"], "a and b"), (["a", "b", "c"], "a, b and c")],
)
def test_join_words(words, joined):
    assert formatting.join_words(words) == joined


def test_saved():
    assert formatting.saved(NOTE) == f'Saved "Album cover ideas" with tags design and music. {ID}'
    assert formatting.saved({**NOTE, "tags": []}).startswith(
        'Saved "Album cover ideas" with no tags.'
    )


@pytest.mark.parametrize(
    ("changed", "tags", "reply"),
    [
        (["tags"], ["art"], 'Updated "Album cover ideas": tags are now art.'),
        (["tags"], [], 'Updated "Album cover ideas": tags cleared.'),
        (["title", "body"], ["art"], 'Updated "Album cover ideas": title and body changed.'),
        (["body", "tags"], ["art"], 'Updated "Album cover ideas": body changed; tags are now art.'),
    ],
)
def test_updated(changed, tags, reply):
    assert formatting.updated({**NOTE, "tags": tags}, changed) == f"{reply} {ID}"


def test_deleted():
    assert formatting.deleted(NOTE) == 'Deleted "Album cover ideas".'


def test_search_results_list_with_excerpt_and_paging():
    page = {"items": [NOTE], "total": 25, "limit": 1, "offset": 0}

    text = formatting.search_results(page, has_query=True)

    assert text.splitlines() == [
        "Found 25 notes:",
        '1. "Album cover ideas" — Tue Nov 24, 11:30 PM — design, music',
        f"   Matte sleeve, hand-drawn type {ID}",
        "Showing 1–1 of 25.",
    ]


def test_search_results_without_query_say_newest_first():
    page = {"items": [NOTE], "total": 1, "limit": 10, "offset": 0}

    assert formatting.search_results(page, has_query=False).startswith(
        "Found 1 note, newest first:"
    )


def test_search_results_number_from_the_offset():
    page = {"items": [NOTE], "total": 12, "limit": 1, "offset": 10}

    assert "\n11. " in "\n" + formatting.search_results(page, has_query=True)


@pytest.mark.parametrize(
    ("offset", "count", "total", "footer"),
    [
        (0, 10, 25, "Showing 1–10 of 25."),
        (10, 10, 25, "Showing 11–20 of 25."),
        (20, 5, 25, "Showing 21–25 of 25."),
        (0, 3, 3, None),
    ],
    ids=["first-page", "middle-page", "last-page", "everything"],
)
def test_paging_footer_shows_the_range(offset, count, total, footer):
    page = {"items": [NOTE] * count, "total": total, "limit": 10, "offset": offset}

    last_line = formatting.search_results(page, has_query=True).splitlines()[-1]

    if footer:
        assert last_line == footer
    else:
        assert not last_line.startswith("Showing")


def test_no_results():
    empty = {"items": [], "total": 0, "limit": 10, "offset": 0}

    assert formatting.search_results(empty, has_query=True) == "No notes matched."


def test_full_filament_has_the_whole_body():
    body = "word " * 100

    text = formatting.full_filament({**NOTE, "body": body})

    assert text.endswith(body)
    assert text.startswith('"Album cover ideas" — Tue Nov 24, 11:30 PM — design, music')


def test_tag_counts():
    tags = [{"name": "music", "count": 5}, {"name": "art", "count": 2}]

    assert formatting.tag_counts(tags) == "music (5), art (2)"
    assert formatting.tag_counts([]) == "No tags yet."


def test_validation_message_from_pydantic():
    with pytest.raises(ValidationError) as exc:
        FilamentCreate(title="t", body="b", tags=[f"t{i}" for i in range(9)])

    assert formatting.validation_message(exc.value.errors()) == "tags: Tag limit is 8; got 9"


def test_validation_message_for_model_level_rule():
    with pytest.raises(ValidationError) as exc:
        FilamentUpdate()

    assert formatting.validation_message(exc.value.errors()) == (
        "Send at least one of title, body or tags"
    )


def test_validation_message_from_api_422_body():
    detail = [
        {"loc": ["body", "data", "tags"], "msg": "Tag limit is 8; got 9"},
        {"loc": ["query", "limit"], "msg": "Input should be less than or equal to 100"},
        {"loc": ["body", "data"], "msg": "Value error, Send at least one of title, body or tags"},
    ]

    assert formatting.validation_message(detail) == (
        "tags: Tag limit is 8; got 9; "
        "limit: Input should be less than or equal to 100; "
        "Send at least one of title, body or tags"
    )
