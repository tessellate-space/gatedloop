# escalation-record Specification

## Purpose
Every time the loop stops short of done, or a human steps into it, the durable ledger
says so with a cause from a closed vocabulary — recorded by the shim, detected by
hooks where a hook can see the event, and never left as free text — so escalations
can be counted, categorised and turned into the next oracle or spec fix.

## Requirements

### Requirement: Escalation causes are a closed set held in one place

The shim SHALL define exactly one closed set of escalation causes:
`missing-oracle` (no declared gate could decide the question), `weak-spec` (the spec
is ambiguous, contradictory or underspecified), `oracle-conflict` (two gates or
reviewers disagree about the same tree), `stalled` (the attempt cap was reached),
`environment` (a declared precondition failed — the gate exited 75), `budget` (the
change's token budget was reached), and `other` (anything else, which MUST carry
free-text detail). Every writer and reader of a cause SHALL resolve it against that
one definition. Extending the set SHALL be a spec change to this capability, never a
prompt-only edit.

#### Scenario: A cause outside the set is refused

- **WHEN** a halt is recorded with a cause that is not one of the seven
- **THEN** nothing is written, the command exits non-zero, and the message names the
  cause given and lists the accepted set

#### Scenario: `other` without detail is refused

- **WHEN** a halt is recorded with cause `other` and no detail text
- **THEN** nothing is written, the command exits non-zero, and the message says that
  `other` requires detail

#### Scenario: A budget halt is accepted

- **WHEN** a halt is recorded with cause `budget` after `gates run` refused on the token budget
- **THEN** the halt row is written with cause `budget`

### Requirement: A halt is a ledger event written by the shim

`gates halt record <cause> --task <N.M> [--detail <text>]` SHALL append one row to the
change's durable ledger with the event name `halt`, the task, the current head tree,
the cause, and the detail (or none). The row SHALL be written through the same
append-only ledger writer as every gate row, and SHALL carry the fixed row shape:
the ledger row fields gain `cause` and `detail`, appended to the shape as an additive
union so that rows of every other kind carry them as absent and readers from before
this change are unaffected. A halt row SHALL never read as a gate outcome: it
contributes no gate time, no failed attempt and no green record to any report or join.

#### Scenario: A halt is recorded with a cause

- **WHEN** `gates halt record stalled --task 2.3 --detail "ci red after 2 attempts"`
  runs on a change branch
- **THEN** one row is appended to `.gatedloop/runs/<change>.jsonl` with `gate: "halt"`,
  `task: "2.3"`, `cause: "stalled"`, the detail text, and the head tree

#### Scenario: A halt row is not a gate row

- **WHEN** `gates stats` aggregates a ledger that holds `halt` rows
- **THEN** they contribute nothing to any gate's runs, failures or time, and they can
  never satisfy the audit's join on green-`ci` trees

#### Scenario: Recording off a change branch

- **WHEN** `gates halt record` runs with no change resolvable (the merge target is
  checked out and no `--change` is given)
- **THEN** it exits non-zero naming the missing change, and writes nothing

### Requirement: Every ledger row records whether it was written inside an agent session

Every row the ledger writer appends SHALL carry a `session` field: `agent` when the
Claude Code session marker (`CLAUDECODE`) is present in the writer's environment, else
`human`. The field SHALL be set by the one ledger writer, not by each caller, so no row
kind can omit it. It is the same discriminator the git-layer commit hook already uses
to scope itself to agent sessions. Rows written before this change SHALL read as
unknown, never as either value.

#### Scenario: A gate run inside a session

- **WHEN** `gates run ci` is invoked from within a Claude Code session
- **THEN** its ledger row carries `session: "agent"`

#### Scenario: A gate run from a plain terminal

- **WHEN** `gates run ci` is invoked with the session marker absent from the
  environment
- **THEN** its ledger row carries `session: "human"`

#### Scenario: A row from before the field existed

- **WHEN** a reader encounters a row with no `session` key
- **THEN** it treats the session as unknown and never infers agent or human from any
  other field

### Requirement: A human turn requested through the question tool is recorded by a hook

A `PreToolUse` hook on the `AskUserQuestion` tool SHALL append an `intervention` row
with cause `ask` to the current change's ledger whenever a change branch is checked
out in the repository the session acts on, carrying the first question's text
(truncated) as detail. The hook SHALL only record — it SHALL never deny or alter the
tool call — and SHALL be a silent no-op when no change branch is checked out. The
same row SHALL be writable by hand via `gates intervention record ask --task <N.M>
[--detail <text>]` for a pause that does not go through the tool, and the loop's
prompts SHALL say so at each point they pause for a human. Self-reporting an `ask`
is acceptable because it can only make a run look less autonomous, never more.

#### Scenario: The interactive loop pauses to ask

- **WHEN** the loop on a change branch calls the `AskUserQuestion` tool
- **THEN** before the question is shown, one `intervention` row with cause `ask` and
  the question text as detail is appended to that change's ledger, and the tool call
  proceeds unchanged

#### Scenario: A question asked off any change branch

- **WHEN** `AskUserQuestion` is called while the merge target is checked out
- **THEN** the hook writes nothing and exits allowing the call

#### Scenario: The hook cannot write

- **WHEN** the ledger cannot be appended to (for example the directory is
  unwritable)
- **THEN** the hook reports the failure on stderr and still allows the tool call — a
  recording failure MUST NOT block the human turn it was trying to record

### Requirement: A human-gated commit is classified as an intervention by the audit

When the post-hoc audit joins a new commit on the change branch to the ledger's
green-`ci` rows and every matching green-`ci` row carries `session: "human"`, the
audit SHALL append one `intervention` row with cause `human-commit`, the commit's SHA
and tree, to the change's ledger. A commit with at least one matching `agent`-session
green-`ci` row SHALL NOT be classified as an intervention. A commit whose matching rows
all lack a `session` value SHALL NOT be classified either way, and SHALL be counted as
unclassifiable. A commit with no green-`ci` row at all keeps today's behaviour: it is
tainted, not classified. The audit SHALL not classify the same commit twice.

#### Scenario: A human runs the gate and commits on the lane

- **WHEN** a green `ci` row for tree T was written with `session: "human"`, a commit
  with tree T lands on the change branch, and the audit runs
- **THEN** one `intervention` row with cause `human-commit` and that commit's SHA is
  appended, and no taint is recorded

#### Scenario: An agent-gated commit is not an intervention

- **WHEN** the only green `ci` row for a commit's tree carries `session: "agent"`
- **THEN** the audit appends nothing for that commit

#### Scenario: Evidence from before the field existed

- **WHEN** a commit's matching green-`ci` rows have no `session` value
- **THEN** the audit records no intervention and no taint for it, and the outcomes
  report counts the commit as unclassifiable

#### Scenario: The audit does not re-classify

- **WHEN** the audit runs again over a commit it already classified as `human-commit`
- **THEN** no second `intervention` row is appended for that SHA

### Requirement: What the record cannot classify is disclosed, not zeroed

Any reader that aggregates halts or interventions SHALL disclose, alongside its
counts: the number of `halt` rows whose cause is missing or outside the set, the
number of rows without a `session` value, and the number of commits the audit could
not classify. It SHALL never report a zero it cannot stand behind. A malformed row
SHALL be counted and skipped, never a crash and never a silent drop.

#### Scenario: A halt row with an unknown cause

- **WHEN** the ledger holds a `halt` row whose `cause` is not in the set (written by a
  future or foreign tool)
- **THEN** the outcomes report excludes it from the by-cause breakdown, counts it under
  malformed halts, and still prints

#### Scenario: Pre-era rows

- **WHEN** a ledger mixes rows with and without `session`
- **THEN** the report states how many rows carried no session value and that
  human-commit classification is unavailable for them

### Requirement: A stalled halt says whether a fresh restart remains

A `stalled` halt row SHALL carry `restart_available`, computed by the shim from the
task's `restart` rows and `loop.fresh-restarts`, never supplied by the caller. `gates
stats --outcomes` SHALL report, per change, the number of restarts and how many of
them were followed by the task reaching a green `ci` and being committed. A restart
SHALL NOT be counted as an intervention.

#### Scenario: Halting with a restart left

- **WHEN** an implementer records `gates halt record stalled --task 1.2` and task 1.2
  has not been restarted under `loop.fresh-restarts: 1`
- **THEN** the halt row carries `restart_available: true`

#### Scenario: A restart that recovered

- **WHEN** task 1.2 was restarted and then reached a green `ci` and its task commit
- **THEN** `gates stats --outcomes` counts one restart and one recovered restart for
  the change, and no intervention
