# Spec Delta

## ADDED Requirements

### Requirement: Under a declared acceptance policy the outcomes view terminates at acceptance

When the manifest declares `approval.acceptance`, `gates stats --outcomes` SHALL
derive a change's terminal state as `accepted` when the ledger holds an `acceptance`
row with verdict `accept` whose tree equals the tree recorded on the change's `merge`
row; `merged` when a `merge` row exists without such an acceptance; and otherwise as
today. Under that policy **hands-off** SHALL require `accepted`, not merely `merged`,
and the hands-off share SHALL be computed over accepted changes divided by changes
that reached `merged` or `accepted`. `acceptance` rows with verdict `reject` SHALL be
counted under halts by their cause. When no acceptance policy is declared, the
terminal-state and hands-off rules SHALL be unchanged, and the report SHALL state that
the metric ends at `merged` because no acceptance policy is declared.

#### Scenario: Accepted and merged

- **WHEN** the policy is declared and a change's ledger holds an `accept` row pinning
  tree T and a `merge` row recording tree T, with no halt, intervention or taint rows
- **THEN** the report shows terminal state `accepted` and verdict `hands-off`

#### Scenario: Merged without acceptance

- **WHEN** the policy is declared and a change's ledger holds a `merge` row but no
  `accept` row for its tree
- **THEN** the report shows terminal state `merged`, verdict `assisted`, and names the
  missing acceptance as the reason

#### Scenario: A rejection is an escalation

- **WHEN** a change's ledger holds an `acceptance` row with verdict `reject` and cause
  `missing-oracle`
- **THEN** the `--all` halts-by-cause breakdown counts one `missing-oracle`

#### Scenario: Policy undeclared

- **WHEN** the manifest has no `approval.acceptance`
- **THEN** terminal states and hands-off are computed exactly as without this change,
  and the report states that the metric ends at `merged`
