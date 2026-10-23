# gate-binding Delta Specification

## ADDED Requirements

### Requirement: Brace alternation in match patterns is honored or rejected, never ignored

A `{a,b}` alternation in a surface's `match` pattern SHALL select exactly the union of
paths its expanded alternatives select, including multiple and nested groups. A brace
construct the matcher cannot expand (for example an unbalanced `{`) SHALL be a
`gates validate` error naming the surface and the pattern. Under no circumstance SHALL
a brace pattern silently match nothing.

#### Scenario: A brace glob selects its alternatives

- **WHEN** a surface declares `match: "{bin,tests}/**"` and a file under `bin/` or
  `tests/` is in the diff
- **THEN** `gates surfaces` reports that surface hot, and `gates rules` includes its
  rules

#### Scenario: Multiple and nested groups

- **WHEN** a `match` pattern contains more than one `{...}` group, or a group nested
  inside another
- **THEN** the pattern selects the union of the fully expanded alternatives

#### Scenario: An unexpandable brace pattern fails validation

- **WHEN** a `.gates.yaml` surface's `match` contains a brace construct the matcher
  cannot expand
- **THEN** `gates validate` exits non-zero with a message naming the surface and the
  offending pattern
