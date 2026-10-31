## Why

An adopter's orchestrator reported how the loop behaved over a month of unattended lanes on 0.8.0. Checked against `origin/main` after 0.9.0 and the 0.10 merges, six defects are still present. Two let a stated guarantee lapse, and four cost a lane time for a reason the shim should have named:

- **#101, the merge does not check the plan approval.** `gates merge` step 1 and every acceptance writer skip the approved-sha comparison. A plan amended after approval, and never re-attested, merges and is accepted as though the approved plan were still the plan. `_approval_check_at` already makes the right comparison; only `gates approval check`, `gates handoff` and the implement hook call it.
- **#108, a sync merge slips the commit hooks.** A committing `git merge origin/main` on a change branch passes the merge hook, which gates only integration, and git runs no pre-commit hook for the merge commit. The commit has no green-ci row, so the reflog audit taints the change, usually first seen at `gates merge` step 1 after acceptance, and only a full `ci` clears it. The prompts never say how to sync main.
- **#109, a crash reported as a shared branch.** An unparseable `.gates.yaml`, for example one with conflict markers, crashes every subcommand with a Python traceback. `hooks/gate-commit.sh` reads any non-zero exit from `discipline check-worktree` as "this branch is shared with another worktree", so the lane is told the wrong cause.
- **#110, the hooks judge the wrong repository.** `gates hook git-cwd` resolves `cd ~/x && git commit` to `<cwd>/~/x`, and `cd $HOME/x && …` and `( cd x && git … )` to the hook's own cwd. Lanes had to fall back to `git -C` in separate calls.
- **#111, two handoff defects.** A `--task` re-handoff keeps the first handoff's base for a file. If main then changes that file and the branch syncs, `gates tests place` refuses and calls it a test defect. A full handoff after a partial placement silently drops every placed task, characterization declarations included.
- **#112, the READY report's gate fields are the agent's claim.** The report allows a review of only `clean` or `findings`, so an implementer with no review recorded had to pick one, and picked wrong. `gates ledger record-ready` says nothing about the gates.

Three more reported items need nothing new. Attempts counted across a test-defect cycle, and a restart that demanded a clean tree, were fixed in 0.8.0 by unblock-authored-lock D6 and D7; the reports predate that release. A gate run that starts as the ci lock frees, under the previous run's load, is the adopter's timing-dependent self-test, not a gatedloop guarantee. design.md records all three.

## What Changes

- `gates merge` step 1, in both modes, and every acceptance writer (`--local`, `--pr`, `--merged`) refuse a change whose plan on the merge target, or at the branch head, does not hash to its recorded `approved_sha`. The refusal names the route to re-approval.
- The merge hook denies a merge into a change branch that would create the merge commit itself, and names the gated route: `git merge --no-commit <ref>`, `gates run ci`, then `git commit`. A fast-forward and a `--no-commit` or `--squash` merge pass as today. `skills/tdd-apply` and `agents/tdd-implementer` give that route for syncing main.
- The reflog audit's taint refusal names each tainted commit and says when it is a merge commit.
- An unparseable manifest fails with one line naming the file and position, and says when the file holds merge-conflict markers. No subcommand prints a traceback for it.
- `hooks/gate-commit.sh` reports a shared branch only on `check-worktree`'s shared verdict, and otherwise passes the shim's own reason through.
- `gates hook git-cwd` expands `~`, `~/…`, `$HOME` and `${HOME}` and reads a leading subshell like the bare command. A `cd` target it cannot resolve makes the hook deny with that reason, instead of judging the session's checkout.
- `gates tests place` also accepts a file at its content on the merge target, so a change main made is not a test defect. A full `gates tests handoff` that would drop an already-placed task refuses and names the `--task` route.
- `gates ledger record-ready` prints the report's `gates` block derived from the ledger, with `none` for a review never recorded, and the implementer copies it unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `merge-step`: proving the head checks the plan approval.
- `acceptance-gate`: an acceptance is refused for a plan that is not the approved one.
- `loop-enforcement`: a sync merge creates no ungated commit; the taint refusal names its commits; the commit hook's shared-branch denial; the hooks' repository resolution; the READY report's gate fields come from the ledger.
- `manifest-parsing`: an unparseable manifest fails loud.
- `test-discipline`: placement accepts main's own change to a file; a full handoff never drops a placed task.

## Impact

- `bin/gates`: `_merge_prove_head`, the acceptance writers, `load_manifest`, `hook git-cwd`, `_tests_handoff`, `_tests_place`, `_taint_refusal`, `ledger record-ready`.
- `hooks/gate-merge.sh`, `hooks/_gate_match.py`, `hooks/gate-commit.sh`.
- `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md`: the sync route and the READY gates block.
- `SETUP.md`, `AUTOMATION.md`: the sync route, the resolved command forms, the approval check at merge.
- Adopters: a change whose plan was amended without re-attesting stops at `gates merge` until it is re-approved. A lane that synced main with a committing merge is told to use `--no-commit`. No manifest key is added. Ships in a minor.
