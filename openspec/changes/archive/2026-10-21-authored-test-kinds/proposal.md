# Proposal

## Why

Issue #42 reports three frictions from a long-running orchestrator. Two are gaps in the authored-tests contract (`split-test-author`); the third is already supported and needs only docs.

1. **No place for tests that must pass on the current tree.** The contract enforces a red run after placement, which is right for new behaviour. A task whose tests all pin *existing* behaviour can never go red, so it fails the contract. A refactor guarded by characterization tests, or a guard for output the task must not change, is that kind of task. In the field, one change was re-planned to merge tasks, and a regression guard was deleted.

   A task that mixes new red tests with such guards already works: the red run fails on the new ones. The red check runs the whole `unit` gate and, being stack-agnostic, can't single out tests. So the gap is exactly the task whose tests are *all* characterization.
2. **Fixture mistakes use up the test-defect cap.** A task gets two defects, then halts. In practice most defects are setup errors in the authored tests, such as a wrong path or a stale fixture, not disagreements about behaviour, so the cap is spent before the real question comes up. The orchestrator now pre-runs held tests from a scratch copy to dodge the cap.
3. **A cold-lane e2e flake on the `confirm` gate** (about 1 in 69 in a fresh stack). The runner-strictness rules correctly refuse a retry to green, and the contract seemed to have no place for a warm-up. It does: every gate's `requires` precondition runs before the gate, and an idempotent warm-up that exits 0 once the stack is warm fits there. That differs from a retry, because it runs before the verdict, never after a failure. Docs only.

## What Changes

- **Characterization tasks.** The author may declare a task `characterization` with a reason, by writing a `CHARACTERIZATION` file beside its held tests, as `NO-TESTS` is written today. For that task:
  - the run after placement must be **green**, which proves the tests pin current behaviour;
  - a red run there is a defect;
  - the tests are placed and locked like any authored test;
  - the authored-set review judges the claim;
  - the implementer can't make the declaration.
- **Defect kinds, each with its own cap.** `gates tests defect <task> --kind setup|assertion --detail …`:
  - `setup`: the test cannot run as written (path, import, fixture);
  - `assertion`: it asserts the wrong behaviour.

  The caps are `assertion` 2 (today's rule) and `setup` 3, counted separately. A defect recorded without `--kind` is refused, because the kind is the point. `gates tests show` and `gates stats` report both counts, so a mislabelled defect is visible.
- **Docs.**
  - **Warm-up.** SETUP's gate-contract section documents a warm-up as a gate's `requires` and how it differs from a retry. `gates-init`'s `confirm` offer mentions it.
  - **Mixed tasks.** The test-author agent's brief explains when a task needs `characterization`, and that mixed tasks need nothing.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: the characterization declaration, and defect kinds with separate caps.

## Impact

- `bin/gates`:
  - the `CHARACTERIZATION` file in the holding area;
  - the placement red-or-green check in `tests check`;
  - `tests defect --kind` and the caps;
  - `tests show` and `stats`.
- `agents/test-author.md`, `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md`: when to declare, and which kind to record.
- `SETUP.md`, `commands/gates-init.md`.
- Tests.
