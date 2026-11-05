# Spec Delta

## MODIFIED Requirements

### Requirement: A surface may bind scoped commit oracles, selected err-full

A surface MAY declare per-surface overrides for the `ci` and `unit` gates. When a
scoped gate is invoked, the relevant diff's hot set SHALL be computed by the existing
surface selection, and the scoped command SHALL run only when that hot set is exactly
one surface and that surface declares the override; for this decision, surfaces whose
pattern matches every path SHALL be ignored. A changed path that no such surface
matches SHALL count as unmatched even when a catch-all surface matches it. In every
other case — no hot surface, an unmatched changed file, multiple hot surfaces, or a
hot surface without the override — the globally declared gate SHALL run, except as
below for `unit`, and for `ci` under `loop.ci-scope: union`. The fallback direction is pinned: scoping may only ever narrow to a
declared scoped command, never skip; when in doubt the full gate runs.

For this decision, the relevant diff SHALL leave out the loop's own state under
`.gatedloop/` and the current change's own `openspec/changes/<change>/tasks.md`, where
the current change is the one the branch resolves to. Neither SHALL count as an
unmatched path or make a surface hot. Any other change's `tasks.md`, and every other
plan artifact, SHALL count as an ordinary path. The hot set reported for convention
review and live-check SHALL NOT change.

When `unit` is invoked and its working set selects two or more such surfaces with no
unmatched changed file, it SHALL run every hot surface's `unit` override and, once,
the global `unit` when any hot surface declares none. The run SHALL fail when any of
those commands fails, and its output and record SHALL name every surface whose
command ran.

Under `loop.ci-scope: union`, when `ci` is invoked and its staged diff selects two or
more such surfaces with no unmatched changed file, and every one of them declares a
`ci` override, it SHALL run each override once, under the same rules as a multi-surface
`unit` run, and record a scope naming every surface. When any of those surfaces
declares no `ci` override, the global `ci` SHALL run alone.

#### Scenario: A single-surface diff with a scoped oracle

- **WHEN** the staged diff's hot set is exactly one surface that declares a scoped
  `ci`, plus a catch-all surface
- **THEN** `gates run ci` runs the scoped command and its exit code is the gate's

#### Scenario: A multi-surface diff

- **WHEN** the staged diff selects two or more non-catch-all surfaces, and
  `loop.ci-scope` is absent or `single`
- **THEN** the global `ci` runs, regardless of what the surfaces declare

#### Scenario: A multi-surface diff under union

- **WHEN** `loop.ci-scope: union` is declared, the staged diff selects two
  non-catch-all surfaces that each declare a `ci` override, and every changed path is
  matched
- **THEN** `gates run ci` runs both overrides, its exit is the first non-zero one, and
  its marker and ledger row record a scope naming both surfaces

#### Scenario: A hot surface without a ci override under union

- **WHEN** `loop.ci-scope: union` is declared and the staged diff selects one surface
  with a `ci` override and one without
- **THEN** the global `ci` runs alone

#### Scenario: An unmatched path under union

- **WHEN** `loop.ci-scope: union` is declared and the staged diff holds files of two
  surfaces with `ci` overrides and one path no non-catch-all surface matches
- **THEN** the global `ci` runs, and its output names the unmatched path

#### Scenario: A surface without the override

- **WHEN** the hot set is one surface and it declares no scoped `ci`
- **THEN** the global `ci` runs

#### Scenario: An unmatched path beside a scoped surface

- **WHEN** the staged diff holds one file of a surface that declares a scoped `ci`
  and one file that only a catch-all surface, or no surface, matches
- **THEN** the global `ci` runs, and its output names the unmatched path

#### Scenario: A multi-surface unit run exercises every surface

- **WHEN** the working set selects two non-catch-all surfaces that each declare a
  `unit` override, and every changed path is matched
- **THEN** `gates run unit` runs both overrides, and its recorded scope names both
  surfaces

#### Scenario: One surface's red is the run's red

- **WHEN** a multi-surface `unit` run's first command passes and its second fails
- **THEN** the run exits non-zero, and both commands' verdicts are reported

#### Scenario: A hot surface without a unit override

- **WHEN** the working set selects one surface with a `unit` override and one
  without, and every changed path is matched
- **THEN** `gates run unit` runs the override and the global `unit`, once each

#### Scenario: A task commit's own tick does not widen the scope

- **WHEN** on a change branch, the staged diff holds one file of a surface that
  declares a scoped `ci` and the change's own `tasks.md`, and no surface covers
  `openspec/**`
- **THEN** `gates run ci` runs the scoped command

#### Scenario: The tick does not make a second hot surface

- **WHEN** the same diff is staged and `openspec/**` belongs to a surface of its own
- **THEN** `gates run ci` runs the scoped command

#### Scenario: Another change's tasks.md still errs full

- **WHEN** on a change branch, the staged diff holds one file of a scoped surface and
  another change's `tasks.md`, which no surface matches
- **THEN** the global `ci` runs, and its output names that `tasks.md` as unmatched

#### Scenario: Off a change branch nothing is exempt

- **WHEN** on `main`, the staged diff holds one file of a scoped surface and a
  change's `tasks.md`, which no surface matches
- **THEN** the global `ci` runs

### Requirement: The record names the oracle that ran, and the merge requires the full one

A marker or ledger row written by a scoped gate run SHALL record the scope it ran
under, distinguishably from a full run. Change completion SHALL require a green
**unscoped** `ci` for the branch head; a scoped marker MAY satisfy a per-task commit
gate but SHALL NOT satisfy the pre-merge requirement. A union-scoped `ci` marker is a
scoped marker: it SHALL NOT satisfy the READY or pre-merge requirement, and SHALL NOT
vouch for an ancestor in the audit.

#### Scenario: A scoped green satisfies the commit, not the merge

- **WHEN** a task commit is gated with a fresh scoped `ci` marker for the staged tree
- **THEN** the commit is allowed, and the pre-merge check still demands a full `ci`
  green on the head before integration

#### Scenario: The ledger distinguishes oracles

- **WHEN** a scoped run and a full run both record their outcome
- **THEN** each row names its oracle scope, so an audit can tell which evidence backed
  which commit

#### Scenario: A union green satisfies the commit, not READY

- **WHEN** a task commit is gated with a union-scoped `ci` marker under `loop.ci-scope:
  union`, and `loop.ci-at: ready` is declared
- **THEN** the commit is allowed, and `gates ledger record-ready` still refuses until
  an unscoped `ci` passes on the head

### Requirement: Both commit layers apply the same commit check

The git-layer commit hook SHALL run the same commit check as the tool-level commit
hook, including the ledger-grade and planning-grade allowances and, under `loop.ci-at:
ready`, the `unit` allowance. On a commit allowed on a `unit` marker, both layers SHALL
print the check's allow line, which names the mode, and SHALL run the authored-test
lock after it as they do for a `ci` marker.

#### Scenario: A ledger-only commit through the git layer

- **WHEN** only `.gatedloop/runs/<change>.jsonl` is staged and the commit is created by
  a path the tool-level hook does not see
- **THEN** the git-layer hook allows it with the ledger-grade verdict, and no `ci` run
  is required

#### Scenario: A unit-gated commit through either layer

- **WHEN** `loop.ci-at: ready` is declared, the branch names an active change, and
  only a `unit` marker matches the staged tree
- **THEN** the tool-level hook and the git-layer hook both allow the commit, both
  print the allow line naming `loop.ci-at: ready`, and both deny it when the
  authored-test lock fails

## ADDED Requirements

### Requirement: Union-scoped ci is declared by `loop.ci-scope`

`.gates.yaml` MAY declare `loop.ci-scope` as `single` (the default) or `union`. `gates
validate` SHALL fail, naming the key, on any other value. Absent, `ci` scoping SHALL
behave as under `single`: a multi-surface staged diff runs the global `ci`.

#### Scenario: An unknown value

- **WHEN** `loop.ci-scope: all` is declared
- **THEN** `gates validate` fails and names `loop.ci-scope` and its two values

#### Scenario: Key absent

- **WHEN** `.gates.yaml` declares no `loop.ci-scope` and the staged diff selects two
  surfaces that each declare a `ci` override
- **THEN** the global `ci` runs, as before
