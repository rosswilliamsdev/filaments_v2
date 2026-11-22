## MODIFIED Requirements

### Requirement: Updating a filament only changes the fields sent
`FilamentUpdate` SHALL treat every field as optional. An omitted field SHALL mean "leave unchanged". `tags: []` SHALL clear all tags, and a tag list SHALL replace the whole set. `title`, `body` or `tags` sent as `null` SHALL be rejected. An update that sends none of `title`, `body` or `tags` SHALL be rejected with the message "Send at least one of title, body or tags". The schema SHALL report which fields were sent.

#### Scenario: Change only the title
- **WHEN** Claude sends `{"title": "Album cover, v2"}`
- **THEN** only `title` is reported as sent, and body and tags are left unchanged

#### Scenario: Clear tags
- **WHEN** Claude sends `{"tags": []}`
- **THEN** `tags` is reported as sent with an empty list

#### Scenario: Null title
- **WHEN** Claude sends `{"title": null}`
- **THEN** the request is rejected with a validation error on `title`

#### Scenario: Empty update
- **WHEN** Claude sends `{}`
- **THEN** the request is rejected with "Send at least one of title, body or tags"
