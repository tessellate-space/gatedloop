## MODIFIED Requirements

### Requirement: The public surface is recorded in one checked-in snapshot

The repository SHALL hold `tests/contract.json`, a snapshot of the public surface:
- `gates` subcommands and flags;
- exit codes;
- status contexts;
- manifest keys;
- the `handoff`, `stats` and `approval check --json` document keys;
- ledger fields.

Each subcommand SHALL be marked `public` or `internal`. It is `internal` only when it is listed, with a reason, as invoked solely by bundled hooks or prompts.

#### Scenario: The snapshot names an internal subcommand

- **WHEN** `tests/contract.json` is generated
- **THEN** `discipline` is recorded as `internal`, with its reason, and `run` as `public`

#### Scenario: The snapshot names every listed surface

- **WHEN** `tests/contract.json` is generated
- **THEN** it holds the reserved exit codes, every `gatedloop/<gate>` context, the top-level keys of `schema/gates.schema.json`, the top-level keys of `gates handoff --json`, `gates stats --json` and `gates approval check --json`, the ledger row fields and the row version
