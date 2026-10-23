# Spec Delta

## MODIFIED Requirements

### Requirement: Merge is blocked unless the live self-check passed on the branch head
A `git merge` SHALL be denied unless a fresh `live-check` marker matches the current
branch head. When the manifest declares an acceptance policy, the merge SHALL
additionally be denied unless the ledger's latest `acceptance` row for the same tree
has verdict `accept` (see the acceptance-gate capability); when no acceptance policy is
declared, this additional check SHALL pass stating that acceptance is not required.
The existing `ask` permission rule on `git merge` SHALL remain: the ask is the human's
presence at the merge, the acceptance row is the human's recorded verdict on the
behaviour, and neither substitutes for the other.

#### Scenario: Merge after green live-check
- **WHEN** `gates run live-check` passed on the branch head and it has not advanced
- **THEN** the hook allows the `git merge`

#### Scenario: Merge attempted without a live-check marker
- **WHEN** a `git merge` is attempted with no matching `live-check` marker
- **THEN** the hook denies the merge and reports that the live self-check must pass first

#### Scenario: Merge without acceptance under a declared policy
- **WHEN** `approval.acceptance` is declared, the live-check marker matches and no taint
  is outstanding, but no `accept` row pins the incoming tree
- **THEN** the hook denies the merge and names the acceptance brief and attestation
  commands as the remedy

#### Scenario: Merge with acceptance under a declared policy
- **WHEN** `approval.acceptance` is declared and an `accept` row pins the incoming tree
  with no later `reject` for it
- **THEN** the hook allows the `git merge`, given the live-check and taint checks also
  pass

#### Scenario: Merge with no acceptance policy
- **WHEN** the manifest declares no `approval.acceptance`
- **THEN** the acceptance check passes without consulting the ledger and the merge is
  governed by the live-check, unscoped-`ci` and taint checks exactly as before

### Requirement: The implementer emits a machine-readable final report
`tdd-implementer` SHALL end with a structured report so headless runs are queryable
without parsing prose. When the outcome is a halt, the report SHALL carry the cause
that was recorded in the ledger, and the ledger row SHALL be written before the report
is emitted — the report echoes the record; it is never the record. The report SHALL
also state whether a human acceptance step remains before the change can merge, read
from the declared policy, and the implementer SHALL generate the acceptance brief as
its last act before the report so the human's next step is already on screen.

#### Scenario: Report is structured
- **WHEN** an autonomous run finishes or halts
- **THEN** its final report contains `change`, `tasks_done`, `tasks_total`, `branch`,
  `gates`, `outcome`, `cause` and `acceptance` as parseable fields

#### Scenario: A halt names its cause
- **WHEN** the run halts
- **THEN** `gates halt record <cause> --task <N.M>` has already appended the `halt`
  row, and the report's `cause` equals that row's cause

#### Scenario: A completed run has no cause
- **WHEN** the run ends `READY TO MERGE`
- **THEN** `cause` is `null`

#### Scenario: Acceptance is required
- **WHEN** the run ends `READY TO MERGE` and the manifest declares
  `approval.acceptance`
- **THEN** `acceptance` is `"required"`, and the acceptance brief was printed
  immediately before the report

#### Scenario: Acceptance is not required
- **WHEN** the manifest declares no acceptance policy
- **THEN** `acceptance` is `"not-required"`, and the brief is still printed as
  information for the human who merges

### Requirement: The forge merge path is covered by documented branch protection for pull-request modes

For `pull-request` integration modes, project documentation SHALL state that forge
branch protection is required, because the forge merge path (`gh pr merge` or a
forge-UI merge) has no local git-hook equivalent and is not covered by the commit or
merge hooks. Specloop SHALL NOT implement a forge-side merge gate itself. Where
`approval.acceptance: review` is declared, the documentation SHALL state that the
required review on the default branch is the acceptance review — the one `gates
acceptance attest --pr` reads — so that the forge path and the local path require the
same human act.

#### Scenario: A pull-request mode is documented

- **WHEN** an adopter configures `integration.mode: pull-request`
- **THEN** the documentation names branch protection on the default branch as a
  requirement and states which checks/reviews to protect

#### Scenario: The local merge path is distinguished from the forge path

- **WHEN** the documentation describes enforcement coverage
- **THEN** it states plainly that the local `git merge` path is covered by the merge
  gate while the forge merge path is covered only by branch protection

#### Scenario: Acceptance under review on the forge path

- **WHEN** an adopter configures `approval.acceptance: review` with
  `integration.mode: pull-request`
- **THEN** the documentation states that the protected branch's required review is the
  acceptance review, and that `gates acceptance attest --pr` records it into the
  ledger so the outcomes view can see it
