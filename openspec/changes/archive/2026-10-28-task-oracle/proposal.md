# Proposal

## Why

Under `loop.test-author: separate`, the test author guesses each task's kind from the plan's prose: red-then-green, `CHARACTERIZATION` or `NO-TESTS`. It also cannot say which gate the tests run under, because the lock reads only `unit`. A wrong guess shows up only after code exists. In #56, tasks 3.1 and 5.1 were declared red-then-green. 3.1 verified data an earlier task had already written, and 5.1 was an e2e step file that `unit` never runs. 0.8.0 made such a guess recoverable (the `green` defect). This change lets the plan prevent it: the planner, who knows what each task is for, declares its oracle, and the shim holds the author and the lock to it. This is item 4 of #56, and the reporter already tags their own plans this way as a stopgap.

## What Changes

- **A per-task oracle tag in `tasks.md`.** A task line may end with `[oracle: <gate>]`, `[oracle: <gate> characterization]` or `[oracle: none]`.
  - `<gate>` is any gate declared in `.gates.yaml` except `ci`, `live-check`, `eval` and `confirm`, which cannot judge one task.
  - `characterization` means the task's tests must pass on their first run under that gate, rather than fail.
  - `none` means the task adds no tests.
  - A task with no tag behaves exactly as today.
- **`gates validate`** checks every tag in the active changes. It names an unknown gate, an excluded gate and a malformed tag.
- **The test author's brief** prints each task's declared oracle, so the author does not infer it.
- **The handoff refuses a declaration that contradicts the plan:**
  - tests, or a `CHARACTERIZATION` marker, for a `none` task;
  - `NO-TESTS` for a task tagged with a gate;
  - a missing `CHARACTERIZATION` marker on a task tagged `characterization`, or one added to a task the plan says goes red first.
- **The lock reads the declared gate.** A task tagged `[oracle: integration]` needs a red `integration` run after placement, not a red `unit` run. A `characterization` task needs its first verdict on that gate to be green. The attempt budget counts from the first red run on the declared gate.
- **`loop.task-oracle: required`** is optional, with `optional` as the default. When set, the handoff refuses a task with no tag. One adoption item offers it, together with a ready line for the adopter's own `openspec/config.yaml` `rules.tasks`, so that `/opsx:propose` writes the tags.
- **The loop prompts** (`tdd-apply`, `tdd-implementer`, `test-author`) run the red step on the declared gate and treat the tag as the contract. The 0.8.0 interim rule, "declare an e2e-only task `CHARACTERIZATION`", is retired.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: tasks may declare their oracle. The handoff, the brief and the lock honour the declaration, and a manifest key can require it.
- `retry-budget`: a task's red run is read on its declared gate.

## Impact

- `bin/gates`:
  - the task-line parser, which reads the tag and strips it from the task text;
  - `gates validate`;
  - the `tests brief`, `tests handoff` and `tests show` commands;
  - the lock evaluator, whose condition 3 reads the declared gate, and `_attempt_state`;
  - the `loop.task-oracle` key.
- `schema/gates.schema.json`: `loop.task-oracle`.
- `adoption/catalog.json`: the `task-oracle` item, `since: 0.9.0`.
- Prompts: `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md` and `agents/test-author.md`.
- Docs: SETUP.md (the tag, the key and the handoff refusals), AUTOMATION.md (what the lock reads) and `docs/status.md` (the sharp edge becomes shipped).
- This repo: a `rules.tasks` line in `docs/conventions.md`, so this repo's own plans carry tags. The repo does not set `required`, so in-flight plans are unaffected.
- Out of scope: lettered task ids such as `1.2a` (#46), which the task-line parser does not match today. A tag on such a line is not read until #46 is fixed, and `gates validate` says so.
- Rejection test: it authors no artifact, because OpenSpec still writes `tasks.md` and the tag reaches it through the adopter's own `rules.tasks`. It names no stack command, because the tag names an abstract gate. It makes a stated guarantee enforceable: the oracle is fixed before implementation, by the plan, and not chosen by the implementer.
