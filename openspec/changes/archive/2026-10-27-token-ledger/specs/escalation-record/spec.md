# Spec Delta

## MODIFIED Requirements

### Requirement: Escalation causes are a closed set held in one place

The shim SHALL define exactly one closed set of escalation causes:
`missing-oracle` (no declared gate could decide the question), `weak-spec` (the spec
is ambiguous, contradictory or underspecified), `oracle-conflict` (two gates or
reviewers disagree about the same tree), `stalled` (the attempt cap was reached),
`environment` (a declared precondition failed — the gate exited 75), `budget` (the
change's token budget was reached), and `other` (anything else, which MUST carry
free-text detail). Every writer and reader of a cause SHALL resolve it against that
one definition. Extending the set SHALL be a spec change to this capability, never a
prompt-only edit.

#### Scenario: A cause outside the set is refused

- **WHEN** a halt is recorded with a cause that is not one of the seven
- **THEN** nothing is written, the command exits non-zero, and the message names the
  cause given and lists the accepted set

#### Scenario: `other` without detail is refused

- **WHEN** a halt is recorded with cause `other` and no detail text
- **THEN** nothing is written, the command exits non-zero, and the message says that
  `other` requires detail

#### Scenario: A budget halt is accepted

- **WHEN** a halt is recorded with cause `budget` after `gates run` refused on the token budget
- **THEN** the halt row is written with cause `budget`
