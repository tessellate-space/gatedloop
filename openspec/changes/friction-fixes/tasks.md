# Tasks

## 1. Lettered task ids (D1–D4)

- [ ] 1.1 Define `TASK_ID_PATTERN` and build `_TASK_LINE_RE` and `_CHECKED_TASK_RE` from it. Verify with tests showing a `1.2a` line read by `_task_lines_text` with its oracle tag, by the test author's brief, by the completion walk (a committed `[x] 1.2a` before a halt row leaves the placement in force), and by the D9 approval digest (retagging `1.2a` voids the approval). Also test that `1A.2`, `1.2-b` and an unnumbered line are not read [oracle: unit]
- [ ] 1.2 Add `_task_sort_key` and use it in `tests show`, the `stats` usage table and both cost listings. Verify with a test that `gates tests show` on a change holding `1.2a` exits 0 and lists `1.2`, `1.2a`, `1.9`, `1.10` in that order (with `--json` too), and that the usage and cost listings use the same order [oracle: unit]
- [ ] 1.3 Narrow the `validate` warning to ids outside the grammar, with the new wording and no `#46` reference. Verify by updating `tests/test_task_oracle_validate.py`: a tagged `1.2a` draws no warning and its tag is validated like any other (an unknown gate on `1.2a` fails), and an unnumbered tagged line still warns [oracle: unit]

## 2. Switch-then-merge (D5)

- [ ] 2.1 Make `_gate_match.py` report `switch_branch` for the `git-merge` kind, per D5. Verify with matcher tests for `checkout my-change`, `switch my-change`, `checkout -b x origin/main`, `switch -c x`, `--detach`, `checkout -- path`, two switches (the last one wins), and an unparsable command (empty) [oracle: unit]
- [ ] 2.2 Add `--branch <b>` to `gates discipline merge-scope`, and have `hooks/gate-merge.sh` use it when `switch_before=1` and `switch_branch` is set. Add the unresolved-switch line to the denial. Verify with hook tests in a real repo with a remote: `checkout my-change && merge --ff-only origin/main` passes; `checkout main && merge --ff-only my-change`, `checkout -b main …` and `checkout --detach origin/main && merge my-change` are gated; and the last of these carries the new line [oracle: unit]

## 3. The authored-set review (D6)

- [ ] 3.1 Add D6's coverage rule to the authored-set paragraph of `agents/convention-review.md`, keeping the task-oracle D8 tag rule and the read-only budget. Verify by the convention review against `stack-agnostic-prompts` and the test-quality items it cites [oracle: none]

## 4. Docs

- [ ] 4.1 Document the task-id grammar beside the oracle tag syntax in SETUP.md, and the switch-then-merge case in AUTOMATION.md's merge hook section. Verify that `scripts/release docs` reports no gap and `gates run ci` is green [oracle: none]

## Workflow follow-up

- Open the implementation PR with "Fixes #46" and "Fixes #44", and "Fixes #47" when 3.1 lands.
- The 0.10.0 release notes say that a plan with an oracle tag on a lettered line needs its approval re-recorded once.
