# gate-binding Delta Specification

## ADDED Requirements

### Requirement: A surface may bind scoped commit oracles, selected err-full

A surface MAY declare per-surface overrides for the `ci` and `unit` gates. When a
scoped gate is invoked, the staged diff's hot set SHALL be computed by the existing
surface selection, and the scoped command SHALL run only when that hot set is exactly
one surface and that surface declares the override; for this decision, surfaces whose
pattern matches every path SHALL be ignored. In every other case — no hot surface, an
unmatched changed file, multiple hot surfaces, or a hot surface without the override —
the globally declared gate SHALL run. The fallback direction is pinned: scoping may
only ever narrow to a declared scoped command, never skip; when in doubt the full gate
runs.

#### Scenario: A single-surface diff with a scoped oracle

- **WHEN** the staged diff's hot set is exactly one surface that declares a scoped
  `ci`, plus a catch-all surface
- **THEN** `gates run ci` runs the scoped command and its exit code is the gate's

#### Scenario: A multi-surface diff

- **WHEN** the staged diff selects two or more non-catch-all surfaces
- **THEN** the global `ci` runs, regardless of what the surfaces declare

#### Scenario: A surface without the override

- **WHEN** the hot set is one surface and it declares no scoped `ci`
- **THEN** the global `ci` runs

### Requirement: The record names the oracle that ran, and the merge requires the full one

A marker or ledger row written by a scoped gate run SHALL record the scope it ran
under, distinguishably from a full run. Change completion SHALL require a green
**unscoped** `ci` for the branch head; a scoped marker MAY satisfy a per-task commit
gate but SHALL NOT satisfy the pre-merge requirement.

#### Scenario: A scoped green satisfies the commit, not the merge

- **WHEN** a task commit is gated with a fresh scoped `ci` marker for the staged tree
- **THEN** the commit is allowed, and the pre-merge check still demands a full `ci`
  green on the head before integration

#### Scenario: The ledger distinguishes oracles

- **WHEN** a scoped run and a full run both record their outcome
- **THEN** each row names its oracle scope, so an audit can tell which evidence backed
  which commit

### Requirement: Gate output is one line on green and everything on red

`gates run` SHALL capture the gate command's output and, on success, print a one-line
summary naming the gate, the scope it ran under, its duration, and where the full
output was saved; on failure it SHALL print the full captured output. A verbose flag
SHALL restore unfiltered streaming.

#### Scenario: A green gate stays quiet

- **WHEN** a declared gate exits zero
- **THEN** exactly one summary line is printed and the full output is available in a
  named file

#### Scenario: A red gate tells everything

- **WHEN** a declared gate exits non-zero
- **THEN** the full captured output is printed and the exit code is preserved
