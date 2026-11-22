## ADDED Requirements

### Requirement: Create a filament
`POST /api/filaments` SHALL accept a `FilamentCreate` body, store the filament with source `claude`, attach its normalized tags (creating any that don't exist), and respond 201 with the filament as `FilamentOut`. The filament and its tags SHALL be written in one transaction.

#### Scenario: Claude saves a note
- **WHEN** Claude posts title "Album cover ideas", body "Matte sleeve, hand-drawn type" and tags ["Music", "design"]
- **THEN** the response is 201 with a new id, source `claude`, tags `design` and `music`, and both timestamps set

#### Scenario: Existing tag is reused
- **WHEN** a tag `music` already exists and Claude creates a filament tagged "Music"
- **THEN** the filament is linked to the existing `music` tag and no second tag is created

#### Scenario: Caller sends a source
- **WHEN** a create request includes `"source": "web"`
- **THEN** the filament is stored with source `claude`

#### Scenario: Nine tags
- **WHEN** Claude posts a filament with 9 distinct tags
- **THEN** the response is 422, the error is located on `tags` with "Tag limit is 8; got 9", and nothing is stored

#### Scenario: Blank body
- **WHEN** Claude posts a filament whose body is only whitespace
- **THEN** the response is 422 with an error located on `body`

#### Scenario: Tag write fails
- **WHEN** attaching tags fails after the filament row is inserted
- **THEN** the filament row is not kept

### Requirement: Get a filament
`GET /api/filaments/{id}` SHALL respond 200 with the filament as `FilamentOut`.

#### Scenario: Existing filament
- **WHEN** Claude gets a filament that exists
- **THEN** the response is 200 with its title, body, tags, source and timestamps, and no `deleted_at`

### Requirement: Update a filament
`PATCH /api/filaments/{id}` SHALL accept a `FilamentUpdate` body, change only the fields sent, and respond 200 with the updated `FilamentOut`. A tag list SHALL replace the filament's tags, and `tags: []` SHALL remove them all. `updated_at` SHALL change whenever an update is applied, including one that only changes tags. The update SHALL run in one transaction.

#### Scenario: Title only
- **WHEN** Claude patches a filament with `{"title": "Album cover, v2"}`
- **THEN** the title changes and the body and tags are unchanged

#### Scenario: Replace tags
- **WHEN** a filament tagged `music` and `design` is patched with `{"tags": ["Art"]}`
- **THEN** its only tag is `art`

#### Scenario: Tags-only update moves updated_at
- **WHEN** a filament is patched with only `{"tags": ["music"]}`
- **THEN** its `updated_at` is later than before

#### Scenario: Empty update
- **WHEN** Claude patches a filament with `{}`
- **THEN** the response is 422 with "Send at least one of title, body or tags"

### Requirement: Delete a filament
`DELETE /api/filaments/{id}` SHALL soft-delete the filament and respond 200 with the filament as it was, so the caller can name what was deleted. A soft-deleted filament SHALL then behave as missing for every route.

#### Scenario: Delete then get
- **WHEN** Claude deletes a filament titled "Album cover ideas"
- **THEN** the response is 200 with title "Album cover ideas", and a following get on the same id returns 404

#### Scenario: Delete twice
- **WHEN** Claude deletes a filament that is already soft-deleted
- **THEN** the response is 404

### Requirement: Missing filaments return a readable 404
Get, update and delete SHALL respond 404 with `{"detail": "No filament with that id"}` when the id does not exist, belongs to a soft-deleted filament, or is not a valid UUID.

#### Scenario: Soft-deleted filament
- **WHEN** Claude gets, patches or deletes a soft-deleted filament
- **THEN** the response is 404 with "No filament with that id"

#### Scenario: Malformed id
- **WHEN** Claude gets `/api/filaments/not-a-uuid`
- **THEN** the response is 404 with a JSON `detail`, not an HTML page

### Requirement: Unexpected errors return a generic JSON 500
Any unhandled exception in an API route SHALL produce a 500 response with a JSON `detail` containing a short generic message and no traceback or exception text. The full traceback SHALL be written to the log.

#### Scenario: Server fault during create
- **WHEN** the service raises an unexpected exception while Claude creates a filament
- **THEN** the response is 500 with a generic `detail`, and the traceback is logged
