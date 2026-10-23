## MODIFIED Requirements

### Requirement: The shipped starter template validates unmodified

The starter manifest template the plugin ships SHALL pass `gates validate` when
copied to a repository without edits. Any rule-id the template references SHALL be
resolvable in the rules-doc the template points at, or the template SHALL ship no
rule-id example at all. This upholds the stated goal of `/specloop:gates-init`
that `gates validate` passes after initialization.

#### Scenario: Fresh template validates

- **WHEN** the shipped starter template is dropped into a repository as the
  manifest and `gates validate` is run against it
- **THEN** validation exits 0 with no unresolved rule-id error

#### Scenario: No dangling rule-id reference

- **WHEN** the starter template references a rule-id in a surface's `rules`
- **THEN** that rule-id is defined in the rules-doc the template's `conventions`
  block points at
