# Tasks

## 1. The plan approval at merge and acceptance (D1, D2)

- [x] 1.1 Make `_merge_prove_head` run `_approval_check_at` and the branch-head sha comparison before its evidence checks, in both modes. Verify with real-repo tests: a plan amended on the target without re-attest halts step 1; a branch editing its own `specs/` halts step 1; an untagged-tick-only `tasks.md` change does not; and pull-request mode halts before any status is published [oracle: unit]
- [x] 1.2 Run the same check in every acceptance writer, and make `record-merged` under `self` write the merge row but no `accept` row, exiting non-zero, when the plan is stale. Verify with tests for `--local`, `--pr` (stubbed review) and `--merged` against an amended plan, and for the `record-merged` row set and exit code [oracle: unit]

## 2. The sync merge (D3, D4, D5)

- [x] 2.1 Make `_gate_match.py` report the merge's committing flags, and make `gate-merge.sh` deny a committing not-integrating merge with the route. Verify with hook tests in a real repo with a remote: `git merge origin/main` on a branch with its own commits is denied; `--no-commit`, `--squash`, `--ff-only`, `--abort` and a pure fast-forward pass; `--no-ff` and `--continue` are denied; an unparsable ref without a non-committing flag is denied; and #44's cases still pass [oracle: unit]
- [ ] 2.2 List each tainted commit in `_taint_refusal`, marking merge commits. Verify with a test where a merge commit made outside the hooks taints the change, and `gates merge` step 1 names its sha and marks it a merge commit [oracle: unit]
- [ ] 2.3 Add the sync route to `skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md`. Verify by convention review against `stack-agnostic-prompts` [oracle: none]

## 3. Denials that name their cause (D6, D7, D8)

- [ ] 3.1 Catch manifest parse errors in `_load` on both YAML paths and exit with D6's one-line message. Verify with tests: a conflicted `.gates.yaml` under PyYAML and under `_mini_yaml` (forced) gives the same message shape, names the position and the conflict markers, and prints no traceback, for `validate` and for `discipline check-worktree` [oracle: unit]
- [ ] 3.2 Drop `gate-commit.sh`'s own shared-branch line in favour of the shim's message. Verify with hook tests: a conflicted manifest denies without mentioning another worktree, and a branch in two worktrees still names both [oracle: unit]
- [ ] 3.3 Expand `~`, `~/`, `$HOME` and `${HOME}` in `_resolve_cd_chain`, read a leading subshell, and exit 3 with the reason for an unresolvable `cd` chain. Make every hook that calls `git-cwd` deny on 3. Verify with resolver tests for each form, and with a commit-hook test that `cd "$LANE" && git commit` is denied naming `$LANE` [oracle: unit]

## 4. The handoff (D9, D10)

- [ ] 4.1 Add the file's blob at `merge-base HEAD <target>` to placement's allowed set. Verify with a real-repo test: main changes a pre-existing test file after the handoff, the branch syncs, and placement succeeds; a lane-only edit still refuses as a test defect [oracle: unit]
- [ ] 4.2 Make a full `tests handoff` refuse when a placed task is absent from the holding area. Verify with a test: 1.1 placed (characterization), a full handoff holding only 1.2 exits 1 naming 1.1 and the `--task` route, and the authoring state is unchanged [oracle: unit]

## 5. The READY report (D11)

- [ ] 5.1 Make `record-ready` print the derived `gates` block. Verify with tests for `review` `none`, `partial`, `findings` and `clean`, for `ci` pass and fail, and for `live_check` `na` when undeclared [oracle: unit]
- [ ] 5.2 Update the report schema in `agents/tdd-implementer.md` to `clean|findings|partial|none` and say to copy `record-ready`'s block unchanged. Verify by convention review [oracle: none]

## 6. Docs

- [ ] 6.1 Document the approval check at merge, the sync route, the resolved `cd` forms and the exit-3 denial in SETUP.md and AUTOMATION.md. Verify that `scripts/release docs` reports no gap and `gates run ci` is green [oracle: none]

## Workflow follow-up

- Open the implementation PR with "Fixes #101", "Fixes #108", "Fixes #109", "Fixes #110", "Fixes #111" and "Fixes #112".
- The release notes say that a change amended without re-attesting now stops at `gates merge`, that a committing sync merge is denied, and that a `cd` to an unresolvable target is denied.
