## Purpose

Reading the gate-cost story back out of the durable ledger: `gates stats` turns
`.specloop/runs/<change>.jsonl` into the bottleneck report field report #18 derived
by hand, and a stack-agnostic playbook tells the adopter what to do about what it
shows.

## ADDED Requirements

### Requirement: `gates stats` reports gate economics from the durable ledger

`gates stats` SHALL read the durable ledger (`.specloop/runs/<change>.jsonl`) and
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
under `.specloop/runs/`. Asking for a change with no ledger, or `--all` with no
ledgers, SHALL fail loud — a non-zero exit with an explicit message naming the
path it looked at — never an empty-but-green report.

#### Scenario: Default scope is the current branch

- **WHEN** `gates stats` runs with no scope flags on branch `<change>`
- **THEN** it reports `.specloop/runs/<change>.jsonl`

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
