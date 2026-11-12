# Tasks

## 1. Release (D1–D3)

- [ ] 1.1 In `bin/gates` `_lock_problems`, record which tasks placed each path, compute `oracles` once before condition 1, drop from `expected` each voided path whose placing tasks are all `NO-TESTS` in the latest handoff and tagged `[oracle: none]` both on the merge target's `tasks.md` and in the evaluated tree, with no task's handoff holding it and never when the target's plan is unreadable, independent of `only` (D1), and append D3's missing-condition clause to the staged and `--ref` refusals. Verify with tests on real repositories for each test-discipline scenario on the staged, `--task` and `--ref` readers, and rewrite the pinned refusal text in `tests/test_tests_check_staged_output.py` to include the clause [oracle: unit rewrites: tests/test_tests_check_staged_output.py]
- [ ] 1.2 In `SETUP.md`'s authored-test lock section, add one sentence saying that a voided path is released when the approved plan moves every task that placed it to `[oracle: none]` with `NO-TESTS`. Verify that `scripts/release docs` reports no gap [oracle: none]
