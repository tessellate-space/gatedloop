## ADDED Requirements

### Requirement: Recording plan send-backs is offered to every project

The catalogue SHALL hold a `plan-returns` item, introduced in 0.14.0, that applies to every project and counts as acted on when the manifest declares `loop.plan-returns`. Its question SHALL say that under `record` the propose path and the planner append a `plan-returned` row, with the sender's exact words, to the change's ledger each time a plan is sent back, and that the ledger is committed with the plan. Its options SHALL be `record`, `skip`, and declining.

#### Scenario: Listed until decided

- **WHEN** the installed plugin is 0.14.0 or later and the manifest does not declare `loop.plan-returns`
- **THEN** `gates adoption status` lists `plan-returns`

#### Scenario: Decided

- **WHEN** the manifest declares `loop.plan-returns: skip`
- **THEN** `plan-returns` is not listed
