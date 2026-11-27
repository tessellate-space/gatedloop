## ADDED Requirements

### Requirement: Approved preflight tests are adopted into the holding area

`gates tests adopt <change>` SHALL copy into `.gatedloop/authored/<change>/` the held
files of every task in the approved snapshot that is not stale under the preflight's
staleness rule, and SHALL print the adopted, stale and present tasks. A task already in
the holding area SHALL be left untouched as present.

#### Scenario: Every task still matches

- **WHEN** the approved snapshot holds tasks 1.1 and 1.2 with disjoint paths and neither
  task's brief changed since approval
- **THEN** `gates tests adopt` writes both tasks' held files to the holding area and
  reports no stale task

#### Scenario: A task's inputs moved after approval

- **WHEN** tasks 1.1 and 1.2 hold disjoint paths, and a path named in 1.2's `rewrites:`
  clause changed on the target after approval
- **THEN** `gates tests adopt` adopts 1.1 and reports 1.2 stale

#### Scenario: A stale task shares a path

- **WHEN** task 1.1 is stale and task 1.2 holds a path 1.1 holds
- **THEN** both are reported stale and neither is adopted

#### Scenario: A task already present

- **WHEN** task 1.1's directory already exists in the holding area
- **THEN** `gates tests adopt` leaves it untouched, reports it present, and does not list
  it in `ADOPTED.json`

#### Scenario: A task with no saved digest

- **WHEN** `tasks.md` holds task 3.1 and the snapshot has no digest for it
- **THEN** `gates tests adopt` reports 3.1 stale

#### Scenario: A kept task with no held files

- **WHEN** task 1.1's digest still matches but the snapshot holds no `authored/1.1/` files
- **THEN** `gates tests adopt` reports 1.1 stale

#### Scenario: A re-run before the handoff

- **WHEN** adoption ran once, task 1.2 was removed from the holding area, and adopt runs
  again
- **THEN** 1.2 is adopted again and `ADOPTED.json` lists both runs' tasks

#### Scenario: A snapshot found in the local branch's history

- **WHEN** the bound tree is carried by an earlier commit of the local preflight branch,
  not its tip
- **THEN** `gates tests adopt` adopts from that commit

#### Scenario: A snapshot found only on the remote

- **WHEN** the bound tree is carried only by a commit of
  `origin/gatedloop/preflight/<change>`, and not by the branch's tip
- **THEN** `gates tests adopt` adopts from that commit

### Requirement: Adoption refuses without an approved snapshot

`gates tests adopt` SHALL refuse, writing nothing, off the change's branch, when the
approval fails, when the change already has a `tests-handoff` row, or when no snapshot
with the bound tree is found. When the approved plan binds no snapshot, it SHALL say
there is nothing to adopt and exit 0.

#### Scenario: Off the change branch

- **WHEN** `gates tests adopt` runs on a branch other than the change's
- **THEN** it exits 1 and writes nothing

#### Scenario: The approval fails

- **WHEN** the plan was edited after approval
- **THEN** `gates tests adopt` exits 1 and writes nothing

#### Scenario: Already handed off

- **WHEN** the change has a `tests-handoff` row
- **THEN** `gates tests adopt` exits 1 and writes nothing

#### Scenario: A different tree recorded

- **WHEN** `ADOPTED.json` names a tree other than the bound one
- **THEN** `gates tests adopt` exits 1 and writes nothing

#### Scenario: The snapshot is missing

- **WHEN** neither the local nor the remote preflight branch's history holds a commit
  with the bound tree
- **THEN** `gates tests adopt` exits 1, naming the tree and the branch, and writes nothing

#### Scenario: No snapshot bound

- **WHEN** the approved `.openspec.yaml` has no `x-gatedloop-preflight-tree`
- **THEN** `gates tests adopt` exits 0 and says there is nothing to adopt

### Requirement: A handoff records the tests it adopted

A full, non-dry handoff with `ADOPTED.json` present SHALL record `preflight_tree` and
`adopted`, the listed tasks whose files all still match the snapshot, on its
`tests-handoff` row, and SHALL then delete `ADOPTED.json`. Adopted tests SHALL be placed,
locked and run red like any authored tests.

#### Scenario: Handing off adopted tests

- **WHEN** tasks 1.1 and 1.2 were adopted and 1.2's held file was then re-authored
- **THEN** the handoff row's `adopted` lists 1.1 only, and both tasks are placed and run
  red as usual

#### Scenario: An inline handoff

- **WHEN** a `--inline` handoff runs with `ADOPTED.json` present
- **THEN** it records `preflight_tree` and `adopted` like any full handoff and deletes the
  file

#### Scenario: A held file deleted after adoption

- **WHEN** task 1.1 was adopted and one of its held files was then deleted
- **THEN** the handoff row's `adopted` does not list 1.1

#### Scenario: A partial or dry handoff

- **WHEN** a `--task` or `--dry-run` handoff runs with `ADOPTED.json` present
- **THEN** the file is left in place and any row it appends has `preflight_tree` and
  `adopted` set to `null`

#### Scenario: No adoption

- **WHEN** the handoff runs without `ADOPTED.json`
- **THEN** its row has `preflight_tree` and `adopted` set to `null`

#### Scenario: Adopted tasks in task-list order

- **WHEN** a full handoff reads `ADOPTED.json` listing 2.1 and 1.1, and both still match
- **THEN** its row's `adopted` is `["1.1", "2.1"]`

#### Scenario: Adoption read but nothing still matches

- **WHEN** a full handoff reads `ADOPTED.json` and no task it lists still matches the
  snapshot
- **THEN** its row has `preflight_tree` set to the file's tree and `adopted` set to `[]`

#### Scenario: Any other row kind

- **WHEN** a row other than a `tests-handoff` row is appended, such as a review row
- **THEN** it has `preflight_tree` and `adopted` set to `null`

#### Scenario: The adopted tree is not readable

- **WHEN** a full, non-dry handoff runs with `ADOPTED.json` present and the tree it names
  is not readable locally
- **THEN** the handoff exits 1 naming the tree and `gates tests adopt`, appends no row,
  and leaves `ADOPTED.json` in place

### Requirement: The loop authors only what adoption leaves

The loop SHALL run `gates tests adopt` before dispatching the test author, SHALL NOT
dispatch the author when no task is stale, and SHALL otherwise dispatch it for the stale
tasks only; the author SHALL write only the tasks it is named. The authored-set review
SHALL cover the stale and present tasks, and not the adopted ones.

#### Scenario: Nothing stale

- **WHEN** adoption reports no stale task and no present task
- **THEN** the loop runs `gates tests handoff` itself without dispatching the test author,
  and skips the authored-set review

#### Scenario: Some tasks stale

- **WHEN** adoption reports 2.1 stale and 1.1 adopted
- **THEN** the author is dispatched naming 2.1 only, writes only 2.1's directory, and the
  authored-set review covers 2.1 and not 1.1

#### Scenario: A present task is reviewed

- **WHEN** adoption reports 1.2 present and no task stale
- **THEN** the author is not dispatched and the authored-set review covers 1.2

#### Scenario: Adoption refuses

- **WHEN** `gates tests adopt` exits 1 before the author would be dispatched
- **THEN** the loop halts quoting adopt's message and authors nothing

#### Scenario: Nothing to adopt

- **WHEN** `gates tests adopt` says there is nothing to adopt
- **THEN** every task is stale and the author is dispatched for the whole change

#### Scenario: The orchestrator with a bound snapshot

- **WHEN** the approved `.openspec.yaml` carries `x-gatedloop-preflight-tree` and the
  project does not declare `loop.test-author: inline`
- **THEN** the orchestrator opens the lane first, runs `gates tests adopt` in the lane
  worktree, dispatches the test author naming only the stale tasks (or runs the handoff
  itself when none is stale), commits the authoring commit there, and dispatches the
  implementer only once the handoff is recorded

#### Scenario: The orchestrator's adoption refuses

- **WHEN** the orchestrator runs `gates tests adopt` in a newly opened lane and it exits 1
- **THEN** the orchestrator removes the lane's worktree and branch, reports adopt's
  message, and dispatches nothing for that change

#### Scenario: The orchestrator under inline authoring

- **WHEN** the approved `.openspec.yaml` carries `x-gatedloop-preflight-tree` and the
  project declares `loop.test-author: inline`
- **THEN** the orchestrator opens the lane and dispatches the implementer as today, and
  the lane adopts in §5-inline

#### Scenario: The orchestrator without a bound snapshot

- **WHEN** the approved `.openspec.yaml` has no `x-gatedloop-preflight-tree`
- **THEN** the orchestrator dispatches the test author at its step 3.1 as today
