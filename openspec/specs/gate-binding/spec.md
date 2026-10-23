# gate-binding Specification

## Purpose
How an abstract gate name becomes a project's real command and an enforceable verdict. It covers the manifest's gates and surfaces, change-level hot-set selection, scoped and full oracles, quiet-on-green output, preconditions, and the tree-keyed markers the hooks compare, so the loop's gates stay stack-agnostic and deterministic.

## Requirements

### Requirement: The gate-binding seam is named for what it binds
The shim, its manifest, its JSON schema, its template, and its onboarding command SHALL be named after gates rather than after a harness.

#### Scenario: An adopter invokes the shim
- **WHEN** the plugin is installed and an adopter runs the shim from the Bash tool
- **THEN** `gates validate`, `gates run <gate>`, `gates surfaces`, `gates rules`, and `gates init` all resolve and behave as their predecessors did

#### Scenario: An adopter scaffolds a new project
- **WHEN** the onboarding command runs in a project with no manifest
- **THEN** it writes `.gates.yaml` carrying a `gatesVersion` key, and no file named `.harness.yaml` is created

#### Scenario: The manifest is validated against its schema
- **WHEN** a `.gates.yaml` is validated
- **THEN** it is checked against `schema/gates.schema.json`, and the gate contract, `surfaces[]` shape, and hot-set rule are unchanged from the previous name

### Requirement: No shipped asset refers to the retired name
Shipped prompts, skills, agents, hooks, and documentation SHALL NOT invoke or reference the retired name, except in the compatibility forwarder and in explicit migration guidance.

#### Scenario: A shipped prompt invokes a gate
- **WHEN** any command, skill, or agent instructs that a gate be run
- **THEN** it names the new shim, so an adopter following the prompt never triggers the deprecation path

#### Scenario: The repository is swept for stale references
- **WHEN** the repository is searched for the retired name after this change
- **THEN** the only matches are the compatibility forwarder, the migration notes in the reader-facing docs, and historical records such as archived changes and the design memo

### Requirement: Change-level gates select against the change, not the working tree

The shim SHALL compute two changed-file baselines, chosen by what is being run and
never by a caller-remembered flag. Task-level selection (`gates rules`, `gates
surfaces`) SHALL use the working set (unstaged + staged + untracked). Change-level
gate execution (`gates run live-check`) SHALL use the union of the working set and
the diff between the merge target and `HEAD` (merge-base diff). The explicit
`--changed` and `--all` overrides SHALL continue to apply to both.

#### Scenario: Live-check on a clean change branch

- **WHEN** every task of a change is committed on its branch, the tree is clean,
  and `gates run live-check` runs with no override flags
- **THEN** the hot set is computed from the branch's diff against the merge target
- **AND** every hot surface's live-check runs, and the command exits non-zero if
  any probe fails

#### Scenario: Live-check mid-change with a dirty tree

- **WHEN** some tasks are committed and further edits are uncommitted
- **THEN** the hot set covers both the committed branch diff and the working set

#### Scenario: Task-level selection is unchanged

- **WHEN** `gates rules` or `gates surfaces` runs during a task with no override
- **THEN** the selection reads only the working set, so the per-task review scope
  does not grow with the change's earlier commits

### Requirement: Merge-target resolution is generic and degrades loudly

The shim SHALL resolve the merge target without hard-coding a branch name — the
remote's default branch when a remote exists, else a local `main` or `master`.
When no target resolves or no merge base exists, the shim SHALL fall back to the
working-set baseline and SHALL report the degradation; the fallback SHALL NOT be
silent.

#### Scenario: No merge target can be resolved

- **WHEN** `gates run live-check` runs in a repo with no remote and no
  `main`/`master` branch
- **THEN** selection falls back to the working set
- **AND** a message names the fallback and the reason

#### Scenario: Running on the target branch itself

- **WHEN** `gates run live-check` runs with the merge target checked out
- **THEN** the merge-base diff contributes nothing and the working set alone
  drives selection, without any degradation warning

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

### Requirement: Rule-ids resolve against headings, not substrings

`gates validate` SHALL resolve a rule-id only against the `### <id>` heading ids
of the conventions rules-doc. A rule-id that appears in the doc's prose but has no
heading SHALL fail validation as dangling.

#### Scenario: A dangling id mentioned in prose

- **WHEN** a surface names rule-id `retired-rule` and the rules-doc contains the
  string "retired-rule" only inside another rule's prose
- **THEN** `gates validate` exits non-zero naming the dangling id

#### Scenario: A heading without sync metadata still resolves

- **WHEN** a rules-doc section has a `### <id>` heading but no `Applies to:` or
  `Rule:` lines
- **THEN** the id resolves for validation and review purposes

### Requirement: Surface matching may only err hot

Glob matching SHALL NOT select fewer surfaces than a path-separator-exact reading
of the manifest would select. Over-selection is permitted and documented;
under-selection is a defect.

#### Scenario: The error direction is pinned

- **WHEN** a glob's approximate matching disagrees with its exact reading for some
  path
- **THEN** the disagreement selects a superset of surfaces, never a subset

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

### Requirement: A gate may declare a precondition command

The manifest SHALL accept, for every gate value and every surface `live-check`
value, either the existing scalar command string or a mapping
`{run: <command>, requires: <command>}`. A scalar SHALL keep its exact current
behavior and be equivalent to a mapping with only `run`. `requires` is optional
and is itself just a command — the shim never inspects either body.

`gates validate` SHALL reject loudly: a mapping whose `run` is missing, not a
string, or empty; a `requires` that is present but not a non-empty string; and
any key other than `run` and `requires`.

#### Scenario: Scalar gate values are unchanged

- **WHEN** a manifest declares `gates: {ci: "make test"}` and `gates run ci` is invoked
- **THEN** behavior is byte-for-byte today's: the command runs, the exit code is returned, markers and ledger rows are written as before

#### Scenario: Mapping form validates

- **WHEN** a manifest declares `integration: {run: "cmd-a", requires: "cmd-b"}` and a surface `live-check: {run: "cmd-c", requires: "cmd-b"}`
- **THEN** `gates validate` accepts the manifest

#### Scenario: Malformed mapping fails loud

- **WHEN** a gate value is a mapping missing `run`, with an empty `requires`, or with an unknown key
- **THEN** `gates validate` exits non-zero naming the gate and the defect, and never treats the mapping as a command string

### Requirement: A failed precondition is a distinct outcome, not a gate failure

When a gate (or a hot surface's live-check) declares `requires`, `gates run`
SHALL execute the precondition first. On non-zero, the shim SHALL report
`precondition '<cmd>' failed (exit N) — the gate itself was not run`, SHALL NOT
run the gate body, SHALL NOT write the gate's marker, SHALL NOT write a ledger
row claiming the gate was exercised, and SHALL exit with the reserved
precondition exit code 75 — distinct from both success and an ordinary gate
failure and documented in the adopter-facing contract. A precondition-failure
ledger row (see manifest of record in design) MUST be distinguishable from a
gate-run row and MUST never read as a green run.

#### Scenario: Precondition fails

- **WHEN** `gates run integration` is invoked and the gate's `requires` command exits 3
- **THEN** the shim prints the precondition-failed report naming the command and its exit code, does not run the gate body, writes no `integration` marker, writes no row claiming the gate ran, and exits 75

#### Scenario: Precondition passes

- **WHEN** the gate's `requires` command exits 0
- **THEN** the gate body runs and success/failure semantics (exit code, marker, ledger row) are exactly today's

#### Scenario: Live-check precondition fails for a hot surface

- **WHEN** `gates run live-check` selects a hot surface whose `live-check` declares a `requires` that exits non-zero
- **THEN** that surface's probe body is not run, no `live-check` marker is written, and the overall run exits 75 with the precondition-failed report

#### Scenario: A precondition failure can never satisfy enforcement

- **WHEN** a precondition fails and any marker- or ledger-based check (commit gate, taint resolution) later reads the record
- **THEN** nothing written by the precondition failure satisfies the check — only a genuinely green gate run can

### Requirement: The loop treats precondition-failed as an environment problem

The tdd-apply loop and the autonomous implementer SHALL treat the precondition
exit path as "the environment was absent": the response is to fix or boot the
environment, never to modify code, retry the gate unchanged, or investigate the
gate body's output. An unattended implementer SHALL HALT at the boundary and
report the precondition failure verbatim.

#### Scenario: Autonomous implementer hits a failed precondition

- **WHEN** the tdd-implementer runs a gate whose precondition fails
- **THEN** it does not edit code and does not re-run the gate as a retry; it halts with a clean tree and reports the precondition command, its exit code, and the shim's message verbatim

#### Scenario: Interactive loop hits a failed precondition

- **WHEN** the tdd-apply skill runs a gate whose precondition fails
- **THEN** it surfaces the environment problem to the user as such, distinct from a red gate

### Requirement: Marker freshness is blind to the durable ledger

The tree hash a gate marker records, and the tree hash a marker check compares
against, SHALL exclude every path under `.gatedloop/runs/**` (the durable ledger).
The normalization SHALL be applied identically when the marker is written and when
it is checked, so the compare remains a single hash equality. Any delta outside
`.gatedloop/runs/**` SHALL still invalidate the marker exactly as today.

The normalization SHALL be a pure function of the tree it is given: the same tree
SHALL normalize to the same hash regardless of which branch is checked out, what the
working tree contains, or what the real index holds — in particular, regardless of
whether any change's ledger under `.gatedloop/runs/**` differs between the tree being
normalized and the current checkout. A marker written on a change branch's head
SHALL therefore match a check of that same head run from the merge target.

If the normalization cannot be performed, the check SHALL fall back to the
unnormalized tree (which can only deny, never pass an unnormalized ledger delta)
AND SHALL report the failure on stderr naming the failing step, so a denial it
causes is attributable — it SHALL NOT be swallowed silently.

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

- **WHEN** any tracked path outside `.gatedloop/runs/**` changes after the marker was
  written
- **THEN** the marker check fails as stale, exactly as before

#### Scenario: The same tree normalizes identically from the branch and from main

- **WHEN** a change branch's head tree carries a ledger file under `.gatedloop/runs/`
  whose content differs from the same file on the merge target, and that head tree
  is normalized once with the branch checked out and once with the merge target
  checked out
- **THEN** both normalizations yield the same hash, equal to the head tree with every
  `.gatedloop/runs/**` entry removed

#### Scenario: A live-check marker written on the head satisfies the merge gate from main

- **WHEN** `gates run live-check` passes green on a change branch's head whose
  ledger diverges from the merge target's, and the squash-merge of that branch is
  then attempted from the merge target
- **THEN** the merge gate's marker check matches on the first attempt, without
  re-running the gate

#### Scenario: A normalization failure is reported, not swallowed

- **WHEN** the ledger-stripping step fails for any reason during a marker write or
  check
- **THEN** the unnormalized tree is used (denying rather than passing) and a one-line
  stderr message names the failed step, so the resulting denial can be traced to it

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
paths under `.gatedloop/runs/**` without requiring a `ci` marker, printing an
explicit ledger-grade verdict. A staged diff consisting solely of ledger paths and
planning paths SHALL be held to the planning-grade requirement for its planning part,
and its verdict SHALL name the ledger paths it carried. A staged diff mixing ledger
paths with any other path SHALL be held to the full requirement for that diff.

#### Scenario: Committing only the merge row

- **WHEN** the only staged path is `.gatedloop/runs/<change>.jsonl`
- **THEN** the commit is allowed with a printed ledger-grade verdict, no `ci` marker
  required

#### Scenario: Committing the merge row with the archive move

- **WHEN** the staged diff holds `.gatedloop/runs/<change>.jsonl`, the change's move
  under `openspec/changes/archive/`, and `openspec/specs/**`
- **THEN** the commit is allowed as planning-grade, after the planning-grade checks
  pass, with no `ci` marker required, and the verdict names the ledger path

#### Scenario: A mixed diff gets no discount

- **WHEN** the staged diff contains a ledger path and a source file
- **THEN** the full commit requirement applies to the staged tree

### Requirement: Brace alternation in match patterns is honored or rejected, never ignored

A `{a,b}` alternation in a surface's `match` pattern SHALL select exactly the union of
paths its expanded alternatives select, including multiple and nested groups. A brace
construct the matcher cannot expand (for example an unbalanced `{`) SHALL be a
`gates validate` error naming the surface and the pattern. Under no circumstance SHALL
a brace pattern silently match nothing.

#### Scenario: A brace glob selects its alternatives

- **WHEN** a surface declares `match: "{bin,tests}/**"` and a file under `bin/` or
  `tests/` is in the diff
- **THEN** `gates surfaces` reports that surface hot, and `gates rules` includes its
  rules

#### Scenario: Multiple and nested groups

- **WHEN** a `match` pattern contains more than one `{...}` group, or a group nested
  inside another
- **THEN** the pattern selects the union of the fully expanded alternatives

#### Scenario: An unexpandable brace pattern fails validation

- **WHEN** a `.gates.yaml` surface's `match` contains a brace construct the matcher
  cannot expand
- **THEN** `gates validate` exits non-zero with a message naming the surface and the
  offending pattern

### Requirement: The manifest may declare machine-level gate serialization

The manifest MAY declare a set of gates to serialize machine-wide across all
worktrees of the repository. When a declared gate runs, the shim SHALL hold an
exclusive lock shared by every worktree of the repository for the duration of the
gate's command — and only the command: recording evidence and ledger rows SHALL
happen outside the lock. A run waiting on the lock SHALL be visibly waiting, printing
a periodic notice naming the holder, never appearing hung. The lock SHALL be
implemented with standard-library facilities only, and where the platform offers no
such facility the shim SHALL degrade loudly to running unlocked, never fail the gate
for want of a lock. Absent the declaration, no locking occurs — behavior is exactly
today's.

#### Scenario: Two lanes contend for a serialized gate

- **WHEN** the manifest declares a gate as serialized and two worktree lanes invoke
  it concurrently
- **THEN** one runs while the other blocks, printing a periodic waiting notice naming
  the holder, and runs as soon as the lock frees

#### Scenario: An undeclared gate never locks

- **WHEN** the manifest declares no serialization, or a gate outside the declared set
  runs
- **THEN** the gate runs immediately with no lock taken, identical to today

#### Scenario: The declaration is validated

- **WHEN** the manifest's serialization block names a gate that is not declared in
  the manifest, or is malformed
- **THEN** `gates validate` exits non-zero naming the defect

#### Scenario: A crashed holder does not wedge the machine

- **WHEN** a process holding the lock dies without releasing it
- **THEN** a subsequent run acquires the lock without manual cleanup

### Requirement: A serialized gate's wait is rate-limited, informative and bounded

While a serialized gate waits for its lock, the shim SHALL print a waiting notice at
most once every 30 seconds. The notice SHALL name the holder's pid, how long the
holder has held the lock, whether the holder is alive, and how long this run has
waited. The wait SHALL end after `concurrency.max-wait-seconds`, which defaults to
480. The run SHALL then exit 75 with a message beginning `gatedloop: lock busy`, and
SHALL record a ledger row marking the precondition as `lock-busy`.

#### Scenario: A five-minute wait

- **WHEN** a serialized gate waits five minutes for its lock
- **THEN** it prints at most eleven waiting lines, each naming the holder and the
  elapsed times

#### Scenario: The bound is reached

- **WHEN** the wait exceeds `concurrency.max-wait-seconds`
- **THEN** the run exits 75 with a `gatedloop: lock busy` message and a `lock-busy`
  ledger row, and the gate command never ran

#### Scenario: An invalid bound

- **WHEN** `concurrency.max-wait-seconds` is not a positive integer
- **THEN** `gates validate` fails naming the key

### Requirement: The implementer retries a busy lock and halts on any other precondition

On an exit of 75 whose message begins `gatedloop: lock busy`, the implementer SHALL
re-run the same command, at most three times, before halting with cause
`environment`. Any other exit of 75 SHALL keep its meaning: the environment is absent,
so halt. The implementer SHALL run every gate in the foreground.

#### Scenario: A lane meets a busy lock

- **WHEN** a gate exits with `gatedloop: lock busy`
- **THEN** the implementer re-runs the identical command rather than halting or
  editing code

### Requirement: Lock state is inspectable, and the shim never kills a holder

`gates lock status` SHALL report, for each serialized gate, whether its lock is held,
and if so the holder's pid, how long it has been held, and whether the holder is
alive. It SHALL flag a holder alive for more than an hour as possibly hung and show a
command a human can use to inspect it. No `gates` command SHALL terminate a holder.

#### Scenario: A hung holder

- **WHEN** a live process has held the `ci` lock for six hours
- **THEN** `gates lock status` reports it as possibly hung, with its pid and age

#### Scenario: A free lock with stale metadata

- **WHEN** the lock is free but its metadata names a pid that has exited
- **THEN** `gates lock status` reports the lock as free

### Requirement: Both commit layers apply the same commit check

The git-layer commit hook SHALL run the same commit check as the tool-level commit
hook, including the ledger-grade and planning-grade allowances.

#### Scenario: A ledger-only commit through the git layer

- **WHEN** only `.gatedloop/runs/<change>.jsonl` is staged and the commit is created by
  a path the tool-level hook does not see
- **THEN** the git-layer hook allows it with the ledger-grade verdict, and no `ci` run
  is required

### Requirement: An optional `confirm` gate proves the merged tree live

The gate contract SHALL include an optional `confirm` gate. The project binds it to a
command that brings the merged tree up and checks it on the project's own
environment. The plugin SHALL NOT read the command's body. An undeclared `confirm`
SHALL be skipped with a printed note, never treated as a failure. A declared `confirm`
SHALL block publication when it fails.

#### Scenario: Confirm is undeclared

- **WHEN** `gates merge` reaches step 5 in a project that declares no `confirm` gate
- **THEN** it prints that live confirmation was skipped because no `confirm` gate is
  declared, and continues

#### Scenario: Confirm has a precondition failure

- **WHEN** the `confirm` gate exits 75 because its declared environment is absent
- **THEN** the merge halts before publishing and reports the precondition message, as
  for any gate precondition
