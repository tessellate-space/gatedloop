## 1. Reproduce and pin the defect

- [x] 1.1 Add the F1 reproduction as a failing test first: a scratch repo with a
  catch-all surface whose live-check is `false`, everything committed on a branch
  cut from the default branch — `gates run live-check` must exit non-zero once
  fixed, and the test must fail red against current `bin/gates`
- [x] 1.2 Add a test fixture helper that builds throwaway git repos (init, config
  identity locally, commit, branch) so selection tests do not depend on the host's
  git config

## 2. Two baselines by gate level

- [x] 2.1 Implement merge-target resolution (design D2): `origin/HEAD` → local
  `main` → local `master`; return None with a reason when nothing resolves
- [x] 2.2 Implement the change-level changed-set: merge-base diff against the
  target ∪ working set; keep the existing working-set function for task-level
  callers untouched
- [x] 2.3 Route `cmd_run` live-check through the change-level set; leave
  `cmd_rules`/`cmd_surfaces` on the working set; `--changed`/`--all` override both
- [x] 2.4 Loud fallback (design D2): no target or no merge base → working-set
  baseline + stderr notice naming the reason; on-target-branch case produces no
  warning
- [x] 2.5 Tests: clean-tree-on-branch (the pinned F1 repro goes green), dirty-tree
  union, on-target-branch, no-remote-no-main fallback, `--changed`/`--all`
  overrides, and a non-`main` default branch (e.g. `trunk` via `origin/HEAD`)

## 3. Loud empty hot set at change level

- [x] 3.1 When change-level selection is empty, print baseline kind, resolved
  target, and files-considered count; exit 0 (design D3)
- [x] 3.2 Test: docs-only change against code-only surfaces asserts the evidence
  appears and the exit code is 0

## 4. Heading-anchored rule-id resolution

- [x] 4.1 Resolve rule-ids in `_errors` against `### <id>` heading ids (reuse the
  conventions parser, relaxed to headings without sync metadata); delete the
  substring check
- [x] 4.2 Tests: dangling id mentioned only in prose fails validate; heading
  without `Applies to:`/`Rule:` metadata resolves; existing manifests
  (`.gates.yaml` of this repo) still validate

## 5. Pin the glob contract

- [x] 5.1 Document fail-hot matching in `SETUP.md`'s surfaces section (design D5):
  over-selection is the contract, under-selection is a defect
- [x] 5.2 Test pinning the direction: for the known `**`→`*` approximations,
  assert selection is a superset of the exact reading, so a future matcher change
  cannot silently under-match

## 6. Close out

- [x] 6.1 Run the full suite and `gates validate`; confirm `gates run ci` green
- [x] 6.2 Confirm no prompt changed: `git diff --name-only` touches only `bin/`,
  `tests/`, `SETUP.md`, and this change's artifacts
- [x] 6.3 Update `docs/review-2026-08-18.md` F1–F4 dispositions to "landed" with
  the change name
- [x] 6.4 Note in the release notes that previously-vacuous live-checks will now
  actually run (proposal Impact: recovered coverage, not regression)
