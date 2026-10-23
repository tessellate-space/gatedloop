# fix-normalize-tree-checkout-dependence — Tasks

## 1. Regression test first (design D3, issue #21)

- [x] 1.1 Add `test_same_tree_normalizes_identically_from_any_checkout` to `tests/test_marker_normalization.py`: build the #21 scenario (`main` with `a.txt` + `.specloop/runs/other-change.jsonl`; `plan/x` adds `b.txt` and appends a ledger row; `main` then rewrites the same ledger), normalize the branch head tree once from each checkout, compute the ground-truth stripped tree with an independent scratch-index `read-tree` → `rm --cached -r -f -q --ignore-unmatch .specloop/runs` → `write-tree`, and assert all three hashes are equal with a failure message naming the checkout dependence; also assert the real index tree and working tree are unchanged by both normalizations; verify the test FAILS on the unmodified shim (step 5 returns the unstripped branch tree).
- [x] 1.2 Add `test_strip_failure_is_reported_on_stderr`: make the `git rm` step exit non-zero (a `git` wrapper script placed first on `PATH` for the subprocess env, or a monkeypatched `subprocess.run` that fails only the `rm` call), and assert `_normalize_tree` returns the input tree unchanged and stderr carries one line containing `ledger normalization failed`; verify it FAILS on the unmodified shim (no stderr output).

## 2. Fix `_normalize_tree` (design D1, D2)

- [x] 2.1 In `bin/gates` `_normalize_tree`, add `-f` to the scratch-index `git rm --cached -r --ignore-unmatch .specloop/runs` call and return `tree` when its exit status is non-zero; verify 1.1 passes and the existing six `TestNormalizeTree`/wiring cases plus `tests/test_marker_tree_keyed.py` and `tests/test_ledger_grade_commit.py` still pass.
- [x] 2.2 On any non-zero exit from `read-tree`, `rm`, or `write-tree`, print one stderr line `specloop: ledger normalization failed (<step>): <first line of git stderr>; comparing the unnormalized tree` before returning `tree` (exit codes and return contract unchanged); verify 1.2 passes and a normal green `gates run ci` in a throwaway repo prints nothing extra.
- [x] 2.3 Update the `_normalize_tree` docstring to state the pure-function property (checkout-independent; `-f` is safe because the scratch index protects nothing) and the reported-failure contract; verify docstring and behavior agree by reading the diff.

## 3. Closure

- [x] 3.1 Run `python3 -m unittest discover -s tests` and `./bin/gates validate`; verify green.
- [x] 3.2 End-to-end in a throwaway repo with a manifest binding `ci: "true"` and a surface with `live-check: "true"`: on `plan/x` diverge a ledger from `main`, run `gates run live-check` on the head, switch to `main`, and confirm `gates gate-marker check live-check <plan/x^{tree}>` passes on the first attempt (spec scenario "A live-check marker written on the head satisfies the merge gate from main"); verify the same check denies before 2.1 is applied.
