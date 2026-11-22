## ADDED Requirements

### Requirement: List filaments newest first
`GET /api/filaments` SHALL return non-deleted filaments as `FilamentList` with `items`, `total` (count of all matches before paging), `limit` and `offset`. Without `q`, items SHALL be ordered by `created_at` newest first, with `id` as a tiebreak so paging never repeats or skips a filament.

#### Scenario: Default listing
- **WHEN** Claude lists filaments with no parameters and 25 exist
- **THEN** the response has the 20 newest, `total` 25, `limit` 20 and `offset` 0

#### Scenario: Second page
- **WHEN** Claude lists with `offset` 20
- **THEN** the response has the remaining 5, none repeated from the first page

#### Scenario: Soft-deleted filaments excluded
- **WHEN** a filament is soft-deleted
- **THEN** it appears in no listing and is not counted in `total`

#### Scenario: Invalid paging
- **WHEN** Claude lists with `limit` 500
- **THEN** the response is 422 with an error located on `limit`

### Requirement: Keyword search over title, body and tags
When `q` is present, the system SHALL parse it with `websearch_to_tsquery` using the `english` configuration and match it against the filament's stored title/body vector combined with a vector of its tag names (tag words weighted like the title). All words SHALL be required unless `or` is used; quoted phrases and `-exclusions` SHALL be honored. Results SHALL be ordered by rank, then `created_at` newest first, then `id`.

#### Scenario: Stemmed match in the body
- **WHEN** a filament's body says "I went for a run" and Claude searches "running"
- **THEN** the filament is returned

#### Scenario: Match on a tag name only
- **WHEN** a filament tagged `music` never mentions music in its text and Claude searches "music"
- **THEN** the filament is returned

#### Scenario: Words split across tags and text
- **WHEN** a filament is tagged `music` and its body says "ideas", and Claude searches "music ideas"
- **THEN** the filament is returned

#### Scenario: Hyphenated tag matches separate words
- **WHEN** a filament is tagged `album-art` and Claude searches "album art"
- **THEN** the filament is returned

#### Scenario: All words required
- **WHEN** Claude searches "harmony bridge" and a filament mentions only "harmony"
- **THEN** that filament is not returned

#### Scenario: Title outranks body
- **WHEN** one filament has "harmony" in its title and another only in its body
- **THEN** the title match is listed first

#### Scenario: Exclusion and phrase
- **WHEN** Claude searches `"hand drawn" -draft`
- **THEN** only filaments containing the phrase "hand drawn" and not the word "draft" are returned

#### Scenario: Only stop words
- **WHEN** Claude searches "the"
- **THEN** the response is 200 with no items and `total` 0

### Requirement: Filter by tags
When `tags` is present, the system SHALL return only filaments that have every listed tag (after normalization). An unknown tag SHALL produce an empty result, not an error.

#### Scenario: All tags must match
- **WHEN** Claude filters by `music` and `design`
- **THEN** a filament tagged only `music` is not returned, and one tagged both is

#### Scenario: Tag filter is normalized
- **WHEN** Claude filters by "#Music"
- **THEN** filaments tagged `music` are returned

#### Scenario: Unknown tag
- **WHEN** Claude filters by a tag no filament has
- **THEN** the response is 200 with no items

### Requirement: Filter by date in the home timezone
`date_from` and `date_to` SHALL filter on `created_at` and be inclusive whole days in the home timezone: from midnight at the start of `date_from` up to, but not including, midnight after `date_to`.

#### Scenario: Late-evening note belongs to its local day
- **WHEN** the home timezone is `America/Chicago`, a filament was created at 23:30 Chicago time on 2026-11-24, and Claude filters `date_from` = `date_to` = 2026-11-24
- **THEN** the filament is returned, and filtering on 2026-11-25 does not return it

#### Scenario: Dates out of order
- **WHEN** Claude sends `date_from` 2026-11-20 and `date_to` 2026-11-10
- **THEN** the response is 422 saying the start date is after the end date

### Requirement: Filters combine
All provided filters SHALL apply together (AND), and `total` SHALL count filaments matching all of them.

#### Scenario: Query, tag and date together
- **WHEN** Claude searches "cover" with tag `music` and a date range
- **THEN** only filaments matching the query, having the tag, and created in the range are returned, and `total` counts exactly those

### Requirement: Tag list with counts
`GET /api/tags` SHALL return `TagWithCount` items for every tag used by at least one non-deleted filament, where `count` is the number of non-deleted filaments with that tag. Items SHALL be ordered by `count` descending, then `name`.

#### Scenario: Counts exclude soft-deleted filaments
- **WHEN** tag `music` is on three filaments and one is soft-deleted
- **THEN** `music` is listed with count 2

#### Scenario: Unused tags hidden
- **WHEN** a tag's only filament is soft-deleted or its tags were replaced
- **THEN** the tag is not listed

#### Scenario: Ordering
- **WHEN** `music` has 5 filaments, `art` 2 and `design` 2
- **THEN** the order is `music`, `art`, `design`
