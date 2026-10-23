# upgrade-adoption Specification

## Purpose
Make a plugin upgrade interactive: a shipped catalogue names each new optional setting with the version that introduced it and a detector, `gates adoption status` lists the ones this project has not yet decided, `/gatedloop:upgrade` walks them, and each answer is recorded in `.gatedloop/adoption.json` so it is asked once.

## Requirements

### Requirement: New decisions are catalogued with the release that introduced them

The plugin SHALL ship an adoption catalogue. Each item SHALL carry an id, the version
that introduced it, a one-line description, a question with options and a recommended
option, a detector, an optional applicability predicate, and an action. Detectors and
predicates SHALL come from a closed set of kinds that the shim evaluates. An unknown
kind SHALL fail loud.

#### Scenario: The catalogue names an unknown detector kind

- **WHEN** the shim evaluates a catalogue item whose detector kind it does not know
- **THEN** it exits non-zero naming the item and the kind, and reports no item as
  decided

#### Scenario: The catalogue is valid

- **WHEN** this repository's `ci` runs
- **THEN** every catalogue item is checked for its required fields, for a known
  detector kind, and for a well-formed `since` version

#### Scenario: An item for the next release on an unreleased tree

- **WHEN** a catalogue item's `since` is later than the installed plugin version
- **THEN** `gates adoption status` does not list it, and no question is asked about
  it

#### Scenario: Publishing with an item tagged for a later release

- **WHEN** `scripts/release publish` runs and a catalogue item's `since` is later
  than the version being published
- **THEN** it refuses before its first write, naming the item

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

### Requirement: Decisions are recorded by the shim in a committed file

`gates adoption record <id> <adopted|declined|later>` SHALL write the decision, the
decider, the time and the installed plugin version to `.gatedloop/adoption.json`. It
SHALL refuse an unknown item id or decision value. The file SHALL be the only place
decisions are stored, and it is meant to be committed so that a whole team shares its
decisions.

#### Scenario: A decision is recorded

- **WHEN** `gates adoption record` runs with a known id and decision
- **THEN** the file holds that decision with its decider, time and plugin version, and
  every other recorded decision is unchanged

#### Scenario: An unknown id

- **WHEN** `gates adoption record` names an id the catalogue does not define
- **THEN** it exits non-zero and writes nothing

### Requirement: The session brief says when decisions are waiting, and never asks

When undecided items exist, the SessionStart brief SHALL add one line naming the
installed version, the count of undecided items, and `/gatedloop:upgrade`. It SHALL NOT
ask a question or start the walk itself. When no item is undecided, it SHALL add
nothing.

#### Scenario: A project upgraded with three undecided items

- **WHEN** a session starts in a project with three undecided items
- **THEN** the brief carries one line naming the version, "3", and `/gatedloop:upgrade`

#### Scenario: Nothing is waiting

- **WHEN** no item is undecided
- **THEN** the brief carries no adoption line

#### Scenario: The status cannot be computed

- **WHEN** `gates adoption status` fails
- **THEN** the brief says the adoption check could not run, in one line, and the rest
  of the brief is unaffected

### Requirement: The upgrade walk asks only what is undecided and reuses onboarding

`/gatedloop:upgrade` SHALL walk only the items `gates adoption status` lists, asking one
question per item with the recommended option first and offering "decide later". It
SHALL record each answer with `gates adoption record` as soon as it is given. Where an
item's action names an onboarding step, the walk SHALL invoke that step instead of
carrying its own copy.

#### Scenario: The adopter accepts an item with an onboarding step

- **WHEN** the adopter adopts the test-conventions item
- **THEN** the walk runs onboarding's test-conventions capture, and records `adopted`
  once that step finishes

#### Scenario: The adopter stops midway

- **WHEN** the walk is interrupted after some answers
- **THEN** every answer already given is recorded, and the next walk starts from the
  first item still undecided

#### Scenario: Nothing is undecided

- **WHEN** `/gatedloop:upgrade` runs and no item is undecided
- **THEN** it says so and asks nothing

### Requirement: A stale copy of the git hook is offered for refresh

The catalogue SHALL hold a recurring `git-hook-refresh` item. It SHALL apply only
when the repository's `pre-commit` hook path holds a direct copy of a gatedloop hook
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

- **WHEN** the adopter adopts `git-hook-refresh` in `/gatedloop:upgrade`
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
