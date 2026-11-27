## ADDED Requirements

### Requirement: `gates stats --plans` reports why plans went back before approval

`gates stats --plans` SHALL read the same durable ledger as `gates stats`, with its scope resolution, fail-loud refusal on a missing ledger and tolerance of other-era rows. Per change it SHALL report send-backs (`plan-returned` rows) in total, by sender and by class, listing every closed-set value with zeros; the loop's own returns (`plan-review` rows with verdict `findings` or `question`) by checker, listing only checkers with at least one such row; the `resume` count; and the earliest send-back's timestamp. Output SHALL be deterministic.

#### Scenario: One change's send-backs

- **WHEN** a change's ledger holds two `plan-returned` rows (`human`/`scope` and `reviewer`/`collision`) and one `plan-review` row with verdict `findings` from `lens:gatedloop.implementability`
- **THEN** `gates stats --plans --change <name>` reports 2 send-backs, `human: 1`, `reviewer: 1`, `scope: 1`, `collision: 1`, every other class as `0`, and `lens:gatedloop.implementability: 1` under the loop's own returns

#### Scenario: A change with no plan rows

- **WHEN** a change's ledger holds only gate rows
- **THEN** the report shows 0 send-backs with every class at `0`, and exits 0

### Requirement: The plans view aggregates across changes with a monthly trend

With `--all`, `gates stats --plans` SHALL add an aggregate: the per-change totals summed across changes, and a per-month trend keyed on each `plan-returned` row's timestamp, giving send-backs by class per month: each month with at least one well-formed, dated send-back maps to every class, zeros included.

#### Scenario: The trend is by month of the send-back

- **WHEN** `gates stats --plans --all` runs over send-backs recorded in two different months
- **THEN** each send-back is counted under its own month and class in the trend
- **AND** each of the two months maps every class, zeros included, and no other month appears

### Requirement: The plans view is not combined with the other views

`--plans` SHALL refuse with exit 1, reading nothing, when combined with `--outcomes`, `--cost` or `--epic`.

#### Scenario: Conflicting views are refused

- **WHEN** `gates stats --plans --outcomes` runs
- **THEN** it exits 1 saying the two views cannot be combined

#### Scenario: The idle gap is ignored

- **WHEN** `gates stats --plans --idle-gap 5` runs
- **THEN** it exits 0 and prints exactly what `gates stats --plans` prints

### Requirement: The plans view has a stable JSON shape

`gates stats --plans --json` SHALL emit exactly one JSON document, key order canonical, always carrying `changes` (per-change objects with `change`, `returns`, `by`, `class`, `checker_returns`, `resumes`, `first_ts`), `aggregate` (`returns`, `by`, `class`, `checker_returns`, `resumes`, `trend`) and `data_quality`, whatever the scope.

#### Scenario: JSON mode is machine-consumable

- **WHEN** `gates stats --plans --json` runs
- **THEN** stdout is exactly one JSON document in the documented shape, with nothing else interleaved

### Requirement: The plans view discloses its blind spots

`data_quality` SHALL count unparseable lines, send-back rows without a usable timestamp, and `plan-returned` rows whose sender or class is missing or outside its set. A row whose sender or class is missing or outside its set SHALL be excluded from every count, `first_ts` and the trend; a well-formed row without a usable timestamp SHALL be counted in the totals, by sender and by class, but left out of `first_ts` and the trend. The human report SHALL print the same disclosures and end by stating what the ledger cannot answer: a send-back nobody recorded, and the send-backs of a plan whose branch never reached the checkout being read.

#### Scenario: A malformed send-back is disclosed

- **WHEN** a ledger holds a `plan-returned` row whose class is not in the closed set
- **THEN** the report prints normally, the by-class breakdown excludes that row, and `data_quality` counts it

#### Scenario: A send-back without a usable timestamp

- **WHEN** a ledger holds a well-formed `plan-returned` row whose `ts` cannot be parsed
- **THEN** it is counted in the totals, by sender and by class, and under `data_quality.rows_without_ts`, and is absent from `first_ts` and the trend

#### Scenario: The human report ends with what the ledger cannot see

- **WHEN** `gates stats --plans` runs without `--json`
- **THEN** the report prints the data-quality line and ends with the closing sentence design D6 states

### Requirement: The existing stats views ignore send-back rows

`gates stats` (with or without `--cost`) and `gates stats --outcomes` SHALL produce byte-identical output with or without `plan-returned` rows in the ledger. A send-back SHALL never read as a gate run, an intervention, a halt or a change's first activity.

#### Scenario: Economics and outcomes are unchanged

- **WHEN** `plan-returned` rows are appended to a ledger
- **THEN** `gates stats --json` and `gates stats --outcomes --json` print exactly what they printed before
