## MODIFIED Requirements

### Requirement: The conventions rules-doc forbids future forks
The rules-doc SHALL carry a stable rule-id forbidding forked upstream assets, replacing the rule that mandated the `/specloop:` namespace for all references.

#### Scenario: The obsolete rule is retired
- **WHEN** the rules-doc is inspected after this change
- **THEN** it contains no rule describing `/opsx:` as a legacy prefix

#### Scenario: The replacement rule resolves
- **WHEN** `gates rules` resolves rule-ids for a diff touching `commands/`
- **THEN** `no-forked-upstream-assets` is among the resolvable ids, and a review finding can cite it
