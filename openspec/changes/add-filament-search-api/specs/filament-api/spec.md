## ADDED Requirements

### Requirement: Timestamps are returned in the home timezone
Every API response containing a filament SHALL give `created_at` and `updated_at` as ISO 8601 datetimes in the home timezone (`FILAMENTS_TIMEZONE`) with their UTC offset. Stored values SHALL remain UTC.

#### Scenario: Chicago time with offset
- **WHEN** the home timezone is `America/Chicago` and Claude gets a filament created at 17:53:10 UTC on 2026-11-22
- **THEN** `created_at` is `2026-11-22T11:53:10-06:00` (to the second)

#### Scenario: Same instant
- **WHEN** a returned local timestamp is converted back to UTC
- **THEN** it equals the stored UTC value
