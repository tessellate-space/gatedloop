# Proposal: split-test-author

## Why

`test-quality-rule` gives review the words for a low-value test and makes the RED step
ask the right questions. Neither removes the cause #34 identifies. **One agent writes
the tests from the implementation it is about to write, or just wrote.** For that
agent, the easiest red is a default, a mock call or a substring of its own text, and a
review applied afterwards can only catch some of them.

#34 piloted the fix on one change: 5 tasks and 49 test cases. A test author saw only
the spec scenarios and the public interfaces. The implementer made those tests green
and was not allowed to edit them. Results:

| | Keep | Waste |
|---|---|---|
| Author-written | 94% | 6% (parametrisation only) |
| Loop baseline | 69% | 31% |

The split cost 2 bounces in 5 tasks, and both were caught before any code was committed
against a wrong test. The implementer edited no test file. Working blind, the author
also raised 7 questions the design had never answered.

The split only works if "the implementer may not edit a test" holds. A sentence in a
prompt doesn't make that hold, as `harden-unattended-loop` established for every
other guarantee. So this change makes it a checked fact.

## What Changes

- **An authoring phase, once per change, before the first task.** This is the review
  decision: all tests in one go. A `test-author` agent writes every task's failing
  tests from `tasks.md`, the spec scenarios, the design and the public interfaces. It
  never reads function bodies or the contents of existing tests.
  - It returns each test with the regression that makes it fail.
  - It marks tasks that change no behaviour, such as docs or config, with a reason.
  - It returns every blocking plan question together, with cause `weak-spec`, before
    any code exists.
- **The author runs on Sonnet, working from the project's conventions.** The shim
  generates `gates tests brief <change>`, which lists:
  - the project's `Applies to: tests` rules;
  - the rules for each task's surface;
  - the built-in rule;
  - the command the `unit` gate is bound to;
  - the paths of nearby existing tests, as paths only;
  - the shared fixtures and helpers.

  A project rule outranks a built-in item. Onboarding gains a test-conventions
  capture.
- **The authored set is reviewed before implementation.** One review runs over the
  whole set against the test-quality rule and the project's test rules. Findings go
  back to the author.
- **The tests are held, then placed.** They are committed as
  `.specloop/authored/<change>/<N.M>/<path>.authored`. No test runner discovers those
  names, so `ci` stays green while they sit in the tree. At the start of each task,
  `gates tests place N.M` moves that task's tests into their real paths.
- **Locked, and red enforced.** `gates tests check` runs in both commit hooks, next to
  the `ci` marker check. A commit is refused when:
  - a placed test differs from what was handed off;
  - a held test was edited;
  - no failing `unit` run was recorded after placement.

  That last condition turns red-before-green from an instruction into a checked fact.
- **A wrong test goes back to its author.** The implementer records
  `gates tests defect`. Whoever dispatched the implementer re-dispatches the author:
  - the top-level loop does it directly;
  - a lane halts with `oracle-conflict` and the defect as detail.

  Tests that pass before implementation count as a defect. A third defect on one task
  goes to a human.
- **Fits any orchestration.** The authoring phase is dispatched by whoever dispatches
  implementation: the interactive or headless session, a session spawning
  `tdd-implementer`, or #37's orchestrator per change. It is always a sibling of the
  implementer, so no subagent has to dispatch another. Under `separate`, an
  implementer with no authored tests halts with `missing-oracle` rather than silently
  writing its own.
- **Opt-out.** `loop.test-author: inline` makes the implementer run the authoring
  phase itself, bound by the same lock.
- **The regression-first route uses the author too,** to write the repro test from
  `report.md`.
- **Visible in outcomes.** `gates stats --outcomes` reports each change's authorship
  (`separate`, `inline`, `mixed` or `none`) and its number of test defects.

## Capabilities

### Modified Capabilities

- `test-discipline` (introduced by `test-quality-rule`): tests are authored before
  and apart from implementation. They are held, placed per task, and locked, and red
  runs are enforced.
- `gate-economics`: the outcomes view reports test authorship and defects.

## Impact

- New `agents/test-author.md`.
- `bin/gates`:
  - `tests brief`, `tests handoff`, `tests place`, `tests check`, `tests defect` and
    `tests show`;
  - new ledger events and fields;
  - `loop.test-author`;
  - `Applies to: tests`;
  - `review record --scope authored`;
  - the outcomes fields.
- Hooks: `hooks/gate-commit.sh` and `templates/git-hooks/pre-commit` call
  `gates tests check`. `hooks/_session_brief.py` offers "dispatch test-author, then
  the implementer".
- Prompts:
  - `skills/tdd-apply/SKILL.md`: the authoring phase, the per-task placement, defects,
    and the regression-first route;
  - `agents/tdd-implementer.md`;
  - `agents/convention-review.md`: the authored-set mode;
  - `commands/gates-init.md`;
  - `templates/rules-doc.template.md`.
- Docs: SETUP.md, AUTOMATION.md and the README.
- Cost: one author dispatch and one review per change, plus one dispatch per defect.
- Depends on `test-quality-rule`, which merges and archives first. The adoption item
  `loop.test-author` in `adoption-prompts` asks existing projects about it. This ships
  in 0.5.0.
