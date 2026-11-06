# Spec Delta

## ADDED Requirements

### Requirement: The plan preflight is offered to every project

The catalogue SHALL hold a `plan-preflight` item, introduced in 0.12.0, that applies to every project and counts as acted on when the manifest declares `loop.plan-preflight`. Its options SHALL be `run` (noting that it needs `loop.test-author: separate`), `skip`, and declining.

#### Scenario: A project that has not decided

- **WHEN** the installed plugin is 0.12.0 or later and the manifest does not declare `loop.plan-preflight`
- **THEN** `gates adoption status` lists `plan-preflight`

#### Scenario: A project that declared the key

- **WHEN** the manifest declares `loop.plan-preflight: skip`
- **THEN** `plan-preflight` is not listed

### Requirement: The plan preflight's cost is stated as usage

The `plan-preflight` item's question SHALL state the cost in usage terms: one extra test-author run plus one review run on every plan and on every amendment that changes the plan's tasks, design or specs. It SHALL NOT state the cost as money. Any dollar figure SHALL be labelled "API-equivalent, if you pay per token", because on a Claude subscription the runs draw on included usage and only an API-key run is billed per token.

#### Scenario: The question a project is asked

- **WHEN** `gates adoption status` lists `plan-preflight`
- **THEN** its question names the extra test-author and review runs per plan
- **AND** it gives no unlabelled money figure
