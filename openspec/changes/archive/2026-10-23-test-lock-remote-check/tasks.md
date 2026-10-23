# Tasks

## 1. The evaluator at a ref

- [x] 1.1 Refactor the lock check into an evaluator over (path→blob map, ledger rows) per design D1, with the staged mode byte-identical in output; the existing `tests check` tests pass unchanged.
- [x] 1.2 `gates tests check --ref <commit> [--change]` per design D1 and D2; tests cover: an edited placed test at the ref, a clean head listing verified tasks, no handoff ("no authored tests"), a voided placement holding base content, a later task replacing an earlier placement, and a missing red run after placement.

## 2. The merge and the status

- [x] 2.1 `_merge_prove_head` adds the lock evaluation on `refs/heads/<change>` per design D3, both modes; tests cover a broken lock refusing before push/squash and a clean lock passing.
- [x] 2.2 `gates marker publish tests` and `check-remote tests` per design D4 (success with tree, failure with path, non-zero exit, "no authored tests" success); tests through the existing fake-forge harness.

## 3. CI, example and docs

- [x] 3.1 `.github/workflows/gatedloop.yml` publishes `tests` after `ci` on pull requests; `docs/running-at-scale.md` workflow example gains the same step; verify the workflow file parses and the docs step matches the real command.
- [x] 3.2 Docs: SETUP (`tests check --ref`, the `tests` status, the two-step adoption); AUTOMATION (the lock holds at commit, merge and forge; protection list gains `tests`); README (`test-author` row says the lock is verified at the merge and the forge). `python3 scripts/release docs` exits 0.

## 4. Close

- [x] 4.1 `gates run ci` green on the final tree; `openspec validate test-lock-remote-check --strict` passes.
