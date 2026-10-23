# acceptance-gate — Tasks

Depends on `escalation-outcomes` (issue #23) having landed: `cause`/`detail` row fields,
`HALT_CAUSES`, `outcomes_from_rows`. Do not start before it is on `main`.

## 1. Policy and manifest shape (design D1, D5 key)

- [x] 1.1 Add tests in `tests/test_approval_policy.py`: `approval: {plan: self, acceptance: self}` validates; `acceptance: nope` fails naming `review`/`self`; `acceptance: review` with no `integration` block or with `mode: local-squash-merge` fails naming the conflict and both resolutions; `acceptance: review` with `mode: pull-request` validates; `_acceptance_policy(m)` returns `None` when undeclared. Verify the new cases fail on the unmodified shim.
- [x] 1.2 Add tests in `tests/test_manifest.py`: a top-level `acceptance: {match: "features/**/*.feature"}` validates; `acceptance: {dir: x}` fails naming `match`; an extra key fails. Verify they fail on the unmodified shim.
- [x] 1.3 Extend `schema/gates.schema.json` (`approval.acceptance` enum; top-level `acceptance` object with required `match`, no additional properties) and the shim's validation (including the review-without-PR conflict, which JSON Schema cannot express); add `_acceptance_policy`. Verify 1.1 and 1.2 pass and `./bin/gates validate` on this repo's manifest is still green.

## 2. Row shape and the writers (design D2, D3)

- [x] 2.1 Add tests in `tests/test_ledger.py`: `LEDGER_ROW_FIELDS` ends with `accepted_by` after `session`; `acceptance` is in `NON_GATE_EVENTS`; `stats_from_rows` ignores acceptance rows for gate arithmetic. Verify they fail; then append the field, add the event, verify they pass.
- [x] 2.2 Add `tests/test_acceptance_attest.py`: in a throwaway repo with `approval: {plan: self, acceptance: self}` on a change branch, `gates acceptance attest <change> --local` appends one `acceptance/accept` row whose `tree` equals `_normalize_tree(HEAD^{tree})` and whose `accepted_by` is the git identity, and changes no tracked file; with `acceptance: review` it refuses naming `--pr`; with no `acceptance` key both writers refuse naming `approval.acceptance`; `--as` changes only `accepted_by`. Verify the cases fail (unknown subcommand).
- [x] 2.3 Add to `tests/test_acceptance_attest.py`: `--pr <n>` with a stubbed `gh` on `PATH` returning an `APPROVED` review appends an `accept` row with the review author; a stub returning no approving review exits non-zero and appends nothing; a missing `gh` exits non-zero and appends nothing; `--pr` with `--as` refuses. Reuse the stub approach `tests/test_approval.py` uses.
- [x] 2.4 Add to `tests/test_acceptance_attest.py`: `gates acceptance reject <change> --cause weak-spec --detail t` appends a `reject` row with cause, detail and the normalized head tree; cause `stalled` is refused naming the two allowed; empty detail is refused.
- [x] 2.5 Implement `cmd_acceptance` (`attest --local|--pr`, `reject`, `policy`) with a shared `_first_approving_review(root, pr)` helper extracted from `cmd_approval_attest` and reused by it; register the `acceptance` subparser. Verify 2.2–2.4 pass and `tests/test_approval.py` still passes after the extraction.

## 3. `gates acceptance check` and the merge hook (design D4)

- [x] 3.1 Add `tests/test_acceptance_check.py`: with no policy, `gates acceptance check <tree>` exits 0 and prints "not required"; with `self` and no rows, exits 1 naming `gates acceptance brief` and `gates acceptance attest`; after `--local`, exits 0 for the head's normalized tree and 1 for a different tree; after a later `reject` for the same tree, exits 1 naming the cause; after a still-later `accept`, exits 0. Verify the cases fail (unknown subcommand).
- [x] 3.2 Implement `check` in `cmd_acceptance` (latest matching row wins, file order). Verify 3.1 passes.
- [x] 3.3 Add an e2e case to `tests/test_merge_gate_incoming_tree.py`: with `approval.acceptance: self`, a green live-check marker and no taint, the merge hook denies naming acceptance; after `gates acceptance attest --local` on the branch head the same merge is allowed; with no policy declared the hook's behaviour is byte-identical to before. Then add the `gates acceptance check "${matched_tree}"` call to `hooks/gate-merge.sh` after the taint check. Verify the test passes and every existing merge-gate test still passes.

## 4. The brief (design D5)

- [x] 4.1 Add `tests/test_acceptance_brief.py`: in a throwaway repo with a change whose spec has two scenarios and `acceptance.match` pointing at a file that titles one of them (different case), the brief lists one `covered`, one `check by hand`, exactly one item in the check-by-hand list, and the footer sentence; with no `acceptance.match`, both are `check by hand` and the stated reason appears; two runs are byte-identical; a green `verify` row for the head tree shows as a verdict while a green `live-check` row for an older tree shows `absent`; `--out` writes the same bytes to the given path. Verify the cases fail (unknown subcommand).
- [x] 4.2 Implement `brief` in `cmd_acceptance`: scenario walk, marker-set title extraction from `acceptance.match` files, tree-scoped ledger verdicts, deterministic rendering, `--out`. Verify 4.1 passes and that writing the brief to `.specloop/runs/<change>.acceptance.md` and committing it leaves `_normalize_tree(HEAD^{tree})` unchanged (add that assertion to 4.1).

## 5. Outcomes terminal event (design D7)

- [x] 5.1 Add tests in `tests/test_outcomes.py`: with policy `self`, an `accept` row whose tree equals the `merge` row's tree yields `terminal: accepted` and `hands_off: true`; a `merge` row with no matching accept yields `merged`, `hands_off: false` with the missing acceptance named; an accept for a different tree than the merge yields `merged`; a `reject` row with cause `missing-oracle` counts under `halts_by_cause`; with policy `None` every result is identical to before this change. Verify the new cases fail.
- [x] 5.2 Extend `outcomes_from_rows(rows, acceptance_policy=None)` and the `--all` share; `cmd_stats` passes `_acceptance_policy(m)`; the human report states "metric ends at merged — no acceptance policy declared" when undeclared. Verify 5.1 and the existing outcomes/stats tests pass.

## 6. Prompts and docs (design D6)

- [x] 6.1 `skills/tdd-apply/SKILL.md` §7.5: insert the brief step after the live-check and the stop-for-acceptance rule under a declared policy, worded to match the existing `requireApproval: true` stop; add the same rule to Guardrails. Verify by diff; no stack tool names (`gates rules` → convention review on the `prompts` surface).
- [x] 6.2 `agents/tdd-implementer.md`: §4 generates the brief last; the report gains the eighth field `"acceptance"`; keep all existing fields. Verify by diff against design D6.
- [x] 6.3 `skills/verify/SKILL.md` Layer 1: replace the restated match rule with "run `gates acceptance brief <change>` and read its coverage list", keeping the verdict format and guardrails. Verify by diff.
- [x] 6.4 `SETUP.md`: the approval section gains `acceptance: review | self`, the writers, `reject`, and the honesty note's acceptance counterpart; the branch-protection section states the required review is the acceptance review under `acceptance: review`; the command reference gains the `gates acceptance` family; "Running headless" lists the eighth report field. `AUTOMATION.md`: the report shape and the merge hook's fourth check. Verify every named command runs with `--help`.
- [x] 6.5 `templates/gates.yaml.template`: commented examples of `approval.acceptance` and `acceptance.match` with one line each on what they do. `docs/gate-economics.md` "Reading the outcomes view": one paragraph on `accepted` vs `merged`. Verify `./bin/gates init` in a throwaway directory still yields a manifest that validates.

## 7. Closure

- [x] 7.1 Run `python3 -m unittest discover -s tests` and `./bin/gates validate`; verify green.
- [x] 7.2 End-to-end in a throwaway repo with `ci: "true"`, a surface with `live-check: "true"`, `approval: {plan: self, acceptance: self}` and `acceptance.match` pointing at a features file: complete a one-task change through the loop's completion steps; confirm `gates acceptance brief` shows the covered/uncovered split and the tree-scoped verdicts; confirm `git merge --squash` is denied naming acceptance; run `gates acceptance attest <change> --local`; confirm the merge is allowed; `gates ledger record-merge`; confirm `gates stats --outcomes` shows `accepted` and `hands-off`. Repeat with a `reject` and confirm the denial names `weak-spec` and `--outcomes` counts it.
