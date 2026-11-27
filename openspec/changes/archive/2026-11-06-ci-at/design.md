# Design: ci-at

## Context

See proposal.md for the motivation (#162). This section covers only the code paths the
change touches. Everything named here is in `bin/gates`.

- **The commit check.** Both commit hooks call `gates discipline check-commit <tree>`
  (`_check_commit_verdict`). A planning-only diff is planning grade. A ledger-only diff
  is ledger grade. Anything else falls to `_check_marker_and_report(root, "ci", tree)`.
  On success the check writes one token (`ledger`, `planning` or `marker`) to
  `--verdict-file`. The hooks branch only on `ledger`: they skip the authored-test lock
  for it and run `gates tests check` for everything else. `gates merge` (`_merge_commit`),
  `gates record-merged` and the approval commit call the same check.
- **Markers.** Only `ci` writes a commit marker today (`cmd_run`:
  `_write_marker(root, "ci", tree, scope=scope)`). `unit` writes a ledger row with its
  tree and scope, and no marker. The marker store is gate-generic and tree-keyed.
- **Scope selection.** `_select_scoped_gate` narrows `ci`/`unit` to a surface override
  only when the hot set is exactly one non-catch-all surface that declares it and no
  path is unmatched (`_first_unmatched_path`). `_unit_union` handles two or more hot
  surfaces for `unit` only. It runs each hot surface's override and, once, the global
  `unit` when any hot surface has none. `_run_unit_union` runs that union under one lock
  and records scope `a+b`. err-full-scoping D3 kept a multi-surface `ci` on the global
  gate on purpose: "a union of narrowings is still a narrowing".
- **READY.** `gates ledger record-ready` appends the `ready` row unconditionally and
  prints `_ready_gates`, whose `ci` is `pass` only when a green unscoped `ci` row names
  the head's tree. **It does not refuse on `ci: fail`.** The issue and the brief assume
  READY already requires the full `ci`. In code, READY only reports it. The requirement
  is enforced at `gates merge` step 1, which needs an unscoped `ci` marker on the head
  (`require_scope="full"`), and step 3 runs `ci` with `--full` on the merged tree.
- **The audit.** `cmd_audit` runs on every `Stop` (`hooks/continue-loop.sh`) and at the
  merge (`gate-merge.sh`, `gates merge` step 1). It walks commits since a per-worktree
  cursor and joins each tree to green `ci` rows (`_GreenCiMatcher`). On a miss it tries
  vouching (`_vouched_by_head`, taint-preclear D1): the commit is an ancestor of the
  audited head, and a green unscoped `ci` row names the head's tree. If that fails too,
  the commit is tainted. The cursor then advances past it. `_unrecorded_commits`, the
  merge's read-only check for a branch no worktree holds, joins `ci` rows only and does
  not vouch.
- **The budget.** `_attempt_state(rows, task, gate)` counts red rows of the task's oracle
  gate after its RED run, and red `ci` rows for the task. A `gates run` with no `--task`
  whose current task is already checked in HEAD's `tasks.md` records no task
  (budget-ticked-task D1), so that run is nobody's attempt.
- **The lock.** `gates tests check` judges placements, held files, and a red run *of the
  task's oracle gate* after placement. It never reads `ci`.

## Goals / Non-Goals

**Goals:**
- Under `loop.ci-at: ready`, a task commit costs a working-set-scoped `unit` run plus the
  convention review, and the full `ci` runs once before READY and once at the merge.
- Every enforcement layer agrees on what a gated commit is under each mode: both commit
  hooks, the audit, the merge's read-only check, the budget and the outcomes view.
- Opt-in union-scoped `ci` for projects that keep `task`.
- Byte-for-byte unchanged gate behaviour for a project that sets neither key.

**Non-Goals:**
- Changing `gates merge`, the merge hook, the push hook, `verify`, `live-check` or
  `confirm`.
- Budgeting the READY `ci` in code. See D5 and Risks.
- A union for `unit` beyond today's. A `ci` union that adds the global `ci` beside the
  overrides (D8).
- Warning that `loop.ci-scope: union` buys little under `ready`. Both keys are valid
  together, and SETUP.md says what each one does.

## Decisions

### D1. `loop.ci-at: task | ready`, opt-in, and `ready` requires a declared `unit`

`ci-at` joins `LOOP_KEYS`, validated like `loop.task-oracle`: `task` or `ready`, and
absent reads as `task`. `ready` without a global `gates.unit` fails `gates validate`,
naming the missing gate (fail-loud-gates; this was the maintainer's stated preference).
A surface-level `unit` override alone does not satisfy it. An unmatched path would
select the absent global gate, `gates run unit` would print "optional gate not declared
— skipping", and no marker would exist to commit on. That failure would be loud, but it
would come at the first commit instead of at validation.

*Alternative:* fall back to `ci` when `unit` is undeclared. Rejected: the project would
think it had chosen `ready`, and every task would still pay the full `ci`.

**Opt-in** is the maintainer's decision. `task` stays the default, and an adopter who
does not set the key sees no gate, exit code or allow/deny change. The one output change
is D7's stderr line.

### D2. Under `ready`, the commit check accepts a `unit` marker, on a change branch only

- `cmd_run` writes a tree-keyed `unit` marker on a green `unit` run, the same
  `_write_marker` the `ci` marker uses, with the run's scope. A union run writes it too.
  The marker is written only under `ready`, so `task` writes nothing new.
- `_check_commit_verdict`'s fallback rung tries the `ci` marker first. A `ci` marker
  still allows a commit in both modes, so a loop that runs `ci` anyway is never refused.
  Under `ready`, when the current branch names an **active** change
  (`openspec/changes/<branch>/` exists, not only an archived one), the rung then tries
  the `unit` marker. A match allows the commit with the new token **`unit`** and the
  allow line `gatedloop: 'unit' marker matches — <tree> (scope: <s>) — loop.ci-at:
  ready; the full ci runs before READY and at the merge`. The tokens stay a closed set,
  and the hooks still branch only on the token.
- **Off a change branch the rung is unchanged.** That covers `main`, `plan/*`, a docs
  branch, and the detached HEAD `gates merge` integrates on. So the squash commit, the
  approval commit and `record-merged`'s commit still need a `ci` marker. `ready` can
  only relax a task commit on the change's own branch.
- A denial under `ready` on a change branch names `gates run unit` (and that `gates run
  ci` also satisfies it). The stale-marker diagnosis runs for whichever gate's store
  holds the newest marker.

*Alternative:* a separate "commit gate" marker name. Rejected: the real gate's marker
keeps the existing store, LRU and `gate-marker check unit` working with no new
vocabulary.

### D3. Both hooks honour the mode identically, through the shim

The selection stays in `bin/gates`. Neither hook reads the manifest.
`hooks/gate-commit.sh` and `templates/git-hooks/pre-commit` each:
- treat the token `unit` exactly like `marker`: run `gates tests check`, then record
  usage;
- print the check's allow line when the token is `unit`. The git layer already echoes
  its line. The tool layer adds the same echo for `unit` only, so a `ci`-marker commit's
  output is unchanged;
- end a denial with a gate-neutral remedy ("run the gate named above, then stage exactly
  what it tested"). Today's trailing "run `gates run ci`" line would send a `ready` loop
  back to the full `ci`. No test pins that line (checked: `tests/` has no assertion on
  it).

The git-layer copy is refreshed through the existing `git-hook-refresh` adoption item,
since the template changes.

### D4. The guarantee moves to READY and the merge. The audit accepts what the hook accepted

**READY.** Under `ready`, `record-ready` refuses (exit 1, no row) unless `_ready_gates`
would report `ci: pass`, that is, a green unscoped `ci` row on the head's tree,
ledger-blind. This is what makes "the full `ci` runs once before READY" true in code.
Today READY only reports the result. Under `task`, `record-ready` is unchanged.

**The merge** is unchanged. Step 1 needs an unscoped `ci` marker on the head (in any
worktree's store), and step 3 runs `ci --full` on the merged tree. Under `ready` the
READY `ci` already satisfies step 1, so the merge adds no `ci` beyond today's.

**The audit, and why taint-preclear's vouching is not enough on its own.** Vouching
covers a commit with no row of its own only when the audit runs *after* a green
unscoped `ci` on the head. The `Stop` hook audits on every stop, including mid-change in
an interactive session and at every turn end. A `ready` task commit is walked before any
full `ci` exists. Vouching fails, the commit is tainted, and the cursor moves past it.
The READY `ci` later clears the taint (`_maybe_resolve_taint`), so the merge is not
blocked. But the ledger would record a bypass incident for every rule-following task
commit, and the AUDIT line would accuse the loop of `--no-verify`. taint-preclear D2
rejected exactly that taint-then-clear pattern. The read-only `_unrecorded_commits`
check does not vouch at all, so under `ready` it would refuse every merge of a branch no
worktree holds.

So under `ready`, `_GreenCiMatcher` also indexes green `unit` rows. `rows_for` then
matches a unit-gated commit, and `_classify_gated_commit` classifies it by session as a
`ci`-gated one is (agent: nothing; human: `human-commit`). `has_unscoped` stays
`ci`-only: a `unit` row never vouches for an ancestor. Both callers get the change:
`cmd_audit` and `_unrecorded_commits`.

The mode is read from the manifest when the audit runs. Flipping `ready` → `task`
mid-change makes unaudited unit-only commits taint until a green `ci` on the head
clears them, which is the fail-loud direction. Flipping `task` → `ready` only widens
what matches.

**How it composes:** the hook allowed the commit on a `unit` marker, the audit records
the commit as gated by the mirroring `unit` row, the READY `ci` covers the head's full
tree, and the merge proves it again. A commit that slipped the hooks has neither row and
taints as before, unless the READY `ci` later vouches for it. That is taint-preclear's
existing rule, unchanged.

### D5. The budget follows the commit gate. The READY ci is change-level

`_attempt_state` takes the commit gate (`ci`, or `unit` under `ready`). After a task's
RED run, a red row of the oracle gate counts, as does a red row of `ci` or of the
commit gate. Under `ready` a red `unit` therefore counts for a task whose oracle is
`integration`, as a red `ci` does under `task`. For an untagged or `unit`-oracle task
the two coincide, and nothing is counted twice: a row is one gate. A red `ci` run with
`--task` still counts in both modes.

The READY `ci` runs with every task checked in HEAD, so budget-ticked-task D1 already
records it with no task. It is nobody's attempt, and the budget never refuses it. A red
READY `ci` is a change-level gate, like `verify` or `live-check`: at most 2 focused fix
attempts, then HALT `stalled`. The prompts say this, as they already do for those gates.
A fix commit is an ordinary change-branch commit gated as in D2.

`gates stats --outcomes` restart recovery (`retry-budget` D6) counts a green `ci` for
the task today. Under `ready` it also counts a green `unit` for the task, or a
`ready`-mode recovery would always read as zero.

### D6. `gates tests check` needs no change

The lock reads the oracle gate's red run after placement, never `ci` (condition 3 in
`_lock_problems`). Both hooks keep running it after the commit check for the `unit`
token (D3). Under `ready` the red step is the same `gates run <oracle-gate> --task`
run. The green `unit` that earns the marker comes after placement and the red run, so
it cannot stand in for the red run either.

### D7. The shim names the commit gate. The prompts run what it names

`gates task start <N.M>` (run at every 5a) and a successful `gates tests handoff`
(right before the authoring commit, where no task has started yet) print one stderr
line naming the commit gate: `gatedloop: commit gate: gates run ci` or `gatedloop:
commit gate: gates run unit (loop.ci-at: ready — the full ci runs before gates ledger
record-ready)`. The line goes to stderr, so no stdout a caller parses changes. This
line is printed under `task` too, which is the one output change for a project that
sets neither key.

The prompts never read `.gates.yaml`. They run the gate the line names, and a wrong
guess is denied with the right gate named (D2), so they correct themselves.

`skills/tdd-apply/SKILL.md` (5e, 5f, 5h, the authoring commit, the sync route, 7.5) and
`agents/tdd-implementer.md` (§2, §4, §5) say what the per-task gate is under each mode,
using only `gates run <gate>`:
- Under `ready`, stage first. The green `gates run unit --task <N.M>` on the staged tree
  is then both 5e's green run and 5f's commit gate.
- Under `ready`, before `gates ledger record-ready`, run `gates run ci` with nothing
  staged. `record-ready` refuses without it.

### D8. Union-scoped `ci`: `loop.ci-scope: single | union`, opt-in

**What `bin/gates` does today with several hot surfaces:** `_select_scoped_gate`
returns the global `ci` whenever more than one non-catch-all surface is hot, and
`_unit_union` is gated to `unit` (`if gate == "unit"`).

Under `union`, `ci` gets a union when the staged diff (after `_scope_paths`) has no
unmatched path, two or more non-catch-all surfaces are hot, and **every** one of them
declares a `ci` override. It then runs each override once, under the same rules as
`_run_unit_union`: preconditions first, identical commands deduped, one lock, every
command run, first non-zero exit wins, scope `a+b`. That runner becomes gate-generic.
On green, a union `ci` writes its marker with that scope.

If any hot surface lacks a `ci` override, the global `ci` runs alone. This differs from
`unit`, which adds the global beside the overrides. The global `ci` is the
aggregate oracle by contract, so running it alongside the overrides would cost more
than the global run it was meant to undercut.

A union marker's scope is not `full`. So `require_scope="full"` (merge step 1, the push
hook), `_ready_gates` and `has_unscoped` (vouching) all refuse it with no new code.
`_maybe_resolve_taint` is unaffected: a union run has a non-empty staged diff, so its
tree is never the head's tree.

**Default: opt-in.** err-full-scoping D3 decided the multi-surface `ci` runs the global
gate, because a union of narrowings makes a multi-surface commit's evidence weaker than
today's. Turning the union on by default would run *less* `ci` for every existing
adopter with two or more scoped surfaces. That changes adopter-facing behaviour, and the
evidence would weaken silently. No strong reason against opt-in turned up: the field
report's lanes want `ready`, which makes the union moot for task commits anyway. So
`single` stays the default, and `union` revises D3 only for projects that ask for it.

*Key placement:* both knobs live under `loop` next to `attempts` and `task-oracle`. The
`gates` block holds only gate bindings, and `surfaces[].gates` holds only overrides.

### D9. Two adoption items, and a dotted `surface-key`

The maintainer asked for one adoption item, for `ci-at`. This design adds a second, for
`ci-scope`, because an opt-in key nobody is told about is never adopted. Each item maps
to one manifest key, the catalogue's existing shape.

- `ci-at` (`since: 0.12.0`, detector and action `manifest-key loop.ci-at`,
  `applies_when: null`). Options: `task` (adopted; keep a full `ci` per task),
  `ready` (adopted; needs `gates.unit`), and declined ("leave it unset: `task` applies").
  The recommended option is to leave the key unset. Like `token-budget`, the safe
  default is the recommendation, and `ready` is offered on the field evidence.
- `ci-scope` (`since: 0.12.0`, `manifest-key loop.ci-scope`, `applies_when` a surface
  declaring `gates.ci`). `adoption_applies`'s `surface-key` today reads `s.get(key)`, a
  flat key. It becomes a dotted-path read through each surface mapping, the same walk
  `_dotted_present` does for the manifest, so `gates.ci` resolves. Flat keys such as
  `live-check` behave as before.

The catalogue's loader and shape tests (`tests/test_adoption*.py`) pin the shape, not
the item list, so adding items rewrites no existing test.

### D10. Sync commits and other change-branch commits

`git merge --no-commit <target>`, then the commit gate, then `git commit` is unchanged
in shape. Under `ready` the sync commit is a change-branch commit, so a `unit` marker
allows it. The merge hook's own denial for a self-committing merge still names `gates
run ci` (`tests/test_merge_sync_commits.py` pins it), and that remedy still satisfies
the hook in both modes. The authoring commit (`author tests: <change>`) is a
change-branch commit too, and runs the gate D7's handoff line names.

## Risks / Trade-offs

- [A red READY `ci` is harder to attribute than a red per-task `ci`] → Each task still
  had a red→green `unit` and a clean review. The field report found no red `ci` that a
  task's `unit` missed and a single READY `ci` would have caught. The bisect is over a
  handful of task commits, each one green on `unit`. This is the trade the issue asks
  for, and the default stays `task`.
- [The READY `ci`'s fix attempts are counted by the prompt, not the ledger] → The same
  stopping rule as `verify` and `live-check` today. A code-enforced change-level budget
  is a candidate, recorded in `docs/candidates.md`.
- [A `unit` marker is keyed on the index but `unit` runs on the working tree] → The
  same gap the `ci` marker has today. "Stage first" is the existing discipline, and the
  stale diagnosis names late-staged paths.
- [The tool-level hook's allow line may not reach the model, depending on the host] →
  The git layer's line is in the commit output, D7's line comes from the shim, and the
  ledger row records the `unit` scope. Nothing depends on the allow line being seen.
- [The mode is read when the audit runs, not when the commit was made] → A mid-change
  flip errs toward a taint (D4). SETUP.md says to change the key between changes.
- [`gates validate` refuses `ready` for a project whose `unit` exists only as surface
  overrides] → It names the missing global `unit`. Declaring one (even the aggregate
  test command) is the fix, and that keeps the unmatched-path case well-defined.

## Migration Plan

Nothing to migrate: both keys are opt-in, and a project that sets neither runs exactly
today's gates. Adopters see the two items in `/gatedloop:upgrade` on 0.12.0. A project
that adopts `ready` refreshes its git-layer hook copy (`git-hook-refresh` item) so both
layers know the `unit` token. Until it does, the stale git-layer copy treats `unit`
like `marker`, which is the correct handling, and only the allow line is missing. To
roll back, remove the key. Commits already made under `ready` stay gated by their
`unit` rows only while the key is set (D4), so a rollback mid-change needs one green
`ci` on the head to clear the resulting taints.
