# Spec Delta

## ADDED Requirements

### Requirement: The lock is verifiable at any commit

`gates tests check --ref <commit>` SHALL evaluate the lock's conditions against that commit's tree and the change's ledger as of that commit, for every task of the change, reading nothing from the working tree or the index. A change with no handoff at that commit SHALL pass and say so.

#### Scenario: The conditions at a commit

- **WHEN** the check runs against a commit
- **THEN** it requires each placed path to hold its placed content (or its base content where a defect or halt voided the placement), the holding area to match the latest handoff, and every placed task with tests to have a red `unit` run recorded after its placement

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
