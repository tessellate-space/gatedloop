# Spec Delta

## Purpose

Check a plan against the code and against the shim's own handoff refusals before a person approves it, so that what the test author would find after approval reaches the planner first, while nothing is recorded, nothing enters the tree, and no approval or merge guarantee changes.

## ADDED Requirements

### Requirement: Preflight tests are held outside the tree

A preflight's authored tests SHALL be held in `.gatedloop/out/preflight/<change>/`, with the real holding area's layout, and git SHALL ignore that directory. `gates tests brief <change> --preflight` SHALL create it, ensure that `.gatedloop/out/` ignores itself, and print it as the place to write. Log rotation SHALL NOT remove it.

#### Scenario: The preflight brief

- **WHEN** `gates tests brief <change> --preflight` runs in a repository that has no `.gatedloop/out/`
- **THEN** it prints `.gatedloop/out/preflight/<change>/` as the holding area, and a file written there does not appear in `git status`

### Requirement: A preflight never touches the real holding area

No preflight command SHALL read or write `.gatedloop/authored/<change>/`. A real `gates tests handoff`, without `--dry-run`, SHALL keep reading only that directory.

#### Scenario: The real holding area is untouched

- **WHEN** a preflight authors, dry-runs and is discarded
- **THEN** `.gatedloop/authored/<change>/` does not exist and was never created

### Requirement: A dry-run handoff runs the handoff's refusals and writes nothing

`gates tests handoff <change> --dry-run` SHALL read the preflight holding area and run the same checks as a real handoff, including under `--task <N.M>`, with the same messages and exit status. It SHALL write no ledger row and no git object. It SHALL NOT require the change to be approved. On success it SHALL print what a real handoff would record and that nothing was recorded.

#### Scenario: A holding area that contradicts a tag

- **WHEN** a task is tagged `[oracle: unit]`, its preflight directory holds `CHARACTERIZATION`, and `gates tests handoff <change> --dry-run` runs
- **THEN** it exits 1 with the same message a real handoff prints for that contradiction, and the change's ledger is unchanged

#### Scenario: A clean preflight on an unapproved plan

- **WHEN** the change carries no approval and its preflight holding area satisfies every refusal
- **THEN** `--dry-run` exits 0, says nothing was recorded, and no ledger file exists for the change

### Requirement: A dry run does not compare tags with the target

`gates tests handoff --dry-run` SHALL NOT compare the tasks' oracle tags with the merge target's `tasks.md`, and SHALL print a line saying that it skipped the comparison. A real handoff SHALL keep the comparison.

#### Scenario: An amended plan whose tags differ from the target

- **WHEN** the plan branch retags a task that the merge target's `tasks.md` tags differently
- **THEN** `--dry-run` does not refuse over the difference, and a real handoff of the same tests from the real holding area still does

### Requirement: The preflight's authored set can be shown without a handoff

`gates tests show <change> --preflight` SHALL report the preflight holding area in the shapes `gates tests show` uses, text and `--json`: each task's declared oracle, its held paths, its reasons and its declared rewrites. Each rewrite's counts, and its diff with `--diff`, SHALL be taken against the path at `HEAD`. It SHALL read no ledger row and write nothing.

#### Scenario: Reviewing a preflight's tests

- **WHEN** the preflight holding area holds tests for tasks 1.1 and 2.1 and no handoff is recorded
- **THEN** `gates tests show <change> --preflight` lists both tasks with their paths, where `gates tests show <change>` says no handoff is recorded

#### Scenario: A held rewrite's diff

- **WHEN** task 2.1 declares `rewrites: tests/a_test.py` and its preflight directory holds the full file
- **THEN** `gates tests show <change> --preflight --diff` prints that file's unified diff against its content at `HEAD`

### Requirement: Plan checks fail loud and write nothing

`gates plan check <change>` SHALL exit 1 when it has any finding, naming each finding's task and path, and SHALL otherwise exit 0 and say the plan is clean. It SHALL write nothing. An unknown change SHALL exit 1. With `--json` it SHALL print `{change, preflight, against, findings: [{kind, task, path, detail}]}`, where `preflight` is the effective `loop.plan-preflight`.

#### Scenario: A clean plan

- **WHEN** every tag is well formed and every declared rewrite exists at the base
- **THEN** `gates plan check` exits 0 and writes no file

#### Scenario: An unknown change

- **WHEN** `gates plan check missing` runs and no such change exists
- **THEN** it exits 1 and says so

### Requirement: Plan checks report what the handoff would refuse

`gates plan check` SHALL report this change's oracle-tag errors and warnings as `gates validate` words them, and, under `loop.task-oracle: required`, every untagged task.

#### Scenario: Untagged tasks under a required oracle

- **WHEN** the manifest declares `loop.task-oracle: required` and task 3.2 carries no tag
- **THEN** `gates plan check` exits 1 naming task 3.2

### Requirement: Plan checks report a rewrite of a file absent at the base

`gates plan check` SHALL report each `rewrites:` path absent at the base: `HEAD`, or `<ref>` with `--against <ref>`. When an earlier task's line of the same change names the path, the finding SHALL say that the earlier task creates the file, so the later task holds the full file without the clause.

#### Scenario: A rewrite of a file an earlier task creates

- **WHEN** task 1.1's line names `` `tests/new_test.py` ``, the file does not exist at `HEAD`, and task 2.1 is tagged `[oracle: unit rewrites: tests/new_test.py]`
- **THEN** `gates plan check` exits 1 with a finding for task 2.1 saying that task 1.1 creates the file

### Requirement: The drift check names what the plan names that moved

With `--against <ref>`, `gates plan check` SHALL report each path the plan names (in task lines, `rewrites:` clauses, or backticked in `design.md`, excluding the change's own directory) that was modified, deleted or renamed between the plan's base commit and `<ref>`. The base commit SHALL be the latest commit in `<ref>`'s history that touches the change's directory when `<ref>` holds the change, and `git merge-base HEAD <ref>` otherwise. An unresolvable `<ref>` SHALL exit 1.

#### Scenario: A named file changed while the plan waited

- **WHEN** the approved plan's design names `` `bin/tool.py` `` and a later commit on the target modifies it
- **THEN** `gates plan check <change> --against <target>` exits 1 naming `bin/tool.py` as modified since the plan's base

#### Scenario: Nothing named moved

- **WHEN** commits land on the target that touch no path the plan names
- **THEN** `--against` adds no finding

### Requirement: The plan preflight is opt-in

The manifest key `loop.plan-preflight` SHALL accept `run` or `skip`, and SHALL default to `skip` when absent. `gates validate` SHALL refuse any other value, and SHALL refuse `run` together with `loop.test-author: inline`, naming both keys.

#### Scenario: A boolean-looking value

- **WHEN** `.gates.yaml` declares `loop.plan-preflight: on`
- **THEN** `gates validate` exits 1 naming the key and the accepted values `run` and `skip`

#### Scenario: Preflight with an inline author

- **WHEN** the manifest declares `loop.plan-preflight: run` and `loop.test-author: inline`
- **THEN** `gates validate` exits 1 naming both keys

### Requirement: The propose path always runs the plan check

`/gatedloop:propose` SHALL run `gates plan check <change>` before it commits the plan, whatever `loop.plan-preflight` says, and SHALL return its findings to the planner to amend.

#### Scenario: The preflight is off

- **WHEN** `loop.plan-preflight` is absent
- **THEN** the propose command runs `gates plan check` and dispatches no test author

### Requirement: Under run, the propose path runs the preflight before the plan PR opens or updates

Under `loop.plan-preflight: run`, `/gatedloop:propose` SHALL, before committing: dispatch the test author in preflight mode, run `gates tests handoff <change> --dry-run`, run the authored-set review over `gates tests show <change> --preflight`, then delete the preflight holding area. It SHALL return every finding to the planner, record no ledger row, and state the outcome in one line of the PR body.

#### Scenario: A preflight finding before approval

- **WHEN** the preflight author returns `blocked: weak-spec` because task 1.3 needs a schema that task 5.1 adds
- **THEN** the propose command reports the question to the planner before the plan PR opens, and no ledger row exists for the change

### Requirement: The test author's preflight mode records nothing

In preflight mode the test author SHALL write only to the area that `gates tests brief --preflight` prints, SHALL end with `gates tests handoff --dry-run`, and SHALL never run a real handoff. It SHALL return, as `blocked: weak-spec`, a task whose tests need what only a later task provides (naming both tasks) and a red-first task whose tests can only pass.

#### Scenario: A task-order deadlock

- **WHEN** task 1.3's tests need an artifact that only task 5.1 creates
- **THEN** the preflight author returns `blocked: weak-spec` naming tasks 1.3 and 5.1, and runs no real handoff

### Requirement: Held tests are never committed off a change branch

`gates tests check`, which both commit hooks run, SHALL refuse a staged path under `.gatedloop/authored/` whenever the current branch resolves to no active change: a `plan/*` branch, the merge target, or any other such branch. The refusal SHALL name each path. On a branch that names an active change, the verdict SHALL be unchanged.

#### Scenario: A held test staged on a plan branch

- **WHEN** on `plan/x`, `.gatedloop/authored/x/1.1/tests/a_test.py.authored` is staged with the plan
- **THEN** `gates tests check` exits 1 naming that path, and both the tool hook and the git-layer `pre-commit` hook deny the commit

#### Scenario: A held test staged on the merge target

- **WHEN** on `main`, a path under `.gatedloop/authored/` is staged
- **THEN** `gates tests check` exits 1 naming it

#### Scenario: The authoring commit on a change branch

- **WHEN** on the change branch `x`, the holding area is staged for the authoring commit
- **THEN** `gates tests check` gives the verdict it gives today
