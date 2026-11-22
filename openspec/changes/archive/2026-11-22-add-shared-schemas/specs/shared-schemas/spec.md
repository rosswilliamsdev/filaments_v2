## ADDED Requirements

### Requirement: Schemas package has no Django dependency
The `schemas` package SHALL be importable without Django installed or configured, so the MCP server can depend on it alone. Every request and response shape used by both the API and the MCP server SHALL be defined once in this package.

#### Scenario: Importing schemas does not load Django
- **WHEN** `schemas` and all of its modules are imported in a fresh Python process
- **THEN** no `django` module is loaded

### Requirement: Tags are normalized before validation
The system SHALL normalize each tag by: trimming whitespace, lowercasing, removing accent marks, replacing each run of characters that are not letters or digits (including spaces, punctuation and `_`) with a single `-`, and trimming leading and trailing `-`. Letters and digits from non-Latin scripts SHALL be kept. The same normalization SHALL be available as a plain function outside the Pydantic models.

#### Scenario: Mixed-case tag with spaces
- **WHEN** Claude sends the tag " Album Art "
- **THEN** it is stored as `album-art`

#### Scenario: Leading hash and punctuation
- **WHEN** Claude sends the tags "#music", "rock'n'roll" and "album_art"
- **THEN** they become `music`, `rock-n-roll` and `album-art`

#### Scenario: Accented tag
- **WHEN** Claude sends the tag "Café"
- **THEN** it becomes `cafe`

#### Scenario: Non-Latin tag
- **WHEN** Claude sends the tag "Музыка"
- **THEN** it becomes `музыка`

### Requirement: Invalid tags are rejected, not silently fixed
The system SHALL reject a tag that is empty after normalization, or longer than 50 characters after normalization, with a validation error that names the problem in plain language. It SHALL NOT drop or truncate such tags.

#### Scenario: Tag with no letters or digits
- **WHEN** Claude sends the tags "music" and "#"
- **THEN** the request is rejected with a validation error saying a tag is empty after removing punctuation

#### Scenario: Tag too long
- **WHEN** Claude sends a tag that is 51 characters after normalization
- **THEN** the request is rejected with a validation error saying tags can be at most 50 characters

### Requirement: Duplicate tags are merged and the limit is 8
The system SHALL remove duplicate tags after normalization, keeping the first occurrence's position, and SHALL then reject a list of more than 8 tags with the message "Tag limit is 8; got N", where N is the count after deduplication. The limit SHALL be described in the field's description rather than as a JSON-schema `maxItems` constraint.

#### Scenario: Duplicates after normalization
- **WHEN** Claude sends the tags "Music", "music " and "#music"
- **THEN** the filament gets the single tag `music`

#### Scenario: Nine distinct tags
- **WHEN** Claude sends 9 distinct tags
- **THEN** the request is rejected with "Tag limit is 8; got 9"

#### Scenario: Ten tags that collapse to eight
- **WHEN** Claude sends 10 tags of which 2 are duplicates after normalization
- **THEN** the request is accepted with 8 tags

### Requirement: Creating a filament
`FilamentCreate` SHALL accept `title` (required, trimmed, 1–200 characters after trimming), `body` (required, must contain non-whitespace, stored as sent) and `tags` (optional, default none). It SHALL NOT accept `source`; the server sets it.

#### Scenario: Valid capture
- **WHEN** Claude sends title "Album cover ideas", body "Matte sleeve, hand-drawn type" and tags ["Music", "design"]
- **THEN** validation passes with tags `music` and `design`

#### Scenario: Blank body
- **WHEN** Claude sends a title and a body of only whitespace
- **THEN** the request is rejected with a validation error on `body`

#### Scenario: Title over 200 characters
- **WHEN** Claude sends a 201-character title
- **THEN** the request is rejected with a validation error on `title`

#### Scenario: Caller tries to set source
- **WHEN** a request includes `"source": "web"`
- **THEN** the field is ignored and does not reach the server's write logic

### Requirement: Updating a filament only changes the fields sent
`FilamentUpdate` SHALL treat every field as optional. An omitted field SHALL mean "leave unchanged". `tags: []` SHALL clear all tags, and a tag list SHALL replace the whole set. `title`, `body` or `tags` sent as `null` SHALL be rejected. The schema SHALL report which fields were sent.

#### Scenario: Change only the title
- **WHEN** Claude sends `{"title": "Album cover, v2"}`
- **THEN** only `title` is reported as sent, and body and tags are left unchanged

#### Scenario: Clear tags
- **WHEN** Claude sends `{"tags": []}`
- **THEN** `tags` is reported as sent with an empty list

#### Scenario: Null title
- **WHEN** Claude sends `{"title": null}`
- **THEN** the request is rejected with a validation error on `title`

### Requirement: Read shapes
`FilamentOut` SHALL contain `id`, `title`, `body`, `tags` (a list of tag names), `source`, `created_at` and `updated_at`, and SHALL NOT contain `deleted_at`. `TagWithCount` SHALL contain `name` and `count`. `FilamentList` SHALL contain `items`, `total`, `limit` and `offset`. All shapes SHALL be flat (no nested objects other than lists of `FilamentOut` or of tag names).

#### Scenario: Output omits deletion state
- **WHEN** a filament is serialized as `FilamentOut`
- **THEN** the result has no `deleted_at` field and tags are plain strings

### Requirement: List and search parameters
`FilamentListParams` SHALL accept `q` (optional text; blank is treated as absent), `tags` (optional, normalized and deduplicated like write tags, no count limit), `date_from` and `date_to` (optional calendar dates, both inclusive), `limit` (1–100, default 20) and `offset` (0 or more, default 0). `date_from` later than `date_to` SHALL be rejected.

#### Scenario: Defaults
- **WHEN** Claude lists filaments with no parameters
- **THEN** `limit` is 20 and `offset` is 0

#### Scenario: Tag filter is normalized
- **WHEN** Claude filters by tags ["#Music"]
- **THEN** the filter uses `music`

#### Scenario: Limit too high
- **WHEN** Claude asks for `limit` 500
- **THEN** the request is rejected with a validation error on `limit`

#### Scenario: Dates out of order
- **WHEN** Claude sends `date_from` 2026-11-20 and `date_to` 2026-11-10
- **THEN** the request is rejected with a validation error saying the start date is after the end date
