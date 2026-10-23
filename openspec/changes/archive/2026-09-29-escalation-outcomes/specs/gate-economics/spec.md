# Spec Delta

## ADDED Requirements

### Requirement: `gates stats --outcomes` reports autonomy from the durable ledger

`gates stats --outcomes` SHALL read the same durable ledger as `gates stats` and
report, per change, its **terminal state** and its **hands-off** verdict, and with
`--all` the aggregate that is the loop's north-star measure. It SHALL be computed only
from ledger rows, deterministically (the same ledger content and flags produce
byte-identical output), with the same scope resolution, `--all`, fail-loud-on-missing
and other-era-row tolerance rules as `gates stats`.

Terminal state SHALL be derived, never declared: `merged` when the ledger holds a
`merge` row; otherwise `halted` when its latest `halt` row is newer than its latest
`task-start` row; otherwise `in-progress`.

A change is **hands-off** when and only when it is `merged` and its ledger holds zero
`halt` rows, zero `intervention` rows and zero `taint` rows. Any of those makes it
`assisted`, and the report names which.

#### Scenario: One change, hands-off

- **WHEN** a change's ledger holds gate, review and task-start rows and one `merge`
  row, and no `halt`, `intervention` or `taint` row
- **THEN** `gates stats --outcomes --change <name>` reports terminal state `merged`
  and verdict `hands-off`

#### Scenario: One change, assisted

- **WHEN** a merged change's ledger holds one `intervention` row with cause `ask`
- **THEN** the report shows terminal state `merged`, verdict `assisted`, and lists
  `ask: 1` under interventions

#### Scenario: A halted change

- **WHEN** a change's latest `halt` row (cause `stalled`) is newer than its latest
  `task-start` row and there is no `merge` row
- **THEN** the report shows terminal state `halted` and the cause `stalled`

#### Scenario: A resumed change is in progress

- **WHEN** a `task-start` row follows the change's last `halt` row and there is no
  `merge` row
- **THEN** the report shows terminal state `in-progress`, and the earlier halt still
  counts under halts by cause

### Requirement: The aggregate view answers "what fraction ran hands-off, and what stopped the rest"

With `--all`, `gates stats --outcomes` SHALL report: the number of changes by terminal
state; the **hands-off share** — hands-off changes divided by merged changes, stated
as a fraction with both counts shown, and reported as not computable (never as zero)
when no change is merged; halts broken down by cause; interventions broken down by
kind; taints; and a per-month trend keyed on each change's earliest row timestamp,
giving changes, merged and hands-off per month. Changes are ordered
deterministically.

#### Scenario: The north-star line

- **WHEN** `gates stats --outcomes --all` runs over ledgers where four changes merged
  and three of them carry no halt, intervention or taint row
- **THEN** the report states a hands-off share of 3 of 4 merged changes

#### Scenario: Nothing merged yet

- **WHEN** no ledger holds a `merge` row
- **THEN** the hands-off share is reported as not computable, with the count of
  changes in each non-merged terminal state, and the command exits zero

#### Scenario: Halts are categorised, not narrated

- **WHEN** the ledgers hold `halt` rows with causes `weak-spec`, `weak-spec` and
  `missing-oracle`
- **THEN** the report lists `weak-spec: 2`, `missing-oracle: 1`, and every cause from
  the closed set that has no occurrences as `0`

#### Scenario: The trend is by month of first activity

- **WHEN** two changes have their earliest rows in different months
- **THEN** each appears under its own month in the trend, with that month's changes,
  merged and hands-off counts

### Requirement: The outcomes view has a stable JSON shape and discloses its blind spots

`--outcomes --json` SHALL emit exactly one JSON document with a documented shape:
per-change objects carrying `change`, `terminal`, `hands_off`, `halts` (by cause),
`interventions` (by kind), `taints`, `first_ts`; an aggregate object carrying counts
by terminal state, `hands_off_share` (numerator, denominator and value or `null`),
`halts_by_cause`, `interventions_by_kind`, `taints`, `trend`; and a `data_quality`
object carrying unparseable lines, rows without a usable timestamp, `halt` rows with a
missing or unknown cause, rows without a `session` value, and commits the audit could
not classify. The human report SHALL print the same disclosures in prose and SHALL end
by stating what the ledger cannot answer: a halt that was never recorded, a human turn
that went through neither the question tool nor a gated commit, and any commit created
after the last audit.

#### Scenario: JSON mode is machine-consumable

- **WHEN** `gates stats --outcomes --json` runs
- **THEN** stdout is exactly one JSON document in the documented shape, key order
  canonical, with nothing else interleaved

#### Scenario: A malformed halt is disclosed

- **WHEN** a ledger holds a `halt` row whose `cause` is missing
- **THEN** the report prints normally, the by-cause breakdown excludes that row, and
  `data_quality` counts it as a malformed halt

#### Scenario: Pre-era rows are disclosed

- **WHEN** a ledger holds rows written before the `session` field existed
- **THEN** `data_quality` reports how many rows had no session value, and the human
  report says human-commit classification is unavailable for them
