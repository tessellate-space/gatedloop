## ADDED Requirements

### Requirement: Onboarding records the adoption decisions it covered

When `gates-init` finishes, it SHALL record a decision for every adoption catalogue item
it walked, and SHALL leave every item it did not walk undecided. A freshly onboarded
project SHALL therefore not be told to decide something onboarding just asked about.

#### Scenario: A project finishes onboarding

- **WHEN** `gates-init` completes and walked every catalogue item
- **THEN** `gates adoption status` lists nothing, and the next session brief carries no
  adoption line

#### Scenario: The adopter declines a step during onboarding

- **WHEN** the adopter declines the test-conventions capture during `gates-init`
- **THEN** the item is recorded `declined`, and it is never raised as undecided
  afterwards
