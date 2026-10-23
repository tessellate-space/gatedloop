# epics Specification

## Purpose
Make a story of several changes a first-class object without a new artifact type: an epic is an ordinary change that its children name in `x-gatedloop-epic`, the link is validated, an epic is never implemented and is archived only after every child, and `gates epics`, `gates stats --epic` and the session brief show each child's state derived from the archive, the ledger and the plan.

## Requirements

### Requirement: A change names its epic, and the name is validated

A change MAY name an epic with a top-level `x-gatedloop-epic: <name>` key in its own
`.openspec.yaml`, where the epic is another change. `gates validate` SHALL fail, naming
the child, when the named epic is neither an active nor an archived change, when a
change names itself, when the named epic itself names an epic, or when an active
child names an archived epic.

#### Scenario: A child names an epic that exists

- **WHEN** change `lane-permissions` declares `x-gatedloop-epic: autonomous-dev` and
  `autonomous-dev` is an active change
- **THEN** `gates validate` passes

#### Scenario: A child names an epic that does not exist

- **WHEN** a change declares `x-gatedloop-epic: no-such-change`
- **THEN** `gates validate` fails, naming the change and the missing epic

#### Scenario: Epics nested two deep

- **WHEN** `autonomous-dev` itself declares `x-gatedloop-epic: roadmap`
- **THEN** `gates validate` fails, naming both changes

### Requirement: An epic is never implemented

`gates discipline check-implement` SHALL refuse to cut an implementation branch for a
change that any active change names as its epic, naming those children, whatever the
epic's schema.

#### Scenario: Cutting a branch for an epic

- **WHEN** `lane-permissions` names `autonomous-dev` as its epic and
  `git checkout -b autonomous-dev` is attempted
- **THEN** the hook denies it, naming `lane-permissions` as the work to implement

### Requirement: An epic is archived only after every child

`gates discipline check-archive <epic>` SHALL refuse while any change naming the epic
is not archived, listing each such child with its state. The existing merge check
SHALL still apply.

#### Scenario: Archiving an epic with an open child

- **WHEN** `autonomous-dev` has one archived child and one child in state
  `implementing`
- **THEN** archiving `autonomous-dev` is refused, naming the open child and its state

#### Scenario: Archiving a drained epic

- **WHEN** every child of `autonomous-dev` is archived
- **THEN** the archive is allowed

### Requirement: Child states are derived in code and rolled up

`gates epics [--json]` SHALL list every epic with each child's state and its tasks
done of total, derived from the archive directory, the ledger and `.openspec.yaml`:
`archived`, `merged`, `halted` (with its cause), `ready`, `implementing`, `approved` or
`proposed`. Where `gates stats --outcomes` classifies the child's ledger, its answer
SHALL decide the state. `gates stats --epic <name>` SHALL
report the existing per-change economics per child and in total.

#### Scenario: A mixed epic

- **WHEN** an epic has one archived child, one with a `ready` row, and one approved
  but not started
- **THEN** `gates epics` lists them as `archived`, `ready` and `approved`

#### Scenario: Economics for an epic

- **WHEN** `gates stats --epic autonomous-dev --json` runs
- **THEN** it reports each child's gate runs, gate minutes, red runs and halts,
  and their totals

### Requirement: The session brief shows active epics

The session brief SHALL print one line per active epic, summarising its children's
states, above the flat change list, and SHALL omit an active epic's children from
that list. A repository with no epics SHALL get a brief identical to one without this
requirement.

#### Scenario: A brief with an epic

- **WHEN** a session starts in a repository with one active epic of three children
- **THEN** the brief shows one epic line with the three states, and the flat list
  does not repeat the children

#### Scenario: No epics

- **WHEN** no change declares `x-gatedloop-epic`
- **THEN** the brief is unchanged
