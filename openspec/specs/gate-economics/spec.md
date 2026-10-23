# gate-economics Specification

## Purpose
Reading the gate-cost story back out of the durable ledger: `gates stats` turns
`.gatedloop/runs/<change>.jsonl` into the bottleneck report field report #18 derived
by hand, and a stack-agnostic playbook tells the adopter what to do about what it
shows.

## Requirements

### Requirement: `gates stats` reports gate economics from the durable ledger

`gates stats` SHALL read the durable ledger (`.gatedloop/runs/<change>.jsonl`) and
report, per change: total active loop time, time and share of active time spent
per gate, failed-gate-attempt counts per gate, and per-task time. The report SHALL
be computed only from fields the ledger rows already carry (`ts`, `gate`, `exit`,
`duration_ms`, `change`, `task`, `attempt`); it SHALL NOT require any new row
field to be written, and it SHALL be deterministic: the same ledger content and
the same flags produce byte-identical output.

#### Scenario: The hand-derived analysis is one command

- **WHEN** a change's ledger holds gate rows spanning its implementation
- **THEN** `gates stats --change <name>` prints the change's active loop time, each gate's total time and percentage share of active time, each gate's failed-attempt count, and a per-task time breakdown — without the adopter parsing jsonl

#### Scenario: Gate share counts gate events only

- **WHEN** the ledger holds gate rows (`ci`, `unit`, `integration`, `verify`, `live-check`, `eval`) alongside non-gate event rows (`merge`, `taint`, `taint-clear`, `review`, `task-start`)
- **THEN** per-gate time and failed-attempt counts aggregate only the gate rows' `duration_ms` and `exit`, while non-gate rows still contribute their timestamps to active-time and per-task interval computation

#### Scenario: Failed attempts are counted per gate

- **WHEN** a gate row's `exit` is non-zero
- **THEN** it is counted as a failed attempt for that gate, and the report shows failed-attempt counts per gate and the change's total

### Requirement: Active loop time has one deterministic definition

Ledger rows are events, not sessions, so `gates stats` SHALL define active loop
time as the sum of wall-clock intervals between consecutive rows (ordered by
`ts`), where any interval longer than an idle threshold is excluded from the sum.
The default threshold SHALL be fixed and documented, and overridable with an
explicit flag. The report SHALL disclose the threshold in effect.

#### Scenario: An overnight gap is not active time

- **WHEN** two consecutive ledger rows are separated by more wall time than the idle threshold
- **THEN** that interval contributes nothing to active loop time, and shorter intervals sum normally

#### Scenario: The threshold is explicit and overridable

- **WHEN** the adopter passes the idle-threshold flag
- **THEN** the computation uses that threshold, and both the table and the JSON output state the threshold that was applied

### Requirement: Per-task attribution uses the recorded task id and never guesses

Rows carrying a `task` id SHALL be attributed to that task; per-task time is the
active-time sum over intervals attributed to the task's rows. Rows whose `task` is
null SHALL be reported under an explicit *unattributed* bucket — never assigned to
a nearby task by inference. The report SHALL state what the ledger cannot answer
(anything between recorded events — edit vs. think time, token cost, host
contention) rather than approximating it.

#### Scenario: Task-tagged rows produce a per-task breakdown

- **WHEN** the ledger holds rows with `task` ids recorded by `gates run --task`
- **THEN** the report shows time and failed attempts per task id

#### Scenario: Untagged rows are unattributed, not guessed

- **WHEN** the ledger holds rows whose `task` is null
- **THEN** their time appears in an explicit unattributed bucket and no heuristic assigns them to a task

### Requirement: Scope defaults to the current branch, with `--all` for every ledger

`gates stats` SHALL resolve its change the same way the shim's other subcommands
do: `--change <name>` when given, else the current branch name (with `main`/
`master` resolving to no change). `--all` SHALL instead report every ledger file
under `.gatedloop/runs/`. Asking for a change with no ledger, or `--all` with no
ledgers, SHALL fail loud — a non-zero exit with an explicit message naming the
path it looked at — never an empty-but-green report.

#### Scenario: Default scope is the current branch

- **WHEN** `gates stats` runs with no scope flags on branch `<change>`
- **THEN** it reports `.gatedloop/runs/<change>.jsonl`

#### Scenario: A missing ledger fails loud

- **WHEN** the resolved change has no ledger file
- **THEN** the command exits non-zero with a message naming the missing path, and prints no report

#### Scenario: `--all` spans every recorded change

- **WHEN** `gates stats --all` runs in a repo with several ledger files
- **THEN** the report covers each change and a cross-change summary, in deterministic order

### Requirement: Output is a human table by default and a stable schema under `--json`

The default output SHALL be a human-readable table. `--json` SHALL emit a single
JSON document with a stable, documented shape: per-change objects carrying active
time, per-gate aggregates (time, share, runs, failures), per-task aggregates, the
unattributed bucket, the idle threshold applied, and data-quality counts
(malformed lines, rows missing usable timestamps). The human report SHALL end by
pointing at the scaffolding playbook as the next step.

#### Scenario: JSON mode is machine-consumable

- **WHEN** `gates stats --json` runs
- **THEN** stdout is exactly one JSON document in the documented shape, with nothing else interleaved

#### Scenario: The report hands off to the playbook

- **WHEN** the human-readable report prints
- **THEN** it ends with a pointer to the gate-economics playbook doc

### Requirement: Stats tolerates rows from other eras without crashing or silently dropping

`gates stats` SHALL accept rows carrying fields it does not know (such as the
`scope` field `scale-gate-cost` adds) and rows missing optional fields, aggregating
on the fields it can read. A line that cannot be parsed as a JSON object, or a row
without a usable `ts`, SHALL be excluded from aggregation but counted and disclosed
in the report — never a crash, never a silent drop.

#### Scenario: A `scope`-era row and a pre-`scope` row coexist

- **WHEN** one ledger file holds rows with and without a `scope` field
- **THEN** both aggregate normally and the report succeeds

#### Scenario: A malformed line is disclosed, not fatal

- **WHEN** a ledger file contains a line that is not valid JSON
- **THEN** the report still prints, and its data-quality section counts the skipped line

### Requirement: A stack-agnostic scaffolding playbook tells adopters what to do about gate cost

The plugin SHALL ship a short gate-economics playbook document covering, as
principles and gate shapes only: run the cheapest suites first, target a fast
per-task `ci`, key expensive builds on their inputs, keep the full suite at the
merge lane, and run one heavy gate per machine. It SHALL name no
project-specific tool (the stack-agnostic-prompts rule binds), and SHALL be
linked from `SETUP.md`.

#### Scenario: The playbook is discoverable from the adopter contract

- **WHEN** an adopter reads `SETUP.md`
- **THEN** it links to the gate-economics playbook

#### Scenario: The playbook stays stack-agnostic

- **WHEN** the playbook is reviewed against the stack-agnostic-prompts rule
- **THEN** every recommendation is a principle or a gate shape, with no named stack tool

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

### Requirement: Under a declared acceptance policy the outcomes view terminates at acceptance

When the manifest declares `approval.acceptance`, `gates stats --outcomes` SHALL
derive a change's terminal state as `accepted` when the ledger holds an `acceptance`
row with verdict `accept` whose tree equals the tree recorded on the change's `merge`
row; `merged` when a `merge` row exists without such an acceptance; and otherwise as
today. Under that policy **hands-off** SHALL require `accepted`, not merely `merged`,
and the hands-off share SHALL be computed over accepted changes divided by changes
that reached `merged` or `accepted`. `acceptance` rows with verdict `reject` SHALL be
counted under halts by their cause. When no acceptance policy is declared, the
terminal-state and hands-off rules SHALL be unchanged, and the report SHALL state that
the metric ends at `merged` because no acceptance policy is declared.

#### Scenario: Accepted and merged

- **WHEN** the policy is declared and a change's ledger holds an `accept` row pinning
  tree T and a `merge` row recording tree T, with no halt, intervention or taint rows
- **THEN** the report shows terminal state `accepted` and verdict `hands-off`

#### Scenario: Merged without acceptance

- **WHEN** the policy is declared and a change's ledger holds a `merge` row but no
  `accept` row for its tree
- **THEN** the report shows terminal state `merged`, verdict `assisted`, and names the
  missing acceptance as the reason

#### Scenario: A rejection is an escalation

- **WHEN** a change's ledger holds an `acceptance` row with verdict `reject` and cause
  `missing-oracle`
- **THEN** the `--all` halts-by-cause breakdown counts one `missing-oracle`

#### Scenario: Policy undeclared

- **WHEN** the manifest has no `approval.acceptance`
- **THEN** terminal states and hands-off are computed exactly as without this change,
  and the report states that the metric ends at `merged`

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
