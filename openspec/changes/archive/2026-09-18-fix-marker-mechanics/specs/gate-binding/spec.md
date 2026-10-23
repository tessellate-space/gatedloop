# gate-binding Delta Specification

## ADDED Requirements

### Requirement: Marker freshness is blind to the durable ledger

The tree hash a gate marker records, and the tree hash a marker check compares
against, SHALL exclude every path under `.specloop/runs/**` (the durable ledger).
The normalization SHALL be applied identically when the marker is written and when
it is checked, so the compare remains a single hash equality. Any delta outside
`.specloop/runs/**` SHALL still invalidate the marker exactly as today.

#### Scenario: Staging the gate's own ledger row keeps the marker fresh

- **WHEN** a green `gates run ci` writes a marker and appends its ledger row, and the
  row is then staged alongside the task's files
- **THEN** the commit gate's marker check still matches — the ledger row is the only
  delta and it is outside the compared hash

#### Scenario: Committing the merge ledger row does not restart the chase

- **WHEN** a green `gates run live-check` has written its marker and the run's ledger
  row is subsequently committed
- **THEN** the live-check marker still matches the resulting head tree

#### Scenario: A real edit still stales the marker

- **WHEN** any tracked path outside `.specloop/runs/**` changes after the marker was
  written
- **THEN** the marker check fails as stale, exactly as before

### Requirement: A resolved-empty live-check records a skip verdict

A `gates run live-check` whose resolved check set is empty — because no surface is
hot, because the hot surfaces declare no `live-check`, or because no surface in the
manifest declares one at all — SHALL write a marker recording a `skip` verdict for
the current head tree, carrying the same evidence the skip message prints (baseline
kind, resolved merge target, number of files considered), and SHALL append a ledger
row recording the same verdict. The merge gate SHALL accept a skip-verdict marker
whose tree matches, and its report SHALL name the verdict and its evidence. A
missing marker SHALL still deny — a recorded skip is distinguishable from "never
ran" — and a declared live-check that ran and failed SHALL still write no marker.

#### Scenario: A docs-only diff can merge after an honest skip

- **WHEN** a change's diff selects no surface with a `live-check` and
  `gates run live-check` is run on the branch head
- **THEN** the run exits 0, records a skip verdict for that head tree, and the merge
  gate accepts it, reporting the skip and its evidence

#### Scenario: A repo with no live-check declared anywhere can merge

- **WHEN** no surface in the manifest declares a `live-check` and
  `gates run live-check` is run on the branch head
- **THEN** the merge is no longer permanently denied: the skip verdict satisfies the
  merge gate for that tree

#### Scenario: Never-ran still blocks

- **WHEN** a merge is attempted and no live-check marker exists at all
- **THEN** the merge gate denies, telling the operator to run `gates run live-check`

#### Scenario: A red declared probe records no satisfying verdict

- **WHEN** a hot surface's declared live-check runs and exits non-zero
- **THEN** no marker is written and the merge gate still denies

### Requirement: Identical live-check recipes run once per invocation

Within a single `gates run live-check` invocation — including `--all` — hot surfaces
that bind the same live-check command SHALL cause exactly one execution of that
command, attributed in the output to every surface that binds it. The run's exit
code SHALL aggregate exactly as if each surface had run it.

#### Scenario: Two surfaces, one recipe, one run

- **WHEN** two hot surfaces declare the same live-check command and
  `gates run live-check --all` executes
- **THEN** the command runs exactly once and the output names both surfaces for it

#### Scenario: Distinct recipes still all run

- **WHEN** hot surfaces declare two different live-check commands
- **THEN** both commands run, once each

### Requirement: The merge gate validates the tree being merged in

A merge gate check SHALL validate the live-check marker against the head tree of the
ref being merged when that ref can be resolved from the merge invocation, falling
back to the current checkout's HEAD tree otherwise. A denial SHALL name the tree(s)
checked and instruct the operator to run `gates run live-check` on the change
branch's head — guidance that the accepted-tree semantics make true.

#### Scenario: A branch-head marker satisfies a squash-merge from the merge target

- **WHEN** `gates run live-check` passed on the change branch's head and a squash
  merge of that branch is attempted from the merge target's checkout
- **THEN** the merge gate resolves the incoming ref's head tree, finds the marker
  fresh for it, and allows the merge

#### Scenario: A stale branch marker still denies

- **WHEN** the change branch gained a commit after its live-check marker was written
  and a squash merge is attempted
- **THEN** the merge gate denies: the marker does not match the incoming head tree

### Requirement: A ledger-only staged diff earns a ledger-grade commit

`discipline check-commit` SHALL allow a non-empty staged diff consisting solely of
paths under `.specloop/runs/**` without requiring a `ci` marker, printing an
explicit ledger-grade verdict. A staged diff mixing ledger paths with any other
path SHALL be held to the full requirement for that diff.

#### Scenario: Committing only the merge row

- **WHEN** the only staged path is `.specloop/runs/<change>.jsonl`
- **THEN** the commit is allowed with a printed ledger-grade verdict, no `ci` marker
  required

#### Scenario: A mixed diff gets no discount

- **WHEN** the staged diff contains a ledger path and a source file
- **THEN** the full commit requirement applies to the staged tree

## MODIFIED Requirements

### Requirement: An empty change-level hot set is reported with evidence

When change-level selection produces no hot surfaces, the shim SHALL report the
baseline kind, the resolved merge target, and the number of changed files
considered. The exit code SHALL remain zero — an empty hot set is a legitimate
outcome — but the skip SHALL never be a bare one-liner indistinguishable from a
selection defect, and for `live-check` the same evidence SHALL also be recorded in
the skip verdict's marker and ledger row so the decision is auditable after the
fact, not only visible in scrollback.

#### Scenario: A docs-only change on a project with code-only surfaces

- **WHEN** the change's diff touches no surface's globs
- **THEN** `gates run live-check` exits 0 and its output names the baseline, the
  merge target, and the file count it selected against

#### Scenario: The printed evidence is also the recorded evidence

- **WHEN** `gates run live-check` skips on an empty resolved check set
- **THEN** the skip verdict it records carries the same baseline, merge target, and
  file count that the message printed
