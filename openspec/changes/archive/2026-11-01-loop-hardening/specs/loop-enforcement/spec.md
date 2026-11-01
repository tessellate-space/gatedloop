## ADDED Requirements

### Requirement: A sync into a change branch creates no ungated commit

The merge hook SHALL deny a merge into a branch other than the integration target when the merge would create its own merge commit, naming the route: `git merge --no-commit <ref>`, then `gates run ci`, then `git commit`. A non-committing merge (`--no-commit`, `--squash`, `--ff-only`, `--abort`) and a fast-forward without `--no-ff` SHALL pass as before. The tdd-apply skill and the implementer SHALL give that route for syncing main.

#### Scenario: A committing sync

- **WHEN** a change branch is behind `origin/main` with commits of its own, and `git merge origin/main` runs in an agent session
- **THEN** the merge hook denies it, naming the `--no-commit`, `gates run ci`, `git commit` route

#### Scenario: The gated route

- **WHEN** `git merge --no-commit origin/main` runs on that branch, then `gates run ci` passes, then `git commit` runs
- **THEN** the merge and the commit pass, the commit is gated as any other, and the reflog audit records no taint

#### Scenario: A sync whose ref cannot be parsed

- **WHEN** a merge into a change branch names no ref the hook can parse and carries no non-committing flag
- **THEN** the merge hook denies it with the same route

#### Scenario: A fast-forward sync

- **WHEN** the change branch has no commits beyond its base and `git merge origin/main` or `git merge --ff-only origin/main` runs
- **THEN** the merge hook allows it

### Requirement: The taint refusal names the commits it found

A refusal for an unresolved taint SHALL list each tainted commit's short sha and subject, and SHALL mark a commit with more than one parent as a merge commit, pointing at the sync route.

#### Scenario: A tainting merge commit

- **WHEN** a change carries a taint for a merge commit and `gates merge <change>` runs
- **THEN** the step-1 refusal names that commit, marks it a merge commit, and gives the `gates run ci` remedy

### Requirement: The commit hook names a shared branch only when it is shared

The commit hook SHALL report that a branch is shared with another worktree only when `gates discipline check-worktree` found more than one holder. On any other failure of that check, the hook SHALL deny with the shim's own message and SHALL NOT name a shared branch.

#### Scenario: A broken manifest at commit time

- **WHEN** `.gates.yaml` holds conflict markers and `git commit` runs in an agent session
- **THEN** the commit is denied with the manifest's parse error, and the denial does not mention another worktree

#### Scenario: A genuinely shared branch

- **WHEN** the branch is checked out in two worktrees and `git commit` runs in one
- **THEN** the denial names both worktrees, as today

### Requirement: The hooks resolve home-relative and subshell directories, or deny

`gates hook git-cwd` SHALL expand `~`, `~/…`, `$HOME` and `${HOME}` in a `cd` target, and SHALL resolve a `cd` inside a leading subshell for the git invocation in that subshell. When the `cd` chain before the guarded invocation holds a target it cannot resolve statically, it SHALL exit 3 with the reason, and every hook that calls it SHALL deny, naming the target and the absolute-path or `git -C` route, instead of judging another directory.

#### Scenario: A home-relative worktree

- **WHEN** the command is `cd ~/projects/lane && git commit -m m`
- **THEN** the hook judges `$HOME/projects/lane`

#### Scenario: A subshell

- **WHEN** the command is `(cd /work/lane && git commit -m m)`
- **THEN** the hook judges `/work/lane`

#### Scenario: A target it cannot resolve

- **WHEN** the command is `cd "$LANE" && git commit -m m`
- **THEN** the commit hook denies, naming `$LANE` and the absolute-path or `git -C` route

### Requirement: The READY report's gate fields are read from the ledger

`gates ledger record-ready <change>` SHALL print the report's `gates` block, derived from the ledger and the markers for the head tree: `ci` as `pass` or `fail`; `review` as `clean`, `findings`, `partial` (some completed task has no review row) or `none` (no review row); `live_check` as `pass`, `fail` or `na`. The implementer SHALL copy that block into its final report unchanged.

#### Scenario: No review was recorded

- **WHEN** a change reaches READY with no review row in its ledger
- **THEN** `record-ready` prints `"review": "none"`, and the implementer's report carries `"review": "none"`

#### Scenario: Every completed task was reviewed clean

- **WHEN** each completed task's latest review row is clean
- **THEN** `record-ready` prints `"review": "clean"`
