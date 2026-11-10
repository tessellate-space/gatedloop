## MODIFIED Requirements

### Requirement: A task is completed once its tick is committed

For the lock, a task SHALL be completed at a ledger row when the commit that checked
the task in `tasks.md` precedes the first commit carrying that row. A row not yet
committed SHALL be judged against the checked state at `HEAD`. A tick staged in the
same commit as the row SHALL NOT make the task completed at that row.
The commits SHALL be read along the change branch's own first-parent line, starting at
the first parent of the branch's first commit after its merge-base with the target, so a
target's copy of the ledger is never compared with the branch's. A ledger that shrinks
along that line SHALL be refused, naming the commit.

#### Scenario: A halt committed after the task's commit

- **WHEN** task 0.3's `[x]` was committed and a later commit carries a halt row for 0.3
- **THEN** task 0.3 is completed at that halt

#### Scenario: A tick staged with the halt

- **WHEN** a halt row for task 2.1 and 2.1's `[x]` are staged in the same commit
- **THEN** task 2.1 is not completed at that halt, and the halt voids its placement

#### Scenario: Approval rows appended on the target after the lane forked

- **WHEN** a plan amendment's approval rows were appended to the change's ledger on the
  target after the lane forked, the lane merged the target in, a halt row names task 7.1,
  and 7.1's `[x]` is staged
- **THEN** `gates tests check` and `gates tests check --ref HEAD` do not report lost rows

#### Scenario: A ledger shrunk on the lane

- **WHEN** a commit on the change branch's first-parent line carries fewer ledger rows
  than its first parent
- **THEN** `gates tests check` refuses, naming that commit
