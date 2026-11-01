## Context

The source is an adopter orchestrator's report from lanes run on 0.8.0. Each item was checked on `origin/main` at 15fd52c, which is 0.9.0 plus the 0.10 merges of `err-full-scoping` and `friction-fixes`. Each was reproduced in a scratch repository or traced in the code:

| Item | Status on main | Where |
|---|---|---|
| Merge and acceptance skip the approval check | present | #101: `_merge_prove_head` and the acceptance writers never call `_approval_check_at` |
| A committing sync merge slips the commit hooks, then taints at merge step 1 | present | #108: `gate-merge.sh` passes every not-integrating merge; git runs no pre-commit hook for a merge commit |
| A conflicted manifest is reported as a shared branch | present, reproduced | #109: `load_manifest` raises a yaml `ScannerError`; `gate-commit.sh` adds "shared with another worktree" to any non-zero exit |
| `cd ~/…`, `cd $HOME/…` and `( cd … )` judge the wrong repository | present, reproduced | #110: `_resolve_cd_chain` joins `~` as a relative path and abandons `$`; the splitter leaves `(cd` as one token |
| A `--task` re-handoff keeps a stale base; a full handoff drops placed tasks | present | #111: `_authoring_state` keeps the first base (`setdefault`); a full handoff rebuilds state from the holding area only |
| The READY report can't say no review ran | present | #112: the schema allows `clean\|findings`; `record-ready` prints no gate facts |
| Attempts counted across a test-defect cycle; restart demands a clean tree | fixed in 0.8.0 | unblock-authored-lock D6 counts from the latest placement; D7 treats placed tests as clean |
| A queued gate run starts under the previous run's load | not a gatedloop guarantee | The lock promises serialization, not an idle machine. The flake was the adopter's whole-second wall-time self-test, which they are fixing |
| The merge hook refused `cd`/switch-then-merge shapes | fixed in 0.10 | friction-fixes D5 |

`friction-fixes` modifies the `Only integration merges are gated` requirement and is not archived yet. This change therefore adds requirements instead of modifying that one. D3 below narrows what passes the merge hook for a sync; it doesn't touch the marker checks that requirement is about.

## Goals / Non-Goals

**Goals:**
- No change merges, or is accepted, on a plan that isn't the approved one.
- A sync of main into a lane goes through the same commit gate as every other commit.
- Every denial names its real cause.
- The hooks judge the repository the command actually runs in, or say they can't tell.
- A handoff never loses tests and never blames the author for main's change.
- The READY report's gate fields are read from the ledger.

**Non-Goals:**
- Installing a git `pre-merge-commit` hook. The reflog audit already catches a merge commit made outside a session. The in-session merge hook is where a lane needs to be told the route, so this change fixes it there.
- Evaluating arbitrary shell. A `cd` to a variable other than `HOME`, or to a command substitution, stays unresolved (D8).
- New manifest keys.

## Decisions

### D1. `gates merge` proves the plan approval before step 1's evidence

`_merge_prove_head` runs `_approval_check_at(root, change, m)` first, in both local and pull-request mode. It then compares `_approval_sha_ref(root, change, "refs/heads/<change>")` with the `approved_sha` read on the target.
- The first check catches #101's case: a plan amended on the target and never re-attested.
- The second catches a branch that edited its own plan artifacts after approval.

Either failure is a step-1 problem, reported with the existing re-approval route. An untagged `tasks.md` stays outside the sha, as today, so a tick or a task-only amendment never needs re-approval.

Alternative: check only the branch head. Rejected, because a lane that synced main carries main's amended plan, and the two hash the same. The comparison has to be against the recorded `approved_sha`, and that lives on the target.

### D2. Every acceptance writer refuses an unapproved plan

`gates acceptance attest` runs the same two checks as D1 before writing, with `--local`, `--pr` or `--merged`. For `--merged`, the head is the merge commit, read from the merged PR as merged-acceptance D2 does.

Under `self`, `record-merged` still records the merge row, because the forge merge already happened. It writes no `accept` row, and exits non-zero with the reason, so the job is red and names the re-approval.

### D3. A sync into a change branch may not create its own merge commit

In `gate-merge.sh`'s not-integrating branch, the hook now asks whether the merge would commit:
- `--no-commit`, `--squash`, `--ff-only` and `--abort` never do.
- A bare merge where HEAD is an ancestor of the ref is a fast-forward unless `--no-ff` is given. This keeps #44's case passing.
- Anything else commits, including `--continue`, which concludes a merge.

A committing merge is denied with: "a merge into change branch `<b>` creates a commit no gate saw — run `git merge --no-commit <ref>`, then `gates run ci`, then `git commit`." `_gate_match.py` reports the merge's flags. When the ref couldn't be parsed and the merge isn't a fast-forward by flag, the hook denies the same way.

The commit that concludes the sync is an ordinary `git commit`, so `gate-commit.sh` and the git-layer pre-commit gate it as usual.

### D4. The prompts give the sync route

`skills/tdd-apply/SKILL.md` and `agents/tdd-implementer.md` say that main is synced with `git merge --no-commit origin/main`, then `gates run ci`, then a commit, and never with a committing merge. One sentence each, naming no stack tool.

### D5. The taint refusal names its commits

`_taint_refusal(change, rows)` lists each unresolved taint row's commit, short sha and subject. A commit with more than one parent is marked "(merge commit — see the sync route)". The remedy is unchanged: one green `gates run ci` on the head clears it.

### D6. An unparseable manifest fails loud in one line

`_load` catches any parse error from PyYAML or `_mini_yaml` and exits 1 with: `gatedloop: .gates.yaml could not be parsed at line L, column C: <reason>`. When a line starts with `<<<<<<<`, `=======` or `>>>>>>>`, it adds "it holds merge-conflict markers — resolve the conflict first". Both YAML paths produce the same message shape (`manifest-parsing`). No traceback reaches the user.

### D7. The commit hook names a shared branch only when that is the verdict

`gate-commit.sh` stops adding its own "this branch is shared" line. `check-worktree` already prints the holders when it refuses, and D6's message when the manifest is broken. The hook prints the shim's output followed by "commit denied in `<repo>` — see above". No exit-code contract is introduced.

### D8. `hook git-cwd` expands home and reads a leading subshell, and an unresolved `cd` denies

- `~`, `~/…`, `$HOME/…` and `${HOME}/…` expand from the hook process's `HOME`.
- A command whose first token begins with `(` is split as if the parentheses were absent. The `cd` inside it governs only that subshell's commands, which is where the git invocation is.
- `~user` and any other `$` or backtick target stay unresolvable.

The behaviour change: when the `cd` chain before the guarded invocation is unresolvable, `git-cwd` exits 3 with the reason on stderr, instead of falling through to the hook cwd. Every hook that calls it denies on 3 with "could not resolve the directory of `cd <target>` — use an absolute path or `git -C <dir>`". This supersedes worktree-native-loop D1's fall-through for the `cd` rung only. Falling through judged the session's checkout, which could allow or deny on evidence about a different repository. Exits 0 and the `git -C`, `GIT_DIR` and `--work-tree` rungs are unchanged.

### D9. Placement accepts main's content for a file

In `_tests_place`, the allowed set for a path gains the file's blob at `git merge-base HEAD <target>`. That is the content the branch received from main at its last sync, so a pre-existing test main changed is no longer called a test defect. With no resolvable target, the set is unchanged, so placement still fails closed.

Alternative: refresh `base` on every `--task` re-handoff. Rejected, because the handoff runs in the author's worktree, which may not have synced, and base is meant to stay "content before the change touched it".

### D10. A full handoff may not drop a placed task

`_tests_handoff` without `--task` compares the tasks it is about to record with the tasks holding a placement under the current authoring state (`_active_placements`). If a placed task is absent from the holding area, it refuses, naming each such task and `gates tests handoff <change> --task <N.M>` for the tasks being re-authored.

Alternative: carry placed tasks forward silently. Rejected, because a full handoff is the author's statement of the whole set, and guessing its intent is the silent behaviour this repo refuses.

### D11. `record-ready` prints the report's gate block from the ledger

`gates ledger record-ready` prints `gatedloop: gates {"ci": …, "review": …, "live_check": …}` after writing the row:
- `ci`: `pass` when a green unscoped `ci` row exists for the head's normalized tree, else `fail`.
- `review`: the latest review row of every completed task.
  - `clean` when all are clean.
  - `findings` when any is findings.
  - `partial` when some completed task has none.
  - `none` when the change has no review row.
- `live_check`: `pass`, `fail`, or `na` for a skip verdict or an undeclared gate, read from the marker for the head tree.

`agents/tdd-implementer.md`'s report schema allows `"review": "clean|findings|partial|none"` and says to copy the printed block unchanged. The ledger row's shape is unchanged.

### D12. Rejection test

Every decision either makes a stated guarantee enforceable (D1, D2, D3, D9, D10, D11) or makes a denial name its cause (D5, D6, D7, D8). None authors an artifact or names a stack command.

## Risks / Trade-offs

- **D1 and D2 will stop changes merged on 0.9.0 habits.** A change whose plan was amended without re-attesting now stops at merge. This is the guarantee #101 asked for, and the refusal gives the one-command route. The 0.10 or 0.11 release notes call it out.
- **D8 will deny commands that passed before.** `cd "$WT" && git commit` used to be judged against the session's checkout, often wrongly. It is now denied with the route. The release notes call it out.
- **D3 denies a habit.** A lane that ran `git merge origin/main` is told the three-step route. The rare legitimate `--no-ff` sync uses the same route.
- **Interaction with `stability-contract`.** If that change lands first, `hook git-cwd`'s new exit 3 is internal, per its D4, and needs no snapshot entry. `record-ready`'s printed line isn't a frozen output.
