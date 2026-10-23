# Design

## Context

`split-test-author` keeps held tests under `.specloop/authored/<change>/<N.M>/`:
- `*.authored` files, one per test path;
- or `NO-TESTS`, holding a reason, for a task that changes no behaviour.

`gates tests place <N.M>` moves a task's tests to their real paths and records a `tests-placed` row. `gates tests check`, which both commit hooks run, refuses a commit unless:
- every placed or held test is unchanged;
- a failing `unit` run for the task is recorded after placement.

`gates tests defect` records a `test-defect` row; `MAX_TEST_DEFECTS_PER_TASK = 2`, and a third defect is refused.

## Decisions

### D1. `CHARACTERIZATION` is a sibling of `NO-TESTS`

`.specloop/authored/<change>/<N.M>/CHARACTERIZATION` holds a one-paragraph reason, and the task also has its `*.authored` tests. Having both `CHARACTERIZATION` and `NO-TESTS` for one task is refused at handoff. The handoff row records the reason, in `characterization: {task: reason}`, beside `no_behaviour`. Only the authoring phase can write the file, and the holding area is locked like everything else in it, so the implementer can't add it later.

### D2. The run after placement must be green

For a characterization task, `tests check` requires a **green** `unit` run for the task recorded after its `tests-placed` row, instead of a red one. The message for a missing run says which one it needs. A red run there means the tests don't describe current behaviour, which is a defect of kind `assertion` or `setup`. The implementer records it, and the author revises.

Everything else is unchanged:
- the lock;
- the placement;
- review, which judges the claim with the test-quality rule;
- the task's own `ci` before commit.

Why green is enforced rather than merely allowed: a characterization test that has never been seen to pass on the base tree pins nothing.

### D3. Defect kinds

`gates tests defect <task> --kind {setup,assertion} --detail TEXT`. `--kind` is required, and the row gains `kind`.

| Kind | Means | Cap per task |
|---|---|---|
| `setup` | the test cannot run as written: a path, import, fixture or environment it assumes is wrong | 3 |
| `assertion` | the test runs, and asserts behaviour the spec doesn't require or contradicts | 2 |

What happens at the caps:
- **The `assertion` cap is today's rule.** Past it, the loop halts with cause `oracle-conflict`.
- **Past the `setup` cap,** it halts with cause `weak-spec`, because an author that can't write runnable tests three times is missing something from the brief, not disagreeing.

Rows written before this change have no `kind`, and count as `assertion`, the conservative reading.

**Mislabelling is visible.** `gates tests show` lists each defect with its kind and detail. `gates stats` reports per-change counts by kind. The authored-set review of a revision sees the defect it answers.

### D4. Who decides the kind

The implementer records the kind it observed:
- the test errored before asserting: `setup`;
- it asserted and the assertion is wrong: `assertion`.

The re-dispatched author may answer a `setup` defect with a fix only. To dispute that a defect was setup, the author defends the tests; the implementer then has to record an `assertion` defect, which counts.

### D5. Warm-up is `requires`, documented

There's no code change. SETUP's gate-contract section gains:
- a `requires` command may prepare the environment as well as probe it, as long as it's idempotent and exits 0 when ready;
- it runs before the gate's verdict, so it never retries a failure;
- a cold-lane warm-up for `confirm` or `live-check` belongs there.

`gates-init`'s `confirm` offer mentions it.

## Risks

- **Characterization as an escape hatch from red-first.** The authored-set review judges every declaration. A characterization task's own tests must pass on the base tree, so they can't smuggle in new behaviour: any test for new behaviour would fail there.
