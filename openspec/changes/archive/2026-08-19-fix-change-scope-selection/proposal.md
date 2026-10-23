# Fix change-scope selection

## Why

The 2026-08-18 field review (`docs/review-2026-08-18.md`, F1–F4) confirmed by
experiment that the deterministic selection layer — the one part of the system whose
whole job is making blocking gates impossible to skip — can skip a blocking gate.
`gates run live-check` computes the hot set from the working-tree diff, which is
empty at change completion when every task is committed, so the BLOCKING merge gate
prints "skipping (not a failure)" and exits 0 without running a single probe. A
live-check bound to `false` passes. This is exactly the silent-skip class the shim's
own docstring claims it exists to prevent, and `harden-unattended-loop` cannot land
first: its D1/D2 merge marker would record the vacuous green as a real one and
enforce it.

Three smaller defects in the same layer travel with it: rule-id resolution is a
substring check against the whole rules-doc (a dangling id validates green if the
string appears in any prose), glob matching lets patterns cross path separators
(`*.md` matches `docs/deep/x.md`), and none of the selection logic is tested — the
suite covers parsing and conventions sync, and a single clean-tree-on-branch test
would have caught F1.

## What Changes

- **Two baselines, decided by gate level, in code.** Task-level selection (`gates
  rules`, `gates surfaces`, the per-task convention-review scope) keeps the
  working-tree diff — its subject is the in-flight task. Change-level gates
  (`live-check`, and the hot-set input to anything else that judges the whole
  change) default to the change's diff against the merge target — merge-base
  `main...HEAD` — unioned with the working set. Never a prompt-remembered flag:
  relying on a skill to pass `--changed`/`--all` is the failure mode this repo is
  built against. `--changed` and `--all` remain as explicit overrides.
- **A change-level gate that selects nothing says so loudly.** An empty hot set at
  change level reports *why* it is empty (baseline used, files considered) rather
  than a bare skip, so a vacuous pass is at least visible when it is legitimate and
  diagnosable when it is not.
- **Rule-id resolution matches `### <id>` headings**, not substrings.
  `parse_conventions_doc` already parses exactly those headings; validation reuses
  it. A rule-id mentioned only in prose is dangling and fails `gates validate`.
- **Glob semantics are fixed or honestly documented.** Either `**`/`*` get
  path-separator-aware semantics, or the fail-hot behaviour (surfaces run hotter
  than declared, never colder) is stated in `SETUP.md` as the contract. Decided in
  design; the invariant either way is that over-matching is the only permitted
  direction of error.
- **Selection gets a test suite.** `_changed_files` baselines, `hot_surfaces`,
  `_matches`, and the `cmd_run` live-check path, including the clean-tree-on-branch
  case that reproduces F1, and the merge-target resolution on a repo whose default
  branch is not `main`.

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `gate-binding`: the hot-set rule gains the two-baseline distinction — task-level
  selection reads the working tree, change-level gates read the change's diff
  against the merge target — and a change-level empty hot set must be loud;
  rule-id resolution is heading-anchored rather than substring.

## Impact

- **Code**: `bin/gates` (`_changed_files`, `hot_surfaces`, `_matches`, `cmd_run`,
  `_errors`), `tests/` (new selection tests). No prompt changes: `skills/tdd-apply`
  §7.5 already calls bare `gates run live-check`, which is the point — the fix
  changes what that call selects, not what anyone types.
- **Dependencies**: hard prerequisite of `harden-unattended-loop` (see the note in
  its design Context: the merge marker must never be satisfiable by a vacuous
  pass). No dependency on any other in-flight change.
- **Adopters**: behaviour change is strictly in the safe direction — change-level
  gates that previously skipped will now run. A project whose live-check was
  passing vacuously will see it run (and possibly fail) for the first time; that is
  the defect being fixed, and the release note must say so.
