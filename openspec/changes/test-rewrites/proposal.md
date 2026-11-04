# Proposal

## Why

The test author may never read an existing test, and the implementer may never edit an authored test. That is right for new behaviour. It leaves no route for a task whose job is to change a test that already exists: one whose subject legitimately changed, or one that pins an assertion the change removes. #157 reports it from an adopter's field use under 0.11.0. Eight of nine changes in three UI plans deliberately change behaviour that existing tests pin (a moved key, a new toolbar). With no route to update those tests, each change halts at its first red `ci`, and nothing inside the loop is allowed to fix it. The workaround is to keep the old behaviour alive beside the new, which a moved key cannot do.

The shim already carries most of the route. `gates tests handoff` records each handed-off path's content before the change as its base, and `gates tests place` overwrites an existing file with the author's copy. What is missing is a declaration in the approved plan, the author's sight of the file it rewrites, and a review that can see what the rewrite dropped.

## What Changes

- **A task's oracle tag may name the existing tests it rewrites.** `[oracle: unit rewrites: tests/a.test.ts]`, or several paths separated by commas. The clause follows the gate and any `characterization`. It is part of the tag, so the approval sha and the tag-drift check already cover it. `[oracle: none]` cannot carry it, because a task that rewrites a test has a test.
- **`gates validate`** fails on a malformed clause: an absolute path, a `..` segment, a path inside gatedloop's state directory, a duplicate, or a `rewrites:` on a `none` tag. It warns when a declared path does not exist in the working tree.
- **The brief prints each declared file's current content** under its task, read from `HEAD`. The test author may read exactly that copy. Every other existing test stays unreadable.
- **The handoff refuses a declared rewrite that is not handed off** as a full file at that path under that task, and a declared path that does not exist at `HEAD`. The base is recorded as today. A handoff that overwrites an existing path without a declaration behaves exactly as today.
- **Once placed, a rewritten file is the task's authored test.** The same lock, the same red-first run (or green first under `characterization`), the same defects. The implementer never edits it.
- **The review can see what a rewrite dropped.** `gates tests show` lists each rewrite with a diffstat against its base, and `gates tests show --diff` prints the unified diff. The authored-set review reads that diff.
- **The loop prompts** state the rule where they state the boundary today: `agents/test-author.md`, `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md` and `agents/convention-review.md`. The ready `rules.tasks` line tells a planner when to declare `rewrites:`.
- **One adoption item**, `test-rewrites` (`since: 0.12.0`), offers the amended `rules.tasks` line to projects that already declare `loop.task-oracle`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-discipline`: a task's oracle tag may declare the existing tests it rewrites. The author may read those files and no others, the handoff must carry them, the lock holds them as the task's authored tests, and review sees each one's diff against its base.

## Impact

- `bin/gates`:
  - the tag parser and the canonical tag label (the approval digest and the drift check read it);
  - `gates validate`;
  - `gates tests brief`, `gates tests handoff` and `gates tests show` (with a `--diff` flag).
- `adoption/catalog.json`: the `test-rewrites` item.
- Prompts: `agents/test-author.md`, `skills/tdd-apply/SKILL.md`, `agents/tdd-implementer.md` and `agents/convention-review.md`.
- Docs: SETUP.md (the clause, the refusals, `--diff`), README.md (the test-author row), AUTOMATION.md (what the lock holds), `docs/stability.md` (the tag syntax is a covered surface), `templates/rules-doc.template.md`, this repo's `docs/conventions.md` `### task-oracle-tags` rule, and `docs/candidates.md` (two deferred items).
- `tests/contract.json`: the new flag.
- Compatibility: a plan with no `rewrites:` clause hashes exactly as before, so no approval in flight is voided. An older shim reads a tag with the clause as malformed and fails `gates validate`. It never ignores the clause silently.
- Ships in 0.12.0, a minor release: the tag grammar grows, and no existing input changes meaning.
- Out of scope: refusing an undeclared overwrite of an existing test (a new adopter-facing refusal, so it would have to be opt-in; recorded as a candidate). A `removes:` clause for deleting a test whose subject is gone (design D1).
- Rejection test: it authors no artifact, because OpenSpec still writes `tasks.md` and the clause reaches it through the adopter's own `rules.tasks`. It names no stack command, because the clause names paths and the oracle stays an abstract gate. It makes a stated guarantee enforceable without blocking legitimate work: today an existing test that a change must update is either rewritten blind or not at all, and afterwards it is rewritten in sight, under the approved plan, and locked like any authored test.
