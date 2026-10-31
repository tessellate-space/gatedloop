# Tasks

## 1. Unmatched paths err full (D1)

- [x] 1.1 Make `_select_scoped_gate` return the global gate when any changed path is matched by no non-catch-all surface, and announce `<gate>[full] — <path> matches no surface` with the first such path in sorted order. Verify with tests: a staged diff of one scoped surface's file plus an unmatched file runs the global `ci`; the same with a catch-all surface declared; the same for `unit` off the working set; a diff wholly in one scoped surface still runs the scoped command [oracle: unit]

## 2. A multi-surface unit runs the union (D2)

- [x] 2.1 For `gates run unit` with two or more non-catch-all hot surfaces and no unmatched path, run each hot surface's `unit` override in surface order and the global `unit` once when any hot surface declares none, deduping identical commands and appending the caller's extra arguments to each; check every precondition before running any; run all commands under one lock acquisition and exit with the first non-zero code. Verify with tests: two overrides both run; first green and second red exits non-zero and reports both; an override plus a surface without one runs the override and the global; two surfaces sharing one command run it once; a failing precondition runs nothing and returns the precondition-failed code [oracle: unit]
- [x] 2.2 Record and announce the union's scope as the run's surface names joined with `+`, `full` for the global component, in one ledger row. Verify with tests: the row's `scope` is `frontend+e2e`, the stderr line is `unit[frontend+e2e]`, the attempt budget counts the invocation once, and a `ci` multi-surface run still records `full` (D3) [oracle: unit]

## 3. Docs (D3, D4, D5)

- [x] 3.1 Update SETUP.md "Scoped `ci`/`unit`" (the unmatched-path rule with catch-alls, the `unit` union and its scope string, why `ci` keeps the global fallback) and the override description in `schema/gates.schema.json`. Verify that `scripts/release docs` reports no gap and `gates run ci` is green [oracle: none]

## Workflow follow-up

- Open the implementation PR with "Fixes #61, Fixes #45".
