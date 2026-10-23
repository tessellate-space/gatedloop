## ADDED Requirements

### Requirement: Hook matching ignores redirections, heredoc bodies and help invocations

The command matcher SHALL NOT take a redirection token as an argument, SHALL NOT scan
the body of a heredoc for guarded invocations, and SHALL NOT treat a guarded command
carrying `--help` or `-h` as a guarded invocation. When a merge invocation matches but
no incoming ref can be parsed, the merge denial SHALL say that no ref was parsed rather
than reporting a stale marker.

#### Scenario: A squash merge with a trailing redirection

- **WHEN** the command is `git merge --squash <change> 2>&1`
- **THEN** the matcher extracts `<change>` as the incoming ref

#### Scenario: A heredoc mentions a gated command

- **WHEN** a command's heredoc body contains a guarded invocation as text
- **THEN** no hook treats it as that invocation

#### Scenario: A help invocation

- **WHEN** the command is `openspec archive --help 2>&1`
- **THEN** the archive hook does not treat it as archiving a change

#### Scenario: No ref can be parsed

- **WHEN** a merge invocation matches and its incoming ref cannot be extracted
- **THEN** a denial names that as the reason and does not mention a stale marker

### Requirement: Only integration merges are gated

The merge hook SHALL gate only a merge whose destination is the integration target. A
merge into any other branch SHALL pass the hook without a marker check.

#### Scenario: Syncing the target into a change branch

- **WHEN** a change branch is checked out and the integration target is merged into it
- **THEN** the merge hook allows it without requiring a live-check marker

#### Scenario: Integrating a change

- **WHEN** the integration target is checked out and a change branch is merged into it
- **THEN** the merge hook applies its marker checks as before

### Requirement: Editing a file never clears gate evidence

No hook SHALL clear a gate marker in response to a file write or edit. Gate markers
SHALL be invalidated only by their tree key no longer matching the tree being
committed or merged.

#### Scenario: A scratch file is written between the gate and the commit

- **WHEN** `gates run ci` passes, a file outside the staged set is written, and the
  commit is attempted with the same staged tree
- **THEN** the commit is allowed

#### Scenario: Another lane writes a file

- **WHEN** one worktree writes a file while another worktree holds a green marker
- **THEN** the other worktree's marker is unaffected

### Requirement: A stale-marker denial names what changed

When a commit is denied because the staged tree differs from the tree the `ci` marker
recorded, the denial SHALL list the paths that differ. When every differing path is
one newly staged since the marker was written, it SHALL say that those files were
staged after the gate ran.

#### Scenario: A new file staged after the gate

- **WHEN** `gates run ci` passed, a new file was then staged, and a commit is attempted
- **THEN** the denial names that file as staged after the gate ran and directs a
  re-run of the gate

### Requirement: The propose gate resolves proposal state without relying on HEAD

The propose gate SHALL decide whether a planning write is allowed from the change's
own state, whether its directory is tracked on the integration target, and SHALL
accept a detached HEAD. Every planning artifact path SHALL be treated consistently.

#### Scenario: Planning while the primary checkout is detached

- **WHEN** HEAD is detached for a merge step and a planning artifact is written for a
  change that is not in implementation
- **THEN** the write is allowed

#### Scenario: A tracked change directory

- **WHEN** a change directory is tracked on the integration target
- **THEN** the gate never describes it as untracked or unproposed

### Requirement: Only a branch that names an active change is a change

A branch SHALL be treated as a change, for ledger keying and every gate that resolves
a change from the branch, only when `openspec/changes/<branch>/` exists. A `--change`
value containing `/` SHALL be refused. On a detached HEAD with no `--change`, `gates
run` SHALL say that no ledger row was written.

#### Scenario: A planning branch

- **WHEN** `gates run ci` runs on a `plan/<name>` branch
- **THEN** no ledger row is written under `.specloop/runs/`

#### Scenario: A documentation branch

- **WHEN** `gates run ci` runs on a branch with no matching change directory
- **THEN** no ledger file is created for that branch

#### Scenario: A slash in an explicit change name

- **WHEN** `--change plan/<name>` is passed
- **THEN** the command refuses and names the bare change name to use instead

### Requirement: A branch checked out in more than one worktree cannot be committed to

The commit gates SHALL refuse a commit when the current branch is checked out in more
than one worktree. The implementer SHALL NOT force a checkout.

#### Scenario: A lane shares a branch with the primary

- **WHEN** a commit is attempted in a worktree whose branch is also checked out in
  another worktree
- **THEN** the commit is denied, naming both worktrees
