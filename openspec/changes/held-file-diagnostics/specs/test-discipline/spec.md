## ADDED Requirements

### Requirement: The lock names an unstaged or missing held file as such

When `gates tests check` finds a held file whose staged content does not match the handoff, it SHALL name the cause from the working tree: not staged (the file on disk matches; remedy `git add <state directory>`), missing (in neither the tree nor the index; remedy a restoring command), or otherwise differing, worded as before. No verdict SHALL change, and `--ref` SHALL keep its wording.

#### Scenario: A behaviour-free change checked before its holding area is staged

- **WHEN** every task of a change is handed off as `NO-TESTS` and `gates tests check` runs while the holding area is untracked
- **THEN** it exits 1, and each task's line says its `NO-TESTS` file is not staged and names `git add .gatedloop`, with no line saying the reason differs from the handoff

#### Scenario: The same change after staging

- **WHEN** the holding area of that change is staged with `git add .gatedloop` and nothing else was touched
- **THEN** `gates tests check` exits 0

#### Scenario: A held test left unstaged

- **WHEN** a held test's file on disk matches the handoff and its index entry does not
- **THEN** the line names the file as not staged, not as differing from the handoff

#### Scenario: A held test edited by hand

- **WHEN** a held test's file on disk and in the index differs from the handoff
- **THEN** the line says it differs from the handoff, worded exactly as before

#### Scenario: A NO-TESTS file gone after a voided placement

- **WHEN** a behaviour-free task's placement is voided and its `NO-TESTS` file is in neither the working tree nor the index
- **THEN** the line says it is missing from the holding area and names `gates tests handoff <change> --task <N.M>`

#### Scenario: A held test or CHARACTERIZATION declaration missing but committed

- **WHEN** a held test, or a held `CHARACTERIZATION` file, is absent from the working tree and the index, and `HEAD` holds it
- **THEN** the line says it is missing from the holding area and names `git checkout HEAD -- <path>`

#### Scenario: A held test or CHARACTERIZATION declaration missing with no committed copy

- **WHEN** a held test, or a held `CHARACTERIZATION` file, is absent from the working tree and the index, and `HEAD` lacks it
- **THEN** the line says it is missing and names the author's re-handoff of that task

#### Scenario: A CHARACTERIZATION declaration left unstaged

- **WHEN** a held `CHARACTERIZATION` file on disk matches the handoff's declaration and its index entry does not
- **THEN** the line names the file as not staged, not as differing from the handoff

#### Scenario: Classifying a mismatch writes no object

- **WHEN** the staged check classifies a held file's mismatch against the working tree, and no placed path mismatches
- **THEN** the object store holds the same objects after the check as before it

#### Scenario: A commit checked with --ref

- **WHEN** `gates tests check --ref <commit>` finds a held file that differs from the handoff in that commit's tree
- **THEN** its line is worded as before this requirement

### Requirement: A per-task re-handoff restores a recorded behaviour-free reason

A real `gates tests handoff <change> --task <N.M>` SHALL, before any holding-area refusal, restore `<N.M>`'s `NO-TESTS` file with its recorded reason when `<N.M>`'s directory holds no file, the handoff declares it behaviour-free, it has no placement in force, and its oracle tag allows that. It SHALL record no row, name the `git add` to run, and exit 0. Every other case SHALL behave as before; `--dry-run` never restores.

#### Scenario: A discarded behaviour-free task is restored

- **WHEN** task 1.1 was handed off as `NO-TESTS`, placed, and its placement voided, and its `NO-TESTS` file is gone
- **THEN** `gates tests handoff <change> --task 1.1` writes the file back with the recorded reason, appends no ledger row, exits 0, and once the file is staged `gates tests check` reports no problem for task 1.1

#### Scenario: The only task left in an empty holding area

- **WHEN** every task of a change is behaviour-free, every other task is placed, and task 1.1's voided placement left the holding area with no file at all
- **THEN** `gates tests handoff <change> --task 1.1` restores 1.1's `NO-TESTS` file rather than refusing the holding area as empty

#### Scenario: An empty task directory left on disk

- **WHEN** task 1.1 is behaviour-free in the handoff, unplaced, and its directory exists with no file in it
- **THEN** the per-task handoff restores its `NO-TESTS` file rather than refusing the directory as holding nothing

#### Scenario: A placed behaviour-free task is not restored

- **WHEN** task 1.1's `NO-TESTS` placement is in force and its holding directory is empty
- **THEN** the per-task handoff refuses as before, and writes nothing

#### Scenario: A task with tests is not restored

- **WHEN** task 1.2 was handed off with tests and its holding directory is empty
- **THEN** the per-task handoff refuses as before, and writes nothing

#### Scenario: A restore the plan now contradicts

- **WHEN** task 1.1's recorded reason is `NO-TESTS` but the approved plan now tags it with a gate
- **THEN** the per-task handoff refuses with the oracle-tag contradiction, and writes nothing
