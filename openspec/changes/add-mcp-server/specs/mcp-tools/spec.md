## ADDED Requirements

### Requirement: Six tools map one-to-one onto API routes
The MCP server SHALL expose exactly these tools, each calling one API route with the service token: `create_filament` (POST `/api/filaments`), `search_filaments` (GET `/api/filaments`), `get_filament` (GET `/api/filaments/{id}`), `update_filament` (PATCH `/api/filaments/{id}`), `delete_filament` (DELETE `/api/filaments/{id}`) and `list_tags` (GET `/api/tags`). The server SHALL NOT access the database or import Django.

#### Scenario: Tool list
- **WHEN** a client lists the server's tools
- **THEN** it sees exactly the six tools above, with `search_filaments`, `get_filament` and `list_tags` marked read-only and `delete_filament` marked destructive

#### Scenario: Token sent
- **WHEN** any tool calls the API
- **THEN** the request carries `Authorization: Bearer <FILAMENTS_API_TOKEN>`

### Requirement: Saving a note
`create_filament` SHALL validate its input with the shared `FilamentCreate` schema, create the filament, and reply with one speakable sentence naming the title and tags, followed by the id in brackets.

#### Scenario: Claude saves a dictated note
- **WHEN** Claude calls `create_filament` with title "Album cover ideas", a body and tags ["Music", "design"]
- **THEN** the reply begins `Saved "Album cover ideas" with tags design and music.` and ends with the new id in brackets

#### Scenario: Note without tags
- **WHEN** Claude saves a note with no tags
- **THEN** the reply begins `Saved "<title>" with no tags.`

#### Scenario: Too many tags
- **WHEN** Claude calls `create_filament` with 9 distinct tags
- **THEN** the tool fails with "tags: Tag limit is 8; got 9" and no API request is sent

### Requirement: Finding notes
`search_filaments` SHALL accept optional `query`, `tags`, `date_from`, `date_to` (YYYY-MM-DD, the user's local days), `limit` (default 10) and `offset`, validate them with `FilamentListParams`, and list matches with one line per note: number, quoted title, local date and time (e.g. "Tue Nov 24, 11:30 PM"), tags, a body excerpt of about 200 characters, and the id in brackets. The reply SHALL start with how many notes were found and end with "Showing X of Y." when more exist.

#### Scenario: No query lists newest first
- **WHEN** Claude calls `search_filaments` with no arguments
- **THEN** the newest notes are listed first

#### Scenario: Search by keyword and tag
- **WHEN** Claude searches query "cover" with tags ["music"]
- **THEN** only matching notes are listed, each with its excerpt and id

#### Scenario: Nothing found
- **WHEN** a search matches nothing
- **THEN** the reply is "No notes matched." with no list

#### Scenario: More results than shown
- **WHEN** 25 notes match and the limit is 10
- **THEN** the reply ends with "Showing 10 of 25."

#### Scenario: Long body
- **WHEN** a matching note's body is 1,000 characters
- **THEN** its line shows roughly the first 200 characters, cut at a word boundary and marked with "…"

#### Scenario: Bad date
- **WHEN** Claude sends `date_from` "next tuesday"
- **THEN** the tool fails with a readable message naming `date_from`

### Requirement: Reading, editing and deleting a note
`get_filament` SHALL reply with the title, local date and time, tags and the full body. `update_filament` SHALL send only the fields Claude provided (validated with `FilamentUpdate`) and reply `Updated "<title>".` naming what changed. `delete_filament` SHALL reply `Deleted "<title>".`

#### Scenario: Read in full
- **WHEN** Claude gets a note
- **THEN** the reply includes the whole body, not an excerpt

#### Scenario: Change only the tags
- **WHEN** Claude calls `update_filament` with only `tags` ["art"]
- **THEN** only tags are sent, and the reply is `Updated "<title>": tags are now art.`

#### Scenario: Nothing to update
- **WHEN** Claude calls `update_filament` with only an id
- **THEN** the tool fails with "Send at least one of title, body or tags"

#### Scenario: Delete
- **WHEN** Claude deletes a note titled "Album cover ideas"
- **THEN** the reply is `Deleted "Album cover ideas".`

### Requirement: Listing tags
`list_tags` SHALL reply with the tags in use and their counts, most used first (e.g. "music (5), art (2), design (2)"), or "No tags yet." when there are none.

#### Scenario: Tags with counts
- **WHEN** Claude lists tags and `music` has 5 notes and `art` 2
- **THEN** the reply lists `music (5)` before `art (2)`

### Requirement: Errors are short and speakable
Tool failures SHALL be raised as tool errors with plain-language messages and no stack traces, JSON or HTTP jargon: validation failures as "<field>: <message>" (joined with "; " when several), API 404 as "No note with that id.", 401 as "The notes server rejected my credentials. Check FILAMENTS_API_TOKEN.", 500 as "The notes server hit an error. It has been logged.", and a connection failure or timeout as "I can't reach the notes server right now." Any other exception SHALL be masked from the client and logged to stderr.

#### Scenario: Unknown id
- **WHEN** Claude gets a note that doesn't exist or was deleted
- **THEN** the tool fails with "No note with that id."

#### Scenario: API down
- **WHEN** the API is not running and Claude calls any tool
- **THEN** the tool fails with "I can't reach the notes server right now."

#### Scenario: Unexpected bug
- **WHEN** a tool raises an unexpected exception containing internal details
- **THEN** the client sees a generic failure without those details, and the traceback is written to stderr

### Requirement: Stdio entry point
`python -m filaments_mcp` SHALL run the server over stdio, writing only protocol messages to stdout and all logs to stderr. It SHALL read `FILAMENTS_API_URL` (default `http://127.0.0.1:8000/api`) and `FILAMENTS_API_TOKEN`, and exit with an error on stderr naming the setting when the token is missing.

#### Scenario: Local client connects
- **WHEN** a client launches `python -m filaments_mcp` and lists tools over stdio
- **THEN** it receives the six tools and stdout contains nothing but protocol messages

#### Scenario: Missing token
- **WHEN** the server starts without `FILAMENTS_API_TOKEN`
- **THEN** it exits with a non-zero status and an error naming `FILAMENTS_API_TOKEN` on stderr
