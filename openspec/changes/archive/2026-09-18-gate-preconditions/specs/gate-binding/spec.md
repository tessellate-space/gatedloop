# gate-binding — delta for gate-preconditions

## ADDED Requirements

### Requirement: A gate may declare a precondition command

The manifest SHALL accept, for every gate value and every surface `live-check`
value, either the existing scalar command string or a mapping
`{run: <command>, requires: <command>}`. A scalar SHALL keep its exact current
behavior and be equivalent to a mapping with only `run`. `requires` is optional
and is itself just a command — the shim never inspects either body.

`gates validate` SHALL reject loudly: a mapping whose `run` is missing, not a
string, or empty; a `requires` that is present but not a non-empty string; and
any key other than `run` and `requires`.

#### Scenario: Scalar gate values are unchanged

- **WHEN** a manifest declares `gates: {ci: "make test"}` and `gates run ci` is invoked
- **THEN** behavior is byte-for-byte today's: the command runs, the exit code is returned, markers and ledger rows are written as before

#### Scenario: Mapping form validates

- **WHEN** a manifest declares `integration: {run: "cmd-a", requires: "cmd-b"}` and a surface `live-check: {run: "cmd-c", requires: "cmd-b"}`
- **THEN** `gates validate` accepts the manifest

#### Scenario: Malformed mapping fails loud

- **WHEN** a gate value is a mapping missing `run`, with an empty `requires`, or with an unknown key
- **THEN** `gates validate` exits non-zero naming the gate and the defect, and never treats the mapping as a command string

### Requirement: A failed precondition is a distinct outcome, not a gate failure

When a gate (or a hot surface's live-check) declares `requires`, `gates run`
SHALL execute the precondition first. On non-zero, the shim SHALL report
`precondition '<cmd>' failed (exit N) — the gate itself was not run`, SHALL NOT
run the gate body, SHALL NOT write the gate's marker, SHALL NOT write a ledger
row claiming the gate was exercised, and SHALL exit with the reserved
precondition exit code 75 — distinct from both success and an ordinary gate
failure and documented in the adopter-facing contract. A precondition-failure
ledger row (see manifest of record in design) MUST be distinguishable from a
gate-run row and MUST never read as a green run.

#### Scenario: Precondition fails

- **WHEN** `gates run integration` is invoked and the gate's `requires` command exits 3
- **THEN** the shim prints the precondition-failed report naming the command and its exit code, does not run the gate body, writes no `integration` marker, writes no row claiming the gate ran, and exits 75

#### Scenario: Precondition passes

- **WHEN** the gate's `requires` command exits 0
- **THEN** the gate body runs and success/failure semantics (exit code, marker, ledger row) are exactly today's

#### Scenario: Live-check precondition fails for a hot surface

- **WHEN** `gates run live-check` selects a hot surface whose `live-check` declares a `requires` that exits non-zero
- **THEN** that surface's probe body is not run, no `live-check` marker is written, and the overall run exits 75 with the precondition-failed report

#### Scenario: A precondition failure can never satisfy enforcement

- **WHEN** a precondition fails and any marker- or ledger-based check (commit gate, taint resolution) later reads the record
- **THEN** nothing written by the precondition failure satisfies the check — only a genuinely green gate run can

### Requirement: The loop treats precondition-failed as an environment problem

The tdd-apply loop and the autonomous implementer SHALL treat the precondition
exit path as "the environment was absent": the response is to fix or boot the
environment, never to modify code, retry the gate unchanged, or investigate the
gate body's output. An unattended implementer SHALL HALT at the boundary and
report the precondition failure verbatim.

#### Scenario: Autonomous implementer hits a failed precondition

- **WHEN** the tdd-implementer runs a gate whose precondition fails
- **THEN** it does not edit code and does not re-run the gate as a retry; it halts with a clean tree and reports the precondition command, its exit code, and the shim's message verbatim

#### Scenario: Interactive loop hits a failed precondition

- **WHEN** the tdd-apply skill runs a gate whose precondition fails
- **THEN** it surfaces the environment problem to the user as such, distinct from a red gate
