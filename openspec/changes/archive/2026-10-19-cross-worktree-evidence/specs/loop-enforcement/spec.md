## ADDED Requirements

### Requirement: A merge counts evidence recorded in the incoming branch's worktree

When a merge brings in a local branch that is checked out in another worktree, the
merge gate SHALL accept a marker from that worktree's marker store as well as from
the store of the worktree the merge runs in. A marker counts only if it matches the
incoming ref's tree, exactly as one in the merging worktree's own store must. The
same lookup SHALL serve the merge hook and `gates merge`. A denial SHALL name every
store it read. The commit gate SHALL NOT consult another worktree's store.

#### Scenario: Merging from the primary after proving the lane

- **WHEN** the change branch is checked out in a lane worktree, `gates run
  live-check` and an unscoped `gates run ci` passed green in the lane on the branch
  head, and `git -C <primary> merge --squash <change>` is issued from any working
  directory
- **THEN** the merge hook finds both markers in the lane's store and allows the merge

#### Scenario: The lane holds uncommitted work

- **WHEN** the lane's markers were recorded on a tree that the change branch's head
  does not point at
- **THEN** the merge hook denies the merge, naming the primary's store and the lane's
  store as the places it looked

#### Scenario: A commit in the primary is not vouched for by the lane

- **WHEN** the lane holds a green `ci` marker for a tree and the same tree is staged
  in the primary checkout, which has no marker of its own
- **THEN** the commit gate in the primary denies the commit

### Requirement: Hook installation and inspection use git's effective hooks directory

`gates hook install`, `gates doctor`'s hook check and the adoption hook detectors
SHALL locate the `pre-commit` hook in the directory git itself runs hooks from, as
`git rev-parse --git-path hooks` reports it. They SHALL NEVER read or write a linked
worktree's private git directory. Run from any worktree of a repository, they SHALL
report the same hook state.

#### Scenario: Doctor run from a linked worktree

- **WHEN** the hook is installed in the repository and `gates doctor` runs in a
  linked worktree
- **THEN** the hook row reports it installed, as it does in the primary checkout

#### Scenario: Install run from a linked worktree

- **WHEN** `gates hook install` runs in a linked worktree of a repository with no
  hook
- **THEN** it writes the hook to the repository's shared hooks directory, names that
  path, and the hook fires for a commit in the primary checkout
