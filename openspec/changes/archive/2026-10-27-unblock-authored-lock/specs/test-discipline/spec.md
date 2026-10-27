# Spec Delta

## MODIFIED Requirements

### Requirement: Authored tests are held undiscoverable, placed per task, and locked

Authored tests SHALL be committed in a holding area whose file names no test runner
discovers. `gates tests place <task>` SHALL move a task's tests onto their real paths
at the start of that task. It SHALL refuse when a real path has changed since
authoring other than by an earlier placement. `gates tests check` SHALL fail unless:

- every placed path is staged with exactly its handed-off content;
- every unplaced holding file matches the handoff;
- for a task with tests, a `unit` run recorded after placement failed for a reason
  other than a precondition. For a task reopened after completion, a red run recorded
  after its first placement satisfies this condition.

The commit gates SHALL run that check wherever they check the `ci` marker.

#### Scenario: The authoring commit

- **WHEN** the authored set is committed before the first task
- **THEN** the `ci` gate is unaffected by the held tests, and the commit is allowed

#### Scenario: The implementer edits a placed test

- **WHEN** a commit is attempted whose staged content changes a placed test
- **THEN** the commit is denied, naming the path and directing the implementer to
  record a test defect

#### Scenario: The implementer skips the red run

- **WHEN** a task commit is attempted with no failing `unit` run recorded after that
  task's tests were placed
- **THEN** the commit is denied, because red before green is required

#### Scenario: Two tasks extend one test file

- **WHEN** a later task's authored copy of a test file already placed by an earlier
  task is placed
- **THEN** it replaces the earlier content, and the lock applies to the new content

#### Scenario: A held test is edited by hand

- **WHEN** a holding-area file differs from the latest handoff at commit time
- **THEN** the commit is denied until the change goes through a re-handoff

#### Scenario: The commit bypasses the tool hook

- **WHEN** a commit is created by a path the tool-level hook does not see
- **THEN** the git-layer commit hook applies the same check

### Requirement: A wrong test goes back to its author, and a persistent disagreement halts

The implementer SHALL NOT correct an authored test. It SHALL record `gates tests defect
<task> --kind setup|assertion|green --detail <why>`, and the author SHALL be
re-dispatched for the task. `green` records that the placed tests passed before any
implementation, without claiming they are wrong. A task SHALL take at most two
`assertion` defects, then halt with cause `oracle-conflict`, at most three `setup`
defects, then halt with cause `weak-spec`, and at most one `green` defect, then halt
with cause `oracle-conflict`. A defect without a kind SHALL be refused.

#### Scenario: The implementer finds a defective test

- **WHEN** the implementer judges a placed test wrong
- **THEN** it records a test defect with its kind and reason, the author revises or
  defends that task's tests, and implementation resumes against the new handoff

#### Scenario: Placed tests are already green

- **WHEN** a task's placed tests pass on their first run and the task is not
  declared `characterization`
- **THEN** the implementer records a `green` defect instead of implementing against
  them, and the author either re-declares the task or rewrites its tests

#### Scenario: Fixture mistakes do not spend the behaviour cap

- **WHEN** a task has two `setup` defects and no `assertion` defect
- **THEN** a first `assertion` defect is still accepted

#### Scenario: A green defect spends neither other cap

- **WHEN** a task has one `green` defect and no other defect
- **THEN** a first `setup` and a first `assertion` defect are still accepted

#### Scenario: Tests still green after the author's answer

- **WHEN** a task already has one `green` defect and its re-placed tests pass on their
  first run again, with no declaration
- **THEN** a second `green` defect is refused, and the loop halts with cause
  `oracle-conflict`

#### Scenario: Author and implementer keep disagreeing

- **WHEN** two `assertion` defects have been recorded for a task
- **THEN** a third `assertion` defect is refused, and the loop halts with cause
  `oracle-conflict`, carrying both positions

### Requirement: The lock is verifiable at any commit

`gates tests check --ref <commit>` SHALL evaluate the lock's conditions against that commit's tree and the change's ledger as of that commit, for every task of the change, reading nothing from the working tree or the index. A change with no handoff at that commit SHALL pass and say so.

#### Scenario: The conditions at a commit

- **WHEN** the check runs against a commit
- **THEN** it requires each placed path to hold its placed content (or its base content where a defect or halt at an uncompleted task voided the placement), the holding area to match the latest handoff, and every placed task with tests to have the red `unit` run its opening requires

#### Scenario: A locked test edited past the commit hooks

- **WHEN** a commit on the change branch changed a placed test's content and no defect voided that placement
- **THEN** `gates tests check --ref <that commit>` fails, naming the path, the task and the commit

#### Scenario: A clean head

- **WHEN** every placed path at the head matches its placed content and every placed task has its red run recorded
- **THEN** the check passes and lists the tasks it verified

#### Scenario: No authored tests

- **WHEN** the change's ledger at the commit holds no handoff
- **THEN** the check passes and reports that there are no authored tests to verify

#### Scenario: A voided placement

- **WHEN** a defect row voided a task's placement and the path holds its base content at the commit
- **THEN** the check passes for that path

#### Scenario: A halt and a reopen after completion

- **WHEN** the head carries a halt at a completed `NO-TESTS` task and a reopened task whose re-placed tests went green against its committed code
- **THEN** the check passes for both, and the merge's head proof is not stopped by either

## ADDED Requirements

### Requirement: A task is completed once its tick is committed

For the lock, a task SHALL be completed at a ledger row when the commit that checked
the task in `tasks.md` precedes the first commit carrying that row. A row not yet
committed SHALL be judged against the checked state at `HEAD`. A tick staged in the
same commit as the row SHALL NOT make the task completed at that row.

#### Scenario: A halt committed after the task's commit

- **WHEN** task 0.3's `[x]` was committed and a later commit carries a halt row for 0.3
- **THEN** task 0.3 is completed at that halt

#### Scenario: A tick staged with the halt

- **WHEN** a halt row for task 2.1 and 2.1's `[x]` are staged in the same commit
- **THEN** task 2.1 is not completed at that halt, and the halt voids its placement

### Requirement: A halt at a completed task leaves its placement in force

A `halt` row SHALL void a task's placement only when the task is not completed at that
row. At a completed task, the placement, its holding-file removals and any `NO-TESTS`
or `CHARACTERIZATION` reason SHALL keep being checked as placed.

#### Scenario: Waiting on a source after the task is done

- **WHEN** task 0.3 is a completed `NO-TESTS` task and `gates halt record oracle-conflict --task 0.3` is recorded and committed
- **THEN** later commits are not refused for 0.3's behaviour-free reason, and 0.3 needs no new placement

#### Scenario: A halt in flight

- **WHEN** a halt is recorded for the task in flight
- **THEN** its placement is voided, as before, and the task is placed again after the restart

### Requirement: A test defect at a completed task reopens it

A `test-defect` row at a completed task SHALL void its placement and open the task again. The author SHALL re-hand off the task, and `gates tests place` SHALL place it as for any task. The reopened placement SHALL be satisfied by a red `unit` run recorded after the task's first placement, so the earlier red-before-green stays the record. The reopened placement's paths SHALL hold their re-handed-off content.

#### Scenario: A late e2e mismatch on a finished task

- **WHEN** task 2.4 is completed, a `setup` defect is recorded for it, the author re-hands off, and the tests are placed again
- **THEN** the lock checks the new content, accepts the red run recorded at 2.4's first placement, and does not demand a new red run against the committed code

#### Scenario: The author re-declares a completed task

- **WHEN** a completed task with tests green on placement takes a `green` defect, and the author re-hands it off as `CHARACTERIZATION` with a reason
- **THEN** a green `unit` run after the re-placement satisfies the lock, and the reason is recorded in the handoff for review to judge

#### Scenario: A reopened test edited by the implementer

- **WHEN** a reopened task's re-placed test differs from its re-handed-off content
- **THEN** the commit is refused as for any placed test
