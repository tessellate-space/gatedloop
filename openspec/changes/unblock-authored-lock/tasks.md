# Tasks

## 1. Ledger-grade commits skip the lock (D1)

- [x] 1.1 Add `--verdict-file <path>` to `gates discipline check-commit`, writing one token (`ledger`, `planning`, `marker`) on success with exit status and printed text unchanged; verify with tests that assert the token for each verdict and that output without the flag is byte-identical to today's
- [x] 1.2 Make `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit` skip `gates tests check` when the token is `ledger`, and update AUTOMATION.md's lock description; verify with real-repo tests in which a ledger-only commit is allowed by both hooks while the lock would fail, and a ledger row staged with an edited placed test is still refused

## 2. Completion is ordered by commits (D2)

- [x] 2.1 Compute, per evaluation, the first commit checking each task in the change's `tasks.md` and the first commit carrying each ledger row, over the branch's first-parent history from its merge-base, with uncommitted and lane-only rows placed after the last commit; verify with tests for a halt committed after the tick (completed), a halt staged with the tick (not completed), an uncommitted row, a ledger that shrinks (refused, naming the commit), and a pinned blob-read count per commit

## 3. Halts and reopens (D3, D4)

- [ ] 3.1 Stop a `halt` row from voiding a completed task's placement; verify with tests, both at the index and with `--ref`, that a completed `NO-TESTS` task followed by a committed halt passes the lock, and that a halt in flight still voids the placement
- [ ] 3.2 Accept, for a task reopened by a defect after completion, a red `unit` run recorded after its first placement, while condition 1 checks the re-placed content; verify with tests for a reopened task placed again with no new red run (passes), a reopened test edited after re-placement (refused), and a `gates merge` step-1 head proof on a fixture shaped like #56 (a completed `NO-TESTS` task with a later halt, and a completed task reopened by a `green` defect and re-handed off as `CHARACTERIZATION`) that proves the head

## 4. The `green` defect kind (D5)

- [ ] 4.1 Add `green` to the defect kinds with a cap of 1 and halt cause `oracle-conflict`, with the refusal naming that halt; verify with tests that `green` spends neither other cap, that a second `green` is refused, and that `gates stats --outcomes` and `gates tests show` report it by kind
- [ ] 4.2 Teach `agents/tdd-implementer.md` and `skills/tdd-apply/SKILL.md` to record `green` for placed tests that pass before implementation, and `agents/test-author.md` to answer a `green` defect (re-declare or rewrite) and a reopened completed task, stating the interim rule that a file the `unit` gate never runs is declared `CHARACTERIZATION` until `task-oracle`; update SETUP.md's defect table and command list and AUTOMATION.md's defect paragraph; verify that the convention review of the `prompts` surface reports no `stack-agnostic-prompts` finding and that `scripts/release docs` reports no gap

## 5. Attempt budget and restart (D6, D7)

- [ ] 5.1 Start the failed-attempt window at the later of the task's latest `task-start` and its latest `tests-placed` row; verify with a test where a `setup` defect cycle's red runs are followed by a re-placement and a first red run, and the count is zero
- [ ] 5.2 Make `gates attempt restart` treat the task's placed tests at exactly their placed content, and the removal of their holding files, as clean, while naming any other placed content in its refusal; verify with tests for the accepted case, an edited placed test (refused, path named) and an unrelated dirty file (refused)

## 6. Integration

- [ ] 6.1 Run `./bin/gates run ci` on the finished branch and `gates tests check --ref HEAD` on the #56-shaped fixture, and verify both exit 0

## Workflow follow-up

- Open the implementation PR with "Fixes #56" and "Fixes #49". The release notes tell adopters with the git-layer hook to re-run its install.
- After merge, plan `task-oracle` (per-task oracle tags in `tasks.md`) as the follow-up change. Re-triage #47 against it.
