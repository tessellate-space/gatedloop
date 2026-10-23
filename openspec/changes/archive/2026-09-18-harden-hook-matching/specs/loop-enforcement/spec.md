## ADDED Requirements

### Requirement: Gate hooks fire on the actual invocation, not a substring

A `PreToolUse` gate hook SHALL decide whether a command is a guarded invocation by
examining the command's parsed token structure, not by raw substring containment.
Specifically: the guarded verb MUST appear as the subcommand token of its program
(`merge` as git's subcommand, `archive` as openspec's, `new change` as openspec's),
with the program's global flags (for git: `-C <path>`, `-c <key>=<value>`,
`--git-dir=…`, `--work-tree=…`, pager flags) and leading environment assignments or
common wrappers skipped when locating that token. Compound commands (joined by
`&&`, `||`, `;`, `|`) SHALL be split into simple commands and each examined. A
token that merely *contains* the guarded phrase — a hyphenated sibling subcommand,
or prose inside a quoted argument — SHALL NOT trigger the gate. All Bash-matching
gate hooks SHALL share one matching implementation; per-hook ad-hoc patterns are
not permitted.

#### Scenario: A read-only merge-family query is not gated

- **WHEN** a session runs `git merge-base --is-ancestor A B` (or `git merge-tree`,
  `git merge-file`) with no fresh live-check marker present
- **THEN** the merge gate does not fire and the command proceeds, because
  `merge-base` is not the `merge` subcommand

#### Scenario: Quoted prose mentioning a guarded command is not gated

- **WHEN** a session runs a command whose quoted argument text contains the words
  "git merge" (for example `gh issue create --body "… git merge …"`)
- **THEN** no gate fires, because the phrase sits inside an argument token, not in
  command position

#### Scenario: A guarded invocation phrased with global flags is still gated

- **WHEN** a session runs `git -C /path/to/repo merge some-branch` (or
  `git -c core.editor=true merge …`) without the required fresh marker
- **THEN** the merge gate fires and denies it, because the subcommand token after
  git's global flags is `merge`

#### Scenario: A guarded invocation inside a compound command is still gated

- **WHEN** a session runs `cd /repo && git merge some-branch` without the required
  fresh marker
- **THEN** the merge gate fires and denies it, because each simple command in the
  compound is examined

#### Scenario: An unparseable command falls back conservatively

- **WHEN** a command string cannot be tokenized (for example unbalanced quotes) and
  it contains a guarded phrase as a substring
- **THEN** the gate still fires, preserving the raise-the-floor posture: parse
  failure never becomes a bypass

#### Scenario: Per-gate arguments are extracted from the matched command

- **WHEN** a gate needs an argument from the invocation (the change name after
  `openspec archive`, the branch name after `checkout -b` / `switch -c`)
- **THEN** the argument is read from the matched simple command's own tokens, never
  by scanning the whole command string for a flag that may belong to a different
  command

### Requirement: An archive-move commit is classified as what it is

The planning-grade commit classification SHALL treat the `archive` path segment
directly under the changes directory as the reserved archive namespace, never as a
change id. For a staged archive move, per-change OpenSpec validation SHALL NOT be
attempted against the literal segment `archive`, and SHALL NOT be attempted against
a change directory that the staged move removes from the working tree. Manifest
validation SHALL still run, and the merge-precedes-archive guarantee SHALL remain
enforced by the archive gate, not by this classification.

#### Scenario: An archive move commits at planning grade

- **WHEN** a change has been merged to the target branch, `openspec archive` has
  moved its directory under the changes directory's `archive/` namespace, and the
  session stages exactly that move and commits
- **THEN** the commit is allowed at planning grade — the manifest validates, no
  `openspec validate archive` is attempted, and no green `ci` marker is demanded
  for a pure planning-tree move

#### Scenario: Archiving an unmerged change is still denied

- **WHEN** a session attempts `openspec archive <change>` for a change not yet
  merged to the resolved target branch
- **THEN** the archive gate denies it, unchanged by this classification fix

### Requirement: Every enforcement denial names its unmet prerequisite and remedy

Every denial emitted by an enforcement hook or the discipline checks behind it
SHALL name the precise prerequisite that is unmet and the exact command that
satisfies it. A denial whose remedy can only be discovered by inspecting prior
commits or reading the enforcement source is a defect.

#### Scenario: A denied archive names the merge prerequisite and the remedy

- **WHEN** the archive gate denies `openspec archive <change>` because the change
  is not on the resolved target branch
- **THEN** the denial names the change and the target branch and states the
  satisfying action (merge the change branch to the target — and push, where the
  check reads the remote ref) before retrying

#### Scenario: A denied commit names the gate to run

- **WHEN** the commit gate denies a commit because no fresh marker matches the
  staged tree, or because a staged planning artifact fails validation
- **THEN** the denial names which check failed and the exact command to run
  (`gates run ci`, or the failing `openspec validate <change>`) before committing
  again
