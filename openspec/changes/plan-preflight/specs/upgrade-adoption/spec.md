# Spec Delta

## ADDED Requirements

### Requirement: The plan preflight is offered to every project

The catalogue SHALL hold a `plan-preflight` item, introduced in 0.12.0, that applies to every project and counts as acted on when the manifest declares `loop.plan-preflight`. Its options SHALL be `run` (noting that it needs `loop.test-author: separate`), `skip`, and declining. Its question SHALL say that the preflight spends model tokens on every plan and on every amendment that changes the plan's tasks, design or specs.

#### Scenario: A project that has not decided

- **WHEN** the installed plugin is 0.12.0 or later and the manifest does not declare `loop.plan-preflight`
- **THEN** `gates adoption status` lists `plan-preflight`

#### Scenario: A project that declared the key

- **WHEN** the manifest declares `loop.plan-preflight: skip`
- **THEN** `plan-preflight` is not listed
