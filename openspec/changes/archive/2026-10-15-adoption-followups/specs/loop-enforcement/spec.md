## MODIFIED Requirements

### Requirement: The git-layer commit hook installs without clobbering an existing hook

Installation of the git `pre-commit` hook SHALL be performed by deterministic shim
code (`gates hook install`), not by prompt prose. It SHALL detect who owns the hook
path — a hook manager (husky, lefthook, the `pre-commit` framework), a `core.hooksPath`
redirect, or a bare existing `.git/hooks/pre-commit` — and SHALL compose with it where
a safe composition is determinable, and refuse-and-instruct where it is not. It SHALL
NEVER overwrite an existing hook or hook-manager configuration, with one exception: a
direct copy of a Specloop hook template whose body differs from the shipped template
SHALL be replaced with the shipped template, after its previous body is saved beside
it.

#### Scenario: An existing hook is present

- **WHEN** `gates hook install` runs in a repository that already has a `pre-commit`
  hook or a recognized hook manager
- **THEN** it composes the `gates` check into the existing flow without overwriting
  what is there

#### Scenario: The hook topology cannot be classified safely

- **WHEN** `gates hook install` cannot determine a safe way to compose with the
  existing hook setup
- **THEN** it refuses to modify anything and reports how to wire the check by hand,
  rather than clobbering

#### Scenario: No hook is present

- **WHEN** `gates hook install` runs in a repository with no existing `pre-commit`
  hook and no hook manager
- **THEN** it installs the shipped hook template directly

#### Scenario: A stale direct copy is present

- **WHEN** `gates hook install` runs and the hook path holds a direct copy of an
  earlier Specloop template
- **THEN** it saves the old body to `pre-commit.specloop-prev` beside the hook,
  writes the shipped template in its place, keeps it executable, and names both paths

#### Scenario: A current direct copy is present

- **WHEN** `gates hook install` runs and the hook path holds a byte-identical copy of
  the shipped template
- **THEN** it changes nothing and says the hook is already installed
