## ADDED Requirements

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

#### Scenario: The project already configured an item

- **WHEN** a project's manifest already sets the key an item's detector checks
- **THEN** the item is not listed, whether or not a decision was recorded

#### Scenario: The project declined an item

- **WHEN** the adoption record holds `declined` for an item
- **THEN** the item is never listed again

#### Scenario: The project deferred an item

- **WHEN** the adoption record holds `later` for an item, recorded at the installed
  version
- **THEN** the item is not listed until the installed plugin version changes, and is
  listed again after it does

#### Scenario: An item does not apply to the project

- **WHEN** an item's applicability predicate does not hold
- **THEN** it is not listed

### Requirement: Decisions are recorded by the shim in a committed file

`gates adoption record <id> <adopted|declined|later>` SHALL write the decision, the
decider, the time and the installed plugin version to `.specloop/adoption.json`. It
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
installed version, the count of undecided items, and `/specloop:upgrade`. It SHALL NOT
ask a question or start the walk itself. When no item is undecided, it SHALL add
nothing.

#### Scenario: A project upgraded with three undecided items

- **WHEN** a session starts in a project with three undecided items
- **THEN** the brief carries one line naming the version, "3", and `/specloop:upgrade`

#### Scenario: Nothing is waiting

- **WHEN** no item is undecided
- **THEN** the brief carries no adoption line

#### Scenario: The status cannot be computed

- **WHEN** `gates adoption status` fails
- **THEN** the brief says the adoption check could not run, in one line, and the rest
  of the brief is unaffected

### Requirement: The upgrade walk asks only what is undecided and reuses onboarding

`/specloop:upgrade` SHALL walk only the items `gates adoption status` lists, asking one
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

- **WHEN** `/specloop:upgrade` runs and no item is undecided
- **THEN** it says so and asks nothing
