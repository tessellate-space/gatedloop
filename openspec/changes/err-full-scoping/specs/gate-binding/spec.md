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
below for `unit`. The fallback direction is pinned: scoping may only ever narrow to a
declared scoped command, never skip; when in doubt the full gate runs.

When `unit` is invoked and its working set selects two or more such surfaces with no
unmatched changed file, it SHALL run every hot surface's `unit` override and, once,
the global `unit` when any hot surface declares none. The run SHALL fail when any of
those commands fails, and its output and record SHALL name every surface whose
command ran.

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
