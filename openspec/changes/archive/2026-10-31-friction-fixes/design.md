## Context

The three issues are independent and share one plan because each is small. See proposal.md, Why.

- **Task ids.** `bin/gates` has two task-line regexes, both spelled `\d+(?:\.\d+)+`:
  - `_TASK_LINE_RE` is read by `_task_lines_text`, the `validate` tag check and `_oracle_tag_pairs`;
  - `_CHECKED_TASK_RE` is read by the completion walk.

  `_tests_show_doc` sorts with `[int(x) if x.isdigit() else x for x in t.split(".")]`, which compares `int` with `str` for `1.2a` (#46). Every other task listing in the shim uses a plain string sort: the `stats` usage table and the cost lines. That sort puts `1.10` before `1.2` but does not crash. The holding area, `gates tests handoff --task` and the ledger take any id string, so `1.2a` is already accepted on the way in. Only the read side drops it.
- **The merge hook.** Since hook-correctness D2 (0.7.0), `hooks/gate-merge.sh` skips its marker checks when `gates discipline merge-scope` prints `not-integrating` and `_gate_match.py` reports `switch_before=0`. Any `git checkout` or `git switch` earlier in the same command sets `switch_before=1`, so the merge stays gated. Reproduced on `origin/main`:
  - `git merge --ff-only origin/main` on a change branch passes;
  - `git checkout my-change && git merge --ff-only origin/main` is denied with "no 'live-check' marker found".
- **The authored-set review.** Since task-oracle D8 (0.9.0), `agents/convention-review.md` judges a `NO-TESTS` reason against the task's tag when it has one. An untagged task is still judged against its own line and the specs.

## Goals / Non-Goals

**Goals:**
- A lettered task behaves like any other task in every read path.
- A lane can sync its branch in the single command an agent naturally writes.
- An untagged plan that splits writing a test from implementing it draws no false finding.

**Non-Goals:**
- Any id form beyond one trailing lowercase letter: no `1.2-b`, no `1a.2`, no unnumbered tasks.
- Letting a fast-forward into the integration target through. A `git merge --ff-only my-change` on `main` lands the change's commits, and it is integration whatever its shape. #44 reads "a pure fast-forward passes", but the safe rule is "a merge into a change branch passes", which 0.7.0 already ships.
- Flagging the split plan at `gates tests handoff` (#47's second option). The review is where the misread happens, and the handoff cannot tell from prose which task a test belongs to.

## Decisions

### D1. One task-id grammar, in one constant

`TASK_ID_PATTERN = r"\d+(?:\.\d+)+[a-z]?"` is defined once, and both task-line regexes are built from it.
- The letter goes on the last segment only, and only one, lowercase. Amendments in the wild are written `1.2a` and `2.2a` (#46), and one letter allows 26 inserts between two numbered tasks, enough for any plan this repo has seen.
- Uppercase is left out because `- [X] 1.2` is the checked marker's letter, and two ids differing only by case would be a typo, not two tasks.

Alternative: any `\S+` id. Rejected because then prose bullets that start with a word would read as tasks.

### D2. One sort key, used by every listing

`_task_sort_key(tid)` splits on `.` and maps each segment to `(int(digits), suffix)`, so `2` < `2a` < `3`. A segment the grammar would not produce sorts after every numeric segment, compared as a string, so a legacy ledger row with an odd task id never crashes a listing.

The key is used by:
- `tests show`;
- the `stats` usage table;
- the cost lines in `stats --cost` and the per-change cost listing.

Changing those listings from string order to natural order is a visible ordering change only, and nothing parses those tables.

### D3. The validate warning narrows to what is still unread

Since task-oracle D1, the `validate` check warns about a tag on any line `_TASK_LINE_RE` does not match. The warning stays, and its text changes: "the task parser reads ids of the form N.M or N.Ma". It now fires only for unnumbered or otherwise malformed ids. The `#46` reference leaves the message.

### D4. The approval digest includes lettered tagged lines

`_oracle_tag_pairs` reads through the widened `_TASK_LINE_RE`, so a tagged `1.2a` line now enters the D9 digest. An untagged plan, and a tagged plan with no lettered lines, hashes exactly as in 0.9.0.

Alternative: keep lettered lines out of the digest. Rejected, because a tag that changes the oracle without voiding the approval is the hole D9 closed.

### D5. The switch target decides a switch-then-merge

`_gate_match.py`'s `git-merge` match reports `switch_branch`. That is the branch named by the last `git checkout <b>`, `git switch <b>`, `git checkout -b <b> …` or `git switch -c <b> …` that runs before the merge in the same command, and it is empty when:
- that switch names no single branch: `--detach`, a `--` path checkout, more than one positional, or an unparsable command;
- a further switch to an unknown branch follows it.

`gates discipline merge-scope --branch <b>` then answers `not-integrating` exactly when `<b>` is a branch name other than the target's branch name.

`gate-merge.sh` uses this when `switch_before=1`:
- a non-empty `switch_branch` is judged by `merge-scope --branch`;
- an empty one stays gated, as today.

A denial issued while `switch_before=1` and `switch_branch` is empty adds one line: "this command switches branches before merging, and the hook could not tell which branch the merge lands on; run the merge as its own command after the switch."

Alternative: let any merge through where HEAD is an ancestor of the incoming ref. Rejected for the non-goal above. On `main` that describes integrating a change by fast-forward.

Alternative: run the switch's effect in a dry run. Rejected, because a hook must not touch the repository.

### D6. The authored-set review reasons over the set

`agents/convention-review.md`'s authored-set paragraph gains one rule. Before reporting a behaviour as lacking an oracle, the reviewer finds the task in `gates tests show` that holds a test for it. A `NO-TESTS` reason on a task whose work is writing a test held by another task of the change is consistent, not a finding. The reviewer may suggest that the plan merge the two tasks, phrased as a plan question for its caller, as task-oracle D8 phrases a wrong tag.

The reviewer stays read-only and keeps its call budget, because `gates tests show` is already its first call.

## Risks / Trade-offs

- [A plan with a tagged lettered line gets a new approval sha after the upgrade] → Rare. 0.9.0's `validate` already warned about every such line. The upgrade notes say to re-approve that plan, and `check-implement` names the stale approval if it is missed.
- [A prose bullet beginning `1.2a` now reads as a task] → It must also be a `- [ ]` checkbox line, which OpenSpec already counts as a task.
- [The switch parse misses a shape and gates a legitimate sync] → It fails closed. The denial now names the fix, and running the merge alone always works.
- [The switch parse reads a branch wrongly and lets an integration through] → Only a branch name other than the target's is let through. Any doubt, such as detached, paths or several positionals, keeps the gate. Tests cover the checkout-to-target shapes: `main`, `-b main`, and `checkout main` following `checkout my-change`.
- [D6 is a prompt change with no oracle] → It is judged by the convention review, as every prompt change in this repo is.

## Migration Plan

Nothing to migrate. The 0.10.0 release notes say that a plan with an oracle tag on a lettered line needs its approval re-recorded once.
