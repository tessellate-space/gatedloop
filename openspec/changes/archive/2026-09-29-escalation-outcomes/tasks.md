# escalation-outcomes — Tasks

## 1. Row shape and the cause set (design D1, D2, D5 part 1)

- [x] 1.1 Add tests in `tests/test_ledger.py`: `LEDGER_ROW_FIELDS` ends with `cause`, `detail`, `session` (in that order, after `scope`); `_append_ledger_row` fills all three as `None` when absent; every row it writes carries `session: "agent"` when `CLAUDECODE` is set in the environment and `"human"` when it is not (patch `os.environ` in a throwaway repo). Verify the tests fail on the unmodified shim.
- [x] 1.2 In `bin/gates`, append `cause`, `detail`, `session` to `LEDGER_ROW_FIELDS`; set `session` inside `_append_ledger_row` from `os.environ.get("CLAUDECODE")`; define `HALT_CAUSES` next to `REVIEW_VERDICTS`; add `"halt"` and `"intervention"` to `NON_GATE_EVENTS`. Verify 1.1 passes and the existing `test_ledger.py`, `test_stats.py`, `test_audit.py`, `test_taint.py` suites still pass.

## 2. `gates halt record` and `gates intervention record` (design D2, D4)

- [x] 2.1 Add `tests/test_halt_record.py`: in a throwaway repo on a change branch, `gates halt record stalled --task 2.3 --detail "x"` appends one row with `gate: "halt"`, `task: "2.3"`, `cause: "stalled"`, `detail: "x"`, `exit: None`, `tree` equal to `HEAD^{tree}`; an unknown cause exits non-zero and writes nothing, stderr lists the six causes; `other` without `--detail` exits non-zero naming the requirement; on `main` with no `--change` it exits non-zero naming the missing change. Verify all fail on the unmodified shim (unknown subcommand).
- [x] 2.2 Implement `cmd_halt` (`record`) and register the `halt` subparser (`cause` positional, `--task`, `--detail`, `--change`). Verify 2.1 passes.
- [x] 2.3 Add to `tests/test_halt_record.py`: `gates intervention record ask --task 2.3 --detail "which port?"` appends `gate: "intervention"`, `cause: "ask"`; a kind other than `ask` or `human-commit` is refused naming both. Implement `cmd_intervention` (`record`) sharing the validation helper with `cmd_halt`. Verify the tests pass.

## 3. A recorded halt stops the loop (design D3)

- [x] 3.1 Add tests in `tests/test_planning_grade_commit.py` or a new `tests/test_check_continue_halt.py`: on a change branch with an unchecked task and a clean tree, `gates discipline check-continue` exits 0 today; after `gates halt record weak-spec --task 1.2` it exits non-zero and stderr names `weak-spec` and `gates task start`; after a subsequent `gates task start 1.2` it exits 0 again; a `halt` row older than the latest `task-start` does not block. Verify the halt cases fail on the unmodified shim.
- [x] 3.2 Extend `check-continue` in `cmd_discipline`: read the change's rows, find the last `halt` and last `task-start` by file order, return 1 with the cause and remedy when the halt is later. Verify 3.1 passes and `hooks/continue-loop.sh` needs no change (it already exits 0 on a non-zero check).

## 4. The `ask` hook (design D4)

- [x] 4.1 Add `tests/test_record_ask_hook.py`: pipe a `PreToolUse` JSON payload for `AskUserQuestion` (with `tool_input.questions[0].question`) into `hooks/record-ask.sh` with `cwd` at a throwaway repo on a change branch; assert exit 0 and one `intervention/ask` row whose `detail` is the question text truncated to 200 characters; on `main` assert exit 0 and no row; with an unwritable ledger directory assert exit 0 and a stderr line. Verify the tests fail (script absent).
- [x] 4.2 Write `hooks/record-ask.sh` (resolve the repo via `gates hook git-cwd`, extract the first question with stdlib Python, call `gates intervention record ask --detail …`, always exit 0) and register it in `hooks/hooks.json` under `PreToolUse` with matcher `AskUserQuestion`, timeout 10. Verify 4.1 passes and `claude plugin validate .` (via `./bin/gates run ci`) is green.

## 5. Human-commit classification in the audit (design D5 parts 2 and 3)

- [x] 5.1 Add tests in `tests/test_audit.py`: a commit whose only green-`ci` row has `session: "human"` yields one `intervention/human-commit` row with that SHA and no taint; a commit with an `agent`-session green row yields nothing; a commit whose green rows have `session: None` yields neither taint nor intervention; running the audit twice appends no second intervention row for the same SHA; a commit with no green row still taints exactly as today. Verify the new cases fail on the unmodified shim.
- [x] 5.2 Extend `cmd_audit`: keep the matching green rows per commit, classify per design D5, extend the SHA-dedupe set to intervention rows, print one stderr line per classification. Verify 5.1 passes and the existing audit tests (adoption exemption, no-target widening, cursor) still pass.
- [x] 5.3 Add a case to `tests/test_merge_gate_incoming_tree.py` (or a new e2e test): a commit created on the branch after the last audit with no green record is tainted by the merge hook's own audit call and the merge is denied naming the taint. Then edit `hooks/gate-merge.sh` to run `"${GATES}" audit >/dev/null 2>&1 || true` immediately before the taint check. Verify the test passes and the hook's existing tests still pass.

## 6. `gates stats --outcomes` (design D7)

- [x] 6.1 Add `tests/test_outcomes.py` for a pure `outcomes_from_rows(rows)`: terminal derivation (`merged` / `halted` / `in-progress`, including a `task-start` after the last `halt`); `hands_off` true only for merged with zero `halt`/`intervention`/`taint`; halts by cause with every member of `HALT_CAUSES` present (zeros included) and an unknown cause counted under `malformed_halts`; interventions by kind; `first_ts`; rows without `session` counted. Verify the tests fail (function absent).
- [x] 6.2 Implement `outcomes_from_rows` beside `stats_from_rows`, and the `--all` aggregate (`hands_off_share` as `{numerator, denominator, value|null}`, `halts_by_cause`, `interventions_by_kind`, `taints`, per-month `trend` keyed on `first_ts`). Verify 6.1 passes.
- [x] 6.3 Add CLI cases to `tests/test_stats_cli.py`: `gates stats --outcomes --change <name>` prints the human table with terminal state, verdict and breakdowns; `--outcomes --all` prints the hands-off line as `N of M merged changes` and "not computable" when nothing is merged, exiting 0; `--outcomes --json` is exactly one JSON document with the documented keys, byte-identical across two runs; missing ledger fails loud as today. Implement the `--outcomes` flag and formatter in `cmd_stats`, ending the human report with the three named blind spots. Verify the tests pass and `gates stats` without `--outcomes` produces byte-identical output to before.

## 7. Prompts and docs (design D6, D8)

- [x] 7.1 `agents/tdd-implementer.md`: add the seventh report field `"cause"`, the record-before-report rule, and the cause table mapping §1/§5/§6 and the two remaining causes; keep every existing field and the "do not merge" text. Verify by reading the diff against design D6 and confirming no stack tool name was introduced (`gates rules` → convention review on the `prompts` surface).
- [x] 7.2 `skills/tdd-apply/SKILL.md`: at §5e, §6 and §7's "pause and ask", add one sentence that the pause is recorded by the question-tool hook and that a pause outside the tool is recorded with `gates intervention record ask --task <N.M>`. Verify by diff; no other prose changes.
- [x] 7.3 `SETUP.md` (report shape in "Running headless", the `gates` command reference gains `gates stats --outcomes`, `gates halt record`, `gates intervention record`) and `AUTOMATION.md` (report shape; the hooks table gains the `AskUserQuestion` hook and the merge hook's audit call). Verify every command named exists by running each with `--help`.
- [x] 7.4 `docs/gate-economics.md`: a short section "Reading the outcomes view" (what hands-off means, why taints count, the three blind spots). `docs/candidates.md`: one sentence in the `gates audit` entry noting `--outcomes` now supplies the run-history half. Verify by reading.

## 8. Closure

- [x] 8.1 Run `python3 -m unittest discover -s tests` and `./bin/gates validate`; verify green.
- [x] 8.2 End-to-end in a throwaway repo with `ci: "true"`: on a change branch with two unchecked tasks, run `gates task start 1.1`, `gates run ci --task 1.1`, commit, then `gates halt record stalled --task 1.2 --detail e2e`; confirm `gates discipline check-continue` exits non-zero naming `stalled`, `gates stats --outcomes` shows `halted` with `stalled: 1`, then `gates task start 1.2` makes `check-continue` exit 0 again and `--outcomes` shows `in-progress`. Unset `CLAUDECODE`, run `gates run ci --task 1.2` and commit; re-set it, run `gates audit`; confirm one `intervention/human-commit` row and that `--outcomes` shows the change as `assisted` once a `merge` row is recorded with `gates ledger record-merge`.
