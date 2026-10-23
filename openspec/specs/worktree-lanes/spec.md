# worktree-lanes Specification

## Purpose
Make the multi-agent, multi-worktree lane a documented, supported pattern: N
implementer/author agents in isolated git worktrees feeding one serialized merge lane
in the primary checkout, with the properties that make it work stated rather than
rediscovered.

## Requirements

### Requirement: The worktree lane pattern is documented as supported

gatedloop's documentation SHALL describe the supported multi-worktree topology — one
worktree per concurrent agent, one serialized merge lane in the primary checkout,
stop-before-merge implementer discipline — including which guarantees are
per-worktree (markers, index, branch) and which are repo-wide (ledger, attestation,
the merge target). It SHALL document as a supported property that per-worktree
directory basenames namespace tooling that derives its project or instance name from
the directory, so gate runs in different worktrees do not collide with each other or
with a running dev stack. It SHALL state push-after-merge as recommended hygiene and
name where the loop accepts a local merge target and where origin is required.

#### Scenario: An adopter sets up a second lane

- **WHEN** an adopter follows the documentation to add a worktree lane
- **THEN** the documented steps yield a lane whose gates, markers, and branch
  discipline work without any undocumented workaround (no branch rename ritual, no
  "expect stale-marker denials" boilerplate)

#### Scenario: The namespacing property is stated, not folklore

- **WHEN** an adopter asks whether concurrent gate runs in two worktrees collide over
  shared directory-derived names
- **THEN** the documentation answers it: directory-basename-derived namespacing is a
  supported property of the pattern, with the caveat that name derivation belongs to
  the adopter's own tooling

### Requirement: A failing gate in a fresh worktree earns a setup hint

When a gate fails in a worktree that has no prior recorded gate history, the shim
SHALL append one line hinting that a freshly created worktree may lack installed
dependencies and pointing at the adopter's own manifest and gates as the place where
setup lives. The hint SHALL be stack-agnostic — it MUST NOT name any package manager,
build tool, or other project-specific command — SHALL appear at most once per
worktree, and SHALL never alter the gate's exit code.

#### Scenario: First failing gate in a new worktree

- **WHEN** a gate exits non-zero in a worktree where no gate has ever recorded an
  outcome
- **THEN** the failure output ends with a single hint that the worktree may need its
  dependencies installed per the project's own gates, and the exit code is the
  gate's own

#### Scenario: The hint names no stack

- **WHEN** the hint is printed
- **THEN** it references only the adopter's manifest and gate names, never a concrete
  tool or package manager

#### Scenario: An established worktree gets no hint

- **WHEN** a gate fails in a worktree that has previously recorded a gate outcome
- **THEN** the failure output is unchanged — no hint is appended
