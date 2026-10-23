## MODIFIED Requirements

### Requirement: Undecided items are determined in code

`gates adoption status` SHALL list an item as undecided exactly when:

- its applicability predicate holds, or it has none;
- its detector reports that the project has not acted on it;
- and the project's adoption record holds no decision for it that still applies.

An `adopted` or `declined` decision always applies. A `later` decision applies until
the installed plugin version differs from the version at which it was recorded.

A catalogue item MAY be marked recurring. For a recurring item, an `adopted` decision
SHALL NOT apply: the detector alone decides whether the project has acted. A
`declined` decision SHALL apply only while the installed plugin version equals the
version at which it was recorded, as `later` does.

#### Scenario: The project already configured an item

- **WHEN** a project's manifest already sets the key an item's detector checks
- **THEN** the item is not listed, whether or not a decision was recorded

#### Scenario: The project declined an item

- **WHEN** the adoption record holds `declined` for an item that is not recurring
- **THEN** the item is never listed again

#### Scenario: The project deferred an item

- **WHEN** the adoption record holds `later` for an item, recorded at the installed
  version
- **THEN** the item is not listed until the installed plugin version changes, and is
  listed again after it does

#### Scenario: An item does not apply to the project

- **WHEN** an item's applicability predicate does not hold
- **THEN** it is not listed

#### Scenario: A recurring item was adopted at an earlier release

- **WHEN** the adoption record holds `adopted` for a recurring item and its detector
  reports that the project has not acted
- **THEN** the item is listed

#### Scenario: A recurring item was declined at an earlier release

- **WHEN** the adoption record holds `declined` for a recurring item, recorded at a
  version other than the installed one, and its detector reports that the project has
  not acted
- **THEN** the item is listed

## ADDED Requirements

### Requirement: A stale copy of the git hook is offered for refresh

The catalogue SHALL hold a recurring `git-hook-refresh` item. It SHALL apply only
when the repository's `pre-commit` hook path holds a direct copy of a Specloop hook
template. It SHALL count as acted on unless that copy's body differs from the shipped
template. A hook that delegates to the shipped template, or no hook at all, SHALL
never cause the item to be listed.

#### Scenario: The installed copy predates the shipped template

- **WHEN** `.git/hooks/pre-commit` is a direct copy of an earlier template
- **THEN** `gates adoption status` lists `git-hook-refresh`

#### Scenario: The hook delegates to the shipped template

- **WHEN** the hook path holds the composed snippet, or no hook is installed
- **THEN** `git-hook-refresh` is not listed

#### Scenario: The adopter refreshes the hook

- **WHEN** the adopter adopts `git-hook-refresh` in `/specloop:upgrade`
- **THEN** the walk runs onboarding's hook-install step, and afterwards the item is
  no longer listed

### Requirement: The confirm gate is offered where a live-check is bound

The catalogue SHALL hold a `confirm-gate` item. It SHALL apply when any surface
declares a `live-check`, and SHALL count as acted on when the manifest binds
`gates.confirm`.

#### Scenario: A surface declares a live-check and no confirm gate is bound

- **WHEN** a manifest declares `live-check` on a surface and binds no `confirm`
- **THEN** `gates adoption status` lists `confirm-gate`

#### Scenario: No surface declares a live-check

- **WHEN** no surface declares `live-check`
- **THEN** `confirm-gate` is not listed
