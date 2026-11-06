# Design

## Context

See proposal.md, Why. These facts in the shim shape the approach:

- **Neither the brief nor the handoff checks approval.** `_render_tests_brief` reads only the change directory. `_tests_handoff` reads `x-gatedloop-approved-by` only to copy it into the row (`_read_approved_by`), and never refuses on it. Approval is enforced at `check-implement` and at the merge. So a preflight on an unapproved plan needs no approval bypass.
- **The handoff has one check that is wrong for a plan under amendment.** `_oracle_handoff_problems` starts with `_oracle_drift_problems`, which compares each task's tag in the working tree with the merge target's `tasks.md` (task-oracle D9). For a new plan the change is not on the target and the check is a no-op. For an amendment to a plan that is already merged, though, every retag would be refused, and the retag is the whole point of the amendment.
- **A real handoff writes in two places.** It appends a ledger row, and `_hash_blob` runs `git hash-object -w` for every held file and every base.
- **The holding area is tracked by design** (split-test-author D3): it is committed in the authoring commit on the change branch. `gates tests check` resolves the change from the branch (`_resolve_change_name`). On `plan/*`, on the target and on any branch that names no change, it prints "no change branch checked out, nothing to check" and passes. Nothing stops held files from riding along on a plan branch.
- **`gates tests show` reads only the ledger** (`_tests_show_doc` folds `_authoring_state(rows)`). With no handoff recorded it says the tests are not authored yet, so the authored-set review has nothing to read in a preflight.
- **`.gatedloop/out/` already ignores itself.** `_run_gate_captured` writes a nested `.gitignore` containing `*`, and `_rotate_out_logs` only removes `<gate>-*.log`.
- **`on`/`off` are a parser trap.** PyYAML reads `on` as `True`, but `_scalar` in `_mini_yaml` turns only `true`/`false` into booleans, so it reads `on` as the string `"on"`. The shim already guards against this ambiguity elsewhere: `_YAML_NON_STRING_RE` refuses a plain `on`/`off` where it reads YAML as text.
- **The oracle-tag grammar has no deletion clause.** test-rewrites D1 rejected `removes:` and parked it in `docs/candidates.md`.

## How it connects end to end

```
/gatedloop:propose (or /gatedloop:planner → propose), on plan/<change>, after /opsx:propose authors
  ├─ gates plan check <change>                      ← always; free; deterministic
  └─ under loop.plan-preflight: run
       ├─ test-author (preflight mode)
       │    gates tests brief <change> --preflight  → writes .gatedloop/out/preflight/<change>/ (ignored)
       │    gates tests handoff <change> --dry-run  → same refusals, no row, no object
       ├─ convention-review (authored-set mode) over gates tests show <change> --preflight [--diff]
       └─ rm -r .gatedloop/out/preflight/<change>/
  findings → planner amends → re-run → git add openspec/changes/<change> → gates run ci → commit → PR
                                         (gates tests check refuses any .gatedloop/authored/** here)
… approval, merge of the plan …
/gatedloop:planner step 4: gates plan check <change> --against <target> → gates handoff
… the real test author runs from scratch on the change branch, exactly as today …
```

## Goals / Non-Goals

**Goals:** the test author's and the handoff's objections reach the planner before approval. The shim's deterministic checks are runnable on a plan alone. Drift is visible at handoff. Preflight output cannot reach a commit.

**Non-Goals:**
- moving any guarantee: approval, attestation, `gates handoff`, the real `gates tests handoff`, the lock and `gates merge` are unchanged;
- reusing preflight tests after approval;
- running any gate in a preflight;
- a deletion clause in the tag grammar;
- making the orchestrator re-check drift (it already verifies each payload).

## Decisions

### D1. Names: `gates tests handoff --dry-run` and `gates plan check` (kept)

These two names were promised provisionally to an adopter's planner, and nothing found argues against them. `--dry-run` describes exactly what the flag does: the same command, writing nothing. `plan check` puts a new noun, `plan`, at the top level, beside `approval` and `handoff`, for checks on a plan's artifacts that are neither approval nor tests. It has room for later checks. `gates validate` was considered as the home: it already reports oracle-tag problems, but it runs in `ci` on the target for every active change. A check that fails one change's plan there would break every other change's `ci` (the same reasoning as test-rewrites D1, where an absent `rewrites:` path is only a warning in `validate`). `plan check` is per change and is run by the planner, so it can fail.

The two companion flags, `tests brief --preflight` and `tests show --preflight`, are named after the area they read. They are not named `--held`, because the area they read is the preflight one, not the tracked one (D3).

### D2. The preflight never records, and its output is never reused

The preflight writes no ledger row: no `tests-handoff`, no `review` with `--scope authored`, no `halt`. After approval, the real test author runs from scratch on the change branch. The preflight's tests are discarded, not handed off, for three reasons:
- the approved plan may differ from the one the preflight saw, since amendments are the point of the preflight;
- a handoff row records the base blobs of the tree it was taken on, and the preflight's tree is the plan branch before approval;
- a reused set would be a lock with no provenance, authored before the approval it is supposed to follow.

The price is a second authoring run per change. It is paid only by projects that opt in (D7), and it replaces the far costlier round trip of halt, amend and re-approve.

### D3. A preflight holding area outside the tree (coordinator's option a), plus a backstop at the lock (option b)

Preflight tests go to `.gatedloop/out/preflight/<change>/`, with the real holding area's layout. `gates tests brief --preflight` creates the directory and ensures the self-ignoring `.gitignore` in `.gatedloop/out/`. That is the same idiom `_run_gate_captured` uses, so the area is ignored in every adopter repository, not only one whose `.gitignore` lists it. `--dry-run` and `show --preflight` read only that area. A real handoff reads only `.gatedloop/authored/<change>/`, as today. `_read_holding_area` takes the directory as a parameter, so the same checks run over either area. `_rotate_out_logs` touches only `<gate>-*.log`, which a test pins.

Alternative considered: a free `--holding <dir>` flag. Rejected, because two flags pointing at two arbitrary directories invite a mismatch. A fixed, shim-owned area is one fact the prompts cannot get wrong.

The backstop: `gates tests check` refuses a staged path under `.gatedloop/authored/` whenever `_resolve_change_name` resolves no change. That covers a `plan/*` branch, the merge target, and any other branch that names no active change. Today that path returns 0 with "nothing to check". Both commit hooks (`hooks/gate-commit.sh` and the git-layer `templates/git-hooks/pre-commit`) already run `gates tests check` after `check-commit`, so the refusal holds at both layers with no change to either script and no hook refresh for adopters. Placing it in `discipline check-commit` was considered and rejected: `check-commit` grades the tree, the lock is the authored-test check, and `gates merge` calls `check-commit` internally on the target, where a squash's net diff never holds the area but a future edge case would fail in the wrong place. A ledger-grade commit skips the lock, but it stages only `.gatedloop/runs/**`, so it cannot carry a held file.

Why both: the preflight area keeps the tests out of the tree, and the backstop catches the other route in, a real holding area populated off a change branch by hand or by a confused agent. The backstop would have stopped the collision tessellate's interim procedure (#134) works around.

### D4. `--dry-run` runs every refusal except tag drift

`--dry-run` runs `_read_holding_area`'s problems, the empty-area refusal, the `--task` refusal, every contradiction in `_oracle_handoff_problems` (tags, `characterization`, `none`, declared rewrites absent at `HEAD` or not held in full, and untagged tasks under `required`) and the full-handoff "would drop a placed task" check. It prints the undeclared-overwrite advisory lines. It skips only `_oracle_drift_problems`, and prints one line saying so: on a plan branch, the tasks are the plan being amended, and a real handoff still runs the check. The advisory computes existence with `is_file()` instead of hashing, so no object is written. The exit status and messages are the real handoff's, with "Nothing was written." as today.

### D5. What `gates plan check` can check, and what goes to the author

The issue asks for three checks. The decision for each, honestly bounded:

- **(a) A `rewrites:` path that a task deletes.** Not mechanically checkable: the plan has no way to declare a deletion (test-rewrites D1). Detecting one from prose ("delete", "remove") would be a heuristic, and a heuristic is not a fail-loud check. What *is* checkable is a `rewrites:` path absent at the base. That is the handoff's refusal, moved before approval. When an earlier task's line of the same change names the path in backticks, the finding says that the earlier task creates it, which is (b)'s one mechanical case. The deletion case goes to the preflight author, who reads the design: a task whose design deletes a declared rewrite is a `blocked: weak-spec` question under §4 and §6. The `removes:` candidate gets this report as evidence, but is not promoted: one observed case among six handoff refusals, and the preflight now catches it before approval.
- **(b) A task whose oracle needs an artifact that a later task creates.** In general this is semantic. Tessellate's #133 (eval cases that validate only after a schema change) names no path that the shim could pair. The mechanical part is the rewrite case above. The rest is the preflight author's job: it already sees the whole change in order (§5). Preflight mode adds an explicit instruction to return any test that cannot be written against the tree plus the earlier tasks' stated interfaces as `blocked: weak-spec`, naming both tasks.
- **(c) A green-first task without `characterization`.** Statically, a tag is red-first unless it says otherwise, and the plan has no other evidence. Two partial checks exist, both in the preflight: the dry run refuses an author's `CHARACTERIZATION` on a red-first tag (an existing contradiction check), and preflight mode tells the author to return `weak-spec` when a red-first task's tests can only pass. The complete check would place the held tests in a scratch worktree and run each task's oracle gate at the base. It is rejected for now: it costs one gate run per task per preflight, needs a scopable oracle gate, and can misjudge a test that an earlier task's implementation would turn red. It is recorded in `docs/candidates.md` with a promotion condition.

The checks it does make: this change's oracle-tag errors and warnings (`_task_oracle_problems`, filtered to the change), untagged tasks under `loop.task-oracle: required`, and the rewrite-existence finding. These reuse the parser and the messages the handoff and `validate` already print, so the planner sees the same words now that it would otherwise see after approval.

### D6. `--against <ref>` is in scope, because it is cheap

Drift needs nothing new: `_named_paths` already extracts backticked repository paths (the brief uses it on `design.md`), and `git diff --name-status <base> <ref>` does the rest. The plan's base is the latest commit in `<ref>`'s history that touches `openspec/changes/<change>/` when `<ref>` holds the change (the approved plan's merge), and `git merge-base HEAD <ref>` otherwise (a plan branch). With `--against`, existence checks run at `<ref>`, because the change branch is cut from it. A drift finding means "re-read this", not "this is wrong". The planner reads the moved files against the plan, sends the handoff when the plan still holds, and otherwise reports and sends nothing (planner step 4). Tessellate's "drifted while queued" category (#111 #119 #129 #131) is exactly the case of a named file moving underneath an approved plan.

### D7. `loop.plan-preflight: run | skip`, default `skip`; `gates plan check` always runs

The model-token part of the preflight (author plus review, on every plan and every amendment that touches tasks, design or specs) is adopter-facing behaviour with a cost, so it is opt-in. The values are `run`/`skip`, not `on`/`off`: PyYAML reads `on` as `True` while `_mini_yaml` reads `"on"`, so the same manifest would mean two things depending on which parser a machine has. That is exactly the conditional-path defect `tests/` exists to catch. `gates validate` refuses `run` with `loop.test-author: inline`. An inline project has chosen not to have a separate author, and a planner authoring tests against its own plan would lose the cold read that makes the preflight worth its tokens.

`gates plan check` runs in the propose path whatever the key says. It costs nothing, records nothing, and reports only what the handoff would refuse after approval anyway.

### D8. The planner's dispatch ban gets one stated exception

`commands/planner.md` forbids dispatching a test author. The preflight needs exactly that dispatch, so the change owns the permission explicitly instead of letting the propose command imply it. Under `loop.plan-preflight: run`, the planner may dispatch the test author in preflight mode, and the convention review in authored-set mode, for the preflight only, within these limits:
- they run against the planner's own `plan/<change>` branch in its own worktree;
- the author writes only to the preflight holding area;
- no real `gates tests handoff`, review verdict or halt is recorded;
- the preflight holding area is deleted before the plan is committed.

Every other dispatch stays forbidden. This covers what tessellate's interim procedure (#134) treats as a local exception. The `command-surface` requirement for the planner role is modified to carry it, with scenarios for the permitted dispatch, the still-forbidden ones and drift.

### D9. Prompts: a mode, not a new agent

`agents/test-author.md` gains a "Preflight mode" section. When its caller says preflight, it:
- reads `gates tests brief <change> --preflight`;
- writes only to the area the brief prints;
- ends with `gates tests handoff <change> --dry-run`, never a real handoff;
- returns order problems (D5 b) and red-first tags that can only pass (D5 c) as `blocked: weak-spec`;
- reports as usual and records nothing.

Every other rule (the boundary, the RED questions, the budget) is unchanged, so a preflight objection is the one the real run would raise. `agents/convention-review.md`'s authored-set mode reads `gates tests show <change> --preflight` (and `--preflight --diff`) when told it is a preflight, and its caller records no verdict. `commands/propose.md` gains the preflight step between reading back the change name and committing, and a preflight line in the PR body. All of these name only `gates …` and gate names (`stack-agnostic-prompts`).

### D10. Order: cheap checks first

The suggested order (author, dry run, review, plan check) is refined to plan check first. It is free and deterministic, and its findings (a malformed tag, an absent rewrite, an untagged task under `required`) would make the author's run either fail at the dry run or waste its budget. The author runs only on a plan that passes `plan check`.

## Risks / Trade-offs

- [The preflight author misses what the real author later finds] → the preflight is advisory and the real run still happens. Stochastic misses cost what they cost today, and nothing is worse.
- ["Plan wrong about the code" is only partly catchable] → the author reads public interfaces, never bodies, so a plan that misreads an implementation detail (tessellate's `gates conventions sync` grep) is caught only where the interface shows it. That is stated in SETUP, not claimed away.
- [Token cost per amendment] → opt-in; on an update to an open plan PR, the propose step re-runs the model part only when the update changes `tasks.md`, `design.md` or a spec, never for a proposal-only edit.
- [A drift finding on a busy file is noise] → the planner reads it and decides. Findings are advice and never block `gates handoff`.
- [The backstop refuses a commit on `main` that some workflow relies on] → no shipped flow commits held files off a change branch: the authoring commit is on the change branch, and placement empties the area before the merge. The suite's fixtures are the check. A fixture that does it is either wrong or names a flow to keep, and either way the implementer reports it.

## Migration Plan

Ships in 0.12.0. `loop.plan-preflight` is unset in every existing manifest, so the propose path changes only by running `gates plan check`. The `plan-preflight` adoption item asks once. The `tests check` backstop changes the verdict only for a staged held file on a branch that names no change, which no shipped flow produces. Rollback: revert the change. An older shim refuses `loop.plan-preflight` as an unknown `loop` key at `gates validate` (fail loud), so a project that set it must unset it to downgrade.
