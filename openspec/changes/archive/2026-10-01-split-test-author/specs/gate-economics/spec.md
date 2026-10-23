## ADDED Requirements

### Requirement: The outcomes view reports test authorship and test defects

`gates stats --outcomes` SHALL report, for each change, how its tests were authored.
The value is `separate` when every handoff came from a test-author agent, `inline`
when every handoff was inline, `mixed` when both occur, and `none` when no handoff
was recorded. It SHALL also report the number of test defects recorded. The fields
SHALL appear in the JSON output and in the human table.

#### Scenario: A change authored by the test author with one bounce

- **WHEN** a change's ledger holds only `separate` handoffs and one test defect
- **THEN** its outcomes row reports authorship `separate` and one test defect

#### Scenario: A change from before handoffs existed

- **WHEN** a change's ledger holds no handoff rows
- **THEN** its outcomes row reports authorship `none` and zero defects, and the change
  is counted as it was before
