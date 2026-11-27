# Spec Delta

## ADDED Requirements

### Requirement: A behaviour or setup defect cites evidence the shim can resolve

`gates tests defect --kind setup|assertion` SHALL require at least one `--cite`. A citation SHALL be a repository path, a path with a line (`path:line`) or a line range (`path:a-b`), or a spec scenario (`spec:<capability>#<scenario name>`). The shim SHALL refuse the defect, naming each citation that does not resolve, and SHALL store the citations on the row.

#### Scenario: A defect with no citation is refused
- **WHEN** the implementer runs `gates tests defect 2.1 --kind assertion --detail "wrong status code"` with no `--cite`
- **THEN** it exits 1, records nothing, and says a citation is required with the accepted forms

#### Scenario: A citation that does not resolve is refused
- **WHEN** a defect cites `src/api.py:900` and that file has fewer than 900 lines
- **THEN** it exits 1, records nothing, and names `src/api.py:900`

#### Scenario: A spec scenario resolves
- **WHEN** a defect cites `spec:checkout#Expired card is declined` and that scenario exists in the change's delta specs or the main specs
- **THEN** the defect is recorded with that citation

#### Scenario: A placed test is citable
- **WHEN** a defect for task 2.1 cites `tests/test_orders.py:12`, the placed test it disputes, and that file has at least 12 lines
- **THEN** the citation resolves and the defect is recorded with it

#### Scenario: A line range resolves within the file
- **WHEN** a defect cites `tests/test_orders.py:10-14` and that file has at least 14 lines
- **THEN** the citation resolves; a range ending past the file's last line, or starting after its end, does not

#### Scenario: A green defect takes no citation
- **WHEN** the implementer passes `--cite` with `--kind green`
- **THEN** it exits 1, records nothing, and says a green defect's evidence is its recorded run

### Requirement: A green defect is backed by a recorded passing run

`gates tests defect --kind green` SHALL be refused unless the change's ledger holds a passing run of the task's oracle gate recorded after the task's latest placement (the latest `tests-placed` row carrying the task).

#### Scenario: Green with no passing run
- **WHEN** the implementer records a `green` defect for task 2.1 and the only run of its oracle gate since placement failed
- **THEN** it exits 1 and says no passing run of that gate has been recorded since placement

#### Scenario: Green with a passing run
- **WHEN** a passing run of task 2.1's oracle gate is recorded after its placement
- **THEN** the `green` defect is recorded

#### Scenario: A passing run before the latest placement does not count
- **WHEN** task 2.1 was placed, passed, and was placed again after a re-handoff, and no run of its oracle gate is recorded since the second placement
- **THEN** a `green` defect for task 2.1 exits 1 and records nothing

#### Scenario: Green before placement
- **WHEN** the implementer records a `green` defect for task 2.1 and its tests have not been placed
- **THEN** it exits 1 and records nothing

### Requirement: A defence is recorded and cannot change the tests

`gates tests handoff <change> --task <N.M> --defend <why>` SHALL record a `test-defence` row answering the task's latest defect, with at least one `--cite` resolved as defects' are. It SHALL be refused when the task has no unanswered defect, or when the task's held tests differ from its previous handoff.

#### Scenario: A defence is recorded
- **WHEN** the author re-hands off task 2.1 unchanged with `--defend "the spec requires 409" --cite "spec:orders#Duplicate order is rejected"`
- **THEN** a `test-defence` row is recorded against the latest defect, with the citation

#### Scenario: A defence that edits the tests is refused
- **WHEN** the author passes `--defend` but has changed a held test for task 2.1
- **THEN** the handoff exits 1 and says changed tests are a revision, to be handed off without `--defend`

#### Scenario: A defence with nothing to answer is refused
- **WHEN** the author passes `--defend` for a task with no defect since its last handoff
- **THEN** the handoff exits 1 and records nothing

#### Scenario: A defence must name its task and its evidence
- **WHEN** the author passes `--defend` without `--task`, or without a `--cite`
- **THEN** the handoff exits 1 and records nothing

#### Scenario: A dry run cannot defend
- **WHEN** the author passes `--defend` with `--dry-run`
- **THEN** the handoff exits 1 and says a dry run records nothing, so it cannot record a defence

#### Scenario: A defence may cite the held copy
- **WHEN** the author defends task 2.1 citing `.gatedloop/authored/<change>/2.1/tests/test_orders.py.authored:12`, its held copy
- **THEN** the citation resolves and the defence is recorded

#### Scenario: A defence citing evidence that does not resolve is refused
- **WHEN** the author passes `--defend` with `--cite src/missing.py`, and that file does not exist
- **THEN** the handoff exits 1, records nothing, and names `src/missing.py`

#### Scenario: A citation without a defence is refused
- **WHEN** the author passes `--cite` to `gates tests handoff` without `--defend`
- **THEN** the handoff exits 1 and records nothing

### Requirement: Both positions reach the human with their evidence

`gates tests show` SHALL list each defect with its citations and the defence that answered it, if any. The refusal past the `assertion` cap SHALL print every defect and defence for the task with their citations.

#### Scenario: Show lists the exchange
- **WHEN** task 2.1 has one assertion defect and one defence
- **THEN** `gates tests show` lists both, each with its citations, in order

#### Scenario: The cap refusal carries both sides
- **WHEN** a third `assertion` defect for task 2.1 is refused
- **THEN** the refusal prints both earlier defects and the author's defences, each with its citations

### Requirement: A change handed off earlier keeps its rules

The citation, passing-run and defence checks SHALL apply to a task only when the handoff that governs it (the latest `tests-handoff` row that is a full handoff or a `--task` handoff of that task) was recorded by a shim that has them. A task governed by an earlier handoff SHALL keep accepting defects without citations, and `green` defects without a recorded passing run.

#### Scenario: An in-flight change is not broken by the upgrade
- **WHEN** a task's governing handoff row predates this change and the implementer records a defect with no `--cite`
- **THEN** the defect is recorded as before

#### Scenario: An in-flight change keeps its green defects
- **WHEN** a task's governing handoff row predates this change and the implementer records a `green` defect with no passing run recorded since placement
- **THEN** the defect is recorded as before

#### Scenario: A task re-handed off after the upgrade takes the new rules
- **WHEN** a task of an in-flight change is re-handed off by the upgraded shim and the implementer then records a defect with no `--cite`
- **THEN** the defect is refused
