# parallel-planning Delta Specification

## Purpose

Let planning proceed while an implementer holds a checkout: gate enforcement acts on
the repository the guarded command actually runs in, docs-only commits are gated at
planning grade, and proposal scaffolding obeys the same branch discipline as proposal
authoring so a refusal leaves the tree unchanged.

## ADDED Requirements

### Requirement: Gate enforcement resolves the repository from the guarded command

Every hook-enforced gate check SHALL evaluate its evidence (index tree, markers,
branch, ledger) against the repository in which the guarded command will execute,
resolved from the hook input's working directory. Only when the hook input carries no
working directory SHALL the session project directory be used as a fallback. A gate
MUST NOT deny a command based on the state of a repository other than the one the
command acts on.

#### Scenario: A commit in a secondary worktree with a green marker

- **WHEN** an agent in a git worktree has run the required gate green on the exact
  staged tree, and the primary checkout has no such marker
- **THEN** the commit gate reads the worktree's own index and marker store and allows
  the commit

#### Scenario: A commit in a secondary worktree without a green marker

- **WHEN** an agent in a git worktree attempts to commit and no fresh required-gate
  marker matches that worktree's staged tree
- **THEN** the commit gate denies with a message naming the missing gate, regardless
  of any marker present in the primary checkout

#### Scenario: The hook input carries no working directory

- **WHEN** a gate hook receives input without a usable working directory field
- **THEN** it falls back to the session project directory and states nothing —
  behavior is identical to today's in the single-checkout case

### Requirement: A planning-only staged tree is gated at planning grade

When every path in the staged diff is a planning file — under the OpenSpec planning
home or the manifest's declared conventions source — the commit gate SHALL be
satisfied by manifest validation and planning-artifact validation both exiting zero,
instead of by a green `ci` marker. If any staged path is not a planning file, the
full `ci` requirement SHALL apply to the whole commit.

#### Scenario: A docs-only proposal commit

- **WHEN** the staged diff touches only files under the planning home (and/or the
  declared conventions source) and both validations pass
- **THEN** the commit is allowed with no `ci` marker present

#### Scenario: A docs-only commit with an invalid artifact

- **WHEN** the staged diff is planning-only but manifest or planning-artifact
  validation exits non-zero
- **THEN** the commit is denied and the message names the failing validation

#### Scenario: A mixed commit

- **WHEN** the staged diff contains a planning file and any non-planning file
- **THEN** the planning-grade path does not apply and the commit requires a fresh
  green `ci` marker for the staged tree

### Requirement: Proposal authoring is permitted on the merge target and on plan branches

The proposal-authoring discipline SHALL permit authoring when the current branch is
the merge target or a `plan/*` branch based on the merge target, and SHALL refuse it
anywhere else. The refusal message SHALL state the rationale and the permitted
locations.

#### Scenario: Authoring in a plan worktree while an implementer runs

- **WHEN** an implementer holds the change branch in one worktree and a proposal is
  authored in another worktree on a `plan/*` branch based on the merge target
- **THEN** the authoring proceeds, and the implementer's gates are unaffected

#### Scenario: Authoring on a feature branch

- **WHEN** proposal artifacts are written on a branch that is neither the merge
  target nor a `plan/*` branch
- **THEN** the write is refused with the rationale and the permitted locations named

### Requirement: A refused proposal leaves the tree unchanged

The branch discipline that gates proposal authoring SHALL also gate the scaffold step
that creates a change directory. When any part of the proposal flow is refused, the
refusal MUST NOT leave a partially created change on the working tree; if debris from
an earlier partial run exists, the refusal message SHALL name it and how to remove it.

#### Scenario: Scaffolding on a disallowed branch

- **WHEN** a new change scaffold is attempted on a branch where proposal authoring
  would be refused
- **THEN** the scaffold itself is refused before any directory is created, citing the
  same rationale as the authoring refusal

#### Scenario: Debris from an earlier stranded scaffold

- **WHEN** a proposal step is refused and an unproposed change directory already
  exists from an earlier partial run
- **THEN** the refusal message names that directory and the cleanup command
