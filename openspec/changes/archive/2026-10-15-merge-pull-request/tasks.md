## 1. Markers as statuses

- [x] 1.1 `gates marker publish <gate> [--sha]` per design D1 (green local marker required; `specloop/<gate>` status carrying the normalized tree; skip-verdict wording; `target_url` in CI); tests with a fake `gh` on PATH recording its arguments
- [x] 1.2 `gates marker check-remote <gate> <sha>` per design D1; tests cover success, a failing status, a mismatched tree, and no status
- [x] 1.3 Missing or unauthenticated `gh` fails loud in both; `gates doctor` gains a `gh` row warning only under `integration.mode: pull-request`; tests

## 2. The loop's finish in pull-request mode

- [x] 2.1 The pull-request branch of `gates merge` per design D2; tests with a fake `gh` and a bare remote cover auto-merge, approval-required stop, and an unproven head
- [x] 2.2 `skills/tdd-apply/SKILL.md` 7.5 pull-request branches become `gates merge <change>`; `agents/merge-runner.md` treats a handed-off PR as success

## 3. Recording forge merges and readiness

- [x] 3.1 `gates record-merged <sha>` per design D3 (resolve PR head via `gh`, skip non-change/archived, record-merge, archive, one local commit, never push); tests with a fake `gh` cover a change PR, an ordinary PR, a follow-up PR branch, and a second run
- [x] 3.2 `gates ledger record-ready <change>` appends a `ready` row (design D4); `agents/tdd-implementer.md` records and commits it at ledger grade immediately before a READY report; test the row

## 4. Documentation

- [x] 4.1 Add `docs/running-at-scale.md` per design D5, headed as an example to adapt, using only shipped commands, with the sample workflow and the branch-protection settings
- [x] 4.2 SETUP.md: pull-request mode, `marker publish`/`check-remote`, `record-merged`, statuses from the CI source; README points at the scale example

## 5. This repository

- [x] 5.1 `.gates.yaml` `integration: { mode: pull-request, requireApproval: true }` and `.github/workflows/specloop.yml` adapted from the example (design D6); the final report lists the branch-protection settings for the maintainer

## 6. Close

- [x] 6.1 `gates run ci` green on the final tree; `openspec validate merge-pull-request --strict` passes
