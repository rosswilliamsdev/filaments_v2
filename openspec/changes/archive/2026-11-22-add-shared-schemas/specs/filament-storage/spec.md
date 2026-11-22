## ADDED Requirements

### Requirement: Dates use the configured home timezone
The system SHALL store timestamps in UTC and SHALL use a home timezone, set by `FILAMENTS_TIMEZONE` (an IANA name such as `America/Chicago`, default `UTC`), as Django's current timezone. Calendar dates such as "today" SHALL be computed in that timezone. An unknown timezone name SHALL stop the app at startup with a clear error.

#### Scenario: Late-evening note counts as the local day
- **WHEN** `FILAMENTS_TIMEZONE` is `America/Chicago` and a filament is created at 2026-11-24 23:30 Chicago time (05:30 UTC on 2026-11-25)
- **THEN** it is stored with a UTC `created_at`, and its local date is 2026-11-24

#### Scenario: Unknown timezone
- **WHEN** `FILAMENTS_TIMEZONE` is `America/Chicagoo`
- **THEN** startup fails with an error naming the bad setting
