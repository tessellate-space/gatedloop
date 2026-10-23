# parallel-planning Delta Specification

## MODIFIED Requirements

### Requirement: Gate enforcement resolves the repository from the guarded command

Every hook-enforced gate check SHALL evaluate its evidence (index tree, markers,
branch, ledger) against the repository in which the guarded command will actually
execute. That repository SHALL be resolved from the guarded command itself — an
explicit `git -C <dir>`, a `GIT_DIR`/`GIT_WORK_TREE` assignment carried by the
command, or the last `cd <dir>` preceding the git invocation in a compound command —
before any session-derived directory is consulted. Only when the command carries no
directory signal SHALL the hook input's working directory be used, and only when that
too is absent SHALL the session project directory be the fallback. A gate MUST NOT
deny a command based on the state of a repository other than the one the command acts
on. The command-to-directory resolution SHALL be deterministic shim code with test
coverage, not shell-script parsing.

#### Scenario: A background agent commits via `cd` into a secondary worktree

- **WHEN** an agent whose shell resets its working directory per call issues
  `cd <worktree> && git commit …`, the worktree's own marker store holds a green
  required-gate marker for its staged tree, and the session cwd is the primary
  checkout
- **THEN** the commit gate evaluates the worktree named in the command — not the
  session's checkout — and allows the commit

#### Scenario: A commit names its repository with `git -C`

- **WHEN** a guarded command is issued as `git -C <worktree> commit …` from any
  working directory
- **THEN** the gate resolves `<worktree>` as the repository under check, regardless
  of the hook input's cwd

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

#### Scenario: The command carries no directory signal

- **WHEN** a guarded command names no directory of its own
- **THEN** the hook input's working directory is used, falling back to the session
  project directory — behavior identical to today's in the single-checkout case

#### Scenario: The hook input carries no working directory

- **WHEN** a guarded command names no directory of its own and the gate hook receives
  input without a usable working directory field
- **THEN** it falls back to the session project directory and states nothing —
  behavior is identical to today's in the single-checkout case

### Requirement: Proposal authoring is permitted on the merge target and on plan branches

The proposal-authoring discipline SHALL permit authoring when the current branch is
the merge target, a `plan/*` branch based on the merge target, or a branch matching a
pattern the manifest explicitly declares as accepted for proposing. Declared patterns
SHALL be validated at manifest load and SHALL NOT waive the requirement that a
non-target branch share history with the merge target. When no patterns are declared,
the accepted set SHALL be exactly the merge target and `plan/*`. Authoring anywhere
else SHALL be refused with the rationale and the permitted locations named.

#### Scenario: Authoring in a plan worktree while an implementer runs

- **WHEN** an implementer holds the change branch in one worktree and a proposal is
  authored in another worktree on a `plan/*` branch based on the merge target
- **THEN** the authoring proceeds, and the implementer's gates are unaffected

#### Scenario: Authoring on a manifest-declared branch pattern

- **WHEN** the manifest declares an accepted branch pattern, and a proposal is
  authored on a branch matching it that shares history with the merge target
- **THEN** the authoring proceeds without any branch rename

#### Scenario: A declared pattern does not admit an orphan branch

- **WHEN** a branch matches a declared accepted pattern but shares no history with
  the merge target
- **THEN** authoring is refused, exactly as for an orphan `plan/*` branch

#### Scenario: Authoring on a feature branch

- **WHEN** proposal artifacts are written on a branch that is neither the merge
  target nor a `plan/*` branch, and the manifest declares no accepted patterns
- **THEN** the write is refused with the rationale and the permitted locations named

#### Scenario: Authoring on an undeclared feature branch

- **WHEN** proposal artifacts are written on a branch that is neither the merge
  target, nor `plan/*`, nor a declared pattern match
- **THEN** the write is refused with the rationale and the permitted locations named

### Requirement: A planning-only staged tree is gated at planning grade

When every path in the staged diff is a planning file — under the OpenSpec planning
home or the manifest's declared conventions source — the commit gate SHALL be
satisfied by manifest validation and planning-artifact validation both exiting zero,
instead of by a green `ci` marker. Planning-artifact validation SHALL be appropriate
to the stage each staged change is at: a change whose artifacts do not yet include
validatable delta content (a deliberately proposal-only backlog entry) SHALL be
validated for the artifacts it has, not refused for lacking artifacts it does not
claim to have, and the allow message SHALL name the stage that was validated. A
change with delta content SHALL be fully validated as today. If any staged path is
not a planning file, the full `ci` requirement SHALL apply to the whole commit. A
stage that cannot be determined SHALL fail loud, never pass silently.

#### Scenario: A docs-only proposal commit

- **WHEN** the staged diff touches only files under the planning home (and/or the
  declared conventions source) and both validations pass
- **THEN** the commit is allowed with no `ci` marker present

#### Scenario: A docs-only commit with an invalid artifact

- **WHEN** the staged diff is planning-only but manifest or planning-artifact
  validation exits non-zero
- **THEN** the commit is denied and the message names the failing validation

#### Scenario: A proposal-only backlog entry is committed alone

- **WHEN** the staged diff touches only a change directory containing a proposal
  (and its change metadata) with no delta specs yet, and manifest validation passes
- **THEN** the commit is allowed, and the message names the proposal-only stage it
  validated — no filler delta spec is required

#### Scenario: A change with delta specs is fully validated

- **WHEN** the staged diff touches a change directory that contains delta content
- **THEN** the full planning-artifact validation applies, and a validation failure
  denies the commit naming the failing validation

#### Scenario: The stage cannot be determined

- **WHEN** the staged diff is planning-only but the change's artifact status cannot
  be read
- **THEN** the commit is denied with a message naming the failed status read, never
  allowed on missing evidence

#### Scenario: A mixed commit

- **WHEN** the staged diff contains a planning file and any non-planning file
- **THEN** the planning-grade path does not apply and the commit requires a fresh
  green `ci` marker for the staged tree
