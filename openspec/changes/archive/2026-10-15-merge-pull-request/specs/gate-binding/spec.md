## MODIFIED Requirements

### Requirement: A ledger-only staged diff earns a ledger-grade commit

`discipline check-commit` SHALL allow a non-empty staged diff consisting solely of
paths under `.specloop/runs/**` without requiring a `ci` marker, printing an
explicit ledger-grade verdict. A staged diff consisting solely of ledger paths and
planning paths SHALL be held to the planning-grade requirement for its planning part,
and its verdict SHALL name the ledger paths it carried. A staged diff mixing ledger
paths with any other path SHALL be held to the full requirement for that diff.

#### Scenario: Committing only the merge row

- **WHEN** the only staged path is `.specloop/runs/<change>.jsonl`
- **THEN** the commit is allowed with a printed ledger-grade verdict, no `ci` marker
  required

#### Scenario: Committing the merge row with the archive move

- **WHEN** the staged diff holds `.specloop/runs/<change>.jsonl`, the change's move
  under `openspec/changes/archive/`, and `openspec/specs/**`
- **THEN** the commit is allowed as planning-grade, after the planning-grade checks
  pass, with no `ci` marker required, and the verdict names the ledger path

#### Scenario: A mixed diff gets no discount

- **WHEN** the staged diff contains a ledger path and a source file
- **THEN** the full commit requirement applies to the staged tree
