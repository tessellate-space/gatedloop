## MODIFIED Requirements

### Requirement: Gate enforcement resolves the repository from the guarded command

Every hook-enforced gate check SHALL evaluate its evidence (index tree, markers,
branch, ledger) against the repository in which the guarded command will actually
execute. That repository SHALL be resolved from the guarded command itself — an
explicit `git -C <dir>`, a `GIT_DIR`/`GIT_WORK_TREE` assignment carried by the
command, git's own `--git-dir`/`--work-tree` options in either `--opt=value` or
`--opt value` form, or the last `cd <dir>` preceding the git invocation in a compound command —
before any session-derived directory is consulted. Only when the command carries no
directory signal SHALL the hook input's working directory be used, and only when that
too is absent SHALL the session project directory be the fallback. A gate MUST NOT
deny a command based on the state of a repository other than the one the command acts
on. The command-to-directory resolution SHALL be deterministic shim code with test
coverage, not shell-script parsing.

#### Scenario: A background agent commits via `cd` into a secondary worktree

- **WHEN** an agent whose shell resets its working directory per call issues
  `cd <worktree> && git commit …`, the worktree's own marker store holds a green
  required-gate marker for its staged tree, and the session cwd is the primary
  checkout
- **THEN** the commit gate evaluates the worktree named in the command — not the
  session's checkout — and allows the commit

#### Scenario: A commit names its repository with `git -C`

- **WHEN** a guarded command is issued as `git -C <worktree> commit …` from any
  working directory
- **THEN** the gate resolves `<worktree>` as the repository under check, regardless
  of the hook input's cwd

#### Scenario: A commit in a secondary worktree with a green marker

- **WHEN** an agent in a git worktree has run the required gate green on the exact
  staged tree, and the primary checkout has no such marker
- **THEN** the commit gate reads the worktree's own index and marker store and allows
  the commit

#### Scenario: A commit in a secondary worktree without a green marker

- **WHEN** an agent in a git worktree attempts to commit and no fresh required-gate
  marker matches that worktree's staged tree
- **THEN** the commit gate denies with a message naming the missing gate, regardless
  of any marker present in the primary checkout

#### Scenario: The command carries no directory signal

- **WHEN** a guarded command names no directory of its own
- **THEN** the hook input's working directory is used, falling back to the session
  project directory — behavior identical to today's in the single-checkout case

#### Scenario: The hook input carries no working directory

- **WHEN** a guarded command names no directory of its own and the gate hook receives
  input without a usable working directory field
- **THEN** it falls back to the session project directory and states nothing —
  behavior is identical to today's in the single-checkout case

#### Scenario: A commit names its repository with `--git-dir` and `--work-tree`

- **WHEN** a guarded command is issued as `git --git-dir=<worktree>/.git
  --work-tree=<worktree> commit …` from any working directory
- **THEN** the gate resolves `<worktree>` as the repository under check, exactly as
  it would for `GIT_DIR=<worktree>/.git GIT_WORK_TREE=<worktree> git commit …`
