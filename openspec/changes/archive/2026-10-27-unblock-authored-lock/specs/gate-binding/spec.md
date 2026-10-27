# Spec Delta

## ADDED Requirements

### Requirement: A ledger-grade commit is exempt from the authored-test lock

When `discipline check-commit` returns a ledger-grade verdict, the tool-level commit hook and the git-layer commit hook SHALL allow the commit without running the authored-test lock. A ledger-grade diff touches no test and no holding file, so the lock has nothing to judge in it. A planning-grade or marker-matched commit SHALL still run the lock, as today.

#### Scenario: The merge proves the head

- **WHEN** `gates merge` commits its trailing ledger rows at step 1 on a change whose lock would fail at the staged index
- **THEN** both commit hooks allow the commit with the ledger-grade verdict, and the lock is not run

#### Scenario: A halt row committed alone

- **WHEN** the only staged path is the change's ledger and it carries a new `halt` row
- **THEN** the commit is allowed without the authored-test lock

#### Scenario: A ledger row staged with a test edit

- **WHEN** the staged diff holds the ledger and a placed test's real path
- **THEN** the verdict is not ledger-grade, and the lock runs and refuses the edited test
