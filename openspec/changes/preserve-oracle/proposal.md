# Proposal: preserve-oracle

## Why

The test lock protects only the tests the test author placed for a change. A task tagged `[oracle: none]`, or any task with no placed tests, can modify, delete or rename an existing test file, and no gate notices. That gap matters most for a behaviour-preserving refactor. A pure refactor has no red-first test: its oracle is "the existing suite stays green **and no existing test changed**". Today only the first half is checked, so an implementer can make a refactor green by editing the tests that would have caught a behaviour change. An adopter found this while designing a refactor fast track and enforces the second half with its own merge-time check in the meantime (issue #217).

Rejection test: this makes a stated guarantee enforceable. "This task preserves behaviour" becomes a checked claim: no test path changes, and the declared gate is green on the task's own tree. It authors no artifact and names no stack command. The gate is the adopter's, through the tag.

## What Changes

- **A new oracle modifier: `[oracle: <gate> preserve]`.** `<gate>` follows the same rules as any oracle gate (declared, and not `ci`, `live-check`, `eval` or `confirm`). `preserve` cannot be combined with `characterization` or with a `rewrites:` clause, and `gates validate` reports either combination as a malformed tag. The approval sha and the tag-drift check cover the modifier, as they cover every tag. A plan without it hashes exactly as before.
- **The test author places nothing for a preserve task.** It holds the task's `NO-TESTS` reason, as for `none`. The handoff refuses tests or `CHARACTERIZATION` for a preserve task, and accepts its `NO-TESTS`.
- **The lock refuses any change to a test path during a preserve task.** At the commit, every test path the task changed is refused, judged from the task's commits and the staged tree, with what a sync merge takes from the target left out. That covers a modified, deleted, renamed or added path. Characterization tests that guard the refactor go in an earlier `[oracle: <gate> characterization]` task, authored and locked as usual.
- **The lock requires a green run of the declared gate on the task's tree.** The task's commit needs a passing `gates run <gate> --task <N.M>` recorded after its `task-start`, on the same tree as the staged commit, with the ledger ignored.
- **The same check runs at any commit.** `gates tests check --ref` checks both conditions at the commit that ticks each preserve task, and derives both from commits only, so it works in a fresh clone. There, the green run is matched by gate and task, as the existing red-run checks are. Matching it by tree is follow-up issue #231.
- **What counts as a test path is reused, not configured.** A path counts when the brief's existing heuristic classes it as a test, or this change's ledger placed or handed it off, or it matches the manifest's existing `acceptance.match`, which is read only for a plan with a preserve task. Paths under `.gatedloop/` and `openspec/` never count. There is no new manifest key.
- **`gates validate` warns** when a preserve task's text names a path that counts as a test path, because the lock would refuse that task's own edit.
- **The prompts learn the tag.** These are the test author, the tdd-apply skill, the tdd-implementer agent and the plan lenses.
- **An adoption item** offers adopters with `loop.task-oracle` the preserve clause alone, with notes for their own tag-parsing tooling and on restarting every session on 0.14.0 before tagging. The `test-rewrites` item keeps printing only its own clause.

Opt-in by construction: a task changes behaviour only when its plan carries the tag.

## Capabilities

### Modified Capabilities

- `test-discipline`: the tag's grammar, the handoff's refusal, the brief's line, the lock's two new conditions and their `--ref` form.

## Impact

- `bin/gates`:
  - the tag parser and `_oracle_label`;
  - `_oracle_brief_line`;
  - `_oracle_handoff_problems`;
  - `_tests_place`'s message for a preserve task;
  - `_lock_problems` and the completion walk, which exposes the commit that ticks each task;
  - `_task_oracle_problems`, for the new warning;
  - a test-path predicate built on `_is_test_path`.
- `agents/test-author.md`, `agents/tdd-implementer.md`, `skills/tdd-apply/SKILL.md` and `rules/plan-lenses.md`.
- `docs/conventions.md` `### task-oracle-tags` and `templates/rules-doc.template.md`, with `openspec/config.yaml` regenerated. `adoption/catalog.json` gains a `preserve-oracle` item.
- `README.md`, `SETUP.md`, `AUTOMATION.md`, `docs/stability.md` (the tag syntax), `schema/gates.schema.json` (the `loop.task-oracle` description) and `docs/candidates.md` (a test-path manifest key, deferred).
- `tests/`: new modules. No subcommand, flag or ledger field changes, so `tests/contract.json` is unchanged.
