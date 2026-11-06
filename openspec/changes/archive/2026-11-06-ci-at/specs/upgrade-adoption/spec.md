# Spec Delta

## ADDED Requirements

### Requirement: When the full ci runs is offered as an adoption item

The catalogue SHALL hold a `ci-at` item, since 0.12.0, that applies to every project,
counts as acted on when the manifest declares `loop.ci-at`, and offers `task` and
`ready` as adopted values and leaving the key unset as declined. Its text SHALL say
that `ready` needs a declared `unit` gate and moves the full `ci` to READY.

#### Scenario: Key absent on 0.12.0

- **WHEN** a project on 0.12.0 declares no `loop.ci-at` and has not decided the item
- **THEN** `gates adoption status` lists `ci-at`

#### Scenario: Key declared

- **WHEN** the manifest declares `loop.ci-at: ready`
- **THEN** `ci-at` is not listed

#### Scenario: An earlier version

- **WHEN** the installed plugin version is 0.11.1
- **THEN** `ci-at` is not listed

### Requirement: Union-scoped ci is offered where a surface scopes ci

The catalogue SHALL hold a `ci-scope` item, since 0.12.0, that applies when any
surface declares a `ci` override and counts as acted on when the manifest declares
`loop.ci-scope`. A `surface-key` predicate SHALL accept a dotted key, read as a path
into each surface's mapping, so `gates.ci` names a surface's `ci` override.

#### Scenario: A surface declares a ci override

- **WHEN** a surface declares `gates: { ci: ... }` and the manifest declares no
  `loop.ci-scope`
- **THEN** `gates adoption status` lists `ci-scope`

#### Scenario: No surface scopes ci

- **WHEN** no surface declares a `ci` override
- **THEN** `ci-scope` is not listed

#### Scenario: A flat surface key still works

- **WHEN** a predicate names `live-check` and a surface declares one
- **THEN** the predicate holds, as before
